# 基金規則清理接續｜2026-11-15 批次證據（不是 SSOT）

依 `DEC-2026-11-15-01`；只接續既有稽核，不重新全庫盤點。正式規則、待辦與現況仍依 PROJECT_RULES／DECISIONS／BACKLOG／HANDOFF。本檔由執行組整理，獨立 QA 與遠端 CI 以對應 PR 最終 head 為準。

## 第一批：既有三 PR 已驗收合併

下表為總管本輪 GitHub API 驗證後轉達的結果；本檔執行組未另重做遠端驗收。各 head 的 Fast／Schema／Slow／Visual 均 success，各 merge main 亦逐項 success；非作者獨立 QA PASS，#1251 修正必讀順序後以最終 head 重驗。QA 詳細報告與 merge 事實以 PR 為錨；[三PR結案驗收記錄](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1251#issuecomment-6889739053)。

| PR | final head | merge SHA | main CI run |
|---|---|---|---|
| [#1253](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1253) | `c122811618cb61b632f56e938316f5f232356275` | `da7650ff` | [43676841459](https://github.com/linchen-20200325/my-Fund-dashboard/actions/runs/43676841459) |
| [#1252](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1252) | `09a236aa6fb843ae9e847edcc235bdf5dccb71f3` | `3405949a` | [43674877446](https://github.com/linchen-20200325/my-Fund-dashboard/actions/runs/43674877446) |
| [#1251](https://github.com/linchen-20200325/my-Fund-dashboard/pull/1251) | `0e85e264` | `abc93c4231a83b761f3020cc782e8803e8854560` | [43678133203](https://github.com/linchen-20200325/my-Fund-dashboard/actions/runs/43678133203) |

總管另讀三個 PR head 與三個 merge main 的12個 Slow／Visual實際log末行：每個 Slow＝1283 passed／16 skipped／20238 deselected，每個 Visual＝7 passed；不代表 Cloud／真機。

最後已驗證 main＝`abc93c4231a83b761f3020cc782e8803e8854560`；總管交付第二批時 Open PR＝0。本批記錄時間＝2026-11-15 05:31Z（非 CI 完成時間）。期間正式排程的 `60deb3a` 總經資料更新不是本次清理修改，不碰資料。

## 第二批：原任務2／3／4

| 項目 | 本地結果／狀態 | 保留邊界 |
|---|---|---|
| 規則防回歸 | NOT VERIFIED（待最終 head CI／非作者 QA）；擴充 canonical 守衛：已核准線框、S1 頁首目標、拆 chip、操作入口與錯誤復活 mutant | 只讀現行入口，歷史共用 chip／底部設計仍保留；不改金融 Golden |
| 靜默巡航 | NOT VERIFIED（待 QA／CI）；3.3 CURRENT 為單一操作入口，3.1／3.2 原地指向 | 收緊而不取代；保留非衝突條文、完成格式、揭露與派工／QA |
| Model／Mode／Effort | NOT VERIFIED（待 QA／CI）；5.1 CURRENT 指向第10＋11點，沿用第8 Gate、第9分級 | 正常階段切換只先做目前配置足夠的收尾；途中能力不足／真 Stop Gate 立即停止；升降皆 Gate、送出後全面停手、等待明確恢復；必要 High correctness 不降級 |

本地 targeted 自驗：canonical＋子法存檔完整性＋修正案8完整性共 **40 passed**（其中 canonical **29 passed**，新增4個測試含負控；原有25項→29項）；doc counters **66 passed**；既有首屏拆 chip／字樣守衛 **49 passed**（132則NumPy既有deprecation warnings）。pre-commit 的 whitespace／EOF／merge-conflict／large-file 四項 Passed，YAML無檔可查；pytest-smoke 全套未跑（本機僅跑本次相關測試，遠端Fast仍必須完整通過）。`git diff --check` 通過。Ruff：新增程式無新增命中；全檔既有5項在基準也可重現，未順手擴修。測試 runtime 為 Python 3.12，CI 使用 3.11；未重錄或重跑金融 Golden。第一輪聚合 QA 回修後重驗：canonical **29 passed**（新增實際4個 test 函式，含舊句 addition、81恢復現行、能力不足先收尾負控與歷史引文正控）；doc counters＋兩份凍結完整性守衛 **77 passed**。首屏49項為初稿自驗，回修未重跑；本輪僅改操作入口、文件證據與守衛。四項文字 pre-commit hooks 再次 Passed、`git diff --check` 通過。修改以後的 exact-head CI／非作者 QA 尚未執行，不把自驗或 Draft 當 FIXED。

## 剩餘狀態與真正 Gate

- **CURRENT**：3.3 與5.1第10＋11點現行內容依正式DEC合讀；本批只是原地操作導航，未永久改變分工。
- **HISTORICAL**：舊降級不停手、舊恢復用語與Gate送出後安全工作條款保留原文，失效範圍精確指向10-25-03／11-02-04；不把整節3.1／3.2或第10點宣稱作廢。
- **PENDING-GATE**：BL-0538 讀法確認及 BL-0541 真正逐字搬移；未搬不刪不改既有 evidence／hash。HANDOFF SHA循環仍須 A／B／C 正式裁示，本批更新快照不豁免每merge更新義務。
- **NOT VERIFIED**：原任務1精確symbol勘誤尚未施工；TDCC境內／境外NAV來源語意待Constitution／Decision Gate；原任務5未作政策修改。BL-0545維持BLOCKED，不要求使用者輸入。
- **FIXED**：第一批 #1251／#1252／#1253（依上表遠端驗收）；本批2／3／4須待本PR合併及main後驗才可改標FIXED。

## 完整新對話接手提示語

```text
Model：GPT-6
Mode：Work／GitHub-first／增量接手／靜默自主巡航
Effort：High（治理衝突與防回歸 correctness，不為省Token降低必要驗證）
Repository：linchen-20200325/my-Fund-dashboard

這是既有稽核收尾，不得重啟全庫盤點、重做已合併工作、重開重複PR或第二套SSOT。
先查即時main、Open/Draft PR、各latest head/base/diff/files、四CI逐job conclusions、非作者QA、threads、在製branch。歷史已驗證main abc93c4231a83b761f3020cc782e8803e8854560 不是即時main。
必讀順序：CLAUDE.md → PROJECT_RULES.md → docs/HANDOFF.md → docs/BACKLOG.md → docs/DECISIONS.md → 當批必要SSOT；風險導向只讀相關條文，不漏Gate。
第一批 #1251/#1252/#1253 已合併，證據見 docs/evidence/fund_rule_cleanup_2026_11_15.md；勿重做。
第二批branch fix/canonical-operation-entry-20261115 限原任務2/3/4：canonical負控守衛、3.3 CURRENT單一入口、5.1 CURRENT入口。若仍Open，先讀最新PR head，修未解Must Fix；精確head非作者獨立QA與Fast/Schema/Slow/Visual逐一success後，符合既有Auto-Ship才一般merge commit，再查新main四CI。未驗完不得稱FIXED。
本輪重新指派只限DEC-2026-11-15-01任務，非永久角色改寫。作者不得自任獨立QA。
禁止改frozen44、子法1/57、CLAUDE/PROCESS/EXCEPTIONS、production/UI/data/workflow、公式、RiskCap、FX、DG2、OneBrain。BL-0545仍BLOCKED，不要求真實輸入；S2-T0暫緩。
BL-0538未裁，BL-0541歷史搬移PENDING-GATE；不得搬刪客戶原文、改DEC或sha256鏈。3.3收緊不取代3.1/3.2；5.1第11收緊不取代第10。
下一個唯一安全工作：若第二批已合併且新main四CI已核實完成，不重做2/3/4，直接接原任務1/5；否則先完成現有第二批PR的QA/CI/合併及新main後驗。原任務1/5：symbol勘誤與真正政策Gate分開；HANDOFF每merge更新義務不得擅自豁免，SHA循環須A/B/C裁示。每批最多三項，必要進度存回既有DEC/BACKLOG/HANDOFF，交付完整接手提示語。
```

## M1 修正與本機測試失敗原因

**(a) 獨立 QA M1 與本次修正**：獨立 QA 指出 `PROJECT_RULES.md` CURRENT-EFFORT 區塊「正常下一階段切換時，只可先完成目前配置足以安全處理的本批收尾，再送 Change Gate」未標示其為執行組讀法，可能被讀成客戶原文。本次修正只在該句後加一個括號，標明「收尾先於 Gate」為執行組讀法、可被客戶推翻（見 `DEC-2026-11-02-04` 執行組讀法 (b)、本檔第 5.1 節第 11 點之張力指標），客戶原文僅要求送出 Gate 後立即停下，「目前配置足以安全處理」為本入口對該讀法的限定、非 DEC 原文。未改任何規則效力，未升格為政策。

**(b) 本機測試失敗原因（環境證據，不是 PASS）**：本機以 uv-tool 直譯器（`/root/.local/bin/pytest`，`--noconftest`）跑 `tests/test_canonical_rule_consistency.py tests/test_doc_counters.py`，在 e24bf1c1 結果為 93 passed、1 failed、1 skipped。失敗為 `test_132_point1_page_names_match_registry_in_order`，`ModuleNotFoundError: No module named 'ui_v3.shell'`。實測成因：`--noconftest` 使 repo 根目錄不在 `sys.path`，`tests/ui_v3`（命名空間目錄）遮蔽了根目錄的 `ui_v3` 套件；`ui_v3/shell/registry.py` 實際存在且被追蹤。並非缺第三方依賴。基底 abc93c42 在獨立 worktree 同環境重跑 `tests/test_canonical_rule_consistency.py`：23 passed、1 failed、1 skipped，同一測試同一錯誤，故為既有環境性失敗，非本 PR 引入。加 `PYTHONPATH=.` 於 M1 修正後重跑同兩檔：94 passed、1 skipped、0 failed（本機結果，非 CI）。CI Fast 才是完整依賴／正確 sys.path 下的結果；本節不宣稱 CI 或 QA 通過。
