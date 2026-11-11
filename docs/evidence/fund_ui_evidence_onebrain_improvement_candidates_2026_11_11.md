# 基金 New UI2／Decision Digest／OneBrain 改善候選矩陣（2026-11-11）

> **性質：基金專屬唯讀設計評估／後續研究提案；不是新的正式規則、DEC、Runtime 實作或施工授權。** 內容僅列基金應具備的能力與基金內部契約依賴；不要求專案 AI 查找其他 repository，亦不提供跨專案程式碼、路徑、資料、公式或投資規則。
>
> **GitHub 觀測快照**：基金 main `55e48d036e1e1f148acaa0364629a8a827dc0c14`（#1210 已合併）；Open PR #1211 為隔離雙模式 PoC Draft，與本文件不重疊。後續任何執行前須重做 GitHub Verification Gate。BL-0545 保持唯一全域 NEXT。
>
> **基金正式依據**：`PROJECT_RULES.md` 第 13 節；`docs/v2/44_fund_ui_ssot.md`（frozen）、`docs/v2/67_ai_action_vocabulary.md`（Digest／行動語意 SSOT）、`docs/v2/75_onebrain_ai_architecture.md`（方向與 Provider／Cache／Budget）、`docs/v2/79_final_ui_contract_freeze.md`、`docs/v2/80_new_ui2_architecture_proposal.md`、`docs/v2/81_new_ui2_wireframe_01_market.md`、`docs/v2/82_new_ui2_assets_ui_data_evidence_proposal.md`、BL-0527、BL-0545。若本文件與正式契約不符，以正式契約為準。

## 1. 先保留的架構（不是新發明）

- **唯一資料權威**：Raw Sources → Canonical Data → Deterministic Rules／Indicators／Risk Cap → Decision Digest → OneBrain → UI。取數／正規化／驗證在資料層；OneBrain 只讀既有證據，不回寫 canonical、不自行補 Missing、不引入新 source／API、不得覆寫公式或 Risk Cap。
- **呈現與決策分離**：UI ViewModel ≠ Decision Digest；UI 可以收合、縮減顯示資訊，不能據此刪除 canonical／完整 Decision Context。AI 也不得從 UI widget、顏色、Top-N 或 Session 文字反推完整資料。資料層與 AI 層的完整性需分開驗。
- **單一 OneBrain**：各頁在未來只呈現同一份正式 Digest／分析結果對應的 slice；不得由各頁各自產生矛盾的投資結論。不得因本研究提前啟用 Phase 7。
- **基金領域語意**：基金身分／ISIN／Share Class／MoneyDJ 原始分類、NAV 觀測日、FX 觀測日與方向、幣別、配置、Freshness／Availability、正式 Risk Cap 缺口、客戶「級別」設定與「系統推算類型」彼此區分；不新造交易觸發值、分數、信心或六行動詞。

## 2. 能力對照與最小改進候選

