# 客戶 2026-11-03 New UI2 規則 A～I：D、G 兩段原文節錄（逐字；非全文）

- **來源**：客戶 2026-11-03 指示，經總管轉交的原文**節錄**；本檔只含 **D、G 兩段**，**不是 A～I 全文**（其餘段落見同日要點轉述檔 `2026-11-03_canonical_convergence_and_new_ui2_rules.md`，那份不是逐字）。執行組未見客戶對話本身。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-08`。**落地位置**：`docs/v2/80` 第 16.2、16.3 節；`PROJECT_RULES.md` 0.4 索引。
- **存檔日期**：2026-11-03。**遮蔽**：無作者或老師姓名，無 secret。

```text
D. 資料健康度集中到 ⚙️：正式方向：完整資料診斷不再散落在 🌍／💼／🔍 主頁。主頁只保留與判讀直接相關的 freshness／source 摘要。完整診斷集中：⚙️ 設定 → 資料健康度。涵蓋所有正式資料類別：市場、基金、持倉、配息、匯率、利率、景氣、其他正式來源。每項可有：status、是否取得、source、as_of、retrieved_at、freshness、Missing／failed reason、source health。三層呈現：1. 一般使用者摘要 2. provenance／date／source 3. developer diagnostics（預設收合）

G. UI ViewModel ≠ OneBrain Decision Digest：Data／Sources → Validation／Normalization → Domain／Deterministic Logic → Complete Evidence Layer → 分流：UI ViewModel（給人看：精簡、圖表優先、key evidence、mobile-first）／Decision Digest／OneBrain Context（給 OneBrain：完整正式 evidence、所有已取得 objective facts、Missing、provenance、source、as_of、retrieved_at、freshness、deterministic calculations、rule results、holdings、allocation、dividend/events、market indicators、counter-evidence、cross-page context）。最新正式規則：『UI 沒顯示的正式資料，OneBrain 仍可讀。』『OneBrain 可讀的資料，不代表 UI 必須全部顯示。』
```
