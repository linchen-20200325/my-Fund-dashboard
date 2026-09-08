"""④ 資產配置新頁的骨架守衛 —— 線框 Tab 04 的四塊，一塊都不准少。

錄製法：**用真的 Streamlit 跑（AppTest），不用假的 recorder**
------------------------------------------------------------
① ② ③ 三頁的同型守衛都是「替換模組層的 `st`」錄下呼叫序列 ——
理由是那三頁**當時**尚未接進 `app.py`，`AppTest.from_file("app.py")` 走不到它們。

**本檔改用 `AppTest.from_string()`**：它不需要頁面被接進 `app.py`，
直接把「import 這個 View 並呼叫它」當成一支 script 跑，拿到的是**真的 Streamlit
渲染出來的元素樹**。三個具體好處，每一個都對應到前三頁踩過的坑：

1. **不會有「patch 打歪」的靜默失效。** ③ 的測試檔就地記著：
   `import ui.helpers.ia.empty_state as _e` 拿到的是**函式**不是模組，
   `setattr(_e, "st", …)` 打在函式身上、模組的 `st` 一動也沒動 ——
   **錯的 patch 不會報錯，只會讓斷言對著半份畫面生效。** 本檔沒有 patch，所以沒有這個面。
2. **元素順序是真的順序**（含 `st.columns` 的欄內巢狀），不是我自己拼的字串流。
3. ⭐ **可以真的按下去。** 本檔因此能回答前三頁**回答不了**的那個問題：
   **「照著那句指路做，那一塊真的會離開灰態嗎？」**（見下方「兩種灰的指路，實跑結果不同」）

⚠️ **代價，據實寫**：AppTest 比假 recorder 慢（每次 `run()` 都真的跑一次 script），
   故本檔用 :func:`_stream` 快取三種 session 形狀的渲染結果，同一形狀只跑一次。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**骨架的形狀**：六個單位都在、順序對、沒有持倉時只畫空狀態、
有持倉時五個灰態單位**各自**誠實灰、Form 那一塊**不灰**（它是本批唯一做完的）、
以及線框的示意值一個都沒有畫出來。

⛔ **本檔不守內容對不對** —— 本批的內容**本來就還沒填**。下一批把真內容接上時，
   `test_every_grey_unit_is_grey_until_its_content_lands` 會**轉紅** ——
   **那是預期的**，屆時請把它改成「真內容放行」，**不要把它放寬**。

⛔ **本檔不驗瀏覽器裡的真實版面**：欄寬、窄螢幕折行、真正的 rerun 次數 ——
   AppTest 沒有瀏覽器，那些看不到。

⛔ **本檔不重複既有的全域規則**（`ui/**` 全掃的那幾條會自動涵蓋這個新檔）：
   `tests/test_ui_grid_contract.py`（欄數）、`tests/test_ui_rerun_contract.py`（form 站點）、
   `tests/test_batch2_top_card_grid.py`（`where=` 必填、灰卡要有 remedy）、
   `tests/test_wpf_five_tab_wiring.py`（分頁名不得手抄）、
   `tests/test_ia_switch_advisor_moved_to_portfolio.py`（換股顧問渲染點恰好一個）。
   **在這裡再抄一份等於製造第二把尺**（`CLAUDE.md §2.1`）。

兩種灰的指路，實跑結果不同 —— 這是本檔最重要的一段
--------------------------------------------------
被測檔有兩種灰，文案刻意分開。**本檔把「照著做有沒有用」真的按了一次**：

⚠️ **2026-09-08：這張表少了一列，而少的那一列正是它最想講的那件事。**
下表**原文保留**（它記載 2026-09-06 的實況），新的一列補在後面。

===================== ============================================ ==========
灰的種類               指路指到哪                                    照著做有效嗎
===================== ============================================ ==========
**沒有持倉**（空狀態）  ④ 📊 資產配置 → ➕ 加入與管理基金               ✅ **有效**
~~**內容還沒接上**~~   ~~④ 📊 資產配置 → 再平衡試算~~                 ~~❌ **無效**~~
**內容還沒接上**       各塊**各自**的真實去處（見 :func:`_expected_pointer`）  ✅ **有效**
===================== ============================================ ==========

⛔ **2026-09-08 起，本頁沒有任何一塊灰態的指路是「去了也沒用」的。**
最後一塊（換股顧問）在本輪改指 ``④ 📊 資產配置 → 🎯 換股顧問`` ——
它在舊 ④ **有一個真的在線上跑的家**。
⚠️ **這件事本檔驗不到，據實揭露**（`CLAUDE.md §-2` 規則 6）：本檔的 AppTest
只渲染 `ui/views/page_04_portfolio.py` 這一頁（見 :data:`_SCRIPT`），
**到不了舊 ④**，所以「去了真的有用」在本檔**沒有**被實跑證明。
它由兩條**別的**東西支撐：(a) `tests/test_ia_switch_advisor_moved_to_portfolio.py::`
`test_switch_advisor_renders_only_from_the_portfolio_tab` 把渲染點釘成
**恰好一個**且就在 `ui/tab3_portfolio.py::render_portfolio_tab`；
(b) 本檔的 :func:`test_the_switch_card_points_at_the_place_that_really_renders_it`
用 AST 確認**本頁指的那個地方真的會渲染它** —— 那是 (a) 沒有回答的問題
（(a) 只數渲染點，不管本頁指去哪）。

- ✅ 那一列由 :func:`test_the_empty_state_pointer_actually_works` 實跑：
  照著做（讓 `portfolio_funds` 有已載入的項目）→ 空狀態**真的消失**、四塊**真的出現**。
- ~~❌ 那一列由 :func:`test_the_pending_pointer_is_honest_about_being_ineffective` 實跑：
  照著做（回到再平衡試算、填金額、按「試算」）→ **五條灰態逐字完全相同**。
  ⛔ **這不是 bug，是本批的實況**：這一塊沒接上，去任何地方都不會讓它出現。~~
  → **2026-09-08 狀態變更，不是漏刪**：那一列已經沒有對象了（見上表的更正）。
  該測試**原封保留、斷言一字未改**，只是**改名**為
  :func:`test_the_form_alone_fills_in_no_grey_block` —— 因為它實際在驗的一直都是
  「**按下試算不會把任何一塊灰態變出內容**」，那件事今天依然為真、依然值得釘。
  ⛔ **舊名字是一句會過期的形容詞**（「指路無效」），新名字是它真正的斷言。
  **本檔把它寫成一條會轉紅的斷言，而不是一句形容詞** ——
  哪天它真的變有效了（內容接上了），那條測試會紅，而那正是要人回來改文案的時候。
  ⚠️ **為什麼不乾脆把 `where=` 拿掉**：全域
  `tests/test_batch2_top_card_grid.py::test_where_is_mandatory` 規定
  `not_ready()` / `empty_state()` **一定要帶 `where=`**，而它的豁免表
  `WHERE_MISSING_EXEMPT` 目前是空的、且該檔就地寫著「**應該保持空的**」。
  本批的檔案邊界不含那個檔（也不該為了自己方便去動全域豁免表），
  所以誠實的做法是：**給一個真的地方，然後把「去了沒用」寫成可被驗證的事實。**
  ⚠️ **但那條全域規則的射程比它看起來窄，本組實測**：它的判準是
  ``[... for _f, _ln, _fn, _w in _where_sites() if _w is None]`` ——
  **看的是「`where=` 這個關鍵字在不在」，不是「它是不是空的」**。
  突變 **M16** 把空狀態改成 ``where=""``（關鍵字還在、值是空字串）→
  **七個全域守衛檔 1001 passed 全綠**，只有本檔的
  :func:`test_nothing_renders_before_holdings_land` 抓到（因為它比對的是
  `where_to_find("pf_add")` 這個**實際字串**有沒有印在畫面上）。

⭐ 本檔實測到的**全域守衛盲點**（登記給後人；不是本頁造成的）
------------------------------------------------------------
下面九條突變**各自對七個全域守衛檔跑過一次**
（`test_ui_grid_contract` / `test_ui_rerun_contract` / `test_wpf_five_tab_wiring` /
`test_batch2_top_card_grid` / `test_ia_switch_advisor_moved_to_portfolio` /
`test_ia_kit` / `test_render_state_color_separation`；基線 **1001 passed, 32 skipped**，
量測日 2026-09-05）。**九條裡只有一條讓全域轉紅。**

======= ========================================== ==================== ==========
突變     內容                                        全域七檔              本檔
======= ========================================== ==================== ==========
M28     呼叫換股顧問既有的渲染函式（第二個渲染點）      **1 failed** ✅       4 failed
M03     拿掉交易帳本的 ``empty_where=``               1001 passed（全綠）    1 failed
M06     保單區塊名改成另一份線框的字面                  1001 passed（全綠）    1 failed
M07     換股顧問改成手抄字面、不走 SSOT                1001 passed（全綠）    1 failed
M12     把線框的示意值畫到畫面上                       1001 passed（全綠）    1 failed
M13     本頁自己開一個**合規的** ``st.columns(3)``     1001 passed（全綠）    1 failed
M14     本頁自己開巢狀 ``st.tabs``                     1001 passed（全綠）    1 failed
M16     空狀態的 ``where`` 改成空字串                  1001 passed（全綠）    2 failed
M25     自己拼 ⬜ 字串、不走 ``not_ready()``            1001 passed（全綠）    2 failed
======= ========================================== ==================== ==========

**四條值得單獨記住的**：

- **M13**：`GRID_EXEMPT_CALL_TOTAL` 是精確 `==`，但它數的是「**欄數不是 3**」的呼叫 ——
  **合規的 3 欄它一動也不動**。所以「本頁不得自己開網格」這條**全域沒有網子**。
  （③ 的紅隊 2026-09-05 先發現了這件事；**本組是自己重跑一次確認的，不是轉述。**）
- **M14**：**巢狀 `st.tabs` 在 `ui/views/**` 沒有任何全域守衛。**
  `tests/test_ia_tab4_ledger_flattened.py` 與
  `test_ia_switch_advisor_moved_to_portfolio.py::test_the_moved_block_opens_no_nested_tabs`
  **都只掃它們各自點名的那一個檔**。而「⚠️ 巢狀 `st.tabs` 一律不留」是線框 Tab 04
  「這裡不放什麼」的逐字條文 —— **本頁自己守，別指望全域。**
- **M16**：見上（`where=""` 穿過去了）。
- **M07**：手抄一個**分區**名（不是分頁名）**不會**讓
  `test_wpf_five_tab_wiring.py` 轉紅 —— 它的黑名單是 `_TAB_LABELS` ∪
  `RETIRED_TAB_LABELS` ∪ `MISWRITTEN_TAB_NAMES`，**`_SECTION_LABELS` 不在裡面**。

⛔ **本段是登記，不是動工授權**（`CLAUDE.md §-1`）。要補全域網子是另一批的事，
且依 §-2 規則 4 不該由本組自己承接。

本檔**已知打不到的地方**（照實寫，不要用形容詞蓋過去）
------------------------------------------------------
- ⛔ **語意維（沒有解）**：灰態斷言驗的是**符號**（⬜）與**常數**（`_PENDING_NOTE`），
  **不驗那句話的意思**。把五個單位的灰態理由**互換**、或在灰態裡塞一句
  投資承諾，本檔**一條都不會響**。這是 ② ③ 被獨立紅隊打穿的同一個維度，
  本檔**沒有比它們好**。
- ⛔ **繞道維（只解掉「字面」那一半）**：
  :func:`test_the_page_never_hand_rolls_the_grey_mark` 只擋得住**字面** `⬜`。
  從 SSOT `from ui.helpers.render_state import NOT_READY_MARK` 再自己拼一句 caption、
  或 `chr(0x2B1C)`，**兩種都繞得過**（③ 已登記同一個洞，本檔沒有修）。
- ⛔ **示意值黑名單只有 `_PINNED_FAKE_VALUES` 那幾個字面寫法。**
  裸數字、全形數字、換算成別的寫法、以及**任何線框以外的捏造值**都抓不到 ——
  黑名單結構上抓不到名單外的第 N+1 個。
- ⛔ **指路挑錯 key 沒有守衛**：職責宣告那一句裡的 `health` / `research` 兩個 key
  換成別的**合法** key，本檔不會有任何東西轉紅。
  **這是「走 SSOT」擋不到的那一類**：SSOT 保證名字不過期，**不保證你挑對了 key**。
  （`_pending_where()` 的 `portfolio` 有守，因為 :func:`test_the_pending_pointer_is_a_place`
  比對的是完整字串。）
- ⛔ **`getattr(st, "columns")(3)` / `from streamlit import columns as _c` 繞得過**
  :func:`test_the_page_draws_no_grid_form_or_tabs_of_its_own`
  —— 但全域 `tests/test_ui_grid_contract.py` 對 alias 同樣失明，
  那是 repo 既有性質，不是本頁造成的（③ 已登記）。
- ⛔ **`_holdings()` 對髒值只測到 `None` / 非 list / 缺旗標三種**；
  舊版 payload 形狀沒有測。

線框衝突的裁決狀態（2026-09-05 回填）—— 兩項已決、一項保留給客戶
------------------------------------------------------------------
④ 同時被 `fund-wireframe-final.html`／`policy-split-wireframe.html`／
`ia-wireframe.html` 三份已拍板線框寫過，而三份的**區塊清單幾乎不相交**；
`docs/wireframes/README.md` 明文寫著三者之間的**射程仍未釐清、不替它下結論**。
完整並陳寫在 `ui/views/page_04_portfolio.py` 的模組 docstring；本檔只記與斷言有關的部分：

- ✅ **(A) ia Tab 04 的清單不是窮舉**（總管 2026-09-05）——
  **線框是「版面規範」，不是「功能清單」。**
  → :func:`test_the_empty_state_pointer_actually_works` 指到 `pf_add` **確認正確**，不改。
  ⛔ **這條同時是給後人的一條讀法禁令**：**不得**因為「線框沒列」就推論
  「那個功能不該存在」；反過來也**不得**讀成「線框沒列的都可以自己加」。
- ⏳ **(B) 保單那一塊的版面（3 欄卡 vs 全寬表）—— 保留給客戶，尚未裁決。**
  **本檔不受影響**（骨架階段一張表都沒畫）。
  ⛔ **下一批要把保單明細接上時，動工前必須先有客戶裁決。**
- ✅ **(C) 區塊名照線框字面**（總管 2026-09-05）——
  **裁決結果是「維持現值」，一行都沒改**（`BLOCK_POLICY` 本來就是線框字面）。
  → :func:`test_the_block_names_are_the_wireframe_wording_verbatim` 因此由
  「釘住本批畫成什麼」**升級為「釘住已裁決的結果」**。

⛔ **本檔的斷言是「骨架長得跟 ia Tab 04 一樣」，不是「ia Tab 04 的每一條都是對的」。**
   (B) 一旦裁決下來、且判定保單要走全寬表，**本檔的順序與單位斷言會轉紅 ——
   那時是要改本檔，不是要把它放寬。**
"""
from __future__ import annotations

import ast
import functools
import pathlib
import sys
import re
from typing import Any

import pytest

streamlit_testing = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit < 1.28 不支援 AppTest")
AppTest = streamlit_testing.AppTest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_04_portfolio.py"

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

from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import section_label, where_to_find  # noqa: E402
from ui.views.page_04_portfolio import (  # noqa: E402
    BLOCK_CONCENTRATION,
    BLOCK_DIVIDEND_CAL,
    BLOCK_FORM,
    BLOCK_LEDGER,
    BLOCK_MACRO_LINK,
    BLOCK_MIX,
    BLOCK_POLICY,
    DELEGATED_ENTRIES,
    DELEGATION_BLACKLIST,
    DIVCAL_GATE_LABEL,
    POLICY_TABLE_COLUMNS,
    RETIRED_REASON_POLICY,
    STATUS_BOOK_LABEL,
    STATUS_COLS,
    STATUS_INVESTED_LABEL,
    STATUS_LOADED_AT_LABEL,
    STATUS_POLICY_LABEL,
    SUBMIT_LABEL,
    UNKNOWN_VALUE,
    _DEFAULT_BUDGET_TWD,
    _DEFAULT_CORE_PCT,
    _DEFAULT_SATELLITE_ONLY,
    _LABEL_BUDGET,
    _LABEL_CORE_PCT,
    _LABEL_SATELLITE_ONLY,
    MIX_CURRENT_LABEL,
    MIX_GAP_LABEL,
    MIX_MOVE_TAIL,
    MIX_TARGET_LABEL,
    MIX_TARGET_PROVENANCE,
    REASON_POLICY,
    _ON_TARGET_TOL_PCT,
    _PENDING_NOTE,
    _gap_action_text,
    _holdings,
    _normalise_plan,
    _pending_where,
    grey_why,
    perf_block_label,
    switch_block_label,
)

#: AppTest 跑的 script。**只做兩件事**：把 repo 根加進 `sys.path`、呼叫被測 View。
#: ⚠️ 刻意**不**走 `app.py` —— 本頁本批尚未接線（客戶明令舊 ④ 不動），
#:    `AppTest.from_file("app.py")` 到不了這裡。
_SCRIPT = (
    f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    "from ui.views.page_04_portfolio import render_asset_allocation\n"
    "render_asset_allocation()\n"
)

#: 一份「已載入」的持倉。形狀就是 `ui/helpers/portfolio/load.py` 寫進 session 的那個。
FAKE_HOLDINGS: list[dict[str, Any]] = [
    {"code": "TESTCODE1", "name": "測試標的一", "loaded": True},
    {"code": "TESTCODE2", "name": "測試標的二", "loaded": True},
]

#: **有投入本金**的兩檔 —— 核心／衛星那一格唯一能算出比例的形狀。
#:
#: ⭐ **金額刻意挑成 620000 ／ 380000，這不是隨手填的**：它算出來剛好是
#: **62.0 ／ 38.0**，也就是線框拿來示範版面的那一組示意值
#: （`_PINNED_FAKE_VALUES` 裡的 `"62 ／ 38"`）。
#: 用它當 fixture，是為了讓 :func:`test_a_real_ratio_that_collides_with_the_mock_up_still_passes`
#: 能證明一件事：**真數字剛好長得跟假數字一樣時，示意值黑名單不會誤殺** ——
#: 而那條性質完全繫於 :func:`ui.views.page_04_portfolio._pct_text` 的格式
#: （數字之間夾著 `%` 與抬頭），改掉格式就會當場破功。
#: ⚠️ `policy_tier` 明示 core／satellite，走的是 SSOT 的第一順位分類依據
#: （`resolve_core_flag`：`policy_tier` 優先，缺才退 `is_core` 關鍵字啟發式）。
FAKE_HOLDINGS_PRICED: list[dict[str, Any]] = [
    {"code": "TESTCODE1", "name": "測試標的一", "loaded": True,
     "invest_twd": 620000, "policy_tier": "core"},
    {"code": "TESTCODE2", "name": "測試標的二", "loaded": True,
     "invest_twd": 380000, "policy_tier": "satellite"},
]

#: **部分**填了本金：兩檔有、一檔沒有 —— 「所需動作」那一句要自己說出射程的唯一形狀。
#: ⚠️ 前兩筆與 :data:`FAKE_HOLDINGS_PRICED` **完全相同**（刻意）：
#: 分母、比例、差距、金額全部不變，**唯一的變因是 `n_missing_amount` 由 0 變 1** ——
#: 於是 :func:`test_the_money_says_so_when_it_only_covers_part_of_the_book`
#: 量到的差異只可能來自那一個欄位，不會是別的東西順帶造成的。
FAKE_HOLDINGS_PARTLY_PRICED: list[dict[str, Any]] = [
    *(dict(_f) for _f in (
        {"code": "TESTCODE1", "name": "測試標的一", "loaded": True,
         "invest_twd": 620000, "policy_tier": "core"},
        {"code": "TESTCODE2", "name": "測試標的二", "loaded": True,
         "invest_twd": 380000, "policy_tier": "satellite"})),
    # ⛔ 刻意**沒有** `invest_twd` —— 這一檔進得了檔數、進不了分母。
    {"code": "TESTCODE3", "name": "測試標的三", "loaded": True,
     "policy_tier": "satellite"},
]

#: :data:`FAKE_HOLDINGS_PRICED` 經 `summarize_core_satellite()` 之後的兩個百分比字串。
#: 620000 / (620000+380000) = 62.0%、380000 / 同分母 = 38.0%（實測回傳值）。
#: ⚠️ **有名字才擋得住對調**：舊斷言寫 ``"62.0%" in _body and "38.0%" in _body``，
#: 把核心／衛星互換後兩個字串都還在 ⇒ 綠燈（2026-09-06 稽核存活突變 F1-b，實測 49 passed）。
#: 具名之後，:func:`test_the_mix_block_pairs_each_label_with_its_own_number`
#: 才能寫成「``核心`` 要貼 :data:`_CORE_PCT_TEXT`」這種**配對**斷言。
#: ⚠️ **本檔各處寫的「49 passed」一律指「本檔當時的全部條數」**（本輪新增 2 條前是 49）——
#: **不是**「51 條裡有 49 條過」。那些數字描述的是**加固之前**的狀態，不會隨本檔變長而失效；
#: 現況是 **51 passed**。（會漂移的量測值標清楚口徑，`CLAUDE.md §8.2.A.0` 規則 4。）
_CORE_PCT_TEXT: str = "62.0%"
_SAT_PCT_TEXT: str = "38.0%"


def _reset_streamlit_container_stack() -> None:
    """把 Streamlit 的「目前開著哪個容器」重設回乾淨狀態。

    **為什麼需要這個 —— 這不是儀式，是實測出來的跨檔污染（2026-09-05）。**

    **機制（逐行讀 streamlit 原始碼 + 實跑確認，不是推論）**：

    1. `DeltaGenerator._block()` 開頭有一句
       ``if dg._root_container is None or dg._cursor is None: return dg`` ——
       **bare 模式下 `st._main._cursor is None`，所以 `_block()` 直接把 `st._main`
       自己回傳**，不會產生新的子容器。
       ⚠️ **2026-09-05 就地更正（獨立稽核指出，本組已重跑確認）**：本句原寫
       ~~「`st._main` **兩者皆為 None**」~~ —— **假的**。實測 bare 模式下
       ``st._main._root_container == 0``（**不是 None**）、``st._main._cursor is None``。
       **早退確實會發生，但成立的理由是 `_cursor` 那一半，不是 `_root_container`。**
       ⛔ 這一句當初是用「我量過」的語氣寫的，實際上沒量 —— 記在這裡，不美化。
    2. 於是 `st.form()` 緊接著的
       ``block_dg._form_data = FormData(form_id)``
       **把 form 標記蓋在了行程層級的 `st._main` 這個單例物件上**。
    3. 那個標記**離開 `with` 也不會被清掉**（`__exit__` 只 pop 容器堆疊，
       不還原 `_form_data`）。
       ⚠️ **2026-09-05 同輪更正**：本句原接著寫 ~~「從此 `is_in_form(st._main)` 恆為 True」~~
       —— **也是假的**，實測 bare 模式下它**仍然回 False**。
    4. **⭐ 真正的引爆點在這裡（本輪補上；上面兩句更正之後才看得完整）**：
       `streamlit/elements/lib/form_utils.py::_current_form()` 第一行是
       ``if not runtime.exists(): return None``。
       → **bare 模式沒有 runtime，所以髒標記在 bare 模式下「看不見」，什麼都不會炸；
       但 `AppTest` 底下有 runtime**，`_current_form()` 於是回傳那個殘留的
       `st._main._form_data`，`is_in_form()` 變成 True，下一個 `st.form(` 當場拋。
       **也就是說：污染在 bare 模式無聲寫入，到 AppTest 才引爆** ——
       這正是它能安靜跨檔存活、又只打到有 AppTest 的那些檔的原因。

    複跑（本組實跑，非推論；bare 模式）::

        with applied_form("probe_a"):
            st.slider("s", 0, 10, 5)
        # 離開 with 之後：
        #   st._main._form_data == FormData(form_id="probe_a")   ← 髒了
        #   is_in_form(st._main) == False                        ← 但這裡看不見

    後果：**同一個 pytest 行程裡，之後每一次 `AppTest` 都會看到這個標記**，
    於是任何 `st.form(` 都會撞上 `StreamlitAPIException: Forms cannot be nested
    in other forms.`

    ⚠️ **走過一次的彎路，寫下來免得下一個人重走**：本組第一版只重設
    `context_dg_stack`，**完全無效** —— 因為髒的不是堆疊的「內容」，
    而是堆疊裡那個唯一元素（`st._main`）**自己**。堆疊長度從頭到尾都是 1。

    ⚠️ **這不是本頁獨有的病，也不是本頁用錯 `applied_form`。** 實測：先跑
    `tests/test_wf01_detail_zone_order.py`（它以 bare 模式渲染 ①，①裡有
    `v01_macro_load_form`），再用 `AppTest` 跑 **②③④ 任何一頁**，
    三頁的 form 區塊**都**會掉進同一個紅框。②③ 的測試檔目前不紅，
    只是因為它們沒有一條「不准有紅框」的守衛去看它。

    ⛔ **本函式只是把本檔隔離起來，沒有修掉那個病。** 真正的修法要動
    `ui/helpers/ia/gated_form.py` 或加一支共用 `conftest.py` 的 autouse fixture，
    **兩者都不在本批的檔案邊界內**，已具名回報總管。

    ⚠️ **這道隔離是「活的」，但它的證據本身是順序相依的 —— 據實寫（2026-09-05 獨立稽核指出）**：
    把 ``_main._form_data = None`` 那一行拿掉（保留其餘重設），跑
    ``pytest tests/test_wf01_detail_zone_order.py tests/test_wf04_portfolio_skeleton.py``：

    ===============================  ==================
    順序                              結果
    ===============================  ==================
    ``-p no:randomly``（字母序）       **6 failed, 52 passed**
    ``--randomly-seed=1``             **6 failed, 52 passed**
    ``--randomly-seed=3``             **58 passed**（不轉紅）
    ===============================  ==================

    **seed 3 為什麼不紅（實測，不是推測）**：``--collect-only`` 顯示 seed 3 把
    **`test_wf04` 排在 `test_wf01` 之前** —— 污染還沒發生，本檔就跑完了。
    → **這顆突變不是死的，是順序相依的：3 種順序中 2 種轉紅。**
    ⛔ **本組原本用「單跑一次 → 6 failed」來宣稱它是活的 —— 那不是證據，是抽到一次。**
    這個 repo 裝著 `pytest-randomly` 且預設開啟（`pytest.ini` 的 `addopts` 只有
    `--strict-markers`），**一次綠 / 一次紅都只是一次抽樣**。
    ⚠️ **這正是本檔在講的那種脆弱性，而本組用它來證明自己** —— 記在這裡，不美化。

    ⚠️ **刻意用 fail-loud 的寫法**（§1）：這裡碰的是 Streamlit 的私有名稱，
    哪天改名就會直接 `ImportError` / `AttributeError` 炸開，**不會**靜默跳過。
    靜默跳過等於這道隔離悄悄失效，而失效的樣子跟「本來就沒事」一模一樣。
    """
    from streamlit.delta_generator import context_dg_stack
    from streamlit.delta_generator_singletons import get_dg_singleton_instance

    _main = get_dg_singleton_instance().main_dg
    # 這一行才是關鍵：清掉蓋在單例上的 form 標記（見上面的機制 2/3）。
    _main._form_data = None
    # 堆疊順帶回到乾淨狀態；正常情況它本來就是 `(main_dg,)`。
    context_dg_stack.set((_main,))


