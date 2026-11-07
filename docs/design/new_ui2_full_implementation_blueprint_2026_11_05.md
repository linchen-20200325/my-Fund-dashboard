# New UI2｜全站施工藍圖與四頁逐卡線框候選（2026-11-05）

> **狀態：設計整合草案，供客戶逐頁核准；不是新授權或現行正式 SSOT。** 本文件將現有已核准設計、可實作候選與待決 Gate 分開列示，避免 Claude Code 為每頁重做產品設計，也避免將草案直接變成正式金融／資料語意。**目前 🌍 已有正式核准的頁線框與 Preview 實作，不重畫。**
>
> **優先權**：`CLAUDE.md`／子法 1＋57／frozen 44、`PROJECT_RULES.md`、既有 DEC 與 `docs/v2/79`／`80`、`81`（🌍 已核准）、`82`（💼 僅 U1～U5 UI 部分核准）、`docs/design/new_ui2_responsive_login_2026_11_05.md`（PR #1150 尚未合併）、此文件。衝突以較高效力和較新正式裁示為準；本草案不得覆寫它們。
>
> **基準**：GitHub main `81827057b6116096ad16cd304540af55a3e1f1af`；此刻 G-2 正於 PR #1149 施工，登入文件於 PR #1150 進行中，**不得藉本文件合併或擴張兩批**。未讀到的 live schema 與尚未裁示口徑一律標待驗證。

> **2026-11-07 目前適用性更正（supersession；本段不是新裁示）**：本檔是 2026-11-05 歷史施工候選，當時的 `main 81827057`、#1149 施工中、#1150 未合併、**手機固定底部導覽**等敘述僅保留為歷史基準，**不得作為當前施工依據**。現行 main 已合併 #1149（G-2）、#1161（登入設計）、#1162（`DEC-2026-11-06-01` 頁首橫向五頁籤 B、`-02` 健康覆蓋）；#1150 是未合併的舊 Draft。手機導覽目標改為**上方橫向五頁籤**，但 #1163 的 BL-0544 frozen 44／57／CONSTITUTION 適用性、精確線框及字樣 Gate 尚未完成，**不得直接改 `ui_v3` 或宣稱已核准實作**。桌機左側欄、五頁 IA、登入共用 OAuth/session、🤖 Phase 7 禁入仍不變。本檔未核准的其他四頁線框／金融演算仍只算候選。
>
## 0. 全站單一設計系統

**固定五頁與順序**：🌍 市場與趨勢（`mkt`）→ 💼 我的資產（`ast`）→ 🔍 找基金（`exp`）→ 🤖 AI 投資總結（`ai`）→ ⚙️ 設定（`set`），`ui_v3/shell/registry.py` 是頁名與掛載狀態來源。Phase 7 前 🤖 **可見、不可進、不註冊頁面、不建空殼**；其餘頁面只有在「已核准整頁線框且已實作」後才能 `registered=True`。

| 設計維度 | 桌機／平板（>768px） | 手機（≤768px） | 不變條件 |
|---|---|---|---|
| 主導航 | 固定左側欄，五頁 IA | ~~固定底部五頁導覽~~ → **頁首橫向五頁籤 B**（新方向；合法及精確線框 Gate 待驗）、安全區留白 | 不新增第六頁、不改五頁順序 |
| 帳號入口 | 左側欄最上方「Google 帳號」精簡區 | 頂部右側精簡入口，按需開啟抽屜／浮層 | 同一 L2 登入狀態；獨立於頁首五頁籤；正式設計已由 #1161 合併 |
| 頂端狀態 | PREVIEW、取得狀態、資料時點等已核准 shell 字樣 | 精簡一列，不複製資料健康大卡 | 無已知時間不猜；資料全齊不額外標「正常」 |
| 頁面第一屏 | 頁面狀態 → 主視覺 → 必要摘要 | 同邏輯，但窄版優先一欄；主 CTA 不藏在長明細下方 | 既有凍結 44 首屏 chip／核心數字 ≤5，Missing 佔位亦需點數 |
| 詳細資訊 | 可視需要右欄／收合 | 圖下方分層展開 | 「Presentation Compression ≠ Evidence Loss」，無 Top-N 截去 evidence |
| 色彩／字樣 | 現行 `shared/ui_semantics/rules.py` | 同一份 | 顏色不能是唯一狀態資訊；不得自造正式新詞 |

