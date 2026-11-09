# Stage 2 REUSE 8 項「金融語意與資料驗證規格草案」（研究草案，非正式金融契約）

| 項目 | 內容 |
|---|---|
| 性質 | **研究草案**。不是正式金融契約、不是 Schema、不是資料來源或程式施工授權 |
| 日期／基準 | 2026-11-09；程式與文件引用以 main `db10beb6` 為準 |
| 上位依據 | `PROJECT_RULES.md` 13.6（`DEC-2026-11-08-06`）；`DEC-2026-11-09-05`、`DEC-2026-11-09-06`（G1／G2／G3）；客戶 2026-11-09 裁示「採方案 3 改良版」，登記於 `DEC-2026-11-09-07`（要點轉述，非逐字，無逐字存檔） |
| 與既有文件的關係 | 對 `docs/evidence/international_market_source_inventory_2026_11_09.md`（下稱「盤點報告」）與 `docs/evidence/reuse8_offline_evidence_2026_11_09.md`（下稱「離線補證」）是**引用關係**，不維護第二份數據；數字、列數、原始探測值一律以那兩份為準，本文只引用位置與標籤 |
| 本文件**不核准** | Eligibility、正式母集合、涵蓋率分母、日期轉換規則、FX Gate；不新增 `indicator_key`、Schema、provider、status／reason 字彙 |
| 不變項 | `FX_OBS_DATE_RULE_VERIFIED=False` 不變；BL-0545 NOT VERIFIED 不變；J-6／SET-5 零寫入約束不變；盤點報告第 1 節 Eligibility 計數不變、不推翻 |
| 紀律 | missing 不等於 0；proxy 不等於 real（替身或手建 fixture 不等於真實回應）；同一供應者的兩份資料不是獨立交叉驗證 |
| 引用慣例 | 不寫行號，用「檔案＋符號」；計數與數字釘在本文給定的基準或證據檔 |

## 1. 先講結論

1. 本文把 REUSE 8 項各自「已知的資料身分、日期語意、單位方向、品質觀察、尚未驗證的定義」整理成規格草案表（第 B 節）；凡需要客戶定義的，一律寫「待客戶定義」，不替客戶定義。
2. 現有離線證據對本文第 C 節五類現象**都不足以判定資料錯誤**；本文只列候選解釋（INFERENCE）與「要什麼證據才能分辨」。
3. 第 D 節是下一批 Yahoo `^GSPC`、`^VIX`、`^TWII` 受控唯讀探測的**最小規格**；它只是規格，不執行、不授權，也不含 D1 與 FRED。
4. 讀程式時發現一個會影響規格設計的事實（FACT）：既有探測腳本 `scripts/probe_fx_obs_date.py` **強制納入 `USDTWD=X`**（`REQUIRED_TICKERS`），且小時 K 只對匯率代號取。因此「直接用既有 workflow 只探三個 Yahoo 指數」不成立，詳見第 D.7 節。
5. 本文件完成後停在下一個 Decision Gate：客戶是否授權 Yahoo 三項探測，以及探測的執行環境與次數上限。FRED 與 D1 不在這一批。

## A. 方法與證據層次

### A.1 標籤

- **FACT**：本次讀檔、讀碼或重讀既有證據檔所得；附出處。
- **INFERENCE**：推論，可被推翻；不得當成已驗事實。
- **NOT VERIFIED**：離線無法驗，也沒有既有證據。
- **待客戶定義**：屬金融語意或產品定義，專案 AI 不替客戶定義。

### A.2 五層證據（不得由前一層推得下一層）

| 層 | 意思 | 本文對 REUSE 8 項的使用方式 |
|---|---|---|
| L-1 程式存在 | 有 fetcher 或轉換碼 | 只用來指出「讀哪裡」，不當作已抓到 |
| L-2 測試通過 | 替身或手建 fixture 下分支符合預期 | 只證明分支行為，不證明真實回應的日期、單位、時區 |
| L-3 真實抓取證據 | 有一份真實連線取回的原始或快照資料 | 重讀既有快照與探測報告；本次**沒有**新連線 |
| L-4 日期來源驗證 | 觀測日／公布日語意經真實資料驗過且客戶核准 | 本文不宣稱任何一項達到 |
| L-5 正式准入 | 客戶核准進入正式清單或分母 | 本文不核准、不改變既有登記 |

### A.3 本次實際做了什麼

- 讀：`docs/v2/83`、盤點報告、離線補證、`docs/evidence/fx_obs_date_winter_probe_2026_11_08.md`、`docs/evidence/probe_fx_obs_date/` 三份既有探測報告、`repositories/macro/yf.py`、`repositories/macro/fred.py`、`infra/proxy.py::fetch_url`、`infra/source_backoff.py`、`shared/backoff_policy.py`、`scripts/probe_fx_obs_date.py`、`.github/workflows/fx_obs_date_probe.yml`、`scripts/update_macro_history.py` 與其 workflow。
- 重讀（只讀、離線）：三份既有探測報告 gz 內 `^VIX` 的 2026-06-03 前後日 K（第 C.2 節新增一項離線事實）。
- 沒做：任何外部連線、任何取數函式執行、探測重跑、安裝套件、改任何 `.py`／workflow／`CLAUDE.md`／frozen 文件。

## B. REUSE 8 項逐項語意與驗證規格草案

共通說明（避免每列重複）：

