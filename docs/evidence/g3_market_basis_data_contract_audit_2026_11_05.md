# G-3 前置：💼 市值基準資料契約與 NAV／FX 歸屬稽核（唯讀）

| 項目 | 內容 |
|---|---|
| 範圍 | G-3 前置資料契約與 NAV／FX 歸屬稽核（為 BL-0542 的 💼 市值基準被擋原因做盤點） |
| 基準 | main `43b54f32` |
| 性質 | 純文件、唯讀稽核；無程式、無測試、無凍結 SSOT、無白名單變更 |
| 授權 | **本文件合併 ≠ 施工授權**；不新增任何 DEC、不新增 BL id、不改 HANDOFF |
| 來源 | 三組唯讀調查＋一組對抗式稽核。標 `[AUDITED]` 者經稽核核實；標 `[UNVERIFIED]` 者未經第二組驗證 |
| 標籤 | **FACT**（可由 repo 查證）／**INFERENCE**（推論）／**RECOMMENDATION**（總管可推翻的建議） |

## 1. 結論一頁

1. 💼 市值基準在 Preview 被擋，原因不只一種，而是**四類**：(a) 尚未施工、(b) 資料缺失或無法驗證、(c) 規則未驗證、(d) 未獲授權或正式禁止搬動。
2. 即使把 NAV 組裝移植完成，只要 `FX_OBS_DATE_RULE_VERIFIED` 仍為 False，所有非台幣持股仍會是 fx_absent。**移植組裝**與**開放 FX 閘門**是兩個互相獨立的決定。
3. NAV「10 日」規則只有一個字面值（`ui_v2/thresholds.py::NAV_NOT_READY_DAYS`），但**沒有專屬 DEC**；證據是轉述與 HTML 草稿。移動歸屬前，建議先登記專屬 DEC。
4. 授權鏈有一個治理缺口：G1-②／③／G-2 的 2026-11-05 授權只存在於 BL-0542／HANDOFF 的要點轉述，沒有對應的 DEC 條目。
5. Producer 目前沒有「未組裝」代碼；缺口若不補，市值基準無法在不偽造的前提下傳入。
6. 本文件不提議開放 FX 閘門，也不授權任何施工。

## 2. 市值基準資料血緣

| 步驟 | 程式位置 | 層 | ui_v3 可匯入？ | 純函式？ | 正式權威 |
|---|---|---|---|---|---|
| 持股＋政策 | `services/v2_tables/alo_holdings.py::load_alo_tables_active` | L2 | 是（函式內惰性匯入，同 🌍 先例） | 否（I/O） | 資料來源登記 |
| 使用者設定 | `services/v2_tables/settings_store.py::load_user_settings`、`load_market_indicator` | L2 | 同上 | 否 | 同上 |
| 執行期 FX 列 | `settings_store.session_runtime`、`merge_sheet_and_runtime_indicators` | L2 | 同上 | 否 | 同上 |
| 代碼對映 | `services/v2_tables/fund_keys.py::resolve_full_keys` | L2 | 同上 | 否 | 同上 |
| NAV 取數 | `services/v2_tables/nav_dividend.py::build_nav_table` | L2 | 同上 | 否（網路，A 鏈） | 資料來源鏈 |
| 非 USD FX | `services/v2_tables/market_indicator.py::build_fx_indicator_table` | L2 | 同上 | 否（受閘門控制） | 見第 6 節 |
| 基準值／缺值原因 | `services/v2_domain/holdings.py`：`basis_value_with_reason`、`category_values`、`fx_row_as_of`、`latest_nav_row` | Domain | 是 | 是 | 44 ALO-2／ALO-4 |
| 證據產生器 | `services/v2_domain/allocation_evidence.py::build_allocation_evidence` | Domain | 是 | 是 | G1-③（已合併） |
| **僅存於 ui_v2** | `ui_v2/alo/live.py::assemble_nav`（約 80 行；純；`today`、`max_age_days` 由外部注入；不碰 streamlit、不讀時鐘）`[AUDITED]` | ui_v2 | 否 | 是 | 無獨立裁示（總管沿用） |
| 僅存於 ui_v2 | `live.py::merge_fx_table`、`fx_ccys_needed`、`wants_market_value`（只定義於此）`[AUDITED]`、`skipped_for_dataset` | ui_v2 | 否 | 是 | 同上 |
| 僅存於 ui_v2 | `ui_v2/alo/source.py::_today_tw`：固定 UTC+8，取 `nav_dividend.MARKET_DATE_TZ`（該常數在 L2，ui_v3 可用） | ui_v2 | 否 | 否 | 台灣日期為草稿讀法 |
| 僅存於 ui_v2 | `ui_v2/alo/source.py` 的 composition root（含 streamlit） | ui_v2 | **不可搬** | 否 | — |
| 僅存於 ui_v2 | `ui_v2/alo/logic.py` 的中文缺值句 | ui_v2 | 屬 UI 字串，非 Domain | — | — |

