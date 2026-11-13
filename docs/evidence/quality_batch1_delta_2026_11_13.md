# 品質補強 Batch 1 delta 稽核（Issue #1228）— 覆蓋 delta／New UI2 五頁驗收契約補缺／NAV‧持倉‧配置 lineage

> **統一聲明（適用本檔 §1／§2／§3 全文）**：本檔是研究證據落盤，**非客戶裁示、非授權施工**；基準 main `2f13fade2f848ac78f0277e9169f3786e1cd6486`（#1227 merge）；來源為 GitHub Issue #1228（客戶 2026-11-13 授權的三批品質補強派工之 Batch 1）。三節皆為**單組作者草稿，尚待非作者 QA**；全稱句（「0 命中」「只有 N 處」）皆為單組字面 `git grep`，未經第二組驗證。**Issue 是派工入口，不是授權狀態 SSOT**；授權見 `docs/DECISIONS.md` `DEC-2026-11-13-02`。登記與建議皆不構成動工授權（`CLAUDE.md` §-1）。
>
> 本檔未重錄、未修改任何 Golden 黃金檔，也未改任何 code／tests／workflow／Schema／provider／公式／Sheet／憑證。「推薦」「讀法」一律是專案 AI 讀法，可被客戶推翻。BL-0545 仍是唯一全域 NEXT，本批不取代它。

## 三節總覽（一頁）

| 節 | 一句結論 | 最重要發現 |
|---|---|---|
| **§1 覆蓋 delta** | Issue 只明列五項（NAV 換幣守衛、缺 FX 資產配置分母、`calc_metrics` 1Y estimated window、ISIN 未啟用、Missing／Partial／UNAVAILABLE／未評估分流），第六項未枚舉，待客戶指明；五項中 NAV 換幣守衛已有測試，其餘四項有「現況被鎖住、目標行為無有效測試」的缺口。 | 本機 CPython 3.13 下 8 條黃金／摘要測試紅燈，經 `builtins.sum` 還原實驗確認根因是 **CPython 3.12 起 float `sum()` 改補償加總**（CI 為 3.11），**不是 baseline 漂移、不是程式退化，禁止重錄 Golden**（細節 §1.2-6）。另：`calc_metrics` 估算分支／`or 365`／窗口上界、ISIN 未啟用畫面、缺 FX 不得顯示完整 100% 三者皆無有效斷言。 |
| **§2 五頁驗收契約** | 以 S1 規格已核准／S2 技術已實作／S3 同 head 測試已通過／S4 正式資料已驗證／S5 使用者已驗收五種互不冒充的狀態，逐頁逐列（每頁 12 列）補驗收契約。 | 五頁的 **S4 正式資料已驗證皆為 NOT VERIFIED、S5 使用者已驗收皆為否**；僅 🌍 有 `ui_v3` Preview-only 頁（非 production 入口）；💼／🔍／⚙️ 在 `ui_v3` 無頁、🤖 僅佔位。§2.3 列出 14 項「容易被誤讀為已完成」的冒充風險。 |
| **§3 NAV／持倉／配置 lineage** | 三條鏈結構與 #1225、#1227 一致、未推翻既有結論；補逐維度保留／丟棄與新事實。 | ①B 線經 A 鏈接受選股池手填 ISIN 查得的晨星 secId（`secid_origin="pool_isin_search"`），無測試釘住收或拒（Δ3-02）；②FX 對齊無新鮮度上限、不讀 `value_unit`（Δ3-03）；③`ui_v2` ALO-2 缺 USD 匯率時印現金 100.0%，與證據支線 `denominator=incomplete` 不一致，有持倉被略過時無持倉的目標類別仍印 0.0%（Δ3-04／Δ3-05）；④Golden 紅燈事實登記（Δ3-01）。另 §2 A2：💼 第一屏順序與 `DEC-2026-11-04-01` 已核准順序相反且被測試鎖住。 |

上列發現已登記為 `docs/BACKLOG.md` BL-0548（待客戶裁示；登記不構成動工授權），並於 BL-0342／BL-0453 追加根因線索註記。

## §1 覆蓋 delta 稽核（Issue #1228 Batch 1 第 1 項）

> 性質聲明見本檔頭統一聲明（研究證據；非客戶裁示、非授權施工；單組作者，尚待非作者 QA）。
> 範圍：Issue 寫「既有六項覆蓋 delta」，但**只明列五項**（NAV 換幣守衛、缺 FX 資產配置分母、`calc_metrics` 1Y estimated window、ISIN 未啟用、Missing／Partial／UNAVAILABLE／未評估分流）。**Issue 未枚舉第六項，待客戶指明**；本節覆核其明列的五項，加上實際發現的鄰近項（Golden 版本相依、BL-0545 探針、治理守衛、🌍 Preview AppTest、直讀 `ret_1y_total` 點）。
> 本節是 #1225（`docs/evidence/ui_data_contract_audit_2026_11_12.md`，下稱 #1225 稽核）與 #1227（`calc_metrics_1y_estimate_path_verification_2026_11_13.md`、`d2_min_approval_pack_r_id_1_r_nav_1_2026_11_13.md`，下稱 1Y 驗證／D2 包）的**最小差異**：只補「測試實際跑了沒、跑出什麼、哪裡沒被斷言鎖住」，**不新建 data dictionary、不重做原稽核**。
> 分類詞只用五種：**已有測試／尚無有效測試／僅研究／需 Gate／production NOT VERIFIED**（可複選，標「主」者為主分類）。「已有測試」＝測試檔存在、斷言鎖住該行為、**且本批在下表環境實跑通過**；它**不代表**正式資料已驗證、也不代表 CI 在 Python 3.11 下同樣綠（§1.3 第 1 點）。
> 全稱句（「0 命中」「沒有任何測試」）皆為單組 `git grep`，指令見各項；不含別名／動態組字，**未經第二組驗證**。路徑一律「檔案::符號」，不寫行號。未寫 secret／NAS／Sheet ID。**Golden 黃金檔本批一個位元組都沒動，也不建議重錄。**

### §1.1 覆蓋 delta 總表

| # | 項目 | #1225／#1227 原結論 | 現行 code 符號 | 既有測試（檔::測試名） | 本批實跑（Py 3.13.18） | 分類 | 缺口與下一步（僅文件／測試草案層級） | 需要的 Gate |
|---|---|---|---|---|---|---|---|---|
| 1 | **NAV 換幣守衛** | #1225 §1.4「幣別與單位：已有且可驗證」；D2 包 R-NAV-1 引 `test_nav_幣別缺_整批不寫_不猜不預設USD` 等 | 舊路徑寫入端 `shared/data_quality.py::assess_nav_series_swap`（採用點 `repositories/fund/fund_orchestration.py::_span_extend_insurance_nav`、`services/nav_history_store.py::backfill_to_gs::_rescue_by_isin`）；讀取端 `repositories/fund/fx_and_main.py::_latest_nav_ccy_ok`；New UI `services/v2_tables/nav_dividend.py::resolve_nav_ccy`／`build_nav_table` | `tests/test_nav_currency_swap_guard.py`（30）；`tests/test_unknown_currency_fail_closed_20261010.py`（196，§14 含 `get_latest_nav`）；`tests/test_v2_tables_nav_dividend.py`（104，含 `test_nav_幣別缺_整批不寫_不猜不預設USD`、`test_nav_同一檔多列持倉幣別互相不同_整批不寫`）；`tests/test_nav_history_currency_column.py`（44） | 30／196／104／44 全 passed | **主：已有測試**；副：production NOT VERIFIED、需 Gate | ① 三層守衛各自有測試，但**New UI 的 nav 鏈不經過寫入端換源守衛**（`git grep -c "span_extend\|assess_nav_series_swap\|nav_series_currency" -- services/moneydj_fetcher.py services/v2_tables/nav_dividend.py` 兩檔皆 0）；A 鏈是否可能回非原生報價＝NOT VERIFIED。② 測試檔頭 docstring 仍寫「候選不宣告幣別（如 cnyes）時**仍會換源**」，與同檔 `test_span_extend_blocks_when_candidate_currency_unknown`（2026-10-10 客戶裁示反轉為擋下）相反＝**過期敘述**（文件層小修，不改斷言） | ①屬 identity／data semantics，**只標 Gate，不處置**；②無 Gate |
| 2 | **缺 FX 資產配置分母** | #1225 §2.4：`_build_alo2` 缺 FX 時分母只加總有值類別，是**尚未對齊 `DEC-2026-11-04-02` 方案 A 的已登記落差**（BL-0542 G-1） | `ui_v2/alo/logic.py::_build_alo2`（`denominator = sum(... if v["value"] is not None)`）；New UI 證據層 `services/v2_domain/allocation_evidence.py::ShareFact`（`share_of_covered_pct`＋`covers_all_holdings`）、`build_allocation_evidence` | `tests/test_alo_core_golden.py`（含 `test_缺值不是零_類別層缺值為None_分母不含缺的類別_已知差異照錄`）；黃金情境 `known_diff:usd_missing_twd_valued_twd_100pct`、`known_diff:twd_100pct_with_eur_missing`；`tests/test_v2_domain_allocation_evidence.py::test_share_of_covered_equals_alo_current_pct_over_the_parity_scenarios`；`tests/ui_v3/test_ui_v3_assets_source_contract.py` | 證據層 104 passed／1 skipped；assets_source 34＋60 passed；**alo golden 見列 6（Py3.13 紅，非行為退化）** | **主：已有測試（鎖的是「現況 100.0%」）**；副：**尚無有效測試（方案 A 目標行為）**、需 Gate | **沒有任何斷言要求「缺 FX 時不得顯示完整 100%」**：Golden 與證據層 parity 測試鎖的都是現況（有值類別 100.0%，尾註「合計未涵蓋」）。方案 A 行為驗收（DEC-2026-11-04-02「驗收限制」：缺 USD／其他必要 FX、部分 worksheet skipped）要等 BL-0542 G-1 授權後另寫；本批**只能**把此缺口記為「尚無有效測試」。⛔ 不得為了變綠改 Golden | BL-0542 G-1（formula／data semantics）；`DEC-2026-11-04-02`；FX 閘門 `DEC-2026-11-08-02` |
| 3 | **`calc_metrics` 1Y estimated window** | 1Y 驗證 §0：估算值與量測值**不可區分**；N1 估算路徑在日頻索引**不可達**；真正可達的是長窗**無上界**；`or 365` 與 ×1.4 估算**無測試鎖定** | `services/fund_service.py::calc_metrics`（`_days_span < 7 → max(int(len(s)*1.4),14)`；`_window_actual_days or 365`）；`services/fund_total_return.py::resolve_1y_total_return`（只判下限 `RET_1Y_RESTORED_MIN_WINDOW_DAYS=350`，`shared/signal_thresholds.py`） | `tests/test_fund_metrics.py`（只鎖 ≥350 與短窗 <350）；`tests/test_compute_1y_total_return.py`；`tests/test_ssot_1b_total_return_adr_eating.py` | 16／18／15 passed；**本批獨立重現**（§1.2-3）：盤中 250／251 列→`window_days` 350／351、`status=ok`；252 列同日→365、`ok`；週頻 252 列→1757、`ok`；月頻 60 列→1795、`ok` | **主：尚無有效測試**（估算分支、`or 365`、窗口上界）；副：需 Gate、production NOT VERIFIED | 現有測試只鎖「下限」。可寫成**特徵化測試草案（文字）**：T-1Y-a 盤中索引 250 列→目前 350／`ok`（記錄現況，非期望）；T-1Y-b 0 天跨度→目前 365；T-1Y-c 週頻 252 列→目前 1757 仍 `ok`。⛔ 不得把這些寫成「期望行為」，也不得提議加上界或旗標（公式／語意） | **BL-0427**（待客戶裁示）、BL-0524、BL-0547；New UI 目前對 `calc_metrics` 0 消費 |
| 4 | **ISIN 未啟用** | #1225 §1.1／§2.4：ISIN→MoneyDJ 無來源，維持「尚未啟用」；BL-0530 research-only | New UI 路徑**無任何 ISIN 消費者**：`services/v2_tables/exp_universe.py`（docstring 明言 `isin` 欄一律不讀）；`ui_v3/fixtures/scenarios.py` 僅有 `isin_not_enabled` **假情境**；舊路徑 `pool_repository.resolve_isin`、`nav_history_store::_rescue_by_isin` 仍用 ISIN 補**淨值**（非 identity） | `tests/test_fund_identity_dg2.py`（128；僅 shadow：缺 ISIN 不警告、外部候選 isin 相符則收）；**New UI 範圍（`tests/ui_v2`、`tests/ui_v3`、`tests/test_v2_tables_exp_universe.py`）對 ISIN 字面 0 命中**（`git grep -nw "isin\|ISIN" -- tests/ui_v2 tests/ui_v3 tests/test_v2_tables_exp_universe.py`） | 128 passed（shadow）；exp_universe 22 passed | **主：尚無有效測試**（「🔍 ISIN 入口顯示尚未啟用、不進 resolver／取數鏈」）；副：需 Gate、僅研究 | `DEC-2026-11-01-02` G-E1 要求的畫面行為（顯示「尚未啟用／目前沒有已核准的 ISIN 對照來源」）**在 repo 內沒有實作也沒有斷言**（Batch E lookup 未實作）。現況是「功能不存在」而非「功能被關閉」。可寫**負向守衛草案**：New UI 範圍內不得 import／讀取 `isin`、`resolve_isin`（AST 斷言，不接資料）。⛔ 不得啟用 mapping、不得用名稱／AI 補 | BL-0530、`DEC-2026-11-01-02`、`DEC-2026-10-28-05`（identity） |
| 5 | **Missing／Partial／UNAVAILABLE／未評估分流** | #1225 §1.8：**四～五套並行詞彙**，非單一型別；`DataStatus` repo 0 命中；crosswalk 為單組草稿 | 見 §1.2-5：`shared/ui_semantics/rules.py::ENTRIES`；`ui_v3/viewmodels/common.py::STATUS_*`；`ui_v2/status_class.py::PARTIAL`；`services/v2_domain/allocation_evidence.py::NOT_EVALUATED／VAL_INCOMPLETE／DEN_INCOMPLETE`；`services/fund_total_return.py::resolve_1y_total_return`（`status="unavailable"`）；`services/fund_position.py::UNAVAILABLE_REASON_TEXT` | `tests/test_bl0441_missing_semantics.py`（39）；`tests/ui_v2/test_p3_page_status_logic.py`（73）；`tests/ui_v2/test_alo_logic.py`（146）；`tests/ui_v3/test_ui_v3_semantics_rules.py`（98）、`test_ui_v3_viewmodel_contract.py`（46）、`test_ui_v3_market_page_adapter.py`（40）；`tests/test_v2_domain_allocation_evidence.py`（104）；`tests/test_compute_1y_total_return.py`（18） | 以上全 passed | **主：已有測試（各詞彙內部）**；副：**尚無有效測試（跨詞彙對映）**、需 Gate | 每一套詞彙**各自**有測試；但**沒有任何單一斷言**把「Missing／Partial／UNAVAILABLE／未評估」跨層對映鎖住（`git grep -l "NOT_EVALUATED" -- tests` 與同檔含 `STATUS_MISSING`／`"missing"` 的交集為空）。`data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 仍是研究草稿。⛔ 不得把 UNAVAILABLE 讀成 0／中性／正常；統一詞彙屬語意取捨 | BL-0540 G-2／G-3；BL-0542 G-5 |
| 6 | **Golden 版本相依（新發現）** | #1225／#1227 皆自陳「未執行任何測試」；BL-0342／BL-0453 登記「本機紅、main 紅、CI 綠，**root cause 未查**」 | `ui_v2/alo/logic.py::_build_alo2` 內 `total = sum(r["_value"] for r in included)`；黃金檔 `tests/fixtures/alo_core_golden_before.json`（header `python: 3.11.18`） | `tests/test_alo_core_golden.py`、`tests/test_alo_core_golden_mutations.py`；同族 `tests/ui_v2/test_hld_logic.py`、`test_hld_read_failure_logic.py`、`test_rulings_2026_10_18b_logic.py` | **Py3.13：alo golden 2 failed、mutations 1 failed；hld 兩檔 4 failed；rulings 1 failed**。換成 3.11 直譯器跑同一矩陣：**逐位元組相同**。把 `sum` 換成左到右逐項相加（3.11 語意）後 **以上 8 條全綠**（§1.2-6） | **主：尚無有效測試**（對「非 3.11」直譯器）；副：production NOT VERIFIED | **根因＝CPython 3.12 起內建 `sum()` 對 float 改用補償加總**，非黃金檔漂移。CI 固定 Python 3.11.18 ⇒ CI 綠。缺口：① 這 8 條沒有版本守衛（同 repo 的 `test_v2_domain_allocation_evidence` 已有 3.11 釘版 skip 先例）；② BL-0342／BL-0453 尚未記根因；③ production Python 版本 repo 內查不到＝NOT VERIFIED。**禁止重錄黃金檔、禁止放寬容差** | 無客戶 Gate（環境／測試守衛，總管讀法）；若要改 CI Python 版本屬基礎設施決定 |
| 7 | **BL-0545 覆蓋率探針** | #1225 §1.8：固定輸出 `real_active_sheet_coverage: "NOT VERIFIED"`、`admission: "NOT DEFINED"`；live 模式 NOT IMPLEMENTED | `scripts/bl0545_coverage_probe.py` | `tests/test_bl0545_coverage_probe.py`（T1～T10，離線注入） | **45 passed**（前階段缺 `requests` 的 37 failed 是環境缺件，本批有 `requests 2.34.2`，已排除） | **主：已有測試**；副：**production NOT VERIFIED**、需 Gate | 測試證明「探針邏輯離線正確」，**不證明任何真實 Active Sheet 覆蓋率**。唯一全域 NEXT 維持 BL-0545（BLOCKED，需自願合法輸入）；專案 AI 不得要求憑證或探 live | BL-0545、`DEC-2026-11-07-03` |
| 8 | 治理完整性守衛 | Issue 要求先確認並重用 | `docs/v2/CONSTITUTION.md` 存檔、`docs/v2/57_amendment_8_directional_judgment.md` | `tests/test_constitution_archive_integrity.py`、`tests/test_amendment_8_integrity.py` | 2 passed；9 passed | **主：已有測試** | 只鎖 sha256／存檔不變，**不涉資料語意**；本批未改任何受守衛檔 | 無 |
| 9 | 🌍 ui_v3 Preview 頁 | #1225 §2.3：Preview 已實作並有 live 接線；**非 production** | `ui_v3/pages/mkt.py`、`ui_v3/adapters/market_page.py` | `tests/ui_v3/test_ui_v3_market_page_apptest.py` | 17 passed（4.70s；AppTest，無外網） | **主：已有測試**；副：**production NOT VERIFIED** | AppTest 綠 ≠ Streamlit Cloud 正式入口（repo 內查不到，NOT VERIFIED，#1225 D15）≠ 使用者已驗收 | BL-0535（cutover） |
| 10 | 鄰近：直讀 `ret_1y_total` 點 | 1Y 驗證 F-C：三處 UI 直讀、繞過 350 天閘門 | `ui/tab2_single_fund.py`、`ui/tab3_portfolio.py`（`"1Y含息%(還原淨值)": _m_rd.get("ret_1y_total")`）、`ui/helpers/fund/checkup.py::_ret_1y_total`、`services/health/grade.py` | （未逐點查測試） | NOT RUN | **僅研究**（本批只確認「直讀點存在」，**未逐點判斷是否繞過閘門，不重驗 F-C**） | 屬 Old UI；New UI 對 `ret_1y_total` 0 消費（`git grep -n "ret_1y_total" -- ui_v2 ui_v3 services/v2_tables services/v2_domain` 無輸出） | BL-0427 |

### §1.2 逐項細節

**1. NAV 換幣守衛**
- 證據 A（測試鎖定）：`tests/test_nav_currency_swap_guard.py` 30 條，分 L0 判定器（`normalize_iso_ccy` 不猜、`nav_currency_verdict`）、L1 provenance（晨星／Yahoo 序列自報幣別）、L1／L2 採用點（`test_span_extend_refuses_currency_swap`、`test_backfill_refuses_currency_swap_and_still_writes_the_right_series`、`test_backfill_does_not_convert_currency`＝不換算）。實跑 30 passed／0.18s。
- 證據 B（讀取端）：`repositories/fund/fx_and_main.py::_latest_nav_ccy_ok` 對非原生報價來源「只有 match 放行」；判定本身例外→拒用。對應測試在 `tests/test_unknown_currency_fail_closed_20261010.py` 的 §14（`get_latest_nav`），**沒有測試以函式名 `_latest_nav_ccy_ok` 直接呼叫**（`git grep -n "_latest_nav_ccy_ok" -- tests` 無輸出），屬間接覆蓋。
- 證據 C（New UI 路徑不同機制）：`services/v2_tables/nav_dividend.py` 的 `nav.ccy` 只收持倉手填或 meta 自報，衝突／缺失→整批不寫；`tests/test_v2_tables_nav_dividend.py` 104 passed。該路徑**不引用**上面兩條守衛（見 §1.1 列 1 指令）。
- 缺口：測試檔頭「已知破口：候選不宣告幣別仍會換源」為舊敘述；實際斷言已反轉（`test_span_extend_blocks_when_candidate_currency_unknown`）。**僅文件過期，斷言無誤。**

**2. 缺 FX 資產配置分母**
- 證據 A：`ui_v2/alo/logic.py::_build_alo2` 分母＝`sum(v["value"] for v in values.values() if v["value"] is not None)`；全缺才走 `ALO-GAP-分母全缺`。
- 證據 B：Golden 明文凍結此現況——檔頭「已知差異（照現況錄下，不修）」；情境 `known_diff:usd_missing_twd_valued_twd_100pct`（核心缺 USD 匯率、衛星 TWD 有值→衛星 `_current_pct == 100.0`，`tail_lines == ["合計未涵蓋 核心"]`）。本批在 3.13 實查：含「100.0%」且帶「缺換算匯率」的情境共 6 個（`mv:partial_fx_missing_core`、`mv:partial_missing_sat`、`mv:partial_missing_with_unclassified`、兩個 `known_diff:*`、`scenario:with_missing_category_mv`）。
- 證據 C（New UI 證據層）：`allocation_evidence.py::ShareFact` docstring 明言 `share_of_covered_pct` 不是總資產占比，除非 `covers_all_holdings`；`test_share_of_covered_equals_alo_current_pct_over_the_parity_scenarios` 鎖定它與 ui_v2 百分比一致。**所以證據層「有誠實欄位」，但沒有任何測試要求畫面在 `covers_all_holdings=False` 時不得顯示完整 100%**（那是方案 A 的 UI 行為，`ui_v3` 💼 頁未註冊）。
- 結論：**「現況被鎖」與「裁示目標被驗」是兩回事**；後者目前 0 斷言。這與 #1225 的「已登記落差」一致，本批補的是「確認確實沒有任何紅燈測試在等這個行為」。

**3. `calc_metrics` 1Y estimated window**（獨立重現，未信任 1Y 驗證的數字）
- 指令：以 `venv313` 對 `services.fund_service.calc_metrics` 餵合成序列（單調上升淨值，無外網），再經 `resolve_1y_total_return`。

| 序列 | `ret_1y_window_days` | `status` |
|---|---|---|
| 盤中 5 分鐘 250 列 | 350（×1.4 估算） | ok |
| 盤中 5 分鐘 251 列 | 351 | ok |
| 盤中 5 分鐘 252 列（同日，跨度 0 天） | 365（`or 365`） | ok |
| 營業日 253 列 | 353（量測） | ok |
| 營業日 250 列 | 349（量測） | unavailable／`window_short` |
| 週頻 252 列 | 1757 | ok（無上界） |
| 月頻 60 列 | 1795 | ok（無上界） |

