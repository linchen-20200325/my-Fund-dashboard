"""services/macro/weights_store.py — Route C-2：總經權重 active.json 注入器

v19.250 B(本次):pending review ceremony 整批拔毒(producer + reviewer + pending
API),只留 C-2 active override 機制 — `services/config/macro_weights_active.json`
為唯一權威來源,可手動編輯,production scoring 透過下方 4 個 helper 注入,
active 為空 / corrupt / 欄位 null → 全部回退至呼叫端原本硬編碼,**零回歸**。

公開 API:
- load_active() -> dict
- apply_weight_overrides(ind) -> dict                                              (C-2)
- get_weight_override(key, fallback) -> float                                       (C-2)
- get_verdict_cutoffs(fallback=...) -> tuple[float, float, float, float]           (C-2)
- get_phase_thresholds(fallback=...) -> tuple[float, float, float]                 (C-2)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_ACTIVE_PATH = _CONFIG_DIR / "macro_weights_active.json"

_SCHEMA_VERSION = "v19.0"
_REQUIRED_KEYS = {"version", "indicators"}

# v19.7 / v19.14:Google Sheets backend(治 Streamlit Cloud FS ephemeral)
# Worksheet schema(單一 worksheet `_macro_weights`,active 用 row3):
#   A1: slot              B1: payload_json       C1: updated_at
#   A3: active            B3: <json or "">       C3: <iso ts or "">
# 偵測:st.secrets["google_service_account"].client_email + st.secrets["macro_weights_sheet_id"]
# 兩者皆有 → 走 GS;否則 fallback 至 FS(本地開發友善)。
# v19.250 B:pending row2 / row4 已退役,worksheet 老資料若仍存在會被忽略。
_GS_WORKSHEET = "_macro_weights"
_GS_ACTIVE_ROW = 3
_GS_SLOT_ROWS: dict[str, int] = {"active": _GS_ACTIVE_ROW}


def _empty_active() -> dict[str, Any]:
    """fallback active payload — active.json 不存在 / corrupt 時面板回退硬編碼,這份占位用。"""
    return {
        "version": _SCHEMA_VERSION + "_empty",
        "calibrated_at": None,
        "calibration_method": None,
        "horizon_months": None,
        "drawdown_threshold": None,
        "indicators": {},
        "verdict_cutoffs": None,
        "phase_thresholds": None,
        "oos_metrics": None,
        "ai_explanation": None,
        "notes": "active 檔不存在 → 回退面板硬編碼。",
    }


# ════════════════════════════════════════════════════════════════
# Google Sheets backend (v19.7) — lazy import + 自動建立 worksheet
# ════════════════════════════════════════════════════════════════
def _gs_enabled() -> bool:
    """偵測 Streamlit secrets 是否齊備(service account + sheet_id)。

    v19.197 P1-2:走 infra.config wrapper,本檔不再直 import streamlit。
    """
    try:
        from infra.config import get_secret
        sa = get_secret("google_service_account") or {}
        sid = get_secret("macro_weights_sheet_id")
        return bool(sa.get("client_email") and sid)
    except Exception:
        return False


def _is_missing_worksheet(exc: BaseException) -> bool:
    """「這本試算表上**還沒有** `_macro_weights` 分頁」→ True;**其餘一律 False**。

    False 的意思是「**這次讀不到**」—— 403 未分享 / 429 配額 / 5xx / 連線中斷 /
    憑證壞掉……全部落在這一邊,呼叫端必須讓它**往上拋**
    (§1 Fail Loud:「空的」與「讀不到」不可以壓成同一個回傳值)。

    ⚠️ **在本模組,這條分界線比別處更要命。** `load_active()` 的回傳會被
    `apply_weight_overrides` / `get_weight_override` / `get_verdict_cutoffs` /
    `get_phase_thresholds` 四個注入器拿去當**總經評分的 active override**。
    把「讀不到」壓成「沒有設定」→ 靜默退回硬編碼預設值 →
    **使用者以為自己的校準生效了,其實沒有**,而畫面上不會有任何一處顯示異常。
    那正是 §1 點名的「錯誤的數字比沒有數字更危險」。

    **判定順序刻意是「先否定、再肯定」**(與 `repositories/pool_repository.py::
    _is_missing_worksheet` 同一套,2026-09-06 #796 首次落地):
      1. **帶 HTTP 狀態碼、或是配額錯誤 → 直接 False**(委派 `infra.gspread_retry`,
         那是本 repo 這兩件事的 SSOT,不在這裡重寫一份)。
         這一道擋的是「訊息裡剛好出現 WorksheetNotFound 字樣的 APIError」。
      2. 其餘才看名字 / 訊息裡有沒有 `WorksheetNotFound`(duck-typed)。

    ⚠️ **為什麼 duck-type 而不 import `gspread.exceptions`**:容 gspread 版本差異,
    且 **CI 精簡環境根本沒裝 gspread**(那個環境裡 `http_status_of` 恆回 None,
    所以第 2 道的**肯定判定**才是主力)。沿用本 repo 既有慣例
    (`repositories/policy/_helpers.py::_is_worksheet_not_found`,v18.253)。

    ⚠️ **已知邊角(與 #796 逐字相同,不是漏抄)**:若某例外**同時**滿足
    「訊息裡剛好含 `WorksheetNotFound` 字樣」**且**「`http_status_of` 與
    `is_quota_error` 都不認得它」,本函式會回 `True`,那次讀失敗仍會被當成空狀態。
    真正會命中這個邊角的是**沒有 gspread 的環境**(CI 精簡環境、離線測試),
    而那裡本來就打不到 Google Sheets。**刻意不改行為**:要修它只能再收窄到
    「型別必須是 gspread 的」,那會讓沒有 gspread 的測試環境完全無法重現
    「分頁不存在」,等於用一個真實的損失去換一個構造不出來的情境。

    ⚠️ **SSOT 債,據實登記**:本函式是本 repo 這段判定的**第三份**
    (另兩份:`repositories/pool_repository.py::_is_missing_worksheet`、
    `repositories/policy/_helpers.py::_is_worksheet_not_found`)。
    正確的收斂位置是 `infra/gspread_retry.py`(HTTP 狀態碼與配額判定已經在那裡),
    但本批的檔案邊界只到本檔 + 測試,**不得**改 `infra/**` 或 `repositories/**`。
    收斂留給下一個動到 `infra/gspread_retry.py` 的人。
    """
    try:
        from infra.gspread_retry import http_status_of, is_quota_error
        if http_status_of(exc) is not None or is_quota_error(exc):
            return False
    except Exception:  # noqa: BLE001 — 偵測工具本身壞掉 → 不敢說「只是沒有分頁」
        return False   # §1:分不清就當作讀失敗(往上拋),不當作「沒有設定」
    return (type(exc).__name__.endswith("WorksheetNotFound")
            or "WorksheetNotFound" in str(exc))


def _gs_get_worksheet(*, for_write: bool = False):
    """取得 `_macro_weights` worksheet — 重用 policy_repository 的認證流程。

    ⚠️ **2026-09-07:本函式從「無條件確保分頁存在」改為「只有寫入路徑才建表」**
    (**有意識的政策變更,不是漏刪** · 決策者:**客戶** · 客戶 2026-09-06 永久授權:
    「凡是『查詢/搜尋』功能,一律強制走『純讀取(唯讀)』,絕對禁止反向寫入我的
    Google Sheet。不用問我,直接切斷寫入!」)。

    **舊寫法**(原文保留於下,加刪除線):
    ~~try: return sh.worksheet(_GS_WORKSHEET)~~
    ~~except Exception:~~
    ~~    ws = sh.add_worksheet(title=_GS_WORKSHEET, rows=3, cols=3)~~
    ~~    ws.update("A1:C3", [[...表頭...], ["", "", ""], ["active", "", ""]]); return ws~~

    **舊寫法的理由仍然成立**:把「分頁存在」這個不變式收在**唯一一處**,
    上層(`_gs_load` / `load_active`)就不必各自處理「還沒建」的情形 ——
    那是很正統的做法,一行都沒有寫錯。
    **被權衡掉的是它的副作用位置**:`load_active()` 這個名字叫「讀」、
    語意是純讀的函式,會經由本函式**改動使用者的試算表**;而觸發條件綁在
    **遠端狀態**(分頁不存在)、**不綁在使用者意圖** ——
    於是「還沒用過權重校準的人」,只要畫面上任何一處算過一次總經分數,
    就會被無聲建一張表,而且平常測不出來、log 也看不到。
    2026-09-07 實測:分頁不存在時,`load_active()` / `get_phase_thresholds()` /
    `get_verdict_cutoffs()` / `get_weight_override()` **每一個都會產生 2 筆寫入**
    (`add_worksheet` + `update`)。

    **現行**:`for_write=False`(預設,讀取路徑)—— 分頁不存在就回 `None`,
    **一格都不碰**。`for_write=True`(寫入路徑)—— 行為與舊寫法**逐字相同**,
    建表與寫表頭都還在,功能沒有消失。

    ⚠️ **本模組今日沒有 production 寫入端**(2026-09-07 AST 實測:全 repo 對
    `_macro_weights` 分頁的寫入呼叫只有本函式這 2 筆;active payload 由使用者
    **手動編輯**該分頁的 B3 儲存格 —— 見 module docstring 與 `ARCHITECTURE.md`
    「C-2 active override(可手動編輯)」)。**`for_write=True` 因此目前只有守衛
    測試會走到。** 保留它而不是整段刪除,是因為「刪掉建表能力」與「把建表移出讀
    路徑」是兩個不同的決定:後者是客戶明令,前者不是,而且會讓沒有分頁的使用者
    再也拿不到那張空白鷹架。**要不要刪,屬 §-1「沒有觸發不主動動工」。**

    回傳:worksheet;或 `None`(唯讀路徑**且**分頁尚不存在)。

    ⚠️ **`None` 只有一個意思:分頁真的還沒建 = 沒有 active override(合法空狀態)。**
    讀取失敗(403 未分享 / 429 配額 / 5xx / 連線中斷)**一律往上拋**,
    **不得**把它們併回 `None` —— 那會讓「讀不到你的校準」長得跟
    「你沒有設定校準」一模一樣,而下游會靜默套用硬編碼預設值(§1)。
    判定見 :func:`_is_missing_worksheet`。
    """
    # v19.197 P1-2:走 infra.config wrapper,本檔不再直 import streamlit
    from infra.config import require_secret
    from repositories.policy_repository import get_gspread_client

    # v19.430:傳 raw secret(str/dict 皆可,get_gspread_client 內部正規化);
    # 不再 dict() 預包(secret 為 JSON 字串時會在進 get_gspread_client 前拋 ValueError)。
    creds = require_secret("google_service_account")
    sheet_id = require_secret("macro_weights_sheet_id")
    client = get_gspread_client(creds)
    sh = client.open_by_key(sheet_id)
    try:
        return sh.worksheet(_GS_WORKSHEET)
    except Exception as _e_ws:
        if not for_write:
            # ── 唯讀路徑:零寫入 ──────────────────────────────────────────
            # ⛔ 這裡**刻意不是**裸 `except Exception: return None`:那會把
            #    403 / 429 / 5xx / 連線中斷一起壓成「沒有設定」,見上方 docstring。
            if not _is_missing_worksheet(_e_ws):
                raise
            import sys
            print(f"[weights_store] 唯讀路徑:`{_GS_WORKSHEET}` 分頁尚不存在 → "
                  f"視為沒有 active override(不建表,下游回退硬編碼)", file=sys.stderr)
            return None
        # 寫入路徑:行為與 2026-09-07 之前逐字相同(分頁不在就建 + 寫表頭)。
        # ⚠️ 這裡**刻意不加**上面那道分流:真的是 403/429 時 `add_worksheet` 自己就會拋,
        #    失敗照樣浮出來;在寫入路徑上多一道判斷只會改動一段沒有壞掉的行為。
        # v19.250 B:active-only schema(pending row2/row4 退役;舊 worksheet 4 列仍可被讀,只是 row2/4 被忽略)
        ws = sh.add_worksheet(title=_GS_WORKSHEET, rows=3, cols=3)
        ws.update("A1:C3", [
            ["slot", "payload_json", "updated_at"],
            ["", "", ""],
            ["active", "", ""],
        ])
        return ws


def _gs_load(slot: str) -> dict[str, Any] | None:
    """讀 slot row(目前只支援 active=row3)。空值 / 解析失敗 → None.

    ⚠️ 2026-09-07:`_gs_get_worksheet()` 走**唯讀**路徑,分頁不存在時回 `None`
    (合法空狀態);讀失敗會由它直接往上拋,**不會**走到這裡(§1)。
    ⛔ 不得在本函式補一層 `try/except → None`:那會把那道分流整個作廢。
    """
    row = _GS_SLOT_ROWS[slot]
    ws = _gs_get_worksheet()
    if ws is None:                      # 分頁還沒建 = 沒有 active override(不是讀失敗)
        return None
    cell = ws.acell(f"B{row}").value
    if not cell:
        return None
    try:
        data = json.loads(cell)
        _validate(data)
        return data
    except (json.JSONDecodeError, ValueError):
        return None


def _validate(payload: dict) -> None:
    """最小 schema 驗證 — 不通過直接 raise,避免靜默 corrupt。"""
    if not isinstance(payload, dict):
        raise ValueError("payload 必須是 dict")
    missing = _REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError(f"payload 缺必要欄位:{sorted(missing)}")
    if not isinstance(payload["indicators"], dict):
        raise ValueError("payload['indicators'] 必須是 dict")


def load_active() -> dict[str, Any]:
    """讀 active。GS 後端 → row3;FS 後端 → ``macro_weights_active.json``。
    不存在 / 解析失敗 → 回 _empty_active()。

    ⛔ **本函式保證零寫入**(2026-09-07)。名字是「讀」,行為就只有讀。
    分頁 / 檔案不存在是**合法的空狀態** → `_empty_active()` → 下游回退硬編碼;
    但**讀失敗**(403 / 429 / 5xx / 連線中斷)**往上拋**,不壓成「沒有設定」——
    否則使用者會以為自己的校準生效了,實際上總經評分正在用硬編碼預設值(§1)。
    """
    if _gs_enabled():
        data = _gs_load("active")
        return data if data is not None else _empty_active()
    if not _ACTIVE_PATH.exists():
        return _empty_active()
    try:
        data = json.loads(_ACTIVE_PATH.read_text(encoding="utf-8"))
        _validate(data)
        return data
    except (json.JSONDecodeError, ValueError):
        return _empty_active()


# ════════════════════════════════════════════════════════════════
# C-2:面板下游 override 注入器
# ════════════════════════════════════════════════════════════════
_DEFAULT_VERDICT_CUTOFFS: tuple[float, float, float, float] = (10.0, 5.0, -5.0, -10.0)
_DEFAULT_PHASE_THRESHOLDS: tuple[float, float, float] = (8.0, 5.0, 3.0)


def apply_weight_overrides(ind: dict | None) -> dict:
    """套用 active.json 對 indicator dict 的 weight override。

    - ``ind`` 為 {key: {"score": ..., "weight": ..., ...}, ...}
    - active.json.indicators[key].weight 存在 → 覆蓋;否則保留原值
    - active 為空 / corrupt / indicators={} → 回傳原 ind(no-op)
    - 不深拷貝 pandas Series(每個 indicator dict 只 shallow-copy 包一層)

    Returns:
        新 dict(不 mutate 輸入);若無 override 則直接 return ind 同物件
    """
    if not isinstance(ind, dict) or not ind:
        return ind if isinstance(ind, dict) else {}
    active = load_active()
    overrides = active.get("indicators") or {}
    if not overrides:
        return ind
    out: dict = {}
    for key, val in ind.items():
        if not isinstance(val, dict):
            out[key] = val
            continue
        ov = overrides.get(key)
        if not isinstance(ov, dict) or "weight" not in ov:
            out[key] = val
            continue
        try:
            new_w = float(ov["weight"])
        except (TypeError, ValueError):
            out[key] = val
            continue
        new_val = dict(val)
        new_val["weight"] = new_w
        out[key] = new_val
    return out


def get_weight_override(key: str, fallback: float) -> float:
    """單一 key 的 weight override 查詢(給 macro_score_calibration.compute_score_row 用).

    Returns:
        active.json.indicators[key].weight(若存在且為 float);否則 fallback。
    """
    active = load_active()
    overrides = active.get("indicators") or {}
    ov = overrides.get(key)
    if not isinstance(ov, dict) or "weight" not in ov:
        return fallback
    try:
        return float(ov["weight"])
    except (TypeError, ValueError):
        return fallback


def get_verdict_cutoffs(
    fallback: tuple[float, float, float, float] = _DEFAULT_VERDICT_CUTOFFS,
) -> tuple[float, float, float, float]:
    """讀 active.json.verdict_cutoffs(5 級分界 [極樂, 樂, 悲, 極悲],降序).

    格式:[c1, c2, c3, c4],要求 c1 > c2 > c3 > c4,否則回 fallback。
    JSON null / 缺欄 / 格式錯 → fallback。
    """
    active = load_active()
    raw = active.get("verdict_cutoffs")
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return fallback
    try:
        cuts = tuple(float(x) for x in raw)
    except (TypeError, ValueError):
        return fallback
    if not (cuts[0] > cuts[1] > cuts[2] > cuts[3]):
        return fallback
    return cuts  # type: ignore[return-value]


def get_phase_thresholds(
    fallback: tuple[float, float, float] = _DEFAULT_PHASE_THRESHOLDS,
) -> tuple[float, float, float]:
    """讀 active.json.phase_thresholds([peak, expansion, recovery] 降序).

    格式:[p, e, r],要求 p > e > r,否則回 fallback。
    """
    active = load_active()
    raw = active.get("phase_thresholds")
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        return fallback
    try:
        thr = tuple(float(x) for x in raw)
    except (TypeError, ValueError):
        return fallback
    if not (thr[0] > thr[1] > thr[2]):
        return fallback
    return thr  # type: ignore[return-value]


__all__ = [
    "load_active",
    "apply_weight_overrides",
    "get_weight_override",
    "get_verdict_cutoffs",
    "get_phase_thresholds",
]
