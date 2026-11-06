# 82｜New UI2 💼 我的資產：UI × Data × Evidence 施工前設計草案（U1～U5 UI 設計已核准〔DEC-2026-11-04-02〕；其餘仍待裁示）

> **定位**：ChatGPT 產品／資料契約初稿，2026-11-04（區塊順序已由 DEC-2026-11-04-01 核准主圖在前，見 §0.1；其餘仍待核准；~~U1～U5 仍待核准~~ 已由 DEC-2026-11-04-02 核准 UI 設計，見 §9.8）。**非已核准 wireframe、非公式或資料語意裁示、非程式實作授權**。此檔不取代 frozen `44`、`79`、`80`、`73`、`74`；同一事實以原正式契約為準。**區塊順序以 §0.1／`DEC-2026-11-04-01` 為準，其餘仍以 `80`／`44` 為準。**先驗既有 capability／欄位，再由客戶核准具體版面。不得因本草案把舊 UI 程式直接搬入 `ui_v3`。
>
> **讀碼範圍**：`services/v2_tables/alo_holdings.py`、`services/v2_domain/{holdings,deviation}.py`、`services/v2_tables/nav_dividend.py`、`ui_v2/{hld,alo}/{source,logic}.py`；對照 `docs/v2/{73,74,79,80}_*.md`。此為 ChatGPT 單組盤點，**尚未由獨立組逐欄複驗**。
>
> **2026-11-04 專案 AI 獨立稽核（單組、三份獨立報告；非客戶裁示）已核實 §2／§4 的主要敘述**：結果見第 8 節；§2、§4 內以【稽核更正】標示就地修正處，ChatGPT 原文保留（錯的字句加刪除線）。本檔仍**非規格**；~~待客戶核准草案~~（U1～U5 UI 設計與缺 FX 方案 A 已核准，僅 UI；其餘 Q／G 仍待裁示；見 §9.8）；主圖資料欄位、公式、狀態詞與 Gate 的登記位置為 `docs/BACKLOG.md` BL-0542，本檔不重複成文；本檔內「G-n」一律指 `BL-0542 G-n`（與 BL-0538、BL-0540 各自的 G 編號不同、互不相通），「Q7～Q15」為本檔 §6.1 的問題編號（BL-0542 沿用，非 BACKLOG 全域編號）。以下「候選接線」不保證已存在 New UI2 可直接調用的 facade；實作組必須在核准後驗證精確 schema。


## 0.1 客戶核准的 💼 版面方向（2026-11-04；DEC-2026-11-04-01）

> **核准射程僅限 UI 順序與缺資料顯示原則**：客戶任務指示逐字（與 `docs/evidence/decisions/2026-11-04_assets_chart_first_direction.md` 一致）：「客戶已核准 💼『我的資產』三項 UI 方向：1. 主要圖表在前。2. 四項摘要在後。3. 資料不足明確顯示 Missing，不填假數據。」另：ChatGPT 向客戶提問、客戶回「同意」屬轉述（轉述者：ChatGPT，非逐字）。這**不是**核准整份 82、未授權 B0 實作，也未裁 BL-0542 G-1～G-5 或 Q1～Q15。本節是（僅限本節所列順序／缺值顯示原則）現行權威落點；§1.1 舊草圖保留為原提案歷史，遇有排序衝突以本節為準。

### 390px 手機設計順序（布局草圖；其餘細節仍待獨立線框核准）

> 本草圖僅示意「主圖在前、四格在後」順序；~~SPEC、偏離、配息的先後與位置屬待裁示（Q3），非客戶已核准~~（U1 配息位置與 U3 SPEC 已由 DEC-2026-11-04-02 核准 UI 設計；Q3 其餘細節仍待裁；原文保留）。

```text
[💼 我的資產：頁名／資料來源時點]
[持倉狀態／是否需注意：僅正式可證的 β／Missing 語意]
[配置主圖：實際 vs 目標；無合法口徑則狀態卡，不畫空軸]
[SPEC：已核准成本或市值基準、單位、日期、缺項]
[摘要 2×2：總資產｜損益｜報酬｜期間配息]
  （無正式合法算法者固定保留欄位、顯示 ◇ 資料未備／⬜ 無法判定；不造 0）
[偏離與未評估事實／查看明細]
[已核實的除息／配息資訊；不誤寫入帳日]
[▸ 全部持倉／逐檔 NAV、配息、配置來源與缺項]
```

桌機 1280px：共用 Shell，下方主圖為主要視覺焦點；右欄可放已核准 evidence／配息，但**四格摘要不得視覺優先於主圖**；持倉詳表與資料限制可展開，全部正式 evidence 不因 UI 精簡而遺失。具體 grid、breakpoint、欄寬、chart height 與截斷測試須在下一輪線框定案，不以此草圖作已量測的證據。

| 區塊 | 現有資料接線的現實限制 | UI 必須遵守 |
|---|---|---|
| 頁首 β／注意 | β 組合邏輯仍在 `ui_v2`、BL-0411 仍有 Gate | 尚未合法接入時不得造「正常／安全／無偏離」 |
| 配置主圖 | `ui_v2/alo/logic.py::_build_alo2` 組合算式未 PORT；成本／市值與 FX 閘門未全部確認 | **主圖位置保留，但不能用未核准公式填數**；可用缺值狀態卡，勿空畫座標軸；缺 FX 不退回成本、不把不完整分母畫成完整 100% |
| 四格摘要 | `summary_strip()` 四格目前均 Missing；無核准的同口徑計算 | 四格**在主圖之後**且維持佔位；不可自造總資產、損益、報酬或配息 |
| 配息資訊 | `pay_date` 無可用正式入帳日、推估日契約另 Gate | 只能揭露已驗證的日期語意；目前不得以「入帳日」命名 |
| 明細／Evidence | holding、policy、NAV、dividend、user setting、FX、skipped、unread、失敗與未評估證據 | 顯示可收合，但 data／domain／future Digest 不刪、不改、不回寫 |

**首屏上限**：保留 frozen 44 的頁級 chip＋核心數字 ≤5，逐元素點數；Missing 佔位不是有值，不代表可無限制疊加狀態 chip；**Missing 佔位仍計入 frozen 44 首屏 ≤5 的元素點數**（保守讀法，待線框逐元素點數確認）。未實測 390px／1280px，不宣稱首屏或視覺 Fidelity 已通過。對 `PROJECT_RULES.md` 13.5 的 chart-first 方向，本裁示確立主圖先於四格；`80 §7.2` 早期 2×2 在前的順序僅作前版草圖，**不得據以覆蓋本次方向**。

**下一個正當交付**：由 ChatGPT 撰寫逐卡欄位／缺值／freshness／evidence 完整 wireframe，經客戶再核准未決細節後才另批授權 Claude Code 寫程式；**本句與本節不構成任何實作授權**。待決項以 BL-0542／82 §6.1 為準。

## 1. 產品目的與顯示優先序

💼 為「持倉＋資產配置＋配息」單頁，不回復舊兩頁；行動建議不自行產生。手機 390px，第一屏讓使用者明確知道：① 我的資產狀態是否可判讀 ② 有哪些缺值／未評估需要注意 ~~③ 核心資產數字與配置入口 ④ 可以查看的主要圖表。~~【已由 DEC-2026-11-04-01 取代（僅順序）：主要圖表在前、四項摘要在後，現行順序見 §0.1；本句其餘（①②、不遺失完整持倉與 evidence）不變】其他資料下沉，不做 Top N 截斷，不遺失完整持倉與 OneBrain evidence。

### 1.1 手機與桌面草圖（區塊順序候選，非最終像素稿）

> 【已由 DEC-2026-11-04-01 取代（僅順序）】下列草圖中「摘要 2×2／摘要四格排在配置主圖之前」的排列為原提案歷史，**現行順序以 §0.1 為準**（主圖在前、四格在後）；欄位內容、Missing 語意與其餘區塊不因此改動。

```text
390px Mobile                            1280px Desktop
[💼 我的資產] [資料狀態／關注]         [💼 我的資產] [狀態／注意] [資料時點]
~~[摘要 2×2：資產／損益／報酬／配息]       [摘要四格，缺值仍佔位置]~~
[配置實際 vs 目標：主要圖]              [配置實際 vs 目標主圖] [配息／近日事件]
（現行：摘要四格改排主圖／SPEC 之後，見 §0.1）
[SPEC：基準／單位／範圍／資料日]         [SPEC + 主要差異依據]
[偏離項摘要 + 查看偏離明細]              [逐檔／類別完整展開區]
[配息／近期事件（正式日期優先）]          [持倉、淨值、配息、資料缺口]
[▸ 全部持倉／單檔淨值與配息]
[▸ 資料限制／分類／來源證據]
```

