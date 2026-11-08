# D2 正式資料契約候選整理：報酬算法（A）／基金身份（A）／持倉占比（C）

> **基準 `origin/main` 85a158bb；單組作者草稿；獨立 QA 已完成一輪並已回修（非 QA 通過；本輪最後小修由專案 AI 自驗 delta）；候選非核准；不構成正式 Schema／契約／裁示。**
> 本檔彙整三份作者草稿（E1 報酬、E2 身份、E3 持倉；原文不改寫，只調整標題層級並加註記），並附「對 #1177 草案的更正」與「下一批最值得核准事項」。
> 客戶 2026-11-08 方向（經總管轉達的**要點轉述，非逐字，客戶可推翻**）：報酬算法選 A、基金身份選 A、持倉占比選 C；**只授權整理正式資料契約候選與裁示登記，不授權新公式、程式施工、FX 開閘或啟動 OneBrain**。登記見 `docs/DECISIONS.md` `DEC-2026-11-08-05`。
> 標記沿用三草稿：FACT／【F】＝可由所引檔案重現；INFERENCE／【I】＝作者推得；NOT VERIFIED／【NV】＝未查證。三部分各自有分類欄（Required／Optional／Excluded／Pending），皆為**作者候選**，客戶逐類核可前不具效力。
> **用語**：「成本」一詞在客戶確認「淨投資金額＝成本」前，一律指「淨投資金額（暫稱成本）」，不是已確認的成本語意。
> **閱讀約定**：各部內文的「§n」「第 n 節」「列 n」一律指**該部自己的節號**（三部節號各自從 0 起算、互不指涉）；原文中「待總管／文件組另行登記」「本檔不寫入 DECISIONS」等句寫於登記前，現已以 `DEC-2026-11-08-05` 登記，原句保留不改。

## 0. 結論先行（白話；只取自三份草稿，不新增結論）

**報酬算法（方案 A）。** 「1 年含息報酬」的算法**已有客戶裁示**（`DEC-2026-10-23-02` 1B：配息還原淨值法為唯一正式算法、官方值只對帳、資料不足顯示「資料未備／無法判定」），所以能形成契約候選；但該裁示的落地範圍寫明是舊站，**延伸到新資料契約尚需客戶正式核准**。此外 `docs/BACKLOG.md` BL-0427（待客戶裁示）另登記該算法的公式層未決題：配息落在非淨值日時還原偏低、日曆日頻序列 `window_days`≈251 恆 unavailable、350 天只是下限而擋不住稀疏序列、配息日期取值口徑（(1)(3)(4)(5)，皆屬正式公式／窗口定義、未授權改）。1 個月、3 個月、6 個月與價格報酬**無唯一核准算法**，只能並列現況、各標算法名稱。現有 1Y 含息輸出**尚缺窗口起訖日、資料末端日期、取得時間**，也不含計價幣別與算法版本（算法版本欄是否需要尚未裁）；補欄要改程式，不在本次授權內。同一基金的「1Y」現況至少並存五套數字，契約若不逐欄標口徑會被混讀。

**基金身份（方案 A）。** 契約候選只收現行取數鍵：輸入的 `fund_code`、取數用的 `full_key`、解析成功旗標 `ok`（共 3 個 Required 候選）；標準化基金身份（`base_fund_code`／`canonical_key` 等）尚在 Shadow、不影響 production、不升格為正式身份，不改 Sheet schema 與 NAV 來源優先序。尚未裁的最大問題：**取數用代碼（`full_key`）能不能帶通路後綴**（今日程式接受，而既有裁示要求 Sheet 欄遇後綴標 `sheet_code_contract_violation`，但 production 路徑打不出這個標記；Shadow 旗標預設關閉時該 hook 根本不執行）。別名表是否屬契約、MoneyDJ 頁型是否入契約、標準化代碼轉正所需的 Stage-2 驗證（V1～V13）皆未備；跨畫面認同目前仍靠現行取數鍵。

**持倉（占比方案 C＝延後）。** 暫不收「類別占比契約」（延後不等於排除，不刪既有程式與歷史計算）。能形成契約候選的是：持有單位、台幣淨投資金額（暫稱成本）、幣別、類別、**各類別淨投資金額（暫稱成本）**（此基準不讀淨值與匯率，不受 FX 閘門影響，非台幣基金亦可入；**但依賴類別名稱設定 `bucket_names`**，未設定時全部歸「未分類」）、來源完整性與缺資料原因。目前缺口／限制：**占比／分母／完整 100% 尚未裁（延後）**、**市值面**受 NAV 10 日規則與 FX 閘門擋住、「**淨投資金額＝成本**」語意 repo 文件未見明文（作者已降為備註，非阻塞）、**真實使用者持倉覆蓋率 NOT VERIFIED**。歷史授權鏈（`DEC-2026-11-05-02`／`-04`）仍為「未重新追認」，其規則不得寫成「已追認」。

### 三類總覽表

| 類別 | 客戶方向（要點轉述） | 已能形成契約候選的 | 候選規模（作者自計） | 主要缺口／待裁 | 目前缺口／限制 | 詳見 |
|---|---|---|---|---|---|---|
| 報酬算法 | 方案 A：1Y 含息列入契約候選（請客戶確認可延伸），其他期間與價格報酬並列標算法、不選唯一正式 | 1Y 含息 `value_pct`／`ccy`／`source`／`window_days`／`status`／`reason` 等 | 24 列（Required 8 列） | 跨新版適用待核准；BL-0427 公式層未決；窗口起訖日、資料末端日期、取得時間缺口；1M／3M／6M 口徑未裁（BL-0524） | 1M／3M／6M／價格報酬無唯一核准算法；無 TWD 換算後報酬輸出（FX 閘門關閉）；多套「1Y」並存 | 第一部 |
| 基金身份 | 方案 A：只收現行取數鍵；標準化身份續 Shadow；不改 Sheet schema／NAV 優先序 | `fund_code`、`full_key`、`ok`（Required）；診斷欄為 Optional | 27 列（Required 3、Optional 4、Excluded 15、Pending 5） | `full_key` 可否帶後綴（S7）；別名表（K11）、頁型（K12）；幣別／出處／名稱歸 NAV／profile 契約（K13～K15）；Stage-2 條件 V1～V13 | 標準化身份、通路後綴、ISIN、share class 等為 Excluded／Unknown；標準化代碼尚在 Shadow | 第二部 |
| 持倉 | 方案 C：延後類別占比契約；只整理單位、成本、類別金額與缺資料原因 | 單位數、台幣淨投資金額（暫稱成本）、幣別、類別、各類別淨投資金額（暫稱成本；依賴 `bucket_names`）、來源完整性、缺資料原因 | 30 列候選項目（§2.A 11＋§2.B 5＋§2.C 6＋§2.D 8） | 「淨投資金額＝成本」語意（X10）；根層資料時點缺；11 項 open gate；授權鏈未追認 | 占比／分母／完整 100% 延後；市值面與 FX；覆蓋率 NOT VERIFIED | 第三部 |

---

## 第一部｜E1 報酬算法（方案 A）

### E1｜報酬算法（方案 A）正式資料契約候選與裁示登記草稿

> 基準 `origin/main` = `85a158bb6ca42066862d1563bb6549fa4304a28c`（2026-11-08 已 `git fetch`；一律 `git show`／`git grep origin/main` 唯讀）。作者：單組，之後有獨立 QA；本檔**未經任何第二組複驗**。
> **性質**：純文件**候選**。**不是**正式契約、**不是**核准、**不新增**公式／報酬窗／門檻／年化方式／還原方法／狀態詞，**不授權**程式施工、FX 開閘、OneBrain、Digest 實作。
> 標記：FACT＝讀碼／讀文件可重現；INFERENCE＝作者推得；NOT VERIFIED＝未查證或原文未定。來源只寫「檔名＋符號／節名」。
> 客戶授權範圍（任務單轉述，非逐字）：「報酬算法選方案 A；這次只授權整理正式資料契約候選與裁示登記，不授權新公式、程式施工、FX 開閘或啟動 OneBrain」。

#### 0. 結論先行

1. 【FACT】方案 A 的字面（`d2_draft_C_customer_decision_list` 題 1）：1 年含息報酬照已有裁示列入契約（請客戶確認可延伸）；1M／3M／6M 與價格報酬並列、各標算法名稱，**不選唯一正式算法**。本檔照此分兩張表：§1「1 年含息」候選欄位；§2「1M／3M／6M／價格報酬」只列現況並存。
2. 【FACT】**「客戶選方案 A」在 repo 內尚無對應 DEC**：`docs/DECISIONS.md` 只有 `DEC-2026-11-08-04`（Q1–Q5 方向，未提題 1 方案），`git grep` 方案 A／題 1 無相關登記。本檔所有「方案 A」依據僅為任務單轉述【NOT VERIFIED，待總管／文件組另行登記】。（**已登記，見 `DEC-2026-11-08-05`**；本句寫於登記前。）
3. 【FACT】1Y 含息的**算法裁示已存在**：`DEC-2026-10-23-02` 1B（基金層唯一 SSOT＝配息還原淨值法、官方值只對帳、資料不足→「⬜ 資料未備／無法判定」、不得 fallback 為純 NAV／0／中性／估算）。【FACT】同筆「影響範圍」寫明落地在 `services/`、`ui/` **舊站 consumer**，**不改 `ui_v2/`**；`DEC-2026-10-23-06` 同為 `ui_v2/` 不改。⇒ **跨新版契約是否適用，裁示沒有講，本檔不擴大解讀**，一律標「擬沿用的唯一正式算法候選（跨新版適用範圍仍需正式核准）」。 【FACT】另 `docs/BACKLOG.md` BL-0427（待客戶裁示）登記該算法公式層未決：(1) 配息落在非淨值日時還原低估；(3) 日曆日頻序列 `window_days`≈251 恆 unavailable；(4) 350 天只是下限、擋不住稀疏序列；(5) 配息日期取值口徑（`date` 優先、缺才退 `ex_date`，而 MoneyDJ 解析器中 `date` 為配息基準日、`ex_date` 為除息日）；皆「正式公式／窗口定義，未授權改」。故「唯一正式算法候選」不等於公式層已定案。
4. 【FACT】既有 1Y 含息實作只在舊站：`services/fund_total_return.py::resolve_1y_total_return` 與 `services/fund_service.py::calc_metrics`／`calculate_fund_total_return`；`git grep resolve_1y_total_return|ret_1y_total|compute_1y_total_return -- services/v2_tables services/v2_domain ui_v2 ui_v3` **0 命中**（本次重跑）。新版線 C 沒有對應輸出。
5. 【FACT】**契約候選欄位有缺口**（既有 `resolve_1y_total_return` 輸出沒有）：窗口起訖日、資料末端日期（as_of）、取得時間；它只輸出 `window_days`；另輸出也不含計價幣別（列 3）與算法版本（列 5）。補這些要改程式，**不在本次授權內**，只登記為缺口（§1 列 3、5、7～9）。
6. 【FACT】更正前稿：`d2_draft_A1` C4 把 6 個字串都稱為 `reason` 值；實際 `UNAVAILABLE_REASON_TEXT` 有 6 個**文字鍵**，但 `reason` **只會輸出 5 種**（`no_series`／`no_restored_value`／`window_short`／`window_unknown`／`dividend_data_missing`）；`dividend_data_missing_unaligned` 只是 `dividend_data_missing` 的白話變體（`_unavailable(..., text_key=...)`，`reason` 仍是 `dividend_data_missing`）。
7. 【INFERENCE】最大風險不是缺欄位，而是「同一基金同名『1Y』並存多套數字」（§3），契約若不逐欄標算法，會被混讀。

#### 1. 「1 年含息報酬」契約候選欄位（共 24 列）

欄：候選資料（既有符號）｜內容與單位｜來源｜缺漏原因／缺值影響｜依據（支持度）｜候選分類（**作者候選，非核准**）｜標記。
「缺漏原因」只用既有字樣（`⬜ 資料未備／無法判定`）與既有原因碼；缺值影響用既有語意（不補 0、不以他算法替代）。

**支持度圖例**：【既裁】＝已由既有裁示支持（舊站範圍）；【候選】＝僅本次文件候選；【待裁】＝待裁示（附 DEC／節）。

