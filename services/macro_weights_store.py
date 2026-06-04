"""services/macro_weights_store.py — Route C-1/C-2：總經權重 JSON 儲存層 + 注入器

雙檔設計：
- ``config/macro_weights_active.json`` — 面板實際載入的權重（C-2 接管後生效）
- ``config/macro_weights_pending.json`` — 回測室「提交為待審權重」寫入，user 在面板批准才升格 active

C-1：純 I/O + schema 驗證。
C-2：3 個 override helper（apply_weight_overrides / get_verdict_cutoffs / get_phase_thresholds）
     讓面板下游函式從 active.json 注入 weight、verdict 五級分界、phase 三段門檻；
     active.json 為空 / corrupt / 欄位 null → 全部回退至呼叫端原本硬編碼，**零回歸**。

公開 API：
- load_active() -> dict
- load_pending() -> dict | None
- save_pending(weights, metadata) -> Path
- approve_pending() -> bool
- reject_pending() -> bool
- has_pending() -> bool
- build_payload_from_multifactor(opt, wf, sel_keys, metric, ai_explanation) -> dict
- apply_weight_overrides(ind) -> dict                                              (C-2)
- get_verdict_cutoffs(fallback=...) -> tuple[float, float, float, float]           (C-2)
- get_phase_thresholds(fallback=...) -> tuple[float, float, float]                 (C-2)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_ACTIVE_PATH = _CONFIG_DIR / "macro_weights_active.json"
_PENDING_PATH = _CONFIG_DIR / "macro_weights_pending.json"

_SCHEMA_VERSION = "v19.0"
_REQUIRED_KEYS = {"version", "indicators"}


def _empty_active() -> dict[str, Any]:
    """fallback active payload — C-2 之前面板回退硬編碼，這份是占位用。"""
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


def _validate(payload: dict) -> None:
    """最小 schema 驗證 — 不通過直接 raise，避免靜默 corrupt。"""
    if not isinstance(payload, dict):
        raise ValueError("payload 必須是 dict")
    missing = _REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError(f"payload 缺必要欄位：{sorted(missing)}")
    if not isinstance(payload["indicators"], dict):
        raise ValueError("payload['indicators'] 必須是 dict")


def load_active() -> dict[str, Any]:
    """讀 active 檔。不存在 / 解析失敗 → 回 _empty_active()。"""
    if not _ACTIVE_PATH.exists():
        return _empty_active()
    try:
        data = json.loads(_ACTIVE_PATH.read_text(encoding="utf-8"))
        _validate(data)
        return data
    except (json.JSONDecodeError, ValueError):
        return _empty_active()


def load_pending() -> dict[str, Any] | None:
    """讀 pending 檔。不存在 → None。解析失敗 → None（避免 corrupt 卡死面板）。"""
    if not _PENDING_PATH.exists():
        return None
    try:
        data = json.loads(_PENDING_PATH.read_text(encoding="utf-8"))
        _validate(data)
        return data
    except (json.JSONDecodeError, ValueError):
        return None


def has_pending() -> bool:
    """快速檢查 pending 是否存在（面板 banner 用，不解析內容）。"""
    return _PENDING_PATH.exists()


def save_pending(payload: dict[str, Any]) -> Path:
    """寫 pending 檔。覆蓋舊 pending（單槽設計，新提交吃掉舊提交）。

    Raises:
        ValueError: payload schema 不合法
    """
    _validate(payload)
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _PENDING_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return _PENDING_PATH


def approve_pending() -> bool:
    """升格 pending → active：覆蓋 active 檔，刪除 pending 檔。

    Returns:
        True 若有 pending 且成功升格；False 若無 pending。
    """
    if not _PENDING_PATH.exists():
        return False
    try:
        payload = json.loads(_PENDING_PATH.read_text(encoding="utf-8"))
        _validate(payload)
    except (json.JSONDecodeError, ValueError):
        return False
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ACTIVE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _PENDING_PATH.unlink(missing_ok=True)
    return True


def reject_pending() -> bool:
    """刪除 pending 檔。Returns True 若有檔可刪。"""
    if not _PENDING_PATH.exists():
        return False
    _PENDING_PATH.unlink(missing_ok=True)
    return True


def build_payload_from_multifactor(
    opt: dict,
    wf: dict,
    sel_keys: list[str],
    metric: str,
    ai_explanation: str | None = None,
    horizon_months: int = 3,
    drawdown_threshold: float = -0.10,
) -> dict[str, Any]:
    """把回測室 ``_multifactor_result`` 結果整理成 pending payload schema。

    Args:
        opt: ``find_plateau_optimum`` 回傳值（含 weights / f1 / sharpe / plateau_score）
        wf: ``walk_forward_validate`` 回傳值（含 oos_f1 / oos_sharpe / n_folds / folds）
        sel_keys: 本次回測用的因子 key list
        metric: 'f1' / 'sharpe'
        ai_explanation: AI 對權重的白話解讀（可為 None）
        horizon_months: 真值定義（forward window 月數）
        drawdown_threshold: 真值定義（跌幅門檻）

    Returns:
        dict 符合 _SCHEMA_VERSION schema，可直接餵 save_pending。
    """
    indicators_payload = {}
    weights = (opt or {}).get("weights") or {}
    for k in sel_keys:
        indicators_payload[k] = {
            "weight": float(weights.get(k, 0.0)),
            "source": "route_c_multifactor",
        }
    return {
        "version": _SCHEMA_VERSION,
        "calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "calibration_method": f"multi_factor_plateau_{metric}",
        "horizon_months": int(horizon_months),
        "drawdown_threshold": float(drawdown_threshold),
        "indicators": indicators_payload,
        "verdict_cutoffs": None,
        "phase_thresholds": None,
        "oos_metrics": {
            "train_f1": float((opt or {}).get("f1", 0.0)),
            "train_sharpe": float((opt or {}).get("sharpe", 0.0)),
            "plateau_score": float((opt or {}).get("plateau_score", 0.0)),
            "oos_f1": float((wf or {}).get("oos_f1", 0.0)),
            "oos_sharpe": float((wf or {}).get("oos_sharpe", 0.0)),
            "n_folds": int((wf or {}).get("n_folds", 0)),
        },
        "ai_explanation": ai_explanation,
        "notes": (
            f"由危機回測室 Phase 3 多因子最佳化提交；"
            f"sel_keys={sel_keys}；metric={metric}。"
        ),
    }


# ════════════════════════════════════════════════════════════════
# C-2：面板下游 override 注入器
# ════════════════════════════════════════════════════════════════
_DEFAULT_VERDICT_CUTOFFS: tuple[float, float, float, float] = (10.0, 5.0, -5.0, -10.0)
_DEFAULT_PHASE_THRESHOLDS: tuple[float, float, float] = (8.0, 5.0, 3.0)


def apply_weight_overrides(ind: dict | None) -> dict:
    """套用 active.json 對 indicator dict 的 weight override。

    - ``ind`` 為 {key: {"score": ..., "weight": ..., ...}, ...}
    - active.json.indicators[key].weight 存在 → 覆蓋；否則保留原值
    - active 為空 / corrupt / indicators={} → 回傳原 ind（no-op）
    - 不深拷貝 pandas Series（每個 indicator dict 只 shallow-copy 包一層）

    Returns:
        新 dict（不 mutate 輸入）；若無 override 則直接 return ind 同物件
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
    """單一 key 的 weight override 查詢（給 macro_score_calibration.compute_score_row 用）.

    Returns:
        active.json.indicators[key].weight（若存在且為 float）；否則 fallback。
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
    """讀 active.json.verdict_cutoffs（5 級分界 [極樂, 樂, 悲, 極悲]，降序）.

    格式：[c1, c2, c3, c4]，要求 c1 > c2 > c3 > c4，否則回 fallback。
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
    """讀 active.json.phase_thresholds（[peak, expansion, recovery] 降序）.

    格式：[p, e, r]，要求 p > e > r，否則回 fallback。
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
    "load_pending",
    "has_pending",
    "save_pending",
    "approve_pending",
    "reject_pending",
    "build_payload_from_multifactor",
    "apply_weight_overrides",
    "get_weight_override",
    "get_verdict_cutoffs",
    "get_phase_thresholds",
]
