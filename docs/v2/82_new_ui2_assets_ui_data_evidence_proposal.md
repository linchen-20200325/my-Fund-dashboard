# 82｜New UI2 💼 我的資產：UI × Data × Evidence 施工前設計草案（U1～U5 UI 設計已核准〔DEC-2026-11-04-02〕；其餘仍待裁示）

> **定位**：ChatGPT 產品／資料契約初稿，2026-11-04（區塊順序已由 DEC-2026-11-04-01 核准主圖在前，見 §0.1；其餘仍待核准；~~U1～U5 仍待核准~~ 已由 DEC-2026-11-04-02 核准 UI 設計，見 §9.8）。**非已核准 wireframe、非公式或資料語意裁示、非程式實作授權**。此檔不取代 frozen `44`、`79`、`80`、`73`、`74`；同一事實以原正式契約為準。**區塊順序以 §0.1／`DEC-2026-11-04-01` 為準，其餘仍以 `80`／`44` 為準。**先驗既有 capability／欄位，再由客戶核准具體版面。不得因本草案把舊 UI 程式直接搬入 `ui_v3`。
>
> **讀碼範圍**：`services/v2_tables/alo_holdings.py`、`services/v2_domain/{holdings,deviation}.py`、`services/v2_tables/nav_dividend.py`、`ui_v2/{hld,alo}/{source,logic}.py`；對照 `docs/v2/{73,74,79,80}_*.md`。此為 ChatGPT 單組盤點，**尚未由獨立組逐欄複驗**。
>
> **2026-11-04 專案 AI 獨立稽核（單組、三份獨立報告；非客戶裁示）已核實 §2／§4 的主要敘述**：結果見第 8 節；§2、§4 內以【稽核更正】標示就地修正處，ChatGPT 原文保留（錯的字句加刪除線）。本檔仍**非規格**；~~待客戶核准草案~~（U1～U5 UI 設計與缺 FX 方案 A 已核准，僅 UI；其餘 Q／G 仍待裁示；見 §9.8）；主圖資料欄位、公式、狀態詞與 Gate 的登記位置為 `docs/BACKLOG.md` BL-0542，本檔不重複成文；本檔內「G-n」一律指 `BL-0542 G-n`（與 BL-0538、BL-0540 各自的 G 編號不同、互不相通），「Q7～Q15」為本檔 §6.1 的問題編號（BL-0542 沿用，非 BACKLOG 全域編號）。以下「候選接線」不保證已存在 New UI2 可直接調用的 facade；實作組必須在核准後驗證精確 schema。


> **2026-11-09 增補（不改上列任何句）**：§11 為 💼 New UI2 線框草稿（390／1280、缺 FX 時原幣可查看、舊能力差距表；客戶選「線框＝A」，停在客戶 UI Review Gate）；§12 為健診「資料涵蓋 N／M 檔」呈現草稿（只提候選）。使用者面一律稱「淨投資金額」，不稱「成本」（見 §11 開頭）。

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
2. **390px／1280px**：首屏能讀狀態、是否需注意與必要數字；符合 44 既有 budget；無橫向捲動、底部導覽不遮內容；顏色非唯一載體。〔2026-11-09 就地標記：現行 Shell 為頁首五格、不吸頂，見 §11.9.7；原句保留〕
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
│ 共用底部五格導航（不可遮蓋內容）   │ 〔2026-11-09 就地標記：現行 Shell 為頁首五格、不吸頂，見 §11.9.7；原句保留〕
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

## 11. 2026-11-09 New UI2 💼 我的資產線框草稿（客戶選「線框＝A」；設計草稿，非核准最終線框、非 UI 施工授權）

> **位階與來源**：客戶 2026-11-09 裁示（派工單轉述；**要點轉述，非逐字**；~~repo 內尚無逐字存檔，`docs/DECISIONS.md` 登記由另組同批處理，登記後以該 DEC 編號為準~~（2026-11-09 更新，有意識，非漏刪：已登記為 `DEC-2026-11-09-01`，以該 DEC 為準）：D2-A＝B、D2-B＝收緊 C、D2-C＝B；「淨投資金額」語意＝B；💼 線框＝A。D2-A／D2-B／D2-C 各選項的內容由 `DEC-2026-11-09-01` 載明，**本檔不轉述、不引申**；本節只落實下面兩件事：
> 1. **使用者面名稱**：一律稱「**淨投資金額**」，不稱「成本」；`cost_twd`、`cost_orig_ccy` 僅是內部既有欄名。淨投資金額**不視為**總市值、本金、已實現損益基礎或配置分母。本檔 §0～§10 與 `docs/v2/44`、`73` 內既有的「成本」是當時寫下的內部名稱，**不改寫、不逐處更正**；New UI2 使用者面讀作「淨投資金額」。
> 2. **線框＝A**：先規劃新版 390px／1280px 線框草稿供客戶審；**不是**核准最終線框，**不授權**任何 Streamlit／`ui_v3` 實作。
>
> 已核准的 UI 方向（`DEC-2026-11-04-01`／`-02`、§0.1、§9.7 U1～U5）、`PROJECT_RULES.md` §13.5（人類 UI 呈現）、§13.6（Legacy Capability Review Gate）照舊；BL-0542 G-1～G-5、DIRECT 持倉、NAV 10 日、組合市值損益、正式配置分母、跨新版 1Y 含息仍是**原 Gate**，本節只標「待裁示」、不代裁。本節不新增資料來源、公式、門檻、狀態詞、API，不動任何程式。
> ⚠️ **本節為設計文件組單組撰寫（作者），未經獨立 QA**；讀碼未實跑，390／1280 像素與首屏預算為設計值、未量測（見 §11.8）。

**標記詞**：〔已核准〕＝客戶 DEC 明文核准的 UI 設計；〔待裁示〕＝本草稿提案或依賴未裁 Gate，需客戶 UI Review 或另行裁示；〔不顯示〕＝Gate 未開或無合法資料，目前不得顯示結果。

### 11.1 Legacy Capability Review Gate（`PROJECT_RULES.md` §13.6；最小必要差距表）

> 只列與本頁直接相關的能力，沿用已有盤點（本檔 §8、`docs/evidence/d2_draft_B_old_ui_to_new_ui_compare_2026_11_08.md`、`docs/evidence/d2_contract_candidates_returns_identity_holdings_2026_11_08.md`、`docs/v2/80` Reuse Matrix），不重做稽核。三條線＝線 A（Old UI 正式頁）、線 B（`ui/views` 的 `[新]` 並行預覽頁）、線 C（`ui_v2`／`ui_v3`）；另含共用的 `services/`、`repositories/`、`shared/`。線 A／B 的內容引自上列既有 evidence，本組**未重驗**。

