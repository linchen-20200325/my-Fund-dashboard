# 82｜New UI2 💼 我的資產：UI × Data × Evidence 施工前設計草案（待客戶核准）

> **定位**：ChatGPT 產品／資料契約初稿，2026-11-04。**非已核准 wireframe、非公式或資料語意裁示、非程式實作授權**。此檔不取代 frozen `44`、`79`、`80`、`73`、`74`；同一事實以原正式契約為準。先驗既有 capability／欄位，再由客戶核准具體版面。不得因本草案把舊 UI 程式直接搬入 `ui_v3`。
>
> **讀碼範圍**：`services/v2_tables/alo_holdings.py`、`services/v2_domain/{holdings,deviation}.py`、`services/v2_tables/nav_dividend.py`、`ui_v2/{hld,alo}/{source,logic}.py`；對照 `docs/v2/{73,74,79,80}_*.md`。此為 ChatGPT 單組盤點，**尚未由獨立組逐欄複驗**。
>
> **2026-11-04 專案 AI 獨立稽核（單組、三份獨立報告；非客戶裁示）已核實 §2／§4 的主要敘述**：結果見第 8 節；§2、§4 內以【稽核更正】標示就地修正處，ChatGPT 原文保留（錯的字句加刪除線）。本檔仍是**待客戶核准草案、非規格**；主圖資料欄位、公式、狀態詞與 Gate 的登記位置為 `docs/BACKLOG.md` BL-0542，本檔不重複成文。以下「候選接線」不保證已存在 New UI2 可直接調用的 facade；實作組必須在核准後驗證精確 schema。

## 1. 產品目的與顯示優先序

💼 為「持倉＋資產配置＋配息」單頁，不回復舊兩頁；行動建議不自行產生。手機 390px，第一屏讓使用者明確知道：① 我的資產狀態是否可判讀 ② 有哪些缺值／未評估需要注意 ③ 核心資產數字與配置入口 ④ 可以查看的主要圖表。其他資料下沉，不做 Top N 截斷，不遺失完整持倉與 OneBrain evidence。

### 1.1 手機與桌面草圖（區塊順序候選，非最終像素稿）

```text
390px Mobile                            1280px Desktop
[💼 我的資產] [資料狀態／關注]         [💼 我的資產] [狀態／注意] [資料時點]
[摘要 2×2：資產／損益／報酬／配息]       [摘要四格，缺值仍佔位置]
[配置實際 vs 目標：主要圖]              [配置實際 vs 目標主圖] [配息／近日事件]
[SPEC：基準／單位／範圍／資料日]         [SPEC + 主要差異依據]
[偏離項摘要 + 查看偏離明細]              [逐檔／類別完整展開區]
[配息／近期事件（正式日期優先）]          [持倉、淨值、配息、資料缺口]
[▸ 全部持倉／單檔淨值與配息]
[▸ 資料限制／分類／來源證據]
```

預設「摘要 2×2」延用 `80 §7.2`：總資產｜損益｜報酬｜配息，但**不宣稱四值已有同口徑、可跨幣別、可匯總的已核准計算**。任何值未具備正式算法時顯示「◇ 資料未備／⬜ 無法判定」，不得造數字或以成本冒充市值。圖表必須有已核准口徑（成本或市值）及對應合法來源；不同幣別不可無匯率硬加總。

【稽核補充（專案 AI；非客戶裁示）】

**與 `80 §7.2`（已凍結 implementation input）的差異；核准前以 `80 §7.2`、`44` 為準：**

| 項目 | `80 §7.2` | 本草案 §1.1 |
|---|---|---|
| 桌機「基金占比｜各檔區間報酬」區 | 有 | 無 |
| SPEC 列、偏離摘要（含查看偏離明細）、資料限制／來源證據展開區 | 無對應區塊 | 新增 |
| 頁級狀態 | β 階梯 | 只寫「資料狀態／關注」，無 β 頁級字樣（BL-0536-W2） |

