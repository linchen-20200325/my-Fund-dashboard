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

⚠️ **2026-08-31 狀態更新（決策者：AI 總管；依據：客戶拍板線框 §03 PAGE 5「E · 📖 說明書」）**
上面那段**是線框原文的逐字引用，故不在引文內畫刪除線**（在逐字引用上動刀＝竄改引用本身，
同 `CLAUDE.md §-1.5.1a` 對 user 原文的處置慣例）；狀態更新改寫在引文外，就是這一段。
**它描述的「現況」已經不成立**：說明書那 10 個子分頁已於 2026-08-31 改為**單頁 + 錨點目錄**
（`ui/tab6_manual.py::_CHAPTERS` + `_render_toc()`，守衛 `tests/test_manual_anchor_toc.py`），
~~**全站最後一層巢狀 `st.tabs` 自此消失**。~~
**⑤ 這一頁自此沒有任何巢狀 `st.tabs`。**
⚠️ **2026-09-01 就地更正（有意識的更正，不是漏刪 · 日期 2026-09-01 ·
決策者：AI 總管 · 依據：實測 `git grep -n -F ".tabs(" -- '*.py'`）**：
舊表述是**現在式全稱句、而且是假的** —— `ui/tab3_t7_ledger.py::render_t7_section`
的 A/B/C 再平衡子分頁**仍然會渲染出巢狀 tab-list**（經 `ui/tab3_portfolio.py`
在頂層分頁 ④ 內呼叫）。**它跟 ⑤ 無關，所以本檔的改動從來就沒有讓它消失。**
**舊表述不是「當天對、後來過期」，是寫下的當天就已經不成立** ——
它想講的其實只是「⑤ 這一頁不再有巢狀分頁」（那句是真的），
卻寫成了涵蓋全站的宣稱。**現行改為只講本頁，範圍與證據對得上。**
⚠️ **2026-09-01 第八輪：上面那道證據指令改寫了寫法。有意識的更正，不是漏刪 ·
決策者：AI 總管。** 原本是 **`-nE` 正則版**（`.` 與 `(` 各自用反斜線跳脫），
現改為 **`-n -F` fixed-string 版**（見上一段引用的指令）。
**理由不是嫌它醜，是它會製造警告**：反斜線寫在**非 raw 的 docstring** 裡，
Python 會對那個跳脫序列發 `SyntaxWarning: invalid escape sequence`，
而它**已經出現在 pytest 的 warnings summary 上**
（`<unknown>:1: DeprecationWarning: invalid escape sequence`）——
本 PR 花了八輪清自己留下的假敘述，不該同時留一條自己製造的雜訊。
**兩個版本的輸出已實測逐字節相同**（`diff` 無差異），故**證據力未被削弱**，
換掉的只是寫法。⚠️ **刻意不寫「共 N 行」** —— 那是會漂移的量測值
（`CLAUDE.md` 引的姊妹 repo `§8.2.A.0 規則 4`）；**本輪初稿寫了「各 23 行」，
而同一次編輯就把它變成 24** —— 因為改寫後**上一行那道指令本身**
（fixed-string 版）**會被自己掃到**，正則版則因為跳脫字元而掃不到。
**要複驗請直接重跑上面那道指令並自行比對，不要引用任何寫死的數字。**
⚠️ **這段註記本身第一次也寫錯了，值得記一筆**：初稿為了「保留原指令」而把
舊寫法**原樣抄進來**，於是**在同一次編輯裡把剛拔掉的警告又種了回去**
（`compile()` 當場復現）。**要拔掉一個字元，就不能在說明它的句子裡再打一次。**
→ **通則：docstring／註解裡引用指令一律避開反斜線**；真的非引用不可，
整段改 raw 字串（三引號前加前綴 `r`）。
⚠️ **同一段還踩了第二顆雷**：初稿把那個 raw 前綴連同**三個引號**一起寫進來，
當場把這段 docstring 提前收掉（`SyntaxError`）。**在三引號字串裡不要打三引號** ——
本檔已改成用文字描述。**兩顆雷都是同一種病：示範一個寫法時，把它照著打了一次。**
📌 同型的假宣稱另有兩處，**同批一併更正**：`app.py` 註解「巢狀 st.tabs 一併消失」、
以及 **PR 標題**（標題會成為 merge commit 的 subject）。
**引文的理由仍然成立、而且正是它促成了這次改動** —— 它精準描述了改動前的病
（「一份公式要點三次才看得到」）；**被權衡掉的只是它的時態**：它寫的是**當時的現況**，
不是**永久的事實**。⚠️ **不得**把這段引文讀成「說明書現在還有 10 個子分頁」。

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
- ~~**E 未改**：線框要「10 個子分頁 → 錨點目錄」。本批 `render_manual_tab()`~~
  ~~原樣呼叫，其內部 `st.tabs` 照舊 —— 在 ⑤ 之下是第二層（可接受），~~
  ~~不再是現況的第三層；改錨點目錄屬說明書自己的改版批次。~~
  → **2026-08-31 就地更正：E 已改，本段自那一刻起是假的。**
  **有意識的變更，不是漏刪**（日期 **2026-08-31** · 決策者：**AI 總管** ·
  依據：客戶拍板線框 `docs/wireframes/fund-wireframe-final.html` §03 PAGE 5）。
  **舊表述在它寫下的當天是對的**：WP-E 確實只做組裝、`render_manual_tab()` 內部
  當時真的還有一層 `st.tabs`，而「屬說明書自己的改版批次」這個範圍判斷也沒錯 ——
  **被權衡掉的只是它的狀態**：它自己指名的那個「說明書自己的改版批次」**已經做完了**。
  **現況**：`ui/tab6_manual.py` 改為**單頁 + 錨點目錄**（章節 SSOT `_CHAPTERS`
  ＋ `_render_toc()`），**其內部已無任何 `st.tabs`**，守衛
  `tests/test_manual_anchor_toc.py::test_manual_has_no_nested_tabs`（AST、alias 不敏感）。
  ⚠️ **一句「E 未改」會讓下一個人以為那層 `st.tabs` 還在，進而據此規劃根本不存在的工作** ——
  這正是本 repo 一再點名的失效模式（沒查證的敘述比沒有敘述更危險）。
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

