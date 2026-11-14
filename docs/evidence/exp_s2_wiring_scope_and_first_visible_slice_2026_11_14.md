# 🔍 找基金：S2 最小資料接線範圍審核＋第一個可見切片申請（2026-11-14）

> **基準**：main `09227f408932c94b1c278fc99efe9335bc963bc5`（#1245 merge；push CI run `43570786781` success）。docs-only。
> **性質**：**審核稿與申請，不是授權**。S2（`ui_v3` 重用既有 L2 的資料接線）依 `DEC-2026-11-14-04` 須另行審核，S0 通過不自動核准 S2；**未獲授權前不開工、不掛頁、不修改 registry**。不改 `ui_v2`、Old UI、frozen 44、Schema、FX、DG2、公式；BL-0545 BLOCKED；不新增來源／Agent／MCP／付費項目。
> **事實來源**：2026-11-14 兩份獨立唯讀讀碼盤點（L2 契約；`ui_v3` 規範與守衛），皆單組、**未跑任何測試**、「轉紅」類判斷皆 NOT VERIFIED。〔事〕＝讀碼可核；〔推〕＝作者推論；〔Gate〕＝需客戶裁示。檔案引用為「檔案::符號」，不寫行號。
> **品質狀態**：單組作者草稿，尚待非作者獨立 QA（依 `DEC-2026-10-16-05`，涉 data semantics 與身份）。

---

## 一、結論先講

1. **L2 裡沒有任何「D2 已核准且可接值」的資料值欄位**〔事〕。唯一接近的 `nav_orig_ccy`（R-NAV-1）必須與同列 `ccy`、`nav_date` 一起解讀，而兩者（R-NAV-5、R-NAV-2）仍 Pending。選股池代碼（EXP 路徑）也**不在** R-ID-1 的契約範圍（命名空間另案待裁）。
2. 因此今天**唯一同時滿足「不碰 Pending 欄位」「不新增來源／Schema／公式」「有真實行為」**的接線深度是 **T0＝只取選股池代碼，再用既有三態篩選器對代碼做篩選**。它真實但很薄（見第四部分）。
3. 要讓下區真正有用（T1：基本資料欄位可篩選），必須先過兩關：選股池代碼命名空間裁示、profile 各欄的 D2 契約。這兩關不是本稿能解的。
4. **今天沒有零 Gate 的可見切片。** 本稿提出**唯一一個最小 Gate**（第五部分）。

---

## 二、S2 最小接線邊界

### 2.1 可重用的既有 L2（`ui_v3` 只能在 `adapters/` 層 lazy import `services.v2_tables*`，`services.v2_domain*` 可在模組層）

| L2 | 回傳與狀態〔事〕 | S2-T0 是否使用 |
|---|---|---|
| `exp_universe::load_pool_codes(secret_values, ...)` | dict：`status ∈ {ok, pool_not_cloud, failed}`、`codes`、`message`（已遮蔽但含例外型別名等，**不得上畫面**）、`cooling`；只快取 ok（TTL 1 小時）；失敗冷卻 | **是**（母體） |
| `services/v2_domain/rule_filter::apply_rules_tristate` | 回 `(steps, alive, undet)`；`steps` 為**四元組** `(rule, 套用前, 符合, 無法判定)` | **是**（N／M／EXP-7） |
| `rule_filter::rule_is_effective` | 值去空白後非空才生效 | **是**（定義 `conditions_count`） |
| `fund_keys::resolve_full_keys` | 逐檔 full_key；受 R-ID-2／3 Pending（D2-A=B 已知落差） | **否** |
| `exp_profile::build_profiles` | 基本資料；對三個外部來源發網路；欄位逐欄受 D2 Pending | **否**（T1 才用） |
| `exp_nav::load_nav_dividend` | 淨值／配息；`nav_date`／`ccy`／`fetched_at`／`source_tier` 受 R-NAV-2／3／4／5／6 Pending | **否** |
| `settings_store::load_user_settings` | 讀 `user_setting` | **否**（Q-B＝A：不讀歷史設定當初值） |

