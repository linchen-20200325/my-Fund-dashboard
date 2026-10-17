# OAuth → Sheet → Worksheet 能力盤點 ＋ READ／WRITE 邊界稽核

- 執行組：資料工程組（安全邊界稽核），**單組產出、未經第二組獨立複驗**（CLAUDE.md §-2 規則 6）。
- 基準：`/home/user/my-Fund-dashboard` HEAD `57f03c9`（= origin/main），量測日 2026-10-17。
- 性質：唯讀。沒有修改 repo 任何檔案、沒有 checkout／reset／stash、沒有對 Google 發出任何請求。
- 標記：**實測**＝本組跑了指令、看了輸出；**讀碼**＝本組讀了原始碼；**推論**＝由讀碼加 Google API 語意推導，沒有實跑驗證。
- 原始輸出存在同目錄：`grep_strong_writes.txt`、`ast_writes.txt`／`ast_writes_gs.txt`、`ast_ambig_all.txt`、`grep_method_as_arg.txt`、`grep_write_fn_callers.txt`、`grep_settings_sheet_id.txt`、`grep_policy_sheet_id.txt`、`tests_related.txt`；掃描腳本 `ast_scan.py`、`ast_scan2.py`、`enclosing.py`。

---

## 一句話結論

1. **ui_v2 目前完全不使用 OAuth 身分讀寫 Google Sheets**：五頁都只走服務帳戶（SA），試算表 ID 只讀 secret（`SETTINGS_SHEET_ID`、`POLICY_SHEET_ID`、`POOL_SHEET_ID`／內建預設、`NAV_SHEET_ID`／內建預設）。`st.session_state["gsheet_tokens"]` 在 ui_v2 只被拿去**遮蔽錯誤訊息**，而 ui_v2 沒有任何登入／callback 程式，所以單獨跑的 ui_v2 app 裡這個值實際上應恆為空（讀碼＋推論）。
2. **ui_v2 的寫入目標只有一本：`SETTINGS_SHEET_ID`**（四張分頁、只做 `add_worksheet` 與 `append_rows`）。保單試算表在 ui_v2 只讀（有靜態守衛）。
3. **舊 UI（`ui/`）才有「OAuth 登入 → 列 Drive 資料夾 → 列 Sheet → 選一本 → 讀／寫」的完整能力**，而且寫入時用哪個身分**依路徑而異**（SA 優先、OAuth 回退／只用 OAuth／只用 SA 三種都有）。
4. **全 repo 沒有「只列 schema 合格的 Sheet」的能力**：`list_user_sheets` 只用 mimeType＋`trashed=false` 過濾；schema 判定（`detect_sheet_schema_version`、`_check_header`）都是**選定之後**才做。
5. 把「OAuth 身分＋使用者選 Sheet」接進 ui_v2，會同時撞到：L1 契約（寫死 SA＋secret ID、快取／冷卻鍵沒有身分維度）、ui_v2 import 守衛（不得 import `ui`／`infra`／`repositories`）、以及已存在的裁示（T6 只讀 secret、Q10/B7 設定試算表走 SA）。其中有數項必須由客戶裁示（見 G6）。

---

## F. OAuth / Sheet / worksheet architecture audit

### F1. `infra/oauth.py`（讀碼）

**public 函式**（`grep -n "^def \|^class \|^[A-Z_]* *=" infra/oauth.py`，實測）：

| 符號 | 作用 |
|---|---|
| `GOOGLE_OAUTH_SCOPES`（常數） | 5 個 scope（見下） |
| `GOOGLE_AUTH_URL`／`GOOGLE_TOKEN_URL`（常數） | Google 端點 |
| `OAuthError`（例外） | 全部 flow 對外例外 |
| `build_authorize_url(client_id, redirect_uri, state="", scopes=None) -> str` | `access_type=offline`、`prompt="select_account consent"`、`include_granted_scopes=true` |
| `generate_state(nbytes=24) -> str` | CSRF／session 綁定 state |
| `decode_id_token_email(tokens) -> str` | **不驗簽**解 id_token 取 email，純顯示用 |
| `exchange_code_for_tokens(code, client_id, client_secret, redirect_uri) -> dict` | 換 token，補 `expires_at` |
| `refresh_access_token(refresh_token, client_id, client_secret) -> dict` | refresh |
| `build_credentials_from_tokens(tokens, client_id, client_secret, scopes=None)` | 轉 `google.oauth2.credentials.Credentials` |
| `is_token_expired(tokens, leeway_sec=60) -> bool` | 沒 `expires_at` 視為過期 |
| `ensure_fresh_tokens(tokens, client_id, client_secret) -> dict` | 快過期就 refresh；沒 refresh_token → `OAuthError("token 已過期且沒有 refresh_token，需要重新授權")` |

⚠️ 檔頭 docstring 寫「三函式 build_oauth_flow / fetch_token / build_credentials_from_token」——**這三個名字在檔內不存在**（讀碼），是過期文字。

**scope**（`infra/oauth.py::GOOGLE_OAUTH_SCOPES`，讀碼）：
- `https://www.googleapis.com/auth/spreadsheets` —— **所有**使用者可存取試算表的讀寫（不限 app 建的檔）（推論：Google scope 語意）
- `https://www.googleapis.com/auth/drive.file` —— app 建立／開啟的檔
- `https://www.googleapis.com/auth/drive.metadata.readonly` —— 列出整個 Drive 的檔案中繼資料（v18.45 加）
- `openid`、`userinfo.email`
- 另 `build_authorize_url` 帶 `include_granted_scopes=true`：同一 OAuth client 先前授予過的 scope 會併入新 token（推論）。

