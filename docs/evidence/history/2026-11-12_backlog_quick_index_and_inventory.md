# NOT CURRENT — Historical BACKLOG quick-index narrative and §3 count snapshots (2026-11-12)

> Original source: `docs/BACKLOG.md` at main `856640fa46fe2f3fd91661d321c6f1e8ea54afaf`; original Git blob SHA `7efa32529a767d8220e18fd73bc54414f0791024`; original sha256 `222fb071af3f3b97dd634ef7afcf24247c926bec49c85b80dd2146c321ad4c7f`; original bytes `639957` (1188 lines).
> The segments below (after the `---` line) are exact unmodified copies of the listed line ranges of that file, as read from that commit. Each segment body lies strictly between its `SEGMENT-BEGIN` and `SEGMENT-END` marker comment lines (the marker lines are not part of the copy); its bytes and sha256 are those of the body lines joined with LF, including the final LF. All BL status, PR, CI, Gate, "待客戶裁示", "NOT VERIFIED" and "單組寫成，未經第二組驗證" assertions in them are historical observations as of their dates, never current instructions and never proof of completion; struck-through (`~~`) text is superseded text kept verbatim. New readers must use the BL rows of `docs/BACKLOG.md`, `docs/HANDOFF.md` and live GitHub.

| id | original lines of `docs/BACKLOG.md` @ `856640fa` | bytes | sha256 |
|---|---|---|---|
| QI-0 | L84–L84 | 589 | `144bc728571aa85d38a024c575e3db5db3d45545fc9e46c7683a87b6b94817bf` |
| QI-1 | L89–L167 | 30842 | `3fb7a93f688746b91fede11643727143919b963f679a19167b09529f44a59eef` |
| INV-1 | L51–L74 | 4323 | `afdd7fa5fabf835830e9bbf308446dce9686d70da0317220f9424526cfcc6687` |

---

## 區塊 QI-0｜〈快速索引〉首行：2026-11-07 最新接手索引（歷史快照）｜原 L84–L84

<!-- SEGMENT-BEGIN id=QI-0 source=docs/BACKLOG.md@856640fa lines=84-84 sha256=144bc728571aa85d38a024c575e3db5db3d45545fc9e46c7683a87b6b94817bf bytes=589 -->
- **2026-11-07 最新接手索引（歷史快照；GitHub 即時優先）**：#1166 研究已合併（`b227ae5c`）；#1168 BL-0545 Phase 1 唯讀探針依 `DEC-2026-11-07-03` 合併（`b34dd2eb`）。探針已授權並實作，live 模式 NOT IMPLEMENTED，真實 Active Sheet 五維覆蓋率 NOT VERIFIED；使用者暫不提供真實輸入。#1167 文件同步已合併（main `861add40`，2026-11-08 查證）。#1164 S1 Preview 已合併但 Cloud／真機／讀屏／真資料畫面未驗；BL-0543 #1152～#1154 均已合併。固定 SHA 只是歷史觀測，不代表當前 main。
<!-- SEGMENT-END id=QI-0 -->

## 區塊 QI-1｜〈快速索引〉2026-10-19 起至 2026-11-05 的逐批登記敘事｜原 L89–L167

