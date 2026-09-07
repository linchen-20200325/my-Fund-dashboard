"""③ 標的探索 —— 五分頁動線重構的第三頁（全新撰寫，非舊三個 `tab*.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。
客戶方針（2026-09-05）：本頁**只做骨架 + 灰態**；結果卡、深度區與批次的真內容**分批填**。
2026-09-06 深度區接上真取數；**2026-09-07 批次分析接上真取數**（客戶三項拍板，見 :func:`_render_batch`）。
⚠️ **仍是灰態的只剩「搜尋結果」一塊** —— 它卡在 `services/**` 沒有搜尋入口，理由見下方。

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

資料從哪裡來（**深度區與批次都已接上**；只剩搜尋結果是缺口）
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
  （:data:`_RESULTS_PENDING_NOTE`）。
  ⚠️ 2026-09-06 起**不再是一句共用的「本頁分批上線」** —— 各塊卡住的原因不同，
  理由見那些常數上方的 ⛔ 段。
  ⚠️ 這些句子混成一句，會讓使用者以為「輸入代碼按下去就會出現結果」—— 不會。
  同樣的分岔在 ① 與 ② 都做過一次（`page_01_macro.py::_detail_pending`、
  `page_02_health.py::_pending_where`）。
- **批次自己的兩種空** → :data:`_BATCH_EMPTY_MISSING`（還沒貼）與
  :data:`_BATCH_UNPARSED_MISSING`（貼了但認不得）。**同樣刻意不共用一句** ——
  下一步不同（去貼 vs 去改格式）。

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

import re
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
from ui.helpers.tw_time import tw_now_str

# ⚠️ **L2 服務層（客戶方針第 2 條的唯一取數入口）**。
#    `services.moneydj_fetcher` 是 L2；它自己往下走 `services.fund_service` 的
#    enriched wrapper → L1。本檔**不碰** `repositories` / `infra` / 任何網路函式庫，
#    由 `tests/test_wf03_research_skeleton.py::test_the_page_never_reaches_into_the_data_layer` 釘住。
from services.moneydj_fetcher import auto_fetch_moneydj
# 幣別一致性判定（純函式、零 I/O）。**不自己寫一份** —— §1 的失效模式就寫在它的 docstring 裡。
from shared.data_quality import reconcile_row_currencies
# 寬鬆數值轉換（`"1,234"` / `"12.3%"` / None → float | None）。批次大表的數值欄要它。
# **不自己寫一份** —— 它是 repo 既有的 SSOT（`shared/converters.py`）。
from shared.converters import safe_num

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

#: ~~區塊 4 的灰態理由。**缺的是一個輸入欄位，不是資料。**~~
#: ~~`_BATCH_PENDING_NOTE = "批次要能一次收多個代碼，而本頁目前只有一個收單一代碼的~~
#: ~~搜尋框 —— 多代碼的輸入欄位是版面異動，要先出線框草稿拍板才會加"`~~
#: → **2026-09-07 換掉（有意識的政策變更，不是漏刪；決策者：客戶）。**
#:
#: **舊表述在寫下的當天完全正確**：多代碼輸入欄位確實是版面異動，確實該先拍板 ——
#: 上一批把它擋下來、寫成灰態、登記待請示，那個處置是對的。
#: **被推翻的是它的前提**：客戶 2026-09-07 已就三項拍板（① 只做貼上框、不做檔案上傳
#: ② 大表照搬全部欄位、不挑子集 ③ ③ 與 ② 的功能重疊兩邊都留），
#: 「要先出線框草稿拍板才會加」這句話**自那一刻起不再為真**，留著就是對使用者說謊。
#:
#: 現在這一塊卡住的原因換成一句**當下真的成立**的話：**貼上框是空的**。
#: ⚠️ 它是**空狀態**（使用者照著做真的能解決），不是「這一塊還沒做」的 pending ——
#:    差別寫在 :func:`_render_batch` 的 docstring。
_BATCH_EMPTY_TITLE: str = "還沒有要批次分析的基金"
_BATCH_EMPTY_MISSING: str = (
    "上面的貼上框是空的，或還沒按下送出 —— "
    "批次是**多代碼**一次跑，貼幾行代碼進去它才有東西可跑")
#: 貼上框有字、但一個代碼都認不出來。**與上一句不是同一件事**：
#: 上一句是「還沒給」，這一句是「給了但認不得」—— 下一步不同（去貼 vs 去改格式），
#: 混成一句使用者無從判斷哪一個跟他有關。
_BATCH_UNPARSED_TITLE: str = "貼上的內容裡找不到基金代碼"
#: 代碼收到了、但一檔都還沒跑完。**與上面兩句又是不同的處境**（他已經給了、也送出了）。
_BATCH_NOTHING_RUN_TITLE: str = "這一批還沒有任何一檔跑完"
_BATCH_NOTHING_RUN_MISSING: str = (
    "代碼已經收到了，但還沒有任何一檔跑完 —— 按一次「{submit}」開始跑")
_BATCH_UNPARSED_MISSING: str = (
    "認得的形狀是**3~20 碼的英數字**（小寫會自動轉大寫）；每行只讀第一欄，"
    "所以「代碼,基金名」這種貼法也可以。常見的表頭字（代號／基金代碼／CODE …）會自動略過")

#: ⭐ **批次的本金口徑**。`build_batch_unified_row(code, principal_twd=…)` 的預設值就是它，
#: 而舊 `ui/tab_batch_analysis.py` 的呼叫端**不傳這個引數** —— 也就是說批次向來就是
#: 「**每一檔都假設投入 100 萬台幣**」的齊頭模擬基準。本頁**照舊**，不改口徑。
#:
#: ⛔ **不得**改成「使用者實際投入的金額」：那是 ② 的口徑（見 :data:`BATCH_PRINCIPAL_NOTE`），
#:    在這裡改掉會讓同一張大表的配息金額欄突然換一套意義，而畫面上看不出來（§1）。
#: ⚠️ 具名而不 inline，是為了讓「有人把它改成別的數字」看得見 —— 它一改，
#:    四類欄位（原幣本金／可申購單位／每月配息／累積配息）全部跟著變。
BATCH_PRINCIPAL_TWD: float = 1_000_000.0

#: ⭐ **本頁與 ② 的口徑差異** —— `{health}` 由呼叫端以 `tab_label('health')` 填入。
#:
#: ⚠️ **這一句是實測出來的，不是照抄派工單** —— 派工單給的例句把兩邊講反了，
#:    本組查證後採相反的寫法。三條各自獨立的依據（皆本組實跑／開檔核對）：
#:
#:    1. `services/fund_row.py::process_one_fund` 的 docstring 逐字：
#:       「`principal_twd`: 本金 TWD（健診 Tab／**批次統一 100 萬**；
#:       Tab3 用**各檔實際 invest_twd**）」。
#:    2. `build_batch_unified_row(code, principal_twd=1_000_000.0, …)` 的**預設值**是
#:       100 萬，而舊 `ui/tab_batch_analysis.py` 的唯一呼叫點**不傳這個引數**
#:       —— 也就是說批次**吃預設**，使用者連改都改不了。
#:       旁證：該檔的欄位說明 expander 逐字寫著「每月配息／累積台幣配息／原幣本金／
#:       單位 全都假設**投入 100 萬台幣**來比較」。
#:    3. **② 那一側是新頁、不是舊健診 Tab**：`ui/views/page_02_health.py::`
#:       `_render_delegated_sections` 餵給舊模組的是使用者的持股清單
#:       （**各檔實際投入金額**），它的 docstring 就地寫著「舊 ② 餵的是
#:       `_build_fund_dict(..., principal_twd)` ——『每檔硬寫同一個本金』的齊頭模擬基準；
#:       新 ② 餵的是 …『使用者每檔實際投入』」。
#:       而該頁那個「本金（TWD）」輸入框**目前 0 caller**（同檔 2026-09-07 就地登記），
#:       所以 ② 畫面上的配息金額吃的是實際投入、不是那個框裡的數字。
#:
#:    4. **⚠️ 已核准線框目錄裡有一份草稿說的是相反的事，這一條非讀不可**：
#:       `docs/wireframes/draft-p03-batch-input.html`（**2026-09-06**，實作組 R 提出、
#:       客戶尚未拍板的提案草稿）的 Q3 逐字寫著「**健診 Tab 在「統一 100 萬」那一側**，
#:       走實際持倉金額的是 **Tab3（＝④ 資產配置）**」。
#:       **那句話在寫下的當天是對的** —— 它描述的是**舊** ②
#:       （`ui/tab_fund_grp_health.py`，本金 widget `value=1_000_000.0`、
#:       help 逐字「所有基金都假設投入這個金額」）。
#:       **被推翻的是它的前提**：`app.py` 已於 **2026-09-07**（commit `c321c0a`）
#:       把 ② 換成 `ui/views/page_02_health.py`（`render_holdings_health()`），
#:       而**舊的 `render_fund_grp_health_tab()` 現在 production 0 caller**（本組實測）。
#:       → **本註描述的是使用者今天真的看得到的那個 ②**，與草稿不衝突，
#:       只是**兩者講的是不同時點的兩個實作**。
#:       ⛔ **不要**拿草稿 Q3 來「更正」這裡，也**不要**拿這裡去改草稿 ——
#:       草稿是拍板紀錄，本檔是現況；**已回報總管，由他決定要不要在草稿上補一行時效註**。
#:
#: ⚠️ **本組沒有查證的那一半，據實寫明**：以上第 1~3 條都是**靜態追蹤**（讀原始碼 ＋ 呼叫點）。
#:    本組**沒有**在真的 Streamlit 裡跑一次兩頁、拿同一檔基金去比對兩邊的配息金額欄
#:    —— 沙箱沒有 streamlit / pandas，跑不了（見模組 docstring 末段）。
#:    依 `CLAUDE.md §-2` 規則 6，這一段只能當**單組實測的靜態結論**，不是端到端實證。
BATCH_PRINCIPAL_NOTE: str = (
    "這張表的每一檔都**假設投入 100 萬台幣**來比較 —— 原幣本金／可申購單位／"
    "每月配息／累積台幣配息這幾欄全部吃這個假設，**不是你實際投入的金額**。"
    "「{health}」算的才是**你每一檔實際投入的金額**：同一檔基金在兩邊的配息金額欄"
    "**不會一樣，那不是算錯** —— 這裡問的是「同樣一筆錢，買哪一檔比較好」，"
    "那裡問的是「我手上這一檔現在怎麼樣」。")

# ── 批次分析：Form 與 session 鍵 ──────────────────────────────────────────
#: 批次自己的送出閘門。**與搜尋框是兩個獨立的 form**，理由見 :func:`_render_batch`。
_BATCH_FORM_KEY: str = "v03_research_batch_form"
#: **已送出**的代碼清單（`list[str]`）。沒送出過 ＝ 不存在。
_SK_BATCH_CODES: str = "v03_research_batch_codes"
#: 已跑完的列：`{代碼: 79 欄的 dict}`。**只活在 session 裡**（見 :func:`_run_batch`）。
_SK_BATCH_ROWS: str = "v03_research_batch_rows"
#: 本輪執行時間（台北）。
_SK_BATCH_RUN_AT: str = "v03_research_batch_run_at"

#: 線框沒有指定批次送出鈕的字（它只畫了頁面頂端那一顆「搜尋」）。
#: 取最平鋪直敘的動詞，並把「繼續」寫進去 —— 因為再按一次會**跳過已完成的檔**。
BATCH_SUBMIT_LABEL: str = "開始 / 繼續批次分析"
_LABEL_BATCH_CODES: str = "基金代碼（每行一檔）"
_LABEL_BATCH_RETRY: str = "連同上一輪失敗 / 部分成功的檔一起重抓"

#: 代碼的形狀 ＋ 常見表頭字。**與舊 `ui/tab_batch_analysis.py::_parse_codes` 同一組規則**
#: —— ⚠️ 那是一份**重複**，不是共用：舊檔依方針第 3 條會被整批拔除，
#:    而本頁**一行都不 import 它**（`tests/test_wf03_research_skeleton.py::`
#:    `test_the_page_does_not_delegate_to_the_old_tabs`），所以只能各留一份。
#:    ⛔ 這是**已知的第二份真相源**，已寫進 PR 登記；舊檔拔除時應收成一處。
_CODE_RE_SRC: str = r"^[A-Z0-9]{3,20}$"
_HEADER_TOKENS: frozenset[str] = frozenset({
    "CODE", "SYMBOL", "TICKER", "代號", "基金代號", "基金代碼", "標的", "標的代號"})

#: 每檔耗時（秒）。⚠️ **不是本組估的**：逐字取自舊 `ui/tab_batch_analysis.py` 的
#: `_SEC_PER_FUND_FAST` / `_SEC_PER_FUND_SLOW`，那兩個值來自該檔記載的 2026-08-14 實測
#: （「原本 ~5s/檔、實機實測 ~45s/檔，400 檔原顯示『約 33 分鐘』實際約 5 小時 —— 差 9 倍」）。
#: ⛔ **不得**憑印象調小：使用者照這個數字決定要不要按下去，**低報等於騙他**。
#: ⚠️ 同上，這是第二份真相源；`tests/test_wf03_research_batch.py::`
#: `test_the_time_estimate_mirrors_the_old_tab` 會逐值比對舊檔，改一邊就轉紅。
_SEC_PER_FUND_FAST: int = 20
_SEC_PER_FUND_SLOW: int = 45
#: 超過這個檔數就跳警告（舊檔同值）。
_LONG_RUN_FUNDS: int = 100

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
    （:data:`_RESULTS_PENDING_NOTE`、:data:`_BATCH_EMPTY_MISSING` …）已經先講了
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
#:
#: ⛔ **三態開了兩個新邊界，據實揭露；本輪刻意不改行為** ⛔
#: ---------------------------------------------------------------------------
#: 完整分類矩陣（**2026-09-06 實跑**，不是推論）：
#:
#: ===================================== ============ ==============
#: 上游那一則的形狀                        結果欄        計入來源數
#: ===================================== ============ ==============
#: 缺 ``success`` 鍵                       上游沒說       0
#: ``success: None``（說了、值是空）        失敗          1
#: ``success: False``（真的失敗）           失敗          1
#: 有 ``error`` 但**無** ``success`` 鍵      上游沒說       0   ← **(a)**
#: ===================================== ============ ==============
#:
#: **(a) 我修掉「多報」的同時，開了一條「少報」的路。**
#:     ``{"source": X, "error": "HTTP 500"}`` 這種**帶 error、沒有 success 鍵**的形狀，
#:     舊的二態會算成失敗，現在**從來源數消失**。
#:     ⚠️ 而 :data:`SYNTHETIC_TRACE_SOURCES` 上方那段只論證過「**虛報比漏排除危險**」——
#:     **它沒有涵蓋這個新方向。**
#:     ✅ **今天沒踩到**：兩個 producer 檔裡真正進 trace 且缺 ``success`` 的，
#:     只有 `services/fund_service.py:1131` 那一個良性的。**這是前瞻風險，不是現行 bug。**
#:     ⛔ **不改行為的理由**：要改就得訂一條「有 ``error`` 就算失敗」的規則，
#:     而上游**沒有保證** ``error`` 只在失敗時出現 —— 那會是另一個沒查證就發明的規則。
#:
#: **(b) ``success: None`` 這一格與上面那句原則不自洽，我承認。**
#:     引入 :data:`_MISSING` 的理由是「**說了但值是空** ≠ **沒說**」，
#:     然後這裡把「說了但值是空」畫成**確定的失敗並計入** ——
#:     按「不知道就說不知道」，它其實也該是「上游沒說」。
#:     ⛔ **本輪不改**：目前**沒有任何 production 形狀**會產生它
#:     （見上方 §「哪些 source 會以 falsy success 出現」的實測列舉），
#:     為一個不存在的形狀改行為是拿猜測換猜測。**但這個不自洽登記在這裡，不是沒看到。**
#: ---------------------------------------------------------------------------
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


# ══════════════════════════════════════════════════════════════════════════
# 區塊 4｜批次分析 —— 版面與互動在這裡，**計算一行都不在這裡**
#
# 客戶 2026-09-07 三項拍板（逐條落在下面哪裡，寫清楚免得下一個人以為可以自己改）：
#   ① **只做貼上框，不做檔案上傳** → :func:`_render_batch` 只有一個 `st.text_area`。
#      理由（客戶原話的技術面）：多一個上傳元件就多一組失敗路徑（解碼失敗、
#      編碼判斷、檔案型別），而真的需要再加屬**純新增**，不會推翻這張草稿。
#      ⚠️ 舊 `ui/tab_batch_analysis.py` **有** `st.file_uploader` —— 本頁刻意沒有，
#      **那是拍板，不是漏做**，由 `tests/test_wf03_research_batch.py` 釘住。
#   ② **大表照搬全部欄位，不挑子集** → :func:`_batch_table_rows` 以
#      `BATCH_UNIFIED_COLUMNS`（實測 79 欄）為欄骨架逐列投影，**一欄都不篩**。
#      挑哪幾欄是**新的業務決定**，會讓這一批從「搬版面」變成「改規格」。
#   ③ **③ 與 ② 的功能重疊：兩邊都留，③ 不收欄位** → 重疊是刻意的，
#      口徑差異就地寫在畫面上（:data:`BATCH_PRINCIPAL_NOTE`）。
#
# ⚠️ **路線 (A)：邏輯一律呼叫既有舊模組。** 本區唯一的計算入口是
#    `ui.helpers.fund_grp_health.unified.build_batch_unified_row`（**與舊批次分頁
#    同一支、同一條資料路徑**）。本檔**不重寫、不搬移、不改資料路徑**。
#    ⛔ 它**不是**線框「從哪裡搬來」列的那三個舊分頁之一 —— 那三個是
#    `ui/tab2_single_fund.py` / `ui/tab_fund_research.py` / `ui/tab_batch_analysis.py`，
#    本檔一行都沒 import（`test_the_page_does_not_delegate_to_the_old_tabs`）。
#    ② `ui/views/page_02_health.py` 委派 `ui.helpers.fund_grp_health.*` 是同一個形狀。
# ══════════════════════════════════════════════════════════════════════════

def _parse_codes(raw: object) -> list[str]:
    """把一坨貼上的文字收成**去重、大寫、保留首次出現順序**的代碼清單。

    規則（逐條與舊 `ui/tab_batch_analysis.py::_parse_codes` 相同）：
    逗號／分號／Tab／換行皆為分隔；**每行只取第一欄**（容忍「ACCP138,美元基金」
    這種從試算表貼過來的兩欄）；只留符合 :data:`_CODE_RE_SRC` 的 token；
    過濾 :data:`_HEADER_TOKENS` 那幾個常見表頭字。

    ⛔ **這是一份重複實作，不是共用** —— 理由寫在 :data:`_CODE_RE_SRC` 上方。

    ⚠️ **`raw` 刻意收 `object` 而不是 `str`**：`st.text_area` 在某些替身／
    降級路徑下不保證回字串，而 `"".join` 之類的寫法遇到非字串會**靜默**產生
    一個看起來合理的空清單。這裡顯式 `isinstance` 判斷，非字串一律回 `[]`
    —— 空清單會讓畫面走空狀態（誠實），不會假裝跑了一輪。
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    _out: list[str] = []
    _seen: set[str] = set()
    for _line in raw.replace("\r", "\n").split("\n"):
        _line = _line.strip()
        if not _line:
            continue
        _token = re.split(r"[,\t;]", _line, maxsplit=1)[0].strip().upper()
        if not _token or _token in _HEADER_TOKENS:
            continue
        if not re.match(_CODE_RE_SRC, _token):
            continue
        if _token not in _seen:
            _seen.add(_token)
            _out.append(_token)
    return _out