**共用元件候選（不代表現有程式 API）**：`PageHeading`（頁名、資料時點）、`PageStatus`（合法狀態）、`PrimaryChart/StatusFallback`、`SummaryMetric`（固定位置、顯示缺值）、`SpecLine`（口徑／幣別／資料範圍）、`Disclosure`（全列與理由）、`AccountEntry`（登入摘要與開啟入口）。只能由 view model／已核准字樣驅動，不得把資料計算寫在元件內。組件清單是施工設計，不能當新金融狀態字典。

## 1. 資料流／責任邊界（全頁共用）

```text
既有合法來源／personal session／Active Sheet
         ↓（L1/L2，取得、驗證、mask、provenance）
Canonical Data／完整來源品質證據
         ↓（services/v2_domain：正式 deterministic 規則，缺值不補）
Complete Evidence（含 skipped／failed／未評估／日期／FX 證據）
         ├──→ UI ViewModel（手機精簡顯示、可展開完整 detail）
         └──→ 未來 Decision Digest → OneBrain（Phase 7 Gate，現在不實作）
```

- **Data ≠ AI**；AI 不取得新資料、不產生未授權金融公式、不更改 canonical data。
- 缺值不可轉 `0`、`False`、中性或 HOLD；來源失敗和沒有資料不同；FX 未驗證時禁止把 covered denominator 畫成全資產 100%。
- 同一基金、同一指標、同一觀測日／幣別／級別，跨頁結果須一致；不得在不同 UI 分別算一份。
- 認證登入狀態／Active Sheet 選本狀態／資料完整性屬三個不同維度。
- G-2 #1149 已合併；`ui_v3/adapters/assets_source.py` 的目前真實 schema 與可接線性仍須以最新 main 實碼獨立核驗，**不得把本歷史候選當成 renderer 已獲授權**。
- Preview 不含 fake production data；fixtures 僅供測試；不得搬 `ui_v2` 舊 CSS、UI 模組或 Old UI presentation；正式 cutover 另 Gate。

## 2. 🌍 市場與趨勢：**已核准，KEEP**

**權威**：`docs/v2/81_new_ui2_wireframe_01_market.md`、`DEC-2026-11-03-01`；render 實況見 `ui_v3/pages/mkt.py` 及 `ui_v3/adapters/market_page.py`。不再對已通過的畫面另發明新線框。

| 區塊 | 設計契約 | 沒資料時 |
|---|---|---|
| 頁面狀態／需注意 | 僅正式規則能判定；絕不以單一指標推投資行動 | 無足夠證據則未判定，不自造「安全」 |
| Primary | TAIEX vs S&P 500，同一已核准共同基準日、100 歸一化與視窗規則 | 不畫假雙線／空座標 |
| Secondary／依據 | 依 `81` 已核准區塊、排序、數據與 detail | 顯示來源／日期／Missing／取數失敗 |
| 操作 | 只提供已核准的期間／視角切換 | 不啟用未核准 threshold 或 refresh |

**禁止：** 重做 market widget、導入額外指數／EPS 算式、把 `81` 歷史刪除句當最新規則。

## 3. 💼 我的資產：**已核准布局方向＋逐卡候選，待正式全頁線框 Gate**

**已核准**：`DEC-2026-11-04-01` 主圖在前、四項摘要在後、缺資料明示；`DEC-2026-11-04-02` U1～U5、缺 FX Option A。**未核准**：尚未裁示的財務算法、β 接入、各類別可比性、配息推估與新狀態詞（`82` §6.1、BL-0542）。**未核准頁面整體 wireframe 不可直接開始 💼 renderer。**

### 3.1 手機 390px（以下是 UI 候選，非真機測量）

```text
[固定 Shell：頂部／右上帳號入口]     ← 登入設計已由 #1161 合併；UI 實作狀態另以程式查證
[💼 我的資產] [日期／持倉來源摘要]
[頁級 β／是否需注意：只有已核准且可證才顯示]
┌────────────────────────────────┐
│ 配置主圖：各類別 實際 vs 目標   │  ← U2：平行水平條圖；需合法同口徑
│ 或「資料未備／無法比較」狀態卡 │
└────────────────────────────────┘
[SPEC：計算基準｜幣別｜涵蓋範圍｜資料日]
[總資產] [損益]                     ← 四格固定占位：未有合法數值就 Missing
[報酬]   [期間配息]
[配置差異摘要＋查看偏離明細 CTA]    ← 只能是事實揭露，不是交易動作
[近期事件／可證實的除息與配息資訊]
[▸ 全部持倉（全列，逐檔 NAV／配息可展開）]
[▸ 各類別設定／來源證據／未計算及錯誤原因]
[頁首橫向五頁籤 B（待合法 Gate／線框核准）]
```

