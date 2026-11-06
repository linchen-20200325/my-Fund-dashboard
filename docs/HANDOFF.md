# HANDOFF — 基金 New UI2 唯一現行接手點（2026-11-06）

> **不是完成證明**：本頁只是熱交接索引；任何 main SHA、PR、CI、QA、合併與授權須先獨立重查 GitHub。上一版全文逐字保全在 `docs/evidence/history/2026-11-06_handoff_before_top_tabs_health_ruling.md`（**NOT CURRENT**）。歷史對話快照 #1158 仍供追溯，但新的兩項裁示已在 `DEC-2026-11-06-01`／`-02`；不能以舊快照或 ChatGPT Memory 取代本次裁示。

## 1. GitHub Verification Gate（本次量測，不保證之後不漂移）

| 項 | 2026-11-06 查核 |
|---|---|
| Repository／main | `linchen-20200325/my-Fund-dashboard`；`861628cc377352c4f651ddc1172e13ab07e4d90d` |
| main CI | 該 SHA 上 Fast／Schema／Slow／Visual Fidelity 均 success（查詢時點）；不是對任何開放 PR 的合併背書 |
| Open PR | #1150／#1151 設計 Draft；#1152～#1154 清理 Work（#1153 已非 Draft）；#1157 4D／5D Draft；#1158 對話快照 Draft；#1159 治理 Draft；#1160 **本次規格與 GitHub 記憶收斂 Draft** |
| 已知檢查 | #1157 head `161784a6` Fast failure 源自三處 Markdown trailing whitespace（pytest passed；尚未修）；#1158 `ff407e54` Fast／Schema／VF success、Slow 在本次檢查仍 in_progress；#1160 head 及 CI **需重新查** |
| 編輯衝突 | #1150 改 `docs/DECISIONS.md`（預留 `DEC-2026-11-05-01`）；#1153 改 `docs/BACKLOG.md`／`docs/HANDOFF.md`（預留 `BL-0543`）。#1160 **不可直接合併**，須在既有 PR 收斂後重對 base、無損整合與獨立 QA |

## 2. 最新客戶裁示與確定的邊界

1. **`DEC-2026-11-06-01`：手機 New UI2 選方案 B，頁首橫向五頁籤。** 五頁 IA／順序與 🤖 Phase 7 不可進入維持；**這是最新設計方向，不代表 frozen 44 已依法 amended 或 `ui_v3` 已改動**。先完成 `BL-0544` 的逐條 44 衝突定位／合法 amendment、導航與登入設計差異、390／768／769／1280 和 WebView／safe-area／鍵盤可用性驗收。#1150／#1151／#1158 的固定底部描述是較舊對話記錄，不能再誤用為新方向。
2. **`DEC-2026-11-06-02`：保留既有健康指標及原始評等，另外顯示覆蓋率與正式資料准入狀態。** `compute_4d_health` 名為 4D 但目前五維，2 維加核心維即可有字母等級；原 Grade 與覆蓋率／准入結果不能混成一種安全結論。缺值、unsupported、N/A、未評估都須獨立追溯；**真實 Active Sheet 命中率尚未測得**，不改任何 Grade threshold／金融公式／Risk Cap。後續見 `BL-0545`、#1157；正式資料准入 ≠ Phase 7。
3. **對話「記憶」是 GitHub 裡的 ChatGPT 對話快照與歷史記錄，不是 ChatGPT 帳戶 Memory**。逐字裁示存 `docs/evidence/decisions/2026-11-06_new_ui2_top_tabs_health_coverage_ruling.md`；#1160 有過期說法的 supersession ledger，舊 Git 歷史不刪；不建立第二套 SSOT。

## 3. 五頁與資料／AI 狀態

| 頁面 | 核准與未完成 |
|---|---|
| 🌍 市場與趨勢 | `docs/v2/81` 線框已核准，保留已有 Preview，不重畫 |
| 💼 我的資產 | `docs/v2/82` U1～U5 **僅 UI 方向**已核准，仍須完整合法線框／資料 Gate；主圖先於四格，持倉去重但保留所有部位，NAV＋σ 同圖與配息台幣、USD 100 萬、A／B／C 僅候選，**不直接搬舊交易公式** |
| 🔍 找基金 | 基金代碼身份與單檔／篩選兩區語意已核准；整頁 New UI2 線框尚待核准 |
| ⚙️ 設定 | 登入／Active Sheet／資料健康分離；#1150 登入草案需與頁首導航收斂，OAuth 不改 |
| 🤖 AI 投資總結 | `docs/v2/67`／`75` OneBrain 設計；Phase 7 前不得註冊／執行。Digest／Evidence 必須完整，UI 簡化不刪 AI Context |

## 4. 唯一下一接手點與禁止事項

**接手點**：先核 #1160 所有變更的獨立 QA、diff／完整 head CI、與 #1150／#1153 的文件競合。**Draft 不合併**。接著依 `BL-0544` 走 frozen 44 最小 amendment Gate、依 `BL-0545` 排 Live Active Sheet 唯讀覆蓋探針；不得把文件合併當施工授權。

- 先讀 `CLAUDE.md` → `PROJECT_RULES.md` → `docs/DECISIONS.md`／`docs/BACKLOG.md` → 本檔；產品規格回查 frozen `docs/v2/44`、子法 1＋57、`docs/v2/67`／`75`／`79`／`80`／`81`／`82`。
- Old UI 唯讀參考、`ui_v2` maintenance-only；不改 production data source、公式、FX 觀測日、Risk Cap、身份與原始持倉；不直接 push main；每批最多三項安全工作；變更 Model／Mode／Effort 必須先依 Hard-Stop Gate。
- 現有 G-3～G-5、完整 💼 renderer、OneBrain／Phase 7 與 cutover 仍未因這次文件裁示獲授權。手機 UI 正式實作前必須完成 44 與相應 guard 的合法收斂。

## 5. 未驗與交接限制

本檔沒有實跑 Cloud 390px／WebView 遮擋、Safari／Android 真機、實際 Active Sheet 五維覆蓋、正式 Google OAuth 與新頁首導航。HTML 設計稿只是視覺候選，不是 GitHub 已上線。所有 PR／CI／head SHA 可能在本文件寫成之後變動，必須重做 GitHub Verification Gate。
