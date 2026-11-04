# 82｜New UI2 💼 我的資產：UI × Data × Evidence 施工前設計草案（待客戶核准）

> **定位**：ChatGPT 產品／資料契約初稿，2026-11-04。**非已核准 wireframe、非公式或資料語意裁示、非程式實作授權**。此檔不取代 frozen `44`、`79`、`80`、`73`、`74`；同一事實以原正式契約為準。先驗既有 capability／欄位，再由客戶核准具體版面。不得因本草案把舊 UI 程式直接搬入 `ui_v3`。
>
> **讀碼範圍**：`services/v2_tables/alo_holdings.py`、`services/v2_domain/{holdings,deviation}.py`、`services/v2_tables/nav_dividend.py`、`ui_v2/{hld,alo}/{source,logic}.py`；對照 `docs/v2/{73,74,79,80}_*.md`。此為 ChatGPT 單組盤點，**尚未由獨立組逐欄複驗**。以下「候選接線」不保證已存在 New UI2 可直接調用的 facade；實作組必須在核准後驗證精確 schema。

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

## 2. 逐區塊資料串接矩陣（施工前須複驗）

| 區塊／元件 | 候選正式資料／欄位 | 已有位置／能力 | 確定性與 Gate | 不可做的事 |
|---|---|---|---|---|
| 頁首持倉健康／β 結論 | holding、policy、nav、dividend、setting、market_indicator 的正式載入與狀態 | `alo_holdings.load_alo_tables_active`、`ui_v2/hld/logic.py`、`ui_v2/alo/logic.py`；D-3 P3／β 見 `74` | **重用既有結論語意**，核對 skipped_tabs／skipped_holdings 對結論的影響；New UI2 adapter／viewmodel 路徑待定 | 不以部分讀取當成「無持倉／正常」，不在 UI 自建狀態 precedence |
| 四項摘要 | holding／policy／nav／dividend 與相關 user_setting、FX | `alo_holdings`、`nav_dividend`、`v2_domain/holdings`、既有 HLD／ALO domain outputs | **欄位級 mapping 待複驗**：總資產、損益、報酬、配息分別查明幣別、時點、區間、投資本金與成本口徑；無已核准跨幣別匯總公式不得顯示假總值 | 不新增匯總公式；缺值不填 0；不混淆報酬率和損益 |
| 配置主圖：實際／目標 | holding.bucket、holding.cost_twd 或 holdings×latest NAV×FX；user_setting 的 `alo_target_weights`、`alo_basis`、`alo_tolerance_pp` | `ui_v2/alo/logic.py` ALO-2／ALO-4；`v2_domain/holdings.py`；`v2_domain/deviation.py` | 正式選定**成本／市值基準**才呈現；僅用已驗證 mapping；百分點差額與容許帶必須附設定來源；缺 FX 不轉用成本 | 不 UI 重算、不能自訂容許帶或默認 0、不能將未分類靜默分配 |
| 偏離摘要／明細 CTA | ALO-2 類別差距、HLD-1 正式逐檔偏離與門檻、未評估件數 | `ui_v2/{alo,hld}/logic.py` 既有 domain / P3 β；`73` | 顯示為「規則比較的事實」；點擊只展開既有明細；不能當投資再平衡指令 | 不提供一鍵再平衡、不造 action state |
| 近期配息／配息日曆 | dividend rows、已核准 date semantics、status；holdings 與 NAV 供必要確認 | `services/v2_tables/nav_dividend.py`、`79 §17.12`、`80 §7.2`、`73 HLD-3/HLD-6` | **日期契約 Gate**：正式日期優先、deterministic estimate 只作 fallback；`pay_date` 未完成 amendment 前不得說「實際入帳日」；資料來源日期類型逐欄標 | 不把除息日當入帳日、不用缺日期預估正式付款、不把推估混成已確認 |
| 持倉明細（全列）／單檔展開 | holding_id、fund_code、政策／級別、單位數、幣別、NAV 日期／點、配息序列；必要 skipped reasons | `alo_holdings.build_alo_tables`、`v2_domain/holdings.py`、`nav_dividend`、`73 HLD-5/HLD-6/ALO-6` | 全列保留，單檔展開只影響畫面；原始 identity、同鍵衝突與 FX gate 不變 | 不用 Top N 切掉持倉；不同基金不能因同名合併 |
| 異常／資料健康摘要 | Active Sheet 狀態、settings、NAV、FX、配息與 skipped/unread/failed | `alo_holdings.load_alo_tables_active`、`ui_v2/{hld,alo}/source.py`、`services/v2_tables/settings_store.py` | 首屏顯示與判讀相關的 Missing／失敗；完整來源健康明細由 ⚙️ 承接（涉及 `BL-0540` 先守現行 44） | 不暴露 secret、內部 reason code、traceback；unavailable ≠ neutral |

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

## 4. Implementation options：先選路徑，再施工

| 路徑 | 正確性與風險 | 工時／Token | 取捨 |
|---|---|---|---|
| A. `ui_v3` 直接 import `ui_v2` page／logic／CSS | 高耦合，可能違反 New UI2 migration boundary | 初期看似快，後續回歸高 | **不採** |
| **B. 以合法 L2／shared domain／adapter 建 `ui_v3` ViewModel** | **最佳**：domain 單一計算、UI 測試可獨立 | 初期需 contract mapping，後續重用率高 | **推薦；符合 `80 §2/3/8`** |
| C. 複製舊 HLD／ALO 計算到 `ui_v3` | 兩份公式失同步、來源／幣別語意漂移 | 眼前省時，總成本高 | **禁止** |

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

## 7. 本次 PR 的 Definition of Done

此 PR **只完成施工前產品草案與資料 mapping 候選**。Merge 不等於客戶已核准設計、不等於 UI 已完成、不等於可開始 💼 程式。下一步為專案 AI 的獨立欄位契約驗證（唯讀報告）＋客戶 wireframe 核准，再另批實作。仍維持 Silent Autonomous Cruise。