預設「摘要 2×2」延用 `80 §7.2`（~~其在主圖前的位置~~【已由 DEC-2026-11-04-01 取代（僅順序）】；四格內容與口徑限制仍有效）：總資產｜損益｜報酬｜配息，但**不宣稱四值已有同口徑、可跨幣別、可匯總的已核准計算**。任何值未具備正式算法時顯示「◇ 資料未備／⬜ 無法判定」，不得造數字或以成本冒充市值。圖表必須有已核准口徑（成本或市值）及對應合法來源；不同幣別不可無匯率硬加總。

【稽核補充（專案 AI；非客戶裁示）】

**與 `80 §7.2`（已凍結 implementation input）的差異；核准前以 `80 §7.2`、`44` 為準（~~含其摘要在圖前的順序~~【已由 DEC-2026-11-04-01 取代（僅順序），順序以 §0.1 為準】）：**

| 項目 | `80 §7.2` | 本草案 §1.1 |
|---|---|---|
| 桌機「基金占比｜各檔區間報酬」區 | 有 | 無 |
| SPEC 列、偏離摘要（含查看偏離明細）、資料限制／來源證據展開區 | 無對應區塊 | 新增 |
| 頁級狀態 | β 階梯 | 只寫「資料狀態／關注」，無 β 頁級字樣（BL-0536-W2） |

- ~~摘要 2×2 排在主圖前的依據是 D-5B（`DEC-2026-10-30-02`，客戶裁示 💼 首屏保留四項 compact summary slots，缺值仍佔位）。稽核讀法（可被客戶推翻）：`PROJECT_RULES.md` 13.5 第 1 點的順序為 ① 狀態 ② 注意 ③ 主圖 ④ evidence ⑤ 必要數字，字面上四格摘要應排在主圖之後，兩者有張力；D-5B（2026-10-30）早於 13.5（2026-11-03），未見客戶調和。列入待客戶裁示，客戶核准線框時一併確認。~~【已由 DEC-2026-11-04-01 取代（僅順序）：客戶 2026-11-04 核准主圖在前、四項摘要在後（DEC-2026-11-04-01；§0.1）。D-5B 的「四項 compact summary slots、缺值仍佔位」保留有效；上列「稽核讀法（可被客戶推翻）」已被客戶核准取代，不再待裁示。】
- 首屏名額（≤5；`DEC-2026-11-03-11`，降級情境也要 ≤5，Status Bar 純文字不計）逐元素讀法：手機首屏 = 頁級狀態 chip 1（正常情境）＋ 摘要四值 4 ＝ 5；若「關注」另算一枚 chip 即為 6。主圖、SPEC、偏離摘要是否計入名額取決於元素形態（chip／核心數字才計）。**Status Bar「n／m 項已取得」是否計名額仍待客戶確認**（HANDOFF、BL-0536）；降級情境（摘要格缺值仍佔位）是否維持 ≤5 須在客戶核准線框時逐元素點數，本草案不宣稱已達成。

## 2. 逐區塊資料串接矩陣（施工前須複驗）

| 區塊／元件 | 候選正式資料／欄位 | 已有位置／能力 | 確定性與 Gate | 不可做的事 |
|---|---|---|---|---|
| 頁首持倉健康／β 結論 | ~~holding、policy、nav、dividend、setting、market_indicator 的正式載入與狀態~~【稽核更正：`load_alo_tables_active` 回 holding、policy、略過／失敗紀錄，另含 `direct`、`warnings`、`read_estimate`、`actor` 等欄；不含 nav、dividend、設定、匯率，這些各走不同 L2 入口，組裝在 `ui_v2/{hld,alo}/source.py`、`live.py`】 | `alo_holdings.load_alo_tables_active`、`ui_v2/hld/logic.py`、`ui_v2/alo/logic.py`；D-3 P3／β 見 `74` | **重用既有結論語意**，核對 skipped_tabs／skipped_holdings 對結論的影響；New UI2 adapter／viewmodel 路徑待定。【稽核更正：判定本體在 `ui_v2/**`，ui_v3 現無合法取得途徑，需 PORT（Gate G-1）；詳見第 8 節】 | 不以部分讀取當成「無持倉／正常」，不在 UI 自建狀態 precedence |
| 四項摘要 | holding／policy／nav／dividend 與相關 user_setting、FX | `alo_holdings`、`nav_dividend`、`v2_domain/holdings`、既有 HLD／ALO domain outputs | ~~**欄位級 mapping 待複驗**~~【稽核已複驗：`ui_v2/asset/overview.py` 的 `summary_strip()` 四格硬編碼 Missing（D-5A／D-5B，`DEC-2026-10-30-02`），FX 閘門關閉（`services/v2_tables/market_indicator.py` 的 `FX_OBS_DATE_RULE_VERIFIED = False`）；`ui_v3` 現無合法可取得、且已核准的四項算法。舊樹另有 Old UI 專屬的 `services/portfolio_performance.py::portfolio_returns`（TWD basis 加權、含匯率損益的組合每日報酬）、`services/portfolio_service.py::compute_portfolio_drawdown`、`services/fund_invest_calc.py::estimate_monthly_income`（單檔投入推估月配）；它們不在 New UI2 合法介面，口徑與 frozen 44 對「報酬」的定義是否一致 UNVERIFIED，併入 G-4（此為依函式名 grep 所得，未窮舉）】：無已核准跨幣別匯總公式不得顯示假總值 | 不新增匯總公式；缺值不填 0；不混淆報酬率和損益 |
| 配置主圖：實際／目標 | holding.bucket、holding.cost_twd 或 holdings×latest NAV×FX；user_setting 的 `alo_target_weights`、`alo_basis`、`alo_tolerance_pp`【稽核補充：另有草案漏列的 `alo_bucket_names`；三鍵皆無預設；類別加總、分母、比重、差額、帶內外的組合算式在 `ui_v2/alo/logic.py`（`_category_values`、`_build_alo2`），L2 `v2_domain/holdings.py` 只有原子】 | `ui_v2/alo/logic.py` ALO-2／ALO-4；`v2_domain/holdings.py`；`v2_domain/deviation.py` | 正式選定**成本／市值基準**才呈現；僅用已驗證 mapping；百分點差額與容許帶必須附設定來源；缺 FX 不轉用成本 | 不 UI 重算、不能自訂容許帶或默認 0、不能將未分類靜默分配 |
| 偏離摘要／明細 CTA | ALO-2 類別差距、HLD-1 正式逐檔偏離與門檻、未評估件數 | `ui_v2/{alo,hld}/logic.py` 既有 domain / P3 β；`73` | 顯示為「規則比較的事實」；點擊只展開既有明細；不能當投資再平衡指令。【稽核更正：`v2_domain/deviation.py` 只有比較方向、差額與失敗優先；HLD-1 逐檔走訪在 `ui_v2/hld/logic.py::deviation_rows`，ui_v3 需 PORT】 | 不提供一鍵再平衡、不造 action state |
| 近期配息／配息日曆 | dividend rows、已核准 date semantics、status；holdings 與 NAV 供必要確認 | `services/v2_tables/nav_dividend.py`、`79 §17.12`、`80 §7.2`、`73 HLD-3/HLD-6` | **日期契約 Gate**：~~正式日期優先、deterministic estimate 只作 fallback~~【稽核更正：此句只存在於規格，程式沒有。dividend 列欄位為 `fund_code, ex_date, pay_date, div_per_unit_orig_ccy, ccy, div_kind, fetched_at`（無 `status`、無 `record_date`）；`pay_date` 現一律空；未來日期的 `ex_date` 被 L2 丟棄；`services/v2_tables/nav_dividend.py` 的 `DIV_DATE_IS_EX_DATE_VERIFIED = False`，`build_dividend_table` 在閘門關閉時整批列 pending、不取數，故 dividend 目前實際有沒有列須以此閘門為前提（現場行為 UNVERIFIED）；推估引擎 `services/dividend_calendar.py` 不在 ui_v3 允許前綴，且目標為配息基準日（≠44 的 ex_date 除息日）】；`pay_date` 未完成 amendment 前不得說「實際入帳日」；資料來源日期類型逐欄標 | 不把除息日當入帳日、不用缺日期預估正式付款、不把推估混成已確認 |
| 持倉明細（全列）／單檔展開 | holding_id、fund_code、~~政策／級別~~【稽核更正：holding 無政策／級別欄，只有 `bucket`】、單位數、幣別、NAV 日期／點、配息序列；必要 skipped reasons | `alo_holdings.build_alo_tables`、`v2_domain/holdings.py`、`nav_dividend`、`73 HLD-5/HLD-6/ALO-6` | 全列保留，單檔展開只影響畫面；原始 identity、同鍵衝突與 FX gate 不變【稽核補充：同鍵多列時 hld 與 alo 兩頁各自合併（hld 去空白比四欄、alo 不去空白比 bucket／ccy）；同鍵不同幣別 raise，不是逐列缺值；`last_synced_at` 是核對日 12:00 台灣時間的推定值，非讀取時間】 | 不用 Top N 切掉持倉；不同基金不能因同名合併 |
| 異常／資料健康摘要 | Active Sheet 狀態、settings、NAV、FX、配息與 skipped/unread/failed | `alo_holdings.load_alo_tables_active`、`ui_v2/{hld,alo}/source.py`、`services/v2_tables/settings_store.py` | 首屏顯示與判讀相關的 Missing／失敗；完整來源健康明細由 ⚙️ 承接（涉及 `BL-0540` 先守現行 44）。【稽核補充：Active Sheet 未設定與讀取失敗可由 `ActiveSourceError` 的 code＋reason 區分，無 fallback；判定 `is_no_active` 在 `ui_v2/active_gate.py`；`ui_v3/viewmodels/common.py` 的 `STATUSES` 只有 ok／missing／failed／stale／undetermined 五個，但 `shared/ui_semantics/rules.py` 已有核准規則列 `not_configured`、`user_param_unset` 等；缺的是 `unread`／`skipped`／`unknown currency` 與頁級 `no_holding`／`partial`／`normal` 字樣（G-5）；`user_setting`／`market_indicator` 讀另一本 `SETTINGS_SHEET_ID`（服務帳戶），不隨 Active Sheet 切換；`refetch_nav` 仍走舊 `POLICY_SHEET_ID`，ui_v3 不得呼叫】 | 不暴露 secret、內部 reason code、traceback；unavailable ≠ neutral |

