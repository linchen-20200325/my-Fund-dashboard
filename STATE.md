# STATE.md — 基金戰情室 (Fund Dashboard)

> **靜態架構地圖**。Roadmap 為高層粗略方向；**所有具體任務狀態以 [`BACKLOG.md`](./BACKLOG.md) 為準**。

---

## 🏗️ v11.0 分層架構重構（v18.109 — ✅ 完工 2026-05-16）

> 30 commits 完成 A-1 → E-30，根目錄業務檔 18 → 2，fast tier 357 → 359 零回歸。
> 詳細完工總結見 `ARCHITECTURE.md §0`。

### Phase A — 葉節點搬遷（無業務變更，低風險）
- [x] **A-1** 建 `infra/__init__.py` + 搬 `proxy_helper.py` → `infra/proxy.py`（+ shim）
- [x] **A-2** 搬 `oauth_helper.py` → `infra/oauth.py`（+ shim）
- [x] **A-3** 建 `models/__init__.py` + 搬 `policy_keys.py` → `models/policy.py`（+ shim）
- [x] **A-4** 從 `fund_ledger.py` 抽 dataclass（Transaction/FundPosition/Switch/SwitchResult/GhostComparison）→ `models/ledger.py`

### Phase B — Repository Layer（純 I/O 抽離）
- [x] **B-5** 建 `repositories/__init__.py` + 搬 `macro_core.py` → `repositories/macro_repository.py`（+ shim）
- [x] **B-6** 搬 `ledger_store.py` → `repositories/ledger_repository.py`（+ shim）
- [x] **B-7** 搬 `ledger_snapshot_store.py` → `repositories/snapshot_repository.py`（+ shim）
- [x] **B-8** 搬 `policy_store.py` → `repositories/policy_repository.py`（+ shim）
- [x] **B-9** 從 `fund_fetcher.py` 抽 `fetch_*` 系列 → `repositories/fund_repository.py`
- [x] **B-10** 從 `fund_fetcher.py` 抽 `fetch_market_news` → `repositories/news_repository.py`

### Phase C — Service Layer（業務邏輯歸位）
- [x] **C-11** 建 `services/__init__.py` + 搬 `macro_engine.py` → `services/macro_service.py`（+ shim）
- [x] **C-12** 抽 `fund_fetcher.calc_metrics` 等指標 → `services/fund_service.py`
- [x] **C-13** 搬 `fund_ledger.py` 剩餘類別 → `services/ledger_service.py`（+ shim）
- [x] **C-14** 搬 `portfolio_engine.py` → `services/portfolio_service.py`（+ shim）
- [x] **C-15** 搬 `precision_engine.py` → `services/precision_service.py`（+ shim）
- [x] **C-16** 搬 `backtest_engine.py` → `services/backtest_service.py`（+ shim）
- [x] **C-17** 搬 `ai_engine.py` → `services/ai_service.py`（+ shim）
- [x] **C-18** 搬 `policy_advisor.py` → `services/policy_advisor_service.py`（+ shim）

### Phase D — UI Layer（最大風險，拆 588 KB app.py）
- [x] **D-19** 建 `ui/components/` + 搬 `shared/macro_card*.py` / `mk_dashboard.py` / `mk_clock.py`
- [x] **D-20** 建 `ui/helpers/session.py` — 抽 `_update_data_registry` / `_check_secrets` / `_calc_data_health`
- [x] **D-21** 抽 Tab1 → `ui/tab1_macro.py`
- [x] **D-22** 抽 Tab2 → `ui/tab2_single_fund.py`
- [x] **D-23** 抽 Tab3 → `ui/tab3_portfolio.py`（最大塊，含 T5/T7）
- [x] **D-24** 抽 Tab4 → `ui/tab4_backtest.py`
- [x] **D-25** 抽 Tab5 → `ui/tab5_data_guard.py`
- [x] **D-26** 抽 Tab6 → `ui/tab6_manual.py`
- [x] **D-27** `app.py` 收口（剩 import + st.tabs(6) + 主入口，目標 <10 KB）

### Phase E — 收尾
- [x] **E-28** 修 17 個 `test_*.py` 的 `from` 路徑（一次性 batch）
- [x] **E-29** 刪除 Phase A-D 的 backward-compat shim
- [x] **E-30** 更新 `ARCHITECTURE.md §1-§6` 反映最終結構（§0 藍圖區塊封存）

### 守則（每步必跑）
1. 邏輯審查：diff 比對前後函式簽名 / 行為一致
2. 邊界測試：列 2-3 個 edge case（空輸入 / 底層斷線 / 異常）
3. 效能評估：import path 改動不引入循環 import
4. Debug 修正：路徑 / DI 潛在 bug 直接改 + 註解
5. 測試守門：`pytest -m "not slow"` 必須 **357 → 357 通過（零回歸）**