- **Yahoo 路徑（A1、A3、A11、D1）**：共用 L1 為 `repositories/macro/yf.py::fetch_yf_close`；傳輸為 `infra/proxy.py::fetch_url`（`timeout=15`、`backoff_on_429=False`）；快取為 `@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=64)`；回應 `meta.exchangeTimezoneName` 為非空字串時放入 `Series.attrs["exchange_tz"]`。**回傳 Series 的索引是以 UTC 秒轉出的無時區時間戳**（`pd.to_datetime(秒, unit="s")`），Old UI 多數呼叫端直接取最後一筆，不取日期欄（FACT，讀碼）。
- **FRED 路徑（C1、C2、C6、C7）**：共用 L1 為 `repositories/macro/fred.py::fetch_fred(series_id, api_key, n)`（請求最新 n 筆、`sort_order=desc`）；`"."` 在 L1 丟棄；`date` 欄為觀測日；`realtime_start` 欄來自 FRED 回應（見 C.4 與 B.5 的待驗說明）。ui_v2／ui_v3 的 B 線走 `repositories/macro/fred_vintage.py::fetch_fred_vintages_with_error`（版次路徑，`"."` 轉 NaN 保留列，離線補證第 6.2 節）。
- **cron 快取（`data_cache/*.parquet`）**：由 `scripts/update_macro_history.py` 自帶一套取數碼寫入（Yahoo 用 `_yf_fetch_close`，以 `period1`／`period2` 取日 K；FRED 用 `_fred_get_single`），**不是**共用 L1。排程見 `.github/workflows/update_macro_history.yml`（每週日 UTC 00:00）。cron 快取只能當 L-3 的旁證，不能當作共用 L1 在 Cloud 可用的證據。
- **「驗證方式分類」欄**只是研究分類：`離線已可`＝再讀既有檔即可；`需 live`＝需要新的上游真實連線；`受 Gate 阻擋`＝被正式 Gate 擋住。**不是 UI 狀態字彙**，不得用於 UI 顯示或寫入任何 Sheet。
- **各表的 Eligibility 欄固定為**：本文件不核准、不改變既有登記（見盤點報告第 1 節）。

### B.1 A1 S&P 500（`^GSPC`）

| 欄位 | 內容 |
|---|---|
| 來源身分 | Yahoo Finance chart 端點，代號 `^GSPC`；指數本身（非 ETF）；Old UI 另有 ETF 代理 `SPY`／`RSP` 屬不同項（盤點報告 A12），本列不涵蓋。New UI2 來源標示常數為 `SP500_SOURCE_LABEL`（`services/v2_tables/market_view.py`）。非 proxy（但 Yahoo 是聚合商，不是 S&P 官方；官方來源身分待客戶定義） |
| 日期語意 | **觀測日**：未驗。Old 路徑取 `iloc[-1]`，無日期欄、無收盤過濾（`services/risk_radar.py::_signal_spx_trend_break`，取 `range_="1y"`，不足 200 日回 `_empty`）；New 路徑以交易所當地日為觀測日並套「未收盤界線」（`services/v2_tables/market_indicator.py::rows_from_daily_close`，`market_view.sp500_domain_from_l1` 取 5y）。**公布日**：指數收盤型資料沒有獨立公布日欄位，待客戶定義是否需要。**抓取時間**：`attrs["fetched_at"]`（UTC ISO），不得充當觀測日 |
| 時區 | **無真實證據**：`^GSPC` 不在任何既有探測代號清單（三份舊探測報告與 2026-11-08 冬令探測皆不含）。`tests/test_v2_tables_market_view.py` 的 `_gspc_series` 為手建（固定 UTC 13:30），不等於真實回應 |
| 單位與方向 | 指數點數；無幣別換算；僅記錄 |
| 資料品質觀察 | cron 快取 3879 列、日期單調、無重複、無 NaN、無週末列（離線補證第 3.2 節，FACT，自製解碼器）。與 VIX 日期集合差異見 C.1 |
| 尚未驗證的定義 | 待客戶定義：(a) 日收盤「完整」的判準（是否含未收盤盤中值？未收盤界線是否沿用現行規則）；(b) 休市日是否要有列；(c) 是否需要記錄指數價格報酬 vs 總報酬口徑。待證據：真實時區字串與時間戳樣態（夏令、冬令各一次） |
| 驗證方式分類 | 日期層：離線已可（快取已重讀）；時間戳與時區層：需 live |
| Eligibility | 本文件不核准、不改變既有登記 |

### B.2 A3 VIX（`^VIX`）

| 欄位 | 內容 |
|---|---|
| 來源身分 | Yahoo `^VIX`；FRED 沒有已實作的 VIX 備援（`DEC-2026-10-19-02` 第 4 項、`CLAUDE.md` §2.1 的 VIX 條）。非 proxy，但 Yahoo 非 CBOE 官方；官方來源身分待客戶定義 |
| 日期語意 | Old 路徑多處各自取不同範圍：`services/risk_radar.py`（`range_="6mo"`）、`services/macro/us_indicators.py` 內 VIX 區塊（5y）、`services/v2_tables/market_view.py::vix_domain_from_l1`（5y）、`INDICATOR_SPECS["vol_index"]`（預設 2y）。Old 多取最後一筆。**觀測日**：New 路徑以 `America/Chicago` 當地日；已有真實探測支持時間戳樣態（見時區欄）。**公布日**：待客戶定義。`fetched_at` 不得充當觀測日 |
| 時區 | 舊探測報告（run `38524215912`，2026-10-14）：`exchangeTimezoneName` 為 `America/Chicago`；日 K 時間戳 UTC 07:00（夏令）／08:00（冬令），等於芝加哥 02:00（FACT，離線補證第 3.3 節；本次重讀同一份報告，`2026-06-03` 的日 K 時間戳為 UTC 07:00） |
| 單位與方向 | 指數點數（波動率指數）；無幣別 |
| 資料品質觀察 | cron 快取 3881 列、無重複、無 NaN；比 SPX 多 2 列（2026-05-25、2026-09-07，均為美國假日，Yahoo 回有非空值，且同值出現在探測原始日 K）；2026-06-03 快取值與探測值不同；探測報告有 19 根空 close（落在美國休市日）。原始 close 值帶單精度浮點尾數（例如 `15.319999694824219`），為回應原樣（FACT，本次重讀） |
| 尚未驗證的定義 | 待客戶定義：VIX 在美國股市休市日是否要有觀測列（來源有值但股票市場休市）；「收盤值」是否以 CBOE 官方結算值為準。待證據：假日列成因、快取與探測差異成因（見 C.1、C.2）、小時 K 值對時刻（2026-11-08 冬令探測標為 NOT RUN） |
| 驗證方式分類 | 時區字串與時間戳樣態：離線已可（既有報告）；假日列與值差異成因、小時 K：需 live |
| Eligibility | 本文件不核准、不改變既有登記 |

