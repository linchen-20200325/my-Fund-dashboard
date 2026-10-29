# MoneyDJ NAV 等價性 probe（`DEC-2026-10-29-02`，方案 A）

只讀 evidence gathering：`TLZF9`／`TLZF9-AL001`／`TLZF9-24A7`／`ACDD01`／`ACDD01-EQTAL005` 在 MoneyDJ 的實際 NAV 是否一致。首次實跑結果見 `docs/v2/70` 16.1；2026-10-29 起改為排程累積多日 evidence（`DEC-2026-10-29-03`）。

- 腳本：`scripts/probe_moneydj_nav_equivalence.py`；workflow：`.github/workflows/moneydj_nav_equivalence_probe.yml`；測試：`tests/test_probe_moneydj_nav_equivalence.py`、`tests/test_moneydj_nav_equivalence_probe_workflow.py`。方法與比較規則見 `docs/v2/70_dg2_canonical_identity_proposal.md` 第 16 節。
- **觸發**（workflow 須先在 main）：`git fetch origin main && git push origin origin/main:refs/heads/probe/moneydj-nav-trigger`（再跑一次推新 SHA 或空 commit），或 `workflow_dispatch`。執行的永遠是 main 上的腳本。
- **輸出**：報告 `results/<時間>_run<id>/report.json.gz` 只推到 `probe/moneydj-nav-results`（不推 main、不 force），並上傳 Actions artifact `moneydj-nav-report`。保存到 main 的做法比照 `docs/evidence/probe_moneydj_basic/README.md`（`git show` 取出、`gzip -9 -n`、記雜湊）。
- **怎麼讀**：`summary.<TLZF9|ACDD01>.verdict` ∈ `consistent`／`not_comparable`／`conflict`／`blocked`（`detail` 寫原因）；`observations` 逐網址（`transport`＝`direct` 或 `nas_proxy`、`kind`、HTTP、解析狀態、NAV、NAV 日、頁面明示幣別、`raw.sha256`／片段）；`comparisons` 逐對比較（`conflict` 附 `candidate_causes`，不下「不同基金」結論）；`network_blocked` 記各路徑實際（已遮蔽）錯誤，MoneyDJ 連不上時停止、不繞路。缺值一律 `null`，不是 0。
- **安全**：只發 GET；不寫 Sheet／`nav_history`／cache；不改 resolver、NAV precedence、畫面、flag；`PROXY_URL` 只在 Run 步驟 env、不入報告；`GITHUB_TOKEN` 只在推送步驟。`consistent` 只是 evidence，不是升格 production source 的授權。
- **幣別／名稱來源**：NAV 頁本身不被當作幣別來源。`currency`／`fund_name` 取自**同一輸入**的基本資料頁（`basic_info`），事後回填到該輸入同路徑的 NAV 觀測；欄位 `currency_source`／`fund_name_source` 記回填來源網址，頁面沒明示則為 `null`。
- **覆蓋判定**：帶後綴的輸入，需至少一組涉及 `platform_*` 頁的一致比較才算被覆蓋（否則 prod 頁可能只回 base 基金頁，一致是 tautology）→ `not_comparable`，detail 寫 "only prod pages compared"。`summary` 另列 `fund_name_mismatch_pairs`（自報名稱不同的配對，僅旗標、不是「不同基金」結論）與 `same_input_conflicts`（同一輸入跨路徑／跨 host 的 NAV 衝突）。
- **浮點比較容差**：`math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)`（CLAUDE.md §4.3）。非 200 回應留遮蔽後的小段純文字（`error_snippet`，300 字內）。

## 排程與多日分析（`DEC-2026-10-29-03`，2026-10-29 起）

- **排程**：workflow 新增 `schedule: 17 13 * * 1-5`（台北週一至週五 21:17），不必有人按按鈕；仍是 `ref: main`、只發 GET、只推 `probe/moneydj-nav-results`。目標累積 3～5 個**不同交易日**後由客戶裁示是否停用（停用＝刪除 `schedule:` 區塊並 PR）。累積期間不開 PR、不改 HANDOFF／BACKLOG／DECISIONS；僅出現 NAV／基金名稱 conflict、parser failure、日期異常、來源失效、identity 語意衝突時才回報。
- **報告 v1.1 的讀法**：`summary.TLZF9.verdict` 仍是 strict 規則（幣別需雙方明示）；並列的 `summary.TLZF9.observational.verdict` ∈ `strong_observational_evidence`／`conflict`／`incomplete`，`currency_evidence` 把「base 頁自報幣別」與「平台頁是否明示幣別」分兩欄記，**不推定平台頁幣別**，永不輸出 strictly comparable。`summary.ACDD01.verdict` ∈ `baseline_verified`／`baseline_failed`／`blocked`（基本頁的名稱＋幣別＋NAV）；`product_mapping`（`EQTAL005 → ACDD01`，來源＝客戶確認，`mapping_verified_against_moneydj` 預設 `null`）不是 NAV 等價題，`ACDD01-EQTAL005` 頁面只當原始觀測、不進 verdict。
- **分析**：`git fetch origin probe/moneydj-nav-results && git worktree add /tmp/mdj-results origin/probe/moneydj-nav-results`，再跑 `python3 scripts/analyze_moneydj_nav_series.py /tmp/mdj-results`（`--json` 輸出結構化結果）。數的是**不同 NAV 日**不是 run 次數；`classification` ∈ `insufficient_days`（<3 個一致日）／`strong_observational_evidence_same_series`（≥3 個不同 NAV 日三輸入全一致且無 conflict）／`conflict_found`／`blocked`。