**token 存放**（讀碼）：
- 只存 `st.session_state["gsheet_tokens"]`（`ui/helpers/io/oauth_state.py::handle_oauth_callback` 寫入）、email 存 `st.session_state["gsheet_email"]`、state 存 `st.session_state["_oauth_state"]`。
- **沒有 cookie／localStorage 持久化**：`git grep -niE "cookie|localStorage|extra_streamlit_components|st_cookie" -- '*.py'`（實測）只命中 `repositories/fundclear_offshore.py` 的 HTTP session cookie，與 OAuth 無關。`docs/OAUTH_SETUP.md`「安全性」段亦寫「目前刻意不做」。
- `infra/cache.py::_GLOBAL_REFRESH_KEEP_KEYS` 把 `gsheet_tokens`、`policy_sheet_id`、`active_policy_id` 列為「全域刷新」時保留的 key。
- OAuth client 設定來源：`ui/helpers/io/oauth_state.py::_resolve_oauth_cfg` —— secret `[google_oauth]` 優先，否則 `st.session_state["custom_oauth_cfg"]`（使用者在 app 內精靈自填，`ui/helpers/portfolio/policy_admin_section.py` 寫入）。

**session 失效處理**（讀碼）：
- `oauth_state._get_oauth_client()`：每次呼叫 `ensure_fresh_tokens` 並把新 token 寫回 session；refresh 失敗會**拋** `OAuthError`，**不清掉** session 裡的舊 token（沒有自動登出）。
- 各呼叫點各自處理：`ui/tab3_portfolio.py::_t3_sheet_client` 捕捉後退回 SA；`ui/tab3_t7_ledger.py` 三處、`ui/tab3_portfolio.py` 批次加入捕捉後 log＋跳過同步；`ui/tab_manage.py::_policy_client_and_sheet` 回 `(None, reason)`。
- 重新整理頁面／重開 app → session 消失 → 需重登（`docs/OAUTH_SETUP.md` 同此）。
- 登出：`ui/sidebar.py` 的「🚪 登出」pop `gsheet_tokens`／`gsheet_email`／`_oauth_state`／`active_policy_id`（不撤銷 Google 端授權，讀碼）。
- callback state 守門：`oauth_state._should_reject_oauth_code` 只在「本 session 記得 state 且回傳 state 不符」才拒；session 遺失（expected=None）一律放行（v19.305 user 選擇的可用性取捨，檔內 docstring 自陳會重開「多分頁互搶授權碼」窗口）。

### F2. client 建立與列舉函式（讀碼＋實測 grep）

| 符號 | 簽名 | 回傳 |
|---|---|---|
| `repositories/policy/_helpers.py::get_gspread_client` | `(credentials) -> gspread.Client` | SA；scope `_SCOPES` = `spreadsheets` ＋ `drive.readonly` |
| `repositories/policy/_helpers.py::get_gspread_client_from_oauth` | `(user_credentials) -> gspread.Client` | `gspread.authorize(OAuth Credentials)` |
| `repositories/policy/v2.py::list_policy_worksheets` | `(client, sheet_id) -> list[str]` | 分頁名，過濾 `_` 開頭與 `Policies` |
| `repositories/policy/v2.py::list_user_sheets` | `(client, folder_id="") -> list[dict]` | Drive v3 `files`，`mimeType=spreadsheet`＋`trashed=false`（＋`"<folder>" in parents`，**只直屬子項、不遞迴**）；`[{"id","name"}]` 依名排序 |
| `repositories/policy/v2.py::list_user_folders` | `(client) -> list[dict]` | Drive 全部資料夾（含共享），`[{"id","name"}]` |
| `repositories/policy/v2.py::get_sheet_title` | `(client, sheet_id) -> str` | 失敗回 `""` |
| `repositories/policy/v2.py::detect_sheet_schema_version` | `(client, sheet_id) -> "empty"|"v1"|"v2"` | 依保單分頁 header 是否含 `fund_code`／`基金代號` |
| `ui/helpers/io/oauth_state.py::_get_oauth_client` | `() -> gspread.Client | None` | L3 包裝：讀 session token → refresh → `get_gspread_client_from_oauth` |

`repositories.policy_repository` 是 `repositories/policy/` 子套件的 re-export（`repositories/policy/__init__.py` 以 `dir()`＋`globals()` 全量轉出）。

**呼叫點**（指令：`for f in get_gspread_client_from_oauth get_gspread_client list_policy_worksheets list_user_sheets list_user_folders create_dashboard_sheet detect_sheet_schema_version; do git grep -nw "$f" -- '*.py' | grep -v "^tests/" | grep -v "def $f"; done`，實測）：

- **舊 UI（`ui/`）**
  - `get_gspread_client_from_oauth`：`ui/helpers/io/oauth_state.py::_get_oauth_client`、`ui/tab3_portfolio.py`（批次加入）、`ui/tab3_t7_ledger.py` 三處。
  - `get_gspread_client`（SA）：`ui/tab3_portfolio.py::_t3_sheet_client`、`ui/helpers/portfolio/policy_admin_section.py` 兩處（舊 SA 表單）。
  - `list_user_folders`／`list_user_sheets`／`create_dashboard_sheet`：只在 `ui/helpers/portfolio/policy_admin_section.py`。
  - `list_policy_worksheets`：`ui/helpers/cloud_io.py`、`ui/helpers/portfolio/policy_admin_section.py`、`ui/helpers/v2_editor.py`、`ui/tab3_portfolio.py`、`ui/tab3_t7_ledger.py`。
  - `detect_sheet_schema_version`：`ui/helpers/cloud_io.py`、`ui/helpers/portfolio/policy_admin_section.py`、`scripts/weekly_switch_notify.py`。
- **ui_v2**：**上列全部 0 命中**（實測）。ui_v2 對 Google 的唯一接觸是經 `services/v2_tables/*` → L1 SA 函式（見 F6）。
- 其他 SA 使用者：`repositories/settings_sheet_repository.py::_make_client`、`repositories/policy_supplement_repository.py::_make_client`、`repositories/pool_repository.py::_get_sheet`、`repositories/portfolio_perf_repository.py::_get_sheet`、`services/nav_history_gs.py::_get_sheet`、`services/macro/weights_store.py::_gs_get_worksheet`、`scripts/*`。

### F3. 舊 UI 的資料夾／Sheet／worksheet 選擇（讀碼）