**待定與缺席的區別**：`notes["fx_pending"]` 只存在於 ui_v2 的旁路 dict；producer（`allocation_evidence`）沒有對應輸入。因此「FX 還在等閘門」與「真的沒有 FX」在證據層無法區分。（FACT）

## 3. NAV 10 日規則（獨立一節）

**FACT `[AUDITED]`**

- 唯一字面值：`ui_v2/thresholds.py::NAV_NOT_READY_DAYS = 10`。
- 三個別名：alo `live.NAV_MAX_AGE_DAYS`、hld `live.NAV_FRESH_DAYS_YELLOW`、exp `NAV_OLD_DAYS`。
- 三處比較都是嚴格 `>`，所以**恰好 10 天仍被接受**。
- 「NAV 日期晚於今天」的處理不一致：hld 會 `raise ValueError`、exp 的 `nav_is_old` 會 raise；**alo 的 `assemble_nav` 沒有這道防線**。
- 鎖：`tests/test_v2_domain_port.py` 的單一擁有者 AST 測試；`tests/ui_v2/test_alo_live_logic.py` 三條測試；ui_v3 匯入隔離測試禁止 `assets_source.py` 出現 `NAV_NOT_READY` 字樣。
- 與其他規則的區別：不同於 `shared/signal_thresholds` 的 `MJ_FRESH_DAYS_*`（2／7 天，舊 UI，BL-0303）；不同於 BL-0369（🌍 新鮮度徽章，未決）。
- 兩種「不新鮮」不同：`too_old`（超過 10 天）只吃這個天數；alo 的 `not_fresh` 聯集（cache_fallback、stale、`is_estimated` 不為 False、too_old）中，其餘三項是實作習慣的 fail-closed（2026-10-13 稽核 N1），與 10 天無關。

**INFERENCE**：alo 若收到未來日期的 NAV，天數為負，永遠不會 too_old，被當成新鮮。這是潛在的語意缺口，**只登記、不修**。

**正式權威 `[AUDITED]`**：沒有專屬 DEC id。repo 內的證據都是轉述性質：

| 出處 | 性質 |
|---|---|
| `docs/handover_2026_09_26_latest.md` | 客戶 2026-10-13 裁示，經總管轉述為「原意、非逐字」 |
| `docs/wireframes/draft_hld_live.html` | 最接近逐字：2026-10-02「threshold 10 天、不放 44、依長假現實設定」，但引在 HTML 草稿內 |
| `docs/v2/44_fund_ui_ssot.md` | 只把它當既有規則引用，**ALO-2 並未定義 NAV 日期門檻** |

客戶明示核准的範圍是 hld；alo 採用是總管以「沿用」作的裁定；「今天＝台灣日期」是草稿的讀法。`DEC-2026-10-18-02`（BL-0375）涵蓋 hld／exp 的過期回退顯示，alo 是否有對應條目——搜尋範圍內未見 `[UNVERIFIED]`。

**RECOMMENDATION**：任何搬動之前，先登記專屬 DEC（頁面範圍、`>` 語意、台灣日期、未來日期處理），作為客戶 Decision Gate。

## 4. 市值基準語意權威表

