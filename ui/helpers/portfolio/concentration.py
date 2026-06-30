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

from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_NEUTRAL


def _norm_name(s) -> str:
    return str(s or "").strip().upper()


def compute_lookthrough_concentration(portfolio_funds) -> dict:
    """聚合各基金 top_holdings → 單一個股穿透總曝險 + 重複持股檔數。

    穿透曝險（某股）= Σ_基金( 基金佔組合權重 × 該股佔基金% )。
    權重用 invest_twd；全缺則等權。純函式，不碰 st，便於單測。

    回傳 {top_stocks: [(disp_name, exposure_pct, fund_count)], max_exposure,
          n_with_holdings, n_funds}。
    """
    _funds = [f for f in (portfolio_funds or [])
              if isinstance(f, dict) and f.get("loaded")]
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
    return {"top_stocks": _top, "max_exposure": _max,
            "n_with_holdings": _n_with, "n_funds": len(_funds)}


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
            f"<b style='color:#c9d1d9'>{_nm[:18]}{_zh_s}</b> "
            f"{_exp_pct:.1f}%{_multi}")

    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
        f"color:#8b949e;line-height:1.7'>"
        f"🎯 <b>穿透式持股集中度</b>（{_emoji} {_lvl}）"
        f"<span style='color:#666;font-size:10px'> · 跨 {_r['n_with_holdings']} 檔基金"
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
    _funds = [f for f in (portfolio_funds or [])
              if isinstance(f, dict) and f.get("loaded")]
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
            f"<b style='color:#c9d1d9'>{_nm[:14]}</b> "
            f"{_exp_pct:.1f}%{_multi}")

    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
        f"color:#8b949e;line-height:1.7'>"
        f"🏭 <b>穿透式產業集中度</b>（{_emoji} {_lvl}）"
        f"<span style='color:#666;font-size:10px'> · 跨 {_r['n_with_sectors']} 檔基金"
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
