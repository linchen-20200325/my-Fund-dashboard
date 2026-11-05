# 基金 New UI2／OneBrain｜ChatGPT 對話接手快照（2026-11-06）

> **用途**：把長對話的使用者需求、最新產品方向、衝突與待確認事項保存為可查證交接**證據**。不是第五套 SSOT、不是取代 `docs/HANDOFF.md`、不是修改正式金融規則或啟動施工的裁示；**不可拿本檔代替 GitHub Verification Gate**。
>
> **記錄來源**：2026-11-06 本次基金專案對話的使用者訊息，由 ChatGPT 進行**要點轉述**，不是逐字錄音或正式 DEC；使用者個別同意的產品方向與助理的尚待核准建議分欄記錄，防止推論被誤寫成裁示。
>
> **GitHub 取證基準**：main `861628cc377352c4f651ddc1172e13ab07e4d90d`，最近 main CI = success（查詢當時）；開啟 PR #1150（帳號入口草案）、#1151（五頁藍圖草案）、#1152～#1154（清理 Work）、#1157（4D／5D 稽核 Draft）。所有 PR、CI、SHA 都**會漂移，接手必須重查**。
>
> **GitHub 正式權威／優先序**：`CLAUDE.md`、`PROJECT_RULES.md`、`docs/v2/CONSTITUTION.md` + `docs/v2/57`、凍結 `docs/v2/44`、`docs/DECISIONS.md`、`docs/BACKLOG.md`、`docs/HANDOFF.md`，New UI2 `docs/v2/79`／`80`／`81`／`82`、OneBrain `docs/v2/67`／`75`；本檔只存**待正式比對的對話脈絡**。
>
> **工作分界**：本文件只屬 `linchen-20200325/my-Fund-dashboard`。不得把台股／mynews 的資料、公式、Risk Cap、UI 或 PR 帶進基金；使用者提供台股 OneBrain 圖像僅作**分段分析與資料隔離的架構參考**。

## 一、最新使用者產品方向（同意方向 ≠ 全部金融公式已核准）

| 主題 | 使用者在本對話明確提出／同意的方向 | 現況及權威 |
|---|---|---|
| 五頁 IA | 固定五頁：🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結／⚙️ 設定，UI 簡潔但不遺失詳細證據 | 現有 New UI2 `docs/v2/80`，🤖 Phase 7 前不可進／不可註冊頁面 |
| 手機導覽 | **2026-11-06 新要求**：底部導覽容易被訊息 App／嵌入 WebView 擋住；使用者同意改為手機**頁首橫向分頁**候選 | **與尚未合併的 #1150／#1151『固定底部』及既有 shell 相衝突**。需正式 UI/DEC／布局 Gate；切勿直接視為已施工 |
| 桌機／登入 | 簡潔可見的 Google 帳號入口、Active Sheet 與資料健康分離，桌機／手機需響應式 | #1150 設計草案；桌機左側欄仍屬現有設計，若另有新裁示須再確認 |
| 💼 持有基金總表 | **同一基金去重但保留全部保單／部位、數量、成本、幣別、來源**；顯示哪些標的表現惡化、配息有本金疑慮 | 尚屬新需求；身份不能只按相似名稱合併。只讀、Missing 不當 0 |
| 單檔 NAV 圖 | 在同頁選擇持有基金並直接跳到／更新該檔走勢；**同一張 NAV 圖疊顯買進／賣出 1σ、2σ、3σ 的價格／水平線，不拆兩頁** | `services/precision_service.py::calc_hwm_sigma_levels` 可作舊邏輯參考；新 UI 不能自算，算法／價格基準／單位需 Gate |
| 買賣點候選公式 | 使用者描述：買進＝近一年高點 − 1／2／3 標準差；賣出＝近一年低點 + 1／2／3 標準差 | **使用者想保留的第一版參考邏輯，不等於新正式 deterministic trade trigger／Risk Cap**；需確認 σ 的量綱、NAV 單位、期間及結算規則 |
| 健康評估 | 基金下跌可能只因市場不好；需**市場環境 vs 適當同類／基準相對品質 vs 絕對風險／配息**分軸，不因負報酬或 σ 低位階直接判壞 | 是使用者明確同意的設計方向；benchmark、公式與「惡化」threshold 尚待核准 |
| 配息來源 | 官方披露的「配息含本金」與模型的「含息報酬未覆蓋配息率」**分開證據、分開顯示** | 第一版 `services/health/dividend.py` 是數學 proxy，不能冒充官方會計來源 |
| 配息台幣試算 | 每檔顯示「以 **USD 1,000,000** 投入」的配息換算台幣，包含基金幣別、NAV、配息率／實際配息序列、適用 FX 日期與來源；另能讀實際持倉配息 | 新要求；跨幣別 FX 觀測日／NAV 可比性仍受 G-3 Gate |
| A／B／C 三場景 | A 新投入（台幣買外幣基金、購入單位及配息）；B 投入再平衡（按目標權重／缺口分配新投入）；C 轉換再平衡（同保單 M→N／A→B、分配、配息差額、成本／資本利得、ghost 保留 A 對照） | 舊 `ui/tab3_t7_ledger.py`、`services/ledger_service.py` 為邏輯參考；新 UI 只核准**唯讀模擬**，不能連真實帳本寫入；「資本利得」與搬移成本不得混稱 |
| OneBrain | **UI 摘要精簡、Evidence 完整且詳細**；但避免一次大量丟入 OneBrain 造成遺漏／異常。採**一個 OneBrain，多個任務式分析視角＋全域反證整合** | 遵循 `docs/v2/67`、`75` 的 One AI Brain 既有正式架構；本次新增的是**分批／覆蓋率／防遺漏的設計方向**，不授權啟動 Phase 7 |
| 取數品質 | 使用者同意調查舊 4D／5D 哪些資料常缺或根本不受支援；不可靠指標**不納入正式評分**，但資料與 Evidence 保留 | #1157 唯讀靜態稽核 Draft 已建；尚無 Active Sheet 真實持倉成功率；不得憑 2 檔歷史樣本宣稱永久 0% |

