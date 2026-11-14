# D2 下一批三列核可包：R-NAV-2 `nav_date`／R-NAV-5 `ccy`／R-NAV-3 `fetched_at`（2026-11-14）

> **基準**：main `ede93f6fe9330deecd429c824422fcd975d7625b`（#1246 merge；其 push CI 作者撰寫時尚未完成，**以 GitHub 為準**）。docs-only。**盤點讀碼的實際樹為 `3e25cc81`（#1246 head）**；與 `ede93f6f` 的差異僅 #1246 的 4 個 docs 檔（作者推論，未逐檔 diff 核對）。
> **性質**：**只準備核可證據，不核可、不升格為正式 Schema、不接線**。契約文字皆**草稿，不具效力**；任何一列都須客戶逐列明示核可（`DEC-2026-11-13-06` 同款：契約文字核准 ≠ 接線授權）。不改 Schema、FX、DG2、公式、資料來源、`ui_v2`、`ui_v3`；BL-0545 BLOCKED。本批沿用範本包 `docs/evidence/d2_min_approval_pack_r_id_1_r_nav_1_2026_11_13.md` 的結構（該包自述基準 `6dcb51f8`，與現在基準的差異本稿未比對）。
> **事實來源**：2026-11-14 一份唯讀盤點（subagent，單組，**只讀函式名、未跑任何測試、未查 CI**）。作者另抽查四個承重點：`services/v2_tables/contract.py::NAV_FIELDS` 存在；`nav_dividend.py` 的 `CHAIN_DECLARED_CCY_ATTR`（「不當標籤，只拿來比對」）、`MIN_VALID_DATE = date(1900, 1, 1)`、`FETCHED_AT_MAX_FUTURE_SEC = 300`、`NAV_HISTORY_PROVENANCE_VERIFIED = False`。**其餘為單組讀碼，全稱句未經第二組驗證。**
> **品質狀態**：單組作者草稿，**尚待非作者獨立 QA**（data semantics 等級，依 `DEC-2026-10-16-05`）。〔事〕＝讀碼可核；〔推〕＝推論；〔Gate〕＝需客戶裁示。檔案引用為「檔案::符號」，不寫行號。

---

## 一、結論先講

| 項目 | 內容 |
|---|---|
| 現況 | 17 列中 2 列已核准契約文字（R-ID-1、R-NAV-1，`DEC-2026-11-13-06`，要點轉述，尚待獨立 QA）；其餘 15 列 Pending |
| 本批建議 | R-NAV-2 → R-NAV-5（可同場）→ R-NAV-3（可延到下一批，不阻擋前兩列）〔推〕 |
| 順序理由 | R-NAV-1 的契約文字已寫「計價幣別以同列 `ccy` 為準」，且 `ccy`、`nav_date`、`fetched_at` 契約「另案」；前兩列是它的直接前置，也是 UI 實際最依賴的欄。R-NAV-3 UI 依賴最低，但 `T-NAV1` 第 5 點與 D2-B 都點名它 |
| 與 ui_v3 的關係 | 〔事，單組〕`ui_v3/` 對 `nav_date`／`nav_orig_ccy` 無命中；`assets_source.py` 市值基準一律 `blocked`、不建 nav 表。**ui_v3 目前沒有消費 NAV 表**，所以核可這三列**不改變任何現有 ui_v3 行為**；它們的 consumer 在 `ui_v2` 與 L2 |
| 不碰 | R-NAV-4、R-NAV-6、R-ID-2／3、R-PERF-1～8、`dividend`／`fund_profile` 同名欄（理由見 §五） |

---

## 二、三列共同的 NAV 生產鏈〔事，單組〕

- 欄位契約：`services/v2_tables/contract.py::NAV_FIELDS` 共 7 欄：`fund_code`、`nav_date`、`nav_orig_ccy`、`ccy`、`source_tier`、`is_estimated`、`fetched_at`。寫列：`nav_dividend.py::_rows_from_segment`，寫入前過 `contract.nav_row_problems`。
- 生產路徑：`build_nav_table` → `_build_tables` → `fetch_nav_chain_with_error` → `_nav_from_chain`。`_nav_from_chain` 把序列 attrs 的 `currency` 剔除，序列自報幣別改存 `CHAIN_DECLARED_CCY_ATTR`，**只用來比對、不當標籤**。
- 兩條入口，同一次呼叫混用會 `ValueError`（`nav_dividend.py::_group_funds`）：💼 持倉／配置（Sheet「幣別」欄 → `holding_ccy`）；🔍 找基金（`declared_ccy`＋`declared_ccy_source`，meta 自報）。

