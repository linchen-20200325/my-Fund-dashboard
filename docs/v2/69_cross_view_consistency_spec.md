# 69 — Cross-View Data Consistency Gate：audit、Matrix、Gap、test proposal（規格草案）

> **性質**：資料治理規格草案。**本輪只做 audit、matrix、gap、test proposal**；不改 source precedence、不定 canonical contract、不改任何 `.py`、不改 `CLAUDE.md`、不改 `docs/v2/44_fund_ui_ssot.md`、不動 `INDICATOR_SPECS`。
> **客戶原文**：`docs/evidence/decisions/2026-10-28_cross_view_consistency_ruling.md`（逐字）。**決策登記**：`docs/DECISIONS.md` `DEC-2026-10-28-01`（客戶裁示）。**永久原則**：`PROJECT_RULES.md` 13.3。**工作項**：`docs/BACKLOG.md` BL-0519～BL-0524。
> **不取代 BL-0509**：BL-0509 多日 probe 照原計畫繼續（客戶原文）；本件是下一個獨立資料治理 batch。
> **基準**：main `10e4670c`（2026-10-28 `git fetch` 後）。會漂移的數字都附 SHA；引用前請重查。
> ⚠️ **未經第二組獨立驗證**：本文由單一寫作組依四份獨立唯讀審計報告整理，另自行重驗 12 條承重宣稱（附錄 A）。其餘宣稱一律標「引用自審計報告，未重驗」。見第 10 節。

## 1. 規則與正式架構鏈（客戶原文，不改寫）

核心規則：

> Same canonical instrument + same metric + same as-of + same currency/share class = same canonical value across all views.

正式架構鏈：`Raw Sources` → `Source Resolution / Validation` → `Canonical Instrument Data` → `Domain Calculation` → 各 Page Data View → `One AI Brain`。

禁止各頁自行選來源，也禁止各頁平行計算同一個 metric。若同一 as-of 的來源數值衝突，不得靜默選一個；至少留下 selected source／rejected source／difference／reason／freshness。尚無法判斷時顯示「⬜ 資料來源不一致，暫無法判定」。

## 2. 分層歸屬（提案；對齊 `CLAUDE.md` §8.2 四層，不改層級規則）

| 層 | 本件的職責 | 現況缺口（見第 5 節） |
|---|---|---|
| L0 `shared/` | 純常數與 schema：source-conflict record 欄位、reason enum、容差常數、canonical identity 欄位定義 | 無 canonical identity 欄位，無 conflict record schema |
| L1 `repositories/` | 只供應「候選值」（附 source／fetched_at／as-of／currency），**不得自行選來源** | 現行 NAV waterfall 在 L1 內「第一個夠長的來源勝出」，選擇權在 L1 |
| L2 `services/` | Source Resolution／Validation（precedence、freshness、identity validation、conflict 記錄）與 Domain Calculation（報酬、估值、FX 換算）的單一實作 | 報酬與估值有多套實作；沒有 resolver |
| L3 `ui`／`ui_v2` | 只渲染 Data View 與 conflict 記錄或「⬜」文字，不選來源、不算 metric | 數處 UI 層直接組字串餵 AI、直接讀 raw metric |

## 3. 證據標籤與審計範圍

- **FACT**：在 main `10e4670c` 的程式碼中讀到，或本文附錄 A 重跑指令確認。
- **INFERENCE**：由程式碼機制推得，但沒有在有網路的環境執行過。**本輪審計全程無網路，沒有任何一條「兩頁顯示不同數字」被實際觀察到。** 下表與缺口清單中的「不一致」一律是**機制層級**的可能性，不是已發生的數字落差。
- **UNVERIFIED**：全稱句或單次 grep 的結論，沒有第二種方法證明，或審計報告自己標為未驗。
- 審計角度四組：A＝NAV／價格來源、cache、as-of、precedence；B＝報酬公式、FX、benchmark；C＝canonical identity、Sheet 作為資料存放、AI 輸入；D＝股票／ETF／指數價格路徑、現有測試、測試提案。審計 A、B、D 讀 `origin/main`（`10e4670c`），審計 C 讀本機 `b17029d1`（較 main 少兩個 commit，未 diff），見第 10 節。

## 4. Cross-View Data Consistency Matrix

欄位依客戶原文。**「Consistent?」欄一律以文字標示，不靠顏色**：🟢 一致｜🔴 不一致（機制已由程式碼證實，但數值落差未經執行期驗證）｜🟡 機制上可能不一致，未經執行期驗證｜⬜ 無法判定。

「Single View」＝舊版單一基金頁（`ui/tab2_single_fund.py`）與找基金；「Holdings」＝舊版我的持股（`ui/tab3_portfolio.py`、`ui/tab3_t7_ledger.py`）與 vNext 持股（`ui_v2/hld`）；「Allocation」＝vNext 配置（`ui_v2/alo`）與舊版配置／帳本估值；「AI Input」＝目前各分頁自行組裝的 AI 快照（`One AI Brain` 尚未實作）。

### 4.1 基金

