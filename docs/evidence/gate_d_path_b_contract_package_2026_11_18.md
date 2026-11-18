# 🔍 Gate-D 路徑 B（MoneyDJ 單檔基本資料查詢）契約研究與內部設計包（草案，2026-11-18）

> **單組作者，尚待非作者獨立稽核（資料語意／身分級）。** 全稱句（「只有／沒有／全部／均否」）皆為單組讀碼或字面搜尋結論，未經第二組驗證；非窮舉。
> **不構成授權聲明、不是客戶裁示、不新增任何程式或測試。** 本檔只新增這一份文件。
> 基準：`origin/main` `9e714861`（2026-11-18 於工作樹實查；使用前須重查）。證據寫法：`檔案::符號`，不寫行號（行號會漂移）。
> 分段標記：**FACT**＝讀現行檔案或本機離線實跑可直接核對（附 `檔:符號`，查不到標 NOT VERIFIED）；**INFERENCE**＝由 FACT 推得、可被推翻；**RECOMMENDATION**＝作者建議，非授權。

## 授權範圍（客戶限縮授權，經對話提示語轉達，待核；repo 無逐字存檔，QA 無法核對）

| 項 | 內容（執行組讀法，可被推翻） |
|---|---|
| 優先序 | Gate-D 路徑 B（使用者輸入一個 MoneyDJ 基金代碼）優先；路徑 A（選股池清單）暫緩 |
| 本批授權 | 契約研究、內部 adapter／ViewModel 的設計、注入測試的施工準備。**施工準備＝設計文件＋測試計畫＋契約包**；本批不新增 production 程式碼或測試檔 |
| 本批不授權 | 真實取數（網路、Sheet、secrets）；修改 frozen 44、Schema、公式、FX、DG2、ISIN resolver；掛 🔍 頁、改 registry／`app_preview`／導覽；修改 L1／L2 正式行為 |
| 真實取數的前置 | 須等 A 線安全 Gate（BL-0551 TLS 揭露）通過，**且**客戶正式核准。FACT：`docs/BACKLOG.md` 的 BL-0551 現況為「open（只讀風險評估；登記不構成動工授權）」；「A 線安全 Gate 通過」的具體條件在 repo 內查無定義（單組字面搜尋，NOT VERIFIED），故本檔不替它定義 |

## 0　結論（先講）

| # | 結論 | 類別 |
|---|---|---|
| 1 | **路徑 B 的五欄（輸入代碼、基金名稱、配息方式、成立日期、經理費率）目前沒有任何一欄有「已核准的 D2 契約文字」。** 已核准的 5 個欄位（R-ID-1、R-NAV-1、R-NAV-2、R-NAV-4、R-NAV-5）與這五欄皆不重疊，且 `T-ID1`（R-ID-1）只限 Sheet「基金代號」欄，故**未涵蓋**使用者輸入框（推論，可被推翻；`DEC-2026-11-13-06` (2) 另明文排除的是 EXP 選股池代碼）。接線前需先有路徑 B 專屬的最小契約文字（本檔第 8 節給草案） | FACT＋RECOMMENDATION |
| 2 | **`build_profiles` 無法做到 MoneyDJ-only**：每個通過金鑰解析的代碼都會固定呼叫 MoneyDJ、TDCC、FundClear 三支 L1；`fetchers` 注入要求恰含三鍵。名稱／成立日／配息方式三格的**值**只讀 MoneyDJ 結果，但**網路行為是三來源**。任何對外揭露不得寫「只查 MoneyDJ」 | FACT |
| 3 | **經理費率在 L2 是寫死的缺值**（`build_profiles` 對 `mgmt_fee_rate_pct` 恆回「來源未提供」），不是「偶爾缺」。路徑 B 的費率欄在現行 L2 下永遠不會有值；若 adapter 看到非缺值，應 fail-closed | FACT＋RECOMMENDATION |
| 4 | **入口須在 adapter 先攔、不呼叫 loader**：現行 `fund_keys.resolve_full_keys` 會收下 ISIN 形字串與 MoneyDJ 網址（本機離線實跑已核）。本檔給出有先後次序的攔截規則（第 4 節）與「結構上不回顯」的輸入保留設計 | FACT＋RECOMMENDATION |
| 5 | **狀態集 6 種互斥（含未知＝契約不符例外）**：尚未查詢／入口攔截／來源失敗／頁面無法確認／有結果（欄位級：有值／缺值／分歧）／未知（fail-closed）。任何一種都不得被說成「基金不存在」（延續 `DEC-2026-11-13-06` (6) 與 `DEC-2026-11-17-03` G-2 的方向） | RECOMMENDATION |
| 6 | **現行 L2 無法區分「頁面標籤自相矛盾」與「單純缺值」**（兩者都是 `not_ready`，只差自由文字 `reason`）；adapter 不得解析文字，所以欄位級「分歧」在目前 L2 形狀下**無法被機器辨識**，只能保留狀態位、誠實記為限制 | FACT＋INFERENCE |
| 7 | 需客戶裁示的問題見第 8.2 節（Q0～Q11），衝突彙整見文末〈需客戶裁示的衝突〉 | — |

---

## 1　逐項契約現況（對應交辦第 1 項）

### 1.1　總表

| 欄 | 內容來源（現行實作） | 已核准契約？ | 缺值語意 | 單位／型別 |
|---|---|---|---|---|
| 輸入代碼 | 使用者輸入原值；不來自任何資料源 | **無**。`T-ID1`（R-ID-1）原文只限 Google Sheet「基金代號」欄，故未涵蓋使用者查詢框（**INFERENCE**）；`DEC-2026-11-13-06` (2)(4) 另明文排除 EXP 選股池代碼；使用者在查詢框輸入的代碼未見任何核准契約 | 不適用（輸入一定存在；空白者在入口被攔） | 字串 |
| 基金名稱（K15） | MoneyDJ 基本資料頁「基金名稱」標籤；須通過 MoneyDJ 身分判準 | **無**。D2 候選檔 K15：Pending（歸 profile 契約，不屬現行取數鍵）、待裁示；17 列 R-* 待審表查無對應列 | 標籤缺、空白、佔位字 → 缺值（⬜）；頁面不符身分判準 → 整格不採用 | 字串，原字面 |
| 配息方式 | MoneyDJ「配息頻率」標籤，經 `docs/v2/49` §6.1 對照表轉為 `accum`／`dist` | **無顯示用契約**。D2 候選檔僅在 Returns 域第 14 列把 `dividend_policy` 當「配息閘門輸入」，狀態 Optional／Pending，DEC 編號標 NOT VERIFIED；對照表本身為「客戶 2026-09-26 定案」 | 標籤缺、表外寫法、空白／「—」／「不定期」→ 缺值（不判定）。**None 不等於「不配息」** | 列舉 `accum`／`dist` |
| 成立日期 | MoneyDJ「成立日期」標籤，經 `_check_inception` 正規化 | **無**（D2 候選檔字面查無 `inception` 或「成立日」） | 字樣認不出、日期不存在、年份早於 1900、晚於台灣今天 → 缺值（皆不採用） | ISO 日期字串 `YYYY-MM-DD`，無時區 |
| 經理費率 | **無來源**：L2 寫死缺值 | **無**（D2 候選檔字面查無 `mgmt_fee`、「經理費」）；44 §4.6 `fund_profile` 有欄位定義（可空：是） | 恆缺值；「最高經理費」不得冒充 | 浮點，百分點／年（僅 44 定義；現無值） |

### 1.2　證據（FACT）

| # | 事實 | 證據 |
|---|---|---|
| F1 | K15「基金名稱」：Pending、待裁示、歸 profile 契約，不屬現行取數鍵；缺值處理寫「該格資料未備；不影響取數鍵」 | `docs/evidence/d2_contract_candidates_returns_identity_holdings_2026_11_08.md`::K15 列 |
| F2 | D2 已核准契約文字欄位數為 5：R-ID-1、R-NAV-1、R-NAV-2、R-NAV-4、R-NAV-5；其餘 12 列仍 Pending（含 R-ID-2、R-ID-3、R-NAV-3 暫緩、R-NAV-6、R-PERF-1～8）。核准的是契約文字，不是接線授權 | `docs/DECISIONS.md`::`DEC-2026-11-17-06`「D2 核准欄位狀態」列 |
| F3 | `T-ID1` 限「Google Sheet 持倉『基金代號』欄」，命名空間固定 MoneyDJ，**只限該欄**；不是 ISIN；「原值保留（僅去前後空白）；不轉大小寫」；已知落差 D2-A＝B 標示尚未實作 | `docs/evidence/d2_min_approval_pack_r_id_1_r_nav_1_2026_11_13.md`::`T-ID1`；`DEC-2026-11-13-06` 裁示 (2)(4) |
| F4 | `fund_profile` 表欄：`fund_code`／`fund_name`／`ccy`／`inception_on`／`dividend_policy`（`accum`／`dist`）／`mgmt_fee_rate_pct`（可空：是，百分點／年）／`fetched_at`；其餘欄「可空：否」；2026-10-13 客戶裁示「缺欄照列」與「可空：否」相撞，正式模式以裁示為準 | `docs/v2/44_fund_ui_ssot.md`::§4.6 表 `fund_profile` |
| F5 | MoneyDJ L1 只保留四個標籤：基金名稱、計價幣別、配息頻率、成立日期；「最高經理費」不讀、不存 | `repositories/fund/declared_profile.py`::`MONEYDJ_LABELS` |
| F6 | L2 組表時對經理費率恆寫缺值：`mgmt_fee_rate_pct` 欄以 `_cell(reason=TEXT_MGMT_FEE)` 建立，不讀任何 L1 欄位；文字為「來源未提供經理費率（不以『最高經理費』代替）」 | `services/v2_tables/exp_profile.py`::`build_profiles`、`TEXT_MGMT_FEE` |
| F7 | 配息頻率對照：月配／季配／半年配／年配／雙月配／月收等 → `dist`；不配息／無配息／累積／累積型 → `accum`；空白、「—」、「不定期」→ None；比對前只去頭尾空白、整欄精確比對；表外 → 缺值。對照表左欄的寫法「是推測的、沒有實測過」（`exp_profile.py` 註解轉述 `docs/v2/49` 原文） | `services/v2_tables/exp_profile.py`::`DIVIDEND_FREQ_TO_POLICY`、`_dividend_cell`；`docs/v2/49_data_integration_plan.md`::〈配息頻率對照表（客戶 2026-09-26 定案）〉 |
| F8 | 成立日期：分隔符 `/` 或 `-`；年 4 位、月日 1–2 位 ASCII 數字；`MIN_INCEPTION_YEAR=1900`；不得晚於台灣今天（`taiwan_today`，可注入 `now`）；民國年、中文年月日一律不採用 | `services/v2_tables/exp_profile.py`::`_check_inception`、`parse_inception`、`taiwan_today` |
| F9 | MoneyDJ 身分判準：以請求的代碼取頁、HTTP 200、恰一張含「基金名稱」的表且名稱非空；`binding` 五項型別嚴格檢查，不符則名稱／成立日期／配息方式整組不採用 | `services/v2_tables/exp_profile.py`::`_bound`、`_mdj_gate`；`repositories/fund/declared_profile.py`::`MONEYDJ_BINDING_METHOD` |
| F10 | `DEC-2026-11-13-06` (6)：New UI2 不顯示「查無基金」「不存在」；依證據分 `◇ 資料未備`／`⛔ 取數失敗`／`⬜ 無法判定`；frozen 44 `EXP-6` 的「查無此 fund_code」**尚未處置**，`EXP-6` 保留〔待定／來源契約未確認〕 | `docs/DECISIONS.md`::`DEC-2026-11-13-06` 決策內容摘要 (6) |

