# New UI2｜過期規格與資料能力裁示前審查（2026-11-06）

> 狀態：**設計與資料契約修訂候選，待使用者核准；非正式 SSOT、非實作授權**。本報告不刪除 frozen 44、原始 DEC、Git 歷史，不修改 80 等已核准規格。不宣稱刪除 ChatGPT 帳戶 Memory。
>
> 驗證基準：main `861628cc377352c4f651ddc1172e13ab07e4d90d`；另參 PR #1150、#1151、#1157、#1158 的 **head 文件**（目前 Draft）。正式現況及 CI 在採納前必須重新查 GitHub。

## A. 需取代／停止當成現況的記憶與文字

| 舊敘述 | 新讀法（候選／既有權威） | 處理方式 |
|---|---|---|
| main #1049、Open PR 0、舊五頁 hld/alo 作為 New UI2 | main／PR 每次重新取得；New UI2 固定 🌍／💼／🔍／🤖／⚙️ 五頁（80），Old UI 只作讀碼參考 | 在現行 HANDOFF 更新最新 checkpoint，舊描述移歷史，不刪歷史 |
| 手機永遠使用底部五頁導覽 | 現行 44／80／ui_v3/shell/nav.py **仍採底部**；2026-11-06 使用者提出 **上方橫向頁籤候選**，與 #1150/#1151 衝突 | 準備專案正式 Layout / DEC Gate；核准前不得直接修改 44、80、程式 |
| 一個基金只保留一條部位 | UI 可以按可驗證身份去重聚合，原始保單／持倉列／成本／幣別必須全保留 | 加入 💼 頁完整線框候選；不能用相似名稱合併 |
| 4D / 5D 分數有 A 就代表健康資料完整 | compute_4d_health 實際為五維，符合最少兩維與核心條件即可有等第 | 顯示 n_scored/n_applicable、missing 與有效性，不把 2/5 說成 5/5 |
| 報酬負值或 NAV 下跌就是基金品質惡化 | 市場／同類相對表現／絕對風險／配息來源需分開判讀 | benchmark 與 thresholds 未核准前不得自評品質 |
| 先塞全部原始資料給 AI 才算完整 | 完整 Evidence Registry 不刪；Digest 任務式切片與 expected/received manifest；唯一 OneBrain 反證整合 | Phase 7 前僅架構提案 |
| 舊的 4D／6F、A/B/C 或 HWM σ 可直接搬進 New UI2 | 只重用有來源與版本證據的 domain 演算法；舊 UI／舊交易觸發／寫入路徑不得直搬 | 逐功能 semantic / FX / identity / read-only Gate |

## B. 現有資料可取得性（分清已證實與未知）

| 資料／指標 | 目前證據 | 能否取得的誠實結論 | 後續處理 |
|---|---|---|---|
| 非 USD 外幣**歷史 FX 波動** | services/fx_regime_service.py: SUPPORTED_FX=("USD",) | **現有特定 provider 不支援**非 USD；不是所有外匯資料永久不可得 | 非 USD 維度列 unsupported／不計分；未來對新來源、FX 期間與觀測日另走 Source + Gate；不得用 USD 代替 |
| TWD 計價基金的 FX 風險維 | 五維稽核 #1157 | **不適用**而非缺失 | N/A 不進 applicable 分母 |
| MA60 方向（特定健康報表） | services/health/report.py: ma_dir=None | **該報表路徑未提供**實際 MA 方向，但 trend 可用 1Y 報酬 fallback | 不顯示「MA 已驗證」；未來須逐 caller 核對及合法歷史 NAV |
| 1Y 含息報酬／配息覆蓋 | services/fund_total_return.py、services/health/grade.py | **條件性缺值**：NAV 期長不足、配息序列缺失時不合法 | 保留計算與 Missing reason，不能用 0、不能把模型 proxy 冒充官方本金來源 |
| Sharpe | services/health/report.py / unified.py | **有機會取得但來源、6M/1Y 口徑可能不同** | 列期間、source、Rf／年化定義；不可混同跨基金比較 |
| 1Y 波動 σ | grade.py、現有 guard | **條件性缺值**：歷史不足或 σ <= 0 | Missing；重用合法序列，不以 0 代替 |
| 官方 TER | 歷史兩檔稽核 0/2 | **樣本不足，不能宣稱永遠抓不到** | 保留來源明細，不進現行五維健康評級；待擴大樣本與官方 source |
| 基金規模 | 歷史樣本單位如億美元、百萬歐元 | **原文可得但未有可比標準化口徑** | 先保留 raw Evidence，不做跨幣別比較或評分 |
| 官方「配息涉及本金」 | 需公告／正式揭露 | **未有實際命中率證據** | 與數學 proxy 分離，按基金／配息日期探針 |
| 實際 Active Sheet 基金 NAV、配息、FX 與五維整體覆蓋 | #1157 明載未取得 Active Sheet、未跑真實探針 | **未實測，不能列作全部無法取得** | 經授權唯讀探針，同時報唯一基金數／抓取成功數／適用數，計 eligible／missing／unsupported／N/A／failed／stale／conflicted |
| 跨幣別市值與 100 萬 USD 配息換算 | 82 §2、G-3 資料契約 | **計算准入 blocked**，不等於 FX 永久不可取 | 禁止成本 fallback、假 100% 分母、假台幣收益；待 NAV/FX 觀測日與幣別一致性 Gate |

