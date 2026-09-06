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

資料從哪裡來（**深度區已接上**；其餘兩塊仍是缺口）
------------------------------------------------------------
**單一基金深度的六格全部由同一次呼叫供給**：
:func:`services.moneydj_fetcher.auto_fetch_moneydj`（**L2**，一次往返、六格共用）。
⚠️ **刻意不走** `fetch_fund_by_key_enriched` —— 本組實測它的回傳**沒有
`holdings` / `perf` / `currency`**，那會讓六格少三格，而且畫面上看不出為什麼。

⚠️ **本組對該入口的四處實測更正，寫在這裡免得下一個人照舊描述做**
（`CLAUDE.md §-2` 規則 6：以下是**本組單組實測**，未經第二組驗證）：

1. **它會拋例外。** 「純代碼」分支有 `try/except` 把例外收成 `{"error": …}`，
   但 **URL 直傳分支（`raw_input` 含 `yp010000` / `yp010001`）沒有** ——
   實測 patch 掉下游使其拋 `RuntimeError`：URL 分支**原封拋出**、代碼分支回 `{'error': …}`。
   → 本檔**刻意不 try/except**：讓它拋到 :func:`~ui.helpers.render_state.safe_section`，
   由那裡走 `system_error()` 畫**真的**紅框（帶真的 traceback）。
   ⛔ **不得**為了塗紅而自己 `raise Exception(result["error"])` —— 那是捏造的例外（§1）。
2. **`status` 不保證存在。** URL 直傳分支**不經** `normalize_result_state`；
   而代碼分支全敗時回的可能是 `{'error': …}` **只有一個鍵**（實測）。
   → 本檔的判定一律**看內容**（:func:`_deep_facts`），`status` 只當佐證。
3. **配息的血緣不在每一筆裡。** 三個產生點（`_src_fundclear_div` / `_src_cnyes_div` /
   `_src_tcb_div` ＋ orchestrator 的 wb05 解析）吐的欄位都是
   `date / ex_date / pay_date / amount / yield_pct / **currency**` ——
   **沒有 `source`、沒有 `fetched_at`**，而**幣別是逐筆帶的**（不是只在 `result["currency"]`）。
   → 本檔逐筆顯示幣別，並用 `shared.data_quality.reconcile_row_currencies`
   判斷「這一組配息能不能誠實宣告單一幣別」。
4. **`risk_metric_meta` 只涵蓋四個指標**（`sharpe` / `sortino` / `calmar` / `max_drawdown`），
   **`std_1y` 沒有 meta**（它的來源在 `metrics["std_source"]`）；
   且 `sharpe` 那一格的缺值原因鍵是 **`self_calc_reason`**，不是 `reason`
   （只有稀疏降級路徑會補寫 `reason`）。**逐格缺因要照這個實況取，不能假設一致。**

⛔ **仍然是缺口，本批沒有動**：**「搜尋」在 L2 沒有入口。**

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
- **送出了、但這一塊的內容還沒填** → 該塊**自己那一句**的灰態
  （:data:`_RESULTS_PENDING_NOTE` / :data:`_BATCH_PENDING_NOTE`）。
  ⚠️ 2026-09-06 起**不再是一句共用的「本頁分批上線」** —— 兩塊卡住的原因不同，
  理由見那兩個常數上方的 ⛔ 段。
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

# ⚠️ **L2 服務層（客戶方針第 2 條的唯一取數入口）**。
#    `services.moneydj_fetcher` 是 L2；它自己往下走 `services.fund_service` 的
#    enriched wrapper → L1。本檔**不碰** `repositories` / `infra` / 任何網路函式庫，
#    由 `tests/test_wf03_research_skeleton.py::test_the_page_never_reaches_into_the_data_layer` 釘住。
from services.moneydj_fetcher import auto_fetch_moneydj
# 幣別一致性判定（純函式、零 I/O）。**不自己寫一份** —— §1 的失效模式就寫在它的 docstring 裡。
from shared.data_quality import reconcile_row_currencies

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

# ── 兩塊還沒接上的灰態理由：**一塊一句，刻意不共用** ────────────────────────
# ⚠️ ~~本批共用的灰態理由。**只有一句話**，因為它會出現在八個地方，~~
#    ~~八個地方各寫一句就是八份會各自漂移的真相源（§2.1）。~~
#    ~~`_PENDING_NOTE: str = "本頁分批上線，這一塊的內容還沒接上"`~~
#    → **2026-09-06 拆成兩句（有意識的政策變更，不是漏刪；決策者：AI 總管）。**
#
#    **舊寫法的理由仍然成立**：一句話當時真的出現在八個地方，共用確實避免了八份漂移。
#    **被權衡掉的是它的前提** —— 深度區六格接上真取數之後，消費者從八個掉到**兩個**，
#    而那兩個「為什麼還沒有」的**原因完全不同**：
#      · 搜尋結果 —— 卡在**沒有可以列出候選的搜尋**；
#      · 批次分析 —— 卡在**沒有可以收多個代碼的輸入欄位**（版面決定，不是資料問題）。
#    共用一句「本頁分批上線」把兩個不同的原因說成同一件事，使用者無從判斷哪一個
#    跟他有關、也無從知道哪一個是他等得到的。**那正是 §1 要防的事**
#    （對照：深度區六格的灰態理由一律**來自資料本身**，缺哪一個就說那一個為什麼缺）。
#
# ⛔ **兩句必須不一樣** —— 由 `tests/test_wf03_research_skeleton.py::`
#    `test_the_two_pending_reasons_are_not_the_same_sentence` 釘住；
#    改回共用一句會轉紅。
# 📌 同型前例：② `ui/views/page_02_health.py` 的 `_SCORE_PENDING_NOTE` /
#    `_LAG_PENDING_NOTE`（2026-09-06 同日、同一個理由拆的）。**本檔照同一個形狀。**

#: 區塊 2 的灰態理由。**說的是「這一塊缺什麼」，不是「這一頁的進度」。**
#: ⚠️ 內容與搜尋框的 `help` 是**同一個事實的兩面**，改一邊要順手看另一邊：
#:    本頁把輸入原封當成代碼送去查（`services/**` 沒有可回傳候選清單的搜尋入口）。
_RESULTS_PENDING_NOTE: str = (
    "本頁目前只查得到**完整代碼** —— 你輸入的字會被原封當成代碼送去查，"
    "結果顯示在下方的「單一基金深度」。**依名稱或關鍵字列出多檔候選**還沒有接上")

