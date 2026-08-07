"""services/fund_screening.py — 基金品質篩選（L2 純計算）

職責（單一）：提供基金篩選純函式（MK 3-3-3 原則 + 低基期進場點）；
無 I/O、無 Streamlit。

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
        _today = pd.Timestamp.now('UTC').tz_localize(None).normalize()
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

    today = pd.Timestamp.now('UTC').tz_localize(None).normalize()

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


# ════════════════════════════════════════════════════════════════════════
# 低基期進場點篩選（「🎯 選基金」清單）
# ════════════════════════════════════════════════════════════════════════
# 2026-08-07 user 拍板：**低基期全站統一用 HWM σ rank**（健診大表「基期」欄那把尺）。
#
# 原本這裡是另一套演算法（`高點 − N×NAV 標準差`，深度取**正數**、倍數由使用者選
# 1 或 2σ、回看期可選 1/2/3 年），與大表的 σ rank（**負數**、報酬率標準差換算、
# 門檻固定 `ROTATION_BUY_SIGMA`）互相獨立 —— 同一檔可能在這裡標「✅ 低基期」、
# 在大表標「⚪ 中性」，使用者照這裡買進，回頭卻看到系統自己說不是低基期。
#
# 統一後的口徑（§4.1 σ sign convention：**一律負數，愈負愈低基期**）：
#   σ rank = (現價 − 期間 HWM) / σ_abs      ← services/precision_service.calc_hwm_sigma_levels
#   低基期 ⇔ σ rank ≤ ROTATION_BUY_SIGMA    ← services/rotation.classify_base
# 兩邊呼叫同一組函式 + 同一組 shared/signal_thresholds 常數，**不可能再分歧**。
LOW_BASE_LOOKBACK_DEFAULT = 252   # 回看窗（交易日，1Y ≈ 252，非 365 日曆日）
# ⚠️ 必須等於 `calc_hwm_sigma_levels` 的 lookback 預設值 —— 大表走預設、本模組顯式
# 傳入，兩者不同就會讓同一檔在兩處算出不同的 σ rank（σ_abs 隨 √n 縮放）。
# 漂移由 tests/test_fund_screener_low_base.py 的 inspect 漂移鎖守住。
LOW_BASE_MIN_POINTS = 60          # 可信度門檻：低於此樣本數 → reliable=False

# 基期狀態 → 給 UI 的說明字串（label 本身由 L3 決定，這裡只給中性描述）
_BASE_NOTE = {
    "low": "低基期（σ rank ≤ 買點門檻）",
    "mid": "中性（介於買賣門檻之間）",
    "high": "高基期（貼近期間高點）",
    "unknown": "資料不足，無法定位階",
}


def compute_base_state(
    nav_series: "pd.Series | None",
    *,
    lookback: int = LOW_BASE_LOOKBACK_DEFAULT,
    min_points: int = LOW_BASE_MIN_POINTS,
    buy_sigma: "float | None" = None,
    sell_sigma: "float | None" = None,
) -> dict:
    """基期定位（純計算）—— **與健診大表「基期」欄同一把尺**。

    數學式（σ sign convention 見 §4.1：**負值愈深愈低基期**）:
        s        = nav_series 最後 lookback 筆（升序、去 NaN）
        HWM      = s.max()
        σ_abs    = HWM × std(日報酬率) × √len(s)
        σ rank   = (現價 − HWM) / σ_abs          ≤ 0（現價必在窗內高點之下）
        低基期  ⇔ σ rank ≤ buy_sigma（預設 ROTATION_BUY_SIGMA = −1.5）
        高基期  ⇔ σ rank ≥ sell_sigma（預設 ROTATION_SELL_SIGMA = −0.5）

    σ rank 與分類皆**不自行實作**：值走 `services.precision_service.calc_hwm_sigma_levels`
    （大表同一支），切點走 `services.rotation.classify_base` + `shared.signal_thresholds`
    常數（§3.3 不 inline magic）。本函式只負責 NAV 前處理 + 樣本數揭露 + 打包。

    §1 Fail Loud 邊界（**停售 / 清算基金絕不可被推薦**）:
      - NAV 不足 30 筆 / 報酬率序列不足 / **σ_abs ≈ 0（NAV 完全不動）**
        → `calc_hwm_sigma_levels` 回 `{"error": ...}` → 本函式回
        `base="unknown"` / `is_low_base=None` / `sigma_rank=None`，
        原因原字轉載到 `note`。停售基金 NAV 長期不動正是 σ≈0 的典型，
        絕不會落進 "low" → `screen_funds(only_low_base=True)` 一定濾掉它。
      - len(s) < min_points → reliable=False（仍給值但標「可信度低」）

    Parameters
    ----------
    nav_series : pd.Series  NAV 序列，index=DatetimeIndex，values=float（>0）
    lookback   : int        回看窗（交易日數）；**必須與大表一致**，見常數註解
    min_points : int        可信度門檻樣本數
    buy_sigma / sell_sigma  : float | None  None → 走 shared/signal_thresholds SSOT

    Returns
    -------
    dict:
        sigma_rank        : float | None  現價在 HWM 下方第幾個 σ（**負數**）
        base              : "low" / "mid" / "high" / "unknown"
        is_low_base       : bool | None   (None = 無法定位階)
        hwm / current / dist_to_hwm_pct : float | None
        buy_threshold_nav : float | None  σ rank 剛好等於 buy_sigma 的 NAV 價位
        hwm_label         : str           precision_service 的 4 級位階標籤
        n_points          : int           實際採用的樣本數
        reliable          : bool          n_points ≥ min_points
        note              : str           狀態說明（供 UI 顯示）
        buy_sigma / sell_sigma : float    本次實際採用的門檻（揭露，不讓 UI 自己猜）
    """
    from shared.signal_thresholds import ROTATION_BUY_SIGMA, ROTATION_SELL_SIGMA
    _buy = float(ROTATION_BUY_SIGMA if buy_sigma is None else buy_sigma)
    _sell = float(ROTATION_SELL_SIGMA if sell_sigma is None else sell_sigma)

    out: dict = {
        "sigma_rank": None, "base": "unknown", "is_low_base": None,
        "hwm": None, "current": None, "dist_to_hwm_pct": None,
        "buy_threshold_nav": None, "hwm_label": "—",
        "n_points": 0, "reliable": False, "note": "",
        "buy_sigma": _buy, "sell_sigma": _sell,
    }

    if nav_series is None:
        out["note"] = "無 NAV"
        return out
    s = nav_series
    if isinstance(s, pd.DataFrame):
        s = s.squeeze()
    if not hasattr(s, "dropna"):
        out["note"] = "NAV 型別非序列"
        return out
    s = s.dropna().sort_index()
    # tz-naive（與檔內其他函式一致）
    if hasattr(s.index, "tz") and s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    if len(s) == 0:
        out["note"] = "NAV 全空"
        return out

    s = s.tail(int(lookback))
    n = len(s)
    out["n_points"] = n
    out["reliable"] = n >= int(min_points)

    from services.precision_service import calc_hwm_sigma_levels
    from services.rotation import classify_base

    _r = calc_hwm_sigma_levels(s, lookback=int(lookback))
    if _r.get("error"):
        # 停售 / 剛成立 / NAV 不動 → 誠實不判定（§1），note 保留上游原因字樣
        out["note"] = str(_r["error"])
        return out

    _hwm = _r.get("hwm")
    _sigma_abs = _r.get("sigma_abs")
    out["sigma_rank"] = _r.get("sigma_rank")
    out["hwm"] = _hwm
    out["current"] = _r.get("current_nav")
    out["dist_to_hwm_pct"] = _r.get("dist_to_hwm_pct")
    out["hwm_label"] = _r.get("label") or "—"
    if _hwm is not None and _sigma_abs:
        # buy_sigma 是**負數**：用加法保持符號一致，不寫 `hwm − |buy|×σ`，
        # 否則有人把常數改成正數時整條線會靜默反向（§4.1）。
        out["buy_threshold_nav"] = round(_hwm + _buy * _sigma_abs, 4)

    _base = classify_base(out["sigma_rank"], _sell, _buy)
    out["base"] = _base
    out["is_low_base"] = None if _base == "unknown" else (_base == "low")
    if not out["reliable"]:
        out["note"] = f"樣本僅 {n} 筆（<{min_points}），可信度低"
    else:
        out["note"] = _BASE_NOTE.get(_base, "")
    return out


def screen_funds(
    items: list[dict],
    *,
    lookback: int = LOW_BASE_LOOKBACK_DEFAULT,
    min_points: int = LOW_BASE_MIN_POINTS,
    only_low_base: bool = True,
    only_no_eat: bool = True,
    currencies: "set[str] | None" = None,
    categories: "set[str] | None" = None,
    buy_sigma: "float | None" = None,
    sell_sigma: "float | None" = None,
) -> list[dict]:
    """「選基金清單」：對已載入基金套低基期 + 不吃本金 + 幣別/類別濾鏡（純函式）。

    Parameters
    ----------
    items : list of dict，每檔需含（缺欄位以 None/"" 容錯）:
        code (str), name (str), series (pd.Series NAV),
        currency (str), category (str),
        eats_principal (bool | None)   # True=吃本金 / False=不吃 / None=未知
    lookback / min_points / buy_sigma / sell_sigma : 傳入 compute_base_state
    only_low_base : True → 僅保留 `base == "low"`（**無法定位階者一併排除** ——
                    停售 / NAV 不動的基金 σ rank 為 None，不得混進進場候選，§1）
    only_no_eat   : True → 僅保留 eats_principal 明確為 False（不吃本金）
    currencies    : None=全部；否則僅保留 currency ∈ 此集合
    categories    : None=全部；否則僅保留 category ∈ 此集合

    Returns
    -------
    list[dict]（依 **σ rank 由負至正**排序 = 跌最深的在最前，無法定位階者排最後）：
    每列含 code / name / currency / category / eats_principal +
    compute_base_state 全欄位。**去重同 code**（一檔一列）。
    """
    rows: list[dict] = []
    seen: set = set()
    for it in items:
        code = str(it.get("code", "") or "").strip()
        if code and code in seen:
            continue
        if code:
            seen.add(code)

        ccy = str(it.get("currency", "") or "").strip()
        cat = str(it.get("category", "") or "").strip()
        eats = it.get("eats_principal", None)

        # 濾鏡（基期以外的先擋，省 compute）
        if currencies is not None and ccy not in currencies:
            continue
        if categories is not None and cat not in categories:
            continue
        if only_no_eat and eats is not False:  # 僅保留「明確不吃本金」
            continue

        lb = compute_base_state(
            it.get("series"), lookback=lookback, min_points=min_points,
            buy_sigma=buy_sigma, sell_sigma=sell_sigma,
        )
        if only_low_base and lb.get("base") != "low":
            continue

        rows.append({
            "code": code, "name": str(it.get("name", "") or ""),
            "currency": ccy, "category": cat, "eats_principal": eats,
            **lb,
        })

    # σ rank 遞增（愈負 = 跌愈深 = 排愈前）；None（無法定位階）一律排最後
    rows.sort(key=lambda r: (r.get("sigma_rank") is None,
                             r.get("sigma_rank") if r.get("sigma_rank") is not None else 0.0))
    return rows
