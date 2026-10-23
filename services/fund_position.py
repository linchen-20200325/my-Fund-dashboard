"""services/fund_position.py — HWM σ「基金位置」唯一 SSOT(L2 純函式,零 IO)。

2026-10-23 客戶裁示 2C(BL-0426)+ 同日 Stop Gate 裁示「選項 1」:

  1. HWM σ **只是**「基金相對自身近一年高點的位置證據」,**不是**任何交易訊號或交易建議(用字守衛見 `tests/test_ssot_2c_fund_position.py`)。
  2. 輸入一律用**既有**的配息還原(Total Return)NAV 序列
     (`services/total_return_series.restore_total_return_series`,核心 = 既有 Factor 法
     `services/fund_service.calculate_fund_total_return`),**不用原始 NAV 做正式判定**。
  3. **Fail closed**:歷史不足 / 配息基金但窗口內沒有任何配息真的被還原 /
     窗口內有配息紀錄卻沒被還原進序列(配息資料與淨值日對不上)/ 貨幣市場型 /
     σ≈0 / 還原無法可靠建立 → 一律 ⬜(資料未備／無法判定／不適用)——
     不退回原始 NAV、不補 0、不當成中性。
  4. 不新增任何數值 threshold。**低波動的數值門檻未裁示,另登記**(本批只用既有的
     σ≈0 `precision_service._SIGMA_ABS_EPS` 與貨幣市場分類 `regime_fit.asset_bucket`)。
  5. 中性三態「接近高點／中段／遠離高點」+「⬜ 無法判定／不適用(白話原因)」。
     切點沿用 `shared/signal_thresholds.ROTATION_SELL_SIGMA`(−0.5)/
     `ROTATION_BUY_SIGMA`(−1.5)—— **legacy／研究候選、未校準、非正式投資門檻**;
     輸出一律標 `thresholds.calibrated=False`。
  6. 全站 HWM σ consumer(含行動類功能)都改讀本函式;行動類功能的既有規則 /
     門檻 / 文字不改,只換 σ 來源(legacy 行動語意,待 BL-0428 重新裁示)。

數值基準(§4.1 單位):σ 位置在**配息還原序列**上計算;`hwm_tr` / `current_nav_tr` /
`level_*s` / `sigma_abs` 以「最新一筆原始淨值」為錨換算回原幣淨值單位
(還原序列 × 最新原始淨值 / 最新還原值;σ rank 與距 HWM % 為比值,不受此換算影響)——
讓畫面上的 HWM 與現價可以直接並列比較,不必另外解讀「還原序列從哪天起算」。
"""
from __future__ import annotations

import pandas as pd

#: 本模組 unavailable 原因 → 白話(放進 ⬜ 標籤括號)。
UNAVAILABLE_REASON_TEXT = {
    "no_series": "無淨值序列",
    "history_short": "淨值筆數不足，歷史太短",
    "returns_short": "日報酬筆數不足",
    "restore_failed": "配息還原序列無法可靠建立",
    "dividend_data_missing": "配息基金但近一年窗口內沒有任何配息被還原",
    "dividend_data_unreliable": "配息資料與淨值日對不上，無法可靠還原",
    "money_market": "貨幣市場型不適用",
    "low_volatility": "淨值幾乎沒有波動（σ≈0）",
}
UNAVAILABLE_LABEL_PREFIX = "⬜ 無法判定／不適用"
SERIES_BASIS = "total_return"
MONEY_MARKET_BUCKET = "貨幣市場"


def unavailable_label(reason: str) -> str:
    return f"{UNAVAILABLE_LABEL_PREFIX}（{UNAVAILABLE_REASON_TEXT.get(reason, reason)}）"


def _thresholds() -> dict:
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    return {"near_high": float(ROTATION_SELL_SIGMA),
            "far_from_high": float(ROTATION_BUY_SIGMA),
            "calibrated": False}


def _fund_parts(fund_obj) -> "tuple[object, object, list]":
    """fund dict(nested 或 flat)→ (series, dividends, [category / fund_type 字串...])。"""
    if not isinstance(fund_obj, dict):
        return None, None, []
    _mj = fund_obj.get("moneydj_raw")
    _mj = _mj if isinstance(_mj, dict) else {}
    _series = fund_obj.get("series")
    if _series is None:
        _series = _mj.get("series")
    _divs = fund_obj.get("dividends")
    if _divs is None:
        _divs = _mj.get("dividends")
    _cats = [str(_src.get(_k)).strip()
             for _src in (_mj, fund_obj) for _k in ("category", "fund_type")
             if _src.get(_k)]
    return _series, _divs, _cats