#: 區塊 4 的灰態理由。**缺的是一個輸入欄位，不是資料。**
#: ⚠️ 刻意把「為什麼還沒加」講出來：多代碼輸入欄位屬**版面異動**，
#:    依草稿先行原則要先提線框草稿拍板（§-1.5 v3 `03`-2 ①），不是實作組自己加。
_BATCH_PENDING_NOTE: str = (
    "批次要能**一次收多個代碼**，而本頁目前只有一個收**單一**代碼的搜尋框 —— "
    "多代碼的輸入欄位是版面異動，要先出線框草稿拍板才會加")

# ── 單一基金深度：欄位對照表（**畫面順序即這裡的順序**）────────────────────
#: 績效分期：`(result["perf"] 的鍵, 畫面標籤)`。
#: ⚠️ **不含 `2Y`**：`fetch_performance_wb01` 的對照表確實吐得出 `2Y`，但線框
#:    沒有列它，本檔**不自行加欄**（多一欄是版面異動 ＝ 客戶 gate，§-1.5 v3 §03-2 ①）。
#:    **它不是漏掉，是刻意不畫** —— 下一個人看到 `perf["2Y"]` 有值卻沒顯示時請讀這一行。
PERF_PERIODS: tuple[tuple[str, str], ...] = (
    ("1M", "近 1 月"), ("3M", "近 3 月"), ("6M", "近 6 月"),
    ("1Y", "近 1 年"), ("3Y", "近 3 年"), ("5Y", "近 5 年"),
)

#: 風險指標：`(metrics 的鍵, 畫面標籤, 單位後綴)`。
#: ⚠️ **`std_1y` 刻意排在最後且沒有 meta**：`risk_metric_meta` 只有前四個
#:    （實測 `services/fund_service.py::calc_metrics` 的 `_risk_metric_meta`），
#:    `std_1y` 的來源住在 `metrics["std_source"]`。:func:`_risk_reason` 因此分兩條路。
RISK_METRICS: tuple[tuple[str, str, str], ...] = (
    ("sharpe", "Sharpe", ""),
    ("sortino", "Sortino", ""),
    ("calmar", "Calmar", ""),
    ("max_drawdown", "最大回撤", "%"),
    ("std_1y", "年化波動", "%"),
)

#: 幣別無法誠實宣告時的標記。**線框第三張示意卡就是在示範這個處境**
#: （「幣別未知／此來源未提供計價幣別，換算後績效不予顯示」＋ chip「不猜值」）。
#: ⚠️ 本檔**不做任何換算**，所以「不予顯示」在這裡的落點是：
#:    金額照樣顯示（那是原幣的真值），但**旁邊一定標明幣別未知**，
#:    絕不挑一個幣別填上去（`reconcile_row_currencies` 的 docstring 講的就是這件事）。
CCY_UNKNOWN: str = "幣別未知"

