# HANDOFF — 基金 New UI2 唯一現行接手點（2026-11-07）

> **⏯ Resume Checkpoint（2026-11-07；唯一現行）**

> **不是完成證明**：本頁只是熱交接索引；任何 main SHA、PR、CI、QA、合併與授權須先獨立重查 GitHub。上一版全文逐字保全在 `docs/evidence/history/2026-11-06_handoff_before_top_tabs_health_ruling.md`（**NOT CURRENT**）。歷史對話快照 #1158 仍供追溯，但新的兩項裁示已在 `DEC-2026-11-06-01`／`-02`；不能以舊快照或 ChatGPT Memory 取代本次裁示。

## 1. GitHub Verification Gate（本次量測，不保證之後不漂移）

| 項 | 2026-11-07 查核 |
|---|---|
| Repository／main | `linchen-20200325/my-Fund-dashboard`；`d0a0af20390af66171f7c75c46aaff9c18a28e0f`（2026-11-07 GitHub 實查；本輪 #1159、#1157、#1151、#1158 依序合併） |
| main CI | `d0a0af20` 的 push／main CI 尚未逐項核對；#1159、#1157、#1151、#1158 各自**合併前 PR head** 的 Fast／Schema／Slow／Visual 四項均 success，不能冒稱新 main CI 已驗過 |
| Open PR（2026-11-07 GitHub 實查） | 僅 **#1163 Draft** 尚未合併（BL-0544 合法適用性／精確線框 Gate）。#1150／#1160 已以 superseded 理由 **closed、未合併**；#1159 → #1157 → #1151 → #1158 **已以一般 merge commit 合併**，其餘 #1152／#1153／#1154／#1161／#1162 亦已合併；非 PR head branch 刪除證據 |
| 已知檢查 | #1163 先前 head `790b3f48` 的 Schema／Fast／Slow／Visual 四項 CI success，**本次 HANDOFF 更新會產生新 head，須重查新 head**；其 frozen 44／57／CONSTITUTION 法定適用性、80 §18.2 舊 amendment 指示與較新 B 的關係及非作者 QA 尚未判為 PASS，精確 Preview 線框／字樣 Gate 未驗。#1158 已合併但僅作歷史對話證據 |
| 文件整合 | #1153、#1161、#1162 已合併；本輪 #1159 `5b27652e`、#1157 `55798db9`、#1151 `18fe3476`、#1158 `d0a0af20` 亦已合併。#1163 仍 Draft，只保存 BL-0544 的有條件核准與提案，**沒有改 frozen 44／57 或程式**，不得當成合法 Gate／施工完成 |

**清理線狀態索引**（只作指標，內容以各 PR 為準）：

| 項 | 狀態 |
|---|---|
| #1152／#1154 | 清理 Work 已合入 main（merge commits `0fa8deb3`／`e1e05ad3`）；#1153 早已合入 main（`be6e1e34`）；後續不得當成仍開放的 Draft |
| 工具盤點 ≠ 死碼確認 | 靜態可達性工具輸出只是候選清單，刪除前仍須逐項人工與 caller 實測 |
| 分支保護 | 讀取 HTTP 403、rulesets=[]：必要檢查 **未驗證**，不得宣稱已驗證 |
| 證據位置 | `BL-0543`；歷史檔 H14 `docs/evidence/history/2026-11-05_cleanup_handoff_superseded.md`（已在 main）；本 PR 的舊 HANDOFF 全文見 `docs/evidence/history/2026-11-06_handoff_before_top_tabs_health_ruling.md` |

## 2. 最新客戶裁示與確定的邊界