### B.3 A11 TAIEX（`^TWII`）

| 欄位 | 內容 |
|---|---|
| 來源身分 | Yahoo `^TWII`；客戶 2026-10-27 裁示（`DEC-2026-10-27-43`）：唯一來源 Yahoo `^TWII`、來源標示固定為 `TAIEX_SOURCE_LABEL`（`services/v2_tables/market_view.py`），成交量與市場統計維持 Data Gap。本表不重述其語意，也不替它補 Eligibility（客戶原話本次未逐字對照存檔，只讀到 `docs/DECISIONS.md` 標題與其自述，離線補證第 6.2 節） |
| 日期語意 | Old UI 沒有獨立 TAIEX 卡片；字面搜尋所見的 Old 使用處為 `services/crisis_backtest.py`（`TWII` 對應 `^TWII`）。New 路徑 `market_view.taiex_domain_from_l1` 取 5y，經 `rows_from_daily_close`。**觀測日**：未驗；INFERENCE：台北日期不早於 UTC 日期，未收盤界線取較晚者時，當日收盤要等台北換日（約 UTC 16:00 之後）才被放行（離線補證 A11 列，未用真實回應驗） |
| 時區 | **無真實證據**。`_tw_series` fixture 為手建（假設台北 09:00 等於 UTC 01:00），不等於真實回應 |
| 單位與方向 | 指數點數 |
| 資料品質觀察 | cron 快取 3762 列、無 NaN／0／重複；**含 1 列週日** `2026-09-20`，close 與前一週五相同（C.3）；New 路徑會以週末規則丟掉週日根，Old 路徑無此規則（離線補證 A11 列） |
| 尚未驗證的定義 | 待客戶定義：週六補班或週日異常列是否保留；`^TWII` 是否等同 TWSE 官方加權指數收盤。待證據：真實時間戳與時區字串、週日列成因 |
| 驗證方式分類 | 週日列與快取內容：離線已可（已重讀）；時間戳與時區：需 live |
| Eligibility | 本文件不核准、不改變既有登記 |

### B.4 D1 USD/TWD（`USDTWD=X`）

| 欄位 | 內容 |
|---|---|
| 來源身分 | Yahoo `USDTWD=X`；Old 路徑另有備援 open.er-api.com（僅 `repositories/fund/fx_and_main.py::get_latest_fx`，盤點報告 D1 列）。Yahoo 的 `USDTWD=X` 是外匯報價聚合，不是央行或官方收盤匯率；官方來源身分待客戶定義 |
| 日期語意 | Old 路徑（`repositories/hot_money_repository.py::fetch_usdtwd_series`、`get_latest_fx`）**不受 `FX_OBS_DATE_RULE_VERIFIED` 管**，直接用最新值，無觀測日規則（FACT，讀碼）。New 路徑 `services/v2_tables/market_indicator.py` 的閘門關閉、不取數不寫列。2026-10-14 客戶裁示的匯率「前一交易日收盤」語意，其規則核准與閘門核准是兩件事，本文不重述 |
| 時區 | 既有探測：`exchangeTimezoneName` 為 `Europe/London`；日 K 時間戳 UTC 23:00 與 00:00 兩種（舊報告）；2026-11-08 冬令探測報告原檔不在 main，只有分析文件，其數字本次無法重算（離線補證第 3.3 節）。不同 run 的新舊取日差異（舊報告 300／518 與冬令文件 298／518）不得互相比對 |
| 單位與方向 | 新臺幣／美元：**TWD per 1 USD**（`INDICATOR_SPECS["fx_twd_per_usd"]` 的命名，盤點報告 D1 列）。僅記錄；本文不轉換、不倒數、不裁決方向。USD/JPY、EUR/USD 等其他匯率的 base／quote 屬 `DEC-2026-11-09-06` G3 範圍，不在本列 |
| 資料品質觀察 | 無真實離線快取（`data_cache` 無 USD/TWD）。冬令文件自述日 K 與 UTC 當日 00:00 起點小時價最一致（0.0034%），樣本 13／5／5 日，自述為一致性而非收盤時間規則；週一值不等於上週五收盤、假日映射未解（冬令文件，本次未重算） |
| 尚未驗證的定義 | **不是缺驗證，是閘門關**：開閘前條件 (a)～(e) 無一已完成（冬令文件第 7 節）。待客戶定義：匯率採哪一時刻收盤、容差、假日規則。本文不推進 FX 開閘，也不納入下一批探測 |
| 驗證方式分類 | 受 Gate 阻擋 |
| Eligibility | 本文件不核准、不改變既有登記 |

### B.5 C1 DGS10、C2 DGS2

