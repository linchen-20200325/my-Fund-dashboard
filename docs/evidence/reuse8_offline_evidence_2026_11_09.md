# REUSE 8 項離線證據補強（唯讀、補充文件）

| 項目 | 內容 |
|---|---|
| 性質 | `docs/evidence/international_market_source_inventory_2026_11_09.md`（下稱「盤點報告」）的**補充**，不是平行 SSOT；盤點報告原文與原推薦一字未改 |
| 範圍 | 盤點報告第 4 節 REUSE 8 項：A1 S&P 500、A3 VIX、A11 TAIEX、D1 USD/TWD、C1 DGS10、C2 DGS2、C6 FEDFUNDS、C7 BAMLH0A0HYM2 |
| 基準 | main `e3ef7ffa`；盤點報告原 pin 為 `558fc00f`，程式引用以讀取當下的 `e3ef7ffa` 為準 |
| 日期 | 2026-11-09 |
| 不是什麼 | **不核准任何 Eligibility**；`FX_OBS_DATE_RULE_VERIFIED=False` 不變；不算任何正式涵蓋率或百分比；不新增 `indicator_key`、Schema、provider；不授權任何上游取數或探測 |
| 上位依據 | `PROJECT_RULES.md` 13.6（`DEC-2026-11-08-06`）；`DEC-2026-11-09-06`（G1／G2／G3 裁示，僅範圍與優先順序、不核准正式金融語意） |
| 標籤 | **FACT**＝本次離線讀檔／讀碼／重現所得；**INFERENCE**＝推論，可被推翻；**NOT VERIFIED**＝離線無法驗 |
| 驗證狀態 | 兩份研究草稿各由單組產出；本文件由第三組抽樣重驗關鍵事實（第 7 節），**不是獨立 QA**；未重驗的部分一律視為單組未驗 |

引用不寫行號，用「檔案＋符號」。

## 1. 先講結論

1. 離線可以補的，已補：`data_cache` 的 parquet 現在讀得出內容（第 3 節），四項取數起訖日、列數、異常列都有 FACT 層證據。
2. 離線補不了的，沒有補：`^GSPC`／`^TWII` 的真實日 K 時間戳與時區字串、FRED 對共用 L1 路徑的真實連線結果、FRED 版次（vintage）起點、USD/TWD 閘門內的日期規則，都仍是 NOT VERIFIED。
3. 本次新看到三個異常（第 3.2 節）與數個盤點報告未列的事實（第 6 節）；它們是**待查線索**，不是已判定的資料錯誤。
4. 本文件不核准任何 Eligibility，也不改變既有登記：盤點報告第 1 節計數為「客戶明文且核對過 1（A11，`DEC-2026-10-27-43`）；檔內自述未逐字核對 7（A1、A3、C1、C2、C4、C6、C7）」，本文件如實引用、不推翻；「程式存在、測試通過」不推得「已抓到」「日期已驗」「可准入」。

## 2. 五層區分（本文件的判讀紀律）

| 層次 | 意思 | 不得由前一層推得 |
|---|---|---|
| L-1 程式存在 | 有 fetcher／轉換碼 | — |
| L-2 測試通過 | 替身或手建 fixture 下分支行為符合預期 | 不等於 L-3 |
| L-3 真實抓取證據 | 有一份真實連線取回的原始或快照資料 | 不等於 L-4；快照由 cron 的另一套抓取碼產生時，也不證明共用 L1 在 Cloud 可用 |
| L-4 日期來源驗證完成 | 觀測日／公布日語意經真實資料驗過並有客戶核准 | 不等於 L-5 |
| L-5 正式准入（Eligibility） | 客戶核准其進入正式清單或分母 | 本文件不核准、不改變既有登記 |

各項目所處層次（FACT／NOT VERIFIED 的依據見各小節）：

| 項目 | L-1 | L-2 | L-3 | L-4 | L-5 |
|---|---|---|---|---|---|
| A1 `^GSPC` | 有 | 手建 fixture | 僅 cron 快照（日期層）；無探測時間戳 | 未驗 | 本文件不核准 |
| A3 `^VIX` | 有 | 有（部分 fixture 取自真實報告） | 有（探測報告＋快照） | 部分（時間戳樣態已見；值對時刻 NOT RUN） | 本文件不核准 |
| A11 `^TWII` | 有 | 手建 fixture | 僅 cron 快照 | 未驗 | 本文件不核准 |
| D1 `USDTWD=X` | 有 | 有 | 有（三份舊探測報告） | 規則未驗，閘門關 | 本文件不核准 |
| C1 DGS10 | 有 | 替身 | 僅 cron 快照（另一套抓取碼） | 未驗 | 本文件不核准 |
| C2 DGS2 | 有 | 替身 | 同 C1 | 未驗 | 本文件不核准 |
| C6 FEDFUNDS | 有 | 替身 | **無**（不在 cron 抓取清單） | 未驗 | 本文件不核准 |
| C7 HY OAS | 有 | 替身 | 僅 cron 快照（898 列） | 未驗 | 本文件不核准 |

