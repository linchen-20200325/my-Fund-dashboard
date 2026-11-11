# 基金 New UI2／Decision Digest／OneBrain 改善候選矩陣（2026-11-11）

> **性質：基金專屬唯讀設計評估／後續研究提案；不是新的正式規則、DEC、Runtime 實作或施工授權。** 內容僅列基金應具備的能力與基金內部契約依賴；不要求專案 AI 查找其他 repository，亦不提供跨專案程式碼、路徑、資料、公式或投資規則。
>
> **GitHub 觀測快照（2026-11-11 當時；歷史快照，使用前須重查）**：基金 main `81010640`（#1210、#1211、#1213 均已合併；#1211＝隔離雙模式 PoC，merge `5e6a950d`），與本文件不重疊。後續任何執行前須重做 GitHub Verification Gate。BL-0545 保持唯一全域 NEXT。
>
> **基金正式依據**：`PROJECT_RULES.md` 第 13 節；`docs/v2/44_fund_ui_ssot.md`（frozen）、`docs/v2/67_ai_action_vocabulary.md`（Digest／行動語意 SSOT）、`docs/v2/75_onebrain_ai_architecture.md`（方向與 Provider／Cache／Budget）、`docs/v2/79_final_ui_contract_freeze.md`、`docs/v2/80_new_ui2_architecture_proposal.md`、`docs/v2/81_new_ui2_wireframe_01_market.md`、`docs/v2/82_new_ui2_assets_ui_data_evidence_proposal.md`、BL-0527、BL-0545；以及 main 上既有的 OneBrain 研究與裁示：`docs/evidence/onebrain_evidence_coverage_gap_audit_2026_11_08.md`（Evidence 覆蓋差距稽核；研究結案，非施工授權）、`docs/evidence/onebrain_decision_gate_route_and_risk_check_2026_11_08.md`（D1～D10 路線與三風險查核；研究提案）、`DEC-2026-11-08-02`（客戶裁示 OneBrain D1 採方案 C，資料契約先行、Decision Digest 後續再建；D8 FX 閘門維持關閉）。若本文件與正式契約不符，以正式契約為準。
>
> **與既有稽核的關係**：本文件與上述 2026-11-08 稽核重疊之處，以該兩份稽核與 `DEC-2026-11-08-02` 為準；本矩陣只增加 F-01～F-08 的對照視角，不取代、不 supersede 它們。
>
> **方案命名**：本文件第 3 節的三方案以 α／β／γ 標示；2026-11-08 稽核的 A／B／C 另有所指（A＝Evidence Adapter、B＝共用 producer、C＝契約收斂後再做 Digest，客戶已採 C），兩者不同，勿混用。

## 1. 先保留的架構（不是新發明）

- **唯一資料權威**：Raw Sources → Canonical Data → Deterministic Rules／Indicators／Risk Cap → Decision Digest → OneBrain → UI。取數／正規化／驗證在資料層；OneBrain 只讀既有證據，不回寫 canonical、不自行補 Missing、不引入新 source／API、不得覆寫公式或 Risk Cap。
- **呈現與決策分離**：UI ViewModel ≠ Decision Digest；UI 可以收合、縮減顯示資訊，不能據此刪除 canonical／完整 Decision Context。AI 也不得從 UI widget、顏色、Top-N 或 Session 文字反推完整資料。資料層與 AI 層的完整性需分開驗。
- **單一 OneBrain**：各頁在未來只呈現同一份正式 Digest／分析結果對應的 slice；不得由各頁各自產生矛盾的投資結論。不得因本研究提前啟用 Phase 7。
- **基金領域語意**：基金身分／ISIN／Share Class／MoneyDJ 原始分類、NAV 觀測日、FX 觀測日與方向、幣別、配置、Freshness／Availability、正式 Risk Cap 缺口、客戶「級別」設定與「系統推算類型」彼此區分；不新造交易觸發值、分數、信心或六行動詞。

## 2. 能力對照與最小改進候選

