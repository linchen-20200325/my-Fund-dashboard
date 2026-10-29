# 客戶 2026-10-29 DG-2 最終整合裁示：Sheet 基金代號＝MoneyDJ 命名空間、基金身份與持倉身份分開（逐字）

- **來源**：客戶 2026-10-29 對話中的 DG-2 最終整合裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-29-01`（客戶裁示；取代 #1098 之後提出的 Sheet 代碼解析 A／B／C 問題）。落地：`docs/v2/70_dg2_canonical_identity_proposal.md` 第 15 節、`shared/fund_identity.py`、`services/fund_identity.py`、`services/fund_identity_shadow.py`、`tests/test_fund_identity_dg2.py`、`docs/BACKLOG.md` BL-0521。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行）。
- **存檔日期**：2026-10-29
- **圍欄內文 sha256**：`4791a666c6babdea4cd35baa234b0a7e5f02ee6829dcc9ba76ff74710a047972`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
基金儀表板 DG-2：最終整合裁示與後續安全修正

本提示語取代本輪所有尚未送出的 DG-2 補充提示語，請勿把先前草稿當成額外任務或重複裁示。

0. GitHub Verification Gate

先重新查核 "linchen-20200325/my-Fund-dashboard"：

- main SHA
- Open／Draft PR
- #1098 merge commit 與實際 diff
- Fast／Schema／Slow CI
- "PROJECT_RULES.md"、"docs/DECISIONS.md"、"docs/BACKLOG.md"、"docs/HANDOFF.md"
- "docs/v2/69_cross_view_consistency_spec.md"
- "docs/v2/70_dg2_canonical_identity_proposal.md"

本次已知基準：main "84a956b5"，PR #1098 已合併；若最新 GitHub 有變化，以 GitHub 為準。

已完成的 Shadow Resolver 不要重做。

1. 客戶正式確認：Sheet 基金代碼全部來自 MoneyDJ

客戶明確確認：

Google Sheet「基金代號」欄現在及未來均使用 MoneyDJ 基本基金代碼。

例如：

- "ACTI71"
- "JFZN3"
- "ACCP138"
- "ACDD01"
- "ACDD19"
- "TLZF9"
- "ACTI94"
- "ALBT8"

因此該欄位的來源命名空間固定為 "MoneyDJ"，不再需要逐筆猜測是否為 FundClear。

這項裁示只適用於客戶確認的 Sheet 基金代號欄，不得推廣成整個 repo 的所有 "code"、所有 Sheet 或所有外部 API 都屬 MoneyDJ。

未來新增基金也沿用 MoneyDJ 基本代碼。

不改 Sheet schema，不要求客戶補 ISIN。

2. 基金身份與保單持倉身份分開

同一基金可以同時出現在多張保單中。

例如多張保單都持有 "TLZF9"，應共用同一 MoneyDJ 基金身份，但保單持倉紀錄必須保持獨立。

概念上：

- Fund identity："moneydj:TLZF9"
- Holding identity：既有保單／持倉識別鍵

"moneydj:TLZF9" 是目標契約的示意，不代表核准立即變更現有儲存鍵。

不得因基金身份收斂而合併不同保單的投入金額、單位數、交易、損益或持倉紀錄。

3. MoneyDJ 平台網址與後綴

客戶確認：

- "TLZF9" → 基本基金代碼 "TLZF9"
- "TLZF9-AL001" → 基本代碼 "TLZF9"，後綴為通路資訊
- "TLZF9-24A7" → 基本代碼 "TLZF9"，後綴為通路資訊
- "ACDD01-EQTAL005" → 客戶確認基本基金代碼為 "ACDD01"

以上是客戶提供的業務語意；各完整網址的實際來源、後綴對應與 NAV 等價性仍須由程式或來源證據確認。

對已確認為 MoneyDJ 的輸入，採 MoneyDJ 專屬解析規則；不得把通用 "split("-")[0]" 套用到其他資料來源。

例如 FundClear：

- "AGIF-HT5"
- "AGIF-HTG"

不能依 MoneyDJ 通路後綴規則拆成 "AGIF"。

FundClear、MoneyDJ、Morningstar 等代碼屬不同命名空間。

4. Sheet 代碼解析的最終決策

原先 A／B／C 三方案不再原樣適用。

最終採 C+，加上客戶已確認的 Sheet MoneyDJ 來源契約：

1. Sheet 指定基金代號欄固定為 MoneyDJ namespace。
2. Sheet 基本代碼不需要後綴剝除。
3. MoneyDJ 平台 URL 先解析 URL／頁型／來源，再依已驗證 mapping 辨識通路後綴。
4. 未知來源或未知後綴不得盲目剝除。
5. 不同 namespace 不得只靠字串相似就合併。
6. 未來若 Sheet 出現不符合基本代碼契約的輸入，應標記資料驗證問題，不得靜默截斷、剝除或改寫原值。

不得將「Sheet 都是 MoneyDJ」解釋成「所有帶 "-" 的代碼都可以剝除」。

5. MoneyDJ 境內／境外頁型

已知 repo 存在：

- "yp010000"
- "yp010001"
- "_DOMESTIC_PREFIXES"
- "parse_moneydj_input"
- "canonicalize_moneydj_url"
- "fund_orchestration" 的頁型推斷

請針對既有程式與測試確認境內／境外對應關係、URL 頁型優先序、代碼前綴推斷的適用範圍。

不要把客戶先前記憶中的 "A00001 / A00002" 當成規格，也不需要為此額外擴大研究。

原始 URL 有明確頁型時，應優先保留可驗證的來源證據；裸碼頁型推斷若不可靠，標示 Unknown 或使用經驗證 mapping，不得猜測。

6. 舊 UI 邏輯復用

PR #1098 已完成舊 UI targeted audit，"docs/v2/70" §12 有 reuse matrix。

請先使用既有 26 項分類結果，不要重做整份 audit。

僅對以下尚未解決的承重路徑補充 targeted verification：

- "ui/tab2"、"ui/tab3"
- 舊單一基金頁
- 舊持股／portfolio
- "repositories/fund/sources.py"
- "repositories/fund/fund_orchestration.py"
- "repositories/policy/v1.py"
- "services/v2_tables/fund_keys.py"
- MoneyDJ URL、頁型、mapping、NAV、cache caller

舊 UI 已驗證的正確邏輯優先復用；有缺陷的邏輯修正，不因其為舊 UI 就沿用。

分類仍採：

"REUSE / ADAPT / LEGACY_COMPAT / REJECT / UNVERIFIED"

不要改動舊 UI 畫面。

7. FundClear 與其他外部來源

客戶目前不使用 FundClear 代碼作為基金輸入。

因此：

- 不直接把 Sheet MoneyDJ code 當成 FundClear code。
- 不自動產生 FundClear 對照。
- 不要求客戶提供 FundClear code 或 ISIN。
- FundClear 若未來作為補充資料來源，必須有經驗證的跨來源 mapping。
- 沒有 mapping 時，顯示無法判定，不得假裝查無基金或自行猜測。

本輪不需要額外建立跨來源基金代碼資料庫。

8. Identity 與 NAV 必須分開

Identity resolver 回答「是哪一檔基金」。

NAV resolver 回答「指定基金、類股、日期與幣別的淨值是多少」。

同一基本基金代碼不代表可以無條件混用不同：

- 日期
- 幣別
- share class
- 配息／累積型
- 避險型態
- NAV series

未知屬性不得猜測，也不得當成已確認相同。

跨頁一致性原則：

Same verified instrument / share class + same metric + same as-of + same currency = same canonical value.

基金身份、NAV、保單持倉估值、報酬率計算必須保持分層。

9. 網路 NAV 查證

針對 MoneyDJ：

- "TLZF9"
- "TLZF9-AL001"
- "TLZF9-24A7"
- "ACDD01"
- "ACDD01-EQTAL005"

在網路可用時，定向查證實際頁面與基金名稱、幣別、NAV 日期、NAV 值及資料來源。

優先驗證同一基金、同一類股、同一日期、同一幣別的 NAV 是否一致。

若無法取得資料，記錄 "UNVERIFIED"，不要虛構數值。

若不同來源 NAV 不一致：

- 記錄 source conflict
- 檢查頁型、更新時間、類股、幣別與解析器
- 不因數值不同就自動建立第二檔基金
- 也不得強迫把不同 NAV series 合併

網路查證不能成功時，不得因此卡住其他安全工作。

10. 修正 PR #1098 回報的已知解析缺陷

已知四類問題：

A. T7／tab3 貼上 URL 變成 "HTTPS"

修正 URL 與裸碼的識別順序，不得先把整個 URL 當成基金代碼大寫處理。

B. "fetch_nav"／"fetch_div" 把平台後綴當基金代碼重試

只在有來源證據的情況下解析通路後綴，禁止把 "AL001" 之類的後綴單獨當基金代碼。

C. policy URL query／fragment 解析錯誤

處理 "#fragment"、"area=TW&a="、參數順序及大小寫。

D. 小寫 URL cache key 錯誤

先確認該 cache helper 是否有 production caller；若無，不要為未使用的 helper 擴大重構。補足有價值的 targeted tests，確保不會產生空 key 或不同基金碰撞。

上述問題先判斷影響範圍。

如果能確定是局部解析 bug、修法唯一、相容性可驗證，可在安全範圍內修復。

若會改變正式 NAV 選源、身份歸併、持倉鍵或估值結果，停在 Decision Gate，不得自行擴大授權。

11. Shadow Mode

保留 #1098 已完成的 Shadow Resolver，不重做。

本輪可補：

- MoneyDJ Sheet namespace 的測試
- "ACDD01-EQTAL005" 的有證據解析案例
- FundClear 類股不可被誤剝的反例
- 境內／境外頁型測試
- URL parsing regression tests
- 同基金多保單的 identity separation tests
- 缺幣別、缺類股、缺 ISIN 的 Unknown 測試

Shadow flag 維持預設關閉。

本輪不授權開啟正式環境 flag，也不授權 production NAV resolver 接管。

若需開啟 Shadow 以蒐集真實資料，先提出明確執行環境、唯讀／日誌範圍、隱私遮罩、回退方式與驗收門檻。

12. 本輪禁止順帶修改

不得擴大修改：

- Sheet schema
- NAV source precedence
- "get_latest_nav" 的選源語意
- Morningstar "results[0]" 的正式採用行為
- valuation methodology
- FX cutoff
- return formulas
- 正式基金頁／持股頁 UI
- One AI Brain
- Risk Cap
- 凍結的 vNext UI SSOT

這些各自依既有 Backlog／Decision Gate 處理。

13. 測試、稽核與治理

- 先 characterization，再修復。
- 保留既有通過的測試與 strict xfail 語意。
- 不得為了綠燈刪測試、放寬 assertion 或把真錯誤當環境問題。
- 資料身份與契約語意變更至少一組真正獨立稽核。
- 同一稽核組可複驗修正；除非真高風險，不增加第二組。
- 每批最多三項實質安全工作。
- 同一批必要文件與測試一起收斂，不製造多餘 PR。
- 不為每個小 bug 建立新的 Decision Gate。
- "PROJECT_RULES"、"DECISIONS"、"BACKLOG"、"HANDOFF" 只做必要同步。
- 交接內容必須進 GitHub，不依賴 ChatGPT 記憶。

資料層與 AI 分析層保持分離。

缺值不填 0、不猜 USD、不視為 neutral 或 safe。

14. 執行順序與停手條件

先完成：

1. GitHub Gate 與現行契約核對。
2. 更新必要的 DG-2 客戶裁示與測試。
3. 定向查證舊 UI／MoneyDJ 頁型／NAV。
4. 在安全範圍修復已知解析 bug。
5. Targeted tests、必要獨立稽核、CI。
6. PR 安全合併與 GitHub 文件交接。

若任何項目需要新資料來源、不可逆 migration、正式估值語意改變、跨來源身份強制合併、正式 flag 啟用或新規格裁示，立即停止該項，其他獨立安全工作可繼續。

維持既有 Auto-Ship 授權範圍，不因本提示語擴張權限。

15. 靜默自主巡航

除以下情況外，完全靜默：

- 完整 Batch 結束
- 真正需要客戶裁示
- Model／Effort Change Gate
- 無法安全繼續的真阻塞

禁止逐步回報讀檔、測試中、稽核中、PR 已開、等待 CI。

最終只回報：

- main SHA
- PR／CI／稽核結果
- MoneyDJ 身份契約完成情況
- 已修缺陷與未修原因
- NAV 網路驗證結果
- 真正剩餘 Decision Gate
- 下一個唯一安全接手點

16. 模型與 Effort

- 身份契約、跨來源驗證、安全邊界：Opus 5.5／High
- 定向讀碼、局部 bug 修復、測試、文件：Sonnet 5.5／Medium
- 純文件整理可使用 Low。

遵守 Minimum Sufficient Effort，不得整批固定使用最高成本模型。

現在開始依上述範圍靜默執行；不要再詢問已由客戶確認的 MoneyDJ Sheet 來源問題。
```