1. **`DEC-2026-11-06-01`：手機 New UI2 選方案 B，頁首橫向五頁籤。** 五頁 IA／順序與 🤖 Phase 7 不可進入維持；**這是已裁設計方向，不代表 frozen 44 已 amended 或 `ui_v3` 已改動**。BL-0544 應先獨立核對 44 真實條文與 57／CONSTITUTION，確認 newer DEC 是否足以合法採 successor（方案 B），無直接衝突且程序允許才保留 44 不動；若有真衝突或程序不允許，停手另提正式 amendment。導航與登入設計、390／768／769／1280 及 WebView／safe-area／鍵盤可用性仍須測試。#1150 已關閉；#1151 已更正為新版候選並合併，#1158 合併但僅保留當時歷史快照。
2. **`DEC-2026-11-06-02`：保留既有健康指標及原始評等，另外顯示覆蓋率與正式資料准入狀態。** `compute_4d_health` 名為 4D 但目前五維，2 維加核心維即可有字母等級；原 Grade 與覆蓋率／准入結果不能混成一種安全結論。缺值、unsupported、N/A、未評估都須獨立追溯；**真實 Active Sheet 命中率尚未測得**，不改任何 Grade threshold／金融公式／Risk Cap。後續見 `BL-0545` 與已合併的 #1157 **靜態稽核 evidence**；正式資料准入 ≠ Phase 7。
3. **對話「記憶」是 GitHub 裡的 ChatGPT 對話快照與歷史記錄，不是 ChatGPT 帳戶 Memory**。逐字裁示存 `docs/evidence/decisions/2026-11-06_new_ui2_top_tabs_health_coverage_ruling.md`；#1160 有過期說法的 supersession ledger，舊 Git 歷史不刪；不建立第二套 SSOT。

## 3. 五頁與資料／AI 狀態

| 頁面 | 核准與未完成 |
|---|---|
| 🌍 市場與趨勢 | `docs/v2/81` 線框已核准，保留已有 Preview，不重畫 |
| 💼 我的資產 | `docs/v2/82` U1～U5 **僅 UI 方向**已核准，仍須完整合法線框／資料 Gate；主圖先於四格，持倉去重但保留所有部位，NAV＋σ 同圖與配息台幣、USD 100 萬、A／B／C 僅候選，**不直接搬舊交易公式** |
| 🔍 找基金 | 基金代碼身份與單檔／篩選兩區語意已核准；整頁 New UI2 線框尚待核准 |
| ⚙️ 設定 | 登入／Active Sheet／資料健康分離；#1161 登入設計、#1162 頁首導覽方向文件均已合入 main；#1163 仍是 Preview-only 施工前合法 Gate，OAuth 不改 |
| 🤖 AI 投資總結 | `docs/v2/67`／`75` OneBrain 設計；Phase 7 前不得註冊／執行。Digest／Evidence 必須完整，UI 簡化不刪 AI Context |

## 4. 接手點與禁止事項

唯一下一接手點：先完成 #1163（BL-0544 客戶已裁方案 B）之非作者**合法適用性稽核**，逐條核 frozen 44／57／CONSTITUTION、導覽與登入／首屏／斷點、並完成精確 Preview 線框與字樣 Gate；無直接衝突才保留 frozen 44 不動，Gate 通過且文件正式合併後，才依 `DEC-2026-11-07-01` 條件式授權 Claude Code 施工 **Preview-only `ui_v3` 手機頁首五頁籤 Shell 單切片**。若真衝突停手走正式 amendment；BL-0545 的 Active Sheet 覆蓋率唯讀實測另批處理，未經 Gate 不進入程式實作。

- 先讀 `CLAUDE.md` → `PROJECT_RULES.md` → `docs/DECISIONS.md`／`docs/BACKLOG.md` → 本檔；產品規格回查 frozen `docs/v2/44`、子法 1＋57、`docs/v2/67`／`75`／`79`／`80`／`81`／`82`。
- Old UI 唯讀參考、`ui_v2` maintenance-only；不改 production data source、公式、FX 觀測日、Risk Cap、身份與原始持倉；不直接 push main；每批最多三項安全工作；變更 Model／Mode／Effort 必須先依 Hard-Stop Gate。
- 現有 G-3～G-5、完整 💼 renderer、OneBrain／Phase 7 與 cutover 仍未因這次文件裁示獲授權。手機 UI 正式實作前必須完成 44 與相應 guard 的合法收斂。

## 5. 未驗與交接限制

本檔沒有實跑 Cloud 390px／WebView 遮擋、Safari／Android 真機、實際 Active Sheet 五維覆蓋、正式 Google OAuth 與新頁首導航。HTML 設計稿只是視覺候選，不是 GitHub 已上線。所有 PR／CI／head SHA 可能在本文件寫成之後變動，必須重做 GitHub Verification Gate。
