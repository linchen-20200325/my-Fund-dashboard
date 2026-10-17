# HANDOFF — 現行交接

> **用途**：自 2026-10-16 起的**現行交接**。只回答六件事：現在在哪、active work、最新 main／PR／CI checkpoint、下一步、blocker／待客戶裁示、新對話從哪開始。
> **歷史交接紀錄**：`docs/handover_2026_09_26_latest.md`（2026-10-16 起整檔轉為歷史紀錄＝~~總管結構判定~~ **客戶裁示**（治理第 5 項，`docs/DECISIONS.md` `DEC-2026-10-16-07`：本檔為唯一現行熱交接；舊大型交接本永久作歷史紀錄、不再續寫；`STATE.md` 保留歷史、不再作現行熱資料來源；有意識的政策變更，不是漏刪，2026-10-16）；第 0 節永遠不准刪＝客戶 2026-09-28 裁示；舊裁示、舊待辦、舊規則原文都在那裡）。
> 出處：客戶 2026-10-16 頒布 Project AI Constitution v1.0（總管轉達要點，對話中，repo 內無逐字原文）；本檔結構依總管 2026-10-16 設計基準。
> 文中若引「約 :N」行號，以 `git show d5d391b:<path>` 讀（本批合併後交接本等檔的行號已因指標行而位移）。

---

## 0. 本檔的規則

1. **HANDOFF ≠ BACKLOG。** 本檔只寫「現在」與「下一步」；未完成工作的主索引在 `docs/BACKLOG.md`，客戶裁示在 `docs/DECISIONS.md`，工作規則在 `PROJECT_RULES.md`。本檔不複製那些內容，只指過去。
2. **本檔不得單獨作為完成或正確的證明。** 任何「已合併」「CI 綠」「已完成」都要能回到 GitHub／git／測試輸出查證；本檔寫的是查詢當下的快照，接手時先重查（見第 5 節）。
3. **更新時機**：每次 merge 後（main SHA）、每完成一輪稽核、milestone、換對話前更新本檔（main SHA、active PR、CI、下一步）。來源是交接本 §0.1（五個觸發點）與 §0.5 第 2～5 條（客戶逐字），**承接不抄**：原文仍在 `docs/handover_2026_09_26_latest.md` 第 0 節；承接規則統一見 `PROJECT_RULES.md` 第 12 節。把「寫進交接本」改讀為「寫進本檔」~~是**總管裁決**（可被客戶推翻），張力見 `PROJECT_RULES.md` 第 14 節之 10~~ → 是**客戶裁示**（治理第 10 項，`DEC-2026-10-16-12`：「每次 merge／audit 後更新交接本」正式改讀為更新本檔；有意識的政策變更，不是漏刪，2026-10-16）。
4. 交接本 §0.6「交接讀取 · 省額度」所稱「HANDOFF 第一節」，自 2026-10-16 起讀作**本檔**（交接本第 0 節開頭已加註；圍欄內逐字原文未改）。
5. 會漂移的數字一律附查詢時間與 SHA；過期就重查，不要引用舊值。

## 1. 必讀順序（新對話或換人接手時）

> 本順序已由客戶治理第 11 項正式統一（`docs/DECISIONS.md` `DEC-2026-10-16-13`）；`STATE.md` 不再作為現行熱資料入口。
> ⚠️ **新對話與所有 agent 開工即適用兩條長期規則（客戶 2026-10-17，不需客戶再提醒）**：`PROJECT_RULES.md` 第 3 節 3.1〈靜默自主巡航／回報節流〉（`DEC-2026-10-17-04`）與第 5 節 5.1〈模型／推理強度主動管理〉（`DEC-2026-10-17-05`）。內容以該兩節為準，本檔不複製。

1. `CLAUDE.md`（資料完整性憲法；`§-2`、`§-1.5`、`§-1` 位階最高）
2. `PROJECT_RULES.md`（專案 AI 工作規則入口；受 `CLAUDE.md` 管轄）
3. 本檔 `docs/HANDOFF.md`
4. `docs/BACKLOG.md`（未完成工作主索引）
5. `docs/DECISIONS.md`（客戶裁示與正式決策）
6. 依任務讀對應 SSOT，例如：
   - `docs/v2/44_fund_ui_ssot.md`（凍結 SSOT，畫面與文案規格）
   - `docs/v2/49_data_integration_plan.md`（資料接線計畫）
   - `docs/v2/55_preview_acceptance_guide.md`（Phase 3 驗收前置與已知限制）
   - `docs/v2/CONSTITUTION.md`（子法 1；**須併讀**正式修正案 #8 `docs/v2/57_amendment_8_directional_judgment.md`，兩者合讀為單一版本，`docs/DECISIONS.md` `DEC-2026-10-16-14`）
   - `EXCEPTIONS.md`（憲法的例外清單與 `8.3.P` 待判定登記簿）

