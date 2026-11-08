# OneBrain Evidence 覆蓋差距稽核（研究結案；不是施工授權）

> **性質**：唯讀研究結案。**不新增規格、不新增 schema、不把 proposal 寫成已核准、不宣稱真實資料覆蓋**。
> **不構成 Phase 7 開工、不構成任何動工授權**（`CLAUDE.md` §-1；登記 ≠ 動工）。
> **基準**：`origin/main` = `b0e2636f`（2026-11-08 觀測；Open PR 0）。以 `git show`／`git grep origin/main` 讀取。
> **產出方式**：兩組單組唯讀稽核（契約／文件側、程式碼側）＋本文件整理者對承重宣稱的抽樣重驗（第 2 節）。**整體未經第二組獨立複驗**（`CLAUDE.md` §-2 規則 6）。
> 分段標示：**FACT**＝可由 repo 指令重現；**INFERENCE**＝由事實推得的讀法；**RECOMMENDATION**＝建議，非裁示。

## 0. 結論先行

| # | 結論 | 類別 |
|---|---|---|
| 1 | Complete Evidence 在程式碼裡**只有一個生產者**：`services/v2_domain/allocation_evidence.py::build_allocation_evidence`（💼 配置面）。狀態 EXISTS IN REPO，**無任何 production 呼叫端**（唯一非測試 import 是 `ui_v3/adapters/assets_source.py`，而該 adapter 本身沒有非測試 importer）。 | FACT（本文件重驗） |
| 2 | Decision Digest、Risk Cap、System Action State、OneBrain、rule_version／Rule ID、counter／supporting evidence：**NOT IMPLEMENTED**。Digest 沒有已核准的完整 schema，只有通則與欄位群。 | FACT（本文件重驗） |
| 3 | 已核准的是**方向與守則**（Missing≠0、五條鐵則、Required／Optional／Excluded 三分通則、欄位 schema 目標），**不是每個資料域的 Required／Optional 清單**。逐域分類一律「待 Gate」。 | FACT（契約側稽核；未逐條重驗） |
| 4 | **真實 Active Sheet 覆蓋率 NOT VERIFIED**（BL-0545）。任何「Evidence 已涵蓋 X% 持倉／健康維度」的說法目前沒有依據。 | FACT |
| 5 | 有 5 項承重風險已被本文件重驗屬實：證據物件無根層 as_of、`nav_metrics` 對 NaN 靜默、Old UI 未知映射為 HOLD、過期 NAV 仍計入市值、`DEC-2026-11-05-04` 文字落後程式。 | FACT |
| 6 | 三方案 A／B／C 的比較見第 6 節。**AI 總管推薦：C**（研究建議，非施工授權）。 | RECOMMENDATION |

## 1. 範圍、基準與方法、盲點

- **範圍**：9 個資料域（市場與總體；基金基本資料／NAV／績效；持倉／資產配置；配息／事件；FX／利率／景氣；基金身份與跨源對應；資料健康／Missing／Freshness；Deterministic Rules／Risk Cap／Action State；Supporting／Counter-evidence）。
- **方法**：(1) 契約側：`docs/v2/66/67/75/79/80/82`、`docs/DECISIONS.md` 相關 DEC、`docs/BACKLOG.md` 相關 BL、`docs/evidence/` 既有稽核。(2) 程式側：`git grep`／`git show origin/main`，並把 `origin/main` 以 `git archive` 解到 scratchpad 實跑 `nav_metrics`。(3) 本文件整理者對 15 條承重宣稱重跑指令（第 2 節）。
- **盲點（必讀）**：
  1. 兩份底稿皆單組；「文件不存在／0 命中」類全稱句以字面符號為準，**改名、動態組字串、別名不在內**。
  2. `docs/DECISIONS.md`（體積大）僅讀相關 DEC，未通讀；`BACKLOG` 僅讀相關列。
  3. Old UI 的 caller 只追到「存在於 `ui/`」，**未逐一追 `app.py` 可達性**。
  4. `tests/ui_v3/*`、`test_v2_tables_*` 等因本機缺 `requests` 無法收集，**未執行**；依 `CLAUDE.md` §-2.A，「依賴齊全下也綠」只能由 CI 驗。
  5. ui_v2 是否為 Streamlit Cloud 實際部署入口：部署設定在 repo 外，**NOT VERIFIED**。
  6. 未做任何真實網路／憑證驗證。
