# 客戶 2026-10-31 V7 正式裁示（💼 我的資產：採 A、H6 維持只評估一部分、F-5 字樣核准、文字線框 Gate）（逐字）

- **來源**：客戶 2026-10-31 對話中的正式裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-31-01`（客戶裁示）。落地：`docs/v2/76_assets_v7_layout_a_wireframe.md`（A 的最小文字線框，待客戶審批）、`docs/v2/74_assets_d3_formula_gate.md`（檔頭追加一條客戶裁示記錄）、`docs/BACKLOG.md` BL-0525（子項 BL-0525-D3 列尾）、`docs/HANDOFF.md`（唯一接手點）。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行；單一換行結尾）。
- **存檔日期**：2026-10-31
- **圍欄內文 sha256**：`2a62a84a1446ee0882ac87ed6e865f3ffb2fb08ffc56858cc0d0a77f0ff0d5c3`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。
- **撞字**：無。

```text
V7 正式裁示

採 A。

頁級 P3 狀態容器保留在第一眼位置，並取代頁面中 HLD-0／ALO-0 兩枚燈的重複 presentation。

目的：

1. 維持「整頁先看到結論」。
2. 讓 390px Primary Visual 回到首屏。
3. 消除同一事實在頁面重複顯示。
4. 不修改既有 Visual Budget / V7 驗收標準。

不採 B。
不要把頁級狀態移到 Primary 後面。

不採 C。
不得為了解決本次 layout 問題而放寬 V7 或修改既有 Mobile Visual Budget。

---

A 的重要邊界

這只是 presentation de-duplication。

不是刪除 HLD-0／ALO-0 domain blocks。

必須保留：

- HLD-0 / ALO-0 Domain Block Identity
- 原始 rule result
- "_page_class"
- "_state"
- "_tone"
- reason / missing reason
- provenance
- Decision Digest mapping
- 原始 deterministic semantics

正式原則：

«Domain Block Identity ≠ Presentation Instance.»

頁級 P3 可以成為 HLD-0／ALO-0 在「💼 我的資產」合併頁上的主要 presentation，但不能因此刪除或改寫兩個 domain blocks。

單獨 HLD／ALO view 或其他正式 consumer 若仍需要原始 block，行為不得被破壞。

---

區段內資訊保全

移除區段內重複燈時，不得順便移除只有原位置才有的功能。

逐項盤點並保留：

- 「前往 Sheets」按鈕
- Missing / omitted rows 附行
- error reason
- provenance / detail
- 任何只存在 HLD-0／ALO-0 presentation 下的必要入口

如果某功能不能合理搬入頁級容器：

可以在原區段保留「功能／證據入口」，但不要再重複完整狀態句。

不要為了 A 新增第二套狀態詞或新 domain vocabulary。

---

H6 正式裁示

H6 逐檔取數失敗維持「持股只評估一部分」級，不升成整區「取數失敗」。

理由：

H6 是部分資料失敗，不等於整個持股區無法取得。

頁級分類維持：

PARTIAL / 只評估一部分

但必須繼續清楚外露既有：

⛔ ‹基金／資料類› 取數失敗

因此：

- partial failure ≠ whole-area failure
- 不能隱藏 ⛔ reason
- 不能把部分失敗寫成無偏離／正常

只有 HLD 整區無法形成有效結果時才進 β 最上層「取數失敗」。

---

F-5 字樣

正式核准沿用：

- "持股："
- "配置："
- "持股與配置："

不另造新詞。

---

文字線框 Gate

依既有規則，先出 A 的最小文字線框，不直接改 production layout。

線框至少同時畫：

Desktop

頁級狀態
→ summary strip
→ 主判讀
→ Primary
→ Secondary
→ 持股明細 / 配置明細

390px

必須證明第一屏仍能看到：

- 必要的頁級狀態
- compact summary
- Primary Visual 的有效可辨識部分

並說明：

- HLD-0 原位置改成什麼
- ALO-0 原位置改成什麼
- Sheets CTA 放哪裡
- Missing/error 附行放哪裡
- 哪些只是 presentation 搬移、哪些完全不動

線框通過後才實作。

---

驗收

實作後至少重跑：

1. P3 7×6 真實模型矩陣
2. 7×7 aggregation matrix
3. 客戶指定 10 情境
4. H6 partial failure 專測
5. HLD / ALO 原 block semantics 不變守衛
6. Sheets CTA 不遺失
7. omitted rows / Missing reason 不遺失
8. desktop Visual Fidelity
9. 390px V7
10. relevant regression tests
11. CI

不得為通過 V7 縮到不可讀、隱藏核心資訊或修改 V7 threshold。

Model / Effort

維持：

Claude Sonnet 5.5 + Medium

這仍屬已裁示架構內的 UI / presentation 調整，不需升 Opus。

若實作過程發現必須改：

- domain semantics
- formula / precedence
- Risk Cap
- Decision Digest semantics
- Visual Budget contract

立即停在新 Decision Gate，不要自行擴 scope。

維持 Silent Autonomous Cruise / No Progress Narration Gate。
```
