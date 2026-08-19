"""services/switch_advisor.py — 換股池顧問編排器(v19.428)。L2 純函式,零 IO,不 import streamlit。

讀「帳本持倉 + 選股池候選」(皆已由 L3 取好數:含 NAV原幣 / 基金類別 / σ rank / 健康欄位),
逐檔依**型態**分流出建議。重用既有 primitive,不重造:
- 型態判定:`fund_type_classifier.classify_fund_type`(ER + override)
- 高/低基期:`rotation.classify_base` / 買方健康:`rotation.is_healthy_buy` / 回歸空間:`revert_upside_pct`
- 匯率位階疊加:`nav_fx_switch.nav_fx_signal`
- 總經看衰:由呼叫端傳入 macro composite 分數(L3 取自 `macro.composite_score`)

**分流規則**:
- **震盪型**:持倉貼近**高基期** → 從池中挑「低基期·健康(不接刀)·(優先)震盪型」配對換股(高→低賺回歸)
- **成長型**:總經看衰(為主)+ 該檔跌破均線(為輔)**雙確認** → 建議賣出轉現金;僅前者 → 🟡 警示
- **無法判定**:誠實回「資料不足·不建議」(§1)

**表現差 overlay(v19.430)**:與型態分流**獨立**的第二觸發 —— 表現差 = 跑輸大盤(`benchmark_compare`)
**OR** 絕對虧損(`switch_strategy` 紅燈)。表現差且型態分流未給換股(且非「賣轉現金」)→ 疊加選股池
替代標的建議(重用 `_best_candidate`)。池空 / 無合格 → 誠實「無合適替代標的」,不硬湊(§1)。

⚠️ 匯率誠實範圍:USDTWD 單一值 → 同幣別 A→B 換股 FX 近中性;匯率真正影響「成長型賣出轉台幣現金」
與「從現金新進場」等跨台幣動作。FX 位階以資訊呈現,不假裝決定每筆同幣別換股。
常數走 shared.signal_thresholds SSOT(§3.3)。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    GROWTH_BREAKDOWN_SMA_DAYS,
    GROWTH_MACRO_BEARISH_CUTOFF,
    UNDERPERF_LAG_THRESHOLD_PCT,
)

# action 詞彙
SWITCH = "switch"            # 震盪:換股 A→B
SELL_CASH = "sell_to_cash"   # 成長:賣出轉現金
WARN = "warn"               # 成長:警示(尚未雙確認)
HOLD = "hold"               # 續抱
INSUFFICIENT = "insufficient"  # 資料不足,不建議

_ACTION_ZH = {
    SWITCH: "🔄 建議換股", SELL_CASH: "🔴 建議賣出轉現金", WARN: "🟡 警示留意",
    HOLD: "➖ 續抱", INSUFFICIENT: "⬜ 資料不足",
}


def _row_get(row, *keys, default=None):
    """容錯取欄(支援中英別名)。不可用 `not in (None,"")`——值可能是 pandas Series(真值歧義)。"""
    for k in keys:
        if k in row:
            v = row[k]
            if v is None:
                continue
            if isinstance(v, str) and v == "":
                continue
            return v
    return default


def _name(row):
    return _row_get(row, "name", "基金名", "基金名稱") or _row_get(row, "code", default="")


def _norm_ccy(v) -> str:
    """計價幣別 → 正規化 ISO(未知回 '')。§4.1 跨幣別換股含匯差,由 cross_ccy 旗標標註。"""
    if not v:
        return ""
    from services.currency import normalize_ccy
    return normalize_ccy(v, default="")


# §4.1(user 2026-08-19「標註匯差但保留」):跨計價幣別換股 = 賣/買幣別不同,
# 動作本身被動吃到匯率變動 → 在建議理由標註提醒,但不砍掉跨幣別分散/賺價差機會。
_CROSS_CCY_NOTE = "⚠️ 跨幣別(換股含匯差風險)"


def _breakdown_below_sma(nav_series, window: int = GROWTH_BREAKDOWN_SMA_DAYS) -> "bool | None":
    """NAV 末值 < 近 window 點均線 → True(跌破);史不足 → None(§1 不硬判)。"""
    from services.portfolio_performance import _clean_nav
    _s = _clean_nav(nav_series)
    if _s is None or len(_s) < window:
        return None
    _sma = float(_s.tail(int(window)).mean())
    return float(_s.iloc[-1]) < _sma


def _best_candidate(held_code: str, pool_rows: list, *, held_ccy: str = "") -> "dict | None":
    """從池中挑最佳換入標的:低基期 + 健康(不接刀)+ 優先震盪型;σ rank 最負(跌最深)優先。

    held_ccy:持倉計價幣別(選填)—— 與候選幣別不同 → 回傳 cross_ccy=True(換股含匯差,§4.1)。
    """
    from services.fund_type_classifier import RANGE, classify_fund_type
    from services.rotation import _sigma, classify_base, is_healthy_buy, revert_upside_pct

    cands = [b for b in (pool_rows or [])
             if str(_row_get(b, "code", default="")) != held_code
             and classify_base(_row_get(b, "σ rank", "sigma_rank")) == "low"
             and is_healthy_buy(b)]
    if not cands:
        return None

    def _btype(b):
        return classify_fund_type(_row_get(b, "nav_series"),
                                  _row_get(b, "基金類別", "category"),
                                  override=_row_get(b, "type_override", default="")).get("type")

    _range_first = [b for b in cands if _btype(b) == RANGE] or cands
    _range_first.sort(key=lambda b: (_sigma(_row_get(b, "σ rank", "sigma_rank"))
                                     if _sigma(_row_get(b, "σ rank", "sigma_rank")) is not None else 0.0))
    b = _range_first[0]
    _cand_ccy = _norm_ccy(_row_get(b, "currency", "ccy", "幣別", default=""))
    return {"code": _row_get(b, "code", default=""), "name": _name(b), "type": _btype(b),
            "buy_sigma": _sigma(_row_get(b, "σ rank", "sigma_rank")),
            "ccy": _cand_ccy or None,
            "cross_ccy": bool(held_ccy and _cand_ccy and held_ccy != _cand_ccy),
            "potential_pct": revert_upside_pct(_row_get(b, "距 HWM %", "dist_hwm_pct"))}


def _blank_underperf() -> dict:
    """未評估 / 未表現差的預設 block(§1:缺料 = 不觸發,不臆測)。"""
    return {"is_underperforming": False, "reasons": [], "excess_pct": None,
            "benchmark_used": None, "full_period": False, "redlight": None,
            "lags_benchmark": False}


def eat_is_red(eat_status) -> bool:
    """吃本金燈號是否為紅 —— **兩種都算**,都值得示警(user 明確要留意吃本金):
      - 「🔴 嚴重吃本金(報酬為負)」:含息報酬 < 0(dividend_safety 的 gap>2pp 且 報酬<0)
      - 「🔴 吃本金」:含息報酬 ≥ 0 但 < 配息率(高配息掩蓋本金侵蝕 —— 最陰險的那種)
    `switch_strategy.switch_signal` 只認前者(字串含「嚴重」);後者靠本函式補上,
    否則「高配息掩蓋的吃本金」會漏報(稽核 HIGH)。無配息/資料不足 → 非紅(§1 不臆測)。
    """
    _e = str(eat_status or "")
    return "🔴" in _e and "吃本金" in _e


def assess_underperformance(*, fund_nav=None, benchmark_nav=None, benchmark_label=None,
                            excess_pct=None, full_period=False,
                            tr1y_pct=None, sharpe=None, eat_status=None,
                            switch_score=None, switch_coverage=None,
                            redlight=None) -> dict:
    """「表現差」= 跑輸大盤 **OR** 絕對虧損(紅燈)。純函式,零 IO;缺料誠實不觸發(§1)。

    - **跑輸大盤**:`excess_pct` < `UNDERPERF_LAG_THRESHOLD_PCT`(百分點,負 = 落後)。
      呼叫端可直接傳算好的 `excess_pct`(+`full_period`;如大表的「vs 大盤%」,避免重抓基準);
      或傳 `fund_nav`+`benchmark_nav` 讓本函式呼 `benchmark_compare.excess_return`。
      無 benchmark(其餘幣別)→ excess 為 None → 不判(§F)。
    - **絕對虧損 / 吃本金**:`switch_strategy.switch_signal(...) == RED`(嚴重吃本金[報酬<0] 或
      1Y含息<0 且 Sharpe<0)**或** `eat_is_red(eat_status)`(正報酬但配息侵蝕本金 = plain 🔴 吃本金,
      switch_signal 不認,補上避免漏報)。reason 依序標「🔴 嚴重吃本金 > 🔴 吃本金 > 絕對虧損」。
      呼叫端若已算好紅燈可直接傳 `redlight`(bool)省重算;否則傳 tr1y/sharpe/eat_status/score(+coverage)。

    Returns:
        {is_underperforming, reasons[], excess_pct, benchmark_used, full_period, redlight, lags_benchmark}
    """
    _reasons: list = []
    _excess = excess_pct
    _full = bool(full_period)
    _lags = False
    if _excess is None and fund_nav is not None and benchmark_nav is not None:
        from services.benchmark_compare import excess_return
        _er = excess_return(fund_nav, benchmark_nav)
        _excess = _er["excess_pct"]
        _full = bool(_er["full_period"])
    if _excess is not None and _excess < UNDERPERF_LAG_THRESHOLD_PCT:
        _lags = True
        _reasons.append("跑輸大盤")

    if redlight is None and (
        eat_status is not None
        or (tr1y_pct is not None and sharpe is not None and switch_score is not None)
    ):
        from services.switch_strategy import RED, switch_signal
        # switch_signal 只認「嚴重」紅;正報酬但配息侵蝕本金(plain 🔴 吃本金)靠 eat_is_red 補上
        redlight = (switch_signal(tr1y_pct, sharpe, eat_status, switch_score,
                                  coverage=switch_coverage) == RED) or eat_is_red(eat_status)
    _abs = bool(redlight) if redlight is not None else False
    if _abs:
        # 紅燈原因講白:嚴重吃本金(報酬<0)> 吃本金(正報酬但配息侵蝕本金)> 籠統絕對虧損
        _es = str(eat_status or "")
        if "嚴重" in _es:
            _reasons.append("🔴 嚴重吃本金")
        elif eat_is_red(_es):
            _reasons.append("🔴 吃本金(配息侵蝕本金)")
        else:
            _reasons.append("絕對虧損")

    return {
        "is_underperforming": bool(_lags or _abs),
        "reasons": _reasons,
        "excess_pct": _excess,
        "benchmark_used": benchmark_label,
        "full_period": _full,
        "redlight": (bool(redlight) if redlight is not None else None),
        "lags_benchmark": _lags,
    }


def advise_holding(held_row: dict, pool_rows: list, *, fx_label=None,
                   macro_composite=None, underperformance=None) -> dict:
    """單一持倉 → 建議 dict。型態分流(震盪高→低換股 / 成長雙確認賣出 / 無法判定)+ 表現差 overlay。

    `underperformance`:由呼叫端以 `assess_underperformance` 算好傳入(需 benchmark / 紅燈輸入)。
    表現差時(§req 3/4/5)疊加選股池替代標的建議 —— 與型態分流獨立,不覆蓋既有動作。
    """
    from services.fund_type_classifier import RANGE, classify_fund_type
    from services.nav_fx_switch import nav_fx_signal
    from services.rotation import classify_base

    _code = str(_row_get(held_row, "code", default=""))
    _nav = _row_get(held_row, "nav_series")
    _cat = _row_get(held_row, "基金類別", "category")
    _held_ccy = _norm_ccy(_row_get(held_row, "currency", "ccy", "幣別", default=""))
    _tinfo = classify_fund_type(_nav, _cat, override=_row_get(held_row, "type_override", default=""))
    _ftype = _tinfo["type"]

    _under = underperformance or _blank_underperf()
    _out = {"code": _code, "name": _name(held_row), "type": _ftype,
            "type_method": _tinfo["method"], "er": _tinfo["er"],
            "action": HOLD, "action_zh": _ACTION_ZH[HOLD], "reason": "",
            "switch_to": None, "underperformance": _under, "underperf_candidate": None,
            "signals": {"nav_level": None, "sigma_rank": None, "fx_label": fx_label,
                        "macro_composite": macro_composite, "breakdown": None}}

    if _ftype is None:
        _out.update(action=INSUFFICIENT, action_zh=_ACTION_ZH[INSUFFICIENT], reason=_tinfo["rationale"])
    elif _ftype == RANGE:
        _nav_level = classify_base(_row_get(held_row, "σ rank", "sigma_rank"))
        _fx = nav_fx_signal(_nav_level, fx_label)
        _out["signals"].update(nav_level=_nav_level, fx_label=fx_label)
        if _nav_level == "high":
            _cand = _best_candidate(_code, pool_rows, held_ccy=_held_ccy)
            if _cand and _cand["code"]:
                _xccy = f" {_CROSS_CCY_NOTE}" if _cand.get("cross_ccy") else ""
                _out.update(action=SWITCH, action_zh=_ACTION_ZH[SWITCH], switch_to=_cand,
                            reason=(f"震盪型 + 貼近高基期 → 換入池中低基期健康標的「{_cand['name']}」"
                                    f"(賺回歸)。{_fx['rationale']}{_xccy}"))
            else:
                _out.update(action=HOLD, action_zh=_ACTION_ZH[HOLD],
                            reason="震盪型 + 高基期,但池中無『低基期且健康』標的可換 → 建議持有或轉現金(不硬湊,§1)。")
        else:
            _nav_zh = {"low": "低基期", "mid": "中性", "unknown": "基期未知"}.get(_nav_level, _nav_level)
            _out.update(reason=f"震盪型 + {_nav_zh}(未貼近高點)→ 續抱,等接近高基期再評估換出。")
    else:
        # 成長型:雙確認賣出
        _bearish = (macro_composite is not None) and (float(macro_composite) <= GROWTH_MACRO_BEARISH_CUTOFF)
        _bd = _breakdown_below_sma(_nav)
        _out["signals"].update(breakdown=_bd)
        if macro_composite is None:
            _out.update(reason="成長型;總經分數未取得 → 暫不觸發賣出(§1 缺料不臆測)。")
        elif _bearish and _bd is True:
            _out.update(action=SELL_CASH, action_zh=_ACTION_ZH[SELL_CASH],
                        reason=(f"成長型:總經看衰(composite {macro_composite:.1f} ≤ {GROWTH_MACRO_BEARISH_CUTOFF:g})"
                                f" + 該檔跌破 {GROWTH_BREAKDOWN_SMA_DAYS} 日均線 → 雙確認,建議賣出轉台幣現金(避開下行)。"))
        elif _bearish and _bd is None:
            _out.update(action=WARN, action_zh=_ACTION_ZH[WARN],
                        reason="成長型:總經看衰,但該檔均線史不足無法確認跌破 → 警示留意(未達雙確認)。")
        elif _bearish:
            _out.update(action=WARN, action_zh=_ACTION_ZH[WARN],
                        reason="成長型:總經看衰(為主)但尚未跌破均線 → 🟡 警示留意,續觀察(未達雙確認賣出)。")
        else:
            _out.update(reason="成長型:總經未看衰 → 續抱成長部位,順勢。")

    # ── 表現差 overlay(§req 3/4/5):與型態分流獨立,不覆蓋既有動作 ──
    if _under.get("is_underperforming"):
        _rz = " + ".join(_under.get("reasons") or []) or "表現差"
        _base = f" 另:{_out['reason']}" if _out["reason"] else ""
        if _out["switch_to"] is not None:
            _out["reason"] = f"⚠️ 表現差({_rz})。{_out['reason']}"            # 型態已給換入標的
        elif _out["action"] == SELL_CASH:
            _out["reason"] = f"⚠️ 表現差({_rz});已建議轉現金避開下行,先不新進場。{_out['reason']}"
        else:
            _uc = _best_candidate(_code, pool_rows, held_ccy=_held_ccy)      # HOLD/WARN/資料不足 → 補選股池建議
            _out["underperf_candidate"] = _uc
            if _uc and _uc["code"]:
                _xccy = f" {_CROSS_CCY_NOTE}" if _uc.get("cross_ccy") else ""
                _out["reason"] = f"⚠️ 表現差({_rz})→ 建議從選股池換入「{_uc['name']}」。{_xccy}{_base}"
            else:
                _out["reason"] = f"⚠️ 表現差({_rz}),但選股池無合適替代標的(不硬湊,§1)。{_base}"

    return _out


def advise_switches(held_rows: list, pool_rows: list, *, fx_label=None,
                    macro_composite=None, underperformance_by_code=None) -> dict:
    """全部持倉 → {advices:[...], summary:{...}}。§1:每筆缺條件誠實標記,不硬給動作。

    `underperformance_by_code`:{code → assess_underperformance(...)},由 L3 逐檔算好(需 benchmark)。
    """
    _ubc = underperformance_by_code or {}
    _adv = [advise_holding(h, pool_rows, fx_label=fx_label, macro_composite=macro_composite,
                           underperformance=_ubc.get(str(_row_get(h, "code", default=""))))
            for h in (held_rows or []) if _row_get(h, "code", default="")]
    _counts: dict = {}
    for a in _adv:
        _counts[a["action"]] = _counts.get(a["action"], 0) + 1
    _n_under = sum(1 for a in _adv if a.get("underperformance", {}).get("is_underperforming"))
    return {
        "advices": _adv,
        "summary": {
            "n_holdings": len(_adv),
            "n_switch": _counts.get(SWITCH, 0),
            "n_sell_cash": _counts.get(SELL_CASH, 0),
            "n_warn": _counts.get(WARN, 0),
            "n_hold": _counts.get(HOLD, 0),
            "n_insufficient": _counts.get(INSUFFICIENT, 0),
            "n_underperforming": _n_under,
            "fx_label": fx_label,
            "macro_composite": macro_composite,
        },
        "caveat": ("換股顧問為紀律工具,非獲利保證:僅在型態 × 基期 × 總經 × 匯率 × 表現差條件對齊時建議動作,"
                   "缺條件一律誠實回「持有/資料不足」。回測顯示規則有正期望值 ≠ 單筆一定賺。"),
    }
