# 獨立治理稽核紀錄：OB-B 最小離線切片使用者逐字授權落盤（docs-only）
- 日期：2026-11-20
- 稽核者角色：fund-independent-qa（非作者；唯讀 Read/Grep/Glob；無法執行測試或查 GitHub/CI）
- 獨立性限制：與主 session 共享派工來源；獨立性僅限不同 context、無寫入能力、不審自己內容；不等於 PROJECT_RULES.md §8 人類層級獨立
- 風險分級：治理規則／AI 行為邊界（DEC-2026-10-16-05：至少 1 組真正獨立稽核）
- 基準／head SHA：未提供（NOT VERIFIED）
- 範圍：docs/DECISIONS.md（DEC-2026-11-20-01）、docs/BACKLOG.md（BL-0557 尾註）、docs/HANDOFF.md（Resume Checkpoint 新增一條）、docs/evidence/decisions/README.md（新增索引列）、docs/evidence/decisions/2026-11-20_obb_offline_slice_user_verbatim_authorization.md；對照 docs/evidence/obb_bc_gate_and_offline_application_2026_11_19.md、DEC-2026-11-18-03、DEC-2026-11-19-10、DEC-2026-10-31-03、DEC-2026-11-08-02
## 逐項結論
1. (a) 未寫入原文沒說的授權：通過（逐句對照）。
2. (b) 限制完整性：部分弱化。SDK 被窄化為「安裝或 requirements.txt 變更」、UI 被窄化為「UI 掛載」；其餘完整。→ S1
3. (c) 前置條件：原文所列（獨立治理稽核、白名單、CI）皆登記；補列項（docs PR 合併、Model/Mode/Effort Gate、非作者 QA）未標來源。→ S3。「四個程式檔」僅在 `__init__.py` 計入時與 Gate 卡 §3-2（4＋3＝7）吻合；原文「services/onebrain/ 的…測試檔」對測試位置有歧義。→ S2。Gate 卡 §3 型別欄位／守衛清單為候選，未經使用者逐項核准。→ S5
4. (d) 對 DEC-2026-11-18-03 待確認欄：原文自述覆蓋 (b)(c)(c″)、不等 D2、(d) 位置；未提 (c′)(e)(f)；DEC 本身未誤稱涵蓋，BACKLOG/HANDOFF 敘述較強。→ S4
5. (e) 對 DEC-2026-10-31-03／11-08-02 僅照錄原文自述，未擴張：通過。
6. (f) README 索引只加不刪、與 DEC 一致（README 自身檔的 byte／sha 未驗）；BACKLOG 舊句未註記被部分取代。→ S4
7. (g) 格式與既有 DEC 一致；無個資、無 secret：通過。
8. HANDOFF 行數：tests/test_canonical_rule_consistency.py 設 HANDOFF_MAX_LINES＝120；工作樹 HANDOFF.md 計 121 行，疑似使 test_handoff_is_not_accumulating 轉紅（稽核者未執行，NOT VERIFIED；主 session 另行實跑確認為紅）。→ M1
## Must-Fix 清單
- M1：HANDOFF 超過 120 行上限，須併入現有行並實跑 tests/test_canonical_rule_consistency.py 附原文證據。
## Should-Fix
- S1 限制措辭不弱化；S2 四程式檔計法與測試位置釐清；S3 前置條件來源標註；S4 BACKLOG/HANDOFF 與 DEC 敘述一致並標明未涵蓋項 (c′)(e)(f)；S5 Gate 卡 §3 設計細節仍為候選。
## NOT VERIFIED
- 逐字檔／README 的 bytes 與 sha256；使用者在 ChatGPT 親自確認之事實；main c7a1349f；HANDOFF 實際行數與守衛結果；Gate 卡 §3 白名單與既有守衛影響；全稱句皆為單組字面搜尋、未經第二組驗證。
## 結論
Must-Fix 1 項（M1）未清零前，不建議合併；Must-Fix 清零後，本稽核不授權程式 PR，亦不解除 DEC-2026-11-20-01 所列任何前置條件。

---

## 處置狀態（執行組於稽核紀錄本文之後附註；上方稽核本文未改寫）

| 項目 | 處置 | 修正位置（2026-11-20，docs-only，未 commit） |
|---|---|---|
| M1 HANDOFF 超過 120 行 | 已修正：新增內容併入「第十四次狀態同步」同一行，刪除獨立新增行；`docs/HANDOFF.md` 回到 120 行 | `docs/HANDOFF.md` |
| S1 不授權列措辭弱化 | 已修正：SDK 改為「不得使用 SDK（含 import、安裝、`requirements.txt` 變更）」；UI 改為「UI（含任何渲染與掛載）」 | `docs/DECISIONS.md` DEC-2026-11-20-01「不授權範圍」列 |
| S2 四程式檔計法與測試位置 | 已修正：註明依 Gate 卡 §3-2 計為 4＋3＝7；測試位置字面有歧義，須白名單核對時由使用者／總管確認，程式 PR 不得單方決定 | `docs/DECISIONS.md`（新增「計法與待確認註」列）、`docs/evidence/decisions/README.md` 索引列 |
| S3 前置條件來源標註 | 已修正：獨立治理稽核、白名單、CI 出自原文；docs PR 合併、Model／Mode／Effort Change Gate、非作者 QA 為執行組補列，非原文 | `docs/DECISIONS.md`「尚未滿足的開工前置」列；`docs/BACKLOG.md` BL-0557 尾註 |
| S4 (c′)(e)(f) 未涵蓋 | 已修正：加註原文自述涵蓋 (b)(c)(c″)、不等 D2、(d) 位置；(c′)（67 §5.7 Stop Gate 1）、(e)、(f) 原文未提，仍待確認；不改 DEC-2026-11-18-03／-11-19-10 本文 | `docs/BACKLOG.md` BL-0557 尾註、`docs/HANDOFF.md`（併入第十四次同步行） |
| S5 Gate 卡 §3 仍為候選 | 已修正：註明 Q-OB1 A／Q-OB2 A 內容見 Gate 卡 §2；Gate 卡 §3 型別欄位、守衛清單、Fake 輸出規格仍為「候選，未經使用者逐項核准」 | `docs/DECISIONS.md`（新增「計法與待確認註」列） |
| Nit DEC 標題 | 已修正：改為「授權範圍以原文為準；開工前置未滿足，尚不得開程式 PR」 | `docs/DECISIONS.md` DEC-2026-11-20-01 標題 |

本處置狀態僅記錄文件修正，不解除 DEC-2026-11-20-01 所列任何前置條件，亦不授權程式 PR。處置後的修正尚待 PR 階段再經獨立確認（本處置由執行組自行撰寫，未經第二組驗證）。
