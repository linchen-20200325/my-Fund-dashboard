# 分支策略 vs 現況 — 盤點稽核（純調查，未建分支／未改檔／未開 PR）

量測日 2026-09-16 · base `origin/main` = `9cbf037`（本 clone 的 origin/main 最新 commit 日期 2026-09-13，
本輪禁止 `fetch`，故此為快照）· 工作樹 HEAD `d0c2a8d`（是 `9cbf037` 的祖先，落後 220 commits）
⚠️ 本 clone 為 **shallow**（`.git/shallow` 5 個 graft 點，最舊 commit 2026-08-28），
故任何「歷史上總共幾個 commit」的數字只涵蓋 2026-08-28 起。

掃描紀律：每批掃描同時跑正控與負控；負控為本組自訂隨機串，未列出。

---

## 0. 現況覆核（自行重跑，未照抄總管）

| 項目 | 實測 | 指令 |
|---|---|---|
| `ui/views/` | **6 檔**（`__init__.py` + `page_01_macro` / `page_02_health` / `page_03_research` / `page_04_portfolio` / `page_05_settings`） | `git ls-tree --name-only origin/main ui/views/` |
| `ui/tab*.py` | **16 個** | `git ls-tree --name-only 9cbf037 \| grep -cE '^ui/tab[^/]*\.py$'` → 16 |
| `feat/ui-redesign-v2` | **不存在**（local + remote refs 皆 0 命中） | `git for-each-ref \| grep -i ui-redesign` |
| 本地分支 | `main` / `claude/fund-handover-verification-89o6ys` / `pr829`~`pr834` | `git for-each-ref refs/heads/` |
| `app.py` 分頁 | `:581-587` `st.tabs(...)` **九格 ＝ 5 正式(`_tab_label`) + 4 預覽(`_preview_tab_label`)** | `git show origin/main:app.py \| awk 'NR==581,NR==587'` |
| `ui/helpers/**` | 82 個 `.py`；`ui/components/**` 17 個 `.py` | `git ls-tree -r --name-only origin/main` |

**九個 PR ＝ #837~#845**（皆 open、皆 draft、base 皆 `9cbf037`，建立於 2026-09-14/15）。
本地 `origin/*` ref 的 SHA 與 GitHub 上九個 PR 的 head SHA **逐一相符**（已核對）。
另有 3 個較舊的 open PR（#836 / #799 / #791），base 不同，**不在這九個之內**。

---

## 1. 九個 PR 動到的檔案（`git diff --name-only <merge-base> <head>`）

| PR | head 分支 | 動到的檔案 | 碰到 `ui/views/page_0*`？ |
|---|---|---|---|
| #837 | `docs/v2-constitution-governance` | `docs/v2/CONSTITUTION.md` | 否 |
| #838 | `claude/v2-data-dictionary-a` | `docs/v2/DATA_DICTIONARY.md` | 否 |
| **#839** | `compliance/remove-action-advice` | `EXCEPTIONS.md`、`tests/test_no_direct_trade_advice_20260914.py`、**`ui/tab6_manual.py`**、**`ui/views/page_01_macro.py`**（+78 / -7） | **是** |
| #840 | `claude/v2-ui-spec-b` | `docs/v2/UI_SPEC.md`、`docs/v2/UI_WIREFRAME_DRAFT.md` | 否 |
| #841 | `fix/fund-category-orchestration` | `repositories/fund/fund_orchestration.py`、`repositories/fund/sources.py`、**`services/regime_fit.py`**、`tests/test_fund_category_paragraph_guard.py` | 否 |
| #842 | `fix/q8-stop-tier-guessing` | `docs/POLICY_SHEETS_SETUP.md`、`repositories/snapshot_repository.py`、`shared/policy_tier.py`、`tests/test_policy_tier_no_guessing.py`、**`ui/helpers/cloud_io.py`**、**`ui/helpers/portfolio/allocation.py`**、**`ui/helpers/portfolio/load.py`** | 否 |
| #843 | `fix/q8-tier-writeback-and-caption` | `tests/test_q8_tier_writeback_and_caption.py`、**`ui/components/allocation_donut_card.py`**、**`ui/helpers/portfolio/allocation.py`**、**`ui/helpers/portfolio/linkage.py`** | 否 |
| #844 | `q8b3-stop-tier-guess-add-paths` | `EXCEPTIONS.md`、`tests/test_constitution_file_refs.py`、`tests/test_q8_add_fund_no_tier_guess.py`、**`ui/tab3_portfolio.py`**、**`ui/tab3_t7_ledger.py`** | 否 |
| #845 | `claude/fund-handover-verification-89o6ys` | `docs/v2/` 下 5 個 `.md` | 否 |

