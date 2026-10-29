# MoneyDJ NAV 等價性 probe（`DEC-2026-10-29-02`，方案 A）

只讀 evidence gathering：`TLZF9`／`TLZF9-AL001`／`TLZF9-24A7`／`ACDD01`／`ACDD01-EQTAL005` 在 MoneyDJ 的實際 NAV 是否一致。**尚未實跑**；本目錄暫無報告。

- 腳本：`scripts/probe_moneydj_nav_equivalence.py`；workflow：`.github/workflows/moneydj_nav_equivalence_probe.yml`；測試：`tests/test_probe_moneydj_nav_equivalence.py`、`tests/test_moneydj_nav_equivalence_probe_workflow.py`。方法與比較規則見 `docs/v2/70_dg2_canonical_identity_proposal.md` 第 16 節。
- **觸發**（workflow 須先在 main）：`git fetch origin main && git push origin origin/main:refs/heads/probe/moneydj-nav-trigger`（再跑一次推新 SHA 或空 commit），或 `workflow_dispatch`。無排程。執行的永遠是 main 上的腳本。
- **輸出**：報告 `results/<時間>_run<id>/report.json.gz` 只推到 `probe/moneydj-nav-results`（不推 main、不 force），並上傳 Actions artifact `moneydj-nav-report`。保存到 main 的做法比照 `docs/evidence/probe_moneydj_basic/README.md`（`git show` 取出、`gzip -9 -n`、記雜湊）。
- **怎麼讀**：`summary.<TLZF9|ACDD01>.verdict` ∈ `consistent`／`not_comparable`／`conflict`／`blocked`（`detail` 寫原因）；`observations` 逐網址（`transport`＝`direct` 或 `nas_proxy`、`kind`、HTTP、解析狀態、NAV、NAV 日、頁面明示幣別、`raw.sha256`／片段）；`comparisons` 逐對比較（`conflict` 附 `candidate_causes`，不下「不同基金」結論）；`network_blocked` 記各路徑實際（已遮蔽）錯誤，MoneyDJ 連不上時停止、不繞路。缺值一律 `null`，不是 0。
- **安全**：只發 GET；不寫 Sheet／`nav_history`／cache；不改 resolver、NAV precedence、畫面、flag；`PROXY_URL` 只在 Run 步驟 env、不入報告；`GITHUB_TOKEN` 只在推送步驟。`consistent` 只是 evidence，不是升格 production source 的授權。