<!-- SEGMENT-BEGIN id=QI-1 source=docs/BACKLOG.md@856640fa lines=89-167 sha256=3fb7a93f688746b91fede11643727143919b963f679a19167b09529f44a59eef bytes=30842 -->
- **2026-10-19 合併**：BL-0212 → BL-0250（BL-0223、BL-0224、BL-0343 未合併，只交叉引用 BL-0250）；BL-0244 → BL-0352；BL-0123 與 BL-0377 兩列保留、交叉引用
- **2026-10-19 客戶指示登記（後續規格，deferred）**：BL-0381（Google 個人資料層；與 BL-0349、BL-0363 一起規劃，排在 Phase 3 收尾之後）
- **2026-10-20 客戶裁示登記（deferred，不構成動工授權）**：BL-0382（線框 61:841「⬜ 未設定」與頁上 ◇ 的符號落差；`DEC-2026-10-20-01` Q1）
- **2026-10-20 實機驗收發現（bug，已修待合併）**：BL-0383（選股池 `_sa_present` 認不得 Streamlit TOML table 的 `AttrDict`；`DEC-2026-10-20-02`）（→ 2026-10-20 狀態更新，不是漏刪：選股池部分 PR #1014 已合併；淨值歷史 `_sa_to_dict` 同型部分本 PR 修，合併後結案）（→ 2026-10-21 狀態更新，不是漏刪：#1014 `e2e43a5a`、#1015 `1ca4017f` 皆已合併，BL-0383 已 `closed`，測試隔離在測試隔離 PR 收尾）
- **2026-10-21 批次 3-C 登記（不構成動工授權）**：BL-0384（全站時區表頭字樣不一致；`DEC-2026-10-21-02` Q5）、BL-0385（新設計 H 有一種情形照留，~~待總管~~ → 2026-10-21 總管裁定維持現況，改 deferred；狀態更新，不是漏刪）
- **2026-10-22 舊 UI 功能盤點登記（Gap Matrix；不構成動工授權、也不構成 UI 改版核准；`docs/v2/62_old_ui_gap_matrix.md`、`DEC-2026-10-22-04`）**：BL-0397～BL-0410（14 列；待客戶裁示 11 列、deferred 2 列、待確認 1 列）；另 G1 重驗實機證據 BL-0411～BL-0414（open 2 列、待客戶裁示 2 列）
- **2026-10-22 交接防遺失保存批登記（不構成動工授權、也不構成 UI 改版核准；`docs/v2/63_market_trend_research_baseline.md`、`DEC-2026-10-22-05`）**：BL-0415～BL-0419（5 列；待客戶裁示 2 列（BL-0415 市場趨勢方法專項對齊稽核＝下一個唯一接手點、BL-0416 G-D～G-S 維持 Decision Gate）、open 1 列、deferred 2 列）
- **2026-10-23 SSOT 收斂方向批登記（不構成動工授權；`docs/v2/64_v2_ssot_convergence.md`、`DEC-2026-10-23-01`）**：BL-0420～BL-0423（4 列；待客戶裁示 2 列（BL-0420 SSOT 收斂 12 項、BL-0421 HWM σ 配息假低基期）、deferred 2 列）；BL-0415 唯讀稽核已完成（列尾補記）
- **2026-10-23 裁示 1B／2C／3A 實作批 Save／Handoff Gate 登記（不構成動工授權；`DEC-2026-10-23-02`、`DEC-2026-10-23-03`）**：BL-0424～BL-0434（11 列；open 8 列（BL-0424 PR1b 合併、BL-0425 PR2 續做、BL-0426 PR3 實作、BL-0429、BL-0430、BL-0431、BL-0433、BL-0434 治理待辦）、待客戶裁示 2 列（BL-0427 公式層三題、BL-0428 契約／語意六題）、deferred 1 列（BL-0432））；BL-0420 列尾補記（三項已裁示，狀態不變）；BL-0421 改 `open`（2C 已裁示、待實作）（→ 2026-10-23 狀態更新，不是漏刪：BL-0424 已 closed，PR #1025，main `6024236`）（→ 2026-10-23 狀態更新，不是漏刪：BL-0434 已 closed，`DEC-2026-10-23-04`；BL-0425 客戶指示暫停、維持 open）
- **2026-10-23 BL-0425 結案批登記（不構成動工授權）**：BL-0435～BL-0437（3 列；open 3 列（BL-0435 新版 UI/UX Blueprint 主工作項、BL-0436 Tab3 `_funds_333` 子集、BL-0437 舊 checkpoint 口徑））；BL-0425 已 closed（PR #1028，main `875b80be`）；BL-0427 併入第 (4) 題（NAV 稀疏窗口）；BL-0429、BL-0432 列尾補記
- **2026-10-23 BL-0426 Final Save 批登記（不構成動工授權；`DEC-2026-10-23-06`～`-10`）**：BL-0438～BL-0439（2 列；待客戶裁示 1 列（BL-0438 非 HWM 位置類指標口徑）、deferred 1 列（BL-0439 回測 PIT 已知限制））；~~BL-0426、BL-0421 實作完成、待 PR #1030 合併後改 closed（#1030 open；main `f2539a7d`）~~（→ 2026-10-23 狀態更新，不是漏刪：PR #1030 已合併，main `b35e2620`，BL-0426、BL-0421 已 closed）；BL-0427 併入第 (5) 題（配息日期口徑）與真實資料盤點；BL-0428 補記 (4)(5)、併入第 (7) 題（三處 legacy，**優先**，`recommend_policy` 第一）；BL-0435 列尾補記 UI 項與 Blueprint 必須處理項（`DEC-2026-10-23-10`）
- **2026-10-24 BL-0438 唯讀研究批登記（不構成動工授權；`DEC-2026-10-24-01`）**：BL-0440 新增（open，客戶指示先不開始）；BL-0438 列尾補記（狀態不變）
- **2026-10-24 BL-0440 部分完成補記**：BL-0440 列尾補記（PR #1038 已修項與未修項；狀態維持 `open`）
- **2026-10-24 BL-0440 第二批補記**：BL-0440 列尾補記（ladder235 σ=0 標示、Tab3 雙確認徽章缺值、測試強度三項；狀態維持 `open`）
- **2026-10-24 DG-2 前置 `combine_action` 唯讀盤點**：BL-0441 新增（open，未開始）；BL-0438 列尾補記（狀態不變，DG-2 仍待裁示）
- **2026-10-24 BL-0441 Stop Gate 裁示批（`DEC-2026-10-24-09`）**：BL-0441 列尾補記（分類未判定 → 不提供行動、旁支 (a)(b) 處置）並改 `closed`（隨 `DEC-2026-10-24-09` 實作 PR 合併結案）；BL-0442 新增（其他引擎同型問題，只登記）
- **2026-10-24 `DEC-2026-10-24-10` 補充批**：BL-0441 列尾補記（不重開，維持 `closed`；分類未判定不以品質單軸給換／留行動）；BL-0442 列尾補記（Batch B 唯讀盤點授權、兩處新候選）
- **2026-10-24 BL-0442 唯讀盤點批（`DEC-2026-10-24-10` Batch B；不構成動工授權）**：BL-0442 列尾補記（盤點完成，見 `docs/v2/64_v2_ssot_convergence.md` §10.7；狀態維持 open）；BL-0443～BL-0445 新增（3 列皆 open：BL-0443 安全修 bug 清單、BL-0444 DG-6 候選（需客戶裁示）、BL-0445 dead code retirement gate 候選）
- **2026-10-24 DG-6 裁示批（`DEC-2026-10-24-12`）**：BL-0444 改 `closed`（客戶核准 (a)(b) 兩條，隨實作 PR 合併結案）；BL-0442 列尾補記（其餘平行引擎未核准，維持 open）；BL-0443、BL-0445 照舊 open；BL-0446（open，換標的 4D 重算未傳幣別）、BL-0447（待確認，非配息 vs 配息資料全缺無法區分）新增（只登記，不構成動工授權）
- **2026-10-24 BL-0447 實作批（`DEC-2026-10-24-12` 原則範圍內的安全修，不新增語意）**：BL-0447 改 `closed`（結果 B：以既有 `dividends_fetch_outcome` 區分「確定不配息」與「配息資料缺」；未新增欄位／來源）
- **2026-10-24 BL-0443 安全修批（2026-10-24 客戶授權執行 BL-0443 安全修）**：BL-0443 改 `closed`（7 項 A 已修、第 (2) 項 C 移至 BL-0448）；BL-0448（待客戶裁示，`tag_health_check` 缺值回 Healthy／是否擋行動）、BL-0449（open，App 端換股區吃本金 except 無 log）新增；同日依獨立稽核：BL-0443 第 (1) 項改記「部分處置」，BL-0450（open，紅燈呼叫端 GRAY→False）、BL-0451（open，T7 組合總報酬率成本 ≤0 退 0.0）新增
- **2026-10-25 BL-0449～BL-0451 安全修批（2026-10-25 客戶授權執行）**：BL-0449、BL-0450、BL-0451 改 `closed`（吃本金 except 補 log；紅燈 GRAY → None 三態；T7 組合總報酬率成本 ≤0 → ⬜）
- **2026-10-25 New UI Capability Matrix 收斂批（`DEC-2026-10-25-01`；文件批，不構成動工授權、也不構成 UI 改版核准）**：`docs/v2/62_old_ui_gap_matrix.md` §6；BL-0397、BL-0400、BL-0402、BL-0403、BL-0405、BL-0435、BL-0351 列尾補記（狀態不變）；BL-0452 新增（待客戶裁示，五頁 Refresh／Retry 一致化）
- **2026-10-25 ⚙️ 設定頁最終 Wireframe 與 CAP-GATE-01／02 裁示落盤批（`DEC-2026-10-25-02`；文件批，不構成動工授權、也不構成 UI 改版核准）**：`docs/v2/65_set_wireframe_and_cap_gate_01_02.md` 改寫為最終 Wireframe（客戶待審）；BL-0402、BL-0381、BL-0392、BL-0349 列尾補記（狀態不變）；BL-0342 列尾補記；BL-0453 新增（open，`tests/ui_v2` 示範模式 md5 測試本機紅、CI 綠，只調查不修）
- **2026-10-26 批 3b 合併後登記（不構成動工授權；#1070～#1073）**：BL-0460～BL-0469（10 列；待客戶裁示 8 列（BL-0460、0461、0462、0463、0464、0466、0467、0468；其中 BL-0460、0461、0462、0466 屬 Decision Gate：資料來源／產品方向／formula／data identity）、open 2 列（BL-0465 部署事項、BL-0469 批次 4 剩餘與批次 5 文件同步））；BL-0454～BL-0459 照舊
- **2026-10-26 批次 4 稽核登記（不構成動工授權；對象 main `623f982e`，修復 #1075）**：BL-0470～BL-0477（8 列；待客戶裁示 5 列（BL-0470～BL-0474，皆使用者可見字樣／行為，屬 Decision Gate）、open 2 列（BL-0475 查證、BL-0477 D1 雙層側欄導覽 Phase 1 設計，線框須客戶核准）、closed 1 列（BL-0476，稽核 F2／F3／F4／F11 已由 #1075 處置））
- **2026-10-27 D1 Gate 裁示批登記（不構成動工授權；`DEC-2026-10-27-01`～`-06`）**：BL-0477 改 closed（Phase 1 設計結案）；BL-0478～BL-0482（5 列；open 2 列（BL-0478 頁序頁名程式＋守衛對齊（排序＝總管排程決定）、BL-0479 方案 A 殼層實作，含未裁小題）、blocked 2 列（BL-0480 🌍 規格補完、BL-0481 EPS × 本益比情境，待客戶資料）、closed 1 列（BL-0482 一鍵再平衡排除邊界））
- **2026-10-27 BL-0478 稽核登記**：BL-0483 新增（open；設定頁總表／進階診斷頁序仍為舊序，待另批對齊）
- **2026-10-27 vNext 視覺藍圖落盤批登記（不構成動工授權；`DEC-2026-10-27-07`、`docs/design/vnext_visual_blueprint.md`）**：BL-0484～BL-0491（8 列；皆 open：BL-0484～BL-0490 為藍圖七批（Shell／🌍／⚖️／💼／🔍／⚙️／One AI Brain）的追蹤列，依賴的 Decision Gate 見各列與規格第 8 節；BL-0491 為衝突登記 → 客戶 Decision Gate 包，是目前唯一的下一個安全動作）；BL-0479 列尾補記（＝藍圖批次 1）
- **2026-10-27 vNext Gate 裁示與隱私／SSOT 收斂批登記（不構成動工授權；`DEC-2026-10-27-08`～`-24`）**：BL-0492～BL-0508（17 列：open 5 列＝BL-0508 對應守衛、BL-0492 隱私 forward-only cleanup、BL-0493 historical exposure 登記、BL-0494 44 G-44 最小解凍 amendment、BL-0497 隱私守衛測試；待客戶裁示 12 列＝BL-0495 Risk Cap、BL-0496 減碼 trigger、BL-0498～BL-0507 逐列 Data Source Decision Gate）；BL-0479、BL-0481、BL-0484～BL-0491 列尾補記（狀態不變）；同 PR 稽核回修補 BL-0508 與 BL-0494 第 10 項待確認
- **2026-10-27 G-44 正式裁示與 44 最小解凍批登記（不構成動工授權；`DEC-2026-10-27-25`～`-38`）**：BL-0494 改 closed（本 PR）；BL-0509～BL-0511 新增（3 列：open 1 列＝BL-0509 EPS Data Source Probe；待客戶裁示 1 列＝BL-0510 EPS 成長假設模式；deferred 1 列＝BL-0511 排名模型）；BL-0481、BL-0485、BL-0488、BL-0501、BL-0508 列尾補記
- **2026-10-27 vNext 殼層實作批登記（不構成動工授權；BL-0484／BL-0479，PR #1084）**：BL-0479、BL-0484 列尾補記（實作完成待獨立稽核與合併，狀態不變）；BL-0512 新增（1 列：待確認＝殼層第二層「本頁區段」跳轉）
- **2026-10-27 BL-0484 合併後同步批登記（不構成動工授權）**：BL-0484、BL-0479 改 closed（#1084 已合併，main `2d1d5e07`）；BL-0512 維持待確認；BL-0513～BL-0515 新增（3 列 open：theme 檔頭 docstring 劃線、設定頁 page_link 28px、收合側欄連結寬 22px）
- **2026-10-27 結束對話同步批登記（不構成動工授權；`DEC-2026-10-27-40`）**：BL-0512 改 deferred（已裁示不另開批次）；BL-0509 標下一優先；BL-0495／BL-0496 加註維持待客戶裁示。
- **2026-10-27 BL-0509 第一次 probe 結果落盤批登記（不構成動工授權）**：BL-0509 狀態改「第一次 probe 完成，部分研究項待多日觀察」；BL-0501 列尾補記；新增 `docs/v2/68_bl0509_eps_probe_result.md`、`docs/evidence/probe_twse_eps/` 報告檔。
- **2026-10-27 A＋C 並行裁示落盤批登記（不構成動工授權；`DEC-2026-10-27-41`、`-42`）**：BL-0509 狀態改「多日 probe 排程已啟用（累積樣本中）」並補記；BL-0516～BL-0518 新增（3 列：open 2 列＝BL-0516 🌍 批 1 骨架、BL-0517 🌍 批 2 國際；待客戶裁示 1 列＝BL-0518 TAIEX 資料接入）；BL-0485 列尾補指向；快速索引〈待客戶裁示〉補 BL-0518。
- **2026-10-28 Cross-View Data Consistency Gate 落盤批登記（不構成動工授權；`DEC-2026-10-28-01`，`docs/v2/69_cross_view_consistency_spec.md`）**：BL-0519～BL-0524 新增（6 列：待客戶裁示 4 列＝BL-0519、BL-0521、BL-0522、BL-0524；open 2 列＝BL-0520、BL-0523）；不取代 BL-0509；快速索引〈待客戶裁示〉補 BL-0519、BL-0521、BL-0522、BL-0524。
- **2026-10-29 Presentation Contract Migration 第一階段落盤批登記（不構成動工授權；`DEC-2026-10-29-05`、`-06`，`docs/v2/71_presentation_contract_migration.md`）**：BL-0525～BL-0528 新增（4 列：open 2 列＝BL-0525 母列、BL-0527 Digest 缺口與守衛；待客戶裁示 2 列＝BL-0526、BL-0528）；BL-0293、BL-0397、BL-0486、BL-0487、BL-0490、BL-0517 列尾補記；快速索引〈待客戶裁示〉補 BL-0526、BL-0528。
- **2026-10-30 BL-0525 Batch C 落盤＋實作批登記（不構成動工授權；`DEC-2026-10-30-01`）**：BL-0525 列尾補 Batch C 狀態；BL-0517 列尾補三序列 layout approved／資料現況；其餘 BL 狀態不變。
- **2026-10-30 BL-0525 Batch D 客戶裁示落盤批登記（`DEC-2026-10-30-02`）**：BL-0525 列尾補 Batch D 裁示狀態與子項 BL-0525-D3（D-3 最小 Formula Gate，列內追蹤、不另開 BL）；其餘 BL 狀態不變。BACKLOG §3 列數統計未重算（未新增 BL 列）。
- **2026-10-30 BL-0525-D3／BL-0525-OAUTH Gate 落盤批登記（不構成動工授權；`DEC-2026-10-30-02`）**：BL-0525 列尾補兩子項狀態（D-3 Formula Gate 落盤 `docs/v2/74_assets_d3_formula_gate.md`；D-8 OAuth 回原頁 Gate 登記於 `docs/v2/73` 第 15 節），兩者待客戶裁示；未新增 BL 列，BACKLOG §3 列數統計未重算。
- **2026-10-30 BL-0525-D3／BL-0525-OAUTH 兩 Gate 文件第二輪回修批登記（不構成動工授權；`DEC-2026-10-30-02`）**：BL-0525 列尾補兩子項狀態（`docs/v2/74` ~~草案 v6~~ 草案 v7（`31c421a5`；有意識的更正，不是漏刪）：阻擋項加 F-18、F-19；`docs/v2/73` 第 15 節 v3：方案含 G，推薦仍是 F）與一則頁名字樣小登記；未新增 BL 列，BACKLOG §3 列數統計未重算；由文件組單組寫成，未經第二組驗證。
- **2026-10-31 D-3 阻擋項修正第三輪登記（依獨立稽核 B-NEW-1／should-fix 1／should-fix 3；`DEC-2026-10-30-04`）**：BL-0411 列尾補第三輪狀態（仍待獨立稽核）；未新增 BL 列，BACKLOG §3 列數統計未重算；實作組單組寫成，未經第二組驗證。
- **2026-10-31 D-3 阻擋項修正第二輪登記（依獨立稽核 B1／B2／S1～S6；`DEC-2026-10-30-04`）**：BL-0411 列尾補第二輪狀態（仍待獨立稽核）；BL-0525 列尾補 F-17 已隨第二輪修、S5 登記豁免；未新增 BL 列，BACKLOG §3 列數統計未重算；實作組單組寫成，未經第二組驗證。
- **2026-10-31 BL-0525-D3 P3 頁級狀態實作登記（`DEC-2026-10-30-04`）**：BL-0525 列尾補 P3 已實作待獨立稽核；其餘 BL 狀態不變；未新增 BL 列。BACKLOG §3 列數統計未重算（未新增 BL 列）。
- **2026-10-31 BL-0525-D3 V7 裁示落盤＋A 線框登記（不構成動工授權；`DEC-2026-10-31-01`）**：BL-0525 列尾補 V7 採 A、H6 維持只評估一部分級、F-5 字樣核准、A 線框待審批（`docs/v2/76`）；其餘 BL 狀態不變；未新增 BL 列。BACKLOG §3 列數統計未重算（未新增 BL 列）。
- **2026-10-31 BL-0525-D3 V7 Layout A 實作登記（`DEC-2026-10-31-02`；不新增 BL 列）**：客戶核准 `docs/v2/76` 線框並授權實作 A；A 已實作（`ui_v2/asset/page.py`，presentation de-duplication），**待獨立稽核**；ALO-0 說明句合併頁改「此配置判讀」；實作後實測見 `docs/v2/76` 第 11 節（兩個極端組合 390px V7 仍紅，客戶已接受）。BL-0525 其餘狀態不變；BACKLOG §3 列數統計未重算（未新增 BL 列）。
- **2026-10-31 D-3 裁示落盤獨立稽核回修批登記（對 `c6804cfd`；只動文件）**：BL-0411 列把原句「修法屬產品語意（Stop Gate）；G1 判定時納入」就地劃線、刪去重複的劃線副本；BL-0525 列把「先修 (i)～(v)、再實作 P3」改標總管讀法（客戶裁示的是五項必修與 BL-0411 修好才允許 P3 production），F-5 處置標總管處置，兩處語意不清的「登記不構成動工授權之外的授權」改寫；未新增 BL 列，BACKLOG §3 列數統計未重算；文件組單組寫成，未經第二組驗證。
- **2026-11-01 找基金正式搜尋入口與 Fund Identity 裁示落盤批登記（不構成動工授權；`DEC-2026-11-01-01`）**：BL-0530 新增（待客戶裁示）；BL-0397、BL-0521、BL-0525、BL-0488、BL-0411 列尾補記（狀態不變）；BL-0511 不動（維持 deferred）。文件組單組，未經第二組驗證。
- **2026-11-01 Batch E Gate 全裁落盤批登記（不構成動工授權；`DEC-2026-11-01-02`）**：BL-0530 由〈待客戶裁示〉移出，改 research-only（open；ISIN → MoneyDJ canonical fund identity 來源調查，不導入）；BL-0525 列尾補 Batch E 狀態（Gate 全裁、wireframe 核准、下一實作批＝MoneyDJ code 主入口）；BL-0397、BL-0521 列尾補「已裁示」；未新增 BL 列，BACKLOG §3 列數統計未重算。文件組單組，未經第二組驗證。
- **2026-11-02 Final UI／Decision System Contract Freeze 落盤批登記（不構成動工授權；`DEC-2026-11-02-01`，`docs/v2/79_final_ui_contract_freeze.md`）**：BL-0531 新增（待客戶裁示；子項 BL-0531-UI1～~~UI14~~ → UI15（UI15 為 2026-11-02 增量，見下一行；狀態更新，不是漏刪）與 cleanup plan 列內追蹤）；BL-0532 新增（open，Missing 語彙機械式統一為 `◇ 資料未備`，需等客戶開實作批）；BL-0525、BL-0527、BL-0495、BL-0496、BL-0490、BL-0529、BL-0528 列尾補指標（狀態不變）。
- **2026-11-02 UI-15 增量登記（#1119，docs-only；不構成動工授權；`docs/v2/79` §17、`DEC-2026-11-02-02`）**：BL-0531 列內追加子項 BL-0531-UI15（配息行事曆與 LINE Information／Event Notification；待客戶裁示；不阻擋 Batch E；不新開 BL）；完整待裁集合為 UI-1～UI-15（UI-11 已裁示不重問）；BL-0531 列尾補 New UI 邊界指標（`DEC-2026-11-02-02`：New UI 唯一正式產品線、Old UI 只作 read-only logic reference）。
- **2026-11-02 New UI2 架構方向登記（#1119，docs-only；不構成動工授權；`DEC-2026-11-02-03`）**：BL-0533 新增（open；New UI2 Architecture Proposal＋Reuse Matrix＋五頁 wireframe＋migration／cutover；Decision Gate；dependency #1119 合併）；BL-0531、BL-0525、BL-0532 列尾補 New UI2 實作落點指標（狀態不變）。
- **2026-11-02 New UI2 Architecture Proposal 落盤（docs-only；不構成動工授權；`DEC-2026-11-02-03`、`DEC-2026-11-02-04`）**：BL-0533 狀態改為 proposal 已落盤（`docs/v2/80`），列內追加子項 BL-0533-NG1～NG5（皆待客戶裁示）；原 NG-6 轉為內部決定。
- **2026-11-02 New UI2 NG／Final UI Contract 一次裁示落盤批登記（docs-only；不構成動工授權；`DEC-2026-11-02-05`～`-08`）**：BL-0533 改 closed（NG-1～NG-5 全採 A，architecture／Reuse Matrix／migration boundary 凍結）；BL-0531 子項 UI1～UI15 改已裁示（UI-11 原已裁示），母列續追蹤回寫（67；78 加註同批另組）；BL-0532 列尾補 NG-2 附題指標（ui_v2 也套用，狀態不變）；BL-0534（open，44 `pay_date` 語意 amendment）、BL-0535（open，cutover navigation／entrypoint 暴露守衛）、BL-0536（blocked，`ui_v3` presentation implementation）新增。
- **2026-11-03 🌍 wireframe 裁示登記（docs-only；不構成動工授權；`DEC-2026-11-03-01`）**：BL-0536-G1 改已裁示（Q1 A、Q2-a／b／c A、Q3 A、Q4 A、Q5 B）；BL-0536 列尾新增實作前置子項 H1～H5（列內追蹤，不另開 BL；H4 freshness threshold 與既有 BL-0369 同一缺口）；BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 Prior-Ruling Audit 缺漏補齊登記（docs-only；`DEC-2026-11-03-02`）**：BL-0525 過期尾段加刪除線與指標（G4）；BL-0535 的「`ui_v3` 尚不存在」更新（G5）；BL-0536 列加頁序、每批獨立稽核、Q2 Gate 規則（G2／G3／G10）；新增 BL-0537（Old UI／`ui_v2` 凍結清單機械守衛，待客戶裁示、未建置）；§3 列數統計若有計數守衛以測試為準。
- **2026-11-03 BL-0536-H1 實作登記（PR 待開；~~獨立稽核待做~~ → 獨立稽核 1 組無 blocker，總管轉述）**：BL-0536-H1 改 implemented（`services/v2_domain/normalization.py` 新寫，非 PORT；依 Q2-a／b／c A 與 UI-13）；Gate 放行與本批條件見 `DEC-2026-11-03-03`；`tests/test_v2_domain_port.py` 分層白名單加 `dataclasses`；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 歸一化 ABC 裁示＋永久規則落盤（docs-only governance；`DEC-2026-11-03-04`、`-05`）**：BL-0536-H1 待客戶確認 (A)(B)(C) 改已裁示（A2／B2／C2）；BL-0536 列內新增子項 H1b（列內追蹤，不另開 BL）；H2／H3 補客戶要求、改依序 H1b → H2 → H3 → Preview rendering；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 BL-0536-H1b 實作登記（PR 待開；公式等級獨立稽核待做）**：BL-0536 列內子項 H1b 改 implemented（`services/v2_domain/normalization.py` 依 `DEC-2026-11-03-04` A2／B2／C2 修改；`tests/test_v2_domain_normalization.py` 更新）；`docs/v2/81` 新增第 9.1 節；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 BL-0536-H2 實作登記（PR 待開，疊在 H1b 之上；公式等級獨立稽核待做）**：BL-0536 列內子項 H2 改 implemented（新增 `services/v2_domain/market_summary.py`：首屏期間漲跌＝歸一化 `period_change` 投影、沒畫線為 None＋原因、首屏無日期、新鮮度恆為 `threshold_pending`；圖卡用逐序列經過天數；`tests/test_v2_domain_market_summary.py` 新增、`tests/test_v2_domain_port.py` 母體加本模組）；ui_v2 未動；adapter 移交 H3；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 BL-0536-H2 稽核後補登（docs-only）**：獨立稽核 1 組無 blocker（總管轉述）；H2 列內補三項 adapter 要求（負經過天數呈現不適用、`series_freshness` 傳台北時區、取數失敗與缺資料分開）與一則上游低優先登記（病態量級 → inf）；`docs/v2/81` 第 4 節重要依據列加 H2 指標；未新增 BL 列，BACKLOG §3 列數統計未重算。
- **2026-11-03 BL-0536-H3 實作登記（PR 待開，疊在 H2 分支 `c01f22f3` 之上；獨立稽核待做）**：BL-0536 列內子項 H3 改 implemented（新增 `ui_v3/viewmodels/chart_disclosure.py`（`NormalizationDisclosure`／`SeriesIssue`）、`ChartCard` 加 `normalized`／`disclosure`、新增 `ui_v3/adapters/market_chart.py::build_comparison_card`；揭露基準日、基準值 100、資料頻率、缺值／缺序列處理，代碼不含畫面字樣；`tests/ui_v3` 新增兩檔、preview 守衛執行期白名單開 `services.v2_domain` 子樹）；未動 Old UI、`ui_v2`、規則表、frozen 文件；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 BL-0536-H3 稽核後修正登記**：獨立稽核 1 組（總管轉述）blocker B1（取數失敗序列不得放 `MissingItem`）已修；N1～N4 補 rendering 批要求（`insufficient` 資料不足字樣、`withheld` 真正原因在 `disclosure.status`、`frequency` 由取數 adapter 保證日頻）與測試；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 BL-0536 🌍 正式字樣落盤＋工程資訊外漏守衛＋MKT 對照登記（`DEC-2026-11-03-07`；PR 待開）**：客戶九項正式字樣進 `shared/ui_semantics/rules.py::APPROVED_WORDING`（畫面不再標 pending；`chart_empty` PENDING 列移除）；一般 UI 移除環境變數名與內部原因代碼，新增靜態＋渲染外漏守衛；依據卡 MKT-1～3 對照 44／72（標籤、MKT-2 兩鍵、位數）；~~首屏拆兩枚 chip 超過預算，登記為 Decision Gate、未實作（BL-0536 列內）；~~ → 客戶 2026-11-03 已裁示採 C 並實作、同批用字統一（`DEC-2026-11-03-09`；狀態更新，不是漏刪；決策者：客戶；#1132 scope 已涵蓋）；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-02 BL-0536 批 2a（PORT）＋批 2b（呈現規則資料表／design token）登記（同一 PR、PR 待開；不構成動工授權；`DEC-2026-11-02-05` NG-2 A、`DEC-2026-11-02-09`）**：BL-0536 列尾補批 2a／2b 狀態與後續子項 BL-0536-F1～F6、BL-0536-W1～W5（列內追蹤，不另開 BL，`PROJECT_RULES.md` 13.4 第 3 條）；未新增 BL 列，BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-03 Canonical Rule Convergence 登記（docs-only；`DEC-2026-11-03-08`）**：BL-0536 列瘦身為單一狀態（舊整列逐字移 `docs/evidence/history/`）；新增 BL-0538（Latest-Rule-Only 讀法確認，待客戶裁示）、BL-0539（🌍 首屏拆 chip，待客戶裁示）、BL-0540（Missing 字樣／資料健康度承接／🤖 輸出對映，待客戶裁示）、BL-0541（第二階段文件收斂，open）；本批不碰任何 production code。
- **2026-11-03 Shell 定字與降級首屏收尾登記（`DEC-2026-11-03-11`；不構成動工授權）**：客戶對 #1134 的驗收裁示落地於 BL-0536 列（Shell 字樣單一 SSOT、Status Bar 純文字、降級第一屏 ≤5、仍待驗證六項逐條登記）；逐字 `docs/evidence/decisions/2026-11-03_shell_wording_and_degraded_first_screen_ruling.md`；方案比較與前後計數 `docs/v2/81` 第 10.2 節。不開新 refresh pipeline；💼 線框為其後一批、尚未開始。
- **2026-11-03 #1135 文字設計修訂整合登記（docs-only；`DEC-2026-11-03-12`；不構成動工授權）**：客戶指示專案 AI 處理 ChatGPT 提交的 New UI2 文字設計修訂（#1135），經獨立稽核後只併入 `docs/v2/80` 第 7.4、16.1 節；其餘捨棄；💼 我的資產詳細設計改由 ChatGPT 先設計文字、資料串接契約與正式 GitHub 規格，專案 AI 現不開始 💼 程式開發。逐字 `docs/evidence/decisions/2026-11-03_pr1135_text_revision_integration_ruling.md`。
- **2026-11-04 #1138 整合與 82 稽核回修登記（docs-only；不構成動工授權；非客戶裁示）**：ChatGPT 的 💼 施工前草案 `docs/v2/82` 併入並依三組獨立稽核回修（第 8 節核實結果、第 6.1 節新問題）；新增 BL-0542（Gate 候選 G-1～G-5）；BL-0536 列補一句、狀態不變；BACKLOG §3 列數統計未重算；執行組單組寫成，未經第二組驗證。
- **2026-11-04 #1140 整合登記（docs-only；不構成動工授權）**：`DEC-2026-11-04-01`（客戶核准 💼 主要圖表在前、四項摘要在後、資料不足明確顯示 Missing，僅 UI 順序方向）與 82 §0.1 併入；BL-0542 G-4 補一句「順序已核准、口徑／公式仍待 Gate」；不授權 G-1～G-5、💼 程式或 Claude Code 實作；BACKLOG §3 列數統計未重算。
- **2026-11-04 #1144 整合登記（docs-only；不構成動工授權）**：`DEC-2026-11-04-02`（客戶核准 💼 U1～U5 全部 UI 設計與缺 FX 方案 A；僅 UI 設計；逐字見 `docs/evidence/decisions/2026-11-04_assets_u1_u5_fx_ruling.md`）；BL-0542 G-1～G-5 仍待分別裁示，不授權 💼 程式。
- **2026-11-04 G-1 方向登記（docs-only；不構成動工授權）**：`DEC-2026-11-04-03`（客戶方向裁示，要點轉述、非逐字）；BL-0542 加 G-1 狀態與待決題；僅授權 G1-① Golden Baseline，G1-②／③、G-2～G-5 與 💼 程式未授權。
- **2026-11-05 G1-② 進度登記（docs；不構成動工授權；非新客戶裁示）**：G1-① 已合併（#1146，`1f260bfc`）；G1-② 最小共用核心 PORT 見 BL-0542 G1 進度（PR 以 GitHub 為準）；G1-③、G-2～G-5 未授權；BACKLOG §3 列數統計未重算。
- **2026-11-05 G1-③ 進度登記（docs；不構成動工授權；非新客戶裁示）**：G1-② 已合併（#1147，`d4eabb35`）；G1-③ Complete Evidence 產生器（純 Domain、無 UI／無 production 呼叫端）見 BL-0542 G1 進度（PR 以 GitHub 為準）；open_gate 代碼僅登記為待決題；G-2～G-5 未授權；BACKLOG §3 列數統計未重算。
- **2026-11-05 G-2 進度登記（docs；不構成動工授權；非新客戶裁示）**：G1-③ 已合併（#1148，`81827057`）；G-2 最小 Preview 資料載入轉接層（無 UI 接線、守衛零變更）見 BL-0542 G-2 進度（PR 以 GitHub 為準）；G-3～G-5 未授權；BACKLOG §3 列數統計未重算。
- **2026-11-05 G-3 前置稽核登記（docs；不構成動工授權；非新客戶裁示）**：新增唯讀稽核 `docs/evidence/g3_market_basis_data_contract_audit_2026_11_05.md`（資料契約與 NAV／FX 歸屬）；BL-0542 列補一句進度；G-3～G-5 仍未授權；BACKLOG §3 列數統計未重算。
- **2026-10-30 D-3 阻擋項修正批登記（`DEC-2026-10-30-04`；代碼 commit `dc670882`）**：BL-0411 改「fixed（待獨立稽核）」；BL-0525 列尾補 BL-0525-D3 子項狀態（F-13、F-14、F-19、F-2、F-18 已修待獨立稽核；P3 未實作；F-17 未修）；未新增 BL 列，BACKLOG §3 列數統計未重算；實作組單組寫成，未經第二組驗證。
- **2026-10-30 BL-0525-D3／BL-0525-OAUTH 客戶裁示落盤批登記（`DEC-2026-10-30-04`、`-05`）**：BL-0525 列尾補兩子項裁示（BL-0525-D3 已裁採 P3／β，下一步實作，列內追蹤必修 F-13、F-2、F-14、F-19 與 BL-0411；BL-0525-OAUTH 以 F closed；G deferred）；BL-0411 列改為客戶已裁的 P3 production 前必修（需客戶裁示欄改「否」）；未新增 BL 列，BACKLOG §3 列數統計未重算；由文件組單組寫成，未經第二組驗證。
<!-- SEGMENT-END id=QI-1 -->

