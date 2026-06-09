"""v19.37 services — 基金組合健診配息計算（純函式 / zero-IO）。

對 100 萬 TWD 為基準，模擬持有期間每次配息折算 TWD 金額並判定吃本金。

設計
----
- zero-IO 純函式，無 Streamlit / requests 依賴 → 可單測
- 預設「不再投入」(reinvest=False)：份額固定 = principal_ccy / buy_nav
- FX 歷史缺漏 → 用 fx_rate_default (spot) fallback，於回傳標 fx_source='spot'
- 自行計算欄位於回傳 dict 的 ``_self_calc_fields`` 列舉

對外 API
========
- ``compute_dividend_twd_series(...)`` 主算式
- ``div_health_light_for_pair(ret_pct, div_pct)`` 三色燈（對齊 fund_screener.div_health_light）
"""
from __future__ import annotations

from datetime import date
from typing import Any

DEFAULT_PRINCIPAL_TWD: float = 1_000_000.0
DEFAULT_WARN_GAP_PCT: float = 2.0

_LIGHT_EMOJI: dict[str, str] = {
    "健康": "🟢",
    "警示": "🟡",
    "吃本金": "🔴",
    "資料不足": "⚪",
}


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def div_health_light_for_pair(
    ret_pct: Any,
    div_pct: Any,
    warn_gap: float = DEFAULT_WARN_GAP_PCT,
) -> tuple[str, str]:
    """三色燈 — 規則對齊 services.fund_screener.div_health_light。

    - 任一 None / NaN → ('資料不足', '⚪')
    - div_pct ≤ 0 → ('健康', '🟢')
    - ret_pct ≥ div_pct → ('健康', '🟢')
    - gap = div_pct - ret_pct ∈ (0, warn_gap] → ('警示', '🟡')
    - gap > warn_gap → ('吃本金', '🔴')
    """
    r = _safe_float(ret_pct)
    d = _safe_float(div_pct)
    if r is None or d is None:
        return ("資料不足", _LIGHT_EMOJI["資料不足"])
    if d <= 0:
        return ("健康", _LIGHT_EMOJI["健康"])
    gap = d - r
    if gap <= 0:
        return ("健康", _LIGHT_EMOJI["健康"])
    if gap <= warn_gap:
        return ("警示", _LIGHT_EMOJI["警示"])
    return ("吃本金", _LIGHT_EMOJI["吃本金"])


def _years_between(start_iso: str, end_iso: str) -> float:
    try:
        sy, sm, sd = int(start_iso[:4]), int(start_iso[5:7]), int(start_iso[8:10])
        ey, em, ed = int(end_iso[:4]), int(end_iso[5:7]), int(end_iso[8:10])
        delta = (date(ey, em, ed) - date(sy, sm, sd)).days
    except (ValueError, TypeError):
        return 0.0
    return max(delta / 365.25, 0.0)


def _pick_fx_for_date(
    date_iso: str,
    fx_by_date: dict | None,
    fx_default: float,
) -> tuple[float, str]:
    if fx_by_date and date_iso in fx_by_date:
        v = _safe_float(fx_by_date[date_iso])
        if v is not None and v > 0:
            return v, "historical"
    return fx_default, "spot"


def _resolve_nav_at_or_before(date_iso: str, nav_by_date: dict, buy_nav: float) -> float:
    if date_iso in nav_by_date:
        return nav_by_date[date_iso]
    below = [d for d in nav_by_date if d <= date_iso]
    return nav_by_date[max(below)] if below else buy_nav


