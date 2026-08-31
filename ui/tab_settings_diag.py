"""ui/tab_settings_diag.py —— 「⑤ ⚙️ 設定與診斷」＝ 管理室 ＋ 資料診斷 ＋ 說明書（合併頁）。

客戶拍板的線框：`docs/wireframes/fund-wireframe-final.html` §03「⑤ ⚙️ 設定與診斷」。

這一頁的一句話職責（線框原文）
------------------------------
> **設定連線、維護資料，東西沒抓到的時候來這裡查。**

結構（線框原文）
----------------
> 五個分區，**單頁 + 目錄錨點**，不再加一層分頁。
>
> 現況「說明書」是**全站唯一的三層巢狀分頁**：頂層 7 個 → 參考／診斷 2 個 →
> 說明書 10 個。…新結構若再開子分頁，等於把三層變成三層。
> 改用**一頁到底 + 頂部目錄跳轉**。

→ 故本檔**沒有任何 `st.tabs`**（守衛：`tests/test_settings_diag_merge.py`）。
分區順序照線框：**頂部目錄 → A 連線與帳號 → B 資料維護（＋C 通報）→
D 資料診斷 → E 說明書**。

本批（WP-E）做到哪、刻意不做哪
------------------------------
本檔是**組裝**，不是拆寫：三個既有 render 函式原樣呼叫、順序照線框，
各自頁內內容一行未動。線框對分區的細部重排，屬後續批次，逐項登記如下：

- **B／C 未拆**：線框把管理室拆成「🗄️ 資料維護」與「🔔 通報」兩個分區
  （另建議選股池／除息行事曆搬去 ②，Q7 待客戶拍板）。本批整支
  `render_manage_tab()` 原樣呼叫 —— B、C 同住一個分區，標題如實寫成合區。
- **E 未改**：線框要「10 個子分頁 → 錨點目錄」。本批 `render_manual_tab()`
  原樣呼叫，其內部 `st.tabs` 照舊 —— 在 ⑤ 之下是第二層（可接受），
  不再是現況的第三層；改錨點目錄屬說明書自己的改版批次。
- **D 內的既有問題原樣**：線框標「gone」的「🔄 重新載入總經」按鈕與
  「每次操作都跑的匯率抓取」（tab5_data_guard.py:275）都是 tab5 頁內行為，
  本批不動該檔內容（僅加標題旗標 guard）。本頁的緩解是把整個 D 分區放在
  checkbox gate 之後（見 `_render_diag_section`）。
- **A 的「API 金鑰狀態／NAS Proxy 測試」未從 tab5 抽出**：那兩塊住在
  `render_data_guard_tab()` 深處（:1055／:935-954，量測日 2026-08-31），
  抽出屬 tab5 的拆分批次；本批 A 分區先承接兩個已可承接的對象
  （保單管理橋接 + 抓取診斷細節）。

📌 (d) NAV 匯入雙入口 —— 據實登記，不合併（量測日 2026-08-31）
--------------------------------------------------------------
線框指出「NAV 匯入現在同時存在於管理室與診斷兩頁」，實測兩個入口：

1. `ui/tab_manage.py::_sec_nav_backfill`（:478；expander 標題
   「🗄️ NAV 歷史資料管理（CSV 上傳當基底 + 系統增量更新）」在 :492）
   —— 本頁經 B 分區的 `render_manage_tab()` 帶入。
2. `ui/tab5_data_guard.py::render_data_guard_tab`（區塊標題
   「🗂️ NAV 歷史匯入與累積狀態（保單對帳單 CSV → nav_history）」在 :1489）
   —— 本頁經 D 分區的 `render_data_guard_tab()` 帶入。

→ 合併成線框說的「三個功能一個入口」屬**行為變更**（兩個舊標題都要拿掉、
widget key 與寫入路徑要收斂），留給接線後的收斂批次；**本批兩個入口原樣並存**。
在 ⑤ 內兩者分屬 B／D 兩個分區，D 又在 gate 之後 —— 不會同屏出現兩份。

⚠️ ~~尚未接線（刻意）~~ → **已接線（2026-08-31 WP-F）**
--------------------------------------------------------
~~本檔**還沒有**被 `app.py` 掛上去；`render_manage_tab` / `render_data_guard_tab` /~~
~~`render_manual_tab` 三個舊入口**原樣保留**（旗標全空 → 行為與現在完全相同，~~
~~守衛：`tests/test_settings_diag_merge.py`）。七分頁 → 五分頁的接線屬另一個~~
~~工作包，在那之前把 app.py 改掉會讓現行畫面壞掉。~~

**有意識的狀態更新，不是漏刪**（日期 2026-08-31 · 決策者：AI 總管）。
舊段落在它寫下的當天是對的（WP-E 刻意只做組裝、不接線）；被權衡掉的只是它的
**狀態**：WP-F 已把本檔掛上 `app.py` 的第 ⑤ 個 slot。
**現況**：`app.py` 只 import `render_settings_diag_tab`，三個舊入口
（`render_manage_tab` / `render_data_guard_tab` / `render_manual_tab`）改由本檔
lazy import，**旗標因此恆為持有**（不再是「全空」）——
那三個舊入口自己畫 `##` 大標的分支在 production **恆不觸發**，
各該檔已就地註明。守衛：`tests/test_settings_diag_merge.py`（檔名未變）
＋ `tests/test_wpf_five_tab_wiring.py`。

對外 API
--------
- `render_settings_diag_tab() -> None`（零參數，與 Tab2/3/5/6 同設計準則）
"""
from __future__ import annotations