| 編號 | 基金目前已有的正式基礎（不是代表 Runtime 完成） | 建議補強／驗收方向 | 優先 | 施工資格 |
|---|---|---|---|---|
| F-01 呈現與完整證據分離 | `67 §5.1`／`§8.6`（Presentation Simplification must never reduce AI Decision Context）與 `79` 已要求呈現與 Digest 分離；`80 §16.3` 明訂 UI ViewModel≠Decision Digest（`81`／`82` 亦使用 ViewModel 一詞）；`ui_v3` 市場頁只消費 view model | 增加「縮減 UI 顯示／切期間／切頁」不影響 headless canonical／Digest 必要證據的守衛；完整 evidence 有追溯入口但不強迫第一屏展開 | P0 | 先做唯讀契約對照；測試／Runtime 額外授權 |
| F-02 讀取完整性 | BL-0527 已承接 Digest 缺口，`67` 未要求一次建立龐大 schema | **先盤點**必要 Evidence ID／來源／as_of／有效性／缺失／讀取／省略／反證能否由現有型別證明；必要時提出 deterministic Coverage Manifest 最小加性設計 | P0 | 未核准 Schema；不得建立重複 Evidence Store |
| F-03 資料與能力狀態 | `shared/ui_semantics/rules.py`、`ui_v3/viewmodels` 和 `67`／`79` 已有既定狀態語意 | 分清 data missing／fetch_failed／stale、feature not wired、rule not evaluated、judgment undeterminable；狀態字樣、符號、顏色遵循基金 SSOT，不搬任何外部狀態 enum | P0 | 僅盤點／測試提案，正式語意另 Gate |
| F-04 基金身分與時間對齊 | 既有基金 Identity／NAV／FX 觀測日規則；BL-0545（Coverage／資料准入）；FX 閘門出處為 `DEC-2026-11-08-02` D8（維持關閉，`FX_OBS_DATE_RULE_VERIFIED` 仍為 `False`） | 同基金同級別／同幣別／同觀測條件跨頁一致；NAV 與 FX 日期不得偷換，資料有值≠准入合格；缺 FX／類別未驗，不得當可信收益／配置數字 | P0 | 未過 FX Gate 只能無法判定 |
| F-05 OneBrain 範圍與反證 | `67 §5–8` 的單一 Brain／AI 只讀與 provenance 對照；`75` 的 Provider／Trace／Cache／Budget 缺口與方向；Phase 7 前置條件見 `44`（Phase 7 正式規格）與 `67 §5.6` | 未來僅按問題 scoped 分包讀取，保留必要支持／反證與 omitted IDs；完整性只能由確定性 validator 判定，AI 不能自行宣稱完整；總結從同一 Digest／compatible snapshot 取得 | P1 | Phase 7 前不得啟用 LLM runtime |
| F-06 AI 成本與快取 | `75` 已研究 provider、fingerprint、cache、trace、budget | 先做既有實作盤點；再比較只計算／模板、兼容 fingerprint cache、必要時有界增量分析；不因每頁入口而每次多一次 LLM 呼叫 | P1 | Provider／Cost Gate 另授權 |
| F-07 手機首屏與證據分層 | `44` 首屏預算；`ui_v3` 市場頁 G3 色票＋G6 卡片、三寬度量測 | 後續「💼 我的資產」優先資產／配置／資料狀態／需注意；詳細 NAV、FX、風險及來源下沉；不改 🌍 已核准主圖與五頁 IA，不複製其他 UI 版型 | P1 | 逐頁 wireframe／UI Gate |
| F-08 Preview、測試與正式入口隔離 | `ui_v3/app_preview.py` 非正式入口、既有防誤用守衛；#1211 獨立 PoC（已合併） | 維持非 production fixture、Preview 僅核准頁面、正式資料不得用 fake 補值；必要時檢查 import/route 反向依賴 | P1 | #1211 範圍不能擴充 |

以上「已有」僅指從正式規格與特定模組可辨識的基礎；實際 Runtime Coverage／Digest 讀取／OneBrain 功能是否已接線，須依後續 GitHub diff、tests、caller、CI 查證，不能由文件存在推定。

## 3. 三路徑評估（正確性／速度／Token）