def _app(funds: list[dict[str, Any]] | None,
         session: dict[str, Any] | None = None) -> Any:
    """跑一次整頁，回傳 `AppTest`。`funds=None` 代表 session 裡根本沒有那個鍵。

    `session`：額外要塞進 `session_state` 的鍵值（例如 `portfolio_core_pct`）。
    ⚠️ **刻意做成參數而不是在測試裡直接寫 `_at.session_state[...]`** ——
    那樣寫的話 `_app()` 已經 `run()` 過了，設定會**晚一步**、對這一次渲染無效。
    """
    # 進場先洗乾淨：別人留下的 form 容器會讓本頁的 `applied_form` 當場炸掉。
    _reset_streamlit_container_stack()
    _at = AppTest.from_string(_SCRIPT, default_timeout=120)
    for _k, _v in (session or {}).items():
        _at.session_state[_k] = _v
    if funds is not None:
        _at.session_state["portfolio_funds"] = funds
    try:
        _at.run()
    finally:
        # 出場也洗乾淨：本檔不把髒堆疊留給後面跑的測試檔（同一個行程）。
        _reset_streamlit_container_stack()
    assert not _at.exception, (
        "整頁渲染時拋了未捕捉例外 —— 骨架連跑都跑不起來：\n"
        + "\n".join(str(_e.value) for _e in _at.exception))
    return _at


def _rerun(at: Any) -> Any:
    """重跑一次已存在的 `AppTest`（例如按下按鈕之後），同樣先後洗乾淨堆疊。

    ⚠️ **不要直接寫 `_at.run()`** —— 那會繞過 :func:`_reset_streamlit_container_stack`，
    於是「上一次 run 留下的 form 容器」會讓這一次 run 的 `applied_form` 炸掉。
    這一條是本檔唯一允許呼叫 `AppTest.run()` 的地方（連同 :func:`_app`）。
    """
    _reset_streamlit_container_stack()
    try:
        at.run()
    finally:
        _reset_streamlit_container_stack()
    return at


def _flat(node: Any) -> list[str]:
    """把 AppTest 的元素樹壓成**有序**的一串字。

    ⚠️ 回傳 list 而不是一整塊字串 —— 順序本身是本檔要驗的東西之一，
    join 成一坨就驗不了「哪一句落在哪一塊底下」。
    ⚠️ **走 `children` 這個 dict 並依 key 排序**：直接 `for c in block` 會無限遞迴
    （Block 的 `__iter__` 會把自己也走進去），這一點是實跑撞到的，不是推論。
    """
    _out: list[str] = []
    _ch = getattr(node, "children", None)
    if not isinstance(_ch, dict):
        return _out
    for _, _c in sorted(_ch.items()):
        _t = type(_c).__name__
        _v = getattr(_c, "value", None)
        _lbl = getattr(_c, "label", None)
        if _t in ("Markdown", "Caption", "Text", "Header", "Subheader",
                  "Title", "Code", "Info", "Warning", "Error", "Success"):
            _out.append(f"[{_t}] {_v}")
        elif _lbl is not None:
            # widget：**記標籤不記值** —— 值是使用者的東西，標籤才是線框定的。
            _out.append(f"[{_t}] {_lbl}")
        else:
            _out.append(f"[{_t}]")
        _out.extend(_flat(_c))
    return _out


@functools.lru_cache(maxsize=8)
def _stream(kind: str) -> tuple[str, ...]:
    """三種 session 形狀的渲染結果（快取：同一形狀只真的跑一次）。

    - `"empty"`   —— `portfolio_funds` 是空 list
    - `"missing"` —— 根本沒有那個鍵（第一次進站）
    - `"loaded"`  —— 兩檔已載入（**都沒填投入本金**）
    - `"priced"`  —— 兩檔已載入**且填了本金**（核心／衛星算得出比例的唯一形狀）
    """
    _funds = {"empty": [], "missing": None,
              "loaded": FAKE_HOLDINGS, "priced": FAKE_HOLDINGS_PRICED}[kind]
    return tuple(_flat(_app(_funds).main))


def _text(parts: tuple[str, ...] | list[str]) -> str:
    return "\n".join(parts)


#: 一級區塊標題（`st.markdown("#### …")`）。
_L4_OPEN = re.compile(r"^\[Markdown\] #{4}\s+(.*)$")
#: 一張卡的標題 —— `ia.state_card()` 在灰態時畫的 `st.markdown(f"**{title}**")`。
#: ⚠️ **這一條是本檔的最小單位，不是裝飾**（理由見 :func:`_units`）。
_CARD_OPEN = re.compile(r"^\[Markdown\] \*\*(.+)\*\*$")