---

## 🚀 v11.1 後續優化（v18.117 → v18.144，2026-05-17 / 18）

> v11.0 完工後同日累積 36 個 PR — 涵蓋 AI 強化、tab 拆檔完工、cloud crash hotfix、helper 收口、sys.modules hack 全清、AppTest 防退化網。
> fast tier 359 → **460** passed（+101 新測試），app.py **9643 → 425 行（−95.6%）**。

### AI 系列（PR #165~#170, #193）
- [x] Phase 4 / 3-B 資料窗口拉長 + frequency-aware 治本（PR #165 #167）
- [x] AI-1 MK prompt 接 Phase 4 + 3-B 結論（PR #166）
- [x] AI-2 prompt 模板抽 `ai_prompts.py`（PR #168）
- [x] AI-3 多 provider fallback chain — Gemini → Claude → GPT（PR #169）
- [x] AI-4 `fund_json` 結構化 JSON 輸出 PoC（PR #170）
- [x] **v18.135** 單一基金 + MK AI 加「持股 × 新聞」交叉分析（PR #193）

### v12.0 backlog 完工（PR #171~#172）
- [x] B-A `fund_fetcher` HTTP 層收口到 `infra/proxy.py`（PR #171，順手修 fund_repository 30+ pre-existing NameError）
- [x] B-B `PrecisionStrategy.fetch_stock_three_ratios` I/O 拆 → `repositories/financial_repository.py`（PR #172）

### B-C 6 Tab 全部抽出（PR #173~#185）
- [x] B-C.1 Tab6 說明書 → `ui/tab6_manual.py`（PR #173）
- [x] B-C.2 Tab4 回測 → `ui/tab4_backtest.py`（PR #181）
- [x] B-C.3 Tab5 資料診斷 → `ui/tab5_data_guard.py`（PR #182）
- [x] B-C.4 Tab2 單一基金 → `ui/tab2_single_fund.py`（PR #183）
- [x] B-C.5 Tab1 總經 → `ui/tab1_macro.py`（PR #184）
- [x] B-C.6 Tab3 組合（最大 3897 行）→ `ui/tab3_portfolio.py`（PR #185）

### Cloud crash hotfix 系列（PR #186~#192）
- [x] PR #186-189 補 13 + 40 個漏 import helper（NameError 連環修）
- [x] PR #190 `MACRO_EDU` cross-ui/components 漏 import
- [x] PR #191 改用 `ui/helpers/macro_helpers.py` 取代 `sys.modules['__main__']` hack
- [x] PR #192 統一 Tab2 vs Tab3 1Y 含息報酬 fallback chain（修同基金兩 view 不同數字）

### 用戶部署反饋（issue rounds，PR #174~#180）
- [x] Round 1-6：PMI series fix / fund_repository 9 個 NameError / Tab2 partial block / NAS Proxy 可視化 / page_type fallback

### Helper 收口（PR #194 — 清單 1/2/3）
- [x] `_HOLDING_ZH` + `_zh_holding` 搬 → `ui/helpers/holdings.py`
- [x] `_update_data_registry` 搬 → `ui/helpers/data_registry.py`
- [x] OAuth chain (`_oauth_cfg / _resolve_oauth_cfg / _get_oauth_client` 等) → `ui/helpers/oauth_state.py`
- [x] **app.py 1164 → 425 行（−63.5%）**

### sys.modules hack 全清 + AppTest 防退化網（PR #196 — v18.139~v18.143）
- [x] **v18.139** `_sync_invest_twd_from_ledgers` 搬 `ui/helpers/data_registry.py` + 清 Tab1/2 `sys.modules['__main__']` 殘留
- [x] **v18.140** Tab3 OAuth chain 改正規 import + ARCHITECTURE §0 同步
- [x] **v18.141** AppTest seed `macro_done=True` → 進 `calculate_composite_score` 路徑（防 PR #186-191 同類 NameError）
- [x] **v18.142** AppTest `monkeypatch _oauth_configured=True` → 進 Tab3 OAuth-aware 分支
- [x] **v18.143** AppTest seed loaded fund + macro → 進 `mk_fund_signal` / `_quartile_check` / `_zh_holding` 鏈
- [x] **Tab1/2/3 徹底脫離 `sys.modules['__main__']` hack** + 三條關鍵分支補 AppTest 防退化網

### 累積最終狀態
- `app.py`：9643 → **425 行**（**−95.6%**，僅剩 sidebar + module init + 6 tab render call）
- 6 個 tab 完整 ui/tab*.py
- 5 個 helper module（session / macro_helpers / holdings / data_registry / oauth_state）
- fast tests：359 → **460**（+101 新測試）
- AppTest 互動測試：12 cases（含 3 個 v18.141-143 防退化新增）