- 摘要 2×2 排在主圖前，與 `PROJECT_RULES.md` 13.5 第 1 點的資訊順序並不衝突：依據是 D-5B（`DEC-2026-10-30-02`，客戶裁示 💼 首屏保留四項 compact summary slots，缺值仍佔位）。
- 首屏名額（≤5；`DEC-2026-11-03-11`，降級情境也要 ≤5，Status Bar 純文字不計）逐元素讀法：手機首屏 = 頁級狀態 chip 1（正常情境）＋ 摘要四值 4 ＝ 5；若「關注」另算一枚 chip 即為 6。主圖、SPEC、偏離摘要是否計入名額取決於元素形態（chip／核心數字才計）。**Status Bar「n／m 項已取得」是否計名額仍待客戶確認**（HANDOFF、BL-0536）；降級情境（摘要格缺值仍佔位）是否維持 ≤5 須在客戶核准線框時逐元素點數，本草案不宣稱已達成。

## 2. 逐區塊資料串接矩陣（施工前須複驗）

| 區塊／元件 | 候選正式資料／欄位 | 已有位置／能力 | 確定性與 Gate | 不可做的事 |
|---|---|---|---|---|
| 頁首持倉健康／β 結論 | ~~holding、policy、nav、dividend、setting、market_indicator 的正式載入與狀態~~【稽核更正：`load_alo_tables_active` 只回 holding、policy 與略過／失敗紀錄；nav、dividend、設定、匯率各走不同 L2 入口，組裝在 `ui_v2/{hld,alo}/source.py`、`live.py`】 | `alo_holdings.load_alo_tables_active`、`ui_v2/hld/logic.py`、`ui_v2/alo/logic.py`；D-3 P3／β 見 `74` | **重用既有結論語意**，核對 skipped_tabs／skipped_holdings 對結論的影響；New UI2 adapter／viewmodel 路徑待定。【稽核更正：判定本體在 `ui_v2/**`，ui_v3 現無合法取得途徑，需 PORT（Gate G-1）；詳見第 8 節】 | 不以部分讀取當成「無持倉／正常」，不在 UI 自建狀態 precedence |
| 四項摘要 | holding／policy／nav／dividend 與相關 user_setting、FX | `alo_holdings`、`nav_dividend`、`v2_domain/holdings`、既有 HLD／ALO domain outputs | ~~**欄位級 mapping 待複驗**~~【稽核已複驗：四項皆無算法；`ui_v2/asset/overview.py` 的 `summary_strip()` 硬編碼 Missing（D-5A／D-5B，`DEC-2026-10-30-02`），FX 閘門關閉（`services/v2_tables/market_indicator.py` 的 `FX_OBS_DATE_RULE_VERIFIED = False`）】：無已核准跨幣別匯總公式不得顯示假總值 | 不新增匯總公式；缺值不填 0；不混淆報酬率和損益 |
| 配置主圖：實際／目標 | holding.bucket、holding.cost_twd 或 holdings×latest NAV×FX；user_setting 的 `alo_target_weights`、`alo_basis`、`alo_tolerance_pp`【稽核補充：另有草案漏列的 `alo_bucket_names`；三鍵皆無預設；類別加總、分母、比重、差額、帶內外的組合算式在 `ui_v2/alo/logic.py`（`_category_values`、`_build_alo2`），L2 `v2_domain/holdings.py` 只有原子】 | `ui_v2/alo/logic.py` ALO-2／ALO-4；`v2_domain/holdings.py`；`v2_domain/deviation.py` | 正式選定**成本／市值基準**才呈現；僅用已驗證 mapping；百分點差額與容許帶必須附設定來源；缺 FX 不轉用成本 | 不 UI 重算、不能自訂容許帶或默認 0、不能將未分類靜默分配 |
| 偏離摘要／明細 CTA | ALO-2 類別差距、HLD-1 正式逐檔偏離與門檻、未評估件數 | `ui_v2/{alo,hld}/logic.py` 既有 domain / P3 β；`73` | 顯示為「規則比較的事實」；點擊只展開既有明細；不能當投資再平衡指令。【稽核更正：`v2_domain/deviation.py` 只有比較方向、差額與失敗優先；HLD-1 逐檔走訪在 `ui_v2/hld/logic.py::deviation_rows`，ui_v3 需 PORT】 | 不提供一鍵再平衡、不造 action state |
| 近期配息／配息日曆 | dividend rows、已核准 date semantics、status；holdings 與 NAV 供必要確認 | `services/v2_tables/nav_dividend.py`、`79 §17.12`、`80 §7.2`、`73 HLD-3/HLD-6` | **日期契約 Gate**：~~正式日期優先、deterministic estimate 只作 fallback~~【稽核更正：此句只存在於規格，程式沒有。dividend 列欄位為 `fund_code, ex_date, pay_date, div_per_unit_orig_ccy, ccy, div_kind, fetched_at`（無 `status`、無 `record_date`）；`pay_date` 現一律空；未來日期的 `ex_date` 被 L2 丟棄；推估引擎 `services/dividend_calendar.py` 不在 ui_v3 允許前綴，且目標為配息基準日（≠44 的 ex_date 除息日）】；`pay_date` 未完成 amendment 前不得說「實際入帳日」；資料來源日期類型逐欄標 | 不把除息日當入帳日、不用缺日期預估正式付款、不把推估混成已確認 |
| 持倉明細（全列）／單檔展開 | holding_id、fund_code、~~政策／級別~~【稽核更正：holding 無政策／級別欄，只有 `bucket`】、單位數、幣別、NAV 日期／點、配息序列；必要 skipped reasons | `alo_holdings.build_alo_tables`、`v2_domain/holdings.py`、`nav_dividend`、`73 HLD-5/HLD-6/ALO-6` | 全列保留，單檔展開只影響畫面；原始 identity、同鍵衝突與 FX gate 不變【稽核補充：同鍵多列時 hld 與 alo 兩頁各自合併（hld 去空白比四欄、alo 不去空白比 bucket／ccy）；同鍵不同幣別 raise，不是逐列缺值；`last_synced_at` 是核對日 12:00 台灣時間的推定值，非讀取時間】 | 不用 Top N 切掉持倉；不同基金不能因同名合併 |
| 異常／資料健康摘要 | Active Sheet 狀態、settings、NAV、FX、配息與 skipped/unread/failed | `alo_holdings.load_alo_tables_active`、`ui_v2/{hld,alo}/source.py`、`services/v2_tables/settings_store.py` | 首屏顯示與判讀相關的 Missing／失敗；完整來源健康明細由 ⚙️ 承接（涉及 `BL-0540` 先守現行 44）。【稽核補充：Active Sheet 未設定與讀取失敗可由 `ActiveSourceError` 的 code＋reason 區分，無 fallback；判定 `is_no_active` 在 `ui_v2/active_gate.py`；ui_v3 狀態詞只有 ok／missing／failed／stale／undetermined 五個，無 `not_configured`／`unread`／`skipped`／`unknown currency`；`user_setting`／`market_indicator` 讀另一本 `SETTINGS_SHEET_ID`（服務帳戶），不隨 Active Sheet 切換；`refetch_nav` 仍走舊 `POLICY_SHEET_ID`，ui_v3 不得呼叫】 | 不暴露 secret、內部 reason code、traceback；unavailable ≠ neutral |

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