- **三個入口（CONNECTED 一律標註其一）**：**Old UI**＝`app.py`→`ui/`；**ui_v2**＝自成入口 `ui_v2/app_*_live.py`（`app.py` 不 import）；**ui_v3 Preview**＝`ui_v3/app_preview.py`（自稱 Preview-only，`docs/HANDOFF.md` 寫「Preview-only ≠ Cloud 正式上線」）。`CONNECTED(ui_v2)` 不等於 `app.py` 可達。
- **狀態詞**只用：EXISTS IN REPO／CONNECTED／CONTRACT APPROVED／NOT IMPLEMENTED／NOT VERIFIED／NOT APPLICABLE。契約側底稿的 NOT DEFINED 一律讀作 NOT IMPLEMENTED（無正式契約或無實作）；PROPOSAL ONLY 讀作「EXISTS IN REPO（內部候選）且非 CONTRACT APPROVED」。

## 2. 本文件整理者的重驗結果（以此為準）

指令皆對 `origin/main`（`b0e2636f`）執行。

| # | 承重宣稱 | 重驗指令（摘要） | 結果 | 與底稿 |
|---|---|---|---|---|
| V1 | `build_allocation_evidence` 唯一生產者；無 production 呼叫端 | `git grep -n "build_allocation_evidence\|allocation_evidence" origin/main -- '*.py'`（排除生產者本檔） | 命中僅：`services/v2_domain/__init__.py`（文字）、`tests/` 內 5 檔、`ui_v3/adapters/assets_source.py:67,439` | 相符 |
| V2 | `assets_source` 無非測試 importer | `git grep -ln "assets_source" origin/main -- '*.py'` | 僅 `ui_v3/adapters/assets_source.py` 自身＋ `tests/ui_v3/` 5 檔 | 相符 |
| V3 | `ACTION_SLOT_SOURCES_ENABLED` 為 False | `git grep -n "ACTION_SLOT_SOURCES_ENABLED" origin/main -- '*.py'` | `ui_v3/viewmodels/action_slot.py:31` = `False`；測試斷言 `is False` | 相符 |
| V4 | `counter_evidence`／`supporting_evidence` 0 檔 | `git grep -il "counter_evidence\|supporting_evidence" origin/main -- '*.py'` | 0 命中（rc=1） | 相符（僅這兩個字面詞） |
| V5 | `rule_version`／`policy_version` 僅 1 測試檔 | `git grep -n -i -E "rule_version\|policy_version" origin/main -- '*.py'` | 僅 `tests/test_v2_domain_allocation_evidence.py:494` | 相符 |
| V6 | `is_imputed` 非測試 0 檔 | `git grep -l is_imputed origin/main -- '*.py' ':!tests'` | 0 命中 | 相符 |
| V7 | `decision_matrix`：未設定→HOLD、未知 verdict→持有 | `git show origin/main:services/decision_matrix.py` | `ACTION_HOLD = "持有"`；未設定級別 fail-closed 一律 HOLD（`:72-75`、`:104-106`）；未知 verdict level 回「預設持有」（約 `:201-202`）；空清單 `core_hold_pct: 0.0`（`:234`） | 相符 |
| V8 | `nav_metrics` 對 NaN 靜默 | 以 `git archive origin/main` 解到 scratchpad，`python3 -I` 直接呼叫 | `return_pct([nan,1,2])`=nan；`drawdown_pct([1,nan,2])`=**0.0**；`vol_pct([1,2,nan,3])`=nan；`return_pct([-1,2])`=-300.0 | 相符 |
| V9 | `DEC-2026-11-05-04` 與程式不同步 | 讀 `docs/DECISIONS.md` 該筆；`git log origin/main -- services/v2_domain/allocation_evidence.py` | DEC「實作狀態」仍寫「位於尚未合併的開放 PR」；程式檔頭與簽名已含 `nav_input_state`；提交 `135210e6` 由合併 `861628cc` 進入 main（`merge-base --is-ancestor` 成立） | **補強**：底稿「merge sha NOT VERIFIED」→ 本文件查得 `861628cc` |
| V10 | `FX_OBS_DATE_RULE_VERIFIED` 為 False | `git grep -n "FX_OBS_DATE_RULE_VERIFIED" origin/main -- '*.py' ':!tests'` | `services/v2_tables/market_indicator.py:107` = `False`；`assets_source.py:497` 於載入時讀取 | 相符 |
| V11 | `DG2_SHADOW_ENABLED` 預設 False；唯一 hook | `git grep -n "DG2_SHADOW_ENABLED" origin/main -- '*.py' ':!tests'` | `shared/fund_identity.py:19` = `False`；hook 在 `services/v2_tables/fund_keys.py:282` | 相符 |
| V12 | 證據物件無根層 as_of／產生時間；不帶 `last_synced_at`／`opened_on` | `git show origin/main:services/v2_domain/allocation_evidence.py \| grep -n "last_synced_at\|opened_on\|generated_at\|retrieved\|as_of"` | 僅命中註解與 `fx_row_as_of` 呼叫；無此類欄位 | 相符 |
| V13 | `latest_nav_row` 不檢查淨值多舊 | `git show origin/main:services/v2_domain/holdings.py` | 實作為「取 `nav_date` 最大的一列」，無新鮮度判斷 | 相符 |
| V14 | `app.py`／`ui/` 不引用 `ui_v2`／`ui_v3` | `git grep -n "ui_v2\|ui_v3" origin/main -- app.py ui` | 0 命中 | 相符 |
| V15 | `mcp_server` 輸出含 UI 字樣 | `git grep -n "action_text\|action_light" origin/main -- mcp_server` | `tools_macro.py:64` 取 `icon, level, _color, action_text = composite_verdict(total)`；輸出含 `action_light` | 相符 |