- 與 1Y 驗證的差異：營業日 250 列、月頻 60 列的天數與其表（347、1796）差 1～2 天，**係合成日期起點不同，非行為差異**；其餘（350／351／365／1757 級距）與其結論一致。
- 「無測試鎖定」自查：`git grep -nE "_days_span|len\(s\) ?\* ?1\.4|or 365|window_days *== *365" -- tests` 無相關命中；`git grep -nE "RET_1Y_RESTORED_(MAX|UPPER)" -- '*.py'` 無輸出（無上界常數）。
- 結論：1Y 驗證 §0 的四項判定**本批全部獨立重現**。可達性（盤中索引）仍以 1Y 驗證為準，本批不重驗 NAV 來源粒度。

**4. ISIN 未啟用**
- 證據 A：`git grep -nw "ISIN" -- ui_v2 ui_v3 services/v2_tables services/v2_domain` 僅命中 `ui_v3/fixtures/scenarios.py`（FAKE 情境）；`exp_universe.py` 為「isin 不讀」的 docstring 宣告。
- 證據 B：`DEC-2026-11-01-02` G-E1 採 A＋C：ISIN 入口保留、顯示尚未啟用、不進 resolver／取數鏈、不用名稱／AI 補。**程式碼層沒有這個入口**（#1225 §2.4 🔍：Batch E lookup 未實作）。
- 證據 C：舊路徑仍使用 ISIN（`repositories/fund/sources.py` 呼叫 `resolve_isin`；`services/nav_history_store.py::backfill_to_gs::_rescue_by_isin`）——用途是補**淨值序列**，與 identity 無關，且受 NAV 換幣守衛約束（列 1）。**不要把「New UI 未啟用 ISIN」讀成「repo 不用 ISIN」。**
- 結論：「尚無有效測試」＝沒有任何測試證明 New UI 範圍不消費 ISIN／不顯示對照結果；負向 AST 守衛是文件層草案，不需 Schema／provider。

**5. Missing／Partial／UNAVAILABLE／未評估分流**（逐詞彙對映，皆為「檔案::符號」，已讀碼）

| 概念 | 符號 | 層 | 鎖定測試 |
|---|---|---|---|
| Missing（缺值） | `ui_v3/viewmodels/common.py::STATUS_MISSING`；`ui_v2/status_class.py::MISSING`（資料未備）；`rules.py` key `missing` | VM／頁級／呈現 | `test_ui_v3_viewmodel_contract.py`、`test_p3_page_status_logic.py`、`test_ui_v3_semantics_rules.py` |
| Partial（只評估一部分） | `ui_v2/status_class.py::PARTIAL`；`allocation_evidence.py::VAL_INCOMPLETE／DEN_INCOMPLETE` | 頁級／證據層 | `test_p3_page_status_logic.py`（8 處引用）、`test_v2_domain_allocation_evidence.py` |
| UNAVAILABLE（算不出／無法判定） | `fund_total_return.py::resolve_1y_total_return` 回 `status="unavailable"`＋`reason`；`fund_position.py::UNAVAILABLE_LABEL_PREFIX`；VM `STATUS_UNDETERMINED` | 服務層／VM | `test_compute_1y_total_return.py`、`test_ui_v3_viewmodel_contract.py` |
| 未評估 | `allocation_evidence.py::NOT_EVALUATED`（`VAL_`／`CHART_`／`NAV_STATE_` 別名） | 證據層 | `test_v2_domain_allocation_evidence.py`、`test_allocation_evidence_mutations.py` |

- 關鍵觀察：`UNAVAILABLE` 在 repo 內是**概念名**，不是單一列舉型別（`DataStatus` 0 命中，與 #1225 一致）；`infra/personal_oauth.py` 另有一個同名但語意無關的 `ec.UNAVAILABLE`（OAuth 錯誤碼），**不要與資料狀態混用**。
- Missing≠0 的測試鎖定（New UI 路徑）：`tests/test_bl0441_missing_semantics.py`（39 passed）、`tests/test_alo_core_golden.py::test_缺值不是零_*`、`resolve_1y_total_return` 對缺值回 `unavailable` 而非 0。
- 缺口：四套詞彙各自被鎖，**跨詞彙對映無單一斷言**；且 `data_state_vocabulary_crosswalk_d3a_2026_11_08.md` 為草稿。是否合併詞彙＝語意取捨，**只標 Gate**。

**6. Golden 版本相依（本項最重要的新發現）**

*起因*：本批在隔離環境（CPython 3.13.18，pandas 2.3.3，numpy 2.5.4）實跑 `tests/test_alo_core_golden.py`，`test_整份矩陣_工作樹與黃金檔逐位元組相同` 與 `test_逐情境相同[alo2_family-cost:near_tied_leaders_within_1e9]` 失敗；`tests/test_alo_core_golden_mutations.py::test_對照組_未突變的載入器重現黃金檔` 失敗。其餘 274＋52 條通過。

*CI 到底跑不跑這組*（讀碼＋CI 步驟）：
- `tests/test_alo_core_golden*.py` **未標 `slow`**；`pytest.ini` `addopts` 只有 `--strict-markers`；`pytest -m "not slow" --collect-only` 對兩檔收集 278 條、`-m slow` 收集 0。
- `.pre-commit-config.yaml` 的 `pytest-smoke` hook 為 `python -m pytest -q -m "not slow"`、`always_run: true`；`.github/workflows/pr-check.yml` Fast checks 以 `pre-commit run --all-files` 執行，`python-version: "3.11"`。⇒ **這組測試屬 Fast lane（會擋合併）**。
- CI 實際直譯器：main run `43322433112`（head `6dcb51f8`）Schema gate 日誌的 setup-python 快取鍵含 `python-3.11.18`；main run `43340239112`（head `2f13fade`）Fast checks／Schema gate／Visual 皆 `success`，Slow 在查詢時仍 `in_progress`。**CI 日誌未取到逐條測試行（僅取尾段），故「該兩檔在 CI 實際被執行並通過」來自靜態推導＋job conclusion，非逐條日誌證據。**
- CI 的 numpy／pandas 實際版本：**NOT VERIFIED**（日誌尾段不含；`requirements.txt` 為 `pandas>=2.3.3,<3.0`、`numpy>=2.3.2,<2.6`、無 lock 檔；本批 venv 版本落在同一區間）。這點與根因無關（下述矩陣不需要 numpy／pandas）。

*根因（三段證據，皆可重現）*：
1. **黃金檔錄製環境**：header `python: 3.11.18`。
2. **同一矩陣、不同直譯器**（`G.run_matrix(G.live_namespace())` 與黃金檔 `strings`＋`matrix` 逐位元組比對；該矩陣不需 numpy／pandas）：`/usr/bin/python3.11`（3.11.18）→ **IDENTICAL**；`/usr/bin/python3.12`（3.12.3）→ DIFFERENT，唯一差異情境 `alo2_family/cost:near_tied_leaders_within_1e9`；`venv313`（3.13.18）→ 同一情境 DIFFERENT。
3. **機制**：該情境三筆成本 `[5500.0000003, 2499.9999998, 1999.9999999]` 的 `sum()`：3.11.18＝`9999.999999999998`，3.12.3 與 3.13.18＝`10000.0`；左到右逐項 `+=` 則三者皆 `9999.999999999998`。衛星占比 `2499.9999998/total*100`：3.11＝`24.999999998000003`（黃金檔值），3.12＋＝`24.999999997999996`。差異欄位**只有** `_current_pct`、`_diff`、`_in_total` 三種**內部浮點欄**（尾差 ~1e-15），`current_text`（"25.0%"）等所有文字欄位相同；`page_model_sha256` 因而不同。
4. **反證（因果確認）**：在 3.13 於 pytest 啟動前把 `builtins.sum` 換成左到右逐項相加（見下方 shim），**alo golden＋mutations 277 passed／1 skipped；`tests/ui_v2/test_hld_logic.py`＋`test_hld_read_failure_logic.py` 264 passed；`test_rulings_2026_10_18b_logic.py` 24 passed**。同一組在未加 shim 的 3.13 為 3＋4＋1＝8 failed。BL-0342 記載的 `4b599a9f2b3f` 在 3.12.3 與 3.13.18 皆重現（3.11.18 為預期的 `6347d81de348`）。

```python
# 僅用於實驗（一次性診斷，未入庫）：還原 3.11 的 float sum 語意；須在 pytest.main(...) 之前執行
import builtins

def _naive_sum(it, /, start=0):
    acc = start
    for x in it:
        acc = acc + x          # 左到右逐項相加
    return acc

builtins.sum = _naive_sum
```

*判斷（單組，待非作者 QA）*：**環境相依（CPython minor 版本），不是 baseline 漂移，也不是程式退化。** BL-0342（hld 黃金雜湊，3.13 紅／3.11 綠）、BL-0453（`test_rulings_2026_10_18b_logic` md5）與本項**同一機制**，三者目前在 BACKLOG 皆標「root cause 未查」。repo 內**已有三處承認並吸收此機制**：`tests/test_v2_domain_allocation_evidence.py::test_legacy_differential_old_callers_get_the_old_output`（版本不符 `pytest.skip`）、`tests/test_allocation_evidence_mutations.py`（兩處 `pytest.skip`，理由寫 compensated sum）、`tests/test_v2_domain_port.py::_SUM_MODE`（雙模式期望值）——**但 alo golden／hld／rulings 這 8 條沒有**。

*風險與限制*：
- 守衛只在 3.11 保護這些行為；若 **production 直譯器為 3.12+**（repo 內查無 `runtime.txt`／`.python-version`／pin；Streamlit Cloud 實際版本＝**NOT VERIFIED**），畫面文字在本情境不變，但內部浮點值與黃金檔相差 ~1e-15，**黃金檔不再代表該環境**。
- 本批在 3.11 直譯器只跑了「不需第三方套件的 ALO 矩陣與 HLD 摘要」；**沒有**在 3.11 + 完整依賴下跑過整套 pytest（隔離環境無 3.11 的 pandas／pytest）。
- 本批僅對上列 8 條做了 shim 驗證；**不宣稱全 suite 在 3.13 的失敗都是這個原因**（`tests/ui_v2` 其餘檔本批 NOT RUN）。

*處置建議（文件／測試層，皆**非**客戶 Gate，總管讀法）*：(a) BL-0342／BL-0453 補記根因（文件）；(b) 另案評估對這 8 條加 3.11 版本守衛（沿用 `test_v2_domain_allocation_evidence` 前例），需 ≥1 組非作者 QA，因為它改變「在哪個直譯器受保護」的語意；(c) 查證 production 直譯器版本（需客戶或 Cloud 設定證據）。⛔ **禁止**：重錄黃金檔、放寬比對容差、改 `sum` 為 `math.fsum` 去「對齊」黃金檔（皆等於改測試語意或公式）。

**7～10.** 見 §1.1 表；列 7 說明：`test_bl0545_coverage_probe.py` 45 passed 僅證明離線探針邏輯，真實覆蓋率仍 NOT VERIFIED。列 9：AppTest 17 passed 是 Preview 證據，不是 production 證據。

### §1.3 本批測試實跑全表

環境：**CPython 3.13.18**（`venv313`）；pandas 2.3.3、numpy 2.5.4、streamlit 1.59.2、pytest 9.2.0、pandera 0.36.0、requests 2.34.2、scipy 1.18.1。**CI：CPython 3.11.18**（setup-python 快取鍵）；CI 的 numpy／pandas／streamlit 實際解析版本 NOT VERIFIED。指令統一為 `<venv python> -m pytest <file> -q -p no:cacheprovider --no-header`，於 `git archive HEAD` 解出後 `git init && git add -A && git commit` 的副本內執行，副本為一次性暫存目錄（不入庫）；repo 工作樹未動。

| 測試檔 | 結果 | 耗時 |
|---|---|---|
| `tests/test_alo_core_golden.py` | **2 failed**（`test_整份矩陣_*`、`test_逐情境相同[alo2_family-cost:near_tied_leaders_within_1e9]`）、222 passed、1 skipped | 3.82s |
| `tests/test_alo_core_golden_mutations.py` | **1 failed**（`test_對照組_未突變的載入器重現黃金檔`）、52 passed | 6.33s |
| `tests/test_nav_currency_swap_guard.py` | 30 passed | 0.18s |
| `tests/test_bl0545_coverage_probe.py` | 45 passed | 0.36s |
| `tests/test_constitution_archive_integrity.py` | 2 passed | 0.05s |
| `tests/test_amendment_8_integrity.py` | 9 passed | 0.10s |
| `tests/test_v2_domain_alo_core.py` | 59 passed、2 skipped（拿不到 `1f260bfc` 歷史＝淺層 clone） | 0.38s |
| `tests/test_nav_history_currency_column.py` | 44 passed | 0.24s |
| `tests/test_unknown_currency_fail_closed_20261010.py` | 196 passed | 2.14s |
| `tests/test_v2_tables_nav_dividend.py` | 104 passed | 0.37s |
| `tests/test_v2_tables_nav_chain_handover.py` | 43 passed | 1.04s |
| `tests/test_v2_tables_alo_holdings.py` | 129 passed | 0.52s |
| `tests/test_v2_tables_fund_keys.py` | 114 passed | 0.30s |
| `tests/test_v2_tables_personal_session.py` | 29 passed | 0.19s |
| `tests/test_v2_tables_exp_nav.py` | 49 passed | 0.59s |
| `tests/test_v2_tables_exp_profile.py` | 168 passed | 0.48s |
| `tests/test_v2_tables_exp_universe.py` | 22 passed | 0.28s |
| `tests/test_v2_tables_dividend_chain.py` | 114 passed | 1.42s |
| `tests/test_v2_tables_contract_settings.py` | 21 passed | 0.15s |
| `tests/test_v2_tables_market_view.py` | 59 passed | 0.52s |
| `tests/test_v2_tables_market_indicator.py`／`_exchange_tz`／`_fred`／`_fx_prev_day`／`_fx_ccy` | 27／73／23／29／25 passed | 各 ≤0.52s |
| `tests/test_v2_tables_masker_factory_equivalence.py`／`_masking.py` | 12／73 passed | ≤0.24s |
| `tests/test_v2_tables_settings_store.py`／`_settings_store_page.py` | 70／71 passed | 0.71s／0.42s |
| `tests/ui_v3/test_ui_v3_market_page_apptest.py` | 17 passed | 4.70s |
| `tests/test_v2_domain_allocation_evidence.py` | 104 passed、1 skipped（釘 3.11.18） | 1.54s |
| `tests/test_allocation_evidence_mutations.py` | 99 passed、2 skipped（compensated sum） | 13.24s |
| `tests/test_bl0441_missing_semantics.py` | 39 passed | 0.32s |
| `tests/ui_v2/test_p3_page_status_logic.py` | 73 passed | 19.03s |
| `tests/ui_v2/test_alo_logic.py` | 146 passed | 1.63s |
| `tests/test_compute_1y_total_return.py`／`test_fund_metrics.py`／`test_ssot_1b_total_return_adr_eating.py` | 18／16／15 passed | ≤0.51s |
| `tests/ui_v3/test_ui_v3_semantics_rules.py`／`_viewmodel_contract.py`／`_market_page_adapter.py` | 98／46／40 passed | 0.48s／0.12s／4.47s |
| `tests/ui_v3/test_ui_v3_assets_source_contract.py`／`_mutations.py` | 34／60 passed | 0.38s／3.92s |
| `tests/test_fund_identity_dg2.py` | 128 passed | 1.99s |
| `tests/test_nav_table_golden_c3a.py`／`test_nav_dividend_golden_c3a.py` | 40／53 passed（其他黃金檔**未**受 sum 影響） | 3.20s／1.89s |
| `tests/ui_v2/test_hld_logic.py -k 第2件反向控制` | **1 failed**（`full_then_badrange/HLD-2` 摘要 `4b599a9f2b3f`，預期 `6347d81de348`；＝BL-0342） | 0.72s |
| 實驗：`test_hld_logic.py`＋`test_hld_read_failure_logic.py`（未加 shim） | 4 failed、260 passed | 21.75s |
| 實驗：`test_rulings_2026_10_18b_logic.py`（未加 shim） | 1 failed（md5；＝BL-0453）、23 passed | 2.23s |
| 實驗（加 `sum` shim，見 §1.2-6）：alo golden＋mutations／hld 兩檔／rulings | 277 passed＋1 skipped／264 passed／24 passed | 9.54s／32.61s／2.31s |
| 1Y 重現腳本（`calc_metrics`＋`resolve_1y_total_return` 合成序列，7 案） | 結果見 §1.2-3 | <10s |

**限制**：(1) 上表為 Py 3.13，**不等於 CI（3.11）結果**；(2) 未跑整套 `tests/`、未跑 `slow` lane、未跑 Playwright 瀏覽器測試、未跑 pre-commit；(3) `main` run `43340239112` 的 Slow lane 於查詢時 `in_progress`，本節不引用其結論；(4) 隔離環境無外網，所有測試為離線。

### §1.4 Agent 角色與任務路由唯讀核對（不是施工；**未建立任何 agent 檔**）

> 客戶預定第一批三個專業 Agent：`fund-nav-data`、`fund-governance-auditor`、`fund-independent-qa`；每個需有 Role／Trigger／Inputs／Tools／Forbidden／Output／Escalation，正式建立於 `.claude/agents/`，排在 Batch 3。**以下為草案，Batch 3 前不落成 agent 檔。**

**(a) repo 現況可直接當依據的角色／路由規則**
- `.claude/` 目錄目前**只有 `worktrees/`**（`git ls-files | grep -E "^\.claude|agents"` 無輸出）＝尚無任何 agent 定義。
- `CLAUDE.md` §-2：總管（主對話）拆任務、定規格、派工、複驗，**不自己寫實作**；執行 AI（subagent）依規格調查／實作／測試（規則 1～2）；調查與稽核獨立分派、不可自己查自己（規則 4）；全稱句要嘛獨立驗要嘛標「未驗」（規則 6）。§-1.5 v2：執行組具名編制（架構與前端／資料工程／品管與紅隊稽核，**職能分類，非併發上限**）；v3 `00` 四組含「計算服務組」。
- `PROCESS.md` §8：角色鏈 Architect→Coder→QA Auditor（獨立）→UAT；QA／UAT 必須是獨立 subagent；退回迴圈受 §7「至多 3 次」與 §5「連 2 次無進展即停機」約束。
- `PROJECT_RULES.md` §8：實作者不得自己驗收自己；風險分級（低風險文字可自驗；治理規則、data semantics、investment meaning、formula、identity、freshness、provenance、migration、destructive cleanup 至少 1 組真正獨立稽核；資安／重大合規 2 組）。§5.1：Model／Effort 由總管依風險選擇（表列 Haiku／Sonnet／Opus 預設）。§4：Stop／Decision Gate。§13.4：Anti-Bloat（最小充分 audit、Batch ≤3 項、文件不重複 SSOT、不氾濫 Gate）。

**(b) 三角色對應近期 PR 實例**（以 #1225／#1227 的工作類型對映；**對映為本組讀法**）

| 角色（草案） | 對應工作類型 | 近期實例 |
|---|---|---|
| `fund-nav-data` | NAV／FX／幣別／as-of／來源 lineage 的**唯讀**盤點與契約對照 | #1225 稽核 §1.1～§1.6（資料來源、快取、身份、NAV、日期、FX）；#1227 D2 包 R-ID-1／R-NAV-1；Batch 1 第 3 項（lineage delta） |
| `fund-governance-auditor` | DEC／BL／HANDOFF／PROJECT_RULES 一致性、Gate 判定、登記不構成授權、全稱句限度標註 | #1225 §5 G1～G13；`gates_and_governance_diff_2026_11_12.md`；各 PR 的 BACKLOG／DECISIONS／HANDOFF 同步 |
| `fund-independent-qa` | 非作者 QA：重跑測試、重現指令、對照原宣稱、查「作者自驗」缺口 | #1225／#1227 各自「非作者 QA 兩輪 MERGE-READY」；1Y 驗證對 N1 的獨立重現；本節 §1.2-3／§1.2-6 |

**(c) 必須逐條寫進 Forbidden 的既有硬規則（附出處）**

| Forbidden（草案） | 出處（檔::節） |
|---|---|
| `fund-independent-qa` 不得驗收自己編修的內容；作者與 QA 不得同一 agent／同一 session 脈絡 | `CLAUDE.md` §-2 規則 4；`PROJECT_RULES.md` §8；`PROCESS.md` §8 獨立性 |
| 三角色**不得自取客戶 Decision Gate 權限**（新／替換 production source、公式／投資語意、identity、threshold、frozen 文件、產品方向、destructive migration…） | `PROJECT_RULES.md` §4（`DEC-2026-10-16-03`）；`CLAUDE.md` §-1、§-1.5.0 |
| 不得把已確認 bug 且只有一個安全修法的事包裝成客戶裁示（反向禁令）；也不得把真 Gate 當 bug 自行修 | `PROJECT_RULES.md` §4「反向禁令」、§13.4 第 6 點 |
| 不改 Sheet Reader／Writer／Secrets／OAuth scope／callback／credential／token；不請求憑證；不探 live | Issue #1228「施工、QA、交接硬界線」；`PROJECT_RULES.md` §13.2 第 8 點（Active Sheet／credential 由 ⚙️ 管）；#1225 §2.4 ⚙️；`docs/DECISIONS.md` `DEC-2026-11-07-03`（BL-0545 專案 AI 不得請求憑證） |
| 不改正式 source／provider／Schema／公式／門檻；不改凍結 `docs/v2/44`、子法 1／57 | Issue #1228；`PROJECT_RULES.md` §4；`tests/test_constitution_archive_integrity.py`、`tests/test_amendment_8_integrity.py` 的守衛 |
| 不啟用 **D2**（核准欄位數 0）、**FX**（`FX_OBS_DATE_RULE_VERIFIED=False`）、**DG2**（`DG2_SHADOW_ENABLED=False`）、**ISIN**（無核准對照來源） | `DEC-2026-11-11-04`；`DEC-2026-11-08-02`；`DEC-2026-10-28-05`／`DEC-2026-10-29-01`；`DEC-2026-11-01-02`（BL-0530） |
| 登記（BL／evidence／草案）不等於動工授權；evidence 草稿不等於客戶裁示 | `CLAUDE.md` §-1；`docs/evidence/` 各檔「非客戶裁示、非授權施工」檔頭慣例 |
| 不重錄 Golden baseline 讓紅測變綠；不放寬比對容差 | `tests/test_alo_core_golden.py` 檔頭「黃金檔不得以改動後的程式重錄」；Issue #1228 Batch 1 驗收標準 |
| 不把 UNAVAILABLE／缺值當 0、中性或正常 | `PROJECT_RULES.md` §13.1（Missing≠0）；`CLAUDE.md` §1 |

**(d) 已知衝突或空缺**
1. **工具權限 vs 總管不寫實作**：`CLAUDE.md` §-2 規則 2 限制的是**總管**；agent 是**執行 AI**，本就可寫檔。空缺在於：`fund-governance-auditor`／`fund-independent-qa` 是否給 Edit／Write 權限。草案建議：兩者**預設唯讀（Read／Grep／Glob／Bash 唯讀）**，產出寫到 repo 以外的暫存區，由總管派執行組併入 repo——這與規則 5「寫入檔案一律派工」相容；但「是否允許 QA 寫 evidence 檔」需 Batch 3 決定。
2. **風險分級 vs agent 配置**：`PROJECT_RULES.md` §8 的稽核組數取決於**任務風險**，不取決於 agent 種類；agent 定義無法自行判斷級別，必須由派工單帶入（`CLAUDE.md` §-2.A 第 5 款「派工單本身納入稽核範圍」）。
3. **Model／Effort**：§5.1 規定由總管判斷、不問客戶；agent 檔若寫死 `model` 欄位，可能與當下 §5.1 表衝突＝需在 Batch 3 決定「預設繼承」或「寫死」。
4. **Anti-Bloat**：`PROJECT_RULES.md` §13.4（不另建治理 SSOT、同一內容不重複）——三個 agent 檔的 Forbidden 欄應**引用**本表出處而非複製全文。
5. **Claude Code agent 檔格式的官方規格（frontmatter 欄位、工具名稱、`.claude/agents/` 載入規則）：NOT VERIFIED**——本批未查；Issue Batch 3 第 1 項已要求「先查當時格式、工具權限與獨立性」，本節不寫任何欄位名。
6. **獨立性的實作難點**：同一 session 內 spawn 的 subagent 是否算「真正獨立」（共享總管脈絡、同模型）＝治理上的解讀問題，`PROJECT_RULES.md` §8 要求「真正獨立」，現行實務由總管另派不同脈絡的組；agent 檔無法單獨保證，**NOT VERIFIED**。