### 1.3　對上游卡片（`gate_d_two_paths_card_2026_11_17.md` §4-B2）的核對與更正

| 項 | 卡片原述 | 本組核對 |
|---|---|---|
| 配息方式 | 「D2 候選表查無專屬列（字面搜尋，未驗）」 | **部分需更正**：`dividend_policy` 並非完全不在 D2 候選檔——它出現在 Returns 域第 14 列（配息閘門輸入，Optional／Pending）。**但那是「報酬計算用的判斷輸入」，不是路徑 B 的顯示欄契約**，故「路徑 B 的配息方式沒有已核准的顯示契約」仍成立 |
| 名稱／成立日／費率 | 同上 | 名稱＝K15（Pending）；成立日、費率＝本組字面搜尋查無（仍為單組結論） |
| 費率「恆為空」 | 【碼】 | 本組核對成立（F6）；補充：**不是 L1 沒讀到，而是 L2 根本不讀**，故即使 MoneyDJ 頁面有經理費欄位，現行鏈也不會出值 |

### 1.4　經理費率恆為 None 的影響（INFERENCE，可被推翻）

1. **畫面上的費率欄在現行 L2 下永遠是缺值格**。使用者會把永遠缺值讀成「這檔暫時沒資料」；實際是「本系統沒有這個來源」。兩者在資料語意上不同（暫時缺 vs 設計上無來源）。
2. L2 把它與其他缺值同樣標成 `not_ready`，adapter 若不加註，兩種缺值在 view model 層會混在一起。**RECOMMENDATION**：view model 對費率欄加一個結構上固定的標記（例如「契約上目前無來源」），讓正式字樣日後可以區分；字樣本身待客戶核准。
3. **若 L2 日後開始回非缺值**（例如有人把「最高經理費」接上），那是語意變更（違反客戶「不以最高經理費代替」裁示，見 `exp_profile.py` 檔頭〈客戶裁示〉），且新來源屬 Stop／Decision Gate，必須先有契約。**RECOMMENDATION**：adapter 在費率欄看到非缺值時 raise 契約錯誤（fail-closed），而不是照顯示。
4. 費率沒有任何 D2 列、也沒有核准契約；任何新來源都屬 Stop／Decision Gate（新來源、正式公式或投資語意）。
5. 不得以 0、空字串或「無費用」呈現缺值（`CLAUDE.md` §1；44 `EXP-6` 判準：缺值顯示 `⬜` 而不是 0）。

---

## 2　R-ID-2／R-ID-3 的「最小必要內部取數鍵語意」（對應交辦第 2 項）

### 2.1　FACT：現行鏈如何使用鍵

| 事實 | 證據 |
|---|---|
| `resolve_full_keys` 逐檔輸出 `ok`（R-ID-3）與 `full_key`（R-ID-2）；`ok` 只代表「這個字串通過決定性對照鏈、格式合格」，**不代表基金存在** | `services/v2_tables/fund_keys.py`::`resolve_full_keys`、`_resolve_one` |
| `full_key` ＝ 去空白、轉大寫後的代碼；若命中別名表，`full_key` 被換成別名表的 `public_code`（例：輸入 `ACTI171` → `full_key` `ACTI71`） | 同上；內建別名表 `repositories/fund/sources.py::_DEFAULT_MAPPING` |
| `mapping=None` 時讀 `fund_code_mapping.csv`（相對於當下工作目錄；本地檔、非網路）；2026-11-18 於本工作樹 repo 根目錄查無此檔，故退回內建表 | `repositories/fund/sources.py::load_fund_code_mapping`；本機 `ls` 實查 |
| 注入 `mapping={}`（空表）時不呼叫 L1 載表、`mapping_source` 記為 `injected`，且**不套用任何別名** | `fund_keys.py`::`_check_injected_mapping`、`resolve_full_keys` |
| 取頁網址只由 `full_key` 組成：固定兩個 host（`tcbbankfund.moneydj.com`、`www.moneydj.com`）、固定路徑 `yp011000`／`yp011001`、`?a={代碼}`；`fund_keys` 只從網址輸入取 `a=` 的值，**host 與 path 一概丟棄** | `repositories/fund/declared_profile.py`::`_moneydj_urls`、`MONEYDJ_HOSTS`；`fund_keys.py` 檔頭 |
| `build_profiles` 以 `key_results[].input`（呼叫端原樣傳入的字串）當 `fund_code` 與 `cells` 的鍵，**不另行去空白或轉大寫** | `exp_profile.py`::`build_profiles` |
| `ok` 為假的代碼不取數：各欄 `not_ready`、`source_status` 為空 dict | 同上 |

### 2.2　RECOMMENDATION：路徑 B 的最小鍵語意

| 項 | 建議 | 理由 |
|---|---|---|
| 需要的鍵 | **只需要一個字串：MoneyDJ 基金代碼（`a=` 參數值）**。即使用者輸入去頭尾空白後的字串；內部 `full_key`＝其大寫形 | 取頁網址只吃這一個值（2.1） |
| 不需要的鍵 | ISIN、`policy_id`、`holding_id`、EXP 選股池代碼命名空間、`portal`（恆空）、`page_type`、別名 `public_code` | 路徑 B 不讀 Sheet，也不碰 ISIN resolver |
| 別名表 | **關閉**：由組裝端以 `mapping={}` 呼叫 `resolve_full_keys` | 避免「輸入 A、畫面顯示 B 的資料」：別名命中時使用者看到的是另一個代碼的頁面，而 R-ID-2 的身分語意仍 Pending（D2-C＝B：別名表不升格、只收追溯）。代價：平台碼（如 `ACTI171`）會被原樣拿去查頁，多半得到「頁面無法確認」，這是誠實的結果 |
| `ok` 的語意 | 內部旗標：「格式通過、可以嘗試取數」。**不得**在畫面說成「基金存在／已確認」 | 與卡片第 2 節一致（R-ID-2／3 為「是」且身分語意仍 Pending） |
| `full_key` 的語意 | 內部取數鍵，不顯示；不寫入任何持久層 | 避免它被誤當成已核准的身分 |
| 後綴碼（`ACDD01-EQTAL005` 形） | 入口**不額外攔截**，視為不透明字串、不剝除後綴、不宣稱「同一檔」；多半會得到「頁面無法確認」（NOT VERIFIED：MoneyDJ 對後綴碼的實際回應未探測） | S7（`full_key` 可否帶後綴）仍未裁，路徑 B 不替它下結論；攔截會把可能合法的輸入擋掉。替代方案見 8.3 Q3 |
| 輸入原值 | view model 保留使用者輸入**原值**（不去空白、不轉大小寫）；但 ISIN 形、網址形、含非可印刷 ASCII 字元、或超過長度上限者**結構上不保留**（見第 4 節） | 對照 poc 預覽既有行為（ISIN 形不回顯輸入） |
| 不冒稱身分 | 畫面不得出現「基金身份：已確認」類字樣；`T-ID1` 只限 Sheet「基金代號」欄，未涵蓋使用者輸入框（**INFERENCE**；`DEC-2026-11-13-06` (2)(4) 另明文排除 EXP 選股池代碼）；故路徑 B 不得宣稱 R-ID-1 適用 | F3 |

---

## 3　`build_profiles` 固定三來源的依賴（對應交辦第 3 項）

### 3.1　逐一證明（FACT）

| # | 證明點 | 證據 |
|---|---|---|
| 1 | 來源名稱封閉：`SOURCES ＝ ("MoneyDJ","TDCC","FundClear")` | `exp_profile.py`::`SOURCES` |
| 2 | 預設取數函式恰三支：`DECLARED_CACHED_FUNCTIONS` ＝ `fetch_moneydj_basic_fields`、`fetch_tdcc_listing`、`fetch_fundclear_declared_ccy`；`fetchers=None` 時以 `zip(SOURCES, DECLARED_CACHED_FUNCTIONS)` 組表 | `exp_profile.py`::`DECLARED_CACHED_FUNCTIONS`、`_check_fetchers` |
| 3 | 注入檢查：`fetchers` 必須是**恰含 `SOURCES` 三鍵**的 dict，每個值可呼叫，否則 `ValueError`——少一鍵（例如只給 MoneyDJ）直接失敗 | `exp_profile.py`::`_check_fetchers`；測試 `tests/test_v2_tables_exp_profile.py::test_fetchers鍵不對_ValueError` |
| 4 | 取數無短路：`ok` 的代碼以 `{src: _call(fns[src], full_key, _L1_STATUSES[src]) for src in SOURCES}` 一次呼叫三來源，無條件、無跳過 | `exp_profile.py`::`build_profiles` |
| 5 | `PARTIAL_FAILURE_POLICY = "accept"`（2026-10-14 客戶裁示：其餘成功來源一致即可顯示幣別，同時保留失敗標示）；每次呼叫都驗它屬於 `("accept","fail")` | `exp_profile.py`::`PARTIAL_FAILURE_POLICY`、`build_profiles` 開頭 |
| 6 | 各來源可交出的 status 白名單 `_L1_STATUSES` 三套各不相同（MoneyDJ：`ok`／`not_listed`／`unrecognized_page`／`not_found`／`failed`；TDCC：`ok`／`not_listed`／`code_unmapped`／`failed`；FundClear：`ok`／`not_listed`／`failed`），表外一律當 L1 回傳型別不符、判 `failed` | `exp_profile.py`::`_L1_STATUSES`、`_call` |
| 7 | 列層 `table_wide_failed`＝「有取數的每一檔，三來源都 failed」；只用三來源綜合判斷 | `exp_profile.py`::`build_profiles` |
| 8 | **欄位值的依賴**：名稱、成立日期、配息方式三格只讀 `results["MoneyDJ"]`（`_fund_name_cell(mdj)`、`_inception_cell(mdj, today)`、`_dividend_cell(mdj)`）；只有 `ccy` 格用三來源 | `exp_profile.py`::`build_profiles`、`_ccy_cell` |
| 9 | 三來源**各自**有成功快取（`TTL_1HOUR`）與失敗記憶（`FAILURE_MEMORY_SEC＝TTL_5MIN`，期間不重打）；快取與失敗記憶為**行程內共用**，鍵為（函式名，代碼），不分使用者。三支成功快取皆為 `_ttl_cache(ttl_sec=TTL_1HOUR, maxsize=256)`（每支最多 256 筆；`TTL_1HOUR`＝3600 秒；淘汰策略：`infra/cache.py::_ttl_cache` 的 docstring 稱 TTL＋LRU，但讀碼所見為超過 `maxsize` 時以 `min(寫入時間)` 砍最舊者、命中不更新時間，即依寫入先後而非存取先後——INFERENCE，**淘汰行為 NOT VERIFIED**，未實測）；`FAILURE_MEMORY_SEC`＝300 秒（`TTL_5MIN`，2026-11-18 於 `9e714861` 實讀常數），失敗記憶是**無上限的 dict**（`_FAILURE_MEMORY`，**有手動清除**：`clear_failure_memory()` 與各函式的 `cache_clear()`，且已 `register_cache`（`clear_all_caches()` 會清到）；**無容量上限、無週期性清除**，自動移除只發生在同鍵再次被查且已過期時；單組讀碼，INFERENCE，未實測） | `repositories/fund/declared_profile.py`::`_public`、`FAILURE_MEMORY_SEC` |
| 10 | 目前 `ui_v3` 與 `poc` 沒有任何檔案引用 `exp_profile`／`fund_keys`／`declared_profile`；`build_profiles` 的呼叫端在舊樹 `ui_v2/exp/` 與測試 | `git grep`（`9e714861`，字面搜尋，非窮舉） |

