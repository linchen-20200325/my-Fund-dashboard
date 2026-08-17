"""services/switch_state_machine.py — L2 深度強化③:Switch Advisor 輕量狀態機閉環(純邏輯)。

標的在換股流程的生命週期:
    WATCHING(觀察)→ TRIGGERED(訊號觸發)→ HOLDING(買進持有)→ CLOSED(出場/換掉)
狀態存於 Google Sheet `_fund_pool` 的 `status` 欄(見 `PoolEntry.status`,additive、向後相容)。
本模組為**純轉移邏輯 + 轉換後績效追蹤(Alpha / 勝率)**,零 IO;實際讀寫走 L1 pool_repository。

閉環目的:記錄「當初建議換股」執行後的**超額報酬(Alpha)與勝率**,回頭校準顧問。
Fail-Loud(§1):非法轉移不靜默改狀態(回 valid=False);基準/淨值缺 → Alpha=None 不硬算。
"""
from __future__ import annotations

from typing import Optional

STATES: tuple = ("WATCHING", "TRIGGERED", "HOLDING", "CLOSED")

# (from_state, signal) → to_state。signal 為語意動作,不是 UI 事件。
_TRANSITIONS: dict = {
    ("WATCHING", "trigger"): "TRIGGERED",     # 顧問訊號觸發(換股建議成立)
    ("TRIGGERED", "execute"): "HOLDING",      # 使用者實際買進
    ("TRIGGERED", "cancel"): "WATCHING",      # 訊號消失 / 放棄 → 退回觀察
    ("HOLDING", "close"): "CLOSED",           # 賣出 / 被換掉
    ("HOLDING", "hold"): "HOLDING",           # 續抱(no-op,合法)
    ("CLOSED", "rewatch"): "WATCHING",        # 重新納入觀察
}


def normalize_status(raw) -> str:
    """任意輸入 → 合法狀態;空 / 未知 → 'WATCHING'(池中預設)。"""
    _s = str(raw or "").strip().upper()
    return _s if _s in STATES else "WATCHING"


def next_status(current, signal: str) -> dict:
    """(現狀, 訊號)→ {status, changed, valid, reason}。

    非法轉移 → valid=False + status 維持現狀(§1 不亂跳);合法 no-op(hold)→ changed=False。
    """
    _cur = normalize_status(current)
    _sig = str(signal or "").strip().lower()
    _to = _TRANSITIONS.get((_cur, _sig))
    if _to is None:
        return {"status": _cur, "changed": False, "valid": False,
                "reason": f"非法轉移:{_cur} + '{_sig}'(合法訊號見 _TRANSITIONS)。"}
    return {"status": _to, "changed": (_to != _cur), "valid": True,
            "reason": f"{_cur} --{_sig}--> {_to}"}


def transition_result(entry_nav: Optional[float], exit_nav: Optional[float],
                      benchmark_entry: Optional[float] = None,
                      benchmark_exit: Optional[float] = None) -> dict:
    """一次 WATCHING→…→CLOSED 週期的績效:{fund_return_pct, benchmark_return_pct, alpha_pct, win}。

    Alpha = 基金期間報酬 − 對應大盤期間報酬(百分點,§4.1);缺基準 → alpha=None、win=None(§1)。
    起點淨值 ≤ 0 → 全 None(§4.4 不除零)。
    """
    def _ret(_a, _b):
        try:
            _a, _b = float(_a), float(_b)
        except (TypeError, ValueError):
            return None
        return (_b / _a - 1.0) * 100.0 if _a > 0 else None

    _fr = _ret(entry_nav, exit_nav)
    _br = _ret(benchmark_entry, benchmark_exit)
    _alpha = round(_fr - _br, 2) if (_fr is not None and _br is not None) else None
    return {
        "fund_return_pct": round(_fr, 2) if _fr is not None else None,
        "benchmark_return_pct": round(_br, 2) if _br is not None else None,
        "alpha_pct": _alpha,
        "win": (bool(_alpha > 0) if _alpha is not None else None),
    }


def aggregate_winrate(results: list) -> dict:
    """多筆 transition_result → {n, n_scored, wins, winrate, avg_alpha_pct}。

    只統計有 alpha 的筆數(缺基準的不灌水勝率,§1);n_scored=0 → winrate/avg=None。
    """
    _scored = [r for r in (results or []) if r and r.get("alpha_pct") is not None]
    _n_scored = len(_scored)
    if _n_scored == 0:
        return {"n": len(results or []), "n_scored": 0, "wins": 0,
                "winrate": None, "avg_alpha_pct": None}
    _wins = sum(1 for r in _scored if r.get("win"))
    _avg = sum(float(r["alpha_pct"]) for r in _scored) / _n_scored
    return {"n": len(results or []), "n_scored": _n_scored, "wins": _wins,
            "winrate": round(_wins / _n_scored, 3), "avg_alpha_pct": round(_avg, 2)}


__all__ = ["STATES", "normalize_status", "next_status",
           "transition_result", "aggregate_winrate"]