def _is_money_market(categories: list) -> bool:
    """category / fund_type 任一個經 `regime_fit.asset_bucket` 對到貨幣市場桶 → 不適用(fail closed)。"""
    from services.regime_fit import asset_bucket
    return any(asset_bucket(_c)[0] == MONEY_MARKET_BUCKET for _c in categories or [])


def _unavailable(reason: str, *, lookback: int, current_nav=None,
                 div_count_in_window=None, detail=None) -> dict:
    from shared.colors import TRAFFIC_NEUTRAL
    _label = unavailable_label(reason)
    return {
        "status": "unavailable", "reason": reason, "detail": detail,
        "position": None, "label": _label, "color": TRAFFIC_NEUTRAL,
        "sigma_rank": None, "sigma_abs": None, "hwm_tr": None, "current_nav_tr": None,
        "current_nav": current_nav, "dist_to_hwm_pct": None,
        "level_1s": None, "level_2s": None, "level_3s": None,
        "series_basis": SERIES_BASIS, "lookback": int(lookback),
        "div_count_in_window": div_count_in_window,
        "thresholds": _thresholds(),
        "error": _label,   # 相容全站既有 `"error" in r` 慣例(只有 unavailable 才帶)
    }


def _prepare(fund_obj) -> "tuple[dict | None, pd.Series | None, list | None, list]":
    """→ (提早結束的 unavailable 結果 | None, 正規化序列, 配息事件 [(Timestamp, amt)], categories)。

    配息只解析一次;任何一筆金額 > 0 的紀錄除息日不可解析 → restore_failed
    (無法判定它在不在窗口內、能不能還原)。"""
    from services.total_return_series import normalize_nav_series, parse_dividend_events
    _series, _divs, _cats = _fund_parts(fund_obj)
    _s, _serr = normalize_nav_series(_series)
    if _s is None and _serr not in ("no_series", "series_not_a_series"):
        # 有序列但日期重複 / 無法解析 → 還原無法可靠建立(不去重、不猜)
        return {"reason": "restore_failed", "detail": _serr}, None, None, _cats
    if _s is None or _s.empty:
        return {"reason": "no_series", "detail": _serr}, None, None, _cats
    _events, _derr = parse_dividend_events(_divs)
    if _derr:
        return ({"reason": "restore_failed", "detail": _derr,
                 "current_nav": round(float(_s.iloc[-1]), 4)}, _s, None, _cats)
    return None, _s, _events, _cats