| Instrument / Metric | Single View | Holdings | Allocation | AI Input | Source | As-of | Currency | Consistent? | Root Cause / Action |
|---|---|---|---|---|---|---|---|---|---|
| 基金 NAV | tab2：`metrics["nav"]`＝series 最後一筆（含 Google Sheet `nav_history` 合併）；banner 值另取純量 `nav_latest` | 舊版：以裸代碼載入的另一份 series，存在 `st.session_state` 無 TTL；T7 帳本市值另走 `get_latest_nav`；vNext hld：關閉 Sheet 歷史合併 | 舊版帳本：`get_latest_nav`；vNext alo：units × nav 表最新列 | tab2／tab3 以 f-string 讀同頁 in-memory dict | A 鏈 waterfall（L1 `fetch_fund_from_moneydj_url`）；`get_latest_nav` 另走 Yahoo 優先 | 見下列 NAV date | 見下列 currency | 🔴 不一致（機制：同基金存在兩條獨立 NAV 取得路徑與三種呼叫形態，FACT；數值落差未驗） | 缺口 G-NAV-1～G-NAV-5；需 Decision Gate（source precedence、canonical identity） |
| NAV date | tab2：純量 `nav_date` 優先於 series 最後日期 | 舊版持股 `metrics["nav"]` 本身無日期；vNext hld：每列 `nav_date` | vNext alo：取最新 `nav_date`，超過 10 天（`NAV_NOT_READY_DAYS`）不納入；舊版帳本 `get_latest_nav` 無日期 | 快照多半不含 NAV 日期（tab2 該行未見日期，未驗全文） | 純量 meta（direct-URL／TCB／FundClear／TDCC meta）與 series 為不同來源 | 純量日期與 series 末日之間無 reconcile | n/a | 🔴 不一致（機制：日期語意與新鮮度門檻兩套，舊版 2／7 天只警示、vNext >10 天扣留） | G-NAV-6、G-NAV-7；freshness 規則統一須 Decision Gate |
| Currency | tab2：來源回報幣別 | 舊版：Sheet 幣別優先於來源（2026-10-10 客戶裁示）；vNext：持股列宣告幣別為準，A 鏈幣別刻意忽略 | vNext alo：幣別缺則「⬜」；非 TWD 需 FX 列 | 同 tab2／tab3 | 來源 meta、Sheet、`reconcile_row_currencies` | n/a | 核心欄位 | 🟡 機制上可能不一致，未經執行期驗證（衝突時各頁處理不同：舊版記 log＋計算時 fail-closed，vNext 扣留顯示） | 幣別驗證邏輯已存在但分散；統一須 Decision Gate（canonical identity） |
| Return 1D | 找不到 1D 報酬欄位：舊版 `calc_metrics` 只有 1W／1M／3M／6M／1Y 等 | 同左 | 同左 | 同左 | — | — | — | ⬜ 無法判定（本輪審計未發現任何 view 輸出 1D 基金報酬；「不存在」為單組結論，UNVERIFIED） | 若未來新增，須先走 canonical return 實作；見 G-RET-1 |
| Return 1M／3M | 舊版健診表優先用 MoneyDJ wb01 公告值，缺值才退回自算（列數窗） | 衛星戰情室 `mk_dashboard` 只用自算（22／65 列）；vNext hld 用使用者自選日曆窗價格報酬 | vNext alo 不輸出報酬 | tab2 快照讀原始 `ret_1m`／`ret_3m` | wb01 scrape｜自算列數窗｜vNext 日曆窗 | 窗口語意三種 | 原幣（vNext）｜原幣（舊版） | 🔴 不一致（機制：同名「近 1M」存在三套定義，FACT；數值落差未驗） | G-RET-1、G-RET-2；公式統一須 Decision Gate（formula） |
| Return 1Y | tab2 KPI：含息 SSOT（`resolve_1y_total_return`，窗口 ≥350 天才有值） | tab3 表欄「1Y含息%」直接讀原始 `ret_1y_total`，未過 SSOT 門檻；vNext hld 為價格報酬 | vNext alo 不輸出 | tab2 快照與 tab3 AI 摘要讀原始值；`ai_service`／健診報告走 SSOT | 還原淨值（reinvest）｜自算列數窗｜wb01｜vNext 價格報酬｜持有期簡單加總 | 252 列 vs 日曆窗 vs 買入日起 | 原幣｜TWD（帳本） | 🔴 不一致（機制：至少四種不同數學的「1Y／含息」，且 AI 與畫面可讀不同門檻，FACT；數值落差未驗） | G-RET-2～G-RET-5；需 Decision Gate（formula） |
| Benchmark | tab2／健診：`services/capture_ratio.py::benchmark_for_currency`（TWD→token `"TWII"`、USD→token `"SPX"`，其餘幣別→`None`；token 對應到 Yahoo 符號 ^TWII／^GSPC 的映射為審計 B 所述、本輪未追，UNVERIFIED；365 天共同日期） | 衛星戰情室：使用者選 SPY／QQQ，9 個月窗，不分基金幣別 | vNext 無逐基金 benchmark | 依各頁 | Yahoo 指數｜Yahoo ETF | 365 天 vs 9 個月 | 指數原幣 | 🔴 不一致（機制：同基金在兩頁對應不同 benchmark 與窗口，FACT） | G-BM-1；benchmark 登記表與口徑須 Decision Gate |
| Fund code | tab2：`canonicalize_moneydj_url`＋`parse_moneydj_input`（平台後綴被剝除或保留視輸入形式） | 舊版持股：`_extract_code_from_url`（原樣）；vNext：`fund_keys`（保留平台後綴） | 同 vNext | n/a | Sheet 使用者輸入字串 | n/a | n/a | 🔴 不一致（機制：至少六種金鑰推導規則，且平台後綴代表不同 NAV 序列，FACT；是否已實際誤配未驗） | G-ID-1；canonical identity 須 Decision Gate |
| ISIN／canonical identity | 無 canonical identity 物件；ISIN 只是選填的選股池欄位，供 NAV 回補查詢 | 保單 Sheet 無 ISIN 欄 | 同左 | 快照不帶 canonical id | 使用者輸入 | n/a | n/a | ⬜ 無法判定（不存在可比較的鍵） | G-ID-2；須先定義 canonical contract（Decision Gate） |
| Share class | 程式碼中沒有 share class 欄位 | 同左 | 同左 | 同左 | 僅 `docs/v2/54` 的未核准設計備忘 | n/a | n/a | ⬜ 無法判定 | G-ID-3；須 Decision Gate |
| Source | tab2：`source_trace` 記錄；series 屬性 `source` | `finalize_fund_metrics` 不把 series 屬性複製進 `metrics`，舊版下游失去血緣 | vNext：`provenance[code]`（source、cache_fallback、stale、ccy_source、latest_from） | 快照不帶逐數字來源 | 見 6.1 | n/a | n/a | 🔴 不一致（機制：vNext 有逐列血緣，舊版 downstream 沒有） | G-PROV-1 |
| fetched_at | tab2：`_moneydj_fetched_at`（快取結果內為原始執行時間） | 舊版 session 副本無過期戳；vNext 逐列 `fetched_at` | 同 vNext | 不帶 | A 鏈 | n/a | n/a | 🟡 機制上可能不一致，未經執行期驗證 | G-CACHE-1、G-CACHE-2 |
| as_of（估值基準日） | 純量日期或 series 末日 | 無統一定義 | alo：NAV 日 + FX obs_date ≤ NAV 日；舊版：NAV 任意日 + FX 最新價 | 不帶 | 多 | 多套 | 多 | 🔴 不一致（機制：同一組合兩套估值語意，FACT） | G-VAL-1、G-FX-1 |
| Allocation valuation | 不適用 | 舊版配置權重＝Σ `invest_twd`（成本，非市值） | vNext alo：基準可選成本｜市值；舊版帳本市值＝units × `get_latest_nav` × 最新 FX | 依頁 | Sheet 成本｜NAV｜FX | 見上 | TWD | 🔴 不一致（機制：至少四套 units×NAV×FX 實作，各自夾帶不同護欄，FACT） | G-VAL-1；估值方法須 Decision Gate（valuation methodology） |
| FX rate／FX date | 舊版 `get_latest_fx`：Yahoo 5 日最後一筆，無日期回傳 | 舊版持股與帳本用最新價；股息換算用逐日 5y ffill；組合報酬用 merge_asof 7 日容忍 | vNext alo：Sheet `market_indicator` 列，obs_date ≤ NAV 日；USD 列因 `FX_OBS_DATE_RULE_VERIFIED=False` 不會被取數寫入 | 部分快照以最新價換算 | Yahoo｜FRED｜open.er-api｜Frankfurter｜Sheet 列 | 最新價 vs 前一週日 vs NAV 日 | USDTWD 等 | 🔴 不一致（機制：FX 日期規則不同，且 vNext 目前在 USD 持股上顯示「⬜ 缺換算匯率」而舊版顯示 TWD 市值，FACT） | G-FX-1～G-FX-3；FX cutoff 須 Decision Gate |

