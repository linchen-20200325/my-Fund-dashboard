"""v19.181 services — 「是否建議換標的」MK 4 規則心型警結合 SSOT 入口(L2 純函式,zero-IO)。

依郭俊宏(MK)老師長線挑核心資產體檢方法論,定義 4 條 hard-trigger 規則:
  (a) 吃本金 1Y·MK 且持有 ≥ 1 年
  (b) 4D Grade F(< 35 分,嚴重警示)
  (c) 3-3-3 未通過且持有 ≥ 3 年
  (d) Sharpe < 0 且 max_dd < -30%(極差雙條件)

Verdict 三色:
  - 任一 hard trigger 中  → 🔴 建議換(replace)
  - 1-2 觀察分(Grade D 等較弱訊號) → 🟡 觀察(observe)
  - 全部未中             → 🟢 保留(keep)

設計
----
- zero-IO 純函式,只接受已算好的 fd dict + holding_years,無 streamlit 依賴
- 所有規則門檻走 shared.signal_thresholds SSOT,禁止 inline magic
- caller 端負責:(1) 算 holding_years(2) 拿 fd_dict(含 metrics, moneydj_raw 等)

對外 API
========
- ``check_replacement_recommendation(fd, holding_years, _4d_result=None)`` 主入口
"""
from __future__ import annotations

from typing import Optional

from shared.signal_thresholds import (
    REPLACE_RULE_A_MIN_HOLD_YEARS,
    REPLACE_RULE_C_MIN_HOLD_YEARS,
    REPLACE_RULE_D_SHARPE_MAX,
    REPLACE_RULE_D_MAX_DD_MIN_PCT,
)

_VERDICT_EMOJI = {
    "replace": "🔴",
    "observe": "🟡",
    "keep": "🟢",
    "unknown": "⬜",
}

