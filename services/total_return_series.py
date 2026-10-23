"""services/total_return_series.py — 配息還原(Total Return)NAV 序列,嚴格版(L2 純函式,零 IO)。

2026-10-23 客戶裁示 2C(BL-0426):HWM σ「基金位置」的輸入一律改用**既有**的配息還原序列,
**不發明新的配息修正公式**。本模組的還原核心就是 `services/fund_service.calculate_fund_total_return`
(Factor 法:`Factor_t = 1 + Dividend_t / NAV_t`、`Adj_NAV_T = NAV_T × Π Factor`),
與 `services/fund_service._total_return_nav`(Sharpe / MDD 風險指標路徑)底層同一支。

和 `_total_return_nav` 的差別只在**失敗時怎麼辦**:
  - `_total_return_nav`:還原失敗 → stderr log + **回退原始 NAV**(那條路徑的既有契約,
    被 `tests/test_total_return_nav_v19_356.py` 鎖住,本批**不改**)。
  - 本模組:還原失敗 → 回 `(None, {"reason": "restore_failed", ...})`,**絕不回原始 NAV**
    (§1 Fail Closed:基金位置寧可 ⬜ 無法判定,也不拿未還原序列冒充)。

前置正規化 / 驗證(舊函式遇到這些情況都會靜默出錯):
  - 序列一律先去 NaN、轉 DatetimeIndex、升冪排序(降冪輸入不會被倒置);日期重複 → restore_failed。
  - 配息紀錄格式與 `services/fund_total_return.is_dividend_fund` **同一份**解析
    (`dividend_record_amount` / `dividend_record_date`)。
  - 配息金額 ≥ 該除息日 NAV → restore_failed(還原不變量不成立;資料品質檢查,**不是**投資門檻)。
  - 同一除息日多筆 → restore_failed(**不自行加總**,加總屬新規則)。
  - 金額 > 0 但除息日無法解析 → restore_failed(這筆配息能不能還原無法判定)。
  - 還原後出現非正值 / 長度不符 → restore_failed。
"""
from __future__ import annotations

import pandas as pd

REASON_RESTORE_FAILED = "restore_failed"
REASON_NO_DIVIDEND_EVENTS = "no_dividend_events"


def _tr_restore_failed(detail: str, **meta) -> "tuple[None, dict]":
    out = {"reason": REASON_RESTORE_FAILED, "detail": detail,
           "div_count_total": meta.get("div_count_total", 0),
           "restored_div_dates": [], "div_count_in_window": 0}
    return None, out


def normalize_nav_series(s) -> "tuple[pd.Series | None, str | None]":
    """NAV 序列前處理:→ (升冪、無 NaN、tz-naive DatetimeIndex 的 float 序列, None)
    或 (None, 失敗原因)。**不補值、不去重**(日期重複 = 回失敗原因)。"""
    if s is None:
        return None, "no_series"
    if isinstance(s, pd.DataFrame):
        s = s.squeeze()
    if isinstance(s, dict):
        s = pd.Series(s)
    if not isinstance(s, pd.Series):
        return None, "series_not_a_series"
    # 快路徑(效能,結果不變):已是升冪、唯一、tz-naive DatetimeIndex 的無 NaN float 序列
    if (isinstance(s.index, pd.DatetimeIndex) and s.index.tz is None
            and s.dtype.kind == "f" and s.index.is_monotonic_increasing
            and s.index.is_unique and not bool(s.isna().any())):
        return s, None
    try:
        _s = pd.to_numeric(s, errors="coerce").dropna()
        _idx = pd.DatetimeIndex(pd.to_datetime(_s.index))
        if _idx.tz is not None:
            _idx = _idx.tz_localize(None)
        _s = pd.Series(_s.to_numpy(dtype=float), index=_idx)
    except (TypeError, ValueError) as _e:
        return None, f"series_index_unparsable:{type(_e).__name__}"
    if not _s.index.is_unique:
        return None, "duplicate_nav_dates"
    return _s.sort_index(), None


def parse_dividend_events(divs) -> "tuple[list, str | None]":
    """配息紀錄 → ([(Timestamp, amount>0), ...], None) 或 ([], 失敗原因)。

    金額不可解析 / ≤ 0 → 不是配息事件(略過,與 `is_dividend_fund` 同語意);
    金額 > 0 但除息日不可解析 → 失敗原因(這筆配息無法放回序列)。
    """
    from services.fund_total_return import dividend_record_amount, dividend_record_date
    events: list = []
    if not divs:
        return events, None
    try:
        _iter = list(divs)
    except TypeError:
        return [], "dividends_not_iterable"
    for _d in _iter:
        _ok, _amt_raw = dividend_record_amount(_d)
        if not _ok:
            continue
        try:
            _amt = float(_amt_raw)
        except (TypeError, ValueError):
            continue
        if _amt != _amt or _amt <= 0:          # NaN / 0 / 負 → 不是配息事件
            continue
        _date_raw = dividend_record_date(_d)
        try:
            if isinstance(_date_raw, pd.Timestamp):      # 已解析(如 as_of 截斷後的 tuple)→ 免重解析
                _dt = _date_raw
            else:
                _dt = pd.Timestamp(pd.to_datetime(str(_date_raw or "").replace("/", "-")))
        except (TypeError, ValueError):
            return [], "dividend_date_unparsable"
        if pd.isna(_dt):
            return [], "dividend_date_unparsable"
        if _dt.tzinfo is not None:
            _dt = _dt.tz_localize(None)
        events.append((_dt.normalize(), _amt))
    return events, None


