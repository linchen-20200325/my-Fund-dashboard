"""ui/tab1_macro_ai.py — v19.261 P3-A2 從 tab1_macro.py 抽出的 🤖 AI 景氣判斷區塊。

從 `ui/tab1_macro.py:render_macro_tab()` body 內抽出獨立 section,降低主檔 LOC:
- `_build_macro_ai_snapshot(ind, phase, score, srd, news)` — 純函式組 AI snapshot
- `render_ai_summary_section(ind, phase, gemini_key, show_l3, mac_pct)` — render 入口

設計:
- 不依賴 render_macro_tab 的 closure local var,全部走參數注入
- `_show_l3` toggle / `_calc_data_health` 等 caller 計算後傳入
- 純呼叫 Streamlit 渲染 + session_state 讀取(不寫)
- §8.2:L3 UI helper,允許讀 session_state,渲染 only
"""
from __future__ import annotations

import streamlit as st

from shared.colors import BG_DARK_NAVY_4, MATERIAL_RED


def render_ai_summary_section(
    ind: dict,
    phase: dict,
    gemini_key: str,
    show_l3: bool = True,
    mac_pct: int | None = None,
) -> None:
    """渲染 🤖 AI 景氣判斷總結 section。

    Args:
        ind: indicators dict(總經指標)
        phase: phase_info dict
        gemini_key: GEMINI_API_KEY str(可空)
        show_l3: L3 expander 開關
        mac_pct: 資料完整率 %(call site 先算好傳入,None → 內部用 0)
    """
    st.markdown("## 🤖 AI 景氣判斷總結")
    st.caption("吃齊上方四桶資料,生成綜合白話摘要")

    if show_l3:
        st.divider()
    if not (gemini_key and show_l3):
        st.caption("⚠️ 未設定 GEMINI_API_KEY，AI 分析功能關閉")
        return

    # ── 三色燈號阻斷(Core Protocol v2.0 Ch.1) ─────────
    _ai_mac_pct = mac_pct if mac_pct is not None else 0
    if _ai_mac_pct < 50:
        st.markdown(
            f"<div style='border-left:4px solid {MATERIAL_RED};background:{BG_DARK_NAVY_4};"
            "border-radius:0 8px 8px 0;padding:10px 14px;font-size:13px'>"
            "🔴 <b>紅燈阻斷</b>：總經資料完整率 "
            f"<b>{_ai_mac_pct}%</b>（&lt;50%），AI 分析停用。"
            "請前往「🔬 資料診斷」頁確認指標載入狀況。</div>",
            unsafe_allow_html=True)
        return

    if _ai_mac_pct < 80:
        st.warning(f"🟡 資料完整率 **{_ai_mac_pct}%**（黃燈），AI 結果參考性降低。")

    # v18.215：Tab1 改用通用「白話總體檢」widget(與 Tab2/3 一致),
    # 刪除舊七節 macro AI;吃全總經資料、逐章節白話結論 + 時事、無選單。
    # v19.38：明示 AI 總結涵蓋上方 6 個 KEEP 面板的同源資料
    st.markdown("### 🤖 AI 景氣判斷總結")
    st.caption(
        "本 AI 摘要吃齊上方 **① 戰情室三儀表 / ② 拐點偵測 / ③ 即時決策矩陣 / "
        "④ 短線雷達 / ⑤ 流動性壓力 / ⑥ 美股流動性熱錢** 的同源資料"
        "（FRED 23 指標 + phase + 系統性風險 + 時事新聞），逐章節白話結論。"
    )
    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
    _mac_snap, _mac_heads, _mac_secs = _build_macro_ai_snapshot(
        ind, phase,
        st.session_state.get("composite_score", {}),
        st.session_state.get("systemic_risk_data"),
        st.session_state.get("news_items", []),
    )
    render_ai_summary_widget(
        tab_key="tab1",
        tab_label="總經位階",
        snapshot=_mac_snap,
        sections=_mac_secs,
        headlines=_mac_heads,
        gemini_api_key=gemini_key,
        expanded=True,
    )