**未重驗（保留底稿原文，標 NOT VERIFIED）**：`open_gates` 碼數改以實數為準（計法見本段下方），不採底稿的 10。**open gate 計法（本文件實數）**：`allocation_evidence.py` 的 `_CHART_AFFECTING_GATES` 有 8 碼，其上方註解另列 3 碼（`tolerance_unset_effect_unjudged`、`omitted_row_reason_codes_undefined`、`non_holding_read_error_effect_unjudged`，刻意不在該集合內），合計 **11**。仍未驗：`INDICATOR_SPECS` 7 鍵（未點算）；`DOMAIN_ORDER` 12 個 domain（本文件只確認其存在與前 12 個常數排列）；Old UI 各 caller 的 `app.py` 可達性；`docs/v2/67/79/80/82` 與各 DEC 的逐字內容（契約側僅抽樣 `67` §5、§8.6 與 `DEC-2026-11-05-02/-04`、`BL-0527`）；底稿所述的測試 passed／skipped 數（326／21）。

## 3. 差距矩陣（9 域）

欄位說明：**R／O／E**＝Required／Optional／Excluded，僅引已核准規則，其餘「待 Gate」。**Digest 契約**依第 1 節狀態詞對映。證據來源：程式側稽核（路徑）＋契約側稽核（DEC／文件節）。

### 3.1 來源、identity、時間、缺值

| 域 | 欄位語意與現有來源（程式路徑） | identity（canonical／share class／currency） | as_of／retrieved_at／source | 缺值／失敗／過期／衝突 |
|---|---|---|---|---|
| 市場與總體 | v2：`services/v2_tables/market_view.py`（12 個 domain：VIX、TAIEX、成交量、市場統計、S&P500、US10Y／2Y、NASDAQ、MSCI World／EM、EPS-PE、隱含盈餘）＋`market_indicator.py`（7 鍵）；L1 `repositories/macro/{yf,fred,fred_vintage}.py`。Old：`services/macro/*`（約 28 指標） | v2 兩套鍵（`domain`、`indicator_key`）；無跨類別統一 identifier（`67` §5.3 自陳） | domain 有 `obs_date`／`fetched_at`／`source`；`market_indicator` 有 `release_date`／`is_revised`，但只有 `source_tier`，無 provider 名 | v2 四態（`ok`／資料未備／業務例外／系統錯誤）；無 stale 狀態；Old `fetch_fred` 失敗回空 DataFrame 不帶原因 |
| 基金基本資料／NAV／績效 | v2：`nav_dividend.py`、`exp_nav.py`、`exp_profile.py`；`nav_metrics`（報酬／回撤／波動）。Old：`repositories/fund/*`、`services/fund_service.py` | `fund_code`＋`full_key`（`resolve_full_keys`）；幣別僅信持倉列或來源自報，不一致整檔不寫 | `nav` 列有 `nav_date`／`fetched_at`；來源放 `provenance` 旁路（表本身無 source 欄） | 取不到不寫列；非有限／非正淨值不寫並計數；過期只記 `provenance`；無獨立 NAV stale 狀態 |
| 持倉／資產配置 | `services/v2_tables/alo_holdings.py`→`services/v2_domain/holdings.py`→`allocation_evidence.py` | 持倉鍵 `(policy_id, fund_code)`；`HoldingKeyConflict` 降級而非 raise；hld／alo 兩套同鍵合併規則並存 | NAV／FX 面有 `nav_date`／`obs_date`／`fetched_at`；**根層無 as_of／產生時間**；`last_synced_at`／`opened_on` 未攜帶 | `None`＋機器碼；`NAV_STATES` 等英文字彙；`UncoveredAmount` 不可算、永不為 0；`open_gates` 記錄「未裁示的判斷」 |
| 配息／事件 | v2 `dividend` 表（`nav_dividend.py`）；Old `services/dividend_calendar.py`、`services/health/dividend*.py` | `(fund_code, ex_date)` | `fetched_at` 每列；來源在 `provenance` | 逐來源證據通過才收；`pay_date` 來源不給→空；`DIV_DATE_IS_EX_DATE_VERIFIED = False`；無 confirmed／scheduled／estimated 欄 |
| FX／利率／景氣 | v2：`market_indicator.py`（`fx_twd_per_usd`、`policy_rate_pct`、`term_spread_pct`、`credit_spread_pct`、`leading_index`、`coincident_index`）。Old：`get_latest_fx`、`composite_score`、`identify_regime` | `indicator_key`；FX 鍵 `fx_twd_per_<iso>` | `obs_date`、`release_date`（FRED 經 vintage）、`is_revised`、`fetched_at` | **FX 閘門關**（`FX_OBS_DATE_RULE_VERIFIED=False`）→ 不取數不寫列，連帶非 TWD 基金市值 `fx_absent`；國發會兩鍵 pending（來源不給公布日） |
| 基金身份與跨源對應 | `services/fund_identity.py`（`CanonicalFundIdentity`）、`fund_identity_shadow.py`、`shared/fund_identity.py` | `base_fund_code`＋`currency`／`share_class`／`distribution_type`／`hedge_status`（無可靠資料→`"Unknown"`，不參與比對）；production 鍵仍是 `full_key` | `source`、`as_of`（呼叫端給）、`suffix_provenance` | `verification_status` 7 種；不剝、不合併、不改寫原值；`isin` 預設 None |
| 資料健康／Missing／Freshness | `ui_v2/health.py`、`page_health.py`（呈現層）；`v2_domain/freshness.delay_days`、`market_summary.SeriesFreshness`；Old `ui/tab5_data_guard.py` | 資料類＋原因鍵 | 延遲日數＝`fetched_at` 日期減 `obs_date`（日曆日） | 至少 5 套狀態字彙並存、無對照表（見第 5 節 R6）；新鮮度門檻散在三處，`v2_domain` 刻意不判（`threshold_pending`） |
| Deterministic Rules／Risk Cap／Action State | v2_domain：`rule_filter`、`deviation`、`holdings.exceeds`；Old：`services/decision_matrix.py`、`policy_advisor_service`、`services/health/*`、`risk_radar` | 不適用（作用對象為基金或類別） | 規則結果無 rule_id／threshold 引用／版本 | Old 有「未設定／未知→持有」映射（V7）；Risk Cap 無實作；`ui_v3/viewmodels/action_slot.py` 只允許「無法判定」或 None |
| Supporting／Counter-evidence | 無生產者。最近類比：`shared/evidence_support.py::EvidenceSupport`（證據充足性，含 `missing` 清單，非支持／反證分類） | NOT APPLICABLE | NOT APPLICABLE | `EvidenceSupport.reason` 是寫給使用者的中文，不可當機器碼 |