**欄位可信度分級**：已看到函式／來源名稱 ≠ 已核對返回 schema。正式施工規格每一列須由專案 AI 在獨立查核中列出「實際 function、return path、value type、unit、source、as_of、retrieved_at、missing／failure、sample fixture／test」，並連回正式 `44` 與 `79`；不確定的格子標 `UNVERIFIED`，不能假設可直接 import `ui_v2`。

## 3. 分層與 OneBrain Evidence 完整性

```text
使用者 Active Sheet＋已核准 NAV／配息／FX／設定來源
  → L1 取得／校驗 → L2 正規化、身份與幣別／日期契約
  → 正式 deterministic domain results（含 HLD／ALO rule results）
      ├─ UI ViewModel → 💼 390px/1280px 人類可讀圖卡／展開列
      └─ Complete Evidence / Future Decision Digest
         （全部通過契約的 holdings、policy、NAV、dividend、settings、
          FX、skipped／failed／unjudged、source、as_of、retrieved_at、
          identity keys、rule result、threshold reference、counter-evidence）
```

- UI **只投影** canonical/deterministic 結果，不能生成新的金融事實或回寫來源。
- 未顯示在第一屏的 evidence 仍應能在正式資料與測試中追溯；**不表示現在就啟動 Phase 7 OneBrain**。
- Missing／failed／not evaluated／not configured／unknown currency／skipped worksheet 分別保存；不得簡化為中性或零。
- `Active Sheet` 未設定與讀取失敗是兩種不同狀態；不可 fallback 到別本持倉。
- 配置成本／市值、貨幣換算與基金識別共用既有正式 domain logic；禁止重複實作。
- 【稽核更正】上圖「正式 deterministic domain results（含 HLD／ALO rule results）」在 💼 現況並不存在於 L2：只存在 `ui_v2` 的 page-model dict；Digest 層零實作；可同時餵 UI 與 Digest 的 domain result 目前只有 🌍（`NormalizedComparison`）。

## 4. Implementation options：先選路徑，再施工

| 路徑 | 正確性與風險 | 工時／Token | 取捨 |
|---|---|---|---|
| A. `ui_v3` 直接 import `ui_v2` page／logic／CSS | 高耦合，可能違反 New UI2 migration boundary | 初期看似快，後續回歸高 | ~~不採~~【稽核更正：已被 `80 §8.1` 與 `tests/ui_v3/test_ui_v3_import_guard.py` 明文禁止，不是待選項】 |
| **B. 以合法 L2／shared domain／adapter 建 `ui_v3` ViewModel** | **最佳**：domain 單一計算、UI 測試可獨立 | 初期需 contract mapping，後續重用率高 | **推薦；符合 `80 §2/3/8`** |
| C. 複製舊 HLD／ALO 計算到 `ui_v3` | 兩份公式失同步、來源／幣別語意漂移 | 眼前省時，總成本高 | **禁止** |

【稽核補充（專案 AI；非客戶裁示）】`80 §3.2` 只點名函式（`return_pct`、`drawdown_pct`、`vol_pct`、`deviation_rows`、`merge_same_key_holdings`、`aggregated_holdings`、`basis_value`、`category_of`、`exceeds`、`target_sum` 等），其中已在批 2a 搬入 `services/v2_domain`（`holdings`、`nav_metrics`、`deviation`）者即為 `ui_v3` adapters 可合法 import 的 L2，另含 `services/v2_domain/freshness.py::delay_days`；本草案要 PORT 的 `_category_values`、`_build_alo2`、`_conclusion_light`、`_build_hld5`／`_build_hld6`、`_build_alo6` 未被 `80 §3.2` 分類為 PORT（屬各頁 live／page WRAP／REIMPLEMENT），所以 G-1 是**新增 PORT 範圍**（Q7）。B 路徑中「合法 L2／shared domain」今天只涵蓋原子與資料表建構，衍生值仍待 PORT；逐檔原料 `return_pct` 等已在 `services/v2_domain/nav_metrics.py`，不需 PORT。可行路徑比較如下（1 為最快、2 與 3 屬 Gate、4 與 5 禁止）：

| 路徑 | 正確性與投資語意風險 | 重用度 | 修改範圍與回歸風險 | 速度 | Token／Model 成本 | 失敗降級路徑 |
|---|---|---|---|---|---|---|
| P1 adapter 只取事實、不產生衍生值 | 低（不算任何衍生數字） | 中（只重用資料表） | 小；須配合 Preview 執行期守衛（G-2） | 最快；合法、不需新 Gate | 低 | 缺值 ViewModel 照實顯示 ◇ 資料未備 |
| P2 完整 PORT 到 `services/v2_domain` | 最低（單一公式源） | 最高 | 大：動 ui_v2 薄包裝與 golden、兩個 ownership lock 測試要改（檔名 UNVERIFIED；稽核只見 `tests/test_v2_domain_port.py` 的 `NAV_NOT_READY_DAYS` 單一來源鎖與 `tests/ui_v2/test_alo_live_logic.py` 的 10 天門檻鎖） | 慢 | 高（formula／data semantics 等級，需獨立稽核與 Model／Effort 重估） | 對照 golden 回退 |
| P3 分階段 PORT，先成本口徑最小核心 | 低（成本口徑不依賴 FX 與 NAV） | 高 | 中；每階段各自稽核 | 中 | 中至高 | 閘門關閉下成本口徑仍可運作；市值面維持 Missing（稽核 A 推薦） |
| P4 `ui_v3` 重寫公式 | 高（兩份公式失同步） | 0 | — | — | — | **禁止** |
| P5 `ui_v3` import `ui_v2` | 高（耦合） | — | — | — | — | **禁止** |

**建議第一切片 B0**：P1＝資料契約＋fixture＋缺值 ViewModel（不產生衍生值），不需新 Gate；衍生值待 P2／P3 的 Gate 裁示後再接。**配息建議採 D1**（稽核建議，待客戶核准）：只顯示已發生的除息列、不顯示 `pay_date`、其餘 ◇ 資料未備。以上為稽核建議，待客戶核准。

B 不是任意抽新 facade 的授權：只有已確認符合 `ui_v3` import boundary 的下層可直接用；發現必須新增 L2、搬遷計算或擴充 source，先依 Stop／Decision Gate 評估；不能自動升級。

## 5. 分批驗收條件（先核准 wireframe／contract，後才可實作）

