# 客戶 2026-11-03 裁示：🌍 市場與趨勢正式字樣、首屏欄位、工程資訊不外漏（逐字）

- **來源**：客戶 2026-11-03 裁示，經總管於派工單內逐字轉交；執行組照抄，未見客戶對話本身（repo 內無另一份原文可做逐位元組比對）。
- **性質**：正式裁示（presentation wording；不改資料、來源、公式、門檻、狀態判定或投資語意）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-11-03-07`
- **存檔日期**：2026-11-03
- **依據規則**：`PROJECT_RULES.md` 12.1 新裁示同批 GitHub 落盤、12.2 GitHub Discussion Persistence Gate。
- **落地位置**：`shared/ui_semantics/rules.py`（`APPROVED_WORDING`）；`ui_v3/viewmodels/preview_wording.py`；`ui_v3/pages/mkt.py`；`docs/v2/81_new_ui2_wireframe_01_market.md`（第 10 節）；`docs/BACKLOG.md` BL-0536；`docs/HANDOFF.md`。

```text
正式字樣（客戶 2026-11-03）：
| 項 | 正式字樣 |
| 資料不足 | 「資料不足」 |
| 整張圖無可畫資料 | 「此圖目前沒有可畫的資料」 |
| 歸一化揭露 | 「基準日 {日}＝100；頻率：日｜缺值不補、斷線」 |
| 檢視標籤 | 比較／VIX／美10Y／美2Y |
| 首屏欄位 | 市場狀態／是否需注意／重要依據／資料新鮮度 |
| 主判讀 | 「暫無完整市場綜合判定（尚未建立正式綜合判定規則）」 |
| 資料日 | 「{序列} 資料日 YYYY-MM-DD（經過 N 日）」 |
| 單序列 fallback | 「目前僅顯示可用序列；另一序列{原因}，暫不進行比較。」 |
| 其他沿用 | 「原因未明」「來源資料無法使用」「沒有觀測值」 |

補充：
- 歸一化揭露的「頻率：日」比先前暫用的「頻率 日」多了冒號。
- 檢視標籤是「美10Y」「美2Y」，無空格。
- 主判讀一般 UI 不得再出現英文 aggregation rule。
- 資料日的日期格式維持 YYYY-MM-DD。
- 單序列 fallback 不得暗示仍有雙序列可比性。
- Missing 語意不變：不補 0、不補 safe／neutral／HOLD；unavailable ≠ neutral；not evaluated ≠ safe。

另兩項要求：
- 首屏「市場狀態」與「是否需注意」不要混成一項；mobile-first 下重新檢查資訊層級（遵守首屏資訊密度，不放寬 frozen 44；若超過上限須停下回報）。
- 一般 UI 不得外漏工程內部資訊：環境變數名、exception class／訊息、Python symbol、內部 reason code、模組路徑、traceback、provider 實作細節；技術細節只留在 log／diagnostics／evidence。
```
