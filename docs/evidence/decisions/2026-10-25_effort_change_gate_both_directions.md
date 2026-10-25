# 客戶 2026-10-25 Model／Minimum Sufficient Effort 有變皆停手永久裁示

- **來源**：客戶 2026-10-25 在對話中的正式裁示，由協作助手直接落盤。
- **性質**：永久治理規則；適用基金專案未來所有對話與 agent。
- **目的**：每個完整工作階段與工作性質明顯改變時重新判斷 Model 與 Minimum Sufficient Effort；若較省的設定已足夠，必須主動提醒降級，以避免不必要的 token／使用量消耗。任何 Model／Effort 升級或降級都由客戶先手動調整後，再開始下一完整工作階段。
- **取代範圍**：本裁示 supersede `PROJECT_RULES.md` 第 5 節 5.1 第 9 點中「調低只標示建議、不停工」及第 3 節 3.1 對應的「只有提高才單獨出聲」讀法；同時把相同 Change Gate 明確擴及 Model。其他 Minimum Sufficient Effort 風險分級、GitHub-first、Silent Autonomous Cruise、Stop／Decision Gate 與 Safe Checkpoint 規則不變。

## 永久規則

1. **每個完整工作階段開始前都必須重新判斷 Model 與 Minimum Sufficient Effort。** 包含新的 Phase、Batch、重要實作、架構／資料／投資語意工作，以及前一完整工作階段結束後準備進入下一階段。
2. **工作性質、複雜度或風險明顯改變時，也必須重新判斷。** 包含工作明顯變簡單或變複雜。
3. 若重新判斷後的建議 **Model 與 Effort 都等於目前設定**：維持 Silent Autonomous Cruise，直接繼續，不需額外回報。
4. 若重新判斷後的建議 **Model 或 Effort 任一項不同於目前設定**：不論是升級或降級，都必須在開始該完整工作階段前停手並通知客戶，等待客戶完成調整並明確回覆後才開始該階段。
5. **Model／Effort 的升級與降級採完全對稱的 Gate**：
   - 較省 Model → 較強 Model：停手，等待客戶調整。
   - 較強 Model → 較省 Model：停手，主動提醒可降低，等待客戶調整。
   - Low → Medium：停手，等待客戶調整。
   - Medium → High：停手，等待客戶調整。
   - High → Medium：停手，主動提醒可降低，等待客戶調整。
   - Medium → Low：停手，主動提醒可降低，等待客戶調整。
   - 客戶介面若提供 Low／Medium／High 以外的 Effort 選項，任何跨級升／降亦遵守同一原則；通知時以客戶當下介面實際可選名稱為準，不自行假設不存在的選項。
6. 通知格式保持精簡：

   ```text
   ⏸️ 建議切換 Model／推理強度
   下一階段：<工作名稱>
   目前 Model：<目前>
   建議 Model：<建議>
   目前 Effort：<目前>
   建議 Effort：<建議>
   原因：<一句話>
   切換完成後請回覆「改好了」。
   ```

   若只有 Model 或只有 Effort 需要變更，未變更的欄位仍可保留，讓客戶清楚核對目前設定。
7. **不得先施工再補問。** Change Gate 觸發後，該下一完整工作階段尚未開始；收到客戶「改好了」或等義明確確認後才可進入。
8. 等待調整期間，不受影響且不屬於下一完整工作階段的既有安全收尾可依原治理規則完成；不得以此偷跑新階段。
9. `PROJECT_RULES.md` 的 Low／Medium／High 保留作 Minimum Sufficient Effort 的風險分級基準；**不得把這個三級風險分類誤讀成客戶介面 Effort picker 的選項上限**。實際切換要求以客戶當下產品介面可用選項為準。
10. **省額度優先**：若較低 Model 或較低 Effort 已足以安全完成下一完整工作階段，必須主動建議降級；不得因「較強比較好」而長期維持較高設定。

## 白話判定

- Model 建議不同：要停下來告知，等客戶改。
- High → Medium：要停下來告知「可以降」，等客戶改。
- Medium → Low：要停下來告知「可以降」，等客戶改。
- Low → Medium：要停下來問，等客戶改。
- Medium → High：要停下來問，等客戶改。

**一句話版本：只要建議 Model 或 Effort 跟目前不同，不論升級或降級，都先停手讓客戶修改；改好後才開始下一完整工作階段。**