1. **文檔驗證**：UI 元件 ID → 正式 L2/domain output → 欄位／單位／日期／來源／缺值 → 規格／tests，逐格對照；不得只有「接 Google Sheet」。
2. **390px／1280px**：首屏能讀狀態、是否需注意與必要數字；符合 44 既有 budget；無橫向捲動、底部導覽不遮內容；顏色非唯一載體。
3. **資料情境**：正常、零持倉、無 Active Sheet、部分 worksheet skipped、全表失敗、NAV 缺／延遲、FX 不可用、user_setting 未設／失敗、配息日期未確認、基金身份衝突，至少各一 fixture。只表示能顯示，**不宣稱已真實連線驗收**。
4. **跨頁一致**：相同 canonical holding id、NAV／FX、配息 row 與同一組 rule results，💼／🔍／⚙️／未來 Digest 不得出現互斥口徑；未完成頁只驗 contract，不假裝已可用。
5. **稽核**：與 frozen 44、79、73、74、`PROJECT_RULES`、`CLAUDE` 逐項比對；涉及 formula／data semantics 必須另走 Gate；有真 bug 記 backlog，不順手擴範圍。

## 6. 需要客戶看線框後決定，而非本檔自行裁定

- Q1：四項摘要是否各自有已核准可比較的值／幣別／區間，還是部分須維持資料未備？
- Q2：配置主圖在未設 `alo_basis` 或缺市值匯率時，應整圖降級，還是只保留未跨越資料契約的部分？
- Q3：手機「配息／近期事件」在主圖前或後？只調 presentation priority，不改資料語意。【DEC-2026-11-04-01 已核准主圖在前、四格在後，§0.1 草圖僅示意主圖／四格順序，~~配息資訊的位置與先後屬待裁示（Q3），非 §0.1 已定~~（已由 DEC-2026-11-04-02 取代：僅 UI 設計；G-1 技術承接仍待裁；原文保留：U1 配息位置已核准），口徑與日期語意仍待 Gate】
- Q4：細節區的基金／保單分組、已被略過來源的警示層級，以及 44 的預算如何在新合併頁保持正確？
- Q5：BL-0538／BL-0540 與 frozen 44 承接、Missing 用字等另案 Decision Gate；本檔不代裁。
- Q6：正式配息日期／估算 fallback 與 44 amendment（BL-0534）未完成前的最小合法顯示。

### 6.1 稽核新增問題（專案 AI 新增，Q1～Q6 原文不動；非客戶裁示）

- Q7：PORT 範圍擴大（配置、偏離、市值、β 分類、NAV 10 日門檻、`is_no_active`）是否核准，屬 Gate（BL-0542 G-1）。
- Q8：四項摘要何時、以何種公式解除 Missing（BL-0542 G-4）；在此之前維持 D-5A／D-5B（四格順序已由 DEC-2026-11-04-01 核准在主圖之後；**口徑／公式仍待 Gate**）。
- Q9：誰負責設定目標比重、容許帶、基準？ui_v3 第一階段唯讀，💼 沒有合法寫入面。
- Q10：hld 與 alo 兩套同鍵合併規則以何者為準。
- Q11：~~部分缺值時分母不完整的呈現方式~~（UI 呈現已由 DEC-2026-11-04-02 方案 A 取代：不顯示完整 100%，改顯示資料未備與未涵蓋範圍；G-1 技術承接與公式仍待裁；原文保留）（市值基準缺 USD 匯率會顯示 100%，須連同「合計未涵蓋」揭露）。
- Q12：BL-0411（頁級燈 production 閘門）是否視為已解除。
- Q13：「資料不足」與「◇ 資料未備」的分工（BL-0540 G-2；非 BL-0542 的 G 編號）。
- Q14：期間配息合計是否核准用「目前單位數」；配息 `pay_date` 與推估日期（BL-0534）。
- Q15：BL-0536-W1（`chart_empty` 字樣）、W2（β 頁級字樣）、BL-0369／H4（freshness 門檻）、Status Bar 與降級首屏的計數讀法。

**Decision Gate 候選**：只記錄、不自行開工；G-1～G-5 的正文與登記位置只在 `docs/BACKLOG.md` BL-0542，本檔不重複成文（避免兩處成文漂移）。

## 7. 本次 PR 的 Definition of Done

此 PR **只完成施工前產品草案與資料 mapping 候選**。Merge 不等於客戶已核准設計、不等於 UI 已完成、不等於可開始 💼 程式（客戶 2026-11-04 ~~僅核准主圖在前／四格在後／Missing 如實顯示的 UI 順序方向，見 §0.1~~〔已由 DEC-2026-11-04-02 取代：僅 UI 設計；G-1 技術承接仍待裁；原文保留：U1～U5 UI 設計與缺 FX 方案 A 已核准，見 §9.8〕；不改本句其餘結論）。下一步為專案 AI 的獨立欄位契約驗證（唯讀報告）＋客戶 wireframe 核准，再另批實作。仍維持 Silent Autonomous Cruise。

【稽核註記】「專案 AI 的獨立欄位契約驗證」這個中間步驟是本草案的提議，不是客戶裁示原文（`DEC-2026-11-03-12` 只寫核准後專案 AI 才實作）；第 8 節即為該驗證的第一輪結果（單組，非客戶裁示）。

## 8. 獨立稽核核實結果（專案 AI，2026-11-04，單組；非客戶裁示）

> 基準 main 21296a0d；三份獨立稽核（資料接線 A、B，文件治理 C）加合成資料 trace；稽核報告不納入 repo，本節只留結論，與下列 file 事實不符時以程式為準。抽查項：ui_v3 守衛禁止 import `ui_v2`、四項摘要硬編碼 Missing、FX 閘門關閉、NAV 10 日門檻位置、`pay_date` 現一律空、Preview 執行期守衛白名單，皆已對照程式確認。

| 元件 | 正式 service::function | 計算所在層 | ui_v3 現在能否合法取得 | 已有測試 | Missing 行為 | 草案敘述判定 |
|---|---|---|---|---|---|---|
| 頁首持倉健康／β | 原料：`services/v2_tables/alo_holdings.py::load_alo_tables_active`、`settings_store.py::load_user_settings`、`nav_dividend.py::build_nav_dividend_tables`；判定：`ui_v2/{hld,alo}/logic.py::_conclusion_light`、`ui_v2/asset/page_status.py::aggregate`、`ui_v2/status_class.py` | 判定在 `ui_v2`（L3） | 原料可由 adapter 取得；判定不能，需 PORT；β 排序純函式在 `shared/ui_semantics/rules.py::resolve_precedence`（viewmodels／pages 可讀；BL-0411 閘門見 Q12） | `tests/ui_v2/test_p3_page_status_logic.py`、`tests/ui_v3/test_ui_v3_semantics_rules.py` | 缺分類鍵直接 raise；取數失敗＞無持倉＞注意＞缺值＞未設定或不適用（`status_class.UNSET`，⬜）＞部分＞正常 | 部分正確 |
| 摘要四項 | 無（`ui_v2/asset/overview.py::summary_strip()` 硬編碼 Missing） | 無算法 | 無可取得項 | `tests/ui_v2/test_ast_overview_logic.py` | 四格一律 ◇ 資料未備 | 「缺值顯示 ◇ 資料未備」正確；「欄位級 mapping 待複驗」已複驗＝四項皆無算法 |
| 配置實際 vs 目標 | 原子：`services/v2_domain/holdings.py`（同鍵加總、最近淨值、匯率對齊、類別歸屬、`exceeds`、`target_sum`）；組合：`ui_v2/alo/logic.py::_build_alo2` | 原子在 L2；組合在 `ui_v2` | 原子可；組合不能，需 PORT（G-1） | `tests/test_v2_domain_port.py`、`tests/ui_v2/test_alo_logic.py` | 缺基準值的類別排除於分母；缺 USD 匯率時債券顯示 100%，須附「合計未涵蓋」 | 部分正確（設定鍵與來源有誤、漏列 `alo_bucket_names`） |
| 偏離摘要／明細 | `services/v2_domain/deviation.py`（比較方向、差額、失敗優先）；HLD-1 逐檔：`ui_v2/hld/logic.py::deviation_rows` | 逐檔走訪在 `ui_v2` | 比較原子可；逐檔不能，需 PORT | `tests/ui_v2/test_hld_logic.py` | 門檻未設顯示 ⬜ 未設定，不當 0；門檻為使用者設定，非 SSOT 常數 | 部分正確 |
| 配息／近期事件 | `services/v2_tables/nav_dividend.py::build_nav_dividend_tables`；推估：`services/dividend_calendar.py` | 資料表在 L2；HLD-3 期間合計在 `ui_v2/hld/logic.py` | 資料表可（受 Preview 執行期守衛限制，G-2）；推估引擎不在允許前綴（G-3） | `tests/test_v2_tables_nav_dividend.py`、`tests/test_v2_tables_dividend_chain.py`、`tests/test_dividend_calendar.py` | 空清單且無證據＝無法判定，不當成「無配息」 | 「正式日期優先」錯誤（程式沒有）；其餘部分正確 |
| 持倉明細／單檔展開 | `alo_holdings.py::build_alo_tables`；`v2_domain/holdings.py::merge_same_key_holdings`、`aggregate_holding_rows`；逐檔組列：`ui_v2/hld/logic.py::_build_hld5`、`_build_hld6`、`ui_v2/alo/logic.py::_build_alo6` | 表在 L2；組列在 `ui_v2` | 表與合併原子可；組列不能，需 PORT | `tests/test_v2_tables_alo_holdings.py`；ui_v3 側尚無 💼 測試 | 單位數空白或為 0 不寫列、進略過紀錄；略過原因為中文字串，非 reason code | 部分正確（無級別欄；同鍵多列兩頁各自合併） |
| 資料健康／異常 | `alo_holdings.py::load_alo_tables_active`（`ActiveSourceError`）；`settings_store.py` | 判定 `is_no_active` 在 `ui_v2/active_gate.py` | 例外型別可；判定與狀態詞不能；`ui_v3/viewmodels/common.py` 的 `STATUSES` 五值，rules 表已有 `not_configured`／`user_param_unset`，缺 `unread`／`skipped`／`unknown currency` 與頁級 `no_holding`／`partial`／`normal` 字樣（G-5） | `tests/ui_v2/test_active_gate.py` | 未設定與讀取失敗可區分、無 fallback | 部分正確 |
| ViewModel／Digest 分流 | 無（Digest 層零實作） | — | — | `tests/ui_v3/test_ui_v3_viewmodel_contract.py`（🌍） | — | 與 💼 現況不符（見第 3 節更正） |

