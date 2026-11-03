# 客戶 2026-11-03 裁示：Shell 驗收（Status Bar 讀法、降級首屏 ≤5、Shell 正式定字、仍待驗證清單）（逐字）

- **來源**：客戶 2026-11-03 對 #1134（全站 Navigation Shell＋H5）的驗收裁示，經總管於派工單內逐字轉交；執行組照抄，未見客戶對話本身（repo 內無另一份原文可做逐位元組比對）。
- **性質**：正式裁示（presentation／wording；不改 formula、data semantics、資料來源、門檻、狀態判定或投資語意；不修訂 frozen 44）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-11`
- **存檔日期**：2026-11-03
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。
- **落地位置**：`shared/ui_semantics/rules.py`（`APPROVED_WORDING` 的 Shell 字樣）；`ui_v3/pages/chrome.py`、`ui_v3/pages/mkt.py`、`ui_v3/shell/nav.py`、`ui_v3/viewmodels/preview_wording.py`；`tests/ui_v3/`；`docs/v2/80` 第 17 節；`docs/v2/81` 第 10.2 節；`docs/BACKLOG.md` BL-0536；`docs/HANDOFF.md`。

```text
一、Status Bar：採現有 Shell chrome 讀法——純文字 PREVIEW 與更新時間，不計入 frozen 44 的頁級 chip＋核心數字 ≤5。若 Status Bar 顯示額外資料狀態 chip 或核心數字，不能僅以位於 Shell 為由排除計數。不放寬 frozen 44。
二、全取得狀態：維持不顯示「正常／資料齊」（資料取得成功不等於 freshness、可靠性、投資判讀或安全狀態全部正常）；不得自創「主要資料正常」等綜合結論。
三、降級情境首屏：不接受 7 chip＋2 數字作為最終第一屏。在不修改 frozen 44、不隱藏重要 Missing、不改變資料語意的前提下，將第一屏控制在既有 ≤5 預算。要求：頁級必要狀態與失敗警示保留；多個逐序列狀態可改為一個明確的摘要呈現；各序列 Missing／failure／unavailable 的詳細原因仍完整保留於圖卡下方或可展開的診斷內容；未來 ⚙️ 資料健康度承接全量健康明細；不得合併不同資料狀態為「正常」；不得把失敗與尚未設定視為相同事件；若無法同時滿足預算及必要的可見警示，先送 Decision Gate（停手回報），不得自行改 44。請以至少三個方案依 Minimum-Cost Correct Path（PROJECT_RULES 9.2）比較，選最小回歸方案。
四、Shell 正式定字（採用，落盤；正式用字只保留一份 SSOT，移除或退役對應 preview-only 舊定義，不建立第二套字樣表）：基金投資儀表板／市場、資產、找基金、AI、設定（短標）／開發中／🤖：尚未開放／PREVIEW／Preview｜非正式頁面／更新：{時間}／資料狀態／最後更新時間／更新資料／預覽版尚未開放更新資料／部分資料未取得（{n}／{m} 項已取得）／其中 {n} 項取數失敗／{n}／{m} 項已取得／主要導覽。與現行暫擬不同處：「部分資料缺失（{n}／{m} 項取得）」→「部分資料未取得（{n}／{m} 項已取得）」；「{n}／{m} 項取得」→「{n}／{m} 項已取得」；🤖 的未開放標籤用「尚未開放」（其餘三頁維持「開發中」）。計數分母必須是明確、已登錄且本次檢查涵蓋的資料項目；不得推廣為未檢查的全系統健康結論（Status Bar／狀態區文字不得暗示涵蓋範圍超過實際檢查的五條主要序列）。
五、仍待驗證（保留 BACKLOG，不得宣稱已通過）：iOS／Android 實機、Safari、深色模式、Yahoo／FRED 真實連線、Streamlit 升版後導覽相容性、安全的資料更新入口。不得為完成 Shell 而開始新 refresh pipeline。
六、順序：Shell 定字與降級首屏收尾批（本批）→ 之後才是 💼 線框（本批不做）。仍遵守 Old UI read-only、ui_v2 maintenance-only、frozen 44 不動、不切正式入口、不做 OneBrain Phase 7。若涉及資料語意、公式、正式規則門檻變更 → 停手送 Model／Effort Gate。
```