**(e) 路由表草案**（標記：**草案，Batch 3 前不落成 agent 檔**；級別由 `PROJECT_RULES.md` §8 判，這裡只給預設）

| 任務類型 | 主責角色 | 是否需獨立 QA | 是否可能觸發客戶 Gate |
|---|---|---|---|
| NAV／FX／幣別／as-of 唯讀盤點、lineage 對照 | `fund-nav-data` | 是（data semantics／freshness／provenance 至少 1 組） | 發現 identity／來源／FX 需改動時**停手**，轉 Gate |
| DEC／BL／HANDOFF 一致性、Gate 判定、登記同步 | `fund-governance-auditor` | 治理規則變更：是；純交接同步：可自驗 | 是（新裁示落盤、supersede） |
| 重跑測試、重現指令、驗證他人宣稱 | `fund-independent-qa` | **本身即獨立 QA**；不得驗自己 | 否（只回報；不裁決） |
| 測試守衛／版本守衛等**不改語意**的測試層調整 | 執行組（非三 agent 之一）→ `fund-independent-qa` 驗 | 是 | 否（總管讀法）；若改變黃金檔語意＝停手 |
| 公式／門檻／Schema／provider／UI layout | **不派 agent 施工** | — | **是**（Stop Gate／UI 草稿先行） |
| BL-0545 真實覆蓋率 | **不派**（需使用者自願合法輸入） | — | 是（BLOCKED） |

### §1.5 盲點與 NOT VERIFIED

1. **範圍**：Issue 稱「六項」只列五項；第六項未枚舉，**待客戶指明**。本節對第六項**不做任何猜測**。
2. **直譯器版本**：本批所有測試在 3.13.18 執行，只在 ALO 矩陣與 HLD 摘要上用 3.11.18／3.12.3 做了對照；**沒有**在 3.11 + 完整依賴下跑整套。CI 逐條日誌未取得，「兩個 Golden 檔在 CI Fast lane 被執行並通過」為靜態推導＋job conclusion。
3. **production Python 版本**：repo 內查無 pin；Streamlit Cloud 實際版本 NOT VERIFIED。
4. **`sum()` 根因的射程**：已證明解釋了 alo golden＋mutations（3）、hld 兩檔（4）、rulings（1）共 8 條；**未**對 `tests/ui_v2` 其餘檔、整套 suite 跑 shim，故不宣稱「3.13 上所有失敗皆此因」。BL-0453 的「本機紅、main 紅、CI 綠」是否另有成因，本批只驗證了該測試在 shim 下轉綠。
5. **全稱句**：「New UI 範圍對 ISIN 0 命中」「`_latest_nav_ccy_ok` 無直接測試」「無測試鎖定 ×1.4／`or 365`」「跨詞彙對映無單一斷言」皆單組 `git grep`，**未經第二組驗證**，不含別名／動態組字。
6. **未重驗**：1Y 驗證所述「盤中索引才可達」的 NAV 來源粒度；#1225 的 14 項抽驗；各 adapter live 可達性；Sheet 真實內容；Streamlit Cloud 入口與 Secrets；`ui/` 直讀 `ret_1y_total` 三處是否繞閘門（列 10 僅確認存在）。
7. **未跑**：`slow` lane、Playwright、pre-commit、整套 pytest、`tests/ui_v2` 其餘檔、`ui_v3` 非 AppTest 的瀏覽器測試。
8. **New UI nav 鏈是否需要寫入端換源守衛**：A 鏈（`auto_fetch_moneydj`）能否回非原生報價＝NOT VERIFIED；屬 identity／data semantics，只標 Gate。
9. **本批新增結論的 provenance**：全部由本作者單組產出並實跑；`sum()` 因果實驗與 7 案 1Y 重現的腳本與實驗輸出為一次性、**未入庫**（重現指令見 §1.2-3／§1.2-6 與本檔附錄 A）；非作者 QA 可依該處獨立重現。
10. **未動**：repo 任何檔、Golden 黃金檔、Schema、provider、公式、Sheet、憑證、live 來源；本節自身未新增 DEC／BL 編號（授權與發現登記由同 PR 另以 `DEC-2026-11-13-02`、BL-0548 處理，登記不構成動工授權）。

## 2. New UI2 五頁需求：驗收契約補缺（Batch 1 第 2 項）

> 性質聲明見本檔頭統一聲明（研究證據；非客戶裁示、非授權施工；單組作者，尚待非作者 QA）；整理日 2026-11-13（Asia/Taipei）。
> 範圍：沿用 `docs/evidence/ui_data_contract_audit_2026_11_12.md`（下稱 **#1225**）§2 五頁對照，**只補缺**——為每頁逐項標示五種**不同**狀態。不重做 #1225、#1227（`exp_wireframe_decision_pack_2026_11_13.md`、`d2_min_approval_pack_…`）；不新建第二份正式 data dictionary；不提議新 Schema／provider／公式／UI layout；不重錄任何 Golden。未核准的欄位、FX、identity、投資語意、UI layout、來源、formula 一律只標 Gate。
> 正確五頁：🌍 市場與趨勢（mkt）／💼 我的資產（ast，含持倉體檢與資產配置）／🔍 找基金（exp）／🤖 AI 投資總結（ai）／⚙️ 設定（set）。權威：`DEC-2026-10-29-06`、`ui_v3/shell/registry.py::IA_PAGES`。
> 「推薦」「讀法」一律是**總管讀法，可被客戶推翻**。缺值／無法判定寫 ⬜／◇，**不得讀成 0 或正常**。路徑一律「檔案::符號」，不寫行號。未寫 secret、NAS 位址、Sheet ID。

### 2.0 五種狀態的判準（互相不得冒充）

| 狀態 | 判準（成立才可標 ✓） | 常見冒充（**不成立**） |
|---|---|---|
| **S1 規格已核准** | 有正式 DEC／frozen 44／已核准線框條文可指，標【逐】（`docs/evidence/decisions/` 有逐字檔，本稿未逐句核對）或【轉】（要點轉述、非逐字，客戶可推翻）。**部分核准（只核准方向／UI 設計）標 △**。 | `docs/v2/79`、`80` 是正式 input contract 但**不等於 frozen**；`82` 是部分核准**草案**；`81` 只核准🌍線框；決策包／證據檔的「推薦」不是核准 |
| **S2 技術已實作** | 程式存在**且被該頁／該層實際呼叫**。必標程式樹：`v3`＝`ui_v3`（New UI2）；`v2`＝`ui_v2`（maintenance-only，**完成率不得算 v3**）；`adp`＝只有 adapter／view model、**0 頁消費**；`poc`＝隔離 PoC；`∅`＝無 | ui_v2 live 頁、Old UI `[新]` 並行預覽分頁、adapter 有測試、fixture 畫面，都不是 `ui_v3` 該頁 |
| **S3 同 head 測試已通過** | 分兩欄記：**(a) 本機實跑**（本稿在 `git archive` 副本實跑，見下方 R1～R6，含環境差異）；**(b) CI 同 head**（#1227 head `66889189`，其樹與 main `2f13fade` 的 diff 為空；`b991df70..HEAD` 非 `docs/` 檔 0 個——本稿 `git diff` 實測）。**該列必須有可執行斷言才可標 ✓**；無斷言＝✗（無有效斷言）。 | 「CI 全綠」不等於該列有斷言；Slow／Visual 兩條 lane 是 `continue-on-error` 的 informational；Visual lane 截的是 `ui_v2` fixtures，**不是 `ui_v3`** |
| **S4 正式資料已驗證** | 有可追溯的**真實來源／真實 Sheet／Streamlit Cloud** 驗證證據，且驗的是**該列本身** | fixture／合成資料（`tests/ui_v3/market_stubs.py`）、一次性探針（Yahoo 4 次 HTTP）、離線快取檢查、客戶口述「Secrets 已更新」皆**不算** |
| **S5 使用者已驗收** | 客戶明示「驗收通過」的紀錄（DEC／PR／逐字檔），驗的是**已建成的畫面** | 客戶核准**線框／字樣／方向**屬 S1；客戶審查後要求修改（如 `DEC-2026-11-03-11`）不是驗收通過；G7（Cloud／WebView／真機）至今待客戶 go |

**列內符號**：✓＝是　△＝部分　✗＝否　?＝NOT VERIFIED　—＝不適用（該列不消費外部資料，S4 無從談起；**不得讀成已驗證**）。

**S3(a) 本機實跑結果**（指令均加 `-p no:cacheprovider`；Python **3.13.18**，pandas 2.3.3／numpy 2.5.4／streamlit 1.59.2／pytest 9.2.0；**CI 為 Python 3.11**，requirements 版本未必相同）：

| 編號 | 範圍 | 結果 | 備註 |
|---|---|---|---|
| R1 | `tests/ui_v3`（全部） | **878 passed、84 skipped**（66.9s） | 84 skipped＝`test_ui_v3_market_page_browser.py` 74＋`test_ui_v3_top_nav_browser.py` 10，**全因本機未裝 playwright**。故 ui_v3 的瀏覽器級斷言本機 **NOT RUN** |
| R2 | `tests/test_v2_tables_*.py`、`tests/test_v2_domain_*.py`、`tests/visual_fidelity`，`-m "not slow"` | **1628 passed、17 skipped、7 deselected**（11.7s） | 17 skipped：1 筆「fixture digest 釘在 python 3.11.18（3.13 的 float `sum()` 不同）」；16 筆「淺層 clone 拿不到舊 commit」（副本為單一 commit） |
| R3 | `tests/ui_v2`，`-m "not slow"` | **4661 passed、5 failed、2 skipped、1116 deselected**（229s） | 5 failed 全是 digest／golden 類，見 R4 |
| R4 | 重跑 R3 的 5 個失敗 | 加 `builtins.sum` 還原成 3.11 逐項加總語意的診斷墊片後 **5 passed** | **成因＝Python 3.12 起 float `sum()` 改為補償加總**（`sum([0.1]*10)` 本機回 `1.0`），非程式 bug；墊片為一次性診斷腳本、**未入庫**（做法見 §1.2-6 的 shim 示意與附錄 A）、**僅診斷用**。5 筆：`test_hld_logic.py::test_第2件反向控制_十二情境乘九塊一百零八格逐格未變`、`::test_第2件_三個新情境的整頁模型逐格釘住`；`test_hld_read_failure_logic.py::test_T2c正_十七個情境_示範與正式模式共389個模型_與改動前相同`、`::test_空白套用d反_設定讀得到_清空再套用照舊說未設定_本條修正不改這些頁面`；`test_rulings_2026_10_18b_logic.py::test_示範模式_持倉體檢與標的探索全情境模型_md5與動手前相同` |
| R5 | `ui_v2` slow 標記子集：`test_ast_page`、`test_asset_layout_a_page`、`test_exp_page`、`test_exp_live_page`、`test_set_page`、`test_set_live_page`、`test_mkt_live_page` | **176 passed、5 skipped**（122s；**加上述墊片**） | 5 skipped＝playwright 缺。`ui_v2` slow 全集 1116 筆**只跑了這 7 檔**，其餘 **NOT RUN** |
| R6 | `test_readonly_live_pages_page`、`tests/poc_dual_theme/{guard,contrast}`、`test_preview_page`（加墊片） | **115 passed、20 skipped** | skipped 皆 playwright 缺 |

**S3(b) CI 同 head**：PR #1227 head `668891893c9f95c99a4b1884520e7327bae23007`，GitHub check-run 讀取（本稿實查）：Fast／Schema／Slow／Visual **四條 `conclusion=success`**（run 43333708724）。PR 描述自陳 Slow 末行「1283 passed, 16 skipped, 19844 deselected」、Visual「7 passed」、Fast 的 pytest hook 不印數量——**此三項是 PR 作者自陳，本稿未重讀 step log**。⚠️ Slow／Visual 的 workflow 為 job 級 `continue-on-error: true`，故 check-run 綠不證明內容全綠。`pre-commit` 本機未安裝，僅 CI 驗。

### 2.1 五頁 × 五狀態總表

每格＝結論＋依據編號（列號見 §2.2）。**這是頁級彙總；任何一格的 ✓ 都不得外推到該頁其他列。**

| 頁 | S1 規格已核准 | S2 技術已實作 | S3 同 head 測試 | S4 正式資料已驗證 | S5 使用者已驗收 | production 入口接線 | 主要 Gate（#1225 §5） |
|---|---|---|---|---|---|---|---|
| 🌍 市場與趨勢 | **部分**：81 線框＋字樣＋歸一化 Q/A 皆有逐字檔（M1～M12）；**市場綜合判定、新鮮度門檻、VIX 門檻、深色模式、cutover 未核准**（M2、M4） | **是（v3，Preview-only）**：`ui_v3/pages/mkt.py`＋`app_preview.py`；`ui_v2` 並存但不計 | **是**（R1＋CI 四 lane success）；瀏覽器級斷言（M1 手機頁首、M12）本機 **NOT RUN** | **NOT VERIFIED**：ui_v3 測試全用合成 stub；Yahoo 探針與 `data_cache` A1 檢查是研究證據、**不是** Preview 頁驗證；Cloud Secrets 不明（M3、M5、M9、M10） | **否**：無「驗收通過」紀錄；`DEC-2026-11-03-11` 是審查後裁示修正；G7 待客戶 go | **否**：`app.py` 對 `ui_v3`／`ui_v2` 0 命中（本稿 `git grep`）；Preview 獨立入口；Cloud 入口 repo 內查不到＝NV | G4、G5、G11、G3 |
| 💼 我的資產 | **部分**：版面順序、U1～U5 UI 設計、缺 FX 方案 A、Stage 1 線框採 A 已核准（多為【轉】）；**摘要四格算法、配息推估、市值基準、D2 欄位（核准數＝0）、NAV 10 日規則重定義未核准**（A2～A12） | **ui_v3＝否**（0 頁；僅 `ui_v3/adapters/assets_source.py` 內部 adapter、**0 production caller**）；**ui_v2＝是**（`ui_v2/asset\|alo\|hld`，maintenance-only），且其版面順序與 `DEC-2026-11-04-01` **相反**（A2） | **部分**：adapter 契約／變異／隔離測試通過（R1）；**無任何 v3 頁級斷言**；ui_v2 在本機 3.13 有 5 筆 digest 失敗（成因見 R4，CI 3.11 同樹 success） | **NOT VERIFIED**：BL-0545 真實 Active Sheet 覆蓋率 NV、使用者暫不提供輸入；無一列有真實 Sheet 證據 | **否**（v3 無頁）；ui_v2 僅有 2026-10-20 BL-0250 3-B 實機驗收（範圍＝四頁件數 Q1，舊版，**不可冒充 v3**） | **否** | G1、G6、G7、G11、#1225-D1～D5 |
| 🔍 找基金 | **部分**：IA P（同頁上下）、Batch E G-E1～G-E7、第一階段唯讀、禁排名等已核准（【逐】多）；**New UI2 🔍 線框未核准**（#1227 決策包待客戶）、ISIN／「查無」／身份未啟用、N 序列歸一化公式未核准 | **ui_v3＝否**；**ui_v2＝是**（EXP-0～7 篩選器 live）；**「找一檔基金」lookup＝否**（`ui_v2/exp` 對 `lookup\|ISIN\|查一檔\|找一檔` 0 命中） | **部分**：ui_v2 篩選器邏輯／AppTest 通過（R3、R5）；lookup、ISIN、身份字樣**無任何斷言** | **NOT VERIFIED**：選股池 Sheet、MoneyDJ 取數、`fund_profile` 皆無真實驗證證據 | **否** | **否** | G8、G11、BL-0530、D2 R-ID／R-NAV |
| 🤖 AI 投資總結 | **部分**：導覽佔位＋Phase 7 前不可進（`DEC-2026-10-29-07`）、六詞語意（`DEC-2026-10-27-22`）、UI-14 四區**方向**（`DEC-2026-11-02-07`）；**頁內容、Digest schema、Risk Cap、減碼 trigger、System Action State 皆未核准** | **ui_v3＝佔位而已**：registry 槽位＋`ActionSlot` view model（**0 頁消費**，`git grep` 僅 `viewmodels/__init__.py` 匯出）；無 renderer、無 Digest 生產者；Old UI AI 摘要殼（`services/ai_service.py`）不算 | **部分**：佔位／詞彙守衛通過（R1）；**無功能可測** | **—／NOT VERIFIED**：無資料流可驗 | **否** | **否**（建構時即拒絕 `registered=True`） | G9、BL-0527／0495／0496／0528、BL-0540 G-5 |
| ⚙️ 設定 | **部分**：44 §3.5 SET-0～8、UI-10 A（Rule Registry 唯讀殼）、UI-15 A（通知所有權）、登入入口位置為方向／設計；**New UI2 ⚙️ 線框未核准**、Rule ID 格式、通知偏好版面未核准 | **ui_v3＝否**；**ui_v2＝是**（SET-0～8 live、登入／Active Sheet picker）；Rule Registry、Digest viewer、通知偏好 **無程式**（`git grep`） | **部分**：ui_v2 SET 邏輯／AppTest 通過（R3、R5、R6）；無 v3 頁級斷言 | **NOT VERIFIED**：設定試算表標頭／列數／值域、FRED 金鑰在 Cloud 皆無真實證據 | **否** | **否** | G10、G5、BL-0534、BL-0540 G-3 |

### 2.2 每頁逐列驗收契約

**縮寫**：`T3/`＝`tests/ui_v3/`；`T2/`＝`tests/ui_v2/`；`T0/`＝`tests/`。「P→C」＝producer→consumer（檔::符號）。DEC 後【逐】／【轉】見 §2.0 S1。狀態欄格式：`S1 S2 S3 S4 S5`（符號定義見 §2.0）。**斷言欄只列「該列需求本身」的既有測試；寫「無有效斷言」＝找不到會因該列行為錯誤而轉紅的測試（單組判讀）。** 所列 `T3/` 測試除瀏覽器兩檔外，R1 皆 passed；`T2/`、`T0/` 測試除明列者外，R2／R3／R5／R6 範圍內皆 passed。

#### 2.2.1 🌍 市場與趨勢（`ui_v3` Preview；12 列）