## 二、資料與 AI 永久守衛（僅指向已存在正式條文，不另立規格）

```text
既有核准來源／Active Sheet → Validate → Normalize → Canonical Data
    → Deterministic Domain／正式金融公式 → Complete Evidence Registry
    ├─ UI ViewModel：手機精簡、完整明細可展開
    └─ Decision Digest：按主題抽取足夠證據、保留索引與覆蓋清單
         → OneBrain 任務分析／反證 → 全域整合 → UI 摘要
```

- **資料層獨占外部取得**：取得／清理／標準化／追溯與 snapshot provenance 皆不由 AI 自行重做。OneBrain 只讀經驗證的 Evidence／Digest，不自行搜尋、調 API、寫回客觀資料。
- **完整但不暴塞**：Registry 可保留所有明細；不同主題 Digest 僅帶**判斷所需足夠上下文＋Evidence ID／來源連結**。長歷史序列依合格切片／查核引用提供，切片時不靜默丟關鍵反證；不能因省 Token 宣稱全部已評。
- **覆蓋率／防遺漏**：每個分析單元記錄 eligible、evaluated、missing、not evaluated、skipped、failed、stale、conflicted、out-of-scope；同時保留 expected evidence manifest、received IDs、omitted/unread IDs 與 hash/version；全域整合需驗證重大風險與反證未丟失。這是**設計建議**，schema／門檻未定。
- **判斷正確性**：缺值不填 0、未知非安全、不評估非正常；市場因素不能視同基金品質；不得只用單一綜合分數冒充全貌；未有 deterministic trigger／Risk Cap 前，不產生已核准買賣行動。
- **費用／效率**：Python 先計算所有能確定性計算的結果，AI 專責理由與交叉證據；優先 Claude API 的方向見既有 `docs/v2/75` policy，不在本批連接憑證／SDK。

## 三、舊版值得沿用的能力（現況認證不等於准許搬 UI）

| 能力 | 主要舊路徑 | 原則 |
|---|---|---|
| 4D 名稱、實際 5 維健康評級及覆蓋證據 | `services/health/grade.py` | 只重用有證據的 domain 指標，**2/5 的 A 不等於 5/5 的 A**；市場調整另 Gate |
| 1Y 含息報酬 | `services/fund_total_return.py` | 按現行 350 天+配息歷史 SSOT，不用舊混合 fallback |
| 官方與代理「吃本金」 | `services/health/dividend.py` | 公式與官方本金配息揭露要分開 |
| 大盤與基金比較 | `services/benchmark_compare.py` | 舊台幣對 TWII、其他對 SPX 的基準簡化，不適合所有基金；需同類／資產分類 Gate |
| HWM σ／走勢 | `services/precision_service.py` | 價格參考，不直接當正式行動／基金管理品質 |
| 4D／6F 額外因子 | `services/portfolio_service.py`、`services/health/report.py` | Sortino、Calmar、Alpha 與重疊度提供進階證據；不能把 deprecated 6F Grade 當正式健康分 |
| A／B／C、成本／XIRR／Ghost | `ui/tab3_t7_ledger.py`、`services/ledger_service.py` | 不搬舊 Streamlit／寫入，需測試帳務及匯率同口徑 |
| 來源對帳 | `services/reconcile.py` | 衝突＝衝突；不得自行取方便的一個數值 |
| 舊品質稽核 | `scripts/audit_6d_coverage.py`、`tests/test_grade_4d_guard.py` | 先核對探針 scope／樣本分母，再做真實現行持倉覆蓋測試 |

## 四、近期重要落差：必須以 GitHub 現行 SSOT 與較新的使用者對話核對