| # | 既有能力 | 既有位置 | 可直接共用？ | 需 Domain 抽取？ | 應捨棄的舊行為 | 受限 Gate |
|---|---|---|---|---|---|---|
| L1 | 讀 Active Sheet 持倉、略過與失敗證據 | `services/v2_tables/alo_holdings.py::load_alo_tables_active`、`build_alo_tables`；`ui_v3/adapters/assets_source.py::load`（無 production 呼叫端） | 可（L2 已存在）；但沒有載入端 composition root，Preview 執行期守衛禁止模組層載入 `services.v2_tables` | 否 | 服務帳戶＋`POLICY_SHEET_ID` 的 `load_alo_tables` 路徑、任何退回別本 Sheet 的 fallback（§8；J-7／J-13） | G-2；Active Sheet 入口歸 ⚙️（BL-0540） |
| L2 | 類別淨投資金額（金額，不含占比） | `services/v2_domain/holdings.py::category_values`（`market=False`）、`allocation_evidence.CategoryEvidence`；組合版在 `ui_v2/alo/logic.py::_build_alo2` | 原子可；組合版需 PORT | 是（`_build_alo2` 的類別／分母組合） | `_build_alo2` 缺 USD 匯率仍顯示 100% 且分母只加總有值類別（與方案 A 相反，§9.8） | G-1；D2-C；淨投資金額語意（不是分母） |
| L3 | 缺值原因與來源完整性證據 | `services/v2_domain/allocation_evidence.py::build_allocation_evidence`（`SourceFacts.source_coverage`、`CoverageFacts.uncovered_*`、`UNPROVEN_ZERO`） | 可（內部候選名稱，非核准詞彙） | 否 | 把讀取失敗或略過畫成空持倉、把來源不完整時的 0 當作「沒有這類」 | G-5；BL-0542 的 11 項 open gate |
| L4 | 逐檔淨值日期、淨值、幣別、取得時間 | `services/v2_tables/nav_dividend.py::build_nav_table`（欄位 `nav_date`、`nav_orig_ccy`、`ccy`、`fetched_at`）；逐檔組列在 `ui_v2/hld/logic.py::_build_hld5`／`_build_hld6` | 資料表可；組列需 PORT | 是（組列） | 無需捨棄的舊行為；但 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`（10 日）**不得自動沿用**為新版規則 | G-1、G-2；NAV 10 日（`DEC-2026-11-05-03`）；`NAV_HISTORY_PROVENANCE_VERIFIED=False` 時累積表的點不採用 |
| L5 | 區間價格報酬 | `services/v2_domain/nav_metrics.py::return_pct`（窗口為使用者設定 `hld_window_*`） | 原子可 | 否（逐檔走訪待 PORT） | 把舊站 1Y 含息算法（`DEC-2026-10-23-02` 1B）當作新版預設 | 跨新版 1Y 含息、報酬口徑（BL-0524）：原 Gate |
| L6 | 組合市值、損益、報酬、XIRR | 線 A：`ui/tab3_t7_ledger.py`、`services/portfolio_performance.py::portfolio_returns` | 否 | 不抽取（口徑未裁） | 缺報價時依序退 `fund.fx_rate`、帳本平均匯率的保底鏈；以 `invest_twd` 加總當「近似市值」 | G-4；`FX_OBS_DATE_RULE_VERIFIED=False`（`services/v2_tables/market_indicator.py`）；BL-0393 |
| L7 | 「已計入 N／M 檔」覆蓋揭露 | 線 A：`ui/tab3_t7_ledger.py` 的 KPI 說明；線 C：`ui_v2/sections.py::hld_count_values` 的 n／m／j | 概念可參考，原樣不可 | 視 §12 | 以「已計入」暗示整體涵蓋、分母未定義 | 見 §12；BL-0545 |
| L8 | 配息／除息 | `nav_dividend.build_dividend_table`（`DIV_DATE_IS_EX_DATE_VERIFIED=False` 時整批 pending）；`services/dividend_calendar.py`（不在 ui_v3 允許前綴） | 資料表可；推估不可 | 推估待 G-3 | 把推估基準日當預計入帳；`pay_date` 恆為空 | G-3；BL-0534 |
| L9 | 偏離比較、類別占比 | `services/v2_domain/deviation.py`（原子）；`ui_v2/hld/logic.py::deviation_rows`、`ui_v2/alo/logic.py::_build_alo2` | 原子可；組合版需 PORT | 是 | 缺值類別被排除後仍顯示完整 100% | G-1；D2-C |
| L10 | 使用者設定唯讀（目標、容許帶、基準、類別名稱） | `services/v2_tables/settings_store.py::load_user_settings`；`ui_v3/adapters/assets_source.py::parse_settings` | 可 | 否 | 任何寫入、系統代填預設 | 第一階段唯讀；BL-0542 Q9 |

**§13.6 第 4 點的最小成本正確路徑（作者推薦，非裁示）**：直接重用 L1／L3／L10 的 L2 讀取與證據物件，其餘維持 Missing；不抽取新公式、不新增第二套取數器。與 §9.6 路徑 Y、§4 的 B 路徑同向。

### 11.2 版面約束（已核准 vs 本草稿落法）

| 約束 | 依據 | 本草稿落法 |
|---|---|---|
| 手機優先設計 390px；1280px 桌面另提供 | `PROJECT_RULES.md` §13.2 提示、`docs/v2/79` 第 10 節 | §11.4、§11.5 各一套，不是同一版縮放 |
| 主圖在前、四項摘要在後 | `DEC-2026-11-04-01` | A10 在 A20 之前，兩套版面皆然 |
| 資料不足明確顯示 Missing，不填假數據；主圖不可用時保留區塊與原因 | `DEC-2026-11-04-01`、`-02` §9.8 | A10 保留狀態卡；不畫空軸、不畫假 100% |
| U1 配息位置；U2 並列橫向條且口徑合法完整才畫；U3 A00 單一容器、A10 簡潔 SPEC、四格保留；U4 展開；U5 Gate 不解鎖 | §9.7、§9.8 | 逐區塊標示，見 §11.6 |
| 首屏 chip／核心數字預算（frozen 44，`docs/v2/80` §17.2 的讀法） | `docs/v2/73` §7.2 保守讀法 | 390px 首屏：A00 狀態容器 1 ＋ 四格佔位 4 ＝ 5（保守讀法）；**不得再加任何 chip**；A10 狀態卡、SPEC 列、限制說明皆為文字，不做成 chip（待 §11.8 實測） |
| 工程資訊不進一般 UI；診斷預設收合 | `PROJECT_RULES.md` §13.5 第 3 點 | 不出現環境變數、例外、錯誤代碼、路徑；A60 預設收合 |
| 簡化呈現不減少 Evidence | §13.5 第 4 點、§9.7 U4 | 不顯示的資料仍留在 L2 與證據層 |

### 11.3 「FX 無法驗證，但原幣資料仍可查看」設計

匯率驗證閘門 `FX_OBS_DATE_RULE_VERIFIED` 維持關閉（`DEC-2026-11-08-02`）時，頁面**不換算、不合計**，但可查看有可靠證據的原始資料：

| 可呈現（有證據） | 內部欄位與來源 | 呈現限制 |
|---|---|---|
| 持有單位 | `holding.units_shares`（保單分頁「持有單位數」） | 空白或 0 的列不進持倉表、進略過清單，不補 0 |
| 持有幣別 | `holding.ccy`（使用者於保單分頁填寫） | 標明「使用者填寫」；與淨值幣別不一致時兩者並列，標「⬜ 無法判定」，不擇一（BL-0542 open gate `holding_nav_ccy_disagreement_unjudged`） |
| 淨投資金額（新臺幣） | `holding.cost_twd`（保單分頁「淨投資金額」） | 非新臺幣基金的淨投資金額仍是新臺幣欄位、不需匯率（evidence E3 K5）；**不稱成本、不當市值、不合計** |
| 已確認分類 | `holding.bucket`（`_持倉補充`「類別」，使用者設定） | 空白＝未分類，獨立呈現、不推斷；類別名稱表（`alo_bucket_names`）未設時全部歸未分類 |
| 資料來源與時點 | Active 來源狀態；`holding.last_synced_at` | 該時點是「最後核對日」當日 12:00 的**推定值**，須標「推定」，不冒充讀取時間 |
| 逐檔最近淨值、淨值日、取得時間 | `nav.nav_orig_ccy`、`nav.nav_date`、`nav.fetched_at` | 只顯示日期與取得時間，**不標示過期／正常**（10 日語意未批准）；`nav.ccy` 實務上只來自持倉手填（`nav_dividend.py` 檔頭），須標出處 |
| 逐檔資料限制 | `nav_dividend` 的 `withheld`／`errors`、`allocation_evidence` 的 `nav_state` | 以人話描述（缺淨值、幣別不一致、累積點不採用…），不顯示代碼 |

| 不可（本草稿不顯示、不推算） | 原因 |
|---|---|
| 以淨投資金額取代市值，或把淨投資金額稱作總資產／本金／成本 | 淨投資金額語意＝B；evidence N1、N7 |
| 把部分持倉的占比畫成完整 100%；任何類別占比或分母 | `DEC-2026-11-04-02` 方案 A；D2-C；G-1 |
| 使用未驗證匯率、保底匯率，或推算整體市值、組合損益 | FX 閘門關閉；G-4 |
| 逐檔原幣市值（單位數×淨值）、淨投資金額合計 | 屬新衍生值，且可能被誤讀為市值或總資產；待裁示（T4、T11） |
| 以 `cost_orig_ccy`（單位數×平均買入單位成本）呈現「原幣成本」 | 它不是淨投資金額，使用者面無核准名稱；待裁示（T3） |
| 自訂 NAV 10 日規則於新版的適用方式 | D7；`DEC-2026-11-05-03` |
| 用缺資料推斷「安全／正常／無需處理」或任何持有／賣出類結論 | Missing ≠ 正常／安全（`PROJECT_RULES.md` §13.2 第 3 點） |

### 11.4 390px 手機線框（文字線框；設計順序＝§0.1 ＋ §9.7 U1）

```text
390px（單欄；共用 Shell 與底部五格導航不在本框內，內容不得被遮蓋）〔2026-11-09 就地標記：現行 Shell 為頁首五格、不吸頂，見 §11.9.7；原句保留〕
┌ A00 〔已核准：U3 單一正式狀態容器；字樣待裁示〕
│  💼 我的資產
│  <來源狀態：已讀完／部分略過／讀取失敗／未選 Active 擇一；描述性，非核准字樣>
│  資料時點：<持倉最後核對日（推定）>
├ A10 資產配置｜實際 vs 目標 〔已核准：主圖在前、U2〕
│  [圖表區：目前一律為狀態卡]
│    ◇ 資料未備
│    原因：<配置比較所需的分母口徑尚未核准；淨投資金額不是配置分母>
│    （不畫座標軸、不畫長條、不出現任何百分比或 100%）
│  SPEC 一列：基準＝<`alo_basis` 設定值，或「⬜ 未設定」>｜金額單位＝<新臺幣（淨投資金額）／各檔原幣（淨值）>｜資料時點｜缺項
│  資料限制一行：<目前未做匯率換算，各檔原幣數值不合計>〔待裁示 T5：字樣〕
│  ~~▸ 各類別淨投資金額（金額表；無長條、無占比、無合計列）〔待裁示 T1〕~~ → 〔不顯示：T1＝B，見 §11.8〕
├ A20 四項摘要 2×2 〔位置與四格已核准；公式待裁示 G-4，值〔不顯示〕〕
│  總資產 ◇ 資料未備 │ 損益 ◇ 資料未備
│  報酬   ◇ 資料未備 │ 期間配息 ◇ 資料未備
├ A30 ▸ 偏離／未評估 〔位置已核准；偏離結果〔不顯示〕（G-1）；佔位去留待裁示 T7〕
├ A40 ▸ 配息／近期事件 〔位置＝U1 已核准；內容〔不顯示〕（G-3、BL-0534）〕
├ A50 ▸ 完整持倉（逐檔，無 Top N、不排名）〔展開已核准 U4；欄位待裁示 T6〕
│  逐檔摺疊列：基金名稱｜持有單位｜持有幣別｜淨投資金額（新臺幣）｜類別｜最近淨值（原幣）＋淨值日
│  A51 單檔展開：淨值取得時間｜淨值幣別出處｜該檔資料限制｜〔區間價格報酬：待裁示 T8〕
├ A52 ▸ 類別歸屬與使用者設定（唯讀）〔U4 已核准；內容待裁示〕
└ A60 ▸ 來源、略過、缺項證據（預設收合；不含代碼、例外、路徑）〔已核准：§13.5 第 3 點〕
```

- **首屏**：390px 實機高度尚未提供，不宣稱四格一定在不捲動首屏；保證順序為 A00 → A10 → A20。chip 名額見 §11.2。
- **A10 狀態卡**是本草稿唯一的圖位內容：在「淨投資金額不是配置分母」且「類別占比契約延後」（D2-C）的現行裁示下，**沒有合法的類別實際 vs 目標比較口徑**，故 U2 的並列橫向條**目前不可畫**；待分母口徑與目標、基準三者合法完整才畫（§9.7 U2 條件不變）。
- ~~各類別淨投資金額的**金額表**（T1）是否可佔用圖位下方，屬待裁示；若核准，表內只列金額、持倉件數與缺漏原因，缺漏類別標 `◇ 資料未備`，來源不完整時的 0 不得顯示為 0（`UNPROVEN_ZERO`）。~~ （2026-11-09 客戶第二則裁示 T1＝B，有意識，非漏刪：暫不顯示各類別淨投資金額小計，見 §11.8 T1）：A10 圖位下方**不放**金額表，主圖維持狀態卡。舊句的 `UNPROVEN_ZERO` 約束仍留作日後若重議 T1 時的前提。
- 逐檔列序沿來源既有順序，不預設排序、不加推薦字樣（frozen 44 第 1.2 節）。

### 11.5 1280px 桌面線框（文字線框）

```text
┌ 共用 Sidebar／Shell ┬──────────────────────────────────────────────────┐
│ 五頁導航／狀態       │ A00 來源狀態（單一容器）                          │
│                    ├────────────────────────────┬─────────────────────┤
│                    │ A10 主圖區（目前為狀態卡）    │ 依據摘要〔待裁示 T5〕 │
│                    │ SPEC 一列＋資料限制一行       │ 淨投資金額語意註記    │
│                    ├────────────────────────────┴─────────────────────┤
│                    │ A20 四格並列：◇ 資料未備 ×4（公式待裁示 G-4）       │
│                    ├────────────────────────────┬─────────────────────┤
│                    │ A30 偏離／未評估（不顯示結果）│ A40 配息／事件（U1） │
│                    │                            │ 不得壓過主圖          │
│                    ├────────────────────────────┴─────────────────────┤
│                    │ A50 完整持倉寬表（無 Top N、不排名）                │
│                    │ 基金名稱｜基金代號｜持有單位｜持有幣別｜淨投資金額（新臺幣）│
│                    │ 類別｜最近淨值（原幣）｜淨值日｜淨值取得時間｜資料限制     │
│                    │ A51 單檔展開／A52 類別歸屬與設定（唯讀）              │
│                    │ A60 來源、略過、缺項證據（預設收合）                  │
└────────────────────┴──────────────────────────────────────────────────┘
```

- 主圖仍是視覺主角，A20 在主圖**之後**（§9.3 不變）；桌機兩欄只是設計提案，不是新的 grid／breakpoint 裁示。
- 桌機保留 `docs/v2/80` §7.2 的「基金占比／各檔區間報酬」能力：基金占比屬類別占比相關，**延後（D2-C）**；各檔區間報酬屬 L5，待 T8。兩者缺合法口徑時不畫圖、不畫假圖，保留 A51 的資料證據。
- 右欄「依據摘要」只放資料限制的人話說明（例：金額單位、未換算、淨投資金額語意），**不造規則、不放結論**。

### 11.6 區塊對應資料來源與核准標記

| ID | 區塊 | 既有資料來源（本組讀碼；檔案::函式） | 標記 |
|---|---|---|---|
| A00 | 頁級來源狀態 | `alo_holdings.load_alo_tables_active`（`ActiveSourceError`、`skipped_tabs`、`skipped_holdings`）；`ui_v3/adapters/assets_source.py` 的 `source_state` | 位置〔已核准〕；內容〔待裁示〕；β 結論〔不顯示〕（G-1、BL-0411） |
| A10 | 主圖區（狀態卡） | `allocation_evidence`（`source_coverage`、`denominator`、`chart_comparability`，內部候選）；`settings_store.load_user_settings` | 位置與 U2〔已核准〕；狀態卡內容〔待裁示〕；圖本身〔不顯示〕 |
| A10-α | 各類別淨投資金額（金額表） | `holdings.category_values(market=False)`、`CategoryEvidence.value_twd` | ~~〔待裁示 T1〕~~ 〔不顯示：T1＝B，2026-11-09〕；底層類別金額與證據照留，不刪（D2-C 契約候選逐類核可前不具效力） |
| A20 | 四項摘要 | `ui_v2/asset/overview.py::summary_strip`（現為硬編碼 Missing） | 位置與四格〔已核准〕；值〔不顯示〕（G-4）。摘要標籤＝程式現行標籤，沿 §0.1／§9 說明，不代表核准新文案 |
| A30 | 偏離／未評估 | `services/v2_domain/deviation.py`（原子）；組合版在 `ui_v2`，待 PORT | 位置〔已核准〕；結果〔不顯示〕（G-1） |
| A40 | 配息／近期事件 | `nav_dividend.build_dividend_table`；推估 `services/dividend_calendar.py`（未獲准） | 位置〔已核准 U1〕；內容〔不顯示〕（G-3、BL-0534） |
| A50 | 完整持倉列 | `alo_holdings.build_alo_tables`（`holding`）；`holdings.aggregate_holding_rows` | 展開〔已核准 U4〕；欄位〔待裁示 T6〕；DIRECT 持倉〔待裁示 T9〕 |
| A51 | 單檔淨值與限制 | `nav_dividend.build_nav_table`；`nav_metrics.return_pct`（L5） | 淨值事實〔待裁示 T6〕；區間報酬〔待裁示 T8〕；過期／正常標示〔不顯示〕（D7） |
| A52 | 類別歸屬、使用者設定 | `holding.bucket`、`settings_store.load_user_settings`（唯讀） | 〔已核准 U4〕；內容〔待裁示〕；寫入〔不顯示〕（第一階段唯讀） |
| A60 | 來源、略過、缺項證據 | `skipped_holdings`、`skipped_tabs`、`invest_twd_parse_errors`、`allocation_evidence` 的 `uncovered_*` | 預設收合〔已核准 §13.5〕；狀態詞〔待裁示〕（G-5） |

### 11.7 三種畫面狀態（FX 閘門在三種狀態下皆維持關閉）

| 區塊 | 狀態一：來源完整、逐檔資料齊 | 狀態二：部分缺資料 | 狀態三：完全未取得 |
|---|---|---|---|
| 狀態說明 | **不等於正常或安全**；只表示讀取證據完整（`source_coverage`＝complete 成立才可寫） | 部分分頁或列被略過、部分基金缺淨值、幣別不一致、類別未設其一以上 | （a）未選 Active；（b）來源讀取失敗；（c）讀到且來源完整但沒有有效持倉列 |
| A00 | 來源已讀完＋資料時點（推定） | 部分略過，並列已知的略過件數（件數為事實；字樣待裁示） | （a）尚未選定來源，不退回別本 Sheet；（b）`⛔ 取數失敗`（已核准字樣）＋人話失敗分類；（c）僅在來源完整的證據成立時才寫「沒有有效持倉列」，否則 `⬜ 無法判定` |
| A10 | 狀態卡（口徑未核准）；~~T1 若核准則加金額表~~（T1＝B，不加） | 同左，原因加「來源不完整」；~~金額表缺漏類別標 `◇ 資料未備` 並揭露未涵蓋範圍~~（無金額表，原因文字仍須揭露未涵蓋範圍） | 狀態卡，原因為來源狀態；不畫圖、不畫 0 |
| A20 | 四格 `◇ 資料未備` | 同左 | 同左（位置保留，不消失） |
| A30／A40 | 保留一行狀態與原因，不顯示結果 | 同左 | 同左，原因引用 A00 |
| A50／A51 | 完整持倉列、逐檔事實齊 | 可用列照列；缺淨值的檔於淨值欄標 `◇ 資料未備` ＋原因；被略過的持倉**不出現在表內**，由 A60 列出，**不說成沒有持倉** | 空狀態句：（a）（b）說明來源狀態；（c）才可寫沒有有效持倉；不寫「持倉 0」 |
| A60 | 預設收合；內容為完整性證據 | 預設收合；A00 一行指向 | 預設收合；失敗分類人話，不含例外、路徑、機密 |

### 11.8 待客戶裁示清單與停止點

- ~~**T1**　A10 在缺比較口徑時，是否以「各類別淨投資金額」金額表（無占比、無長條、無合計）佔用圖位下方（D2-C 契約候選須逐類核可）。~~
  **T1：已裁示（B）**（客戶 2026-11-09 第二則裁示；登記 DEC-2026-11-09-02〔已登記，以 `docs/DECISIONS.md` 為準；舊標「登記中」已更新，非漏刪〕；本檔不重述其全文，**有意識，非漏刪**）：暫不顯示各類別淨投資金額小計；主圖維持狀態卡；總合計也不顯示。限制：不因此刪底層類別金額與證據；不新增占比、分母或替代圖表；**不宣稱同時解決 T10／G-1**。T2～T10 仍待裁示。
- **T2**　`alo_basis` 設定值「成本」（Sheet 內使用者資料）在使用者面是否標示為「淨投資金額」（設定值不改，只問顯示標籤）。
- **T3**　`cost_orig_ccy`（單位數×平均買入單位成本）的使用者面名稱與是否顯示；本草稿不顯示。
- **T4**　逐檔原幣市值（單位數×淨值）是否可顯示；本草稿不顯示（新衍生值、NAV 日期語意 D7）。
- **T5**　資料限制說明與右欄「依據摘要」的字樣（G-5 狀態詞另案）。
- **T6**　A50／A51 的逐檔欄位集合與是否顯示淨值取得時間、淨值幣別出處。
- **T7**　A30 在偏離結果不顯示時，是否保留佔位列或整塊隱藏。
- **T8**　逐檔區間價格報酬是否在 A51 顯示（價格報酬與跨新版 1Y 含息為不同口徑，後者仍待裁）。
- **T9**　DIRECT 持倉在 New UI2 的顯示（evidence E3 X13；hld 頁未決題）。
- **T10**　淨投資金額合計是否可顯示；本草稿不顯示（可能被誤讀為總資產）。註：各類別淨投資金額小計（A10-α）與「淨投資金額總合計（不顯示）」是兩件不同的事；~~小計是否顯示仍屬 T1 待裁示，不因此放寬合計不顯示~~ → 小計現已由 T1＝B 裁為暫不顯示（2026-11-09），總合計亦不顯示；**T10 本身仍待裁示，T1＝B 不視為已解決 T10**。
- **原 Gate（原樣保留，不代裁）**：G-1～G-5、NAV 10 日（D7）、組合市值損益、正式配置分母、跨新版 1Y 含息、390／1280 真實像素與首屏預算實測（U3）。

**停止點**：本節為設計草稿，**停在客戶 UI Review Gate，不得接續 Streamlit 實作**。客戶審後若核准線框，仍須各 Gate 另行處理，才可談 PORT、adapter 或畫面程式。

**限制與未驗（作者揭露）**：（1）全節為單組作者讀碼，未實跑、未經獨立 QA；（2）線 A／B 的舊能力引自既有 evidence，未重驗；（3）`ui_v3/pages/` 目前沒有 💼 頁，本節所有「現行行為」描述止於 L2／`ui_v2` 讀碼；（4）`nav.ccy` 只來自持倉手填、`dividend` 現場是否取數，依 §8 UNVERIFIED，未實測；（5）首屏 chip 枚數、390／1280 像素皆為設計值；（6）客戶 2026-11-09 裁示為轉述，D2-A／D2-B／D2-C 的選項內容本組未見逐字。

### 11.9 主圖缺資料時的首頁降級線框候選（設計候選；非核准、非施工授權）

> **問題**：現行裁示下 A10 沒有合法的類別比較口徑（§11.4）、A20 四格無正式數值（G-4），兩者幾乎必然是 `◇ 資料未備`；但客戶真正可看的持倉事實（持有單位、幣別、淨投資金額、逐檔淨值）在 A50／A51，位於 A30／A40 之後，容易被藏在下方。本節只比較「首頁怎麼降級呈現」，**不改已核准的 A00→A10→A20 順序**，不新增資料來源、公式、門檻或狀態詞。
> **位階**：方案推薦只是作者（設計文件組）與 ChatGPT 候選的整理，**未經客戶裁示**；客戶 2026-11-09「線框＝A」只授權分階段審查，不是核准最終設計（見 §11.10）。

#### 11.9.1 現況證據（本組讀碼，未實跑）

| 事實 | 證據（檔案::函式） | 對本節的意義 |
|---|---|---|
| ui_v2 合併頁順序：頁級狀態→四格→一句主判讀→主圖（`_render_primary`）→配置占比／各檔報酬→注意事項→**持股明細（`_render_holdings`）**→層 3／層 4 收合區 | `ui_v2/asset/page.py::_render` | 舊 ui_v2 持股明細同樣在主圖之後，並非首屏；只能參考其資訊順序，不是「已解決」的先例 |
| 配置側與持股側各自 `_prepare`，一側失敗只影響該側 | `ui_v2/asset/page.py::_prepare`、`_side_notice` | 「主圖不可用但持倉可用」在 ui_v2 已是被分開處理的情形；概念可參考 |
| 主圖側未載入時只畫一句短狀態；載入但無口徑時畫 `placeholder`（原因句）＋已有列 | `ui_v2/asset/page.py::_render_primary`、`ui_v2/alo/page.py::_placeholder` | A10 降級卡的「原因句」有既有做法；列與圖不假裝完整 |
| 層 3／層 4 的**多塊容器**為預設收合的展開區（單塊容器為該塊自己的展開區，`_render_group` 內 `expanded=block["_default_open"]` 為例外，其塊可預設展開），**標題列帶該塊狀態**（取數失敗、資料未備…） | `ui_v2/asset/page.py::_render_group`、`ui_v2/asset/overview.py::container_title`、`LAYER3_CONTAINERS`／`LAYER4_CONTAINERS` | 「收合列標題先講狀態」是既有導覽方式；可參考 |
| 合併頁容器內**不得巢狀 expander**（`DEC-2026-10-30-02`），改以 `flat=True` 小標題段落 | `ui_v2/hld/page.py::_section`（註解） | A50 內再放 A51 單檔展開時，Streamlit 實作需遵守此限制；舊解法是技術約束，不是設計理想 |
| 持倉頁的取數路徑（持倉讀取→代碼對照→淨值／配息表）**不含匯率讀取** | `ui_v2/hld/source.py::load_live`（本檔讀碼未見匯率讀取呼叫，僅就該檔，未掃 `live.py` 與 L2；未驗） | FX 閘門關閉時逐檔原幣事實在資料層可取得，與 §11.3 一致 |
| 舊 UI 持倉明細以保單分組 `📋 保單 … 檔基金` 展開區，**預設展開**，逐檔卡含 NAV、配息率、Sharpe、σ、💡 建議；不依賴任何「主圖」 | `ui/tab3_portfolio.py`（主清單為 `:1761` 的 `expanded=True`；同名的「📋 保單 … 檔基金」展開區在 `:649` 屬 T5 持股重疊度診斷，`expanded=False`，不是持倉明細；2026-11-09 實查；全檔 2700 行；`ui/tab3_t7_ledger.py` 3547 行） | 舊 UI 持倉就是頁面主體，使用者找得到；但卡內含舊口徑（見下表捨棄項） |
| 新版 `ui_v3/pages/` 目前只有 `mkt.py`，沒有 💼 頁 | `ui_v3/pages/` | 本節一切描述止於設計；無現成 ui_v3 持倉頁可沿用 |

⚠️ 「展開／點擊會不會觸發重新讀 Active Sheet」**未驗**：`ui_v2/hld/source.py` 檔頭自述「不放任何快取」，頁級是否以 session 暫存未讀完整；故下文「不需重新取數」是**設計要求**，不是已證明的現況，須在 Stage 3 以量測證明（見 §11.10）。

#### 11.9.2 可參考 vs 舊版技術負債 vs 視覺優化 vs 需新契約

| 類別 | 項目 | 說明 |
|---|---|---|
| **可參考** | 收合列標題帶狀態（`container_title`）；`placeholder` 原因句；兩側獨立降級；持倉預設可見 | 皆為既有行為，不需新增資料契約 |
| **舊版技術負債（不照搬）** | `tab3_portfolio.py` 內大量 inline HTML 與逐檔卡混入 💡 建議、買賣訊號、核心／衛星標籤；缺報價時的匯率保底鏈（§11.1 L6）；以 `invest_twd` 加總當近似市值；單檔 2700／3547 行混合取數與畫面 | 與 §13.6 的「應捨棄舊行為」及 `DEC-2026-11-04-02` 方案 A 相反 |
| **僅視覺優化（不需改資料契約）** | A10 狀態卡精簡成「原因＋入口」；入口文字或錨點；A50 預設展開或收合；A50 折疊列密度與欄位順序；手機／桌面展開方式；A00 與 A10 的資料限制文字合併去重 | 只動版面；欄位仍是 §11.3 已列的有證據欄位 |
| **需新正式金融契約者（本節不得偷渡）** | 逐檔原幣市值（單位數×淨值）、淨投資金額合計（T4、T10）；類別占比、分母（D2-C、G-1）；任何「已取得 N／M」「資料涵蓋」計數（N＝C，§12）；NAV 過期／正常標示（D7）；組合損益、報酬、1Y 含息（G-4、BL-0524）；Top N 或排名；配息預計入帳 | 皆屬原 Gate，不因降級卡的需求而放行 |

#### 11.9.3 三方案

| 方案 | 內容 |
|---|---|
| **A　保留現有大型狀態卡** | 即 §11.4：A10 狀態卡（原因＋SPEC 列＋資料限制）完整保留，A50 在 A30／A40 之後，順序不動 |
| **B　A10 位置不變，狀態卡精簡＋已有資料入口**（ChatGPT 推薦候選，**非客戶裁示**） | A10 仍在 A00 後、A20 前；狀態卡縮為 2～3 行：`◇ 資料未備`＋一句原因＋一個入口列「查看持倉明細」（**候選文案，未核准**；入口列不放新計數，是否帶 n 依賴 G-1，不預設）；SPEC 列與資料限制改併入 A60 或卡內展開；入口導向 A50，A50 與 A51 規格不變 |
| **C　調整內容階層，持倉事實提早** | 將 A50（或其摘要列）提到 A20 之前或 A10 之前；或僅在主圖不可用時才換序（條件式版面） |

| 維度 | A | B | C |
|---|---|---|---|
| 金融語意正確性 | 正確（不畫假圖、不顯示假 100%） | 同 A（同樣不畫、不合計；入口不增語意） | 同 A，但持倉事實放在摘要前可能被讀成「這才是資產全貌」，須加限制說明 |
| 是否違反 U1～U5、「主圖在前／四格在後」 | 否 | ~~否~~ **A10→A20 位置不動；但 U3「A10 簡潔 SPEC」的去向待裁（U3）**：精簡卡把 SPEC 列併入 A60 或卡內展開，是否仍符合 U3 須客戶確認；390px 線框已補一行簡潔 SPEC 列作為候選落法 | **有風險**：A50 置於 A10 前＝違反「主圖在前」；置於 A10 與 A20 之間＝改動已核准的 A00→A10→A20 順序；條件式換序則版面位置隨資料狀態跳動 |
| 手機第一屏辨識性 | 狀態卡占高；持倉入口在下方，需捲動（未量測） | 狀態卡短、入口在首屏的機率較高（390px 實機高度未提供，**未驗**） | 持倉事實最先看到，但四格與主圖被推下，破壞已核准視覺順序 |
| 缺 NAV／FX／分類／Active Sheet 時是否仍正確 | 是（逐情境見 §11.7） | 是；入口在「完全未取得」情境須改指狀態說明或隱藏，不得導向空頁 | 需為每個缺項情境各設一套換序規則，錯配風險最高 |
| 開發維護成本 | 最低（現狀） | 低（一個降級卡變體＋入口；Streamlit 內不巢狀 expander 的限制須處理） | 最高（設計推測、未量測：兩種版面路徑、測試矩陣倍增） |
| Token 成本 | 最低 | 低 | 高（設計推測、未量測：版面分支、QA 情境、截圖審查皆增） |
| 是否需額外 UI Review Gate | 否 | 是（精簡後的 A10 內容與入口文案；仍屬 Stage 1，見 §11.10） | 是，且必須先由客戶裁示是否同意改動 A00→A10→A20 順序 |

**總管推薦（設計文件組作者意見，未經客戶裁示）：B。** 理由：不動已核准順序、不新增資料契約、只改 A10 的版面占用與入口；A 的問題是首屏資訊價值低、C 需先推翻已核准順序。推薦附條件：(1) 入口列不放新計數；(2) 「資料限制」文字不得因精簡而消失；(3) 完全未取得時入口不導向空內容。~~**此推薦會成為待客戶審查的 Stage 1 選項之一，不是預設已選。**~~（2026-11-09 客戶 Stage 1 裁示 S1-1＝B，有意識，非漏刪；登記見 DEC-2026-11-09-03（以 DECISIONS 為準），要點見 §11.9.5。舊句的用意——推薦非預設已選——在裁示前成立；被權衡掉的是它的前提：客戶已選 B。裁示只涵蓋降級卡形態與入口原則，卡內文案與入口文案仍〔待裁示〕。）

#### 11.9.4 線框（文字線框；方案 B；A00／A20／A30／A40 與 §11.4 同，不重畫；390px 為手機設計、1280px 為桌面另一套）

**共通前提**：現行裁示下，A10 在三情境**都是降級卡**（沒有合法的比較口徑，主圖不可畫；主圖可畫的情境待 U2 條件成立，**本節不畫**）。A20 四格皆 `◇ 資料未備`，不得新增首頁 chip／核心數字，沿 §11.2 預算。

```text
390px 情境一：來源完整、逐檔事實齊（不等於正常或安全）
┌ A00 💼 我的資產｜來源：<已讀完，描述性>｜資料時點（推定）
├ A10 資產配置｜實際 vs 目標
│   ◇ 資料未備｜原因：<配置比較口徑尚未核准；淨投資金額不是配置分母>
│   SPEC：基準＝<設定值／⬜ 未設定>｜單位＝<新臺幣（淨投資金額）／各檔原幣>｜時點｜缺項〔簡潔一列；去向待裁（U3）〕
│   ▸ 查看持倉明細〔候選文案，未核准〕　→ A50
├ A20 總資產 ◇│損益 ◇ / 報酬 ◇│期間配息 ◇（四格標籤＝A20 現行標籤，不代表核准新文案）
├ A30／A40 一行狀態（不顯示結果）
├ A50 ▸ 完整持倉（逐檔；入口落點）｜名稱｜單位｜幣別｜淨投資金額（新臺幣）｜類別｜最近淨值（原幣）＋淨值日
└ A60 ▸ 來源、略過、缺項證據（收合）

