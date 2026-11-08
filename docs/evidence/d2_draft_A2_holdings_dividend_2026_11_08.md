> 基準 origin/main 772d6e9a；單組作者草稿；獨立 QA 已完成一輪並已回修，見 PR #1177，非 QA 通過，合併前仍待 CI；不構成正式契約或裁示

# D2 唯讀資料需求草案（輕量盤點）：持倉與配置、配息與事件

> **性質**：作者草稿，供客戶討論用的唯讀盤點。**不是正式契約、不是 Schema、不是裁示、不是施工授權**（`CLAUDE.md` §-1：登記不等於動工）。
> **基準**：`origin/main` = `772d6e9a179413c3596f5a5150a6c07edb7a12af`（本組已 `git fetch`；一律以 `git show`／`git grep origin/main` 讀取，未 checkout、未改任何 repo 檔、未連網、未 commit）。
> **標記**：【F】＝FACT（可由 repo 指令或文字重現）；【I】＝INFERENCE（作者由事實推得）；【NV】＝NOT VERIFIED（未查證、或原文即未證實）。
> **來源寫法**：「檔名＋符號／節名」，不寫行號。
> **作者候選分類**（必備／選備／不納入／待決）＝作者的**候選**，**不是**客戶核准；唯一例外是明標「已核准」者（附 DEC／節）。
> **客戶已選方向（本稿遵守，不再重問；方向五項見 `DEC-2026-11-08-04` Q1–Q5——該 DEC 在 PR #1177 分支新增、`origin/main`（772d6e9a）尚無）**：(Q4) 缺資料沿用既有「資料未備／無法判定」字樣，不新增詞、不提門檻；(Q5) FX 閘門關閉（`DEC-2026-11-08-02` 要點 (1)），非台幣基金仍整理原幣資料，只把無法可靠換算者標「無法判定」；D6／G-3／BL-0534 等只列依賴、不代替決定；不使用真實帳號或未提供的持倉資料。

---

## 0. 結論先行

| # | 結論 | 標記 |
|---|---|---|
| 1 | 「持倉與配置」目前**有正式程式產出的**是：持倉表（`holding` 列，含數量、台幣成本、原幣成本、幣別、類別）、成本基準的類別加總、以及一個尚無生產呼叫端的 Complete Evidence 物件。市值面（NAV×單位數×匯率）程式碼存在，但在 New UI2 預覽路徑被擋（`BLOCKED_MARKET_BASIS`），匯率閘門關閉使非台幣基金市值＝`fx_absent`（無法換算）。 | 【F】 |
| 2 | 「配息與事件」目前**有正式程式產出的**是：`dividend` 表（每單位配息、原幣、除息日、來源自報幣別、`div_kind` 恆為 `unknown`、`pay_date` 恆空）——且**逐來源逐筆**通過證據核對才寫入，過不了就整檔不寫並記原因。 | 【F】 |
| 3 | 基準日／除息日／付款日**尚無統一口徑**：舊行事曆引擎以「配息基準日」為推估目標、事件欄卻命名 `ex_date`；v2 `dividend.ex_date` 指除息日；44 `pay_date` 寫「實際入帳日」，79 §17.3 提案卻說 `payment_date` 不是入帳日。舊路徑旗標 `DIV_DATE_IS_EX_DATE_VERIFIED` 為 `False`。 | 【F】 |
| 4 | 配息「預估 vs 實際」只存在於舊行事曆引擎的 `is_actual` 布林旗標；v2 `dividend` 表**沒有**預估／實際欄。`confirmed`／`scheduled`／`estimated`／`unavailable` 四態是 79 §17.4 的**提案**，非核准契約。 | 【F】 |
| 5 | 這兩類的 Required／Optional／Excluded **逐項清單尚未核准**（D2 仍待裁；`DEC-2026-11-08-02` 明寫逐域契約未核准）。已核准或已有明文的屬以下幾類：缺值≠0／中性／安全／HOLD 的通則；UI 呈現層的缺 FX 方案 A（`DEC-2026-11-04-02`）；使用者參數留空＝「未設定」的規則鍵 `user_param_unset`；Missing／Unknown 不得被另一軸繞過（引 `DEC-2026-10-24-09`，本稿未逐條重驗【NV】）；以及 Excluded 的 delivery metadata／通知偏好（67 §8.11 第 1、3 點——該節自稱「單組轉錄、須至少 1 組獨立稽核後才視為已驗」，故本項『已核准』以 79 第 17 節原文為準，67 §8.11 為轉錄、未經獨立驗證）。此處不主張這份分類窮舉。 | 【F】 |
| 6 | **真實使用者持倉對這些欄位的覆蓋率 NOT VERIFIED**（BL-0545）；本稿所有「有資料」均指「程式有路徑且有契約檢查」，不是「真實資料已涵蓋」。 | 【F】 |
| 7 | 本稿查到一個與「缺值不得變 0」相關、但屬既有行為的觀察：`calc_holdings_overlap` 對「兩檔皆缺持股與產業」的配對填 `0.0`；下游 `services/homogeneity.py` 自述已把它排除於成功對數之外。其他消費者（如 `ui/components/mutual_exclusion.py`）是否直接讀該矩陣格、畫面如何呈現，**未驗**。 | 【F】＋【NV】 |

---

## 1. 範圍、基準、方法與盲點

- 【F】已讀：`docs/evidence/onebrain_evidence_coverage_gap_audit_2026_11_08.md`（§3.1、§3.2、§5、§8）、`docs/evidence/onebrain_decision_gate_route_and_risk_check_2026_11_08.md`（§1、D6、§2 三風險）、`docs/evidence/data_state_vocabulary_crosswalk_d3a_2026_11_08.md`（§0、A～Q 組標題與配息、NAV、SRC/VAL 相關列）、`docs/v2/74`／`73`（與持倉、配息、分母相關段落，非通讀）、`docs/v2/67` §8.11、`docs/v2/79` §17.3／§17.4、`docs/DECISIONS.md` 的 DEC-2026-11-04-02／-03、-11-05-02／-04、-11-03-02、-11-08-02／-03，`docs/BACKLOG.md` 的 BL-0534／0542／0527／0217。
- 【F】已讀程式：`services/v2_domain/allocation_evidence.py`（含 `_CHART_AFFECTING_GATES`）、`services/v2_domain/holdings.py`、`services/v2_tables/alo_holdings.py`、`services/v2_tables/nav_dividend.py`、`services/v2_tables/contract.py`（`HOLDING_FIELDS`、`DIVIDEND_FIELDS`）、`services/dividend_calendar.py`（模組說明與事件欄）、`services/health/dividend.py`、`services/health/dividend_calc.py`（檔頭）、`services/portfolio_service.py::calc_holdings_overlap`（只讀）、`services/homogeneity.py`（檔頭與一段）。
- 【NV】`docs/DECISIONS.md` 與 `docs/BACKLOG.md` 只讀相關列，未通讀；`docs/v2/73`、`74` 為關鍵字掃描，未逐行讀；`services/dividend_calendar.py`（約兩千行）只讀模組說明、事件欄與少數函式簽名；各 DEC 引用的客戶逐字 evidence 檔**多數未讀**（部分 DEC 自述僅「要點轉述」）。
- 【NV】Old UI（`app.py`→`ui/`）各呼叫端的可達性、`ui/tab3_t7_ledger.py` 的市值顯示、`ui_v2/hld` 市值欄位逐項實作，均**未逐行驗**；本稿引用的 Old UI 事實出自上列 evidence 文件，標為轉引。
- 【NV】本稿未執行任何測試、未跑程式、未做網路或憑證驗證；本機缺 `requests`（見 AUD §1 盲點 4），依賴齊全環境下是否綠只能由 CI 驗。
- 【I】「已有且可靠」一詞在本稿僅表示：有正式程式路徑＋契約或證據檢查＋不依賴任何未裁 Gate。**不代表真實資料已驗證**（見結論 6）。