#: 取數全敗時的**兩種可能**。⛔ **刻意不寫「代碼打錯」**（2026-09-06 獨立稽核 應修 1）。
#: 舊文案寫「可能是代碼打錯」——**那是把責任推給使用者，而不能用的是本頁自己宣告的輸入格式**：
#: 搜尋框的 `help` 當時承諾「基金代碼、Morningstar secId，或名稱的一部分」，
#: 但**後兩種靜默失敗**（`services/**` 沒有搜尋入口，term 直接被拼成 `?a=<原字串>`）。
#: 一個打對了 secId 的使用者，會被告知他「打錯了」。
#: **現在改成據實說明本頁只查得到代碼**，並保留「來源當下不可用」這第二種可能
#: —— L2 分不出這兩者，挑一種講就是編的。
_BLAME_FREE: str = (
    "可能是這串輸入不是本頁查得到的基金代碼（本頁目前只查得到代碼，"
    "secId 與名稱查不到），也可能是這幾個來源當下不可用。")


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
    （:data:`_RESULTS_PENDING_NOTE` / :data:`_BATCH_PENDING_NOTE`）已經先講了
    **這一塊**缺的是什麼。
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

    ⛔ **一個本批查出來、但刻意沒有自行修掉的問題：`help` 裡的「Morningstar secId」**

    骨架時期這句話不承擔任何後果（沒有東西會去用它）；**2026-09-06 深度區接上
    取數之後它就變成一句對使用者的承諾**，而本組**靜態追蹤顯示這條路走不通**：

    - `services.moneydj_fetcher.build_moneydj_url("0P0000ABCD", "yp010000")`
      實測回 `https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=0P0000ABCD`
      —— **secId 被原封當成 MoneyDJ 的基金代碼送出去**；
    - 走 Morningstar 的那條備援有閘門
      `if len(nav_s) < 10 and (_is_insurance_code or _pool_secid_or_isin(_code))`，
      而 `_pool_secid_or_isin("0P0000ABCD")` 實測為 **False**
      （它是拿**基金代碼**去選股池反查 secId，不是拿 secId 反查基金）。

    ⚠️ **這是靜態追蹤，不是端到端實證** —— 沙箱的 egress proxy 擋掉了上游
    （實測 `fund.api.cnyes.com:443` 被拒），本組**無法**真的送一次 secId 去看回什麼。
    依 `CLAUDE.md §-2` 規則 6，上面只能當**待驗事項**，不得當成已查證的事實。

    ✅ **2026-09-06 已改，總管裁決分兩半**（獨立稽核 應修 1）：

    ⚠️ **本組原本說「兩句一起改屬客戶 gate」——那是個假兩難，被實測推翻。**
    `git grep -c <pat> origin/main -- 'docs/wireframes/*'`：
    ``secId`` **0 命中**、``Morningstar`` **0 命中**、``0P0000ABCD`` **1 命中**。
    → **help 那句是我方自己寫的，不是線框逐字**，所以存在第三條路，
    而本組當時的選項描述裡**少了它** —— 兩個選項都不對，就會得出「只能不動」的結論。

    - **(a) `help`（本行上方）：已改，內部自決。** 把一句不實的承諾改成真話屬
      「修正錯誤」不屬「改變設計」（§-1.5.1a 接合 A2）。
      連帶把失敗文案的「可能是代碼打錯」也改掉（見 :data:`_BLAME_FREE`）。
    - **(b) `_CODE_PLACEHOLDER`（`0P0000ABCD`）：一個字都沒動。** 那是線框逐字；
      **線框指定了一個程式服務不了的輸入格式** —— 那不是實作缺陷，
      是規格與實作對不上，**總管帶去問客戶**，不在本批。

    ⚠️ **獨立稽核用比本組更強的方法確認了這件事**，據實記下來：本組的驗法是
    「拿真實池查 `0P0000ABCD` → False」，**那有可能走的是 `except → False` 的
    吞例外路徑（右答案、錯理由）**。稽核組改成植入「池裡確實有這個 secId」的 fixture：
    ``_pool_secid_or_isin('ACDD19') -> True``（用**代碼**查，通）／
    ``_pool_secid_or_isin('0P0000ABCD') -> False``（用 **secId** 查，即使池裡就有它也不通）。
    **它還多找到一件本組沒說的：連「名稱」也不通**，理由同上（`services/**` 沒有搜尋入口）。
    """
    with applied_form(_FORM_KEY, submit_label=SUBMIT_LABEL) as _gate:
        st.caption(f"{BLOCK_FORM}：輸入完按「{SUBMIT_LABEL}」才查 —— "
                   "打字的當下不會觸發任何取數。")
        _term = st.text_input(
            _LABEL_TERM, value="", placeholder=_CODE_PLACEHOLDER,
            help="目前只查得到**基金代碼**。Morningstar secId 與基金名稱查不到 —— "
                 "本頁沒有搜尋入口，輸入會被原封當成代碼送去查。",
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
    not_ready(f"{_RESULTS_PENDING_NOTE}（符合條件的基金清單與各自的績效摘要）。",
              where=_pending_where(BLOCK_FORM))


# ══════════════════════════════════════════════════════════════════════════
# 單一基金深度：把**一次**取數的回傳攤成六格各自的事實（純函式、零 I/O、零渲染）
# ══════════════════════════════════════════════════════════════════════════
# ⚠️ **為什麼要把它們拆成純函式**：這一區的規則全部是「**沒有值的時候不准生一個出來**」，
#    而那種規則在渲染函式裡幾乎驗不動（要先組畫面、再對字串猜哪個數字屬於誰）。
#    拆成純函式之後，守衛可以逐格餵 `None` 再看回傳 —— 突變拿掉任何一條 `is None`
#    判斷都會**單獨**轉紅。

#: 前十大持股表的欄名（`wide_table` 直接吃 list[dict]，鍵即欄名）。
HOLDING_COLS: tuple[str, ...] = ("排名", "持股名稱", "產業", "權重 %")
#: 配息表的欄名。⚠️ **幣別是逐筆欄位**，不是表外的一句話 —— 理由見模組 docstring 第 3 點。
DIVIDEND_COLS: tuple[str, ...] = ("配息基準日", "除息日", "發放日", "每單位配息", "幣別", "年化配息率 %")
#: 來源軌跡表的欄名。
TRACE_COLS: tuple[str, ...] = ("來源", "結果", "說明")
#: 來源軌跡的結果字面值（具名而不 inline —— 守衛要拿它比對）。
TRACE_OK: str = "成功"
TRACE_FAIL: str = "失敗"
#: **第三態，2026-09-06 加**：上游那一則**根本沒有 `success` 這個鍵**。
#: ⛔ **為什麼不是二選一** —— 這是 §1「不可造假」在這張表上的落點：
#:    「沒有說」和「說了失敗」是兩件事，把前者畫成後者是**我方替上游編了一個結論**。
#:    實例（`services/fund_service.py:1131`）：`nav_history_merge` 在
#:    「累積序列讀成功、只是目前還沒產生淨增益」時回的 dict **沒有 `success` 鍵**，
#:    它的 `note` 逐字是「…目前全部落在本次 live 序列的日期範圍內 → 尚未產生淨增益」——
#:    **一切正常**。舊寫法 `bool(_t.get("success"))` 把它畫成「失敗」，
#:    於是同一張表上出現「說明＝一切正常」配「結果＝失敗」。
#: ⚠️ **刻意不採「缺鍵就當成功」**（那是本檔突變實驗 M5 的做法，它也能讓症狀消失）：
#:    我方**沒有觀察到**它成功，寫「成功」同樣是編的。**不知道就說不知道。**
TRACE_UNKNOWN: str = "上游沒說"

#: `source_trace` 裡「**沒有淨值序列**」那一則合成標記的名字。
#: :func:`_nav_reason` 靠它挑出缺值原因，:data:`SYNTHETIC_TRACE_SOURCES` 靠它排除計數。
TRACE_NAV_SERIES: str = "nav_series"

#: ⛔ **`source_trace` 裡**不是來源**的那幾則。**
#: 它們是我方 pipeline **對 pipeline 自己**下的結論，被 `.append()` 進同一個 list，
#: 但把它們算進「試過幾個來源」會**虛報**（2026-09-06 獨立稽核 應修 2）。
#: 逐則的出處與語意（**本組實測，逐行讀過**）：
#:   - ``nav_series``        —— `services/fund_service.py::finalize_fund_metrics`
#:     與 `repositories/fund/fund_orchestration.py` 兩處都會追加，
#:     error 是「無淨值序列」/「只有 N 筆(需≥10)」＝ **對結果的判定**，不是一次抓取。
#:   - ``nav_all``           —— 同上，error 是「所有來源均不足10筆（最多:N）」＝ **彙總判詞**。
#:   - ``calc_metrics``      —— 指標**計算**成功/失敗，根本不涉及取數。
#:   - ``nav_history_rescue`` —— 「live 全敗，改用累積序列」的**註記**。
#:   - ``nav_history_merge``  —— **2026-09-06 補**，見下方 ⛔。
#:
#: ⛔ **`nav_history_merge` 的補登，以及一句要講清楚的話** ⛔
#: ---------------------------------------------------------------------------
#: **它不是「黑名單日後腐化」，是這份黑名單寫下的那一天就不完整。**
#: 加這份黑名單的 commit 是 `b83c29f`（2026-09-06 稽核回修）；**在那個 commit 當下**，
#: `services/fund_service.py` 裡**真正的 `nav_history_merge` 標記**已經有 **3** 處
#: （`:1098` / `:1132` / `:1164`）。
#: ⚠️ `git grep -c "nav_history_merge" b83c29f -- services/fund_service.py` **回的是 4** ——
#:    多出來的 `:1161` 是 ``merged.attrs["nav_history_merged"]``（**多一個 d**），
#:    那是序列的 attrs 註記，不是 trace 標記。**本行刻意寫 3 不寫 4**：
#:    拿一個沒有逐行判讀過的 `grep -c` 當證據，正是本節在講的那種錯。
#: 也就是說：漏掉它靠的不是時間，是**當時沒有把上游的標記逐一列出來對過**。
#:
#: **它是什麼**：`services/fund_service.py::_merge_nav_history_series` 的回傳，
#: 由同檔 `finalize_fund_metrics` 直接 `result["source_trace"].append(...)`。
#: 它講的是「**我方要不要／能不能把累積序列併進來**」，**不是一次對外取數**。
#:
#: **它有兩種形狀會被算成失敗（兩種都實測過，不是推論）**：
#:   1. ``{"source": "nav_history_merge", "success": False, "error": …}``
#:      —— 讀 Google Sheet `nav_history` **失敗**時（`fund_service.py:1098`）。
#:   2. ``{"source": "nav_history_merge", "merged": False, "hist_points": …}``
#:      —— **完全沒有 `success` 這個鍵**（`fund_service.py:1131`）。這一則的語意是
#:      「讀成功了，但累積點目前全部落在 live 的日期範圍內、還沒產生淨增益」——
#:      **一切正常**。而 :func:`_trace_rows` 用 ``bool(_t.get("success"))`` 判定，
#:      缺鍵 → `False` → 被畫成「失敗」並計入來源數。
#:      ⚠️ **第 2 種比第 1 種更值得記**：它在**什麼都沒出錯**的時候虛報。
#:
#: ✅ **順手掃過、但刻意沒有一起改的（只登記，不擴大修）**：
#:   - ``multi_source``（`fund_orchestration.py:1013`，`success: False`）——
#:     它是「多來源流程本身拋例外」的紀錄。**算不算一次「試過的來源」有兩種讀法**，
#:     本組**不裁決**，維持現況（會被計入）。留在這裡等有人裁決。
#: ⛔ **順手掃同時推翻了本組自己先前報告裡的一句話，據實更正**：先前說
#:    ``tdcc_meta`` 這類 `*_meta` 與 ``fetch_holdings:exception`` 也會灌水 —— **那是假的**。
#:    AST 逐一列出所有 append 進 `source_trace` 的 dict 與其 `success` 字面值後：
#:    六個 `*_meta` **一律只在 `success: True` 時 append** —— 但**守門條件不是同一個**：
#:    四個（`allianzgi_meta` / `tcb_meta` / `fundclear_meta` / `sitca_meta`）包在
#:    `if meta.get("fund_name"):` 裡；另外**兩個**（`tdcc_meta_early` / `tdcc_meta`）用的是
#:    **不同的變數、而且多一個 `or`**：`if _tdcc_early.get("fund_name") or
#:    _tdcc_early.get("nav_latest"):`（`tdcc_meta` 同形，變數為 `_tdcc_m`）。
#:    ⚠️ **結論不受影響**（六個都只在成功時 append），**被更正的是本組對守門條件的描述** ——
#:    「都包在同一個 if 裡」是掃過去的印象，不是逐行讀出來的。
#:    而 ``fetch_holdings:exception`` **根本不在 `source_trace`**，它是 `result["holdings"]["source"]`。
#:    **那句話是拿一個手寫的 dict 當成程式會產生的情境，重現腳本跑得出來、production 跑不出來。**
#: ---------------------------------------------------------------------------
#:
#: ⚠️ **這是黑名單，會腐化**：上游日後新增別的合成標記，這裡不會自動知道。
#:    但**虛報一個來源數**比**漏排除一個**危險（前者是編造的證據），故採黑名單而非白名單。
#:    ⛔ **不要改成「只數已知的真來源名」** —— 那是白名單，新來源會被靜靜漏掉，
#:    使用者會看到一個比實際更小的數字，同樣是假的。
#:    ⚠️ **腐化這件事有守衛，但它的射程有限，據實寫明**：
#:    `tests/test_wf03_research_skeleton.py::test_every_upstream_failure_marker_has_been_triaged`
#:    會把上游標記比對本黑名單與一份具名的「已裁決要計入」清單。
#:    **守得到**：那兩個 producer 檔裡、**字面字串**當 source 名、**字面 dict** 的新標記。
#:    **守不到**（2026-09-06 獨立稽核構造、實測全綠）：動態 source 名（f-string）、
#:    `dict(...)` 建構式、逐鍵組出來的 dict、以及**第三個檔**只用 `.extend`／`+=`／`insert`。
#:    ⛔ **不要讀成「上游新增任何標記都會轉紅」** —— 逐條射程見該測試的 docstring 表格。
SYNTHETIC_TRACE_SOURCES: frozenset = frozenset({
    TRACE_NAV_SERIES, "nav_all", "calc_metrics", "nav_history_rescue",
    # 2026-09-06 補（理由見上方 ⛔）。⚠️ 缺 `success` 鍵的那一種形狀同樣被這行擋掉 ——
    # 排除是按 **source 名字**做的，不是按 success 值做的。
    "nav_history_merge",
})
#: 上游**沒有**給缺值原因時的誠實佔位。⛔ 不得換成一句猜出來的理由。
NO_REASON: str = "上游沒有附缺值原因"

#: 「這個鍵根本不存在」的哨兵。⛔ **不得用 `None` 代替** —— 上游是有可能寫
#: `{"success": None}` 的，那是「說了、但值是空」，與「沒說」不是同一件事。
_MISSING: object = object()


def _fmt(value: object, unit: str = "") -> str | None:
    """數值 → 顯示字串；**不是數字就回 `None`（呼叫端據此判定「這一格沒有值」）**。

    ⚠️ **`None` 進來就 `None` 出去，絕不回 `0` 或 `"—"`** —— 回一個佔位字元會讓
    「算不出來」與「算出來剛好是 0」長得一模一樣（§1）。
    ⚠️ `bool` 明確排除：`isinstance(True, int)` 為真，不擋的話 `True` 會被印成 `1`。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value:                      # NaN（不 import numpy/pandas 的判法）
        return None
    return f"{value:,.2f}{unit}"