**只有 #839 動到 `ui/views/page_0*`（`page_01_macro.py`，+78/-7）。** 九個 PR **沒有任何一個動 `app.py`**。
附帶：#842 與 #843 **都改 `ui/helpers/portfolio/allocation.py`**（兩者之間也會相撞）；
#839 與 #844 **都改 `EXCEPTIONS.md`**。

---

## 2. 凍結令原文（出處：**PR #837**，`docs/v2/CONSTITUTION.md` §1.1，未合併的 draft）

| # | 凍結對象 | 原文 |
|---|---|---|
| F1 | 16 個 `ui/tab*.py` | 「**16 檔，一個位元組都不准動**」 |
| **F2** | **五個線上頁 `ui/views/page_0*.py`** | 「**5 檔 / 11,357 行**」 |
| F3 | `app.py` | orchestrator，含五頁接線 |
| F4 | 計算引擎 `services/**` | — |
| F5 | 資料表 Schema | — |
| F6 | 遷移歷史鏈 | — |

§1.1 表下逐字：
> ⭐ **F2 是最容易被誤判的一格，故就地釘死。**
> 「`ui/views/` 看起來像 v2 的新目錄」是**錯的**：`app.py` 現在**同時** import 全部五頁，
> 它們是**正在服務使用者的線上 UI**，因此**與 16 個 `tab*.py` 同級凍結**。
> ⛔ **不得**以「那是新頁、還在預覽」為由去動它們。

§1.2：「非動不可 → 走 §5『母法修正提案單』，在 PR 裡提出，⛔ **不得自己動手**。」

**本組實測覆核該表的數字（全部相符）**：
`ui/views/page_0*.py` 逐檔行數 2192 / 1858 / 2755 / 2789 / 1763 = **11357**；`__init__.py` = **67**；`ui/tab*.py` = **16**。

⚠️ 母法〈專案重構終審令〉**原文在 repo 內查不到**（只有 `CONSTITUTION.md` 引用它）。

---

## 3. 五個潛在衝突點

### 衝突點 1 — 九個 PR 有沒有動 `ui/views/page_0X_*.py`？
**有，一個：#839 動 `ui/views/page_01_macro.py`（+78 / -7）。**
→ 若 `feat/ui-redesign-v2` 依規則 2 在 `page_01_macro.py` 上寫新 UI，而 #839 之後落地，**同檔相撞**。
其餘八個都不碰 `ui/views/`。

### 衝突點 2 — 規則 2＋3＋4 併起來做得到「關舊入口」嗎？
**做不到（在規則 2/3/4 的字面下）。**
- 切換哪一格渲染哪個頁面的接線**全部在 `app.py`**：`:581-587` 的 `st.tabs(...)` 九格，
  以及 `:619 / :646 / :660 / :671 / :686` 五個正式 `with tab_*:` 區塊。
- `app.py` 位於 **repo 根目錄**，**既不是 `ui/views/`、也不是 `ui/tab*.py`**。
- 它算不算規則 4 的「共用層」：**客戶的六條沒有定義「共用層」**，故本組不裁決；
  但**凍結令 F3 明文把 `app.py` 列為凍結對象**，且 §1.2 說「⛔ 不得自己動手」。