| # | 候選資料 | 內容與單位 | 來源 | 缺漏原因／缺值影響 | 依據（支持度） | 候選分類 | 標記 |
|---|---|---|---|---|---|---|---|
| 1 | 基金身份 `fund_code` | 列主鍵 | 持倉 Sheet「基金代號」／呼叫端（A1 A1） | 無法掛到基金 → 結論只能「無法判定」 | 【候選】；身份鍵以何者為準＝題 2（D2／D9）【待裁】 | Required | FACT（既有欄）／INFERENCE（分類） |
| 2 | 1Y 含息報酬值 `value_pct` | 百分點；`calc_metrics` 內 `round((adj_end/adj_start−1)×100, 2)`；**原幣**淨值還原，無 TWD 換算 | `resolve_1y_total_return` ← `calc_metrics`→`calculate_fund_total_return`（Adj_NAV＝NAV×累積因子，因子＝1＋配息/當日 NAV） | `status=unavailable` 時 `value_pct=None`；**不補 0、不退純 NAV、不外推年化** | 算法【既裁】`DEC-2026-10-23-02` 1B（舊站範圍）；公式層另有 BL-0427 (1)(3)(4)(5) 未裁【待裁】；收入新契約／跨新版【待裁】（方案 A 要求客戶確認可延伸；`DEC-2026-10-23-02` 影響範圍＝舊站、不改 `ui_v2/`） | Required；**擬沿用的唯一正式算法候選（跨新版適用範圍仍需正式核准）** | FACT |
| 3 | 計價幣別 `ccy`（說明報酬基準為原幣） | 字串；本值為原幣百分比，非 TWD 報酬 | `nav.ccy`／`fund_profile.ccy`（A1 A9）；`resolve_1y_total_return` **輸出不含 ccy** | 幣別缺或衝突→**新版 nav 表**該檔淨值整批不寫（`nav_dividend.py`）；舊站 `calc_metrics`→`resolve_1y_total_return` 不使用 `ccy`，故不會因幣別缺而算不出 1Y | Q5（原幣可整理）【既裁，要點轉述】；「把 `ccy` 列為 1Y 契約 Required」是**作者候選，不是現有行為**【候選】 | Required（說明「原幣」基準；缺則百分比不可被誤讀為 TWD） | FACT（輸出無 ccy）／INFERENCE（分類） |
| 4 | 計算口徑標識 `source` | 字串：有值＝`自算（還原含息淨值）`（`SRC_SELF_RESTORED`）；無值＝`—`（`SRC_NONE`） | 常數定義於 `services/fund_total_return.py` | 缺口徑→不同口徑的值被混讀（G-RET-2 病徵） | 純 NAV／外推不得掛「含息」名【既裁】1B；收入契約【候選】 | Required | FACT |
| 5 | 算法版本／識別碼（algorithm id／rule_version） | **既有輸出沒有**；`rule_version` 全 repo 零命中（`docs/v2/67` §5.3 表） | — | 無此欄→口徑只靠 `source` 文字辨識 | 【待裁】是否需要＝Digest／Rule 層議題（`67` §8.6 Rule 群、BL-0527）；本檔**不新增** | Pending | FACT（無此欄）／NOT VERIFIED（是否需要） |
| 6 | 窗口天數 `window_days`（←`ret_1y_window_days`） | 整數日曆天；窗首＝倒數第 252 列淨值日（列數 ≥252 時）或整段序列（<252 列且跨度 ≥30 天時）至末筆 | `calc_metrics`；門檻 `RET_1Y_RESTORED_MIN_WINDOW_DAYS`＝350（`shared/signal_thresholds.py`） | 窗口 <350 天→`window_short`；有值但無窗口證據→`window_unknown`；不讓短窗值冒充一年 | 350 天為既有 SSOT 常數【既有，核准依據 NOT VERIFIED】（A1 C4）；BL-0427 (3)(4) 登記此窗口定義的未決題（恆 unavailable／擋不住稀疏）；收入契約【候選】 | Required（沒有期間的報酬無法解讀；A1 C8 同向） | FACT |
| 7 | 窗口起訖日（起日、迄日） | **既有輸出沒有**；`calc_metrics` 內部有 `_window_start_dt`，未輸出 | — | 缺→只能靠 `window_days` 回推，不可驗證起日 | 【待裁】：是否要求輸出＝需改程式，**本次不授權**，僅登記缺口 | Pending（缺口） | FACT（內部有、輸出無） |
| 8 | 資料末端日期 `as_of`（最後淨值日） | **`resolve_1y_total_return` 輸出沒有**；來源淨值列有 `nav_date`（Preview `contract.NAV_FIELDS`；舊站 `nav_date`） | NAV 序列 | 缺→1Y 值無法對應「截至哪天」 | `67` §8.6 把 as_of 列 Required 例【既有文件，非核准清單】；由誰提供【待裁】 | Required 候選（缺口） | FACT／INFERENCE |
| 9 | 取得時間 `fetched_at` | **輸出沒有**；NAV 列有 `fetched_at`（`contract.NAV_FIELDS`） | NAV 列 | 缺→無法判斷資料多舊 | 【待裁】（Freshness 門檻另案：`stale_after` 值待裁，`67` §8.5） | Optional／Pending | FACT |
| 10 | 健康狀態 `status` | 既有二值：`ok`／`unavailable` | `resolve_1y_total_return` | `unavailable`＝缺資料 | Q4（`DEC-2026-11-08-04`）管的是缺資料字樣與不新增「過期／衝突」詞、不改門檻，**不直接核准 `ok`／`unavailable` 兩值**；是否採 `ok`／`unavailable` 當契約狀態字彙＝D3(a)／(b)【待裁】 | Required | FACT |
| 11 | 缺漏原因碼 `reason` | **只會輸出 5 種**：`no_series`、`no_restored_value`、`window_short`、`window_unknown`、`dividend_data_missing` | `_unavailable()` | 對應白話原因見 `UNAVAILABLE_REASON_TEXT` | 原因碼為既有；1B 要求「資料不足→資料未備／無法判定」【既裁】；收入契約【候選】 | Required（當 `status=unavailable`） | FACT |
| 12 | 缺漏原因白話全句 `label` | `⬜ 資料未備／無法判定（原因）`；有值時為口徑字串＋可能的「⚠️ 數值異常大」警語 | 同上 | — | 屬呈現層；`67` §5.2 第 3 點（執行組讀法，可推翻）：`value_text` 類字串不得當值來源 | Excluded（全句）；但**字樣「資料未備／無法判定」沿用**（Q4） | FACT／INFERENCE |
| 13 | 窗內配息筆數 `div_count_in_window` | 整數或 `None`（`None`＝窗口未建，非 0） | `calc_metrics.ret_1y_div_count`（從還原表 `Dividend>0` 數） | 配息型且＝0→`dividend_data_missing`（配息資料未備） | 配息閘門屬 1B 落地內容（**依據出自程式註解**，裁示原文逐字未核對）【舊站範圍】；收入契約【候選】 | Optional | FACT |
| 14 | 配息型判斷（`is_dividend_fund`／`dividend_policy`） | 閘門輸入：配息型＋窗內 0 筆→不判 | `services/fund_total_return.py::is_dividend_fund`；`exp_profile.py` `dividend_policy`（A1 A12） | 判斷缺→配息閘門無法啟動 | 配息頻率對照表為客戶 2026-09-26 定案（檔註，DEC 編號 NOT VERIFIED，A1 A12）；納入 Digest【待裁】 | Optional／Pending | FACT／NOT VERIFIED |
| 15 | MoneyDJ 官方 1Y `official_1y_pct` | 百分點（MoneyDJ 頁面值）；僅 `perf_source=="wb01"` 時取 `perf["1Y"]`；送對帳時才 ÷100 轉小數 | `resolve_1y_total_return` | 缺→只少一個對照，不影響自算值；**另見 §2 M3：在 `fetch_fund_from_moneydj_url` 路徑，wb01 只回部分期間時 `perf["1Y"]` 可能仍是 wb07 值而被當官方值（讀碼，未實跑）** | **只作對帳**【既裁】1B；引 DEC：`DEC-2026-10-23-02` | Optional（僅對帳；**不得當主值**） | FACT |
| 16 | 對帳結果 `ret_1y_reconcile` | `agree`／`disagree`／`a_missing`／`b_missing`／`both_missing` | `services/reconcile.py::reconcile_fund_annual_return`；`fund_service.finalize_fund_metrics` 注入 | 缺→少第二算法交叉檢查 | 對帳義務＝`CLAUDE.md` §4.3；**容差（abs 0.005／rel 0.05，小數制）是否為客戶核准門檻 NOT VERIFIED**；僅舊站 | Optional | FACT／NOT VERIFIED |
| 17 | 離譜值旗標 `is_implausible_1y` | 布林；超出 `RET_1Y_PLAUSIBLE_*` 範圍→label 加警語 | `services/fund_total_return.py` | — | 該範圍的核准依據 NOT VERIFIED（A1 C9） | Optional／Pending | FACT／NOT VERIFIED |
| 18 | 輸入淨值序列的來源與歷史合併 | 舊站序列合併 Google Sheet `nav_history`（同日 live 勝出）；vNext 關閉（`NAV_HISTORY_PROVENANCE_VERIFIED=False`）；A 鏈 waterfall 對不完整結果不快取 | `docs/v2/69` G-NAV-2、G-NAV-9（引，未重驗） | 同一基金新舊站輸入序列不同→1Y 可能不同 | 【待裁】`docs/v2/69` G-NAV-2（source precedence）／BL-0524 | Pending | 引文，NOT VERIFIED |
| 19 | 純淨值 1Y（`ret_1y`，252 列價格報酬）或官方 `perf["1Y"]` **冒充**含息值 | — | `calc_metrics`／MoneyDJ | — | **不得**【既裁】1B（純 NAV 不得掛含息名；不得 fallback） | Excluded（作為含息值） | FACT |
| 20 | 外推年化／短窗累積／舊四層 fallback | `SRC_SELF_ANNUALIZED`、`SRC_SELF_TOTAL`、`SRC_TOO_SHORT` 等舊標籤，僅相容保留，已不由 SSOT 產出 | `services/fund_total_return.py` 常數與檔頭 | — | 已退役【既裁】1B | Excluded | FACT |
| 21 | 持有期間年化／相對買入成本／帳本 TWD 報酬 | 💼 持股層 | `get_latest_nav` 市值等（引 `69`） | — | **不得稱基金層 1Y 含息**【既裁】1B；持倉域另判 | Excluded（作為基金層 1Y） | FACT |
| 22 | TWD 換算後的 1Y 含息報酬 | — | 無（現況無此輸出） | — | FX 閘門關閉（`DEC-2026-11-08-02`；`FX_OBS_DATE_RULE_VERIFIED=False`）；本檔不開閘、不新增 | Excluded／Pending（本輪不處理） | FACT |
| 23 | 顯示字串 `value_text` | 格式化字串 | UI 呈現層 | — | `67` §5.2 第 3 點（執行組讀法，可推翻） | Excluded | FACT |
| 24 | `confidence` | — | — | — | `67` §5.3：條件不成立，不納入（可算客戶核准方向） | Excluded | FACT |

> 列數核對：§1 共 24 列。分類以各列「候選分類」欄為準（Required 類：#1、#2、#3、#4、#6、#8、#10、#11；Optional 類：#9、#13～#17；Pending 類：#5、#7、#18；Excluded 類：#12、#19～#24，其中 #22 兼 Pending）。

#### 2. 1M／3M／6M 與價格報酬：現有各算法與口徑（只列並存，不選唯一、不統一）

**命名說明**：方案 A 要求「各標算法名稱」。本表「算法識別」欄只是**以既有函式／欄位名描述**，**不是**新立的正式名稱；正式命名【待裁】。

| # | 算法識別（描述用） | 實作位置 | 窗口 | 含息與否 | 幣別 | 缺值行為 | 出現處 | 狀態與標記 |
|---|---|---|---|---|---|---|---|---|
| M1 | 列數窗價格報酬 `ret_1w／ret_1m／ret_3m／ret_6m／ret_1y` | `services/fund_service.py::calc_metrics` 內 `_ret(n)`：n＝6／22／65／130／252 列；`(now−s[−n])/s[−n]×100`，`round(,2)` | **以列數**，無日曆跨度護欄；稀疏／週頻序列時「1M」可能不是一個月（G-RET-3，引，未重驗；BL-0520 實測週頻 22 列＝22 週，引） | **否**（純淨值；`ret_1y_total` 才是含息） | 原幣 | 列數不足或基準≤0→`None` | 舊站健診／衛星戰情室（引 `69`）、tab2 快照（引） | 【待裁】BL-0524／D2；FACT（公式）／引文（出現處） |
| M2 | MoneyDJ 官方績效 `perf["1M"／"3M"／"6M"／"1Y"／"3Y"／"5Y"]`（wb01） | `repositories/fund/fund_orchestration.py`（`fetch_performance_wb01`；`perf_source="wb01"`）；`ui/views/page_03_research.py::PERF_PERIODS` 顯示 | 由 MoneyDJ 頁面定義（本組未讀其期間定義）【NOT VERIFIED】 | 程式註解稱「含息總報酬率 wb01（MoneyDJ 說明：已考慮配息）」；`fund_total_return.py` 檔頭稱「官方複利」。【FACT 為註解字面；MoneyDJ 實際定義 NOT VERIFIED】 | 原幣（引 `69`） | 境內基金 `_fetch_domestic_perf` 恆回空（引 `69`，未重驗） | ⑧ 單檔深度、舊健診表 | 1Y 僅作對帳【既裁】1B；1M／3M／6M 作為主值**無核准紀錄**【NOT VERIFIED，A1 C5】 |
| M3 | wb07 同類比較備援 `perf["1Y"]` | `fund_orchestration.py`（**僅 `fetch_fund_from_moneydj_url` 路徑**）：先由 `peer_compare` 取基金列首值寫入 `perf["1Y"]`，wb01 有回才覆蓋並設 `perf_source="wb01"` | 未定義 | 不明 | 原幣 | wb01 缺時 `perf["1Y"]` 可能殘留 wb07 值、`perf_source` 非 wb01 | `page_03_research.py::_perf_lines` 讀 `perf` 顯示（不分來源） | 【FACT】程式路徑；【INFERENCE】⑧ 的「近 1 年」在 wb01 缺時可能顯示 wb07 值而不標來源，**本組未實跑**；**更嚴重變體（讀碼推論，未實跑）**：`fund_orchestration` 先把 wb07 `peer_compare` 首值寫入 `perf["1Y"]`，`fetch_performance_wb01` 只要回非空 dict（例如只抓到 1M／3M，沒有 1Y）即設 `perf_source="wb01"`，但 `perf["1Y"]` 仍是 wb07 值；`resolve_1y_total_return` 的 `official_1y_pct`（只看 `perf_source=="wb01"`）與 `finalize_fund_metrics` 的對帳判斷 `_is_wb01` 會因此把 wb07 值當成官方 wb01 值（此情境在 `fetch_fund_from_moneydj_url` 路徑成立；`_fetch_fund_single` 路徑只有 `result["perf"].update(perf_wb01)` 與設 `perf_source`，未見把 wb07 寫進 `perf["1Y"]`——讀碼，未窮舉、未實跑）。 |
| M4 | 官方優先、缺才自算的混用欄 `_period_ret` | `ui/helpers/fund/checkup.py::_period_ret`：先 `moneydj_raw.perf[key]`，缺才 `metrics[ret_1m／ret_3m]` | wb01 與列數窗混用 | 否／不明（混） | 原幣 | 兩者皆缺→`None` | 基金體檢表「近 1M／3M／6M」 | 同一欄兩種口徑（B §體檢表）；【待裁】BL-0524 |
| M5 | 使用者自選日曆窗價格報酬 `return_pct` | `services/v2_domain/nav_metrics.py::return_pct`（`(末/首−1)×100`，單位百分點，不另 round）；`ui_v2/hld/logic.py::fund_metrics` 切區間後呼叫（鍵「區間報酬率」） | 使用者自選起迄日；首末兩筆；筆數<2 或首值≈0→`None` | **否**（只用 `nav_orig_ccy`；配息另算「配息佔淨值比」） | 原幣（`_ccy`） | 無列→`⬜ 資料未備`；最早 `nav_date` 晚於區間起點（`fund_profile` 未接時推定）→`⬜ 資料未備`；筆數不足→不適用字樣 | 新版預覽 HLD-7（`ui_v2`／`ui_v3`，非 `app.py` 入口） | 【待裁】；FACT。輸入含 NaN 的行為：`return_pct([nan,1,2])`＝nan（A1 引 audit V8），nav 表路徑已擋非有限值 |
| M6 | 持有期間簡單加總／帳本 TWD 報酬 | T7 帳本（引 `69` G-RET-2） | 買入日起 | 不明 | TWD | — | 💼 持股層 | **不屬基金層**【既裁】1B；持倉域另判 |
| M7 | 相鄰：3Y 含息年化 `ret_3y_ann_tr` | `calc_metrics`（756 列窗；與 Calmar 分子同一條還原序列） | 756 列 | 是（同 1B 口徑） | 原幣 | 不足→`None` | 3-3-3（`DEC-2026-10-23-02` 3A） | **不在本檔候選範圍**（任務限 1M／3M／6M／價格／1Y），僅為免漏而點名 |

#### 3. 同一基金不同來源／算法並存（只描述，不挑較好看的值）