### 4.2 指數與市場指標

| Instrument / Metric | Single View | Holdings | Allocation | AI Input | Source | As-of | Currency | Consistent? | Root Cause / Action |
|---|---|---|---|---|---|---|---|---|---|
| VIX（`^VIX`） | 不適用 | 不適用 | 不適用 | `ai_service` 取 `us_indicators` 字典 | Yahoo；市場頁 5y、B 線 2y、風險雷達 6mo、健診 1y、流動性 5y，各自快取鍵 | vNext 排除未收盤 K 棒；舊版 `iloc[-1]` 原樣 | 指數點 | 🟡 機制上可能不一致，未經執行期驗證（盤中時舊版可能多一根未收盤 K 棒；FACT 為規則不同） | G-IDX-1；as-of／收盤規則統一須 Decision Gate |
| S&P 500（`^GSPC`） | 不適用 | 不適用 | 不適用 | 同上 | Yahoo；市場頁 5y、風險雷達 1y、轉折點變動窗 | 同上 | 指數點 | 🟡 機制上可能不一致，未經執行期驗證 | G-IDX-1 |
| TAIEX（`^TWII`） | 不適用 | 不適用 | 不適用 | 未見 | Yahoo `^TWII`（BL-0518 核准） | vNext 市場頁 | 指數點 | ⬜ 無法判定（審計只見 vNext 市場頁一個消費者，單一消費者無從跨頁比較；「沒有第二處」為 UNVERIFIED） | 新增消費者時納入矩陣 |
| US10Y／US2Y（FRED `DGS10`／`DGS2`） | 不適用 | 不適用 | 不適用 | `us_indicators` 字典 | FRED：市場頁 n=1500、風險雷達 n=120、`us_indicators` 2600、B 線走 vintage | 觀測日 vs 發布日語意 | % | 🟡 機制上可能不一致，未經執行期驗證 | G-IDX-1；FRED 快取 TTL（30 分）與 Yahoo（10 分）不同 |
| USDTWD | 見 4.1 FX 列 | 見 4.1 | 見 4.1 | 見 4.1 | 同 4.1 | 同 4.1 | TWD per USD | 🔴 不一致（同 4.1 FX 列） | G-FX-1～G-FX-3 |

### 4.3 股票／ETF

**本輪審計未發現任何 view 輸出單一股票或 ETF 的價格**（close／adjusted close／price date／ticker 的 view 皆不存在）。基金持股是 MoneyDJ 基金紀錄；SPY／QQQ／指數 ticker 只作 benchmark 或市場指標。Yahoo 的收盤序列為原始 close，未見 adjusted close 路徑（僅 Yahoo 序列；AlphaVantage NAV 備援 `repositories/fund/sources.py` 讀 `5. adjusted close`，該備援是基金 NAV 而非股票價格）。另有一條已知的非 UI 價格路徑：`scripts/export_fund_db.py` 的 `_DEFAULT_US_IDS`（NVDA、AMD、TSM、AAPL、MSFT、SPY、QQQ）由 `write_us_market` 寫入，經 `.github/workflows/export_db.yml` 執行；其產出的下游消費者 **UNVERIFIED**（本輪未追），故上述「沒有 view 輸出個股／ETF 價格」僅限 `ui`／`ui_v2` 的 view。此結論為單組 grep 與讀碼（審計 D），「沒有其他消費者」為 UNVERIFIED。故股票／ETF 的 close、return、currency、ticker／canonical ID 等列在本矩陣中**不出列**；若未來新增，必須先建立 canonical identity 與 as-of 規則，再開 view。

## 5. Gap 清單

標籤：F＝FACT（機制已由程式碼證實）、I＝INFERENCE、U＝UNVERIFIED。「DG」＝是否需要 Decision Gate（客戶 2026-10-28 列舉：source precedence、canonical identity、valuation methodology、FX cutoff、formula）。**每條 gap 的「實際數值落差」皆未經執行期驗證。**

### 5.1 NAV 與來源（審計 A，D1～D11）

