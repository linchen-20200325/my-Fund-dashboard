"""repositories/policy/_helpers.py — 共用 helpers(B2 拆自 policy_repository v19.206).

從原 1372 LOC god module 拆出 v1 + v2 共用的 module-level constants / 例外 /
gspread retry helper / Google client 建立 / `_*` normalization helpers。

v1.py + v2.py 都從本檔 import,規避 P2-4 v19.199 revert 主因(`from X import *`
不取 `_*`,v2 用到 v1 的 `_normalize_*` 私函必須 explicit import — 集中後省解耦)。
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd

# v19.385 T2a:gspread 429 偵測 + 退避迴圈收 L0 infra(與 snapshot_repository 去重)。
# 保留私名 `_is_quota_error` 供既有 caller / test(from policy_repository import _is_quota_error)。
from infra.gspread_retry import (
    is_quota_error as _is_quota_error,
    with_quota_retry as _shared_quota_retry,
)


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
# v18.183：新增 div_cash_pct / avg_nav_with_div —— 接在尾端（既有欄位位置不變、
# 純追加），讓 T7 設定的「現金給付%」「含息成本」也能存進 v1 保單分頁 + 全部讀回不掉。
OPTIONAL_COLS: tuple[str, ...] = (
    "policy_tier",       # "core" / "satellite" / ""，控制保單級配置統計
    "div_cash_pct",      # v18.183: 配息現金給付% (0~100)
    "avg_nav_with_div",  # v18.183: 平均買入含息單位成本（對帳單欄(10)）
    # v18.198：把完整成本基礎也存進保單分頁（寫入時從 t7_ledgers 帶出），讓保單分頁
    # 自成完整、不再「存檔資料沒有全部」（原本這三欄只在 _T7_State / _持倉總覽）。
    "avg_nav",           # v18.198: 平均買入淨值（cost_unit）
    "fx_avg",            # v18.198: 平均買入匯率（fx_avg）
    "units",             # v18.198: 持有單位數
)

ALL_COLS: tuple[str, ...] = REQUIRED_COLS + OPTIONAL_COLS

DEFAULT_WORKSHEET = "Policies"

_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
)


class PolicySheetError(Exception):
    """所有 policy_store 對外丟出的錯誤都用這個 class。"""


# v18.152：Google Sheets API 429 配額退避。每 user 每分鐘 60 reads，v2 編輯介面進場
# 一次就 1 + 2N reads（N=保單數），容易爆配額。本層所有 gspread 呼叫應走 _with_quota_retry。
# v18.253：起點 1→2s（給 Google quota 視窗多一拍 reset），總等待 15s→30s。
# v19.385 T2a：偵測 + 迴圈收 infra.gspread_retry；退避節奏 _QUOTA_BACKOFFS 仍本層專屬
# （30s，snapshot 為 15s，值不同不合併，§8.4）。
_QUOTA_BACKOFFS: tuple[float, ...] = (2.0, 4.0, 8.0, 16.0)


def _is_worksheet_not_found(exc: BaseException) -> bool:
    """v18.253：偵測 gspread WorksheetNotFound（duck-typed，避免依賴
    gspread.exceptions 容版差）。配合 write_policy_v2 區分「分頁不存在」與
    「429 quota」: 後者重試，前者才 add_worksheet — 杜絕「429 誤判成不存在
    → addSheet 撞 400 Invalid」連鎖崩潰。

    同時吃 class name 與 message string，相容 gspread 真實例外與測試環境的
    `Exception("WorksheetNotFound")` 模擬慣例。"""
    return (type(exc).__name__ == "WorksheetNotFound"
            or "WorksheetNotFound" in str(exc))


def _with_quota_retry(call, *args, **kwargs):
    """policy 層 gspread 退避（節奏 _QUOTA_BACKOFFS=30s）；邏輯委派 infra.gspread_retry。"""
    return _shared_quota_retry(call, *args, backoffs=_QUOTA_BACKOFFS, **kwargs)


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


def _row_to_list(row: dict, cols: tuple[str, ...] = REQUIRED_COLS) -> list:
    """B2 v19.206:從 v1.py 搬上來,v1+v2 共用(upsert row 序列化)。"""
    return [row.get(c, "") for c in cols]