## 3. 離線證據：`data_cache` 與探測報告

### 3.1 怎麼讀的（限制）

- 本機沒有 pyarrow 與 pandera，且不得安裝。parquet 以**兩份各自獨立撰寫的純 Python 解碼器**（thrift footer＋snappy＋dictionary／RLE）讀出；第三組以其中一份重讀並與兩份草稿的數字逐項比對，關鍵數字一致（第 7 節）。解碼器皆為單組自製、未以 pyarrow 交叉驗證；列數與 `data_cache/metadata.json` 的 `row_count` 相符是唯一的外部旁證。
- 三個 parquet 與探測報告是**別人過去用真實連線取得的快照**，本次離線重讀不構成本次的真實連線證據。
- 寫入端：`scripts/update_macro_history.py`（`update_one`、`fetch_fred_indicators`、`_yf_fetch_close`），排程 `.github/workflows/update_macro_history.yml`。它**自帶一套取數碼**（經 `_fetch_url_via_proxy`），不是共用 L1 `repositories/macro/fred.py::fetch_fred`／`repositories/macro/yf.py::fetch_yf_close`。

### 3.2 快取內容（FACT，第三組重讀已核對）

| 序列 | 列數 | 首日～末日 | 重複／NaN／0 | 備註 |
|---|---|---|---|---|
| `spx_history` | 3879 | 2011-06-07～2026-11-06 | 0／0／0 | 無週末列；最新三筆 7688.62、7353.73、7376.86 |
| `vix_history` | 3881 | 同上 | 0／0／0 | 比 SPX 多 2 列（見下）；最新 25.64 |
| `twii_history` | 3762 | 同上 | 0／0／0 | 含 1 列週日（見下）；最新 39701.64 |
| `fred_indicators` 內 DGS10 | 3855 | 2011-06-07～2026-11-05 | 0／0／0 | 無週末列；最新 4.84 |
| 同表 DGS2 | 3855 | 同上 | 0／0／0 | 最新 4.46 |
| 同表 BAMLH0A0HYM2 | **898** | **2023-06-05**～2026-11-05 | 0／0／0 | 12 列落在週末（皆月底日，例 2023-09-30、2026-05-31）；值域 2.59～4.61；最新 3.48 |
| 同表 FEDFUNDS | **不在表內** | — | — | 不在 `FRED_SERIES_IDS`，cron 從未抓取 |

`data_cache/metadata.json` 的 `last_updated` 是該資料集日期欄的**最大觀測日**，不是取數時刻；取數時刻見檔頭 `updated_at`（`2026-11-08T04:07:01+00:00`，整批一個值）。`last_error: null` 不保證每個 series 都取到（見第 6.1 節第 12 條）。

三個異常（FACT；成因皆 NOT VERIFIED，只能當待查線索）：

1. **VIX 比 SPX 多 2 列**：`2026-05-25`（美國陣亡將士紀念日）與 `2026-09-07`（勞動節）。這兩天 SPX 沒有列，VIX 有非空值（16.59、15.30）。同一份探測報告（`probe_fx_obs_date` 的 2026-10-14 run `38524215912`）的原始日 K 也有這兩根且值相同；該報告 `^VIX` 的 19 根空 close 不含這兩天。成因（Yahoo 補列、或 VIX 計算日曆與 SPX 不同）未驗。
2. **`2026-06-03` 的 VIX 快取值與探測值不同**：快取 16.26、探測原始 16.06。兩者同為 Yahoo，只證明一致性不是獨立來源。**INFERENCE**：寫入端增量只抓「最後日期 +1 天」之後，已入庫日期不會被重抓，Yahoo 事後改值不會反映到快取。
3. **TWII 含 1 列週日**：`2026-09-20`，close 47180.75，與前一週五 `2026-09-18` 完全相同。是否真實交易（補班）或 Yahoo 重複列，未驗。

### 3.3 探測報告能證明什麼（FACT，舊 run 重讀）

