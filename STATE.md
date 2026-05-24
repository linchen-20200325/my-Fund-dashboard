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
- [x] **PR B.5 v18.155 Drive Sheets 列表過濾已刪除** — user 反饋下拉清單出現重複 / 殭屍項目（已刪除的、舊備份等都在）
  - `list_user_sheets` 從 gspread `list_spreadsheet_files()` 改成自己打 Drive v3 API（mirror `list_user_folders` pattern）
  - 加 `trashed=false` 過濾，再加 `mimeType="...spreadsheet"` 過濾
  - 支援 paging（`nextPageToken`）與 shared drives（`supportsAllDrives` / `includeItemsFromAllDrives`）
  - folder_id 非空 → 加 `'FOLDER_ID' in parents` 縮限
  - 測試 +2（filter_trashed_via_query / folder_id_adds_parents_filter）+ 3 個 existing 改 mock `http_client.request`
  - 91/91 pass

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
- [ ] **PR C**（#3，**v18.178 延後**）「📦 全部寫入/讀回」切換到 v2 主路徑 — 觸及真實 Sheet 持倉、沙箱無法 round-trip 驗證，**詳細實作計畫見 `BACKLOG.md` 🚧 Next**，需有 Sheet 憑證 + 副本驗證的 session 執行
- [ ] **PR D**（#4，**v18.178 延後**）移除舊 `_T7_State` / `_Ledgers` 寫入路徑 + 文件 cleanup — 破壞性，須 PR C 上線且真實資料驗證 OK 後才做（計畫見 `BACKLOG.md`）

### v18.157 對帳單 type B 支援（累積配息反推含息成本）（2026-05-20）

- [x] **背景** v18.153 加 `avg_nav_with_div`（平均買入含息單位成本）對齊 CHUBB 對帳單欄(10)。User 發現另一格式對帳單（例 USDEQ6200）**沒有此欄**，只有「**累積現金配息金額 (NT)**」+「累積含息回報率」
- [x] **後端 helper** `repositories/policy_repository.py:avg_nav_with_div_from_cumul_div_twd(avg_nav, avg_fx, units, cumul_div_twd)` 公式：`avg_nav − (cumul_div_twd / (avg_fx × units))`，clamp ≥ 0；user 截圖實例驗證 8.25/31.0885/3900.05/49913 → 7.838 ✓
- [x] **UI radio toggle** v2 編輯介面 wizard 與 T7「編輯持倉」表單兩處都加 `📋 對帳單格式` 選項：
  - A. 有「平均買入含息單位成本」→ 直接抄欄(10)（既有行為）
  - B. 只有「累積現金配息金額 (NT)」→ submit 時用 helper 換算成 `avg_nav_with_div` 存進去
- [x] **Schema 不動** — 仍 12 欄，內部統一存 `avg_nav_with_div`；type B 對帳單只在 input UI 層多一個換算步驟
- [x] 測試 +3（user 截圖實例 / 零配息 round-trip / 壞輸入 safe）= 94/94 pass

### v18.156 hotfix — Tab3「保單分組視圖」載入按鈕 nested expander crash（2026-05-20）

- [x] **事故** v18.151 抽 `ui/helpers/portfolio_load.py` 後，`batch_load_unloaded_funds` 內用 `st.status` 包 progress / log。該 helper 被 tab3 `with st.expander("🗂️ 保單分組視圖")` 內的「📡 載入未載入基金」按鈕呼叫 → `st.status` 本質是 expander → `StreamlitAPIException: Expanders may not be nested inside other expanders`
- [x] **修法** `ui/helpers/portfolio_load.py` Step 1 把 `st.status(...) as ld_status` 改成 `st.empty()` placeholder（動態 label）+ `st.progress` + `st.write` 平面組合；UX 保留（開始 / 載入中 / 完成皆有狀態提示 + 進度條 + 逐檔 ✅/❌ log）
- [x] **影響範圍** 3 處 call sites（L1052 頂部捷徑 / L1252 未綁保單快捷 / L1721 主清單下方）一次修復，helper 從此 context-agnostic
- [x] **驗證** smoke + portfolio_load test 共 **101 passed** 零回歸
- [ ] **後續觀察** `test_app_smoke.py` 的 expander 巢狀偵測只看 `st.expander` literal，未涵蓋 `st.status`／其它 expander-like API；下次踩到再補偵測（先記在 backlog）

### v18.192 — Task2.1 教學化：量化指標加「💡 這代表什麼」白話文 expander（2026-05-24）

- [x] **目標**（v5.0 Task2.1）：新手看得懂、老手有深度，**不藏任何專業數據**——複雜指標旁加收合 expander，白話解釋 + 資產配置實戰意義
- [x] **集中收口**：新增 `ui/helpers/metric_explainers.py`——`METRIC_EXPLAINERS` dict（sharpe/sigma/alpha/beta/mdd/core_satellite/div_coverage/overlap 共 8 條，含實戰意義）+ 純函式 `explainer_markdown(keys)`（可測）+ `render_metric_explainer(keys)`（就近渲染 `st.expander`、無內容不渲染）。內容/渲染分離
- [x] **接線**（不動任何既有數據顯示、純加法）：Tab2 風險指標 col_a（波動σ/Sharpe/Alpha/Beta）下方加 `["sharpe","sigma","alpha","beta"]`；Tab3 核心/衛星 Hero 下方加 `["core_satellite","div_coverage"]`
- [x] **巢狀防呆**：兩處 call site 經查皆非在 `st.expander` 內（Tab2 在主視圖 col_a、Tab3 在函式體 indent4）→ 不觸發 v18.156 巢狀 expander crash
- [x] **驗證** AST PASS；ruff clean；新增 `test_metric_explainers.py` 5 test（已知/未知 key/空輸入/欄位齊全/spec 點名指標）；`test_metric_explainers + test_app_smoke + test_tab2_single_fund + test_tab3_portfolio` 109 PASSED；AppTest 渲染驗證

### v18.191 — 讀取齊全：讀回/還原時用帳本補齊 portfolio_funds spine + 回填成本（2026-05-24）

- [x] **問題場景**（user）：「讀取資料時帳本一直缺資料，只要讀取齊全就好」
- [x] **以 user 實際 JSON 備份驗證**：portfolio_funds(19) ⨝ t7_ledgers(19) pk **100% 對得上**、`Ledger.from_dict` 19/19 解析成功含完整成本（units/cost_unit/fx_avg/cost_unit_with_div）→ **JSON 還原本身是齊全的**。缺料發生在 Sheet 讀回：表單/帳本表都以 portfolio_funds 為主軸迭代、再用 `fund_pk_str` 取 t7_ledgers 成本；保單分頁（→portfolio_funds）與 `_T7_State`（→t7_ledgers）漂移時，只在快照裡的基金會「看不到」
- [x] **Fix**：新增純函式 `reconcile_funds_with_ledgers(funds, t7_ledgers)`（`ui/helpers/portfolio_load.py`）—（1）帳本有但 portfolio_funds 沒有的部位→以 `parse_pk` 還原 (policy_id, code) 補成 spine 條目（loaded=False）（2）回填成本基礎 avg_nav/fx_avg/units/avg_nav_with_div（**缺值才補、不覆蓋既有**）。接 `load_all_from_sheet`（`_T7_State` 讀回後）與 `restore_from_json_bytes`（還原後）兩條讀取路徑；report 加 `reconciled_added`
- [x] **實證**：模擬 Sheet 漂移（保單分頁只回 5/19）→ reconcile 後補回 14 檔、19 檔全有 spine + 成本（ACTI71: avg_nav=8.67/fx=32.35/units=1780.94/含息=6.9655）
- [x] **驗證** AST PASS；ruff clean；新增 4 reconcile test；`test_portfolio_load + test_cloud_io + test_json_backup + test_app_smoke` 132 PASSED 零回歸

### v18.190 — log 降噪：Styler.applymap→map（pandas 3.0）+ 精準引擎資料不足降 debug（2026-05-24）

- [x] **問題場景**（user Cloud log）：① `tab3_t7_ledger.py:1995` + `tab3_portfolio.py:2053` `Styler.applymap` FutureWarning（pandas 2.1 deprecate、3.0 移除）② `precision_service` 每次 rerun 刷「對齊後資料筆數不足 20（實際 0）」「宏觀數據筆數不足」WARNING
- [x] **Fix**：(1) 兩處 `.style.applymap(` → `.style.map(`（pandas≥2.1 API）；`requirements.txt` pandas floor 2.0.0→2.1.0（保證 `.map` 存在、`applymap` 在 3.0 已移除）(2) `precision_service.py` 兩處 `logger.warning`→`logger.debug`（資料不足→回中性 0.0/空 df 是預期降級、Tab1 UI 已另顯友善提示，不該每 rerun 刷 WARNING）
- [x] **註**：宏觀資料實際 0 筆是部署端 FRED/yfinance 可用性問題（VIX/HY/殖利率對齊後 <20），非本次 scope；本次只降噪
- [x] **驗證** AST PASS；ruff clean；`test_app_smoke + test_tab3_portfolio + test_engines` 126 PASSED 零回歸

