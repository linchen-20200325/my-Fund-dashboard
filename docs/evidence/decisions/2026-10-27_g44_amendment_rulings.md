# 客戶 2026-10-27 G-44 正式裁示（1A～10A、⚖️ 註記、EPS_base／g 資料來源裁示、執行順序）與同日補充確認（逐字）

- **來源**：客戶 2026-10-27 在對話中的正式裁示與補充確認，經總管轉存為逐字檔；執行組照抄，未見客戶對話本身。
- **範圍**：圍欄內兩段：第一段從「正式裁示：」起，至「維持 Silent Autonomous Cruise。」止；第二段從「改好了。」起，至「不需中途回報。」止。圍欄內兩個 `###` 小標是總管轉存時加的分段標題，照抄保留；其餘不含總管派工單的文字。
- **遮蔽**：無。本文沒有任何作者或老師姓名，也沒有 secret（執行組逐行讀過；「ChatGPT 協作助手」是協作角色名稱，不是人名）。後續文件不得為本文補寫姓名（`PROJECT_RULES.md` 12.3）。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-27-25`～`DEC-2026-10-27-38`。**落地**：`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十八與行尾加註；`docs/v2/66_market_trend_spec.md` 區段 D；`docs/design/vnext_visual_blueprint.md` 第 8.10 節；`docs/BACKLOG.md`；`docs/HANDOFF.md`。
- **存檔 base**：main `babfb88c`（#1082 合併後）。
- **性質**：本檔只存原文，不含任何執行組的讀法；讀法與邊界見上列 DECISIONS 條目。

