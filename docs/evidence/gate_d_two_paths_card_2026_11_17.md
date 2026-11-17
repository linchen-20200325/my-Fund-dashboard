# 🔍 Gate-D 兩條路徑裁示卡：選股池清單（路徑 A）vs 單檔基本資料查詢（路徑 B）（2026-11-17）

> **單組作者整理，未經獨立 QA；全稱句（「只有／沒有／全部／均否」）皆為單組讀碼／grep 結論，未經第二組驗證。**
> **不構成授權、不是客戶裁示、不改任何程式或測試。** 基準 main `4dec2788`（2026-11-17 `git fetch` 實查；使用前須重查 GitHub）。
> 證據符號：【碼】讀現行程式；【DEC】對照 `docs/DECISIONS.md`；【文】依既有 evidence／BACKLOG（本組未重驗）；【實跑】本組實際執行；【未驗】本組沒查。不寫行號，以「檔案::符號」定位。
> 本卡**不重寫** `docs/evidence/fund_search_mount_gate_card_2026_11_17.md`（Gate-M 掛載卡），只引用其第 8 節的 Gate-D 盤點；本卡把 Gate-D 拆成兩條路徑，並補上依賴矩陣。

## 0　結論（先講）

| 問題 | 單組結論 |
|---|---|
| 兩條路徑的差別 | **A 讀的是「使用者自己維護的選股池清單」（Google Sheet）；B 讀的是「使用者輸入一個 MoneyDJ 基金代碼」後的外部網站基本資料。兩者依賴的前提幾乎不重疊**：A 卡在 Sheet 讀取權限、`pool_not_cloud` 顯示語意、選股池代碼命名空間；B 卡在外部網路（NAS proxy）、BL-0551 TLS 揭露、入口擋 ISIN 形字串。【碼】 |
| 單組建議 | **B（單檔基本資料查詢）優先；A（選股池清單）維持暫緩**。理由：B 不需要 Sheet、不需要選股池命名空間裁示，且只需要一次「使用者輸入一個代碼」就能驗證端到端；A 仍被 `DEC-2026-11-14-08`（S2-T0 暫緩）與 `pool_not_cloud` 未裁語意擋住。**這是作者建議，非授權。** |
| 但 B 不是「現在就能做」 | 6a 只核欄位**位置**、資料值維持占位、不接線（`exp_wireframe_approval_draft…` U7）；B 的真實值接線**需要新 Gate**（本卡第 4 節）。且 B 會對外發請求，**BL-0551（TLS 驗證在 NAS proxy 模式停用）對 B 是實際生效的**，A 不涉及。【碼】【文】 |
| 與 44 EXP-6 的關係 | B 與 `44` 的 `EXP-6`「單檔基礎資料」內容**部分重疊**（基金全名／代碼／ccy／成立日／配息方式／費率）；`EXP-6` 在 🔍 尚屬待定（`DEC-2026-11-17-02` 不授權 EXP-6）。**B 是否算 EXP-6 的前置、替代或另一個功能，需設計者／客戶確認，本卡不自行定。** |
| 不需新 Gate 的下一步 | 見第 5 節（少，且皆有條件）。 |

## 1　兩條路徑的現況事實

