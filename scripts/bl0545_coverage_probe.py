"""BL-0545 Phase 1 -- 唯讀「五維健康評級資料覆蓋」探針(獨立、離線、非 production decision)。

授權:客戶於 PR #1167 留言「核准唯讀探針」(DEC-2026-11-07-03)。協定出處:
`docs/evidence/bl0545_active_sheet_coverage_probe_status_2026_11_07.md` 第 4 節。

本檔是什麼
==========
- 單檔、獨立腳本;**沒有任何 production 呼叫端**,不被任何 production 模組 import。
- 輸入:使用者自備的匿名基金代號清單(`--codes-file`)與/或離線 fixture(`--fixture`)。
- 輸出:協定第 4.2 節的 JSON(schema `bl0545_probe_output_v1`):三層分母、五維分項狀態、
  缺值/抓取失敗原因、來源/時間/版本證據。只陳述計數與原因代碼。

本檔不是什麼
============
- **不是**真實 Active Sheet 覆蓋率。Active Sheet 讀取**本批不實作、不呼叫**;輸出固定標
  `real_active_sheet_coverage: "NOT VERIFIED"`。
- **不是**准入判定。不產出任何總結燈號;輸出固定標 `admission: "NOT DEFINED"`。
- **live 抓取模式:NOT IMPLEMENTED**(本批不新增來源、不改 production、本環境無網路與使用者憑證,
  未實測)。每檔資料只能來自 fixture 或呼叫端注入的 `fetcher`。
- 不寫回 Google Sheet、不碰 OAuth、不要求或保存任何密碼/token、不讀任何憑證設定。

設計約定
========
- 主分組鍵 = production `services.v2_tables.fund_keys.resolve_full_keys`(對照表可由呼叫端注入;未注入時
  沿用 production 預設=內建表+本機 csv,純本機讀取、無網路)。DG2 `services.fund_identity.resolve_fund_identity` **只做平行差異報告**
  (`identity.shadow_diff`),不影響主分組;DG2 旗標 `DG2_SHADOW_ENABLED` 本檔不讀、不寫。
- 維度結果一律由 `compute_4d_health`(唯讀呼叫,不改它)的回傳導出,**不自行重算分數**。
- 狀態:scored / not_applicable / unsupported / missing。stale、conflict 沒有裁示的判定依據,
  一律 `not_evaluated`(計數欄位為 null,不是 0)。
- unsupported 是**探針標籤**(非 USD 外幣且 production 為 missing);同時保留
  `production_status` 說明 production 原樣是什麼。
- 抓取失敗只記原因、不重試;抓取失敗的基金不進任一維計數。
- 守恆(T7/T9)不成立 → 輸出標 `valid: false` 且 CLI 以非 0 結束,**不補數**。
- 輸出只含白名單格式的字串;其餘一律以固定占位符取代(不輸出自由文字、例外訊息、原始 URL)。
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SCHEMA = "bl0545_probe_output_v1"
FIXTURE_SCHEMA = "bl0545_probe_fixture_v1"

DIMENSIONS: Tuple[str, ...] = ("coverage", "sharpe", "trend", "volatility", "fx_risk")
NOT_EVALUATED_STATES: Tuple[str, ...] = ("stale", "conflict")

ST_SCORED = "scored"
ST_NA = "not_applicable"
ST_UNSUPPORTED = "unsupported"
ST_MISSING = "missing"
DIM_STATUSES: Tuple[str, ...] = (ST_SCORED, ST_NA, ST_UNSUPPORTED, ST_MISSING)

FETCH_OK = "ok"
FETCH_FAILED = "failed"
FETCH_NOT_ATTEMPTED = "not_attempted"

REASON_FX_LABEL = "probe_label_fx_provider_usd_only"

# 白名單:輸出中的自由字串只准這些形狀,其餘以占位符取代。
_RE_CODE = re.compile(r"^[A-Za-z0-9\-]{1,40}$")
_MAX_LABEL = 40
_RE_REASON = re.compile(r"^[a-z0-9_]{1,40}$")
_RE_REASON_ANYLEN = re.compile(r"^[a-z0-9_]+$")
TOO_LONG = "reason_code_too_long"
_RE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ][0-9:.]{1,15}(Z|[+-]\d{2}:?\d{2})?)?$")
_RE_TAG = re.compile(r"^[A-Za-z0-9_.:+\-]{1,40}$")
_RE_SHA = re.compile(r"^[0-9a-f]{7,40}$")
# 輸出落盤前的最後一道網:任何一個命中即視為洩漏疑慮,拒絕輸出。
_LEAK_PATTERNS = (
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),  # email
    re.compile(r"https?://", re.I),
    re.compile(r"\b(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?\b"),
    re.compile(r"\bya29\.[A-Za-z0-9_\-]+"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+", re.I),
    re.compile(r"(?i)client[_ ]?secret|refresh[_ ]?token|access[_ ]?token|password"),
    re.compile(r"[A-Za-z0-9_\-]{41,}"),  # 疑似 sheet id / token 長字串(40 字元 SHA 不在此列)
)


# ───────────────────────── 輔助 ─────────────────────────

def _blob_sha(path: Path) -> Optional[str]:
    """git blob SHA(sha1('blob <n>\\0' + bytes));檔不存在 → None。不呼叫 git。"""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def _safe_label(value: Any, pattern: "re.Pattern[str]", placeholder: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str) and pattern.match(value):
        return value
    if isinstance(value, str) and pattern in (_RE_REASON, _RE_TAG) and len(value) > _MAX_LABEL \
            and re.fullmatch(r"[A-Za-z0-9_.:\-]+", value):
        return TOO_LONG  # 合法字元但過長:固定占位符,不洩漏內容(原長度另記)
    return placeholder


def _note_len(entry: Dict[str, Any], reason: Any) -> None:
    if entry.get("fetch_failure_reason") == TOO_LONG and isinstance(reason, str):
        entry["fetch_failure_reason_length"] = len(reason)


def _norm(raw: Any) -> str:
    return raw.strip().upper() if isinstance(raw, str) else ""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ───────────────────────── 輸入解析 ─────────────────────────

def parse_codes_text(text: str) -> List[Dict[str, Optional[str]]]:
    """匿名代號清單 → holding rows。一行一個 `fund_code`,或兩欄 CSV `policy_id,fund_code`。

    空行與 `#` 開頭視為註解而略過;`policy_id,fund_code` 標題列略過。
    """
    rows: List[Dict[str, Optional[str]]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "," in s:
            parts = next(csv.reader([s]))
            if len(parts) != 2:
                raise ValueError("codes 檔的列須為單欄 fund_code 或兩欄 policy_id,fund_code")
            pid, code = parts[0].strip(), parts[1].strip()
            if pid.lower() == "policy_id" and code.lower() == "fund_code":
                continue
            rows.append({"policy_id": pid or None, "fund_code": code})
        else:
            rows.append({"policy_id": None, "fund_code": s})
    return rows


def make_fixture_fetcher(fixture_funds: Dict[str, Any]) -> Callable[[str], Dict[str, Any]]:
    """fixture 的 `funds` 區塊 → fetcher。以 production 主鍵 `full_key` 查;沒有該鍵 → 回 not_attempted 標記。"""

    def _fetch(full_key: str) -> Dict[str, Any]:
        if full_key not in fixture_funds:
            return {"status": FETCH_NOT_ATTEMPTED, "reason": "no_fixture_entry"}
        return copy.deepcopy(fixture_funds[full_key])

    return _fetch


# ───────────────────────── 身份 ─────────────────────────

def build_identity(rows: List[Dict[str, Optional[str]]], *, mapping: Optional[dict] = None,
                   resolver: Optional[Callable] = None,
                   shadow_resolver: Optional[Callable] = None) -> Dict[str, Any]:
    """主分組(production `resolve_full_keys`)+ DG2 平行差異報告。

    回傳 dict:`primary_groups`(list,每組 key/kind/raw_codes/row_indexes)、`shadow_diff`、
    `provenance`、內部用 `_row_group`(row index → group index)。
    """
    if resolver is None:
        from services.v2_tables.fund_keys import resolve_full_keys as resolver  # production 主鍵
    # mapping 未注入 → 沿用 production 預設(內建表 + 本機 cwd 的 fund_code_mapping.csv;
    # 只做本機讀取,無網路、不寫檔;L1 可能 print 到 stdout,故攔截以免污染 JSON 輸出)。
    codes = [r["fund_code"] for r in rows]
    with contextlib.redirect_stdout(io.StringIO()):
        res = resolver(list(codes), mapping=mapping)
        if mapping is None:
            from repositories.fund.sources import load_fund_code_mapping
            table = load_fund_code_mapping()  # 僅供 DG2 shadow 取同一份別名表
        else:
            table = mapping
    results = res["results"]
    if len(results) != len(rows):
        raise RuntimeError("resolve_full_keys 回傳長度與輸入不符")

    groups: List[Dict[str, Any]] = []
    index_by_key: Dict[Tuple[str, str], int] = {}
    row_group: List[int] = []
    for i, (row, r) in enumerate(zip(rows, results)):
        if r.get("ok"):
            gkey = ("full_key", r["full_key"])
        else:
            gkey = ("unresolved", _norm(row["fund_code"]) or f"__row{i}")
        if gkey not in index_by_key:
            index_by_key[gkey] = len(groups)
            groups.append({"key": gkey[1], "kind": gkey[0], "raw_codes": [], "row_indexes": []})
        gi = index_by_key[gkey]
        row_group.append(gi)
        g = groups[gi]
        g["row_indexes"].append(i)
        nr = _norm(row["fund_code"])
        if nr not in g["raw_codes"]:
            g["raw_codes"].append(nr)

    shadow_diff = _shadow_diff(rows, groups, row_group, table, shadow_resolver)
    return {
        "primary_groups": groups,
        "shadow_diff": shadow_diff,
        "provenance": dict(res.get("provenance") or {}),
        "_row_group": row_group,
        "_results": results,
    }


def _shadow_diff(rows, groups, row_group, table, shadow_resolver) -> Dict[str, Any]:
    """DG2 平行比較。失敗或例外只記錄,不影響主結果。"""
    try:
        if shadow_resolver is None:
            from services.fund_identity import resolve_fund_identity as shadow_resolver
        distinct = sorted({_norm(r["fund_code"]) for r in rows if _norm(r["fund_code"])})
        primary_of: Dict[str, int] = {}
        for ri, r in enumerate(rows):
            primary_of.setdefault(_norm(r["fund_code"]), row_group[ri])
        shadow_key: Dict[str, str] = {}
        status: Dict[str, str] = {}
        for code in distinct:
            ident = shadow_resolver(code, alias_mapping=table, input_source="sheet_fund_code_column")
            ck = getattr(ident, "canonical_key", None)
            status[code] = str(getattr(ident, "verification_status", "unknown"))
            shadow_key[code] = ck if ck else (getattr(ident, "original_code", None) or code)
        shadow_groups: Dict[str, List[str]] = {}
        for code in distinct:
            shadow_groups.setdefault(shadow_key[code], []).append(code)
        # 連通分量:主分組或影子分組任一邊相連的代碼歸為一個成分;成分內任一邊分得不一致 = 差異
        parent = {c: c for c in distinct}

        def _find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        first_in_primary: Dict[int, str] = {}
        first_in_shadow: Dict[str, str] = {}
        for c in distinct:
            for table_, key_ in ((first_in_primary, primary_of[c]), (first_in_shadow, shadow_key[c])):
                if key_ in table_:
                    parent[_find(c)] = _find(table_[key_])
                else:
                    table_[key_] = c
        comps: Dict[str, List[str]] = {}
        for c in distinct:
            comps.setdefault(_find(c), []).append(c)
        entries: List[Dict[str, Any]] = []
        for members in comps.values():
            p_groups = {primary_of[c] for c in members}
            s_groups = {shadow_key[c] for c in members}
            if len(p_groups) > 1 or len(s_groups) > 1:
                entries.append({
                    "codes": [_safe_label(c, _RE_CODE, "unparsed_input") for c in members],
                    "primary_group_count": len(p_groups),
                    "shadow_group_count": len(s_groups),
                    "shadow_verification_status": {
                        _safe_label(c, _RE_CODE, "unparsed_input"): _safe_label(status[c], _RE_REASON, "unknown")
                        for c in members},
                    "primary_resolved": {
                        _safe_label(c, _RE_CODE, "unparsed_input"):
                        groups[primary_of[c]]["kind"] == "full_key" for c in members},
                })
        entries.sort(key=lambda e: e["codes"])
        counts: Dict[str, int] = {}
        for s in status.values():
            k = _safe_label(s, _RE_REASON, "unknown")
            counts[k] = counts.get(k, 0) + 1
        return {
            "evaluated": True,
            "primary_unique_count": len(groups),
            "shadow_unique_count": len(shadow_groups),
            "shadow_status_counts": dict(sorted(counts.items())),
            "primary_ok_dg2_not_base_n": sum(
                1 for c in distinct
                if groups[primary_of[c]]["kind"] == "full_key"
                and status[c] != "base_resolved_attributes_unverified"),
            "differs": bool(entries),
            "entries": entries,
            "shadow_error": None,
            "_status_by_code": status,
            "note": "DG2 僅平行比較,不影響主分組;DG2_SHADOW_ENABLED 本探針不讀不寫",
        }
    except Exception as e:  # noqa: BLE001 -- shadow 失敗只記錄類別,不影響主結果
        return {"evaluated": False, "primary_unique_count": len(groups), "shadow_unique_count": None,
                "shadow_status_counts": None, "primary_ok_dg2_not_base_n": None, "differs": None, "entries": None,
                "shadow_error": _safe_label(type(e).__name__, _RE_TAG, "unknown_error"),
                "_status_by_code": {},
                "note": "shadow 失敗,主結果不受影響"}


# ───────────────────────── 維度導出 ─────────────────────────

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x


def _miss_reason(dim: str, inp: Dict[str, Any]) -> str:
    """缺值原因代碼:只看輸入是否存在/是否為正,不含任何門檻。"""
    g = inp.get
    if dim == "coverage":
        if not _is_number(g("tr1y_pct")):
            return "tr1y_pct_absent"
        if not _is_number(g("adr_pct")):
            return "adr_pct_absent"
        return "adr_pct_nonpositive"
    if dim == "sharpe":
        return "sharpe_absent"
    if dim == "trend":
        return "trend_inputs_insufficient"
    if dim == "volatility":
        return "sigma_pct_absent" if not _is_number(g("sigma_pct")) else "sigma_pct_nonpositive"
    if dim == "fx_risk":
        ccy = g("fund_ccy")
        if not (isinstance(ccy, str) and ccy.strip()):
            return "fund_ccy_absent"
        return "fx_cv_pct_unavailable"
    return "unknown"


def derive_dimensions(inp: Dict[str, Any], meta: Dict[str, Any],
                      health_fn: Optional[Callable] = None) -> Dict[str, Any]:
    """一檔基金 → 五維狀態。分數/覆蓋一律取自 `compute_4d_health` 回傳,不重算。"""
    if health_fn is None:
        from services.health.grade import compute_4d_health as health_fn
    h = health_fn(
        tr1y_pct=inp.get("tr1y_pct"), adr_pct=inp.get("adr_pct"), sharpe=inp.get("sharpe"),
        sigma_pct=inp.get("sigma_pct"), ma_dir=inp.get("ma_dir"),
        fund_ccy=inp.get("fund_ccy"), fx_cv_pct=inp.get("fx_cv_pct"),
    )
    factors = h.get("factors") or {}
    fx_status = h.get("fx_risk_status")
    ccy = str(inp.get("fund_ccy") or "").strip().upper()
    out: Dict[str, Any] = {}
    for dim in DIMENSIONS:
        scored = factors.get(dim) is not None
        if dim == "fx_risk" and fx_status == "n/a":
            status, reason, prod = ST_NA, "twd_denominated", "n/a"
        elif scored:
            status, reason, prod = ST_SCORED, "scored", "scored"
        elif dim == "fx_risk" and ccy and ccy not in ("USD",):
            status, reason, prod = ST_UNSUPPORTED, REASON_FX_LABEL, "missing"
        else:
            status, reason, prod = ST_MISSING, _miss_reason(dim, inp), "missing"
        m = (meta or {}).get(dim) or {}
        out[dim] = {
            "status": status,
            "reason_code": reason,
            "production_status": prod,
            "proxy": bool(m.get("proxy", False)),
            "obs_date": _safe_label(m.get("obs_date"), _RE_ISO, "redacted_non_date"),
            "source_tag": _safe_label(m.get("source_tag"), _RE_TAG, "redacted_source_tag"),
            "stale_status": "not_evaluated",
            "conflict_status": "not_evaluated",
        }
    cov = h.get("coverage") or {}
    n_scored = sum(1 for d in DIMENSIONS if out[d]["status"] == ST_SCORED)
    n_app = sum(1 for d in DIMENSIONS if out[d]["status"] != ST_NA)
    prod_missing = sorted(d for d in DIMENSIONS if out[d]["status"] in (ST_MISSING, ST_UNSUPPORTED))
    consistent = (cov.get("n_scored") == n_scored and cov.get("n_applicable") == n_app
                  and sorted(cov.get("missing") or []) == prod_missing)
    return {
        "dimensions": out,
        "disclosure": {"scored_n": n_scored, "applicable_n": n_app, "n_total": len(DIMENSIONS),
                       "text": f"{n_scored}/{n_app}", "missing_dimensions": prod_missing},
        "consistent_with_production": bool(consistent),
    }


# ───────────────────────── 主流程 ─────────────────────────

def run_probe(rows: List[Dict[str, Optional[str]]], *, fetcher: Optional[Callable] = None,
              mapping: Optional[dict] = None, holdings_origin: str = "user_supplied_code_list",
              as_of: Optional[str] = None, main_sha: Optional[str] = None,
              clock: Optional[Callable[[], datetime]] = None,
              resolver: Optional[Callable] = None, shadow_resolver: Optional[Callable] = None,
              health_fn: Optional[Callable] = None) -> Dict[str, Any]:
    """純邏輯入口:可注入 fetcher/mapping/clock/resolver/health_fn,離線可測。"""
    now = (clock or _utc_now)()
    ident = build_identity(rows, mapping=mapping, resolver=resolver, shadow_resolver=shadow_resolver)
    groups = ident["primary_groups"]
    row_group = ident["_row_group"]

    # policy 序號(不輸出原始 policy_id)
    pol_ord: Dict[str, int] = {}
    group_policy_rows: List[List[str]] = [[] for _ in groups]
    for ri, row in enumerate(rows):
        pid = row.get("policy_id")
        if pid:
            if pid not in pol_ord:
                pol_ord[pid] = len(pol_ord) + 1
            label = f"policy#{pol_ord[pid]}"
        else:
            label = f"row#{ri + 1}"
        group_policy_rows[row_group[ri]].append(label)

    per_fund: List[Dict[str, Any]] = []
    unresolved = fetch_success = fetch_failed = not_attempted = 0
    dim_counts = {d: {s: 0 for s in DIM_STATUSES} for d in DIMENSIONS}
    proxy_n = {d: 0 for d in DIMENSIONS}
    invalid: List[str] = []

    for gi, g in enumerate(groups):
        label = g["key"] if _RE_CODE.match(g["key"]) else f"unparsed_input_{gi + 1}"
        entry: Dict[str, Any] = {
            "canonical_key_or_raw_code": label,
            "primary_key_kind": g["kind"],
            "identity_status": None,
            "shadow_verification_status": sorted({
                _safe_label(ident["shadow_diff"]["_status_by_code"][c], _RE_REASON, "unknown")
                for c in g["raw_codes"] if c in ident["shadow_diff"]["_status_by_code"]}),
            "policy_rows": group_policy_rows[gi],
            "fetch_status": FETCH_NOT_ATTEMPTED,
            "fetch_failure_reason": None,
            "dimensions": None,
            "coverage_disclosure": None,
        }
        if g["kind"] != "full_key":
            unresolved += 1
            not_attempted += 1
            entry["identity_status"] = "primary_unresolved"
            entry["fetch_failure_reason"] = "identity_unresolved"
            per_fund.append(entry)
            continue
        entry["identity_status"] = "primary_resolved"
        if fetcher is None:
            not_attempted += 1
            entry["fetch_failure_reason"] = "live_mode_not_implemented_no_fetcher"
            per_fund.append(entry)
            continue
        try:
            res = fetcher(g["key"])
        except Exception as e:  # noqa: BLE001 -- 只記類別,不重試、不輸出訊息
            res = {"status": FETCH_FAILED,
                   "reason": "fetcher_exception_" + re.sub(r"[^a-z0-9]", "", type(e).__name__.lower())}
        status = res.get("status") if isinstance(res, dict) else None
        if status == FETCH_NOT_ATTEMPTED:
            not_attempted += 1
            entry["fetch_failure_reason"] = _safe_label(res.get("reason"), _RE_REASON, "unspecified_reason_redacted")
            _note_len(entry, res.get("reason"))
        elif status == FETCH_OK and isinstance(res.get("inputs"), dict):
            try:
                d = derive_dimensions(res["inputs"], res.get("dimension_meta") or {}, health_fn)
            except Exception as e:  # noqa: BLE001
                fetch_failed += 1
                entry["fetch_status"] = FETCH_FAILED
                entry["fetch_failure_reason"] = "health_call_exception_" + re.sub(
                    r"[^a-z0-9]", "", type(e).__name__.lower())
                per_fund.append(entry)
                continue
            fetch_success += 1
            entry["fetch_status"] = FETCH_OK
            entry["dimensions"] = d["dimensions"]
            entry["coverage_disclosure"] = d["disclosure"]
            if not d["consistent_with_production"]:
                invalid.append(f"fund#{gi + 1}: coverage_mismatch_vs_4d")
            for dim in DIMENSIONS:
                dd = d["dimensions"][dim]
                dim_counts[dim][dd["status"]] += 1
                if dd["proxy"]:
                    proxy_n[dim] += 1
        else:
            fetch_failed += 1
            entry["fetch_status"] = FETCH_FAILED
            entry["fetch_failure_reason"] = _safe_label(
                res.get("reason") if isinstance(res, dict) else None, _RE_REASON,
                "unspecified_reason_redacted") or "fetcher_bad_result"
            _note_len(entry, res.get("reason") if isinstance(res, dict) else None)
        per_fund.append(entry)

    unique_funds = len(groups)
    dims_out: Dict[str, Any] = {}
    for dim in DIMENSIONS:
        if fetch_success == 0:
            dims_out[dim] = {"applicable_n": None, "scored_n": None, "not_applicable": None,
                             "unsupported": None, "missing": None, "proxy_scored_n": None,
                             "stale": None, "conflict": None}
        else:
            c = dim_counts[dim]
            dims_out[dim] = {"applicable_n": fetch_success - c[ST_NA], "scored_n": c[ST_SCORED],
                             "not_applicable": c[ST_NA], "unsupported": c[ST_UNSUPPORTED],
                             "missing": c[ST_MISSING], "proxy_scored_n": proxy_n[dim],
                             "stale": None, "conflict": None}

    out: Dict[str, Any] = {
        "schema": SCHEMA,
        "valid": True,
        "invalid_reasons": [],
        "admission": "NOT DEFINED",
        "real_active_sheet_coverage": "NOT VERIFIED",
        "live_mode": "NOT IMPLEMENTED",
        "not_evaluated_states": list(NOT_EVALUATED_STATES),
        "source": {"holdings_origin": holdings_origin, "active_sheet_id_hash": None,
                   "account_sub_hash": None},
        "as_of": _safe_label(as_of, _RE_ISO, "redacted_non_date"),
        "fetched_at": now.isoformat(),
        "formula_version": {
            "health_module": _blob_sha(_REPO_ROOT / "services" / "health" / "grade.py"),
            "main_sha": _safe_label(main_sha, _RE_SHA, "redacted_sha"),
        },
        "identity": {
            "primary_key": "services.v2_tables.fund_keys.resolve_full_keys",
            "primary_provenance": {k: _safe_label(v, _RE_TAG, "redacted") if isinstance(v, str) else v
                                   for k, v in ident["provenance"].items()},
            "primary_groups": [
                {"key": p["canonical_key_or_raw_code"], "kind": p["primary_key_kind"],
                 "row_count": len(groups[i]["row_indexes"])}
                for i, p in enumerate(per_fund)],
            "shadow_diff": {k: v for k, v in ident["shadow_diff"].items() if not k.startswith("_")},
        },
        "population": {"holding_rows": len(rows), "unique_funds": unique_funds,
                       "identity_unresolved": unresolved, "fetch_success": fetch_success,
                       "fetch_failed": fetch_failed, "not_attempted": not_attempted},
        "dimensions": dims_out,
        "per_fund": per_fund,
    }
    out["invalid_reasons"].extend(invalid)
    out["invalid_reasons"].extend(check_invariants(out))
    if out["invalid_reasons"]:
        out["valid"] = False
    return out


def check_invariants(out: Dict[str, Any]) -> List[str]:
    """T7/T9 守恆檢查。只回報違反項,絕不補數。"""
    bad: List[str] = []
    p = out.get("population") or {}
    if p.get("fetch_success") + p.get("fetch_failed") + p.get("not_attempted") != p.get("unique_funds"):
        bad.append("T7_fetch_sum_ne_unique_funds")
    for dim, c in (out.get("dimensions") or {}).items():
        if c.get("scored_n") is None:
            if p.get("fetch_success"):
                bad.append(f"T9_{dim}_null_but_fetch_ok_positive")
            continue
        total = c["scored_n"] + c["not_applicable"] + c["unsupported"] + c["missing"]
        if total != p.get("fetch_success"):
            bad.append(f"T9_{dim}_sum_ne_fetch_success")
        if c["applicable_n"] != p.get("fetch_success") - c["not_applicable"]:
            bad.append(f"T9_{dim}_applicable_inconsistent")
    return bad


def assert_no_leak(text: str) -> None:
    """輸出序列化後的最後一道網;命中即拒絕輸出。"""
    for pat in _LEAK_PATTERNS:
        if pat.search(text):
            raise ValueError("輸出疑含敏感字串,拒絕輸出")


def render_json(out: Dict[str, Any]) -> str:
    text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    assert_no_leak(text)
    return text


# ───────────────────────── CLI ─────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="BL-0545 唯讀五維覆蓋探針(Phase 1:匿名代號清單/離線 fixture)。"
                    "live 抓取模式 NOT IMPLEMENTED(未實測);Active Sheet 讀取本批不實作。"
                    "輸出不是真實 Active Sheet 覆蓋率,也不是准入判定。")
    ap.add_argument("--codes-file", help="匿名代號清單:一行一個 fund_code,或 policy_id,fund_code 兩欄 CSV")
    ap.add_argument("--fixture", help="離線 JSON fixture(schema bl0545_probe_fixture_v1)")
    ap.add_argument("--out", help="輸出 JSON 路徑;省略則印到標準輸出")
    ap.add_argument("--main-sha", help="執行時 main SHA(由使用者提供;探針不推斷)")
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.codes_file and not args.fixture:
        print("需要 --codes-file 或 --fixture(live 模式 NOT IMPLEMENTED)", file=sys.stderr)
        return 2
    fixture: Dict[str, Any] = {}
    if args.fixture:
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        if not isinstance(fixture, dict) or fixture.get("schema") != FIXTURE_SCHEMA:
            print(f"fixture schema 須為 {FIXTURE_SCHEMA}", file=sys.stderr)
            return 2
    if args.codes_file:
        rows = parse_codes_text(Path(args.codes_file).read_text(encoding="utf-8"))
        origin = "user_supplied_code_list"
    else:
        origin = "fixture"
        holdings = fixture.get("holdings", [])
        if not isinstance(holdings, list) or not all(
                isinstance(h, dict) and isinstance(h.get("fund_code"), str) and h["fund_code"].strip()
                for h in holdings):
            print("fixture.holdings 每列須為含非空字串 fund_code 的物件", file=sys.stderr)
            return 2
        rows = [{"policy_id": h.get("policy_id"), "fund_code": h["fund_code"]} for h in holdings]
    fetcher = make_fixture_fetcher(fixture.get("funds") or {}) if args.fixture else None
    out = run_probe(rows, fetcher=fetcher, mapping=fixture.get("mapping"),
                    holdings_origin=origin,
                    as_of=fixture.get("as_of"), main_sha=args.main_sha)
    try:
        text = render_json(out)
    except ValueError as e:
        print(f"輸出被洩漏檢查拒絕,未寫出任何檔案:{e}", file=sys.stderr)
        return 4
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if out["valid"] else 3


if __name__ == "__main__":
    sys.exit(main())