`docs/evidence/probe_fx_obs_date/` 有三份 gz（2026-10-13 run `38450455092`、2026-10-14 run `38510633247`、run `38524215912`），皆 6 個代號、`fx_obs_date_rule_verified_at_run: false`。代號是 `USDTWD=X`、`^VIX`、EURTWD、JPYTWD、CNYTWD、CNHTWD；**不含 `^GSPC`、`^TWII`**。

- `^VIX`：`exchangeTimezoneName` 為 `America/Chicago`；日 K 時間戳 UTC 07:00（夏令）／08:00（冬令）＝芝加哥 02:00；非空 503 根；以交易所時區取日與舊規則的 `diff_count` 為 0。
- `USDTWD=X`：`exchangeTimezoneName` 為 `Europe/London`；日 K 根時間戳 UTC 23:00 與 00:00 兩種（另有 1 根即時 bar：該 run 為 UTC 06:47、等於 `regularMarketTime`，其他 run 時刻不同）；以 UTC 取日（舊規則）週日根 60；新舊取日規則不同的根 300／518。
- **2026-11-08 冬令探測（E1174，run `42455423910`）的原始 `report.json` 不在 main**，可見的是分析文件 `docs/evidence/fx_obs_date_winter_probe_2026_11_08.md`；該文件引用的數字（例如 518 列、0.0034%、-0.1264%）本次**無法由原始檔重算**。注意舊報告的新舊取日規則差異 300／518 與 E1174 文件的 298／518 屬不同 run，不可互相比對。

## 4. 八項逐項補證

欄位：既有證據來源｜證據實際支持｜限制｜最小缺口｜能否離線補足｜是否需另行授權唯讀上游探測｜Eligibility｜分類。

分類僅為本研究文件的分類，**不是 UI 狀態字彙**，不得用於 UI 顯示或寫入任何 Sheet；EXISTING_EVIDENCE＝repo 內已有證據；OFFLINE_VERIFIABLE＝離線可再驗；NEEDS_LIVE_EVIDENCE＝需上游真實連線；BLOCKED_BY_GATE＝被正式 Gate 擋住。

### A1 S&P 500（`^GSPC`）

| 欄位 | 內容 |
|---|---|
| 既有證據來源 | 盤點報告第 2、3、4 節；`data_cache/spx_history.parquet`；`repositories/macro/yf.py::fetch_yf_close`；`services/risk_radar.py`（200 日均線燈）；`services/v2_tables/market_view.py`；`ui_v3/adapters/market_page.py` |
| 證據實際支持 | cron 快取 3879 列、日期單調無重複、無週末列、無 NaN（FACT）。Old 路徑直接取最後一筆、不判收盤；New UI2／ui_v3 路徑以交易所當地日與「未收盤界線」判斷（FACT，讀碼）。`tests/test_risk_radar.py` 有 `_signal_spx_trend_break` 測試（本機無法執行） |
| 限制 | `^GSPC` 真實日 K 時間戳與 `exchangeTimezoneName` **無真實證據**（範圍：repo 內、離線可見、讀取當下 `e3ef7ffa`）（不在探測清單）。`tests/test_v2_tables_market_view.py` 的 `_gspc_series` 是手建（固定 UTC 13:30，無夏令 14:30 案例）；手建 fixture 驗分支，不等於真實回應（proxy≠real） |
| 最小缺口 | 一次真實 `^GSPC` 日 K 的時區字串與時間戳樣態（夏令／冬令各一） |
| 能否離線補足 | 否。**INFERENCE**：美股 16:00 ET 收盤後到 UTC 換日前取數，當日根會被「未收盤界線」擋掉，要等 UTC 換日才放行；與盤點報告第 4 節推論一致，仍未用真實回應驗 |
| 是否需另行授權唯讀上游探測 | 是（補第二句缺口） |
| Eligibility | 本文件不核准、不改變既有登記（見盤點報告第 1 節） |
| 分類 | EXISTING_EVIDENCE、OFFLINE_VERIFIABLE（日期層）、NEEDS_LIVE_EVIDENCE（時間戳層） |

### A3 VIX（`^VIX`）