def _series_of(result: dict) -> object | None:
    """`result["series"]`，且**確定它有長度**；否則 `None`。"""
    _s = result.get("series")
    if _s is None or not hasattr(_s, "__len__") or len(_s) == 0:
        return None
    return _s


def _attrs_of(series: object) -> dict:
    """`Series.attrs`，型別異常一律當空。

    ⚠️ **attrs 會掉。** `repositories/fund/fund_orchestration.py` 就地寫著
    「`attrs` 在 concat/copy 中可能掉」—— 所以本檔**不得**把「有 series 就有血緣」
    當成前提；掉了就誠實顯示沒有，不要回填一個來源名。
    """
    _a = getattr(series, "attrs", None)
    return _a if isinstance(_a, dict) else {}


def _nav_facts(result: dict) -> dict | None:
    """格 1｜NAV 走勢的事實；序列不存在或為空 → `None`。

    ⚠️ **本格刻意不畫折線圖，這是決定不是遺漏。** 線框把前三塊釘死為 3 欄卡片，
    而 `ia.state_card()`（鐵則 01／03 的組合入口）**沒有圖表槽位**；
    另開一張全寬圖 ＝ **版面異動**，屬 §-1.5 v3 §03-2 ① 的**客戶 gate**，
    不是實作細節。**已登記待客戶裁決**，在那之前本格給的是序列本身的事實
    （最新值／幣別／筆數／跨度／首末日／來源），**不是一句「走勢向上」的形容詞**。
    """
    _s = _series_of(result)
    if _s is None:
        return None
    _attrs = _attrs_of(_s)
    # ⛔ **這裡刻意沒有 try/except，本組初稿有、自己拆掉的，理由記在這裡**：
    #    初稿把「索引讀不出來」收斂成 `return None` → 呼叫端走灰態、
    #    而灰態的文案是 :func:`_nav_reason`（「這次沒有帶回淨值序列」）——
    #    **但序列明明帶回來了，只是讀不出來。那句話是假的。**
    #    序列的索引不是時間軸 ＝ 上游契約被破壞（`CLAUDE.md §3.1` 明訂
    #    `nav_df.date` 是遞增且唯一的 DatetimeIndex），那是**系統真出錯**，
    #    §1 要求炸掉：讓它一路拋到 `safe_section()` 去畫**紅框 ＋ 真 traceback**，
    #    而不是安靜地變成一句與事實不符的灰字。
    _first, _last = str(_s.index.min())[:10], str(_s.index.max())[:10]
    _latest = _fmt(float(_s.iloc[-1]), "")
    if _latest is None:
        return None
    return {
        "name": str(result.get("fund_name") or "").strip(),
        "latest": _latest,
        "currency": str(result.get("currency") or "").strip(),
        "n": len(_s),
        "first": _first,
        "last": _last,
        "span_days": result.get("nav_span_days"),
        "source": str(_attrs.get("source") or result.get("source") or "").strip(),
        "fetched_at": str(_attrs.get("fetched_at") or "").strip(),
        "merged": str(_attrs.get("nav_history_merged") or "").strip(),
    }