### 實測驗收建議

1. 由已授權的 Active Sheet 唯讀取得 **全體唯一基金**及對應的**全部原始部位**，記錄 eligible、failed、skipped、unread 與覆蓋率分母；禁止憑基金名稱去重。
2. 先驗 source → 樣本長度 → 口徑可比 → 正式規則准入四層；不以 spot FX 命中代表 FX 歷史波動可算。
3. 各維產出 `source/as_of/observation_date/window/formula_version/n_scored/n_applicable/missing_reason` 供 UI 與未來 Digest 唯讀引用；**不在本報告創設新的正式 schema 或門檻**。
4. 結果分三類：可正式評分、僅揭露不評分、候選淘汰。指標移除須客戶金融規則／Risk Cap Gate，歷史 evidence 不刪。

## C. 五頁藍圖更新優先序（供使用者 HTML 審稿）

- 🌍 已有 New UI2 wireframe 與 preview；本批不重畫、不加入未核准 regime。
- 💼 U1～U5 **只有 UI 設計方向已核准**；保留主圖→四格摘要、去重但保留全持倉、新需求 NAV + 買賣 σ 同圖、配息台幣與 USD 1,000,000、A/B/C 唯讀情境；所有價格、配息及 FX 合法前不假算。
- 🔍 身份與兩區語意已核准；完整 New UI2 單頁線框仍需核准。
- ⚙️ 帳號／Active Sheet／資料健康度分離；#1150 草稿與頁首導覽衝突須先解決。
- 🤖 Phase 7 前只能描述候選頁，不掛 runtime、不生成 AI 分析。
- **手機導覽三方案**：A 保留底部＋safe-area（與嵌入 App 遮擋風險仍在）；B 頁首可橫向捲動的五頁籤（最直接解決遮擋，須正式 Layout Gate）；C 頁首單一選單（最省空間但降低五頁可見性）。**建議 B 供客戶確認，核准前不施工**。

## D. 治理與限制

- 將本文件視為「審稿候選」，沒有任何舊正式決策被本 PR 自動撤銷。確定的過期敘述在下一個不撞檔治理 PR 更新 `docs/BACKLOG.md`／`docs/HANDOFF.md`；新客戶裁示經核准寫進 `docs/DECISIONS.md`。
- 已開 Draft #1150／#1151／#1157／#1158／#1159 及清理 Work #1152～#1154；本批不修改其編輯中的檔案、不直接 push main、不合併 Draft。
- **ChatGPT Memory 不能由 GitHub 修改。** Repo 中舊聊天快照可標 NOT CURRENT 並引用現行決策；帳戶記憶的完整移除另須使用者在 Settings → Personalization → Memory summary → Manage 修訂、刪除含有該內容的原始聊天與其他來源。
