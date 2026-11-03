# 80 第 17.2／17.4 節舊字樣搬出（歷史；2026-11-03，DEC-2026-11-03-11）

> ⛔ **NOT CURRENT — Historical evidence only — not current contract.** 本檔是客戶 2026-11-03 Shell 驗收裁示（`DEC-2026-11-03-11`）落地時，從 `docs/v2/80` 現行區**逐字**搬出的舊內容：第 17.4 節「候選字樣與推薦」整張 pending 字樣表（含標題行）、第 17.2 節 Status Bar 舊條文、第 17.2 節「首屏預算讀法」舊條文（含「此讀法未經客戶確認」的原句）。基準 commit 為 `875b1955`（#1134 合併點），每區塊的基準記在 `source` 的 `@` 後；sha256 與位元組數記在 `MOVED-BEGIN` 標記與 `README.md` 清冊，由 `tests/test_canonical_rule_consistency.py` 機械比對。**這些舊字樣在現行區是整段取代、沒有以劃線形式保留**；取代關係見 `docs/DECISIONS.md` `DEC-2026-11-03-11` 的 supersedes 欄。現行規則看 `docs/v2/80` 第 17 節與 `shared/ui_semantics/rules.py::APPROVED_WORDING`。

## S1｜`section-17.4-candidate-wording-table`

<!-- MOVED-BEGIN id=S1 source=docs/v2/80_new_ui2_architecture_proposal.md#section-17.4-candidate-wording-table@875b1955 sha256=a283f085e0103bbe9a16f7a7bf7b91fec02541c0f46cd22fdb9ed96843cd162a bytes=1301 -->
### 17.4 候選字樣與推薦（Shell 新字樣全部為 pending；定字後搬進 `shared/ui_semantics/rules.py`）

| 鍵 | 目前字樣 | 來源 | 推薦 |
|---|---|---|---|
| `shell_app_title` | 基金投資儀表板 | 客戶要求列舉 | 採用 |
| `shell_nav_short_*` | 市場／資產／找基金／AI／設定 | 客戶要求列舉 | 採用 |
| `shell_nav_soon` | 開發中 | 客戶要求範例 | 採用；🤖 若覺得「開發中」不貼切可改「尚未開放」 |
| `shell_preview_tag`／`shell_preview_tip` | PREVIEW／Preview｜非正式頁面 | 客戶要求列舉 | 採用（標籤顯示、提示放 tooltip） |
| `shell_updated`／`shell_updated_label` | 更新：{時間}／最後更新時間 | 客戶要求範例／列舉 | 採用 |
| `shell_data_status_label` | 資料狀態 | 客戶要求列舉 | 採用 |
| `shell_refresh_cta` | 更新資料 | 客戶要求列舉 | 採用 |
| `shell_refresh_unavailable` | 預覽版尚未開放更新資料 | 執行組暫擬 | 採用或客戶改字 |
| `shell_status_partial`／`_none`／`_counts`／`_failed_note` | 部分資料缺失（{n}／{m} 項取得）等 | 執行組暫擬 | 採用；全取得時維持不寫「正常」，除非客戶明示要放寬 `ok` 無字規則 |
| `shell_nav_aria` | 主要導覽 | 執行組暫擬 | 採用 |
<!-- MOVED-END id=S1 -->

## S2｜`section-17.2-first-screen-budget-bullet`

<!-- MOVED-BEGIN id=S2 source=docs/v2/80_new_ui2_architecture_proposal.md#section-17.2-first-screen-budget-bullet@875b1955 sha256=d1e48014cb6044fe3a00e18552c3e5ac7fca6ebfeb62e2aa5f1e45d0f32e910e bytes=391 -->
- **首屏預算讀法**【I】：Status Bar 是 Shell 的一行純文字（不是 chip、不是頁級核心數字），與導覽同屬 chrome，不計入 44 之十九其一之一的「頁級 chip＋核心數字 ≤5」；頁本體仍是 3 chip＋2 數字＝5（量測見 17.5）。此讀法未經客戶確認；若客戶認為 Status Bar 該計入，會變成 6，需回到 Decision Gate。
<!-- MOVED-END id=S2 -->

## S3｜`section-17.2-status-bar-bullet`

<!-- MOVED-BEGIN id=S3 source=docs/v2/80_new_ui2_architecture_proposal.md#section-17.2-status-bar-bullet@875b1955 sha256=adc6f6b68a9c6aaa0be7d52d474ed0657223fb281488a0d907e5e34bdc220ba4 bytes=657 -->
- **Top／Status Bar**：主區頂端一行，內容為「PREVIEW」（滑過顯示「Preview｜非正式頁面」）＋（有缺資料時）資料狀態＋更新時間。資料狀態與時間只來自 `MarketPageModel.statuses` 的既有取得狀態與 `fetched_at`（取得時間，不是資料日）；沒有取得時間就寫規則表的缺資料 chip，不推估。⚠️ **資料全部取得時不寫「正常」「資料齊」**：`rules.entry("ok")` 刻意無字（44 頁首資料狀態行規則），客戶要求範例中的「● 主要資料正常」因此未採用，列入待定字清單。長說明（原頁首 Preview 橫幅）移到頁尾。
<!-- MOVED-END id=S3 -->