390px 情境二：部分缺資料（略過列、缺淨值、幣別不一致、未分類之一以上）
┌ A00 來源：<部分略過；件數為事實>
├ A10 ◇ 資料未備｜原因：<配置口徑未核准＋來源不完整>
│   ▸ 查看持倉明細（可用的 <已有列> 仍可看；略過者見 A60）〔不新增計數，字樣待裁示〕
├ A20 四格 ◇ ×4
├ A50 ▸ 可用列照列；缺淨值之檔：淨值欄 ◇ 資料未備＋原因；被略過者不出現在表內，不說成沒有持倉
└ A60 ▸ 略過與缺項證據（A00 一行指向）

390px 情境三：完全未取得（(a) 未選 Active (b) 讀取失敗 (c) 來源完整且無有效列）
┌ A00 (a) ⬜ 尚未選定持倉資料來源（不退回別本 Sheet）／(b) ⛔ 取數失敗＋人話分類／(c) 僅在證據成立才寫「沒有有效持倉列」，否則 ⬜ 無法判定
├ A10 ◇ 資料未備｜原因＝引用 A00；**不放持倉入口**（無可看之物）
├ A20 四格 ◇ ×4
└ A50 空狀態句（同 §11.7）；不寫「持倉 0」
```

```text
1280px（共用 Sidebar／Shell 同 §11.5；內容區兩欄）
┌ A00 來源狀態（單一容器）
├──────────────────────────────┬──────────────────────┐
│ A10 降級卡：◇ 資料未備＋原因   │ 依據摘要（資料限制人話）│
│ 入口列「查看持倉明細」〔候選〕   │ 淨投資金額語意註記      │
├──────────────────────────────┴──────────────────────┤
│ A20 四格並列 ◇ ×4                                      │
├──────────────────────────────┬──────────────────────┤
│ A30 偏離／未評估（不顯示）       │ A40 配息／事件（U1）   │
├──────────────────────────────┴──────────────────────┤
│ A50 完整持倉寬表（桌面是否多顯示基金代號、淨值取得時間、資料限制欄：〔欄位待 T6〕） │
└────────────────────────────────────────────────────┘
情境二、三的差異同 390px 規則（缺項標示、完全未取得時隱藏入口）；桌面不另增計數或圖表。
```

**使用者路徑（設計要求；展開是否重新取數未驗，見 §11.9.1）**：看到 A10 降級卡與原因 →（有可用持倉列時）點「查看持倉明細」→ 停在 A50 的已讀入列 → 點單檔展開 A51 看淨值取得時間、幣別出處、該檔資料限制。整段只消費本次已讀入的、可追溯的持倉事實（`holding`、`nav` 表），**不新增取數、不換算匯率、不推算市值**；若這條路徑在實作時會觸發重新讀取，即退回 Stage 3 重新評估，不得為求入口而放寬。

**不可做（沿 §11.3、§11.2，重列為本節硬限制）**：不改 A00→A10→A20；A10 不畫假圖、不顯示假 100% 或任何占比；A20 無正式數值維持 Missing；不新增首頁 chip／核心數字（不破 44 預算）；淨投資金額不稱成本、市值或總資產；不以同源證據不完整的 1Y 含息填摘要；FX 閘門關閉時仍可見持有單位、幣別、淨投資金額、逐檔淨值事實；NAV 10 日、DIRECT、配息、偏離、組合損益依原 Gate，不因降級卡放行；T1＝B（不顯示各類別淨投資金額小計與總合計）與 N＝C（不顯示新定義的資料涵蓋 N／M）同樣適用。

#### 11.9.5 客戶 Stage 1 裁示（2026-11-09；登記見 DEC-2026-11-09-03（以 DECISIONS 為準））

> **來源**：客戶 Stage 1 三題裁示，經總管派工單轉述（**要點轉述，非逐字；本檔不重述 DEC 全文**）。本小節以下（§11.9.5～§11.9.12）是依該裁示更新的**設計規格草稿**，**不是真機驗收、不是施工授權**；作者＝設計文件組，**未經獨立 QA**。

| 題 | 客戶裁示（要點） | 本檔落法 |
|---|---|---|
| S1-1 主圖缺資料降級 | ＝**B**：A10 原位；無合法計算口徑時為精簡降級卡＝已核准的資料不足狀態＋一句原因＋持倉明細入口；保留 U3 簡潔 SPEC 與必要資料限制；入口不放檔數／涵蓋率／金融數字／投資建議；完全沒有可查看持倉時隱藏入口或改顯示合法來源狀態、不導向空內容；「查看持倉明細」仍是**候選文案** | §11.9.7～§11.9.9 |
| S1-2 A50 預設狀態 | 手機＝預設收合，點 A10 入口後展開 A50 並**定位**；桌面＝有可靠證據存在可用持倉列時預設展開，無 Active Sheet／取數失敗／無合法持倉時不展開空表，部分缺漏保留可用列；不因展開推定完整／健康／安全；**展開／定位／rerun 是否重新讀 Active Sheet 未驗（Stage 3 技術 Gate，不得宣稱已測）**；保留禁巢狀 expander | §11.9.9、§11.9.10、§11.9.12 |
| S1-3 逐檔密度 | 手機＝單欄精簡逐檔卡（已確認事實優先、次要按需展開、不橫向捲動、缺資料顯示合法 Missing 與原因、不隱藏整檔）；桌面＝完整寬表（可按需看單檔更多來源／日期／幣別／限制）；不新增排名／建議／分類推論／未核准金融指標；**T6 欄位集合與語意仍未核准**，只定排版密度、資訊階層、展開方式、欄位容器 | §11.9.10 |

**不變的限制**：已核准順序 A00→A10→A20→A30→A40→A50／A51→A52→A60 不動，A10 仍為主圖位置，**不得把持倉明細搬到主圖前**；A20 無正式值維持 Missing；不新增 chip、假數字、假圖、占比、涵蓋率；T1＝B、N＝C 不回退；「淨投資金額」不稱成本／市值／總資產／本金；T6、G-1～G-5、NAV 10 日、DIRECT、配息、組合損益、分母占比、1Y 跨版含息、D2 Schema 全部**維持原狀態**（本節只標「依賴」，不裁）。

#### 11.9.6 舊 UI 對照補充（只補與「入口→展開→定位→逐檔卡／寬表」直接相關者；#1180／#1181 已做的對照不重做）

| 類別 | 項目與證據（本組唯讀；`ui/tab3_portfolio.py` 為約略位置、未逐行複核） | 對本節的意義 |
|---|---|---|
| **可參考的操作能力** | ① 持倉主清單為「📋 保單 … 檔基金」展開區，`expanded=True`（`ui/tab3_portfolio.py:1761`）——持倉是舊頁主體、不必先點開；② 逐檔卡首行帶載入狀態圖示（✅／❌／⏳，同檔約 :1763）——「單檔失敗不拖垮整頁」的呈現方式；③ ui_v2 的展開區**標題列帶狀態**（`ui_v2/asset/overview.py::container_title`）與「單塊容器＝該塊自己的展開區」（`ui_v2/asset/page.py::_render_group`） | 桌面「有證據則預設展開」與舊頁一致；收合時標題先講狀態＝手機 A50 收合列的做法；單檔缺資料以逐卡標示、不隱藏整檔 |
| **可保留的資料事實**（皆已在 §11.3 列出且有來源，不新增欄位） | 持有單位、持有幣別（使用者填寫）、淨投資金額（新臺幣）、類別（使用者設定）、逐檔最近淨值／淨值日／取得時間、逐檔資料限制；以保單分組為舊頁的組織方式（是否沿用屬 T6／客戶，**本節不採用也不否決**） | 容器內可放的事實範圍；欄位集合仍〔待 T6〕 |
| **不適合移植的舊版互動與金融語意** | 卡內 💡 建議／買賣訊號、核心／衛星標籤、配息率、Sharpe、σ（`DEC-2026-11-04-02` 方案 A、§11.1 L6、§11.9.2 已列）；✅／❌／⏳ 圖示不是已核准狀態字樣（核准字樣見 §12.3）；以 `invest_twd` 加總當近似市值；單檔 inline HTML 與取數混合的寫法 | 不移植；逐檔卡只放事實，不放建議、不放分類推論 |
| **需下一階段（Stage 3）驗證的技術問題** | 舊頁「預設展開」在 rerun 後是否維持、展開是否重新取數：舊頁行為本組**未驗**；新版同題見 §11.9.12 | 不得以舊頁行為當新版已證明 |

#### 11.9.7 390px 手機線框（S1-1＝B／S1-2 手機收合；文字線框；設計值，未量測）

導覽依現行 Shell：手機 ≤768px 為**頁首五格、位於文件流內、不吸頂**（`ui_v3/shell/nav.py`：`MOBILE_MAX_PX=768`、`TOP_NAV_HEIGHT_PX=60`、`TOUCH_MIN_PX=48`；依 BL-0544／`DEC-2026-11-07-02`）。**§11.4 原寫的「底部五格導航」與現行 Shell 不一致，以 Shell 現況為準**（§11.4 舊句不改，這裡更正；有意識，非漏刪）。以下三種情境，A00／A20／A30／A40 沿 §11.4／§11.9.4，不重畫細節。

```text
390px 情境一：來源完整、逐檔事實齊（不等於正常或安全）
┌ A00 〔已核准〕💼 我的資產｜來源：<已讀完，描述性>｜資料時點（推定）
├ A10 資產配置｜實際 vs 目標 〔位置已核准；降級卡＝S1-1 B；Missing 分類＝UI-1 候選〕
│   ◇ 資料未備｜類別(b)：已有持倉資料可查看；配置比較的計算口徑尚未核准，故不提供結果
│                〔原因句＝候選文字，未核准；狀態字樣仍只用已核准的「◇ 資料未備」；淨投資金額不是配置分母〕
│   SPEC：基準＝<設定值／⬜ 未設定>｜單位｜時點｜缺項   〔簡潔一列；U3 保留〕
│   限制：<目前未做匯率換算，各檔原幣數值不合計>      〔必要資料限制；字樣待 T5〕
│   ▸ 查看持倉明細   〔候選文案，未核准；≥48px 觸控；文字列，非 chip；不帶任何數字；位於原因句之後、不被重複文字擠走〕
├ A20 2×2（方案 B 候選）：總資產 ◇ 資料未備(b)｜損益 ◇(b)｜報酬 ◇(b)｜期間配息 ◇(b)
│   ＝四格各自保留 Missing、各一行（括號內為極短原因類別標記，候選文字）；格下不重複長說明，詳細原因由 A60（既有展開區）按需查看
├ A30 ▸ 一行狀態（不顯示結果）
├ A40 ▸ 一行狀態（不顯示結果）
├ A50 ▸ 完整持倉（預設收合；收合列標題帶狀態）
├ A52 ▸ 類別歸屬與使用者設定（唯讀）
└ A60 ▸ 來源、略過、缺項證據（預設收合）