def _batch_where() -> str:
    """批次那兩種空狀態的「去哪補」。**這一則是真的有效的那一種。**

    ⚠️ **刻意不走** :func:`_pending_where`（它指的是「搜尋條件」）——
    搜尋條件那一格**解決不了**「還沒貼代碼」這件事：使用者照它做會去打一個
    單一代碼、按「搜尋」，然後回到這裡看到**一模一樣的灰**。
    本則指到**批次自己的貼上框**：分頁 → 區塊 → 欄位，三段都是畫面上真的有的東西，
    而且照著做**真的會離開灰態**。

    ⛔ 對照 :func:`_pending_where` 的長註：那一族之所以「有效性有限」，
    是因為那一塊還沒接上、去哪都沒用。**批次已經接上了，所以這一則不該再沿用它。**
    `tests/test_wf03_research_batch.py::test_the_batch_pointer_is_the_paste_box`
    釘住這個差別 —— 改回 `_pending_where()` 會轉紅。
    """
    return f"{where_to_find('research')} → {BLOCK_BATCH} → {_LABEL_BATCH_CODES}"


def _applied_batch_codes() -> list[str]:
    """**已送出**的批次清單。沒送出過（或送出的解析不到代碼）＝ 空 list。

    ⚠️ 與 :func:`_applied_query` 同一個道理：下游一律讀這個，
    **不要讀 `st.text_area` 的回傳值** —— 讀了就等於沒有 form。
    """
    _cur = st.session_state.get(_SK_BATCH_CODES)
    return [str(_c) for _c in _cur] if isinstance(_cur, list) else []