| 項目 | 路徑 A：選股池清單 | 路徑 B：單檔 MoneyDJ 代碼查詢 |
|---|---|---|
| 入口函式【碼】 | `services/v2_tables/exp_universe.py::load_pool_codes` | `services/v2_tables/fund_keys.py::resolve_full_keys` → `services/v2_tables/exp_profile.py::build_profiles` |
| 資料來源【碼】 | 選股池 Google Sheet（`POOL_SHEET_ID` secret；`pool_repository.get_pool_store`） | 外部網站：MoneyDJ 基本資料頁、TDCC OpenAPI 清單、FundClear SmartFundAPI（三來源） |
| 回傳形狀【碼】 | `status` ∈ `STATUS_OK`／`STATUS_NOT_CLOUD`（`pool_not_cloud`）／`STATUS_FAILED`；`ok` 時才帶代碼清單 | `rows`／`cells`（逐欄 `status`∈ ok／not_ready／fetch_failed／inconsistent）／`declared`／`source_status`／`table_wide_failed` |
| 取用範圍【碼】 | **只取 `entry.code`**（其餘欄位結構上不回傳） | 欄位：`fund_name`、`ccy`、`inception_on`、`dividend_policy`、`mgmt_fee_rate_pct`（＋列層 `fetched_at`） |
| 快取與冷卻【碼】 | 只快取成功結果，TTL＝`shared.ttls.TTL_1HOUR`；失敗冷卻沿用 `infra.gspread_retry`（最長一種限流 1800 秒，須短於成功 TTL） | 三支 L1 各自有快取與失敗記憶（`DECLARED_CACHED_FUNCTIONS`）；MoneyDJ／FundClear 走 `infra.proxy.fetch_url` 的來源退避；TDCC 手動接 `infra.source_backoff` |
| 現行呼叫端【碼】 | 舊樹 `ui_v2/exp/source.py::load_live` 呼叫，且**恆傳 `oauth_client=None`**（取登入者 client 的函式住在舊樹 `ui/`，ui_v2 不得 import）；故本機 JSON store／未設定 `POOL_SHEET_ID` 時回 `pool_not_cloud` | 舊樹 `ui_v2/exp/source.py::_load_funds` 以 `fund_keys.resolve_full_keys` → `exp_profile.build_profiles` 取基本資料；`ui_v3` **尚無**呼叫端 |
| 無「只用 MoneyDJ」入口【碼】 | — | `build_profiles` 對每個 `ok` 的代碼**固定同一次呼叫三來源**；`fetchers` 注入參數要求**恰含 MoneyDJ／TDCC／FundClear 三鍵**，少一鍵即 `ValueError`。不存在「只打 MoneyDJ」的公開入口 |
| MoneyDJ 讀哪些欄位【碼】 | — | `declared_profile.fetch_moneydj_basic_fields` 只收四個標籤：**基金名稱、計價幣別、配息頻率、成立日期** |
| `mgmt_fee_rate_pct`【碼】 | — | **恆為 None**（「最高經理費」不冒充經理費率；`TEXT_MGMT_FEE`） |
| 成立日期檢核【碼】 | — | 只收 `YYYY/M/D` 類寫法；年份 `< 1900` 判 `INCEPTION_TOO_EARLY`、晚於台灣今天判 `INCEPTION_FUTURE`，皆不採用 |
| 配息方式【碼】 | — | 依 `docs/v2/49` §6.1 對照表（`DIVIDEND_FREQ_TO_POLICY`）：月配／季配／半年配／年配等 → `dist`；不配息／累積等 → `accum`；空白／「—」／不定期 → 不判定（None）；表外 → `not_ready` |
| 入口接受什麼字串【實跑】 | — | `resolve_full_keys` 對 `US0378331005`、`LU0123456789`（12 字元、ISIN 形）回 `ok=True`、`full_key` 原字串；對 MoneyDJ 網址（`…?a=ACTI71`）回 `ok=True`、`full_key=ACTI71`。**即：`PURE_CODE_PATTERN`（3–30 個大寫英數，可接 `-` 後綴）會把 ISIN 形字串當作基金代碼收下，不會擋。** |
| 對照表來源【碼】 | — | `fund_keys` 的 `mapping` 預設讀內建表／`fund_code_mapping.csv`（本地，非網路）；命中別名時 `full_key` 會被換成 `public_code`（涉 R-ID-2／3 語意） |

## 2　依賴矩陣（只有「實際依賴該項」的功能，才受該項 Gate 限制）

「是」＝該路徑在真實資料接線時**實際依賴**該項，需先有對應 Gate／裁示；「否」＝不依賴（或前提是不把該欄位顯示給使用者）。

