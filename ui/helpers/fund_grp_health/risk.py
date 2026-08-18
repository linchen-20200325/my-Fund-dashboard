"""v19.198 P1-6:⑦ HWM σ + ⑧ 風險對比 + ⑨ -2σ 警示(從 fund_grp_health_extras 主檔抽出)。"""
from __future__ import annotations

import streamlit as st

from shared.colors import BG_DARK_RED_1, GRAY_CC, MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED, TRAFFIC_NEUTRAL

from ui.helpers.fund_grp_health._utils import _safe_num


def hwm_sigma_by_code(funds: list) -> dict:
    """⑦ HWM σ 逐檔欄位(keyed by code)。供「健診總表」合併 + 標準表共用(單一資料源)。

    SSOT:services/precision_service.py calc_hwm_sigma_levels。缺資料 → '—'(§1 不偽造)。
    """
    out: dict = {}
    try:
        from services.precision_service import calc_hwm_sigma_levels
    except Exception as _e_imp:  # noqa: BLE001 — 模組載入失敗 → 全檔缺值,不炸
        # 原本靜默:整組 σ/HWM 5 欄一起消失,user 只看到大表少了一整區,以為功能壞了。
        # 補 log + 讓「HWM 位階」欄自己說出是**載入失敗**,不是這些基金沒資料(§1)。
        import sys as _sys_imp
        print(f"[grp_health/risk] precision_service 載入失敗,σ/HWM 欄全缺:"
              f"{type(_e_imp).__name__}: {_e_imp}", file=_sys_imp.stderr)
        _err = f"⬜ σ 模組載入失敗({type(_e_imp).__name__})"
        return {(_f.get("code") or "?"): {
            "現價": "—", "HWM": "—", "距 HWM %": "—", "σ rank": "—", "HWM 位階": _err,
        } for _f in funds}
    for _f in funds:
        _code = _f.get("code", "?")
        _series = _f.get("series")
        _blank = {"現價": "—", "HWM": "—", "距 HWM %": "—", "σ rank": "—"}
        if _series is None or len(_series) < 30:
            out[_code] = {**_blank, "HWM 位階": "⬜ NAV 不足 30 天"}
            continue
        _r = calc_hwm_sigma_levels(_series)
        if _r.get("error"):
            out[_code] = {**_blank, "HWM 位階": f"⬜ {_r['error']}"}
            continue
        out[_code] = {
            "現價": f"{_r['current_nav']:.2f}",
            "HWM": f"{_r['hwm']:.2f}",
            "距 HWM %": f"{_r['dist_to_hwm_pct']:+.2f}%",
            "σ rank": f"{_r['sigma_rank']:+.2f}σ",
            "HWM 位階": f"{_r.get('label', '—')}",
        }
    return out


def _render_hwm_sigma_table(funds: list) -> None:
    """⑦ HWM σ 位階表(獨立版,保留供直接呼叫 / 測試;主流程已併入健診總表)。"""
    st.divider()
    st.markdown("### 📐 HWM σ 位階")
    st.caption("HWM = 過去 252 天歷史最高 NAV;σ_rank = 現價在 HWM 下方第幾個 σ(負值)。"
               "**-2σ 以下 = 深度超跌**(若基本面健康可能是機會),**+1σ 以上 = 過熱**。")
    _data = hwm_sigma_by_code(funds)
    _rows = [
        {"基金": f"{(_f.get('name') or _f.get('code', '?'))[:24]} ({_f.get('code', '?')})",
         **_data.get(_f.get("code", "?"), {})}
        for _f in funds
    ]
    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
    except Exception as e:  # noqa: BLE001
        st.caption(f"⬜ HWM σ 表渲染失敗:{type(e).__name__}: {e}")


# v19.181 Bug 3 fix: MoneyDJ wb07 risk_metrics 是 **nested** 結構
# ({risk_table: {期間: {標準差/Sharpe/Alpha/Beta}}}),不是 flat dict。
_PERIOD_KEYS = ("近一年", "一年", "近1年", "1年", "近三年", "三年", "近六月", "六個月")


