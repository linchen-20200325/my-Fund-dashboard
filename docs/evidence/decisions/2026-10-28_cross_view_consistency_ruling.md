# 客戶 2026-10-28 新增正式高優先需求：Cross-View Data Consistency Gate（逐字）

- **來源**：客戶 2026-10-28 對話中的正式需求指示，經總管於派工單內逐字轉存；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-28-01`（客戶裁示，永久治理原則＋本輪僅 audit／matrix／gap／test proposal）。落地：`PROJECT_RULES.md` 13.3、第 0.5 節索引一列、`docs/v2/69_cross_view_consistency_spec.md`、`docs/BACKLOG.md` BL-0519～BL-0524、`docs/HANDOFF.md` Resume Checkpoint。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為派工單內客戶原文，字句未改；唯一格式處理：本檔圍欄內無只含空白的行，行尾空白已確認為 0 行，其餘字元、順序、段落一字未動。
- **存檔日期**：2026-10-28
- **圍欄內文 sha256**：`cf764a431f42db59d8d84b07b2e0e295e90a246a7e604feb73f78c5ff3497617`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
新增正式高優先需求：

Cross-View Data Consistency Gate

客戶曾實際遇過：
同一檔基金／股票，在單一標的頁與投資組合／持股頁顯示不同 NAV、價格或報酬，原因是各頁使用不同來源、cache、as-of 或 fallback。

這次 vNext 必須避免重演。

請先將此需求正式落盤到：

- PROJECT_RULES（永久治理原則）
- BACKLOG
- HANDOFF
- 必要的 data-contract / design spec

核心規則：

Same canonical instrument + same metric + same as-of + same currency/share class = same canonical value across all views.

正式架構：

"Raw Sources"
→ "Source Resolution / Validation"
→ "Canonical Instrument Data"
→ "Domain Calculation"
→ 各 Page Data View
→ "One AI Brain"

禁止各頁自行選來源或平行計算同一 metric。

先做 repo-wide audit，不直接重構。

至少盤點：

1. 單一基金 NAV 的來源
2. 我的持股 NAV 的來源
3. 資產配置估值來源
4. 各頁報酬率公式是否一致
5. cache key / TTL 是否一致
6. NAV / price business date 是否一致
7. FX date 是否一致
8. primary / fallback source precedence 是否一致
9. canonical fund identity / ISIN / share class 是否一致
10. 同一 metric 是否存在多套 implementation
11. Sheet 內的 NAV／價格是否被當成 market-data SSOT
12. AI Brain 未來是否可能讀到與 UI 不同版本的數值

產出：

"Cross-View Data Consistency Matrix"

至少包含：

Instrument / Metric| Single View| Holdings| Allocation| AI Input| Source| As-of| Currency| Consistent?| Root Cause / Action

基金至少檢查：

- NAV
- NAV date
- currency
- return 1D / 1M / 3M / 1Y
- benchmark
- fund code
- ISIN / canonical identity
- share class
- source
- fetched_at
- as_of

股票／ETF 若有則至少：

- close / adjusted close
- price date
- return
- currency
- ticker / canonical ID
- source
- fetched_at
- as_of

若同一資料有多來源：

- primary
- fallback
- fallback trigger
- freshness requirement
- identity validation
- conflict behavior

必須集中在資料層定義，頁面不得自行決定。

如果同一 as-of 的來源數值衝突：
不要靜默選一個。
至少留下 selected source / rejected source / difference / reason / freshness。

若尚無法判斷：
"⬜ 資料來源不一致，暫無法判定"

另外建立 automated consistency test proposal：
同 canonical ID + 同 metric + 同 as-of 的單一基金／持股／配置／AI input 必須一致。

本輪只做：

- audit
- matrix
- gap
- test proposal

不要直接大改 source precedence / canonical contract。

若 audit 發現需要更改：

- source precedence
- canonical identity
- valuation methodology
- FX cutoff
- formula

再走 Decision Gate。

此項不要取代 BL-0509。
BL-0509 多日 probe 照原計畫繼續；Cross-View Consistency 可作為下一個獨立資料治理 batch。

Model：Sonnet 5.5
Effort：Medium

若進入 canonical data contract / source precedence 實作，再依 Model Gate 評估升 Opus。
```
