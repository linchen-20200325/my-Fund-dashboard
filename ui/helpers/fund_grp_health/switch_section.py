"""ui/helpers/fund_grp_health/switch_section.py — 🔀 換標決策區塊(v19.423)。

大表列(dict,含 基金類別/Sharpe 1Y/1Y 含息 %/Sortino/費用率 %/策略燈號/吃本金燈號 …)→
大盤 regime banner + 紅燈檔「一對一替換」建議(同資產類別 argmax)。L3 orchestrator →
L2 `services.switch_strategy`(純邏輯)。三張大表共用(組合/持倉/批次)。
"""
from __future__ import annotations

import streamlit as st


def render_switch_section(rows: list) -> None:
    """🔀 換標決策:大盤 regime banner + 紅燈檔一對一替換建議。rows = 大表列(dict list)。"""
    from services.switch_strategy import (
        RED,
        execution_advice,
        market_regime_alert,
        replacement_candidate,
    )

    _rows = [r for r in (rows or []) if isinstance(r, dict) and r.get("code")]
    if not _rows:
        return

    st.divider()
    st.markdown("### 🔀 換標決策建議")
    st.caption("紅燈=賣出/平轉、黃燈=觀望、綠燈=續抱加碼、灰燈=資料不足。**參考非保證** —— "
               "換標前確認申購/贖回費與匯差;同公司內轉換通常較省。")
    st.caption("ℹ️ 「策略燈號」紅燈條件 = **嚴重吃本金** 或(1Y含息<0 且 Sharpe<0);"
               "故一般 🔴 吃本金(報酬仍正)不一定是策略紅燈,兩欄語意不同。")

    # 大盤 regime filter:系統性風險 → 暫緩換標
    _reg = market_regime_alert(_rows)
    if _reg.get("systemic_risk"):
        st.warning(f"⚠️ **系統性風險**:同池 {_reg['neg_pct']}% 基金 Sharpe 為負(≥80%)→ "
                   "**建議暫緩換標**,避免在市場低點殺低(定期定額續扣即可,等大波段落底)。")

    _reds = [r for r in _rows if RED in str(r.get("策略燈號") or "")]
    if not _reds:
        st.info("目前無 🔴 紅燈(賣出/平轉)檔 —— 沒有急需換掉的標的。")
        return

    import pandas as pd
    _disp = []
    for r in _reds:
        _cands = [c for c in _rows if c.get("code") != r.get("code")]
        _rep = replacement_candidate(r.get("基金類別"), _cands)
        _disp.append({
            "賣出(🔴紅燈)": f"{r.get('基金名') or r.get('code')} ({r.get('code')})",
            "類別": r.get("基金類別") or "—",
            "策略分": r.get("換標策略分"),
            "建議換入(同類最佳)": (f"{_rep.get('基金名') or _rep.get('code')} ({_rep.get('code')})"
                                    if _rep else "⚪ 同類無健康替換標的"),
            "換入 Sharpe": _rep.get("Sharpe 1Y") if _rep else None,
            "換入 1Y含息%": _rep.get("1Y 含息 %") if _rep else None,
        })
    from streamlit import column_config as _cc
    st.dataframe(
        pd.DataFrame(_disp), use_container_width=True, hide_index=True,
        column_config={
            "賣出(🔴紅燈)": _cc.TextColumn("賣出(🔴紅燈)", width="medium",
                help="大表「策略燈號」為 🔴 的檔(1Y含息<0 且 Sharpe<0,或嚴重吃本金)。"),
            "類別": _cc.TextColumn("類別", width="small"),
            "策略分": _cc.NumberColumn("策略分", format="%d",
                help="換標策略分 0-100;**分母可能被收斂**(缺 MaxDD / vs大盤),"
                     "詳見大表「策略分覆蓋」欄。"),
            "建議換入(同類最佳)": _cc.TextColumn("建議換入(同類最佳)", width="medium",
                help="**同**資產類別內取最佳者(與跨類的「輪動配對」不同);"
                     "同類無合格標的 → ⚪,不硬湊。"),
            "換入 Sharpe": _cc.NumberColumn("換入 Sharpe", format="%.2f",
                help="⚠️ 期間可能混 wb07 1Y / 6M / 本地自算,見大表「Sharpe 來源」欄。"),
            "換入 1Y含息%": _cc.NumberColumn("換入 1Y含息%", format="%.2f %%"),
        },
    )
    _n_ok = sum(1 for d in _disp if not str(d["建議換入(同類最佳)"]).startswith("⚪"))
    st.caption(
        f"共 {len(_reds)} 檔紅燈;其中 **{_n_ok}** 檔有同類健康替換標的。替換 = 同資產類別內 "
        "argmax(Sharpe·0.4 + 1Y含息·0.4 + Sortino·0.2),限 綠燈/健康 + Sharpe≥0.5 + "
        "費用率<1.5% + 總報酬>0。")
    st.caption("💡 **處置**:" + execution_advice(RED))