### 3.2 桌機 1280px（UI 候選）

```text
[左欄：Google 帳號 → 五頁導覽] | [主頁頁級狀態／資料時點]
                                  | [配置 實際 vs 目標主圖][近期事件／配息]
                                  | [SPEC／涵蓋範圍／缺值摘要]
                                  | [四項摘要：總資產｜損益｜報酬｜配息]
                                  | [差異事實＋展開 CTA]
                                  | [全部持倉／每檔 NAV／配息、來源與未評估]
```

### 3.3 每卡資料契約與降級

| 卡／操作 | 唯一可用的證據類型 | 正式可用前提 | 不完整時必須做 |
|---|---|---|---|
| 頁級狀態 | 正式 β／H6 定義之 Domain Evidence | β 移植與語意 Gate 完成 | 不顯示捏造的「正常／安全」，顯示規則對應不可判定 |
| 實際 vs 目標 | `v2_domain` 確認的合法 bucket／basis／target／denominator | 同口徑、幣別、FX 日期與類別分母皆合法 | 替換成缺值狀態卡；揭露 covered／uncovered，不把 covered 畫滿 100% |
| SPEC | basis、currency、coverage、source obs date、validity | 資料 producer 可證且有正式用字 | 缺哪項就標哪項；不推測 |
| 四格 summary | 個別正式計算結果與個別來源日期 | 四個指標各自有合法既有算法 | 四格**保留且顯示 Missing**，不暗填假值 |
| 差異／查看偏離 | 正式已判可比的類別差距 Evidence | 目標權重、容許帶與分母合法 | 只列已評估數量與未評估原因；CTA 展開詳情，非再平衡 |
| 事件／配息 | 正式 dividend row、date type、provenance | 除息／支付／預估日期各自契約已核准 | 不能把 pay_date 叫實際入帳日；不能將推估冒充已確定 |
| 全持倉 detail | holding identity、原始 rows、skipped、missing NAV／FX | Canonical identity 守衛、現有讀取契約 | 顯示**全部列**及 skipped／failed 原因，不裁掉不利資料 |

**視覺驗收前置**：390×844 與 1280×800 的**實際**截圖、狀態 chip＋核心數字逐元素點數、文字過長／橫向捲動／safe-area／可展開完整 evidence；需要客戶再核准完整頁面線框才可實作。

## 4. 🔍 找基金：**入口語意已核准；New UI2 全頁視覺候選待核准**

**已核准語意**：`docs/v2/78`＋`DEC-2026-11-01-01`／`-02`，`docs/v2/80` §7.3、`DEC-2026-11-02-07`。主查 MoneyDJ 基金代碼；ISIN alternate 僅在有**可靠對照來源**時才 resolution；無來源則標尚未啟用而非猜身份。取消名稱／模糊搜尋及 AI ranking；兩區獨立：單檔查詢與既有篩選。

### 4.1 手機 390px 候選

```text
[固定 Shell]
[🔍 找基金] [資料日／來源]
[第一區｜查一檔基金]
[單一輸入框：依正式格式分流 MoneyDJ／ISIN]
[查詢 CTA]
[基金身份核對／基金代碼／正式查得基本資料]
[歸一化 NAV（合法有值才畫）]
[▸ NAV／配息／身分證據／查無或讀取失敗原因]
────────────────────────────────
[第二區｜依條件篩選]
[合法母體與條件選取；已核准三態條件]
[符合筆數、全部符合清單／可展開詳情]
[比較區：最多 3 檔；與第一區其他比較元件互不混用]
[頁首橫向五頁籤 B（待合法 Gate／線框核准）]
```

### 4.2 桌機 1280px 候選

- 頁首直接顯示第一區「查一檔基金」，輸入框與查詢 CTA 同列；合法 NAV 圖表為主視覺，查得欄位與證據在右側或圖下。
- 第二區「依條件篩選」獨立在下一段，不把篩選器折成同一個搜尋框；條件與結果可左右排，但完整符合清單不得 Top-N 截斷。
- 真正的比較圖只由既有核准 normalization、identity 和期間規則產生；無有效點不畫假圖。

