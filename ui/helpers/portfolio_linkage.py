"""v19.65 I2：單一基金 ↔ 組合持倉 跨 Tab 聯動。

在 Tab2（單一基金）研究一檔基金時，讀 Tab3（組合基金）的 portfolio_funds
（session_state），顯示「此基金是否已在你的組合 / 佔多少權重」，避免重複
加碼、看清現有曝險。屬「跨 Tab 訊號聯動」系列（I1=總經→組合，I2=單檔↔組合）。

讀 session_state（Tab3 未載入組合 → portfolio_funds 為空 → 靜默不顯）：
  - portfolio_funds：list[{code, name, invest_twd, is_core, ...}]
"""
from __future__ import annotations

import streamlit as st


def _norm(s) -> str:
    return str(s or "").strip().upper()


def render_fund_portfolio_membership(session_state, fund_codes, fund_name="") -> None:
    """渲染單檔→組合持倉聯動提示（純顯示，零副作用，零新 IO）。

    fund_codes: 當前基金候選識別碼（full_key / fund_code 等），任一命中即算。
    fund_name:  當前基金名稱（fallback 比對用）。
    """
    _pf = session_state.get("portfolio_funds") or []
    if not isinstance(_pf, list) or not _pf:
        return  # 無組合 → 靜默，不打擾只用單檔功能的 user

    _wanted = {_norm(c) for c in (fund_codes or []) if _norm(c)}
    _nm = _norm(fund_name)

    _matched = None
    for _f in _pf:
        if not isinstance(_f, dict):
            continue
        _code = _norm(_f.get("code"))
        if (_code and _code in _wanted) or (_nm and _norm(_f.get("name")) == _nm):
            _matched = _f
            break

    _total = sum(float(_f.get("invest_twd", 0) or 0)
                 for _f in _pf if isinstance(_f, dict))
    _n = sum(1 for _f in _pf if isinstance(_f, dict))

    if _matched is not None:
        _amt = float(_matched.get("invest_twd", 0) or 0)
        _tag = "核心(穩健)" if _matched.get("is_core") else "衛星(積極)"
        if _total > 0 and _amt > 0:
            _w = _amt / _total * 100.0
            _msg = (f"✅ <b>此基金已在你的組合</b>：權重 <b style='color:#58a6ff'>"
                    f"{_w:.1f}%</b>（NT$ {_amt:,.0f}）｜定位 {_tag}")
        else:
            _msg = (f"✅ <b>此基金已在你的組合</b>（共 {_n} 檔）｜定位 {_tag}"
                    f"<span style='color:#666'>（尚未填投資金額）</span>")
        _border = "#3fb950"
    else:
        _msg = (f"➕ 此基金<b>尚未加入</b>你的組合（目前 {_n} 檔）"
                f"<span style='color:#666'>　· 可至「📊 組合基金」Tab 加入後比較</span>")
        _border = "#d29922"

    st.markdown(
        f"<div style='background:#0d1117;border-left:4px solid {_border};"
        f"border-radius:4px;padding:6px 12px;margin-bottom:8px;font-size:12px;"
        f"color:#8b949e;line-height:1.6'>🔗 {_msg}</div>",
        unsafe_allow_html=True,
    )
