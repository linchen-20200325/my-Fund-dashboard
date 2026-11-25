# RESUME｜投資基金 輕量接續索引

> 衍生索引，非第二權威；不構成施工授權或驗收證明。唯一 SSOT [#1296](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296)，正式規則及最新有效裁示優先。
> 快照：2026-11-25 Asia/Taipei；main `95e17e7061a16ad714854cd7c03e703aa8085e4a`。狀態會過期，未核項目 NOT VERIFIED。

## 1. 接續入口
- 一般「接續」先讀[最新完整交接 #7165566834](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7165566834)及其後最新有效增量，只恢復身分、版本、工作線、未完成項目與證據入口。
- 進度只查新差額；派工按需讀精確 SHA、留言、檔案行數及 CI step；正式驗收、Ready／merge 前完成原完整 LIVE Gate。
- 正式文件按需讀：CLAUDE.md、PROJECT_RULES.md、docs/HANDOFF.md、docs/BACKLOG.md、docs/DECISIONS.md、適用 Constitution／spec／Contract。
- 歷史導航：#7157975400 完整封存、#7161727036 舊輕量錨點；HANDOFF 2026-11-21 快照、STATE.md 舊歷史均不是現況。

## 2. 版本及定案
- APPROVED：正式 v0.1＋有效 DEC／Contract；凍結 docs/v2/44_fund_ui_ssot.md、正式 amendment（含 57）、79–81 適用條文。
- PROPOSED：FUND-v0.2-REAL-DATA-FIRST 候選，未發布；2026-11-20 New UI2 HTML v3 僅視覺參考。
- #7131458348：合法資料→既有確定性規則→共用邏輯證據→五頁 UI＋單一 OneBrain；平行互不阻塞；前三頁各一解釋槽、設定無槽，手機頂五格／桌機側欄。
- Outcome-First #7132092153／#7132100934；不以文件或 FAKE 冒充真功能。#1340/#1338 已入 main，舊 main CI 已驗不重驗。

## 3. FACT／HOLD 快照（使用前按需 LIVE 重核）
| 線 | PR／head | 已通過／剩餘 |
|---|---|---|
| A 找基金 | #1336 7a5b631a | 已一般 merge，main 同已驗 tree；FAKE 隔離 Preview，非真 NAV；main push CI NOT VERIFIED |
| A 市場／資產 | #1339 f11fc258 | 靜態／公式／七例外／負控 PASS；舊候選 CI success；新 main 同步及獨立 390/1280 零外連 HOLD |
| B 11641 | #1337 a337b941 | 程式 MF0、舊候選四項＋Slow step7 success；新 main exact candidate/CI HOLD |
| B 共用快照 | #1344 a4c2d811 | 已有三檔 Draft；前置未完成，程序衝突 HOLD，停止追加，不追認；CI in_progress |
| C OneBrain | #1341 cf843f68 | MF-C2 PASS；MF-C1 修復 d28e21b2 與第二批短解釋待分段 QA；CI in_progress |
| O 索引 | #1342 | 本次同步單檔，MF-RESUME-1 修後待非作者複驗；新 head/CI 按需查 |
| O 授權 | #1343 7a022b51 | DEC-2026-11-25-08 Draft 未生效；原話已補證，出處更新、治理 QA、合併授權待辦 |
| D 盤點 | #7164123963 | APPROVED 唯讀 HOT/WARM/COLD；完整清單 NOT VERIFIED，不刪改 |
- #1335/#1334/#1331/#1330 原排序／HOLD；本輪只查 Open，詳細 refs NOT VERIFIED；#1335 nav.py 衝突另排。

## 4. B 共用快照的條件式授權
- APPROVED D1～D4 原話 [#7165301966](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7165301966)，提案 #7164422442；須先完成契約、既有 Gate、正式治理登記生效及槽位。
- D1 僅 services/v2_domain/nav_evidence.py、tests/test_v2_domain_nav_evidence.py、tests/fixtures/nav_evidence_snapshots.json；純函式、合成資料、離線。
- D2 ISIN 僅本機記憶體，外傳限 rev3.1 聚合白名單；D3 supplier_fetched_at 缺證 null＋gap；D4 非正式 Digest schema，A/C 只讀不重算。
- HOLD MF-NAV-1：A 投影必備欄位、來源與原因對照；缺 cache_updated_at／ConflictDiag 不補造；配息狀態獨立。
- HOLD MF-NAV-2：逐軸權利與逐指標准入；7 日不足不產生長期健診 support；R4 DENY 僅 RJ3，不誤傷合法本機值。
- HOLD MF-NAV-3：深層不可變、取樣邊界、同源及外傳白名單；詳細 [Work #7165268269](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7165268269)。
- #1344 已提前施工，保留證據、不追加、不 Ready/merge；待 Work 與總管處置。三檔守衛可行不等於施工合法。
- #1343 原話補證已完成；DEC 出處更正、獨立分支偏離、非作者 QA、CI、exact 合併授權及合入 main 尚待處理。

## 5. Work 下一棒（只驗增量）
- #1336 main push CI；#1337 新 main 候選及四項 CI／Slow checkout；#1344 程序衝突及三 MF 契約；#1343 治理 QA。
- C 分段：d28e21b2 只驗 MF-C1；cf843f68 驗新增短解釋的功能授權、共用 EvidenceBundle、證據/反證/缺口/可信邊界、AI 失敗不阻塞及零真呼叫。
- A #1339 只驗同步差額；獨立畫面必須有合法零外連環境，不重試被拒路徑。#1342 只驗索引新差額。
- Work 非作者 QA；O 不得自驗治理；O 備援僅 Work 明確不可用，provisional 不替代正式 Gate。

## 6. 既有 HOLD（全部繼承）
- 真 TDCC/OAS/NAV、其他真取數及未授權 R1–R4/T0/T1；LIVE_ENABLED=False；官方 OAS/級別/欄位/Windows/真 urllib3 NOT VERIFIED。
- 正式 L1/L2/Schema/Digest/Runtime/Provider/D2-G2/AI USE、正式掛載/ui_v2、Cloud/部署、Secrets/NAS/OAuth/FX、Phase 7、公式/交易規則/Risk Cap/System Action。
- 市場雙線色票、stHeader 40px、AS-2/3/4、MK-2/3、BL-0545/0551 原 HOLD；Cloud/真機/縮放 NOT VERIFIED。
- Missing≠0、unknown≠safe、STALE≠fresh、未評估≠未通過、配息缺失≠無配息、proxy≠真值；時間欄不互代；衝突 NAV 不作 support_ref；政府顯名、私人持倉本機、Real 失敗不以 FAKE 補畫。

## 7. 接續與施工紀律
- 一般接續／日常進度按需查新差額、未核標 NOT VERIFIED；不得把完整 LIVE Gate 當一般接續第一步。
- 正式驗收及原要求的 Ready／merge 才完成原完整 Gate：main、Open PR refs、候選父節點/tree、checkout/diff、四項 CI 與實際 Slow AppTest step、reviews/threads、有效 DEC/Contract；既有標準不降低。
- 最多三活躍施工線、單一 writer、檔案隔離；D 唯讀不占槽；同 head 已 PASS 無差額不重驗，無新合法任務釋槽。
- 永久靜默：正常成果、CI、MF/SF、阻塞、交接依授權只回存 #1296；只有必要客戶裁示、人工操作或重大異常才聊天。
- 不自行 Ready/merge/deploy/解除 HOLD；不重問已核准事項；不以本索引新增授權或第二權威。

## 8. 精確證據入口
- 最新完整存檔 #7165566834；#1336 正式 Gate #7163666964／合併 #7164419296。
- B/C/O 前輪 QA #7163414730；C 交付 #7164443834／#7164458151；B 前置 HOLD #7165268269。
- #1343 Draft 登記 #7165221352／#7165295643；客戶核准原話 #7165301966；D 唯讀 #7164123963。
- 正式治理正本 docs/DECISIONS.md、docs/BACKLOG.md（BL-0562）；Gate-D docs/evidence/gate_d_path_b_contract_package_2026_11_18.md。