| 欄位 | 內容 |
|---|---|
| 來源身分 | FRED series `DGS10`、`DGS2`（常數見 `shared/fred_series.py::FRED_DGS10`、`FRED_DGS2`）；FRED 為聚合發布商，原始資料屬美國財政部 H.15 系列，**後半句為已知背景，本文未以真實連線驗證** |
| 日期語意 | `fetch_fred` 的 `date` 為**觀測日**；`realtime_start` 欄來自 FRED 回應，`fetch_fred` 的 docstring 自述其「約等於首次發布日」，但 `fetch_fred` 不帶 real-time 參數，**INFERENCE**：該欄實為查詢當天（離線補證第 6.3 節），所以以它計算的「發布延遲」可能實為「查詢日減觀測日」。**NOT VERIFIED**，需 live 證據。Old 取數量：`services/macro/us_indicators.py` n=2600、`services/risk_radar.py` n=120；New 的 `market_view.fred_yield_domain_from_l1` 取 n=1500（盤點報告 C1 列：經 `fetch_fred_with_error` 的原文旁路）。`mv` 明示 obs_date 是 FRED 觀測日、不是公布日 |
| 時區 | FRED 日資料沒有時區欄位，觀測日為日曆日；公布時刻待客戶定義 |
| 單位與方向 | FRED 原始百分比數值（例如 4.84 表示 4.84%）；**單位在不同層的標示不一致**：同一類數字在不同層標 `%`、`pp`、bp（僅記錄；離線補證 C7 列對 HY 另有一條）。`services/risk_radar.py` 的殖利率衝擊判定另以 `(cur-prev)*100` 轉 bp（盤點報告 C7 列）。本文不裁決單位語意 |
| 資料品質觀察 | cron 快取各 3855 列、2011-06-07 至 2026-11-05、無缺漏列、假日 `.` 已丟（離線補證第 3.2 節）。`META.fred_indicators` 的 `last_error: null` 不保證每個 series 都取到（見 C.4） |
| 尚未驗證的定義 | 待客戶定義：觀測日與公布日的採用順序；殖利率變動的單位口徑（%、pp、bp）。待證據：共用 L1 在 Cloud 的真實連線結果、n=1500 實際回幾列、FRED 版次起點 |
| 驗證方式分類 | cron 快取內容：離線已可；共用 L1 真實行為、版次與公布日：需 live（需 FRED 金鑰，屬不在本批範圍的另一道 Gate） |
| Eligibility | 本文件不核准、不改變既有登記 |

### B.6 C6 FEDFUNDS

| 欄位 | 內容 |
|---|---|
| 來源身分 | FRED `FEDFUNDS`（有效聯邦基金利率，月頻）。「月均有效利率」的出處為 repo 內註解自述（`services/macro/tw_local.py`），外部事實未驗（離線補證 C6 列） |
| 日期語意 | 月頻 `date` 是否為月初、版次起點皆 NOT VERIFIED。Old 路徑：`services/macro/us_indicators.py` 取 n=144，`FAI["FED_RATE"]`；ui_v2 路徑 `services/v2_tables/market_indicator.py::INDICATOR_SPECS["policy_rate_pct"]` 走版次路徑。`.` 在版次路徑轉 NaN 保留列，L2 才略過（離線補證第 6.2 節） |
| 時區 | 月頻無時區 |
| 單位與方向 | 百分比數值；Old 路徑注入無風險利率時由 `app.py` 除以 100 並呼叫 `services/fund_service.py::set_risk_free_rate`，缺值時不呼叫、沿用預設 4%（離線補證 C6 列，FACT 讀碼，單組） |
| 資料品質觀察 | **不在** cron 抓取清單 `FRED_SERIES_IDS`，也不在 parquet；沒有任何間接證據可引用（離線補證 C6 列）。缺值以非零預設（4%）替代是否符合 `CLAUDE.md` §1 與 13.6 的風險判斷，離線補證只陳述事實不裁決，**本文同樣不裁決** |
| 尚未驗證的定義 | 待客戶定義：缺值時無風險利率採何種處置（不在本文範圍，只記錄）。待證據：真實觀測日慣例與版次起點 |
| 驗證方式分類 | 需 live |
| Eligibility | 本文件不核准、不改變既有登記 |

### B.7 C7 BAMLH0A0HYM2（HY OAS）

| 欄位 | 內容 |
|---|---|
| 來源身分 | FRED `BAMLH0A0HYM2`（ICE BofA 美國高收益債選擇權調整利差）；常數 `FRED_HY_SPREAD`。授權與再發布條件未驗 |
| 日期語意 | 日頻觀測日。Old 取數量：`services/macro/us_indicators.py` n=2500、`services/risk_radar.py` n=120、`services/us_liquidity_engine.py` n=60、`services/macro/turning_points.py` n=400（離線補證第 6.1 節 7）；ui_v2 的 `credit_spread_pct` 走版次路徑。Old 的 HY 區塊只檢查 `len(df) >= 2`，樣本變短不會報錯（離線補證 C7 列，live 行為 NOT VERIFIED） |
| 時區 | 日曆日，無時區 |
| 單位與方向 | FRED 單位 Percent；同一組數字在不同層標 `%`、`pp`、bp（僅記錄） |
| 資料品質觀察 | cron 快取**只有 898 列、起自 2023-06-05**，同批 DGS 皆起自 2011-06-07；12 列落在週末（皆為月底日）；值域 2.59 至 4.61（離線補證第 3.2 節）。若 live 取數也受相同限制，「n=2500 約等於 10 年」的假設不成立（INFERENCE，成因未驗） |
| 尚未驗證的定義 | 待客戶定義：歷史長度不足時的呈現與下游判定口徑（本文不涉）。待證據：真實可取歷史長度、版次路徑的回溯下界落點、月底週末列的意義（C.5） |
| 驗證方式分類 | 快取起點與列數：離線已可；成因與 live 長度：需 live（FRED，不在本批） |
| Eligibility | 本文件不核准、不改變既有登記 |

## C. 待驗項目清單（不得直接判為資料錯誤）

每項格式：現象｜已知證據出處｜候選解釋（INFERENCE，不下定論）｜需要什麼證據才能分辨。

### C.1 VIX 快取比 SPX 多 2 個美國假日列