| 區塊 | 資料來源與門檻 | 異常呈現 |
|---|---|---|
| 單檔入口 | 已核准 MoneyDJ 代碼 identity；ISIN 無合法 resolver 時不啟用 | 無法對應／查無／讀取失敗不得混在一起 |
| 單檔事實卡 | 既有合法 fund profile、NAV、dividend、source 日期 | 欄位缺失逐欄顯示 Missing |
| 對照 | 既有審核 100 歸一化、至多 3 檔、與篩選比較狀態獨立 | 不補非交易日或不存在的值 |
| 篩選 | 正式 `EXP` 三態條件與來源池 | 缺來源不能假報 0 符合；不製造排名 |
| 觀察／寫入 | 未經 writer Gate 不呈現可用寫入 | 不做假「加入清單」成功 |

**UI Gate**：正式欄位組合、按鈕排序、結果卡優先序、長清單手機可用性尚需客戶核准 New UI2 全頁線框；不得以 `78` 的 Legacy UI 區塊位置直接當新線框已通過。

## 5. ⚙️ 設定：**頁面擁有的功能已核准；New UI2 全頁視覺候選待核准**

**現行 ownership**：`docs/v2/80` §7.5、`DEC-2026-11-02-07`；帳號／Active Sheet、資料可信度與來源健康、通知偏好／送達健康／稽核、唯讀規則登錄；Digest viewer 必須等 Digest production。此頁不是投資 Risk Cap／threshold rule editor；不得顯示 secrets。

### 5.1 手機 390px 候選

```text
[固定 Shell]
[⚙️ 設定]
[帳號／登入／切換／登出（同頂部登入入口狀態）]
[Active Sheet：選本／Pending 確認／已選來源摘要]
[來源健康摘要：取得、未備、失敗、時點]
[▸ 逐來源取得結果／日期／缺值與失敗理由（安全遮蔽）]
[▸ 通知偏好／送達健康／稽核（僅合法已接線）]
[▸ 正式規則登錄（唯讀）]
[▸ Digest viewer：未有 production 時不啟用]
[頁首橫向五頁籤 B（待合法 Gate／線框核准）]
```

### 5.2 桌機 1280px 候選

- 左側登入和 Active Sheet 功能清晰呈現；右側來源健康總覽，進階資料狀態和通知偏好折疊在下方。
- 已登入無 Active、Pending 未確認、登入過期、來源失敗，各自獨立顯示，不可將任何一項翻成「帳號沒問題、資料正常」。
- 用 `services/v2_tables/personal_session.status()` 與合法 existing OAuth／Picker；嚴守 `pending_login` 明確確認與帳號切換清理原則。

| 卡／操作 | 合法前提 | 不得做 |
|---|---|---|
| Google 帳號與來源 | session L2 成功、部署 OAuth 已設定 | 前端自管 token、直接顯示驗證錯誤原文 |
| Active Sheet | Pending／Active state machine 與已驗證 picker 白名單 | 自動選本、接受未驗證任意 ID |
| 資料來源健康 | 現行 fetch health／provenance／錯誤遮蔽 | 以 Missing 當成 ok、暴露 exception trace |
| 通知與稽核 | 既有核准 preference 與 delivery metadata | 把 notification preference 寫成 investment rule |
| 規則登錄 | 已落地正式規則資料 | 提供修改門檻、Risk Cap 或 action rule 的 editor |
| Digest | 真正啟用前只保留未來設計登記 | 製造假 OneBrain 結論或假啟用按鈕 |

**UI Gate**：帳號卡展開位置、資料健康度與 frozen 44 的界線、通知區資訊密度／動作權限需要在 ⚙️ 專屬 New UI2 線框核准；涉及 frozen 文件的規格調整仍須合法 amendment。

## 6. 🤖 AI 投資總結：**Phase 7 以前不實作頁面**

- 現行只保留 Shell 的 **可見、不可進**導覽項；不註冊 renderer，不產生空殼或「模擬分析」。
- Phase 7 後的候選資訊順序（非授權）：系統狀態／能否判定 → 解讀與依據 → 最重要反證 → 展開完整 Evidence／Digest provenance；沒有正式 runtime 時只能顯示正式不可用語意。
- 核准 Digest、Risk Cap、狀態詞、可追溯性、校準等合約前，禁止 AI 機率／信心值／投資行動。**本文件完全不授權 Phase 7。**

## 7. 工程交付矩陣（不授權開工）