---

## 三、逐列證據

### 3.1 R-NAV-2 `nav_date`

| 面向 | 內容 |
|---|---|
| 來源 | 來源序列索引，經 `nav_dividend.py::_date_value`／`_dated` 過濾，寫成 YYYY-MM-DD 字串。只收：無時區 `pd.Timestamp`、`datetime.date`、恰為 YYYY-MM-DD 的字串；帶時區、`datetime`、NaT、整數索引一律不收。早於 `MIN_VALID_DATE`（1900-01-01）或晚於 `MARKET_DATE_TZ`（UTC+8）當日者不寫 |
| 缺值語意 | 該筆不寫；原因只進 `skipped` **自由文字，沒有封閉原因碼**。週末假日無列，不 ffill、不補 0（44 §4.2）。同日同值併一列；同日不同值或同日有無效值，該日全不寫 |
| 日期語意 | 44 §4.2：「這筆淨值對應的日期」。程式不轉時區，**不判斷各 provider 的 `nav_date` 是估值日、交易日還是公布日**（NOT VERIFIED） |
| Consumer | L2：`services/v2_domain/holdings.py::latest_nav_row`（取 `max(nav_date)`）、`basis_value_with_reason`（以 `nav_date` 對齊 FX：`obs_date <= nav_date` 最近一列）、`allocation_evidence.py`（`NavFact`）。`ui_v2`：`hld/live.py`（N＝台灣今天減最後一筆；`> NAV_NOT_READY_DAYS`＝10 → 資料未備）、`hld/logic.py`、`hld/page.py`、`alo/live.py`、`alo/logic.py`、`exp/live.py::nav_is_old`、`exp/logic.py`。ui_v3：無 |
| 風險 | (1)「資料日」與「取得時間」不可混用（`alo/live.py` 註解明寫用列本身 `nav_date`，不用 `fetched_at`）；(2) 舊站純量 `nav_date` 與序列末日不同源、無 reconcile（G-NAV-6，引 `docs/v2/69`，本稿沒重驗）；(3) 契約若順帶寫 10 日規則會違反 `DEC-2026-11-05-03`（不得升格為全頁正式規則，其待決 (a)～(e) 未裁）；(4) PIT 取哪個日期欄未定；(5) `ui_v2/alo` 會以**整檔為單位**剔除未就緒的基金（`alo/live.py` 的 `not_fresh` 為 fund_code 集合），並另有最新淨值日距今超過 `max_age_days` 的剔除，故 alo 看到的 `nav_date` 集合比表本身小（本稿採 QA 的讀法，單組讀碼） |
| 已知落差 | 候選檔寫「與 D2-B 衝突」；`DEC-2026-11-13-06` Q0＝A（D2-B 僅約束 1Y 含息證據與四項同源條件，不擴張為 NAV 全域契約）後，不再構成阻擋，但此列仍 Pending |
| 測試證據（只讀函式名，未跑） | `test_nav_索引帶時區_不猜日期`、`test_必修1_非日期索引一律不寫_理由寫明`、`test_必修1_三種合格日期都收`、`test_3_nav_date未來或1900以前不寫_台灣當日照收`、`test_nav_同一日期同值只寫一列_不同值該日全不寫`（`tests/test_v2_tables_nav_dividend.py`） |

**契約文字草稿 T-NAV2（不具效力）**：
1. 型別：日期，YYYY-MM-DD 字串，不可空。語意：該列 `nav_orig_ccy` 所對應的日期，取自來源序列索引，原樣，不平移、不換時區、不補列。
2. 只收：無時區 Timestamp、`date`、恰為 YYYY-MM-DD 的字串；帶時區、`datetime`、NaT、非日期型別不寫。另有合理日期範圍過濾——**以下僅描述寫入端現行實作事實，不是正式門檻**：下限現為程式常數 `MIN_VALID_DATE`（1900-01-01），上限現為寫入當下的台灣日期。「今天」是否定義為台灣日期、未來日期 NAV 的正式語意，屬 `DEC-2026-11-05-03` (a)(c)，**未裁，不在本核准內**。
3. 與 `fund_code` 為主鍵；同日同值併一列；同日不同值或同日有無效值，該日全不寫。
4. 週末、假日、停止交易日沒有列；不 ffill、不補 0。
5. 缺值：該筆不寫；原因目前只在旁路自由文字，**無封閉碼**。呈現文案與狀態字彙**不在本核准內**（程式註解明寫「文案未定」；狀態字彙歸 D3）。
6. **不含**：新鮮度與 10 日規則、「今天」的定義與未來日期 NAV 的正式語意（`DEC-2026-11-05-03` (a)(c)）、PIT 取欄、FX 對齊規則、各 provider 日期語意（估值日／交易日／公布日）。1Y 的 `as_of`（R-PERF-6）不因此核准。