1. 【FACT】同一基金的「1Y」至少五套並存：**(a)** 還原含息 `ret_1y_total`（SSOT 門檻 350 天後才是 `value_pct`）；**(b)** 252 列價格 `ret_1y`；**(c)** MoneyDJ wb01 `perf["1Y"]`（對帳）；**(d)** 新版預覽自選窗價格報酬 `return_pct`；**(e)** 持有期簡單加總（引 `69` G-RET-2）。
2. 【FACT】`docs/v2/69` G-RET-2 另記：tab3 表欄與 AI 摘要讀**原始** `ret_1y_total`，繞過 350 天門檻（引，本組未重驗）。【FACT】本次重讀 `resolve_1y_total_return`：門檻只存在於該函式內；`calc_metrics` 直接輸出的 `ret_1y_total` 在窗口 <350 天時仍有值（`_days_span≥30` 即建窗）。⇒ **原始鍵與 SSOT 解析後的值可以不同，契約若收值必須收解析後的 `value_pct`，不是原始鍵**【INFERENCE】。
3. 【FACT（引 `69`，BL-0520 替身實測）】同一週頻序列：`ret_1y`＝`None`、`ret_1y_total`＝74.5%（窗口 1043 天）、vNext 測試選定日曆窗 17.5%。其意義＝機制已證實並存；**這是替身輸入，不是真實基金證據**，且 74.5% 對應的是 1043 天窗口（「1Y」名稱下窗口遠大於一年；這恰是 G-RET-3 的徵兆）。
4. 【INFERENCE】`ret_1y_total` 的窗首在列數≥252 時取「倒數第 252 列」，350 天門檻只檢查實際日曆天數**下限**，不檢查上限；週頻或稀疏序列可通過門檻卻非一年。本組**未實跑**，只讀碼；是否構成問題屬 BL-0524／G-RET-3，**同一問題亦登記於 BL-0427 (4)**（「350 天只是下限，擋得住窗口太短、擋不住稀疏序列跨度過長」，待客戶裁示、未授權加門檻），**本檔不判、不修**。
5. 【FACT】對帳函式 `reconcile_fund_annual_return` 的 `source_a` 標籤寫 `self_calc:nav[-1]/nav[-252]-1`（描述純價格式），但 `fund_service.finalize_fund_metrics` 實際餵入的是 `ret_1y_total/100`（還原含息）。⇒ **標籤與實際輸入不一致**【FACT 讀碼】；只登記，不改（改碼不在授權內）。
6. 【FACT】本檔**不評斷**任何一套較準；契約若並列，必須各自帶「計算口徑標識」，否則不得並列顯示。

#### 4. 擬登記的裁示項目（供總管／文件組；本檔不寫入 `docs/DECISIONS.md`）

> **登記草稿參考（整合註記）**：本節為作者當時的擬登記草稿；實際登記以 `docs/DECISIONS.md` `DEC-2026-11-08-05` 實際條文為準，不一致處以該條為準。

| 項 | 內容 | 狀態 |
|---|---|---|
| R-1 | 客戶 2026-11-08 題 1 選方案 A 的**要點**（任務單轉述，非逐字）：1Y 含息列入契約候選（客戶確認可延伸），其他期間與價格報酬並列標算法、不選唯一正式算法 | 【NOT VERIFIED】repo 內無登記，需文件組依 `DEC-2026-11-08-04` 體例補登（要點轉述、可逆） |
| R-2 | 1Y 含息跨新版適用：`DEC-2026-10-23-02` 1B 落地範圍＝舊站、不改 `ui_v2/`；「延伸到新資料契約」**尚未核准** | 【待裁】方案 A 的前提動作＝請客戶確認 |
| R-3 | 1M／3M／6M 正式口徑 | 【待裁】維持 BL-0524，本方案不選 |
| R-4 | 契約是否要求新增 as_of／窗口起訖日／取得時間欄 | 【待裁】需改程式，另走授權 |
| R-5 | 對帳容差是否為客戶核准門檻；`RET_1Y_PLAUSIBLE_*` 核准依據 | 【NOT VERIFIED】 |

#### 5. 限制與未涵蓋、單組揭露

- 單組作者，無第二組複驗；分類欄（Required／Optional／Excluded／Pending）是**作者候選**，`docs/v2/67` §8.6 只給 Required 的**例**，不是封閉清單。
- 只讀碼與文件，**未執行任何函式、未跑測試、未取任何資料**；故所有數值行為（如 NaN、窗口邊界、稀疏序列）皆為讀碼推論或引文。
- 引自 `docs/v2/69`、`docs/v2/45`、`d2_draft_A1／B／C` 的列未逐條重驗，已於各格標「引」。
- 未讀取：`ui_v2/exp`、`services/health/dividend.py`、`services/fund_position.py`（`DEC-2026-10-23-06` 的 HWM σ SSOT 另讀同一條還原序列，錨定方式為總管讀法，本組未讀碼，不納入）；`BL-0524` 全文只讀索引列。
- 沒有核對 `fetch_performance_wb01` 實際回傳的期間集合與其是否含息；M2 的「含息」僅為程式註解字面。
- 本檔不涵蓋：配息、持倉、FX、身份鍵、NAV 新鮮度門檻（各有 Gate），也不涵蓋 3Y／5Y 報酬窗。
- 「方案 A」的客戶原意以任務單轉述為準，repo 無逐字紀錄。

---

## 第二部｜E2 基金身份（方案 A）

### E2｜基金身份：資料契約候選（方案 A）與裁示登記草稿

> 基準：`origin/main` = `85a158bb6ca42066862d1563bb6549fa4304a28c`（已 `git fetch`；一律 `git show`／`git grep origin/main` 讀取，未動 repo、未連網、未執行測試）。
> 性質：**單組作者草稿，未經獨立 QA**；**不是**正式契約、**不是**裁示、不授權新公式／程式施工／FX 開閘／啟動 OneBrain。
> 標記：【FACT】讀文件或程式可直接重現；【INFERENCE】作者推得；【NOT VERIFIED】未查證或原文即未定。
> 來源寫法：檔名＋符號／節名，不寫行號。

#### 0. 結論先行

1. 【FACT】現行 production 的基金「取數鍵」只有一個：`services/v2_tables/fund_keys.py::resolve_full_keys` 輸出的 `full_key`（字串，通過 `PURE_CODE_PATTERN`：主碼 3–30 碼大寫英數，可再接一個 `-` 與 2–20 碼大寫英數），`portal` 恆為空字串。
2. 【FACT】標準化身份（`base_fund_code`／`canonical_key`、`verification_status`、`platform_suffix`、`channel_code` 等）只存在於 shadow：`shared/fund_identity.py::DG2_SHADOW_ENABLED = False`，無 production consumer（`DEC-2026-10-28-05`、`DEC-2026-10-29-01`、`DEC-2026-11-01-02` G-E4）。
3. 【FACT】客戶選方案 A 的內容（依派工單轉述，非逐字）：契約只收現行取數鍵；標準化基金身份繼續 Shadow Mode，不啟用新 resolver 影響 production；不改 Sheet schema 或 NAV source precedence。`docs/evidence/d2_draft_C_customer_decision_list_2026_11_08.md` 題 2 的方案 A 與此一致。
4. 【NOT VERIFIED】本 repo（origin/main）的 `docs/DECISIONS.md` 目前只到 `DEC-2026-11-08-04`，**沒有**登記這次「方案 A」裁示；本檔第 7 節只是登記草稿，**未寫入**任何 DEC。（**已登記，見 `DEC-2026-11-08-05`**；本句寫於登記前。）
5. 【INFERENCE】方案 A 下契約的身份欄位只有 `fund_code`（輸入）與 `full_key`（取數用）兩個必收欄，其餘身份欄位一律不收或待決；最大的未解問題是「`full_key` 是否可帶通路後綴」（第 3 節 S7）。

#### 1. 「現行取數鍵」資料契約候選表（共 27 列）

欄位：欄位名稱｜既有程式名稱｜用途｜來源｜日期與健康狀態｜候選分類（Required／Optional／Excluded／Pending，**作者候選**）｜核准狀態（已核准／候選／待裁示）｜既有 DEC／BL｜缺值影響。
「日期與健康狀態」：身份鍵本身沒有 as_of；健康狀態沿用既有字樣，不新增狀態詞。缺值一律用既有「資料未備」「無法判定」。

| # | 欄位名稱 | 既有程式名稱 | 用途 | 來源 | 日期／健康狀態 | 候選分類 | 核准狀態 | 既有 DEC／BL | 缺值影響 |
|---|---|---|---|---|---|---|---|---|---|
| K1 | 基金代碼（輸入） | `fund_code`（`nav`／`dividend`／`fund_profile` 列鍵；持倉 Sheet「基金代號」欄） | 列主鍵、跨表串接 | Google Sheet「基金代號」欄；選股池 `code` 欄（`exp_universe`） | 無 as_of【FACT】 | Required | 候選（Sheet 欄＝MoneyDJ 基本代碼的命名空間為已核准；「列入 Required」尚未核准） | `DEC-2026-10-29-01` 第 1 項；`-03` 第 1 項；`DEC-2026-11-08-04` Q2 | 其餘欄無法掛到基金 → 無法判定【INFERENCE】 |
| K2 | 取數鍵 | `resolve_full_keys` → `results[].full_key` | 傳給 MoneyDJ 等取數鏈的鍵 | `services/v2_tables/fund_keys.py`：strip→upper→`parse_moneydj_input`→`load_fund_code_mapping`→最終 `_is_pure_code` | 解析失敗時 `ok=False`、`full_key=None`、帶 `error`【FACT】 | Required | 候選（作為現行鍵的描述屬 FACT；列入契約待核） | BL-0527 第 5 項；A1 草稿 A2 | 該檔取不到 key → NAV 取不到 → 資料未備【FACT，引 A1 A2】 |
| K3 | 解析成功旗標 | `results[].ok` | 區分「有 key／沒 key」 | `fund_keys.py` | 同上 | Required | 候選 | 無專屬 DEC | 無此旗標則無法區分「沒取到」與「沒有這檔」→ 無法判定【INFERENCE】 |
| K4 | 解析失敗原因 | `results[].error` | 說明為何沒有 `full_key` | `fund_keys.py`（中文原因字串） | 失敗時才有【FACT】 | Optional | 候選 | 無 | 缺原因 → 看不出是格式不符或對照表值不合格【INFERENCE】 |
| K5 | 平台／入口 | `results[].portal`（恆 `PORTAL_DEFAULT = ""`） | 歷史上的入口欄 | `fund_keys.py`（總管裁定一律空） | 常數【FACT】 | Excluded | 候選 | 無 | 無（恆空）。若日後 portal 有值須另裁【NOT VERIFIED】 |
| K6 | 解析出的代碼 | `results[].parsed_code` | 診斷：`parse_moneydj_input` 抽出的代碼 | `fund_keys.py` | 失敗時可能為 None【FACT】 | Optional | 候選 | 無 | 診斷用；缺則少一個除錯線索 |
| K7 | 對照表是否命中 | `results[].mapping_hit`（True／False／None） | 診斷：別名表是否改寫了代碼 | `fund_keys.py` | None＝還沒走到查表就失敗【FACT】 | Optional | 候選 | 無 | 缺則看不出 `full_key` 是否被別名改寫 |
| K8 | 對照表出處 | `provenance.mapping_source`（`builtin`／`csv+builtin`／`injected`） | 說明用的是哪份別名表 | `fund_keys.py::_load_mapping_with_provenance` | `builtin` 無法區分「csv 不存在」與「csv 讀取失敗」【FACT，檔頭自述】 | Optional | 候選 | BL-0521（hook 傳同一份 table） | 缺則無法追溯別名來源 |
| K9 | 對照表筆數 | `provenance.mapping_size` | 診斷 | `fund_keys.py` | — | Excluded | 候選 | 無 | 無 |
| K10 | 解析器名稱 | `provenance.parser` | 診斷 | `fund_keys.py::PARSER_NAME` | 常數【FACT】 | Excluded | 候選 | 無 | 無 |
| K11 | 別名對照內容 | `repositories/fund/sources.py::_DEFAULT_MAPPING`（內建 12 筆）＋ `load_fund_code_mapping`（`fund_code_mapping.csv`，欄 `input_code,public_code,page_type,note`） | 把輸入別名轉成 MoneyDJ 公開代碼與頁型 | 內建表＋可選 csv | `git ls-tree origin/main` 根目錄**沒有** `fund_code_mapping.csv`【FACT】；執行環境是否另有 csv【NOT VERIFIED】 | Pending | 待裁示（別名表是否為契約的一部分、由誰維護） | 無專屬 DEC；`docs/v2/70` §14 第 8 點 | 別名表不同 → 同一輸入得不同 `full_key`（例 `ACTI171`／`ACTI7`／`ACTI71` 在內建表都指 `ACTI71`）【FACT】 |
| K12 | MoneyDJ 頁型 | `parse_moneydj_input` → `page_type`（`yp010000` 境內、`yp010001` 境外、`wb01`／`wb02`／`wb05`／`wr01`／`wr02`／`a1_mobile`／`b1_mobile`）；對照表 `page_type` | 取數時選頁 | 網址明示或對照表；裸碼由 `_is_domestic_code` 推斷（對照表→前綴→預設境外） | 推斷不可靠【FACT，`docs/v2/70` §15.3】 | Pending | 待裁示 | `DEC-2026-10-29-01` 第 5 項（shadow 側：網址明示才記，裸碼 Unknown） | 頁型錯 → 首選失敗後互換重試（`get_page_types_to_try`）【FACT】 |
| K13 | 計價幣別 | `ccy`（`nav` 表）；`declared_ccy` | 淨值原幣 | 持倉列手填或 meta 頁自報（MoneyDJ／TDCC／FundClear） | 缺或不一致 → 該檔淨值整批不寫（A1 草稿 A9） | Pending（屬 NAV 契約，不屬方案 A「只收現行取數鍵」；待該契約核可） | 待裁示 | `DEC-2026-10-28-05`（currency 與 share class 分開、不預設 USD）；A1 草稿 A9、`DEC-2026-11-08-04` Q5 | 缺幣別 → 淨值資料未備；不得補 USD【FACT】 |
| K14 | 幣別出處 | `ccy_source`（`provenance[fund_code]`） | 幣別是誰說的 | `nav_dividend.py` | 旁路 provenance，不在表欄內【FACT，引 A1 A10】 | Pending（同 K13，歸 NAV 契約） | 待裁示 | 同 K13 | 無法追溯 |
| K15 | 基金名稱 | `fund_name`（`exp_profile`） | 人工核對 | MoneyDJ 基本資料頁（需通過身分判準） | 頁不符判準 → `unrecognized_page`／`not_found` | Pending（歸 profile 契約，不屬現行取數鍵） | 待裁示 | A1 草稿 A8 | 該格資料未備；不影響取數鍵 |
| K16 | 持倉身份（保單＋基金） | `(policy_id, fund_url)` 複合鍵；持股鍵 `"{policy_id}::{CODE}"` | 持倉列身份 | Google Sheet 政策分頁（`repositories/policy/v1.py`） | — | Excluded（基金身份契約不收；歸持倉契約） | 已核准其「與基金身份分開」之原則 | `DEC-2026-10-29-01` 第 2 項；`-03` 第 1 項；`CLAUDE.md` §3.1 | 若混入基金身份 → 可能合併不同保單持倉（禁止）【FACT，客戶裁示】 |
| K17 | 選股池 ISIN | `PoolEntry.isin`；`repositories/pool_repository.py::resolve_isin` | Morningstar／Yahoo secId 解析與 backfill 救援的**查找輔助**（`fund_orchestration._pool_secid_or_isin`、`sources._src_morningstar_nav` 內 screener 與 SecuritySearch 兩條 ISIN 路徑、`sources._src_yahoo_finance_nav`、`services/nav_history_store.py::backfill_to_gs` 同時試 Yahoo／Morningstar／CnYES）；**不構成身份依據** | 選股池手填欄，單向（code→ISIN） | 手填、無驗證【FACT，`docs/v2/70` §12、BL-0530】 | Excluded（作為身份來源）；若列入僅能是 Optional 驗證屬性 | 已核准其「不得作為 identity authority」；是否收為屬性待裁示 | `DEC-2026-10-28-05`；`DEC-2026-11-01-02` G-E1；BL-0530 | 缺 ISIN 不影響比對、不警告【FACT，已核准語意】 |
| K18 | Morningstar secId | `PoolEntry.morningstar_secid`；`_MORNINGSTAR_SECID_MAP`（硬編） | Morningstar 取數專用鍵 | 選股池手填、硬編表、名稱搜尋 `results[0]` | 名稱搜尋路徑不驗 ISIN／名稱／幣別／級別【FACT，`docs/v2/70` §12】 | Excluded（來源專屬鍵，不屬身份） | 候選 | `DEC-2026-10-29-01` 第 12 項（本輪不改 `results[0]` 行為） | 缺則該來源不可用，走其他備援 |
| K19 | FundClear 三碼 | `(organizeCode, fundCode, fundClassCode)`（`repositories/fundclear_offshore.py`）；另有 SmartFundAPI 單碼 `_src_fundclear_nav(code)` | FundClear 歷史淨值定位 | FundClear API | `fundClassCode` 不可傳 `all`【FACT】 | Excluded（獨立命名空間） | 已核准其獨立命名空間、不自動對照 | `DEC-2026-10-29-01` 第 3、7 項；`-03` 第 5 項 | 沒有經驗證 mapping → 無法判定【FACT，客戶裁示】 |
| K20 | TDCC 基金代碼 | `declared_profile._TDCC_CODE_KEYS = ("基金代碼","境外基金代碼")` | TDCC 3-2 清單比對 | TDCC OpenAPI | 3-2 使用另一套代碼體系（實測例 `GLIACU`、`AGIF-FVGM`），0 命中 → `code_unmapped`，不證明未收錄【FACT，`declared_profile.py` 檔頭】 | Excluded（獨立命名空間） | 候選 | `DEC-2026-10-29-01` 第 7 項（同理適用 FundClear，TDCC 為作者類推【INFERENCE】） | 不以名稱比對補對應【FACT】 |
| K21 | Cnyes 代碼 | `sources.fetch_nav_cnyes(code)`／`_src_cnyes_nav` | 鉅亨網淨值最末備援 | 鉅亨 REST | 本組未查證 Cnyes 使用的代碼是否等同 MoneyDJ 碼【NOT VERIFIED】 | Excluded（暫不收） | 待裁示 | 無專屬 DEC | 無 |
| K22 | 保單商通路代碼表 | `_BANK_PLATFORM_CODES`（`TLZF9-AL001`／`-24A7`／`-1180`／`-57C0060T`／`-F1740` 等）；`fund_fetcher.PORTAL_CFG` 與 `_INSURANCE_SUBDOMAIN_HINTS`（前綴猜子網域） | 通路頁取數 | 程式碼硬編 | 命中即用，第一個成功就回傳，不比對其他通路【FACT，`docs/v2/70` §14 第 6 點】 | Excluded（取數內部細節，不進身份契約） | 候選 | `DEC-2026-10-28-05`（shadow 注入通路表） | 缺則少一條取數通路 |
| K23 | 標準化基金碼 | `base_fund_code`／`canonical_key`（僅 `base_resolved_attributes_unverified` 時有值） | 跨 view 認同一檔 | `services/fund_identity.py::resolve_fund_identity`（shadow） | production consumer = 0；旗標預設關【FACT】 | Excluded（方案 A） | 已核准「Shadow Mode、不影響 production」；進契約為候選 | `DEC-2026-10-28-05`；BL-0521 | 不進契約 → 跨畫面認同仍靠 `full_key`【INFERENCE，A1/C 草稿題 2 缺點欄】 |
| K24 | 身份驗證狀態 | `verification_status`（7 種） | 標示身份能信到哪 | shadow | 7 個值不在 D3(a) 對照表（字面搜尋 0 命中，引 A1 A5）【FACT，僅字面】 | Excluded | 候選 | `DEC-2026-11-08-02` D3(a) | — |
| K25 | 通路 metadata（shadow） | `original_code`、`platform_suffix`、`channel_code`、`source_url`、`input_source`、`page_type_source`、`url_page_market`、`suffix_provenance` | 保留通路脈絡，後綴不當基金身份 | shadow | 同 K23 | Excluded | 已核准 shadow 階段規則；進契約候選 | `DEC-2026-10-28-05`、`-10-29-01`、`-03` | 通路脈絡遺失；不影響 base 比對【INFERENCE】 |
| K26 | 身份屬性（shadow） | `currency`／`share_class`／`distribution_type`／`hedge_status`（預設 `Unknown`） | 判斷兩代碼是否同一檔 | shadow；只在有可靠資料時填 | Unknown 不得視為相同、不同、安全或已確認【FACT，已核准】 | Excluded | 已核准「Unknown 不猜」；進契約為候選 | `DEC-2026-10-28-05` | 多數為 Unknown → 不能判定是否同一 share class |
| K27 | 儲存鍵（cache／history） | `cache/nav/{full_key}.json`（目前 main 僅見 `cache/nav/TLZF9.json`）；`nav_history` 以代碼（strip／upper）為鍵 | 預存序列與累積序列 | repo 預存檔／Google Sheet | 含 `-` 的鍵**不查**預存檔；改讀 dashed key 備援＝新 fallback，**不核准**【FACT】 | Excluded（儲存細節，不進身份契約） | 已核准「dashed key cache 備援不核准」 | `DEC-2026-10-29-02` 第 2 項；`docs/v2/70` §14 第 2 點 | 無 |

