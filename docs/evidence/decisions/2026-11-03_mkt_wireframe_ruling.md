# 客戶 2026-11-03 🌍 市場與趨勢線框裁示（Q1～Q5）＋Prior-Ruling／Discussion Persistence Audit 指示（逐字）

- **來源**：客戶 2026-11-03 在本對話中的訊息，經總管逐字轉存為文字檔；執行組照抄，未見客戶對話本身。
- **性質**：正式裁示（formal ruling）。本檔只存原文，不含執行組讀法；圍欄為轉存的客戶原文，字句未改（原文中的模型名屬客戶原文，保留）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-01`（客戶裁示）。
- **存檔日期**：2026-11-03
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。
- **落地位置**：
  - `docs/DECISIONS.md` `DEC-2026-11-03-01`
  - `docs/v2/81_new_ui2_wireframe_01_market.md`（狀態、第 1 節、第 3 節、第 5 節、第 7 節就地更新）
  - `docs/BACKLOG.md` BL-0536 G1 與後續登記
  - `docs/HANDOFF.md` 頂部 checkpoint
  - `docs/DECISIONS.md` `DEC-2026-11-03-02`（同批補錄第二節與缺漏補齊）
  - `docs/BACKLOG.md`、`PROJECT_RULES.md`、`docs/v2/67`、`docs/v2/79`、`docs/v2/80` 的指標與補齊處（見 `DEC-2026-11-03-02`）

```text
🌍 市場與趨勢線框裁示如下：

- Q1：A
- Q2-a：A
- Q2-b：A
- Q2-c：A
- Q3：A
- Q4：A
- Q5：B

Q5 補充理由

首屏仍需遵守既有 frozen 44 的資訊密度限制。

因此：

- 首屏保留一枚「資料新鮮度」chip
- 不在首屏額外顯示「延遲 N 日」
- 日期／經過天數仍只放在圖卡
- 不因這次線框去放寬 frozen 44 的「核心數字＋chip」上限
- freshness threshold 尚未正式裁示前，不自行創造「新／舊／正常／過期」等判定

---

🌍 已核准方向

1. 沒有正式市場規則時：

   - 市場狀態＝"⬜ 無法判定"
   - 是否需注意＝"⬜ 無法判定"
   - 兩者可共用一枚 chip
   - 不得因沒有規則而省略，避免被誤讀為「沒有風險」

2. TAIEX vs S&P 500：

   - 共同交易日第一個有效共同點＝100
   - 視窗起點取兩條可比較範圍中較晚者
   - 歷史不足就明確顯示不足，不偷偷縮短定義
   - 不得用兩條各自不同日期的首筆都設為 100

3. 終點：

   - 各序列畫到自己的最後觀測日
   - 但所有 value / date / return 顯示必須清楚對應自身資料日，不能讓使用者以為兩者最後一天相同

4. 缺一條序列：

   - 另一條仍可顯示
   - 明確標示缺少哪一條
   - 不把整張 Primary 圖直接消失

5. Primary：

   - 保留比較／VIX／美 10Y／美 2Y 的檢視切換
   - 移除重複的 S&P 500 Secondary 卡
   - 不移除既有 VIX／美債完整查看能力

6. 首屏重要依據：

   - 使用 TAIEX／S&P 500 期間漲跌等客觀觀測值
   - 不把仍大量 Missing 的依據卡提前到首屏
   - 依據卡維持 Secondary 之後，保留既有 D7 段序

---

既有裁示／先前討論缺漏補齊稽核

這次不要只落 Q1～Q5。

請額外做一次 Prior-Ruling / Discussion Persistence Audit：

逐項比對最近 New UI2 相關已裁示與已明確同意事項，確認是否已完整同步到：

- "PROJECT_RULES.md"
- "docs/DECISIONS.md"
- "docs/BACKLOG.md"
- "docs/HANDOFF.md"
- "docs/v2/79"
- "docs/v2/80"
- "docs/v2/81"
- 對應 evidence
- audit checklist / tests

至少重驗以下既有永久方向沒有遺漏：

