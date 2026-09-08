"""③ 標的探索新頁的骨架守衛 —— 線框 Tab 03 的四塊，一塊都不准少。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**骨架的形狀**：四個區塊都在、順序對、Form 真的 gate 住下游、
還沒搜尋時只畫空狀態、送出後八個單位**各自**誠實灰、深度區的五塊 ＋ 來源標註逐字。

⛔ **本檔不守內容對不對** —— 本批的內容**本來就還沒填**（客戶 2026-09-05：
   骨架先上線、CI 綠、再分批填）。下一批把真內容接上時，
   `test_every_grey_unit_is_grey_until_its_content_lands` 會**轉紅** ——
   **那是預期的**，屆時請把它改成「真內容放行」，**不要把它放寬**
   （① 與 ② 的同型守衛就是這樣從灰態放行轉成真內容放行的）。

⛔ **本檔不守「選定後展開」這個 gate** —— 骨架階段沒有東西可以被選定，
   那個 gate 在本批**還不存在**（理由見 `ui/views/page_03_research.py` 的模組 docstring）。
   下一批接上結果卡時，
   `test_all_blocks_are_present_and_in_wireframe_order` 會因為深度區不再無條件渲染而轉紅
   —— **正解是把它改成 gate 驗證，不是把斷言放寬。**

⛔ **本檔不驗瀏覽器裡的真實版面**：欄寬、窄螢幕折行、`st.form` 送出後真正的
   rerun 次數 —— 那些是 Streamlit 的執行期行為，靜態規則與 recorder 都看不到。

⛔ **本檔不重複既有的全域規則**（`ui/**` 全掃的那幾條會自動涵蓋這個新檔）：
   `tests/test_ui_grid_contract.py`（欄數）、`tests/test_ui_rerun_contract.py`（form 站點）、
   `tests/test_batch2_top_card_grid.py`（`where=` 必填、灰卡要有 remedy）、
   `tests/test_wpf_five_tab_wiring.py`（分頁名不得手抄）。
   **在這裡再抄一份等於製造第二把尺**（`CLAUDE.md §2.1`）。

本檔**已知打不到的地方**（照實寫，不要用形容詞蓋過去）
------------------------------------------------------
這三條是 ② `tests/test_wf02_health_skeleton.py` 被獨立紅隊打穿的三個維度。
本檔**只解掉其中一條半**，其餘照實登記 —— 讀本檔的人請據此打折信任它。

- **繞道維（本檔已解）**：② 的 `_segments()` 回傳 dict，**同名單位後者覆蓋前者**，
  於是「掏空真區塊 ＋ 另造一個同名誘餌帶灰態」可以全綠。
  本檔補了 :func:`test_unit_names_are_unique`，同名誘餌**當場轉紅**（突變 M11 實測）。
- **繞道維（本檔只解掉「字面」那一半，2026-09-05 紅隊更正）**：② 的「手刻
  `st.markdown("⬜ …")` 不走 `not_ready()` 也照樣被認成灰態」——
  :func:`test_the_page_never_hand_rolls_the_grey_mark` 只擋得住**字面** `⬜`。
  ⛔ **兩種寫法照樣全綠**：(a) 從 SSOT `from ui.helpers.render_state import
  NOT_READY_MARK` 再自己拼成一句 caption；(b) `chr(0x2B1C)`。
  ⚠️ **(a) 特別值得記著：那正是本檔自己在教的寫法**（本檔頂部就寫著
  「從那個模組 import，不在這裡抄一份字面值」）——
  **一個照著檔案自己的教誨寫的人，會剛好落在守衛的盲區裡。**
  （總管 2026-09-05 排程裁決：登記，本批不修。）
- ⛔ **語意維（本檔**沒有**解，而且比本檔原本自陳的更寬）**：所有灰態斷言驗的是
  **符號**（⬜）與**常數**（`_PENDING_NOTE`），**不驗那句話的意思**。
  紅隊實測全綠的三種：句尾接「目前一切正常，無異常」／八個單位的灰態理由**互換**／
  **在灰態裡塞一句投資承諾「目前查無風險，此檔可安心買進。」**
  ⚠️ 第三種是本檔原本沒有想到的等級 —— **一句會讓人賠錢的話，本檔一條都不會響。**
- ⛔ **情境維（本檔只覆蓋到一半）**：頁面只被渲染過 **兩種** session 形狀
  （`None` 與一份 `{"term","source"}`）。`_applied_query()` 對**非 dict 髒值**
  （字串／list／舊版 payload）的行為**沒有任何斷言**。
  `_normalise_query()` 本身有直接測（:func:`test_a_blank_search_never_counts_as_applied`），
  但它與 `_render_search_form()` 之間的接線**只由 AST 驗形狀，沒有跑過**。
- ⛔ **指路挑錯 key 沒有守衛**：`_pending_where()` 若把 `where_to_find('research')`
  換成任何一個**別的合法 key**，:func:`test_every_grey_says_where_to_look` 才會紅；
  但職責宣告那一句裡的 `health` / `portfolio` 兩個 key **換成別的合法 key 不會有任何東西轉紅**。
  **這是「走 SSOT」擋不到的那一類**：SSOT 保證名字不過期，**不保證你挑對了 key**。
- ⛔ **其餘已登記、本批不修**（總管 2026-09-05 排程裁決）：
  示意值黑名單只有 10 個字面寫法；**指路挑錯 key 沒有任何守衛**；
  `_applied_query()` 對非 dict 髒值零斷言；`BLOCK_RESULTS` 可以被改成空字串；
  `getattr(st, "columns")(2)` 與 `from streamlit import columns as _c` 繞得過
  :func:`test_the_page_draws_no_grid_or_form_of_its_own`
  —— **但全域 `tests/test_ui_grid_contract.py` 對 alias 同樣失明，
  那是 repo 既有性質，不是本頁造成的。**

⚠️ 兩個**全域守衛的實測盲點**（本檔的突變順便量到的，登記給後人，不是本檔的功勞）
------------------------------------------------------------------------------
下面兩項不是本檔的缺口 —— 是「本頁**只靠全域守衛**會漏掉什麼」。
兩項都是**本批實跑**（各跑 5 個測試檔、503 passed 的那一輪）：

- **突變 M15：把指路的分頁名手抄成去掉 emoji 的「標的探索」** →
  `tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`
  **沒有轉紅**，只有本檔的 `test_every_grey_says_where_to_look` 抓到。
  原因是那條守衛的黑名單**只對 `RETIRED_TAB_LABELS` / `MISWRITTEN_TAB_NAMES` 展開
  「去 emoji 變體」**，**現行**分頁名只比對含 emoji 的完整標籤
  （該守衛自己的 docstring 就寫著這個取捨）。
  → **手抄一個現行分頁名、順手把 emoji 丟掉，全域網子接不住。**
- **突變 M09：本頁自己寫 `st.columns(3)`** →
  `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL` **沒有轉紅**
  （它抓的是「**欄數不是 3**」的呼叫，3 欄是合規的），只有本檔的
  `test_the_page_draws_no_grid_or_form_of_its_own` 抓到。
  → 那個精確 `==` 的計數器**不會**因為本頁多寫一個合規 3 欄而動，
  也就是說「本頁不得自己開網格」這條**只有本檔在守**。

錄製法：為什麼不用 AppTest
--------------------------
~~本頁尚未接進 `app.py`（客戶明令舊三頁不動、不接線），AppTest 走不到它。~~
⚠️ **2026-09-07 更正：這個理由已經不成立**（**有意識的更正，不是漏刪** ·
決策者：**客戶 2026-09-07「雙軌並行」**）。本頁已掛成第 ⑧ 格 `[新] 標的探索`，
`tests/test_app_apptest.py` 的 AppTest **走得到它了**。
**舊表述在寫下的當天是對的**（那時 `app.py` 真的沒有掛它）；**被推翻的是它的前提**。
**但錄製法不因此換掉，理由換了一個、而且更強**：
(a) AppTest 是 **slow lane**、且該 lane 是 `continue-on-error: true`
    —— 它紅了**不會擋 merge**，本檔這些逐格斷言不能建在一條不擋門的 lane 上；
(b) AppTest 只跑**一種** session 形狀，而本檔要對**同一頁的多種 session 形狀**
    各錄一次呼叫序列，那是 AppTest fixture 做不到的。
⚠️ ~~反過來也要講清楚：**AppTest 現在補上了本檔結構上做不到的那一半** ——~~
~~「這一頁在真的 Streamlit runtime 裡畫得出來、而且不會與舊 ③ 撞 widget key」。~~
~~**兩者互補，不是誰取代誰。**~~
⛔ **2026-09-07 更正：上面那三行是假的**（**有意識的更正，不是漏刪** ·
決策者：**AI 總管**，依獨立稽核對本 PR 的實測）。**這是同一句話在本 PR 內的第三處** ——
`tests/test_wf03_research_wiring.py` 已經逐字寫著「那句話是假的，已刪」，PR 描述也自陳
「同一句話寫在兩個檔，只改了被抓到的那一處」，**而這一處還在**。
**一句被判定為假的話沒有被同步撤掉，比它從來沒有被抓到更危險** ——
它旁邊那句「已經改掉了」會讓下一個人以為整批都改完了。

**AppTest（`tests/test_app_apptest.py`）驗得到的是**：`app.py` 在真的 Streamlit
runtime 裡跑得完、**沒有未捕捉例外逸出到 script 層**（`assert not at.exception`），
以及該檔各條自己點名的**內容存在性**（某顆按鈕在、某段 caption 在）。

**它驗不到「畫面上出現了一行紅字」，而撞 key 正好落在那裡**（三步，逐步可自驗）：
  1. `app.py` 每一格分頁的 body 都是 `try: render_*() / except Exception:` →
     `ui.helpers.session.friendly_error(..., level="error")`；
  2. `friendly_error` 在 `level="error"` 時執行的是 **`st.error(body)`**，
     **不 re-raise**（該函式一路走到結尾回 `None`）；
  3. 於是 `StreamlitDuplicateElementId` / `StreamlitDuplicateElementKey`
     這類**在分頁 body 內**拋出的例外會被第 1 步接住、被第 2 步畫成紅框，
     **`at.exception` 仍然是空的** → `assert not at.exception` **照樣綠**。

**⑧ 這一格也不例外**：它的 body 同樣是 `try/except Exception → friendly_error(level="error")`
（`app.py` 的 `with tab_preview_research:`）。

**而「跑完不得有紅字」這一層，本 repo 目前沒有任何守衛**（本組實測，指令附下）：
**碰到 AppTest `.error` 元素集合的可執行程式碼只在 `tests/test_app_apptest.py`，共 2 處，
而且兩處都不是在斷言它是空的** —— 一處是把 `app.error` 的文字**當成內容來源**去搜
「計算方式」，另一處只擋一個很窄的類別（同一則訊息裡**同時**出現某把金鑰名與
「還沒設定」語彙時，不得用紅／橘字）；撞 key 的訊息**不含**那些字，兩處都不會響。
**沒有任何一條斷言說「跑完不得有紅字」。**

**驗證指令**（repo 根目錄，2026-09-07 實跑；本行即從它在本檔的最終位置照抄後重跑）::

    git grep -nE "(at|app|_at)[.]error" -- 'tests/*.py'
    git grep -nE "assert +not +[A-Za-z_]+[.](error|warning)" -- 'tests/*.py'

第二條 **0 行**（exit 1）。第一條的命中裡，**可執行程式碼只有
`tests/test_app_apptest.py` 那 2 行**，其餘是**本段自己的散文**（本輪 2 行）——
⚠️ **命中必須人工逐一判讀是程式碼還是散文**，這正是為什麼上面寫的是
「**可執行程式碼**只在 `tests/test_app_apptest.py`」，而不是「全 repo 只有 2 處」。
（本段刻意不寫命中總數：**它會隨這段散文被編輯而漂移**，寫死就是下一個假數字。）
⚠️ 兩條刻意**不帶詞界符**：本檔的模組 docstring 不是 raw string，
反斜線在原始碼裡會長成兩個、複製出去就跑錯 —— 改用 `[.]` 表達字面點。
代價是**多抓**（`app.errors` 之類也會中），而多抓正是這裡要的。

⚠️ **本段刻意不寫「現在守住了」**：撞 key 的**執行層**守衛不在本分支上 ——
`tests/test_dual_track_widget_key_collision.py` 在 `origin/main` 與本分支**都不存在**
（本組 `git cat-file -e` 實測），它是另一顆 PR（#819）的東西。
**本分支上擋撞 key 的只有靜態守衛**：本檔的骨架斷言與
`tests/test_wf03_research_wiring.py` 的三層 key 規則 —— 而那一檔自己就寫明
它是純靜態的、看不到動態組出來的 key / label。
⛔ **因此不得引用「AppTest 會抓到」為理由去拆掉任何一條靜態 key 守衛。**
**那句話正是本更正撤掉的那一句。**

**舊表述的用意仍然成立**（AppTest 與本檔確實各看一半、確實互補，這個方向沒有被推翻）；
**被權衡掉的是它的事實面** —— 它把「AppTest 走得到這一頁」講成了
「AppTest 因此保證這一頁不會撞 key」。**走得到 ≠ 看得見。**

⚠️ **本組未查證的部分，據實列出**（`CLAUDE.md §-2` 規則 6）：
本環境**沒有 streamlit / pytest**（`ModuleNotFoundError`，本組實測），
上述第 1~3 步是**讀原始碼導出的**，**不是本組跑出來的**。
另有一則**他組在 CI 上的實測**（本組轉述、未複驗）：`[新] ⑦` 打開時出現一個
`StreamlitDuplicateElementId` 紅框，而既有測試全綠 —— 與上述導出結果同向。
「可執行程式碼只有那 2 處」是**取決於有沒有漏看**的宣稱，出自上列兩條字面 grep，
**掃不到**：別名寫法（`from streamlit.testing... import AppTest as X` 之後的 `X`）、
把元素集合先存進中間變數再斷言、以及任何非 `.error` / `.warning` 的紅字管道。

📌 **本輪把這把尺對全 repo 重跑過一次（2026-09-07）—— 不是只修這一處**
--------------------------------------------------------------------
起因：**同一句話寫在兩個檔，上一輪只改了被抓到的那一處**（`CLAUDE.md §8.2.A.1`
驗證段 ④ 記載的失效模式：「條件只往外用、不往內用」）。故本輪先掃再改。

**掃到並修掉的（分類敘述，刻意不寫「只有 N 處」）**：
- **「AppTest 保證不會撞 key」族** —— 本檔上方那三行（第三處），已撤。
- **「這一塊全站只有一份」族** —— 兩處，**兩處都是假的、且都在 merge-base 上就已經假了**：
  `app.py` 的「→ 全站只剩它那一份」與 `tests/test_wf03_research_wiring.py` 的
  「所以全站現在剛好一份」。實測 ⑤ 與 ⑦ **各畫一份**（AST 追呼叫鏈，兩條都不在 `if` 底下）。
- **分頁數過期計數族** —— `app.py` 與 `tests/test_wpf_five_tab_wiring.py` 內描述**現況**的
  「五個分頁 / 兩格預覽 / 7 格」等。**描述過去的（「七→五接線」「原本五段」）刻意不動**，
  它們在寫下的當天為真，改了反而變成新的假話。

**掃到但**不**修、登記回報的**：
- `tests/_ast_bindings.py` 的「（靜態規則）認得出是閘門、認不出語意，**要靠 AppTest
  行為測試（③④ 各有兩條）去驗**」—— **形狀與本檔剛撤掉的那句相同**（把一層外包給
  一個看不見它的測試）。**已實測的部分**：③ 的那一檔
  `tests/test_wf03_research_batch.py` **一個 `AppTest` 都沒有**（`grep` 0 命中），
  它的行為測試走的是**替換 `st` 的假 recorder**。**未實測**：④ 那兩條是哪兩條、
  以及「各有兩條」這個數字。⛔ **因此本輪不動它** —— 一個只驗了一半就下筆的「更正」，
  正是本輪在修的那個病。

**這次掃描看不到的形態（誠實揭露，不是免責）**：
用的是**中文關鍵詞字面 grep**（`撞 key` / `全站只剩` / `唯一一份` / `執行層` /
`真憑據` / `畫得出來` / `AppTest` 等）。**結構上掃不到**：換句話說而不含這些詞的、
用英文寫的、跨行被拆開的、以及**寫在 `.md` 以外任何非文字載體裡**的同類宣稱。
⛔ **不得**把「本輪掃過了」讀成「全 repo 已經沒有同類假話」。
⚠️ **禁區未動**：`ui/views/page_05_settings.py` / `docs/**` / `CLAUDE.md` 等本輪
無權改動的檔案**只讀不改**；其中命中的兩處（`st.expander(expanded=False)` 收合仍執行
的自證）**本組判定為成立** —— 它拿 AppTest 當**存在性**證據（那條測試若沒渲染到就會紅），
與本檔撤掉的那句（拿 AppTest 當**不存在性**證據）**方向相反**，不是同一族。
故以**替換 `st` 的渲染 API**錄下呼叫序列 —— 與
`tests/test_wf01_detail_zone_order.py` / `tests/test_wf02_health_skeleton.py`
同一套做法，那裡已經被多輪獨立稽核打過。
"""
from __future__ import annotations

import ast
import pathlib
import sys
import re
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_03_research.py"

#: 灰態的視覺記號（`ui/helpers/render_state.py::NOT_READY_MARK`）。
#: ⚠️ **從那個模組 import，不在這裡抄一份字面值** —— 抄了就是第二份真相源。
#: form 閘門守衛共用的 AST 偵測（`tests/_ast_bindings.py`）——
#: ⚠️ 這裡**不要**再抄一份掃描邏輯：②③④ 三頁曾各自抄一份較弱的版本，
#:    三份同時漏掉屬性賦值／`update()`／widget `key=` 三條管道（`CLAUDE.md §2.1`）。
#: ⚠️ `sys.path` 那一行不是多餘的：pytest 預設會把 `tests/` 放進 `sys.path`，
#:    但那是預設值的副作用，換 `--import-mode=importlib` 就沒了。
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ast_bindings import (gate_guarded_ids, gate_ifs,  # noqa: E402
                           guarded_key_names, session_writes)

from ui.helpers.ia import STATE_NOT_READY  # noqa: E402
from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import where_to_find  # noqa: E402
from ui.views.page_03_research import (  # noqa: E402
    _LABEL_SOURCE,
    _LABEL_TERM,
    CCY_UNKNOWN,
    SYNTHETIC_TRACE_SOURCES,
    TRACE_NAV_SERIES,
    DIVIDEND_COLS,
    HOLDING_COLS,
    NO_REASON,
    PERF_PERIODS,
    RISK_METRICS,
    TRACE_COLS,
    TRACE_FAIL,
    TRACE_OK,
    TRACE_UNKNOWN,
    BLOCK_BATCH,
    BLOCK_DEEP,
    BLOCK_FORM,
    BLOCK_RESULTS,
    DEEP_DIVE_CARDS,
    DEEP_DIVE_PROVENANCE,
    DEEP_DIVE_TABLES,
    SOURCE_OPTIONS,
    SUBMIT_LABEL,
    DIRECT_LABEL,
    MAX_RESULT_CARDS,
    SELECT_LABEL,
    _BATCH_EMPTY_MISSING,
    _BATCH_UNPARSED_MISSING,
    _NAMELESS_TITLE,
    _NOT_SELECTED_MISSING,
    _NOT_SELECTED_TITLE,
    _RESULTS_EMPTY_MISSING,
    _RESULTS_EMPTY_TITLE,
    _RESULTS_NO_PERF_NOTE,
    _declared_currency,
    _dividend_rows,
    _holdings_rows,
    _nav_facts,
    _normalise_query,
    _pending_where,
    _failed_source_count,
    _fmt,
    _perf_lines,
    _pick_token,
    _result_card,
    _result_note,
    _result_value,
    _results_caption,
    _risk_lines,
    _row_str,
    _selected_code,
    _trace_rows,
    render_fund_research,
)
# ⚠️ L2 的鍵名 SSOT —— **不在本檔抄一份中文字面值**（抄了就是第二份真相源，§2.1）。
from services.fund_search import (  # noqa: E402
    EMPTY_MEANS_UNKNOWN,
    KEY_AGENT,
    KEY_CODE,
    KEY_NAME,
    KEY_NAV,
    KEY_NAV_DATE,
    KEY_SOURCE,
)

#: `_render(result=…)` 的「沒有傳」哨兵 —— 不能用 `None`，`None` 是合法的假回傳。
_SENTINEL: Any = object()

# ══════════════════════════════════════════════════════════════════
# 假的 L2 回傳（**唯一的資料入口**，本檔所有深度區斷言都吃它）
#
# ⚠️ **每一個數字都是獨一無二的哨兵**，這是刻意的：
#    「某一格印出了別格的數字」與「某一格印出了 0」都是本檔要抓的失效模式，
#    而它們在**共用同一個數值**的 fixture 底下**完全看不出來**。
# ⚠️ **哨兵值必須避開 `_PINNED_FAKE_VALUES`**（它含裸子字串 `"0.81"` / `"0.22"`）——
#    撞到的話會讓另一條守衛誤紅，而且那個紅燈指的方向是錯的。
# ══════════════════════════════════════════════════════════════════

#: 風險指標的哨兵：`metrics 鍵 -> 值`。刻意**每個都不同、且不含 0.81 / 0.22**。
RISK_SENTINELS: dict = {
    "sharpe": 71.11, "sortino": 72.22, "calmar": 73.33,
    "max_drawdown": -74.44, "std_1y": 75.55,
}
#: 績效的哨兵：`perf 鍵 -> 值`。
PERF_SENTINELS: dict = {
    "1M": 61.11, "3M": 62.22, "6M": 63.33,
    "1Y": 64.44, "3Y": 65.55, "5Y": 66.66,
}


class _FakeSeries:
    """夠用的假 `pd.Series` —— 只實作被測檔真的會碰的那幾個介面。

    ⚠️ **刻意不 import pandas**：本檔要驗的是「UI 怎麼讀資料」，
    不是 pandas 的行為；真的 Series 進來會讓失敗訊息指向 pandas 而不是被測檔。
    """

    def __init__(self, values: list, dates: list, attrs: dict | None = None) -> None:
        self._v, self._d = values, dates
        self.attrs = dict(attrs or {})
        self.index = _FakeIndex(dates)
        self.iloc = _FakeILoc(values)

    def __len__(self) -> int:
        return len(self._v)


class _FakeIndex:
    def __init__(self, dates: list) -> None:
        self._d = dates

    def min(self):
        return min(self._d)

    def max(self):
        return max(self._d)


class _ExplodingIndex:
    """索引**有** `min` / `max`，但一碰就拋 —— 模擬「上游契約破了」。

    ⚠️ **刻意讓方法存在**：獨立稽核有一顆突變因為「`BadIndex` 有 `min` 只是會拋」
    而**其實沒生效**，稽核組自己把它撤回了、不列為證據。
    本類別把那個教訓做成 fixture：要驗「壞索引會不會被吞成灰態」，
    就必須讓它**真的走到 `.min()` 才炸**，不能靠 `hasattr` 早退。
    """

    def min(self):
        raise TypeError("哨兵：索引不是時間軸（上游契約被破壞）")

    def max(self):
        raise TypeError("哨兵：索引不是時間軸（上游契約被破壞）")


def _broken_series(n: int = 3):
    """長度正常、`iloc` 正常，**只有索引會炸**的假序列。"""
    _s = _FakeSeries([1.0] * n, ["2024-01-0%d" % (i + 1) for i in range(n)])
    _s.index = _ExplodingIndex()
    return _s


class _FakeILoc:
    def __init__(self, values: list) -> None:
        self._v = values

    def __getitem__(self, i):
        return self._v[i]


def _BLANK_RESULT() -> dict:
    """**全敗**的回傳：淨值一筆都沒有，只有逐源軌跡。

    形狀照 `repositories/fund/fund_orchestration.py` 與
    `services/fund_service.py::finalize_fund_metrics` 實際會 append 的鍵
    （`{source, success, error}` / `{source, success, nav_count}`）——
    **不是憑印象編的**，見被測檔模組 docstring 的實測段。
    """
    return {
        "status": "failed",
        "fund_code": "ZZTEST",
        "series": None, "perf": {}, "metrics": {}, "holdings": {}, "dividends": [],
        "currency": "",
        "source_trace": [
            {"source": "bank_platform", "success": False, "error": "所有平台均無回應"},
            {"source": "morningstar", "success": False, "error": "查無資料"},
            {"source": "nav_series", "success": False, "error": "無淨值序列"},
        ],
    }


def _RICH_RESULT(**over: Any) -> dict:
    """**六格都有料**的回傳。`over` 用來逐格挖掉東西做突變。"""
    _res: dict = {
        "status": "complete",
        "fund_name": "測試用基金甲",
        "fund_code": "ZZTEST",
        "currency": "USD",
        "nav_span_days": 909,
        "_moneydj_fetched_at": "2026-09-06 07:07:07",
        "series": _FakeSeries(
            [50.01, 50.02, 59.99], ["2024-01-02", "2024-06-03", "2026-09-05"],
            attrs={"source": "FundClear:GetFundNAV",
                   "fetched_at": "2026-09-06T07:00:00+00:00"}),
        "perf": dict(PERF_SENTINELS),
        "perf_source": "wb01",
        "metrics": {
            **RISK_SENTINELS,
            "std_source": "wb07",
            "risk_metric_meta": {
                "sharpe": {"source": "wb07", "self_calc_reason": None},
                "sortino": {"source": "self_calc", "reason": None},
                "calmar": {"source": "self_calc", "reason": None},
                "max_drawdown": {"source": "self_calc", "reason": None},
            },
        },
        "holdings": {
            "data_date": "2026/07",
            "source": "MoneyDJ:yp:yp013001",
            "fetched_at": "2026-09-06T07:00:01+00:00",
            "top_holdings": [
                {"name": "哨兵持股甲", "sector": "科技", "pct": 91.11},
                {"name": "哨兵持股乙", "sector": "金融", "pct": 92.22},
            ],
        },
        "dividends": [
            {"date": "2026/08/15", "ex_date": "2026/08/16", "pay_date": "2026/08/20",
             "amount": 81.11, "yield_pct": 83.33, "currency": "USD"},
            {"date": "2026/07/15", "ex_date": "2026/07/16", "pay_date": "2026/07/20",
             "amount": 82.22, "yield_pct": 84.44, "currency": "USD"},
        ],
        "source_trace": [
            {"source": "fundclear", "success": True, "nav_count": 3},
            {"source": "calc_metrics", "success": True},
        ],
    }
    _res.update(over)
    return _res