- 位置：`ui/tab3_portfolio.py::render_portfolio_tab` → `ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section`，「📋 保單管理（Google Sheets）」收合區 → 「🚀 快速存讀面板」→「📥 雲端讀取」子面板（`_io_panel == "load"`）。只有 `_oauth_configured and _logged_in_q` 時顯示。
- 流程：
  1. 「🔄 載入資料夾清單」→ `list_user_folders(_get_oauth_client())` → `st.session_state["_my_folders"]`。
  2. 「📁 限定資料夾」selectbox（含「🌐 整個帳號」）→ `st.session_state["_drive_folder_id"]`。
  3. 「📂 從 Drive 列出 Sheets」→ `list_user_sheets(..., folder_id=...)` → `st.session_state["_my_sheets"]`。
  4. selectbox 選一本 →「✅ 使用此 Sheet 作為投組資料庫」→ `st.session_state["policy_sheet_id"] = 選定 id`、清 `_t3_cur_sheet_title`、rerun。
  5. 之後偵測到 `policy_sheet_id` 變了 → 自動 `ui/helpers/cloud_io.py::load_all_from_sheet` 讀回（讀路徑，見 G1 說明）。
- 另一條：「✨ 新增帳本」→ `create_dashboard_sheet(_get_oauth_client(), title)` 建全新 Spreadsheet 並設為 `policy_sheet_id`。
- worksheet 選擇：沒有給使用者選 worksheet 的 UI；保單分頁＝`list_policy_worksheets` 過濾後的全部分頁（tab 名＝`policy_id`）。
- sidebar 另有「工作中帳本」區（`ui/sidebar.py`，v18.164 hoist）。
- **「只列 schema-valid Sheet」：沒有這個能力**（讀碼）。`list_user_sheets` 只過濾 mimeType 與 trashed；選定時**不做任何 schema 檢查**。事後才有的判定：`detect_sheet_schema_version`（保單 v1/v2/empty）、`settings_sheet_repository._check_header`、`policy_supplement_repository._check_header`（逐分頁標頭比對）、`load_supplement_tabs` 的 `tab_missing`。這些都可以拿來組一個「選定前的唯讀探測」，但**目前不存在**。

### F4. 保單 repository（`repositories/policy/`）讀寫清單（讀碼）

- **讀**：`v1.load_policies`、`v2.list_policy_worksheets`、`v2.load_policy_worksheet`、`v2.load_all_policy_worksheets`（60 秒 TTL、key=sheet_id）、`v2.load_all_policy_worksheets_with_error`、`v2.get_sheet_title`、`v2.detect_sheet_schema_version`、`v2.is_v2_worksheet`、`v2.load_policy_v2`、`v2.load_all_policies_v2`、`v2.list_user_sheets`、`v2.list_user_folders`。
- **寫**（AST 掃描對應的外層函式，實測，見 `ast_writes_gs.txt`）：`v1.upsert_policy_row`（update／append_row）、`v1.delete_policy_row`（delete_rows）、`v2.ensure_policy_worksheet`（add_worksheet／update header）、`v2.upsert_fund_in_policy`（update header 升級／append_row／update）、`v2.delete_fund_in_policy`（delete_rows）、`v2.delete_policy_worksheet`（del_worksheet）、`v2.rename_sheet`（update_title）、`v2.create_dashboard_sheet`（`client.create` 建新 Spreadsheet）、`v2.write_policy_v2`（add_worksheet／**`ws.clear`**＋update 整頁覆寫）、`v2._apply_v2_header_format`（format）、`v2.copy_sheet_as_backup`（`client.copy` 建新 Spreadsheet）。
- **身分**：一律由**呼叫端注入 client**（SA 或 OAuth 都可），本套件不自己選身分。
- **Sheet ID 來源**：一律是參數 `sheet_id`。舊 UI 傳 `st.session_state["policy_sheet_id"]`，沒有時（部分路徑）退 secret `POLICY_SHEET_ID`（`oauth_state._sheet_id_secret`）。
- 對照：ui_v2 讀保單用的是**另一個** L1 —— `repositories/policy_supplement_repository.py`：只讀、**寫死 SA**（`_service_account()`＋`_make_client`）、ID 只讀 secret `POLICY_SHEET_ID`，**不退回 session、不退回其他 secret**（`policy_sheet_id(*, mask)`）。檔頭自陳：「49 6.2 T6 說憑證仍可走 OAuth 或服務帳戶兩條路，本檔本輪只接服務帳戶；OAuth 那一條沒有做（回報列為待裁）」。

### F5. `SETTINGS_SHEET_ID` 與 `POLICY_SHEET_ID` 讀取點（實測）

指令：`git grep -n "SETTINGS_SHEET_ID"` → 72 行／21 檔；`git grep -n "POLICY_SHEET_ID"` → 131 行。完整輸出：`grep_settings_sheet_id.txt`、`grep_policy_sheet_id.txt`。排除 `docs/`、`tests/`、`.md`、`.html` 後：

- **`SETTINGS_SHEET_ID`**：程式的**唯一讀取點**是 `repositories/settings_sheet_repository.py::SECRET_KEY` → `settings_sheet_id()`（`infra.config.get_secret`：`st.secrets` → 環境變數；無預設值，缺 → `SettingsSheetError(code="not_configured")`）。`services/v2_tables/masking.py::MASKED_WHOLE_VALUE_KEYS` 把它列為要遮的鍵；`ui_v2/app_preview.py` 只在 docstring 提到。**舊 UI（`app.py`、`ui/`）0 命中** —— 這本只有 ui_v2 在用。
- **`POLICY_SHEET_ID`**：程式讀取點 ——
  - ui_v2 路徑：`repositories/policy_supplement_repository.py::SECRET_KEY`（只讀這個，不退回）。
  - 舊 UI：`ui/helpers/io/oauth_state.py::_sheet_id_secret`（module-level 讀一次，作為 session `policy_sheet_id` 的備援）；`ui/tab_manage.py::_policy_client_and_sheet` 同樣「session 優先、secret 次之」。
  - 排程：`scripts/weekly_nav_backfill.py`、`scripts/weekly_switch_notify.py`（未設退 `macro_weights_sheet_id`）、`scripts/fetch_nav_cache.py`（未設退 `SHEET_ID`）；三支 workflow yml 傳入。