### 2.2 欄位分類（T0 之外一律不接值）

| 欄位／功能 | 分類 | 依據 |
|---|---|---|
| 選股池 `code` 字串 | **身份阻擋（部分）**：R-ID-1 明文不含 EXP 路徑；T0 只把它當**不透明字串**顯示與篩選，**不宣稱它是 MoneyDJ 基金代碼或已確認身份** | `DEC-2026-11-13-06` (4)、附三；Q3＝A「身份維持 ◇ 尚未確認」 |
| `full_key`／`ok`／`portal` | D2 Pending（R-ID-2／3） | 同上 |
| `fund_name`、`ccy`、`inception_on`、`dividend_policy` | D2 Pending；其中 `inception_on`／`dividend_policy` 作者未找到對應 R- 列 | 盤點；NOT VERIFIED |
| `mgmt_fee_rate_pct` | 恆 `None`（不以最高經理費冒充）→ 真實的「資料未備」來源 | `exp_profile` |
| `nav_date`／`nav_orig_ccy`／`fetched_at`／`source_tier`／dividend 各欄 | D2 Pending；6b 數值接線未核 | `DEC-2026-11-14-02` Q6＝6a |
| `div_ratio_pct` | **非 L2 產物**，算式在 `ui_v2/exp/live.py`；ui_v3 重做＝新增公式；且 C9 禁顯示未核准報酬／績效類數值 | 盤點；`DEC-2026-11-14-02` (8) |
| 歸一化 NAV、報酬 | L2 無基金版；Q5 Formula Gate | 盤點 |
| 跨幣別合計 | 被阻擋：FX 閘門關、ccy Pending | `DEC-2026-11-13-06` 附三 |

### 2.3 狀態區分（讓取數失敗不會變成「尚未設定條件」）〔S2 必驗〕

adapter 回傳**單一 view model**，其 `state` 為互斥列舉；`exp0_conclusion` **只有在 `state==OK` 時才被呼叫**：

| adapter state | 來源（L2 事實） | 畫面（原因代碼，不帶原文） | 是否呼叫 `exp0_conclusion` |
|---|---|---|---|
| `OK` | `status=="ok"` 且 `codes` 非空 | 正常 | **是** |
| `EMPTY_POOL` | `status=="ok"` 且 `codes==[]`（L2 無獨立狀態，adapter 自行判斷） | 選股池是空的（**不併入「沒有符合」**，字樣待定） | 否 |
| `UNAVAILABLE` | `status=="pool_not_cloud"`（未設定選股池或憑證） | `◇ 資料未備`＋原因代碼 | 否 |
| `ERROR` | `status=="failed"`（含 `cooling==True`） | `⛔ … 取數失敗`＋原因代碼；**原文不上畫面** | **否**（絕不傳 `conditions_count=0`） |
| `PARTIAL` | `OK` 且 `M>0`（部分檔無法判定） | 文案接「；另有 M 檔無法判定」 | 是 |

- 〔Gate 內〕「尚未設定條件」**只在 `state==OK` 且生效條件數為 0 時**出現。T0 的 `OK` 判定見上；`UNAVAILABLE`／`ERROR`／`EMPTY_POOL` 即使條件為空也不顯示「尚未設定條件」。
- 與 ui_v2 的分歧〔事〕：ui_v2 的 `has_rules` 是「已存條件列非空」，S0 的 `conditions_count` 定義為**生效條件數**（`rule_is_effective` 為真的列數）。分歧情境＝所有條件列值皆空：ui_v2 視為有條件且 N＝全部母體；S0 視為 0 條件顯示「尚未設定條件」。**本稿採 S0 定義**（已是 `DEC-2026-11-14-04` 的「未填數值條件不生效」），測試須鎖定此差異。