【稽核補充（專案 AI；非客戶裁示）】`80 §3.2` 已把 `ui_v2/{hld,alo}/logic.py` 的計算分類為 PORT（住在 L3 的領域計算）；因此 B 路徑中「合法 L2／shared domain」今天只涵蓋原子與資料表建構，衍生值仍待 PORT。可行路徑比較如下（1 為最快、2 與 3 屬 Gate、4 與 5 禁止）：

| 路徑 | 正確性與投資語意風險 | 重用度 | 修改範圍與回歸風險 | 速度 | Token／Model 成本 | 失敗降級路徑 |
|---|---|---|---|---|---|---|
| P1 adapter 只取事實、不產生衍生值 | 低（不算任何衍生數字） | 中（只重用資料表） | 小；須配合 Preview 執行期守衛（G-2） | 最快；合法、不需新 Gate | 低 | 缺值 ViewModel 照實顯示 ◇ 資料未備 |
| P2 完整 PORT 到 `services/v2_domain` | 最低（單一公式源） | 最高 | 大：動 ui_v2 薄包裝與 golden、兩個 ownership lock 測試要改 | 慢 | 高（formula／data semantics 等級，需獨立稽核與 Model／Effort 重估） | 對照 golden 回退 |
| P3 分階段 PORT，先成本口徑最小核心 | 低（成本口徑不依賴 FX 與 NAV） | 高 | 中；每階段各自稽核 | 中 | 中至高 | 閘門關閉下成本口徑仍可運作；市值面維持 Missing（稽核 A 推薦） |
| P4 `ui_v3` 重寫公式 | 高（兩份公式失同步） | 0 | — | — | — | **禁止** |
| P5 `ui_v3` import `ui_v2` | 高（耦合） | — | — | — | — | **禁止** |