| 依賴項 | 路徑 A（選股池清單） | 路徑 B（單檔查詢） | 說明（含前提） |
|---|---|---|---|
| ISIN 對照來源 | 否 | 否，**但入口須自行擋 ISIN 形字串** | 目前**沒有已核准的 ISIN 對照來源**（`DEC-2026-11-01-02` G-E1【DEC】）；`fund_keys` 不擋 ISIN 形（第 1 節【實跑】），B 若不在入口擋，會把 ISIN 形字串拿去打 MoneyDJ 並得到「查不到」，易被誤讀成「基金不存在」。擋的位置（adapter 或 view model）屬設計選擇，本卡不定。 |
| Provider 名稱（R-NAV-4） | 否 | 否 | 兩者皆不顯示來源名。R-NAV-4 在 main 的狀態仍為 Pending；`DEC-2026-11-17-06`（核准 NAV 域 `source_tier` 契約文字 T-NAV4）目前**只登記在未合併分支 `origin/ccr-c565878d-9vggvn`（`afab8e2c`）**，不在 main `4dec2788`。【DEC】【未驗】 |
| NAV 來源時間（R-NAV-3） | 否 | 否，**前提：不顯示 `fetched_at`** | R-NAV-3 暫緩（`DEC-2026-11-14-07`）。`build_profiles` 的列層帶 `fetched_at`，B 的畫面**不得**顯示它；TDCC 的 `fetched_at` 恆 None、改記 `observed_at`（不可考）。 |
| `ccy_source`（R-NAV-6） | 否 | 否，**前提：不顯示 ccy 與其來源** | R-NAV-6 仍 Pending。`ccy` 由三來源合成（`PARTIAL_FAILURE_POLICY="accept"`，2026-10-14 客戶裁示）；B 若要顯示 ccy，需先裁 R-NAV-6，故本卡切片**不顯示 ccy**。 |
| 歸一化公式 | 否 | 否 | 兩者皆不算報酬／歸一化。 |
| FX | 否 | 否 | 兩者皆不換匯。 |
| R-ID-1（基金身份契約，已核准） | 否 | 否 | 已核准契約文字（`DEC-2026-11-13-06`），但**其射程不含 EXP 選股池代碼與使用者輸入代碼**（命名空間另案）；兩者皆不得宣稱「已確認基金身份」。 |
| R-ID-2／R-ID-3（full_key／ok 的身份語意） | 否 | **是**（內部 `full_key`／`ok`） | B 內部以 `full_key` 取數、以 `ok` 判斷是否取數；這兩個欄位的身份語意仍 Pending。**B 的畫面不得把 `ok=True` 說成「基金存在／已確認」**。 |
| EXP 選股池代碼命名空間 | **是** | 否 | 選股池代碼與 MoneyDJ 代碼是否同一套命名空間，客戶裁示另案（`DEC-2026-11-13-06`、`DEC-2026-11-17-04` 皆明列不授權）。 |
| `pool_not_cloud` 顯示語意 | **是** | 否 | 未設定 vs 憑證格式錯誤是否區分、正式字樣，三個顯示候選客戶尚未選定（`DEC-2026-11-14-08`）。 |
| BL-0551 TLS 驗證停用 | 否 | **是（MoneyDJ、FundClear）** | `infra/proxy.py::fetch_url` 在有 Proxy 設定時 `verify=False`；`declared_profile` 的 MoneyDJ 與 FundClear 取數經 `fetch_url_with_retry` → `fetch_url`，故實際落在該風險內。**TDCC 不同**：`sources._tdcc_get` 用 `urllib.request.urlopen`，由 `infra.proxy.install_global_urllib_proxy` 的全域 opener 導向 NAS，**程式碼未顯式關閉憑證驗證**（執行期行為【未驗】）。降級直連時為 `verify=True`。 |
| Sheet 讀取權限 | **是** | 否 | A 需服務帳戶／登入者對選股池 Sheet 有讀取權；`ui_v2` 路徑恆傳 `oauth_client=None`。 |
| NAS proxy secrets（`PROXY_URL`） | 否 | **是** | B 的三來源取數經 `infra.proxy`（`st.secrets["PROXY_URL"]` 或 `[proxy]`）；無 proxy 設定時降級直連，而 `infra/proxy.py` 自述 Streamlit Cloud IP 可能被 MoneyDJ 封鎖。MoneyDJ 在目標部署端是否可達【未驗】。 |