### Polish 後續（v18.144 / v18.145，2026-05-18 / 19）
- [x] **v18.144** Tab3 T7 抽檔 → `ui/tab3_t7_ledger.py`（1978 行，含 A/B/C 落帳 + 帳本面板 + MK AI 深度建議）
  - `ui/tab3_portfolio.py`：3976 → **2001 行**（−49.7%）
  - `render_t7_section()` 零閉包依賴，全部狀態走 `st.session_state`
  - GEMINI_KEY 函式內部即時取，不靠 caller 注入
  - fast tier 零回歸（456 passed + 4 個 pre-existing 路徑硬編碼 bug 不在本次 scope）
- [x] **v18.145** 總經指南針 UI 標籤誠實化（PR #3）
  - `app.py:349/363` 把「即時抓取（無快取）」「禁用快取」改成「**5min TTL 快取**」反映實際 `@_ttl_cache(ttl_sec=300)` 行為
  - 零行為變更；避免使用者誤以為時間戳代表即時抓取時刻
- [x] **v18.146** 環境遷移防雷紀錄（docs only，無 code 變更）
  - 事故：環境遷移後 Streamlit Cloud 換新子網域，secrets 寫死的舊 `redirect_uri` → Google OAuth `redirect_uri_mismatch`
  - 修法：刪掉 secrets 裡寫死的 URL，讓 `ui/helpers/oauth_state.py` runtime 推導即可
  - 防雷註記寫進 `ARCHITECTURE.md §5.4`：secrets 只放 client_id/client_secret，URL 不入庫

### v18.147 雲端儲存 UX 對齊台股 ETF（2026-05-19）
- [x] **PR #6** `tab3` 雲端儲存加資料夾下拉過濾（移植自台股 PR #18）
  - `repositories/policy_repository.py`: `list_user_sheets(folder_id='')` + 新 `list_user_folders()`（走 Drive v3 API）
  - `ui/tab3_portfolio.py`: 「🔄 載入資料夾清單」按鈕 + 「📁 限定資料夾」selectbox + 清單來源 hint
- [x] **PR #7** OAuth wizard `redirect_uri` 防呆 — 自動補 `https://` 與結尾 `/`（移植自台股 PR #10）
- [x] **PR #8** Expander 內部順序對齊標題承諾「Sheet 設定 / 保單清單」
  - 把第 3 順位的「📊 帳本內容速覽」前移到第 2 順位 + 改名為「📋 保單清單（這本 Sheet 內的保單分頁與輔助 tab）」
  - 新順序：`Sheet 設定 → 保單清單 → 多帳本管理 → 一鍵存讀 → 本機 JSON 備份`
  - 純 UI cut-paste；保單 worksheet 多 tab 資料模型完全不動

### v18.148 OAuth wizard 套用設定 no-op bug 修補（2026-05-20）
- [x] **PR #9** `_oauth_configured` / `_oauth_cfg` 由 module-import-time snapshot 改 per-render refresh
  - 症狀：user 在 wizard 填 client_id/secret/redirect_uri + 按「💾 套用設定」沒反應，登入按鈕不亮
  - 根因：兩個 module-level 變數在 `ui/helpers/oauth_state.py` import 時 cache，session_state 寫入後 `st.rerun()` 不會重 run module body → snapshot 永遠 stale
  - 修法：新增 `refresh_oauth_state()` 公開函式；`render_portfolio_tab()` 開頭 + `app.py` sidebar 渲染前各呼叫一次，並 local 重 `from ... import` 拿 fresh 值
  - 旁路：使用 Streamlit Secrets `[google_oauth]` 永久設定者 reboot app 即可（一直能用），bug 只影響 session-only wizard 路徑
  - 新增單元測試 `test_refresh_oauth_state_updates_module_snapshot`；舊 `test_tab3_oauth_configured_branch_renders_without_exception` 改 monkeypatch `_resolve_oauth_cfg` 以相容 refresh