def _lookup_risk_table(rm: dict, *zh_keys: str):
    """從 risk_table 多期間找第一個非空值,zh_keys 對齊 MoneyDJ 中文欄位名。"""
    rt = (rm or {}).get("risk_table") or {}
    for _p in _PERIOD_KEYS:
        _row = rt.get(_p) or {}
        for _k in zh_keys:
            n = _safe_num(_row.get(_k))
            if n is not None:
                return n
    return None


def _local_first(local, rm: dict, *zh_keys):
    """本地 metrics 值優先,**只有真的缺(None)** 才退到 MoneyDJ wb07 風險表。

    §1:不用 `a or b` —— 0.0 是 falsy 但為合法值(Sharpe / Alpha 恰好 0)。
    """
    _v = _safe_num(local)
    return _v if _v is not None else _lookup_risk_table(rm, *zh_keys)


def risk_compare_by_code(funds: list) -> dict:
    """⑧ 風險指標逐檔欄位(keyed by code):σ / Sharpe / Sortino / Alpha / Beta。

    資料源:metrics(本地算)優先 → MoneyDJ wb07 risk_table nested fallback。
    缺項 '—',不偽造(§1)。供健診總表合併 + 標準表共用(單一資料源)。
    """
    def _fmt(v):
        return f"{v:.2f}" if v is not None else "—"

    out: dict = {}
    for _f in funds:
        _code = _f.get("code", "?")
        _mj = _f.get("moneydj_raw") or {}
        _m = _f.get("metrics") or {}
        _rm = _f.get("risk_metrics") or _mj.get("risk_metrics") or {}

        # §1:`a or b` 會把**合法的 0.0** 誤當缺值退到 fallback ——
        # Sharpe / Alpha 恰好 0.00(報酬等於無風險利率 / 零超額)是真實可能值,
        # 用 `or` 會改抓 MoneyDJ wb07 另一個期間的數字,兩個來源在同一格悄悄互換。
        # `_local_first` 改用顯式 `is None` 判斷,0.0 保留為 0.0。
        _sigma = _local_first(_m.get("std_1y"), _rm, "標準差", "年化標準差")
        _sharpe = _local_first(_m.get("sharpe"), _rm, "Sharpe", "Sharpe Ratio", "夏普值")
        _sortino = _safe_num(_m.get("sortino"))  # wb07 無此欄,本地未算 → —
        _alpha = _local_first(_m.get("alpha"), _rm, "Alpha", "α")
        _beta = _local_first(_m.get("beta"), _rm, "Beta", "β")

        out[_code] = {
            "σ (年化%)": _fmt(_sigma), "Sharpe": _fmt(_sharpe),
            "Sortino": _fmt(_sortino), "Alpha": _fmt(_alpha), "Beta": _fmt(_beta),
        }
    return out


def _render_risk_compare_table(funds: list) -> None:
    """⑧ 風險指標對比表(獨立版,保留供直接呼叫 / 測試;主流程已併入健診總表)。"""
    st.divider()
    st.markdown("### 📊 風險指標對比表")
    st.caption("資料源:MoneyDJ wb07 風險表(直接顯示,不重算)。**Sharpe 越高越好 / σ 越低越穩**。")
    _data = risk_compare_by_code(funds)
    _rows = [
        {"基金": f"{(_f.get('name') or _f.get('code', '?'))[:24]} ({_f.get('code', '?')})",
         **_data.get(_f.get("code", "?"), {})}
        for _f in funds
    ]
    try:
        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
        _has_sharpe = sum(1 for r in _rows if r.get("Sharpe", "—") != "—")
        if _has_sharpe < len(_rows):
            st.caption(f"⬜ {len(_rows) - _has_sharpe} / {len(_rows)} 檔基金 MoneyDJ 風險表"
                       f"資料不全(顯示 '—',不偽造)")
    except Exception as e:  # noqa: BLE001
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
# v19.121 P1 視覺 — 買賣點表 + Bollinger 可展開詳圖
# ════════════════════════════════════════════════════════════════
