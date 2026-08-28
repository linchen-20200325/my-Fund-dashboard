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
from ui.helpers.render_state import not_ready


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

    if show_l3:
        st.divider()
    if not (gemini_key and show_l3):
        not_ready("未設定 GEMINI_API_KEY，AI 分析功能關閉",
                  where="Streamlit Cloud → Settings → Secrets 的 `GEMINI_API_KEY`")
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
    # 2026-08-10:這裡原本再印一次「🤖 AI 景氣判斷總結」——與本函式開頭那個區塊標題
    # 逐字相同,加上 widget 自己的標題,同一句話在畫面上連印三次(同型現場見
    # `tests/test_audit_20260810_tab1_shells.py` 決策矩陣那條)。開頭那個是區塊標題
    # (三條早退路徑也靠它),留;這一份副本移除。開頭那句短 caption 一併移除 ——
    # 下面這段把同一件事講得更完整(逐一列出吃了哪 6 個面板),兩句並存只是重複。
    st.caption(
        "本 AI 摘要吃齊上方 **① 戰情室三儀表 / ② 拐點偵測 / ③ 即時決策矩陣 / "
        "④ 短線雷達 / ⑤ 流動性壓力 / ⑥ 美股流動性熱錢** 的同源資料"
        "（FRED 23 指標 + phase + 系統性風險 + 時事新聞），逐章節白話結論。"
    )
    from ui.helpers.ai_summary import render_ai_summary_widget  # noqa: PLC0415
    # 綜合分數的 producer 是 `ui/tab1_macro.py` 的 ② 依據段(算完當場 stash 進
    # session),本段是它的**消費端**;拿掉那一行 stash,這裡就會退回缺值符號。
    # 預設值原本是空 dict —— 空 dict 走的是「dict 分支查不到 key」那條路,
    # 與「真的沒有這個鍵」在下游混成同一種結果;改成不給預設,讓缺值就是缺值。
    _mac_snap, _mac_heads, _mac_secs = _build_macro_ai_snapshot(
        ind, phase,
        st.session_state.get("composite_score"),
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
    )


def _format_composite(score) -> str:
    """把 session 拿到的總經加權淨分格式化成 prompt 用字串;拿不到 → 缺值符號。

    2026-08-10:原本寫 `score or "—"`。composite 是**有正負的加權淨分**,
    正好落在 0.0(多空完全打平)是一個真實讀數,卻會被 falsy 判成缺資料 ——
    §1「缺值要誠實」的反面:把算出來的值謊報成沒算出來。同型缺陷見
    `PROCESS.md §4` 表格第一列(`0 or 1` 把去重後的權重還原回去)。

    小數位對齊 `build_evidence_rows` 那一列(一位),避免 AI 講的數字與畫面
    上同一個數字的位數對不起來,讀者以為是兩個判斷。
    """
    import math  # noqa: PLC0415

    def _num(v) -> "str | None":
        # bool 是 int 的子型別,先擋掉(True 會變成 +1.0 這種假分數)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        # NaN / inf 不是讀數,誠實回缺值,不讓 "+nan" 進 prompt(§1)
        return f"{float(v):+.1f}" if math.isfinite(v) else None

    _direct = _num(score)
    if _direct is not None:
        return _direct
    if isinstance(score, dict):        # 舊契約相容:曾以 dict 承載
        for _k in ("total", "score", "composite", "value"):
            _hit = _num(score.get(_k))
            if _hit is not None:
                return _hit
    return "—"