點「查看持倉明細」之後（同一頁、不換頁）
┌ A10 降級卡（入口列維持原位，不消失）
├ A20／A30／A40 照舊
├ A50 ▾ 完整持倉（已展開；標題列貼近可視區頂端、不被頁首導覽或 Streamlit 頂列遮住）
│   ┌ 卡 1：<基金名稱，可換行>
│   │  持有單位｜持有幣別（使用者填寫）〔欄位待 T6〕
│   │  淨投資金額（新臺幣）〔欄位待 T6〕
│   │  類別｜最近淨值（原幣）＋淨值日〔欄位待 T6〕
│   │  ▸ 更多（A51）：淨值取得時間｜幣別出處｜該檔資料限制〔欄位待 T6〕
│   └ 卡 2 … 卡 k（來源順序；無 Top N、不排名、不排序）
└ A52／A60 ▸ 照舊

390px 情境二：部分缺資料（略過列／缺淨值／幣別不一致／類別未設之一以上）
┌ A00 來源：<部分略過；件數為事實，字樣待裁示>
├ A10 ◇ 資料未備｜兩類原因分兩短句並列、不混成一句：類別(a)<來源不完整（部分略過）>；類別(b)<配置口徑未核准>；SPEC／限制各一列；▸ 查看持倉明細（有可用列才出現；〔候選對映，見 §11.9.9〕）
├ A20 四格各一行 ◇ 資料未備：缺來源者標(a)、口徑未核准者標(b)（逐格各自判斷、不統一寫成同一原因）
├ A50 ▸ 完整持倉（收合列標題帶狀態，例：部分略過）；展開後可用列照列，被略過者不在表內、由 A60 列出
│   缺淨值之檔：該卡淨值列 ◇ 資料未備｜<原因>（整卡不隱藏）
└ A60 ▸ 略過與缺項證據