### 3.2　結論與揭露字句（RECOMMENDATION）

- **不得宣稱「MoneyDJ-only」。** 正確的兩句並列：①「路徑 B 顯示的名稱、成立日期、配息方式**取自 MoneyDJ 基本資料頁**」；②「一次查詢**會呼叫 MoneyDJ、TDCC、FundClear 三個來源**」。缺其中任一句，都會讓客戶對 BL-0551（FundClear 與 MoneyDJ 在 proxy 模式不驗憑證；TDCC 走 urllib）的暴露面判斷失準。
- 三來源的暴露面：TDCC 3-2 為整份清單下載（`repositories/fund/declared_profile.py` 內註記實測 5,295 列）；FundClear 為 `GetFundBasicInfo`。這兩個來源的資料**路徑 B 畫面完全用不到**（`ccy` 不顯示）。

### 3.3　若只想查 MoneyDJ 單來源：設計選項（這是設計選項，不是授權）

| 選項 | 內容 | 優點 | 缺點／風險 | 需要的新契約或授權 |
|---|---|---|---|---|
| **O1** 沿用 `build_profiles` 三來源呼叫，路徑 B 忽略 `ccy`／`declared`／`table_wide_failed` | adapter 只讀名稱、成立日、配息方式、費率四格與 MoneyDJ 的 `source_status` | **L2 零改動**；用的是已稽核的鏈 | 每次查詢多打兩個畫面用不到的來源；BL-0551 暴露面變大；TDCC／FundClear 失敗被靜默忽略（使用者看不到，但事實上發生） | 客戶接受第 3.2 節兩句揭露＋BL-0551 風險；仍屬「真實取數」，須等 A 線安全 Gate |
| **O2** 新增 L2 單來源建構函式（例如「只取 MoneyDJ 基本資料四格」） | 新函式重用同檔既有的 `_fund_name_cell`／`_inception_cell`／`_dividend_cell`／`_bound`（目前皆為私有）；不產出 `ccy`／`declared`；`fetcher` 可注入（單一可呼叫物） | 網路暴露面最小；與路徑 B 的「五欄」一致；來源語意誠實 | **修改 L2**：新契約文字（輸出形狀、狀態語意、與三來源版的值一致性）、新測試（與 `build_profiles` 的 MoneyDJ 三格逐格對拍）、`docs/v2/49` 登記；屬 data semantics 等級，需 1 組獨立稽核；不得影響 `ui_v2` 既有呼叫 | 新 DEC＋獨立稽核；本批**不授權** |
| **O3** 注入兩支假的 TDCC／FundClear 取數函式湊滿三鍵 | 組裝端提供回傳固定 status 的替身 | 不改 L2 | **不建議**：替身必須捏造 status（`ok`／`failed`／`not_listed` 任一種都是假證據），`source_status`、`ccy` 格與 `table_wide_failed` 會帶假資訊；違反 `CLAUDE.md` §1 | 無（不應採用） |

**RECOMMENDATION**：長期以 **O2** 為設計方向（暴露面最小、語意最誠實）；若客戶要最快驗證端到端且接受第 3.2 節揭露，**O1** 是唯一不改 L2 的路。兩者都須等 A 線安全 Gate 通過與客戶正式核准；**O3 不採用**。第 6 節的 adapter 草案只讀 O1／O2 共同擁有的欄位與 MoneyDJ 來源狀態，因此兩者皆相容。

---

## 4　入口攔截設計（對應交辦第 4 項）

### 4.1　FACT：現行 `fund_keys` 的實際行為

2026-11-18 於本工作樹以 `resolve_full_keys(輸入, mapping={})` 離線實跑（只呼叫本地純函式；`mapping={}` 不讀檔；未呼叫任何 L1 取數、未發任何請求）：

| 輸入（原樣） | `ok` | `full_key` | 備註 |
|---|---|---|---|
| `US0378331005`（ISIN 形，12 字元） | True | `US0378331005` | 被當作基金代碼收下 |
| `lu0123456789`（小寫 ISIN 形） | True | `LU0123456789` | 同上，且轉大寫 |
| `JP3633400001`、`KY1234567890`、`US0378331006`（皆為 ISIN 形；檢查碼對錯本組未逐一驗算） | True | 原字串 | 不檢查 ISIN 檢查碼 |
| `https://www.moneydj.com/funddj/yp/yp011001.djhtm?a=ACTI71`（MoneyDJ 網址） | True | `ACTI71` | 網址整段被吃掉，只留 `a=` 值 |
| `ACDD01-EQTAL005`（後綴碼） | True | 原字串 | 接受 `-` 後綴 |
| `TLZF9 X`（中間空白）／`AB`（2 字元）／空白／全形字元 | False | None | 各有原因文字 |

另：`PURE_CODE_PATTERN`＝`^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$`（`fund_keys.py`::`PURE_CODE_PATTERN`）；`build_profiles` 的列層 `fund_code` 與 `cells` 鍵＝呼叫端傳入的原字串，不受 `resolve_full_keys` 的大寫化影響。

### 4.2　攔截放在哪一層

| 層 | 評估 |
|---|---|
| L2 `fund_keys`／`exp_profile` | **不放**：它同時服務舊樹 `hld`／`alo`／`exp`；改規則屬修改 L2 正式行為與 R-ID-2／3 身分語意（Stop Gate），且本批不授權 |
| `ui_v3/viewmodels/`（純函式） | 可放「規則函式」本體（純 Python、無 I/O、易測），但 viewmodel 不應持有「是否呼叫 loader」的流程 |
| **`ui_v3/adapters/` 入口（建議）** | **在呼叫注入的 loader 之前**先做攔截；攔到即回 `BLOCKED` 狀態、不呼叫 loader、不發任何請求。規則表可就近放同檔，並以測試對照 `fund_keys` 原始碼鎖死 `PURE_CODE_PATTERN`（adapters 層不得 import `services`／`repositories`，同 `exp_pool` 切片做法） |
| 頁面（renderer） | 不放：頁面不應含資料規則；且頁面可能被繞過 |

### 4.3　規則（先後次序固定，第一個命中者決定原因；皆為 RECOMMENDATION）

| 序 | 規則 | 原因碼（固定類別碼，非畫面字樣） | 是否保留輸入原值 |
|---|---|---|---|
| 0 | 輸入不是字串 → 程式錯誤，raise 契約錯誤（不轉成狀態） | — | — |
| 1a | **原始輸入字串（未經任何 strip）的總長度** > `INPUT_ECHO_MAX`（建議 64；合法代碼上限為 51＝30＋1＋20，故只留餘裕）→ 攔截，**不呼叫 loader、不發請求**。此閘門在所有 strip 之前，使「合格代碼前後塞大量空格」與超大輸入都無法進入後續處理 | `code_format` | **不保留**（`input_code` 為 None） |
| 1 | 原始輸入字串為空字串，或全由 ASCII 空格（0x20）組成（長度已通過 1a）→ 攔截。tab、換行等其他空白**不屬 blank**，歸規則 2 | `blank` | 保留（僅含空格，無控制字元） |
| 2 | **原始輸入字串（未經任何 strip）** 含任何 **0x20–0x7e 以外**的字元 → 攔截。判定採**正向白名單**（可印刷 ASCII），不用「控制字元」一詞，以免漏掉零寬、全形、DEL（0x7f）、C1 與各種空白。**本批不設例外**（含前後的 tab／換行：fail-closed，寧可請使用者重貼） | `control_or_non_ascii`（沿用此名，涵蓋白名單以外的所有字元） | **不保留**（結構上不帶，避免回顯不可見字元或隱寫內容） |
| 3 | **網址形**：含任一字元 `:` `/` `\` `?` `&` `=` `#` `%` `@`，或（不分大小寫）含子字串 `http`、`www.`、`moneydj` → 攔截 | `url_shape` | **不保留**（網址可能夾帶 token 或個資） |
| 4 | **ISIN 形**：僅為判斷而暫時把**所有非英數字元**（空格、`-`、`.`、`_`、`,` 等，規則 2 之後必為可印刷 ASCII）全部移除並轉大寫，再 `fullmatch` `[A-Z]{2}[A-Z0-9]{9}[0-9]`（移除後共 12 字元，結構判斷，**不檢查 ISIN 檢查碼**）→ 攔截。移除只用於判斷，**不改變**傳給 loader 的字串（放行者仍是原樣） | `isin_shape` | **不保留**（延續 poc 預覽既有行為：ISIN 形不回顯） |
| 5 | 以 `strip(' ')`（**只去 ASCII 空格**，不用不帶參數的 `strip()`）並轉大寫後，**以 `fullmatch`（整段完全符合）**比對 `PURE_CODE_PATTERN`，不符（含內部空白、其他標點、長度不合）→ 攔截 | `code_format` | 保留（原始長度已由規則 1a 保證 ≤ `INPUT_ECHO_MAX`） |
| 6 | 以上皆未命中 → 放行；以 `raw.strip(' ')`（**保留大小寫**）呼叫 loader（`resolve_full_keys` 自行大寫化） | — | 保留（原始長度已由規則 1a 保證 ≤ `INPUT_ECHO_MAX`，故 `input_code` 必保留；strip 後 ≤ 51 由規則 5 的 `PURE_CODE_PATTERN` 保證。**更正前一版**：「放行者必 ≤ 51」只對 strip 後成立，對原始字串不成立，故需要 1a） |