| ID | 內容 | 標籤 | DG |
|---|---|---|---|
| G-NAV-1（A-D1） | 呼叫形態不同：tab2／健診／研究／hld 走 URL 形式或 `auto_fetch_moneydj`（先試 yp010000 再 yp010001）；舊版持股批次載入用**裸代碼**並先 `clear_all_caches()`。L1 快取鍵不同、頁型順序不同、略過 direct-URL meta | 機制 F／落差 I | 是（precedence） |
| G-NAV-2（A-D2） | 舊版 series 合併 Google Sheet `nav_history`（live 同日勝出）；vNext 因 `NAV_HISTORY_PROVENANCE_VERIFIED=False` 關閉讀取 | F／I | 是（Sheet 不應為市場資料 SSOT 的判斷） |
| G-NAV-3（A-D3） | `get_latest_nav`：第二條獨立 NAV 路徑（Yahoo 以基金代碼為 ticker 優先 → Yahoo secId → cnyes → Morningstar），回傳裸 float，無日期、無來源；供 T7 市值與 `fee_deduction` | F | 是（precedence、valuation） |
| G-NAV-4（A-D4） | 舊版持股的 series 存 `st.session_state`，無 `loaded_at`／TTL | F（本文已重驗無 `loaded_at`）／I | 否（可作 BL 修正，但屬 freshness 規則，建議併入 DG） |
| G-NAV-5（A-D5／D8） | vNext 拒絕以名稱／代碼搜尋得到的 Morningstar secId，並要求 `full_key` 相等；舊版照舊採用 | F／I | 是（identity validation） |
| G-NAV-6（A-D6） | 舊版純量 `nav_latest`／`nav_date`（meta）與 `series[-1]` 來自不同來源，無 reconcile | 機制 F／落差 I | 是 |
| G-NAV-7（A-D5） | 新鮮度門檻：舊版 `MJ_FRESH_DAYS_GREEN=2`／`YELLOW=7` 警示但仍顯示；vNext `NAV_NOT_READY_DAYS=10` 扣留 | F | 是（freshness requirement） |
| G-NAV-8（A-D7） | hld 與 exp 相差：exp 在 L1 之上再疊 15 分鐘 memo，最壞約 30 分鐘 | F（檔內自述） | 否 |
| G-NAV-9（A-D10） | L1 對不完整結果不快取，每次呼叫重跑 waterfall，可能落在不同來源 | 機制 F | 是（precedence） |
| G-NAV-10（A-§6） | NAV 沒有任何兩來源同 as-of 比對；waterfall 的觸發條件是「前一來源點數不足」，不是新鮮度或數值衝突 | F（讀碼）／全稱 U | 是 |
| G-DOC-1 | 文件與程式不符：`CLAUDE.md` §2.1 寫「FundClear 主、TDCC 主」，程式 waterfall 先走 Allianz 站（部分代碼）→ FundClear → Cnyes → TCB…，TDCC 只用於 meta（`_src_tdcc_meta`），不在 NAV series waterfall 內（附錄 A 已重驗） | F | 是（precedence；**本輪不改 `CLAUDE.md`**，僅記錄） |
| G-NAV-11 | 倉庫內有 GitHub 提交的 fallback `cache/nav/TLZF9.json`（最後一點 2026-04-23），`scripts/fetch_nav_cache.py` 無作用中 workflow；舊版與 vNext 都可能採用（vNext 標示 `cache_fallback`） | F（引用自審計 A，未重驗） | 否 |

### 5.2 報酬、FX、benchmark（審計 B）

| ID | 內容 | 標籤 | DG |
|---|---|---|---|
| G-RET-1（B-D1） | 「近 1M／3M」：健診表優先 wb01 公告值，缺值才自算；境內基金 `_fetch_domestic_perf` 恆回空，故境內只用自算；衛星戰情室只用自算 | F（`_fetch_domestic_perf` 存在已重驗；「恆回空」引用自審計 B，未重驗）／落差 I | 是（formula） |
| G-RET-2（B-D2／D5） | 1Y：SSOT 含息（R4）、自算列數窗（R1）、wb01、持有期簡單加總（R9）、vNext 價格報酬（R11）並存；tab2 AI 快照與 tab3 表欄／AI 摘要讀原始 `ret_1y_total`，繞過 `resolve_1y_total_return` 的 ≥350 天門檻 | F（`RET_1Y_RESTORED_MIN_WINDOW_DAYS=350` 已重驗）／落差 I | 是 |
| G-RET-3（B-D3） | R1 `_ret(n)` 以列數取窗、無日曆跨度護欄；稀疏或合併歷史時「1Y」可能不是一年 | F（引用自審計 B，未重驗） | 是 |
| G-RET-4（B-D4） | vNext hld 的區間報酬為價格報酬、原幣、使用者窗口；舊版含息與 TWD 帳本報酬不同；`ui_v2` 只有各頁 `source.py` 可 import `services.v2_tables`（`docs/v2/49`），不能直接 import 其他 `services` 模組，故 vNext 無法直接共用舊版 `services` 的報酬實作 | F（引用）／I | 是 |
| G-RET-5（B-annualisation） | 年化口徑四種：固定 N 年、rows/252、日曆日/365.25、cum/years 線性 | F（引用） | 是 |
| G-RET-6 | `ytd` 鍵在 tab2 快照被讀取，但全 repo 沒有產生者（死鍵，已重驗：僅一個讀取點） | F | 否 |
| G-RET-7 | `compute_1y_total_return_mk_simple` 已無 production caller 但仍從 `services/health/__init__.py` 匯出（已重驗） | F | 否 |
| G-BM-1（B-§3） | benchmark 三種定義：健診／tab2 指數（依幣別）、衛星 SPY／QQQ 使用者切換、vNext 無逐基金 benchmark（後者 UNVERIFIED 窮舉） | F／U | 是 |
| G-FX-1（B-X1／X3） | 舊版估值用最新價 FX（無日期、5 分鐘快取），vNext alo 用 obs_date ≤ NAV 日的 FX 且 USD 閘門關閉 | F（`FX_OBS_DATE_RULE_VERIFIED=False` 已重驗） | 是（FX cutoff） |
| G-FX-2（B-X2） | 舊版內部三種 FX 基準：最新價、5y 逐日 ffill、10 分鐘 series（merge_asof 7 日容忍） | F（引用） | 是 |
| G-FX-3（B-X4／X5） | T7 在 FX 失敗時退回帳本平均匯率或寫死表（USD 32.0 等），僅以 session 旗標標示；組合報酬排除非 USD／TWD 基金，健診卻支援其他幣別 | F（`_FX_FALLBACK` 存在已重驗；其餘引用） | 是 |

### 5.3 identity、Sheet、AI（審計 C）