- **現象**：`2026-05-25`（陣亡將士紀念日）、`2026-09-07`（勞動節）；VIX 快取有值（16.59、15.30），SPX 快取無列。
- **已知證據**：離線補證第 3.2 節 1、第 7 節；探測報告 run `38524215912` 的原始日 K 同樣有這兩根且值相同，且不在該報告 `^VIX` 的 19 根空 close 之列。
- **候選解釋**：(a) Yahoo 對 `^VIX` 在股票休市日補列（例如沿用前值或另一計算日曆）；(b) CBOE 的 VIX 計算日曆與 S&P 500 股票交易日曆本來不同；(c) 日期映射誤差（日 K 時間戳為 UTC 07:00，以 UTC 取日與以芝加哥取日在這兩天可能不同，但離線補證記「時間戳樣態為芝加哥 02:00」，所以日期映射誤差的可能性較低，未排除）。
- **要分辨需要**：對這兩天的日 K 取得時間戳、`close`、成交量（若有）與同日其他指數的對照；對 `^GSPC` 同窗取數確認其無列；必要時對照 CBOE 公開日曆（屬新來源，須另行授權）。
- **不得判為資料錯誤**：目前沒有任何證據表明 VIX 在這兩天不該有值。

### C.2 2026-06-03 VIX 快取 16.26 與探測 16.06

- **現象**：快取 `data_cache/vix_history.parquet` 為 16.26；探測原始 close 為 16.06（UTC 07:00 根，離線補證第 7 節）。
- **新增離線事實（本次重讀三份既有探測報告，只讀）**：探測報告 run `38524215912` 的 `^VIX` 於 `2026-06-03` 的日 K 為 open 15.97、high 16.63、low 15.94、close 16.06（單精度尾數已四捨五入顯示）；**16.26 落在該日 low 與 high 之間**；該報告 2 年窗內**沒有任何一根日 K 的 close 等於 16.26**（以 ±0.005 比對）。另兩份較早報告（run `38450455092`、`38510633247`）不含 `^VIX` 的原始日 K 陣列，故不可比。
- **候選解釋**：(a) Yahoo 事後修改該日收盤值，而 cron 只抓「最後日期加 1 天」之後，已入庫日期不會被重抓（離線補證的 INFERENCE）；(b) cron 取到的是盤中或未結算值：但 cron 為每週日 UTC 00:00（FACT，workflow cron 設定），週日取數時當週日 K 皆已收盤，此候選較弱，且 `scripts/update_macro_history.py::_yf_fetch_close` 不過濾未收盤根，未排除；(c) 兩套取數碼參數不同（cron 用 `period1`／`period2` 加 `events=history`，探測用 `range=2y`），Yahoo 對兩種參數回的同日值是否一致未驗；(d) cron 以執行環境本地時區做 `fromtimestamp(...).date()`，若本地時區非 UTC 可能日期位移，把相鄰日的值寫到 06-03（執行環境時區 NOT VERIFIED；本離線事實顯示 16.26 不等於任何相鄰日 close，對 (d) 為反證線索，但不是排除）。
- **要分辨需要**：同一代號、同一日，以兩種參數形式（`range`、`period1`／`period2`）各取一次並比對原始回應；或取得該 parquet 在 git 歷史各版本中 `2026-06-03` 的值（本工作樹為 shallow clone，僅見 3 個 commit，歷史完整性 NOT VERIFIED，離線可否重建待確認）。
- **不得判為資料錯誤**：只證明 cron 快取與某一次探測不同，兩者同為 Yahoo，不是獨立來源。

### C.3 TWII 週日列 `2026-09-20`

- **現象**：`data_cache/twii_history.parquet` 有一列 `2026-09-20`（週日），close 47180.75，與前一週五 `2026-09-18` 相同。
- **已知證據**：離線補證第 3.2 節 3、第 7 節；`^TWII` 不在任何既有探測清單，**沒有原始日 K 可對照**。
- **候選解釋**：(a) 週日補班日（但本文未查證 2026 年該日是否為補班日）；(b) Yahoo 對未開市日重複前值補列；(c) 日期映射：cron 以本地時區做 `fromtimestamp(...).date()`，若時間戳為週六晚間 UTC 但本地時區已進入週日，可能位移（需時區與原始時間戳才能分辨）。
- **要分辨需要**：對 `^TWII` 取原始日 K（時間戳、時區字串、該日前後三根）；並由客戶或可信官方日曆確認 2026-09-20 是否為補班交易日（屬新來源，須另行授權）。
- **不得判為資料錯誤**：只觀察到值與前一週五完全相同，不足以證明是重複列或補班。

### C.4 FRED 快取缺漏

- **現象**：`FRED_SERIES_IDS` 有 11 項，parquet 只見 9 個 series（`PPIACO`、`PCOPPUSDM` 缺）；`DTWEXBGS` 僅 21 列（2026-06-05 起）；`data_cache/metadata.json` 的 `last_error` 為 null。
- **已知證據**：離線補證第 6.1 節 12、第 7 節（單組重讀 parquet 與腳本）。
- **候選解釋**：腳本增量以整表最大日加 1 為起點（`update_one` 的 `start = last + 1 天`），後加入或曾失敗的 series 不回補；`last_error` 只記錄整個 dataset 層級的例外，不記錄單一 series 的空回（INFERENCE，成因未逐一驗）。
- **要分辨需要**：腳本 `fetch_fred_indicators` 逐 series 的取數紀錄（Actions log，本次未讀）；或對這三個 series 做一次受控唯讀取數（FRED 屬另一道 Gate，不在本批）。
- **不得判為資料錯誤**：只觀察到 series 數與列數落差，原因可能是增量設計，不等於來源缺資料。

### C.5 HY OAS 898 列、起自 2023-06-05、12 列月底週末