## 3　其他事實

| 事實 | 出處 | 對本卡的含意 |
|---|---|---|
| 6a 只核欄位**位置**；U7「所有資料值維持占位，不接線」 | 【文】`docs/evidence/exp_wireframe_approval_draft_and_slice_request_2026_11_14.md` U7／U8 | B 的真實值接線**不在既有授權內**，需新 Gate（第 4 節）。 |
| B 與 44 `EXP-6` 內容部分重疊 | 【碼】`docs/v2/44_fund_ui_ssot.md` 塊 EXP-6（基金全名、`fund_code`、`ccy`、成立日、配息方式、費率；整檔查無→`來源缺`「查無此 `fund_code`」） | EXP-6 的「查無此 `fund_code`」文案與本卡「不顯示『查無基金』『不存在』」衝突點**需設計者／客戶確認**；`DEC-2026-11-17-02` 不授權 EXP-3／4／5／6。 |
| `DEC-2026-11-14-08` 暫緩 S2-T0；不掛 🔍、不接 Google Sheet | 【DEC】main | 路徑 A 被擋於此；B 不讀 Sheet，但「不掛 🔍 頁」仍適用，故 B 的方案不含掛 🔍 頁。 |
| `DEC-2026-11-17-02`／`-04` 的授權範圍不含真實資料 | 【DEC】`-02` 在 main；`-04`（內部唯讀 adapter 切片，只允許明確注入的測試輸入、禁真實網路／Sheet）**僅登記在未合併分支 `afab8e2c`** | 兩者都不授權 B 的真實取數。 |
| 舊樹 `ui_v2` 已有 B 同型實作 | 【碼】`ui_v2/exp/source.py::_load_funds` | 說明 L2 資料層可用；`ui_v3` 與舊樹不得互 import，需新 adapter。 |

## 4　裁示卡（只問一題）

> **問**：是否同意為「**使用者輸入一個 MoneyDJ 基金代碼**」這一功能，先做「**接真實資料、獨立入口、不入導覽**」的切片？
> （本問題只涉路徑 B；路徑 A 維持暫緩，不在本卡問。）

### 4-A　方案表（方案編號為本卡自訂，避免與路徑 A／B 混淆；括號內為派工單原稱）

| 方案 | 內容 | 優點 | 缺點 | 風險 | AI 推薦 |
|---|---|---|---|---|---|
| **方案 1（原稱 A）獨立入口接真實值** | 新增獨立 Streamlit 入口（不掛 `registry`／`app_preview` 導覽）；使用者輸入一個代碼，顯示該檔 MoneyDJ 基本資料四欄（名稱、配息方式、成立日、費率欄固定缺值）；其餘全不顯示 | 範圍小、與 🌍 Preview／🔍 FAKE 互不干擾；revert 一個 PR 即回滾；可先驗證 NAS proxy 與 MoneyDJ 可達性 | 要客戶接受 BL-0551 揭露與 proxy 先決事實；多一個入口要維護；與 EXP-6 的關係未定 | BL-0551（MoneyDJ／FundClear 在 proxy 模式不驗憑證）；MoneyDJ 在部署端可能被封；ISIN 形字串被誤送 | **推薦（前提：客戶接受 BL-0551 揭露、且 proxy 先決事實屬實）** |
| 方案 2（原稱 B）同方案 1 並掛 Preview 導覽 | 方案 1 ＋ 改 `registry`／`app_preview` 掛入 Preview 導覽 | 在 Shell 內可見 | 直接牴觸 `app_preview`「不顯示 fake／未核准資料」原則的延伸；需 Gate-M 同類改動（見掛載卡 A1～A6）；暫行字樣更顯眼 | 高於方案 1：誤讀為正式功能、`registered` 語意稀釋 | **不推薦** |
| 方案 3（原稱 C）維持暫緩 | 不接真實資料；等 S2-T0 解凍與 R-NAV／R-ID-2／3 裁示 | 零風險、零改動 | 無進度；B 的先決事實（proxy／可達性）仍未驗 | 無新增 | 客戶若要**先評估 BL-0551**（例如先決定是否改 proxy 的 TLS 設定）則選此 |

