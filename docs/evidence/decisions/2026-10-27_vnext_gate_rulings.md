# 客戶 2026-10-27 vNext Decision Gate 1A～7A、治理兩題、隱私規則與 SSOT 收斂裁示（逐字）

- **來源**：客戶 2026-10-27 在對話中的正式裁示，經總管於派工單內逐字轉存；文件組照抄，未見客戶對話本身。
- **範圍**：圍欄內從「正式裁示如下」起，至第十五節末「之外，不需中途回報。」止，全文逐字，不含總管派工單的其他文字。
- **遮蔽**：無。本文沒有任何作者或老師姓名（總管轉存時已註明「contains no real name」），也沒有 secret；後續文件不得為本文補寫姓名（本文第十一節）。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-27-08`～`DEC-2026-10-27-24`。**落地**：`PROJECT_RULES.md` 第 12 節 12.2、12.3 與 0.5 索引；`docs/v2/66_market_trend_spec.md` 區段 D；`docs/v2/67_ai_action_vocabulary.md`；`docs/design/vnext_visual_blueprint.md` 第 8.10、8.11 節；`docs/BACKLOG.md` BL-0492～BL-0507 與 BL-0484～BL-0491 列尾補記；`docs/HANDOFF.md` Resume Checkpoint。
- **存檔 base**：main `c1d4ecab`（全長 `c1d4ecab870330c25f430687440a3db9732352bd`；分支 `docs/vnext-rulings-privacy-ssot-20261027`）。
- **性質**：本檔只存原文，不含任何文件組的讀法；讀法、supersede 範圍與邊界見上列 DECISIONS 條目。

```text
正式裁示如下，請依 GitHub Verification Gate 後的最新實況執行。

一、Decision Gate

- 1A：批次 1 殼層可以先開始
- 2B：本批直接採「深色主側欄＋淺色主內容區」
- 3A：第二層入口先使用 44 現有區塊標題
- 4A：Mobile 採五大主頁底部導航＋頁內跳轉，主要目的地最多 2 次互動
- 5A：「風險觀察」目前不顯示，不做空殼
- 6A：9 個 G-44 衝突走正式最小解凍，但必須逐項裁示／修訂
- 7A：允許新版綜合狀態與方向性輸出，但依下方「有限 supersede」執行

前輪治理兩題：

- AI commit 署名：A，不改寫歷史，從現在起遵守既有規則
- 歷史 PR／commit 已曾出現教材作者姓名：不 force-push、不 rewrite history；但依下方隱私規則做 forward-only cleanup

---

二、殼層與視覺

Desktop

正式目標視覺：

深色主側欄＋淺色主內容區

不要先維持全深色再做第二次 theme migration。

若舊 "docs/v2/21"、".streamlit/config.toml"、既有 "theme.py" 與此衝突，請正式記錄：

- vNext Visual Blueprint supersede 舊全深色視覺方向
- 僅取代視覺 theme
- 不藉此更動資料、公式或投資邏輯

Mobile

- 五大主頁使用底部導航
- 頁內第二層使用頁內跳轉／收合
- 主要目的地最多 2 次互動可達
- 必須實測 390px
- 若五個底部入口在 390px 發生截斷、誤觸或空間不足，再提出技術性調整
- 不得自行刪主頁

五大主頁固定為：

1. 🌍 市場與趨勢
2. ⚖️ 資產配置
3. 💼 我的持股
4. 🔍 找基金
5. ⚙️ 設定

第二層入口先使用 44 既有區塊標題，不自行創造新文案。

「風險觀察」目前沒有正式功能，因此先不顯示，也不放「規劃中」空殼。

---

三、G-44：正式最小解凍

同意 6A。

但 9 個 G-44 必須逐項處理，不是整份 44 放行。

每一項必須列：

1. 44 現行文字
2. Blueprint 新需求
3. 衝突原因
4. 最小 amendment
5. 風險
6. 對 tests / guards 的影響

解凍目的只限於實現已核准 Visual Blueprint。

禁止藉此：

- 改投資核心規則
- 改資料契約
- 新增外部資料來源
- 改 OAuth / security
- 放寬 Missing 規則
- 放寬 Risk Cap
- 全面重寫 44

---

四、G-DEC：有限 supersede

舊 DEC 不整個推翻。

仍然禁止

- 黑盒單一總分
- 用單一 0～100 分數決定市場好壞
- AI 自己決定資產水位
- AI 自己發明持股比例
- AI 自己發明 threshold
- 關鍵資料不足仍硬給方向
- AI 覆寫 deterministic rule

新允許

可以產生：

- 中性偏多／中性／中性偏空等綜合狀態
- 風險升高／下降
- 配置偏離
- 續抱
- 觀察
- 降低曝險
- 減碼
- 替代比較
- 無法判定
- 對基金配置的含義