- **現象**：同批 DGS 皆起自 2011-06-07；HY 只有 898 列；12 列落在週末，皆為月底日（例如 2023-09-30、2026-05-31）。
- **已知證據**：離線補證第 3.2 節、第 7 節。
- **候選解釋**：(a) 供應端對 ICE BofA 系列只提供近約 3 年的完整歷史（授權限制，INFERENCE，未經 FRED 文件或真實連線驗證）；(b) 月底週末列來自 FRED 對月底的特殊日曆或月末標記（未驗）；(c) cron 的取數窗口或 `limit` 造成截斷（未排除）。
- **要分辨需要**：FRED 對該 series 的 series 資訊（觀測起點、頻率、版次區間）與一次完整取數的列數；對 12 列月底週末的原始回應。
- **不得判為資料錯誤**：與下游影響相關的判斷（例如 Old 的 n=2500 假設）列為 NOT VERIFIED，不代表 Old 路徑已出錯。

### C.6 其他已由離線補證列出的線索（只引用，不新增事實）

| 線索 | 出處（離線補證） | 本文處置 |
|---|---|---|
| `fetch_fred` 以不同 n 各自成快取鍵，`maxsize=32` 下 TTL 內有被擠出的可能 | 第 6.1 節 10 | 與本批 Yahoo 探測無關；列入後續 FRED 探測前的待辦背景 |
| `publish_lag_days` 以 `realtime_start` 減觀測日計算，疑為「查詢日減觀測日」 | 第 6.3 節 | 見 B.5；NOT VERIFIED |
| 「同日規則寫出 504 列」屬 11-08 run，原始檔不在 main，無法重算 | 第 6.3 節 | 本批探測若執行，不得用其結果回頭「驗證」該數字 |
| D1 週一值不等於上週五收盤、假日映射未解 | 冬令探測文件 | 受 FX Gate 阻擋，不納入本批 |
| 探測時間點只有單一取數時刻，「當日根何時出現」無法由單次取數回答 | 離線補證 A1、A11 的 INFERENCE | 見 D.1 的選配設計 T2 |

## D. 下一批 Yahoo `^GSPC`、`^VIX`、`^TWII` 受控唯讀探測：最小規格

> **僅規格，不執行、不授權。** 探測須客戶另行裁示。FRED 與 D1 不在這一批。本節所有建議值均標為「專案 AI 建議，未經客戶裁示」。

### D.1 目標問題與範圍

| 對應 | 目標問題 | 資料可回答的程度 |
|---|---|---|
| A1、A11（盤點報告缺口 c） | `^GSPC`、`^TWII` 回應自報的 `exchangeTimezoneName`、日 K 時間戳樣態（夏令／冬令） | 單次取數的 2y 窗含夏令與冬令兩段歷史根，可看樣態；不能代表未來規則 |
| A3 與 C.1 | 假日列（2026-05-25、2026-09-07）在 `^VIX`、`^GSPC` 各自的有無與值 | 可回答 |
| A3 與 C.2 | 2026-06-03 同日以不同參數形式的值是否一致 | 只有選配 T3 可回答 |
| A11 與 C.3 | `^TWII` 2026-09-20 週日根的時間戳、值與前後根關係 | 可回答 |
| 離線補證 A1／A11 的 INFERENCE | 「當日根何時出現」（未收盤界線）、收盤是否完整 | 單次取數只看一個時刻；需選配 T2（兩個取數時刻）才有對照 |

**範圍**：僅 `^GSPC`、`^VIX`、`^TWII` 三個代號；不含 D1、不含 FRED、不含其他 Yahoo 代號；不新增資料來源。

### D.2 查詢組合與次數上限（逐代號逐參數列出）

基準組合 S（必要）對齊既有探測的 `range=2y`、`interval=1d`（`scripts/probe_fx_obs_date.py` 的 `RANGE`、`INTERVAL`），使 `^VIX` 可與 run `38524215912` 對照；其餘選配組合各自獨立勾選。

| 組合 | 代號 | interval／range | 請求數 | 用途 | 必要性 |
|---|---|---|---|---|---|
| S | `^GSPC`、`^VIX`、`^TWII` 各 1 | `1d`／`2y` | 3 | 時區字串、時間戳樣態、假日列、週日列、最後一根與 `regularMarketTime` | 必要 |
| L | 同上各 1 | `1d`／`5y` | 3 | 對齊 New UI2 `market_view` 取數量（5y），看長窗是否改變同一日的值或列 | 選配 |
| P | `^VIX` 1 | 以 `period1`／`period2` 指定包含 2026-06-03 的窗，`interval=1d` | 1 | 對照 cron 形式取數與 `range` 形式取數的同日值（C.2） | 選配 |
| H | 同上各 1 | `60m`／`1mo` | 3 | `^VIX` 值對時刻（冬令探測標 NOT RUN）；`^GSPC`、`^TWII` 看小時根的時區 | 選配；`1mo` 窗**不含** 2026-06-03，不能回答 C.2 |
| T2 | 重複 S | 同 S，但兩個取數時刻 | S 的請求數乘 2 | 對照「美股收盤後、UTC 換日前」與「換日後」、「台北換日前後」的最後一根 | 選配，須客戶決定取數時刻 |

**上限**（每次授權的總上限，客戶可只勾選部分組合）：

- 僅 S：**3 個請求**。
- S＋L＋P＋H：**10 個請求**。
- 再加 T2（僅對 S 重複一次）：**13 個請求**。
- 嚴禁超過所授權組合的上限；任何組合都**不得因失敗而自動補打**。

**重試規定（FACT 與規格要求）**：

- FACT：`infra/proxy.py::fetch_url` 的 `retries` 預設為 3，探測的 `fetch_chart` 呼叫未覆寫；加上 ProxyError 立即降級直連的行為，**以既有 `fetch_chart` 照搬時，單一邏輯請求在實際 HTTP 層可能多於 1 次**（確切上限取決於失敗類型，本文未逐分支窮舉）。
- 規格要求：新探測須以 `retries=1`（或等效的單次請求）呼叫，並在報告記錄 **HTTP 層實際嘗試次數**（`http_requests_attempted`），使上限可核對；**0 重試**（失敗即記錄、不重打）。429 時 `backoff_on_429=False` 為立即回 None（FACT，見 `fetch_url`），維持不睡眠重試。

