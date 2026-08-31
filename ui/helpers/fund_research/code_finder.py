"""「找代號」工具 —— ③ 基金研究合併頁的**共用頂部**（線框 §03 原文）。

線框 `docs/wireframes/fund-wireframe-final.html` §03「③ 🔍 基金研究」：

> **共用頂部（兩個模式都看得到）**
> 保留 🔍 關鍵字搜尋境外基金（TDCC / FundClear）
> 現況只在個基深掘頁，且藏在一個收合區內。**合併後上升為兩模式共用的「找代號」工具**
> `tab2_single_fund.py:338-344`
>
> 理由：兩頁現在各有一套輸入框，而「用關鍵字找基金代號」的工具**只存在於個基深掘頁裡**，
> 批次分析頁的使用者要湊代號清單時得**跨頁去找**。

⚠️ 兩件必須誠實講清楚的事（`CLAUDE.md §-2` 規則 6）
--------------------------------------------------
1. ~~**這是本檔與 `ui/tab2_single_fund.py` 併存的第二份實作。** 併存是**暫時的**：~~
   ~~合併頁接手之後，`render_single_fund_tab()` 內那份摺疊版會被~~
   ~~`merge_context` 的旗標關掉（同一次畫面上不會出現兩份）。~~
   ~~舊入口（`app.py` 目前仍直接掛 `render_single_fund_tab`）被移除時，~~
   ~~那份摺疊版即成孤兒、應一併刪除 —— **本批不動它**（app.py 接線屬另一個工作包）。~~
   → **2026-08-31 已結案**（有意識的狀態變更，不是漏刪 · 決策者：AI 總管）。
   舊段落自己寫下的觸發條件（「舊入口被移除時，那份摺疊版即成孤兒、應一併刪除」）
   已命中：WP-F 七→五接線移除了舊入口，`render_single_fund_tab()` 的唯一 caller
   永遠持有 `SHARED_SEARCH` 旗標 → 那份摺疊版成為死碼，**已整段實體刪除**。
   **本檔現在是全站唯一的「找代號」實作。**
2. ~~**本檔是 `repositories.fund.tdcc_search_fund` 的第二個 UI 呼叫點。**~~
   → **2026-08-31 更正：本檔現在是 `tdcc_search_fund` 在 UI 層的　*唯一*　呼叫點。**
   守衛：`tests/test_fund_research_merge.py::test_code_finder_is_the_only_search_entry`
   （AST 數呼叫點，不看 docstring —— 本段自己就是會騙過 grep 的那種文字）。
   ⚠️ **但憲法登記仍未更新**：該 fetcher 登記在 `CLAUDE.md §8.2.A` 的
   **EX-PASSTHRU-1**，登記路徑指的是 `ui/tab2_single_fund.py:147` ——
   **那個呼叫點已經被刪掉了**，也就是例外表現在指向一個不存在的位置，
   而真正活著的這一處**從未登錄**（＝ §8.2.A 末句明禁的「未經登錄的軟例外」）。
   **登記表的更新不在本工作包的檔案邊界內**（`CLAUDE.md` 不得由執行組改），
   已在 PR 描述具名回報請總管裁決。
   ⚠️ 不要把「測試沒紅」讀成「這件事已經合規」—— 上面那條新守衛守的是
   **呼叫點數量**，**不是**憲法登記的正確性；本 repo 目前沒有任何機器規則在守後者。

§1 Fail Loud：搜尋失敗一律走 `system_error()` 紅框 + 技術細節，
**不吞例外、不回假清單**；查無結果（真的沒有這檔）與抓取失敗（系統壞了）分開講。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import not_ready, system_error

#: 搜尋結果的 session key。**刻意沿用 `ui/tab2_single_fund.py` 用的同一個 key** ——
#: 兩處是同一份「使用者剛剛查到的基金清單」，分兩個 key 會變成兩個真相源（§2.1）。
RESULTS_KEY: str = "tdcc_results"


def _search(keyword: str) -> None:
    """打 TDCC / FundClear 找基金代號，結果寫回 session。失敗走系統紅燈。"""
    # lazy import：與本 repo 既有慣例一致，避免 module load 時拉起整條抓取相依鏈。
    from repositories.fund import tdcc_search_fund

    try:
        with st.spinner(f"搜尋「{keyword}」中..."):
            results = tdcc_search_fund(keyword)
    except Exception as _e_search:  # noqa: BLE001 — 誠實上報，不吞（§1）
        # ⚠️ 2026-08-28 稽核修正：失敗時**刻意不清掉**上一次的結果（清掉等於把使用者
        # 已經查到的東西沒收），但那份清單會原樣留在下方、標題還寫「選擇基金（N 筆）」——
        # 看起來就像**這次**搜出來的。§2.4：過期資料可以留，但**必須帶 is_stale 旗標**。
        # 旗標寫進既有的紅框 hint（使用者此刻正在看的地方），不新增視覺語彙。
        _stale = st.session_state.get(RESULTS_KEY) or []
        _hint = ("這是抓取端的問題，不是「查無此基金」。"
                 "可稍後重試，或直接在下方模式 A 貼上 MoneyDJ 代碼／網址。")
        if _stale:
            _hint += (f"　⚠️ 下方仍列出的 {len(_stale)} 筆是**上一次**搜尋的結果，"
                      f"**不是**這次「{keyword}」的 —— 這次沒有拿到任何資料。")
        system_error("基金關鍵字搜尋失敗", _e_search, hint=_hint)
        return
    st.session_state[RESULTS_KEY] = results
    if not results:
        # 「查無結果」是**業務事實**（真的沒有這檔），不是系統故障 → 不用紅框。
        st.info("🔎 查無結果 —— 換個關鍵字，或直接使用 MoneyDJ 代碼／網址。")
    else:
        st.success(f"✅ 找到 {len(results)} 檔基金")


def render_code_finder() -> None:
    """共用頂部：關鍵字 → 基金代號。兩個模式（單檔深掘 / 批次掃描）都看得到。

    版面：固定 3 欄自適應網格（關鍵字 ｜ 搜尋鈕 ｜ 這一格在做什麼）。
    """
    c_kw, c_btn, c_hint = st.columns(3)
    with c_kw:
        keyword = st.text_input(
            "基金關鍵字",
            placeholder="安聯、收益成長、摩根、聯博...",
            label_visibility="collapsed", key="fr_fund_keyword",
        )
    with c_btn:
        do_search = st.button("🔍 搜尋基金代號", type="primary",
                              use_container_width=True, key="fr_btn_search")
    with c_hint:
        st.caption("關鍵字 → 代號。查到的代號：模式 A 貼進網址欄，模式 B 併進清單。")

    if do_search and keyword.strip():
        _search(keyword.strip())

    results = st.session_state.get(RESULTS_KEY, [])
    if not results:
        # ⬜ 未執行 ≠ 出錯（線框 §03「顏色：三態統一規則」）。
        not_ready("尚未搜尋，或上次搜尋沒有結果", where="上方「🔍 搜尋基金代號」")
        return

    options = {f"{r.get('基金名稱','')} | {r.get('基金代碼','')}": r for r in results}
    sel = st.selectbox(f"選擇基金（{len(results)} 筆）", list(options.keys()),
                       key="fr_tdcc_select")
    code = options[sel].get("基金代碼", "")
    st.info(f"💡 代碼：**{code}** —— 模式 A 貼進「MoneyDJ URL 或代碼」欄；"
            f"模式 B 加進代號清單。")