說明：
- **次序理由**：網址形與 ISIN 形的字串也能通過 `PURE_CODE_PATTERN`（4.1），所以必須排在格式檢查之前，否則會被放行。ISIN 形判斷在轉大寫之後做，才能涵蓋小寫輸入。
- **為何規則 2 作用於未 strip 的原始字串（S3，FACT）**：Python `str.strip()` 預設會吃掉 `\x1c`–`\x1f`、`\x0b`、`\x0c`、`\n`、`\t`，以及 `\x85`、`\xa0`（2026-11-18 本機 Python 實測；`\x00`、`\x7f` 不會被吃）。若先 strip 再檢查，這些字元出現在頭尾時會**無聲消失**。實測 `resolve_full_keys` 對 `\x1cACTI71\n` 回 `ok=True`、`full_key＝ACTI71`（`mapping={}`，離線）——L2 本身就會吃掉頭尾控制字元。因此 adapter 必須在 strip 之前用白名單檢查，且 `input_code` 絕不存入白名單以外的字元（A8 的「原值保留」只適用於通過規則 2 的字串）。
- **ISIN 形的覆蓋範圍與限制（S4，RECOMMENDATION＋待客戶／設計者確認）**：若只對緊密 12 碼判斷，`US 0378331005`、`US-0378331005`、`US.0378331005`、`US_0378331005`、`US,0378331005` 會落入 `code_format` 並被回顯，`US0378331005X`（13 碼）亦同。**推薦**：規則 4 先移除**所有非英數字元**再判斷（已寫入上表），涵蓋前面各種分隔寫法；**理由**：分隔符可以是任何標點，只列空格與 `-` 會留下漏洞，回顯它們等於回顯 ISIN。**仍存在的限制，據實揭露**：多一個字元的變體（如 13 碼）不是 ISIN 形，仍走 `code_format` 並在長度上限內回顯；poc 預覽的 `classify_lookup`（`poc/fund_search_fixture_preview/fund_search_logic.py`）只判緊密 12 碼，同樣有此限制，且該 poc 不剝除分隔符。**誤攔面評估（INFERENCE，未實測）**：`PURE_CODE_PATTERN` 本來就只允許字母、數字與一個 `-`，所以除 `-` 以外的分隔符號本來就會被規則 5 以 `code_format` 攔下——改為移除所有非英數字元，對它們只改變**原因碼與是否回顯**，不新增被擋的輸入。真正新增誤攔的只有「帶 `-` 後綴、移除 `-` 後恰為 2 字母開頭＋9 英數＋末碼數字」的合法後綴碼（例如主碼 6 碼＋`-`＋後綴 6 碼，且前 2 碼為字母、末碼為數字）；是否存在未驗。偏保守側，併入 U9。是否採用列入 Q6。
- **`http` 子字串的誤攔面（Nit）**：規則 3 的子字串判斷會攔下含 `HTTP`（不分大小寫）的合法 MoneyDJ 代碼；機率極低（repo 內 8 個真實代碼樣本長度皆 5–7 字元，無一含此子字串），偏保守側。
- **不檢查 ISIN 檢查碼的理由**：檢查碼錯誤的「像 ISIN 的字串」同樣不該被當 MoneyDJ 代碼送出；檢查碼是結構之外的額外判斷，也不應讓「錯誤的 ISIN」意外通過。
- **誤傷風險（INFERENCE，NOT VERIFIED）**：真實 MoneyDJ 代碼若恰為「前 2 碼字母、共 12 碼、末碼數字」會被誤攔。repo 內 8 個真實 MoneyDJ 代碼樣本（`tests/fixtures/moneydj_basic/`）長度皆為 5–7 字元，**未見 12 字元者**；但這不證明不存在。誤攔的代價是使用者看到「ISIN 目前未啟用」類訊息而無法查該檔（偏保守側）。
- **為何非 ASCII 先於網址形**：`fund_keys._resolve_one` 本身也先擋非 ASCII（避免 `upper()` 的 Unicode 展開）；順序與其一致。

### 4.4　輸入原值如何保留

- adapter 對外函式簽章同時收「使用者原始輸入」；view model 的 `input_code` 欄存**原值**（不去空白、不轉大小寫），**但僅限通過規則 2 白名單、未命中規則 3／4、且原始長度 ≤ `INPUT_ECHO_MAX`（建議 64）者**——長度閘門（規則 1a）作用於**未 strip 的原始字串**並在呼叫 loader 之前，所以不會出現「state＝RESULT 而 `input_code`＝None」（合格代碼加大量前後空格會被 1a 以 `code_format` 攔截，不發請求）；其餘一律為 None（結構上不帶，**不是交給 renderer 決定**，S5）。
- 傳給 loader 的是**另一個**以 `strip(' ')` 去頭尾 ASCII 空格的字串，並以同一字串作為 `build_profiles` 的 `cells` 鍵；adapter 以該字串反查 `cells`，不靠大寫化後的代碼。
- 轉義是 renderer 的責任（poc 預覽已有 HTML escape 前例）；view model 不存已轉義字串，避免二次轉義。
- 對照 `T-ID1`「原值保留（僅去前後空白）」：該契約不適用於使用者輸入，但路徑 B 採更保守的「連空白都保留」，並在需要時才由 renderer 決定如何顯示。

---

## 5　狀態集設計（對應交辦第 5 項）

### 5.1　完整狀態表

字樣一律是 `PendingWording`（暫行、未核准）；下表「可說／不可說」指**語意範圍**，不是定稿字樣。

| # | 狀態 | 觸發條件 | UI 可說（語意） | UI 不可說 |
|---|---|---|---|---|
| S0 | **尚未查詢** | 頁面剛載入或使用者尚未送出；adapter 未被呼叫 | 提示輸入 MoneyDJ 基金代碼；常駐「ISIN 尚未啟用」說明（延續 poc 暫行句，待 G-4 定字） | 任何基金資料、「查無」、「0 筆」 |
| S1 | **入口攔截**（原因碼 6 種） | 第 4.3 節規則 1～5 命中，或 loader 回傳顯示 L2 拒絕該鍵（`source_status[代碼]` 為空，即 `ok` 非真；原因碼 `key_rejected`） | `blank`：請輸入代碼；`isin_shape`：ISIN 目前未啟用；`url_shape`／`code_format`／`control_or_non_ascii`：輸入不是可用的代碼格式；`key_rejected`：這個輸入無法對應到查詢用代碼。**皆為格式或功能範圍的說明** | 基金不存在、代碼錯誤（格式不符不等於代碼錯誤）、ISIN 無效、已轉換為某基金、回顯網址或 ISIN |
| S2 | **來源失敗** | MoneyDJ 來源狀態為 `failed`（取不到：網路、403／407／429、5xx、主機冷卻、200 空內文、L1 非預期例外）；或失敗記憶冷卻中（`cooling`）；或注入的 loader 拋明確的取數例外（`LookupSourceError`、內建 `ConnectionError`／`TimeoutError`；原因碼 `loader_io_error`；其餘例外型別是程式或契約錯誤，往外拋） | 這次取數失敗，不是對基金身份的判斷（G-2 暫行句）；冷卻中可說「稍後再試」類 | 基金不存在、查無基金、代碼有誤、已停售；錯誤原文、網址、例外訊息 |
| S3 | **頁面無法確認**（原因碼 4 種） | MoneyDJ 來源狀態為 `unrecognized_page`（回來了但不符身分判準）、`not_found`（兩種頁型兩個主機全 404）、`not_listed`（L2 白名單內但現行 L1 不會交出）；或來源 `ok` 但名稱格不是有值（名稱是身分綁定的證據，沒有它就不展示其他欄） | 來源頁面無法確認是這一檔／沒有找到對應頁面；**這不是對基金存在與否的結論** | 基金不存在、查無此基金、代碼錯誤、顯示部分欄位當作這一檔的資料 |
| S4 | **有結果** | MoneyDJ 通過身分判準且名稱有值 | 逐欄顯示：名稱原字面；配息方式（`accum`／`dist` 對應的暫行字樣）；成立日；費率欄 | 基金身份已確認、幣別、淨值、報酬、績效、取得時間、來源名、推薦／排名；欄位缺值寫成 0、「無」、「不配息」、「無費用」 |
| S4-a | ├ 欄位級**有值** | 該格 `status＝ok` | 顯示值 | 加工過的值 |
| S4-b | ├ 欄位級**缺值** | 該格 `not_ready`（含標籤缺、表外寫法、成立日不採用、費率恆缺） | 缺值符號（`◇` 或 `⬜` 待定，見 Q5）；費率欄可帶「契約上目前無來源」的結構標記 | 把缺值說成「不存在」「無」或 0 |
| S4-c | └ 欄位級**分歧** | 該格 `status＝inconsistent`（L2 目前只對 `ccy` 使用此值；若出現在四格即映為分歧） | 該欄各來源不一致，不採用任何一個 | 挑一個顯示 |
| S5 | **未知**（契約不符，fail-closed） | loader 回傳缺鍵、型別不符、未知的 status 字面、cells 鍵不符、費率格非缺值、配息方式不在 `accum`／`dist`、成立日不是 ISO 日期等 | adapter **raise 契約錯誤**；由**頁面層單一邊界**攔截（見 5.2 第 7 點），只顯示一句固定的「目前無法顯示」並標固定類別碼，不回顯收到的內容；log 只記型別名 | 任何資料、猜測的狀態、把未知併入 S2 或 S3 |

### 5.2　設計要點（RECOMMENDATION）