def _units(parts: tuple[str, ...] | list[str]) -> list[tuple[str, list[str]]]:
    """把渲染流切成**有序**的最小單位：一級段落，或**一張卡**。

    ⚠️ **粒度是「一張卡」，這是被 ② 的一次突變逼出來的，不是設計出來的。**
    `tests/test_wf02_health_skeleton.py::_units` 記著：初版只依 `#### 區塊名` 切段，
    突變「只拿掉其中一塊的灰態」**沒有轉紅** —— 因為同一段裡別張卡的 ⬜ 替它過關了。
    同一個形狀在 ① 被獨立稽核連續打穿兩輪。**答案每次都一樣：把邊界往下降。**

    ⛔ **不要為了讓斷言好寫而把邊界往上收。** 邊界一寬，鄰居的字就會替你通過。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _m = _L4_OPEN.match(_p) or _CARD_OPEN.match(_p)
        if _m:
            _out.append((_m.group(1).strip(), []))
            continue
        if _out:
            _out[-1][1].append(_p)
    return _out


def _segments(parts: tuple[str, ...] | list[str]) -> dict[str, list[str]]:
    """`單位名 -> 該單位內的渲染紀錄`（:func:`_units` 的 dict 檢視）。

    ⚠️ **dict 會讓同名單位後者覆蓋前者** —— 那正是 ② 被紅隊打穿的繞道。
    本檔用 :func:`test_unit_names_are_unique` 把「不會有同名單位」變成一條**斷言**，
    而不是一個假設。
    """
    return {_k: _v for _k, _v in _units(parts)}


def _expected_units() -> tuple[str, ...]:
    """由上而下的**九**個單位。**`換股顧問` 與 `組合績效` 走 SSOT，不在這裡抄字面。**

    ## ⚠️ 2026-09-07：六 → 九，而且**其中一個換了版面**

    客戶 2026-09-07 四項拍板（逐條見被測檔的模組 docstring）：
    - **決定 ①** 把 `保單與扣款標的` 從那一列 3 張卡裡**抽出來變成全寬區塊** ——
      所以它在本序列裡**往後挪了一格**（原本夾在 `換股顧問` 與 `配息月曆` 中間）。
    - **決定 ③** 新增三個具名區塊：組合績效（SSOT）／穿透式持股 ／ 產業集中度／總經曝險聯動。

    ⛔ **本函式的舊 docstring 說「線框 Tab 04 的六個單位」，那句自此不再為真** ——
    現行序列裡有**三個是線框沒有列的**（決定 ③ 那三塊）。
    這**不是**偏離線框：總管 2026-09-05 裁決 (A) 已明訂
    「**線框是版面規範，不是功能清單**；線框沒列 ⇒ 不該存在，這個推論不成立」。
    ⚠️ 但**反過來也不成立**（裁決 (A) 的原文）：**不得**因此主張「線框沒列的都可以自己加」。
    這三塊之所以可以加，是因為**客戶 2026-09-07 逐條點名要它們**。
    """
    return (BLOCK_MIX, BLOCK_FORM,
            switch_block_label(), BLOCK_DIVIDEND_CAL,
            BLOCK_POLICY,
            perf_block_label(), BLOCK_CONCENTRATION, BLOCK_MACRO_LINK,
            BLOCK_LEDGER)


#: **已經接上真資料、因此不該再有「本頁分批上線」那句話**的單位。
#: ⚠️ 每從這裡多一個名字，就要有一條**正向**守衛接手它
#: （`BLOCK_FORM` → :func:`test_the_form_block_is_not_grey`；
#:  `BLOCK_MIX` → :func:`test_the_mix_block_shows_the_real_ratio` 等四條）。
#: ⛔ **不准只把名字加進來、不補正向守衛** —— 那等於把一塊的守衛整個拿掉。
#: ⚠️ **2026-09-07 從 2 個變成 6 個**，每一個新加的名字都有一條**正向**守衛接手：
#: - `BLOCK_POLICY`      → :func:`test_the_policy_block_shows_the_status_bar_and_the_roster`
#:                         ＋ :func:`test_the_retired_policy_excuse_is_off_the_screen`
#: - `BLOCK_CONCENTRATION`／`BLOCK_MACRO_LINK`
#:                       → :func:`test_a_delegated_block_says_what_is_missing_instead_of_going_blank`
#:                         （逐單位 parametrize）＋ :func:`test_delegation_matches_the_registry`
#: ⚠️ **`perf_block_label()` 刻意不在這裡** —— 決定 ③ 要它升成具名區塊（**做到了**，
#:    它是 `_expected_units()` 的一員），但**委派本身被實測擋下來**
#:    （那一支一渲染就打匯率 API ＋ 落盤，見 `page_04_portfolio.REASON_PERF`）。
#:    所以它是**具名區塊 ＋ 灰態**，歸 :func:`_grey_units`。
#:    ⛔ **不要因為「決定 ③ 說要接」就把它移到這裡** —— 那會讓一條正向守衛去驗
#:       一塊其實沒接上的東西，也就是把「沒做」寫成「做了」。
#: ⛔ **「委派了」不等於「畫得出來」**：測試 fixture 沒有 `series` / `moneydj_raw` /
#:    `phase_info`，所以那三塊在測試裡走的是**本頁自己畫的灰態**。
#:    被委派的五支函式**本檔一次都沒有真的跑過它們的內容** ——
#:    被測檔的模組 docstring「本批沒有做到的事」已具名登記這一點。
_WIRED_UNITS: tuple[str, ...] = (
    BLOCK_FORM, BLOCK_MIX, BLOCK_POLICY,
    BLOCK_CONCENTRATION, BLOCK_MACRO_LINK)


def _grey_units() -> tuple[str, ...]:
    """**每一個都要各自帶 :data:`_PENDING_NOTE` 灰態**的單位（2026-09-07 起剩三個）。

    ⚠️ 六個 :data:`_WIRED_UNITS` 不在這裡，而且它們**不在的理由各不相同**：
    - `BLOCK_FORM` —— 骨架批唯一做完的一塊；
    - `BLOCK_MIX` —— 2026-09-06 接上核心／衛星 SSOT；
    - `BLOCK_POLICY` —— **2026-09-07 客戶決定 ①**，改成全寬區塊、真的畫出來了；
    - 另外三個 —— **2026-09-07 客戶決定 ③**，委派既有模組。
    全部由**正向**守衛反向釘著 —— 一旦變回「本頁分批上線」那句灰態，那些條就轉紅。

    ⛔ **不要把「這裡少了一個」讀成「那一塊不會是灰的」。** 委派的那三塊在資料不足時
    **仍然是灰的**，只是它們的灰**不帶 `_PENDING_NOTE`**（它們不是「還沒接」，
    是「接上了，但你的資料還不夠」）。**兩種灰的下一步不同，所以文案不共用。**
    """
    return tuple(_u for _u in _expected_units() if _u not in _WIRED_UNITS)


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


# ══════════════════════════════════════════════════════════════════
# 骨架：六個單位都在、順序對、名字唯一
# ══════════════════════════════════════════════════════════════════

def test_all_units_are_present_and_in_wireframe_order():
    """有持倉之後：核心／衛星 → 再平衡試算 → 換股顧問 → 保單 → 配息月曆 → 交易帳本。

    順序不是美感問題：線框把「現況 vs 建議」擺在最前面，是因為**先知道差多少，
    才知道要不要調** —— 把試算 Form 擺到現況前面，等於要使用者先填一個
    他還不知道該填什麼的目標值。

    ⚠️ **這一條同時是三份線框衝突的紀錄點**：它釘的是 `ia-wireframe.html` Tab 04
    的清單與順序。若總管裁決 ④ 應含 `policy-split-wireframe.html` 的區塊，
    **本條會轉紅 —— 那時是要改本條，不是要把它放寬。**
    """
    _parts = _stream("loaded")
    _names = [_k for _k, _ in _units(_parts)]
    assert _names == list(_expected_units()), (
        f"單位順序與線框 Tab 04 不符：\n實際：{_names}\n應為：{list(_expected_units())}")


def test_unit_names_are_unique():
    """**單位名不得重複** —— 這條堵的是 ② 被紅隊打穿的那條繞道。

    ② 的 `_segments()` 回傳 dict，**同名單位後者覆蓋前者**；紅隊因此可以
    「把真區塊掏空、另造一個同名誘餌帶著灰態」→ 全綠。
    只要單位名保證唯一，dict 檢視就不會遮蔽任何東西。

    ⚠️ 這條同時是 :func:`_segments` 的**前提** —— 它紅了，所有用 `_segments()`
    的斷言都要重新看，不是只有這一條。
    """
    for _kind in ("empty", "missing", "loaded"):
        _names = [_k for _k, _ in _units(_stream(_kind))]
        _dupes = sorted({_n for _n in _names if _names.count(_n) > 1})
        assert not _dupes, (
            f"（{_kind}）出現同名單位 {_dupes} —— "
            "`_segments()` 的 dict 檢視會讓後者覆蓋前者，"
            "等於在灰態斷言上開一道後門。請把段落名改成唯一。")


def test_the_block_names_are_the_wireframe_wording_verbatim():
    """四個區塊名**逐字對 `ia-wireframe.html` Tab 04**。

    ⚠️ **釘線框的字面值，不是釘模組常數**（③ 的第二輪突變 M02 抓到的坑）：
    如果寫成 `assert BLOCK_MIX == BLOCK_MIX` 那種從被測模組 import 進來的自我參照，
    改常數時兩邊一起變，斷言**永遠是 True**。這裡右邊是**寫死的線框字面**。

    ✅ **`保單與扣款標的` 已於 2026-09-05 由總管裁決：照線框字面**（沿用 ③ 的同一條）。
    ⚠️ **該次裁決沒有改動任何值** —— `BLOCK_POLICY` **本來就是**線框字面，
    變的是狀態（未裁決 → 已裁決）。**本條因此從「釘住本批畫成什麼」升級為
    「釘住已裁決的結果」** —— 它現在紅了，代表有人偏離了一個**已經拍板**的名字。
    ⛔ **另一份線框把 ④ 那一區叫「📋 保單資料」，那是它的區「段」名，不是本卡的名字**；
    保單版面之爭（3 欄卡 vs 全寬表）**與本條無關**，見被測檔 docstring 的 (B)。
    """
    assert BLOCK_MIX == "核心 ／ 衛星現況 vs 建議", (
        f"`BLOCK_MIX` 是 {BLOCK_MIX!r} —— 線框 Tab 04 那張全寬卡逐字是這個。")
    assert BLOCK_FORM == "再平衡試算", (
        f"`BLOCK_FORM` 是 {BLOCK_FORM!r} —— 線框寫的是「Form ─ 再平衡試算」。")
    assert BLOCK_POLICY == "保單與扣款標的", (
        f"`BLOCK_POLICY` 是 {BLOCK_POLICY!r} —— 線框 Tab 04 逐字是這個。")
    assert BLOCK_DIVIDEND_CAL == "配息月曆", (
        f"`BLOCK_DIVIDEND_CAL` 是 {BLOCK_DIVIDEND_CAL!r} —— 線框 Tab 04 逐字是這個。")
    assert BLOCK_LEDGER == "交易帳本", (
        f"`BLOCK_LEDGER` 是 {BLOCK_LEDGER!r} —— 線框 Tab 04 逐字是這個。")


def test_the_switch_block_name_comes_from_the_ssot_not_a_hand_copy():
    """換股顧問那一塊**必須**吃 `story_nav.section_label('switch')`，不得手抄線框字面。

    ## 為什麼這一塊與其他四塊處理不同

    `ui/helpers/story_nav.py::_SECTION_LABELS["switch"]` **已經是這個分區的 SSOT**，
    而且它的就地註解逐字寫著它來自「2026-09-01（客戶拍板線框 `ia-wireframe.html` Tab 04）」。
    ④ 裡已經有人在用它（`ui/helpers/fund_grp_health/switch_advisor_section.py`
    的 `st.subheader(f"{_section_label('switch')}…")`）。
    本頁若手抄一次線框的「換股顧問」，**同一個區塊在 ④ 就有兩個名字** ——
    那正是 `story_nav` 整個模組在防的事（本 repo 死指路已發作三次）。

    ## 兩件事分開驗，避免自我參照的恆真式

    (a) 畫面上那個單位名 **等於** `section_label("switch")`（跨模組比對，不是自己比自己）；
    (b) 被測檔的**活字串裡沒有**「換股顧問」四個字（手抄當場轉紅）。
    """
    _seg = _segments(_stream("loaded"))
    assert section_label("switch") in _seg, (
        f"畫面上找不到 `section_label('switch')` ＝ {section_label('switch')!r} 這個單位。\n"
        f"現有單位：{list(_seg)}")
    _bad = [f"第 {_n.lineno} 行 {_n.value[:40]!r}"
            for _n in _live_strings(_tree()) if "換股顧問" in _n.value]
    assert not _bad, (
        "本頁把「換股顧問」手抄成活字串了 —— 這個分區已經有 SSOT "
        "（`story_nav.section_label('switch')`），手抄會讓 ④ 出現兩個名字：\n  "
        + "\n  ".join(_bad))


# ══════════════════════════════════════════════════════════════════
# 鐵則 02 / 04：沒有持倉就什麼都不畫
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("kind", ["empty", "missing"])
def test_nothing_renders_before_holdings_land(kind: str):
    """一檔持倉都沒有 → 只有空狀態三要素，下面**四塊都不畫**。

    線框 Rule 04：「無資料不畫空表格外框，改用空狀態三要素：標題、缺什麼、去哪補」。

    ⚠️ 兩種 session 形狀都測：**空 list** 與 **鍵根本不存在**（第一次進站）。
    前三頁的同型守衛只測了一種，而「`.get()` 回 `None` 時炸掉」是真的會發生的。
    """
    _parts = _stream(kind)
    _seg = _segments(_parts)
    _leaked = [_u for _u in _expected_units() if _u in _seg]
    assert not _leaked, (
        f"（{kind}）還沒有持倉就畫出了 {_leaked} —— 空狀態應**取代**它們。")
    _all = _text(_parts)
    assert "尚未設定持倉" in _all, f"（{kind}）沒有空狀態的標題。\n{_all}"
    assert "還沒有任何已載入的保單或扣款標的" in _all, (
        f"（{kind}）空狀態缺了「缺什麼」這一要素。\n{_all}")
    assert where_to_find("pf_add") in _all, (
        "空狀態的「去哪補」沒有指到加入基金的地方 —— "
        f"應含 `where_to_find('pf_add')` ＝ {where_to_find('pf_add')!r}。\n{_all}")


def test_the_empty_state_does_not_also_print_the_pending_excuse():
    """兩種灰不得混在一起。

    ⚠️ 這條擋的是一個很容易犯、而且看起來無害的錯：沒有持倉時**同時**印出
    「本頁分批上線」的灰字。使用者會以為「加了基金就會看到配置建議」—— 不會，
    加完看到的是另一種灰。**一次只給一個下一步。**

    ⚠️ 比對 `_PENDING_NOTE` 本體，**不硬抄字面值**。硬抄的話，常數一改措辭
    這條就永遠是 True —— 它守的 bug 照樣存在、而它不再看得見。
    """
    for _kind in ("empty", "missing"):
        _all = _text(_stream(_kind))
        assert _PENDING_NOTE not in _all, (
            f"（{_kind}）沒有持倉時不應同時印出「內容還沒接上」的灰字 —— "
            "兩個下一步會互相抵消。\n" + _all)


def test_the_empty_state_pointer_actually_works():
    """⭐ **照著空狀態的指路做，這一頁真的會離開空狀態** —— 實跑，不是推論。

    指路寫的是「④ 📊 資產配置 → ➕ 加入與管理基金」，而那個區塊做的事就是
    把基金寫進 `portfolio_funds`（`ui/tab3_portfolio.py` 現行 ④ 真的有
    `### ➕ 加入與管理基金` 這個標題）。本條**在同一個 AppTest session 裡**
    模擬「使用者照著做完了」：把已載入的持倉放進 session，再跑一次。

    ⛔ **本條驗的是「機制通了」，不驗「那個按鈕長什麼樣」** ——
    AppTest 到不了舊 ④（本頁尚未接線），所以它按不到那顆真的按鈕。
    **本條證明的是：那句指路描述的那件事一旦發生，這一塊真的會換掉。**

    ⚠️ **它同時是未決事項 (A) 的哨兵**：`ia-wireframe.html` Tab 04 的清單裡
    **沒有**「加入與管理基金」。若 ④ 日後真的被收斂成 ia 的六塊，這句指路會變成
    死指路（而且使用者將無處可加基金）—— 那時要改的是線框的裁決，不是這條測試。
    """
    _at = _app([])
    assert any("尚未設定持倉" in _p for _p in _flat(_at.main)), "起手式應該是空狀態。"
    # 照著指路做：那個區塊做的事 ＝ 把已載入的基金寫進 `portfolio_funds`。
    _at.session_state["portfolio_funds"] = FAKE_HOLDINGS
    _rerun(_at)
    _after = _flat(_at.main)
    assert not any("尚未設定持倉" in _p for _p in _after), (
        "照著空狀態的指路做完之後，空狀態**還在** —— 那句指路是無效的。\n"
        + _text(_after))
    _names = [_k for _k, _ in _units(_after)]
    assert _names == list(_expected_units()), (
        "照著做之後，四塊沒有如預期出現。\n"
        f"實際：{_names}\n應為：{list(_expected_units())}")


# ══════════════════════════════════════════════════════════════════
# 灰態：五個單位各自誠實
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("unit", _grey_units())
def test_every_grey_unit_is_grey_until_its_content_lands(unit: str):
    """有持倉、但內容還沒接上 → 每一個單位**各自**要有灰態記號與理由。

    ⚠️ **斷言的單位是「一段」或「一張卡」，不是整頁，也不是整塊。**
    ② 的初版以「一級區塊」為單位，突變「只拿掉其中一塊的灰態」**沒有轉紅**
    （同一段裡別張卡的 ⬜ 替它通過了）—— 粒度因此下降。詳見 :func:`_units` 的長註。

    ⚠️ **下一批把真內容接上時，這條會轉紅 —— 那是預期的。**
    屆時請把它改成「真內容放行」，**不要把它放寬成「有東西就好」**。
    """
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」有標題但沒有任何內容 —— 那是空占位。"
    assert NOT_READY_MARK in _body, (
        f"單位「{unit}」沒有灰態記號 {NOT_READY_MARK!r} —— "
        "內容還沒接上就要誠實留灰，不得空著也不得填示意值（§1）。\n" + _body)
    assert _PENDING_NOTE in _body, (
        f"單位「{unit}」的灰態沒說「為什麼沒有」。\n" + _body)


@pytest.mark.parametrize("unit", _grey_units())
def test_every_grey_unit_states_its_own_reason(unit: str):
    """⭐ 每一塊灰態要說**自己的**原因，不准四塊共用一句藉口。

    ## 這條是本批新增的，理由比條文本身重要

    接線批真正危險的不是「少接一塊」，是**用一句放諸四海皆準的藉口蓋住四個
    完全不同的原因**。本頁四塊的原因實際上互不相同：

    - 換股顧問 → **撞到既有的唯一渲染點**（＋ 缺雲端選股池與逐檔基準線）
    - 保單與扣款標的 → **兩份已拍板線框把同一塊版面畫成兩種不同的東西**，已送客戶
      （⚠️ **2026-09-06 更正，稽核擋下**：原寫 ~~「對同一塊版面**規定相反**」~~ 講太滿，
      理由見 :func:`test_the_policy_block_does_not_blame_the_data` 的更正段）
    - 配息月曆 → **算得出來但很貴**，要接得先多一道開關（版面異動）
    - 交易帳本 → **線框根本沒給欄位規格**

    四句寫成同一句「資料還沒接」，對使用者說了三次謊（只有配息月曆勉強沾邊）。

    ⚠️ 本條驗的是「**這一塊的原因子句有沒有出現在這一塊底下**」，
    粒度是單位、不是整頁 —— 整頁 containment 會被鄰居的字替它通過
    （同 :func:`test_every_grey_unit_says_where_to_look` 的長註）。
    """
    _body = "\n".join(_segments(_stream("loaded")).get(unit, []))
    assert _body.strip(), f"單位「{unit}」不見了。"
    _why = grey_why()
    assert unit in _why, (
        f"單位「{unit}」在 `grey_why()` 裡沒有對應的原因 —— "
        "灰態不得沒有理由（新增區塊時請一起補）。")
    assert _why[unit] in _body, (
        f"單位「{unit}」的灰態沒有說出它自己的原因。\n"
        f"預期包含：{_why[unit]!r}\n實際：\n{_body}")


def test_the_grey_reasons_are_actually_different():
    """⛔ 每個原因**兩兩相異** —— 防止「各寫一句」退化回「複製同一句 N 次」。

    ⚠️ 這條與上一條**不重複**：上一條驗「每塊有帶自己的字串」，
    但如果有人把 `grey_why()` 的值全填成同一句，上一條**照樣全綠**
    （每塊都含有那一句）。本條才擋得住那個退化。

    ⚠️ **2026-09-07 從「四個」變成「三個」，而且函式名一起改了**（原
    `test_the_four_grey_reasons_are_actually_different`）——
    保單那一塊不再是灰態（客戶決定 ①）。
    ⛔ **名字裡不再寫死數量**：上一次寫死「four」的代價就是這一次得連函式名一起改，
    而**改函式名會讓「這條測試有沒有被停用過」在 git 上變得難查**。
    本條改用 `len(grey_why())` 自己算 —— 下次增減灰態，本條不必再改一次名字。
    """
    _vals = list(grey_why().values())
    assert len(set(_vals)) == len(_vals), (
        f"{len(_vals)} 塊灰態的原因出現重複 —— 那就是「一句藉口蓋 N 個原因」的退化形狀：\n"
        + "\n".join(_vals))
    # 反向保險：`grey_why()` 空掉時上面那條恆真（`set() == list()` 長度都是 0）。
    assert len(_vals) >= 2, (
        f"`grey_why()` 只剩 {len(_vals)} 筆 —— 少於兩筆時「兩兩相異」這條恆真，"
        "等於守衛靜默失效。真的只剩一塊灰態時，請連同本條一起改。")


def test_the_retired_policy_excuse_is_off_the_screen():
    """⭐ **保單那一區的「灰態理由」已經退役，而且不准再出現在畫面上。**

    ## ⚠️ 2026-09-07：本條**換了守的東西**，函式名一起改（原
    `test_the_policy_block_does_not_blame_the_data`）

    客戶 2026-09-07 **決定 ①** 把這一區改成**全寬區塊**，它**不再是灰態** ——
    於是舊斷言（「畫面上要說原因是版面」「畫面上要說已送客戶裁決」）
    **全部會轉紅，而且轉紅是對的**：那兩句話現在是**假的**（沒有人還在等裁決）。

    ⛔ **舊斷言不是被放寬，是被反轉**：本條現在驗**相反**的事 ——
    那句退役的理由（:data:`RETIRED_REASON_POLICY`）**必須從畫面上消失**。
    一個「已經拍板了、但畫面上還在說『已送客戶裁決』」的區塊，
    正是 `CLAUDE.md §-2` 講的那種**會說謊的記錄**。

    ⚠️ **被測檔的常數刻意保留不刪**（改名為 `RETIRED_REASON_POLICY`），
    因為它是「未決事項 (B) 從登記到結案」的完整病史；
    **本條就是負責證明「保留常數」沒有變成「保留在畫面上」。**

    ⏳ **以下為 2026-09-07 之前的原文，一字未刪**（它記載了那次裁決之前的判斷）：

    ⭐ **保單那一區的灰態不准把原因說成「資料還沒接」**（總管裁決 2）。

    真正卡住它的是**版面**：`docs/wireframes/ia-wireframe.html` 把它畫成三欄網格
    裡的**一張摘要卡**，而 `docs/wireframes/policy-split-wireframe.html` 的**決定 E**
    逐字寫「**狀態列**用三欄自適應網格；**保單明細表維持全寬**，不塞進三欄」——
    兩份都是客戶拍板過的線框，**把同一塊版面畫成兩種不同的東西**。已另派線框組送客戶裁決。

    ## ⚠️ 2026-09-06 更正，稽核擋下：~~「對同一塊版面給了**相反的規定**」~~ 講太滿

    **衝突為真，但不是不可調和** —— 逐字讀兩份線框後：

    * `ia-wireframe.html` 那個是 **摘要卡**（markup 實測：`<div class="grid3">` 底下的
      `<div class="card">`，內容是彙總數字「**3 張保單**」）；
    * 決定 E 管的是**明細表**，而且它**自己的理由**就寫著「三欄網格是給**卡片型內容**用的
      規則，六七欄的表格壓成三分之一寬反而更難看 —— 這不是破例，**是規則本來就不涵蓋表格**」。

    → **摘要卡進三欄、明細表另外全寬，兩份可以同時成立**；決定 E 甚至**主動排除了**
    「表格塞進三欄」這個讀法。**真正要客戶拍板的是「那張 1/3 摘要卡要不要留」。**

    ⛔ **這一處為什麼非改不可（比措辭重要）**：`~~相反的規定~~` 這句是**本 PR 自己新增**的
    （merge-base `1ad0821` 實測 **0 命中**），本 PR 的 delta **自己判定它講太滿**並在
    `ui/views/page_04_portfolio.py` 改了兩處，本 PR 還**因為這句去提醒了 PR #791**。
    留著等於讓 repo 同時存在「這句是對的」與「這句講太滿」兩份記錄，
    **而留下來的那份剛好在被別人引用的那條鏈上** —— 正是 `CLAUDE.md §-2`
    「**一節在講『會說謊的記錄』的條文，自己的描述必須先為真**」。
    ⚠️ **怎麼漏的，一併記**：上一輪的一致性掃描**朝外做了、朝內沒做** ——
    查了 sibling 檔、查了別的 PR，**唯獨沒查自己正在改的這個測試檔**。

    ⚠️ 說成「資料還沒接」不只是不精確，是**假的原因**：它會讓下一個人以為
    「去把資料接上就好」，然後一頭撞進那個還沒裁決的版面衝突。
    """
    # (a) 常數本身還在（病史保留），而且它確實還是**那一句** —— 不是被清空後留個空殼。
    assert "版面" in RETIRED_REASON_POLICY and "已送客戶裁決" in RETIRED_REASON_POLICY, (
        "`RETIRED_REASON_POLICY` 已經不是原來那句話了 —— 它的用途是保存病史，"
        "改掉它等於把「(B) 曾經未決」這件事從記錄裡抹掉：\n" + RETIRED_REASON_POLICY)
    # (b) ⛔ 但它**不准**出現在畫面上。四種 session 形狀都查。
    for _kind in ("empty", "missing", "loaded", "priced"):
        _all = _text(_stream(_kind))
        assert "已送客戶裁決" not in _all, (
            f"（{_kind}）畫面上還在說保單版面「已送客戶裁決」—— "
            "客戶 2026-09-07 已經裁決了（決定 ①：全寬區塊）。"
            "一個已經拍板、畫面卻還在等的區塊，是一則會說謊的記錄。")
    # (c) 那一區確實不再帶「本頁分批上線」那句灰態藉口。
    _body = "\n".join(_segments(_stream("loaded")).get(BLOCK_POLICY, []))
    assert _body.strip(), f"單位「{BLOCK_POLICY}」不見了 —— 決定 ① 要它變成全寬區塊，不是消失。"
    assert _PENDING_NOTE not in _body, (
        f"「{BLOCK_POLICY}」還帶著「{_PENDING_NOTE}」的灰態藉口 —— "
        "它已經接上真資料了（決定 ①）。\n" + _body)


def _expected_pointer() -> dict[str, str]:
    """單位名 → 它的灰態**應該**指到哪裡。**三塊三個地方，刻意不共用。**

    ## ⚠️ 2026-09-07：從「三塊共用一個地方」變成「三塊三個地方」

    到 2026-09-06 為止，三塊灰態的指路**全部**是
    ``where_to_find("portfolio") → 再平衡試算``（本頁唯一做完的那一塊）——
    也就是三句「去了也沒用」的指路。客戶 2026-09-07 指示
    「**交易帳本的灰態必須指出去哪裡看得到**，⛔ 不得只寫『尚未提供』」，
    加上決定 ④ 給了配息月曆一個勾選框，於是三塊各自有了自己的下一步：

    ===================== ================================ =========================
    單位                   指到哪                            照著做真的有用嗎
    ===================== ================================ =========================
    ~~換股顧問~~           ~~本頁的「再平衡試算」~~           ~~❌ **沒用**（撞既有渲染點）~~
    換股顧問               舊 ④ 的「🎯 換股顧問」             ✅ **有用**（那裡現在就在跑）
    配息月曆               它自己上方那個勾選框               ✅ **有用**（勾了就會算）
    組合績效               舊 ④ 的「📊 組合績效」             ✅ **有用**（那裡現在就看得到）
    交易帳本               舊 ④ 的「💼 持倉戰情（T7 帳本）」  ✅ **有用**（那裡現在就看得到）
    ===================== ================================ =========================

    ## ⚠️ 2026-09-08：最後一塊「沒用」的指路也修掉了

    **有意識的狀態變更，不是漏刪**（決策者：架構與前端組）。上表 ~~刪除線~~ 那一列
    保留不刪，它記載 2026-09-07 的實況。改的理由**不是**「換股顧問接上了」——
    它今天**仍然是灰態、仍然沒接**（:data:`REASON_SWITCH` 一字未改）；
    改的是**指路本身原本就指錯了**：那一塊在**舊 ④ 有一個真的在線上跑的家**，
    而 :data:`REASON_SWITCH` 自己就寫著「這一塊在目前線上的 ④ 已經有唯一的渲染點」。
    → 也就是說，這一頁**一邊寫著「它在舊 ④ 有渲染點」，一邊把使用者指回本頁的試算**。
    ⛔ **兩件事不要混為一談**：「這一塊在本頁還沒接上」（仍然為真）
    vs「使用者現在沒有地方可以用它」（**假的**）。舊指路把前者說成了後者。

    ⚠️ **舊表述在寫下的當天是對的**：2026-09-07 那一輪確實剛把另外三塊各自指出去，
    「只剩換股顧問沒地方去」是那時候的實況判斷。
    **被推翻的是那個判斷本身，不是它的謹慎** —— 沒有人回頭問一句
    「它真的沒地方去嗎」，而答案早就寫在同一份檔案的 :data:`REASON_SWITCH` 裡。

    ⚠️ **9 格分頁列上「兩個資產配置」分不分得出來 —— 本組實測，據實寫**：
    `app.py` 掛的九格逐字是
    ``🌐 市場總覽 / 💊 持倉體檢 / 🔍 標的探索 / 📊 資產配置 / ⚙️ 設定與診斷 /``
    ``[新] 💊 持倉體檢 / [新] ⚙️ 設定與診斷 / [新] 🔍 標的探索 / [新] 📊 資產配置``。
    本頁是**第 9 格**、名字帶 ``[新] `` 前綴；指路吐的是 ``④ 📊 資產配置``（**無前綴**），
    指的是**第 4 格**。兩者靠 :data:`ui.helpers.story_nav.PREVIEW_PREFIX` 區分，
    而那個前綴的存在理由就寫在 `story_nav.py` 的 `preview_tab_label()`：
    「回退會讓預覽分頁與正式分頁在畫面上叫同一個名字，使用者分不出自己在看哪一版」。
    → **分得出來。** 由 :func:`test_the_pointer_does_not_collide_with_this_pages_own_tab`
    釘住（前綴哪天被拿掉，那條會轉紅）。

    ⛔ **三個都要逐字比對，不要退回「有 `where_to_find('portfolio')` 就好」** ——
    那種寬鬆比對在 2026-09-07 之後會**同時放過三種錯**：
    (a) 交易帳本指回本頁（`pf_ledger` 的字串剛好也以 `④ 📊 資產配置` 開頭）；
    (b) 配息月曆指到一個不存在的勾選框；
    (c) 三塊又退回共用同一句。
    ⚠️ **配息月曆那一格的期望值吃 :data:`DIVCAL_GATE_LABEL` 這個 SSOT** ——
    不在這裡抄第二份字面值，改了 gate 的字，本條會**跟著對**而不是**跟著錯**。
    """
    return {
        # ⚠️ 走 `where_to_find("switch")` 這個 SSOT，**不抄字面** —— 換股顧問哪天被
        #    搬到別的分頁，本條會**跟著對**而不是**跟著錯**（同 `pf_perf` / `pf_ledger`）。
        switch_block_label(): where_to_find("switch"),
        BLOCK_DIVIDEND_CAL: f"上方「{DIVCAL_GATE_LABEL}」",
        # 組合績效：委派被實測擋下（見 `page_04_portfolio.REASON_PERF`），
        # 但**它現在就在舊 ④ 看得到** —— 與交易帳本同一種「指了真的有用」的灰。
        perf_block_label(): where_to_find("pf_perf"),
        BLOCK_LEDGER: where_to_find("pf_ledger"),
    }


@pytest.mark.parametrize("unit", _grey_units())
def test_every_grey_unit_says_where_to_look(unit: str):
    """每一個灰態單位**各自**要有「去哪補」，而且不得手抄分頁名。

    ## ⚠️ 粒度必須是「一個單位」，整頁 containment 會被打穿

    **以下是 ③ 的紀錄，本組照抄，沒有重跑**（`CLAUDE.md §-2` 規則 6）：
    ③ 的同型守衛原本是 `assert where_to_find(...) in 整頁`，紅隊拿掉三處
    `wide_table(empty_where=)` → 該組記載「**1007 passed，一條都沒響**」，
    而畫面上那三塊**真的失去了「（請先到：…）」**。兩個原因疊在一起：
    全域網子（`tests/test_batch2_top_card_grid.py::_where_sites`）
    **不收 `wide_table(empty_where=)` 這個形狀**，而該守衛當時的粒度是整頁。

    ✅ **本組自己驗的是這一條**：本檔的 `wide_table(empty_where=)`（交易帳本那一塊）
    被拿掉時（突變 **M03**）—— **七個全域守衛檔 1001 passed 全綠**，
    只有本條轉紅。**也就是那個形狀今天仍然在全域網子的射程外。**
    → **本檔從第一版就是逐單位。**

    ⚠️ 這條驗的是「**有沒有指路**」，**不驗「照著做有沒有用」**。兩件事不要混為一談。
    ⚠️ **2026-09-08 更正（有意識的更正，不是漏刪）**：本段原寫
    ~~「後者由 `test_the_pending_pointer_is_honest_about_being_ineffective` 實跑，
    而且答案是**沒用**」~~ —— **那個答案今天是假的**（四塊指路現在都有真的去處），
    而且那條測試**從來沒有真的驗過「有沒有用」** ：它按的是本頁的「試算」鈕，
    量的是「按完之後灰態變了沒」，**到不了任何一個指路指去的地方**。
    → 現行分工：**「去了有用嗎」在本檔只有換股顧問那一塊有守**
    （:func:`test_the_switch_card_points_at_the_place_that_really_renders_it`，AST）；
    配息月曆那一塊由 :func:`test_ticking_the_dividend_gate_actually_changes_the_block` 實跑；
    **組合績效與交易帳本兩塊指向舊 ④，本檔一律驗不到，也不宣稱**（`CLAUDE.md §-2` 規則 6）。
    """
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」不見了。"
    _want = _expected_pointer()[unit]
    assert f"（請先到：{_want}）" in _body, (
        f"單位「{unit}」的灰態沒有帶到它該帶的「去哪補」。\n"
        f"應含：（請先到：{_want}）\n實際：\n{_body}")


def test_the_pending_pointer_is_a_place_not_a_status_sentence():
    """`_pending_where()` 回傳的必須是一個**地方**，不是一句狀態陳述。

    ## 這條是 ③ 的紅隊突變 R5 逼出來的（本檔從第一版就帶著它）

    ③ 的 `_pending_where()` 原本回傳
    ``f"{where_to_find('research')} → 目前只有「{block}」是完整的"``，
    而 `render_state.not_ready()` 會把它包成「（請先到：…）」——
    畫面上於是印出一句**不可執行的指令**：「請先到：③ … → 目前只有「搜尋條件」是完整的」。
    修好之後 ③ 把它退回舊寫法重跑，**1014 passed 一條都沒紅** ——
    也就是**修好了渲染，卻沒有任何東西在防它退回去**。

    ## 判準用**結構相等**，不用關鍵字黑名單

    黑名單（「不准出現『完整』兩個字」之類）只擋得住上一次那個寫法，換個措辭就繞過。
    本條直接釘住組成：**分頁路徑 ＋ `→` ＋ 區塊名**，中間不得夾任何述語。
    """
    for _block in (BLOCK_FORM, "任意區塊名"):
        assert _pending_where(_block) == f"{where_to_find('portfolio')} → {_block}", (
            f"`_pending_where({_block!r})` ＝ {_pending_where(_block)!r}\n"
            "它會被 `render_state.not_ready()` 包成「（請先到：…）」——"
            "所以它必須是一個**地方**（分頁路徑 → 區塊名），不能是一句狀態陳述。")
    # ── 第二半：**它現在有幾個 caller** ───────────────────────────────
    # ⏳ **以下三段是 2026-09-06／09-07 的原註解，一字未刪**（病史）：
    # ⚠️ ~~**2026-09-06 改指 `BLOCK_POLICY`**：本條原本取 `BLOCK_MIX`，而那一塊已經
    #    接上真資料、不再走 `_pending_where()`（它的指路改成「去哪填本金」那條
    #    **真的有效**的 `pf_add`）。留著會變成一條驗不到 `_pending_where()` 的測試。
    #    ⛔ 這不是把斷言放寬 —— 換的是**取樣的單位**，斷言的字串一字未改，
    #    而且 `BLOCK_POLICY` 是四個灰態單位中**最不可能被下一批接走**的那一個
    #    （它卡在客戶裁決上，見 `REASON_POLICY`）。~~
    # ⚠️ ~~**2026-09-07 再改一次，改指換股顧問** —— 上面那句「最不可能被下一批接走」
    #    **在寫下來的第二天就被推翻了**（客戶決定 ①，保單改成全寬區塊，不再走
    #    `_pending_where()`）。⛔ **這次不再挑「最不可能被接走的那一個」** ——
    #    那個判斷已經錯過一次；改挑 `_pending_where()` **目前唯一的 caller**，~~
    #    **也就是說：它哪天沒有 caller 了，本條就會紅，而那正是該來重看本條的時機。**
    #
    # ✅ **2026-09-08：上面那句話應驗了 —— 那一天到了。**
    #    換股顧問（最後一個 caller）改指 `where_to_find("switch")`，
    #    `_pending_where()` 自此 **0 caller**。
    #    ⛔ **本半段因此不能再「取樣某一塊的畫面」** —— 沒有任何一塊會印出它。
    #    改成**直接把 0-caller 這個事實釘住**，理由有三，缺一不可：
    #      (a) **不是放寬**：畫面形狀那一半的守備**沒有消失**，它移交給
    #          `test_every_grey_unit_says_where_to_look[換股顧問]` ——
    #          那條比對的是**完整字串** `（請先到：{_expected_pointer()[...]}）`，
    #          嚴格程度一模一樣，只是期望值換成了新的那個地方。
    #      (b) **它是一條會轉紅的觸發器**：有人把 `_pending_where()` 接回任何渲染
    #          路徑（＝ 把某一塊的指路又指回本頁的試算），本條**當場轉紅**。
    #      (c) **它是「該不該刪掉這個函式」的出口**：依 `CLAUDE.md §-1.5.1c` 判定 3，
    #          本次任務造成的孤兒應在同一次任務內實體刪除；本批**沒有刪**，
    #          因為刪它會連帶要刪本條（＝ ③ 紅隊突變 R5 逼出來的守衛），
    #          而**刪守衛屬派工單明令要先回報的事**。已回報總管裁決。
    #          ⛔ **在裁決之前，「它還活著而且沒人用」這件事必須是可見的，不是註解。**
    _calls = [_n for _n in ast.walk(_tree())
              if isinstance(_n, ast.Call)
              and isinstance(_n.func, ast.Name)
              and _n.func.id == "_pending_where"]
    assert not _calls, (
        f"`_pending_where()` 又有 {len(_calls)} 個呼叫點了"
        f"（行號：{[_c.lineno for _c in _calls]}）。\n"
        "⛔ 它指回**本頁自己的**「再平衡試算」，而本頁四塊灰態各自都有真的去處 ——\n"
        "   換股顧問 → 舊 ④ 的 🎯 換股顧問；配息月曆 → 上方的勾選框；\n"
        "   組合績效 → 舊 ④ 的 📊 組合績效；交易帳本 → 舊 ④ 的 💼 持倉戰情。\n"
        "⛔ **請不要把哪一塊的指路改回它** —— 要新增一塊「真的無處可去」的灰態，\n"
        "   先在這裡說明為什麼那一塊與上面四塊不同，再改本條。")


def test_the_form_alone_fills_in_no_grey_block():
    """⭐ **按下「試算」不會把任何一塊灰態變出內容** —— 本條把那個事實釘成斷言。

    ## ⚠️ 2026-09-08：**純改名，斷言一字未改**（原
    `test_the_pending_pointer_is_honest_about_being_ineffective`）

    **有意識的更正，不是漏刪**（決策者：架構與前端組）。舊名字宣稱的是
    「**這一族的指路去了也沒用**」，而本條**從來沒有驗過那件事** ——
    它按的是**本頁**的「試算」鈕，量的是「按完之後灰態變了沒」，
    **到不了任何一個指路指去的地方**（那些地方在舊 ④，本檔的 AppTest
    只渲染本頁，見 :data:`_SCRIPT`）。
    2026-09-08 換股顧問改指舊 ④ 之後，**舊名字會變成畫面上的一句假話**，
    但**它的斷言依然為真、依然值得釘**：本頁的 Form 確實不會填出任何一塊內容。
    → **只改名，一行斷言都沒動。**

    ⛔ **舊 docstring 曾預言「有人把指路改成真的有用的地方 → 它也會紅」—— 那個預言不成立。**
    理由是**結構**，不是巧合：本條比的是**同一次渲染的前後兩份 ⬜ 清單**
    （`_after == _before`），而改 `where=` 會讓**兩邊同時**變成新字串 ——
    差集永遠是空的。逐單位那條數的是 `_PENDING_NOTE` 的**條數**，也與 `where=` 無關。
    **一條測不到 X 的測試，不會因為 X 變了而轉紅** —— 這正是舊名字誤導人的地方。
    ⚠️ **本段是推導，不是本地實跑**（沙箱沒有 streamlit／pytest，見模組 docstring）；
    它由 CI 的 fast lane 實際驗證 —— **本條若在 CI 轉紅，就是這段推導錯了。**

    ## 這條為什麼還要存在

    它擋的是**「試算」被偷偷接上下游、卻沒人發現**：`_applied_plan()` 自陳
    「本批沒有下游」，本條就是那句話的守衛。哪天真的接上了，本條會紅，
    **正解是刪掉本條並改掉那句 docstring**，不是把它放寬。
    """
    # ⚠️ **2026-09-06 改用 `FAKE_HOLDINGS_PRICED`，理由不是「讓數字對上」** ——
    #    是因為這一頁自本批起有**兩種灰**，混在一起數就數不出東西：
    #      (a) **「還沒接上」的灰**（四個 `_grey_units()`）—— 本條要驗的那一種；
    #      (b) **「接上了，但你沒填本金」的灰**（`BLOCK_MIX`）—— 那是**真資料的誠實缺料**，
    #          而且它的指路（去填本金）**照著做是真的有用的**，與 (a) 恰好相反。
    #    用沒填本金的 fixture 會讓 (b) 也算進來，本條就變成在數兩種語意相反的東西。
    #    改用有本金的 fixture → `BLOCK_MIX` 畫出真比例、不留灰，剩下的**恰好**是 (a)。
    # ⛔ 這不是放寬：全頁 `⬜` 總數的斷言**原封保留**（它擋得住「多長出第五條灰」），
    #    換掉的只有 fixture。
    _at = _app(FAKE_HOLDINGS_PRICED)
    _before = [_p for _p in _flat(_at.main) if NOT_READY_MARK in _p]
    # ⚠️ **2026-09-07：舊斷言是「全頁 ⬜ 條數 == len(_grey_units())」，那條已經失效。**
    #    決定 ①／③ 之後，畫面上**合法地**多了好幾條不帶 `_PENDING_NOTE` 的灰
    #    （狀態列缺值那幾格、三個委派區塊在資料不足時的誠實灰態）。
    #    ⛔ 舊斷言若照留，會把**正確的行為**判成紅，然後有人為了讓 CI 綠而放寬它。
    # ✅ **換成更嚴的形狀，不是更鬆的**：舊的只數總數（多一條少一條都看不出是哪一塊）；
    #    現在逐單位驗「這一塊有且只有一條『本頁分批上線』的灰」——
    #    多長一條、少長一條、跑到別的單位底下，三種都會指名道姓地紅。
    _seg_before = _segments(_flat(_at.main))
    for _u in _grey_units():
        _n = sum(1 for _p in _seg_before.get(_u, []) if _PENDING_NOTE in _p)
        assert _n == 1, (
            f"單位「{_u}」應該剛好帶一條「{_PENDING_NOTE}」的灰態，實際 {_n} 條：\n"
            + _text(_seg_before.get(_u, [])))
    # 照著指路做：回到「再平衡試算」，填金額、按「試算」。
    _at.number_input[0].set_value(150_000)
    _at.button[0].click()
    _rerun(_at)
    assert not _at.exception, "按下「試算」之後整頁炸了。"
    _after = [_p for _p in _flat(_at.main) if NOT_READY_MARK in _p]
    assert _after == _before, (
        "照著灰態的指路做完之後，灰態**變了** —— 那麼被測檔 `_pending_where()` 的 "
        "docstring（「這一族的指路去了也沒用」）就是假話，要一起改。\n"
        f"之前：{_before}\n之後：{_after}")


# ══════════════════════════════════════════════════════════════════
# 核心 ／ 衛星：本批接上的那一格（`_WIRED_UNITS` 少一個名字，這裡就要多一組守衛）
# ══════════════════════════════════════════════════════════════════

def _mix_body(kind: str = "priced") -> str:
    """`BLOCK_MIX` 那一個單位的渲染內容（字串）。"""
    return "\n".join(_segments(_stream(kind)).get(BLOCK_MIX, []))


def test_the_mix_block_shows_the_real_ratio():
    """有本金 → 這一格畫出**真的**核心／衛星比例，而且不再是灰態。

    fixture 是 620000 ／ 380000（`policy_tier` 明示 core ／ satellite）
    → SSOT `summarize_core_satellite` 實測回 `core_pct == 62.0` / `sat_pct == 38.0`。
    """
    _body = _mix_body("priced")
    assert _body.strip(), f"單位「{BLOCK_MIX}」不見了。"
    assert NOT_READY_MARK not in _body, (
        f"「{BLOCK_MIX}」已經接上真資料，不該還是灰態：\n{_body}")
    assert MIX_CURRENT_LABEL in _body and "62.0%" in _body and "38.0%" in _body, (
        f"「{BLOCK_MIX}」沒有畫出現況比例（預期核心 62.0% ／ 衛星 38.0%）：\n{_body}")
    # ⚠️ 上面那條**只驗兩個數字在不在**，驗不到它們有沒有貼對標籤 ——
    #    把核心／衛星對調，兩個字串都還在（實測 49 passed）。配對由下一條守。


def test_the_mix_block_pairs_each_label_with_its_own_number():
    """⭐ **順序**：`核心` 要貼 62.0%、`衛星` 要貼 38.0% —— 對調就是說謊。

    ## 這條是補洞，不是加保險（2026-09-06 稽核存活突變 F1-b）

    :func:`test_the_mix_block_shows_the_real_ratio` 的斷言是
    ``"62.0%" in _body and "38.0%" in _body``。**把兩個數字對調，它照樣綠**
    —— 實測：核心／衛星互換後全檔仍 **49 passed**。

    對調後畫面長這樣（真實輸出，不是想像）::

        **現況**　核心 38.0%　衛星 62.0%　→　**你設定的目標**　核心 75.0%
        **差距**　核心比目標少 13.0%

    ⛔ **它自己跟自己打架**：核心若真的是 38%，離 75% 的目標差的是 **37 個百分點**，
    不是 13。畫面同時說「核心 38%」與「差 13%」，兩句不可能都對。
    而使用者會照著這一格**調自己的部位** —— 這正是客戶說的
    「我不接受假資料、缺資料」裡最貴的那一種：**不是缺，是反的。**

    ⚠️ **本條驗的是「標籤↔數字的配對」，不是「數字對不對」**（後者由上一條 + SSOT 守）。
    兩條合起來才完整：一條問「數字在不在」，一條問「有沒有貼對人」。
    """
    _body = _mix_body("priced")
    assert f"核心 {_CORE_PCT_TEXT}" in _body, (
        f"「{BLOCK_MIX}」沒有把核心與 {_CORE_PCT_TEXT} 貼在一起：\n{_body}")
    assert f"衛星 {_SAT_PCT_TEXT}" in _body, (
        f"「{BLOCK_MIX}」沒有把衛星與 {_SAT_PCT_TEXT} 貼在一起：\n{_body}")
    # 把對調後的形狀直接寫成禁令：失敗訊息才看得出「紅在哪」而不只是「少了什麼」。
    assert f"核心 {_SAT_PCT_TEXT}" not in _body and f"衛星 {_CORE_PCT_TEXT}" not in _body, (
        f"「{BLOCK_MIX}」把核心／衛星的數字對調了 —— "
        f"預期核心 {_CORE_PCT_TEXT} ／ 衛星 {_SAT_PCT_TEXT}：\n{_body}")


def test_the_mix_gap_direction_agrees_with_the_numbers_it_just_printed():
    """⭐ **方向**：現況 62% < 目標 75% ⇒ 只能說「**少**」，而且差額要等於 |62−75|。

    ## 這條是補洞，不是加保險（2026-09-06 稽核存活突變 F1-c）

    既有斷言只驗數字、不驗方向詞：把 `_render_mix()` 裡的多／少**反轉**，
    畫面變成「核心比目標**多** 13.0%」，**全檔仍 49 passed**（實測）。
    「核心配置過重、該減碼」與「核心配置不足、該加碼」是**相反的動作指示**，
    而這一格的存在目的就是告訴使用者往哪邊調。

    ## 為什麼用「自我一致」而不是寫死「少 13.0%」

    寫死字串只能釘住這一組 fixture；**改成從畫面自己讀回來對帳**，
    等於要求這一格**內部不自相矛盾** —— 它同時擋住：

    * 方向詞反轉（F1-c：62 < 75 卻說「多」）；
    * 差額算錯或沒跟著變（F1-b 對調後：說「核心 38%」卻仍寫「差 13%」，
      而 |38−75| = 37 ⇒ 本條也會轉紅，與上一條形成交叉守備）。

    ⛔ **守不到什麼**：現況與目標**同時**被改成另一組自洽的數字（例如全部 ×2），
    本條看不出來 —— 那要靠上一條與 SSOT 的實際回傳值。**兩條互補，缺一不可。**
    ⚠️ **本條假設這組 fixture 的現況與目標不相等**（62.0 vs 75.0）。若日後有人把 fixture
    改成剛好落在目標上，`_render_mix()` 走的是「剛好落在目標上」那一支、**沒有方向詞**，
    本條會在第一個斷言就紅（訊息是「讀不出三者之一」）。**那是刻意的**：
    這條的前提是「有差距可言」，前提沒了就該有人回來看一眼，而不是靜靜通過。
    """
    _body = _mix_body("priced")
    # 從畫面**讀回**現況核心、目標核心、以及差距那一行講的方向與差額。
    _cur = re.search(r"核心 (\d+\.\d)%\u3000衛星", _body)
    _tgt = re.search(r"目標\*\*\u3000核心 (\d+\.\d)%", _body)
    _gap = re.search(r"核心比目標(多|少) (\d+\.\d)%", _body)
    assert _cur and _tgt and _gap, (
        f"「{BLOCK_MIX}」讀不出現況／目標／差距三者之一，無法對帳：\n{_body}")
    _cur_v, _tgt_v, _gap_v = float(_cur.group(1)), float(_tgt.group(1)), float(_gap.group(2))
    _expect_word = "多" if _cur_v > _tgt_v else "少"
    assert _gap.group(1) == _expect_word, (
        f"「{BLOCK_MIX}」的方向詞與它自己印出來的數字相反："
        f"現況核心 {_cur_v}% vs 目標 {_tgt_v}% 應該是「{_expect_word}」，"
        f"畫面卻寫「{_gap.group(1)}」：\n{_body}")
    assert abs(_gap_v - abs(_cur_v - _tgt_v)) < 0.05, (
        f"「{BLOCK_MIX}」的差額對不上它自己印出來的數字："
        f"|{_cur_v} − {_tgt_v}| = {abs(_cur_v - _tgt_v):.1f}，畫面卻寫 {_gap_v}：\n{_body}")


def test_the_mix_block_never_prints_a_zero_when_it_cannot_compute():
    """⭐ **一檔本金都沒填 → 誠實留灰，`絕不`畫成 0%。**

    ## 這條擋的是本批最貴的那個錯

    派工單點名的坑之一：② 那批第一版把讀不出來的值畫成 `0`，
    「最大回撤 0.0%」讀起來是「這檔從沒跌過」。
    同一個形狀在這裡會變成「**核心 0.0% ／ 衛星 0.0%**」——
    使用者會讀成「我的錢全都不在核心也不在衛星」，然後照著它調部位。

    ## 為什麼這條擋得住（而不是只是碰巧綠）

    上游 SSOT `summarize_core_satellite` 在 `total_twd == 0` 時把 `core_pct`
    回成 **`None`**（其 docstring 逐字：「缺資料時誠實回 None，不捏造 0」）。
    本頁據此走 `not_ready()` 直接 return。
    **突變驗證（實跑，兩顆；⚠️ 第一顆的死法與本組原本寫的不一樣，據實更正）**：

    - **M1**：`if _core is None:` → `if False:`（把 `None` 當數字往下畫）→ 本條**轉紅**，
      **但死因不是畫出 `0.0%`** —— 是 `TypeError: unsupported format string passed to
      NoneType.__format__`，被 `safe_section()` 接成紅框。
      ⚠️ 本組原本在這裡寫的是「畫面出現 `0.0%`」，**那是沒跑就寫下的推測，實測推翻**。
      連帶：`test_no_block_silently_renders_a_system_error[loaded]` 也一起轉紅。
    - **M1b**（補跑，這顆才真的在測本條的字面斷言）：把 `None` **補成 `0.0` 再往下畫**
      → 畫面真的出現 `0.0%`，本條**單獨轉紅**（49 條裡只有它紅）。

    **兩顆都要記**：M1 證明「`None` 流下去會炸」，M1b 才證明
    「**就算有人特地把它補成 0，這條也擋得住**」—— 而後者才是真正會發生的那種寫法
    （沒有人會故意讓它炸，但很多人會「順手補個預設值讓它不要炸」）。
    """
    _body = _mix_body("loaded")          # 兩檔已載入，但都沒填 invest_twd
    assert _body.strip(), f"單位「{BLOCK_MIX}」不見了。"
    assert NOT_READY_MARK in _body, (
        f"沒有本金就算不出比例，這一格必須誠實留灰：\n{_body}")
    assert "0.0%" not in _body and "0%" not in _body, (
        f"「{BLOCK_MIX}」在算不出比例時畫了 0% —— 「不知道」被畫成了「是零」（§1）：\n{_body}")
    # 指路必須是**真的有效**的那一條（去填本金），不是四塊灰態那種「去了也沒用」。
    assert where_to_find("pf_add") in _body, (
        f"算不出比例時要指到「去哪填本金」（`pf_add`），而不是指回本頁的試算：\n{_body}")


def test_the_target_number_comes_from_the_user_setting_not_a_constant():
    """⭐ 目標值必須**真的**從 session `portfolio_core_pct` 流過來（總管裁決 1）。

    ## 這條是本組**唯一**能證明「裁決 1 真的落地」的那一條

    只驗「畫面上有一個目標數字」是驗不到東西的 —— 寫死一個 75 也會過。
    本條把 session 設成一個**不可能碰巧出現**的值（41），
    再確認畫面上出現 `41.0%`，而且**預設值 75 不在畫面上**。

    **突變驗證（實跑）**：把被測檔的 `get_core_target_pct(st.session_state)` 換成
    常數 `75.0` → 本條**轉紅**（畫面上沒有 41.0%）。
    ⚠️ 這正是派工單點名的第 3 個坑（卡片文案宣告的門檻與 SSOT 脫鉤）在本頁的形狀：
    差別只在這裡脫鉤的不是文案裡的門檻，是**那個數字本身**。
    """
    _at = _app(FAKE_HOLDINGS_PRICED, session={"portfolio_core_pct": 41})
    _body = "\n".join(_segments(tuple(_flat(_at.main))).get(BLOCK_MIX, []))
    assert MIX_TARGET_LABEL in _body, f"目標那一段不見了：\n{_body}"
    assert "41.0%" in _body, (
        "目標值沒有跟著 session `portfolio_core_pct` 走 —— "
        f"把它設成 41 之後畫面上找不到 41.0%：\n{_body}")
    assert "75.0%" not in _body, (
        f"使用者把目標改成 41 了，畫面上卻還留著預設的 75：\n{_body}")
    # 差距要跟著一起動：現況 62.0 − 目標 41.0 = +21.0
    assert MIX_GAP_LABEL in _body and "21.0%" in _body, (
        f"差距沒有跟著目標一起重算（預期核心比目標多 21.0%）：\n{_body}")


def test_the_target_says_out_loud_that_it_is_the_users_own_setting():
    """⭐ **總管裁決 1 逐字要求的那句話，必須真的在畫面上。**

    線框把這一格畫成「現況 → **建議**」＋ chip「與 01 同源」，
    但 ①（`ui/views/page_01_macro.py`）整條鏈只給**股／債／現金**，
    給不出核心／衛星（該檔模組 docstring 逐字寫著這件事）。
    → 這一格改用**使用者自己設的目標**，而**改用之後就必須說出來** ——
    否則使用者會把自己填的數字讀成系統的建議，那是系統冒名替他背書（§1）。

    ⚠️ 本條驗的是「那句話在不在」，**不驗它寫得好不好**。
    """
    _body = _mix_body("priced")
    assert MIX_TARGET_PROVENANCE in _body, (
        "畫面上沒有說明那個目標值的出身 —— 使用者無從分辨它是自己設的還是系統算的：\n"
        + _body)
    assert "建議" not in _body.split(BLOCK_MIX)[-1] or MIX_TARGET_LABEL in _body, (
        "這一格把數字標成了「建議」—— 那是系統宣稱的事實，"
        "而它其實是使用者自己設定的目標。")


def test_a_real_ratio_that_collides_with_the_mock_up_still_passes():
    """⭐ **真數字剛好長得跟線框示意值一樣時，示意值黑名單不得誤殺。**

    ## 這條在防的東西很反直覺，值得讀完

    `_PINNED_FAKE_VALUES` 釘著線框的示意值 `"62 ／ 38"`。
    而 `summarize_core_satellite` 的分子分母都是**使用者填的金額** ——
    一個 620000 ／ 380000 的**真實**組合算出來就是 **62.0 ／ 38.0**。
    也就是說：**真數字有可能剛好等於假數字。**

    如果本頁把比例畫成 `f"{核心} ／ {衛星}"`，那個真實組合會讓
    :func:`test_the_grey_blocks_never_print_the_illustrative_values_from_the_wireframe`
    **轉紅**，而「修法」會變成**放寬示意值黑名單** —— 那才是真正的災難：
    為了讓一個真數字過關，把擋假數字的網子剪開。

    本頁的做法是讓格式本身避開那個形狀（`_pct_text()`：數字後面緊跟 `%`，
    中間夾抬頭），於是兩者可以並存。**本條把這個性質釘死。**

    **突變驗證（實跑）**：把被測檔 `_render_mix()` 那一行改成
    `f"核心 {_core:.0f} ／ 衛星 {_sat:.0f}"` → 示意值黑名單那條**轉紅**，
    本條也**轉紅**。
    """
    _all = _text(_stream("priced"))
    for _fake in _PINNED_FAKE_VALUES:
        assert _fake not in _all, (
            f"（priced）畫面上出現了線框示意值的字面寫法 {_fake!r}。\n"
            "⚠️ 注意：這一組 fixture 算出來的 62.0 ／ 38.0 是**真數字**，"
            "所以正解**不是**把它從黑名單拿掉，而是把格式改回「數字後面緊跟 %」。")


# ══════════════════════════════════════════════════════════════════
# 「差距」的**後半** —— 所需動作（2026-09-08 補上，線框逐字要求的那一半）
# ══════════════════════════════════════════════════════════════════
# 客戶 2026-09-07 逐字：「無法判斷……搭配組合以及標的**是否需要調整**」。
# 線框 `ia-wireframe.html` 自己也寫「這裡只呈現差距**與所需動作**」。
# 到 2026-09-06 為止本頁只畫了「差距」，後半被一句
# 「要算該搬多少錢得先知道可動用金額」擋掉 —— **那句話把「再平衡」誤當成「加碼」**。
#
# ⚠️ 下面這一組刻意**不寫死任何金額字面值**（除了直接對帳的那一條）：
#    期望值一律由 `summarize_core_satellite()`（SSOT）＋ `_gap_action_text()` 現算，
#    fixture 改了、目標值改了、文案改了，這幾條會**跟著對**而不是**跟著錯**。


def _mix_gap_paragraph(kind: str = "priced",
                       session: dict[str, Any] | None = None,
                       funds: list[dict[str, Any]] | None = None) -> str:
    """「差距」那**一行**（不是整個單位）——`同一行` 是本批的硬要求之一。

    ⚠️ 回傳的是 `_flat()` 的**單一元素**：`st.markdown()` 一次呼叫 ＝ 一段。
    所以「金額有沒有跟差距在同一行」在這裡是**可驗證的**，不是形容詞。
    """
    _funds = funds if funds is not None else (
        {"loaded": FAKE_HOLDINGS, "priced": FAKE_HOLDINGS_PRICED}[kind])
    _at = _app(_funds, session=session)
    _parts = _segments(tuple(_flat(_at.main))).get(BLOCK_MIX, [])
    # ⚠️ 比對**粗體**的抬頭而不是裸的「差距」二字 —— :data:`MIX_TARGET_PROVENANCE`
    #    最後一句也含「差距」，裸比對會抓到那一段 caption（順序上它排在後面，
    #    今天取 `[0]` 剛好還是對的，但那是**運氣**，不是判準）。
    _hits = [_p for _p in _parts if f"**{MIX_GAP_LABEL}**" in _p]
    assert len(_hits) <= 1, (
        f"「{BLOCK_MIX}」出現了 {len(_hits)} 行「{MIX_GAP_LABEL}」——"
        f"差距只該有一行：\n{_hits}")
    return _hits[0] if _hits else ""


def _summary_for(funds: list[dict[str, Any]], target: float) -> dict[str, Any]:
    """測試自己**獨立**跟 SSOT 要一份摘要 —— 不從被測頁面回讀期望值。"""
    from ui.helpers.portfolio.allocation import summarize_core_satellite
    return summarize_core_satellite(funds, target_pct=target)


def test_the_gap_also_says_how_much_money_to_move():
    """⭐ 「核心比目標少 13.0%」後面要接**要搬多少錢**，而且**在同一行**。

    ## 這條在補的是客戶原話裡的那個洞

    百分比回答「差多少」，**不回答「我要動多少錢」**。而使用者拿這一格去調部位。
    ⛔ 期望值**不是寫死的字串**：本條跟 SSOT 要一份摘要、丟給被測檔自己的
    :func:`ui.views.page_04_portfolio._gap_action_text` 算出應該長什麼樣，
    再確認那一整句**逐字**出現在「差距」那一行裡。

    **突變驗證（實跑，見 PR 突變表）**：
    - 把 `_render_mix()` 裡的 `+ (f"　→　{_action}" if _action else "")` 整段拿掉
      （＝ 退回 2026-09-06 只畫差距的版本）→ **本條轉紅**。
    - 把 `_gap_action_text()` 的 `return f"{_move}{MIX_MOVE_TAIL}{_scope}"`
      改成 `return ""`（＝ 一律不講）→ **本條轉紅**。
    """
    _want = _gap_action_text(_summary_for(FAKE_HOLDINGS_PRICED, 75.0))
    assert _want, "SSOT 這組 fixture 本來就該算得出金額，測試前提壞了。"
    _line = _mix_gap_paragraph("priced")
    assert _line, f"「{BLOCK_MIX}」裡找不到「{MIX_GAP_LABEL}」那一行。"
    assert _want in _line, (
        "「差距」那一行只講了百分比，沒講要搬多少錢 —— "
        "線框逐字要的是「差距**與所需動作**」。\n"
        f"應含：{_want}\n實際那一行：\n{_line}")
    assert MIX_MOVE_TAIL in _line, (
        f"少了「{MIX_MOVE_TAIL}」—— 使用者不知道那筆錢是搬完就結束，"
        f"還是只是第一步：\n{_line}")


def test_the_money_and_the_percentage_are_two_views_of_one_number():
    """⭐ **對帳**：畫面上的金額 ÷ 總投入，必須等於畫面上的那個百分比。

    ## 為什麼要對帳，而不是比對一個寫死的數字

    寫死「NT$130,000」只釘得住這一組 fixture。**從畫面自己讀回來對帳**
    等於要求這一行**內部不自相矛盾** —— 它同時擋住：

    * 金額用了另一個分母（例如只除核心、或把總額算成別的東西）；
    * 百分比改了、金額沒跟著改（或反過來）；
    * 正負號在中途被吃掉（那會讓金額對、方向錯 —— 由下一條交叉守）。

    ⚠️ **本條刻意允許 1 元的誤差**：`fmt_twd()` 的精度是 0 位小數（四捨五入到元），
    而百分比印的是一位小數 —— 兩者的捨入不可能永遠一致。
    ⛔ 但**不允許更大的容差**：13.0% 對 1,000,000 是 130,000，
    差一個數量級就是差 90 萬，那不是捨入。

    **突變驗證（實跑）**：把 `_gap_action_text()` 的
    `_need_twd = -_diff / 100.0 * _total` 改成 `-_diff * _total`（漏掉 ÷100）
    → **本條轉紅**（金額變成 1.3 億）。
    """
    _line = _mix_gap_paragraph("priced")
    _pct = re.search(r"核心比目標(?:多|少) (\d+\.\d)%", _line)
    _amt = re.search(r"NT\$([\d,]+)", _line)
    assert _pct and _amt, (
        f"「{MIX_GAP_LABEL}」那一行讀不出百分比或金額，無法對帳：\n{_line}")
    _total = _summary_for(FAKE_HOLDINGS_PRICED, 75.0)["total_twd"]
    _expect = round(float(_pct.group(1)) / 100.0 * float(_total))
    _got = int(_amt.group(1).replace(",", ""))
    assert abs(_got - _expect) <= 1, (
        f"金額與它自己印出來的百分比對不上：{_pct.group(1)}% × "
        f"總投入 {_total:,.0f} = {_expect:,}，畫面卻寫 {_got:,}。\n{_line}")


@pytest.mark.parametrize(
    "target, expect_from, expect_to",
    [(75.0, "衛星", "核心"),   # 核心 62% < 目標 75% → 錢要往核心搬
     (41.0, "核心", "衛星")])  # 核心 62% > 目標 41% → 錢要往衛星搬
def test_the_move_direction_matches_the_gap_direction(
        target: float, expect_from: str, expect_to: str):
    """⭐ **方向**：搬錯邊比不講更糟 —— 那是一句**相反**的操作指示。

    ## 這條是 F1-c 那個教訓的第二個路口

    2026-09-06 稽核的存活突變 F1-c 證明：只驗數字、不驗方向詞，
    把「多／少」反轉全檔照樣綠。**金額這一句有完全一樣的破口，而且更貴** ——
    百分比講反了使用者還可能自己算一下；
    「從核心移 NT$210,000 到衛星」是一句**可以照著下單**的指令。

    **突變驗證（實跑）**：把 `_gap_action_text()` 的
    `_move = (... if _need_twd > 0 else ...)` 兩支對調 → **兩個參數都轉紅**。
    """
    _line = _mix_gap_paragraph("priced", session={"portfolio_core_pct": target})
    _m = re.search(r"從(核心|衛星)移 NT\$[\d,]+ 到(核心|衛星)", _line)
    assert _m, f"「{MIX_GAP_LABEL}」那一行沒有講「從哪搬到哪」：\n{_line}"
    assert (_m.group(1), _m.group(2)) == (expect_from, expect_to), (
        f"目標 {target}% 時錢應該從「{expect_from}」搬到「{expect_to}」，"
        f"畫面卻寫從「{_m.group(1)}」搬到「{_m.group(2)}」——"
        "那是一句方向相反的操作指示。\n" + _line)


def test_a_portfolio_already_on_target_is_never_told_to_move_money():
    """⭐ 「剛好落在目標上」旁邊**不准**再接一句「搬 NT$x 過去」。

    ## 這條擋的是一種很容易寫出來的自相矛盾

    差距那一行有兩個分支共用同一個容差 :data:`_ON_TARGET_TOL_PCT`。
    若金額那一半各寫一個 `0.05`（或忘了判），畫面就會同時出現
    「剛好落在目標上」與「把 NT$3 從衛星移到核心就到目標」——
    **兩句話不可能都對**，而使用者會相信後面那一句（它比較具體）。

    fixture 現況 62.0%，把目標也設成 62 → 差距 0.0，走「剛好」那一支。

    **突變驗證（實跑）**：把 `_gap_action_text()` 裡
    `if abs(_diff) < _ON_TARGET_TOL_PCT: return ""` 整段拿掉 → **本條轉紅**
    （會冒出一句「從衛星移 NT$0 到核心」之類的東西）。
    """
    _line = _mix_gap_paragraph("priced", session={"portfolio_core_pct": 62})
    assert "剛好落在目標上" in _line, (
        f"目標設成 62、現況也是 62.0%，這一行應該走「剛好落在目標上」：\n{_line}")
    assert "NT$" not in _line and MIX_MOVE_TAIL not in _line, (
        "已經在目標上了，畫面卻還叫使用者搬錢 —— 同一行自己跟自己打架：\n" + _line)
    # 兩支**共用同一個容差**這件事，直接在邊界上驗一次 —— 不是靠「兩邊都寫 0.05」。
    # ⛔ 若哪天有人把其中一支改成別的數字，這裡就會出現「剛好落在目標上」
    #    與一句搬錢指令並存的畫面，而上面那兩條斷言在**那一組**參數下未必抓得到。
    _base = {"total_twd": 1_000_000.0, "is_amount_weighted": True,
             "n_funds": 2, "n_missing_amount": 0}
    assert _gap_action_text({**_base, "diff_pct": -_ON_TARGET_TOL_PCT / 2}) == "", (
        f"差距落在容差（{_ON_TARGET_TOL_PCT}）之內時，畫面說的是「剛好落在目標上」，"
        "金額那一半必須跟著閉嘴。")
    assert _gap_action_text({**_base, "diff_pct": -_ON_TARGET_TOL_PCT * 100}), (
        "差距明顯超出容差時卻算不出金額 —— 那不是保守，是這一格失效了。")


def test_no_money_is_promised_when_nobody_filled_in_a_cost():
    """⭐ **一檔本金都沒填 → 一個金額都不准出現。**

    分母是 0 的時候，`summarize_core_satellite` 連 `core_pct` 都誠實回 `None`
    （其 docstring 逐字：「缺資料時誠實回 None，不捏造 0」）。
    此時若還印出一個金額，那個金額**憑空而來** —— 比 `0.0%` 更糟，
    因為它長得像一筆可以照著執行的交易。

    ⚠️ 本條與 :func:`test_the_mix_block_never_prints_a_zero_when_it_cannot_compute`
    **不重複**：那條驗「不准畫 0%」，本條驗「不准畫**錢**」。
    兩者的失敗長相不同，黑名單也不同（`0%` vs `NT$`）。

    **突變驗證（實跑）**：把 `_gap_action_text()` 開頭的
    `not summary.get("is_amount_weighted")` 拿掉 → 本條**不會**紅
    （上游 `core_pct is None` 時 `_render_mix()` 更早就 return 了）——
    ⚠️ **這一點據實寫出來**：本條守的是「畫面上不准有錢」這個**結果**，
    **守不到** `_gap_action_text()` 裡那一道 `is_amount_weighted` 前提本身。
    那一道由 :func:`test_the_money_helper_refuses_an_untrustworthy_ratio` 直接呼叫驗。
    """
    _body = _mix_body("loaded")
    assert NOT_READY_MARK in _body, f"沒有本金就該留灰：\n{_body}"
    assert "NT$" not in _body and MIX_MOVE_TAIL not in _body, (
        "算不出比例的時候畫面上出現了金額 —— 那筆錢是憑空來的（§1）：\n" + _body)


def test_the_money_helper_refuses_an_untrustworthy_ratio():
    """⭐ 直接呼叫：`is_amount_weighted=False` 時 :func:`_gap_action_text` 必須閉嘴。

    ## 為什麼要有一條「畫面上到不了」的測試

    上一條自陳它守不到這一道前提（`_render_mix()` 更早就 return 了）。
    但那道前提**不是多餘的**：它是「可以講金額」的**語意**條件 ——
    哪天上游改成「本金缺一半就補一個估計比例」，`core_pct` 就不再是 `None`，
    而**金額會跟著被印出來**。到那時，唯一擋著的就是這一道。

    ⛔ **不要因為「現在走不到」就把它刪掉** —— 那正是本 repo 反覆記載的死法：
    一段沒有測試的防線，下一輪會被當成沒用的東西順手拿掉。

    **突變驗證（實跑）**：把 `_gap_action_text()` 的
    `or not summary.get("is_amount_weighted")` 拿掉 → **本條轉紅**
    （它會拿一個不可信的 `diff_pct` 算出一筆錢）。
    """
    _fake = {"diff_pct": -13.0, "total_twd": 1_000_000.0,
             "is_amount_weighted": False, "n_funds": 2, "n_missing_amount": 2}
    assert _gap_action_text(_fake) == "", (
        "`is_amount_weighted=False` 代表比例本身不可信（SSOT docstring 逐字），"
        f"這種時候不准算出金額，實際回了：{_gap_action_text(_fake)!r}")


def test_the_money_says_so_when_it_only_covers_part_of_the_book():
    """⭐ **只涵蓋一半持倉的金額，必須自己說出它只涵蓋哪幾檔。**

    ## 這是本批最容易造假的一步，理由寫清楚

    沒填 `invest_twd` 的標的**不進分母**。百分比與金額**受害程度完全一樣**，
    但金額更像一道指令 —— 使用者會照著它搬錢，而它其實只算了三檔裡的兩檔。
    ⛔ **把只涵蓋一部分的金額講得像全部，比不講更糟**（`CLAUDE.md §1`）。

    ⚠️ **為什麼不是乾脆不講**：只要有一檔沒填本金就整句消失 ——
    而那正是客戶抱怨「看不出要不要調整」的那個情境。
    ⚠️ **為什麼不算重複** `format_core_satellite_caption()`：那一行講的是
    「**分母**漏了幾檔」（資料品質），這一句講的是「**這個金額**涵蓋幾檔」（指令射程）。
    同一個事實的兩面，但只有後者會被拿去下單。

    fixture：三檔（兩檔有本金、一檔沒有）—— 分母、比例、金額與
    :data:`FAKE_HOLDINGS_PRICED` **完全相同**，唯一的變因是 `n_missing_amount`。

    **突變驗證（實跑）**：把 `_gap_action_text()` 的 `_scope` 恆設為 `""`
    → **本條轉紅**，而 :func:`test_the_gap_also_says_how_much_money_to_move`
    **不會**紅（它用的是全部填了本金的 fixture）——
    **兩條 fixture 不同，守的東西才不同。**
    """
    _s = _summary_for(FAKE_HOLDINGS_PARTLY_PRICED, 75.0)
    assert _s["n_missing_amount"] == 1 and _s["n_funds"] == 3, (
        f"測試前提壞了：這組 fixture 應該是 3 檔缺 1，實際 {_s}")
    _line = _mix_gap_paragraph(funds=FAKE_HOLDINGS_PARTLY_PRICED)
    assert "NT$" in _line, f"這一組算得出金額，卻沒有畫出來：\n{_line}"
    _n_priced = _s["n_funds"] - _s["n_missing_amount"]
    assert f"{_n_priced} 檔" in _line, (
        f"金額只涵蓋 {_n_priced} 檔（另有 {_s['n_missing_amount']} 檔沒填本金），"
        f"這一句卻沒有說出它的射程：\n{_line}")
    assert f"{_s['n_funds']} 檔" not in _line, (
        f"這一句宣稱涵蓋 {_s['n_funds']} 檔，但其中 {_s['n_missing_amount']} 檔"
        f"根本不在分母裡：\n{_line}")
    # 全部填了本金的那一組**不准**冒出這個附註（否則它只是無條件加的裝飾）。
    assert "檔" not in _mix_gap_paragraph("priced").split("NT$")[-1], (
        "所有標的都填了本金時，不該還掛一句「只算 N 檔」——"
        "那會讓使用者以為有東西漏掉了。")


# ══════════════════════════════════════════════════════════════════
# 換股顧問的指路 —— 它指的那個地方是不是真的在跑（2026-09-08）
# ══════════════════════════════════════════════════════════════════

def test_the_switch_card_points_at_the_place_that_really_renders_it():
    """⭐ **指路不能指到一個沒有東西的地方** —— 本條去那個檔案裡確認它真的會渲染。

    ## 這條與既有的全域守衛**不重複**，差別要看清楚

    `tests/test_ia_switch_advisor_moved_to_portfolio.py::`
    `test_switch_advisor_renders_only_from_the_portfolio_tab` 釘的是
    「**全 repo 的渲染點恰好一個，而且在 `ui/tab3_portfolio.py::render_portfolio_tab`**」。
    它**沒有回答**「**本頁的指路指去哪**」—— 兩件事可以各自成立卻兜不起來
    （本頁在 2026-09-07 之前就正是這樣：一邊寫著「它在舊 ④ 有渲染點」，
    一邊把使用者指回本頁的試算）。

    → 本條把兩端接起來：**本頁指的那個分頁，它的檔案裡真的呼叫得到那一支。**

    ⚠️ **本條驗的是「那個地方有沒有東西」，不是「使用者點過去真的看得到」** ——
    後者要跑起整個 `app.py`，而本檔的 AppTest 只渲染本頁（`CLAUDE.md §-2` 規則 6）。
    ⛔ 這一點**不得**被讀成「已經驗過去了真的有用」。

    **突變驗證（實跑）**：把 `_render_action_cards()` 的
    `where=where_to_find("switch")` 改回 `where=_pending_where(BLOCK_FORM)`
    → **本條轉紅**（同時 `test_every_grey_unit_says_where_to_look[換股顧問]`
    與 :func:`test_the_pending_pointer_is_a_place_not_a_status_sentence` 也轉紅）。
    """
    from ui.helpers.story_nav import section_label, where_to_find as _wtf
    # 1) 本頁的換股顧問灰態，指的必須是 `switch` 這個分區。
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(switch_block_label(), []))
    assert f"（請先到：{_wtf('switch')}）" in _body, (
        f"換股顧問的灰態沒有指向 `where_to_find('switch')`：\n{_body}")
    assert section_label("switch") in _wtf("switch"), (
        "`where_to_find('switch')` 沒有帶上分區名 —— 指路只指到分頁，"
        "使用者到了那一頁還是不知道要看哪一塊。")
    # 2) 那個分區所屬的舊分頁，檔案裡真的有那一支的渲染呼叫。
    _old = ROOT / "ui" / "tab3_portfolio.py"
    _calls = [_n for _n in ast.walk(ast.parse(_old.read_text(encoding="utf-8")))
              if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
              and _n.func.id == "render_switch_advisor_section"]
    assert _calls, (
        f"本頁把使用者指到 {_wtf('switch')}，但 {_old.name} 裡"
        "找不到 `render_switch_advisor_section(...)` 的呼叫 —— 那是一條死指路。\n"
        "⛔ 若那一塊真的被移走了，正解是改本頁的指路（走 SSOT），"
        "不是把本條拿掉。")


def test_the_pointer_does_not_collide_with_this_pages_own_tab():
    """⭐ 分頁列上有**兩個**「資產配置」—— 指路指的必須是舊的那一格，而且分得出來。

    ## 這條為什麼要存在

    雙軌並行之後 `app.py` 掛了 **9 格**，其中第 4 格與第 9 格**同名**
    （`📊 資產配置` vs `[新] 📊 資產配置`）。換股顧問的指路吐的是
    ``④ 📊 資產配置 → 🎯 換股顧問`` —— 如果那個 ``[新] `` 前綴哪天沒了，
    使用者會把它讀成「就是你現在看的這一頁」，而這一頁**正是沒有換股顧問的那一頁**。
    **那會是一句原地打轉的指路。**

    ⛔ 本條**不**驗分頁列本身（那是 `tests/test_wpf_five_tab_wiring.py` 與
    `tests/test_dual_track_t9_portfolio.py` 的事）——
    它驗的是**本頁的指路與本頁自己的分頁名分得出來**。

    **突變驗證（實跑）**：把 `ui/helpers/story_nav.PREVIEW_PREFIX` 改成 `""`
    → **本條轉紅**。
    """
    from ui.helpers.story_nav import (
        preview_tab_label, tab_label, where_to_find as _wtf)
    _here = preview_tab_label("portfolio")   # 本頁在分頁列上的名字
    _there = tab_label("portfolio")          # 指路指去的那一格
    assert _here != _there, (
        "分頁列上兩格「資產配置」現在叫同一個名字 —— "
        f"指路（{_wtf('switch')}）會被讀成「就是你現在這一頁」，"
        "而這一頁沒有換股顧問。")
    assert _there in _wtf("switch") and _here not in _wtf("switch"), (
        f"指路 {_wtf('switch')!r} 指到的不是舊那一格（{_there!r}），"
        f"或反而帶上了本頁自己的名字（{_here!r}）。")


def test_the_form_block_is_not_grey():
    """再平衡試算那一塊**不得**是灰的 —— 它是本批唯一真的做完的一塊。

    ⚠️ 這是**反向**斷言，存在的理由是：所有灰態的指路都指向它。
    它哪天自己也變灰了，整頁的指路就會指向一塊同樣沒做完的東西 ——
    那時使用者拿到的是一個閉環。
    """
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(BLOCK_FORM, []))
    assert _body.strip(), f"單位「{BLOCK_FORM}」不見了。"
    assert NOT_READY_MARK not in _body, (
        f"「{BLOCK_FORM}」變成灰態了 —— 它是本批唯一做完的一塊，"
        "而且是所有灰態指路的終點。\n" + _body)
    for _lbl in (_LABEL_CORE_PCT, _LABEL_BUDGET, _LABEL_SATELLITE_ONLY):
        assert any(_lbl in _p for _p in _seg[BLOCK_FORM]), (
            f"「{BLOCK_FORM}」少了「{_lbl}」這個欄位。\n" + _body)


def test_the_page_never_hand_rolls_the_grey_mark():
    """⛔ 不准自己拼 ⬜ 字串 —— 灰態一律委派 `render_state` / `ia` 的入口。

    ⚠️ 這條堵的是 ② 被紅隊打穿的繞道：**手刻 `st.markdown("⬜ …")` 不走
    `not_ready()`，也照樣被灰態斷言認成灰態。** 自己拼的 ⬜ 不會有 `where=`、
    不會跟著 `render_state` 的視覺一起變，等於在 SSOT 旁邊長出第二套灰。

    ⛔ **只擋得住字面值。** 從 SSOT import `NOT_READY_MARK` 再自己拼、
    或 `chr(0x2B1C)`，**兩種都繞得過**（③ 已登記同一個洞，本檔沒有修）。
    """
    _bad = [f"第 {_n.lineno} 行 {_n.value[:40]!r}"
            for _n in _live_strings(_tree()) if NOT_READY_MARK in _n.value]
    assert not _bad, (
        f"本頁的活字串裡出現了 {NOT_READY_MARK!r} —— 灰態請走 "
        "`ui.helpers.render_state.not_ready()` / `ui.helpers.ia.empty_state()` / "
        "`state_card(state=STATE_NOT_READY)`：\n  " + "\n  ".join(_bad))


# ══════════════════════════════════════════════════════════════════
# Form：三個欄位、一個刻意的偏離、以及「0 不算送出」
# ══════════════════════════════════════════════════════════════════

#: ⭐ **線框那三個欄位之外，本頁**額外**允許出現的 checkbox —— 逐一具名。**
#:
#: ## 為什麼需要這個常數（2026-09-07，決策者 **AI 總管**）
#:
#: :func:`test_the_three_fields_and_the_submit_verb_come_from_the_wireframe` 的
#: checkbox 斷言原本是 ``== [_LABEL_SATELLITE_ONLY]`` —— **整頁精確相等**。
#: 它的失敗訊息自陳前提是「**骨架階段**不該有第二顆按鈕」，
#: 而**本批正是 ④ 從骨架進入內容的那一批**：客戶決定 ④ 要求配息月曆改成
#: **Checkbox Gate 延遲載入**，那必然是頁面上的第二個 checkbox。
#: → **前提過期了，所以更新這條守衛；但只更新過期的那一半。**
#:
#: ⛔ **這是「具名放行」，不是「放寬」，兩者的分界寫死在這裡**：
#: * 比對仍然是 **`==` 精確相等**，不是 `in` / `<=` / 「≥1 個」；
#: * 每一個額外的 checkbox 都要**逐字列名**在這裡；
#: * 塞第三個沒列名的 checkbox → **照樣紅**。
#: ⛔ **不准**把本常數改成 pattern／前綴／「以 gate 開頭就放行」之類的東西 ——
#:    那一刻起這條守衛就變成裝飾品。
#: ⚠️ **字面吃 `page_04_portfolio.DIVCAL_GATE_LABEL` 這個 SSOT，不在這裡抄第二份** ——
#:    抄了的話，gate 改字時本檔會**跟著錯**而不是**跟著對**。
_ALLOWED_EXTRA_CHECKBOXES: tuple[str, ...] = (DIVCAL_GATE_LABEL,)


def _expected_checkbox_labels() -> list[str]:
    """整頁**應該**出現的 checkbox 標籤，**依渲染順序**。

    線框那一個（`只調衛星`，在 Form 裡、排在前面）＋
    :data:`_ALLOWED_EXTRA_CHECKBOXES` 逐一具名的那些（排在後面）。

    ⚠️ **回傳 list 而不是 set** —— 順序本身也是斷言的一部分：
    gate 若跑到 Form 前面去，代表版面順序被動過了，那也該紅。
    """
    return [_LABEL_SATELLITE_ONLY, *_ALLOWED_EXTRA_CHECKBOXES]


def test_the_extra_checkbox_allowlist_is_exact_and_named():
    """⭐ **上面那個放行清單本身要被守住** —— 它是本批唯一在既有守衛上開的口。

    ## 這條是「更新守衛」與「改鬆守衛」的分界線

    一個「開了就沒人再看」的放行清單，就是 `CLAUDE.md §8.2.A.0` 規則 5 點名的
    **把違憲寫成合憲**。所以放行的**前提**要被釘成斷言：

    1. 清單**不是空的**（空清單會讓 :func:`_expected_checkbox_labels` 退化回舊行為，
       那時本批的 gate 反而過不了 —— 這一條是防「有人為了讓別的東西過而把它清空」）；
    2. 清單**恰好一項**，而且**就是** `page_04_portfolio.DIVCAL_GATE_LABEL`
       —— 多一項就要有人來改這條測試，也就是**多一項就要有人負責**；
    3. 它**不等於**線框那個欄位（避免有人用複製貼上把線框欄位塞進放行清單，
       那會讓 :func:`_expected_checkbox_labels` 出現兩個一樣的字串而永遠對不上）。

    ⛔ **本條刻意不驗「畫面上有幾個 checkbox」** —— 那是上一條的事。
    本條驗的是**清單本身**，所以它**不需要渲染**，在沒有 streamlit 的環境也跑得到。
    """
    assert _ALLOWED_EXTRA_CHECKBOXES, (
        "放行清單是空的 —— 空清單會讓整頁 checkbox 斷言退回「只有線框那一個」，"
        "而客戶決定 ④ 明示要有一個 Checkbox Gate。清空它等於撤銷那個決定。")
    assert _ALLOWED_EXTRA_CHECKBOXES == (DIVCAL_GATE_LABEL,), (
        f"放行清單被改成 {_ALLOWED_EXTRA_CHECKBOXES!r}。\n"
        "⛔ 每多一個 checkbox 就要多一個具名項，而且要有人來改這條測試 —— "
        "**那個「要有人來改」就是這道關卡本身**。")
    assert _LABEL_SATELLITE_ONLY not in _ALLOWED_EXTRA_CHECKBOXES, (
        "線框那個欄位被塞進「額外放行」清單了 —— 它本來就在預期清單裡，"
        "重複會讓預期清單出現兩個一樣的字串，整條斷言永遠對不上。")


def test_the_three_fields_and_the_submit_verb_come_from_the_wireframe():
    """線框 Tab 04 的 Form 逐字：「目標核心比例」「可動用金額」「只調衛星」「試算」。

    ⚠️ **送出鈕的字是「試算」不是「套用」** —— `ui.helpers.ia.APPLY_LABEL` 的預設值是
    「套用」，線框 Tab 04 明確畫的是「試算」。這不是文案潔癖：
    使用者要知道按下去會發生什麼，「套用」在一個模擬器上不知所云。

    ⚠️ **標籤上多的單位是刻意的**：畫面上是「目標核心比例（%）」「可動用金額（TWD）」。
    線框把單位寫在**值**上（「70%」「TWD 200,000」），而本 repo 的
    `CLAUDE.md §4.1` 要求「新增變數**必須**編碼單位」，且本 repo 真的有多幣別基金 ——
    一個沒有幣別的金額框正是那一節點名的陷阱。故單位進標籤，**線框的字一個沒少**。
    """
    assert (_LABEL_CORE_PCT, _LABEL_BUDGET, _LABEL_SATELLITE_ONLY) == (
        "目標核心比例", "可動用金額", "只調衛星"), (
        "欄位標籤被改了 —— 線框 Tab 04 的 Form 逐字寫的是這三個。")
    assert SUBMIT_LABEL == "試算", (
        f"`SUBMIT_LABEL` 被改成 {SUBMIT_LABEL!r} —— 線框 Tab 04 的送出鈕是「試算」。")
    _at = _app(FAKE_HOLDINGS)
    assert [_s.label for _s in _at.slider] == [f"{_LABEL_CORE_PCT}（%）"]
    assert [_n.label for _n in _at.number_input] == [f"{_LABEL_BUDGET}（TWD）"]
    # ⛔ ~~`assert [_c.label for _c in _at.checkbox] == [_LABEL_SATELLITE_ONLY]`~~
    #    → **2026-09-07 更新（有意識的政策變更，不是漏刪；決策者：AI 總管）。**
    #    **理由：這條斷言自陳的前提是「骨架階段」，而本批正是 ④ 進入內容階段的那一批。**
    #    客戶決定 ④ 要求配息月曆改成 Checkbox Gate 延遲載入 ⇒ 頁面上必然有第二個
    #    checkbox。舊斷言在那一刻起就不是在守線框，而是在守一個**已經過期的階段假設**。
    #    ⚠️ **只更新過期的那一半**：上面三條（線框欄位逐字、`SUBMIT_LABEL`、
    #    slider／number_input 精確相等）**一個字都沒動** —— 那些釘的是客戶核准線框的字面。
    #    ⛔ **比對仍是 `==` 精確相等**，放行的每一個都逐字具名在
    #    :data:`_ALLOWED_EXTRA_CHECKBOXES`（另有 :func:`test_the_extra_checkbox_allowlist_is_exact_and_named`
    #    守著那份清單本身）。**塞第三個沒列名的 checkbox 照樣紅。**
    assert [_c.label for _c in _at.checkbox] == _expected_checkbox_labels(), (
        "整頁的 checkbox 與預期清單不符。\n"
        f"預期：{_expected_checkbox_labels()}\n"
        "⛔ 多出來的那一個若是刻意新增的互動元件，請**具名**加進 "
        "`_ALLOWED_EXTRA_CHECKBOXES`（並在 PR 描述說明它為什麼該存在）；"
        "⛔ **不要**把這條改成「包含即可」——那樣任何人塞一個 checkbox 都不會紅。")
    # ⚠️ **按鈕那一條一個字都沒改**：本批**沒有**新增任何按鈕
    #    （gate 是 checkbox，不是 button）。沒有新增就不動它 —— 順手放寬一條
    #    自己用不到的守衛，是最廉價也最常見的退步。
    assert [_b.label for _b in _at.button] == [SUBMIT_LABEL], (
        "整頁的按鈕不是「恰好一顆送出鈕」—— 骨架階段不該有第二顆按鈕。")


def test_the_budget_default_deviates_from_the_wireframe_on_purpose():
    """⚠️ 可動用金額預設 **0**，**刻意不照線框的 TWD 200,000**。

    這是本檔唯一一處偏離線框字面的地方，理由寫在被測檔的模組 docstring：
    **那是使用者的錢，不是模擬參數。** 預先填一個金額，使用者只要沒注意到，
    就會拿到一份「用他沒有的 20 萬」算出來的再平衡計畫（`CLAUDE.md §1`）。

    另外兩個預設值**照線框**：目標核心比例 70、只調衛星勾選。
    ⚠️ 70 這個數字同時是線框那張卡的示意「建議 70 ／ 30」——
    **本檔畫 Form 的預設值、不畫卡片上的建議值**，分界見被測檔 docstring。
    """
    assert _DEFAULT_BUDGET_TWD == 0, (
        f"`_DEFAULT_BUDGET_TWD` 變成 {_DEFAULT_BUDGET_TWD!r} —— "
        "預填一個金額會讓使用者拿到一份用他沒有的錢算出來的計畫（§1）。")
    assert _DEFAULT_CORE_PCT == 70, "線框 Tab 04 的 Form 寫的是「目標核心比例　70%」。"
    assert _DEFAULT_SATELLITE_ONLY is True, "線框 Tab 04 的「只調衛星」是勾起來的（☑）。"
    _at = _app(FAKE_HOLDINGS)
    assert _at.number_input[0].value == 0
    assert _at.slider[0].value == 70
    assert _at.checkbox[0].value is True


def test_a_zero_budget_never_counts_as_applied():
    """沒有可動用金額 → **不算送出** —— 這是本頁唯一一條 §1 邏輯，所以它要有自己的測試。

    再平衡試算回答的是「這筆錢怎麼分」。硬把 0 當成一次有效試算，
    畫面會停在一份與任何投入都無關的結果上。

    ⚠️ 兩個層次都測：純函式（快、精確）＋ AppTest 實跑（證明它真的接在送出路徑上）。
    只測純函式的話，有人把 `_normalise_plan` 從 `_render_rebalance_form` 拆掉，
    這條照樣全綠。
    """
    assert _normalise_plan(70, 0, True) is None
    assert _normalise_plan(70, None, True) is None
    assert _normalise_plan(70, -1, True) is None
    assert _normalise_plan(70, 150_000, True) == {
        "core_pct": 70, "budget_twd": 150_000, "satellite_only": True}
    # 實跑：預設 0，直接按「試算」→ 不得寫進任何已送出條件。
    _at = _app(FAKE_HOLDINGS)
    _at.button[0].click()
    _rerun(_at)
    assert _at.session_state["v04_portfolio_applied_plan"] is None, (
        "金額 0 的送出被當成一次有效試算了。")
    # 對照組：填了金額才算數。
    _at2 = _app(FAKE_HOLDINGS)
    _at2.number_input[0].set_value(150_000)
    _at2.button[0].click()
    _rerun(_at2)
    assert _at2.session_state["v04_portfolio_applied_plan"] == {
        "core_pct": _DEFAULT_CORE_PCT, "budget_twd": 150_000,
        "satellite_only": _DEFAULT_SATELLITE_ONLY}, (
        "填了金額按下試算，卻沒有寫進已送出條件 —— 那個閘門根本沒接上。")


def test_downstream_reads_the_applied_plan_not_the_widget_values():
    """試算的**已送出值**與 widget 當下值必須是兩個東西。

    ⚠️ 這條守的是鐵則 02 真正的那一半。只包 `st.form` 只擋住「widget 互動觸發 rerun」，
    **沒有擋住重運算** —— 每次 rerun 照樣把下游跑一遍，畫面看起來沒問題、成本一分沒省
    （`ui/helpers/ia/gated_form.py` 模組 docstring 把這個陷阱寫得很清楚）。

    ⚠️ ~~**這條分不出真假閘門**（② 的紅隊實測：`if True:` 與 `if not _gate:` 都全綠）——
    它只驗「session 寫入有沒有被某個 `if` 包住」。**登記，本批不補。**~~
    → **2026-09-05 狀態更新，不是漏刪**：**`if True:` 那一種已修**（見下方重寫說明）；
    **`if not _gate:` 那一種仍然分不出來**。
    ✅ 但 :func:`test_a_zero_budget_never_counts_as_applied` 的 AppTest 那半
    **會**抓到「閘門恆真」那一種（沒按也寫進去）。兩條互補。

    📌 ~~**2026-09-05 順帶查了 `ast.Assign` 的同型盲點（總管指定，查完照實寫）——
    結論不是「這裡不受影響」，是「一半受影響、一半 fail-closed」，故本輪不改，只登記**~~
    → ✅ **2026-09-05 同日已修，登記在此保留當病史（狀態變更，不是漏刪）**：
    下面整段描述的洞（`AnnAssign` / **屬性賦值** / `update()` / **`key=`**）
    已由 `tests/_ast_bindings.py::session_writes` 四條管道全收，
    三頁 × 四管道 × 修前修後 × 三種測試順序的突變矩陣實跑於本輪 PR 描述。
    **以下原文一字未改**，因為它記的是「當時為什麼判斷可以不修」，那個判斷過程仍值得讀：
    Python 允許 ``st.session_state[k]: dict = v`` 這種 **subscript 的 `AnnAssign`**，
    本條的兩段掃描都只收 `ast.Assign`，所以：
    - **前半 fail-closed（安全）**：若把**唯一**那個寫入改成 `AnnAssign`，
      `_writes` 會變空 → ``assert _writes`` **當場轉紅**。這一半擋得住。
    - **後半有洞（不安全）**：若**保留**一個被閘門包住的 `Assign` 寫入、
      **再加**一個裸的 `AnnAssign` 寫入 → `_writes` 非空、`_naked` 空 →
      **本條全綠，而裸寫入確實存在**。
    ⛔ **本輪刻意不修**（總管指示「不要順手也改」）；且 :func:`test_a_zero_budget_never_counts_as_applied`
    的 AppTest 那半**會**抓到它造成的行為（沒按也寫進去），縱深沒破。
    ⚠️ **但「這裡只可能是 subscript assign、所以不受影響」是不成立的**，
    不要引用那個說法把本項當成已結案。

    ⭐ **上面只寫了「subscript 的 `AnnAssign`」，那還不是最該擔心的一種**
    （2026-09-05 總管指定補上，理由如下）：
    **`st.session_state.<name> = …`（target 是 `ast.Attribute`，不是 `ast.Subscript`）
    同樣落在射程外**，而它是本 repo **跨 6 檔 27 處的主流寫法**
    （本組實測，`ui/**` production：`ui/tab1_macro.py` 10、`ui/tab3_t7_ledger.py` 9、
    `ui/tab1_macro_radar.py` 4、`ui/tab3_portfolio.py` 2、`ui/tab2_single_fund.py` 1、
    `ui/tab5_data_guard.py` 1）——
    **比 `AnnAssign` 更可能被真的踩到**：下一個人照 `ui/tab1_macro.py` 的家風往這裡寫一行，
    這條守衛不會出聲。
    ✅ **前半的 fail-closed 對 attribute 形態同樣成立**（本組實測：把**唯一**那個寫入
    改成 `st.session_state.v04_portfolio_applied_plan = …` → `_writes` 由 1 變 0 →
    ``assert _writes`` 轉紅）。**破的仍然只有後半那一種組合。**
    ⚠️ **`st.session_state.update(` 這條路不現實** —— 出自另一組稽核（「全 repo 0 處」），
    **本組沒有複驗它的窮舉性**；本組只驗到一件較弱的事：以 AST 掃全 repo，
    **真正的 `st.session_state.update(...)` 呼叫點是 0**，
    `grep` 的 3 個命中全部是 `tests/test_wpg_portfolio_health_link_20260831.py`
    **docstring 裡的散文**，不是呼叫。

    📌 ~~**要修這個洞的人請先看這兩份既有實作，不要再寫第四份**
    （本批不動它們 —— 跨檔重構，超出邊界；總管另排）：~~
    → ✅ **2026-09-05 部分照辦**：兩份的長處合併進 `tests/_ast_bindings.py`
    （綁定形態取前者、session 四管道取後者），`test_settings_diag_merge.py` 已改成 import 它；
    本條與 ②③ 同樣改用它。下面兩行保留當出處：
    ⚠️ ~~**不留第二份**~~ → **2026-09-05 稽核更正，這句不為真（狀態描述錯誤，不是漏刪）**：
    **本輪只收斂了 `test_settings_diag_merge.py`。**
    `tests/test_wpg_portfolio_health_link_20260831.py` **原封未動**，
    它自己那份四管道掃描與 `_dotted` 都還在（實測仍在檔內）。
    → **待另案**；本批**刻意不遷**（跨檔重構，超出本批檔案邊界）。
    - `tests/test_settings_diag_merge.py::_reassigned_names` —— **綁定形態**最完整的一份
      （`Assign`／`AnnAssign`／`AugAssign`／`NamedExpr`／`For`／`withitem`，
      且對 target 再跑一次 `ast.walk` 找 `ast.Name`，所以 tuple／starred 解包自動涵蓋）。
    - ⭐ `tests/test_wpg_portfolio_health_link_20260831.py`（同檔 session 寫入偵測段）——
      **針對「session 寫入」這個題目，它比上面那份更貼題**，且經 4 次突變實跑驗證：
      下標賦值／**屬性賦值**／`update()`＋`setdefault()`／**widget 的 `key=`**。
      ⚠️ **第四種（`key=`）是上面兩份都沒有、而本頁的討論也一直漏掉的** ——
      streamlit 會**代呼叫端**把 widget 值寫進 `session_state`，
      它看起來完全不像賦值。**本頁的 form 三個 widget 目前都沒帶 `key=`**（本組實測），
      所以現在不是問題；**但真要補這個洞時，這一種不能漏。**
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
    for _need in ("_applied_plan", "_normalise_plan"):
        assert _need in _fns, (
            f"找不到 `{_need}()` —— 「已送出值」這一層被拿掉了，"
            "下游就會直接讀 widget 值，等於沒有 form。")
    _form_fn = _fns["_render_rebalance_form"]
        # ⚠️ 管道 4（widget `key=`）**必須**收窄成「只認守衛在乎的那個 session key」：
    #    widget 一定建在 `with applied_form(...)` 內，而閘門 `if` 一定在 `with` 外
    #    ⇒ 帶 `key=` 的 widget 結構上永遠不可能落在閘門 body 裡，不收窄就是一條
    #    **永遠無法滿足**的守衛（本 repo `ui/**` 有 231 處 `key=`，量測日 2026-09-05）。
    # ⚠️ **自動收齊模組層所有 `_SK_*`，不要列舉** —— 列舉一定會漏下一個新加的鍵。
    #    上一版只餵 `_SK_APPLIED`，於是 `key=_SK_PORTFOLIO`（使用者的 live 持股）
    #    那顆突變從紅掉成綠（2026-09-06 稽核 M-1，三頁 × 三序實測）。
    _applied_keys = guarded_key_names(_t)
    _writes = session_writes(_form_fn, widget_key_names=_applied_keys)
    assert _writes, "`_render_rebalance_form()` 沒有把送出結果寫回 session。"
    _gate_ifs = gate_ifs(_form_fn)
    assert _gate_ifs, (
        "`_render_rebalance_form()` 裡找不到 `with applied_form(...) as <gate>:` 綁出來的那個閘門 `if` —— "
        "form 沒有 gate 住任何東西（或閘門換了寫法，請同步 `gate_ifs()` 的判準）。")
    # ⚠️ 只算閘門 `if` 的 **body** —— `else:` / `elif` 是閘門為假才跑的路徑，
    #    整棵 `ast.walk(_g)` 會把它們一起算成 guarded（2026-09-05 實測的洞）。
    _guarded = gate_guarded_ids(_form_fn)
    _naked = [_w for _w in _writes if id(_w) not in _guarded]
    assert not _naked, (
        "有 session 寫入**沒有**被送出閘門包住 —— 那代表每次 rerun 都會覆寫已送出值，\n"
        "使用者拖滑桿的當下就會觸發下游重算，form 等於白包。\n  "
        + "\n  ".join(f"第 {_w.lineno} 行：{ast.unparse(_w)[:70]}" for _w in _naked))