```text
### 客戶 2026-10-27 G-44 正式裁示（逐字）
正式裁示：

- 1A
- 2A，但加上以下資訊密度限制
- 3aA
- 3bA
- 4A
- 5：照既定方案執行，不修改
- 6A
- 7A
- 8A
- 9A
- 10A

---

1A｜全站 AI 區

採 A。

全站 AI Brain 屬導覽／全站殼層能力，不算各頁內容塊。

各頁第一階段只顯示：

- deterministic rule result
- template/local explanation
- 查看依據

不要因此讓各頁各自呼叫一個獨立 AI。

正式 AI Brain integration 仍依既定 Batch 7。

---

2A｜摘要卡＋核心圖

採 A，但補上強制 guardrail：

「一頁最多 16 塊」只能視為 implementation ceiling，不是設計目標。

不得因上限提高就真的塞滿 16 塊。

正式 UI 原則仍然是：

Desktop 第一屏：

- 1 句狀態
- 3～5 張摘要卡
- 實際可視核心圖原則上 1～2 張
- 其餘核心圖往下排列
- 最多 1 個 AI 摘要入口

整頁：

- 核心圖最多 4 張
- cards 最多 5 張
- 完整表格／證據／公式／來源放下層或收合

Mobile：

- 第一屏更少
- 不把 Desktop 卡片硬縮成五張並排

因此：

16 是容器上限，不是 UX target。

核心目標仍是：

「簡單，但不能失去判斷能力」。

---

3aA｜圖表序列顏色

採 A。

允許顏色區分：

- 不同資料序列
- 不同基金
- benchmark
- scenario lines

但必須同時至少提供其中一種非顏色辨識：

- 直接標籤
- legend
- 線型
- marker
- 文字

禁止只靠紅／綠代表：

- 好／壞
- 買／賣
- 安全／危險

原本「顏色非唯一語意載體」不變。

---

3bA｜期間切換

採 A。

期間切換：

"3M / 6M / 1Y / 3Y"

屬於 Data View display control，不是：

- 投資試算參數
- 投資假設
- recommendation input

因此可以有預設值。

建議第一版統一預設：
"1Y"

若既有頁已有更合理的一致預設，可在 design spec 統一定義，但禁止各頁任意不同。

---

4A｜各頁回答什麼

採 A。

本輪 frozen 44 amendment 不趁機新增大量文字。

等各頁內容 Batch 才依正式資料／規則定稿。

避免現在產生：

- 「健康」
- 「值得看」
- 「適合」
  等尚未有完整 deterministic definition 的文案。

---

5｜不負責什麼

照目前方案執行：

一字不改。

跨頁整合只由 One AI Brain 負責。

---

6A｜🌍 現有三卡與新四卡

採 A。

現有三卡：

- 不刪邏輯
- 保留資料與規則
- 移到較下層 evidence/context 區

Blueprint 的新摘要卡：

必須等 "docs/v2/66" 對應規格與資料來源成立後才正式啟用。

禁止為了湊四張卡：

- 補假資料
- 顯示 0
- 用 placeholder 假裝已有判斷

資料不足時寧可少卡。

---

7A｜🔍「精選」語意

採 A。

目前不要使用：

- 精選
- 最佳
- 推薦
- Top pick

第一屏改成客觀語意：

"目前條件下有 N 檔符合"

或等同意思的既有正式文案。

這代表：
Rule Filter Result

不是 recommendation。

---

8A｜排名

採 A。

目前不做：

- 排名
- 星等
- AI score
- Top 1 / Top 5

顯示前 5～10 檔只是 UI 截斷，不代表名次。

穩定排序先採可重現 deterministic key，例如：
"基金代碼"

日後若正式建立 ranking model，再另走 Formula / Decision Gate。

---

9A｜找基金仍為使用者條件導向

採 A。

第一階段仍維持：

"使用者條件 → deterministic filtering → candidate set"

不是：

"AI 幫你挑基金"

AI 只能解釋已經由資料與規則產生的 candidate set。

---

10A｜EPS×PE 是情境指數，不是目標價

採 A。

正式定義：

"Index_target(g, PE)"

雖然變數歷史命名用了 "target"，產品語意不是「目標價」。

UI 請優先顯示：

情境指數
或
情境點位

不要顯示：

- 目標價
- 目標點位
- 預測高點

其含義只是：

在指定 EPS scenario 與 PE scenario 下，
依透明公式得到的 hypothetical index level。

必須同時顯示：

- EPS scenario
- PE scenario
- as-of
- data source
- Missing state
- 「情境分析，非目標價／投資建議」

因此不用解除 44 對「目標價」的禁止。

---

⚖️「增加某類型／維持」

這兩個目前不要補進畫面。

本輪 action vocabulary 已正式定義六個詞：

- 續抱
- 觀察
- 降低曝險
- 減碼
- 替代比較
- 無法判定

「增加某類型」涉及新的方向性 allocation action。

不要因 Blueprint 文案自行放行。

等未來：

- allocation rule
- Risk Cap
- trigger
  完整後再 Decision Gate。

---

EPS_base / g 資料來源 Decision

ChatGPT 協作助手已先查外部官方來源。

目前裁示為：

Phase 1：優先研究官方 actual/trailing data

候選：

TWSE

用途：

- TAIEX
- 市場 trailing P/E
- 市場統計

MOPS / TWSE

用途：

- 上市公司實際財報
- EPS
- EPS YoY
- earnings actuals

以上可以進行 Data Source Probe / Shadow Research。

但注意：

這些資料是：
actual / trailing

不是：
forward consensus forecast

---

EPS_base 第一階段定義

不要直接把：

"TAIEX / 市場PE"

命名成正式的 "forward EPS_base"。

可以研究：

"implied_trailing_index_earnings = TAIEX / trailing_market_PE"

但這個值在完成：

- universe alignment
- PE methodology
- denominator consistency
- historical validation

之前，只能是 research metric。

不能直接升格成 Product SSOT 的 forward EPS。

如果驗證不成立：
就不用。

---

g 的處理

目前 TWSE／MOPS 可以提供實際歷史 earnings growth。

但是：

歷史 EPS growth ≠ 未來 EPS growth forecast。

因此 Phase 1 不准用：

- 過去一年成長率
- AI 自己預測
- 線性外推
- 隨便抓新聞數字

冒充正式 "g"。

正式 forward "g" 仍保持：

"⬜ forward EPS growth source not available"

直到 Data Source Gate 核准正式預估來源。

---

EPS×PE 圖在 forward data 尚未完成時

若沒有正式 forward EPS：

不要假裝畫出正式預測。

可以：

A. 顯示
"⬜ EPS 預估資料未取得，無法計算正式指數情境"

或

B. 若未來另行核准 scenario mode：
明確標示為
"假設情境"
而不是
"市場預估"

例如使用者選擇：

- +10%
- +20%
- +30%

只能叫：
"EPS 成長假設"

不能叫：
"EPS 預估"

目前先不要自行啟用 B，待後續 Decision Gate。

---

Data Source Probe 要求

請新增安全的 research / shadow batch，研究：

1. TWSE TAIEX
2. TWSE market trailing P/E
3. MOPS earnings / EPS actual data
4. 是否能建立一致且可重現的 "implied_trailing_index_earnings"
5. universe 是否一致
6. update frequency
7. publication lag
8. revision behavior
9. Missing / stale policy
10. licensing / usage restrictions

只做 probe / spec。

不得接正式 signal。
不得接 AI Brain。
不得用 actual data 冒充 forward forecast。

若需要：

- FactSet
- Bloomberg
- LSEG
- 券商 consensus
- 其他付費／授權預估來源

必須另回 Data Source Decision Gate，不得自行接入。

---

執行順序

現在先：

1. 依上述 1A～10A 完成 frozen 44 最小 amendment
2. 同步 guards/tests
3. 獨立稽核
4. CI
5. Auto-Ship

完成 SSOT 解凍後：

開始 BL-0484：

- 深色側欄
- 淺色主內容
- Desktop shell
- Mobile bottom navigation
- 390px 真實驗收

EPS 資料來源 probe 可以作為獨立後續 batch，不要阻塞純殼層 UI。

Model / Effort

目前仍在 frozen 44 amendment：

Opus 5.5 + Medium

44 收斂並進入純 Shell/UI wiring 後，依既有 Model Change Gate 通知切回：

Sonnet 5.5 + Medium

維持 Silent Autonomous Cruise。

### 客戶 2026-10-27 補充確認（逐字）
改好了。

請依前述已核准的 1A～10A、EPS_base／g 資料來源裁示與既定執行順序繼續。

10A 的「情境指數」視為正式裁示，請同步關閉 #1082 對 "Index_target" 是否屬目標價的待決項；不得再使用「目標價／目標點位／預測高點」語意。

其餘維持 Silent Autonomous Cruise；除真正 Stop Gate、Model／Effort Change Gate 或完整階段完成外，不需中途回報。
```