def _build_macro_ai_snapshot(ind, phase, score, srd, news):
    """v18.215：組 Tab1 總經「全資料」快照給通用白話摘要 widget。

    回傳 (snapshot_str, headlines, sections)。吃齊 Tab1 已算好的資料：
    景氣位階/分數、系統性風險、全部總經指標、領先指標排名、當下子領域燈號、新聞。
    """
    lines = ["## 總經全章節快照"]
    if isinstance(phase, dict) and phase:
        _sc = _format_composite(score)
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
                # 2026-08-05 稽核 🔴 必修 1(§1 Fail Loud / 反造假):
                # 原本寫 dict key(`PMI`)→ Gemini 收到「- PMI：63.8」,把
                # **Phil Fed 擴散指數轉換出來的代理值**當官方 ISM PMI 論述
                # (官方 2026-07 實際 55.6;63.8 若為真是 1983 年來最高)。
                # 服務層 `services/macro/us_indicators.py:481-494` 早已備妥
                # name / is_proxy / proxy_note / source,但 prompt 端
                # **0 consumer**(`PROCESS.md §4`「算對了但沒接出去」)。
                # 這裡改吃服務層 name(身分 SSOT)+ 顯式 [PROXY] 標記。
                # 旗標優先於文案:不靠 name 裡剛好有「替代」二字判斷
                # (同 `ui/tab1_macro_midcycle._card_title` 的既有裁決)。
                _nm = str(v.get("name") or "").strip() or k
                _is_proxy = bool(v.get("is_proxy"))
                _tag = "[PROXY 代理值] " if _is_proxy else ""
                lines.append(f"  - {_tag}{_nm}：{v.get('value')} {v.get('unit', '')}"
                             f"{(' / ' + str(_sig)) if _sig else ''}".rstrip())
                if _is_proxy:
                    _pn = str(v.get("proxy_note") or "").strip()
                    _src = str(v.get("source") or "").strip()
                    _meta = "；".join(p for p in (
                        f"資料源 {_src}" if _src else "", _pn) if p)
                    lines.append(
                        "    ⚠️ 上一項為**代理值**，不是該指標的官方本尊讀數，"
                        "敘述時必須註明「替代指標」，禁止當官方數據引用"
                        + (f"（{_meta}）" if _meta else ""))
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
        # (2026-08-07 移除)原本這裡還讀一份「景氣循環羅盤」stash。全 repo 查不到
        # 任何寫入端(唯一的寫入者隨 🧭 總經指南針一併下架),所以該段永遠取不到值、
        # 章節永遠是空的,卻仍掛在下方 sections 目錄裡要 AI 逐節輸出 —— 等於每次都
        # 產出一節「這項目前沒資料」的固定噪音,並讓節數宣稱高於實際可產出的內容。
        # 依 `PROCESS.md §4` 0-consumer 條款:讀取端與章節目錄一起清。
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
        # (2026-08-07 一併移除)同上,另有三段讀取端全站查無寫入者:因果鏈 Sankey /
        # 細項燈號回測 / 變數重要性。它們與指南針屬同一種缺陷(有讀無寫),不是
        # 「這次剛好沒資料」而是「永遠不會有資料」,故讀取端與章節目錄一併清。
        # 判準見 tests/test_tab1_macro.py 的漂移鎖(讀了沒人寫 → 紅)。
        # 若日後把對應產生端接回來,再連同章節目錄一起加回。
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
    # 章節目錄 = 交給 AI 逐節輸出的維度清單(prompt 端會要求「缺資料就老實說沒資料」,
    # 所以這裡刻意列出「這個 Tab 有哪些維度」而非「這次剛好有值的維度」—— 見
    # tests/test_tab1_macro.py 對此設計的鎖)。
    # 但**沒有寫入端的維度不算維度**:它不是「這次沒資料」,是永遠不會有資料。
    # 2026-08-07 依此判準移除 4 節(景氣循環羅盤 / 總經因果鏈 / 細項燈號回測 /
    # 變數重要性)—— 上游 stash 全站零寫入端,列進來只會讓 AI 每次多產 4 段
    # 「這項目前沒資料」,並讓 caption 的節數高於實際做得出來的內容。
    sections = ["景氣位階與分數", "資產配置建議", "關鍵總經指標", "系統性風險",
                "領先指標與產業燈號", "校準健檢",
                "流動性壓力", "23 項加扣分明細", "資本防線",
                "倒掛翻正歷史回測", "台股熱錢三角交叉",
                "新聞時事"]
    return "\n".join(lines), headlines, sections


__all__ = ["render_ai_summary_section", "_build_macro_ai_snapshot"]