### 3.2 計算、生產者、契約、R／O／E、風險

| 域 | 是否有 deterministic calculation | Complete Evidence 生產者 | Digest 正式契約 | R／O／E | 缺口風險、依賴、必要決策 |
|---|---|---|---|---|---|
| 市場與總體 | 有：`normalization.normalize_pair`、`market_summary.first_screen_summary`、`periods.slice_period`、`freshness.delay_days`；Old `composite_score`、`calc_macro_phase` | **NOT IMPLEMENTED**。CONNECTED(ui_v3 Preview)：`ui_v3/adapters/market_page.py`；CONNECTED(ui_v2)：`ui_v2/mkt/source.py`；Old UI 消費 `fetch_all_indicators`（可達性 NOT VERIFIED） | NOT IMPLEMENTED | 待 Gate（無逐鍵規則；regime 聚合規則另走 Formula Gate） | NASDAQ／MSCI／成交量／市場統計／EPS-PE 僅回 Missing；`stale_after` 門檻未定（出處：`docs/v2/67` §8.5 與 `79` UI-8，BL-0531 後續項 (5)；BL-0369 是另一件事：市場總覽 ② 核心卡 `◷` 徽章與 47 `Q-05` 的色調門檻）；各指標 provider 缺（`67` §5.6-2）；BL-0501 待客戶。需決策：stale 門檻、provider 表、聚合規則 |
| 基金基本資料／NAV／績效 | 有：`nav_metrics`、Old `fund_service`、`fund_total_return`、`reconcile.py` | **NOT IMPLEMENTED**（NAV／績效層級）；僅 💼 證據內嵌 `NavFact`。CONNECTED(Old UI；`app.py` 可達性 NOT VERIFIED)：`ui/tab2_single_fund.py`；CONNECTED(ui_v2)：`ui_v2/hld/logic.py` | NOT IMPLEMENTED | 待 Gate | 報酬口徑多套（BL-0524）；NAV 10 日規則僅存 `ui_v2/thresholds.py`、無專屬 DEC（`DEC-2026-11-05-03` 五待決）；真實頁面覆蓋 NOT VERIFIED。需決策：報酬口徑、NAV 新鮮度語意 |
| 持倉／資產配置 | 有：成本／市值基準、類別加總、`exceeds`、`deviation`、`rule_filter`、`target_sum` | **EXISTS IN REPO，未 CONNECTED**：`allocation_evidence.py`（`SCHEMA_VERSION=2`，檔頭自稱「INTERNAL CANDIDATE, not approved vocabulary」）；市值面未接線（`BLOCKED_MARKET_BASIS`） | 通則 CONTRACT APPROVED；本域無 Digest 契約（NOT IMPLEMENTED） | 部分：Missing≠0、covered-only≠完整 100%、未設定≠讀取失敗（引 `DEC-2026-11-04-02`、`DEC-2026-10-24-09`）；其餘（G-1 分母公式、G-3～G-5、11 項 open gate（計法：`_CHART_AFFECTING_GATES` 8 碼＋註解列另 3 碼，見第 2 節））待 Gate | 授權鏈為要點轉述、無逐字（`DEC-2026-11-05-02/-04` 自述「不補造」）；`DEC-04` 文字落後程式（V9）；過期 NAV 仍計市值（僅記 gate）。需決策：G-1～G-5 |
| 配息／事件 | 有：吃本金判定、Old 除息日推估 | **NOT IMPLEMENTED**。CONNECTED(ui_v2)：`ui_v2/{exp,hld}/source.py`；CONNECTED(Old UI；`app.py` 可達性 NOT VERIFIED)：`ui/tab_manage.py` | NOT IMPLEMENTED（`67` §8.11：納入與否「隨 Digest schema Gate」） | 待 Gate（delivery metadata 屬 Excluded，已核准） | `pay_date` 語意 amendment 未起草（BL-0534）；date_status 四態無正式契約。需決策：配息日期語意（G-3） |
| FX／利率／景氣 | v2 僅取數與列轉換；Old 有 `composite_score`、`identify_regime` | **NOT IMPLEMENTED**；`allocation_evidence` 只內嵌 `FxFact`。CONNECTED(ui_v2)：`ui_v2/mkt|set` | NOT IMPLEMENTED | 待 Gate | FX 閘門需冬令探測（BL-0217，約 2026-11-02～11-24，repo 內尚無重跑結果）；EUR／JPY／CNY 需各自驗證；`mcp_server` 輸出含 UI 字樣。需決策：開閘證據軌 |
| 基金身份與跨源對應 | 有（純字串規則＋通路表） | **NOT IMPLEMENTED**（`evaluate_suffix_evidence` 是比較器，非生產者）。DG2：EXISTS IN REPO，shadow，旗標預設關 | NOT IMPLEMENTED（欄位群僅在 `67` §8.6 Identity 列） | 部分：shadow 階段規則已核准（`DEC-2026-10-28-05`）；canonical key 採用與跨類別 identifier 待 Gate | canonical identity consumer 在 production 為 0；幣別／share class 多為 Unknown；ISIN→identity 來源未核准（BL-0530 research）。需決策：何時由 shadow 轉用 |
| 資料健康／Missing／Freshness | 有：`delay_days`（純）；`page_health.main_reason` 優先序（呈現用） | **NOT IMPLEMENTED**（無統一健康 Evidence）；💼 專屬評估在 `allocation_evidence`。CONNECTED(ui_v2、ui_v3 Preview、Old UI) | NOT IMPLEMENTED | 部分：Missing≠0／neutral／safe／HOLD（`PROJECT_RULES` 13.1）；健康 Grade／覆蓋／准入三軸分開（`DEC-2026-11-06-02`）；其餘待 Gate | 狀態字彙對照表缺（`docs/v2/67` §5.6 第 1 項）；stale／conflict 門檻未裁（探針一律 `not_evaluated`）；`ui_v2/health.py` 含判定邏輯、屬呈現層不得當資料源。需決策：字彙對照、門檻、准入準則 |
| Deterministic Rules／Risk Cap／Action State | 有（使用者門檻比較；Old 規則碼）；**無** Risk Cap、減碼 trigger、Action State 產出 | **NOT IMPLEMENTED**（Risk Cap／Action State）。Old 規則 CONNECTED(Old UI；`app.py` 可達性 NOT VERIFIED)；`rule_filter`／`deviation` CONNECTED(ui_v2) | NOT IMPLEMENTED（六行動詞語意與 System Action State 通則為 CONTRACT APPROVED，Rules／Risk Cap 未定義前恆為「無法判定」） | 待 Gate | Risk Cap 與減碼 trigger 待客戶（BL-0495／0496）；`rule_version`／Rule ID 格式 Gate（`docs/v2/67` §5.6 第 4 項）。需決策：Risk Cap、trigger、Rule ID 格式 |
| Supporting／Counter-evidence | 無 | **NOT IMPLEMENTED**（V4） | NOT IMPLEMENTED（輸出需含「最大反證」之方向已核准；定義未裁） | 待 Gate | 反證的投資語意定義未裁（BL-0542 G-1 新待決題 (b)）；若把 `EvidenceSupport` 當反證語意不符。需決策：反證定義 |

