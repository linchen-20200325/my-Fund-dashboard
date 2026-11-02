# 客戶 2026-11-02 正式裁示：New UI2 NG-1～NG-5、正式 Streamlit 顯示規則、Final UI UI-1～UI-15、Git 歷史、Model／Effort Change Gate（逐字）

- **來源**：客戶 2026-11-02 在本對話中的訊息，經總管轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **性質**：正式裁示（formal ruling）。其中「正式 Streamlit 顯示規則」一節客戶明列為正式裁示，屬永久治理。本檔只存原文，不含執行組讀法；圍欄為轉存的客戶原文，字句未改。原文中的模型名屬客戶原文，保留。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **存檔日期**：2026-11-02
- **base**：main `e5794711`（#1120 合併；本檔為未追蹤新檔）
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。

```text
同意這次一次收斂。

目前建議模型／模式／理解力：

- Model：Claude Opus 5.5
- Mode：維持目前高理解／架構決策模式
- Effort：High

本批仍是正式架構與合約裁示落盤，不是機械式 UI coding。

---

New UI2 NG-1～NG-5

全部採 A。

- NG-1：採 "ui_v3/"
- NG-2："ui_v2" 凍結為 maintenance-only；只修安全／正確性問題。若需把共用計算搬到 shared/domain 層，可以做，但必須保持 "ui_v2" 行為不變，且搬遷批需獨立稽核。
- NG-2 附題：BL-0532 缺資料字樣統一也套用到 "ui_v2"，視為正確性修正。
- NG-3：New UI2 先以獨立 Streamlit Preview App 平行驗收，通過後才切正式預設。
- NG-4：保留既有狀態符號、顏色語意與正式用字；layout、component、spacing、information hierarchy 重新建立。
- NG-5：純 presentation / layout DEC 由 New UI2 各頁 wireframe 重新核准；涉及資料語意、投資語意、規則語意者保留。任何被 amendment 的既有 DEC 必須逐條列出，不得默默覆蓋。

Streamlit 維持現行內部決定，不更換 framework。

---

正式 Streamlit 顯示規則

這條新增為正式裁示：

«正式 Streamlit 對使用者只顯示目前最新正式 UI。»

New UI2 驗收通過並正式切換後：

- 正式 Streamlit 只顯示 New UI2 / "ui_v3"
- Old UI 不出現在正式導覽
- "ui_v2" 不出現在正式導覽
- 不提供一般使用者舊 UI 切換入口
- 不提供首頁上的「舊版／新版」切換器
- 正式使用者不需要知道 repo 裡仍保留舊 UI

但 repo 中：

- Old UI 保留，read-only
- "ui_v2" 保留，maintenance-only / rollback candidate
- 不先刪除
- 不再做新功能或新版面

也就是：

保留程式 ≠ 對使用者公開。

---

Preview / Cutover

正式切換前：

- New UI2 可有獨立 Preview App
- 正式 App 仍維持目前版本
- Preview 不影響正式使用者

當 New UI2 驗收完成後：

1. 將正式 Streamlit entrypoint 切到 "ui_v3"
2. 正式 UI 只顯示 New UI2
3. "ui_v2" 與 Old UI 從正式 navigation / entrypoint 隱藏
4. repo 內仍保留 rollback 能力
5. rollback 僅為維運用途，不做一般使用者切換功能

如果正式 Streamlit URL 可以在不破壞部署與 OAuth / redirect contract 的情況下維持原網址，優先維持原正式網址。

不要為了 New UI2 任意改正式 URL。

---

Final UI UI-1～UI-15

除已裁示且不重問的 UI-11 外，其餘全部採總管推薦 A。

UI-12 明確裁示

我同意 amendment "DEC-2026-10-30-01" D1。

新版 🌍「市場與趨勢」首頁主圖方向改為：

TAIEX vs S&P 500 比較圖

並由 New UI2 🌍 頁 wireframe 重新核准最終呈現。

同時核准 UI-12 其餘推薦 A，包括：

- 💼 容許帶
- 依據卡數量上限
- 基金比較最多 3 檔
- 其他 §13 已列出的數量／版面限制

歸一化基準依 UI-13 採 100。

---

UI-15

UI-15 採 A：

- 💼 我的資產擁有 Dividend Calendar
- ⚙️ 設定擁有 notification preference / delivery health / audit
- 正式日期優先
- deterministic estimate 只作 fallback
- 月底下月 LINE summary 保留
- semantic date change 可作未來 notification
- directional / action LINE 不恢復
- Old UI calendar 只參考 logic / capability，不搬 UI

另外正式處理：

"docs/v2/44" 目前 "pay_date"「實際入帳日」與 Final Contract 的

Payment Date ≠ 實際銀行／平台入帳日

之間的語意衝突。

不得直接偷改 frozen 44。

請建立正式 amendment / backlog，將：

- Payment Date
- Estimated Bank Credit Window

清楚拆開。

---

Durable Persistence

本次裁示必須同步：

- "PROJECT_RULES.md"（若此正式 Streamlit 顯示規則屬永久治理）
- "docs/DECISIONS.md"
- "docs/BACKLOG.md"
- "docs/HANDOFF.md"
- "docs/v2/79"
- "docs/v2/80"
- 必要 amendment backlog
- evidence
- audit checklist

尤其新增一條可稽核要求：

«New UI2 cutover 後，正式 Streamlit navigation / entrypoint 不得再暴露 Old UI 或 "ui_v2"。»

需有測試或可驗證證據。

---

舊 UI 的正式邊界

再次明確：

Old UI

- 不修改
- 不新增功能
- 不公開到正式 Streamlit
- 只作 logic / capability reference

"ui_v2"

- maintenance-only
- 不新增新版面
- 不公開到正式 Streamlit
- 只保留 rollback / reuse 能力

"ui_v3"

- New UI2
- 未來唯一正式 Presentation Layer
- 正式 cutover 後唯一出現在 Streamlit 對使用者的 UI

---

Git 歷史違規

#1115～#1119 squash / AI trailer 的既有歷史不改寫。

保持揭露即可。

從 #1120 起：

- 使用一般 merge commit
- 禁止 AI co-author
- 禁止 session URL trailer

---

Model / Effort Change Gate

完成：

- 本次裁示 Durable Persistence
- independent audit
- CI
- GitHub final verification
- New UI2 architecture frozen
- Reuse Matrix frozen
- migration boundary frozen
- 五頁 wireframe 成為正式 implementation input

之後只回報：

«🟡 Model / Effort Change Gate：New UI2 架構與 Final UI Contract 已完成裁示與凍結。下一階段為 "ui_v3" presentation implementation，建議切換 Claude Sonnet 5.5 + Medium。»

然後立即停下。

不得先開始 "ui_v3" production。

等我明確回覆：

「已切換／可以開始」

才開始下一階段。
```