| ID | 內容 | 標籤 | DG |
|---|---|---|---|
| G-ID-1（C-F9.3） | 基金代碼推導：`parse_moneydj_input`、`canonicalize_moneydj_url`、`fetch_fund_from_moneydj_url` 內 fallback regex、policy `_extract_code_from_url`、cache key 正規化、`fund_keys` 至少六種規則；`fund_keys` 檔頭自陳其他輸入「本組沒有逐一比對」（已重驗）；平台後綴＝不同 NAV 序列 | F／高風險 I | 是（canonical identity） |
| G-ID-2（C-F9.1／F9.2） | 沒有 canonical instrument 物件；ISIN 為選填、手填，持股 Sheet 無 ISIN 欄（`share_class`、`canonical_id` 在 `*.py` 已重驗 0 命中） | F | 是 |
| G-ID-3（C-F9.5） | `_morningstar_search_secid` 取 `results[0]` 且不驗 ISIN／名稱／幣別／級別，結果會被快取並回存選股池（`results[0]` 已重驗；回存引用自審計 C） | F／高風險 I | 是 |
| G-ID-4（C-F9.4） | 鍵形態：裸代碼、(policy_id, code)、holding_id；`alo_holdings` 比對不改大小寫、無補零 | F（引用）／U | 是 |
| G-SHEET-1（C-F11.2） | `nav_history` 為 Sheet 存放的 NAV 序列，並入舊版 series；live 全敗時「rescue」成為唯一 series；僅以 `source_trace` 註記 | F（引用，合併邏輯 `groupby(level=0).last()` 已重驗） | 是 |
| G-SHEET-2（C-F11.3） | vNext 讀使用者 Active Sheet；舊版重取路徑仍用 `POLICY_SHEET_ID`；兩份 Sheet 理論上可給出不同 units／成本 | I／U | 否（屬 ⚙️ 設定 Gate） |
| G-VAL-1（C-F11.2） | units×NAV×FX 至少四套實作：`models/ledger.py::Position.value_twd`、`services/portfolio_csv.py::enrich_returns`（有 0.2～5 倍護欄會把值清空）、`ui_v2/alo/logic.py`、`services/policy_fee_optimizer.py` | F（引用） | 是（valuation methodology） |
| G-AI-1（C-F12） | `One AI Brain` 未實作；各分頁自行組裝快照；`ui_v2`／`services/v2_tables` 無 AI 呼叫 | F（引用） | 是（AI 介面屬 BL-0490／0495／0496 範圍） |
| G-AI-2（C-F12.2） | tab3 AI 快照指紋＝code｜invest_twd｜len(series)｜currency｜tier…，不含 NAV 值、NAV 日期、FX 值、fetched_at；`ai_summary.py` 只要 session 內有舊 AI 文字就顯示，不比對 snapshot 變更，只顯示字元數 | F（引用）／落差 I | 否（修補屬 BL-0523；不改公式，但改 AI 行為時依第 5 節 Model Gate 評估） |

### 5.4 as-of 與快取分歧（審計 A、D）

| ID | 內容 | 標籤 | DG |
|---|---|---|---|
| G-CACHE-1（D-A2） | `fetch_yf_close` 的快取鍵隨位置參數／關鍵字參數與預設值而異；同一 ticker（`^VIX`、`^GSPC`、`USDTWD=X`）有多個快取條目，TTL 皆 10 分鐘但獨立填充，`fetched_at` 可差至 10 分鐘 | F（讀碼＋審計 D 的 grep；`^VIX` ≥5 個呼叫點為審計 D 的指令結果，未重驗） | 否 |
| G-CACHE-2（A-§4） | 沒有任何快取以 (canonical instrument, as-of, share class) 為鍵；鍵是呼叫端傳入的原始字串 | F | 是（隨 canonical contract） |
| G-IDX-1（D-A3） | 舊版 `iloc[-1]` 與 vNext 收盤規則不同（vNext 排除未收盤 K 棒、用交易所本地日期；FX 取前一週日） | F（引用）／落差 U | 是（as-of 規則） |
| G-PROV-1（A-§5） | `finalize_fund_metrics` 不把 series 屬性複製進 `metrics`，舊版下游失去 source／fetched_at | F | 否 |

## 6. 多來源政策表（資料層定義，頁面不得自行決定）

### 6.1 欄位定義（提案，待 Decision Gate）

每個 (canonical instrument, metric) 在資料層必須有一筆政策紀錄，欄位：`primary`、`fallback`（有序清單）、`fallback_trigger`（以明確條件列舉：失敗、空、點數不足、過期、identity 驗證失敗）、`freshness_requirement`（最大可接受 as-of 落後與超過時的行為：警示｜扣留）、`identity_validation`（以何鍵比對：canonical id、ISIN、幣別、級別）、`conflict_behaviour`（同 as-of 兩來源超過容差時：記錄並選定｜扣留顯示「⬜ 資料來源不一致，暫無法判定」）。

### 6.2 現況（引用審計 A §6，並以附錄 A 重驗其中標註者）

| 路徑 | primary → fallback（程式碼中的順序） | fallback trigger | freshness requirement | identity validation | conflict behaviour |
|---|---|---|---|---|---|
| A 鏈基金 NAV series | Allianz 站（部分代碼）→ FundClear（≥20 點）→ Cnyes（≥20）→ TCB（≥10）→ 保險子網域 → www MoneyDJ → SITCA → … → Morningstar → Yahoo(secId.F) → AlphaVantage → 公司站 → 救援（引用審計 A） | 前一來源點數不足 | 無 | 代碼字串原樣送各來源；僅對非原生來源事後做幣別 swap 檢查 | 第一個夠長的來源勝出，不比對 |
| Sheet `nav_history` 合併 | 在 A 鏈之後 | Sheet 可讀 | 無 | 僅 `reconcile_row_currencies` | live 同日勝出，靜默；只記錄 `added` 筆數 |
| `get_latest_nav` | Yahoo（基金代碼當 ticker）→ Yahoo(secId) → cnyes → Morningstar | 第一個非空且 >0 | 無 | 非原生來源有幣別檢查；代碼恰巧等於無關 Yahoo 符號時無名稱／價格健檢（I） | 第一個勝出；完全不含 TDCC／FundClear／MoneyDJ |
| vNext（經 A 鏈，關閉歷史） | 同 A 鏈 | 同 | >10 天扣留 | 加 `full_key` 相等、禁 secId 名稱搜尋來源、持股幣別 gate | 扣留或標示，仍不做兩來源比對 |
| 舊版 FX `get_latest_fx` | Yahoo 5d → FRED DEX* → open.er-api → Frankfurter | 第一個成功 | 無 | 不適用 | 第一個勝出 |
| vNext FX | Sheet `market_indicator`／session 列；Yahoo 路徑閘門關閉 | — | obs_date ≤ NAV 日 | — | 主鍵衝突不採用並顯示錯誤文字 |