_VERDICT_LABEL = {
    "replace": "建議換",
    "observe": "觀察",
    "keep": "保留",
    "unknown": "資料不足",
}


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def check_replacement_recommendation(
    fd: dict,
    holding_years: Optional[float] = None,
    _4d_result: Optional[dict] = None,
) -> dict:
    """換標的建議 SSOT 入口 — MK 4 規則心型警結合。

    Args:
        fd: 基金 dict(支援 Tab2/Tab3/健診 3 種 shape):
            - 平坦:`{metrics, moneydj_raw, series, perf_source, ...}`
            - 嵌套:`{moneydj_raw: {perf, metrics, ...}}`
        holding_years: user 持有年數(從 portfolio_funds.invest_date 或 NAV 序列首日推算)。
            None → rule (a)(c) 自動退 unknown(不下硬判定)。
        _4d_result: 預算好的 compute_4d_health() 結果(免重算)。None → 本函式呼叫。

    Returns:
        {
            "verdict": "replace" | "observe" | "keep" | "unknown",
            "emoji": str,
            "label": str,
            "triggered_rules": [str, ...],  # 中的 hard trigger 規則名
            "observe_signals": [str, ...],  # 較弱訊號(觀察分)
            "message": str,                  # 給 UI 顯示的人類可讀說明
        }
    """
    # 規則延遲 import 避免循環依賴
    from services.fund_dividend_health import (
        check_333_principle,
        check_eating_principal_1y_mk,
    )
    from services.fund_health import compute_4d_health
    from services.fund_total_return import compute_1y_total_return

    # ─── shape normalize:平坦 fd 自動 wrap(對齊 v19.178 SSOT 模式)──
    if "moneydj_raw" not in fd and "perf" in fd:
        fd = {
            "moneydj_raw": fd,
            "metrics": fd.get("metrics") or {},
            "series": fd.get("series"),
            "perf_source": fd.get("perf_source"),
        }
    m = fd.get("metrics") or {}
    mj = fd.get("moneydj_raw") or {}

    triggered: list = []
    observe: list = []

    # ─── 規則 (a) — 吃本金 1Y·MK 且持有 ≥ 1 年 ───────────────
    holding_y = _safe_float(holding_years)
    rule_a_eligible = (holding_y is not None
                       and holding_y >= REPLACE_RULE_A_MIN_HOLD_YEARS)
    try:
        eat_result = check_eating_principal_1y_mk(fd)
    except Exception:
        eat_result = None
    eat_status = (eat_result or {}).get("status", "")
    if rule_a_eligible and "吃本金" in str(eat_status):
        triggered.append(f"(a) 持有 {holding_y:.1f} 年 + 吃本金 1Y·MK")
    elif eat_result and "吃本金" in str(eat_status):
        # 持有 < 1 年也吃本金 — 計觀察分(尚未到 hard trigger)
        observe.append(f"(a*) 持有 < 1 年但吃本金(短期 NAV 波動,先觀察)")

    # ─── 規則 (b) — 4D Grade F(嚴重警示)/ D 計觀察分 ─────────
    if _4d_result is None:
        try:
            tr1y, _ = compute_1y_total_return(fd)
            adr = (eat_result or {}).get("annual_div_rate_pct")
            _4d_result = compute_4d_health(
                tr1y_pct=tr1y,
                adr_pct=adr,
                sharpe=_safe_float(m.get("sharpe")),
                sigma_pct=_safe_float(m.get("std_1y")),
                ma_dir=None,
            )
        except Exception:
            _4d_result = None
    grade = (_4d_result or {}).get("grade")
    if grade == "F":
        triggered.append("(b) 4D Grade F(健康度嚴重不足)")
    elif grade == "D":
        observe.append("(b*) 4D Grade D(健康度偏弱)")

    # ─── 規則 (c) — 3-3-3 未通過且持有 ≥ 3 年 ────────────────
    rule_c_eligible = (holding_y is not None
                       and holding_y >= REPLACE_RULE_C_MIN_HOLD_YEARS)
    _ret_3y_ann = _safe_float(m.get("ret_3y_ann"))
    if _ret_3y_ann is None:
        # 舊 schema fallback:metrics.ret_3y_cum → 開根
        _cum = _safe_float(m.get("ret_3y_cum") or m.get("ret_3y"))
        if _cum is not None:
            _ret_3y_ann = ((1.0 + _cum / 100.0) ** (1.0 / 3.0) - 1.0) * 100.0
    try:
        _333 = check_333_principle(holding_y, _ret_3y_ann)
    except Exception:
        _333 = {}
    if rule_c_eligible and _333.get("passed") is False:
        triggered.append(f"(c) 持有 {holding_y:.1f} 年 + 3-3-3 未通過")
    # v19.181:不再為持有 < 3 年的「3-3-3 未過」開觀察分 —
    # 新基金本來就過不了 3-3-3(成立年數不足),非真警示;
    # 避免每檔新基金都跳 🟡 觀察。

    # ─── 規則 (d) — Sharpe < 0 且 max_dd < -30% ──────────────
    sharpe_v = _safe_float(m.get("sharpe"))
    max_dd_v = _safe_float(m.get("max_drawdown"))
    if (sharpe_v is not None and sharpe_v < REPLACE_RULE_D_SHARPE_MAX
            and max_dd_v is not None and max_dd_v < REPLACE_RULE_D_MAX_DD_MIN_PCT):
        triggered.append(
            f"(d) Sharpe {sharpe_v:.2f} < 0 且 max_dd {max_dd_v:.1f}% < "
            f"{REPLACE_RULE_D_MAX_DD_MIN_PCT}%"
        )
    elif sharpe_v is not None and sharpe_v < REPLACE_RULE_D_SHARPE_MAX:
        observe.append(f"(d*) Sharpe {sharpe_v:.2f} < 0(風險調整後無報酬)")

    # ─── 綜合 verdict ────────────────────────────────────────
    # unknown 判定:所有關鍵指標都拿不到時不下 verdict(避免假綠燈)
    _has_any_signal = (
        eat_status or grade not in (None, "—")
        or sharpe_v is not None or max_dd_v is not None
        or _ret_3y_ann is not None
    )
    if triggered:
        verdict = "replace"
    elif observe:
        verdict = "observe"
    elif not _has_any_signal:
        verdict = "unknown"
    else:
        verdict = "keep"

    # ─── 人類可讀訊息 ──────────────────────────────────────────
    if verdict == "replace":
        msg = f"🔴 建議換 — 中 {len(triggered)} 條 hard trigger:" + " / ".join(triggered)
    elif verdict == "observe":
        msg = f"🟡 觀察 — {len(observe)} 個警示訊號:" + " / ".join(observe)
    elif verdict == "keep":
        msg = "🟢 保留 — MK 4 規則全未中,持續持有"
    else:
        msg = "⬜ 資料不足 — 無法判定(持有期或關鍵指標缺)"

    return {
        "verdict": verdict,
        "emoji": _VERDICT_EMOJI[verdict],
        "label": _VERDICT_LABEL[verdict],
        "triggered_rules": triggered,
        "observe_signals": observe,
        "message": msg,
    }
