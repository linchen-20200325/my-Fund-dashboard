"""v19.66 I3：組合穿透式持股集中度（look-through concentration）。

聚合組合各基金的 top_holdings，算「你的組合實際上 X% 押在某個股
（跨 N 檔基金）」，與 Tab3 下方 T5 兩兩基金重疊度互補：
  - T5：說「基金 A 與 B 持股 70% 相似」（pairwise）
  - I3：說「你的組合實際 12% 集中在 NVIDIA（跨 3 檔）」（look-through）

純函式 + 純顯示，零新 IO（吃 moneydj_raw 已載入的 holdings）。
屬「跨 Tab / 跨區塊 訊號聯動」系列（I1 總經→組合、I2 單檔↔組合、I3 集中度）。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import GH_BG_PRIMARY, GH_FG_MUTED, GH_FG_SECONDARY, GRAY_66, TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW


def _norm_name(s) -> str:
    return str(s or "").strip().upper()


def _safe_pct(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def lookthrough_coverage(portfolio_funds) -> dict:
    """v19.458 深度強化④:穿透成分的**時效 + 覆蓋率**(§1 Fail-Loud)。

    - coverage_pct:各檔已揭露 top_holdings Σpct 的 **invest_twd 加權平均**(基金常只公布前 10 大
      → 覆蓋 40~60% 很常見)。覆蓋不足 → 穿透曝險是**下限**,未覆蓋部分未知。
    - as_of:各檔 `holdings.fetched_at` **最舊**者(誠實:這是『資料抓取時間』,非基金揭露基準日)。
    - is_stale:as_of 舊於 `LOOKTHROUGH_STALE_DAYS` → 標「落後推估下限」。
    回 {coverage_pct, as_of, is_stale, n_with_holdings, note}。無成分 → coverage_pct=None。
    """
    import pandas as pd

    from shared.signal_thresholds import LOOKTHROUGH_COVERAGE_MIN, LOOKTHROUGH_STALE_DAYS
    from ui.helpers.session import usable_funds
    _funds = usable_funds(portfolio_funds)
    _rows = []                                   # (invest_twd, coverage_frac, fetched_at)
    for _f in _funds:
        _h = ((_f.get("moneydj_raw") or {}).get("holdings") or {})
        _tops = _h.get("top_holdings") or []
        if not _tops:
            continue
        _cov = sum(_safe_pct(_t.get("pct")) for _t in _tops if isinstance(_t, dict)) / 100.0
        _cov = min(max(_cov, 0.0), 1.0)          # 揭露 pct 理論 ≤ 100%,容錯封頂/地板
        _rows.append((float(_f.get("invest_twd", 0) or 0), _cov, _h.get("fetched_at")))
    if not _rows:
        return {"coverage_pct": None, "as_of": None, "is_stale": None,
                "n_with_holdings": 0, "note": "無穿透成分資料"}

    _tot = sum(r[0] for r in _rows)
    _cov_w = (sum(r[0] * r[1] for r in _rows) / _tot if _tot > 0
              else sum(r[1] for r in _rows) / len(_rows))     # 無金額 → 等權 fallback
    _dates = [pd.to_datetime(r[2], errors="coerce", utc=True) for r in _rows if r[2]]
    _dates = [d for d in _dates if pd.notna(d)]
    _as_of = min(_dates) if _dates else None
    _stale, _age = None, None
    if _as_of is not None:
        _age = int((pd.Timestamp.now(tz="UTC") - _as_of).days)
        _stale = _age > LOOKTHROUGH_STALE_DAYS
    _note = None
    if _stale:
        _note = f"成分資料已 {_age} 天未更新(> {LOOKTHROUGH_STALE_DAYS}d)→ 穿透曝險為『落後推估下限』"
    elif _cov_w < LOOKTHROUGH_COVERAGE_MIN:
        _note = f"僅揭露前 N 大(加權覆蓋 {_cov_w * 100:.0f}%)→ 曝險為下限,未覆蓋部分未知"
    return {"coverage_pct": round(_cov_w * 100.0, 1),
            "as_of": (_as_of.date().isoformat() if _as_of is not None else None),
            "is_stale": _stale, "n_with_holdings": len(_rows), "note": _note}


def compute_lookthrough_concentration(portfolio_funds) -> dict:
    """聚合各基金 top_holdings → 單一個股穿透總曝險 + 重複持股檔數。

    穿透曝險（某股）= Σ_基金( 基金佔組合權重 × 該股佔基金% )。
    權重用 invest_twd；全缺則等權。純函式，不碰 st，便於單測。

    回傳 {top_stocks: [(disp_name, exposure_pct, fund_count)], max_exposure,
          n_with_holdings, n_funds}。
    """
    # 稽核 E2:原為 `f.get("loaded")` —— 抓失敗的基金也是 loaded=True。
    # 它們沒有 holdings,會被算進分母 `n_funds` 卻不進分子 → **集中度被低估**,
    # 而集中度低估正是這個函式最不該犯的錯(它存在的理由就是示警)。
    # 走 SSOT 判定;`ui.helpers.session` 不 import streamlit,本檔仍是純函式。
    from ui.helpers.session import usable_funds as _usable_funds_conc
    _funds = _usable_funds_conc(portfolio_funds)
    _hold_funds = []
    for _f in _funds:
        _tops = (((_f.get("moneydj_raw") or {}).get("holdings") or {})
                 .get("top_holdings") or [])
        if _tops:
            _hold_funds.append((_f, _tops))
    _n_with = len(_hold_funds)
    if not _hold_funds:
        return {"top_stocks": [], "max_exposure": 0.0,
                "n_with_holdings": 0, "n_funds": len(_funds)}

    _total_inv = sum(float(_f.get("invest_twd", 0) or 0) for _f, _ in _hold_funds)
    _use_equal = _total_inv <= 0

    _exp: dict = {}    # norm_name → 穿透曝險 (fraction)
    _disp: dict = {}   # norm_name → 顯示名
    _cnt: dict = {}    # norm_name → 出現的基金檔數
    for _f, _tops in _hold_funds:
        if _use_equal:
            _w = 1.0 / _n_with
        else:
            _w = float(_f.get("invest_twd", 0) or 0) / _total_inv
        _seen_in_fund: set = set()
        for _t in _tops:
            if not isinstance(_t, dict):
                continue
            _nm = _norm_name(_t.get("name"))
            if not _nm:
                continue
            try:
                _pct = float(_t.get("pct", 0) or 0)
            except (TypeError, ValueError):
                _pct = 0.0
            _exp[_nm] = _exp.get(_nm, 0.0) + _w * (_pct / 100.0)
            _disp.setdefault(_nm, str(_t.get("name", "")).strip())
            if _nm not in _seen_in_fund:
                _cnt[_nm] = _cnt.get(_nm, 0) + 1
                _seen_in_fund.add(_nm)

    _ranked = sorted(_exp.items(), key=lambda kv: kv[1], reverse=True)
    _top = [(_disp.get(_k, _k), _v * 100.0, _cnt.get(_k, 1)) for _k, _v in _ranked[:5]]
    _max = _top[0][1] if _top else 0.0
    # v19.458 ④:附上時效 + 覆蓋率(§1 資料過期 → 標「落後推估下限」);additive,舊 caller 無視新鍵
    _cov = lookthrough_coverage(portfolio_funds)
    return {"top_stocks": _top, "max_exposure": _max,
            "n_with_holdings": _n_with, "n_funds": len(_funds),
            "coverage_pct": _cov["coverage_pct"], "as_of": _cov["as_of"],
            "is_stale": _cov["is_stale"], "coverage_note": _cov["note"]}


def render_concentration_summary(portfolio_funds) -> None:
    """渲染穿透式持股集中度摘要 banner（純顯示，零副作用，零新 IO）。"""
    _r = compute_lookthrough_concentration(portfolio_funds)
    _top = _r["top_stocks"]
    if not _top:
        return  # 無持股穿透資料 → 靜默不洗版

    _max = _r["max_exposure"]
    if _max >= 10:
        _emoji, _border, _lvl = "🔴", TRAFFIC_RED, "高度集中"
    elif _max >= 6:
        _emoji, _border, _lvl = "🟠", TRAFFIC_YELLOW, "偏集中"
    else:
        _emoji, _border, _lvl = "🟢", TRAFFIC_GREEN, "相對分散"

    try:
        from ui.helpers.holdings import _zh_holding
    except Exception:
        def _zh_holding(_n):  # type: ignore
            return ""

    _items = []
    for _nm, _exp_pct, _fc in _top:
        _zh = _zh_holding(_nm)
        _zh_s = f"({_zh})" if _zh else ""
        _multi = f" <span style='color:{TRAFFIC_NEUTRAL}'>·{_fc}檔</span>" if _fc >= 2 else ""
        _items.append(
            f"<b style='color:{GH_FG_SECONDARY}'>{_nm[:18]}{_zh_s}</b> "
            f"{_exp_pct:.1f}%{_multi}")

    st.markdown(
        f"<div style='background:{GH_BG_PRIMARY};border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
        f"color:{GH_FG_MUTED};line-height:1.7'>"
        f"🎯 <b>穿透式持股集中度</b>（{_emoji} {_lvl}）"
        f"<span style='color:{GRAY_66};font-size:10px'> · 跨 {_r['n_with_holdings']} 檔基金"
        f"看你實際押在哪些個股</span><br/>"
        f"{' ｜ '.join(_items)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if _max >= 10:
        st.caption(
            f"🔴 最大單一個股穿透曝險 {_max:.1f}% — 多檔基金重押同股，"
            f"分散效果打折；兩兩基金重疊度詳見下方「④ 持股重疊度診斷」"
        )


def compute_lookthrough_sectors(portfolio_funds) -> dict:
    """v19.74 I7：聚合各基金 sector_alloc → 穿透 sector 總曝險。

    與 compute_lookthrough_concentration 對稱：個股集中度看「重押哪檔股票」，
    sector 集中度看「重押哪個產業」。同一加權邏輯（基金佔組合權重 × sector 佔基金%）。

    回傳 {top_sectors: [(disp_name, exposure_pct, fund_count)], max_exposure,
          n_with_sectors, n_funds}。
    """
    # 稽核 E2:原為 `f.get("loaded")` —— 抓失敗的基金也是 loaded=True。
    # 它們沒有 holdings,會被算進分母 `n_funds` 卻不進分子 → **集中度被低估**,
    # 而集中度低估正是這個函式最不該犯的錯(它存在的理由就是示警)。
    # 走 SSOT 判定;`ui.helpers.session` 不 import streamlit,本檔仍是純函式。
    from ui.helpers.session import usable_funds as _usable_funds_conc
    _funds = _usable_funds_conc(portfolio_funds)
    _sec_funds = []
    for _f in _funds:
        _secs = (((_f.get("moneydj_raw") or {}).get("holdings") or {})
                 .get("sector_alloc") or [])
        if _secs:
            _sec_funds.append((_f, _secs))
    _n_with = len(_sec_funds)
    if not _sec_funds:
        return {"top_sectors": [], "max_exposure": 0.0,
                "n_with_sectors": 0, "n_funds": len(_funds)}

    _total_inv = sum(float(_f.get("invest_twd", 0) or 0) for _f, _ in _sec_funds)
    _use_equal = _total_inv <= 0

    _exp: dict = {}    # norm_name → 穿透曝險 (fraction)
    _disp: dict = {}   # norm_name → 顯示名（保留原大小寫）
    _cnt: dict = {}    # norm_name → 出現的基金檔數
    for _f, _secs in _sec_funds:
        _w = (1.0 / _n_with) if _use_equal else (
            float(_f.get("invest_twd", 0) or 0) / _total_inv
        )
        _seen_in_fund: set = set()
        for _s in _secs:
            if not isinstance(_s, dict):
                continue
            _nm = _norm_name(_s.get("name"))
            if not _nm:
                continue
            try:
                _pct = float(_s.get("pct", 0) or 0)
            except (TypeError, ValueError):
                _pct = 0.0
            _exp[_nm] = _exp.get(_nm, 0.0) + _w * (_pct / 100.0)
            _disp.setdefault(_nm, str(_s.get("name", "")).strip())
            if _nm not in _seen_in_fund:
                _cnt[_nm] = _cnt.get(_nm, 0) + 1
                _seen_in_fund.add(_nm)

    _ranked = sorted(_exp.items(), key=lambda kv: kv[1], reverse=True)
    _top = [(_disp.get(_k, _k), _v * 100.0, _cnt.get(_k, 1)) for _k, _v in _ranked[:5]]
    _max = _top[0][1] if _top else 0.0
    return {"top_sectors": _top, "max_exposure": _max,
            "n_with_sectors": _n_with, "n_funds": len(_funds)}


def render_sector_concentration_summary(portfolio_funds) -> None:
    """v19.74 I7：渲染穿透式 sector 集中度 banner。

    閾值較個股集中度寬鬆（單一 sector 自然比單一 stock 高）：
      🔴 ≥30% 高度集中 / 🟠 ≥20% 偏集中 / 🟢 <20% 相對分散
    """
    _r = compute_lookthrough_sectors(portfolio_funds)
    _top = _r["top_sectors"]
    if not _top:
        return  # 無 sector 穿透資料 → 靜默不洗版

    _max = _r["max_exposure"]
    if _max >= 30:
        _emoji, _border, _lvl = "🔴", TRAFFIC_RED, "高度集中"
    elif _max >= 20:
        _emoji, _border, _lvl = "🟠", TRAFFIC_YELLOW, "偏集中"
    else:
        _emoji, _border, _lvl = "🟢", TRAFFIC_GREEN, "相對分散"

    _items = []
    for _nm, _exp_pct, _fc in _top:
        _multi = f" <span style='color:{TRAFFIC_NEUTRAL}'>·{_fc}檔</span>" if _fc >= 2 else ""
        _items.append(
            f"<b style='color:{GH_FG_SECONDARY}'>{_nm[:14]}</b> "
            f"{_exp_pct:.1f}%{_multi}")

    st.markdown(
        f"<div style='background:{GH_BG_PRIMARY};border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
        f"color:{GH_FG_MUTED};line-height:1.7'>"
        f"🏭 <b>穿透式產業集中度</b>（{_emoji} {_lvl}）"
        f"<span style='color:{GRAY_66};font-size:10px'> · 跨 {_r['n_with_sectors']} 檔基金"
        f"看你實際押在哪些產業</span><br/>"
        f"{' ｜ '.join(_items)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if _max >= 30:
        st.caption(
            f"🔴 最大單一產業穿透曝險 {_max:.1f}% — 組合對該產業循環敏感度高，"
            f"建議檢查是否要增加跨產業多元化"
        )