| 語意 | 權威狀態 | 出處／備註 |
|---|---|---|
| FX 取 `obs_date <= nav_date` 的最近一筆 | 已核准、44 凍結（ALO-2） | `holdings.fx_row_as_of` 用 `<=` |
| FX 鍵用 NAV 幣別 | USD 鍵＝44；非 USD 鍵＝49 §6.1 Q9（2026-09-26 核准）；「以 `nav.ccy` 為準」是實作 | `nav.ccy` 只來自持股列或 meta；`holding.ccy` 與 `nav.ccy` 不一致＝開放 gate `holding_nav_ccy_disagreement_unjudged`，未裁 |
| 成本基準不碰 FX／NAV | 已核准（44） | — |
| FX 缺時不得退回成本基準 | 已核准（44 ALO-4） | — |
| 某類別缺基準值時顯示 ⬜，其他類別照常判定 | 客戶 2026-10-16（44 §7 轉述，無 DEC id） | — |
| 「一檔缺就整類別排除」 | 實作習慣，未找到明文裁示 | 44 的 ALO-GAP-同類別多理由 自述 44 沉默 |
| 類別缺值時的分母 | `DEC-2026-11-04-02` 方案 A：不得顯示誤導的完整 100% | ui_v2 `_build_alo2` 仍對剩餘類別顯示 100%，附「合計未涵蓋」註腳（部分緩解）；已登記為 `DEC-2026-11-04-03` 的已知缺口；`tests/ui_v2/test_alo_logic.py` 鎖住此行為 `[AUDITED]` |
| 同鍵合併 | hld 與 alo 刻意不同 | — |

## 5. Canonical 資料可得性矩陣

| Producer 需要的證據欄位 | 在 Canonical 列內？ | 位置／狀態 |
|---|---|---|
| NAV：`nav_date`、`ccy`、`fetched_at` | 是（`NAV_FIELDS`） | `fetched_at` 語意依路徑而異：live 為 L1 `fetched_at`；stored 為 `cache_updated_at`；累積為 `recorded_at` |
| NAV：`source_tier` | 是，但只有一個類別 | — |
| NAV：`cache_fallback`、`stale`、`live_error`、`ccy_source`、`latest_from` | **否** | 只在旁路 dict `provenance[fund_code]` |
| NAV：`is_estimated` | 是 | 僅讀到一個寫入點且恆為 False；全稱性 `[UNVERIFIED]` |
| stale／fallback／estimated／too_old 的持股 | **被刪** | `assemble_nav` 在進 Domain 前就從 nav 刪掉，原因只在 notes；Domain 只有在呼叫端傳入 `nav_provenance` 時才能區分 `not_provided` 與 `no_entry` |
| FX：`obs_date`、`release_date`、`fetched_at`、`is_revised` | 是 | 但 `release_date = obs_date`、`is_revised = False` 是**規定值**（客戶 Q3），`obs_date` 是推定的「前一個平日」（`OBS_DATE_PREV_WEEKDAY`） |
| FX：具體來源名 | **否** | 列內只有 `source_tier`（4 類）；具體來源只在 `INDICATOR_SPECS`／`fx_yahoo_ticker` 常數 → **逐列血緣無法重建** |
| 被選中的 FX 列與落後天數 | 可推導 | `FxFact.obs_date`、`candidate_obs_dates`、`NavFact.nav_date`；但只有開放 gate `fx_obs_date_lag_degradation_unjudged`，沒有「落後天數」欄位 |

## 6. `FX_OBS_DATE_RULE_VERIFIED`

**FACT `[AUDITED]`**