---

## 2. 持倉與配置

### 2.1 項目盤點表

欄位：既有名稱／現有來源／有無正式程式產出／是否客戶核准／候選分類（作者候選）／缺少時的影響／待裁問題與 Gate／出處。

| # | 項目 | 既有名稱與現有來源 | 有無正式程式產出 | 是否客戶核准 | 候選分類 | 缺少時的影響 | 待裁問題與 Gate | 出處（檔名＋符號／節） |
|---|---|---|---|---|---|---|---|---|
| H1 | 持有數量 | `holding.units_shares`；來源＝保單分頁「持有單位數」，經 L1 `policy_supplement_repository` 讀取 | 【F】有：`alo_holdings.build_alo_tables`＋`contract.holding_row_problems` | 【F】欄位在 44 §4.1（frozen）；`alo_holdings` 檔頭自述規則出自客戶 2026-09-27 前裁示（Q4(a)）——逐字【NV】 | 必備 | 【F】空白或 0＝該筆**不寫入**並列入 `skipped_holdings`，原因「持有單位數空白或為 0（沒填）」；不補 0 | 略過列的原因代碼尚未定義＝open gate `omitted_row_reason_codes_undefined`（D6；BL-0411／F-18 相關【I】；BACKLOG 現寫 BL-0411 為「open→fixed（待獨立稽核）」，本稿未驗修正是否涵蓋原因碼） | `alo_holdings::_holding_reasons`；`contract::HOLDING_FIELDS`；`74` F-18 列 |
| H2 | 台幣成本 | `holding.cost_twd`＝保單分頁「淨投資金額」（空白、0、無法解析一律不寫入，U10） | 【F】有 | 【F】44 §4.1；U10 出自 `alo_holdings` 檔頭（客戶 2026-09-27 前裁示，逐字【NV】） | 必備（成本基準） | 【F】該筆不寫入，原因寫明；成本基準的類別值會少這一筆 | 「淨投資金額」是否等於正式「成本」語意：【NV】repo 文件未見明文；G-1 分母口徑（D6）連動【I】 | `alo_holdings::_holding_reasons`；`holdings::basis_value_with_reason`（成本基準＝`float(cost_twd)`，不讀 NAV／匯率） |
| H3 | 原幣成本 | `holding.cost_orig_ccy`＝持有單位數×平均買入單位成本（任一為 0 或空白＝沒填） | 【F】有 | 【F】44 §4.1；Q4(a) 同上 | 選備（現行配置公式不讀它，只由證據物件回顯）【I】 | 缺（任一源欄空白）時該筆整筆不寫入（同 H1 原因清單） | 無專屬 Gate；非台幣基金的原幣成本是否列為「必備」＝D2【I】 | `alo_holdings::_holding_reasons`；`allocation_evidence::HoldingEvidence` |
| H4 | 幣別 | `holding.ccy`＝保單分頁「幣別」；`nav.ccy` **只收持倉列手填或來源自報**，兩者皆有但不同＝整檔不寫 | 【F】有 | 【F】44 §4.1；`nav_dividend` 檔頭記 `49` §2.6／T3 與客戶 2026-10-13／10-14 幣別裁示（逐字【NV】） | 必備 | 【F】幣別空白＝持倉不寫入；`nav.ccy` 缺或衝突＝該檔淨值整批不寫（`ccy_missing`／`ccy_conflict`） | 持倉幣別與淨值幣別不一致時對圖的影響＝open gate `holding_nav_ccy_disagreement_unjudged`（D6） | `alo_holdings::_holding_reasons`；`nav_dividend::resolve_nav_ccy`、`WITHHELD_CCY_*`；`allocation_evidence::_CHART_AFFECTING_GATES` |
| H5 | 匯率（TWD 換算） | `market_indicator` 的 `fx_twd_per_<iso>`；台幣基金不需要 | 【F】取數與換算程式存在，但閘門 `FX_OBS_DATE_RULE_VERIFIED = False` ⇒ 不取數、不寫列 | 【F】客戶 2026-11-08 裁示「FX 閘門維持關閉」（`DEC-2026-11-08-02` 要點 (1)，要點轉述、非逐字）；開閘**未核准** | 待決（閘門由客戶掌握；本稿只列依賴） | 【F】非台幣基金的市值＝`None`＋原因 `fx_absent`；成本基準不受影響（不讀匯率） | 閘門開放證據軌：D8／BL-0217（補證方法與是否補跑未授權）；EUR／JPY／CNY 另需各自驗證【F】 | `market_indicator::FX_OBS_DATE_RULE_VERIFIED`；`holdings::basis_value_with_reason`；`DEC-2026-11-08-02` |
| H6 | 淨值（市值的輸入） | `nav` 表（`nav_date`、`nav_orig_ccy`、`ccy`、`source_tier`、`is_estimated`、`fetched_at`）；B 線走 A 鏈多來源淨值 | 【F】有 | 【F】44 §4.2；B 線復用 A 鏈出自客戶 2026-10-13 裁示（`nav_dividend` 檔頭自述，逐字【NV】） | 待決（市值面才需要；成本基準不需要） | 【F】無淨值列＝市值 `None`＋`nav_absent`／`nav_stale`；**過期 NAV 仍可被計入**（`latest_nav_row` 只取最新一列、不看多舊；僅記 gate `stale_nav_degradation_unjudged`）；ui_v2 有「超過 10 日不納入」的既有實作 | 過期天數規則的跨頁語意＝D7（`DEC-2026-11-05-03` 五待決 (a)～(e)）；Old UI T7 是否也套用＝三風險 R3（轉引【NV】） | `holdings::latest_nav_row`；`ui_v2/thresholds::NAV_NOT_READY_DAYS`；`DEC-2026-11-05-03`；`onebrain_decision_gate…` §2.3 |
| H7 | 市值 | 單檔＝單位數×淨值（非台幣再乘匯率）；類別市值＝加總 | 【F】L2 有（`holdings::basis_value_with_reason`／`category_values`）；【F】New UI2 預覽路徑 `ui_v3/adapters/assets_source.py` 對市值基準回 `STATUS_BLOCKED`、不呼叫生產者 | 【F】UI 呈現：`DEC-2026-11-04-02`（僅 UI 設計、缺 FX 採方案 A）；公式 PORT：G1-②／③ 的授權記在 `DEC-2026-11-05-02`（**事後補登、要點轉述、非逐字；客戶 2026-11-08 選擇保留歷史摘要、未重新追認，見 `DEC-2026-11-08-03`**）；`DEC-2026-11-04-03` 本身只授權 G1-① Golden Baseline，其不授權事項明列 G1-②／③、現行效果為「須客戶另批授權」；**市值面接線未授權**（`DEC-2026-11-05-04`「仍未授權」） | 待決 | 【F】缺值＝`None`＋機器碼，永不為 0；整類缺時分母不完整 | G-1（D6）、D7、D8 | `holdings.py`；`assets_source::evaluate`（轉引 AUD §3.2、§5 R1／R5）；`DEC-2026-11-05-02`、`DEC-2026-11-04-03` |
| H8 | 持倉識別（保單＋基金代號） | `holding_id`、`policy_id`、`fund_code`；`holding_id`＝保單編號、基金代號、同鍵序號 n 以直線符號 `\|` 串接 | 【F】有 | 【F】44 §4.1；`holding_id` 組法為「總管自決」（T2，非客戶裁示） | 必備 | 【F】鍵含直線符號的列不寫入；`holding_id` 撞號＝raise（fail loud）；同鍵兩列語意不同＝`HoldingKeyConflict`（不加總、不挑一列） | hld／alo **兩套同鍵合併規則刻意並存、未收斂**（`holdings.py` 檔頭登記「屬跨頁一致性，本批登記、不裁」）；【NV】未見專屬 BL 編號；依 `PROJECT_RULES` 13.3【I】 | `alo_holdings::_holding_id`；`holdings::merge_same_key_holdings`／`aggregate_holding_rows` |
| H9 | 直接持有（DIRECT） | `policy_id` 恰為 `DIRECT` 的列（保單分頁） | 【F】有：讀入但**不產生 `holding` 列**，逐筆警示 `DIRECT_WARNING` | 【F】客戶 U9：「不計入配置」；「不產生 `holding` 列」是**總管暫定、非客戶裁示**（`alo_holdings` 檔頭自述） | 不納入（目前行為）；是否改變＝待決 | 【F】DIRECT 持倉不進分子與分母；hld 頁看不到 DIRECT 持倉（已登記未定題） | hld 頁遇 DIRECT 持倉如何顯示＝待 hld 接真資料時送客戶【F】（檔頭自述）；無 Gate 編號【NV】 | `alo_holdings` 檔頭「DIRECT」段；`DIRECT_WARNING` |
| H10 | 類別（分類） | `holding.bucket`＝`_持倉補充` 的「類別」（不取保單分頁的「級別」，Q8）；空白或不在名稱表＝未分類 | 【F】有：`holdings::bucket_category`、證據物件 `is_unclassified` | 【F】Q8 出自 `alo_holdings` 檔頭（客戶 2026-09-27 前裁示，逐字【NV】）；未分類是否影響圖的可比性＝未裁 | 必備（配置面）【I】 | 【F】未分類保留為獨立類別，不猜 | open gate `unclassified_comparability_unjudged`（D6）；BL-0542 G-1 新待決題 (e)「unclassified／空目標的完整性」 | `holdings::bucket_category`；`BL-0542` G-1 註 |
| H11 | 目標配置、容許帶、比重基準 | `user_setting` 的 `targets`、`tolerance`、`basis`、`bucket_names`（使用者自設） | 【F】證據物件回顯，狀態 `set`／`unset`／`empty`／`read_failed`／`invalid` | 【F】「使用者參數留空＝⬜ 未設定、不代填」＝已核准規則鍵 `user_param_unset`（crosswalk A11，引 44 SET-3、`DEC-2026-10-20-01`） | 選備（使用者參數；缺時「未設定」，不代填）【I】 | 【F】基準或目標未設＝圖狀態 `not_evaluated`；目標類別缺權重＝阻擋事實 `target_weight_missing` | open gate：`target_weight_sum_rule_undefined`（權重和以容差比較）、`target_duplicate_bucket_unjudged`、`tolerance_unset_effect_unjudged`（記錄但**刻意不影響圖狀態**，客戶可推翻）— D6 | `allocation_evidence`（`SettingsEcho`、gates 段）；`BL-0542` 註 |
| H12 | 分母 | `DenominatorFacts`（`value_twd`、`verdict`∈`complete`／`incomplete`／`none`／`non_positive`／`non_finite`、各計數） | 【F】有（內部候選） | 【F】**UI 呈現**已核准：缺必要 FX 使分母不完整時，不得顯示誤導性完整 100%，改顯示資料未備與未涵蓋範圍（`DEC-2026-11-04-02` 方案 A）。**分母公式與 PORT 技術承接＝G-1 未裁** | 待決 | 【F】`ui_v2` `_build_alo2` 對其餘類別仍可能以可估值類別分母顯示 100%（`DEC-2026-11-04-03`「已知落差」，現行測試釘住）；證據物件不輸出「占總資產 100%」欄，只有 `share_of_covered_pct`＋`covers_all_holdings` | G-1（D6）；分母口徑（`resolve_full_keys` vs DG2 canonical）亦見 D9【F】 | `allocation_evidence::DenominatorFacts`、`ShareFact`；`DEC-2026-11-04-02`、`-03` |
| H13 | 涵蓋與未涵蓋範圍 | `CoverageFacts`（`covered_value_twd`、`uncovered_categories`、`uncovered_holdings`、`uncovered_value`） | 【F】有（內部候選） | 【F】「covered-only≠完整 100%」「Missing≠0」為已核准原則（AUD §3.2 引 `DEC-2026-11-04-02`、`DEC-2026-10-24-09`；本稿未逐條重驗【NV】） | 必備（證據型）【I】 | 【F】未涵蓋的台幣金額標為**不可計算**，永不為 0；目標有但無持倉且來源未完整時，0 標 `unproven_zero` | G-1、D3(a)（狀態詞對映）、G-5（D6） | `allocation_evidence::CoverageFacts`、`UncoveredAmount` |
| H14 | 來源涵蓋（讀取是否完整） | `SourceFacts`（`active_source`、讀取錯誤、`skipped_tabs`、略過列）；評估 `source_coverage`∈`complete`／`incomplete`／`unknown`／`failed`／`not_selected` | 【F】有（內部候選） | 【F】候選詞彙，檔頭自稱「INTERNAL CANDIDATE, not approved vocabulary」 | 必備（證據型）【I】 | 【F】來源不完整時，圖狀態＝`not_comparable`，且分類值不標 `value_reliable` | `non_holding_read_error_effect_unjudged`、`omitted_row_reason_codes_undefined`（D6）；字彙對映＝D3(a)（crosswalk L 組全數「不能判定」【F】） | `allocation_evidence::SourceFacts`；crosswalk L1～L9 |
| H15 | 持倉開始日、最後核對日 | `holding.opened_on`；`holding.last_synced_at`（`最後核對日` 的當日 12:00 台灣時間＝推定值，R1＝B） | 【F】持倉表有；【F】證據物件**不攜帶**這兩欄、也沒有根層 as_of／產生時間（本組讀 `HoldingEvidence`、`AllocationEvidence` 欄位確認；AUD V12 同） | 【F】R1＝B 出自 `alo_holdings` 檔頭（客戶 2026-09-27 前裁示，逐字【NV】）；時刻為推定值，登記於 `ACCEPTANCE.md` 8.1 | 選備（作者候選）；Digest 是否需要根層時間＝D2 | 【I】Evidence 無法自證「這份是何時產生、基於何時的持倉」 | 無專屬 Gate；歸入 D2（Required 含 `as_of`，67 §8.6 通則）【I】 | `alo_holdings::last_synced_at_from_check_date`；`allocation_evidence::HoldingEvidence`；AUD §5 R2 |
| H16 | Complete Evidence 物件本身 | `AllocationEvidence`（`SCHEMA_VERSION = 2`、`PRODUCER_ID = "v2_domain.allocation_evidence"`；`rule_ref` 只是 placeholder） | 【F】有生產者 `build_allocation_evidence`；【F】非測試的唯一匯入在 `ui_v3/adapters/assets_source.py`，該 adapter 本身**無非測試匯入者**（本組重跑 `git grep`，與 AUD V1／V2 相符）⇒ **無 production 呼叫端** | 【F】`DEC-2026-11-05-02`／`-04` 的授權為要點轉述、無逐字；客戶 2026-11-08 選擇**保留歷史摘要、未重新追認**（`DEC-2026-11-08-03`）。【F】schema 為候選，非核准契約 | 待決（整個物件的去留與外型＝D1 方案 C 已定「契約先行」，物件升格與否未裁） | 【F】沒有它，配置面沒有統一的「完整性」輸出；有它但未接線，同樣沒有人消費 | D10（授權鏈未追認）；D2；D6（11 項 open gate）；G-2 之後接線另需授權 | `allocation_evidence` 模組說明；`DEC-2026-11-05-02`／`-04`、`DEC-2026-11-08-03` |
| H17 | 基金間持股／產業重疊（影子基金） | `calc_holdings_overlap` 的 Jaccard（持股名稱）＋ cosine（產業）；來源＝各基金的 `top_holdings`、`sector_alloc` | 【F】有（L2 純函式）；【F】**不是**使用者持倉的資料域，是「基金底層持股」的衍生分析 | 【NV】未見客戶對其「缺值呈現」的核准條文；`calc_holdings_overlap` 門檻與權重在 `shared/signal_thresholds` SSOT（本稿不列值） | 待決（是否屬配置面 Digest 輸入＝D2）【I】 | 【F】兩檔皆缺持股與產業的配對，矩陣格填 `0.0`、且不入 shadow（原始碼與 docstring）；【F】`services/homogeneity.py` 自述另行排除這類配對、不算成功對 | 呈現是否沿用既有「資料未備／無法判定」＝客戶已選方向；是否納入本草案範圍＝待客戶確認；無既有專屬 Gate【NV】 | `portfolio_service::calc_holdings_overlap`；`services/homogeneity` 檔頭 |