def _perf_lines(result: dict) -> tuple[list[str], list[str]]:
    """格 2｜績效分期 → `(有值的行, 缺值的標籤)`。

    ⚠️ **缺的期別列出名字、不列數字** —— 少一個期別跟「那個期別是 0%」是兩回事。
    """
    _perf = result.get("perf")
    _perf = _perf if isinstance(_perf, dict) else {}
    _shown: list[str] = []
    _missing: list[str] = []
    for _key, _label in PERF_PERIODS:
        _txt = _fmt(_perf.get(_key), "%")
        (_shown.append(f"{_label} {_txt}") if _txt is not None
         else _missing.append(_label))
    return _shown, _missing


def _perf_source(result: dict) -> str:
    """績效的來源標記：`wb01`（MoneyDJ 官方含息總報酬）或 `local_calc`（本地補算）。"""
    return str(result.get("perf_source") or "").strip()


def _risk_reason(metrics: dict, key: str) -> str:
    """某個風險指標**為什麼**沒有值。**取該指標自己的原因，不共用一句。**

    取用順序與其實測依據（模組 docstring 第 4 點）：
    1. `risk_metric_meta[key]["reason"]` —— `sortino` / `calmar` / `max_drawdown` 走這條；
    2. `risk_metric_meta[key]["self_calc_reason"]` —— **`sharpe` 只有這一個鍵**；
    3. `metrics["sparse_reason"]` —— 稀疏降級路徑（也是 `std_1y` 唯一可能的來源，
       因為 **`std_1y` 在 `risk_metric_meta` 裡根本沒有條目**）；
    4. 都沒有 → :data:`NO_REASON`。⛔ **不編一個聽起來合理的理由。**
    """
    _meta = metrics.get("risk_metric_meta")
    _entry = _meta.get(key) if isinstance(_meta, dict) else None
    if isinstance(_entry, dict):
        for _k in ("reason", "self_calc_reason"):
            _v = _entry.get(_k)
            if isinstance(_v, str) and _v.strip():
                return _v.strip()
    _sparse = metrics.get("sparse_reason")
    if isinstance(_sparse, str) and _sparse.strip():
        return _sparse.strip()
    return NO_REASON


def _risk_lines(result: dict) -> tuple[list[str], list[str]]:
    """格 3｜風險指標 → `(有值的行, 缺值的行＋各自的原因)`。

    ⛔ **`None` 一律進第二個 list，不補 0、不沿用別的指標、不留空字串。**
    `finalize_fund_metrics` 在序列稀疏時會**主動**把 `sortino` / `calmar` /
    自算 `sharpe` / 自算 `std_*` 設成 `None` 並寫好 `sparse_reason` ——
    那句話**已經是寫好的誠實理由**，本檔照抄，不自己再想一句。
    """
    _m = result.get("metrics")
    _m = _m if isinstance(_m, dict) else {}
    _shown: list[str] = []
    _missing: list[str] = []
    for _key, _label, _unit in RISK_METRICS:
        _txt = _fmt(_m.get(_key), _unit)
        if _txt is not None:
            _shown.append(f"{_label} {_txt}")
        else:
            _missing.append(f"{_label}：{_risk_reason(_m, _key)}")
    return _shown, _missing


def _holdings_rows(result: dict) -> list[dict]:
    """格 4｜前十大持股的表格列。**缺權重照樣列出（權重留空）；缺名稱才跳過。**

    ⚠️ **不過濾掉沒有權重的持股** —— 那會讓「前十大」變成「我算得出權重的那幾大」，
    使用者看到的排名就不再是上游給的排名（§1）。
    ⚠️ **但沒有名稱的列會跳過**：一列既沒有名字、只有一個百分比，
    在畫面上是一行「2　　35.00」—— 那不是資料，是雜訊。
    ⛔ **`排名` 欄用的是上游清單的原始位置**（`enumerate(_top, 1)`），
    **不是跳過之後重新編號** —— 重新編號會把「上游第 3 檔沒有名字」這件事抹掉，
    使用者會以為他看到的就是完整的前 N 大。
    """
    _h = result.get("holdings")
    _h = _h if isinstance(_h, dict) else {}
    _top = _h.get("top_holdings")
    if not isinstance(_top, list):
        return []
    _rows: list[dict] = []
    for _i, _item in enumerate(_top, start=1):
        if not isinstance(_item, dict):
            continue
        _name = str(_item.get("name") or "").strip()
        if not _name:
            continue
        _rows.append({
            HOLDING_COLS[0]: _i,
            HOLDING_COLS[1]: _name,
            HOLDING_COLS[2]: str(_item.get("sector") or "").strip(),
            HOLDING_COLS[3]: _fmt(_item.get("pct")) or "",
        })
    return _rows


def _holdings_reason(result: dict) -> str:
    """持股抓不到時，**上游自己給的診斷**（`holdings["diag"]`）。

    `fetch_holdings` 全失敗時會回 `{"source": "MoneyDJ:all_failed", "diag": [...]}`
    —— 那份 diag 逐一列出哪個 host 回了什麼，比任何我們自己寫的一句話都有用。
    """
    _h = result.get("holdings")
    _h = _h if isinstance(_h, dict) else {}
    _diag = _h.get("diag")
    if isinstance(_diag, list) and _diag:
        return " ".join(str(_d).strip() for _d in _diag if str(_d).strip())[:300]
    _src = str(_h.get("source") or "").strip()
    return f"上游回報來源：{_src}" if _src else NO_REASON