## 4. 與 BL-0545 的關係

- **FACT**：真實 Active Sheet 覆蓋率 **NOT VERIFIED**（無合法使用者 session／持倉清單）；探針 `scripts/bl0545_coverage_probe.py` 僅離線 fixture／匿名清單／注入 fetcher；live 模式 NOT IMPLEMENTED；輸出固定 `real_active_sheet_coverage:"NOT VERIFIED"`、`admission:"NOT DEFINED"`；stale／conflict 因無門檻一律 `not_evaluated`。
- **本文件的推論限制（INFERENCE）**：
  1. **不得**宣稱任何健康維度對「使用者實際持倉」的 `n_scored/n_applicable` 比例；可說的只有「機制」（五維、2/5 不等於 5/5、非 USD 外幣目前不受支援），且皆為靜態讀碼、單組。
  2. 「正式資料准入」未定義，故 Digest 的 Required 無法依准入狀態篩選；Evidence 內不得出現 passed／safe／eligible 類結論詞（`DEC-2026-11-06-02`）。
  3. 分母口徑（`resolve_full_keys` vs DG2 canonical）未由客戶或總管指定。
  4. `SUPPORTED_FX` 目前僅為常數、非守門條件（探針文件 F5）。
- 本研究**不取代、不推進** BL-0545 的 Gate；兩者獨立。

