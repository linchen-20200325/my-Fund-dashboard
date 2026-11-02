# 客戶 2026-11-02 第四則指示：New UI2 架構方向（逐字摘錄）

- **來源**：客戶 2026-11-02 在對話中的第四則指示（同日 Final UI／Decision System Contract Freeze 主線、#1119 收斂中）；經總管逐字轉存為文字檔。執行組未見客戶對話本身，只依派工單抄入。
- **摘錄範圍**：只摘錄開頭裁示段與第 3～6、9、19 節。**未摘錄**：第 1～2、7～8、10～18、20～25 節（架構提案的工作指示；完整架構提案另批落盤，`docs/BACKLOG.md` BL-0533）。第 6 節內的「……」為轉存時原有的省略，不是執行組刪字。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-02-03`（New UI2 架構方向；amend `DEC-2026-11-02-02`）。目錄命名、ui_v2 freeze policy 細節、preview／cutover 細節、視覺語言沿用範圍、既有 presentation DEC 的 amendment **仍待客戶裁示**，另批 New UI2 Architecture Proposal 提出。
- **存檔日期**：2026-11-02
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
客戶已作新的架構方向裁示：
「後續不再以「持續修改現有 New UI」為主要路線。改為建立全新的 New UI2 Presentation Layer。
但不是重寫整套系統。
已驗證的 data / services / deterministic logic / source / provenance / health / domain rules 能重用就重用。
Old UI 與目前 New UI 都只能作能力、邏輯與經驗參考；New UI2 的 presentation 必須重新乾淨建立。」
這是一個新的 Architecture Decision Gate。

3. 先處理 #1119
#1119 不因 New UI2 而作廢。它仍負責 Final UI / Decision System Contract 的語意收斂，尤其：UI-15 Dividend Calendar、LINE Information / Event Notification、date semantics、source precedence、provenance、notification ownership、Digest / OneBrain boundary。
但是：#1119 不得再寫成「後續直接在現有 ui_v2 上逐批修改 production」。
若需要最小 docs amendment，應改成：「Final UI Contract 的語意規格將作為 New UI2 的 input contract。production implementation target 改為 New UI2。現有 New UI 不再作主要演進目標。」
不要擴大 #1119 成大規模 architecture PR。

4. New UI2 核心架構原則
New UI2 定義：「Greenfield Presentation Layer」
它不是：新資料系統、新 business rule engine、新 AI engine、新 source layer、新 portfolio engine。
New UI2 的目標是：「重新建立乾淨、mobile-first、五頁一致的 presentation architecture。」

5. 三代 UI 的永久邊界
Old UI 定位：Read-only Logic Reference。可參考：業務邏輯、計算公式、edge cases、fallback、已驗證流程、capability。禁止：修改、重構、新增功能、搬 layout、搬 navigation、搬 visual style。
現有 New UI / "ui_v2" 定位：Legacy New UI / Reuse Candidate。從現在開始：不再把「持續 patch ui_v2 畫面」當主要路線。但是 "ui_v2" 裡已經乾淨分層、可重用的東西不得盲目重寫。（例如可研究是否重用：pure helpers、health model、source adapters、view-model-like structures、deterministic presentation contract、shared symbols、data normalization、live/source split、tests that validate domain semantics）不可因為要做 New UI2 就重寫所有成熟模組。
New UI2 定位：唯一未來正式 Presentation Layer。未來所有 UI production 都只進 New UI2。

6. 不要先決定資料夾名字
先盤點，再提案。……資料夾命名屬 architecture freeze 的一部分。

9. 五頁 IA 不變：1. 🌍 市場與趨勢 2. 💼 我的資產 3. 🔍 找基金 4. 🤖 AI 投資總結 5. ⚙️ 設定。禁止新增第六個主要頁面。

19. Cutover Strategy
預設方向：Old UI → 永久 read-only；ui_v2 → Freeze / maintenance-only；New UI2 → 建立 → fake/view-model data 驗證 → page-by-page integration → parallel preview → acceptance → switch default → 再評估清理 ui_v2。禁止先刪 ui_v2。
```