1. **S2 與 S3 不得合併**。L2 本身已把「取不到」（⛔）與「頁面回來但不符判準／404」（⬜）分開（`exp_profile.py` 檔頭〈綁定閘門〉最後一段）；合併會把「來源出問題」與「這個代碼沒有對得上的頁面」混為一談，兩者對使用者的下一步動作不同。
2. **S3 的 `not_found`（全 404）不是「基金不存在」**：404 可能來自代理、頁型錯誤或來源不收該代碼。該原因碼的名稱用 `no_page`，不用任何含「不存在」意味的詞。
3. **S4-c 在現行 L2 下無法被觸發**（見 0 結論第 6 點）：MoneyDJ 頁面上同一標籤出現兩個不同值時，L2 輸出 `not_ready`＋自由文字，adapter 無法也不應解析文字，因此該情形在 view model 內會落在 S4-b。這是**已知的語意損失**（缺值與分歧不可區分），不是設計目標；若要區分，需 L2 輸出機器可讀的原因碼（屬新契約，列入 9 未決）。
4. **TDCC／FundClear 的失敗與 `ccy` 格的 `inconsistent`／`fetch_failed` 必須不影響路徑 B 的狀態**（O1 下它們仍會發生）。測試計畫第 7 節 T-B6 專門鎖這一點。
5. **未知狀態用例外而非 view 狀態**：沿用 `exp_pool` 切片的做法（契約不符 raise、訊息只含欄位名與型別名）。**S2 只接受明確的取數例外**（見 6.3：`LookupSourceError`、內建 `ConnectionError`／`TimeoutError`）；其餘非契約例外（`TypeError`、`ValueError`、`KeyError` 等）不轉任何狀態，往外拋，由**頁面層邊界**處理（下一點）。
6. 欄位級狀態只在 S4 內存在；S1／S2／S3 不帶任何欄位值（結構上不可能洩漏部分資料）。
7. **頁面層對非契約例外的邊界（RECOMMENDATION）**：`LookupContractError` 與所有往外拋的非契約例外，都必須在**日後頁面／獨立入口的單一呼叫邊界**被攔截（不在 adapter、不在 view model；Streamlit 預設會把未攔截例外連同訊息畫給使用者，故必須有人攔）。邊界行為：①畫面只顯示**一句固定句**（`PendingWording`，待核；語意為「目前無法顯示」，不暗示基金不存在、不鼓勵重試）；②**不回顯**例外文字、不顯示 traceback、不顯示輸入；③log **只記例外型別名與固定類別碼**（不記訊息、不記 traceback 的參數值、不記使用者輸入）；④不把它歸類成 S2／S3，也不寫入失敗記憶；⑤測試：頁面層（日後）須有「注入會拋 `TypeError`／`ValueError`／`LookupContractError` 的 loader，斷言畫面只含固定句、log 無訊息」的案例。本批無頁面，故僅登記邊界歸屬，不設計頁面。

---

## 6　內部 adapter／ViewModel 設計草案（對應交辦第 6 項）

> 以下簽章以文字表示，**不是可 import 的程式檔**，本批不新增任何 `.py`。

### 6.1　模組與檔名（草案）

| 檔 | 內容 |
|---|---|
| `ui_v3/viewmodels/fund_lookup.py` | 狀態列舉、原因碼常數、frozen dataclass、契約錯誤型別；只用標準函式庫（與 `ui_v3/viewmodels/exp_pool.py` 同風格）。**不含任何顯示字樣**（字樣屬 renderer／wording 層，待核准） |
| `ui_v3/adapters/fund_lookup.py` | 入口攔截函式、L2 回傳形狀適配、注入式 loader 呼叫；**不 import 任何 `services`／`repositories`／`infra`／`shared`／`streamlit`**（與 `ui_v3/adapters/exp_pool.py` 同做法，L2 字面在本檔另存並由測試對照原始碼鎖死） |

### 6.2　ViewModel 欄位（文字簽章）

```text
LookupState        : 列舉 NOT_QUERIED | BLOCKED | SOURCE_FAILED | PAGE_UNMATCHED | RESULT
FieldStatus        : 列舉 VALUE | MISSING | CONFLICT
FieldView          : (status: FieldStatus, value: str | None)         # VALUE 時 value 非空；其餘 value 必為 None
ProfileFields      : (fund_name: FieldView, dividend_policy: FieldView,
                      inception_on: FieldView, mgmt_fee_rate_pct: FieldView)
FundLookupView     : (state: LookupState,
                      input_code: str | None,        # 輸入原值；isin_shape／url_shape／control_or_non_ascii 命中、或長度 > INPUT_ECHO_MAX 時為 None
                      reason_code: str | None,       # 固定類別碼；NOT_QUERIED 與 RESULT 為 None，其餘必非 None
                      fields: ProfileFields | None)  # 只有 RESULT 才有
原因碼（固定集合）  : BLOCKED        ∈ {blank, control_or_non_ascii, url_shape, isin_shape, code_format, key_rejected}
                      SOURCE_FAILED  ∈ {source_failed, source_cooling, loader_io_error}
                      PAGE_UNMATCHED ∈ {unrecognized_page, no_page, source_not_listed, name_unconfirmed}
LookupContractError: 繼承 ValueError；訊息只含欄位名與型別名，不回顯收到的值
LookupSourceError  : 繼承 Exception；組裝端 loader 包裝層用來表示「取數本身失敗」；訊息不被讀取、不進 view、不進 log
```

`__post_init__` 不變式（比照 `PoolSourceView`）：
- `RESULT` ⇒ `fields` 非空、`reason_code` 為 None、`fund_name.status` 必為 `VALUE`（名稱是身分綁定證據）、`mgmt_fee_rate_pct` 必為 `MISSING`、`dividend_policy.value ∈ {accum, dist, None}`、`inception_on.value` 為合法 ISO 日期字串或 None。
- 非 `RESULT` ⇒ `fields` 為 None。
- `reason_code` 必須屬於該狀態的固定集合。
- `FieldView`：`VALUE` ⇔ `value` 非 None。

**結構上不存在的欄位（防洩漏，由測試以 `dataclasses.fields` 鎖死）**：`ccy`、`fetched_at`、`observed_at`、任何來源或供應者名稱、`source_tier`、`raw`、`reason` 文字、`error` 文字、`declared`、`table_wide_failed`、`full_key`、淨值、報酬、績效。

### 6.3　Adapter 函式（文字簽章）

```text
screen_input(raw: str) -> (reason_code | None)
    純函式；依 4.3 規則 1～5；不呼叫任何外部東西。

adapt_profile_result(input_code: str, query_text: str, raw_result: object) -> FundLookupView
    純函式；raw_result 為「build_profiles 形狀」的 dict（O1）或其 MoneyDJ 子集（O2）；
    只讀：cells[query_text] 的 fund_name／dividend_policy／inception_on／mgmt_fee_rate_pct 四格（status、value）、
          source_status[query_text]["MoneyDJ"] 的 status 與 cooling。
    不讀：ccy 格、declared、table_wide_failed、rows、任何 reason／raw／error 文字、其他來源的狀態。
    形狀不符 → LookupContractError。

lookup_fund(loader: Callable[[str], object], raw_input: object) -> FundLookupView
    loader 無預設值（本模組不知道、也不 import 真實 L1／L2）；
    先 screen_input；命中即回 BLOCKED（不呼叫 loader）；
    放行後 loader(query_text)；loader 拋 `LookupSourceError`（viewmodel 層定義；由組裝端 loader 包裝層在**自己的**網路呼叫失敗時轉出）或內建 `ConnectionError`／`TimeoutError` → SOURCE_FAILED(loader_io_error)（例外字串丟棄，log 只記例外型別名）；**其餘例外（TypeError、ValueError、KeyError、AssertionError 等）一律往外拋，不轉狀態**；
    回傳形狀不符 → LookupContractError 照樣往外拋（不吞、不轉成 SOURCE_FAILED）。

not_queried() -> FundLookupView
```

**loader 契約（組裝端日後負責，本批不寫）**：`loader(query_text) → resolve_full_keys([query_text], mapping={}) → build_profiles(…)`，回傳 `build_profiles` 原樣 dict。真正的組裝（把真實 L1／L2 接到 loader）屬「資料接線」，不在本批授權內，也不在 adapter 內。

**State 判定順序（`adapt_profile_result` 內）**：
1. `source_status[query_text]` 為空 dict ⇒ BLOCKED(`key_rejected`)（L2 已拒絕該鍵，未取數）。
2. MoneyDJ 來源狀態 `failed` ⇒ SOURCE_FAILED（`cooling` 為真 ⇒ `source_cooling`，否則 `source_failed`）。
3. MoneyDJ 來源狀態 `unrecognized_page`／`not_found`／`not_listed` ⇒ PAGE_UNMATCHED（`unrecognized_page`／`no_page`／`source_not_listed`）。
4. MoneyDJ 來源狀態 `ok`，但 `fund_name` 格不是 `ok` ⇒ PAGE_UNMATCHED（`name_unconfirmed`）。
5. 其餘 ⇒ RESULT，四格逐格轉為 `FieldView`（`ok`→VALUE、`not_ready`→MISSING、`inconsistent`→CONFLICT；`fetch_failed` 出現在 MoneyDJ 來源 `ok` 的情況下 ⇒ 契約不符）。
6. 任何未列舉的 status 字面 ⇒ `LookupContractError`。

### 6.4　與 ui_v3 layer guard 的相容性（FACT＋INFERENCE）

| 守衛規則（`tests/ui_v3/ui_v3_guard_lib.py`） | 本設計 |
|---|---|
| `LAYER_DEPS["adapters"] ＝ {adapters, viewmodels}`：adapters 只可 import 同層與 viewmodels | adapter 只 import `ui_v3.viewmodels.fund_lookup` 與標準函式庫 ✅ |
| `services` 僅 adapters 可 import 且只准 `services.v2_tables`／`services.v2_domain` 前綴 | 本設計**連這兩個前綴都不 import**（比守衛更嚴），L2 字面由測試鎖死 ✅ |
| `shared` 僅 `shared.ui_semantics` 且只准 viewmodels／pages | view model 本批不 import（字樣未核准）✅ |
| 網路／外部程序／動態 import 套件一律擋；未知第三方套件擋 | 只用 `dataclasses`、`enum`、`logging`、`re` 等標準函式庫 ✅ |
| 唯讀守衛：不得 import 已知寫入函式、不得有 HTTP 寫入動詞、檔案寫入等 | 不涉及 ✅ |
| 母體取 `ui_v3/` 底下全部 `.py`（新增檔自動納入） | INFERENCE：新檔會被既有守衛自動掃到；實際是否有其他守衛需同步登記（例如頁面登錄表、no-engineering-leak、wording fidelity 類）**NOT VERIFIED**，施工時以整個 `tests/ui_v3/` 目錄實跑為準 |

### 6.5　與 `exp_pool` 切片的一致性