## 5. 實證風險清單（附重驗結果）

| # | 風險 | 證據 | 重驗 |
|---|---|---|---|
| R1 | 唯一 Evidence 生產者無 production 呼叫端，市值面未接線 | V1、V2；`assets_source` 檔頭自陳 | 已重驗，屬實 |
| R2 | 證據物件無根層 as_of／產生時間；`last_synced_at`／`opened_on` 不被攜帶 | V12 | 已重驗，屬實 |
| R3 | `nav_metrics` 對 NaN 靜默：`drawdown_pct([1,nan,2])`＝0.0 | V8（本機實跑 `git archive` 副本） | 已重驗，屬實。風險限於「有呼叫端直接餵含 NaN 序列」；上游 `nav_row_problems` 是否擋住：NOT VERIFIED（未讀函式本體） |
| R4 | Old UI 未設定／未知 verdict 映射為 HOLD（註解自稱 fail-closed） | V7 | 已重驗，屬實；是否與「Missing≠HOLD」衝突屬語意判定，**待 Gate**，本文件不裁 |
| R5 | 過期 NAV 仍計入市值，僅記 gate `stale_nav_degradation_unjudged` | V13 | 已重驗，屬實 |
| R6 | 至少 5 套狀態字彙並存（中文四態、英文 `NAV_STATES`／`SRC_*`／`VAL_*`、Cell 狀態、`threshold_pending`、頁首符號） | 程式側 §2.7 | NOT VERIFIED（採底稿；V7／V8 僅證明其中數套存在，「恰好 5 套」未逐一點算） |
| R7 | 新鮮度門檻散在三處（`v2_domain` 不判／`ui_v2/thresholds.py`／Old `shared/signal_thresholds.py`） | 程式側 §2.1、§2.7 | NOT VERIFIED（採底稿） |
| R8 | FX 閘門關＋國發會 pending＝非 TWD 市值與景氣在 v2 路徑實質無資料 | V10 | 閘門值已重驗；「實質無資料」為 INFERENCE |
| R9 | DG-2 canonical identity 無 production consumer | V11 | 已重驗，屬實（hook 在旗標關閉時不載入） |
| R10 | `mcp_server` 輸出含 UI 字樣（icon、action_text、顏色燈號），provenance 無逐指標 as_of | V15 | action_text／action_light 已重驗；「無逐指標 as_of」NOT VERIFIED |
| R11 | hld／alo 兩套同鍵合併規則並存未收斂 | `holdings.py` 檔頭 | NOT VERIFIED（採底稿） |
| R12 | `DEC-2026-11-05-04` 文字落後程式（仍寫「開放 PR 未合併」） | V9 | 已重驗，屬實；merge 為 `861628cc` |
| R13 | 授權鏈缺逐字證據：G1-②／③／G-2、方案 D 皆為要點轉述 | `DEC-2026-11-05-02/-04` 自述「不補造」 | 已重驗 `-02` 含「不補造」字樣；承重的生產者據此建立 |
| R14 | 「AI 不讀畫面」「AI 不回寫 canonical」守衛缺（BL-0527 自述 repo 內沒找到專門守衛） | BL-0527 | NOT VERIFIED（未再掃守衛） |