但必須來自：

"Raw Data → Validate → Normalize → Domain / Formula → Deterministic Rules → Risk Cap → AI Explanation"

「一句話市場結論」不是單一總分。

它只是多個已計算結果的自然語言摘要。

例如可使用：

- EPS revision
- PE scenario
- rates
- international earnings
- market risk
- portfolio exposure

請修訂 "DEC-2026-10-23-01"，明確記錄本次 amendment / supersede 關係，不得讓新舊規則同時存在造成歧義。

---

五、台股大盤 EPS × PE Product Calculation SSOT

請正式落盤，不再標示「等待客戶提供公式」。

核心公式：

"Index_target = EPS_scenario × PE_target"

其中：

"EPS_scenario = EPS_base × (1 + g)"

因此：

"Index_target(g, PE) = EPS_base × (1 + g) × PE"

變數定義

EPS_base

台股加權指數對應之基準年度整體 EPS / 指數盈餘。

規則：

- 必須來自可追溯資料來源
- 必須有年度與 as-of date
- 不得從教材案例反推後永久寫死

g

指定年度台股整體 EPS / 獲利成長率。

規則：

- 必須有來源或正式估算模型
- Missing 不得自行猜測

PE_target

情境本益比。

教材案例使用約：

"15x ～ 21x"

但這只是 scenario axis，不代表 15～21 倍永久等於合理本益比。

未來若要建立 dynamic PE regime，需另案正式規格化。

---

六、教材案例與產品公式分離

外部教材案例提供的資訊包括：

- 樂觀獲利年增約 35% 以上
- PE 情境約 15～21 倍
- 教材案例加權指數高點區間約 39,856～56,862
- 教材資料時間約 2026/8/11

以上只能保存為：

Source Evidence / 教材案例

不能直接變成產品永久常數。

正式產品每次應依：

- 當期 EPS_base
- 當期 EPS 成長情境 g
- PE scenario

重新計算。

如果沒有 EPS：

"⬜ EPS 預估資料未取得，無法計算指數情境"

禁止：

"EPS = 0"

---

七、六個 AI 行動語意 SSOT

本輪先定義「語意邊界」。

不要自行發明數值 threshold。

1. 續抱

代表：

目前正式規則與 Risk Cap 沒有要求降低部位，且資料完整度足以判定。

不代表：

- 加碼
- 強烈看多
- 保證上漲

2. 觀察

代表：

出現值得追蹤的惡化／不確定因素，但尚未達正式降低部位條件。

必須顯示：

- 觀察原因
- 相關指標
- 下一個需要確認的條件

3. 降低曝險

屬 portfolio / asset-class / region / style 層級。

代表：

某類型曝險過高或風險環境改變，建議降低該 exposure。

不等同指定單一基金一定要賣。

4. 減碼

屬單一基金／單一部位的具體方向性動作。

正式使用前必須有：

- deterministic trigger
- 足夠資料
- Risk Cap
- 可追溯依據

trigger 尚未正式定義前，AI 不得自行決定減碼。

5. 替代比較

代表：

現有基金出現弱化／不適配，且候選池存在可比較標的，進入 replacement comparison。

不代表 AI 自動換基金。

至少比較：

- 原基金
- 候選基金
- 類型
- 風險
- 績效／回撤
- 配置影響
- 資料完整度

6. 無法判定

當關鍵資料：

- Missing
- stale
- error
- 或規則所需證據不足

就使用：

"無法判定"

並正式規定：

"無法判定 ≠ 續抱"
"無法判定 ≠ 安全"
"無法判定 ≠ 中性"

---

八、One AI Brain

正式採：

One AI Brain, Many Data Views

不是每頁各有一個獨立 AI Brain。

各頁只提供：

- Data View
- Domain Result
- Rule Result
- Local Explanation

全站唯一 AI Brain 整合：

市場
→ 資產配置
→ 持股
→ 候選基金
→ Missing / freshness
→ Risk Cap
→ 最終行動摘要

最終輸出固定：

1. 市場
2. 配置
3. 持股
4. 候選基金
5. 主要風險
6. 本期最多 3 項行動

每一項未來都必須能展開：

"查看依據"

AI 不得：

- 自己生成市場數字
- 自己補 Missing
- 自己改 threshold
- 自己新增資料來源
- 自己改 Risk Cap
- 自己推翻 deterministic rule

---

九、資料缺口

目前已盤點的 G-DATA：

- NASDAQ
- MSCI World
- MSCI EM
- EPS / PE
- 同類平均
- 基準指數
- 新 B 線財報／國際資料健康
- 區域欄位
- 產業欄位
- 投資風格欄位