### 2.2 現有 Complete Evidence 的「資料不足或被阻擋」情況（逐項）

| # | 情況 | 既有名稱（內部候選碼） | 觸發條件（事實） | 白話影響 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| B1 | 沒有 Active 來源 | `source_coverage = not_selected` | 沒有選定的持倉來源 | 無資料可評估 | 【F】 | `allocation_evidence::SRC_NOT_SELECTED` |
| B2 | 持倉表讀取失敗 | `source_coverage = failed` | `holding` 表讀取失敗 | 配置整頁無法評估 | 【F】 | `SRC_FAILED` |
| B3 | 有略過分頁／略過列／非持倉表讀取失敗 | `source_coverage = incomplete`；`unknown` 為「有略過證據但沒有持倉可聚合」 | 讀取不完整 | 圖狀態＝`not_comparable` | 【F】 | `SRC_INCOMPLETE`、`SRC_UNKNOWN`；`ChartComparability` docstring |
| B4 | 市值面 NAV 端未組裝 | `nav_input_state = not_assembled`；逐檔 `nav_state = not_assembled`；軟代碼 `nav_not_assembled`；估值 `not_evaluated` | 呼叫端宣告未組裝 NAV；New UI2 預覽路徑對市值基準恆回阻擋 | 市值面完全不評估 | 【F】 | `NAV_INPUT_STATES`、`NAV_STATES`；`assets_source::evaluate` |
| B5 | 該檔無淨值列且原因不明 | `nav_state = cause_unknown` | 呼叫端未宣告「已組裝」，缺列時不宣稱「無資料」 | 不把缺值說成「查無」 | 【F】 | `NAV_STATE_CAUSE_UNKNOWN` |
| B6 | 淨值已取得但被資料有效性規則擋下 | `nav_state = obtained_rejected` | 該檔在 `nav_not_ready`／過期清單 | 市值 `None`（`nav_stale`） | 【F】 | `NAV_STATE_OBTAINED_REJECTED` |
| B7 | 缺必要 FX（閘門關閉） | 原因 `fx_absent`；gate `fx_obs_date_rule_unverified`（傳 `False`）或 `fx_obs_date_rule_status_not_provided`（傳 `None`） | 非台幣淨值需要匯率鍵，而閘門關閉、不寫列 | 非台幣基金市值不可算；分母不完整 | 【F】 | `FX_OBS_DATE_RULE_VERIFIED`；`holdings::REASON_FX_ABSENT` |
| B8 | 分母非正／非有限 | `denominator.verdict = non_positive`／`non_finite`；估值 `failed` | 分母為零、負或 NaN／inf | 不輸出占比 | 【F】 | `DEN_*`、`VAL_FAILED` |
| B9 | 持倉鍵衝突 | `identity_conflict` | 同鍵兩列語意不同 | 降級，不 raise | 【F】 | `HoldingKeyConflict`；`IdentityConflict` |
| B10 | 未涵蓋的台幣金額 | `uncovered_value`（不可計算） | 有缺值類別 | 不能說「未涵蓋 N 元」；永不為 0 | 【F】 | `UncoveredAmount` |
| B11 | 實測風險（轉引） | `nav_metrics` 遇 NaN 靜默（例：回撤 0.0）；Old UI 未知級別映射為「持有」；過期 NAV 仍計入市值；證據物件無根層 as_of | 見 AUD §5 R1～R5 | 重驗屬實；可達性與影響等級見三風險查核（`nav_metrics` 僅 Preview；`decision_matrix` 該線 `app.py` 不可達；Old UI T7 `app.py` 可達但未驗細節） | 【F】（AUD 重驗）＋【NV】（Old UI T7 細節） | `onebrain_evidence_coverage_gap_audit…` §5；`onebrain_decision_gate…` §2 |