# ══════════════════════════════════════════════════════════════════
# 假的 L2 搜尋回傳（2026-09-08 加，搜尋結果接上真取數時）
#
# ⚠️ **每一個字串都是獨一無二的哨兵**，理由與上面那組數字哨兵一樣：
#    「某一張卡印出了別一列的欄位」在共用值的 fixture 底下完全看不出來。
# ⚠️ **NAV 哨兵刻意避開 `_PINNED_FAKE_VALUES` 的裸子字串**（它含 `"0.81"` / `"0.22"`）
#    —— 一個長得像 `10.81` 的真實淨值會讓那條守衛誤紅，而且紅的方向是錯的。
# ⚠️ **第二列刻意殘缺**（沒有淨值、沒有日期、沒有總代理）：那是 L1 真的會吐的形狀
#    （TDCC-3-2 分支把 `淨值`/`日期` 填成空字串等 3-4 補，補不到就留空），
#    也是本頁「上游沒給就整段不畫」那條規則唯一驗得到的地方。
# ══════════════════════════════════════════════════════════════════

#: 完整的一列（六個鍵都有值）。
FAKE_ROW_FULL: dict = {
    KEY_NAME: "哨兵候選甲基金", KEY_CODE: "SENTINELFUNDA",
    KEY_AGENT: "哨兵總代理甲", KEY_NAV: "51.53",
    KEY_NAV_DATE: "2026/09/05", KEY_SOURCE: "TDCC-3-2",
}
#: 殘缺的一列（只有名稱、代碼、來源）。
FAKE_ROW_SPARSE: dict = {
    KEY_NAME: "哨兵候選乙基金", KEY_CODE: "SENTINELFUNDB",
    KEY_AGENT: "", KEY_NAV: "", KEY_NAV_DATE: "", KEY_SOURCE: "FundClear",
}


def _FAKE_ROWS() -> list[dict]:
    """`search_funds()` 的預設假回傳 —— 每次呼叫回**新的** list，避免測試之間互相污染。"""
    return [dict(FAKE_ROW_FULL), dict(FAKE_ROW_SPARSE)]


#: 「使用者已經選定的那一檔」。**刻意不等於 `FAKE_QUERY["term"]`** ——
#: 兩者一樣的話，「深度區吃的是選定值還是查詢字串」這件事在畫面上分不出來。
SELECTED_CODE: str = "SENTINELPICKED"

#: 會產生「使用者看得到的字」的 st API。錄下來當作單位有沒有真的畫東西的證據。
_TEXT_APIS = (
    "markdown", "write", "caption", "text", "info", "warning", "error",
    "success", "metric", "dataframe", "table", "code", "header", "subheader",
    "title", "slider", "number_input", "checkbox", "text_input", "selectbox",
    "form_submit_button",
    # ⚠️ 2026-09-07 批次接上真取數時補：批次的貼上框走 `st.text_area`。
    #    **少了它不是「少錄一行」，是整條路徑會炸** —— `__getattr__` 的預設分支
    #    回傳的是假容器，`_parse_codes()` 拿到它之後 `for line in …` 會 TypeError。
    "text_area",
    # ⚠️ 同輪補：批次的 CSV 下載鈕。**少了它是「靜靜漏錄」而不是炸** ——
    #    比對「有沒有畫出下載鈕」的斷言會恆為 False，看起來像產品碼少畫了一顆。
    "download_button",
    # ⚠️ 2026-09-08 搜尋結果接上真取數時補：結果卡的「查這一檔」與深度區的
    #    「直接用我輸入的內容查」都是 `st.button`。**在此之前這一頁一個
    #    `st.button` 都沒有**（實測），所以補它不會改到任何既有錄音行。
    #    ⛔ 少了它，「選定後展開」那個 gate 的**入口**整個錄不到 ——
    #    斷言只看得到 gate 關著，看不到有沒有人打得開它。
    "button",
)


class _Rec:
    """把 `st.<api>(...)` 錄成一串字，其餘屬性一律回傳可呼叫 / 可進 `with` 的假物件。"""

    def __init__(self, submitted: bool = False,
                 widgets: dict[str, Any] | None = None,
                 clicked: set[str] | None = None) -> None:
        self.parts: list[str] = []
        self.session_state: dict[str, Any] = {}
        #: `{widget 的 label: 要回傳的值}`。**沒指定的 widget 行為完全不變**
        #: （`text_input` 回 `value=`、`checkbox` 回 `value=`），
        #: 所以既有的每一條斷言都看到與從前一模一樣的畫面。
        self.widgets: dict[str, Any] = dict(widgets or {})
        #: 送出鈕的回傳值。**預設 `False`（＝純渲染）**，這是絕大多數斷言要的處境。
        #: ⚠️ 2026-09-07 批次上線時補：在此之前**沒有任何測試走得到送出後的路徑**，
        #:    也就是「按下去會發生什麼」整條是**沒有被驗過的**。
        self.submitted = bool(submitted)
        #: **被按下的 `st.button` 的 `key` 集合**（2026-09-08 加）。
        #: `None` ＝ 沒有指定 ⇒ `st.button` 一律回 :attr:`submitted`（＝舊行為）。
        #: ⚠️ **為什麼要按 key 而不是跟著 `submitted` 走**：搜尋結果一次會畫最多
        #:    :data:`ui.views.page_03_research.MAX_RESULT_CARDS` 顆「查這一檔」，
        #:    `submitted=True` 會讓**九顆同時回 True** —— 那不是任何使用者做得到的事，
        #:    而且「哪一顆被按 → 選定哪一檔」正是本輪要驗的東西，混在一起就驗不了。
        self.clicked: set[str] | None = (
            None if clicked is None else set(clicked))

    # ── context manager（`with st.container():` 之類）────────────────
    def __enter__(self) -> "_Rec":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def _child(self) -> "_Rec._Child":
        return _Rec._Child(self)

    def __getattr__(self, name: str):
        def _fn(*args: Any, **kwargs: Any):
            if name in _TEXT_APIS:
                _bits = [str(a) for a in args if isinstance(a, (str, int, float))]
                # widget 的 label 是第一個位置引數；`metric` 的值是第二個。
                _line = f"[{name}] " + " ".join(_bits)
                # ⚠️ **只有 `button` 把 `key=` 一起錄**（2026-09-08）：
                #    這一頁的 `st.button` 都是**動態組 key**（每一列一顆），
                #    而 `tests/test_wf03_research_wiring.py` 的靜態掃描
                #    **只認字面值 key**、結構上看不到它們（那一檔的
                #    「看不到的形態」段自己就寫著）。錄下來，本檔才驗得到
                #    「⑧ 的每一顆按鈕都在 `v03_` 命名空間裡」。
                #    ⛔ 刻意**不**對 `download_button` / `form_submit_button` 這樣做 ——
                #    它們是既有錄音行，改格式會動到別條斷言看到的字。
                if name == "button" and kwargs.get("key") is not None:
                    _line += f" key={kwargs['key']}"
                self.parts.append(_line)
            if name in ("text_input", "text_area"):
                _label = args[0] if args else kwargs.get("label")
                if _label in self.widgets:
                    return self.widgets[_label]
                return kwargs.get("value", "")
            if name == "selectbox":
                _opts = kwargs.get("options") or (args[1] if len(args) > 1 else ())
                _opts = list(_opts or [])
                return _opts[kwargs.get("index", 0) or 0] if _opts else ""
            if name in ("slider", "number_input"):
                return kwargs.get("value", args[2] if len(args) > 2 else 0)
            if name in ("checkbox", "toggle"):
                _label = args[0] if args else kwargs.get("label")
                if _label in self.widgets:
                    return bool(self.widgets[_label])
                return bool(kwargs.get("value", False))
            if name == "button":
                # `clicked=` 沒指定 → 完全照舊（回 `submitted`）。
                if self.clicked is None:
                    return self.submitted
                return kwargs.get("key") in self.clicked
            if name == "form_submit_button":
                return self.submitted
            # 下載鈕：**恆回 `False`（＝沒人按）**，與其他按鈕同一個立場。
            if name == "download_button":
                return False
            if name == "columns":
                _spec = args[0] if args else 1
                _n = _spec if isinstance(_spec, int) else len(list(_spec))
                return [self._child() for _ in range(max(int(_n), 1))]
            return self._child()
        return _fn

    class _Child:
        """`st.columns()` / `st.form()` 回傳的容器：寫回同一份紀錄。"""

        def __init__(self, root: "_Rec") -> None:
            self._root = root

        def __enter__(self):
            return self

        def __exit__(self, *_exc: Any) -> bool:
            return False

        def __getattr__(self, name: str):
            return getattr(self._root, name)


def _render(applied: dict | None = None, result: Any = _SENTINEL,
            raiser: BaseException | None = None, *,
            session: dict[str, Any] | None = None,
            submitted: bool = False,
            widget: dict[str, Any] | None = None,
            patch: dict[str, Any] | None = None,
            selected: str | None = None,
            search: Any = _SENTINEL,
            search_raiser: BaseException | None = None,
            clicked: set[str] | None = None,
            state_out: dict[str, Any] | None = None) -> list[str]:
    """跑一次整頁，回傳**有序**的渲染紀錄。

    ⚠️ 回傳 list 而不是一整塊字串 —— 順序本身是本檔要驗的東西之一，
    join 成一坨就驗不了「哪一句落在哪一塊底下」。

    ## ⛔ `auto_fetch_moneydj` **一律被換掉，這不是方便，是必要**

    2026-09-06 深度區接上取數之後，本函式若不換掉它，
    **每一條帶 `applied=` 的測試都會真的連外網**。
    本組實測：第一次跑改動後的測試檔，沙箱的 egress proxy 擋下了
    `fund.api.cnyes.com:443`，整份測試**掛在網路逾時上跑不完**（不是紅，是不會結束）。
    → 一份會連外網的守衛，在 CI 上是**不可重現**的；它紅不紅取決於當天上游活著沒有。

    Parameters
    ----------
    result : 假的 L2 回傳。預設 :data:`_BLANK_RESULT`（全敗），
             因為那才是**大多數既有斷言**在骨架時期看到的處境。
    raiser : 給它一個例外物件 → 假的 `auto_fetch_moneydj` 會 `raise` 它。
             用來驗「真的例外走 `safe_section` 的紅框」那條路徑。
    session : 額外預塞的 session 鍵值（批次的已送出清單／已跑完的列）。
              ⚠️ 2026-09-07 補。**不要**改成「測試自己去動真的 `st.session_state`」——
              本函式用的是 recorder 自帶的那一份 dict，改動不會外洩到別條測試。
    patch : 渲染期間要暫時換掉的**被測模組屬性**（`{名字: 替身}`）。
            ⚠️ 一個泛用的鉤子，**刻意不做成三個具名參數** —— 每加一個具名參數
            就是一次「這個 harness 只服務某一條測試」的耦合。
            用途：批次那一塊的重運算入口（`_run_batch`）與需要 pandas 的
            `_batch_column_config` 都必須換掉，否則測試會連外網 / 進不了 CI 以外的環境。
            **一律在 `finally` 還原**（與底下 `st` / `auto_fetch_moneydj` 同一套）。
    widget : `{widget label: 使用者輸入的值}`。**沒指定的完全照舊。**
             ⚠️ 2026-09-07 補：批次的貼上框是 `st.text_area`，
             在此之前 recorder 對它恆回 `value=`（空字串）——
             也就是「使用者真的貼了東西進去」這條路徑**從來沒有被走過**。
    submitted : 送出鈕的回傳值。`True` ＝ 模擬使用者**按下去了**。
              ⚠️ 在此之前 recorder 對送出鈕**恆回 `False`**，也就是整條
              「按下去之後會發生什麼」的路徑**從來沒有被任何測試走過** ——
              批次的長時間運算就長在那條路徑上，所以它必須可驗。
    selected : **已選定的那一檔**（寫進 `v03_research_selected_fund`）。
              ⚠️ 2026-09-08 加。`None` ＝ **還沒選** ⇒ 深度區走空狀態、
              `auto_fetch_moneydj` 一次都不會被呼叫（＝線框「選定後展開」那個 gate）。
              ⛔ **不要**為了讓舊斷言少改而給它一個「有值」的預設 ——
              那等於讓每一條測試都繞過 gate，gate 就沒有人在驗了。
    search : 假的 `services.fund_search.search_funds` 回傳。預設兩列哨兵
              （:func:`_FAKE_ROWS`）。給 `[]` 走「名錄沒有回傳候選」那條路。
              ⚠️ **與 `auto_fetch_moneydj` 同一個理由必須換掉**：不換的話，
              每一條帶 `applied=` 的測試都會真的連 TDCC / FundClear。
    search_raiser : 給它一個例外物件 → 假的 `search_funds` 會 `raise` 它。
              用來驗「搜尋炸了走 `safe_section` 的紅框，而不是被畫成查無結果」。
    clicked : **被按下的 `st.button` 的 key 集合**。`None` ＝ 一顆都沒按
              （`st.button` 回 `submitted`，＝舊行為）。
    state_out : 給它一個 dict → 渲染結束後把 recorder 那份 `session_state`
              **倒進去**。⚠️ 這是「按下按鈕之後 session 變成什麼」唯一驗得到的方式；
              沒有它，「選定後展開」那個 gate 的**寫入端**完全沒有人在看。
              ⛔ **不要**改成讓測試去動真的 `st.session_state` —— recorder 用的是
              自己那一份 dict，改真的那一份會外洩到別條測試。
    """
    import sys

    # 匯入套件 → 它的 `__init__` 會把四個子模組都放進 `sys.modules`。
    import ui.helpers.ia  # noqa: F401

    # ⚠️ **一律走 `sys.modules`，不要用 `import a.b.c as x`。**
    #    `ui/helpers/ia/__init__.py` 有一行 `from ui.helpers.ia.empty_state import
    #    empty_state` —— 它把**函式**綁成了套件的 `empty_state` 屬性，於是
    #    `import ui.helpers.ia.empty_state as _e` 拿到的是那個**函式**而不是模組，
    #    `setattr(_e, "st", …)` 就打在函式身上、模組的 `st` 一動也沒動。
    #    **② 的同型測試初稿就是這樣寫的，症狀是空狀態的標題與 footer 整個錄不到**
    #    —— 也就是說：**錯的 patch 不會報錯，只會讓斷言對著半份畫面生效。**
    _targets = tuple(sys.modules[_n] for _n in (
        "ui.views.page_03_research",
        "ui.helpers.ia.cards",
        "ui.helpers.ia.empty_state",
        "ui.helpers.ia.gated_form",
        "ui.helpers.ia.layout",
        "ui.helpers.render_state",
    ))
    # ⚠️ **`ui.helpers.story_nav` 刻意不在上表**：它的 `render_story_nav()` 是
    #    **函式內** `import streamlit as st`，沒有 module 層的 `st` 可以換 ——
    #    它那一行麵包屑 caption 走的是**真的** streamlit（bare 模式下無害）、
    #    **不會**進到紀錄裡。本檔沒有任何斷言依賴它。

    _rec = _Rec(submitted=submitted, widgets=widget, clicked=clicked)
    if applied is not None:
        _rec.session_state["v03_research_applied_query"] = applied
    if selected is not None:
        _rec.session_state["v03_research_selected_fund"] = selected
    _rec.session_state.update(session or {})

    # ⛔ **紅燈也要錄得到，否則「不准紅」那一族斷言是空的。**
    #    `render_state.system_error()` 走 **lazy** `from ui.helpers.session import
    #    friendly_error`，而 `friendly_error` 自己又是**函式內** `import streamlit`
    #    —— 兩層都繞過了上面那份 `_targets` 的 module 層 `st` 替換，
    #    紅框因此打在**真的** streamlit 上（bare 模式無聲）。
    #    本組實測：補這一段之前，`assert "[error]" not in _all` 是
    #    **恆真**的（頁面就算真的塗紅它也看不見）；補了之後
    #    `test_a_real_exception_stays_a_real_exception` 才第一次真的驗到東西。
    #    ⚠️ 這正是本檔 `_render()` 開頭那段「錯的 patch 不會報錯，
    #    只會讓斷言對著半份畫面生效」講的同一個陷阱，換一層發作。
    import ui.helpers.session as _sess          # noqa: PLC0415 — 與 _targets 同理由
    _real_friendly = _sess.friendly_error

    def _fake_friendly(_title, _exc, *, hint: str = "", level: str = "warning"):
        _rec.parts.append(f"[{level}] {_title} — {type(_exc).__name__}: {_exc}")

    _sess.friendly_error = _fake_friendly

    _page = sys.modules["ui.views.page_03_research"]
    _real_fetch = _page.auto_fetch_moneydj
    _payload = _BLANK_RESULT() if result is _SENTINEL else result

    def _fake_fetch(_raw, **_kw):
        _rec.parts.append(f"[fetch] {_raw}")
        if raiser is not None:
            raise raiser
        return _payload

    _page.auto_fetch_moneydj = _fake_fetch

    # ── 搜尋的 L2 入口，同樣一律換掉（2026-09-08）────────────────────────
    _real_search = _page.search_funds
    _search_payload = _FAKE_ROWS() if search is _SENTINEL else search

    def _fake_search(_term, **_kw):
        _rec.parts.append(f"[search] {_term}")
        if search_raiser is not None:
            raise search_raiser
        return _search_payload

    _page.search_funds = _fake_search
    # ⚠️ 先確認要換的名字**真的存在**：打錯字的 patch 會靜靜地新增一個沒人讀的屬性，
    #    然後測試對著**沒有被換掉**的真實實作跑（那正是本函式開頭那段長註的病）。
    _patch = dict(patch or {})
    _missing = [_k for _k in _patch if not hasattr(_page, _k)]
    assert not _missing, (
        f"`patch=` 指定了被測模組沒有的名字：{_missing} —— "
        "打錯字的 patch 不會報錯，只會讓斷言對著真實實作生效。")
    _patched = [(_k, getattr(_page, _k)) for _k in _patch]
    for _k, _v in _patch.items():
        setattr(_page, _k, _v)
    _saved = [(_m, getattr(_m, "st", None)) for _m in _targets]
    # 錨點：每一個目標模組**都要**真的有 `st` 可以換掉。少一個就代表上面那個
    # 遮蔽陷阱又發作了，而它的症狀是**靜默漏錄**，不是報錯。
    _blind = [_m.__name__ for _m, _old in _saved if _old is None]
    assert not _blind, (
        f"下列模組沒有 module 層的 `st` 可以替換：{_blind}\n"
        "錄不到它們畫的東西，本檔所有斷言會對著半份畫面生效。")
    try:
        for _m in _targets:
            _m.st = _rec
        render_fund_research()
    finally:
        for _m, _old in _saved:
            _m.st = _old
        for _k, _old in _patched:
            setattr(_page, _k, _old)
        _page.auto_fetch_moneydj = _real_fetch
        _page.search_funds = _real_search
        _sess.friendly_error = _real_friendly
        if state_out is not None:
            state_out.clear()
            state_out.update(_rec.session_state)
    return _rec.parts


def _text(parts: list[str]) -> str:
    return "\n".join(parts)


#: 一級區塊標題（`st.markdown("#### …")`）。
_L4_OPEN = re.compile(r"^\[markdown\] #{4}\s+(.*)$")
#: 深度區裡的次級段落（`st.markdown("##### …")`）。
_L5_OPEN = re.compile(r"^\[markdown\] #{5}\s+(.*)$")
#: 一張卡的標題 —— `ia.state_card()` 在灰態時畫的 `st.markdown(f"**{title}**")`。
#: ⚠️ **這一條是本檔的最小單位，不是裝飾**（理由見 :func:`_units`）。
_CARD_OPEN = re.compile(r"^\[markdown\] \*\*(.+)\*\*$")


def _metric_open(part: str) -> str | None:
    """**OK 狀態**的卡片開頭 —— `state_card()` 走 `st.metric(title, value)`。

    ⚠️ **這一條是 2026-09-06 深度區接上真資料時補的，沒有它整份斷言會靜靜半盲。**
    在此之前 :func:`_units` 只認得灰態卡的 `**標題**`；卡片一旦有值就改走
    `st.metric`，錄下來長成 `[metric] NAV 走勢 59.99 USD` ——
    **三個 opener regex 沒有一個match得到**，於是那張卡的內容會被歸進**前一個單位**。
    症狀是「斷言全綠、但它驗的是別人的字」，正是本檔 `_units` 長註在講的那個病。

    ⚠️ 為什麼比對**已知標題**而不是用 regex 切第一個詞：recorder 把位置引數用空白
    join 起來（`f"[metric] " + " ".join(bits)`），而標題自己就含空白（「NAV 走勢」）
    —— 從字串上**無法**分辨標題到哪裡結束。已知標題集合是唯一不會猜錯的判準。
    """
    if not part.startswith("[metric] "):
        return None
    _rest = part[len("[metric] "):]
    for _t in DEEP_DIVE_CARDS:
        if _rest == _t or _rest.startswith(_t + " "):
            return _t
    return None