# ══════════════════════════════════════════════════════════════════
# §1：線框的示意值一個都不准畫
# ══════════════════════════════════════════════════════════════════

#: 本條**實際釘住**的字面值 —— 線框 Tab 04 四張示意卡與 Form 上的東西。
#: 列成常數，是為了讓「它到底守了什麼」可以被讀出來，而不是藏在 docstring 的形容詞裡。
#:
#: ⚠️ **`"200,000"` 那一筆有一個已知的碰撞風險，讀到這裡就要知道**（2026-09-08 登記）：
#: 2026-09-08 起「差距」那一行會印出**真實的再平衡金額**，走 `fmt_twd()` ——
#: 而 `fmt_twd(200000)` ＝ ``"NT$200,000"`` **含有這個子字串**。
#: 也就是說，**一個真實的 20 萬再平衡金額會讓黑名單轉紅**。
#: ⛔ **屆時的正解與 2026-09-06「62 ／ 38」那次完全相同：改 fixture 或改格式，
#:    絕不是把這一筆從黑名單拿掉** —— 為了讓一個真數字過關而剪開擋假數字的網子，
#:    正是 :func:`test_a_real_ratio_that_collides_with_the_mock_up_still_passes`
#:    整條在防的東西。
#: ⚠️ **會由哪一條抓到，2026-09-08 實測過**：
#:    :func:`test_the_grey_blocks_never_print_the_illustrative_values_from_the_wireframe`
#:    只掃 `empty` / `missing` / `loaded`，而金額只在 `priced` 出現 —— **它掃不到**；
#:    真正會轉紅的是 :func:`test_a_real_ratio_that_collides_with_the_mock_up_still_passes`。
#: 📌 完整理由同時就地寫在 `page_04_portfolio._gap_action_text` 的 docstring 裡
#:    （**兩邊都寫，是刻意的**：改黑名單的人讀這裡，改金額格式的人讀那裡）。
_PINNED_FAKE_VALUES: tuple[str, ...] = (
    "現況 62 ／ 38", "建議 70 ／ 30", "62 ／ 38", "70 ／ 30",
    "2 組建議", "3 張保單", "本月 4 筆",
    "TWD 200,000", "200,000",
)