def _batch_rows() -> dict:
    """已跑完的列：`{代碼: 79 欄的 dict}`。"""
    _cur = st.session_state.get(_SK_BATCH_ROWS)
    return _cur if isinstance(_cur, dict) else {}


def _is_batch_fail(row: object) -> bool:
    """這一檔算不算失敗 / 無效 —— 狀態欄含「失敗」或「無效」。

    ⚠️ 「⚠️ 部分成功」**不算**失敗：它有抓到淨值、大部分欄位算得出來，
    只是某一組欄留白。**判「該不該重跑」請用** :func:`_is_batch_retryable`。
    """
    _s = str((row or {}).get("狀態", "")) if isinstance(row, dict) else ""
    return ("失敗" in _s) or ("無效" in _s)


def _is_batch_retryable(row: object) -> bool:
    """值不值得重跑 ＝ 抓取失敗／代號無效／**部分成功**。

    ⚠️ 「部分成功」多半是暫時的（大盤基準抓失敗／匯率逾時），重跑單檔通常就好了；
    把它排除在重試之外，使用者會拿到一個**自己無法處理**的狀態。
    """
    if _is_batch_fail(row):
        return True
    _s = str((row or {}).get("狀態", "")) if isinstance(row, dict) else ""
    return "部分成功" in _s