### 2.4 N／M 型別驗證（不得用 `int()` 掩蓋）

- adapter 的 N／M **只能由 `len()`、計數與整數相減得出**（Python `int`），**禁止**對來源值做 `int(x)` 轉型：`float`、`None`、`bool`、`numpy` 整數一律讓 `require_count` 拒絕（`ValueError`），由 adapter 轉成 `ERROR` 狀態而非靜默截斷。
- 測試條件：傳 `3.0`、`None`、`True`、`numpy.int64` 進 adapter 的計數入口，都必須失敗（不得被轉成 3、0、1）。

### 2.5 EXP-7 末列適配 S0（不改 L2）

- `apply_rules_tristate` 的 `steps` 為四元組 `(rule, 套用前, 符合, 無法判定)`；adapter 取 `[(s[2], s[3]) for s in steps]` 組成兩元素列給 `verify_exp7_last_row`。
- **只在 `state==OK` 且生效條件數>0 時呼叫**；無條件或失敗時 `rows` 為空，不呼叫（空列會 `ValueError`）。
- 不使用 EXP-7 block 的 `before_text`／`after_text`（那是千分位字串，不可解析）。

### 2.6 呈現層約束（讀碼所得，S2 施工時必守）

- 失敗原文（`exp_universe.message` 含例外型別名與試算表錯誤文字）**不得進 view model／畫面**（44 P0-①；`no_engineering_leak` 守衛會紅）。
- 「選股池」資料類名、`⬜ 無法判定（資料未備）`、`EMPTY_POOL`、`ERROR` 文案在 `ui_v3` 現有字樣表**沒有**；屬新字樣，已決者（W1、W15、W16、W19 等）走 viewmodel 常數＋「等於核准稿原文」測試，未決者走 `preview_wording` 的 pending 並帶虛線標示。
- 可在 `adapters/` lazy import 的僅 `services.v2_tables*`；`adapters/` **不得 import `shared.*`**；`repositories`／`infra` 不准。

---

## 三、Amendment P1～P4 收斂（本批）

- 依指示 **X1（之十八其八標題行）併入 P2 同節關聯修正**，註記範圍由五處增為六處；**X2～X6 保留待核，不擴大 frozen 44 修改**。草稿 `exp_amendment_p1_p4_verbatim_draft_2026_11_14.md` 已同步（草稿不具效力）。
- **X2（手機首屏結論燈）列入正式 UI 掛頁前的版面驗收，不得忽略**：驗收落點＝新增 browser（slow）測試，量 390px 寬時 `EXP-0` 燈的 `bottom` 不超過視窗高度、燈在條件輸入區之前、無橫向溢出，並附變異驗證。
  - **重要限制**〔事／推〕：只含下區的最小頁會因「沒有上區」而通過此驗收，**不代表完整頁通過**；完整頁（含上區）做出來時必須重量。
- **逐字註記仍須再一輪針對定稿註記句的獨立 QA 與客戶確認，才能修改 44**；本批 44 零修改。

---

## 四、第一個可見的 New UI2 切片（申請稿）：S2-T0「下區最小頁」

### 4.1 可做 ／ 不可做