## 2. 現況 checkpoint

**查詢時間**：~~2026-10-16 10:33 UTC~~ ~~2026-10-16 13:18 UTC~~ ~~2026-10-16 14:38 UTC~~ ~~2026-10-16 17:23 UTC~~ ~~2026-10-17 00:37 UTC~~ ~~2026-10-17 02:21 UTC~~ ~~2026-10-17 02:47 UTC~~ ~~2026-10-17 03:10 UTC~~ 2026-10-17 04:22 UTC（`date -u` 實測；狀態更新，不是漏刪）。**查詢方式**：`git fetch` 後 `git log`、`git ls-remote --heads origin`；GitHub REST 唯讀（`gh api` 的 open PR 清單、main commit 的 check-runs；查詢方式 2026-10-16 更新）。

| 項目 | 現況 | 出處 |
|---|---|---|
| main | ~~`d5d391b`（全長 `d5d391bd6f2b14939f71dd1ed0e007449f519f59`；PR #978 的 merge commit，2 parents `cac7c005`、`74b865d4`）~~ → ~~`ab30239`（全長 `ab302390886e1818f0d9a56afccdf3ba9dd7a41b`；PR #979 的 merge commit，2 parents `d5d391bd`、`63ad45d9`），**本批 PR（治理十一項裁示批）合併後更新**；PR 號由總管合併後補（2026-10-16 更新）~~ → ~~`cbf24b5`（全長 `cbf24b5c05c98f1c759d072f3149bdd9adb49787`；PR #980（治理十一項裁示收斂批）的 merge commit，2 parents `ab302390`、`3b0d43f4`）（2026-10-16 更新）~~ → ~~`37ae00f`（全長 `37ae00fc503f7088fcc7a646dcf1746b1123bd73`；PR #982（子法 1 正式修正案 #8）的 merge commit，2 parents `66b60336`、`9f1f79b2`）（2026-10-16 更新）~~ → ~~`c395148`（全長 `c3951482134e412b2db78ddf0d2b15e600e62054`；PR #984（Phase 3 第一批驗收開始、登記 BL-0342／BL-0343）的 merge commit，2 parents `1ab6128f`、`45a64a51`）（狀態更新，不是漏刪；2026-10-17）~~ → ~~`57f03c9`（全長 `57f03c9188f35cf0aaee147625e159aaa002b6ad`；PR #985（對話結束交接同步）的 merge commit，2 parents `c3951482`、`7f72b6d9`）（狀態更新，不是漏刪；2026-10-17 02:21 UTC）~~ → ~~`a3b7e79`（全長 `a3b7e79ad027b86a6264a84d42f6f329c2fd3a1a`；PR #986（UI/UX 與 PIDS 長期方向登記）合併進 main 的 commit，1 parent `57f03c9`）（狀態更新，不是漏刪；2026-10-17 02:47 UTC）。**本批 PR（Phase 3 UI/UX 文件批）合併後 main 會再前進**（~~本交接同步 PR 合併後 main 會再前進一個 merge commit~~，狀態更新，不是漏刪）~~ → `10db810`（全長 `10db8108e64c0809d52e22375d0032ac061fd750`；PR #987（Phase 3 UI/UX 文件批）的 merge commit，2 parents `a3b7e79a`、`7e1a9e30`）（狀態更新，不是漏刪）；2026-10-17 04:22 UTC）。**本批 PR（八題裁示同步＋44 解凍批）合併後 main 會再前進**；接手時以 `git log -1 origin/main` 為準 | 本組 `git log -1 --format='%H %P'` 實查 |
| main CI | ~~`ab30239` 的三條 check-run：Schema gate、Fast checks、Slow tests（informational）皆 `completed`／`success`（逐條看 `conclusion`，不看 run 總結）（2026-10-16 更新）~~ → ~~`cbf24b5`（量測時間 2026-10-16 14:38 UTC）：Schema gate `completed`／`success`；Fast checks 量測時 `in_progress`（尚無 conclusion）；Slow tests（informational）量測時**尚未出現在 check-run 清單**。三條未全部完成，**不得當成 CI 綠引用**，接手時重查~~ → ~~`cbf24b5` 的三條 check-run：Schema gate、Fast checks、Slow tests（informational）皆 `completed`／`success`（量測時間 2026-10-16 15:04 UTC；逐條看 `conclusion`，不看 run 總結；狀態更新，不是漏刪）（2026-10-16 更新）~~ → ~~`37ae00f` 的三條 check-run：Schema gate、Fast checks、Slow tests（informational）皆 `completed`／`success`（量測時間 2026-10-16 17:23 UTC）（2026-10-16 更新）~~ → ~~`c395148` 的三條 check-run：Schema gate、Fast checks、Slow tests（informational）皆 `completed`／`success`（量測時間 2026-10-17 00:37 UTC；逐條看 `conclusion`，不看 run 總結；狀態更新，不是漏刪）~~ → ~~`57f03c9` 的三條 check-run：Schema gate、Fast checks、Slow tests（informational）皆 `completed`／`success`（總管 2026-10-17 以 GitHub check-runs 實查；本組 2026-10-17 02:21 UTC 以同一查詢重查，結果相同；逐條看 `conclusion`；狀態更新，不是漏刪）~~ → ~~`a3b7e79`（量測時間 2026-10-17 02:47 UTC）：Schema gate `completed`／`success`；Fast checks `completed`／`success`；Slow tests（informational）`in_progress`（尚無 conclusion）。**三條未全部完成，不得當成 CI 綠引用**；後續由總管實查（狀態更新，不是漏刪）~~ → ~~`a3b7e79` 的三條 check-run：Schema gate、Fast checks、Slow tests（informational）皆 `completed`／`success`（本組 2026-10-17 03:10 UTC 實查；稽核組 02:59 UTC 查到相同結果；逐條看 `conclusion`；狀態更新，不是漏刪）~~ → `10db810` 的三條 check-run：Schema gate、Fast checks、Slow tests（informational）皆 `completed`／`success`（本組 2026-10-17 04:22 UTC 實查；逐條看 `conclusion`；狀態更新，不是漏刪） | ~~`gh api repos/linchen-20200325/my-Fund-dashboard/commits/ab30239/check-runs` 實查（2026-10-16 更新）~~ → ~~`gh api repos/linchen-20200325/my-Fund-dashboard/commits/cbf24b5c05c98f1c759d072f3149bdd9adb49787/check-runs` 實查（~~ ~~2026-10-16 14:38 UTC~~ ~~2026-10-16 15:04 UTC）~~ → ~~`gh api repos/linchen-20200325/my-Fund-dashboard/commits/37ae00fc503f7088fcc7a646dcf1746b1123bd73/check-runs` 實查（2026-10-16 17:23 UTC）~~ → ~~`gh api repos/linchen-20200325/my-Fund-dashboard/commits/c3951482134e412b2db78ddf0d2b15e600e62054/check-runs` 實查（2026-10-17 00:37 UTC）~~ → ~~`gh api repos/linchen-20200325/my-Fund-dashboard/commits/57f03c9188f35cf0aaee147625e159aaa002b6ad/check-runs` 實查（2026-10-17 02:21 UTC）~~ → ~~`gh api repos/linchen-20200325/my-Fund-dashboard/commits/a3b7e79ad027b86a6264a84d42f6f329c2fd3a1a/check-runs` 實查（~~2026-10-17 02:47 UTC~~ 2026-10-17 03:10 UTC）~~ → `gh api repos/linchen-20200325/my-Fund-dashboard/commits/10db8108e64c0809d52e22375d0032ac061fd750/check-runs` 實查（2026-10-17 04:22 UTC） |
| Phase 位置 | **Phase 2 完成**；分支成果保存批完成（#978）；~~**Project AI Constitution v1.0 導入中**（本批）~~ v1.0 導入完成（#979 已合併）；~~**治理十一項裁示收斂批進行中**（本批）~~ 治理十一項裁示收斂批完成（#980 已合併，`cbf24b5`）；修正案 #8 批完成（#982 已合併，`37ae00f`）；~~**Phase 3 尚未開始**；可以開新對話開始 Phase 3（總管判定）（2026-10-16 更新）~~ → **Phase 3 已開始**（客戶 2026-10-16 同意開始第一批實際／視覺驗收）；準備檢查完成、無 blocker；目前等客戶提供五頁（MKT／HLD／EXP／ALO／SET）390px 首屏與桌面首屏的真實資料預覽截圖；準備檢查發現的兩項已登記 `docs/BACKLOG.md` BL-0342、BL-0343（皆不擋 Phase 3）（狀態更新，不是漏刪）。→ 2026-10-17：客戶已給新的〈B 線 UI Phase 3 提示語〉（取代先前未執行的那一份，`docs/DECISIONS.md` `DEC-2026-10-17-02`）；依它完成的文件：三份唯讀稽核（`docs/evidence/phase3_uiux_audit_2026-10-17/`）、UI/UX Constitution 草案 `docs/v2/58_ui_ux_constitution.md`、五頁 390px 線框 `docs/v2/59_b_line_390_wireframes.md`（方向來源 `DEC-2026-10-17-01`）；~~**改 UI 的批次尚未開始**，等客戶裁示 58 第 13 節（狀態更新，不是漏刪）~~ → 2026-10-17：#987 已合併（`10db810`）；**客戶已裁示 58 第 13 節 8 題（`DEC-2026-10-17-03`：全部照總管建議＝選項 A，附六條護欄）**；44 本輪解凍已改完並重新凍結（44 第七節第三小節之七）；**下一步：P0 第一批（58 附錄 C P0-①②③）**；OAuth 批不開始（狀態更新，不是漏刪） | Phase 2 完成見交接本〈第六十五次更新〉；保存批見〈第六十六次更新〉；#979 見 `git log -1 ab30239`；#980 見 `git log -1 cbf24b5`；#982 見 `git log -1 37ae00f`；Phase 3 時機為客戶 2026-10-16 治理十一項裁示〈本批禁止〉清單之後一句「完成後停在 safe checkpoint，不要自行開始 Phase 3」（2026-10-16 更新） |
| active PR | ~~**本批 PR #979**（導入 v1.0 四份治理文件；由總管開與合併）~~ ~~#979 已合併；**本批 PR 待開**（治理十一項裁示收斂；由總管開與合併，PR 號合併後補）~~ → ~~#979、#980 皆已合併~~ → ~~#979、#980、#982 皆已合併；**目前沒有 active PR**~~ → ~~#979、#980、#982、#984 皆已合併（#984 → `c395148`）；**目前沒有 active PR（本交接同步 PR 除外）**（狀態更新，不是漏刪；2026-10-17）~~ → ~~#984、#985 皆已合併（#985 → `57f03c9`）；open 且非 draft 的有 **#986**（head `ccr-342580ff-lp3eh7`，2026-10-17 02:07 UTC 開立，改 `docs/BACKLOG.md`／`docs/DECISIONS.md`／本檔／`docs/evidence/decisions/`，登記同日客戶的 UI/UX 與 PIDS 長期方向；量測時未合併）；**本批 PR（Phase 3 UI/UX 文件批）待開**，由總管稽核後開立。#986 與本批改同幾個檔、編號已錯開（`DEC-2026-10-17-01`／`-02`、BL-0344～0361／BL-0362～0368），合併時有文字衝突要處理（狀態更新，不是漏刪；2026-10-17 02:21 UTC）~~ → ~~#985、#986 皆已合併（#986 → `a3b7e79`）；open PR 只剩四支舊 draft；**本批 PR（Phase 3 UI/UX 文件批）待開**，由總管稽核後開立（狀態更新，不是漏刪；2026-10-17 02:47 UTC）~~ → ~~#985、#986 皆已合併（#986 → `a3b7e79`）；**active PR：#987（本批，Phase 3 UI/UX 文件批，head `claude/fund-dashboard-b-ui-phase3-0hdhsy`）**，稽核回修中、尚未合併（狀態更新，不是漏刪；2026-10-17 03:10 UTC）~~ → #987 已合併（`10db810`）；**本批 PR（八題裁示同步＋44 解凍批，head `claude/fund-dashboard-b-ui-phase3-0hdhsy` 重建）待總管開立**（狀態更新，不是漏刪）；2026-10-17 04:22 UTC）（舊 draft 四支見下一列） | 總管 2026-10-16 派工單；#979 合併由 `ab30239` 的 parents 實查；#980 合併由 `cbf24b5` 的 parents 實查；#982 合併由 `37ae00f` 的 parents 實查；#984 合併由 `c395148` 的 parents 實查；open PR 以 `gh api …/pulls?state=open` 實查（~~2026-10-16 14:38 UTC~~ ~~2026-10-16 17:23 UTC~~ 2026-10-17 00:37 UTC） |
| 舊 draft PR | #791、#836、#837、#839 四支，**客戶指示不動** | `gh api …/pulls?state=open` 實查（~~2026-10-16 13:18 UTC~~ ~~2026-10-16 14:38 UTC~~ ~~2026-10-16 17:23 UTC~~ ~~2026-10-17 00:37 UTC~~ ~~2026-10-17 02:21 UTC~~ ~~2026-10-17 02:47 UTC~~ ~~2026-10-17 03:10 UTC~~ 2026-10-17 04:22 UTC）：~~open 只有這四支 draft~~ → ~~draft 只有這四支，另有 #987（本批，非 draft）（狀態更新，不是漏刪）~~ → open 只有這四支 draft（#987 已合併；狀態更新，不是漏刪）（~~本批 PR 開之前~~ ~~#980 合併之後~~ ~~#982 合併之後~~ ~~#984 合併之後、本交接同步 PR 開立之前~~ ~~#985 合併之後；另有非 draft 的 #986，見上一列~~ ~~#986 合併之後、本批 PR 開立之前~~ #987 開立之後；狀態更新，不是漏刪） |
| blocker | ~~目前無（依上列實查：~~ ~~main CI 三條 success、~~ ~~無衝突中的 PR；main `cbf24b5` 的 CI 量測時尚未跑完，跑完前不判定為 blocker 也不判定為綠）~~ → ~~無（依上列實查，2026-10-16 15:04 UTC：main `cbf24b5` CI 三條 success、沒有 active PR）~~ → ~~無（依上列實查，2026-10-16 17:23 UTC：main `37ae00f` CI 三條 success、沒有 active PR）~~ → ~~無（依上列實查，2026-10-17 00:37 UTC：main `c395148` CI 三條 success、沒有 active PR（本交接同步 PR 除外）；狀態更新，不是漏刪）~~ → ~~無技術 blocker（2026-10-17 02:47 UTC：main `a3b7e79` CI 兩條 success、Slow tests 未完成，見上列）~~ → ~~無技術 blocker（2026-10-17 03:10 UTC：main `a3b7e79` CI 三條 success）；**待客戶**：58 第 13 節 8 題（BL-0366）擋 Phase 3 改 UI 的批次（狀態更新，不是漏刪）~~ → 無技術 blocker（2026-10-17 04:22 UTC：main `10db810` CI 三條 success）；58 第 13 節 8 題已由客戶裁示（`DEC-2026-10-17-03`，BL-0366 關閉），不再擋 Phase 3 改 UI 的批次（狀態更新，不是漏刪）；方向性政策 blocker：無（客戶 2026-10-16 已核准提案單 #8，`DEC-2026-10-16-14`；狀態更新，不是漏刪）。本次只取消永久禁止，不啟用任何方向性輸出；B 線 v1 仍不輸出正式 production 方向性判斷（`DEC-2026-10-16-14`） | 本組實查；「無」只涵蓋上列查過的項目；方向性政策一項見 `docs/DECISIONS.md` `DEC-2026-10-16-14` |
| 治理面待客戶的唯一動作 | ~~核准〈母法修正提案單 #8〉（`docs/v2/56_proposal_8_directional_judgment.md`）：第 1 欄所列「修改後完整條文」（可改字後核准）＋同一次明示該提案單列出的四點~~；**不擋 Phase 3**（總管 2026-10-16 派工判定）→ **無**：客戶 2026-10-16 已正式核准提案單 #8 全部四項，正式修正案 `docs/v2/57_amendment_8_directional_judgment.md` 自併入 main 起生效（有意識的狀態變更，不是漏刪；2026-10-16；決策者：客戶（#8 核准裁示，`DEC-2026-10-16-14`））。本次只取消永久禁止，不啟用任何方向性輸出；B 線 v1 仍不輸出正式 production 方向性判斷（`DEC-2026-10-16-14`）。待客戶動作：無 | `docs/DECISIONS.md` `DEC-2026-10-16-08`、`DEC-2026-10-16-14`；`docs/BACKLOG.md` BL-0221（已關閉） |