def split_batch_status_counts(statuses) -> tuple[int, int, int]:
    """狀態欄 → `(完全成功, 部分成功, 失敗/無效)` 三態計數。

    ⭐ **具名而不 inline，全部的理由就是這一句**：`"部分成功"` 這個字串
    **字面上含有「成功」** —— 任何人回頭用最直覺的 `"成功" in s` 改寫，
    都會把「有 13~22 欄沒算出來」的檔靜靜混進全綠計數，
    而使用者永遠不會去看它的備註。抽成純函式才守得住。
    ⚠️ 三者相加**必等於**輸入長度（`tests/test_wf03_research_batch.py` 釘住）。
    """
    _ok = _partial = _fail = 0
    for _s in statuses:
        _t = str(_s or "")
        if "部分成功" in _t:
            _partial += 1
        elif "成功" in _t:
            _ok += 1
        else:
            _fail += 1
    return _ok, _partial, _fail


def _batch_estimate(todo_n: int) -> str:
    """剩餘檔數 → 預估時間字串。**給區間，不給單點。**

    ⚠️ 每檔秒數來自 :data:`_SEC_PER_FUND_FAST` / :data:`_SEC_PER_FUND_SLOW`
    （＝舊分頁的實測值，見那兩個常數）。給區間是因為 MoneyDJ 每檔要走多頁
    ＋ fallback chain，境外基金常態跑兩輪 page_type，**離散度本來就大**。
    """
    _n = max(int(todo_n or 0), 0)
    if _n <= 0:
        return "—"
    _lo = max(1, round(_n * _SEC_PER_FUND_FAST / 60))
    _hi = max(1, round(_n * _SEC_PER_FUND_SLOW / 60))
    return f"約 {_hi} 分鐘" if _hi <= _lo else f"約 {_lo}~{_hi} 分鐘"