390px 情境三：完全未取得（(a) 未選 Active (b) 讀取失敗 (c) 來源完整且無有效列）
┌ A00 (a) ⬜ 尚未選定持倉資料來源（不退回別本 Sheet）／(b) ⛔ 取數失敗＋人話分類／(c) 證據成立才寫「沒有有效持倉列」，否則 ⬜ 無法判定
├ A10 ◇ 資料未備｜類別(a)：原因＝引用 A00 同一狀態（來源未取得）；SPEC／限制各一列；**不放入口**（無可看之物）
├ A20 四格各一行 ◇ 資料未備(a) ×4（原因＝A00 同一狀態；不重複展開說明）
└ A50 不是可展開區：僅一列狀態文字「完整持倉　—　<A00 同一狀態句>」，不畫空表、不寫「持倉 0」
```

> **2026-11-09 UI Review 補強更新註記（有意識，非漏刪）**：上列 A10／A20 行已依客戶 UI-1／Batch 2 更新；~~舊句：A10「◇ 資料未備｜<一句原因：配置比較口徑尚未核准；淨投資金額不是配置分母>」、A20「總資產 ◇｜損益 ◇／報酬 ◇｜期間配息 ◇（值全 Missing 時每格單行…）」、情境二「<配置口徑未核准＋來源不完整>」、情境三「A20 四格 ◇ ×4」~~。舊句的用意（不畫假圖、不假裝有值）仍成立；被權衡掉的是它**沒有區分**「原始資料缺漏／取數失敗」與「原始資料可能存在但計算口徑未核准」，使用者可能誤把後者讀成沒有持倉資料。**不新增狀態詞、reason_code 或狀態映射**；類別(a)＝原始資料缺漏或取數失敗、類別(b)＝原始資料可能存在但正式計算口徑尚未核准，僅是**說明原因的設計候選**，詳見 §11.9.11。
> **A51 在手機的呈現**：卡內「▸ 更多」**不得**是 A50 內的第二層 Streamlit expander（`DEC-2026-10-30-02`）；實際元件、焦點與 rerun 行為屬 §11.9.12 候選，**未驗**。

**手機第一屏資訊效率（設計意圖；390px 實機高度未提供，不宣稱入口一定在首屏）**：A10 降級卡由「大卡」縮為 4 個文字層（狀態＋原因、SPEC、限制、入口），入口離 A00 約一卡之距；A20 值全為 Missing 時每格單行、不放長說明；A30／A40 無結果時各只剩一行。使用者要找的既有持倉事實，路徑縮短為「看到 A10 入口→一次點擊」，**不改任何已核准順序**。

**390px 逐項設計要求（Batch 2；皆為設計值、未量測）**：
- **A10 不重新變大型狀態卡**：仍限上列四個文字層；原因句一句、兩類原因（情境二）最多兩短句；不放圖示堆疊、不放說明段落。
- **A20 四格易讀、不需四次重複冗長解釋**：每格一行 Missing＋極短類別標記；共同原因由 A10 原因句與 A60 承載，不在四格各複製一遍。
- **有合法持倉時快速找到 A50 入口**：入口在 A10 內、原因句之後；入口不被 A20 之後的內容推遠（不依賴 A20 的說明文字長度）。
- **單欄逐檔卡不橫向捲動；單檔缺資料整卡保留**（缺欄位格標 `◇ 資料未備`＋原因）。
- **A51 的「▸ 更多」不形成巢狀 expander**（見上註；元件候選＝§11.9.12，未驗）。
- **導覽**：以 `ui_v3/shell/nav.py` 現行頁首五格為準（≤768px、文件流內、不吸頂）；頁內「查看持倉明細」定位須避開頁首與 Streamlit 頂列。
- 三情境（已有合法資料／部分缺漏／完全沒有合法可讀取資料）皆見上列線框；**皆為「設計／未實測」，不得據此宣稱手機或 Cloud 驗收**。

#### 11.9.8 1280px 桌面線框（S1-1＝B／S1-2 桌面條件式展開；設計值，未量測）

```text
1280px（共用 Sidebar／Shell 同 §11.5；內容區兩欄；桌面與手機是不同版面，不是縮放）
┌ A00 來源狀態（單一容器）
├──────────────────────────────┬──────────────────────┐
│ A10 降級卡：◇ 資料未備＋一句原因  │ 依據摘要（資料限制人話）│
│  〔類別(a)來源缺漏／取數失敗 或      │ 淨投資金額語意註記      │
│   類別(b)口徑未核准；分開說明〕       │〔待裁示 T5〕        │
│ SPEC 一列＋資料限制一行（保留） │                      │
│ ▸ 查看持倉明細（候選；有可用列才出現） │                      │
├──────────────────────────────┴──────────────────────┤
│ A20 四格並列，各一行 ◇ 資料未備＋極短類別標記(a)/(b)（公式待裁示 G-4；方案 B 候選）│
│   詳細原因由 A60 按需查看；四格不重複長說明                  │
├──────────────────────────────┬──────────────────────┤
│ A30 偏離／未評估（不顯示結果）   │ A40 配息／事件（U1）   │
├──────────────────────────────┴──────────────────────┤
│ A50 ▾ 完整持倉（有可靠證據存在可用持倉列→預設展開；否則不展開空表）│
│  寬表〔欄位待 T6〕：名稱｜代號｜持有單位｜持有幣別｜淨投資金額（新臺幣）│
│                     類別｜最近淨值（原幣）｜淨值日｜取得時間｜資料限制  │
│  A51 單檔「更多」：非巢狀列內詳情＝優先設計候選（見下方 A51 線框；側欄為備選，須回 UI Review）│
├──────────────────────────────────────────────────────┤
│ A52 ▸ 類別歸屬與設定（唯讀）  A60 ▸ 來源、略過、缺項證據（預設收合）│
└──────────────────────────────────────────────────────┘
部分缺漏：可用列保留；缺項格標 ◇ 資料未備＋原因；被略過者由 A60 列出。
完全未取得：入口隱藏；A50 退為一列狀態文字（同手機情境三），不展開、不畫空表。
```

> **更新註記（有意識，非漏刪）**：上圖 A10／A20 與 A51 行已依 UI-1／UI-3 更新；~~舊句：「A10 降級卡：◇ 資料未備＋一句原因」「A20 四格並列 ◇ ×4」「A51 單檔『更多』…列內或側欄，二選一，待 UI Review」~~。舊句用意仍成立；被權衡掉的是未區分兩類 Missing 原因，以及 A51 位置二選一未排序（現改為客戶 UI-3 的**非巢狀列內詳情優先候選**，若技術驗證不可行即回 UI Review 比較其他方案）。

- 桌面入口行為與手機相同（展開＋定位）；預設已展開時，點入口＝定位到 A50，不會把它收起。
- 欄位頭是**容器佔位**，不是已核准欄位集合；是否出現「代號」「取得時間」「資料限制」欄屬 T6。
- 桌面寬表仍不新增排名、建議、分類推論、占比、區間報酬（T8 待裁示）；基金占比圖維持延後（D2-C）。

**A51 桌面非巢狀列內詳情線框（1280px；UI-3 優先設計候選；只畫欄位容器、主次階層、互動位置；不選定 Streamlit API／HTML／JS；T6 欄位未核准）**

```text
A50 ▾ 完整持倉（保留 A50 完整寬表；欄位容器〔待 T6〕）
┌────────┬────┬──────┬──────┬──────────┬────┬────────┬──────┬────────┬────┐
│ 名稱    │代號 │持有單位│持有幣別│淨投資金額(新臺幣)│類別 │最近淨值(原幣)│淨值日 │資料限制(摘要)│ 更多│
├────────┼────┼──────┼──────┼──────────┼────┼────────┼──────┼────────┼────┤
│ 基金甲  │ …  │ …    │ …    │ …        │ …  │ …      │ …    │ …      │ ▾  │  ← 被展開的列：控制項為「▾」，列有明確選取標示（不只靠顏色）
│ ┃ A51 詳情｜屬於：基金甲（標題重複基金名稱，避免錯列）                       │
│ ┃ 淨值取得時間｜幣別出處｜該檔資料限制（完整）〔欄位待 T6〕｜[收合 ▴]         │  ← 緊接在該列下方；左側縮排＋垂直線連到該列；與表同寬、不蓋住下一列
├────────┼────┼──────┼──────┼──────────┼────┼────────┼──────┼────────┼────┤
│ 基金乙  │ …  │ …    │ …    │ …        │ …  │ …      │ …    │ …      │ ▸  │
└────────┴────┴──────┴──────┴──────────┴────┴────────┴──────┴────────┴────┘
設計要求：① 在對應列附近展開，不把使用者帶到頁面他處；② 詳情標題含基金名稱，明確屬於哪一檔；③ 展開不改變其他列的順序與位置之外的內容，
避免畫面跳躍與錯列；④ A51 控制項與詳情**不是** A50 內的第二層 Streamlit expander（`DEC-2026-10-30-02`）；⑤ 是否允許多列同時展開＝〔待 UI Review〕；
⑥ 缺資料之檔：詳情內欄位標 ◇ 資料未備＋原因，整列保留；⑦ 不新增排名／建議／分類推論／區間報酬；⑧ 寬表過寬時的欄位取捨＝〔待 T6／UI Review〕，整頁不得水平溢出。
技術未驗：Streamlit 1.59.x 能否在原生表格元件的列下方插入詳情、焦點管理、rerun 是否重讀 Active Sheet——**全部未驗**（§11.9.12）。若不可行，回 UI Review 比較其他方案（側欄、單檔選擇器＋下方詳情等，皆須另經裁示）。
```

**1280px 三情境（設計／未實測；A00／A30／A40／A52／A60 沿 §11.5／§11.9.4，不重畫）**

```text
情境一 已有合法資料（來源完整，不等於正常或安全）
  左欄 A10：◇ 資料未備｜類別(b) 計算口徑未核准；已有持倉資料可查看 ｜ SPEC／限制 ｜ ▸ 查看持倉明細
  A20：四格各一行 ◇(b)；  A50 ▾ 預設展開（有可靠證據存在可用持倉列，〔候選對映，見 §11.9.9〕）；A51 列內詳情按需展開
情境二 部分缺漏
  A10：◇ 資料未備｜(a) 來源不完整（部分略過）；(b) 口徑未核准（兩短句分開）｜ ▸ 查看持倉明細
  A20：逐格各自標(a)或(b)；A50 ▾ 只列可用列，缺項格 ◇ 資料未備＋原因；被略過者列於 A60；不因展開推定完整
情境三 完全沒有合法可讀取資料
  A10：◇ 資料未備｜(a) 引用 A00 同一狀態；不放入口；A20 四格 ◇(a)；A50 退為一列狀態文字，不展開、不畫空表
