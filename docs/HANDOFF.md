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
| main | `b0ca4b949e969165570c693a24e9f23f51952ac1`（#1164 合併 commit） | 本次觀測，**不是永遠最新 SHA** |
| #1163 | **merged=true**；**歷史 merge SHA `025922382ef3921fc7b6858cb733084935fbf066`**（是 #1164 之前的 commit，不是當前 main HEAD） | [PR #1163](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1163)；B／S1 設計文件已進 main |
| Open PR | **0**（本次觀測）；#1164 **merged=true**，merge SHA `b0ca4b949e969165570c693a24e9f23f51952ac1`；最後 head `4f045c26e64f71901bcf14db9209c7338f7de2dc` | [PR #1164](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1164)；**Code 已合入 main** |
| #1164 已合併 head CI | [run 42359253829](https://github.com/linchen-20200325/my-Fund-dashboard/actions/runs/42359253829)：Fast／Schema／Slow／Visual **success** | 最後 head `4f045c26` 的結論；**不是 merge commit 的 main CI** |
| Code | ≤768px 五格同列頁首／無橫滑／≥48px；769px+ 原側欄；僅 🌍 可進、🤖 不開放；無效 sticky 已修 | #1164 **已 merged 到 main**，但 Preview-only ≠ Cloud 正式上線 |
| 視覺證據 | #1164 已合入 Chromium 合成 fixture 的 374／375／390／768／769／1280 及 190% 模擬 JSON／PNG | `docs/evidence/bl0544_s1_chromium_fixture_2026_11_07/`；**不代表**正式 Cloud／真機／WebView |
| QA／review | #1164 0 unresolved threads；GitHub 3 則 `COMMENTED` review 並非明確非作者 QA 核准；最新 head 完整 QA 證據 **NOT VERIFIED** | **已 merge ≠ QA 自動 PASS**；留下事後稽核缺口，不得否認合併事實 |
| main CI | 本次未取得 main HEAD 的逐 job 結論 | **NOT VERIFIED** |
| 清理線 #1152／#1153／#1154 | GitHub 均顯示 `merged=true` | BL-0543 的舊「三 PR 尚未合併」敘事不得復活 |

## 2. 唯一 NOW：#1164 已合併後的驗收證據／交接一致性核對

**#1163、#1164 均已合併；不重做 S1／S2 選型，不重做舊 PR QA，不重修 37 個 tests、sticky 或 fixture JSON EOF，也不重開同功能 Code PR。**

- Claude Code 負責 Code／測試／必要非作者技術 QA；ChatGPT 負責獨立 GitHub Gate、規格、文件與符合條件的 Auto-Ship。ChatGPT 不能僅靠留言聲稱已啟動外部 Claude 工作階段。
- #1164 **最後 head** `4f045c26` 已解決初版 `c3117554` 的 37 測試失敗，及後續 non-sticky 表述、fixture JSON EOF 格式失敗；最後 head 的四項 CI success，不拿舊紅燈推論現在失敗。
- **已合併但仍未證實**：最後 head 真正非作者完整 QA、production-like Cloud 390／1280 正式截圖、真機／WebView／OS 字體放大／讀屏；Preview 帳號入口 **NOT IMPLEMENTED**。這些仍須依既有正式條款保留驗收缺口，不能把 fixture 當 Cloud PASS，也不能因已合併就說驗證齊備。
- **單一步驟（已合併，不要重複合併）**：回查 #1164 實際合併 SHA、最後 head 四項 CI、review 和正式視覺 Gate，逐一標記 PASS／NOT VERIFIED／NOT RUN。若必要 QA／Cloud 仍缺，登記 **post-merge evidence gap**，辨明環境／責任與下一個最小取證工作，不回滾、重開同功能 PR 或捏造驗收；然後接續 BL-0545 已核准的唯讀研究。
- 不動 frozen `docs/v2/44`／57／CONSTITUTION、Old UI／`ui_v2`、OAuth、Active Sheet 正式設定、金融資料、公式、FX、Risk Cap、OneBrain／Phase7、cutover；`DEC-2026-11-07-01/02` 為已核准 S1 射程。

## 3. NEXT／LATER（只安排已有安全條件的批次）

| 順序 | 工作 | Gate／owner |
|---|---|---|
| 輔助 | 只有 GitHub 再次出現實質狀態漂移時才追加交接更正 | ChatGPT，必查 live source；不得每輪為改文件而開 PR |
| NEXT | BL-0545 五維健康評級覆蓋率唯讀分母調查 | ChatGPT 設計／Claude Code 必要 probe；既有來源、不可改原 Grade／門檻／資料准入規則 |
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
