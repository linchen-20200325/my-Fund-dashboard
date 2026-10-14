# -*- coding: utf-8 -*-
"""標的探索（exp）正式模式的 `fund_profile` 逐欄出處（L2；exp 正式模式批 C 的 C2）。

把 C1 的三支 L1（`repositories/fund/declared_profile.py`）對每一檔基金「自己寫了什麼」，照客戶裁示逐欄
判成「可以顯示的值」或「為什麼不顯示」。**本檔不取新來源、不新增 API、不推斷、不補值，也不接任何畫面。**

## 客戶裁示（逐條落在下面的欄規則裡）

- 基本資料缺值保留並 ⬜資料未備（`STATUS_NOT_READY`）；取數失敗 → ⛔ 取數失敗（`STATUS_FAILED`）。
- 名稱只採 MoneyDJ；成立日期只讀 MoneyDJ「成立日期」；配息政策依 2026-09-26 對照表（`docs/v2/49` §6.1），表外 ⬜。
- 「最高經理費」不冒充經理費率 → `mgmt_fee_rate_pct` 恆為 None。
- 幣別只採來源自報、可追溯；多來源不一致 → ⬜（`STATUS_INCONSISTENT`，畫面以 ⬜ 呈現）。
  （「meta 幣別與淨值資料不一 → ⬜」那一半在淨值那一支判：`nav_dividend` 的幣別閘，本檔只交出 `declared`。）

## 輸出

`build_profiles(key_results)` 回 `{"rows", "cells", "declared", "source_status", "table_wide_failed"}`，見該函式。
**原文不遮蔽**（`raw`、`reason`、`source_status[...]["error"]`）—— 遮蔽在寫出點（L3）做一次，同 `market_indicator`。

## 綁定閘門（docs/v2/49 第 8 節 (n)）

MoneyDJ 基本資料頁的 ok 只確認「頁面可見文字提到代碼」＋「頁面上有一張含基金名稱的表」。本檔另要求
`binding["code_in_label_table"]` 為真（代碼出現在**那張表自身**的文字裡）才採用 MoneyDJ 的四個欄位；
否則名稱、成立日期、配息方式判 ⬜，MoneyDJ 也**不參與**幣別比對。⚠️ 真實頁面上代碼是否寫在那張表裡**未以樣本驗證**。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from repositories.fund import declared_profile as dp
from repositories.fund.sources import _normalize_declared_ccy

STATUS_OK = "ok"
STATUS_NOT_READY = "not_ready"
STATUS_FAILED = "fetch_failed"
STATUS_INCONSISTENT = "inconsistent"

#: 封閉、固定順序。`declared` 的出處字串只能由這三個名稱組成（例 `meta:MoneyDJ+TDCC`），順序照這裡。
SOURCES: tuple[str, ...] = ("MoneyDJ", "TDCC", "FundClear")

#: set 頁「重新取數」要清的三支公開 L1（各自的 `cache_clear()` 同時清成功快取與自己的失敗記憶，見 `dp._public`）。
DECLARED_CACHED_FUNCTIONS = (
    dp.fetch_moneydj_basic_fields,
    dp.fetch_tdcc_listing,
    dp.fetch_fundclear_declared_ccy,
)

#: `fund_profile` 的欄名與順序（與 `ui_v2/exp/logic.py::FUND_PROFILE_FIELDS` 逐字相同；L2 不得 import ui_v2，
#: 由 `tests/test_v2_tables_exp_profile.py` 對拍）。
FUND_PROFILE_FIELDS: tuple[str, ...] = (
    "fund_code", "fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct", "fetched_at",
)
#: 有逐格出處的欄（`fund_code` 是輸入、`fetched_at` 是列層彙總，兩者不進 `cells`）。
CELL_FIELDS: tuple[str, ...] = ("fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct")

DIVIDEND_POLICY_DIST = "dist"
DIVIDEND_POLICY_ACCUM = "accum"

#: 配息頻率對照表，逐字照 `docs/v2/49` §6.1〈配息頻率對照表（客戶 2026-09-26 定案）〉。
#: 值為 None ＝ 該表「不寫入」那一類（空白、「—」、不定期）：依對照表不判定配息方式。
#: 比對前只去頭尾空白，之後**整欄精確比對**（不做子字串、不轉全半形）。表上沒有的寫法 → 表外。
#: ⚠️ 左欄是推測的寫法，沒有實測過（49 原文）。
DIVIDEND_FREQ_TO_POLICY: dict = {
    "月配": DIVIDEND_POLICY_DIST, "月配息": DIVIDEND_POLICY_DIST,
    "季配": DIVIDEND_POLICY_DIST, "季配息": DIVIDEND_POLICY_DIST,
    "半年配": DIVIDEND_POLICY_DIST, "半年配息": DIVIDEND_POLICY_DIST,
    "年配": DIVIDEND_POLICY_DIST, "年配息": DIVIDEND_POLICY_DIST,
    "雙月配": DIVIDEND_POLICY_DIST, "月收": DIVIDEND_POLICY_DIST,
    "不配息": DIVIDEND_POLICY_ACCUM, "無配息": DIVIDEND_POLICY_ACCUM,
    "累積": DIVIDEND_POLICY_ACCUM, "累積型": DIVIDEND_POLICY_ACCUM,
    "": None, "—": None, "不定期": None,
}

#: 幣別「有值，但另有來源取數失敗」時的處置。
#: ~~`"fail"`（預設，從嚴）：整格 ⛔ 取數失敗 —— 失敗的那個來源可能報的是另一種幣別，無法確認各來源一致；~~
#: ~~⚠️ **預設從嚴、待客戶裁示**（決策者：AI 總管，暫定）。~~
#: → **2026-10-14 客戶裁示（有意識的政策變更，不是漏刪；決策者：客戶）**：預設改 `"accept"` ——
#:   其餘已成功的來源若一致且證據充分，可顯示該值；同時保留來源失敗標示與原因；**不得把失敗來源當成一致證據**。
#:   「證據充分」＝至少一個成功來源給出可正規化的 ISO 值，且所有成功來源之間沒有不同的 ISO、沒有「認不出」；
#:   MoneyDJ 未綁定（身分未核實）不算成功來源。`"accept"` 時：`status` ok、`value` 為一致的 ISO、
#:   `sources` 只列成功且同意的來源、`failed_sources` 列失敗來源、`reason` 寫失敗來源與原因摘要（原文留在
#:   `source_status`）。舊的從嚴用意（失敗來源可能報別的幣別）仍成立，被權衡掉的是它的結論：客戶接受這個風險，
#:   換取畫面不因單一來源失敗而整格 ⛔；失敗照樣標示，使用者看得到。
#:   `"fail"` 保留為可切換的從嚴行為（兩種行為都有測試），正式路徑不用。
PARTIAL_FAILURE_POLICY = "accept"
_PARTIAL_POLICIES = ("accept", "fail")

# 逐來源幣別歸類
CCY_VALUE = "value"                   # 認得出的 ISO 幣別
CCY_UNRECOGNIZED = "unrecognized"     # 有寫，但認不出（含零寬字元、自相矛盾）
CCY_NOT_PROVIDED = "not_provided"     # 來源有這一檔，但沒寫幣別
CCY_NOT_LISTED = "not_listed"         # 來源明確回答沒有這一檔
CCY_FAILED = "failed"                 # 取數失敗
CCY_UNVERIFIED = "identity_unverified"  # 只 MoneyDJ：頁面無法確認是本檔，不參與比對
_CCY_CLASS_TEXT = {CCY_UNRECOGNIZED: "認不出", CCY_NOT_PROVIDED: "沒提供", CCY_NOT_LISTED: "未收錄",
                   CCY_FAILED: "取數失敗", CCY_UNVERIFIED: "身分未核實"}

TEXT_UNBOUND = "MoneyDJ 頁面無法確認是本檔（表格內未見代碼）"
TEXT_MGMT_FEE = "來源未提供經理費率（不以「最高經理費」代替）"
TEXT_KEY_FAILED = "代碼無法對照：{reason}"

# MoneyDJ 欄 → `declared_profile.MONEYDJ_LABELS` 的標籤
_MDJ_LABEL = {"fund_name": "基金名稱", "ccy": "計價幣別", "dividend_policy": "配息頻率", "inception_on": "成立日期"}
_INCEPTION_FORMATS = ("%Y/%m/%d", "%Y-%m-%d")


# ───────────────────────── 小工具 ─────────────────────────

def _cell(value=None, status=STATUS_NOT_READY, *, sources=(), failed_sources=(), raw=None,
          fetched_at=None, observed_at=None, reason=None) -> dict:
    return {"value": value, "status": status, "sources": tuple(sources), "failed_sources": tuple(failed_sources),
            "raw": dict(raw or {}), "fetched_at": dict(fetched_at or {}), "observed_at": dict(observed_at or {}),
            "reason": reason}


def _ordered(names) -> tuple:
    names = set(names)
    return tuple(s for s in SOURCES if s in names)


def _call(fetch, full_key: str) -> dict:
    """呼叫一支 L1；例外與型別不符都轉成 failed 結果（原文可見，不吞）。"""
    try:
        res = fetch(full_key)
    except Exception as exc:  # noqa: BLE001 —— 轉成可見的失敗原文，不是吞掉
        return {"status": dp.STATUS_FAILED, "error": f"{type(exc).__name__}: {exc}", "cooling": False,
                "cooling_remaining_sec": None, "fields": {}}
    if not isinstance(res, dict) or res.get("status") not in (dp.STATUS_OK, dp.STATUS_NOT_LISTED, dp.STATUS_FAILED):
        got = f"dict（status={res.get('status')!r}）" if isinstance(res, dict) else type(res).__name__
        return {"status": dp.STATUS_FAILED, "fields": {}, "cooling": False, "cooling_remaining_sec": None,
                "error": f"L1 回傳型別不符：預期帶合法 status 的 dict，收到 {got}"}
    return res


def _status_entry(res: dict) -> dict:
    return {"status": res.get("status"), "error": res.get("error"), "cooling": bool(res.get("cooling")),
            "cooling_remaining_sec": res.get("cooling_remaining_sec")}


def _failed_reason(source: str, res: dict) -> str:
    text = f"{source} 取數失敗"
    if res.get("cooling"):
        text += f"（失敗記憶冷卻中，約剩 {res.get('cooling_remaining_sec')} 秒，本次未重打）"
    return text


def _bound(res: dict) -> bool:
    binding = res.get("binding")
    return isinstance(binding, dict) and binding.get("code_in_label_table") is True


def _parse_aware(value) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


# ───────────────────────── MoneyDJ 三欄（名稱、成立日期、配息方式）─────────────────────────

def _mdj_gate(field: str, res: dict):
    """MoneyDJ 欄共用的閘門 → `(cell 或 None, 原字面)`。回 cell ＝ 已判定（不必再解析）。"""
    label = _MDJ_LABEL[field]
    status = res.get("status")
    if status == dp.STATUS_FAILED:
        return _cell(status=STATUS_FAILED, failed_sources=("MoneyDJ",), reason=_failed_reason("MoneyDJ", res)), None
    if status == dp.STATUS_NOT_LISTED:
        return _cell(reason="MoneyDJ 未收錄此代碼"), None
    raw = (res.get("fields") or {}).get(label)
    raw_map = {"MoneyDJ": raw} if raw is not None else {}
    fetched = {"MoneyDJ": res.get("fetched_at")}
    if not _bound(res):
        return _cell(raw=raw_map, fetched_at=fetched, reason=TEXT_UNBOUND), None
    if raw is None:
        conflict = next((c for c in res.get("label_conflicts") or () if c.get("label") == label), None)
        if conflict is not None:
            return _cell(fetched_at=fetched,
                         reason=f"MoneyDJ 頁面上「{label}」出現不同的值：{list(conflict.get('values') or [])}"), None
        return _cell(fetched_at=fetched, reason=f"MoneyDJ 未提供「{label}」"), None
    return None, raw


def _fund_name_cell(res: dict) -> dict:
    decided, raw = _mdj_gate("fund_name", res)
    if decided is not None:
        return decided
    if not isinstance(raw, str) or not raw.strip():
        return _cell(raw={"MoneyDJ": raw}, fetched_at={"MoneyDJ": res.get("fetched_at")},
                     reason="MoneyDJ「基金名稱」為空白")
    return _cell(raw, STATUS_OK, sources=("MoneyDJ",), raw={"MoneyDJ": raw},
                 fetched_at={"MoneyDJ": res.get("fetched_at")})


def parse_inception(raw) -> Optional[str]:
    """MoneyDJ「成立日期」→ 補零 ISO（`YYYY-MM-DD`）；只收 `YYYY/MM/DD` 或 `YYYY-MM-DD`（`strptime` 解析，
    月日可不補零），去頭尾空白後須為 ASCII。不存在的日期（2018/02/30）、民國年、中文年月日 → None。"""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or not text.isascii():
        return None
    for fmt in _INCEPTION_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _inception_cell(res: dict) -> dict:
    decided, raw = _mdj_gate("inception_on", res)
    if decided is not None:
        return decided
    fetched = {"MoneyDJ": res.get("fetched_at")}
    iso = parse_inception(raw)
    if iso is None:
        return _cell(raw={"MoneyDJ": raw}, fetched_at=fetched, reason=f"成立日期字樣無法辨識：{raw}")
    return _cell(iso, STATUS_OK, sources=("MoneyDJ",), raw={"MoneyDJ": raw}, fetched_at=fetched)


def _dividend_cell(res: dict) -> dict:
    decided, raw = _mdj_gate("dividend_policy", res)
    if decided is not None:
        return decided
    fetched = {"MoneyDJ": res.get("fetched_at")}
    text = raw.strip() if isinstance(raw, str) else None
    if text is None or text not in DIVIDEND_FREQ_TO_POLICY:
        return _cell(raw={"MoneyDJ": raw}, fetched_at=fetched, reason=f"配息頻率「{raw}」不在對照表")
    policy = DIVIDEND_FREQ_TO_POLICY[text]
    if policy is None:
        return _cell(raw={"MoneyDJ": raw}, fetched_at=fetched, reason=f"配息頻率「{text}」依對照表不判定配息方式")
    return _cell(policy, STATUS_OK, sources=("MoneyDJ",), raw={"MoneyDJ": raw}, fetched_at=fetched)


# ───────────────────────── 幣別（三來源）─────────────────────────

def _ccy_raw(source: str, res: dict):
    fields = res.get("fields") or {}
    if source == "MoneyDJ":
        raw = fields.get(_MDJ_LABEL["ccy"])
        if raw is None:
            conflict = next((c for c in res.get("label_conflicts") or () if c.get("label") == _MDJ_LABEL["ccy"]), None)
            if conflict is not None:
                return ("conflict", list(conflict.get("values") or []))
        return raw
    if source == "TDCC":
        return fields.get("計價幣別")
    return fields.get("currency")


def classify_ccy(source: str, res: dict):
    """單一來源 → `(歸類, 原字面, ISO 或 None)`。歸類見 `CCY_*`；值一律經 L1 `_normalize_declared_ccy` 正規化。"""
    status = res.get("status")
    if status == dp.STATUS_FAILED:
        return CCY_FAILED, None, None
    if status == dp.STATUS_NOT_LISTED:
        return CCY_NOT_LISTED, None, None
    if source == "MoneyDJ" and not _bound(res):
        return CCY_UNVERIFIED, (res.get("fields") or {}).get(_MDJ_LABEL["ccy"]), None
    raw = _ccy_raw(source, res)
    if isinstance(raw, tuple):                       # MoneyDJ 同一標籤兩個不同值：自相矛盾，認不出
        return CCY_UNRECOGNIZED, "／".join(map(str, raw[1])), None
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return CCY_NOT_PROVIDED, raw, None
    if not isinstance(raw, str):
        return CCY_UNRECOGNIZED, raw, None
    iso = _normalize_declared_ccy(raw)
    if not iso:
        return CCY_UNRECOGNIZED, raw, None
    return CCY_VALUE, raw, iso


#: 原因摘要的長度上限（原文完整留在 `source_status[代碼][來源]["error"]`）。
_FAILURE_SUMMARY_MAX = 80


def _failure_summary(results: dict, failed) -> str:
    """失敗來源 → 「來源：原文第一行（過長截斷）」；冷卻中另註明。原文完整版在 `source_status`。"""
    parts = []
    for src in failed:
        res = results[src]
        text = str(res.get("error") or "").strip()
        first = text.splitlines()[0] if text else "未提供原因"
        if len(first) > _FAILURE_SUMMARY_MAX:
            first = first[:_FAILURE_SUMMARY_MAX] + "…"
        if res.get("cooling"):
            first += f"；失敗記憶冷卻中，約剩 {res.get('cooling_remaining_sec')} 秒"
        parts.append(f"{src}：{first}")
    return "；".join(parts) + "；完整原文見 source_status"


def _ccy_cell(results: dict, policy: str) -> dict:
    cls = {src: classify_ccy(src, results[src]) for src in SOURCES}
    raw = {src: c[1] for src, c in cls.items() if c[1] is not None}
    seen = [src for src in SOURCES if cls[src][0] not in (CCY_FAILED, CCY_NOT_LISTED)]
    fetched = {src: results[src].get("fetched_at") for src in seen}
    observed = ({"TDCC": results["TDCC"].get("observed_at")}
                if "TDCC" in seen and results["TDCC"].get("observed_at") else {})
    failed = _ordered(src for src in SOURCES if cls[src][0] == CCY_FAILED)
    isos = {}
    for src in SOURCES:
        if cls[src][0] == CCY_VALUE:
            isos.setdefault(cls[src][2], []).append(src)
    unrec = [src for src in SOURCES if cls[src][0] == CCY_UNRECOGNIZED]
    summary = "、".join(
        f"{src}:{cls[src][1]!r}→{cls[src][2]}" if cls[src][0] == CCY_VALUE
        else f"{src}:{_CCY_CLASS_TEXT[cls[src][0]]}" + (f"（{cls[src][1]!r}）" if cls[src][1] is not None else "")
        for src in SOURCES)
    common = dict(raw=raw, fetched_at=fetched, observed_at=observed, failed_sources=failed)
    if len(isos) >= 2 or (isos and unrec):
        return _cell(status=STATUS_INCONSISTENT, reason=f"各來源幣別不一致（{summary}）", **common)
    if len(isos) == 1:
        (iso, agree), = isos.items()
        if failed and policy == "fail":
            return _cell(status=STATUS_FAILED,
                         reason=f"部分來源取數失敗，無法確認各來源幣別一致（{summary}）", **common)
        if failed:   # 客戶 2026-10-14 裁示：其餘成功來源一致即可顯示，失敗照樣標示（失敗來源不進 sources）
            return _cell(iso, STATUS_OK, sources=_ordered(agree),
                         reason=f"部分來源取數失敗，以其餘一致的來源為準（{_failure_summary(results, failed)}）",
                         **common)
        return _cell(iso, STATUS_OK, sources=_ordered(agree), **common)
    if failed:
        return _cell(status=STATUS_FAILED, reason=f"幣別來源取數失敗（{summary}）", **common)
    if unrec:
        return _cell(reason=f"各來源幣別字樣無法辨識（{summary}）", **common)
    return _cell(reason=f"各來源未提供幣別／未收錄（{summary}）", **common)


# ───────────────────────── 組表 ─────────────────────────

def _row_fetched_at(cells: dict, results: dict) -> Optional[str]:
    """被採用來源中最舊的實際取得時間（MoneyDJ／FundClear）。只有 TDCC 被採用、或沒有任何來源被採用 → None。
    被採用的 MoneyDJ／FundClear 有一個取不到合格時間 → None（最舊的那一個不可考，不挑別的冒充）。"""
    adopted = {src for cell in cells.values() if cell["status"] == STATUS_OK for src in cell["sources"]}
    timed = [src for src in ("MoneyDJ", "FundClear") if src in adopted]
    if not timed:
        return None
    pairs = []
    for src in timed:
        text = results[src].get("fetched_at")
        parsed = _parse_aware(text)
        if parsed is None:
            return None
        pairs.append((parsed, text))
    return min(pairs, key=lambda p: p[0])[1]


def _key_results_list(key_results) -> list:
    if isinstance(key_results, dict):
        if "results" not in key_results:
            raise TypeError("key_results 是 dict 時須為 fund_keys.resolve_full_keys 的回傳（帶 results 鍵）")
        key_results = key_results["results"]
    if not isinstance(key_results, (list, tuple)):
        raise TypeError(f"key_results 須為 resolve_full_keys 的回傳或其 results 串列（收到 {type(key_results).__name__}）")
    return list(key_results)


def _check_fetchers(fetchers) -> dict:
    if fetchers is None:
        return dict(zip(SOURCES, DECLARED_CACHED_FUNCTIONS))
    if not isinstance(fetchers, dict) or set(fetchers) != set(SOURCES):
        raise ValueError(f"fetchers 須為恰含 {SOURCES} 三個鍵的 dict（收到 {fetchers!r}）")
    for name, fn in fetchers.items():
        if not callable(fn):
            raise ValueError(f"fetchers[{name!r}] 須為可呼叫物（{fn!r}）")
    return dict(fetchers)


def _row(code: str, cells: dict, fetched_at) -> dict:
    row = {"fund_code": code}
    for f in CELL_FIELDS:
        cell = cells[f]
        row[f] = cell["value"] if cell["status"] == STATUS_OK else None
    row["fetched_at"] = fetched_at
    return {f: row[f] for f in FUND_PROFILE_FIELDS}


def build_profiles(key_results, *, fetchers=None) -> dict:
    """`fund_keys.resolve_full_keys` 的結果 → `fund_profile` 列與逐欄出處。

    - `key_results`：`resolve_full_keys(...)` 的回傳（帶 `results`），或其 `results` 串列。每一筆的 `input` 當
      `fund_code`（須為字串，否則 `TypeError`）；同一個代碼重複出現只處理第一筆（保持原順序）。
      `ok` 為真者以 `full_key` 呼叫三支 L1；`ok` 為假者不取數，各欄 ⬜「代碼無法對照：<原因>」。
    - `fetchers`：測試注入 `{"MoneyDJ": fn, "TDCC": fn, "FundClear": fn}`（恰三鍵）；None ＝ `DECLARED_CACHED_FUNCTIONS`。

    回傳::

        {"rows": [fund_profile 列（欄名照 FUND_PROFILE_FIELDS；非 ok 的格為 None）],
         "cells": {code: {欄: Cell}},          # 欄＝CELL_FIELDS
         "declared": {code: (ISO 或 None, "meta:<來源+來源>" 或 None)},   # 幣別 ok 時才有值
         "source_status": {code: {來源: {status, error, cooling, cooling_remaining_sec}}},  # 代碼無法對照 → {}
         "table_wide_failed": bool}            # 有取數的每一檔，三來源都 failed（沒有任何一檔取數 → False）

    Cell ＝ `{"value", "status", "sources", "failed_sources", "raw", "fetched_at", "observed_at", "reason"}`：
    `status` ∈ {ok, not_ready, fetch_failed, inconsistent}；`sources` ＝ 被採用的來源（依 `SOURCES` 順序）；
    `raw` ＝ 各來源原字面（不遮蔽）；`fetched_at` ＝ 各來源的實際取得時間（TDCC 恆 None，另放 `observed_at`）。
    """
    if PARTIAL_FAILURE_POLICY not in _PARTIAL_POLICIES:
        raise ValueError(f"PARTIAL_FAILURE_POLICY 須為 {_PARTIAL_POLICIES} 之一（{PARTIAL_FAILURE_POLICY!r}）")
    entries = _key_results_list(key_results)
    fns = _check_fetchers(fetchers)
    out = {"rows": [], "cells": {}, "declared": {}, "source_status": {}, "table_wide_failed": False}
    fetched_any = False
    all_failed = True
    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError(f"key_results 的每一筆須為 dict（收到 {type(entry).__name__}）")
        code = entry.get("input")
        if not isinstance(code, str):
            raise TypeError(f"fund_code（key_results 的 input）須為字串（收到 {type(code).__name__}：{code!r}）")
        if code in out["cells"]:
            continue
        if entry.get("ok") is not True:
            reason = TEXT_KEY_FAILED.format(reason=entry.get("error"))
            cells = {f: _cell(reason=reason) for f in CELL_FIELDS}
            out["cells"][code] = cells
            out["declared"][code] = (None, None)
            out["source_status"][code] = {}
            out["rows"].append(_row(code, cells, None))
            continue
        full_key = entry.get("full_key")
        results = {src: _call(fns[src], full_key) for src in SOURCES}
        fetched_any = True
        if any(results[src].get("status") != dp.STATUS_FAILED for src in SOURCES):
            all_failed = False
        mdj = results["MoneyDJ"]
        cells = {
            "fund_name": _fund_name_cell(mdj),
            "ccy": _ccy_cell(results, PARTIAL_FAILURE_POLICY),
            "inception_on": _inception_cell(mdj),
            "dividend_policy": _dividend_cell(mdj),
            "mgmt_fee_rate_pct": _cell(reason=TEXT_MGMT_FEE),
        }
        ccy = cells["ccy"]
        out["declared"][code] = ((ccy["value"], "meta:" + "+".join(ccy["sources"]))
                                 if ccy["status"] == STATUS_OK else (None, None))
        out["cells"][code] = cells
        out["source_status"][code] = {src: _status_entry(results[src]) for src in SOURCES}
        out["rows"].append(_row(code, cells, _row_fetched_at(cells, results)))
    out["table_wide_failed"] = fetched_any and all_failed
    return out