### v18.189 — 「存檔無含息來源」§5 除錯協議：全部寫入失敗不再靜默 + 釐清 v1 欄名為英文（2026-05-24）

- [x] **user 回報症狀①**：「Google Sheet 保單分頁存完沒有『含息成本』這欄位」
- [x] **完整追蹤（per-policy 寫+讀全正確、不盲改）**：user 走 per-policy 分頁路徑（如 QL19676552）→ `upsert_fund_in_policy` 表頭缺欄會自動升級成 ALL_COLS 11 欄（`A1:K1`）、`_row_to_list` 依序輸出 11 值含 `avg_nav_with_div`(K 欄)；legacy 單表 `upsert_policy_row` 才不強制升級（非 user 路徑）。`load_policy_worksheet` reindex ALL_COLS、sync 有值才帶 — 全對
- [x] **§5 除錯協議（不再盲改第 4 次）**：(1) `dump_all_to_sheet` 原 `except (PolicySheetError, OAuthError): continue` **靜默吞** per-fund 寫入失敗 → 改收集失敗 (pid/code + 原因) 進 `out["warnings"]`，下次「全部寫入」若真的寫失敗（配額/權限/表頭升級失敗）畫面會顯示根因，而非默默漏欄；(2) 釐清 v1 保單分頁表頭是**英文 key**（`avg_nav_with_div` / `div_cash_pct`），非中文「平均買入含息單位成本」（後者只在 v2 schema）→ user 若找中文欄名會誤判「沒有」
- [x] **待 user 驗證**：① 找英文欄 `avg_nav_with_div`（K 欄）；② 確認部署的 app 已更新到含 v18.183 的 main（Streamlit Cloud reboot）；③ 再按「全部寫入」看有無新 ⚠️ 寫入失敗提示
- [x] **驗證** AST PASS；ruff clean；新增 1 test（per-fund 寫入失敗進 warnings）；`test_cloud_io` 13 PASSED 零回歸

### v18.188 — 移除「多帳本管理」區塊（改用存取/讀取管理多帳本）（2026-05-24）

- [x] **決策**（user）：「取消多帳本管理，帳本管理改用存取、讀取的方式，就不用切換」——切換帳本一連串 stale bug（v18.185/187）後，user 決定不要獨立的「切換到此帳本」流程
- [x] **移除**（`ui/tab3_portfolio.py`）：整個「📁 多帳本管理（不同人/帳戶各自一本）」區塊（123 行）——含「🆕 建立另一本 / 📝 改名目前帳本 / 🔁 切換到別本」三個 tab；順手刪只此處用到的 `rename_sheet` import
- [x] **替代路徑**（皆既有）：切換 → 「📥 雲端讀取（從 Drive 挑帳本）」挑一本即自動讀回（v18.185 auto-load）；建立 → 頂部「✨ 新增帳本」；改名 → 直接在 Google Drive 操作
- [x] **保留**：v18.185 auto-load（挑帳本後自動讀回 + 共用基金資訊）、v18.187 t7_ledgers 空→清，仍適用於「挑帳本」路徑（`policy_sheet_id` 改變即觸發）
- [x] **驗證** AST PASS；ruff F821 無未定義名、無殘留變數（`_cur_title`/`_ms2` 等隨區塊移除）、`rename_sheet` import 清除；`test_app_smoke + test_tab3_portfolio` 99 PASSED 零回歸；無 test 引用被移除的 widget key

### v18.187 — 修「切換帳本後帳本無法更新」：load 一律覆蓋 t7_ledgers（空→清）（2026-05-24）

- [x] **問題場景**（user）：①「存檔無含息來源」②「切換帳本後，帳本那些都無法更新」
- [x] **#2 根因（v18.185 auto-load 放大）**：`load_all_from_sheet`（`ui/helpers/cloud_io.py`）只在 `_restored`（新帳本 `_T7_State` 快照）非空時才 `ss["t7_ledgers"]=_restored`；切換到「沒有 `_T7_State`」的帳本時 t7_ledgers **殘留前一本** → 持倉換了、T7 帳本面板卻還是舊本。v18.185 把切換改成自動讀回後，此 stale 每次切換都出現
- [x] **#2 Fix**：改 `ss["t7_ledgers"] = _restored or {}`（空→清掉舊本）；`_t7_auto_restore_done`/`_t7_auto_estimate_done` 旗標**一律**清（移出 `if _restored`）→ 新本無快照時 T7 區塊重跑 auto-restore（`tab3_t7_ledger.py:200`）、t7_ledgers 維持空（正確）不再顯示舊本；`_sync_invest_twd_from_ledgers()` 仍只在有快照時呼叫（避免空帳本把 invest_twd 歸零）
- [x] **#1 含息來源（§5 anti-loop，不盲改）**：完整追蹤寫+讀 round-trip 全正確 — T7 表單寫 `portfolio_funds["avg_nav_with_div"]`（`_fund_by_pk` 是 portfolio_funds 參照）+ `cost_unit_with_div` + 保單分頁；`dump_all_to_sheet` / `upsert_fund_in_policy`（ALL_COLS 含該欄 + 表頭自動升級）/ `load_policy_worksheet`（reindex ALL_COLS）/ `sync`（有值才帶）皆正確。已在 v18.180/183/184 修過 3 次仍報 → 依 §5 停止盲改，**待 user 給精確重現**（哪個存檔鈕 / 看哪裡為空）。v18.187 staleness 修復可能順帶修好「切換後含息成本顯示舊本」
- [x] **驗證** AST PASS；ruff clean（順手刪 `test_cloud_io` dead import `pytest`）；新增 2 regression test（空快照清舊本+清旗標 / 有快照換新本）；`test_cloud_io + test_app_smoke + test_portfolio_load` 119 PASSED 零回歸

### v18.186 — 連線健檢 #1：RSS 新聞走 NAS Proxy + timeout + 友善空狀態（2026-05-24）

- [x] **背景**（v5.0 Task1 連線健檢）：盤點互動元件與外部抓取流程的穩定度，目標所有抓取走 NAS Proxy + timeout + try-except + 友善降級
- [x] **稽核結果（互動元件全活）**：Explore 標的 8 個可疑 selectbox/slider/button 逐一實讀驗證 — 全 LIVE（值都有被消費）；特別 `tab5_data_guard.py:301 _snap_sel` 確認有用（L306-318 算 head5 表）且已有空狀態提示（L321-322），**非死按鍵**（防幻覺：未盲改）
- [x] **真實 gap：news RSS 沒走 Proxy**（`repositories/news_repository.py`）：原 `feedparser.parse(feed_url)` 裸連、無 timeout、`except: pass` 靜默 → Streamlit Cloud IP 被封時新聞整條死且無提示（fund_fetcher / fund_repository 全局 urllib opener / macro_repository 早走 proxy，news 是最後一條裸連）
- [x] **Fix**：(a) 改 `infra.proxy.fetch_url(url, timeout=12, retries=2)` 抓 bytes 再 `feedparser.parse(bytes)`（含 407/403×2 自動降級直連）；無 infra 時退回直連（行為相容）；(b) 抓取失敗累計 `failed` 來源不再靜默；(c) 結果為空回友善提示，區分「⚠️ 全失敗可能 Proxy 斷」vs「ℹ️ 正常但無命中關鍵字」。簽名 `fetch_market_news(max_per_feed)` 不變（callers 零修改）
- [x] **驗證** AST PASS；ruff clean；新增 `test_news_repository.py` 4 test（全失敗/無命中/systemic 排前/確有走 fetch_url）；`test_app_smoke + test_proxy_infra` 109 PASSED 零回歸（沙箱無 feedparser，用假模組 + mock fetch_url 離線驗證）
- [ ] **後續（Task3）**：`fetch_macro_news(asset_class)` 分類接口、AI 解盤 widget 推到 Tab5 — 待 user 指定該切片

### v18.185 — 切換帳本自動讀回 + 跨帳本共用基金資訊（同 code 免重抓）（2026-05-24）