| # | 需求項 | spec／DEC | P→C | 可執行斷言 | 狀態 | 證據／NV | 缺口（Gate／文件／測試層級） |
|---|---|---|---|---|---|---|---|
| M1 | 五頁導覽與 IA：頁序固定、僅 🌍 可進、未掛載頁可見不可進、不建空殼 | `DEC-2026-10-29-06`【逐】、`-11-03-10`、`-11-03-11`【逐】；80 §17 | `ui_v3/shell/registry.py::IA_PAGES` → `ui_v3/shell/nav.py::nav_items` → `ui_v3/pages/chrome.py::render_navigation` | `T3/test_ui_v3_page_registry_guard.py::test_five_pages_in_ia_order`、`::test_only_market_page_is_registered_so_no_empty_shell`；`T3/test_ui_v3_navigation_shell.py::test_unregistered_pages_are_visible_but_never_available_and_ai_never_available` | ✓ ✓v3 ✓ — ✗ | R1 passed；CI success | 手機頁首 S1 五格的瀏覽器斷言（`test_ui_v3_top_nav_browser.py`）本機 NOT RUN；G7 Cloud／WebView／真機待客戶 go |
| M2 | 首屏「市場狀態」「是否需注意」兩枚獨立 chip，**恆 `⬜ 無法判定`**（無正式規則），不得省略或寫成「無須注意」 | `DEC-2026-11-03-01` Q1 A【逐】、`-11-03-09` 採 C【逐】；81 §10.2 | `ui_v3/viewmodels/market_page.py::MarketPageModel` → `ui_v3/pages/mkt.py::summary_html` | `T3/test_ui_v3_first_screen_c_and_wording_unify.py::test_first_screen_has_two_separate_labelled_rows_each_with_its_own_chip`、`::test_first_screen_chips_plus_core_numbers_stay_within_five`；`T3/test_ui_v3_market_page_apptest.py::test_normal_page_renders_four_first_screen_answers_and_no_exception` | ✓ ✓v3 ✓ — ✗ | 兩枚 chip 是常數 ⬜，**測試通過只證明「呈現規則」，不證明市場被判定** | #1225-G4／D7：市場綜合判定規則未核准，**不得出現 `⬜` 以外的值** |
| M3 | 「重要依據」＝兩序列期間漲跌（與圖同基準、隨期間切換），缺／失敗時該格改一枚狀態 chip | `DEC-2026-11-03-01` Q4 A【逐】 | `ui_v3/adapters/market_page.py::_evidence_changes` → `mkt.py::summary_html` | `T3/test_ui_v3_market_page_adapter.py::test_evidence_changes_equal_chart_end_values_minus_base`；`T3/test_ui_v3_first_screen_c_and_wording_unify.py::test_ok_fixture_has_two_ok_evidence_numbers` | ✓ ✓v3 ✓ ? ✗ | 斷言用 `tests/ui_v3/market_stubs.py` **合成資料**；Yahoo 探針（`DEC-2026-11-09-08`，4 次 HTTP）**不是**本頁驗證 | 真實 TAIEX／S&P 500 經 Preview 頁的端到端驗證 NV；Yahoo 收盤判準＝**暫行**（`DEC-2026-11-09-10` Q3【轉】） |
| M4 | 「資料新鮮度」首屏僅一枚 `⬜ 門檻待裁示`，無延遲天數、無日期、無新舊判定 | `DEC-2026-11-03-01` Q5 B【逐】、`DEC-2026-11-03-09`【逐】 | `shared/ui_semantics/rules.py::entry_for_freshness` → `mkt.py::summary_html` | `T3/test_ui_v3_semantics_rules.py::test_status_and_freshness_keys_match_view_model_contract`；`T3/test_ui_v3_market_page_apptest.py::test_stale_series_is_shown_as_a_fact_only_and_never_judged` | ✓ ✓v3 ✓ — ✗ | 同 M2 | #1225-G4／BL-0369：新鮮度門檻未核准；`◷` 不是最新徽章尚未落地 |
| M5 | Primary 比較圖：TAIEX vs S&P 500，**共同基準日＝100**、視窗起點取兩條可比較範圍較晚者、各畫到自己最後觀測日、斷線不補 | `DEC-2026-11-02-07` UI-12(1)／UI-13【逐】、`DEC-2026-11-03-01` Q2-a/b/c A【逐】、`DEC-2026-11-03-04` A2/B2/C2【逐】；81 §7 | `services/v2_domain/normalization.py::normalize_pair` → `ui_v3/adapters/market_chart.py::build_comparison_card` → `ui_v3/pages/mkt.py::primary_chart_html` | `T0/test_v2_domain_normalization.py::test_golden_pair_基準日晚於視窗起點_各自終點不同`、`::test_先例對照_終點_先例截到最後共同日_H1各畫到自己最後一天`、`::test_無共同日_no_common_base_不出線`；`T3/test_ui_v3_market_page_apptest.py::test_primary_chart_has_two_lines_base_chip_frequency_and_per_series_data_dates`；`T3/test_ui_v3_market_page_adapter.py::test_each_series_is_drawn_to_its_own_last_observation_date` | ✓ ✓v3 ✓ ? ✗ | 公式有 golden（R2、R1 passed）；`DEC-2026-11-03-04` 要求的**公式等級獨立稽核紀錄，本稿未見＝NV** | 真實序列驗證 NV；Yahoo 週末排除僅限縮維持，台股補班日待證據（`DEC-2026-11-09-10` Q2） |
| M6 | 缺值呈現：缺一條仍畫另一條並指明缺哪條；兩條皆缺不畫空座標軸；歷史不足標示不足、不縮短冒充 | `DEC-2026-11-03-01` Q2-c A【逐】、`-11-03-07`【逐】；81 §4.1 S2～S7 | `ui_v3/adapters/market_page.py::build_market_page` → `mkt.py::primary_notes_html` | `T3/test_ui_v3_market_page_apptest.py::test_missing_taiex_shows_data_not_ready_and_still_draws_the_other_series`、`::test_both_missing_shows_empty_state_without_drawing_an_empty_chart`、`::test_partial_history_falls_back_to_single_chart_with_insufficient_marked` | ✓ ✓v3 ✓ ? ✗ | 情境為合成 stub | 真實缺值情境 NV |
| M7 | 狀態分流：**取數失敗 ≠ 資料未備 ≠ 尚未設定**，原文不上一般畫面 | 81 §4.1 S6；`DEC-2026-11-03-07`／`-09`【逐】；79 §11 | `ui_v3/adapters/market_page.py::domain_state` → `mkt.py::status_html` | `T3/test_ui_v3_market_page_apptest.py::test_failed_sp500_shows_fetch_failed_not_data_not_ready_and_no_raw_error`、`::test_missing_fred_key_renders_not_configured_not_fetch_failed`；`T3/test_ui_v3_market_page_adapter.py::test_failure_original_text_never_enters_the_view_model`；`T3/test_ui_v3_no_engineering_leak_guard.py::test_rendered_page_never_shows_engineering_information` | ✓ ✓v3 ✓ ? ✗ | 同上 | 真實失敗路徑（429／Key 缺）NV |
| M8 | Secondary VIX 卡；Primary 檢視為 VIX 時該卡讓位 | `DEC-2026-11-03-06`【逐】 | `ui_v3/adapters/market_page.py::build_market_page` → `mkt.py::secondary_html` | `T3/test_ui_v3_market_page_apptest.py::test_switching_view_to_vix_drops_the_secondary_vix_card_and_keeps_first_screen`；`T3/test_ui_v3_market_page_adapter.py::test_vix_yield_ruling_secondary_count_follows_primary_view_and_never_backfills` | ✓ ✓v3 ✓ ? ✗ | 同上 | VIX 門檻未核准（#1225-G4）；`ui_v3` 不得沿用舊樹 22／30 |
| M9 | Secondary 利率與信用（三子序列；FRED **觀測日≠公布日**；金鑰缺→「尚未設定」） | `DEC-2026-10-30-01` D2＝P2；81 §4；`CLAUDE.md` §2.3（FRED 發布延遲與 PIT） | `repositories/macro/fred.py::fetch_fred` → `services/v2_tables/market_indicator.py` → `ui_v3/adapters/market_page.py::_rates_card` → `mkt.py::secondary_html` | `T3/test_ui_v3_market_page_apptest.py::test_rates_radio_switches_sub_series_without_dropping_the_card`、`::test_missing_fred_key_renders_not_configured_not_fetch_failed`；`T0/test_v2_tables_market_indicator_fred.py`（檔級，R2 passed） | ✓ ✓v3 ✓ ? ✗ | **FRED Secrets 在 Cloud 是否生效 NV**（客戶口述更新，`secrets_recovery_verification_2026_11_10.md` §0） | #1225-G11：Actions→Cache 接線不在本列範圍 |
| M10 | 依據卡 MKT-1～MKT-3：鍵、順序、位數、單位；MKT-2 兩鍵 Missing；MKT-3 匯率閘門關不可達 | 44 §3.1【frozen】；72 §3；81 §10.3；`DEC-2026-11-02-07` UI-12(3) | `ui_v3/adapters/market_page.py::_evidence_cards` → `mkt.py::fact_html` | `T3/test_ui_v3_mkt_evidence_alignment.py::test_each_card_has_the_formal_keys_in_the_formal_order_with_the_formal_names`、`::test_keys_without_formal_data_are_missing_not_filled`、`::test_fx_formal_decimals_are_three_but_the_key_is_not_reachable_today` | △ ✓v3 ✓ ? ✗ | `FX_OBS_DATE_RULE_VERIFIED=False`（`services/v2_tables/market_indicator.py`，`DEC-2026-11-08-02`） | #1225-G11：FX 閘門；NDC 景氣燈號無公布日；TW PMI／出口 YoY 無 production 消費端（#1225 §1.1） |
| M11 | 降級首屏名額 ≤5、頁級失敗警示保留、**全取得時不寫「正常／資料齊」**；Status Bar／側欄純文字、零 chip | `DEC-2026-11-03-11`【逐】；81 §10.2 | `ui_v3/adapters/shell_status.py::from_market_model` → `ui_v3/pages/chrome.py::status_bar_html` | `T3/test_ui_v3_degraded_first_screen_budget.py::test_first_screen_slots_stay_within_five_in_every_scenario_and_view`、`::test_degraded_first_screen_keeps_a_visible_warning_and_never_says_normal`；`T3/test_ui_v3_navigation_shell.py::test_status_bar_when_all_primary_data_present_never_says_normal_or_complete` | ✓ ✓v3 ✓ — ✗ | 該 DEC 自陳「若以 `data-status-key` 計，降級 390px 仍為 7」待客戶確認（81 §10.2 揭露） | 計數讀法客戶尚未明確接受＝文件層待確認 |
| M12 | 視覺：B 色票＋A 尺寸 token、卡片容器化、Secondary 頂對齊、390px 首屏主圖可見量不明顯變差；手機頁首五格無橫滑 | `DEC-2026-11-11-01`【轉】、`-11-07-02`【逐】、`-11-06-01`【逐】 | `ui_v3/design/tokens.py` → `ui_v3/pages/mkt.py::_css` | token 層：`T3/test_ui_v3_design_tokens.py::test_only_approved_tokens_have_values_and_the_values_are_the_approved_ones`、`T3/test_ui_v3_token_contrast.py`（檔級）；**瀏覽器層**：`T3/test_ui_v3_market_page_browser.py::test_no_horizontal_overflow`、`::test_primary_chart_present_visible_nonzero_and_in_place`（**本機 NOT RUN**） | ✓ ✓v3 △ — ✗ | token 層本機 passed；瀏覽器層僅 CI Slow（informational）曾 success，PR 自陳計數；`#1207` 作者自驗＋非作者 QA 紀錄見 `fund_newui2_market_g3_g6_build_evidence_2026_11_11.md` §10 | G7 Cloud／WebView／真機；12px→13px、`grey`／`neutral` 區分、`config.toml` 統一皆待客戶；**深色模式不授權施工**（`DEC-2026-11-11-03`【轉】） |

**🌍 Gate-only（不列為需求列、不得施工）**：市場綜合判定規則、新鮮度門檻、VIX 門檻、深色模式正式施工、Preview→正式 cutover（BL-0535）、FX 開閘（D8）、NDC 公布日、國際市場監控（83）、真實覆蓋驗證（G7）。

#### 2.2.2 💼 我的資產（`ui_v3` **無頁**；`ui_v2/asset|alo|hld` 為 maintenance-only；12 列）

| # | 需求項 | spec／DEC | P→C | 可執行斷言 | 狀態 | 證據／NV | 缺口 |
|---|---|---|---|---|---|---|---|
| A1 | New UI2 💼 頁本身：登錄為 `wireframe_not_approved`，不建空殼、不接 adapter | `DEC-2026-10-29-06`【逐】；80 §7.2；`ui_v3/shell/registry.py` 檔頭 | `ui_v3/shell/registry.py::IA_PAGES`（`ast`，`registered=False`） | `T3/test_ui_v3_page_registry_guard.py::test_only_market_page_is_registered_so_no_empty_shell`；`T3/test_ui_v3_assets_source_import_isolation.py::test_nothing_in_ui_v3_references_the_adapter_so_no_page_is_wired`、`::test_registry_has_no_new_page_and_preview_renderers_are_unchanged` | △ ✗v3 ✓ — ✗ | 守衛通過＝**「尚未接線」被鎖住**，不是頁完成 | Stage 1 線框停在客戶 UI Review（#1225-G7）；`DEC-2026-11-09-04` 採方案 A |
| A2 | 版面順序：**主圖在前、四項摘要在後**、資料不足明確顯示 Missing | `DEC-2026-11-04-01`【逐】；82 §0.1 | v3：無。v2：`ui_v2/asset/page.py::_render_primary`／`_render_summary` | **無有效斷言（New UI2 順序）**。⚠️ 反向事實：`T2/test_ast_page.py::test_第一屏順序_selector在summary之前_summary在主判讀之前_主判讀在Primary之前` 釘的是 **summary 在 Primary 之前**（本稿讀測試原碼） | ✓ ✗v3 ✗ — ✗ | **ui_v2 的 💼 順序與已核准的 New UI2 順序相反**；ui_v2 完成率不得冒充 | 需 New UI2 💼 線框審批後的實作批，並新增順序斷言 |
| A3 | 摘要四格（總資產／總損益／報酬／配息）**一律 `◇ 資料未備`**，不造 0、不新增彙總公式 | `DEC-2026-11-04-02`【轉】、`DEC-2026-10-30-02`【逐】；82 §9.8；#1225-G6（G-4 暫不開） | `ui_v2/asset/overview.py::summary_strip` → `ui_v2/asset/page.py::_render_summary` | `T2/test_ast_overview_logic.py::test_summary四格_總資產總損益報酬配息_全是Missing_字樣沿正式contract`、`::test_summary沒有任何彙總計算_模組不含加總平均的實作`；`T2/test_ast_page.py::test_summary四格_一個容器_全是Missing` | △ ✓v2 ✓(v2) ? ✗ | v3 無；4 格算法無核准（G-4） | BL-0542 G-4；`ui_v3` 沒有對應 view model |
| A4 | 配置主圖「現況 vs 目標」；**缺 FX＝方案 A**（不退回成本、不把不完整分母畫成完整 100%） | `DEC-2026-11-04-02`【轉】、`-11-04-03`（方案 C 保守 PORT）；BL-0542 G-1 | `ui_v2/alo/logic.py::_build_alo2` → `ui_v2/asset/page.py::_render_primary`；domain 層 `services/v2_domain/allocation_evidence.py` | `T3/test_ui_v3_assets_source_contract.py::test_basis_words_match_l2_and_ui_v2`（僅字詞對齊）；`T2/test_alo_live_logic.py`（檔級）。**方案 A 本身無專屬斷言** | △ △v2 △ ? ✗ | 沿用 #1225 §2.4：`_build_alo2` 缺 FX 時分母只加總有值類別＝**尚未對齊方案 A 的已登記落差**（本稿未重驗） | BL-0542 G-1 公式承接須獨立稽核；不得改 `_build_alo2` |
| A5 | 頁級狀態（β 階梯）：取數失敗＞無持倉＞需要注意＞資料未備＞未設定／不適用＞只評估一部分＞無偏離；頭條非 rule result | `DEC-2026-10-30-04`【逐】、`-10-31-01`【逐】 | `ui_v2/status_class.py` → `ui_v2/asset/page_status.py::classify_side`／`_merge` → `ui_v2/asset/page.py::_render_page_status` | `T2/test_p3_page_status_logic.py::test_嚴重度階梯照客戶原話_取數失敗_無持倉_注意_資料未備_未設定_只評估一部分_無偏離`、`::test_全排列_任一方非正常時頭條一定非正常_正常絕不當頭條` | ✓ ✓v2 ✓(v2) — ✗ | β 組合邏輯仍在 `ui_v2`，**未 PORT 至 `ui_v3`**（82 頂部「現有資料接線的現實限制」表：「β 組合邏輯仍在 `ui_v2`、BL-0411 仍有 Gate」） | BL-0411 Gate；`ui_v3` 需另有 view model |
| A6 | 持倉資料來源：只讀使用者 Active Sheet、**無 fallback**、一次一個 Active、「持倉資料來源 ▼」為 💼 頁唯一 Sheet 入口 | 44 之二十其三（`DEC-2026-10-29-06`）；`DEC-2026-10-25-01` | `ui_v3/adapters/assets_source.py::load` → `services/v2_tables/alo_holdings.py::load_alo_tables_active`；v2：`ui_v2/asset/page.py::_render_source_row` | `T3/test_ui_v3_assets_source_contract.py::test_no_active_judgement_matches_ui_v2_active_gate_exactly`、`::test_real_l2_without_credentials_ends_in_no_active_and_blocks_all_network`；`T2/test_ast_page.py::test_沒有Active_整頁明確第三種狀態_沿既有字樣與連結` | ✓ △adp+v2 ✓ ? ✗ | **真實 Active Sheet 覆蓋率 NOT VERIFIED**（BL-0545；探針固定輸出 `NOT VERIFIED`） | #1225-G1：使用者合法輸入；專案 AI 不得請求憑證 |
| A7 | Complete Evidence 載入端：成本基準／基準未設可組證據，**證據物件原樣通過、不補值** | `DEC-2026-11-05-02`【轉補登】、`-11-05-04`【轉】；BL-0542 G-2 | `ui_v3/adapters/assets_source.py::evaluate` → `services/v2_domain/allocation_evidence.py::build_allocation_evidence`；**consumer：無頁** | `T3/test_ui_v3_assets_source_contract.py`（11 筆）、`T3/test_ui_v3_assets_source_mutations.py`（6 筆）、`T3/test_ui_v3_assets_source_import_isolation.py`（12 筆）；`T0/test_v2_domain_allocation_evidence.py`（R2 passed，其中 1 筆 digest 因 3.13 skipped） | △ △adp ✓ ? ✗ | 證據 schema＝**內部候選、非核准契約**（模組檔頭自述）；`chart_claim` 恆 `withheld_pending_approval` | 接頁需線框＋客戶核准；證據根層缺 `as_of`（#1225 §1.5） |
| A8 | 市值基準／匯率：FX 閘門關⇒**市值基準一律 `blocked`**；使用者面一律稱「淨投資金額」不稱成本 | `DEC-2026-11-08-02`【轉】、`DEC-2026-11-09-01`【轉】 | `services/v2_tables/market_indicator.py::FX_OBS_DATE_RULE_VERIFIED`（False）→ `ui_v3/adapters/assets_source.py::BLOCKED_MARKET_BASIS` | `T3/test_ui_v3_assets_source_contract.py::test_fx_rule_reader_follows_the_live_l2_attribute`；**「淨投資金額」用語無斷言**（`git grep` 於 `ui_v2/` 0 命中；`ui_v2/{alo,hld}` 仍有「成本」字面，單組 grep） | △ ✗ ✓(blocked) ✗ ✗ | 開閘證據不足（`fx_obs_date_winter_probe_2026_11_08.md`） | #1225-G11 FX 閘門；用語落地待 `ui_v3` 💼 頁 |
| A9 | 持倉明細與逐檔 NAV／配息序列（HLD） | 44 HLD-0～8【frozen】；`DEC-2026-11-05-03`【轉】（NAV 10 日規則：保留既有、未授權重定義） | `services/v2_tables/nav_dividend.py::build_nav_dividend_tables` → `ui_v2/hld/logic.py` → `ui_v2/asset/page.py`；v3 無 | `T0/test_v2_tables_nav_dividend.py`、`T0/test_v2_tables_nav_chain_handover.py`（R2 passed）；`T2/test_hld_live_freshness.py`（R3 passed）。⚠️ R3 的 5 筆失敗皆為 HLD／示範模式 digest（R4：3.13 float `sum` 所致） | ✗ ✓v2 △ ? ✗ | `NAV_HISTORY_PROVENANCE_VERIFIED=False`、`NAV_NOT_READY_DAYS=10`（`ui_v2/thresholds.py`）；**D2 核准欄位數＝0**（`DEC-2026-11-11-04`【轉】） | D2 R-NAV 逐列核可（#1227 最小包）；`ui_v3` 資料接線在核准前不得動 |
| A10 | 基金身份：production 主鍵 `full_key`、`holding_id`、DIRECT 不產生 holding 列（總管暫定）；DG2 canonical identity 仍 shadow | `DEC-2026-10-28-05`【逐】、`-10-29-01`【逐】、`-11-09-01`（D2-A＝B，**未實作**）【轉】 | `services/v2_tables/fund_keys.py::resolve_full_keys` → `services/v2_tables/alo_holdings.py`；`shared/fund_identity.py::DG2_SHADOW_ENABLED`（False，無 consumer） | `T0/test_v2_tables_fund_keys.py`、`T0/test_fund_identity_dg2.py`（純函式層，非 UI 列） | △ △ ✓(底層) ? ✗ | 影子差異真實分布 NV；Sheet「基金代號」欄違反契約標示尚未實作 | BL-0530、D2 R-ID；identity 規則屬 Stop Gate |
| A11 | 配息／近期事件（Dividend Calendar）：正式日期優先、`pay_date` **不得標成入帳日** | `DEC-2026-11-02-07` UI-15 A【逐】；79 §17.12；BL-0534 | `services/v2_tables/nav_dividend.py`（`DIV_DATE_IS_EX_DATE_VERIFIED=False`）→ `ui_v2/hld/*`（HLD-3）；New UI2 行事曆＝無 | `T0/test_v2_tables_dividend_chain.py`（檔級，R2 passed）。**New UI2 配息日期語意無斷言** | △ △v2 △ ? ✗ | 44 `pay_date` amendment 文字未起草（BL-0534）；BL-0427(5) 取值順序真實資料未驗 | amendment 草稿可自理；日期語意屬 formula／data semantics Gate |
| A12 | Stage 1 線框審批結果與暫不顯示項：類別淨投資金額小計暫不顯示（T1＝B）、健診「涵蓋 N／M」暫不顯示（N＝C）、A10／A20 Missing 區分、A50 入口判定**維持待驗** | `DEC-2026-11-09-02`／`-03`／`-04`【均轉】；82 §11 | 無（線框／設計層） | 無有效斷言（尚無 `ui_v3` 💼 程式） | △ ✗ ✗ — ✗ | A50 暫行候選非正式契約，不得當 production 規則 | 停在客戶 UI Review，不跳 Stage 3；BL-0542 G-3／G-5 |

**💼 Gate-only**：摘要四格算法（G-4）、配息推估、市值基準與 FX、類別小計、涵蓋 N／M、容許帶端點歸屬、D2 逐列欄位、DIRECT／ISIN、PORT 後續（BL-0542 G-1）、`ui_v3` 資料接線、cutover。

#### 2.2.3 🔍 找基金（`ui_v3` **無頁**；`ui_v2/exp` EXP-0～7 為 maintenance-only；12 列）

| # | 需求項 | spec／DEC | P→C | 可執行斷言 | 狀態 | 證據／NV | 缺口 |
|---|---|---|---|---|---|---|---|
| E1 | New UI2 🔍 頁本身：登錄 `wireframe_not_approved` | `DEC-2026-10-29-06`【逐】；80 §7.3 | `ui_v3/shell/registry.py::IA_PAGES`（`exp`） | `T3/test_ui_v3_page_registry_guard.py::test_only_market_page_is_registered_so_no_empty_shell` | △ ✗v3 ✓ — ✗ | 守衛鎖住「未接線」 | `exp_wireframe_decision_pack_2026_11_13.md` Q1～Q9 待客戶（#1225-G8） |
| E2 | 「找一檔基金」lookup：**單一輸入框 X**、MoneyDJ 基金代碼為第一入口，格式分流在 resolver／取數**之前** | `DEC-2026-11-01-01`、`-11-01-02` G-E1／G-E7【逐】 | **無實作**（`git grep -n -i "lookup\|ISIN\|查一檔\|找一檔" -- 'ui_v2/exp/*.py'` 0 命中，單組） | 無有效斷言 | ✓ ∅ ✗ — ✗ | Batch E lookup 未實作（#1225 §2.4） | 需線框核准＋Source Gate（G-E3 取數鏈外露實際命中來源） |
| E3 | ISIN 入口保留但顯示「尚未啟用」，**不進 resolver／取數鏈**，不以名稱搜尋或 AI 猜補 | `DEC-2026-11-01-02` G-E1 A＋C【逐】；BL-0530（research-only） | 無實作 | 無有效斷言 | ✓ ∅ ✗ — ✗ | 無已核准 ISIN→MoneyDJ 對照來源 | BL-0530；不得啟用 mapping |
| E4 | 輸入類型「代碼型字串（原值未改寫）」＋基金身份 `◇ 尚未確認`；**不得 `split("-")[0]`**，本批不啟用 DG2 shadow | `DEC-2026-11-01-02` G-E4／S6【逐】 | 無 UI；底層 `shared/fund_identity.py::DG2_SHADOW_ENABLED`＝False | `T0/test_fund_identity_dg2.py`（只測身份純函式，**對 S6 字樣無斷言**） | ✓ ∅ ✗ — ✗ | — | D2 R-ID-1（核准欄位數＝0）、#1225-D3 |
| E5 | 「查無」vs「取數失敗」分流：**無法可靠區分時不得顯示「不存在／查無」** | `DEC-2026-11-01-02` G-E3【逐】、2026-11-02 重申 | 無實作 | 無有效斷言 | △ ∅ ✗ — ✗ | 規則已核；「查無」啟用需 confirmed-not-found 來源契約（決策包 Q1） | 屬 Source／Identity Gate，本稿只標 Gate |
| E6 | 篩選器 EXP-0～7（三態篩選、比較上限 3、第一階段**唯讀**、條件 session-only） | 44 §3.3【frozen】；`DEC-2026-10-29-06` Gate 2 A（44 之二十其四）【逐】 | `ui_v2/exp/source.py::load_live` → `ui_v2/exp/logic.py` → `ui_v2/exp/page.py::_render_live` | `T2/test_exp_live_wiring_logic.py::test_規則1_條件用到缺值欄位_無法判定_不算符合不排除`；`T2/test_exp_live_page.py::test_條件作用在資料未備欄位_畫面照列並標無法判定_結論列灰燈不紅`（R5 passed） | ✓ ✓v2 ✓(v2) ? ✗ | ui_v2 只；`ui_v3` 無 | 見 E12 的寫入路徑待釐清 |
| E7 | 結果列「目前條件下有 N 檔符合」**不排名**、不星等／分數／Top N／「精選」；穩定順序用 deterministic key | `DEC-2026-10-27-32`／`-33`【逐】；44 §1.2 | `ui_v2/exp/logic.py`（EXP-0／EXP-2）→ `ui_v2/exp/page.py::_render_exp0`／`_render_exp2_live` | `T2/test_exp_logic.py::test_欄名集合裡沒有分數星等排名推薦四類欄`（R3 passed） | ✓ ✓v2 ✓(v2) — ✗ | 欄名級斷言；畫面字樣掃描見 `T2/test_exp_page.py`（檔級） | `ui_v3` 重做時須重寫同等守衛 |
| E8 | 母體＝選股池**代碼欄**；無名稱／模糊搜尋；服務帳戶缺→照實「選股池未設定雲端來源」，不讀本機暫存檔 | `DEC-2026-11-01-01`【逐】；44 §7.3.2（2026-10-13 裁示） | `repositories/pool_repository.py` → `services/v2_tables/exp_universe.py` → `ui_v2/exp/source.py::load_live` | `T0/test_v2_tables_exp_universe.py::test_只取代碼_其他欄一碰就炸也不炸`、`::test_本機store時不讀本機JSON當母體_照實回未設定雲端` | ✓ ✓v2 ✓ ? ✗ | 真實選股池 Sheet NV | — |
| E9 | 基本資料缺值：缺欄 `◇ 資料未備`＋原因；經理費缺不以最高費代替；部分來源失敗標示來源 | 44 §7.3.2／§7.3.3（2026-10-14 C2 接線）；`DEC-2026-11-08-04`【轉】 | `services/v2_tables/exp_profile.py` → `ui_v2/exp/logic.py`／`page.py` | `T2/test_exp_live_wiring_logic.py::test_規則1_基本資料缺值_基金照列_該格寫資料未備與原因`、`::test_規則5_經理費率留空_原因是不以最高經理費代替`、`::test_規則12_部分來源失敗_顯示一致的值_標示失敗來源與原因`；`T0/test_v2_tables_exp_profile.py` | △ ✓v2 ✓ ? ✗ | `fund_profile` 欄位的 D2 逐列核准＝0 | D2 首批限基金身份／NAV／績效（`DEC-2026-11-11-04`【轉】）；其餘欄位各走 Source Gate |
| E10 | NAV 序列取數（對照／歸一化比較用）：幣別來源自報標示、快取成功 TTL／失敗冷卻、幣別閘 | 44 EXP-2／EXP-3；D2 R-NAV | `services/v2_tables/exp_nav.py` → `ui_v2/exp/*` | `T0/test_v2_tables_exp_nav.py::test_成功_899秒命中_900秒不命中`、`::test_失敗_300秒記憶_冷卻旗標與剩餘秒數`；`T2/test_exp_live_wiring_logic.py::test_規則3與10_幣別值旁掛來源標示_tooltip寫來源自報` | △ ✓v2 ✓ ? ✗ | 無累積 NAV 出處（`NAV_HISTORY_PROVENANCE_VERIFIED=False`） | D2 R-NAV-1／R-NAV-2／R-NAV-5 待客戶；Q0 射程題待一句話 |
| E11 | lookup 結果的歸一化 NAV 比較：基準＝100、**≤3 檔**、同單位 overlay、禁雙軸、強制揭露起始日／基準值／頻率／缺值；與 EXP-3 為兩個獨立元件、選取不互通 | `DEC-2026-11-02-07` UI-12(5)／UI-13／UI-3【逐】；79 §4.4、§9.3 | 無（現有 `services/v2_domain/normalization.py::normalize_pair` **只做兩序列、服務🌍**，N 序列公式未核准） | 無有效斷言 | △ ∅ ✗ — ✗ | 方向核准，**N 序列公式與揭露句未核准** | formula Gate＋公式等級獨立稽核（決策包 Q5）；本稿不提議公式 |
| E12 | 觀察清單／候選清單：第一階段**唯讀**、加入候選暫不可用；池外 code 唯讀查詢、**不自動加入、不寫 Sheet** | `DEC-2026-10-29-06` Gate 2 A【逐】、`DEC-2026-11-01-02` G-E6【逐】；44 之二十其四第 3 條；`ui_v2/readonly.py` 檔頭（`DEC-2026-10-25-04` J-6） | v2：`ui_v2/exp/page.py::_render_exp5`、`ui_v2/readonly.py::strip_write_controls`；v3：無頁 | `T3/test_ui_v3_readonly_guard.py::test_ui_v3_has_no_write_surface`（v3 全樹唯讀，無 🔍 頁）；`T2/test_readonly_live_pages_page.py::test_live_page_has_no_write_controls`（R6 passed）。⚠️ 同時 `T2/test_exp_live_page.py::test_EXP5加入觀察清單_寫已存與勾起的聯集` 仍測**寫入路徑** | △ △v2 △ ? ✗ | **兩組測試的關係（寫入路徑被隱藏或被測）本稿未釐清＝NV** | 以 `readonly` 守衛為準的讀法屬單組判讀；CAP-GATE-05（候選池身分）未核准 |

