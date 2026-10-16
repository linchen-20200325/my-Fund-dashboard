# 客戶 2026-10-16 提案單 #8 核准裁示（逐字存檔）

- **來源**：客戶 2026-10-16 在對話中正式核准 `docs/v2/56_proposal_8_directional_judgment.md`〈母法修正提案單 #8〉全部四項，經總管逐字轉存給文件實作組；本檔把全文落盤到 repo，作為 `docs/DECISIONS.md` `DEC-2026-10-16-14` 的 provenance。依此裁示施工的正式修正案是 `docs/v2/57_amendment_8_directional_judgment.md`〈子法 1 正式修正案 #8〉。
- **存檔日期**：2026-10-16。**存檔時的 base**：main `66b6033`（全長 `66b60336589b7fe04bce051f629bb76ff41c692f`）。
- **名稱**：一律稱「客戶 2026-10-16 提案單 #8 核准裁示」，簡稱「#8 核准裁示」。它不是「客戶 2026-10-16 治理十一項裁示」（`docs/evidence/decisions/2026-10-16_governance_11_rulings.md`），也不是同日的「十點裁示」（PR #974～#977），不得混用。
- **逐字原則與唯一例外**：下方圍欄內容逐字照抄總管轉存的全文，一字不改、不加刪除線、不重排；**唯一例外**是禁詞。裁示全文有**三處**含交接本第 7 節〈客戶 2026-10-05 接手訊息：禁詞〉詞表的第 7、8 個詞，都在「新正式政策邊界」一段「允許的方向性狀態」列舉內（圍欄內第 62、64、65 行；第 1 行為圍欄內第一行）：`\u52a0\u78bc`（第 7 個詞單獨一列）、`暫停\u52a0\u78bc`（「暫停」後接第 7 個詞）、`\u6e1b\u78bc`（第 8 個詞單獨一列）。這三處依交接本第 7 節〈禁詞〉體例以 Unicode 跳脫碼書寫，理由：本批新增行以禁詞 0 命中為目標（碼位組字掃描），若照字面寫入，本檔自己會命中。把這兩組跳脫碼換回原字，即與總管轉存的原文逐位元組相同。
- **三個 sha256**（2026-10-16 實跑；驗證指令見同目錄 `README.md`）：
  - 圍欄內文（跳脫碼形式，即本檔圍欄內實際位元組）：`8a0ab952b71f09142e7277243d994fe111de2a44efc763c98d23aaf8a237e0e2`
  - 圍欄內文把兩組跳脫碼換回原字後（＝總管轉存的原文）：`81fa7da3edd0289e8172e4950d517d4c9f86c918e32407b66f275eedb80ed770`
  - 整檔：見同目錄 `README.md` 存檔清單。整檔雜湊涵蓋本檔頭，無法寫在本檔之內（寫進來就會改變它自己），所以只登記在 `README.md`。
- **效力**：本檔是裁示原文的存檔，不是新規則；落地條文以 `docs/v2/57_amendment_8_directional_judgment.md` 與 `docs/DECISIONS.md` `DEC-2026-10-16-14` 為準。

---

```text
客戶正式核准 "docs/v2/56_proposal_8_directional_judgment.md"（提案單 #8）全部四項。

本訊息即為客戶對提案單 #8 的正式批准，日期 2026-10-16。

正式裁示

1. 黑名單前三個片語

批准改為：

「Phase 7 正式准入前的現況守衛」

不再解讀為永久禁止方向性投資判斷。

Phase 7 正式准入前仍維持現況，不得因本次 amendment 提前啟用 production 方向性建議。

2. 2026-08-07 舊裁決

「不再輸出任何配置行動建議」正式改讀為：

Phase 7 正式准入前的現況限制，而非永久禁止。

保留原始歷史裁決與 provenance，不得竄改歷史紀錄。

3. 母法修改方式

批准採你建議的方式：

原母法／歷史原檔不直接改寫；另立正式 amendment 文件。

新 amendment 必須：

- 清楚指出被修正／取代的條文；
- 記錄客戶核准日期與 decision provenance；
- 保留原文歷史；
- 清楚寫明新規則的生效範圍；
- 不製造第二套互相競爭的母法。

4. 子法 1

批准：

子法 1 中把相同永久禁止內容稱為母法、或延續相同永久禁止語意的條文，一併依正式 amendment procedure 修正。

修正後必須與新母法 amendment 一致，不得殘留「永久禁止方向性投資建議」的矛盾讀法。

---

新正式政策邊界

本次 amendment 的目的只有：

取消「永久禁止方向性投資建議」。

不代表現在立即啟用方向性建議。

目前 B 線 v1 仍不得輸出正式 production 方向性投資判斷。

未來 Phase 7 完成正式准入後，允許的方向性狀態可包括：

- 建立部位
- \u52a0\u78bc
- 續抱
- 暫停\u52a0\u78bc
- \u6e1b\u78bc
- 退出
- 無法判定

正式啟用前仍必須完成／符合：

- 正式 Phase 7 specification
- evidence requirements
- data completeness
- freshness
- provenance
- validation / backtest
- safety / veto / invalidation conditions
- 正式 review
- 必要客戶裁示

資料不足或證據不足時必須：

"⬜ 無法判定（資料未備／證據不足）"

不得猜測，不得以 AI 補造客觀資料。

Phase 7 Research Hypotheses 仍維持 Non-Production；本次 amendment 不會把任何候選 threshold 自動升格為 production rule。

---

執行要求

請依 repo 現行 Constitution／amendment procedure 完成本次正式修正。

同步處理：

- 正式 amendment 文件
- 子法 1 必要修正
- "docs/DECISIONS.md"
- "docs/BACKLOG.md" 對應項目的狀態
- "PROJECT_RULES.md" 若仍有相關 provisional/conflict 記錄
- "docs/HANDOFF.md"
- 必要 cross-reference / constitution guards

保留所有歷史原始文件與 provenance。

本批屬母法／投資語意治理變更：

- 必須做適當獨立稽核；
- constitution guards／相關 tests 必須通過；
- CI 全綠才可 merge；
- merge 後重新驗證 main。

本批禁止：

- Phase 3 UI 修改
- 現在啟用方向性投資建議
- 實作 Phase 7 decision engine
- 修改 production threshold
- 修改 production data source
- 歷史 remote branch cleanup
- 順手處理無關 backlog

目前 GitHub 最後確認 checkpoint：

- main "66b6033"
- Phase 3 尚未開始
- "ccr-8f3b9d52-xgnleg" 與 main 指向相同 commit；不要把它誤判成未合併功能工作。

完成後停在 safe checkpoint。

最終只需精簡回報：

1. 提案單 #8 amendment 是否正式生效；
2. 母法 amendment／子法 1 是否已完全一致；
3. PR／最新 main SHA；
4. audit／tests／CI；
5. 是否還有任何方向性政策 blocker。

不要自行開始 Phase 3。
維持 Silent Autonomous Cruise。
```