## 3. 下一步與待客戶裁示

**下一步**：

1. ~~本批 PR（`PROJECT_RULES.md`、`docs/BACKLOG.md`、`docs/DECISIONS.md`、本檔，及交接本／`CLAUDE.md`／root `BACKLOG.md`／`TODO.md` 的指標行）→ 稽核 → CI → 合併 → 更新本檔第 2 節 main SHA。~~ → #979 已合併（`ab30239`；狀態更新，不是漏刪）。~~**本批（治理十一項裁示收斂批）**：逐字裁示存檔、`docs/DECISIONS.md` `DEC-2026-10-16-03`～`-13`、`PROJECT_RULES.md` 第 14 節收斂、`CLAUDE.md`／`PROCESS.md`／`STATE.md`／`ARCHITECTURE.md` 指標、提案單 #8 → 至少 1 組獨立稽核（治理規則屬 `DEC-2026-10-16-05` 第二級）→ CI → 合併 → 驗證 main → 更新本檔第 2 節（**本批 PR 合併後更新**）。~~ → #980 已合併（`cbf24b5`；狀態更新，不是漏刪）。~~**本批（提案單 #8 核准裁示批）**：逐字裁示存檔 `docs/evidence/decisions/2026-10-16_proposal8_approval.md`、正式修正案 `docs/v2/57_amendment_8_directional_judgment.md`、`docs/DECISIONS.md` `DEC-2026-10-16-14`、`PROJECT_RULES.md`／`docs/BACKLOG.md`／本檔／提案單 56 狀態同步、守衛 `tests/test_amendment_8_integrity.py` → 獨立稽核（母法／投資語意治理變更）→ CI 全綠 → 合併 → 重新驗證 main → 更新本檔第 2 節（checkpoint 由總管合併後更新）。~~ → #982 已合併（`37ae00f`；狀態更新，不是漏刪）。
2. ~~合併後停在 safe checkpoint；**本對話不自行開始 Phase 3**。之後可開新對話開始 **Phase 3：客戶實際使用／視覺／390px 手機 UX 驗收**（依 `docs/v2/55_preview_acceptance_guide.md`）。~~ → **Phase 3 已開始**（客戶 2026-10-16 同意開始第一批實際／視覺驗收；依 `docs/v2/55_preview_acceptance_guide.md`）：準備檢查完成、無 blocker；**目前等客戶提供五頁（MKT／HLD／EXP／ALO／SET）390px 首屏與桌面首屏的真實資料預覽截圖**。客戶指示：截圖到齊前不改 UI、不因 HLD 取數失敗畫面自行開修復批次；客戶已提供的 HLD 390px「取數失敗」畫面視為驗收證據、**不判定為 UI defect**，待五頁真實資料截圖後由客戶／驗收層統一裁定。準備檢查登記 `docs/BACKLOG.md` BL-0342（Python 3.13 一條測試失敗，未判 root cause）、BL-0343（直接開 `/mkt` 跳 Page not found 提示框），兩項皆不擋 Phase 3、驗收結論前不修（狀態更新，不是漏刪）。客戶回報驗收問題後進 Phase 4（修驗收問題，每批原則上最多 3 項）。
   - **2026-10-17 補記（對話結束交接同步；狀態更新，不是漏刪）**：2026-10-16 實況——客戶當時開的是正式舊站 `app.py`（頂部橫向 tabs、有「[新]」分頁），**不是 B 線預覽**；B 線預覽的 Streamlit Cloud 第二個 App **尚未確認已建立**（repo 內沒有任何 B 線預覽網址）。
   - 下一步：客戶在 Streamlit Cloud 另建第二個 App（repo `linchen-20200325/my-Fund-dashboard`、branch `main`、main file `ui_v2/app_preview.py`），Secrets 依 `docs/v2/55_preview_acceptance_guide.md` §2；`SETTINGS_SHEET_ID` 只填驗收用複本（複本名稱要看得出是複本，並以編輯權共用給服務帳戶），存檔前先在設定與診斷頁看「設定試算表：〔名稱〕」；正式站 App 設定不動。
   - 辨認 B 線：分頁標題「B 線 UI 預覽（非正式站）」、左側欄五頁不帶 emoji、側欄藍框說明、首屏有 `MKT-0` 等結論燈；看到頂部橫向分頁或「[新]」即舊站。市場總覽從網址根目錄進（`/mkt` 會跳 Page not found，BL-0343）。
   - 之後才收五頁 390px／桌面首屏真實資料截圖；截圖到齊前不改 UI、不改 `app.py`／舊站；下一個新對話會收到新的完整 Phase 3 UI/UX 提示語。 → 2026-10-17：「截圖到齊前不改 UI」已由 `DEC-2026-10-17-03` 第 7 題解除（P0 第一批可以開工，截圖仍收作驗收證據）；「不改 `app.py`／舊站」照舊（狀態更新，不是漏刪）。
   - **2026-10-17 方向登記**：客戶確認之 UI/UX／Personal Investment Decision System 長期方向已登記於 `docs/BACKLOG.md`（BL-0344～BL-0361，另補記 BL-0250、BL-0293，另於 BL-0244／0248／0287 補交叉指標）與 `docs/DECISIONS.md` `DEC-2026-10-17-01`；Phase 3 範圍項目仍依 Phase 3 驗收流程逐批（≤3）處理、版面變更先出草稿；Roadmap 項目不得在 Phase 3 實作；新對話以 BACKLOG／DECISIONS 為正式來源（登記不構成動工授權）。
   - **2026-10-17 八題裁示**（`docs/DECISIONS.md` `DEC-2026-10-17-03`；逐字存檔 `docs/evidence/decisions/2026-10-17_phase3_8_rulings.md`）：客戶已裁示 58 第 13 節 8 題（全部選項 A，附六條護欄，58 第 14 節）；44 第 (1)(3)(4)(5)(8) 題範圍解凍已改完並重新凍結（44 第七節第三小節之七；本輪只改正式模式，示範模式另列 BL-0367）；「截圖到齊前不改 UI」由第 7 題解除，截圖仍是驗收證據（護欄 5）。**下一步：P0 第一批（58 附錄 C P0-① 一般畫面去工程化、P0-② 重複錯誤與資料健康收斂、P0-③ MKT 控制項簡化），每批最多 3 項**；不開始 OAuth 批（護欄 4）、不擴張到 Roadmap、不改舊 UI、不新增或替換 production 資料來源、不改資料層與投資業務規則；完成 P0 第一批、CI 與獨立稽核後再回報客戶一次。
   - **2026-10-17 Phase 3 執行提示語**（`docs/DECISIONS.md` `DEC-2026-10-17-02`，取代本小項上方預告的那一份；方向以上一行與 `DEC-2026-10-17-01` 為準）：文件已完成（58 草案、59 線框、`docs/evidence/phase3_uiux_audit_2026-10-17/`、BL-0362～BL-0366）。~~**下一步：等客戶裁示 `docs/v2/58_ui_ux_constitution.md` 第 13 節 8 題**（BL-0366；其中 (7) 決定核准線框後可否不等五頁截圖就開 P0 第一批）；裁示前不改 UI，上方建 App、收截圖的步驟照舊（狀態更新，不是漏刪）。~~ → 已裁示，下一步見上一小項（狀態更新，不是漏刪）。