- [x] **問題場景**（user）：①切換帳本後「沒有載入鍵與計算」（只 set sheet_id + rerun，持倉/分析不動，要自己滾回頂部按「📥 雲端讀取」）②同一檔基金在不同帳本（不同人/保單）會被當全新重抓 MoneyDJ（~30s/檔）
- [x] **根因**：①「🔁 切換到此帳本」(`tab3_portfolio.py:757`) 只 `policy_sheet_id=新id`+`st.rerun()`，無自動讀回 ②`sync_policies_to_portfolio_funds` 以 `(policy_id, fund_code)` 複合鍵 merge → 換帳本時 policy_id 不同，同 code 落在「added/loaded=False」骨架 → 全部重抓（但 NAV 歷史/指標只跟 fund_code 有關、與保單無關）
- [x] **Fix（user 選「切換後自動載入」+「新標的用既有按鈕抓」）**：
  - **共用基金資訊**：新增純函式 `ui/helpers/portfolio_load.py:reuse_fund_info_by_code(merged, previous_funds)` — 把上一本已 `loaded=True` 條目依 code 補回（series/dividends/metrics/moneydj_raw/risk_metrics/name/currency/is_core，set loaded=True；空值不覆蓋如保單帶來的 currency）。`load_all_from_sheet`（`cloud_io.py`）sync 後呼叫、report 加 `reused`
  - **自動讀回**：`render_portfolio_tab` 早段（client closure 後）加 `_last_loaded_sheet_id` 追蹤 — id 變且雲端可達就自動跑一次 `load_all_from_sheet`（持倉切換+基金資訊沿用、零 MoneyDJ）、`st.toast` 報「持倉 N 檔／沿用 M 檔免重抓／K 檔新標的待載入」
  - **新標的**：真正不同的 code 仍 `loaded=False`，留給既有「📡 載入未載入基金（N 檔）」一鍵抓（避免切換時卡 30s×N）
- [x] **防呆**：本次 session「第一次進入」且已有本地持倉（如剛還原 JSON）→ 只記 sheet_id 不自動讀回，避免 sync 把本地狀態洗掉；真正切換 id 才讀。失敗也記 id 不重試迴圈，可手動再按「📥 雲端讀取」
- [x] **驗證** AST PASS；ruff clean（順手刪 `test_portfolio_load` dead import `patch`）；新增 6 個 `reuse_fund_info_by_code` 單元測試；`test_portfolio_load + test_cloud_io + test_app_smoke + test_tab3_portfolio + test_policy_store + test_json_backup` 共 **212 PASSED** 零回歸

### v18.184 — T7 持倉明細表加「含息成本 + 累積已配息率」欄（dangling input 終於被用）（2026-05-23）

- [x] **問題場景**（user）：①「含息來源沒在存檔（Sheet/JSON）」②「之前說含息來源有資料可算含息率，但分析資料沒看到」
- [x] **釐清 Point1**：「含息來源」是 A/B **輸入方式**（A 直接抄含息成本 / B 累積配息反推），本身不持久化（user 同意不存）；它的**結果含息成本(`avg_nav_with_div`)有存**（JSON v18.180 / 保單分頁 v18.183 / ledger `cost_unit_with_div` v18.180）
- [x] **釐清 Point2（真 gap）**：`cost_unit_with_div` 一直被收集+存檔但**從沒在任何顯示分析用過**（dangling input）；app 內唯一「含息報酬率」來自 MoneyDJ 基金層資料、非 user 對帳單含息成本
- [x] **Fix（user 選「累積已配息率」）**：T7 持倉明細表（`tab3_t7_ledger.py` `_snap_rows`）新增兩欄 — 「含息成本」(`cost_unit_with_div`) + 「累積已配息率」= (平均買入淨值 − 含息成本)/平均買入淨值（純成本面、不需即時 NAV）。含息成本未填（`cuwd>=cu0`）顯示「—」；累積已配息率併入綠色著色 subset。units≤0 分支同步補兩欄保持對齊
- [x] **邊界**：QL19676552 那幾檔含息成本=淨值（未填）→ 兩欄顯「—」正確；ACTI71=(8.67−6.9655)/8.67=19.66%
- [x] **驗證** AST PASS；`test_app_smoke + test_fund_ledger + test_tab3_portfolio` 共 **128 PASSED** 零回歸（純顯示層、無新測試需求）

### v18.183 — div_cash_pct/avg_nav_with_div 加進 v1 保單分頁 schema（存進 Sheet + 讀回不掉）（2026-05-23）

- [x] **問題場景**（user）：「div_cash_pct 存檔不在 google sheet」。釐清：v1 保單分頁 `ALL_COLS` 只有 invest_twd/policy_tier 等，**無 div_cash_pct/avg_nav_with_div 欄** → 從不寫進保單分頁、且「全部讀回」會歸零（只有 JSON 備份留得住）。v2 schema 早有這兩欄、但 user 走 v1+T7 流程
- [x] **方案**（user 選「兩欄都加」）：`OPTIONAL_COLS` 尾端追加 `div_cash_pct` + `avg_nav_with_div`（純追加、既有欄位位置不變）；`ALL_COLS` 自動 9→11 欄
- [x] **寫**：`upsert_fund_in_policy`（per-policy 分頁、user 路徑）寫入前若表頭缺新欄 → 自動 `update("A1:K1", ALL_COLS)` 升級表頭（既有資料列尾端補空、不錯位）、cols 固定 ALL_COLS；寫入端（T7 套用 v18.179 區塊、`dump_all_to_sheet`）row 帶上兩欄。`upsert_policy_row`（legacy Policies 單表）改「寫表頭實際有的欄交集」避免孤兒欄、不強制升級（保留向後相容）
- [x] **讀回**：`sync_policies_to_portfolio_funds` 把兩欄讀進 portfolio_funds（**有值才帶**，空欄不覆蓋記憶體既有設定）→ 全部讀回不再歸零
- [x] **驗證** AST PASS；改 1 舊 test（9→11 欄）+ 新增 3 test（升級表頭/sync round-trip/空欄不覆蓋）；`test_policy_store + test_cloud_io + test_policy_keys + test_ledger_snapshot_store + test_app_smoke + test_json_backup + test_fund_ledger + test_migrate_v149_schema + test_portfolio_load` 共 **269 PASSED** 零回歸

### v18.182 — 新增「人看得懂的完整成本帳本」分頁 _持倉總覽（2026-05-23）

- [x] **問題場景**（user 截圖 + JSON）：v18.180/181 已驗證 OK（JSON 有含息/現金給付%、exported_at 台灣時間）。但 user「看不到 T7、帳本資料沒在 Excel」。釐清：①user 在看 Google 預設空白的 `工作表1`（資料其實在保單分頁，user 確認「有資料」）②完整帳本（單位數/含息成本…）只存在 `_T7_State`（JSON blob、人看不懂）且 user 的 Sheet 沒這分頁；保單分頁只有 invest_twd
- [x] **方案**（user 選「只存成本帳本」）：新增 `repositories/snapshot_repository.py` `save_holdings_overview()` — t7_ledgers ⨝ portfolio_funds 組「每檔基金一列」可讀表格，寫進 `_持倉總覽`（`_` 開頭→不被 `list_policy_worksheets`/`detect_sheet_schema_version` 誤認成保單分頁；clear+batch 同 `_T7_State` 模式）
- [x] **欄位**：保單號碼/基金代碼/基金名稱/幣別/級別/持有單位數/平均成本淨值/平均含息成本/平均匯率/投資金額(TWD)/現金給付%/累積已領配息(TWD)/更新時間（台灣時間）。只存成本面，不存市值（市值隨 NAV 過時，由 app 即時算）
- [x] **接線**：`_t7_save_snapshot_to_sheets()`（所有 T7 落帳共同出口）與 `dump_all_to_sheet()`（全部寫入）寫完 `_T7_State` 後一併呼叫；成功訊息加「_持倉總覽 +N 筆」。repo 層用固定 UTC+8（不 import ui.helpers.tw_time，避免反向依賴）
- [x] **驗證** AST PASS；新增 3 個 test（空/可讀列/級別+pid fallback）；`test_ledger_snapshot_store + test_cloud_io + test_app_smoke + test_policy_store + test_fund_ledger + test_json_backup` 共 **236 PASSED** 零回歸（修 2 個 test_cloud_io 斷言：新 overview 寫入）

### v18.181 — 修「上次寫入/讀回」時間戳顯示 UTC（應為台灣 UTC+8）（2026-05-23）

- [x] **問題場景**（user 截圖）：雲端存檔面板「上次寫入：2026-05-23 13:26」看起來「不會動」，且對不上 Google Drive 顯示的「晚上9:25」。實為時區 bug — 13:26 UTC = 21:26 台灣，同一刻只是差 8 小時
- [x] **根因**：所有 wall-clock 時間戳用 bare `datetime.now()`；Streamlit Cloud 伺服器跑 UTC → 比台灣慢 8 小時。`t3_last_save_at` 其實每次寫入都有更新（無 reset），只是顯示 UTC
- [x] **Fix（全部統一台灣時間）**：新增 `ui/helpers/tw_time.py`（`tw_now()` / `tw_now_str()`，固定 UTC+8 offset、不依賴 tzdata、台灣無 DST）。改 5 處：`tab3_portfolio.py` 上次寫入/上次讀回/JSON 備份檔名、`json_backup.py` `exported_at`、`tab3_t7_ledger.py` 方案 `created_at`。順手清掉 inline `import datetime as _dt_q/_dt_top` dead import
- [x] **邊界**：方案 id 的 `.timestamp()`（epoch）tz 無關不動；ledger 交易 `.today()`（日期）不在範圍。`tw_now_str()` 實測回 21:3x（容器 UTC 13:3x +8）正確
- [x] **驗證** AST PASS、import 無循環；`test_json_backup + test_app_smoke + test_policy_store + test_cloud_io + test_fund_ledger` 共 **222 PASSED** 零回歸

