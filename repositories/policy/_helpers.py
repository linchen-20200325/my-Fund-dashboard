"""repositories/policy/_helpers.py — 共用 helpers(B2 拆自 policy_repository v19.206).

從原 1372 LOC god module 拆出 v1 + v2 共用的 module-level constants / 例外 /
gspread retry helper / Google client 建立 / `_*` normalization helpers。

v1.py + v2.py 都從本檔 import,規避 P2-4 v19.199 revert 主因(`from X import *`
不取 `_*`,v2 用到 v1 的 `_normalize_*` 私函必須 explicit import — 集中後省解耦)。
"""
from __future__ import annotations

import math
import sys
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
def coerce_sa_credentials(credentials) -> dict:
    """Service Account secret 正規化 → plain dict。

    接受:dict / Streamlit AttrDict(Mapping,原樣轉)、**JSON 字串**(Streamlit TOML 表格
    吃不下多行 private_key 時,改用三引號 `'''<整包 JSON>'''` 貼上;或 NAS/cron env 只能給
    字串 → 自動 `json.loads`)。§1:字串非合法 JSON / 解析非物件 / 空值 → 丟 `PolicySheetError`
    帶可讀原因,不靜默回空(對照 services.nav_history_gs._sa_to_dict,但這裡 fail-loud)。"""
    if isinstance(credentials, str):
        import json
        _s = credentials.strip()
        if not _s:
            raise PolicySheetError("google_service_account 為空字串")
        try:
            parsed = json.loads(_s)
        except (ValueError, TypeError) as e:
            raise PolicySheetError(
                f"google_service_account 是字串但非合法 JSON:{e}"
                "（Streamlit Secrets 請用三引號 google_service_account = '''<整包 JSON>''' 貼上）"
            ) from e
        if not isinstance(parsed, dict):
            raise PolicySheetError("google_service_account JSON 未解析成物件(dict)")
        return parsed
    try:
        return dict(credentials)                 # dict / Streamlit AttrDict(Mapping)→ plain dict
    except (TypeError, ValueError) as e:
        raise PolicySheetError(
            f"google_service_account 型別無法解析為 dict:{type(credentials).__name__}"
        ) from e


def get_gspread_client(credentials) -> Any:
    """
    用 Service Account 憑證(dict / Mapping / **JSON 字串**)換一個已授權的 gspread Client。

    credentials: st.secrets["google_service_account"] —— 字串會自動 `json.loads`
                 (見 `coerce_sa_credentials`)。必含 type / project_id / private_key /
                 client_email 等欄位。
    """
    credentials = coerce_sa_credentials(credentials)     # 接受 str(JSON)/dict/Mapping(§1 fail-loud)
    if not credentials.get("client_email"):
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


# ──────────────────────────────────────────────────────────────────────
# invest_twd（保單投入本金）解析 — §1 Fail Loud：不可靜默歸零
#
# 背景：本欄原本「無法解析一律回 0」，Sheet 打成 `NT$1,000` / `1000元` 等寫法
# 時，該檔基金會在「投入本金」「核心%」「月配息」「回撤權重」全數消失，而畫面
# 上零提示 —— 使用者只能一格一格對才找得出是哪一列。
#
# 現行處置（維持 int 回傳型別，零 caller 破壞）：
#   1. `parse_invest_twd()` 純函式回 (值, 失敗原因)，可單測、可被上層決定 fallback
#   2. `_normalize_invest_twd()` 失敗時 stderr log + 記進 module registry，再回 0
#   3. `normalize_invest_twd_column()` 逐列解析並帶列號/主鍵，供 UI 彙總揭露
# ──────────────────────────────────────────────────────────────────────

# 最近一次載入的解析失敗紀錄（replace 語意：每次 loader 進場先 reset）。
# 上限防呆：壞掉的整張表也不至於把記憶體吃光。
_INVEST_TWD_PARSE_ERRORS: list[dict] = []
_INVEST_TWD_ERR_CAP = 200


