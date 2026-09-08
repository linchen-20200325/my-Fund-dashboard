"""② 持倉體檢 —— 五分頁動線重構的第二頁（全新撰寫，非舊 `ui/tab_fund_grp_health.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。
客戶方針（2026-09-05）：本頁**只做骨架 + 灰態**；三張卡與逐檔表的真內容**分批填**。

⚠️ **2026-09-06 本批（接真資料）改了哪些、以及哪些刻意沒改**
------------------------------------------------------------
接上真資料的三塊：**吃本金警示**、**影子基金重疊**、**逐檔體檢表**。
維持灰態的兩塊，**理由各自具名寫在該處，不是「還沒排到」**：

- **組合健康總分** —— 線框寫「五桶評等加權」，而本站的「五桶」是**總經**概念
  （`shared/macro_buckets.py`），**沒有逐檔基金版本**；逐檔真正存在的是
  `services/health/grade.py::compute_4d_health` 的 4D/5D Grade（A～F）。
  該用哪一個屬**業務規格**，已送客戶、尚未答覆 → 不自行拍板（§-1.5 v3 `03`-2 ②）。
  **逐檔體檢表的「五桶評等」欄同一個原因，整欄誠實留白。**
- **衛星連續落後** —— 語意相符的實作是 `ui/components/mk_dashboard.py::tag_benchmark_lag`，
  但 (a) 客戶已裁決波段觀測站的搬遷是**本頁上線之後的獨立批次**、
  (b) 它要的基準序列來自 L1 `repositories/**`（本檔禁 import）。
  **`services/**` 底下沒有同語意替代品**（`benchmark_compare.excess_return` 是「近 1 年」
  超額報酬，不是「連兩季」）。

⛔ **本批最大的一個坑，寫在最前面**：`ui/components/mk_dashboard.py` 有一個叫
   **`Principal_Erosion`（直譯就是「吃本金」）** 的訊號，**它不是吃本金**。
   它自己的 docstring 逐字寫著「v19.402 正名：本訊號實為『淨值連續下跌動能』，
   **非配息覆蓋/吃本金** … **勿混用**」。真正的吃本金 SSOT 是
   `services/health/dividend.py::check_eating_principal_1y_mk`（含息總報酬 vs 年化配息率）。
   詳見 :func:`_eating_verdict` 的長註 —— **那一段是本批最重要的一段，改這裡之前先讀它。**

整頁骨架 —— 逐字取自已核准線框 `docs/wireframes/ia-wireframe.html` 的 **Tab 02**
------------------------------------------------------------------------------

===== ================================== ==========================================
順序   區塊                                版面
===== ================================== ==========================================
1      Form — 診斷條件（σ／回看窗／只看衛星）  `applied_form`，按「套用」才算
1.5    🧾 ① 結論（2026-09-08 補，見下）        **全寬**，兩句話
2      組合健康總分                          **全寬**
3      吃本金警示／衛星連續落後／影子基金重疊    3 欄自適應網格
4      逐檔體檢表（9 欄）                    **全寬 + 橫向捲動**
–      尚未設定持倉                          空狀態三要素（取代 2～4）
===== ================================== ==========================================

⭐ **2026-09-08 新增「🧾 ① 結論」層 —— 這一列不在線框的四塊裡，理由寫在這裡。**
   客戶原話（同日，兩句要**合起來**讀）：
   「新的 UI 設計我不滿意，少了很多資訊，**無法判斷這檔基金好不好，配息金額**，
     搭配組合以及標的是否需要調整，這些都沒有」
   ＋「我覺得**舊 UI 資訊太多**，才希望總管 AI 重新設計，去重複然後讓新手也能看得懂」
   ⇒ **他要的不是更多欄位，是看一眼就知道「所以呢」。**
   盤點結論：本頁的**數字都在**（9 欄有 8 欄是真資料），**缺的是有人下判定**。

   ⛔ **因此這一層只准放「一句話」等級的結論，不准長成第二張表。**
   逐檔體檢表**維持 9 欄**（`HEALTH_TABLE_COLUMNS`），這一批**一欄都沒有加** ——
   要加的是一句結論，不是第 10 欄。想在這裡加卡片／表格／把舊 ② 的欄位搬回來的人，
   請先讀客戶的第二句話：**那正是他當初要求重新設計的理由**，把密度搬回來等於推翻它。

   結構照 ① `ui/views/page_01_macro.py` 的既有四層閱讀順序
   （`### 🧾 ① 結論` → 卡片 → `### 🧾 ② 依據` → 詳細區）—— **不另發明第二套**。
   本層用 `###`（H3），比下面四個 `####` 區塊大一級，讀者一眼看得出誰是結論、誰是依據。

線框同時釘死了本頁的**職責邊界**，這一條比版面更要緊：

> 回答一個問題：**我手上這些，哪一檔出問題了？**
> **只診斷、不決策** —— 要換什麼、怎麼配，在 ④。

⛔ **因此本頁不放：換股建議、再平衡試算、任何「你應該買/賣什麼」的輸出。**
   線框「這裡不放什麼」逐字寫著「換股建議與再平衡試算 → 04（那是決策，不是診斷）」。
   下一批填內容時，看到 `services/switch_advisor.py` / `services/rotation.py`
   這類**建議**類服務要停手 —— 它們的落點是 ④，不是這裡。

~~⛔ **不修補舊 ②，也不委派它。** 舊實作（`ui/tab_fund_grp_health.py` 1,441 行~~
   ~~＋ `ui/helpers/fund_grp_health/` 一整包）依方針第 3 條會在五頁驗收完成後**整批拔除**。~~
   ~~本檔**一行都不 import 它們** —— 每多一條委派，那一刻就多一處會斷頭。~~
   ~~⚠️ 這一點是 ① 的既有教訓：`ui/views/page_01_macro.py` 留了一條對~~
   ~~`ui/tab1_macro_midcycle.py` 的委派，它自己的 docstring 就登記著~~
   ~~「有效期到舊 tab 整批拔除為止」。**本檔一條都沒有。**~~

⚠️ **2026-09-06 路線 (A)：上段已被客戶推翻。有意識的政策變更，不是漏刪。**
   **決策者：客戶**。日期 **2026-09-06**。原文加刪除線保留，**不刪除**。

   客戶原話：「新頁只做**版面呈現與互動排版**，寫入邏輯**原封不動呼叫既有舊模組**，
   資料路徑不動，**Google Sheet 零風險**。」→ **版面留新版的，功能接回既有 public 入口。**

   **兩邊理由並陳（舊條的理由仍然成立，只是被權衡掉，不是「當初寫錯」）**：
   - **舊條為什麼是對的** —— 「每多一條委派，那一刻就多一處會斷頭」今天依然成立；
     舊實作確實排定要整批拔除。這個顧慮**沒有消失**，它被轉成了**登記**
     （見 :data:`DELEGATED_ENTRIES` 的「舊 tab 拔除時要回來改這裡」註）。
   - **新條為什麼勝出** —— 從零重寫那些子區塊要重新實作一整包計算與取數，
     那既違反客戶「資料路徑不動」的要求，也把 Google Sheet 的風險面重新打開一次；
     **呼叫既有 public 入口，寫入面完全不變**（本批實測：委派後仍是零寫入）。

⛔ **委派黑名單 —— 這兩支不准接，理由不是風格，是它們會寫客戶的 Google Sheet：**
   - `ui/helpers/fund_grp_health/switch_advisor_section.py::render_switch_advisor_section`
   - 同檔 `::render_portfolio_tracking`
   **打開就寫一列進客戶 Google Sheet，沒有按鈕、沒有勾選**（該區塊 caption 自陳
   「每次開啟本區自動存一筆」）。它們現在住在 ④，另有一組正在修。
   ⚠️ **它們的程式碼就放在 `ui/helpers/fund_grp_health/` 這個「舊 ② 的資料夾」裡** ——
   **照資料夾委派的人會把它們搬回 ②**。機器規則見
   `tests/test_wf02_health_skeleton.py::test_the_page_never_delegates_to_the_write_blacklist`。

⛔ **波段觀測站（`ui/components/mk_dashboard.py`）本批完全不碰。**
   線框「從哪裡搬來」把它列進 ②，但客戶 2026-09-05 裁決：**搬，排在本頁上線之後的獨立批次**。
   本檔沒有任何對它的 import 或呼叫。

~~⚠️ **本頁本批尚未接進 `app.py`。** `app.py` 的 `with tab_health:` 仍呼叫舊的~~
   ~~`render_fund_grp_health_tab()`，客戶明令「舊 ② 這批不動、不接線、不下架」。~~
   ~~接線是下一批的事 —— 骨架先上線、CI 綠、再分批填內容。~~

⚠️ **2026-09-07 事實更正：上段已過期。有意識的更正，不是漏刪**
   （決策者：**AI 總管**，依獨立稽核指出）。**舊表述在寫下的當天是對的** ——
   那一批確實沒有接線；**被推翻的是它的前提**：接線那一批已經做完。
   ~~**實測**：`app.py` 的 `with tab_health:` 現在呼叫的是本檔的~~
   ~~`render_holdings_health()`。~~

⛔ **2026-09-07 同日再更正（第二次）：上面那句只活了幾分鐘，#814 之後為假。**
   **有意識的更正，不是漏刪**（日期 **2026-09-07** · 決策者：**AI 總管**，依獨立稽核實測）。
   **實測（`origin/main` `c6b4d1b`，本分支已 merge）—— 雙軌並行**：

   ===================== ==========================================
   `app.py` 的分頁槽        呼叫誰
   ===================== ==========================================
   `tab_health`（②）      **`render_fund_grp_health_tab()`（舊 ②）**
   `tab_preview_health`   **`render_holdings_health()`（本檔）**
   ===================== ==========================================

   ⇒ **本檔掛的是「[新] 並行預覽」那一格，不是 ② 那一格**；`app.py` 現在有
   **七**個分頁槽，而且**同時 import 舊 ② 與本檔**。客戶 2026-09-07 原則：
   **舊 Tab 原位保留、新 View 並行掛新 Tab**，直到客戶親自驗收才換。
   機器規則見 `tests/test_wf02_health_golive.py::test_app_mounts_the_new_health_view`
   —— ⚠️ **它現在斷言的正是「`tab_health` 必須是舊 ②」**，與上面那句劃掉的話**正面相反**。

   ⚠️ **這一輪要記的教訓比事實本身重要**：上一版寫下那句話時它是真的，
   **#814 在本 PR 交件後幾分鐘合併，把它的前提整個翻面** ——
   而**本檔 12 條守衛全綠、CI 也全綠**，因為那句話是**散文，不是斷言**。
   **綠燈不保證文件為真**；這正是 `DROPPED_WITH_REASON` 那張表一路在犯的同一個病。

Form 為什麼是本批唯一「真的做完」的一塊
--------------------------------------
線框在 Tab 02 的 Form 區塊就地點名了舊 ② 的缺陷：**「目前每拉一格全頁重繪，本次一併修掉」**。
這**不是新增需求，是四大鐵律之一**（鐵則 02），所以它必須由**建構**就解掉，
不能留給下一批 —— 一旦骨架先用裸 widget 寫成，下一批要改就是回頭重做。

**解法的結構（這一段是本檔最重要的設計決定）**：
widget 的**當下值**與**已套用值**是兩個不同的東西，本檔只讓下游讀後者
（:data:`_SK_APPLIED`）。使用者拖滑桿時 Streamlit 仍會 rerun（那是 `st.form` 擋不住的），
但 rerun 讀到的 `_SK_APPLIED` **沒有變** → 下游的取數與計算不會被觸發。
**只包 form 而不分離「已套用值」，省下的只有 widget 互動的 rerun，沒有省下重運算**
（`ui/helpers/ia/gated_form.py` 的模組 docstring 把這個陷阱寫得很清楚）。

⚠️ **`if _gate:` 一定要寫在 `with` 之外** —— 送出鈕是在 `yield` 之後才建立的，
   區塊內判斷恆為 `False`。

持股從哪裡來
------------
**一律從組合帶入**（客戶 2026-09-05 裁決：**不保留手動輸入基金代號**）。
來源是 `st.session_state["portfolio_funds"]` —— 由 ④ 資產配置／雲端讀回
（`ui/helpers/cloud_io.py`）寫入的既有 session 契約。
**讀 session 不是資料層呼叫**，不違反「資料只走 `services/**`」。

⚠️ **2026-09-06 起本檔有 `services/**` 呼叫了**（骨架批那句「本批沒有任何 `services/**`
   呼叫」已不再成立，據實更新）。實際接上的四個入口，**全部是 public、全部零 I/O**：

   - `services.health.dividend.check_eating_principal_1y_mk` —— 吃本金（含息 vs 配息率）
   - `services.portfolio_service.calc_holdings_overlap` —— 影子基金相似度（v19.176 SSOT WRITER）
   - `services.fund_total_return.compute_1y_total_return` —— 近 1 年含息報酬 + 來源標籤
   - `services.fund_row.nav_freshness_label` —— 淨值日期 → 新鮮度標籤

   **不 import** `repositories/**`、`infra/**`、`requests`、`yfinance`、`gspread`
   （`tests/test_wf02_health_skeleton.py::test_the_page_never_reaches_into_the_data_layer` 守）。
   取不到的東西**一律做成灰態並誠實說明**，**不反向要求修改底層**。
   ⚠️ 上面那串入口是本組**實測接起來跑過的**，**不是**「這些就夠了」的宣稱 ——
   「五桶評等」就是一個**接不到**的例子，它維持誠實留白。

三態與空狀態：兩種灰的理由不同，文案必須分開
------------------------------------------
- **沒有持倉** → 線框指定的空狀態三要素，指路到 ④（使用者**照著做真的能解決**）。
- **有持倉、但這一塊的內容還沒填** → 「本頁分批上線」的灰態。
  ⚠️ 這兩句混成一句，會讓使用者以為「去 ④ 加了基金這裡就會出現」—— 不會。
  同樣的分岔在 ① 也做過一次（`page_01_macro.py::_detail_pending`）。

四大鐵律的落點（本檔不自己實作任何一條，一律走既有共用元件）
------------------------------------------------------------
- **鐵則 01 三欄網格** → `ui.helpers.ia.render_cards`。**本檔沒有任何 `st.columns` 呼叫**
  —— 自己寫會讓 `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL`（精確 `==` 90）轉紅。
- **鐵則 02 Form 防重繪** → `ui.helpers.ia.applied_form`。**本檔沒有任何 `st.form(` 站點**
  —— 自己寫會讓 `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==` 7）轉紅。
- **鐵則 03 三態顏色** → `ui.helpers.render_state`（經 `ia.state_card` 的 `state=`）。
- **鐵則 04 空狀態三要素** → `ui.helpers.ia.empty_state` ＋ `wide_table` 的空分支。
- **指路一律走 `ui.helpers.story_nav`**，不手抄分頁名
  （`tests/test_wpf_five_tab_wiring.py` 兩條規則會擋）。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from ui.helpers.ia import (
    STATE_BUSINESS,
    STATE_NOT_READY,
    STATE_OK,
    applied_form,
    render_cards,
    wide_table,
)
from ui.helpers.ia.empty_state import empty_state
from ui.helpers.render_state import NOT_READY_MARK, not_ready, safe_section
from ui.helpers.story_nav import render_story_nav, tab_label, where_to_find

# ── session 鍵名（本檔自己的命名空間）────────────────────────────────────────
# ⚠️ 刻意**不**沿用舊 ② 的鍵：舊頁依方針第 3 條仍在磁碟上、**且仍接在 `app.py`**，
#    共用鍵會讓兩套 View 互相覆寫對方的狀態，而 payload 形狀並不相同。
#
#    ⚠️ **這一行的刪除線來回過一次，過程照實留著（2026-09-07，決策者：AI 總管）**：
#    ~~2026-09-07 就地更正：「且仍接在 `app.py`」**後半句已過期**~~
#    ~~（`with tab_health:` 現在呼叫的是本檔）。~~
#    **⛔ 同日 #814 合併後，那句劃掉的話又變回真的，故刪除線撤銷、原句恢復效力。**
#    **劃掉它在當時是對的**：那一刻 `tab_health` 確實掛的是本檔（新 ②）；
#    **被推翻的是它的前提** —— #814 把舊 ② 接回 `tab_health`、新 View 改掛
#    `tab_preview_health`（雙軌並行），於是「舊頁仍接在 `app.py`」重新成立。
#    ⚠️ **不直接把刪除線拿掉了事** —— 留著這條來回的痕跡，
#    下一個人才看得出這句話為什麼曾經被劃掉，以及它是怎麼回來的。
#
#    ⭐ **而且本註的結論在兩種世界下都成立、從頭到尾一字未改** ——
#    兩套 View **現在真的同時掛在 `app.py` 上**（② 舊、⑥ 新），
#    **不共用鍵的理由因此比當初更硬，不是更軟。**
_FORM_KEY: str = "v02_health_filter_form"
#: **已套用**的診斷條件（不是 widget 當下值）。下游只准讀這個 —— 理由見模組 docstring。
_SK_APPLIED: str = "v02_health_applied_filters"

#: 使用者的持股來源。既有 session 契約，由 ④ 資產配置／`ui/helpers/cloud_io.py` 寫入。
#: ⚠️ 這個字串是**別人定義**的鍵名，本檔只讀不寫 —— 不要在這裡「順手改個好名字」。
_SK_PORTFOLIO: str = "portfolio_funds"

# ── 診斷條件的預設值（線框 Tab 02 逐字）──────────────────────────────────
#: 線框：「輪動門檻　σ ±1.0」。
_DEFAULT_SIGMA: float = 1.0
#: 線框：「回看窗　12 個月」。
_DEFAULT_WINDOW_MONTHS: int = 12
#: 線框：「只看衛星　☐」（預設不勾）。
_DEFAULT_SATELLITE_ONLY: bool = False

#: 滑桿範圍。⚠️ 線框只給了預設值 **±1.0**，**沒有給範圍** ——
#: 這裡的 0.5～2.0 是本組挑的，`σ` 在 0 附近沒有鑑別度、超過 2 幾乎不會觸發。
#: **這是實作細節不是業務規格**，若客戶要別的範圍改這兩個常數即可。
_SIGMA_MIN: float = 0.5
_SIGMA_MAX: float = 2.0
_SIGMA_STEP: float = 0.1
_WINDOW_MIN: int = 1
_WINDOW_MAX: int = 36

#: 本金（TWD）—— **核准線框 `docs/wireframes/wireframe-macro-health.html` 的
#: 「Form ②-A　健診輸入（防全頁重繪）」內逐字寫著「本金（TWD）：1,000,000」**
#: （本組 2026-09-06 自行開檔核對，非轉述）。**下列各界值**沿用舊 ②
#: `ui/tab_fund_grp_health.py` 的 `st.number_input`，**不是本組挑的**。
#: ⚠️ **刻意不寫「N 個」** —— 這幾個常數會被增減（`_PRINCIPAL_STEP` 就是 2026-09-07
#: 補進來的），寫死數量等於埋一個下一輪會過期的數字。**權威清單是
#: `tests/test_wf02_health_skeleton.py::_WIREFRAME_PRINCIPAL`，那裡有守衛釘住值。**
#:
#: ⚠️ **它的語意是「假設每檔都投入這個金額」的比較基準，不是使用者的實際持倉金額。**
#: ⛔ **不得**改用 `sum(invest_twd)` 之類推導 —— 那會把「每檔各投入 N」
#: 悄悄換成「每檔各投入全部身家」，畫面上每一個「可申購單位／月配 TWD」都會變，
#: 而使用者**看不出來**（§1）。要改語意請走線框草稿，不要在這裡動常數。
#:
#: ⚠️ **這一欄在 `ia-wireframe.html`（本頁骨架的來源）裡不存在** ——
#: 本組實測該檔 `本金` 僅 2 命中，且**兩處都是「吃本金警示」卡**，不是輸入欄。
#: 依總管 2026-09-06 裁決加回：客戶永久授權第 2 條把「批次輸入框等細節元件」
#: 列為總管自決，且它**有既有規格可對照**（＝修正錯誤，不是改變設計）。
_DEFAULT_PRINCIPAL_TWD: float = 1_000_000.0
_PRINCIPAL_MIN: float = 10_000.0
_PRINCIPAL_MAX: float = 10_000_000.0
_PRINCIPAL_STEP: float = 100_000.0

#: 逐檔體檢表的欄位 —— **線框 Tab 02 逐字**：
#: 「代碼 / 名稱 / 幣別 / 近 1 年 / Sharpe / 最大回撤 / 配息覆蓋 / 五桶評等 / 資料日期」。
#: ⚠️ 定成常數而不是散在下一批的程式碼裡，是為了讓「欄位少了一欄」看得見
#: （`tests/test_wf02_health_skeleton.py` 釘住它是 9 欄且逐字相符）。
#: ⚠️ **下一批填內容時，任一欄取不到 → 那一格走灰態，不得從別的欄位湊一個數字充數**（§1）。
HEALTH_TABLE_COLUMNS: tuple[str, ...] = (
    "代碼", "名稱", "幣別", "近 1 年", "Sharpe",
    "最大回撤", "配息覆蓋", "五桶評等", "資料日期",
)

#: ⛔ **骨架批的共用灰態理由「本頁分批上線…」已於 2026-09-06 刪除，這是有意識的移除、不是漏刪。**
#: 它在骨架批是對的（那時四塊真的都只是還沒排到）。本批之後**只剩兩塊是灰的，而且
#: 它們灰的理由各自不同、也都不是「還沒排到」**——一個是評等定義未定（等客戶），
#: 一個是來源住在下一個批次才會搬的檔案裡。
#: **留著一句「還沒接上」給它們共用，等於用一句含糊的話蓋掉兩個具體、可行動的原因**
#: （而且下一個人會照著它繼續產生新的含糊灰態）。兩個理由因此各自具名如下。
#:
#: 組合健康總分為什麼還是灰的（見 :func:`_render_health_score`）。
_SCORE_PENDING_NOTE: str = (
    "「五桶評等加權」的評等定義未定（本站的「五桶」是總經概念，逐檔評等是另一套 4D Grade），"
    "已送客戶確認，**不先湊一個分數出來**。")

#: 衛星連續落後為什麼還是灰的（見 :func:`_render_alert_cards`）。
_LAG_PENDING_NOTE: str = (
    "「連兩季落後基準」目前只實作在波段觀測站裡，"
    "它的搬遷是客戶指定的**下一個獨立批次**；"
    "本站服務層沒有同語意的替代算法（現有的是「近 1 年」超額報酬，期間對不上）。")


# ══════════════════════════════════════════════════════════════════════════
# 路線 (A) 委派名單 —— 客戶 2026-09-06 拍板「功能接回既有 public 入口」
# ══════════════════════════════════════════════════════════════════════════
#: **第一階段已接回**的舊模組 public 入口，`(module, symbol)`。
#:
#: ⚠️ **這份名單是機器規則的 SSOT**：`tests/test_wf02_health_skeleton.py` 拿它跟
#: 本檔**實際 import 到的符號**做 `==` 比對（**精確集合相等，不是白名單過濾**）。
#: 於是三個方向都會轉紅：**多接一支**、**少接一支**、**接了黑名單那兩支**。
#: ⛔ **改這份常數不等於改守衛** —— 兩邊都要動，這是刻意的摩擦。
#:
#: ⚠️ **舊 tab 整批拔除時要回來改這裡**（這就是被劃掉的舊條文所擔心的那個斷頭點，
#: 現在把它變成一個**看得見、機器守得住的登記**，而不是一句「本檔一條都沒有」）。
#:
#: **為什麼是 `ui.helpers.fund.checkup` 而不是 `ui.helpers.fund_checkup`**：
#: 後者是 v19.204 P2-7 的**向後相容 shim**（整檔只有 `import *` ＋ `dir()` 迴圈），
#: 兩者 re-export 的是**同一個函式物件**，行為完全一致；直接指 canonical 位置，
#: shim 哪天依 `CLAUDE.md` §-1.5.1c `01`-2「用不到即清理」被刪時本檔不會斷。
#: ⚠️ **2026-09-06 第二輪：由 2 支擴為 8 支。`render_fund_grp_health_extras`
#: 刻意「拆開逐支接」，⛔ 不整支接** —— 理由是核准線框把它的子區塊**分派到不同頁**
#: （本組開檔核對逐字，非轉述）：
#:
#:   `docs/wireframes/wireframe-macro-health.html` §04 對照表
#:     「💼 逐檔深度分析（投資試算／TER／持股）… **搬 ③ 基金研究** …
#:       每檔一個 expander ＝ 單一檔基金的細節，依動線原則一律屬 ③」
#:     「⑪ Bollinger 詳圖／⑬ 個股新聞／⑭ 三率穿透 … **搬 ③ 基金研究**」
#:     「📊 健診大表／🩺 體檢 PK／📈 比較圖／**🔁 回測**／⑫ AI 跨檔 … **留 ② 原位**」
#:
#: → **整支接會把 5 個屬 ③ 的子區塊一起搬回 ②，那是違反核准線框。**
#:
#: ⚠️ **「拆得開」是實測結論**：那 10 塊各自是獨立的 module-level 函式、住在
#: `ui/helpers/fund_grp_health/` 的不同子模組，簽名幾乎都是 `(funds)` ——
#: **本檔逐支呼叫它們，沒有改舊模組一個字**（路線 (A)「原封不動」）。
#:
#: ⛔ **但有一個必須講明的代價：從 extras 拆進來的四支全是 `_` 開頭的私有名。**
#: 該套件的 `__init__` 確實把它們全部 re-export（docstring 自陳「re-export 全部子函式」，
#: 且既有 14+ 測試就是這樣取用），但**沒有 `__all__`**。也就是說本檔對它們的依賴
#: **比對 public API 的依賴更脆** —— 舊模組整批拔除時，這幾條是最先斷的。
#: **這一點登記在此，不是藏在 PR 描述裡。**
DELEGATED_ENTRIES: tuple[tuple[str, str], ...] = (
    # ── 原本就接的兩支（public）────────────────────────────────
    ("ui.helpers.fund.checkup", "render_fund_checkup"),
    ("ui.components.mutual_exclusion", "render_mutual_exclusion_section"),
    # ── 🔁 配置回測（public）──────────────────────────────────
    # 線框 §04：「🔁 回測 … 留 ② 原位 … 全部是跨檔比較或組合層結論，正是 ② 的題目」，
    # 同檔另標「哪套配置效益最高（**教學非建議**）」。
    # ⚠️ **本組原先判它屬 ④ 是錯的**，已依線框逐字更正（詳見 DEFERRED_ENTRIES 的說明）。
    ("ui.helpers.fund_grp_health.backtest_section",
     "render_allocation_backtest_section"),
    # ── `render_fund_grp_health_extras` 底下「留 ②」的五塊 ────────
    ("ui.helpers.fund_grp_health.dividend", "_render_dividend_matrix"),
    ("ui.helpers.fund_grp_health.correlation", "_render_correlation_matrix"),
    ("ui.helpers.fund_grp_health.risk", "_render_oversold_badges"),
    ("ui.helpers.fund_grp_health.ai", "_render_ai_cross_fund_evaluation"),
    # ── 🧾 ① 結論層用的**純計算** helper（2026-09-08）─────────────
    # ⚠️ **這一組跟上面每一支都不同類，讀本表的人必須看得出差別**：
    #    上面那些是**會畫東西**的 renderer，住在閘門**後面**的委派區；
    #    這一組**一個 `st.` 都沒有**，住在閘門**前面**的結論層，只把數字算出來。
    #
    # ⭐ **「為什麼可以放在閘門前面」——本批的關鍵前提，用 AST 實測，不是推論：**
    #    閘門擋的是 `StreamlitDuplicateElementId`，而那個 id 是
    #    **`st.plotly_chart` 每次呼叫都註冊**才產生的（見 :data:`DELEGATE_GATE_LABEL`
    #    上方那一整段）。**渲染才會撞，計算不會。**
    #    這四支的函式體與其呼叫閉包（`check_eating_principal_1y_mk` /
    #    `compute_1y_total_return` / `_safe_num`）**沒有任何 `st.` 呼叫、也沒有任何
    #    I/O** —— 特別是**沒有** `checkup._safe_fx`（那支才會打 `get_latest_fx`）。
    #    守衛：`tests/test_wf02_health_conclusion.py::
    #           test_the_conclusion_layer_draws_nothing_through_the_shared_helpers`
    #    （用假 streamlit 錄一輪，錄到任何一筆就紅）。
    # ⛔ **因此不得為了拿這兩句結論而拆掉閘門、或放寬任何守衛** —— 也不需要。
    #
    # ⚠️ 它們是**私有名**（`_` 開頭），脆度與上面那四支 `fund_grp_health` 私有名相同，
    #    理由同上方那段登記：舊模組整批拔除時，這幾條是最先斷的。
    ("ui.helpers.fund.checkup", "_compute_fund_health_kpis"),
    ("ui.helpers.fund.checkup", "_ret_1y_total"),
    ("ui.helpers.fund.checkup", "_extract_peer_1y"),
    ("ui.helpers.fund.checkup", "_grade"),
)

# ── ⑥ 委派區 Checkbox Gate（2026-09-07，雙軌並行的必要條件）──────────────
#: gate 的字面。**畫面上與灰態指路吃的是同一個常數** —— 指到一個不存在的勾選框，
#: 是本 repo 發作過三次的死指路（同 ④ `page_04_portfolio.py::DIVCAL_GATE_LABEL`
#: 與 ⑤ `page_05_settings.py::NAV_GATE_LABEL` 的處置）。
DELEGATE_GATE_LABEL: str = "載入逐檔健診與互斥分析（與舊分頁同一份程式碼）"

#: ⛔ **這個 gate 擋的不是效能，是一個 CI 結構上看不到的當機。逐步寫清楚，不要靠記憶。**
#:
#: ## 機制（**讀 streamlit 1.59.1 原始碼求證，不是推論**）
#:
#: `st.tabs` 一次 run 會把**所有**分頁的 body 全部執行（`app.py` 自己的註解就地寫著）。
#: 雙軌之後舊 ②（`tab_health`）與新 ⑥（`tab_preview_health`）**委派同一批舊模組**，
#: 於是同一個 run 裡同一支 renderer 會被呼叫兩次。此時：
#:
#: - **`st.plotly_chart` 每一次呼叫都會註冊 element id** —— 1.59.1 `plotly_chart.py`
#:   就地註解逐字寫著「We are computing the widget id for all plotly uses」，
#:   `compute_and_register_element_id(...)` **不在任何 `if` 底下**。
#:   id 由 `plotly_spec`（圖的 JSON）＋ config ＋ theme ＋ 寬高算出 ⇒
#:   **同一份資料畫出同一張圖 ⇒ 同一個 id ⇒ 第二次呼叫拋 `StreamlitDuplicateElementId`**
#:   （`elements/lib/utils.py::_register_element_id`）。
#: - **`st.dataframe` 不會** —— 同版 `arrow.py` 的 `compute_and_register_element_id`
#:   包在 `if is_selection_activated:` 裡，而 `is_selection_activated = on_select != "ignore"`，
#:   預設就是 `"ignore"`。**本頁委派到的 7 個 `st.dataframe` 一個都沒有傳 `on_select`。**
#:
#: ⚠️ **這個不對稱是本批最容易搞錯的一點，據實寫明**：交接說明把
#:    `backtest_section.py` 的「3 個 `dataframe` ＋ 1 個 `plotly_chart`」當成同一種危險，
#:    **實測不是** —— 危險的只有 `plotly_chart` 那一個；而真正的 collision surface
#:    **另外還有兩個 `plotly_chart`**（`correlation.py` 與 `dividend.py`），
#:    那兩支交接說明完全沒有提到。**清單見 `tests/test_dual_track_plotly_id_collision.py`。**
#:
#: ## 為什麼 CI 看不到（這才是本批的重點）
#:
#: 舊 ② 在 `st.session_state["_fund_grp_health_ran"]` 沒有被設起來之前**直接 `return`**，
#: 而那個旗標要使用者**按過一次「🩺 開始健診」**才會是 True（`tab_fund_grp_health.py`
#: v19.504 就地註解）。CI 既沒有持倉、也不會去按那顆鈕 ⇒ **舊 ② 那一半永遠不執行**
#: ⇒ 兩份永遠不會同時出現 ⇒ **測試永遠是綠的**。
#: **但客戶有持倉，而且他按過那顆鈕之後旗標會一直留在 session 裡** ——
#: 從那一刻起他**每一次** rerun 都同時渲染兩份。
#:
#: ## 為什麼是 gate，不是「誠實留白（乾脆不委派）」
#:
#: 留白**不可逆**：它等於把「舊 ② 還在」寫死成一個永久假設，而**沒有任何機制**
#: 會在那個假設失效（舊 ② 整批拔除）的那天叫一聲。gate 則有前提守衛 ——
#: `tests/test_dual_track_plotly_id_collision.py::test_the_gate_still_has_a_reason_to_exist`
#: 在舊 ② 不再委派同一批模組的那一刻轉紅，告訴我們可以把 gate 拿掉了。
#: （同一個取捨 ⑤ 那一組已經做過一次並被獨立稽核驗過，本檔沿用，不另發明第二套。）
#:
#: ## 三顆已知的雷，逐一避開（本 repo 都真的踩過）
#:
#: 1. ⛔ **不得帶 `key=`** —— streamlit 對帶 `key=` 的 widget 會**代呼叫端**把值寫進
#:    `st.session_state`，那是每次渲染都發生、不經任何閘門的寫入，會踩
#:    `tests/test_wf02_health_no_writes.py::test_the_page_only_writes_its_own_session_namespace`。
#:    gate 只需要「這一次 run 有沒有勾」，直接用回傳值當條件即可。
#: 2. ⛔ **不得放進 `st.form`** —— 本檔一個 `st.form(` 站點都沒有（鐵則 02 走
#:    `ui.helpers.ia.applied_form`，`FORM_SITE_TOTAL` 精確 `== 7`），而且 form 內的
#:    widget 要按送出才生效，行為上也是錯的。gate 在 form **外面**。
#: 3. ⛔ **灰態本文不得把「勾下去」當成解法** —— 勾下去**正是撞的那一刻**。
#:    本文因此寫的是「勾下去會發生什麼」，指路指向**舊 ② 分頁**（內容現在真的在那裡），
#:    不是指向這個勾選框。**說反了比沒說更糟。**
#: ⚠️ **不寫 `where=` 指向 gate 自己**：那會變成「要修就勾它」，與第 3 點直接矛盾。
#: ⚠️ **寫成函式、分頁名走 `tab_label()`，刻意不手抄** —— 本 repo 分頁改名漏改
#: 已發作三次，每次都是「文案裡抄了一份分頁名」這個形狀。
#: ⛔ **不要改回模組層常數**：常數就得在 import 時求值，而 `tab_label()` 是
#: `story_nav` 的 SSOT 查表；寫成函式才能在改名後**自動跟著變**。
#: ⚠️ 這裡特別要提一筆：`tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`
#: 的比對規則是「**完整標籤（含 emoji 前綴）的子字串出現**」，所以像
#: 「② 持倉體檢」這種**丟掉 emoji 的手抄**它**抓不到**（該守衛自己的 docstring
#: 就地登記了這個缺口）。**本檔不靠那條守衛沒抓到就放行** —— 走 SSOT 是因為它對，
#: 不是因為抄了不會被抓。
def _delegate_gate_help() -> str:
    """gate 的 `help=` 文案。**同 ⑤ `_backfill_gate_label()` 的既有家風。**"""
    return (f"舊「{tab_label('health')}」分頁已經在畫同一批圖表。"
            "兩份同時載入會撞 Streamlit 的重複元件 ID（`plotly_chart`），"
            "畫面上會出現紅色錯誤塊。"
            "勾選只建議在**舊分頁尚未跑過健診**時用來預覽新版動線。")

#: `render_fund_grp_health_extras` 底下**線框明文搬 ③**、故本檔**刻意不接**的五塊。
#: ⚠️ 寫成常數是為了讓「為什麼少了這幾塊」可稽核 ——
#: 下一個人看到 ② 沒有「投資試算」時，要能查到這是**線框指定的**，不是漏接。
#: ⛔ **不要因為「舊 ② 本來就有」就把它們加回來** —— 那正是線框要拆掉的東西。
#: ⛔ **線框判給 ②、但因為會碰到寫入槽而「本批不接」的區塊。**
#:
#: **這一列不是「做不到」，是依既有裁決本來就不該進來** ——
#: 總管 2026-09-06 裁決（讀法甲）：**② 零寫入**；
#: 「在 `nav_history` 涵蓋範圍調查有結論之前，**不得**新增任何寫使用者 Google Sheet 的路徑」。
#:
#: **它是怎麼被抓到的（呼叫圖逐跳，不是猜的）**::
#:
#:     ui.views.page_02_health::_render_delegated_sections
#:       → ui.helpers.fund_grp_health.rotation::render_rotation_section
#:       → ui.helpers.fund_grp_health.rotation::_render_pairs_ui
#:       → ui.helpers.fund_grp_health.rotation::_render_pairs_body   ← 寫入槽
#:
#: ~~**渲染期就會碰到，不是綁在使用者點擊後面**：那個呼叫是~~
#: ~~`st.download_button(..., _out.to_csv(...).encode("utf-8-sig"), ...)` 的**引數**，~~
#: ~~必須在按鈕建立**之前**求值 —— 使用者沒有按任何東西，它就已經被呼叫了。~~
#:
#: ⚠️ **2026-09-07 更正：上面那句機制是錯的。有意識的更正，不是漏刪。**
#: **決策者：AI 總管（依獨立稽核實跑）**。本組已自行覆核（AST 實測，逐條）：
#:   - `_render_pairs_body` 的 `to_csv` **包在 `if offer_download:` 裡**；
#:   - 本檔委派的 `render_rotation_section` **硬編 `offer_download=False`**；
#:     傳 `True` 的是 `render_rotation_section_from_df`（**批次分頁，不是這一支**）。
#:   → **舊敘述只對批次那一支成立，對被委派的這一支不成立。**
#:
#: ✅ **守衛為什麼還是紅（這才是真正的機制）**：
#: `_sink_targets` 是**函式粒度的名字哨兵** —— 只要函式體內**任何位置**出現
#: `.to_csv(`（`ast.walk`，**不看分支、不看可達性、不看引數**），就把**整顆函式**
#: 登記為寫入槽、並把函式物件換成 recorder。
#: ⇒ 那筆紅是記在**進入** `_render_pairs_body` 的當下，**函式體一行都沒跑**。
#: ⇒ **對這個 call site 而言它是偽陽性。**
#: 📌 佐證：同一份 PR 的另一條守衛判定相反 —— `_callgraph_sheet_writes` 對
#:    `render_rotation_section` 是 **hits 0**（`to_csv` 不在 `_SHEET_WRITE_METHODS`，
#:    那條只管 Google Sheet）。
#:
#: ⛔ **但「偽陽性」不是把它接回來的理由，也不是改守衛的理由。**
#: `to_csv` 是依前次稽核**刻意補進**名字清單的，判準是「名字含不含糊」。
#: **在合併壓力下放寬守衛，正是本 repo 反覆吃虧的形狀。**
#:
#: ✅ **它要回到 ② 的前提（2026-09-07 更正：前提換了，因為舊前提繫於錯的機制）**：
#:   ~~(1) `nav_history` 涵蓋範圍調查有結論；(2) 補齊呼叫圖 ＋ 執行期哨兵雙重證據。~~
#:   → **改為：等守衛能分辨「分支／引數」之後**（也就是 `_sink_targets` 不再是
#:     純函式粒度的名字比對）。**總管已另開一單處理守衛精度，不併進本批。**
#: ⛔ **在那之前不得把它加進 `DELEGATED_ENTRIES`，也不得改守衛去配合它。**
DROPPED_FOR_ZERO_WRITE: tuple[tuple[str, str], ...] = (
    ("ui.helpers.fund_grp_health.rotation", "render_rotation_section"),
)

MOVED_TO_PAGE_03: tuple[tuple[str, str], ...] = (
    ("ui.helpers.fund_grp_health.investment", "_render_investment_calc"),
    ("ui.helpers.fund_grp_health.investment", "_render_holdings_block"),
    ("ui.helpers.fund_grp_health.signals", "_render_bollinger_expanders"),
    ("ui.helpers.fund_grp_health.ai", "_render_per_fund_news_expanders"),
    ("ui.helpers.fund_grp_health.ai", "_render_per_fund_three_ratio_expanders"),
)

#: ⛔ **黑名單：接了就是把 P0 寫入面搬回 ②。**
#: 這兩支**打開就寫一列進客戶的 Google Sheet**，沒有按鈕、沒有勾選。
#: 它們住在 `ui/helpers/fund_grp_health/`，也就是**舊 ② 的資料夾** ——
#: 任何「照資料夾整包委派」的作法都會把它們一起帶回來，所以要具名擋。
DELEGATION_BLACKLIST: tuple[tuple[str, str], ...] = (
    ("ui.helpers.fund_grp_health.switch_advisor_section",
     "render_switch_advisor_section"),
    ("ui.helpers.fund_grp_health.switch_advisor_section",
     "render_portfolio_tracking"),
)

#: **第一階段刻意沒接**的入口，以及**具名**理由。
#:
#: ⚠️ 寫成常數而不是散在註解裡，是為了讓「為什麼沒接」跟「接了什麼」一樣可稽核 ——
#: 一個沒有理由的缺口，下一輪就會被當成「還沒排到」隨手補上（本檔上方
#: `_SCORE_PENDING_NOTE` 那段講的就是這件事）。
#:
#: ⭐ **2026-09-06 第二輪：原本三條裡的前兩條已被核准線框推翻，就地加刪除線保留。**
#: **有意識的政策變更，不是漏刪** · 日期 **2026-09-06** · 決策者：**AI 總管**（依核准線框逐字）。
#:
#: ~~① `render_fund_grp_health_extras`：`principal_twd` 無第二來源、新增 widget 需客戶草稿。~~
#:   → **推翻**：核准線框 `wireframe-macro-health.html` 的「Form ②-A　健診輸入」內
#:     **逐字就有「本金（TWD）：1,000,000」**（本組開檔核對）。既然有既有規格可對照，
#:     加回去屬「**修正錯誤**」而非「改變設計」，是內部自決。**已加回**（見
#:     :data:`_DEFAULT_PRINCIPAL_TWD`）。**舊理由的事實面仍然成立**
#:     （repo 裡確實只有舊 ② 那一個 widget）—— **被推翻的是它的結論**：
#:     我漏查了線框，把「本頁骨架來源 `ia-wireframe.html` 沒有」誤當成「線框沒有」。
#:   ⚠️ 但 `render_fund_grp_health_extras` **整支仍然不接**，改成**拆開逐支接**（見
#:     :data:`DELEGATED_ENTRIES` 與 :data:`MOVED_TO_PAGE_03`）—— 換了理由，不是換了結論。
#:
#: ~~② `render_allocation_backtest_section`：屬再平衡試算，線框說 → 04。~~
#:   → **推翻，這一條是本組判錯**：同一份線框 §04 對照表**逐字**寫
#:     「📊 健診大表／🩺 體檢 PK／📈 比較圖／**🔁 回測**／⑫ AI 跨檔｜**留 ② 原位**｜
#:     全部是**跨檔**比較或組合層結論，正是 ② 的題目」，並標「哪套配置效益最高
#:     （**教學非建議**）」。**已接**。
#:   ⚠️ **歸屬判斷的分界由總管承擔，不是線框明文**：線框**沒有定義**「再平衡試算」的外延，
#:     總管的依據是「教學非建議」這個標註 ⇒ 它不落在被排除的「**建議**」那一類。
#:     **這一句刻意寫在程式碼裡，不是只寫在 PR 描述裡** —— 日後有人質疑
#:     「② 為什麼有回測」時，要看得到這是誰、依據什麼下的判斷。
#:
#: **只剩下面這一條仍然成立**（key 交集是實測，不是判讀）：
DEFERRED_ENTRIES: tuple[tuple[str, str], ...] = (
    ("ui.helpers.fund_grp_health.{switch_section,regime_section}"
     "::{render_switch_section,render_regime_fit_section}",
     "兩支都吃**健診大表列** `df.to_dict('records')`，不是本頁的 9 欄列。"
     "實測 key 交集 **0/8** 與 **0/4**（連 `code` 都沒有：本頁的鍵是「代碼」）；"
     "且本頁的值是**格式化後的顯示字串**（`_pct()` 產「12.34%”），"
     "而 `replacement_candidate` 要對 `Sharpe 1Y`／`Sortino` 做加權**算術**。"
     "→ 需要一個 rows adapter，規格見本輪回報；**不硬湊一份假的 rows**（§1）。"),
)


#: 本金（TWD）widget 的 `help=`。**寫成常數，是為了讓「文案有沒有跟著接線走」可以被機器守。**
#:
#: ⛔ **2026-09-08 就地更正：舊文案是一句不成立的話。有意識的更正，不是漏刪**
#: （決策者：**AI 總管**；依據：**本頁既有的 AST 實測**，見 `_render_filter_form` 內
#: 2026-09-07 那條更正 ——「`_principal_twd` 呼叫點 0、裸參照 0」）。
#: 舊文案逐字寫著：
#:
#:     ~~「所有基金都假設投入這個金額，才能把「每月配息」「累積配息」放在同一個
#:       尺度上比較。**這不是你的實際投入金額。**」~~
#:
#: **它描述的是一個本頁沒有發生的行為**：本頁沒有任何區塊讀這個值，而唯一真的會用到
#: 「每月配息」的地方（本檔新增的 🧾 ① 結論層）用的是**各檔實際 `invest_twd`**，
#: 也就是**與舊文案所述正好相反**。
#: **舊表述在寫下的當天為什麼是對的**：它照抄舊 ② 的語意（舊 ② 真的把每檔本金覆寫成
#: 同一個值），那是有出處的；**被推翻的是它的前提** —— 新頁沒有把那條線接上。
#:
#: ⚠️ **這是「修正錯誤」不是「改變設計」**（§-1.5.4 兩步判定）：版面結構未動、
#: widget 未增未減、四個界值一個沒改（`_WIREFRAME_PRINCIPAL` 照舊釘住）；
#: 改的只有一句**與實際行為不符的描述**。
#: ⛔ **這一批沒有動這個 widget 的去留** —— 拿掉它會同時打掉三條既有守衛
#: （`test_the_principal_input_keeps_the_wireframe_numbers` /
#:  `test_the_principal_is_read_from_the_applied_gate_not_derived` /
#:  `test_the_principal_input_lives_inside_the_single_applied_form`），
#: 而**為了拿掉一個 widget 去放寬守衛是本 repo 反覆吃虧的形狀**。已具名回報總管裁決。
#: **守衛**：`tests/test_wf02_health_conclusion.py::
#: test_the_principal_help_never_claims_a_consumer_it_does_not_have`
#: —— 它把**文案**跟**接線**綁在一起：0 caller 時文案必須誠實揭露；
#: 哪天有人真的把它接上，那條守衛會轉紅，逼他回來改文案。**兩個方向都 fail-closed。**
PRINCIPAL_HELP: str = (
    "這個欄位**目前不影響上面任何一個數字**。"
    "上方的「每月配息合計」算的是**你每一檔實際投入的金額**。"
    "這裡填的是「假設每檔都投入同一筆錢」的比較基準，保留給日後的齊頭比較功能。")

#: ⚠️ **上面那段 `help=` 是給使用者看的，工程細節一律留在這裡（2026-09-08 M3）。**
#:
#: **舊文案**（同日稍早）寫的是：
#:   ~~「⚠️ **這一欄目前沒有任何區塊在讀它**（本頁實測 **0 caller**）……**接線與否待客戶裁決**」~~
#:
#: **事實完全正確**（獨立稽核驗過 0 caller），**錯的是講給誰聽**：
#: 「0 caller／接線／待客戶裁決」是**我們內部的話**，而客戶第二條驗收標準逐字是
#: 「讓**新手**也能看得懂」。**一句對的話講給錯的人聽，在這一頁就是錯的。**
#: ⛔ **不得把工程術語搬回 `help=`** —— 那是使用者滑鼠停在輸入框上會看到的東西。
#:
#: **工程事實（留在這裡，不上畫面）**：`_principal_twd()` 目前 **0 caller**；
#: 使用者填了數字、按了套用，下游一個字都不會讀。
#: 該 widget 的去留已具名回報總管，本批**不動**（拿掉會打掉三條既有守衛）。


# ══════════════════════════════════════════════════════════════════════
# 🧾 ① 結論層 —— 本頁原本缺的那一層（2026-09-08）
# ══════════════════════════════════════════════════════════════════════
#: 結論層的標題。**與 ① `page_01_macro.py::_render_layer_conclusion` 同一個層級、
#: 同一種寫法**（`###`）—— 本 repo 已經有一套四層閱讀順序，這裡不發明第二套。
#:
#: ⚠️ 寫成常數而不是 inline 字面值：守衛要拿它比對「結論在依據**前面**」，
#: 抄一份字面值到測試裡就是第二份真相源（§2.1）。
CONCLUSION_HEADING: str = "### 🧾 ① 結論 — 我手上這些，現在怎麼了"

#: 逐檔判定失敗時的落點。**具名，不靜默丟掉那一檔**（§1）——
#: 一檔判定拋例外若直接 `continue`，那一檔就從分母裡消失，而使用者看不出來。
_VERDICT_ERROR: str = f"{NOT_READY_MARK} 判定時出錯（詳見系統紀錄）"


def _income_tally(funds: list[dict]) -> dict[str, Any]:
    """每月配息合計（TWD），**外加「沒算進去的各是什麼原因」**。

    ~~⭐ **這是本批最高價值的一句話：客戶目前在三頁閘門前完全答不出「我每個月領多少」。**~~
    ~~盤點實測：「配息覆蓋」是**比率**、「吃本金警示」給**檔數**、⑧ 的配息表是~~
    ~~**每單位、原幣** —— 三頁閘門前**沒有任何一個 TWD 金額**。~~

    ⛔ **2026-09-08 就地更正：上段為假。有意識的更正，不是漏刪**
    （決策者：**AI 總管**，依獨立稽核指出；**本組已逐條複驗，不是轉述**）。

    **實測推翻它的兩條（指令與輸出見本輪 PR 描述）**：

    - **逐檔的月配息 TWD 早就存在，而且吃的就是使用者各檔真實 `invest_twd`**：
      `ui/helpers/fund/checkup.py::_compute_fund_health_kpis` 算它、同檔
      `_render_fund_health_card` **無條件**渲染那格 KPI，`build_checkup_dataframe`
      另有「原幣本金／月配息／年配息」三欄。
    - **本檔早在 2026-09-07 就更正過同一個誤解** —— 見 :func:`_render_delegated_sections`
      docstring 那段「⛔ 上面那句對 `render_fund_checkup` 是假的」。
      **再講反一次，等於覆蓋掉 repo 已經查證過的事實。**

    ✅ **真正成立的問題是兩個，而且是不同的兩個 —— 分開讀**：

    1. **它被閘門關著。** ⑥ 對 `render_fund_checkup` 的呼叫住在
       :func:`_render_delegated_sections` 的 Checkbox Gate **之後**（預設不勾），
       所以使用者一打開 ⑥ **看不到**它。**存在 ≠ 看得到。**
    2. **它是逐檔的，沒有「合計」。** 客戶問的是「**我每個月總共領多少**」。
       實測全 repo，`monthly_div_twd` 的消費者**全部是逐檔的**（`checkup.py` 內
       計算處、回傳處、健診卡文字、逐檔 row dict），**沒有任何地方把它加總**。
       ⇒ **本函式新增的只有「加總」這一步，公式仍然完全走 SSOT。**
       ⚠️ **這一句只對「月配息 TWD」成立，不要外推** —— 舊 ② 確實有一個
       **別的**金額合計（「累積 TWD 配息」，見下方 📌），那是另一個量。
       ⚠️ 而本頁的另一句結論（:func:`_peer_verdicts`）**處境不同**：
       那個盤點**上游已經有了**，本頁新增的是「把它搬到閘門前」＋兩處改良，
       **不是新增一個統計**。**兩句不要一起宣稱成「本批新做的」。**

    📌 **另一個相關、但不是同一個東西的量，據實登記（⛔ 不得互相冒充）**：
    核准線框 `docs/wireframes/wireframe-macro-health.html` 的「大表區」5 格 KPI，
    第 5 格逐字是「**累積 TWD 配息**」，而它**已經實作在舊 ②**
    （`ui/tab_fund_grp_health.py::_render_health_summary`，
    `total_twd = sum(r["累積 TWD 配息 🧮"] …)` ＋ `k5.metric(...)`）。
    **那是「到今天為止實際領到的」；本函式算的是「依年化配息率推估的每月」——
    兩個不同的數。** ⛔ **所以不得在任何地方寫「線框沒要求配息金額」，也不得宣稱
    本批做到了線框那一格。**
    **本批沒有接它，理由不是漏做**：它的列來自
    `services/fund_row.py::process_one_fund`，該函式 docstring 自陳「**純 IO** + 計算」
    （`auto_fetch_moneydj` / `get_latest_fx`）—— 在閘門前跑它等於把重取數搬到頁面入口；
    而舊 ② 那份合計住在 `ui/tab_fund_grp_health.py`，本檔**禁止 import**
    （`tests/test_wf02_health_skeleton.py::test_the_page_does_not_delegate_to_the_old_tab`）。
    ⇒ **登記為缺口，不是宣稱不需要。**

    **數字從哪來（不是本檔算的）**
    ------------------------------
    走 `ui.helpers.fund.checkup._compute_fund_health_kpis`，取它的
    ``monthly_div_twd`` —— 那是 SSOT 自己的公式
    ``invest_twd × 年化配息率 ÷ 12``（`adr` 走 MoneyDJ wb05 優先、缺則退
    `metrics.annual_div_rate`）。**本檔一個門檻、一條公式都沒有自己寫**（§3.3）。

    ⛔ **不用齊頭本金。** 這一句要回答的是「**我**每個月領多少」，
       所以吃的是使用者**每檔真正的** ``invest_twd``；
       用 `_principal_twd()`（＝「假設每檔都投入 100 萬」）會變成**另一個問題的答案**，
       而畫面上看不出差別（§1：錯的數字比沒有數字更危險）。

    **為什麼可以放在委派區的 Checkbox Gate 前面（AST 實測，非推論）**
    ------------------------------------------------------------------
    閘門擋的是 `st.plotly_chart` 的重複 element id；**那是渲染才會發生的事**。
    `_compute_fund_health_kpis` 的函式體與其呼叫閉包
    （`check_eating_principal_1y_mk` / `_ret_1y_total` / `_safe_num`）
    **一個 `st.` 都沒有、也沒有任何 I/O**（特別是**沒有** `checkup._safe_fx` ——
    那支在幣別非 `TWD` 時會去打 `get_latest_fx`；`TWD` 直接回 `1.0`、沒有幣別則整個跳過。
    **精確講清楚，是因為本 PR 已經因為含糊的全稱句被推翻兩次**）。
    ⇒ **計算搬到閘門前不會撞，也不會多一次網路往返。**
    守衛：`test_the_conclusion_layer_draws_nothing_through_the_shared_helpers`。

    **回傳的四個計數，為什麼要分那麼細**
    ------------------------------------
    ``monthly_div_twd`` 是 None 有**兩個完全不同的原因**，而它們的下一步不一樣：

    - **沒有 `invest_twd`** → 使用者**可以去補**（④ 加入與管理基金）→ ``no_amount``
    - **有金額、但查不到年化配息率** → 使用者**補不了**，那是上游沒抓到 → ``no_rate``

    把兩者併成一句「N 檔資料不足」，等於把**唯一可行動的那個原因**蓋掉
    （同本檔 `_SCORE_PENDING_NOTE` 上方那一整段講的病）。

    ⚠️ **兩個都缺時算進 ``no_amount``**：那句話（「沒有填投入金額」）對它**仍然為真**，
    只是不是唯一的原因；選這一邊是因為它是**可行動**的那一邊。**這是刻意的取捨，不是漏判。**

    ⚠️ **單檔失敗不拖垮整句**（同 :func:`_eating_verdict` 的處置）：例外印到 stderr
    並落進 ``no_rate``，**不是靜默跳過** —— 靜默跳過會讓那一檔從分母消失。
    """
    from ui.helpers.fund.checkup import _compute_fund_health_kpis

    _out: dict[str, Any] = {"monthly_twd": None, "counted": 0,
                            "no_amount": 0, "no_rate": 0, "total": len(funds)}
    _sum = 0.0
    for _f in funds:
        try:
            _k = _compute_fund_health_kpis(_f)
        except Exception as _exc:  # noqa: BLE001 — 留痕，不靜默
            import sys as _sys
            print(f"[page_02_health] _compute_fund_health_kpis 失敗 "
                  f"({_f.get('code')}): {type(_exc).__name__}: {_exc}", file=_sys.stderr)
            _out["no_rate"] += 1
            continue
        if not isinstance(_k, dict):
            _out["no_rate"] += 1
            continue
        _m = _safe_num(_k.get("monthly_div_twd"))
        if _m is not None:
            _sum += _m
            _out["counted"] += 1
        elif _safe_num(_k.get("invest_twd")) is None:
            _out["no_amount"] += 1
        else:
            _out["no_rate"] += 1
    if _out["counted"]:
        _out["monthly_twd"] = _sum
    return _out


def _peer_verdicts(funds: list[dict]) -> "tuple[list[tuple[str, int]], list[tuple[str, int]]]":
    """逐檔「跟同類型比，到底好不好」→ ``(判得動的, 判不動的)``，各為 ``[(判定字, 檔數)]``。

    ⭐ **這一句回答客戶的第一題：「無法判斷這檔基金好不好」。**

    ⛔⛔ **先講清楚「新在哪裡」，因為這一句**不是**憑空多出來的（2026-09-08 實測）**
    ------------------------------------------------------------------------
    `ui/helpers/fund/checkup.py::render_fund_checkup` **已經在畫一句幾乎一樣的話**::

        _verdict = df["體檢判定"]
        n_good = int(_verdict.str.startswith("🏆").sum())
        n_lag  = int(_verdict.str.startswith("⚠️").sum())
        n_na   = int(_verdict.str.startswith("⬜").sum())
        # …接著印出「🏆 n_good 檔 ・ ⚠️ n_lag 檔 ・ ⬜ n_na 檔（共 len(df) 檔）」

    **和上面 :func:`_income_tally` 那個配息數字一模一樣的處境** ——
    它**存在、而且是對的**，只是**住在閘門後面**（⑥ 對 `render_fund_checkup`
    的呼叫在 :func:`_render_delegated_sections` 的 Checkbox Gate 之後，預設不勾）。
    ⛔ **所以不得寫「⑥ 判不出基金好不好」——那是假的。** 成立的說法是
    **「使用者一打開 ⑥ 看不到它」**。

    **本函式真正新增的只有三件事，逐條列出，不要多宣稱**：

    1. **它在閘門前**（那正是這一批要解決的問題）。
    2. **它不丟掉 `🟡` 那一桶。** 上游那一句只印 🏆／⚠️／⬜ 三個桶，
       **`🟡` 沒有自己的數字**，使用者得拿「（共 N 檔）」自己減。本函式按
       `_grade` **實際回傳的每一個桶**計數，一個都不省。
    3. **它不寫死 emoji 前綴。** 上游用 `.str.startswith("🏆")`；本函式拿
       `_grade` **回傳的整句話**當 key ⇒ SSOT 改措辭，本頁自動跟著改。

    ⚠️ **上游那一句同時是本函式的正確性對照**：同一組持股，兩邊的 🏆／⚠️／⬜
    **必須對得上**（都走同一支 `_grade`）。對不上就是本函式錯了。

    ⛔⛔ **兩個必須寫在這裡、不能只寫在 PR 留言的事實（2026-09-08 獨立稽核實測）**
    ----------------------------------------------------------------------------
    **(1) 勾開閘門之後，這一頁會有兩句在講同一件事。**
    稽核把畫面真的渲染出來，同一次 run 錄到**兩句摘要**：一句來自本函式，
    一句來自 `checkup.render_fund_checkup`（上游）。
    ⚠️ **但預設畫面只有本函式這一句** —— 上游那句要使用者**主動勾**
    :data:`DELEGATE_GATE_LABEL`（`value=False`）才會出現。

    **(2) ⛔ 上游那一句是錯的 —— 它漏數一個桶。**
    上游只 `startswith` **三個** emoji 前綴（`🏆` / `⚠️` / `⬜`），
    而 `_grade()` 實際會回**四種**判得動／判不動的結果 ——
    **`🟡`（與同類持平）那一桶沒有自己的數字**。
    於是在「四檔、每桶各一」的情境下，它印出來的三個數字加起來是 **3**，
    卻同時宣稱「**共 4 檔**」：**第 4 檔在摘要裡憑空消失。**
    **這不是「重複」的問題，這是線上舊分頁現在就有的缺陷 —— 摘要與分母對不起來。**

    ⚠️ **上面刻意用「描述」而不是貼原文，這一點請照做下去。**
    本檔受 `test_the_page_never_hardcodes_the_ssot_verdict_words` 管，
    **整份原始碼**（含 docstring）都不准出現 `_grade()` 的中文判定字面值 ——
    **貼一段畫面輸出當證據，就會把那些字帶進來**（本 PR 為此紅了兩次，第二次
    正是「為了記錄第一次」而貼了原文）。
    ⛔ **不要為了「讀起來完整」把桶名補回來。** 要指哪一桶，用 **emoji** 或
    `_grade()` 的回傳值來指 —— **描述保住了每一個承重事實，而且一個字面值都沒抄。**

    ⛔ **本批不修它，四個理由，這是總管 2026-09-08 的裁決，不是我的偷懶**：
      1. 它住在**舊 ② 分頁共用**的 `ui/helpers/fund/checkup.py`，而客戶紅線是
         「**絕對禁止**修改現有線上正常運作的舊版 Tab 代碼」——**那條線不由我方放寬**。
      2. 重複**只在使用者主動勾選之後才出現**；預設畫面只有本函式這一句，而且是對的那一句。
      3. 另兩條「消重」路都被否決：給 gate checkbox 加 `key=` 會踩本頁的寫入守衛，
         **而且會藏掉對的、留下錯的**；把結論搬到閘門後則讓整批失去意義。
      4. 客戶驗收新 ⑥ 並下令拆掉舊分頁時，重複與該缺陷會**一起消失**。
    ⚠️ **不要把上面第 4 點讀成「未來會修」** —— 那不是本批能承諾的事，
    它只是說明「為什麼現在為它碰紅線划不來」。
    **守衛**：`test_the_per_fund_number_is_gated_but_our_total_is_not`
    釘住「`render_fund_checkup` 的呼叫點只在委派區」——
    它一旦被搬到閘門外，上面「使用者看不到」這句話當場失效，該條轉紅。

    **判準完全走既有 SSOT，本檔沒有自己定義任何門檻**
    --------------------------------------------------
    `ui.helpers.fund.checkup._grade(近一年含息報酬, 同類型平均)` ——
    它就是使用者在**閘門後**那張基金體檢表「體檢判定」欄看到的同一支函式，
    門檻 `_EXCESS_GOOD` / `_EXCESS_LAG` 也住在那裡。

    ⛔ **為什麼不照派工單原本舉例的「四項都在標準內」**（近 1 年／Sharpe／最大回撤／配息覆蓋）：
       那需要替 Sharpe 與最大回撤**發明兩個門檻** —— 本站的 `services/**` 沒有這兩個門檻，
       而在 UI 層自己訂一個，等於在畫面上生出一條沒有出處的業務規則（§3.3 反捏造），
       而且它會**跟閘門後那張表的判定各說各話**（§2.1：同一個組合、兩個結論，
       使用者只會覺得系統壞了）。
       改走 `_grade` 之後：**零新門檻、零新公式，而且與同頁那張表逐字一致。**

    ⛔ **本檔不把 `_grade` 的字串抄一份下來分桶。** 分桶直接拿它**回傳的那句話**當 key
       —— SSOT 改措辭，畫面自動跟著改；抄一份就會有一天兩邊不一樣而沒人發現。

    **「判不動」為什麼一定要獨立成一類**
    ------------------------------------
    `_grade` 對缺資料回的是 ``(None, "⬜ …資料不足")``。把它併進「沒問題」那一堆，
    就是本頁 `_eating_tally` 早就寫死的那條規矩的反面 ——
    該處逐字寫著「**無法判定（不是判定為沒有吃本金）**」。**這裡照同一個慣例。**

    **排序**：判得動的依**該桶最好的超額報酬**由大到小（好消息在前、壞消息看得見）；
    判不動的依檔數由多到少。**兩者都是決定性的**，不吃 dict 的插入順序。
    """
    from ui.helpers.fund.checkup import _extract_peer_1y, _grade, _ret_1y_total

    _judged: dict[str, list[float]] = {}
    _unjudged: dict[str, int] = {}
    for _f in funds:
        try:
            _peer, _ = _extract_peer_1y(_f)
            _excess, _text = _grade(_ret_1y_total(_f), _peer)
        except Exception as _exc:  # noqa: BLE001 — 留痕，且**仍然計入分母**
            import sys as _sys
            print(f"[page_02_health] _grade 失敗 "
                  f"({_f.get('code')}): {type(_exc).__name__}: {_exc}", file=_sys.stderr)
            _unjudged[_VERDICT_ERROR] = _unjudged.get(_VERDICT_ERROR, 0) + 1
            continue
        _e = _safe_num(_excess)
        if _e is None:
            _key = str(_text or _VERDICT_ERROR)
            _unjudged[_key] = _unjudged.get(_key, 0) + 1
        else:
            _judged.setdefault(str(_text), []).append(_e)
    return (
        [(_t, len(_v)) for _t, _v in
         sorted(_judged.items(), key=lambda _kv: -max(_kv[1]))],
        sorted(_unjudged.items(), key=lambda _kv: (-_kv[1], _kv[0])),
    )


def _render_income_line(funds: list[dict]) -> None:
    """結論句 ①：**每月配息合計（TWD）**。算不出來就誠實留白（§1）。"""
    _t = _income_tally(funds)
    _left_out = []
    if _t["no_amount"]:
        _left_out.append(f"{_t['no_amount']} 檔沒有填投入金額")
    if _t["no_rate"]:
        _left_out.append(f"{_t['no_rate']} 檔查不到配息率")

    if _t["monthly_twd"] is None:
        # ⛔ **不印「0 TWD」。**「算不出來」與「一毛都沒領」在畫面上長得一樣、意思相反
        #    （同 `_render_alert_cards` 對「0 檔吃本金」的處置）。
        not_ready(
            "算不出你每月的配息合計（TWD）："
            + ("、".join(_left_out) or f"這 {_t['total']} 檔都沒有可用的配息資料")
            + "。**不拿「假設每檔都投入同一個金額」的齊頭本金替你估一個數字** —— "
              "那是另一個問題的答案。"
            # ⚠️ 這句刻意**不寫出那個金額**：本檔已經有 `_DEFAULT_PRINCIPAL_TWD`，
            #    在文案裡抄一份數字就是第二份真相源，常數一改畫面就開始說謊（§3.3）。
            ,
            where=where_to_find("pf_add"))
        return

    st.markdown(
        f"**每月配息合計約 {_t['monthly_twd']:,.0f} TWD**"
        f"（依這 {_t['counted']} 檔**各自實際投入的金額**推估，不是齊頭本金）。")
    if _left_out:
        # §1：沒進到那個數字裡的檔數要講出來，否則使用者會以為「這就是全部」。
        st.caption("・另有 " + "、".join(_left_out) + "，**都沒有算進上面那個數字**。")


def _render_verdict_line(funds: list[dict]) -> None:
    """結論句 ②：**這幾檔跟同類型比，好不好**。判不動的獨立成一類（§1）。"""
    _judged, _unjudged = _peer_verdicts(funds)
    # ⚠️ `{_c} 檔` 與 `{_t}` 之間的空格是刻意的：`_t` 以 `⬜` 開頭，
    #    黏在一起會變成「3 檔⬜ 同類資料不足」，一頁在講「看得懂」的畫面不該這樣讀。
    _undecided = "、".join(f"{_c} 檔 {_t}" for _t, _c in _unjudged)

    if not _judged:
        not_ready(
            f"這 {len(funds)} 檔**都判不出**跟同類型比好不好："
            + (_undecided or "沒有可比對的同類型平均")
            + "。**判不出來不等於沒問題。**",
            where=_pending_where("下方「逐檔體檢表」可先逐檔看"))
        return

    st.markdown(
        f"**這 {len(funds)} 檔裡："
        + "、".join(f"{_t} {_c} 檔" for _t, _c in _judged)
        + "**（比的是「近一年含息報酬 − 同類型平均」）。")
    if _unjudged:
        st.caption(f"・另有 {_undecided}，**未判定 ≠ 沒問題** —— 那幾檔在下方逐檔表也是空的。")


def _render_conclusion() -> None:
    """區塊 1.5｜🧾 ① 結論 —— **兩句話，沒有第三樣東西。**

    ⛔ **這一層的驗收標準是「有沒有回答問題」，不是「有沒有更多資訊」。**
    若哪天有人在這裡加了第三、第四句、或一張表，請先回頭讀本檔模組 docstring
    引的客戶第二句原話：**「我覺得舊 UI 資訊太多」** —— 把密度搬回來就是把它推翻。
    """
    st.markdown(CONCLUSION_HEADING)
    _funds = _uniq_by_code(_holdings())
    _render_income_line(_funds)
    _render_verdict_line(_funds)


def _pending_where(block: str) -> str:
    """「內容還沒填」這種灰態的指路。

    ⚠️ **這種灰跟「沒有持倉」那種灰不一樣，使用者沒有地方可以去** ——
    所以指路能給的最誠實的東西是「**現在哪一塊是完整的**」，而不是假裝有個開關可以按。
    同樣的處理在 ① 做過一次（`page_01_macro.py::_detail_pending`）。

    ⚠️ 分頁名走 `where_to_find()`，**不手抄**；區塊名由呼叫端傳進來，
    不在這裡再抄一份（手抄的指路在本 repo 已經指錯三次）。

    ⚠️ **2026-09-06 就地更正：舊版寫死「目前只有『診斷條件』是完整的」，本批之後那句話變成假的。**
    骨架批只有 Form 是完整的，所以那句在**當時為真**；本批把「吃本金警示」「影子基金重疊」
    「逐檔體檢表」三塊接上真資料之後，它就成了一句**會誤導使用者的過期承諾** ——
    使用者照它走到「診斷條件」，會發現那裡什麼診斷結果都沒有。
    **一句在寫下當天為真的指路，不會自己過期；它只會安靜地變成假的。**
    現行做法：由呼叫端傳入**那一塊自己的**下一步，本函式只負責把分頁名接上（仍不手抄）。
    """
    return f"{where_to_find('health')} → {block}"


def _holdings() -> list[dict[str, Any]]:
    """使用者**目前持有**的基金。

    讀既有 session 契約 `portfolio_funds`（由 ④ 寫入），**不自己取數**。

    ⚠️ **`loaded` 過濾是刻意的**：那份清單裡會有「已列入但 NAV 還沒抓回來」
    與「抓取失敗」的項目（`ui/helpers/portfolio/load.py` 寫入 `loaded` / `load_error`
    兩個旗標）。拿那些去算體檢分數，等於用不完整的資料生一個看起來完整的結論（§1）。
    ⚠️ **回傳空 list 有兩種原因**（完全沒設定 vs 設定了但都還沒載入成功），
    本批的骨架**不區分**它們 —— 因為兩者的下一步都是先去 ④。
    下一批若要分開講，這裡是分岔點。
    """
    _raw = st.session_state.get(_SK_PORTFOLIO) or []
    if not isinstance(_raw, list):
        return []
    return [_f for _f in _raw
            if isinstance(_f, dict) and _f.get("loaded") and not _f.get("load_error")]


def _applied_filters() -> dict[str, Any]:
    """**已套用**的診斷條件；沒按過「套用」就是線框寫的那組預設值。

    ⚠️ 下游一律讀這個，**不要讀 widget 的回傳值** —— 讀了就等於沒有 form
    （鐵則 02 的重點不是「有沒有 form」，是「重運算有沒有被 gate 住」）。
    """
    _cur = st.session_state.get(_SK_APPLIED)
    if isinstance(_cur, dict):
        return _cur
    return {
        "sigma": _DEFAULT_SIGMA,
        "window_months": _DEFAULT_WINDOW_MONTHS,
        "satellite_only": _DEFAULT_SATELLITE_ONLY,
        "principal_twd": _DEFAULT_PRINCIPAL_TWD,
    }


def _principal_twd() -> float:
    """**已套用**的本金（TWD）。委派區塊的 `principal_twd` 引數只准從這裡拿。

    ⚠️ **舊值相容**：`_SK_APPLIED` 可能是本欄位加入**之前**存下的 dict
    （使用者上一輪按過「套用」、session 還活著），那時候沒有 `principal_twd` 這個鍵。
    `.get(..., 預設)` 是為了那個情形，**不是**為了容忍缺值 —— 缺就退回線框的預設值，
    那是**有出處的常數**（見 :data:`_DEFAULT_PRINCIPAL_TWD`），不是隨手編一個數字。
    """
    _v = _applied_filters().get("principal_twd", _DEFAULT_PRINCIPAL_TWD)
    try:
        return float(_v)
    except (TypeError, ValueError):
        return float(_DEFAULT_PRINCIPAL_TWD)


def _render_filter_form() -> None:
    """區塊 1｜Form — 診斷條件。**本批唯一做完的一塊。**

    線框 Tab 02 逐字：「輪動門檻　σ ±1.0／回看窗　12 個月／只看衛星　☐／套用」。

    ⚠️ **沒有基金代號輸入框，這是客戶 2026-09-05 的裁決，不是漏做**：
    持股一律從組合帶入（見 :func:`_holdings`）。日後若有人覺得「加個代號框比較方便」，
    那是**把 ③ 標的探索的職責搬進來**，線框把「我沒持有的基金」明列在「這裡不放什麼」。
    """
    _cur = _applied_filters()
    with applied_form(_FORM_KEY) as _gate:
        st.caption("條件改完按「套用」才重算 —— 拖滑桿的當下不會觸發任何取數。")
        _sigma = st.slider(
            "輪動門檻　σ", min_value=_SIGMA_MIN, max_value=_SIGMA_MAX,
            value=float(_cur["sigma"]), step=_SIGMA_STEP,
            help="偏離同類均值幾個標準差才算異常。",
        )
        _window = st.number_input(
            "回看窗（月）", min_value=_WINDOW_MIN, max_value=_WINDOW_MAX,
            value=int(_cur["window_months"]), step=1,
            help="往回看多久的績效來判定。",
        )
        _satellite_only = st.checkbox(
            "只看衛星", value=bool(_cur["satellite_only"]),
            help="勾選後只診斷衛星部位，核心部位不列入。",
        )
        # ⭐ 本金（TWD）—— 核准線框 Form ②-A 逐字有這一欄，2026-09-06 加回。
        # ⚠️ **放在既有的 `applied_form` 裡面，不另開第二個 form**（鐵則 02：
        #    本頁 `st.form` 站點必須維持 0，`applied_form` 維持 1；自己寫 form
        #    會讓 `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==7`）轉紅）。
        # ⚠️ 它跟其他三個條件一樣**受送出閘門管**：拖數字的當下不會觸發下游重算。
        # ⚠️ **2026-09-07 就地更正（有意識的更正，不是漏刪 · 決策者：AI 總管）**：
        #    本行原寫 ~~「因為委派區塊讀的是 `_principal_twd()`（＝已套用值）」~~ ——
        #    **那是假的**。實測（AST）`_principal_twd` 在本檔的**呼叫點 0、裸參照 0**，
        #    也就是它目前是 **0 caller**，委派區塊一個字都沒讀它。
        #    → 這個 widget 現在**收得到值、但沒有任何下游消費它**。
        #    **不受閘門影響的真正原因**是更前面那一句：`_render_filter_form()` 只把值
        #    寫進 `_SK_APPLIED`，而委派區塊傳給舊模組的是 `_uniq_by_code(_holdings())`，
        #    整條路徑上沒有 principal 這個引數。
        #    ⛔ **本批不接線**：接上去等於改變委派區塊餵給舊模組的輸入
        #    （齊頭本金 vs 實際 `invest_twd`），那是行為變更，不是切換。已具名登記於 PR。
        _principal = st.number_input(
            "本金（TWD）",
            min_value=_PRINCIPAL_MIN, max_value=_PRINCIPAL_MAX,
            value=float(_cur.get("principal_twd", _DEFAULT_PRINCIPAL_TWD)),
            step=_PRINCIPAL_STEP,
            help=PRINCIPAL_HELP,
        )

    # ⚠️ `if _gate:` 必須在 `with` **之外**（送出鈕在 `yield` 之後才建立）。
    if _gate:
        st.session_state[_SK_APPLIED] = {
            "sigma": float(_sigma),
            "window_months": int(_window),
            "satellite_only": bool(_satellite_only),
            "principal_twd": float(_principal),
        }


def _render_no_holdings() -> None:
    """線框指定的空狀態 —— **三要素逐字取自線框**，這一段不要「潤飾」。

    線框 Tab 02：
      標題「尚未設定持倉」／缺什麼「還沒有任何保單或扣款標的」／
      去哪補「到『04 資產配置 › 保單與扣款標的』新增」／
      footer「補完後這裡會自動出現逐檔體檢」。

    ⚠️ **「去哪補」不照線框那句字面抄，走 `where_to_find('pf_add')`。**
    線框寫的是「保單與扣款標的」，而 SSOT（`ui/helpers/story_nav.py`）現行的區塊名是
    「➕ 加入與管理基金」—— **兩者不一致**。抄線框會產生第二份真相源，
    下一次區塊改名就指錯（本 repo 這個形狀已經死過三次）。
    **線框定的是「指到哪個分區」，不是「那個分區叫什麼名字」。**
    """
    empty_state(
        "尚未設定持倉",
        "還沒有任何保單或扣款標的",
        where=where_to_find("pf_add"),
        footer="補完後這裡會自動出現逐檔體檢。",
    )


# ══════════════════════════════════════════════════════════════════════
# 取數層 —— 一律走 `services/**` 的 public 入口
# ══════════════════════════════════════════════════════════════════════
# ⚠️ 下面每一個 `services.*` 都是**函式內 lazy import**，兩個理由：
#   (a) module load 不把計算層整包拖進來；
#   (b) 測試要 patch 得到**真正的定義處** —— module 層 `from X import f` 會把
#       函式綁進本檔的命名空間，之後 patch `X.f` 對本檔完全無效。
# 這也是本 repo 的家風（`services/fund_row.py`、`ui/helpers/fund_grp_health/rotation.py`
# 等既有 caller 都這樣寫）。


def _mj(fund: dict) -> dict:
    """該檔的 MoneyDJ 原始 payload（`portfolio_funds[i].moneydj_raw`）。

    ⚠️ 這是**讀既有 session 契約的欄位**，不是資料層呼叫（同 :func:`_holdings`）。
    鍵名由 `ui/helpers/portfolio/load.py::_FUND_INFO_KEYS` 定義，本檔只讀不寫。
    """
    _v = fund.get("moneydj_raw")
    return _v if isinstance(_v, dict) else {}


def _metrics(fund: dict) -> dict:
    """該檔的本地計算指標（`portfolio_funds[i].metrics`）。同 :func:`_mj`，只讀。"""
    _v = fund.get("metrics")
    return _v if isinstance(_v, dict) else {}


def _uniq_by_code(funds: list[dict]) -> list[dict]:
    """同一檔基金跨多張保單只算一次。

    ⚠️ **這不是可有可無的整理**：`portfolio_funds` 的主鍵是 `(policy_id, code)`
    （見 `ui/helpers/portfolio/load.py::reconcile_funds_with_ledgers`），
    同一檔基金買在兩張保單就會有兩筆。不去重的話「2 檔吃本金」可能其實只有 1 檔，
    而使用者無從得知 —— 那是一個**看不出來的錯誤數字**（§1）。
    既有實作（`ui/helpers/portfolio/health.py::compute_health_kpis`、
    `ui/components/mk_dashboard.py::render_mk_war_room`）都先去重，本檔對齊。
    """
    _seen: set[str] = set()
    _out: list[dict] = []
    for _f in funds:
        _c = str(_f.get("code", "") or "").strip().upper()
        if not _c or _c in _seen:
            continue
        _seen.add(_c)
        _out.append(_f)
    return _out


# ── 吃本金 ────────────────────────────────────────────────────────────
#: 四種落點。**直接對映 SSOT 回傳的 `alert_level`，本檔不自己定義任何門檻**
#: —— 門檻住在 `shared/signal_thresholds.py::NEAR_DIVIDEND_WARNING_PCT`（§3.3）。
_EAT_EATING: str = "eating"      # SSOT `alert_level == "red"`
_EAT_NEAR: str = "near"          # SSOT `alert_level == "yellow"`
_EAT_HEALTHY: str = "healthy"    # SSOT `alert_level == "green"`
_EAT_UNKNOWN: str = "unknown"    # SSOT 回 None / `"grey"` / 判定拋例外

_EAT_BY_ALERT_LEVEL: dict[str, str] = {
    "red": _EAT_EATING, "yellow": _EAT_NEAR, "green": _EAT_HEALTHY,
}


def _eating_verdict(fund: dict) -> "tuple[str, dict | None]":
    """單檔吃本金判定 → `(落點, SSOT 原始 dict | None)`。

    ⛔⛔ **這一段是本批最重要的一個決定，動它之前請先讀完。**

    走的是 `services.health.dividend.check_eating_principal_1y_mk` ——
    「**近一年含息總報酬率 vs 年化配息率**」，也就是線框那句「配息覆蓋率」講的東西。

    ⛔ **不要**改接 `ui/components/mk_dashboard.py::tag_principal_erosion`。
       它的名字（`Principal_Erosion`，直譯就是「吃本金」）看起來正是這張卡要的東西，
       **但它算的是另一件事**。該函式自己的 docstring 逐字寫著：

           ⚠️ v19.402 正名：本訊號實為「淨值連續下跌動能」，**非配息覆蓋/吃本金**。
           …與「吃本金」（含息總報酬 vs 配息率，見 tag_health_check B /
           dividend_safety）是**不同訊號**，**勿混用**。

       它實際做的是「近 3 個 22 日滾動**純 NAV** 報酬三段皆為負」——
       一檔**完全不配息**的基金淨值連跌三個月就會被它標成 `Eroding`，
       而那跟「配息有沒有在吃本金」毫無關係。
       **接錯的後果不是畫面壞掉，是一張標題正確、數字正確、意思完全錯的卡**，
       而使用者**看不出來**（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。
       那句「勿混用」會存在，代表以前有人混用過。

    **為什麼只把 `red` 算成「吃本金」，而不是「覆蓋率 < 1.0」**
    ------------------------------------------------------------
    SSOT 的 `eating_principal` 欄位確實就是「覆蓋率 < 1.0」，字面上更貼線框那句話。
    本檔仍取 `alert_level == "red"`，理由是**跨頁一致性**（§2.1）：
    `red` 是本 repo **既有的、production 正在用的**「這檔在吃本金」判準 ——
    `ui/tab_fund_grp_health.py::_eats_principal_flag` 逐字寫
    「red→吃本金；green/**yellow**→不吃（黃＝margin 薄但未吃）」，
    而 `services/switch_advisor.py` 一線、NAS 週報一線也都吃同一個 `status` 字串。
    若本頁改用「覆蓋率 < 1.0」，同一個組合在 ② 會顯示「3 檔吃本金」、
    在 ④ 換股顧問卻顯示「1 檔」—— **兩個都對，但使用者只會覺得系統壞了**。
    ⚠️ 黃燈那一段**沒有被丟掉**，它以「另有 N 檔接近警戒」出現在卡片說明裡
    （見 :func:`_eating_note`），不是靜默併進綠燈。

    ⚠️ **單檔判定失敗不拖垮整組**（與 `switch_advisor_section._underperf_by_code`
    同一處理）：例外收成 `_EAT_UNKNOWN` 並印到 stderr，**且會被計入卡片說明的
    「N 檔資料不足」**—— 不是靜默吞掉（§1）。
    **守衛**：`test_the_eating_card_accounts_for_every_fund_it_looked_at`
    （這句承重宣稱原本沒有守衛，2026-09-06 獨立稽核抓到後補上）。

    📌 **已登記的上游缺口：無配息基金會被說成「資料不足」，但它其實是「不適用」**
    （2026-09-06 稽核發現，**根因在 `services/**`，不在本檔邊界內，本批不修**）：
    `check_eating_principal_1y_mk` 在 `adr <= 0` 時直接 `return None`，於是累積型
    （不配息）基金落進 :data:`_EAT_UNKNOWN`，卡片說「N 檔**資料不足**」。
    **本組實測確認**（同日）::

        check_eating_principal_1y_mk(累積型 div=0)     → None          → unknown
        classify_eating_principal(6.0, 0.0)            → is_no_dividend=True,
                                                         is_data_missing=False

    —— **SSOT 內部分得出來**（`is_no_dividend`），只是在 `check_eating_principal_1y_mk`
    回傳前被折疊成 `None` 了，本檔拿不到那個區別。
    ⚠️ **不造成假綠也不造成假紅**（它不會被算成「沒吃本金」），
    **只是低估了我們的認知** —— 我們其實知道「這檔不配息，所以吃本金這個概念不適用」，
    畫面上卻說「不知道」。**要修得動 `services/**`，屬另案。**
    """
    from services.health.dividend import check_eating_principal_1y_mk
    try:
        _v = check_eating_principal_1y_mk(fund)
    except Exception as _exc:  # noqa: BLE001 — 單檔失敗不拖垮整組；但要留痕
        import sys as _sys
        print(f"[page_02_health] check_eating_principal_1y_mk 失敗 "
              f"({fund.get('code')}): {type(_exc).__name__}: {_exc}", file=_sys.stderr)
        return _EAT_UNKNOWN, None
    if not isinstance(_v, dict):
        # SSOT 回 None ＝「adr 缺 / tr1y 缺」→ 資料不足，**不是**「不吃本金」。
        return _EAT_UNKNOWN, None
    return _EAT_BY_ALERT_LEVEL.get(str(_v.get("alert_level")), _EAT_UNKNOWN), _v


def _eating_tally(funds: list[dict]) -> dict[str, int]:
    """四種落點各幾檔。key 為 :data:`_EAT_EATING` 等四個常數。"""
    _out = {_k: 0 for _k in (_EAT_EATING, _EAT_NEAR, _EAT_HEALTHY, _EAT_UNKNOWN)}
    for _f in funds:
        _bucket, _ = _eating_verdict(_f)
        _out[_bucket] += 1
    return _out


def _eating_note(tally: dict[str, int]) -> str:
    """吃本金卡的說明句。**把判準與所有沒進主數字的檔數都講出來。**

    ⚠️ 卡片上的主數字只有一個，但它背後有四種落點。**沒講出來的那三種，
    使用者會自己補一個（多半補成「其餘都健康」）** —— 那正是 §1 要防的事。

    ⚠️ 門檻**現場從 SSOT 讀**（`shared/signal_thresholds.py::NEAR_DIVIDEND_WARNING_PCT`），
    不在本檔抄一個數字（§3.3 反捏造）—— 抄了之後 SSOT 一改，畫面上的說明就開始說謊，
    而且**畫面與判定會各說各話**（判定走 SSOT、說明走抄本）。
    """
    from shared.signal_thresholds import NEAR_DIVIDEND_WARNING_PCT as _gap

    _bits = [f"判準：近一年含息報酬低於年化配息率超過 {_gap:.0f} 個百分點"]
    if tally[_EAT_NEAR]:
        _bits.append(f"另有 {tally[_EAT_NEAR]} 檔接近警戒（缺口在 {_gap:.0f}pp 內）")
    if tally[_EAT_HEALTHY]:
        _bits.append(f"{tally[_EAT_HEALTHY]} 檔覆蓋充足")
    if tally[_EAT_UNKNOWN]:
        _bits.append(f"{tally[_EAT_UNKNOWN]} 檔資料不足、未列入判定")
    return "；".join(_bits) + "。"


# ── 影子基金重疊 ──────────────────────────────────────────────────────
def _clean_holdings(raw: Any) -> list[dict]:
    """把一檔的 `top_holdings` 洗成「名稱 strip 後真的非空」的那些。

    ⛔⛔ **這不是防禦性程式碼潔癖，它擋的是一個已實測存在的假警示。**

    SSOT `services/portfolio_service.py::calc_holdings_overlap` 收集持股名時寫的是
    ``{(h.get("name") or "").strip().upper() for h in tops if h.get("name")}`` ——
    過濾條件 ``if h.get("name")`` 取的是 **strip 之前**的 truthy。於是名稱為
    **純空白**（`"  "`、`"\\t"`）時：該筆通過過濾 → 正規化成 `""` → 集合變成 `{""}`
    → **兩檔基金共享 `{""}` ⇒ Jaccard = 1.0 ⇒ 一對「相似度 1.00」的影子警示**。

    **本組 2026-09-06 於 `origin/main` 實跑確認這個缺陷還在**（指令與輸出見 PR 描述）::

        calc_holdings_overlap([
            {"code": "AAA", "top_holdings": [{"name": "   ", "pct": 10.0}]},
            {"code": "BBB", "top_holdings": [{"name": "\\t",  "pct": 10.0}]},
        ])["shadow_pairs"]                      # → [('AAA', 'BBB', 1.0)]

    `services/homogeneity.py::_has_dims` 早就把這件事就地寫下來了（「根因在 SSOT 端把
    純空白名當資料（既有行為，本批無權改）；修法屬另案裁決」），並在**它自己**的
    鏡像判定裡改用「strip **後**非空」。**本檔採同一條判準，套在自己的輸入上。**

    ⚠️ **修的是「我餵進去的東西」，不是 SSOT** —— 本批的檔案邊界只有兩個檔，
    `services/**` 一行都不准動（也不該由 UI 端去改一個多處共用的計算 SSOT：實測
    `origin/main` 上有 **4 個 production 呼叫點** —— `ui/components/mutual_exclusion.py`、
    `ui/helpers/fund_grp_health/ai.py`、`ui/helpers/fund_grp_health/correlation.py`、
    `ui/tab3_portfolio.py`，量測日 2026-09-06）。
    ⛔ **那 4 處都沒有這道防線** —— 本檔擋住的只有本頁自己，**不是全站**。

    📌 **這個數字本身有一段病史，留在這裡是因為它比數字有用**（2026-09-06 就地更正）：
    本段初稿寫的是「**8 個** caller 共用」，**那是沒查證就寫下的**。
    8 的來源是把稍早一次寬掃的**命中行數**當成呼叫點數 —— 那份輸出裡混著
    `services/homogeneity.py` 的 docstring 提及、函式定義本身、以及註解。
    實跑 `git grep -n 'calc_holdings_overlap(' origin/main -- '*.py'`
    再濾掉 `tests/` 與定義行，**只有 4 個**。
    ⚠️ **結論不受影響**（「不該由 UI 端去改共用 SSOT」在 4 或 8 都成立），
    **錯的是那個數字本身** —— 而這正是本節在指控上游的同一種病：
    **把「掃到幾行」當成「有幾個」。**
    一段在講「不要寫沒查過的數字」的程式碼，自己的數字必須先為真。
    餵一份「名稱其實是空白」的持股進去本來就是 garbage-in；把它擋在自己門口
    既不改別人的行為，也不需要別人先修好。
    ⚠️ **被剔掉的檔會被算進「N 檔缺持股資料」並顯示出來**，不是靜默縮小比對範圍
    （§1；`homogeneity.py` 模組 docstring 點名的正是「靜默縮小」這個病）。
    ⛔ **這不代表這張卡從此不會有假陽性**：本函式只擋掉「純空白名」這**一個**已知成因。
       持股清單被上游截斷成 1～2 筆時，兩檔共享那一筆一樣會算出 1.0 ——
       **那是這個指標本身的稀疏樣本問題，本檔沒有解，也不假裝有解。**
    """
    if not isinstance(raw, list):
        return []
    return [_h for _h in raw
            if isinstance(_h, dict) and str(_h.get("name") or "").strip()]


def _overlap_input(funds: list[dict]) -> "tuple[list[dict], list[str]]":
    """→ (`calc_holdings_overlap` 的輸入, **一維證據都沒有**的基金代碼)。

    持股／產業住在 `moneydj_raw.holdings`（既有 session 契約）。
    """
    _rows: list[dict] = []
    _blind: list[str] = []
    for _f in funds:
        _code = str(_f.get("code", "") or "?")
        _h = _mj(_f).get("holdings") or {}
        _tops = _clean_holdings(_h.get("top_holdings"))
        _sects = _h.get("sector_alloc") or []
        if not _tops and not _sects:
            _blind.append(_code)
        _rows.append({
            "code": _code,
            "name": _f.get("name") or _code,
            "top_holdings": _tops,
            "sector_alloc": _sects,
        })
    return _rows, _blind


def _overlap_result(funds: list[dict]) -> "tuple[dict | None, list[str]]":
    """影子基金重疊 → (SSOT 回傳值 | None, 缺持股/產業資料的代碼)。"""
    from services.portfolio_service import calc_holdings_overlap
    _rows, _blind = _overlap_input(funds)
    try:
        return calc_holdings_overlap(_rows), _blind
    except Exception as _exc:  # noqa: BLE001 — 留痕，不靜默
        import sys as _sys
        print(f"[page_02_health] calc_holdings_overlap 失敗："
              f"{type(_exc).__name__}: {_exc}", file=_sys.stderr)
        return None, _blind


def _shadow_formula() -> str:
    """影子基金的門檻與加權公式，**整句從 SSOT 組出來**（§3.3 反捏造）。

    ⚠️ 門檻 `0.70` 與加權 `0.6 / 0.4` 三個數字**一個都不准在本檔寫死**：
    它們是 `services/portfolio_service.py::calc_holdings_overlap` 真正在用的參數，
    抄一份到 UI 之後，SSOT 一改，**判定會跟著改、而畫面上的說明不會** ——
    使用者看到的門檻就和實際判定用的門檻不同，卻沒有任何東西會報錯。
    """
    from shared.signal_thresholds import (
        SHADOW_FUND_COSINE_WEIGHT_RATIO,
        SHADOW_FUND_JACCARD_WEIGHT_RATIO,
        SHADOW_FUND_THRESHOLD_RATIO,
    )
    return (f"門檻：相似度 ≥ {float(SHADOW_FUND_THRESHOLD_RATIO):.2f}"
            f"（持股 Jaccard × {float(SHADOW_FUND_JACCARD_WEIGHT_RATIO)}"
            f" ＋ 產業 cosine × {float(SHADOW_FUND_COSINE_WEIGHT_RATIO)}）")


def _pct(value: Any, digits: int = 1) -> str:
    """百分比欄位。**算不出來就是 `⬜`，不是 `0`、不是 `—`**（§1）。

    ⚠️ `0` 與「不知道」在一張表裡長得一模一樣，而它們的意思完全相反：
    「最大回撤 0%」是「這檔從沒跌過」，「最大回撤不知道」是「我們沒有它的淨值歷史」。
    """
    _v = _safe_num(value)
    return NOT_READY_MARK if _v is None else f"{_v:.{digits}f}%"


def _num(value: Any, digits: int = 2) -> str:
    """純數字欄位（Sharpe／覆蓋率）。同 :func:`_pct`，未知一律 `⬜`。"""
    _v = _safe_num(value)
    return NOT_READY_MARK if _v is None else f"{_v:.{digits}f}"


def _safe_num(value: Any) -> "float | None":
    """→ float 或 None。**NaN 也算 None**（NaN 會被 f-string 印成 `nan` 混進表裡）。"""
    try:
        _v = float(value)
    except (TypeError, ValueError):
        return None
    return None if _v != _v else _v


def _table_rows(funds: list[dict]) -> list[dict]:
    """逐檔體檢表的列。**key 就是 :data:`HEALTH_TABLE_COLUMNS`，順序一致。**

    每一欄的來源（**全部走 `services/**` 的 public 入口或既有 session 契約**）::

        代碼      portfolio_funds[i].code                     （session 契約）
        名稱      portfolio_funds[i].name                     （session 契約）
        幣別      .currency ／ .moneydj_raw.currency          （session 契約）
        近 1 年   services.fund_total_return.compute_1y_total_return()
        Sharpe    .metrics.sharpe                             （session 契約）
        最大回撤  .metrics.max_drawdown                       （session 契約）
        配息覆蓋  services.health.dividend.check_eating_principal_1y_mk() → coverage
        五桶評等  **無來源** —— 見下
        資料日期  services.fund_row.nav_freshness_label(.moneydj_raw.nav_date)

    ⛔ **「五桶評等」整欄恆為 `⬜`，這是刻意的，不是還沒接。**
       線框寫的「五桶評等」在本 repo 是**總經**概念（`shared/macro_buckets.py`：
       長期／中期／短線／拐點／新聞），**沒有逐檔基金版本**。逐檔真正存在的是
       `services/health/grade.py::compute_4d_health` 的 **4D/5D Grade（A～F）**——
       維度不同、級距不同、名字不同。**把 4D Grade 印在「五桶評等」欄底下，
       就是本頁 `_eating_verdict` docstring 講的那種錯**（名字對得上、語意不同、
       使用者看不出來）。欄位本身**不刪**（線框是客戶拍板的，增刪欄位屬客戶 gate），
       改由表下方一句 caption 說明為什麼是空的。
       → 該用哪個評等**已送客戶、尚未答覆**；在那之前這一欄誠實留白。

    ⚠️ **`check_eating_principal_1y_mk` 在本頁被呼叫兩次**（一次給警示卡、一次給本表）。
       它是純函式、同輸入同輸出，所以**不會不一致**；沒有收成一份共用結果，是因為
       兩塊各自包在 `safe_section()` 裡刻意隔離 —— 共用一份中間結果會讓其中一塊的
       失敗連坐另一塊，那正是區塊級隔離要防的事。持股數量級是「使用者手上的基金」，
       這個取捨划算；**若日後真的變慢，正解是在 `services/**` 那一層加快取，不是拆掉隔離。**
    """
    from services.fund_row import nav_freshness_label
    from services.fund_total_return import SRC_NONE, compute_1y_total_return

    _rows: list[dict] = []
    for _f in funds:
        _m = _metrics(_f)
        _raw = _mj(_f)

        # 近 1 年：算不出來時**印 SSOT 自己給的理由**（例如「僅 45 天資料，不足以推算一年」），
        # 那比一個 `⬜` 更有用，而且那句話是 SSOT 產的、不是本檔編的（§2.2）。
        try:
            _tr1y, _tr1y_src = compute_1y_total_return(_f)
        except Exception as _exc:  # noqa: BLE001 — 單檔失敗不拖垮整張表；留痕
            import sys as _sys
            print(f"[page_02_health] compute_1y_total_return 失敗 "
                  f"({_f.get('code')}): {type(_exc).__name__}: {_exc}", file=_sys.stderr)
            _tr1y, _tr1y_src = None, ""
        # 算不出來時印 SSOT 自己給的**理由**（例如「（僅 45 天資料，不足以推算一年）」），
        # 那比一個 ⬜ 有用得多，而且那句話是 SSOT 產的、不是本檔編的（§2.2 provenance）。
        # ⚠️ 但 `SRC_NONE`（就是一個「—」）**不帶任何資訊**，印它只會讓這一格
        #    和同一列其他「不知道」的格子長得不一樣，卻是同一個意思 → 統一回 ⬜。
        #    比對走 SSOT 常數，**不在本檔寫死那個破折號**（§3.3）。
        _src_txt = str(_tr1y_src or "").strip()
        _tr1y_cell = _pct(_tr1y) if _safe_num(_tr1y) is not None else (
            NOT_READY_MARK if not _src_txt or _src_txt == SRC_NONE else _src_txt)

        _, _eat = _eating_verdict(_f)
        _nav_label, _ = nav_freshness_label(
            _raw.get("nav_date") or _f.get("nav_date"))

        _rows.append({
            "代碼": str(_f.get("code", "") or NOT_READY_MARK),
            "名稱": str(_f.get("name") or _f.get("code") or NOT_READY_MARK),
            "幣別": str(_f.get("currency") or _raw.get("currency")
                        or NOT_READY_MARK).strip() or NOT_READY_MARK,
            "近 1 年": _tr1y_cell,
            "Sharpe": _num(_m.get("sharpe")),
            "最大回撤": _pct(_m.get("max_drawdown")),
            "配息覆蓋": _num((_eat or {}).get("coverage")),
            # ⛔ 恆為 ⬜ —— 理由見本函式 docstring。**不要拿 4D Grade 填進來。**
            "五桶評等": NOT_READY_MARK,
            "資料日期": str(_nav_label),
        })
    return _rows


def _render_health_score() -> None:
    """區塊 2｜組合健康總分（**全寬**）。**本批仍為灰態，這是刻意的。**

    線框：「72 ／ 100　五桶評等加權。下方三張卡是扣分最重的三項，點進去看逐檔。」

    ⛔ **不畫那個 72。** 線框裡的數字是**示意**，不是資料。填一個看起來合理的分數
    正是 §1 點名最危險的那種造假 —— 它會被使用者拿去做決定，而且完全看不出是假的。

    ⛔ **本批刻意不接，原因不是「還沒排到」，是「來源本身未定」：**
    線框把總分定義成「**五桶評等**加權」，而本 repo 的「五桶」是**總經**概念
    （`shared/macro_buckets.py`：長期／中期／短線／拐點／新聞），**不是逐檔基金評等**。
    逐檔真正存在的評等是 `services/health/grade.py::compute_4d_health` 的
    **4D/5D Grade（A～F）**—— 名字、維度、級距全都不同。
    **拿 4D Grade 加權出一個數字，再掛在「五桶評等加權」底下，就是 `Principal_Erosion`
    那一類錯誤的翻版**（名字對得上、語意不同、使用者看不出來）。
    → 該用哪個定義**屬業務規格，已送客戶、尚未答覆**（§-1.5 v3 `03`-2 ②），本批不自行拍板。

    ⚠️ **指路已於 2026-09-06 就地更正**：舊版指向「診斷條件」，那在骨架批為真
    （當時只有 Form 是完整的）；本批之後同一頁已有三塊接上真資料，
    那句話會把使用者送去一個什麼結論都沒有的地方。現行指路指向**同一頁下方真的能看的東西**。
    """
    st.markdown("#### 組合健康總分")
    not_ready(_SCORE_PENDING_NOTE,
              where=_pending_where("下方「逐檔體檢表」可先逐檔看"))


def _render_alert_cards() -> None:
    """區塊 3｜三張卡（3 欄自適應網格）。**本批接上兩張，第三張維持灰態。**

    線框 Tab 02 三張卡逐字：
      「吃本金警示／2 檔／配息覆蓋率低於 1.0，實際在配回本金。」（業務警示）
      「衛星連續落後／1 檔／連兩季落後對比基準（SPY / QQQ）。」（業務警示）
      「影子基金重疊／相似度 0.78／兩檔持股高度重疊，分散效果打折。」（業務警示）

    ⚠️ **線框把三張都標成「業務警示」，那是因為線框在示範「有壞消息時長什麼樣」。**
    真接上之後，**沒有壞消息就該是 `STATE_OK`**，不是永遠紅著 ——
    三態的選擇由**資料**決定，不是由線框的示意圖決定（鐵則 03：`state` 決定視覺，不是文案）。

    ⛔ **本批不畫「2 檔」「1 檔」「0.78」那三個示意值** —— 卡片上的數字**一律由 SSOT 算出**，
       算不出來就走灰態。線框的數字是版面示意，不是資料。

    **「衛星連續落後」為什麼還是灰的（這一段是本批的裁決，不是漏做）**
    ----------------------------------------------------------------
    「連兩季落後基準」在本 repo **有**一份語意完全相符的實作 ——
    `ui/components/mk_dashboard.py::tag_benchmark_lag`（衛星 q1、q2 兩季季報酬皆低於
    基準同期 → `Lag`）。**但它接不進來，兩道各自獨立的閘門都擋著**：

    1. **客戶裁決**：波段觀測站（`mk_dashboard.py`）的搬遷是**本頁上線之後的獨立批次**
       （見本檔模組 docstring），本批不碰；`tests/test_wf02_health_skeleton.py::
       test_the_page_does_not_delegate_to_the_old_tab` 也明文擋 `mk_dashboard` 的 import。
    2. **層級**：它是 L3 UI，而它要的基準序列來自 L1
       `repositories/macro/yf.py::fetch_benchmark_close`（本檔禁 import `repositories/**`）。

    ⛔ **而 `services/**` 底下沒有語意相符的替代品，這一點本組實測過**：
       `services/benchmark_compare.py::excess_return` 算的是「**近 1 年**純價格超額報酬」，
       **不是**「連續兩季」；`services/capture_ratio.py` 算的是上／下檔捕捉率。
       **把 1 年超額報酬接到一張寫著「連兩季落後」的卡上，就是 `Principal_Erosion`
       那個錯誤換一個方向再犯一次** —— 名字對、數字真、意思錯。
       ⚠️ 實測：`fetch_benchmark_close` 在 `origin/main` 上的**唯一** production caller
       就是 `ui/components/mk_dashboard.py` 本身。
    → **維持灰態，並在灰態文案裡誠實說明「現在要看這件事該去哪」**（那個地方現在真的看得到：
      `app.py` 的 ④ 分頁呼叫 `render_portfolio_tab()` → `render_mk_war_room()`，本組實測過接線）。
    """
    _funds = _uniq_by_code(_holdings())

    # ── 卡 1：吃本金 ──────────────────────────────────────────────
    _tally = _eating_tally(_funds)
    _n_eat = _tally[_EAT_EATING]
    _judged = _n_eat + _tally[_EAT_NEAR] + _tally[_EAT_HEALTHY]
    if _judged == 0:
        # 一檔都判不動 ＝ 沒有結論，**不是**「0 檔吃本金」。
        # 印「0 檔」會讓使用者以為已經檢查過而且沒事 —— 那是最貴的一種假綠燈（§1）。
        _eat_card: dict[str, Any] = {
            "title": "吃本金警示", "state": STATE_NOT_READY,
            "note": (f"{len(_funds)} 檔都算不出「近一年含息報酬」或「年化配息率」，"
                     "**無法判定**（不是判定為沒有吃本金）。"),
            "where": where_to_find("diag"),
        }
    else:
        _eat_card = {
            "title": "吃本金警示", "value": f"{_n_eat} 檔",
            "state": STATE_BUSINESS if _n_eat else STATE_OK,
            "note": _eating_note(_tally),
        }

    # ── 卡 2：衛星連續落後（維持灰態，理由見本函式 docstring）────────
    _lag_card = {
        "title": "衛星連續落後", "state": STATE_NOT_READY,
        "note": _LAG_PENDING_NOTE,
        "where": where_to_find("portfolio"),
    }

    # ── 卡 3：影子基金重疊 ────────────────────────────────────────
    _ov, _blind = _overlap_result(_funds)
    _pairs = list((_ov or {}).get("shadow_pairs") or [])
    if _ov is None or (_ov.get("matrix") is None and not _pairs):
        # 少於 2 檔、或全部缺持股與產業資料 → 沒得比，誠實說「沒得比」。
        _shadow_card: dict[str, Any] = {
            "title": "影子基金重疊", "state": STATE_NOT_READY,
            "note": ("需要至少兩檔、且有持股或產業資料才比得出重疊度；"
                     + (f"目前 {len(_blind)} 檔缺這兩種資料。" if _blind
                        else f"目前只有 {len(_funds)} 檔可比。")),
            "where": where_to_find("diag"),
        }
    else:
        _top = _pairs[0] if _pairs else None
        _note_bits = [_shadow_formula()]
        if _top:
            _note_bits.append(f"最高一對 {_top[0]}／{_top[1]}：{float(_top[2]):.2f}")
        if _blind:
            # §1：被排除的檔要具名帶出來，不得靜默縮小比對範圍
            # （`services/homogeneity.py` 模組 docstring 點名的正是這個病）。
            _note_bits.append(f"{len(_blind)} 檔缺持股／產業資料未列入比對"
                              f"（{'、'.join(_blind[:3])}{'…' if len(_blind) > 3 else ''}）")
        _shadow_card = {
            "title": "影子基金重疊",
            "value": f"{len(_pairs)} 對",
            "state": STATE_BUSINESS if _pairs else STATE_OK,
            "note": "；".join(_note_bits) + "。",
        }

    render_cards([_eat_card, _lag_card, _shadow_card])


def _render_health_table() -> None:
    """區塊 4｜逐檔體檢表（**全寬 + 橫向捲動**）。**本批接上真資料。**

    線框：「欄位多，全寬橫向捲動」「不畫空表格外框」。

    ⚠️ **走 `wide_table()` 而不是 `st.dataframe()`**：空資料不畫空框這件事，
    只有收在唯一的大表入口才有機械上的著力點（`ui/helpers/ia/layout.py` 的 docstring）。

    ⚠️ **這張表不得放進 `render_cards()` 的欄位裡**（9 欄在 1/3 寬會被壓成無法閱讀），
    所以它是頁面層級的直接呼叫，不在任何網格內 ——
    `wide_table` 自己的 docstring 就地寫著「不要把本函式放進 `card_row()` 的欄位裡」。

    ✅ **骨架批那行「欄位名 caption」已依登記刪除**：它當時的作用是「先告訴使用者
    這張表會有什麼」（因為表是空的）；真資料接上後表頭會講同一件事，
    留著就變成鐵則 04 要禁的冗餘占位。
    連帶 `test_the_per_fund_table_keeps_the_nine_columns_from_the_wireframe`
    的「畫面上看得到每一欄」那半**已改成驗真表頭**，不是把斷言刪掉。
    """
    st.markdown("#### 逐檔體檢表")
    _rows = _table_rows(_uniq_by_code(_holdings()))
    _drawn = wide_table(
        _rows,
        empty_title="逐檔體檢還沒有可顯示的列",
        empty_missing="目前的持股都還沒有可用的淨值或指標資料。",
        empty_where=where_to_find("diag"),
        hide_index=True,
    )
    if _drawn:
        # ⚠️ 這一句**不是**骨架批那行冗餘 caption 的復活：它講的是表頭講不出來的事
        # —— 「五桶評等」整欄為何恆為 ⬜（§1：不解釋的空欄會被讀成「這檔沒評等」）。
        st.caption(
            f"「五桶評等」整欄顯示 {NOT_READY_MARK} —— 線框這一欄的評等定義未定"
            "（本站「五桶」是總經概念，逐檔評等是另一套 4D Grade），"
            "已送客戶確認；**不拿別的評等填進來充數**。")


def _render_delegated_sections() -> None:
    """區塊 5｜**路線 (A) 委派區** —— 原封不動呼叫既有舊模組的 public 入口。

    客戶 2026-09-06：「新頁只做版面呈現與互動排版，**寫入邏輯原封不動呼叫既有舊模組**。」
    本函式**不重新實作任何計算**，只負責：拿到持股 → 傳給既有 public 入口 → 隔離失敗。

    接了哪兩支、為什麼是這兩支，見 :data:`DELEGATED_ENTRIES`；
    **沒接的三組與具名理由**見 :data:`DEFERRED_ENTRIES`；
    **不准接的兩支**見 :data:`DELEGATION_BLACKLIST`。

    **傳什麼進去 —— 這一段是本函式唯一的實質判斷，寫清楚**
    ------------------------------------------------------
    兩支都吃「rich fund dict list」。舊 ② 傳的是
    `_build_fund_dict(r["_fund_raw"], r["code"], principal_twd)` 的產物，
    而那個 helper 的 docstring **逐字自陳**：「把 `_auto_fetch_moneydj` 回傳的 raw dict
    **包成 portfolio_funds 標準結構**」。

    也就是說 —— **舊 ② 是把它的資料轉成本頁 `portfolio_funds` 的形狀，才餵進去的。**
    本頁的 `_holdings()` **已經就是那個形狀**，所以**直接傳，不需要 adapter**：

        `_build_fund_dict` 產出  code / name / series / dividends / metrics /
                                 moneydj_raw / risk_metrics / currency / loaded / invest_twd
        `portfolio_funds` 契約   name / series / dividends / metrics / moneydj_raw /
                                 risk_metrics / is_core / currency（`ui/helpers/portfolio/load.py::
                                 _FUND_INFO_KEYS`）＋ code / loaded / invest_twd（同檔 sync）

    ⚠️ **唯一的實質差異，據實寫明、不掩蓋**：`_build_fund_dict` 把每檔的 `invest_twd`
    **統一覆寫成同一個 `principal_twd`**（那是「假設每檔都投入相同金額才能比較」的
    刻意設計）；而 `portfolio_funds` 帶的是**使用者每檔真正投入的金額**。
    ~~→ 對本批接的這兩支**沒有影響**（實測兩支都不讀 `invest_twd`：~~
      ~~`render_fund_checkup` 走 `metrics`／`moneydj_raw`／`series`，~~
      ~~`render_mutual_exclusion_section` 走持股與相關性）。~~

    ⛔ **2026-09-07 就地更正：上面那句對 `render_fund_checkup` 是假的。
    有意識的更正，不是漏刪**（決策者：**AI 總管**；依據：**本組實測**，非轉述）::

        grep -n "invest_twd" ui/helpers/fund/checkup.py   # → 11 處命中

    `render_fund_checkup` **確實會讀 `invest_twd`**，而且它驅動使用者看得到的東西：
    `_compute_fund_health_kpis` 的月配息、`build_checkup_dataframe` 的
    **原幣本金 ／ 月配 TWD ／ 年配 TWD 三欄**，以及健診卡上那句
    「本金 N TWD ÷ 12 月」。`ui/tab3_portfolio.py` 就地寫著同一件事
    （「`invest_twd` 會驅動可見輸出（原幣本金 / 月配息 / 年配息三欄 + 健診卡文案）」）
    —— **同一個 repo 裡兩份記錄互相矛盾，本行是錯的那一份。**
    ⚠️ `render_mutual_exclusion_section` 那半句**仍然成立**（實測 0 命中）。

    **這個差異的實際後果，據實寫明（它不是 bug，但它是一個功能面的變化）**：
    舊 ② 餵的是 `_build_fund_dict(..., principal_twd)` ——「**每檔硬寫同一個本金**」
    的**齊頭模擬基準**；新 ② 餵的是 `portfolio_funds` ——「**使用者每檔實際投入**」。
    也就是說 ② 切換之後，**全站不再有任何地方畫齊頭本金版的基金體檢 PK**
    （④ 那一份在 WP-G 已經移除，它當時的理由就是「同型的齊頭模擬版在 ② 仍在」，
    而那句話自本次切換起不再成立）。
    ⛔ **本批不補**：要補等於把 `_build_fund_dict` 接回來，那是委派清單的變更、
    不是切換，且會連帶把 `_render_investment_calc` 的那個張力提前引爆。
    **已寫進 PR 描述具名登記。**
    ⛔ **但下一批接 `render_fund_grp_health_extras` 時這個差異會變成真的**
      —— 它底下的 `_render_investment_calc` 就是吃那個本金算「可申購單位／月配 TWD」。
      **那正是 :data:`DEFERRED_ENTRIES` 第一條擋著它的原因，不要以為那只是缺個 widget。**

    ⚠️ **`_uniq_by_code` 一定要先跑**：`portfolio_funds` 的主鍵是 `(policy_id, code)`，
    同一檔基金跨兩張保單會出現兩次；不去重的話「互斥避險」會拿同一檔跟自己比相關性，
    必然算出 1.0 的假警訊。
    """
    _funds = _uniq_by_code(_holdings())
    if not _funds:
        return

    # ⭐ **標題與分隔線一定要畫在閘門【之前】,這不是排版偏好,是本 repo 拍板過的判準。**
    #    2026-08-28 客戶 Q1「三問判準」的結論逐字寫在
    #    `ui/helpers/fund_grp_health/backtest_section.py` 的就地註解裡:
    #    「守衛寫在標題前面,使用者看不到任何痕跡;寫在後面,他看到標題和一句灰字說明。」
    #
    # ⚠️ **第一版把標題留在閘門後面,CI 當場抓到,值得記一筆**:
    #    `tests/test_wf02_health_skeleton.py` 的 `_units()` 以 `#### 標題` 切段,
    #    閘門關著時標題不會畫 ⇒ 灰字**被歸到上一個區塊「逐檔體檢表」名下**
    #    ⇒ `test_wired_blocks_show_real_content_when_the_data_is_there[逐檔體檢表]`
    #    紅了,訊息是「資料齊全時仍是灰態 —— 那是退化」。
    #    **那條守衛沒有錯,是我把灰字掛到了別人的區塊上。** 標題移到閘門前面之後,
    #    灰字落在它自己的單位裡,那條守衛**一個字都不必改**就恢復綠燈。
    st.divider()
    st.markdown("#### 🔬 逐檔健診與互斥分析")

    # ── Checkbox Gate ───────────────────────────────────────────────────
    # ⛔ **這一段是本區塊唯一的進入條件，理由整段寫在 :data:`DELEGATE_GATE_LABEL` 上方。**
    #    一句話：舊 ② 與本頁委派**同一批**舊模組，其中三支會畫 `st.plotly_chart`，
    #    而 `plotly_chart` **每次呼叫都註冊 element id** ⇒ 同一個 run 畫兩次就拋
    #    `StreamlitDuplicateElementId`。CI 沒有持倉、也不會按舊 ② 的「🩺 開始健診」，
    #    **所以測試永遠是綠的，只有真實使用者會踩到。**
    #
    # ⚠️ **`st.checkbox` 必須是這個 `if` 的唯一運算元** —— 不要寫成
    #    `if not X and st.checkbox(...)` 這類布林短路：那會讓 gate 在某些情況下
    #    被跳過，而靜態守衛看到的仍然是一個「有 checkbox 的 if」。
    #    守衛 `test_the_gate_is_the_only_way_in` 對這一點是 fail-closed 的。
    _open = st.checkbox(DELEGATE_GATE_LABEL, value=False, help=_delegate_gate_help())
    if not _open:
        # ⚠️ 指路指向**舊 ② 分頁**，不是指向上面那個勾選框 —— 內容現在真的在那裡，
        #    而「勾下去」是撞的那一刻、不是解法（見 :data:`DELEGATE_GATE_LABEL` 第 3 點）。
        not_ready(
            f"逐檔健診與互斥分析**尚未載入**。這一區與舊「{tab_label('health')}」分頁"
            "是同一份程式碼；兩邊同時載入會撞 Streamlit 的重複元件 ID，"
            f"畫面上會出現紅色錯誤塊。勾選上方「{DELEGATE_GATE_LABEL}」會**立刻載入本頁這一份**"
            "（舊分頁若已跑過健診，那一刻就會撞）。",
            where=f"{where_to_find('health')}（該分頁已經在畫同一批圖表）")
        return

    # ⛔ **lazy import，且逐支具名** —— 不是 `from ui.helpers import fund_grp_health`
    #    那種整包委派。整包委派會把黑名單那兩支（同一個資料夾裡的
    #    `switch_advisor_section`）一起帶進射程，而它們打開就寫 Google Sheet。
    #    守衛拿 `DELEGATED_ENTRIES` 對本檔實際 import 到的符號做**精確集合相等**比對。
    from ui.components.mutual_exclusion import render_mutual_exclusion_section
    from ui.helpers.fund.checkup import render_fund_checkup
    from ui.helpers.fund_grp_health.ai import _render_ai_cross_fund_evaluation
    from ui.helpers.fund_grp_health.backtest_section import (
        render_allocation_backtest_section,
    )
    from ui.helpers.fund_grp_health.correlation import _render_correlation_matrix
    from ui.helpers.fund_grp_health.dividend import _render_dividend_matrix
    from ui.helpers.fund_grp_health.risk import _render_oversold_badges

    # ⚠️ 這句 caption 是**誠實揭露**，不是行銷詞：本區塊的內容與舊 ② 同源同碼，
    #    使用者若發現這裡跟舊 ② 長得一樣，那是對的、是刻意的。
    st.caption("本區直接沿用既有的健診模組（**與舊分頁同一份程式碼、同一條資料路徑**），"
               "版面走新版動線。")

    # 每一支各自包 `safe_section` —— 一支失敗不連坐另一支，也不連坐本頁其他區塊。
    # ⚠️ `safe_section` **不吞例外**（§1）：走 `system_error()` 顯式紅框 ＋ traceback。
    safe_section("基金體檢", lambda: render_fund_checkup(_funds, expanded=True))
    safe_section("持倉互斥避險", lambda: render_mutual_exclusion_section(_funds))

    # ── 以下五塊拆自 `render_fund_grp_health_extras`，**只接線框判給 ② 的那些** ──
    #    ⛔ 屬 ③ 的五塊（投資試算／TER＋持股／Bollinger／個股新聞／三率穿透）
    #       一支都沒有接，清單見 :data:`MOVED_TO_PAGE_03`。
    #    ⚠️ 順序照線框 §04「留 ②」那一列的敘述走：先跨檔矩陣、再風險、再輪動、最後 AI。
    safe_section("真實收益矩陣", lambda: _render_dividend_matrix(_funds))
    safe_section("持股相關性矩陣", lambda: _render_correlation_matrix(_funds))
    safe_section("−2σ 超跌警示", lambda: _render_oversold_badges(_funds))
    # 🔁 配置回測 —— 線框 §04「留 ② 原位」，標註「教學非建議」。
    # ⚠️ 它吃的是 rich fund dict（含 `series` 原幣 NAV ＋ `currency`），
    #    `<2 檔有序列` 時它自己會印標題 ＋ 一句灰字說明缺什麼，**不會靜默消失**。
    safe_section("配置回測", lambda: render_allocation_backtest_section(_funds))
    # ⑫ AI 跨檔評論 —— 線框「留 ②（按鈕觸發）」。
    # ⚠️ **這一支是本頁唯一還會碰到寫入 primitive 的委派**
    #    （Gemini API ＋ `repositories/ai_cache.py` 的本機原子寫）。
    #
    # ~~⭐ 它與被拿掉的「輪動配對」差在哪 —— 這一段是實測，不是推論：~~
    # ~~  輪動配對  `to_csv(...)` 是 `st.download_button(...)` 的引數 ⇒ 渲染期無條件求值。~~
    # ~~  AI 跨檔   `ai_cache.save(...)` 的外層守衛是 `try` → `if run` → `with st.container()`，~~
    # ~~            而 `run = st.button(...)`；假 streamlit（`_Rec`）對 `button` 回 `False`~~
    # ~~            ⇒ 該分支不執行。~~
    # ~~  ⛔ 若日後假 streamlit 改成 `button` 回 `True`，這一支會變成第二顆紅燈。~~
    #
    # ⚠️ **2026-09-07 更正：上面整段機制是錯的。有意識的更正，不是漏刪。**
    #    **決策者：AI 總管（依獨立稽核實跑四個變體）**。稽核實測：**`button=True` 仍不紅**。
    #    ⇒ 我原本寫的「靠 `_Rec.button` 回 `False` 擋住」**不成立**，
    #      連帶那句「改回 `True` 就會變第二顆紅燈」也是錯的。
    #
    # ✅ **真正先擋住的是更前面的一道早退**（本組 AST 覆核 `ai.py` 確認）：
    #    `_render_ai_cross_fund_evaluation` 在呼叫 `render_ai_summary_widget` **之前**
    #    就有 `if not _key: st.caption("⬜ 未設定 GEMINI_API_KEY…"); return`
    #    ⇒ **CI 沒有 `GEMINI_API_KEY`，所以三個 `st` 呼叫之後直接返回，連 button 都走不到。**
    #
    # ⚠️ **據實講清楚這個結論靠什麼成立**：它**依賴「CI 環境沒有 `GEMINI_API_KEY`」**，
    #    而那不是本檔能保證的事。⇒ **若哪天 CI 設了那把 key，這一支就會往下走**，
    #    屆時 `ai_cache.save`（`tempfile.mkstemp` ＋ `os.replace` 的**本機磁碟**寫，
    #    **不是** Google Sheet）會不會被碰到，**必須重驗**。
    #    ⛔ 真的紅了就**照裁決移進 `DROPPED_FOR_ZERO_WRITE`，不要改守衛**。
    safe_section("AI 跨檔評論", lambda: _render_ai_cross_fund_evaluation(_funds))


def render_holdings_health() -> None:
    """渲染「② 持倉體檢」整頁。

    ~~⚠️ **本批尚未接進 `app.py`**（客戶明令舊 ② 不動、不接線、不下架），~~
    ~~所以現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。~~
    ~~接線是下一批的事。~~

    ⚠️ **2026-09-07 事實更正：上段已過期，本函式現在有 production caller。**
    **有意識的更正，不是漏刪**（決策者：**AI 總管**，依獨立稽核指出）。

    ~~**實測**：`app.py` 的 `with tab_health:` 呼叫本函式。~~
    ⛔ **2026-09-07 同日再更正（第二次）：「有 caller」這半仍然為真，
    但「是哪一格」講錯了**（決策者：**AI 總管**，依獨立稽核實測）。
    **實測（`origin/main` `c6b4d1b`）**：呼叫本函式的是
    **`with tab_preview_health:`（[新] 並行預覽那一格）**；
    **`tab_health` 掛的是舊 ② `render_fund_grp_health_tab()`** ——
    客戶 2026-09-07 雙軌原則：舊 Tab 原位保留、新 View 並行掛新 Tab。
    守衛 `tests/test_wf02_health_golive.py::test_app_mounts_the_new_health_view`
    **兩格都釘**（新頁沒接出去 → 紅；舊頁被覆蓋 → 也紅）。
    ⚠️ **舊表述在寫下當天是真的**（那時 `tab_health` 確實掛本檔），
    **被推翻的是它的前提** —— #814 在幾分鐘後合併改成了雙軌。

    ⛔ **同一句「沒有 production caller」在 `ui/views/page_05_settings.py` 也有一份**
    —— **本批不碰那個檔**（另一組正在動它），已於本批 PR 描述具名登記。
    ⚠️ 該檔的落點與本檔**不同**（⑤ 現在是 `tab_settings` → `render_settings_diag_tab`、
    `tab_preview_settings` → `render_settings_and_diagnostics`），**由那一組現場實測，
    不要照抄本段的結論。**

    ⚠️ **區塊之間走 `safe_section()` 隔離**：`st.tabs` 是單次 run 渲染全部分頁，
    任一區塊拋未捕捉例外會**中止整個 script**，其後所有分頁空白。
    `app.py` 已有分頁級的 try，但那是「一頁失敗不連坐其他頁」；
    區塊級隔離要的是「一塊失敗不連坐同一頁的其他塊」。
    ⚠️ `safe_section` **不吞例外**（§1）：它走 `system_error()` 顯式紅框 ＋ traceback。
    """
    st.markdown(f"## {tab_label('health')}")
    render_story_nav("health")
    # 線框 Tab 02 的職責宣告，逐字。**只診斷不決策**這半句是邊界，不是文案。
    # ⚠️ **指 `portfolio`（整個 ④），不是 `pf_add`。**
    #    這句同時涵蓋「換什麼」與「怎麼配」兩件事：`switch`（🎯 換股顧問）只接得住前者，
    #    `pf_add`（➕ 加入與管理基金）**兩者都不是** —— 那裡是去新增標的，不是去換或去配。
    #    線框原文寫的就是「在 **04**」（整個分頁），指整個 ④ 最忠於它。
    # ⚠️ 本檔另一處 `where_to_find('pf_add')`（空狀態）**是對的、不要一起改**：
    #    那裡確實是要使用者去加基金。**同一個 key 用在兩處，語意不同。**
    st.caption("回答一個問題：**我手上這些，哪一檔出問題了？** "
               f"只診斷、不決策 —— 要換什麼、怎麼配，在 {where_to_find('portfolio')}。")

    safe_section("診斷條件", _render_filter_form)

    if not _holdings():
        # 沒有持倉時，下面三塊沒有任何東西可以診斷 —— 直接走空狀態，
        # **不要**把三塊各印一次灰（那會變成四份在講同一件事的灰字）。
        safe_section("尚未設定持倉", _render_no_holdings)
        return

    # 🧾 ① 結論 —— **排在所有依據之前**（同 ① 的四層閱讀順序）。
    # ⚠️ 位置在 `if not _holdings(): return` **之後**：沒有持倉時空狀態**取代**全部內容，
    #    不得再多印一句結論（`test_no_holdings_hides_the_diagnosis_blocks_entirely` 的精神）。
    safe_section("結論", _render_conclusion)
    safe_section("組合健康總分", _render_health_score)
    safe_section("警示卡片", _render_alert_cards)
    safe_section("逐檔體檢表", _render_health_table)
    # 路線 (A) 委派區 —— 放在**最後**，理由不是隨手排的：
    # 線框 Tab 02 釘死的順序是「總分 → 三張卡 → 逐檔表」，那三塊是本頁自己的版面，
    # 委派進來的是**既有模組自帶的版面**（它們自己會 `st.divider()` + 下標題）。
    # 夾在中間會把線框指定的動線切斷；接在後面則是「線框的四塊 ＋ 沿用的深度分析」。
    _render_delegated_sections()
