# 客戶 2026-11-02 第三則指示：永久 UI 邊界（只動 New UI）、Final UI 視覺基準與 UI-15 Gate（逐字摘錄）

- **來源**：客戶 2026-11-02 在對話中的第三則指示（同日 Final UI／Decision System Contract Freeze 主線、#1119 UI-15 增量收斂）；經總管逐字轉存為文字檔。執行組未見客戶對話本身，只依派工單抄入。
- **摘錄範圍**：只摘錄與落盤有關的段落：第三、四、七～十二、十四、十五節。**未摘錄**：第二節（Model／Effort）、第五、六、十三、十六～十八節（總管註明為執行指示）；第一節派工單未提及、執行組未見其內容。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-02-02`（第三、四節：New UI 唯一正式產品線、Old UI 永久只作 read-only reference、Final UI 視覺基準＝既有 New UI）。第七～十二、十四、十五節屬 UI-15 proposal 與最終 Gate 的呈現要求，落地：`docs/v2/79_final_ui_contract_freeze.md` 第 13、14、17 節（**UI-15 尚未裁示，A 只是推薦；本檔不構成 UI-15 裁示**）、`docs/BACKLOG.md` BL-0531（子項 BL-0531-UI15）、`docs/HANDOFF.md` Resume Checkpoint。
- **存檔日期**：2026-11-02
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
三、永久 UI 邊界：只動 New UI
客戶最新明確裁示：
「正式產品只修改 New UI。Old UI 永遠只作參考，不再修改。」
這條必須成為本專案持久治理規則。
Old UI 可以參考
只允許參考：業務邏輯、資料處理方式、已驗證公式、deterministic rule、欄位、流程、edge case、fallback、interaction experience、已存在且仍值得遷移的 capability
Old UI 不可以搬回
禁止直接移植：layout、visual design、navigation、page structure、information architecture、component hierarchy、Old UI presentation pattern
正確遷移方式
Old UI capability / logic → 確認是否仍符合最新 DEC / Contract → 重新設計成 New UI information architecture / component → 只在 New UI production 實作
因此：「New UI 是唯一正式產品線。」
不得維護兩套 UI。
不得因為 Old UI 有某個功能，就去修 Old UI。
不得把 Old UI 當 migration target。

四、Final UI 視覺基準
Final UI Contract 不代表重新設計整站。
目前既有 New UI 是正式 baseline。
原則：「保留現有 New UI visual language、mobile-first、card hierarchy、navigation 與既有 layout baseline；只對經 Decision Gate 核准的資訊架構、component 或局部 layout 做增量調整。」
禁止：全站 redesign；因 Final UI Freeze 重新發明另一套 design system；把 Old UI 外觀重新搬回 New UI；同時演進 Old / New UI

七、UI-15 Ownership
目前 proposal 維持：💼 我的資產擁有 Dividend Calendar；定位：secondary/detail 或「查看配息行事曆」CTA；不塞第一屏；不新增第六頁；未來 UI 必須依 New UI design system 重做。Old UI calendar 只能參考其能力／邏輯。禁止直接複製 Old UI calendar layout。
⚙️ 設定擁有：Notification Preferences、LINE connection / delivery health、notification audit、最近成功通知、最近失敗、test notification。但：「Notification Preference ≠ Investment Rule」。⚙️ 不得因此取得：Risk Cap 編輯權、action rule 編輯權、threshold 編輯權。

八、UI-15 Information 與 Action 必須永久分離
Information / Event Notification 可以進此次 proposal：Record Date、Ex-Dividend Date、Payment Date、date change、Missing、estimate → official upgrade、Dividend Calendar、月底下月摘要。
Directional / Action Notification 本批禁止恢復：換股、加碼、減碼、賣出、switch、allocation advice、action advice。未來必須等待：Deterministic Rules → Risk Cap → System Action State → official action vocabulary → OneBrain controlled integration。

九、Date Contract
至少區分：1. Record Date 2. Ex-Dividend Date 3. Payment Date 4. Estimated Bank Credit Window。強制：「Payment Date ≠ 實際銀行／平台入帳日。」除非未來存在 actual bank/platform credit event data。否則不得冒充。Missing 就是 Missing。

十、Date Status / Source Precedence
目前 proposal：confirmed、scheduled、estimated、unavailable。但必須先查 repo 是否已有正式 vocabulary。不得建立第二套。尤其：estimated ≠ confirmed；legacy "is_actual" 不得直接等同 official confirmed。
Source precedence 方向：Official confirmed / scheduled ↓ existing approved authoritative structured ↓ existing approved secondary structured ↓ historical deterministic estimation ↓ Unavailable。不新增 source。正式日期永遠優先於 estimation。

十一、Dividend Estimator
既有："services/dividend_calendar.py" 可以保留。定位：「Dividend Date Fallback Estimation Engine」。這是 logic capability。不是 Old UI ownership。只在正式日期不存在時 fallback。不得把 estimator confidence 當：LLM confidence、success probability、未校準機率。需保持 deterministic evidence semantics。

十二、Decision Digest / OneBrain Boundary
未來 objective Dividend Event facts 可以進 Digest candidate：event date、event type、status、provenance、revision、Missing。但以下不得進投資 Decision Digest / OneBrain fingerprint：LINE delivery status、retry count、render metadata、channel health、test notification state、UI widget state、Old UI presentation metadata。資料層與 AI reasoning 層保持分離。

十四、Final Decision Gate
等 #1119 完整收斂後，再一次呈給客戶。應為：UI-1～UI-15 一次裁示。但 UI-11：「已裁示，不重問。」
UI-15：
A｜推薦：💼 擁有 Dividend Calendar；⚙️ 擁有 notification preferences / health / audit；official date first；deterministic estimate fallback；月底下月 LINE summary 保留；semantic date-change notification 可作未來能力；directional/action LINE 不恢復；Old UI capability 只參考邏輯；production 只實作 New UI
B：只保留月底 LINE summary，不把 Calendar 納入 New UI。
C：全部延後。
不得替客戶選 A。

十五、UI-12 特別注意
原先 UI-12 包含：🌍 比較圖、💼 容許帶、依據卡上限、比較上限 3 檔。其中 🌍 比較圖若會改動既有 "DEC-2026-10-30-01" D1：必須在最終 Gate 明確指出：「這是 amendment，而不是單純機械實作。」不得偷偷改既有裁示。
```