- **ui_v2/set 與 ui_v2/hld 怎麼取資料來源**：
  - set：`ui_v2/set/source.py::load_live` → `settings_store.load_user_settings`／`load_fetch_log`／`load_market_indicator`／`sheet_title`／`sheet_gate` → `settings_sheet_repository`（SA ＋ `SETTINGS_SHEET_ID`）。
  - hld：`ui_v2/hld/source.py` → `alo_holdings`（→ `policy_supplement_repository`，SA ＋ `POLICY_SHEET_ID`）＋ `settings_store.load_user_settings`（SA ＋ `SETTINGS_SHEET_ID`）＋ `nav_dividend`（淨值 A 鏈，見 F6）。
  - 兩頁的 `_secret_values()` 讀 `st.secrets`、`os.environ`、`st.session_state["gsheet_tokens"]`、`["custom_oauth_cfg"]` —— **只用於遮蔽**（`masking.secret_values`），不建 client。

### F6. ui_v2 五頁的取數身分（讀碼）

| 頁 | Google Sheets 讀取 | 身分 | Sheet ID |
|---|---|---|---|
| mkt | `settings_store.load_user_settings`（＋ Yahoo／FRED 取數，非 Sheets） | SA | `SETTINGS_SHEET_ID` |
| hld | `alo_holdings.load_alo_tables`（保單分頁＋`_持倉補充`＋`_保單資料`）、`settings_store.load_user_settings`；淨值 A 鏈經 `services/moneydj_fetcher.py::nav_history_shared_reads` 讀 `nav_history` | SA（保單、設定）；`nav_history` 走 `services/nav_history_gs.py::_get_sheet`，ui_v2 不注入 OAuth ⇒ SA | `POLICY_SHEET_ID`、`SETTINGS_SHEET_ID`、`NAV_SHEET_ID`（未設 → 檔內寫死預設） |
| exp | `exp_universe.load_pool_codes(values, oauth_client=None)` → `pool_repository.get_pool_store(None)`；`settings_store.load_user_settings`；淨值同 A 鏈 | SA（`ui_v2/exp/source.py` 註明「`oauth_client` 恆為 None：取登入者 client 的函式住在舊樹 ui/，ui_v2 不得 import」） | `POOL_SHEET_ID`（未設 → 檔內寫死預設）、`SETTINGS_SHEET_ID` |
| alo | `alo_holdings.load_alo_tables`、`settings_store.load_user_settings`、`settings_store.load_market_indicator`；市值基準時淨值 A 鏈 | SA | `POLICY_SHEET_ID`、`SETTINGS_SHEET_ID`、（`NAV_SHEET_ID`） |
| set | `settings_store.load_user_settings`／`load_fetch_log`／`load_market_indicator`／`sheet_title`／`sheet_gate` | SA | `SETTINGS_SHEET_ID` |

- ui_v2 本身**不 import gspread／repositories／infra**：`tests/ui_v2/test_ui_v2_live_import_guard.py`（`_OLD_ROOTS`＝`ui`、`services`、`repositories`、`shared`、`infra`、`fund_fetcher`；`_NET_ROOTS` 含 `gspread`；只有 `ui_v2/<頁>/source.py` 可依逐檔白名單 import `services.v2_tables.*`；禁動態 import）。本組讀碼確認，**未實跑該測試**。
- ui_v2 **沒有任何登入／callback 程式**：`git grep -nE "build_authorize_url|handle_oauth_callback|_get_oauth_client|oauth_state|infra\.oauth|from ui\." -- 'ui_v2/**'` 只命中 docstring／註解（實測）。

---

## G. READ / WRITE boundary audit

### G1. 全 repo 對 Google Sheets／Drive 的寫入呼叫點

**方法（三種，互補；指令全部實跑）**

1. 字面 grep（強寫入方法名，不含易與 dict 撞名的 `update`／`clear`／`copy`／`create`）：
   ```
   git grep -nE "\.(append_row|append_rows|insert_row|insert_rows|insert_cols|add_rows|add_cols|delete_rows|delete_row|delete_columns|delete_dimension|batch_clear|values_update|values_append|values_clear|values_batch_update|batch_update|update_cell|update_cells|update_acell|add_worksheet|del_worksheet|duplicate_sheet|update_title|update_index|update_tab_color|del_spreadsheet|import_csv|insert_permission|remove_permission|share|merge_cells|batch_format|add_protected_range|set_basic_filter|freeze|resize)\(" -- 'ui/**' 'ui_v2/**' 'repositories/**' 'services/**' 'infra/**' 'scripts/**' 'app.py' 'fund_fetcher.py' 'mcp_server/**'
   ```
   → 31 行（含 4 行註解／刪除線內的舊寫法），`grep_strong_writes.txt`。
2. 「方法被當參數傳」的寫法（例 `_with_quota_retry(ws.update, ...)`），字面 grep 1 結構上掃不到：
   ```
   git grep -nE "\.(update|clear|append_row|append_rows|batch_update|batch_clear|values_update|values_append|values_clear|add_worksheet|del_worksheet|delete_rows|insert_rows|insert_row|update_cells|resize|create|copy|update_title|add_cols|add_rows)\s*[,)]" -- (同上目錄)
   ```
   → 16 行，`grep_method_as_arg.txt`（`snapshot_repository.py` 的寫入全部只在這裡出現）。
3. AST 掃描（`ast_scan2.py`）：所有 `Attribute.attr ∈ 寫入字表`，含 call 與 ref 兩種；`update/clear/copy/format/sort` 只保留接收者名像 worksheet／spreadsheet／client 的（`ws`、`sh`、`spreadsheet`、`client`…）。→ 63 筆，去掉 2 筆非 Sheets（`policy_supplement_repository.py` 的 dict `target.update`、`portfolio_service.py` 的 list `.sort`）後 61 筆，`ast_writes_gs.txt`；外層函式對照由 `enclosing.py` 產生。

**已知分類（依目錄）**

