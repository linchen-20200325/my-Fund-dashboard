# 客戶 2026-10-30 Batch C wireframe 核准裁示 D1～D7 與額外 UI Guardrail（逐字）

- **來源**：客戶 2026-10-30 對話中的正式裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-30-01`（客戶裁示）。落地：`docs/v2/72_mkt_wireframe_batch_c.md`（標「已核准」）、`docs/v2/71_presentation_contract_migration.md` Batch C 列、`docs/BACKLOG.md` BL-0525／BL-0517、`docs/HANDOFF.md`、`ui_v2/mkt/**`、`tests/visual_fidelity/layout_checks.py`。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行；單一換行結尾）。
- **存檔日期**：2026-10-30
- **圍欄內文 sha256**：`7c76499b706535b9e66a426728cb46d0eeb179eec39c618ebabd7e5a2fc9b086`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
先重新做 GitHub Verification Gate，再依最新 main 執行。

我方最新核對：

- main："7ce28478f2adda59870113cbdd08c00d23e8913a"
- #1107 已合併
- Open / Draft PR：0

Batch C wireframe 已核准，以下為正式裁示。

D1｜五個序列呈現

採 A。

一張 Primary Visual＋序列切換：

- TAIEX
- S&P 500
- VIX
- US10Y
- US2Y

預設：

TAIEX

但請加一條硬限制：

«Primary Visual 是完整趨勢閱讀入口；Secondary Visual 只負責快速環境掃描，不得把同一組完整資訊再複製一次。»

不得形成：

主圖已顯示完整序列
＋下面又放五張完整縮小版圖。

---

D2｜BL-0517 三張新圖

採 P2。

將：

- credit spread
- term spread
- policy rate

歸入一個 Secondary Visual：

「利率與信用」

內部以切換方式呈現。

硬限制：

- 同時間只顯示一個主要序列
- 不得三張小圖並排常駐
- chips 只保留必要數值／期間變化
- 判定文字仍集中於依據卡／local explanation
- 不得在圖卡與依據卡重複同一大段判讀

注意：

這個裁示批准的是位置與呈現模式。

若其中任何序列目前尚未有正式核准資料來源／production data：

仍維持 Missing / placeholder。

不得因 wireframe 核准就順便新增資料來源。

---

D3｜頁首主判讀與日期

採 C1 + (i)。

頁首：

只呈現資料事實層級的一句話。

在完整市場綜合判定尚未建立前：

必須清楚保持：

暫無完整市場綜合判定

不得偽裝成完整 AI 市場結論。

不放 page-level date。

資料日期只放在對應圖卡／主圖 chip。

避免不同市場資料日期不一致時，頁首日期造成錯誤暗示。

---

D4｜EPS × PE Missing

採 β。

沒有資料時：

併入「尚未取得」群組。

不要為了 Missing 本身在首屏建立獨立瘦卡。

原因：

Missing 必須誠實存在，
但「存在」不等於「一定要佔第一屏」。

Decision Digest 資訊仍完整保留。

---

D5｜結論燈

採一行 chip。

不要保留大型整條燈卡。

維持既有正式狀態語意與字樣。

例如仍使用：

"◇ 資料未備"

不要新增：

"n 項資料未備"

除非未來另有正式 wording Decision。

硬限制：

«Status chip 是狀態，不是 Primary Visual。»

頁面視覺焦點仍必須是圖。

---

D6｜390px 手機 Secondary Visual

採外露三條緊湊列。

但這裡要特別收斂：

手機上的三個 Secondary Visual 不得直接縮成三張桌機圖。

請使用：

- sparkline
- mini trend
- compact row
- 小型狀態圖

高度以 wireframe 的緊湊規格為主。

每列只回答：

- 現在值
- 方向／期間變化
- 必要狀態

要看完整趨勢時，再進 Primary Visual 切換。

如果 390px screenshot 顯示仍然太擠：

優先降低 secondary visual detail，
不是把 Primary Visual 壓小。

---

D7｜依據卡位置

採 E2。

順序：

1. 頁首 status chip
2. 一句主判讀
3. Primary Visual
4. Secondary Visual
5. 依據卡
6. details / Missing / provenance

依據卡不要求塞進第一屏。

這裡正式確認：

«第一屏不需要為了符合舊藍圖「3～5 張摘要卡」而重新堆卡片。»

新版 Presentation Contract 的：

圖表 > 數字 > 短句 > 長文字

優先於舊 presentation-only 密度。

但不要因此刪除依據內容。

---

本次額外 UI Guardrail

這個請一起落 GitHub。

第一屏目標

使用者進入 🌍 市場與趨勢後：

第一眼

「現在市場有沒有異常／需要注意？」

第二眼

「主要市場趨勢長怎樣？」

第三眼

「為什麼這樣顯示、資料從哪來？」

如果實際 screenshot 無法呈現這個順序：

Visual Fidelity FAIL。

---

避免圖表牆

正式要求：

桌機核心視覺上限仍是：

- 1 Primary
- 最多 3 Secondary

但「最多 3」不是 KPI。

如果實際 screenshot 顯示 2 個 Secondary 就足夠：

可以少於 3。

不得為了「用滿額度」硬塞第三張。

---

Batch C Production Implementation

以上 D1～D7 核准後，可以開始正式 Batch C UI implementation。

本批範圍：

- 🌍 市場與趨勢
- presentation primitives 實際接入
- 對應 T1 / T6 / T9 / T13 等必要 test migration
- desktop + 390px Visual Fidelity
- CI fixture screenshot

不得：

- 新增 production data source
- 修改資料語意
- 修改 identity / NAV
- 修改 Risk Cap
- 實作 One AI Brain
- 實作完整 AI 投資總結
- 順便改其他頁
- 順便處理舊 "ui/"

---

Cloud Visual Fidelity

Cloud 層目前仍因 execution environment network policy 無法取得，照既有裁示處理：

- CI fixture screenshot 照跑
- 不得冒充 production-like confirmation
- 不因此阻塞機械式 implementation
- Cloud 可用時再補正式確認

---

Durable Memory

D1～D7 以及上述新增 Guardrail 必須正式落 GitHub。

不能只留在對話。

完成 Batch C 時，HANDOFF 要能讓新 session 明確知道：

- 🌍 頁正式 visual hierarchy
- D1～D7 裁示
- 尚未完成的 Cloud confirmation
- BL-0517 哪些只是 layout approval、哪些仍缺資料
- 下一個唯一安全接手點

---

模型 / Effort

本批維持：

Claude Sonnet 5.5
Effort：Medium

只有遇到新的：

- SSOT 衝突
- 資料語意
- 新資料來源
- Risk Cap
- Decision Digest semantics
- One AI Brain architecture

才走 Model / Effort Change Gate，再考慮 Opus 5.5 + High。

恢復 Silent Autonomous Cruise。

只有真 Decision Gate、真 blocker、Model/Effort Gate 或 Batch C 完整完成才回報。
```