小計：Required 3（K1、K2、K3；K3 為解析成功旗標 `ok`）、Optional 4（K4、K6、K7、K8）、Excluded 15（K5、K9、K10、K16～K27，其中 K21 核准狀態欄為待裁示）、Pending 5（K11、K12、K13、K14、K15），合計 27——**分類為作者候選，客戶逐類核可前不具效力**。【INFERENCE：計數由作者人工統計，已於整合時以 Python 重數。】

#### 2. 各來源代碼與對照證據（描述事實，不推論）

| 來源 | 代碼形態（FACT） | 與 MoneyDJ 碼的對照證據 | 證據出處 |
|---|---|---|---|
| MoneyDJ 基本基金碼 | 如 `ACTI71`、`JFZN3`、`ACCP138`、`ACDD01`、`ACDD19`、`TLZF9`、`ACTI94`、`ALBT8`；Sheet 欄現在及未來固定此命名空間（客戶裁示） | 本身即基準 | `DEC-2026-10-29-01` 第 1 項 |
| MoneyDJ 通路後綴碼 | `TLZF9-AL001`（台新人壽）、`TLZF9-24A7`（遠東銀行）、`TLZF9-1180`、`TLZF9-57C0060T`、`TLZF9-F1740`、`ANZ89-1G11`、`ACTI94-AB116` 等，由 `_BANK_PLATFORM_CODES` 硬編列出對應通路網域與頁型 | 2026-10-29 單日觀察：`TLZF9`／`TLZF9-AL001`／`TLZF9-24A7` NAV 皆 8.4121、日期皆 2026-10-28；平台頁未明示幣別，故 `not_comparable`，僅為 strong observational 候選，**不是**確認；多日累積結果在 `probe/moneydj-nav-results` 分支，本組未取得，完成與否【NOT VERIFIED】 | `docs/v2/70` §16.1、§17；`DEC-2026-10-29-02`、`-03` |
| 保險商品代碼 | `ACDD01-EQTAL005`：`ACDD01`＝MoneyDJ 基金碼、`EQTAL005`＝保險公司商品代碼，不是 share class／另一檔基金／另一條 NAV（客戶裁示） | 來源＝客戶確認（`customer_confirmed_2026-10-29`）；`EQTAL005 → ACDD01` 對 MoneyDJ 頁面的驗證標 `UNVERIFIED`；首次 probe 對該輸入各頁皆 `no_nav_table` | `DEC-2026-10-29-03` 第 1、2 項；`shared/fund_identity.py::CUSTOMER_CONFIRMED_SUFFIXES`；`docs/v2/70` §16.1 |
| MoneyDJ 別名 | `_DEFAULT_MAPPING` 內建 12 筆（例 `ACTI171`／`ACTI7`→`ACTI71`），可由 `fund_code_mapping.csv` 覆寫 | 內建表；origin/main 根目錄無該 csv | `repositories/fund/sources.py`；`git ls-tree` |
| TDCC | OpenAPI 3-2 欄 `基金代碼`／`境外基金代碼`；清單另一套代碼體系（實測 5,295 列，例 `GLIACU`、`AGIF-FVGM`） | 與 MoneyDJ 碼**無**已驗證對照；0 命中＝`code_unmapped`；不以名稱比對 | `repositories/fund/declared_profile.py` 檔頭 |
| FundClear | 境外：`(organizeCode, fundCode, fundClassCode)` 三碼；SmartFundAPI 單碼 `FundCode`；級別碼 `AGIF-HT5`（IT 累積）／`AGIF-HTG`（A 配息）是同基金不同級別 | 不把 Sheet MoneyDJ code 當 FundClear code、不自動產生對照、不要求客戶提供；未來作補充來源須先有經驗證的跨來源 mapping，否則無法判定 | `DEC-2026-10-29-01` 第 3、7 項；`repositories/fundclear_offshore.py`；`docs/v2/70` §14 第 7 點 |
| Cnyes | `fetch_nav_cnyes(code)` 直接以傳入代碼取數 | 與 MoneyDJ 碼是否等同【NOT VERIFIED】 | `repositories/fund/sources.py` |
| Morningstar | secId（選股池手填／硬編 5 筆／名稱搜尋）；ISIN 輔助篩選 | 名稱搜尋取 `results[0]`，不驗 ISIN／名稱／幣別／級別；本輪裁示不改其行為 | `repositories/fund/sources.py::_MORNINGSTAR_SECID_MAP`、`_resolve_ms_secid`；`DEC-2026-10-29-01` 第 12 項 |
| ISIN | 選股池手填欄；`CanonicalFundIdentity.isin` 預設 `None` | **沒有**已核准的 ISIN→MoneyDJ 對照來源；BL-0530 為 research-only | `DEC-2026-11-01-02` G-E1；BL-0530 |
| 保單商 URL／子網域 | `PORTAL_CFG`（`tcbbankfund`、`chubb`）；`_INSURANCE_SUBDOMAIN_HINTS` 以代碼前綴（TL／FL／CT／ANZ／JF／NN／FS／NS／CH／SN）猜子網域 | 前綴→子網域為「推測」性提示（原文標「推測」），非身份證據 | `fund_fetcher.py` |

#### 3. 已核准的適用範圍（逐項；皆為客戶裁示的整理，以 `docs/DECISIONS.md` 與逐字檔為準）

| # | 範圍 | 已核准內容（FACT） | 出處 |
|---|---|---|---|
| S1 | Sheet「基金代號」欄 | 現在及未來均為 MoneyDJ 基本基金代碼；**只適用於該欄**，不得推廣為整個 repo 的所有 code、所有 Sheet 或所有外部 API；不改 Sheet schema、不要求補 ISIN | `DEC-2026-10-29-01` 第 1 項 |
| S2 | 違反該欄契約的輸入 | 出現 URL／`-` 後綴／格式異常 → 標 `sheet_code_contract_violation`，原值保留，不靜默截斷、剝除或改寫 | `DEC-2026-10-29-01` 第 4 項；`-03` 第 1 項 |
| S3 | 基金身份 vs 保單／持倉身份 | 必須分開；同一基金可在多張保單，不得合併投入金額、單位數、成本、損益、交易或持倉紀錄；Identity／NAV／Product Mapping／Holding 四種 resolver 不得混用 | `DEC-2026-10-29-01` 第 2 項；`-03` 第 1 項；`DEC-2026-11-01-01`（三）(四) |
| S4 | 通路後綴不得盲目刪除 | 後綴只在**已驗證 mapping** 命中時才視為通路資訊；未知來源或未知後綴不得剝除；後綴對應不同 share class／幣別／配息／避險／NAV series 時不得強制合併，須產生 Exception／Decision Gate；`AGIF-HT5`／`AGIF-HTG` 不得拆成 `AGIF`；不得套通用 `split("-")[0]` | `DEC-2026-10-28-05`；`DEC-2026-10-29-01` 第 3、4 項；`DEC-2026-11-01-01`（三）；`DEC-2026-11-01-02` contract 摘要(5) |
| S5 | ISIN 角色（**依場景分開，不得一概**） | ① canonical key 與必備欄位：**不是**（`DEC-2026-10-28-05`）。② 找基金搜尋入口：正式 alternate lookup key，但 ISIN 入口目前顯示「尚未啟用」，不進 resolver、不進取數鏈（`DEC-2026-11-01-01`、`-02` G-E1）。③ 一對多或與 code 衝突：`unresolved`，不選第一筆、不設猜測型優先序（`-02` G-E2）。④ 選股池手填 `isin` 欄：**不得**當正式 identity authority（`-02` G-E1）。⑤ ISIN→MoneyDJ 對照來源：research-only（BL-0530），找到候選仍須另走 Source／Identity Gate。⑥ 不要求 Sheet 補 ISIN、缺 ISIN 不警告、不影響 matching | 同左 |
| S6 | Unknown 不推定 | currency／share class／platform suffix／distribution type／hedge status 分開；禁止 currency＝share class、platform_suffix＝share class；禁止由名稱、後綴或幣別推配息／累積／避險；沒有可靠資料一律 Unknown；Unknown 不得視為相同、不同、安全或已確認；missing ≠ known | `DEC-2026-10-28-05`；`DEC-2026-10-29-03` 理由欄 |
| S7 | 「`full_key` 可否帶後綴」——**未裁**【NOT VERIFIED】 | 【FACT】`fund_keys.py::_is_pure_code` 接受「主碼＋`-`＋2–20 碼」，所以含後綴的輸入（如 `ACDD01-EQTAL005`）今日仍可得到帶後綴的 `full_key`；【FACT】`DEC-2026-10-29-01` 第 4 項要求 Sheet 欄出現此類輸入標 `sheet_code_contract_violation`，但 hook 逐筆不傳 `input_source`（來源不一，`docs/v2/70` §15.2），production 路徑今日**不會**打這個標記。第二層原因：打標記的 hook 受 `DG2_SHADOW_ENABLED`（預設 `False`）把關，旗標關閉時根本不執行；`scripts/bl0545_coverage_probe.py` 雖傳 `input_source`，但屬離線探針、不是 production 路徑。契約是否在入口拒絕、改標、或維持現況，**客戶未裁**，方案 A 也未涵蓋 | `fund_keys.py`；`docs/v2/70` §15.2 |
| S8 | 外部來源候選 | 不得因 `results[0]` 直接接受；已知身份屬性衝突即拒收、留 evidence、顯示「⬜ 資料來源不一致，暫無法判定」（shadow 階段，尚未接線） | `DEC-2026-10-28-05` |
| S9 | NAV 與身份分開 | 同 base＋同 NAV date＋同幣別、不同 view 的 NAV 不一致 → source conflict，不得偷偷建第二個 canonical fund；本輪禁止順帶改 NAV precedence | `DEC-2026-10-28-05` |
| S10 | 這次（2026-11-08）方案 A | 契約只收現行取數鍵；標準化身份繼續 Shadow；不啟用新 resolver 影響 production；不改 Sheet schema 或 NAV source precedence。授權範圍＝整理資料契約候選與裁示登記，**不**授權新公式、程式施工、FX 開閘、啟動 OneBrain | 派工單轉述（非逐字）；repo 尚無 DEC【NOT VERIFIED】；同向約束見 `DEC-2026-11-08-02`、`-04` |