| 欄位 | 內容 |
|---|---|
| 既有證據來源 | 盤點報告第 2、4 節；探測報告 run `38524215912`；`data_cache/vix_history.parquet`；`services/risk_radar.py`、`services/macro/us_indicators.py`、`services/liquidity_engine.py`、`services/fund_service.py::get_latest_vix`（各自不同取數範圍） |
| 證據實際支持 | 時區字串 `America/Chicago`、時間戳＝芝加哥 02:00（FACT，舊 run）；19 根空 close 為美國休市日；快取 3881 列。另有兩項異常（第 3.2 節 1、2） |
| 限制 | 探測報告到 2026-10-13；E1174 原始檔不在 main；盤點報告「同日規則寫出 504 列」屬 11-08 run，本次**無法重算**（NOT VERIFIED，不判錯）。小時 K 值對時刻（E1174 標 NOT RUN）仍未驗 |
| 最小缺口 | 2026 年兩個美國假日列是否為真實 VIX 收盤；快取與探測的 0.20 差異成因；小時 K 值對時刻 |
| 能否離線補足 | 部分：可離線再對照兩份已存資料（已做）；成因需上游重取 |
| 是否需另行授權唯讀上游探測 | 是（成因與小時 K） |
| Eligibility | 本文件不核准、不改變既有登記（見盤點報告第 1 節） |
| 分類 | EXISTING_EVIDENCE、OFFLINE_VERIFIABLE、NEEDS_LIVE_EVIDENCE |

### A11 TAIEX（`^TWII`）

| 欄位 | 內容 |
|---|---|
| 既有證據來源 | 盤點報告第 4 節；`data_cache/twii_history.parquet`；`services/v2_tables/market_view.py`；`DEC-2026-10-27-43`（客戶裁示：唯一來源 Yahoo `^TWII`，成交量與市場統計維持 Data Gap） |
| 證據實際支持 | 快取 3762 列、無 NaN／0／重複；**含 1 列週日**（第 3.2 節 3）。New UI2 的 `rows_from_daily_close` 會以「週末」規則丟掉週日根；Old 路徑無此規則，但 Old 無獨立 TAIEX 卡片，字面搜尋所見的使用處為 `services/crisis_backtest.py`（FACT，讀碼，`git grep` 字面搜尋） |
| 限制 | `^TWII` 真實時間戳與時區字串無證據；`_tw_series` fixture 為手建（台北 09:00＝UTC 01:00 的假設）。客戶原話本次未逐字對照存檔，只讀到 `docs/DECISIONS.md` 標題與其自述 |
| 最小缺口 | 同 A1，另加週日列成因；**INFERENCE**：台北日期不早於 UTC 日期，未收盤界線取台北日，故當日收盤要到台北換日（UTC 16:00 後）才被放行。盤點報告對 A11 只寫「同 A1」，未點出此台北側延遲 |
| 能否離線補足 | 否 |
| 是否需另行授權唯讀上游探測 | 是 |
| Eligibility | 本文件不核准、不改變既有登記（見盤點報告第 1 節） |
| 分類 | EXISTING_EVIDENCE、NEEDS_LIVE_EVIDENCE |

### D1 USD/TWD（`USDTWD=X`）

| 欄位 | 內容 |
|---|---|
| 既有證據來源 | 盤點報告第 5 節；三份舊探測報告；`docs/evidence/fx_obs_date_winter_probe_2026_11_08.md`；`services/v2_tables/market_indicator.py`（`FX_OBS_DATE_RULE_VERIFIED=False`）；`repositories/hot_money_repository.py::fetch_usdtwd_series`；`repositories/fund/fx_and_main.py::get_latest_fx` |
| 證據實際支持 | 來源回得了資料；日 K 時間戳樣態（倫敦時區、UTC 23:00／00:00）；規則碼與閘門現狀。Old 路徑（`hot_money_repository`、`get_latest_fx`）不看閘門、對觀測日無規則（FACT，讀碼） |
| 限制 | 值與小時價一致性（0.0034%）自述為一致性而非收盤時間規則，樣本 13／5／5 日；冬令樣態的證據為 E1174 文件文字；無真實離線快取（`data_cache` 無 USD/TWD）；`tests/test_v2_tables_market_indicator.py` 有手建 `USDTWD=X` 序列（約 25 個平日，非真實回應） |
| 最小缺口 | **不是缺驗證，是閘門關**：開閘前條件（見碼內註解與冬令探測文件）無一完成；Eligibility 屬客戶核准層次，離線資料不能推導 |
| 能否離線補足 | 否（且不應以離線資料嘗試推導 Eligibility） |
| 是否需另行授權唯讀上游探測 | 視客戶是否要推進 FX 開閘；本文件不推薦 |
| Eligibility | 本文件不核准、不改變既有登記（見盤點報告第 1 節） |
| 分類 | EXISTING_EVIDENCE、BLOCKED_BY_GATE |