| 方案 | 作法 | 正確性與風險 | 速度／Token | 建議 |
|---|---|---|---|---|
| α 全量仿製另一套資料／AI／UI | 直接另立資料表、Schema、分頁或引入未核准規則 | **高風險**：Duplicate SSOT、基金 identity／FX／Risk Cap 語意漂移 | 初期看似快，後續返工成本高 | 不採 |
| **β 基金既有契約差異稽核 → 補最小守衛 → 經 Gate 施工** | 逐項核對 `67`／`75`／BL-0527／BL-0545 與程式 caller／tests，僅補真正缺口 | **最低風險**，可回滾，避免重新命名／重定義 | 中等實作速度、最低重複 Token | **推薦** |
| γ 重構 UI／Digest／Brain 全鏈 | 在所有功能完成前大幅重寫架構 | **高風險**：凍結契約衝突、投資語意與資料來源不一致 | 慢／最高成本 | 不採 |

## 4. 建議執行次序與授權邊界

**目前優先，不改排程：**
1. #1211 隔離雙模式 PoC 已合併（`5e6a950d`）；其範圍不得因本文件擴充，正式雙模式仍依 `DEC-2026-11-11-02` 另走 Gate。
2. BL-0545 繼續是唯一全域 NEXT；不得要求使用者立即提供真實 Active Sheet、不得把 live 模式未實作說成已完成。
3. 12→13px、grey／neutral、設定頁、正式雙模式、G7 依 `DEC-2026-11-11-02` 延後／另 Gate；不因本研究動工。
4. **待授權的下一個架構／資料契約研究批次（尚未授權）**：唯讀建立 F-01～F-08 的 Existing Contract → Runtime → Gap → Recommended Minimal Test/Change → Gate 矩陣；必須標明 verified／not found／not run。查基金 repo，不要求跨 repo 讀取或同步；若已存在同等矩陣，直接補差異，不另建競爭規格。
5. **客戶裁示之後**：僅對具重大風險的 schema、正式 AI 行為、資料源、投資語意／Risk Cap／FX Gate、正式 UI 改動施工；安全測試能否自主處理依現行治理。

**不是本文件的授權**：新增正式資料來源／外部 API／Claude API 花費／Evidence Registry storage／Coverage schema／OneBrain runtime／AI 輸出／真實 Active Sheet 寫入／正式 UI、設定頁、全域主題、Share Class mapping／任何基金金融公式。

## 5. 下一批的最小驗收條件（研究，不是假裝完成）

- 查到 Canonical → Domain／Rules → Digest → OneBrain → UI 每個環節的實際 caller／contract；沒有 caller 就標 `NOT_IMPLEMENTED`，無法核對就 `NOT_VERIFIED`。
- 對同一基金，應可追溯 fund identity、share class、currency、observation as_of、retrieved_at、來源、validity、status／rejection reason；查不到的列缺口，不填假預設。
- 是否可以確定性計算 Required／Available／Read／Excluded／Omitted／Counterevidence；無法時標 PARTIAL 或 unavailable，**不得把這些字串直接當正式 schema enum**。
- 實驗：UI 收合／期間切換／隱藏細節，不得反過來改變正式 Digest／required evidence；同一兼容快照跨頁應能對拍。
- 證明 fixture 沒有進正式 UI／資料層，AI 無網路／資料寫入權；未授權先只做靜態證據，不呼叫實際 LLM。
- 完整區分正式契約、研究建議、已合併 production、仍在 Draft、測試涵蓋、未執行；形成不超過三個高優先實作候選的 Decision Gate。

## 6. 工作規則處理（刻意不動）

本文件**不修改** `CLAUDE.md`、`PROJECT_RULES.md`、`PROCESS.md`、`docs/DECISIONS.md` 或現有 frozen SSOT；也不建立永久的跨專案操作規則。基金專案後續技術工作只需要本專案的正式契約與最小研究結果；**跨領域參考已轉為基金專屬能力要求**，專案 AI 無須取得任何外部專案的原始檔或程式。靜默巡航根因稽核與對話過長時的 durable-first checkpoint／結束／新對話交接，仍依原治理及先前排程處理。

## 7. 增補：F-01～F-08 五欄對照（唯讀盤點；2026-11-11；main `f68ef73e`）

