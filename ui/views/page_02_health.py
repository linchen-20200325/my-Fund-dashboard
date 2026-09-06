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
2      組合健康總分                          **全寬**
3      吃本金警示／衛星連續落後／影子基金重疊    3 欄自適應網格
4      逐檔體檢表（9 欄）                    **全寬 + 橫向捲動**
–      尚未設定持倉                          空狀態三要素（取代 2～4）
===== ================================== ==========================================

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

⚠️ **本頁本批尚未接進 `app.py`。** `app.py` 的 `with tab_health:` 仍呼叫舊的
   `render_fund_grp_health_tab()`，客戶明令「舊 ② 這批不動、不接線、不下架」。
   接線是下一批的事 —— 骨架先上線、CI 綠、再分批填內容。

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
# ⚠️ 刻意**不**沿用舊 ② 的鍵：舊頁依方針第 3 條仍在磁碟上、且仍接在 `app.py`，
#    共用鍵會讓兩套 View 互相覆寫對方的狀態，而 payload 形狀並不相同。
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
DELEGATED_ENTRIES: tuple[tuple[str, str], ...] = (
    ("ui.helpers.fund.checkup", "render_fund_checkup"),
    ("ui.components.mutual_exclusion", "render_mutual_exclusion_section"),
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
#: ⛔ **這三條的前兩條是「業務規則衝突」，不是技術問題** ——
#: 依 `CLAUDE.md` §-1.5 v3 `03`-2 ② **須由客戶拍板**，本檔不自行決定。
DEFERRED_ENTRIES: tuple[tuple[str, str], ...] = (
    ("ui.helpers.fund_grp_health::render_fund_grp_health_extras",
     "① 它需要 `principal_twd`（一個**使用者選的比較基準本金**）。舊 ② 從一個 "
     "`st.number_input`（預設 1,000,000）拿這個值；**本頁沒有那個 widget，"
     "而新增 widget 屬版面異動，要先送客戶線框草稿**。實測全 repo 除了舊 ② 那個 "
     "widget 之外**沒有第二個來源**。用 `sum(invest_twd)` 會把「每檔各投入 N」"
     "悄悄換成「每檔各投入全部身家」，畫面數字全變、使用者看不出來 —— "
     "那正是 §1 禁止的那種造假。② 它還會轉呼叫 `services/rotation.py` 的"
     "**輪動配對建議**，那是本頁 docstring 逐字點名要停手的「建議類服務」。"),
    ("ui.helpers.fund_grp_health.backtest_section::render_allocation_backtest_section",
     "它輸出「📋 勝出策略建議」「🔄 賣→買 配對建議」「⚖️ 建議配置權重／目標權重%」—— "
     "那就是**再平衡試算與換股建議**，而客戶核准的線框在 Tab 02 的「這裡不放什麼」"
     "逐字寫著「換股建議與再平衡試算 → 04（那是決策，不是診斷）」。"
     "**技術上可以接（只吃 `funds`、實測零寫入），是範圍邊界擋著，不是做不到。**"),
    ("ui.helpers.fund_grp_health.{switch_section,regime_section}"
     "::{render_switch_section,render_regime_fit_section}",
     "兩支都吃**健診大表列** `df.to_dict('records')`，不是本頁的 9 欄列。"
     "實測 key 交集 **0/8** 與 **0/4**（連 `code` 都沒有：本頁的鍵是「代碼」）；"
     "且本頁的值是**格式化後的顯示字串**（`_pct()` 產「12.34%”），"
     "而 `replacement_candidate` 要對 `Sharpe 1Y`／`Sortino` 做加權**算術**。"
     "→ 需要一個 rows adapter，規格見本輪回報；**不硬湊一份假的 rows**（§1）。"),
)


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
    }


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

    # ⚠️ `if _gate:` 必須在 `with` **之外**（送出鈕在 `yield` 之後才建立）。
    if _gate:
        st.session_state[_SK_APPLIED] = {
            "sigma": float(_sigma),
            "window_months": int(_window),
            "satellite_only": bool(_satellite_only),
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
    → 對本批接的這兩支**沒有影響**（實測兩支都不讀 `invest_twd`：
      `render_fund_checkup` 走 `metrics`／`moneydj_raw`／`series`，
      `render_mutual_exclusion_section` 走持股與相關性）。
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

    # ⛔ **lazy import，且逐支具名** —— 不是 `from ui.helpers import fund_grp_health`
    #    那種整包委派。整包委派會把黑名單那兩支（同一個資料夾裡的
    #    `switch_advisor_section`）一起帶進射程，而它們打開就寫 Google Sheet。
    #    守衛拿 `DELEGATED_ENTRIES` 對本檔實際 import 到的符號做**精確集合相等**比對。
    from ui.components.mutual_exclusion import render_mutual_exclusion_section
    from ui.helpers.fund.checkup import render_fund_checkup

    st.divider()
    st.markdown("#### 🔬 逐檔健診與互斥分析")
    # ⚠️ 這句 caption 是**誠實揭露**，不是行銷詞：本區塊的內容與舊 ② 同源同碼，
    #    使用者若發現這裡跟舊 ② 長得一樣，那是對的、是刻意的。
    st.caption("本區直接沿用既有的健診模組（**與舊分頁同一份程式碼、同一條資料路徑**），"
               "版面走新版動線。")

    # 每一支各自包 `safe_section` —— 一支失敗不連坐另一支，也不連坐本頁其他區塊。
    # ⚠️ `safe_section` **不吞例外**（§1）：走 `system_error()` 顯式紅框 ＋ traceback。
    safe_section("基金體檢", lambda: render_fund_checkup(_funds, expanded=True))
    safe_section("持倉互斥避險", lambda: render_mutual_exclusion_section(_funds))


def render_holdings_health() -> None:
    """渲染「② 持倉體檢」整頁。

    ⚠️ **本批尚未接進 `app.py`**（客戶明令舊 ② 不動、不接線、不下架），
    所以現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。
    接線是下一批的事。

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

    safe_section("組合健康總分", _render_health_score)
    safe_section("警示卡片", _render_alert_cards)
    safe_section("逐檔體檢表", _render_health_table)
    # 路線 (A) 委派區 —— 放在**最後**，理由不是隨手排的：
    # 線框 Tab 02 釘死的順序是「總分 → 三張卡 → 逐檔表」，那三塊是本頁自己的版面，
    # 委派進來的是**既有模組自帶的版面**（它們自己會 `st.divider()` + 下標題）。
    # 夾在中間會把線框指定的動線切斷；接在後面則是「線框的四塊 ＋ 沿用的深度分析」。
    _render_delegated_sections()