### C1 DGS10 與 C2 DGS2

| 欄位 | 內容 |
|---|---|
| 既有證據來源 | 盤點報告第 2、3 節；`data_cache/fred_indicators.parquet`；`repositories/macro/fred.py::fetch_fred`；`services/macro/us_indicators.py`（預熱 n=2600）；`services/v2_tables/market_view.py`（n=1500）；`tests/test_v2_tables_market_view.py` |
| 證據實際支持 | cron 取回各 3855 列、2011-06-07～2026-11-05、無缺漏列；假日 `.` 已丟（FACT）。單位是 FRED 原始百分比數值（4.84、4.46）。本次重跑 `tests/test_v2_tables_market_view.py`、`tests/test_v2_tables_market_indicator_fred.py`、`tests/test_fred_vintage_l1.py`：通過（第 5 節） |
| 限制 | cron 用的是 `scripts/update_macro_history.py` 自己的 `_fred_get_single`，**不等於共用 L1 `fetch_fred` 在 Cloud 可用**；FRED 對共用 L1 路徑的真實連線證據，repo 內離線可見範圍未見（範圍：repo 內、離線可見、讀取當下 `e3ef7ffa`）。測試皆替身，驗形狀與分支，不是真實日期／單位／版次語意 |
| 最小缺口 | 共用 L1 首次部署是否出現取數失敗或空序列；n=1500 在真實 FRED 實際回幾列 |
| 能否離線補足 | 否（cron 快照只補 L-3 的旁證） |
| 是否需另行授權唯讀上游探測 | 是（FRED 需金鑰與 L1 真實呼叫） |
| Eligibility | 本文件不核准、不改變既有登記（見盤點報告第 1 節） |
| 分類 | EXISTING_EVIDENCE、OFFLINE_VERIFIABLE、NEEDS_LIVE_EVIDENCE |

### C6 FEDFUNDS

| 欄位 | 內容 |
|---|---|
| 既有證據來源 | 盤點報告第 2、3 節；`services/macro/us_indicators.py`（n=144）；`services/v2_tables/market_indicator.py::INDICATOR_SPECS`（`policy_rate_pct`，走 vintage）；`app.py`（注入無風險利率）；`services/fund_service.py::set_risk_free_rate` |
| 證據實際支持 | 讀碼：`fetch_fred_vintages` 路徑對 `.` 轉 NaN **保留列**，在 L2 才略過；Old 路徑 FEDFUNDS 缺值時 `app.py` 不呼叫 `set_risk_free_rate`，`fund_service` 沿用預設 4%（FACT，讀碼） |
| 限制 | **未見任何間接證據**（範圍：repo 內、離線可見、讀取當下 `e3ef7ffa`）：FEDFUNDS 不在 `FRED_SERIES_IDS`、不在 parquet，不能引用 `META.fred_indicators`。月頻 `date` 是否為期初、vintage 起點，皆 NOT VERIFIED。「月均有效利率」的出處為 repo 內自述（`services/macro/tw_local.py` 註解），外部事實未驗 |
| 最小缺口 | 一次真實 FEDFUNDS 的觀測日慣例與 vintage 起點 |
| 能否離線補足 | 否 |
| 是否需另行授權唯讀上游探測 | 是 |
| Eligibility | 本文件不核准、不改變既有登記（見盤點報告第 1 節） |
| 分類 | NEEDS_LIVE_EVIDENCE |

缺值以非零預設（4%）替代是否符合 `CLAUDE.md` §1／13.6 的風險判斷，**本文件只陳述事實、不裁決**。

### C7 BAMLH0A0HYM2（HY OAS）

