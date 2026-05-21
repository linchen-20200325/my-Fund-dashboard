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


# v18.152：Google Sheets API 429 配額退避（與 snapshot_repository 一致）
# 每 user 每分鐘 60 reads，v2 編輯介面進場一次就 1 + 2N reads（N=保單數），
# 容易爆配額。本層所有 gspread 呼叫應走 _with_quota_retry。
_QUOTA_BACKOFFS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)


def _is_quota_error(exc: BaseException) -> bool:
    """偵測 gspread 429 / RESOURCE_EXHAUSTED；不依賴 gspread.exceptions 細節容版差。"""
    msg = str(exc)
    return ("429" in msg or "Quota exceeded" in msg or "RATE_LIMIT" in msg
            or "RESOURCE_EXHAUSTED" in msg)


def _with_quota_retry(call, *args, **kwargs):
    """包裝 gspread 呼叫：遇 429 退避重試；非配額錯誤立即拋。"""
    import time as _t
    last_err: BaseException | None = None
    for attempt, delay in enumerate(_QUOTA_BACKOFFS):
        try:
            return call(*args, **kwargs)
        except Exception as e:  # noqa: BLE001 — gspread 例外類型隨版本變
            last_err = e
            is_last = attempt == len(_QUOTA_BACKOFFS) - 1
            if not _is_quota_error(e) or is_last:
                raise
            _t.sleep(delay)
    if last_err is not None:
        raise last_err


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


def _normalize_float(v: Any, default: float = 0.0) -> float:
    """容錯：'1,234.56' / '' / None → float（失敗回 default）。"""
    if v is None or v == "":
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    if not s:
        return default
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def estimate_dividend_split(
    invest_twd: float,
    annual_div_rate_pct: float,
    div_cash_pct: float,
    avg_nav: float = 0.0,
    avg_fx: float = 0.0,
) -> dict[str, float]:
    """v18.160：依 user 設定的「現金給付%」拆分年配息估算。

    Args:
        invest_twd: 淨投資金額 (TWD)
        annual_div_rate_pct: 年配息率 (%)，如 6 表示 6%
        div_cash_pct: 配息現金給付百分比 (0~100)
        avg_nav: 平均買入單位成本（用來算「新增單位數」）；給 0 → new_units 回 0
        avg_fx: 平均買入匯率（用來把 TWD 還原 local currency）；給 0 → new_units 回 0

    Returns:
        dict 含：
        - annual_div_twd:  年配息總額 (TWD)
        - cash_twd:        年現金給付部分 (TWD)
        - reinvest_twd:    年再投入新單位部分 (TWD)
        - new_units:       年新增單位數（local currency per unit 除回去）
        - cash_pct / unit_pct: echo back for display
    """
    try:
        inv = float(invest_twd or 0)
        rate = float(annual_div_rate_pct or 0)
        cash_pct = max(0.0, min(100.0, float(div_cash_pct or 0)))
    except (TypeError, ValueError):
        return {
            "annual_div_twd": 0.0, "cash_twd": 0.0, "reinvest_twd": 0.0,
            "new_units": 0.0, "cash_pct": 0.0, "unit_pct": 100.0,
        }
    annual_div_twd = inv * rate / 100.0
    cash_twd = annual_div_twd * cash_pct / 100.0
    reinvest_twd = annual_div_twd - cash_twd
    new_units = 0.0
    try:
        nav = float(avg_nav or 0)
        fx = float(avg_fx or 0)
        denom = nav * fx
        if denom > 0:
            new_units = reinvest_twd / denom
    except (TypeError, ValueError):
        new_units = 0.0
    return {
        "annual_div_twd": annual_div_twd,
        "cash_twd": cash_twd,
        "reinvest_twd": reinvest_twd,
        "new_units": new_units,
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
        except Exception:
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
        pass  # noqa: smoke-allow-pass — 配色失敗不影響資料正確性


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