**建議第一切片 B0**：P1＝資料契約＋fixture＋缺值 ViewModel（不產生衍生值），不需新 Gate；衍生值待 P2／P3 的 Gate 裁示後再接。**配息暫用 D1**：只顯示已發生的除息列、不顯示 `pay_date`、其餘 ◇ 資料未備。以上為稽核建議，待客戶核准。

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
- Q3：手機「配息／近期事件」在主圖前或後？只調 presentation priority，不改資料語意。
- Q4：細節區的基金／保單分組、已被略過來源的警示層級，以及 44 的預算如何在新合併頁保持正確？
- Q5：BL-0538／BL-0540 與 frozen 44 承接、Missing 用字等另案 Decision Gate；本檔不代裁。
- Q6：正式配息日期／估算 fallback 與 44 amendment（BL-0534）未完成前的最小合法顯示。

### 6.1 稽核新增問題（專案 AI 新增，Q1～Q6 原文不動；非客戶裁示）

- Q7：PORT 範圍擴大（配置、偏離、市值、β 分類、NAV 10 日門檻、`is_no_active`）是否核准，屬 Gate（G-1）。
- Q8：四項摘要何時、以何種公式解除 Missing（G-4）；在此之前維持 D-5A／D-5B。
- Q9：誰負責設定目標比重、容許帶、基準？ui_v3 第一階段唯讀，💼 沒有合法寫入面。
- Q10：hld 與 alo 兩套同鍵合併規則以何者為準。
- Q11：部分缺值時分母不完整的呈現方式（市值基準缺 USD 匯率會顯示 100%，須連同「合計未涵蓋」揭露）。
- Q12：BL-0411（頁級燈 production 閘門）是否視為已解除。
- Q13：「資料不足」與「◇ 資料未備」的分工（BL-0540 G-2）。
- Q14：期間配息合計是否核准用「目前單位數」；配息 `pay_date` 與推估日期（BL-0534）。
- Q15：BL-0536-W1（`chart_empty` 字樣）、W2（β 頁級字樣）、BL-0369／H4（freshness 門檻）、Status Bar 與降級首屏的計數讀法。

**Decision Gate 候選（只記錄，不自行開工；正文與登記位置在 `docs/BACKLOG.md` BL-0542）**：G-1 PORT 範圍；G-2 放寬 Preview 執行期守衛並新增載入端 composition root；G-3 配息推估引擎如何進 ui_v3；G-4 摘要四格口徑；G-5 狀態詞對映與 `no_holding`／`partial`／`normal` 字樣（`shared/ui_semantics/rules.py` 目前無核准字樣）。