- 定義：`services/v2_tables/market_indicator.py`，值為 False。
- 讀取者：`build_fx_indicator_table`、`_phase1_of`、ui_v3 `assets_source` 的 lambda（每次載入現讀，回填到 `evidence.fx_rule_verified`）、`scripts/probe_fx_obs_date.py`（僅記錄）、測試。`allocation_evidence` 刻意不匯入它。
- 為 False 時：不抓非 USD、不產生列，`pending[key]=fx_obs_date_rule`（這是待定，不是錯誤）；USD 鍵走 phase1 `write_if_fx_verified` → pending，L2 不寫 USD 列。USD 列只可能已存在於設定表或執行期；真實 sheet 是否有——`[UNVERIFIED]`。
- **一個旗標管全部幣別**。程式註解寫明：單獨開放 USD 前須先加分幣別閘門；目前不存在。
- 開放條件（出自程式註解與 49 §8(i)／82 A10／BL-0217）：冬令時間偏移重跑探測（視窗約 2026-11-02～11-24，BL-0217；repo 內尚無重跑結果）、2026-10-14 日 K 數值的容差、小時 K 時間戳慣例、09-15～09-17 不一致的成因、假日對映，以及獨立稽核。
- 客戶 2026-10-14 裁示（轉述）：規則核准 ≠ 閘門核准；USD 須有後續佐證與獨立稽核才能顯示；EUR／JPY／CNY 維持「資料未備」，不估算、不替代、不自動切換來源。
- 沒有定義任何數值驗收測試。
- 探測產物：`docs/evidence/probe_fx_obs_date/*.json.gz`（3 份報告，2026-10-13～14）；workflow `fx_obs_date_probe.yml`（僅手動）。
- #1152 的稽核把此旗標視為「清理不得打開的資料有效性閘門」。**本文件不提議開放。**

## 7. 被擋原因分類（每項只歸一類）

| 阻擋項 | 類別 | 說明 |
|---|---|---|
| NAV 組裝移植 | 尚未施工（同時未授權：BL-0542） | — |
| NAV 10 日的歸屬搬動／注入來源 | **正式禁止（目前）** | `DEC-2026-11-04-03` 的「未授權」清單明列；另有單一擁有者鎖；解鎖＝新的客戶 Gate |
| 非 USD FX 列 | 規則未驗證 | 加上客戶 10-14「資料未備」 |
| USD FX 可得性 | 規則未驗證 | 同一閘門 |
| Producer 缺「未組裝」代碼 | 尚未施工 | 改 schema／詞彙須 Gate。後果 `[AUDITED]`：`nav_not_ready=None` 會被讀成「無過期持股」（對市值基準是偽造）；`tables['nav']=[]` 讀成「基金沒有 NAV」（與未組裝無法區分）；缺 `'nav'` 鍵 → `KeyError` → `holding_evaluation_error` → `valuation_completeness=failed`；留在 tables 的過期列會被 producer 當成有效，故 `assemble_nav` 必須先刪 |
| Preview 沒有登入／Active 入口 | 尚未施工 | 等 #1150／#1151 核准 |
| 真實 MoneyDJ／TDCC／FundClear／Yahoo／Google 鏈 | 資料缺失（本環境無憑證，真實連線從未驗過） | — |
| `NAV_HISTORY_PROVENANCE_VERIFIED=False` 的累積點 | 規則未驗證 | 客戶待決 |

## 8. 授權鏈弱點 `[AUDITED]`

- `DEC-2026-11-04-03` 只授權 G1-①；G1-②／③、PORT、NAV 10 日門檻、ui_v3、G-2～G-5 列為**未授權**。
- repo 內**沒有** `DEC-2026-11-05` 條目；2026-11-05 對 G1-②／③／G-2 的授權只存在於 BL-0542／HANDOFF 的要點轉述。
- **RECOMMENDATION**：請客戶確認並登記一則涵蓋 G1-②／③／G-2 的 DEC，再於其上繼續建構。這是治理缺口的回報，不阻擋本文件。

## 9. 已合併 G-2 轉接層的跨層債務 `[AUDITED]`

**(a) 設定解析鏡像**：轉接層的解析與 `ui_v2` 的 `parse_user_settings` 不只在 `OverflowError` 上不同——還有極大整數、亂結構容器（rows 非 mapping、`broken_keys` 型別錯：ui_v2 會當掉，轉接層標四個鍵無效）、轉接層忽略 `alo_scenario_input`（只處理四個證據鍵）、轉接層多一個 `broken_row` 狀態。`_skipped_holdings`／`_skipped_tabs` 鏡像 `skipped_for_dataset`，`basis_mode_of` 鏡像基準路由。差異測試（1500 組合）只覆蓋四個證據鍵。