#### 4. Shadow 模式與正式身份之間尚缺的驗證（引既有條件，不新增）

| # | 缺口 | 出處 | 狀態 |
|---|---|---|---|
| V1 | TLZF9 多日 probe 完成（3～5 個不同 NAV 日）且無 NAV conflict | `DEC-2026-10-29-03` 第 4、5 項 | 結果在 `probe/moneydj-nav-results`，本組未取得；完成與否【NOT VERIFIED】。目前 repo 僅有 2026-10-29 單日結果，結論為「證據尚不充分」 |
| V2 | 平台頁幣別未明示；share class 全為 unknown | `docs/v2/70` §16.1 | 未解；客戶明示不以 base 頁幣別推定（`DEC-2026-10-29-03` 第 3 項） |
| V3 | `EQTAL005 → ACDD01` 商品對應對 MoneyDJ 頁面未驗證（`mapping_verified_against_moneydj` 預設 null）；該輸入各頁無 NAV 表 | `DEC-2026-10-29-03` 第 2 項；`docs/v2/70` §16.1、§17 | UNVERIFIED |
| V4 | product／fund／holding 分層未完成：專用 `insurance_product_code` 欄位未做，目前以 `platform_suffix`／`channel_code` 暫載 | `DEC-2026-10-29-03` 影響範圍；`docs/v2/70` §17 | 未做 |
| V5 | resolver identity 穩定性：單獨呼叫預設不套別名表（`ACTI171`／`ACTI7`／`ACTI71` 得三個 base）；別名表是否為正式輸入未決 | `docs/v2/70` §14 第 8 點 | 未決 |
| V6 | shadow hook 無法證明輸入來源（呼叫端來源不一），因此 Sheet 契約違反在 production 呼叫鏈不會被標記；要標須由能證明來源的呼叫端往下帶，會改 production 介面 | `docs/v2/70` §15.2 | 未做 |
| V7 | 真實持倉覆蓋率與分母：production `resolve_full_keys` 為主分組，canonical 僅 `shadow_diff`；真實 Active Sheet 覆蓋率 NOT VERIFIED | `docs/HANDOFF.md`（BL-0545 段）；BL-0545 | NOT VERIFIED |
| V8 | 已知缺陷未修／只釘現況：cache 正規化（production 0 呼叫者，只釘現況）、tab2 `nav_latest` 不與序列對帳、銀行平台第一個成功即用 | `docs/v2/70` §14 第 4～6 點 | 未修 |
| V9 | `validate_external_candidate`、`check_cross_view_nav` 皆未接任何取數路徑（production 0 呼叫端）；Morningstar `results[0]` 行為未改 | `docs/v2/70` §13；A1 草稿 B13、B14 | 未接線 |
| V10 | `verification_status` 7 個值未納入 D3(a) 狀態字彙對照表 | A1 草稿 A5；`DEC-2026-11-08-02` D3(a) | 未納入 |
| V11 | 跨類別 identifier（隨 DG-2）：Digest 契約第 5 項缺口 | BL-0527 | 未解 |
| V12 | ISIN→MoneyDJ 來源：research-only，無候選來源導入 | BL-0530；`DEC-2026-11-01-02` G-E1 | 未導入 |
| V13 | 下次提 Shadow flag 提案須一次附齊：執行環境、觸發頻率、讀取哪些 production input、log 欄位、是否含 policy id／個資、遮罩規則、retention、差異分類、success／fail threshold、rollback、關閉方式、是否完全不影響正式 return value | `DEC-2026-10-29-02` 第 3 項 | 未備 |

#### 5. 未來切換（Stage-2：啟用 resolver 影響任何鍵或顯示）需另行裁示的條件

以下全部為**既有條件的彙整**，不是新增條件，也不是現在要做的事。【FACT 出處見第 4 節】

1. 須**另一次 Decision Gate**（`DEC-2026-10-28-05` 影響範圍；`DEC-2026-11-01-02` G-E4）。
2. 須先滿足 V1～V5（`DEC-2026-10-29-03` 第 5 項前置：多日 probe、無 NAV conflict、resolver identity 穩定、product／fund／holding 分層完成）。
3. 提案須附 V13 的 12 項（`DEC-2026-10-29-02` 第 3 項）。
4. 涉及 fund vs share class identity、NAV semantics、product mapping 語意、canonical contract 或 source precedence 改動時，先通知客戶切換 Opus 5.5 + High（`DEC-2026-10-29-03` 第 7 項）。
5. 屬 identity／data semantics，合併前至少 1 組真正獨立稽核（`PROJECT_RULES.md` 第 8 節，引 `DEC-2026-10-29-01` provenance）。
6. 會影響的面：`get_latest_nav`／NAV precedence、持倉分母口徑（`resolve_full_keys` vs canonical，A1 草稿 §3 第 2 題）、Sheet schema 與儲存鍵（皆各自走 Gate，`DEC-2026-10-28-05` 禁止順帶修改清單）。
7. 若要把標準化碼放進**契約**（方案 B／C，`d2_draft_C` 題 2）：B 需標「未驗證」並增加驗證負擔；C 與「轉正須另開 Gate」衝突（引草稿，作者的定性判斷【INFERENCE】）。

#### 6. 限制與未涵蓋、單組揭露

- 【FACT】單組作者，未經獨立 QA；全稱敘述（如「production consumer = 0」）引自既有文件，本組只對 `fund_keys.py`、`shared/fund_identity.py`、`services/fund_identity.py` 函式清單、`sources.py` 的 `_BANK_PLATFORM_CODES`／`_DEFAULT_MAPPING`／`parse_moneydj_input`／`get_page_types_to_try`、`pool_repository.resolve_isin`、`declared_profile` 檔頭做了直接讀取。
- 【NOT VERIFIED】未開啟 `docs/evidence/decisions/` 下逐字存檔，裁示內容以 `docs/DECISIONS.md` 摘要與 `docs/v2/70` 為準；摘要與逐字檔若有出入，以逐字檔為準。
- 【NOT VERIFIED】未讀 `PROJECT_RULES.md`、`docs/HANDOFF.md` 全文（只 grep 相關段）；未讀 `probe/moneydj-nav-results` 分支（無網路）；多日 probe 的最新狀態未知。
- 【NOT VERIFIED】未跑任何測試；未實測 `resolve_full_keys` 對 `ACDD01-EQTAL005` 的實際輸出（S7 為讀碼推論：`_is_pure_code` 接受帶後綴碼，且 `mapping` 內建表無此鍵 → 走原碼）。
- 【NOT VERIFIED】Cnyes、保單商子網域的代碼語意、`fund_code_mapping.csv` 在部署環境是否存在、`ui_v2` 是否為雲端正式入口。
- 【INFERENCE】第 1 節的 Required／Optional／Excluded／Pending 分類、K 列計數，皆為作者候選；A1 草稿 A 區分類（如 A1「必備」）與本檔有範圍差異：本檔只收「現行取數鍵」，A1 草稿含 shadow 欄位（本檔歸 Excluded）。
- 本檔**沒有**：把標準化代碼升格為正式身份、新增 Schema／生產者、改 Sheet schema、新增狀態詞（沿用「資料未備」「無法判定」；`sheet_code_contract_violation` 等為既有 shadow 字彙，僅描述）、把候選寫成核准。
- 未涵蓋：EXP-1 選股池以外的身份推導點（`ui/tab2`／`ui/tab3` 就地推導、`ui_v2/alo` 的 `holding_id` 組法），沿用 `docs/v2/70` §12 的「六是下界、非窮舉」。

#### 7. 裁示登記草稿（候選文字，**未寫入** `docs/DECISIONS.md`；是否登記、編號由總管決定）

> **登記草稿參考（整合註記）**：下列引用區塊為作者當時的擬登記草稿；實際登記以 `docs/DECISIONS.md` `DEC-2026-11-08-05` 實際條文為準，不一致處以該條為準。

> DEC-（待編）｜客戶裁示：基金身份選方案 A（D2／D9 題 2）
> - 日期：2026-11-08；決策者：客戶（經總管派工單轉達，要點轉述，非逐字；客戶可推翻）。
> - 內容：資料契約只收現行取數鍵（`fund_code`、`full_key`；其餘欄位逐類另核）；標準化基金身份繼續 Shadow Mode，不啟用新 resolver 影響 production；不改 Sheet schema 或 NAV source precedence。
> - 授權範圍：整理正式資料契約候選與裁示登記。**不授權**新公式、程式施工、FX 開閘、啟動 OneBrain。
> - 不取代：`DEC-2026-10-28-05`、`DEC-2026-10-29-01`、`-03`、`DEC-2026-11-01-01`、`-02`；Stage-2 仍須另一次 Decision Gate。
> - 未解（不由本筆裁）：S7（`full_key` 可否帶通路後綴）、K11（別名表是否屬契約）、K12（頁型是否入契約）、V1～V13。
> - provenance：要點轉述；supersedes 範圍由文件組讀法，可被客戶推翻；單組草稿。

---

## 第三部｜E3 持倉：持有單位、成本、類別金額（持倉占比方案 C＝延後）

> 基準 `origin/main` = `85a158bb6ca42066862d1563bb6549fa4304a28c`（已 `git fetch`；全程只用 `git show`／`git grep origin/main`，未 checkout、未改 repo、未連網、未 commit）。單組作者草稿，**尚無獨立 QA**；不構成正式契約、Schema、裁示或施工授權。

### E3｜持倉：持有單位、成本、類別金額——正式資料契約「候選」整理（持倉占比採方案 C＝延後）

**標記**：【F】＝FACT（可由所引檔案文字重現）；【I】＝INFERENCE（作者推得）；【NV】＝NOT VERIFIED。
**來源寫法**：檔名＋符號／節名，不寫行號。
**分類欄**（Required／Optional／Excluded／Pending）＝作者**候選**，不是客戶核准。「核准狀態」欄只有明標「已核准」且附 DEC／程式證據者才算數。

---

#### 0. 結論先行

| # | 結論 | 標記 |
|---|---|---|
| 1 | 客戶 2026-11-08 對「持倉占比」選**方案 C＝延後**（暫不收「類別占比契約」）；原話只在派工單轉述，**`origin/main` 的 `docs/DECISIONS.md` 尚無對應 DEC**（`git grep` 「類別占比契約」「持倉占比」於 DECISIONS／HANDOFF／BACKLOG 皆 0 命中）。本稿因此把該裁示當「**要點轉述、尚待登記**」，不另引 DEC 編號（**已登記，見 `DEC-2026-11-08-05`**；本句寫於登記前）。 | 【F】 |
| 2 | 本輪只整理五件事：(1) 持有單位與成本資料；(2) 淨投資金額（暫稱成本）、幣別與來源；(3) 現有可追溯的類別金額；(4) 缺資料原因與未涵蓋範圍；(5) 在合法且已核准規則下哪些金額可被確認。**不定義占比分母、不新增公式／門檻／Schema／狀態詞。** | 【F】 |
| 3 | 現有程式裡，**不需要匯率與淨值的金額路徑是成本基準（作者讀法，未窮舉）**：`holdings.basis_value_with_reason(..., market=False)` 直接回 `float(holding["cost_twd"])`，不讀 `nav`／`market_indicator`。因此「各類別成本金額」在 FX 閘門關閉（`FX_OBS_DATE_RULE_VERIFIED = False`）下**不受影響**。 | 【F】 |
| 4 | 但「**淨投資金額（暫稱成本）可算**」≠「**客戶已核准把它當契約欄位**」：`cost_twd` 來源為保單分頁「淨投資金額」，**它是否等於正式『成本』語意，repo 文件未見明文**（A2 Q2；C 題 3 稱若選成本占比此題變擋路題）。方案 C 不收占比，故本題暫不擋，但**不得**因此把「淨投資金額＝成本」寫成已確認。 | 【F】＋【NV】 |
| 5 | 市值面（淨值×單位數×匯率）程式存在，但 New UI2 預覽路徑 `ui_v3/adapters/assets_source.py` 對市值基準**恆回阻擋** `BLOCKED_MARKET_BASIS`、不呼叫生產者；非台幣基金市值在共用層為 `None`＋`fx_absent`。**這是「該筆台幣換算結果無法判定」，不是「整檔不可分析」**（`DEC-2026-11-08-04` Q5）。 | 【F】 |
| 6 | 作者讀為可引用的規則有：缺值不得為 0／完整／可比／安全（`DEC-2026-11-05-04` 客戶裁示欄「另有規則」；**該筆為要點轉述、未重新追認**，`DEC-2026-11-08-03`）；缺必要 FX 使分母不完整時不得顯示誤導性完整 100%（`DEC-2026-11-04-02` 方案 A，僅 UI 呈現）；缺資料沿用「資料未備／無法判定」、非台幣不得整檔判不可用（`DEC-2026-11-08-04` Q4／Q5）；FX 閘門維持關閉（`DEC-2026-11-08-02` 要點 (1)）。其餘（分母公式、完整性契約、過期天數、11 項 open gate）仍是 Decision Gate（作者讀法，未窮舉）。 | 【F】 |
| 7 | **真實使用者持倉對這些欄位的覆蓋率 NOT VERIFIED**（BL-0545；客戶暫不提供輸入）。本稿所有「有資料」＝「程式有路徑且有契約檢查」，不是真實資料已涵蓋。 | 【F】 |

---

#### 1. 範圍、方法與盲點

