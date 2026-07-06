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
from typing import Any, Optional

from shared.signal_thresholds import (  # v19.74 W2 SSOT
    MIN_YEARS_FOR_ANNUALIZE,  # v19.175 短歷史 guard
    NEAR_DIVIDEND_WARNING_PCT,
)

DEFAULT_PRINCIPAL_TWD: float = 1_000_000.0
DEFAULT_WARN_GAP_PCT: float = NEAR_DIVIDEND_WARNING_PCT

_LIGHT_EMOJI: dict[str, str] = {
    "健康": "🟢",
    "警示": "🟡",
    "吃本金": "🔴",
    "資料不足": "⚪",
    "歷史不足": "⬜",  # v19.175 — 持有 < 0.5 年無法年化
}


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402



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

    v19.119:核心判定委派 services.health.dividend.classify_eating_principal
    (output tuple 100% 向後相容,3 色燈門檻 gap vs warn_gap 保留於本 wrapper)。
    """
    from services.health.dividend import classify_eating_principal
    core = classify_eating_principal(ret_pct, div_pct)
    if core.is_data_missing:
        return ("資料不足", _LIGHT_EMOJI["資料不足"])
    if core.is_no_dividend:
        return ("健康", _LIGHT_EMOJI["健康"])
    # core.gap_pct = div - ret(資料齊全且 div > 0 時必非 None)
    gap = core.gap_pct
    if gap <= 0:
        return ("健康", _LIGHT_EMOJI["健康"])
    if gap <= warn_gap:
        return ("警示", _LIGHT_EMOJI["警示"])
    return ("吃本金", _LIGHT_EMOJI["吃本金"])


def latest_dividend_per_unit(dividends: Any) -> Optional[float]:
    """從 dividends[] 取「最近一筆」真實配息額(原幣 / 單位)SSOT。

    dividends[] 為 MoneyDJ wh06 / TDCC 真實每筆配息記錄:
    ``[{date|ex_date, amount, ...}]``,amount = 每單位實際配息(原幣)。
    月配息基金 = 一個月一筆 → 最新一筆即「這個月」實配。

    取法:依 date(缺則 ex_date)ISO 日期字串**降序**取第一筆 amount > 0。
    日期正規化 `/`→`-` 避免混格式誤排序。

    Returns:
        最近一筆配息(原幣 / 單位)float,或 None(無記錄 / 全 ≤ 0 → §1 顯式 None,不估算)
    """
    if not dividends:
        return None
    best_date = ""
    best_amt: Optional[float] = None
    for d in dividends:
        if not isinstance(d, dict):
            continue
        ds = str(d.get("date") or d.get("ex_date") or "")[:10].replace("/", "-")
        amt = _safe_float(d.get("amount"))
        if amt is None:
            amt = _safe_float(d.get("div_per_unit"))
        if amt is None or amt <= 0 or not ds:
            continue
        if ds >= best_date:  # ISO 字串比較,保留最新日期
            best_date, best_amt = ds, amt
    return best_amt


def monthly_dividend_from_records(
    dividends: Any,
    units_held: Any,
    nav: Any,
    fx: Any = 1.0,
    adr_pct: Any = None,
) -> dict:
    """算每月配息(原幣 / TWD / 可再投入單位數)SSOT — 真實記錄優先,年化估算 fallback。

    全站(單一基金 Tab2 / 組合基金 Tab3 / 基金健檢 ② 表)月配息 / 配息單位數一律
    走本函式,確保跨頁同源(§2.1 SSOT)+ 帶 `source` 供 UI 註記來源。

    **兩層取數**(每筆都回傳 `source` 標記,§2.2 血緣):
      1. **真實記錄**(source="records"):最近一筆實配 d = latest_dividend_per_unit(dividends)
         每月配息(原幣) = d × 持有單位;每月配息單位數 = 每月配息(原幣) / nav
      2. **年化估算 fallback**(source="estimate"):無真實逐筆記錄但有年化配息率時,
         原幣本金 = 持有單位 × nav;每月配息(原幣) = 原幣本金 × adr% / 100 / 12
         (= 年化配息 ÷ 12 攤平至每月;季配 / 年配基金為平均值非實配,故標 estimate)
    共通:每月配息(TWD) = 每月配息(原幣) × fx。

    Args:
        dividends: 真實配息記錄 list(見 latest_dividend_per_unit)
        units_held: 持有單位數(caller 算:原幣本金 / nav)
        nav: 現在 NAV(原幣)
        fx: 1 原幣 = ? TWD(TWD 基金 = 1.0);缺 / ≤ 0 → mon_div_twd None
        adr_pct: 年化配息率(%)—— 真實記錄缺時的 fallback 依據;None → 不 fallback
    Returns:
        dict {latest_div_per_unit, mon_div_ccy, mon_div_twd, mon_div_units, source}
        source ∈ {"records", "estimate", None};必要輸入缺 → 值 None + source None
        (§1 Fail Loud:真實與估算皆不可得時不捏造)
    """
    latest = latest_dividend_per_unit(dividends)
    u = _safe_float(units_held)
    n = _safe_float(nav)
    f = _safe_float(fx)
    a = _safe_float(adr_pct)
    out: dict = {
        "latest_div_per_unit": latest,
        "mon_div_ccy": None,
        "mon_div_twd": None,
        "mon_div_units": None,
        "source": None,
    }
    if u is None or u <= 0 or n is None or n <= 0:
        return out
    if latest is not None and latest > 0:
        mon_div_ccy = latest * u                       # 真實:最近一筆實配 × 持有單位
        out["source"] = "records"
    elif a is not None and a > 0:
        mon_div_ccy = (u * n) * a / 100.0 / 12.0       # 估算:原幣本金 × adr / 12
        out["source"] = "estimate"
    else:
        return out
    out["mon_div_ccy"] = mon_div_ccy
    if f is not None and f > 0:
        out["mon_div_twd"] = mon_div_ccy * f
    out["mon_div_units"] = mon_div_ccy / n
    return out


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
    """歷史配息折 TWD 的 FX 取數 SSOT(v19.176 標註)。

    全站「歷史 dividend × FX」一律走本函式:
    - buy_date FX(本檔 line 160 用):買入日換匯率
    - ex_date FX(本檔 line 187 用):每筆配息除息日換匯率
    優先順序:fx_by_date 字典查當日歷史率 → fx_default(spot)fallback。
    回傳 (rate, source) 讓 caller 可記 provenance。

    **不要** 在 UI / 其他 service 自行算「dividend × 某 FX」— 一律 import 本函式。
    """
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
    nav_return_pct = ((last_nav - buy_nav) / buy_nav) * 100.0 if buy_nav > 0 else 0.0

    # v19.180:全期實際累計 3 軸(不年化,即使持有 < 0.5 年也算出真實值)。
    # 修截圖反饋:「(全期自算)」欄名暗示實際累計,但 v19.175 設計實作年化值,
    # 短歷史顯示 None 反讓 user 失去「實際累計多少」這個 100% 真實 user 持有期數據。
    # 兩軸並陳邏輯:
    #   - 全期實際(本段):整段持有期累計配息 / 本金,持有 0.1 年也照算
    #   - 年化(下段 v19.175 guard):需 ≥ 0.5 年才有意義,< 0.5 年仍 None
    cum_div_rate_pct = (
        (total_ccy_div / principal_ccy) * 100.0
        if principal_ccy > 0 else 0.0
    )
    cum_nav_return_pct = nav_return_pct  # 全期實際 NAV 漲跌幅(同 nav_return_pct,語意命名)
    cum_total_return_pct = cum_nav_return_pct + cum_div_rate_pct

    # v19.175:短歷史 guard — < 0.5 年不年化,顯示「—」/「⬜ 歷史不足」
    # (避免「2 個月配息 × 6 倍 = 30% 高配息率」幻象,§1 Fail Loud)
    if years < MIN_YEARS_FOR_ANNUALIZE:
        annual_nav_return_pct = None
        annual_div_rate_pct = None
        ret_1y_total_pct = None
        light = "歷史不足"
        light_emoji = _LIGHT_EMOJI["歷史不足"]
    else:
        safe_years = years
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
            # v19.180:全期實際 3 軸(永遠算出 — 短歷史也回真實累計值)
            "cum_div_rate_pct_🧮": round(cum_div_rate_pct, 2),
            "cum_nav_return_pct_🧮": round(cum_nav_return_pct, 2),
            "cum_total_return_pct_🧮": round(cum_total_return_pct, 2),
            # v19.175:年化 3 軸 — 短歷史(< 0.5 年)時 None;caller / UI 顯示「—」
            "annual_nav_return_pct_🧮": (round(annual_nav_return_pct, 2)
                                         if annual_nav_return_pct is not None else None),
            "annual_div_rate_pct_🧮": (round(annual_div_rate_pct, 2)
                                       if annual_div_rate_pct is not None else None),
            "ret_1y_total_pct_🧮": (round(ret_1y_total_pct, 2)
                                    if ret_1y_total_pct is not None else None),
            "div_health_light_🧮": light,
            "div_health_emoji_🧮": light_emoji,
        },
        "_self_calc_fields": [
            "principal_ccy", "units_held",
            "events[].units_at_event", "events[].ccy_div_total",
            "events[].twd_div", "events[].single_event_div_pct",
            "summary.total_ccy_div", "summary.total_twd_div",
            "summary.holding_years", "summary.nav_return_pct",
            "summary.cum_div_rate_pct", "summary.cum_nav_return_pct",
            "summary.cum_total_return_pct",
            "summary.annual_nav_return_pct", "summary.annual_div_rate_pct",
            "summary.ret_1y_total_pct", "summary.div_health_light",
        ],
    }
