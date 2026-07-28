"""ui/helpers/fund_grp_health/rotation.py — 🔄 輪動配對建議表(v19.415)。

賣「高基期」→ 買「低基期 + 體質健康」的**同類**基金,賺均值回歸差價。組每檔資料:
`build_merged_extra_columns`(σ rank / 距 HWM % / 操盤評分)+ `build_health_analysis_row`
(基金類別 / 4D Grade)+ `check_eating_principal_1y_mk`(吃本金)→ `services.rotation`。

L3 orchestrator → L2(rotation / health.report / health.dividend)+ L3(unified),全下行。
"""
from __future__ import annotations

import streamlit as st


def _assemble_rows(funds: list) -> list:
    """每檔組成 suggest_rotation_pairs 需要的欄位 dict。"""
    from services.health.report import build_health_analysis_row
    from ui.helpers.fund_grp_health.unified import build_merged_extra_columns

    _pi = st.session_state.get("phase_info") if hasattr(st, "session_state") else None
    _, _extra = build_merged_extra_columns(
        funds, (_pi or {}).get("phase") or "", (_pi or {}).get("score"))

    rows = []
    for _f in funds:
        _code = _f.get("code", "?")
        _fd = _f.get("moneydj_raw") or _f
        try:
            _h = build_health_analysis_row(_fd, _code)
        except Exception:  # noqa: BLE001
            _h = {}
        try:
            from services.health.dividend import check_eating_principal_1y_mk
            _eat = (check_eating_principal_1y_mk(_fd) or {}).get("status", "")
        except Exception:  # noqa: BLE001
            _eat = ""
        _e = _extra.get(_code, {})
        rows.append({
            "code": _code, "name": _f.get("name") or _code,
            "基金類別": _h.get("基金類別"), "4D Grade": _h.get("4D Grade"),
            "σ rank": _e.get("σ rank"), "距 HWM %": _e.get("距 HWM %"),
            "操盤評分": _e.get("操盤評分"), "吃本金燈號": _eat,
        })
    return rows


def render_rotation_section(funds: list) -> None:
    """🔄 輪動配對建議表 —— 賣高基期、買同類低基期健康標的。"""
    if not funds or len(funds) < 2:
        return
    from services.rotation import suggest_rotation_pairs

    st.divider()
    st.markdown("### 🔄 輪動配對建議(賣高基期 → 買**別類**低基期健康)")
    st.caption("跨產業/性質輪動:賣掉貼近高點的基金,換進**不同類別**、深跌但體質健康的基金"
               "(分散 + 賺回歸差價)。⚠️ 低基期**不一定**回漲 —— 買方已過濾"
               "(4D∈A/B/C + 非吃本金 + 操盤評分達標)避免接刀。")

    c1, c2, c3 = st.columns(3)
    _sell = c1.slider("高基期門檻(σ rank ≥)", -2.0, 0.5, -0.5, 0.1, key="rot_sell",
                      help="現價貼近高點幾 σ 內算高基期(賣方候選)")
    _buy = c2.slider("低基期門檻(σ rank ≤)", -3.0, -0.5, -1.5, 0.1, key="rot_buy",
                     help="跌破高點幾 σ 算低基期(買方候選)")
    _minsc = c3.slider("買方操盤評分 ≥", 0, 100, 50, 5, key="rot_score",
                       help="買方經理人操盤評分門檻(避免換進操作差的)")

    try:
        _pairs = suggest_rotation_pairs(_assemble_rows(funds),
                                        sell_sigma=_sell, buy_sigma=_buy, min_score=float(_minsc))
    except Exception as e:  # noqa: BLE001
        st.caption(f"⬜ 輪動配對計算失敗:[{type(e).__name__}] {str(e)[:80]}")
        return

    if not _pairs:
        st.info("目前無「高基期」持有基金 —— 沒有需要輪動賣出的標的(可放寬高基期門檻 σ)。")
        return

    import pandas as pd
    _disp = [{
        "賣出(高基期)": f"{p['sell_name']} ({p['sell_code']})",
        "賣方類別": p["sell_cat"] or "—",
        "賣方 σ": p["sell_sigma"],
        "建議換進(別類低基期健康)": (f"{p['buy_name']} ({p['buy_code']})"
                                     if p["buy_code"] else "⚪ 無不同類健康低基期標的"),
        "買方類別": p.get("buy_cat") or "—",
        "買方 σ": p["buy_sigma"],
        "買方 4D": p["buy_grade"],
        "買方操盤評分": p["buy_score"],
        "潛在差價%": p["potential_pct"],
    } for p in _pairs]

    st.dataframe(pd.DataFrame(_disp), use_container_width=True, hide_index=True)
    _n_ok = sum(1 for p in _pairs if p["buy_code"])
    st.caption(f"共 {len(_pairs)} 檔高基期;其中 **{_n_ok}** 檔有**不同類別**健康低基期可換。"
               "「潛在差價%」= 買方回到自己期間高點的漲幅(僅參考,非保證)。")