### 4-B　方案 1 的程式範圍與不碰清單

| 類別 | 內容 |
|---|---|
| 新增（單組估計） | `ui_v3/adapters/`：一個 adapter（呼叫 `fund_keys.resolve_full_keys` → `exp_profile.build_profiles`；入口擋 ISIN 形字串）；`ui_v3/viewmodels/`：view model 與暫行字樣；`ui_v3/pages/`：renderer；獨立入口檔；對應測試與守衛。位置與檔名屬實作時再定。 |
| 不改 | `ui_v3/shell/registry.py`、`ui_v3/app_preview.py`、`services/**`、`repositories/**`、Schema、frozen 44、公式、FX、Old UI／`ui_v2`。 |
| 畫面**不顯示** | `ccy`（幣別）、`fetched_at`（取得時間）、來源名（MoneyDJ／TDCC／FundClear 或 `source_tier`）、淨值、報酬、績效；不出現「查無基金」「不存在」等字樣（取數失敗不得推論為基金不存在，延續 `DEC-2026-11-17-03` G-2 的方向〔該 DEC 在未合併分支〕）。 |
| 畫面**可顯示（候選）** | 基金名稱、配息方式（`dist`／`accum`）、成立日、經理費率欄（恆缺值）；以及「輸入代碼」原值。是否顯示、怎麼措辭，皆屬 `PendingWording`，客戶未核准。 |

### 4-C　不授權清單（本卡即使被採納也不授權）

| 項 |
|---|
| 路徑 A（選股池清單）任何真實資料接線；讀真實 Google Sheet；改 `pool_not_cloud` 語意或字樣 |
| 掛 🔍 頁、改 registry／`app_preview`／正式導覽；Preview 導覽收錄本入口 |
| ISIN 解析、ISIN 對照來源、把選股池代碼視為已確認基金身份 |
| D2 Pending 欄位的值（R-NAV-3／6、R-ID-2／3、R-PERF-*）；`ccy`、淨值、報酬的顯示 |
| 修改 L1／L2 正式行為、公式、Schema、FX、frozen 44；變更 BL-0551 範圍內任何 `verify` 設定 |
| 解除 BL-0545；宣稱 🔍 或單檔查詢「功能完成」；Cloud／真機驗收 |

### 4-D　字樣與缺值規則（`PendingWording`）

| 項 | 規則 |
|---|---|
| 新字樣 | 一律 `PendingWording`（暫行、未核准）；不進 `shared/ui_semantics/rules.py`；不自行定稿。 |
| 配息方式畫面詞 | 內部值為 `dist`／`accum`（`docs/v2/49` §6.1）；畫面用語**未核准**，不自行定稿。 |
| 缺值符號 | 正式模式既有核准字樣為 `◇ 資料未備`；離線 FAKE Preview 採 `⬜ 資料未備`（`DEC-2026-11-17-03` G-3，在未合併分支）。**獨立入口接真實值屬正式還是示範模式、該用 `◇` 或 `⬜`，本卡不自行定，列為待設計者／客戶確認。** |
| 取數失敗 | 以「這次取數失敗」類措辭表達；不得寫「查無基金」「基金不存在」。 |