**文件與程式差異（僅記錄，不改 `CLAUDE.md`）**：`CLAUDE.md` §2.1 的衝突裁決寫「FundClear（境外）主、TDCC（境內）主、MoneyDJ 補強」。程式碼中 TDCC 只供 meta（`_src_tdcc_meta`，附錄 A 重驗），不在 NAV series waterfall 內；Allianz 站對部分代碼排在最前。實際 precedence 是否需要與文件對齊，是 Decision Gate 項目（source precedence）。

## 7. Source conflict record（提案，審計 D(d)）

同 canonical instrument、同 metric、同 as-of 的兩來源數值超過容差時，不得靜默選一個，必須產出一筆紀錄（扁平欄位）：

`canonical_id`（過渡期＝fund_code 或 ticker）、`metric`、`as_of`（營業日 ISO）、`currency`、`share_class`（可為 None）、`selected_source`、`selected_value`、`rejected_source`、`rejected_value`、`difference`（絕對與相對）、`reason`（precedence｜freshness｜identity_mismatch｜unit_mismatch｜undeterminable）、`freshness`（選用與被拒絕來源各自的 `fetched_at` 與使用的 max_age 規則）、`resolution`（`selected` 或「⬜ 資料來源不一致，暫無法判定」）、`detected_at`。

- 無法判斷（`reason=undeterminable`）時，各頁一律顯示「⬜ 資料來源不一致，暫無法判定」，不顯示任何一個來源的值。
- 放置：欄位名稱、reason enum、容差常數放 L0 `shared/`；紀錄建構與 resolution 政策放 L2 `services/`（純函式）；L1 只供候選值與屬性；L3 只渲染紀錄或「⬜」文字。
- 容差值、是否持久化（例如寫入 Sheet 紀錄）皆為 Decision Gate 項目，本輪不提案數值。

## 8. 自動化一致性測試提案（**提案，未實作**）

原則：同 canonical ID＋同 metric＋同 as-of 的單一基金／持股／配置／AI input 必須一致。檔名建議 `tests/test_cross_view_consistency_*.py`，共用 stub 放 `tests/_xview_fixtures.py`（yf Series 含 `source`／`fetched_at`／`exchange_tz` 屬性、FRED frame、A 鏈結果、FX series、凍結 `now`）。同來源同 as-of 的比較用 `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`；`services/reconcile.py` 的容差（abs 0.005／rel 0.05）只用於跨來源對帳，不得拿來掩蓋 view 漂移。每個案例同時斷言值、as-of、source 標籤相等，且沒有任何 view 悄悄丟棄衝突紀錄。

**特徵化測試（現在可寫，斷言目前行為並記錄分歧，不是 xfail）**

| ID | 內容 |
|---|---|
| C1 | vNext 內部：B 線 `vol_index` 列與 `build_market_view` 的 VIX，用同一 stub 經 monkeypatch 的 `fetch_yf_close_with_error`，斷言 obs_date／值／source 相等 |
| C2 | 同上，對 ^TWII／^GSPC／US10Y／US2Y 兩處重疊者 |
| C3 | 舊版與 vNext 的 VIX：stub 最後一根為「今日 UTC」未收盤 K 棒；斷言 `get_latest_vix` 取最後一根而 market_view 排除（記錄已知分歧，canonical 層完成後改為相等） |
| C4 | 快取鍵：`fetch_yf_close("^VIX")`、`("^VIX","5y")`、`("^VIX", range_="5y")` 以計數 transport stub，斷言產生 N 次不同取數（固定目前分歧；有人靜默合併會紅燈） |
| C5 | 基金 NAV／NAV date／currency：同一 `chain_fetch` stub，經 hld 與 exp 入口對同一代碼，斷言 nav、nav_date、currency、source 相等 |
| C6 | 1M／3M／1Y 報酬：同一 NAV series 經 `fund_service`、`fund_row.process_one_fund` 與所有輸出報酬的 consumer；另加 AST 守衛（仿 `tests/test_ssot_2c_fund_position.py`）禁止第二套報酬實作。**需先做報酬實作盤點，目前數量未知（UNVERIFIED）** |
| C7 | FX：`get_fx_rate_by_date`／`fx_and_main` 對 `build_fx_indicator_table(["USD"])` 同 stub，比對匯率並斷言 obs_date 關係（vNext 前一週日、舊版原始）。⚠️ `FX_OBS_DATE_RULE_VERIFIED=False` 時 vNext 不取數，此案需在測試中顯式處理閘門，未驗證可行性 |
| C8 | AI 輸入：以同 stub 建 `ai_service` 的 key_inds 與 market_view，斷言 VIX／SP500 值與日期；預期目前不同，作為特徵化 |
| C9 | AST 守衛：禁止在 allow-list 外新增直接 `fetch_yf_close("^VIX"…)` |

**阻塞中的測試（`xfail(strict=True)`，reason 寫「需 canonical instrument 層／Decision Gate」；strict 的用意是有人未計畫地修好時 CI 變紅，逼人移除標記）**

| ID | 內容 |
|---|---|
| X1 | 舊版風險雷達 VIX＝🌍 VIX（值＋as-of） |
| X2 | AI input 的 VIX／SP500／FX＝頁面值 |
| X3 | 持股估值 NAV＝單一基金 NAV（同 ISIN＋級別＋幣別；需 canonical id） |
| X4 | alo 配置估值＝持股估值（同 as-of 與 FX cutoff） |
| X5 | 兩來源同 as-of 不一致時必須產出 conflict record（需 resolver） |
| X6 | Sheet 內的 NAV／價格不得被當市場資料 SSOT |

審計 C 另提五個測試點（identity 金鑰一致性對照、Morningstar `results[0]` 拒收錯級別、single/hld/alo 同鍵同日 NAV 相等、四套 units×NAV×FX 同輸入比較、AI 快照指紋隨 NAV 變動而變），可併入 C5、X3、X4 與 BL-0523；**以上全部是提案，本批沒有新增任何測試檔。**