> **性質**：客戶授權範圍內，對本檔既有 F-01～F-08 補五欄（Existing Contract／Runtime Caller／Test Evidence／Gap／Authorization Gate）。**不是第二份矩陣或 SSOT、不新增 DEC／BL／schema／enum、不是施工授權**；與第 1～6 節衝突時，仍以第 1～6 節的免責與正式契約為準。重用且不重做 `docs/v2/67／75／79／80／81／82`、BL-0527、BL-0545、`DEC-2026-11-08-02`、`docs/evidence/onebrain_evidence_coverage_gap_audit_2026_11_08.md`（下稱 AUD）、`docs/evidence/onebrain_decision_gate_route_and_risk_check_2026_11_08.md`（下稱 DG）。
>
> **標記**：**FACT**＝本批在 `f68ef73e` 以 `git grep`／讀檔取得；**INFERENCE**＝由事實推得；**NV**＝NOT VERIFIED。**搜尋只在 `*.py` 與所列路徑；動態 import、字串組名、別名不在範圍內**，單次 grep 0 命中不等於未實作，只代表「在此範圍內沒找到」。
>
> **Test Evidence 的共同限制**：本批**沒有執行任何測試**（只讀）。可引的執行紀錄只有兩類：(a) PoC 作者的本機 `pytest -q -m "not slow"` 結果（`docs/evidence/fund_newui2_dual_theme_poc_evidence_2026_11_11.md` §十一）。**兩個範圍必須分開讀**：全 repo「9 failed／19782 passed」是在 **PoC 分支（含 PoC）**上量的，**不是**乾淨 main；乾淨 `origin/main` `55e48d03` 上只重跑了那 5 個失敗檔，結果 9 failed／557 passed（見第 7.3 節 A）；(b) 各 PR head 的 CI check 結論（見各 PR 頁）。**逐檔「是否被 `-m "not slow"` 涵蓋、是否在特定 CI run 實跑」下列一律 NV**，不因檔案存在推定已跑。

### 7.1 五欄對照

**F-01 呈現與完整證據分離**
- **Existing Contract**：`docs/v2/67` §5.1（硬規則）、§5.2、§8.6；`docs/v2/79` §8.1～8.3；`docs/v2/80` §16.3（UI ViewModel≠Decision Digest）；`DEC-2026-10-29-06`、`DEC-2026-11-02-07`。
- **Runtime Caller**：FACT：🌍 市場頁資料流為 `ui_v3/app_preview.py` → `ui_v3/adapters/market_page.py`（呼叫 `services.v2_tables.market_view.build_market_view`、`market_indicator.build_market_indicator_table`）→ `ui_v3/viewmodels/market_page.py` → `ui_v3/pages/mkt.py`。Decision Digest：**not found**——搜尋範圍 `*.py` 全 repo、樣式 `decision_digest|DecisionDigest|build_digest`（不分大小寫）0 命中；`ui_v3/viewmodels/action_slot.py` 檔頭自述「本批不實作 Risk Cap、System Action State、Decision Digest、OneBrain」。
- **Test Evidence**：`tests/ui_v3/test_ui_v3_viewmodel_contract.py`、`test_ui_v3_readonly_guard.py`、`test_ui_v3_import_guard.py`（ui_v3 層級與唯讀）；PoC 作者 §十一紀錄 `tests/ui_v3` 於 `55e48d03` 無失敗（FACT，引述）。專測「縮減 UI 顯示不影響 Digest 必要證據」的測試：**not found**（Digest 本身不存在，無從測）。
- **Gap**：FACT：契約已定、ViewModel 側已實作；因 Digest 不存在，「呈現縮減不改變完整證據」目前**無可驗對象**（INFERENCE：屬 Digest 之前置而非獨立缺口）。
- **Authorization Gate**：Digest schema／生產者＝未授權（`DEC-2026-11-08-02`）；僅唯讀契約對照可繼續。

**F-02 讀取完整性（Required／Available／Read／Omitted）**
- **Existing Contract**：BL-0527（`67` §5.6 七項缺口）；`67` §5.3；AUD §0 結論 1～3、§3 九域差距矩陣；`DEC-2026-11-08-02`（D2 逐域 Required／Optional／Excluded 未核准）；`DEC-2026-11-08-04`（採納 Q1–Q5 方向並產出唯讀草案，**仍不是正式契約**）。
- **Runtime Caller**：FACT：唯一 Complete Evidence 生產者 `services/v2_domain/allocation_evidence.py::build_allocation_evidence`（檔內自標 `SCHEMA_VERSION = 2   # CANDIDATE`，名稱皆為內部候選、非核准詞彙）；唯一非測試 importer 為 `ui_v3/adapters/assets_source.py`（第 67 行 `import allocation_evidence`、第 439 行取用），而 `assets_source` 在 `*.py` 非測試範圍內**沒有 importer**（AUD §0 結論 1 同）。Required／Available／Read／Omitted 的確定性計算：**not found**（範圍同上）。
- **Test Evidence**：`tests/test_v2_domain_allocation_evidence.py`、`tests/test_allocation_evidence_mutations.py`、`tests/ui_v3/test_ui_v3_assets_source_*.py`（生產者與 adapter 契約／突變）；執行狀態 NV。
- **Gap**：FACT：只有 💼 配置面一個候選生產者且無 production 呼叫端；其他八域無。不建立 manifest 或 enum；缺口以 AUD §3 為準。
- **Authorization Gate**：D2 逐域契約＋Digest schema＝未核准，須客戶裁示；`allocation_evidence` 的詞彙不得因本檔升格。