- New UI2 / "ui_v3" 是唯一正式新 Presentation Layer
- Old UI 永久 read-only，不修改
- "ui_v2" maintenance-only，不做新版面
- 正式 Streamlit cutover 後只顯示 "ui_v3"
- Old UI／"ui_v2" 不出現在正式 navigation / entrypoint
- repo 仍保留 rollback 能力，但不提供一般使用者切換舊版
- Data layer 與 AI reasoning layer 分離
- Missing 不得補 0／neutral／HOLD／safe
- provenance / freshness / source / as_of contract
- mobile-first
- 首屏需回答：目前狀態／是否需注意／重要依據／資料新鮮度
- TAIEX vs S&P 500，normalized base = 100
- UI-1～UI-15 已裁示內容
- Dividend Calendar / notification ownership
- Payment Date vs Estimated Bank Credit Window amendment backlog
- Silent Autonomous Cruise / No Progress Narration
- Model / Mode / Effort Change Gate 必須先回報、立即停手
- 所有新規則、裁示、待辦、稽核與接手點必須 Durable Persistence 到 GitHub

若發現「聊天中已正式裁示，但 canonical GitHub 尚未完整落盤」：

- 本批可安全補文件者，補齊
- 若會改 frozen spec、production semantics 或需要新裁示，登記 BACKLOG / Decision Gate，不得自行決定

不得用聊天記憶當 SSOT。

---

下一步

先完成：

1. 本次裁示 durable persistence
2. prior-ruling gap audit
3. independent audit
4. CI
5. GitHub final verification

然後再評估 🌍 production implementation 所需 Model / Mode / Effort。

如果因 Q2 歸一化公式需要升級 Model / Effort：
先送 Model / Effort Change Gate，立即停手。

不得先開始 production rendering。

---

目前建議模型／模式／理解力：

- Model：Claude Sonnet 5.5
- Mode：UI / UX + governance
- Effort：Medium

但若下一步開始實作 Q2 歸一化公式與視窗對齊：
建議重新評估是否升至 Claude Opus 5.5 + High，並依硬停手規則先送 Gate。
```

---

## 同批補錄：先前對話中已明示、尚無逐字落盤的指示

> 本節四段由總管自客戶 2026-11-02 的對話訊息轉存，逐字；執行組未見客戶對話本身。日期與情境行是轉存者的標示，不是客戶原話。這些指示先前只以轉述存在於 `docs/DECISIONS.md` `DEC-2026-11-02-09` 與 BL-0536，本節補上逐字（Prior-Ruling Audit 缺漏補齊）。

### (a') 2026-11-02 Model／Effort Change Gate 放行時的維持條件

情境：客戶回覆「已切換／可以開始」（`DEC-2026-11-02-09`）時所列的維持條件。

```text
維持：Silent Autonomous Cruise / No Progress Narration；所有新規則、決策、待辦、稽核要求與接手點都必須 Durable Persistence 到 GitHub；Old UI 不動；"ui_v2" maintenance-only，不做新版面；正式 cutover 前先走 Preview App；正式 cutover 後 Streamlit 對使用者只顯示最新 "ui_v3"；若下一階段需要再次切 Model / Mode / Effort，先回報 Gate 並立即停下，等我切換完成後再繼續
```

### (b) 2026-11-02 放行 🌍 wireframe 批時的 Gate 後靜默重申

```text
另外重申：Gate 已送出後，不需要再重複回報「沒有東西要 push／我已停手／等你回覆」。一次 Gate 回報後就保持靜默。
```

### (c) 2026-11-02 同一則訊息：New UI2 各頁線框 Gate 順序

```text
請依 GitHub 最新 SSOT 進行 New UI2 各頁線框 Gate，順序：1. 🌍 市場與趨勢 2. 💼 我的資產 3. 🔍 找基金 4. ⚙️ 設定。🤖 AI 投資總結仍依既有 Phase / Gate，不提前實作。先從 🌍 開始；在我核准該頁線框前，不要寫該頁 production rendering。
```

### (d) 2026-11-02 批 2 放行時的稽核要求

情境：客戶列出批 2 的工作清單（PORT 領域計算到共用層／保持 ui_v2 行為完全不變／golden tests 不變／建立正式 presentation rules table／建立 design token naming／每批至少一組真正獨立稽核）；以下為清單中的稽核一項。

```text
每批至少一組真正獨立稽核
```
