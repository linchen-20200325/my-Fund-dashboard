"""④ 資產配置新頁的**零寫入**守衛 —— 渲染一輪不得動客戶的 Google Sheet 或磁碟。

客戶 2026-09-06 永久授權（逐字）
--------------------------------
> 「凡是『查詢/搜尋』功能，一律強制走純讀取（唯讀），**絕對禁止反向寫入我的 Google Sheet**。
>   不用問我，直接切斷寫入！」

本檔守的是 ④ 這一頁的那道切斷。**它現在就要在，而不是等委派落地才補** ——
理由是 `ui/views/page_02_health.py` 的實證：② 的同型守衛因為走**靜態 import 閉包**，
委派一加就**自動**把新模組納入射程（實測閉包 65 → 95），
**機器本來就設計對了，不需要有人記得回來改**。本檔沿用同一個結構。

⚠️ **本檔為什麼不長得像 `test_wf02_health_no_writes.py`**（刻意的，逐條說明）
---------------------------------------------------------------------------
派工單點名不要照抄那一份的弱點。本檔的三處差異：

1. ⛔ **不用「函式名白名單」，也不用「import 來源白名單」。**
   本 repo 已實測那種守衛擋不住四種寫法：
   ``from m import f as g`` ／ ``g = m.f`` 再 ``g()`` ／ ``getattr`` ／ ``importlib``。
   → 本檔比對的是**低階寫入動作本身的名字**（`append_row` / `update` / `write_text` …），
     那是 gspread 與 `pathlib` 的 API 表面，**不是本 repo 可以改名繞過的東西**。
2. ⭐ **涵蓋 `ast.Attribute` —— 把寫入方法「當引數傳出去」也算命中。**
   `_with_quota_retry(ws.append_row, ...)` 這種寫法**沒有呼叫節點**
   （`ws.append_row` 是 `ast.Attribute`，被當引數傳給包裝器，由包裝器去呼叫）。
   只看 `ast.Call` 的偵測器**看不到它**。
   ⚠️ 這不是假想：`bacfe06`（「補掉 M5c —— 把寫入函式**當引數傳出去**也算命中」）
   就是為了同一個形狀而補的。由 :func:`test_the_detector_sees_the_four_evasions` 釘住。
3. ⭐ **哨兵記名、不拋例外。**
   會 `raise` 的哨兵會被上層 ``try/except`` 吃掉 —— 那等於沒有守衛，
   而且**吃掉之後畫面看起來一切正常**，比沒有守衛更糟。
   由 :func:`test_the_sentinel_records_instead_of_raising` 與
   :func:`test_a_swallowing_caller_cannot_hide_a_write` 釘住。

⚠️ 這道守衛看得見什麼、看不見什麼（照實寫，不要讀成「守死了」）
----------------------------------------------------------------
**看得見**

* 頁面**靜態 import 閉包**內任何一支 repo 模組裡的寫入動作 ——
  無論它是被呼叫（`ast.Call`）還是被當引數傳出去（`ast.Attribute`）。
* 那些寫入動作**有沒有被按鈕擋住**（`st.button` / `st.form_submit_button` /
  `st.checkbox` / `st.download_button`，含「先存成變數再 `if`」那種寫法）。
  這正是 `#800` 的教訓：`_maybe_snapshot()` **一渲染就寫**，
  唯一的閘門是一個 session 旗標 —— 而**「少寫幾次」不叫切斷**。

**看不見（已知缺口，逐條寫出來，不要當成保證）**

1. **只追靜態 import。** `importlib.import_module("a." + "b")` 這種動態載入
   不在閉包內，本檔看不到它引進來的模組。
2. **閘門偵測是語法層的。**
   ~~一個 `if _go:` 而 `_go` 來自別的函式的回傳值，本檔會判成**未被擋住**（偽陽性，從嚴）。~~
   → ⛔ **2026-09-07 更正：這句話只在一半的情況下成立，另一半剛好相反**
   （**有意識的更正，不是漏刪** · 日期 **2026-09-07** ·
   決策者 **AI 總管（依獨立稽核實測）** · 本組已自行重現，重現方式見缺口 **7**）。

   **實測** —— 同一個「`_go` 來自別的函式的回傳值」的形狀，**只差變數名撞不撞**::

       # A 名字沒撞到 → _intent_names()=[]      → 判「沒擋住」＝ 偽陽性（舊句成立）
       # B 名字撞到了 → _intent_names()=['_go'] → 判「**有擋住**」＝ **漏報**（舊句相反）

   決定結果的**不是**「`_go` 從哪來」——:func:`_intent_names` 根本不追值的來源。
   決定結果的是「**同一個模組裡任何一處有沒有出現過** ``_go = st.button(...)``」，
   因為它掃的是**整份模組的 AST、沒有作用域概念**。
   → **舊句把一個會漏報的形狀寫成了偽陽性**，也就是把最危險的方向講成了最安全的方向。
   完整形狀與端對端重現見缺口 **7-(2)**（那一種是四種殘留裡最寫實的一種）。

   ~~**寧可誤報，不可漏報。**~~
   → ⛔ **2026-09-07 更正：這句話在 `#809` 當時是假的**（**有意識的更正，不是漏刪**；
   由獨立稽核抓出，本組已自行重現）。**`#810` 把方向收緊了，但「不會漏報」仍然不成立**
   —— 詳見下方缺口 **7**。先講 `#810` 修好的那一類：

   **`#809` 的實況** —— 閘門偵測是把 `If.test` **unparse 成字串**，看裡面有沒有
   ``.button(``。於是下面這段被判成「**有擋住**」，而它**每次渲染都寫**::

       if not st.button("送出"):
           ws.append_row(row)

   字串裡確實有 ``.button(``，但那是一個**反向**閘門。也就是說：
   **它在自己宣告的方向上漏報。** `if _flag or st.button(...)` 是同一個病的另一張臉。
   ⚠️ 這個 idiom 在本 repo **有前科**，不是理論上的角落：`ui/tab_fund_grp_health.py`
   與 `ui/helpers/fund_grp_health/switch_advisor_section.py` 兩處都留著
   「原 ``if not st.button(): return`` 的**致命 bug**」的就地註解。

   **本次修法** —— 改成比對 `If.test` 的**節點形狀**（:func:`_is_intent_expr`）：
   test 必須**整個就是**那個意圖運算式（`st.button(...)` 或指派自它的變數名）；
   包了任何一層（``not`` ／ ``and`` ／ ``or`` ／ ``==`` …）一律當「看不懂」＝**沒擋住**。
   **回歸釘**：:func:`test_a_reversed_or_widened_gate_is_not_treated_as_a_gate`
   （已實測：對 `#809` 的舊邏輯轉紅）。

   ⚠️ **這個修法自己帶了一個已知誤報，就地寫明，不要當成瑕疵去「修掉」**：
   ``if _ready and st.button(...):`` **真的有擋住**，本檔仍判它沒擋住。
   **那是刻意選的方向** —— 誤報會被人看到並就地處理，漏報只會安靜地放行一次寫入。
   ⛔ **不得**為了消掉這種誤報而讓判定「更聰明」；不確定算不算擋住，一律判**沒擋住**。

   ⛔ **本條的射程到此為止，不要再往外讀**：`#810` 修好的是「**把 `If.test` 整個
   unparse 成字串**」那一類 —— 也就是「**反向／放寬的閘門被當成閘門**」。
   **它沒有、也不打算讓「不會漏報」成立**；`_is_intent_expr` 判 `ast.Name` 時
   仍然只查一個**模組層的名字集合**，那正是缺口 **7** 的入口。
3. ⛔ **`getattr` 家族整族看不見** —— 本檔只認 `ast.Attribute`，
   而下面四種寫法**連一個 `ast.Attribute` 節點都不會產生**，故 sink 名字從頭到尾不出現::

       getattr(ws, "append_row")(row)              # 字面字串
       getattr(ws, "append" + "_row")(row)         # 執行期拼接
       _M = "append_row"; getattr(ws, _M)(row)     # 名字放進常數
       _fn = getattr(ws, "append" + "_row"); wrap(_fn, row)   # 組好再當引數傳出去

   ⚠️ **四種本組都實測過，對本檔全部是綠燈**（2026-09-07，注入 `ui/views/page_04_portfolio.py`
   的渲染路徑後跑本檔）。⛔ **本批刻意不補**：要看穿它們得追值的來源（跨函式、跨模組），
   那是**行為層**的事，而本檔是純靜態的；硬補會變成另一個題目，
   而且補到一半的靜態追蹤最危險 —— 它會讓人以為這一族已經守住了。
   ⛔ **絕對不要把這一條讀成「已經守住了」。** 真正罩得住它的是執行期那一層（見下一條）。
4. ⛔ **本檔不驗執行期。** 它讀 AST，不渲染。真的跑一輪、用假件攔截的那一層，
   由 `tests/test_portfolio_perf_render_no_writes.py` 負責（deny-by-default 假件）。
   **兩者互補，不重疊**：那一份只罩「📈 組合績效追蹤」那一條路，本檔罩整個閉包。
   ⚠️ 上一條的 `getattr` 家族**只有這一層攔得到**（哨兵是靠 `__getattr__` 認名字的，
   名字怎麼組出來的它不在乎）—— 本檔的 :class:`_Recorder` 已具備該能力，
   但它**只在本檔自己的單元測試裡跑**，沒有接到 ④ 的整頁渲染上。
5. **本地無 `streamlit`，故本檔刻意設計成不需要它** —— 見上一條。
6. ⚠️ ~~**主規則目前在寫入這一半是「空掃通過」**~~ → **2026-09-07 已經不是空掃了，
   而且它是被本條自己預告的那件事終結的**（**有意識的狀態變更，不是漏刪**）。
   本條原文逐字寫著「**委派一落地，閉包會自己變大，屆時這一條會自然過期**」——
   ④ 依客戶路線 (A) 開始委派，**閉包 11 → 17**，主規則命中 **1** 個節點。
   ⛔ **原文那句「過期時請刪掉本條，不要留著誤導」本組沒有照做**，理由如下：
   本條真正有價值的是**它記載的失效模式**（空掃恆綠 ＋ 三條正對照存在的理由），
   那一半今天依然成立；過期的只有**數字**。**刪掉它會連教訓一起刪掉。**
   → 現行：**數字就地更新、舊敘述加刪除線保留**。
   ⚠️ **那唯一命中的 1 個節點是偽陽性**（`str.replace`），已具名豁免，
   見 :data:`_FALSE_POSITIVE_SINKS`。也就是說**真陽性目前仍然是 0** ——
   ⛔ 但那是「**接進來的那幾支真的沒有寫入**」，**不再是**「沒有東西可掃」。
   ⚠️ **一支被實測擋下來的委派**：`ui/helpers/portfolio_perf.py`
   （接上去閉包會變 **34**、槽變 **14**，其中 `infra/cache.py` 的
   `makedirs` / `to_csv` / `remove` 是**真的**磁碟寫入，而且它**一渲染就打一次匯率 API**）——
   本批**沒有接它**，理由與出路寫在 `ui/views/page_04_portfolio.py::REASON_PERF`。
   **舊表述（量測日 2026-09-07 稍早，接線前）**：
   ~~閉包共 **11** 個模組，其中 `_WRITE_SINKS` 命中的節點數是 **0**。~~
   也就是說 :func:`test_the_page_closure_never_writes_on_render` 現在恆綠，
   **不是因為擋住了什麼，是因為還沒有東西可擋** ——
   `#809` 的閘門漏報能活下來正是這個緣故：閘門那一段**只被合成 fixture 跑過**，
   而當時的 fixture 只有正向的 `if st.button(...)`，一格反向的都沒有。
   → 這正是本檔三條「正對照」存在的理由（**空掃就是最危險的那種綠燈**）；
   委派一落地，閉包會自己變大，屆時這一條會自然過期。**過期時請刪掉本條，不要留著誤導。**

   **⭐ 正對照：這個「0」不是掃描器壞了**（2026-09-07 實測，可自行重跑）——
   ⛔ 沒有這一段，讀者無從分辨「沒有東西可擋」與「掃描器根本沒接上」::

       services/nav_history_gs.py 單獨掃                     → 命中 7 個節點
       把它 import 進 ④ 的渲染路徑（加一行 import 而已）      → 閉包 11 → 57
                                                            → 命中 0 → 106
                                                            → 主規則**當場轉紅**

   → **今天的綠只證明「這 11 個模組裡沒有東西可報」，不證明閘門邏輯是對的。**
   ⚠️ **閘門那一半目前只被合成 fixture 跑過**（:data:`_EVASIONS` 與
   :data:`_REVERSED_GATES`），所以**它的正確性等於那些 fixture 的覆蓋度** ——
   而缺口 **7** 的四種殘留，正是那份覆蓋度照不到的地方。
   ⚠️ **這是登記，不是動工授權**（`CLAUDE.md §-1`）；
   也 ⛔ **不得**被讀成「這條規則沒用」—— 它的射程是真的，只是今天還沒有東西落在射程內。

7. ⛔ **閘門偵測仍有四種已知殘留漏報 —— 逐條寫出來，不要當成保證**
   （2026-09-07 由獨立稽核指出，本組**自行重現**；**新舊完全相同，不是 `#810` 引進的**）。

   **重現方式（端對端，用真守衛，非合成推論）**：把下列片段各自附加到
   ``ui/views/page_04_portfolio.py``（④ 的渲染路徑，本閉包的根）後跑本檔。
   **正對照先行** —— 一個裸寫入 ``ws.append_row(row)`` 與一個 ``if not st.button(): write``
   在同一位置**都會讓主規則轉紅**（實測 ``1 failed, 38 passed``），
   ⛔ 所以下面四格的「全綠」**不是掃描器沒接上，是真的判成有擋住**::

       (1) 指派被覆寫 —— 判定不追值
           _b = st.button("x"); _b = True
           if _b: ws.append_row(row)                      → 39 passed（漏報）

       (2) ⭐ 跨函式意圖變數名污染 —— 四種裡**唯一會在真實程式碼裡自然發生**的
           def a(): _go = st.button("另一顆完全無關的按鈕")
           def b(ws, row, flag):
               _go = flag                                 # 與任何 widget 無關
               if _go: ws.append_row(row)                 → 39 passed（漏報）

       (3) 參數名遮蔽模組層的意圖變數名（(2) 的變體）
           def a(): _go = st.button("elsewhere")
           def b(ws, row, _go):                           # 呼叫端傳什麼都行
               if _go: ws.append_row(row)                 → 39 passed（漏報）

       (4) 非 streamlit 的呼叫，但末段名字撞到意圖元件
           if form.confirm(): ws.append_row(row)          → 39 passed（漏報）
           if x.toggle():     ws.append_rows([row])       （`confirm` / `toggle`
                                                           都在 :data:`_INTENT_WIDGETS`）

   ⚠️ **(2) 為什麼是四種裡最該擔心的那一種，講清楚它會怎麼咬到自己** ——
   前三種看起來都像刻意寫壞的示範，**只有 (2) 是正常人寫正常程式時會長出來的形狀**：
   一個 UI 模組裡本來就會有好幾顆按鈕，而 ``_go`` ／ ``_ok`` ／ ``_do`` ／ ``_submit``
   這種變數名**本來就會在不同函式裡重複使用**。
   :func:`_intent_names` 掃的是**整份模組、沒有作用域** ——
   所以**只要模組裡任何一個角落曾經寫過** ``_go = st.button(...)``，
   從那一刻起，**同模組任何一個** ``if _go:`` 都會被當成「使用者按了按鈕」，
   **即使那個 `_go` 是函式參數、是別的函式的回傳值、是一個 dict 取值、或根本是常數 `True`**。
   → 也就是說：**在別的函式裡加一顆按鈕，會讓一段離它很遠、完全無關的寫入
   從「被守衛盯著」變成「被守衛放行」，而且沒有任何紅燈** ——
   守衛的射程**會被一個看起來毫不相干的改動悄悄縮小**。
   ⚠️ 這正是缺口 **2** 舊表述講反的那一格。

   ⛔ **本批刻意不補這四種**（純文件批次，**不動任何判定邏輯**）。理由與缺口 3 相同：
   要看穿 (1)~(3) 得做**作用域分析與值追蹤**，(4) 得判斷**呼叫對象是不是 streamlit**，
   兩者都是把純語法判定改成資料流判定 —— **那是另一個題目，必須另開一批並重新稽核。**
   ⛔ **絕對不要把這四條讀成「已經守住了」**，也不要順手「補一半」：
   補到一半的追蹤最危險，它會讓人以為這一族已經沒事了。

⚠️ **本檔由執行組單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
   ⚠️ 上列第 3 條的「四種 `getattr` 寫法全綠」、第 6 條的「11 模組 / 0 個 sink 節點」
   與其正對照（7 / 57 / 106）、以及第 7 條的四種殘留
   是**本組實測**（可自行重跑）；但「**除了這四種以外沒有第五種繞道**」
   本組**沒有查證，也不宣稱** —— 那是一句取決於「有沒有漏看」的全稱句。
   ⚠️ 同理，**「閘門偵測只剩這四種漏報」本組也不宣稱** ——
   第 7 條是**已知清單，不是窮舉**。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_PAGE = "ui.views.page_04_portfolio"
#: 閉包只追這幾個頂層套件 —— 其餘（`streamlit` / `pandas` / stdlib）不是本 repo 的程式碼。
_REPO_ROOTS = ("ui", "services", "shared", "repositories", "infra")

#: gspread 試算表物件上的**寫入**方法。
#: ⚠️ 這是**第三方 API 的表面**，不是本 repo 的函式名 —— 所以它不會因為
#:    我們自己改名／取別名而失效。這正是它比「函式名白名單」強的地方。
_SHEET_WRITES: frozenset[str] = frozenset({
    "append_row", "append_rows", "update", "batch_update", "update_cell",
    "update_cells", "update_acell", "insert_row", "insert_rows",
    "add_worksheet", "del_worksheet", "delete_rows", "delete_columns",
    "clear", "resize", "values_append", "values_update", "values_clear",
})
#: 磁碟寫入（本地 JSON / parquet 後端那一路）。
_DISK_WRITES: frozenset[str] = frozenset({
    "write_text", "write_bytes", "mkdir", "makedirs", "touch", "unlink",
    "rmdir", "remove", "rename", "replace", "to_csv", "to_parquet", "to_json",
})
_WRITE_SINKS: frozenset[str] = _SHEET_WRITES | _DISK_WRITES

#: ⭐ **具名偽陽性豁免 —— 逐行、綁原始碼文字，不是綁行號、也不是整條放寬。**
#:
#: ## 為什麼是這個形狀（本檔自己的「紅了要做什麼」就是這樣寫的）
#:
#: :func:`test_the_page_closure_never_writes_on_render` 的 docstring 逐字寫著：
#: 「紅了要做什麼：看那一行是不是真的會在渲染時跑到。…
#:  **不是** → …**在此處具名豁免**，不要整條放寬。」本常數就是那個「此處」。
#:
#: ## 這一筆是怎麼來的（2026-09-07，實測，可自行重跑）
#:
#: ④ 這一批依客戶路線 (A) 開始委派既有模組，閉包從 **11 → 17** 個模組。
#: 新進來的模組裡，`_WRITE_SINKS` 只命中**一個**節點，而它是::
#:
#:     services/dividend_calendar.py::_pdate
#:         s = str(v or "").strip()[:10].replace("/", "-")
#:
#: —— 一個 **`str.replace`**。它與 `pathlib.Path.replace`（**真的**會覆寫檔案）
#: 同名，而本檔的偵測器**只比對名字**（那正是它比「函式名白名單」強的原因，
#: 也是它必然會有的代價）。
#:
#: ⚠️ **姊妹頁早就踩過同一顆雷，而且它的結論寫得比本檔重**：
#: `tests/test_wf02_health_no_writes.py::_WRITE_PRIMITIVES` 就地寫著 ——
#: 「初版 docstring 寫『寧可多抓不可漏抓（多抓的代價只是多裝一個哨兵）』——
#:   **那句是錯的**：名字比對命中一個無辜的函式…得到的是**偽陽性紅燈**，
#:   而下一個人只會去加豁免。」
#: 它的做法是把 `update` / `clear` / `rename` 這類**歧義名字整批移出字表**，
#: 改用執行期哨兵去守 primitive 本身。
#: ⛔ **本檔刻意不照抄那個做法** —— 那會把 `ws.update(...)`（**真的** Google Sheets 寫入）
#:    一起放掉，而本檔**沒有**接上執行期哨兵那一層（見已知缺口 4）。
#:    **整條放寬的代價比一筆具名豁免大得多。**
#:
#: ## 這個豁免**綁的是原始碼那一行的文字**，不是行號
#:
#: 每一筆 = ``(相對路徑, sink 名, 那一行 strip 之後的原文)``。
#: 檔案一改動那一行，比對就對不上 → **豁免自動失效、主規則當場轉紅**。
#: 由 :func:`test_every_false_positive_exemption_still_points_at_that_exact_line` 釘住。
#: ⛔ **不得**改成綁行號（行號會漂移，漂移之後豁免會落到另一行上，那比沒有豁免更糟）。
#: ⛔ **不得**往這裡加「我覺得它不會跑到」的東西 —— 判準只有一個：
#:    **那一行的接收者在語法上就不可能是檔案系統物件**（這裡是 `str(...)` 的回傳值）。
#:
#: ## ⭐ 2026-09-07：這張表上了兩道鎖（**本節是新增，不是改鬆**）
#:
#: **為什麼非上鎖不可** —— 獨立稽核 2026-09-07 三步實測，本組已自行重現（指令與輸出見 PR）：
#:
#: 1. 把一個**真的** ``pathlib.Path(...).write_text(...)`` 注入 ④ 的渲染路徑
#:    → 主規則**當場轉紅**（`40 passed, 1 failed`）。**偵測器本身是好的。**
#: 2. 在本表**加一行**指向那一行 → **`41 passed, 0 failed`**。
#: 3. 把植入物換成 gspread ``_ws.append_row(...)``
#:    （**客戶永久紅線**：絕對禁止反向寫入他的 Google Sheet）→ **一樣 41/41 全綠**。
#:
#: **零阻力的三個成因（本組逐一實測）**：
#:
#: * 本表**沒有任何計數上限** —— 從 1 筆長到 2 筆，沒有任何東西出聲；
#: * :func:`test_every_false_positive_exemption_still_points_at_that_exact_line`
#:   只逐筆檢查「**檔在、文字在、sink 名還在**」——
#:   一筆**指向真寫入**的豁免，這三項**全部通過**；
#: * :func:`test_the_exemption_does_not_blind_the_detector_to_a_real_write`
#:   當時只看 ``sorted(...)[0]``，新加的那筆**根本不在射程內**（已於本次一併修掉）。
#:
#: → **那兩條巡邏擋的是「死豁免／過期豁免」，不是「不正當的豁免」。**
#:
#: ⚠️ **而本表上方那句「判準只有一個」，在上鎖前只活在這段註解裡** ——
#:    也就是本檔的自我要求（「**豁免的前提要被釘成斷言，不是寫在註解裡自律**」，
#:    見下方自我巡邏段的標頭）**它自己沒有做到**。本次補上：
#:
#: * **鎖一** :func:`test_the_false_positive_exemption_table_is_exact_and_named`
#:   —— **整張表精確相等**（沿用同批 `tests/test_wf04_portfolio_skeleton.py::
#:   test_the_extra_checkbox_allowlist_is_exact_and_named` 的形狀：``==`` 精確相等）。
#:   **多一筆就要有人來改這條測試 —— 那個「要有人來改」就是關卡本身。**
#: * **鎖二** :func:`test_every_exemption_receiver_is_syntactically_not_a_filesystem_object`
#:   —— 把上面那句**判準本身**變成斷言：被豁免那一行的**接收者鏈**必須
#:   根在 ``str(...)`` 或字串字面值上。
#:
#: ⚠️ **兩道鎖為什麼都要，講清楚它們各自擋不住什麼**：
#:    改本表的人**本來就在編輯本檔** —— 鎖一紅了，最順手的「修 CI」動作就是
#:    **把鎖一裡那份字面也一起更新**（兩行的 diff，看起來像例行公事）。
#:    鎖二擋的正是這一步：``append_row`` / ``write_text`` 的接收者是裸 `Name` 或
#:    `Path(...)`，**再怎麼更新鎖一的字面都不會變綠**，只能去砍掉鎖二本身 ——
#:    那是一個**大聲得多**的 diff。
#:    反過來，鎖二對「接收者剛好合格、但其實會跑到」的東西無能為力，那由鎖一的
#:    具名問責擋。**兩者失效的方式不一樣，這正是要兩道的理由。**
#:
#: ⚠️ **鎖二會擋掉一種「其實合理」的未來豁免，這是刻意的**：
#:    例如 ``_d.update(...)``（`_d` 是 dict）或 ``_s.clear()``（set）——
#:    它們確實不是檔案系統寫入，但**從語法上看不出來**（`_d` 是裸名字），
#:    所以**不滿足本表自己寫的判準**。屆時正解是**大聲修改鎖二並在 PR 說明**，
#:    ⛔ **不是**把鎖二放寬成「凡是裸名字都放行」——那等於把整張表交回給自律。
_FALSE_POSITIVE_SINKS: frozenset[tuple[str, str, str]] = frozenset({
    ("services/dividend_calendar.py", "replace",
     's = str(v or "").strip()[:10].replace("/", "-")'),
})

#: 使用者**明示意圖**的 streamlit 元件。寫入只能發生在它們的正分支裡。
#: ⛔ **session 旗標不在此列，而且永遠不會加進來** —— `#800` 的教訓逐字：
#:    session 旗標「只把『每個 session 寫一次』變成『少寫幾次』，
#:    寫入依然發生在使用者沒有表達任何意圖的時候。**少寫幾次不叫切斷。**」
_INTENT_WIDGETS: frozenset[str] = frozenset({
    "button", "form_submit_button", "checkbox", "download_button",
    "toggle", "confirm",
})


# ══════════════════════════════════════════════════════════════════════
# 偵測器
# ══════════════════════════════════════════════════════════════════════

def _mod_path(mod: str) -> "pathlib.Path | None":
    _p = _REPO / (mod.replace(".", "/") + ".py")
    if _p.exists():
        return _p
    _pkg = _REPO / mod.replace(".", "/") / "__init__.py"
    return _pkg if _pkg.exists() else None


def _imports(tree: ast.AST) -> set[str]:
    _out: set[str] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            _out.update(_a.name for _a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.level == 0 and _n.module:
            _out.add(_n.module)
            _out.update(f"{_n.module}.{_a.name}" for _a in _n.names)
    return _out


def _closure(root: str = _PAGE) -> dict[str, pathlib.Path]:
    """`root` 靜態 import 得到的所有 repo 模組。**委派一加，這裡自動變大。**"""
    _seen: dict[str, pathlib.Path] = {}
    _stack = [root]
    while _stack:
        _m = _stack.pop()
        if _m in _seen:
            continue
        _p = _mod_path(_m)
        if _p is None:
            continue
        _seen[_m] = _p
        for _x in _imports(ast.parse(_p.read_text(encoding="utf-8"))):
            if _x.split(".")[0] in _REPO_ROOTS and _x not in _seen:
                _stack.append(_x)
    return _seen


def _intent_names(tree: ast.AST) -> set[str]:
    """被指派成「使用者按了某個東西」的變數名（`_go = st.button(...)`）。"""
    _out: set[str] = set()
    for _n in ast.walk(tree):
        if not isinstance(_n, ast.Assign) or not isinstance(_n.value, ast.Call):
            continue
        try:
            _base = ast.unparse(_n.value.func).split(".")[-1]
        except Exception:                                    # pragma: no cover
            continue
        if _base in _INTENT_WIDGETS:
            _out.update(_t.id for _t in _n.targets if isinstance(_t, ast.Name))
    return _out


def _is_intent_expr(node: ast.AST, intent: set[str]) -> bool:
    """這個運算式**本身**是不是「使用者剛剛按了某個東西」。

    ⭐ **本函式刻意只認兩種形狀，其餘一律回 `False`**（＝判成「沒被擋住」）::

        st.button("送出")      # ast.Call，func 的最後一段是意圖元件
        _go                    # ast.Name，且它被指派自上面那種呼叫

    ⛔ **為什麼不肯再聰明一點** —— 這正是 `#809` 那個洞的成因。
    舊版判斷閘門的方式是**把 `If` 的 test unparse 成字串，看裡面有沒有 `.button(`**，
    於是下面這一段被判成「有擋住」::

        if not st.button("送出"):
            ws.append_row(row)          # ← 其實**每次渲染都寫**

    字串裡確實有 `.button(`，但那是一個**反向**閘門：沒按的時候才寫。
    也就是舊版在**它自陳「寧可誤報，不可漏報」的方向上漏報**。
    `if _flag or st.button(...)` 是同一個病的另一張臉（不按也可能寫）。

    → 現在的規則是：**test 必須整個就是那個意圖運算式**。
    包了任何一層（`not X` ／ `X and Y` ／ `X or Y` ／ `X == True` ／ 三元式 …）
    一律當成「看不懂」，也就是**沒被擋住**。
    ⚠️ 這對 `if _ready and st.button(...)` 這種**真的有擋住**的寫法會**誤報** ——
    **那是刻意的**，也是本檔唯一可接受的錯誤方向：
    誤報會被人看到並就地處理，漏報只會安靜地放行一次寫入。

    ⛔ **但「只會誤報、不會漏報」對本函式並不成立 —— 讀到這裡不要就走**
    （2026-09-07 實測，四種形狀端對端重現，詳見模組 docstring 缺口 **7**）：
    上面那句講的是**「包了一層」那一類**（`not` ／ `or` ／ `else`），它確實已經收緊了。
    **沒有收緊的是下面那兩個分支各自認得太寬**：

    **(a) `ast.Name` 分支** —— 它只查 `intent` 這個**模組層的名字集合**，
    而 :func:`_intent_names` **掃整份模組、沒有作用域概念**。於是：

    * `_b = st.button(...)` 之後 `_b = True`，`if _b:` 仍被判成有擋住（指派覆寫不追）；
    * **模組裡任一函式**出現過 `_go = st.button(...)`，**同模組任何** `if _go:`
      都被判成有擋住 —— 即使那個 `_go` 是參數、是別的函式的回傳值、或常數 `True`。

    **(b) `ast.Call` 分支** —— 它只比對 `func` 的**最後一段名字**，
    所以 `form.confirm()` ／ `x.toggle()` 這種**與 streamlit 無關**的呼叫也算意圖。

    ⛔ **不要順手把這幾種「補聰明」** —— 那要做作用域分析與值追蹤，
    是把純語法判定改成資料流判定，**屬另一批、須重新稽核**。
    """
    if isinstance(node, ast.Call):
        try:
            return ast.unparse(node.func).split(".")[-1] in _INTENT_WIDGETS
        except Exception:                                    # pragma: no cover
            return False
    return isinstance(node, ast.Name) and node.id in intent


def _write_refs(tree: ast.AST) -> list[tuple[int, str, bool]]:
    """`(行號, 寫入動作, 有沒有被使用者意圖擋住)` —— **呼叫與傳參都算**。

    ⚠️ **兩種形狀都要收**（缺一就是 `bacfe06` 補過的那個洞）::

        ws.append_row(row)                      # ast.Call    ← 只看這個會漏掉下一行
        _with_quota_retry(ws.append_row, row)   # ast.Attribute（當引數傳出去）
    """
    _parent: dict[int, ast.AST] = {}
    for _n in ast.walk(tree):
        for _c in ast.iter_child_nodes(_n):
            _parent[id(_c)] = _n
    _intent = _intent_names(tree)

    def _gated(node: ast.AST) -> bool:
        """往上找：這個寫入有沒有長在某個 `if <意圖運算式>:` 的**正**分支裡。

        ⚠️ **比對的是 `If.test` 這個節點的形狀，不是它 unparse 出來的字串** ——
        字串比對看不出 `not`，那正是 `#809` 漏報的成因（見 :func:`_is_intent_expr`）。
        ⚠️ `_cur in _up.body` 是刻意的：`else` 分支**不算**被擋住
        （`if st.button(): ... else: ws.append_row(...)` 是沒按才寫）。
        """
        _cur = node
        while id(_cur) in _parent:
            _up = _parent[id(_cur)]
            if (isinstance(_up, ast.If) and _cur in _up.body
                    and _is_intent_expr(_up.test, _intent)):
                return True
            _cur = _up
        return False

    _out: list[tuple[int, str, bool]] = []
    _seen: set[tuple[int, str]] = set()
    for _n in ast.walk(tree):
        if not isinstance(_n, ast.Attribute) or _n.attr not in _WRITE_SINKS:
            continue
        # `ast.Call` 的 func 與被當引數傳出去的裸 `ast.Attribute` 是同一個節點型別，
        # 所以只要掃 Attribute 就兩種都收到了 —— 這正是本函式不掃 `ast.Call` 的原因。
        _key = (_n.lineno, _n.attr)
        if _key in _seen:
            continue
        _seen.add(_key)
        _out.append((_n.lineno, _n.attr, _gated(_n)))
    return _out


# ══════════════════════════════════════════════════════════════════════
# 正對照 —— 偵測器沒瞎
# ══════════════════════════════════════════════════════════════════════

_EVASIONS = '''
import streamlit as st
def a(ws, row):
    ws.append_row(row)                       # 1 直接呼叫
def b(ws, row, wrap):
    wrap(ws.update_cell, row)                # 2 當引數傳出去（沒有 Call 節點）
    # ⚠️ 這裡刻意用 `update_cell` 而不是 `append_row` —— 下面的斷言比對的是**集合**，
    #    若第 1、2 種用同一個方法名，第 2 種被漏掉時集合**不會變**，斷言就抓不到。
    #    （本註是突變測試 M7 當場打出來的：初版兩處都用 `append_row`，
    #      把偵測器改成只看 `ast.Call` 之後**測試照樣全綠**。）
def c(ws, row):
    if st.session_state.get("done"): return  # 3 session 旗標**不算**閘門
    ws.append_rows([row])
def c2(ws, row):
    # 3b ⭐ `#800` 的真實形狀：寫入**就長在** session 旗標的正分支裡。
    #     這一格必須被判成「**沒有**被擋住」——「少寫幾次」不叫切斷。
    #     （本案例是突變測試 M8 當場逼出來的：初版只有 c()，而那裡的寫入在
    #       early-return 的 `if` **外面**，所以把 session_state 加進閘門判準時
    #       **測試照樣全綠** —— 等於這條規則從來沒被驗過。）
    if not st.session_state.get("snapshot_done"):
        ws.insert_row(row)
def d(p, text):
    p.write_text(text)                       # 4 磁碟
def gated(ws, row):
    if st.button("存"):                      # 這一個**應該**被判成有擋住
        ws.append_row(row)
'''


def test_the_detector_sees_the_four_evasions():
    """⭐ **正對照：四種寫法都要被抓到，而且 `st.button` 那一個要被判成「有擋住」。**

    ⚠️ **這條為什麼是本檔最重要的一條**：主規則
    （:func:`test_the_page_closure_never_writes_on_render`）的形狀是
    「掃到的未擋住寫入 == 空集合」—— 那個形狀在**偵測器變瞎的時候恆真**。
    偵測器壞掉的那一天，主規則會安靜地全綠。**空掃就是最危險的那種綠燈。**

    第 2 種（當引數傳出去）與第 3 種（session 旗標不算閘門）
    **是本檔相對既有守衛真正多守到的東西**，不是湊數。
    """
    _refs = _write_refs(ast.parse(_EVASIONS))
    _ungated = sorted({_a for _l, _a, _g in _refs if not _g})
    assert _ungated == ["append_row", "append_rows", "insert_row",
                        "update_cell", "write_text"], (
        "偵測器沒有抓到全部四種規避寫法。\n"
        f"實際抓到（未被擋住的）：{_ungated}\n"
        "⛔ 特別注意第 2 種 `wrap(ws.append_row, row)` —— 它沒有 `ast.Call` 節點，"
        "只掃 `ast.Call` 的偵測器看不到它。")
    _gated = sorted({_a for _l, _a, _g in _refs if _g})
    assert _gated == ["append_row"], (
        f"`if st.button(...)` 那一個應該被判成「有擋住」，實際：{_gated}\n"
        "閘門偵測壞了 —— 它會把合法的按鈕寫入也報成違規，"
        "然後有人為了讓 CI 綠而把整條守衛放寬。")


#: ⭐ **反向／放寬閘門的正對照。`#809` 的漏報就住在這裡。**
#:
#: 每一格用**不同的** sink 名字，理由與 :data:`_EVASIONS` 的 M7 註記相同：
#: 名字撞在一起時，漏掉其中一格**集合不會變**，斷言就抓不到。
_REVERSED_GATES = '''
import streamlit as st
def not_button(ws, row):
    # ⛔ `#809` 的漏報形狀：字串裡有 `.button(`，但它是**反向**閘門 —— 每次渲染都寫。
    if not st.button("送出"):
        ws.append_row(row)
def not_name(ws, row):
    # 同上，換成「先存成變數再 `if not`」。
    _go = st.button("送出")
    if not _go:
        ws.append_rows([row])
def or_widened(ws, row):
    # `or` —— 沒按也可能寫。
    if st.session_state.get("f") or st.button("送出"):
        ws.insert_row(row)
def else_branch(ws, row):
    # `else` —— 沒按才寫。
    if st.button("送出"):
        pass
    else:
        ws.update_cell(1, 1, row)
def and_narrowed(ws, row):
    # ⚠️ `and` —— 這一格**真的被擋住了**，本檔仍刻意判成「沒擋住」。
    #    這是本檔唯一**已知且接受**的誤報，理由見 `_is_intent_expr` 的 docstring。
    if st.session_state.get("f") and st.button("送出"):
        ws.update_acell("A1", row)
def really_gated(ws, row):
    if st.button("送出"):
        ws.batch_update([row])
def really_gated_name(ws, row):
    _go2 = st.button("送出")
    if _go2:
        ws.values_update(row)
'''


def test_a_reversed_or_widened_gate_is_not_treated_as_a_gate():
    """⭐ **`#809` 漏報的回歸釘 —— 反向／放寬的閘門一律不算閘門。**

    ## 這條為什麼存在（病史，不要刪）

    `#809` 的閘門偵測是**把 `If.test` unparse 成字串，看裡面有沒有 `.button(`**。
    於是下面這段被判成「有擋住」，而它**每次渲染都寫**::

        if not st.button("送出"):
            ws.append_row(row)

    也就是那道守衛在**它自陳「寧可誤報，不可漏報」的方向上漏報**
    —— 比沒有守衛更糟，因為後面的人會信它。
    ⚠️ 這個 idiom 在本 repo **有前科**：`ui/tab_fund_grp_health.py` 與
    `ui/helpers/fund_grp_health/switch_advisor_section.py` 兩處都留著
    「原 `if not st.button(): return` 的**致命 bug**」的就地註解。**它不是理論上的角落。**

    ## 這條釘住什麼

    * **五種不算閘門**：`not <呼叫>` ／ `not <變數>` ／ `or` ／ `else` 分支 ／
      以及 `and`（**它其實真的擋住了，我們刻意誤報** —— 見 :func:`_is_intent_expr`）。
    * **兩種算閘門**：`if st.button(...)` 與 `if _go:`（`_go` 指派自意圖元件）。
      ⚠️ 這兩格是**反向保險**：少了它們，一個「一律回 False」的偵測器
      也能通過上半段，而那會讓主規則變成整片誤報，接著就有人來放寬它。
    """
    _refs = _write_refs(ast.parse(_REVERSED_GATES))
    _ungated = sorted({_a for _l, _a, _g in _refs if not _g})
    _gated = sorted({_a for _l, _a, _g in _refs if _g})
    assert _ungated == ["append_row", "append_rows", "insert_row",
                        "update_acell", "update_cell"], (
        f"反向／放寬的閘門被當成閘門了 —— 實際判成「沒擋住」的只有：{_ungated}\n"
        "⛔ 這正是 `#809` 的漏報：閘門偵測若比對 unparse 出來的**字串**，"
        "`not st.button(...)` 裡面一樣有 `.button(`。**要比對 `If.test` 的節點形狀。**")
    assert _gated == ["batch_update", "values_update"], (
        f"正向閘門被判成沒擋住了，實際：{_gated}\n"
        "偵測器變成「一律回 False」——主規則會整片誤報，"
        "接下來就會有人為了讓 CI 綠而把整條守衛放寬。")


def test_the_detector_finds_real_writes_in_a_known_writer():
    """正對照之二：拿 repo 內**真的會寫**的模組跑一次，必須抓到東西。

    ⚠️ 上一條用的是本檔自己寫的合成字串 —— 一個只看得懂自己 fixture 的偵測器
    也能過那一關。本條改用**真實程式碼**（`services/nav_history_gs.py`，
    它就地記載自己會 `add_worksheet` / `ws.update` / `append_rows`）。
    """
    _p = _REPO / "services" / "nav_history_gs.py"
    assert _p.exists(), f"正對照的檔案不見了：{_p}（改名了就換一個真的會寫的模組）"
    _found = {_a for _l, _a, _g in _write_refs(ast.parse(_p.read_text(encoding="utf-8")))}
    for _expect in ("add_worksheet", "update", "append_rows"):
        assert _expect in _found, (
            f"偵測器在一個已知會寫的模組裡找不到 `{_expect}` —— 它瞎了。\n"
            f"找到的：{sorted(_found)}")


def test_the_closure_is_not_empty_and_contains_the_page_itself():
    """正對照之三：閉包非空，而且真的含本頁與幾個已知一定會被拉進來的模組。"""
    _c = _closure()
    assert _PAGE in _c, f"閉包裡沒有本頁自己 —— `{_PAGE}` 解析失敗了？"
    assert len(_c) >= 5, (
        f"閉包只有 {len(_c)} 個模組，太小了，主規則會空轉。\n掃到：{sorted(_c)}")
    for _anchor in ("ui.helpers.render_state", "ui.helpers.ia.gated_form"):
        assert _anchor in _c, (
            f"閉包裡沒有 `{_anchor}` —— import 追蹤壞了。\n掃到：{sorted(_c)}")


# ══════════════════════════════════════════════════════════════════════
# 主規則
# ══════════════════════════════════════════════════════════════════════

def test_the_page_closure_never_writes_on_render():
    """⭐ **本檔的本體：④ 這一頁 import 得到的任何地方，都不得在渲染期寫入。**

    「渲染期」＝**沒有被使用者明示意圖擋住**。寫入只能長在
    `if st.button(...)` / `if st.form_submit_button(...)` 這種正分支裡。

    **紅了要做什麼**：看那一行是不是真的會在渲染時跑到。
    - 是 → **修程式，把它移到按鈕的正分支裡**（`#800` 的修法）。
    - 不是（例如閘門用了本檔看不懂的寫法）→ 那是本檔的已知缺口 2，
      **在被測模組就地寫清楚，並在此處具名豁免**，不要整條放寬。

    ⛔ **絕對不要**用「加一個 session 旗標」來讓本條變綠 ——
       :data:`_INTENT_WIDGETS` 刻意不收 session 旗標，理由見該常數。
    """
    _bad: list[str] = []
    for _mod, _path in sorted(_closure().items()):
        _src = _path.read_text(encoding="utf-8").splitlines()
        _tree = ast.parse("\n".join(_src))
        _rel = str(_path.relative_to(_REPO))
        for _line, _attr, _gated in _write_refs(_tree):
            if _gated:
                continue
            _text = _src[_line - 1].strip() if 0 < _line <= len(_src) else ""
            if (_rel, _attr, _text) in _FALSE_POSITIVE_SINKS:
                continue          # 具名偽陽性，見 `_FALSE_POSITIVE_SINKS` 的長註
            _bad.append(
                f"{_rel}:{_line}  `.{_attr}(…)`  （模組 {_mod}）")
    assert not _bad, (
        "④ 的 import 閉包裡有**沒有被按鈕擋住**的寫入動作 —— "
        "使用者只是打開這一頁，它就會動到磁碟或他的 Google Sheet：\n  "
        + "\n  ".join(_bad)
        + "\n\n客戶 2026-09-06 永久授權逐字：「絕對禁止反向寫入我的 Google Sheet…"
          "不用問我，直接切斷寫入！」")


# ══════════════════════════════════════════════════════════════════════
# 哨兵機制 —— 記名、不拋例外
# ══════════════════════════════════════════════════════════════════════

class _Recorder:
    """把一個物件包起來：**寫入方法被碰到就記一筆，然後安靜地回 None**。

    ⭐ **為什麼不 `raise`**（本類別存在的全部理由）：
    會拋例外的哨兵，遇到 ``try/except Exception`` 就被吃掉了 ——
    守衛沒響、畫面一切正常、而那一筆寫入**照樣送出去了**。
    **記名不拋** 讓呼叫端無從吞掉它：`records` 是外部可讀的證據。
    """

    def __init__(self, inner: object = None) -> None:
        self.records: list[str] = []
        self._inner = inner

    def __getattr__(self, name: str):
        if name in _WRITE_SINKS:
            def _noop(*_a, **_kw):
                self.records.append(name)
                return None
            return _noop
        return getattr(self._inner, name)


def test_the_sentinel_records_instead_of_raising():
    """哨兵被碰到時**記一筆並回 None**，不得拋例外。"""
    _ws = _Recorder()
    _ws.append_row(["a"])
    _ws.update("A1", [["b"]])
    assert _ws.records == ["append_row", "update"], (
        f"哨兵沒有記到兩筆寫入，實際：{_ws.records}")


def test_a_swallowing_caller_cannot_hide_a_write():
    """⭐ 呼叫端包了 ``try/except Exception`` 也藏不住 —— 這就是「不拋例外」的用處。

    ⚠️ **對照組（會 `raise` 的哨兵在這裡就失效了）**：若哨兵改成拋例外，
    下面這個 ``except Exception: pass`` 會把它整個吃掉，
    `records` 是空的、測試通過、而寫入其實發生過。
    """
    _ws = _Recorder()
    try:
        _ws.append_rows([["x"]])
    except Exception:            # noqa: BLE001  ← 這正是實務上會出現的吞法
        pass
    assert _ws.records == ["append_rows"], (
        "呼叫端的 `try/except` 把哨兵吃掉了 —— 哨兵不能靠拋例外來報告。")


def test_the_sentinel_also_catches_a_write_passed_as_an_argument():
    """⭐ 把寫入方法**當引數傳給包裝器**，哨兵一樣要記到。

    這是執行期版本的「`ast.Attribute` 那一半」——
    對應 `_with_quota_retry(ws.append_row, ...)` 這種真實寫法。
    """
    _ws = _Recorder()

    def _with_quota_retry(fn, *args):
        return fn(*args)

    _with_quota_retry(_ws.append_row, ["y"])
    assert _ws.records == ["append_row"], (
        "把寫入方法當引數傳出去之後，哨兵沒記到 —— "
        "那正是 `bacfe06` 補過的那個形狀。")


@pytest.mark.parametrize("sink", sorted(_SHEET_WRITES | _DISK_WRITES))
def test_every_declared_sink_is_actually_intercepted(sink: str):
    """:data:`_WRITE_SINKS` 裡宣告的每一個名字，哨兵都要真的攔得到。

    ⚠️ 擋的是「清單上寫了、但攔截邏輯漏掉」這種**宣告與實作不同步**：
    一個只寫在常數裡、實際沒被攔的名字，會讓讀表的人以為它被守住了。
    """
    _r = _Recorder()
    getattr(_r, sink)()
    assert _r.records == [sink], f"`{sink}` 宣告在 `_WRITE_SINKS` 裡，但哨兵沒攔到它。"


# ══════════════════════════════════════════════════════════════════════
# 具名偽陽性豁免的**自我巡邏**（2026-09-07）
# ⚠️ 一個「開了就沒人再看」的豁免，就是 `CLAUDE.md §8.2.A.0` 規則 5 點名的那種
#    **把違憲寫成合憲**。所以豁免的前提要被釘成斷言，不是寫在註解裡自律。
# ══════════════════════════════════════════════════════════════════════

def test_every_false_positive_exemption_still_points_at_that_exact_line():
    """⭐ 每一筆豁免的**那一行原文**都要還在原檔裡，而且該行真的被偵測器命中。

    兩件事一起驗，缺一邊豁免就會變成一張空頭支票：

    1. **那一行還在** —— 檔案改了那一行 ⇒ 對不上 ⇒ 豁免自動失效（主規則會轉紅）。
       ⛔ 這正是**綁文字而不綁行號**的理由：行號會漂，漂到別行上就是替另一段程式碼背書。
    2. **偵測器真的會命中它** —— 若哪天 `replace` 從 :data:`_WRITE_SINKS` 移除，
       這一筆就是**死豁免**；死豁免會讓下一個人以為那條路徑「已經審過了」。

    ⚠️ 第 2 點紅了**不是**要去刪這條測試，是要去刪那一筆豁免（它不再需要）。
    """
    for _rel, _attr, _text in sorted(_FALSE_POSITIVE_SINKS):
        _p = _REPO / _rel
        assert _p.exists(), (
            f"豁免指到一個不存在的檔案：{_rel}\n"
            "⛔ 這不是「測試過期」：檔案不在了，那筆豁免就是在替空氣背書，請刪掉它。")
        _lines = [_l.strip() for _l in _p.read_text(encoding="utf-8").splitlines()]
        assert _text in _lines, (
            f"豁免登記的那一行原文在 {_rel} 裡找不到了：\n  {_text}\n"
            "⛔ 那一行被改過了 —— 請重新判斷它現在是不是還是偽陽性，"
            "**不要**直接把新的文字貼進 `_FALSE_POSITIVE_SINKS` 了事。")
        assert _attr in _WRITE_SINKS, (
            f"`{_attr}` 已經不在 `_WRITE_SINKS` 裡了 —— "
            f"{_rel} 那一筆豁免變成**死豁免**，請刪掉它（死豁免會讓人以為那條路徑審過了）。")


def test_the_exemption_does_not_blind_the_detector_to_a_real_write():
    """⭐ **正對照：豁免只認「那一個檔 ＋ 那一個名字 ＋ 那一行文字」，三者缺一就不放行。**

    ⛔ 沒有這一條，`_FALSE_POSITIVE_SINKS` 有可能被寫成「凡是 `.replace` 都放行」
    而**沒有任何東西會發現** —— 那會讓 `pathlib.Path.replace`（真的會覆寫檔案）
    整族隱形。本條用三個**只差一項**的變體去戳它。

    ⚠️ **2026-09-07 就地更正：本條原本只戳** ``sorted(_FALSE_POSITIVE_SINKS)[0]``
    （**有意識的更正，不是漏刪** · 日期 **2026-09-07** ·
    決策者 **品管與 CI 守衛組（依獨立稽核實測）**）。舊寫法逐字::

        _rel, _attr, _text = sorted(_FALSE_POSITIVE_SINKS)[0]

    **舊寫法在只有一筆豁免時完全正確** —— 被權衡掉的是它的**前提**：
    表一旦長到兩筆，它就只驗得到排最前面那一筆。**兩個方向都實測過**：

    * 新豁免排在**後面**（``ui/views/...`` > ``services/...``）→ 新的那筆**完全沒被驗到**；
    * 新豁免排在**前面**（``infra/...`` / ``repositories/...`` < ``services/...``）
      → 更糟：它**擠掉**原本那筆，於是**真正該被驗的那筆反而沒被驗**，
      而末尾那句「反向保險」變成在替**植入物**背書。

    → 現行：**逐筆驗**，位置不再影響射程。非空保險改成獨立的一句。
    """
    assert _FALSE_POSITIVE_SINKS, (
        "豁免集合是空的 —— 下面的迴圈在空集合上恆真，等於這條正對照沒有驗到東西。")
    for _rel, _attr, _text in sorted(_FALSE_POSITIVE_SINKS):
        _variants = [
            ("換一個檔", (_rel + "x", _attr, _text)),
            ("換一個 sink 名", (_rel, "write_text" if _attr != "write_text" else "to_csv", _text)),
            ("換一行文字", (_rel, _attr, _text + "  # 動過了")),
        ]
        for _label, _v in _variants:
            assert _v not in _FALSE_POSITIVE_SINKS, (
                f"豁免比對太寬：{_rel} 那一筆，{_label} 之後竟然還在豁免集合裡 —— {_v}")


# ══════════════════════════════════════════════════════════════════════
# ⭐ 豁免表本身的兩道鎖（2026-09-07 新增）
#
# 上面那三條巡邏擋的是**死豁免／過期豁免**（檔不見了、那一行被改了、sink 名被拿掉了）。
# 它們**擋不住「不正當的豁免」** —— 一筆指向**真寫入**的豁免，三項全部通過。
# 獨立稽核 2026-09-07 實測：加一行就能讓 `Path(...).write_text(...)` 與 gspread
# `append_row(...)` 兩者都變成 41/41 全綠（本組已自行重現，見 `_FALSE_POSITIVE_SINKS` 的長註）。
# 下面兩條補的就是那個口。
# ══════════════════════════════════════════════════════════════════════

def test_the_false_positive_exemption_table_is_exact_and_named():
    """⭐ **鎖一：整張豁免表精確相等 —— 多一筆就要有人來改這條測試。**

    ## 這條是「加一筆豁免」與「偷偷把違憲寫成合憲」的分界線

    形狀**刻意沿用同批** ``tests/test_wf04_portfolio_skeleton.py::
    test_the_extra_checkbox_allowlist_is_exact_and_named``（那條把放行清單釘成
    ``== (DIVCAL_GATE_LABEL,)``）。**同一個病，用同一把鎖**：

    一個「開了就沒人再看」的放行口，就是 ``CLAUDE.md §8.2.A.0`` 規則 5 點名的
    **把違憲寫成合憲**。本檔自我巡邏段的標頭逐字寫著
    「**豁免的前提要被釘成斷言，不是寫在註解裡自律**」——
    ⚠️ 而在本條之前，**那個判準本身（「接收者在語法上不可能是檔案系統物件」）
    只活在註解裡**。也就是這張表**自己違反自己那句話**。

    ## 釘住三件事

    1. 表**不是空的**（空表會讓上面三條巡邏全部在空集合上恆真）；
    2. 表**恰好就是**那一筆已知的 `str.replace` 偽陽性 —— 逐字、精確相等；
    3. 表裡**沒有任何一筆指到 ④ 這一頁自己**
       —— 頁面是閉包的**根**，它自己的寫入永遠不會是「別的模組的偽陽性」，
       而稽核的兩顆植入物正是放在那裡。

    ⛔ **本條看不到什麼（照實寫，不要讀成「守死了」）**：
    改本表的人**本來就在編輯本檔**，所以他可以「加一筆 ＋ 順手更新本條的字面」——
    兩行的 diff。**擋那一步的是鎖二**
    （:func:`test_every_exemption_receiver_is_syntactically_not_a_filesystem_object`），
    不是本條。**兩條要一起讀。**
    """
    assert _FALSE_POSITIVE_SINKS, (
        "豁免表是空的 —— 三條自我巡邏會在空集合上恆真，等於整組關卡沒有驗到東西。\n"
        "⛔ 若那一筆偽陽性真的不再需要，請連同本條一起刪，不要只把表清空。")
    _expected = frozenset({
        ("services/dividend_calendar.py", "replace",
         's = str(v or "").strip()[:10].replace("/", "-")'),
    })
    assert _FALSE_POSITIVE_SINKS == _expected, (
        "豁免表被改動了。\n"
        f"  現在：{sorted(_FALSE_POSITIVE_SINKS)}\n"
        f"  預期：{sorted(_expected)}\n"
        "⛔ **每多一筆豁免，就是在主規則上開一個洞，所以要有人來改這條測試 —— "
        "那個「要有人來改」就是這道關卡本身。**\n"
        "加之前先回答：那一行的**接收者在語法上**真的不可能是檔案系統物件嗎？"
        "（那是本表唯一的判準，由鎖二強制執行）")
    for _rel, _attr, _text in sorted(_FALSE_POSITIVE_SINKS):
        assert _rel != _PAGE.replace(".", "/") + ".py", (
            f"有一筆豁免指到 ④ 這一頁自己（{_rel}）。\n"
            "⛔ 本頁是閉包的**根** —— 它自己的寫入不可能是「別的模組的偽陽性」，"
            "而那正是 2026-09-07 稽核植入物放的位置。這種豁免一律不得存在。")


def _exempted_attribute_nodes(rel: str, attr: str, text: str) -> list[ast.Attribute]:
    """找出被豁免那一行上、名字相符的 `ast.Attribute` 節點。

    ⚠️ **行號解析規則刻意與主規則一致** —— 主規則
    (:func:`test_the_page_closure_never_writes_on_render`) 是拿 ``_n.lineno``
    去查 ``_src[_line - 1].strip()``。本函式用**同一條規則**，
    否則兩邊可能對「哪一行」有不同看法，鎖就會驗到別的東西。
    """
    _src = (_REPO / rel).read_text(encoding="utf-8").splitlines()
    _tree = ast.parse("\n".join(_src))
    _out = []
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.Attribute) or _n.attr != attr:
            continue
        _line = _n.lineno
        if 0 < _line <= len(_src) and _src[_line - 1].strip() == text:
            _out.append(_n)
    return _out


def _receiver_root(node: ast.Attribute) -> ast.AST:
    """從 `x.y.z[0].sink` 一路往下走到**接收者鏈的根**。

    走法：`Attribute` → `.value`；`Subscript` → `.value`；`Call` → `.func`，
    但 ``str(...)`` 是這條鏈**合法見底**的地方，碰到就直接回傳它。

    實例（本表現有那一筆）::

        str(v or "").strip()[:10].replace("/", "-")
        └ .replace → Subscript → Call(.strip) → Attribute(strip) → Call(str)  ← 根

    反例::

        _ws.append_row(row)                    → 根是 Name('_ws')            ✗
        _pathlib.Path("x").write_text("y")     → 根是 Name('_pathlib')       ✗
    """
    _cur: ast.AST = node.value
    while True:
        if isinstance(_cur, ast.Attribute):
            _cur = _cur.value
        elif isinstance(_cur, ast.Subscript):
            _cur = _cur.value
        elif isinstance(_cur, ast.Call):
            if isinstance(_cur.func, ast.Name) and _cur.func.id == "str":
                return _cur                      # 合法見底
            _cur = _cur.func
        else:
            return _cur


def test_every_exemption_receiver_is_syntactically_not_a_filesystem_object():
    """⭐ **鎖二：把本表的判準本身變成斷言，不再只是註解裡的自律。**

    :data:`_FALSE_POSITIVE_SINKS` 的長註逐字寫著判準只有一個 ——
    「**那一行的接收者在語法上就不可能是檔案系統物件**（這裡是 ``str(...)`` 的回傳值）」。
    ⚠️ 在本條之前，**那句話沒有任何東西在執行它**。
    本檔自己的標頭又寫著「豁免的前提要被釘成斷言，不是寫在註解裡自律」——
    **本條就是那句話的可執行版本。**

    ## 判準（逐字實作，不多不少）

    被豁免那一行的**接收者鏈**，往下走到底必須是下列兩者之一：

    * ``str(...)`` 的呼叫（本表現有那一筆就是這種）；
    * **字串字面值**（``"a/b".replace(...)``）。

    其餘一律**不合格** —— 尤其是裸名字（``_ws.append_row``）與
    ``Path(...)``（``_pathlib.Path("x").write_text("y")``）。

    ## 這條真正擋住的是什麼（鎖一擋不住的那一步）

    改本表的人**本來就在編輯本檔**：鎖一紅了，最順手的「修 CI」動作是
    **連同鎖一裡那份字面一起更新**，兩行的 diff、看起來像例行公事。
    **本條讓那一步無效** —— ``append_row`` / ``write_text`` 的接收者是裸 `Name`
    或 ``Path(...)``，**再怎麼更新鎖一的字面都不會變綠**，
    只能去砍掉本條本身，而那是一個**大聲得多**的 diff。

    ## ⛔ 本條看不到什麼（不要讀成「守死了」）

    * **只看語法，不看語意** —— ``str`` 這個名字若在該模組被遮蔽
      （``str = something_else``），本條會被騙。本組**沒有**追值的來源，
      也**不打算**追（同本檔缺口 3／7 的理由：半套的靜態追蹤最危險）。
    * **不判斷那一行會不會真的跑到** —— 那一半由鎖一的具名問責擋。
    * 找不到節點時**一律判失敗（fail closed）** —— 驗不了就不背書。
    * ⛔ **本條沒有守住 :func:`_receiver_root` 自己** —— 把那支改成永遠回一個
      ``str(...)`` 節點，本條就會全綠。**這一族「誰來守守衛」的遞迴，本檔一律不追**
      （`_is_intent_expr` / `_intent_names` 同樣沒有人守），
      理由是它沒有底 —— 擋它的是**那種 diff 很大聲**，不是機器。
      ⛔ **不要把這一條讀成「所以上鎖沒有用」**：上鎖前是**加一行**就能放行真寫入
      （2026-09-07 實測 41/41 全綠），上鎖後**必須動判定邏輯本身**。
      **兩者的可見度差一個數量級，那正是這兩道鎖買到的東西。**
    """
    assert _FALSE_POSITIVE_SINKS, (
        "豁免表是空的 —— 下面的迴圈恆真，本條沒有驗到任何東西。")
    for _rel, _attr, _text in sorted(_FALSE_POSITIVE_SINKS):
        # ⚠️ 自己驗檔案在不在，**不要**倚賴巡邏一先跑過 —— pytest 各條測試獨立，
        #    少了這一句，檔案被改名時本條會噴 `FileNotFoundError`（仍是紅的，
        #    fail closed 沒破，但訊息看不出發生什麼事）。
        assert (_REPO / _rel).exists(), (
            f"豁免指到一個不存在的檔案：{_rel}\n"
            "⛔ 檔案不在了，那筆豁免就是在替空氣背書，請刪掉它。")
        _nodes = _exempted_attribute_nodes(_rel, _attr, _text)
        assert _nodes, (
            f"在 {_rel} 裡找不到 `.{_attr}` 長在這一行上：\n  {_text}\n"
            "⛔ **驗不到就不背書（fail closed）** —— 這一筆豁免無法被本條檢查，"
            "請確認它指的位置，不要繞過本條。")
        for _n in _nodes:
            _root = _receiver_root(_n)
            _ok_str_call = (isinstance(_root, ast.Call)
                            and isinstance(_root.func, ast.Name)
                            and _root.func.id == "str")
            _ok_literal = (isinstance(_root, ast.Constant)
                           and isinstance(_root.value, str))
            assert _ok_str_call or _ok_literal, (
                f"豁免不合格：{_rel}:{_n.lineno} 的 `.{_attr}(…)`\n"
                f"  那一行：{_text}\n"
                f"  接收者鏈的根：{ast.unparse(_root)[:120]}"
                f"（{type(_root).__name__}）\n\n"
                "⛔ 本表的判準逐字是：**那一行的接收者在語法上就不可能是檔案系統物件** ——\n"
                "   也就是接收者鏈必須根在 `str(...)` 或字串字面值上。\n"
                f"   `{ast.unparse(_root)[:60]}` 是一個裸名字／別的呼叫，"
                "從語法上**看不出**它不是 worksheet 或 Path。\n"
                "⛔ 這正是 2026-09-07 稽核用來把 `append_row` / `write_text` "
                "變成全綠的那條路 —— 本條就是為了堵它而存在。\n"
                "⛔ **不要**為了讓 CI 綠而放寬本條；若這一筆真的合理"
                "（例如 dict.update / set.clear），那是一次**要大聲說明**的修改，"
                "請在 PR 描述寫清楚為什麼，並同時更新鎖一。")