| 面向 | `exp_pool` 切片 | 本設計 |
|---|---|---|
| 檔位置 | `ui_v3/viewmodels/` ＋ `ui_v3/adapters/` | 相同 |
| loader | 注入、無預設 | 相同 |
| 契約不符 | `PoolContractError`（訊息只含欄位名與型別名）fail-closed | 相同（`LookupContractError`） |
| 取數函式拋例外 | 注入的取數函式拋**任何 `Exception`** → `FAILED`（`loader_raised`），例外字串丟棄、log 只記型別名（`ui_v3/adapters/exp_pool.py::load_pool_view` 現況：`except Exception`） | **刻意不同（S6）**：只轉明確列舉的取數例外（`LookupSourceError`、內建 `ConnectionError`／`TimeoutError` → `loader_io_error`），其餘往外拋。**不用廣義 `OSError`**：它含 `FileNotFoundError`／`PermissionError` 等多半是設定或程式問題的子類，會把它們偽裝成暫時性故障；`requests.exceptions.RequestException` 雖繼承 `OSError`，但 `requests` 的 `ConnectionError`／`Timeout` **不是**內建的 `ConnectionError`／`TimeoutError`（本機以 `issubclass` 實測為否），adapter 也不得 import `requests`——所以翻譯責任在組裝端 loader 包裝層（把自己的網路例外轉成 `LookupSourceError`）。**理由**：路徑 B 的 loader 內層是 `build_profiles`，它的 `_call` 已把 L1 的任何 `Exception` 轉成 `failed` 結果；真正跑到 adapter 的例外多半是程式或契約錯誤（例如非字串輸入、`fetchers` 鍵不對、`PARTIAL_FAILURE_POLICY` 非法的 `TypeError`／`ValueError`），一律轉成「來源失敗」會把程式錯誤偽裝成暫時性故障，使用者會一直重試。`exp_pool` 的 loader 是 `load_pool_codes`（Sheet 讀取），例外面較寬，故其做法不直接適用 |
| 原因碼 | 固定類別碼，不上畫面 | 相同 |
| 洩漏面 | 無 backend 名稱、無原始訊息 | 相同，另加：無 `ccy`／`fetched_at`／來源名 |
| L2 字面 | adapter 另存一份，測試對照原始碼鎖死 | 相同 |
| 時間欄 | 有 `read_at`（選股池讀取時間） | **刻意沒有**：路徑 B 不得顯示 `fetched_at`（R-NAV-3 暫緩，卡片第 2 節） |
| 不可用狀態 | `UNAVAILABLE`（`pool_not_cloud`） | 無對應（路徑 B 不讀 Sheet） |
| 頁面層對非契約例外 | 本批 `exp_pool` 切片無頁面，未定義 | **本設計補定義邊界歸屬**（5.2 第 7 點）：頁面層單一邊界攔截 `LookupContractError` 與往外拋的非契約例外，固定句、不回顯、log 只記型別名；adapter 與 view model 不攔截 |

---

## 7　注入測試計畫（對應交辦第 7 項）

> 本批**不新增測試檔**；以下是施工時的測試設計。命名比照既有 `tests/ui_v3/test_ui_v3_exp_pool_*.py`。所有輸入為注入的假 loader 與假字典；負控字串為各測試現編，**不列入本文件**（`CLAUDE.md` §-2.A 第 8 款）。

### 7.1　案例清單

| 群 | 案例 | 目的 |
|---|---|---|
| **T-A 入口攔截**（loader 為「被呼叫即失敗」的哨兵，並計次） | A1 空字串、純 ASCII 空格（`blank`）；tab、換行**不屬 blank**，歸規則 2，案例見 A6；A2 非字串輸入（None、數字、bytes）→ 契約錯誤而非狀態；A3 ISIN 形：大寫、小寫、前後空白、檢查碼對與錯、不同國碼前綴、含各種分隔符（`US 0378331005`、`US-0378331005`、`US.0378331005`、`US_0378331005`、`US,0378331005`；斷言皆為 `isin_shape` 且 `input_code` 為 None）；A3b 13 碼變體（限制內案例，斷言走 `code_format` 且僅在長度上限內回顯）；A4 邊界：11 字元、13 字元、12 字元末碼為字母（不是 ISIN 形，應放行）、12 字元含連字號；A5 網址形：`http`／`https`／大寫 `HTTP`（並含一個合法形狀但內含此子字串的代碼，斷言被攔並記為已知誤攔面）、無 scheme 的 `www.moneydj.com/…`、只含 `?a=`、含 `%`／`#`／`@`、`//host`；A6 白名單以外字元：全形英數、零寬字元、DEL（0x7f）、C1、`\x1c`–`\x1f`、`\x0b`、`\x0c`、`\xa0`，且分別置於**頭、中、尾**（尤其頭尾——strip 會吃掉的位置）、換行、tab；A6b 以上任一命中時 `input_code` 為 None 且 view 內不含該字元；A7 格式：2 字元、含空白、31 以上字元、`-` 開頭／結尾、過長後綴；A7b **原始字串總長度**剛好等於、剛好超過 `INPUT_ECHO_MAX`，含「合格代碼＋前後大量空格」使原始長度超限（應以 `code_format` 攔截、`input_code` 為 None、loader 計次為 0），以及長度恰為上限的合格輸入（應放行且 `input_code` 保留）；A7c 帶尾端換行的合法代碼：由規則 2 先攔下（`control_or_non_ascii`），**不會觸及規則 5**——故 `fullmatch` 改 `match` 的突變在規則 2 之後是等價突變，無法由公開行為分辨，須列入「已記載存活」（見 7.2 末）；A8 `input_code` 原值保留（ASCII 空格、大小寫、HTML 特殊字元原樣）與「規則 1a／2／3／4 命中（即原始長度超限、白名單以外字元、網址形、ISIN 形）時為 None」；A9 規則次序（ISIN 形字串同時符合格式 → 應報 `isin_shape`；網址形含 12 字元尾碼 → 應報 `url_shape`）；A10 每個攔截案例 loader 呼叫次數為 0 | 證明攔截在 loader 之前、原因碼互斥、不回顯 |
| **T-B 狀態轉換**（假 loader 回 `build_profiles` 形狀） | B1 全欄有值；B2 各格逐一缺值組合（含費率恆缺）；B3 MoneyDJ `failed`（含 `cooling` 真／假）；B4 `unrecognized_page`／`not_found`／`not_listed` 各自 → `PAGE_UNMATCHED` 對應原因碼；B5 來源 `ok` 但名稱格 `not_ready` → `name_unconfirmed`，且不帶其他欄位；B6 **TDCC／FundClear 失敗、`ccy` 格 `inconsistent`／`fetch_failed`、`table_wide_failed` 為真，而 MoneyDJ 為 `ok` ⇒ 仍為 RESULT，且 view 看不出任何異常**；B7 `source_status[code]` 為空 → `key_rejected`；B8 同一字串重複、大小寫不同字串（`cells` 鍵必須用 adapter 傳給 loader 的那一個）；B9 loader 拋 `LookupSourceError`／內建 `ConnectionError`／`TimeoutError`（含帶密鑰字樣的例外訊息）→ `loader_io_error`，view／log 皆不含該字串；B10 loader 拋 TypeError／ValueError／KeyError／FileNotFoundError／PermissionError → 原樣往外拋，不轉成任何狀態 | 狀態互斥且不混淆 |
| **T-C fail-closed** | C1 回傳非 dict／缺 `cells`／缺 `source_status`；C2 `cells` 缺某欄或多出別的代碼；C3 未知 cell status 字面；C4 未知 MoneyDJ 來源 status；C5 費率格有值或 `ok`；C6 `dividend_policy` 值不在 `accum`／`dist`；C7 `inception_on` 非 ISO、日期不存在；C8 `status＝ok` 但 value 為 None，或非 `ok` 但 value 非 None；C9 `fetch_failed` 出現在 MoneyDJ 來源 `ok` 之下；C10 契約錯誤訊息不含收到的值（含 URL、密鑰字樣） | 未知一律 raise，不降級成缺值或失敗 |
| **T-D 不洩漏** | D1 以 `dataclasses.fields` 鎖死 view model 欄位集合（無 `ccy`／`fetched_at`／來源名等）；D2 將 L2 的 `reason`／`raw`／`error` 填入含網址與密鑰形字串，確認 view 與 log 皆不含；D3 `FundLookupView` 的 `repr`／`str` 不含上述字串 | 結構上不帶 |
| **T-E 禁語意** | E1 原因碼集合為封閉集合，且集合內沒有表達「不存在」「查無」「無效」的碼；E2 `PAGE_UNMATCHED` 與 `SOURCE_FAILED` 的原因碼集合互不相交；E3 每個 MoneyDJ 來源 status 字面都有恰一個去處（窮舉表測試，新增字面時紅燈） | 防止日後把「無對應頁面」改成「不存在」 |
| **T-F 靜態守衛** | F1 兩個新檔符合既有 `ui_v3` import 守衛；F2 adapter 不含 `services`／`repositories`／`infra`／`shared`／`streamlit` import（比照 `exp_pool` adapter 測試的字串／AST 掃描）；F3 檔內無 I/O、環境變數、`os`／`sys` 等；F4 `lookup_fund` 的 `loader` 參數無預設值（以簽章檢查）；F5 不含任何 `ccy`／`fetched_at` 識別字 | 守衛 |
| **T-G 與真實 L2 的差分** | G1 在**獨立子程序**內載入真實 `fund_keys.resolve_full_keys(…, mapping={})` 與 `exp_profile.build_profiles(…, fetchers=<測試注入的三支假取數>, now=<固定時間>)`，把真實輸出餵 adapter，逐情境（全有值、MoneyDJ 失敗、`unrecognized_page`、`not_found`、冷卻中、未綁定、代碼被 L2 拒絕、TDCC／FundClear 失敗）斷言狀態；G2 離線黃金樣本：用 `tests/fixtures/moneydj_basic/` 的真實頁面快照，沿 `tests/test_declared_profile.py` 既有做法把 `fetch_url_with_retry` 換成依網址回應的替身，串「真實 L1 解析 → 真實 L2 → adapter」，比對 adapter 的名稱／成立日／配息方式與 `rows[0]` 逐格相同；G3 以 AST 讀 `exp_profile.py`／`declared_profile.py`／`fund_keys.py` 原始碼，鎖死：`STATUS_*` 四個字面、`CELL_FIELDS`、`dp.STATUS_*` 六個字面、`PURE_CODE_PATTERN`、`accum`／`dist` 兩值、`MIN_INCEPTION_YEAR` | **可行（INFERENCE）**：L2 的 `build_profiles` 本來就支援注入 `fetchers` 與 `now`，全程不需網路；已有同型前例（`exp_pool` adapter 的子程序差分）。可行性僅讀碼判斷，未實作驗證 |
| **T-H 突變測試** | 見 7.2 | 證明檢查咬得住 production 函式 |

### 7.2　變異測試目標（讀目前 production 原始碼、套一處記憶體內替換，至少一條檢查必須失敗）