def test_the_grey_blocks_never_print_the_illustrative_values_from_the_wireframe():
    """⛔ 線框那幾張示意卡上的東西不准出現在畫面上（**只涵蓋下列字面寫法**）。

    為什麼要有這條：填一個看起來合理的核心／衛星比例，使用者**完全看不出它是假的**，
    而且會拿它去調真的部位（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ## ⚠️ 這條**實際**守得到什麼（照實寫，不要用形容詞）

    **只釘 `_PINNED_FAKE_VALUES` 這 9 個字面寫法。**
    **明確守不到**：裸數字（`62` / `38` 不帶那個全形斜線）、半形斜線的寫法、
    以及**任何線框以外的捏造值** —— 黑名單結構上抓不到名單外的第 N+1 個。

    ## ⚠️ 一個**刻意的例外**：Form 上的預設值 70

    `70` 是線框給「目標核心比例」的預設值（一個**使用者可以改的參數**），
    同時也出現在示意卡的「建議 70 ／ 30」（一個**系統宣稱的事實**）。
    本條釘的是後者那個**組合字串**（`"70 ／ 30"`），**不釘裸的 70** ——
    釘裸數字會把 Form 的合法預設值一起打紅。
    """
    for _kind in ("empty", "missing", "loaded"):
        _all = _text(_stream(_kind))
        for _fake in _PINNED_FAKE_VALUES:
            assert _fake not in _all, (
                f"（{_kind}）畫面上出現了線框的示意值 {_fake!r} —— "
                "那不是資料，是線框用來示範版面的假數字。")