**F-03 資料與能力狀態**
- **Existing Contract**：`docs/v2/44` 四狀態與用字（經 `shared/ui_semantics/rules.py` 的 `source` 欄逐條指回）；`67` §5.3、§5.4；`docs/evidence/data_state_vocabulary_crosswalk_d3a_2026_11_08.md`（`DEC-2026-11-08-02` 的 D3(a) 唯讀對照表）；BL-0527 第 1 項。
- **Runtime Caller**：FACT：`shared/ui_semantics/rules.py` 的 `ENTRIES` 現有 key：`ok`、`attention`、`missing`、`undetermined`、`not_applicable`、`fetch_failed`、`stale`、`threshold_pending`、`neutral`、`not_configured`、`user_param_unset`；`ui_v3/viewmodels/common.py` 的 `STATUS_OK／MISSING／FAILED／STALE／UNDETERMINED`；實際 import `shared.ui_semantics` 的非測試模組（FACT，`git grep`）：`ui_v3/viewmodels/common.py`、`ui_v3/viewmodels/action_slot.py`、`ui_v3/viewmodels/preview_wording.py`、`ui_v3/pages/mkt.py`、`ui_v3/pages/chrome.py`（另 `poc/dual_theme_isolated/poc_fixtures.py` 為 PoC）。`services/v2_domain/market_summary.py` 只在 docstring 提到 `rules.py` 的 `FRESHNESS_TO_KEY`，`services/v2_domain/allocation_evidence.py` 的 import 只有 `dataclasses／datetime／math／holdings`，**兩者都沒有 import** `shared.ui_semantics`。
- **Test Evidence**：`tests/ui_v3/test_ui_v3_semantics_rules.py`、`test_ui_v3_wording_fidelity.py`、`test_ui_v3_preview_wording_guard.py`、`tests/test_v2_domain_normalization.py`；執行狀態 NV。
- **Gap**：INFERENCE：`ENTRIES` 沒有以「Not Implemented」「Not Evaluated」命名的條目；`threshold_pending`／`not_configured`／`undetermined` 是否分別承載這兩個概念，**NV**（見 crosswalk 文件逐項對應）。本檔第 2 節的研究字串**不得**當正式 enum。
- **Authorization Gate**：狀態語意或新字樣＝正式語意 Gate（客戶裁示）；盤點／對照可唯讀進行。