import streamlit as st

from ui.helpers.render_state import not_ready, safe_section
from ui.helpers.settings_diag.fetch_diag_section import render_fetch_diag_from_session
from ui.helpers.settings_diag.merge_context import (
    DATA_GUARD_HEADER,
    MANAGE_HEADER,
    MANUAL_HEADER,
    settings_page_owns,
)
from ui.helpers.settings_diag.policy_admin_bridge import render_policy_admin_bridge
from ui.helpers.story_nav import tab_label

#: 合併頁的頁面大標。
#: ~~⚠️ **寫死在這裡是有代價的、而且是已知的**（WP-C 同款處置）：全站分頁名的~~
#: ~~SSOT 是 `ui/helpers/story_nav.py::tab_label()`，但它目前沒有「設定與診斷」~~
#: ~~這個合併後的名字。新增 key 要改 `ui/helpers/story_nav.py` ——~~
#: ~~**不在本工作包的檔案邊界內**，故先在本檔具名成常數（至少同一檔內只有一份），~~
#: ~~並在 PR 描述回報：接線工作包（app.py 七→五）應把它收進 story_nav SSOT。~~
#: **2026-08-31 已收進 SSOT**（有意識的狀態變更，不是漏刪 · 決策者：AI 總管）。
#: 理由同 `ui/tab_fund_research.py` 該處：舊註記在它寫下的當天是對的（`settings`
#: 那時真的不在 `_TAB_LABELS` 裡），只是它自己指名的那個「接線工作包」就是 WP-F。
MERGED_TAB_LABEL: str = tab_label("settings")

#: 目錄錨點（Streamlit 對中文標題的自動 anchor 不可靠 → 顯式指定）。
ANCHOR_CONN: str = "sd-sec-conn"
ANCHOR_MAINT: str = "sd-sec-maint"
ANCHOR_DIAG: str = "sd-sec-diag"
ANCHOR_MANUAL: str = "sd-sec-manual"