## 6. 已有稽核涵蓋範圍與新差距 G 清單

### 6.1 已涵蓋（避免重做）

| 文件 | 涵蓋 | 限制 |
|---|---|---|
| `docs/evidence/g3_market_basis_data_contract_audit_2026_11_05.md` | 💼 市值基準：NAV／FX 血緣、NAV 10 日規則、FX 閘門、授權鏈弱點 | 僅 💼；單組＋對抗稽核 1 組 |
| `docs/evidence/code_data_boundaries_readonly_audit_2026_11_05.md` | 程式可達性與資料責任九分類 | 非全庫 AST、非刪碼授權 |
| `docs/evidence/health_4d_coverage_static_audit_2026_11_06.md`（#1157） | 五維健康靜態讀碼 | 單組靜態、無實測 |
| `docs/evidence/bl0545_*`（2 檔） | 探針協定、F1～F12、合法取得路徑 | 單組；無真實覆蓋率 |
| `docs/evidence/new_ui2_spec_supersession_data_capability_review_2026_11_06.md` | 舊規格取代索引、各資料可取得性 | 索引性質，非 SSOT |
| `docs/v2/82` §8、`docs/v2/69/70/71` | 💼 逐元件追溯；跨 view 分歧；DG-2；舊線 AI 盤點 | 單組；僅部分域 |

### 6.2 新差距 G 清單（**INFERENCE，本研究判讀，非既有文件主張**；本研究判讀；「查無文件」不宣稱窮舉）

| # | 差距 | 備註 |
|---|---|---|
| G1 | 無跨資料域的 Evidence 清單（誰必須進 Digest）；僅 💼 有生產者 | `67` §8.6 只有通則與欄位群 |
| G2 | 🔍 找基金域無任何 Digest／Evidence 契約文件 | NOT VERIFIED 無漏掃 |
| G3 | 基金績效／健康域無 Complete Evidence 生產者 | 五維原值僅存在於探針輸出協定（調查協定，非產品契約） |
| G4 | System Action State 無生產者；Risk Cap／trigger 未定義 | BL-0495／0496 |
| G5 | expected／received manifest（防遺漏覆蓋校驗）只存在於 ChatGPT 對話證據，非正式契約，且未與 fingerprint 規則對接 | 設計建議，非裁示 |
| G6 | Evidence 版本化／`schema_version`／fingerprint canonicalization：Digest 層無 | `75` §6 明寫不在本輪拍死 |
| G7 | Excluded 清單無機器守衛 | 與 R14 同源 |
| G8 | NAV 10 日跨頁語意無專屬 DEC | `DEC-2026-11-05-03` 五待決 |
| G9 | DEC 授權鏈缺逐字證據 | 同 R13 |
| G10 | `DEC-2026-11-05-04` 與程式不同步 | 同 R12；merge `861628cc` |
| G11 | Evidence 之間的衝突紀錄格式未涵蓋（`PROJECT_RULES` 13.3 要求 selected／rejected source、difference、reason、freshness；Digest 欄位群 Source 列無 rejected source 欄） | 底稿判讀，未逐字重驗 |
| G12 | 舊線 AI 輸出行動句（BL-0528）與 AI 快照指紋不含 NAV／FX 值（BL-0523），與未來 fingerprint 契約的銜接無文件 | 採底稿 |
| G13 | BL-0501 EPS×PE 資料源與區段 B／C 公式待客戶；🌍「市場結論」Digest 欄位無法定義 | 採底稿 |
| G14 | **新增（本文件）**：Old UI 與 ui_v2／ui_v3 各自一套資料出口，對應 R5／R6／R7，尚無任何文件主張「哪一套是 Digest 的唯一輸入來源」 | INFERENCE |

## 7. 三方案比較

**定義（皆為本研究的選項描述，非既有規格）**：
- **A 最小必要 Evidence Adapter**：只做唯讀轉接層，把現有各域輸出原樣包成統一外型，供未來 Digest 取用。
- **B 先完善 Complete Evidence 共用生產者**：把 💼 的 `allocation_evidence` 模式擴到其餘域，各域各有生產者，再組 Digest。
- **C 等各頁資料契約收斂後再組裝 Digest**：先走既有 Gate（字彙對照、門檻、R／O／E、Risk Cap、反證定義、BL-0545 合法輸入），契約收斂後才設計 Digest。