- **`ui/`：0 處直接 gspread 寫入呼叫**（三法皆 0，實測）。舊 UI 的寫入全部經 repository 函式（下表右欄），呼叫點見 `grep_write_fn_callers.txt`。
- **`ui_v2/`：0 處**（三法皆 0，實測；且有 import 守衛禁 `gspread`）。
- **`repositories/`**：

  | 檔::函式 | 寫入動作 | 身分／ID |
  |---|---|---|
  | `settings_sheet_repository.py::_worksheet_for_append`、`_append`（經 `save_user_setting`／`open_fetch_log`／`close_fetch_log`／`append_market_indicator`） | `add_worksheet`（分頁不存在）、零列時 `append_rows([header])`、`append_rows` | **SA 寫死**；`SETTINGS_SHEET_ID` |
  | `policy/v1.py::upsert_policy_row`、`delete_policy_row` | `update`、`append_row`、`delete_rows` | 注入 client；參數 sheet_id |
  | `policy/v2.py::ensure_policy_worksheet`、`upsert_fund_in_policy`、`delete_fund_in_policy`、`delete_policy_worksheet`、`rename_sheet`、`create_dashboard_sheet`、`write_policy_v2`、`_apply_v2_header_format`、`copy_sheet_as_backup` | `add_worksheet`、`update`、`append_row`、`delete_rows`、`del_worksheet`、`update_title`、`client.create`、`ws.clear`、`format`、`client.copy` | 注入 client；參數 sheet_id |
  | `ledger_repository.py::ensure_ledger_worksheet`、`append_ledger_row`、`replace_ledgers_for_policy` | `add_worksheet`、`append_row`、`delete_rows` | 注入 client |
  | `snapshot_repository.py::ensure_state_worksheet`、`_ensure_overview_worksheet`、`save_all_ledgers_snapshot`、`save_holdings_overview` | `add_worksheet`、`append_row`、`ws.clear`、`update` | 注入 client |
  | `pool_repository.py::GoogleSheetsPoolStore._ws`（for_write）、`upsert`、`remove` | `add_worksheet`、`update`（含改寫 header）、`append_row`、`delete_rows` | SA 優先、注入 OAuth 回退；`POOL_SHEET_ID` → 檔內寫死預設 |
  | `portfolio_perf_repository.py::GoogleSheetsPerfStore._ws_for_write`、`append_snapshot` | `add_worksheet`、`update`、`append_row` | SA；`macro_weights_sheet_id` |
  | `policy_supplement_repository.py` | **無寫入**（有守衛 `tests/test_policy_supplement_repository.py::test_C4_模組沒有任何寫入函式`） | SA；`POLICY_SHEET_ID` |
- **`services/`**：`nav_history_gs.py::_get_worksheet`（add_worksheet／update header）、`_ensure_grid_width`（`add_cols`）、`append_points`（`append_rows`, `USER_ENTERED`）；`macro/weights_store.py::_gs_get_worksheet(for_write=True)`（add_worksheet／update）。`services/v2_tables/*`：**0 處直接寫入**，寫入全經 `settings_sheet_repository`。
- **`scripts/`**：AST 0 處直接寫入；經 repository：`scripts/migrate_v149_schema.py`（`write_policy_v2`、`copy_sheet_as_backup`）、`scripts/accumulate_nav_tw.py`／`scripts/migrate_nav_caches_to_sheet.py`／`scripts/weekly_nav_backfill.py`（`append_points`／`backfill_to_gs`）。
- **非 gspread 方法的 Drive 呼叫**：`policy/v2.py::list_user_sheets`／`list_user_folders` 走 `client.http_client.request("get", drive/v3/files)`（唯讀）。AST 另掃 `.request`／`.post`（`ast_ambig_all.txt`），其餘命中為 FRED／LLM／OAuth token／asset_publish 等非 Sheets 端點。

**字表未涵蓋的形態（誠實揭露）**：
- 以變數持有方法再呼叫（`fn = ws.update; fn(...)` 之外的更深間接）、`getattr(ws, "update")` 字串反射、動態 import；
- 接收者命名不在 AST 白名單（例 `w`、`tab`）時的 `update`／`clear`／`copy`；
- 直接打 Sheets REST（`http_client.request("post"/"put", sheets/v4/...)`）且 URL 動態組出者 —— 本組只確認 `.request` 三處命中皆為 GET 或非 Sheets；
- gspread 未列入字表的新方法名；`mcp_server/` 已在掃描範圍內，0 命中。
⇒ 上列是**已知分類，不是窮舉**。

### G2. ui_v2/set 的寫入（讀碼）

- **寫到哪**：只有 `SETTINGS_SHEET_ID` 那一本；分頁 `user_setting_log`（存檔）、`fetch_log_open`／`fetch_log`／`market_indicator`（「重新取數」）。路徑：`ui_v2/set/page.py::_live_save` → `ui_v2/set/source.py::save_setting` → `settings_store.save_setting_for_page` → `settings_store.save_user_setting`（先 `check_setting_value` 型別檢查）→ `settings_sheet_repository.save_user_setting`。重新取數：`ui_v2/set/source.py::refetch` → `settings_store.REFETCH_BY_TIER`。
- **目標如何決定**：固定 secret，**沒有參數、沒有 session 覆寫、沒有預設值**。
- **draft vs saved**：沒有正式的草稿模型。輸入欄當下值（widget state）＝未存；按「存檔」才寫，且只寫 `live.changed_settings` 判定有改動的鍵（`tests/ui_v2/test_set_live_logic.py::test_存檔_要寫的只有被改的那幾鍵_清空為None`）。存檔結果暫存 `st.session_state["_set_live_save_results"]`，下一輪畫「已存檔」或失敗框。每鍵逐列追加、**沒有交易**（多鍵部分成功時表上新舊混搭；`docs/v2/55` §6 第 14 條對 hld 有同樣記載）。`user_setting_log` 追加**不重試**（`50` §6）。
- **防寫錯 Sheet 的既有防線**：
  - ID 只來自 secret、無預設 ID（`tests/test_settings_sheet_repository.py::test_模組內沒有寫死任何預設ID`、`test_沒設SETTINGS_SHEET_ID_報未設定且不打上游`）；
  - 每次讀寫比對第 1 列標頭，不符就停、不改寫（`_check_header`；`test_標頭不符_讀寫都停_不改寫標頭`）；
  - 寫入閘門 `gate_status`（未設 ID／缺 SA／冷卻 → 存檔停用）；
  - set 頁顯示「設定試算表：{title}」（`ui_v2/set/live.py` 的 `TEXT_TITLE`；`tests/test_settings_sheet_title_gate.py`）—— 人工辨識；
  - SA 必須是該本編輯者（分享即白名單）。
  - ⚠️ **缺口**：分頁**不存在**時會自動 `add_worksheet` 再寫 → 若 secret 指到一本 SA 有編輯權、但不是設定試算表的檔，程式會在那本新建四張分頁並寫入，沒有「標記欄／標記分頁」驗證（讀碼）。