def _render_shared_top() -> None:
    """頂部：頁面大標 + 一句話職責 + 目錄列（線框「頂部・目錄」分區）。"""
    st.markdown(f"## {MERGED_TAB_LABEL}")
    st.caption("設定連線、維護資料，東西沒抓到的時候來這裡查。")
    # 目錄列：點擊跳到該分區（線框建議項；anchor 對應各分區 subheader）。
    # 線框列 5 項（連線與帳號 · 資料維護 · 通報 · 資料診斷 · 說明書）；
    # 本批 B／C 未拆（見模組 docstring），故目錄如實列 4 項，通報併在資料維護內。
    st.markdown(
        f"[🔌 連線與帳號](#{ANCHOR_CONN}) · "
        f"[🗄️ 資料維護與通報](#{ANCHOR_MAINT}) · "
        f"[🔭 資料診斷](#{ANCHOR_DIAG}) · "
        f"[📖 說明書](#{ANCHOR_MANUAL})"
    )


def _render_conn_section() -> None:
    """A · 🔌 連線與帳號 —— 本批承接兩塊：保單管理橋接（旗標關閉）＋ 抓取診斷細節。"""
    st.subheader("🔌 連線與帳號", anchor=ANCHOR_CONN)

    # ── 保單管理（Google Sheets）承接 ──────────────────────────────────
    # ⚠️ 預設由旗標關閉（POLICY_ADMIN），這一批不切換。切換前必須先處置的
    #    session_state 先寫後讀耦合，**清單在 `ui/tab3_portfolio.py` 的
    #    「⚠️ 為什麼用 container 佔位」註解區**（#736 兩輪稽核留下的施工指南）：
    #    `portfolio_core_pct`／`policy_sheet_id`／`gsheet_tokens`／`_schema_ver`
    #    —— 該處明標「**已知清單，不是窮舉**」。把保單管理搬到 ④ 之後執行
    #    會讓 ④ 讀到舊值；**接線批次切換旗標前必須先重掃並處置耦合**，
    #    完整前置（含 sheet_client SSOT 抽出）見 `policy_admin_bridge` docstring。
    render_policy_admin_bridge(sheet_client=None)

    # ── 🔍 抓取診斷細節（從個基頁搬入；線框 A 分區「搬入」項）──────────
    # 區塊本體與個基頁共用同一份（ui/helpers/settings_diag/fetch_diag_section.py）；
    # 個基頁那份由 FETCH_DIAG 旗標控制。
    # ~~本批旗標全空 → 個基頁行為不變。~~
    # ⚠️ 2026-08-31 WP-F 接線後就地更正（**有意識的更正，不是漏刪**）：
    # `app.py` 已把五個分頁全部包進 `with settings_page_owns(FETCH_DIAG)`
    # → 旗標**恆為持有**，個基頁那份**恆不畫**，抓取診斷只由本行畫一次。
    render_fetch_diag_from_session()


def _render_maintain_section() -> None:
    """B（🗄️ 資料維護）＋ C（🔔 通報）—— 本批以整支管理室原樣承接，不拆。"""
    st.subheader("🗄️ 資料維護與通報（管理室）", anchor=ANCHOR_MAINT)
    from ui.tab_manage import render_manage_tab

    # ⑤ 已畫分區標題 → 管理室不再畫自己的 `##` 頁面大標（其餘一行不動）。
    with settings_page_owns(MANAGE_HEADER):
        render_manage_tab()