- 【F】已讀（`origin/main`）：`docs/evidence/d2_draft_A2_holdings_dividend_2026_11_08.md`（持倉 H1～H17、§2.2、§2.3、§4、§5）、`docs/evidence/d2_draft_C_customer_decision_list_2026_11_08.md`（題 3）、`docs/DECISIONS.md` 的 `DEC-2026-11-04-02`／`-03`、`DEC-2026-11-05-02`／`-04`、`DEC-2026-11-08-02`／`-03`／`-04`（逐字讀欄位）、`docs/BACKLOG.md` BL-0542 列、`docs/v2/74_assets_d3_formula_gate.md`（分母、DIRECT、F-13／F-18／F-19 段）；程式 `services/v2_domain/allocation_evidence.py`（模組說明、dataclass、`_CHART_AFFECTING_GATES`、open gate 產生段）、`services/v2_domain/holdings.py`、`services/v2_tables/alo_holdings.py`（檔頭、`_holding_reasons`、`build_alo_tables` 輸出鍵）、`services/v2_tables/contract.py::HOLDING_FIELDS`、`ui_v3/adapters/assets_source.py`（`BLOCKED_MARKET_BASIS`）、`ui/helpers/portfolio/allocation.py`（檔頭）。
- 【F】本稿重新核對的少數事實：`FX_OBS_DATE_RULE_VERIFIED = False`（`services/v2_tables/market_indicator.py`）；`NAV_NOT_READY_DAYS = 10`（`ui_v2/thresholds.py`）；`_CHART_AFFECTING_GATES` 為 8 碼，另 3 碼（`tolerance_unset_effect_unjudged`／`omitted_row_reason_codes_undefined`／`non_holding_read_error_effect_unjudged`）在檔內產生但不在該集合內；`AllocationEvidence` 根層欄位無任何 `as_of`／產生時間欄。
- 【NV】未執行任何測試／程式；未查任何真實 Sheet；各 DEC 的客戶逐字原話多數不在 repo（`DEC-2026-11-04-02` 有 evidence 檔，本稿未讀該檔；`-03`／`11-05-02`／`-04`／`11-08-02`／`-04` 為要點轉述，`11-08-03` 本次對話逐字）；`docs/v2/44` 未重讀，其 §4.1 欄位定義**轉引**自 `alo_holdings` 檔頭與 `contract.py`。
- 【NV】Old UI 各畫面如何呈現本稿所列欄位未逐行驗。
- 【I】沿用 A2 的做法：本稿候選分類為作者自擬；A2 的 H 組列號在本稿以「(A2-Hn)」回指，**本稿不重複 A2 已列且與本題無關的項目（如 H15 以外的重疊度 H17、配息）**。

---

#### 2. 候選欄位表

欄位：欄位名稱／既有程式名稱／用途／來源／日期與健康狀態／候選分類／核准狀態／既有 DEC 或程式證據／缺值影響。
「核准狀態」三值：**已核准**（附證據）／**候選**（作者提議，待客戶逐類核可）／**待裁示**（依賴未裁 Gate）。

##### 2.A 持有單位與成本資料（`holding` 表，`44` §4.1）

| # | 欄位名稱 | 既有程式名稱 | 用途 | 來源 | 日期與健康狀態 | 候選分類 | 核准狀態 | 證據（DEC／程式） | 缺值影響 |
|---|---|---|---|---|---|---|---|---|---|
| A1 | 持倉識別 | `holding_id`、`policy_id`、`fund_code`（`HOLDING_FIELDS`）；`holding_id` 組法 `<保單編號>\|<基金代號>\|<n>` | 追溯到單一列；同鍵合併 | 保單分頁（L1 `policy_supplement_repository`）→ `alo_holdings.build_alo_tables` | 無獨立日期欄 | Required | 候選（欄位在 frozen `44` §4.1；`holding_id` 組法為「總管自決」，非客戶裁示——`alo_holdings` 檔頭 T2） | `alo_holdings` 檔頭 T2／U11；`contract.HOLDING_FIELDS`；`holdings.aggregate_holding_rows`／`HoldingKeyConflict` | 鍵含直線符號或非字串＝該列**不寫入**並寫明原因；撞號＝raise；同鍵語意不同＝`HoldingKeyConflict`（不加總、不挑一列）。【F】 |
| A2 | 基金名稱 | `fund_name` | 人讀追溯 | 保單分頁 | 無 | Optional（僅供辨識；不參與金額）【I】 | 候選 | `contract.HOLDING_FIELDS`；`alo_holdings._holding_reasons`（基金名稱空白→該列不寫入） | 空白＝該列不寫入（與 A3～A6 同列級）。【F】 |
| A3 | 持有單位數 | `units_shares`（來源「持有單位數」） | 市值基準的乘數；成本基準不使用 | 保單分頁 | 無 | Required（持有單位）【I】 | 候選（規則出自 `alo_holdings` 檔頭 Q4(a)，客戶 2026-09-27 前裁示，逐字【NV】） | `alo_holdings._holding_reasons`「持有單位數空白或為 0（沒填）」；`contract.holding_row_problems`（須 > 0） | 空白或 0＝該列**不寫入**、列入 `skipped_holdings`；不補 0。【F】 |
| A4 | 平均買入單位成本（來源欄，非 `holding` 欄） | 來源欄 `avg_nav`（保單分頁「平均買入單位成本」） | 僅用來算 A6 `cost_orig_ccy` | 保單分頁 | 無 | Optional（中間欄，不進契約）【I】 | 候選 | `alo_holdings._holding_reasons`「平均買入單位成本空白或為 0（沒填）」 | 空白或 0＝該列不寫入。【F】 |
| A5 | 台幣成本 | `cost_twd`（來源「淨投資金額」；`holding_row_problems` 須 > 0） | 成本基準的單檔金額 | 保單分頁「淨投資金額」（欄名另有 `invest_twd` 並存時讀 `invest_twd`，原因字樣會註明） | 無日期欄 | Required（成本金額）；**語意標籤待確認**（C 題 3 原話：「必備，語意標籤待確認」） | 候選；來源規則 U10 出自 `alo_holdings` 檔頭（客戶 2026-09-27 前裁示，逐字【NV】） | `alo_holdings._holding_reasons`；`holdings.basis_value_with_reason`（`market=False` → `float(cost_twd)`） | 空白／0／無法解析（例 `NT$1,000`）／非正整數＝該列**不寫入**，原因寫明（「淨投資金額空白（沒填）」「為 0（不當成本）」「無法解析：<原文>」「不是正整數」）；成本類別值因此少這一筆；不補 0。【F】 |
| A6 | 原幣成本 | `cost_orig_ccy`＝持有單位數×平均買入單位成本 | 回顯用；現行配置公式不讀它 | 保單分頁（衍生） | 無 | Optional【I】（A2-H3 同判） | 候選 | `alo_holdings._holding_reasons`；`allocation_evidence.RawRowFact`（回顯）；`holdings.HOLDING_SUM_COLUMNS`（同鍵加總） | 任一源欄空白＝該列不寫入。同鍵不同幣別不得相加（`aggregate_holding_rows` 遇 `ccy` 不同＝`HoldingKeyConflict`）。【F】 |
| A7 | 持有幣別 | `ccy`（來源「幣別」） | 決定是否需匯率（市值面）；成本幣別的標籤 | 保單分頁 | 無 | Required【I】 | 候選（欄位在 `44` §4.1） | `alo_holdings._holding_reasons`「幣別空白」；`contract.holding_row_problems`（`_ccy_problem`） | 空白＝該列不寫入。【F】 |
| A8 | 類別 | `bucket`（取 `_持倉補充` 的「類別」，**不**取保單分頁的「級別」） | 類別金額的分組鍵 | `_持倉補充` 分頁 | 無 | Required（類別金額需要它）【I】 | 候選（Q8 出自 `alo_holdings` 檔頭，客戶 2026-09-27 前裁示，逐字【NV】） | `alo_holdings` 檔頭 Q8；`holdings.bucket_category`（空白或不在名稱表＝`None`＝未分類） | **依賴 `bucket_names`（類別名稱設定）**：`bucket_category(bucket, names)` 在 `names` 未設定時全部進未分類，故本欄可用與否取決於該設定（Pending 依賴）。空白＝未分類，**保留為獨立類別、不猜**；`unclassified_comparability_unjudged` 是否影響可比＝未裁（open gate #1）。【F】 |
| A9 | 持有起始日 | `opened_on` | 回顯 | `_持倉補充`「持有起始日」 | 日期欄（來源原值） | Optional【I】 | 候選 | `contract.HOLDING_FIELDS`；`HOLDING_SAME_COLUMNS`（hld 規則下兩列不同＝不加總） | 本稿未追到缺值處理的專屬原因碼【NV】。 |
| A10 | 最後核對日（推定時間） | `last_synced_at`＝「最後核對日」當日 12:00 台灣時間（`YYYY-MM-DDT04:00:00Z`），**推定值** | 唯一可見的「持倉資料新舊」線索 | `_持倉補充` | 推定值，登記於 `ACCEPTANCE.md` 8.1（R1＝B） | Optional（作者候選）；是否需要根層 `as_of`＝D2 | 候選 | `alo_holdings.last_synced_at_from_check_date`；`AllocationEvidence` 無根層 as_of、`HoldingEvidence` 不攜帶此欄（本稿核對） | 非 `YYYY-MM-DD` 格式＝拒收，不以讀取時間冒充。【F】 |
| A11 | 直接持有（DIRECT） | `policy_id` 恰為 `DIRECT`（去前後空白、大小寫敏感）的列 | 目前**不產生 `holding` 列**，只逐筆警示 `DIRECT_WARNING`「DIRECT 列暫不支援，該筆不計入配置」 | 保單分頁／`_保單資料` | — | Excluded（目前行為）；hld 頁如何顯示＝待裁 | 「不計入配置」＝客戶 U9 裁示；「不產生 `holding` 列」＝**總管暫定、非客戶裁示**（`alo_holdings` 檔頭自述） | `alo_holdings` 檔頭 DIRECT 段；`docs/v2/74` DIRECT 段 | DIRECT 持倉不進分子也不進分母。【F】 |

##### 2.B 淨投資金額（暫稱成本）、幣別與來源

| # | 欄位名稱 | 既有程式名稱 | 用途 | 來源 | 日期與健康狀態 | 候選分類 | 核准狀態 | 證據 | 缺值影響 |
|---|---|---|---|---|---|---|---|---|---|
| B1 | 單檔成本基準值（台幣） | `holdings.basis_value_with_reason(holding, tables, market=False, ...)` → `(float(cost_twd), None, None)` | 類別成本金額的單檔輸入 | 同 A5 | 不讀 `nav`／`market_indicator`，無日期 | Required（作為「成本金額」的導出）【I】 | 候選；數值與缺值核心的 PORT 屬 G1-②（授權記於 `DEC-2026-11-05-02`，事後補登、要點轉述、客戶 2026-11-08 選「保留未追認」`DEC-2026-11-08-03`） | `holdings.basis_value_with_reason`；`HoldingEvidence.value_twd`／`value_status` | 成本基準下單檔值不會是 `None`（因 A5 缺值的列根本不在 `holding` 表）【I】：缺口以「列不寫入」形式出現在來源側，而不是以 `None` 出現在金額側。 |
| B2 | 成本幣別的標示 | `cost_twd` 欄名內含 `_twd`；`cost_orig_ccy` 的幣別＝`holding.ccy` | 避免「台幣成本」與「原幣成本」混加 | — | — | Required（單位標示）【I】 | 候選 | `contract.HOLDING_FIELDS`；`CLAUDE.md` §4.1（量綱）；`aggregate_holding_rows`（不同 `ccy` 不得相加） | 見 A6。「`cost_orig_ccy` 的幣別＝`holding.ccy`」是【I】：我讀到的程式把兩欄並列、未見另一個幣別欄。 |
| B3 | 持倉來源與讀取是否完整 | `SourceFacts`（`active_source`、`read_errors`、`skipped_tabs`、`omitted_rows`）；`source_coverage`∈`complete`／`incomplete`／`unknown`／`failed`／`not_selected` | 說明「這些金額來自哪個 Active 來源、是否完整讀完」 | `build_alo_tables` 輸出的 `skipped_tabs`／`skipped_holdings`／`invest_twd_parse_errors` 等 | 無根層時間；分頁快取 60 秒的已知限制見 `alo_holdings` 說明 | Required（證據型）【I】 | **候選**；檔頭自稱「INTERNAL CANDIDATE, not approved vocabulary」（A2-H14 轉引） | `allocation_evidence.SourceFacts`；`alo_holdings.build_alo_tables` docstring | 來源不完整＝`chart_comparability` 為 `not_comparable`，且類別值 `value_reliable=False`。【F】 |
| B4 | 列級來源追溯 | `RawRowFact`（每個被合併的原始列：`holding_id`、`policy_id`、`fund_code`、`fund_name`、`bucket`、`ccy`、`units_shares`、`cost_orig_ccy`、`cost_twd`） | 追溯一個彙總持倉由哪幾列合成 | 同上 | 無 | Optional【I】 | 候選 | `allocation_evidence.RawRowFact`；`HoldingEvidence.source_rows` | 無。 |
| B5 | 資料時點（根層） | **現無**（`AllocationEvidence` 根層無 `as_of`／產生時間；`holding` 表亦無 `source`／`fetched_at`） | 若要證明「這份金額是何時、依哪個時點的持倉」才需要 | — | — | Pending（是否補＝D2；不新增欄位） | 待裁示 | `contract.HOLDING_FIELDS`（無 `source`／`fetched_at`）；`AllocationEvidence` 欄位清單；A2-H15、AUD §5 R2（轉引） | 現況下 Evidence 無法自證產生時間。【F】本稿**不提議新增欄位**，僅登記。 |

##### 2.C 現有可追溯的類別金額

> 這一組只描述**現有程式已能產出、且能回溯到持倉列**的金額。**不含占比**（方案 C 延後，見 §4）。

| # | 欄位名稱 | 既有程式名稱 | 用途 | 來源 | 日期與健康狀態 | 候選分類 | 核准狀態 | 證據 | 缺值影響 |
|---|---|---|---|---|---|---|---|---|---|
| C1 | 類別淨投資金額（暫稱成本，台幣）；**依賴 `bucket_names`，未設定則全進「未分類」，列 Pending 依賴** | `CategoryEvidence.value_twd`（`category_values(..., market=False)` 的加總，浮點累加起點 `0.0`、依持倉順序） | 「各類別成本金額」 | 同 B1 加總 | 無日期 | **Required（金額，不含占比）候選**；成本基準下不受 FX／NAV 影響 | 候選；公式核心是 G1-② 既有 PORT（逐位元組不變由 `tests/test_alo_core_golden.py` 守，轉引【NV】）；**授權鏈為事後補登未追認** | `holdings.category_values`；`allocation_evidence.CategoryEvidence`；`DEC-2026-11-05-02`、`DEC-2026-11-08-03` | 該類別所有列缺值時為 `None`＋原因（成本基準下因列不寫入，通常是類別根本沒出現）。永不為 0。【F】 |
| C2 | 類別金額的來源狀態 | `CategoryEvidence.origin`∈`from_holdings`／`target_without_holdings`／`real_zero_by_rule`／`unproven_zero`；`value_reliable` | 區分「真的 0」與「來源未完整時的 0」 | `allocation_evidence` | 與 B3 同 | Required（證據型）【I】 | 候選（名稱皆「內部候選、非已核准詞彙」） | `allocation_evidence`（`UNPROVEN_ZERO`、`REAL_ZERO_BY_RULE`、`value_reliable`） | 目標有、持倉無、來源未完整時，0 標 `unproven_zero`，不可當成「沒有這類」。【F】 |
| C3 | 類別持倉件數 | `holding_count`、`valued_holding_count` | 說明該類別值由幾檔組成 | 同上 | — | Optional【I】 | 候選 | `CategoryEvidence` | 件數含被忽略的後續持倉（`CategorySlot.count`）。【F】 |
| C4 | 未分類類別 | `is_unclassified`／`bucket_category` 回 `None` | 把 bucket 空白或不在名稱表者另列 | — | — | Required（證據型）【I】 | 候選；是否影響可比＝未裁 | open gate `unclassified_comparability_unjudged`；`docs/v2/74` F-19（該檔標為阻擋項；其後續裁示狀態本稿未查【NV】）；BL-0542 G-1 新待決題 (e) | 保留獨立類別，不猜。【F】 |
| C5 | 類別市值金額 | `CategoryEvidence.value_twd`（`market=True` 路徑）；`holdings.category_values(market=True)` | 市值面的類別金額 | `nav` × `units_shares` ×（非台幣）`market_indicator` 匯率 | 受 `nav_date`、`obs_date`、10 日規則影響 | Pending（**本輪暫不納入**） | 待裁示；New UI2 預覽路徑對市值基準回 `BLOCKED_MARKET_BASIS`、`DEC-2026-11-05-04`「仍未授權」列 NAV 組裝搬遷、FX 閘門開放、正式 UI 接線 | `ui_v3/adapters/assets_source.py`（`BLOCKED_MARKET_BASIS`）；`holdings.basis_value_with_reason`；`DEC-2026-11-05-04`、`DEC-2026-11-08-02` | 非台幣基金：`None`＋`fx_absent`；缺淨值：`nav_absent`／`nav_stale`／`nav_stale_undated`。永不為 0。【F】 |
| C6 | 覆蓋範圍內的金額合計 | `CoverageFacts.covered_value_twd`、`DenominatorFacts.value_twd`（**內部候選，其公式屬 G-1 未裁**） | 說明「已涵蓋的金額加總」 | `allocation_evidence` | — | Pending（**本輪不定義**；僅承認物件存在） | 待裁示（G-1） | `allocation_evidence.DenominatorFacts`、`CoverageFacts`；`DEC-2026-11-04-03`（G-1 方向：保守 PORT、另立完整性契約，**公式不變**） | 見 §4。本稿**不**把 `DenominatorFacts.value_twd` 稱為「分母」的定義。 |