**🔍 Gate-only**：ISIN 啟用、`full_key` 通路後綴、「查無」顯示、結果卡欄位（類別／報酬／風險／費用／規模／經理人皆無來源）、N 序列歸一化公式、D2 R-ID／R-NAV 逐列、New UI2 🔍 線框與位置（Q4／Q7／Q9）、候選池寫入。

#### 2.2.4 🤖 AI 投資總結（`ui_v3` 僅佔位；12 列）

| # | 需求項 | spec／DEC | P→C | 可執行斷言 | 狀態 | 證據／NV | 缺口 |
|---|---|---|---|---|---|---|---|
| G1 | 導覽項**可見但不可點**、不註冊頁；Phase 7 前**建構時即拒絕** `registered=True` | `DEC-2026-10-29-07`【逐】、`-10-29-06` 其一第 2 條；80 §7.4 | `ui_v3/shell/registry.py::PageSlot.__post_init__` → `ui_v3/shell/nav.py::nav_items` → `ui_v3/pages/chrome.py::disabled_side_html`／`disabled_top_html` | `T3/test_ui_v3_page_registry_guard.py::test_ai_page_is_never_registered_before_phase7`、`::test_ai_slot_cannot_be_constructed_as_registered`；`T3/test_ui_v3_navigation_shell.py::test_not_yet_open_label_is_not_open_for_ai_and_under_development_for_the_rest`、`::test_disabled_nav_items_are_not_links_and_say_under_development` | ✓ ✓v3(佔位) ✓ — ✗ | 這是**入口佔位**，不是 🤖 頁 | Phase 7 Gate |
| G2 | `ActionSlot`：`state` 只可為 None 或「無法判定」、`source_ref` 必空；「無法判定」必帶 `reason` | 80 §2／§6；79 §6.1；`DEC-2026-10-26-01`【逐】 | `ui_v3/viewmodels/action_slot.py::ActionSlot`；**consumer：無**（`git grep` 僅 `viewmodels/__init__.py` 匯出） | `T3/test_ui_v3_viewmodel_contract.py::test_action_slot_absent_or_undetermined_only_before_phase7`、`::test_phase7_gate_is_closed_in_batch1`、`::test_action_slot_undetermined_must_explain_and_cannot_cite_a_source` | ✓ △adp ✓ — ✗ | `ACTION_SLOT_SOURCES_ENABLED=False` | Gate 通過後須有意識改旗標並改測試 |
| G3 | 六個行動詞語意邊界 SSOT：續抱／觀察／降低曝險／減碼／替代比較／無法判定 | `DEC-2026-10-27-22`【逐】；67 §2 | `shared/ui_semantics/rules.py::ACTION_WORDS` → `ui_v3/viewmodels/action_slot.py::ACTION_VOCABULARY` | `T3/test_ui_v3_viewmodel_contract.py::test_action_vocabulary_is_exactly_the_six_words_of_67`、`::test_action_slot_rejects_words_outside_vocabulary` | △ ✓v3(詞彙) ✓ — ✗ | 只鎖**詞彙**；各詞的**觸發規則未定義**（67 §1 表） | BL-0495／0496 |
| G4 | System Action State／Risk Cap／「減碼」deterministic trigger（行動的唯一來源） | `DEC-2026-11-02-07` UI-6 A【逐】（僅定義）；BL-0495／0496（待客戶裁示） | 無 | 無有效斷言 | △ ∅ ✗ — ✗ | 數值、trigger、輸出走 BL-0495／0496 | Stop Gate（正式公式／投資語意） |
| G5 | Decision Digest schema 與 production 生產者（Phase 7 前置；與 D2 契約分離） | BL-0527（open）；`DEC-2026-11-11-04` D2-G2＝A【轉】；`DEC-2026-11-02-07` UI-8／UI-9 | 無（`git grep -i "decision digest"` 僅註解／docstring 命中，無 `class`／`def` 定義；單組） | 無有效斷言 | ✗ ∅ ✗ — ✗ | 七項缺口見 67 §5.6 | Phase 7 前不啟動 |
| G6 | 版面四區：System State｜OneBrain Interpretation｜Maximum Falsification（最大反證）｜Evidence（可展開） | `DEC-2026-11-02-07` UI-14 A【逐】（**方向核准，Phase 7 實作時出線框再定**）；67 §8.9 | 無 renderer | 無有效斷言 | △ ∅ ✗ — ✗ | 超出 67 §6.1 固定輸出（79 UI-14 自陳） | 線框屬 Phase 7 |
| G7 | 不放假資料、不顯示機率或信心（沒有 calibration contract 前禁止） | 79 C-2／`DEC-2026-11-02-07` UI-1 A【逐】；80 §7.4 | 無頁可違反 | `T3/test_ui_v3_fixtures_are_fake_guard.py::test_all_fixture_data_is_visibly_fake_and_never_rule_ref_or_action`（防 fixture 冒充，**非**機率守衛）。機率／信心字樣無專屬斷言 | ✓ ∅ △ — ✗ | — | 做頁時須新增字樣守衛 |
| G8 | 輸出「客戶六項」對映 67 §6.1 六段／§8.9 四區 | BL-0540 G-5（待客戶裁示） | 無 | 無有效斷言 | ✗ ∅ ✗ — ✗ | #1225 §2.2 C3：未確認前不改 67 | #1225-G3 |
| G9 | Runtime 未啟用時整區只顯示「AI 分析暫不可用／無法判定」 | 75 §12；80 §7.4 | 無 renderer；導覽字樣在 `shared/ui_semantics/rules.py` | `T3/test_ui_v3_navigation_shell.py::test_not_yet_open_label_is_not_open_for_ai_and_under_development_for_the_rest`（僅導覽標籤，**非**頁內降級字樣） | △ ∅ △ — ✗ | 頁內降級字樣無實作 | Phase 7 |
| G10 | OneBrain 架構與 UI ViewModel≠Decision Digest 分流（架構／治理，**非 runtime 動工授權**） | `DEC-2026-10-31-03`【逐】、`-11-08-02` D1 方案 C【轉】；75；80 §16.3～16.4 | 文件層 | 不適用（文件） | ✓(文件) ∅ — — ✗ | 資料契約先行（D2→Digest 後續） | — |
| G11 | A 線現行 AI 行為（Old UI `services/ai_service.py`／`ai_prompts.py`）與正式裁示牴觸；A 線**不遷移** | BL-0528（待客戶裁示） | Old UI 路徑；**不屬 New UI2** | `T0/test_ai_service.py`、`T0/test_ai_prompts.py` 存在，**本稿 NOT RUN** | ✗ ✗v3(Old UI 有) ? — ✗ | Old UI 有 AI 摘要殼 **≠ 🤖 已實作** | #1225-G9；BL-0528 處置待客戶 |
| G12 | Preview 對「已登錄卻無 renderer」的頁 **fail loud**，不畫空殼 | `DEC-2026-10-27-10`／`-12`（registry 檔頭引） | `ui_v3/app_preview.py::main` | `T3/test_ui_v3_preview_not_formal_guard.py::test_preview_main_fails_loud_when_registered_page_has_no_renderer`、`::test_preview_main_fails_loud_when_no_page_is_registered` | ✓ ✓v3 ✓ — ✗ | — | — |

**🤖 Gate-only**：Digest schema／producer、Risk Cap、減碼 trigger、System Action State、Interpretation／Falsification 內容與任何機率或信心、AI 輸出對映、runtime 啟用、A 線 prompt 處置。

#### 2.2.5 ⚙️ 設定（`ui_v3` **無頁**；`ui_v2/set` SET-0～8 為 maintenance-only；12 列）

| # | 需求項 | spec／DEC | P→C | 可執行斷言 | 狀態 | 證據／NV | 缺口 |
|---|---|---|---|---|---|---|---|
| T1 | New UI2 ⚙️ 頁本身：登錄 `wireframe_not_approved` | `DEC-2026-10-29-06`【逐】；80 §7.5 | `ui_v3/shell/registry.py::IA_PAGES`（`set`） | `T3/test_ui_v3_page_registry_guard.py::test_only_market_page_is_registered_so_no_empty_shell` | △ ✗v3 ✓ — ✗ | 守衛鎖住「未接線」 | New UI2 ⚙️ 線框（BL-0536-G4，#1225-G10） |
| T2 | SET-0 可信度結論燈（燈的外框照 44；未設定時不重複印） | 44 §3.5 SET-0【frozen】 | `ui_v2/set/logic.py` → `ui_v2/set/page.py::_render_set0` | `T2/test_set_logic.py::test_八塊的塊名逐字引44`、`::test_八塊的回答什麼逐字引44現行那一句`；`T2/test_set_live_logic.py::test_ID未設_燈照44外框_其餘位置統一一句_不重複印` | ✓ ✓v2 ✓(v2) ? ✗ | 設定試算表真實標頭／值域 NV | — |
| T3 | SET-1 資料新鮮度、SET-2 來源健康：失敗訊息與 `fetch_log` 逐字相同且經遮蔽 | 44 §3.5 SET-1／SET-2 | `services/v2_tables/settings_store.py`（fetch_log）→ `ui_v2/set/page.py::_render_set1`／`_render_set2` | `T2/test_set_live_page.py::test_M11_SET版_取數失敗訊息與fetch_log逐字相同_SET2與SET6下一行加註`（R5 passed）；`T0/test_v2_tables_masking.py::test_M1_含金鑰網址的連線失敗例外字串` | ✓ ✓v2 ✓ ? ✗ | 真實 Sheet NV | — |
| T4 | SET-8 各頁資料狀態總表；資料健康度**集中承接**於 ⚙️ | 44 SET-8（BL-0250 3-B）；80 §16.2；BL-0540 G-3（待裁） | `ui_v2/page_health.py` → `ui_v2/set/page.py::_render_page_health` | `T2/test_health_logic.py::test_受影響的塊每一塊恰一次`（健康度邏輯；**未逐測試名對應 SET-8，單組判讀**）；`T2/test_set_page.py::test_八塊的代號與標題都畫出來了` | △ ✓v2 △ ? ✗ | 「集中 ⚙️」vs「44 頁內資料狀態塊」並存（#1225 C4） | #1225-G3：各頁 wireframe 承接 vs 44 解凍 |
| T5 | 第一階段**唯讀**：正式模式 SET-4 參數編輯整塊不畫、不顯示寫入控制 | `DEC-2026-10-25-04` J-6、2026-10-26 J-14（`ui_v2/readonly.py` 檔頭）；`DEC-2026-10-26-01` | `ui_v2/readonly.py::visible_codes`／`strip_write_controls`；v3：全樹唯讀 | `T2/test_readonly_live_pages_page.py::test_set_page_has_no_set4_block`、`::test_live_page_has_no_write_controls`（R6 passed）；`T2/test_readonly_write_surface_guard.py::test_no_settings_sheet_l1_write_calls`；`T3/test_ui_v3_readonly_guard.py::test_ui_v3_has_no_write_surface` | ✓ ✓v2 ✓ — ✗ | — | 寫入能力日後須另案（`DEC-2026-10-29-06` 其四第 2 條） |
| T6 | SET-5 重新取數／SET-6 取數紀錄（市場指標、淨值層；只記一筆 fetch_log） | 44 SET-5／SET-6 | `services/v2_tables/settings_store.py::refetch_market_indicator`／`refetch_nav` → `ui_v2/set/page.py::_render_set5` | `T0/test_v2_tables_settings_store.py::test_成功_記開始紀錄_記列_記ok結束紀錄`；`T2/test_set_live_page.py::test_重新取數_淨值層按下後只記一筆fetch_log_SET1淨值列印時間與新句` | ✓ ✓v2 ✓ ? ✗ | 寫入設定試算表受 `DEC-2026-10-25-04` 第一階段限制，**與 T5 的關係本稿未釐清＝NV**；`refetch_nav` 仍走舊 `POLICY_SHEET_ID`（`ui_v2/app_preview.py` 檔頭，BL-0460） | 重新取數的正式授權範圍待釐清 |
| T7 | Google 登入／帳號與 Active Sheet 選擇器：驗證成功才切換、失敗保留原 Active、不 fallback；OAuth scope／callback／credential **不得改** | 44 之二十其三；`DEC-2026-11-05-01`（登入入口設計方向）、`DEC-2026-10-30-05`（OAuth 回原頁 Gate 採 F＝維持現況） | `ui_v2/set/page.py::_render_login`／`_render_picker`；Preview 帳號入口＝無 | `T2/test_set_picker_logic.py::test_picker只在正式登入後出現_其餘一律hidden`、`::test_待確認_顯示待確認尚未使用_且使用中仍是舊的`；`T2/test_set_login_logic.py::test_未登入_授權網址不是Google端點_不畫連結` | △ ✓v2 ✓ ? ✗ | HANDOFF §1：Preview 帳號入口 NOT IMPLEMENTED；真實 OAuth NV | 登入入口位置落地需 ⚙️／Shell 線框 |
| T8 | 規則登錄（Rule Registry）**唯讀殼**：只列名稱與出處 | `DEC-2026-11-02-07` UI-10 A【逐】；80 §7.5 | 無（`git grep -il "規則登錄\|rule registry" -- '*.py'` 僅 `ui_v3/viewmodels/components.py` 註解命中，單組） | 無有效斷言 | △ ∅ ✗ — ✗ | Rule ID／rule_version／門檻引用格式另走 Gate | #1225-G10 |
| T9 | 通知偏好／送達健康／audit（UI-15 A）；Digest viewer（待 Digest production） | `DEC-2026-11-02-07` UI-15 A【逐】；79 §17.9～17.10 | 無 UI；`infra/line_push.py` 存在但**未接 New UI2** | 無有效斷言 | △ ∅ ✗ — ✗ | UI-15 A 只凍結 ownership／語意邊界，**不等於授權 production migration** | 版面、cadence、fingerprint 皆另走 Gate |
| T10 | 不顯示 secret／token；錯誤原文遮蔽 | `CLAUDE.md` §1；80 §7.5「不顯示 secret」 | `services/v2_tables/masking.py`（遮蔽函式）→ `ui_v2/set/source.py::mask_error` | `T0/test_v2_tables_masking.py::test_M2_407代理驗證失敗`、`::test_M3_代理帳密直接出現在訊息裡_主機與埠保留`；`T2/test_personal_token_mask.py`（檔級） | ✓ ✓v2 ✓ — ✗ | — | — |
| T11 | 雙模式（☀️淺色預設＋🌙使用者手動深色）：入口優先考慮 ⚙️；正式深色方向＝深色主內容＋深色側欄 | `DEC-2026-11-11-01`（雙模式列下一階段）【轉】、`-11-11-02`（僅授權隔離 PoC）、`-11-11-03` G1～G6（方向，**不授權任何 UI／Runtime 施工**）【轉】 | `poc/dual_theme_isolated/*`（隔離 PoC；守衛：`tests/poc_dual_theme/test_poc_dual_theme_guard.py::test_no_production_path_references_the_poc`） | `tests/poc_dual_theme/test_poc_dual_theme_guard.py::test_poc_has_no_write_surface_and_never_names_ui_v3_in_code`（R6 passed；對比度瀏覽器測試 NOT RUN） | △ poc ✓(PoC) — ✗ | PoC≠`ui_v3` 實作；偏好保存機制無裁示 | #1225-G5：深色模式正式施工 |
| T12 | 資料健康度之外的低頻全域功能（Google 帳號控制位置、Sheet 選擇位置）與 Shell 共用面（Status Bar、更新資料 CTA） | 44 之二十其三第 1、5 條；`DEC-2026-11-03-10`／`-11` | `ui_v3/pages/chrome.py::render_status`（🌍 專用資料來源）→ `ui_v3/adapters/shell_status.py` | `T3/test_ui_v3_navigation_shell.py::test_status_counts_cover_only_the_registered_items_actually_checked_and_never_claim_system_wide_health` | △ △v3(Shell 屬 🌍 批) ✓ — ✗ | Shell 狀態只涵蓋已註冊頁，**不得讀成全站資料健康** | 全站健康度承接屬 T4 的 G-3 |

**⚙️ Gate-only**：New UI2 ⚙️ 線框、Rule ID 格式、通知偏好版面與 cadence、Digest viewer、深色模式施工與偏好保存、`pay_date` amendment（BL-0534）、寫入設定試算表的正式授權範圍。

### 2.3 冒充風險清單（容易被誤讀為已完成的點）

| # | 容易被誤讀為 | 實際（附出處） |
|---|---|---|
| 1 | 🌍 Preview 已實作＝production 已上線 | `app.py` 對 `ui_v3`／`ui_v2` **0 命中**（`git grep -n "ui_v3\|ui_v2" -- app.py`）；`T3/test_ui_v3_preview_not_formal_guard.py::test_formal_entry_candidates_do_not_reference_ui_v3`；`ui_v3/app_preview.py` 檔頭「絕不可設為 Streamlit Cloud 的 main file」；`DEC-2026-11-02-06`；Cloud 入口設定 repo 內查不到＝NV（HANDOFF §1） |
| 2 | 「ui_v2 五頁 live／完成」＝New UI2 完成 | `ui_v2/app_preview.py::PAGES` 只 4 頁；`DEC-2026-11-02-05` NG-2 ui_v2 maintenance-only；`ui_v3` registry 僅 `mkt` 註冊（`T3/…registry_guard`）；**ui_v2 💼 的順序與 `DEC-2026-11-04-01` 相反**（A2） |
| 3 | `app.py` 的 9 個分頁中的 4 個 `[新]` 並行預覽＝New UI2 | 那 4 個來自 **Old UI 樹 `ui/views/page_0x_*.py`**（`app.py` 的 `_preview_tab_label`），既非 `ui_v2` 也非 `ui_v3`；`DEC-2026-11-02-02`：Old UI 永久 read-only |
| 4 | fixture／stub／PoC 通過＝正式資料正確 | `tests/ui_v3/market_stubs.py` 為合成資料（`fund_newui2_market_g3_g6_build_evidence_2026_11_11.md` §0 自陳「不連 FRED／Yahoo」）；`ui_v3/fixtures` 有守衛 `test_ui_v3_fixtures_are_fake_guard.py`；`poc/dual_theme_isolated` 為 PoC |
| 5 | 探針成功＝正式來源已核准 | Yahoo 受控探測僅 4 次 HTTP（`DEC-2026-11-09-08`、`yahoo_indices_sp_probe_result_2026_11_09.md` 自陳「單次探測不得判定永久日期規則」）；`DEC-2026-11-09-10` Q3 收盤判準＝**暫行**；FX 冬令探測「證據不足以開閘」（`fx_obs_date_winter_probe_2026_11_08.md`） |
| 6 | CI 四條 success＝畫面／資料已驗 | Slow／Visual 為 job 級 `continue-on-error`（`.github/workflows/pr-check.yml`）；Visual lane 截圖對象是 **ui_v2 的五頁 fixtures**（`tests/visual_fidelity/test_ci_fixture_screenshots.py`）、檔頭自述「CI fixture screenshot ≠ production-like Cloud screenshot」；CI 全程用替身資料；本稿 R1～R6 也一樣 |
| 7 | 舊 44 的「五頁」＝New UI2 五頁 | 44 §3.0 的五頁是**舊名**（市場總覽／持倉體檢／標的探索／資產配置／設定與診斷），New UI2 把 ⚖️ 併入 💼 並新增 🤖；`ui_v2/app_preview.py` 檔頭表仍列舊名；`DEC-2026-10-29-06` 為準 |
| 8 | 有 `assets_source.py`（契約 11＋變異 6＋隔離 12 筆測試）＝💼 已做 | 該 adapter **0 production caller、0 頁**（`T3/test_ui_v3_assets_source_import_isolation.py::test_nothing_in_ui_v3_references_the_adapter_so_no_page_is_wired`）；證據 schema＝內部候選 |
| 9 | `ActionSlot`／六詞守衛＝🤖 功能 | `ActionSlot` 0 頁消費；只鎖詞彙，行動觸發規則未定義（67；BL-0495／0496）；Old UI AI 摘要殼 ≠ 🤖（BL-0528） |
| 10 | 「Shell 驗收」DEC＝使用者驗收通過 | `DEC-2026-11-03-11` 是客戶審查後**要求修改**並裁示字樣，內含「仍待驗證清單」；G7（Cloud／WebView／真機）待客戶 go（`DEC-2026-11-11-01` 後續欄） |
| 11 | 客戶口述「Secrets 已更新」＝FRED／Yahoo 在 Cloud 可用 | `secrets_recovery_verification_2026_11_10.md` §0：Cloud 端「無法驗證」 |
| 12 | 要點轉述的 DEC＝逐字裁示 | `DEC-2026-11-10-07`、`-11-11-01`、`-11-09-02/-03/-04`、`-11-05-03/-04`、`-11-08-02`、`-11-11-03/-04`、`-11-12-01/-02`、`-11-13-01` 皆自述「要點轉述、非逐字」；引用時不得當逐字稿 |
| 13 | D2 草稿／決策包的「推薦」＝已核准 | D2 核准欄位數＝**0**（`DEC-2026-11-11-04`【轉】）；#1227 兩份包「非客戶裁示」；`docs/v2/82` 僅部分核准 |
| 14 | 本機測試綠＝CI 綠（反向亦然） | 本機 Python 3.13 vs CI 3.11：R3 有 5 筆 digest 失敗、R2 有 1 筆 skip，皆因 float `sum()` 語意（R4）；兩邊都**不是** S4 |

