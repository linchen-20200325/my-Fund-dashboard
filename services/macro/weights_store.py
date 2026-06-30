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


def _gs_get_worksheet():
    """開啟(或自動建立)`_macro_weights` worksheet — 重用 policy_repository 的認證流程."""
    # v19.197 P1-2:走 infra.config wrapper,本檔不再直 import streamlit
    from infra.config import require_secret
    from repositories.policy_repository import get_gspread_client

    creds = dict(require_secret("google_service_account"))
    sheet_id = require_secret("macro_weights_sheet_id")
    client = get_gspread_client(creds)
    sh = client.open_by_key(sheet_id)
    try:
        return sh.worksheet(_GS_WORKSHEET)
    except Exception:
        # v19.250 B:active-only schema(pending row2/row4 退役;舊 worksheet 4 列仍可被讀,只是 row2/4 被忽略)
        ws = sh.add_worksheet(title=_GS_WORKSHEET, rows=3, cols=3)
        ws.update("A1:C3", [
            ["slot", "payload_json", "updated_at"],
            ["", "", ""],
            ["active", "", ""],
        ])
        return ws


def _gs_load(slot: str) -> dict[str, Any] | None:
    """讀 slot row(目前只支援 active=row3)。空值 / 解析失敗 → None."""
    row = _GS_SLOT_ROWS[slot]
    ws = _gs_get_worksheet()
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