```

**1280px 逐項設計要求（Batch 2；設計值、未量測）**：主圖（A10）位於摘要之前；左欄主內容、右欄資料限制（層級不顛倒、右欄不壓過主圖）；有合法持倉時 A50 展開為完整寬表；A51 列內詳情不破壞表格可讀性；寬表不致整頁水平溢出；**缺資料與「計算口徑未核准」不混為「無持倉」**；不加建議／排名／風險判定。

#### 11.9.9 A10 降級卡與入口的精細操作流程（設計規格；技術行為未驗）

**入口出現條件（只引用已有證據來源，不新定義）**：入口（以及桌面 A50 預設展開）只在下列**兩項同時成立**時才出現：
1. 持倉讀取成功：Active 來源已選定且持倉讀取未失敗（`ui_v3/adapters/assets_source.py` 的 `holding.kind` 不是 `KIND_NO_ACTIVE`／`KIND_FAILED`，`AssetsLoadResult.problems` 不含 `PROBLEM_NO_ACTIVE`／`PROBLEM_HOLDING_READ_FAILED`；ui_v2 側等價為 `ActiveSourceError` 未發生）；
2. 讀到的 `holding` 表（`services/v2_tables/alo_holdings.py::build_alo_tables` 輸出）**至少有一列**——被 L2 既有略過規則（單位空白或 0 等）擋下者在 `skipped_holdings`、不在表內，不算可用列。

> ⚠️ **UI-2（客戶 2026-11-09）標示：本對映為「候選對映／未獨立驗證／不得直接升格 production contract」**——A50 入口「有可靠證據存在可用持倉列」的**原則不變**；但 `holding.kind`、`AssetsLoadResult.problems`、`holding` 表至少一列這三者與該原則的對映，是作者讀碼的**暫行候選**，未實跑、未經客戶或獨立 QA 確認；入口只能在證據成立時出現、無可用持倉不得出現導向空內容的入口。
>
> 「可用持倉列」＝上列兩項的作者對映（沿 §11.3「空白或 0 的列不進持倉表、進略過清單」）；**不使用 n／m／j、不算 N／M、不增門檻**；此對映與「可靠證據」一詞是否等同，**待客戶或獨立 QA 確認**。入口**不依賴**任何已被 Gate 擋住的值（G-1～G-5）。

**入口狀態矩陣（暫行：可用持倉列的判定來源與門檻，客戶未定義）**

| 情境 | 入口 | A10 原因句 | A50 手機 | A50 桌面 |
|---|---|---|---|---|
| 來源完整、有可用列 | 顯示 | 配置口徑未核准 | 收合 | 預設展開 |
| 部分缺漏、仍有可用列 | 顯示（不帶件數） | 配置口徑未核准＋來源不完整 | 收合 | 預設展開（只列可用列） |
| 未選 Active／讀取失敗 | **隱藏** | 引用 A00 同一狀態 | 不展開（一列狀態文字） | 不展開（一列狀態文字） |
| 來源完整但無可用列（c） | **隱藏** | 證據成立才寫「沒有有效持倉列」，否則 ⬜ 無法判定 | 同上 | 同上 |

**點擊後的流程（手機；桌面同 1～3，只是 A50 已展開）**
1. 點「查看持倉明細」＝**同頁**操作，不換頁、不彈窗覆蓋頁首導覽。
2. A50 展開（已展開則維持展開，**不切換成收合**；收合只靠 A50 自己的標題列）。
3. 視窗定位到 A50 標題列：標題列貼近可視區頂端、**不被文件流內的頁首導覽或 Streamlit 自身頂列遮住**（預留偏移值**未驗**）；整頁不產生水平捲動；不依賴動畫。
4. **當前區塊辨識**：A50 標題列維持可見的「完整持倉」字樣＋展開狀態（▾）；入口列留在原位，使用者可往上回到 A10。是否額外加「回到資產配置」連結、以及目前區塊的視覺強調方式，屬〔待 UI Review〕；**色票沿現行 Shell，不新增 token**；不得只靠顏色表達狀態（`PROJECT_RULES.md` §13.2 第 3 點）。
5. **焦點**：展開／定位後鍵盤與輔助技術焦點應落在 A50 標題列（可聚焦者），不得停在已被捲離的入口或回到頁頂；**能否做到取決於 §11.9.12 候選，未驗**。

**入口與 A10 原因句的相對位置（Batch 2）**：原因句（含 Missing 類別）在前、入口列在後；重複性說明（SPEC、限制）各限一列，不得壓過入口；使用者可從 A10 直接找到「已有持倉資料可查看」的路徑。此為設計要求，不是已量測的首屏位置。

**入口不放**：檔數、涵蓋率、占比、金融數字、投資建議、狀態詞新創字樣；入口是文字列，不做成 chip、不計入首屏 chip 名額（是否仍被保守讀法計入 44 首屏預算＝待 UI Review）。

#### 11.9.10 A50／A51 資訊階層：手機逐檔卡 vs 桌面寬表（容器級；欄位全部〔欄位待 T6〕）

| 面向 | 手機（單欄逐檔卡） | 桌面（完整寬表） |
|---|---|---|
| 容器 | 每檔一張卡；不橫向捲動；長名稱換行 | 一張表；欄位容器依 T6 結果定；若欄位多於容器寬度，捲動／欄位取捨方式待 UI Review（不得讓整頁橫溢） |
| 主層（常駐，已確認事實優先） | 基金名稱；持有單位＋持有幣別（使用者填寫）；淨投資金額（新臺幣）；類別；最近淨值（原幣）＋淨值日 | 同左各欄並排；可多顯示代號 |
| 次層（按需，A51） | 卡內「更多」：淨值取得時間、幣別出處、該檔資料限制 | ~~列內展開或側欄（二選一）~~ → **非巢狀列內詳情＝優先設計候選**（客戶 UI-3；線框見 §11.9.8）；側欄為備選、須回 UI Review；亦可作為欄位常駐（T6）。（舊句劃線保留，非漏刪） |
| 缺資料 | 該欄 `◇ 資料未備`＋原因；整卡保留 | 同；缺項格標示，整列保留 |
| 幣別不一致 | 兩幣別並列、標 `⬜ 無法判定`，不擇一（§11.3） | 同 |
| 列序 | 來源既有順序；無排序、無 Top N、無排名 | 同 |
| 不顯示 | 逐檔原幣市值（T4）、淨投資金額合計（T10）、區間報酬（T8）、過期／正常標示（D7）、💡建議、核心／衛星推論、占比、「已計入 N／M」 | 同 |
| 單層展開 | A50 是唯一一層展開區；A51 以**非展開區元件**呈現（見 §11.9.12），不得在 A50 內再放 expander（`DEC-2026-10-30-02`；`ui_v2/hld/page.py::_section` 之 `flat=True` 註解） | 同 |

#### 11.9.11 三種來源狀態與區塊標記總表

**三種狀態（沿 §11.7，只補 S1 的入口與展開行為；FX 閘門三態皆關閉）**

| 狀態 | 判斷依據（既有證據） | 入口 | A50 |
|---|---|---|---|
| 來源完整 | `source_coverage`＝complete 成立（`allocation_evidence`）且有可用列；**不等於正常／安全／健康** | 有 | 手機收合；桌面預設展開 |
| 部分缺漏 | `skipped_holdings`／`skipped_tabs`、缺淨值、幣別不一致、類別未設之一以上，且仍有可用列 | 有（不帶件數） | 手機收合；桌面預設展開；可用列保留、原因可追溯（A60）；**不因展開推定完整** |
| 完全未取得 | 未選 Active／讀取失敗／（來源完整但無可用列） | 無 | 不展開；一列狀態文字；不畫空表 |

**區塊標記（本批 S1 後）**

| ID | 標記 |
|---|---|
| A00 | 位置〔已核准〕；內容〔待裁示〕；β 結論〔不顯示〕 |
| A10 | 位置與主圖角色〔已核准〕；降級卡形態＝S1-1 B〔已核准（客戶 Stage 1）〕；卡內文案、入口文案「查看持倉明細」、SPEC／限制字樣〔待裁示〕；圖本身〔不顯示〕 |
| A20 | 位置與四格〔已核准〕；值〔不顯示〕；Missing 時單行密度〔待裁示：僅視覺〕 |
| A30／A40 | 位置〔已核准〕；無結果時的一行狀態〔待裁示 T7 之去留〕；結果內容〔不顯示〕 |
| A50 | 展開〔已核准 U4〕；手機收合／桌面條件式展開＝S1-2〔已核准（客戶 Stage 1）〕；入口定位的實際技術做法〔待裁示：Stage 3 技術 Gate〕；欄位集合〔待裁示 T6〕 |
| A51 | 手機卡內「更多」／桌面列內或側欄＝S1-3〔已核准（客戶 Stage 1）：次要按需展開〕；欄位〔待裁示 T6〕；區間報酬〔待裁示 T8〕 |
| A52 | 位置〔已核准 U4〕；內容〔待裁示〕；寫入〔不顯示〕 |
| A60 | 預設收合〔已核准〕；狀態詞〔待裁示 G-5〕 |

**A10／A20 Missing 兩類原因的說明區分與降級視覺比較（客戶 UI-1／Batch 2；ChatGPT／作者候選；客戶核准「補強 A10／A20 Missing 的視覺與語意區分」並要求「優先評估 B」，故 B 僅為「優先評估候選」，**未核准最終，不等於已選定 B**）**

- **類別(a)**：原始資料缺漏或取數失敗（例：未選 Active、讀取失敗、來源略過、缺淨值）；**類別(b)**：原始資料可能存在但正式計算口徑尚未核准，故不能提供衍生結果（例：配置比較、總資產、報酬）。兩類**說明不得混同**。
- **只能用已核准狀態字樣**：`◇ 資料未備`、`⬜ 無法判定`、`⛔ 取數失敗`、`⛔ 尚未設定`、`⬜ 未設定`（`shared/ui_semantics/rules.py`，已讀）；**本次不核准新狀態詞、reason_code、狀態映射**；區分僅以「說明原因」的文字候選呈現，字樣〔待 T5／G-5〕。
- **畫面目標**：使用者能分辨「哪些資料可查看（持倉事實）」「哪些結果因資料不足無法呈現」「哪些結果是計算口徑或正式契約未核准」，並知道**下一步在哪看到已有持倉資料（A10 入口→A50）**；只是解釋與路徑，**不得推導投資結論**，不得暗示「資料不足＝風險／安全」。

| 比較維度 | 方案 A：每區塊完整重複 Missing 與原因 | 方案 B（優先評估）：A10 保留主要原因與持倉入口；A20 四格各自保留 Missing、壓縮重複文字，詳細原因按需看 A60 | 方案 C：A10／A20 合併為單一狀態區 |
|---|---|---|---|
| 金融語意（防誤讀） | 最完整，但重複文字多，可能讓使用者把大量說明讀成「很嚴重」 | 每格仍明確 Missing、不被誤讀為 0；原因集中一處，口徑未核准與來源缺漏可分開說 | 四格個別缺漏／未核准原因被合併，**可能混同(a)(b)**，風險最高 |
| U1～U5 | 不違反 | 不違反：A10 位置／A20 四格／A50 入口全保留（U3、U4） | **違反已核准**：取消 A20 四格獨立區塊、改變 A10→A20 區塊結構（U3「A20 四格保留」、§0.1 順序）→**不採** |
| 手機首屏 | 最耗高度，入口被推遠 | 文字層最少，入口離 A00 約一卡（設計推測，未量測） | 最短，但以違反核准為代價 |
| 缺資料情境 | 三情境皆可，但冗長 | 三情境皆可；部分缺漏時 A20 逐格標(a)/(b)，細節在 A60 | 部分缺漏時單一區難表達逐格差異 |
| 成本 | 最低（沿用現況） | 低（只調文字密度與位置，無新元件） | 低，但須先經客戶裁示才可改已核准結構 |
| Gate | 無新增 | 不放行 G-1～G-5；不新增狀態詞；字樣〔待 T5／G-5〕 | **須客戶先裁示是否可改已核准區塊／順序**；未獲裁示不得採 |

**結論（作者候選，未經客戶裁示）**：優先評估 **方案 B**；方案 A 可作為文字密度過度壓縮時的備選；**方案 C 因取消已核准區塊／改變已核准結構而不採**（除非客戶另行裁示）。**不得以本比較宣稱 B 已選定、已核准或已驗收。**

#### 11.9.12 Streamlit 單層展開＋入口定位：設計候選（**全部未驗證**；本組唯讀，只寫候選，不實作）

**事實基礎（本組讀到的）**：`requirements.txt` 宣告 `streamlit>=1.59.1,<1.60.0`；本環境**未安裝 streamlit**，故以下行為**一律未在 1.59.x 實測**。repo 現況：`DEC-2026-10-30-02` 禁巢狀 expander，合併頁以 `flat=True` 小標題段落替代（`ui_v2/hld/page.py::_section` 註解）；expander 標題列一變即被當成新元件重建、預設收合（`ui_v2/hld/page.py` 內 `_HLD4_KEEP_OPEN_KEY` 的註解，紅隊 M2 實例）；既有錨點用法僅一處：`ui_v2/set/page.py` 以 `<div id="set-refetch">` 與 `<a href="#set-refetch">`（`ui_v2/sections.py::SET_NAV_ANCHOR`），**其真機跳轉行為本組未驗**；`ui_v3` 目前只有 `st.expander(...)` 預設收合的用法（`ui_v3/pages/mkt.py`）。

**三個技術問題（Stage 3 要回答；本節不裁）**
- **Q-a 展開來源**：`st.expander(expanded=…)` 的展開狀態在瀏覽器端；「點 A10 入口後把 A50 展開」若由伺服端旗標（例如 `session_state`）驅動，必然是一次 rerun，且展開區標題或參數一變即重建（上述 M2 實例）。
- **Q-b 手機收合／桌面展開**：伺服端沒有已知的可靠視窗寬度來源（本組**未查證** Streamlit 1.59 是否提供；`st.context` 是否可用、是否可靠＝未驗）。因此「手機收合、桌面預設展開」若要在伺服端分支，缺少可靠依據；若用 CSS 斷點（`ui_v3/shell/nav.py` 的 768px）則需要兩份 DOM 或純 CSS 展開機制。
- **Q-c 定位**：把視窗捲到 A50 需要錨點（hash）或 JS；`st.markdown`／`st.html` 對 `<a href="#…">`、`id`、`<details>`、`<script>` 的消毒與執行行為**未驗**。

**候選（作者整理；排序僅為設計偏好，非裁示，未驗）**

| 候選 | 做法 | 優點 | 風險／未驗 |
|---|---|---|---|
| **C-1　純 HTML 錨點＋`<details>`** | A50 以 HTML `<details>`／`<summary>` 呈現；入口為 `<a href="#a50">`（沿 `ui_v2/set/page.py` 既有寫法）；A51 以卡內第二層 `<details>`（非 Streamlit expander） | 不 rerun，故「是否重新讀 Active Sheet」問題不進入（rerun 路徑被繞開）〔未驗〕；單層 Streamlit 展開區〔未驗〕；錨點定位〔未驗〕 | `<details>` 能否被 hash 自動打開（純 CSS 做不到，通常需 JS）；消毒是否保留 `details`／`id`；`<details>` 內再放 `<details>` 是否算「巢狀 expander」＝待客戶／總管讀法（`DEC-2026-10-30-02` 字面禁的是 expander）；a11y（焦點、讀屏）需實測 |
| **C-2　`:target` 顯示切換（無 JS）** | A50 內容常駐於 DOM，以 `#a50:target` 的 CSS 控制顯示；手機預設隱藏、桌面（媒體查詢）預設顯示 | 手機／桌面分流由 CSS 斷點完成（回答 Q-b）；無 rerun | 非原生 expander，狀態字樣與鍵盤操作需自建；收合只靠再點別處／清 hash 的機制未定；隱藏內容的讀屏行為需實測；hash 在 rerun 後是否保留未驗 |
| **C-3　`st.button` 旗標＋`st.expander(expanded=flag)`＋錨點** | 入口為按鈕，設旗標後 rerun 以展開態重建 A50，再以錨點／JS 定位 | 全為原生元件、手機／桌面可用 key 控制 | **必然 rerun**（Q-a）；展開／定位是否重新讀 Active Sheet＝S1-2 明列的未驗技術 Gate（`ui_v2/hld/source.py` 檔頭自述不放任何快取，頁級是否以 session 暫存本組未讀完整）；標題或參數變動導致重建；仍缺 Q-b 解法 |
| **C-4　A50 內單檔 detail 以 `st.popover`／選單驅動** | A51 不用展開，改成每檔一個 popover，或用單一選擇器選檔後在下方顯示 detail | 不巢狀 expander | popover 放在 expander 內是否允許、手機觸控行為、焦點管理＝未驗；選擇器驅動＝rerun |
| **C-6　A51 桌面「列內詳情」（UI-3 優先候選的技術對應；未驗）** | 在 A50 寬表中，點「更多」後於該列下方插入詳情區塊（非 expander）；詳情以單一控制項開合；單檔詳情以基金名稱為標題 | 對應客戶 UI-3：對應列附近展開、屬於哪檔明確、不巢狀 expander；不指定實作 API | 原生資料表元件通常不支援列間插入；可能需以多段容器自繪列（影響 A50 寬表一致性與 a11y）；焦點管理、列多時效能、rerun 是否重讀 Active Sheet **全部未驗**；若不可行→回 UI Review 比較其他方案（側欄／選檔後下方詳情＝C-4 類） |
| **不推薦：C-5　手機改用 `st.dialog`／底部抽屜顯示持倉** | — | — | 新互動型式，須另經 UI Review；且 dialog 內容會觸發 rerun；不屬 S1 裁示範圍 |

