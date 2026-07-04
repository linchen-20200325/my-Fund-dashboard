"""services/fund_screening.py — 基金品質篩選（L2 純計算）

職責（單一）：提供 MK 3-3-3 原則篩選函式；無 I/O、無 Streamlit。

§8.2 分層：L2 Service — 禁止 import requests / httpx / streamlit。
資料由 L3 UI 從 session_state 取出後傳入。

MK 郭俊宏「3-3-3 原則」：
  C1: 成立 > 3 年（以最早 NAV 日期推算，老標的歷經牛熊考驗）
  C2: 過去 3 年平均年化報酬率 > 7%（定存替代品，含息總報酬）
  C3: 晨星評級 3 顆星以上 / 同儕排名前 1/3（中前段班，有上升潛力）
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass


def fund_inception_years(inception_date, series=None) -> "float | None":
    """v19.308 SSOT — 基金「成立至今」年數（MK 3-3-3 ① / 健診 / 戰情室共用）。

    優先用 MoneyDJ 頁面現成的「成立日期」（inception_date，ISO 或 YYYY/MM/DD）——
    這是 user 要的「抓 MoneyDJ 已算好的」，不需本地長 NAV 歷史。缺成立日才以 NAV
    序列最早日推算；序列在 Streamlit Cloud 上可能因長歷史源被擋而過短
    （< 90 筆且推算 < 0.5 年 → 不可信 → None，§1 Fail Loud 不硬報 0.1 年）。

    回傳 float 年數，或 None（無成立日且序列不足以可信推算）。
    """
    import datetime as _dt
    # 1) MoneyDJ 現成成立日優先（免依賴本地長歷史）
    if inception_date:
        try:
            _inc = _dt.date.fromisoformat(str(inception_date)[:10])
            return (_dt.date.today() - _inc).days / 365.25
        except Exception:
            pass  # 成立日格式異常 → 落到序列 fallback
    # 2) fallback：NAV 序列最早日
    if series is None:
        return None
    try:
        s = series.dropna().sort_index() if hasattr(series, "dropna") else series
        if len(s) == 0:
            return None
        first = pd.Timestamp(s.index[0])
        if first.tzinfo is not None:
            first = first.tz_localize(None)
        _today = pd.Timestamp.utcnow().tz_localize(None).normalize()
        years = (_today - first).days / 365.25
        if len(s) < 90 and years < 0.5:
            return None  # 序列太短，無法可信估算成立日（Cloud 長歷史被擋時常見）
        return years
    except Exception:
        return None


def check_333_fund(
    nav_series: "pd.Series | None",
    metrics: "dict | None" = None,
    peer_series_map: "dict[str, pd.Series] | None" = None,
    *,
    min_years: float = 3.0,
    target_annualized: float = 0.07,
    peer_top_pct: float = 1 / 3,
) -> dict:
    """MK 3-3-3 原則評估（基金版）。

    Parameters
    ----------
    nav_series       : pd.Series  NAV 序列，index=DatetimeIndex（升序），values=float
    metrics          : dict       fund_service.calc_metrics 回傳的 metrics dict
                                  （用 ret_3y_ann 作 C2 最優先來源；單位為 %）
    peer_series_map  : dict       {fund_code → pd.Series}，用來計算同儕排名（C3）
    min_years        : float      C1/C2 年限（預設 3.0）
    target_annualized: float      C2 目標年化報酬（預設 0.07 = 7%，與 metrics % 轉換）
    peer_top_pct     : float      C3 通過門檻（預設 1/3）

    Returns
    -------
    dict 含：
        c1_age_years     : float | None   成立年數（以最早 NAV 日推算）
        c1_pass          : bool  | None
        c2_return_3y     : float | None   3 年年化報酬率（小數，非 %）
        c2_source        : str            "metrics"（MoneyDJ）or "nav_series"（本地計算）
        c2_pass          : bool  | None
        c3_peer_rank_pct : float | None   排名百分位（0=最好 ~ 1=最差）
        c3_pass          : bool  | None
        overall_pass     : bool  | None   三項全過；有任一明確 Fail → False
        criteria_count   : int            可計算項目數（最多 3）
    """
    result: dict = {
        'c1_age_years': None, 'c1_pass': None,
        'c2_return_3y': None, 'c2_source': '', 'c2_pass': None,
        'c3_peer_rank_pct': None, 'c3_pass': None,
        'overall_pass': None,
        'criteria_count': 0,
    }

    if nav_series is None or (hasattr(nav_series, 'empty') and nav_series.empty):
        return result

    # 統一 Series
    if isinstance(nav_series, pd.DataFrame):
        nav_series = nav_series.squeeze()
    s = nav_series.dropna().sort_index()
    if len(s) < 10:
        return result

    # 確保 tz-naive
    if hasattr(s.index, 'tz') and s.index.tz is not None:
        s.index = s.index.tz_localize(None)

    today = pd.Timestamp.utcnow().tz_localize(None).normalize()

    # ── C1：成立年數（v19.308：優先 MoneyDJ 現成成立日，缺則 NAV 最早日推算）──
    _inception = (metrics or {}).get("inception_date")
    age_years = fund_inception_years(_inception, s)
    if age_years is not None:
        c1_pass = age_years >= min_years
        result.update({'c1_age_years': round(age_years, 2), 'c1_pass': c1_pass})
        result['criteria_count'] += 1
    else:
        # 無成立日且序列過短 → 資料不足（c1_age_years/c1_pass 保持 None，
        # 顯示「—」/❓ 而非誤導的「0.1 年 ❌」）
        result['c1_age_years'] = None

    # ── C2：3 年年化報酬率 ──────────────────────────────────────────────────
    _m = metrics or {}

    # 優先用 MoneyDJ 的 ret_3y_ann（含息總報酬，已由 MoneyDJ 算好，單位 %）
    _ret_3y_pct = _m.get("ret_3y_ann")
    if _ret_3y_pct is not None:
        try:
            ann_ret = float(_ret_3y_pct) / 100.0
            c2_pass = ann_ret >= target_annualized
            result.update({
                'c2_return_3y': round(ann_ret, 4),
                'c2_source': 'metrics(MoneyDJ)',
                'c2_pass': c2_pass,
            })
            result['criteria_count'] += 1
        except (TypeError, ValueError):
            pass

    # 若 metrics 沒有 ret_3y_ann，從 NAV 序列自算（不含息，保守估計）
    if result['c2_return_3y'] is None:
        three_yr_ago = today - pd.Timedelta(days=int(min_years * 365.25))
        try:
            idx_loc = min(s.index.searchsorted(three_yr_ago, side='left'), len(s) - 1)
            start_ts = pd.Timestamp(s.index[idx_loc])
            if start_ts.tzinfo is not None:
                start_ts = start_ts.tz_localize(None)
            actual_years = (today - start_ts).days / 365.25
            sp = float(s.iloc[idx_loc])
            ep = float(s.iloc[-1])
            if actual_years >= 2.5 and sp > 0 and ep > 0:
                ann_ret = (ep / sp) ** (1.0 / actual_years) - 1.0
                c2_pass = ann_ret >= target_annualized
                result.update({
                    'c2_return_3y': round(ann_ret, 4),
                    'c2_source': 'nav_series（NAV，不含息）',
                    'c2_pass': c2_pass,
                })
                result['criteria_count'] += 1
        except Exception:
            pass

    # ── C3：同儕排名 ────────────────────────────────────────────────────────
    if peer_series_map:
        try:
            _ref_ago = today - pd.Timedelta(days=int(min_years * 365.25))
            peer_ann_rets: dict[str, float] = {}
            for code, ps in peer_series_map.items():
                if ps is None or len(ps) < 50:
                    continue
                ps2 = ps.dropna().sort_index()
                if hasattr(ps2.index, 'tz') and ps2.index.tz is not None:
                    ps2.index = ps2.index.tz_localize(None)
                li = min(ps2.index.searchsorted(_ref_ago, side='left'), len(ps2) - 1)
                sp_p = float(ps2.iloc[li])
                ep_p = float(ps2.iloc[-1])
                st_ts = pd.Timestamp(ps2.index[li])
                if st_ts.tzinfo is not None:
                    st_ts = st_ts.tz_localize(None)
                ay = (today - st_ts).days / 365.25
                if ay >= 2.5 and sp_p > 0 and ep_p > 0:
                    peer_ann_rets[code] = (ep_p / sp_p) ** (1.0 / ay) - 1.0

            if peer_ann_rets:
                # 用 NAV 報酬也加入自己（若有 C2 from nav_series）
                _my_ret = result.get('c2_return_3y')
                if _my_ret is not None:
                    _me_key = '__self__'
                    peer_ann_rets[_me_key] = _my_ret
                    sorted_rets = sorted(peer_ann_rets.values(), reverse=True)
                    rank_0 = sorted_rets.index(peer_ann_rets[_me_key])
                    rank_pct = rank_0 / len(sorted_rets)
                    c3_pass = rank_pct <= peer_top_pct
                    result.update({'c3_peer_rank_pct': round(rank_pct, 3), 'c3_pass': c3_pass})
                    result['criteria_count'] += 1
        except Exception:
            pass

    # ── Overall ─────────────────────────────────────────────────────────────
    passes = [result['c1_pass'], result['c2_pass'], result['c3_pass']]
    if all(p is not None for p in passes):
        result['overall_pass'] = all(passes)
    elif any(p is False for p in passes):
        result['overall_pass'] = False

    return result


def batch_333_funds(
    fund_list: list[dict],
    *,
    min_years: float = 3.0,
    target_annualized: float = 0.07,
) -> "pd.DataFrame":
    """批次評估多檔基金的 3-3-3 通過狀況（用於 Tab3 組合）。

    Parameters
    ----------
    fund_list : list of dict，每個 dict 需含：
                  code (str), name (str),
                  series (pd.Series), metrics (dict)

    Returns
    -------
    pd.DataFrame  欄位：代碼 / 名稱 / C1成立年 / C2三年年化 / C2來源 / 整體通過

    v19.306：以 code 去重（一檔一列，保留首次出現順序）。3-3-3 評估的是基金
    內在屬性（成立年 / 3 年年化 / 同儕排名），同一基金若跨多張保單在
    portfolio_funds 重複，會產生完全相同的重複列 + 灌水「共 N 檔」統計。此處
    收斂為 SSOT 一檔一列。注意：僅基金內在分析去重；組合層投入金額 / 配置需保留
    跨保單重複，故不在 portfolio_funds 源頭去重。
    """
    rows = []
    _seen_codes: set = set()  # v19.306 SSOT 去重（見 docstring）：同 code 只評一次
    for f in fund_list:
        code    = f.get('code', '')
        if code and code in _seen_codes:
            continue  # 同基金已評過，跳過重複列
        if code:
            _seen_codes.add(code)
        name    = f.get('name', '')
        series  = f.get('series')
        metrics = f.get('metrics', {})

        r = check_333_fund(series, metrics, min_years=min_years,
                           target_annualized=target_annualized)

        def _pct(v) -> str:
            return f'{v * 100:.1f}%' if v is not None else '—'

        def _icon(b) -> str:
            if b is True:   return '✅'
            if b is False:  return '❌'
            return '❓'

        rows.append({
            '代碼':       code,
            '名稱':       name[:18],
            '①成立年':   f'{r["c1_age_years"]:.1f}年' if r['c1_age_years'] else '—',
            '①通過':     _icon(r['c1_pass']),
            '②3年年化':  _pct(r['c2_return_3y']),
            '②來源':     r['c2_source'].replace('(MoneyDJ)', '').replace('（NAV，不含息）', '*') if r['c2_source'] else '—',
            '②通過':     _icon(r['c2_pass']),
            '③同儕排名': f'前{r["c3_peer_rank_pct"]*100:.0f}%' if r['c3_peer_rank_pct'] is not None else '—',
            '③通過':     _icon(r['c3_pass']),
            '整體':       _icon(r['overall_pass']),
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
