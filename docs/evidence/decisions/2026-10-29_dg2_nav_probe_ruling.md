# 客戶 2026-10-29 DG-2 下一步裁示：MoneyDJ NAV probe 方案 A、dashed key cache 不核准、Shadow flag 維持 OFF（逐字）

- **來源**：客戶 2026-10-29 對話中的 DG-2 下一步裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-29-02`（客戶裁示）。落地：`scripts/probe_moneydj_nav_equivalence.py`、`.github/workflows/moneydj_nav_equivalence_probe.yml`、`docs/evidence/probe_moneydj_nav/README.md`、`docs/v2/70_dg2_canonical_identity_proposal.md` 第 16 節、`docs/BACKLOG.md` BL-0521 子項 (a)。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行）。
- **存檔日期**：2026-10-29
- **圍欄內文 sha256**：`a88d4427ec9db5c2f890f0a3b721cdca59bda5d5689e3363fbbf04a7da6f3a6c`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
DG-2 下一步裁示如下。

1. MoneyDJ NAV 網路查證

採 方案 A。

建立一個獨立、唯讀的 MoneyDJ NAV probe workflow，沿用 BL-0509 已驗證的 probe 模式。

目標只做 evidence gathering，不接 production。

驗證至少包含：

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"
- "ACDD01"
- "ACDD01-EQTAL005"

對每一筆記錄：

- original input
- resolved base fund code
- MoneyDJ URL / page type
- fund name
- NAV
- NAV date
- currency（若來源明確提供）
- source timestamp
- HTTP / parse status
- raw evidence reference
- parser version / commit SHA

比較規則：

同 base fund、同 share class（若可確認）、同 currency、同 NAV date 才可比較。

若：

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"

在相同條件下 NAV 一致：

記為「支持通路 suffix 不改變 fund NAV」的 evidence。

若不一致：

不得直接判定為不同基金。

先分類可能原因：

- as-of 不同
- publication lag
- page type
- currency
- share class
- platform stale cache
- parser difference
- source inconsistency

然後記為 source conflict / UNVERIFIED。

"ACDD01" 與 "ACDD01-EQTAL005" 同樣處理。

Probe 安全邊界

workflow：

- 只讀 MoneyDJ
- 不寫 production Sheet
- 不寫 "nav_history"
- 不寫正式 cache
- 不改 canonical resolver
- 不改 NAV precedence
- 不改正式畫面
- 不啟用 DG2 Shadow flag

結果只允許寫入：

- probe evidence / report
- 專用 probe branch 或既有 probe evidence 路徑

不得因 probe 成功就自動把 MoneyDJ 某 URL 升格為新的 production source。

若 GitHub Actions 同樣被 MoneyDJ 阻擋，記錄實際錯誤後停止，不再建立新的網路繞路方案。

---

2. dashed key cache 備援

目前不核准新增。

不要新增：

"cache/nav/{完整帶後綴代碼}.json"

作為新的 production fallback。

原因：

目前還沒有證據證明：

- 帶 suffix 的 NAV series 必須獨立保存
- 或完整 dashed key 應成為正式 NAV source

而且這會新增資料來源／fallback semantics。

先完成 MoneyDJ NAV probe。

若未來證據顯示：

- 同 base fund 不同通路其實存在有效且不同的 NAV series，
- 或 production 確實需要完整 dashed key cache，

再另走 Data Source / NAV semantics Decision Gate。

目前維持現況。

---

3. DG2 Shadow flag

目前不開啟。

順序固定為：

1. 完成 MoneyDJ NAV probe
2. 取得可追溯 evidence
3. 評估 resolver identity 與 NAV equivalence 是否成立
4. 再提出 Shadow flag 執行方案

下一次要提出 Shadow flag 時，必須一次附：

- 執行環境
- 觸發頻率
- 讀取哪些 production input
- log 欄位
- 是否含 policy id / 個資
- 遮罩規則
- retention
- 差異分類
- success / fail threshold
- rollback
- 關閉方式
- 是否完全不影響正式 return value

在我核准前 flag 維持 OFF。

---

4. 真實 Sheet URL 限制

"#fragment" / "area=TW&a=" 真實 Sheet 是否存在，目前不需要額外請客戶人工檢查。

若現有 Google Sheet reader 能在唯讀情況下安全盤點：

只做結構性檢查：

- 是否存在含 "#"
- 是否存在 "area="
- 是否存在完整 URL

不要把原值全文寫進 log。

若需要新的憑證、權限或會碰敏感資料，跳過並標 "UNVERIFIED"。

不得因此阻塞 NAV probe。

---

5. BL-0509

BL-0509 照原排程平行累積，不受 DG-2 影響。

不要把 MoneyDJ probe 與 BL-0509 合成同一資料來源契約；可以復用 workflow pattern，但 evidence 與 Decision Gate 各自獨立。

---

6. 執行與回報

維持 Silent Autonomous Cruise / Anti-Bloat。

本輪最多處理：

1. MoneyDJ NAV probe workflow
2. probe evidence / tests
3. 必要 docs / handoff 同步

不需要額外獨立研究組；若 workflow 屬純唯讀 probe，可依 Minimum Sufficient Effort 做 targeted review。

完成後只回報：

- GitHub main / PR / CI
- GitHub Actions 是否能連 MoneyDJ
- 五個輸入的 evidence matrix
- 哪些已確認一致
- 哪些仍 UNVERIFIED / conflict
- 是否已有足夠證據進入 Shadow flag Decision Gate

Model：

- workflow / probe 實作：Sonnet 5.5
- Effort：Medium
- 若 probe 結果出現 identity / NAV semantics 衝突，再升 Opus 5.5 + High

現在依上述裁示靜默執行。
```