## 7. 本次 PR 的 Definition of Done

此 PR **只完成施工前產品草案與資料 mapping 候選**。Merge 不等於客戶已核准設計、不等於 UI 已完成、不等於可開始 💼 程式。下一步為專案 AI 的獨立欄位契約驗證（唯讀報告）＋客戶 wireframe 核准，再另批實作。仍維持 Silent Autonomous Cruise。

【稽核註記】「專案 AI 的獨立欄位契約驗證」這個中間步驟是本草案的提議，不是客戶裁示原文（`DEC-2026-11-03-12` 只寫核准後專案 AI 才實作）；第 8 節即為該驗證的第一輪結果（單組，非客戶裁示）。

## 8. 獨立稽核核實結果（專案 AI，2026-11-04，單組；非客戶裁示）

> 基準 main 21296a0d；三份獨立稽核（資料接線 A、B，文件治理 C）加合成資料 trace；稽核報告不納入 repo，本節只留結論，與下列 file 事實不符時以程式為準。抽查項：ui_v3 守衛禁止 import `ui_v2`、四項摘要硬編碼 Missing、FX 閘門關閉、NAV 10 日門檻位置、`pay_date` 現一律空、Preview 執行期守衛白名單，皆已對照程式確認。

| 元件 | 正式 service::function | 計算所在層 | ui_v3 現在能否合法取得 | 已有測試 | Missing 行為 | 草案敘述判定 |
|---|---|---|---|---|---|---|
| 頁首持倉健康／β | 原料：`services/v2_tables/alo_holdings.py::load_alo_tables_active`、`settings_store.py::load_user_settings`、`nav_dividend.py::build_nav_dividend_tables`；判定：`ui_v2/{hld,alo}/logic.py::_conclusion_light`、`ui_v2/asset/page_status.py::aggregate`、`ui_v2/status_class.py` | 判定在 `ui_v2`（L3） | 原料可由 adapter 取得；判定不能，需 PORT；β 排序純函式在 `shared/ui_semantics/rules.py::resolve_precedence`（viewmodels／pages 可讀；BL-0411 閘門見 Q12） | `tests/ui_v2/test_p3_page_status_logic.py`、`tests/ui_v3/test_ui_v3_semantics_rules.py` | 缺分類鍵直接 raise；取數失敗＞無持倉＞注意＞缺值＞未設定＞部分＞正常 | 部分正確 |
| 摘要四項 | 無（`ui_v2/asset/overview.py::summary_strip()` 硬編碼 Missing） | 無算法 | 無可取得項 | `tests/ui_v2/test_ast_overview_logic.py` | 四格一律 ◇ 資料未備 | 「缺值顯示 ◇ 資料未備」正確；「欄位級 mapping 待複驗」已複驗＝四項皆無算法 |
| 配置實際 vs 目標 | 原子：`services/v2_domain/holdings.py`（同鍵加總、最近淨值、匯率對齊、類別歸屬、`exceeds`、`target_sum`）；組合：`ui_v2/alo/logic.py::_build_alo2` | 原子在 L2；組合在 `ui_v2` | 原子可；組合不能，需 PORT（G-1） | `tests/test_v2_domain_port.py`、`tests/ui_v2/test_alo_logic.py` | 缺基準值的類別排除於分母；缺 USD 匯率時債券顯示 100%，須附「合計未涵蓋」 | 部分正確（設定鍵與來源有誤、漏列 `alo_bucket_names`） |
| 偏離摘要／明細 | `services/v2_domain/deviation.py`（比較方向、差額、失敗優先）；HLD-1 逐檔：`ui_v2/hld/logic.py::deviation_rows` | 逐檔走訪在 `ui_v2` | 比較原子可；逐檔不能，需 PORT | `tests/ui_v2/test_hld_logic.py` | 門檻未設顯示 ⬜ 未設定，不當 0；門檻為使用者設定，非 SSOT 常數 | 部分正確 |
| 配息／近期事件 | `services/v2_tables/nav_dividend.py::build_nav_dividend_tables`；推估：`services/dividend_calendar.py` | 資料表在 L2；HLD-3 期間合計在 `ui_v2/hld/logic.py` | 資料表可（受 Preview 執行期守衛限制，G-2）；推估引擎不在允許前綴（G-3） | `tests/test_v2_tables_nav_dividend.py`、`tests/test_v2_tables_dividend_chain.py`、`tests/test_dividend_calendar.py` | 空清單且無證據＝無法判定，不當成「無配息」 | 「正式日期優先」錯誤（程式沒有）；其餘部分正確 |
| 持倉明細／單檔展開 | `alo_holdings.py::build_alo_tables`；`v2_domain/holdings.py::merge_same_key_holdings`、`aggregate_holding_rows`；逐檔組列：`ui_v2/hld/logic.py::_build_hld5`、`_build_hld6`、`ui_v2/alo/logic.py::_build_alo6` | 表在 L2；組列在 `ui_v2` | 表與合併原子可；組列不能，需 PORT | `tests/test_v2_tables_alo_holdings.py`；ui_v3 側尚無 💼 測試 | 單位數空白或為 0 不寫列、進略過紀錄；略過原因為中文字串，非 reason code | 部分正確（無級別欄；同鍵多列兩頁各自合併） |
| 資料健康／異常 | `alo_holdings.py::load_alo_tables_active`（`ActiveSourceError`）；`settings_store.py` | 判定 `is_no_active` 在 `ui_v2/active_gate.py` | 例外型別可；判定與狀態詞不能；ui_v3 狀態詞無 `not_configured`／`unread`／`skipped`／`unknown currency`（G-5） | `tests/ui_v2/test_active_gate.py` | 未設定與讀取失敗可區分、無 fallback | 部分正確 |
| ViewModel／Digest 分流 | 無（Digest 層零實作） | — | — | `tests/ui_v3/test_ui_v3_viewmodel_contract.py`（🌍） | — | 與 💼 現況不符（見第 3 節更正） |