### v18.180 — 修 T7 含息成本不生效 + JSON 備份漏存含息/現金給付%（2026-05-23）

- [x] **問題場景**（user 反饋）：T7 套用起始部位後 ①ledger「看起來沒變」（`cost_unit_with_div` 永遠 = `cost_unit`）②下載的 JSON 備份檔沒有「🟨 現金給付 %」與「📋 含息來源（含息成本）」
- [x] **Bug A — 含息成本不生效**（`ui/tab3_t7_ledger.py:676`）：建 ledger 時 `subscribe(_amount_twd, _fx, _cu, …)` 傳的是 `_cu`（淨值）非 `_anw`（含息成本）；`subscribe()` 首買把 `cost_unit_with_div = nav` → user 抄入的對帳單欄(10) 含息成本被覆蓋。Fix：subscribe 後 `if _anw > 0: _new_led.position.cost_unit_with_div = float(_anw)` 校正
- [x] **Bug B — JSON 備份漏欄**（`ui/helpers/json_backup.py:23-34`）：`build_export_payload` 的 slim fund 固定欄位漏掉 `avg_nav_with_div` + `div_cash_pct`。Fix：補這兩欄；restore 沿用「保留 JSON 全部 key」邏輯自動還原，T7 表單 `_f.get("avg_nav_with_div"/"div_cash_pct")` 重新讀回
- [x] **Constraint C**（背景）：v1 保單分頁 `ALL_COLS` 無含息成本/現金給付% 欄位 → 這兩欄唯一持久化途徑是 JSON 備份（本次 Bug B 修好）。user 選「含息+JSON 兩修」、暫不擴充 v1 schema
- [x] **驗證** AST PASS；`test_json_backup + test_fund_ledger + test_app_smoke + test_policy_store + test_cloud_io` 共 **222 PASSED** 零回歸

### v18.179 — 修 T7「套用為起始部位」存檔不回寫保單分頁（被迫每次下載手改）（2026-05-23）

- [x] **問題場景**（user 截圖反饋）：在 T7「✏️ 編輯持倉」表單輸入各基金的淨投資金額後按「💾 套用為起始部位（覆蓋 T7 帳本）」存檔，新增/編輯的項目**不會回寫到使用者實際讀寫的保單分頁**（如 QL19676552），只能每次下載手改
- [x] **根因**（`ui/tab3_t7_ledger.py` submit handler）：存檔只寫 ①本地 `t7_ledgers` ②`_T7_State` 快照 ③`_Ledgers` 交易分頁；保單分頁的 `upsert_fund_in_policy` **只在「保單號碼改變」（`_pid_changes`）時觸發** → 同保單內編輯金額（無 pid 變更）的基金列永遠不更新
- [x] **Fix（全量同步保單分頁）**：新增 `_funds_to_sheet` 收集每一檔已套用且有保單號碼的基金 `(pid, code, fund_obj)`；OAuth 區塊改成全量 `upsert_fund_in_policy`（帶 invest_twd / currency / policy_tier），涵蓋「新增 + 同保單編輯」；notes 對 pid 變更標 `T7 pid migrate`、其餘 `T7 套用起始部位`；成功訊息加「+ 保單分頁回寫 N 檔」；`policy_tabs` cache 改在 `_funds_to_sheet` 非空時刷新
- [x] **邊界**：無 pid 的基金（未綁保單）仍不寫（無分頁可寫，正確）；`_f_obj` 為 `{}` 時 upsert 用 `.get` 預設值安全；未登入 OAuth / 無 sheet_id 時整段略過只更新本地
- [x] **驗證** AST PASS；`test_app_smoke + test_policy_store + test_cloud_io` 共 **185 PASSED** 零回歸

### v18.178 — 審計 punch-list 清理 #2/#5/#6（2026-05-23）

- [x] **#5 expander 偵測擴及 `st.status`**（`test_app_smoke.py:33`）：`_is_expander_call` 從只認 `st.expander` 改認 `_EXPANDER_LIKE_ATTRS=("expander","status")` — v18.156 crash 元凶正是 `st.status` 巢狀在 expander 內，偵測網現在涵蓋兩者。95 PASSED（無現存違規）
- [x] **#6 刪除 backtest dead code**：`services/backtest_service.py` + `test_backtest_engine.py` 全刪 — v18.176 移除回測 Tab 後僅剩自己 test 在用、`backtest_engine.py` shim 早已不存在，確認全孤兒。resolve「月底再平衡 TODO」by elimination（CLAUDE.md §2 清 dead code）。ARCHITECTURE.md:217 同步（§4.5b 等歷史 backtest_engine 段為 pre-existing drift，未重寫）
- [x] **#2 NAV cache 腳本補強**（`scripts/fetch_nav_cache.py`）：(a) `FUND_CODES` 補 `ACDD01`（安聯台灣大壩 — 原漏列致無 cache、T5 相關係數算不出的根因之一）；(b) 結尾加診斷彙整表（每檔筆數 + 🔴<30/🟠<60/🟡<252/✅≥252 狀態 + 來源，列出 <60 筆需查的 fund）
- [x] **驗證** AST PASS；診斷表邏輯 isolation dry-run OK；`test_app_smoke + test_holdings_overlap + test_tab3_portfolio` 107 PASSED 零回歸
- [ ] **#2 殘留**：腳本改好但**沙箱擋 MoneyDJ/Yahoo 403 無法實跑驗證抓取**；需 user 在本地或 GitHub Actions 跑 `python scripts/fetch_nav_cache.py` 才會真正補出 cache。`FUND_CODES` 仍是硬編碼，須與 Sheet 保單分頁手動同步

### v18.177 — 修 T5 相關係數矩陣「短 NAV → 相關係數=0」假象（自適應頻率）（2026-05-23）

- [x] **問題場景**（user 反饋）：ACDD19 安聯台灣智慧 vs ACDD01 安聯台灣大壩，同為台股基金，T5 矩陣相關係數卻顯示 0，不合直覺
- [x] **根因**（`services/portfolio_service.py:454` `calc_correlation_matrix`）：寫死 `s.resample("ME")` 月底重採樣 — 這幾檔卡 ~30 天 fallback NAV，月底只剩 1-2 點 → `pct_change` 僅 1 個 return → `corr` 退化成 NaN（顯示成 0）。模擬證實：月底→NaN；日頻→真實 0.96
- [x] **Fix**：改自適應頻率，月→週→日逐級降頻，挑第一個 return 列數 ≥6 的最粗頻率，都不足退日頻；回傳新增 `freq` 欄位
- [x] **UI**（`ui/tab3_portfolio.py:2080`）：notes 顯示實際採用頻率（如「日頻」「週末」），讓 user 知道是降頻算的
- [x] **新增測試**（`test_holdings_overlap.py`）：`test_corr_short_nav_not_zero`（短 NAV 降頻後相關 >0.8 非 0）、`test_corr_long_nav_keeps_monthly`（長歷史維持月底）、`test_corr_too_few_funds_returns_none`
- [x] **驗證** AST PASS；`test_holdings_overlap`(8) + `test_tab3_portfolio` + `test_app_smoke` 共 **107 PASSED** 零回歸
- [ ] **殘留**：根本上 NAV 歷史太短仍是 #2 NAV cache 問題；此 fix 讓「有資料時算對」，但若兩檔完全無重疊期仍會 NaN

### v18.176 — 移除回測 Tab（user 只需汰弱留強判斷換基金）（2026-05-23）

- [x] **決策**（user 明確要求）：「直接移除回測這功能，不想他拖累整個系統速度」— 真實需求是「判斷未來要不要換基金」，由組合基金的戰情室（Sharpe<0 / 配息覆蓋率<1 汰換訊號）+ 汰弱留強評分 + 同類排名滿足，回測（歷史組合模擬）非必要且 NAV 歷史抓不全
- [x] **app.py**：`st.tabs` 6→5（拿掉「🔬 回測」），刪 `with tab4:` block、`render_backtest_tab` import、死的 `backtest_service` import（calc_performance_metrics/quick_backtest/backtest_portfolio 在 app.py body 從未使用）、更新 docstring
- [x] **刪 `ui/tab4_backtest.py`**；**保留 `services/backtest_service.py`**（純計算零 IO，不影響速度，留供未來重啟回測；`test_backtest_engine.py` 14 項照留）
- [x] **測試對齊**：刪 `test_tab4_backtest.py`、刪 apptest `test_tab4_backtest_button...`、smoke tab 清單 6→5、`test_app_py_only_has_render_calls_for_all_5_tabs`（改名 + 斷言 `render_backtest_tab not in src`）、刪 playwright `test_tab4_screenshot_baseline`
- [x] **文件同步** SPEC.md Tab4 列刪除線標註、STATE 五大模組描述更新、ARCHITECTURE 提及回測處更新
- [x] **驗證** AST × 5 PASS；`test_app_smoke + test_tab3_portfolio + test_backtest_engine` 115 PASSED；AppTest 啟動 2 passed app 正常開（`test_tab3_kpi` 1 失敗為 sandbox yfinance 403 環境問題，非本次）

