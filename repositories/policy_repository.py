"""
repositories/policy_repository.py — 保單視圖 Google Sheets 儲存層
（v11.0 從 policy_store.py 搬入；原 Policy Store P1.2）

設計原則（與 CLAUDE.md §2 精準讀寫 §4 鋼鐵自省一致）：
- 純資料層：不 import streamlit、不寫死 UI 訊息
- gspread / google-auth 採 lazy import：模組載入不依賴第三方套件
  → 未安裝時 `get_gspread_client` 觸發 PolicySheetError；其餘 CRUD 函式以
    duck-typed client/worksheet 操作，便於 MagicMock 單元測試
- 全部錯誤統一包成 PolicySheetError，呼叫端只接這個例外

Sheet schema（8 欄，順序固定）：
    policy_id | policy_name | fund_url | invest_twd | invest_date |
    currency  | fx_at_buy   | notes

一張 Sheet = 多保單，每列 = (保單, 基金) 一對。
同 policy_id 多列即為「一張保單下的多檔基金」。

v11.0 分層歸位：本檔屬於 Repository Layer，Google Sheets per-policy worksheet API。
向後相容：根目錄 policy_store.py 保留 `from repositories.policy_repository import *` shim，
        E 階段收尾後 shim 刪除。同 Phase 的 ledger_repository / snapshot_repository
        透過 policy_store shim 取 PolicySheetError 仍可工作（雙重 shim 一跳）。
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd


REQUIRED_COLS: tuple[str, ...] = (
    "policy_id",
    "policy_name",
    "fund_url",
    "invest_twd",
    "invest_date",
    "currency",
    "fx_at_buy",
    "notes",
)

# P3：選填欄，舊 Sheet 沒這欄也能讀寫
OPTIONAL_COLS: tuple[str, ...] = (
    "policy_tier",   # "core" / "satellite" / ""，控制保單級配置統計
)

ALL_COLS: tuple[str, ...] = REQUIRED_COLS + OPTIONAL_COLS

DEFAULT_WORKSHEET = "Policies"

_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
)


class PolicySheetError(Exception):
    """所有 policy_store 對外丟出的錯誤都用這個 class。"""


# ──────────────────────────────────────────────────────────────────────
# 連線：lazy import，避免測試環境/未安裝套件時 import 失敗
# ──────────────────────────────────────────────────────────────────────
def get_gspread_client(credentials: dict) -> Any:
    """
    用 Service Account JSON dict 換一個已授權的 gspread Client。

    credentials: 從 st.secrets["google_service_account"] 來的 dict（必含
                 type / project_id / private_key / client_email 等欄位）
    """
    if not isinstance(credentials, dict) or not credentials.get("client_email"):
        raise PolicySheetError("Service Account credentials 缺 client_email 欄位")

    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except ImportError as e:
        raise PolicySheetError(
            f"gspread / google-auth 未安裝：{e}；請 `pip install gspread google-auth`"
        ) from e

    try:
        creds = Credentials.from_service_account_info(dict(credentials), scopes=list(_SCOPES))
        return gspread.authorize(creds)
    except Exception as e:
        raise PolicySheetError(f"Service Account 授權失敗：{e}") from e


def get_gspread_client_from_oauth(user_credentials: Any) -> Any:
    """
    P4: 從 oauth_helper.build_credentials_from_tokens() 拿到的 google.oauth2.credentials.Credentials
    建一個 gspread Client。

    user_credentials: google.oauth2.credentials.Credentials 物件（已含 access_token + refresh_token）
    """
    if user_credentials is None:
        raise PolicySheetError("user_credentials 為 None；先完成 OAuth flow")

    try:
        import gspread  # type: ignore
    except ImportError as e:
        raise PolicySheetError(f"gspread 未安裝：{e}；請 `pip install gspread`") from e

    try:
        return gspread.authorize(user_credentials)
    except Exception as e:
        raise PolicySheetError(f"OAuth Credentials 授權失敗：{e}") from e


# ──────────────────────────────────────────────────────────────────────
# 內部工具
# ──────────────────────────────────────────────────────────────────────
def _open_worksheet(client: Any, sheet_id: str, worksheet: str = DEFAULT_WORKSHEET) -> Any:
    try:
        sh = client.open_by_key(sheet_id)
        return sh.worksheet(worksheet)
    except Exception as e:
        raise PolicySheetError(f"開啟 Sheet/{worksheet} 失敗：{e}") from e


def _normalize_invest_twd(v: Any) -> int:
    """容錯：'1,000' / 1000.0 / '' → int；無法解析回 0。"""
    if v is None or v == "":
        return 0
    try:
        if isinstance(v, str):
            v = v.replace(",", "").strip()
            if not v:
                return 0
        return int(float(v))
    except (ValueError, TypeError):
        return 0


def _normalize_fx(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────────────────────────────
# Read
# ──────────────────────────────────────────────────────────────────────
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
    return df


# ──────────────────────────────────────────────────────────────────────
# Write：upsert / delete（以 (policy_id, fund_url) 為主鍵）
# ──────────────────────────────────────────────────────────────────────
def _row_to_list(row: dict, cols: tuple[str, ...] = REQUIRED_COLS) -> list:
    return [row.get(c, "") for c in cols]


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
            ws.append_row(list(ALL_COLS))
            header = list(ALL_COLS)
        except Exception as e:
            raise PolicySheetError(f"寫入表頭失敗：{e}") from e

    # 依現有表頭寬度決定寫 8 / 9 欄（向後相容舊 Sheet）
    _has_tier = "policy_tier" in header
    cols = ALL_COLS if _has_tier else REQUIRED_COLS
    values = _row_to_list(row, cols)
    last_col_letter = chr(ord("A") + len(cols) - 1)  # 8 → H、9 → I

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


# ══════════════════════════════════════════════════════════════════════
# P4：per-policy worksheet — 每張保單一個 tab，tab 名 = policy_id
#     舊 API（load_policies / upsert_policy_row / delete_policy_row）仍可用
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
        sh = client.open_by_key(sheet_id)
        names = [ws.title for ws in sh.worksheets()]
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
            ws.append_row(list(ALL_COLS))
        return ws
    except Exception:
        # tab 不存在 → 建立
        try:
            ws = sh.add_worksheet(title=tab, rows=rows, cols=cols)
            ws.append_row(list(ALL_COLS))
            return ws
        except Exception as e:
            raise PolicySheetError(f"建立 worksheet '{tab}' 失敗：{e}") from e


def load_policy_worksheet(client: Any, sheet_id: str, policy_id: str) -> pd.DataFrame:
    """讀單一保單的所有基金列。tab 不存在回空 DataFrame（不丟錯）。"""
    tab = _sanitize_tab_name(policy_id)
    try:
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet(tab)
    except Exception:
        return pd.DataFrame(columns=list(ALL_COLS))

    try:
        records = ws.get_all_records()
    except Exception as e:
        raise PolicySheetError(f"讀取 '{tab}' 失敗：{e}") from e

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
    return df


def load_all_policy_worksheets(client: Any, sheet_id: str) -> pd.DataFrame:
    """跨所有保單 tab 合併成一張 DataFrame（用於分組視圖、總配置統計）。"""
    tabs = list_policy_worksheets(client, sheet_id)
    if not tabs:
        return pd.DataFrame(columns=list(ALL_COLS))
    frames = []
    for tab in tabs:
        try:
            df = load_policy_worksheet(client, sheet_id, tab)
            if not df.empty:
                # tab 名覆寫 policy_id（保證一致性）
                df = df.assign(policy_id=tab)
                frames.append(df)
        except PolicySheetError:
            continue  # 單一 tab 失敗不影響其他
    if not frames:
        return pd.DataFrame(columns=list(ALL_COLS))
    return pd.concat(frames, ignore_index=True)


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

    cols = ALL_COLS if "policy_tier" in header else REQUIRED_COLS
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


def list_user_sheets(client: Any) -> list[dict]:
    """v18.45：列出使用者 Drive 內所有 Google Sheets。
    需要 OAuth scope `drive.metadata.readonly`（或 drive.readonly）。
    回傳 [{"id": ..., "name": ...}, ...] 依名稱排序。
    """
    try:
        files = client.list_spreadsheet_files()
    except Exception as e:
        _hint = f"[{type(e).__name__}] {e}" if str(e) else type(e).__name__
        raise PolicySheetError(f"列出 Drive Sheets 失敗：{_hint}") from e
    out: list[dict] = []
    for f in (files or []):
        _id = f.get("id") if isinstance(f, dict) else getattr(f, "id", None)
        _nm = f.get("name") if isinstance(f, dict) else getattr(f, "name", None)
        if _id and _nm:
            out.append({"id": _id, "name": _nm})
    out.sort(key=lambda x: x["name"].lower())
    return out


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