| 編號 | 基金目前已有的正式基礎（不是代表 Runtime 完成） | 建議補強／驗收方向 | 優先 | 施工資格 |
|---|---|---|---|---|
| F-01 呈現與完整證據分離 | `67 §5`、`79`、`80` 已要求 ViewModel 與 Digest 分離；`ui_v3` 市場頁只消費 view model | 增加「縮減 UI 顯示／切期間／切頁」不影響 headless canonical／Digest 必要證據的守衛；完整 evidence 有追溯入口但不強迫第一屏展開 | P0 | 先做唯讀契約對照；測試／Runtime 額外授權 |
| F-02 讀取完整性 | BL-0527 已承接 Digest 缺口，`67` 未要求一次建立龐大 schema | **先盤點**必要 Evidence ID／來源／as_of／有效性／缺失／讀取／省略／反證能否由現有型別證明；必要時提出 deterministic Coverage Manifest 最小加性設計 | P0 | 未核准 Schema；不得建立重複 Evidence Store |
| F-03 資料與能力狀態 | `shared/ui_semantics/rules.py`、`ui_v3/viewmodels` 和 `67`／`79` 已有既定狀態語意 | 分清 data missing／fetch_failed／stale、feature not wired、rule not evaluated、judgment undeterminable；狀態字樣、符號、顏色遵循基金 SSOT，不搬任何外部狀態 enum | P0 | 僅盤點／測試提案，正式語意另 Gate |
| F-04 基金身分與時間對齊 | 既有基金 Identity／NAV／FX／Coverage Gate 與 BL-0545 | 同基金同級別／同幣別／同觀測條件跨頁一致；NAV 與 FX 日期不得偷換，資料有值≠准入合格；缺 FX／類別未驗，不得當可信收益／配置數字 | P0 | 未過 FX Gate 只能無法判定 |
| F-05 OneBrain 範圍與反證 | `67 §5–8`、`75` 的單一 Brain、provenance、trace／budget 方向 | 未來僅按問題 scoped 分包讀取，保留必要支持／反證與 omitted IDs；完整性只能由確定性 validator 判定，AI 不能自行宣稱完整；總結從同一 Digest／compatible snapshot 取得 | P1 | Phase 7 前不得啟用 LLM runtime |
| F-06 AI 成本與快取 | `75` 已研究 provider、fingerprint、cache、trace、budget | 先做既有實作盤點；再比較只計算／模板、兼容 fingerprint cache、必要時有界增量分析；不因每頁入口而每次多一次 LLM 呼叫 | P1 | Provider／Cost Gate 另授權 |
| F-07 手機首屏與證據分層 | `44` 首屏預算；`ui_v3` 市場頁 G3 色票＋G6 卡片、三寬度量測 | 後續「💼 我的資產」優先資產／配置／資料狀態／需注意；詳細 NAV、FX、風險及來源下沉；不改 🌍 已核准主圖與五頁 IA，不複製其他 UI 版型 | P1 | 逐頁 wireframe／UI Gate |
| F-08 Preview、測試與正式入口隔離 | `ui_v3/app_preview.py` 非正式入口、既有防誤用守衛；#1211 獨立 PoC | 維持非 production fixture、Preview 僅核准頁面、正式資料不得用 fake 補值；必要時檢查 import/route 反向依賴 | P1 | #1211 範圍不能擴充，本文件不重派 |

以上「已有」僅指從正式規格與特定模組可辨識的基礎；實際 Runtime Coverage／Digest 讀取／OneBrain 功能是否已接線，須依後續 GitHub diff、tests、caller、CI 查證，不能由文件存在推定。

## 3. 三路徑評估（正確性／速度／Token）

| 方案 | 作法 | 正確性與風險 | 速度／Token | 建議 |
|---|---|---|---|---|
| A 全量仿製另一套資料／AI／UI | 直接另立資料表、Schema、分頁或引入未核准規則 | **高風險**：Duplicate SSOT、基金 identity／FX／Risk Cap 語意漂移 | 初期看似快，後續返工成本高 | 不採 |
| **B 基金既有契約差異稽核 → 補最小守衛 → 經 Gate 施工** | 逐項核對 `67`／`75`／BL-0527／BL-0545 與程式 caller／tests，僅補真正缺口 | **最低風險**，可回滾，避免重新命名／重定義 | 中等實作速度、最低重複 Token | **推薦** |
| C 重構 UI／Digest／Brain 全鏈 | 在所有功能完成前大幅重寫架構 | **高風險**：凍結契約衝突、投資語意與資料來源不一致 | 慢／最高成本 | 不採 |

## 4. 建議執行次序與授權邊界

**目前優先，不改排程：**
1. 維持 #1211 隔離雙模式 PoC 的既有權限與 QA／CI／merge Gate；本文件不得修改其分支或任務範圍。
2. BL-0545 繼續是唯一全域 NEXT；不得要求使用者立即提供真實 Active Sheet、不得把 live 模式未實作說成已完成。
3. 12→13px、grey／neutral、設定頁、正式雙模式、G7 依 `DEC-2026-11-11-02` 延後／另 Gate；不因本研究動工。
4. **下一個適當、獲授權的架構／資料契約研究批次**：唯讀建立 F-01～F-08 的 Existing Contract → Runtime → Gap → Recommended Minimal Test/Change → Gate 矩陣；必須標明 verified／not found／not run。查基金 repo，不要求跨 repo 讀取或同步；若已存在同等矩陣，直接補差異，不另建競爭規格。
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