| 欄位 | 內容 |
|---|---|
| 既有證據來源 | 盤點報告第 2、3 節；`data_cache/fred_indicators.parquet`；`services/macro/us_indicators.py`（n=2500）；`services/risk_radar.py`（n=120）；`services/us_liquidity_engine.py`（n=60）；`services/macro/turning_points.py`（n=400）；`INDICATOR_SPECS` 的 `credit_spread_pct`（vintage） |
| 證據實際支持 | cron 取回 **898 列、起自 2023-06-05**，同批 DGS 都從 2011-06-07 起（FACT）。同一組數字在不同層標 `%`、`pp`、bp（FACT，僅陳述，不裁決單位語意） |
| 限制 | 起點較晚的成因為 **INFERENCE**（供應端約 3 年窗），未經 FRED 文件或真實連線驗證。若 live `fetch_fred(HY, n=2500)` 也受同一限制，Old 的「n=2500＝10 年」假設不成立；Old 的 HY 區塊只檢查 `len(df) >= 2`，樣本變短不會報錯（FACT，讀碼；live 行為 NOT VERIFIED） |
| 最小缺口 | HY 真實可取歷史長度；vintage 路徑 `at_floor`／`before_obs` 比例（**INFERENCE**：供應端若只保留近 3 年，版次起點可能等於回溯下界，大量落入不寫列） |
| 能否離線補足 | 部分（898 列起點已離線確認；成因與 live 長度不能） |
| 是否需另行授權唯讀上游探測 | 是 |
| Eligibility | 本文件不核准、不改變既有登記（見盤點報告第 1 節） |
| 分類 | EXISTING_EVIDENCE、OFFLINE_VERIFIABLE、NEEDS_LIVE_EVIDENCE |

## 5. 測試狀態（誠實揭露）

| 項目 | 結果 |
|---|---|
| 第三組本次執行（`PYTHONPATH=.:/usr/local/lib/python3.13/site-packages /root/.local/bin/pytest … --noconftest -p no:cacheprovider -q`） | `tests/test_v2_tables_market_view.py`、`tests/test_v2_tables_market_indicator_fred.py`、`tests/test_fred_vintage_l1.py`、`tests/test_probe_fx_obs_date.py`：**146 passed** |
| 本次**未能執行** | `tests/test_risk_radar.py`、`tests/test_us_liquidity_engine.py`（收集階段缺 pandera）。**不得宣稱通過**；只以靜態讀檔確認有對應測試 |
| 草稿自報、第三組未重跑 | 草稿 A：`test_probe_fx_obs_date`＋`test_probe_fx_daily_value_check`＋`test_update_macro_history` 為 114 passed、5 failed（5 項因缺 pyarrow 的 parquet 讀寫）；草稿 B：相關批次 166 passed、16 failed（部分缺 pyarrow，其餘未查明，疑與 `--noconftest` 少 fixture 有關）。這些數字**單組自報，未驗** |
| 測試性質 | 以上皆替身或手建 fixture，驗形狀與分支，**不是真實連線、不是真實日期／單位／版次語意** |

## 6. 對盤點報告的「需補充／需修正」清單

只列兩份草稿所指；**不改盤點報告**。每條附證據與標籤。

### 6.1 需補充（報告原句不錯，缺一塊）

| # | 補充點 | 證據 | 標籤 |
|---|---|---|---|
| 1 | `data_cache` 的三個 parquet 另有三個下游消費者：`services/macro/validation.py`、`scripts/calibrate_macro_score.py`、`scripts/export_fund_db.py` | `git grep` 檔名（第三組重跑，命中這三個非測試檔加寫入端） | FACT（字面搜尋，會漏動態組字串） |
| 2 | A3：2026 年兩個美國假日有非空 VIX 收盤；快取 2026-06-03 與探測差 0.20 | 第 3.2 節，第三組重讀兩份資料 | FACT；成因 NOT VERIFIED |
| 3 | A11：快取含 1 列週日、值同前一週五；台北側當日收盤要等台北換日才被放行 | 第 3.2 節；放行邏輯為讀碼推論 | 週日列 FACT；延遲 INFERENCE |
| 4 | 盤點報告第 5 節「`data_cache/*.parquet` 讀不到」可更新為「已離線解碼」：三檔最後觀測日 2026-11-06，FRED 表 2026-11-05 | 第 3.2 節 | FACT（自製解碼器） |
| 5 | C7：cron 只取回 898 列、2023-06-05 起，可把「歷史長度是否滿足 n=2500」由 NOT VERIFIED 升級為「離線快取顯示不足，live 未驗」 | 第 3.2 節 | FACT（快取）／INFERENCE（成因） |
| 6 | C6：Runtime evidence 應明寫「未見間接證據（repo 內離線可見）」（不在 cron 清單） | `FRED_SERIES_IDS` 讀碼＋parquet 無此 series | FACT |
| 7 | C7 漏列 `services/macro/turning_points.py` 的 n=400 | 讀碼 | FACT |
| 8 | C1：`services/risk_radar.py` 另以 Yahoo `^TNX` 與 FRED 做雙源對帳（`reconcile_us10y_yield`） | 草稿 B 讀碼 | FACT（單組，第三組未重驗） |
| 9 | C6：`fund_service.set_risk_free_rate` 注入點為 `app.py`（FEDFUNDS÷100），缺值沿用預設 4% | 草稿 B 讀碼 | FACT（單組，第三組未重驗） |
| 10 | `fetch_fred` 快取 `maxsize=32`（`fetch_fred_vintages` 為 16）；同一 series 以不同 n 各自成鍵，Old 預熱與其他路徑合計的不同鍵數下限約 39（人工逐項數，下限、未實跑），TTL 內有被擠出重打的可能 | `maxsize=32` 第三組已核對；鍵數與擠出為 INFERENCE | FACT（maxsize）／INFERENCE（擠出） |
| 11 | 盤點報告把 A1 計為「檔內自述未逐字核對」；草稿 A 讀 `DEC-2026-10-27-41` 與 `-42`，`-42` 自述客戶原文為條件式。本文件**不改變該登記**，只建議盤點報告 A1 列註明「依據為條件式自述」 | 草稿 A 讀 `docs/DECISIONS.md`；**未再逐字核對客戶原話** | FACT（讀文件）／原話 NOT VERIFIED |
| 12 | `FRED_SERIES_IDS` 有 11 項，但 parquet 只見 9 個 series（PPIACO、PCOPPUSDM 缺）；DTWEXBGS 僅 21 列（2026-06-05 起），而 `metadata.json` 的 `last_error` 為 null——`last_error: null` 不保證每個 series 都取到；增量以整表最大日 +1 為起點，後加入或曾失敗的 series 不回補（成因為 INFERENCE） | 第三組重讀 parquet 與 `scripts/update_macro_history.py` | FACT（序列結構）／INFERENCE（成因） |