### 2.4 與 #1225 §2 的最小差異

**新補（#1225 沒有的軸或事實）**

| # | 內容 |
|---|---|
| 1 | #1225 §2.3 把「狀態／契約齊備度／可否施工」混成一欄；本節拆成 S1～S5，並逐列給斷言。 |
| 2 | #1225 §6.1 寫「未執行任何測試」；本節已實跑 R1～R6（含環境差異與 5 筆 3.13 失敗的成因）。**這會改變 #1225 §1「已有且可驗證」的證據強度**：「測試檔存在」已升級為「本機 3.13 實跑 passed／CI 同樹 success」，**但仍不是 S4**。 |
| 3 | 新發現：`ui_v2` 💼 第一屏順序（summary 在 Primary 前）與 `DEC-2026-11-04-01` 已核准的 New UI2 順序**相反**，且有測試鎖住舊順序（A2）。 |
| 4 | 新發現：CI Visual lane 的截圖對象是 `ui_v2` fixtures，**不涵蓋 `ui_v3`**；ui_v3 的瀏覽器級斷言只在 Slow lane（informational）。 |
| 5 | 新發現：Old UI `app.py` 的 4 個 `[新]` 並行預覽分頁來自 `ui/views/*`，與 New UI2 再區分（§2.3 #3）。 |
| 6 | #1225 §2.3 「🌍 ui_v3 Preview 已實作並有 live 接線」補限定：**live 接線存在，但全部 ui_v3 測試用合成 stub；無 Cloud／真實資料驗證（S4＝NV）**。 |
| 7 | 🤖：`ActionSlot` 0 頁消費（`git grep`）、導覽佔位與詞彙守衛各有測試，但**不構成功能**。 |
| 8 | 🔍：lookup／ISIN／身份字樣在 `ui_v2/exp` 與 `ui_v3` 均 0 實作，且無任何斷言；現有 N 序列歸一化函式僅兩序列。 |
| 9 | `ui_v2` 寫入路徑測試（EXP-5、SET 重新取數）與「第一階段唯讀」裁示的關係未釐清（E12、T6），登記為 NV。 |

**與 #1225 結論不同／需更新（old→new）**

| # | #1225 原文 | 本節更正 |
|---|---|---|
| 1 | §2.2 C2：HANDOFF §0 第 4 點把 82 與 79／80／81 並列為「正式 SSOT」，「需確認」 | **已解決**：main `2f13fade` 的 HANDOFF §0 第 4 點現文已標「82＝部分核准草案、非現行規格」（本稿讀 `docs/HANDOFF.md`）；#1225 的待辦可改記為已修（#1226 E1）。 |
| 2 | §0 第 5 點／§1 各表的「已有且可驗證＝不是我們跑綠」 | 對 §2 五頁相關測試，本節已有本機實跑結果；**其餘 #1225 §1 的資料層列未重跑**（R2 只涵蓋 `v2_tables`／`v2_domain`）。 |
| 3 | §2.3「🌍 資料契約齊備度＝高」 | 契約／VM／守衛面屬實；**S4＝NV 與 S5＝否須同欄揭露**，不得單獨引用「高」。 |

**未變（確認一致，不重寫）**：五頁名稱與順序、`ui_v3` 僅 🌍 註冊、🤖 建構時拒絕 `registered=True`、💼 摘要四格一律 Missing、`ui_v2` Preview 為 4 頁、BL-0545 為唯一全域 NEXT、D2 核准欄位數＝0。

### 2.5 盲點與 NOT VERIFIED

1. **本機環境 ≠ CI**：Python 3.13.18（CI 3.11）；無 playwright（ui_v3 瀏覽器級 84 筆、ui_v2／poc 瀏覽器級若干筆 NOT RUN）；副本為單一 commit（16 筆因淺層 clone skip）；`pre-commit` 未安裝。R4／R5／R6 使用 `builtins.sum` 診斷墊片，**不是 CI 的執行方式**。
2. **未跑的測試**：`ui_v2` slow 標記全集 1116 筆只跑 7 檔（R5）＋R6 的 2 檔；`tests/` 其餘 Old UI 與 `repositories`／`services` 測試未跑（含 G11 的 `test_ai_service.py`）；Visual lane 的 `test_ci_fixture_screenshots.py` 未跑（需 Chromium）。
3. **CI 數字**：僅 check-run `conclusion` 為本稿實查；Slow 1283／Visual 7／Fast 無數量三項取自 PR #1227 描述（作者自陳），未重讀 step log。Slow／Visual 為 informational。
4. **全稱句**：「0 命中」「0 caller」「僅 N 檔」皆單組字面 `git grep`（`lookup|ISIN`、`ActionSlot`、`decision digest`、規則登錄、`淨投資金額`、`app.py` 對 `ui_v3`），**不含別名、動態組字**，未經第二組驗證。
5. **「無有效斷言」是單組判讀**：只掃了測試名稱與抽讀的內容，未逐檔讀完 `tests/ui_v2`（約 150 檔）；可能存在未被我找到的斷言。
6. **S1 的【逐】僅表示逐字檔存在**，未逐句核對 DEC 與逐字檔；【轉】者客戶可推翻；`DEC-2026-11-12-01`／`-02`／`-13-01` 只當優先序與「不授權」邊界引用。
7. **S5**：只掃 `docs/DECISIONS.md`／`docs/HANDOFF.md` 的「驗收」字樣；`ui_v2` 另有 BL-0250 3-B 實機驗收通過（`DEC-2026-10-20-02`，範圍＝四頁件數 Q1）；3-D「五頁最終實機驗收」的通過紀錄本稿**未找到**（不等於不存在）。客戶口頭驗收若未入 repo，專案 AI 無從核對。
8. **未驗**：81 §檔頭「獨立稽核本批尚未完成」之後是否補稽核（`DEC-2026-11-03-02` 要求每批至少一組）、`DEC-2026-11-03-04` 要求的公式等級獨立稽核紀錄；A4 `_build_alo2` 缺 FX 落差沿用 #1225 未重驗；E12／T6 的寫入路徑與唯讀裁示關係。
9. **範圍之外**：未讀 `docs/v2/44`（約 94 萬字元）全文，僅依 #1225、目錄與抽讀；`docs/v2/79`／`80`／`82` 只讀相關節。
10. 本節 R1～R6 為單組在隔離環境的結果；**S3 的最終依據仍是 CI 同 head**，S4／S5 無法由本稿代替客戶與真實環境取得。

## 3. NAV／持倉／配置：資料 lineage 與契約 delta（Batch 1 第 3 項）

> 性質聲明見本檔頭統一聲明（研究證據；非客戶裁示、非授權施工；單組作者，尚待非作者 QA）。方法：讀碼＋讀文件＋字面 `git grep`＋在 `git archive` 副本上實跑既有測試與純函式小實驗（不連網、不碰憑證與 Sheet、不改 repo）。
> **執行環境揭露**：測試跑在 Python **3.13.18**（pytest 9.2.0、pandas 2.3.3、numpy 2.5.4、streamlit 1.59.2、pandera 0.36.0）；CI 的 `.github/workflows/pr-check.yml` 釘 Python **3.11**，兩者不同，§3.4 的結果**不等於** CI 結果。
> 本節只做**最小差異**：#1225（`ui_data_contract_audit_2026_11_12.md` §1）與 #1227（`d2_min_approval_pack_r_id_1_r_nav_1_2026_11_13.md`、`calc_metrics_1y_estimate_path_verification_2026_11_13.md`）已有的結論一律只引用、不重述。
> 不新建第二份正式 data dictionary；不更動 Schema、source、公式、資料；D2 核准欄位數仍為 **0**；DG2、FX、ISIN、D2-A＝B 實作、BL-0545 一律維持關閉／BLOCKED。「推薦／總管讀法」可被客戶推翻。
> 路徑一律「檔案::符號」不寫行號。全稱句（「0 命中」「只有 N 處」）皆為單組字面 `git grep`，**未經第二組驗證**，指令見 §3.6。缺值一律寫 ⬜（UNAVAILABLE），**不得讀成 0、中性或正常**。

### 3.0 結論先行

1. **三條鏈的結構與前兩份證據一致，沒有推翻任何既有結論**；本節補的是「維度逐項保留／丟棄」與五個前兩份未提的新事實（下列 2～6）。
2. **側車（`provenance`）有、畫面丟棄的維度很多**：`nav` 列本身沒有 provider 欄（只有 `source_tier`＝恆為「淨值」）；供應者字串、取得時間、幣別出處、`latest_from`、`chain` 等全在 L2 側車；`ui_v2` 的 `hld`／`alo` 只讀其中 `cache_fallback`／`stale`（`hld` 另讀 `latest_from`），`exp` 才把供應者與取得時間放進 tooltip。代碼對照的 `mapping_source` 三個消費端全丟（§3.1-A）。
3. **新發現（中）**：B 線經 A 鏈**接受**以選股池手填 ISIN 查出的晨星 secId（`secid_origin="pool_isin_search"`），來源不進 `provenance`、也沒有測試釘住「收或拒」；現有測試只釘「池表／寫死表照收、名稱／代碼搜尋拒收」（§3.3 Δ3-02）。
4. **新發現（中）**：💼 市值基準的 FX 對齊（`fx_row_as_of`）**沒有匯率新鮮度上限、也不讀 `value_unit`**；純函式實測：10 個月前的匯率照乘、單位相反（美元／新臺幣）的列照乘，差 1000 倍（§3.3 Δ3-03）。`value_unit` 不讀已登記為 `ALO-GAP-匯率單位待裁`；**匯率過舊未見登記**。
5. **同輸入對照（補 #1225 §2.4）**：缺 USD 匯率時，`ui_v2` ALO-2 印「現金 100.0%／+90.0 pp／外」，同一組輸入餵 `build_allocation_evidence` 則回 `denominator.verdict=incomplete`、`chart_comparability=not_comparable`（§3.3 Δ3-04）。另實測「有持倉被略過、目標類別無持倉」時 ALO-2 仍印 `0.0%`（Δ3-05）。
6. **`tests/test_alo_core_golden.py` 在 Python 3.13 浮點差 1 ulp 而失敗，根因已定位**：`_build_alo2` 的 `sum()` 在 CPython ≥3.12 改為補償加總；同一份黃金矩陣在系統 Python 3.11.18 上 **0 差異**（Δ3-01）。`requirements.txt` 註解稱 Streamlit Cloud 已遷 Python 3.14（實際執行版本 NOT VERIFIED），故**正式環境與 CI 的 `sum()` 行為可能不同**。
7. `nav` 列 `is_estimated` 在 live 路徑恆為 `False`（#1227 N-6 已提）；補充**後果**：`hld` HLD-6 的「推估」徽章在 live 不可達（Δ3-06）。
8. 所有 UI 消費端只有 `ui_v2` 的 `hld`／`alo`／`exp`；`ui_v3` 沒有任何頁面消費這三條鏈（`ui_v3/adapters/assets_source.py` 無 import 者，只有測試）。

---

### 3.1 Lineage 逐層表

**圖例**。每格狀態只用四種：**保留**（該層有且往下層傳）／**丟棄**（該層有、下一層讀不到或不渲染）／**無**（該層沒有這個維度）／**NV**（NOT VERIFIED）。缺值一律 ⬜。「消費端」＝`ui_v2/{hld,alo,exp}`；`ui_v3` 見各表末列。

#### 3.1-A NAV 鏈

鏈名沿用 #1227：`repositories/fund/*`（A 鏈）→ `services/v2_tables/nav_dividend.py` → `ui_v2`。入口有兩條：持倉路徑（`hld`／`alo`，幣別標籤＝持倉手填）與 🔍 找基金（`exp`，幣別標籤＝基本資料頁自報）。

| 層 | producer（檔::符號） | 輸出欄位／側車 |
|---|---|---|
| L1 取數 | `services/moneydj_fetcher.py::auto_fetch_moneydj`（A 鏈，內經 `repositories/fund/fund_orchestration.py::_fetch_fund_single` 與 `repositories/fund/sources.py::_src_*`） | 回 dict：`series`（`attrs`：`source`、`fetched_at`、`currency`、`cache_updated_at`、`nav_quality`、`secid_origin`、`currency_id_origin`、累積表標記）、`full_key`、`data_source`、`chain_started_at`、失敗瀑布原文。**同一次呼叫另算 `metrics`（`calc_metrics`）**，見 §3.3-C |
| L2 代碼對照 | `services/v2_tables/fund_keys.py::resolve_full_keys` | `results[]`：`input`、`ok`、`full_key`、`parsed_code`、`portal`、`mapping_hit`、`error`；頂層 `provenance.mapping_source` |
| L2 轉接 | `nav_dividend.py::_nav_from_chain`、`_chain_ccy_gate`、`rows_from_nav_series` | `nav` 7 欄（`contract.NAV_FIELDS`）＋側車 `provenance[code]`、`withheld[code]`、`errors[code]`、`skipped[code]`、`fetched`、`skipped_rows` |
| 消費端 | `ui_v2/hld/{source,live,logic}.py`、`ui_v2/alo/{source,live,logic}.py`、`ui_v2/exp/{source,live}.py`（經 `services/v2_tables/exp_nav.py`） | `hld` HLD-1／2／3／5／6／7／8；`alo` 市值基準各塊；`exp` EXP-2／3 淨值格 |