### D.3 節流與冷卻

- **串行**，不並行。
- **請求間最小間隔：專案 AI 建議 ≥ 5 秒**（未經客戶裁示）。理由：本 repo 內沒有 Yahoo 限流的實證值可引用（INFERENCE：既有探測 6 個代號同次執行、無間隔，歷次均成功，但這不證明安全邊界）；5 秒是保守值，使 13 個請求的總時長小於 2 分鐘。
- **遵循現行來源冷卻設定（FACT，`shared/backoff_policy.py`）**：unreachable 60 秒、server_error 300 秒、blocked 900 秒、rate_limited 1800 秒；單一主機（`query1.finance.yahoo.com`）共用。這些冷卻狀態在 `infra/source_backoff.py` 內以行程內字典保存（INFERENCE：新的 Actions runner 行程不繼承），因此**跨執行不持久**：失敗後不得再次觸發探測的最短等待，**專案 AI 建議取該失敗類別冷卻秒數，429 或 blocked 類取 30 分鐘**，且重跑須客戶重新授權。
- 同一主機在冷卻期內由 `fetch_url` 直接回 None 且不發封包；報告須分得出「沒發請求」與「發了但失敗」（既有 `status` 字彙 `skipped_backoff_no_request`／`request_failed` 已有此區分，屬 FACT）。

### D.4 原始證據保留

- **存放位置慣例**：沿用 `docs/evidence/probe_fx_obs_date/` 的保存慣例，建議新目錄 `docs/evidence/probe_yahoo_index_a1_a3_a11/`（建議名，未經核准）。
- **每個請求保存一份原始 HTTP 回應本文**（JSON，進 JSON 解析前的位元組），以 `gzip -9 -n` 壓縮；**不人工改寫、不重排、不四捨五入**。
- 檔名：`<UTC 取得時間 YYYYMMDDTHHMMSSZ>_run<GitHub run id>_<代號去除特殊字元>_<interval>_<range>.json.gz`（建議；沿用既有 `<UTC>_run<id>_report.json.gz` 的形式）。
- **每個請求另記 metadata 欄位**：代號、完整請求 URL（含查詢字串，Yahoo 無金鑰，不含任何 token）、請求開始與結束 UTC 時間、HTTP 狀態碼、回應本文 `sha256`、gzip 後 `sha256`、位元組數、`meta.exchangeTimezoneName`（原值，另從本文複製，僅為索引，不取代原始本文）、`meta.regularMarketTime`、`http_requests_attempted`、`trigger_sha`、`executed_sha`、`github_run_id`。
- 一份 `README.md` 比照既有目錄：來源、執行 SHA、雜湊表、驗證指令（用 gzip 解壓後 `sha256sum` 與紀錄比對）。
- **不保存**：cookie、授權標頭、代理帳密、`PROXY_URL` 字面值（既有 `mask_text` 慣例，離線可見於 `scripts/probe_fx_obs_date.py`）。

### D.5 停止條件（任一成立即停止，不重試放大）

1. 任一請求回 4xx（含 403、404、407、429）、5xx、逾時、連線失敗。
2. HTTP 200 但回應空本文、非 JSON、`chart.error` 非空、`chart.result` 為空或缺 `timestamp`／`indicators`。
3. 時間戳序列非單調遞增（遇到即停，但已取得的原始回應仍保存）。
4. 回應 schema 異常（欄位缺漏、`timestamp` 與 `close` 陣列長度不等）。
5. 已達授權的請求數上限。
6. 任一代號出現「來源冷卻中」跳過即停止其後所有請求。
7. 偵測到報告中出現疑似敏感字串（比照既有敏感字串樣式掃描）時，不推送報告，停下回報。

停止後只回報狀態與原始證據，不自動重跑，不另找替代來源，不以其他代號補位。

### D.6 輸出與判讀規則

- **僅描述性輸出**：時區字串、時間戳 UTC 時分分布（依該時區當下是否夏令分組）、以交易所時區取日的星期分布、空 close 根清單、最後一根與 `regularMarketTime` 的關係、假日列與週日列的有無與原值、以及與 `data_cache` 現值的逐日差異表。
- **不得**據以：宣稱 `FX_OBS_DATE_RULE_VERIFIED` 或任何日期規則已驗、核准任何 Eligibility、斷言快取值錯誤、改寫 `rows_from_daily_close` 的規則、決定是否補列或刪列。
- 單次探測只證明「該次、該時刻、該窗」的回應，不外推到其他季節、其他代號或未來；與 `data_cache` 的差異只列為待釐清線索，兩者同為 Yahoo，不是獨立交叉驗證。
- 一律標註 `INFERENCE` 的結論不得升級為 FACT。

### D.7 執行環境與權限（選項與風險，不選定）

| 選項 | 說明 | 風險／限制 |
|---|---|---|
| E1 新增專用最小探測腳本與 workflow | 只含 `^GSPC`、`^VIX`、`^TWII`；單次請求、記 `http_requests_attempted`、存原始本文 | 需要新增 `.py` 與 workflow（屬程式／workflow 施工，須另行授權）；沿用 `ref: main` 與專用報告分支的防護設計 |
| E2 直接用既有 `.github/workflows/fx_obs_date_probe.yml` 傳 `tickers` | 不需新程式 | **FACT：腳本強制納入 `USDTWD=X` 與 `^VIX`（`REQUIRED_TICKERS`、`_parse_tickers`）**，會多探 D1，違反本批範圍；既有 `fetch_chart` 不覆寫 `retries`；既有報告只存解析後欄位而非原始本文；小時 K 只對匯率代號；`2y` 以外參數需改碼 |
| E3 以 Cloud 或 Streamlit 應用內觸發 | 以正式取數函式在 Cloud 上取 | 混入正式快取與 UI 狀態；不可重現；不建議 |
| E4 本機開發環境 | 離線補證與冬令探測文件均指出開發環境連不到 Yahoo | 不可行；本機另缺 pyarrow 與 pandera |