def _units(parts: list[str]) -> list[tuple[str, list[str]]]:
    """把紀錄切成**有序**的最小單位：一級／次級段落，或**一張卡**。

    ⚠️ **粒度是「一張卡」，這是被 ② 的一次突變逼出來的，不是設計出來的。**
    `tests/test_wf02_health_skeleton.py::_units` 記著：初版只依 `#### 區塊名` 切段，
    突變「只拿掉其中一塊的灰態」**沒有轉紅** —— 因為同一段裡別張卡的 ⬜ 替它過關了。
    同一個形狀在 ① 被獨立稽核連續打穿兩輪。**答案每次都一樣：把邊界往下降。**

    ⛔ **不要為了讓斷言好寫而把邊界往上收。** 邊界一寬，鄰居的字就會替你通過。

    ## ⚠️ 這個切法**看不到什麼**（2026-09-06 實測補；不要讀成「整頁都被切進單位裡」）

    **第一個 opener 之前的每一行都會被整段丟掉** —— 本函式只在 `if _out:` 成立時
    才把行歸進單位，而 `_out` 在遇到第一個 opener 之前是空的。
    以本頁**送出查詢後**的實際渲染紀錄實測，落在所有單位之外的有 **6 行**：

    ```
    [markdown] ## 🔍 標的探索          ← 頁標題
    [caption]  回答一個問題：…          ← 職責宣告 ＋「這裡不放什麼」的指路
    [caption]  搜尋條件：輸入完按…      ← Form 的說明
    [text_input] 代碼或名稱             ┐
    [selectbox]  來源                   ├ **整個 Form**
    [form_submit_button] 搜尋           ┘
    ```

    ⚠️ **重點不是「頁首看不到」，是「Form 整塊看不到」** —— 而 Form 正是本頁
    唯一真的做完、也是所有灰態指路都指向的那一塊。
    → 任何**針對 Form 的**斷言都必須走**整頁**紀錄（`_text(_render(...))`）
    或直接呼叫純函式，**不能**用 `_segments()` 去拿它（會拿到空字串而**靜靜通過**）。
    本檔既有的 Form 斷言（`test_the_search_form_is_the_first_thing_on_the_page`
    等）**本來就是走整頁的**，所以現況沒有被打穿；這段是寫給**下一個**要加
    Form 斷言的人看的。
    ⚠️ 同型限制在 ①②④⑤ 四頁的骨架守衛都存在（同一套 `_units` 寫法）。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _metric = _metric_open(_p)
        if _metric is not None:
            # ⚠️ 有值的卡：`st.metric` 那一行**自己也算內容**（值就印在裡面），
            #    所以開新單位之後要把它放回 body，否則「這一格印了什麼數字」驗不到。
            _out.append((_metric, [_p]))
            continue
        _m = _L4_OPEN.match(_p) or _L5_OPEN.match(_p) or _CARD_OPEN.match(_p)
        if _m:
            _out.append((_m.group(1).strip(), []))
            continue
        if _out:
            _out[-1][1].append(_p)
    return _out


def _segments(parts: list[str]) -> dict[str, list[str]]:
    """`單位名 -> 該單位內的渲染紀錄`（:func:`_units` 的 dict 檢視）。

    ⚠️ **dict 會讓同名單位後者覆蓋前者** —— 那正是 ② 被紅隊打穿的繞道。
    本檔用 :func:`test_unit_names_are_unique` 把「不會有同名單位」變成一條**斷言**，
    而不是一個假設。**本函式因此可以安全地用 dict。**
    """
    return {_k: _v for _k, _v in _units(parts)}


#: 一級區塊（`####`）的順序，即線框 Tab 03 由上而下的順序。
EXPECTED_BLOCKS: tuple[str, ...] = (BLOCK_RESULTS, BLOCK_DEEP, BLOCK_BATCH)

#: **每一個都要各自帶灰態**的最小單位（八個）。
#: ⚠️ `BLOCK_DEEP` 不在這裡：它是**純容器**（標題底下直接接三張卡），
#:    它的「內容」就是下面這幾個單位，各自有自己的灰。
GREY_UNITS: tuple[str, ...] = (
    (BLOCK_RESULTS,) + DEEP_DIVE_CARDS + DEEP_DIVE_TABLES
    + (DEEP_DIVE_PROVENANCE, BLOCK_BATCH)
)

#: 內容還沒接上的單位 → **它自己那一句**灰態理由。
#: ⚠️ ~~舊版是 `PENDING_UNITS: tuple = (BLOCK_RESULTS, BLOCK_BATCH)`，兩個單位共用~~
#:    ~~一個 `_PENDING_NOTE`。~~ → **2026-09-06 改成 dict（狀態變更，不是漏刪）**：
#:    兩塊「為什麼還沒有」的原因**完全不同**（一個缺搜尋、一個缺輸入欄位），
#:    共用一句就等於對使用者說謊。改成 dict 之後，
#:    :func:`test_every_grey_unit_is_grey_until_its_content_lands` 驗的是
#:    「**這個單位有沒有印它自己那一句**」，而不是「頁面上有沒有出現那句共用的話」。
#: ⚠️ **這個粒度差別是有實據的**：舊寫法只要頁面上任一處印了共用那句就通過，
#:    把兩塊的理由對調**不會轉紅**；改 dict 之後對調就轉紅（突變 P2，見該函式）。
#: ⚠️ **2026-09-07：批次也離開了這一族（狀態變更，不是漏刪）。**
#:    批次接上真取數之後，它的灰態理由不再是「這一塊還沒做」，而是
#:    **「你還沒貼代碼」**（`_BATCH_EMPTY_MISSING`）或**「貼了但認不得」**
#:    （`_BATCH_UNPARSED_MISSING`）—— 兩者都是使用者**照著做真的能解決**的空狀態。
#:    依既有處置（深度區 2026-09-06 離開時走的同一條路）：**參數化縮小，
#:    不是把規則放寬** —— 批次改由 `tests/test_wf03_research_batch.py` 驗真內容。
#: ⚠️ **2026-09-08：這一族空了（狀態變更，不是漏刪）。**
#:    搜尋結果是它最後一個成員；接上 `services.fund_search.search_funds` 之後，
#:    它的空狀態理由變成 :data:`_RESULTS_EMPTY_MISSING`（**來自資料**：名錄回了空清單），
#:    不再是「這一頁做到哪裡」。
#:    ⛔ **空 dict 會讓 `test_every_grey_unit_is_grey_until_its_content_lands`
#:    變成零參數的死測試**，所以那一條**沒有留著空轉** —— 它已依自己 docstring 寫的
#:    處置改寫成 :func:`test_no_block_still_explains_itself_with_this_pages_progress`，
#:    驗的是「這一族真的空了、而且畫面上沒有進度式的措辭」。
#:    **這不是放寬**：舊條驗「還沒接上的那幾塊有沒有誠實留灰」，新條驗「已經沒有
#:    任何一塊還沒接上」，**後者比前者強**（它連「悄悄把一塊退回灰態」都會抓到）。
PENDING_NOTES: dict[str, str] = {}
#: 仍然吃「內容還沒接上」灰態的單位 —— **一個都沒有了**。
#: ⚠️ 深度區的六格自 2026-09-06 起、批次自 2026-09-07 起、搜尋結果自 2026-09-08 起
#:    **都不再**吃那一族：它們的灰／空理由來自資料本身或使用者的輸入。
PENDING_UNITS: tuple[str, ...] = tuple(PENDING_NOTES)

#: 本頁**現行**所有「沒有內容時要說的話」，每一句都必須不一樣（:func:`test_the_greys_on_this_page_are_not_one_recycled_sentence`）。
#: ⚠️ 它取代了舊的 `PENDING_NOTES` 當那條規則的主詞 —— **句子只增不減**。
LIVE_EMPTY_NOTES: dict[str, str] = {
    "搜尋結果（名錄沒回候選）": _RESULTS_EMPTY_MISSING,
    "深度區（還沒選定）": _NOT_SELECTED_MISSING,
    "批次（還沒貼代碼）": _BATCH_EMPTY_MISSING,
    "批次（貼了但認不得）": _BATCH_UNPARSED_MISSING,
}


#: 深度區的六個單位（三張卡 ＋ 兩張大表 ＋ 來源標註）。
DEEP_UNITS: tuple[str, ...] = (
    DEEP_DIVE_CARDS + DEEP_DIVE_TABLES + (DEEP_DIVE_PROVENANCE,)
)

#: 取數**全敗**時應該是灰的單位。
#: ⛔ **`DEEP_DIVE_PROVENANCE` 刻意不在其中，這是本批的核心設計不是遺漏**：
#:    全敗正是那一格**最該有內容**的時候 —— 它要把逐源軌跡攤開，
#:    讓使用者自己判斷「代碼打錯」還是「來源當下不可用」（L2 分不出來，見被測檔
#:    `_fetch_failed_note()`）。把它一起要求成灰態，等於要求證據在最需要時消失。
#:    它有沒有真的攤開，由
#:    :func:`test_a_total_failure_shows_the_source_trace_and_never_paints_red` 驗。
#: ⚠️ **2026-09-07：`BLOCK_BATCH` 已自動掉出這個清單，這是刻意的，不是漏改。**
#:    它是跟著 :data:`PENDING_UNITS` 縮的（批次接上真取數 → 離開「內容還沒接上」那一族）。
#:    **後果要講明**：`test_every_grey_unit_says_where_to_look` 對批次**不再生效** ——
#:    因為那條除了驗「有指路」還會驗「指路指回**搜尋條件**」，而批次的指路
#:    現在指的是**它自己的貼上框**（`page_03_research._batch_where()`）。
#:    「去搜尋條件打一個代碼」**解決不了**「你還沒貼多個代碼」，照著做會回到一模一樣的灰。
#:    ⛔ **不得**為了讓批次留在這條規則裡而把它的指路改回搜尋條件 —— 那是把一則
#:    **真的有效**的指路換成一則**已知無效**的。批次的指路改由
#:    `tests/test_wf03_research_batch.py::test_the_batch_pointer_is_the_paste_box` 驗，
#:    而且**驗得比本條嚴**（它連「指到的欄位在畫面上真的存在」都驗）。
#: ⚠️ **2026-09-08：`PENDING_UNITS` 空了之後，本清單剩下純深度區的五格**
#:    （狀態變更，不是漏刪）。**後果要講明，不要讓下一個人以為射程沒變**：
#:    使用這個清單的 :func:`test_every_grey_unit_says_where_to_look` 現在
#:    **只在「已選定一檔」的處境下**生效 —— 沒選定時深度區根本不畫這五格
#:    （那是線框「選定後展開」的 gate，見被測檔 `_render_deep_dive()`）。
#:    「搜尋結果」的指路改由 :func:`test_the_pending_pointer_is_a_place_not_a_status_sentence`
#:    與 :func:`test_the_empty_results_state_carries_all_three_elements` 驗。
GREY_ON_BLANK: tuple[str, ...] = PENDING_UNITS + DEEP_DIVE_CARDS + DEEP_DIVE_TABLES

#: 一份「已送出」的查詢。形狀就是 `_normalise_query()` 的回傳值。
FAKE_QUERY = {"term": "ACDD", "source": SOURCE_OPTIONS[0]}


def _live_strings(tree: ast.AST) -> list[ast.Constant]:
    """檔內**活字串**（排除 module / class / function 的 docstring）。

    ⚠️ 沒有這個排除，本檔的規則會被**被測檔自己的說明文字**打紅 ——
    例如模組 docstring 裡就寫著「本檔沒有自己拼 ⬜ 的字串」。
    """
    _docs: set[int] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                           ast.AsyncFunctionDef)):
            _b = getattr(_n, "body", None)
            if (_b and isinstance(_b[0], ast.Expr)
                    and isinstance(_b[0].value, ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _docs.add(id(_b[0].value))
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str)
            and id(_n) not in _docs]


def _tree() -> ast.Module:
    return ast.parse(SRC.read_text(encoding="utf-8"))


def _attr_calls(tree: ast.AST, names: tuple[str, ...]) -> list[str]:
    return [f"第 {_n.lineno} 行 {ast.unparse(_n.func)}(…)"
            for _n in ast.walk(tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in names]


# ══════════════════════════════════════════════════════════════════
# 骨架：四塊都在、順序對
# ══════════════════════════════════════════════════════════════════

def test_the_search_form_is_the_first_thing_on_the_page():
    """線框 Tab 03 的第一塊就是 Form —— 而且它必須在任何結果**之前**。

    順序不是美感問題：搜尋條件在結果**後面**的話，使用者會先看到一堆
    他還沒下條件的東西。
    """
    _parts = _render(applied=FAKE_QUERY)
    _submit = [_i for _i, _p in enumerate(_parts)
               if _p.startswith("[form_submit_button]")]
    assert _submit, (
        "整頁沒有任何 `form_submit_button` —— 搜尋條件沒有包在 `applied_form()` 裡。\n"
        "線框 Rule 02「篩選、輸入框、滑桿一律 `st.form` 包住」是四大鐵律之二，不是選配。")
    _first_block = next(
        (_i for _i, _p in enumerate(_parts) if _L4_OPEN.match(_p)), None)
    assert _first_block is not None, "找不到任何 `#### 區塊標題` —— 骨架的分段記號不見了。"
    assert _submit[0] < _first_block, (
        "送出鈕出現在第一個內容區塊**之後** —— 搜尋條件必須在結果前面。\n"
        f"送出鈕在第 {_submit[0]} 筆，第一個區塊在第 {_first_block} 筆。")


def test_the_two_fields_and_the_submit_verb_come_from_the_wireframe():
    """線框 Tab 03 的 Form 逐字：「代碼或名稱」「來源」「搜尋」。少一個就紅。

    ⚠️ **送出鈕的字是「搜尋」不是「套用」** —— `ui.helpers.ia.APPLY_LABEL` 的預設值是
    「套用」，線框 Tab 03 明確畫的是「搜尋」（Tab 02 才是「套用」）。
    這不是文案潔癖：使用者要知道按下去會發生什麼事，「套用」在一個搜尋框上不知所云。

    ⚠️ 用**標籤字**比對，因為線框定的就是這兩個欄位本身，不是它們的實作型別
    （型別本檔不驗，見模組 docstring 的已知缺口）。
    """
    _all = _text(_render(applied=FAKE_QUERY))
    # ⚠️ **驗 recorder 的精確前綴，不是 substring**（2026-09-05 紅隊實測）：
    #    上一版寫的是 `assert "來源" in _all`，而畫面上**永遠**有一句
    #    `##### 資料來源與抓取時間` —— 「來源」兩個字被那個**完全無關的段落標題**滿足了。
    #    紅隊把整個 `st.selectbox(_LABEL_SOURCE, …)` 刪掉 → **零紅燈**；
    #    對照組刪 `text_input` → 1 failed。**也就是兩個欄位只守住了一個。**
    #    現在比對 `[selectbox] 來源` / `[text_input] 代碼或名稱`，順帶把型別釘住。
    # ⚠️ **釘線框的字面值，不是釘模組常數**（2026-09-05 第二輪突變 M02 抓到）：
    #    上一版寫的是 `f"[{_api}] {_label}"`，而 `_label` 是**從被測模組 import 進來的
    #    同一個常數** —— 於是把 `_LABEL_TERM` 從「代碼或名稱」改成「關鍵字」，
    #    斷言跟著一起變，**35 passed 全綠**。那是一條**自我參照的恆真式**，
    #    它守的是「渲染有沒有用到那個常數」，**不是**「那個常數是不是線框寫的字」。
    #    現在兩件事分開驗：字面值對線框（下方 `==`），渲染有沒有用到它（`in _all`）。
    assert (_LABEL_TERM, _LABEL_SOURCE) == ("代碼或名稱", "來源"), (
        f"欄位標籤被改成 {(_LABEL_TERM, _LABEL_SOURCE)!r} —— "
        "線框 Tab 03 的 Form 逐字寫的是「代碼或名稱」與「來源」。")
    for _api, _label in (("text_input", "代碼或名稱"), ("selectbox", "來源")):
        assert f"[{_api}] {_label}" in _all, (
            f"搜尋條件少了「{_label}」這個 `st.{_api}` —— "
            "線框 Tab 03 的 Form 逐字列了兩個欄位。\n" + _all)
    assert f"[form_submit_button] {SUBMIT_LABEL}" in _all, (
        f"送出鈕不是「{SUBMIT_LABEL}」—— 線框 Tab 03 畫的是這兩個字。\n" + _all)
    assert SUBMIT_LABEL == "搜尋", (
        f"`SUBMIT_LABEL` 被改成 {SUBMIT_LABEL!r} —— 線框 Tab 03 的送出鈕是「搜尋」。")


def test_the_source_filter_does_not_invent_options():
    """⛔ 「來源」下拉**只准有線框給的那一個值**，不准憑印象補一份來源清單。

    線框只寫了「來源　全部」。這個站點實際支援哪幾個來源要等取數接上才知道；
    先列一份，使用者挑了一個實際上不生效的來源 —— 那是 §1 的**假選項**，
    比少一個選項危險得多（他會以為自己已經篩掉了別的來源）。

    ⚠️ **下一批把真來源集合接上時，這條會轉紅 —— 那是預期的。**
    屆時請把它改成「選項必須來自取數層回報的來源集合」，**不要**直接刪掉它。
    """
    assert SOURCE_OPTIONS == ("全部",), (
        f"`SOURCE_OPTIONS` 變成 {SOURCE_OPTIONS!r} —— 線框只給了「全部」。\n"
        "多出來的選項如果不是取數層真的支援的，它就是一個會騙人的篩選條件（§1）。")


def test_all_blocks_are_present_and_in_wireframe_order():
    """送出搜尋後：搜尋結果 → 單一基金深度 → 批次分析，缺一或倒序即紅。

    ⚠️ **下一批把「選定後展開」的 gate 接上時，這條會轉紅** ——
    因為深度區將不再無條件渲染。**正解是改成 gate 驗證，不是放寬。**
    """
    _parts = _render(applied=FAKE_QUERY)
    _seg = _segments(_parts)
    for _b in EXPECTED_BLOCKS:
        assert _b in _seg, (
            f"線框 Tab 03 的區塊「{_b}」不見了。現有單位：{list(_seg)}")
    _order = [_m.group(1).strip() for _m in
              (_L4_OPEN.match(_p) for _p in _parts) if _m]
    assert _order == list(EXPECTED_BLOCKS), (
        f"一級區塊順序與線框 Tab 03 不符：{_order}\n"
        f"應為：{list(EXPECTED_BLOCKS)}（先給結果，再給單檔深度，最後才是批次）。")


def test_deep_dive_keeps_the_five_blocks_and_the_source_annotation():
    """單一基金深度：3 欄 ×3 ＋ 大表全寬 ×2 ＋ 來源標註，逐字對線框。

    線框原文：「NAV 走勢 · 績效分期 · 風險指標 · 前十大持股 · 配息紀錄 ·
    資料來源與抓取時間。**五個區塊各自 3 欄，持股與配息為大表全寬。**」

    ⚠️ **那句話列了六項卻說「五個區塊」，是線框自己的歧義**（見被測檔的模組 docstring）。
    本檔的處理方式讓**兩種讀法都通過**：五塊各有自己的段落，
    來源標註**也有**自己的段落 —— 突變拿掉其中任何一個都會轉紅。
    """
    assert DEEP_DIVE_CARDS == ("NAV 走勢", "績效分期", "風險指標"), (
        f"深度區的 3 欄卡與線框不符：{DEEP_DIVE_CARDS}")
    assert DEEP_DIVE_TABLES == ("前十大持股", "配息紀錄"), (
        f"深度區的大表與線框不符：{DEEP_DIVE_TABLES}")
    assert DEEP_DIVE_PROVENANCE == "資料來源與抓取時間", (
        f"來源標註與線框不符：{DEEP_DIVE_PROVENANCE!r}")
    # ⚠️ **2026-09-08 起要先「選定一檔」才畫得出這六段（狀態變更，不是漏刪）** ——
    #    那是線框「選定後展開」的 gate。**規則一個字沒放寬**：六段照樣一段都不准少，
    #    只是換到 gate 打開之後才驗。gate **關著**的那一半由
    #    :func:`test_the_deep_dive_does_not_fetch_until_a_fund_is_selected` 與
    #    :func:`test_the_locked_deep_dive_says_how_to_unlock_it` 各驗一半。
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE))
    for _name in DEEP_DIVE_CARDS + DEEP_DIVE_TABLES + (DEEP_DIVE_PROVENANCE,):
        assert _name in _seg, (
            f"深度區少了「{_name}」這一段。現有單位：{list(_seg)}")


def test_unit_names_are_unique():
    """**單位名不得重複** —— 這條堵的是 ② 被紅隊打穿的那條繞道。

    ② 的 `_segments()` 回傳 dict，**同名單位後者覆蓋前者**；紅隊因此可以
    「把真區塊掏空、另造一個同名誘餌帶著灰態」→ 全綠。
    只要單位名保證唯一，dict 檢視就不會遮蔽任何東西。

    ⚠️ 這條同時是 :func:`_segments` 的**前提** —— 它紅了，所有用 `_segments()`
    的斷言都要重新看，不是只有這一條。
    """
    for _applied in (None, FAKE_QUERY):
        _names = [_k for _k, _ in _units(_render(applied=_applied))]
        _dupes = sorted({_n for _n in _names if _names.count(_n) > 1})
        assert not _dupes, (
            f"（applied={_applied is not None}）出現同名單位 {_dupes} —— "
            "`_segments()` 的 dict 檢視會讓後者覆蓋前者，"
            "等於在灰態斷言上開一道後門。請把段落名改成唯一。")


def test_the_two_block_names_are_the_wireframe_wording_verbatim():
    """這兩塊的名字**逐字對 `ia-wireframe.html` Tab 03**：單一基金深度／批次分析。

    ## 沿革（這條前後被推翻過一次，寫下來免得後人以為它一直長這樣）

    本檔上一版把這兩個名字**釘成必須走 `story_nav.section_label()`**
    （畫面上是「🔍 單檔深掘」「📦 批次掃描」），理由是當時
    `wireframe-fund-research.html`（2026-08-31）與 `ia-wireframe.html`（2026-09-01）
    **兩份都已客戶拍板、對這一頁的說法不同**，而 `docs/wireframes/README.md`
    的「版本關係」段沒有登記後者覆蓋前者 —— **在裁決之前不自行拍板，那個處置是對的。**

    **2026-09-05 客戶已裁決：③ 以 `ia-wireframe.html` Tab 03 為準。**
    裁決一下來，走 SSOT 就從「保守」變成**開放偏離**，故本條**反過來**釘線框字面。

    ## ⚠️ 「批次分析」帶著一個真的代價，不要以為它是免費的

    「📦 批次分析」是**已退役的頂層分頁名**（`story_nav.RETIRED_TAB_LABELS`），
    而 `tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`
    的黑名單**含去 emoji 變體** → 直接寫會**當場轉紅**（紅隊與本組都實測過）。
    故依總管裁決在該守衛的 `_LEGIT_EXEMPT` **具名加了一條**，理由逐字寫在那裡：
    它在這裡是 **③ 頁內的區塊標題**，而批次分析**正是被合併進 ③ 的那個功能**，
    所以不會讓使用者去分頁列上找一個不存在的分頁。
    ⛔ **`RETIRED_TAB_LABELS` 本身與 `_KNOWN_DEBT` 一個字都沒動。**

    ⚠️ 本條與那條豁免是**一組的**：有人把這裡改回 `section_label()`，
    那條豁免就會變成**指不到東西的殭屍條目**（`test_exemption_tables_do_not_rot` 會抓）。
    """
    assert BLOCK_DEEP == "單一基金深度", (
        f"`BLOCK_DEEP` 是 {BLOCK_DEEP!r} —— 客戶 2026-09-05 裁決以 "
        "`ia-wireframe.html` Tab 03 為準，該線框那張卡逐字寫的是「單一基金深度」。")
    assert BLOCK_BATCH == "批次分析", (
        f"`BLOCK_BATCH` 是 {BLOCK_BATCH!r} —— 同上，線框逐字是「批次分析」。")
    _t = _tree()
    _lits = {_n.value for _n in _live_strings(_t)}
    assert {"單一基金深度", "批次分析"} <= _lits, (
        "這兩個名字不是本檔的活字串 —— 裁決後它們必須逐字寫在這裡，"
        "不得再委派給 `section_label()`（那會偏離客戶已裁決的線框）。")


def test_the_wide_tables_go_through_wide_table_not_st_dataframe():
    """大表一律走 `ui.helpers.ia.wide_table()`，不得自己 `st.dataframe`。

    線框 Rule 04：「無資料不畫空表格外框」。而 `st.dataframe(空)` 的**預設行為
    正好就是畫一個空框** —— 把判斷收在唯一的大表入口，這條規則才有著力點
    （`ui/helpers/ia/layout.py` 的模組 docstring）。
    """
    _bad = _attr_calls(_tree(), ("dataframe", "table"))
    assert not _bad, (
        "本頁自己畫了表格，繞過 `wide_table()` 的空狀態分支：\n  "
        + "\n  ".join(_bad)
        + "\n空資料時它會畫一個空表格外框，正是鐵則 04 要禁的冗餘占位。")


def test_the_page_draws_no_grid_or_form_of_its_own():
    """鐵則 01 / 02 一律走共用元件：本檔不得有 `st.columns` 或 `st.form`。

    ⚠️ **這裡曾寫「自己寫 `st.columns` 會讓 `GRID_EXEMPT_CALL_TOTAL` 轉紅」——
    那是假的，2026-09-05 由獨立紅隊實測推翻**：加 `st.columns(3)`（＝鐵則 01 叫你開的
    那個）→ **全綠**；`st.columns(2)` → 2 failed。那個計數器抓的是「**欄數不是 3**」
    的呼叫，**合規的 3 欄它一動也不動**。
    ⛔ **所以「本頁不得自己開網格」這條，全域沒有任何一道網子，只有本條在守。**
    （`st.form` 那半仍然成立：`FORM_SITE_TOTAL` 是精確 `==`，多一個站點就紅。）
    ⚠️ 同一份 PR 的模組 docstring（本檔開頭「兩個全域守衛的實測盲點」段）**當時就寫對了**，
    是這裡把假話又抄了一遍 —— **一份在講「文件不該說謊」的守衛，自己的描述必須先為真。**

    ⛔ **本條擋得住的只有 `st.columns` / `st.form` 這兩個 attribute 名。**
    `getattr(st, "columns")(2)` 與 `from streamlit import columns as _c` 都繞得過
    —— **但全域 `tests/test_ui_grid_contract.py` 對 alias 同樣失明，
    那是 repo 既有性質，不是本頁造成的**（總管 2026-09-05 排程裁決：登記，本批不修）。
    """
    _bad = _attr_calls(_tree(), ("columns", "form"))
    assert not _bad, (
        "本頁自己開了網格 / 表單，沒有走 IA kit：\n  " + "\n  ".join(_bad)
        + "\n請改用 `ui.helpers.ia.render_cards()` 與 `ui.helpers.ia.applied_form()`。")


# ══════════════════════════════════════════════════════════════════
# 鐵則 02 / 04：Form 之前什麼都不畫
# ══════════════════════════════════════════════════════════════════

def test_nothing_below_the_form_renders_before_a_search():
    """還沒送出查詢 → 只有 Form ＋ 空狀態三要素，下面**一塊都不畫**。

    兩條線框依據，缺一不可：
      - **Rule 04**「無資料不畫空表格外框，改用空狀態三要素」；
      - Tab 03 批次分析的 chip「**Form 後才跑**」（長時間運算不得在載入時自己啟動）。
    """
    _parts = _render(applied=None)
    _seg = _segments(_parts)
    _leaked = [_b for _b in EXPECTED_BLOCKS + GREY_UNITS if _b in _seg]
    assert not _leaked, (
        f"還沒搜尋就畫出了 {_leaked} —— 空狀態應**取代**它們，"
        "而且批次分析的「Form 後才跑」不允許它在載入時就出現。")
    _all = _text(_parts)
    assert "還沒開始搜尋" in _all, "還沒搜尋時應出現空狀態的標題。"
    assert "還沒有查詢條件" in _all, "空狀態缺了「缺什麼」這一要素。"
    assert where_to_find("research") in _all, (
        "空狀態的「去哪補」沒有指回本頁的搜尋條件 —— "
        f"應含 `where_to_find('research')` ＝ {where_to_find('research')!r}。")


def test_the_empty_state_does_not_also_print_the_batch_pending_excuse():
    """兩種灰不得混在一起。

    ⚠️ 這條擋的是一個很容易犯、而且看起來無害的錯：還沒搜尋時**同時**印出
    「本頁分批上線」的灰字。使用者會以為「輸入代碼按下去就會看到績效」—— 不會，
    因為內容根本還沒接上。**一次只給一個下一步。**

    ⚠️ 比對常數本體，**不硬抄字面值**。硬抄的話，常數一改措辭
    這條就永遠是 True —— 它守的 bug 照樣存在、而它不再看得見。
    ⚠️ **2026-09-06：兩塊的理由拆成兩句之後，兩句都要檢查。**
    只檢查其中一句的話，另一塊漏印進空狀態就看不見了。
    """
    _all = _text(_render(applied=None))
    for _unit, _note in PENDING_NOTES.items():
        assert _note not in _all, (
            f"還沒搜尋時不應同時印出「{_unit}」的「內容還沒接上」灰字 —— "
            "兩個下一步會互相抵消。\n" + _all)


def test_a_blank_search_never_counts_as_applied():
    """空白查詢**不算送出** —— 這是本頁唯一一條 §1 邏輯，所以它要有自己的測試。

    使用者把欄位清空再按一次送出，語意是「我不查了」；若把空字串當成一次有效查詢，
    畫面會停在一堆與任何查詢條件都無關的灰態上。

    ⚠️ 這條**直接呼叫 `_normalise_query()`**，不經渲染 ——
    recorder 的送出鈕恆為 `False`，走渲染路徑測不到這一段（模組 docstring 已登記）。
    """
    assert _normalise_query("", SOURCE_OPTIONS[0]) is None
    assert _normalise_query("   ", SOURCE_OPTIONS[0]) is None
    assert _normalise_query(None, SOURCE_OPTIONS[0]) is None  # type: ignore[arg-type]
    _q = _normalise_query("  ACDD19 ", SOURCE_OPTIONS[0])
    assert _q == {"term": "ACDD19", "source": SOURCE_OPTIONS[0]}, (
        f"非空查詢應被收成 `{{'term','source'}}`，實際得到 {_q!r}。")
    # `source` 給空**不得自己挑一個來源** —— 退回第一個選項（目前是「全部」）。
    assert _normalise_query("ACDD19", "") == {
        "term": "ACDD19", "source": SOURCE_OPTIONS[0]}


def test_downstream_reads_the_applied_query_not_the_widget_values():
    """查詢的**已送出值**與 widget 當下值必須是兩個東西。

    ⚠️ 這條守的是鐵則 02 真正的那一半。只包 `st.form` 只擋住「widget 互動觸發 rerun」，
    **沒有擋住重運算** —— 每次 rerun 照樣把下游跑一遍，畫面看起來沒問題、成本一分沒省
    （`ui/helpers/ia/gated_form.py` 模組 docstring 把這個陷阱寫得很清楚）。

    ⚠️ ~~**這條分不出真假閘門**（② 的紅隊實測：`if True:` 與 `if not _gate:` 都全綠）——
    它只驗「session 寫入有沒有被某個 `if` 包住」。**登記，本批不補。**~~
    → **2026-09-05 狀態更新，不是漏刪**：**後半已修** —— 不再是「被某個 `if` 包住」，
    改成「被**閘門那個** `if` 包住」（`gate_ifs()`），所以 `if True:` 那一種**現在會轉紅**
    （它不提到 `_gate` ⇒ 不算閘門 ⇒ 底下的寫入判為裸寫入）。
    **前半仍然成立**：`if not _gate:` 照樣被認成閘門，靜態規則分不出語意反轉。
        ## 這條看得見／看不見什麼（2026-09-05 重寫，**先讀這段再信它**）

    session 寫入有**四條管道**，本條靠 `tests/_ast_bindings.py::session_writes`
    四條全收：下標賦值／**屬性賦值**／`update()`＋`setdefault()`／**widget 的 `key=`**。
    ⚠️ **2026-09-05 第二輪：管道 4 已收窄，這不是放水，是修一條無解的偽陽性。**
    widget 一定建在 `with applied_form(...)` 內、閘門 `if` 一定在 `with` 外
    ⇒ 帶 `key=` 的 widget **結構上永遠不可能**落在閘門 body 裡；不收窄的話這條
    **沒有任何合法擺法能轉綠**（本 repo `ui/**` 有 231 處 `key=`，那是家風）。
    現行判準：`key=` **指到守衛在乎的那個 session key** 才算違規（常數名與字面值都認），
    widget 寫自己的鍵不是。**此判準不依賴任何未經實測的 streamlit runtime 語意。**
    ⚠️ 重寫前它**只認第一條**（`ast.Assign` ＋ target 是 `ast.Subscript`）——
    本組 2026-09-05 的基線實測：三頁 × 另外三條管道，注入裸寫入後**全部 18/18 綠**。
    其中**屬性賦值**是本 repo `ui/**` 跨 6 檔 27 處的主流寫法，
    **最可能被下一個人照家風真的踩到**；`key=` 那條最陰 —— streamlit **代呼叫端**
    把 widget 值寫進 session，AST 上是普通 `ast.Call`，任何「找賦值節點」的手段都收不到。

    「被閘門包住」的判準也換了：從「在**任何**一個 `ast.If` 底下」改成
    **「在 `with applied_form(...) as X` 綁出來的那個 `X` 所控制的 `if` 底下」**
    （`gate_ifs()`）。舊判準的洞：只要有人往這個函式加第二個 `if`
    （例如 `if not _funds: return`），藏在它底下的裸寫入就會被算成「已被閘門包住」。
    **實測**：重寫前本函式只有 `_gate` 一個 `if`，所以那個洞**尚未發作** ——
    修的是「下一個人加第二個 `if` 就會中」。

    ⛔ **仍然分不出真假閘門**：`if not _gate:` 的 test 一樣提到 `_gate`，
    本條照樣認它是閘門（`gate_ifs()` 的 docstring 就地寫明）。
    那一種要靠 AppTest 行為測試去驗，靜態規則做不到。
    ⛔ **不遞迴進被呼叫的函式**：把 `st.session_state` 傳出去、由別處寫，本條看不到。
    """
    _t = _tree()
    _fns = {_n.name: _n for _n in ast.walk(_t) if isinstance(_n, ast.FunctionDef)}
    for _need in ("_applied_query", "_normalise_query"):
        assert _need in _fns, (
            f"找不到 `{_need}()` —— 「已送出值」這一層被拿掉了，"
            "下游就會直接讀 widget 值，等於沒有 form。")
    _form_fn = _fns["_render_search_form"]
        # ⚠️ 管道 4（widget `key=`）**必須**收窄成「只認守衛在乎的那個 session key」：
    #    widget 一定建在 `with applied_form(...)` 內，而閘門 `if` 一定在 `with` 外
    #    ⇒ 帶 `key=` 的 widget 結構上永遠不可能落在閘門 body 裡，不收窄就是一條
    #    **永遠無法滿足**的守衛（本 repo `ui/**` 有 231 處 `key=`，量測日 2026-09-05）。
    # ⚠️ **自動收齊模組層所有 `_SK_*`，不要列舉** —— 列舉一定會漏下一個新加的鍵。
    #    上一版只餵 `_SK_APPLIED`，於是 `key=_SK_PORTFOLIO`（使用者的 live 持股）
    #    那顆突變從紅掉成綠（2026-09-06 稽核 M-1，②④ × 三序實測）。
    # ⚠️ **本頁（③）沒有 `_SK_PORTFOLIO`，所以這個改動在本 SHA 是字面上的 no-op**
    #    —— 實測新舊回傳**完全相同的集合** `{_SK_APPLIED, 字面值}`。
    #    本頁的線框明訂「不預設我有持有」，另有一條守衛專門禁 `"portfolio_funds"`
    #    出現在本頁，所以那個常數本來就不該在這裡。
    #    **改成掃前綴的價值在本頁是前瞻的**：日後本頁新增任何 `_SK_*`（實測以
    #    `_SK_DRAFT` 驗過）會自動被守到，不必記得回來改這一行。
    _applied_keys = guarded_key_names(_t)
    _writes = session_writes(_form_fn, widget_key_names=_applied_keys)
    assert _writes, "`_render_search_form()` 沒有把送出結果寫回 session。"
    _gate_ifs = gate_ifs(_form_fn)
    assert _gate_ifs, (
        "`_render_search_form()` 裡找不到 `with applied_form(...) as <gate>:` 綁出來的那個閘門 `if` —— "
        "form 沒有 gate 住任何東西（或閘門換了寫法，請同步 `gate_ifs()` 的判準）。")
    # ⚠️ 只算閘門 `if` 的 **body** —— `else:` / `elif` 是閘門為假才跑的路徑，
    #    整棵 `ast.walk(_g)` 會把它們一起算成 guarded（2026-09-05 實測的洞）。
    _guarded = gate_guarded_ids(_form_fn)
    _naked = [_w for _w in _writes if id(_w) not in _guarded]
    assert not _naked, (
        "有 session 寫入**沒有**被送出閘門包住 —— 那代表每次 rerun 都會覆寫已送出值，\n"
        "使用者打字的當下就會觸發下游重算，form 等於白包。\n  "
        + "\n  ".join(f"第 {_w.lineno} 行：{ast.unparse(_w)[:70]}" for _w in _naked))


# ══════════════════════════════════════════════════════════════════
# 灰態：八個單位各自誠實
# ══════════════════════════════════════════════════════════════════

#: 「這一頁做到哪裡」這一族的措辭 —— **本頁一句都不准再出現**。
#: ⚠️ 這是一份**黑名單**，黑名單結構上抓不到名單外的第 N+1 個寫法
#:    （同 :data:`_PINNED_FAKE_VALUES` 的自陳）。它守的是「**退回**舊寫法」，
#:    不是「所有可能的進度式措辭」。真正的主力是下面第一條 `PENDING_NOTES == {}`。
_PROGRESS_EXCUSES: tuple[str, ...] = (
    "本頁分批上線", "還沒有接上", "還沒接上", "本批", "下一批", "尚未實作",
)


def test_no_block_still_explains_itself_with_this_pages_progress():
    """本頁**沒有任何一塊**還在拿「這一頁做到哪裡」當「為什麼沒有內容」。

    ## 這一條是誰的接班人，以及為什麼不是放寬

    ~~`test_every_grey_unit_is_grey_until_its_content_lands`~~
    （逐一驗 :data:`PENDING_UNITS` 裡每個單位有沒有誠實留灰）
    **2026-09-08 起沒有參數可以跑了** —— 它的最後一個成員「搜尋結果」
    在同一批接上了 `services.fund_search.search_funds`。
    一個零參數的 parametrize **會靜靜地通過**，那是本 repo 反覆記載的
    「規則對空氣生效還天天綠」。

    **舊條自己寫的處置逐字是**：「屆時請把它改成『真內容放行』，**不要把它放寬**」。
    照做的結果就是本條 —— 而且它**比舊條強**：
      · 舊條問「**還沒接上的那幾塊**有沒有誠實留灰」（漏掉的塊它看不到）；
      · 本條問「**還有沒有塊還沒接上**」（多一塊退回灰態，它當場紅）。
    真內容那一半沒有消失，散在各自的守衛裡：搜尋結果由
    :func:`test_the_results_block_lists_the_candidates_the_service_returned` 等條，
    深度區由 :func:`test_a_deep_unit_that_has_data_shows_it_and_one_that_has_none_stays_grey`，
    批次由 `tests/test_wf03_research_batch.py`。

    ## 兩條斷言，各守一半

    1. **`PENDING_NOTES == {}`** —— 有人新增一個「內容還沒接上」的常數並登記進來，
       本條當場紅。這一半是**結構性**的，不靠字表。
    2. **畫面上不得出現進度式措辭**（:data:`_PROGRESS_EXCUSES`）——
       擋的是「不登記、直接把句子寫進渲染函式」那條繞道。
       ⚠️ 這一半是黑名單，**只擋得住列出來的那幾個寫法**，照實寫在這裡。
    """
    assert PENDING_NOTES == {}, (
        "有單位回到了「這一頁做到哪裡」那一族的灰態："
        f"{sorted(PENDING_NOTES)}\n"
        "一句進度回報對使用者沒有下一步 —— §1 要的是「缺什麼、去哪補」。\n"
        "若真的有一塊還沒接上，請給它一句**來自資料或使用者輸入**的理由，"
        "而不是復活 `_PENDING_NOTE` 那一族。")
    for _kw in (dict(applied=None),
                dict(applied=FAKE_QUERY),
                dict(applied=FAKE_QUERY, search=[]),
                dict(applied=FAKE_QUERY, selected=SELECTED_CODE)):
        _all = _text(_render(**_kw))
        _hit = sorted({_e for _e in _PROGRESS_EXCUSES if _e in _all})
        assert not _hit, (
            f"（處境 {_kw}）畫面上出現了進度式措辭 {_hit} —— "
            "使用者要的是「缺什麼、去哪補」，不是這一頁的開發進度。\n" + _all)


def test_the_greys_on_this_page_are_not_one_recycled_sentence():
    """本頁的灰態理由**兩兩不得相同** —— 它們卡住的原因根本不同。

    ⚠️ **2026-09-07 換了主詞（狀態變更，不是漏刪）**：本條原名
    `test_the_two_pending_reasons_are_not_the_same_sentence`，驗的是
    `_RESULTS_PENDING_NOTE` vs ~~`_BATCH_PENDING_NOTE`~~。批次接上真取數之後
    後者**已不存在**（它的灰換成兩句**空狀態**），故主詞由「兩句 pending」
    換成「本頁現有的三句灰」。**規則一個字都沒有放寬，涵蓋的句子反而多了一句。**

    · 「搜尋結果」卡在**沒有可以列出候選的搜尋**（資料面）；
    · 「批次（還沒貼）」卡在**使用者還沒給代碼**（他照著做就能解決）；
    · 「批次（貼了但認不得）」卡在**格式不對**（下一步是去改格式，不是去貼）。

    共用一句「本頁分批上線」會把兩件事說成同一件，使用者無從判斷哪一個跟他有關、
    也無從知道哪一個是他等得到的 —— 那是 §1 的失效模式（**看起來有解釋、實際沒有**）。

    ⚠️ **本條不驗那幾句話的「意思」**（測試沒有判讀語意的能力），只驗三件可驗的事：
    (1) 兩兩不相等、(2) 每句都不是空的、(3) 都沒有退回舊的共用措辭。

    ## 突變實驗（2026-09-06 實跑）

    - **P1** 把 `_BATCH_PENDING_NOTE` 改成 `_RESULTS_PENDING_NOTE`（退回共用一句）
      → **本條轉紅**。
    - **P2** 把兩句**對調**（各自都還在，只是掛錯塊）→ 本條**不會**紅（兩句仍不相等），
      但 :func:`test_every_grey_unit_is_grey_until_its_content_lands` **轉紅** ——
      那條驗的是「這個單位有沒有印**它自己**那一句」。**兩條分工，缺一不可。**
    """
    # ⚠️ **2026-09-08 換主詞（狀態變更，不是漏刪）**：本條原本吃
    #    ~~`_RESULTS_PENDING_NOTE`~~，而它在搜尋結果接上真取數之後**已不存在**
    #    （它的灰換成一句**空狀態**：名錄回了空清單）。主詞改成
    #    :data:`LIVE_EMPTY_NOTES` —— **本頁現行所有「沒有內容時要說的話」**。
    #    **規則一個字沒放寬，涵蓋的句子從三句變成四句。**
    _NOTES = dict(LIVE_EMPTY_NOTES)
    assert len(set(_NOTES.values())) == len(_NOTES), (
        "本頁的灰態理由有兩句以上是同一句 —— 它們卡住的原因不同"
        f"（{' / '.join(_NOTES)}），共用一句等於對使用者說謊。\n"
        + "\n".join(f"  {_k}: {_v}" for _k, _v in _NOTES.items()))
    # ⛔ **內容錨定**（2026-09-06 獨立稽核 應修 2）：只驗「兩者不相等」擋不住
    #    **把兩個常數的字串內容互換**（突變 B1）—— 因為 `PENDING_NOTES` 是按**常數名字**
    #    綁期望值，內容一起換、期望值就跟著換，畫面輸出與突變 P2 一模一樣卻全綠。
    #    ⚠️ 而那兩個常數在檔案裡**相鄰**、呼叫點卻隔 600 行 ——
    #    **本組守住了難發現的那一種（P2 對調呼叫點），漏掉了容易寫錯的那一種。**
    #    下面兩條各挑一個**真的只屬於那一塊**的詞釘住。
    assert "多代碼" in _BATCH_EMPTY_MISSING, (
        "批次「還沒貼」那一句沒有講到「多代碼」—— 它缺的就是多個代碼。")
    assert "名錄" in _RESULTS_EMPTY_MISSING, (
        "搜尋結果那一句沒有講到「名錄」—— 它缺的就是名錄回來的候選清單。")
    # ⛔ **這一條比錨定詞更要緊**：空清單的意思**必須**照抄 L2 那句實話，
    #    不得被改寫成「查無此基金」——L1 把「真的沒有」與「來源全掛」都回成 `[]`。
    assert EMPTY_MEANS_UNKNOWN in _RESULTS_EMPTY_MISSING, (
        "搜尋結果的空狀態沒有照抄 `services.fund_search.EMPTY_MEANS_UNKNOWN` ——\n"
        "本頁分不出「名錄裡真的沒有」與「名錄來源當下取不到」，"
        "挑一種講就是替上游編了一個它沒說過的結論（§1）。")
    assert "候選" in _NOT_SELECTED_MISSING and "一次只看一檔" in _NOT_SELECTED_MISSING, (
        "深度區「還沒選定」那一句沒有講出它在等什麼 —— "
        "使用者無從知道下一步是「去上面點一張卡」。")
    assert "英數字" in _BATCH_UNPARSED_MISSING, (
        "批次「認不得」那一句沒有講出代碼的形狀 —— "
        "使用者無從知道要把貼上的內容改成什麼樣子。")
    assert "多代碼" not in _RESULTS_EMPTY_MISSING and "名錄" not in _BATCH_EMPTY_MISSING, (
        "兩句的內容被互換了（或串在一起）—— 錨定詞跑到另一塊去了。")
    for _unit, _note in _NOTES.items():
        assert _note.strip(), f"「{_unit}」的灰態理由是空的。"
        assert "本頁分批上線" not in _note, (
            f"「{_unit}」退回了舊的共用措辭「本頁分批上線」—— "
            "那句話講的是**這一頁的進度**，不是**這一塊缺什麼**。")


def test_the_pending_pointer_is_a_place_not_a_status_sentence():
    """`_pending_where()` 回傳的必須是一個**地方**，不是一句狀態陳述。

    ## 這條是本輪突變 **R5** 逼出來的（不是設計出來的）

    2026-09-05 修好 `_pending_where()` 之後，本組把它**退回舊寫法**
    （``f"{where_to_find('research')} → 目前只有「{block}」是完整的"``）再跑一次 ——
    **1014 passed，一條都沒紅。** 也就是說：**修好了渲染，卻沒有任何東西在防它退回去。**
    依「沒突變過的守衛不要宣稱它守得住」，補上本條。

    ## 判準用**結構相等**，不用關鍵字黑名單

    黑名單（「不准出現『完整』兩個字」之類）只擋得住上一次那個寫法，換個措辭就繞過。
    本條直接釘住組成：**分頁路徑 ＋ `→` ＋ 區塊名**，中間不得夾任何述語。
    任何「狀態陳述」都會因為多出述語而不相等。

    ⚠️ 本條驗的是「**它是不是一個地方**」，**不驗「去了有沒有用」** ——
    後者做不到（這一塊沒接上，去任何地方都不會讓它出現），
    已就地寫在被測檔 `_pending_where()` 的 docstring 裡，不在這裡假裝有守。
    """
    for _block in (BLOCK_FORM, "任意區塊名"):
        assert _pending_where(_block) == (
            f"{where_to_find('research')} → {_block}"), (
            f"`_pending_where({_block!r})` ＝ {_pending_where(_block)!r}\n"
            "它會被 `render_state.not_ready()` 包成「（請先到：…）」——"
            "所以它必須是一個**地方**（分頁路徑 → 區塊名），不能是一句狀態陳述。\n"
            "舊寫法「…→ 目前只有「X」是完整的」被包起來之後是一句**不可執行的指令**："
            "使用者照著回到搜尋條件再送一次，8 條灰態逐字完全相同（紅隊實跑）。")
    # 組成之後真的長成祈使句該有的樣子（不是只驗回傳值，也驗它進到畫面上的形狀）。
    # ⚠️ **2026-09-08 加 `search=[]`（狀態變更，不是放寬）**：搜尋結果接上真取數之後，
    #    「有候選」時那一塊畫的是**卡片**（`STATE_OK`，沒有「請先到」），
    #    指路只在**名錄沒有回傳候選**那條路上出現。本條驗的就是那一條路。
    #    ⛔ 不要改成去別的區塊找那句話 —— 那會讓本條驗到的東西換了對象。
    _seg = _segments(_render(applied=FAKE_QUERY, search=[]))
    _body = "\n".join(_seg.get(BLOCK_RESULTS, []))
    assert f"（請先到：{where_to_find('research')} → {BLOCK_FORM}）" in _body, (
        "畫面上那句「請先到：…」不是預期的地方字串。\n" + _body)


@pytest.mark.parametrize("unit", GREY_ON_BLANK)
def test_every_grey_unit_says_where_to_look(unit: str):
    """每一個灰態單位**各自**要有「去哪補」，而且不得手抄分頁名。

    ## ⚠️ 這條原本是**整頁一次性檢查**，2026-09-05 被紅隊打穿

    舊寫法是 ``assert where_to_find("research") in _all`` —— **整頁 containment**，
    任何**一條**帶著指路就過。紅隊拿掉三處 `wide_table(empty_where=)` →
    **本檔 27 passed、全域 1007 passed，一條都沒紅**，而畫面上那三塊
    **真的失去了「（請先到：…）」**。

    兩個原因疊在一起，缺一都不會出事：
      1. 全域網子（`tests/test_batch2_top_card_grid.py::_where_sites`）
         **不收 `wide_table(empty_where=)` 這個形狀** —— 它只收
         `not_ready` / `empty_state` / `state_card` / 卡片 dict 四種；
      2. 本條當時的粒度是整頁。

    → **現在粒度降到與 :func:`test_every_grey_unit_is_grey_until_its_content_lands`
       一致（一段或一張卡）**，拿掉任一個單位的指路都會**單獨**轉紅。

    ⚠️ **這條驗的是「有沒有指路」，不驗「照著做有沒有用」。**
    這一族的指路**有效性有限**，理由就地寫在被測檔的 `_pending_where()` 上：
    這一塊沒接上，去任何地方都不會讓它出現。
    ✅ 真的有效的是**空狀態**那一則（另由
    :func:`test_nothing_below_the_form_renders_before_a_search` 驗）。
    """
    # ⚠️ **2026-09-08 加上 `selected=`（狀態變更，不是放寬）**：本清單自這一天起
    #    只剩深度區那五格，而深度區在「還沒選定」時**整段不畫**（線框的 gate）。
    #    不給選定的話，這五條會全部紅在「單位不見了」——那是 gate 的正常行為，
    #    不是指路不見了。**斷言本身一個字沒改。**
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」不見了。"
    assert where_to_find("research") in _body, (
        f"單位「{unit}」的灰態沒有「去哪補」—— 指路要走 `where_to_find('research')`，"
        "手抄的分頁名在本 repo 已經指錯三次（見 `story_nav.RETIRED_TAB_LABELS`）。\n"
        + _body)
    # ⚠️ **這一條近乎恆真，失敗訊息 2026-09-06 就地改正**（獨立稽核 登記 3）：
    #    `_body` 是灰態自己的文字，而指路是 `_pending_where(BLOCK_FORM)` 組出來的
    #    → 它**必然**包含 `BLOCK_FORM`。**底層性質成立，但它驗不到「畫面上找得到」**
    #    —— 舊訊息寫「在畫面上找不到」，**宣稱的比它驗到的多**。
    #    真正驗「指路指到的東西存不存在」的規則見 `CLAUDE.md §8.3.P` 的
    #    `P-WHERECONTENT-1`（執行期組出來的指路，靜態規則看不到）。
    assert BLOCK_FORM in _body, (
        f"單位「{unit}」的指路沒有提到「{BLOCK_FORM}」—— "
        "本條只驗**指路字串的組成**（它是否由 `_pending_where(BLOCK_FORM)` 產生），"
        "**不驗**那個名字在畫面上是否真的存在。")


def test_the_page_never_hand_rolls_the_grey_mark():
    """⛔ 不准自己拼 ⬜ 字串 —— 灰態一律委派 `render_state` / `ia` 的入口。

    ⚠️ 這條堵的是 ② 被紅隊打穿的另一條繞道：**手刻
    `st.markdown("⬜ …")` 不走 `not_ready()`，也照樣被灰態斷言認成灰態。**
    自己拼的 ⬜ 不會有 `where=`、不會跟著 `render_state` 的視覺一起變，
    等於在 SSOT 旁邊長出第二套灰。

    ⚠️ 只掃**活字串**：被測檔的 docstring 本身就寫著「本檔沒有自己拼 ⬜ 的字串」，
    不排除 docstring 的話，這條規則會被那句說明打紅。
    """
    _bad = [f"第 {_n.lineno} 行 {_n.value[:40]!r}"
            for _n in _live_strings(_tree()) if NOT_READY_MARK in _n.value]
    assert not _bad, (
        f"本頁的活字串裡出現了 {NOT_READY_MARK!r} —— 灰態請走 "
        "`ui.helpers.render_state.not_ready()` / `ui.helpers.ia.empty_state()` / "
        "`state_card(state=STATE_NOT_READY)`：\n  " + "\n  ".join(_bad))


#: 本條**實際釘住**的字面值 —— 線框 Tab 03 三張示意結果卡上的東西。
#: 列成常數，是為了讓「它到底守了什麼」可以被讀出來，而不是藏在 docstring 的形容詞裡。
_PINNED_FAKE_VALUES: tuple[str, ...] = (
    "安聯台灣智慧基金", "貝萊德世界礦業", "元大高股息平衡",
    "ACDD19", "0P00000XYZ",
    "+12.4%", "+3.1%", "Sharpe 0.81", "0.81", "0.22",
)


def test_the_grey_blocks_never_print_the_illustrative_values_from_the_wireframe():
    """⛔ 線框那三張示意卡上的東西不准出現在畫面上（**只涵蓋下列字面寫法**）。

    為什麼要有這條：填一個看起來合理的績效，使用者**完全看不出它是假的**，
    而且會拿它去決定要不要買（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ## ⚠️ 這條**實際**守得到什麼（照實寫，不要用形容詞）

    **只釘 `_PINNED_FAKE_VALUES` 這 10 個字面寫法。**

    **明確守不到**：裸數字（`12.4` / `3.1` 不帶 `+` 與 `%`）、全形數字、
    把示意值換算成別的寫法（`0.810`）、以及**任何線框以外的捏造值**
    —— 本條是黑名單，黑名單結構上抓不到名單外的第 N+1 個。

    ## ⚠️ 一個**刻意的例外**：`0P0000ABCD`

    它是線框給輸入框的 **placeholder**（灰色格式提示），**不是畫面上的資料** ——
    不會被讀成任何一檔基金的績效或分數，而線框正是用它來指定這個欄位收什麼形狀的字。
    故本條**不釘它**，被測檔的 `_CODE_PLACEHOLDER` 就地寫了同一段理由。
    ⛔ 若客戶認為連 placeholder 都不該出現一個像真的代碼，改那個常數即可。

    ## ⚠️ 2026-09-08：本條曾在**一顆 commit 之內悄悄失去深度區的視野**（獨立稽核抓到）

    ~~舊寫法只渲染**一種**情境：``_all = _text(_render(applied=FAKE_QUERY))``。~~
    「選定後展開」的 gate 上線之後，**那一種情境不再包含深度區的六格**
    （沒有選定 → 深度區整塊不渲染），於是 :data:`_PINNED_FAKE_VALUES` 這 10 個字面值
    **在深度區完全無人看守**；`search=[]` 的空狀態那一屏同樣不在視野內。

    **稽核用同一顆突變在兩個 commit 上跑，證明的就是這件事**
    （把 ``Sharpe 0.81`` / ``+12.4%`` / 線框基金名種進 `_render_deep_dive` 的渲染路徑）：

    ===========================  ==========  ================================
    commit                        本條結果    為什麼
    ===========================  ==========  ================================
    gate 上線**前**               **RED**     那一種情境會渲染深度區
    gate 上線**後**（舊寫法）      **GREEN**   深度區沒被渲染 → 守衛看不見
    ===========================  ==========  ================================

    ⛔ **綠的理由從「掃過了、沒有」變成「沒去掃」** —— 而本 PR 的描述當時還拿它當保證。
    **這正是憲法 §8.2.A.1 驗證段 ④ 記的失效模式：同一把尺只往外用、不往內用** ——
    同一輪新寫的 :func:`test_no_block_still_explains_itself_with_this_pages_progress`
    **已經**用了多情境迴圈，卻沒有回頭把同一個 pattern 套到本條上。

    **現行：五種情境各掃一次**，`gate 前／後`、`有候選／沒候選`、`灰態／有真值`
    四個維度都覆蓋得到。⛔ **不要為了跑快一點把情境砍回一種** ——
    砍掉哪一種，那一屏的示意值就從那一刻起無人看守，**而且畫面上看不出來**。
    """
    # ⚠️ 五種情境的分工，逐條寫明（少一種就是少一屏的視野）：
    #   1. 還沒搜尋            → 空狀態三要素那一屏
    #   2. 有候選、還沒選定     → 結果卡 ＋ 深度區的 gate 空狀態
    #   3. 沒候選（名錄回空）   → 搜尋結果的空狀態 ＋ 逃生門那一屏
    #   4. 已選定、取數全敗     → 深度區六格的**灰態**
    #   5. 已選定、取數有真值   → 深度區六格的**有值**路徑（`st.metric` 那一半）
    for _kw in (dict(applied=None),
                dict(applied=FAKE_QUERY),
                dict(applied=FAKE_QUERY, search=[]),
                dict(applied=FAKE_QUERY, selected=SELECTED_CODE),
                dict(applied=FAKE_QUERY, selected=SELECTED_CODE,
                     result=_RICH_RESULT())):
        _all = _text(_render(**_kw))
        for _fake in _PINNED_FAKE_VALUES:
            assert _fake not in _all, (
                f"（處境 {_kw}）畫面上出現了線框的示意值 {_fake!r} —— "
                "那不是資料，是線框用來示範版面的假數字。\n" + _all)


# ══════════════════════════════════════════════════════════════════
# 邊界：只讀對接既有 Service，不碰底層、不委派舊頁
# ══════════════════════════════════════════════════════════════════

def _imported_modules(tree: ast.AST) -> list[str]:
    _mods: list[str] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            _mods.extend(_a.name for _a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            # ⚠️ **兩個都要吐**：只吐 `_n.module` 會漏掉「同層 import」這條最自然的寫法 ——
            #    `import ui.tab3_portfolio`                     -> "ui.tab3_portfolio"  ✅
            #    `from ui.tab3_portfolio import render_...`     -> "ui.tab3_portfolio"  ✅
            #    `from ui import tab3_portfolio`                -> "ui"  🔴 舊寫法靜靜通過
            #    而下面的判準是 `startswith("ui.tab")` ⇒ 第三種完全不會被擋。
            #    「不得委派舊分頁」是客戶方針的唯一機械保證，漏掉這條等於沒守。
            # ⚠️ **代價照實寫（2026-09-06 更正：原本這裡寫「多吐無害」，那是假的）**：
            #    `from services.fund_service import single_fund_metrics` 會多吐
            #    "services.fund_service.single_fund_metrics" 這種**不是模組**的字串。
            #
            #    ~~消費端都是 `startswith` 比對，多吐無害~~
            #    → **四個消費端沒有一個是純 `startswith`**（實測，不是推論）：
            #      兩個是 `_m.split(".")[0] in (...)`（多吐的字串首段與模組相同 ⇒ 無影響），
            #      **另外兩個是 `startswith(...) or <子字串> in _m`** ⇒ **會被符號名誤觸發**。
            #
            #    **已量到的誤紅形狀（三序一致；`180fb93` 上皆為綠 ⇒ 這些偽陽性是
            #    「同時吐兩個」這個改動新引入的）**。
            #    ⚠️ **量測形態要講清楚，否則照抄會得到相反的結論**：下列 import
            #    **是放在一個「函式內、永不被呼叫」的 lazy import 裡量的**
            #    （`def _qa_never_called(): from services.batch import ...`）——
            #    這樣模組載入時不會真的去 import，pytest 回 **rc=1（測試真的紅）**。
            #    **若照抄成模組頂層 import，會得到 rc=4（collection error）**，
            #    那是**壞掉的突變、不是守衛的結果**（2026-09-06 兩種形態各實測一次）。
            #    這五個模組多數**並不存在**（`services/batch.py` 等），
            #    lazy import 不需要它們存在 —— **AST 掃描看的是原始碼，不是能不能 import**。
            #      `from services.fund_service import single_fund_metrics`  → 命中 "single_fund"
            #      `from services.batch import batch_analysis_runner`       → 命中 "batch_analysis"
            #      `from services.research import fund_research_helper`     → 命中 "fund_research"
            #      `from services.perf import portfolio_perf_summary`       → 命中 "portfolio_perf"
            #      `from services.health import fund_grp_health_score`      → 命中 "fund_grp_health"
            #    這些 import **本來就合法**（同檔另一條測試只禁 repositories/infra/網路函式庫，
            #    `services/**` 是允許的），現況只是**還沒有人這樣寫**，屬**潛伏**的誤紅。
            #
            #    ⛔ **不要為了消掉誤紅而把這裡收窄** —— 「兩個都要吐」的理由仍然成立
            #    （`from ui import tab3_portfolio` 是同層 import 最自然的寫法，只吐
            #    `_n.module` 會得到 "ui"、被 `startswith("ui.tab")` 靜靜放過）。
            #    ⚠️ ~~**真要修，該動的是那兩個子字串消費端**（讓它們只看模組清單）~~
            #    → **2026-09-06 更正：這個方向被實測推翻，不要照做**（有意識的更正，不是漏刪）。
            #    「只看模組清單」會**重開剛關掉的洞**：`ui/helpers/fund_research/` 是
            #    **真實存在的套件**，`from ui.helpers import fund_research` 在
            #    只看模組清單時是 `["ui.helpers"]` → **綠（漏放）**；
            #    同時吐兩個才是 `["ui.helpers", "ui.helpers.fund_research"]` → **紅**。
            #    **正確方向：讓 `_imported_modules` 回傳結構化的 `(module, symbol)`，
            #    由消費端各自選比對哪一半** —— 兩邊的分辨能力都保住，也不必碰檔案系統。
            #    超出本批邊界，**已登記待裁決**。
            #    **本函式的回傳值自此不是一份「真的 import 到的模組」清單，不要拿去做別的用途。**
            _mods.append(_n.module)
            _mods.extend(f"{_n.module}.{_a.name}" for _a in _n.names)
    return _mods


def test_the_page_never_reaches_into_the_data_layer():
    """客戶方針第 2 條：資料只走 `services/**`，**不碰** `repositories` / `infra` / 網路函式庫。

    ⚠️ 本批連 `services/**` 都沒有呼叫（骨架階段沒有東西要算）——
    但這條**現在就要在**，因為下一批填內容時它才是真正在守的那道線。
    ⚠️ **③ 特別容易犯**：搜尋在 `services/**` **沒有入口**（實測），
    現行實作住在 L1 `repositories.fund.tdcc_search_fund`。
    「反正 `EX-PASSTHRU-1` 有登記」**不是**在這裡 import 它的理由 ——
    那條例外的升級觸發條件就是「出現第二個 UI caller」，要總管裁決。
    """
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.split(".")[0] in ("repositories", "infra", "requests", "httpx",
                                    "yfinance", "gspread", "urllib", "bs4",
                                    "feedparser")]
    assert not _bad, (
        "本頁 import 了資料層 / 網路函式庫：" + ", ".join(_bad)
        + "\n客戶方針第 2 條：UI 只讀對接既有 Service，取不到就誠實灰態，**不反向修底層**。")


def test_the_page_does_not_delegate_to_the_old_tabs():
    """⛔ 不 import 線框「從哪裡搬來」列的那三個舊頁。

    它們會在五頁驗收完成後**整批拔除**，每一條委派都是一處會斷頭。
    ⚠️ ① 留了一條對 `ui/tab1_macro_midcycle.py` 的委派並就地登記
    「有效期到舊 tab 整批拔除為止」—— **本頁一條都沒有，而且要維持這樣。**
    """
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.startswith("ui.tab") or "fund_research" in _m
            or "batch_analysis" in _m or "single_fund" in _m]
    assert not _bad, (
        "本頁委派了舊 ③ 的來源分頁：" + ", ".join(_bad)
        + "\n舊實作會被整批拔除；本頁一律自己畫完。")


def test_the_page_does_not_assume_i_already_hold_these_funds():
    """線框 Tab 03 畫底線的那半句：**這裡的基金不預設我有持有**。

    ⚠️ 這條是**反向**規則（守「不要有」而不是「要有」），因為它擋的是一種
    看起來很貼心的退化：順手讀 `portfolio_funds`，在結果卡上標「你已持有」。
    那會把 ② 持倉體檢的職責搬進 ③，而線框把「我持有部位的健康度」
    明列在 Tab 03 的「這裡不放什麼」。
    """
    _bad = [f"第 {_n.lineno} 行 {_n.value!r}"
            for _n in _live_strings(_tree()) if "portfolio_funds" in _n.value]
    assert not _bad, (
        "本頁讀了組合持股的 session 契約：\n  " + "\n  ".join(_bad)
        + "\n線框 Tab 03：「這裡的基金**不預設我有持有**」。"
          "要標示持有狀態是 ② 的職責，不是這裡的。")


# ══════════════════════════════════════════════════════════════════
# 深度區：一次取數、六格共用、缺值不生數字
#
# ⚠️ **本節的每一條都寫「機制」，不寫「某一顆突變會紅」。**
#    「拿掉 X 這一行會轉紅」是一次觀察；下一個人換個寫法犯同一個錯，
#    那條斷言照樣綠。所以下面一律**逐指標／逐格參數化**，
#    讓「所有同類的錯」都在射程內，而不是其中一個示範。
# ══════════════════════════════════════════════════════════════════

def test_the_deep_dive_fetches_exactly_once():
    """六格由**一次** L2 呼叫供給 —— AST 數 `auto_fetch_moneydj(...)` 的呼叫點。

    ## 機制（為什麼是「恰好 1 個」而不是「至少 1 個」）

    每多一個呼叫點就是**多一次網路往返**；更糟的是六格會拿到**不同時間點**的快照
    （L1 的 `@_ttl_cache` 只擋重複的 HTTP，`finalize_fund_metrics` 每次都重跑），
    於是畫面上可能出現「NAV 是這一秒的、持股是上一分鐘的」而**沒有任何跡象**。

    ⚠️ **AST 不是 grep**：本檔的 docstring 就寫了好幾次 `auto_fetch_moneydj`
    這個字，字串比對會把它們一起算進去。
    ⛔ 這條看不到的：`getattr(mod, "auto_fetch_moneydj")()` 這種間接呼叫，
    以及**別的模組**替本頁去呼叫（本檔只掃這一個檔案）。**登記，不宣稱涵蓋。**
    """
    _calls = [_n for _n in ast.walk(_tree())
              if isinstance(_n, ast.Call)
              and (getattr(_n.func, "id", None) == "auto_fetch_moneydj"
                   or getattr(_n.func, "attr", None) == "auto_fetch_moneydj")]
    assert len(_calls) == 1, (
        f"本頁對 `auto_fetch_moneydj()` 有 {len(_calls)} 個呼叫點（應為 1）："
        + ", ".join(f"第 {_c.lineno} 行" for _c in _calls)
        + "\n六格共用同一次取數；多一個呼叫點 = 多一次往返 + 六格可能不同步。")
    # 渲染路徑上也真的只呼叫一次（AST 數的是「寫了幾處」，這裡數「跑了幾次」）。
    _fetches = [_p for _p in _render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_RICH_RESULT())
                if _p.startswith("[fetch] ")]
    assert len(_fetches) == 1, (
        f"一次渲染實際呼叫了 {len(_fetches)} 次取數：{_fetches}")


@pytest.mark.parametrize("key,label,unit", RISK_METRICS)
def test_a_missing_risk_metric_never_becomes_a_number(key: str, label: str, unit: str):
    """`metrics[<指標>] is None` → **那個指標不得出現任何數字**，且要說出自己的原因。

    ## 機制（三件事一起驗，缺一都能被繞過）

    1. **它自己的哨兵值不得出現** —— 擋「其實有值卻說沒有」以外的反向錯誤；
    2. **不得出現 `<標籤> <數字>` 的形狀** —— 這才是真正在擋的東西：
       `metrics.get(k) or 0` / `or 0.0` / 沿用上一個指標的值 / 填一個「保守估計」，
       全部會在這個形狀上現形；
    3. **其餘四個指標的哨兵必須還在** —— 擋「乾脆整格不畫」這種假修法
       （把一格藏起來，前兩條都會通過）。

    ⚠️ **逐指標參數化**，不是挑一個示範：`sharpe` 的缺值原因鍵是
    `self_calc_reason`、其餘三個是 `reason`、`std_1y` **在 `risk_metric_meta`
    裡根本沒有條目**（實測，見被測檔模組 docstring 第 4 點）——
    只驗其中一個，另外四條路完全沒有守到。
    """
    _metrics = {**RISK_SENTINELS, key: None,
                "risk_metric_meta": {key: {"reason": f"哨兵原因：{label} 樣本不足"}}}
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                             result=_RICH_RESULT(metrics=_metrics)))
    _body = "\n".join(_seg.get(DEEP_DIVE_CARDS[2], []))
    assert _body.strip(), f"風險指標那一格不見了（{label}）。"

    _own = f"{RISK_SENTINELS[key]:,.2f}"
    assert _own not in _body, (
        f"`metrics[{key!r}]` 是 None，畫面上卻出現了它的哨兵值 {_own}：\n{_body}")
    _leak = re.search(re.escape(label) + r"\s*[-+]?\d", _body)
    assert _leak is None, (
        f"`{label}` 沒有值，畫面上卻出現「{_leak.group(0)}」——"
        "那是憑空生出來的數字（`or 0` / 沿用別的指標 / 自己估一個）。\n" + _body)
    assert f"哨兵原因：{label}" in _body, (
        f"`{label}` 缺值卻沒有說出**它自己的**原因 —— "
        "八格共用一句話會讓「樣本不足」和「來源掛掉」長得一模一樣。\n" + _body)
    _others = [f"{_v:,.2f}" for _k, _v in RISK_SENTINELS.items() if _k != key]
    _gone = [_o for _o in _others if _o not in _body]
    assert not _gone, (
        f"拿掉 `{key}` 之後，其他指標的值也一起消失了：{_gone} —— "
        "整格藏起來不算誠實降級，那是把有的資料也丟掉。\n" + _body)


@pytest.mark.parametrize("key,label", PERF_PERIODS)
def test_a_missing_performance_period_is_named_not_zeroed(key: str, label: str):
    """某個期別沒有值 → **列出它的名字，不得補一個數字**。

    機制同上一條：`perf.get("3Y") or 0` 會讓「近三年沒資料」變成「近三年 0%」，
    而 0% 是一個**看起來完全合理**的報酬率 —— 使用者不可能看出它是編的（§1）。
    """
    _perf = {**PERF_SENTINELS}
    _perf.pop(key)
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_RICH_RESULT(perf=_perf)))
    _body = "\n".join(_seg.get(DEEP_DIVE_CARDS[1], []))
    _own = f"{PERF_SENTINELS[key]:,.2f}"
    assert _own not in _body, f"`perf[{key!r}]` 已拿掉，畫面上卻仍有 {_own}：\n{_body}"
    assert re.search(re.escape(label) + r"\s*[-+]?\d", _body) is None, (
        f"「{label}」沒有值，畫面上卻給了它一個數字：\n{_body}")
    assert label in _body, (
        f"「{label}」缺值時應**列出名字**（讓使用者知道少了哪一段），"
        f"不得整個消失：\n{_body}")


def test_a_total_failure_shows_the_source_trace_and_never_paints_red():
    """取數全敗 → **灰態 ＋ 逐源證據**；畫面上**不得**出現系統紅燈。

    ## 機制（總管 2026-09-06 裁決的可執行版本）

    `auto_fetch_moneydj` 對「代碼打錯」與「來源全掛」**回傳完全一樣的 failed**
    （本組實測：兩者都走同一條 `_attempts` 路徑，`error` 是「查無資料」
    「所有平台均無回應」這種泛稱）。所以：
    - 塗紅 → 對打錯代碼的人謊稱系統故障；
    - 寫「查無此檔」→ 對來源掛掉的人謊稱這檔不存在。
    **兩種都是編的**，因此本條同時釘住「不准紅」與「必須攤開證據」兩半。

    ⚠️ **紅燈的判準是 `state_card(state=STATE_ERROR)` 走的 `system_error()`，
    不是「畫面上有沒有紅色」** —— 顏色驗不到，入口驗得到。
    `system_error` 的第一個 render 是 `friendly_error(level="error")`，
    在 recorder 底下會錄成 `[error] …`。
    """
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_BLANK_RESULT())
    _all = _text(_parts)
    assert "[error]" not in _all, (
        "取數全敗被畫成了系統紅燈 —— 但 L2 分不出「代碼打錯」與「來源當下不可用」，"
        "塗紅等於對打錯代碼的使用者謊稱系統故障。\n" + _all)
    assert "查無此檔" not in _all, (
        "畫面上宣告了「查無此檔」—— 同一份 failed 也可能只是來源當下不可用，"
        "這句話對後者是假的。")
    # 逐源證據必須真的出現在來源標註那一格
    _seg = _segments(_parts)
    _prov = "\n".join(_seg.get(DEEP_DIVE_PROVENANCE, []))
    _rows = _trace_rows(_BLANK_RESULT())
    assert _rows, "fixture 自己就沒有 source_trace，這條測試會空轉。"
    assert "[dataframe]" in _prov, (
        f"全敗時「{DEEP_DIVE_PROVENANCE}」沒有攤開逐源軌跡 —— "
        "那是使用者唯一能自己判斷「打錯還是掛掉」的依據。\n" + _prov)
    # 三個 grey 卡片必須說出「兩種可能」而不是二選一
    _nav = "\n".join(_seg.get(DEEP_DIVE_CARDS[0], []))
    # ⚠️ **2026-09-08 只換了錨點字，規則一個字沒放寬**（狀態變更，不是漏刪）：
    #    上一版的錨點是 ~~「不是本頁查得到的基金代碼」~~，而 `_BLAME_FREE` 那半句
    #    在搜尋入口接上之後**變成假的**（「本頁只查得到代碼」不再為真），
    #    被測檔已就地改寫。本條改抓兩個**只屬於其中一半**的詞，
    #    並**多加一條**：那句話必須自陳「這兩種分不出來」——
    #    只給兩種可能、卻讓使用者以為我們知道是哪一種，同樣是編的。
    assert "認得的基金代碼" in _nav and "當下不可用" in _nav, (
        "全敗時的說明沒有同時給出兩種可能 —— 挑一種講就是編的。\n" + _nav)
    assert "分不出來" in _nav, (
        "全敗時的說明給了兩種可能，卻沒有說明「本頁分不出是哪一種」——\n"
        "使用者會以為我們心裡有數只是沒講。\n" + _nav)
    # ⚠️ 2026-09-06 獨立稽核 應修 1：**不得把責任推給使用者**。
    #    舊文案「可能是代碼打錯」對一個打對了 secId 的人是假的 ——
    #    不能用的是本頁自己宣告的輸入格式，不是他的手指。
    assert "打錯" not in _all, (
        "失敗文案把責任推給使用者（「打錯」）—— 但 secId 與名稱查不到是"
        "**本頁自己的限制**，help 已據實改口，這裡不得再指著使用者。\n" + _all)


def test_a_real_exception_stays_a_real_exception():
    """取數**真的拋例外** → 走 `safe_section()` 的紅框；**不得**被降級成灰態。

    ## 機制

    `auto_fetch_moneydj` 的 **URL 直傳分支沒有 try/except**（本組實測：patch 掉
    下游使其拋 `RuntimeError`，URL 分支原封拋出、純代碼分支才回 `{'error': …}`）。
    那條路徑是**真的系統故障**，必須紅。

    ⛔ 反向也要擋（下一條）：**不得為了塗紅而自己造一個例外**。
    """
    _all = _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                         raiser=RuntimeError("哨兵：上游炸了")))
    assert "[error]" in _all, (
        "取數拋出的真例外沒有被畫成紅燈 —— 它被吞了或被降級成灰態（§1）。\n" + _all)
    assert BLOCK_DEEP in _all, (
        f"紅框沒有標明是「{BLOCK_DEEP}」出事，使用者不知道哪一塊壞了。\n" + _all)
    # 其餘區塊照常渲染（區塊級隔離，不是整頁陪葬）
    assert BLOCK_BATCH in _all, "深度區炸掉不該帶走批次分析那一塊。"


def test_the_page_never_fabricates_an_exception_to_paint_red():
    """⛔ 本頁**不得**自己 `raise` 一個由 `result["error"]` / 字串組出來的例外。

    ## 機制

    `state_card(state=STATE_ERROR)` 對非 `BaseException` 直接 `TypeError`，
    所以「想塗紅」最順手的寫法就是 `raise Exception(result["error"])` ——
    那是**捏造的故障**：手上根本沒有例外，只有一句上游的錯誤字串。

    本條掃所有 `raise`：**只准 raise 型別錯誤這種「契約被破壞」的真斷言**，
    不准把 `result[...]` / `.get(...)` 的內容包成例外丟出去。
    """
    _bad: list[str] = []
    for _n in ast.walk(_tree()):
        if not isinstance(_n, ast.Raise) or _n.exc is None:
            continue
        _txt = ast.unparse(_n)
        if "error" in _txt or "source_trace" in _txt:
            _bad.append(f"第 {_n.lineno} 行 {_txt[:90]}")
    assert not _bad, (
        "本頁把上游的錯誤字串包成例外丟出去，好讓它被畫成紅框：\n  "
        + "\n  ".join(_bad)
        + "\n手上沒有例外就不是系統故障 —— 那一格該是灰的，技術細節交給"
          " `safe_section()` 去接真的例外。")


def test_a_grey_reason_is_never_an_exception_object():
    """⛔ `result["error"]` 不得出現在畫面上的任何一個字裡。

    ## ⚠️ 本條原本是**純 AST**，突變實測後改寫 —— 記下來免得有人改回去

    初版只掃 `not_ready(...)` / `empty_state(...)` 的**直接呼叫引數**。
    突變 **M9**（把 `result["error"]` 當成卡片 `note` 傳給 `_risk_card()`，
    再由 `state_card()` 轉交 `not_ready()`）→ **全綠**。
    也就是說：它擋得住最笨的那個寫法，擋不住本檔**實際在用**的那個寫法
    （卡片一律走 dict → `render_cards()` → `state_card()`）。
    **拔不紅的守衛是裝飾品**，故改為「**執行期哨兵**：把 `error` 換成一個
    絕不會自然出現的字串，然後要求它在整份渲染紀錄裡一次都不出現」——
    這樣**不管經過幾層轉交**都攔得到。

    ## 兩個獨立的理由，都不是理論

    1. **型別**：`not_ready()` / `empty_state()` 對 `BaseException` **直接 `TypeError`**
       （就地防呆），所以這種寫法在 production 是一顆會炸的地雷。
    2. **版面注入**：`empty_state()` 的 `title` 走 **`unsafe_allow_html=True`**
       （實測其實作）。上游是 HTML 爬蟲，`error` 可能含 `<` `>`。

    ## 這條**允許**什麼（分清楚，否則會被讀成「所有上游文字都不准顯示」）

    `source_trace[i]["error"]`（逐源診斷，如「查無資料」）**照樣要顯示** ——
    那是使用者判斷「代碼打錯 vs 來源掛掉」的唯一依據，而且它走
    `st.caption` / `st.dataframe`（兩者都不開 `unsafe_allow_html`）。
    本條釘的是**頂層那個 `result["error"]`**，它可能是 `f"{type(e).__name__}: {e}"`
    這種原始例外字面（見 `services/moneydj_fetcher.py` 的 `_attempts` 分支）。
    """
    _poison = "<b>哨兵毒藥XYZ</b>"
    for _base in (_BLANK_RESULT(), _RICH_RESULT()):
        _base["error"] = _poison
        _all = _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_base))
        assert _poison not in _all, (
            f'`result["error"]` 的內容被畫到畫面上了（狀態={_base.get("status")!r}）：\n'
            + _all)
        assert "哨兵毒藥XYZ" not in _all, (
            "錯誤字串經過改寫後仍然流到畫面上 —— 逃逸的是內容不是標籤。")

    # AST 那一半保留：直接呼叫的寫法要在**讀 code 時**就看得出來，
    # 不必等到有人跑測試（兩層一起才叫縱深，不是重複）。
    _bad: list[str] = []
    for _n in ast.walk(_tree()):
        if not (isinstance(_n, ast.Call)
                and getattr(_n.func, "id", None) in ("not_ready", "empty_state")):
            continue
        for _a in list(_n.args) + [_k.value for _k in _n.keywords]:
            _txt = ast.unparse(_a)
            if ("error" in _txt or "exc" in _txt) and "empty_" not in _txt:
                _bad.append(f"第 {_n.lineno} 行 {ast.unparse(_n.func)}(… {_txt[:60]} …)")
    assert not _bad, (
        "灰態的文案吃到了錯誤字串 / 例外物件：\n  " + "\n  ".join(_bad))


def test_the_empty_state_title_never_carries_upstream_text():
    """⛔ `empty_state()` 的**標題**只准是本檔自己的字面值。

    ## 機制（這一條與上一條守的不是同一件事）

    上一條守「錯誤字串不要外流」；本條守的是**注入面本身**：
    `empty_state()` 的 title 是本頁唯一走 **`unsafe_allow_html=True`** 的參數
    （實測 `ui/helpers/ia/empty_state.py`）。**只要那個位置永遠是常數，
    這個注入面就結構性地不存在** —— 不必逐一去猜哪個上游欄位可能含 `<`。

    ⚠️ `wide_table(empty_title=…)` 也算，它會原封轉交給 `empty_state()`。
    ⚠️ 允許 f-string，但**內插的每一段都必須是本檔的模組層常數**
    （`DEEP_DIVE_TABLES[0]` 這種），不得是 `result` / 參數 / 區域變數。

    ## ⚠️ 2026-09-07：白名單改成**推導**的（收緊，不是放寬）

    ~~舊寫法是一份**手寫的七個名字**清單。~~ 它有兩個問題，批次接上真取數時同時發作：
      1. **會過期** —— 本頁新增一個模組層標題常數（`_BATCH_EMPTY_TITLE`）就誤紅，
         而修法會被推向「把名字加進清單」，那是**每次都要有人記得**的維護；
      2. **它其實沒有驗到「那個名字真的是常數」** —— 清單裡的名字若哪天被改成
         `BLOCK_BATCH = _fetch_title()`，這條照樣綠。

    **現行判準**：允許的名字 ＝ **本頁模組層、綁定到一個 `ast.literal_eval` 得出來的
    字面值**（字串或字串 tuple）的那些。它自己會長大，而且**驗的是值的性質不是名字**
    —— 一個名字只要改成執行期算出來的東西，當場就掉出集合、本條轉紅。
    ⚠️ 舊的七個名字改成**下限斷言**（見下）：推導壞掉時會當場看見，不會靜靜放行。
    """
    _tree_mod = _tree()
    _allowed = set()
    for _stmt in _tree_mod.body:
        if isinstance(_stmt, ast.Assign):
            _targets, _value = _stmt.targets, _stmt.value
        elif isinstance(_stmt, ast.AnnAssign) and _stmt.value is not None:
            _targets, _value = [_stmt.target], _stmt.value
        else:
            continue
        try:
            _lit = ast.literal_eval(_value)
        except Exception:
            continue
        if not isinstance(_lit, (str, tuple)):
            continue
        if isinstance(_lit, tuple) and not all(isinstance(_x, str) for _x in _lit):
            continue
        _allowed.update(_t.id for _t in _targets if isinstance(_t, ast.Name))
    # ⛔ **下限**：推導若壞掉（例如有人把常數改成執行期算的），本條要當場說出來，
    #    而不是變成一個空集合把所有東西都判成違規（那會是**方向相反**的假紅）。
    _floor = {"DEEP_DIVE_CARDS", "DEEP_DIVE_TABLES", "DEEP_DIVE_PROVENANCE",
              "BLOCK_RESULTS", "BLOCK_DEEP", "BLOCK_BATCH", "BLOCK_FORM"}
    assert _floor <= _allowed, (
        "推導出來的『模組層字面值常數』集合少了原本就該在裡面的名字："
        f"{sorted(_floor - _allowed)} —— 它們被改成執行期算出來的東西了嗎？"
        "若是，那正是本條要擋的事，請改回字面值；若是推導邏輯壞了，請修推導。")
    _bad: list[str] = []
    for _n in ast.walk(_tree_mod):
        if not isinstance(_n, ast.Call):
            continue
        _fn = getattr(_n.func, "id", None)
        if _fn not in ("empty_state", "wide_table"):
            continue
        _title = None
        if _fn == "empty_state" and _n.args:
            _title = _n.args[0]
        for _k in _n.keywords:
            if _k.arg in ("title", "empty_title"):
                _title = _k.value
        if _title is None:
            continue
        for _sub in ast.walk(_title):
            if isinstance(_sub, ast.Name) and _sub.id not in _allowed:
                _bad.append(f"第 {_n.lineno} 行 {_fn}(…) 標題內插了 `{_sub.id}`")
            if isinstance(_sub, ast.Attribute):
                _bad.append(f"第 {_n.lineno} 行 {_fn}(…) 標題內插了 "
                            f"`{ast.unparse(_sub)[:40]}`")
    assert not _bad, (
        "空狀態標題吃到了非常數的東西：\n  " + "\n  ".join(_bad)
        + "\n那個位置走 `unsafe_allow_html=True`，上游是 HTML 爬蟲 —— "
          "任何含 `<` 的字串都會直接打壞版面，而且畫面上沒有任何跡象。")


def test_the_page_has_no_exception_handler_of_its_own():
    """本頁**只准**有一個 `except`，而且它不准印任何東西。

    ## 為什麼是「幾乎不准有」而不是「不准吞」

    區塊級隔離已經由 `safe_section()` 提供（它走 `system_error()` ＋ traceback）。
    本頁自己再接一層，只會有兩種結果：**吞掉**（違 §1），
    或**用錯顏色重印一次**（踩 `tests/test_render_state_color_separation.py`
    的方向 A ratchet —— 那條規則掃 `ui/**` 全部，本檔在射程內）。

    ⚠️ **本條的門檻 2026-09-06 由「≤1」收成「0」**（本組自己拆掉了那一個）：
    初稿在 `_nav_facts()` 有一個 `except`，把「序列的索引讀不出來」收斂成
    `return None` → 呼叫端走灰態、文案是「這次沒有帶回淨值序列」——
    **但序列帶回來了，只是讀不出來，那句話是假的。**
    索引不是時間軸 ＝ 上游契約被破壞（`CLAUDE.md §3.1`），§1 要求炸掉。
    **一個 `except` 都沒有，這條規則才不必再判斷「這個 handler 乖不乖」。**
    """
    _handlers = [_n for _n in ast.walk(_tree()) if isinstance(_n, ast.ExceptHandler)]
    assert not _handlers, (
        f"本頁有 {len(_handlers)} 個 except（應為 0） —— 區塊級隔離已由 `safe_section()` 提供，"
        "自己再接一層不是吞掉就是用錯顏色重印一次。\n  "
        + "\n  ".join(f"第 {_h.lineno} 行" for _h in _handlers))
    for _h in _handlers:
        _printed = [ast.unparse(_c)[:60] for _c in ast.walk(_h)
                    if isinstance(_c, ast.Call)
                    and (getattr(_c.func, "attr", None) or "") in _TEXT_APIS]
        assert not _printed, (
            f"第 {_h.lineno} 行的 except 裡印了東西：{_printed} —— "
            "在 handler 裡印例外是「把系統故障畫成別的顏色」，"
            "而且會撞上 `test_render_state_color_separation.py` 的方向 A ratchet。")


@pytest.mark.parametrize("unit", DEEP_UNITS)
def test_a_deep_unit_that_has_data_shows_it_and_one_that_has_none_stays_grey(unit: str):
    """**逐格**：有料就把料畫出來、沒料就灰 —— 兩個方向同時驗。

    ⚠️ 這條取代了骨架時期
    :func:`test_every_grey_unit_is_grey_until_its_content_lands` 對深度區那六格的涵蓋。
    **它不是「有東西就好」**：正向要求那一格**真的出現自己的哨兵字**，
    反向要求全敗時它**不得**印出任何哨兵字。
    """
    _need = {
        DEEP_DIVE_CARDS[0]: "59.99",                    # 最新淨值
        DEEP_DIVE_CARDS[1]: f"{PERF_SENTINELS['1Y']:,.2f}",
        DEEP_DIVE_CARDS[2]: f"{RISK_SENTINELS['sharpe']:,.2f}",
        DEEP_DIVE_TABLES[0]: "[dataframe]",
        DEEP_DIVE_TABLES[1]: "[dataframe]",
        DEEP_DIVE_PROVENANCE: "[dataframe]",
    }[unit]
    _rich = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_RICH_RESULT()))
    _body = "\n".join(_rich.get(unit, []))
    assert _body.strip(), f"有料的時候「{unit}」這一格不見了。現有單位：{list(_rich)}"
    assert _need in _body, (
        f"「{unit}」有資料卻沒有把它畫出來（找不到 {_need!r}）：\n{_body}")

    _blank = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_BLANK_RESULT()))
    _bbody = "\n".join(_blank.get(unit, []))
    assert _bbody.strip(), f"沒料的時候「{unit}」這一格整個消失了 —— 應該留灰態。"
    if unit != DEEP_DIVE_PROVENANCE:      # 來源標註在全敗時要攤開證據，見 GREY_ON_BLANK
        assert NOT_READY_MARK in _bbody, (
            f"「{unit}」沒料卻不是灰的：\n{_bbody}")
        assert _need not in _bbody, (
            f"「{unit}」沒料卻印出了 {_need!r} —— 那是憑空生出來的：\n{_bbody}")


def test_the_page_only_talks_to_the_service_layer():
    """本頁的 import 清單：**不得**碰資料層 / 網路函式庫，也不得委派舊三頁。

    ⚠️ **AST 掃 import 節點，不是字串 grep** —— 本檔與被測檔的 docstring 都反覆
    提到 `repositories.fund.tdcc_search_fund`、`fund_research`、`single_fund`
    這些名字（那是在說明「為什麼不能用」），grep 會把說明文字當成違規。
    ⚠️ 本條與既有的
    :func:`test_the_page_never_reaches_into_the_data_layer` /
    :func:`test_the_page_does_not_delegate_to_the_old_tabs` **是同一組規則的合驗**，
    多一條的價值在於：它同時釘住「**該有的那一個** L2 入口真的在」——
    只有反向禁令的話，把整段取數刪掉也會全綠。
    """
    _mods = _imported_modules(_tree())
    _bad_layer = [_m for _m in _mods
                  if _m.split(".")[0] in ("repositories", "infra", "requests",
                                          "httpx", "yfinance", "gspread",
                                          "urllib", "bs4", "feedparser")]
    assert not _bad_layer, f"本頁 import 了資料層 / 網路函式庫：{_bad_layer}"
    _bad_old = [_m for _m in _mods
                if _m.startswith("ui.tab") or "fund_research" in _m
                or "batch_analysis" in _m or "single_fund" in _m]
    assert not _bad_old, f"本頁委派了舊 ③ 的來源分頁：{_bad_old}"
    assert "services.moneydj_fetcher" in _mods, (
        "本頁沒有 import L2 取數入口 —— 只有反向禁令的話，"
        "把整段取數刪掉也會全綠，那是一份守不到東西的規則。")


def test_the_dividend_currency_is_reconciled_not_guessed():
    """配息幣別：**逐列一致才敢宣告**，不一致就明說不知道，**絕不挑一個**。

    委派 `shared.data_quality.reconcile_row_currencies`（本組實測
    `['TWD','USD'] → ''`、`['USD','USD'] → 'USD'`）。
    ⚠️ 這一格是**線框第三張示意卡在示範的處境**（「幣別未知／此來源未提供計價幣別」
    ＋ chip「不猜值」），所以它不是邊角，是線框點名要做對的地方。
    """
    _mixed = _RICH_RESULT()
    _mixed["dividends"][0]["currency"] = "TWD"          # 兩列幣別不一致
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_mixed))
    _body = "\n".join(_seg.get(DEEP_DIVE_TABLES[1], []))
    assert CCY_UNKNOWN in _body, (
        "逐列幣別不一致，畫面卻沒有標示幣別無法宣告：\n" + _body)
    # 純函式層再驗一次（渲染層可能被別的字串蒙混過去）
    assert _declared_currency(_dividend_rows(_mixed)) == "", (
        "`_declared_currency()` 對混幣別的配息挑了一個幣別出來 —— "
        "那正是 `reconcile_row_currencies` 的 docstring 明禁的事。")
    assert _declared_currency(_dividend_rows(_RICH_RESULT())) == "USD", (
        "逐列一致時反而不敢宣告幣別 —— 那會讓「不知道」與「知道」長得一樣。")


def test_missing_upstream_reason_is_admitted_not_invented():
    """上游**沒有**給缺值原因時，畫面要說「上游沒給」，**不准自己編一個**。

    ⚠️ 這條擋的是最容易被當成「貼心」的退化：缺 `reason` 就補一句
    「資料不足」——那是**我們猜的**，而使用者無從分辨它是上游說的還是我們編的。
    """
    _metrics = {_k: None for _k in RISK_SENTINELS}       # 五個全缺、且沒有任何 meta

    # (a) 純函式層：**每一個**缺值指標都要據實承認「上游沒給原因」。
    #     ⚠️ 這一半是本條真正在守的東西 —— 渲染層看不到它
    #     （`_risk_card()` 會在「每一條原因都是 NO_REASON」時改用區塊層級的
    #      處境描述，那是刻意的，見該函式）。只驗渲染層等於沒驗到這條規則。
    _shown, _missing = _risk_lines({"metrics": _metrics})
    assert not _shown, f"五個指標都是 None，卻有東西被當成有值：{_shown}"
    _invented = [_m for _m in _missing if not _m.endswith(NO_REASON)]
    assert not _invented, (
        "上游沒有給缺值原因，本頁卻自己編了一個：\n  " + "\n  ".join(_invented)
        + f"\n沒有原因就據實寫 {NO_REASON!r} —— 使用者無從分辨"
          "「上游說的」與「我們猜的」，猜的那一種比沒有更危險（§1）。")
    assert len(_missing) == len(RISK_METRICS), (
        f"缺值清單少了指標：{_missing} —— 缺一個就整個不提，等於靜默丟掉。")

    # (b) 渲染層：不得因此生出任何數字。
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                             result=_RICH_RESULT(metrics=_metrics)))
    _body = "\n".join(_seg.get(DEEP_DIVE_CARDS[2], []))
    assert NOT_READY_MARK in _body, "五個指標全缺卻不是灰態：\n" + _body
    for _key, _label, _unit in RISK_METRICS:
        assert re.search(re.escape(_label) + r"\s*[-+]?\d", _body) is None, (
            f"「{_label}」沒有值，畫面上卻出現了數字：\n{_body}")


@pytest.mark.parametrize("unit,ccy_field", [
    (DEEP_DIVE_CARDS[0], "currency"),        # NAV 卡：`result["currency"]`
    (DEEP_DIVE_TABLES[1], "dividends"),      # 配息表：逐列 `currency`
])
def test_an_unknown_currency_is_declared_unknown_not_filled_in(unit: str, ccy_field: str):
    """幣別取不到 → **明說不知道**，不得填一個 ISO 三碼上去。

    ## 這條是突變 **M18** 逼出來的，不是設計出來的

    上一輪把 `nav["currency"] or CCY_UNKNOWN` 改成 `nav["currency"] or "USD"`
    → **全套 55 條一條都沒紅**。也就是說：本檔當時**只守了配息那一格的幣別**
    （`test_the_dividend_currency_is_reconciled_not_guessed`），
    NAV 卡那一格的幣別**完全沒有守**，而它就印在最顯眼的位置（`st.metric` 的值旁邊）。

    ⚠️ **`"USD"` 是本 repo 反覆出現的死預設**（`repositories/fund/` 至少三處
    `.get("計價幣別", "USD")` / `result.get("currency", "USD")`，L1 自己的註解就寫著
    「v19.505:不矇 USD」是為了修這個病）。所以這不是假想的突變 ——
    **它是這份 codebase 已經犯過的那一種錯**，只是換到 UI 層再犯一次。

    ⚠️ 一個台幣基金被標成 USD，使用者看到的是「淨值 59.99 美元」——
    數字是真的、單位是編的，而畫面上沒有任何跡象（`CLAUDE.md §4.1` 量綱陷阱）。
    """
    _res = _RICH_RESULT()
    if ccy_field == "currency":
        _res["currency"] = ""                      # 上游沒給計價幣別
    else:
        for _d in _res["dividends"]:
            _d["currency"] = ""
    _body = "\n".join(_segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_res)).get(unit, []))
    assert _body.strip(), f"「{unit}」這一格不見了。"
    assert CCY_UNKNOWN in _body, (
        f"「{unit}」的幣別取不到，畫面卻沒有標示 {CCY_UNKNOWN!r}：\n{_body}")
    for _iso in ("USD", "TWD", "EUR", "JPY", "AUD"):
        assert _iso not in _body, (
            f"「{unit}」的幣別取不到，畫面上卻出現了 {_iso!r} —— "
            "那是憑空填上去的計價幣別。數字是真的、單位是編的，"
            "使用者看不出任何異狀（§4.1 量綱陷阱）。\n" + _body)


def test_holdings_keep_the_upstream_ranking_and_do_not_drop_weightless_rows():
    """持股表：**沒有權重照樣列、沒有名稱才跳過，而且排名用上游的原始位置**。

    ## 三個失效模式，一條各守一個

    1. **過濾掉沒有權重的持股** → 「前十大」悄悄變成「我算得出權重的那幾大」，
       使用者看到的排名不再是上游給的排名。
    2. **跳過之後重新編號** → 「上游第 2 檔沒有名字」這件事被抹掉，
       畫面上是一份看起來完整、實際上少一檔的前 N 大（§1：比缺資料更危險）。
    3. **權重缺值補 0** → 「沒揭露權重」與「權重是 0%」長得一樣。
    """
    _res = _RICH_RESULT()
    _res["holdings"]["top_holdings"] = [
        {"name": "哨兵持股甲", "sector": "科技", "pct": 91.11},
        {"name": "", "sector": "金融", "pct": 92.22},          # 無名 → 應跳過
        {"name": "哨兵持股丙", "sector": "能源", "pct": None},  # 無權重 → 應保留
    ]
    _rows = _holdings_rows(_res)
    _names = [_r[HOLDING_COLS[1]] for _r in _rows]
    assert _names == ["哨兵持股甲", "哨兵持股丙"], (
        f"無名列沒被跳過，或有權重的列被丟掉了：{_names}")
    assert [_r[HOLDING_COLS[0]] for _r in _rows] == [1, 3], (
        "排名被重新編號了 —— 上游第 2 檔沒有名字這件事因此被抹掉，"
        "畫面上會是一份看起來完整、實際上少一檔的前 N 大。"
        f"實際排名：{[_r[HOLDING_COLS[0]] for _r in _rows]}")
    _weightless = [_r for _r in _rows if _r[HOLDING_COLS[1]] == "哨兵持股丙"][0]
    assert _weightless[HOLDING_COLS[3]] == "", (
        f"沒有權重的持股被補了一個值 {_weightless[HOLDING_COLS[3]]!r} —— "
        "「沒揭露」與「是 0%」不是同一件事（§1）。")


# ══════════════════════════════════════════════════════════════════
# 2026-09-06 獨立稽核回修 —— 三項必修 ＋ 兩項應修
#
# ⚠️ **通則（本節存在的理由，比任何一條斷言重要）**：
#    **修完一個 bug，第一顆該試的突變就是「把那個修復拔掉」。**
#    上一輪的 24 顆突變對它們自己為真，但**沒有一顆是「拔掉我剛修好的東西」** ——
#    於是 `_has_anything()` 這個 fix（它的 docstring 自己寫「存在的唯一理由是
#    不要讓一句話跑到不屬於它的格子裡」）**零守衛**，稽核組三顆突變全部存活。
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("hollow,unit,keep", [
    # (把哪一格挖空, 該格單位名, 其餘哪一格必須仍有料 —— 證明「有料」這個前提成立)
    ("dividends", DEEP_DIVE_TABLES[1], DEEP_DIVE_CARDS[0]),
    ("holdings", DEEP_DIVE_TABLES[0], DEEP_DIVE_CARDS[0]),
    ("perf", DEEP_DIVE_CARDS[1], DEEP_DIVE_CARDS[0]),
    ("metrics", DEEP_DIVE_CARDS[2], DEEP_DIVE_CARDS[0]),
])
def test_the_all_sources_failed_note_never_leaks_into_a_unit_whose_neighbours_have_data(
        hollow: str, unit: str, keep: str):
    """⛔ 只有**一格都沒有**時才准講「N 個來源都沒有取到淨值」。

    ## 這條守的是 `_has_anything()`，而它上一輪**零守衛**（獨立稽核 必修 1）

    稽核組三顆突變**全部存活 58/58 × 3 序**：配息格 `empty_missing` 退回共用文案、
    持股格同樣退回、以及 **`_has_anything()` 整個改成 `return False`**
    （＝本組初稿的 bug 完整復辟）。

    **失效模式長這樣**（稽核組實測的畫面）：淨值 3 筆、績效有、持股有、**就是沒配息**
    → 配息格印出「這次取數沒有帶回任何淨值」，
    **而同一個畫面上 NAV 卡正印著「59.99 USD · 3 筆」**。
    兩句都是本頁印的，其中一句是假的。

    ## 判準：**指名道姓**，不是「有沒有灰態」

    只驗「這一格是灰的」擋不住任何東西（兩種文案都是灰的）。
    本條驗的是**那一格說的理由對不對** —— 全敗文案的特徵句不得出現在
    「鄰居有料」的畫面上，而且該格必須換上**它自己**的理由。
    """
    _res = _RICH_RESULT()
    _res[hollow] = {} if hollow in ("holdings", "perf", "metrics") else []
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_res))

    # 前提：鄰居真的有料（否則這條測試會空轉，稽核組要求的「排除突變沒生效」）
    _keep_body = "\n".join(_seg.get(keep, []))
    assert "59.99" in _keep_body, (
        f"前提不成立：挖空 {hollow!r} 之後鄰居「{keep}」也沒有料了，"
        f"本條會空轉。\n{_keep_body}")

    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"挖空 {hollow!r} 之後「{unit}」整格消失了。"
    assert NOT_READY_MARK in _body, f"「{unit}」沒料卻不是灰的：\n{_body}"
    for _leak in ("都沒有取到淨值", "沒有帶回任何淨值"):
        assert _leak not in _body, (
            f"「{unit}」沒料，卻印出了**全敗**才該講的話（{_leak!r}）——\n"
            f"但同一個畫面上「{keep}」正印著淨值。**那句話是假的。**\n"
            f"共用文案只准在「一格都沒有」時使用（見 `_has_anything()`）。\n{_body}")


def test_the_dividend_currency_never_contradicts_the_fund_currency():
    """⛔ 配息幣別與基金計價幣別不一致時，**不得宣告任何一個**（獨立稽核 必修 2）。

    ## 這是活的缺陷，不是突變 —— HEAD 未突變時就會發生

    稽核組實測畫面：

    ```
    NAV 走勢     [metric]  59.99 TWD
    配息紀錄     [caption] 2 筆 · 全部以 USD 計價
    ```

    成因在上游、**但本頁是第一個把它端上畫面的**：`_src_fundclear_div` 缺欄時
    逐列填 `"USD"` 死預設，而 `_ensure_currency` 已經為了同一個死預設修好了
    `result["currency"]` —— **只修了一半，本頁端出沒修的那一半，還加了一句
    斬釘截鐵的「全部以 USD 計價」。數字真、單位編（§4.1）。**

    ⛔ **答案不是「相信 `result` 那一邊」**：它只是**比較可信**，不是**確定對**。
    §1 的答案是**不宣稱**。
    """
    _res = _RICH_RESULT()
    _res["currency"] = "TWD"                     # 基金計價幣別（已被 _ensure_currency 修正）
    for _d in _res["dividends"]:
        _d["currency"] = "USD"                   # 逐列死預設
    _all = _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_res))
    assert "全部以 USD 計價" not in _all and "全部以 TWD 計價" not in _all, (
        "兩邊幣別不一致，本頁卻還是挑了一個宣告：\n" + _all)
    assert "資料疑義" in _all, (
        "幣別矛盾沒有被標成資料疑義 —— 使用者看不出這一頁自己在打架。\n" + _all)

    # 反向：兩邊一致時**要**敢宣告（否則「不知道」與「知道」又長得一樣了）
    _ok = _RICH_RESULT()                          # currency=USD、逐列 USD
    assert "全部以 USD 計價" in _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_ok)), (
        "兩邊都說 USD，本頁卻不敢宣告 —— 那會讓「不知道」與「知道」長得一樣。")


def test_a_broken_series_index_is_red_not_grey():
    """壞掉的索引 ＝ 上游契約破了 → **紅框**，不得被吞成灰態（獨立稽核 必修 3）。

    ## 為什麼純 AST 的「0 個 except」不夠

    稽核組用 `contextlib.suppress` 把本組**自陳拆掉**的那個「會說謊的 except」
    **原樣復辟**：零 `except` 節點、**58 passed × 3 序**。畫面：

    ```
    HEAD → NAV 格空，紅框 + traceback                     ← 正確（§1）
    突變 → ⬜ 這次沒有帶回淨值序列，上游也沒有說明原因      ← 序列明明帶回來了，3 筆
    ```

    **形狀檢查擋不住換一個形狀。** 本條改驗**行為**；
    純 AST 那條（`test_the_page_has_no_exception_handler_of_its_own`）
    **留著當第二層**，不是被取代。

    ⚠️ fixture 刻意讓 `min` / `max` **存在但會拋**（見 :class:`_ExplodingIndex`）——
    稽核組有一顆突變就是因為「方法存在、只是會拋」而其實沒生效，它自己撤回了。
    """
    _res = _RICH_RESULT(series=_broken_series())
    _all = _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_res))
    assert "[error]" in _all, (
        "索引壞掉（上游契約被破壞）被畫成灰態或被吞掉了 —— "
        "序列**有**帶回來，只是讀不出來，說「沒有帶回序列」是假的（§1 要求炸掉）。\n"
        + _all)
    assert "哨兵：索引不是時間軸" in _all, (
        "紅框沒有帶出真正的例外訊息 —— 那就只是一個紅色的猜測。\n" + _all)
    assert "這次沒有帶回淨值序列" not in _all, (
        "壞索引被說成「沒有帶回淨值序列」—— 序列帶回來了，那句話是假的。\n" + _all)


def test_the_failed_source_count_excludes_synthetic_markers():
    """「N 個來源」只能數**真的來源**（獨立稽核 應修 2）。

    `nav_series` 是 `finalize_fund_metrics` 追加的**合成標記**（意思是「沒有淨值序列」），
    不是一個被試過的來源。畫面曾印「這個代碼在 **3** 個來源都沒有取到淨值」，
    **實際只試了 2 個** —— 而 `_nav_reason()` 正是靠這個名字把它挑出來當缺值原因用。
    **同一個東西一邊當標記、一邊當來源數**，那個數字是編出來的證據。

    ⚠️ 本條也守**去重**：同一個來源被 append 兩次不得算成兩個。
    """
    assert TRACE_NAV_SERIES in SYNTHETIC_TRACE_SOURCES, (
        "`nav_series` 沒有被列為合成標記 —— 它會被算進來源數。")
    _blank = _BLANK_RESULT()
    assert _failed_source_count(_blank) == 2, (
        "來源數把合成標記也算進去了。fixture 的 source_trace 是 "
        "bank_platform（失敗）／morningstar（失敗）／nav_series（合成標記）"
        f"→ 應為 2，實得 {_failed_source_count(_blank)}。")
    assert "在 2 個來源" in _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_blank)), (
        "畫面上的來源數與 `_failed_source_count()` 不一致。")
    # 去重
    _dupe = _BLANK_RESULT()
    _dupe["source_trace"].append(
        {"source": "bank_platform", "success": False, "error": "短窗重試也失敗"})
    assert _failed_source_count(_dupe) == 2, (
        "同一個來源被追加兩次就被算成兩個 —— 那同樣是虛報。")
    # 合成標記全員：逐一確認每一個都不會把數字撐大
    for _syn in SYNTHETIC_TRACE_SOURCES:
        _r = _BLANK_RESULT()
        _r["source_trace"].append({"source": _syn, "success": False, "error": "x"})
        assert _failed_source_count(_r) == 2, (
            f"合成標記 {_syn!r} 把來源數撐大了。")


# ══════════════════════════════════════════════════════════════════════════
# `nav_history_merge` —— 2026-09-06 補的合成標記，以及它的「不要再漏第二個」守衛
# ══════════════════════════════════════════════════════════════════════════
#: 上游**確實會**以 falsy `success` 出現、而且**經人工裁決要計入**「試過的來源數」的名字。
#: ⚠️ 這不是「所有真來源」的清單 —— 只收**會失敗**的那些（成功的不影響計數）。
#: ⛔ 往這裡加名字**等於裁決「它算一次試過的來源」**，請附理由，不要為了消紅而加。
COUNTED_REAL_SOURCES: frozenset = frozenset({
    "alphavantage", "bank_platform", "morningstar", "taiwanlife_direct", "yahoo_finance",
    # ⚠️ `multi_source` 是「多來源流程**本身**拋例外」的紀錄（`fund_orchestration.py:1013`）。
    #    **算不算一次「試過的來源」有兩種讀法**，2026-09-06 本組**不裁決**、維持現況（計入），
    #    只把它具名登記在這裡 —— 具名之後它至少不會再是「沒有人看過的漏網」。
    "multi_source",
})

#: 上游那兩個檔裡**帶 `source` 鍵、但根本不是 `source_trace` 條目**的 dict。
#: ⛔ **這份清單是本組先前一句錯話的產物，理由寫在這裡免得有人再犯**：
#:    本組曾報「`fetch_holdings:exception` 也會把來源數撐大」——**那是假的**。
#:    它是 `result["holdings"]["source"]`（`fund_orchestration.py:791`），
#:    **從來沒有進過 `source_trace`**。當時是拿一個手寫的 dict 當成程式會產生的情境。
#:    ⚠️ **同一個坑，本條守衛自己上線第一次跑就又抓到三個**（2026-09-06）：
#:    ``fundclear`` / ``moneydj_menu`` / ``mj_search`` 是
#:    `search_fundclear()` 與 `search_moneydj_by_name()` **搜尋結果的每一列**
#:    （形狀 `{full_key, name, portal, nav, source}`，append 進區域變數 `results`
#:    後由函式回傳），**不是** `source_trace`。
#:    → 本組先前用「只掃 `.append()` 的引數」那種掃法**看不到它們**；
#:      改成「掃所有帶 `source` 鍵的 dict」才看得到，代價是要像這樣逐一 triage。
#:      **寧可多抓再人工判，也不要用一份剛好掃不到的字表下結論。**
NOT_TRACE_ENTRIES: frozenset = frozenset({
    "fetch_holdings:exception",
    "fundclear", "moneydj_menu", "mj_search",
})

#: 會 `append` 進 `source_trace` 的上游檔（**恰好這兩個**，AST 實測）。
#: 第三個檔開始 append → 下面的守衛轉紅，因為那表示本檔的掃描範圍不再完整。
TRACE_PRODUCERS: tuple[str, ...] = (
    "services/fund_service.py",
    "repositories/fund/fund_orchestration.py",
)


def _trace_marker_shapes() -> list[tuple[str, str, int, object]]:
    """AST 掃上游兩個檔裡**所有帶字面 `source` 鍵的 dict**，連同其 `success` 字面值。

    回傳 `(檔, source 名, 行號, success)`；`success` 缺鍵時回 `KeyError` 這個哨兵物件。

    ⚠️ **為什麼掃 dict 而不是掃 `.append()`**：`services/fund_service.py:1203` append 的是
    一個**變數**（`_hist_trace`，由 `_merge_nav_history_series` 回傳）——
    只掃 append 的引數，`nav_history_merge` 這一族**一個都看不到**。
    **這正是它當初被漏掉的機制**：用錯的形狀去掃，跑一百次也掃不到。
    """
    out: list[tuple[str, str, int, object]] = []
    for _rel in TRACE_PRODUCERS:
        _tree = ast.parse((ROOT / _rel).read_text(encoding="utf-8"))
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.Dict):
                continue
            _src = _succ = KeyError
            for _k, _v in zip(_n.keys, _n.values):
                if not (isinstance(_k, ast.Constant) and isinstance(_k.value, str)):
                    continue
                if _k.value == "source":
                    _src = _v.value if isinstance(_v, ast.Constant) else None
                elif _k.value == "success":
                    _succ = _v.value if isinstance(_v, ast.Constant) else None
            if isinstance(_src, str):
                out.append((_rel, _src, _n.lineno, _succ))
    return out


def test_the_nav_history_merge_marker_never_counts_as_a_failed_source():
    """`nav_history_merge` 是**我方併資料的步驟**，不是一次對外取數 —— 不得計入來源數。

    ## 兩種形狀都要驗，因為第二種才是最容易漏的

    1. ``{"source": …, "success": False, "error": …}`` —— 讀 Google Sheet 失敗
       （`services/fund_service.py:1098`）。
    2. ``{"source": …, "merged": False, "hist_points": …}`` —— **完全沒有 `success` 鍵**
       （同檔 `:1131`）。語意是「讀成功了，只是累積點還沒產生淨增益」＝ **一切正常**，
       而 `_trace_rows()` 的 ``bool(_t.get("success"))`` 會把缺鍵判成失敗。
       **第 2 種在什麼都沒出錯的時候虛報**，比第 1 種更該有測試。

    ## 突變實驗（2026-09-06 實跑，拿掉修復必須轉紅）

    - **M1**：把 `"nav_history_merge"` 從 :data:`SYNTHETIC_TRACE_SOURCES` 拿掉 →
      **本條兩個 case 都轉紅**（來源數 2 → 3，畫面字串跟著變）。✅

    ## 本條到底釘住什麼（**2026-09-06 重寫；舊版兩句自述一句高估一句低估**）

    ⚠️ **舊版寫過兩句話，兩句都不準，一起更正**：

    ~~「本條**不釘住**『排除是靠 source 名字做的』」~~ → **低估了自己。**
    本條**第一行**就是 ``assert "nav_history_merge" in SYNTHETIC_TRACE_SOURCES`` ——
    那是一條**釘手段**的斷言：**任何把它從那個集合裡拿掉的改動，一律轉紅**，
    不管症狀有沒有被別的方式壓下去（獨立稽核用三種「換手段」突變撞過，全紅在這一行）。

    ~~「那時要看的是 `test_a_total_failure_shows_the_source_trace_and_never_paints_red`」~~
    → **那條根本不驗這件事。** 實測：M5 之下它 **1 passed**。逐行讀也對得上 ——
    它的 fixture 每一筆都帶顯式 ``success: False``，斷言只驗
    「``[error]`` 不在／``[dataframe]`` 在／幾個字串在不在」，**一個字都沒碰成功失敗欄**。
    **那句指路會讓下一個人以為有人接住，其實沒有。**

    **精確版（本組實測，逐條可自驗）**：

    ===== ================================================== ============ ============
    突變   內容                                                 上一輪        **現在**
    ===== ================================================== ============ ============
    M1     把 `"nav_history_merge"` 從黑名單拿掉                 紅            紅
    B-b    拿掉黑名單 ＋ 改成「名字含 merge 就不算」              紅            紅
    B-a    **保留**黑名單，但把來源數硬夾 ``min(2, …)``          **綠**       **紅**
    R1     `_failed_source_count` 直接 ``return 2``            **綠**       **紅**
    M5     改 `_trace_rows` 的 falsy 判定（缺鍵→成功）           綠            綠
    ===== ================================================== ============ ============

    ⚠️ **B-a／R1 這兩列在 2026-09-06 第二輪由綠轉紅** —— 補的不是斷言，是**一組期望值
    不是 2 的 fixture**（見本函式下半）。在那之前全檔對 `_failed_source_count()` 的期望值
    **全部是 2**，所以「完全不看輸入、直接回 2」也能全綠。
    **一條只驗得出一個固定數字的測試，驗的不是「有沒有數對」，是「有沒有回那個數」。**

    → **現在釘住的是**：這個名字必須在集合裡（M1／B-b）**＋** 來源數必須真的隨輸入變（B-a／R1）。
    → **仍然沒釘住的是** `_trace_rows` 怎麼判 falsy（M5 照樣綠）——
      那一段改由 :func:`test_a_trace_entry_that_never_said_it_failed_is_not_drawn_as_failed` 接住。
    ⚠️ **上一輪這裡寫「沒釘住集合下游怎麼用」，那句話已經被本輪的 fixture 推翻，故改寫。**
      **同一把尺要對全部同類項目重跑** —— 補完 fixture 就得回頭改這張表，
      否則補強的動作本身會留下一句新的假話。
    ⛔ 不要把 M5／B-a 讀成「這條測試很弱」：它們都是**症狀被另一條路壓掉**，
      而 M5 同時把**所有**缺鍵條目改判成成功 —— 那是範圍大得多的行為變更
      （本輪已改用第三態 :data:`~ui.views.page_03_research.TRACE_UNKNOWN` 處理，見下）。
    """
    assert "nav_history_merge" in SYNTHETIC_TRACE_SOURCES, (
        "`nav_history_merge` 不在合成標記清單裡 —— 它會被算成一個「取不到淨值的來源」。")

    _shapes = {
        "讀 sheet 失敗（success=False）":
            {"source": "nav_history_merge", "success": False,
             "error": "NavHistoryError: 開不了 NAV sheet"},
        "讀成功但無淨增益（**沒有 success 鍵**）":
            {"source": "nav_history_merge", "merged": False, "hist_points": 56,
             "hist_first": "2026-06-01", "hist_last": "2026-08-30", "added": 0,
             "note": "累積 56 點目前全部落在本次 live 序列的日期範圍內 → 尚未產生淨增益。"},
    }
    for _why, _entry in _shapes.items():
        _r = _BLANK_RESULT()
        _r["source_trace"].append(_entry)
        assert _failed_source_count(_r) == 2, (
            f"{_why}：`nav_history_merge` 被算進來源數了 —— "
            f"實際試過的取數來源仍是 2 個（bank_platform／morningstar），"
            f"實得 {_failed_source_count(_r)}。")
        assert "在 2 個來源" in _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_r)), (
            f"{_why}：畫面上的來源數被撐大了。")

    # ⭐ **期望值不是 2 的那一組**（2026-09-06 第二輪複驗建議，實測值得做）
    # ---------------------------------------------------------------------
    # 在這組之前，全檔對 `_failed_source_count()` 的斷言**期望值全部是 2**，
    # 畫面字串也全部是「在 2 個來源」—— 於是 `def _failed_source_count(...): return 2`
    # 這種**完全不看輸入**的實作可以讓 **74 條全綠**（實測）。
    # 一條只驗得出一個固定數字的測試，驗的不是「有沒有數對」，是「有沒有回那個數」。
    # ⛔ 這比再加一條「釘手段」的斷言划算：它同時殺掉 `return 2` 與 `min(2, …)` 兩顆。
    _three = _BLANK_RESULT()
    _three["source_trace"].append(
        {"source": "yahoo_finance", "success": False, "error": "查無此代碼"})
    _three["source_trace"].append(
        {"source": "nav_history_merge", "success": False, "error": "開不了 NAV sheet"})
    assert _failed_source_count(_three) == 3, (
        "三個真來源（bank_platform／morningstar／yahoo_finance）全敗、外加一個合成標記 —— "
        f"應為 3，實得 {_failed_source_count(_three)}。\n"
        "⚠️ 若這裡回 2，多半是來源數被寫死或被夾住了，而不是合成標記被排除。")
    assert "在 3 個來源" in _text(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_three)), (
        "畫面上的來源數與 `_failed_source_count()` 不一致（期望「在 3 個來源」）。")


def test_a_trace_entry_that_never_said_it_failed_is_not_drawn_as_failed():
    """上游**沒說**成功失敗的那一則，不得被畫成「失敗」——**沒說 ≠ 說了失敗**。

    ## 這條補的是一個「只修一半」的洞（2026-09-06 獨立稽核 應修 1）

    `nav_history_merge` 的**第二種形狀**（`services/fund_service.py:1131`）
    **完全沒有 `success` 鍵**，語意是「累積序列讀成功了，只是目前還沒產生淨增益」
    ＝ **一切正常**。上一輪把它從**來源數**排掉了（✅），
    **但同一張逐源軌跡表仍然把它畫成「失敗」** —— 於是同一頁上出現：

        {'來源': 'nav_history_merge', '結果': '失敗',
         '說明': '累積 56 點目前全部落在本次 live 序列的日期範圍內 → 尚未產生淨增益。'}

    「說明」說一切正常、「結果」說失敗，而下面那句話又說「在 **2** 個來源都沒有取到淨值」
    —— **三個地方互相打架，而且那個「失敗」是我方替上游編的結論**（§1）。

    ## 為什麼是第三態，不是「缺鍵當成功」

    「缺鍵當成功」（＝突變 M5）也能讓症狀消失，但我方**沒有觀察到**它成功 ——
    寫「成功」同樣是編的。**不知道就說不知道**，故用
    :data:`~ui.views.page_03_research.TRACE_UNKNOWN`。

    ## 突變實驗（2026-09-06 實跑）

    - 把 `_trace_rows()` 的三態判定改回 ``bool(_t.get("success"))`` → **轉紅**。
    - 把 `TRACE_UNKNOWN` 的值改成和 `TRACE_FAIL` 一樣 → **轉紅**。
    """
    assert TRACE_UNKNOWN not in (TRACE_OK, TRACE_FAIL), (
        "第三態的字面值和成功／失敗撞在一起 —— 那等於沒有第三態。")

    _r = _BLANK_RESULT()
    _r["source_trace"].append({
        "source": "nav_history_merge", "merged": False, "hist_points": 56,
        "added": 0,
        "note": "累積 56 點目前全部落在本次 live 序列的日期範圍內 → 尚未產生淨增益。",
    })
    _rows = _trace_rows(_r)
    _hit = [_x for _x in _rows if _x[TRACE_COLS[0]] == "nav_history_merge"]
    assert len(_hit) == 1, f"逐源軌跡表裡找不到那一則：{_rows}"
    assert _hit[0][TRACE_COLS[1]] == TRACE_UNKNOWN, (
        "上游沒有說成功或失敗，卻被畫成 "
        f"{_hit[0][TRACE_COLS[1]]!r} —— 那是我方替上游編了一個結論（§1）。\n"
        f"該則的說明逐字是：{_hit[0][TRACE_COLS[2]]!r}")

    # ⚠️ 顯式 False 仍然要是「失敗」—— 不得把三態做成「什麼都不確定」。
    _r2 = _BLANK_RESULT()
    _r2["source_trace"].append(
        {"source": "nav_history_merge", "success": False, "error": "開不了 NAV sheet"})
    _hit2 = [_x for _x in _trace_rows(_r2) if _x[TRACE_COLS[0]] == "nav_history_merge"]
    assert _hit2[0][TRACE_COLS[1]] == TRACE_FAIL, (
        "上游**明說**失敗的那一則被畫成別的東西 —— 第三態只准接住「沒說」的。")
    # 顯式 True 照舊
    _r3 = _BLANK_RESULT()
    _r3["source_trace"].append({"source": "moneydj_menu", "success": True, "nav_count": 120})
    _hit3 = [_x for _x in _trace_rows(_r3) if _x[TRACE_COLS[0]] == "moneydj_menu"]
    assert _hit3[0][TRACE_COLS[1]] == TRACE_OK


def test_every_upstream_failure_marker_has_been_triaged():
    """**字面** `source` 名 ＋ **字面 dict** 的上游失敗標記，都必須被裁決過（射程見下表）。

    ## 這條在守什麼（它不是在守某一個名字）

    `SYNTHETIC_TRACE_SOURCES` 是**黑名單**，被測檔自己就寫著「會腐化」。
    但 2026-09-06 查出來的事實比「腐化」更難堪：**它寫下的那一天就不完整**
    —— `nav_history_merge` 在加黑名單的那個 commit（`b83c29f`）當下，
    `services/fund_service.py` 裡**真正的標記**已經有 **3** 處（`:1098` / `:1132` / `:1164`）。
    ⚠️ `git grep -c` 回的是 **4** —— 多出來的 `:1161` 是 ``merged.attrs["nav_history_merged"]``
    （**多一個 d**）。**這裡刻意寫 3 不寫 4。**
    ⚠️ 這一行在 2026-09-06 第二輪複驗前寫的是「4 處」，而同一份 PR 裡
    `ui/views/page_03_research.py` 已經改成 3 —— **同一把尺只套到了被點名的那個檔**
    （`CLAUDE.md §8.2.A.1` 驗證段 ④ 記載的正是這個失效模式）。

    → **靠人記得去對是不會發生的。** 本條把「對一遍」變成機器做的事。

    ## ⛔ 它守得到什麼、守不到什麼（**逐條寫死，不要讀成「沒有漏網」**）

    **守得到**：在 :data:`TRACE_PRODUCERS` 那兩個檔裡、以**字面字串**當 `source` 名、
    且該 dict 是**字面 dict** 的標記 —— 兩邊清單都沒有就轉紅。

    **守不到（2026-09-06 獨立稽核構造，四種形狀實測全綠）**：

    ===== ========================================= ==========================================
    代號   形狀                                       為什麼掃不到
    ===== ========================================= ==========================================
    G1     ``{"source": f"{x}_retry", "success": …}``  非 `ast.Constant` → 本檔填 `None` 後被
                                                       `isinstance(_src, str)` 濾掉
    G3     ``dict(source=…, success=False)``           那是 `ast.Call` 不是 `ast.Dict`
    G4     逐鍵組出來（`t = {}` / `t["source"] = …`）   沒有帶 `source` 鍵的字面 dict
    F3     **第三個檔**只用 `.extend` / `+=` / `insert`  ① 的檔案集合只比對 `.append`，
                                                       該檔不會被認成 producer，也就不會被掃
    ===== ========================================= ==========================================

    ⚠️ **現在沒踩到 G1 是運氣不是設計**：上游目前有 3 個動態 source 名
    （`_intl_src` / `f"{_best_src}(best-of-waterfall)"` / `nav_source`），
    **碰巧全部是 `success: True`** —— 只要有一天其中一個改成失敗路徑，本條不會知道。

    ⛔ **因此不得把本條讀成「上游新增任何標記都會轉紅」。** 它的射程就是上面那一格。
    （`CLAUDE.md §-1.5.1c` 判定 2 的方法教訓：**能被一條構造推翻的全稱句，就不該寫進去。**）

    ⚠️ **它也不會替你決定**新標記該歸哪一邊 —— 它只保證**在射程內**你會知道有這件事。
    ⛔ 轉紅時**不要**為了消紅隨手往某一邊加：加進 `COUNTED_REAL_SOURCES` 等於
    宣告「它是一次真的取數嘗試」，那是會被印在使用者眼前的數字。

    ## 突變實驗（2026-09-06 實跑，逐條確認會轉紅）

    - 把 `"nav_history_merge"` 從黑名單拿掉、也不加進 `COUNTED_REAL_SOURCES` → **轉紅**。
    - 把 `"multi_source"` 從 `COUNTED_REAL_SOURCES` 拿掉 → **轉紅**。
    - 在 `TRACE_PRODUCERS` 裡刪掉 `fund_service.py`（模擬掃描範圍縮水）→ **轉紅**
      （第一個斷言：實際 append 的檔不只清單裡那些）。
    - ⚠️ **G1 / G3 / G4 / F3 四種構造 → 全綠**（見上表）。**這是已知射程外，不是 bug**，
      但**必須寫在這裡**，否則下一個人會以為它守得比實際多。
    """
    # ① 掃描範圍本身要正確：只有這兩個檔會 append 進 source_trace。
    _appenders: set[str] = set()
    for _p in sorted(ROOT.glob("**/*.py")):
        _rel = str(_p.relative_to(ROOT))
        if _rel.startswith((".git", "tests/", "_recon/")):
            continue
        try:
            _t = ast.parse(_p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for _n in ast.walk(_t):
            if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "append"
                    and "source_trace" in ast.unparse(_n.func.value)):
                _appenders.add(_rel)
    assert _appenders == set(TRACE_PRODUCERS), (
        f"會 append 進 source_trace 的檔變了：{sorted(_appenders)}\n"
        f"本檔的掃描範圍 `TRACE_PRODUCERS` 是 {list(TRACE_PRODUCERS)} —— "
        "範圍不對的話，下面那一段 triage 是在一份不完整的清單上做的（本 bug 的原始成因）。")

    # ② 每一個可能被畫成「失敗」的 source 名字都要被裁決過。
    _untriaged: dict[str, list[str]] = {}
    for _rel, _src, _lineno, _succ in _trace_marker_shapes():
        if _succ is True:                       # 只在成功時 append → 不影響失敗計數
            continue
        if _src in NOT_TRACE_ENTRIES:           # 帶 source 鍵但不是 trace 條目
            continue
        if _src in SYNTHETIC_TRACE_SOURCES or _src in COUNTED_REAL_SOURCES:
            continue
        _untriaged.setdefault(_src, []).append(f"{_rel}:{_lineno}")

    assert not _untriaged, (
        "上游有還沒被裁決過的失敗標記：\n"
        + "\n".join(f"  {_s!r}  ({', '.join(_w)})" for _s, _w in sorted(_untriaged.items()))
        + "\n\n它現在會被算進畫面上那句「在 N 個來源都沒有取到淨值」。請逐一裁決：\n"
          "  · 它是我方 pipeline 對自己下的結論 → 加進 `SYNTHETIC_TRACE_SOURCES`；\n"
          "  · 它是一次真的對外取數嘗試       → 加進 `COUNTED_REAL_SOURCES`；\n"
          "  · 它根本不進 source_trace        → 加進 `NOT_TRACE_ENTRIES`。\n"
          "⛔ 三個都要附理由。隨手加一邊就是把一個沒查過的判斷印給使用者看。")


@pytest.mark.parametrize("key,label,unit", RISK_METRICS)
def test_a_nan_metric_is_treated_as_missing_not_as_a_value(key: str, label: str, unit: str):
    """`NaN` ＝ 缺值，**不得**被畫成一個有值的指標（獨立稽核 應修 3）。

    拿掉 `_fmt()` 的 `if value != value: return None` → 稽核組實測 58 passed，
    而行為**確實變了**：`Sharpe nan` 從「未提供」變成一個有值的 metric。
    **缺值被重新分類成有值** —— 使用者失去「未提供」那個誠實訊號，
    而 `nan` 在畫面上看起來只像是一個沒見過的格式，不像是「這個算不出來」。

    ⚠️ 純函式層也驗一次：`_fmt(float("nan"))` 必須是 `None`，
    不是「渲染時剛好看不出來」。
    """
    assert _fmt(float("nan")) is None, "`_fmt()` 把 NaN 當成一個可顯示的數值。"
    assert _fmt(float("nan"), "%") is None, "帶單位時 NaN 的防線失效。"
    _metrics = {**RISK_SENTINELS, key: float("nan")}
    _body = "\n".join(_segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                                        result=_RICH_RESULT(metrics=_metrics))
                                ).get(DEEP_DIVE_CARDS[2], []))
    assert "nan" not in _body.lower(), (
        f"`metrics[{key!r}]` 是 NaN，卻被畫成一個值：\n{_body}")
    assert re.search(re.escape(label) + r"\s*[-+]?\d", _body) is None, (
        f"「{label}」是 NaN（＝算不出來），畫面上卻給了它一個數字：\n{_body}")


# ══════════════════════════════════════════════════════════════════
# 搜尋結果：真候選、真欄位，缺什麼就說什麼（2026-09-08 接上 L2 之後）
#
# ⚠️ **本節的斷言一律以「上游給了什麼」為前提**，不以「畫面上有沒有東西」為前提。
#    後者在「隨便印點什麼」的實作下也會通過 —— 那正是 §1 要防的。
# ══════════════════════════════════════════════════════════════════

#: `[button] <label> key=<key>` 這種錄音行 → key 清單（**有序**）。
#: ⚠️ 只認**帶 key 的** `st.button` —— 沒有 key 的按鈕靠 (型別, label) 產生 ID，
#:    那是 `tests/test_wf03_research_wiring.py` 第三條規則的射程，不在這裡重抄一份。
def _button_keys(parts: list[str]) -> list[str]:
    return [_p.rsplit(" key=", 1)[1] for _p in parts
            if _p.startswith("[button] ") and " key=" in _p]


#: 搜尋結果那一塊的錄音（一級區塊 `#### 搜尋結果` 底下那一段）。
def _results_body(**kw: Any) -> str:
    return "\n".join(_segments(_render(applied=FAKE_QUERY, **kw)).get(
        BLOCK_RESULTS, []))


def test_the_page_asks_the_search_service_not_the_repository():
    """⑧ 的搜尋走 **L2** `services.fund_search`，不是 L1 `repositories.fund`。

    ⚠️ 這一條是**正向錨點**，與既有的兩條反向禁令
    （:func:`test_the_page_never_reaches_into_the_data_layer` /
    :func:`test_the_page_only_talks_to_the_service_layer`）**一組的**：
    只有反向禁令的話，把整段搜尋刪掉也會全綠。

    ## 為什麼是 L2 而不是「再開一個 UI 直呼點」（總管 2026-09-08 裁決）

    `CLAUDE.md §8.2.A.1` 的 **`EX-PASSTHRU-1`** 那一列自己寫著升級觸發條件：
    「…**或本 fetcher 出現第二個 UI caller**（fan-out 一旦出現，(a) 的理由即失效，
    **應比照 R16 上提 L2**）」。也就是說「直接多開一個 UI 呼叫點」那條路，
    **憲法自己把它導向 L2** —— 兩條路是同一個答案。
    ⛔ 舊 ③（`ui/helpers/fund_research/code_finder.py`）仍直呼 L1，**那是刻意保留**
    （客戶明令不動線上舊 Tab），不是可以拿來當「所以 ⑧ 也可以直呼」的先例。
    """
    _mods = _imported_modules(_tree())
    assert "services.fund_search" in _mods, (
        "⑧ 沒有 import 搜尋的 L2 入口 `services.fund_search` —— "
        "只有反向禁令的話，把整段搜尋刪掉也會全綠。")
    assert not [_m for _m in _mods if _m.split(".")[0] == "repositories"], (
        "⑧ 直接 import 了 L1 —— 那正是 `EX-PASSTHRU-1` 的升級觸發條件"
        "（第二個 UI caller），總管 2026-09-08 已裁決走 L2。")


def test_the_search_service_is_called_once_with_the_applied_term():
    """搜尋**每次渲染只打一次**，而且吃的是**已送出**的查詢字串。

    ⛔ 兩個各自獨立的失效模式，一條斷言擋不住兩個，所以這裡兩件都驗：
      · 打兩次 ＝ 一次 rerun 兩趟往返（而 L1 的 FundClear 備援分支沒有快取）；
      · 吃 widget 當下值 ＝ 使用者每打一個字就查一次（鐵則 02 的重點）。
    """
    _hits = [_p for _p in _render(applied=FAKE_QUERY) if _p.startswith("[search] ")]
    assert _hits == [f"[search] {FAKE_QUERY['term']}"], (
        f"搜尋的呼叫序列不是「剛好一次、且吃已送出的字串」：{_hits}")


def test_the_results_block_lists_the_candidates_the_service_returned():
    """L2 回幾列，畫面就列幾張卡 —— **名稱、代碼、淨值、日期、來源逐欄照抄**。

    ⚠️ 每一個哨兵值都獨一無二，所以「某一張卡印了別一列的欄位」會被抓到；
    共用同一個值的 fixture 底下那種錯**完全看不出來**。
    """
    _body = _results_body()
    for _row in _FAKE_ROWS():
        assert _row[KEY_NAME] in _body, (
            f"候選「{_row[KEY_NAME]}」沒有出現在搜尋結果裡。\n" + _body)
        assert _row[KEY_CODE] in _body, (
            f"候選「{_row[KEY_NAME]}」的代碼沒有出現 —— "
            "使用者要拿它去別的地方查，代碼是這張卡最實用的欄位。\n" + _body)
    assert FAKE_ROW_FULL[KEY_NAV] in _body, "有淨值的那一列沒有把淨值印出來。"
    assert FAKE_ROW_FULL[KEY_NAV_DATE] in _body, (
        "有淨值日的那一列沒有把日期印出來 —— 一個沒有日期的淨值無法判斷新不新。")
    # ⚠️ **2026-09-08 補：`總代理` 這一欄原本零守衛**（獨立稽核 S2）——
    #    整段刪掉是 GREEN，而 `來源`／`淨值日` 刪掉都會 RED。
    #    **PR 描述當時宣稱「逐欄照抄」六欄，守衛只驗到五欄** ——
    #    過度宣稱的是描述，不是實作，故補守衛而不是改描述。
    #    ⛔ 它不是可有可無的欄位：境外基金**買哪一檔要看總代理**
    #    （同一檔基金不同總代理的手續費與可買通路不同），這正是線框把它畫在卡上的理由。
    assert FAKE_ROW_FULL[KEY_AGENT] in _body, (
        "有總代理的那一列沒有把總代理印出來 —— 那是使用者要拿去查通路的欄位。")
    assert FAKE_ROW_FULL[KEY_SOURCE] in _body, (
        "沒有標出這一列是哪個來源給的（§2.2 血緣）。")
    # 反向：上游**沒給**總代理的那一列，那個標籤**整個不准出現**。
    # ⚠️ **判準是「那一列自己的說明行裡有沒有這三個字」，不是字串樣式比對** ——
    #    初版寫 ``"總代理 ·" not in _body``，突變（空值也硬畫標籤）**沒有轉紅**：
    #    實際輸出是 ``總代理  · ``（f-string 一個空白 ＋ join 一個空白，**兩個**），
    #    樣式差一個空白就漏掉。**猜輸出長什麼樣 ＝ 猜；抓那一列來看 ＝ 驗。**
    _lines = _segments(_render(applied=FAKE_QUERY)).get(BLOCK_RESULTS, [])
    _sparse = [_p for _p in _lines
               if _p.startswith("[caption] ") and FAKE_ROW_SPARSE[KEY_CODE] in _p]
    assert _sparse, (
        f"找不到沒有總代理那一列（{FAKE_ROW_SPARSE[KEY_CODE]}）的說明行 —— "
        "本段反向斷言會對空氣生效。\n" + "\n".join(_lines))
    assert "總代理" not in _sparse[0], (
        "上游沒給總代理的那一列還是印出了「總代理」標籤 —— "
        "上游沒給的欄位整段不畫，佔位會讓每一列看起來一樣完整。\n" + _sparse[0])
    # 順序：L2 回傳的順序就是畫面順序，不得重排（重排＝本頁自己發明了一套排名）
    _i_a = _body.index(FAKE_ROW_FULL[KEY_NAME])
    _i_b = _body.index(FAKE_ROW_SPARSE[KEY_NAME])
    assert _i_a < _i_b, (
        "畫面把 L2 回傳的順序重排了 —— 本頁沒有任何排序依據，"
        "重排等於憑空發明一個排名（§1）。\n" + _body)


def test_the_results_block_never_invents_a_nav_it_was_not_given():
    """沒有淨值的那一列：**不准生一個數字**，而且要說出是這個來源沒給。

    ⚠️ 這是本節最重要的一條：填一個看起來合理的淨值，使用者**完全看不出它是假的**
    （`CLAUDE.md §1`）。留白又會讓他以為「這檔沒有淨值」——所以要**明說是來源沒給**。
    """
    _body = _results_body(search=[dict(FAKE_ROW_SPARSE)])
    assert "這個來源沒有給淨值" in _body, (
        "沒有淨值的那一列沒有說明原因 —— 一個孤零零的「—」讓使用者只能猜。\n" + _body)
    # 上游沒給的欄位**整段不畫**，不用「未知」「N/A」去佔位
    for _word in ("未知", "N/A", "無資料"):
        assert f"淨值日 {_word}" not in _body and f"總代理 {_word}" not in _body, (
            f"用「{_word}」去佔位了 —— 上游沒給的欄位整段不畫，"
            "佔位會讓四段看起來一樣長、實際上有幾段是編的。\n" + _body)
    # 純函式層：餵空值進去不得長出任何東西
    assert _result_value(dict(FAKE_ROW_SPARSE)) == "", (
        "`_result_value()` 在上游沒給淨值時生出了一個值。")
    assert _row_str({}, KEY_NAV) == "" and _row_str({KEY_NAV: None}, KEY_NAV) == "", (
        "`_row_str()` 把「沒有」變成了別的東西。")


def test_a_row_with_no_name_is_declared_grey_not_numbered():
    """連名稱與代碼都沒有的那一列 → **灰態 ＋ 說出上游沒給**，不得編一個名字。

    ⛔ 「未知基金」「候選 3」這種標題看起來像一個真的名字，
       使用者會以為那是基金的名字。**灰態 ＋ 一句實話**才是誠實的畫法。
    """
    _nameless = {KEY_NAME: "", KEY_CODE: "", KEY_AGENT: "", KEY_NAV: "",
                 KEY_NAV_DATE: "", KEY_SOURCE: "TDCC-3-4"}
    _card = _result_card(dict(_nameless))
    assert _card["title"] == _NAMELESS_TITLE, (
        f"沒有名稱的那一列被安上了標題 {_card['title']!r}。")
    assert _card["state"] == STATE_NOT_READY, (
        "沒有名稱的那一列不是灰態 —— 它看起來會像一張正常的卡。")
    assert _card.get("where"), (
        "灰卡沒有「去哪補」—— `render_state` 的 docstring 逐字："
        "「沒有它，占位只是把『消失』換成『灰色的消失』。」")
    # ⚠️ **這裡刻意讀整頁而不是 `_results_body()`**：灰態卡走
    #    `state_card()` 的 `st.markdown(f"**{title}**")`，而那正是 `_units()`
    #    的卡片 opener —— 它會**自己開一個新單位**，不會留在「搜尋結果」那一段裡。
    #    （同理：兩列都沒有名稱時，畫面上會出現兩個同名單位，
    #    `test_unit_names_are_unique` 會紅 —— 那是 `_segments()` 的已知性質，
    #    不是本頁的 bug，所以本檔的 fixture 不製造那個處境。）
    _all = _text(_render(applied=FAKE_QUERY, search=[dict(_nameless)]))
    assert _NAMELESS_TITLE in _all and NOT_READY_MARK in _all, (
        "畫面上沒有把那一列標成灰態。\n" + _all)


def test_the_results_block_says_out_loud_that_it_has_no_performance():
    """結果卡上**沒有績效**，而且這件事要說出來一次（不是每張卡各印一次）。

    線框那三張示意卡有「+12.4%」「Sharpe 0.81」——**名錄搜尋根本不回傳績效**
    （L1 那六個鍵裡沒有）。填一個數字是造假；留白會讓使用者以為「這檔沒有績效」。
    ⚠️ 只印**一次**是刻意的：客戶原話「舊 UI 資訊太多」，
    同一句話印九遍就是那個病。
    """
    _body = _results_body()
    assert _RESULTS_NO_PERF_NOTE in _body, (
        "沒有說明這份清單裡為什麼沒有績效。\n" + _body)
    assert _body.count(_RESULTS_NO_PERF_NOTE) == 1, (
        f"「這份清單只有淨值」印了 {_body.count(_RESULTS_NO_PERF_NOTE)} 次 —— "
        "整塊講一次就夠，每張卡各印一次正是客戶說的「資訊太多」。\n" + _body)


def test_truncating_the_candidate_list_is_disclosed_not_silent():
    """只畫前 N 張卡時，**總筆數一定要講出來**。

    ⛔ 默默截斷 ＝ 用一個版面決定去偽造一個資料事實（使用者會以為名錄裡就這幾檔）。
    """
    _many = [dict(FAKE_ROW_FULL, **{KEY_NAME: f"哨兵候選第{_i}檔",
                                    KEY_CODE: f"SENTINELMANY{_i}"})
             for _i in range(MAX_RESULT_CARDS + 3)]
    _body = _results_body(search=_many)
    assert str(len(_many)) in _body, (
        f"截斷了卻沒有講出總筆數 {len(_many)}。\n" + _body)
    _drawn = [_r for _r in _many if _r[KEY_NAME] in _body]
    assert len(_drawn) == MAX_RESULT_CARDS, (
        f"畫了 {len(_drawn)} 張卡，`MAX_RESULT_CARDS` 是 {MAX_RESULT_CARDS}。")
    # 純函式層：講不講總數與畫幾張是兩件事，分開驗
    assert "12" in _results_caption(12, 9) and "9" in _results_caption(12, 9)
    assert "5" in _results_caption(5, 5), "沒有截斷時也要講總筆數。"


def test_the_empty_results_state_never_claims_the_fund_does_not_exist():
    """名錄回空清單 → 空狀態三要素 ＋ **照抄 L2 那句「分不出是哪一種」**。

    ⛔ L1 的 `tdcc_search_fund` 把所有例外都吞掉（`_tdcc_get` 是
       `except Exception: return []`，FundClear 備援是 `except Exception: pass`）——
       **三個來源全掛與名錄裡真的沒有，回傳值一模一樣是 `[]`**。
       寫「查無此基金」就是替上游編了一個它沒說過的結論（§1）。
    """
    _body = _results_body(search=[])
    assert _RESULTS_EMPTY_TITLE in _body, "空狀態少了標題這一要素。\n" + _body
    assert EMPTY_MEANS_UNKNOWN in _body, (
        "空狀態沒有照抄 `services.fund_search.EMPTY_MEANS_UNKNOWN` —— "
        "本頁分不出「真的沒有」與「來源取不到」。\n" + _body)
    assert where_to_find("research") in _body, "空狀態少了「去哪補」這一要素。\n" + _body
    for _lie in ("查無此基金", "查無結果", "這檔基金不存在", "沒有這檔"):
        assert _lie not in _body, (
            f"空狀態宣告了「{_lie}」—— 同一個空清單也可能是三個來源都掛了，"
            "這句話對後者是假的（§1）。\n" + _body)


def test_a_search_failure_is_a_red_frame_not_an_empty_result():
    """搜尋**拋例外** → 真的紅框（`safe_section`），**不得**被畫成「沒有候選」。

    ⚠️ 這一條與上一條是**一對的**：上一條要求空清單不准講成「不存在」，
    本條要求**真的炸掉**不准講成「空清單」。兩者都是把「不知道」講成「知道」。
    ⛔ 本頁**刻意沒有** try/except（`test_the_page_has_no_exception_handler_of_its_own`
    在守），所以例外會一路走到 `safe_section()` —— 那才是有 traceback 的紅框。
    """
    _parts = _render(applied=FAKE_QUERY,
                     search_raiser=RuntimeError("哨兵：搜尋炸了"))
    _all = _text(_parts)
    assert "[error]" in _all, (
        "搜尋拋出的真例外沒有被畫成紅燈 —— 它被吞了或被降級成空狀態（§1）。\n" + _all)
    assert "哨兵：搜尋炸了" in _all, (
        "紅框沒有帶出真正的例外訊息 —— 那只是一個紅色的猜測。\n" + _all)
    assert _RESULTS_EMPTY_TITLE not in _all, (
        "搜尋炸了卻畫成「沒有列出任何候選」—— 那是把系統故障說成業務事實。\n" + _all)


# ══════════════════════════════════════════════════════════════════
# 「選定後展開」—— 線框 Tab 03 的 gate（2026-09-08 恢復）
#
# ⚠️ **每一條都驗「取數有沒有真的被擋住」，不是「畫面上有沒有字」。**
#    只驗畫面的話，「照樣取數、只是不顯示」會全綠 —— 那看起來一模一樣，
#    但每一次 rerun 都在打上游。
# ══════════════════════════════════════════════════════════════════

def test_the_deep_dive_does_not_fetch_until_a_fund_is_selected():
    """⭐ **gate 的本體**：沒選定 → `auto_fetch_moneydj` **一次都不准被呼叫**。

    ## 這一條取代了什麼（不是放寬，是換一個更嚴的判準）

    2026-09-05 的骨架版**沒有** gate（那時沒有東西可以被選定，模組 docstring 就地登記過），
    深度區直接拿**已送出的查詢字串**去取數。本輪接上結果卡之後，
    舊登記自己寫的觸發條件成立，gate 照它說的恢復。

    ⛔ **判準是呼叫次數，不是畫面**。「照樣 fetch、只是把結果藏起來」在任何
       只看畫面的斷言底下都是全綠的，而它每一次 rerun 都在打上游。
    """
    _no_pick = [_p for _p in _render(applied=FAKE_QUERY) if _p.startswith("[fetch] ")]
    assert _no_pick == [], (
        f"還沒選定任何一檔，深度區就已經去取數了：{_no_pick}\n"
        "線框 Tab 03 寫的是「**選定後**展開」——"
        "沒有選定就不該有任何一次往返。")
    _picked = [_p for _p in _render(applied=FAKE_QUERY, selected=SELECTED_CODE)
               if _p.startswith("[fetch] ")]
    assert _picked == [f"[fetch] {SELECTED_CODE}"], (
        f"選定之後的取數不是「剛好一次、且吃選定的那一檔」：{_picked}\n"
        "吃查詢字串而不是選定值 ＝ gate 是假的（畫面換了、資料沒換）。")


def test_the_expanded_deep_dive_says_which_fund_it_is_showing():
    """⭐ gate 打開之後，畫面上必須說出**現在展開的是哪一檔**。

    ## 為什麼這是 §1 等級、不是文案潤飾

    深度區六格的數字**全部是真的**，只是**不知道是誰的**。使用者從九張候選卡裡
    點了其中一張、或換過關鍵字之後，下面那六格是哪一檔**完全看不出來** ——
    `CLAUDE.md §1`：**錯誤的數字比沒有數字更危險**，而「對的數字掛錯基金」
    就是錯誤的數字。被測檔 `_render_deep_dive()` 的註解自己就是這樣寫的。

    ## ⚠️ 2026-09-08 補：這句話原本**零守衛**（獨立稽核 S1）

    整行刪掉 → **GREEN**；`grep 目前展開 tests/` **0 命中**。
    ⛔ 一句被程式碼註解與 PR 描述雙雙當成交付項的 §1 宣稱，**不能只靠自律**。

    ## 判準刻意**不是**關鍵字黑名單

    黑名單（「必須出現『目前展開』四個字」）只擋得住上一次那個寫法，換句話說就繞過。
    本條釘的是**可驗證的內容**：深度區的 `st.caption` 裡要出現
    (1) **選定的那一檔**的識別字、(2) 換一檔的**去處**（區塊名 ＋ 那顆按鈕的字）。

    ⚠️ **只看 `[caption]` 行，不看整段** —— recorder 會把 `[fetch] <代碼>` 也記進
    同一個單位，拿整段做 containment 會**恆真**（那條線根本不是畫給使用者看的）。
    """
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE))
    _body = _seg.get(BLOCK_DEEP, [])
    assert _body, f"深度區那一段不見了。現有單位：{list(_seg)}"
    _caps = [_p for _p in _body if _p.startswith("[caption] ")]
    assert _caps, (
        "深度區一句 `st.caption` 都沒有 —— 「現在展開的是哪一檔」沒有落點。\n"
        + "\n".join(_body))
    _named = [_c for _c in _caps if SELECTED_CODE in _c]
    assert _named, (
        f"深度區沒有任何一句說明文字提到選定的那一檔（{SELECTED_CODE!r}）——\n"
        "六格的數字都是真的，只是使用者不知道是誰的（§1）。\n"
        + "\n".join(_caps))
    # 它同時要給出「換一檔」的去處，否則使用者只知道是誰、不知道怎麼換
    assert any(BLOCK_RESULTS in _c and SELECT_LABEL in _c for _c in _named), (
        f"說出了是哪一檔，卻沒說怎麼換 —— 應指回「{BLOCK_RESULTS}」的"
        f"「{SELECT_LABEL}」。\n" + "\n".join(_named))
    # 反向：它講的必須是**選定值**，不是查詢字串（兩者在本檔刻意不相等）
    assert not any(FAKE_QUERY["term"] in _c and SELECTED_CODE not in _c
                   for _c in _caps), (
        "深度區的說明文字報的是**查詢字串**而不是選定的那一檔 —— "
        "那會讓使用者以為看到的是他打的那一串。\n" + "\n".join(_caps))


def test_the_locked_deep_dive_says_how_to_unlock_it():
    """gate 關著時 → 空狀態三要素，而且「去哪補」指回**搜尋結果**。

    ⚠️ 指回搜尋條件是**錯的**：使用者已經搜尋過了，他缺的是「點一張卡」。
    這是本頁少數幾則**照著做真的有效**的指路之一，不要把它換成那族
    「有效性有限」的（見 `_pending_where()` 的 docstring）。
    """
    _seg = _segments(_render(applied=FAKE_QUERY))
    _body = "\n".join(_seg.get(BLOCK_DEEP, []))
    assert _NOT_SELECTED_TITLE in _body, "gate 關著卻沒有標題。\n" + _body
    assert _NOT_SELECTED_MISSING in _body, "gate 關著卻沒說在等什麼。\n" + _body
    assert f"{where_to_find('research')} → {BLOCK_RESULTS}" in _body, (
        "「去哪補」沒有指回搜尋結果 —— 使用者已經搜尋過了，"
        "叫他回搜尋條件再打一次是一則無效的指路。\n" + _body)
    # 深度區的六格一格都不准畫（畫了就等於 gate 只是視覺上的）
    for _unit in DEEP_UNITS:
        assert _unit not in _seg, (
            f"gate 關著，深度區的「{_unit}」卻還是畫出來了。現有單位：{list(_seg)}")


def test_clicking_a_result_card_selects_that_fund():
    """⭐ 按下某一張卡的「查這一檔」→ session 記住**那一列**的代碼。

    ⚠️ **按 key 而不是按 `submitted`**：一次會畫最多九顆同樣 label 的按鈕，
    `submitted=True` 會讓九顆同時回 True —— 那不是任何使用者做得到的事，
    而且「哪一顆被按 → 選定哪一檔」正是本條要驗的東西。
    """
    _keys = _button_keys(_render(applied=FAKE_QUERY))
    _picks = [_k for _k in _keys if _k.startswith("v03_pick_")]
    assert len(_picks) == len(_FAKE_ROWS()), (
        f"「{SELECT_LABEL}」的按鈕數 {len(_picks)} 與候選數不符：{_picks}")
    _state: dict = {}
    _render(applied=FAKE_QUERY, clicked={_picks[1]}, state_out=_state)
    assert _state.get("v03_research_selected_fund") == FAKE_ROW_SPARSE[KEY_CODE], (
        "按了第二張卡，選定的卻不是第二列那一檔 —— "
        f"session 是 {_state.get('v03_research_selected_fund')!r}。")
    _state.clear()
    _render(applied=FAKE_QUERY, clicked={_picks[0]}, state_out=_state)
    assert _state.get("v03_research_selected_fund") == FAKE_ROW_FULL[KEY_CODE]


def test_every_pick_button_has_its_own_key_in_the_v03_namespace():
    """每一顆按鈕的 key **兩兩不同**，而且都在 `v03_` 命名空間裡。

    ## 為什麼要在**行為層**驗這件事

    `tests/test_wf03_research_wiring.py` 的靜態掃描**只認字面值 key**
    （它自己的「看不到的形態」段就寫著），而這一頁的按鈕 key 是**逐列動態組出來**的
    —— 那條規則結構上看不到它們。

    ⛔ 撞 key 在 Streamlit 是 `StreamlitDuplicateElementId`，
       而 `app.py` 的分頁 body 會把它接住畫成紅框、**`at.exception` 仍然是空的**
       （本檔開頭那段長註已記載）—— 也就是說 AppTest 也看不到。
       **這一條是那個洞在 ⑧ 這一頁上唯一的守衛。**
    """
    _dupe = [dict(FAKE_ROW_FULL), dict(FAKE_ROW_FULL)]   # 兩列一模一樣
    for _label, _search in (("一般", _SENTINEL), ("兩列完全相同", _dupe)):
        _keys = _button_keys(_render(applied=FAKE_QUERY, search=_search))
        assert _keys, f"（{_label}）一顆帶 key 的按鈕都沒錄到 —— 本條會變成假守衛。"
        _bad = sorted(_k for _k in _keys if not _k.startswith("v03_"))
        assert not _bad, (
            f"（{_label}）有按鈕的 key 不在 `v03_` 命名空間內：{_bad}\n"
            "新舊 ③ 在同一次 `st.tabs` run 裡同時渲染，key 撞上 ＝ 整個 App 當場崩潰。")
        assert len(set(_keys)) == len(_keys), (
            f"（{_label}）按鈕 key 重複了：{_keys}\n"
            "`_pick_token()` 含序號正是為了擋這個 —— 兩列代碼相同時它必須仍然唯一。")
    # 純函式層：同樣的兩列，token 也必須不同
    assert _pick_token(dict(FAKE_ROW_FULL), 0) != _pick_token(dict(FAKE_ROW_FULL), 1)
    # 連代碼與名稱都空的兩列（`re.sub` 之後是空字串）同樣不准撞
    assert _pick_token({}, 0) != _pick_token({}, 1)


def test_the_escape_hatch_lets_a_known_code_through_when_the_directory_has_none():
    """⭐ 名錄查不到候選時，使用者**仍然到得了**深度區（`DIRECT_LABEL`）。

    ⛔ **拿掉這顆按鈕是功能退化，不是「gate 做得比較嚴」**：一個手上就有完整代碼
       或 MoneyDJ 網址、但那串字不在 TDCC 名錄裡的使用者（保單商代碼、境內基金…），
       在新頁上會**完全到不了**深度區 —— 而舊 ③ 支援這條路。
    ⚠️ 它仍然是 gate：使用者要**明示**「就用我打的這一串」，
       不是由本頁偷偷替他決定。
    """
    _keys = _button_keys(_render(applied=FAKE_QUERY, search=[]))
    assert "v03_use_raw_term" in _keys, (
        f"名錄沒有候選時找不到「{DIRECT_LABEL}」那顆按鈕 —— "
        "手上有完整代碼的使用者到不了深度區。\n" + str(_keys))
    _state: dict = {}
    _render(applied=FAKE_QUERY, search=[], clicked={"v03_use_raw_term"},
            state_out=_state)
    assert _state.get("v03_research_selected_fund") == FAKE_QUERY["term"], (
        "按下逃生門之後，選定的不是使用者原封輸入的那一串 —— "
        f"session 是 {_state.get('v03_research_selected_fund')!r}。")
    # 已經選定之後，這顆按鈕不該再出現（那一塊已經展開了）
    _after = _button_keys(_render(applied=FAKE_QUERY, search=[],
                                  selected=SELECTED_CODE))
    assert "v03_use_raw_term" not in _after, (
        "已經展開了還畫著逃生門 —— 那是鐵則 04 要禁的冗餘占位。")


def test_submitting_a_new_search_drops_the_previous_selection():
    """⭐ 送出**新的**查詢 → 舊的選定作廢。

    ⛔ 不清的話：使用者換了關鍵字，深度區還停在上一次選的**另一檔**上，
       而畫面上**沒有任何跡象**。那比顯示過期資料更糟 ——
       §2.4 允許留著過期資料**但必須帶旗標**，而這裡連旗標都給不出來
       （它不是「舊的同一檔」，是完全另一檔）。
    ⚠️ `clicked=set()` ＝ **一顆按鈕都沒按**。不給它的話，recorder 會讓
       `st.button` 跟著 `submitted=True` 一起回 True，九顆卡片鈕同時「被按」，
       送出之後又立刻把選定寫回去 —— 本條就驗不到東西了。
    """
    _state: dict = {}
    _render(applied=FAKE_QUERY, selected=SELECTED_CODE, submitted=True,
            clicked=set(), widget={_LABEL_TERM: "另一個哨兵關鍵字"},
            state_out=_state)
    assert _state.get("v03_research_selected_fund") is None, (
        "送出新查詢之後，上一次選定的那一檔還留著："
        f"{_state.get('v03_research_selected_fund')!r}\n"
        "深度區會停在一檔與這次查詢無關的基金上，而畫面上沒有任何跡象。")
    assert (_state.get("v03_research_applied_query") or {}).get("term") \
        == "另一個哨兵關鍵字", (
        "送出之後已套用查詢沒有換成新的 —— 那 gate 清掉選定就沒有意義了。")