### v18.149 Schema v2 — snapshot-only 11 欄 + 多幣別現金（2026-05-20）
> 對齊使用者真實工作流程：「第一次輸入 → 日常編輯/存檔；真實加碼/贖回自己改 Sheet；T7 純模擬不寫資料」。
> 砍掉舊三 tab 結構（保單分頁 v1 + `_T7_State` + `_Ledgers`）→ 只剩**每張保單一個 worksheet** + 內聯持倉。
- [x] **PR A** Schema v2 後端 + migration 工具
  - `repositories/policy_repository.py` 加 v2 API：`ALL_COLS_V2`（11 欄）/ `is_v2_worksheet` / `detect_sheet_schema_version` / `load_policy_v2` / `write_policy_v2` / `load_all_policies_v2` / `copy_sheet_as_backup`
  - 新 schema 11 欄：`policy_id / item_type / fund_code / fund_name / units / avg_nav / avg_fx / currency / tier / amount / invest_twd`
    - `item_type="fund"`：基金列，填 fund_code/units/avg_nav/avg_fx/tier/invest_twd
    - `item_type="cash"`：現金列，填 currency/amount（支援多幣別現金部位）
  - `scripts/migrate_v149_schema.py` 一次性升級腳本：
    - `_fold_ledger_json` 把 `_T7_State.ledger_json` fold 算 weighted units/avg_nav/avg_fx
    - `migrate_one_policy` 單張保單 v1 → v2
    - `migrate_sheet(with_backup=True)` safety net：先 `copy_sheet_as_backup` 才動原本
    - 冪等：已是 v2 的 worksheet 自動跳過
  - `ui/tab3_portfolio.py` 加偵測 + 升級 UI（在「多帳本管理」與「一鍵存讀」之間）：
    - `[🔍 偵測目前 Sheet 格式]` 按鈕 → 顯示 v1/v2/empty
    - v1 → `[🚀 升級到 v2（先備份原 Sheet）]` 按鈕，跑完顯示備份連結 + 升級統計
    - v2 → `[👁️ 預覽 v2 schema 資料]` checkbox 顯示 read-only `st.dataframe`
  - 新增單元測試：`test_policy_store.py` +12 個 v2 測試 / `test_migrate_v149_schema.py` 12 個 fold + migration 測試（共 +24，總計 64/64 pass）
  - **本 PR 不動「一鍵存讀」與 T7 模組** — 既有 v1 路徑完整保留；user 跑完 migration 後可在 Google Sheet 上看到新 v2 schema，但日常存讀仍走 v1（PR B 才接 v2 編輯 UI）
- [x] **PR B v18.150 v2 native 編輯 UI** — `ui/helpers/v2_editor.py`（373 行）：
  - `render_v2_section(client, sheet_id)`：偵測到 v2 schema 時自動接管 UI（從 tab3_portfolio expander 內呼叫）
  - 每張保單一個區塊，內含 fund 與 cash 兩個 `st.data_editor`（dynamic rows）+ [💾 存到雲端] / [📥 重新讀回] / [🗑️ 刪除]
  - dirty tracking：本機編輯後標 `未存檔`，按存才推 `write_policy_v2`
  - [➕ 新增保單] 一鍵建 worksheet + 寫 v2 header（讓下次 detect 一致回 v2）
  - `render_first_use_wizard(client, sheet_id)`：empty sheet 顯示「🚀 第一次使用」按鈕 → 3-step wizard（保單名 + 第一檔基金 + 現金可跳過）
  - T7 模組（`tab3_t7_ledger.py`）開頭加紅字 banner：v2 下 T7 為純模擬器，真實加碼/贖回請至 v2 編輯介面或直接改 Sheet
  - 新增單元測試 `test_v2_editor.py`（split / merge / round-trip / drop empty rows，共 +8 測試，PR A 64 + PR B 8 = **72/72 pass**）
  - 注：本 PR 不動 v1 路徑、不切換「📦 全部寫入/讀回」主路徑（留 PR C）
- [x] **PR B.4 v18.154 T7「編輯持倉」對齊新 schema** — user 反饋這頁仍要 user 填 `持有單位數`，與「units 系統自動算」設計矛盾
  - `ui/tab3_t7_ledger.py:537` 表單欄位 4 → 5：
    - 砍 `持有單位數` 輸入 → 改 read-only `st.caption` 顯示 `compute_units` 自動算的結果
    - 加 🟨 `淨投資金額 (NT)` 輸入（取代 持有單位數，成為 source of truth）
    - 加 🟨 `平均買入含息單位成本 (10)` 輸入（對齊 v2 schema `avg_nav_with_div`）
    - 5 個 user input 全部加 🟨 icon prefix（黃色對齊 v2 編輯介面）
    - 即時顯示 `⬜ 持有單位數（自動算） ≈ X.XXXX · 公式：...`
  - Submit handler：
    - `if _inv <= 0` 取代 `if _u <= 0`（門檻改 invest_twd）
    - `_amount_twd = float(_inv)` 不再 `_u × _cu × _fx`
    - 把 `_inv` / `_anw` 也存進 `portfolio_funds[i]["invest_twd"]` / `["avg_nav_with_div"]`，給 v2 編輯介面同步使用
  - 89/89 pass