**(b) 屬性鏈讀取**：轉接層讀 `alo_holdings.personal_session` 的 `.ec`（`AUTH_REQUIRED`、`UNAVAILABLE`、`ALL_ERROR_CODES`；另有 `REASON_NO_ACTIVE`），刻意繞過匯入守衛。轉接層 docstring 列了前三者但漏了 `REASON_NO_ACTIVE`（小不一致，之後修文件或註解）。`is_no_active` 與 `ui_v2/active_gate.py::is_no_active` 重複，僅靠測試維持相等。

| 債 | 選項 | 影響 |
|---|---|---|
| (a) | A1 提升為中立 `services/v2_domain/settings_parse.py`，兩邊共用 | 需在 `tests/ui_v2/test_ui_v2_live_import_guard.py` 的 `_V2_DOMAIN_ALLOWLIST` 加項，且須總管／客戶裁示是否統一 `OverflowError`／亂結構行為（會動 ui_v2 行為 → Gate） |
| (a) | A2 維持現狀、加強差異測試 | 零風險，債仍在 |
| (a) | A3 只讓 ui_v3 用新中立模組 | 兩套並存 |
| (b) | B1 在 L2 開一個小型公開函式（例如 `alo_holdings.is_no_active`／`classify_load_error`），轉接層不再碰屬性鏈 | 小；碰 `alo_holdings.py` |
| (b) | B2 放寬白名單 | 守衛變更＝Gate |
| (b) | B3 維持 | 零風險，債仍在 |

**RECOMMENDATION**：B1 → A1，兩者獨立；B1 小，A1 動 ui_v2 行為須 Gate。兩者都會碰 `services/v2_tables/alo_holdings.py`，而 PR #1154 也改該檔（匯入區與 masker）。**INFERENCE（僅讀 diff、未試合併）**：宜排在 #1154 合併之後，或讓 hunk 互不相鄰。

## 10. 讓 Preview 啟用市值基準的選項

| 選項 | 做法 | 正確性／語意風險 | Canonical／Domain／Evidence 契合 | 速度 | 長期維護 | token／執行成本 | 守衛影響 | 需要的 Gate |
|---|---|---|---|---|---|---|---|---|
| **A** 中立 PORT | 把 `assemble_nav`／`merge_fx_table`／`fx_ccys_needed`／`wants_market_value`／`skipped_for_dataset` 移到中立模組，`days` 與 `today` 作參數，ui_v2 變薄包裝（G1-② 風格） | 低（可用 byte-equal 差異／golden 鎖） | 最佳 | 中 | **最佳** | 中 | 需動單一擁有者鎖 | 是：10 日歸屬 |
| **B** 在 ui_v3 轉接層重寫 | 轉接層內自行實作＋差異測試 | 中（第三份規則密集邏輯） | 差 | 快 | 差 | 低 | 與 NAV 字樣鎖衝突 | 是 |
| **C** 維持被擋，只做成本基準 | 等線框核准 | 零 | 不變 | 即刻 | 不變 | 零 | 無 | 無 |
| **D** 只補 producer「未組裝」代碼 | 加 `not_assembled` 類代碼（＋ `fx_pending` 證據欄位） | 低 | 良 | 快 | 良 | 低 | 需 `SCHEMA_VERSION` bump＋mutation／golden | 是（schema／詞彙） |

**RECOMMENDATION**：A 為長期最佳；D 是讓市值基準「誠實可表達」的最小一步；B 不建議。**關鍵洞見**：把天數改成注入**並不會**消除「誰決定 10、從哪讀」的問題——要嘛 ui_v3 去匯入 `ui_v2.thresholds`（被禁止），要嘛給該值一個中立住處（受單一擁有者鎖保護），這就是客戶 Gate。

**最小建議順序（每步都需另行授權；此刻均未授權）**

0. 客戶登記 G1-②／③／G-2 的 DEC，以及 NAV 10 日的範圍與語意。
1. D（含 `fx_pending` 證據欄位、`SCHEMA_VERSION` bump、mutation／golden 補強）。
2. B1 與 A1 並行（於 #1154 合併之後）。
3. A。
4. FX 閘門開放是**獨立的證據軌**（冬令探測重跑＋獨立稽核＋客戶裁示），不屬建構的一部分。