### v18.175 — 修 Tab4 回測「月底剛好 2 點」off-by-one 矛盾 + 補日頻 fallback（2026-05-23）

- [x] **問題場景**（user 截圖反饋）：4 檔基金回測，補抓全歷史 timeout 退 cache → 月底 resample 剛好 2 點（2026-04-30 ~ 05-31）→ 綠字「回測完成 2 期」**同時**紅字「樣本不足 returns<2」自相矛盾、績效全 —%
- [x] **根因（off-by-one）**（`ui/tab4_backtest.py:300-323`）：降頻門檻 `len(nav_monthly) < 2` — 月底 2 點不 <2 → **不降週頻也不報錯** → 跑回測 → 2 NAV 點僅 1 個 return → `calc_performance_metrics` 要 ≥2 returns → 回 `{}` → 全 —%
- [x] **Fix**：門檻 `< 2` → `< 3`（需 ≥3 點 = ≥2 returns）；降頻 ladder 補第 4 層「日頻」（週仍 <3 時保留每交易日，freq=252）；`_bt_freq` 改在 ladder 內決定（月12/週52/日252），移除 L351 重複推導
- [x] **驗證** 獨立模擬證實月底 2 點 → 新邏輯降週頻得 6 點 / 5 returns 可算指標；`test_backtest_engine.py` 14 + Tab4 apptest PASS（`test_tab3_kpi` 1 失敗為 sandbox yfinance 403 環境問題，stash 後同樣失敗，非本次改動）

### v18.174 — 全局指標關聯地圖搬到說明書 + 總經因果鏈 Sankey 動態詳細說明（2026-05-23）

- [x] **問題場景**（user 截圖反饋）：Tab1「🗺️ 全局指標關聯地圖」純靜態教學圖長期占首屏；下方「🔗 總經因果鏈 Sankey」動態圖看不懂節點/邊代表什麼
- [x] **Move 教學圖**（`ui/tab1_macro.py:126-133` 整塊移除 / `ui/tab6_manual.py` 新增第 10 sub-tab）：靜態地圖 + 升息/降息劇本 + 投資應用 3 點搬到說明書，避免占首屏；`render_indicator_map()` 函數保留在 tab1，tab6 cross-import 復用避免重複定義
- [x] **動態詳細說明**（`ui/tab1_macro.py:1763+` Sankey 圖下方新 expander）：
  - 🔍 8 節點現況：依 node_colors 映射 🔴 壓力高 / 🟠 偏離均值 / 🟡 略偏負面 / 🟢 健康 / 🌫️ 無 z-score
  - 🔗 9 條因果鏈強弱分級：依 |corr| 三檔（🔥≥0.5 強 / 🌤️ 0.3-0.5 中等 / ❄️ <0.3 弱 / 🌫️ <12 期共同期無法計算），每條附 `source → target：edu_note (corr=±0.XX, 強/中/弱 正/負相關)`
  - 若 Phase 2（非動態）→ 引導 user 打開「🆕 動態權重」checkbox 才看得到分級
- [x] **驗證** AST × 2 PASS；`test_policy_store + test_app_smoke + test_macro_core` 共 **217 PASSED** 零回歸

### v18.173 — T7「預估月配股 (TWD)」欄附顯「可換單位數」（2026-05-23）

- [x] **問題場景**（user 截圖反饋）：v18.172 已把月配股 TWD 拆出來，但只看到金額不知對應幾單位 — 配股 = 把現金部位再投入基金，需直接呈現「能換到的單位數」才好對應到帳本 units
- [x] **算式**（`ui/tab3_t7_ledger.py:1929-1934`）：`units = (月配股 TWD) / FX / NAV`；只在 `_ann_reinv > 0 and _nav and _fx` 才附顯，否則維持單純 `NT$0`
- [x] **顯示格式**：`"NT$2,802 (32.8762 單位)"`；no-ledger 與 0 配股列照舊 `—` / `NT$0`
- [x] **驗證** AST PASS；`python -m pytest test_policy_store.py -q` 80 PASSED 零回歸

### v18.172 — T7 KPI 拆「現金配息 / 配股」+ 鬼列 filter 補修大寫（2026-05-22）

- [x] **問題場景**（user 截圖反饋）：T7 帳本 KPI「💵 預估年配息 NT$1,250,792 / 📅 每月被動現金流 NT$104,233」**沒套用 `div_cash_pct`** — 即使設部分配股（如 60% 現金），現金流仍顯示全額；配股估算也沒分開呈現
- [x] **算式拆分**（`ui/tab3_t7_ledger.py:1860-1908`）：新增 `_cash_total_twd / _reinvest_total_twd` 累計；per-row 加「預估月配股 (TWD)」欄；no-ledger branch 同步補 `—`
- [x] **KPI 6 columns 重排**（L1951-1992）：`st.columns([2,2,2,2,1])` → `st.columns([2,2,2,2,2,1])`；KPI3 改「💵 預估年**現金**配息 (TWD)」、KPI4「📅 每月被動現金流」用 cash-only / 12、新增 KPI5「🪙 預估年配股 (TWD)」、重置按鈕移到 _pc6
- [x] **鬼列 filter 補修**（`repositories/policy_repository.py:516-528`）：v18.171 filter 只擋小寫 `fund_url` — `dump_all_to_sheet` 把 `code .upper()` 後鬼列回寫變 `FUND_URL` 大寫繞過。改 `.str.lower()` case-insensitive；新增 `test_load_policy_worksheet_filters_uppercase_ghost_rows` regression
- [x] **驗證** AST × 2 PASS；smoke test 6 + policy_store 鬼列 test 4 = 10 PASSED 零回歸

### v18.171 — 修保單分頁「schema 鬼列」append_row bug + 自動過濾髒資料（2026-05-22）

- [x] **問題場景**（user 截圖反饋）：「📋 保單分頁清單」存檔後 `QL19676552` tab 出現 3 列 `policy_name / fund_url / invest_date / currency / notes` 等**schema 英文 key 字串當成資料值**的鬼列
- [x] **根因**：`repositories/policy_repository.py:474 & :480 & :276` 的 `ws.append_row(list(ALL_COLS))` — 當 worksheet 已存在但 row 1 被讀成空（user 手動清過 header / gspread row_values 偶發空回應），`append_row` 把表頭塞到**資料最末列**而非 row 1，被當成基金紀錄；user 多次「全部寫入」累積 3 列
- [x] **Fix A**（3 處 `policy_repository.py:276,474,480`）：`ws.append_row(list(ALL_COLS))` → `ws.update("A1", [list(ALL_COLS)])` 強制 row 1，杜絕表頭漂移
- [x] **Fix B 防禦性過濾**（`load_policy_worksheet:516-525`）：DataFrame 過濾 `(fund_url=='fund_url') & (invest_date=='invest_date') & (currency=='currency')` 鬼列；現存髒資料畫面立刻乾淨，不必去 Google Sheet 手動刪
- [x] **更新 regression test**：`test_ensure_policy_worksheet_creates_when_missing` 改斷言 `update.assert_called_once_with("A1", [list(ALL_COLS)])`；新增 `test_ensure_policy_worksheet_existing_with_empty_row1_writes_header_to_A1_not_append`、`test_load_policy_worksheet_filters_schema_ghost_rows` 兩個 case
- [x] **驗證** `test_policy_store.py` 79/79 PASSED 零回歸

### v18.170 — T7 編輯持倉表單暴露 div_cash_pct + 月配息估算（部分配股新功能）（2026-05-22）

- [x] **問題場景**（user 截圖反饋）：T7「📝 編輯持倉（手動微調 — 從 CHUBB 對帳單抄入精確值）」表單只有 5 欄（淨投資金額／淨值／匯率／含息來源／保單號碼）；user 反映保單實際支援「部分配息+部分配股（單位）」，希望用「資金的百分比」算每月配息與配股
- [x] **既有 v18.160 基礎**：`div_cash_pct`（0-100）已有 schema、estimate_dividend_split 函式、v2 編輯表格欄位、年度估算 expander；T7 編輯持倉表單未暴露此欄位
- [x] **T7 表單第 6 欄**（`ui/tab3_t7_ledger.py:564, 615-628, 627, 646, 689`）：`st.columns([1,1,1,1,1])` → `st.columns([1,1,1,1,1,1])`，最末加 `ic6.number_input("🟨 現金給付 %", 0-100, step=5, default=100)`；`_init_inputs` tuple 加 `_dcp`；submit handler 寫入 `_f_obj["div_cash_pct"] = max(0, min(100, float(_dcp)))`
- [x] **月配息估算 toggle**（`ui/helpers/v2_editor.py:151-204`）：`_render_div_split_estimate` 加 `st.segmented_control(["📅 年估算", "📆 月估算"])`；月模式下 `annual_div_rate_pct / 12` 傳給 `estimate_dividend_split`，表格欄與 metric 標題隨 `_label = "月"/"年"` 動態切換
- [x] **驗證** 結構 smoke test（AST × 2 + no_direct_expander_nesting × 2 + no_silent_except_pass + no_crossfile_expander_nesting）6 個 PASSED；既有 `test_estimate_dividend_split_*` 4 個 case 函式簽名未變不受影響