| 可做（真實行為） | 不可做（本切片不含） |
|---|---|
| 下區 `EXP-0`：依 S0 文案顯示 N／M／尚未設定條件 | 整個上區（單檔查詢、結果卡、歸一化圖、「比較」）：依賴 D2 R-NAV-2／5 與 Formula Gate |
| `EXP-1` 暫時條件輸入（本次瀏覽、不存檔、不讀歷史 `user_setting`）；**可選欄位僅 `fund_code`**（eq／ne），其餘欄位在 T0 恆無法判定、不開放 | `EXP-3`「對照」（需 `nav_date`／`nav_orig_ccy`／`div_ratio_pct`，皆 Pending） |
| `EXP-2` 清單：每列一個代碼，其餘欄位 `◇ 資料未備`；列數＝N＋M；無法判定者標 `⬜ 無法判定（資料未備）`；同值以 `fund_code` 字面值升冪 | 任何 profile／NAV／配息欄位的值；來源與取得時間展開（沒有值可展開） |
| `EXP-7` 篩選軌跡（三數；末列＝N、M） | `EXP-4`（欄位勾選與排序）：T0 只有代碼一欄，勾選與排序無意義，**不做假控制項** |
| 四種狀態（OK／EMPTY_POOL／UNAVAILABLE／ERROR）互斥且原文不外洩 | `EXP-5`、候選清單、`EXP-6`、跨幣別合計、任何報酬／績效／排名語意 |
| 暫時狀態提示句（W19）、分隔小標題（W15）、頁尾句（W16 第 2 式） | 掛上正式入口、`ui_v2`／Old UI 變更 |

〔推〕**誠實評價**：T0 的真實價值很低——只能對「代碼字串」做等於／不等於，其餘欄位都是 `資料未備`。它的作用是：(1) 驗證 ui_v3 的接線、狀態區分、暫時條件與 S0 契約能端到端運作；(2) 讓版面與 X2 首屏驗收有真實頁可量。**它不是完整的 🔍 找基金，不得宣稱頁面功能完成**；是否值得做，由客戶在第五部分決定。

### 4.2 預計修改檔案〔推，未驗；來源：兩份讀碼盤點〕

| 類別 | 檔案 |
|---|---|
| 新增 | `ui_v3/adapters/exp_page.py`、`ui_v3/viewmodels/exp_page.py`、`ui_v3/pages/exp.py`、`tests/ui_v3/exp_stubs.py`、`tests/ui_v3/test_ui_v3_exp_page_{adapter,viewmodel,apptest,browser}.py` |
| 修改（production） | `ui_v3/shell/registry.py`（exp 改 `registered=True`，同時移除 `unregistered_reason`）、`ui_v3/app_preview.py`（加 `_render_exp` renderer）、`ui_v3/adapters/shell_status.py`（exp 的資料狀態來源）、`ui_v3/viewmodels/preview_wording.py`（新字樣） |
| 修改（既有測試；**掛載後會轉紅，須改成預期含 exp，不得放寬或刪斷言**） | `test_ui_v3_page_registry_guard.py`、`test_ui_v3_navigation_shell.py`（多處）、`test_ui_v3_assets_source_import_isolation.py`（**前稿預填清單漏列**）、`test_ui_v3_top_nav_browser.py`（slow，第 3 格由「開發中」變可進連結、頁首可聚焦者變 2 個）；另建議擴充 token／CJK／leak 三個守衛納入 exp 頁 |
| 不得動 | `ui_v2`、`ui/`、`services/`、`repositories/`、Schema、frozen 44、`.github/workflows/` |

### 4.3 資料來源與失敗狀態

- 來源：`exp_universe.load_pool_codes`（讀 Google Sheet 選股池）＋ `rule_filter.apply_rules_tristate`（純計算）。**不新增來源、Schema、公式。**
- 失敗狀態：見 §2.3。**Preview 部署端是否有選股池服務帳戶憑證 NOT VERIFIED**——沒有憑證時頁面會落在 `UNAVAILABLE`，實質是一個沒有可調條件的失敗頁，**等同空殼**；施工前須先確認憑證，否則第五部分的 Gate 應改選「暫緩」。

### 4.4 測試、非作者 QA、回滾