## 落地位置

- `docs/DECISIONS.md`：`DEC-2026-11-02-05`（NG-1～NG-5 全採 A＋Streamlit 維持；architecture、Reuse Matrix、migration boundary 凍結；五頁 wireframe 為正式 implementation input）、`DEC-2026-11-02-06`（永久：正式 Streamlit 只顯示目前最新正式 UI；Preview／Cutover；三代 UI 邊界）、`DEC-2026-11-02-07`（UI-1～UI-15：UI-11 不重問、其餘採 A；UI-12 amend `DEC-2026-10-30-01` D1；UI-13＝100；UI-15＝A；44 `pay_date` 語意衝突另開 amendment）、`DEC-2026-11-02-08`（Git merge 規範重申）；被 amend／resolve 的既有 DEC 就地加指標。
- `PROJECT_RULES.md`：0.5 索引一列、13.2 永久規則與稽核檢查項、第 10 節重申指標。
- `docs/BACKLOG.md`：BL-0531（UI-1～UI-15 已裁示）、BL-0532（ui_v2 一併套用）、BL-0533（NG-1～NG-5 已裁示）、BL-0534（44 `pay_date` 語意 amendment）、BL-0535（cutover navigation／entrypoint 暴露守衛）、BL-0536（`ui_v3` presentation implementation）。
- `docs/HANDOFF.md`：Resume Checkpoint 最上方一則、第 0 節接手檢查一行。
- `docs/v2/79_final_ui_contract_freeze.md`、`docs/v2/80_new_ui2_architecture_proposal.md`：同批另組落盤（不在本檔描述範圍）。