def parse_invest_twd(v: Any) -> tuple[Optional[int], Optional[str]]:
    """解析保單投入本金欄 → `(值, 失敗原因)`。

    - `None` / 空字串 / 純空白 / NaN → `(0, None)`：業務語意是「這列沒填本金」，
      **不是**解析失敗（NaN 幾乎都來自 pandas 對空儲存格的表示，報成錯誤會製造
      大量假警報，反而讓真正的格式錯誤被淹沒）
    - 可解析 → `(int, None)`；⚠️ 小數**無條件捨去**（1000.9 → 1000，沿用既有行為）
    - 無法解析（含 ±inf、`NT$1,000`、`1000元`、中文數字）→ `(None, 原因字串)`：
      呼叫端**必須**顯式決定 fallback 並向使用者揭露，禁止當成 0 靜默吞掉（§1）

    單位：TWD 整數（`amount_twd`），非百分比、非原幣。
    """
    if v is None or v == "":
        return 0, None
    raw = v
    if isinstance(v, str):
        v = v.replace(",", "").strip()
        if not v:
            return 0, None
    try:
        f = float(v)
    except (ValueError, TypeError):
        return None, f"非數值（原始值：{str(raw)[:40]}）"
    if math.isnan(f):
        return 0, None          # 空儲存格
    if math.isinf(f):
        return None, f"數值無界（原始值：{str(raw)[:40]}）"
    return int(f), None


def reset_invest_twd_parse_errors() -> None:
    """loader 進場時呼叫；registry 為 replace 語意（只反映最近一次載入）。"""
    _INVEST_TWD_PARSE_ERRORS.clear()


def get_invest_twd_parse_errors() -> list[dict]:
    """回最近一次載入的本金解析失敗清單（copy，呼叫端改不到內部狀態）。"""
    return list(_INVEST_TWD_PARSE_ERRORS)


def _record_invest_twd_parse_error(rec: dict) -> None:
    if len(_INVEST_TWD_PARSE_ERRORS) < _INVEST_TWD_ERR_CAP:
        _INVEST_TWD_PARSE_ERRORS.append(dict(rec))


def _normalize_invest_twd(v: Any) -> int:
    """容錯：'1,000' / 1000.0 / '' → int。

    ⚠️ 無法解析時仍回 0（維持既有 caller 契約），但**不再靜默**：
    寫 stderr + 記進 registry，供 `get_invest_twd_parse_errors()` 彙總給使用者。
    需要區分「填了 0」與「解析失敗」的呼叫端請改用 `parse_invest_twd()`。
    """
    val, err = parse_invest_twd(v)
    if err is not None:
        print(f"[policy/_helpers] invest_twd 解析失敗 → 以 0 計：{err}",
              file=sys.stderr)
        _record_invest_twd_parse_error({"raw": str(v)[:40], "reason": err})
        return 0
    return val or 0


def normalize_invest_twd_column(
    df: pd.DataFrame,
    *,
    source: str = "",
    id_cols: Iterable[str] = (),
) -> list[dict]:
    """就地把 `df['invest_twd']` 逐列解析成 int，並回報無法解析的列（§1）。

    - 逐列（非 `.map`）是為了取得**列號與主鍵**，讓使用者知道要去 Sheet 改哪一格
    - `row` 為 Google Sheet 的實際列號（header 佔第 1 列 → DataFrame index 0 = 第 2 列）
    - 失敗列仍以 0 記錄（維持既有下游算式不炸），但同時寫入
      `df.attrs['invest_twd_parse_errors']` 與 module registry

    回傳：失敗清單（空 list = 全部可解析）。
    """
    if "invest_twd" not in df.columns:
        return []
    _ids = [c for c in id_cols if c in df.columns]
    bad: list[dict] = []
    vals: list[int] = []
    for _pos, _raw in enumerate(df["invest_twd"].tolist()):
        _v, _err = parse_invest_twd(_raw)
        if _err is not None:
            rec = {
                "row": _pos + 2,
                "source": source,
                "raw": str(_raw)[:40],
                "reason": _err,
            }
            for c in _ids:
                rec[c] = str(df[c].iloc[_pos])
            bad.append(rec)
            _record_invest_twd_parse_error(rec)
            print(f"[policy/{source or 'sheet'}] invest_twd 第 {rec['row']} 列"
                  f"無法解析 → 以 0 計：{_err}", file=sys.stderr)
            _v = 0
        vals.append(_v or 0)
    df["invest_twd"] = vals
    df.attrs["invest_twd_parse_errors"] = bad
    return bad


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
