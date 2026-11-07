# HANDOFF — 基金 New UI2 現行零記憶接手點

> **CURRENT／GitHub-first；觀測日期：2026-11-07（Asia/Taipei）**。本檔是「最後一次查到什麼」的**導航快照**，不是現在的 GitHub 查詢結果，更不是完成、CI 或獨立 QA 證明。任何新對話、長對話 compact、排程巡檢、Claude Code 接手、合併前都必須重新讀 GitHub。
>
> 舊版錯誤將 #1163 當 Draft 且否認 S1 Code 已動工。舊版原文逐字留存在 `docs/evidence/history/2026-11-07_handoff_before_cold_start_resync.md`（NOT CURRENT）；不可用舊版文件、對話記憶、PR body 或排程回報推翻即時 GitHub 證據。

## 0. 無記憶恢復順序（必須重新核查）

1. **只查基金 repo** `linchen-20200325/my-Fund-dashboard`：`main` 完整 SHA、最近 commits、已 merged PR（讀 `merged`、`merge_commit_sha`）；不要拿今天的 main SHA 不同判斷歷史 PR 沒合併。
2. **所有 Open／Draft PR**：逐一查 head/base SHA、diff/files、reviews、unresolved threads、mergeability 和 branches，確認是否已有人施工；PR 分支不等於 main，不能重開重複 PR。
3. **CI 依最新 head**：Fast、Schema、Slow、Visual 逐項查 `conclusion`。新 head 不能繼承舊 head 的 success，`mergeable=true` 不代表 CI／QA 合格；main CI 不可拿 PR CI 冒充。
4. **讀權威文件**：`CLAUDE.md` → `PROJECT_RULES.md` → 本檔 → `docs/BACKLOG.md` → `docs/DECISIONS.md` → 該批正式 SSOT／規格（frozen 44、子法 1＋57、79／80／81／82）。歷史快照不得當現行規格，HANDOFF 不能獨立宣稱完成。
5. **判斷與交接**：標明 NOW／NEXT、owner、可動工 Gate、實際 CI／QA／視覺證據和未驗項；遇到文件與 GitHub 不一致，以即時 GitHub 為準，文件另由安全治理批修正，不重做已合併功能。不具備工具／證據就寫 NOT VERIFIED，禁止猜測。

## 1. 最近一次 GitHub 實查快照（歷史觀測，必須重新查）

| 項目 | 2026-11-07 查到的狀態 | 對應證據 |
|---|---|---|
| main | `b227ae5c8c94bb322eb24c3c1412ec2683819dd8`（#1166 一般 merge commit） | GitHub 2026-11-07 觀測快照，每次重新查 |
| #1163 | **merged=true**；**歷史 merge SHA `025922382ef3921fc7b6858cb733084935fbf066`**（是 #1164 之前的 commit，不是當前 main HEAD） | [PR #1163](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1163)；B／S1 設計文件已進 main |
| Open PR | #1166 **merged=true**，merge SHA `b227ae5c8c94bb322eb24c3c1412ec2683819dd8`；另有本交接文件 PR #1167 Open（head `ae9608df`，最新狀態須再查） | [#1166](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1166)／[#1167](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1167)；不得把 #1166 再當 Draft |
| #1164 已合併 head CI | [run 42359253829](https://github.com/linchen-20200325/my-Fund-dashboard/actions/runs/42359253829)：Fast／Schema／Slow／Visual **success** | 最後 head `4f045c26` 的結論；**不是 merge commit 的 main CI** |
| Code | ≤768px 五格同列頁首／無橫滑／≥48px；769px+ 原側欄；僅 🌍 可進、🤖 不開放；無效 sticky 已修 | #1164 **已 merged 到 main**，但 Preview-only ≠ Cloud 正式上線 |
| 視覺證據 | #1164 已合入 Chromium 合成 fixture 的 374／375／390／768／769／1280 及 190% 模擬 JSON／PNG | `docs/evidence/bl0544_s1_chromium_fixture_2026_11_07/`；**不代表**正式 Cloud／真機／WebView |
| QA／review | #1164 0 unresolved threads；GitHub 3 則 `COMMENTED` review 並非明確非作者 QA 核准；最新 head 完整 QA 證據 **NOT VERIFIED** | **已 merge ≠ QA 自動 PASS**；留下事後稽核缺口，不得否認合併事實 |
| main CI | #1166 merge `b227ae5c` 對應逐 job CI 未查到完成證據 | **NOT VERIFIED**，不能拿 #1166 PR head 四綠替代 |
| 清理線 #1152／#1153／#1154 | 三 PR 均已合併；#1165 交接修復也已合併（`7a3ab87c`） | 不重做、也不把已 merged 的 PR 當 Open |

## 2. 唯一 NOW：BL-0545／#1166 文件驗收與合法唯讀資料 Gate

唯一下一接手點：先獨立驗收本進度 PR #1167 最新 CI／合併條件並完成文件存檔；接著 BL-0545 只讀探針須先取得客戶授權並選定合法輸入與身份對照，未授權前維持 NOT VERIFIED，不改 Grade、正式准入或資料來源。

