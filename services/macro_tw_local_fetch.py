"""台股本地總經 fetcher 層 — Phase v19.24（2026-06-07）。

A+B Step 2a：為 services/macro_tw_local.py 純函式層補上資料抓取能力，
4 個 fetcher 鏡像 stock dashboard `tw_macro.py`：

- fetch_ndc_signal_history     : 國發會景氣對策信號（分數 9~45）
- fetch_tw_pmi_local           : 中華經濟研究院製造業 PMI
- fetch_tw_export_yoy          : 財政部出口年增率（%）
- fetch_foreign_consecutive_days : 外資連續買賣超日數

設計原則
========
- 統一資料源 FinMind（單源 MVP；多源 fallback 留待 v19.25 視需求加）
- 統一 HTTP 走 infra.proxy.fetch_url（NAS Squid proxy 備援）
- 統一 schema：失敗時回填 `error` 欄而非 raise，UI 可降級顯示
- 統一 _ttl_cache(900s) + register_cache 受 clear_all_caches 管理

⚠️ 此檔故意與 services/macro_service.py 既有 FRED/Yahoo 路徑分離：
   - macro_service.py    : 全球 / 美國（FRED + Yahoo Chart API）
   - macro_tw_local_fetch: 台灣（FinMind TaiwanMacroEconomics + 法人籌碼）
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

import pandas as pd

from infra.cache import _ttl_cache, register_cache
from infra.proxy import fetch_url
from shared.ttls import TTL_15MIN

__version__ = "1.0.0"

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# FinMind TaiwanMacroEconomics 指標關鍵字（含模糊比對 fallback）
_NDC_SIGNAL_KEYS = ('景氣對策信號(分)', '景氣對策信號')
_TW_PMI_KEYS     = ('製造業採購經理人指數', '製造業 PMI', 'PMI')
_EXPORT_YOY_KEYS = ('出口年增率(%)', '出口年增率', '出口貿易')


# ════════════════════════════════════════════════════════════════════════════
# 共用 FinMind macro series helper（鏡像 stock tw_macro.py:322）
# ════════════════════════════════════════════════════════════════════════════
def _finmind_macro_series(indicator_keys: tuple,
                          months_back: int = 18,
                          token: str = "") -> Optional[pd.DataFrame]:
    """抓 FinMind TaiwanMacroEconomics 指定指標月頻歷史。

    Returns
    -------
    pd.DataFrame[date, value] | None
        由舊到新排序；找不到資料或 HTTP 失敗回 None。
    """
    today    = _dt.date.today()
    end_dt   = today.strftime("%Y-%m-%d")
    start_dt = (today - _dt.timedelta(days=int(months_back * 31))).strftime("%Y-%m-%d")
    params: dict = {
        'dataset':    'TaiwanMacroEconomics',
        'start_date': start_dt,
        'end_date':   end_dt,
    }
    if token:
        params['token'] = token
    r = fetch_url(FINMIND_BASE, params=params, timeout=15)
    if r is None:
        return None
    try:
        rows = r.json().get('data', [])
    except Exception:
        return None
    if not rows:
        return None
    df = pd.DataFrame(rows)
    cand_col = next((c for c in ('indicator', 'name', 'metric')
                     if c in df.columns), None)
    val_col  = next((c for c in ('value', 'data') if c in df.columns), None)
    if cand_col is None or val_col is None or 'date' not in df.columns:
        return None
    mask = df[cand_col].astype(str).isin(indicator_keys)
    if not mask.any():
        mask = df[cand_col].astype(str).apply(
            lambda x: any(k in x for k in indicator_keys))
    if not mask.any():
        return None
    sub = df.loc[mask, ['date', val_col]].copy()
    sub.columns = ['date', 'value']
    sub['value'] = pd.to_numeric(sub['value'], errors='coerce')
    sub = sub.dropna().sort_values('date').reset_index(drop=True)
    if sub.empty:
        return None
    return sub


# ════════════════════════════════════════════════════════════════════════════
# §1 NDC 景氣對策信號（鏡像 stock tw_macro.py:369）
# ════════════════════════════════════════════════════════════════════════════
@register_cache
@_ttl_cache(ttl_sec=TTL_15MIN)
def fetch_ndc_signal_history(months_back: int = 12, token: str = "") -> dict:
    """抓景氣對策信號分數歷史，偵測連 2 月反轉拐點。

    Returns
    -------
    dict
        {
          'score_latest': int | None,
          'score_prev':   int | None,
          'score_prev2':  int | None,
          'trend':        list[int],   # 近 6 月
          'inflection':   str,          # '🚀 連2月翻多' / '⚠️ 連2月翻空' / ...
          'date_latest':  str,
          'source':       'FinMind' | None,
          'error':        str | None,
        }
    """
    result: dict = {
        'score_latest': None, 'score_prev': None, 'score_prev2': None,
        'trend': [], 'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
    }
    sub = _finmind_macro_series(_NDC_SIGNAL_KEYS,
                                months_back=months_back, token=token)
    if sub is None or len(sub) < 3:
        result['error'] = 'FinMind TaiwanMacroEconomics 無景氣對策信號資料'
        return result
    vals = [int(round(v)) for v in sub['value'].tail(6).tolist()]
    cur, prev = vals[-1], vals[-2]
    prev2 = vals[-3] if len(vals) >= 3 else None
    result['score_latest'] = cur
    result['score_prev']   = prev
    result['score_prev2']  = prev2
    result['trend']        = vals
    result['date_latest']  = str(sub['date'].iloc[-1])[:10]
    result['source']       = 'FinMind'
    if prev2 is not None:
        if prev2 >= prev and cur > prev:
            result['inflection'] = '🚀 連2月翻多'
        elif prev2 <= prev and cur < prev:
            result['inflection'] = '⚠️ 連2月翻空'
        elif cur > prev > prev2:
            result['inflection'] = '🟢 連3月上升'
        elif cur < prev < prev2:
            result['inflection'] = '🔴 連3月下降'
        else:
            result['inflection'] = '📊 震盪持平'
    return result


# ════════════════════════════════════════════════════════════════════════════
# §2 TW PMI（CIER 中華經濟研究院製造業）
# ════════════════════════════════════════════════════════════════════════════
@register_cache
@_ttl_cache(ttl_sec=TTL_15MIN)
def fetch_tw_pmi_local(months_back: int = 12, token: str = "") -> dict:
    """抓台灣製造業 PMI 歷史（FinMind 單源 MVP）。

    Returns
    -------
    dict
        {
          'value':       float | None,   # 最新月份 PMI
          'prev':        float | None,   # 上月 PMI
          'trend':       list[float],    # 近 6 月
          'inflection':  str,            # '🚀 由縮轉擴' / '⚠️ 由擴轉縮' / ...
          'date_latest': str,
          'source':      'FinMind' | None,
          'error':       str | None,
        }

    分類門檻：PMI 50 為擴張 / 收縮分水嶺。
    """
    result: dict = {
        'value': None, 'prev': None, 'trend': [],
        'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
    }
    sub = _finmind_macro_series(_TW_PMI_KEYS,
                                months_back=months_back, token=token)
    if sub is None or len(sub) < 2:
        result['error'] = 'FinMind TaiwanMacroEconomics 無 PMI 資料'
        return result
    vals = [round(float(v), 1) for v in sub['value'].tail(6).tolist()]
    cur, prev = vals[-1], vals[-2]
    result['value']       = cur
    result['prev']        = prev
    result['trend']       = vals
    result['date_latest'] = str(sub['date'].iloc[-1])[:10]
    result['source']      = 'FinMind'
    if prev < 50 <= cur:
        result['inflection'] = '🚀 由縮轉擴'
    elif prev >= 50 > cur:
        result['inflection'] = '⚠️ 由擴轉縮'
    elif cur >= 50 and cur > prev:
        result['inflection'] = '🟢 擴張加速'
    elif cur >= 50:
        result['inflection'] = '🟡 擴張趨緩'
    elif cur < prev:
        result['inflection'] = '🔴 收縮加深'
    else:
        result['inflection'] = '📊 收縮趨緩'
    return result


# ════════════════════════════════════════════════════════════════════════════
# §3 TW Export YoY（財政部出口年增率）
# ════════════════════════════════════════════════════════════════════════════
@register_cache
@_ttl_cache(ttl_sec=TTL_15MIN)
def fetch_tw_export_yoy(months_back: int = 12, token: str = "") -> dict:
    """抓台灣出口年增率歷史。

    Returns
    -------
    dict
        {
          'value':       float | None,   # 最新月份 YoY (%)
          'prev':        float | None,   # 上月 YoY (%)
          'trend':       list[float],    # 近 6 月
          'inflection':  str,            # '🚀 由負轉正' / '⚠️ 由正轉負' / ...
          'date_latest': str,
          'source':      'FinMind' | None,
          'error':       str | None,
        }
    """
    result: dict = {
        'value': None, 'prev': None, 'trend': [],
        'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
    }
    sub = _finmind_macro_series(_EXPORT_YOY_KEYS,
                                months_back=months_back, token=token)
    if sub is None or len(sub) < 2:
        result['error'] = 'FinMind TaiwanMacroEconomics 無出口年增率資料'
        return result
    vals = [round(float(v), 2) for v in sub['value'].tail(6).tolist()]
    cur, prev = vals[-1], vals[-2]
    result['value']       = cur
    result['prev']        = prev
    result['trend']       = vals
    result['date_latest'] = str(sub['date'].iloc[-1])[:10]
    result['source']      = 'FinMind'
    if prev < 0 <= cur:
        result['inflection'] = '🚀 由負轉正'
    elif prev >= 0 > cur:
        result['inflection'] = '⚠️ 由正轉負'
    elif cur >= 0 and cur > prev:
        result['inflection'] = '🟢 正成長加速'
    elif cur >= 0:
        result['inflection'] = '🟡 正成長趨緩'
    elif cur < prev:
        result['inflection'] = '🔴 衰退加深'
    else:
        result['inflection'] = '📊 衰退趨緩'
    return result


# ════════════════════════════════════════════════════════════════════════════
# §4 外資連續日數（鏡像 stock tw_macro.py:492）
# ════════════════════════════════════════════════════════════════════════════
@register_cache
@_ttl_cache(ttl_sec=TTL_15MIN)
def fetch_foreign_consecutive_days(days_back: int = 30, token: str = "") -> dict:
    """抓外資最近 N 日買賣超，計算連續同向日數與反轉拐點。

    Returns
    -------
    dict
        {
          'consec_days': int | None,    # 帶號（+ 連買、- 連賣）
          'reversed':    bool,
          'today_net':   int | None,    # 元
          'prev_streak': int | None,    # 帶號上一段連續日數
          'inflection':  str,
          'date_latest': str,
          'source':      'FinMind' | None,
          'error':       str | None,
        }
    """
    result: dict = {
        'consec_days': None, 'reversed': False, 'today_net': None,
        'prev_streak': None, 'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
    }
    today    = _dt.date.today()
    end_dt   = today.strftime("%Y-%m-%d")
    start_dt = (today - _dt.timedelta(days=days_back)).strftime("%Y-%m-%d")
    params: dict = {
        'dataset':    'TaiwanStockTotalInstitutionalInvestors',
        'start_date': start_dt,
        'end_date':   end_dt,
    }
    if token:
        params['token'] = token
    r = fetch_url(FINMIND_BASE, params=params, timeout=15)
    if r is None:
        result['error'] = 'FinMind 抓取失敗'
        return result
    try:
        rows = r.json().get('data', [])
    except Exception as e:
        result['error'] = f'FinMind JSON 解析失敗: {e}'
        return result
    fi_rows = [x for x in rows if x.get('name') == 'Foreign_Investor']
    if not fi_rows:
        result['error'] = 'FinMind 無 Foreign_Investor 資料'
        return result
    df = pd.DataFrame(fi_rows)
    # W5-3 §1: FII buy/sell 缺值處理 — to_numeric(errors='coerce') 把不可解析轉 NaN;
    # 接 fillna(0) 視為「該方向無交易」(業務正確,FinMind 偶爾單向欄位缺漏)。加 log 透明化
    _buy_num = pd.to_numeric(df.get('buy', 0), errors='coerce')
    _sell_num = pd.to_numeric(df.get('sell', 0), errors='coerce')
    _buy_nan = int(_buy_num.isna().sum())
    _sell_nan = int(_sell_num.isna().sum())
    if _buy_nan or _sell_nan:
        print(f"[macro_tw_local_fetch FII] fillna(0): buy={_buy_nan}, sell={_sell_nan} 筆視為當日該向無交易")
    df['net'] = _buy_num.fillna(0) - _sell_num.fillna(0)
    df = df.sort_values('date').reset_index(drop=True)
    if len(df) < 2:
        result['error'] = '外資資料筆數不足'
        return result
    nets = df['net'].astype(float).tolist()
    last_sign = 1 if nets[-1] > 0 else (-1 if nets[-1] < 0 else 0)
    consec = 0
    for v in reversed(nets):
        sign = 1 if v > 0 else (-1 if v < 0 else 0)
        if sign == last_sign and sign != 0:
            consec += 1
        else:
            break
    prev_streak = 0
    if consec < len(nets):
        before = nets[:len(nets) - consec]
        if before:
            prev_sign = 1 if before[-1] > 0 else (-1 if before[-1] < 0 else 0)
            for v in reversed(before):
                sign = 1 if v > 0 else (-1 if v < 0 else 0)
                if sign == prev_sign and sign != 0:
                    prev_streak += 1
                else:
                    break
            prev_streak = prev_streak * prev_sign
    result['consec_days'] = consec * last_sign
    result['today_net']   = int(nets[-1])
    result['prev_streak'] = prev_streak
    result['date_latest'] = str(df['date'].iloc[-1])[:10]
    result['source']      = 'FinMind'
    result['reversed']    = (consec == 1 and prev_streak * last_sign < -5)
    if consec == 1 and prev_streak <= -5:
        result['inflection'] = f'🚀 連{-prev_streak}賣→買（拐點）'
    elif consec == 1 and prev_streak >= 5:
        result['inflection'] = f'⚠️ 連{prev_streak}買→賣（拐點）'
    elif consec >= 5 and last_sign > 0:
        result['inflection'] = f'🟢 連{consec}日買超'
    elif consec >= 5 and last_sign < 0:
        result['inflection'] = f'🔴 連{consec}日賣超'
    else:
        result['inflection'] = '📊 震盪'
    return result