def _run_batch(codes: list[str], *, retry_failed: bool) -> None:
    """逐檔跑（進度條）。已完成的跳過；`retry_failed` 時把可重試的檔一起重抓。

    ⭐ **它只會在送出閘門的正分支裡被呼叫**
    （線框 Tab 03 的 chip：「長時間運算，**必須在 Form 之後才啟動**」）。
    ⚠️ **刻意不寫「本頁唯一的長時間運算」** —— 那句話不成立：深度區的
    :func:`auto_fetch_moneydj` 同樣是一次外部往返，只是**單檔**。
    本函式真正特別的地方是它**隨代碼數線性放大**（N × 20~45 秒），
    所以「有沒有被 gate 住」在這裡的代價是幾小時，在深度區是幾秒。
    ⛔ 不得改成「頁面載入就跑」或「有代碼就跑」—— 那會讓每一次 rerun
    都重打一輪 MoneyDJ。

    ⚠️ **與舊分頁的四個已知差異，逐條寫明，不要讀成「一模一樣」**：

    1. ⛔ **沒有磁碟續存（checkpoint）。** 舊分頁每跑完一檔就寫
       `repositories/batch_checkpoint`，關分頁 / 重啟後可續跑。
       本頁**不寫任何磁碟、不寫任何 Google Sheet** —— 客戶 2026-09-06 永久授權
       「查詢/搜尋一律唯讀」，而且本頁一行都不 import `repositories`
       （`test_the_page_never_reaches_into_the_data_layer`）。
       → **結果只活在 session 裡**：同一個 session 內可以續跑（再按一次會跳過
       已完成的檔），**關掉分頁就沒了**。線框寫的「結果落地可續跑」，
       **落地那一半本頁沒有做到** —— 這是缺口，已在 PR 具名登記，不是靜默省略。
    2. **不傳 `name_hint`。** 舊分頁會去選股池查名字（`repositories.pool_repository`），
       線上抓不到真名的池成員因此顯示池名。本頁不能 import `repositories`，
       所以那種檔的「基金名」會留白 —— **留白是誠實的**（我們真的不知道它叫什麼）。
    3. **不傳 `oauth_client`。** 舊分頁會把登入者的 OAuth client 傳下去，
       讓沒有 service account 的環境也讀得到雲端 `nav_history` 補回歷史。
       本頁不碰 OAuth（那是 ⑤ 的職責），故退回 service account / 空。
    4. **`phase` / `score` 改由 session 讀**（見下方）—— 這一項與舊分頁**相同**，
       列在這裡只是為了讓四項並排看得完整。

    ⚠️ **每一檔跑完就立刻寫回 session**，不是整輪跑完才寫一次 ——
    中途出錯／使用者切走時，已經跑完的檔不會白費。
    """
    from ui.helpers.fund_grp_health.unified import build_batch_unified_row

    _rows = dict(_batch_rows())
    _todo = [_c for _c in codes
             if _c not in _rows or (retry_failed and _is_batch_retryable(_rows[_c]))]
    if not _todo:
        st.session_state[_SK_BATCH_ROWS] = _rows
        return

    # 景氣位階 —— 與舊分頁同一個 session 鍵。① 還沒載過總經資料時它是空的，
    # 那時「資產屬性 / 操作訊號 / 景氣適配」三欄會誠實留白（§1），**不猜一個位階**。
    _pi = st.session_state.get("phase_info") or {}
    _phase = str(_pi.get("phase") or "") if isinstance(_pi, dict) else ""
    _score = _pi.get("score") if isinstance(_pi, dict) else None

    _bar = st.progress(0.0)
    _live = st.empty()
    _total = len(_todo)
    for _i, _code in enumerate(_todo, start=1):
        _live.markdown(f"⏳ 處理中 **{_i}/{_total}**：`{_code}` …")
        # ⭐ `principal_twd` **顯式傳**，即使它等於函式的預設值 ——
        #    口徑是這一區最容易被悄悄改掉的東西，寫出來才看得見（見該常數）。
        _rows[_code] = build_batch_unified_row(
            _code, principal_twd=BATCH_PRINCIPAL_TWD, phase=_phase, score=_score)
        st.session_state[_SK_BATCH_ROWS] = _rows
        _bar.progress(_i / _total)
    _bar.empty()
    _live.markdown(f"✅ 本輪完成 **{_total}** 檔。")
    st.session_state[_SK_BATCH_RUN_AT] = tw_now_str()