## 區塊 INV-1｜§3 初版計數與六次現況重算快照｜原 L51–L74

<!-- SEGMENT-BEGIN id=INV-1 source=docs/BACKLOG.md@856640fa lines=51-74 sha256=afdd7fa5fabf835830e9bbf308446dce9686d70da0317220f9424526cfcc6687 bytes=4323 -->
**計數（量測於 `d5d391b`、2026-10-16）**：

- 來源條目總數：**439**
- 列入本檔（各自開 BL 號）：**339**
- 合併到其他列（不另開號）：**32**
- 判為關閉：**65**
- 非待辦（確認句／行為說明）：**3**
- 列入者之中狀態為「待確認」：**36**

列入者依狀態：open 244、blocked 4、待客戶裁示 21、待確認 36、deferred 34。

列入者依類別：bug 85、data gap 16、tech debt 86、research 16、UX debt 58、deferred improvement 6、source-quality 3、architecture debt 10、future validation 3、governance 56。

**現況重算（量測於 2026-10-18，本批 commit 前；上面兩行是初版，一字未改）**：§4 各表共 **376** 列（BL-0001～BL-0376）。依狀態：open 263、deferred 44、待確認 36、待客戶裁示 19、closed 10、blocked 4（狀態格以劃線後的現行值計，例 `closed（~~待客戶裁示~~）` 算 closed）。依類別：tech debt 87、bug 86、UX debt 72、governance 62、research 24、data gap 18、architecture debt 13、deferred improvement 7、future validation 4、source-quality 3。⚠️ 以「行首為 `| BL-` 的表格列」機械計數，本組單組量測，未經第二組驗證；數字會漂移，引用前請現場重算。