### 4-E　品質門檻與回滾

| 項 | 內容 |
|---|---|
| 獨立 QA | 涉 identity 邊界與 data semantics → 至少 1 組真正獨立 QA（`DEC-2026-10-16-05` 分級）。 |
| CI | 全綠（Fast／Schema／Slow／Visual；含 browser 層）；Cloud／真機另列 NOT VERIFIED，不得宣稱已驗。 |
| 回滾 | `git revert` 該 PR；無資料回滾（只讀、不寫任何持久層）。 |

### 4-F　需客戶或合法持有人確認的資料存取與部署權限

| 項 | 誰確認 | 現況 |
|---|---|---|
| MoneyDJ 在目標部署端的可達性（含是否被封 IP） | 客戶／部署端持有人 | 【未驗】 |
| `PROXY_URL` secret 是否已設定、NAS proxy 是否在線 | 客戶／NAS 持有人 | 【未驗】（本組不探查 secrets） |
| Streamlit Cloud 部署端是否允許新增獨立入口 | 客戶 | 【未驗】 |
| 接受 BL-0551 的揭露（proxy 模式不驗 MoneyDJ／FundClear 憑證）並同意不在本切片處理 | 客戶 | 待裁示 |
| Sheet 服務帳戶讀取權限（**僅路徑 A**，方案 1 不需要） | 客戶 | 不適用方案 1 |

### 4-G　先決事實（全部 NOT VERIFIED）

| 先決事實 | 狀態 |
|---|---|
| NAS proxy 在線且可轉發 MoneyDJ／TDCC／FundClear | NOT VERIFIED |
| MoneyDJ 基本資料頁格式目前仍符合 `declared_profile` 的身分判準（恰一張含「基金名稱」的表） | NOT VERIFIED（`probe/moneydj-basic-*` 為歷史探測，本組未重跑） |
| 部署端 `requests` 於 proxy 模式的 TLS 行為與 `infra/proxy.py` 註解一致 | NOT VERIFIED（僅讀碼） |
| 使用者輸入 ISIN 形字串時入口能擋、且措辭不暗示基金不存在 | 尚未設計，無從驗 |

## 5　現在可做、不需新 Gate 的工作（若有）

| 工作 | 屬哪條路徑 | 現況與條件 |
|---|---|---|
| S2-T0 內部唯讀 adapter／ViewModel 切片（只用明確注入的測試輸入；驗既有選股池 L2 回傳形狀、四狀態區分、fail-closed、重用 S0 計數） | 路徑 A 的**內部測試切片**（不接真資料、不可見） | 由 `DEC-2026-11-17-04` 授權；但該 DEC **目前只在未合併分支 `afab8e2c`**，且其文字自述「須先完成新 DEC 與治理查核再施工」。→ **在該 DEC 合併並完成治理查核前，不應視為可動工。**【DEC】【未驗】 |
| 🔍 FAKE Preview 視覺量測（對比度等） | 兩條路徑皆無關（離線 FAKE） | 屬 `DEC-2026-11-17-02`（main）授權的 `poc/fund_search_fixture_preview/` 範圍；視覺 3:1 要求來自 `DEC-2026-11-17-03`（未合併分支）。僅在該 poc 範圍內，不接資料。 |
| 路徑 B 的 view model 純函式（輸入：注入的假 `build_profiles` 結果；含 ISIN 形字串擋門測試） | 路徑 B 內部測試切片 | **目前沒有任何 DEC 授權**（`-04` 只涵蓋選股池 adapter 的措辭）；若要做，需客戶明示或併入方案 1。不視為「不需新 Gate」。 |
| 其餘 | — | 本組查無其他不需新 Gate 且有使用者可見成果的工作。（單組結論，全稱句未驗） |

## 6　抽查核對紀錄（對現行程式／DEC 的 9 項，與派工單不符處已修正）

