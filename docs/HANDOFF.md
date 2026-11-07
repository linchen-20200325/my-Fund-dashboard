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
| main | `025922382ef3921fc7b6858cb733084935fbf066` | 這不是永久最新 SHA |
| #1163 | **merged=true**，merge SHA 同上；B／S1 設計與合法適用性文書已進 main | [PR #1163](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1163) |
| Open PR | **僅 #1164，Draft**；base `02592238`；head `4f045c26e64f71901bcf14db9209c7338f7de2dc`，mergeable=true | [PR #1164](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1164)；Code **尚未合入 main** |
| #1164 最新 head CI | [run 42359253829](https://github.com/linchen-20200325/my-Fund-dashboard/actions/runs/42359253829) Fast／Schema／Slow／Visual 均 **success** | 只適用 head `4f045c26` |
| Code | ≤768px 五格同列頁首／無橫滑／至少 48px；769px+ 原側欄；僅 🌍 可進、🤖 不開放；原無效 sticky 已在此 PR 修正 | `ui_v3/shell/nav.py`、`pages/chrome.py`、tests；**未正式上線** |
| 視覺證據 | PR 已加入 374／375／390／768／769／1280 及 190% 模擬的 Chromium **fixture** JSON／PNG | `docs/evidence/bl0544_s1_chromium_fixture_2026_11_07/`；不等於正式 Cloud／真機／WebView |
| QA／review | 0 unresolved threads；最新 head 非作者增量 QA 是否達完整 Gate **NOT VERIFIED** | COMMENTED review／CI 四綠不得自動當獨立 QA |
| main CI | 本次未取得 main HEAD 的逐 job 結論 | **NOT VERIFIED** |
| 清理線 #1152／#1153／#1154 | GitHub 均顯示 `merged=true` | BL-0543 的舊「三 PR 尚未合併」敘事不得復活 |

## 2. 唯一 NOW：BL-0544／PR #1164 結案驗證

**不再做 S1／S2 選型，不再做 #1163 文書 QA，也不再叫 Claude 重修已修的 37 tests、sticky 或 fixture JSON 換行。**

- Claude Code 負責 Code／測試／必要非作者技術 QA；ChatGPT 負責獨立 GitHub Gate、規格、文件與符合條件的 Auto-Ship。ChatGPT 不能僅靠留言聲稱已啟動外部 Claude 工作階段。
- #1164 最新 head `4f045c26` 已解決 `c3117554` 的 37 測試失敗、`4ff03a49` 的 non-sticky 表述缺口，以及 `d27dad13` 的兩個 JSON 檔尾換行造成的 Fast CI 失敗。**舊紅燈不能沿用作現在的結論**。
- **尚未證實**：真正非作者最新 head QA；production-like Cloud 390／1280 正式畫面確認；真機／WebView／OS 字體放大／讀屏。Preview 帳號入口目前 **NOT IMPLEMENTED**。fixture PASS 不能寫成 Cloud PASS。逐項確認是否是本批依上位規格必備的合併 Gate；不能為求合併自行降級為非阻擋。
- **單一步驟**：對最新 head 取得獨立增量 QA 與正式視覺 Gate 判斷／證據 → 重新查四項 CI、diff、threads、review → 真正符合 Gate 才合併。若實測不能取得，留 Draft，明示唯一硬阻塞與需要的授權／環境，不重複開 PR。
- 不動 frozen `docs/v2/44`／57／CONSTITUTION、Old UI／`ui_v2`、OAuth、Active Sheet 正式設定、金融資料、公式、FX、Risk Cap、OneBrain／Phase7、cutover；`DEC-2026-11-07-01/02` 為已核准 S1 射程。

## 3. NEXT／LATER（只安排已有安全條件的批次）

| 順序 | 工作 | Gate／owner |
|---|---|---|
| NEXT | 更新本 HANDOFF／BACKLOG 的過期指標 | ChatGPT 文件批；不等於 #1164 已 merged，文件 PR 自己須驗收 |
| NEXT | BL-0545 五維健康評級覆蓋率唯讀分母調查 | ChatGPT 設計／Claude Code 必要 probe；既有來源、不可改原 Grade／門檻／資料准入規則 |
| LATER | BL-0542 💼 我的資產 G-3～G-5 | UI 設計部分核准，資料／配息／整頁接線 Gate 未全授權 |
| LATER | BL-0530 找基金 ISIN → MoneyDJ deterministic identity | research-only；無已核准 source 時不得啟用 mapping |
| LATER | 設定登入、BL-0534 frozen amendment、BL-0535 cutover、OneBrain／Phase7 | 各走正式授權、獨立 QA、必要人工／法規 Gate |

## 4. 新對話／compact 後交接自驗

- [ ] 我已重新讀取 main SHA、Open／Draft PR、PR merged flag、最新 head diff、四 job conclusions、review／threads。
- [ ] 能分清 **已在 main**、**Draft PR 中**、**尚未授權**、**NOT RUN／NOT VERIFIED**，不把 fixture 當正式畫面。
- [ ] 沒有重派 #1163 工作、重開 #1164、再次「修復」舊 head 已結案的問題。
- [ ] 最新 PR／CI 狀態寫在 GitHub 可追溯處；下一個 owner 與單一接手點清楚；只有已核准的安全工作才繼續。
- [ ] 作者／非作者 QA 分離，`COMMENTED`／自述不冒充非作者驗收；無證據不 merge。
- [ ] 文件或聊天太長仍從 GitHub 重查；本 HANDOFF 不能取代即時核驗或現行正式 DEC／SSOT。

> 這份文件沒有創造新客戶裁示或改動高位階治理條文；詳細執行與權限一律回到 `CLAUDE.md`／`PROJECT_RULES.md`。舊交接保存在 history，僅作追溯。