**F-04 基金身分、幣別、NAV／FX 日期與資料准入**
- **Existing Contract**：`PROJECT_RULES.md` 第 13 節；BL-0545（五維評級覆蓋率與資料准入）；`DEC-2026-11-07-03`；`DEC-2026-10-28-05`（DG-2 canonical 身分）；`DEC-2026-11-08-02` D8（FX 閘門維持關閉）；`docs/evidence/fx_d8_gap_and_supplementary_plan_2026_11_08.md`；#1166（研究）、#1168（唯讀探針）。
- **Runtime Caller**：FACT：`services/v2_tables/market_indicator.py` 第 107 行 `FX_OBS_DATE_RULE_VERIFIED = False`；該常數的讀取者在 `*.py` 非測試範圍內為 `market_indicator.py` 自身（取數／寫列閘）、`ui_v3/adapters/assets_source.py`（第 497 行 `read_fx_rule_verified`）、`services/v2_domain/allocation_evidence.py`（由呼叫端傳入）、`ui_v2/alo/source.py`（註解）、以及 `scripts/probe_fx_obs_date.py`／`check_cache_quality.py`／`probe_yahoo_indices_sp.py`。身分解析：`repositories/pool_repository.py::resolve_secid／resolve_isin／resolve_currency`，以及 ISIN→secId 的取數側處理（`repositories/fund/sources.py` 的 `_morningstar_screener_secid`、`repositories/fund/fund_orchestration.py`；FACT 存在，涵蓋率 NV）。Canonical 身分：`services/fund_identity.py::resolve_fund_identity`／`CanonicalFundIdentity`（含 `share_class`、`currency` 屬性，`DEC-2026-10-28-05`、DG-2 Stage-1）——檔頭自述**Shadow Mode、沒有 production 呼叫端**；唯一 hook 為 `services/v2_tables/fund_keys.py`（第 284 行附近延遲 import）→ `services/fund_identity_shadow.py::log_shadow_for_fund_keys` → `resolve_fund_identity`（`fund_identity_shadow.py` 第 26 行 import、第 67 行呼叫）；由 `shared/fund_identity.py::DG2_SHADOW_ENABLED` 把關，該旗標為 `False`（FACT，已讀檔），故此鏈**預設不執行**。其餘非測試呼叫者僅在 `scripts/`（`bl0545_coverage_probe.py`、`probe_moneydj_nav_equivalence.py`）。
- **Test Evidence**：`tests/test_fund_identity_dg2.py`（身分解析）；`tests/test_bl0545_coverage_probe.py`（45 個 test 函式，FACT：計數；離線 fixture／injected fetcher，不證真實覆蓋率）；FX 閘門測試檔 NV。真實 Active Sheet 覆蓋率：**NOT VERIFIED**（BL-0545）。
- **Gap**：FACT：FX 閘門仍關；INFERENCE：因此**不得推論**任何非 TWD 基金已可准入或其市值／配置數字可信。覆蓋率無實證；canonical 身分（含 share class）僅 Shadow、未接 production 路徑。
- **Authorization Gate**：FX 開閘＝未核准、D8 補跑＝未授權（`DEC-2026-11-08-02`）；真實覆蓋率驗證需客戶提供 Active Sheet 的授權（BL-0545 邊界）。

**F-05 OneBrain 範圍與反證**
- **Existing Contract**：`67` §5（AI 只讀、單一 Brain）、§5.3 provenance 對照表、§5.6、§8.6／§8.7（Traceability）；`75` §2、§3.2、§5～§7；`44` 的 Phase 7 正式規格章節；AUD §0、§7；DG；`DEC-2026-11-08-02` D1＝方案 C（資料契約先行，Digest 後續）。
- **Runtime Caller**：FACT：OneBrain runtime **not found**（搜尋範圍 `*.py` 非測試，樣式 `onebrain`（不分大小寫）僅命中 `ui_v3/shell/registry.py`（🤖 頁於 Phase 7 前建構即擋 `registered=True`）與 `ui_v3/viewmodels/action_slot.py` 的「不實作」註解）。現有 AI 總結為舊路徑：`ui/helpers/ai_summary.py` → `services/ai_service.py`（`gemini_generate`）→ `infra/llm.py::call_llm`（`75` §3.1 已列為可沿用骨架，而非 OneBrain）。
- **Test Evidence**：`tests/ui_v3/test_ui_v3_page_registry_guard.py`（🤖 頁不得掛載）；`tests/test_llm.py`（檔存在；`75` §3.1 所列 provider 行為測試）；執行狀態 NV。
- **Gap**：FACT：研究與守則已有、runtime 沒有；支持／反證與 omitted ID 的確定性 validator：not found。**本節任何描述都不是「OneBrain 已啟用」。**
- **Authorization Gate**：Phase 7／Provider／Claude API runtime＝未授權；D2 與 Digest schema＝未核准。