3. 有時間窗：FX 觀測日探測重跑窗口 2026-11-02～約 11-24（上限約 11-26），錯過要等明年 3 月；重跑方式與按鈕分支見 `docs/BACKLOG.md` BL-0217（按鈕分支窗口結束前不得刪，見 BL-0265）。
4. 本項以外**不構成動工授權**（`CLAUDE.md` §-1）。

**待客戶裁示**（本檔不複製，只指位置）：

- ~~`PROJECT_RULES.md` 第 14 節〈未調和的衝突（待客戶裁示）〉。~~ → 第 14 節 11 項已由客戶 2026-10-16 治理十一項裁示收斂（`docs/DECISIONS.md` `DEC-2026-10-16-03`～`-13`；狀態更新，不是漏刪）；該節改題為〈已裁示的治理衝突（2026-10-16 收斂）~~與尚待程序完成者~~〉→ 尚待程序完成的之 6 已全結（`DEC-2026-10-16-14`；有意識的狀態變更，不是漏刪；2026-10-16；決策者：客戶（#8 核准裁示，`DEC-2026-10-16-14`））。
- **治理面唯一剩餘的客戶動作**：~~核准〈母法修正提案單 #8〉（`docs/v2/56_proposal_8_directional_judgment.md`）第 1 欄所列「修改後完整條文」（可改字後核准），並在同一次簽核明示該提案單列出的四點~~（黑名單前三片語、user 2026-08-07 裁決的讀法、改法、母法同字條文）；詳見 `DEC-2026-10-16-08`。在那之前子法 1 一個位元組都不改，修正程序**~~尚未完成~~**。→ **無**（有意識的狀態變更，不是漏刪；2026-10-16；決策者：客戶（#8 核准裁示，`DEC-2026-10-16-14`））：客戶已正式核准提案單 #8 全部四項；正式修正案 `docs/v2/57_amendment_8_directional_judgment.md` 生效，子法 1 存檔仍一個位元組未改（方案 A）。
- `docs/BACKLOG.md` 中標「需客戶裁示」的條目（例：~~子法 1 條款衝突 BL-0221~~（2026-10-16 由 `DEC-2026-10-16-14` 關閉）；BL-0222（`delete_branch_on_merge`）已由 `DEC-2026-10-16-10` 關閉；以該檔為準；2026-10-16 更新）。

