"""④ 資產配置 —— 五分頁動線重構的第四頁（全新撰寫，非舊 `ui/tab3_portfolio.py` 的搬運）。

客戶方針（2026-09-04）第 1 條：UI 渲染層打掉重練，不改舊 `tab*.py`，從零撰寫全新 View。
客戶方針（2026-09-05）：本頁**只做骨架 + 灰態**；每一塊的真內容**分批填**。

2026-09-06 接線批：**六塊裡接上一塊，另外四塊的「為什麼還沒接」全部查清楚並就地寫死**
--------------------------------------------------------------------------------
本批的產出**不是**「接了幾塊」，是「**每一塊的狀態都變成可查證的**」。逐塊如下：

===================================== ==========================================
區塊                                    本批狀態
===================================== ==========================================
核心 ／ 衛星現況 vs 建議                 ✅ **接上真資料**（:func:`_render_mix`）
再平衡試算 Form                         ✅ 骨架批就已完成，本批未動
換股顧問                                ⬜ 灰 —— :data:`REASON_SWITCH`
保單與扣款標的                          ⬜ 灰 —— :data:`REASON_POLICY`（**版面待客戶裁決**）
配息月曆                                ⬜ 灰 —— :data:`REASON_DIVIDEND_CAL`（**成本，已量測**）
交易帳本                                ⬜ 灰 —— :data:`REASON_LEDGER`
===================================== ==========================================

⭐ **四塊灰態的原因互不相同，這是本批最重要的一件事。**
在此之前六塊共用一句「本頁分批上線，這一塊的內容還沒接上」——
那句話對其中**三塊是假的**：換股顧問是**撞到既有的唯一渲染點**、
保單是**兩份已拍板線框互相矛盾**、交易帳本是**線框根本沒給欄位規格**。
只有配息月曆勉強沾得上「還沒做」，而它真正的理由是**成本**（見該常數的量測值）。
**用一句藉口蓋住四個不同的原因，等於對使用者說了三次謊**，而且會讓下一個人
一頭撞進那些其實卡在別處的東西。守衛：`test_every_grey_unit_states_its_own_reason`
＋ `test_the_four_grey_reasons_are_actually_different`。

⚠️ **本批查了、但決定「不接」的東西，一併登記（不寫下來就等於沒查）**：

- **配息月曆的資料其實拿得到，而且不必連網** —— 已載入持倉的 `dividends` 就在
  session 裡（`ui/helpers/portfolio/load.py` 寫入），`services.dividend_calendar.
  build_month_calendar` 是零 IO 純函式。**卡住它的是成本不是來源**，數字見
  :data:`REASON_DIVIDEND_CAL`。
- **交易帳本的資料也拿得到** —— `st.session_state["t7_ledgers"]`（舊 ④ 的 T7
  進場時由雲端還原）。**卡住它的是「要顯示哪幾欄」**，那是客戶 gate。
- ⛔ **兩者都不是「沒有來源」。** 下一批不要再從頭找一次來源。

⚠️ **一個本批做出來、但總管有權推翻的判斷**（`CLAUDE.md §-2` 規則 6）：
核心／衛星的唯一真相 `ui/helpers/portfolio/allocation.py` 落在本頁既有守衛
「不得委派舊 ④ 來源檔」的**子字串**射程內（`"ui.helpers.portfolio" in _m`）。
本批**把它具名放行、其餘一個字都沒放寬**，並補了一條會自己巡邏的守衛
（`test_the_named_exemption_is_still_a_pure_ssot`：那支一旦 import streamlit／IO
就轉紅）。**「它到底會不會跟舊 ④ 一起被拔除」本組沒有查證、也不宣稱** ——
若總管認定它在拔除名單內，請推翻本豁免並把這一格退回灰態（成本只有一格）。

整頁骨架 —— 取自已核准線框 `docs/wireframes/ia-wireframe.html` 的 **Tab 04**
------------------------------------------------------------------------------

===== ====================================== ==========================================
順序   區塊                                    版面
===== ====================================== ==========================================
1      核心 ／ 衛星現況 vs 建議                 **全寬**（線框 chip：「全寬」「與 01 同源」）
2      Form — 再平衡試算                       `applied_form`，按「試算」才算
3      換股顧問 ／ 保單與扣款標的 ／ 配息月曆      3 欄自適應網格
4      交易帳本                                **全寬 + 橫向捲動**（線框：「解掉巢狀分頁」）
–      尚未設定持倉                            空狀態三要素（取代 1～4）
===== ====================================== ==========================================

線框同時釘死了本頁的**職責邊界**：

> 回答一個問題：**那我要怎麼調？** 所有會改變我部位的動作都集中在這裡。

⛔ **因此本頁不放**（線框「這裡不放什麼」逐字）：
   「診斷『哪裡有問題』 → **02**」「研究『這檔好不好』 → **03**」
   「⚠️ **巢狀 `st.tabs` 一律不留**；分頁只有一層」。
   → 本檔**沒有任何 `st.tabs` 呼叫**，由 `tests/test_wf04_portfolio_skeleton.py` 釘住。
   下一批填內容時，看到 `services/health` 這類**診斷**服務要停手（落點是 ②）。

⚠️ 一處**尚未裁決的線框衝突**，這一段請務必讀完（不要略過）
--------------------------------------------------------
**④ 同時被三份已拍板線框寫過，而三份的區塊清單幾乎不相交。**
`docs/wireframes/README.md`「版本關係」段明文寫著：
「**`ia-wireframe.html` 與那三份之間的射程本身仍未釐清**，本 README **不替它下結論**。」

===================================== =========================================================
線框（核准先後）                        它說 ④ 有哪些區塊
===================================== =========================================================
`fund-wireframe-final.html`（先）        加入與管理基金／配置總覽／持股重疊度診斷／
                                       帳本（**內部三個子分頁不動**）／費用與扣款／
                                       🤖 AI 摘要／🗂️ Raw data
`policy-split-wireframe.html`（中）      加入與管理基金／📋 保單資料（3 欄狀態列＋保單一覽＋
                                       每張保單明細＋新增更新保單列）／
                                       〔配置總覽·持股重疊度·帳本·費用扣款·AI·Raw data **全部不動**〕
`ia-wireframe.html` Tab 04（後）         核心／衛星現況 vs 建議・再平衡試算 Form・換股顧問・
                                       保單與扣款標的・配息月曆・交易帳本（**解巢狀**）
===================================== =========================================================

**本檔畫的是 `ia-wireframe.html` Tab 04 那一列**，理由（不是「我選了它」，是三條可自驗的依據）：

1. **派工單指名它** —— 本批的規範文件就是 `ia-wireframe.html`，範圍是 Tab 04。
2. **`README.md` 的現行讀法自己寫著** ia-wireframe「對 ②③④ 的頁內架構另有規範
   （四大鐵則 ＋ **Tab 02／03／04 的區塊清單與順序** ＋ ④ 交易帳本解巢狀 …）」。
3. **④ 已經在依它施工並且 merge 了**：`adac135`（④ 交易帳本拉平巢狀分頁）——
   那正是 `fund-wireframe-final.html`「帳本內部三個子分頁**不動**」被推翻的那一條；
   `story_nav._SECTION_LABELS["switch"]` 的就地註解也逐字寫著它來自 ia-wireframe Tab 04。

下面三件事本檔原本登記為「未裁決」，**2026-09-05 總管已回填兩項**，逐條記錄：

- ✅ **(A) ia Tab 04 的清單「不是窮舉」—— 總管 2026-09-05 裁決。**
  **裁決內容**：Tab 04 的區塊清單是「**這一批要做哪幾塊**」，**不是**「④ 只有這幾塊」。
  **三條依據（前兩條本組已自行複跑確認，第三條是論證不是事實）**：
  1. `ui/helpers/story_nav.py::_SECTION_TO_TAB` 寫著 **`"pf_add": "portfolio"`** ——
     **SSOT 自己就把「➕ 加入與管理基金」歸給 ④**
     （實測：`where_to_find("pf_add")` ＝「④ 📊 資產配置 → ➕ 加入與管理基金」）。
  2. 同檔註解 `pf_add → ui/tab3_portfolio.py 的「加入與管理基金」區塊標題`；
     而 `ui/tab3_portfolio.py` 的 `_sec_add = st.container()` 就地註解是
     「**1. 加入與管理基金（沒有標的就沒有配置）**」—— 它是**現行 ④ 的第一個區塊**
     （同檔另有 `st.markdown("### ➕ 加入與管理基金")` 實際渲染）。
  3. ~~**反證法（論證，非實測）**：若讀成窮舉，④ 將**沒有任何地方可以新增基金**，
     整個產品斷掉。客戶拍板的線框不可能被合理地讀成「把唯一能加標的的入口刪掉」。~~
     → ⛔ **2026-09-05 撤回：這一條是假的。**（**有意識的更正，不是漏刪**）
     **產出者：AI 總管**（不是本執行組）；**推翻者：獨立稽核**，以線框實測。
     **反證**：`docs/wireframes/ia-wireframe.html` **第 490 行**（在 **Tab 02** 的空狀態裡）
     逐字寫著 `<li>去哪補 ─ 到「04 資產配置 › 保單與扣款標的」新增</li>` ——
     **ia 自己就在 Tab 04 已列的六塊之內指定了新增入口**，
     所以「讀成窮舉就沒有地方可以新增」這個前提**不成立**。
     ✅ **裁決 (A) 的結論不受影響**：依據 1 與依據 2 是**兩條各自獨立的實測**，
     不靠本條。**本條只是被拿掉，不是被替換。**
     ⚠️ **不要把這段讀成「補充說明」** —— 一句論證被當成依據寫上 production docstring，
     而它可以被一行 grep 推翻。**這正是本檔各處在防的那種形狀。**
  → **本頁的空狀態指到 `pf_add` 是對的、有效的，不改。**
  📌 **但上面那條反證同時掀出一件本檔原本沒有登記的事，就地登記、不裁決**：
  **ia 指的新增入口是「保單與扣款標的」，本頁的空狀態指的是「➕ 加入與管理基金」（`pf_add`）——
  兩者不是同一塊。** 本頁**維持 `pf_add`**，理由是可驗證的：`pf_add` 那一塊**現在就存在於舊 ④**，
  照著做真的會離開空狀態（:func:`_render_no_holdings` 的 AppTest 實跑釘住它）；
  而「保單與扣款標的」在本頁**還是一張灰卡**，指過去等於指到一塊同樣沒做完的東西。
  ⛔ **「線框指的那個入口與現行實作不同名」這件事本身尚未裁決**，
  它與 **未決事項 (B)** 是同一塊版面，**下一批動保單明細時一併送客戶**。

  ⭐ **這條裁決的附帶意義，比它解決的那一題更重要（總管指定寫入本檔）**：
  **它把「線框清單 ＝ 窮舉」這個讀法整個擋掉了。**
  往後**任何一頁**都**不得**因為「線框沒列」就推論「那個功能不該存在」——
  **線框是「版面規範」，不是「功能清單」。**
  ⚠️ 反過來也不成立：**不得**把本條讀成「線框沒列的都可以自己加」。
  它解除的是「**沒列 ⇒ 不該存在**」這個推論，**不是**授權在線框之外新增版面
  （那仍是 `CLAUDE.md §-1.5.1c` v3 §03-2 ① 的客戶 gate）。

- ⏳ **(B) 保單那一塊的版面 —— 未決，且「下一批動工前必須先決」。**
  ia 把「保單與扣款標的」畫成 **3 欄網格裡的一張卡**；
  `policy-split-wireframe.html` **決定 E** 逐字寫「保單明細表**維持全寬**，不塞進三欄」。
  **兩份都是客戶拍板過的線框，對同一塊版面給了相反的規定** —— 與 ③ 那次同型，
  **③ 是客戶裁決的，這一題總管明示也該是客戶裁決，不由總管代決。**
  ✅ **本批不受影響**：骨架階段**一張表都沒畫**，衝突尚未被觸及。
  ⛔ **硬性前置**：**下一批要把保單明細接上時，動工前必須先有客戶裁決** ——
  那一刻才是「3 欄卡 vs 全寬表」真正對撞的時候。
  ⚠️ **這一行不是提醒，是這一題的出口**（總管指定寫入本檔，理由照錄）：
  **「登記為未裁決」的事項，最常見的死法是「裁決真的落下時，沒有人回頭改它」** ——
  ③ 剛剛就發生過這件事。所以本項的觸發點就地寫死在這裡，而不是只寫在 PR 描述裡
  （PR 會被合併掉，這個檔不會）。

- ✅ **(C) 區塊名照線框字面 —— 總管 2026-09-05 裁決，沿用 ③ 的同一條：
  「線框有逐字寫的區塊名，就照它」。**
  ⚠️ **本項的裁決結果是「維持現值」，本檔因此一行都沒有改** ——
  :data:`BLOCK_POLICY` **本來就是** ia Tab 04 的逐字字面「保單與扣款標的」
  （實測：從線框 HTML 抽出的那張卡標題與本常數逐字相同）。
  **變的是它的狀態（未裁決 → 已裁決），不是它的值。**
  ⛔ **據實寫明，不要美化成「已照裁決修改」**：派工回覆寫的是
  「`BLOCK_POLICY` 改成線框字面」，而本檔**原本就是**線框字面 ——
  若照字面「改」，反而會把一個已經正確的值改壞。**核對後回報，不照做，是對的。**
  ✅ **順帶實測**：這個字面**沒有**命中任何既有全域守衛
  （`RETIRED_TAB_LABELS` / `MISWRITTEN_TAB_NAMES` 都沒有它），
  **不需要任何具名豁免** —— 與 ③ 的 `批次分析` 撞黑名單那次不同。

⚠️ **`換股顧問` 例外：走 SSOT，不抄線框字面**（與 (C) 不同的處理，理由在此）
--------------------------------------------------------------------------
ia Tab 04 那張卡寫的是「換股顧問」，而 `ui/helpers/story_nav.py::_SECTION_LABELS`
**已經有這個分區的 SSOT**（`section_label("switch")`），且該筆的就地註解逐字寫著
它是「2026-09-01（客戶拍板線框 `ia-wireframe.html` Tab 04）」加進去的。
→ 手抄一次線框字面，會讓**同一個區塊在 ④ 出現兩個名字**（SSOT 一個、本頁一個），
而 `ui/helpers/fund_grp_health/switch_advisor_section.py` 已經在用 SSOT 那個。
**這正是 `story_nav` 整個模組在防的事**（同型病史：本 repo 死指路已發作三次）。
⚠️ 與 (C) 的差別**只有一個**：`switch` 有 SSOT key，`保單與扣款標的` 沒有 ——
而本批的檔案邊界**不含 `story_nav.py`**，不得為了統一而去新增 key。

⚠️ **線框 Tab 04 的 5 個 chip，逐一登記（2026-09-05 獨立稽核指出第 5 個零登記）**
------------------------------------------------------------------------------
本組自己數過（從 `ia-wireframe.html` 的 Tab 04 區段抽 `<span class="chip">`）：
**恰好 5 個** —— `全寬`／`與 01 同源`／`串接 02 ＋ 03`／`解掉巢狀分頁`／`大表全寬`。

| chip | 本批處置 |
|---|---|
| `全寬` | ✅ 已落地：核心／衛星與交易帳本都不進 3 欄網格（後者走 :func:`wide_table`） |
| `與 01 同源` | 📝 已登記：建議值必須來自 ① 的資產水位，**下一批取數時的約束**（見 :func:`_render_mix`） |
| **`串接 02 ＋ 03`** | 📝 **本次補登，本批未實作** —— 見下段 |
| `解掉巢狀分頁` | ✅ 已落地：本檔沒有任何 `st.tabs` 呼叫（測試釘住） |
| `大表全寬` | ✅ 已落地：交易帳本走 :func:`wide_table`（橫向捲動，不塞進 1/3 欄） |

**`串接 02 ＋ 03`（線框掛在「換股顧問」那張卡上）**：它講的是**資料流**——
換股顧問要把 **② 診斷出的問題檔**配對到 **③ 的候選標的**。
⛔ **本批 0 實作、0 取數**：那張卡在本頁是灰的，串接屬於**接線批**的事
（要先有 ②③ 的真資料出口，本批三頁都還是骨架）。
⚠️ **本項在此之前於頁面／測試／PR 描述皆 0 次提及**（本組實測：`grep -c "串接 02"`
在 `ui/views/page_04_portfolio.py` 與 `tests/test_wf04_portfolio_skeleton.py` 皆為 **0**）——
**登記它，是為了讓它有出口**；不登記的線框元素會直接從交付紀錄裡消失。

⛔ **不修補舊 ④，也不委派它。** 線框「從哪裡搬來」列的 `ui/tab3_portfolio.py`／
   `ui/tab3_t7_ledger.py`／`ui/helpers/portfolio/allocation.py`，以及已經住在 ④ 的
   `ui/helpers/fund_grp_health/switch_advisor_section.py`，本檔**一行都不 import**。
   ⚠️ 換股顧問那一個特別要小心：`tests/test_ia_switch_advisor_moved_to_portfolio.py::`
   `test_switch_advisor_renders_only_from_the_portfolio_tab` 釘住它的渲染點**恰好一個**。
   本頁若「順手也 render 一次」，那條守衛會當場轉紅，而且線上會撞 widget key。

⚠️ **本頁本批尚未接進 `app.py`。** ④ 仍呼叫舊的 `render_portfolio_tab()`，
   客戶明令「舊分頁這批不動、不接線、不下架」。接線是下一批的事。

空狀態的指路依賴什麼（**這一段是本檔最重要的誠實揭露**）
--------------------------------------------------------
沒有持倉時，本頁走空狀態三要素，「去哪補」＝ `where_to_find("pf_add")`
＝「④ 📊 資產配置 → ➕ 加入與管理基金」。

- ✅ **它現在是有效的**：`ui/tab3_portfolio.py` 裡真的有 `### ➕ 加入與管理基金`
  （production 的 ④ 就是那個檔），使用者照著做會寫進 `portfolio_funds`，
  而 `portfolio_funds` 一有內容，本頁**當場離開空狀態** ——
  這一句**由 `tests/test_wf04_portfolio_skeleton.py` 用 AppTest 實跑驗證**，不是推論。
- ✅ **它的長期有效性也已經確定了**（**2026-09-05 總管裁決 (A)，見上**）：
  ia Tab 04 的清單**不是窮舉**，「➕ 加入與管理基金」**沒有**因為線框沒列它而消失 ——
  `story_nav` 的 SSOT 本來就把它歸在 ④（`_SECTION_TO_TAB["pf_add"] == "portfolio"`）。
  ⛔ 這一段原本寫「**它的有效性繫於未決事項 (A)**」——
  **那個顧慮已經解除，但它當初是真的**（若 ia 清單被讀成窮舉，這句指路會變成死指路，
  而且使用者將無處可加基金）。**保留這段病史，是因為它正是 (A) 被裁決的觸發理由。**

三態與空狀態：兩種灰的理由不同，文案必須分開
------------------------------------------
- **沒有持倉** → 空狀態三要素，指路到「➕ 加入與管理基金」（照著做**真的有效**，見上）。
- **有持倉、但這一塊的內容還沒填** → :data:`_PENDING_NOTE` 的灰態。
  ⚠️ **這一族的指路「有效性有限」，就地寫明，不要讀成已經解決**：
  這一塊沒接上，**去任何地方都不會讓它出現**；能指的最誠實的地方就是本頁上**唯一
  真的做完**的那一塊（＝再平衡試算）。這一點**同樣由 AppTest 實跑確認過**
  （送出試算之後，五個灰態單位逐字不變）—— 見測試檔 `test_the_pending_pointer_...`。
  ⚠️ 兩句混成一句，會讓使用者以為「按了試算就會出現配置建議」——不會。

⛔ **線框裡的示意值一個都不准畫**（`CLAUDE.md §1`）：
   「現況 62 ／ 38 → 建議 70 ／ 30」「2 組建議」「3 張保單」「本月 4 筆」
   全部是線框用來示範版面的假數字。填一個看起來合理的核心／衛星比例，
   使用者**完全看不出它是假的**，而且會拿它去決定要不要調部位。

Form 的三個預設值：兩個照線框、一個**刻意不照**，理由逐條寫明
-------------------------------------------------------------
線框畫的是「目標核心比例　70%／可動用金額　TWD 200,000／只調衛星　☑」。

- :data:`_DEFAULT_CORE_PCT` ＝ **70**（照線框）。
  ⚠️ **它與線框那張卡的示意「建議 70 ／ 30」是同一個數字，這個張力要講清楚**：
  本檔**畫 Form 的預設值、不畫卡片上的建議值**。分界是「這個數字是**誰**在說」——
  Form 欄位是**使用者自己設定的參數**（可改、擺明是輸入），
  卡片上的「建議 70 ／ 30」是**系統宣稱的事實**（§1 禁止捏造）。
- :data:`_DEFAULT_SATELLITE_ONLY` ＝ **True**（照線框的 ☑）。
- :data:`_DEFAULT_BUDGET_TWD` ＝ **0**，**刻意不照線框的 200,000**。
  ✅ **2026-09-05 總管明示肯定並要求維持**，理由就地寫死如下（**不要「修正」回 200,000**）：
  **那是使用者的錢，不是模擬參數。** 客戶的紅線是「**不接受假資料**」，而一個
  **預先填好的金額，使用者完全可能以為那是系統知道的他的錢** ——
  他只要沒注意到，就會拿到一份「用他沒有的 20 萬」算出來的再平衡計畫。
  **線框的示意值在這個欄位上不是規格，是佔位。** §1 取嚴 → 預設 0，
  而且 **0 不算送出**（:func:`_normalise_plan`），退回等待輸入。
  ⛔ ~~**這是本檔唯一一處偏離線框字面的地方。**~~
  → **2026-09-05 更正（獨立稽核指出；有意識的更正，不是漏刪）：這句是假的，
  而且它在同一份 docstring 內就自相矛盾** —— 往上約 60 行的「`換股顧問` 例外」
  就是**另一處**刻意偏離線框字面的地方（走 SSOT，不抄字面）。
  **現行（範圍限定版，不再寫成全稱句）**：**本檔偏離線框字面的地方有兩處** ——
  (i) 本項（金額預設 0，不照 200,000）；(ii) `換股顧問` 走 `section_label("switch")` SSOT。
  **兩處的理由不同**：(i) 是 §1（不預填使用者的財產狀態），(ii) 是 SSOT（同一區塊不准兩個名字）。
  ⚠️ **刻意不寫「只有這兩處」** —— 那會是另一句同型的全稱句。
  這裡寫的是「**已知有兩處**」，後人發現第三處請往下加，不必先推翻本行。
  它與 :data:`_DEFAULT_CORE_PCT`（照線框的 70）**的差別就是上面那一句**：
  比例是**參數**，金額是**使用者的財產狀態**。**下一個人要改回去之前，先回答這一句。**

四大鐵律的落點（本檔不自己實作任何一條，一律走既有共用元件）
------------------------------------------------------------
- **鐵則 01 三欄網格** → `ui.helpers.ia.render_cards`。**本檔沒有任何 `st.columns` 呼叫。**
  ⚠️ 全域 `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL` 抓的是「**欄數不是 3**」
  的呼叫，**合規的 3 欄它一動也不動**（③ 的紅隊 2026-09-05 實測）——
  所以「本頁不得自己開網格」這條**只有本頁自己的守衛在守**。
- **鐵則 02 Form 防重繪** → `ui.helpers.ia.applied_form`。**本檔沒有任何 `st.form(` 站點**
  —— 自己寫會讓 `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL`（精確 `==`）轉紅。
- **鐵則 03 三態顏色** → `ui.helpers.render_state`（灰態直接用 `not_ready`，
  卡片走 `ia.state_card` 的 `state=`）。**本檔沒有自己拼 ⬜ 的字串**。
- **鐵則 04 空狀態三要素** → `ui.helpers.ia.empty_state` ＋ `wide_table` 的空分支。
- **指路一律走 `ui.helpers.story_nav`**，不手抄分頁名／分區名。
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
from ui.helpers.story_nav import (
    render_story_nav,
    section_label,
    tab_label,
    where_to_find,
)

# ── session 鍵名（本檔自己的命名空間）────────────────────────────────────────
# ⚠️ 刻意**不**沿用舊 ④ 的鍵：舊頁依方針第 3 條仍在磁碟上、且仍接在 `app.py`，
#    共用鍵會讓兩套 View 互相覆寫對方的狀態，而 payload 形狀並不相同。
_FORM_KEY: str = "v04_portfolio_rebalance_form"
#: **已送出**的試算條件（不是 widget 當下值）。下游只准讀這個 —— 理由見 :func:`_applied_plan`。
#: `None`／不存在 ＝ 還沒試算過（或送出時可動用金額是 0）。
_SK_APPLIED: str = "v04_portfolio_applied_plan"

#: 使用者的持股來源。既有 session 契約，由 ④ 的加入基金流程／`ui/helpers/cloud_io.py` 寫入。
#: ⚠️ 這個字串是**別人定義**的鍵名，本檔只讀不寫 —— 不要在這裡「順手改個好名字」。
_SK_PORTFOLIO: str = "portfolio_funds"

# ── Form 的三個欄位（線框 Tab 04 逐字）──────────────────────────────────────
#: 線框把送出鈕的字寫成「試算」，**不是** `ia.APPLY_LABEL` 的預設「套用」。
#: 具名而不 inline，讓「線框指定的動詞被改掉」看得見。
SUBMIT_LABEL: str = "試算"
_LABEL_CORE_PCT: str = "目標核心比例"
_LABEL_BUDGET: str = "可動用金額"
_LABEL_SATELLITE_ONLY: str = "只調衛星"

#: 線框：「目標核心比例　70%」。理由與那個張力見模組 docstring。
_DEFAULT_CORE_PCT: int = 70
#: 線框：「只調衛星　☑」（預設勾選）。
_DEFAULT_SATELLITE_ONLY: bool = True
#: ⚠️ **刻意不照線框的 200,000**，理由見模組 docstring（那是使用者的錢，不是參數）。
_DEFAULT_BUDGET_TWD: int = 0

#: 滑桿 / 數字框的範圍。⚠️ **線框只給了預設值，沒有給範圍** —— 這幾個是本組挑的，
#: 屬實作細節不是業務規格（同 `page_02_health.py` 的 σ 範圍處置）。
_CORE_PCT_MIN: int = 0
_CORE_PCT_MAX: int = 100
_CORE_PCT_STEP: int = 1
_BUDGET_STEP: int = 10_000

# ── 區塊名 ────────────────────────────────────────────────────────────────
#: 線框 Tab 04 逐字（含全形斜線）。線框 chip：「全寬」「與 01 同源」。
BLOCK_MIX: str = "核心 ／ 衛星現況 vs 建議"
#: 線框寫「Form ─ 再平衡試算」，這裡取其區塊名。
#: **它是本頁唯一「真的做完」的一塊**，所以所有灰態的指路都指向它（見 :func:`_pending_where`）。
BLOCK_FORM: str = "再平衡試算"
#: 線框 Tab 04 逐字。✅ **2026-09-05 總管裁決：照線框字面** —— 本常數**本來就是**它，
#: 故該次裁決**沒有改動這一行**，改的是它的狀態（未裁決 → 已裁決）。見模組 docstring 的 (C)。
#: ⚠️ 另一份已拍板線框（`policy-split-wireframe.html`）把 ④ 那一區叫「📋 保單資料」——
#: **那是它的區「段」名，不是本卡的名字**；(B) 的版面之爭與本常數無關，不要一起改。
BLOCK_POLICY: str = "保單與扣款標的"
#: 線框 Tab 04 逐字。
BLOCK_DIVIDEND_CAL: str = "配息月曆"
#: 線框 Tab 04 逐字。線框 chip：「解掉巢狀分頁」「大表全寬」。
BLOCK_LEDGER: str = "交易帳本"


def switch_block_label() -> str:
    """換股顧問那一塊的名字 —— **走 SSOT，不抄線框字面**（理由見模組 docstring）。

    ⚠️ 做成函式而不是 module 層常數，是為了讓 `section_label()` 的
    §1 Fail Loud（未知 key 直接 `KeyError`）發生在**渲染當下**而不是 import 期 ——
    import 期炸掉會讓整個 `ui.views` 套件無法載入，連帶打死其他四頁。
    """
    return section_label("switch")


#: 灰態的**共用前綴** —— 只描述「狀態」，不描述「原因」。
#: ⚠️ **2026-09-06 語意變更（接線批）**：它原本是「本批共用的灰態理由」，五塊共用一句。
#: 現在每一塊的**原因各不相同而且都已經查清楚了**（見 :data:`_GREY_WHY`），
#: 於是它降格成前綴：**狀態共用一句、原因各寫各的**。
#: ⛔ **為什麼不乾脆讓每塊各寫一整句**：這一句是「本頁分批上線」這個事實的唯一真相源，
#:    五處各寫一次就是五份會各自漂移的文案（§2.1）。**共用的是不會變的那一半。**
_PENDING_NOTE: str = "本頁分批上線，這一塊的內容還沒接上"

#: 每一塊灰態的**真實原因**，接在 :data:`_PENDING_NOTE` 後面。
#:
#: ⭐ **這張表是本批最重要的產出之一，理由寫在這裡**：接線批真正危險的不是「少接一塊」，
#: 是**用一句放諸四海皆準的藉口蓋住四個完全不同的原因**。四塊之中只有一塊
#: （:data:`BLOCK_DIVIDEND_CAL`）的原因勉強算「還沒做」；另外三塊分別是
#: **撞到既有的唯一渲染點**、**線框自己打架**、**線框根本沒給規格** ——
#: 全都不是「資料還沒接」。寫成同一句，等於對使用者說了三次謊。
#:
#: ⚠️ **鍵是「單位名」**（`_units()` 切出來的那個名字），值是接在前綴後的原因子句。
#: `switch` 那一塊的鍵走 SSOT（:func:`switch_block_label`），不抄字面。
#: 換股顧問：**不是沒做，是不能在這裡做第二次。**
#: `tests/test_ia_switch_advisor_moved_to_portfolio.py::`
#: `test_switch_advisor_renders_only_from_the_portfolio_tab` 釘住它的渲染點**恰好一個**
#: （實測 `EXPECTED_RENDER_SITE == "ui/tab3_portfolio.py::render_portfolio_tab"`），
#: 本頁再畫一次會讓那條全域守衛當場轉紅，線上還會撞 widget key `switch_advise_btn`。
#: ⚠️ 它同時還缺兩份本頁拿不到的輸入（實測 `services/switch_advisor.py::advise_switches`
#: 的兩個必要參數）：**選股池**（`repositories.pool_repository.list_pool`，要 OAuth 往返
#: Google Sheets，本頁禁 import `repositories/**`）與**逐檔基準線**
#: （`underperformance_by_code`，要 L3 逐檔算 benchmark）。
#: ⛔ 兩個理由**各自獨立成立**，不要只記其中一個 —— 就算哪天渲染點的限制解除了，
#:    取數那一半仍然擋著。
REASON_SWITCH: str = (
    "（把 02 診斷出的問題檔配對到 03 的候選標的）。"
    "原因不是資料：這一塊在目前線上的 ④ 已經有唯一的渲染點，本頁再畫一次會撞同一個按鈕；"
    "它另外還需要雲端選股池與逐檔基準線，兩者本頁都拿不到")

#: 保單與扣款標的：**原因是版面，不是資料。**（總管 2026-09-06 裁決 2）
#: ⛔ **這一句刻意不說「資料還沒接」** —— 那是假的原因。真正卡住的是
#: `docs/wireframes/ia-wireframe.html`（畫成三欄網格裡的一張卡）與
#: `docs/wireframes/policy-split-wireframe.html`**決定 E**（「保單明細表**維持全寬**，
#: 不塞進三欄」）**對同一塊版面給了相反的規定**，而兩份都是客戶拍板過的線框。
#: 已另派線框組產出草稿送客戶；**在客戶拍板之前，這一區不動工**
#: （`CLAUDE.md §-1.5.1c` v3 §03-2 ①：版面異動一律客戶 gate）。
#: 📌 這正是模組 docstring **未決事項 (B)** 所說的那個觸發點，現在踩到了。
REASON_POLICY: str = (
    "（每張保單下的基金與投入金額）。"
    "原因不是資料，是版面：兩份都已拍板的線框對這一區給了相反的規定"
    "（三欄網格裡的一張卡 vs 維持全寬的明細表），已送客戶裁決，拍板前不動工")

#: 配息月曆：**推得出來，但貴到必須先有一道開關。**
#: 本組實測 `services.dividend_calendar.build_month_calendar`（純 CPU、零 IO，
#: 持倉的 `dividends` 已經在 session 裡，不必連網）：成本隨**配息史長度**超線性成長 ——
#: 6 筆 2.5 ms／12 筆 37 ms／24 筆 156 ms／36 筆 275 ms（單檔，量測日 2026-09-06）。
#: 一個持有 20 檔月配、各三年史的組合 ≈ **3 秒**，而 Streamlit **每次互動都會重跑整頁**。
#: ⚠️ 早期量到的「約 5 ms／檔」是**短路路徑**（無配息 / 陳舊 → 直接落 excluded），
#:    **資料越完整反而越慢**：會出事的正好是資料最好的那個使用者。
#: → 要接上必須先加一道 Checkbox Gate（同 ⑤ `page_05_settings.py::NAV_GATE_LABEL` 的
#:   總管裁決：在 `ui/**` 自建 `@st.cache_data` 會替 `CLAUDE.md` 的 `EX-UICACHE-1`
#:   新增一個成員，而那個例外的成立**繫於尚未裁決的** `P-UIGSPREAD-1`）。
#: ⛔ **本批不加那道開關**：gate 是新的視覺元件，而線框畫的是一張**沒有開關**的卡。
#:    「要不要為它多一個開關」是版面問題 → 客戶 gate，與 :data:`REASON_POLICY` 同一道。
#: ⚠️ **UI 文案刻意不寫那幾個毫秒數**（`CLAUDE.md §8.2.A.0` 規則 4：會漂移的量測值
#:    不寫死）；數字留在這裡並標了量測日，要用請現場重量。
REASON_DIVIDEND_CAL: str = (
    "（預估除息日與誤差天數）。"
    "原因不是沒有來源：推估算得出來，但它很花時間，而這一頁每次互動都會整頁重跑；"
    "要接上得先多一道「按了才算」的開關，那是版面異動，得先過客戶那一關")

#: 交易帳本：**線框沒有給欄位規格。**
#: 線框對它只寫了**內容類型**（買賣紀錄／成本／已實現損益／對帳），沒有像 Tab 02
#: 那樣逐欄列舉；憑印象補一份欄位表就是自己發明規格，而**欄位增減是客戶 gate**
#: （`CLAUDE.md §-1.5.1c` v3 §03-2 ①）。
#: ⚠️ **資料本身其實搆得到**（`st.session_state["t7_ledgers"]`，舊 ④ 的 T7 進場時
#: 由雲端還原），所以「沒有資料」**不是**這一塊的原因 —— 卡住的是「要顯示哪幾欄」。
#: ⛔ 這一條由 `test_the_ledger_invents_no_column_list` 機械釘住（禁止出現名字帶
#:    `COLUMN` 的模組層常數），本說明只是把**為什麼**寫下來。
REASON_LEDGER: str = (
    "（買賣紀錄、成本、已實現損益與對帳）。"
    "原因不是沒有資料：線框沒有給這張表的欄位規格，補一份等於自己發明，"
    "而欄位要列哪幾個是客戶要拍板的事")


def grey_why() -> dict[str, str]:
    """單位名 → 該塊灰態的**真實原因**子句。

    做成函式而不是 module 層 dict，理由與 :func:`switch_block_label` 相同：
    `switch` 那個鍵要走 SSOT（`section_label("switch")`），而 SSOT 的
    §1 Fail Loud 必須發生在**渲染當下**，不是 import 期。
    """
    return {
        switch_block_label(): REASON_SWITCH,
        BLOCK_POLICY: REASON_POLICY,
        BLOCK_DIVIDEND_CAL: REASON_DIVIDEND_CAL,
        BLOCK_LEDGER: REASON_LEDGER,
    }


def _pending_where(block: str) -> str:
    """「內容還沒填」這種灰態的指路。**回傳的必須是一個「地方」。**

    `render_state.not_ready()` 會把它包成「（請先到：…）」——
    也就是說回傳值會變成一句**祈使句的受詞**。塞一句狀態陳述進去
    （「目前只有 X 是完整的」）會產生一句**不可執行的指令**：
    那是 ③ `ui/views/page_03_research.py` 2026-09-05 被獨立紅隊實測抓到的錯，
    修法與病史逐字寫在該檔的同名函式上。**本檔從第一版就避開它。**

    ⛔ **「是一個地方」不等於「去了有用」，這兩件事本檔分開講**：
    這一塊沒接上，去任何地方都不會讓它出現 —— 能指的最誠實的地方就是本頁上
    唯一真的做完的那一塊（＝ :data:`BLOCK_FORM`），而灰態本文
    （:data:`_PENDING_NOTE`）已經先講了「這一塊的內容還沒接上」。
    ✅ **對照**：空狀態（:func:`_render_no_holdings`）那一則的指路是**真的有效**的，
    而且是 AppTest 實跑驗過的。**兩者不要混為一談。**

    ⚠️ 分頁名走 `where_to_find()`，**不手抄**；區塊名由呼叫端傳進來，
    不在這裡再抄一份（手抄的指路在本 repo 已經指錯三次）。
    ⚠️ **刻意不用「」把 `block` 括起來**：`tests/test_batch2_top_card_grid.py::`
    `test_every_where_names_something_that_exists_on_screen` 只對 ``「」`` 內的
    **字面值**比對「畫面上有沒有這個字」，而它的字表不收 `st.caption` ——
    加了括號會產生一條**必然失敗**的比對，不是多一層保護（③ 的既有登記）。
    """
    return f"{where_to_find('portfolio')} → {block}"


def _holdings() -> list[dict[str, Any]]:
    """使用者**目前持有**的基金。

    讀既有 session 契約 `portfolio_funds`，**不自己取數**。

    ⚠️ **`loaded` 過濾是刻意的**（與 `ui/views/page_02_health.py::_holdings` 同源）：
    那份清單裡會有「已列入但 NAV 還沒抓回來」與「抓取失敗」的項目
    （`ui/helpers/portfolio/load.py` 寫入 `loaded` / `load_error` 兩個旗標）。
    拿那些去算配置比例，等於用不完整的資料生一個看起來完整的結論（§1）。
    ⚠️ **回傳空 list 有兩種原因**（完全沒設定 vs 設定了但都還沒載入成功），
    本批的骨架**不區分**它們 —— 兩者的下一步都是先去把基金載進來。
    """
    _raw = st.session_state.get(_SK_PORTFOLIO) or []
    if not isinstance(_raw, list):
        return []
    return [_f for _f in _raw
            if isinstance(_f, dict) and _f.get("loaded") and not _f.get("load_error")]


def _normalise_plan(core_pct: Any, budget_twd: Any,
                    satellite_only: Any) -> dict[str, Any] | None:
    """把 widget 的當下值收成**已送出的試算條件**；沒有可動用金額回 `None`。

    ⚠️ **金額 ≤ 0 不算送出，這是刻意的，不是漏判**：再平衡試算要回答的是
    「這筆錢怎麼分」，沒有錢就沒有題目。硬把 0 當成一次有效試算，
    畫面會停在一份與任何投入都無關的結果上 —— 比退回等待輸入更不誠實（§1）。

    ⚠️ **不吞例外、不猜值**：型別轉不過去就讓它照常拋出去
    （`safe_section()` 會把它畫成系統紅框 ＋ traceback），**不會**自己補一個預設金額。
    """
    _budget = int(budget_twd or 0)
    if _budget <= 0:
        return None
    return {
        "core_pct": int(core_pct),
        "budget_twd": _budget,
        "satellite_only": bool(satellite_only),
    }


def _applied_plan() -> dict[str, Any] | None:
    """**已送出**的試算條件；沒送出過（或送出時金額是 0）就是 `None`。

    ⚠️ 下游一律讀這個，**不要讀 widget 的回傳值** —— 讀了就等於沒有 form
    （鐵則 02 的重點不是「有沒有 form」，是「重運算有沒有被 gate 住」）。
    ⚠️ **本批沒有下游** —— 骨架階段沒有東西要算。這一層現在就要在，
    是因為下一批接上再平衡計算時，它才是真正在擋重運算的那道閘門。
    """
    _cur = st.session_state.get(_SK_APPLIED)
    return _cur if isinstance(_cur, dict) else None


def _render_no_holdings() -> None:
    """空狀態三要素（鐵則 04）—— 一檔持倉都還沒載入。

    ✅ **這一則的「去哪補」照著做真的有效**，而且是 AppTest 實跑驗過的：
       `portfolio_funds` 一有已載入的項目，本頁當場離開空狀態。
    ⛔ 但它的有效性繫於「④ 仍然保有『➕ 加入與管理基金』」。
       ✅ **2026-09-05 更正（獨立稽核指出；有意識的狀態更新，不是漏刪）**：本句原寫
       ~~「而 ia Tab 04 的清單裡**沒有那一塊**。完整說明見模組 docstring 的**未決事項 (A)**。」~~
       —— **(A) 早已在同一份檔案的模組 docstring 裡被裁決為「線框清單不是窮舉」**，
       這裡卻還把它當成未決，**同一份檔案自己打自己**。
       **現行**：見模組 docstring **已裁決的 (A)** ——「線框是版面規範，不是功能清單」。
       ⚠️ **當初的顧慮是真的，病史保留**：ia Tab 04 的六塊裡確實沒有逐字寫
       「➕ 加入與管理基金」，所以當時懷疑這條指路會指空**是合理的**；
       被推翻的是那個推論（沒列 ⇒ 不存在），不是當時的謹慎。
       ⛔ **這一則本身就是 (B) 段警告的那個死法的實例**：同一個 commit 裡，(B) 寫著
       「『登記為未裁決』的事項，最常見的死法是裁決落下時沒有人回頭改它」，
       **而它警告的事就發生在同一份檔案的下游 docstring。留著這段，是為了讓它可被引用。**
    ⛔ **不得**在這裡順便說「加完就會看到再平衡建議」：加完看到的是下一段的灰態。
       兩種灰的下一步不同，一次只給一個（`page_02_health.py` / `page_03_research.py` 同型）。
    """
    empty_state(
        "尚未設定持倉",
        "還沒有任何已載入的保單或扣款標的 —— 沒有標的就沒有配置可以調",
        where=where_to_find("pf_add"),
        footer="載入之後，這一頁才會往下展開。",
    )


#: 「現況」那一組數字的抬頭。
MIX_CURRENT_LABEL: str = "現況"
#: 「目標」那一組數字的抬頭。
#: ⛔ **刻意是「目標」不是「建議」**（總管 2026-09-06 裁決 1）。區塊名
#: :data:`BLOCK_MIX` 照線框逐字寫著「vs **建議**」，但這個數字**不是系統算出來的建議** ——
#: 它是使用者自己在 ④ ⚙️ 組合設定裡拉的那根滑桿（`portfolio_core_pct`）。
#: 把使用者自己設的值標成「建議」，等於系統冒名替他背書一個他自己填的數字（§1）。
#: **抬頭說真話、區塊名照線框**，兩者的落差由 :data:`MIX_TARGET_PROVENANCE` 就地講明。
MIX_TARGET_LABEL: str = "你設定的目標"
#: 「差距」那一行的抬頭（線框：「這裡只呈現差距與所需動作」）。
MIX_GAP_LABEL: str = "差距"

#: ⭐ **裁決 1 要求逐字出現在畫面上的那句話。**
#: 線框把這一格畫成「現況 → **建議**」，並在 chip 上寫「**與 01 同源**」——
#: 也就是原本設想「建議值來自 ① 的資產水位」。
#: ⛔ **① 給不出這個數字，這是實測不是推論**：`ui/views/page_01_macro.py` 的模組
#: docstring 第 63~66 行逐字寫著「『建議資產水位』為什麼是**股／債／現金**，
#: 不是核心／衛星」，其資料源 `services.allocation_ladder.allocation_from_composite`
#: 的回傳欄位就是 `{equity, bond, cash}` —— **整條鏈上沒有核心／衛星這個維度**。
#: → 於是這一格改用**使用者自己設定的目標**，並且**在畫面上說出它的出身**。
#: ⛔ **絕對不准自己算一個「建議核心比例」** —— 那會是一個長得像系統建議、
#:    實際上憑空生出來的數字，而使用者會拿它去調真的部位。
MIX_TARGET_PROVENANCE: str = (
    f"「{MIX_TARGET_LABEL}」是你自己在組合設定裡設定的值，不是系統算出來的建議 —— "
    "本頁只把它跟現況擺在一起看差距。")


def _pct_text(value: float) -> str:
    """把 0~100 的百分比畫成字。**一位小數 ＋ 緊接著的 `%`。**

    ⚠️ **格式本身是一條 §1 防線，不是排版偏好。** `summarize_core_satellite` 的
    分子分母都是使用者填的金額，所以**真實組合完全可能剛好算出 62.0 ／ 38.0** ——
    那正是線框拿來示範版面的那一組示意值（實測：`invest_twd` 620000 ／ 380000
    → `core_pct == 62.0`）。
    只要中間夾著 `%` 與抬頭，畫面上就不會出現 `tests/…::_PINNED_FAKE_VALUES`
    釘的那個「數字 ／ 數字」形狀，**真數字不會被誤判成假數字，假數字也不會偷渡成真的**。
    ⛔ 不要「順手」改成 `f"{a} ／ {b}"` —— 那一改，一個**真實**的 62/38 組合會讓
       示意值黑名單轉紅，而修法會變成放寬黑名單。
    """
    return f"{value:.1f}%"


def _render_mix() -> None:
    """區塊 1｜核心 ／ 衛星現況 vs 建議（**全寬**）。**2026-09-06 接上真資料。**

    線框：「現況 62 ／ 38　→　建議 70 ／ 30／建議值來自 01 的資產水位，
    這裡只呈現差距與所需動作。」chip：「全寬」「與 01 同源」。

    來源（三個問題逐一回答，`CLAUDE.md §1`）
    ----------------------------------------
    1. **數字從哪來** —— `ui/helpers/portfolio/allocation.py`：
       `summarize_core_satellite()`（現況）＋ `get_core_target_pct()`（目標）。
       該模組的 docstring 自陳是「核心 / 衛星配置的**唯一真相**」，
       而且是為了收掉「同一頁 4 處各算各的、3 種定義、2 種目標值」才存在的。
    2. **它算的是不是這一格講的那件事** —— 是。分母是 **Σ 投入本金**（金額加權，
       不是檔數）、分類**`policy_tier` 優先**（使用者在 Sheet 明示的級別），
       目標**一律讀 `portfolio_core_pct`**。這正是「核心／衛星現況 vs 目標」。
       ⛔ **對照組（差一點就接錯的那個）**：`services/policy_advisor_service.py::`
       `recommend_policy` —— **名字對，意思錯**。分歧軸有兩條，**都與滑桿無關**：
       (a) **分類**：它只看 `is_core`（名稱關鍵字啟發式），**完全不看 `policy_tier`**
       （實測 `git grep -n policy_tier -- services/policy_advisor_service.py` **0 命中**；
       正對照：同一條 grep 在全 repo 命中 10+ 檔，所以那個 0 是真的 0）；
       (b) **範圍**：它是**單一保單**級，本頁是**整個組合**。

       ⚠️ **`target_core_pct` 寫死 75.0 那條不成立，不要再拿它當理由**
       （2026-09-06 稽核擋下，實測更正）：`75.0` 是**參數預設值，production 從來沒被用過**。
       全 repo 唯一的 production 呼叫點是 `ui/tab3_portfolio.py`
       （`recommend_policy(_funds_enriched, target_core_pct=_policy_target)`），
       而 `_policy_target` 來自 `get_core_target_pct(st.session_state)` ——
       **與本頁同一支 SSOT 函式**。也就是說目標值兩邊本來就同源，
       ~~「預設下一模一樣、拉滑桿才分歧」~~ 這個機制**是假的**。

       **把目標值固定成同一個數（排除該變因）後實測，差距 62 個百分點**：
       用本檔 fixture（620000 `core` ／ 380000 `satellite`，`policy_tier` 明示）、
       兩邊同給 `target=75.0` ——
       SSOT `core_pct` = **62.0**；`recommend_policy` 的訊息是
       「核心配置 **0.0%** 低於目標 75%（-75.0%）」。
       0.0 的來源正是 (a)：fixture 沒有 `is_core` 欄位，它就當成一檔核心都沒有。

       ⚠️ **它其實連 `core_pct` 這個欄位都不回**（AST 掃過 4 條 return path，
       鍵一律只有 `{code, color, text}`）—— 那個數字是**內嵌在 `text` 字串裡**的。
       所以「接它」實際上是把一句**用另一把尺算出來的中文句子**貼到畫面上，
       比「拿錯一個數字」更難被發現。
    3. **算不出來時它回什麼** —— 回 `None`，**不是 0**。該函式的 docstring 逐字寫著
       「缺資料時誠實回 None，不捏造 0；CLAUDE.md §1」，並另外吐一個
       `is_amount_weighted` 旗標。→ 本函式據此走 :func:`not_ready`，**不畫 0%**。

    ⚠️ **「與 01 同源」這個 chip 沒有落地，而且是刻意的** —— 見
    :data:`MIX_TARGET_PROVENANCE`：① 整條鏈只給股／債／現金，給不出核心／衛星。
    這一格因此改用**使用者自己的目標**並在畫面上說明出身。**登記，不假裝已達成。**
    """
    # 唯一真相：核心／衛星的分類、分母與目標值全部走這一支（理由見本函式 docstring）。
    from ui.helpers.portfolio.allocation import (
        format_core_satellite_caption,
        get_core_target_pct,
        summarize_core_satellite,
    )

    _target = get_core_target_pct(st.session_state)
    _summary = summarize_core_satellite(_holdings(), target_pct=_target)
    _core = _summary.get("core_pct")

    if _core is None:
        # 一檔本金都沒填 → **沒有比例可言**。⛔ 這裡不畫 0%／不畫甜甜圈／不猜 ——
        # 「0% 核心」與「不知道核心佔多少」在畫面上長得一樣，但意思差到相反（§1）。
        # 缺什麼由 SSOT 的 `format_core_satellite_caption()` 講（它知道幾檔沒填、
        # 級別是 Sheet 給的還是關鍵字猜的），本檔不另寫一份會漂移的說明。
        # 去哪補 = 「➕ 加入與管理基金」——**這一條指路是真的有效的**
        # （同空狀態那一則，由 AppTest 實跑釘住），與四塊灰態那種「指了也沒用」不同。
        not_ready(format_core_satellite_caption(_summary),
                  where=where_to_find("pf_add"))
        return

    _sat = _summary.get("sat_pct")
    _diff = _summary.get("diff_pct")
    st.markdown(
        f"**{MIX_CURRENT_LABEL}**　核心 {_pct_text(_core)}　"
        f"衛星 {_pct_text(_sat)}　→　"
        f"**{MIX_TARGET_LABEL}**　核心 {_pct_text(_target)}")
    if _diff is not None:
        # 「差距與所需動作」的**差距**那一半（線框逐字）。
        # ⛔ **所需動作那一半本批不畫** —— 要算「該搬多少錢」得先知道可動用金額，
        #    而那是 Form 的輸入；把它寫死或猜一個，就是替使用者決定他的錢。
        _gap = "剛好落在目標上" if abs(_diff) < 0.05 else (
            f"核心比目標多 {_pct_text(abs(_diff))}" if _diff > 0
            else f"核心比目標少 {_pct_text(abs(_diff))}")
        st.markdown(f"**{MIX_GAP_LABEL}**　{_gap}")
    # 出身 ＋ 分母／級別來源／幾檔沒填本金：兩句都不是本檔自己寫的結論。
    st.caption(MIX_TARGET_PROVENANCE)
    st.caption(format_core_satellite_caption(_summary))


def _render_rebalance_form() -> None:
    """區塊 2｜Form — 再平衡試算。**本批唯一做完的一塊。**

    線框 Tab 04 逐字：「目標核心比例　70%／可動用金額　TWD 200,000／只調衛星　☑／試算」。
    三個預設值的取捨（其中一個刻意不照線框）見模組 docstring。
    """
    _cur = _applied_plan() or {}
    with applied_form(_FORM_KEY, submit_label=SUBMIT_LABEL) as _gate:
        st.caption(f"{BLOCK_FORM}：條件改完按「{SUBMIT_LABEL}」才算 —— "
                   "拖滑桿的當下不會觸發任何取數或重算。")
        _core = st.slider(
            f"{_LABEL_CORE_PCT}（%）",
            min_value=_CORE_PCT_MIN, max_value=_CORE_PCT_MAX,
            value=int(_cur.get("core_pct", _DEFAULT_CORE_PCT)),
            step=_CORE_PCT_STEP,
            help="調整後希望核心部位佔整體的比例；其餘為衛星。",
        )
        _budget = st.number_input(
            f"{_LABEL_BUDGET}（TWD）",
            min_value=0, value=int(_cur.get("budget_twd", _DEFAULT_BUDGET_TWD)),
            step=_BUDGET_STEP,
            help="這次打算投入或挪動的金額。留 0 代表還沒決定，不會進行試算。",
        )
        _satellite_only = st.checkbox(
            _LABEL_SATELLITE_ONLY,
            value=bool(_cur.get("satellite_only", _DEFAULT_SATELLITE_ONLY)),
            help="勾選後只調整衛星部位，核心部位不動。",
        )

    # ⚠️ `if _gate:` 必須在 `with` **之外**（送出鈕在 `yield` 之後才建立）。
    if _gate:
        st.session_state[_SK_APPLIED] = _normalise_plan(
            _core, _budget, _satellite_only)


def _render_action_cards() -> None:
    """區塊 3｜三張卡（3 欄自適應網格）。本批三張全灰。

    線框 Tab 04 三張卡逐字：
      「換股顧問／2 組建議／把 02 診斷出的問題檔，配對到 03 的候選標的。」
      「保單與扣款標的／3 張保單／每張保單下的基金與投入金額；權重是算出來的，不是存的。」
      「配息月曆／本月 4 筆／預估除息日與誤差天數，推不出來的保留可見。」

    ⛔ **本批不畫「2 組建議」「3 張保單」「本月 4 筆」** —— 那些是示意值（§1）。
    ⚠️ 線框把三張都畫成有內容的樣子，是在示範「有東西時長什麼樣」。
       真接上之後，狀態由**資料**決定（沒有建議就該是 `STATE_OK` 而不是永遠灰著），
       不是由線框的示意圖決定（鐵則 03：`state` 決定視覺，不是文案）。
    ⚠️ **「推不出來的保留可見」是配息月曆自己的 §1 約束**（線框逐字）：
       下一批接上時，推不出除息日的那幾筆**要留在畫面上並標明推不出來**，
       不得從清單裡消失 —— 消失會被讀成「這檔本月不配息」。**登記，本批不實作。**
    """
    _where = _pending_where(BLOCK_FORM)
    _why = grey_why()
    render_cards([
        {"title": _t, "state": STATE_NOT_READY,
         "note": f"{_PENDING_NOTE}{_why[_t]}。", "where": _where}
        for _t in (switch_block_label(), BLOCK_POLICY, BLOCK_DIVIDEND_CAL)
    ])


def _render_ledger() -> None:
    """區塊 4｜交易帳本（**大表全寬 + 橫向捲動**）。本批無列資料 → 走空狀態。

    線框逐字：「**目前埋在「持股」分頁裡的第二層 `st.tabs`，此次拉到同一層。**
    買賣紀錄 / 成本 / 已實現損益 / 對帳。欄位多，全寬橫向捲動。」

    ⚠️ **本檔沒有列出欄位清單，這是刻意的**：線框對交易帳本**只寫了內容類型**
       （買賣紀錄／成本／已實現損益／對帳），**沒有像 Tab 02 那樣逐欄列舉**。
       憑印象補一份欄位表，下一批接真資料時就會發現欄位對不上 —— 那是自己發明規格。
       ⛔ 對照：`page_02_health.py::HEALTH_TABLE_COLUMNS` 之所以能釘住 9 欄，
       是因為**線框真的逐字列了那 9 欄**。這裡沒有，所以這裡不釘。

    ⚠️ **走 `wide_table()` 而不是 `st.dataframe()`**：空資料不畫空框這件事，
       只有收在唯一的大表入口才有機械上的著力點（`ui/helpers/ia/layout.py` 的 docstring）。
    ⚠️ **這張表不得放進 `render_cards()` 的欄位裡**（欄位多，1/3 寬會被壓到無法閱讀），
       所以它是頁面層級的直接呼叫，不在任何網格內。
    """
    # ⛔ 標題只講「本塊未接線」，**不得**講使用者有幾列（§1）。
    #    舊字串是 ~~「交易帳本還沒有可顯示的列」~~ —— 2026-09-05 獨立稽核指出它在
    #    **斷言使用者的資料狀態**：這一塊根本還沒接線，我們沒有查過他的帳本，
    #    「還沒有可顯示的列」是一句我們無從得知真假的話，而且與同一個呼叫的
    #    `empty_missing`（「本頁分批上線，這一塊的內容還沒接上」）**互相矛盾**。
    #    使用者讀完舊標題會以為系統查過他的帳本、結論是空的 —— 那是造假。
    wide_table([], empty_title="交易帳本這一塊還沒接上",
               empty_missing=f"{_PENDING_NOTE}{grey_why()[BLOCK_LEDGER]}。",
               empty_where=_pending_where(BLOCK_FORM))


def render_asset_allocation() -> None:
    """渲染「④ 資產配置」整頁。

    ⚠️ **本批尚未接進 `app.py`**（客戶明令舊 ④ 不動、不接線、不下架），
    所以現在**沒有 production caller** —— 這是**刻意的中間狀態**，不是漏接。

    ⚠️ **區塊之間走 `safe_section()` 隔離**：`st.tabs` 是單次 run 渲染全部分頁，
    任一區塊拋未捕捉例外會**中止整個 script**，其後所有分頁空白。
    `safe_section` **不吞例外**（§1）：它走 `system_error()` 顯式紅框 ＋ traceback。
    """
    st.markdown(f"## {tab_label('portfolio')}")
    render_story_nav("portfolio")
    # 線框 Tab 04 的職責宣告 ＋「這裡不放什麼」。
    # ⚠️ 指路的顆粒度**跟著線框走**：線框寫「→ 02」「→ 03」（整個分頁），
    #    所以這裡指 `health` 與 `research` 兩個**分頁**，不是頁內分區。
    st.caption(
        "回答一個問題：**那我要怎麼調？** 所有會改變我部位的動作都集中在這裡 —— "
        f"診斷「哪裡有問題」在 {where_to_find('health')}，"
        f"研究「這檔好不好」在 {where_to_find('research')}。")

    if not _holdings():
        # 一檔都還沒載入 —— 下面四塊沒有任何東西可以呈現或調整，直接走空狀態，
        # **不要**把四塊各印一次灰（那會變成五份在講同一件事的灰字，違鐵則 04）。
        safe_section("尚未設定持倉", _render_no_holdings)
        return

    st.markdown(f"#### {BLOCK_MIX}")
    safe_section(BLOCK_MIX, _render_mix)
    st.markdown(f"#### {BLOCK_FORM}")
    safe_section(BLOCK_FORM, _render_rebalance_form)
    safe_section("動作卡", _render_action_cards)
    st.markdown(f"#### {BLOCK_LEDGER}")
    safe_section(BLOCK_LEDGER, _render_ledger)