##### 2.D 缺資料原因與未涵蓋範圍（只用既有原因碼與字樣）

| # | 項目 | 既有碼／字樣 | 觸發條件（事實） | 候選分類 | 核准狀態 | 證據 |
|---|---|---|---|---|---|---|
| D1 | 列未寫入（來源側缺資料） | `skipped_holdings`（含原因句：「基金名稱空白」「幣別空白」「持有單位數空白或為 0（沒填）」「平均買入單位成本空白或為 0（沒填）」「淨投資金額空白（沒填）」「淨投資金額為 0（不當成本）」「淨投資金額無法解析：<原文>」「淨投資金額不是正整數」） | 保單分頁該列不滿足契約 | Required（缺資料必須有原因）【I】 | 候選；**略過列原因代碼未定義**＝open gate `omitted_row_reason_codes_undefined`（不影響圖狀態）；`docs/v2/74` F-18（阻擋項，→ BL-0411） | `alo_holdings._holding_reasons`；`allocation_evidence`（gate 產生段） |
| D2 | 來源讀取不完整 | `source_coverage = incomplete／unknown／failed／not_selected` | 略過分頁／略過列／持倉表讀取失敗／無 Active 來源 | Required（證據型）【I】 | 候選（內部候選詞彙） | `allocation_evidence.SRC_*` |
| D3 | 單檔市值缺值原因 | `nav_absent`、`nav_stale`、`nav_stale_undated`、`fx_absent`；`KIND_NAV`／`KIND_FX` | 無淨值列／在過期名單／缺匯率（含閘門關閉不寫列） | Pending（僅市值面；本輪暫不納入） | 待裁示（D7／D8） | `holdings.REASON_*` |
| D4 | NAV 輸入狀態 | `nav_input_state`；逐檔 `nav_state`（`not_assembled`／`failed`／`no_data`／`obtained_rejected`／`cause_unknown`／`present`／`not_required`／`not_evaluated`／`error`） | 市值面 NAV 是否組裝、為何缺 | Pending（市值面）；成本基準下逐檔 `nav_state` 為 `not_required` | **最小方案 D 已授權**（`DEC-2026-11-05-04`，要點轉述；`DEC-2026-11-08-03` 註明未重新追認）；詞彙仍為內部候選 | `allocation_evidence`（`NAV_STATES`）；BL-0542 D 後續狀態段 |
| D5 | 未涵蓋範圍 | `CoverageFacts.uncovered_categories`／`uncovered_holdings`／`uncovered_value`（`UncoveredAmount.status`＝`not_computable`；有來源完整證明才 `none_uncovered`） | 有類別缺值 | Required（證據型）【I】 | 候選；原則「未涵蓋台幣金額＝不可計算、永不為 0」＝已核准規則的程式化（`DEC-2026-11-05-04` 另有規則；**要點轉述、未重新追認**，`DEC-2026-11-08-03`） | `allocation_evidence.UncoveredAmount` |
| D6 | 分母不成立 | `denominator.verdict`＝`complete`／`incomplete`／`none`／`non_positive`／`non_finite` | 分母為零、負、NaN／inf 等 | Pending（隨 G-1） | 待裁示 | `allocation_evidence.DEN_*` |
| D7 | 持倉鍵衝突 | `identity_conflict`（`HoldingKeyConflict`） | 同鍵兩列 `bucket` 或 `ccy` 不同 | Required（證據型）【I】 | 候選；hld／alo 兩套同鍵合併規則並存未收斂（`holdings.py` 檔頭登記） | `holdings.aggregate_holding_rows` |
| D8 | 缺資料呈現字樣 | 沿用既有「資料未備」「無法判定」；UI 缺必要 FX 使分母不完整時不得顯示誤導性完整 100%，改顯示資料未備與未涵蓋範圍 | 畫面呈現規則 | —（UI 呈現，非資料欄位） | **已核准**：`DEC-2026-11-08-04` Q4；`DEC-2026-11-04-02`（方案 A，僅 UI 設計；`_build_alo2` 現況與之不同，`DEC-2026-11-04-03`「已知落差」，本批不修） | 見左 |

---

#### 3. 在合法且已核准規則下，哪些金額可被確認（逐項附證據）

> 「可被確認」＝可由現有程式從持倉列**追溯並重算**，且不需要任何未裁的公式、門檻、字彙或 FX 閘門。**不等於真實資料已驗證**（BL-0545）。

| # | 金額 | 可被確認的條件 | 依據（DEC／程式） | 為什麼不是「新規則」 | 標記 |
|---|---|---|---|---|---|
| K1 | 單一持倉的**台幣成本** `cost_twd` | 該列通過 `holding_row_problems`（須 > 0、整數、有幣別與單位數） | `alo_holdings._holding_reasons`；`contract.holding_row_problems` | 逐列檢查既有；不補 0 | 【F】 |
| K2 | 單一持倉的**原幣成本** `cost_orig_ccy` | 同上，且單位數與平均買入單位成本皆非空非 0 | `alo_holdings._holding_reasons` | 既有計算（單位數×平均買入單位成本） | 【F】 |
| K3 | 同鍵多列的加總成本 | 同鍵兩列 `bucket` 與 `ccy` 皆相同 | `holdings.aggregate_holding_rows`（alo 規則）；`HOLDING_SUM_COLUMNS` | 既有；不同幣別不得相加 | 【F】 |
| K4 | 各**類別的台幣淨投資金額（暫稱成本）** | 成本基準；各列已通過 K1；類別以 `bucket` 為準（空白＝未分類獨立類別）；**並依賴類別名稱設定 `bucket_names`（未設定時全部歸「未分類」）**；`source_coverage` 為完整時才標 `value_reliable`（成本基準不讀 NAV／匯率，故**不受 FX 閘門與 NAV 過期影響**） | `holdings.category_values(market=False)`；`allocation_evidence.CategoryEvidence.value_reliable`；FX 閘門維持關閉＝`DEC-2026-11-08-02` 要點 (1) | 公式核心是既有 G1-② PORT（公式不變，`DEC-2026-11-04-03` 客戶裁示 (1)）。**但**：授權鏈為事後補登、未追認（`DEC-2026-11-08-03`）；且「淨投資金額＝成本」語意未確認（見 §0 #4） | 【F】＋【NV】 |
| K5 | **非台幣基金的成本金額（台幣）** | `cost_twd` 本身是台幣欄位，成本基準不需匯率 ⇒ 非台幣基金的**成本**仍可入 K4 | `holdings.basis_value_with_reason`（`market=False` 不呼叫 `fx_key_of`）；`DEC-2026-11-08-04` Q5（不得整檔判不可用） | 這與 Q5 一致：只有「需要匯率才算得出的台幣換算結果」才標無法判定 | 【F】；【I】（把它連結到 Q5 是作者讀法） |
| K6 | 缺值**不被偽造** | 任何缺值＝`None`＋機器原因碼；未涵蓋台幣金額＝`not_computable`；來源未完整時的 0＝`unproven_zero` | `DEC-2026-11-05-04` 客戶裁示「另有規則」；`allocation_evidence`（`UncoveredAmount`、`UNPROVEN_ZERO`） | 作者讀為已核准原則的程式化（來源 `DEC-2026-11-05-04` 為要點轉述、未重新追認） | 【F】 |
| K7 | **市值**（單位數×淨值，非台幣再乘匯率） | **本輪不確認**：FX 閘門關閉；市值基準在預覽路徑被阻擋；NAV 10 日規則的跨頁語意未裁 | `DEC-2026-11-08-02`；`DEC-2026-11-05-03`（五待決）；`ui_v3/adapters/assets_source.py` | — | 【F】 |
| K8 | 任何**占比、分母、完整 100%** | **本輪不確認**（方案 C） | 見 §4 | — | 【F】 |

---

#### 4. 本輪暫不納入「類別占比契約」的清單與依賴

> **本節全部是 Decision Gate，由客戶決定；作者不代決定。** 「延後」≠「永久排除」。

| # | 暫不納入項目 | 依賴／擋路事項 | 目前狀態（事實） | 仍為 Decision Gate？ | 標記 |
|---|---|---|---|---|---|
| X1 | 類別占比欄位（`ShareFact.share_of_covered_pct`、`covers_all_holdings`、`TargetFact`）作為**契約欄位** | 客戶 2026-11-08 方案 C（延後） | 程式物件存在（`allocation_evidence`），**不刪、不改**；契約不收 | 是（是否、何時收） | 【F】 |
| X2 | **分母定義**（`DenominatorFacts.value_twd` 的公式／口徑） | **D6 G-1**；`DEC-2026-11-04-03`（方向：保守 PORT，公式不變，另立完整性契約）；BL-0542 | 公式未裁；`resolve_full_keys` vs DG2 canonical 口徑亦見 D9（A2-H12 轉引） | 是 | 【F】 |
| X3 | 缺類別時其他類別是否仍可顯示百分比 | `DEC-2026-11-04-02` 方案 A 只管**UI 呈現**；技術／資料語意承接仍待 G-1 | 現行 `ui_v2/alo/logic.py::_build_alo2` 仍可能對其餘類別顯示 100%（`DEC-2026-11-04-03` 已知落差；`tests/ui_v2/test_alo_logic.py` 釘住）；**本稿不改、不替客戶判定** | 是 | 【F】 |
| X4 | **完整性契約**（完整／不完整／可比的判準） | G-1；open gate #1～#11（見下） | `chart_comparability` 等為內部候選 | 是 | 【F】 |
| X5 | **NAV 過期天數規則**（`NAV_NOT_READY_DAYS = 10`，嚴格 `>`） | **D7**；`DEC-2026-11-05-03` 五待決 (a)～(e)；D3(b) | 該筆 DEC 客戶裁示：不授權重新定義或搬遷，既有實作事實保留但**不得升格**為全頁產品規則 | 是 | 【F】 |
| X6 | **G-3**（配息推估引擎進 `ui_v3`）、**G-4**（摘要四格口徑）、**G-5**（狀態詞對映與 `no_holding`／`partial`／`normal` 字樣） | BL-0542；`DEC-2026-11-05-02`「不授權事項」；`DEC-2026-11-04-02`「G-1～G-5 仍須分別處理」 | 未授權 | 是 | 【F】 |
| X7 | **BL-0542 11 項 open gate** 逐碼處置 | D6；BL-0542 | 記錄但未裁決（見下表）。其中 8 碼在 `_CHART_AFFECTING_GATES`（影響圖狀態）；3 碼刻意不影響 | 是 | 【F】 |
| X8 | **FX 閘門開放**（`FX_OBS_DATE_RULE_VERIFIED`） | **D8**；BL-0217；`DEC-2026-11-08-02`（維持關閉；不以相同方法立即重跑；補跑未授權；開閘未核准） | `False` | 是 | 【F】 |
| X9 | **市值面**（類別市值、市值占比）、New UI2 市值基準接線 | NAV 組裝搬遷、NAV 10 日歸屬、FX 閘門、正式 UI 接線 | `BLOCKED_MARKET_BASIS`；`DEC-2026-11-05-04`「仍未授權」 | 是 | 【F】 |
| X10 | 「**淨投資金額 ＝ 成本**」語意確認 | 無專屬 Gate【NV】；C 題 3：若日後選成本占比，此題變擋路題 | repo 文件未見明文 | 是（待客戶答） | 【NV】 |
| X11 | **Complete Evidence 物件整體升格為正式契約** | D1 方案 C 已定「資料契約先行」，但 D2 逐域契約與 Digest schema 未核准；授權鏈未追認（`DEC-2026-11-08-03`）；`rule_ref` 只是 placeholder | 無 production 呼叫端（A2-H16 轉引，與 AUD 相符） | 是 | 【F】＋【NV】 |
| X12 | 真實 Active Sheet 覆蓋率 | D9；BL-0545；`DEC-2026-11-07-03`（探針協定）；客戶暫不提供輸入 | NOT VERIFIED | 是 | 【F】 |
| X13 | 直接持有（DIRECT）在 hld 頁如何顯示 | `alo_holdings` 檔頭已登記的未定題；無 Gate 編號 | 登記、未裁 | 是 | 【F】＋【NV】 |
| X14 | 兩套同鍵合併規則（hld／alo）是否收斂 | `PROJECT_RULES` 13.3；無專屬 BL【NV】 | 登記、未裁 | 是 | 【F】＋【NV】 |

##### 4.1 BL-0542 的 11 項 open gate（只列，不裁）

| # | 代碼 | 影響圖狀態？ | 白話 | 本稿與契約候選的關係 |
|---|---|---|---|---|
| 1 | `unclassified_comparability_unjudged` | 是 | 有未分類持倉時圖能否稱「可比」未裁 | 影響 C4 |
| 2 | `target_weight_sum_rule_undefined` | 是 | 目標權重和的容差規則未定 | 屬占比／目標側，本輪不涉 |
| 3 | `target_duplicate_bucket_unjudged` | 是 | 目標重複類別名的處理未裁 | 同上 |
| 4 | `fx_obs_date_lag_degradation_unjudged` | 是 | 匯率觀測日落後於淨值日是否降級未裁 | 市值面（X8／X9） |
| 5 | `stale_nav_degradation_unjudged` | 是 | 過期淨值是否降級未裁 | 市值面（X5） |
| 6 | `holding_nav_ccy_disagreement_unjudged` | 是 | 持倉幣別與淨值幣別不一致未裁 | 市值面；A7 |
| 7 | `fx_obs_date_rule_status_not_provided` | 是 | 呼叫端未傳匯率閘門狀態 | 市值面（X8） |
| 8 | `fx_obs_date_rule_unverified` | 是 | 匯率閘門為 `False` | 市值面（X8） |
| 9 | `tolerance_unset_effect_unjudged` | 否（刻意；客戶可推翻） | 容許帶未設的影響未裁 | 目標側，本輪不涉 |
| 10 | `omitted_row_reason_codes_undefined` | 否 | 略過列原因代碼未定義 | 影響 D1 |
| 11 | `non_holding_read_error_effect_unjudged` | 否 | 非持倉表讀取錯誤的影響未裁 | 影響 D2 |

