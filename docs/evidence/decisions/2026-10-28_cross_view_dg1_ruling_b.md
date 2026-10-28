# 客戶 2026-10-28 DG-1 裁示（方案 B）：先執行 BL-0520 特徵化測試，不改 production（逐字）

- **來源**：客戶 2026-10-28 對話中對 Cross-View Data Consistency Gate 之 DG-1 的裁示，經總管於派工單轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-28-03`（客戶裁示）。落地：`docs/BACKLOG.md` BL-0520／BL-0521／BL-0522、`docs/HANDOFF.md` Resume Checkpoint、`tests/test_xview_characterization.py`、`docs/v2/69_cross_view_consistency_spec.md` 〈BL-0520 實測結果〉。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為派工單轉存的客戶原文，字句未改；唯一格式處理：無（原文無只含空白的行，行尾空白：0 行）。
- **存檔日期**：2026-10-28
- **圍欄內文 sha256**：`999b24f83e9d83ab65a01edcc8313f63d7fcf5dec9aeb49b204bc8d16e17c51f`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

```text
裁示：

先執行方案 B：BL-0520 characterization tests（C1～C9）。

目前不要先改：

- source precedence
- canonical identity
- "get_latest_nav"
- valuation methodology
- FX cutoff
- return formula
- freshness / conflict tolerance

目的不是把現況當規格，而是先把目前各路徑的差異變成可重跑證據。

特別要求：

1. characterization test 必須清楚標示：
   「描述現況，不代表核准現況語意」
   避免未來把錯但穩定的行為誤認成 SSOT。

2. 能量測的差異請實際量測：

   - 同 fund code / URL 不同呼叫形式
   - cache key
   - NAV source
   - NAV date / as-of
   - Sheet "nav_history"
   - "get_latest_nav"
   - return formula
   - FX
   - identity key
   - AI snapshot/cache

3. 不要為了讓測試通過而改 production 行為。

4. C1～C9 完成後做獨立稽核，整理成：

   - 已證實一致
   - 已證實不一致
   - 尚無法驗證
   - 哪些差異會造成使用者看到不同數值

5. 完成後再提出下一個 Gate：
   DG-2 canonical identity
   並提供具體 contract 方案，至少涵蓋：

   - canonical_id
   - fund code
   - ISIN
   - share class
   - currency
   - platform suffix
   - historical compatibility / migration

6. DG-2 尚未核准前，不開始 canonical identity production refactor。

7. 暫時不要執行方案 C（把 "get_latest_nav" 併入 A 鏈），因為會直接改變 T7 估值數字；等 identity 與 precedence 有證據後再裁。

BL-0509 照原排程平行累積，不互相阻塞。

Model：Sonnet 5.5
Effort：Medium

若進入 DG-2 canonical data contract 的正式實作，再走 Model Gate，優先評估 Opus + High。
```
