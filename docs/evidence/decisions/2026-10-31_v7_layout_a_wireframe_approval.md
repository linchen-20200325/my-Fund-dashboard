# 客戶 2026-10-31 V7 Layout A 線框核准裁示（逐字）

- **來源**：客戶 2026-10-31 對話中對 `docs/v2/76_assets_v7_layout_a_wireframe.md` 的正式裁示，經總管於派工單內轉存為逐字文字；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-31-02`（客戶裁示）。落地：`docs/v2/76_assets_v7_layout_a_wireframe.md`（檔頭追加核准記錄與第 11 節「實作後實測」）、`ui_v2/asset/page.py`（A 的實作）、`docs/HANDOFF.md`（唯一接手點）。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行；單一換行結尾）。
- **存檔日期**：2026-10-31
- **圍欄內文 sha256**：`16a159737b75445c2dce9a5f353599c40972e7760e85c57358fd5cc8c7becad9`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。
- **撞字**：無。

```text
線框裁示：「docs/v2/76_assets_v7_layout_a_wireframe.md」核准，可以開始實作 A。
1. HLD-0／ALO-0 燈標題在合併頁消失：接受。「體檢結論燈」「差距結論燈」是原 presentation component 的標題。A 後該 component 不再於合併頁重複呈現，因此不需要另外搬這兩個標題。但必須繼續保留 Domain Block Identity、data-block anchor、_page_class、_state、_tone、reason / missing reason、provenance、Decision Digest mapping、deterministic semantics。單獨 HLD／ALO 頁不變。
2. ALO-0 說明句：原「本燈只讀 目標對照卡 算出的差距，不指出方向。」不要照原字保留「本燈」。改為「此配置判讀只讀 目標對照卡 算出的差距，不指出方向。」理由：A 實作後該位置沒有獨立「燈」元件，「本燈」會造成 presentation 語意錯位。這只是 UI copy 校正：不改公式、不改 rule result、不改方向性限制、不新增投資狀態、不新增 domain vocabulary。核心安全語意「只讀既有差距、不指出方向」完全不變。請把此字樣裁示同步到適合的 Decision / 76 文件；不要藉此順改其他文案。
3. 前往 Sheets 按鈕：接受。保留在「持股明細」第一個位置；key 不變；不塞入 P3 HTML 容器；不因 A 增加頁頂高度；原本只有需要時才出現的行為不變。
Mobile Visual Fidelity 補充裁示：接受線框已揭露的限制：A 不要求所有 Missing／Error／partial 組合都必須在 390px 第一屏完整看到 Primary 第一列。優先序為：重要頁級狀態／Missing／Error reason > 強迫 Primary 完整露出。因此：不得隱藏 Missing / omitted rows / error reason 來換取圖表高度；不得縮字到難讀；不得放寬既有 V7；不得修改 Mobile Visual Budget；不新增自動折疊重要錯誤資訊；不為少見 degraded-data 組合另開本批 layout 重構。但正式實作後仍必須實測並記錄：full、blank_target、hld_partial、alo=nofx、hld=fetchfail、skipped_rows、稽核已指出的兩個極端組合；將結果分成 1. V7 hard pass/fail 2. Primary 實際可見高度 3. 為何 degraded 情境允許狀態資訊優先；不得把未測寫成通過。
實作邊界：A 只做 presentation de-duplication。禁止順手改 P3 precedence、H6 分類、HLD-0 / ALO-0 domain semantics、Risk Cap、Decision Digest semantics、formula / threshold、OneBrain、其他頁、Visual Budget / V7 contract。實作後依既定 11 項驗收全跑，並補：附行不得因合成／de-duplication 被吞掉的守衛。完成獨立稽核、CI、Visual Fidelity 後，安全則依 Auto-Ship 收尾。Model / Effort：維持 Claude Sonnet 5.5 + Medium。
```