#: ⭐ **「欄位清單常數」的唯一具名豁免。**
#:
#: ## 為什麼開這個洞（判準不是「我想釘」，是「線框有沒有逐欄列」）
#:
#: :func:`test_the_ledger_invents_no_column_list` 的判準是**模組層有沒有一個
#: 看起來像欄位表的常數**，而它擋的那件事是「**線框沒列欄位，所以不准自己發明**」。
#: 保單一覽**不是那個情形**：`docs/wireframes/policy-split-wireframe.html` ④ 那一段
#: 的「📋 保單一覽」把表頭**逐欄畫出來了**
#: （`保單編號 │ 基金代號 │ 基金名稱 │ 幣別 │ 級別 │ 金額 │ 現金%`）——
#: 這正是那條守衛自己的 docstring 拿來當**正面對照**的情形
#: （「`page_02_health.py::HEALTH_TABLE_COLUMNS` 之所以能釘住 9 欄，
#:   是因為**線框真的逐字列了那 9 欄**」）。
#:
#: ⛔ **豁免的前提被釘成斷言，不是寫在註解裡自律**（同 `_ALLOC_SSOT` 的處置）：
#: :func:`test_the_policy_columns_are_the_wireframe_header_verbatim` 每次跑都
#: **打開線框檔重新查證**那七個字真的在裡面。**線框改了、或有人偷加第八欄，本檔當場轉紅。**
#: ⛔ **不得往這個集合加第二個名字**，除非同樣附上一條「去線框裡查證」的斷言。
_WIREFRAMED_COLUMN_CONSTS: frozenset[str] = frozenset({"POLICY_TABLE_COLUMNS"})

#: 保單一覽表頭的出處。**客戶已拍板的線框**（`docs/wireframes/README.md` 的「客戶已拍板」表）。
_POLICY_WIREFRAME = ROOT / "docs" / "wireframes" / "policy-split-wireframe.html"


def test_the_policy_columns_are_the_wireframe_header_verbatim():
    """⭐ :data:`POLICY_TABLE_COLUMNS` 的每一欄，都要**真的**在客戶拍板的線框裡。

    ## 這條是上面那個豁免的**代價**，不是裝飾

    :data:`_WIREFRAMED_COLUMN_CONSTS` 在
    :func:`test_the_ledger_invents_no_column_list` 上開了一個洞。
    一個「開了就沒人再看」的豁免，正是 `CLAUDE.md §8.2.A.0` 規則 5 點名的那種
    **把違憲寫成合憲**：豁免當下的理由成立，之後那份清單長成什麼樣沒有人知道。
    → 所以豁免的**前提**（「這七欄是線框逐字列的」）本身要被釘成斷言。

    ⚠️ **本條讀的是線框檔，不是被測檔的常數自己** —— 沒有自我參照的恆真式。
    ⛔ **加第八欄就會紅**（除非線框裡真的也有它）—— 那正是預期行為：
       畫面上多一欄，就是自己發明了一條規格。
    """
    assert _POLICY_WIREFRAME.exists(), (
        f"找不到線框 {_POLICY_WIREFRAME} —— 保單一覽那七欄的**唯一出處**不見了。"
        "這不是「測試過期」：出處不在了，那份欄位清單就退回「自己發明」的狀態。")
    _src = _POLICY_WIREFRAME.read_text(encoding="utf-8")
    _missing = [_c for _c in POLICY_TABLE_COLUMNS if _c not in _src]
    assert not _missing, (
        f"這幾欄在客戶拍板的線框裡找不到：{_missing}\n"
        f"線框：{_POLICY_WIREFRAME.relative_to(ROOT)}\n"
        "⛔ 線框沒有的欄位 ＝ 自己發明的規格（欄位增減是客戶 gate）。")
    assert len(set(POLICY_TABLE_COLUMNS)) == len(POLICY_TABLE_COLUMNS), (
        f"欄位名重複：{POLICY_TABLE_COLUMNS}")


def test_the_ledger_invents_no_column_list():
    """⛔ 交易帳本**不准**自己發明一份欄位清單。

    線框對交易帳本**只寫了內容類型**（買賣紀錄／成本／已實現損益／對帳），
    **沒有像 Tab 02 那樣逐欄列舉**。憑印象補一份欄位表，
    下一批接真資料時就會發現欄位對不上 —— 那是自己發明規格。

    ⛔ **對照**：`page_02_health.py::HEALTH_TABLE_COLUMNS` 之所以能釘住 9 欄，
    是因為**線框真的逐字列了那 9 欄**。這裡沒有，所以這裡不釘。

    ⚠️ 判準是「模組層有沒有一個看起來像欄位表的常數」，不是「畫面上有沒有欄位名」——
    後者在骨架階段恆為真（表是空的），驗不到任何東西。

    ⛔ **2026-09-05 修（獨立稽核抓到；本條原本形同虛設）**：舊寫法只走 `ast.Assign`，
    而**被測檔 20 個模組層常數全部是 `ast.AnnAssign`**（`BLOCK_LEDGER: str = ...` 這種），
    也就是照本檔既有風格寫一行 `LEDGER_COLUMNS: tuple[str, ...] = (...)`，
    這條守衛**一個字都看不到**。⚠️ **這不是假想的攻擊** —— 姊妹頁
    `ui/views/page_02_health.py::HEALTH_TABLE_COLUMNS` 用的就是 `AnnAssign`，
    **repo 的既有寫法正好落在舊射程之外**。
    現在兩種都收（`Assign` 走 `targets` 清單、`AnnAssign` 走單一 `target`，型別不同要分開處理）。
    """
    _names: list[ast.Name] = []
    for _n in ast.walk(_tree()):
        if isinstance(_n, ast.Assign):
            _names.extend(_t for _t in _n.targets if isinstance(_t, ast.Name))
        elif isinstance(_n, ast.AnnAssign) and isinstance(_n.target, ast.Name):
            # `AnnAssign` 只有單一 `target`，不是 `targets` —— 不能跟上面共用一行。
            _names.append(_n.target)
    _bad = [_t.id for _t in _names
            if "COLUMN" in _t.id.upper() and _t.id not in _WIREFRAMED_COLUMN_CONSTS]
    assert not _bad, (
        f"被測檔多了看起來像欄位清單的常數：{_bad}\n"
        "線框對交易帳本沒有列欄位 —— 補一份等於自己發明規格。\n"
        f"（唯一具名豁免：{sorted(_WIREFRAMED_COLUMN_CONSTS)} —— "
        "見 `_WIREFRAMED_COLUMN_CONSTS` 的長註，豁免的前提由 "
        "`test_the_policy_columns_are_the_wireframe_header_verbatim` 每次重新查證）")


# ══════════════════════════════════════════════════════════════════
# 邊界：走共用元件、不碰底層、不委派舊頁、不搶別人的渲染點
# ══════════════════════════════════════════════════════════════════

def test_the_page_draws_no_grid_form_or_tabs_of_its_own():
    """鐵則 01 / 02 一律走共用元件；巢狀 `st.tabs` 一個都不准有。

    ⚠️ **`st.columns` 那半只有本條在守。** 全域
    `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL` 抓的是「**欄數不是 3**」
    的呼叫 —— 合規的 `st.columns(3)`（＝鐵則 01 叫你開的那個）它**一動也不動**
    （③ 的獨立紅隊 2026-09-05 實測）。
    ⚠️ **`st.form` 那半有全域網子**：`FORM_SITE_TOTAL` 是精確 `==`，多一個站點就紅。
    ⚠️ **`st.tabs` 是線框 Tab 04 的「這裡不放什麼」逐字**：
       「⚠️ **巢狀 `st.tabs` 一律不留**；分頁只有一層」。

    ⛔ **本條擋得住的只有這三個 attribute 名。** `getattr(st, "columns")(3)` 與
    `from streamlit import columns as _c` 都繞得過 —— 但全域那條對 alias 同樣失明，
    那是 repo 既有性質，不是本頁造成的。
    """
    _bad = _attr_calls(_tree(), ("columns", "form", "tabs"))
    assert not _bad, (
        "本頁自己開了網格 / 表單 / 巢狀分頁，沒有走 IA kit：\n  " + "\n  ".join(_bad)
        + "\n請改用 `ui.helpers.ia.render_cards()` 與 `ui.helpers.ia.applied_form()`；"
          "巢狀 `st.tabs` 依線框 Tab 04「這裡不放什麼」一律不留。")


def test_the_wide_table_goes_through_wide_table_not_st_dataframe():
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


def test_the_page_never_reaches_into_the_data_layer():
    """客戶方針第 2 條：資料只走 `services/**`，**不碰** `repositories` / `infra` / 網路函式庫。

    ⚠️ 本批連 `services/**` 都沒有呼叫（骨架階段沒有東西要算）——
    但這條**現在就要在**，因為下一批填內容時它才是真正在守的那道線。
    """
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.split(".")[0] in ("repositories", "infra", "requests", "httpx",
                                    "yfinance", "gspread", "urllib", "bs4",
                                    "feedparser")]
    assert not _bad, (
        "本頁 import 了資料層 / 網路函式庫：" + ", ".join(_bad)
        + "\n客戶方針第 2 條：UI 只讀對接既有 Service，取不到就誠實灰態，**不反向修底層**。")


#: ⭐ **`ui.helpers.portfolio` 底下唯一具名豁免的模組**（2026-09-06 接線批新增）。
#:
#: ## 為什麼要開這個洞（三條**實測**依據，不是「我覺得它應該算純函式」）
#:
#: 1. **它是純函式，不是 UI。** 全檔 import 只有 `typing.Optional` 與一行
#:    **函式內** `from ui.helpers.session import INITIAL_SESSION_STATE`（取預設值）——
#:    **零 `streamlit`、零 IO、零 `repositories`**。由
#:    :func:`test_the_named_exemption_is_still_a_pure_ssot` **每次跑都重新查證**。
#: 2. **它是核心／衛星的全站唯一真相。** 該檔 docstring 自陳存在理由是收掉
#:    「同一頁 4 處各算各的、3 種定義、2 種目標值」；`services/health/asset_class.py`
#:    就地註解也指著它。它有兩個專屬測試檔（`test_portfolio_allocation.py` /
#:    `test_core_satellite_single_verdict.py`）。
#: 3. **`services/**` 沒有替代品。** 實測 `git grep -n "portfolio_core_pct|
#:    summarize_core_satellite|get_core_target_pct" origin/main -- 'services/'`
#:    只命中 `services/health/asset_class.py` 的**註解**（它自己也是指回這一支）。
#:    唯一名字相近的 `services/policy_advisor_service.py::recommend_policy` 是
#:    **另一把尺**（單一保單級／不看 `policy_tier`；2026-09-06 更正：~~target 寫死 75~~
#:    那條實測不成立，見 `test_the_page_does_not_use_the_look_alike_advisor` 的更正段），
#:    接了會得到「名字對、意思錯」的比例 —— 由
#:    :func:`test_the_page_does_not_use_the_look_alike_advisor` 明文擋住。
#:
#: ## ⚠️ 這個豁免的**射程與未驗狀態**，據實寫明（`CLAUDE.md §-2` 規則 6）
#:
#: 本守衛原本的判準是子字串 `"ui.helpers.portfolio" in _m`，它**同時**罩住
#: 兩種東西：真正的舊 ④ UI 區塊（`policy_admin_section.py` 會渲染畫面）與
#: 這一支純函式 SSOT。本次**只把後者具名放行，前者一個字都沒放寬**。
#: ⛔ **「`allocation.py` 到底會不會跟著舊 ④ 一起被拔除」本組沒有查證、也不宣稱** ——
#:    那取決於一個還沒發生的 scope 決定（`CLAUDE.md §8.4` step 4：範圍屬客戶／總管）。
#:    本組的判斷是「不會，因為拔了它核心／衛星就沒有真相源了」，
#:    但那是**論證不是事實**，已在 PR 描述具名回報請總管覆核。
#:    若總管認定它確實在拔除名單內，**請推翻本豁免並把核心／衛星那一格退回灰態** ——
#:    退回的成本只有一格，遠低於留一條會斷頭的委派。
_ALLOC_SSOT: str = "ui.helpers.portfolio.allocation"


