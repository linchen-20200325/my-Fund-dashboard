# 客戶 2026-11-03 指示：Canonical Rule Convergence／Latest-Rule-Only 與 New UI2 最新有效規則 A～I（要點轉述）

- **來源**：客戶 2026-11-03 指示，經總管於派工單內**摘要轉交**；執行組未見客戶對話本身。**性質＝要點轉述，不是逐字**（`docs/DECISIONS.md` 第二節 provenance：要點轉述）。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-08`。**存檔日期**：2026-11-03。
- **遮蔽**：無作者或老師姓名，無 secret。

## 一、收斂指示（摘要）

1. 規則狀態分類 CURRENT／SUPERSEDED／HISTORICAL EVIDENCE ONLY／CONFLICT-NEEDS-GATE；現行區只留 CURRENT，互斥規則不得同時在現行區。
2. 已被最新裁示明確取代的舊條文從現行規則區移除（舊五頁 IA、舊 page naming、資產配置／我的持股雙 top-level、被新 Missing wording 取代的舊字樣、舊 Preview 暫定字樣、已裁示卻仍寫待裁示、被正式裁示取代的執行組舊推論、多檔重複正文）。
3. 歷史不可直接消滅：歷史 DEC、原始 evidence、merged PR evidence、audit history、migration history、rationale 保留，標 SUPERSEDED 或 Historical evidence only，移出現行區；禁止 rewrite Git history、禁止刪稽核證據。
4. SSOT：每條正式規則只有一個主要權威位置，其他地方只做 index／cross-reference／summary。
5. frozen／append-only 文件不直接破壞：先收斂 canonical active docs，在合法 amendment／索引位置標明 successor；不確定能不能刪就不刪、走 Gate。
6. Prior-Ruling Gap＋Conflict Audit：Missing／Duplicate／Conflict／Superseded／Stale wording 全部收斂。

## 二、New UI2 最新有效規則 A～I（摘要）

- **A** 人類 UI 簡單但不失判讀：簡潔、mobile-first、圖表優先、低資訊噪音；第一屏回答「狀態／是否需注意／關鍵證據」；資訊順序 ① 狀態／結論 ② 是否需注意／正式 action state ③ 主要圖表 ④ 關鍵 evidence ⑤ 必要數字 ⑥ 詳細來源／raw data／diagnostics 收合。
- **B** Chart-first：不得為美觀創造不存在語意、硬疊不同單位、未核准雙軸、圖表自行做 domain calculation、用圖形掩蓋 Missing。
- **C** Chart SPEC：標的、period、benchmark／normalized base、base date、unit、frequency、latest data date、Missing handling、comparison rule（依適用）；例「SPEC｜基準日 2025-11-03＝100｜日頻｜缺值不補」。
- **D** 資料健康度集中到 ⚙️：完整診斷不散落主頁；主頁只留與判讀直接相關的 freshness／source 摘要；涵蓋市場、基金、持倉、配息、匯率、利率、景氣與其他正式來源；三層呈現（一般摘要／provenance／developer diagnostics 預設收合）。
- **E** 工程資訊（env var、Python exception、traceback、internal reason code、module path）不得進一般 UI。
- **F** Presentation Compression≠Information Loss。
- **G** UI ViewModel≠OneBrain Decision Digest（共用 Complete Evidence Layer 分流）。
- **H** OneBrain 讀完整 Decision Digest；未來輸出六項（系統狀態、AI 投資總結、主要依據、最強反證、風險／不確定性、Evidence trace）；禁止造 objective facts、回寫 canonical data、補 Missing、fake probability／Risk Cap／action state；Phase 7 前不正式啟用 🤖。
- **I** 五頁 IA：🌍 市場與趨勢／💼 我的資產／🔍 找基金／🤖 AI 投資總結／⚙️ 設定；舊「資產配置」「我的持股」不得作 current top-level page。

## 三、落地位置

A、B、E、F → `PROJECT_RULES.md` 13.5；I → 13.2 第 1 點；C、D、G、H → `docs/v2/80` 第 16 節；索引 → `PROJECT_RULES.md` 0.4。