**內部先例（不代表 Streamlit 渲染已驗）**：`ui_v2/exp/page.py` 已有 `<details class="exp-rowsrc">`（約 :442，grep 確認）作為 repo 內 HTML `<details>` 用法；本組未驗它在 Streamlit 1.59.x 的消毒、渲染與互動，亦不代表 C-1 可行。

**作者暫行排序（設計偏好，未驗，非裁示）**：先以 C-1／C-2 做**純前端可行性小測**（驗：hash 跳轉、`details` 消毒、斷點分流、焦點、不水平捲動、是否 rerun），再視結果決定是否需要 C-3；C-3 一旦被採用，**必須先過「展開不重新讀 Active Sheet」的量測**（§11.11 項 J-17）才可寫成已通過。這些都屬 Stage 3，**本節不得宣稱可行**。

### 11.10 分階段 UI Review 清單（客戶 2026-11-09 裁示：線框審查改為分階段；非核准最終設計、非施工授權）

| 階段 | 範圍 | 狀態 |
|---|---|---|
| **Stage 1　頁面操作與資訊可見度** | 主圖缺資料的降級卡（§11.9）；已取得持倉資料的易找度；A50／A51 逐檔密度；手機與桌面展開方式；既有核准狀態字樣（`◇ 資料未備`、`⬜ 無法判定`、`⛔ 取數失敗` 等）是否易懂。**僅限 UI／UX**；牽涉資料契約者只標「依賴」，不提前裁 | ~~本節提出供客戶審；未審~~ → 2026-11-09 客戶已就 S1-1／S1-2／S1-3 裁示（見 §11.9.5；有意識，非漏刪）；其餘 UI 細節（文案、欄位、辨識方式、技術做法）仍待 UI Review；**不是真機驗收** |
| **Stage 2　保留項（不因 Stage 1 通過自動核准）** | G-1～G-5；T2～T9 及 T10 未核准部分（T1 已裁＝B）；NAV 10 日與 D7；DIRECT 持倉；組合市值損益報酬；分母與類別占比；配息資料時點與正式狀態字彙；1Y 含息跨新版；是否重用 n／m／j（依 G-1） | 各項維持其原有狀態，不因本階段改變 |
| **Stage 3　最小 UI／Domain 實作批規劃** | 取得客戶授權後才規劃；含「展開不重新取數」的量測、390／1280 真實像素與首屏實測 | **本次不得進入** |

**Stage 1 需客戶審核的 UI 選項（最多三個）**

1. ~~**S1-1　主圖缺資料的首頁降級（§11.9）**：A（保留大卡）／B（精簡卡＋入口；作者推薦，未經裁示）／C（調整階層；須先裁示是否可改 A00→A10→A20）。~~ → **已裁示＝B**（客戶 2026-11-09 Stage 1；DEC-2026-11-09-03（以 DECISIONS 為準）；有意識，非漏刪）。A、C 不再列為選項。
2. ~~**S1-2　A50 預設狀態與入口落點**：持倉預設收合（沿 U4）而以入口展開，或在有可用列時預設展開；依賴：Streamlit 展開行為與「不重新取數」未驗、合併頁容器不得巢狀 expander（`DEC-2026-10-30-02`）。~~ → **已裁示**：手機預設收合、點入口後展開並定位；桌面有可靠證據存在可用持倉列時預設展開；「展開／定位／rerun 是否重新讀 Active Sheet」仍未驗（Stage 3 技術 Gate）；禁巢狀 expander 維持（§11.9.5、§11.9.9、§11.9.12）。
3. ~~**S1-3　A50／A51 逐檔密度與桌機／手機展開方式**：手機單欄摺疊列的欄位取捨（欄位集合仍屬 T6）、桌面寬表是否多顯示代碼與取得時間；依賴：T6、T8、T9 未裁，**只審排版，不裁欄位語意**。~~ → **已裁示**：手機單欄精簡逐檔卡、桌面完整寬表；T6 欄位集合與語意仍未核准，只定排版密度、資訊階層、展開方式、欄位容器（§11.9.10）。

**（2026-11-09 更新）本表以下三題已由客戶 Stage 1 裁示；§11.9.5～§11.9.12 為依裁示更新的線框與交互規格，§11.11 為驗收清單草稿。**

**Stage 1 通過後的效力**：僅表示客戶同意該 UI 方向可進一步規劃；**不解除** Stage 2 任何一項，**不授權** Streamlit／`ui_v3` 實作。

**限制與未驗（本輪新增，作者揭露）**：（8）§11.9 與 §11.10 由設計文件組單組撰寫，未經獨立 QA；（9）390／1280 像素、首屏高度、入口是否落在首屏皆為設計推測，未量測；（10）展開／點擊是否重新讀 Active Sheet 未驗；（11）舊 UI 行號為約略位置，未逐行複核；（12）DEC-2026-11-09-02 由另一組登記，其編號與內容以 `docs/DECISIONS.md` 為準，本節對 T1、N 的轉述以作者所得派工要點為據，非逐字。

### 11.11 Stage 1 交互驗收清單（**設計規格，非實測**；各項皆「未驗」；不是真機驗收，不得據此宣稱通過）

> 用途：未來 Stage 3 若獲客戶授權進入施工規劃，本清單是 Stage 1 UI 的驗收條件草稿。每列都**未執行**；「依賴 Gate」欄只標依賴、不代裁。390／1280 真實像素、首屏預算、輔助技術與真機行為皆須實測（§11.8 限制 5）。作者＝設計文件組，**未經獨立 QA**。

| # | 驗收項（預期行為） | 依賴的未核准 Gate／未驗點 |
|---|---|---|
| J-1 | **（暫行：可用持倉列判定來源與門檻客戶未定義；UI-2：候選對映／未獨立驗證／不得直接升格 production contract）** A10 入口只在「有可用持倉列」時出現，入口存在條件須可追溯到證據（§11.9.9 兩項同時成立）；未選 Active、讀取失敗、來源完整但無可用列時**不出現**，也不導向空內容；`holding.kind`／`problems`／至少一列的對映仍標 **NOT VERIFIED** | 「可用持倉列」對映待客戶／QA 確認；入口文案〔待裁示〕 |
| J-2 | 入口不含任何檔數、涵蓋率、占比、金融數字、投資建議；不是 chip、不新增首屏名額 | N＝C、T1＝B 已裁；是否仍計入 44 首屏預算〔待 UI Review〕 |
| J-3 | 手機：預設 A50 收合；點入口後 A50 展開**並**定位至 A50（前次裁示），不是只捲到仍收合標題列；重複文字（A10／A20）不壓過持倉入口 | 技術做法〔§11.9.12 候選，Stage 3 Gate，未驗〕 |
| J-4 | 手機定位後可辨識目前在「完整持倉」：標題列可見、展開狀態可見；不被文件流內頁首導覽或 Streamlit 頂列遮住；無水平捲動；焦點落在 A50 標題列、不迷失 | 偏移值、焦點行為未驗；辨識方式〔待 UI Review〕 |
| J-5 | **（暫行：可用持倉列判定來源與門檻客戶未定義；UI-2 候選對映，未獨立驗證）** 桌面：**僅在證據成立時**有可靠證據存在可用持倉列→A50 預設展開；無 Active／取數失敗／無合法持倉→不展開空表、不顯示導向空內容的入口 | 手機／桌面分流機制（Q-b）未驗；證據對映同 J-1 |
| J-6 | 部分缺漏：可用列保留；缺項格顯示合法 Missing＋原因；被略過者不在表內、由 A60 列出；不因展開推定完整、健康、安全 | G-5（部分狀態詞）；原因字樣〔待裁示〕 |
| J-7 | 完全未取得：無空入口、無空表、不寫「持倉 0」；A50 退為一列狀態文字，狀態句與 A00 一致 | G-5；(c)「沒有有效持倉列」字樣只在來源完整證據成立時使用 |
| J-8 | A10 降級卡保留已核准資料不足狀態＋一句原因；**原因說明可區分(a)原始資料缺漏／取數失敗與(b)計算口徑未核准**，兩類不混同；**未新增正式狀態詞、reason_code 或映射**（僅用已核准字樣＋說明文字候選）；U3 簡潔 SPEC 與必要資料限制**仍可見**（不因精簡消失）；不畫圖、不出現百分比或 100%、無假數據／假圖／新公式 | D2-C、G-1；SPEC／限制字樣〔待 T5〕 |
| J-9 | 順序不變：A00→A10→A20→A30→A40→A50／A51→A52→A60；持倉明細未被搬到主圖前；A20 四格各自保留；**A20 無可用正式計算維持 Missing**；(a)/(b) 原因在四格以極短標記區分、詳細原因按需（A60）查看，重複文字不壓過持倉入口；不採把 A10／A20 合併為單一區（方案 C，違反已核准區塊與順序） | G-4；視覺密度（A20 單行）〔待裁示〕 |
| J-10 | 手機逐檔卡：單欄、不橫向捲動、長名稱換行；主層為已確認事實、次層按需展開；缺資料整卡保留 | **T6**（欄位集合與語意未核准）；T8／T4／T10 不顯示 |
| J-11 | 桌面寬表：逐檔易讀、可比較；A51 以**非巢狀列內詳情**（優先設計候選）按需看單檔更多來源／日期／幣別／限制；詳情與列對應清楚（標題含基金名稱）、不錯列、不造成焦點迷失、寬於容器時整頁不橫溢 | **T6**；列內詳情元件／焦點管理／rerun 行為為**技術未驗**（§11.9.12 C-6）；若不可行回 UI Review 比較其他方案 |
| J-12 | 全頁無巢狀 expander（A50 內不再放 Streamlit expander）；A51（手機「更多」、桌面列內詳情）不形成巢狀 expander，以非展開區元件呈現 | `DEC-2026-10-30-02`；`<details>` 是否算巢狀＝待讀法確認；候選未驗 |
| J-13 | 標籤與觸控：入口與逐檔「更多」觸控目標≥48px（`ui_v3/shell/nav.py::TOUCH_MIN_PX`）；狀態不只靠顏色；鍵盤可操作；讀屏可讀出展開／收合狀態 | 輔助技術實測未做 |
| J-14 | 不新增排名、Top N、建議、分類推論、新 chip、假數字、假圖、占比、涵蓋率；不稱淨投資金額為成本／市值／總資產／本金 | T1＝B、N＝C、D2-C、淨投資金額語意＝B |
| J-15 | 保留 Gate 不被解鎖：T6、T8、T9、T10、G-1～G-5、NAV 10 日（D7）、DIRECT、配息、組合損益、分母占比、跨新版 1Y 含息、D2 Schema；FX 閘門維持關閉 | 各項維持原狀態，不因 Stage 1 通過放行 |
| J-16 | 三態皆不顯示「過期／正常」類 NAV 標示、不顯示「完整／健康／安全」推定 | D7；`DEC-2026-11-05-03` |
| J-17 | **（未來技術驗收條件；現為未驗、不得宣稱已通過）** 入口點擊、A50 展開、A51 展開、定位、頁內 rerun，是否重新讀取 Active Sheet（**留待 Stage 3 真實量測**）——須以量測（讀取次數／日誌）證明；若會重新讀取，退回 Stage 3 重新評估，不得為求入口而放寬 | Stage 3 技術 Gate；`ui_v2/hld/source.py` 自述不放快取；頁級暫存本組未讀完整 |
| J-18 | 手機／桌面分流機制（「手機收合、桌面條件式展開」）在 390、768、769、1280 皆行為一致；不依賴不可靠的伺服端視窗寬度 | Q-b 未驗；`ui_v3/shell/nav.py::MOBILE_MAX_PX`＝768 為現行斷點 |