def _exempted_by_name(mod: str) -> bool:
    """具名豁免的判準：**恰好是** :data:`_ALLOC_SSOT`，或它底下用點接的名字。

    ## 為什麼不是 ``mod.startswith(_ALLOC_SSOT)``（2026-09-06 稽核擋下，實測後更正）

    舊判準是裸的 ``startswith``，那是**前綴**豁免、不是**具名**豁免 ——
    而同一條守衛的失敗訊息與 PR 描述都寫「唯一**具名**豁免」。
    **判準與記錄不一致，且鬆的那一邊是判準。**

    純字串實測（`_ALLOC_SSOT` = ``ui.helpers.portfolio.allocation``）::

        模組名                                              舊 startswith   本函式
        ui.helpers.portfolio.allocation                     True            True
        ui.helpers.portfolio.allocation.summarize_...       True            True
        ui.helpers.portfolio.allocation_evil                True    🔴      False  ✅
        ui.helpers.portfolio.allocation_anything            True    🔴      False  ✅
        ui.helpers.portfolio.allocationX                    True    🔴      False  ✅
        ui.helpers.portfolio.health                         False           False
        ui.helpers.portfolio.policy_admin_section           False           False

    也就是說：**任何叫 ``allocation*`` 的新檔都會自動獲得豁免**，
    包含一支 import 了 streamlit／requests 的檔。
    ⚠️ 這**不是假想**：本次回修在 clone 內建了 `allocation_evil.py`
    （內含 ``import streamlit`` / ``import requests``）讓本頁 import 它，
    **舊判準下全檔 49 passed、兩道守衛都沒響**；換成本函式後當場轉紅（實測，見 PR 描述）。

    ## 為什麼點號那一支要留

    :func:`_imported_modules` 對 ``from X import Y`` 會**同時吐** ``X`` 與 ``X.Y``
    （見該函式的長註）。所以 ``ui.helpers.portfolio.allocation.summarize_core_satellite``
    這種「不是模組的字串」一定會出現，必須放行，否則本頁自己的 import 會被誤殺。
    ⚠️ **今天 `allocation` 是一支 .py 檔、不是套件**（實測 ``ui/helpers/portfolio/allocation.py``
    存在、同名目錄不存在），所以點號後面只可能是**符號名**，不可能是真的子模組；
    若日後它被改成套件，:func:`test_the_named_exemption_is_still_a_pure_ssot`
    會因為解析到的檔案清單改變而重新涵蓋它（該條已改為讀「本頁實際 import 的東西」）。
    """
    return mod == _ALLOC_SSOT or mod.startswith(_ALLOC_SSOT + ".")


def test_the_named_exemption_is_still_a_pure_ssot():
    """⭐ 具名豁免的**自我巡邏**：`allocation.py` 一旦不再是純函式，本條當場轉紅。

    ## 這條存在的理由（比它擋的東西更重要）

    :data:`_ALLOC_SSOT` 是本檔在一條既有守衛上開的**唯一一個洞**。
    一個「開了就沒人再看」的豁免，就是 `CLAUDE.md §8.2.A.0` 規則 5 點名的那種
    **把違憲寫成合憲**：豁免當下的理由成立，之後那個檔案變成什麼樣沒有人知道。
    → 所以豁免的**前提**（它是純函式 SSOT）本身要被釘成斷言，而不是寫在註解裡自律。

    ⚠️ **本條讀的是被豁免那個檔案的原始碼，不是本頁的。** 它會因為**別人**改壞
    `allocation.py` 而轉紅 —— 那正是預期行為：那一刻本頁的豁免就不再成立。

    ⛔ **守不到什麼（三條，第三條是 2026-09-06 稽核實測補上的）**：

    1. 它**只看 import**。被豁免的檔案若改用 `__import__("streamlit")` 或在函式內
       組字串動態載入，本條看不到（同本檔其餘 AST 守衛的既有射程）。
    2. 它只看**被豁免的那幾支**，不看它們的**呼叫對象**。
    3. ⭐ **「一跳洗白」：只查一層 import，經另一支 `ui.*` 模組轉一手就完全繞過。**
       髒名單比對的是**模組路徑的第一段**（`_m.split(".")[0]`），而 **`ui` 不在髒名單裡** ——
       所以只要中間隔一支 `ui.*`，`streamlit` / `requests` 就洗白了。
       **實測（2026-09-06，回修組在自己的 clone 重現）**：在 `ui/helpers/portfolio/` 放一支
       `_launder.py`（內含 `import streamlit` / `import requests`），讓 `allocation.py`
       `from ui.helpers.portfolio import _launder` —— **全檔 51 passed，兩道守衛都沒響。**
       ⚠️ **這不是本輪造成的退步**：舊版同樣只查一層，本輪改的是「**查哪些檔**」
       （寫死 → 跟著實際 import 走），**沒有改「查幾層」**。
       ⚠️ **但本條原本列的逃生口漏了它** —— 只寫了 `__import__` / 動態載入這種
       「**繞過 AST**」的手法，**沒寫「不繞過 AST、光明正大 import，但多轉一手」**這種。
       **後者不需要任何奇技淫巧，是實務上真的會自然發生的形狀**（有人為了整理而抽一支
       共用模組），所以它比前兩條更該被寫下來。
       ⛔ **本批只補這行文字，未改判準**（`CLAUDE.md §-1`：無 user 指派、無 bug 觸發；
       且遞迴追 import 會把射程擴到整個 `ui/**`，屬 `§8.4` step 4 的 scope 決定）。
       **登記，不宣稱已解決。**

    ## ⚠️ 2026-09-06 更正：本條原本**寫死去讀 `allocation.py`**，從不看本頁實際 import 了什麼

    稽核實測抓到的形狀：在 `ui/helpers/portfolio/` 底下新建一支
    `allocation_evil.py`（內含 ``import streamlit`` / ``import requests``）
    並讓本頁 import 它 —— **兩道守衛都沒響，全檔 49 passed**。
    原因是兩道各瞎一半：

    * :func:`test_the_page_does_not_delegate_to_the_old_tabs` 當時用**前綴**比對
      （``startswith``），``allocation_evil`` 前綴命中 ⇒ 被當成豁免放行；
    * **本條**寫死讀 `allocation.py`，那支檔案本身乾淨 ⇒ 綠燈。

    也就是說：**豁免的「誰能過」與「過了的要乾淨」中間有一道縫。**
    前者已改為具名比對（:func:`_exempted_by_name`）；**本條同步改為
    「本頁實際 import 到什麼、就去讀什麼」**，兩條因此接成一個閉環 ——
    日後若有人再把 :func:`_exempted_by_name` 放寬，本條會**自動**跟著涵蓋新放行的檔案，
    不必有人記得回來改這裡。這正是 `CLAUDE.md §8.2.A.0` 規則 3 的精神
    （清單由測試強制，不靠人工同步）。

    ⚠️ **仍然保留「宣告的那支一定要在、一定要乾淨」**：若本頁哪天完全不 import 它，
    只驗「實際 import 到的」會**空集合通過**（vacuous pass），豁免的自我巡邏就沒了。
    """
    # 要police 的檔案 = 宣告的那支（永遠驗）∪ 本頁實際在豁免名下 import 到的每一支。
    _names = {_ALLOC_SSOT} | {_m for _m in _imported_modules(_tree())
                              if _exempted_by_name(_m)}
    _srcs: dict[str, pathlib.Path] = {}
    for _name in sorted(_names):
        _base = ROOT.joinpath(*_name.split("."))
        if (_base / "__init__.py").exists():      # 它是套件
            _srcs[_name] = _base / "__init__.py"
        elif _base.with_suffix(".py").exists():   # 它是模組
            _srcs[_name] = _base.with_suffix(".py")
        elif _name == _ALLOC_SSOT:
            # 宣告的豁免指向一個不存在的東西 ⇒ 一定是錯的，立刻炸。
            raise AssertionError(f"具名豁免指向一個不存在的模組：{_name}")
        # 其餘解析不到的，是 `_imported_modules` 對 `from X import Y` 多吐的**符號名**
        # （見該函式長註），不是模組 ⇒ 跳過。它的模組本體 `X` 一定也在 `_names` 裡。

    _dirty: dict[str, list[str]] = {}
    for _name, _src in _srcs.items():
        _mods = _imported_modules(ast.parse(_src.read_text(encoding="utf-8")))
        _bad = [_m for _m in _mods
                if _m.split(".")[0] in ("streamlit", "repositories", "infra",
                                        "requests", "httpx", "yfinance", "gspread",
                                        "urllib", "bs4", "feedparser", "pandas")]
        if _bad:
            _dirty[_name] = _bad
    assert not _dirty, (
        "在具名豁免底下被放行的模組不再是純函式 SSOT：\n  "
        + "\n  ".join(f"{_k} import 了 {_v}" for _k, _v in _dirty.items())
        + "\n本頁對它的具名豁免（`_ALLOC_SSOT`）建立在「它是零 IO、零 streamlit 的純函式」"
        "這個前提上 —— 前提沒了，豁免就該收回，核心／衛星那一格退回灰態。")


def test_the_page_does_not_use_the_look_alike_advisor():
    """⛔ **名字對、意思錯的那一個**：`policy_advisor_service` 不准出現在本頁。

    `services/policy_advisor_service.py::recommend_policy` 講的也是「核心配置百分之幾」，
    接起來畫面上**看不出任何異狀** —— 但它是用另一把尺量的：

    ====================== ================================ ==============================
    項目                    `recommend_policy`               本頁用的 SSOT
    ====================== ================================ ==============================
    範圍                    **單一保單**內的基金              **整個組合**
    核心／衛星怎麼分         只看 `is_core`（名稱關鍵字啟發）  **`policy_tier` 優先**，缺才退
    ====================== ================================ ==============================

    ## ⚠️ 2026-09-06 更正：原本這裡還有第三列「目標值哪來」，那一列是**假的**

    舊表寫「`recommend_policy` 的 target 參數預設**寫死 75.0**」，並據此推出
    ~~「session 預設也是 75 ⇒ **預設下兩者一模一樣，使用者拉滑桿才分歧**」~~。
    **實測推翻（稽核擋下）**：`75.0` 只是**參數預設值，production 從來沒被用過**。
    全 repo 唯一的 production 呼叫點是 `ui/tab3_portfolio.py`::

        _policy_target = _get_core_target_p(st.session_state)   # = get_core_target_pct
        _p_rec = recommend_policy(_funds_enriched, target_core_pct=_policy_target)

    —— 它傳的是 **session 值**，而且走的是**與本頁同一支 SSOT 函式**
    (`ui.helpers.portfolio.allocation.get_core_target_pct`)。目標值兩邊本來就同源，
    **分歧軸與滑桿無關**，只有上表那兩條（分類、範圍）。

    ## 分歧有多大：把目標值固定成同一個數，實測差 62 個百分點

    用本檔 :data:`FAKE_HOLDINGS_PRICED`（620000 `core` ／ 380000 `satellite`）、
    兩邊同給 ``target=75.0``（刻意排除「目標不同」這個變因）：

    * `summarize_core_satellite` → ``core_pct = 62.0``
    * `recommend_policy` → 訊息是「核心配置 **0.0%** 低於目標 75%（-75.0%）」

    0.0 的來源正是分類那一列：fixture 用 `policy_tier` 明示級別、**沒有 `is_core` 欄位**，
    而 `recommend_policy` 只看 `is_core` ⇒ 它認為一檔核心都沒有。
    （`git grep -n policy_tier -- services/policy_advisor_service.py` **0 命中**；
    正對照：同一條 grep 在全 repo 命中 10+ 檔，所以那個 0 是真的 0。）

    ## ⚠️ 被引用的那份文件**沒有錯**，錯的是從它推出來的那一步

    舊表述引 `PHASE1_UX_AUDIT_PROPOSAL.md` 的「`portfolio_core_pct` 75%
    （**碰巧一致，無機制保證**）」當靠山。**那句話本身是對的，不要去改它** ——
    它在一份「**應綁 SSOT 而未綁**」的清單裡，講的是「**有一個寫死的 75 字面值，
    剛好與 session 預設同值，但沒有機制保證它們同步**」。那是一句關於**字面值**的話。

    ⛔ **舊表述把它擴寫成一句關於 production 行為的話** ——
    「所以**預設下兩者算出來一模一樣**，拉滑桿才分歧」。**這一步不成立**：
    production 根本走不到那個字面值（唯一呼叫點顯式傳 session 值）。
    **原文說的是「這個常數沒綁 SSOT」，被讀成了「這條路徑會用到這個常數」。**
    ⚠️ 記這一筆是因為：**引用是真的、出處是真的，錯的是中間那一步推論** ——
    這種錯比抄錯數字更難抓，因為每一個零件看起來都有出處。

    ⚠️ **它連 `core_pct` 這個欄位都不回** —— AST 掃過它 **6** 條 return path
    （`services/policy_advisor_service.py` 的 `182 / 194 / 205 / 222 / 238 / 248` 行，
    函式跨 159–255、**無巢狀 def**），鍵**一律**只有 ``{code, color, text}``；
    那個百分比是**內嵌在 `text` 中文句子裡**的。
    （舊表述寫「也吐一個叫 `core_pct` 的數字」，一併更正。）

    ⚠️ **2026-09-06 二度更正：~~「4 條」~~ 是假的，實為 6 條**（稽核以 AST 重數後擋下）。
    **結論不受影響、反而更強** —— 6 條**全部**不回 `core_pct`。
    ⛔ **這個錯的形狀值得記**：本組當時是用 `sed -n '159,235p'` 切一段再 `grep return`，
    而該函式**跨到 255 行** —— 那個切片**在 235 行就截斷了**，`238` 與 `248` 兩條
    根本不在視野內。**把截斷的輸出當成全部**，於是數出 4 條。
    （同批的 AST 腳本其實有走完整個函式、鍵也數對了，**錯的只有那個從截斷 grep 抄來的條數**。）
    → **要數「有幾條」就別用行區間切片**：函式邊界要靠 AST 的 `lineno/end_lineno` 拿，
    不能靠肉眼估一個範圍。
    所以「接它」實際上是把一句**用另一把尺算出來的話**貼上畫面，
    比「拿錯一個數字」更難被發現 —— 這反而讓本條的阻擋結論**更強**，不是更弱。

    ⛔ 這正是派工單點名的那個坑：**接一個名字對、語意錯的來源，比留白更糟。**
    """
    _bad = [_m for _m in _imported_modules(_tree()) if "policy_advisor" in _m]
    assert not _bad, (
        "本頁 import 了 `policy_advisor_service`：" + ", ".join(_bad)
        + "\n它是保單級、只看 `is_core` 不看 `policy_tier` —— "
        "與本頁「整個組合 vs 使用者自己設的目標」不是同一件事。")


def _delegated_modules() -> set[str]:
    """:data:`DELEGATED_ENTRIES` 裡出現過的模組名（白名單的模組那一半）。"""
    return {_m for _m, _ in DELEGATED_ENTRIES}


def test_the_page_only_delegates_to_the_registered_entries():
    """⛔ 委派只能發生在 :data:`DELEGATED_ENTRIES` 逐字列名的那幾支上。

    ## ⚠️ 2026-09-07：本條的**放行面**換了，函式名一起改（原
    `test_the_page_does_not_delegate_to_the_old_tabs`）

    **舊條**：`ui.tab*` / `fund_grp_health` / `portfolio_perf` / `ui.helpers.portfolio`
    **一律禁止**（只有 `_ALLOC_SSOT` 一個具名豁免），docstring 逐字寫著
    「**本頁一條都沒有，而且要維持這樣**」。
    **新條**：客戶 2026-09-07 指示**路線 (A)**（「邏輯呼叫既有舊模組，不重寫、
    不搬移、不改資料路徑」）—— 與 ② 2026-09-06 收到的是同一條指示。
    **舊條的顧慮沒有消失**（「每多一條委派就多一處會斷頭」今天依然成立），
    它變成了 :data:`DELEGATED_ENTRIES` 的存在理由：**拔除那天要回來改的地方只有那一張表。**

    ⛔ **放行面沒有變成「那幾個資料夾都放行」** —— 那會是真的放寬。
    放行的是**逐支列名**的模組；同一個資料夾裡沒被列名的東西**照樣紅**。
    形狀直接抄 `tests/test_wf02_health_skeleton.py` 的同型守衛
    （② 的那條也是「舊條整包封鎖 → 新條逐支白名單」，理由與本條逐字相同）。
    """
    _allowed = _delegated_modules() | {_ALLOC_SSOT}
    assert _allowed, "白名單是空的 —— 空白名單會讓本條退化成整包封鎖。"
    _bad = [_m for _m in _imported_modules(_tree())
            if (_m.startswith("ui.tab")
                or "fund_grp_health" in _m
                or "portfolio_perf" in _m
                or "ui.helpers.portfolio" in _m
                or "ui.helpers.macro" in _m)
            and not any(_m == _a or _m.startswith(_a + ".") for _a in _allowed)]
    assert not _bad, (
        "本頁委派了**沒有登記**的舊 ④ 來源檔：" + ", ".join(_bad)
        + "\n每一支委派都要進 `page_04_portfolio.DELEGATED_ENTRIES` 受審 —— "
          "那是「悄悄多接一支」唯一的關卡。\n"
        + f"（另有一個具名豁免：{_ALLOC_SSOT} —— 見 `_ALLOC_SSOT` 的長註）")


def test_delegation_matches_the_registry():
    """⭐ **本頁實際 import 到的委派入口，與 :data:`DELEGATED_ENTRIES` 精確集合相等。**

    ## 兩個方向都要擋，缺一邊就等於沒守

    - **多接一支沒登記的** → 白名單那條（上一條）擋得住「模組」，
      但擋不住「同一個模組裡多 import 一個符號」。本條擋得住。
    - **登記了卻沒接** → 一張比實作長的表，讀的人會以為那幾塊已經接上了。
      這一半**沒有任何其他守衛在看**。

    ⚠️ 形狀（精確 `==`，不是 `<=` 也不是 `>=`）直接抄 ② 的
    `tests/test_wf02_health_skeleton.py`；那條的病史逐字記著單向比對的代價。
    ⚠️ 只比對 :data:`DELEGATED_ENTRIES` **列到的那幾個模組**的 import ——
    版面共用元件（`ui.helpers.ia` / `render_state` / `story_nav`）不在射程內，
    它們不是「被委派的舊模組」。
    """
    _mods = _delegated_modules()
    _actual: set[tuple[str, str]] = set()
    for _n in ast.walk(_tree()):
        if isinstance(_n, ast.ImportFrom) and _n.module in _mods:
            _actual |= {(_n.module, _a.name) for _a in _n.names}
    _want = {tuple(_e) for _e in DELEGATED_ENTRIES}
    assert _actual == _want, (
        "本頁實際 import 到的委派入口與 `DELEGATED_ENTRIES` 不一致。\n"
        f"表上有、實作沒接：{sorted(_want - _actual)}\n"
        f"實作接了、表上沒有：{sorted(_actual - _want)}\n"
        "⛔ 新增委派請同時更新 `page_04_portfolio.DELEGATED_ENTRIES`（那是 SSOT）。")


def test_the_page_never_delegates_to_the_write_blacklist():
    """⛔ :data:`DELEGATION_BLACKLIST` 上那兩支，一個字都不准 import。

    ## 為什麼要有一條**專門**擋它們的守衛

    `render_portfolio_tracking` **打開就寫一列進客戶的 Google Sheet**，
    沒有按鈕、沒有勾選（② 已具名列進 `page_02_health.DELEGATION_BLACKLIST`，
    理由逐字：「接了就是把 P0 寫入面搬回 ②」）。
    它與本頁委派的 `render_portfolio_performance` **在畫面上是同一個標籤的兩張卡**，
    所以「順手把兩張都接上」是一個**看起來很合理**的動作 ——
    客戶決定 ③ 明示「只留一份」，而留的是不寫入的那一支。

    ⚠️ **這條與零寫入守衛不重複**：`tests/test_wf04_portfolio_no_writes.py`
    掃的是**閉包內的寫入動作**，它會在接了之後才紅；本條在**接的當下**就紅，
    而且訊息會直接說出「這是那兩支不准接的東西」。
    ⚠️ 它們同時也**不在** :data:`DELEGATED_ENTRIES` 裡，所以上面兩條也會紅 ——
    **三條一起紅是刻意的**（`CLAUDE.md` 的縱深防禦）。
    """
    _imports = set(_imported_modules(_tree()))
    _bad = [f"{_m}::{_sym}" for _m, _sym in DELEGATION_BLACKLIST
            if _m in _imports or f"{_m}.{_sym}" in _imports]
    assert not _bad, (
        "本頁 import 了寫入黑名單上的東西：" + ", ".join(_bad)
        + "\n它們**打開就寫一列進客戶的 Google Sheet**（沒有按鈕、沒有勾選）。"
          "客戶決定 ③『組合績效只留一份』留的是不寫入的那一支。")


def test_the_page_never_renders_the_switch_advisor_section():
    """⛔ 本頁**不得**呼叫 `render_switch_advisor_section` —— 那一塊已經有唯一渲染點。

    `tests/test_ia_switch_advisor_moved_to_portfolio.py::`
    `test_switch_advisor_renders_only_from_the_portfolio_tab` 釘住它的呼叫點**恰好一個**
    （在舊 ④）。本頁若「順手也 render 一次」，那條全域守衛會當場轉紅，
    而且線上會撞 widget key `switch_advise_btn` → `DuplicateWidgetID`。

    ⚠️ 本條與那條全域守衛**不重複**：那條問「全 repo 有幾個呼叫點」，
    本條問「**本檔**有沒有」—— 本檔紅時訊息會直接指向這裡，不必去讀另一個檔的集合差。
    """
    _bad = [f"第 {_n.lineno} 行" for _n in ast.walk(_tree())
            if isinstance(_n, ast.Call)
            and (getattr(_n.func, "id", None) == "render_switch_advisor_section"
                 or getattr(_n.func, "attr", None) == "render_switch_advisor_section")]
    assert not _bad, (
        "本頁呼叫了 `render_switch_advisor_section` —— 它的渲染點必須恰好一個：\n  "
        + "\n  ".join(_bad))


def test_holdings_filters_out_the_not_yet_loaded_and_the_failed():
    """`_holdings()` 只回**已載入且沒有錯誤**的項目，其餘一律排除。

    ⚠️ **這個過濾是刻意的**：`portfolio_funds` 裡會有「已列入但 NAV 還沒抓回來」
    與「抓取失敗」的項目（`ui/helpers/portfolio/load.py` 寫入 `loaded` / `load_error`）。
    拿那些去算配置比例，等於用不完整的資料生一個看起來完整的結論（§1）。

    ⛔ **本條沒有測到的**：舊版 payload 形狀（缺 `loaded` 以外的其他欄位組合）。
    ⚠️ **本條直接寫 bare-mode 的 `st.session_state`，跑完會還原** ——
    不還原的話，它會依測試順序污染別的測試（`AppTest` 有自己的 session，不受影響，
    但同檔／同 session 的其他直呼路徑會）。
    """
    import streamlit as _st

    _cases = (
        (None, 0),
        ("不是 list", 0),
        ([], 0),
        ([{"code": "A"}], 0),                                   # 沒有 loaded
        ([{"code": "A", "loaded": True}], 1),
        ([{"code": "A", "loaded": True, "load_error": "429"}], 0),
        ([{"code": "A", "loaded": True}, {"code": "B"}], 1),
        (["不是 dict", {"code": "A", "loaded": True}], 1),
    )
    _had = "portfolio_funds" in _st.session_state
    _saved = _st.session_state.get("portfolio_funds") if _had else None
    try:
        for _raw, _want in _cases:
            _st.session_state["portfolio_funds"] = _raw
            assert len(_holdings()) == _want, (
                f"`_holdings()` 對 {_raw!r} 回了 {_holdings()!r}，預期 {_want} 筆。")
    finally:
        if _had:
            _st.session_state["portfolio_funds"] = _saved
        else:
            _st.session_state.pop("portfolio_funds", None)


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded", "priced"])
def test_no_block_silently_renders_a_system_error(kind: str):
    """⛔ **四**種 session 形狀下，都不得有任何區塊掉進 `safe_section()` 的紅框。

    ⚠️ **2026-09-06 增列 `"priced"`**：核心／衛星那一格接上真資料之後，
    「有本金」是**唯一會真的走進計算分支**的形狀 —— 只跑前三種的話，
    那條新路徑上任何例外都不會被本條看到。

    ## 這條擋的是一種「測起來會綠、實際壞掉」的形狀

    `render_asset_allocation()` 把每一塊都包在 `safe_section()` 裡（區塊級隔離）。
    那是對的 —— 但它的**副作用**是：某一塊拋例外時，**AppTest 不會有 `exception`**，
    只會多出一個 `st.error` 紅框，而其他斷言（順序、灰態）**只看得到那一塊不見了**，
    訊息會指向「單位不見了」而不是「它炸了」。

    本條直接驗**渲染流裡沒有 `Error` / `Warning` 元素**，
    紅了就會直接把 `friendly_error()` 印的例外類型與訊息貼出來。

    ⚠️ **`Warning` 也一起擋**：`render_state.system_error(degraded=True)` 走的是
    `st.warning`（`ui/helpers/render_state.py` 的五態表）。骨架階段**不該有任何一種**。
    ⚠️ **反過來說，這條在下一批會需要重看**：真內容接上後，
    某些區塊可能**合法地**出現業務警示或降級橘框。**屆時要改的是本條的射程
    （限定「不得有 `system_error` 紅框」），不是把它刪掉。**
    """
    _bad = [_p for _p in _stream(kind)
            if _p.startswith("[Error]") or _p.startswith("[Warning]")]
    assert not _bad, (
        f"（{kind}）有區塊掉進 `safe_section()` 的紅框 —— 骨架階段不該有任何例外：\n  "
        + "\n  ".join(_bad))