def _build_macro_ai_snapshot(ind, phase, score, srd, news):
    """v18.215：組 Tab1 總經「全資料」快照給通用白話摘要 widget。

    回傳 (snapshot_str, headlines, sections)。吃齊 Tab1 已算好的資料：
    景氣位階/分數、系統性風險、全部總經指標、領先指標排名、當下子領域燈號、新聞。
    """
    lines = ["## 總經全章節快照"]
    if isinstance(phase, dict) and phase:
        _sc = score.get("total", "—") if isinstance(score, dict) else (score or "—")
        lines.append(f"- 景氣位階：{phase.get('phase', '—')}｜綜合分數：{_sc}")
        _alloc = phase.get("allocation") or phase.get("alloc")
        if isinstance(_alloc, dict) and _alloc:
            lines.append("- 建議配置：" + "、".join(f"{k} {v}%" for k, v in _alloc.items()))
        elif _alloc:
            lines.append(f"- 建議配置：{_alloc}")
    if isinstance(srd, dict) and srd:
        lines.append(f"- 系統性風險評級：{srd.get('risk_level', 'LOW')}"
                     f"（分數 {srd.get('risk_score', '—')}）")
        _trig = srd.get("triggered") or srd.get("keywords")
        if isinstance(_trig, (list, tuple)) and _trig:
            lines.append("  - 觸發事件關鍵字：" + "、".join(str(t) for t in _trig[:5]))
    if isinstance(ind, dict) and ind:
        lines.append("- 關鍵總經指標：")
        for k, v in ind.items():
            if isinstance(v, dict) and "value" in v:
                _sig = v.get("signal", "")
                lines.append(f"  - {k}：{v.get('value')} {v.get('unit', '')}"
                             f"{(' / ' + str(_sig)) if _sig else ''}".rstrip())
            elif isinstance(v, (int, float, str)) and v not in (None, ""):
                lines.append(f"  - {k}：{v}")
    try:
        from services.macro import (  # noqa: PLC0415
            rank_macro_drivers as _rmd,
            calc_sub_cycle_lights as _csl,
        )
        _drv = _rmd(ind, target_key="LEI", lag_months=3, min_overlap=24)
        if isinstance(_drv, dict) and _drv.get("ok") and _drv.get("ranked"):
            lines.append("- 領先指標排名（與景氣約 3 個月後的關聯強弱）：" + "、".join(
                f"{r.get('name')}({'同向' if r.get('direction') == '+' else '反向'}"
                f" {float(r.get('abs_corr', 0) or 0):.2f})"
                for r in _drv["ranked"][:3]))
        _lights = _csl(ind)
        if isinstance(_lights, list) and _lights:
            lines.append("- 各產業/子領域當下燈號：" + "、".join(
                f"{x.get('name', '')}{x.get('icon', '')}"
                f"{('(' + str(x.get('verdict')) + ')') if x.get('verdict') else ''}"
                for x in _lights[:8]))
    except Exception:
        pass   # smoke-allow-pass — 進階分析缺失不阻斷 AI 摘要
    # v18.254：把兩個校準器最新結果寫進快照，供 AI 產出「校準健檢」段落
    # v18.255：改三段式（這代表 / 為什麼 / 該怎麼做）
    try:
        _cms = st.session_state.get("_cal_macro_score")
        _crs = st.session_state.get("_cal_risk_score")
        if _cms or _crs:
            lines.append("- 校準健檢（真實 FRED+SPX 回測）：")
            if isinstance(_cms, dict) and _cms:
                lines.append(
                    f"  - 14-factor 景氣分數【代表】總體命中率 {_cms['overall_acc_pct']:.1f}%"
                    f"（horizon={_cms['horizon']}M、{_cms['src']}）；"
                    f"當前 Macro_Score={_cms['cur_score']:.2f} → {_cms['cur_phase']}")
                _pa = _cms.get("phase_acc") or []
                if _pa:
                    _pa_str = "、".join(
                        f"{r.get('phase')} {r.get('hit_rate_pct', 0):.0f}%(n={r.get('n', 0)})"
                        for r in _pa)
                    lines.append(f"    -【為什麼】各位階命中：{_pa_str}（n 越大越可信、<10 不能當主要依據）")
                _gt = _cms.get("grid_top")
                if isinstance(_gt, dict):
                    lines.append(
                        f"    -【該怎麼做】grid_search 最佳門檻 (Peak/Exp/Rec)="
                        f"({_gt['peak_thr']:.1f}/{_gt['expansion_thr']:.1f}/{_gt['recovery_thr']:.1f})"
                        f"→ {_gt['overall_acc_pct']:.1f}%；"
                        f"若比當前公式門檻 (8.0/5.0/3.0) 高 >5% 才值得改 macro_service.py")
                else:
                    lines.append(
                        "    -【該怎麼做】命中率 ≥70% 可照位階建議配置；<70% 應搭配其他指標佐證")
            if isinstance(_crs, dict) and _crs:
                if _crs.get("no_hit"):
                    lines.append(
                        f"  - 3-factor 風險評分【代表】horizon={_crs['horizon']}M、"
                        f"drawdown={_crs['drawdown_pct']}%、window={_crs['rolling_win']}M "
                        f"參數下校準器無命中")
                    lines.append(
                        "    -【為什麼】該回看期內 SPX 未出現此規模回檔（樣本不足、不是規則 bug）")
                    lines.append(
                        "    -【該怎麼做】放寬 drawdown 到 -15% 或 -10% 重新校準才能讀")
                else:
                    lines.append(
                        f"  - 3-factor 風險評分【代表】最佳 F1 門檻={_crs['best_threshold']:.2f}（"
                        f"P={_crs['precision']:.0%}、R={_crs['recall']:.0%}、"
                        f"F1={_crs['f1']:.0%}）；當前 risk_score={_crs['cur_risk_score']:.2f}")
                    if _crs['cur_risk_score'] >= _crs['best_threshold']:
                        lines.append(
                            "    -【為什麼】當前分數已 ≥ 警戒門檻 → 歷史上類似讀數有機率出現 drawdown")
                        lines.append(
                            "    -【該怎麼做】建議減持高 beta 部位、提高現金比、停止新加碼")
                    else:
                        lines.append(
                            "    -【為什麼】當前分數低於警戒門檻 → 短期內出現該規模回檔機率較低")
                        lines.append(
                            "    -【該怎麼做】維持配置、追蹤 risk_score 月變化、突破門檻才動作")
    except Exception:
        pass   # smoke-allow-pass — 校準資料缺失不阻斷 AI 摘要
    # v18.255：9 章節白話判讀
    try:
        _liq = st.session_state.get("_macro_liquidity")
        if isinstance(_liq, dict) and _liq:
            lines.append(
                f"- 流動性壓力：{_liq.get('signal', '')} {_liq.get('tier', '')}"
                f"（分數 {_liq.get('value', 0):+.2f}）"
            )
            if _liq.get("top_contrib"):
                _tc = "、".join(
                    f"{b['name']}({b['contrib']:+.2f})" for b in _liq["top_contrib"])
                lines.append(f"  - 主要推升/壓低因子：{_tc}")
            if _liq.get("verdict"):
                lines.append(f"  - 判讀：{str(_liq['verdict'])[:200]}")
        _comp = st.session_state.get("_macro_compass")
        if isinstance(_comp, dict) and _comp:
            _sahm_v = _comp.get("sahm_latest")
            _adl_v = _comp.get("adl_latest")
            lines.append(
                f"- 景氣循環羅盤：薩姆規則={_sahm_v:+.2f}pp" if _sahm_v is not None
                else "- 景氣循環羅盤：薩姆規則=—"
            )
            if _adl_v is not None:
                lines[-1] += f"、RSP/SPY 廣度={_adl_v:+.2f}%MoM"
            if _comp.get("verdict"):
                lines.append(f"  - 研判：{_comp['verdict']}")
        _items = st.session_state.get("_macro_23items")
        if isinstance(_items, dict) and _items:
            lines.append(
                f"- 23 項加扣分明細：{_items.get('n_pos', 0)} 項正貢獻 / "
                f"{_items.get('n_neg', 0)} 項負貢獻（共 {_items.get('n_total', 0)}）"
            )
            if _items.get("top_pos"):
                lines.append("  - 最強正貢獻 Top3：" + "；".join(
                    str(r.get("verdict", ""))[:60] for r in _items["top_pos"]))
            if _items.get("top_neg"):
                lines.append("  - 最強負貢獻 Top3：" + "；".join(
                    str(r.get("verdict", ""))[:60] for r in _items["top_neg"]))
        _cap = st.session_state.get("_macro_capital_line")
        if isinstance(_cap, dict) and _cap:
            _n_ero = _cap.get("n_eroded", 0)
            _n_total_funds = _cap.get("n_funds", 0)
            if _n_total_funds > 0:
                if _n_ero == 0:
                    lines.append(
                        f"- 資本防線：{_n_total_funds} 檔基金全部 TR1Y ≥ 配息率（配息有保障）")
                else:
                    lines.append(
                        f"- 資本防線：⚠️ {_n_ero}/{_n_total_funds} 檔本金侵蝕"
                        f"（TR1Y < 配息率，配息來自本金）"
                    )
                    if _cap.get("eroded_funds"):
                        _ef = "、".join(
                            f"{f['name']}(TR1Y {f['tr1y']:.1f}% vs 配息率 {f['adr']:.1f}%)"
                            for f in _cap["eroded_funds"][:3])
                        lines.append(f"  - 受損基金：{_ef}")
        _ibt = st.session_state.get("_macro_inv_backtest")
        if isinstance(_ibt, dict) and _ibt and _ibt.get("n_events", 0) > 0:
            _m12 = _ibt.get("median_12m")
            _wr12 = _ibt.get("win_rate_12m")
            _m18 = _ibt.get("median_18m")
            lines.append(
                f"- 倒掛翻正歷史回測：近 30 年 {_ibt['n_events']} 個事件，"
                f"翻正後 12M 中位 {_m12:+.2f}%（勝率 {_wr12:.0f}%）" if _m12 is not None
                else f"- 倒掛翻正歷史回測：近 30 年 {_ibt['n_events']} 個事件"
            )
            if _m18 is not None:
                lines.append(
                    f"  - 18M 中位 {_m18:+.2f}%；歷史意義：翻正為衰退末期，"
                    f"屬股市底部累積區（1990/2000/2008/2020）"
                )
        _sk = st.session_state.get("_macro_sankey")
        if isinstance(_sk, dict) and _sk and _sk.get("ok"):
            lines.append(
                f"- 總經因果鏈 Sankey：{_sk.get('n_strong_links', 0)} 條強相關因果路徑"
                f"（|corr|≥0.5）"
            )
            if _sk.get("top_strong"):
                _ts = "、".join(
                    f"{s['src']}→{s['tgt']}({s['corr']:+.2f})"
                    for s in _sk["top_strong"])
                lines.append(f"  - 強傳導 Top3：{_ts}")
        _sbt = st.session_state.get("_macro_subsector_bt")
        if isinstance(_sbt, dict) and _sbt and _sbt.get("alerts"):
            lines.append(
                f"- 細項燈號歷史回測（target={_sbt.get('target')}、"
                f"forward={_sbt.get('forward_months')}M）："
            )
            for _a in _sbt["alerts"][:3]:
                lines.append(f"  - {str(_a)[:120]}")
        _vi = st.session_state.get("_macro_var_importance")
        if isinstance(_vi, dict) and _vi and _vi.get("top3"):
            _top3_str = "、".join(
                f"{r['name']}(|corr|={r['abs_corr']:.2f}, "
                f"{'同向' if r.get('direction') == '+' else '反向'})"
                for r in _vi["top3"])
            lines.append(
                f"- 變數重要性 Top3（預測 {_vi.get('target')} 在 {_vi.get('lag_months')}M 後變化）："
                f"{_top3_str}"
            )
        _hm = st.session_state.get("_macro_hot_money")
        if isinstance(_hm, dict) and _hm:
            # v19.142：staleness gate — 熱錢監測在 v19.47 起被收進 📦 ARCHIVED expander,
            # session 卡舊資料 90 天屢見不鮮。對齊 CLAUDE.md §2.4 STALE 注入慣例:
            # - > 30 天:全段 skip(避免 Gemini 用 3 月份外資資料做 6 月決策的 §1 違憲)
            # - 8-30 天:Prompt 前加 [STALE: Nd] 標籤,Gemini 知道別重押
            import datetime as _dt_hm
            _hm_stale_days = None
            try:
                _hm_dt = _dt_hm.date.fromisoformat(str(_hm.get("date", ""))[:10])
                _hm_stale_days = (_dt_hm.date.today() - _hm_dt).days
            except (ValueError, TypeError):
                _hm_stale_days = None
            if _hm_stale_days is not None and _hm_stale_days > 30:
                # 超過 30 天直接 drop（避免污染 prompt）；但留個簡短 marker 讓 AI 知道沒料
                lines.append(
                    f"- 台股熱錢三角交叉:資料過舊({_hm_stale_days} 天前),"
                    "已從 prompt 中排除(需展開「📦 ARCHIVED 台股熱錢監測」更新)"
                )
            else:
                _hm_stale_tag = (f"[STALE:{_hm_stale_days}d] "
                                 if _hm_stale_days is not None and _hm_stale_days > 7 else "")
                lines.append(
                    f"- {_hm_stale_tag}台股熱錢三角交叉（{_hm.get('date', '')}）：{_hm.get('state', '')}"
                    f"{'（背離警示）' if _hm.get('is_divergence') else ''}"
                )
                lines.append(
                    f"  - 近 {_hm.get('window', 5)}日累計外資 {_hm.get('roll_flow', 0):+.0f} 億、"
                    f"台幣升貶 {_hm.get('roll_apprec_pct', 0):+.2f}%"
                )
                if _hm.get("interpretation"):
                    lines.append(f"  - 判讀：{_hm['interpretation']}")
    except Exception:
        pass   # smoke-allow-pass — 章節資料缺失不阻斷 AI 摘要
    headlines = [str(n.get("title", "") or n.get("headline", ""))
                 for n in (news or []) if isinstance(n, dict)][:8]
    sections = ["景氣位階與分數", "資產配置建議", "關鍵總經指標", "系統性風險",
                "領先指標與產業燈號", "校準健檢",
                "流動性壓力", "景氣循環羅盤", "23 項加扣分明細", "資本防線",
                "倒掛翻正歷史回測", "總經因果鏈", "細項燈號回測",
                "變數重要性", "台股熱錢三角交叉",
                "新聞時事"]
    return "\n".join(lines), headlines, sections


__all__ = ["render_ai_summary_section", "_build_macro_ai_snapshot"]
