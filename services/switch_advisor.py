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

⚠️ 匯率誠實範圍:USDTWD 單一值 → 同幣別 A→B 換股 FX 近中性;匯率真正影響「成長型賣出轉台幣現金」
與「從現金新進場」等跨台幣動作。FX 位階以資訊呈現,不假裝決定每筆同幣別換股。
常數走 shared.signal_thresholds SSOT(§3.3)。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    GROWTH_BREAKDOWN_SMA_DAYS,
    GROWTH_MACRO_BEARISH_CUTOFF,
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


def _breakdown_below_sma(nav_series, window: int = GROWTH_BREAKDOWN_SMA_DAYS) -> "bool | None":
    """NAV 末值 < 近 window 點均線 → True(跌破);史不足 → None(§1 不硬判)。"""
    from services.portfolio_performance import _clean_nav
    _s = _clean_nav(nav_series)
    if _s is None or len(_s) < window:
        return None
    _sma = float(_s.tail(int(window)).mean())
    return float(_s.iloc[-1]) < _sma


def _best_candidate(held_code: str, pool_rows: list) -> "dict | None":
    """從池中挑最佳換入標的:低基期 + 健康(不接刀)+ 優先震盪型;σ rank 最負(跌最深)優先。"""
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
    return {"code": _row_get(b, "code", default=""), "name": _name(b), "type": _btype(b),
            "buy_sigma": _sigma(_row_get(b, "σ rank", "sigma_rank")),
            "potential_pct": revert_upside_pct(_row_get(b, "距 HWM %", "dist_hwm_pct"))}


def advise_holding(held_row: dict, pool_rows: list, *, fx_label=None,
                   macro_composite=None) -> dict:
    """單一持倉 → 建議 dict。型態分流:震盪(高→低換股)/ 成長(雙確認賣出)/ 無法判定。"""
    from services.fund_type_classifier import RANGE, classify_fund_type
    from services.nav_fx_switch import nav_fx_signal
    from services.rotation import classify_base

    _code = str(_row_get(held_row, "code", default=""))
    _nav = _row_get(held_row, "nav_series")
    _cat = _row_get(held_row, "基金類別", "category")
    _tinfo = classify_fund_type(_nav, _cat, override=_row_get(held_row, "type_override", default=""))
    _ftype = _tinfo["type"]

    _out = {"code": _code, "name": _name(held_row), "type": _ftype,
            "type_method": _tinfo["method"], "er": _tinfo["er"],
            "action": HOLD, "action_zh": _ACTION_ZH[HOLD], "reason": "",
            "switch_to": None,
            "signals": {"nav_level": None, "sigma_rank": None, "fx_label": fx_label,
                        "macro_composite": macro_composite, "breakdown": None}}

    if _ftype is None:
        _out.update(action=INSUFFICIENT, action_zh=_ACTION_ZH[INSUFFICIENT], reason=_tinfo["rationale"])
        return _out

    if _ftype == RANGE:
        _nav_level = classify_base(_row_get(held_row, "σ rank", "sigma_rank"))
        _fx = nav_fx_signal(_nav_level, fx_label)
        _out["signals"].update(nav_level=_nav_level, fx_label=fx_label)
        if _nav_level == "high":
            _cand = _best_candidate(_code, pool_rows)
            if _cand and _cand["code"]:
                _out.update(action=SWITCH, action_zh=_ACTION_ZH[SWITCH], switch_to=_cand,
                            reason=(f"震盪型 + 貼近高基期 → 換入池中低基期健康標的「{_cand['name']}」"
                                    f"(賺回歸)。{_fx['rationale']}"))
            else:
                _out.update(action=HOLD, action_zh=_ACTION_ZH[HOLD],
                            reason="震盪型 + 高基期,但池中無『低基期且健康』標的可換 → 建議持有或轉現金(不硬湊,§1)。")
        else:
            _nav_zh = {"low": "低基期", "mid": "中性", "unknown": "基期未知"}.get(_nav_level, _nav_level)
            _out.update(reason=f"震盪型 + {_nav_zh}(未貼近高點)→ 續抱,等接近高基期再評估換出。")
        return _out

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
    return _out


def advise_switches(held_rows: list, pool_rows: list, *, fx_label=None,
                    macro_composite=None) -> dict:
    """全部持倉 → {advices:[...], summary:{...}}。§1:每筆缺條件誠實標記,不硬給動作。"""
    _adv = [advise_holding(h, pool_rows, fx_label=fx_label, macro_composite=macro_composite)
            for h in (held_rows or []) if _row_get(h, "code", default="")]
    _counts = {}
    for a in _adv:
        _counts[a["action"]] = _counts.get(a["action"], 0) + 1
    return {
        "advices": _adv,
        "summary": {
            "n_holdings": len(_adv),
            "n_switch": _counts.get(SWITCH, 0),
            "n_sell_cash": _counts.get(SELL_CASH, 0),
            "n_warn": _counts.get(WARN, 0),
            "n_hold": _counts.get(HOLD, 0),
            "n_insufficient": _counts.get(INSUFFICIENT, 0),
            "fx_label": fx_label,
            "macro_composite": macro_composite,
        },
        "caveat": ("換股顧問為紀律工具,非獲利保證:僅在型態 × 基期 × 總經 × 匯率條件對齊時建議動作,"
                   "缺條件一律誠實回「持有/資料不足」。回測顯示規則有正期望值 ≠ 單筆一定賺。"),
    }
