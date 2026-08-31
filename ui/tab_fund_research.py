"""ui/tab_fund_research.py —— 「③ 🔍 基金研究」＝ 個基深掘 ＋ 批次分析（合併頁）。

客戶拍板的線框：`docs/wireframes/fund-wireframe-final.html` §03「③ 🔍 基金研究」。

這一頁的一句話職責（線框原文）
------------------------------
> **還沒放進組合之前，查一檔或掃一批的體質。**

合併方式（線框原文，逐字）
--------------------------
> **不是把兩頁上下相接**，而是共用一個「先找到標的」的頂部，
> 再用一個模式切換決定下面畫什麼。
>
> 建議模式切換：🔍 單檔深掘　｜　📦 批次掃描
> **單一切換鍵，切換的是下方版面。不是第二層分頁** —— 全站已經有三層巢狀分頁的問題，
> 這裡不再加一層。

> 至於兩模式下方的內容順序，**維持各自現況不動**：
> 本次改的是入口與歸屬，不是各自頁內的順序（那會讓改動面一次太大）。

→ 故本檔**不重排**任何既有區塊，也**不改任何數字的算法**：模式 A 直接呼叫
`render_single_fund_tab()`、模式 B 直接呼叫 `render_batch_analysis_tab()`，
本檔只負責「共用頂部 + 模式切換 + 批次的延遲載入 gate」。

⚠️ 批次掃描的 gate（本檔最重要的一條）
--------------------------------------
批次掃描是全站唯一會跑 **30~40 分鐘**（實測估算 20~45 秒/檔）的長任務。
合併之後**絕不能**「切到 ③ 就開始掃」。兩道防線：

1. **預設模式是 A（單檔深掘）** —— 進入本頁不會碰到批次面板的任何一行。
2. **模式 B 仍要先勾一個 checkbox 才載入面板** —— 面板本身會讀磁碟 checkpoint
   （`repositories.batch_checkpoint`），gate 讓那件事也留在使用者的一次點擊之後。
   真正的掃描還要再按面板內的「▶️ 開始 / 繼續分析」，所以掃描總共隔了兩道。

`tests/test_fund_research_merge.py` 以 sentinel（patch 掉底層、驗有沒有真的被呼叫）
守住這條，**不是**字串比對 —— 本 repo 已實證過字串守衛會被檔案自己的說明文字騙過。

⚠️ 尚未接線（刻意）
-------------------
本檔**還沒有**被 `app.py` 掛上去；`render_single_fund_tab` / `render_batch_analysis_tab`
兩個舊入口**原樣保留**。七分頁 → 五分頁的接線屬另一個工作包，
在那之前把 app.py 改掉會讓現行畫面壞掉。

對外 API
--------
- `render_fund_research_tab() -> None`（零參數，與 Tab2/3/5/6 同設計準則）
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.fund_research.code_finder import render_code_finder
from ui.helpers.fund_research.merge_context import (
    PAGE_HEADER,
    SHARED_SEARCH,
    merged_page_owns,
)
from ui.helpers.render_state import not_ready, safe_section
from ui.helpers.story_nav import tab_label

#: 合併頁的頁面大標。
#: ~~⚠️ **寫死在這裡是有代價的、而且是已知的**：全站分頁名的 SSOT 是~~
#: ~~`ui/helpers/story_nav.py::tab_label()`，但它目前只有 `fund` / `batch` 兩個舊 key，~~
#: ~~沒有「基金研究」這個合併後的名字。新增 key 要改 `ui/helpers/story_nav.py` ——~~
#: ~~**不在本工作包的檔案邊界內**，故先在本檔具名成常數（至少同一檔內只有一份），~~
#: ~~並在 PR 描述回報：接線工作包（app.py 七→五）應把它收進 story_nav SSOT。~~
#: **2026-08-31 已收進 SSOT**（有意識的狀態變更，不是漏刪 · 決策者：AI 總管）。
#: 舊註記的理由**仍然成立**：當時 `_TAB_LABELS` 真的沒有 `research` 這個 key，
#: 而新增 key 不在該工作包的檔案邊界內 —— 具名成常數是那個情境下的正解。
#: 被權衡掉的只是那個**前提**：WP-F 接線批次已把 `research` 加進 `_TAB_LABELS`，
#: 該註記自己寫的「接線工作包應把它收進 story_nav SSOT」這件事，就是這一行。
MERGED_TAB_LABEL: str = tab_label("research")

#: 模式切換的兩個選項（線框原文用字，不要改寫）。
MODE_SINGLE: str = "🔍 單檔深掘"
MODE_BATCH: str = "📦 批次掃描"


def _render_shared_top() -> None:
    """共用頂部：頁面大標 + 一句話職責 + 「找代號」工具。兩個模式都看得到。

    ⚠️ 「找代號」工具**單獨隔離**（2026-08-31 補）：它是本頁唯一會**打外部網路**的
    區塊（`tdcc_search_fund` → TDCC / FundClear）。不隔離的話，一次搜尋例外會把
    整個 ③ 打掉 —— 連下面的模式切換鍵與單檔深掘一起消失，而使用者其實只是
    「搜尋失敗」而已。大標與職責句不包：它們不會失敗，包起來只是多一層。
    """
    st.markdown(f"## {MERGED_TAB_LABEL}")
    st.caption("還沒放進組合之前，查一檔或掃一批的體質。")
    safe_section("🔍 找代號", render_code_finder)


def _render_single_mode() -> None:
    """模式 A · 單檔深掘 —— 既有 20 區塊原樣，順序不動。"""
    from ui.tab2_single_fund import render_single_fund_tab

    # 頁面大標與「找代號」工具已由共用頂部畫過 → 子頁不再畫第二份。
    with merged_page_owns(PAGE_HEADER, SHARED_SEARCH):
        render_single_fund_tab()


def _render_batch_mode() -> None:
    """模式 B · 批次掃描 —— 既有 11 區塊原樣，但面板本身放在 checkbox gate 之後。

    gate 的理由寫在模組 docstring：這是全站唯一 30~40 分鐘的長任務，
    「切過來就開始做事」是本次合併最容易踩爆的地方。
    """
    gate_on = st.checkbox(
        "📦 載入批次掃描面板",
        key="fr_batch_gate",
        help="批次掃描一次可跑數百檔（實測 20~45 秒/檔），是全站最長的任務。"
             "面板載入後還要再按「▶️ 開始 / 繼續分析」才會真的開始跑。",
    )
    if not gate_on:
        not_ready("批次掃描面板尚未載入（避免一切換過來就開始讀取進度）",
                  where="上方「📦 載入批次掃描面板」")
        return

    from ui.tab_batch_analysis import render_batch_analysis_tab

    with merged_page_owns(PAGE_HEADER):
        render_batch_analysis_tab()


def render_fund_research_tab() -> None:
    """渲染「③ 🔍 基金研究」合併頁（共用頂部 + 單一模式切換鍵）。

    Caller 不需傳參數（與 Tab2/3/5/6 同設計準則）。
    """
    _render_shared_top()

    st.divider()
    mode = st.radio(
        "模式",
        (MODE_SINGLE, MODE_BATCH),
        horizontal=True,
        label_visibility="collapsed",
        key="fr_mode",
    )

    # ⚠️ 模式本體各自隔離（2026-08-31 補）：兩個模式各自是一整支舊分頁的 body
    # （`render_batch_analysis_tab` / `render_single_fund_tab`）。合併之前它們分屬
    # 兩個頂層分頁、各有 `app.py` 給的一段 try；合併之後共用 ③ 的那一個 try ——
    # 任一模式炸掉會把**共用頂部的「找代號」工具與模式切換鍵一起帶走**，
    # 使用者連換去另一個模式都做不到。走 `safe_section()` 之後，模式本體失敗
    # 只會就地紅燈（顯式顯示 + log + 可展開 traceback，§1 不吞例外），
    # 頂部與切換鍵照常在，使用者切得回去。
    # 守衛：`tests/test_wpf_section_isolation.py`。
    if mode == MODE_BATCH:
        safe_section(MODE_BATCH, _render_batch_mode)
    else:
        safe_section(MODE_SINGLE, _render_single_mode)