**重點事實（稽核據程式；凡抽查不到者標 UNVERIFIED）**

- 逐檔原料：成本只有 `cost_twd`（int，TWD）；`return_pct` 是 NAV 價格報酬（百分點，期間為使用者設定 `hld_window_*`，不含配息與匯率）；配息為每單位原幣金額，`pay_date` 一律空、只有 `ex_date`；`DIV_DATE_IS_EX_DATE_VERIFIED = False` 時 `build_dividend_table` 整批 pending（現場行為 UNVERIFIED）。
- 門檻都是使用者設定，不是 SSOT 常數，唯一寫死的是淨值過期 10 天（`ui_v2/thresholds.py`）；設定 JSON 的形狀由 `ui_v2` live 層自訂，不在 L2。
- ui_v2 配息表欄名「入帳日」與 `79 §17.3` 衝突，New UI2 不得沿用。
- Preview 執行期守衛（`tests/ui_v3/test_ui_v3_preview_not_formal_guard.py`）規定 import 全部 ui_v3 後不得載入 `services.v2_tables`；模組層 import `alo_holdings`／`nav_dividend` 的 adapter 會令它轉紅，而目前沒有載入端 composition root（G-2）。
- ui_v3 第一階段唯讀（`KNOWN_WRITE_FUNCTIONS` 含 `save_setting_for_page`）；💼 沒有合法寫入面設定目標、容許帶、基準。
- `rules.resolve_precedence` 的 docstring 明文 BL-0411 修好前不得接進頁級燈；`shared/ui_semantics/rules.py` 目前無 `no_holding`／`partial`／`normal` 的核准字樣。
- UNVERIFIED：兩頁同鍵合併規則在同鍵不同幣別以外的實務差異（稽核只用合成資料驗過 ccy 情境）；`skipped_holdings` 中文原因與 `80 §3.1` 的 reason_code 鍵落差由誰補；ui_v3 側完整欄位契約（需核准後的實作批驗證）。


## 9. 💼 390／1280 精細線框與逐卡 Data × Evidence Contract（ChatGPT 設計提案；2026-11-04；~~**未核准**~~ U1～U5 UI 設計已核准〔DEC-2026-11-04-02，見 §9.8〕，其餘仍待裁示）

> **文件角色**：延續第 0.1 節已核准的「主圖優先、四格後置、資料不足明確 Missing」，~~其他版面與顯示選型皆為待客戶裁示的設計提案~~（已由 DEC-2026-11-04-02 取代：U1～U5 UI 設計已核准，僅 UI；其餘版面細節與 G-1 技術承接仍待裁。原文保留）。**非產品核准、非 technical PORT、非實作授權**。本節不修改 §8 已稽核的程式事實；若本節與 §8 衝突，回到已核准正式契約，不能由 UI 便利性覆蓋。其他 Q1～Q15／BL-0542 G-1～G-5 仍未裁。

### 9.1 Information architecture 與元件識別

- **第一層：決策入口**：頁級來源／評估狀態（A00）、配置主圖／降級卡（A10）、四項摘要（A20）、偏離／未評估入口（A30）；只能顯示已核准 domain 結果，不產生行動指令。
- **第二層：有價值的詳細資料**：近期配息資訊（A40）、全部持倉（A50）、逐檔 NAV／配息／區間報酬（A51）、成本／市值與分組明細（A52）。沒有 Top N 截斷。
- **第三層：資料證據與設定指引**：來源／缺值／失敗／skipped（A60）、成本／市值基準／使用者設定之唯讀對照（A61）、註記／門檻出處（A62）。未來完整 OneBrain Digest 是另一輸出投影，不由本頁畫面反推。
- **共享 Shell**：沿用現行 ui_v3 navigation／Status Bar；不假設能連接刷新資料流程，禁新建 refresh pipeline。

### 9.2 390px Mobile（~~僅「主圖在前」方向已核准；其餘版面皆候選~~ 已由 DEC-2026-11-04-02 取代：U1～U5 UI 設計已核准，其餘版面細節仍待裁；原文保留）

```text
┌────────────────────────────────────┐
│ 共用 Shell／狀態文字（不造新計數） │
│ 💼 我的資產                        │  A00：狀態／未評估、來源
│ <既有正式可證的狀態或 Missing>     │  沒有合法 β 就不顯示 β 結論
├────────────────────────────────────┤
│ 資產配置｜實際 vs 目標             │  A10
│ [圖表 OR 缺值／取數失敗狀態卡]     │  不畫空軸、不造 100%（見下 FX 註）
│ [SPEC：成本／市值、單位、時間等]   │  SPEC 上方／緊鄰主圖；確切排版待核
├────────────────────────────────────┤
│ 總資產            │ 損益           │  A20 固定四格；Missing 也佔位
│ ◇ 資料未備        │ ◇ 資料未備     │
│ 報酬              │ 期間配息       │
│ ◇ 資料未備        │ ◇ 資料未備     │
├────────────────────────────────────┤
│ ▸ 偏離／未評估與查看明細           │  A30；不是再平衡交易動作
│ ▸ 已核實配息／近期事件             │  A40（~~位置候選，待 Q3~~ U1 已核准位置）
│ ▸ 完整持倉與單檔 NAV、配息         │  A50／A51
│ ▸ 配置明細／類別分組               │  A52
│ ▸ 來源、缺項、完整證據             │  A60／A61／A62
└────────────────────────────────────┘
│ 共用底部五格導航（不可遮蓋內容）   │
```