### 2.3 11 項 open gate（`allocation_evidence`）——只列，不裁

> 【F】計法：`_CHART_AFFECTING_GATES` 8 碼＋檔內註解另列 3 碼＝11；其中 3 碼刻意不在影響圖狀態的集合內。每碼的「文件所指 Gate」欄：BL-0542 與 D6 只寫「逐碼依所屬 Gate」，**文件未逐碼指定**；以下「作者推測關聯」為【I】【NV】。

| # | 代碼 | 影響圖狀態？ | 白話（事實） | 作者推測關聯（【I】【NV】） |
|---|---|---|---|---|
| 1 | `unclassified_comparability_unjudged` | 是 | 有未分類持倉時，圖可不可稱「可比」尚未裁 | BL-0542 G-1 待決 (e) |
| 2 | `target_weight_sum_rule_undefined` | 是 | 目標權重和是否等於 1 的容差規則未定（`CLAUDE.md` 4.3 禁止精確浮點比較） | G-1 |
| 3 | `target_duplicate_bucket_unjudged` | 是 | 目標中出現重複類別名的處理未裁 | G-1 |
| 4 | `fx_obs_date_lag_degradation_unjudged` | 是 | 匯率觀測日落後於淨值日時是否降級未裁 | D8／BL-0217；G-1 |
| 5 | `stale_nav_degradation_unjudged` | 是 | 過期淨值是否降級未裁（僅在有 `nav_stale` 或 `nav_stale_undated` 原因時加入；舊淨值仍被計入時**不會**觸發） | D7；BL-0542 G-1 待決 (a) |
| 6 | `holding_nav_ccy_disagreement_unjudged` | 是 | 持倉幣別與淨值幣別不一致時未裁 | G-1；BL-0542 G-1 待決 (f)（必要幣別判斷重複）【NV】 |
| 7 | `fx_obs_date_rule_status_not_provided` | 是 | 呼叫端沒傳匯率閘門狀態（`None`） | D8 |
| 8 | `fx_obs_date_rule_unverified` | 是 | 匯率閘門為 `False` | D8；BL-0217 |
| 9 | `tolerance_unset_effect_unjudged` | 否（刻意） | 容許帶未設對判定的影響未裁；記錄但不影響圖狀態（客戶可推翻） | G-1 |
| 10 | `omitted_row_reason_codes_undefined` | 否 | 略過列的原因代碼未定義 | BL-0411／F-18【NV】 |
| 11 | `non_holding_read_error_effect_unjudged` | 否 | 非持倉表讀取錯誤的影響未裁 | G-1／G-5【NV】 |

