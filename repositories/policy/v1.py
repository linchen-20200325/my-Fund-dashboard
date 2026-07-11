"""repositories/policy/v1.py — V1 schema 「保單視圖」(B2 拆自 policy_repository v19.206).

V1 schema:1 張 worksheet (DEFAULT_WORKSHEET="Policies") 含 8+6 欄,每列 = (保單, 基金) 一對,
同 policy_id 多列為「一張保單下的多檔基金」。

包含:
- load_policies / upsert_policy_row / delete_policy_row
- `_find_row_index` / `_extract_code_from_url`
- sync_policies_to_portfolio_funds(整合 t7_ledgers 寫回 v1 sheet)
"""
from __future__ import annotations

# v19.340(ruff F821):Iterable 用於 sync_policies_to_portfolio_funds 型別註解,
# 原漏 import — 靠 future-annotations 延遲求值才沒在 runtime 炸;補正以免
# 未來有人拿掉 future import 或 runtime introspect 註解時爆 NameError。
from collections.abc import Iterable
from typing import Any, Optional

import pandas as pd

from ._helpers import (
    ALL_COLS,
    DEFAULT_WORKSHEET,
    OPTIONAL_COLS,
    PolicySheetError,
    REQUIRED_COLS,
    _normalize_float,
    _normalize_fx,
    _normalize_invest_twd,
    _open_worksheet,
    _row_to_list,
    _with_quota_retry,
)