- **Yahoo 無金鑰**；既有 workflow 的 `PROXY_URL` 為可選 secret，是否經 NAS 中繼會影響出口 IP，屬待客戶決定項；規格不得內含任何 token 或 secret。
- 既有 workflow 以 `permissions: contents: write` 將報告推送到專用分支 `probe/fx-obs-date-results`；是否沿用該分支或另開，屬待客戶決定項。
- 授權單位：**專案 AI 無權自行觸發 workflow**；依 `PROJECT_RULES.md` 第 4 節，上游取數與新探測屬 Stop／Decision Gate。

### D.8 回滾與無副作用說明

- 對上游：只送 HTTP GET；不登入、不寫入、不變更任何第三方狀態。
- 對本 repo：不寫 Google Sheet、不寫 `data_cache`、不寫任何正式快取、不改 `FX_OBS_DATE_RULE_VERIFIED`、不碰 UI；**唯一寫入是報告檔**（選項 E1 的專用報告分支或證據目錄）。這是 repo 寫入，不是零副作用，須一併授權。
- 回滾：刪除報告檔或報告分支即可；報告不被任何正式程式讀取（與既有探測一致，`docs/evidence/probe_fx_obs_date/README.md`）。分支刪除須依 `PROJECT_RULES.md` 的分支刪除規定另行處理，本文不授權。
- 進程內快取（`_ttl_cache`、`source_backoff`）隨 runner 行程結束消失，不外溢。

### D.9 需客戶裁示的項目

**以下為專案 AI 推薦，未經客戶裁示。**

| # | 裁示題 | 方案 | 優點 | 風險／成本 | 專案 AI 推薦 |
|---|---|---|---|---|---|
| 1 | 是否授權這批 Yahoo 探測 | 不授權（維持第 C 節待驗） | 零上游風險 | 缺口維持 NEEDS_LIVE_EVIDENCE | 推薦在客戶確認第 2、3 題的條件後再授權；不是現在必須授權 |
| 1 | 同上 | 授權組合 S（3 請求） | 以最少請求回答時區與樣態、假日列、週日列 | 單一取數時刻 | **若授權，推薦只先授權 S** |
| 1 | 同上 | 授權 S＋L＋P＋H（10 請求） | 一次補多個缺口 | 請求數較多，且 H 的 1mo 窗不含 06-03 | 不推薦一次到位；先看 S 的結果再決定 |
| 2 | 執行環境 | E1 新增專用最小腳本與 workflow | 符合本批範圍、單次請求、原始本文可存 | 需程式與 workflow 施工授權 | **推薦 E1**；E2 因強制含 D1 且不存原始本文，不推薦 |
| 3 | 請求間隔與冷卻 | 5 秒、失敗後 30 分鐘內不得重跑 | 保守 | 增加執行時間 | 推薦 |
| 4 | 報告落點 | 沿用 `probe/fx-obs-date-results` 分支 vs 新分支 vs 直接提交 `docs/evidence/` | 沿用既有慣例省工 | 混放不同探測目的的報告；新分支需另管理 | 推薦新專用分支（探測目的不同），但屬客戶偏好，不是技術必要 |
| 5 | 是否做 T2 兩個取數時刻 | 做／不做 | 可對照「當日根何時出現」 | 兩次執行、請求數加倍 | 推薦先不做，視 S 的結果再議 |

本批探測即使授權並執行，也**不**解鎖 Eligibility、日期轉換規則、FX Gate、正式母集合或涵蓋率分母；這些仍各自需要獨立的客戶裁示。

## E. 揭露

- **單組產出，未經獨立複驗**：本文由單組專案 AI 研究寫成；第 C.2 節的新增離線事實（`^VIX` 於 2026-06-03 的日 K 與 16.26 的位置）為本次重讀三份既有探測報告所得，**未經第二組驗證**。
- **本次未做**：任何外部連線、任何取數函式執行、探測重跑；未安裝套件。本機沒有 pyarrow 與 pandera，故本文引用的 parquet 列數、日期與值全部來自離線補證（其自製解碼器單組自製、未以 pyarrow 交叉驗證，列數與 `data_cache/metadata.json` 的 `row_count` 相符是唯一外部旁證）；本文**未重新解碼 parquet**。
- **未涵蓋**：`ui_v2`／`ui_v3` 圖表縮放細節；EUR／JPY／CNY 與其他匯率；NASDAQ、MSCI、歐洲股指等無來源項；FRED 版次路徑的真實行為；2026-11-08 冬令探測的原始 `report.json`（不在 main，無法重算）；`tests/test_risk_radar.py`、`tests/test_us_liquidity_engine.py` 本機因缺 pandera 無法執行，不得宣稱通過。
- **讀碼為字面讀取**：以讀檔與符號名為主，會漏動態組出的字串與間接呼叫；本文沒有「某處只有 N 個使用點」類的封閉結論。
- **不確定處**：(a) `fetch_url` 在各類失敗下的實際 HTTP 嘗試次數上限本文未逐分支窮舉（D.2 因此要求報告記錄實際次數）；(b) `realtime_start` 的實際語意僅為推論；(c) 本文建議的 5 秒間隔、30 分鐘冷卻、目錄與檔名皆為專案 AI 建議，非既有規定；(d) cron 執行環境的本地時區未驗，影響 C.2、C.3 的候選 (d) 與 (c)；(e) 本工作樹為 shallow clone，git 歷史重建的可行性未驗。
- **語氣紀律**：缺漏不等於 0；proxy 不等於 real；程式存在不等於已抓到不等於日期已驗不等於可准入；本文件所列候選解釋均為待查線索，不是已判定的資料錯誤。