| 編號 | 突變 | 應被誰咬住 |
|---|---|---|
| M1 | 移除 ISIN 形攔截 | A3、A9 |
| M2 | 把 ISIN 形末碼條件由「數字」放寬為「英數」 | A4（12 字元末碼為字母案例） |
| M3 | 移除網址形攔截 | A5 |
| M4 | 把攔截挪到 loader 呼叫之後 | A10（loader 計次） |
| M5 | 把 `input_code` 的規則 2／3／4 不保留改為保留 | A8、D3 |
| M6 | 把 `unrecognized_page` 併入 `SOURCE_FAILED` | B4、E2 |
| M7 | 把 `not_found` 改成會觸發「不存在」類原因碼 | E1 |
| M8 | 接受費率格的非缺值 | C5 |
| M9 | 未知 cell status 一律當 MISSING | C3 |
| M10 | 把契約錯誤吞掉並回 `SOURCE_FAILED` | C 群整體、B9 對照 |
| M11 | 例外字串帶進 view 或 log | B9、D2 |
| M12 | view model 新增 `fetched_at` 或 `ccy` 欄位 | D1、F5 |
| M13 | `ok` 來源但名稱格缺值時仍回 RESULT | B5 |
| M14 | 讀取 `table_wide_failed` 或 `ccy` 格影響狀態 | B6 |
| M15 | 刪除 `key_rejected` 分支 | B7 |
| M16 | 把 `cooling` 判斷反向 | B3 |
| M17 | `inconsistent` 映為 VALUE | B2／C 群 |
| M18 | 對輸入做 `strip()`／`upper()` 後存入 `input_code` | A8 |
| M19 | 規則 2 改成先 `strip()` 再檢查白名單 | A6（頭尾位置案例） |
| M20 | 移除原始字串總長度閘門（規則 1a） | A7b |
| M21 | 規則 4 不先移除非英數字元（只移除空格與 `-`，或完全不移除） | A3（`.`、`_`、`,`、空格、`-` 分隔案例） |
| M22 | loader 例外改回「任何 Exception 皆轉狀態」，或擴大為廣義 `OSError` | B10 |
| M23 | 規則 2 之後的 `fullmatch` 改為 `match` | **等價突變，預期存活**（見下） |

存活的突變只能列在「已記載存活」清單並附理由（比照 `test_ui_v3_exp_pool_mutations.py`）。**預期的已記載存活：M23**——規則 2 已攔下所有換行，`$` 吃尾端換行的差異在規則 2 之後不可觀察；以靜態檢查（原始碼須使用 `fullmatch`）補強。

### 7.3　CI 不得靜默跳過

沿用 `exp_pool` adapter 測試既有做法：差分測試（T-G）所需依賴載不起來時，`CI` 環境變數為真則 **`pytest.fail`**，非 CI 本機才 `skip` 並印明確原因；另加一個後設守衛，確認該差分測試檔內除該輔助函式外沒有其他 `skip`／`importorskip` 路徑。fast lane 與整個 `tests/ui_v3/` 目錄須全數實跑；瀏覽器層測試不在本批範圍（無頁面）。

---

## 8　最小正式資料契約與接線授權包（對應交辦第 8 項）

### 8.1　最小正式資料契約（草案；**僅路徑 B 的五欄**）

> 這是**供客戶審閱的契約文字草案**，不是已核准契約；核准前不得被引用為依據。不含幣別、淨值、報酬、績效、`fetched_at`、供應者名稱。
> 狀態與缺值語意遵循 `CLAUDE.md` §1（Fail Loud）與 `DEC-2026-11-13-06` (6)（不下「不存在」結論）。

**P-B 共通規則**

1. 資料來源限定為 MoneyDJ 基本資料頁（`yp011000`／`yp011001`，host 為 `tcbbankfund.moneydj.com`、`www.moneydj.com`）。
2. 一次查詢只針對**一個**使用者輸入的 MoneyDJ 基金代碼；不寫入任何持久層；不加入選股池或任何清單。
3. 只有通過 MoneyDJ 身分判準（F9）的頁面，其欄位才可呈現。
4. 取數失敗、頁面無法確認、入口攔截，皆不得推論為「基金不存在」。
5. 本契約不核准（亦**不升格** R-ID-2／R-ID-3；Q2 若獲准，僅為路徑 B 專屬的內部鍵語意）：R-ID-2／R-ID-3 的全域身分語意、別名表、ISIN 解析、後綴碼語意（S7）、`ccy`、`fetched_at`、供應者名稱、Schema、資料接線。

| 欄 | 型別 | 值域／格式 | 缺值語意 | 狀態 | 來源追溯（契約層；**不進 view model、不上畫面**） |
|---|---|---|---|---|---|
| **輸入代碼** `input_code` | 字串或 None | 使用者輸入原值；僅在輸入為 ISIN 形、網址形、含可印刷 ASCII 以外字元、或長度超過 `INPUT_ECHO_MAX` 時為 None | 不適用 | 隨 `LookupState`；**不代表基金身分**（`T-ID1` 只限 Sheet「基金代號」欄，未涵蓋使用者輸入框，INFERENCE） | 使用者輸入框；無資料源 |
| **基金名稱** `fund_name` | 字串或缺值 | MoneyDJ「基金名稱」原字面；非空白、非佔位字（共用 `declared_profile.name_is_blank`） | 缺值＝標籤缺／空白／佔位；`RESULT` 狀態下必有值（名稱是身分綁定證據） | `VALUE`｜`MISSING`（僅在非 `RESULT` 時以狀態表達） | MoneyDJ「基金名稱」→ `declared_profile.fetch_moneydj_basic_fields` → `exp_profile._fund_name_cell` |
| **配息方式** `dividend_policy` | 列舉或缺值 | `accum`｜`dist`｜缺值 | 缺值＝標籤缺／表外寫法／空白／「—」／「不定期」；**缺值不等於不配息** | `VALUE`｜`MISSING` | MoneyDJ「配息頻率」→ `exp_profile.DIVIDEND_FREQ_TO_POLICY`（`docs/v2/49` §6.1，客戶 2026-09-26 定案） |
| **成立日期** `inception_on` | ISO 日期字串或缺值 | `YYYY-MM-DD`；無時區；年份 ≥ 1900 且不晚於台灣今天 | 缺值＝標籤缺／字樣認不出／日期不存在／過早／未來（皆不採用，原因不另外區分） | `VALUE`｜`MISSING` | MoneyDJ「成立日期」→ `exp_profile._check_inception`、`taiwan_today` |
| **經理費率** `mgmt_fee_rate_pct` | 浮點或缺值 | 單位百分點／年（44 §4.6）；**目前恆缺值** | 恆缺值＝本系統無此來源；**不得以「最高經理費」或 0 取代**；若 L2 回非缺值視為契約違反（fail-closed） | 恆 `MISSING`（附「契約上目前無來源」結構標記） | 無來源（`exp_profile.build_profiles` 寫死） |

**限制聲明（隨契約一併揭露）**：①配息頻率對照表左欄寫法「是推測的、沒有實測過」（`exp_profile.py` 註解轉述 `docs/v2/49`）；②MoneyDJ 頁面標籤自相矛盾與單純缺值目前無法區分；③資料可能來自行程內 1 小時成功快取，**畫面不顯示取得時間**（R-NAV-3 暫緩），使用者無法得知資料新舊——對名稱／成立日屬低風險，對配息方式屬較高風險（配息方式可能變動）；④MoneyDJ 頁面格式是否仍符合身分判準、部署端可達性皆 NOT VERIFIED。

### 8.2　接線授權包：客戶需裁示的逐項問題

> 每題附推薦與理由。**推薦非授權**。第 Q0 題為前置依賴，其餘題在 Q0 之後才有意義。

