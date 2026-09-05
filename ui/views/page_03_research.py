"""③ 標的探索 —— 五分頁動線重構的第三頁（全新撰寫，非舊三個 `tab*.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。
客戶方針（2026-09-05）：本頁**只做骨架 + 灰態**；結果卡、深度區與批次的真內容**分批填**。

整頁骨架 —— 逐字取自已核准線框 `docs/wireframes/ia-wireframe.html` 的 **Tab 03**
------------------------------------------------------------------------------

===== ====================================== ==========================================
順序   區塊                                    版面
===== ====================================== ==========================================
1      Form — 唯一搜尋入口（代碼或名稱／來源）    `applied_form`，按「搜尋」才算
2      搜尋結果                                 3 欄結果卡
3      單一基金深度                             五個區塊（3 欄 ×3 ＋ 大表全寬 ×2）＋ 來源標註
4      批次分析                                 **全寬大表**；Form 後才跑
–      還沒開始搜尋                             空狀態三要素（取代 2～4）
===== ====================================== ==========================================

⚠️ 第 3、4 塊的名字曾被登記為「兩份已核准線框衝突」，**2026-09-05 總管裁決以本線框字面為準**；
沿革與那條具名守衛豁免的理由寫在 :data:`BLOCK_DEEP` 上方那段 ⛔ 註解。

線框同時釘死了本頁的**職責邊界**，這一條比版面更要緊：

> 回答一個問題：**有沒有更好的標的？** 這裡的基金**不預設我有持有**。

⛔ **因此本頁不放**（線框「這裡不放什麼」逐字）：
   「我持有部位的健康度 → **02**」「『要不要換成這檔』的試算 → **04**」。
   下一批填內容時，看到 `services/health` / `services/switch_*` / `services/rotation.py`
   這類**診斷我的持倉**或**建議我怎麼換**的服務要停手 —— 它們的落點是 ② 與 ④。
   ⚠️ 反過來也要擋：本頁**不得**去讀 `st.session_state["portfolio_funds"]`
   來「順便標出我已經持有哪幾檔」——「不預設我有持有」是線框畫底線的那半句。

⛔ **不修補舊三頁，也不委派它們。** 線框「從哪裡搬來」列的
   `ui/tab2_single_fund.py`（深度區）／`ui/tab_fund_research.py`（搜尋與比較）／
   `ui/tab_batch_analysis.py`（批次）依方針第 3 條會在五頁驗收完成後**整批拔除**。
   本檔**一行都不 import 它們** —— 每多一條委派，那一刻就多一處會斷頭。
   ⚠️ 這一點是 ① 的既有教訓：`ui/views/page_01_macro.py` 留了一條對
   `ui/tab1_macro_midcycle.py` 的委派，它自己的 docstring 就登記著
   「有效期到舊 tab 整批拔除為止」。**本檔一條都沒有**（② `page_02_health.py` 亦然）。

⚠️ **本頁本批尚未接進 `app.py`。** `app.py` 的 ③ 仍呼叫舊的
   `render_fund_research_tab()`，客戶明令「舊分頁這批不動、不接線、不下架」。
   接線是下一批的事 —— 骨架先上線、CI 綠、再分批填內容。

線框的一處**內部歧義**，以及本檔取哪一種讀法（不要略過這一段）
--------------------------------------------------------------
線框「單一基金深度」那張卡的原文是：

> 選定後展開：NAV 走勢 · 績效分期 · 風險指標 · 前十大持股 · 配息紀錄 · 資料來源與抓取時間。
> **五個區塊各自 3 欄，持股與配息為大表全寬。**

**冒號後列了六項，句子卻說「五個區塊」** —— 兩種讀法都講得通：

- **讀法 A（本檔採用）**：五個區塊 ＝ NAV 走勢／績效分期／風險指標／前十大持股／配息紀錄；
  「資料來源與抓取時間」是**來源標註**，不是內容區塊。
  佐證：那張卡的三個 chip 正好是「3 欄」「大表全寬」「**來源標註**」——
  第三個 chip 單獨點名了它，形狀上就是「另一種東西」而不是「第六個區塊」。
- **讀法 B**：六個區塊，「五個」是筆誤。

⚠️ **本檔取讀法 A，但這是解讀不是事實**（`CLAUDE.md §-2` 規則 6）——
本組沒有向客戶求證，也沒有第二組驗過。
**取捨的方式是「兩種讀法下都不會少畫東西」**：`資料來源與抓取時間`
照樣有自己的段落與自己的灰態（否則突變拿掉它不會轉紅），
只是在語意上被歸為**標註**而不是第六個內容區塊。
⛔ 若客戶認定是讀法 B，要改的只有註解與 :data:`DEEP_DIVE_PROVENANCE` 的歸類，
**畫面一格都不用動** —— 這正是選這個處理方式的理由。

為什麼「還沒搜尋」就把下面三塊整個藏起來
--------------------------------------
線框在 Tab 03 給了兩個**條件**：批次分析的 chip 寫「**Form 後才跑**」（長時間運算），
單一基金深度寫「**選定後**展開」。骨架階段：

- **「Form 後才跑」照做** —— 沒有送出過搜尋，下面**一塊都不畫**（鐵則 04 首屏無冗餘占位），
  只留空狀態三要素。
- ⚠️ **「選定後展開」本批做不到，據實登記而不是假裝有做**：骨架階段**沒有任何東西可以被選定**
  （結果卡還沒接上），若照字面「選定後才畫」，深度區在本批**永遠不會被渲染** ——
  等於既沒有骨架、也沒有守衛。故本批在送出搜尋後**一律畫出深度區的灰態**。
  ⛔ **下一批接上結果卡時，這個 gate 必須恢復**，屆時
  `tests/test_wf03_research_skeleton.py` 的順序斷言會轉紅 ——
  **正解是把它改成「選定後才展開」的 gate 驗證，不是把斷言放寬。**

資料從哪裡來（下一批的入口，以及一個**現在就要知道的缺口**）
------------------------------------------------------------
⚠️ **本批沒有任何 `services/**` 呼叫** —— 骨架階段沒有東西要算。
下一批填內容時，取數一律走 `services/**` 的 public 函式；本組**實地確認存在**的有：
`services.fund_service.fetch_fund_by_key_enriched` /
`services.fund_service.fetch_fund_from_moneydj_url_enriched`（單檔深度）、
`services.fund_row.process_one_fund`（批次單檔 worker）。
⚠️ 這串是**看到的**，**不是**「這些就夠了」的宣稱 —— 夠不夠要等真的去接才知道。

⛔ **缺口，先寫在這裡免得下一批當場自己發明**：**「搜尋」在 L2 沒有入口。**
   本組實測 `services/**` 沒有任何 fund 搜尋函式；現行搜尋實作住在 **L1**
   （`repositories.fund.tdcc_search_fund`），UI 直呼它走的是憲法 §8.2.A.1
   **已登記的 `EX-PASSTHRU-1` 例外**（該列現行登記的呼叫點是
   `ui/helpers/fund_research/code_finder.py::_search`）。
   → 下一批**不得**擅自新增一層 L2 facade（那是動後端邊界，本批方針明禁），
   也**不得**直接多開一個 UI 呼叫點就算了 —— `EX-PASSTHRU-1` 該列自己寫著
   「**本 fetcher 出現第二個 UI caller**」就是它的**升級觸發條件**。
   **兩條路都要總管裁決，不是執行組自己選。**
   ⚠️ 本段的「`services/**` 沒有搜尋入口」是**單組 grep 的全稱句，未經第二組驗證**。

三態與空狀態：兩種灰的理由不同，文案必須分開
------------------------------------------
- **還沒開始搜尋** → 線框 Rule 04 的空狀態三要素，指路回本頁上方的搜尋條件
  （使用者**照著做真的能解決**「沒有查詢條件」這件事）。
- **送出了、但這一塊的內容還沒填** → 「本頁分批上線」的灰態（:data:`_PENDING_NOTE`）。
  ⚠️ 這兩句混成一句，會讓使用者以為「輸入代碼按下去就會出現結果」—— 不會。
  同樣的分岔在 ① 與 ② 都做過一次（`page_01_macro.py::_detail_pending`、
  `page_02_health.py::_pending_where`）。

⛔ **線框裡的示意值一個都不准畫**（`CLAUDE.md §1`）：那三張結果卡的
   基金名、`ACDD19` / `0P00000XYZ`、`+12.4%` / `Sharpe 0.81` / `+3.1%` / `0.22`
   全部是線框用來示範版面的假數字。填一個看起來合理的績效，使用者**完全看不出它是假的**，
   而且會拿它去決定要不要買。
   ⚠️ **唯一的例外是 :data:`_CODE_PLACEHOLDER`**，理由見該常數的註解。

四大鐵律的落點（本檔不自己實作任何一條，一律走既有共用元件）
------------------------------------------------------------
- **鐵則 01 三欄網格** → `ui.helpers.ia.render_cards`。**本檔沒有任何 `st.columns` 呼叫。**
  ⚠️ **這裡曾寫「自己寫會讓 `GRID_EXEMPT_CALL_TOTAL`（精確 `==` 90）轉紅」——那是假的，
  已於 2026-09-05 由獨立紅隊實測推翻**：加 `st.columns(3)`（＝鐵則 01 叫你開的那個）
  → **全綠**；`st.columns(2)` → 2 failed。那個計數器抓的是「**欄數不是 3**」的呼叫，
  **合規的 3 欄它一動也不動**。
  → **「本頁不得自己開網格」這條，只有 `tests/test_wf03_research_skeleton.py::`
  `test_the_page_draws_no_grid_or_form_of_its_own` 在守。**
  留著那句假話，下一個人會以為有一道其實不存在的網子。
- **鐵則 02 Form 防重繪** → `ui.helpers.ia.applied_form`。**本檔沒有任何 `st.form(` 站點**
  —— 自己寫會讓 `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==` 7）轉紅。
- **鐵則 03 三態顏色** → `ui.helpers.render_state`（灰態直接用 `not_ready`，
  卡片走 `ia.state_card` 的 `state=`）。**本檔沒有自己拼 ⬜ 的字串**。
- **鐵則 04 空狀態三要素** → `ui.helpers.ia.empty_state` ＋ `wide_table` 的空分支。
- **指路一律走 `ui.helpers.story_nav`**，不手抄分頁名
  （`tests/test_wpf_five_tab_wiring.py` 兩條規則會擋）。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from ui.helpers.ia import (
    STATE_NOT_READY,
    applied_form,
    render_cards,
    wide_table,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.render_state import not_ready, safe_section
from ui.helpers.story_nav import render_story_nav, tab_label, where_to_find

# ── session 鍵名（本檔自己的命名空間）────────────────────────────────────────
# ⚠️ 刻意**不**沿用舊三頁的鍵：舊頁依方針第 3 條仍在磁碟上、且仍接在 `app.py`，
#    共用鍵會讓兩套 View 互相覆寫對方的狀態，而 payload 形狀並不相同。
_FORM_KEY: str = "v03_research_search_form"
#: **已送出**的查詢（不是 widget 當下值）。下游只准讀這個 —— 理由見 `_applied_query()`。
#: `None`／不存在 ＝ 還沒搜尋過（或上一次送出時查詢條件是空的）。
_SK_APPLIED: str = "v03_research_applied_query"

# ── Form 的兩個欄位（線框 Tab 03 逐字：「代碼或名稱　0P0000ABCD」「來源　全部」）──
#: 線框把送出鈕的字寫成「搜尋」，**不是** `ia.APPLY_LABEL` 的預設「套用」。
#: 具名而不 inline，讓「線框指定的動詞被改掉」看得見。
SUBMIT_LABEL: str = "搜尋"
_LABEL_TERM: str = "代碼或名稱"
_LABEL_SOURCE: str = "來源"

#: 輸入框的 placeholder，**線框逐字**。
#: ⚠️ **它是唯一被允許照抄的線框字面值，理由要講清楚**：placeholder 是輸入框裡的
#:    灰色格式提示，**不是畫面上的資料** —— 它不會被讀成任何一檔基金的績效或分數，
#:    而線框正是用它來指定「這個欄位收的是什麼形狀的字」。
#:    ⛔ 其餘線框示意值（基金名、`ACDD19`、`+12.4%`、`Sharpe 0.81` …）**一律不得出現**，
#:    由 `tests/test_wf03_research_skeleton.py` 釘住。
_CODE_PLACEHOLDER: str = "0P0000ABCD"

#: 「來源」下拉的選項。線框只給了一個值：**全部**。
#: ⛔ **本批刻意不多發明幾個來源選項。** 這個站點實際支援哪幾個來源，要等取數接上
#:    才知道（§2.1 的 fallback chain 有 FundClear／TDCC／MoneyDJ／Cnyes／Morningstar，
#:    但**哪幾個真的能當「使用者可挑的篩選條件」是另一回事**）。
#:    憑印象列一份清單，使用者挑了一個實際上不生效的來源 —— 那是 §1 的假選項，
#:    比少一個選項危險得多。**下一批由真實來源集合填滿它。**
SOURCE_OPTIONS: tuple[str, ...] = ("全部",)

# ── 區塊名（線框 Tab 03）──────────────────────────────────────────────────
#: Form 那一塊的名字。**它是本頁唯一「真的做完」的一塊**，所以所有灰態的指路
#: 都指向它（見 :func:`_pending_where`）。線框把它寫成「Form ─ 唯一搜尋入口」，
#: 這裡取其中文名「搜尋條件」；它會出現在 Form 自己的 caption 上，**不是憑空的名字**。
BLOCK_FORM: str = "搜尋條件"
#: ⚠️ **這一個是本組取的名字，不是線框逐字**：線框的結果卡區沒有標題，
#:    只有一個「結果卡 3 欄」的 chip。骨架需要一個段落名才能被守衛切段，
#:    故取最平鋪直敘的「搜尋結果」。**若客戶要別的名字，改這一個常數即可。**
BLOCK_RESULTS: str = "搜尋結果"

# ⛔ 這兩個名字曾被登記為「兩份已核准線框衝突、待裁決」，**2026-09-05 總管已裁決** ⛔
# ---------------------------------------------------------------------------
# **裁決：③ 以 `ia-wireframe.html` Tab 03 為準，這兩塊照線框字面。**
# 前一版本檔把它們暫行改走 `story_nav.section_label('fund'/'batch')`
# （畫面上是「🔍 單檔深掘」「📦 批次掃描」）—— 那在**裁決下來之前**是對的處置，
# **裁決之後它就變成開放偏離**，故本輪改回線框字面。
#
# ⚠️ **「改回來只要動兩行」這句話當時只對一半，據實記下來**（獨立紅隊實測）：
#   - `BLOCK_DEEP = "單一基金深度"` → 全域守衛**全綠，沒有任何阻礙**。
#   - `BLOCK_BATCH = "批次分析"`    → **紅**（`tests/test_wpf_five_tab_wiring.py::`
#     `test_no_live_string_hardcodes_a_tab_name`）。因為「📦 批次分析」是**已退役的
#     頂層分頁名**（`story_nav.RETIRED_TAB_LABELS`），而該守衛的黑名單**含去 emoji 變體**。
#     → 已依總管裁決在該守衛的 `_LEGIT_EXEMPT` **具名加一條**（理由逐字寫在那裡）。
#     ⛔ **沒有動 `RETIRED_TAB_LABELS` 本身，也沒有碰 `_KNOWN_DEBT`。**
#
# **為什麼這一處豁免是對的，不是為了消紅**：那個守衛防的是**指路文案指向一個已退役的
# 頂層分頁**。而「批次分析」在這裡是 **③ 內部的區塊標題** —— 批次分析**正是被合併進 ③
# 的那個功能**，所以頁內用它當段落名**不會**讓使用者去分頁列上找一個不存在的分頁，
# 反而是正確的。它命中黑名單純粹因為字面重疊。
# **同型前例**：`_LEGIT_EXEMPT` 既有的 `ui/tab3_portfolio.py`「組合配置與健康度」。
# ---------------------------------------------------------------------------

#: 線框 Tab 03 逐字。
BLOCK_DEEP: str = "單一基金深度"
#: 線框 Tab 03 逐字。⚠️ 它同時是**已退役的頂層分頁名**「📦 批次分析」的裸名，
#: 故在 `tests/test_wpf_five_tab_wiring.py::_LEGIT_EXEMPT` 有一條具名豁免 —— 見上方 ⛔。
BLOCK_BATCH: str = "批次分析"

#: 單一基金深度裡走 **3 欄網格**的三塊（線框逐字，順序即線框列舉順序）。
DEEP_DIVE_CARDS: tuple[str, ...] = ("NAV 走勢", "績效分期", "風險指標")
#: 單一基金深度裡走 **大表全寬**的兩塊（線框：「持股與配息為大表全寬」）。
DEEP_DIVE_TABLES: tuple[str, ...] = ("前十大持股", "配息紀錄")
#: **來源標註**（不是第六個內容區塊，理由見模組 docstring 的「內部歧義」段）。
DEEP_DIVE_PROVENANCE: str = "資料來源與抓取時間"

#: 本批共用的灰態理由。**只有一句話**，因為它會出現在八個地方，
#: 八個地方各寫一句就是八份會各自漂移的真相源（§2.1）。
_PENDING_NOTE: str = "本頁分批上線，這一塊的內容還沒接上"


def _pending_where(block: str) -> str:
    """「內容還沒填」這種灰態的指路。**回傳的必須是一個「地方」。**

    ⚠️ **這裡有一個 2026-09-05 由獨立紅隊實測抓到的錯，修法登記在這裡**：
    本函式**原本**回傳 ``f"{where_to_find('research')} → 目前只有「{block}」是完整的"``，
    而 `render_state.not_ready()` 會把它包成 ``（請先到：…）`` ——
    於是畫面上印出的是「**請先到：③ 🔍 標的探索 → 目前只有「搜尋條件」是完整的**」。
    「目前只有 X 是完整的」**不是一個地方，是一句狀態陳述**，被固定的祈使前綴包成了
    一句**不可執行的指令**。紅隊實跑：送出一個代碼 → 8 條灰態；照它指的回到搜尋條件
    換一個代碼再送 → **8 條逐字完全相同**。

    **現行**：回傳 ``③ 🔍 標的探索 → 搜尋條件`` —— 一個真的地方，
    包進祈使句之後文法與語意都成立。

    ⛔ **這一族的指路仍然「有效性有限」，據實寫明，不要讀成已經解決**：
    這一塊沒接上，**去任何地方都不會讓它出現**；能指的最誠實的地方，
    就是這一頁上**唯一真的做完**的那一塊（＝搜尋條件），而灰態本文
    （:data:`_PENDING_NOTE`）已經先講了「這一塊的內容還沒接上」。
    ✅ **對照**：空狀態（:func:`_render_not_searched_yet`）那一則的指路是**真的有效**的
    —— 紅隊實跑：照它做真的會離開灰態。**兩者不要混為一談。**

    ⚠️ 分頁名走 `where_to_find()`，**不手抄**；區塊名由呼叫端傳進來，
    不在這裡再抄一份（手抄的指路在本 repo 已經指錯三次）。
    ⚠️ **刻意不用「」把 `block` 括起來**：`tests/test_batch2_top_card_grid.py::`
    `test_every_where_names_something_that_exists_on_screen` 只對 ``「」`` 內的
    **字面值**比對「畫面上有沒有這個字」，而它的字表不收 `st.caption` ——
    加了括號會產生一條**必然失敗**的比對，不是多一層保護。
    """
    return f"{where_to_find('research')} → {block}"


def _normalise_query(term: str, source: str) -> dict[str, str] | None:
    """把 widget 的當下值收成**已送出的查詢**；空白查詢回 `None`。

    ⚠️ **空字串不算送出，這是刻意的，不是漏判**：使用者把欄位清空再按一次「搜尋」，
    語意是「我不查了」，不是「查一個空字串」。回 `None` 會讓頁面退回空狀態 ——
    比留著上一次的查詢條件、卻顯示著與它無關的畫面誠實（§1）。

    ⚠️ **不吞例外、不猜值**：`source` 給空就退回 :data:`SOURCE_OPTIONS` 的第一項
    （目前是「全部」），**不會**自己挑一個來源。
    """
    _term = (term or "").strip()
    if not _term:
        return None
    return {"term": _term, "source": (source or SOURCE_OPTIONS[0])}


def _applied_query() -> dict[str, str] | None:
    """**已送出**的查詢；沒送出過（或送出的是空白）就是 `None`。

    ⚠️ 下游一律讀這個，**不要讀 widget 的回傳值** —— 讀了就等於沒有 form
    （鐵則 02 的重點不是「有沒有 form」，是「重運算有沒有被 gate 住」）。
    """
    _cur = st.session_state.get(_SK_APPLIED)
    return _cur if isinstance(_cur, dict) else None


def _render_search_form() -> None:
    """區塊 1｜Form — 唯一搜尋入口。**本批唯一做完的一塊。**

    線框 Tab 03 逐字：「代碼或名稱　0P0000ABCD／來源　全部／搜尋」，
    標題寫著「**取代目前三處分散的搜尋框**」。

    ⚠️ **這裡有自由文字輸入框，而 ② 持倉體檢明令沒有 —— 兩者不衝突，是職責不同**：
       ② 的持股一律從組合帶入（那是「我手上這些」）；③ 的基金**不預設我有持有**，
       沒有輸入框就沒有入口。**不要拿 ② 的規則來刪這個框。**
    """
    with applied_form(_FORM_KEY, submit_label=SUBMIT_LABEL) as _gate:
        st.caption(f"{BLOCK_FORM}：輸入完按「{SUBMIT_LABEL}」才查 —— "
                   "打字的當下不會觸發任何取數。")
        _term = st.text_input(
            _LABEL_TERM, value="", placeholder=_CODE_PLACEHOLDER,
            help="基金代碼、Morningstar secId，或名稱的一部分。",
        )
        _source = st.selectbox(
            _LABEL_SOURCE, options=SOURCE_OPTIONS, index=0,
            help="限定只查某一個資料來源；目前只有「全部」，其餘選項待取數接上後補。",
        )

    # ⚠️ `if _gate:` 必須在 `with` **之外**（送出鈕在 `yield` 之後才建立）。
    if _gate:
        st.session_state[_SK_APPLIED] = _normalise_query(_term, _source)


def _render_not_searched_yet() -> None:
    """空狀態三要素（鐵則 04）—— 還沒送出任何查詢條件。

    ⚠️ **「去哪補」指回本頁上方的搜尋條件，這是本頁少數幾個「使用者照著做真的有效」
       的指路之一** —— 他打一個代碼按下去，這一塊真的會換掉。
       ⛔ 但**不得**在這裡順便說「按下去就會看到績效」：按下去看到的是下一段的灰態。
       兩種灰的下一步不同，一次只給一個（`page_02_health.py` 同型）。
    """
    empty_state(
        "還沒開始搜尋",
        "還沒有查詢條件 —— 代碼或名稱是空的，或還沒按下送出",
        where=f"{where_to_find('research')} → 上方的搜尋條件",
        footer="送出後，這一頁才會往下展開。",
    )


def _render_results() -> None:
    """區塊 2｜搜尋結果（**3 欄結果卡**）。本批灰態。

    線框畫了三張示意卡，其中第三張本身就是灰態示範
    （「幣別未知／此來源未提供計價幣別，換算後績效不予顯示」＋ chip「不猜值」）——
    **那是線框在示範「查得到、但某一欄不可信時該長什麼樣」，不是三張要照抄的卡。**

    ⛔ **本批不畫任何一張結果卡**：骨架階段連「有幾筆結果」都不知道，
       畫三張空卡就是鐵則 04 要禁的冗餘占位；填上線框的基金名與績效則是造假（§1）。
    """
    not_ready(f"{_PENDING_NOTE}（符合條件的基金清單與各自的績效摘要）。",
              where=_pending_where(BLOCK_FORM))


def _render_deep_dive() -> None:
    """區塊 3｜單一基金深度。**五個區塊 ＋ 一則來源標註**，本批全灰。

    版面依線框：前三塊走 3 欄網格，持股與配息走**大表全寬**
    （9 欄以上的表塞進 1/3 寬會被壓到無法閱讀 —— `ui/helpers/ia/layout.py` 的
    `wide_table()` 存在的理由就是這個）。

    ⚠️ **本函式沒有為「還沒選定基金」另立一種灰**：骨架階段就算真的選了一檔，
       這裡照樣畫不出東西 —— 那時說「請先選一檔」是**假的下一步**。
       誠實的理由只有一個：這一塊還沒接上（見模組 docstring「選定後展開」那段）。
    """
    _where = _pending_where(BLOCK_FORM)
    render_cards([
        {"title": DEEP_DIVE_CARDS[0], "state": STATE_NOT_READY,
         "note": f"{_PENDING_NOTE}（淨值時間序列）。", "where": _where},
        {"title": DEEP_DIVE_CARDS[1], "state": STATE_NOT_READY,
         "note": f"{_PENDING_NOTE}（近 1 月／3 月／1 年／成立以來的分期報酬）。",
         "where": _where},
        {"title": DEEP_DIVE_CARDS[2], "state": STATE_NOT_READY,
         "note": f"{_PENDING_NOTE}（波動度、最大回撤、Sharpe）。", "where": _where},
    ])

    for _name, _missing in zip(
            DEEP_DIVE_TABLES,
            (f"{_PENDING_NOTE}（持股名稱、權重與截止日）。",
             f"{_PENDING_NOTE}（除息日、每單位配息與幣別）。")):
        st.markdown(f"##### {_name}")
        wide_table([], empty_title=f"{_name}還沒有可顯示的列",
                   empty_missing=_missing, empty_where=_where)

    # 來源標註 —— 讀法 A 下它不是第六個內容區塊，但**照樣要有自己的段落與灰態**，
    # 否則突變把它拿掉不會轉紅（見模組 docstring 的「內部歧義」段）。
    st.markdown(f"##### {DEEP_DIVE_PROVENANCE}")
    not_ready(f"{_PENDING_NOTE}（每一個數字各自來自哪個來源、什麼時候抓的）。",
              where=_where)


def _render_batch() -> None:
    """區塊 4｜批次分析（**大表全寬**）。本批灰態。

    線框逐字：「一次丟多個代碼跑同一組指標，結果落地可續跑。
    **長時間運算，必須在 Form 之後才啟動。**」

    ⚠️ **線框沒有畫批次自己的輸入框** —— 它只畫了頁面頂端那一個「唯一搜尋入口」，
       而該入口收的是**單一**代碼或名稱，餵不了「一次丟多個代碼」。
       ⛔ **本批刻意不發明一個批次輸入框**（那是線框沒有的新版面 ＝ 客戶 gate，
       §-1.5 v3 §03-2 ①）。**已登記，待下一批連同真內容一起請示。**
       在那之前，本頁靠「送出過搜尋才往下畫」滿足 chip「Form 後才跑」的下限：
       **批次絕不會在頁面載入時自己啟動。**
    """
    wide_table([], empty_title="批次結果還沒有可顯示的列",
               empty_missing=f"{_PENDING_NOTE}（多檔同一組指標的結果表與續跑進度）。",
               empty_where=_pending_where(BLOCK_FORM))


def render_fund_research() -> None:
    """渲染「③ 標的探索」整頁。

    ⚠️ **本批尚未接進 `app.py`**（客戶明令舊三頁不動、不接線、不下架），
    所以現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。

    ⚠️ **區塊之間走 `safe_section()` 隔離**：`st.tabs` 是單次 run 渲染全部分頁，
    任一區塊拋未捕捉例外會**中止整個 script**，其後所有分頁空白。
    `safe_section` **不吞例外**（§1）：它走 `system_error()` 顯式紅框 ＋ traceback。
    """
    st.markdown(f"## {tab_label('research')}")
    render_story_nav("research")
    # 線框 Tab 03 的職責宣告 ＋「這裡不放什麼」，逐字。
    # ⚠️ 指路的顆粒度**跟著線框走**：線框寫「→ 02」「→ 04」（整個分頁），
    #    所以這裡指 `health` 與 `portfolio` 兩個**分頁**，不是 ④ 裡的 🎯 換股顧問分區。
    #    `switch` 在語意上更精準，但那會是本組替客戶決定顆粒度 —— 不做。
    st.caption(
        "回答一個問題：**有沒有更好的標的？** 這裡的基金不預設我有持有 —— "
        f"我持有部位的健康度在 {where_to_find('health')}，"
        f"「要不要換成這檔」的試算在 {where_to_find('portfolio')}。")

    safe_section(BLOCK_FORM, _render_search_form)

    if _applied_query() is None:
        # 還沒送出查詢 —— 下面三塊沒有任何東西可畫，直接走空狀態，
        # **不要**把三塊各印一次灰（那會變成四份在講同一件事的灰字，違鐵則 04），
        # 也順帶滿足線框給批次的「Form 後才跑」。
        safe_section("還沒開始搜尋", _render_not_searched_yet)
        return

    st.markdown(f"#### {BLOCK_RESULTS}")
    safe_section(BLOCK_RESULTS, _render_results)
    st.markdown(f"#### {BLOCK_DEEP}")
    safe_section(BLOCK_DEEP, _render_deep_dive)
    st.markdown(f"#### {BLOCK_BATCH}")
    safe_section(BLOCK_BATCH, _render_batch)