def _dividend_rows(result: dict) -> list[dict]:
    """格 5｜配息紀錄的表格列。**幣別逐筆帶**（實測欄位，見模組 docstring 第 3 點）。

    ⚠️ 逐筆的 `currency` 在上游可能是**死預設**（`_src_fundclear_div` 缺欄時填 `"USD"`）。
    `reconcile_row_currencies` 的 docstring 已就地寫明它證明不了這一種
    （「上游若整批死預設成同一個錯幣別，這裡照樣回那個錯的值」）。

    ⚠️ **但本頁看得出來的比那句多，這裡據實更正**（2026-09-06 獨立稽核 必修 2）：
    ~~「本檔不假裝看得出來」~~ —— 那句話**低估了本頁手上的東西**。
    本頁另外拿得到 `result["currency"]`（它經過 `_ensure_currency` 修正過，
    正是為了修同一個 USD 死預設）。**兩邊不一致時，本頁看得出來，而且必須說。**
    比對在 :func:`_dividend_caption`。
    **仍然看不出來的只有一種**：逐列與 `result` **整批**被死預設成同一個錯幣別
    —— 那一種本頁確實沒有第三個獨立證據可以推翻，照實承認。
    """
    _divs = result.get("dividends")
    if not isinstance(_divs, list):
        return []
    _rows: list[dict] = []
    for _d in _divs:
        if not isinstance(_d, dict):
            continue
        _amt = _fmt(_d.get("amount"))
        if _amt is None:
            continue                        # 沒有金額的配息列不是資料，是雜訊
        _rows.append({
            DIVIDEND_COLS[0]: str(_d.get("date") or "").strip(),
            DIVIDEND_COLS[1]: str(_d.get("ex_date") or "").strip(),
            DIVIDEND_COLS[2]: str(_d.get("pay_date") or "").strip(),
            DIVIDEND_COLS[3]: _amt,
            DIVIDEND_COLS[4]: str(_d.get("currency") or "").strip() or CCY_UNKNOWN,
            DIVIDEND_COLS[5]: _fmt(_d.get("yield_pct")) or "",
        })
    return _rows


def _declared_currency(rows: list[dict]) -> str:
    """這一組配息能不能**誠實宣告**單一幣別；任何分歧或未知 → `""`。

    直接委派 `shared.data_quality.reconcile_row_currencies`（**不自己寫一份**）：
    本組實測 `['TWD','USD'] → ''`、`['USD','USD'] → 'USD'`、`[] → ''`、`['USD',''] → ''`。
    """
    return reconcile_row_currencies([_r.get(DIVIDEND_COLS[4], "") for _r in rows])


def _trace_rows(result: dict) -> list[dict]:
    """格 6｜逐源軌跡。**成功與失敗都列** —— 只列失敗會看不出「試過哪些」。"""
    _tr = result.get("source_trace")
    if not isinstance(_tr, list):
        return []
    _rows: list[dict] = []
    for _t in _tr:
        if not isinstance(_t, dict):
            continue
        # ⚠️ **三態，不是二態**：`success` 缺鍵 ≠ 失敗（見 :data:`TRACE_UNKNOWN`）。
        #    `_failed_source_count()` 只數 `TRACE_FAIL`，所以「上游沒說」不會被計入 ——
        #    這與 :data:`SYNTHETIC_TRACE_SOURCES` 那條排除是**兩道各自獨立**的防線：
        #    前者按**名字**排除（就算上游哪天補上 `success: False` 也擋得住），
        #    後者按**有沒有說**排除（就算名字沒被登記也不會被誣賴成失敗）。
        _succ = _t.get("success", _MISSING)
        if _succ is _MISSING:
            _result = TRACE_UNKNOWN
        else:
            _result = TRACE_OK if bool(_succ) else TRACE_FAIL
        _detail = _t.get("error") or _t.get("note")
        if _detail is None and _t.get("nav_count") is not None:
            _detail = f"取得 {_t['nav_count']} 筆淨值"
        _rows.append({
            TRACE_COLS[0]: str(_t.get("source") or "").strip(),
            TRACE_COLS[1]: _result,
            TRACE_COLS[2]: str(_detail or "").strip(),
        })
    return _rows


def _has_anything(result: dict) -> bool:
    """這次取數**到底有沒有帶回任何一格能用的東西**。

    ⚠️ **這個旗標存在的唯一理由，是不要讓一句話跑到不屬於它的格子裡。**
    本組初稿把 :func:`_fetch_failed_note`（「這個代碼在 N 個來源都沒有取到淨值」）
    當成**所有**空格子的共用文案 —— 於是一檔**淨值抓到了、只是沒有配息**的基金，
    配息那一格會印出「沒有取到淨值」。**那是一句對著使用者說的假話**，
    而且它看起來完全合理，正是 §1 最難發現的那一種。
    → 全敗才用共用文案；只要有任何一格有料，其餘空格一律講**自己**的原因。
    """
    return bool(_series_of(result) is not None
                or _perf_lines(result)[0]
                or _risk_lines(result)[0]
                or _holdings_rows(result)
                or _dividend_rows(result))


def _nav_reason(result: dict) -> str:
    """淨值序列缺席的原因 —— **優先用上游 `source_trace` 裡自己寫的那一句**。

    `finalize_fund_metrics` 會就地追加 `{"source": "nav_series", "success": False,
    "error": "無淨值序列"}`，序列太短時則是 `"只有 N 筆(需≥10)"`。
    那兩句分別對應完全不同的下一步（換代碼／等資料補齊），**不能合併**。
    """
    for _r in _trace_rows(result):
        if _r[TRACE_COLS[0]] == TRACE_NAV_SERIES and _r[TRACE_COLS[1]] == TRACE_FAIL:
            return _r[TRACE_COLS[2]] or NO_REASON
    return "這次沒有帶回淨值序列，上游也沒有說明原因。"


def _fetch_failed_note(result: dict) -> str:
    """全敗時的**共用處境描述** —— 刻意寫成「兩種可能」，因為 L2 分不出來。

    ⛔ **總管裁決（2026-09-06，內部自決）：不畫紅、也不寫「查無此檔」。**
    `auto_fetch_moneydj` 對「代碼打錯」與「來源全掛」**回傳完全一樣的 failed**，
    `source_trace` 的 error 是「查無資料」「所有平台均無回應」這種泛稱。
    - 塗紅 → 對打錯代碼的人謊稱系統故障；
    - 寫「查無此檔」→ 對來源掛掉的人謊稱這檔不存在。
    **兩種都是編出來的**，而 L2 沒有給我們分辨所需的資訊。
    → 誠實的做法是說出兩種可能，並把逐源軌跡攤開讓使用者自己判斷（格 6）。
    """
    _n = _failed_source_count(result)
    _where = f"（逐一嘗試的結果列在下方的「{DEEP_DIVE_PROVENANCE}」）"
    if _n:
        return (f"在 {_n} 個來源都沒有取到淨值 —— {_BLAME_FREE}{_where}")
    return f"這次取數沒有帶回任何淨值，上游也沒有留下逐源紀錄 —— {_BLAME_FREE}"


