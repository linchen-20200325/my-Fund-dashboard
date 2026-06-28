"""repositories/policy/v2.py — V2 schema 「每保單一頁」(B2 拆自 policy_repository v19.206).

V2 schema:每張保單獨立 worksheet(policy_id 為 tab name),既支援巢狀資料結構也
能避開 V1「同 policy_id 多列」單頁過長問題。

包含:
- worksheet 管理:list_policy_worksheets / ensure_policy_worksheet /
  load_policy_worksheet / load_all_policy_worksheets / clear_load_all_ws_cache /
  upsert_fund_in_policy / delete_fund_in_policy / delete_policy_worksheet
- Sheet 工具:rename_sheet / get_sheet_title / list_user_sheets /
  list_user_folders / create_dashboard_sheet
- V2 data:compute_units / avg_nav_with_div_from_cumul_div_twd /
  is_v2_worksheet / detect_sheet_schema_version / estimate_dividend_split /
  load_policy_v2 / write_policy_v2 / load_all_policies_v2
- backup:copy_sheet_as_backup
- V2-only `_*`:`_sanitize_tab_name` / `_records_to_policy_df` /
  `_normalize_header_to_en` / `_normalize_div_cash_pct` / `_apply_v2_header_format`
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from ._helpers import (
    ALL_COLS,
    DEFAULT_WORKSHEET,
    OPTIONAL_COLS,
    PolicySheetError,
    REQUIRED_COLS,
    _is_worksheet_not_found,
    _normalize_float,
    _normalize_fx,
    _normalize_invest_twd,
    _row_to_list,
    _with_quota_retry,
)


#     用於既有 Policies 平面 schema；新使用者建議用以下 API
# ══════════════════════════════════════════════════════════════════════

# 保留給 ledger / metadata 等內部 tab 的前綴，list_policy_worksheets 會過濾
_RESERVED_TAB_PREFIX = "_"

# Google Sheets worksheet 名禁字符
_BAD_TAB_CHARS = set("[]:\\?/*'\"")


def _sanitize_tab_name(policy_id: str) -> str:
    """把 policy_id 變成合法的 worksheet 名（禁字符換 _，長度 ≤ 100）。"""
    s = str(policy_id or "").strip()
    if not s:
        raise PolicySheetError("policy_id 不可為空")
    clean = "".join("_" if c in _BAD_TAB_CHARS else c for c in s)[:100]
    if clean.startswith(_RESERVED_TAB_PREFIX):
        raise PolicySheetError(f"policy_id 不能以 '{_RESERVED_TAB_PREFIX}' 開頭（保留給系統 tab）")
    return clean


def list_policy_worksheets(client: Any, sheet_id: str) -> list[str]:
    """回傳所有保單 tab 名（過濾掉 _ 開頭的系統 tab，如 _Ledgers）。"""
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        names = [ws.title for ws in _with_quota_retry(sh.worksheets)]
    except Exception as e:
        raise PolicySheetError(f"列 worksheets 失敗：{e}") from e
    return [n for n in names
            if not n.startswith(_RESERVED_TAB_PREFIX) and n != DEFAULT_WORKSHEET]


def ensure_policy_worksheet(client: Any, sheet_id: str, policy_id: str,
                            cols: int = 12, rows: int = 100) -> Any:
    """
    確保該 policy_id 的 worksheet 存在；不存在則建立並寫入表頭。
    回傳 worksheet 物件。
    """
    tab = _sanitize_tab_name(policy_id)
    if not sheet_id:
        raise PolicySheetError("開啟 Sheet 失敗：sheet_id 為空")
    try:
        sh = client.open_by_key(sheet_id)
    except Exception as e:
        # v18.41 強化錯誤訊息：gspread 例外 str(e) 常空白，補上型別與 ID 前綴
        _hint = f"[{type(e).__name__}] {e}" if str(e) else type(e).__name__
        _sid_hint = sheet_id[:12] + ("…" if len(sheet_id) > 12 else "")
        raise PolicySheetError(
            f"開啟 Sheet 失敗（ID `{_sid_hint}`）：{_hint}"
        ) from e

    try:
        ws = sh.worksheet(tab)
        # 確保表頭存在
        try:
            header = ws.row_values(1)
        except Exception:
            header = []
        if not header:
            # v18.171：用 update("A1",...) 強制 row 1 — append_row 會把 header
            # 塞到資料最末列（rows 1 空但 rows 2+ 有資料時），造成 schema 列
            # 被當資料寫進保單分頁。
            ws.update("A1", [list(ALL_COLS)])
        return ws
    except Exception:
        # tab 不存在 → 建立
        try:
            ws = sh.add_worksheet(title=tab, rows=rows, cols=cols)
            # v18.171：新建空 sheet 用 update("A1",...) 也比 append_row 穩
            # （行為一致、不依賴「資料範圍從哪算」的 gspread 細節）。
            ws.update("A1", [list(ALL_COLS)])
            return ws
        except Exception as e:
            raise PolicySheetError(f"建立 worksheet '{tab}' 失敗：{e}") from e


def _records_to_policy_df(records: list) -> pd.DataFrame:
    """gspread get_all_records → 正規化 + 過濾 schema 鬼列的保單 DataFrame。

    v18.200：從 load_policy_worksheet 抽出，讓 load_policy_worksheet（單分頁）與
    load_all_policy_worksheets（open 一次、重用 worksheet 物件）共用同一份解析邏輯。
    """
    if not records:
        return pd.DataFrame(columns=list(ALL_COLS))
    df = pd.DataFrame(records)
    for c in ALL_COLS:
        if c not in df.columns:
            df[c] = ""
    df = df[list(ALL_COLS)].copy()
    df["invest_twd"] = df["invest_twd"].map(_normalize_invest_twd)
    df["fx_at_buy"]  = df["fx_at_buy"].map(_normalize_fx)
    for c in ("policy_id", "policy_name", "fund_url", "invest_date",
              "currency", "notes", "policy_tier"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    df["policy_tier"] = df["policy_tier"].str.lower().where(
        df["policy_tier"].str.lower().isin(["core", "satellite"]), ""
    )
    # v18.171/172：防禦性過濾 schema 鬼列（fund_url/invest_date/currency 三欄都是
    # 字面 schema key 的明顯鬼列；case-insensitive 擋大小寫兩種）。
    _fu_low = df["fund_url"].astype(str).str.lower()
    _id_low = df["invest_date"].astype(str).str.lower()
    _cc_low = df["currency"].astype(str).str.lower()
    _ghost_mask = (
        (_fu_low == "fund_url")
        & (_id_low == "invest_date")
        & (_cc_low == "currency")
    )
    if _ghost_mask.any():
        df = df[~_ghost_mask].copy()
    return df


def load_policy_worksheet(client: Any, sheet_id: str, policy_id: str) -> pd.DataFrame:
    """讀單一保單的所有基金列。tab 不存在回空 DataFrame（不丟錯）。"""
    tab = _sanitize_tab_name(policy_id)
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        ws = sh.worksheet(tab)
    except Exception:
        return pd.DataFrame(columns=list(ALL_COLS))

    try:
        records = _with_quota_retry(ws.get_all_records)
    except Exception as e:
        raise PolicySheetError(f"讀取 '{tab}' 失敗：{e}") from e

    return _records_to_policy_df(records)


def load_all_policy_worksheets(client: Any, sheet_id: str) -> pd.DataFrame:
    """跨所有保單 tab 合併成一張 DataFrame（用於分組視圖、總配置統計）。

    v18.200（讀取治本）：open 試算表**一次**，`sh.worksheets()` 一次拿到所有分頁
    物件（同時當清單 + 讀取 handle），再逐分頁 get_all_records — 省掉原本「每分頁
    各 open_by_key 一次」的大量讀取（429 Quota 主因）。讀取數從 ~2+3N → ~2+N。

    v18.248（短 TTL 快取）：同 user session 反覆 rerun 仍會打 API 撞 429；加 60 秒
    TTL 快取（key=sheet_id），同 sheet 60 秒內第二次呼叫直接回 cached DataFrame
    `.copy()`（防外部 mutate）。`gspread.Client` 物件 unhashable，故走手動 dict
    而非 `infra/cache.py:_ttl_cache`。
    """
    import time as _t
    _now = _t.time()
    _hit = _LOAD_ALL_WS_CACHE.get(sheet_id)
    if _hit is not None and (_now - _hit[0]) < _LOAD_ALL_WS_TTL:
        return _hit[1].copy()
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        all_ws = _with_quota_retry(sh.worksheets)
    except Exception as e:
        raise PolicySheetError(f"列 worksheets 失敗：{e}") from e

    # 過濾出保單分頁（排除 _ 開頭系統 tab 與 legacy 單表 DEFAULT_WORKSHEET）
    policy_ws = [ws for ws in all_ws
                 if not ws.title.startswith(_RESERVED_TAB_PREFIX)
                 and ws.title != DEFAULT_WORKSHEET]
    if not policy_ws:
        _empty = pd.DataFrame(columns=list(ALL_COLS))
        _LOAD_ALL_WS_CACHE[sheet_id] = (_now, _empty)
        return _empty.copy()

    frames = []
    for ws in policy_ws:
        try:
            records = _with_quota_retry(ws.get_all_records)
        except Exception:
            continue   # 單一分頁失敗不影響其他
        df = _records_to_policy_df(records)
        if not df.empty:
            df = df.assign(policy_id=ws.title)   # tab 名覆寫 policy_id（保證一致）
            frames.append(df)
    if not frames:
        _empty = pd.DataFrame(columns=list(ALL_COLS))
        _LOAD_ALL_WS_CACHE[sheet_id] = (_now, _empty)
        return _empty.copy()
    _result = pd.concat(frames, ignore_index=True)
    _LOAD_ALL_WS_CACHE[sheet_id] = (_now, _result)
    return _result.copy()


# v18.248: 60 秒 TTL 快取（key=sheet_id）— 配合「🔄 清空快取」按鈕
_LOAD_ALL_WS_CACHE: dict = {}
_LOAD_ALL_WS_TTL = 60


def clear_load_all_ws_cache() -> None:
    """清空 load_all_policy_worksheets 的短 TTL 快取（手動失效用）。"""
    _LOAD_ALL_WS_CACHE.clear()


def upsert_fund_in_policy(
    client: Any, sheet_id: str, policy_id: str, row: dict,
) -> str:
    """
    在指定保單 tab 內 upsert 一檔基金（以 fund_url 為主鍵）。
    回傳 "inserted" / "updated"。
    自動 ensure tab 存在。
    """
    tab = _sanitize_tab_name(policy_id)
    url = str(row.get("fund_url", "")).strip()
    if not url:
        raise PolicySheetError("upsert_fund_in_policy 必須提供 fund_url")

    ws = ensure_policy_worksheet(client, sheet_id, policy_id)
    # 強制覆寫 policy_id 為 tab 名（保證一致）
    row = dict(row)
    row["policy_id"] = tab

    try:
        all_values = ws.get_all_values()
    except Exception as e:
        raise PolicySheetError(f"讀取 '{tab}' 失敗：{e}") from e

    header = all_values[0] if all_values else list(ALL_COLS)
    try:
        url_idx = header.index("fund_url")
    except ValueError as e:
        raise PolicySheetError(f"'{tab}' 表頭缺 fund_url：{e}") from e

    # v18.183：表頭缺 ALL_COLS 任一欄（如舊表沒有 div_cash_pct/avg_nav_with_div）→
    # 升級表頭。OPTIONAL_COLS 接在尾端、純追加，既有欄位位置不變、既有資料列只是尾端
    # 多出空格，不會錯位；之後該列被 upsert 才補滿值。
    if any(c not in header for c in ALL_COLS):
        try:
            _hdr_last = chr(ord("A") + len(ALL_COLS) - 1)
            ws.update(f"A1:{_hdr_last}1", [list(ALL_COLS)])
        except Exception as e:
            raise PolicySheetError(f"升級 '{tab}' 表頭失敗：{e}") from e
        header = list(ALL_COLS)
        if all_values:
            all_values[0] = list(ALL_COLS)

    cols = ALL_COLS
    values = _row_to_list(row, cols)
    last_col_letter = chr(ord("A") + len(cols) - 1)

    found_row = None
    for r, line in enumerate(all_values[1:], start=2):
        if len(line) > url_idx and line[url_idx] == url:
            found_row = r
            break

    try:
        if found_row is None:
            ws.append_row(values)
            return "inserted"
        ws.update(f"A{found_row}:{last_col_letter}{found_row}", [values])
        return "updated"
    except Exception as e:
        raise PolicySheetError(f"寫入 '{tab}' 失敗：{e}") from e


def delete_fund_in_policy(
    client: Any, sheet_id: str, policy_id: str, fund_url: str,
) -> bool:
    """從指定保單 tab 刪除一檔基金（fund_url 主鍵）。回傳是否真有刪到。"""
    tab = _sanitize_tab_name(policy_id)
    url = str(fund_url or "").strip()
    if not url:
        raise PolicySheetError("delete_fund_in_policy 必須提供 fund_url")

    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(tab)
    except Exception:
        return False

    try:
        all_values = ws.get_all_values()
    except Exception as e:
        raise PolicySheetError(f"讀取 '{tab}' 失敗：{e}") from e

    if not all_values:
        return False
    header = all_values[0]
    try:
        url_idx = header.index("fund_url")
    except ValueError:
        return False

    for r, line in enumerate(all_values[1:], start=2):
        if len(line) > url_idx and line[url_idx] == url:
            try:
                ws.delete_rows(r)
                return True
            except Exception as e:
                raise PolicySheetError(f"刪除 '{tab}' 列失敗：{e}") from e
    return False


def delete_policy_worksheet(client: Any, sheet_id: str, policy_id: str) -> bool:
    """刪除整個保單 tab（含所有基金）。回傳是否真有刪到。"""
    tab = _sanitize_tab_name(policy_id)
    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(tab)
    except Exception:
        return False
    try:
        sh.del_worksheet(ws)
        return True
    except Exception as e:
        raise PolicySheetError(f"刪除 worksheet '{tab}' 失敗：{e}") from e


# ──────────────────────────────────────────────────────────────────────
# v18.40 自動建立新 Sheet（免去使用者先到 Drive 開檔）
# ──────────────────────────────────────────────────────────────────────
def rename_sheet(client: Any, sheet_id: str, new_title: str) -> bool:
    """v18.48：重新命名既有 Google Sheet。需要編輯權限。"""
    if not sheet_id or not (new_title or "").strip():
        raise PolicySheetError("rename_sheet: sheet_id 或 new_title 為空")
    try:
        sh = client.open_by_key(sheet_id)
        sh.update_title(new_title.strip())
        return True
    except Exception as e:
        _hint = f"[{type(e).__name__}] {e}" if str(e) else type(e).__name__
        raise PolicySheetError(f"重新命名 Sheet 失敗：{_hint}") from e


def get_sheet_title(client: Any, sheet_id: str) -> str:
    """v18.48：取得 Sheet 目前的標題。失敗回空字串。"""
    if not sheet_id:
        return ""
    try:
        sh = client.open_by_key(sheet_id)
        return getattr(sh, "title", "") or ""
    except Exception:
        return ""


def list_user_sheets(client: Any, folder_id: str = "") -> list[dict]:
    """v18.45：列出使用者 Drive 內所有 Google Sheets。

    Args:
        client: gspread Client (OAuth)
        folder_id: 若提供，僅列該資料夾內的 Sheets；留空 = 列全部。

    需要 OAuth scope `drive.metadata.readonly`（或 drive.readonly）。
    回傳 [{"id": ..., "name": ...}, ...] 依名稱排序。

    v18.155：直接走 Drive v3 API（同 `list_user_folders`）加 `trashed=false` 過濾，
    取代原本 gspread `list_spreadsheet_files()`（會抓出已刪除 / trashed Sheets，造成
    UI 下拉出現殭屍項）。
    """
    url = "https://www.googleapis.com/drive/v3/files"
    q_parts = [
        'mimeType="application/vnd.google-apps.spreadsheet"',
        "trashed=false",
    ]
    if folder_id and folder_id.strip():
        q_parts.append(f'"{folder_id.strip()}" in parents')
    params = {
        "q": " and ".join(q_parts),
        "pageSize": 1000,
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
        "fields": "nextPageToken,files(id,name)",
    }
    files: list[dict] = []
    page_token: str | None = None
    try:
        while True:
            if page_token:
                params["pageToken"] = page_token
            resp = client.http_client.request("get", url, params=params)
            data = resp.json() if hasattr(resp, "json") else resp
            for f in (data.get("files") or []):
                _id, _nm = f.get("id"), f.get("name")
                if _id and _nm:
                    files.append({"id": _id, "name": _nm})
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        _hint = f"[{type(e).__name__}] {e}" if str(e) else type(e).__name__
        raise PolicySheetError(f"列出 Drive Sheets 失敗：{_hint}") from e
    files.sort(key=lambda x: x["name"].lower())
    return files


def list_user_folders(client: Any) -> list[dict]:
    """v18.146：列出使用者 Google Drive 內所有資料夾（含共享）。

    走 gspread http_client 打 Drive v3 API（不依賴 googleapiclient）。
    需要 OAuth scope `drive.metadata.readonly`。
    回傳 [{"id": ..., "name": ...}, ...] 依名稱排序。
    """
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": 'mimeType="application/vnd.google-apps.folder" and trashed=false',
        "pageSize": 1000,
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
        "fields": "nextPageToken,files(id,name)",
    }
    folders: list[dict] = []
    page_token: str | None = None
    try:
        while True:
            if page_token:
                params["pageToken"] = page_token
            resp = client.http_client.request("get", url, params=params)
            data = resp.json()
            for f in (data.get("files") or []):
                _id, _nm = f.get("id"), f.get("name")
                if _id and _nm:
                    folders.append({"id": _id, "name": _nm})
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        _hint = f"[{type(e).__name__}] {e}" if str(e) else type(e).__name__
        raise PolicySheetError(f"列出 Drive 資料夾失敗：{_hint}") from e
    folders.sort(key=lambda x: x["name"].lower())
    return folders


def create_dashboard_sheet(client: Any,
                            title: str = "Fund Dashboard - 投資組合") -> tuple[str, str]:
    """建立新 Google Sheet 並回傳 (sheet_id, sheet_url)。
    OAuth 模式下 client 的 `drive.file` scope 已允許建立並擁有此檔。
    """
    try:
        sh = client.create(title)
    except Exception as e:
        raise PolicySheetError(f"建立 Sheet 失敗：{e}") from e
    sheet_id = getattr(sh, "id", "") or ""
    sheet_url = getattr(sh, "url", "") or (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else "")
    if not sheet_id:
        raise PolicySheetError("建立 Sheet 後未取得 ID（gspread 回傳異常）")
    return sheet_id, sheet_url


# ════════════════════════════════════════════════════════════
# v18.149 — Schema v2（snapshot-only，內聯 _T7_State 持倉 + 多幣別現金）
# ════════════════════════════════════════════════════════════
# 設計目的：把舊 3-tab（保單分頁 + _T7_State + _Ledgers）的「**目前持倉**」內聯
# 到單張保單 worksheet。T7 變成純讀模擬器；user 真的加碼贖回時自己改 Sheet。
#
# 與 v1 的差異：
# - v1：保單分頁只有「規劃投入」(invest_twd / fx_at_buy)，實際持倉在 _T7_State.ledger_json
# - v2：保單分頁同時有「規劃投入」(invest_twd) + 「目前持倉」(units / avg_nav / avg_fx)
#       + 「多幣別現金部位」（item_type=cash 列）
# - v2 不需要 _Ledgers（T7 唯讀），不需要 _T7_State（資料內聯了）
#
# v1 → v2 migration 走 `scripts/migrate_v149_schema.py`。
# 偵測方式：worksheet 第一列 header 含 `item_type` 即為 v2。
ALL_COLS_V2: tuple[str, ...] = (
    "policy_id",
    "item_type",         # "fund" | "cash"
    "fund_code",
    "fund_name",
    "units",
    "avg_nav",
    "avg_nav_with_div",  # v18.153: 平均買入「含息」單位成本（對帳單欄(10)）
    "avg_fx",
    "currency",
    "tier",              # "core" | "satellite" | ""
    "amount",            # cash 列才填（多幣別現金金額）
    "invest_twd",        # 淨投資金額（對帳單欄(4)），= units × avg_nav × avg_fx
    "div_cash_pct",      # v18.160: 配息「現金給付」百分比 (0~100)；單位數% = 100 - 該值
)

ITEM_TYPE_FUND = "fund"
ITEM_TYPE_CASH = "cash"

# v18.153：中文 header 雙向翻譯（Sheet 上顯示中文、程式內部仍用英文 col name）
ZH_HEADERS_V2: dict[str, str] = {
    "policy_id":         "保單編號",
    "item_type":         "類型",
    "fund_code":         "基金代號",
    "fund_name":         "基金名稱",
    "units":             "持有單位數",
    "avg_nav":           "平均買入單位成本",
    "avg_nav_with_div":  "平均買入含息單位成本",
    "avg_fx":            "平均買入匯率",
    "currency":          "幣別",
    "tier":              "級別",
    "amount":            "金額",
    "invest_twd":        "淨投資金額",
    "div_cash_pct":      "現金給付%",   # v18.160
}
EN_HEADERS_V2: dict[str, str] = {v: k for k, v in ZH_HEADERS_V2.items()}

# v18.153：欄位填寫責任分類（給 UI + Sheet 配色用）
# user 自行填寫（從對帳單抄）：黃底
USER_INPUT_COLS: tuple[str, ...] = (
    "policy_id", "fund_code", "avg_nav", "avg_nav_with_div",
    "avg_fx", "amount", "invest_twd",
    "div_cash_pct",   # v18.160: user 從保險公司 APP 抄（如 80% 現金 / 20% 單位）
)
# 自動填寫（MoneyDJ 抓 / 系統算 / 系統定）：灰底（read-only signal）
AUTO_COLS: tuple[str, ...] = (
    "item_type", "fund_name", "units", "currency", "tier",
)


def _normalize_header_to_en(header_cell: str) -> str:
    """收到一個 header cell（可能是中文或英文）→ 回對應的英文 col name。
    認不出來就回原字串（向後相容 v1 schema 偵測）。"""
    s = str(header_cell or "").strip()
    return EN_HEADERS_V2.get(s, s)


def compute_units(invest_twd: float, avg_nav: float, avg_fx: float) -> float:
    """v18.153：對帳單算式 units = invest_twd / (avg_nav × avg_fx)。

    任一分母為 0 或負 → 回 0（避除以 0）。
    """
    try:
        denom = float(avg_nav) * float(avg_fx)
        if denom <= 0:
            return 0.0
        return float(invest_twd) / denom
    except (TypeError, ValueError):
        return 0.0


def avg_nav_with_div_from_cumul_div_twd(
    avg_nav: float, avg_fx: float, units: float, cumul_div_twd: float,
) -> float:
    """v18.157：從「累積現金配息金額 (TWD)」反推「平均買入含息單位成本」。

    場景：對帳單沒列「平均買入含息單位成本」，但有「累積現金配息金額 (NT)」
    與「累積含息回報率」（兩者擇一足夠）。

    公式（local currency per unit）：
        含息成本 per unit = avg_nav − (累積配息 local / units)
                          = avg_nav − (cumul_div_twd / (avg_fx × units))

    任一分母為 0/負 → 回 0（讓 caller 顯示「無含息成本資料」）。
    """
    try:
        units_f = float(units)
        fx_f = float(avg_fx)
        nav_f = float(avg_nav)
        div_twd = float(cumul_div_twd)
        denom = fx_f * units_f
        if denom <= 0 or nav_f <= 0:
            return 0.0
        per_unit_div_local = div_twd / denom
        result = nav_f - per_unit_div_local
        return max(0.0, result)
    except (TypeError, ValueError):
        return 0.0


def is_v2_worksheet(ws: Any) -> bool:
    """偵測單張 worksheet 是不是 v2 schema：

    - 含 `item_type` 英文 header → v2（v18.149 以來）
    - 含 `類型` 中文 header → v2（v18.153 中文 schema）
    讀檔失敗 / 無 header 一律回 False（caller 走 v1 fallback 安全）。
    """
    try:
        header = _with_quota_retry(ws.row_values, 1) or []
    except Exception:
        return False
    cells = [str(c).strip() for c in header]
    return "item_type" in cells or "類型" in cells


def detect_sheet_schema_version(client: Any, sheet_id: str) -> str:
    """偵測整本 Sheet 是 v1 還是 v2：

    - 沒有任何保單 worksheet → "empty"（一張新 Sheet）
    - 至少一張保單分頁 header 含 item_type → "v2"
    - 否則 → "v1"（舊 schema 待升級）
    """
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        tabs = [ws for ws in _with_quota_retry(sh.worksheets)
                if not ws.title.startswith("_") and ws.title != DEFAULT_WORKSHEET]
    except Exception as e:
        raise PolicySheetError(f"開啟 Sheet 失敗：{e}") from e
    if not tabs:
        return "empty"
    for ws in tabs:
        if is_v2_worksheet(ws):
            return "v2"
    return "v1"



def estimate_dividend_split(
    invest_twd: float,
    annual_div_rate_pct: float,
    div_cash_pct: float,
    avg_nav: float = 0.0,
    avg_fx: float = 0.0,
    current_fx: float = 0.0,
    current_nav: float = 0.0,
) -> dict[str, float]:
    """v18.160：依 user 設定的「現金給付%」拆分年配息估算。

    v18.273：分離「成本基礎 FX/NAV」與「配息折算 FX/NAV」 — user 反饋
    「組合買入的匯率固定，但轉配息由美元轉台必須要即時匯率」。
    - 成本基礎用 avg_* （買入時的歷史值，不變）
    - 配息折算用 current_*（未傳則 fallback 到 avg_*，向後相容）

    Args:
        invest_twd: 淨投資金額 (TWD)
        annual_div_rate_pct: 年配息率 (%)，如 6 表示 6%
        div_cash_pct: 配息現金給付百分比 (0~100)
        avg_nav: 平均買入單位成本
        avg_fx: 平均買入匯率
        current_fx: 配息發放當下匯率（傳 0 視為「等同 avg_fx」）
        current_nav: 配息發放當下 NAV（用於再投入新單位數，傳 0 → 用 avg_nav）

    Returns:
        dict 含：
        - annual_div_twd:  年配息折算 TWD（用 current_fx）
        - cash_twd:        年現金給付部分 TWD
        - reinvest_twd:    年再投入部分 TWD
        - new_units:       年新增單位數（用 current_nav × current_fx 還原）
        - cash_pct / unit_pct: echo back
        - fx_ratio:        current_fx / avg_fx（>1 為新台幣貶值對配息有利）
    """
    try:
        inv = float(invest_twd or 0)
        rate = float(annual_div_rate_pct or 0)
        cash_pct = max(0.0, min(100.0, float(div_cash_pct or 0)))
    except (TypeError, ValueError):
        return {
            "annual_div_twd": 0.0, "cash_twd": 0.0, "reinvest_twd": 0.0,
            "new_units": 0.0, "cash_pct": 0.0, "unit_pct": 100.0,
            "fx_ratio": 1.0,
        }
    try:
        afx = float(avg_fx or 0)
        cfx = float(current_fx or 0)
    except (TypeError, ValueError):
        afx = cfx = 0.0
    # 配息折算 FX：current_fx 有給且 > 0 → 用 current；否則 fallback avg_fx
    eff_fx = cfx if cfx > 0 else afx
    fx_ratio = (eff_fx / afx) if (afx > 0 and eff_fx > 0) else 1.0
    annual_div_twd = inv * rate / 100.0 * fx_ratio
    cash_twd = annual_div_twd * cash_pct / 100.0
    reinvest_twd = annual_div_twd - cash_twd
    new_units = 0.0
    try:
        # 再投入單位數：用「配息時的 NAV × FX」還原 local 後 ÷ NAV
        anav = float(avg_nav or 0)
        cnav = float(current_nav or 0)
        eff_nav = cnav if cnav > 0 else anav
        denom = eff_nav * eff_fx
        if denom > 0:
            new_units = reinvest_twd / denom
    except (TypeError, ValueError):
        new_units = 0.0
    return {
        "annual_div_twd": annual_div_twd,
        "cash_twd": cash_twd,
        "reinvest_twd": reinvest_twd,
        "new_units": new_units,
        "fx_ratio": fx_ratio,
        "cash_pct": cash_pct,
        "unit_pct": 100.0 - cash_pct,
    }


def _normalize_div_cash_pct(v: Any) -> float:
    """v18.160：配息現金給付百分比 (0~100)。
    缺值/解析失敗 → 100（多數保單預設「全部現金給付」）。
    超界 → clip 到 [0, 100]。
    """
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return 100.0
    if isinstance(v, (int, float)):
        n = float(v)
    else:
        s = str(v).replace("%", "").replace(",", "").strip()
        if not s:
            return 100.0
        try:
            n = float(s)
        except (TypeError, ValueError):
            return 100.0
    if n < 0:
        return 0.0
    if n > 100:
        return 100.0
    return n


def load_policy_v2(client: Any, sheet_id: str, policy_id: str) -> pd.DataFrame:
    """讀單張 v2 保單分頁，回 DataFrame（11 欄齊備）。

    若該 worksheet 不存在或非 v2 schema → 回空 DataFrame（11 欄 header 齊）。
    """
    empty = pd.DataFrame(columns=list(ALL_COLS_V2))
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        title = _sanitize_tab_name(policy_id)
        try:
            ws = _with_quota_retry(sh.worksheet, title)
        except Exception:
            return empty
        if not is_v2_worksheet(ws):
            return empty
        rows = _with_quota_retry(ws.get_all_records) or []
    except Exception as e:
        raise PolicySheetError(f"讀取 v2 保單分頁失敗：{e}") from e
    if not rows:
        return empty
    df = pd.DataFrame(rows)
    # v18.153：rename 中文 header → 英文 col name（向後相容雙語）
    df = df.rename(columns={zh: en for zh, en in EN_HEADERS_V2.items()
                              if zh in df.columns})
    for c in ALL_COLS_V2:
        if c not in df.columns:
            df[c] = ""
    df = df[list(ALL_COLS_V2)].copy()
    df["units"]            = df["units"].map(_normalize_float)
    df["avg_nav"]          = df["avg_nav"].map(_normalize_float)
    df["avg_nav_with_div"] = df["avg_nav_with_div"].map(_normalize_float)
    df["avg_fx"]           = df["avg_fx"].map(_normalize_float)
    df["amount"]           = df["amount"].map(_normalize_float)
    df["invest_twd"]       = df["invest_twd"].map(_normalize_invest_twd)
    # v18.160：div_cash_pct 預設 100（全現金給付）；舊 Sheet 缺欄補 100；超界 clip
    df["div_cash_pct"]     = df["div_cash_pct"].map(_normalize_div_cash_pct)
    return df


def write_policy_v2(
    client: Any, sheet_id: str, policy_id: str, df: pd.DataFrame,
) -> int:
    """整 tab 覆寫單張 v2 保單分頁（user 點「💾 存到雲端」時呼叫）。

    df 缺欄會自動補空字串；多餘欄會被丟掉（只寫 ALL_COLS_V2 11 欄）。
    回傳寫入列數（不含 header）。
    """
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        title = _sanitize_tab_name(policy_id)
        try:
            ws = _with_quota_retry(sh.worksheet, title)
        except Exception as _e_ws:
            # v18.253：只在「真的找不到分頁」時才 add_worksheet；
            # 429 quota / 其他 API 錯誤一律 raise，避免誤判成「不存在」→
            # 試圖建立 → 撞既存分頁拿 400 Invalid addSheet。
            if not _is_worksheet_not_found(_e_ws):
                raise
            ws = _with_quota_retry(
                sh.add_worksheet, title=title,
                rows=max(len(df) + 5, 20),
                cols=len(ALL_COLS_V2) + 2)
    except Exception as e:
        raise PolicySheetError(f"開啟/建立保單分頁失敗：{e}") from e

    norm = df.copy()
    for c in ALL_COLS_V2:
        if c not in norm.columns:
            norm[c] = ""
    norm = norm[list(ALL_COLS_V2)].copy()
    # 整列空（全部欄都空白或 NaN）剔除；pandas NaN.str == 'nan' 要排除
    def _cell_empty(v):
        if v is None:
            return True
        if isinstance(v, float) and pd.isna(v):
            return True
        return str(v).strip() in ("", "nan", "NaN", "None")
    norm = norm[norm.apply(lambda r: not all(_cell_empty(v) for v in r), axis=1)]

    # v18.153：fund 列 units 自動算（單純存便利、給 T7 模擬用；不依賴 user 手填）
    rows_out: list[list] = [
        [ZH_HEADERS_V2[c] for c in ALL_COLS_V2],   # 中文 header 列
    ]
    for _, r in norm.iterrows():
        is_fund = r.get("item_type") == ITEM_TYPE_FUND
        is_cash = r.get("item_type") == ITEM_TYPE_CASH
        # fund 列 units 用公式自動算（若 user override 過則優先用 user 給的非零值）
        _u_user = _normalize_float(r.get("units", 0))
        _avg_nav = _normalize_float(r.get("avg_nav", 0))
        _avg_fx  = _normalize_float(r.get("avg_fx", 0))
        _inv_twd = _normalize_invest_twd(r.get("invest_twd", 0))
        _u_calc = compute_units(_inv_twd, _avg_nav, _avg_fx)
        _u_final = _u_user if (_u_user > 0 and abs(_u_user - _u_calc) > 0.5) else _u_calc
        rows_out.append([
            str(r.get("policy_id", "") or ""),
            str(r.get("item_type", "") or ""),
            str(r.get("fund_code", "") or ""),
            str(r.get("fund_name", "") or ""),
            _u_final if is_fund else "",
            _avg_nav if is_fund else "",
            _normalize_float(r.get("avg_nav_with_div", 0)) if is_fund else "",
            _avg_fx if is_fund else "",
            str(r.get("currency", "") or ""),
            str(r.get("tier", "") or "") if is_fund else "",
            _normalize_float(r.get("amount", 0)) if is_cash else "",
            _inv_twd if is_fund else "",
        ])
    try:
        _with_quota_retry(ws.clear)
        _with_quota_retry(ws.update, "A1", rows_out)
        # v18.153：header 配色 — user-input 黃、auto 灰
        _apply_v2_header_format(ws)
    except Exception as e:
        raise PolicySheetError(f"寫入 v2 保單分頁失敗：{e}") from e
    return len(rows_out) - 1


def _apply_v2_header_format(ws: Any) -> None:
    """v18.153：把 v2 worksheet 的 header 列依 user-input/auto 上色。

    - USER_INPUT_COLS → 黃底 (#fff2cc)
    - AUTO_COLS       → 灰底 (#e0e0e0)
    全部 bold。配色失敗（gspread format API 例外）不拋，靜默放過。
    """
    user_bg = {"red": 1.0, "green": 0.949, "blue": 0.8}      # #fff2cc
    auto_bg = {"red": 0.878, "green": 0.878, "blue": 0.878}  # #e0e0e0
    bold = {"bold": True}
    user_ranges: list[str] = []
    auto_ranges: list[str] = []
    for i, c in enumerate(ALL_COLS_V2):
        col_letter = chr(ord("A") + i)
        rng = f"{col_letter}1"
        if c in USER_INPUT_COLS:
            user_ranges.append(rng)
        else:
            auto_ranges.append(rng)
    try:
        if user_ranges:
            _with_quota_retry(
                ws.format, user_ranges,
                {"backgroundColor": user_bg, "textFormat": bold})
        if auto_ranges:
            _with_quota_retry(
                ws.format, auto_ranges,
                {"backgroundColor": auto_bg, "textFormat": bold})
    except Exception:
        pass  # smoke-allow-pass — 配色失敗不影響資料正確性


def load_all_policies_v2(client: Any, sheet_id: str) -> pd.DataFrame:
    """讀整本 Sheet 內所有 v2 保單分頁，合併成一張 DataFrame。

    非 v2 的 worksheet 自動跳過（caller 應先用 detect_sheet_schema_version
    判斷整本狀態並引導升級）。
    """
    try:
        sh = _with_quota_retry(client.open_by_key, sheet_id)
        tabs = [ws for ws in _with_quota_retry(sh.worksheets)
                if not ws.title.startswith("_") and ws.title != DEFAULT_WORKSHEET]
    except Exception as e:
        raise PolicySheetError(f"列保單分頁失敗：{e}") from e
    frames: list[pd.DataFrame] = []
    for ws in tabs:
        if not is_v2_worksheet(ws):
            continue
        try:
            rows = _with_quota_retry(ws.get_all_records) or []
        except Exception:
            continue
        if not rows:
            continue
        df_one = pd.DataFrame(rows)
        # v18.153：中文 header → 英文 col name
        df_one = df_one.rename(columns={zh: en for zh, en in EN_HEADERS_V2.items()
                                          if zh in df_one.columns})
        for c in ALL_COLS_V2:
            if c not in df_one.columns:
                df_one[c] = ""
        df_one = df_one[list(ALL_COLS_V2)].copy()
        df_one["units"]            = df_one["units"].map(_normalize_float)
        df_one["avg_nav"]          = df_one["avg_nav"].map(_normalize_float)
        df_one["avg_nav_with_div"] = df_one["avg_nav_with_div"].map(_normalize_float)
        df_one["avg_fx"]           = df_one["avg_fx"].map(_normalize_float)
        df_one["amount"]           = df_one["amount"].map(_normalize_float)
        df_one["invest_twd"]       = df_one["invest_twd"].map(_normalize_invest_twd)
        df_one["div_cash_pct"]     = df_one["div_cash_pct"].map(_normalize_div_cash_pct)
        frames.append(df_one)
    if not frames:
        return pd.DataFrame(columns=list(ALL_COLS_V2))
    return pd.concat(frames, ignore_index=True)


def copy_sheet_as_backup(
    client: Any, src_sheet_id: str, backup_suffix: str = " - backup",
) -> tuple[str, str]:
    """v18.149 migration safety net：把整本 Sheet copy 一份做 backup。

    gspread 6.x 用 `client.copy(file_id, title=..., copy_permissions=False)` 走 Drive API。
    回傳 (backup_sheet_id, backup_sheet_url)。
    """
    try:
        src_title = get_sheet_title(client, src_sheet_id) or "Fund Dashboard"
    except Exception:
        src_title = "Fund Dashboard"
    import datetime as _dt
    backup_title = f"{src_title}{backup_suffix} {_dt.datetime.now().strftime('%Y%m%d_%H%M')}"
    try:
        new_sh = client.copy(src_sheet_id, title=backup_title, copy_permissions=False)
    except Exception as e:
        raise PolicySheetError(f"備份 Sheet 失敗：{e}") from e
    new_id = getattr(new_sh, "id", "") or ""
    new_url = getattr(new_sh, "url", "") or (
        f"https://docs.google.com/spreadsheets/d/{new_id}/edit" if new_id else "")
    if not new_id:
        raise PolicySheetError("備份成功但未取得新 Sheet ID")
    return new_id, new_url