- **首屏**：390px 的實際裝置高度尚未提供，**不能宣稱 A20 四格一定全在不捲動首屏**。不以固定像素高度作已核准契約。設計時至少保證「頁級狀態＋主圖入口」先出現；核心數字／chip 的總量（包含 Missing 佔位）依 frozen 44 ≤5 逐 DOM／視覺兩套驗收。保守讀法（待線框逐元素點數確認；frozen 44 字面是頁級主數字＋chips ≤5、一張卡算一個，Missing 佔位是否計入屬讀法，A10 SPEC／primary_chips 是否計入亦待確認）：狀態 chip 1＋四格佔位 4 可能已耗盡名額，**額外注意 chip 不得任意加入**；注意資訊可用既有正式文案在不增名額的單一摘要容器呈現，是否合約允許尚待 wireframe 驗證。
- **主圖可用時**：僅投影同一口徑的 ALO-2 類別實際值／目標值／偏差與已設定容許帶；長類別名稱可換行，不截掉任何持倉。圖的設計方向為「每類別兩值比較條」而非跨幣別資產金額堆疊，~~**但具體圖型仍待客戶核准**~~（已由 DEC-2026-11-04-02 取代：U2 並列橫向條已核准；原文保留）；沒有正式分類或來源不可臆造。
- **主圖不可用時**：A10 位置保留，顯示現有核准詞彙下的失敗、未設定或 Missing，並在可追溯明細保留原因；不得以示意數字、灰色空軸、預設目標 0 或不完整 100% 冒充完整比較（新要求；現行 _build_alo2 行為相反；~~屬 BL-0542 G-1 Decision Gate，不代裁~~（已由 DEC-2026-11-04-02 取代：UI 呈現（方案 A）已核准，僅 UI 設計；G-1 技術承接仍待裁；原文保留）。
- **FX 現況註記**：上列「不畫完整 100%」與 §9.4 A10／§9.5 的相關禁令，**此為新要求；現行 `ui_v2/alo/logic.py::_build_alo2` 行為相反**（缺 USD 匯率時該類別值為 None 並寫「合計未涵蓋 <類別>」，分母只加總有值類別，其餘類別照算且可顯示 100%）；~~採用與否為 BL-0542 G-1 的 Decision Gate 項，客戶未裁，本節不代裁~~（已由 DEC-2026-11-04-02 取代：UI 呈現（方案 A）已核准，僅 UI 設計；G-1 技術承接仍待裁；原文保留）。
- **SPEC**：基準（成本／市值）、計價單位／百分比、已涵蓋持倉範圍、資料有效日與來源。SPEC 的**內容分類**沿用 80 §16.1，確切字樣只取現有正式 SSOT。沒有值時顯示缺項而非「最新」。
- **閱讀路徑**：A30「查看偏離明細」是展開控制，不是下單／建議；A50 按基金可進單檔展開，無新導航頁。~~A40 的排位、事件種類仍待裁示；此處不是默認客戶核准。~~（已由 DEC-2026-11-04-02 取代：僅 UI 設計；G-1 技術承接仍待裁；原文保留：U1 排位已核准；事件種類與日期語意仍待 G-3 裁示。）

### 9.3 1280px Desktop（布局候選）

```text
┌ 共用 Sidebar/Shell ──┬───────────────────────────────────────────┐
│ 五頁導航／狀態       │ 💼 我的資產｜來源／頁級判讀 A00         │
│                     ├──────────────────────────┬────────────────┤
│                     │ 資產配置主圖 A10         │ 已核准依據摘要 │
│                     │ [主圖 OR 狀態卡]         │ （不造 rule）  │
│                     │ SPEC／分母未涵蓋揭露     │                │
│                     ├──────────────────────────┴────────────────┤
│                     │ 總資產｜損益｜報酬｜期間配息 A20          │
│                     ├──────────────────────────┬────────────────┤
│                     │ A30 偏離／未評估         │ A40 配息事件   │
│                     ├──────────────────────────┴────────────────┤
│                     │ A50 全列持倉／A51 NAV 配息／A52 配置明細 │
│                     │ A60～A62 來源證據與唯讀設定              │
└─────────────────────┴───────────────────────────────────────────┘
```

- 共用 Shell 左側；主圖為視覺主角，A20 四格**在主圖之後**（不把四格移到主圖上方或側欄置頂）。桌機兩欄只屬設計提案，不是設計 Token 或 grid breakpoints 的新裁示。
- 桌機保留 80 §7.2 的「基金占比／各檔區間報酬」能力，優先整合於 A51／A52，不因視覺收斂而刪功能。這些圖若缺合法計算，顯示缺值且保留對應資料證據，不畫假圖。
- A40 若佔右欄，只能顯示已驗證日期的資訊；不以「預計入帳」冒充 pay_date。~~未核准配息排位前右欄也可僅留 evidence／限制，不必建空卡占位。~~（已由 DEC-2026-11-04-02 取代：僅 UI 設計；G-1 技術承接仍待裁；原文保留：U1 允許桌機右欄呈現但不得壓過主圖；事件內容仍受 G-3 限制。）

### 9.4 每張卡的來源／欄位／轉換／Missing／Evidence 映射

| ID | UI 資料需求與可用欄位（不得臆造 output） | 目前函式／來源（已稽核 §8） | Domain／顯示契約、必須 Gate | Missing／Evidence |
|---|---|---|---|---|
| A00 | holding、policy、skipped_tabs、skipped_holdings、source failure、active sheet 狀態及 HLD／ALO 結論 | `alo_holdings.load_alo_tables_active`；判定在 `ui_v2/{hld,alo}/logic.py`、`ui_v2/asset/page_status.py` | β 組合尚不可合法接 ui_v3（G-1、BL-0411）；`is_no_active` 尚在 `ui_v2/active_gate.py`（G-1）。未 PORT 時只顯示確實可追溯的 source 狀態，不宣稱已評估全部 | 區分未選 Active、來源讀取失敗、空持倉、部分略過；保存原始來源時間與略過證據；無 UI traceback |
| A10 | holding.bucket、cost_twd、units_shares、NAV、FX；`alo_target_weights`、`alo_basis`、`alo_bucket_names`、`alo_tolerance_pp` | 原子 `services/v2_domain/holdings.py`；組合 `ui_v2/alo/logic.py::_build_alo2` | 成本或市值依使用者設定，不能在 UI 選預設；組合必須 G-1 PORT 且 G-2 解執行期守衛；`FX_OBS_DATE_RULE_VERIFIED=False` 時不能假設市值合法。不得把排除缺值後所得 100% 當全持倉 100%（此為新要求；現行 `ui_v2/alo/logic.py::_build_alo2` 行為相反（缺 USD 匯率時該類別值為 None 並寫「合計未涵蓋 <類別>」，分母只加總有值類別，其餘類別照算且可顯示 100%）；採用與否為 BL-0542 G-1 的 Decision Gate 項，客戶未裁，本節不代裁） | 每類別 actual／target／差額 pp／band 狀態／completeness 與排除數；若採用該新要求，則無完整分母時須清楚揭露（若規格不夠先降級，不畫看似完整配置圖）（新要求；現行 _build_alo2 行為相反；屬 BL-0542 G-1 Decision Gate，不代裁） |
| A20-1 | 總資產：跨持倉彙總所需計價日、基準、換匯 | `ui_v2/asset/overview.py::summary_strip`＝Missing | G-4 未核准前**不計、不顯示假總額**；`cost_twd` 不是市值，不拿來冒充總資產 | 固定佔位；Missing 原因引用 G-4；Digest 不把 Missing 寫成 0 |
| A20-2 | 損益：本金、估值、幣別、期間及已核准公式 | 同上（目前沒有可用正式算法） | G-4；不假設舊 `portfolio_returns` 等價於 44 的損益口徑 | Missing；保留底層有合法來源者及其日期／計價單位 |
| A20-3 | 報酬：需釐清價格報酬 vs 總報酬／組合報酬、是否含 FX 與配息 | `services/v2_domain/nav_metrics.py::return_pct` 為 NAV 價格報酬原子；組合總報酬未核准 | G-4；不能把逐檔 NAV 價格報酬直接當組合總報酬 | Missing；正確的金額／% 單位及期間仍需裁示 |
| A20-4 | 期間配息：已確認 ex_date、每單位原幣、單位數、幣別與區間 | `nav_dividend.build_nav_dividend_tables`；既有 HLD-3 組合在 `ui_v2` | G-1／G-3／G-4、BL-0534；日期與期間配息彙總口徑未核准前固定 Missing | 無證據不能報 0 或「無配息」；`pay_date` 恆為 None（未提供） |
| A30 | HLD-1 逐檔偏離、ALO-2 類別與門檻、未評估原因 | `v2_domain/deviation.py` 原子；完整 `ui_v2/hld/logic.py::deviation_rows` 與 ALO page model | G-1；用已生效的使用者門檻，不從 UI 新建門檻；動作只有「展開」 | 未設定門檻 ≠ 未觸發；保留 rule source、threshold reference、不可評估明細 |
| A40 | `dividend` 的 `fund_code, ex_date, pay_date, div_per_unit_orig_ccy, ccy, div_kind, fetched_at`（**無 record_date/status，pay_date 目前 None**） | `services/v2_tables/nav_dividend.py`；`services/dividend_calendar.py` 不在 ui_v3 白名單 | G-3、BL-0534；已發生除息資料僅在 L2 真正合法可用時顯示；「推估基準日」不得當「預計入帳」 | Date semantics、原幣、資料取得日分欄保存；當取數 gate 關閉，不造已發生事件 |
| A50 | holding_id、fund_code、holding.bucket、cost_twd、units_shares、ccy 及其可用來源 | `alo_holdings.build_alo_tables`、`v2_domain/holdings.py` | 身份、同鍵合併規則 HLD vs ALO 差異（Q10）先 Gate；不能憑基金名合併；只讀、全列 | 另存 skipped_holdings、skipped_tabs，表層不把失敗說無持倉 |
| A51 | 單檔 NAV 日期／淨值點、配息逐筆、已核准區間指標 | `nav_dividend.build_nav_dividend_tables`、`v2_domain/nav_metrics.py`；逐檔組列仍在 `ui_v2/hld/logic.py` | G-1／G-2；NAV not-ready 10 天語意移植未批准；來源點被扣下不重建 | 每檔獨立來源、日期、幣別、缺值與扣下原因；不補日期 |
| A52 | ALO-6 歸屬明細、類別比例、已核准分類與使用者基準 | `ui_v2/alo/logic.py::_build_alo6` 尚待 PORT；`alo_holdings` 原料 | G-1；使用者未分類不得假定某類；完整來源與分母揭露 | 總體比例缺項不可藏在 100%；不丟未歸類原始資料 |
| A60 | 未取得／失敗／略過／未讀／未設定／unknown currency 與來源診斷 | L2 `alo_holdings`／`settings_store`、`ui_v2` source；`ui_v3/viewmodels/common.py` 五態 | G-5、BL-0540：只用核准 human-readable vocabulary；`skipped_holdings` 為中文字串而非 reason_code，轉換仍未核准 | 對一般 UI 遮蔽 secret／traceback，診斷預設收合；來源健康在 ⚙️ 詳細承接 |
| A61／A62 | `alo_*` 四個設定鍵（target、tolerance、basis、bucket_names）；區間鍵、threshold reference、來源時間 | `settings_store.load_user_settings`（SETTINGS_SHEET_ID）、既有 HLD／ALO 契約 | New UI2 第一階段唯讀；沒有合法寫入端；User setting 不因 Active Sheet 改切而跟著換；版面標示設定來源 | 未設定與取數失敗分開；不暴露 private Sheet ID／credential |