### v18.169 — 「📋 保單清單」說明區塊搬到 Tab6 說明書（§9 Sheet 資料結構）（2026-05-22）

- [x] **問題場景**（user 截圖反饋）：Tab3 expander 內「📋 保單清單（這本 Sheet 內的保單分頁與輔助 tab）」說明區塊（3 行說明文 + 3 個動態 metric）屬於「使用說明」性質，user 認為不該占 Tab3 動作面板版面，要求移到「📖 說明書」tab
- [x] **刪除 Tab3 區塊**（`ui/tab3_portfolio.py:644-675`）：32 行整個 `if _sheet_id:` 區塊（包含 markdown 標題、caption 說明、3 個 `st.metric` 卡片、可選的 `last_sync` caption）→ 改成 1 行註解；動態 metric 數字（`_sheet_stats` 的 tabs / t7_state / ledgers）依 user 決定捨棄不重現
- [x] **新增 Tab6 第 9 個 sub-tab**（`ui/tab6_manual.py`）：`_t6 = st.tabs([...])` 從 8 個加到 9 個，新增「📋 9. Sheet 資料結構」；內容為純靜態 markdown 表格（3 種 tab 類型 × 命名規則 × 用途 × 同步來源）+ 4 個重點觀念 bullet + 多帳本管理引導
- [x] **module docstring** 同步「8 個 sub-tab」→「9 個 sub-tab」標註 v18.169 新增來源
- [x] **驗證** 結構 smoke test（AST parse / no_direct_expander_nesting / no_silent_except_pass / no_crossfile_expander_nesting）全綠；test 環境缺 pandas/numpy 為 pre-existing env issue 不影響 markdown 改動

### v18.168 — 📥 雲端讀取面板：上下半對調（從 Drive 挑帳本 → 全部讀回）（2026-05-22）

- [x] **問題場景**（user 截圖紅框 + 紅箭頭）：v18.166 面板上半「全部讀回」、下半「從 Drive 挑帳本」，user 反饋要對調 — 先挑帳本（前置動作）再讀回（後續動作）符合操作順序
- [x] **對調順序**（`ui/tab3_portfolio.py:271-396`）：
  - 上半 ── 「📂 從 Drive 挑帳本（切換 / 首次選用）」整段（OAuth + 已登入時顯示）+ 末端加 `st.markdown("---")` 分隔
  - 下半 ── 「📥 全部讀回（雲端 → 本地）」（需有 `_sheet_id_q`，加 `**📥 全部讀回（雲端 → 本地）**` 標題；無 ID 時改顯示 info 引導去上方挑）
- [x] **info 文案微調**：「請從下方挑一本」→「請從上方挑一本」對齊新版型
- [x] **驗證** fast tier `pytest -m "not slow"` **565 passed**，與 v18.167 baseline 一致零回歸；widget key 順序不影響 streamlit state 一致性

### v18.167 — 刪除「🧰 一鍵存讀」「📁 本機 JSON 備份」雙入口，瘦身成「🛠️ 進階工具」（2026-05-21）

- [x] **問題場景**（user 截圖紅框 + 文字反饋）：頂部 5 顆按鈕已完整覆蓋全部存讀，但下方 expander 內仍有 v18.50「🧰 一鍵存讀（同步整本帳本）」（📦 全部寫入 + 📥 全部讀回 + 🔄 只重新整理 + 🗑️ 清空快取）與 v18.70「📁 本機 JSON 備份」（💾 下載 + 📂 上傳）兩個重複區段「占版面」
- [x] **刪除「🧰 一鍵存讀」雙入口**（`ui/tab3_portfolio.py:895-1001`）：
  - 移除 `btn_dump_all_v18_50` / `btn_load_all_v18_50` 兩顆按鈕 + 對應 `_dump_all_clicked` / `_load_all_clicked` 變數與 handler block（與頂部 📦 雲端存檔 / 📥 雲端讀取 完全重複）
  - 重命名 header「⬇️ 🧰 一鍵存讀（同步整本帳本）」→「🛠️ 進階工具」
  - 簡化 handler：只剩 `if _refresh_clicked:` 走 `load_all_from_sheet(refresh_only=True)`
- [x] **保留頂部沒有的小工具**（同位置）：
  - 🔄 只重新整理分頁清單（不動投組）— refresh_only 路徑
  - 🗑️ 清空抓取快取 — fund_fetcher / macro 快取 TTL 清空
  - 快取狀態 caption（hit-rate / entries / hits-misses）
  - 兩按鈕改用 `st.columns(2)` 並列、`use_container_width=True`
  - 加 `**📋 保單分頁清單**` 標題給原本無名的 `_pdf_cached` dataframe
- [x] **刪除「📁 本機 JSON 備份」整段**（`ui/tab3_portfolio.py:1003-1050`）：與頂部 💾 下載 JSON / 📂 上傳 JSON 完全重複，47 行整段移除
- [x] **更新引導文字**（`tab3_portfolio.py:653`）：「用下方「🧰 一鍵存讀」」→「用頂部「🚀 快速存讀面板」」對齊現況
- [x] **驗證** fast tier `pytest -m "not slow"` **565 passed**，與 v18.166 baseline 一致零回歸；total Tab3 expander 內容瘦身 ~100 行

### v18.166 — 從 Drive 挑帳本移到「📥 雲端讀取」面板（職責分離）（2026-05-21）

- [x] **問題場景**（user 截圖紅框 + 紅箭頭）：v18.165「✨ 新增帳本」面板上下並列「自動建立」+「從 Drive 挑」，user 反饋「下面的讀取檔案要放回第一個按鈕下」希望分流到「📥 雲端讀取」面板
- [x] **「📥 雲端讀取」面板擴充**（`ui/tab3_portfolio.py:263-405`）：
  - 上半：原「全部讀回」邏輯（需有 `_sheet_id_q`）；無 ID 時改顯示 info 引導去下方挑
  - 下半（v18.166 新增）：「📂 從 Drive 挑帳本」整段 hoist 過來 — 載入資料夾清單 / 限定資料夾 / 從 Drive 列出 Sheets / 選用 Sheet，OAuth 登入時恆顯示
- [x] **「✨ 新增帳本」面板瘦身**（`ui/tab3_portfolio.py:432-490`）：只剩「自動建立新 Sheet」（caption 加註「想挑 Drive 內既有的 Sheet 請改點 📥 雲端讀取」引導 user），button help 改為「建立全新的 Google Sheet 作為帳本」
- [x] **職責分離 UX**：「✨ 新增 = create new」「📥 雲端讀取 = pick existing + load」字面語義對齊
- [x] **驗證** fast tier `pytest -m "not slow"` **565 passed**，與 v18.165 baseline 一致零回歸；6 個 widget key 仍唯一（移動而非複製）

### v18.165 — 快捷面板加第 5 顆「✨ 新增帳本」互動式 button（2026-05-21）

- [x] **問題場景**（user 截圖紅框 + 紅箭頭）：v18.164 把「✨ 新增帳本」做成 expander 內的小標題，但功能仍埋在下方需捲動；user 要求頂部「🚀 快速存讀面板」加第 5 顆 button、點下去直接顯示互動面板（與其他 4 顆一致）
- [x] **頂部 toolbar 由 4 顆改 5 顆**（`ui/tab3_portfolio.py:212-237`）：`st.columns(5)`，順序 `📥 讀 / 📦 存 / ✨ 新增帳本 / 💾 下載 / 📂 上傳`；`✨ 新增帳本` 對應 `_io_panel == "new"`
- [x] **新增 `elif _io_panel == "new":` 面板**（`tab3_portfolio.py:340-486`）：
  - 上半：「🚀 自動建立 Sheet」（無條件顯示，user 已點 button 表示想新增）— caption 改「讓 app 建一張全新的 Google Sheet 作為帳本」
  - 下半：「📂 從 Drive 既有 Sheets 挑」（資料夾下拉 → 列 Sheets → 選用）
  - 未配 OAuth / 未登入 → 顯示友善 warning
- [x] **移除 expander 內 L630-770 重複區段**：v18.164 hoist 到 expander 的「✨ 新增帳本」段（自動建立 + Drive 挑）整段刪除，避免 widget key 衝突；只留下單行 `_sheet_id = session_state.get(...)` + 註解
- [x] **驗證** fast tier `pytest -m "not slow"` **565 passed**，與 v18.164 baseline 一致零回歸；6 個 widget key (`btn_auto_create_sheet` / `btn_load_drive_folders` / `sel_drive_folder` / `btn_list_drive_sheets` / `sel_my_sheets` / `btn_pick_my_sheet`) 確認唯一