---

## 3. 配息與事件

### 3.1 項目盤點表

| # | 項目 | 既有名稱與現有來源 | 有無正式程式產出 | 是否客戶核准 | 候選分類 | 缺少時的影響 | 待裁問題與 Gate | 出處 |
|---|---|---|---|---|---|---|---|---|
| E1 | 配息金額（每單位，原幣） | `dividend.div_per_unit_orig_ccy`；來源＝A 鏈配息瀑布（合庫 MoneyDJ、FundClear、鉅亨三個解析器）；每筆須通過金額欄出處證據（表頭恰為「每單位配息額」／JSON 欄名恰為 `DividendAmount`／`dividend`）才收 | 【F】有；過不了＝不寫列、列入 `pending`（`div_ex_date_unverified` 擴大射程，代碼字面不改） | 【F】44 §4.3（frozen）；B 線配息改走 A 鏈出自客戶 2026-10-13 裁示（`nav_dividend` 檔頭自述，逐字【NV】） | 必備（若配息納入 Digest）；是否納入＝待決（67 §8.11 第 2 點：隨 Digest schema Gate） | 【F】該檔配息不寫；不以 0 補；缺值≠沒有配息 | D2；G-3（D6） | `nav_dividend::DIV_AMOUNT_EVIDENCE`、`rows_from_chain_dividends` |
| E2 | 配息幣別 | `dividend.ccy`；**只收來源自報**，不沿用持倉幣別；自報值與持倉手填意思相同才寫、標籤用持倉手填；不同或認不出＝整檔不寫 | 【F】有 | 【F】`nav_dividend` 檔頭記客戶 2026-10-13「幣別規則與淨值相同」、2026-10-14 C3a 裁示（逐字【NV】） | 必備 | 【F】`WITHHELD_CCY_NOT_SOURCE_REPORTED`／`ccy_conflict`／`div_ccy_differs` ⇒ 整檔不寫；鉅亨解析器**不回報幣別**⇒一律不寫 | 客戶已選：非台幣仍整理原幣、無法可靠換算者標「無法判定」（Q5）；與 FX 閘門無關（配息不換算） | `nav_dividend::DIV_CCY_EVIDENCE`、`WITHHELD_*` |
| E3 | 除息日 | `dividend.ex_date`；逐來源逐筆核對日期欄出處（合庫表頭第 2 格恰為「除息日」；FundClear 取自 `ExDividendDate`；鉅亨取自 `exDate`） | 【F】有（A 鏈路徑）；【F】舊路徑 `build_dividend_table` 受 `DIV_DATE_IS_EX_DATE_VERIFIED = False` 管：每一檔列 `pending`、不取數、不寫列 | 【F】44 §4.3 `ex_date`＝除息日；舊路徑「`fetch_div` 的 date 是不是除息日未查證」自述（49 §2.2 引） | 待決 | 【F】日期欄證明不了＝`pending`／不寫；**repo 無真實頁面 fixture**（`nav_dividend` 註解自述），所以改成每頁每筆當場核對 | G-3（基準日 vs 除息日）；D6 | `nav_dividend::DIV_DATE_IS_EX_DATE_VERIFIED`、`DIV_EX_DATE_EVIDENCE`、`PENDING_DIV_DATE_SEMANTICS` |
| E4 | 基準日（record date） | v2 `dividend` 表**沒有**此欄（`DIVIDEND_FIELDS` 為 `fund_code`、`ex_date`、`pay_date`、`div_per_unit_orig_ccy`、`ccy`、`div_kind`、`fetched_at`）；舊引擎以 MoneyDJ「配息基準日」為推估目標，事件欄卻命名 `ex_date` | 【F】舊引擎有；v2 無 | 【F】79 §17.3 提案四概念（`record_date`、`ex_dividend_date`、`payment_date`、`estimated_bank_credit_window`）；**提案、非核准**；79 自述「legacy `ex_date`（取 `date`＝基準日優先）≠ 44 `dividend.ex_date`（除息日）」 | 待決 | 【F】兩處「ex_date」語意不同，混用會把基準日當除息日 | BL-0534；G-3 | `dividend_calendar` 模組說明；`contract::DIVIDEND_FIELDS`；`79` §17.3 |
| E5 | 付款日 | `dividend.pay_date`＝可空；v2 寫入端一律空值（FundClear 解析器把同一值同時寫進 `pay_date`，但 `nav_dividend` **不讀**，因為那不是入帳日）；舊引擎另有 `pay_date_est`、`pay_window_est`（推估） | 【F】v2：有欄、恆空；舊引擎：有推估 | 【F】44 §4.3 寫「實際入帳日；尚未公布時為空」，79 §17.3 提案 `payment_date`＝基金端正式發放日、**不得稱銀行入帳日**；兩者衝突，客戶已裁示不得偷改 frozen 44、須走正式 amendment（`DEC-2026-11-02-07`）；**amendment 文字未起草**（BL-0534） | 待決 | 【F】無付款日＝空；不把 `pay_window` 升格為入帳事實（79 §17.3） | BL-0534（D6 G-3 依賴）；D2 | `contract::DIVIDEND_FIELDS`；`nav_dividend` 檔頭（`pay_date` 來源不給→空）；`BL-0534` |
| E6 | 預估 vs 實際 | 舊引擎事件欄 `is_actual`（True＝目標月已有實際基準日紀錄；False＝推估）；`confidence`（`none`／`low`／`medium`／`high`，內部 gating）；`error_band`／`error_worst`；v2 `nav` 有 `is_estimated`，**v2 `dividend` 表沒有預估／實際欄** | 【F】舊引擎有；v2 配息表無 | 【F】67 §8.11 第 4 點（轉錄自 79 §17.2／§17.4）：`is_actual` ≠ `confirmed`；`estimated` 不得寫成 `confirmed`。【F】四態（`confirmed`／`scheduled`／`estimated`／`unavailable`）為 data 層**候選值、非核准**（79 §17.4）。【F】畫面上區分實際／推估屬新增視覺元件，須線框草稿先行（模組說明自述） | 待決 | 【F】`unavailable` 在 UI 呈現仍沿用既有「◇ 資料未備」，不新增第四套文案（79 §17.4） | 四態是否採用＝UI-15 後續 data-semantics Gate【NV 無編號】；BL-0534 欄名與狀態值域對齊 | `dividend_calendar`（`is_actual`、§16.2）；`79` §17.4；`67` §8.11 |
| E7 | 配息是否存在（結果狀態） | A 鏈總結 `DIV_OUTCOME_ROWS`＝`rows`、`DIV_OUTCOME_NONE`＝`none_confirmed`、`DIV_OUTCOME_FAILED`＝`failed`，以及「分辨不出」（`div_outcome_undetermined`） | 【F】有 | 【F】Missing≠0／中性的原則已核准；此四態本身未見客戶核准字彙【NV】 | 必備（配息事件有無）；是否納入＝待決 | 【F】`none_confirmed` 為每個跑過的來源都回報成功取數且無配息列；程式另以 `none_evidenced` 要求每個回空的來源都有「同一來源認得同一代碼」的證據（`code_recognized`，`fund_orchestration`）才算確認；否則「沒抓到」不被說成「沒有配息」 | D2；D3(a)（字彙對照：這四態與 `⬜ 不適用：區間內無配息` 等 44 空狀態的關係）【I】 | `fund_orchestration::DIV_OUTCOME_*`；`nav_dividend::WITHHELD_DIV_OUTCOME_UNDETERMINED`、`TEXT_DIV_NONE` |
| E8 | 配息類別（收益／本金） | `dividend.div_kind`；值域 `income`／`principal`／`unknown`；目前一律 `unknown`（來源沒有區分） | 【F】欄位有、值恆 `unknown` | 【F】44 §4.3 值域；Q5 一律 `unknown`（`nav_dividend` 檔頭） | 待決（缺來源） | 【F】依賴本金類配息佔比的畫面（`HLD-8`）無資料可算；【I】應落「無法判定」類既有字樣 | 新來源不屬本草案；BL-0393 六項（`DEC-2026-10-22-02` G9 登記）中沒有「配息收益／本金」，僅 (3)「含息報酬定義」勉強相關，關聯弱【NV】 | `nav_dividend`（`DIV_KIND_UNKNOWN`）；`73` `HLD-8` 列 |
| E9 | 事件日期可信度（`confidence`、誤差帶、估算依據） | `dividend_calendar` 的 `confidence`、`estimate_error_band`、`anchor_type`、`roll_convention` 等 provenance key | 【F】舊引擎有；v2／ui_v3 無 | 【F】67 §8.11 第 5 點（轉錄）：`confidence` 是 deterministic 內部 gating，**不是** LLM 信心或機率；Final UI 不得當成未校準成功機率；`evidence_count`、誤差窗、估算方法可作 objective evidence | 選備（作者候選：僅限客觀證據欄，不含 `confidence` 字面轉譯） | 缺＝只能呈現「推估」而無依據 | G-3（估算引擎如何進 `ui_v3`，D6） | `dividend_calendar` 模組說明；`67` §8.11 |
| E10 | 吃本金判定與配息相關衍生 | `services/health/dividend.py::classify_eating_principal`（`is_eating = total_return < dividend_yield`）；資料缺＝`eating_principal = None`、狀態字「⬜ 資料未備／無法判定」 | 【F】有 | 【NV】本稿未查客戶對該公式的核准依據（屬投資語意，不在本盤點射程） | 待決（投資語意） | 【F】缺資料時不判為「不吃本金」（`None`，非 `False`） | D2（是否作 Digest 輸入）；與配息資料完整度連動【I】 | `services/health/dividend::_eating_grey`、`EATING_STATUS_UNAVAILABLE` |
| E11 | 配息抓取日期（`fetched_at`）與來源 | 每列 `fetched_at`；來源字串、解析器、幣別出處放在回傳的 `provenance[fund_code]`，**`dividend` 表本身沒有 `source` 欄** | 【F】有 | 【F】44 §4.3 | 必備（`as_of`／provenance 屬 67 §8.6 通則）【I】 | 【F】`fetched_at` 取不到真的取得時間＝整檔不寫（`fetched_at_missing`／`fetched_at_in_future`） | 來源欄是否納入契約＝D2【I】 | `nav_dividend`（檔頭「provenance」段、`WITHHELD_FETCHED_AT_*`） |
| E12 | 通知送達、重試次數、渲染 metadata、通知偏好 | LINE 是否送達／已讀、重試次數、Flex／PNG metadata、通知偏好 | 【NV】本稿未盤點程式 | **已核准 Excluded**：delivery metadata 不得進 Digest／OneBrain fingerprint（67 §8.11 第 1 點）；通知偏好不是 Investment Rule（第 3 點）；【NV】67 §8.11 自稱單組轉錄、須獨立稽核才視為已驗，原文在 79 第 17 節 | **不納入（依上列已核准文字，非作者候選；轉錄未經獨立驗證）** | — | — | `docs/v2/67` §8.11 第 1、3 點 |