**各步獨立稽核須驗證**：`assemble_nav` 的 byte-equal 差異／golden（含 raise 路徑）；ui_v2 薄包裝零行為變更；未組裝輸入 ⇒ Missing 而非 0、且圖表不可比；單一擁有者鎖完好；`fx_pending` 可與缺席區分。

**退路**：若客戶不想再增加風險，採選項 C。

## 11. 需要客戶決定的事（精簡）

| # | 問題 | 總管建議 | 利 | 弊／風險 |
|---|---|---|---|---|
| i | 登記／確認涵蓋 G1-②／③／G-2 的 DEC | 確認並登記 | 授權鏈完整 | 無實質風險 |
| ii | NAV 10 日：適用頁面、`>` 語意、台灣日期、alo 的未來日期 NAV 處理、中立擁有者放哪 | 登記專屬 DEC | 消除「轉述當法源」 | 需客戶時間 |
| iii | 是否授權順序第 1 步（D） | 授權 | 最小一步讓市值基準可誠實表達 | 動 schema，須獨立稽核 |
| iv | ui_v2 的「完整 100% 加註腳」是否對齊方案 A | 另批處理 | 與 `DEC-2026-11-04-02` 一致 | 動 ui_v2 行為與鎖定測試 |
| v | 開放 FX 閘門 | **本次不請求** | — | — |

## 12. 未讀／未驗清單

- 調查者未執行完整 pytest；`docs/v2/79`、`73`、`74` 僅 grep；`_build_alo2` 與 `apply_live_notes` 的本體未讀；hld 同形組裝未讀；探測報告未解壓。
- 全稱性主張僅限已 grep 的目錄；真實 sheet 內容未知。
- #1154 衝突判斷僅讀 diff，未試合併。
- 本機測試註記：`tests/test_v2_domain_allocation_evidence.py::check_target_sum_uses_a_tolerance_not_exact_equality` 在 Python 3.13 本機失敗（補償加總）——既有測試對直譯器版本敏感，非產品缺陷，與本 PR 無關（CI 版本未查證）。

## 13. 本 PR 不做的事

- 不授權任何施工、不新增 DEC、不新增 BL id。
- 不改程式、不改測試。
- 不改 HANDOFF（避免與 #1153 衝突）；其唯一下一接手點的敘述仍然有效——本批不授權任何新事項，G-3 建構仍等 Gate。

## 後續狀態（2026-11-05 之後補註）

> 本節為事後補註；上文各節為合併當時的稽核內容，**原文未改**。

- 第 1 節第 5 點與第 7 節「Producer 缺『未組裝』代碼」，以及第 10 節選項 D，其最小形式現已**實作於開放 PR（尚未合併；PR 與 merge sha 於合併後補登）**；授權見 `DEC-2026-11-05-04`。轉接層仍回阻擋、未傳入宣告。獨立稽核已通過（總管轉達）。
- **`fx_pending` 結論**：無法經 `nav_provenance`（未知鍵使整條旁路被丟棄）或 `source_state.errors`（會被讀成失敗）無損承載；目前可由 `fx_rule_verified` 回顯、閘門 `fx_obs_date_rule_unverified` 與 `FxFact` 缺值導出，依賴一項 L2 不變量 `[UNVERIFIED]`。明確的逐鍵 pending 代碼會重新標記 FX 閘門語意，須另案裁示，**not authorised**，不屬 D。
- 第 12 節的 Python 3.13 註記已有後續發現：`sum()` 自 3.12 起改補償加總，三條 golden 位元組測試在 3.12／3.13 失敗（golden 錄於 CI 版本 3.11）；`page_model_sha256` 隨直譯器版本而異，下游用途未追蹤，登記為開放項、未改。
- 其餘 not authorised：B1、A1、NAV 組裝搬遷、NAV 10 日新規則、FX 閘門開放、正式 UI 接線、OneBrain。
- **文件合併 ≠ 施工授權**（第 13 節）仍然有效；本補註不授權任何事項。