def load_policies(client: Any, sheet_id: str, worksheet: str = DEFAULT_WORKSHEET) -> pd.DataFrame:
    """
    讀回 DataFrame；REQUIRED_COLS 缺欄丟 PolicySheetError，
    OPTIONAL_COLS（policy_tier）缺欄則自動補空字串向後相容。空表回空 DataFrame。
    """
    ws = _open_worksheet(client, sheet_id, worksheet)
    try:
        records = ws.get_all_records()  # list[dict]
    except Exception as e:
        raise PolicySheetError(f"讀取資料失敗：{e}") from e

    if not records:
        return pd.DataFrame(columns=list(ALL_COLS))

    df = pd.DataFrame(records)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise PolicySheetError(f"Sheet 缺欄位：{missing}（必須包含 {list(REQUIRED_COLS)}）")

    # 選填欄缺則補空字串（向後相容舊 8 欄表）
    for c in OPTIONAL_COLS:
        if c not in df.columns:
            df[c] = ""

    df = df[list(ALL_COLS)].copy()
    df["invest_twd"] = df["invest_twd"].map(_normalize_invest_twd)
    df["fx_at_buy"] = df["fx_at_buy"].map(_normalize_fx)
    for c in ("policy_id", "policy_name", "fund_url", "invest_date",
              "currency", "notes", "policy_tier"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    # policy_tier 統一小寫；非 core/satellite 一律視為 ""
    df["policy_tier"] = df["policy_tier"].str.lower().where(
        df["policy_tier"].str.lower().isin(["core", "satellite"]), ""
    )
    # v18.159：過濾「value 剛好等於 column 名」的 schema-leak 列。
    # 已知 user 部署有 sheet 出現 policy_name="policy_name" / fund_url="fund_url"
    # 這種 header 字串被誤寫成 data row 的情況（v1→v2 schema 遷移殘留 / JSON 還原
    # 把 header dict 當資料寫回）。判斷準則：policy_name 或 fund_url 任一 == 欄名。
    _schema_leak = (
        (df["policy_name"].str.lower() == "policy_name")
        | (df["fund_url"].str.lower() == "fund_url")
    )
    if _schema_leak.any():
        df = df[~_schema_leak].copy().reset_index(drop=True)
    return df


# ──────────────────────────────────────────────────────────────────────
# Write：upsert / delete（以 (policy_id, fund_url) 為主鍵）
# ──────────────────────────────────────────────────────────────────────
def _find_row_index(ws: Any, policy_id: str, fund_url: str) -> Optional[int]:
    """1-based 列號（含表頭，header 為第 1 列）；找不到回 None。"""
    try:
        all_values = ws.get_all_values()
    except Exception as e:
        raise PolicySheetError(f"讀取 sheet 全表失敗：{e}") from e
    if not all_values:
        return None
    header = all_values[0]
    try:
        pid_idx = header.index("policy_id")
        url_idx = header.index("fund_url")
    except ValueError as e:
        raise PolicySheetError(f"表頭缺主鍵欄位：{e}") from e

    for r, row in enumerate(all_values[1:], start=2):
        if len(row) > max(pid_idx, url_idx) and row[pid_idx] == policy_id and row[url_idx] == fund_url:
            return r
    return None


def upsert_policy_row(
    client: Any,
    sheet_id: str,
    row: dict,
    worksheet: str = DEFAULT_WORKSHEET,
) -> str:
    """
    存在則更新、不存在則 append；以 (policy_id, fund_url) 為主鍵。
    回傳 "inserted" / "updated"。
    """
    pid = str(row.get("policy_id", "")).strip()
    url = str(row.get("fund_url", "")).strip()
    if not pid or not url:
        raise PolicySheetError("upsert_policy_row 必須提供 policy_id 與 fund_url")

    ws = _open_worksheet(client, sheet_id, worksheet)

    # 表頭缺失時補回（建立空表時直接寫 9 欄完整 schema）
    try:
        header = ws.row_values(1)
    except Exception:
        header = []
    if not header:
        try:
            # v18.171：用 update("A1",...) 強制 row 1 — append_row 會把 header
            # 塞到資料最末列（rows 1 空但 rows 2+ 有資料時），造成 schema 列
            # 被當資料寫進保單分頁。
            ws.update("A1", [list(ALL_COLS)])
            header = list(ALL_COLS)
        except Exception as e:
            raise PolicySheetError(f"寫入表頭失敗：{e}") from e

    # v18.183：寫入對齊「表頭實際有的欄」（依 ALL_COLS 順序取交集）。既不漏寫既有欄、
    # 也不會寫到表頭沒有的欄（避免無表頭的孤兒欄）。空表頭已補成 ALL_COLS → 寫滿；
    # 舊 8/9 欄表維持原寬度向後相容（此為 legacy「Policies」單表路徑；per-policy
    # 分頁的 upsert_fund_in_policy 才會主動升級表頭以持久化新欄）。
    cols = tuple(c for c in ALL_COLS if c in header) or REQUIRED_COLS
    values = _row_to_list(row, cols)
    last_col_letter = chr(ord("A") + len(cols) - 1)

    idx = _find_row_index(ws, pid, url)
    try:
        if idx is None:
            ws.append_row(values)
            return "inserted"
        ws.update(f"A{idx}:{last_col_letter}{idx}", [values])
        return "updated"
    except Exception as e:
        raise PolicySheetError(f"寫入 sheet 失敗：{e}") from e


def delete_policy_row(
    client: Any,
    sheet_id: str,
    policy_id: str,
    fund_url: str,
    worksheet: str = DEFAULT_WORKSHEET,
) -> bool:
    """以 (policy_id, fund_url) 為主鍵刪除一列。回傳是否真有刪到。"""
    ws = _open_worksheet(client, sheet_id, worksheet)
    idx = _find_row_index(ws, str(policy_id), str(fund_url))
    if idx is None:
        return False
    try:
        ws.delete_rows(idx)
        return True
    except Exception as e:
        raise PolicySheetError(f"刪除列失敗：{e}") from e


# ──────────────────────────────────────────────────────────────────────
# 純函式：把保單表轉成 portfolio_funds 骨架，給既有 batch-load 流程接手
# ──────────────────────────────────────────────────────────────────────
def _extract_code_from_url(url: str) -> str:
    """從 MoneyDJ URL 取基金代碼；若 url 本身像代碼就原樣回傳。"""
    if not url:
        return ""
    s = str(url).strip()
    if "://" not in s and "/" not in s:
        return s.upper()
    for token in s.replace("?", "&").split("&"):
        if "=" in token:
            k, v = token.split("=", 1)
            if k.lower().endswith(("a", "code")) and v:
                return v.strip().upper()
    tail = s.rstrip("/").split("/")[-1]
    return tail.split(".")[0].upper()


def sync_policies_to_portfolio_funds(
    policies_df: pd.DataFrame,
    current_funds: Iterable[dict] | None = None,
) -> tuple[list[dict], dict]:
    """
    純函式：把多保單 DataFrame 攤平成 portfolio_funds 條目 list。

    v18.56：dedupe 鍵升級為 `(policy_id, fund_code)` 複合鍵，與 P2 後 T7
    `t7_ledgers` 對齊 — 同 code 跨多保單會各自保留一條，不再被合併丟失。
    （根因：使用者報告 19 筆跨 4 保單，讀回後變 7 檔 unique code）

    - 既存 (policy_id, code) 保留現有 loaded/metrics（不覆蓋已抓回的資料）
    - 新 (policy_id, code) 以 `loaded=False` 骨架加入，等使用者按「批次載入」
    - 同 (policy_id, code) 在 Sheet 內出現多次 → invest_twd 加總（罕見邊界）

    回傳: (merged_funds, report)
      report = {"added": [pk_str...], "kept": [pk_str...], "removed": [pk_str...]}
      pk_str 格式："{policy_id}::{fund_code}"，方便 UI 顯示「在哪保單」
    """
    def _pk(_pid: str, _code: str) -> str:
        return f"{str(_pid or '').strip()}::{str(_code or '').strip().upper()}"

    current = list(current_funds or [])
    cur_by_pk: dict[str, dict] = {}
    for _f in current:
        _c = str(_f.get("code", "") or "").upper()
        if not _c:
            continue
        _p = str(_f.get("policy_id", "") or "").strip()
        cur_by_pk[_pk(_p, _c)] = _f

    target_pks: list[str] = []
    aggregated: dict[str, dict] = {}
    if policies_df is not None and not policies_df.empty:
        for _, row in policies_df.iterrows():
            code = _extract_code_from_url(row.get("fund_url", ""))
            if not code:
                continue
            policy_id = str(row.get("policy_id", "")).strip()
            pk = _pk(policy_id, code)
            invest = _normalize_invest_twd(row.get("invest_twd", 0))
            if pk in aggregated:
                aggregated[pk]["invest_twd"] += invest
            else:
                _tier_raw = str(row.get("policy_tier", "") or "").strip().lower()
                _tier = _tier_raw if _tier_raw in ("core", "satellite") else ""
                aggregated[pk] = {
                    "code": code,
                    "invest_twd": invest,
                    "policy_id": policy_id,
                    "policy_name": str(row.get("policy_name", "")).strip(),
                    "currency": str(row.get("currency", "")).strip(),
                    "invest_date": str(row.get("invest_date", "")).strip(),
                    "fx_at_buy": _normalize_fx(row.get("fx_at_buy")),
                    "policy_tier": _tier,    # P3：空字串 → 呼叫端 fallback heuristic
                }
                target_pks.append(pk)
                # v18.183：div_cash_pct / avg_nav_with_div 有值才帶回，避免空欄
                # （舊表/未升級）覆蓋掉記憶體既有設定（kept 走 base.update）。
                _dcp_raw = row.get("div_cash_pct", "")
                if str(_dcp_raw).strip() != "":
                    aggregated[pk]["div_cash_pct"] = _normalize_float(_dcp_raw, 100.0)
                _anw_raw = row.get("avg_nav_with_div", "")
                if str(_anw_raw).strip() != "":
                    aggregated[pk]["avg_nav_with_div"] = _normalize_float(_anw_raw, 0.0)
                # v18.198：avg_nav / fx_avg / units 也讀回（有值才帶，空欄不覆蓋）
                for _extra in ("avg_nav", "fx_avg", "units"):
                    _ex_raw = row.get(_extra, "")
                    if str(_ex_raw).strip() != "":
                        aggregated[pk][_extra] = _normalize_float(_ex_raw, 0.0)

    added, kept = [], []
    merged: list[dict] = []
    for pk in target_pks:
        if pk in cur_by_pk:
            base = dict(cur_by_pk[pk])
            base.update(aggregated[pk])
            merged.append(base)
            kept.append(pk)
        else:
            entry = dict(aggregated[pk])
            entry.update({"loaded": False, "load_error": None})
            merged.append(entry)
            added.append(pk)

    removed = [pk for pk in cur_by_pk.keys() if pk not in aggregated]
    return merged, {"added": added, "kept": kept, "removed": removed}