- **測試**：`tests/test_settings_sheet_repository.py`（51）、`tests/test_settings_sheet_title_gate.py`（10）、`tests/test_v2_tables_settings_store.py`（60）、`tests/test_v2_tables_settings_store_page.py`、`tests/ui_v2/test_set_live_logic.py`（67）、`tests/ui_v2/test_set_live_page.py`（12，slow）、`tests/_fake_settings_sheet.py`（替身）。數字為 `grep -c '^def test_'` 實測，**本組未實跑這些測試**。

### G3. ui_v2/alo 是否寫入（讀碼）

- **會**：ALO-1／ALO-4 的「存檔」→ `ui_v2/alo/source.py::save_setting` → `settings_store.save_setting_for_page` → `user_setting_log`（`alo_` 開頭五鍵）。
- **不會**寫保單試算表（`policy_supplement_repository` 無寫入函式）、不寫 `market_indicator`（只讀）、不寫淨值。
- 同樣會寫入的還有 mkt、exp、hld 的「存檔」（`ui_v2/*/source.py::save_setting`，實測 grep），全部寫同一本 `user_setting_log`。
- 淨值 A 鏈（alo／hld／exp 呼叫 `nav_dividend`）：`git grep` 在 `services/v2_tables` 與 `services/moneydj_fetcher.py` 找不到 `append_points`／`backfill_to_gs`／`nav_history_store` 寫入函式呼叫（實測）；`nav_history_shared_reads` 為讀取。⚠️ 間接深層路徑未逐層追到底，屬**已知分類**。

### G4. 登入後是否自動取得寫入能力；寫入時用誰的身分

- **token 層**：是。scope 含 `spreadsheets`（全部可存取試算表讀寫）＋`drive.file`，登入即具備寫入**能力**（讀碼＋推論）。
- **app 層（舊 UI）**：登入不會自動寫；寫入都由按鈕觸發。但**身分依路徑不同**（讀碼）：

  | 舊 UI 寫入路徑 | 身分 | Sheet ID |
  |---|---|---|
  | 「📦 立即全部寫入」→ `cloud_io.dump_all_to_sheet`（v2：`write_policy_v2` 會 `ws.clear`；v1／empty：`upsert_fund_in_policy` 會建分頁）；backfill 先 `copy_sheet_as_backup` | `_t3_sheet_client`：**SA 優先**，SA 開不了（403/404、非 429）且已登入 → OAuth | session `policy_sheet_id` → secret |
  | 批次加入基金同步（`ui/tab3_portfolio.py` `upsert_fund_in_policy`） | **只用 OAuth** | session `policy_sheet_id`（無 secret 備援） |
  | T7 帳本同步（`ui/tab3_t7_ledger.py`：`append_ledger_row`、`replace_ledgers_for_policy`、`upsert_fund_in_policy`、`save_all_ledgers_snapshot`、`save_holdings_overview`） | **只用 OAuth** | session `policy_sheet_id` |
  | 「✨ 新增帳本」`create_dashboard_sheet` | **只用 OAuth** | 新建 |
  | 舊 SA 表單（`upsert_policy_row`／`delete_policy_row`，`_gsa_secret and not _oauth_configured`） | **只用 SA** | 區域 `_sheet_id` |
  | 選股池 `pool_repository` upsert／remove（`ui/tab_manage.py`） | SA 優先、注入 OAuth 回退 | `POOL_SHEET_ID` → 寫死預設 |
  | `nav_history_gs.append_points`（`ui/helpers/nav_history_hook.py`、`ui/tab_manage.py`） | SA 優先、注入 OAuth 回退 | `NAV_SHEET_ID` → 寫死預設 |
  | `portfolio_perf_repository.append_snapshot`（`switch_advisor_section.py`） | SA | `macro_weights_sheet_id` |
- **ui_v2**：一律 SA，OAuth 完全不參與寫入（讀碼）。

### G5. 風險逐項判定

| 風險 | ui_v2 | 舊 UI | 證據／標記 |
|---|---|---|---|
| **arbitrary Sheet write** | **已有防線**：寫入目標只來自 secret `SETTINGS_SHEET_ID`；ui_v2 不得 import gspread／repositories（import 守衛）；保單 L1 無寫入函式（C4 守衛） | **無 app 層防線**：使用者可從 Drive 任選一本（`list_user_sheets` 不篩 schema）設為 `policy_sheet_id`，之後「全部寫入」會在該本建保單分頁或 `ws.clear` 保單分頁；邊界只剩使用者自己的 Google 權限（`spreadsheets` scope）或 SA 被分享範圍 | 讀碼 |
| **silent wrong Sheet** | **部分防線**：標頭不符即停；set 頁顯示標題。**缺口**：分頁不存在時自動建立並寫入（錯本若 SA 可編輯，會靜默長出四張分頁）；`POOL_SHEET_ID`／`NAV_SHEET_ID` 未設時靜默退到檔內寫死的那一本（ui_v2 對它們只讀；`50` §2 已登記此類風險） | **部分防線**：`detect_sheet_schema_version` 決定 v1/v2 路徑、`copy_sheet_as_backup` 先備份（backfill 路徑）；但 ID 有 session／secret 兩個來源，不同寫入路徑看的來源也不同（見 G4 表） | 讀碼 |
| **自動建立 production Sheet** | **未發現路徑**：ui_v2 可達的 L1 只會 `add_worksheet`（分頁），不會建 Spreadsheet；`client.create`／`client.copy` 只在 `policy/v2.py::create_dashboard_sheet`／`copy_sheet_as_backup`，呼叫點只在 `ui/` 與 `scripts/`。**本組未找到專門守這條的測試** | 有，但都是按鈕觸發：「✨ 新增帳本」建新本；「全部寫入」backfill／`migrate_v149_schema` 先 copy 出備份本 | 實測 grep／AST ＋ 讀碼 |
| **Preview 的 SETTINGS_SHEET_ID 指到 production** | **無程式防線**：預覽與正式 ui_v2 用同一個鍵、同一個 L1，程式分不出是哪個環境。**流程防線**：客戶 2026-10-16 裁示第 1 點「驗收期間指向複本」（`docs/v2/55` §4），驗收前看 set 頁標題。**實際 Cloud secret 指向哪本：無法判定**（本組看不到部署 secrets） | 不適用（舊 UI 不讀這個鍵） | 讀碼；部署面無法判定 |
| **login 後默認全寫權** | 不適用（ui_v2 不用 OAuth） | **token 層：是**（`spreadsheets` 全權 ＋ `include_granted_scopes=true`）；app 層寫入需按鈕觸發。沒有 scope 收窄或「唯讀登入」選項 | 讀碼＋推論 |