- **兩者不能同時為真**：規則 6 要「關舊入口」＝必須改 `app.py`；F3＋§1.2 說 `app.py` 不准自己動。
- 附帶：`tests/test_wpf_five_tab_wiring.py:117` `_want_n = len(_FIVE_KEYS) + len(_PREVIEW_KEYS)`（5+4=9）
  且 `:131` `assert _keys == _FIVE_KEYS`、`:149` `assert _pv_keys == _PREVIEW_KEYS` ——
  **關掉任一舊入口，這幾條當場轉紅**，而 `tests/` 也不在規則 2 允許寫的 `ui/views/page_0X_*.py` 內。

### 衝突點 3 — 規則 4「共用層不准 import 任何 UI」的射程
**現況（實測）與該規則不一致，且是兩個方向：**
1. **新頁 import 舊 UI（4 處）**：
   - `ui/views/page_01_macro.py:1117` `from ui.tab1_macro_midcycle import render_mid_cycle_section`
   - `ui/views/page_05_settings.py:1246` `from ui.tab5_data_guard import render_data_guard_tab`
   - `ui/views/page_05_settings.py:1528` `from ui.tab_manage import render_manage_tab`
   - `ui/views/page_05_settings.py:1632` `from ui.tab6_manual import render_manual_tab`
2. **共用層 import 舊 UI（已經在 main 上，4 行 / 2 檔）**：
   - `ui/helpers/cloud_io.py:489` `from ui.tab3_t7_ledger import _sync_invest_twd_from_ledgers`
   - `ui/helpers/settings_diag/nav_history_section.py:63 / :86 / :87` → `ui.tab5_data_guard` ×2、`ui.tab_manage` ×1
3. **新頁對共用層的依賴量**：五頁合計 import **26 個** distinct `ui.helpers.* / ui.components.*` 模組
   （含 function-level lazy import）。
4. **`ui/helpers/ia/` 是真共用，不是新 UI 專屬**：同時被 5 個新頁 **與** `ui/tab1_macro.py` /
   `ui/tab2_single_fund.py` / `ui/tab5_data_guard.py` / `ui/tab_fund_grp_health.py` / `ui/tab_manage.py` / `app.py` 使用。

→ 「`ui/helpers/*`、`ui/components/*` 算 UI 還是共用層」**客戶六條未定義，本組不裁決**；
兩種讀法都有一個條文被違反：
- 讀成「是 UI」→ 規則 4 的「不准 import 任何 UI」**已被 main 現況違反**（上列第 2 點），
  而修它要改共用層 ⇒ 撞規則 4 的「不可改」。
- 讀成「是共用層」→ 新頁要演進自己的 IA kit（`ui/helpers/ia/*`）就得改共用層 ⇒ 撞規則 4 的「不可改」；
  而改了又會同時改到 5 個舊 tab 的行為（雖然舊 tab 的 byte 沒動）。

### 衝突點 4 — 規則 5「不准中途 merge 回主線」vs 九個 PR
**`origin/main` 推進速度（committer date，本 clone 快照）**：

| 日期 | commits |
|---|---|
| 2026-09-13 | 1 |
| 2026-09-09 | 7 |
| 2026-09-08 | 106 |
| 2026-09-07 | 86 |
| 2026-09-06 | 97 |
| 2026-09-05 | 52 |
| 2026-09-04 | 32 |
| 2026-09-03 | 24 |
| 2026-09-02 | 44 |
| 2026-09-01 | 44 |
| 2026-08-31 | 5 |
| 2026-08-28 | 12 |

**2026-09-01 ~ 2026-09-13（13 天）＝ 493 commits（約 38/日）。**
（⚠️ clone 為 shallow，2026-08-28 之前量不到；且 `origin/main` ref 停在 2026-09-13，本輪禁止 fetch。）
九個 PR 合計動到的檔案去重後含 `ui/tab*.py` 2 檔、`ui/views/page_0*` 1 檔、`services/` 1 檔、
`ui/helpers/*` 4 檔、`ui/components/*` 1 檔、`repositories/*` 3 檔 —— **其中 `ui/views/page_01_macro.py`
與 `ui/helpers/*`、`ui/components/*` 正是新分支會讀（甚至想改）的東西**。
→ 規則 5 與這個推進速度不能同時成立：分支不 merge 回來，main 每天約 38 個 commit 往前跑，
**分叉會在「新 UI 驗收 + 觀察一週」（規則 6）期間持續擴大**。

