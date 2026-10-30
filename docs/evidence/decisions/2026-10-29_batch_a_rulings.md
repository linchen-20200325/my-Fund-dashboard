# 客戶 2026-10-29 Batch A 啟動裁示：BL-0526 採方案 C、Cloud Preview URL、Sonnet 5.5／Medium 起始點（逐字）

- **來源**：客戶 2026-10-29 對話中的正式裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。圍欄內的預覽站網址是公開 URL，不是 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-29-07`（客戶裁示）。落地：`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之二十其一第 2 條行尾加註、`docs/v2/67_ai_action_vocabulary.md` 第 6 節、`docs/v2/71_presentation_contract_migration.md` 第六、七、九節、`docs/BACKLOG.md` BL-0525／BL-0526、`docs/HANDOFF.md`、`PROJECT_RULES.md` 模型原則指標、`tests/visual_fidelity/config.py`（Cloud Preview URL 的程式可讀單一位置）。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行；單一換行結尾）。
- **存檔日期**：2026-10-29
- **圍欄內文 sha256**：`60c794c2525dce9e550ee101259f1f020743aa71a704cb21fbf4c659b0f4dc54`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
先做 GitHub Verification Gate，再依最新實況執行。

我方最新獨立核對：

- main："5e0550834f2b81b166c78bff50ed5e67b6e11ad0"
- #1105 已合併
- Open / Draft PR：0

第一階段視為完成。

以下三個 Gate 正式裁示，不需要再次詢問。

1. BL-0526｜AI 投資總結入口

採方案 C。

正式定義：

🤖 AI 投資總結

它是：

«全站唯一完整整合型 AI Decision Output。»

來源只能是：

Canonical Data
→ Rules / Indicators / Risk Cap
→ Decision Digest
→ One AI Brain
→ AI 投資總結

不得由 UI 文字拼湊。

---

各頁 AI 呈現

🌍 市場與趨勢
💼 我的資產
🔍 找基金

每頁最多只能存在：

- 一個 local AI summary
  或
- 一個「查看 AI 判斷」鏡像入口

不得再建立另一套 AI Brain。

Local summary 必須：

- 來自同一份 Decision Digest
- 只是對應 slice
- 與 🤖 AI 投資總結結論一致
- 可以查看依據
- 不得自行重新呼叫另一套 prompt 得到不同結論

---

🤖 頁的責任

只回答：

1. 現在怎麼看？
2. 主要原因？
3. 最大風險？
4. 是否需要行動？

正式輸出維持：

- 市場：一句話
- 我的資產／配置：一句話
- 持股：一句話
- 候選基金：一句話
- 主要風險：1～3 點
- 本期行動：最多 3 項
- 每一項都有「查看依據」

不要把它做成另一個資料牆。

不要重複其他頁全部圖表。

---

導覽

Phase 7 實作 One AI Brain 時，正式加入：

"🤖 AI 投資總結"

作為頂層入口。

目標 navigation：

1. 🌍 市場與趨勢
2. 💼 我的資產
3. 🔍 找基金
4. 🤖 AI 投資總結
5. ⚙️ 設定

注意：

這個裁示只批准 IA / entry。

現在 Batch A 不要提前實作 AI Brain。

先將 BL-0526 的正式裁示落盤，更新對應：

- DECISIONS
- 44 / IA SSOT（若需要最小 amendment）
- 67 One AI Brain contract
- BACKLOG
- HANDOFF

保留 supersession history。

---

2. Visual Fidelity｜Cloud Preview

B 線預覽站：

"https://my-fund-dashboard-3atbdymetmxyi2fbkxujtv.streamlit.app/"

把這個 URL 登記到適合的正式測試／Visual Fidelity 設定或文件中。

不要把 URL 只留在聊天。

但不要將 credential、token、secret 寫進 repo。

---

驗收分兩層

A. CI deterministic screenshot

Batch A 建立：

- Playwright / Chromium
- deterministic fixtures
- desktop screenshot
- 390px mobile screenshot
- artifact upload
- 基本 visual regression / layout checks

這是 automated safety net。

B. Streamlit Cloud screenshot

從上述 B 線預覽站取得：

- desktop
- 390px mobile

這是 production-like Visual Fidelity confirmation。

必須明確標示：

«CI fixture screenshot ≠ production-like Cloud screenshot»

不能互相冒充。

---

網路限制處理

如果你目前 execution environment 無法存取該 Streamlit Cloud 網域：

不得因此停止 Batch A。

Batch A 照常：

- 建工具鏈
- 建 fixture screenshot
- 建 artifact
- 建 Visual Fidelity checks

並只記錄：

"production-like Cloud capture blocked by current environment network policy"

不要每個 Batch 重複要求客戶提供 URL。

URL 已提供。

等環境允許時再補正式 Cloud confirmation。

---

3. Model / Effort Change Gate

批准。

從 BL-0525 Batch A 起切換：

Claude Sonnet 5.5
Effort：Medium

適用範圍：

- presentation helpers
- tests migration
- screenshot tooling
- shared card
- chips
- expander
- Missing presentation
- mechanical UI migration
- routing / layout 等明確實作

不要繼續使用 Opus + High 做這些機械性工作。

---

升級回 Opus + High 的條件

若遇到：

- 新 SSOT 衝突
- frozen contract 無法判讀
- data semantics
- identity
- NAV
- Risk Cap
- Decision Digest semantics
- One AI Brain architecture
- 新 Data Source Decision
- 需要推翻既有正式裁示

才走 Model / Effort Change Gate。

先通知，再升級。

不要自行把整個後續工作永久切回 High。

---

現在開始 BL-0525 Batch A

Batch A 只做已凍結契約下的機械遷移。

優先：

1. B 線 presentation helpers / test contract migration
2. CI screenshot / Visual Fidelity automated safety net
3. 必要的 shared presentation primitives

仍遵守：

≤3 real work items / batch。

不要趁 Batch A：

- 改資料來源
- 改資料語意
- 改 identity
- 改 NAV
- 改 Risk Cap
- 實作 One AI Brain
- 實作完整 🤖 頁
- 處理 BL-0528 舊線 AI
- 順手重構舊 "ui/"

---

UI 硬性驗收原則再次確認

Presentation Simplification must never reduce AI Decision Context.

以及：

Visual Priority does not mean Visual Quantity.

每頁原則：

- 1 Primary Visual
- ≤3 Secondary Visual
- 第一屏 ≤5 個核心 metrics / chips
- 1 句主要判讀
- detailed provenance / formula / limits / Missing reason 下沉

不得把：

文字牆 → 圖表牆。

---

GitHub Durable Memory

本次三個裁示：

- BL-0526 方案 C
- Cloud Preview URL
- Sonnet 5.5 + Medium 起始點

都必須正式落 GitHub。

Conversation 不是 SSOT。

完成 Batch A 時，新對話只讀 GitHub 必須能知道：

- AI 入口裁示
- URL / Visual Fidelity 方法
- 目前模型切換原則
- Batch A 做了什麼
- 下一個唯一 handoff point

否則交接不算完成。

---

回報規則

恢復 Silent Autonomous Cruise。

不要回報：

- 開始工作
- agent 已派出
- PR 已開
- CI 等待中
- audit 等待中
- screenshot 工具正在寫
- docs 正在同步

只在：

1. 真 Decision Gate
2. 真 blocker
3. 需要 Model / Effort Change
4. Batch A 完整完成

時一次回報。

如果 Batch A：

- targeted tests 綠
- regression 綠
- CI 綠
- audit 無 must-fix
- 無 unresolved thread
- 無新 Decision Gate

依既有 Auto-Ship 規則處理。
```