**GitHub 已合併**：#1163（S1 設計）、#1164（S1 Preview-only Code）、#1165（零記憶 HANDOFF 修復，merge SHA `7a3ab87c268b5e8ca7c39947e37717071840cbcf`）。不重做已合併 PR；原 37 tests／sticky／JSON EOF 歷史失敗不當作現在的阻塞。

- **#1166 已正式 merged**：最後 head `e16a5bbb` 四項 CI success，merge SHA `b227ae5c`；新增 `docs/evidence/bl0545_active_sheet_coverage_probe_status_2026_11_07.md`，僅是已合併研究證據，沒有實測個人 Active Sheet 覆蓋率。main push CI 與 #1166 PR head CI 必須區分。
- **BL-0545 真實持倉覆蓋率 NOT VERIFIED**：沒有合法使用者 Active Sheet session、access token 或持倉清單，也沒有已授權可執行的五維探針。#1166 §7 列出 Decision Gates：新增只讀探針程式、DG2 canonical vs production `resolve_full_keys` 去重口徑、輸入用本人登入還是匿名清單；stale/conflict/unsupported 的正式准入定義與 FX guard 均不得從探針建置授權推導。缺資料不填 0，不用服務帳戶或公開基金樣本冒充個人持倉。
- **#1164 合併後仍未驗**：正式 Streamlit Cloud 390/1280、真機／WebView/safe-area、OS 字放大、讀屏與實資料畫面；最後 head 的非作者完整 QA 未在 GitHub review 清楚證實。Chromium 合成 fixture 不是正式 production PASS；Preview 帳號入口 NOT IMPLEMENTED。歸於 BL-0544 post-merge evidence gap，不重開原 Code PR。
- **遠端分支**：本次 GitHub 列出 main、data、push-assets、#1166 的 evidence branch，以及四組 probe trigger/results（12 條）；`probe/*-trigger` 雖無獨有提交但被 workflows 用作按鈕，`probe/*-results` 存證據；`main`、`data`、`push-assets` 必留。先前 3 條歷史清理候選已不在遠端列舉中，**本輪沒有執行刪除，也未驗其刪除原因／者**。
- **分工**：ChatGPT 獨立 GitHub Gate、產品／治理、文件、已授權 Auto-Ship；Claude Code 只做 Code、技術測試、實測、必要非作者技術 QA（需使用者把提示語交付給外部 Claude session）。每批最多三項安全工作；不得為消除待辦擅改 frozen 44／57／CONSTITUTION、金融 Grade、資料來源、OAuth、Risk Cap、OneBrain 或 Phase 7。

## 3. NEXT／LATER（只安排已有安全條件的批次）

| 順序 | 工作 | Gate／owner |
|---|---|---|
| NOW | 本交接 PR #1167 文件驗收，接續 BL-0545 最小只讀探針 Decision Gate | ChatGPT 驗收 #1167；尚無客戶授權時不派 Claude 改 Code |
| NEXT | BL-0545 真實 Active Sheet 五維分母探針 | 先完成 #1166 文件 PR；探針程式與 Active Sheet 取數欠合法環境／授權，依正式 Decision Gate，NOT VERIFIED 不冒充 PASS |
| LATER | BL-0542 💼 我的資產 G-3～G-5 | UI 設計部分核准，資料／配息／整頁接線 Gate 未全授權 |
| LATER | BL-0530 找基金 ISIN → MoneyDJ deterministic identity | research-only；無已核准 source 時不得啟用 mapping |
| LATER | 設定登入、BL-0534 frozen amendment、BL-0535 cutover、OneBrain／Phase7 | 各走正式授權、獨立 QA、必要人工／法規 Gate |

## 4. 新對話／compact 後交接自驗

- [ ] 我已重新讀取 main SHA、Open／Draft PR、PR merged flag、最新 head diff、四 job conclusions、review／threads。
- [ ] 能分清 **已在 main**、**Draft PR 中**、**尚未授權**、**NOT RUN／NOT VERIFIED**，不把 fixture 當正式畫面。
- [ ] 沒有重派已合併的 #1163／#1164，也不把已合併的 Code 說成仍在 Draft；舊 head 的失敗不當成最新結果。
- [ ] 最新 PR／CI 狀態寫在 GitHub 可追溯處；下一個 owner 與單一接手點清楚；只有已核准的安全工作才繼續。
- [ ] 作者／非作者 QA 分離，`COMMENTED`／自述不冒充非作者驗收；無證據不 merge。
- [ ] 文件或聊天太長仍從 GitHub 重查；本 HANDOFF 不能取代即時核驗或現行正式 DEC／SSOT。

> 這份文件沒有創造新客戶裁示或改動高位階治理條文；詳細執行與權限一律回到 `CLAUDE.md`／`PROJECT_RULES.md`。舊交接保存在 history，僅作追溯。
