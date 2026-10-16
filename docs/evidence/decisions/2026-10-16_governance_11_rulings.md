# 客戶 2026-10-16 治理十一項裁示（逐字存檔）

- **來源**：客戶 2026-10-16 在對話中正式裁示（`PROJECT_RULES.md` 第 14 節所列 11 項治理衝突的處理方案），經總管逐字轉存給文件實作組；本檔把全文落盤到 repo，作為 `docs/DECISIONS.md` `DEC-2026-10-16-03`～`DEC-2026-10-16-13` 的 provenance。
- **存檔日期**：2026-10-16。**存檔時的 base**：main `ab30239`（全長 `ab302390886e1818f0d9a56afccdf3ba9dd7a41b`）。
- **名稱**：一律稱「客戶 2026-10-16 治理十一項裁示」，項次寫「治理第 N 項」。同日另有一份「客戶 2026-10-16 十點裁示」（PR #974～#977；交接本第 5 節〈已裁示（2026-10-16）〉第 62～71 點），兩者不是同一份，不得只寫「第 6 點」。
- **逐字原則與唯一例外**：下方圍欄內容逐字照抄總管轉存的全文，一字不改、不加刪除線、不重排；**唯一例外**是禁詞。全文含交接本第 7 節〈客戶 2026-10-05 接手訊息：禁詞〉詞表的**第 7、8 個詞**，共 **3 處**，都在治理第 6 項的「未來允許的方向」列舉內（圍欄內第 114、116、117 行；第 1 行為圍欄內第一行）：第 7 個詞單獨一列一次、「暫停」後接第 7 個詞一次、第 8 個詞單獨一列一次。這 3 處依交接本第 7 節〈禁詞〉體例以 Unicode 跳脫碼書寫（`\u52a0\u78bc`、`\u6e1b\u78bc`），理由：本批新增行以禁詞 0 命中為目標（碼位組字掃描），若照字面寫入，本檔自己會命中。把這兩組跳脫碼換回原字，即與總管轉存的原文逐位元組相同（驗證見 `README.md`）。
- **效力**：本檔是裁示原文的存檔，不是新規則；各項如何落地、哪些仍待程序完成，以 `docs/DECISIONS.md` 第四節各條目為準。治理第 6 項涉及子法 1 的修正，**修正程序尚未完成**（提案單見 `docs/v2/56_proposal_8_directional_judgment.md`〈母法修正提案單 #8〉）。

---