- 測試：adapter 純邏輯（stub 餵 L2 輸出，驗 N／M／N＋M、steps→EXP-7、四種狀態互斥、`int` 型別拒絕、原文不外洩、`services.v2_tables` 僅於 `load()` 內載入）；view model 建構驗證；AppTest（調條件後 N／M 改變、不出現「查無基金」「存檔」）；browser（390／768／1280：燈在首屏、DOM 順序、無橫向溢出、離開本頁再回來條件回初始〔L7〕、變異驗證）。
- 非作者 QA 重點：授權（Gate 是否已有客戶明示）；有無假控制項；失敗原文外洩；暫時狀態是否寫入／讀取 `user_setting`；M 不被當成符合／0；既有守衛是否被削弱；燈色對應；新字樣狀態；X2 結論燈是否因無上區而過；選股池代碼不得套用 R-ID-1 契約文字。
- 回滾：單一 PR 一般 merge，`revert` 整個 PR（連同被改的既有測試一起還原）；僅影響 Preview（守衛確保無正式入口引用 `ui_v3`）；暫時狀態不寫持久層，無資料回滾。

---

## 五、需要客戶核准的唯一最小 Gate

**一句話請示**：是否核准「S2-T0」＝在 `ui_v3` 新增 🔍 下區最小頁（僅 §4.1「可做」欄），資料只重用 `exp_universe`＋`rule_filter`，選股池代碼**僅作不透明字串顯示與篩選、不宣稱身份、不套 R-ID-1**，並接受它**沒有上區、沒有 EXP-3／EXP-4、只能篩代碼**。

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| A　核准 S2-T0 | 依 §4 施工，獨立 PR、非作者 QA、exact-head CI | 最早有可見頁；驗證 ui_v3 接線、狀態區分、X2 首屏；範圍最小 | 價值薄（只能篩代碼）；Preview 無憑證則等同空殼；需改 4 支既有測試與 registry | 中：憑證未驗；被誤讀為「🔍 頁面完成」 |
| B　暫緩，先裁選股池代碼命名空間與 profile 欄位的 D2 契約，再做 T1 | 不做 T0 | 一次做出有用的頁（基本資料可篩選）；不產生薄頁 | 時間較長；D2 其餘列與命名空間仍待客戶 | 低 |
| C　核准 A，並同時另開選股池代碼命名空間裁示 | A＋平行推動 B 的前置 | 不浪費等待時間；T0 接線可被 T1 直接擴充 | 同時兩條線，需客戶多做一個裁示 | 中低 |

**AI 總管推薦：C。** 理由〔推〕：T0 的接線、狀態區分與 X2 驗收是 T1 的必經基礎，早做早驗；命名空間是 T1 的真正瓶頸，應平行啟動。**但前提是先確認 Preview 有選股池憑證**——若確認沒有，推薦改為 B。此為作者推論，客戶可選任一。

不屬於本 Gate、仍擋著：Q5 Formula Gate、R-NAV-2／5、EXP-6、BL-0545。frozen 44 的 amendment 另走原 Gate（P1～P4＋X1），**與本 Gate 互不阻擋，但完整頁（含上區）掛頁前必須完成**。

---

## 六、我沒有驗證的部分

1. 兩份盤點皆為單組讀碼：L2 契約、守衛轉紅判斷、`ui_v3` 層規則、「ui_v3 無 text_input／multiselect 先例」等**未實跑任何測試**；`AppTest` 在 `st.navigation` 下切頁、Streamlit 切頁後 `session_state` 清除行為未驗證。
2. Preview 部署端是否有選股池服務帳戶憑證：未驗證。
3. `inception_on`／`dividend_policy` 是否有對應 D2 R- 列：未找到，非「確定沒有」。
4. 空池在 `ui_v2/exp/page.py` 是否另有處理：單組字面搜尋。
5. 預填檔案與轉紅測試清單可能仍有遺漏；全稱句（「L2 沒有 D2 已核准且可接值的欄位」「ui_v3 沒有 text_input 先例」）皆單組搜尋，**未經第二組驗證，不得引用為已查證事實**。
6. 新字樣的核准狀態（W 各項）未逐一對照。
7. 本稿單組作者草稿，尚待非作者獨立 QA。