### 3.2 R-NAV-5 `ccy`

| 面向 | 內容 |
|---|---|
| 來源 | 持倉入口：Sheet「幣別」欄 → `holding_ccy` → `nav_dividend.py::resolve_nav_ccy`；🔍 入口：`exp_nav` 的 `declared_ccy`／`declared_ccy_source`。回傳 `(ccy, ccy_source, withheld, reason)`；`ccy_source` 取值 `holding_user_input`、`source_reported`、`meta:<來源>` |
| 缺值語意 | 缺或不合形狀 → `withheld=ccy_missing`，整檔 NAV 不寫；多值意思不同 → `ccy_conflict`，整檔不寫；序列宣告與標籤不同 → `_chain_ccy_gate` 整檔不寫；非原生報價來源未宣告（`fund_orchestration._NAV_NON_NATIVE_PREFIXES`）→ 整檔不寫（`ccy_missing`）；🔍 幣別未確定 → `exp_nav.py::WITHHELD_CCY_UNDETERMINED` 該檔不取數 |
| 幣別語意 | 44 §4.2 只寫「ISO 4217、計價幣別」。**程式只檢查三個 ASCII 大寫字母**（`contract.py::_is_iso_4217`、`nav_dividend.py::_iso_ccy`），**沒有 ISO 4217 清單成員檢查**；衝突比對是字串比對（`_ccy_meaning` 去空白、大寫化後比） |
| Consumer | L2：`holdings.py::basis_value_with_reason`（`nav["ccy"] == "TWD"` 不乘匯率，否則 `fx_key_of(nav["ccy"])` 再 `fx_rate_as_of`）、`aggregate_holding_rows`（同鍵 `ccy` 不同 → `HoldingKeyConflict`）、`allocation_evidence.py`（`NavFact` 比對 `holding["ccy"]`）。`ui_v2`：`alo/live.py::fx_ccys_needed`、`alo/logic.py`、`hld/page.py`（HLD-6）、`exp/live.py`（規則 14：淨值 ccy 與 profile 自報不同 → ⬜）、`exp/logic.py::format_nav`。ui_v3：無 |
| 風險 | (1) 同一欄兩種出處語意（持倉手填 vs meta 自報）；`ccy_source` 與 `provenance.source`、`source_tier`、績效 `source` 是不同概念，**不可合併**；(2) **持倉手填標籤沒有獨立證明**：原生報價來源且序列未宣告時直接採手填，只能排除「已宣告的衝突」；(3) **錯的 `ccy` 會直接進 alo 的 FX 乘法**；(4) FX 閘門關（`FX_OBS_DATE_RULE_VERIFIED = False`），匯率鍵方向未逐 provider 驗證；(5) `quality_batch1_delta` Δ3-03：消費端無匯率新鮮度上限、不讀 `value_unit` |
| 已知落差 | (1) 候選契約寫「ISO 4217」，程式只做形狀檢查；(2)〔推，單組〕`ccy_source=source_reported` 在 `build_nav_table` 的 A 鏈路徑上因 `currency` 被剔除而不會出現，直接呼叫 `rows_from_nav_series` 才會——**契約若寫「序列自報幣別優先於手填」會與生產路徑不符**；(3) `EXCEPTIONS.md` 登記 `P-CNHALIAS-1`、`P-ALIASSHAPE-1`（本稿只確認存在，未讀內容）；真實 Sheet 幣別值分布 NOT VERIFIED（BL-0545 BLOCKED） |
| 測試證據（只讀函式名，未跑） | `test_nav_幣別缺_整批不寫_不猜不預設USD`、`test_nav_持倉幣別不合ISO4217_不改大小寫_整批不寫`、`test_nav_來源自報幣別優先記出處_與持倉相同照寫`、`test_nav_同一檔多列持倉幣別互相不同_整批不寫` |