### v18.164 — Sheet ID hoist 到 sidebar +「✨ 新增帳本」互動式面板（2026-05-21）

- [x] **問題場景**（user 截圖紅框）：Tab3「📋 保單管理」expander 內，OAuth 登入狀態與「Google Sheet ID 輸入」並列在快捷面板下方占大半版面；下方「自動建立 Sheet」與「從 Drive 挑」上下兩段被「或者」文字隔開、層次不一致
- [x] **Sidebar 加「📋 工作中帳本」區塊**（`app.py:280-310`）
  - Sheet ID / URL 輸入（自動解析 `/spreadsheets/d/<id>/`）→ 寫回 `policy_sheet_id`
  - 當前帳本標題顯示（`get_sheet_title` + `_t3_cur_sheet_title:<sid>` cache），登入但無 ID 顯示引導 caption
- [x] **Tab3 重組「✨ 新增帳本」面板**（`ui/tab3_portfolio.py:485-544`）
  - 移除 expander 內原 `text_input("Google Sheet ID 或完整 URL")` 區塊（已搬 sidebar），改為單行 `_sheet_id = session_state.get("policy_sheet_id") or _sheet_id_secret`
  - 新增 `##### ✨ 新增帳本` header 統一兩個子區塊
  - 上：自動建立 Sheet（保留條件 `not _sheet_id`，避免已選帳本時噪音）
  - 下：從 Drive 挑既有 Sheets（移除「或者」字眼，與上半無縫銜接；只在兩者都顯示時加 `---` 分隔）
- [x] **驗證** fast tier `pytest -m "not slow"` **565 passed**，與 v18.163 baseline 完全一致零回歸
- [x] **CLAUDE.md §3 三步法**：Explore（grep `_sheet_id`/sidebar 結構）→ AskUserQuestion 確認面板版型（上下並列）+ sidebar 位置（Google 帳號區之下）→ Execute

### v18.163 — Tab3 KPI 合併 hero + sub-tab 改 segmented_control（消除上下兩段重複占版面）（2026-05-21）

- [x] **問題場景**（user 截圖兩張）：Tab3 上下兩段 KPI 重複（上方 mk_war_room 4 卡 + 下方真實收益矩陣 4 卡）；三個 sub-tab（核心戰情室/波段觀測站/3-3-3 篩選器）視覺上像「同一份基金清單顯示三次」
- [x] **抽 helper** `ui/helpers/portfolio_health.py` 純函式
  - `compute_health_kpis(portfolio_funds, mk_df=None) -> dict`：合併 MK 標籤（撿便宜/留校/停利/配置比）+ 現金流（基金數/健康/吃本金/資料不足）共 12 個 field
  - `render_hero_kpi_cards(kpis)`：6 卡 hero（基金數 / 配置比 / 現金流安全 N/M / 撿便宜 / 留校 / 停利），把 `n_eat` 收進「現金流安全」的 `delta` inverse、`n_na` 進 tooltip
- [x] **Tab3 頂部加 hero KPI** `ui/tab3_portfolio.py:155+`，在 `render_mk_war_room` 之上；session_state 存 `_t3_kpis_hero` 供下方共用
- [x] **`mk_dashboard.py:728-743` 重構**：
  - 移除 `_render_kpi_cards(df)` 呼叫（hero 已涵蓋）
  - `st.tabs` 3 sub-tab → `st.segmented_control`（基金池大小寫進選項 label：`🛡️ 核心戰情室（N 檔）`）
  - 內容渲染邏輯一字不動，只換切換器
- [x] **`tab3_portfolio.py:2148-2160` 移除下方重複 4 卡 KPI**（hero 已涵蓋同樣資訊）
- [x] **T5 重疊矩陣不動** — 已是 per-policy `st.expander(expanded=False)` 收合（`tab3_portfolio.py:2195`）
- [x] **新測試** `test_portfolio_health.py` 9 cases：空輸入 / None / dedup by code / MK 標籤 / 80/20 落差 / 80/20 符合 / 吃本金邏輯 / 1Y 資料不足 / 無 mk_df 只算現金流
- [x] **驗證** fast tier `pytest -m "not slow"` **565 passed**（v18.162 baseline 556 + 9 新增），零回歸
- [x] **CLAUDE.md §3 三步法**：Explore agent 並行查重複度（KPI 中互補 / sub-tab 高 / 衛星 vs 配息矩陣低）→ Plan 3 句獲准 → Execute

### v18.162 — Tab3 快捷面板雲端動作改真執行 + 抽 cloud_io helper（2026-05-21）

- [x] **問題場景**（user 截圖三張）：v18.161 快捷面板的 📥/📦 panel 只是「狀態 + 請往下捲」提示牌，與 toast 等價；且「目前帳本」誤讀 `active_policy_id`（保單）而非 `policy_sheet_id`（帳本），顯示「(未選定)」與實際不符
- [x] **設計**：4 顆按鈕全部**真執行**
  - 📥/📦 panel 顯示「📂 帳本：**真實 sheet name** ｜ 持倉檔數 ｜ 上次讀寫時間」+ 一顆「立即執行」按鈕
  - 未登入/無 sheet_id 時顯示友善 warning + 引導到下方完成設定
  - 寫入 disabled 條件：無持倉
- [x] **抽 helper** `ui/helpers/cloud_io.py`（純函式、streamlit-agnostic）
  - `dump_all_to_sheet(client, sheet_id, ss) -> {ok, written, skipped_no_pid, n_state, warnings, error}`
  - `load_all_from_sheet(client, sheet_id, ss, *, oauth_mode, refresh_only=False) -> {ok, refresh_only, added, kept, removed, restored_ct, warnings, error}`
  - PolicySheetError / OAuthError / 未預期 exception 統一收進回傳 dict，warnings 與 error 分離（致命 vs 非致命）
- [x] **sheet name 快取** `_t3_cur_sheet_title` session_state，避免每次 panel rerun 都打 `get_sheet_title` API
- [x] **下方 L863+ 「🧰 一鍵存讀」段瘦身** ── 改呼叫同一 helper，移除 ~120 行重複邏輯；加 caption「📌 主入口在頂部『🚀 快速存讀面板』；此處作雙入口備援」
- [x] **新測試** `test_cloud_io.py` 10 cases：dump 正常 / 無 policy_id skip / _T7_State 失敗變 warning / 未預期 exception 收口 / 空 portfolio / load refresh_only OAuth / SA 模式 / full load sync report / ledger 載入失敗 warning / RuntimeError 收口
- [x] **驗證** fast tier `pytest -m "not slow"` **556 passed**（v18.161 baseline 546 + 10 新增），零回歸
- [x] **CLAUDE.md §3 三步法**：Explore（grep 確認 L791-1066 邏輯 + 依賴 + 無 closure-bound 變數）→ Plan（3 句話獲准）→ Execute

### v18.161 — Tab3 IO toolbar 升級為互動式快捷面板（toggle + 真執行 JSON / 雲端導引）（2026-05-21）

- [x] **問題場景**：v18.159 把 4 顆按鈕做成「toast 跳轉提示」，但實際操作區（一鍵存讀 L711 / 本機 JSON 備份 L920）中間隔了 OAuth / Sheet ID / 自動建立 / 資料夾載入 等大段，user 每次仍要狂滑找按鈕
- [x] **設計**：4 顆按鈕升級為 **toggle**（`st.session_state["t3_io_panel"]`，預設 `"load"`），點哪顆下方 placeholder 渲染哪顆動作面板，**不再用 toast**
  - 📥 雲端讀取 / 📦 雲端存檔 ── 顯示「目前帳本 + 本地持倉檔數 + 上次讀寫時間 + ⬇️ 完整面板提示」（依賴 `_client / _sheet_id / _active_book_id` 仍在下方解析，純導引）
  - 💾 下載 JSON / 📂 上傳 JSON ── **直接在快捷面板真執行**（不依賴 Google API，只動 `session_state`）
- [x] **抽 helper** `ui/helpers/json_backup.py`（純函式）
  - `build_export_payload(ss)` ── 剝掉 series / moneydj_raw 等大物件
  - `restore_from_json_bytes(raw, ss)` ── 回傳 `{ok, n_funds, n_ledgers, error}` 統一介面
  - 上方快捷面板 + 下方 L1008 完整面板共用同一份序列化規則（避免雙寫）
- [x] **timestamp 寫入點** `ui/tab3_portfolio.py`
  - L791 寫入成功 → `st.session_state["t3_last_save_at"]`
  - L860 讀取成功 → `st.session_state["t3_last_load_at"]`
  - 格式 `"%Y-%m-%d %H:%M"`，上方面板讀來顯示
