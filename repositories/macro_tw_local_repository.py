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

# v19.223 P1-2:FinMind URL 收口至 shared/api_endpoints.py SSOT
from shared.api_endpoints import FINMIND_BASE

# v19.385 T1 拔毒:`_finmind_macro_series` + `_NDC_SIGNAL_KEYS` / `_TW_PMI_KEYS`
# 三者為 dataset `TaiwanMacroEconomics`(FinMind 不存在,v19.342 查證)遺留,production
# 0 caller 已刪(NDC → `_finmind_business_indicator`;PMI → `tw_pmi_repository` 9 源賽跑;
# export → 海關 opendata 6053)。各 fetcher 現況見其自身 docstring。


def _finmind_business_indicator(months_back: int = 18,
                                token: str = "") -> Optional[pd.DataFrame]:
    """抓 FinMind `TaiwanBusinessIndicator`(國發會景氣指標官方鏡像,寬表)。

    v19.342 新增(鏡像 stock tw_macro.fetch_business_indicator_series v19.85):
    欄位契約(FinMind SDK data_loader.taiwan_business_indicator):
      date / leading / coincident / lagging / monitoring(景氣對策信號綜合分數)
      / monitoring_color(燈號)。
    失敗回 None(print log,不捏造)。
    """
    today = _dt.date.today()
    params: dict = {
        'dataset':    'TaiwanBusinessIndicator',
        'start_date': (today - _dt.timedelta(days=int(months_back * 31))
                       ).strftime('%Y-%m-%d'),
        'end_date':   today.strftime('%Y-%m-%d'),
    }
    if token:
        params['token'] = token
    r = fetch_url(FINMIND_BASE, params=params, timeout=15)
    if r is None:
        print('[macro_tw_local/TBI] ❌ FinMind TaiwanBusinessIndicator 無回應')
        return None
    try:
        _j = r.json()
    except Exception as e:
        import sys as _sys
        print(f'[macro_tw_local/TBI] ❌ JSON parse: {type(e).__name__}: {e}',
              file=_sys.stderr)
        return None
    rows = _j.get('data', [])
    if not rows:
        print(f"[macro_tw_local/TBI] ⚠️ 空 data(msg={str(_j.get('msg', ''))[:80]})")
        return None
    df = pd.DataFrame(rows)
    if 'date' not in df.columns or 'monitoring' not in df.columns:
        print(f'[macro_tw_local/TBI] ❌ 欄位不符: {list(df.columns)[:8]}')
        return None
    _keep = ['date'] + [c for c in ('monitoring', 'monitoring_color', 'leading')
                        if c in df.columns]
    out = df[_keep].copy()
    out['monitoring'] = pd.to_numeric(out['monitoring'], errors='coerce')
    out = out.dropna(subset=['monitoring']).sort_values('date').reset_index(drop=True)
    if out.empty:
        return None
    return out


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
        # v19.342 additive:官方燈號字串(TBI monitoring_color;schema 驗證僅驗
        # score/trend,additive key 安全)
        'color_latest': None,
    }
    # v19.342:改走 TaiwanBusinessIndicator 寬表(原 TaiwanMacroEconomics 長表
    # dataset 不存在,自建立起恆回「無資料」— 見檔頭 v19.342 診斷註)。
    sub_tbi = _finmind_business_indicator(months_back=max(months_back, 6),
                                          token=token)
    if sub_tbi is None or len(sub_tbi) < 3:
        result['error'] = 'FinMind TaiwanBusinessIndicator 無景氣對策信號資料'
        return result
    if 'monitoring_color' in sub_tbi.columns:
        _c = str(sub_tbi['monitoring_color'].iloc[-1] or '').strip()
        result['color_latest'] = _c or None
    sub = sub_tbi[['date', 'monitoring']].rename(columns={'monitoring': 'value'})
    vals = [int(round(v)) for v in sub['value'].tail(6).tolist()]
    cur, prev = vals[-1], vals[-2]
    prev2 = vals[-3] if len(vals) >= 3 else None
    result['score_latest'] = cur
    result['score_prev']   = prev
    result['score_prev2']  = prev2
    result['trend']        = vals
    result['date_latest']  = str(sub['date'].iloc[-1])[:10]
    # v19.151 F-PROV-1 phase 2:升級 source 至具名 dataset + 加 fetched_at UTC ISO
    # v19.342:dataset 正名 TaiwanBusinessIndicator(舊名不存在,見檔頭診斷註)
    result['source']       = 'FinMind:TaiwanBusinessIndicator'
    result['fetched_at']   = _dt.datetime.now(_dt.timezone.utc).isoformat()
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
# §2 TW PMI（9 源並行賽跑 — v19.348 自 Stock repo 移植）
# ════════════════════════════════════════════════════════════════════════════
@register_cache
@_ttl_cache(ttl_sec=TTL_15MIN)
def fetch_tw_pmi_local(months_back: int = 12, token: str = "") -> dict:
    """抓台灣製造業 PMI（9 源並行賽跑;user 2026-07-12 核准設計 B）。

    v19.348:原 FinMind 單源打的 dataset `TaiwanMacroEconomics` 不存在
    (v19.342 查證,恆無資料)→ 改走 `repositories.tw_pmi_repository`
    9 源賽跑(CIER-EN → data.gov.tw → NDC → MacroMicro → CIER → StockFeel
    → Cnyes → CIER-cid8 → MoneyDJ,第一命中即用、禁止平均,§2.1)。

    trend/prev 資料現實(§1 不腦補):
    - 命中源=data.gov.tw(CSV 天然含全月度歷史,帶 `series`)→ trend=近 6 月、
      prev=上月、inflection 正常判定
    - 命中源=其他 8 個單點源 → value/date/source 有值,trend=[value]、
      prev=None、inflection 維持「⬜ 資料不足」(單點無從判轉折,誠實顯示)

    Args:
        months_back: 保留參數(向後相容;賽跑源天然回最新,不吃此參數)。
        token: 保留參數(向後相容;9 源皆無需 token)。

    Returns
    -------
    dict
        {
          'value':       float | None,   # 最新月份 PMI
          'prev':        float | None,   # 上月 PMI(單點源為 None)
          'trend':       list[float],    # 近 6 月(單點源為 [value])
          'inflection':  str,            # '🚀 由縮轉擴' / '⚠️ 由擴轉縮' / ...
          'date_latest': str,
          'source':      str | None,     # 'CIER-EN' / 'data.gov.tw' / ...
          'error':       str | None,
        }

    分類門檻：PMI 50 為擴張 / 收縮分水嶺。
    """
    _ = (months_back, token)   # 向後相容保留,賽跑版不使用
    result: dict = {
        'value': None, 'prev': None, 'trend': [],
        'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
    }
    from repositories.tw_pmi_repository import fetch_tw_pmi_race
    hit = fetch_tw_pmi_race()
    result['fetched_at'] = hit.get('fetched_at') or _dt.datetime.now(
        _dt.timezone.utc).isoformat()
    if hit.get('value') is None:
        result['error'] = f"TW PMI 9 源全敗:{hit.get('_err_pmi', 'unknown')}"
        return result
    result['value']       = round(float(hit['value']), 1)
    result['date_latest'] = str(hit.get('date', ''))[:10]
    result['source']      = str(hit.get('source', ''))   # F-PROV-1 血緣沿用
    _series = hit.get('series') or []
    if len(_series) >= 2:
        vals = [round(float(v), 1) for _, v in _series[-6:]]
        cur, prev = vals[-1], vals[-2]
        result['prev']  = prev
        result['trend'] = vals
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
    else:
        # 單點源:值可用但無上月對照 — inflection 誠實維持「資料不足」
        result['trend'] = [result['value']]
    return result