**契約文字草稿 T-NAV5（不具效力）**：
1. 型別：字串，不可空，三個 ASCII 大寫英文字母（**形狀檢查，非 ISO 4217 清單成員檢查**）。語意：與同列 `nav_orig_ccy` 配對的計價幣別標籤。
2. 標籤出處依入口，不混用：持倉入口＝Sheet 持倉列「幣別」欄手填；🔍 入口＝基本資料頁自報。A 鏈序列自報的幣別不當標籤，只用於比對。
3. 缺或不合形狀 → 整檔 NAV 不寫（`ccy_missing`；多個值意思相同〔去空白、大寫化後相同，例 `usd` 與 `USD` 並存〕時取合格的那一個，僅有不合形狀值而無合格值時才不寫）；標籤之間或與序列宣告意思不同（去空白、大寫化後比）→ 整檔不寫（`ccy_conflict`）；非原生報價來源未宣告 → 整檔不寫。不預設 USD、不改大小寫、不猜、不換算。
4. **不證明**：手填標籤並未獨立證明數值確實以該幣別計價，只排除已宣告的衝突。
5. **不含**：TWD 換算、匯率方向、FX 閘門、share class／配息型／避險型態、`ccy_source`（R-NAV-6）、`dividend` 與 `fund_profile` 的 `ccy`。R-PERF-3 不因此核准。

### 3.3 R-NAV-3 `fetched_at`

| 面向 | 內容 |
|---|---|
| 來源與語意 | 列欄一律為 UTC ISO（`+00:00`）；`_fetched_at_check` 缺、無時區、格式不符 → 該段整批不寫。取值依分支：(a) 序列自帶 `attrs["fetched_at"]`；(b) 否則 A 鏈 `chain_started_at`（標 `orchestrator`；命中快取時是原本那一次）；(c) 預存檔 → `cache_updated_at`；(d) 累積表點 → 各點 `recorded_at`（`NAV_HISTORY_PROVENANCE_VERIFIED=False` 時為 0 列） |
| 缺值語意 | 晚於當下超過 `FETCHED_AT_MAX_FUTURE_SEC`（300 秒）→ `fetched_at_in_future`；缺或無時區 → `fetched_at_missing`。**封閉碼，不以當下時間補** |
| Consumer | `ui_v2/set/logic.py`（`max(r["fetched_at"])`，設定與診斷頁「最近取得」）；`ui_v2/exp/live.py` tooltip 讀旁路 `prov["fetched_at"]`（不是表列欄）。hld、alo 不讀 nav 列的 `fetched_at`（`quality_batch1_delta` §3.1-A 同）。ui_v3：無（其 `fetched_at` 命中全屬市場指標） |
| 風險 | (1) 同欄三種語意（本次取得／orchestrator 起點／GitHub Actions 寫入快取時間），列內不標分支，只有旁路可辨；(2) 300 秒是程式常數，是否為正式門檻 NOT VERIFIED；(3) `stale_after` 未裁（D3(b)、`docs/v2/67` §8.5）；(4) D2-B 明文：不以讀取時間冒充 `fetched_at`；(5) **不是資料日，不得拿來判新舊** |
| 已知落差 | 範本包 §4.3 建議預存退回取 `cache_updated_at` 的語意與新鮮度綁在一起、等 D3(b)；該建議本稿未重驗 |
| 測試證據（只讀函式名，未跑） | `test_nav_fetched_at換成世界協調時間_同一瞬間_一律加00冒號00形式`、`test_nav_fetched_at取不到或沒有時區_整批不寫_不以當下時間補`、`test_nav_預存舊序列_fetched_at改取cache_updated_at_stale照記`、`test_3_fetched_at晚於當下_整批不寫_代碼與理由正確`、`test_小修1_nav即時那一支_fetched_at未來容差` |

**契約文字草稿 T-NAV3（不具效力）**：
1. 型別：時間，UTC，`+00:00` 形式，不可空。語意：該列所屬那一段序列的取得時間；**不是資料日、不是畫面 render 時間**。
2. 取值依分支：序列自帶；否則 A 鏈本輪起始時間；預存檔取 `cache_updated_at`；累積表點取 `recorded_at`。列內不標分支，分支只在旁路 provenance。**累積表分支目前受 `NAV_HISTORY_PROVENANCE_VERIFIED=False` 關閘、不產生列，其出處語意不在本核准內。**
3. 缺、無時區、格式不符 → 該段不寫；晚於當下超過一個容差者不寫（容差現為程式常數 `FETCHED_AT_MAX_FUTURE_SEC`＝300 秒，**僅為實作事實，是否為正式門檻不在本核准內**）。不以當下時間補。
4. **不含**：新鮮度、`stale_after`、300 秒是否為正式門檻、10 日規則。

---

## 四、AI 總管推薦與請示（逐列；客戶可推翻，亦可只裁其中一列）

**AI 總管推薦（先講）：R-NAV-2 選 A；R-NAV-5 選 A（如實標明限制）；R-NAV-3 延到下一批（選 B 的「暫緩」）。** 理由：前兩列貼合 44 §4.2 且不寫新鮮度，不與 `DEC-2026-11-05-03` 衝突；R-NAV-3 UI 依賴最低、且依賴 D3(b)。此為作者推論。