| 批次 | 由誰負責 | 前置 | 可交付的單位 | 驗收 |
|---|---|---|---|---|
| D0 設計 | ChatGPT | GitHub Gate | 本藍圖、登入 UI 契約、逐頁候選與未決項 | 同步客戶裁示／審查；**文件不等於核准線框** |
| G-2 Data | 既有 Claude Code #1149 | **已合併（歷史任務）** | `assets_source` 最小 adapter | 最新 schema／CI 仍應重查；不得跨入未授權 renderer |
| D1 💼 最終線框 | ChatGPT | G-2 真 schema＋82 U1～U5 | 390／1280 完整逐卡 wireframe、保留待決 Gate | 客戶核准頁線框後才能寫該頁 UI |
| D2 🔍 最終線框 | ChatGPT | 78／80 現行語意、identity 能力 Gate | 390／1280 New UI2 搜尋與篩選單頁 | 客戶核准再寫程式 |
| D3 ⚙️ 最終線框 | ChatGPT | Session／OAuth、健康度、通知 ownership | 390／1280 New UI2 設定單頁 | 客戶核准再寫程式 |
| C1/C2/C3 | Claude Code | 對應 D1/D2/D3 已核准，且 Model/Effort Gate | 依序 view model → adapters → page → AppTest/VF | 每批獨立稽核、完整真實證據 |
| Login UI | Claude Code | **#1161 設計已合併；實作仍須獨立 Gate**（#1150 為舊 Draft） | 桌機左欄＋手機頂部單一登入入口 | 登入、Pending、Active、安全／390px |
| AI／cutover | 暫不派工 | Phase 7 與 BL-0535 另 Gate | 無 | 不得提前 |

**最大化速度、最省 Token 的選型**：① 不重做已完成的 🌍；② 一份共用 Shell／狀態／缺值／證據規格，供各頁直接引用；③ 每頁只保留真正依資料能力與核准口徑才能決定的 Gate，將其餘 presentation 細節做成候選供客戶一次核准。禁止每一個控件各發一次裁示題。

## 8. 施工前統一驗收清單

1. 重新取 GitHub main／Open PR／diff／CI；不能憑當下本文件的基準 SHA 宣稱最新。
2. 對應頁面「完整 New UI2 線框」有客戶明確核准且裁示寫入 `docs/DECISIONS.md`；對應 `registry` 當前仍未掛載，沒有理由偷偷打開。
3. UI 的資料欄位有合法既有 producer、同口徑證據、來源日期與 Missing／skipped／failed 明確分類；沒有就顯示資料未備，不推算。
4. `APPROVED_WORDING` 未有的正式新詞不加；沒有 Risk Cap、公式或新來源 Gate 就不新增。
5. 390×844、768px、769px、1280×800 四個 layout／斷點情境；long names、no holdings、mixed currencies、FX unverified、failed source、logged_out／pending_login／no_active。
6. 無假資料輸入正式 Preview、無 Old UI／ui_v2 presentation import；readonly guard／Phase 7 guard／cutover guard 有效。
7. 每個 UI 實作批至少一組真正獨立稽核；Cloud production-like screenshot＋客戶目視驗收不能由 CI 成功取代。
8. 只在上述 Gate 成立後交給 Claude Code 實作；本藍圖是減少研究與返工，不是跳過專案憲法。

## 9. 交接與限制

**可當後續設計參考、但仍須核現行 Gate**：五頁 IA、現行 🌍 設計、全站 Shell／~~手機底部導覽~~ → 手機頁首五頁籤 B（待合法 Gate）、已核准帳號 UI 方向、資料與 Evidence 分離、不補 Missing、💼 主圖優先與 U1～U5 的 UI 方向、🔍 的正式搜尋身份語意、⚙️ 的 ownership、🤖 Phase 7 前禁入。

**不能直接開始寫 UI 的部分**：💼／🔍／⚙️ 尚未收到逐頁 **完整** New UI2 線框核准；💼 的未決金融口徑；🔍 身份與實際來源尚缺的能力；⚙️ frozen 44 與通知動作前置；🤖 所有 Phase 7 動作。不得用這份文件冒充已核准或已上線。

**本文件作者與驗證邊界**：ChatGPT 單組整合，未執行 Streamlit UI／AppTest／截圖或獨立 QA；已直接核對 `registry.py`、`nav.py`、`personal_session.py`、`docs/v2/78`／`80`／`81`／`82` 的相關部分；其餘逐欄返回值仍須施工前重新核實。無實證者明確標候選。