**重點事實（稽核據程式；凡抽查不到者標 UNVERIFIED）**

- 逐檔原料：成本只有 `cost_twd`（int，TWD）；`return_pct` 是 NAV 價格報酬（百分點，期間為使用者設定 `hld_window_*`，不含配息與匯率）；配息為每單位原幣金額，`pay_date` 一律空、只有 `ex_date`。
- 門檻都是使用者設定，不是 SSOT 常數，唯一寫死的是淨值過期 10 天（`ui_v2/thresholds.py`）；設定 JSON 的形狀由 `ui_v2` live 層自訂，不在 L2。
- ui_v2 配息表欄名「入帳日」與 `79 §17.3` 衝突，New UI2 不得沿用。
- Preview 執行期守衛（`tests/ui_v3/test_ui_v3_preview_not_formal_guard.py`）規定 import 全部 ui_v3 後不得載入 `services.v2_tables`；模組層 import `alo_holdings`／`nav_dividend` 的 adapter 會令它轉紅，而目前沒有載入端 composition root（G-2）。
- ui_v3 第一階段唯讀（`KNOWN_WRITE_FUNCTIONS` 含 `save_setting_for_page`）；💼 沒有合法寫入面設定目標、容許帶、基準。
- `rules.resolve_precedence` 的 docstring 明文 BL-0411 修好前不得接進頁級燈；`shared/ui_semantics/rules.py` 目前無 `no_holding`／`partial`／`normal` 的核准字樣。
- UNVERIFIED：兩頁同鍵合併規則在同鍵不同幣別以外的實務差異（稽核只用合成資料驗過 ccy 情境）；`skipped_holdings` 中文原因與 `80 §3.1` 的 reason_code 鍵落差由誰補；ui_v3 側完整欄位契約（需核准後的實作批驗證）。