| 列 | 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|---|
| R-NAV-2 | A　核准 T-NAV2 | 如上，不寫新鮮度 | 補完 T-ID1／T-NAV1 的主鍵與日期語意；UI 依賴最高 | 原因碼仍無封閉碼；各 provider 日期語意未驗 | 低 |
| | B　暫不核准 | 待 `DEC-2026-11-05-03` 與 D3(b) | 一次裁完新鮮度 | 拖延前置 | 低 |
| | C　核准但附「各 provider 日期語意未驗」 | 同 A＋限制附註 | 揭露更完整 | 契約文字變長 | 低 |
| R-NAV-5 | A　核准 T-NAV5 | 如實標明形狀檢查與手填標籤的限制 | 不假裝有獨立證明 | 讓錯標籤可進 alo 的 FX 乘法（契約不碰換算，但後果在 consumer） | 中 |
| | B　暫不核准 | 待有獨立幣別證明 | 不固化弱證明 | 無日程；BL-0545 BLOCKED 下短期無法驗 | 低 |
| | C　核准並把 `ccy_source` 兩個出處語意寫成本列附註 | 不獨立核可 R-NAV-6 | 少一列待審 | 附註即新語意，須獨立 QA | 中 |
| R-NAV-3 | A　核准 T-NAV3 | 如上 | 把「取得時間≠資料日」寫死 | UI 依賴最低；三種分支語意列內不可辨 | 低 |
| | B　暫不核准，待 D3(b) | 範本包 §4.3 的建議 | 不綁新鮮度 | 延後 | 低 |
| | C　只核准「取得時間≠資料日」兩句 | 分支語意另案 | 最小 | 契約不完整 | 低 |

---

## 五、本批不碰的列與理由

| 列 | 理由 |
|---|---|
| R-NAV-6 `ccy_source` | 旁路欄位、`ui_v2` 三頁不渲染、是否進契約欄未定；客戶可選擇把它當 R-NAV-5 的一句附註（上表 C），沒明示維持 Pending |
| R-NAV-4 `source_tier`／供應者 | 混了「有值域的 `source_tier`」與「無規則的供應者名」，須先拆分（客戶決定）；「三種 source 不可合併」是新語意，另案 |
| R-ID-2／R-ID-3 | S7（後綴）未裁，identity 屬 Stop Gate；DG2 Shadow 關閉 |
| R-PERF-1～8 | 1Y 含息只在舊站（範本包附錄 A-9）；BL-0427 公式未裁；R-PERF-3／6 分別與 R-NAV-5／2 重複（1Y 輸出無此二鍵），核可 R-NAV-2／5 **不連帶**核可 R-PERF-3／6；R-PERF-7／8 狀態字彙歸 D3 |
| `dividend`、`fund_profile` 同名欄 | D2-G3 延後之域 |
| 不碰的語意 | FX／TWD 換算、NAV 10 日規則、NAV 來源優先序、`NAV_HISTORY_PROVENANCE_VERIFIED`、ISIN、`full_key` 後綴、DG2 |

---

## 六、我沒有驗證的部分

1. 盤點基準 SHA 由盤點組讀 `.git/refs` 取得（當時為 `3e25cc81`），不是 #1246 merge；差異僅 docs。
2. 所有測試只讀函式名，未跑；CI 狀態未查。
3. 單組字面搜尋的全稱句，均未經第二組驗證：「ui_v3 對 `nav_date`／`nav_orig_ccy` 無命中」「hld／alo 不讀 nav 列 `fetched_at`」「`ccy_source` 在 `ui_v2` 三頁不被渲染」「`source_reported` 分支在生產路徑不出現」。
4. 各 provider 的 `nav_date`／`fetched_at` 實際語意與時區（`repositories/fund/*` 未讀）；真實 Sheet 幣別值分布（BL-0545 BLOCKED）；匯率鍵方向與 `value_unit`；Cloud、真機、live 可達性。
5. `docs/v2/44` 全檔、`docs/v2/67`、`69`、`70` 未通讀；`DEC-2026-10-28-05`、`DEC-2026-10-29-01／02` 逐字檔未開；`DEC-2026-11-13-06` 客戶原話無逐字存檔，T-ID1／T-NAV1 核准為要點轉述。
6. 本稿契約文字草稿為單組整理，**尚待非作者獨立 QA**；登記與準備 ≠ 核可 ≠ 接線授權。