審計 D 另列現有可借鑑的測試：`tests/test_mk_ssot_unification.py`（同 fund dict 跨 caller 同 verdict）、`tests/test_ssot_2c_fund_position.py`（AST 守衛）、`tests/test_cross_site_cutoffs.py`（VIX 22／30 門檻）、`tests/test_reconcile.py`、golden 檔 `tests/test_nav_table_golden_c3a.py`（引用自審計 D，未重驗）。

## 9. Decision Gate 清單（客戶 2026-10-28：下列任一項需變更時，走 Decision Gate）

| Gate | 內容 | 本輪是否變更 |
|---|---|---|
| DG-1 source precedence | 基金 NAV 的 primary／fallback 次序；`get_latest_nav` 是否併入 A 鏈；TDCC 角色；文件與程式次序對齊 | 否 |
| DG-2 canonical identity | canonical 基金識別（代碼、ISIN、share class、幣別、平台後綴）與推導單一實作 | 否 |
| DG-3 valuation methodology | units×NAV×FX 單一實作、成本 vs 市值、護欄 | 否 |
| DG-4 FX cutoff | FX 日期規則（最新價｜前一週日｜≤NAV 日）、`FX_OBS_DATE_RULE_VERIFIED` 開閘條件 | 否 |
| DG-5 formula | 報酬窗口（列數｜日曆）、含息｜價格、年化口徑、benchmark 對應 | 否 |
| DG-6（延伸） | freshness 門檻統一（警示｜扣留）、as-of／收盤規則、source conflict 容差 | 否 |

**第一個排序步驟的選項（以下只是總管 RECOMMENDATION，不是已決定、不是核准）**

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| A | 先定 canonical identity contract（DG-2）：單一 `resolve_instrument` 推導 + 級別／幣別欄位，其餘稍後 | 其他 Gate（NAV precedence、估值、AI）都要靠它當鍵；缺它則任何一致性測試沒有可比較的鍵 | 範圍動到持股 Sheet 欄位與 `fund_keys`、舊版金鑰推導，波及面最大 | 平台後綴語意（不同 NAV 序列）處理錯誤會讓現有持股對錯序列 |
| B | 先做 characterization 測試（BL-0520 的 C1～C9）固定現況，不動行為 | 零行為變更；讓分歧變成會紅燈的紀錄；可平行於 BL-0509 | 不能解決任何不一致，只是量測 | 測試固定了「錯但穩定」的行為，後人可能誤當規格 |
| C | 先收斂單點：`get_latest_nav` 併入 A 鏈（DG-1／DG-3） | 去掉一條獨立 NAV 路徑，影響 T7 市值與費用扣除 | 改變 T7 估值數字；舊版 Yahoo 優先的行為會變 | 數字改變須客戶確認，且 precedence 變更屬 Gate |

**總管推薦（RECOMMENDATION，可被客戶推翻）：先做方案 B**（characterization 測試），再依其結果請客戶就方案 A 簽 DG-2。理由：不改任何 precedence／identity／formula，符合本輪範圍；測試能把本文「機制層級」的 INFERENCE 轉成可重跑的證據，讓客戶簽 Gate 時有據。canonical contract 實作啟動時，依 Model Gate 評估升 Opus（客戶原文：「若進入 canonical data contract／source precedence 實作，再依 Model Gate 評估升 Opus」）。

## 10. 揭露：這份文件是怎麼來的、哪裡沒有驗

- **單一寫作組**依四份獨立唯讀審計報告寫成，**未經第二組獨立驗證**；依 `CLAUDE.md` §-2 規則 6，本文所有全稱句只能當待驗事項。涉及治理規則與 data semantics，**合併前需要至少一組真正獨立的稽核**（`DEC-2026-10-16-05` 風險分級）。
- 四份審計**全程無網路**，只用 `git grep`、`git show` 與讀碼；**沒有任何一條數值落差被實際觀察到**。本文所有「不一致」是機制層級；落差大小、是否已在使用者畫面發生，皆 UNVERIFIED。客戶曾實際遇過同基金在不同頁顯示不同值，但本輪審計不能指出是哪一條機制造成的。
- 各審計自己標為 UNVERIFIED 的事項，忠實帶入：A——「沒有其他路徑做兩來源 NAV 比對」只在指定路徑成立；Sheet 內容、`market_indicator` 是否有 USD 列、`ui/tab5_data_guard.py` 的快取、`fund_keys` 與 `normalize_domestic_code` 是否對每個代碼解出同一檔基金，均未查；B——`portfolio_tracking`／`portfolio_frontier` 未讀、`_BENCH_TTL_SEC` 值未讀、「vNext 沒有 benchmark」為 UNVERIFIED、FX 單位慣例未窮舉；C——tab2／tab3 render 碼未全讀、「沒有其他 canonical id 函式」為 UNVERIFIED、舊版 UI 是否顯示 latest-from 未讀；D——盤中分歧幅度未知、「沒有其他股票／ETF 價格消費者」為 UNVERIFIED、快取鍵相等測試的缺席僅由檔名推得。
- **審計報告之間與對 repo 的差異（不抹平）**：(1) 審計 C 讀本機 `b17029d1` 並**未**與 `10e4670c` 對 diff（較 main 少兩個 commit，標題顯示為 ui_v2 市場圖表與文件同步）；審計 A 稱兩者在其讀的目錄下 diff 為空；審計 B 自述 `git diff --stat` 輸出「看起來是空的」。本文引用 C 的 FACT 時，重驗過的條目已改在 `10e4670c` 上跑（附錄 A），其餘為「引用自審計報告，未重驗」。(2) 審計 C 指出選股池幣別在資料類別註解寫「空＝未知，抓取時退 USD」而程式碼路徑寫「幣別未知則不以 USD 猜測」，審計自己標為「mixed, flag」，本文不裁決。(3) 審計 D 的 C7 提案（比對 `build_fx_indicator_table(["USD"])`）與審計 B 的 X3（FX 閘門關閉時 vNext 不取數）存在張力，本文已在 C7 註明。(4) `CLAUDE.md` §2.1 與程式的 TDCC 角色不符（G-DOC-1）。
- **本文使用的主觀判斷**：把四個審計的 D／X／R 系列合併成 G 系列編號並重新歸類，歸類、Consistent? 欄的燈號文字與 DG 欄的「是／否」皆為寫作組判讀，可被推翻。
- **登記不構成動工授權**（`CLAUDE.md` §-1）。本文不授權任何 source precedence、canonical identity、FX、公式或估值的變更；也不授權新增 view。