**狀態宣告**：以上各項皆為**設計規格、未驗**；Stage 1 客戶審核通過僅表示 UI 方向可進一步規劃，**不解除 Stage 2 任何一項、不授權 Streamlit／`ui_v3` 實作、不構成 Preview 或真機驗收**（`PROJECT_RULES.md` §13.6 第 6 點：功能已實作 ≠ Preview 已驗 ≠ 正式 Cloud／真機已驗）。

**限制與未驗（本輪 Stage 1 更新，作者揭露）**：（13）§11.9.5～§11.9.12 與 §11.11 由設計文件組單組撰寫，未經獨立 QA，不是真機驗收；（14）客戶 Stage 1 裁示為總管轉述的要點，非逐字，DEC 編號與內容以 `docs/DECISIONS.md` 為準（本檔寫作時該 DEC 由另一組登記，未核對其最終文字）；（15）本環境未安裝 streamlit，§11.9.12 所有 Streamlit 行為（巢狀 expander 限制於 1.59.x 的現況、錨點／`<details>`／JS 的消毒與執行、視窗寬度來源、rerun 與展開狀態）皆**未驗證**，只是設計候選；（16）「可用持倉列」「可靠證據」與程式證據的對映是作者讀碼（`ui_v3/adapters/assets_source.py`、`services/v2_tables/alo_holdings.py`），未實跑、未經客戶或獨立 QA 確認；（17）現行頁首導覽（文件流內、不吸頂）取自 `ui_v3/shell/nav.py` 讀碼，未在真機驗證，且與 §11.4 舊句「底部五格」不一致，已於 §11.9.7 就地更正；（18）舊 UI 行號為約略位置；390／1280 像素、首屏高度、入口是否落在首屏皆為設計推測，未量測。（19）**2026-11-09 UI Review 補強（Batch 2／3；引用 DEC-2026-11-09-04，以 `docs/DECISIONS.md` 為準，本檔寫作時該筆由另一組登記，未核對其最終文字）**：客戶 UI-1／UI-2／UI-3 為經總管轉述的要點，非逐字；A10／A20 三方案比較中 B 僅為「優先評估候選」，客戶並未選定 B；A50 暫行對映仍標「候選對映／未獨立驗證／不得直接升格 production contract」；A51 桌面列內詳情為優先設計候選、技術可行性未驗；本批線框全為設計、未量測，不是手機或 Cloud 驗收；本批由設計文件組單組撰寫，未經獨立 QA。

## 12. 健診「資料涵蓋 N／M 檔」呈現草稿（最小規格；只提候選，不正式定義、不硬算）

> **2026-11-09 客戶第二則裁示 N＝C（有意識，非漏刪；登記 DEC-2026-11-09-02〔已登記，以 `docs/DECISIONS.md` 為準；舊標「登記中」已更新，非漏刪〕，本檔不重述全文）**：暫不顯示新定義的「資料涵蓋 N／M 檔」；K2、K3 不升格；不算 n−j、n−m−j；不以讀取成功檔數冒充 Active Sheet 覆蓋率；舊 n／m／j 契約不變、不刪；New UI2 是否重用 n／m／j 依 G-1 另議；BL-0545 維持 NOT VERIFIED。無正式涵蓋計數時，只可呈現**已有核准字樣**的來源狀態與具體缺漏原因（見 §12.3 第三欄），**不得自創狀態詞**。下文 §12.1～§12.5 為裁示前草稿，保留作候選紀錄，**其中凡寫「待裁示」之 N 口徑，現況＝暫不顯示**。
>
> **性質**：呈現草稿，**不定義**正式分母、**不新增**健診分數、等級、Risk Cap 或投資訊號。「資料涵蓋 N／M 檔」目前**沒有**核准字樣，也沒有正式計數契約；`shared/ui_semantics/rules.py` 的 `shell_status_partial`（`{ok}／{total} 項已取得`）只適用 🌍 頁的狀態列，其分母界線見 `docs/v2/80` §17.4「計數分母的界線」，**不可類推**到持倉。「本次已讀取 N／M」**不是**真實持倉的正式覆蓋率、也不是資料准入（BL-0545 的真實 Active Sheet 覆蓋率 **NOT VERIFIED**）。

### 12.1 先看現行正式計數：ui_v2 HLD-0 ①的 n／m／j

- 規格：`docs/v2/44` 第七節第三小節之八其一 (a-2)；客戶核准 `DEC-2026-10-17-07`；程式 `ui_v2/sections.py::hld_count_values`、`hld_holding_count`。三個數：持有 n 檔、`◆ 需要注意` m 檔、`⬜ 無法判定` j 檔。
- **單位**：不重複基金代碼（`fund_groups` 是保單×基金的逐筆分組，同一檔在兩張保單只算 1）；j＝`HLD-1` 彙總的「沒有進入偏離評估」的不重複檔數，不論成因；已有偏離列的檔算在 m，不重算進 j。
- **分母不成立時不寫數**：保單分頁有持倉列沒寫進持倉（`_omitted_rows`）時 n 為 None（畫面寫「持有檔數無法判定」）；紅燈、無持倉、門檻未設時整組計數不列。
- **刻意不列**：n 減 m 減 j 的差（44 明文）。
- 這組計數**只存在於 ui_v2**；`ui_v3` 沒有合法取得途徑，接入屬 G-1 PORT。

### 12.2 N 與 M 的候選來源（母集合不混用）

| 候選 | M（母集合與單位） | N（條件與單位） | 計數條件與依賴 | 狀態 |
|---|---|---|---|---|
| K1　沿用 n／m／j，不引入 N／M | n＝不重複基金代碼（HLD-2） | —（不另設 N） | 既有契約；`ui_v3` 需 G-1 PORT | 字樣已核准（ui_v2）；New UI2 接入待裁示 |
| K2　已進入評估 N／持有 M 檔 | M＝n | N＝n－j（j＝`HLD-1._unevaluated_count`） | n 為 None 時整句不顯示；門檻未設時現行三計數不列，本候選是否照辦待裁；**44 明文不列此差** | 〔待裁示〕~~：新增衍生計數，與 44 既有取捨相反~~ → **N＝C：暫不顯示、不升格**（2026-11-09）；與 44 既有取捨相反之事實不變 |
| K3　已取得淨值 N／持有 M 檔 | M＝n | N＝在 `nav` 表至少有一列的不重複 `fund_code` | 受 NAV 10 日（D7）、累積表出處閘門 `NAV_HISTORY_PROVENANCE_VERIFIED`、幣別閘門（`withheld`）影響；N 的定義取決於未裁項 | 〔待裁示〕~~：只提候選~~ → **N＝C：暫不顯示、不升格**（2026-11-09） |
| K4　逐檔五維 `n_scored`／`n_applicable` | 單位是**維度**，不是檔 | 來自 `services/health/grade.py::compute_4d_health` 的 `coverage`（`DEC-2026-11-06-02`） | 屬逐檔列（A50，§10.3）；**不得與檔數 N／M 共用同一種「N／M」字樣** | 資料有；呈現字樣待裁示 |
| K5　BL-0545 三層分母（唯一基金／成功取數／各維適用） | 唯一基金（production 以 `resolve_full_keys` 分組；canonical 身份僅 shadow） | 成功取數、各維適用 | 真實 Active Sheet 未量測 | 〔不顯示〕：NOT VERIFIED |

**不得混用的四種母集合**：保單分頁的**列**、`holding` 表的**持倉（保單×基金）**、不重複**基金代碼**、**維度**。畫面上的 N／M 必須點名單位（例：「檔（不重複基金代碼）」），字樣待核准；不得讓 N 取自一個母集合、M 取自另一個。

### 12.3 六種資料狀態的區分（沿用既有證據，不新增詞彙）

| 狀態 | 既有證據（檔案／欄位） | 既有核准字樣 | 缺口 |
|---|---|---|---|
| 讀取失敗 | `ActiveSourceError`；`ui_v3/adapters/assets_source.py` 的 `PROBLEM_HOLDING_READ_FAILED`；失敗分頁（`skipped_tabs`）；`nav_dividend` 的 `errors[fund_code]` | `⛔ 取數失敗`（`rules.py` `fetch_failed`） | 無 |
| 未讀取 | 無 Active（`source_coverage`＝`not_selected`）；分頁冷卻／短路／預算未讀（`alo_holdings.py` 的「可能屬於本次未讀的分頁」） | 無（BL-0542 G-5，§8） | 缺 `unread` 字樣 |
| 資料缺漏 | `skipped_holdings` 的原因句（欄位空白）；`nav_absent`；`missing_supplement` | `◇ 資料未備`（`missing`） | 無 |
| 解析失敗 | `invest_twd_parse_errors`（「淨投資金額無法解析」）、`bad_rows`、鍵非字串的略過原因 | 無（G-5） | 缺字樣；是否與「資料缺漏」同字待裁示 |
| 未設定 | `user_param_unset`（`⬜ 未設定`：使用者自己的參數留空）；`not_configured`（`⛔ 尚未設定`：資料來源或設定尚未設定） | 兩者皆已核准；使用者參數留空**不計入**資料狀態件數、不進 β 排序（`rules.py` 註記，`DEC-2026-10-20-01`） | 無 |
| 真正沒有資料 | 僅在來源完整證明成立時：`source_coverage`＝complete 且持倉表空；`nav_state`＝`no_data`；配息的「各來源皆成功取數且無紀錄」 | 無 | 無證據時一律 `⬜ 無法判定`，**不得寫「沒有」** |

- N 不含狀態不明的檔；缺資料的檔**列在 M 內、不排除、不算作符合**（44 第七節第三小節之三）。
- 「本次已讀取 N／M」這類字樣**不得**使用「覆蓋率」措辭（evidence E3 N9），不得暗示涵蓋真實持倉全集。

### 12.4 呈現位置與最小規格

- **資產頁**只放與判讀直接相關的一行文字：390px 放 A00 狀態容器第二行（文字，**不是 chip、不增名額**）；1280px 放 A50 表頭。完整來源健康診斷歸 ⚙️ 設定→資料健康度（`docs/v2/80` §16.2、`PROJECT_RULES.md` §13.2 第 8 點）。
- 分母為 None 時，**不顯示 N／M**，改顯示 `⬜ 無法判定` 與原因（沿 `hld_holding_count` 的做法）。
- 不與原字母 Grade、覆蓋維度數、正式資料准入合併成單一「健康」顏色或分數（`DEC-2026-11-06-02`、§10.1 三群互相獨立）。
- 字樣、母集合名稱與是否採 K2／K3，皆〔待裁示〕；本節不提供可直接上畫面的新文案。

### 12.5 此草稿是否具備合法分母與資料狀態證據？——**部分**

- **有**：M（不重複基金代碼的持有檔數 n）與 j（未進入評估檔數）是**已核准的正式契約**，且分母不成立時有「不寫數」的既有做法；六種狀態中讀取失敗、資料缺漏、未設定三種已有機器證據與核准字樣，其餘三種有機器證據但缺字樣。證據檔：`docs/v2/44`（之八其一 (a-2)）、`DEC-2026-10-17-07`、`ui_v2/sections.py`、`services/v2_tables/alo_holdings.py`、`ui_v3/adapters/assets_source.py`、`shared/ui_semantics/rules.py`、`docs/evidence/d2_contract_candidates_returns_identity_holdings_2026_11_08.md`（E3 §2.D）。
- **無**：①「資料涵蓋」的 N 口徑（K2、K3 皆未核准）；② `unread`／解析失敗／真正沒有資料的核准字樣（G-5）；③ New UI2 側的 n／j 組裝（`ui_v3` 無合法取得途徑，G-1）；④ 真實 Active Sheet 覆蓋率（BL-0545，NOT VERIFIED）。
- 結論：**分母 M 與狀態證據有、N 的口徑與部分字樣無**；本草稿不正式定義 N／M，也不硬算。
- **2026-11-09 N＝C 後的現況**：不顯示新定義的「資料涵蓋 N／M 檔」；資產頁只可寫已有核准字樣的來源狀態（`⛔ 取數失敗`、`◇ 資料未備`、`⬜ 未設定`／`⛔ 尚未設定`、`⬜ 無法判定`，見 §12.3）與具體缺漏原因，不得寫「已讀取 N／M」類暗示覆蓋率的文字。

**限制**：作者單組、未獨立 QA；讀碼未實跑；未量測任何真實 Active Sheet；`ui_v2` 契約是否同意搬入 New UI2 屬 G-1，本節不預判。