def restore_total_return_series(s, divs, *, window_start=None) -> "tuple[pd.Series | None, dict]":
    """配息還原序列(嚴格版)。

    Parameters
    ----------
    s : pd.Series        原始 NAV(任意順序;會先正規化)
    divs : list          配息紀錄(dict `date`/`amount`/`div_per_unit`,或 tuple (date, amount))
    window_start : 日期   (選填)只用來計 `div_count_in_window`:該日(含)之後**真的被還原**的筆數

    Returns
    -------
    (series | None, meta)
      成功:(還原序列,與正規化後的 `s` 同 index、同長度, meta)
      無任何配息事件:(正規化後的 `s` 本身, meta(reason="no_dividend_events"))
                      —— 還原序列 ≡ 原序列,顯式標出,不是偽造。
      失敗:(None, meta(reason="restore_failed", detail=...))—— **絕不回原始 NAV**。

    meta 必含:`reason`(None / "no_dividend_events" / "restore_failed")、`div_count_total`
    (有效配息事件數)、`restored_div_dates`(真的被套進序列的除息日)、`div_count_in_window`。
    """
    _s, _err = normalize_nav_series(s)
    if _s is None:
        return _tr_restore_failed(_err or "no_series")
    if _s.empty:
        return _tr_restore_failed("empty_series")
    if bool((_s <= 0).any()):
        return _tr_restore_failed("non_positive_nav")

    events, _derr = parse_dividend_events(divs)
    if _derr:
        return _tr_restore_failed(_derr)

    _first, _last = _s.index[0], _s.index[-1]
    _in_range = [(d, a) for d, a in events if _first <= d <= _last]
    meta = {"reason": None, "detail": None, "div_count_total": len(events),
            "restored_div_dates": [], "div_count_in_window": 0}

    if not events:
        meta["reason"] = REASON_NO_DIVIDEND_EVENTS
        return _s, meta

    # 同一除息日多筆 → 失敗(不自行加總)。只檢查會影響本序列的區間內事件。
    _dates = [d for d, _ in _in_range]
    if len(_dates) != len(set(_dates)):
        return _tr_restore_failed("duplicate_ex_date", div_count_total=len(events))

    # 配息金額 ≥ 該除息日 NAV → 還原不變量不成立(資料品質檢查,不是投資門檻)
    if _in_range:
        _ev = pd.Series([a for _, a in _in_range], index=pd.DatetimeIndex(_dates))
        _common = _ev.index.intersection(_s.index)
        if len(_common) and bool((_ev.loc[_common].to_numpy()
                                  >= _s.loc[_common].to_numpy()).any()):
            return _tr_restore_failed("dividend_ge_nav", div_count_total=len(events))

    try:
        from services.fund_service import calculate_fund_total_return
        _nav_df = pd.DataFrame({"Date": _s.index, "NAV": _s.to_numpy(dtype=float)})
        _div_df = pd.DataFrame({"Date": [d for d, _ in events],
                                "Dividend": [a for _, a in events]})
        _tr = calculate_fund_total_return(_nav_df, _div_df)
    except Exception as _e:  # noqa: BLE001 — 核心炸掉 → 誠實失敗,不回 raw
        return _tr_restore_failed(f"core_exception:{type(_e).__name__}", div_count_total=len(events))

    if _tr is None or _tr.empty or len(_tr) != len(_s):
        return _tr_restore_failed("length_mismatch", div_count_total=len(events))
    s_tr = pd.Series(_tr["Adj_NAV"].to_numpy(dtype=float), index=_s.index)
    if not bool((s_tr > 0).all()) or bool(s_tr.isna().any()):
        return _tr_restore_failed("non_positive_restored", div_count_total=len(events))

    _restored = [pd.Timestamp(x) for x in _tr.loc[_tr["Dividend"] > 0, "Date"]]
    meta["restored_div_dates"] = _restored
    if window_start is not None:
        _ws = pd.Timestamp(window_start)
        meta["div_count_in_window"] = sum(1 for d in _restored if d >= _ws)
    else:
        meta["div_count_in_window"] = len(_restored)
    return s_tr, meta


__all__ = [
    "REASON_NO_DIVIDEND_EVENTS",
    "REASON_RESTORE_FAILED",
    "normalize_nav_series",
    "parse_dividend_events",
    "restore_total_return_series",
]