def _batch_table_rows(codes: list[str], rows: dict) -> list[dict]:
    """把已完成的列投影成**大表的欄骨架**，依送出順序排列。

    ⭐ **客戶拍板②「照搬全部欄位、不挑子集」就落在這一行**：欄骨架是
    `BATCH_UNIFIED_COLUMNS`（＝ 舊分頁 `_build_df(columns=…)` 用的同一份 SSOT），
    **本函式一欄都不篩、一欄都不加**。
    ⛔ 想少放幾欄請先回去讀該拍板 —— 挑哪幾欄是**新的業務決定**，不是實作細節。

    ⚠️ **數值欄的轉型**：舊分頁走 `pd.to_numeric(errors="coerce")`。本頁不 import
    pandas（沒有必要 —— `build_batch_unified_row` 回的已經是 79 個鍵的 flat dict），
    改用 repo 既有的 `shared.converters.safe_num`。
    **兩者有一處差異，據實寫明**：`safe_num` 會額外 strip `%` 與 `,`，
    也就是 `"12.3%"` 在 pandas 下是空白、在這裡會變 `12.3`。
    方向是**多顯示一個真值**，不會產生假值（認不得的一律回 `None` → 留白）。
    """
    from ui.helpers.fund_grp_health.unified import (
        BATCH_NUMERIC_COLUMNS,
        BATCH_UNIFIED_COLUMNS,
    )
    _numeric = set(BATCH_NUMERIC_COLUMNS)
    _out: list[dict] = []
    for _c in codes:
        _row = rows.get(_c)
        if not isinstance(_row, dict):
            continue
        _out.append({
            _col: (safe_num(_row.get(_col)) if _col in _numeric else _row.get(_col))
            for _col in BATCH_UNIFIED_COLUMNS
        })
    return _out


def _batch_csv(rows: list[dict]) -> bytes:
    """把大表轉成可下載的 CSV bytes。**欄序與畫面上完全相同。**

    ⚠️ **`utf-8-sig` 不是隨手挑的**：少了那個 BOM，Excel 會把中文欄名讀成亂碼
    （舊 `ui/tab_batch_analysis.py` 的下載鈕用的也是它，同一個理由）。
    ⚠️ **不走 pandas 的 `to_csv`** —— 本頁不 import pandas（沒有必要），
    而 `csv` 是標準庫。⛔ 也**不要**改成 `to_csv`：那個名字落在零寫入守衛的
    磁碟 sink 清單裡，會讓一個**根本不碰磁碟**的動作看起來像在寫檔。
    ⚠️ `None` 由 `csv` 寫成空字串 ＝ **留白**，⛔ 不得填 0（§1）。
    """
    import csv
    import io
    _buf = io.StringIO()
    _cols = list(rows[0]) if rows else []
    _w = csv.DictWriter(_buf, fieldnames=_cols, extrasaction="ignore")
    _w.writeheader()
    for _r in rows:
        _w.writerow({_c: ("" if _r.get(_c) is None else _r.get(_c)) for _c in _cols})
    return _buf.getvalue().encode("utf-8-sig")