**現況重算（量測於 2026-10-19，`DEC-2026-10-19-01` 批改完後、commit 前；上面各行一字未改）**：§4 各表共 **378** 列（BL-0001～BL-0378）。依狀態：open 264、deferred 44、待確認 36、待客戶裁示 18、closed 12、blocked 4（計法同上一行）。依類別：tech debt 87、bug 86、UX debt 73、governance 63、research 24、data gap 18、architecture debt 13、deferred improvement 7、future validation 4、source-quality 3。⚠️ 同上一行的機械計數法，本組單組量測，未經第二組驗證；會漂移，引用前請現場重算。

**現況重算（量測於 2026-10-19，`DEC-2026-10-19-02` 清整批改完後、commit 前；上面各行一字未改）**：§4 各表共 **380** 列（BL-0001～BL-0380）。依狀態：open 261、closed 33、待確認 32、deferred 32、待客戶裁示 18、blocked 4（計法同上；本批依證據關閉 8 列、標示知悉項 11 列（含 BL-0063、BL-0236）、併入他列 2 列，皆記為 closed，原文保留）。依類別：tech debt 87、bug 86、UX debt 74、governance 63、research 24、data gap 19、architecture debt 13、deferred improvement 7、future validation 4、source-quality 3。⚠️ 同上的機械計數法，本組單組量測，未經第二組驗證；會漂移，引用前請現場重算。

