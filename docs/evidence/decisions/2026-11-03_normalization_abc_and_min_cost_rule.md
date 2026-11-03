# 客戶 2026-11-03 🌍 歸一化三題（A2／B2／C2）裁示＋後續實作順序＋永久規則「多元解法與最小成本決策規則」（逐字）

- **來源**：客戶 2026-11-03 在本對話中的訊息，經總管逐字轉存為文字檔；執行組照抄，未見客戶對話本身。
- **性質**：正式裁示（formal ruling：🌍 歸一化 (A) A2、(B) B2、(C) C2 與後續實作順序）＋永久治理規則（多元解法與最小成本決策規則）。本檔只存原文，不含執行組讀法；圍欄為轉存的客戶原文，字句未改（原文中的模型名屬客戶原文，保留）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-04`（歸一化三題與實作順序）、`DEC-2026-11-03-05`（永久規則）。
- **存檔日期**：2026-11-03
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。
- **落地位置**：
  - `docs/DECISIONS.md` `DEC-2026-11-03-04`、`DEC-2026-11-03-05`（`DEC-2026-11-03-03` 讀法 (a) 加指標）
  - `PROJECT_RULES.md` 9.2（永久規則）與 0.5 索引列
  - `docs/BACKLOG.md` BL-0536-H1 待客戶確認 (A)(B)(C) 改已裁示；新增子項 H1b；H2／H3 註記
  - `docs/v2/81_new_ui2_wireframe_01_market.md` 第 9 節 (A)(B)(C) 加已裁示指標
  - `docs/HANDOFF.md` 頂部 checkpoint 與第 0 節接手檢查

```text
裁示如下。

一、🌍 歸一化三題

(A)：採 A2

期間起點落在週末／休市日，不應僅因該日沒有市場觀測值就判為歷史不足。

規則：

- 以所選期間的比較視窗為基準
- 起點若為非交易／無觀測日，使用視窗內第一個可供兩序列共同比較的有效觀測日
- 該共同有效日作為 normalized base = 100
- 這不是新增 ±N 日 tolerance
- 不得自行建立「容忍幾天」規則
- 若真正缺乏所選期間應有的有效歷史覆蓋，仍必須回 "insufficient"
- 不新增交易日曆 dependency，除非未來另有正式需求

請把「週末／休市正常無觀測」與「真正歷史不足」分開。

(B)：採 B2

其中一條歷史不足時：

- 歷史足夠的序列仍顯示
- 不足的序列明確標示「資料不足」
- 不得因此讓整張 Primary 圖消失
- 不得把不足序列補值、補 0 或假造基準

(C)：採 C2

其中一條因停更而無共同基準日時：

- 仍可顯示可用的另一條序列
- 舊序列必須標示真正原因，例如「無共同基準日／資料不足」，不得假裝成正常比較
- 不得把兩條各自不同日期設成 100 後冒充可比較

B2／C2 修改 formula contract，完成後須重新做公式等級獨立稽核。

---

二、允許後續 🌍 實作順序

正式允許：

1. H2：期間漲跌＋freshness 共用層
2. H3：normalized chart disclosure
3. 🌍 production-like rendering 只進 Preview App

其中：

- H2 的期間漲跌必須與圖表使用一致的基準與資料視窗
- H3 至少揭露：基準日、基準值 100、資料頻率、缺值／缺序列處理
- Preview rendering 可開始於 H2/H3 完成、測試與獨立稽核通過之後

尚未授權

- 不得切換正式 Streamlit entrypoint
- 不得 cutover
- 不得讓 Old UI／"ui_v2" 出現在正式 navigation
- 不得把 Preview App 當正式 App
- VIX 在 Primary 顯示時 Secondary VIX 是否讓位，仍不是正式裁示；碰到前另送 Decision Gate

---

三、現在先補永久治理規則

目前 #1126 已完成，下一個 implementation batch 尚未開始。

因此請先開一個獨立、極小、docs-first governance batch／PR，把以下永久規則完整 Durable Persistence；不要和 H2 formula changes 混成同一個 PR。

多元解法與最小成本決策規則

遇到技術、資料、UI、架構、流程、除錯或實作問題時，不得預設只有單一路徑，也不得在同一路徑持續原地試錯。

1. 實作前先比較方案

原則上至少評估 3 個可行方案。

若客觀上不足 3 個：

- 說明原因
- 不得為了湊數製造假方案

至少比較：

- 正確性與資料／投資語意風險
- 實作／修復速度
- Token 與 Model 成本
- 修改範圍
- 回歸風險
- 可逆性
- 是否可沿用既有 module / service / data / tests / workflow
- 是否需要新增 dependency
- 失敗後 fallback / downgrade path

2. 預設決策優先序

預設依序選：

正確性足夠且風險低
→ 完成最快
→ Token／成本最低
→ 修改範圍最小
→ 可逆性最高

採 Minimum-Cost Correct Path。

不是追求最少程式碼，而是：

«足夠正確＋最低總成本。»

3. 禁止 sunk-cost 原地試錯

若發生任一情況，立即重新比較 A／B／C：

- 同一路徑重複失敗
- 第二次修正仍未解決核心問題
- 修改範圍持續擴大
- 開始波及無關模組
- 需要新增不必要 dependency
- workaround 持續堆疊
- Token／時間已明顯高於替代方案
- 已出現更簡單且同樣正確的方案
- rollback／regression 風險持續升高

不得以「已經做到這裡」作為繼續方案 A 的理由。

4. 專案 AI 的主動責任

專案 AI 必須主動比客戶更早尋找：

- 可重用的現有模組
- wrapper / adapter 而非重寫
- fake / shadow / preview 驗證
- presentation-only 解法
- 不新增 dependency 的方法
- 小範圍止血方案
- B／C fallback

不能等客戶先提出替代方案。

5. 與 Model / Effort 聯動

方案評估同時包含：

- Model
- Mode
- Effort

採既有 Minimum Sufficient Effort。

高階模型不是預設答案；只有公式、資料語意、Risk Cap、身份／來源、跨模組 contract 等風險需要時才升級。

6. 不增加碎碎念

三方案比較預設是內部決策流程。

安全、可逆、無須客戶裁示時：

- 內部比較後直接走最佳方案
- 不必把三方案全部回報

只有：

- Decision Gate
- 重大架構差異
- 不可逆
- 成本差異顯著
- 需新增來源／dependency
- 需客戶裁示

才對外呈現方案比較。

不得因這條規則增加不必要 Token。

---

四、Durable Persistence

本治理規則至少同步檢查：

- "PROJECT_RULES.md"
- "docs/DECISIONS.md"
- "docs/BACKLOG.md"
- "docs/HANDOFF.md"
- 適用的 audit checklist / constitution tests
- 必要 evidence

不能只寫其中一個檔案。

規則未完成 Durable Persistence，就不能宣告 governance batch 完成。

完成 governance PR、獨立檢查、CI、final GitHub verification 後，再開始 H2。

---

Model / Mode / Effort

目前維持：

- Model：Claude Opus 5.5
- Mode：Formula / data semantics + governance
- Effort：High

理由：治理文件本身只需 Medium，但目前接續 H2 仍是公式等級；為避免先降 Sonnet 再立刻升 Opus造成額外 Gate、上下文與 Token 成本，本次小型 governance batch 可沿用現有 Opus + High。

Governance PR 必須保持 docs/governance scope，不能因模型較強而擴大工作。

完成後直接依最新 GitHub SSOT 接 H2；若工作性質改變到適合降低 Model / Effort，再依既有硬停手規則先送 Change Gate。
```