1. **手機導覽互相矛盾**：#1150 `docs/design/new_ui2_responsive_login_2026_11_05.md` 及 #1151 `docs/design/new_ui2_full_implementation_blueprint_2026_11_05.md` 皆寫「固定底部」；使用者後續因訊息 App 遮擋希望改頁首橫向導覽。**不得在既有草案中悄悄單方改為已核准正式規格**；需針對實際 WebView／390px 測試決定安全可達性及正式 supersede。
2. **#1151 不是最新 main 的事實快照**：其文件仍述 G-2 #1149 在施工；目前 #1149 已合併，#1155 稽核完成、main `861628cc377352c4f651ddc1172e13ab07e4d90d` 已有 NAV 輸入狀態 evidence。不得引用草案舊 SHA 作 GitHub 現況。
3. **持有基金品質總表與 A/B/C／配息／圖表**在本對話已提出並同意產品方向，但**沒有完整 New UI2 正式金融演算決策或全頁 wireframe gate**。本檔不得創造新的 APPROVED_WORDING、變更凍結 44、宣稱五頁 renderer 已完成或 OneBrain runtime 已啟動。
4. **4D／5D 實際覆蓋已知**：`services/fx_regime_service.py::SUPPORTED_FX=("USD",)`；`services/health/report.py` 傳 `ma_dir=None`；舊 `audit_6d_coverage.py` 檢查現價 FX，不代表歷史 FX 波動；歷史 TER 0/2 及規模解析問題不構成「永遠抓不到」。詳見 [#1157](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1157)。
5. **部分舊 ChatGPT 記憶已過期**：例如「B 版五頁」的 `hld/alo` 不是現行 New UI2 五頁；「#1049 為 main」「Open PR 0」「手機底部導覽已最終核准」「B4／舊 UI 所有功能直接搬入」等均不可用於現況判斷；新對話先查 main/PR/CI，再依現行上位治理和新裁示處理。**不刪除歷史 Git 記錄**。

## 五、任務角色與安全範圍

- **ChatGPT**：需求收斂、三路方案比較、基金金融語意與資料契約審查、五頁 HTML／390px 視覺藍圖候選、獨立 GitHub Gate／驗收與交接。
- **Claude Code 專案 AI**：已授權的正式程式實作、測試、PR／CI／獨立 QA；其正在施工的分支優先。ChatGPT 不和清理 Work 的 #1152～#1154 撞檔。
- **治理與移交**：每次動作先查 main SHA／Open+Draft PR／diff／CI、必要時 branch；已核准安全工作每批≤3、靜默處理。只用獨立 PR，不直接修改 main；HANDOFF 只是索引，不能取代 GitHub 事實。
- **Model／Effort**：涉及公式／FX 觀測日／Risk Cap／資料有效性／跨模組語意＝High；純文件／UI 呈現與 metadata＝Medium（可更低時 Low）；必要 Change Gate 依 `PROJECT_RULES.md`。不可把模型建議當作已完成手動切換。

## 六、交接與下一步（按證據排序，非逕行動工授權）

1. **先處理規格衝突**：手機底部五頁 vs 頁首橫向頁籤；從本快照對照 #1150／#1151、現行 `ui_v3/shell/` 與正式 DEC；出新版候選，經使用者／QA 與裝置實測 Gate。
2. **完成五頁交互藍圖的正式差異清單**：💼 淨值＋σ 同圖、去重保留部位健康總表、配息換算、A／B／C 新投入／再平衡／換檔，OneBrain 精簡摘要。若有本地 HTML prototype，**須實際驗證和提交**，不得以聊天中的 sandbox path 或 ChatGPT 宣稱當作 GitHub 已存檔。
3. **#1157 獨立核對與未來持倉實測**：先審查程式靜態事實與文件，然後在合格授權／Active Sheet 下取得真實分母與覆蓋；**不改公式、不刪指標**，待客戶裁示後才考慮正式準入。
4. **OneBrain 防遺漏設計**：利用 `docs/v2/67`／`75` 既有正式 Digest 架構，設計最小 manifest/coverage schema 與任務切片、反證／失敗標記，**不啟動 Phase 7 runtime**。
5. **最終收斂**：正式裁示、BL、短 HANDOFF 更新**須由既有治理寫入流程**完成；#1153 正在改 `docs/BACKLOG.md`／`docs/HANDOFF.md`，本 PR 刻意不碰這兩檔，避免工作互相覆寫。待 #1153 實況明確後再將本證據索引整合到既有 HANDOFF；不建立另一套 current-state 系統。

## 七、無法由本次快照確認

- 當前使用者 Active Sheet 的現行基金清單與真實指標命中率（未讀取私人帳戶）。
- 任何正式實作後的 390px 實機截圖、Streamlit Cloud/OAuth 配置與實際行動語意。
- 對話中所有協助者的推論是否已在另一 PR 登錄為正式客戶裁示；提交前仍須依 GitHub main / PR 檢查衝突。
- 這份檔案只是 repo 中的一份可追溯**對話證據**，不會刪除或替換 ChatGPT 帳戶本身的 Memory 系統。