這些不得因 Visual Blueprint 就自行新增 API。

請整理：

欄位| 用途| 現有來源| 缺口| 候選來源| 是否需 Decision Gate

需要新來源時，先交 ChatGPT 協作助手評估，再走 Data Source Decision Gate。

舊程式碼中的 S&P 500、加權指數等資料邏輯：

可以研究與比對。

但不能因舊 UI 存在，就默認符合新 B 線 Data Contract。

---

十、⚙️ 設定頁寫入邊界

第一階段仍維持 read-only。

因此若：

「管理組合」
「管理觀察清單」

代表直接修改 Google Sheet，本階段禁止。

第一階段可做：

- 查看目前組合
- 查看觀察清單
- 前往 Google Sheet 管理
- read-only detail

未來若正式解除 J-6 read-only，再另案加入寫入。

---

十一、公開 GitHub Repo 隱私規則

這是正式 Privacy Requirement。

核心原則

公開 GitHub repo 不得公開外部教材作者／老師的真實姓名。

後續一律使用中性名稱，例如：

- "外部投資教材"
- "客戶提供之投資教材"
- "台股大盤／國際趨勢參考教材"
- "External Investment Reference"

不得從上下文反推出作者身分。

禁止姓名出現的位置

所有新增或修改內容都不得再出現真實姓名，包括：

- PROJECT_RULES
- DECISIONS
- BACKLOG
- HANDOFF
- design/spec
- evidence
- 程式碼
- helper / function / class / constant 名稱
- 註解
- 測試名稱
- fixture
- PR title
- PR body
- commit message
- review comment
- audit report
- issue
- branch name

可以保存的內容

可以保存：

- 公式
- 方法
- 原始數值
- 日期
- 資料口徑
- source evidence
- 教材頁面／章節位置

但不得保存作者姓名。

---

十二、歷史姓名處理

不 force-push。
不 rewrite Git history。

但要做 forward-only cleanup。

請盤點 default branch 目前仍可見的：

- 文件
- 程式碼
- 註解
- helper 名稱
- 測試
- evidence

若姓名不是程式必要識別：

全部改成中性名稱。

已知至少盤點：

"ui/helpers/fund/checkup.py"

如果其中姓名只是 attribution 或歷史命名，請匿名化。

歷史 commit / PR metadata 若已經公開且必須改寫歷史才能移除：

- 不改寫
- 登記 historical exposure
- 不再擴散
- 新文件不得再次引用姓名

另外，請新增永久治理規則：

Public Repository Personal Name Redaction Rule

確保未來新對話／新專案 AI 不會再次把教材作者姓名寫進公開 repo。

---

十三、GitHub Discussion Persistence Gate

另外請正式保存這條長期治理規則：

只要 ChatGPT 協作助手與客戶一輪討論形成新的：

- UI 結論
- 產品方向
- 公式
- AI 語意
- 架構
- 資料規則
- 治理規則
- supersede

就不能只留在聊天記憶。

在下一個相關實作批次前，必須同步到適當 GitHub SSOT：

- DECISIONS
- BACKLOG
- HANDOFF
- design/spec
- PROJECT_RULES（只有永久治理規則）

不需要逐字複製整段對話。

只保存：

- 最終裁示
- 邊界
- supersede
- 未決事項
- 下一步
- Model / Effort Gate（若相關）

GitHub 為跨對話 SSOT。

聊天記憶只能作輔助。

---

十四、本輪工作順序

請先完成：

1. 本次 Decision / supersede 落盤
2. Privacy Requirement 落盤
3. default branch 姓名 forward-only cleanup 盤點
4. EPS × PE Product Calculation SSOT
5. 六個 Action Vocabulary SSOT
6. 9 個 G-44 最小解凍 amendment
7. DEC-2026-10-23-01 amendment
8. 對應 guards / tests
9. BACKLOG / HANDOFF 更新

完成以上 SSOT 收斂後，再開始：

- BL-0484 Shell / Navigation
- 深色側欄＋淺色主內容
- Mobile bottom navigation

不要在正式公式／Risk Cap／trigger 尚未完成前做假的 AI 投資建議。

---

十五、Model / Effort

本階段涉及：

- frozen 44 解凍
- 舊 DEC supersede
- AI action semantics
- privacy governance
- deterministic rule / AI boundary

請使用：

Model：Opus 5.5
Effort：Medium

完成 SSOT / 解凍／隱私收斂，工作回到單純 UI wiring 後，再依 Minimum Sufficient Effort 主動通知是否可降回：

Sonnet 5.5 + Medium

維持 Silent Autonomous Cruise。

除：

- Model / Effort Change Gate
- 真正 Stop Gate
- 完整階段完成

之外，不需中途回報。
```