- [x] **下方原段** L1008 加 caption「💡 也可從上方『🚀 快速存讀面板』的 💾 / 📂 直接使用」；改用 helper 重寫 → 移除 80 行重複邏輯
- [x] **新測試** `test_json_backup.py` 8 個 cases：
  - empty session_state / heavy field stripping / ledger.to_dict / 還原成功 / 壞 JSON / 缺 key / 壞 ledger entry skip / round-trip 不丟資料
- [x] **驗證** fast tier `pytest -m "not slow"` **546 passed**（v18.160 baseline 538 + 8 新增），零回歸
- [x] **CLAUDE.md §3 三步法**：Explore（grep + sed 確認 L920 不依賴 Google API、L791/L860 success path）→ Plan（3 句話獲准）→ Execute
- [x] **零作用域風險**：上方面板的雲端動作純導引（不碰 `_client / _sheet_id`），JSON 動作只動 session_state，下方完整面板邏輯完全保留

### v18.160 — 保單基金配息現金/單位拆分（div_cash_pct 0-100%）+ 估算 + AI 整合（2026-05-21）

- [x] **問題場景**：保險公司 APP 可設定每檔基金的配息「現金給付 % / 增加單位數 %」拆分（user 截圖：USDEQ5110 設 80%/20%）；dashboard 需要對應功能讓 user 紀錄此設定並估算年化現金流
- [x] **Schema 擴 v2 第 13 欄** `div_cash_pct` (0~100，預設 100=全現金；單位 % = 100 - 該值)
  - `repositories/policy_repository.py:799` `ALL_COLS_V2` +1 欄
  - 中英 header 雙向 map（`ZH_HEADERS_V2["div_cash_pct"] = "現金給付%"`）
  - `USER_INPUT_COLS` 加入該欄（黃底，user 從保險公司 APP 抄）
  - `_normalize_div_cash_pct()` 新 helper：缺值/解析失敗 → 100；超界 clip [0,100]；容錯帶 `%` 符號
  - `load_policy_v2` / `load_all_policies_v2` 在 row normalize 階段套用
  - 舊 12 欄 Sheet **向後相容**：缺欄補預設 100，`is_v2_worksheet` 仍認舊 sheet
- [x] **編輯器 UI** `ui/helpers/v2_editor.py`
  - `_empty_fund_df` / `_split_policy_df` / `_merge_policy_df` 全部跟著 +1 欄
  - data_editor 新增 NumberColumn「🟨 現金給付 %」(0-100 step=10)
  - data_editor 下方加 caption「💡 配息拆分均值：現金 X% / 新增單位 Y%」
- [x] **配息估算 mini-section**（新 helper `_render_div_split_estimate`）
  - expander「📊 配息現金/單位拆分估算」內：user 手填「年配息率假設 %」(預設 5) + 每檔基金的 fund_code/invest_twd/cash%/單位%/年現金/年再投入/年新增單位數 表格 + 3 個彙總 metric
  - 純前端計算，不依賴 portfolio_funds metrics
- [x] **estimate_dividend_split 純函式 helper**（`repositories/policy_repository.py`）
  - 輸入：invest_twd / annual_div_rate_pct / div_cash_pct / avg_nav / avg_fx
  - 輸出 dict：annual_div_twd / cash_twd / reinvest_twd / new_units / cash_pct / unit_pct
  - avg_nav=0 等邊界安全（new_units 回 0，不爆 ZeroDivision）
- [x] **AI snapshot 整合** `ui/tab3_portfolio.py:_render_tab3_ai_summary`
  - 從 `st.session_state["_v2_buf"]` 撈 user 已編輯保單的 div_cash_pct
  - 用 portfolio_funds metrics 的 `annual_div_rate` 估算
  - snapshot 加「📊 年配息現金/單位拆分估算」段（彙總 + 每檔細節）
- [x] **測試 +10**
  - test_policy_store.py：schema 13 欄、normalize 預設/clip/garbage、estimate 5 種場景（100%/80%/0%/zero_nav/safe）、舊 Sheet 載入補預設
  - test_v2_editor.py：empty_fund_df 10 欄、merge 保留 div_cash_pct/補預設/clip
- [x] **驗證** fast tier **538 passed**（+10 新）零回歸

### v18.159 — Tab3 存讀工具列收口 + 保單清單 schema-leak 過濾 + 4 視角 AI 白話文總結（2026-05-21）

- [x] **Task A：Tab3「📋 保單管理」expander 頂部加「🚀 快速跳轉」toolbar**
  - 問題：4 顆讀寫按鈕（雲端寫入/讀回 L686-700、JSON 下載/上傳 L935-949）散在不同子段，中間夾保單清單 / 多帳本管理 / Sheet 設定等標題打斷流程
  - 修法：expander L177 加 4-column toolbar（📥 雲端讀取 / 📦 雲端存檔 / 💾 下載 JSON / 📂 上傳 JSON），click 後 `st.toast()` 告知該往下找的段落；同步在「🧰 一鍵存讀」「📁 本機 JSON 備份」標題前加 ⬇️ 視覺錨點
  - 折衷理由：4 個 section 內邏輯依賴前段 `_client/_sheet_id/_pdf` 等變數作用域，整段搬到開頭風險過高 → 採「指路 + 錨點」最低風險方案
- [x] **Task B：`load_policies` 加 schema-leak 防護過濾**
  - 問題（截圖實證）：保單清單 dataframe 列出現字串 `policy_name` / `fund_url` 當資料列（推測為 v1→v2 schema 遷移殘留，或 JSON 還原把 header dict 當 row 寫回）
  - 修法：`repositories/policy_repository.py:211` `load_policies` 末加 defensive filter — `policy_name` 或 `fund_url` 任一欄值 == 欄名本身 → 過濾掉該列
  - 新增測試 `test_load_policies_filters_schema_leak_rows`
- [x] **Task C：4 個 Tab 加「AI 白話文總結」widget（4 視角 selectbox）**
  - 新增 `services/ai_prompts.py` 4 個 builder：`build_trend_action_prompt` / `build_allocation_diagnosis_prompt` / `build_beginner_guide_prompt` / `build_news_driven_prompt`
  - 新增 `ui/helpers/ai_summary.py` — 統一 `render_ai_summary_widget(tab_key, tab_label, snapshot, headlines, gemini_api_key)`，內含 selectbox（4 視角）+ 「▶️ 生成」按鈕 + 結果 markdown
  - 集成位置：Tab1 (`_render_tab1_ai_summary`)、Tab2 (`_render_tab2_ai_summary`)、Tab3 (`_render_tab3_ai_summary`)、Tab4 (`_render_tab4_ai_summary`)；Tab4 需 cache `_bt_last_result` session_state 供 widget 取用
  - Tab5（資料診斷）/ Tab6（說明書）跳過 — 純技術 / 純文檔，無分析價值
  - 新增 5 個 prompt builder smoke tests
- [x] **驗證** fast tier **528 passed**（+9 新：5 prompt + 1 schema-leak + 3 既有未動）零回歸

### v18.158 hotfix — 策略3 智能戰情室判斷修正（2026-05-20）

- [x] **問題（1）「成立 > 3 年」近似太脆弱** 原以 `ret_3y` 是否存在近似，但 `_ret(756)` 要 NAV series ≥ 756 點才回值；低頻 NAV（週/雙週/月線）即使基金成立 5+ 年也回 None → 3-3-3 第一條誤判
  - **修法** 加 `_fund_age_years(series)` helper，從 `series.index[0]` 算實際年資；跨 3+ 年即使只 12 點月線資料也能正確判斷
- [x] **問題（2）3-3-3 三層計數讓人誤解** 原顯示「有 3Y 數據 / 年化>7% / 波動優於中位」是各自獨立通過率，看似矛盾（例：「有 3Y 數據 0 但波動優於中位 3」）
  - **修法** 改 cascade「① 成立 ≥ 3 年 → ② ① + 年化 > 7% → ③ ② + 波動優於中位」三層遞減 + 每層 delta 顯示「卡關幾檔」，user 一眼看出哪層卡關
- [x] **問題（3）撿便宜 / 警示 / 停利籃子全 0 無提示** 三標籤（Price_Zone / Health_Check / Principal_Erosion）全 N/A（metrics 缺欄）或全 Hold/Healthy 都會造成全 0，畫面卻沒提示
  - **修法** 新增 `_render_buckets_diagnostic()` — 偵測三籃子全 0 時自動掛 expander，列出每檔基金的三標籤值；user 展開即知是「N/A 數據缺」還是「真的全健康」
- [x] **驗證** 新增 `test_mk_dashboard.py` 5 個 case 測 `_fund_age_years`；全套 fast tier **519 passed**（+5 新）零回歸

---

## 專案定位
Streamlit Cloud 部署的境外共同基金監控儀表板。整合總經位階、單一基金診斷、組合再平衡試算、資料診斷五大 Tab（v18.176 移除回測 Tab，換基金判斷改用組合基金的汰弱留強/戰情室）。

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