| 維度 | L1（A 鏈） | L2（nav 列／側車） | 消費端是否保留 | 狀態 ＋ 證據 |
|---|---|---|---|---|
| source／provider | `series.attrs["source"]`（例：`Morningstar:UK:timeseries:<secId>`、`GitHubActions:cache/nav/<code>.json`）；`res["data_source"]` | **nav 列無此欄**（44 §4.2）；側車 `provenance[code]["source"]`、`["chain"]={page_type,data_source,fetched_at_from}` | `exp`：保留（cell 的 `source_tag`＋tooltip，`ui_v2/exp/live.py::_nav_tip`）；`hld`／`alo`：**丟棄**（`alo` 明寫 ALO-GAP-來源徽章；`hld` 只讀 `cache_fallback`／`stale`／`latest_from`） | 保留（exp）／丟棄（hld、alo）。實驗 E1、E3 |
| canonical identity | 輸入 `fund_code`；A 鏈自己查對照表並回 `full_key` | `resolve_full_keys` 產 `full_key`（production 主鍵）；A 鏈回的 `full_key` 必須等於它，否則整檔 ⬜。`nav` 列的 `fund_code` ＝呼叫端原值（去前後空白），**不含 `full_key`**；DG2 canonical 未接（`DG2_SHADOW_ENABLED=False`） | 三個消費端都只取 `["results"]`，**丟棄** `provenance.mapping_source`（`ui_v2` 內 `mapping_source` 0 命中） | 保留（full_key 比對）／丟棄（mapping_source）。實驗 E6 |
| NAV 值 | 各來源序列值 | `nav_orig_ccy`：`float()` 原樣，非有限／非正／布林／溢位不寫，同日不同值全不寫 | `hld` HLD-6 以 `:.4f` 顯示；`alo` 取 `latest_nav_row` × 單位數；`exp` 取最新一筆 | 保留。測試見 §3.4 |
| ccy／FX 方向 | 序列可能自報 `attrs["currency"]`（晨星為**請求參數**回聲）；A 鏈 `res["currency"]` 可能是硬編表／推定值 | **A 鏈幣別一律不採用**（`_nav_from_chain` 移除 `currency` attr，另存 `v2_declared_ccy` 只供比對）；`nav.ccy` ＝持倉手填（`hld`／`alo`）或 meta 自報（`exp`），出處記 `provenance["ccy_source"]`（`holding_user_input`／`meta:…`）；序列宣告與標籤不同、或非原生來源（`Morningstar:`／`Yahoo:`／`AlphaVantage:`）未宣告 → 整檔不寫。**nav 表無 TWD 欄**；FX 方向僅在配置鏈（§3.1-C） | `ccy` 欄：三端保留；`ccy_source`：**三端皆不渲染**（`ui_v2/{hld,alo,exp}` 對輸出側 `ccy_source` 無讀取） | 保留（ccy）／丟棄（ccy_source）。**原生來源未宣告幣別時，標籤只憑使用者說法、無獨立驗證**（實驗 E1／E1b；#1227 N-1 已指） |
| as-of date | 序列索引（日期粒度） | `nav_date`（`YYYY-MM-DD`；帶時區索引、NaT、1900 前、晚於台灣當日者不寫） | 三端皆以 `nav_date` 算「距今日數」，不以 `fetched_at` | 保留 |
| fetched_at | 序列 `attrs["fetched_at"]`（L1 取得當下）；預存檔另有 `cache_updated_at`（GitHub Actions 寫入時間）；A 鏈 `chain_started_at` | 列欄 `fetched_at`（UTC）。**取值依分支三種語意**：(1) 序列自帶 `fetched_at`；(2) 序列沒有 → `chain_started_at`（`CHAIN_ATTR["fetched_at_from"]="orchestrator"`，命中快取時是原本那一次）；(3) 預存檔 → `cache_updated_at`（讀檔當下的 `fetched_at` 被丟棄）。累積表點取各自 `recorded_at`（閘門關閉時 0 列） | `exp`：tooltip 保留；`hld`／`alo`：**丟棄**（`hld` 只算日數、`alo` 明寫「取資料列本身的 `nav_date`，不用 `fetched_at`」） | 保留（exp）／丟棄（hld、alo）。實驗 E2、E4 |
| freshness | 預存檔品質 `nav_quality["stale"]` | 側車 `stale`、`cache_fallback`、`latest_from`（`live`／`cache_nav`／`nav_history`）；**nav 列無新鮮度欄** | 消費端各自以 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`（10 日曆日，`>10` 才算資料未備）判定；`hld` 另用 `cache_fallback`＋`latest_from` 判「取數失敗後退回預存」 | 保留（側車）。10 日規則 `DEC-2026-11-05-03` 不得升格 |
| coverage | 失敗瀑布逐來源原文 | `fetched`／`skipped_rows`／`skipped`；核帳恆等式 `len(rows)+skipped_rows==fetched`；`withheld` | `hld`／`alo`／`exp` 讀 `withheld`（四碼→「⬜ 資料未備」）與 `errors`；真實持倉覆蓋率＝BL-0545 NV | 保留；真實覆蓋率 NV |
| missing_reason（值域） | 自由文字（各來源原文） | **封閉碼** `withheld`：`ccy_missing`、`ccy_conflict`、`fetched_at_missing`、`fetched_at_in_future`、`input_conflict`；`errors[code]` 自由文字（含 `EMPTY_WITHOUT_REASON`）；`skipped[code]` 文字行 | `hld`／`alo` 允許清單 4 碼（不含 `input_conflict`，遇到即 raise）；`exp` 的 `withheld_texts` 為封閉集合，未登記碼 raise | 保留。無任何補 0／中性／ffill（§3.3-E） |
| estimated／actual | 無 | `is_estimated` **恆 False**（`_rows_from_segment` 寫死）；`source_tier` 恆「淨值」；舊資料只靠側車 `cache_fallback`／`stale` | `hld` HLD-6 有「推估」徽章，但 live 永不為真；`alo` 以 `is_estimated is not False` 當不新鮮 | 無（欄位在、無產生器）。Δ3-06 |
| consumer（ui_v3） | — | — | `ui_v3` 對 `nav_dividend`／`build_nav_table`／`resolve_full_keys` 無 import | 無 |

#### 3.1-B 持倉鏈

鏈名：Active Sheet（使用者 Google 帳號）→ `services/v2_tables/alo_holdings.py` → `ui_v2/{hld,alo}`。

| 層 | producer（檔::符號） | 輸出欄位／側車 |
|---|---|---|
| L1 | `repositories/personal_policy_reader.py::load_workbook_tables`（快取鍵含 `account_sub`＋`sheet_id`，`CACHE_TTL_SEC=60`）；目標來自 `services/v2_tables/personal_session.py::access_target`（無 fallback） | 保單分頁列＋補充分頁（`_持倉補充`、`_保單資料`） |
| L2 | `alo_holdings.py::load_alo_tables_active` → `build_alo_tables` | `holding` 11 欄、`policy` 8 欄；側車 `skipped`／`skipped_tabs`／`bad_rows`／`blank_rows`／`tab_missing`／`direct`／`warnings`／`read_estimate`／`actor` |
| 消費端 | `ui_v2/hld/source.py::load_live`、`ui_v2/alo/source.py` | `hld` HLD 全塊；`alo` ALO-2／3／4／6 |

| 維度 | 該層狀態 | 消費端是否保留 | 狀態 ＋ 證據 |
|---|---|---|---|
| source／provider | 使用者 Active Sheet（OAuth session）；`actor="oauth"`；`holding` 列**無來源欄** | `actor` 進 notes，不渲染 | 丟棄（列層）；`actor` 傳遞不渲染 |
| canonical identity | `holding_id`＝`<保單編號>\|<基金代號>\|<n>`；業務鍵（`policy_id`,`fund_code`）；`fund_code` 只去前後空白；鍵含 `\|` 不寫；撞號 raise；DIRECT 持倉**不產生 `holding` 列**（總管暫定，非客戶裁示）。`full_key` 不在列內，由 `hld`／`alo` source 另呼叫 `resolve_full_keys`，**只留 `ok is True` 的檔** | 保留 | 保留；`ok=False` 的檔被濾掉後畫面如何揭露＝NV（#1227 G3） |
| NAV | 無（持倉成本基準不用 NAV） | — | 無 |
| ccy／FX 方向 | `ccy`＝Sheet「幣別」欄 trim 後原字串，契約只做三碼大寫形狀檢查（`contract._is_iso_4217`），非 ISO 形狀整列不寫；`cost_twd`＝使用者填「淨投資金額」（新臺幣，正整數）；`cost_orig_ccy`＝`持有單位數 × 平均買入單位成本`（原幣）；**列內不含任何匯率** | 保留 | 保留。原幣↔TWD 的隱含匯率不存在、不計算 |
| as-of date | `last_synced_at`＝「最後核對日」`YYYY-MM-DD` 換成當日 12:00 台灣時間（`T04:00:00Z`），**推定時刻**；`opened_on` 取補充分頁 | `hld` 經 `sync_date()` 只顯示台灣**日期**（推定的 12:00 被降為日期）；不合格值 ⛔ | 保留（日期）；時刻為推定（#1225 §1.5 已指） |
| fetched_at | **無**（列無讀取時間欄；`read_estimate` 為 L1 讀取量診斷，非時間） | — | 無 |
| freshness | 無獨立欄；`hld` 顯示核對日；無門檻 | — | 無 |
| coverage | `skipped`（逐列原因）、`bad_rows`、`blank_rows`、`tab_missing`、`skipped_tabs`、`direct`；真實覆蓋率＝BL-0545 NV | `hld` 轉成「未列入」行；`alo` 把 `skipped_holdings` 記成 `_omitted_rows` **只記不改格**（實驗 E8） | 保留；`alo` 的格值不受影響 |
| missing_reason（值域） | `skipped[].reasons` 自由文字（例：缺持倉補充、基金名稱空白、幣別空白、淨投資金額空白／為 0／無法解析、鍵含 `\|`、純數字代號可能已被轉數字）；固定字樣 `DIRECT_WARNING`；L1 讀取失敗用 9 個 `error_code`（`shared/ui_v2_error_codes.py`） | 保留 | 保留。無補預設值 |
| estimated／actual | `last_synced_at` 推定；`cost_orig_ccy` 由單位數×均價**算出**；兩者**列內無旗標**（只在 docstring／ACCEPTANCE 8.1） | 丟棄（無旗標可傳） | 無（旗標）；事實有文件記載 |
| consumer（ui_v3） | `ui_v3/adapters/assets_source.py::load` 只取**成本基準**，市值基準一律 `blocked`（`market_basis_assembly_not_available_in_preview`），**無任何頁面 import 它** | — | 無 UI 消費端 |

#### 3.1-C 配置鏈

鏈名：`holding`＋`nav`＋`market_indicator`（FX）＋`user_setting` → `services/v2_domain/holdings.py`（`aggregate_holding_rows`、`basis_value_with_reason`、`category_values`、`fx_row_as_of`）→ `ui_v2/alo/logic.py::_build_alo2`（及 ALO-0／3／4／6）；並行的證據支線：`services/v2_domain/allocation_evidence.py::build_allocation_evidence` → `ui_v3/adapters/assets_source.py`。

| 維度 | 狀態 | 消費端是否保留 | 狀態 ＋ 證據 |
|---|---|---|---|
| source／provider | 目標／容許帶／基準／類別名稱來自設定試算表 `user_setting`；USD 匯率來自設定試算表已存的 `market_indicator` 列；非美元匯率由 `alo/source.py` 經 `market_indicator.build_fx_indicator_table`（Yahoo `<ISO>TWD=X`）；`market_indicator.source_tier`＝「市場指標」 | `alo` 明寫塊上無 `source_tier`／`fetched_at`，不掛來源徽章 | 丟棄（ALO-GAP-來源徽章） |
| canonical identity | 類別＝`holding.bucket`（空值／不在 `alo_bucket_names` → 「未分類」）；同鍵（`policy_id`,`fund_code`）多列加總，`bucket` 或 `ccy` 不同 → raise | 保留 | 保留 |
| NAV | 市值基準：`latest_nav_row` × `units_shares`；淨值日距今 `>10` → 該檔視為缺（`REASON_NAV_STALE`），過期或 `cache_fallback`／`stale`／`is_estimated is not False` 的檔在 `assemble_nav` 就被拿掉 | 保留 | 保留 |
| ccy／FX 方向 | 鍵 `fx_twd_per_<小寫ISO>`＝**新臺幣／該幣（TWD per 1 單位外幣）**，Yahoo `USDTWD=X` 同向；`value_twd = nav × units × rate`；`nav.ccy=="TWD"` 不乘；對齊規則＝`obs_date` 不晚於 `nav_date` 的最近一筆；閘門 `FX_OBS_DATE_RULE_VERIFIED=False` ⇒ 非美元鍵 `pending`、不取數，該類別「⬜ 資料未備：缺換算匯率 <鍵>」。**消費端不讀 `value_unit`，也無匯率新鮮度上限**（Δ3-03）。Old UI 的 `get_latest_fx`／`get_fx_rate_by_date` 在 `ui_v2`／`ui_v3`／`services/v2_*` 無呼叫（僅一行註解命中，見 §3.6 G-2），兩條 FX 路徑不相交 | 保留（缺 FX → 該類別缺值） | 保留；方向於寫入端固定、於消費端**未驗**（E5） |
| as-of date | 以 `nav_date` 為 FX 對齊鍵；`allocation_evidence` 根層**無 `as_of`**（#1225 §1.5） | `alo` 無配置層級 as-of | 無（配置層級） |
| fetched_at | 配置結果無 `fetched_at`；FX 列有 `fetched_at` 但消費端不讀 | 丟棄 | 丟棄 |
| freshness | NAV 10 日門檻（見 3.1-A）；FX **無** | — | NAV 保留／FX 無 |
| coverage | ALO-2：`uncovered`→表尾「合計未涵蓋 …」；證據支線：`source_coverage`／`denominator.verdict`／`valuation_completeness`／`chart_comparability`／`category.value_origin`（含 `unproven_zero`） | `alo`：表尾一行；**百分比與內外判定不隨覆蓋度改變**（Δ3-04、Δ3-05）；`ui_v3/assets_source`：`chart_claim` 恆 `withheld_pending_approval` | 部分保留 |
| missing_reason（值域） | `services/v2_domain/holdings.py`：`REASON_NAV_ABSENT`／`REASON_NAV_STALE`／`REASON_NAV_STALE_UNDATED`／`REASON_FX_ABSENT`＋`KIND_NAV`／`KIND_FX`；`alo/logic.py::_missing_text` 把代碼換回中文句，未知代碼 raise | 保留 | 保留。缺值是 `None` 不是 0.0（核心註明） |
| estimated／actual | 無旗標；證據支線有 `value_reliable`、`value_origin` | `alo` 不使用 | 無（ui_v2）／保留（evidence，無 UI） |
| consumer（ui_v3） | `assets_source.py` 無頁面；`ACTION_SLOT_SOURCES_ENABLED=False` | — | 無 |

---

### 3.2 三種 `source` 語意嚴格分離

**不得合併**：`provenance.source`（供應者）、`source_tier`（表類別）、績效 `source`（計算口徑）是三個不同概念。另有三個鄰近名詞也不得混入（`ccy_source`、`chain.data_source`、`CLAUDE.md` §2.1 的 `T1`～`T5` 權威分級）。

| 項目 | 定義 | 產出處 | 值域／例 | 消費處 | 容易被混用的位置 |
|---|---|---|---|---|---|
| **`provenance.source`**（供應者） | 這一檔這次序列是**誰給的** | L1 `series.attrs["source"]` → L2 `nav_dividend.py::_rows_from_segment`（`provenance[code]["source"]`）；配息側為逐筆 `source` | 自由字串，例 `Morningstar:UK:timeseries:<secId>`、`GitHubActions:cache/nav/<code>.json`；非原生來源以前綴 `Morningstar:`／`Yahoo:`／`AlphaVantage:` 辨識（`fund_orchestration._NAV_NON_NATIVE_PREFIXES`） | `exp`：`ui_v2/exp/live.py::nav_notes_and_rows`（`source_tag`）、`_nav_tip`；`nav_dividend` 以前綴判預存檔 | `nav` 列**沒有 `source` 欄**（44 §4.2），所以「來源」二字在列層只能指 `source_tier` |
| **`source_tier`**（表類別） | 這一列屬**哪一類表**，封閉四值 | `contract.SOURCE_TIER_VALUES`；`nav` 列由 `nav_dividend.py::SOURCE_TIER_NAV` 恆寫「淨值」；`market_indicator` 列「市場指標」；`fetch_log` 也用此欄 | `淨值`／`配息`／`市場指標`／`其他` | `hld` HLD-6：`ui_v2/hld/logic.py::_build_hld6` 以 `source_badge(row["source_tier"])` 掛「來源」徽章；`ui_v2/plain.py` 欄標「來源層級」 | **UI 上的徽章 `_kind="來源"`、字面是「淨值」**（44 §5.2「來源徽章」）——讀者易把它當供應者。屬 44 frozen 命名，不是程式錯 |
| **績效 `source`**（計算口徑） | 1Y 含息數字是**怎麼算的** | `services/fund_total_return.py::resolve_1y_total_return` 回傳鍵 `source`：`自算（還原含息淨值）`（ok）或 `—`（無值） | 兩個字串（另有相容保留的退役標籤）；官方值只在 `perf_source=="wb01"` 時進 `official_1y_pct` 對帳 | Old UI 與 AI prompt；**New UI 路徑 0 命中** | 與 `provenance.source` 同名不同義；一旦接進 New UI 契約，欄名須區分（D2 `R-PERF-4`，Pending，#1227 §4.4.1） |
| `provenance.ccy_source`（鄰近） | 幣別**標籤**是誰說的 | L2 `resolve_nav_ccy`：`holding_user_input`／`source_reported`／`meta:<來源+來源>` | 封閉前綴（`_RESERVED_CCY_SOURCES`） | 三端皆不渲染 | 與供應者無關，不得當 provider |
| `provenance.chain.data_source`（鄰近） | A 鏈最後採用的來源名 | `_add_chain_provenance` | 自由字串 | 無消費端渲染 | 與 `provenance.source` 通常相近、但來自 `res["data_source"]` 而非序列 attrs |
| `CLAUDE.md` §2.1 `T1`～`T5`（鄰近） | 來源**權威分級** | 憲法文件 | `T1`～`T5` | 無程式使用 | 與 `source_tier` 都叫「Tier」；`ui_v2/hld/fixtures.py` 已更正舊寫的 `"T1"`，但 `ui_v2/mkt/fixtures.py` 示範資料仍以 `source_tier="T1"` 預設（`ui_v2/mkt/live.py` 註解自陳「T1／T2 只出現在示範資料」） |

**實際混用檢查（讀過範圍內）**：
- `nav`／`holding`／配置鏈與 `ui_v2/{hld,alo,exp}`、`ui_v3/adapters`、`services/v2_tables`、`services/v2_domain`、`shared/ui_semantics`：**未見把三者互換使用**（`source_tier` 只用於值域檢查與徽章；`provenance.source` 只在 `exp` 當標籤與 tooltip；績效 `source` 在這些目錄 0 命中）。指令見 §3.6 G-3。
- 邊界外兩處（**不在本鏈**，僅登記）：(a) `ui_v2/mkt/fixtures.py` 示範資料 `source_tier="T1"` 與正式值域不符（嚴重度：低，示範專用，`mkt/live.py` 已註明）；(b) Old UI 裡 `source` 一詞兼指供應者與計算口徑（例 `services/health/dividend.py` 的 `meta["source"]="mk_strict"`、`dividend_calc.py` 的 `"records"／"estimate"`、`ui/tab2_single_fund.py` 讀 `_t.get("source")`）——**Old UI 未逐檔讀**，只做字面 grep，不下結論。

---

### 3.3 契約 delta（相對 #1225 §1、#1227 的最小差異）

嚴重度（本組判斷，可被推翻）：**高**＝可能讓使用者看到錯誤數字且無旗標；**中**＝證據／來源／覆蓋度被丟棄或不可驗；**低**＝文件或命名。

| ID | 類型 | old → new | 嚴重度 | 證據 |
|---|---|---|---|---|
| Δ3-01 | 新發現 | （無前述）→ `test_alo_core_golden.py` 在 Python 3.13 有 3 個失敗，**根因是 CPython ≥3.12 的 `sum()` 補償加總**，不是程式或黃金檔錯 | 中（驗收訊號依賴 Python 版本） | 見下 §3.3-F |
| Δ3-02 | 新發現 | #1227 §2.3／G6 只談 `exp` 的選股池命名空間 → B 線**接受** `secid_origin="pool_isin_search"` 的晨星序列；來源不進 `provenance`；無測試釘住 | 中 | 見下 §3.3-D |
| Δ3-03 | 新發現 | #1225 §1.6 只寫「FX 閘門關」→ 消費端 `fx_row_as_of` 無匯率新鮮度上限、不讀 `value_unit`（實測） | 中（閘門關閉時不可達） | 實驗 E5；`ui_v2/alo/logic.py` 的 ALO-GAP 表 |
| Δ3-04 | 補強 | #1225 §2.4「已登記落差，不寫缺陷」→ 仍成立；**補**同輸入對照與數值（現金 100.0%／+90.0 pp／外 vs evidence `incomplete`／`not_comparable`） | 中（已登記） | 見下 §3.3-B |
| Δ3-05 | 補強 | #1225 §2.5「預設 `{"value": 0.0}`，真 0 或缺值需看資料完整性」→ 實測：有持倉被略過時目標類別仍印 `0.0%` 並判「外」 | 中 | 實驗 E8；`allocation_evidence` 有 `unproven_zero` 而 ALO-2 沒有 |
| Δ3-06 | 補強 | #1227 N-6「`is_estimated` 恆 False」→ **後果**：`hld` HLD-6「推估」徽章 live 不可達；`alo` 的 `is_estimated is not False` 守門在 live 永不觸發 | 低 | `nav_dividend.py::_rows_from_segment`；`ui_v2/hld/logic.py::_build_hld6` |
| Δ3-07 | 補強 | #1225 §1.4「來源放在 provenance 側車」→ 補**逐欄保留／丟棄**（§3.1-A）：`ccy_source`、`chain`、`nav_history`、`mapping_source`、`secid_origin`、`currency_id_origin` 無任何 UI 消費者 | 低～中 | 實驗 E1／E3／E6；grep G-4 |
| Δ3-08 | 更正（文件） | `tests/test_nav_currency_swap_guard.py` 檔頭 docstring 寫「候選不宣告幣別（如 cnyes）時仍會換源—刻意的權衡」→ 2026-10-10 客戶 Q3 後測試已反轉為「擋下」；**檔頭過期，測試本身正確** | 低 | `test_span_extend_blocks_when_candidate_currency_unknown`、`test_backfill_blocks_when_candidate_currency_unknown` 內註明反轉 |
| Δ3-09 | 仍成立 | #1227 R-ID-1 G1／G2：Sheet 欄遇網址或帶後綴 → `ok=True` 且無違反標記 | — | 實驗 E6（小寫後綴碼、網址皆 `ok=True`） |
| Δ3-10 | 仍成立 | #1227 §4.4：`calc_metrics` 1Y 估算路徑在 New UI 0 消費 | — | 見 §3.3-C |
| Δ3-11 | 仍成立 | #1225 §1.8：New UI 路徑無 `fillna`／`ffill`／`bfill`／`interpolate`；`ui_v2`／`ui_v3` Missing≠0 | — | grep G-1（本批擴大範圍重跑，結果同） |

#### 3.3-A NAV 換幣守衛：`test_nav_currency_swap_guard.py` 鎖什麼、沒鎖什麼

**鎖住（30 個測試，3.13 全綠）**：
1. L0 判定器 `shared/data_quality.py::{normalize_iso_ccy,nav_series_currency,nav_currency_verdict,assess_nav_series_swap}`：只有雙方皆可辨識 ISO 三碼才說 match／mismatch，其餘 unknown；只放行 match；輸出沒有「換算」出口。
2. L1 `fund_orchestration.py::_span_extend_insurance_nav`（長歷史整條替換）與晨星／Yahoo 序列**要宣告自己的幣別**。
3. L2 `services/nav_history_store.py::backfill_to_gs`／`_rescue_by_isin`（每日 cron 寫 `nav_history` 的採用點）：幣別不一致或未知 → 拒絕換源、不換算。

**沒鎖（由別的測試／別層負責，或無人負責）**：

| 不在本檔範圍 | 實際負責者／現況 |
|---|---|
| B 線 `nav_dividend._chain_ccy_gate`／`resolve_nav_ccy`（序列宣告 vs 持倉手填） | `tests/test_v2_tables_nav_dividend.py`、`tests/test_v2_tables_nav_chain_handover.py`（例：`test_B1例二_FundClear序列宣告USD_持倉填TWD_整檔不寫`、`test_非原生來源沒宣告幣別_整檔不寫`） |
| **原生來源（MoneyDJ 等）序列未自報幣別** | 守衛放行；`nav.ccy` 只憑持倉手填，`ccy_source="holding_user_input"`，**無獨立驗證**（實驗 E1／E1b）。L1 守衛看不到 Sheet 上的幣別（`repositories/fund/fx_and_main.py::_latest_nav_expected_ccy` 註明「L1 讀不到客戶 Sheet 上的幣別…偵測不到」）。#1227 N-1 已指 |
| `get_latest_nav` 的單點守衛、跨來源 NAV 回驗 | `tests/test_unknown_currency_fail_closed_20261010.py`（196 個，3.13 全綠）；非本檔 |
| 檔頭 docstring 與現行行為 | 過期（Δ3-08） |

**結論**：此守衛保護的是**歷史長序列寫入 `nav_history` 的路徑**；B 線 `nav` 表的幣別正確性由 L2 閘（`_chain_ccy_gate`）＋持倉手填負責，兩者互補但**都不證明「數字真的是該幣別」**。

#### 3.3-B 缺 FX 時的資產配置分母（`_build_alo2` vs BL-0542 G-1／`DEC-2026-11-04-02` 方案 A）

**已知（引用）**：#1225 §2.4、`BACKLOG.md` BL-0542 G-1 補註、`DEC-2026-11-04-02`「技術與資料現況」：方案 A 是 **New UI2 呈現**要求，`ui_v2` 為 maintenance-only，舊分母行為「本批不修」。

**補的實測（純函式，`ui_v2.alo.fixtures.scenario_with("nofx")`，市值基準、核心與衛星各含一檔 USD、現金只有 TWD）**：

| 路徑 | 結果 |
|---|---|
| `ui_v2.alo.logic.build_page_model` → ALO-2 | 核心、衛星：「⬜ 資料未備：缺換算匯率 fx_twd_per_usd」；**現金：`100.0%`、差額 `+90.0 pp`、內外 `外`**；表尾「合計未涵蓋 核心（示意）、衛星（示意）」；`_tone`＝灰 |
| `services.v2_domain.allocation_evidence.build_allocation_evidence`（同表、`fx_rule_verified=False`） | `denominator.verdict=incomplete`（`valued_holding_count=2`、`counted_holding_count=1`、`covered_category_count=1`／`excluded_category_count=2`）、`valuation_completeness=incomplete`、`chart_comparability=not_comparable`、`open_gates=['fx_obs_date_rule_unverified']` |

**測試釘住的是舊行為**：`tests/ui_v2/test_alo_logic.py::test_ALO2判準_市值基準而沒有任何匯率_含外幣的類別資料未備_不以1硬算` 斷言 `rows[CASH]["current_text"]=="100.0%"`；`::test_ALO2部分類別缺基準值_有值的類別照判內外_缺值的類別寫資料未備_不整張不判` 斷言有值類別**照判內外**（其 docstring 引「客戶 2026-10-16 裁示 ALO-GAP-部分缺的內外判讀，已裁結案」）；`tests/test_alo_core_golden.py` 的檔頭自陳黃金檔「凍結現況，含已知差異…顯示 100.0%」。
**兩個客戶裁示的射程是否衝突，本組不判**：2026-10-16（`ui_v2` 部分缺仍判內外）與 2026-11-04 方案 A（New UI2 不得畫完整 100%）射程標的不同（Preview vs New UI2）。**待客戶／總管確認**；任何程式變更屬 BL-0542 G-1 formula／data semantics Gate，本批不動。

#### 3.3-C `calc_metrics` 1Y estimated window 在此鏈的位置（引用 #1227，不重做）

- 位置：A 鏈每次 `auto_fetch_moneydj` 經 `services.fund_service.fetch_fund_from_moneydj_url_enriched`→`finalize_fund_metrics`→`calc_metrics`，**同一次呼叫算出 `metrics`**（`ret_1y_total`、`ret_1y_window_days` 等，含 #1227 的估算／預設窗口路徑 P2／P3／P5）。
- **L2 邊界丟棄**：`nav_dividend.py::_nav_from_chain` 只讀 `series`／`full_key`／`data_source`／`chain_started_at`／失敗原文與累積表標記；`metrics` **不進** `nav` 列、不進 `provenance`。
- 因此 1Y 估算窗口路徑**不會**經此鏈到達 `hld`／`alo`／`exp`（對 `calc_metrics`／`ret_1y_total`／`resolve_1y_total_return` 於 `ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain` 0 命中，與 #1227 §0-4 一致）。可達性結論（日頻索引不可達、窗口無上界）引用 #1227 驗證檔，本批不重跑。
- 附帶：B 線 build 在 `NAV_HISTORY_PROVENANCE_VERIFIED=False` 時以 `nav_history_shared_reads(skip_reads=True)` 包住迴圈，A 鏈不讀累積表；故 B 線觸發的 `calc_metrics` 輸入序列**不含累積點**（`tests/test_v2_tables_nav_chain_handover.py::test_B4_*`）。

#### 3.3-D ISIN 未啟用與 `full_key` 後綴在此鏈的流向

| 項 | 流向（實測／讀碼） | 與 Gate 的關係 |
|---|---|---|
| Sheet 欄是網址或帶後綴碼 | `resolve_full_keys` 判 `ok=True`，`full_key` 保留後綴（E6：`acdd01-eqtal005`→`ACDD01-EQTAL005`；網址 `?a=ACDD01-EQTAL005`→同）；**無違反標記**；`nav` 列的 `fund_code` 保留原輸入（含小寫）；同代碼不同大小寫成不同列鍵、同一 `full_key`（#1227 G4） | D2-A＝B 標示尚未實作（`DEC-2026-11-09-01`）；S7 後綴規則未裁（`R-ID-2` Pending） |
| DG2 shadow | `fund_keys.py` 僅 `if DG2_SHADOW_ENABLED:` hook，常數 `False`；三個 UI 消費端不讀 shadow 結果 | `DEC-2026-10-28-05`；本批不解除 |
| ISIN 作為輸入／查詢鍵 | 三條鏈的輸入是 `fund_code`；`ui_v2/{hld,alo,exp}`、`services/v2_tables` 對 ISIN 無讀取（`exp_universe.py` 明寫不讀選股池 `isin`） | BL-0530 research-only；`DEC-2026-11-01-02` |
| **A 鏈內部的 ISIN→晨星 secId（新）** | `repositories/fund/sources.py::_src_morningstar_nav` 以 `pool_repository.resolve_isin(code)`（選股池**手填** ISIN）查晨星 secId，標 `secid_origin="pool_isin_search"`；`_nav_from_chain` 只拒 `name_search`／`code_search`，**其餘（含 `pool_isin_search`）照收**（實驗 E3：五種 origin 中 `pool_isin_search`／`pool`／`hardcoded_map` ACCEPT、兩種搜尋 REJECT）；`secid_origin` 與 `currency_id_origin` **不進 `provenance`**；測試只覆蓋 `pool`／`hardcoded_map` 照收（`test_B2_晨星secId來自池表或寫死表_照收…`）與搜尋拒收，**`pool_isin_search` 無測試** | **本組不宣稱違規**：此路徑是 A 鏈既有（v19.491）、B 線 2026-10-13 起復用；但 `DEC-2026-11-01-02`／BL-0530 明寫「不得使用選股池手填 `isin` 欄作正式 identity authority」。**是否構成越界需客戶／總管判斷**（identity 規則屬 Stop Gate）。本批不改 |

#### 3.3-E Missing／Partial／UNAVAILABLE／未評估 分流

| 概念 | 在此鏈的承載 | 是否補 0／中性／ffill |
|---|---|---|
| 取不到值（單筆） | 該列不寫（`nav_row_problems`）；同日有無效值該日全不寫 | 否 |
| 整檔扣下（Partial／UNAVAILABLE） | `withheld[code]` 封閉碼＋`skipped` 文字；畫面「⬜ 資料未備」（`hld`／`alo` 4 碼） | 否 |
| 取數失敗 | `errors[code]` 原文（遮蔽後）；畫面 ⛔ | 否 |
| 資料過舊 | `NAV_NOT_READY_DAYS`：`hld` 該檔淨值列不交給 `logic`（走 `nav_missing`）；`alo` 不交進 dataset；皆「⬜ 資料未備」，**不用舊淨值算任何數** | 否 |
| 未評估 | `ui_v3/adapters/assets_source.py`：市值基準 `blocked`；`allocation_evidence` 的 `not_evaluated`／`nav_state=not_assembled`；`shared/ui_semantics/rules.py` 有 `undetermined`／`not_configured`／`user_param_unset`，但 `ui_v2` 的 `hld`／`alo`／`exp` **不 import 它**（用自己的 `page_health`／`symbols`／`status_class`，此為 BL-0540 G-2／G-3 範圍） | 否 |
| 目標類別無持倉 | `_build_alo2` 預設 `{"value": 0.0}`（真 0）；證據支線區分 `real_zero_by_rule` 與 `unproven_zero` | **有風險**：覆蓋不完整時 ALO-2 仍印 `0.0%`（Δ3-05）；加註：model 層 ALO-0／ALO-6 另行揭露略過列，見 §3.6 盲點 3，嚴重度由後續 QA 判 |

**搜尋結果**：`services/v2_tables`、`services/v2_domain`、`ui_v2/{hld,alo,exp}`、`ui_v3`、`shared/ui_semantics`、`shared/active_sheet.py`、`repositories/fund` 對 `fillna|ffill|bfill|interpolate|fill_value|reindex(` **0 命中**；`or 0`／`.get(…,0)` 命中皆為計數器累加（見 G-1）。

#### 3.3-F Python 3.13 黃金檔失敗事實（只報事實，不重錄）

- 失敗：`tests/test_alo_core_golden.py::test_整份矩陣_工作樹與黃金檔逐位元組相同`、`::test_逐情境相同[alo2_family-cost:near_tied_leaders_within_1e9]`、`tests/test_alo_core_golden_mutations.py::test_對照組_未突變的載入器重現黃金檔`。
- 現象：**僅一個情境**（`cost:near_tied_leaders_within_1e9`）、**僅 1 ulp**：`_current_pct` `55.000000003000004`（黃金）vs `55.000000003`（3.13），`_diff` `5.000000003000004` vs `5.000000002999997`，ALO-6 `_in_total` 同型。其餘 `basis_value` 67／`category_values` 38／`alo2_family` 106 個情境與黃金一致。
- 根因（已用 CPython 3.11.18 驗證）：`ui_v2/alo/logic.py::_build_alo2` 的 `denominator = sum(...)`。`sum([5500.0000003, 2499.9999998, 1999.9999999])`：3.13 回 `10000.0`（補償加總，CPython 3.12 起），3.11.18 回 `9999.999999999998`（逐項相加）。黃金檔檔頭記錄錄製版本 `python=3.11.18`。
- 驗證：同一份矩陣執行器（`tests/_alo_core_golden.py::run_matrix`，不依賴 pandas／pytest）在系統 `/usr/bin/python3.11`（3.11.18）上**與黃金檔 0 差異**；在 3.13 上 1 個情境有差異。**未**在 3.11 下跑 pytest 本身（該直譯器無 pytest／pandas），第三個失敗（對照組）以同一載入器推定為同因，**未獨立驗證**。
- 含意：(1) 黃金檔實際綁定 Python minor；CI 釘 3.11，所以 CI 不受影響（另有作者核對 CI 是否實跑，本節不重複）；(2) `requirements.txt` 註解稱 Streamlit Cloud 已遷 Python 3.14（實際版本 NOT VERIFIED），若屬實，正式環境的 `denominator` 與 CI 在 1 ulp 層級可能不同；畫面只印 1 位小數，除非恰在容許帶邊界（`exceeds` 已用 `isclose(abs_tol=1e-9)`），**預期不可見**；(3) **不得重錄黃金檔**（黃金檔檔頭與 sha256 釘死已明文禁止）。處置（釘 3.11、改用 `math.fsum`、或放寬比對）屬測試／公式決定，本批不提議。

---

### 3.4 可執行斷言對照（本批實跑）

**環境**：Python 3.13.18；`pytest -p no:cacheprovider -q`；副本為 `git archive HEAD`＋`git init`；未使用 `--noconftest`（依賴齊全）。**與 CI（Python 3.11）不同**。

| 批 | 指令（範圍） | 結果 |
|---|---|---|
| R1 | `tests/test_v2_tables_*.py`（20 檔，收集 1255 項）＋`tests/test_fund_identity_dg2.py`＋`tests/test_nav_dividend_golden_c3a.py` | **1436 passed** |
| R2 | `tests/test_unknown_currency_fail_closed_20261010.py`＋`tests/test_nav_currency_swap_guard.py`＋`tests/test_v2_domain_alo_core.py` | **285 passed, 2 skipped** |
| R3 | `tests/test_alo_core_golden.py`＋`tests/test_alo_core_golden_mutations.py` | **274 passed, 1 skipped, 3 failed**（見 §3.3-F） |
| R3b | 6 檔合跑：`test_nav_currency_swap_guard.py`、`test_alo_core_golden.py`、`test_alo_core_golden_mutations.py`、`test_nav_table_golden_c3a.py`、`test_nav_dividend_golden_c3a.py`、`test_v2_domain_alo_core.py` | 3 failed／456 passed／3 skipped（失敗同 R3；C3a 兩黃金檔通過） |
| R4 | `tests/ui_v2/test_{alo_logic,alo_live_logic,alo_source,hld_live_assemble,hld_live_freshness,hld_live_logic,hld_source,exp_live_logic,exp_live_wiring_logic,exp_source}.py`＋`tests/ui_v3/test_ui_v3_assets_source_*.py`（4 檔）＋`tests/ui_v3/test_ui_v3_semantics_rules.py` | **1963 passed, 2 skipped**（skip：`test_hld_live_logic.py` 空持倉無字尾，檔內註明） |
| R5 | `tests/test_v2_domain_allocation_evidence.py`＋`tests/test_allocation_evidence_mutations.py` | **203 passed, 3 skipped** |
| 實驗 | 一次性純函式實驗腳本與輸出（未入庫；不連網），重現方式見附錄 A | E1～E8，見 §3.6 |

| 契約宣稱 | 既有測試（檔::測試名） | 本批結果 | 缺口 |
|---|---|---|---|
| `nav` 7 欄、型別、可空與 44 §4.2 逐欄相同；無 TWD 欄 | `test_v2_tables_nav_dividend.py::test_契約_nav與44逐欄相同_source_tier值域相同` | 過（R1） | 有效 |
| 取不到值不補 0／不 ffill／不補列 | 同檔 `::test_nav_部分NaN_只略過那幾筆_不ffill`、`::test_nav_週末與假日沒有列_不補列`、`::test_nav_零與負淨值不寫`、`::test_nav_全NaN_一列都不寫_理由寫明` | 過 | 有效 |
| 同日同值併一列、不同值全不寫；數值不四捨五入 | `::test_nav_同一日期同值只寫一列_不同值該日全不寫`、`::test_數值_淨值保留原精度不四捨五入` | 過 | 有效 |
| 幣別缺／衝突／不合 ISO → 整檔不寫、不預設 USD | `::test_nav_幣別缺_整批不寫_不猜不預設USD`、`::test_nav_來源自報與持倉不同_不猜_整批不寫`、`::test_nav_持倉幣別不合ISO4217_不改大小寫_整批不寫` | 過 | 有效（但只證明「不矛盾」，不證明「真是該幣別」） |
| A 鏈幣別不當標籤；非原生來源未宣告 → 整檔不寫 | `test_v2_tables_nav_chain_handover.py::test_非原生來源沒宣告幣別_整檔不寫`、`::test_B1例二_FundClear序列宣告USD_持倉填TWD_整檔不寫`、`::test_B1例三_累積表點宣告USD_持倉填TWD_整檔不寫_閘門開啟` | 過 | 有效 |
| `fetched_at` 不以當下時間補；預存檔取 `cache_updated_at`；缺則整批不寫 | `test_v2_tables_nav_dividend.py::test_nav_fetched_at取不到或沒有時區_整批不寫_不以當下時間補`、`::test_nav_預存舊序列_fetched_at改取cache_updated_at_stale照記`、`::test_nav_預存舊序列沒有cache_updated_at_整批不寫`；`test_v2_tables_nav_chain_handover.py`：`::test_N1_序列沒帶fetched_at_用快取內原本那次的chain_started_at_不是當下`、`::test_N3_預存檔那一支_fetched_at_from標cache_updated_at` | 過 | 有效 |
| 累積表閘門關閉：累積點不寫、不讀表 | `test_v2_tables_nav_chain_handover.py::test_閘門預設關閉`、`::test_閘門關閉_累積點一律不寫_重疊日是即時值照寫`、`::test_B4_閘門關閉_只有第二頁型有即時資料加累積點_寫出25列_latest_live_不讀表` | 過 | 有效 |
| 名稱／代碼搜尋得來的晨星 secId 拒收；池表／寫死表照收 | `::test_B2_晨星secId由名稱搜尋得來_B線整檔不寫_A鏈照舊採用`、`::test_M11_code_search_也拒收`、`::test_B2_晨星secId來自池表或寫死表_照收_並標出currencyId出處`（參數僅 `pool`／`hardcoded_map`） | 過 | **`pool_isin_search` 尚無有效測試**：缺「收或拒」的斷言（只描述，不寫碼） |
| A 鏈 `full_key` 必須等於代碼對照的 `full_key` | `::test_A鏈回的full_key與fund_keys不同_照實標缺_原因讀得懂`、`::test_nav_同一檔給了不同full_key_不取數不寫` | 過 | 有效 |
| 後綴碼／網址 → `ok=True` 且保留後綴（現況行為） | `test_v2_tables_fund_keys.py::test_mapping_miss_passes_through`、`::test_url_extracts_code`、`::test_fallback_is_error`、`::test_non_ascii_is_error` | 過 | 這是**特徵化**，不是 D2-A＝B 驗收；「違反標示」**尚無測試**（production 無此行為） |
| 換源幣別守衛（L0／L1／L2） | `test_nav_currency_swap_guard.py`（30）、`test_unknown_currency_fail_closed_20261010.py`（196） | 過 | 見 §3.3-A；Δ3-08 檔頭過期 |
| 持倉：淨投資金額空白不補 0、鍵含 `\|` 不寫、撞號 raise、DIRECT 不產 `holding` | `test_v2_tables_alo_holdings.py`（129 項） | 過 | DIRECT 不產列是總管暫定 |
| 市值基準：淨值×單位數，美元再乘「不晚於淨值日的最近一筆」匯率；歐元不拿美元匯率 | `tests/ui_v2/test_alo_live_logic.py::test_市值基準_新臺幣與美元_照淨值乘單位數_美元再乘不晚於淨值日的最近一筆匯率`、`::test_市值基準_歐元不拿美元的匯率` | 過（R4） | **無匯率過舊上限、無 `value_unit`／方向斷言**（Δ3-03）：缺這兩個斷言 |
| 缺 FX → 該類別資料未備、不以 1 硬算 | `test_alo_logic.py::test_ALO2判準_市值基準而沒有任何匯率_含外幣的類別資料未備_不以1硬算` | 過 | 同時釘住「現金 100.0%」舊行為（§3.3-B） |
| ALO 核心搬遷逐位元組不變 | `test_alo_core_golden.py`（225）＋`test_alo_core_golden_mutations.py`（53） | **3 失敗（3.13）** | 僅 Python minor 差異（§3.3-F）；3.11 執行器 0 差異 |
| 證據支線：缺 FX／覆蓋不完整不宣稱 complete／comparable；`unproven_zero` | `test_v2_domain_allocation_evidence.py`（含 `check_target_zero_is_unproven_when_source_is_not_complete`）、`test_allocation_evidence_mutations.py` | 過（R5） | 有效，但 **`ui_v2` ALO-2 不使用它** |
| 市值基準不呼叫生產者、`chart_claim` 恆 withheld | `tests/ui_v3/test_ui_v3_assets_source_contract.py::test_real_module_passes[check_market_basis_is_blocked_without_calling_the_producer]`、`[check_chart_claim_is_always_withheld]` | 過（R4） | 有效；無頁面消費 |
| `hld` 淨值新鮮度：`>10` 才資料未備；不讀 `stale` | `tests/ui_v2/test_hld_live_freshness.py::test_邊界_0天_1天_10天_11天`、`::test_不讀stale_新舊只看N` | 過 | 有效 |
| ALO-2 在「有持倉被略過」時目標類別不印 `0.0%` | — | — | **尚無有效測試**（現行行為相反，E8）；缺的斷言：覆蓋不完整時無持倉目標類別不得以 0.0% 與內外判定呈現（只描述） |

---

### 3.5 Gate 對照（本批不解除任何一項）

| 此鏈上的未決點 | 對應 DEC／BL／編號 | 狀態（實測值） | 本批 |
|---|---|---|---|
| D2 正式核准欄位數 | `DEC-2026-11-11-04`（D2-G1／G2／G3）；#1227 為 `R-ID-1`／`R-NAV-1` 準備包（`DEC-2026-11-13-01`） | **0**；17 列 Pending | 不解除 |
| DG2 canonical identity | `DEC-2026-10-28-05`、`DEC-2026-10-29-01`～`-03`；`shared/fund_identity.py::DG2_SHADOW_ENABLED` | `False`（實測） | 不解除 |
| D2-A＝B 違反欄位契約標示 | `DEC-2026-11-09-01`（要點轉述） | 尚未實作（E6：無標記） | 不解除 |
| `full_key` 後綴／S7、ISIN | `R-ID-2`（Pending）；BL-0530、`DEC-2026-11-01-02` | ISIN 維持「尚未啟用」；A 鏈內 `pool_isin_search` 路徑待判（Δ3-02） | 不解除 |
| FX 觀測日規則 | `DEC-2026-11-08-02`；`market_indicator.FX_OBS_DATE_RULE_VERIFIED` | `False`（實測） | 不解除 |
| 缺 FX 分母／方案 A | `DEC-2026-11-04-02`；BL-0542 G-1 | `ui_v2` 仍印 100.0%（E7）；G-1 PORT／分母待獨立 Gate | 不解除 |
| BL-0542 G-2～G-5 | BL-0542（摘要四格、配息推估、狀態詞對映、Preview 守衛） | 待客戶裁示 | 不解除 |
| NAV 10 日規則 | `DEC-2026-11-05-03`；`ui_v2/thresholds.py::NAV_NOT_READY_DAYS` | 10（實測）；不得升格 | 不解除 |
| 累積 NAV 出處 | `nav_dividend.py::NAV_HISTORY_PROVENANCE_VERIFIED`；`P-NAVCACHE-1` | `False`（實測） | 不解除 |
| 配息日期語意 | `nav_dividend.py::DIV_DATE_IS_EX_DATE_VERIFIED`；BL-0427(5)、BL-0534 | `False`（實測） | 不解除 |
| 真實覆蓋率／准入 | BL-0545（`DEC-2026-11-07-03`、`-11-12-02` (5)） | BLOCKED；真實 Active Sheet 覆蓋率 NV | 不解除 |
| 1Y 含息窗口 | BL-0427(3)(4)、BL-0524、BL-0547（`DEC-2026-11-13-01`） | 待客戶裁示；New UI 0 消費 | 不解除 |
| 狀態詞彙／`ui_semantics` 未被 `ui_v2` 使用 | BL-0540 G-2／G-3 | 待客戶裁示 | 不解除 |
| Python 3.13 黃金檔 | 無對應 BL／DEC | 事實登記（§3.3-F） | 不建議在本批處置 |

---

### 3.6 盲點與 NOT VERIFIED

**實驗與 grep 指令（單組，可重跑）**

- 副本：`git archive HEAD | tar -x`（基準 `2f13fade…`）；E1～E8 與黃金檔差異比對所用的臨時腳本為一次性、**未入庫**，重現方式見附錄 A。
- **E1** `rows_from_nav_series`：原生來源（`MoneyDJ:wb01`）序列無 `currency`，持倉 `["USD"]` → 寫 `ccy=USD`、`ccy_source=holding_user_input`；持倉 `["TWD"]` 亦寫入，無從矛盾。**E1c** 序列自報 `EUR` vs 持倉 `USD` → `ccy_conflict`。
- **E2** 預存檔序列：列 `fetched_at`＝`cache_updated_at`（`2026-07-22…`）、`is_estimated=False`、`provenance.stale=True`、`cache_fallback=True`。
- **E3** `_nav_from_chain`：`secid_origin` ∈ {`pool_isin_search`,`pool`,`hardcoded_map`} → ACCEPT；{`name_search`,`code_search`} → REJECT；`provenance` 鍵集合中**無** `secid_origin`。**E3b** 晨星無宣告幣別 → `ccy_missing`；**E3c** 宣告 EUR vs 持倉 USD → `ccy_conflict`。
- **E4** 序列無 `fetched_at` → 列 `fetched_at`＝`chain_started_at`，`chain.fetched_at_from="orchestrator"`。
- **E5** `holdings.basis_value_with_reason`：USD 基金 10 單位×淨值 10.5，匯率列 `obs_date=2026-01-02`、`nav_date=2026-11-10` → `3307.5`（照乘，無過舊判斷）；匯率列 `value_unit="美元／新臺幣"`、`value_num=0.0317` → `3.3285`（照乘，差約 1000 倍，無單位檢查）。
- **E6** `resolve_full_keys`：`ACTI71`→ok；`acdd01-eqtal005`→ok、`ACDD01-EQTAL005`；`…?a=ACDD01-EQTAL005` 網址→ok、同 `full_key`；`TLZF9 X`→`ok=False`；`""`→`ok=False`；頂層 `provenance.mapping_source="builtin"`（三端皆不讀）。
- **E7** ALO-2 `nofx`（結果見 §3.3-B）。**E8** `scenario_with("full")` 移除「現金」類全部持倉＋在 dataset 加一筆略過列（`skipped_holdings`，`page_health.OMITTED_DATASET_KEY`） → 現金列仍 `0.0%`／`外`，`_missing_cells` 無，`tail_lines` 空；僅多一個 `_omitted_rows` 鍵。
- **G-1** `git grep -n -E "fillna|\.ffill|\.bfill|interpolate|fill_value|reindex\(" -- services/v2_tables services/v2_domain ui_v2/hld ui_v2/alo ui_v2/exp ui_v3 shared/ui_semantics shared/active_sheet.py repositories/fund`（排除 fixtures）→ 無輸出。
- **G-2** `git grep -n "get_latest_fx\|get_fx_rate_by_date" -- ui_v2 ui_v3 services/v2_tables services/v2_domain` → 僅 `services/v2_tables/market_indicator.py` 一行註解命中（約 :214，提到 `repositories/fund/fx_and_main.py::get_latest_fx` 的組法），無呼叫。
- **G-3** `git grep -n -E "perf_source|official_1y|SRC_SELF|resolve_1y_total_return" -- ui_v2 ui_v3 services/v2_tables services/v2_domain shared/ui_semantics` → 無輸出；`git grep -n "source_tier" -- ui_v2 ui_v3`（非 fixtures）僅值域／徽章／欄標。
- **G-4** `git grep -n -E "mapping_source|ccy_source|currency_id_origin|secid_origin" -- ui_v2 ui_v3` → `ccy_source` 僅 `exp` 輸入側（`declared_ccy_source`）；`mapping_source`、`currency_id_origin` 0 命中；`secid_origin` 0 命中（只在 L2 `nav_dividend.py` 與 L1 `sources.py`）。
- **G-5** `git grep -n "assets_source\|AssetsLoadResult" -- ui_v3 ui_v2 app.py`（排除自身）→ 無消費端。

**盲點**

1. **未連 live、未碰憑證與真實 Sheet**：各 NAV adapter 的 live 可達性、真實 Active Sheet 的欄位／覆蓋率（BL-0545）、Streamlit Cloud 實際 Python 版本與 Secrets＝NV。
2. **測試在 Python 3.13 跑，CI 為 3.11**：R1～R5 綠＝「在 3.13 綠」，不是 CI 綠；唯一與版本相關的失敗已定位（§3.3-F）。第三個黃金失敗（對照組）以同一載入器推定同因，未在 3.11 下以 pytest 實跑。
3. **ALO-2 畫面渲染層未實跑**：Δ3-04／Δ3-05 的數字取自 `logic.build_page_model` 輸出；`ui_v2/alo/page.py` 實際渲染（含 `_omitted_rows` 是否由 ALO-0 另行揭露）未跑 AppTest，**NV**。model 層實測：ALO-0 的 `detail_lines` 與 ALO-6 的 `footer_lines` 另行揭露略過列（「⬜ 資料未備：… 未列入：缺持倉補充」）；ALO-2 該列值仍為 0.0%；page 渲染層 NOT VERIFIED。
4. **`ok=False` 被濾掉的基金畫面如何揭露**（#1227 G3）仍 NV；本批未追到呈現層。
5. **Old UI 的 `source` 多義用法**只做字面 grep，未逐檔讀。
6. **Δ3-02 的判斷力**：本組只證明「B 線接受、來源不進側車、無測試」，**不證明**它違反 `DEC-2026-11-01-02`；選股池 `isin` 的手填程度與實際命中率 NV。
7. **Δ3-03 的可達性**：FX 閘門關閉時非美元不取數；USD 匯率列來自設定試算表已存列，其內容與寫入者 NV；因此「過舊／反向單位」目前是潛在而非已觀測。
8. **`exp` 路徑**：`exp_profile`／`exp_nav` 的 `declared_ccy` 鏈只讀到入口與 #1227 的描述，未逐項重驗；`dividend` 側（`ccy`、`ex_date` 語意）不在本節範圍。
9. **全稱句**：「`ui_v2`／`ui_v3` 無 fill 類操作」「三端皆丟棄 `ccy_source`」「`secid_origin` 無 UI 消費者」「`assets_source` 無消費端」皆為單組字面 grep，**不含別名、動態組字、字串內嵌 import**，未經第二組驗證。
10. 本節所有「嚴重度」與「推薦」為單組作者讀法，可被客戶推翻；本節**不構成**對任何 Gate 的解除、對任何程式／測試／黃金檔／Schema 的變更授權。

## 附錄 A　一次性腳本與實驗輸出未入庫；重現方式

本檔所稱的診斷腳本與實驗輸出（`sum()` 因果實驗、7 案 1Y 合成序列重現、E1～E8 純函式實驗、黃金檔跨直譯器比對）皆為一次性、**未入庫**，不構成可執行的 repo 資產。非作者 QA 可依下列描述獨立重現（皆不連網、不碰憑證與 Sheet，在 `git archive` 副本上執行）：

1. **`sum()` 因果實驗（§1.2-6）**：在 pytest 啟動前執行 §1.2-6 所附 shim（`builtins.sum` 換成左到右逐項相加），再以 `pytest.main([...])` 重跑 §1.2-6 所列 8 條測試；對照組為不加 shim 的同一指令。
2. **黃金檔跨直譯器比對（§1.2-6 第 2 點）**：在 `git archive HEAD` 副本內，以 `tests/_alo_core_golden.py` 的 `run_matrix(live_namespace())` 產出矩陣，與黃金檔的 `strings`＋`matrix` 逐位元組比對；分別用 CPython 3.11 與 3.12／3.13 直譯器各跑一次（該矩陣不需 numpy／pandas）。**只比對、不寫回黃金檔。**
3. **7 案 1Y 重現（§1.2-3）**：以 §1.2-3 所列的合成序列（盤中 250／251／252 列、週頻 252 列、月頻 60 列等）呼叫 `services/fund_service.py::calc_metrics` 與 `services/fund_total_return.py::resolve_1y_total_return`，記錄 `window_days` 與 `status`。
4. **E1～E8（§3.6）**：依 §3.6 列出的函式名與輸入（`rows_from_nav_series`、`_nav_from_chain`、`holdings.basis_value_with_reason`、`resolve_full_keys`、ALO-2 `_build_alo2` 等）以純函式呼叫重現；輸入與預期輸出已寫在 §3.6 各條。

若上述描述不足以重現，應視為本檔的**重現性缺口**，由非作者 QA 回報，而不是以口述補足。

> **更正指標（2026-11-13，`DEC-2026-11-13-03`；本檔其餘文字不變）**：本檔「三節總覽」§1 列、§1 開頭「範圍」與 §1.5 第 1 點關於「Issue 只明列五項、第六項未枚舉、待客戶指明」的敘述為誤讀。依客戶裁示：六項品質補強已明確列在 Issue #1228；本檔覆核的五個高風險案例只是 Batch 1 至少覆核的案例，不是六項工作的完整清單，無待指明的第六案例。五項覆核的結論本身不受影響。