## 附錄 A　重驗指令與結果（main `10e4670c`，2026-10-28 實跑）

指令在 repo 根目錄、以 `10e4670c` 為讀取基準。每列結論只對該列的範圍成立。

| # | 宣稱 | 指令（基準 `10e4670c`） | 實際輸出摘要 | 判定 |
|---|---|---|---|---|
| 1 | `FX_OBS_DATE_RULE_VERIFIED` 為 False | `git grep -nE "FX_OBS_DATE_RULE_VERIFIED\s*=" 10e4670c -- . ':!docs' ':!tests'` | `services/v2_tables/market_indicator.py` 的賦值為 `False`，該範圍 1 處 | 重驗成立 |
| 2 | `NAV_HISTORY_PROVENANCE_VERIFIED` 為 False | `git grep -nE "NAV_HISTORY_PROVENANCE_VERIFIED\s*=" 10e4670c -- . ':!docs' ':!tests'` | `services/v2_tables/nav_dividend.py` 的賦值為 `False`，該範圍 1 處 | 重驗成立 |
| 3 | `get_latest_nav` 回傳裸 float、無日期無來源，且有兩個定義處 | `git grep -n "def get_latest_nav" 10e4670c -- repositories services` 再讀 `repositories/fund/fx_and_main.py` 該函式開頭 | 兩處：`repositories/fund/fx_and_main.py` 本體與 `services/fund_service.py` 門面；簽名回傳 `"float \| None"`，docstring「回傳：最新淨值 (float)，全部失敗回 None」 | 重驗成立（回傳型別；「無日期無來源」由簽名推得） |
| 4 | TDCC 只供 meta、不在 NAV series waterfall | `git grep -n "_src_tdcc" 10e4670c -- repositories/fund` | 僅見 `_src_tdcc_meta`（`sources.py` 定義，`fund_orchestration.py` 兩處呼叫）與 `declared_profile.py` 引用；未見 `_src_tdcc_nav` 之類的 NAV 取數函式 | 重驗成立（指令範圍 `repositories/fund`；全 repo 窮舉為 UNVERIFIED） |
| 5 | `share_class`／`canonical_id` 在 `.py` 中不存在 | `git grep -ciE "share_class\|ShareClass" 10e4670c -- '*.py' ':!tests'`；`git grep -ciE "canonical_id\|canonical_instrument" 10e4670c -- '*.py'` | 兩條皆無任何檔案有命中（每檔計數皆 0） | 重驗成立（`*.py` 範圍） |
| 6 | `_morningstar_search_secid` 取 `results[0]` | `git grep -n "results\[0\]" 10e4670c -- repositories/fund/sources.py` | `sources.py` 內 `sec_id = results[0].get("i", "")` 與 `results[0].get("n", "")` | 重驗成立（「不驗 ISIN／名稱」由審計 C 讀碼得，未逐行重驗） |
| 7 | 1Y 含息 SSOT 窗口門檻 350 天 | `git grep -nE "RET_1Y_RESTORED_MIN_WINDOW_DAYS\s*[:=]" 10e4670c -- shared services` | `shared/signal_thresholds.py` 定義為 `350`；`services/fund_total_return.py` 與 `services/fund_service.py` 以 `<` 比較使用 | 重驗成立 |
| 8 | `fund_keys` 檔頭自陳其他輸入未逐一比對 | `git show 10e4670c:services/v2_tables/fund_keys.py` 並檢視檔頭 | 檔頭寫「其他輸入兩邊是否一致，本組沒有逐一比對。」 | 重驗成立 |
| 9 | 新鮮度門檻常數 | `git grep -nE "NAV_NOT_READY_DAYS\s*[:=]\|MJ_FRESH_DAYS_(GREEN\|YELLOW)\s*[:=]" 10e4670c -- shared ui_v2` | `MJ_FRESH_DAYS_GREEN=2`、`MJ_FRESH_DAYS_YELLOW=7`（`shared/signal_thresholds.py`）；`NAV_NOT_READY_DAYS=10`（`ui_v2/thresholds.py`） | 重驗成立 |
| 10 | `ytd` 只有讀取點、無產生者 | `git grep -nE "\"ytd\"\|'ytd'" 10e4670c -- '*.py' ':!tests'` | 僅 `ui/tab2_single_fund.py` 的鍵列表中出現一次 | 重驗成立（字面鍵；以其他方式產生的 `ytd` 變數為 UNVERIFIED） |
| 11 | 舊版持股 session 副本無 `loaded_at` | `git grep -nE "loaded_at" 10e4670c -- ui` | 無輸出 | 重驗成立（`ui` 範圍） |
| 12 | `_merge_nav_history_series` 以 live 同日勝出；`get_latest_fx` 快取 300 秒；持股批次載入先清全部快取 | `git grep -nE "groupby\(level=0\)\.last" 10e4670c -- services/fund_service.py`；`git grep -nE "_FX_CACHE_TTL\s*=" 10e4670c -- repositories`；`git grep -n "clear_all_caches" 10e4670c -- ui/helpers/portfolio/load.py` | 合併式為 `pd.concat([s_hist, s_live]).groupby(level=0).last()`（live 在後，故同日 live 勝出）；`_FX_CACHE_TTL = 300.0`；`load.py` 內有 `clear_all_caches` 呼叫 | 重驗成立 |
| 13 | `compute_1y_total_return_mk_simple` 無 production caller 但仍匯出 | `git grep -n "compute_1y_total_return_mk_simple" 10e4670c -- '*.py' ':!tests'` | 命中為定義、`services/health/__init__.py` 匯出與 `shared/schemas.py` docstring 提及 | 重驗成立（無 import 之外的呼叫點；非窮舉保證） |
| 14 | 未重驗項 | — | 其餘審計報告宣稱（含各表的 TTL 數值、`_BENCH_TTL_SEC`、`^VIX` 呼叫點數量、wb01 域內恆為空、T7 `_FX_FALLBACK` 之外的細節）皆為「引用自審計報告，未重驗」 | 未重驗 |

本附錄沒有跑負控（刻意壞掉的對照組）；各指令的「無輸出」結論只代表該指令在該範圍沒有命中，不證明指令本身有效。