### G6. 「OAuth 身分 ＋ 使用者選 Sheet」接到 ui_v2 的架構衝突

**衝突點（讀碼）**
1. **L1 契約寫死 SA ＋ secret ID**：`settings_sheet_repository._service_account/_make_client/settings_sheet_id`、`policy_supplement_repository._service_account/_make_client/policy_sheet_id` 都不收 client 也不收 sheet_id 參數。
2. **快取與冷卻沒有身分維度**：兩支 L1 的模組層快取以 `sheet_id` 為鍵、跨 session 共用；冷卻 `ACTOR = "sa"`。改成 per-user OAuth 後，同一本被不同登入者讀到的結果會互相共用、冷卻互相牽連（`50` 第 10 節 B7 已點出「快取鍵要改成登入者＋試算表 ID」）。
3. **ui_v2 import 守衛**：ui_v2 不得 import `ui`、`infra`（含 `infra.oauth`）、`repositories`；`source.py` 只能 import 逐檔白名單內的 `services.v2_tables.*`。取 OAuth client 的現有函式（`ui/helpers/io/oauth_state.py::_get_oauth_client`）住在舊樹 → 必須新增 L2 模組或改白名單（改測試＝治理變更）。
4. **ui_v2 沒有登入流程**：沒有 authorize 按鈕、沒有 callback 處理。預覽是獨立 Streamlit app，需要另登 redirect_uri；且 `ui/tab3_portfolio.py` v19.302 註解記載 Streamlit Cloud 上 app 內 OAuth 會與平台登入相撞。
5. **既有裁示**：`49` §6.2 **T6**（客戶 2026-09-27 核准「保單那一本」；總管技術裁定 ui_v2 只讀 secret `POLICY_SHEET_ID`、不退回 session）；`50` **Q10**（客戶：設定試算表由客戶自建並分享給 SA）、**B1**（ID 只放 secret）、**B7**（建議一律 SA；L1 檔頭寫「本檔拍板：一律服務帳戶」—— 屬總管／實作組技術裁定，非客戶裁示）。「使用者選 Sheet」直接牴觸 T6 的總管裁定與 Q10 的前提。
6. **scope 太寬**：沿用 `GOOGLE_OAUTH_SCOPES` 等於讓 ui_v2 登入者具備任意試算表寫權；而 `include_granted_scopes=true` 讓同一 OAuth client 先前授予的寬 scope 會被併入（推論），即使 ui_v2 另傳窄 scope 也可能拿到寬 token。
7. **沒有 schema 篩選**：使用者選 Sheet 時沒有既成的「這本是否合格」探測函式。

**不做 migration 前提下的最小安全接線（只描述，未實作）**
- **方案 0（\u63a8\u85a6現狀維持）**：寫入維持「SA ＋ secret `SETTINGS_SHEET_ID`」不變；OAuth 不接入 ui_v2 的任何寫入路徑。這是目前程式的狀態，零改動。
- **方案 1（只開 OAuth「讀」保單，寫入不動）**：
  1. 新增一支 L2 入口（`services/v2_tables` 內），接受 L3 注入的 OAuth client 與 sheet_id，比照 `pool_repository._get_sheet(oauth_client=...)` 的「注入」體例；
  2. `policy_supplement_repository` 增加可選的 client／sheet_id 注入參數，**快取鍵與冷卻 actor 加入身分**（例：`(actor_email_or_sa, sheet_id)`）；
  3. 使用者選定前先跑**唯讀探測**：`_check_header`（`_持倉補充`、`_保單資料`）＋ 保單分頁 header 判 v2，不合格不接受；
  4. ui_v2 登入流程要求**唯讀 scope**（`spreadsheets.readonly`、`drive.metadata.readonly`），並評估 `include_granted_scopes` 對此的影響（需要獨立 OAuth client 才能保證窄 scope —— 推論，未驗）；
  5. 所有寫入仍只到 SA ＋ `SETTINGS_SHEET_ID`；選定的保單本只讀。
- **寫入目標綁定（若未來要讓 OAuth 寫）**：至少需要「寫入目標 ∈ secret 白名單」或「目標本內必須有一個標記分頁／標記儲存格」；後者要在既有生產試算表上新增標記＝資料變更。

**必須由客戶裁示的部分**（依 `PROJECT_RULES.md` 第 4 節 Stop／Decision Gate 的分類，讀法為本組判斷）
- ui_v2 是否引入 OAuth 身分（替換／新增 production data source 的身分規則、data identity 規則）；
- 是否推翻／修改 T6「ui_v2 只讀 secret `POLICY_SHEET_ID`、不退回 session」；
- 設定試算表是否可由使用者自選（牴觸 Q10 前提）；
- OAuth scope 收窄（會影響舊 UI 依賴 `spreadsheets`／`drive.file` 的寫入與「✨ 新增帳本」）；
- 在生產試算表加標記分頁／標記欄（資料變更）；
- 預覽與正式 ui_v2 是否改成程式層強制不同本（例：獨立鍵名或環境旗標）—— 產品／部署方向。
- 技術細節（快取鍵設計、L2 模組命名、探測函式寫法）屬內部自決。

### G7. 規格／裁示文件 vs 現況