> **Mapping 的完整度**：本表為設計至已稽核 function 的 mapping，**不是逐欄已通過的 machine schema**。尚缺每個 L2 output 的 return path／型別／source／as_of／retrieved_at／status reason_code 的實際契約與跨頁 golden；不應以本表直接生成 Python。精確 schema 仍以 §8 與核准後獨立實跑 trace 為準。UI 沒顯示的正式 evidence 也不能從 future Digest 移除。

### 9.5 Missing、Freshness、幣別及資料健康矩陣

| 情境 | 第一屏 A00／A10／A20 | 明細與 Evidence | 禁止的誤解 |
|---|---|---|---|
| 沒有 Active Sheet | A00 反映「尚未選定來源」之核准語意；主圖及四格無值 | 可提示既有來源選擇路徑，但無合法一鍵改 Sheet 時不造按鈕 | 不說「持倉 0」，不 fallback 到別的 Sheet |
| Source 整體讀取失敗 | A00 失敗；A10 卡片降級；A20 Missing | A60 留錯誤分類，遮蔽機密與 raw trace | 不以「空持倉」代替失敗 |
| 一部分 worksheet skipped/unread | 第一屏不能出現虛假的完整結論；A10 覆蓋不足時降級／註明不可完整 | A50 保留可用列，A60 完整提示略過／未讀證據 | 不依可讀列算全持倉百分比 |
| 真正空持倉（資料完整才可判） | 不能用零值編造四格；A10 缺可比較類別 | A60 證明資料源確實完整且無有效列 | skipped all ≠ zero holdings |
| `alo_basis` 未設定 | A10 顯示未設定的核准狀態；四格仍 Missing | A61 顯示唯讀設定缺項 | 不自行預設成本 |
| 市值缺 USD/TWD 或其他必要 FX | A10 不可畫看似完整的 100%（~~新要求~~ 已由 DEC-2026-11-04-02 方案 A 核准 UI 呈現；現行行為相反，見 §9.2 FX 現況註記；G-1 技術承接仍待裁）；四格 Missing | A60 記載排除基金與未涵蓋基準金額 | 不自動改用成本、不說債券佔全組合 100% |
| NAV 缺點／超過 10 天 | 依現行 `ui_v2` 常數 `NAV_NOT_READY_DAYS=10` 之語意處理（移植語意未批准，見 A51／G-1）；主圖僅取合法用來計算的資料 | A51 保留觀測日、取得日與扣下原因 | 不補 0、不另創或擴大 freshness 門檻 |
| 設定讀取失敗／門檻未設定 | A00 不假裝「安全」，A10 顯示不可判讀或未設定 | A61 保留設定失敗或未設之區別 | not configured ≠ neutral |
| Dividend gate pending／無日期語意 | A40 不宣稱確認配息；A20-4 Missing | A60 留取得失敗與日期欄位的狀態 | `pay_date` 為 None 不得讀成入帳日或預計入帳；空列 ≠ 無配息 |
| 同鍵身份衝突或同鍵不同 ccy | 依正式 identity fail-closed，不合併成一檔 | A50 保留衝突來源作資料診斷 | 不以同名、相近字串自動合併 |

- **新鮮度**：每個欄位層級區分 `as_of/obs_date`（資料涵蓋時點）、`fetched_at/retrieved_at`（取得時點）與來源聲明。尚未正式裁示的 stale threshold 不自行開啟，也不拿 render timestamp 當市場資料時間。
- **匯率**：跨幣別金額缺任何必要 FX，就標註不可完整計算；不可把被排除的基金從分母靜默移除、又顯示「100% 完成」。**此為新要求；現行 `ui_v2/alo/logic.py::_build_alo2` 行為相反**（缺 USD 匯率時該類別值為 None 並寫「合計未涵蓋 <類別>」，分母只加總有值類別，其餘類別照算且可顯示 100%）；~~採用與否為 BL-0542 G-1 的 Decision Gate 項，客戶未裁，本節不代裁~~（已由 DEC-2026-11-04-02 取代：UI 呈現（方案 A）已核准，僅 UI 設計；G-1 技術承接仍待裁；原文保留）。
- **配息**：顯示以正式 date semantics 及實際可用 L2 為前提；ex_date、配息基準日、pay_date、平台入帳日是不同概念，不能合併命名；「正式日期優先、deterministic estimate fallback」尚未落實，不作現況宣稱。
- **配息日期補註**：79 §17.3／BL-0534 的 `payment_date`（基金端正式發放日）與 `estimated_bank_credit_window`（預估銀行／平台入帳區間）是不同概念，皆不等同現行 `pay_date`；「近期事件」只含 L2 已提供的列，L2 會丟台灣今日之後的列，故不含未來事件。
- **摘要標籤**：程式現行標籤為「總資產、總損益、報酬、配息」；本節的「損益／期間配息」是簡稱，非新增字樣。
- **語意字樣**：使用 `shared/ui_semantics/rules.py` 已核准詞彙；上表敘述只說明意義，**不是核准新文案**。

### 9.6 Three-path design & build decision（路徑 X／Y／Z；本輪只選設計，不核准程式）

| 路徑 | 正確性 | 速度／Token | 決策 |
|---|---|---|---|
| X. 直接照 UI 草圖填字／做圖，留公式交 Claude 臨場決定 | 高風險，會重複判定及藏 Missing | 表面最快、返工成本最高 | 不採 |
| **Y. 先正式逐卡 contract 與降級 wireframe，等 G-1～G-5 Gate 後分階段 PORT 與 ViewModel** | **低風險、可驗收、符合分層** | 單一 SSOT，總 Token／返工較低 | **推薦（僅設計路徑）** |
| Z. 本輪先要求全部資料源、公式、OneBrain 一次上線 | 未授權跨模組高風險 | 最慢、需要 High／完整 QA | 不採 |

> 註：§9.6 路徑 X／Y／Z 為設計路徑，與 §4 的 A／B／C 及 P1～P5（PORT 路徑）不同；Y 不等於 §4 的 B0，與「B0 不需新 Gate」並存，不改 §4 的最小成本路徑結論。


### 9.7 設計事項 U1～U5（✅ 2026-11-04 已核准；僅 UI 設計；與 §4 的 P1～P5 無關）

1. **U1**：390px 配息／近期事件放 A30 偏離摘要之後、全部持倉之前；1280px 允許右欄（但不要壓過主圖）。
2. **U2**：配置主圖使用「類別實際 vs 目標」**並列橫向條**，若採用該新要求，只在有完整合法 category denominator／target／basis 時畫（新要求；現行 _build_alo2 行為相反；~~屬 BL-0542 G-1 Decision Gate，不代裁~~（已由 DEC-2026-11-04-02 取代：UI 呈現（方案 A）已核准，僅 UI 設計；G-1 技術承接仍待裁；原文保留）；不具備時以狀態卡保留位置，完整依據放展開區。
3. **U3**：首屏 A00 使用單一正式狀態容器，A10 SPEC 簡潔列；四項摘要仍是四個 slot，**不得把注意 chip 再加一個使名額突破 5**。真正高度、Status Bar 字句名額與降級情境另以真實 390px／1280px 像素實測。
4. **U4**：持倉完整清單及單檔 NAV／配息在 A50／A51 展開，完整類別歸屬與使用者設定在 A52／A61，UI 精簡不影響 OneBrain Evidence。
5. **U5**：尚未合法接入的 β、四格公式、配息推估、status wording 不因採這套版面自動放行，仍按 BL-0542 Gate 決定。