# ════════════════════════════════════════════════════════════════════════════
# §3 TW Export YoY（財政部出口年增率）
# ════════════════════════════════════════════════════════════════════════════
# ── 海關 opendata 6053(新臺幣出口總值)CSV 解析 — v19.355 移植股票 repo ──
_CUSTOMS_EXPORT_CSV_URL = 'https://opendata.customs.gov.tw/data/6053/csv.csv'


def _customs_export_yoy_points(text: str) -> list:
    """解析海關 6053 出口 CSV → 同月對齊 YoY 序列(純函式,可單測)。

    真實格式(股票 repo 探針實測):
        "年度","月份","出口總值(新臺幣千元)",...
        "115","4","2153671224",...        # 民國年、降序、新臺幣千元
    §7 數學式:西元年 = 民國年 + 1911;YoY% = (值[Y,M] / 值[Y-1,M] − 1) × 100
    (**同月對齊**,非 iloc 位置索引 — 抗缺月/亂序)。
    sanity:base>0、民國年≥50、月∈[1,12]、YoY∈[-80,200]。
    Returns: [((西元年, 月), yoy_pct), ...] 依 (年,月) 升冪;資料不足 → []。
    """
    import csv as _csv
    import io as _io
    try:
        _rows = list(_csv.DictReader(_io.StringIO(text)))
    except Exception:
        return []
    if len(_rows) < 13:
        return []
    _cols = list(_rows[0].keys())
    _yr_c = next((c for c in _cols if '年度' in str(c)), None)
    _mo_c = next((c for c in _cols if '月份' in str(c) or str(c).strip() == '月'), None)
    # 出口總值優先(含復出口,對齊頭條口徑);無則純出口(排除 增/率/比/差/復)
    _val_c = (next((c for c in _cols if '出口總值' in str(c)), None)
              or next((c for c in _cols if str(c).startswith('出口')
                       and not any(_x in str(c) for _x in ('增', '率', '比', '差', '復'))),
                      None))
    if not (_yr_c and _mo_c and _val_c):
        return []
    _by_ym: dict = {}   # (西元年, 月) -> 出口總值(千元)
    for _r in _rows:
        try:
            _roc = int(str(_r.get(_yr_c, '')).strip())
            _mo = int(str(_r.get(_mo_c, '')).strip())
            _v = float(str(_r.get(_val_c, '')).replace(',', '').strip())
        except (ValueError, TypeError):
            continue
        if _roc < 50 or not (1 <= _mo <= 12):   # 民國年 sanity
            continue
        _by_ym[(_roc + 1911, _mo)] = _v
    _pts = []
    for (_y, _m), _v_now in _by_ym.items():
        _base = _by_ym.get((_y - 1, _m))         # 去年同月
        if _base is None or _base <= 0:
            continue
        _yoy = round((_v_now / _base - 1) * 100, 2)
        if -80 <= _yoy <= 200:
            _pts.append(((_y, _m), _yoy))
    _pts.sort(key=lambda t: t[0])                # 依 (年,月) 升冪
    return _pts


