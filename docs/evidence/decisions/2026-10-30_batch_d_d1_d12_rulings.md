# 客戶 2026-10-30 Batch D（💼 我的資產）D-1～D-12 正式裁示與 Domain Block Identity 定義（逐字）

- **來源**：客戶 2026-10-30 對話中的正式裁示，經總管於派工單內轉存為逐字文字檔；執行組照抄，未見客戶對話本身。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-30-02`（客戶裁示）。落地：`docs/v2/73_assets_wireframe_batch_d.md`（檔頭狀態更新）、`docs/v2/71_presentation_contract_migration.md` Batch D 指標、`docs/v2/44_fund_ui_ssot.md` 之十九其一之一第 6 條與之二十其二第 5 條行尾註、`docs/BACKLOG.md` BL-0525、`docs/HANDOFF.md`。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：0 行；單一換行結尾）。
- **存檔日期**：2026-10-30
- **圍欄內文 sha256**：`1c185b91d60517258fc59bcb07c3b9f6c45184842fa748c8aab72737a4f50681`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。
- **撞字**：D-10 客戶列舉「不寫」的字樣含詞表第 7、8 個詞各 1 處；照字面保留，登記見 `README.md` 〈撞字登記〉。

```text
先做 GitHub Verification Gate。

我方基準為：

- #1109 已合併
- main "b816df1c"
- Open PR 0

以下為 Batch D「💼 我的資產」D-1～D-12 正式裁示。

D-1｜層 3／層 4 的「塊」怎麼計

採 R-C：以 presentation container 計。

正式定義：

«「≤3 塊」限制的是同一層對使用者形成的主要 presentation containers，不是要求每一個既有 block ID 都必須各自占一個可見容器。»

因此：

- block ID 不刪
- block semantics 不變
- 四件事不變
- Decision Digest 不減少
- 多個 block 可以在同一 container 內以小標題分組呈現
- 不得形成巢狀 expander

「塊數」與「domain block ID 數」正式分離。

請把這個定義落 GitHub，避免未來再次把 presentation budget 誤解成 domain block 下架要求。

被降成一行的 "ALO-0" / "HLD-0" 仍保留原 domain block 身分，但 presentation 計數按其實際 container 處理。

---

D-2｜層 3／層 4 收斂

採 S1：3a + 4a。

理由：

- 資料零刪除
- 不用頁內多重 tabs 隱藏大量內容
- 不需要改 domain semantics
- 使用者打開容器即可看到完整內容
- 最符合「簡單 UI，但資訊仍完整存在」

不要把 "ALO-6" 搬進 Primary 的 detail。

Primary 是 visualization，不應變成 domain block 收納箱。

---

D-3｜整頁唯一結論燈

不採推薦 L-a。

原因：

若：

- 持股沒有偏離
- 但資產配置超出容許帶

L-a 會讓「💼 我的資產」的整頁燈仍顯示持股灰色／無偏離。

這與頁面回答：

«「我的錢放在哪？有沒有偏離？哪些持股需要注意？」»

不一致。

採 L-c 方向，但必須先走最小 Formula Gate

目標：

«page-level conclusion 必須同時反映 "HLD-0" 與 "ALO-0"，而不是只代表其中一區。»

不要直接自行寫「最差級」演算法。

請先提出最小 Formula / Rule Gate，至少列：

- HLD-0 所有正式狀態
- ALO-0 所有正式狀態
- 組合矩陣
- Missing / unavailable precedence
- system error precedence
- deviation precedence
- 是否只是 presentation aggregation，還是新增 investment logic
- 是否會改 Risk Cap / Decision Digest semantics

我的產品方向是：

«一頁一個整體狀態，不能讓其中一個區段的正常狀態遮掉另一區段的異常。»

在這個 Gate 正式落盤前：

不要 production implementation page-level combined light。

可以先完成其餘不依賴這個公式的 UI。

若該 Gate 觸發 Model / Effort Change：
先通知，再升 Opus 5.5 + High。

---

D-4｜Primary Visual

採「資產配置：現況 vs 目標」。

目前只有這個有既有正式資料可直接支援。

維持：

- 現況
- 目標
- 差距
- 容許帶狀態

缺資料誠實 Missing。

不要為了 Primary 去新增核心衛星或曝險來源。

---

D-5｜總資產／總損益／報酬／配息

分兩層裁示。

A. 本 Batch 不准入新彙總公式

採「不准入」。

不要現在新增：

- 總投入成本
- 總資產
- 總損益
- 組合報酬
- 組合配息
- 幣別曝險新彙總

原因：

目前牽涉：

- 跨幣別 identity
- 匯率
- "FX_OBS_DATE_RULE_VERIFIED"
- HLD-2 既有「不做跨幣別合計」
- HL-1～HL-4 / G-FORM

這些不是 UI Batch 應順手解掉的。

B. 但不同意把四個核心項目全部藏進「▸ 尚未取得」

這四項是已核准的第一屏核心資訊：

- 總資產
- 總損益
- 組合報酬
- 組合配息

目前算不出來時：

仍應在第一屏保留 compact summary slots，誠實顯示 Missing / 無法判定。

例如概念上：

"總資產 ◇ 資料未備"
"總損益 ◇ 資料未備"
"報酬 ◇ 資料未備"
"配息 ◇ 資料未備"

但不要現在新增新字彙；實際 Missing wording 沿正式 contract。

重要原則：

«Missing 可以是空狀態，但不能因為 Missing 就讓原本的核心決策欄位從第一屏消失。»

詳細：

- 為什麼缺
- 來源
- 限制
- 去哪補

仍可下沉 detail。

請重新處理 Visual Budget：

這四個 compact metrics 應視為一個 summary strip / summary container，而不是四張大型卡。