### 3.2 日期口徑現況對照（只描述事實；不選用哪一個）

| 概念 | 舊行事曆引擎（`services/dividend_calendar.py`） | v2 `dividend` 表（`nav_dividend`／`contract`） | 79 §17.3 提案（非核准） | 44 frozen §4.3 | 標記 |
|---|---|---|---|---|---|
| 配息基準日 | 推估目標；從 MoneyDJ 第一欄（`date`）取；事件欄命名 `ex_date` | 無此欄 | `record_date` | 無此欄 | 【F】 |
| 除息日 | 解析時另保留 `ex_date`（MoneyDJ 第二欄），非推估目標 | `ex_date`；逐來源逐筆核對欄名；舊路徑旗標 `DIV_DATE_IS_EX_DATE_VERIFIED = False` | `ex_dividend_date` | `ex_date`＝除息日 | 【F】 |
| 付款日 | 推估：`pay_date_est`、`pay_window_est`（基準日＋歷史間隔中位數；缺 `pay_date`＝`None`） | `pay_date` 恆空 | `payment_date`＝基金端正式發放日（不得稱入帳日） | `pay_date`＝「實際入帳日」 | 【F】 |
| 預估入帳區間 | `pay_window_est`（舊語彙「入帳(估)」） | 無 | `estimated_bank_credit_window`；無可支持的 deterministic contract 時為 Missing | 無 | 【F】 |
| 預估 vs 實際 | `is_actual` 布林；`confidence` 內部 | 無（僅 `nav.is_estimated`） | `date_status` 四態（候選） | `nav` 有 `is_estimated`，配息無 | 【F】 |

【F】79 §17.3 還明載：舊線的「入帳(估)」「pay-window」語彙屬既存語意，本輪不改 production copy／code；新 UI 遷移前須先拆開 `payment_date` 與 bank credit window。

---

## 4. 依賴清單（擋路事項指向的 Gate／BL；只列，不代決）