### 衝突點 5 — 規則 3「舊 UI 一個 byte 不動」vs 既有守衛測試
**有守衛會因為「新 UI 改了、舊 UI 沒改」轉紅，逐條列出：**

1. **`tests/test_wf05_settings_skeleton.py:987` `test_the_new_page_delegates_the_same_set_as_the_old_one_minus_the_lying_block`**
   `:1053-1066` 逐字：
   ```
   _old = _entries("ui/tab_settings_diag.py")
   _new = _entries("ui/views/page_05_settings.py")
   assert _old, "舊 ⑤ 掃不到任何委派 —— 基準沒了，本條失去對象。"
   _lost = sorted(_old - _new)
   assert _lost == [("ui.helpers.settings_diag.nav_history_section", "render_nav_status_section")], ...
   _gained = sorted(_new - _old)
   assert not _gained, (f"新 ⑤ 多了舊 ⑤ 沒有的依賴：{_gained}\n" ...)
   ```
   → 新 ⑤ **只要多委派一個舊 ⑤ 沒有的模組就轉紅**；要讓它綠，得改舊 ⑤ ⇒ 撞規則 3。

2. **`tests/test_wf02_health_golive.py:700` `test_the_switch_adds_no_write_surface`**
   docstring 逐字：「切換**沒有**把任何新的寫入槽拉進射程（新頁閉包的寫入面 ⊆ 舊 ②）」
   → 新 ② 加任何新寫入能力即紅；基準是舊 ②（規則 3 凍住）。

3. **`tests/test_wf05_settings_golive.py:333` `test_the_new_page_adds_no_write_surface`** — 同型，基準為舊 ⑤。
   該檔 docstring 逐字：「⛔ 舊 ⑤ 哪天被下架，本條失去基準 —— **正解是把基準換成一份明列的白名單，不是刪掉本條。**」

4. **`tests/test_wf02_health_golive.py:1224` `test_the_old_page_is_still_the_fallback`**
   `:1230` `assert OLD_SRC.exists()`、`:1236` `assert OLD_ENTRY[1] in _tops`
   → 規則 6 最後一步「合併刪舊」會讓它轉紅。

5. **`tests/test_wf04_old_block_inventory.py`** docstring 逐字：「**舊 ④ 一旦長出第 12 個區塊而沒有人登記，本檔當場轉紅**」
   —— 它每次 CI 重掃 `ui/tab3_portfolio.py`；刪舊即失去掃描對象。

6. **耦合規模**：`tests/` 下 **95 個檔案**以路徑字串引用 `ui/tab*.py`、**61 個檔案** `import ui.tab*`。

7. **同一張表混編新舊**：`tests/test_wpf_five_tab_wiring.py:563-593` `_LEGIT_EXEMPT` 內同時列
   `("ui/tab3_portfolio.py", ...)`、`("ui/views/page_03_research.py", ...)`、`("ui/tab6_manual.py", ...)`。

---

## 4. 本組沒查到的（照實寫）

- 母法〈專案重構終審令〉**原文查不到**（repo 內只有 `CONSTITUTION.md` 引用它）。
- 客戶六條裡「**共用層**」的定義**查不到**（六條本身沒定義，repo 內也沒找到對應清單）。
- 「凍結令是否已對客戶生效」**查不到** —— #837 目前是 **open + draft，未合併**。
- `pr829`~`pr834` 六個本地分支對應哪些 PR、是否屬那九個之內：**查不到**
  （GitHub 上 open PR 只有 #791/#799/#836~#845，號段對不上；本組未動這六個分支）。
- 本報告的掃描射程**未涵蓋**：動態 import（`getattr` / `importlib`）、非字面別名再呼叫、
  以及 `ui/` 以外可能存在的 UI 接線。**故本文所有清單為分類敘述，不宣稱窮舉。**
- 本組為單組實測，**沒有第二雙眼睛**看過。