- [x] **PR B.3 v18.153 12 欄 schema + 中文 header + UI 自動填寫分離** — 對齊真實對帳單欄位、UI 黃灰配色區分 user 填寫 vs 自動帶
  - **Schema 12 欄**（加 `avg_nav_with_div` 平均買入含息單位成本，對帳單欄(10)）：`policy_id / item_type / fund_code / fund_name / units / avg_nav / avg_nav_with_div / avg_fx / currency / tier / amount / invest_twd`
  - **欄位填寫責任分類**：
    - 🟨 `USER_INPUT_COLS`：`policy_id / fund_code / avg_nav / avg_nav_with_div / avg_fx / amount / invest_twd`（從對帳單抄）
    - ⬜ `AUTO_COLS`：`item_type / fund_name / units / currency / tier`（MoneyDJ / 公式 / 系統）
  - **Sheet 中文 header 雙向翻譯層**：`ZH_HEADERS_V2` mapping，`load_policy_v2` 讀進來自動翻譯回英文 col name，`write_policy_v2` 寫中文 header；`is_v2_worksheet` 同時認 `item_type` 與 `類型`
  - **Sheet header 配色** `_apply_v2_header_format()`：user-input 黃 (#fff2cc) / auto 灰 (#e0e0e0)，全部 bold
  - **`compute_units()` 公式自動算**：`units = invest_twd / (avg_nav × avg_fx)`（對帳單公式 (4) 反推），對齊截圖實例 1781.025 ✓
  - **Wizard 簡化**：只露 6 個 user-input 欄位（policy_id / fund_code / avg_nav / avg_nav_with_div / avg_fx / invest_twd + cash），fund_name / currency / units / tier 自動帶；`_autofill_from_moneydj()` 在存檔時自動抓 MoneyDJ
  - **`st.data_editor` 加 `disabled=True` 與 🟨/⬜ icon hint**：user-input 黃 icon、auto 灰 icon read-only；user 編完按存到雲時對缺漏自動補 MoneyDJ
  - **Migration 預設 `avg_nav_with_div=0`**（v1 → v2 沒這個值，user 之後到對帳單抄）
  - 單元測試 +6 個（12 欄 schema / USER vs AUTO 互斥完整 / ZH-EN round-trip / compute_units 對齊截圖 / 零分母 / `_normalize_header_to_en`）+ 更新 v2_editor 測試 9 欄 fund 表 & 12 欄 merged & units 自動算優先
  - 總計 **89/89 pass**（PR A 64 + PR B 8 + PR B.1 6 + PR B.2 4 + PR B.3 7）

- [x] **PR B.2 v18.152 Google Sheets 429 quota 退避 + 60s cache + 友善訊息** — 修補 v2 編輯介面進場一次 1+2N reads 爆配額的 bug
  - `repositories/policy_repository.py` 加 `_QUOTA_BACKOFFS` + `_is_quota_error` + `_with_quota_retry`（與 `snapshot_repository` 一致，1s→2s→4s→8s 共 4 次）
  - `list_policy_worksheets` / `is_v2_worksheet` / `detect_sheet_schema_version` / `load_policy_v2` / `write_policy_v2` / `load_all_policies_v2` 全部包 `_with_quota_retry`
  - `ui/helpers/v2_editor.py` 加 `st.cache_data(ttl=60)` wrapper：`_cached_list_policies` / `_cached_load_policy_v2`（client 用 `_client` 底線前綴避 hash），寫入/刪除/重讀後 `_invalidate_cache(sheet_id)`
  - 友善 429 訊息 `_show_quota_friendly()`：偵測「Quota exceeded / RATE_LIMIT / 429」→ 改顯示「⏳ Google Sheets API 配額暫時超載...請等 30-60 秒再點任何按鈕重整」，並加 `[🔄 重試（清快取）]` 按鈕
  - 單元測試 +4 個：`test_is_quota_error_detects_common_signatures` / `test_with_quota_retry_eventually_succeeds` / `test_with_quota_retry_non_quota_error_raised_immediately` / `test_with_quota_retry_persistent_429_eventually_raises`
  - 總計 PR A 64 + PR B 8 + PR B.1 6 + PR B.2 4 = **82/82 pass**

- [x] **PR B.1 v18.151 載入按鈕上移 + 未綁基金快捷** — 反映「載入按鈕滾不到」與「未綁保單意思不清」用戶反饋
  - 抽 `ui/helpers/portfolio_load.py`：`count_unloaded_funds()` + `batch_load_unloaded_funds()`（從原 `tab3_portfolio.py:1656` ~70 行 fetch 邏輯整塊抽出）
  - 「🗂️ 保單分組視圖」expander 頂部加 prominent `[📡 載入未載入基金（N 條 / M unique code）]` 按鈕 — user 不用滾到底
  - 「📂 未分組基金」區塊加 inline 提示「⚠️ 你有 N 檔未綁保單」+ 兩個快捷按鈕：
    - `[📡 載入這 N 檔]`（同效，就近點）
    - v2 用戶獨享：`[🔗 綁到保單 ▾]` selectbox → 一鍵把所有未綁基金 set `policy_id`
  - 原 `tab3_portfolio.py:1656` 那段 fetch 邏輯改 1 行 call helper
  - 單元測試 `test_portfolio_load.py` 6 個（empty / all loaded / mixed / dedupe / drop empty code / missing session_state）
  - 總計 PR A 64 + PR B 8 + PR B.1 6 = **78/78 pass**
- [ ] **PR C**（下一輪）「📦 全部寫入/讀回」切換到 v2 主路徑（v2 sheet 自動走 v2）
- [ ] **PR D**（之後）移除舊 `_T7_State` / `_Ledgers` tab 寫入路徑 + 文件 cleanup

---

## 專案定位
Streamlit Cloud 部署的境外共同基金監控儀表板。整合總經位階、單一基金診斷、組合再平衡試算、歷史回測、資料診斷五大模組。

## 模組地圖
| 檔案 | 職責 |
|------|------|
| `app.py` | Streamlit UI 入口（Tab1~Tab6）+ session state 管理 |
| `macro_core.py` | FRED / yfinance 資料抽象層（含 next_release_date 動態 stale 判斷）|
| `macro_engine.py` | 總經指標評分、景氣位階、衰退機率、景氣時鐘 |
| `tw_macro.py` | 台股 TPI 指標 |
| `fund_fetcher.py` | MoneyDJ / FundClear / TDCC 基金抓取 + NAV / FX 快取（v18.23 模組層 `_install_global_urllib_proxy()`）|
| `fund_ledger.py` | 通用型基金帳務引擎（CHUBB 11 欄位、Switch 同/跨幣別、XIRR）|
| `portfolio_engine.py` | 六因子評分、相關性、Kelly、holdings_overlap |
| `precision_engine.py` | σ 絕對位階、複合風險溫度計、微觀防護盾 |
| `ai_engine.py` | Gemini AI 分析引擎 |
| `backtest_engine.py` | 歷史回測 + 績效指標 |
| `proxy_helper.py` | NAS Proxy HTTP 中繼工具 |
| `mk_dashboard.py` | MK 智能戰情室：核心戰情室 / 波段觀測站 / 3-3-3 篩選器（v18.34 分析視圖按 code 去重）|
| `policy_keys.py` | 保單視圖：複合鍵 `(policy_id, fund_code)` ↔ `pid::code` pk_str 工具 |
| `policy_advisor.py` | 保單視圖：純規則建議引擎（σ × 配息覆蓋 × 60MA × VIX）+ `recommend_policy()` |
| `policy_store.py` | gspread 儲存層：Service Account / OAuth、每保單一 worksheet API |
| `oauth_helper.py` | Google OAuth 2.0 web flow（refresh_token + auto-refresh）|
| `ledger_store.py` | `_Ledgers` 系統 tab：append-only 交易帳（policy_id, date, action, units, twd, …）|
| `ledger_snapshot_store.py` | `_T7_State` 系統 tab：T7 帳本 JSON snapshot 跨刷新還原 |

## Tab 結構
- Tab1 總經儀表板：景氣位階、Sankey 因果鏈、事件驅動建議
- Tab2 單一基金深度：MK 操作訊號、布林帶、三合一趨勢圖、微觀防護盾
- Tab3 組合基金：核心衛星比例、T5 持股 + 產業重疊度、T7 帳務試算（A 新投入 / B 投入再平衡 / C 1→N 轉換）+ 帳本面板
- Tab4 歷史回測
- Tab5 資料診斷中控台 Data Guard
- Tab6 系統說明書

## 關鍵測試
- `test_fund_ledger.py` — 27 項（Phase 1 引擎 + Phase 2 Switch / XIRR + JSON + 1→N 守恆）
- `test_holdings_overlap.py` — 5 項
- `test_macro_core.py` / `test_tw_macro.py` — `test_macro_core.py` 26 cases（**v18.21 補完** 倒掛翻正回測 3 case）
- `test_app_smoke.py` — 27 項（AST 編譯 + expander 巢狀偵測（跨檔 transitive）+ except:pass 偵測 + _zh_holding 對照單元）
- `test_app_apptest.py` — 4 項（Streamlit AppTest runtime e2e，pytest 標 `slow`）
- `test_backtest_engine.py` — 14 項（**v18.17 補完** Sharpe/Sortino/MaxDD/Calmar + 邊界 + freq 參數）
- 全套 commit 前自動執行（pre-commit hook）：`pip install -r requirements-dev.txt && pre-commit install`
- 遠端 PR 自動執行（GitHub Actions）：`.github/workflows/pr-check.yml`

## 部署
- 平台：Streamlit Community Cloud + GitHub
- 主分支：`main`
- API 金鑰：`FRED_API_KEY` / `GEMINI_API_KEY`（Streamlit Secrets）
- 全域禁用 `@st.cache_data`，除非另有明確授權

## Roadmap（熱資料：高層方向，逐項細節見 BACKLOG.md）
- 🟢 **總經指南針 Phase 2**：PR #39 為 Phase 1（Tab1 頂部三大美股指標）；Phase 2 範圍未定，待規格輸入。
- 🟢 **`_HOLDING_ZH` 持續擴充**：PR #43 後 277 keys 覆蓋美/歐/台/日/韓/陸港/印度/東南亞；視 hit-rate 補澳紐/拉美。
- 🟢 **驗證金字塔**：
  - 靜態 ✅ — `test_app_smoke.py` 27 cases（AST + expander 巢狀 + except:pass + _zh_holding；PR #46/#49）
  - pre-commit ✅ — `.pre-commit-config.yaml` + `requirements-dev.txt`（PR #48）
  - AppTest Phase A ✅ — `test_app_apptest.py` 4 場景 + `slow` marker 雙車道（PR #51 三場景 + PR #55 第二場景）
  - CI Phase C ✅ — `.github/workflows/pr-check.yml`（fast-checks 阻擋 / slow-tests informational）
  - AppTest Phase A 擴充 🟡 — Ideas 區 3 個場景候選（Tab3 KPI / Tab2 view_mode / T5 重疊度）
  - Playwright Phase B 🟢 — 3 個關鍵 tab screenshot diff 待規劃

## 近期里程碑（冷資料：已完成 PR 紀錄，詳見 BACKLOG.md Done 區）
- PR #104 — refactor(t3): v18.54 移除 T7 重複的「存檔到 Sheets / 從 Sheets 讀取」雙鈕（與上方「📦 全部寫入 / 📥 全部讀回」重複），統一由上方入口；批次加入 caption 改成「2 步驟流程」明示加代碼 → T7 編輯持倉 → 一鍵存
- PR #102 — feat(fetch+tab5): v18.53 境內基金 1Y 含息報酬本地計算（NAV + 累積配息）+ Tab5 累積型基金「N/A 不適用」灰標 — 解決 wb01 為境外專屬頁、境內基金 1Y含息報酬永遠缺失的結構缺陷
- PR #100 — fix(t3+sheets+fetch): v18.50/51/52 三合包 — (50) 帳本內容速覽 3 metrics +「📦 全部寫入 / 📥 全部讀回」一鍵雙鈕串聯三 tab；(51) `_src_tcb_div` 修「tcbbankfund 對部分境內代碼回空頁就 break、主站 fallback 永遠不啟動」bug → ACCP138 / ACTI71 配息抓取恢復；(52) hoist `_sync_invest_twd_from_ledgers` 到模組層解 T7 NameError + 全部讀回補 sync 讓 invest_twd 從 _T7_State 灌回 + 移除保單分頁內重複「新增 / 更新基金」大表單
- PR #98 — feat(t3+t2): v18.48 多帳本管理 UI（建立/改名/切換）+ v18.49 配息率 divs 歷史 fallback
- PR #97 — hotfix: 補推 policy_store.rename_sheet / get_sheet_title 救 ImportError 起不來
- PR #96 — fix(t2+t3): v18.48 1Y fallback 日期版 + Tab3 真實收益分「真 0%」與「資料不足」
- PR #95 — feat(tab2): v18.47 基金健康總覽大卡（4 維度評分 + Overall Grade A-F + 白話結論）
- PR #94 — feat(sheets+ux): v18.45/46 從 Drive 選 Sheet + 按鈕用語直白「存檔/讀取」+ 歡迎卡緊湊
- PR #92 — fix(sheets): v18.44 自動建 Sheet 後 StreamlitAPIException — widget key 改用刪 reinit
- PR #90 — fix(t3): v18.43 資產成長曲線 dedupe by code + OAuth 403 scope 提示重登入
- PR #89 — fix(tab2): v18.42 吃本金檢查卡 1Y 含息報酬 fallback 鏈（metrics → perf → NAV 年化外推）
- PR #87 — fix(t7+sheets): v18.41 強化「開啟 Sheet 失敗」診斷訊息（補 type(e).__name__ + ID 前綴）+ T7 inline URL 解析 + 顯示綁定 ID
- PR #85 — feat(sheets): v18.40 一鍵自動建立 Google Sheet（policy_store.create_dashboard_sheet helper + Tab3 自動建檔按鈕；免去先到 Drive 開檔）
- PR #83 — fix(t3): v18.39 三合一 — Sheet URL 自動解析 / pid 反查代入 / 預估月配息卡修零（讀錯 schema key）
- PR #81 — fix(t3): v18.38 真實收益 vs 配息率矩陣按 code 去重
- PR #79 — feat(t3): v18.37 投資組合主清單按保單號碼分組成 expander（取代 v18.35 per-fund expander，避免 expander 巢狀）
- PR #77 — fix(t3): v18.36 T5 重疊度按保單分組 + 修 pyarrow Duplicate column names 例外（同 code 跨多保單矩陣欄名衝突）
- PR #76 — feat(t3): v18.35 投資組合主清單每檔「💡 advice + 📍 MK 訊號」包進 expander（預設收合，KPI 列永遠可見）
- PR #75 — docs(state+arch): v18.34 模組地圖 + 目錄樹補 7 個新模組（mk_dashboard / policy_* / oauth_helper / ledger_*）
- PR #74 — docs(backlog): 補 PR #71/#72/#73 drift
- PR #73 — fix(mk): v18.34 MK 戰情室分析視圖按 code 去重（同基金跨多保單只算一筆；T7 帳本仍以 (code, policy_id) 分流）
- PR #72 — feat(t3): v18.33 批次加入基金 — text_area 多檔貼上 + ThreadPoolExecutor(4) 並行 fetch + st.progress 進度條
- PR #71 — docs(backlog): 補 PR #62-#70 drift（保單視圖 + Google Sheets 整合系列對齊）
- PR #70 — feat(oauth): v18.32 in-app OAuth Client 引導 wizard（免改 secrets.toml；session-only 套用）
- PR #69 — fix(t3): v18.31 同 code 不同保單能共存（複合鍵檢查）+ KPI vs 表格差額來源說明
- PR #68 — feat(t3+t7): v18.30 T7 inline OAuth 登入 + 主清單每檔顯示 advise 字眼（_compute_advice_for helper）
- PR #67 — feat(t7): v18.28+29 T7 加 policy_id 欄 + JSON 存檔 + `_T7_State` snapshot tab 雙向直連 Sheets
- PR #66 — feat(t3+t7): v18.27 加入即綁保單 + A/B/C 落帳同步進 `_Ledgers`
- PR #65 — fix(t7): v18.26 市值 NT$0（FX fallback chain 補 position.fx_avg）+ -100% 綠色 ↓ 假象修復
- PR #64 — feat(oauth+sheets): Google Sheet OAuth + 每保單一 worksheet + T7 帳目同步（4 phase 封包）
- PR #63 — fix(fetch): v18.23+24 Tab3 抓不到資料（`_install_global_urllib_proxy()` 攔截 30+ 處裸 urlopen → NAS Squid）
- PR #62 — feat(policy): 保單視圖 P1+P2+P3 封包（policy_advisor / policy_store / policy_keys / Tab3 改造 / T7 複合鍵 / mini 甜甜圈）
- PR #60 — feat(macro): v18.20+v18.21 三合一 — Tab2 吃本金 KPI 紅綠燈 / Tab1 景氣拐點監控（PMI 新訂單擴散 + 10Y2Y 倒掛翻正）/ 倒掛翻正歷史回測子卡（30Y T10Y2Y × ^GSPC 6/12/18M）/ FRED CCSA·CPI·FEDFUNDS 鮮度標籤改用 next_release_date 動態判斷
- PR #56 — refactor(backtest): backtest_engine 排毒（iterrows 死碼 / weights ZeroDiv 防護 / freq 參數）+ 14 cases 單測 + ARCHITECTURE §4.5b
- PR #55 — test(apptest): AppTest 第二場景—Tab1 缺 FRED_API_KEY 降級警告
- PR #54 — build(ci): GitHub Actions PR 檢查 workflow（Phase C 落地）
- PR #51 — test(apptest): Streamlit AppTest 首炮 3 場景 + slow marker 雙車道
- PR #49 — fix(tab5): 修兩個 except:pass 沉默吞例外 + AST 偵測護欄
- PR #48 — build(ci): pre-commit hook 強制驗證機制 + 修 trend_arrow 反彈誤判
- PR #46 — test(smoke): test_app_smoke.py 26 cases
- PR #43 — feat(holdings): 擴充亞太企業中文對照 + T5 影子基金共同持股顯示
- PR #41 — fix(tab3): 修復 MK 戰情室 expander 巢狀錯誤
- PR #40 — fix(tab2): 趨勢診斷圖 y 軸修正 + 持股外企中文對照
- PR #39 — feat(macro): 總經指南針 Top-Down Macro Phase 1
- PR #37 / #38 — MK Phase 3 共同基金規格補齊（三紅綠燈 / Sparkline / 配置比例）

## 動態任務追蹤
本檔之上為**摘要**（高層 Roadmap + 已 merge 里程碑）。逐項細節（含 Next / Ideas、checkbox 進度）見 [`BACKLOG.md`](./BACKLOG.md)。