⚠️ **2026-09-02 就地更正：上面整段是舊狀態，那個「收斂批次」已經做完了。**
**有意識的變更，不是漏刪**（日期 **2026-09-02** · 決策者：**AI 總管** ·
依據：客戶拍板線框 §03 ⑤ B「合一 NAV 歷史 —— 三個功能一個入口」）。
**舊表述在它寫下的當天是對的**（WP-E 確實刻意不合併，理由「屬行為變更」也沒錯）；
**被權衡掉的只是它的狀態**。
**現況**：兩個舊入口都由 `merge_context.NAV_HISTORY` 旗標守住（⑤ 持有 → 兩邊都不畫），
唯一一份由 `ui/helpers/settings_diag/nav_history_section.py::render_nav_history_section()`
在 B 分區畫出來，標題為「🗄️ NAV 歷史」，**兩個舊標題都不留**。
⚠️ **合的是入口，不是實作** —— 三條寫入路徑實測**行為不等價**
（多檔/單檔、代號來源、寫本機/只寫雲端、CSV 要不要代號欄），
**一條都沒有刪**，只是收到同一個標題底下。逐項對照見該 helper 的模組 docstring。
⚠️ 舊表述那句「D 又在 gate 之後 → 不會同屏出現兩份」**當時就只是緩解，不是解法**：
使用者只要勾了診斷 gate 就會同屏看到兩份。守衛：
`tests/test_ia_tab5_nav_history_merge.py`（gate 開著也只有一份）。

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
    NAV_HISTORY,
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
    """B（🗄️ 資料維護）＋ C（🔔 通報）—— 本批以整支管理室原樣承接，不拆。

    ⚠️ **2026-09-02 就地更新：NAV 歷史已收成合一入口**（有意識的變更，不是漏刪 ·
    決策者：AI 總管 · 依據：客戶拍板線框 §03 ⑤ B「合一 NAV 歷史 —— 三個功能一個入口」）。
    模組 docstring 的「📌 (d) NAV 匯入雙入口 —— 據實登記，不合併」那一段
    **自本次起是舊狀態**，就地更正見該處。
    """
    st.subheader("🗄️ 資料維護與通報（管理室）", anchor=ANCHOR_MAINT)
    from ui.helpers.settings_diag.nav_history_section import (
        render_nav_manual_section,
        render_nav_status_section,
    )
    from ui.tab_manage import render_manage_tab

    # ⑤ 已畫分區標題 → 管理室不再畫自己的 `##` 頁面大標（其餘一行不動）。
    # ⑤ 同時持有 NAV_HISTORY → 管理室**不畫**它自己那份「🗄️ 補歷史淨值」，
    # 資料診斷那份「🗂️ NAV 歷史匯入與累積狀態」同樣不畫（見各該檔的極性守衛）；
    # 唯一一份由下面兩個區塊畫出來。
    #
    # ⚠️ **這裡的擺法是過渡狀態，據實寫明**：線框 `ia-wireframe.html` Tab 05 的
    #    最終順序是「資料來源健康度 → NAV 累積狀態 → 連線與金鑰 → 手動補資料 →
    #    使用手冊」，兩塊之間**夾著「連線與金鑰」**。把 ⑤ 重組成那五塊屬 **T18 批次**
    #    （T18 本來就要動「連線與金鑰」，同一塊不能兩批同時改），**本批不做**。
    #    本批只把 NAV 由「一塊」拆成「兩塊」並維持**狀態在前、寫入在後**的相對順序 ——
    #    T18 之後在中間插入「連線與金鑰」時，這個相對順序仍然成立，守衛也不必改。
    with settings_page_owns(MANAGE_HEADER, NAV_HISTORY):
        render_manage_tab()
        st.divider()
        render_nav_status_section()
        st.divider()
        render_nav_manual_section()


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
    # ⚠️ **`NAV_HISTORY` 在這裡也要持有，而且這一項最容易漏** —— 所有權是
    #    thread-local ＋ context manager 作用域，B 分區那個 `with` 一離開就還原了。
    #    漏掉它的後果不是報錯，是「🗂️ NAV 歷史匯入與累積狀態」**又在 D 分區畫一次**，
    #    合一當場失效而且沒有任何東西會叫。守衛：
    #    `tests/test_ia_tab5_nav_history_merge.py::test_whole_page_renders_exactly_one_nav_entry`。
    with settings_page_owns(DATA_GUARD_HEADER, NAV_HISTORY):
        render_data_guard_tab()


def _render_manual_section() -> None:
    """E · 📖 說明書 —— 原樣承接（本節只畫分區標題 + 委派，頁內內容一行未動）。

    ~~10 子分頁 → 錨點目錄屬後續批次（見模組 docstring）~~
    → **2026-08-31 就地更正：那個「後續批次」已完成，本句自那一刻起是假的。**
    **有意識的變更，不是漏刪**（日期 **2026-08-31** · 決策者：**AI 總管** ·
    依據：客戶拍板線框 §03 PAGE 5）。**舊句在它寫下的當天是對的**（WP-E 確實只做組裝，
    也正確地把改版劃到說明書自己的批次）；**被權衡掉的只是它的狀態**。
    **現況**：`ui/tab6_manual.py` 已是**單頁 + 錨點目錄**、內部無 `st.tabs`。
    詳見模組 docstring 的「E 未改」該項更正與 `tests/test_manual_anchor_toc.py`。
    """
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