| # | 擋路事項 | 受影響項目 | 依賴的 Gate／BL／DEC | 目前狀態（事實） | 標記 |
|---|---|---|---|---|---|
| D-1 | 資產分母公式與市值基準承接 | H7、H12、H13 | D6 G-1；BL-0542；`DEC-2026-11-04-02`（UI 方案 A 已核准）、`-03`（G-1 方向已核准，但僅授權 G1-①；G1-②／③ 須另批）、`DEC-2026-11-05-02`（G1-②／③ 授權的**事後補登**，要點轉述、未重新追認，見 `DEC-2026-11-08-03`）；G-1 公式未裁 | 待裁 | 【F】 |
| D-2 | 摘要四格口徑 | H12 衍生 | D6 G-4（依賴 G-1）；BL-0542 | 待裁 | 【F】 |
| D-3 | 配息日期語意（基準日 vs 除息日）與配息推估引擎進 `ui_v3` | E3、E4、E5、E6、E9 | D6 G-3；BL-0534（`pay_date` 語意 amendment，文字未起草）；`DIV_DATE_IS_EX_DATE_VERIFIED = False`；`DEC-2026-11-02-07` | 待裁／待起草 | 【F】 |
| D-4 | 狀態詞對映與頁級字樣（`no_holding`／`partial`／`normal`） | H13、H14、E6、E7 | D6 G-5；D3(a)（對照表為唯讀文件，**不是契約**，crosswalk 自述；獨立 QA 狀態見 PR #1175，本稿【NV】） | 待裁 | 【F】 |
| D-5 | 11 項 open gate 逐碼處置 | H4、H6、H10、H11、H14 | D6；見本稿 §2.3 | 待裁 | 【F】 |
| D-6 | 淨值過期天數規則的跨頁語意（今天的定義、適用範圍、未來日期、`>` 或 `>=`、擁有者） | H6、H7 | D7；`DEC-2026-11-05-03`；D3(b)（`stale_after`、conflict）與 D7 建議合併處理（提案、非裁示） | 待裁 | 【F】 |
| D-7 | FX 閘門開放證據軌 | H5、H7、B7 | D8；BL-0217；`DEC-2026-11-08-02`（維持關閉；不以相同方法立即重跑；補跑**未授權**） | 客戶已選：閘門關閉 | 【F】 |
| D-8 | 承重生產者的授權鏈 | H16 | D10；`DEC-2026-11-08-03`（客戶選 B：保留歷史摘要、標示未重新追認、不擴大授權） | 已按客戶選擇登記；追認狀態：未追認 | 【F】 |
| D-9 | 各域 Required／Optional／Excluded 逐項清單與 Digest schema／fingerprint | 本稿全部候選分類 | D2；BL-0527；67 §8.6；`DEC-2026-11-08-02`（D1 採方案 C；D2 未核准） | 待裁 | 【F】 |
| D-10 | 狀態字彙對照與 `stale_after`／conflict 門檻 | H6、H14、E7 | D3(a)／(b)；67 §5.6 第 1、3 項；BL-0527 | (a) 文件整理中、(b) 待裁 | 【F】 |
| D-11 | Rule ID／`rule_version` 格式 | `rule_ref` placeholder | D4-3；67 §5.6 第 4 項 | 待裁 | 【F】 |
| D-12 | 真實 Active Sheet 覆蓋率與分母口徑 | 全部「有資料」宣稱的實證 | D9；BL-0545；`DEC-2026-11-07-03`（探針協定）；客戶暫不提供輸入 | NOT VERIFIED | 【F】 |
| D-13 | 略過列原因碼；持倉列被略過時兩區未浮出 | H1、H2、H14 | BL-0411／F-18（`74` F-18）；open gate `omitted_row_reason_codes_undefined` | BACKLOG 現寫 BL-0411「open→fixed（待獨立稽核）」；狀態以 BACKLOG 與 `74` 第 5 節為準 | 【NV】 |
| D-14 | 兩套同鍵合併規則是否收斂 | H8 | `PROJECT_RULES` 13.3（跨頁一致性）；【NV】未見專屬 BL 編號 | 登記、未裁 | 【F】＋【NV】 |
| D-15 | 配息「收益／本金」來源缺 | E8 | 無既有專屬 Gate；BL-0393 六項無「配息收益／本金」，僅 (3)「含息報酬定義」勉強相關，關聯弱 | 【NV】 | 【NV】 |

---

## 5. 「已有且可靠」vs「有資料但還不能正式用來做投資判斷」（白話）

> 判準（【I】作者自訂，非既有分類）：**已有且可靠**＝有正式程式路徑、有契約或證據檢查、缺值時不造假、且不依賴任何未裁 Gate。**還不能正式用**＝有資料或程式路徑，但依賴未裁的公式、門檻、字彙、閘門，或尚無正式呼叫端。
> **兩組都不代表真實資料已驗證**（BL-0545）。

### 5.1 已有且可靠

| # | 項目 | 依據 |
|---|---|---|
| R-1 | 持倉列的欄位契約與「寫不進就列原因、不補 0」：數量、台幣成本、原幣成本、幣別、類別、保單與基金識別 | 【F】`holding_row_problems`；`alo_holdings::_holding_reasons`（U10）；【I】可靠性僅限程式行為，非真實資料 |
| R-2 | 成本基準的單檔基準值＝`cost_twd`，不讀淨值、不讀匯率 ⇒ 不受匯率閘門與 NAV 過期影響（**「可靠」僅指程式行為**；「淨投資金額」是否等於正式成本語意為【NV】，見 H2／Q2） | 【F】`holdings::basis_value_with_reason` |
| R-3 | 缺值一律 `None`＋機器碼，永不為 0；未涵蓋的台幣金額標「不可計算」；`unproven_zero` 把「來源未完整時的 0」與真實 0 分開 | 【F】`allocation_evidence`（設計與 docstring）；【I】原則已核准，詞彙為內部候選 |
| R-4 | 配息表的寫入前提：每個來源、每一筆都須通過日期、金額、幣別的出處證據；過不了＝不寫、記原因（寧可缺、不猜） | 【F】`nav_dividend::DIV_EX_DATE_EVIDENCE`、`DIV_AMOUNT_EVIDENCE`、`DIV_CCY_EVIDENCE`；【I】資料量因此較保守，覆蓋率未驗 |
| R-5 | 使用者參數留空＝「未設定」、不代填；不算資料狀態件數 | 【F】已核准規則鍵 `user_param_unset`（crosswalk A11） |
| R-6 | 通知送達／重試／渲染 metadata 與通知偏好不進 Digest fingerprint | 【F】67 §8.11 第 1、3 點（轉錄自 79 第 17 節；該節自稱單組轉錄、須獨立稽核才視為已驗，【NV】） |
| R-7 | 「沒配息」與「沒抓到」分開：`none_confirmed` 為每個跑過的來源都回報成功取數且無列，另需 `none_evidenced`（每個回空的來源都有認得同一代碼的證據）才算確認沒配息 | 【F】`DIV_OUTCOME_*`；【NV】字彙本身未見客戶核准 |

### 5.2 有資料但還不能正式用來做投資判斷