@register_cache
@_ttl_cache(ttl_sec=TTL_15MIN)
def fetch_tw_export_yoy(months_back: int = 12, token: str = "") -> dict:
    """抓台灣出口年增率歷史(海關 opendata 6053,**新臺幣**計價)。

    v19.355:原掛 FinMind `TaiwanMacroEconomics`(FinMind 不存在此 dataset,恆
    error)→ 改走海關 opendata 6053 CSV(股票 repo 已驗證穩定源),同月對齊算 YoY。
    §4.1 單位:新臺幣千元(YoY 為比率,單位無關;但與財政部美元頭條有匯率落差,
    source 標「新臺幣」誠實區分)。months_back / token 參數保留相容(本源不需)。

    Returns  # (contract 不變)
    -------
    dict {value/prev/trend/inflection/date_latest/source/error}
    """
    result: dict = {
        'value': None, 'prev': None, 'trend': [],
        'inflection': '⬜ 資料不足',
        'date_latest': '', 'source': None, 'error': None,
    }
    r = fetch_url(_CUSTOMS_EXPORT_CSV_URL, timeout=15)
    if r is None or getattr(r, 'status_code', 0) != 200:
        result['error'] = (f'海關 opendata 6053 無回應'
                           f'(status={getattr(r, "status_code", "None")})')
        return result
    try:
        _text = r.content.decode('utf-8-sig', errors='ignore')
    except Exception:
        _text = getattr(r, 'text', '') or ''
    _pts = _customs_export_yoy_points(_text)
    if not _pts:
        result['error'] = '海關 6053 CSV 解析後無足夠出口 YoY 資料(需 ≥13 月同月對齊)'
        return result
    _tail = _pts[-6:]                            # 近 6 月(升冪)
    result['trend'] = [p[1] for p in _tail]
    (_y, _m), cur = _pts[-1]
    result['value'] = cur
    result['prev'] = _pts[-2][1] if len(_pts) >= 2 else None
    result['date_latest'] = f'{_y}-{_m:02d}'
    result['source'] = 'Customs:Export6053(海關新臺幣出口總值)'
    result['fetched_at'] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    prev = result['prev']
    if prev is None:
        result['inflection'] = '⬜ 資料不足'
    elif prev < 0 <= cur:
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
    # v19.151 F-PROV-1 phase 2(外資資料集名稱不同)
    result['source']      = 'FinMind:TaiwanStockTotalInstitutionalInvestors'
    result['fetched_at']  = _dt.datetime.now(_dt.timezone.utc).isoformat()
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
