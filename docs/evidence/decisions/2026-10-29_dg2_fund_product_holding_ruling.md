# 客戶 2026-10-29 DG-2 最終整合（二）裁示：基金／保險商品通路／持倉三層身份、多日 MoneyDJ NAV probe（逐字）

- **來源**：客戶 2026-10-29 對話中的 DG-2 最終整合裁示（二），經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-29-03`（客戶裁示；承接並收斂 `DEC-2026-10-29-01`、`-02`）。落地：`docs/v2/70_dg2_canonical_identity_proposal.md` 第 17 節、`.github/workflows/moneydj_nav_equivalence_probe.yml`（排程）、`scripts/probe_moneydj_nav_equivalence.py`、`scripts/analyze_moneydj_nav_series.py`、`docs/evidence/probe_moneydj_nav/README.md`、`docs/BACKLOG.md` BL-0521。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行）。
- **存檔日期**：2026-10-29
- **圍欄內文 sha256**：`2036965762f658585f3ec9f6c10f65261b2d61bf05e42d69fa58cec2c6a61d3e`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
DG-2 最終整合裁示：MoneyDJ Fund Identity、Insurance Product、Holding 與 NAV Probe

本提示語取代本輪所有尚未送出的 DG-2 補充提示語。

先重新做 GitHub Verification Gate，再依最新 main 執行。GitHub 為 SSOT，HANDOFF／STATE 僅參考。

目前已知基準：

- main 已到 "ba1b54ee"
- PR #1100 / #1101 已合併
- MoneyDJ NAV probe 已可在 GitHub Actions 連線
- production resolver、NAV precedence、UI、Shadow flag 均未變更

如 GitHub 最新狀態不同，以最新實況為準。

---

1. 最終資料身份模型

正式分成三層：

A. Fund Identity

代表真正的基金。

客戶目前及未來在 Google Sheet「基金代號」欄使用的都是：

MoneyDJ 基本基金代碼

例如：

- "TLZF9"
- "ACDD01"
- "ACTI71"
- "JFZN3"
- "ACCP138"

因此：

"Sheet 基金代號欄 = MoneyDJ namespace"

只限這一欄，不得擴張成全 repo 所有 code 都是 MoneyDJ。

基金 canonical identity 概念上應以：

"MoneyDJ base fund code"

為核心。

---

B. Insurance Product / Channel Identity

保險公司、保經、銀行平台等自己的商品／通路識別，與基金身份分開。

客戶已確認：

"ACDD01-EQTAL005"

其中：

- "ACDD01" = MoneyDJ 基金基本代號
- "EQTAL005" = 保險公司的商品代號

因此：

"EQTAL005" 不是基金 share class、不是另一檔基金，也不是另一條 NAV series。

正式概念：

- fund identity = "ACDD01"
- insurance product identity = "EQTAL005"

同理，若：

- "AL001"
- "24A7"

查證後屬保險／銀行／通路商品識別，也應放在 channel / product metadata，不建立新的 fund identity。

---

C. Holding Identity

同一基金可以存在於多張保單、多個商品、多筆持倉。

因此：

同一 "TLZF9"
≠ 同一 holding。

Fund Identity 與 Holding Identity 必須分開。

不得因基金 identity 收斂而合併：

- 保單
- 投入金額
- 單位數
- 成本
- 損益
- 交易
- 持倉紀錄

---

2. MoneyDJ Code 規則

MoneyDJ 基本基金代碼例如：

"ACDD01"
"TLZF9"

保險／銀行平台可能形成：

"ACDD01-EQTAL005"
"TLZF9-AL001"
"TLZF9-24A7"

但：

禁止使用通用 "split("-")[0]" 來判斷所有資料來源。

只有在來源已確認為 MoneyDJ＋平台／商品 mapping 有證據時，才可解析成：

"base fund code"
+
"channel / product code"

其他 namespace 不套用。

例如 FundClear：

"AGIF-HT5"
"AGIF-HTG"

不可切成 "AGIF"。

---

3. Sheet 契約

Google Sheet「基金代號」欄：

只接受 MoneyDJ 基本基金代碼。

例如：

"ACDD01"

而不是：

"ACDD01-EQTAL005"

如果 Sheet 此欄出現：

- URL
- "-" 後綴
- 非基本 MoneyDJ code
- 格式異常

標記資料契約問題：

"sheet_code_contract_violation"

原值保留，不靜默：

- 剝除
- 截斷
- 改寫
- 猜測

不改 Sheet schema。

---

4. MoneyDJ 境內／境外頁型

目前 repo 已驗證：

- "yp010000" = 境內
- "yp010001" = 境外

URL 若明確帶 page type：

以 URL evidence 為優先。

裸基金代碼：

不要再依不可靠 prefix 強推境內／境外。

無明確 evidence 時：

"page_type = Unknown"

不得猜。

客戶先前記憶中的 "A00001 / A00002" 不列入規格。

---

5. ACDD01 的正式解讀

客戶提供有效 MoneyDJ 頁：

"https://m.moneydj.com/a1.aspx?a=acdd01"

因此：

- "ACDD01" MoneyDJ fund identity 已確認
- 基本基金 MoneyDJ 頁可用
- "ACDD01" 的 NAV 應以基金基本頁為 baseline

不要再記成：

"ACDD01 基本頁找不到"

真正要驗的是：

"EQTAL005 → ACDD01"

這個保險商品 mapping。

它不是 NAV equivalence 問題。

---

6. ACDD01-EQTAL005 的 probe 解讀修正

原先：

"ACDD01 vs ACDD01-EQTAL005 NAV equivalence"

不再作為主要比較題。

改為：

Fund NAV

"ACDD01"

直接由 MoneyDJ 基本基金頁驗證。

Product Mapping

"EQTAL005"

只驗證：

「此保險商品是否連結到 MoneyDJ 基金 ACDD01」

如果 mapping 已來自客戶 policy / Sheet / 保險商品資料：

保留 provenance 即可。

不需要為 "ACDD01-EQTAL005" 強行尋找另一個 MoneyDJ NAV 頁。

---

7. TLZF9 probe 繼續累積

目前已觀察：

同一日期：

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"

三條路徑 NAV 都是：

"8.4121"

這是 FACT：

「三個頁面同日顯示相同 NAV」。

但：

平台頁沒有明示幣別。

因此目前只能記：

"strong observational evidence"

不能改成：

"strictly comparable"

不能自行補 USD。

---

8. 下一步：多日 MoneyDJ NAV Probe

沿用既有 probe workflow。

不用另開第二套 workflow。

累積：

3–5 個不同交易日

追蹤：

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"

每日記錄：

- NAV date
- NAV value
- fund name
- source page / platform
- currency 是否明示
- HTTP / parse status
- source timestamp
- parser / commit SHA

若 3–5 個不同交易日均：

- 同 NAV date
- 同 NAV value
- 基金名稱一致
- 無 identity conflict

則記：

"strong observational evidence: same NAV series"

但平台頁未明示幣別前，仍不得寫成 strict comparable。

---

9. 不採「幣別推定」

不同意：

平台頁未標幣別時，直接拿基本基金頁的 USD / TWD 補上。

原因：

- missing ≠ known
- provenance 必須可追溯
- 不猜幣別
- 不預設 USD

可以記：

"base page reports USD"

與：

"platform page currency not stated"

但不能合併成：

"platform currency = USD"

除非有來源證據。

---

10. Identity 與 NAV 分層

Identity resolver 回答：

「是哪一檔基金？」

NAV resolver 回答：

「這檔基金在指定日期／幣別／類股的 NAV 是多少？」

Insurance Product Mapping 回答：

「這個保險／銀行商品連結到哪一檔基金？」

Holding resolver 回答：

「哪一張保單／哪一筆持倉持有這檔基金？」

四者不得混用。

---

11. Cross-View 一致性

最終規則維持：

Same verified instrument / share class + same metric + same as-of + same currency = same canonical value across all views.

UI 不得各自：

- 重新選 source
- 重做 identity
- 建自己的 NAV semantics
- 建自己的公式

單一基金、我的持股、資產配置與 AI 最終都應讀 canonical data layer。

---

12. FundClear

FundClear 保持獨立 namespace。

客戶目前不是用 FundClear code 操作基金。

因此：

- 不直接把 MoneyDJ Sheet code 當 FundClear code
- 不自動 cross-map
- 不要求客戶補 FundClear code
- 不要求 ISIN

若未來要用 FundClear 當補充來源：

必須建立有 provenance 的 cross-source mapping。

無 mapping：

"Unknown / 無法判定"

不得猜。

---

13. ISIN

維持：

- 非必要
- 不作 canonical key
- 缺 ISIN 不警告
- 不要求 Sheet 補 ISIN
- 若外部來源自然提供，可當 verification attribute

---

14. dashed key cache

目前：

不新增

"cache/nav/{完整帶後綴代碼}.json"

作 production fallback。

因為 channel / insurance product code 不應自動建立新的 fund NAV source。

若未來證據真的顯示不同 product code 對應不同基金 share class / NAV series，再另走 Decision Gate。

---

15. Shadow flag

目前仍：

OFF

不要開。

至少等：

1. TLZF9 多日 probe 完成
2. 無 NAV conflict
3. resolver identity 穩定
4. product / fund / holding 分層完成
5. 再提出 Shadow flag Decision Gate

未核准前：

不得啟用正式 Shadow。

---

16. 之前 #1099 修過的解析 bug

已修：

- URL 被解析成 "HTTPS"
- "fetch_nav" / "fetch_div" 把 suffix 當基金 code
- policy URL fragment / "area="
- cache helper 無 production caller，僅釘測試

不要重做。

若後續 probe 發現新 bug：

先判斷是否局部修復。

只有涉及：

- canonical identity
- NAV source precedence
- valuation
- Sheet schema
- holding key
- 新資料來源

才進 Decision Gate。

---

17. Probe Evidence 與 Anti-Bloat

Probe 結果繼續寫既有：

"probe/moneydj-nav-results"

不要每天：

- 開新 PR
- 改 HANDOFF
- 改 BACKLOG
- 開新 Decision
- 寫重複 evidence

等累積到階段性結果再一次同步。

除非出現：

- NAV conflict
- fund name conflict
- parser failure
- 日期異常
- source 失效
- identity 語意衝突

否則完全靜默。

---

18. BL-0509

BL-0509 繼續原排程平行累積。

MoneyDJ probe 只可復用 workflow pattern。

不得和 BL-0509 合併成同一 data-source contract。

---

19. 下一次回報條件

等 3–5 個有效交易日 evidence 後，一次回報：

1. GitHub main / PR / CI
2. 日期矩陣
3. "TLZF9 / AL001 / 24A7" 每日 NAV
4. fund name 是否一致
5. currency evidence
6. 是否有 conflict
7. 是否仍屬 "strong observational evidence"
8. 是否已足夠進 Shadow flag Decision Gate
9. "EQTAL005 → ACDD01" mapping evidence 狀態
10. 下一個唯一安全接手點

---

20. 模型與 Effort

目前這一批：

Sonnet 5.5 + Medium

適用：

- probe
- targeted verification
- tests
- docs sync

若出現：

- fund vs share class identity 衝突
- NAV semantics 衝突
- product mapping 語意衝突
- canonical contract 要改
- source precedence 要改

先通知客戶，升：

Opus 5.5 + High

不要自行長期維持最高模型。

---

21. 工作模式

維持：

Silent Autonomous Cruise + Anti-Bloat

只有：

- 整批完成
- 真 Decision Gate
- Model / Effort Change Gate
- 真 blocker

才回報。

現在開始依上述規則執行。
```