## 4. 分支現況摘要

- 遠端分支的 A～E 分類、保存清單與保存位置：見交接本〈第六十六次更新〉四與 `docs/evidence/README.md`。
- ~~本批**未刪任何既有分支、未建 tag**（PR 自身 head 依 `delete_branch_on_merge` 於合併時自動刪除，屬既有常設授權，總管裁決，可被客戶推翻；見 `PROJECT_RULES.md` 第 10 節、第 14 節之 8）。既有／歷史 remote branch 的刪除須客戶指示；刪前六項確認見 `PROJECT_RULES.md` 第 10 節。~~（#979 批的記載，在寫下當時為真）
- **branch lifecycle（客戶治理第 8 項，`DEC-2026-10-16-10`；有意識的政策變更，不是漏刪，2026-10-16）**：PR 自身 head 依 `delete_branch_on_merge` 於合併時自動刪除，屬正常常設授權、不需每次另問；既有／歷史 remote branch 先做 Preservation Check（`PROJECT_RULES.md` 第 10 節六項），證據完整且明確 superseded 者可進入 cleanup eligible；大批清理、證據不完整、有 production/workflow dependency、刪除具產品或資料保存意義者仍需客戶裁示。**本批不刪任何歷史分支、不建 tag。**
- 遠端分支數：~~19（量測時間 2026-10-16 13:18 UTC；2026-10-16 更新，main `ab30239`，`git ls-remote --heads origin | wc -l`，本批 PR 開立之前；本批 PR head 推送後與合併自動刪除後都會變，引用前重查）~~ → ~~19（量測時間 2026-10-16 14:38 UTC，main `cbf24b5`，`git ls-remote --heads origin | wc -l`；#980 合併之後、本交接同步分支推送之前；推送後會變，引用前重查）~~ → ~~20（量測時間 2026-10-16 17:23 UTC，main `37ae00f`；#982 合併之後、本交接同步分支推送之前）~~ → ~~20（量測時間 2026-10-17 00:37 UTC，main `c395148`，`git ls-remote --heads origin | wc -l`；#984 合併之後、本交接同步分支推送之前；推送後會變，引用前重查；狀態更新，不是漏刪）~~ → ~~21（量測時間 2026-10-17 02:21 UTC，main `57f03c9`，同一指令；本批分支推送之前；會變，引用前重查；狀態更新，不是漏刪）~~ → ~~20（量測時間 2026-10-17 02:47 UTC，main `a3b7e79`，同一指令；#986 合併之後、本批分支推送之前；會變，引用前重查；狀態更新，不是漏刪）~~ → ~~21（量測時間 2026-10-17 03:10 UTC，main `a3b7e79`，同一指令；本批分支已推送為 #987；會變，引用前重查；狀態更新，不是漏刪）~~ → 20（量測時間 2026-10-17 04:22 UTC，main `10db810`，同一指令；#987 合併、head 自動刪除之後，本批分支推送之前；會變，引用前重查；狀態更新，不是漏刪）。