**F-06 AI 成本與快取**
- **Existing Contract**：`75` §4（Provider）、§6（Analysis fingerprint／Cache）、§7（Trace／Audit）、§8（Cost／Budget Governance，含 §8.1 成本原則、§8.2 未來 Budget Control）、§3.2 的 Budget／Trace／Cache 缺口；DG 相關 Gate。
- **Runtime Caller**：FACT：`75` §6 所指「OneBrain analysis fingerprint 驅動的 AI cache 契約」**not found**。已驗證兩個**同名不同用**的既有物：`services/portfolio_tracking.py::weights_fingerprint`＝歸一化權重的 md5 前 12 碼，供快照去重（與 AI cache 無關，確認為同名誤配）；`ui/tab3_portfolio.py::_pf_health_fingerprint`＝健診結果快取查核。另有**舊路徑實際存在的 AI 磁碟快取** `repositories/ai_cache.py`（`make_key(tab_key, snapshot)`；`ui/helpers/ai_summary.py` 以 snapshot＋新聞標題＋stale 註記為 key 使用），它**不是** `75` §6 的契約（INFERENCE：兩者 key 組成、版本欄位與 trace 是否一致 NV）。付費模型呼叫：本批不做、不測。
- **Test Evidence**：`tests/test_ai_cache.py`（舊路徑快取）；`75` §6 契約無測試（契約本身未實作）；執行狀態 NV。
- **Gap**：FACT：Budget／Trace 契約 not found（`75` §3.2 同）；INFERENCE：舊 `ai_cache` 與 `75` §6 目標之間的差距需獨立比對，本批不做。
- **Authorization Gate**：Provider／Cost Gate＝另行授權；不因每頁入口新增 LLM 呼叫。

**F-07 手機首屏與證據分層**
- **Existing Contract**：`docs/v2/44`（首屏預算相關章節；精確節號本批 NV）；`docs/v2/80`、`81`（🌍 線框）、`82`（💼 設計提案）；`DEC-2026-11-11-01`（G3／G6）；BL-0542 G-3～G-5（設計部分核准，資料／配息／整頁接線 Gate 未全授權）。
- **Runtime Caller**：FACT：🌍 市場頁 `ui_v3/pages/mkt.py`（`IA_PAGES` 中唯一 `registered=True`）；💼 頁在 `ui_v3` **沒有 renderer**（`ui_v3/adapters/assets_source.py` 有 adapter、無頁面）。#1207 已合併的量測見 `docs/evidence/fund_newui2_market_g3_g6_build_evidence_2026_11_11.md`。
- **Test Evidence**：`tests/ui_v3/test_ui_v3_degraded_first_screen_budget.py`、`test_ui_v3_market_page_browser.py`（瀏覽器量測）、`test_ui_v3_top_nav_browser.py`；#1207 head `68329b5d` 的 CI 四項 success 見 BACKLOG 檔尾 G3／G6 完成索引（引述，本批未重驗）；瀏覽器測試本身屬 slow／playwright 類，其執行位置 NV。
- **Gap**：INFERENCE：💼 的分層規則尚未有可看的實作；不改 IA、不複製其他 UI 版型。
- **Authorization Gate**：逐頁 wireframe／UI Gate（客戶）；12→13px 併入下一個已授權 UI 批（`DEC-2026-11-11-03`）。

**F-08 Preview、測試與正式入口隔離**
- **Existing Contract**：`DEC-2026-11-02-06`、`PROJECT_RULES.md` 13.2（preview 不是正式入口）；`DEC-2026-11-11-02`、`-03`（PoC 邊界、不授權施工）。
- **Runtime Caller**：FACT：`ui_v3/app_preview.py` 為 Preview 入口；正式入口候選不得引用 `ui_v3`，由 `tests/ui_v3/test_ui_v3_preview_not_formal_guard.py` 掃描（根目錄 `*.py`、`ui`、`ui_v2`、`services`、`repositories`、`shared`、`infra`、`scripts`、`mcp_server`、`models` 與 `.streamlit`／`.github`／`.devcontainer`）。#1211 PoC 位於 `poc/dual_theme_isolated/`、`tests/poc_dual_theme/`，不在上述掃描範圍內（設計如此，見 `docs/evidence/decisions/2026-11-11_new_ui2_dual_theme_t1_t5_ruling.md`）。
- **Test Evidence**：`tests/ui_v3/test_ui_v3_import_guard.py`、`test_ui_v3_preview_not_formal_guard.py`、`test_ui_v3_fixtures_are_fake_guard.py`、`tests/poc_dual_theme/test_poc_dual_theme_guard.py`；PoC 作者 §十一紀錄 `tests/ui_v3` 與 PoC 在 `55e48d03` 全數通過、PoC 的 CI 結果見 #1211 頁（引述）；各 head 實跑狀態 NV。
- **Gap**：FACT：未發現缺口；INFERENCE：守衛的掃描範圍是靜態 AST，繞法（動態組名）不在內，守衛檔頭已自述。
- **Authorization Gate**：無新增；新接線一律須客戶 Gate（本文件不新增任何接線）。