def _finish(fund_obj, *, s_t: "pd.Series", s_tr_t: "pd.Series", restored_dates: list,
            events: list, cats: list, lookback: int) -> dict:
    """步驟 3~6(單點與批次共用同一份判定;`s_t` / `s_tr_t` 已截到同一個 t)。"""
    from services.fund_total_return import is_dividend_fund
    from services.precision_service import calc_hwm_sigma_levels

    _current_nav = round(float(s_t.iloc[-1]), 4)
    _ws, _we = s_t.tail(lookback).index[0], s_t.index[-1]
    _n_in_win = sum(1 for d in restored_dates if _ws <= d <= _we)
    _n_records_in_win = sum(1 for d, _ in events if _ws <= d <= _we)

    # 3a) 配息資料品質(二元檢查,不是數值門檻):窗口內有配息紀錄卻沒被還原進序列
    #     (例:除息日不在淨值日上)→ 還原不完整,不判。**不自行把配息挪到下一個淨值日**
    #     (那等於新公式)。
    if _n_records_in_win > _n_in_win:
        return _unavailable("dividend_data_unreliable", lookback=lookback,
                            current_nav=_current_nav, div_count_in_window=_n_in_win,
                            detail=f"records_in_window={_n_records_in_win},restored={_n_in_win}")

    # 3b) 配息閘門:配息基金,窗口內卻沒有任何配息紀錄 → 等於原始 NAV,不判。
    #     ⚠️ 「是不是配息基金」用的是 fund_obj 的**現在資訊**(完整配息清單 + 現在的
    #     moneydj_div_yield),不受 as_of 截斷 —— 方向是 fail closed(見 compute_fund_position)。
    if is_dividend_fund(fund_obj) and _n_in_win == 0:
        return _unavailable("dividend_data_missing", lookback=lookback,
                            current_nav=_current_nav, div_count_in_window=0)

    # 4) 貨幣市場型
    if _is_money_market(cats):
        return _unavailable("money_market", lookback=lookback, current_nav=_current_nav,
                            div_count_in_window=_n_in_win)

    # 5) σ 位階(還原窗口;以最新原始淨值為錨換算回原幣單位,比值不變)
    _win = s_tr_t.tail(lookback)
    _anchor = float(s_t.iloc[-1]) / float(_win.iloc[-1])
    _r = calc_hwm_sigma_levels(_win * _anchor, lookback=lookback)
    if not isinstance(_r, dict) or "error" in _r:
        _err = str((_r or {}).get("error", ""))
        if "報酬率序列不足" in _err:
            _reason = "returns_short"
        elif "σ≈0" in _err:
            _reason = "low_volatility"
        elif _err == "資料不足":
            _reason = "history_short"
        else:
            _reason = "restore_failed"
        return _unavailable(_reason, lookback=lookback, current_nav=_current_nav,
                            div_count_in_window=_n_in_win, detail=_err or None)

    # 6) 中性三態(calc_hwm_sigma_levels 已經 classify_base 對映好)
    return {
        "status": "ok", "reason": None, "detail": None,
        "position": _r["position"], "label": _r["label"], "color": _r["color"],
        "sigma_rank": _r["sigma_rank"], "sigma_abs": _r["sigma_abs"],
        "hwm_tr": _r["hwm"], "current_nav_tr": _r["current_nav"],
        "current_nav": _current_nav,
        "dist_to_hwm_pct": _r["dist_to_hwm_pct"],
        "level_1s": _r["level_1s"], "level_2s": _r["level_2s"], "level_3s": _r["level_3s"],
        "series_basis": SERIES_BASIS, "lookback": lookback,
        "div_count_in_window": _n_in_win,
        "thresholds": _thresholds(),
    }


def _early(pre: dict, lookback: int) -> dict:
    return _unavailable(pre["reason"], lookback=lookback, current_nav=pre.get("current_nav"),
                        detail=pre.get("detail"))


def compute_fund_position(fund_obj: dict, lookback: int = 252, *, as_of=None) -> dict:
    """HWM σ 基金位置(唯一 SSOT)。

    Parameters
    ----------
    fund_obj : dict  nested(`moneydj_raw` 內含 category / moneydj_div_yield / dividends)或 flat;
                     讀 `series`、`dividends`、`category`/`fund_type`、`moneydj_div_yield`
                     (與 `services.fund_total_return.is_dividend_fund` 同一套讀法)。
    lookback : int   回看窗(交易日筆數,1Y ≈ 252)。
    as_of : 日期     (選填,回測用)**序列與還原用的配息**都截到 ≤ as_of。
                     ⚠️ **不是完整 PIT**:「這檔是不是配息基金」(`is_dividend_fund`)用的是
                     fund_obj 的**現在資訊**(完整配息清單、現在的 moneydj_div_yield),不截斷。
                     方向是 fail closed —— 例如 t 之後才開始配息的基金,在 t 時點會被判
                     `dividend_data_missing`(⬜),而不是本來可判的位置;不會反過來把配息
                     基金當非配息基金去判。

    Returns
    -------
    dict(鍵見下;unavailable 時數值鍵為 None,並額外帶 `"error": label`):
      status ("ok"/"unavailable"), reason, position ("near_high"/"mid"/"far_from_high"/None),
      label, color, sigma_rank, sigma_abs, hwm_tr, current_nav_tr, current_nav(原始最後值,只供顯示),
      dist_to_hwm_pct(還原基準), level_1s/level_2s/level_3s(還原基準),
      series_basis="total_return", lookback, div_count_in_window,
      thresholds={"near_high": −0.5, "far_from_high": −1.5, "calibrated": False}

    步驟(依序,第一個成立的 ⬜ 原因勝出):
      1. 序列缺 → no_series;筆數 < HWM_MIN_POINTS(既有 30)→ history_short
      2. 全段(≤ as_of)還原 → 取最後 lookback 筆窗口;還原失敗 → restore_failed
      3a. 窗口內有配息紀錄(金額 > 0)卻沒被還原進序列 → dividend_data_unreliable
      3b. 配息基金且窗口內真的被還原的配息 = 0 → dividend_data_missing
      4. 貨幣市場型 → money_market
      5. calc_hwm_sigma_levels(還原窗口):報酬不足 → returns_short;σ≈0 → low_volatility;
         其他 error → restore_failed
      6. 三態:`services.rotation.classify_base`(經 precision_service 對映)
    低波動的**數值**門檻未裁示,另登記;本函式不設。
    """
    from services.precision_service import HWM_MIN_POINTS
    from services.total_return_series import restore_total_return_series

    lookback = int(lookback)
    pre, _s, _events, _cats = _prepare(fund_obj)
    if pre is not None:
        return _early(pre, lookback)

    # 1) 序列(截到 ≤ as_of)
    if as_of is not None:
        _cut = pd.Timestamp(as_of)
        _s = _s[_s.index <= _cut]
        _events = [(d, a) for d, a in _events if d <= _cut]
    if _s.empty:
        return _unavailable("no_series", lookback=lookback, detail="no_points_before_as_of")
    if len(_s) < HWM_MIN_POINTS:
        return _unavailable("history_short", lookback=lookback,
                            current_nav=round(float(_s.iloc[-1]), 4))

    # 2) 全段還原 → 同一窗口
    _s_tr, _meta = restore_total_return_series(_s, _events)
    if _s_tr is None:
        return _unavailable("restore_failed", lookback=lookback,
                            current_nav=round(float(_s.iloc[-1]), 4),
                            div_count_in_window=0, detail=_meta.get("detail"))
    return _finish(fund_obj, s_t=_s, s_tr_t=_s_tr,
                   restored_dates=list(_meta.get("restored_div_dates") or []),
                   events=_events, cats=_cats, lookback=lookback)