| 題 | 問題 | 推薦 | 理由 |
|---|---|---|---|
| **Q0** | **前置依賴**：路徑 B 的任何真實取數，是否確認須等 **A 線安全 Gate（BL-0551）通過**與客戶正式核准後才開始？「A 線安全 Gate 通過」的具體條件是什麼？ | 確認「須等」；並請客戶定義通過條件（repo 查無定義） | 路徑 B 一定會走 `infra.proxy.fetch_url`（MoneyDJ、FundClear 在 proxy 模式 `verify=False`），TDCC 走 urllib；BL-0551 對路徑 B 是實際生效的風險。**請求放大面（S8，併入 BL-0551 暴露面；單組讀碼，未實測）**：①每個不同的合格輸入，最多觸發 MoneyDJ **4 個網址**（2 頁型 `yp011000`／`yp011001` × 2 主機 `tcbbankfund.moneydj.com`／`www.moneydj.com`；每個網址以 `retries=1` 呼叫，單網址實際請求數未驗）＋FundClear 1 支＋TDCC（整份清單，行程內快取後僅本地比對）；②快取：三支成功快取各 `maxsize=256`、TTL 3600 秒，超過 256 個不同代碼會逐出舊項（淘汰依據見 F9 第 9 項：讀碼為依寫入時間，非存取；NOT VERIFIED）；失敗記憶 300 秒、無容量上限的 dict；③使用者可任意輸入合格形狀的代碼，**現行設計沒有速率限制**，`ui_v3` 與 adapter 草案皆未含；④快取與失敗記憶行程內共用，一位使用者的大量不同輸入會擠掉他人的快取、並可能使他人在 5 分鐘內對同代碼看到冷卻中的失敗（INFERENCE：由失敗記憶行程內共用、鍵為函式名＋代碼推得，未實測）。是否要在 A 線安全 Gate 內要求入口速率限制或單次查詢上限，屬客戶裁示 |
| Q1 | 是否核准 8.1 的路徑 B 五欄契約文字（或指示修改）？ | 核准（可修改）後才進入接線；僅核准契約文字、不連帶核准 R-ID-2／3 | 目前五欄皆無已核准契約（第 0 結論 1）；沒有契約的接線是無依據的資料語意 |
| Q2 | 路徑 B 的最小內部鍵語意：同意「內部取數鍵＝使用者輸入以 `strip(' ')` 後的大寫形；`ok`＝格式通過；兩者皆不顯示、不代表基金存在、不寫入持久層」？**本題的核准範圍是路徑 B 專屬，不升格 R-ID-2／R-ID-3**（兩者全域身分語意維持 Pending，不得被引用為已核准） | 同意（路徑 B 專屬；不升格 R-ID-2／R-ID-3） | 第 2.2 節；不動用 ISIN resolver，不冒稱 R-ID-1；與 P-B 共通規則 5、Q1 一致，消除「核准內部鍵語意」與「不核准 R-ID-2／3」的字面矛盾 |
| Q3 | 別名表與後綴碼：①是否同意路徑 B **關閉別名表**（`mapping={}`）？②後綴碼是否入口放行（視為不透明字串）？ | ①同意；②放行（若客戶偏好保守，可改為入口攔截並待 S7 裁示後再開） | ①避免「輸入 A 顯示 B」；②不替未裁的 S7 下結論，且攔截會擋掉可能合法的輸入 |
| Q4 | 來源範圍：O1（沿用三來源，不改 L2）還是 O2（新增 L2 單來源建構函式，需新 DEC 與獨立稽核）？ | 長期 O2；若要最快驗證且接受三來源揭露（第 3.2 節兩句）與 BL-0551 暴露面，先 O1；不採 O3 | O2 暴露面最小；O1 零 L2 改動；O3 需捏造來源狀態 |
| Q5 | 缺值符號與字樣：路徑 B 獨立入口接真實值，缺值格如何呈現？配息方式 `accum`／`dist` 的畫面用語、費率欄「契約上目前無來源」的字樣如何定？**緊張關係須先明列**：`DEC-2026-11-13-06` (6) 要求依證據分 `◇`（確實屬資料未提供或未建立來源）／`⛔`（上游取得失敗）／`⬜`（無法確認），並明文「**不得把所有空結果一律轉為 `◇`**」；而 view model 的 `MISSING` 底下混有多種原因（標籤缺、表外寫法、「不定期」、成立日過早或未來、頁面標籤矛盾——見 U3／U4），目前 L2 只給自由文字、無機器可讀原因碼，adapter 不得解析文字，故**目前無法細分子原因**。<br>**① 現有客戶指示**：缺值字樣「`◇ 資料未備`」已登記於 **`DEC-2026-11-18-01` C(5)（待合併；本工作樹的 `docs/DECISIONS.md` 查無此編號，NOT VERIFIED；經對話提示語轉達自稱客戶，待核）**——這是客戶指示，不是執行組創作。<br>**Q5-alt（稽核提出的保守替代，供客戶選擇）**：僅費率欄（設計上無來源）用 `◇ 資料未備`，其餘 `MISSING` 在第一切片用 `⬜ 無法判定`，待 L2 輸出機器可讀原因碼後再細分。代價：把「缺值」併入「無法判定」，與 poc 預覽把兩者分開呈現（G-3）不同。 | **不由作者選定**：請客戶裁示 ① 或 Q5-alt。兩者並陳——①：遵循已登記的客戶指示、畫面一致，但在 L2 有原因碼之前，所有缺值子原因都顯示 `◇`，與 (6)「不得一律 `◇`」有未解的緊張，不得單方宣稱無牴觸；Q5-alt：不與 (6) 牴觸，但偏離已登記的字樣指示。無論選哪個，費率欄與一般缺值**要能區分** | (6) 是已核准的方向裁示，不能被「一律 `◇`」悄悄架空；客戶指示（①）同樣不能被執行組單方改寫；兩者衝突的取捨權在客戶。`DEC-2026-11-17-03` G-3 只裁了離線 FAKE Preview 用 `⬜`；字樣核准不等於細分規則核准 |
| Q6 | 入口規則：同意第 4.3 節的攔截（含網址形一律攔、ISIN 形用結構判斷不驗檢查碼）？是否允許「貼上 MoneyDJ 網址」作為便利輸入？ | 同意攔截；**不允許貼網址** | 網址可夾帶 token，且 `fund_keys` 會丟棄 host／path 只留 `a=`，使用者看不出系統用了什麼；ISIN 結構判斷避免「錯誤 ISIN」意外通過；另請設計者／客戶確認規則 4 是否先移除空格與 `-`（推薦：是，見 4.3 說明）與 `INPUT_ECHO_MAX` 數值 |
| Q7 | frozen 44 `EXP-6` 的「查無此 fund_code」字面與 `DEC-2026-11-13-06` (6) 的「不顯示查無／不存在」並存且尚未處置：路徑 B 是否明確為**獨立功能、不是 `EXP-6`**，`EXP-6` 維持〔待定〕？ | 是；`EXP-6` 維持待定 | 避免在路徑 B 中悄悄採用被裁示禁止的字面；是否需要 amendment 另案處理 |
| Q8 | 資料新舊：畫面不顯示取得時間（R-NAV-3 暫緩），但資料可能來自行程內 1 小時快取；是否接受第一個切片不顯示時間，並在契約限制聲明揭露？ | 接受（第一切片）；日後 R-NAV-3 核准後再顯示 | 名稱、成立日變動極少；配息方式風險較高，故須揭露 |
| Q9 | 資料保存：確認路徑 B 不寫任何持久層（含 `user_setting`、Sheet、檔案），僅行程內快取與失敗記憶？ | 確認 | 只讀、可回滾（`git revert`，無資料回滾） |
| Q10 | 部署前置事實由誰、用什麼方式確認：NAS proxy 在線、`PROXY_URL` 已設定、MoneyDJ 在目標部署端可達、頁面格式仍符合身分判準？ | 由客戶或部署端持有人在 A 線安全 Gate 內確認；任何探測需另行授權 | 本批不探查 secrets、不發請求；全部 NOT VERIFIED |
| Q11 | 驗收門檻：涉 identity 邊界與 data semantics → 至少 1 組真正獨立 QA（`DEC-2026-10-16-05` 分級）；是否另要求 Cloud／真機驗收？ | 至少 1 組獨立 QA；Cloud／真機另列 NOT VERIFIED，不宣稱已驗 | 與卡片 4-E 一致 |

### 8.3　施工前應完成的順序（RECOMMENDATION，非授權）

1. 客戶回覆 Q0、Q1、Q2、Q3、Q4（資料與範圍類）；Q5、Q6、Q7（UI 與字樣類）可與設計者並行。
2. 契約文字核准（Q1）與必要的 L2 新契約（若選 O2）取得 DEC。
3. A 線安全 Gate 通過與客戶正式核准真實取數。
4. 內部切片（第 6、7 節）：先施工 view model、adapter 與注入測試（無真實取數），經獨立 QA。
5. 最後才做資料接線與（若獲准）獨立入口；每一步各有獨立授權。

---

## 9　未決與 NOT VERIFIED

### 9.1　未決

| # | 未決 | 影響 |
|---|---|---|
| U1 | 五欄契約文字未核准（Q1）；K15 仍 Pending | 接線無依據 |
| U2 | R-ID-2／R-ID-3 身分語意 Pending；S7（後綴）未裁 | 內部鍵語意只是本檔建議 |
| U3 | 欄位級「分歧」在現行 L2 形狀下無法由機器辨識（缺值與分歧不可區分） | 若要區分，需 L2 輸出機器可讀原因碼，屬新契約 |
| U4 | 成立日期不採用的三種原因（認不出／過早／未來）在 view model 不可區分 | 同上 |
| U5 | 路徑 B 與 frozen 44 `EXP-6` 的關係（前置、替代或另一功能）未定；`EXP-6` 的「查無此 fund_code」未處置 | 見 Q7 |
| U6 | 缺值符號（`◇`／`⬜`）與全部新字樣未核准 | 字樣一律 `PendingWording` |
| U7 | 配息頻率對照表左欄寫法為推測、未以真實樣本全面驗證 | 配息方式可能大量落在「表外」缺值 |
| U8 | `INPUT_ECHO_MAX` 的數值（建議 64）與 renderer 顯示時是否再截斷 | view model 的上限已定為結構性設計（S5）；數值待設計者確認 |
| U9 | 12 字元且前 2 碼字母、末碼數字的真實 MoneyDJ 代碼是否存在；以及帶 `-` 後綴、移除所有非英數字元後恰為 ISIN 形的真實代碼是否存在（規則 4 的誤攔面，見 4.3）；含 `http` 子字串的合法代碼（規則 3） | 見 4.3 |
| U10 | 「A 線安全 Gate 通過」的定義 | 見 Q0 |

### 9.2　NOT VERIFIED

1. 本檔全部內容為單組作者研究，**未經獨立 QA**；全稱句與「查無」類結論為單組讀碼或字面搜尋，非窮舉；動態組出的呼叫、未列檔案可能漏看。
2. **未執行任何對外請求**；未讀取真實 Google Sheet 或 secrets；MoneyDJ、TDCC、FundClear 的可達性、NAS proxy 狀態、TLS 實際行為、MoneyDJ 頁面目前格式皆未驗。第 1 節 `K15` 等 D2 候選檔結論來自讀檔，未重驗其與其他治理文件的同步狀態。
3. 唯一實跑為第 4.1 節的 `resolve_full_keys` 離線呼叫（本機 Python 直譯器、`mapping={}`、無網路），其餘皆為讀碼。測試計畫（第 7 節）的可行性（尤其 T-G 差分與離線黃金樣本）僅讀碼判斷，**未實作驗證**。
4. 既有 `ui_v3` 守衛中是否有其他需同步登記新檔的規則（頁面登錄表、no-engineering-leak、wording fidelity 等）未逐一核對。
5. 上游卡片 `DEC-2026-11-17-03`～`-06` 的稽核沿革以 `docs/DECISIONS.md` 現文為準，本組未重驗各輪稽核內容。
6. 客戶限縮授權（路徑 B 優先、路徑 A 暫緩、不授權真實取數）來自對話提示語轉達，**待核**；repo 無逐字存檔。
7. 本檔所有推薦為作者建議，**非授權、非客戶裁示**；登記不構成動工授權。

---

## 〈需客戶裁示的衝突〉（彙整）

| # | 衝突 | 兩邊 | 建議處置（非授權） |
|---|---|---|---|
| X1 | frozen 44 `EXP-6`「整檔查無→來源缺，文案『查無此 `fund_code`』」 vs `DEC-2026-11-13-06` (6)「New UI2 不顯示『查無基金』『不存在』」 | 44 原文（待定，未處置）／客戶裁示（方向） | 路徑 B 明定為獨立功能、不採用 `EXP-6` 字面；`EXP-6` 維持待定（Q7）。是否需要 amendment 另案 |
| X2 | 44 §4.6 `fund_profile` 多數欄「可空：否」 vs 2026-10-13「缺欄照列」裁示 vs 路徑 B 費率恆缺值 | 表文／客戶裁示／實作現況 | 路徑 B 以客戶裁示為準（缺值照列），費率欄另加「契約上目前無來源」標記（Q5） |
| X3 | 卡片 §4-B2 稱配息方式「D2 候選表查無專屬列」 vs 本組發現 `dividend_policy` 出現在 Returns 域第 14 列（配息閘門輸入，Optional／Pending） | 卡片／本組核對 | 結論（無顯示用契約）不變；卡片文字建議更正（本批不改該檔） |
| X4 | `T-ID1`（R-ID-1）只限 Sheet「基金代號」欄、未涵蓋使用者輸入框（推論） vs 路徑 B 必須使用使用者輸入代碼 | 已核准契約／功能需求 | 以 Q1／Q2 核准路徑 B 專屬的最小鍵語意，**不擴張 R-ID-1，也不升格 R-ID-2／R-ID-3** |
| X5 | 別名表命中時「輸入 A、取 B 頁」 vs R-ID-2 Pending（D2-C＝B：別名不升格） | 現行預設行為／D2-C＝B | 路徑 B 關閉別名表（Q3） |