## 5. 新對話 takeover

接手時先做下列驗證，**不得要客戶重講已落盤的資訊**：

1. `git fetch origin`，以 `git log -1 --format='%H %P' origin/main` 確認 main SHA，與本檔第 2 節比對；不一致 → 以 GitHub 為準，先更新本檔再動作。
2. 查 open PR 與 main 最新 push 的三條 CI job（Schema gate、Fast checks、Slow tests）逐條 `conclusion`。
3. 依第 1 節順序讀文件；待辦查 `docs/BACKLOG.md`，裁示查 `docs/DECISIONS.md`，舊脈絡查交接本（凍結，只讀）。
4. 確認 working tree 乾淨、沒有遺留的未提交內容或殘留 worktree。
5. 確認之後再接續第 3 節的下一步；有不一致或新發現，依 `PROJECT_RULES.md` 第 12 節（新發現落盤）寫進對應文件，不只留在聊天。

## 6. 本檔沒查證的部分

- ~~「Phase 3 等客戶指示」與本批範圍為總管 2026-10-16 轉達，本組未見客戶原文。~~ → 本批範圍與「完成後停在 safe checkpoint，不要自行開始 Phase 3」出自客戶 2026-10-16 治理十一項裁示（逐字存檔 `docs/evidence/decisions/2026-10-16_governance_11_rulings.md`）；「提案單 #8 不擋 Phase 3」與「可開新對話開始 Phase 3」是總管派工判定，本組未見客戶原文。
- 第 2 節 main、CI、open PR、遠端分支數為本組 ~~2026-10-16 13:18 UTC~~ ~~2026-10-16 14:38 UTC 實查（#980 合併後的交接同步）~~ ~~2026-10-16 17:23 UTC 實查（#982 合併後的交接同步）~~ ~~2026-10-17 00:37 UTC 實查（#984 合併後的對話結束交接同步）~~ ~~2026-10-17 02:21 UTC 實查（Phase 3 UI/UX 文件批；main CI 另由總管同日實查）~~ ~~2026-10-17 02:47 UTC 實查（Phase 3 UI/UX 文件批，#986 合併之後）~~ 2026-10-17 03:10 UTC 實查（#987 第二輪回修）；`CLAUDE.md`、`PROCESS.md`、`STATE.md`、`ARCHITECTURE.md` 與提案單 #8 由同批其他組撰寫，本組撰寫本檔時未見其定稿。
- `PROJECT_RULES.md`、`docs/BACKLOG.md`、`docs/DECISIONS.md` 由同批其他組撰寫，本檔原稿寫作時尚未見其定稿；PR #979 稽核回修時已把本檔對 `PROJECT_RULES.md` 的引用改為該檔節號。
- blocker「目前無」只涵蓋第 2 節查過的項目，不宣稱窮舉。
- 提案單 #8 核准裁示批只改本檔第 1 節子法 1 指標、第 2 節「blocker」與「治理面待客戶的唯一動作」兩列、第 3 節；第 2 節 main／CI／active PR 等 checkpoint 欄位未動，由總管合併後更新。
- 「客戶是否已建立 B 線預覽 App、Secrets 實際填法」本組無法從 repo 查證（第 3 節第 2 項 2026-10-17 補記的「尚未確認已建立」即指此）。
- 2026-10-17 八題裁示同步批：客戶裁示原文由總管逐字轉存，本組未見客戶對話本身；第 2 節 main／CI／open PR／分支數為本組 2026-10-17 04:22 UTC 實查（本批分支推送之前）。
- 2026-10-17 Phase 3 UI/UX 文件批：客戶提示語原文本組未見（總管轉述）；「先前那一份提示語已被取代」是總管轉述；#986 已合併（`a3b7e79`），本批已把它併入並去重。
