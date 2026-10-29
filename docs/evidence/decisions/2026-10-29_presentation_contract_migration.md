# 客戶 2026-10-29 裁示：Presentation Contract Migration＋Visual Fidelity Gate，及其 Gate 裁示與追加方向（逐字）

- **來源**：客戶 2026-10-29 對話中的正式裁示，分三則訊息送出，經總管於派工單內轉存為三個逐字文字檔；執行組照抄，未見客戶對話本身。
- **三則訊息的關係**：第一則（第一段圍欄）在「六、舊契約 migration」開頭、「A. 資訊語」處被截斷；第二則（第二段圍欄）為客戶補送的第六～二十四節全文。第一則的第六節開頭與第二則的第六節是同一節的兩個版本，**以第二則為準**（第二則是客戶補送的完整版）；第一則照原樣保留，不補字、不刪截斷處。第三則（第三段圍欄）是客戶對前兩則落盤後所提五個 Decision Gate 的裁示，並追加新方向（簡單決策儀表板、Visual Budget、四頁 IA、Decision Digest、One AI Brain、AI 投資總結、GitHub Durable Memory）。
- **遮蔽**：無。本文沒有作者或老師姓名，也沒有 secret。
- **決策登記**：`docs/DECISIONS.md` `DEC-2026-10-29-05`（Presentation Contract 與 Visual Fidelity Gate，含第三則的 Visual Budget 與 VFG 確認）、`DEC-2026-10-29-06`（第三則的 IA 裁示、Decision Digest／One AI Brain 方向與 GitHub Durable Memory）（皆客戶裁示）。落地：`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十九（Presentation Contract 與 Visual Fidelity Gate 正式條文）、第七節第三小節之二十（基金 IA 最小 amendment）、`docs/v2/67_ai_action_vocabulary.md` 第 5～7 節（Decision Digest 與 One AI Brain）、`docs/v2/71_presentation_contract_migration.md`（盤點、矩陣、清單、分批計畫）、`PROJECT_RULES.md` 第 7 節指標、`docs/design/vnext_visual_blueprint.md` 檔頭指標、`docs/BACKLOG.md` BL-0525～BL-0528 與相關列尾補記。
- **性質**：本檔只存原文，不含執行組讀法。圍欄為轉存的客戶原文，字句未改；唯一格式處理：無（行尾空白：三段皆 0 行；三段各以單一換行結尾）。
- **圍欄寫法**：原文第二則自己含三個反引號的程式碼區塊，故三段圍欄一律用**四個反引號**，圍欄內文逐位元組等於原文。
- **存檔日期**：2026-10-29
- **圍欄內文 sha256**：第一段 `7f069a1f8df4200712fe02942c3beac6fdd9af7bcbe9265dabe325f69f035e73`；第二段 `a19f3bf169143ea7b1cd3e57cea2a057ec09f83a33b26652365a3b9a0680886a`；第三段 `00a1505635263503f59d7e43645eef80559aae1b47cf2248d5e8bebfcbd1d4bd`
- **依據規則**：`PROJECT_RULES.md` 12.2 GitHub Discussion Persistence Gate。

## 第一則訊息（在第六節開頭截斷）

````text
先做 GitHub Verification Gate，再開始任何判斷。
我方最新核對時間為 2026-10-29：

* main：`6b60b2b6309197396456ba96592f440961df39ff`
* Open PR：Draft #1104
* #1104 處理 BL-0513／BL-0517 殘餘 Decision Gate／BL-0501 唯讀盤點
* #1104 與本次 Presentation Contract Migration 是不同工作線

若你查到 GitHub 實況不同，以最新 GitHub 為準。
本輪目標
正式啟動：
Presentation Contract Migration + Visual Fidelity Gate
目的不是單純改 CSS，也不是重做整個產品，而是把目前 B 線 UI 從「文字完整外露」校正回客戶已核准的 vNext Visual Blueprint。
本輪第一階段先處理：

1. 舊 presentation contract 與新 Visual SSOT 的衝突盤點
2. 新 Presentation Contract 正式落盤
3. Visual Fidelity Gate 正式落盤
4. helper / tests / wireframe / SSOT 受影響面盤點
5. 規劃後續 UI migration batches

本階段以規格遷移與影響盤點為主。不要直接把五頁一次重寫。
一、最高優先原則
客戶正式確認新的 Visual hierarchy：
圖表 > 數字 > 短句 > 長文字
這不是裝飾性偏好，而是新的 Presentation Contract 核心。
主畫面優先呈現：

1. 圖表／主要視覺
2. 關鍵數字
3. metadata / status chips
4. 最多一句簡短說明
5. 詳細文字、來源、公式、限制、診斷放入 expander

二、「資訊存在」與「資訊外露」正式分離
舊 UI 中常見：

* 現在怎樣
* 為什麼
* 去哪補
* 來源
* 限制
* 資料日期
* 缺資料原因

新規則：
這些資訊必須存在、可追溯、可取得，但不再要求全部常駐主畫面。
硬規則：
不得刪除「現在／為什麼／去哪補」承載的治理資訊；只取消它們必須全部外露的要求。
主卡原則：

* 狀態
* 關鍵數字
* 一句摘要
* 3～5 個 metadata/status chips

詳細內容：

* 為什麼
* 資料來源
* 取得時間
* 限制
* 缺值規則
* 公式
* 去哪補
* 技術診斷

預設放進 expander / detail layer。
三、圖表呈現契約
圖表必須：

* 永遠在主視覺層
* 不得預設塞進 expander
* 不得被大段說明文字推到第一屏以下
* 上方可放：
   * 標題
   * 3～5 個 metadata chips
   * 最多一句簡短說明

範例結構：
台股加權指數
`47,036` ｜ `1Y +68.3%` ｜ `資料 10/28` ｜ `延遲 1日` ｜ `✅ 可讀`
一句話摘要
[圖表]
`▸ 為什麼／來源／限制／去哪補`
禁止在圖表下方常駐大量：

* provenance 長句
* 缺值說明
* 新鮮度規則
* 技術描述

除非該資訊本身就是使用者當下必須立即知道的警示。
四、Missing / unavailable 呈現
既有資料治理規則全部維持：

* missing ≠ 0
* unavailable ≠ neutral
* not evaluated ≠ safe
* Unknown 保持 Unknown
* 顏色不能是唯一資訊載體

但 Missing UI 改為：

* placeholder card
* status chip
* 一句短原因

例如：
`⬜ 資料未取得`
`目前沒有已核准資料來源`
詳細：
`▸ 原因／來源狀態／去哪補`
不得再用多段文字填滿卡片以補空間。
五、Visual Fidelity Gate
正式建立 UI Stage 的驗收規則：
功能測試、CI、QA 全綠 ≠ UI Stage 完成。
每個 UI PR 必須有 production-like screenshot 驗收。
至少驗：

1. 首屏結構
2. 圖表是否位於主層
3. 圖表 / 文字比例
4. 資訊密度
5. 圖表尺寸
6. metadata chips 是否取代重複文字
7. 長文字是否正確下沉
8. Missing placeholder 是否符合新契約
9. desktop
10. 390px mobile

必須直接對照：

* 已核准 `docs/design/vnext_visual_blueprint.md`
* 最新正式 Presentation Contract

若 screenshot 在 visual hierarchy 上有明顯偏差，即使 CI 全綠：
不得標記 Stage complete。
六、舊契約 migration
請全面盤點以下可能與新契約衝突的地方：

* `render_state.*`
* 「三要素」helper
* `not_ready(..., where=...)`
* ui_v2 共用 helper
* 舊 ui/views
* tests
* snapshot / string assertion
* wireframe
* UI spec
* frozen 44
* CONSTITUTION
* audit spec
* preview acceptance tests

判斷每項屬於：
A. 資訊語
````

## 第二則訊息（客戶補送的第六～二十四節全文）

````text
六、舊契約 Migration 與分類標準
請全面盤點目前 repo 中所有可能與新 Presentation Contract 衝突的呈現規則，包括但不限於：

* `render_state.*`
* 「現在／為什麼／去哪補」三要素 helper
* `not_ready(..., where=...)`
* `ui_v2/**` 共用 helper
* 舊 `ui/views/**`
* tests / guard tests
* snapshot / string assertion
* wireframes
* UI spec
* `docs/v2/44_fund_ui_ssot.md`
* `docs/v2/CONSTITUTION.md`
* audit spec
* preview acceptance tests
* 任何會強制「文字必須常駐外露」的規則

每一項必須分類為：
A. 資訊語意 Contract
定義：
它規定的是「資訊本身必須存在／語意必須保持」，而不是規定資訊一定要怎麼排版。
例如：

* Missing 不得被寫成 0
* unavailable 不得表示 neutral
* 「去哪補」的資訊必須存在
* provenance 必須可追溯
* 資料日期必須可以查到
* error / missing / business alert 必須語意分離

處理：
保留。
Presentation Migration 不得刪除或弱化這些資訊。
B. Presentation-only Contract
定義：
它只規定資訊如何顯示，例如：

* 「現在／為什麼／去哪補」三列一定全部外露
* 某段說明文字一定常駐主卡
* 某來源文字一定放圖表下方
* 某卡必須固定有 N 行說明
* 主頁必須展開某技術資訊

但不影響底層資料語意。
處理：
由新的 Presentation Contract supersede。
允許改成：
主卡：

* 狀態
* 數字
* chip
* 一句摘要

詳細資訊：

* expander
* detail layer
* drill-down

C. Mixed Contract
定義：
同一 helper / test / spec 同時包含：

1. 必須保留的資訊語意；
2. 舊的呈現方式要求。

例如：
`not_ready(message, where=...)`
其中：

* Missing / not-ready 語意可能屬 A；
* `where` 必須常駐外露可能屬 B。

處理：
拆開。
保留資訊 contract；
只 migration presentation responsibility。
不得因為要改畫面而把資料治理一起刪掉。
七、SSOT precedence
這次正式採用：
舊 helper / test / wireframe 若與新的 Visual SSOT 在「呈現方式」上衝突，以新的 Presentation Contract 為準。
但此 precedence 僅限：

* visual hierarchy
* information density
* default expanded / collapsed state
* chart placement
* text placement
* metadata chip
* placeholder
* presentation responsibility

不得藉此 supersede：

* 資料語意
* missing semantics
* provenance requirement
* 公式
* 投資邏輯
* Risk Cap
* 減碼 trigger
* canonical identity
* NAV semantics
* Sheet fund-code contract
* AI decision semantics

八、測試契約 Migration
請找出所有目前會強制：

* 三列文字必須存在於主畫面
* 某段詳細說明必須直接 render
* `where` 一定常駐
* 技術來源一定直接展開

的 UI tests。
新的 test contract 應改為驗：

1. 資訊存在；
2. 資訊沒有遺失；
3. 使用者可以展開／取得；
4. Missing / error / business alert 語意不變；
5. provenance 仍可追溯；
6. 主畫面不必全部外露。

不要為了讓新 UI 過測試而刪除資訊。
也不要保留與新 Visual SSOT 明確衝突的「文字一定外露」assertion。
九、圖表優先正式 Contract
新的 Visual hierarchy：
圖表 > 數字 > 短句 > 長文字
圖表規則：

* 圖表預設外露。
* 圖表不得被放進預設收合的 expander。
* 圖表上方可以有 3～5 個 metadata / status chips。
* 每張圖最多一句使用者語言摘要。
* provenance、限制、公式、缺值規則放 detail layer。

推薦卡片結構：

```
標題

主要數字 ｜ 期間變化 ｜ 資料日 ｜ 狀態

一句短說明

[ 圖表 ]

▸ 為什麼／來源／限制／去哪補
```

十、Missing Presentation Contract
既有資料治理不變：

* missing ≠ 0
* unavailable ≠ neutral
* not evaluated ≠ safe
* Unknown 保持 Unknown
* 顏色不是唯一資訊載體

但呈現方式改成：

```
⬜ 資料未取得
目前沒有已核准資料來源

▸ 詳細原因／來源狀態／去哪補
```

必要時保留圖表 placeholder。
禁止：
用數段技術文字填滿 Missing 卡片。
十一、Visual Fidelity Gate
新增正式 UI Stage 驗收條件：
功能測試、CI、QA 全綠，不代表 UI Stage 完成。
每個 UI PR 都必須有 production-like screenshot 驗收。
至少檢查：

1. 第一屏 visual hierarchy
2. 圖表是否外露
3. 圖表相對文字是否足夠突出
4. 關鍵數字是否易讀
5. metadata chips 是否取代重複長句
6. 是否仍存在不必要的文字牆
7. 詳細文字是否下沉
8. Missing placeholder 是否正確
9. desktop
10. 390px mobile
11. 圖表尺寸
12. 與核准 blueprint 的資訊密度差異

Visual Fidelity 必須直接對照：

* `docs/design/vnext_visual_blueprint.md`
* 最新正式 Presentation Contract

只要 production screenshot 在以下任一項有明顯偏離：

* 首屏結構
* 圖文比例
* 資訊密度
* 圖表尺寸
* 主次 hierarchy

即使 CI 全綠：
不得標 Stage complete。
十二、基金專屬 IA 裁示
以下是基金專案本身的新方向，不是從其他 repo 照搬。
A. Google 帳號
Desktop：
Google account control 放在左側固定面板。
至少顯示：

* 已登入 / 未登入
* 目前帳號
* 登入
* 切換／登出入口

使用者不應為了登入先進「設定」。
Mobile：
若固定 sidebar 不適合，可放入既有 navigation drawer / compact account control。
但必須：

* 隨時可找到；
* 不佔據主要第一屏；
* 不強迫先進設定頁。

B. Sheet selector
正式原則：
Sheet 是 contextual data source，不是全部集中在設定頁的全域操作。
放到真正使用該 Sheet 的頁面。
例如：
我的資產
頁面頂部附近：
`持倉資料來源 ▼`
找基金
若存在候選清單：
`候選清單 ▼`
但候選清單只影響：

* 加入候選
* 讀候選清單

不得阻擋基本基金搜尋／篩選功能。
避免主要流程：
`頁面 → 前往設定 → 選 Sheet → 回頁面`
C. 設定頁
設定頁保留低頻全域功能：

* 資料新鮮度
* 資料健康
* 來源診斷
* 規則參數
* 進階診斷
* 真正全域設定

不要再把所有資料連接入口都塞進設定。
十三、「我的持股＋資產配置」整合方向
客戶裁示：
朝「我的資產」整合。
這是 IA / presentation 合併，不是資料模型合併。
資料架構仍必須保持：

```
Holding Data
      ↓
Canonical Fund Data
      ↓
Portfolio Aggregation
      ↓
Portfolio Views
```

同一 canonical data 必須供：

* 持股明細
* 資產配置
* AI Brain

使用。
禁止：
資產配置自己再抓第二套基金資料。
我的資產頁建議資訊層
第一層：總覽

* 總資產
* 總損益
* 報酬
* 配息
* 重要偏離

第二層：Visual
優先圖表：

* 核心 / 衛星比例
* 資產類型
* 區域配置
* 幣別曝險
* 基金占比
* 持股損益

第三層
個別持股明細。
Detail

* 公式
* provenance
* Missing 原因
* technical diagnostics

收合。
十四、頁面合併的 SSOT 處理
「資產配置＋我的持股 → 我的資產」可能涉及：

* page count
* page name
* frozen 44
* existing visual blueprint
* routing
* tests

因此：
先做 conflict analysis。
若需要 amendment：
正式建立最小必要 amendment / Decision record。
不得：

* 偷偷改 page count；
* 把歷史 SSOT 刪掉；
* 用 implementation PR 偷帶規格修改。

正式紀錄：
舊規則被哪個新 Decision supersede；
哪些資料 contract 完全不變。
十五、找基金
正式方向：
找基金基本功能 ≠ 候選池。
正確關係：

```
基金搜尋
   ↓
篩選
   ↓
比較
   ↓
可選：加入候選清單
```

候選清單是輸出目的地，不是 prerequisite。
如果沒有候選清單：
主頁可以顯示：
`⬜ 尚未連接候選清單`
`仍可正常搜尋；加入候選暫不可用`
不得整頁鎖死。
但資料來源原則不變
如果 repo 目前實際上沒有已核准基金搜尋資料來源：
不得因本裁示自行創造來源。
此時：

* 搜尋區保持 Missing / Data Gap；
* 說明真正缺的是搜尋資料來源；
* 進 Data Source Decision Gate。

「解除候選池 prerequisite」不等於「虛構搜尋資料來源」。
十六、本次 Migration 禁止順帶修改
不得碰：

* NAV semantics
* canonical identity
* Sheet MoneyDJ base-code contract
* MoneyDJ production resolver
* DG-2 Shadow flag
* NAV precedence
* valuation
* FX
* returns
* 投資公式
* Risk Cap
* 減碼 trigger
* One AI Brain decision behavior
* BL-0509 production source semantics

MoneyDJ probe 與 BL-0509 probe：
維持既有排程背景累積。
十七、與 PR #1104 的關係
#1104 為獨立工作線。
不要把本 Migration 塞進 #1104。
如果 #1104 尚未 merge：
本工作保持獨立。
如果 #1104 已 merge：
重新 fetch main 後再開本工作 branch。
若 #1104 與本 Migration 修改同一 docs / BACKLOG：
merge 後重新 rebase / sync，
不得覆蓋 #1104 正確內容。
十八、BL-0517 三張圖卡 Decision Gate
關於：

* credit spread
* term spread
* policy rate

你回報它們屬於新增視覺元件、需要草稿先行。
裁示：
採方案 A。
先做文字／wireframe 草稿，不直接 production implementation。
而且這三張圖卡必須依新的 Presentation Contract 設計：

* 圖表優先
* metadata chips
* 一句摘要
* provenance / 限制收合

草稿完成後再送客戶看。
此 Decision 與 Presentation Contract Migration 同方向，但：
不要把三張圖卡實作塞入本次 contract migration PR。
十九、第一階段交付
第一階段先完成：

1. Presentation contract inventory
2. A / B / C 分類
3. old contract vs new Visual SSOT conflict matrix
4. Presentation Contract 正式規格
5. Visual Fidelity Gate 正式規格
6. helper migration impact list
7. test migration impact list
8. frozen SSOT amendment list
9. 基金 IA amendment list
10. implementation batch plan

第一階段：
以 docs / spec / impact analysis 為主。
不要直接一次重寫五頁 UI。
二十、後續 Implementation Batch
規格穩定後依序：
Batch A
Presentation helper / tests migration
Batch B
共用：

* chart card
* metadata/status chip
* detail expander
* Missing placeholder

presentation pattern。
Batch C
🌍 市場與趨勢
作為 reference implementation。
因為目前已有可實際驗證的：

* VIX
* TAIEX
* S&P 500
* US10Y
* US2Y

先把這一頁真正校正成：
圖表 > 數字 > 短句 > 長文字
並完成 desktop / mobile Visual Fidelity Gate。
Batch D
💼 我的資產
處理：

* 資產配置＋持股 IA
* contextual Sheet selector
* portfolio visuals

Batch E
🔍 找基金
處理：

* candidate pool decoupling
* contextual candidate Sheet
* search/filter/compare presentation

Batch F
⚙️ 設定＋Account placement

* 設定頁瘦身
* Google account global placement
* desktop / mobile interaction

依 repo dependency 可以微調順序，
但每批仍遵守 Anti-Bloat：
≤3 real work items。
二十一、UI Batch 驗收
每批至少：

1. targeted tests
2. relevant regression
3. desktop screenshot
4. 390px screenshot
5. Visual Fidelity audit
6. 1 組 independent audit
7. CI
8. Auto-Ship 安全條件

Visual audit 必須明確回答：

* 第一屏主要看到的是圖表／數字，還是文字？
* 圖表是否足夠突出？
* 是否仍有文字牆？
* metadata 是否有效取代長句？
* 長文字是否真的下沉？
* Missing 是否簡潔但誠實？
* blueprint hierarchy 是否被保持？
* mobile 是否直覺？
* 是否需要進設定才能完成正常頁面操作？

任一主要問題 FAIL：
不得宣稱該 UI Batch 完成。
二十二、治理要求
不要為這件事建立第二套平行 UI 憲法。
優先：

* amendment 現有正式規格；
* 明確 supersede 舊 presentation-only contract；
* 保留歷史；
* Git history 保留舊版本。

BACKLOG / DECISIONS / HANDOFF：
只做必要同步。
不得為每個 helper / 每個 test 另外新增 Decision。
二十三、Silent Autonomous Cruise
沿用既有正式規則。
不要回報：

* 正在掃
* 已開始
* agent 派出
* PR 開了
* audit 跑了
* CI waiting
* merge waiting
* docs syncing

只有：

1. 真 Decision Gate
2. 真 blocker
3. Model / Effort Change Gate
4. 完整 Batch 完成

才回報。
Context Compaction Gate：
照現有正式規則靜默執行。
二十四、模型與 Effort
目前階段：
Claude Opus 5.5
Effort：High
因為目前工作涉及：

* SSOT precedence
* frozen SSOT
* presentation contract
* test contract
* helper semantics
* IA
* visual hierarchy
* migration sequencing

完成：

* inventory
* conflict matrix
* formal contract
* amendments
* Visual Fidelity Gate

並進入明確、機械式 UI implementation 後：
請走 Model / Effort Change Gate。
建議降為：
Claude Sonnet 5.5
Effort：Medium
純 docs / metadata 機械同步再依 Minimum Sufficient Effort 降低。
不要整個 UI migration 長期維持 Opus + High。
````

## 第三則訊息（客戶 Gate 裁示與追加方向）

````text
先重新做 GitHub Verification Gate。
我方最新實查：

* main：`02615e417700e880796e2fe5251df97a3494183b`
* Open / Draft PR：0
* #1104 已合併，不需要再等待
* 若你查到更新狀態，以 GitHub 最新實況為準

你上一則列出的 5 個 Decision Gate 已經由客戶裁示完成，不要再次詢問：

1. 「資產配置＋我的持股」→ 採 A，正式朝四頁 IA、「💼 我的資產」整合
2. 找基金第一階段 → 採 A，唯讀＋session-only transient filtering
3. 舊 `ui/` compatibility line → 採 A，只遷移 B 線 / vNext
4. Visual Fidelity → production-like Cloud screenshot 為正式確認，CI deterministic screenshot 為自動安全網
5. 找基金搜尋資料來源 → 目前維持 `◇ 資料未備`，另外做 Data Source Decision Gate，不新增外部來源

另：

* frozen 44 僅 amendment presentation responsibility
* Missing 正式字樣仍沿用 `◇ 資料未備`
* BL-0517 三張新圖先 wireframe，不直接 production implementation

現在繼續目前的 Presentation Contract Migration，但補入以下最新正式產品方向。
一、新增核心原則：簡單，但不能失去判斷
新版 UI 不是「圖越多越好」。
正式原則：
Simple Decision Dashboard, not Report Wall and not Chart Wall.
資訊優先級：
圖表 > 數字 > 短句 > 長文字
但每頁必須有明確視覺主次。
每頁 Visual Budget
正常情況：

* 1 個 Primary Visual
* 最多 2～3 個 Secondary Visual
* 3～5 個核心數字 / status chips
* 最多一句主要判讀
* 詳細文字下沉

禁止：

* 第一屏同時出現多個彼此競爭的大圖
* 大量 donut / pie / chart 疊滿整頁
* 把文字牆單純換成 chart wall
* 每個資料欄位都做一張圖

如果一頁無法清楚回答：

1. 第一眼看什麼？
2. 第二眼看什麼？
3. 第三層才看什麼？

則 Visual Fidelity FAIL。
二、全站頁面目標
正式 IA 朝：

1. 🌍 市場與趨勢
2. 💼 我的資產
3. 🔍 找基金
4. 🤖 AI 投資總結
5. ⚙️ 設定

注意：
「🤖 AI 投資總結」是全站唯一 One AI Brain 的整合輸出入口。
如果目前正式 blueprint 把 AI 總結設計成右側區或其他形式，請做 conflict analysis 與最小 amendment；不要直接偷偷新增頁面。
客戶產品意圖是：
AI 總結必須有一個清楚、容易找到的集中入口。
其是否最終為獨立頂層頁、固定右欄或兩者之一，請先依現有 One AI Brain 正式規格盤點；若需要 page-count Decision，整理成單一最小 Gate，不要自行猜。
三、各頁簡化方向
🌍 市場與趨勢
回答：
現在市場環境怎樣？和上次相比有沒有重要變化？
第一屏：

* 3～5 個核心市場狀態 / 數字
* 1 張 Primary Visual
* 1 句市場摘要

Secondary Visual 最多 2～3 張。
VIX、TAIEX、S&P 500、US2Y、US10Y 等資料仍完整保留，但不需要全部同時以大型圖表常駐。
可以採：

* 主圖切換
* 小型 secondary chart
* tabs / segmented control

但不可因 UI 簡化刪除底層資料。
💼 我的資產
回答：
我的錢放在哪？有沒有偏離？哪些持股需要注意？
第一屏：

* 總資產
* 總損益
* 報酬
* 配息
* 一個主要配置狀態
* 1 張 Primary Visual

建議 Primary Visual：
資產配置 / 核心衛星 / 主要曝險三者擇一，以最能回答當期問題者為主。
Secondary Visual 最多 2～3：

* 區域
* 幣別
* 損益分布
* 基金占比

不要全部同時展開。
下方才是持股明細。
「資產配置」保留為我的資產頁內區段，不再是獨立頂層頁。
🔍 找基金
回答：
符合我的條件有哪些？彼此差在哪？
第一屏：

* 搜尋
* 少量核心 filters
* 結果數
* 1 個主要比較視覺或精簡結果表

候選清單不是 prerequisite。
候選 Sheet 未連接時：
不得整頁鎖死。
第一階段仍唯讀：

* 可以讀候選
* 不寫入候選
* transient filters 只在 session 生效

若搜尋資料來源本身未核准：
維持 `◇ 資料未備`；
不能拿候選池缺失冒充搜尋來源缺失。
⚙️ 設定
只保留低頻：

* 新鮮度
* 資料健康
* 規則參數
* 來源診斷
* 進階診斷
* 真正全域設定

Google Login 不應要求使用者進設定完成。
Desktop：
Google account control 固定左側。
Contextual Sheet selector：
放在真正使用 Sheet 的頁面。
四、Decision Digest Contract
這是本輪新增的正式架構要求。
必須把它落 GitHub，不得只記在對話。
核心架構：
Raw Sources
→ Canonical Data
→ Rules / Indicators / Risk Cap
→ Decision Digest
→ One AI Brain
→ UI Local Summary / AI 投資總結
正式硬規則：
Presentation Simplification must never reduce AI Decision Context.
也就是：
UI 可以：

* 壓縮
* 聚合
* 收合
* 少顯示欄位
* 少顯示圖表

但不得因此刪除或降低：

* canonical data
* rule results
* indicator results
* Risk Cap inputs / outputs
* provenance
* source
* as_of
* stale
* missing
* confidence / quality state（若既有 contract 有）
* identity
* relevant history
* AI Decision Context

五、Decision Digest 的責任
Decision Digest 是：
AI 的完整、結構化決策輸入層。
它不是 UI scrape。
AI 不得：

* 從 Streamlit widget 文字反推 canonical data
* 從顏色猜狀態
* 從 UI 隱藏 / 展開狀態決定是否讀資料
* 因 UI 沒顯示某指標就認為該資料不存在

Decision Digest 應直接由：
canonical data + formal rule results
建立。
六、Decision Digest 最低必要欄位
不要現在武斷建立全新巨大 schema。
先盤點 repo 既有資料結構並設計最小契約。
概念上，每個可判斷項至少需保有：

* identifier
* value / result
* unit（如適用）
* source
* as_of
* retrieved_at（如既有）
* stale / freshness state
* missing / unavailable state
* provenance
* rule result
* relevant threshold / policy reference
* confidence / evidence state（僅若既有系統已有正式語意）

Missing 必須保持 Missing。
不得：

* Missing → 0
* Missing → neutral
* not evaluated → safe
* unavailable → HOLD

七、One AI Brain
沿用 repo 已存在的：
One AI Brain, Many Data Views
不是每頁一套 AI。
各頁只提供：

* Data View
* Rule Result
* Local Explanation
* Local AI Summary（若需要）

所有 Local AI Summary 必須來自同一個 Brain / 同一份 Decision Digest 的對應 slice。
不得：
🌍 自己生成一套市場 AI
💼 再生成另一套資產 AI
🔍 再生成另一套基金 AI
而最後彼此結論不一致。
八、🤖 AI 投資總結
全站 AI 最終整合順序維持正式方向：
市場
→ 資產配置 / 我的資產
→ 持股
→ 候選基金
→ Risk Cap
→ 最終行動摘要
畫面本身要極簡。
目標輸出：
市場
一句話
我的資產
一句話
持股
一句話
候選基金
一句話
主要風險
1～3 點
本期行動
最多 3 項
每一句都必須：
`查看依據`
可以回鏈到：
Decision Digest / canonical evidence / rule result。
九、AI 總結頁禁止事項
AI 投資總結不是另一個大型資料頁。
不要：

* 把所有原始圖表複製一次
* 把所有市場資料重新列一次
* 再做一套持股表
* 重複其他頁的所有內容
* 產生大量 AI 長文

它的功能只有：
現在怎麼看 → 為什麼 → 風險在哪 → 是否要行動
證據按需要展開。
十、UI 與 AI 的分離
正式確立：
Data View ≠ Decision Context ≠ AI Output
UI 主畫面可以只顯示 5 個數字。
Decision Digest 可能保留 30+ 項有效資訊。
One AI Brain 可以讀完整 Decision Digest。
因此：
不得因為「使用者看不到」就把該資料從 AI context 移除。
反過來：
也不得因為「AI 需要」就把所有資料全部塞到 UI。
十一、Presentation Contract 再補一條 Guardrail
新增：
Visual Priority does not mean Visual Quantity.
每頁：

* 1 Primary Visual
* ≤3 Secondary Visual
* ≤5 key chips / metrics in first screen
* 1 main summary sentence

超過時優先：

1. 合併
2. 切換
3. 下沉
4. 收合

不是繼續往下堆。
十二、GitHub Durable Memory Contract
這次非常重要。
客戶正式要求：
任何重要裁示、規格、架構、UI 原則、AI Contract、未完成工作，不得只留在 ChatGPT / Claude conversation。
Conversation 不是 SSOT。
GitHub 是 durable memory。
完成任何 Batch 前必須檢查是否需要同步：
`docs/DECISIONS.md`
正式裁示、supersede、amendment。
`PROJECT_RULES.md`
跨 Batch 永久治理規則。
正式 design / architecture spec

* Presentation Contract
* Visual Fidelity
* Decision Digest
* One AI Brain
* IA / blueprint

`docs/BACKLOG.md`
未完成工作、Gate、後續 batch。
`docs/HANDOFF.md`
目前 main、已完成、未完成、唯一下一接手點。
十三、不得只靠 HANDOFF
HANDOFF 只是接手索引。
正式規格必須存在正式文件。
不要把：

* Decision Digest schema
* One AI Brain contract
* UI hierarchy
* Missing contract
* Visual Fidelity rule

只寫 HANDOFF。
HANDOFF 應指向正式 SSOT。
十四、Context Compaction / 對話中斷防遺失
每完成一個實質 Batch：
如果本批產生新的正式知識：
先落 GitHub，再結案。
若 context compaction / 新對話 / 額度中斷：
新 session 應能只靠：

* GitHub current main
* PROJECT_RULES
* DECISIONS
* BACKLOG
* HANDOFF
* 正式 SSOT

完整恢復，而不需要依賴前一段聊天紀錄。
這是本輪驗收條件之一。
十五、本輪不要急著一次實作全部
目前優先順序：
Phase 1
完成 Presentation Contract / Visual Fidelity / IA amendment / Decision Digest Contract 的正式落盤。
Phase 2
helper / test migration。
Phase 3
共用 visual components。
Phase 4
🌍 市場與趨勢 reference implementation。
Phase 5
💼 我的資產。
Phase 6
🔍 找基金。
Phase 7
🤖 One AI Brain / Decision Digest / AI 投資總結實作。
具體依 repo dependency 可調整。
但不要：
因為 AI 總結重要，就在 Decision Digest contract 尚未定義前直接寫 prompt / LLM glue。
十六、AI 實作前的 Stop Gate
如果目前 repo 的 `build_ai_summary`：
只是 holdings digest / 舊 AI summary，
而不是完整全站 Decision Digest，
不得直接把它宣稱為 One AI Brain 完成。
先盤點：

* input
* scope
* provenance
* missing handling
* source freshness
* Risk Cap integration
* cross-page consistency

再判斷：
reuse / refactor / replace。
不得只因函式名稱像 `build_ai_summary` 就認定已符合新架構。
十七、資料治理不變
本輪任何 UI / Decision Digest / AI 改造都不得破壞：

* 資料層 ≠ AI 推理層
* canonical data 只由正式 data pipeline 建立
* AI 只讀
* AI 不回寫 canonical data
* missing ≠ 0
* unavailable ≠ neutral
* not evaluated ≠ safe
* provenance 必須保留
* 顏色不是唯一資訊載體

十八、下一次回報
不要回報零碎進度。
只有：

* 真 Decision Gate
* 真 blocker
* Model / Effort Change Gate
* 完整 Phase / Batch 完成

才回報。
完成第一階段時，回報至少包含：

1. 最新 main / PR
2. Presentation Contract 落點
3. Visual Fidelity Gate 落點
4. IA amendment 落點
5. Decision Digest Contract 落點
6. One AI Brain contract 是否已正式化
7. 哪些舊 DEC 被 supersede
8. 哪些未完成項已進 BACKLOG
9. HANDOFF 是否可在新對話完整恢復
10. 下一個唯一安全接手點

模型 / Effort
目前這一輪仍使用：
Claude Opus 5.5
Effort：High
因為現在仍在處理：

* SSOT precedence
* IA amendment
* Presentation Contract
* Decision Digest architecture
* One AI Brain boundaries
* test contract
* durable-memory governance

當這些全部正式凍結，進入：

* 共用卡片
* chips
* expander
* chart layout
* routing
* 機械式 UI migration

先走 Model / Effort Change Gate，再降：
Claude Sonnet 5.5
Effort：Medium
不要長期用 Opus + High 做機械 UI。
````