**本節 Design Gate（DEC-2026-11-04-02）**：客戶已核准 §0.1 方向及 **U1～U5 全部 UI 設計事項**；BL-0542 G-1～G-5 仍待各自核准後才可實作，Q1～Q15 中尚未被此狹義 UI 裁示涵蓋的事項仍待決。專案 AI 只可獨立稽核本節的引用／資料來源／與 frozen 契約是否一致，不得因 merge 自動做 Python／Streamlit。正式實作前應再補逐欄 L2 schema／fixture／測試與必要 Decision Gate 結果；新口徑、新公式與新增文字一律停止待裁。

### 9.8 客戶裁示：U1～U5 與缺 FX 方案 A（DEC-2026-11-04-02）

> **要點轉述（轉述者：ChatGPT，經 #1144 PR 載明；非逐字）**：「U1～U5 全部採用 ChatGPT 建議，僅核准 UI 設計，G-1～G-5 仍須分別處理。缺 FX 顯示百分比選 A：不顯示可能誤導的完整 100%，改顯示資料未備與未涵蓋範圍；依此落盤，不直接授權程式實作。」逐字內容見 `docs/evidence/decisions/2026-11-04_assets_u1_u5_fx_ruling.md`。

| 項目 | 已核准的 UI 設計 | 未授權的部分 |
|---|---|---|
| U1 | 手機配息／近期事件排在偏離摘要後、全部持倉前；桌機可於右欄呈現，不得壓過主圖 | 配息推估、日期語意仍依 G-3／BL-0534 |
| U2 | 主圖採「類別實際 vs 目標」並列橫向條；只有 denominator、target、basis 合法且完整才畫，否則顯示資料狀態卡 | G-1 PORT／新公式與 G-2 runtime guard 未核准 |
| U3 | A00 單一正式狀態容器、A10 簡潔 SPEC、A20 四格保留；不得增加額外注意 chip 突破 ≤5 | 尚未證明 β 已合法接入或 390／1280 首屏實測通過 |
| U4 | A50／A51 完整持倉、逐檔 NAV／配息可展開；A52／A61 類別歸屬與唯讀設定；UI 簡化不刪完整 Evidence | OneBrain Digest／Phase 7 未啟用 |
| U5 | β、四格公式、配息推估、status wording 未經 Gate 前不啟用 | G-1～G-5 不因 UI 核准自動解鎖 |
| 缺 FX 方案 A | 必要 FX 不足而使配置分母不完整時，**不可顯示看似涵蓋全部資產的 100%**；改以已核准 Missing 語意顯示「資料未備」與未涵蓋範圍，已驗證的原始資料與明細仍完整保存 | **僅是 New UI2 呈現裁示**，不是修改配置公式、定義匯率門檻、動 ui_v2 或自動從市值改成本 |

**已知程式與裁示差異**：現行 ui_v2/alo/logic.py::_build_alo2 在缺 USD 匯率時可因分母僅納入有值類別而顯示 100%，同時註記「合計未涵蓋」。此舊行為目前仍在；本次不修改它，不授權在 ui_v3 自行重算或默默扣除基金。**BL-0542 G-1 仍待獨立技術／資料語意 Gate**，G-2～G-5 亦然。

**其他邊界**：U1～U5 設計已核准不等於 390px／1280px 實際版面與首屏驗收完成。Q1～Q15 中獨立的欄位／資料／日期／跨頁語意 Gate 繼續保留；未經核准之公式、資料來源、狀態詞、Risk Cap、System Action 與 OneBrain 仍不得新增或啟用。

## 10. 2026-11-06 客戶新增：健康原評級、覆蓋率與正式資料准入分開呈現（DEC-2026-11-06-02）

> **位階**：使用者已核准**展示方向**（逐字於 `docs/evidence/decisions/2026-11-06_new_ui2_top_tabs_health_coverage_ruling.md`）；本節補足 💼 頁未施工的 Data × Evidence 顯示要求。不是更動正式評級公式、權重、門檻、FX 來源、Risk Cap、准入政策或 Phase 7 的授權；原 U1～U5 UI 核准範圍不擴充為 renderer 授權。

### 10.1 3 個獨立欄位群，不可混成「健康」

| 顯示群 | 資料責任與來源 | 未取得時如何處理 |
|---|---|---|
| **原始健康指標及原字母 Grade** | 沿用已驗證 `services/health/grade.py::compute_4d_health` 等既有 Domain 計算結果，不在 UI 重算；保留五維各自的 raw evidence、期間、原值、原模型版本 | 原本無值就維持 Missing；**不得因缺資料改造新 Grade**，也不自行修改評級切點 |
| **資料覆蓋率** | 各基金適用維度數 `n_applicable`、合格可計分維度數 `n_scored`、各缺項 reason/source/as_of/window；TWD 的 FX 維度若不適用應區別 N/A；完整原始持倉與 skipped/failed 仍在 Evidence | 無法算分母就顯示無法取得／尚未評估，不得寫 `0/5`；不把 `2/5` A 視為完整 A |
| **正式資料准入狀態** | 另由經核准的 deterministic data-validity／coverage Gate 判定能否將健康結果用於**正式品質判斷**；需引用所用規則版本與 evidence | **尚未有核准准入準則時不得顯示通過或安全**；使用已核准 Missing／無法判定語意，不自創 `safe`／`passed` 詞彙；此准入不是 OneBrain／Phase 7 action Gate |

### 10.2 現有資料覆蓋的已知事實與待實測（PR #1157）

- `compute_4d_health` 實際評估 coverage、Sharpe、trend、volatility、FX risk **五個維度**；至少兩維加一核心維（配息 coverage 或 Sharpe）即可有原 Grade，故 Grade 的資訊強度**必須**附上覆蓋率。
- `services/fx_regime_service.py` 目前只支援 USD 歷史 FX volatility provider；非 USD 的其他外幣只能標現有提供器 unsupported，**不是永久抓不到所有外匯數據**。TWD 對該外幣風險維度屬 N/A。現行健康報表 `ma_dir=None`，不能宣稱已評估 MA60 方向。
- Sharpe 若混 6M／1Y、TER 只曾在歷史兩檔樣本 0/2、規模單位不統一、NAV／配息期間不足等，全部是**來源有效性或可比性問題**，不得武斷當作永久缺數。spot FX 是否抓得到，也不證明歷史 FX 波動可計分。
- 現時未有使用者 Active Sheet **全部唯一基金**的逐維合格覆蓋率。實測需保留原始保單持倉列，在 canonical 身份確認後才按基金去重，並列出全體唯一基金／來源成功抓取／該維適用三個分母及 skipped／failed／missing／stale／conflicted 分類。
- 原有「配息含本金」官方披露與模型 proxy 必須分開；「市場全面下跌」與「基金相對品質下降」也必須分軸分析，未核准同類 benchmark 前不得用單檔負報酬當成品質壞。

### 10.3 UI 設計候選（仍須完整 💼 線框及正式文案 Gate）

- 手機在既有 A50/A51（完整持倉）中依經驗證基金身份聚合行、可展開全部保單／部位。每檔顯示原 Grade／有效維度數／正式准入結果三項**互相獨立**；查不到的項目不可消失或擠成同一顏色。
- 單檔詳細 Evidence 能展開五維原值、來源日期、Missing 原因與完整部位，不因主畫面簡化而刪除或阻斷未來 Decision Digest。
- 與客戶同日的手機頁首橫向五頁籤選型（`DEC-2026-11-06-01`）一併遵守 `docs/v2/80` §18；**frozen 44 合法 amendment 未完成前不能把此段當作新 Shell 已上線**。
- G-1～G-5 及其餘 Q 類財務／資料／狀態語意 Gate 仍然未裁。健康資料准入規則的數值門檻需另行客戶裁示，這份文件不提供任何建議升格或自動交易決策。

**資料可靠性審查待辦**：`docs/BACKLOG.md` BL-0545；靜態來源 #1157；現有舊規格中單一 Grade 直接被理解為全面健康的對話推論視為 **NOT CURRENT**，保留原始證據以供查核。
