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

## Model × Effort 節省基準矩陣（2026-10-25 客戶核准）

> 本表是**最低足夠設定的預設基準**，不是硬性綁定。每個完整工作階段仍必須依實際工作內容、風險與複雜度重新判斷；若現場判斷不同，依上方 Change Gate 停手請客戶切換。

| 工作類型 | 預設建議 Model | 預設 Effort | 原則 |
|---|---|---|---|
| GitHub 狀態確認、HANDOFF／BACKLOG／DECISIONS 機械同步、改字、小型文件修正、簡單 commit／PR 收尾 | Haiku 5.5 | Low | 優先最低成本；若只需讀取／機械修改，不使用較高模型 |
| 一般文件整理、規格明確的小修、簡單 bug、低風險測試修正 | Haiku 5.5 或 Sonnet 5.5 | Low～Medium | Haiku 能安全完成就不用 Sonnet；需一般推理再升 Sonnet |
| 一般 UI／UX、單模組 bug、tests、wiring、一般低風險實作 | Sonnet 5.5 | Medium | 日常開發預設基準 |
| Wireframe／UX 設計、規格清楚的跨少數模組工作 | Sonnet 5.5 | Medium | 不因「設計」自動使用 Opus |
| ~~OAuth／Google Sheet／跨模組架構、複雜 correctness、重要資料流~~ | ~~Opus 5.5~~ | ~~Medium~~ | ~~涉及安全、跨模組或複雜狀態時才升 Opus~~ ⛔ 2026-10-26 客戶修訂 supersede（見文末修訂註；有意識的政策變更，不是漏刪） |
| 一般 OAuth／Google Sheet 實作、規格明確的一般跨模組 wiring（含已明確規格的架構 wiring）〔2026-10-26 新列〕 | Sonnet 5.5 | Medium | 先用 Sonnet，不預設直接升 Opus |
| 複雜 OAuth／資安決策、credential／token storage、scope／callback、資料契約、重大架構取捨、重要跨模組架構、複雜 correctness〔2026-10-26 新列〕 | Opus 5.5 | Medium | 只有 Sonnet 不足或風險明顯提高才升 Opus |
| 投資語意、Risk Cap、PIT、資料契約、重大架構、不可逆或高風險決策 | Opus 5.5 | High | 高風險語意與資料契約須保守處理 |
| 極高複雜度、多方案重大衝突、大型紅隊／重大驗證 | Fable 5.1 或當下可用且明確更適合的最高能力模型 | High／更高（若介面提供） | 非必要不使用；必須有具體理由 |
| Ultracode | 不預設使用 | 不預設 | 只有已確認有明確必要時才建議，且先停手讓客戶切換 |

### 節省策略

1. **平常不要把 Opus 當日常預設。** 一般開發優先 Sonnet；機械工作優先 Haiku。
2. **Effort 採最低足夠值。** Low 能完成就不用 Medium；Medium 能完成就不用 High。
3. **工作變簡單時必須重新判斷並停手提醒降級。** 例如架構設計結束、進入文件同步／CI 收尾時，不得因前一階段使用 Opus／High 而一路沿用。
4. **不要為微小短暫狀態頻繁切換。** CI 等待、push、PR 開啟、同一完整工作階段內的短暫安全收尾，不視為新完整工作階段；只在新完整階段、工作性質明顯改變或 Safe Checkpoint 重新判斷。
5. **模型表只是預設起點，不是固定對照。** 例如 UI 若只改一行文字可降至 Haiku；反之 UI 若牽涉 OAuth／跨模組資料契約則可升至 Opus，但都必須經 Change Gate。
6. **目標是降低不必要的 token／使用量，不是犧牲 correctness。** 只要較低設定不足以安全完成，就應建議升級並停手等客戶調整。

## 白話判定

- Model 建議不同：要停下來告知，等客戶改。
- High → Medium：要停下來告知「可以降」，等客戶改。
- Medium → Low：要停下來告知「可以降」，等客戶改。
- Low → Medium：要停下來問，等客戶改。
- Medium → High：要停下來問，等客戶改。
- 日常機械工作：優先 Haiku／Low。
- 一般開發：優先 Sonnet／Medium。
- 高風險／複雜架構：才用 Opus／較高 Effort。
- Fable／Ultracode：不作預設。

**一句話版本：只要建議 Model 或 Effort 跟目前不同，不論升級或降級，都先停手讓客戶修改；改好後才開始下一完整工作階段；並永遠優先採用能安全完成工作的最低足夠 Model × Effort。**

## 2026-10-26 客戶修訂註（要點轉述，經總管派工單轉達，非逐字；有意識的政策變更，不是漏刪）

- 客戶 2026-10-26 修訂本檔矩陣（路線 a）：上方「OAuth／Google Sheet／跨模組架構…」列（Opus 5.5／Medium）已劃線，由兩列取代 —— 一般 OAuth／Google Sheet 實作與規格明確的一般跨模組 wiring ＝ Sonnet 5.5／Medium；複雜 OAuth／資安決策、credential／token storage、scope／callback、資料契約、重大架構取捨 ＝ Opus 5.5／Medium。其餘列照新版措辭微調（Haiku 列加入 commit／PR 收尾預設最低成本；Fable 列改為「極端複雜、重大治理衝突、大型 red-team、Opus 明顯不足」，非預設）。
- 舊列兩邊理由：舊讀法的用意 —— 安全相關工作不輕忽 —— 仍成立；被權衡掉的是「看到 OAuth／Google Sheet／跨模組關鍵字就預設升 Opus」。上方「節省策略」第 5 點的 OAuth 舉例（「牽涉 OAuth／跨模組資料契約則可升至 Opus」）在新版下讀作「複雜 OAuth／資安或資料契約才升」，該例句原文不動。
- 濃縮後的選用規則與現行矩陣以 `PROJECT_RULES.md` 5.1 第 10 點為準；本檔其餘（Change Gate、永久規則 1～10、白話判定）不變。客戶長文 Rule 1–12 未全文落盤。