不要因此做四張 placeholder 大卡。

---

D-6｜Secondary Visual

採 2 張真資料。

不要用 placeholder 湊第三張。

目前：

1. 基金占比
2. 各檔區間報酬

足夠。

若未來有正式幣別曝險資料，再另行判斷是否成為第三張。

---

D-7｜圖表是不是新 block

採「圖表是 presentation component」。

圖表：

- 讀既有 block output
- 不自建 domain semantics
- 不自行產生 canonical values
- 不新增 block ID

若未來圖表需要新計算／新資料來源，另外走 Gate。

---

D-8｜持倉資料來源 selector

採頁頂獨立一列。

位置：

頁標附近／頁首上方。

不要塞到：

- 左側帳號區
- 全域設定
- 資料狀態 chip 裡

因為它是此頁 contextual source selector。

OAuth callback

目前 callback 只能回 "/set" 的問題：

先做 read-only 技術查證。

若只是 navigation return-state 能在既有 OAuth contract 內安全解：

可提出最小方案。

若涉及：

- scope
- redirect URI
- callback contract
- credential
- OAuth architecture

則停在新 Gate。

不要在 Batch D 順手改 OAuth。

---

D-9｜頁面回答什麼

沿用：

«我的錢放在哪？有沒有偏離？哪些持股需要注意？»

正式保留。

---

D-10｜一句主判讀

改採 C2，不採文件推薦 C1。

原因：

C1：

«持有 n 檔；m 檔超門檻……»

主要仍是持股摘要，而且與 HLD 燈高度重複。

合併頁現在必須真正同時代表：

- 持股
- 配置

因此使用 C2 的方向：

«持有 ‹n› 檔基金；配置與目標的最大差距在 ‹類別› ‹N› pp。»

但請做一點去重：

若 Primary 已非常清楚顯示最大差距，不需要在同一屏把完整相同資訊再寫一次。

可以縮成：

«「持有 ‹n› 檔基金；目前最大配置差距在 ‹類別›。」»

實際文案必須：

- 只描述既有事實
- 不新增投資判斷
- 不寫「應加碼／應減碼」
- 不把 Missing 推論成正常

若資料不足，照實「無法判定」。

---

D-11｜新擬字樣

原擬：

- 我設定的條件
- 持股證據
- 配置證據
- ▸ 尚未取得

我裁示：

保留

"▸ 尚未取得"

調整容器名稱

不要用「證據」當主要 UI 名稱，太偏工程／稽核語氣。

建議改成：

- 我的條件
- 持股明細
- 配置明細

底層 provenance / evidence 仍然完整保留。

使用者不需要在主 UI 一直看到「證據」這個工程詞。

如果現有正式詞彙已有更接近名稱，優先沿用既有 vocabulary，不另創新詞。

頁尾一句也不要增加新的結論；能刪 presentation redundancy 就刪，但資訊不得遺失。

---

D-12｜持股很多時怎麼畫

採全列＋卡內固定高度捲動。

禁止：

- Top 5
- Top 8
- 前 N 名

因為這會新增 ranking / selection rule。

排序維持既有正式規則。

水平條可以：

- 固定高度
- 垂直捲動
- 全列
- 明確 label

不要因 N 大而刪資料。

---

Batch D 正式產品結構

目標順序：

1. 持倉資料來源 selector
2. 第一屏 compact summary
   - 總資產
   - 總損益
   - 報酬
   - 配息
   - 缺資料就誠實 Missing
3. page-level status（D-3 Formula Gate 完成後）
4. 一句主判讀
5. Primary：資產配置 現況 vs 目標
6. Secondary × 2
7. 需要注意
8. 持股明細
9. Layer 3 grouped containers
10. Layer 4 grouped containers
11. 尚未取得 / provenance / detail

實際第一屏位置可依 desktop / 390px Visual Fidelity 微調，但不要違反資訊優先級。

---

Mobile 390px

四個核心 summary 不要變成四張巨大直式卡。

使用：

- 2×2 compact metrics
  或
- 緊湊 summary rows

以能在第一屏同時保留：

- 核心摘要
- page status
- Primary 上緣

為目標。

若放不下：

先縮 summary presentation，
不要把核心摘要全部搬進 expander。

---

關於 D-1 的正式定義

請特別把下面這條寫進正式 SSOT / Decision：

«Domain Block Identity ≠ Presentation Container Count.»

Block ID 用於：

- domain semantics
- traceability
- rule ownership
- Decision Digest mapping

Presentation Container 用於：

- UI density
- Visual Budget
- layer count

兩者不得再混為同一個計數。

這樣未來其他頁做 Presentation Migration 時，不需要再次為同一問題重開 Gate。

---

Decision Digest 保全

任何合併 container 都只改 presentation。

不能：

- 合併 canonical values
- 丟掉 block IDs
- 丟掉 source
- 丟掉 as_of
- 丟掉 missing
- 丟掉 reason
- 丟掉 provenance
- 把多個 rule result 合成一個新 rule result

除非另有正式 formula / Decision Digest Gate。

---

下一步

可以先進 Batch D implementation，但拆開：

可直接做

- S1 container structure
- summary strip
- Primary / Secondary
- selector placement
- details migration
- desktop / 390px Visual Fidelity
- tests migration

暫停

- D-3 page-level combined conclusion

先完成最小 Formula Gate，再接 page-level conclusion。

如果 D-3 需要升級：

Claude Opus 5.5 + High

只用在該 Formula / SSOT 判斷。

其餘 UI implementation：

Claude Sonnet 5.5 + Medium

恢復 Silent Autonomous Cruise。

只有：

- D-3 Formula Gate
- OAuth 真 Gate
- 新資料／公式 Gate
- Batch D 完整完成

才回報。
```