def compute_fund_positions_at(fund_obj: dict, dates, lookback: int = 252) -> dict:
    """批次版(回測用):{t: compute_fund_position(fund_obj, lookback, as_of=t)},**逐位元相同**。

    效能:整條序列只還原一次再按 t 切片。依據 —— Factor 法的還原值只用到 ≤ 該日的資料
    (cumprod 前綴),所以「全段還原後截到 t」與「截到 t 後再還原」逐點相同;判定步驟 3~6
    走同一份 `_finish`。全段還原失敗時(失敗原因可能在 t 之後,截到 t 不一定失敗),
    **一律退回逐 t 呼叫 `compute_fund_position`**,不猜。等價性由
    `tests/test_ssot_2c_fund_position.py` 隨機多檔 × 多個 t 鎖住。
    """
    from services.precision_service import HWM_MIN_POINTS
    from services.total_return_series import restore_total_return_series

    lookback = int(lookback)
    _dates = list(dates or [])
    pre, _s, _events, _cats = _prepare(fund_obj)
    if pre is not None:
        return {t: compute_fund_position(fund_obj, lookback, as_of=t) for t in _dates}
    _s_tr, _meta = restore_total_return_series(_s, _events)
    if _s_tr is None:
        return {t: compute_fund_position(fund_obj, lookback, as_of=t) for t in _dates}
    _restored = list(_meta.get("restored_div_dates") or [])
    out: dict = {}
    for t in _dates:
        _cut = pd.Timestamp(t)
        _mask = _s.index <= _cut
        _s_t = _s[_mask]
        if _s_t.empty:
            out[t] = _unavailable("no_series", lookback=lookback, detail="no_points_before_as_of")
            continue
        if len(_s_t) < HWM_MIN_POINTS:
            out[t] = _unavailable("history_short", lookback=lookback,
                                  current_nav=round(float(_s_t.iloc[-1]), 4))
            continue
        out[t] = _finish(fund_obj, s_t=_s_t, s_tr_t=_s_tr[_mask],
                         restored_dates=[d for d in _restored if d <= _cut],
                         events=[(d, a) for d, a in _events if d <= _cut],
                         cats=_cats, lookback=lookback)
    return out


__all__ = [
    "MONEY_MARKET_BUCKET",
    "SERIES_BASIS",
    "UNAVAILABLE_LABEL_PREFIX",
    "UNAVAILABLE_REASON_TEXT",
    "compute_fund_position",
    "compute_fund_positions_at",
    "unavailable_label",
]