| # | 核對項 | 結果 |
|---|---|---|
| 1 | `load_pool_codes` 的 `STATUS_OK`／`STATUS_NOT_CLOUD`／`STATUS_FAILED`、只取 `entry.code`、`TTL_1HOUR`、`infra.gspread_retry` 冷卻 | 相符【碼】 |
| 2 | `ui_v2/exp/source.py::load_live` 恆傳 `oauth_client=None` | 相符【碼】（註解自述原因：登入者 client 函式在舊樹 `ui/`） |
| 3 | `build_profiles` 固定同呼叫三來源、無只用 MoneyDJ 入口 | 相符【碼】：`_check_fetchers` 要求恰三鍵 |
| 4 | `fetch_moneydj_basic_fields` 只讀四欄；`mgmt_fee_rate_pct` 恆 None；成立日 1900～今日 | 相符【碼】 |
| 5 | `dividend_policy` 依 `docs/v2/49` §6.1 | 相符【碼】；補：值為 `dist`／`accum`／None |
| 6 | `PURE_CODE_PATTERN` 會把 12 字元 ISIN 形字串收為代碼 | 相符【實跑】（`US0378331005`、`LU0123456789` 皆 `ok=True`）。**補充派工單未提**：`resolve_full_keys` 也接受 MoneyDJ 網址並抽出 `a=` 代碼。 |
| 7 | **派工單原稱「MoneyDJ／FundClear／TDCC 外部請求走 NAS proxy，停用 TLS 驗證」** | **部分不符，已修正**：MoneyDJ、FundClear 經 `fetch_url_with_retry`→`infra.proxy.fetch_url`，proxy 模式 `verify=False`（相符）；**TDCC 走 `sources._tdcc_get` 的 `urllib.request.urlopen`**，proxy 由全域 opener 套用，程式碼未顯式關閉驗證。第 2 節 BL-0551 列已據此分列。 |
| 8 | **派工單原稱 `DEC-2026-11-17-06` 已核 `source_tier` 文字〔若已落盤〕；`-04` 授權 S2-T0 內部 adapter** | **在 main 查無**：`DEC-2026-11-17-03`～`-06` 只存在於未合併分支 `origin/ccr-c565878d-9vggvn`（`afab8e2c`，一個 commit，登記 DEC＋PROJECT_RULES 第 16 節）。本卡引用處皆已標註「未合併分支」，R-NAV-4 在 main 仍 Pending。 |
| 9 | 6a／U7「所有資料值維持占位，不接線」；`DEC-2026-11-14-08`、`-17-02` 範圍 | 相符【DEC】【文】 |
| 10 | 路徑更正：`exp_universe`／`exp_profile`／`exp_nav`／`fund_keys` 在 `services/v2_tables/`，不在 `services/v2_domain/` | 相符【碼】（`v2_domain` 只有 `rule_filter` 等純計算；`ui_v3` adapters 守衛的 `LOWER_LAYER_PREFIXES` 同時開放兩者） |

## 7　NOT VERIFIED

1. 本卡全部內容為單組作者整理，**未經獨立 QA**；全稱句（「不依賴」「均否」「沒有其他」）未經第二組驗證。
2. 第 2 節「均否」係就「畫面不顯示該欄位」的前提成立；若日後顯示 ccy／`fetched_at`／來源名，對應 R-NAV-6／R-NAV-3／R-NAV-4 立即變「是」。
3. 未執行任何對外請求；未探查 secrets；MoneyDJ／FundClear／TDCC 可達性、NAS proxy 狀態、TLS 實際行為皆未驗。
4. `DEC-2026-11-17-03`～`-06` 在未合併分支，其內容與後續合併狀態未驗；使用前須重查。
5. 單組 grep／讀碼，非窮舉；動態組出的呼叫、未列檔案可能漏看。
6. Cloud／真機／瀏覽器像素未驗；CI 結果未查。
7. 本卡所有「推薦」為作者建議，**非授權、非客戶裁示**；登記不構成動工授權。
