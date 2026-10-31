# 客戶 2026-10-30 D-3 Formula／Rule Gate（採 P3、precedence 採 β；F-13／F-2／F-14／F-18〔BL-0411〕／F-19）與 OAuth 回原頁 Gate（採 F）正式裁示（逐字）

- **來源**：客戶 2026-10-30 對話中的正式裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-30-04`（D-3 Formula／Rule Gate）、`DEC-2026-10-30-05`（OAuth 回原頁 Gate）（客戶裁示）。落地：`docs/v2/74_assets_d3_formula_gate.md`（檔頭狀態與第 5 節各 F 項）、`docs/v2/73_assets_wireframe_batch_d.md` 第 15 節、`docs/BACKLOG.md` BL-0525（子項 BL-0525-D3／BL-0525-OAUTH）與 BL-0411、`docs/HANDOFF.md`。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行；單一換行結尾）。
- **存檔日期**：2026-10-30
- **圍欄內文 sha256**：`3ba8c91b7388690ac639816d3c10d64bd92eaef97740e864e56c3a44c31d1dfd`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。
- **撞字**：無。

```text
先做 GitHub Verification Gate，以目前 main "9e508046" 為基準。

D-3 Formula / Rule Gate 正式裁示

採 P3，precedence 採 β。

正式原則：

«整頁狀態必須同時涵蓋持股與配置；任何一區有異常、資料不足或尚未完整評估時，不得被另一區的正常結果遮蔽成「正常」。»

precedence 採：

取數失敗 > 無持倉 > ◆ > ◇ > ⬜ > 持股只評估一部分（H7） > 無偏離／帶內

此 aggregation 僅用於 page-level presentation status。

不得藉此：

- 改 Risk Cap
- 改 domain block 原判定
- 改 canonical data
- 改 Decision Digest 原始 rule result
- 新增買賣判斷
- 把 Missing 推論成任何投資結論

各 domain block 的原始狀態與 reason 必須仍完整保留、可追溯。

F-13

必修。

只要任何配置類別沒有成功評估：

不得顯示：

«各類別皆在容許帶內»

應改成正式 Missing / 無法完整判定語意。

已成功評估的類別結果可以保留，但不能從「已評估子集合」推論整體配置正常。

F-2

必修。

持股只評估一部分時：

不得只顯示「無偏離項」。

必須同時讓使用者看得到既有的缺值／未評估原因。

不要新增第二套 Missing vocabulary。

F-14

必修。

任何正式狀態不得出現「有狀態但沒有文字」的情況。

在該市值基準情境無法形成完整配置判定時，使用既有正式 Missing / 無法判定語意。

不得補成正常、帶內或無偏離。

F-18 / BL-0411

先修 BL-0411，再允許 P3 production 上線。

如果部分列目前被略過但 UI 沒揭露：

- 頁燈
- 持有 N 檔
- 配置／持股整體判定

都不能假裝覆蓋完整集合。

必須先讓 omitted rows / 未納入集合的事實可被辨識。

不要為了 P3 在 page layer 臨時掩蓋 BL-0411。

F-19

採：算「沒評估到」。

有市值但沒有設定目標的類別：

不能視為「帶內」。

因為沒有目標，就沒有足夠條件判斷是否在容許帶內。

因此進未完整評估語意。

P3 實作驗收

至少補完整組合矩陣測試，確認：

- HLD 正常 + ALO 異常
- HLD 異常 + ALO 正常
- 一側 Missing
- 一側取數失敗
- 一側部分評估
- ALO 有未設定目標類別
- BL-0411 omitted rows
- 雙方皆完整正常

都不會發生：

Unknown / Missing / Error 被正常狀態蓋掉。

並確認 page-level aggregation 不回寫 domain block。

---

OAuth 回原頁 Gate

採 F：維持現況。

流程接受：

登入 → "/set" → 確認 → 使用導覽回「💼 我的資產」。

目前只多一次點擊，不值得改 OAuth callback / redirect contract。

因此：

- 不做 A
- 不做 B
- 暫不做 G

若未來實際 Visual Fidelity / 使用者操作證明這一步造成明顯摩擦，再考慮 G：

«"/set" 確認後提供靜態「回到 💼 我的資產」»

但 G 屆時仍先出最小 UI 線框，不碰 OAuth。

---

模型 / Effort

這一輪 D-3 Formula / SSOT 落盤與阻擋項修正：

Claude Opus 5.5 + High

P3、F-13/F-2/F-14/F-18/F-19 全部正式落盤並驗證後：

立即走 Model / Effort Change Gate，降回：

Claude Sonnet 5.5 + Medium

後續 UI / tests / Visual Fidelity 不需要繼續用 Opus。

維持 No Progress Narration Gate / Silent Autonomous Cruise。

除非：

- 真 Decision Gate
- 真 blocker
- Model/Effort Change Gate
- 或整批完成

否則不要回報過程。
```