| # | 項目 | 為什麼還不能 | 依據 |
|---|---|---|---|
| N-1 | 市值與非台幣基金的市值占比 | 匯率閘門關閉（`fx_absent`）；`ui_v3` 市值基準被擋；市值面無 production 呼叫端 | 【F】H5、H7、B4、B7；`DEC-2026-11-08-02` |
| N-2 | 類別占比與「分母」 | 分母公式 G-1 未裁；`ui_v2` 舊 `_build_alo2` 仍可能對其餘類別顯示 100%（與已核准方案 A 不同，現行測試釘住）；證據物件是內部候選 | 【F】`DEC-2026-11-04-03`「已知落差」；`allocation_evidence` 檔頭 |
| N-3 | 以淨值計算的任何「現值」 | 過期天數規則跨頁語意未裁（D7）；過期 NAV 在共用層仍被計入，僅記 gate；Old UI T7 未驗（轉引 R3，【NV】） | 【F】`holdings::latest_nav_row`；`onebrain_decision_gate…` §2.3 |
| N-4 | Complete Evidence 物件整體 | 內部候選 schema；無 production 呼叫端；授權鏈未重新追認；無根層 as_of | 【F】AUD V1／V2／V12；`DEC-2026-11-08-03` |
| N-5 | 除息日、基準日、付款日的任何「日期」呈現 | 口徑未統一；舊路徑旗標 `False`；`pay_date` 恆空；44 與 79 對 `pay_date` 語意衝突；BL-0534 未起草 | 【F】§3.2；`BL-0534` |
| N-6 | 配息預估日期、入帳窗、誤差帶 | 只在舊引擎；`is_actual`≠`confirmed`；`confidence` 非機率；是否進 `ui_v3` 未裁（G-3） | 【F】`dividend_calendar`；`67` §8.11 第 4、5 點 |
| N-7 | 本金類配息佔比、吃本金判定 | `div_kind` 恆 `unknown`（來源無區分）；判定屬投資語意，未核准納入 Digest | 【F】`nav_dividend`（`DIV_KIND_UNKNOWN`）；【NV】公式核准依據 |
| N-8 | 持股／產業重疊度矩陣格的 0.0 | 雙缺對填 0.0＝「沒比到」不是「不相關」；其他消費者呈現未驗 | 【F】`calc_holdings_overlap`、`homogeneity` 檔頭；【NV】消費者 |
| N-9 | 任何「覆蓋了 X% 真實持倉」的說法 | BL-0545 真實覆蓋率 NOT VERIFIED | 【F】AUD §4 |

---

## 6. 對這兩類真正擋路的待裁問題（每題一句、標 Gate；不含選項、不預設答案）

> 客戶已選（不再問）：缺資料沿用既有「資料未備／無法判定」字樣；FX 閘門關閉、非台幣基金整理原幣資料、無法可靠換算者標「無法判定」。

| # | 問題（一句） | Gate／依賴 |
|---|---|---|
| Q1 | 資產分母要怎麼算，以及缺必要資料的類別在占比中如何處理？ | D6 G-1 |
| Q2 | 「淨投資金額」是否就是這份產品要用的「成本」？ | D6 G-1（【NV】無專屬 Gate） |
| Q3 | 缺淨值、淨值過期、被略過的持倉，在配置圖中各要怎麼處置？ | D6 G-1；BL-0542 待決 (a)；D7 |
| Q4 | 淨值超過幾天算過期，是否全站統一，以及用哪一天當「今天」？ | D7；`DEC-2026-11-05-03` (a)～(e)；D3(b) |
| Q5 | Old UI 的「組合當前市值」是否也要套用同一過期規則？ | D7；三風險 R3（轉引，【NV】） |
| Q6 | 配息要以「基準日」還是「除息日」為準，兩者是否分欄並存？ | D6 G-3；BL-0534 |
| Q7 | 「付款日」與「預估入帳區間」是否按 79 §17.3 拆開，並如何改寫 44 §4.3 的 `pay_date`？ | BL-0534（需 amendment，走 frozen 修改程序） |
| Q8 | 配息日期是否要區分已確認、已公布預定、預估、無法取得四種狀態？ | 79 §17.4 對應的 data-semantics Gate（【NV】編號）；BL-0534 欄名對齊 |
| Q9 | 配息事件（金額、幣別、日期、狀態）要列為 Digest 的必備還是選備？ | D2；67 §8.11 第 2 點 |
| Q10 | 舊行事曆的推估引擎要不要進入 `ui_v3`，若進入其內部信心與誤差帶如何呈現？ | D6 G-3；67 §8.11 第 5 點 |
| Q11 | 11 項 open gate 逐碼要如何處置？ | D6 |
| Q12 | 兩套同鍵持倉合併規則是否收斂成一套？ | `PROJECT_RULES` 13.3（【NV】無 BL 編號） |
| Q13 | 直接持有（DIRECT）持倉在持股頁要不要顯示？ | alo_holdings 檔頭已登記的未定題（【NV】無 Gate 編號） |
| Q14 | 持股重疊度在兩檔皆缺資料時，這一格是否納入本草案並沿用既有「資料未備／無法判定」？ | 無既有專屬 Gate【NV】；D2 |
| Q15 | 資料健康的 stale／conflict 判定標準與狀態字彙對照何時定？ | D3(a)／(b) |
| Q16 | 2026-11-05 的 Evidence 授權鏈是否要重新追認？ | D10（客戶已選保留未追認，`DEC-2026-11-08-03`；是否再追認＝客戶另決） |

---

## 7. 限制與未涵蓋範圍

- 【F】本稿是「輕量盤點」：只涵蓋持倉與配置、配息與事件兩類；**不涵蓋**市場／總體、基金績效、FX／利率／景氣、基金身份跨源對應、資料健康、規則／Risk Cap／Action State、反證；不代替 D2 逐域契約。
- 【NV】本稿**未查證**下列事項：真實 Active Sheet 與真實配息頁面的資料樣態；各 DEC 的客戶逐字原話（多為要點轉述）；Old UI 各畫面如何呈現本稿所列欄位；`ui_v2` 各頁對 `dividend` 表的消費細節；`docs/v2/73`、`74` 的完整內容；`services/dividend_calendar.py` 全檔行為；本機測試未執行。
- 【NV】「文件未見某條裁示」類敘述均以字面符號與本組實際讀過的文件為準，**不宣稱涵蓋所有文件、別名或動態組字串**；本稿未使用「全部」「只有 N」作為窮舉主張，任何此類讀法請以原出處重驗。
- 【I】候選分類（必備／選備／不納入／待決）、「推測關聯」與「已有且可靠」判準均為作者自擬，**不是核准、不是契約欄位**；若客戶採用其中任何詞，須另走 D2 或相應 Gate。
- 【F】本稿沒有新增狀態詞、門檻、公式或 Schema；所有狀態與代碼均引自既有程式或文件，其中 `allocation_evidence` 內的名稱皆為「內部候選、非已核准詞彙」。
- 【F】本稿沒有使用 Missing→0、中性、安全或 HOLD 作為任何缺值的處理；觀察到的既有 `0.0` 填值（H17）只是被登記，不是被採用。

### 單組作者揭露（`CLAUDE.md` §-2 規則 6）

本稿由單一作者組產出；**獨立 QA 已完成一輪並已回修（非 QA 通過；仍待合併前檢查）**。依 `DEC-2026-10-16-05` 風險分級，本稿涉及 data semantics，須至少 1 組真正獨立稽核後才視為已驗。作者已重跑的少數指令：`git grep` 確認 `build_allocation_evidence` 非測試匯入、`NAV_NOT_READY_DAYS = 10`、`DIV_DATE_IS_EX_DATE_VERIFIED` 消費處；其餘事實為讀碼與讀文件所得，標【F】者指「可由所引檔案的文字重現」，**不等於作者在執行環境中運行驗證**。

---

## 附：本檔列數（作者自計）

- §2.1 項目盤點：17 列；§2.2：11 列；§2.3：11 列。
- §3.1 項目盤點：12 列；§3.2 對照：5 列。
- §4 依賴清單：15 列。
- §5.1：7 列；§5.2：9 列。
- §6 待裁問題：16 列。

（回修說明：`DEC-2026-11-08-04` Q4 明定「不新增過期／衝突正式詞、不改門檻」，本稿無任何新增詞或門檻。）