| 維度（INFERENCE，定性） | A | B | C |
|---|---|---|---|
| 正確性 | 中低：外型統一但語意沒統一，會把 R4／R6／R7 的分歧原樣帶進 Digest | 中：每域語意可明確，但每域都要先有 R／O／E 與門檻 | 高：契約先於實作，語意分歧先在 Gate 解決 |
| 架構風險 | 高：adapter 的欄位集合事實上會成為未核准的 schema；與客戶「不要武斷建立巨大 schema」相衝 | 高：8 個域各自長出候選 schema；`allocation_evidence` 現況已是「內部候選」，複製只會放大 | 低：不新增程式；風險是延遲 |
| 實作時間 | 短 | 長（多域） | 實作時間≈0；但等待客戶 Gate 的時間不可控 |
| 測試量 | 中（契約測試＋差異測試） | 大（每域需突變測試與 golden） | 小（目前只需文件守衛） |
| Token 成本 | 中 | 高 | 低 |

| 方案 | 優點 | 缺點 | 主要風險 |
|---|---|---|---|
| A | 快；可早期暴露各域缺口 | 先有外型再有契約，易被誤當既定 schema；Required／Optional 無依據 | 未核准欄位被下游依賴，後續 Gate 難回頭 |
| B | 每域語意最完整；沿用 `allocation_evidence` 已有的測試體例 | 工程量大；每域都卡在未裁示項（門檻、字彙、口徑） | 工作量在 Gate 未過時白做；與「登記 ≠ 動工」衝突 |
| C | 不造未核准的東西；缺口全部落到可決策的 Gate 清單 | 沒有產出可跑的東西；進度完全取決於客戶裁示 | 長期延遲；期間 R3／R5 等風險仍留在現況（但它們是現況，不是 C 造成的） |

**AI 總管推薦：C**。理由（INFERENCE）：第 3 節顯示 9 個域中，8 個域缺 R／O／E 規則，且 stale／conflict 門檻、狀態字彙對照、Risk Cap、反證定義皆未裁；A 與 B 都得在這些空白上先選一個答案，等於在 Gate 之外自創規格。C 的代價（無可跑產出）可用第 8 節的「需客戶裁示事項」換成明確的下一步。
**這是研究建議，不是施工授權，不構成 Phase 7 開工**；`docs/HANDOFF.md` 的唯一 NEXT（BL-0545 真實覆蓋率合法輸入 Gate）不因本文件改變。

## 8. 需客戶裁示事項（若要往 A／B／C 任一方向前進；皆未裁）

| # | 事項 | 為何需要 | 對應登記 |
|---|---|---|---|
| D1 | 方案方向（A／B／C）本身，以及是否啟動任何 Digest 相關施工 | 屬產品方向與 Phase 7 範圍 | 新決策（本文件不起草 DEC） |
| D2 | 各域 Required／Optional 逐項清單與 Digest schema 版本／fingerprint | `67` §8.6 僅通則；三分隨 Digest 實作調整 | BL-0527 |
| D3 | 狀態字彙對照表與 stale／conflict／`stale_after` 門檻 | 無門檻則 Health 兩態無法產出 | `docs/v2/67` §5.6 第 1／3 項（BL-0527）、`67` §8.5／`79` UI-8（BL-0531 後續項 (5)）、BL-0369（卡片 `◷` 徽章／47 `Q-05`，另案）、BL-0545 |
| D4 | Risk Cap、減碼 trigger、Rule ID／`rule_version` 格式 | Rules／Risk Cap 未定義前 Action State 恆為「無法判定」 | BL-0495／0496、`docs/v2/67` §5.6 第 4 項 |
| D5 | 反證（counter-evidence）的投資語意定義 | 無定義則無法有生產者 | BL-0542 G-1 (b) |
| D6 | 💼 G-1（分母公式）、G-3（配息日期語意）、G-4、G-5 與 11 項 open gate（計法：`_CHART_AFFECTING_GATES` 8 碼＋註解列另 3 碼，見第 2 節） | 現有生產者的詞彙仍是內部候選 | BL-0542 |
| D7 | NAV 10 日規則的跨頁語意（五待決 (a)～(e)） | 影響 Digest 的 stale／too_old 欄 | `DEC-2026-11-05-03` |
| D8 | FX 閘門開放之證據軌與冬令探測結果 | 非 TWD 市值與景氣目前實質無資料 | BL-0217 |
| D9 | BL-0545 覆蓋率所需的合法輸入與分母口徑 | 覆蓋率仍 NOT VERIFIED | BL-0545、`DEC-2026-11-07-03` |
| D10 | 是否補齊或重新確認 `DEC-2026-11-05-02/-04` 的客戶授權（目前為要點轉述、無逐字）並同步 `-04` 的實作狀態 | 承重生產者的授權鏈 | `DEC-2026-11-05-02/-04` |

> 以上每項在本文件中**僅登記為待決**，不起草選項、不預設答案，也不視為已由客戶同意。