def _batch_column_config(cols: list[str]) -> dict:
    """大表的逐欄顯示設定（欄寬 ＋ **逐欄 tooltip**）。

    ⭐ **這不是新設計，是接既有的那一份** ——
    `ui.helpers.fund_grp_health.columns.unified_column_config(batch=True)`
    是健診大表與批次大表**共用**的 SSOT，舊分頁用的就是它。
    ⚠️ 它是**本批**對「79 欄橫向捲很久」唯一做了的緩解，而且**不動任何欄位**：
    欄名一律可以把滑鼠移上去看「怎麼算的、單位是什麼、留白代表什麼」。
    （**不宣稱它是唯一可能的手段** —— 凍結欄／分組欄也是，只是那屬版面決定，見下。）
    ⛔ **凍結欄 / 分組欄不在本批**：repo 內確實有一支
    `ui/components/column_group_tabs.py`，但它 **production 0 caller**、
    而且**要求呼叫端自己傳 `groups` 與 `pinned`** —— 也就是「哪幾欄算一組」
    得由我們發明，那是**版面決定**（§-1.5 v3 `03`-2 ①），已回報總管，不自決。
    """
    from ui.helpers.fund_grp_health.columns import unified_column_config
    _cfg = unified_column_config(batch=True)
    return {_k: _v for _k, _v in _cfg.items() if _k in set(cols)}


def _render_batch_form() -> None:
    """批次自己的送出閘門（貼上框 ＋ 重試勾選 ＋ 送出鈕）。

    ⚠️ **為什麼是第二個 form，而不是把欄位塞進頂端那一個** —— 三個理由：
      1. 頂端那一顆鈕的字是線框逐字指定的「**搜尋**」，它送出的語意是「查一檔」；
         批次送出的語意是「跑一批、可能要好幾小時」。**同一顆鈕做兩件事，
         使用者按下去之前不知道會發生什麼。**
      2. 線框給批次的 chip 是「**Form 後才跑**」——「Form」在那句話裡指的是
         「有一道送出閘門」，不是「必須是同一個 form」。
      3. 合成一個的話，每次查單檔都會順便重跑整批（或反之），
         那正是鐵則 02 要擋的重運算。
    ⚠️ 兩個 form 都走 `ui.helpers.ia.applied_form`，**本檔沒有任何 `st.form(` 站點**
    —— 自己寫會讓 `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==` 7）轉紅。

    ⛔ **沒有 `st.file_uploader`，那是客戶 2026-09-07 拍板①，不是漏做。**
    """
    with applied_form(_BATCH_FORM_KEY, submit_label=BATCH_SUBMIT_LABEL) as _gate:
        st.caption(BATCH_PRINCIPAL_NOTE.format(health=tab_label("health")))
        st.caption(
            f"逐檔**序列**跑（避免對來源造成過高請求速率），每檔約 "
            f"{_SEC_PER_FUND_FAST}~{_SEC_PER_FUND_SLOW} 秒 —— "
            f"送出後才開始，打字的當下不會觸發任何取數。"
            f"結果**只留在這個瀏覽器分頁裡**，關掉就沒了（本頁不寫任何檔案）。")
        _raw = st.text_area(
            _LABEL_BATCH_CODES, value="", height=140,
            placeholder=_CODE_PLACEHOLDER,
            help="每行一檔；逗號／分號／Tab 也可以當分隔，每行只讀第一欄，"
                 "所以直接從試算表貼「代碼,基金名」兩欄也可以。"
                 "重複的代碼會自動去掉，小寫會自動轉大寫。",
        )
        _retry = st.checkbox(
            _LABEL_BATCH_RETRY, value=False,
            help="不勾：只跑還沒跑過的檔（已完成的直接跳過，所以再按一次很快）。"
                 "勾了：連「抓取失敗 / 代號無效 / 部分成功」的檔一起重抓 —— "
                 "那幾種多半是暫時性的，重抓通常就會補齊。",
        )

    # ⚠️ `if _gate:` 必須在 `with` **之外**（送出鈕在 `yield` 之後才建立）。
    if _gate:
        _codes = _parse_codes(_raw)
        st.session_state[_SK_BATCH_CODES] = _codes
        if _codes:
            _run_batch(_codes, retry_failed=bool(_retry))