### 7.2 後續階段候選（至多三項；皆待授權，非排程）

| 候選 | 內容 | Gate |
|---|---|---|
| 1 | 逐域 Required／Optional／Excluded 與讀取完整性的唯讀契約對照（F-02／F-05），以 AUD §3 為底，只補差異 | D2、BL-0527；客戶授權 |
| 2 | 非 TWD／FX 的證據補強（F-04）：依 `fx_d8_gap_and_supplementary_plan_2026_11_08.md` 的缺口與補證方法，不以相同方法立即重跑 | `DEC-2026-11-08-02` D8；客戶授權補證 |
| 3 | 舊 `repositories/ai_cache.py` 與 `75` §6／§7 契約的差距比對（F-06）；不做付費呼叫 | Provider／Cost Gate；Phase 7 前僅唯讀 |

### 7.3 誠實性檢查

**A. 「9 個既有失敗」**
- **記錄位置**：`docs/evidence/fund_newui2_dual_theme_poc_evidence_2026_11_11.md` §十一（明細）；`DEC-2026-11-11-03` 的「仍未驗證」欄（根因未驗證）；BACKLOG BL-0342（`test_hld_logic` 於 Python 3.13 失敗、3.11 基準全過）與 BL-0453（`test_rulings_2026_10_18b_logic` 本機紅、CI 綠）。
- **明細（依 PoC 作者）**：`tests/test_alo_core_golden.py` 3、`tests/test_alo_core_golden_mutations.py` 1、`tests/ui_v2/test_hld_logic.py` 2、`tests/ui_v2/test_hld_read_failure_logic.py` 2、`tests/ui_v2/test_rulings_2026_10_18b_logic.py` 1，合計 9。**注意**：協作者口頭轉述「alo_core_golden 4」包含 `_mutations` 那 1 條；上列分開計。
- **量測範圍（兩個，勿混）**：全 repo `-m "not slow"` 的 9 failed／19782 passed 是 **PoC 分支（含 PoC）**的結果；乾淨 `origin/main` `55e48d03` 上**只重跑了 5 個失敗檔**，得 9 failed／557 passed、失敗清單相同（PoC 作者，FACT，引述）。另一個「14 failed」來自無 `.git` 的 `git archive` 副本，是人為環境差異（多出的 6 條在有 `.git` 的真 repo 都通過），**與這 9 條無關**，不是比較基準。
- **狀態**：**現在是否仍可重現＝NOT RUN（本批不跑全套）**；**根因＝NOT VERIFIED**——BL-0342／BL-0453 懷疑為 Python／Streamlit 版本差異，僅為 INFERENCE，BL-0342 自述「尚未完成 root-cause 判定」。不得稱已解決。
- 以上數字來自文件引述，**本批未獨立重算**。

**B. Slow／Visual 兩條 informational lane**
- **設定（FACT，讀 `.github/workflows/pr-check.yml`）**：兩條皆 `continue-on-error: true`（非阻擋）；瀏覽器安裝步驟為 `python -m playwright install --with-deps chromium`（`--with-deps` 會走 apt）。
- **近期紀錄（依協調者轉述的 check run 讀取結果；本批未重讀、不重跑）**：#1214 head `d8ef3bbd` 與 #1212 head `c6bd4323` 的 Slow、Visual 兩條皆在瀏覽器安裝步驟失敗，訊息為 apt「Temporary failure resolving azure.archive.ubuntu.com」，**沒有任何測試被執行**；#1207／#1211／#1213 較早的 head 這兩條曾通過（同為轉述、**NOT VERIFIED**）。
- **結論**：上述兩 head 的 Slow／Visual＝**NOT RUN，不是 PASS**；該失敗是 runner 網路（apt DNS），**不能**解讀為測試通過或程式問題。**未改 workflow。**
- 阻擋性的 Fast／Schema 兩條與此分開看，各 head 的結論以 PR 頁為準。

**C. 本節的驗證層級**：單組（本檔作者）產出，**未經第二組獨立複驗**；等待獨立 QA。