【F】計法：8＋3＝11，與 `allocation_evidence` 的 `_CHART_AFFECTING_GATES`（8 碼）與 gate 產生段（另 3 碼）相符。【F】BL-0542 列所列代碼合計 11 個（作者自數；`fx_obs_date_rule_status_not_provided`／`fx_obs_date_rule_unverified` 並列計入）。逐碼對 Gate 編號**文件未指定**，上表「關係」欄為作者推測【I】。

---

#### 5. 不得做的解讀

| # | 不得做的解讀 | 為什麼（證據） |
|---|---|---|
| N1 | **淨投資金額（暫稱成本）占比 ≠ 市值占比。** 不得把 K4 的類別成本金額（或將來由它算出的任何比例）寫成「各類別占總資產（市值）多少」。 | 成本基準用 `cost_twd`（歷史投入），市值基準用 `units_shares × nav × fx`，兩者數值可大不同；C 題 3 方案 B 的風險即「成本占比可能被誤讀為市值占比」。`allocation_evidence` 刻意不輸出「占總資產 100%」欄，只有 `share_of_covered_pct` 加 `covers_all_holdings`。 |
| N2 | **非台幣基金不可整檔判不可分析。** 缺必要換算證據時，只有**相關台幣換算結果**維持無法判定；其原幣資料、台幣成本（K5）、持有單位、類別歸屬仍可整理。 | `DEC-2026-11-08-04` Q5；`DEC-2026-11-08-02` 要點 (1)。 |
| N3 | **延後 ≠ 排除。** 不得把「本輪不收類別占比契約」寫成「永不收／已否決」，也不得因此刪除 `allocation_evidence` 的占比相關欄位或既有歷史計算。 | 方案 C 原話：延後不等於永久排除；不刪既有正式功能或歷史計算。 |
| N4 | **不得重定義占比分母**，也不得把 `DenominatorFacts.value_twd`、`covered_value_twd` 稱為「正式分母」。 | G-1 未裁；`DEC-2026-11-04-03` 客戶裁示 (1) 公式不變。 |
| N5 | **不得顯示或暗示誤導性完整 100%**；缺必要 FX 使分母不完整時維持「資料未備＋未涵蓋範圍」。 | `DEC-2026-11-04-02` 方案 A（已核准；本稿不修改該呈現規則）。 |
| N6 | 缺值不得被讀成 0、完整、可比或安全；`unproven_zero` 不是「沒有這類」。 | `DEC-2026-11-05-04` 客戶裁示「另有規則」；`allocation_evidence`。 |
| N7 | 「淨投資金額」不得直接當「成本」寫進對客戶的說明。 | X10；repo 文件未見明文。 |
| N8 | 本稿候選欄位**不是契約**；「必備／選備／不納入／待決」是作者候選，不是客戶核准。`allocation_evidence` 內所有名稱仍是「內部候選、非已核准詞彙」。 | `DEC-2026-11-08-02` 仍未授權欄；`DEC-2026-11-08-04` 不授權事項。 |
| N9 | 不得用「覆蓋率」措辭（例：「已涵蓋 X% 真實持倉」）。 | BL-0545 NOT VERIFIED。 |
| N10 | 不得把 `DEC-2026-11-05-02`／`-04` 的歷史授權寫成「已追認／授權鏈完整」。 | `DEC-2026-11-08-03`：客戶保留歷史摘要、**未重新追認**。 |
| N11 | 不得新增「過期」「衝突」為正式狀態詞，也不得改任何門檻；本稿出現的 `nav_stale` 等僅是既有機器碼。 | `DEC-2026-11-08-04` Q4。 |

---

#### 6. 限制與未涵蓋範圍（單組揭露）

- 【F】本稿只涵蓋「持倉：持有單位、成本、類別金額」。**不涵蓋**：基金身份、淨值／績效、配息與事件、FX／總體指標、資料健康總覽、規則／Risk Cap／Action State、反證、Old UI 比較、policy 表（`premium_paid_twd` 等）。
- 【F】本稿**沒有**：定義占比分母、新增公式／門檻／Schema／狀態詞、把候選寫成核准。所有代碼與字樣引自既有程式或文件。
- 【NV】`docs/v2/44` §4.1／`57`／CONSTITUTION 未重讀；欄位定義轉引。`DEC-2026-11-04-02` 的客戶逐字 evidence 檔未讀。其餘 DEC 為要點轉述，**本稿無法核實客戶原話**。
- 【NV】客戶方案 C 裁示來自派工單轉述，`origin/main` 無對應 DEC；登記時請另行編號。
- 【NV】`opened_on` 缺值時的專屬原因碼未追到；`cost_orig_ccy` 幣別＝`holding.ccy` 為作者讀法。
- 【NV】測試未執行；golden 測試（`tests/test_alo_core_golden.py`）與突變測試僅轉引。
- 【NV】不宣稱窮舉：本稿部分敘述含「唯一」「只有」「全部」字樣，皆為作者讀法、未經窮舉驗證，不得引為全稱；「無 DEC」「無 BL」皆限於本組實際 `git grep` 的字面符號與範圍（`docs/DECISIONS.md`、`HANDOFF.md`、`BACKLOG.md`），不含別名或動態組字串。
- **單組作者揭露（`CLAUDE.md` §-2 規則 6）**：本稿由單一作者產出，**尚無獨立 QA**；涉 data semantics，依 `DEC-2026-10-16-05` 風險分級須至少 1 組真正獨立稽核後才視為已驗。本稿標【F】指「可由所引檔案文字重現」，不等於在執行環境中運行驗證。

---

#### 7. 列數（作者自計）

- §2.A：11 列；§2.B：5 列；§2.C：6 列；§2.D：8 列（候選項目共 30 列）。
- §3：8 列；§4：14 列；§4.1：11 列；§5：11 列。

---

## 對 #1177 草案的更正（只在本檔註記；不改已合併的 `d2_draft_A1`）

- **被更正處**：`docs/evidence/d2_draft_A1_fund_identity_nav_perf_2026_11_08.md` 的 C4 列把 6 個字串（含 `dividend_data_missing_unaligned`）都列為 `unavailable` 的 `reason` 值。
- **更正**：`reason` 實際只有 **5 種**：`no_series`、`no_restored_value`、`window_short`、`window_unknown`、`dividend_data_missing`。`dividend_data_missing_unaligned` 只是 `UNAVAILABLE_REASON_TEXT` 的**第 6 個文字鍵**（白話變體），由 `_unavailable(..., text_key=...)` 在「配息型基金、窗內配息筆數為 0、但 `annual_div_rate_div_count` > 0（有配息紀錄卻一筆都沒對齊到淨值日）」時選用；此時輸出的 `reason` 仍是 `dividend_data_missing`。
- **本次重驗（FACT，唯讀對 origin/main 85a158bb）**：`services/fund_total_return.py` 中 `_unavailable(` 的呼叫點傳入的 `reason` 僅為 `"window_short"`、`"window_unknown"`、`"dividend_data_missing"`、`"no_restored_value"`／`"no_series"`（同一呼叫依有無序列二選一）、`"no_restored_value"`；`dividend_data_missing_unaligned` 只出現在 `UNAVAILABLE_REASON_TEXT` 與 `text_key=` 參數；測試 `tests/test_pr1a_audit_fixes.py` 也是以 `UNAVAILABLE_REASON_TEXT[...]` 比對 `label`，未把它當 `reason`。
- **影響**：契約若以 `reason` 當缺漏原因碼欄，值域是 5 種；第 6 種屬呈現文字，歸「白話全句」類（E1 §1 列 12，Excluded）。此更正不改任何程式與已合併文件。

## 下一批最值得核准事項（最多三題）

> 題目只從三份草稿已列的真阻塞中挑（原「淨投資金額是否等於成本」一題，因 E3 自述方案 C 下暫不擋，已降為本節末的「待確認備註」，不再列為三題之一）；「正確性／風險」「成本與速度」與缺點為作者定性判斷【INFERENCE】，已把原本分開的速度與 Token 欄合併。**推薦不是裁示，客戶未裁示前不得採納。**所有方案都**不授權**新公式、程式施工、FX 開閘、OneBrain／Digest 實作；凡需改程式者，核准契約文字後仍須另行授權。

### 題一｜Sheet「基金代號」欄的格式檢查：契約要不要寫進去？（E2 S7、V6；身份）

**白話背景**：客戶已裁示該欄固定為 MoneyDJ 基本代碼，遇 URL、後綴、格式異常要標「違反欄位契約」（程式標記名 `sheet_code_contract_violation`）並保留原值（`DEC-2026-10-29-01` 第 4 項）。但現行程式把代碼轉成取數用代碼（`full_key`）時，接受「主碼＋`-`＋後綴」，且呼叫端不傳輸入來源，所以 production 今天**打不出**這個標記；打標記的 Shadow hook 旗標預設也是關閉（`DG2_SHADOW_ENABLED=False`，關閉時不執行）。契約要不要寫這件事，客戶未裁。

| 方案 | 做法 | 正確性／風險 | 成本與速度 | 缺點 |
|---|---|---|---|---|
| A | 契約只描述現況：取數用代碼今日可帶後綴，列為已知缺口，不寫入口規則 | 中／低：不改行為，但後綴碼可能被當正式取數鍵 | 快、低 | 與既有裁示第 4 項並存矛盾，日後仍要裁 |
| B | 契約文字寫明：Sheet 欄遇後綴／URL／格式異常須標「違反欄位契約」、原值保留、不靜默截斷（僅契約文字；實作另授權，需由能證明來源的呼叫端往下帶，會改 production 介面） | 高／中：契約先於實作，有落差 | 中 | 落地要改介面；落差期間須在契約標「尚未實作」 |
| C | 契約寫明入口直接拒絕帶後綴輸入（不產出取數用代碼） | 取決於後續驗證／高：與「不剝除、原值保留」及「後綴只在已驗證 mapping 命中時才是通路資訊」有張力，屬新行為 | 慢、高 | 可能擋掉合法的保險商品代碼輸入 |

**推薦：B（僅契約文字，不施工）。** 理由：與既有裁示同向、不新增規則；代價是契約與實作暫有落差，須明標。

### 題二｜1 年含息輸出缺的欄位，契約要先認哪幾個？（E1 §0 結論 5、§1 列 3、5、7、8、9；報酬）

**白話背景**：現有輸出只有 `window_days`，沒有窗口起訖日、資料末端日期（as_of）、取得時間，也不含計價幣別與算法版本；NAV 列另有 `nav_date`／`fetched_at`。沒有這些，1Y 數字無法說明「截至哪天、取自哪個窗口、是原幣還是 TWD」。補欄要改程式。**另請留意**：1Y 含息的公式層另有 BL-0427 (1)(3)(4)(5) 未裁，不在本題內，須走 Decision Gate；本題只問欄位。

| 方案 | 做法 | 正確性／風險 | 成本與速度 | 缺點 |
|---|---|---|---|---|
| A | 五欄全部只登記為 Pending，不要求補欄 | 中／低（不改碼）；但數字可被誤讀為更新、更長或 TWD 報酬 | 快、低 | 契約的 1Y 欄位無法自證時點與窗口 |
| B | as_of、窗口起訖日、取得時間、幣別四欄納入 Required（算法版本維持 Pending）；補欄另授權、不改算法與門檻。**若選 B，E1 §1 列 7 由 Pending 改 Required、列 9 由 Optional／Pending 改 Required，列 3 維持 Required，列 5 維持 Pending** | 高／中：需另授權小幅改碼，並先確認 1Y 含息跨新版適用 | 中 | 要先確認跨新版適用，否則欄位無所附麗 |
| C | 分階段：先認 as_of 與幣別（由 NAV 契約同一基金的 `nav_date`／`ccy` 組合，契約註明來源、不改輸出）；窗口起訖日、取得時間、算法版本維持 Pending | 中高／中：組合邏輯分散，窗口起訖日仍缺 | 快、低 | 起訖日仍缺，需日後再裁 |

**推薦：C。** 理由：不改碼就能先補最低限度的時點與幣別證據；代價是窗口起訖日仍缺。客戶亦可逐欄勾選（列 3、7、8、9 各自獨立），不必整包決定。

### 題三｜取數用代碼的別名表與 MoneyDJ 頁型，算不算契約的一部分？（E2 K11／K12；身份）

**白話背景**：同一個輸入代碼經不同別名表會得到不同的取數用代碼（例：`ACTI171`／`ACTI7`／`ACTI71` 在內建表都指 `ACTI71`，單獨呼叫解析器而不套別名表則得三個）；origin/main 根目錄沒有別名檔 `fund_code_mapping.csv`，部署環境是否另有，未查證。頁型（境內／境外）由網址或對照表決定，裸碼是推斷、不可靠。

| 方案 | 做法 | 正確性／風險 | 成本與速度 | 缺點 |
|---|---|---|---|---|
| A | 別名表與頁型不入契約；契約註明「取數用代碼的值取決於部署端別名表」 | 中／低：不改行為，但同一輸入可能得不同代碼 | 快、低 | 跨環境結果可能不一致，無契約可查 |
| B | 契約只加記「所用別名表的出處」（已有 `mapping_source` 診斷欄，E2 K8）；別名表內容與頁型仍不入契約 | 中高／低 | 中、中 | 內容仍無人負責維護 |
| C | 別名表與頁型整體納入契約，並指定維護者 | 高／中：涉及誰維護、如何版本化，屬新責任 | 慢、高 | 需客戶指定維護者與更新流程 |

**推薦：A（暫不入契約，維持現況並明標限制）。** 理由：別名表現況是程式內建＋可選檔，把它升格要先答「誰維護」；先明標限制成本最低。

### 待確認備註（非阻塞，不列為三題之一）

「淨投資金額」是否等於「成本」：E3 自述方案 C（不收占比）下暫不擋；在客戶確認前，本檔一律稱「淨投資金額（暫稱成本）」，不得對外說明為成本（E3 §0 結論 4、X10、N7）。若日後選成本口徑的占比，此題才變成擋路題。

## 驗證與限制（本檔層級；三部各自的限制見其內文）

- 本檔整合時只做文件層動作：讀 origin/main 原文與三份草稿、對 `services/fund_total_return.py` 做上述唯讀重驗；**未執行任何應用程式測試、未取任何資料、未改任何程式**。
- 三部內文來自三組單組作者草稿，未經第二組複驗；各表的列數、分類與「小計」為作者人工統計，整合時以 Python 逐表重數欄數一致（見 PR／提交說明）。
- 三題的方案表與推薦為整合作者判斷；客戶方向的原話只有要點轉述，repo 內無逐字存檔。