```text
客戶已正式裁示："PROJECT_RULES.md" 第 14 節列出的 11 項治理衝突，全部依下列方案處理。

請先重新核對 GitHub 最新實況；目前最後確認 checkpoint：

- repo："linchen-20200325/my-Fund-dashboard"
- main："ab30239"
- PR #979 已合併
- Project AI Constitution v1.0 已導入
- Phase 3 尚未開始

本批目標是「消除治理衝突並正式落盤」，不是產品功能開發。

客戶正式裁示

1. 請示邊界／正式 threshold

統一採 Project AI Constitution v1.0 的 Stop / Decision Gate。

已核准範圍內的安全工作由專案 AI 自主完成。

涉及以下事項必須停下請客戶裁示：

- 新／替換 production data source、API、MCP
- 正式公式或投資語意
- data identity 規則
- 正式 threshold 的值或語意
- frozen Constitution／正式母法
- 產品方向
- 會改變投資判斷的 AI 行為
- destructive migration
- 無法證明安全的資料／歷史成果刪除
- 多個合理方案且結果具有產品意義

若只是把「已經核准的 threshold」接到程式常數，值與語意完全不變，可自主處理。

已確認 bug 且只有一個明確安全修法，不得包裝成客戶裁示。

舊規則中與此衝突的「唯一只能問兩類／三類」或其他封閉列舉，正式 supersede。

2. Silent Autonomous Cruise 出聲時機

統一為六類：

1. 完整 milestone／batch 完成
2. 真正 blocker
3. 客戶裁示
4. GitHub 實況重大不一致
5. 無法安全自行修復的錯誤
6. 需要客戶手動切換 model／mode／Effort

除此之外保持靜默。

施工過程、派 agent、push、開 PR、等 CI、audit 進行中等，不回報。

完成回報原則上 ≤5 行。

3. QA／獨立稽核

採風險分級：

- 普通低風險文字、說明、交接同步：可以自驗。
- 治理規則、data semantics、investment meaning、formula、identity、freshness、provenance、migration、destructive cleanup：至少 1 組真正獨立稽核。
- 資安／重大合規：2 組獨立稽核。

不得要求所有 C 級文件一律派多組稽核，也不得用「文件修改」名義逃避高風險語意變更的獨立稽核。

4. commit／push／merge

2026-09-28 之後的常設授權正式 supersede 舊的「未經我同意不准 commit／push／merge」字面規則。

符合既有 Auto-Ship／常設授權條件時：

- commit
- push
- PR
- CI
- audit
- fix
- merge

均可自主完成。

任一必要條件不成立則不得強行 merge。

force push、破壞性操作及不在常設授權內的高風險動作仍需依 Stop / Decision Gate 處理。

5. 現行熱狀態文件

"docs/HANDOFF.md" 正式成為唯一現行熱交接文件。

"STATE.md"：

- 保留歷史；
- 不再作為現行熱資料來源；
- 不再要求持續更新；
- 不刪除，除非未來另有正式裁示。

舊大型交接本：

- 永久作歷史紀錄；
- 不再續寫。

請修正 "PROCESS.md" 等仍要求使用 "STATE.md" 作現行熱資料的字面衝突。

6. 方向性投資判斷

正式確認：

取消「永久禁止方向性投資建議」的規則。

未來允許的方向可以包括：

- 建立部位
- \u52a0\u78bc
- 續抱
- 暫停\u52a0\u78bc
- \u6e1b\u78bc
- 退出
- 無法判定

但這不代表現在立即啟用。

B 線 v1 現階段仍不輸出正式方向性判斷。

必須等 Phase 7：

- 正式准入規格
- evidence requirements
- freshness/provenance
- data completeness
- validation/backtest
- safety/invalidation conditions
- 正式審查／客戶裁示

完成後才能 production 啟用。

資料不足時必須：
"⬜ 無法判定（資料未備／證據不足）"

不得猜測。

請依 repo 既有 amendment procedure 正式處理與此裁示衝突的子法／母法文字。

若修改 frozen Constitution／母法本身依既有程序仍需要額外明示批准，不要自行越權修改：

- 先完成合法可完成的 amendment proposal／提案單；
- 清楚指出唯一剩餘需要客戶簽核的動作；
- 不要因為本裁示而假裝 amendment procedure 已完成。

7. commit AI 署名

維持既有客戶裁示：

commit message 不加入 AI 共同作者署名、session URL 或其他 AI 身分署名。

此項視為已解決，不再列為 open conflict。

8. Remote branch lifecycle

新 PR 的 head branch：

- PR 合併後依 repo 現有 "delete_branch_on_merge" 設定自動刪除，屬正常常設授權。
- 不需要每次另問客戶。

既有／歷史 remote branch：

- 必須先完成 Preservation Check；
- 確認 unique commits、research/evidence、worktree residue、正式引用與 workflow/runtime dependency 均已處理；
- 證據完整且明確 superseded 者，可進入 cleanup eligible。

不要求「每刪一支都永久必須問客戶」。

但以下仍需客戶裁示：

- 大批／大規模 branch cleanup；
- preservation evidence 不完整；
- branch 有 production/workflow dependency；
- 刪除結果具有產品或資料保存意義。

本批仍不要實際清理歷史 remote branches。

9. 完成回報格式

聊天中的 milestone 完成回報原則上 ≤5 行。

詳細內容放：

- PR description
- tests／audit evidence
- "docs/HANDOFF.md"
- 必要正式文件

不得因聊天精簡而省略正式證據。

舊三段式長報告不再要求完整貼進聊天。

10. 舊交接本更新義務

舊規則中「每次 merge／audit 後更新交接本」的義務，正式改讀為更新：

"docs/HANDOFF.md"

舊大型交接本不再更新。

請修正仍指向舊交接本的現行治理文字，但保留歷史原文與 provenance，不改寫歷史紀錄。

11. 新對話／開工必讀順序

正式統一為：

1. "CLAUDE.md"
2. "PROJECT_RULES.md"
3. "docs/HANDOFF.md"
4. "docs/BACKLOG.md"
5. "docs/DECISIONS.md"
6. 本階段對應的正式 Constitution／SSOT／spec

"STATE.md" 不再作為現行熱資料入口。

請修正 "PROCESS.md" 中與此衝突的「僅限讀 STATE.md」等字面規則。

執行要求

1. 把上述 11 項正式登記到 "docs/DECISIONS.md"，provenance 標示為客戶 2026-10-16 正式裁示。
2. 更新 "PROJECT_RULES.md" 第 14 節：
   - 已裁示者不得繼續列成 open conflict；
   - 清楚標示 superseded 關係。
3. 合法範圍內同步修正 "PROCESS.md"、現行治理索引與其他會讓新 agent 誤讀的 active rule。
4. 歷史文件保留原文，不為了乾淨而重寫歷史。
5. 第 6 項若涉及 frozen Constitution／母法 amendment，嚴格走既有 amendment procedure；不要越權。
6. 重新做 cross-reference audit，確認不再產生競爭 SSOT。
7. 本批屬治理高風險變更，至少 1 組真正獨立稽核；若實際觸及重大合規／母法，依規則升級驗證。
8. 適當 tests／constitution guards／CI 全綠後才可 merge。
9. merge 後重新驗證 main，更新 "docs/HANDOFF.md"。

本批禁止：

- Phase 3 UI 修改
- 基金功能修改
- production data source 修改
- production formula／threshold 修改
- Phase 7 production 實作
- 歷史 remote branch cleanup
- 關閉與本批無關的舊 Draft PR

完成後停在 safe checkpoint，不要自行開始 Phase 3。

最終只需精簡回報：

- 11 項是否全部正式收斂；
- 第 6 項是否仍有 amendment／母法簽核待客戶處理；
- PR / main SHA；
- audit / CI；
- 是否已可開新對話正式開始 Phase 3。

維持 Silent Autonomous Cruise。
```
