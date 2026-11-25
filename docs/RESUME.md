# RESUME｜投資基金 輕量接續索引

> **衍生索引，非第二權威；不構成施工授權或驗收證明。** 一律以 [#1296](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296) 最新有效客戶裁示與正式規則為準；與之衝突時本檔作廢。
> 快照：2026-11-25（Asia/Taipei）；main `d509bdb3`。**狀態會過期，本檔數字不得當現況引用。** 一般「接續」只讀輕量錨點與最新增量；**正式驗收、Ready／merge 前才完成原 LIVE Gate**（見第 7 節）；未核項目標 NOT VERIFIED。

## 1. 先讀（順序）
1. **輕量錨點（一般接續的第一步）**：#1296 comment [7161727036](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7161727036)，及其後**最新有效增量**（以 #1296 最新留言為準）。只恢復：身分、版本、工作線、未完成事項、必要證據入口。
2. **按需再讀**：正式文件 `CLAUDE.md` → `PROJECT_RULES.md` → `docs/HANDOFF.md` → `docs/BACKLOG.md` → `docs/DECISIONS.md` → 適用 Constitution／spec／Contract；只讀本次任務必要者。
3. **歷史導航**：永久封存 #1296 comment [7157975400](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7157975400) 保留作歷史導航，**不是**一般接續的起點，其現況差額已由上列錨點更新。
- 注意：`HANDOFF.md` 仍是 2026-11-21 快照；`STATE.md`、舊大型 handover 為歷史，皆不作現況。

## 2. 版本：正式 v0.1 vs 候選 v0.2（不得混為一談）
- **正式執行**：v0.1＋有效 DEC／Contract；凍結 `docs/v2/44_fund_ui_ssot.md`；正式 amendment（含 `57`）；`79`–`81` 適用條文。程式版本＝exact main，非 release／Cloud 部署版本。
- **候選方向（未發布）**：FUND-v0.2-REAL-DATA-FIRST（#1296 [7099966150](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7099966150)）；版本指引 [7110807758](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7110807758)。
- **已定案設計**（優先於舊圖，不重畫、不重問）：[7131458348](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7131458348)——合法資料→既有確定性規則→共用 Digest 邏輯證據→New UI2 五頁＋OneBrain×1。**不是**正式 Digest／Runtime 授權。
- #1334（版本導航）仍是 Draft，未合併；本檔不取代它的正式化程序。

## 3. 已入 main 的治理（FACT，2026-11-25）
- #1340 一般 merge commit 入 main，#1338 隨祖先鏈 merged；DEC `-24-02`、`-25-01`～`-07` 各一次；`BL-0562` 一列；push run 45580779093 四項＋Slow 實際 step success。
- 精確授權：A 七項守衛例外（`-06`）、C 第四檔（`-05`）、分角色複製派工（`-07`）。B 的 `DEC-2026-11-24-01` **尚未入 main**（隨 #1337）。
- 成果優先 Outcome-First：[7132092153](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7132092153)、[7132100934](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7132100934)（七禁令；比例為資源方向，非安全上限）。

## 4. 各線快照（觀測自 #1296；需 LIVE 重核）
| 線 | PR／head | 狀態 | 下一步 |
|---|---|---|---|
| A 🔍 | #1336 `7a5b631a` | 九檔技術 PASS 沿用；新候選 CI 與專屬 Ready／merge 授權未見 | 只收 CI 差額 |
| A 💼／🌍 | #1339 `f11fc258` | 靜態與負控 PASS；獨立 390／1280 與零外連證據缺（HOLD）；Gate-M／G1／G5 作者回存見 [7160448067](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7160448067) | 在可證封鎖外連環境補獨立畫面證據 |
| B 11641 | #1337 `29aa8277` | 前輪 HOLD；MF2／MF3 剛修，待 Work 複驗；`LIVE_ENABLED=False`、零真請求 | Work 只驗 MF2／MF3 |
| C OneBrain | #1341 `2ae05e78` | 精確四檔；MF-C1／C2 剛修，待 Work 複驗；CI 待終態 | Work 增量複驗 |
| 其他 | #1335／#1334／#1331／#1330 | DEFERRED／待同步；#1335 與 #1339 於 `nav.py` 衝突另排 | 依原裁示，不共編 |
- Work＝非作者 QA；O 僅在 Work **明確不可用**時備援，不得自驗治理文件，provisional 不取代正式 Gate。

## 5. 11641（TDCC）推進
- 優先 11641，11639／11642 後評估；私人資料後續本機。B 規格 rev3.1 PASS（[7132928714](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7132928714)）、腳本施工授權（[7133015104](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7133015104)）。
- **未驗**：R0 實際回應、官方唯一對應、級別文字、R-1 欄位、真 urllib3、真 NAV、Windows。真 OAS／NAV 請求須另行明示授權，不因合併或 CI 解除。

## 6. 既有 HOLD 與安全邊界（全數繼承；本檔不新增、不解除）
- 資料：Missing≠0、unknown≠safe、STALE≠fresh、未評估≠未通過、配息缺失≠無配息；`nav_date`／`cache_updated_at`／原始擷取時間分離；proxy≠真資料。
- 不授權：真取數與 R1–R4／T0／T1、正式 L1／L2／Schema／Digest／Provider／Runtime／D2-G2／AI USE、Phase 7、正式掛載／`ui_v2`、Cloud、Secrets／NAS／OAuth／FX、公式／交易規則／Risk Cap。
- 未核定不得施工：市場雙線色票、stHeader 縮 40px、AS-2／3／4、MK-2／3、BL-0545／0551（BLOCKED）。
- 不得把已合併治理當產品已上線；不得用文件冒充功能；不得只記阻塞不指定責任人。

## 7. 輕量接續規則
1. **一般接續**：先讀輕量錨點與最新增量（第 1 節）；查進度只查**新差額**；派工只讀本次必要證據；未核項目標 NOT VERIFIED。**不得**把完整 LIVE Gate 當每次接續的第一步。
   **正式驗收、Ready／merge 或任何引用現況作結論前**，才完成原 LIVE Gate：main SHA、Open PR head／base、exact-head CI 四項與 Slow 實際 `Run AppTest (slow lane)` step；舊 CI 不得挪用到新 head。既有正式驗收與安全標準不降低。
2. 最多三條活躍線、單一 writer；同檔寫入需協調；已 PASS 不重驗，只驗新 SHA／新差額。
3. 永久靜默：成果、阻塞、CI、交接只回存 #1296；除真正需新客戶裁示或人工操作外不聊天。
4. 事實／推論／建議分開寫；未驗證項明標 NOT VERIFIED，不把推測寫成事實。
5. Ready／merge／deploy 一律需客戶針對 exact SHA 的明示授權；不自行為之。
6. 無新任務即釋出槽位，不派無成果的反覆分析。

## 8. 證據入口
- 治理正本：`docs/DECISIONS.md`、`docs/BACKLOG.md`（`BL-0562`）；Gate-D：`docs/evidence/gate_d_path_b_contract_package_2026_11_18.md`。
- 守衛矩陣：A [7150037256](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7150037256)；精確授權：[7151556522](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7151556522)、[7148843625](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7148843625)。
- 最近 Work 驗收：[7161452041](https://github.com/linchen-20200325/my-Fund-dashboard/issues/1296#issuecomment-7161452041)。
