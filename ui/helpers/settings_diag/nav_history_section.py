"""⑤ 的 NAV 兩塊 —— 「NAV 累積狀態」（唯讀）與「手動補資料」（寫入類）。

客戶拍板線框：`docs/wireframes/ia-wireframe.html` **Tab 05**（2026-09-01）。
該檔把 ⑤ 定為五塊，順序為：

    資料來源健康度 → **NAV 累積狀態** → 連線與金鑰 → **手動補資料** → 使用手冊

其中：

> **NAV 累積狀態** — 42 檔 · 最長 6.2 年。雲端歷史涵蓋度，逐檔可展開。
> **手動補資料** — CSV 匯入淨值歷史、一鍵補抓、逐檔結果。**寫入類動作，全部 Form 封裝。**

⚠️ **它取代了較舊的 `fund-wireframe-final.html` §03「三個功能一個入口」**
（有意識的政策變更，不是漏刪 · 日期 **2026-09-02** · 決策者：**AI 總管**）。
**舊線框的理由仍然成立** —— NAV 匯入分散在兩個分頁、連名字都不一樣，確實要收；
**被權衡掉的是它的切法**：新線框改用「**唯讀狀態** vs **寫入動作**」切，
而不是「全部塞進一個入口」。**兩份線框只有後者被客戶 2026-09-02 再次核准。**

⭐ 「兩塊」不代表可以刪功能 —— 三條寫入路徑實測不等價
------------------------------------------------------
動工前實測，三條路徑吃的東西與寫的地方都不同，**挑一條留＝刪功能**：

| 路徑 | 實作 | 代號怎麼來 | 寫到哪 | CSV 形狀 |
|---|---|---|---|---|
| 一鍵自動補全 | `nav_history_store.backfill_to_gs` | 持倉 ∪ 選股池，自動 | 本地 cache ＋ 雲端 | 不吃 CSV（連外抓） |
| 對帳單 CSV | `nav_history_gs.import_csv_text` | **使用者手填**，單檔 | **只寫雲端** | 兩欄即可（日期｜淨值） |
| 本地基底 CSV | `nav_history_store.import_nav_csv_multi` | **讀自 CSV 代號欄**，可多檔 | 本地 cache ＋ 雲端 | **必須有代號欄** |

砍掉「對帳單」那條 → 保險公司匯出的兩欄 CSV 匯不進來（它沒有代號欄）。
砍掉「本地基底」那條 → `cache/nav_history/{code}.json` 沒有人寫得進去，
而健診／長期報酬會優先讀它。**三條全留，全部收進「手動補資料」這一塊。**

⚠️ 區塊順序：狀態在前，寫入在後 —— 但**不相鄰**
------------------------------------------------
雲端沒啟用時，「手動補資料」的三條路徑**都寫不進雲端**，所以狀態必須先被看到
（`CLAUDE.md §1`：不可讓流程看起來成功）。但線框在兩者之間夾了「連線與金鑰」，
所以守衛錨的是**兩個區塊的相對順序**，**不是相鄰** ——
錨到相鄰會在 ⑤ 依線框重組（T18）的當天無故轉紅。

⚠️ 本模組不含任何取數／寫入實作：三塊的本體仍住在 `ui/tab_manage.py` 與
`ui/tab5_data_guard.py`，本模組只負責**分塊與擺放**。把實作也搬過來會變成
「同一份邏輯兩個地方」，正是這一批要消滅的東西。
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.story_nav import section_label

#: 兩個區塊的標題。**吃 `story_nav` SSOT，不手抄** —— 手抄的那一刻它就開始漂移，
#: 而本 repo 的「指路指到不存在的東西」已經發作過三次。
#: 漂移鎖：`tests/test_story_nav.py::test_section_labels_match_merged_pages`。
NAV_STATUS_HEADING: str = f"### {section_label('nav_status')}"
NAV_MANUAL_HEADING: str = f"### {section_label('nav_manual')}"


def render_nav_status_section() -> None:
    """線框 Tab 05 第 2 塊「NAV 累積狀態」—— **唯讀**：能不能累 ＋ 累了多少。

    這一塊**不含任何寫入動作**（那些全在「手動補資料」）。它回答的是
    「我的歷史淨值到底有沒有在累、累到哪一天」，而那正是下一塊的前提。
    """
    from ui.tab5_data_guard import render_nav_accumulation_status

    st.markdown(NAV_STATUS_HEADING)
    st.caption("雲端 `nav_history` 的涵蓋度：有沒有在累積、每一檔補到哪一天。"
               "**這一塊只看不寫** —— 要補資料請用下方的「"
               f"{section_label('nav_manual')}」。")
    render_nav_accumulation_status()


def render_nav_manual_section() -> None:
    """線框 Tab 05 第 4 塊「手動補資料」—— **寫入類，全部 Form 封裝**。

    三條路徑並列（實測不等價，見模組 docstring 的對照表）：
    ① 一鍵自動補抓　② 對帳單 CSV（只寫雲端）　③ 本地基底 CSV（多檔，寫本機 cache）。

    ⚠️ **一個 Form 封裝上的硬限制，據實寫明（不是偷懶）**：③ 那條底下的
    「📤 下載當前 cache 為 CSV」用的是 `st.download_button`，而 Streamlit
    **在原始碼層面無條件禁止它出現在 `st.form` 內**
    （`streamlit/elements/widgets/button.py`：``st.download_button() can't be used
    in an st.form()`` → `StreamlitAPIException`，且該檢查**沒有** `runtime.exists()`
    的豁免）。故 ③ 的**上傳**包在 form 內，**逐檔的增量／下載／清除維持在 form 外**。
    這是平台限制，不是選擇；硬包會讓整塊在 render 時當場炸掉。
    """
    from ui.tab5_data_guard import render_nav_statement_csv_import
    from ui.tab_manage import (
        render_nav_backfill_auto_section,
        render_nav_csv_manage_section,
    )

    st.markdown(NAV_MANUAL_HEADING)
    st.caption(
        "系統抓不到的歷史淨值在這裡補。**三條路徑吃的 CSV 形狀不一樣，不是重複功能**："
        "① 讓系統自己抓（不用 CSV）；② 對帳單 CSV 只要「日期｜淨值」兩欄、代碼你自己填、"
        "只寫雲端；③ 基底 CSV 要「代號｜日期｜淨值」、可一次多檔，而且會寫進本機 cache。"
    )

    # ① 系統自己抓 —— 先給最省事的那條
    render_nav_backfill_auto_section()

    st.divider()
    # ② 對帳單 CSV（單檔、代碼手填、只寫雲端）
    render_nav_statement_csv_import()

    st.divider()
    # ③ 本地基底 CSV（多檔、代號讀自 CSV、寫本機 cache ＋ 雲端）＋ 逐檔增量／下載／清除
    render_nav_csv_manage_section(
        expander_label="🗄️ 進階：「代號｜日期｜淨值」CSV 當本機基底（多檔）＋ 增量更新／備份")