### 6.2 需修正（適用範圍）

| # | 修正點 | 證據 | 標籤 |
|---|---|---|---|
| 1 | 盤點報告 C1 列寫「假日 `.` 在 L1 丟棄、不補」，只對 `fetch_fred` 成立；C6／C7 的 `ui_v2`／`ui_v3` B 線走 `fetch_fred_vintages`，`.` 轉 NaN 並**保留列**，在 L2 才略過。Fetch behavior 欄需分開寫 | 草稿 B 讀碼；第三組未重驗 | FACT（單組） |
| 2 | A11 的客戶裁示（`DEC-2026-10-27-43`）涵蓋來源選擇（唯一來源 Yahoo `^TWII`）與成交量／市場統計維持 Data Gap；盤點報告第 1 節將其計為 Eligibility 客戶明文 1 項。本文件不改變該計數；是否另含 Eligibility 以 `docs/DECISIONS.md` 該筆原文為準，本組未逐字重核 | 草稿 A 讀 DECISIONS 標題 | 待核（不推翻） |

### 6.3 兩項待查（不判錯、不改）

- 草稿 B 指出：`services/macro/us_indicators.py` 的「發布延遲」`publish_lag_days` 以 `realtime_start − 觀測日` 計算，而 `fetch_fred` 不帶 real-time 參數、`realtime_start` 為查詢當天，故該「延遲」實為「查詢日 − 觀測日」。依 repo 自述與 FRED 預設行為推論，**INFERENCE，未連線驗證**。
- 盤點報告「同日規則寫出 504 列」屬 11-08 run，原檔不在 main，本次無法重算。

## 7. 抽樣重驗紀錄（第三組，離線）

| 重驗項 | 方法 | 結果 |
|---|---|---|
| 三個 parquet 列數、首末日、單調、重複、NaN | 以草稿 B 的解碼器重讀並計算 | 與草稿 A 一致（3879／3881／3762；2011-06-07～2026-11-06） |
| VIX 比 SPX 多 2 列 | 兩序列日期集合差 | 恰為 `2026-05-25`、`2026-09-07`；SPX 多於 VIX 的日期為空 |
| `2026-06-03` 差異 | 快取與探測 gz 原始日 K | 快取 16.26，探測原始 16.06（UTC 07:00 根） |
| 兩個假日於探測資料 | 探測 gz 的 `raw_daily_full` | 兩根存在、值與快取相同；不在 `null_close_bars` |
| TWII 週日列 | 快取 | `2026-09-20` 週日、47180.75，等於 `2026-09-18` 週五 |
| HY OAS 898 列、2023-06-05、12 列週末、FEDFUNDS 不在表 | 重讀 `fred_indicators` | 與草稿 B 一致 |
| `FRED_SERIES_IDS`、增量起點 | 讀 `scripts/update_macro_history.py` | 11 項、不含 FEDFUNDS；增量 `start = last + 1 天` |
| `fetch_fred` `maxsize=32`、預熱 n 值、turning_points n=400、`FX_OBS_DATE_RULE_VERIFIED=False` | `git grep` | 與草稿一致 |
| 探測 gz 時區與時間戳 | 讀 `^VIX` 項 | `America/Chicago`、UTC 07:00／08:00 |
| 解碼器交叉 | QA 以第二套獨立解碼器重現相同數字 | 一致；仍非 pyarrow 交叉驗證 |