def _render_diag_section() -> None:
    """D · 🔭 資料診斷 —— 原樣搬入，但整區放在 checkbox gate 之後。

    gate 的理由（本檔最重要的一條）：`render_data_guard_tab()` 的開頭有一次
    **無條件的匯率抓取**（tab5_data_guard.py:275，線框已點名）＋ caller 契約
    要求先跑 `_update_data_registry()`。在單頁合併的 ⑤ 裡，這些會跟著本頁
    **每一次互動**重跑 —— gate 讓重運算留在使用者的一次點擊之後
    （硬性紀律「重運算在 gate 後」；WP-C 批次面板同款處置）。
    tab5 自己頁內既有的 gate 與 EX-UICACHE-1 快取**語意未動**（本批只包裝）。
    """
    st.subheader("🔭 資料診斷", anchor=ANCHOR_DIAG)
    gate_on = st.checkbox(
        "🔭 載入資料診斷",
        key="sd_diag_gate",
        help="診斷區載入時會更新資料註冊表並抓取匯率等即時狀態。"
             "沒遇到問題時可以完全略過（診斷頁自己的說明原文）。",
    )
    if not gate_on:
        not_ready("資料診斷尚未載入（避免每次互動都重跑註冊表更新與匯率抓取）",
                  where="上方「🔭 載入資料診斷」")
        return

    # caller 契約（tab5_data_guard.py docstring）：呼叫前先更新 data_registry。
    # 與 app.py 現行「參考 / 診斷」分頁的呼叫方式完全同款。
    from ui.helpers.data_registry import _update_data_registry
    from ui.tab5_data_guard import render_data_guard_tab

    _update_data_registry()
    # ⑤ 已畫分區標題 → 診斷頁不再畫自己的 `##` 頁面大標（其餘一行不動）。
    with settings_page_owns(DATA_GUARD_HEADER):
        render_data_guard_tab()


def _render_manual_section() -> None:
    """E · 📖 說明書 —— 原樣承接；10 子分頁 → 錨點目錄屬後續批次（見模組 docstring）。"""
    st.subheader("📖 說明書", anchor=ANCHOR_MANUAL)
    from ui.tab6_manual import render_manual_tab

    # ⑤ 已畫分區標題 → 說明書不再畫自己的 `##` 頁面大標（其餘一行不動）。
    with settings_page_owns(MANUAL_HEADER):
        render_manual_tab()


def render_settings_diag_tab() -> None:
    """渲染「⑤ ⚙️ 設定與診斷」合併頁（單頁 + 目錄，分區順序照線框）。

    Caller 不需傳參數（與 Tab2/3/5/6 同設計準則）。

    ⚠️ **每個分區各自隔離（2026-08-31 補；本頁最重要的一條）**
    ------------------------------------------------------------
    七→五之前，「🗄️ 資料維護與通報」（舊 `tab_manage`）與「🔭 資料診斷 / 📖 說明書」
    （舊 `tab_ref`）分屬**兩個頂層分頁**，各有 `app.py` 給的一段 try —— 管理室炸掉
    不會影響診斷頁。合併成 ⑤ 一頁之後，它們共用 ⑤ 的那**一個** try：
    **管理室當掉會一併帶走 🔭 資料診斷與 📖 說明書。**
    而那兩塊正是使用者出事時要去的地方（本頁一句話職責：「東西沒抓到的時候來這裡查」）
    —— 把診斷跟故障綁在同一條命上，等於在最需要它的時候把它拿走。

    故四個分區各自走 `safe_section()`：一個分區炸掉就地紅燈（顯式顯示 + log +
    可展開 traceback，`CLAUDE.md §1` 不吞例外），其餘三個照常渲染。
    這也讓 `app.py:317-318` 那句「內層各頁自己的 `_safe_section` 再做 section 級
    細粒度隔離」對本頁**由假變真** —— 在此之前本頁一個 `_safe_section` 都沒有。

    守衛：`tests/test_wpf_section_isolation.py`。
    """
    # 頂部（大標 + 目錄）不包 —— 它一炸就沒有目錄可以跳，包起來只是讓使用者
    # 對著一個沒有入口的空頁；那種情況就該讓 app.py 的分頁級隔離接手。
    _render_shared_top()

    st.divider()
    safe_section("🔌 連線與帳號", _render_conn_section)

    st.divider()
    safe_section("🗄️ 資料維護與通報", _render_maintain_section)

    st.divider()
    safe_section("🔭 資料診斷", _render_diag_section)

    st.divider()
    safe_section("📖 說明書", _render_manual_section)