def _failed_source_count(result: dict) -> int:
    """**真的試過而且失敗**的來源數；合成標記不算，同名只算一次。

    ⛔ **不要退回 `sum(1 for … if 失敗)`**（2026-09-06 獨立稽核 應修 2）：
    那會把 :data:`SYNTHETIC_TRACE_SOURCES` 也算進去 —— 實測畫面曾印
    「這個代碼在 **3** 個來源都沒有取到淨值」，而**實際只試了 2 個**，
    第 3 個是 `nav_series`（「沒有淨值序列」這個**判定**本身）。
    **同一個東西一邊被 :func:`_nav_reason` 當標記用、一邊被算成來源數**，
    那個數字是編出來的證據。

    ⚠️ **去重**：同一個來源在 fallback chain 裡可能被追加多次
    （例如短窗重試），數兩次同樣是虛報。
    """
    _names = {_r[TRACE_COLS[0]] for _r in _trace_rows(result)
              if _r[TRACE_COLS[1]] == TRACE_FAIL}
    return len({_n for _n in _names if _n and _n not in SYNTHETIC_TRACE_SOURCES})


def _render_deep_dive() -> None:
    """區塊 3｜單一基金深度。**六格全部由同一次 L2 呼叫供給。**

    ⛔ **一次呼叫，不是六次。** 六格各自呼叫一次 ＝ 六次網路往返（L1 有 TTL cache，
    但 `finalize_fund_metrics` 每次都會重跑），而且六格可能拿到**不同時間點**的
    快照 —— 畫面上會出現「NAV 是今天的、持股是一小時前的」而沒有任何跡象。
    守衛：`tests/test_wf03_research_skeleton.py::test_the_deep_dive_fetches_exactly_once`。

    ⛔ **本函式沒有 try/except，這是刻意的。** `auto_fetch_moneydj` 的 URL 直傳分支
    會原封拋出下游例外（本組實測）—— 那條路徑一路拋到
    `safe_section(BLOCK_DEEP, …)`，由它用**真的**例外物件畫紅框 ＋ traceback。
    自己接下來再包一個假例外去塗紅，是 §1 明禁的造假。

    ⚠️ **「選定後展開」仍未恢復**（模組 docstring 已登記）：結果卡還沒接上，
    沒有東西可以被「選定」，所以本批直接拿**已送出的查詢字串**當基金鍵。
    下一批接上結果卡時，這裡要改吃使用者選中的那一檔。
    """
    _query = _applied_query() or {}
    _result = auto_fetch_moneydj(str(_query.get("term") or ""))
    if not isinstance(_result, dict):
        # `return_page_type=False` 的契約就是回 dict；型別不對代表上游換了契約。
        # ⛔ 不猜、不降級 —— 交給 `safe_section()` 畫紅框（§1）。
        raise TypeError(
            f"auto_fetch_moneydj() 應回 dict（return_page_type=False），"
            f"實際得到 {type(_result).__name__} —— 上游契約變了，畫面不得自行降級。")

    _where = _pending_where(BLOCK_FORM)
    # ⚠️ **共用文案只在「一格都沒有」時才准用**（理由見 :func:`_has_anything`）。
    _blank = _fetch_failed_note(_result) if not _has_anything(_result) else ""

    _nav = _nav_facts(_result)
    _perf_shown, _perf_missing = _perf_lines(_result)
    _risk_shown, _risk_missing = _risk_lines(_result)

    render_cards([
        _nav_card(_nav, _blank or _nav_reason(_result), _where),
        _perf_card(_perf_shown, _perf_missing, _perf_source(_result),
                   _blank or "上游沒有給任何期別的報酬。", _where),
        _risk_card(_risk_shown, _risk_missing,
                   _blank or "上游沒有給任何風險指標。", _where),
    ])

    # ── 持股與配息：大表全寬（線框：「持股與配息為大表全寬」）───────────────
    # ⛔ `wide_table` **不得**放進 `card_row()` 的欄位裡（layout.py 就地寫明理由）。
    _hold_rows = _holdings_rows(_result)
    st.markdown(f"##### {DEEP_DIVE_TABLES[0]}")
    if wide_table(_hold_rows,
                  empty_title=f"{DEEP_DIVE_TABLES[0]}還沒有可顯示的列",
                  empty_missing=(_holdings_reason(_result) if _result.get("holdings")
                                 else _blank or "上游這次沒有回傳持股資料。"),
                  empty_where=_where):
        st.caption(_holdings_caption(_result, len(_hold_rows)))

    _div_rows = _dividend_rows(_result)
    st.markdown(f"##### {DEEP_DIVE_TABLES[1]}")
    if wide_table(_div_rows,
                  empty_title=f"{DEEP_DIVE_TABLES[1]}還沒有可顯示的列",
                  empty_missing=(_blank or
                                 "這一檔在上游沒有配息紀錄 —— "
                                 "可能是它不配息，也可能是配息頁當下取不到。"),
                  empty_where=_where):
        st.caption(_dividend_caption(_div_rows, str(_result.get("currency") or "")))

    # ── 來源標註（讀法 A：標註，不是第六個內容區塊；理由見模組 docstring）──────
    _trace = _trace_rows(_result)
    st.markdown(f"##### {DEEP_DIVE_PROVENANCE}")
    st.caption(_provenance_caption(_result, _nav))
    wide_table(_trace,
               empty_title=f"{DEEP_DIVE_PROVENANCE}還沒有可顯示的列",
               empty_missing="這次取數沒有留下逐源紀錄（上游未提供 source_trace）。",
               empty_where=_where)


def _nav_card(nav: dict | None, blank_note: str, where: str) -> dict:
    """格 1 的卡片定義。`nav is None` → 灰態，**不填任何數字**。"""
    if nav is None:
        return {"title": DEEP_DIVE_CARDS[0], "state": STATE_NOT_READY,
                "note": blank_note, "where": where}
    _ccy = nav["currency"] or CCY_UNKNOWN
    _bits = [f"{nav['n']} 筆", f"{nav['first']} ~ {nav['last']}"]
    if isinstance(nav["span_days"], int):
        _bits.append(f"跨度 {nav['span_days']} 天")
    if nav["name"]:
        _bits.insert(0, nav["name"])
    if nav["merged"]:
        _bits.append(nav["merged"])
    return {"title": DEEP_DIVE_CARDS[0],
            "value": f"{nav['latest']} {_ccy}",
            "note": " · ".join(_bits)}