## 8. 三種補證方法比較

| 方法 | 做法 | 能補到的層次 | 風險 | 本文件現況 |
|---|---|---|---|---|
| A 重用報告與測試 | 讀既有盤點報告、探測報告、測試 | L-1、L-2、舊 L-3 的重讀 | 把測試當真實證據 | 已做 |
| B 離線 fixture／歷史資料描述性驗證 | 重讀 `data_cache` 快照做描述統計與跨來源對照 | L-3 的一致性旁證、異常線索 | 快照可能來自另一套抓取碼；同源（Yahoo）對照不是獨立證據；自製解碼器 | 已做（第 3 節） |
| C 未來受控唯讀探測 | 於 Cloud 或 workflow 對上游做一次唯讀取數 | L-3 真實、L-4 時間戳樣態 | 屬 Stop Gate 的上游取數；需金鑰、需新增探測代碼；**本文件只記需求，不執行、不授權** | 僅記需求 |

## 9. 下一個最小 Decision Gate（待客戶裁示）

**以下為專案 AI 推薦，未經客戶裁示。**

**推薦：方案 3（暫不探測，先把本文件與盤點報告的缺口併入文件契約整理）**；若客戶要補證，優先方案 2（Yahoo 三項）而非方案 1（FRED 四項）。理由：方案 3 零上游風險、與 `DEC-2026-11-09-06` 的 G2＝A 一致；方案 2 不需金鑰，且 `probe_fx_obs_date` 已有探測基礎；方案 1 需要 FRED 金鑰與共用 L1 真實呼叫，成本最高。

| 方案 | 內容 | 優點 | 風險／成本 |
|---|---|---|---|
| 1 | 授權一次受控唯讀探測 FRED 四項（DGS10、DGS2、FEDFUNDS、BAMLH0A0HYM2） | 一次補 C1／C2／C6／C7 的 live 缺口（版次起點、HY 長度、FEDFUNDS 日期慣例） | 需金鑰與新探測代碼；屬 Stop Gate；FRED 限流與 vintage 解讀需另行審 |
| 2 | 授權一次受控唯讀探測 Yahoo 三項（`^GSPC`、`^TWII`、`^VIX`） | 補 A1／A11 的時區字串與時間戳樣態，並查 A3 假日列與 0.20 差異；不需金鑰 | 需擴充探測清單（程式變更）；結果只證明該次，不推得准入；仍不涵蓋 D1 閘門 |
| 3 | 暫不探測，先做 Stage 2 契約（純文件） | 零上游風險；把已知缺口寫死在契約裡 | 缺口維持 NEEDS_LIVE_EVIDENCE，待日後再議 |

不論選哪個方案，本文件與 `DEC-2026-11-09-06` 都**不授權**上游取數、探測、Sheet 施工、FX 開閘；任何探測仍須客戶另行裁示。

## 10. 未涵蓋範圍與揭露

- 本次未做真實連線、未執行取數函式；本提交未改 `.py`、workflow、CLAUDE.md、frozen SSOT（範圍：repo 內、離線可見、讀取當下 `e3ef7ffa`）。
- 本機缺 pyarrow 與 pandera：parquet 以自製解碼器讀取，未以 pyarrow 交叉驗證；`tests/test_risk_radar.py`、`tests/test_us_liquidity_engine.py` 未執行。
- 兩份研究草稿各為單組產出、未經第二組驗證；第 7 節為第三組抽樣重驗，**不是獨立 QA**，未涵蓋的項目（第 6.1 的 8、9 兩條、第 6.2、第 6.3 的 `publish_lag_days` 推論、測試批次的自報數字）維持單組未驗。
- 讀碼以字面 `git grep` 為主，會漏動態組字串；未讀 `ui_v2/mkt/chart.py`、`ui_v3/adapters/market_chart.py` 的圖表縮放細節；未驗 EUR／JPY／CNY；未重算 E1174 數字。
- 語氣紀律：缺漏不等於 0；proxy 不等於 real；程式存在不等於已抓到不等於日期已驗不等於可准入。