**現況重算（量測於 2026-10-19，BL-0381 登記後、commit 前；上面各行一字未改）**：§4 各表共 **381** 列（BL-0001～BL-0381）。依狀態：open 261、closed 33、deferred 33、待確認 32、待客戶裁示 18、blocked 4（計法同上）。依類別：tech debt 87、bug 86、UX debt 74、governance 64、research 24、data gap 19、architecture debt 13、deferred improvement 7、future validation 4、source-quality 3。⚠️ 同上的機械計數法，本組單組量測，未經第二組驗證；會漂移，引用前請現場重算。

**現況重算（量測於 2026-10-20，BL-0382 登記後、commit 前；上面各行一字未改）**：§4 各表共 **382** 列（BL-0001～BL-0382）。依狀態：open 261、deferred 34、closed 33、待確認 32、待客戶裁示 18、blocked 4（計法同上）。依類別：tech debt 87、bug 86、UX debt 75、governance 64、research 24、data gap 19、architecture debt 13、deferred improvement 7、future validation 4、source-quality 3。⚠️ 同上的機械計數法，本組單組量測，未經第二組驗證；會漂移，引用前請現場重算。

**現況重算（量測於 2026-10-20，BL-0383 登記後、commit 前；上面各行一字未改）**：§4 各表共 **383** 列（BL-0001～BL-0383）。依狀態：open 262、deferred 34、closed 33、待確認 32、待客戶裁示 18、blocked 4（計法同上）。依類別：tech debt 87、bug 87、UX debt 75、governance 64、research 24、data gap 19、architecture debt 13、deferred improvement 7、future validation 4、source-quality 3。⚠️ 同上的機械計數法，本組單組量測，未經第二組驗證；會漂移，引用前請現場重算。
<!-- SEGMENT-END id=INV-1 -->
