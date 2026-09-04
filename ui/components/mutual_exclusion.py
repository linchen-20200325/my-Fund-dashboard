"""ui/components/mutual_exclusion.py — 🛡️ ② 持倉互斥避險(元件 A)。

客戶 2026-08-31 拍板(線框 `docs/wireframes/rotation-components-wireframe.html`,
Q1~Q4 全數照推薦):

- **Q1 位置**:緊接「結論摘要」(淘汰候選紅區)之後、健診大表之前 ——
  「哪幾檔在吃本金」與「哪幾對會一起跌」是同一層級的行動答案。
  完整相關性矩陣熱力圖**不搬家**,仍留在 🔬 進階分析;本元件只把「警示對」上移。
- **Q2 同質化分級**:警示對數 ÷ 實際比對成功對數;切點收 shared/signal_thresholds
  SSOT;成功對數不足 → ⬜ 樣本不足,不硬判。
- 一句話職責:**我手上這幾檔,會不會一起跌。**

分層:本檔只「畫」。係數計算住 L2 `services/portfolio_service.py`(v19.176 SSOT),
彙整/分級住 L2 `services/homogeneity.py`;輸入組裝與 🔬 進階分析矩陣共用
`correlation.build_overlap_input / build_corr_input`(同一份輸入餵同一個計算,§2.1)。
**本元件不新增任何演算法、不改任何既有數字**(線框 02 節「why」原文)。

顏色三態(render_state 五態,線框 05 節鐵律 ③):
  未跑健診 → 整個元件不渲染(② 既有 gating 之內);前提不足 → ⬜ 灰;
  計算/渲染失敗 → 🔴 system_error;**高相關警示對 = 🔴 業務紅(卡片左軌)**,
  不用錯誤框 —— 分析成功了、答案很難看,那是成果不是故障;無警示 → ✅ 誠實好結果。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import GH_FG_MUTED, GH_FG_PRIMARY, MATERIAL_RED
from ui.helpers.render_state import not_ready, system_error

#: 警示對卡片超過此數 → 其餘收進「顯示其餘 N 對」展開,避免撐爆版面(線框 02 節區塊 2)。
#: 純版面收納參數(第 7 張起收合),不是任何業務門檻 —— 不屬 signal_thresholds 的量綱。
_MAX_CARDS_BEFORE_FOLD = 6

#: 型態徽章(線框:🏭 持股重疊 / 📈 走勢同步 —— 兩維度獨立判定,不合併)
_KIND_ICONS = {"holdings": "🏭", "nav": "📈"}

#: Q2 三級 + 樣本不足 → stat_tile 的 status 語彙(status.py SSOT:ok/warn/bad/unknown)
_GRADE_TILE = {
    "low": ("低", "ok"),
    "mid": ("中", "warn"),
    "high": ("高", "bad"),
    "insufficient": (None, "unknown"),
}


def _alert_card_html(alert: dict) -> str:
    """單張警示對卡(gh_card 外框 + 🔴 業務紅左軌;沿用 #726 六元件語彙,不另創視覺)。"""
    from ui.components.cards import gh_card

    rail = (f"<span style='position:absolute;left:0;top:0;bottom:0;width:3px;"
            f"background:{MATERIAL_RED}'></span>")
    pair = (f"<div style='font-size:13.5px;font-weight:700;color:{GH_FG_PRIMARY};"
            f"line-height:1.4'>{alert['name_a']}"
            f"<span style='color:{GH_FG_MUTED};font-size:11px'>（{alert['code_a']}）</span>"
            f" ⟷ {alert['name_b']}"
            f"<span style='color:{GH_FG_MUTED};font-size:11px'>（{alert['code_b']}）</span></div>")
    hits = "".join(
        f"<div style='font-size:12px;color:{MATERIAL_RED};margin-top:3px'>"
        f"{_KIND_ICONS.get(h['kind'], '')} {h['label']}　"
        f"<b>{h['value']:.2f}</b>"
        f"<span style='color:{GH_FG_MUTED}'>（門檻 {h['threshold']:.2f}）</span></div>"
        for h in alert["hits"]
    )
    warn = (f"<div style='font-size:11px;color:{GH_FG_MUTED};margin-top:5px'>"
            f"回撤時可能齊跌 —— 這兩檔互為影子,建議檢視是否擇一持有</div>")
    return gh_card(rail + pair + hits + warn, radius=9, padding="12px 14px",
                   extra="position:relative;overflow:hidden")


def _render_alert_cards(alerts: list) -> None:
    """3 欄自適應網格逐張畫卡;超過 `_MAX_CARDS_BEFORE_FOLD` 張起收進展開(不撐爆版面)。"""
    def _grid(batch: list) -> None:
        for i in range(0, len(batch), 3):
            cols = st.columns(3)
            for col, al in zip(cols, batch[i:i + 3]):
                col.markdown(_alert_card_html(al), unsafe_allow_html=True)

    _grid(alerts[:_MAX_CARDS_BEFORE_FOLD])
    rest = alerts[_MAX_CARDS_BEFORE_FOLD:]
    if rest:
        with st.expander(f"顯示其餘 {len(rest)} 對高相關警示", expanded=False):
            _grid(rest)


def render_mutual_exclusion_section(funds: list) -> None:
    """🛡️ 持倉互斥避險:同質化診斷帶(3 tile)+ 高相關警示對卡 + 一行指路。

    caller:`ui/tab_fund_grp_health._render_health_3tables`(僅 ② 健診 Tab,
    `source_tab == "health"`;Tab3 持倉健診 embed 未在 Q1 拍板範圍,不渲染)。
    健診未跑時本函式根本不會被呼叫(② 既有 gating),故無「未跑」占位。
    """
    from shared.signal_thresholds import HOMOGENEITY_MIN_PAIRS
    # ⚠️ 分頁／分區名一律走 SSOT。本函式原本兩處手寫「⑤ 資料診斷」——
    #    **站號與名字都是手寫的**,而 ⑤ 的分區實際叫「🔭 資料診斷」、
    #    分頁叫「⚙️ 設定與診斷」,兩個都對不上;站號更是分頁一增刪就過期
    #    (`story_nav._tab_ordinal` 存在的唯一理由)。
    from ui.helpers.story_nav import where_to_find as _where_to_find

    st.divider()
    st.markdown("#### 🛡️ 持倉互斥避險")
    st.caption("一句話:**我手上這幾檔,會不會一起跌。** 兩個維度獨立判定 —— "
               "🏭 持股重疊(買一樣的東西)與 📈 走勢同步(即使持股不同也同漲同跌),"
               "不合併成單一分數。")

    if len(funds or []) < 2:
        # 「去哪補」原本整個缺席（Lane E）。線框 Rule 04 的三要素裡它最常被省掉,
        # 而省掉之後空狀態只是把「消失」換成「灰色的消失」—— 使用者知道少了東西,
        # 但不知道下一步。指名的兩個字串**與同頁 `backtest_section` 那條同源**
        # (本頁同一個 form 的輸入框與送出鈕),不是另外想一個講法。
        # ⚠️ 刻意**不寫「上方」** —— `backtest_section` 那條寫了,本條沒跟著抄:
        #    方位是版面順序的函數,寫進文案等於保證下一次重排就說謊
        #    (`tests/test_ia_tab13_batch3.py::test_new_user_facing_copy_has_no_positional_words`
        #     的理由,那條規則的射程只到 ③ 的四個檔,但**理由對本檔一樣成立**)。
        #    「哪個欄位」已經由 `「基金代號」` 這個名字唯一指定了,方位詞不增加資訊。
        not_ready("至少需 2 檔基金才能比對互斥性",
                  where="本頁的「基金代號」欄位（多貼幾檔後重按「🩺 開始健診」）")
        return

    try:
        from services.homogeneity import build_mutual_exclusion_summary
        from services.portfolio_service import (
            calc_correlation_matrix,
            calc_holdings_overlap,
        )
        from ui.helpers.fund_grp_health.correlation import (
            build_corr_input,
            build_overlap_input,
        )

        _hov_input = build_overlap_input(funds)
        _corr_input = build_corr_input(funds)
        summary = build_mutual_exclusion_summary(
            _hov_input, _corr_input,
            calc_holdings_overlap(_hov_input),
            calc_correlation_matrix(_corr_input),
        )
    except Exception as _e_me:  # noqa: BLE001
        system_error("持倉互斥避險計算失敗", _e_me,
                     hint="本區塊已隔離;下方健診大表與 🔬 進階分析的完整相關性矩陣不受影響。")
        return

    dims = summary["dims"]
    if not dims["holdings"]["computed"] and not dims["nav"]["computed"]:
        _miss = "、".join(f"{x['name']}（{x['code']}）" for x in summary["excluded"]) or "全部"
        not_ready(f"缺持股與淨值資料,無法比對互斥性 —— 缺資料檔:{_miss}",
                  where=_where_to_find("diag"))
        return

    # ── 區塊 1:同質化診斷帶(3 欄 stat tile;#726 元件,不另創視覺)──
    from ui.components.stat_tile import stat_tile

    hom = summary["homogeneity"]
    _grade_txt, _grade_status = _GRADE_TILE[hom["grade"]]
    _ratio = hom["ratio"]
    if hom["grade"] == "insufficient":
        _grade_sub = f"樣本不足（成功對數 < {HOMOGENEITY_MIN_PAIRS}）"
    else:
        _grade_sub = f"警示 ÷ 成功 = {_ratio:.0%}"

    c1, c2, c3 = st.columns(3)
    c1.markdown(stat_tile(
        summary["theoretical_pairs"], "可比對數",
        sublabel=f"{summary['n_funds']} 檔 → 理論對數;實際成功 "
                 f"{summary['success_pairs_union']} 對（同質化分母）"),
        unsafe_allow_html=True)
    c2.markdown(stat_tile(
        summary["alert_pair_count"], "高相關警示對數",
        status=("bad" if summary["alert_pair_count"] else "ok"),
        sublabel="兩維度聯集"), unsafe_allow_html=True)
    c3.markdown(stat_tile(_grade_txt, "同質化程度", status=_grade_status,
                          sublabel=_grade_sub), unsafe_allow_html=True)

    # ── 單一維度整組沒算成:講清楚計數少了哪半邊(§1,缺口不靜默)──
    _dim_missing = [d["label"] for d in dims.values() if not d["computed"]]
    if _dim_missing:
        st.caption(f"⬜ 「{'、'.join(_dim_missing)}」維度本次整組算不出來（資料不足），"
                   f"上列計數只含另一個維度。")

    # ── 部分檔資料不足:明確標名,不靜默剔除(§1;沿用輪動表 σ 名單同一手法)──
    if summary["excluded"]:
        _lines = "；".join(
            f"{x['name']}（{x['code']}）:{'、'.join(x['reasons'])}"
            for x in summary["excluded"])
        st.caption(f"⬜ 未納入比對（資料不足）:{_lines} —— 明確標名,不靜默剔除。"
                   f"可到 {_where_to_find('diag')} 查來源狀態。")

    # ── 區塊 2:高相關警示對卡片(🔴 業務紅卡,非錯誤框)──
    if summary["alerts"]:
        _render_alert_cards(summary["alerts"])
    elif summary["success_pairs_union"] > 0:
        st.success("✅ 本組合無高相關警示對（兩維度皆低於門檻）")

    # ── 區塊 3:一行指路(答案在上、依據在下;矩陣不重畫)──
    st.caption("🔎 完整相關性矩陣（兩維度熱力圖 + 逐對係數）在下方「🔬 進階分析」——"
               "本區只上移「警示對」這個答案,依據不搬家。")
