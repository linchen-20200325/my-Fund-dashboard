"""v19.198 P1-6:⑦ HWM σ + ⑧ 風險對比 + ⑨ -2σ 警示(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import BG_DARK_RED_1, GRAY_CC, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, TRAFFIC_NEUTRAL

from ui.helpers.fund_grp_health._utils import _safe_num


def _render_hwm_sigma_table(funds: list) -> None:
    """⑦ HWM σ 位階表(現價距歷史高點 + σ rank)。

    SSOT:services/precision_service.py calc_hwm_sigma_levels
    每檔 NAV 序列 → HWM / σ / current / σ_rank / label
    """
    st.divider()
    st.markdown("### 📐 HWM σ 位階")
    st.caption("HWM = 過去 252 天歷史最高 NAV;σ_rank = 現價在 HWM 下方第幾個 σ(負值)。"
               "**-2σ 以下 = 深度超跌**(若基本面健康可能是機會),**+1σ 以上 = 過熱**。")

    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception as e:
        st.caption(f"⬜ HWM σ 模組載入失敗:{type(e).__name__}: {e}")
        return

    _rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _series = _f.get("series")
        if _series is None or len(_series) < 30:
            _rows.append({
                "基金": f"{_name} ({_code})",
                "現價": "—", "HWM": "—",
                "距 HWM %": "—", "σ rank": "—",
                "位階": "⬜ NAV 不足 30 天",
            })
            continue
        _r = calc_hwm_sigma_levels(_series)
        if _r.get("error"):
            _rows.append({
                "基金": f"{_name} ({_code})",
                "現價": "—", "HWM": "—",
                "距 HWM %": "—", "σ rank": "—",
                "位階": f"⬜ {_r['error']}",
            })
            continue
        _rows.append({
            "基金": f"{_name} ({_code})",
            "現價": f"{_r['current_nav']:.2f}",
            "HWM": f"{_r['hwm']:.2f}",
            "距 HWM %": f"{_r['dist_to_hwm_pct']:+.2f}%",
            "σ rank": f"{_r['sigma_rank']:+.2f}σ",
            "位階": f"{_r.get('label', '—')}",
        })

    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
    except Exception as e:
        st.caption(f"⬜ HWM σ 表渲染失敗:{type(e).__name__}: {e}")


def _render_risk_compare_table(funds: list) -> None:
    """⑧ 風險指標對比表(σ / Sharpe / Sortino / Alpha / Beta 多檔並排)。

    資料源:MoneyDJ wb07 已抓的 risk_metrics + metrics dict(不重算)。
    缺項顯示 '—',不偽造數值(§1 Fail Loud)。
    """
    st.divider()
    st.markdown("### 📊 風險指標對比表")
    st.caption("資料源:MoneyDJ wb07 風險表(直接顯示,不重算)。**Sharpe 越高越好 / σ 越低越穩**。")

    # v19.181 Bug 3 fix: MoneyDJ wb07 risk_metrics 是 **nested** 結構
    # ({risk_table: {期間: {標準差/Sharpe/Alpha/Beta}}}),不是 flat dict;
    # 過去 `_rm.get("std_dev")` flat lookup 永遠 None,所有欄位顯示 — 。
    # 改為:metrics(本地算)優先 → wb07 risk_table 多期間 nested fallback。
    _PERIOD_KEYS = ("近一年", "一年", "近1年", "1年", "近三年", "三年", "近六月", "六個月")

    def _lookup_risk_table(rm: dict, *zh_keys: str):
        """從 risk_table 多期間找第一個非空值,zh_keys 對齊 MoneyDJ 中文欄位名。"""
        rt = (rm or {}).get("risk_table") or {}
        for _p in _PERIOD_KEYS:
            _row = rt.get(_p) or {}
            for _k in zh_keys:
                v = _row.get(_k)
                n = _safe_num(v)
                if n is not None:
                    return n
        return None

    _rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _mj = _f.get("moneydj_raw") or {}
        _m = _f.get("metrics") or {}
        _rm = _f.get("risk_metrics") or _mj.get("risk_metrics") or {}

        # σ:本地算 std_1y 優先 → wb07 risk_table["一年"]["標準差"]
        _sigma = _safe_num(_m.get("std_1y"))
        if _sigma is None:
            _sigma = _lookup_risk_table(_rm, "標準差", "年化標準差")

        # Sharpe:metrics.sharpe 優先 → wb07 risk_table["一年"]["Sharpe"]
        _sharpe = _safe_num(_m.get("sharpe"))
        if _sharpe is None:
            _sharpe = _lookup_risk_table(_rm, "Sharpe", "Sharpe Ratio", "夏普值")

        # Sortino:wb07 無此欄位,本地未算 → §1 Fail Loud,顯示 —
        _sortino = _safe_num(_m.get("sortino"))

        # Alpha / Beta:本地未算 → 只能走 wb07 nested
        _alpha = _safe_num(_m.get("alpha")) or _lookup_risk_table(_rm, "Alpha", "α")
        _beta = _safe_num(_m.get("beta")) or _lookup_risk_table(_rm, "Beta", "β")

        def _fmt(v):
            return f"{v:.2f}" if v is not None else "—"

        _rows.append({
            "基金": f"{_name} ({_code})",
            "σ (年化%)": _fmt(_sigma),
            "Sharpe": _fmt(_sharpe),
            "Sortino": _fmt(_sortino),
            "Alpha": _fmt(_alpha),
            "Beta": _fmt(_beta),
        })

    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        # 統計:有資料的基金數 / 全部
        _has_sharpe = sum(1 for r in _rows if r["Sharpe"] != "—")
        if _has_sharpe < len(_rows):
            st.caption(
                f"⬜ {len(_rows) - _has_sharpe} / {len(_rows)} 檔基金 MoneyDJ 風險表"
                f"資料不全(顯示 '—',不偽造)"
            )
    except Exception as e:
        st.caption(f"⬜ 風險表渲染失敗:{type(e).__name__}: {e}")


def _render_oversold_badges(funds: list) -> None:
    """⑨ -2σ 超跌警示 badges(深度超跌基金一覽)。

    依 HWM σ rank 篩 σ ≤ -2.0 的基金。
    深度超跌 + 基本面健康 = 抄底機會;若基本面也差 = 真實衰退,不要接刀。
    """
    st.divider()
    st.markdown("### 🩸 -2σ 超跌警示")

    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception as e:
        st.caption(f"⬜ σ 模組載入失敗:{type(e).__name__}: {e}")
        return

    _oversold = []
    for _f in funds:
        _code = _f.get("code", "?")
        _name = (_f.get("name") or _code)[:24]
        _series = _f.get("series")
        if _series is None or len(_series) < 30:
            continue
        _r = calc_hwm_sigma_levels(_series)
        if _r.get("error"):
            continue
        _sigma_rank = _r.get("sigma_rank")
        if _sigma_rank is not None and _sigma_rank <= -2.0:
            _oversold.append({
                "code": _code, "name": _name,
                "sigma_rank": _sigma_rank,
                "dist_pct": _r.get("dist_to_hwm_pct", 0),
                "current": _r.get("current_nav"),
                "hwm": _r.get("hwm"),
            })

    if not _oversold:
        st.success("✅ 目前無基金落入 -2σ 深度超跌區")
        return

    st.caption(f"⚠️ 偵測到 **{len(_oversold)} 檔基金** σ ≤ -2.0(歷史高點下方 2 個標準差以上)")
    for _o in _oversold:
        st.markdown(
            f"<div style='background:{BG_DARK_RED_1};border-left:4px solid {MATERIAL_RED};"
            f"padding:8px 14px;margin:6px 0;border-radius:6px;'>"
            f"<b style='color:#ff6b6b'>🩸 {_o['name']} ({_o['code']})</b><br>"
            f"<span style='color:{GRAY_CC};font-size:12px'>"
            f"現價 {_o['current']:.2f} ｜ HWM {_o['hwm']:.2f} ｜ "
            f"距高點 <b style='color:{MATERIAL_RED}'>{_o['dist_pct']:+.2f}%</b> ｜ "
            f"σ rank <b style='color:{MATERIAL_RED}'>{_o['sigma_rank']:+.2f}σ</b>"
            f"</span><br>"
            f"<span style='color:{TRAFFIC_NEUTRAL};font-size:11px'>"
            f"💡 深度超跌:若基本面(評分/吃本金/Sharpe)仍健康 → 可考慮抄底;"
            f"基本面也轉差 → 不要接刀</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ════════════════════════════════════════════════════════════════
# v19.121 P1 視覺 — MK 買賣點表 + Bollinger 可展開詳圖
# ════════════════════════════════════════════════════════════════