def _render_batch_results() -> None:
    """送出之後的三種處境，**一次只給一個下一步**。

    1. **還沒送出 / 貼上框是空的** → 空狀態三要素（:data:`_BATCH_EMPTY_TITLE`）。
    2. **送出了但一個代碼都認不出來** → **另一句**空狀態（:data:`_BATCH_UNPARSED_TITLE`）。
       ⚠️ 與第 1 種**刻意不共用一句**：一個是「還沒給」、一個是「給了但認不得」，
       下一步不同（去貼 vs 去改格式）。共用一句使用者無從判斷哪一個跟他有關 ——
       同一個道理在本檔的 :data:`_RESULTS_PENDING_NOTE` 那裡已經吃過一次虧。
    3. **有結果** → 三態摘要 ＋ 全部欄位的大表。

    ⚠️ **狀態 2 與狀態 1 分不出來的那一格**：送出了、解析到 0 個代碼 →
    `_SK_BATCH_CODES` 是 `[]`，與「送出前」的預設值長得一樣。
    本函式因此**看的是 session 鍵在不在**（`in st.session_state`），不是它的真假值。
    """
    _submitted = _SK_BATCH_CODES in st.session_state
    _codes = _applied_batch_codes()
    _rows = _batch_rows()

    if not _codes:
        if _submitted:
            empty_state(_BATCH_UNPARSED_TITLE, _BATCH_UNPARSED_MISSING,
                        where=_batch_where(),
                        footer="改成每行一個代碼再送出一次即可。")
        else:
            empty_state(_BATCH_EMPTY_TITLE, _BATCH_EMPTY_MISSING,
                        where=_batch_where(),
                        footer="送出後這裡會出現一張大表，每一檔一列。")
        return

    _table = _batch_table_rows(_codes, _rows)
    _done = len(_table)
    _todo_n = max(len(_codes) - _done, 0)
    _ok, _partial, _fail = split_batch_status_counts(
        str((_rows.get(_c) or {}).get("狀態", "")) for _c in _codes if _c in _rows)
    st.caption(
        f"解析到 **{len(_codes)}** 檔（已去重）　·　已完成 **{_done}**　·　"
        f"剩餘 **{_todo_n}**（{_batch_estimate(_todo_n)}）　·　"
        f"✅ 完全成功 {_ok}　·　⚠️ 部分成功 {_partial}　·　❌ 失敗 / 無效 {_fail}"
        + (f"　·　執行時間（台北）{st.session_state.get(_SK_BATCH_RUN_AT)}"
           if st.session_state.get(_SK_BATCH_RUN_AT) else ""))
    if _todo_n >= _LONG_RUN_FUNDS:
        st.caption(
            f"⚠️ 還有 **{_todo_n}** 檔沒跑，預估 **{_batch_estimate(_todo_n)}**。"
            "跑的過程中請不要關掉分頁；已完成的檔會即時留在這個分頁裡，"
            "中斷後再送出同一份清單會從沒跑過的那一檔接下去。")
    if _partial or _fail:
        st.caption(
            "失敗與部分成功的檔**完整留在表裡**（狀態 ＋ 備註寫明原因、數值欄留白），"
            "**不會偷偷丟掉、也不會填 0**。「部分成功」是淨值抓到了、但某一組欄位"
            "算到一半出錯而留白 —— **留白不代表這檔沒有那個特性**。"
            f"勾上「{_LABEL_BATCH_RETRY}」再送出一次通常就會補齊。")

    if not _table:
        # ⚠️ **早退是刻意的，不是為了少寫一行** —— `_batch_column_config()` 會
        #    lazy import 一條需要 `pandas` 的鏈（`services.fund_service`）。
        #    空表根本不需要那份設定，硬算等於在「代碼收到了、還沒跑完任何一檔」
        #    這個**必經**處境上多掛一條進口路徑；那條路徑一出事，
        #    使用者看到的是**紅框**，而他其實只是還沒開始跑（那是灰）。
        #    ⚠️ **這不是假想**：本組第一版就是先算 config 再判空，
        #    本機驅動器當場把那一格畫成紅框（`ModuleNotFoundError: pandas`）。
        wide_table([], empty_title=_BATCH_NOTHING_RUN_TITLE,
                   empty_missing=_BATCH_NOTHING_RUN_MISSING.format(
                       submit=BATCH_SUBMIT_LABEL),
                   empty_where=_batch_where())
        return
    # ⭐ 全部欄位、全寬。`wide_table` 走 `st.dataframe` —— 它自己就是一個
    #    `overflow-x` 的捲動容器；`height` 讓它成為**固定高度**的捲動區，
    #    不會把整頁撐長。**欄位一欄都沒有少**（客戶拍板②）。
    wide_table(
        _table,
        empty_title=_BATCH_NOTHING_RUN_TITLE,
        empty_missing=_BATCH_NOTHING_RUN_MISSING.format(submit=BATCH_SUBMIT_LABEL),
        empty_where=_batch_where(),
        column_config=_batch_column_config(list(_table[0])),
        height=460, hide_index=True,
    )
    st.caption(
        f"表格可以**左右捲動**（共 {len(_table[0])} 欄）；"
        "每一個欄名都可以把滑鼠移上去看說明 —— 怎麼算的、單位是什麼、"
        "留白代表什麼、能不能拿去跨檔比大小。")
    # ⬇️ CSV 下載 —— **草稿版面裡就有這一顆**，不是本組加的新元件
    #    （`docs/wireframes/draft-p03-batch-input.html` 的「提案版面（最小可用）」
    #    末行逐字：「⬇️ 下載 CSV」）。舊分頁同樣有一顆。
    # ⚠️ **它不寫任何檔案** —— `st.download_button` 收的是 bytes，由瀏覽器存檔；
    #    本頁到磁碟的距離仍然是 0（`tests/test_wf03_research_no_writes.py` 釘住）。
    st.download_button(
        "⬇️ 下載這張表（CSV）", _batch_csv(_table),
        file_name=f"fund_batch_{tw_now_str('%Y%m%d_%H%M')}.csv",
        mime="text/csv", use_container_width=True, key="v03_batch_download")


def _render_batch() -> None:
    """區塊 4｜批次分析（**大表全寬**）。

    線框逐字：「一次丟多個代碼跑同一組指標，結果落地可續跑。
    **長時間運算，必須在 Form 之後才啟動。**」

    ⚠️ ~~「線框沒有畫批次自己的輸入框……本批刻意不發明一個批次輸入框
    （那是線框沒有的新版面 ＝ 客戶 gate）。已登記，待下一批連同真內容一起請示。」~~
    → **2026-09-07 狀態更新（不是漏刪）：那次請示已經回來了。**
    客戶拍板「**只做貼上框，不做檔案上傳**」，所以輸入框現在有了、而且刻意只有一個。
    **舊表述當時的處置是對的** —— 它擋下了一個沒有被拍板的版面異動；
    **被推翻的只有它的前提**（那時還沒拍板，現在拍了）。

    ⚠️ **「結果落地可續跑」只做到一半，這是缺口不是取捨** ——
    `session` 內可續跑，**落地（磁碟 checkpoint）沒有做**，理由與代價見
    :func:`_run_batch` 的差異第 1 條。**已在 PR 具名登記。**
    """
    _render_batch_form()
    _render_batch_results()


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
