# 客戶 2026-11-01 正式裁示（找基金搜尋入口、Canonical Fund Identity、Source ≠ Identity、Batch E 第一批範圍）（逐字）

- **來源**：客戶 2026-11-01 在對話中的正式指示，經總管逐字轉存為文字檔；執行組未見客戶對話本身，只依派工單抄入。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；原文中的模型名與強度字樣屬客戶原文逐字，保留。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-01-01`。落地：`docs/BACKLOG.md`（BL-0397／BL-0521／BL-0525／BL-0488／BL-0411 補記，新增 BL-0530）、`docs/HANDOFF.md`（唯一接手點）、`docs/v2/78_fund_search_batch_e_inventory_wireframe.md`（現況盤點與最小 wireframe）。
- **存檔日期**：2026-11-01
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
一、正式產品裁示：基金搜尋入口
新版基金儀表板的「找基金」頁，只保留兩種正式使用者搜尋方式：
1. MoneyDJ 基金代碼：主要入口；例如 "ACTI97"；客戶實際使用上通常會直接輸入 MoneyDJ code，而不是基金全名
2. ISIN：保留正式搜尋入口；作為 alternate lookup key / cross-reference
取消使用者端：基金名稱搜尋；模糊名稱搜尋；FundClear 搜尋入口；TDCC 搜尋入口；其他非正式代碼搜尋入口；多來源搜尋模式切換；AI 猜基金／AI 模糊配對。
不要為了「方便」自行把上述入口加回來。

二、Canonical Fund Identity
基金層 canonical identity 仍以 MoneyDJ 基金代碼為核心。例如 "ACTI97"。
未來以下功能都應盡量對到同一 canonical fund identity：找基金；基金基本資料；基金績效；持股基金識別；持股比例／基金占比；基金比較；候選基金；後續 AI Decision Digest 的基金 referent。
ISIN 是正式 alternate lookup key，不建立第二套 fund identity。
流程應為：ISIN → identity resolution → 對應同一 canonical fund identity
若 ISIN 無法可靠對應 MoneyDJ code：不猜；不用基金名稱模糊補；不用 AI 猜測；顯示既有 Missing／無法判定語意；保留 provenance 與 unresolved 狀態。

三、Fund Identity 與 Holding / Product Identity 必須分離
MoneyDJ fund identity 與保單商品碼、平台碼、通路碼、holding row identity、policy/product identity 必須分離。
例如類似 "ACDD01-EQTAL005" 不能直接假設整串就是基金代碼，也不能建立通用 "split("-")[0]" 規則去猜 MoneyDJ code。
外部持股資料若只提供 product / platform code：必須經正式 identity mapping 才能得到 MoneyDJ canonical fund code。無法可靠 mapping：保持 Unknown / Missing / 無法判定。不得因為字串長得像就自動配對。

四、持股比例／基金占比
未來持股比例、基金占比與基金層彙總，應以 resolved canonical fund identity 為基礎。
也就是：holding/product identity → identity mapping → MoneyDJ canonical fund identity → fund-level aggregation
不要直接用基金名稱、顯示文字、平台商品碼、通路碼、UI label 作基金比例合併鍵。
若部分 holding 無法完成 identity mapping：不得把它偷偷排除後宣稱整體比例完整；必須保留 missing / omitted / unresolved disclosure；不得補成 0；不得當作已知基金合併。
這部分維持既有 BL-0411／Missing semantics／presentation disclosure 原則。

五、其他資料來源的角色
本裁示取消的是使用者搜尋入口與基金身份入口，不是禁止後端使用其他既有可靠資料來源。
例如 TDCC、FundClear、MoneyDJ、其他已正式核准來源，仍可分別負責：客觀資料取得；驗證；cross-check；classification；provenance；補充資料。
但不得因為使用不同 source，就建立第二套基金 identity。統一原則：Source ≠ Identity。資料來源可以多個；基金 canonical identity 只能有一致的解析規則。

六、Data ≠ AI
維持既有架構：Raw Sources → Validation / Identity Resolution → Canonical Data → Domain Calculations → Decision Digest → One AI Brain
AI 不得負責：猜 MoneyDJ code；猜 ISIN 對應；猜基金名稱；猜 platform code 對應；補 missing identity；把 unresolved 當作 resolved。
Identity resolution 必須是 deterministic / traceable 的資料層責任。

七、Batch E：🔍 找基金
接下來正式進入 BL-0525 Batch E：🔍 找基金。但不要直接開始 production implementation。
第一批先做：
A. 現況盤點：盤點現有 ui_v2/exp；services/fund_search.py；MoneyDJ code lookup；ISIN 能力；TDCC / FundClear 現有用途；candidate pool／選股池／觀察清單；Fund Identity mapping；holding → fund mapping；相關 tests / guards / SSOT。確認哪些：可 reuse；要 replace；與本次裁示衝突；只是舊 UI／舊語意；尚缺正式 contract。不要新增第四套／第五套搜尋來源。
B. 最小 Wireframe：先出 🔍 找基金最小 wireframe。核心使用流程：輸入 MoneyDJ Code 或 ISIN → 找到基金 → 顯示核心基金資料 → 比較／後續操作。第一屏應簡潔：搜尋輸入；MoneyDJ Code / ISIN 自動辨識或最簡單可理解的輸入方式；找到的基金名稱；MoneyDJ canonical code；ISIN（若有）；基金類別／必要基本資料；1 個主要比較視覺或結果區；明確 Missing／來源／as_of。不要第一批就做成大型 Screener。

八、這一批不要做
不要自行啟動：AI ranking；星等；Top N；AI score；自動推薦買哪一檔；新正式篩選公式；新 Risk Cap；新資料來源；OneBrain runtime；Claude API production；候選清單寫入；觀察清單寫入；Google Sheet 新 writer；舊 UI 大規模搬運。
BL-0511 ranking model 仍維持 deferred，除非另走正式 Formula / Decision Gate。

九、Decision Gate 條件
如果盤點發現本裁示需要改：canonical fund identity contract；MoneyDJ / ISIN precedence；NAV mapping；holding/product identity contract；source precedence；formal aggregation formula；Risk Cap；Decision Digest semantics；OAuth / credential architecture——停在 Decision Gate，不自行改。

十、GitHub Durable Memory
這次裁示不能只留在聊天。請將正式結果落盤到適當位置：docs/DECISIONS.md；docs/BACKLOG.md；docs/HANDOFF.md；Fund Identity / Batch E 正式規格或 wireframe；必要的 evidence decision file。若既有 SSOT 已涵蓋部分內容，採 amendment / pointer，不建立第二套憲法。舊裁示若被本次 supersede：依 repo 慣例保留歷史並明確標示 superseded，不要直接抹掉歷史。

十一、工作模式
Model / Effort：Claude Sonnet 5.5 + Medium。這一輪先做盤點、衝突分析、wireframe 與 durable record。只有正式碰到 identity semantics、source precedence、formula、Risk Cap、Decision Digest semantic conflict 才走 Model / Effort Change Gate，暫升 Claude Opus 5.5 + High；Gate 收斂後立即降回。維持 Silent Autonomous Cruise / No Progress Narration。只在：真 Decision Gate、真 blocker、Model / Effort Change Gate、整批完成時一次回報。
```