def compute_dividend_twd_series(
    nav_series: dict,
    dividend_events: list,
    fx_rate_default: Any,
    fx_rate_by_date: dict | None = None,
    principal_twd: Any = DEFAULT_PRINCIPAL_TWD,
    reinvest: bool = False,
    warn_gap_pct: float = DEFAULT_WARN_GAP_PCT,
) -> dict:
    """主算式：以 N 元 TWD 為基準，逐次配息折算 TWD 金額 + 吃本金判定。

    Args:
        nav_series: ``{date_iso: NAV(原幣)}`` —— 至少含買進日 / 末日
        dividend_events: ``[{date, amount, yield_pct?}]`` amount = 配息(原幣)/單位
        fx_rate_default: spot CCY→TWD（1 單位原幣 = N TWD）
        fx_rate_by_date: ``{date_iso: ccy_to_twd}`` 歷史 FX；缺則 fallback default
        principal_twd: 投資本金 TWD（預設 100 萬）
        reinvest: True = 配息再投入（v19.37 暫不實作，預設 False）
        warn_gap_pct: 配息率超出含息報酬率多少 → 警示燈

    Returns:
        dict:
            ok: bool
            error: str (僅 ok=False 時)
            principal_twd / principal_ccy 🧮 / buy_date / buy_nav / buy_fx / buy_fx_source
            units_held 🧮
            n_events
            events: list[dict] —— 每筆配息明細（多數欄位 🧮）
            summary: dict —— 累積年化、吃本金判定（均 🧮）
            _self_calc_fields: list[str] —— 自行計算欄位清單（UI 加 🧮 icon 用）
    """
    p_twd = _safe_float(principal_twd) or 0.0
    fx_def = _safe_float(fx_rate_default) or 0.0
    if p_twd <= 0:
        return {"ok": False, "error": "principal_twd 必須 > 0", "events": []}
    if fx_def <= 0:
        return {"ok": False, "error": "fx_rate_default 必須 > 0", "events": []}
    if not isinstance(nav_series, dict) or not nav_series:
        return {"ok": False, "error": "nav_series 為空", "events": []}

    nav_items = sorted(
        (d, _safe_float(v)) for d, v in nav_series.items()
        if isinstance(d, str) and _safe_float(v) is not None and _safe_float(v) > 0
    )
    if not nav_items:
        return {"ok": False, "error": "nav_series 無有效 NAV", "events": []}

    buy_date, buy_nav = nav_items[0]
    last_date, last_nav = nav_items[-1]
    buy_fx, buy_fx_src = _pick_fx_for_date(buy_date, fx_rate_by_date, fx_def)

    # 100 萬 TWD → 原幣本金 → 持有單位（reinvest=False 全程固定）
    principal_ccy = p_twd / buy_fx
    units_held = principal_ccy / buy_nav

    nav_by_date = {d: v for d, v in nav_items}

    sorted_divs = sorted(
        (e for e in (dividend_events or []) if isinstance(e, dict)),
        key=lambda e: str(e.get("date") or "")
    )

    events_out: list[dict] = []
    total_ccy_div = 0.0
    total_twd_div = 0.0
    cumulative_units = units_held  # reinvest=True 時可成長，v19.37 鎖死

    for ev in sorted_divs:
        ex_date = str(ev.get("date") or "")[:10]
        if not ex_date or ex_date < buy_date:
            continue
        amt = _safe_float(ev.get("amount"))
        if amt is None or amt <= 0:
            continue

        nav_at_ex = _resolve_nav_at_or_before(ex_date, nav_by_date, buy_nav)
        fx_at_ex, fx_src = _pick_fx_for_date(ex_date, fx_rate_by_date, fx_def)

        ccy_div_total = amt * cumulative_units
        twd_div = ccy_div_total * fx_at_ex
        single_div_pct = (amt / nav_at_ex) * 100.0 if nav_at_ex > 0 else 0.0

        events_out.append({
            "ex_date": ex_date,
            "ccy_div_per_unit": round(amt, 4),
            "units_at_event_🧮": round(cumulative_units, 4),
            "ccy_div_total_🧮": round(ccy_div_total, 2),
            "fx_at_ex": round(fx_at_ex, 4),
            "fx_source": fx_src,
            "twd_div_🧮": round(twd_div, 0),
            "nav_at_ex": nav_at_ex,
            "single_event_div_pct_🧮": round(single_div_pct, 3),
        })
        total_ccy_div += ccy_div_total
        total_twd_div += twd_div

        if reinvest and nav_at_ex > 0:
            # v19.37 預設 False；reinvest=True 路徑保留簽名相容
            cumulative_units += ccy_div_total / nav_at_ex

    years = _years_between(buy_date, last_date)
    safe_years = years if years > 0 else 1.0
    nav_return_pct = ((last_nav - buy_nav) / buy_nav) * 100.0 if buy_nav > 0 else 0.0
    annual_nav_return_pct = nav_return_pct / safe_years
    annual_div_rate_pct = (
        (total_ccy_div / principal_ccy / safe_years) * 100.0
        if principal_ccy > 0 else 0.0
    )
    ret_1y_total_pct = annual_nav_return_pct + annual_div_rate_pct

    light, light_emoji = div_health_light_for_pair(
        ret_1y_total_pct, annual_div_rate_pct, warn_gap=warn_gap_pct
    )

    return {
        "ok": True,
        "principal_twd": p_twd,
        "principal_ccy_🧮": round(principal_ccy, 2),
        "buy_date": buy_date,
        "buy_nav": buy_nav,
        "buy_fx": round(buy_fx, 4),
        "buy_fx_source": buy_fx_src,
        "units_held_🧮": round(units_held, 4),
        "n_events": len(events_out),
        "events": events_out,
        "summary": {
            "total_ccy_div_🧮": round(total_ccy_div, 2),
            "total_twd_div_🧮": round(total_twd_div, 0),
            "last_date": last_date,
            "last_nav": last_nav,
            "holding_years_🧮": round(years, 2),
            "nav_return_pct_🧮": round(nav_return_pct, 2),
            "annual_nav_return_pct_🧮": round(annual_nav_return_pct, 2),
            "annual_div_rate_pct_🧮": round(annual_div_rate_pct, 2),
            "ret_1y_total_pct_🧮": round(ret_1y_total_pct, 2),
            "div_health_light_🧮": light,
            "div_health_emoji_🧮": light_emoji,
        },
        "_self_calc_fields": [
            "principal_ccy", "units_held",
            "events[].units_at_event", "events[].ccy_div_total",
            "events[].twd_div", "events[].single_event_div_pct",
            "summary.total_ccy_div", "summary.total_twd_div",
            "summary.holding_years", "summary.nav_return_pct",
            "summary.annual_nav_return_pct", "summary.annual_div_rate_pct",
            "summary.ret_1y_total_pct", "summary.div_health_light",
        ],
    }