def _perf_card(shown: list[str], missing: list[str], source: str,
               blank_note: str, where: str) -> dict:
    """格 2 的卡片定義。**一個期別都沒有 → 灰態**；有幾個就畫幾個。"""
    if not shown:
        return {"title": DEEP_DIVE_CARDS[1], "state": STATE_NOT_READY,
                "note": blank_note, "where": where}
    _note = [" · ".join(shown)]
    if source:
        _note.append(f"來源：{source}")
    if missing:
        _note.append(f"未提供：{'、'.join(missing)}")
    return {"title": DEEP_DIVE_CARDS[1], "value": shown[-1], "note": "　".join(_note)}


def _risk_card(shown: list[str], missing: list[str],
               blank_note: str, where: str) -> dict:
    """格 3 的卡片定義。

    ⛔ **缺的指標連同它自己的原因一起印，不合併成一句。**
    `sortino` 缺（樣本不足）與 `std_1y` 缺（序列稀疏）是兩件事，
    合併成「部分指標無法計算」就把兩個不同的下一步抹成同一個。
    """
    if not shown:
        # ⚠️ 五個指標全缺時，`missing` 裡可能**每一條都是** :data:`NO_REASON`
        #    （上游根本沒跑到計算那一步）。那種「原因」沒有資訊量，
        #    此時改用區塊層級那句誠實的處境描述，**不要印五行「上游沒有附缺值原因」**。
        _real = [_m for _m in missing if not _m.endswith(NO_REASON)]
        return {"title": DEEP_DIVE_CARDS[2], "state": STATE_NOT_READY,
                "note": "；".join(_real) if _real else blank_note, "where": where}
    _note = [" · ".join(shown)]
    if missing:
        _note.append("未計算 —— " + "；".join(missing))
    return {"title": DEEP_DIVE_CARDS[2], "value": shown[0], "note": "　".join(_note)}


def _holdings_caption(result: dict, n_rows: int) -> str:
    """持股表底下的血緣一行：截止日 ＋ 來源 ＋ 抓取時間。缺哪一項就不寫哪一項。"""
    _h = result.get("holdings")
    _h = _h if isinstance(_h, dict) else {}
    _bits = [f"{n_rows} 檔"]
    for _key, _label in (("data_date", "截止"), ("source", "來源"),
                         ("fetched_at", "抓取於")):
        _v = str(_h.get(_key) or "").strip()
        if _v:
            _bits.append(f"{_label} {_v}")
    return " · ".join(_bits)


def _dividend_caption(rows: list[dict], fund_ccy: str) -> str:
    """配息表底下的一行。**逐列一致「而且」與基金計價幣別一致，才敢宣告單一幣別。**

    ## ⛔ 這個 `fund_ccy` 參數是 2026-09-06 獨立稽核（必修 2）加的，別再拿掉

    在此之前本函式**只看逐列**，於是同一個畫面上同時出現：

    ```
    NAV 走勢     59.99 TWD
    配息紀錄     2 筆 · 全部以 USD 計價
    ```

    **兩句都是本頁印的，而且互相矛盾。** 成因在上游、但**本頁是第一個把它端上畫面的**：
    - `repositories/fund/sources.py::_src_fundclear_div` 缺欄時
      `item.get("Currency") or item.get("currency") or **"USD"**` —— **逐列 USD 死預設**；
    - 而 `repositories/fund/fund_orchestration.py::_ensure_currency` 的 docstring 自陳
      「純代碼經 **`auto_fetch_moneydj`** 會被合成 URL →「計價幣別」缺欄 **USD 死預設** …
      此處在收口再修一次」—— 也就是 **v19.505 已經認定這個死預設是 bug 並修了
      `result["currency"]`，但沒修 `dividends[i]["currency"]`。**
      本頁走的正是那條路，端出來的正是沒修的那一半。

    **數字是真的、單位是編的**（§4.1 量綱陷阱），也正是客戶原話「我不接受假資料」。

    ⛔ **不得改成「相信 `result` 那一邊」**：`result["currency"]` 經過 `_ensure_currency`
    修正，只是**比較可信**，不是**確定對**。**§1 的答案是不宣稱，不是挑一個比較可能的宣稱。**

    ⚠️ 三方比對一律走 `reconcile_row_currencies`（**不自己寫比較邏輯**）：
    單一元素進去 ＝ 借它做 ISO 正規化（認不得就回 `""`），兩元素進去 ＝ 一致性判定。
    """
    _row = _declared_currency(rows)                       # 逐列一致才非空
    _fund = reconcile_row_currencies([fund_ccy])          # 可辨識的 ISO 才非空
    _agreed = reconcile_row_currencies([_row, _fund])
    if _agreed:
        return f"{len(rows)} 筆 · 全部以 {_agreed} 計價 · 金額為原幣，未做任何換算"
    if _row and _fund:
        # 兩邊都講得出一個 ISO，但講的不是同一個 —— 這是**資料疑義**，要指名道姓。
        return (f"{len(rows)} 筆 · ⚠️ 資料疑義：逐筆配息宣告 {_row}，"
                f"這檔基金的計價幣別卻是 {_fund} —— 兩邊不一致，本頁**不挑一個**宣告"
                "（§1 不猜值）· 金額照原幣顯示，不合計、不換算")
    return (f"{len(rows)} 筆 · {CCY_UNKNOWN}或逐筆幣別不一致 —— "
            "金額照原幣顯示，**不合計、不換算**（不猜值）")


def _provenance_caption(result: dict, nav: dict | None) -> str:
    """來源標註的摘要行：這一份資料是什麼時候抓的、淨值那條線來自哪裡。"""
    _bits: list[str] = []
    _at = str(result.get("_moneydj_fetched_at") or "").strip()
    if _at:
        _bits.append(f"本次抓取於 {_at}")
    if nav is not None and nav["source"]:
        _bits.append(f"淨值序列來源 {nav['source']}")
    if nav is not None and nav["fetched_at"]:
        _bits.append(f"序列抓取於 {nav['fetched_at']}")
    if not _bits:
        # ⚠️ **不留空**：血緣掉了本身就是要告訴使用者的事（`attrs` 會在 concat 中掉）。
        return "上游這次沒有帶回抓取時間與序列來源標記。"
    return " · ".join(_bits)


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
               empty_missing=f"{_BATCH_PENDING_NOTE}（多檔同一組指標的結果表與續跑進度）。",
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