# ══════════════════════════════════════════════════════════════════
# 2026-09-07 客戶四項拍板：每一項各自的**正向**守衛
# ⚠️ `_WIRED_UNITS` 多一個名字，這裡就要多一組守衛（那條規則寫在 `_WIRED_UNITS` 上）。
# ══════════════════════════════════════════════════════════════════

def _policy_body(kind: str = "loaded") -> str:
    """`BLOCK_POLICY` 那一個單位的渲染內容（字串）。"""
    return "\n".join(_segments(_stream(kind)).get(BLOCK_POLICY, []))


def test_the_status_bar_is_four_cells_because_the_client_said_so():
    """⭐ **決定 ②：狀態列四格。** 四個抬頭都要在畫面上，而且 :data:`STATUS_COLS` 是 4。

    ## ⚠️ 這條同時是一個**已知未驗風險**的登記點，不要把它讀成「已經驗過了」

    「四格在窄螢幕會不會塌成兩列」**本 repo 從來沒有人實測過**，本輪也**沒有測到** ——
    沙箱沒有 `streamlit`／沒有瀏覽器；AppTest 回的是元素樹、**沒有 viewport 也沒有 CSS**；
    repo 內唯一能測寬度的 `tests/test_app_playwright.py` 整檔 `importorskip`、
    而且只跑 Tab1、還需要一個真的跑起來的 app（本頁尚未接進 `app.py`）。
    完整說明寫在被測檔的模組 docstring「四格狀態列會不會塌」那一段。
    ⛔ **本條驗的是「有四格、抬頭沒被改掉」，不是「四格排得下」。**

    ⚠️ 前三個抬頭**逐字**取自 `docs/wireframes/policy-split-wireframe.html` 的 3 欄狀態列；
    第四個是決定 ② 新增的。這裡對**線框檔**查證前三個，第四個對**客戶原話**的字面。
    """
    assert STATUS_COLS == 4, (
        f"`STATUS_COLS` 是 {STATUS_COLS} —— 客戶 2026-09-07 決定 ② 明示「變四格」。"
        "改回 3 等於把那個決定撤銷掉，那要回去問客戶，不是實作細節。")
    _body = _policy_body()
    for _lbl in (STATUS_BOOK_LABEL, STATUS_POLICY_LABEL,
                 STATUS_LOADED_AT_LABEL, STATUS_INVESTED_LABEL):
        assert _lbl in _body, (
            f"狀態列少了「{_lbl}」這一格。\n{_body}")
    # 前三格對線框查證（第四格線框上沒有，它是決定 ② 新增的 —— 不去線框裡找它）。
    _src = _POLICY_WIREFRAME.read_text(encoding="utf-8")
    for _lbl in (STATUS_BOOK_LABEL, STATUS_POLICY_LABEL, STATUS_LOADED_AT_LABEL):
        assert _lbl in _src, (
            f"「{_lbl}」在客戶拍板的線框裡找不到 —— 這一格的抬頭被改成自己想的字了。")
    assert STATUS_INVESTED_LABEL not in _src, (
        f"「{STATUS_INVESTED_LABEL}」竟然在線框裡 —— 那它就不是決定 ② 新增的，"
        "本條與被測檔的註解都要重寫（**這種紅燈是提醒，不是責備**）。")


def test_the_status_bar_never_prints_a_number_it_does_not_know():
    """⭐ **§1：不知道就寫 `—` ＋ 灰字，不准寫 0。**

    測試 fixture 的持倉**沒有 `invest_twd`、沒有 `policy_id`**，也沒有帳本設定 ——
    也就是四格**全部都不知道**。這時畫面上：

    - **必須**出現 :data:`UNKNOWN_VALUE`（`—`）；
    - **必須**每一格各帶一句灰字說「缺什麼」；
    - ⛔ **不准**出現 `NT$0` / `0 張` 這種**把「不知道」寫成「是 0」**的東西。

    「0 元」與「不知道投了多少」在畫面上長得一樣，意思差到相反 ——
    而使用者會拿它去決定要不要加碼（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。
    """
    _body = _policy_body()
    assert UNKNOWN_VALUE in _body, (
        f"四格都不知道，畫面上卻找不到 {UNKNOWN_VALUE!r}。\n{_body}")
    assert NOT_READY_MARK in _body, (
        f"狀態列有格子不知道，卻沒有任何灰字說缺什麼。\n{_body}")
    for _fake in ("NT$0", "0 張", "NT$ 0"):
        assert _fake not in _body, (
            f"畫面上出現了 {_fake!r} —— 那是把「不知道」寫成「是 0」。\n{_body}")


def test_the_total_invested_says_what_it_left_out():
    """⭐ **總投入只加「已載入」的，而且必須說出來。**

    一個**安靜少算**的總投入，比沒有總投入更危險：畫面上看不出少了誰。
    本條驗那句範圍說明真的在畫面上，而且提到 :data:`STATUS_INVESTED_LABEL`
    （吃常數，不抄字面 —— 抬頭改字時本條會跟著對，而不是跟著錯）。
    """
    _body = _policy_body()
    assert STATUS_INVESTED_LABEL in _body and "已載入" in _body, (
        "畫面上沒有說「總投入只加已載入的那幾檔」—— "
        "少算是看不見的，所以它必須被說出來。\n" + _body)


def test_the_policy_roster_is_on_screen_and_not_an_empty_frame():
    """⭐ **決定 ①：保單一覽是一張全寬表，不是一張 1/3 摘要卡。**

    ⚠️ 本條驗的是**表真的被畫出來**（有持倉時），以及**它不是空框**
    （鐵則 04：無資料不畫空表格外框 —— 由 `wide_table()` 的空分支保證）。
    ⛔ 不驗欄位內容 —— 欄位由
    :func:`test_the_policy_columns_are_the_wireframe_header_verbatim` 對線框查證。
    """
    _parts = _segments(_stream("loaded")).get(BLOCK_POLICY, [])
    # ⚠️ **不寫死 AppTest 的元素類別名**（`Dataframe` / `ArrowDataFrame` / … 版本間會變）：
    #    改成「這一塊裡出現了一個**不是文字類**的元素」。狀態列與 caption 全是
    #    `[Markdown]` / `[Caption]`，所以**只有那張表**能滿足這一條。
    # ⛔ 這不是把斷言放寬 —— 寫死類別名的版本會在 streamlit 升版時**靜默轉綠或轉紅**，
    #    而兩種都不是我們要驗的事。
    _TEXTY = ("[Markdown]", "[Caption]", "[Text]", "[Header]", "[Subheader]",
              "[Title]", "[Code]", "[Info]", "[Warning]", "[Error]", "[Success]")
    _non_text = [_p for _p in _parts if not _p.startswith(_TEXTY)]
    assert _non_text, (
        "保單一覽那張表沒有被畫出來 —— 決定 ① 要的是全寬表，不是一張摘要卡。\n"
        "（這一塊裡找不到任何非文字元素；若 streamlit 改了元素命名，"
        "請看下面這份實際串流再決定怎麼改。）\n" + _text(_parts))
    # 有持倉時**不得**走空狀態（那代表 `_policy_rows()` 空掉了）。
    assert "保單一覽目前沒有可列的標的" not in _text(_parts), (
        "有持倉，保單一覽卻走了空狀態 —— `_policy_rows()` 的來源接錯了。\n"
        + _text(_parts))


@pytest.mark.parametrize(
    "unit", [BLOCK_CONCENTRATION, BLOCK_MACRO_LINK],
    ids=["concentration", "macro_link"])
def test_a_delegated_block_says_what_is_missing_instead_of_going_blank(unit: str):
    """⭐ **決定 ③ 的三塊：資料不足時要誠實灰態，不准是一個「有標題、底下全空」的區塊。**

    ## 這條擋的是一種**看起來沒事**的退化

    被委派的五支在資料不足時的行為**各不相同，而且沒有一支合鐵則 03／04**：
    兩支直接 `return`（畫面全空）、一支走 `st.info`（藍框）、一支走沒有 ⬜ 的灰字。
    本頁因此在委派**之前**先把前提問完；本條驗那道前提檢查真的在。

    ⛔ **拿掉本頁的前提檢查 → 這三塊會變成「標題底下什麼都沒有」，
       而現有的其他守衛一條都不會紅**（順序守衛只看標題、灰態守衛只看
       `_grey_units()`，而這三塊不在裡面）。**本條是唯一在看它的。**

    ⚠️ **這三塊的灰不帶** :data:`_PENDING_NOTE` —— 它們不是「還沒接」，
    是「**接上了，但你的資料還不夠**」。兩種灰的下一步不同，所以文案不共用；
    本條把「不共用」也釘成斷言。
    """
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), (
        f"單位「{unit}」有標題、底下什麼都沒有 —— 那是鐵則 04 明禁的冗餘占位。"
        "被委派的那幾支在資料不足時會直接 `return`，所以前提要由本頁先問。")
    assert NOT_READY_MARK in _body, (
        f"單位「{unit}」資料不足，卻沒有灰態記號 {NOT_READY_MARK!r}。\n{_body}")
    assert _PENDING_NOTE not in _body, (
        f"單位「{unit}」用了「{_PENDING_NOTE}」這句 —— 它**已經接上了**，"
        "缺的是使用者的資料。用「還沒接上」會讓使用者去等一個不會來的版本。\n" + _body)


def test_the_dividend_calendar_is_gated_and_defaults_to_off():
    """⭐ **決定 ④：Checkbox Gate，預設不載入。**

    三件事一起驗（缺一都會讓那個決定失效）：

    1. **勾選框在畫面上**，字面吃 :data:`DIVCAL_GATE_LABEL`（SSOT，不抄）；
    2. **預設沒勾** —— ⛔「不得預設載入」是客戶逐字的紅線；
    3. **灰態說得出「為什麼預設不載入」與「勾哪裡會載入」**（客戶逐字要求）。

    ⚠️ 第 3 點的「為什麼」驗的是**成本**這個語意（`約五秒`／`每次互動`），
    不是驗某一句固定文案 —— 文案可以改，**理由不能消失**。
    """
    _seg = _segments(_stream("loaded"))
    _parts = _seg.get(BLOCK_DIVIDEND_CAL, [])
    _body = "\n".join(_parts)
    assert any(DIVCAL_GATE_LABEL in _p for _p in _parts), (
        f"配息月曆那一塊找不到勾選框「{DIVCAL_GATE_LABEL}」。\n{_body}")
    assert NOT_READY_MARK in _body, (
        f"配息月曆預設應該是灰的（不得預設載入）。\n{_body}")
    assert "約五秒" in _body, (
        "灰態沒有說**為什麼**預設不載入（成本）—— 客戶逐字要求要寫出來。\n" + _body)
    assert "每次互動" in _body, (
        "灰態沒有說「這一頁每次互動都會整頁重跑」—— 少了它，"
        "使用者看不出為什麼一個算得出來的東西要他自己按。\n" + _body)
    assert f"（請先到：上方「{DIVCAL_GATE_LABEL}」）" in _body, (
        "灰態沒有指出**勾哪裡**會載入 —— 客戶逐字要求要寫出來。\n" + _body)


def test_ticking_the_dividend_gate_actually_changes_the_block():
    """⭐ **勾了要真的算 —— 而且算不出來時要說實話。**

    ## 這條為什麼不是多餘的

    上一條驗「預設不載入」。**只有上一條的話，一個永遠不做事的勾選框也會全綠** ——
    那正是 `CLAUDE.md` 反覆記載的「空掃綠燈」。本條實跑：勾下去、重跑一次，
    **那一塊的內容必須變**。

    ⚠️ **測試 fixture 的持倉沒有 `dividends`**，所以勾下去之後正確的結果是
    「已載入的標的都還沒有配息紀錄」——**不是**一張月曆。
    本條驗的就是那句實話：**算不出來時說算不出來，不是畫一個空月曆或 0 筆**
    （「本月 0 筆」讀起來是「這個月沒配息」，那是造假）。
    """
    _at = _app(FAKE_HOLDINGS_PRICED)
    _before = "\n".join(_segments(_flat(_at.main)).get(BLOCK_DIVIDEND_CAL, []))
    _boxes = [_c for _c in _at.checkbox if DIVCAL_GATE_LABEL in str(_c.label)]
    assert _boxes, f"找不到那個勾選框「{DIVCAL_GATE_LABEL}」。"
    _boxes[0].check()
    _rerun(_at)
    assert not _at.exception, (
        "勾下去之後整頁炸了：\n"
        + "\n".join(str(_e.value) for _e in _at.exception))
    _after = "\n".join(_segments(_flat(_at.main)).get(BLOCK_DIVIDEND_CAL, []))
    assert _after != _before, (
        "勾了之後那一塊一個字都沒變 —— 這個勾選框沒有接到任何東西。\n"
        f"之前：\n{_before}\n之後：\n{_after}")
    assert "配息紀錄" in _after, (
        "fixture 的持倉沒有配息史，勾下去之後應該誠實說「還沒有配息紀錄」，"
        "而不是畫一張空月曆或宣稱「本月 0 筆」。\n" + _after)
    for _fake in ("本月推估除息 0 檔", "本月 0 筆"):
        assert _fake not in _after, (
            f"畫面上出現 {_fake!r} —— 那讀起來是「這個月沒配息」，"
            "而事實是「沒有配息史可以推」。\n" + _after)


def test_the_two_perf_cards_are_not_both_brought_over():
    """⭐ **決定 ③「組合績效只留一份」—— 兩張同名卡不准同時出現在新 ④。**

    舊 ④ 同頁有兩張**標籤逐字相同**的績效卡（年化報酬／年化波動 σ／最大回撤）。
    本條從**被測檔的原始碼**驗：只 import 了其中一支，另一支連名字都沒有。

    ⚠️ 與 :func:`test_the_page_never_delegates_to_the_write_blacklist` **不重複**：
    那條看 `import`，本條連**字面提及**都看（有人可能用 `getattr` 或字串繞過 import）。
    ⛔ **本條只擋「本頁把重複帶進來」**，不處置舊 ④ 那兩張卡的去留 ——
    那是客戶 gate，舊 ④ 已具名回報總管。
    """
    # ⚠️ **要先把黑名單那一格自己排掉，否則本條會被它自己打紅**（本輪實測撞到）：
    #    `DELEGATION_BLACKLIST` 的值裡**本來就有**這個符號名的字串字面值 ——
    #    那正是「具名擋住它」的做法，不是「接它」。
    #    ⛔ 排除法用**節點身分**（`id()`），不是用字串內容比對 ——
    #       用內容比對的話，任何地方只要寫出同一個字串都會被一起放行。
    _tree_ = _tree()
    _blacklist_ids: set[int] = set()
    for _n in _tree_.body:
        _tgt = (_n.targets[0] if isinstance(_n, ast.Assign)
                else getattr(_n, "target", None) if isinstance(_n, ast.AnnAssign) else None)
        if isinstance(_tgt, ast.Name) and _tgt.id == "DELEGATION_BLACKLIST":
            _blacklist_ids = {id(_c) for _c in ast.walk(_n) if isinstance(_c, ast.Constant)}
    assert _blacklist_ids, (
        "被測檔找不到 `DELEGATION_BLACKLIST` —— 那是「具名擋住那兩支」的 SSOT，"
        "它不見了代表擋它的機制被拿掉了。")
    _bad = [_n.value[:60] for _n in _live_strings(_tree_)
            if "render_portfolio_tracking" in _n.value and id(_n) not in _blacklist_ids]
    assert not _bad, (
        "被測檔的**活字串**裡出現了 `render_portfolio_tracking`（且不在黑名單宣告內）—— "
        "那是繞過 import 守衛去接它的形狀：\n  " + "\n  ".join(_bad))
    _calls = [ast.unparse(_n.func) for _n in ast.walk(_tree())
              if isinstance(_n, ast.Call)]
    assert not [_c for _c in _calls if "portfolio_tracking" in _c], (
        "被測檔呼叫了 `render_portfolio_tracking` —— 決定 ③ 明示只留一份，"
        "而留的是不寫入客戶 Google Sheet 的 `render_portfolio_performance`。")


def test_the_dividend_gate_is_a_real_gate_and_cannot_be_short_circuited():
    """⭐ **那個勾選框必須真的是閘門 —— 而且不得被布林字面值短路。**

    ## 這條為什麼要存在（⑤ 那一組今天實測出來的洞，本檔照抄它的教訓）

    ⑤ 的第一版 gate 守衛只問「**這個函式裡有沒有 `st.checkbox` 呼叫**」——
    於是 ``if False and st.checkbox(...):`` **照樣綠**：勾選框在、閘門形同虛設。
    「有一個 widget」與「那個 widget 真的擋住了東西」是兩件事。

    ## 本條釘住的四件事（缺一都能讓 gate 變成裝飾）

    1. :func:`~ui.views.page_04_portfolio._render_dividend_calendar_card` 裡
       **恰好一個** `st.checkbox` 呼叫，而且它的回傳值**被指派給一個變數**
       （沒有指派 ⇒ 那個值不可能被拿來當條件）。
    2. 函式裡有一個 `if`，其 test **就是** ``not <那個變數>``，
       而且那個分支**以 `return` 結束** —— 也就是「沒勾就到此為止」。
    3. ⭐ **那個 test 裡不得出現任何布林字面值**（`True` / `False`）。
       這一條擋的就是 ``if False and _flag:`` ／ ``if _flag or True:`` 這一族。
    4. 昂貴的那一段（:func:`~ui.views.page_04_portfolio._render_dividend_calendar_body`）
       **只在那個 early-return 之後**被呼叫，且**不在**那個 early-return 分支裡。

    ⚠️ **為什麼驗「沒勾就 return」而不是「有勾才呼叫」**：本頁採的是 ⑤ 的
    early-return 形狀（`ui/views/page_05_settings.py` 的 `NAV_GATE_LABEL` gate），
    那是 repo 內已經跑過 CI 的合規樣板。**驗實際的形狀，不是驗我希望的形狀。**

    ⛔ **本條看不到什麼（照實寫）**：它是**語法**檢查。
    `_render_dividend_calendar_body()` 內部若自己又去做了昂貴的事而不管旗標，
    本條看不到；`st.checkbox` 被 alias 成別的名字也看不到。
    **「不勾就真的沒有執行」那一半由 :func:`test_ticking_the_dividend_gate_actually_changes_the_block`
    在 AppTest 裡實跑**，兩條互補、都不可省。
    """
    _fn = next((_n for _n in ast.walk(_tree())
                if isinstance(_n, ast.FunctionDef)
                and _n.name == "_render_dividend_calendar_card"), None)
    assert _fn is not None, (
        "找不到 `_render_dividend_calendar_card()` —— 本條所有斷言都掛在它身上，"
        "找不到它就等於這道 gate 的守衛靜默失效。")

    # (1) 恰好一個 checkbox，且回傳值有被接住
    _cb_assigns = [_n for _n in ast.walk(_fn)
                   if isinstance(_n, ast.Assign) and isinstance(_n.value, ast.Call)
                   and getattr(_n.value.func, "attr", None) == "checkbox"]
    _cb_calls = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.Call)
                 and getattr(_n.func, "attr", None) == "checkbox"]
    assert len(_cb_calls) == 1, (
        f"`_render_dividend_calendar_card()` 裡有 {len(_cb_calls)} 個 `checkbox` 呼叫，"
        "預期恰好 1 個。多一個 gate ＝ 多一個沒人在守的閘門。")
    assert len(_cb_assigns) == 1 and isinstance(_cb_assigns[0].targets[0], ast.Name), (
        "那個 `st.checkbox(...)` 的回傳值沒有被指派給變數 —— "
        "沒接住的值不可能拿來當條件，那個勾選框就只是裝飾。")
    _flag = _cb_assigns[0].targets[0].id

    # (2)(3) `if not <flag>:` 且以 return 收尾，且 test 裡沒有布林字面值
    _gates = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.If)
              and isinstance(_n.test, ast.UnaryOp) and isinstance(_n.test.op, ast.Not)
              and isinstance(_n.test.operand, ast.Name)
              and _n.test.operand.id == _flag]
    assert len(_gates) == 1, (
        f"找不到（或不只一個）`if not {_flag}:` 的 early-return 閘門 —— 實際 {len(_gates)} 個。\n"
        "⛔ 這正是 ⑤ 那一組實測過的洞：勾選框在、閘門不在，畫面看起來一模一樣。")
    _gate = _gates[0]
    assert any(isinstance(_s, ast.Return) for _s in _gate.body), (
        f"`if not {_flag}:` 那個分支沒有 `return` —— 沒勾的時候會繼續往下跑，等於沒有閘門。")
    _bools = [_n for _n in ast.walk(_gate.test)
              if isinstance(_n, ast.Constant) and isinstance(_n.value, bool)]
    assert not _bools, (
        f"閘門條件裡出現布林字面值 {[_b.value for _b in _bools]} —— "
        "`if False and _flag:` / `if _flag or True:` 這一族會讓閘門恆真或恆假，"
        "而畫面上**看不出任何差別**（⑤ 2026-09-07 實測：這種寫法在只問「有沒有 checkbox」"
        "的守衛下照樣全綠）。")

    # (4) 昂貴的那一段只在閘門之後、且不在閘門分支內
    _body_calls = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.Call)
                   and getattr(_n.func, "id", None) == "_render_dividend_calendar_body"]
    assert len(_body_calls) == 1, (
        f"`_render_dividend_calendar_body()` 在這個函式裡被呼叫 {len(_body_calls)} 次，預期 1 次。")
    _in_gate_branch = [_n for _s in _gate.body for _n in ast.walk(_s)
                       if isinstance(_n, ast.Call)
                       and getattr(_n.func, "id", None) == "_render_dividend_calendar_body"]
    assert not _in_gate_branch, (
        "昂貴的那一段長在「沒勾」的分支裡 —— 那是把閘門接反了（不勾才算）。")
    assert _body_calls[0].lineno > _gate.lineno, (
        "昂貴的那一段在閘門**之前**就被呼叫了 —— 客戶逐字的紅線是「⛔ 不得預設載入」。")


def test_the_checkbox_assertion_is_still_an_exact_equality():
    """⭐ **那條 checkbox 斷言必須維持 `==` 精確相等，不得被改成「包含即可」。**

    ## 這條為什麼要存在（它守的是**守衛本身**）

    2026-09-07 本批把整頁 checkbox 斷言從
    ``== [_LABEL_SATELLITE_ONLY]`` 改成 ``== _expected_checkbox_labels()``——
    那是**具名放行**（多一個就要有人來改清單），不是放寬。
    **但這兩者只差一個運算子**：把 `==` 換成 ``set(...) <= set(...)`` 或 `in`，
    畫面上、清單上、PR 描述上**看不出任何差別**，而守衛從此對「多一個 checkbox」失明。

    ⚠️ **這一條是本地唯一能證明那件事的方法。** 真正的行為突變（在頁面上塞第三個
    checkbox，看那條斷言會不會紅）**需要渲染**，而本批的環境沒有 streamlit ——
    所以改成從**測試自己的原始碼**驗運算子。**兩者不等價，這一點照實寫在這裡。**

    ## 釘住三件事

    1. 那個 assert 的 test 是一個 `ast.Compare`；
    2. 運算子**恰好一個，而且是 `ast.Eq`**（不是 `In` / `LtE` / `NotEq`）；
    3. 右邊**就是** ``_expected_checkbox_labels()`` 的呼叫
       （不是就地拼一份，那會繞過 :data:`_ALLOWED_EXTRA_CHECKBOXES` 的關卡）。

    ⛔ **本條看不到什麼**：把 `_expected_checkbox_labels()` 的**實作**改鬆
    （例如回傳 `[]`）它看不到 —— 那一半由
    :func:`test_the_extra_checkbox_allowlist_is_exact_and_named` 守。
    """
    _self = pathlib.Path(__file__).read_text(encoding="utf-8")
    _fn = next((_n for _n in ast.walk(ast.parse(_self))
                if isinstance(_n, ast.FunctionDef)
                and _n.name == "test_the_three_fields_and_the_submit_verb_come_from_the_wireframe"), None)
    assert _fn is not None, (
        "找不到那條線框守衛 —— 它被改名或刪掉了，而本條所有斷言都掛在它身上。")
    _cands = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.Assert)
              and "_at.checkbox" in ast.unparse(_n.test)]
    assert len(_cands) == 1, (
        f"那條守衛裡提到 `_at.checkbox` 的 assert 有 {len(_cands)} 條，預期恰好 1 條。")
    _test = _cands[0].test
    assert isinstance(_test, ast.Compare), (
        f"checkbox 斷言不再是一個比較式，而是 {type(_test).__name__} —— "
        f"實際：{ast.unparse(_test)[:120]}")
    assert len(_test.ops) == 1 and isinstance(_test.ops[0], ast.Eq), (
        "checkbox 斷言的運算子不是 `==` —— "
        f"實際：{ast.unparse(_test)[:120]}\n"
        "⛔ `in` / `<=` / `issubset` 這一族會讓「多一個沒列名的 checkbox」**不再轉紅**，"
        "那一刻起這條守衛就只是裝飾品。")
    _right = _test.comparators[0]
    assert (isinstance(_right, ast.Call)
            and getattr(_right.func, "id", None) == "_expected_checkbox_labels"), (
        "checkbox 斷言的右邊不是 `_expected_checkbox_labels()` —— "
        f"實際：{ast.unparse(_right)[:120]}\n"
        "⛔ 就地拼一份預期清單會繞過 `_ALLOWED_EXTRA_CHECKBOXES` 那道關卡。")