| 文件 | 相關規格 | 現況是否一致 |
|---|---|---|
| `docs/v2/50_settings_sheet_design.md` §2 | 不寫保單試算表；ID 只放 secret；無預設 ID；不退本地檔；憑證 SA | **一致**（`settings_sheet_repository.py`、相關測試） |
| `50` §6 | 只做 `append_rows` 與零列寫標頭；不刪分頁、不清除、不改寫 | **一致**（實測 grep：該檔寫入類只有 `add_worksheet`、`append_rows`；`.clear(` 為快取 dict） |
| `50` §7.1 | 標頭不符停下、不改寫；分頁不存在則建立 | **一致**；但「分頁不存在即建立」正是 G2 所列錯本缺口 |
| `50` §10 B7 | 「建議一律用服務帳戶」（表內只寫建議） | 程式已照建議實作（L1 檔頭「本檔拍板」）；**文件該列未標定案** |
| `docs/v2/55_preview_acceptance_guide.md` §2／§4 | 五頁存檔＋重新取數寫 `SETTINGS_SHEET_ID`；客戶裁示驗收期間指向複本 | **一致**（讀碼）；複本是否實際設定無法判定。§2 自陳 `ui_v2/app_preview.py` 檔頭寫入頁清單仍未列持倉體檢 —— 本組讀檔頭確認該句確實只列四頁 |
| `docs/v2/49` §4.1「OAuth 與服務帳戶兩條路」 | 「ui_v2 沿用『有 SA 就優先用它』同一條規則」 | **部分不一致**：ui_v2 實作只有 SA，沒有 OAuth 回退（`policy_supplement_repository` 檔頭自陳「OAuth 那一條沒有做（回報列為待裁）」） |
| `49` §6.2 T6 | ui_v2 只讀 secret `POLICY_SHEET_ID` | **一致** |
| `docs/OAUTH_SETUP.md` | scope 4 個；「兩者皆有 → 預設 OAuth，可選 SA fallback」；登入在 Tab3 expander；「貼上 Sheet ID」 | **不一致**：程式 scope 5 個（多 `drive.metadata.readonly`）；`_t3_sheet_client` 是 **SA 優先**、OAuth 回退（v19.302／v19.431）；登入在 sidebar（v18.75）；選本改為 Drive 列表 |
| `docs/POLICY_SHEETS_SETUP.md` | 對應檔 `policy_store.py`；單一 `Policies` 分頁 v1 schema；驗證範例 `from policy_store import ...` | **不一致**：`policy_store.py` 不存在（實測 `ls`）；現行為 `repositories/policy/` 與每保單一頁（v2 10 欄）；範例 import 會失敗 |
| `infra/oauth.py` 檔頭 | 「三函式 build_oauth_flow / fetch_token / build_credentials_from_token」；「根目錄 oauth_helper.py 保留 shim」 | **不一致**：三個函式名不存在；`oauth_helper.py` 不存在（實測 `ls`） |

### G8. 既有相關測試檔（`git grep -lE` 字表命中 87 檔，`tests_related.txt`；以下為本組讀過檔名／測試名後的分類，**未實跑**）

- **OAuth**：`tests/test_oauth_callback_state.py`（state 守門）、`tests/test_tab3_sa_client_preference.py`（SA 優先＋OAuth 回退）、`tests/test_pool_oauth_fallback_v19508.py`、`tests/test_nav_history_oauth_v19509.py`、`tests/test_tab_manage_pool_oauth_v19520.py`、`tests/test_sa_secret_string_no_dict_prewrap.py`。
- **設定試算表寫入目標／閘門**：`tests/test_settings_sheet_repository.py`、`tests/test_settings_sheet_title_gate.py`、`tests/test_v2_tables_settings_store.py`、`tests/test_v2_tables_settings_store_page.py`、`tests/test_v2_tables_contract_settings.py`、`tests/ui_v2/test_set_live_logic.py`、`tests/ui_v2/test_set_live_page.py`、`tests/_fake_settings_sheet.py`、`tests/ui_v2/test_mkt_settings_logic.py`／`_page.py`、`tests/ui_v2/test_hld_live_settings.py`。
- **唯讀保證**：`tests/test_policy_supplement_repository.py`（C4 無寫入函式、分頁不存在不建）、`tests/test_readonly_query_paths.py`（Tripwire 假 worksheet，任何寫入即炸）、`tests/test_weights_store_read_no_writes.py`、`tests/test_portfolio_perf_render_no_writes.py`、`tests/test_wf02_health_no_writes.py`、`tests/test_wf03_research_no_writes.py`、`tests/test_wf04_portfolio_no_writes.py`。
- **舊 UI 讀寫**：`tests/test_cloud_io.py`、`tests/test_policy_store.py`、`tests/test_policy_mixed_schema.py`、`tests/test_ledger_store.py`、`tests/test_ledger_snapshot_store.py`、`tests/test_migrate_v149_schema.py`、`tests/test_fix_and_shrink_v2.py`、`tests/test_tier_stale_and_sheet_preserve.py`、`tests/test_pool_repository.py`、`tests/test_nav_history_gs.py` 等。
- **ui_v2 隔離**：`tests/ui_v2/test_ui_v2_live_import_guard.py`、`tests/ui_v2/test_preview_entry.py`、`tests/ui_v2/test_preview_page.py`、`tests/test_services_purity_contract.py`、`tests/test_v2_tables_masking.py`。
- **未找到**：「`settings_sheet_repository` 不得呼叫 `client.create`／`client.copy`」的專門守衛；「`list_user_sheets` 只列合格 Sheet」的測試（因為沒有這個功能）；「OAuth scope 清單」的釘版測試（`git grep GOOGLE_OAUTH_SCOPES -- tests` 0 命中，實測）。

---

## 本組沒有查證的部分

- 沒有實跑任何測試（列出的測試數為 `grep -c` 計數）。
- 沒有對 Google 發任何請求；Google scope 語意（`spreadsheets` 全權、`include_granted_scopes` 併入行為）為依官方語意的推論。
- 部署端（Streamlit Cloud）各 app 的 secrets 實際指向哪本試算表：無法判定。
- G1 寫入盤點的字表未涵蓋形態（見 G1 末段）；G3 淨值 A 鏈深層呼叫未逐層追到底。
- 「ui_v2 單獨 app 內 `gsheet_tokens` 恆為空」為推論（ui_v2 無寫入該 key 的程式），未在執行期驗證。
