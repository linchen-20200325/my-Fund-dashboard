# 國際市場資料來源與 UI 重用盤點（唯讀彙整）

| 項目 | 內容 |
|---|---|
| 範圍 | 美國與國際股市、美國總經、美債／利率／信用／流動性、美元與匯率，共四個領域；加上 Old UI → `ui_v2` → `ui_v3` → 共用資料層的能力差距，以及 `docs/v2/83` 候選監控 Sheet 四分頁的準備度 |
| 基準 | main `558fc00f`（本報告所有程式引用以該 commit 為準；研究組初稿曾基於 `15538a57`，兩者的 `*.py` 只差 `tests/test_doc_counters.py` 一行註解） |
| 日期 | 2026-11-09 |
| 性質 | 純文件、唯讀盤點；沒有打任何外部 API、沒有新增程式或測試、沒有凍結 SSOT 或白名單變更 |
| 授權 | **本文件合併不是施工授權**；不新增 DEC、不新增 BL 編號、不改 BL 狀態、不改 HANDOFF 唯一 NEXT；不推薦也不授權任何實際抓取或探測 |
| 作者與驗證 | 三組單組唯讀研究（股市＋匯率、總經＋利率信用流動性、UI＋Sheet）由文件組彙整；彙整者另行抽查研究組宣稱（見第 9 節），**不是獨立 QA**；除附指令者外，全稱句一律是單組未驗 |
| 標籤 | **FACT**＝讀碼或讀檔所得；**INFERENCE**＝推論；**NOT VERIFIED**＝本報告與既有證據都沒有驗 |
| 上位文件 | `docs/v2/83_international_market_data_monitor_design.md`（候選設計，不授權實作）、`PROJECT_RULES.md` 13.6（`DEC-2026-11-08-06`，New UI2 Legacy Capability Review Gate） |

## 1. Executive Summary

1. **範圍與總量**：逐指標表共 **61 列**（A 美國與國際股市 12、B 美國總經 22、C 美債／利率／信用／流動性 13、D 美元與匯率 14）。這是研究組的列數合計；兩組的主表沒有重疊列，美元與利率相關的補充列（第 2.5 節）只是對主表的交叉引用。
2. **四個概念必須分開，且不可互相推導**：

| 概念 | 白話 | 本盤點的判定標準 | 61 列中的計數 |
|---|---|---|---|
| Source exists | 程式裡有這個來源的取數碼且可達 | 靜態讀碼 | 有 **52**、無 **9**（A2、A4、A5、A6、B3、B6、B7、B9、B22） |
| Fetch verified | 有真實連線的證據檔 | 探測報告或 cron 的 `metadata.json` | 直接證據 **4**（A3、D1、D11、D12）；名義成功但實質只回 1 根 **1**（D13）；間接證據（另一套抓取器、只到資料集層級）**12**；無證據 **44** |
| Validation verified | 日期、單位、方向經獨立證據驗過 | 獨立證據，不是替身測試 | 完整正向 **0**；部分正向 **2**（A3、D1）；證據呈負向或未解 **3**（D11、D12、D13）；無證據 **56** |
| Eligibility approved | 客戶正式核准進入畫面、計算或 AI evidence | DECISIONS 與凍結規格 | 客戶明文且我核對過登記者 **1**（A11 TAIEX，`DEC-2026-10-27-43`）；檔內自述有依據、我未逐字核對者 **7**（A1、A3、C1、C2、C4、C6、C7）；無 **53** |

   **四者不可互相推導**：來源存在不等於抓得到；抓得到不等於驗過日期；驗過日期不等於核准採用。最明顯的反例是 USD/TWD（D1）：來源存在、有真實探測、日期規則有部分證據，但 `FX_OBS_DATE_RULE_VERIFIED=False`，Eligibility 仍是否。另一個反例是 D13：探測狀態是 `ok`，實際只回 1 根，不能當作有歷史資料。
3. **重用分類**（本報告彙整後的計數，規則見第 4 節）：**REUSE 8／EXTRACT 31／REDESIGN 8／NOT VERIFIED 14**，合計 61。研究組原標籤合計為 REUSE 20／EXTRACT 19／REDESIGN 8／NOT VERIFIED 14；差異來自本報告對 REUSE 與 EXTRACT 的界線採同一條規則（第 4 節）。**REUSE 與 EXTRACT 只表示程式能力可重用，不是 Eligibility。**
4. **最大缺口（依影響排序）**：(a) FRED 對真實連線的證據在共用 L1 路徑上是零，只有 cron 另一套抓取器的資料集層級旁證；(b) `FX_OBS_DATE_RULE_VERIFIED=False` 讓全部匯率停在資料未備，且「抓得到」與「可准入」必須分開；(c) `^GSPC`、`^TWII` 等的時區與時間戳樣態沒有證據；(d) NASDAQ、MSCI World、MSCI EM、歐洲股指在 production 沒有任何來源；(e) 既有 `fetch_log` 只有 7 欄，無法提供逐指標健康度，且 New UI2 第一階段對 Sheet 零寫入。
5. **新監控 Sheet 四分頁仍是候選**：沒有升格正式 Schema、沒有 writer、沒有分母；本報告不宣稱它可運作。
6. **專案 AI 推薦（未經客戶裁示）**：先以「直接重用已接線的共用 L1／L2」處理 REUSE 類，再以「抽離」處理 EXTRACT 類，只有確定無法重用的才另行設計；詳見第 7 節。需要客戶裁示的 Decision Gate 最多三題，見第 8 節。

## 2. 國際市場逐指標來源矩陣

### 2.0 欄位縮寫與共通行為（先讀，下表引用）

- **層級縮寫**：`fyc`＝`repositories/macro/yf.py::fetch_yf_close`（`fyce` 為 `_with_error` 版）；`ffred`＝`repositories/macro/fred.py::fetch_fred`（`ffrede` 為 `_with_error` 版）；`ffv`＝`repositories/macro/fred_vintage.py::fetch_fred_vintages_with_error`；`FAI`＝`services/macro/us_indicators.py::fetch_all_indicators`；`RR`＝`services/risk_radar.py::detect_risk_radar`；`mv`＝`services/v2_tables/market_view.py`；`mi`＝`services/v2_tables/market_indicator.py`；`LE`＝Old UI 的 `_load_everything`；`UL`＝`services/us_liquidity_engine.py`；`LQ`＝`services/liquidity_engine.py`。
- **Old UI**：`app.py` 的 `tab_macro` → `ui/views/page_01_macro.py::render_market_overview`（送出鈕後才取數）。**ui_v2／ui_v3 是獨立 Streamlit 入口**，Old UI 沒有 import 它們（第 9 節指令 V5）。
- **共通 Yahoo（Y）**：傳輸為 `infra.proxy.fetch_url`；`fyc` 的快取為 `@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=64)`；`fetch_url` 回 None 的可重試失敗標記不入快取，HTTP 200 空序列與 404／407 照舊快取；退避以**主機**為單位（`query1.finance.yahoo.com`），冷卻秒數 SSOT 在 `shared/backoff_policy.py`：unreachable 60、server_error 300、blocked 900、rate_limited 1800。
- **共通 FRED（R）**：`ffred` 為 `@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=32)`；缺 key → 空表加 `fetch_error`；200 但 `observations` 為空 → 空表且照常快取（不標記為失敗）；`"."` 在 L1 丟掉；請求是「最新 n 筆」，所以月頻或週頻「今天沒新值」只是最後一筆較舊，不會變成空表（靜態推論）。
- **共通日期（Y 日 K 取日）**：New UI2 的 `mi.rows_from_daily_close` 以 `meta.exchangeTimezoneName` 當地日取觀測日，未收盤界線取 max(UTC 日, 當地日)；只有 VIX、USD/TWD 等少數代號有探測證據（E1174）。Old UI 多取 `s.iloc[-1]`，無日期欄。
- **證據代號**：`E1174`＝`docs/evidence/fx_obs_date_winter_probe_2026_11_08.md`；`E1175`＝`docs/evidence/fx_d8_gap_and_supplementary_plan_2026_11_08.md`；`D83`＝`docs/v2/83_international_market_data_monitor_design.md`；`G3`＝`docs/evidence/g3_market_basis_data_contract_audit_2026_11_05.md`（只引用，不重建）；`META`＝`data_cache/metadata.json`（cron 腳本 `scripts/update_macro_history.py` 的自有抓取器所寫，不是共用 L1）。
- **Runtime evidence 的規則**：沒有證據一律寫 NOT VERIFIED；不填 0、不填成功、不填中性。
- **Reuse decision 的定義**見第 4 節；欄位開頭的第一個詞就是分類。

### 2.1 A 美國與國際股市（12 列）

| ID／Domain | Indicator | Series/Ticker | Provider | L1 | L2 | Old UI | ui_v2 | ui_v3 | Frequency | Unit/Direction | Date evidence | Fetch behavior | Cache/Cooldown | Runtime evidence | Formal Gate | Reuse decision | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1／A | S&P 500 | `^GSPC` | Yahoo | `fyc`／`fyce`（L2 傳 5y） | `mv.sp500_domain_from_l1`；`RR._signal_spx_trend_break`；`crisis_backtest` | 只有 200DMA 破口燈，無指數圖；`FAI` 不含 S&P 序列 | 真資料（`mv`） | 真資料（`market_page.load`→`mv`） | 日 | 指數點數 | 時區與時間戳樣態無證據（`^GSPC` 不在探測清單）；Old 取 `iloc[-1]`，無收盤過濾 | New：失敗→系統錯誤，通過規則後無列→資料未備；Old：不足 200 日→`_empty`（空與失敗同句） | Y | 間接：`META.spx_history` last_updated 2026-11-06、`last_error` 空（自有抓取器）；經 L1／ui_v2／ui_v3 的真實連線 NOT VERIFIED | `DEC-2026-10-27-41`（客戶）；`-42`、`-44` 是執行組讀法，不是客戶裁示 | REUSE | `mv.sp500_domain_from_l1`、`SP500_TICKER`；`risk_radar._signal_spx_trend_break`；`tests/test_v2_tables_market_view.py` |
| A2／A | NASDAQ | 無 | 無 | 無 | `mv.DOMAIN_NASDAQ`→`_MISSING_DOMAINS`（`no_official_source`） | 無 | 資料未備 | 資料未備 | — | — | — | 不抓；資料未備與抓取失敗分開 | — | 無行為可驗 | 客戶裁示：維持 Data Gap，不得以 QQQ／ETF 頂替（測試守） | REDESIGN | `mv._MISSING_DOMAINS`；指令 V4 |
| A3／A | VIX | `^VIX` | Yahoo（FRED 無 VIX 備援） | `fyc`／`fyce` | `mi.INDICATOR_SPECS["vol_index"]`；`mv.vix_domain_from_l1`；`RR`；`FAI["VIX"]`；`LQ`；`fund_service` | `LE`→`FAI`＋`RR`＋`LQ` | 真資料 | 真資料 | 日 | 指數點數 | E1174 FACT：回應自報 `America/Chicago`、時間戳為芝加哥 02:00；同日規則寫出 504 列；空 close 19 根落在美國假日；值對時刻的小時 K 對照 NOT RUN | New 同 A1；`FAI` 資料少於 6 筆時整格無聲消失，靠 `EXPECTED_INDICATOR_KEYS` 差集補顯示 | Y；Old 各處以不同範圍各自快取（第 3.3 節） | E1174：run `42455423910` 的 `^VIX` status ok；`META.vix_history` 2026-11-06 無 error；Cloud 真機 NOT VERIFIED | frozen 44（`vol_index`）、49 §6.1 Q3 | REUSE | `mi.INDICATOR_SPECS`；`mv.vix_domain_from_l1`；`us_indicators`（VIX 區塊）；E1174 §0、§2 |
| A4／A | MSCI World | 無 | 無 | 無 | `mv.DOMAIN_MSCI_WORLD` | 無 | 資料未備 | 資料未備 | — | — | — | 不抓（`no_official_source`） | — | 無行為可驗 | 同 A2；D83 §6 列為候選缺口 | REDESIGN | `mv._MISSING_DOMAINS`；指令 V4 |
| A5／A | MSCI EM | 無 | 無 | 無 | `mv.DOMAIN_MSCI_EM` | 無 | 資料未備 | 資料未備 | — | — | — | 同 A4 | — | 無行為可驗 | 同 A4 | REDESIGN | 同 A4 |
| A6／A | 歐洲股市（DAX／STOXX／FTSE／CAC） | 無 | 無 | 無 | 無 | 無 | 無 | 無 | — | — | — | 無實作 | — | 無 | D83 §6 只列未來候選；未核准 | REDESIGN | 指令 V4 |
| A7／A | VIX 期限結構與 MOVE | `^VIX3M`、`^VXV`、`^MOVE`（Yahoo）→ CBOE CSV → stooq → FRED `VXVCLS` | Yahoo／CBOE／stooq／FRED | `fyc`、`fetch_cboe_csv`、`ffred` | `RR._resolve_vix3m`、`_signal_move_level`；`LQ` | `LE`→`RR`＋`LQ` | 無 | 無 | 日 | 指數點數、比值 | 無日期欄，取 Series 位置末二筆 | 空表→進下一源；`RR` 註解自述 Yahoo 曾對 `^CPC` 等回空、`fetch_cboe_csv` docstring 稱 `^VIX3M` 等已停供，空與停供無法區分 | Y | NOT VERIFIED（只有註解中的舊診斷口述） | 無獨立 DEC | NOT VERIFIED | `risk_radar._resolve_vix3m`；`external_market_repository.fetch_cboe_csv` |
| A8／A | 日經 225 | `^N225` | Yahoo | `fyc`（1mo） | `RR._signal_asia_overnight`（與 HSI 平均單日跌幅） | `LE`→`RR` | 無 | 無 | 日 | 指數點數；以位置末二筆算漲跌，兩市休市日不同 | 時區與時間戳 NOT VERIFIED（不在探測清單） | 兩市都空才整體空；單側空標 N/A（空與失敗同） | Y | NOT VERIFIED | 無 | EXTRACT | `risk_radar._signal_asia_overnight` |
| A9／A | 恆生指數 | `^HSI` | Yahoo | `fyc`（1mo） | 同 A8 | 同 A8 | 無 | 無 | 日 | 指數點數 | 同 A8 | 同 A8 | Y | NOT VERIFIED | 無 | EXTRACT | 同 A8 |
| A10／A | 費城半導體 | `^SOX` | Yahoo | `fyc`（6mo） | `RR._signal_sox_drop` | `LE`→`RR` | 無 | 無 | 日 | 指數點數 | 時區未驗 | 不足 2 筆→`_empty` | Y | NOT VERIFIED | 無 | EXTRACT | `risk_radar._signal_sox_drop` |
| A11／A（邊界：台股） | TAIEX | `^TWII` | Yahoo（標示固定 `Yahoo Finance (^TWII)`，非 TWSE 官方） | `fyc`／`fyce`（5y） | `mv.taiex_domain_from_l1`；`crisis_backtest` | Old 無獨立卡片 | 真資料 | 真資料 | 日 | 指數點數 | 同 A1（不在探測清單） | 同 A1 | Y | 間接：`META.twii_history` 2026-11-06 無 error；L1 真實連線 NOT VERIFIED | `DEC-2026-10-27-43`（客戶裁示：唯一來源 Yahoo `^TWII`；成交量與市場統計維持 Data Gap） | REUSE | `mv.taiex_domain_from_l1`、`TAIEX_SOURCE_LABEL` |
| A12／A | SPY／RSP／QQQ（ETF，非指數） | `SPY`、`RSP`、`QQQ` | Yahoo | `fyc`；`fetch_benchmark_close`（9mo） | `FAI` ADL（RSP／SPY）；`mk_dashboard` 組合基準 | `FAI`→ADL；`ui/tab3_portfolio.py`→`mk_dashboard` | 無 | 無 | 日 | ETF 價 | ADL 日期為 UTC 無時區日；未驗 | `len>=22` 否則無聲不產生；基準取不到回 None | Y | NOT VERIFIED | 客戶裁示明禁以 ETF 當 NASDAQ／MSCI 代理（測試守） | NOT VERIFIED | `us_indicators`（ADL）；`yf.fetch_benchmark_close`；`tests/test_v2_tables_market_view.py` |

### 2.2 B 美國總經（22 列）

本節的 FRED 取數皆走共通 R；觀測日以 `date` 欄（observation_date）為準，**`realtime_start` 是查詢當天，不是首次公布日**（見第 5 節風險 6）；「Date evidence」欄只寫差異。Old UI 路徑一律為 `LE`→`FAI`（除另註）；ui_v2、ui_v3 的 `INDICATOR_SPECS` 與 `mv` 都沒有這一組指標，所以兩欄皆為「無」。

| ID／Domain | Indicator | Series/Ticker | Provider | L1 | L2 | Old UI | ui_v2 | ui_v3 | Frequency | Unit/Direction | Date evidence | Fetch behavior | Cache/Cooldown | Runtime evidence | Formal Gate | Reuse decision | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1／B | CPI（YoY 自算） | `CPIAUCSL` | FRED | `ffred`（批次 n=144） | `FAI["CPI"]` | 有 | 無 | 無 | 月 | %；高＝通膨 | 觀測日；無 vintage；CLAUDE.md §2.3 記發布約月後 13 日 | R；失敗該格不產生，`_fred_iso` 逐 series 隔離 | R；另有 next_release_date 檔案快取 | 間接：`META.fred_indicators` 2026-11-05 無 error（資料集層級，逐 series 最後日期 NOT VERIFIED）；`ffred` 路徑 NOT VERIFIED | 無 | EXTRACT | `us_indicators.fetch_all_indicators`；`FRED_CPI`；`data_registry._FRED_SERIES_MAP` |
| B2／B | PPI（全商品 YoY） | `PPIACO` | FRED | `ffred` | `FAI["PPI"]` | 有 | 無 | 無 | 月 | % | 同 B1 | R | R | 間接（同 B1） | 無 | EXTRACT | `FRED_PPI` |
| B3／B | PCE／核心 PCE | 無 | — | 無 | 無 | 無 | 無 | 無 | 月 | — | — | 無實作 | — | 無 | 無 | NOT VERIFIED | 指令 V14 |
| B4／B | 非農（NFP） | `PAYEMS` | FRED | `ffred`（n=144） | `FAI["NFP"]`（含 `_nfp_tier`） | 有 | 無 | 無 | 月 | 千人（變動量自算）；高＝就業強 | 觀測日；PAYEMS 會被大幅修正，本 repo 沒有首版值追溯 | R | R | `PAYEMS` 不在 cron 清單；NOT VERIFIED | 無 | EXTRACT | `us_indicators._nfp_tier` |
| B5／B | 失業率 | `UNRATE` | FRED | `ffred` | `FAI["UNEMPLOYMENT"]` | 有 | 無 | 無 | 月 | %；高＝就業弱 | 同 B4 | R | R | 間接（同 B1） | 無 | EXTRACT | `FRED_UNRATE` |
| B6／B | GDP（實質／名目） | 無 | — | 無 | 無（`data_registry` 僅有季頻註解） | 無 | 無 | 無 | 季 | — | — | 無實作 | — | 無 | 無 | NOT VERIFIED | 指令 V14 |
| B7／B | GDPNow | `GDPNOW`（只有常數） | FRED（Atlanta Fed；存在性未驗） | 無呼叫 | 無 | 無 | 無 | 無 | 不定 | — | — | 常數存在、無任何取數呼叫 | — | 無 | 無 | NOT VERIFIED | `shared/fred_series.py::FRED_GDPNOW`；指令 V13 |
| B8／B | CFNAI（Old UI 稱 LEI） | `CFNAI` | FRED | `ffred`（n=144；拐點 n=36） | `FAI["LEI"]`；`turning_points`（3M MA） | 有 | 無 | 無 | 月 | 指數；≤-0.7 衰退（`signal_thresholds`） | 觀測日；無 vintage | R；兩處各自取數，n 不同＝兩個快取鍵 | R | NOT VERIFIED | 無 | EXTRACT | `turning_points`；`data_registry._FRED_SERIES_MAP["LEI"]` |
| B9／B | LEI（USSLIND） | `USSLIND`（只有常數，標 deprecated） | FRED | 無呼叫 | 無 | 無 | 無 | 無 | — | — | — | 停更；註解自陳 2020 方法論失效 | — | 無 | 無 | NOT VERIFIED | `FRED_LEI`；指令 V13 |
| B10／B | ISM 製造業 PMI | FRED `NAPM`、`ISPMANPMI` 已停更並自取數拔除（CLAUDE.md §2.3，2026-09-01）；現行走非 FRED 源 | MacroMicro／ISM World／DBnomics；後兩段備援走 FRED | `alternate.fetch_ism_pmi`（5 段備援） | `FAI["PMI"]`（含 `is_proxy` 旗標） | 有 | 無 | 無 | 月 | 指數；50 為榮枯線 | 視命中段；見 `proxy_note` | 全敗誠實回 `value=None`（不填 0） | 各段自有快取 | NOT VERIFIED（HTML 源易變動，檔內自陳） | 無 | REDESIGN | `alternate.fetch_ism_pmi`；`tests/test_dead_fred_pmi_series_removed.py`；`FRED_ISM_PMI`（僅供 `services/macro/_helpers.py` re-export） |
| B11／B | PMI 代理：費城聯儲製造業擴散指數 | `GACDFSA066MSFRBPHI` | FRED | `ffred`（`fetch_ism_pmi` 方案 6） | `FAI["PMI"]`，`is_proxy=True` | 僅前段全敗才用 | 無 | 無 | 月 | 擴散指數；以常數換算 PMI 刻度（常數檔自陳無出處，只能看方向） | 觀測日 | R | R | NOT VERIFIED | 無 | REDESIGN | `fred_series.PHILLY_FED_PMI_BASE`、`PHILLY_FED_TO_PMI_DIVISOR` |
| B12／B | PMI 代理：OECD 美國商業信心 | `BSCICP02USM460S` | FRED | `ffred`（方案 7） | `FAI["PMI"]`，`is_proxy=True` | 同 B11 | 無 | 無 | 月 | 值域約 98–102，非 PMI 刻度 | 觀測延遲較大；是否仍更新 NOT VERIFIED | R | R | NOT VERIFIED | 無 | NOT VERIFIED | `FRED_BSCICP02`；`us_indicators`（v19.404 註解） |
| B13／B | 製造業新訂單與存貨（拐點用） | `AMTMNO`、`MNFCTRIRSA` | FRED | `ffred`（n=60） | `turning_points`（`pmi_diff`） | `detect_turning_points` | 無 | 無 | 月 | 美元、比率 | 觀測日 | R | R | NOT VERIFIED | 無 | EXTRACT | `turning_points.py` |
| B14／B | 消費者信心（密大） | `UMCSENT` | FRED | `ffred` | `FAI["CONSUMER_CONF"]` | 有 | 無 | 無 | 月 | 指數 | 同 B4 | R | R | NOT VERIFIED（授權與更新狀態未驗） | 無 | EXTRACT | `FRED_UMCSENT` |
| B15／B | 初領失業金 | `ICSA` | FRED | `ffred`（n=312） | `FAI["JOBLESS"]`（值除以 10000 換萬人） | 有 | 無 | 無 | 週 | 人→萬人 | 觀測日為週六；CLAUDE.md §2.3 寫週 +3 天，研究組讀到的程式註解為 +5 天，兩說未對帳 | R；週頻無新值不判失敗 | R | NOT VERIFIED | 無 | EXTRACT | `FRED_ICSA` |
| B16／B | 續請失業金 | `CCSA` | FRED | `ffred`（n=312） | `FAI["CONT_CLAIMS"]` | 有 | 無 | 無 | 週 | 人→萬人 | 同 B15 | R | R | NOT VERIFIED | 無 | EXTRACT | `FRED_CCSA` |
| B17／B | 薩姆規則 | `SAHMREALTIME` | FRED | `ffred`（n=144；拐點 n=36） | `FAI["SAHM"]`；`turning_points` | 有 | 無 | 無 | 月 | pp；≥0.5 衰退（`SAHM_RECESSION_THRESHOLD`） | 「realtime」序列會隨 vintage 改值；本 repo 無 vintage 對照 | R | R | NOT VERIFIED | 無 | EXTRACT | `FRED_SAHM`；`FRED_SAHM_CURRENT` 只有常數 |
| B18／B | SLOOS 放貸標準 | `DRTSCILM` | FRED | `ffred`（n=80） | `FAI["SLOOS"]` | 有 | 無 | 無 | 季 | %淨比例 | 季首標記，發布約 30–45 天（`data_registry` 註解） | R | R | NOT VERIFIED | 無 | EXTRACT | `data_registry`（季頻 135／170 天註解） |
| B19／B | 新屋銷售 | `HSN1F` | FRED | `ffred` | `FAI["NEW_HOME"]` | 有 | 無 | 無 | 月 | 千戶 | 同 B4 | R | R | NOT VERIFIED | 無 | EXTRACT | `FRED_HSN1F` |
| B20／B | 建照核發 | `PERMIT` | FRED | `ffred` | `FAI["PERMIT_HOUSING"]` | 有 | 無 | 無 | 月 | 千戶 | 同 B4 | R | R | NOT VERIFIED | 無 | EXTRACT | `FRED_PERMIT` |
| B21／B | 5Y 通膨預期 | `T5YIE` | FRED | `ffred`（n=2500） | `FAI["INFL_EXP_5Y"]` | 有 | 無 | 無 | 日 | % | 觀測日 | R | R | NOT VERIFIED | 無 | EXTRACT | `FRED_T5YIE` |
| B22／B | 金融狀況與製造業就業（未用） | `NFCI`、`MANEMP`、`SAHMCURRENT` | FRED | 無呼叫 | 無 | 無 | 無 | 無 | — | — | — | 只有常數 | — | 無 | 無 | NOT VERIFIED | `shared/fred_series.py`；指令 V13 |

### 2.3 C 美債／利率／信用／流動性（13 列）

| ID／Domain | Indicator | Series/Ticker | Provider | L1 | L2 | Old UI | ui_v2 | ui_v3 | Frequency | Unit/Direction | Date evidence | Fetch behavior | Cache/Cooldown | Runtime evidence | Formal Gate | Reuse decision | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C1／C | 10Y 殖利率 | `DGS10` | FRED | `ffred`（Old n=2600；`RR` n=120）；`ffrede`（`mv` n=1500） | Old：作利差輸入、`RR._signal_yield_10y_shock`；`mv.fred_yield_domain_from_l1` | `LE`（無獨立卡片） | 真資料（domain `us10y`） | 真資料 | 日 | %（非價格） | `mv`：obs_date＝FRED 觀測日，明示不是公布日 | 缺 key→`MISSING_FRED_API_KEY` 且不打 L1；空表無原因→`EMPTY_WITHOUT_REASON`；失敗→系統錯誤加原文；假日 `.` 在 L1 丟棄、不補 | R；n 不同＝不同快取鍵；主機冷卻共用 | 間接：`META.fred_indicators` 2026-11-05；`ffrede` 路徑 NOT VERIFIED（`mv` 檔頭自陳 FRED 未真實連線，只用替身測形狀） | BL-0517 (2)，檔內自述為客戶裁示 C；我只核對 `-41` 為客戶裁示、`-42`／`-44` 為執行組讀法，未逐字核對全文 | REUSE | `mv.fred_yield_domain_from_l1`；`FRED_DGS10`；`tests/test_v2_tables_market_view.py` |
| C2／C | 2Y 殖利率 | `DGS2` | FRED | 同 C1 | 同 C1（domain `us2y`） | 同 C1 | 真資料 | 真資料 | 日 | % | 同 C1 | 同 C1 | 同 C1 | 同 C1 | 同 C1 | REUSE | `FRED_DGS2`；`mv` |
| C3／C | 3M 國庫券殖利率 | `DGS3MO` | FRED | `ffred`（n=2600） | `FAI`（僅作 10Y–3M 輸入） | `LE` | 無 | 無 | 日 | % | 觀測日 | R | R | 間接（`META`） | 無 | EXTRACT | `us_indicators`（`sp3m`）；`FRED_DGS3MO` |
| C4／C | 10Y–2Y 利差 | Old：自算 `DGS10−DGS2`；ui_v2 與拐點：`T10Y2Y` | FRED | Old：`math_utils.spread_series`；ui_v2：`ffv`；拐點：`ffred`（n=120／11000） | Old：`FAI["YIELD_10Y2Y"]`；ui_v2：`mi` 鍵 `term_spread_pct`；拐點：`turning_points` | 有（先月底 resample、ffill 後相減，月頻約 120 點，日期只到 `YYYY-MM`） | 有（日頻 vintage，`RATES_KEYS`） | 有（rates 區） | Old：月；ui_v2：日 | pp | ui_v2：每個版次一列，`release_date`＝vintage `realtime_start`，且首版等於查詢下界者不寫（防截斷） | 兩條路徑各有各的失敗語意 | 兩個快取鍵（vintage、觀測） | vintage 路徑 NOT VERIFIED（49 與函式 docstring 自陳未以真實 FRED 實測）；`tests/test_fred_vintage_l1.py` 等為替身測試 | v2 B 線已列（Q 系列，裁示文本未逐字核對） | REDESIGN | `fred_vintage.py`；`mi.INDICATOR_SPECS["term_spread_pct"]`；`math_utils.spread_series`；`tests/test_yield_10y3m_align.py` |
| C5／C | 10Y–3M 利差 | Old：自算 `DGS10−DGS3MO`；`T10Y3M` 只有常數與發布日對照 | FRED | Old：`spread_series`（月底法） | `FAI["YIELD_10Y3M"]`；`recession_probability` | 有 | 無 | 無 | Old：月 | pp | 同 C4 的 Old 側 | R | R | NOT VERIFIED；`T10Y3M` 常數沒有取數呼叫，只被 `data_registry` 用來查下次發布日 | 無 | EXTRACT | `FRED_T10Y3M`；`data_registry`；`tests/test_yield_10y3m_align.py` |
| C6／C | 聯邦基金利率 | `FEDFUNDS` | FRED | Old：`ffred`（n=144）；ui_v2：`ffv` | Old：`FAI["FED_RATE"]`；ui_v2：`mi` 鍵 `policy_rate_pct` | 有 | 有 | 有 | 月（月均） | % | ui_v2：vintage 逐版次 | 同 C4 的 ui_v2 側 | R | vintage NOT VERIFIED | 49 Q1 已狀態更新（未逐字核對） | REUSE | `mi.INDICATOR_SPECS["policy_rate_pct"]`；`fund_service.set_risk_free_rate`（只讀註解，未追注入點） |
| C7／C | 高收益債信用利差（OAS） | `BAMLH0A0HYM2` | FRED（ICE BofA 指數） | Old：`ffred`（n=2500；`RR` n=120；`UL` n=60）；ui_v2：`ffv` | Old：`FAI["HY_SPREAD"]`、`RR._signal_hy_oas_delta`；ui_v2：`credit_spread_pct` | 有 | 有 | 有 | 日 | FRED 單位 Percent；利差標 pp；`RR` 以 `(cur-prev)*100` 轉 bp | ui_v2：vintage；Old：觀測日 | R；多處各用不同 n＝多個快取項 | R | 間接（`META`）；歷史長度是否滿足 n=2500 NOT VERIFIED | 49 已列（未逐字核對） | REUSE | `risk_radar.py`；`us_liquidity_engine._hy_oas`；`mi.INDICATOR_SPECS["credit_spread_pct"]` |
| C8／C | M2（月，季調） | `M2SL` | FRED | `ffred`（n=144；`UL` n=24） | `FAI["M2"]`（YoY 自算）；`UL` | 有 | 無 | 無 | 月 | 十億美元→YoY % | 觀測日；發布約月後 7–30 天（CLAUDE.md §2.3） | R | R | 間接（`META`） | 無 | EXTRACT | `FRED_M2`；`us_liquidity_engine` |
| C9／C | M2（週，非季調） | `WM2NS` | FRED | `ffred`（n=520） | `FAI["M2_WEEKLY"]` | 有 | 無 | 無 | 週資料、月頻發布（`data_registry` 註解） | % YoY | 同 C8 | R | R | NOT VERIFIED | 無 | EXTRACT | `FRED_M2_WEEKLY` |
| C10／C | Fed 資產負債表 | `WALCL` | FRED | `ffred`（n=312；`UL` n=40／60） | `FAI["FED_BS"]`（有淨流動性時改用淨流動性 YoY，否則 WALCL YoY）；`UL._walcl` | 有 | 無 | 無 | 週（週三） | 百萬美元；`UL` 換兆（除以 1e6） | 觀測日 | R；淨流動性序列不足 53 週則降級 | R | 間接（`META`） | 無 | EXTRACT | `us_liquidity_engine.net_liquidity_series`；`tests/test_net_liquidity.py`、`tests/test_us_liquidity_engine.py` |
| C11／C | 隔夜逆回購（RRP） | `RRPONTSYD` | FRED | `ffred`（n=2000／260／60，各自快取鍵） | `UL._rrp`、`_net_liquidity`；`FAI`（淨流動性組件） | 有 | 無 | 無 | 日 | 十億美元（程式註解） | 與週三 WALCL 以 `merge_asof` backward、容差 7 天對齊 | R | R | NOT VERIFIED | 無 | EXTRACT | `us_liquidity_engine.py` |
| C12／C | TGA（財政部一般帳戶） | `WTREGEN` | FRED | `ffred`（n=312／40） | `net_liquidity_series`；`FAI["FED_BS"]` | 有 | 無 | 無 | 週（週三） | 百萬美元（常數註解） | 觀測日 | R；缺 TGA 則降級 WALCL | R | NOT VERIFIED | 無 | EXTRACT | `FRED_TGA`；`data_registry._FRED_SERIES_MAP["TGA"]` |
| C13／C | 淨流動性（衍生） | `WALCL−RRPONTSYD−WTREGEN` | FRED（三條） | 三次 `ffred` | `UL.net_liquidity_series`、`_net_liquidity`（Δ13 週） | 有 | 無 | 無 | 週 | 兆美元 | 依三個 series 對齊結果 | 任一缺→`_err`，不捏造 | R | NOT VERIFIED | 無（「淨流動性＝進股市的錢」是既有詮釋，客戶核准紀錄未查） | EXTRACT | `us_liquidity_engine.net_liquidity_series` |

### 2.4 D 美元與匯率（14 列）

| ID／Domain | Indicator | Series/Ticker | Provider | L1 | L2 | Old UI | ui_v2 | ui_v3 | Frequency | Unit/Direction | Date evidence | Fetch behavior | Cache/Cooldown | Runtime evidence | Formal Gate | Reuse decision | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1／D | USD/TWD | `USDTWD=X` | Yahoo；備援 open.er-api.com（僅 `get_latest_fx`） | `fyc`／`fyce`；`hot_money_repository.fetch_usdtwd_series`；`fx_and_main.get_latest_fx` | `mi.INDICATOR_SPECS["fx_twd_per_usd"]`（`write_if_fx_verified`）；`fx_regime_service`（只支援 USD）；`fund_invest_calc`／`fund_row`／`fund_service` | 熱錢卡、基金健診、研究的幣別換算；**Old UI 不受 `FX_OBS_DATE_RULE_VERIFIED` 管**，直接用最新值，無觀測日規則 | 閘門關：`mi` 不取數、不寫列；`ui_v2/alo` 缺匯率顯示資料未備 | `fact_fx` 資料未備；市值基準恆 `blocked`（G3） | 日 | 新臺幣／美元（TWD per USD） | E1174 FACT（2026-11-08 冬令探測）：日 K 時間戳為倫敦 00:00；新規則 518 列、週末 0；與 UTC 當日 00:00 小時價的中位絕對差 0.0034%；**不是已證實的收盤時間規則**；10-19 週一值不等於上週五收盤（-0.1264%）；假日映射（4 列錯映、5 日缺列）未解；條件 (a)–(e) 無一已完成 | `fyce` 以原文 error 旁路交出；Old `fetch_usdtwd_series`：空表當失敗（`_FetchFailed`）；`fx_regime_service` 失敗回 `{}` | `fyc` 10 分；`_FX_CACHE` 5 分且 positive-only；`st.cache_data` 10 分；主機冷卻；`get_latest_fx` 的 er-api 與 Frankfurter 有各自冷卻鍵 | E1174 run `42455423910`（`15538a57`）6 個代號 status ok；舊報告 `docs/evidence/probe_fx_obs_date/*.json.gz`（10-13、10-14）；Cloud 真機 NOT VERIFIED | **`FX_OBS_DATE_RULE_VERIFIED=False`**；客戶 2026-10-14 裁示（規則核准不等於閘門核准）；`DEC-2026-11-08-02`（D8 維持關閉）；49 §6.1 Q3、Q9；D83 §2 第 5 點 | REUSE（eligibility 不得因抓得到而放行） | `mi.FX_OBS_DATE_RULE_VERIFIED`、`INDICATOR_SPECS`、`rows_from_daily_close`、`prev_weekday`；`hot_money_repository.fetch_usdtwd_series`；`fx_and_main.get_latest_fx`；E1174 §0–§5；E1175 §1(1) |
| D2／D | USD/JPY（Yahoo） | `JPY=X`（鍵 `USDJPY`） | Yahoo | `fyc`（5y） | `FAI`（`_CROSS_RATES`） | `LE`→`FAI["USDJPY"]`（門檻 140／155 為 inline） | 無 | 無 | 日 | JPY per USD；高＝USD 強（`FAI` 註解一致） | 日期＝`s.index[-1]` 的 UTC 無時區日（夏令倫敦 D 日 00:00 的根會顯示成 D−1）；不在探測清單 | `len>=22` 否則該鍵無聲不產生 | Y | NOT VERIFIED | 無 | EXTRACT | `us_indicators`（`_CROSS_RATES`） |
| D3／D | USD/JPY（FRED 日頻） | `DEXJPUS` | FRED | `ffred` | `LQ.build_carry_unwind`（JPY／CHF 5 日升值%） | `LE`→`fetch_liquidity_factors` | 無 | 無 | 日 | JPY per USD（`FRED_JPY_USD` 註解）；`build_carry_unwind` 以下跌＝日圓升值處理 | 觀測日（非公布日） | R；200 但 `observations` 空→空表加 error 且照常快取 | R | NOT VERIFIED；不在 cron 的 `FRED_SERIES_IDS` | 無 | EXTRACT | `FRED_JPY_USD`；`LQ.build_carry_unwind` |
| D4／D | EUR/USD（Yahoo） | `EURUSD=X`（鍵 `EURUSD`） | Yahoo | `fyc`（5y） | `FAI`（同 D2） | `LE`→`FAI["EURUSD"]`（門檻 1.05／1.15 inline） | 無 | 無 | 日 | USD per EUR；`FAI` 對 EURUSD 以「高＝EUR 強」處理，與 USDJPY 的「高＝USD 強」方向相反，程式分支明確 | 同 D2 | 同 D2 | Y | NOT VERIFIED | 無 | EXTRACT | `us_indicators`（`_CROSS_RATES`） |
| D5／D | EUR/USD（FRED） | `DEXUSEU` | FRED | `ffred` | 只在 `get_latest_fx` 的 FRED 備援（`_FRED_FX_MAP[("EUR","USD")]`，模式 `inv`＝取倒數） | 無（`get_latest_fx` 的 production 呼叫端都傳 `<ccy>TWD=X`，TWD 幣對不進 FRED 分支） | 無 | 無 | 日 | FRED 序列為 USD per EUR；`get_latest_fx` 取倒數（約 0.926）。**INFERENCE：對 `EURUSD=X`，Yahoo 主路約 1.08，FRED 備援約 0.926，兩條路徑方向相反**；同函式的診斷函式 `diagnose_fx_sources` 卻不取倒數（第 9 節 V6） | 見左欄 | R | NOT VERIFIED | 無 | NOT VERIFIED | `fx_and_main.get_latest_fx`（`_FRED_FX_MAP`）、`diagnose_fx_sources`；`shared/fred_series.py::FRED_EUR_USD`；`tests/test_get_latest_fx_fred_fallback.py` |
| D6／D | USD/CNH（Yahoo） | `CNH=X`（鍵 `USDCNH`） | Yahoo | `fyc`（5y） | `FAI`（同 D2） | `LE`→`FAI["USDCNH"]` | 無 | 無 | 日 | CNH per USD | 同 D2 | 同 D2 | Y | NOT VERIFIED（探測的是 `CNHTWD=X`，不是 `CNH=X`） | 無 | EXTRACT | `us_indicators._CROSS_RATES` |
| D7／D | USD/CNY（FRED） | `DEXCHUS`（常數名 `FRED_CNH_USD`，註解 CNY per USD，CNH 代理） | FRED | `ffred` | `get_latest_fx` 備援（`("CNH","USD")`、`("CNY","USD")` 皆映此序列）；`data_registry` 頻率與發布日對映 | 同 D5 | 無 | 無 | 日 | CNY per USD；常數名寫 CNH、實為在岸 CNY | 同 D3 | R | R | NOT VERIFIED（`data_registry` 註解稱已生產驗證，找不到證據檔） | 無 | NOT VERIFIED | `FRED_CNH_USD`；`data_registry`（`USDCNY`） |
| D8／D | 廣義貿易加權美元指數 | `DTWEXBGS`（常數 `FRED_DXY`） | FRED | `ffred`；cron 自有抓取器 | `LQ.build_xccy_proxy`（20 日動能 z-score，標「代理、非真 XCCY basis」）；`FAI` 預熱 | `LE`→`fetch_liquidity_factors` | 無 | 無 | 日 | 指數點（基期 2006=100，**不是 ICE DXY**） | 觀測日 | R | R | 間接：`META.fred_indicators`（`DTWEXBGS` 在 cron 的 `FRED_SERIES_IDS`；逐 series 最新日 NOT VERIFIED，parquet 本機讀不開） | D83 §6：`DTWEXBGS` 不是 ICE DXY | EXTRACT（重用前須先改稱呼，見 D9） | `LQ.build_xccy_proxy`；`FRED_DXY`；`scripts/update_macro_history.py` |
| D9／D | 「美元指數 DXY」（Old UI 卡片） | `DX-Y.NYB` | Yahoo | `fyc`（5y） | `FAI["DXY"]`（月漲跌 ±1% 燈） | `LE`→`FAI` | 無 | 無 | 日 | 指數點；**與 D8 是兩條不同序列，repo 內都叫 DXY** | UTC 日；不在探測清單；是否即 ICE DXY、更新是否準時 NOT VERIFIED | `len>=22` 否則整張卡無聲不產生 | Y | NOT VERIFIED（`tests/test_macro_core.py` 只有替身值） | 無 | NOT VERIFIED | `us_indicators`（`DX-Y.NYB` 區塊）；`ui/tab6_manual.py` |
| D10／D | USD/CHF（FRED） | `DEXSZUS` | FRED | `ffred` | `LQ.build_carry_unwind`；`FAI` 預熱 | 同 D3 | 無 | 無 | 日 | CHF per USD | 同 D3 | R | R | NOT VERIFIED | 無 | EXTRACT | `FRED_CHF_USD`；`liquidity_engine.py` |
| D11／D | EUR/TWD | `EURTWD=X` | Yahoo | `fyce` | `mi.build_fx_indicator_table`（鍵 `fx_twd_per_eur`）；`get_latest_fx` | Old：基金幣別換算（不受閘門管） | 閘門關→pending；`ui_v2/alo` 缺匯率 | `fx_twd_per_eur` 無頁面 | 日 | TWD per EUR（與 `USDTWD=X` 同向、不取倒數） | E1174 FACT：EUR 日 K 與小時價系統差 +0.1324%；45 根日 K 的 \|close/open−1\| 大於 1%，其中 42 根為週一；10-26、11-02 兩根週一值對 UTC 00:00 小時價差 -3.13%、-2.88%；位移掃描最小在 k=0 但僅 0.1148%（n=17）→ **不支持由 USD 外推** | 同 D1 | 同 D1 | 同 D1：`EURTWD=X` status ok、523 根；證據只說異常需補證 | `FX_OBS_DATE_RULE_VERIFIED=False`；客戶 2026-10-14：EUR／JPY／CNY 未驗證完成前維持資料未備、不推估、不換來源；49 §6.1 Q9 | NOT VERIFIED | `mi.build_fx_indicator_table`、`fx_yahoo_ticker`；E1174 §4；E1175 §1(3) |
| D12／D | JPY/TWD | `JPYTWD=X` | Yahoo | `fyce` | 同 D11（`fx_twd_per_jpy`）；`services/health/*` 以 CV 處理量綱 | 同 D11 | 同 D11 | 無 | 日 | TWD per JPY（約 0.21） | E1174 FACT：日 K 與小時價系統差 -1.0788%（23 日全負）；位移掃描最小落在掃描邊界 k=+26（0.7827%）→ 不能判定；與 USD 序列的疑點未解 | 同 D1 | 同 D1 | 同 D1：status ok、523 根 | 同 D11 | NOT VERIFIED | 同 D11；E1174 §4 新疑點 2；E1175 §1(4) |
| D13／D | CNY／CNH 對 TWD | `CNYTWD=X`、`CNHTWD=X` | Yahoo | `fyce` | `mi.build_fx_indicator_table`（規則碼）；`fund_invest_calc` 註解：人民幣優先 `CNHTWD=X` | 同 D11（人民幣基金換算） | 同 D11 | 無 | 日 | TWD per CNY／CNH | E1174 FACT：`range=2y interval=1d` 僅回 **1 根**（時間戳＝`regularMarketTime`），四次取數皆 1 根；正式路徑 0 列（`FX_MIN_REFERENCE_VOTES=20`）；`CNH firstTradeDate=null` | 同 D1 | 同 D1 | 四次探測 status ok 但 `raw_bar_count=1`；**ok 不等於有歷史資料** | 同 D11；客戶明示不得換來源 | REDESIGN | E1174 §6；E1175 §1(7)；`mi.FX_MIN_REFERENCE_VOTES` |
| D14／D | 其他幣別對 TWD（GBP、AUD、ZAR 等基金計價幣別） | `<ISO>TWD=X` | Yahoo → open.er-api.com →（非 TWD 幣對才）FRED／Frankfurter | `get_latest_fx`（er-api 與 Frankfurter 直打 `requests`，`verify=False`，繞過 `fetch_url` 的統一 timeout 與 proxy 路徑） | `fund_row`、`fund_invest_calc.fx_rate_to_twd`、`fund_service`；`fx_regime_service` 只支援 USD | 基金換算（研究、健診、批次） | 無 | 無 | 日 | TWD per ccy（各幣別方向未逐一驗，僅 Yahoo 慣例） | **無觀測日**：`get_latest_fx` 只回 float，不帶 obs_date 或 fetched_at（INFERENCE，讀碼） | Yahoo 空→改試 er-api；全敗回 None（positive-only，不快取 None）；空與失敗不分；2026-10-10 裁示：不足 6 碼的幣對 fail closed | `_FX_CACHE` 5 分；er-api 與 Frankfurter 各自 `_sb_fx` 冷卻鍵 | NOT VERIFIED（備援 er-api、Frankfurter 無探測證據） | 不在 `FX_OBS_DATE_RULE_VERIFIED` 管轄（只管 `mi` 路徑） | NOT VERIFIED | `fx_and_main.get_latest_fx`；`fund_invest_calc.fx_rate_to_twd`；`fx_regime_service.SUPPORTED_FX` |

### 2.5 其他既有 FRED series（補充，非主表列）

這六列是對主表的交叉引用或主表以外的既有常數，不併入 61 列的計數：

| Series | 用途 | 是否有 production 呼叫 | Evidence |
|---|---|---|---|
| `DTWEXBGS` | 同 D8 | 有 | `liquidity_engine.py`、`FRED_DXY` |
| `DEXJPUS`、`DEXSZUS` | 同 D3、D10 | 有 | `liquidity_engine.build_carry_unwind` |
| `DEXCHUS`、`DEXUSEU` | 同 D7、D5（基金 FX 換算備援） | 有（僅備援分支） | `fx_and_main.py` |
| `VXVCLS` | VIX 備援第 6 層（3M vol，**不是** VIX 本身；CLAUDE.md §2.1 VIX 條 2026-10-19 更正：VIX 只有 Yahoo 一源） | 有（`risk_radar`） | `risk_radar.py` |
| `PCOPPUSDM` | 銅價 | 僅 cron 腳本 | `scripts/update_macro_history.py` |
| 中國四條 OECD series（`CHN_CLI`／`CHN_PMI`／`CHN_CPI`／`CHN_M2`） | 已於 v19.493 退役、常數已刪；字面 series id 仍殘留在 `data_registry` 的頻率與發布日對映 | 只剩發布日查詢殘留；是否仍進評估迴圈單組未驗 | `ui/helpers/io/data_registry.py`（指令 V15） |

## 3. Old UI → ui_v2 → ui_v3 → 共用資料層能力差距矩陣

### 3.0 三代 UI 掛載位置（FACT，會影響整張矩陣）

- **Old UI（正式 ①～⑤）**：`app.py` 的 `st.tabs` 前五格；① 市場總覽是 `ui/views/page_01_macro.py::render_market_overview`（不是 `ui/tab1_macro.py`，後者註明暫留作參考，不被 `app.py` 掛載）。
- **`app.py` 的 [新] ⑥～⑨**：來自 `ui/views/page_02..05`（Old 樹內的重寫版），**不是** `ui_v2`、也不是 `ui_v3`；沒有 [新] 市場總覽分頁。
- **`ui_v2`**：獨立 Streamlit app（`ui_v2/app_mkt.py` 為示範入口、`ui_v2/app_mkt_live.py` 走真資料）；主 app 沒有掛載。
- **`ui_v3`**：獨立 Preview App（`ui_v3/app_preview.py`，檔頭明示不可設為 Cloud main file）；目前只有一頁（`ui_v3/pages/mkt.py`）；是否為正式入口，研究組未確認。

### 3.1 能力差距矩陣（23 列）

缺口類型：**A**＝沒有來源；**B**＝沒有 UI 接線；**C**＝沒有資料契約；**D**＝正式 Gate 未核准；**OK**＝該層無缺口。

| # | Capability | Old UI path（①） | ui_v2 | ui_v3 | 共用層（L1／L2） | 缺口 | Evidence |
|---|---|---|---|---|---|---|---|
| 1 | S&P 500 價格序列 | 無價格卡；`RR`、`turning_points` 內部抓 `^GSPC` | 接（`mv` domain `sp500`；fixtures 另有 mock） | 接（Primary 比較圖） | L1 `fyc`；L2 `mv.sp500_domain_from_l1` | OK（5y 日 K、無首次發布概念） | `risk_radar.py`、`turning_points.py`、`mv.SP500_TICKER`；V3 |
| 2 | NASDAQ | 無 | 資料未備 | 缺口 | 無 | **A** | `mv._MISSING_DOMAINS`；V4 |
| 3 | MSCI World／MSCI EM／ACWI | 無 | 資料未備 | 缺口 | 無 | **A** | `mv._MISSING_DOMAINS`；V4 |
| 4 | 歐日股市（`^N225`、`^HSI` 等） | 只在 `RR` 的風險分項 | 無 | 無 | L1 可抓；L2 無 domain、無契約 | **C** | `risk_radar.py` |
| 5 | VIX | 有（`FAI`／`RR`／`LQ`） | 接（`vol_index` 與 `mv`） | 接 | L1 `fyc`；L2 `mi`、`mv` | OK（有重複抓取，見 3.3） | `us_indicators.py`；`mi.INDICATOR_SPECS` |
| 6 | 美債 10Y／2Y | 有（FRED 批次） | 接（觀測日，非公布日） | 接 | L1 `ffred`／`ffrede` | OK；若監控要 `release_date` 則為 **C** | `mv.fred_yield_domain_from_l1` |
| 7 | 殖利率差 T10Y2Y | 有（自算或 `ffred`） | 接（vintage 公布日） | 讀 B 線 table | L1 `ffv` | OK（但與 Old 兩法並存，見 C4） | `mi.INDICATOR_SPECS["term_spread_pct"]` |
| 8 | HY 信用利差 | 有 | 接 | 同上 | 同上 | OK | `INDICATOR_SPECS["credit_spread_pct"]` |
| 9 | 聯邦基金利率 | 有 | 接 | 同上 | 同上 | OK | `INDICATOR_SPECS["policy_rate_pct"]` |
| 10 | CPI／UNRATE／PAYEMS／CFNAI | 有 | **無**（`INDICATOR_SPECS` 只有 7 鍵） | 無 | L1 可用；`FRED_*` 常數存在 | **B／C** | `us_indicators.py`；`INDICATOR_SPECS` |
| 11 | 流動性：WALCL／M2SL／RRPONTSYD | 有（`UL`） | 無 | 無 | L1 可用 | **B／C** | `us_indicators.py` 批次清單 |
| 12 | 美元廣義指數 `DTWEXBGS` | 有（`LQ`） | 無 | 無 | L1 可用 | **B／C**（不是 ICE DXY；Old UI 另有 `DX-Y.NYB`） | `FRED_DXY`；`us_indicators.py` |
| 13 | USD/TWD | 有（`get_latest_fx`、`fetch_usdtwd_series`、`fx_regime`） | 契約有但**閘門關**：不取數 | 讀 table，必為 pending | L1 僅在閘門開時被呼叫 | **D** | `mi.FX_OBS_DATE_RULE_VERIFIED` |
| 14 | 其他幣別（EUR／JPY／CNH、`DEXJPUS`、`DEXUSEU`） | 有（cross-rate、FRED、`fx_and_main`） | `build_fx_indicator_table`（同閘門） | 無 | L1 可用 | **D**＋**C** | `mi.build_fx_indicator_table`；`_CROSS_RATES` |
| 15 | TAIEX（邊界） | 熱錢與 TW 區塊 | 接 | 接 | L1 同 | OK | `mv.taiex_domain_from_l1` |
| 16 | 台灣景氣燈號與領先指標（FinMind） | 有 | `leading_index`／`coincident_index` 契約 pending（無公布日） | 讀 table，pending | L1 有；L2 只標 pending | **C** | `INDICATOR_SPECS`、`PENDING_NDC_NO_RELEASE_DATE` |
| 17 | ISM PMI（5 段備援） | 有 | 無 | 無 | L1 `alternate.fetch_ism_pmi` | **B／C**（多源爬蟲、授權與契約未定） | `us_indicators.py`（PMI 段） |
| 18 | 風險雷達（VIX＋SPX 200DMA＋亞股） | 有（`RR`） | 無 | 無 | L2 `risk_radar` | **B**；含判斷語意故亦屬 **D** | `risk_radar.detect_risk_radar` |
| 19 | 新聞情緒 | 灰態 | 無 | 無 | L1 `news_repository` | **B**；D83 範圍外 | `page_01_macro._card_news` |
| 20 | 逐指標資料健康度 | 有（session 內 `data_registry`，頻率表加 FRED next_release_date） | 無對應（只有 `fetch_log` 以 source_tier 分類） | 無（`shell_status` 只有總覽層） | L2 無；registry 存在 `st.session_state` | **C** | `data_registry.py`；`ui_v3/adapters/shell_status.py` |
| 21 | 來源冷卻與退避狀態 | 無畫面（只有一處 caption） | 設定頁以 `cooldowns` 顯示重新取數停用原因 | 無 | L0 `infra/source_backoff.py`（主機粒度、行程記憶體）；L1 `v2_source_status.cooling_sources` | **C** | `infra/source_backoff.py`；`get_backoff_state` |
| 22 | 更新資料與連線診斷 | 有（sidebar、`tab5_data_guard` ping） | 重新取數只寫記憶體 `RuntimeFetchStore` | `REFRESH_NOT_WIRED` | — | ui_v3 為 **B** | `shell_status.py`；`settings_store.RuntimeFetchStore` |
| 23 | 事件日曆與發布時刻 | 只有 FRED `next_release_date` 動態查詢 | 無 | 無 | L1 `fred_get_next_release_date` | **A／C**（D83 §7 屬未來候選）；`FOMC` 字樣是否有取數來源研究組未查 | `data_registry.py`（`_fred_next_rel`） |

### 3.2 補充

- `ui_v2/mkt/fixtures.py` 是 mock，只供示範入口 `app_mkt.py` 使用；`app_mkt_live.py` 走 `source.load_live()`；`ui_v3` preview 守衛禁止 import `ui_v3.fixtures`（檔頭註）。
- Old UI 的 `FAI` 對各指標「長度不足就無聲不建鍵」，缺口靠 `EXPECTED_INDICATOR_KEYS` 差集在診斷頁補顯示。

### 3.3 重複抓取與重複快取

Yahoo 與 FRED 的**傳輸實作各只有一份**（`fyc`、`ffred`，指令 V22）；重複的是同一 ticker 或 series 以**不同引數形狀**呼叫，`@_ttl_cache` 的快取鍵是 `(args, sorted kwargs)`（我讀了 `infra/cache.py::_ttl_cache` 的實作確認，**FACT**），因此位置參數與關鍵字參數的寫法不同就是不同快取鍵，多次打同一上游。

| 資料 | 呼叫點與引數形狀 | 說明 |
|---|---|---|
| `^VIX` | `fund_service`（`("^VIX","1y")`）；`liquidity_engine`（`("^VIX","5y")`）；`us_indicators`（`_yf_iso("^VIX","5y")`，經 `_yf_s`）；`risk_radar`（`range_="6mo"`，同一檔兩處同鍵）；`mi`（預設 2y）；`mv`（5y） | 至少 5 種不同引數形狀＝至少 5 個快取項；`mv` 檔頭自述其 VIX 呼叫與 B 線 `vol_index` 刻意不同簽名 |
| `^GSPC` | `risk_radar`（`range_="1y"`）；`turning_points`（`range_` 變數）；`mv`（5y） | 3 套 |
| `DGS10`、`DGS2` | Old：批次 n=2600；ui_v2：`ffrede` n=1500 | n 不同＝快取鍵不同 |
| `T10Y2Y`、`BAMLH0A0HYM2`、`FEDFUNDS` | Old：`ffred`；ui_v2：`ffv`（vintage，不同請求參數） | 同 series 兩類請求，不能互相共用 |
| `USDTWD=X` | `hot_money_repository`；`get_latest_fx`；`fund_service`；ui_v2 `mi`（閘門關，不打） | 若閘門日後開啟會再多一套 |
| `<ISO>TWD=X` | `fund_row`、`ui/helpers/fund/checkup.py`、`fund_service`；ui_v2 `build_fx_indicator_table`（閘門關） | 基金換匯路徑與市場監控路徑並存 |
| 取數架構 | Old：`FAI` 一次抓約 26 條 FRED 與 yfinance 池；ui_v2：`mi` 與 `mv` 連續兩個 builder 打同主機 | 兩個 L2 builder 各自組裝；主機冷卻共用，所以一次 429 會讓同主機所有代號一起被擋 |

「只有這些呼叫點」是單組未驗：掃不到動態組字串，也掃不到經 shim（`fund_fetcher`、`macro_repository`）的間接呼叫。

## 4. REUSE／EXTRACT／REDESIGN／NOT VERIFIED 分類

### 4.1 分類規則與彙整調整

| 分類 | 定義（本報告使用） |
|---|---|
| **REUSE** | New UI2（`ui_v2`／`ui_v3`）已有 L2 接線與測試，共用 L1／L2 可直接重用；仍要看 Eligibility |
| **EXTRACT** | L1 現成，但 L2 的取數組裝、換算或語意埋在 Old UI（`FAI`、`RR`、`LQ`、`UL`）內，或 New UI2 尚無 domain 與契約；需要從 Old 路徑抽出或新建 domain |
| **REDESIGN** | 現有取法或契約不足以滿足需求（無來源、取法拿不到歷史、同名兩法並存、代理值語意未核定）；需要另行設計，其中涉及新來源者屬 Stop Gate |
| **NOT VERIFIED** | 缺少判定所需的證據，無法歸入前三類 |

**彙整調整（FACT：我重數並對齊界線後的結果）**：研究組 R2 把「只有 Old UI 路徑、New UI2 沒有 L2」的 12 列標為 REUSE（B14–B21、C3、C9、C11、C12），而 R1 對同形狀的 A8–A10、D3、D8、D10 標為 EXTRACT。為了同一條規則適用全表，本報告把這 12 列改為 **EXTRACT**。這是分類界線的調整，不是新事實；兩組原標籤仍可由第 2 節各表與研究組計數追溯。

**計數（以第 2 節 61 列的最後一欄重數；本報告自行重數，非兩份報告相加）**

| 分類 | 列數 | 成員 |
|---|---|---|
| REUSE | **8** | A1、A3、A11、D1、C1、C2、C6、C7 |
| EXTRACT | **31** | A8、A9、A10、D2、D3、D4、D6、D8、D10；B1、B2、B4、B5、B8、B13、B14、B15、B16、B17、B18、B19、B20、B21；C3、C5、C8、C9、C10、C11、C12、C13 |
| REDESIGN | **8** | A2、A4、A5、A6、D13、B10、B11、C4 |
| NOT VERIFIED | **14** | A7、A12、D5、D7、D9、D11、D12、D14、B3、B6、B7、B9、B12、B22 |
| 合計 | **61** | A 12＋B 22＋C 13＋D 14 |

### 4.2 REUSE（8）

| ID | 為何 | 還缺哪一個最小驗證 |
|---|---|---|
| A1 S&P 500 | L1、L2、`ui_v2`、`ui_v3` 都已接線並有測試 | `^GSPC` 的時區字串與時間戳樣態沒有證據（要補須另行授權唯讀取數；本報告不推薦） |
| A3 VIX | 唯一有真實探測證據的非匯率指標 | E1174 已標 NOT RUN 的 VIX 值對時刻（小時 K）對照 |
| A11 TAIEX | 有客戶明文裁示；邊界項，僅供對照 | 同 A1 的日期證據缺口 |
| D1 USD/TWD | L1 與規則碼現成 | **不是缺驗證，而是閘門關**：E1175 M1-a 為離線重算既有報告（不新增取數）；閘門決定屬客戶／總管 |
| C1 DGS10、C2 DGS2 | `mv` 已轉換並有 `tests/test_v2_tables_market_view.py` | 首次部署是否出現取數失敗或空序列（FRED 對共用 L1 路徑的真實連線證據為零） |
| C6 FEDFUNDS、C7 HY OAS | `ui_v2` B 線已接，走 vintage | vintage 路徑 NOT VERIFIED；C7 另需確認歷史長度是否滿足 Old UI 的 n=2500 假設 |

### 4.3 EXTRACT（31）

| 組 | 成員 | 為何 | 還缺哪一個最小驗證 |
|---|---|---|---|
| 亞股與費半 | A8、A9、A10 | L1 現成；L2 是 `RR` 內的位置式末二筆報酬，兩市休市日不同，**不得沿用** | 新 domain 改走 `rows_from_daily_close` 的設計；時區與時間戳證據缺 |
| 美元與匯率（FRED／Yahoo） | D2、D3、D4、D6、D8、D10 | L1 現成；方向語意（USD/JPY 為 JPY per USD、EUR/USD 為 USD per EUR）須先決定；D8 常數名 `FRED_DXY` 易與 D9 混淆 | 先決定方向語意與稱呼（第 8 節 G3）；日期證據缺 |
| 總經月頻（有發布日需求者） | B1、B2、B4、B5、B8、B13、B17 | L1 單呼叫即可；YoY、tier、拐點邏輯埋在 `FAI`（2,000 餘行單檔）或 `turning_points`；會修正的 series 在本 repo 只有觀測日、沒有首版值 | 以替身餵 `ffred` 鎖 YoY 數值（現有 `test_macro_*` 是否已鎖，未逐檔確認）；若要顯示公布日須走 vintage，且 vintage 路徑 NOT VERIFIED |
| 總經其他 | B14、B15、B16、B18、B19、B20、B21 | 同上；B15 的發布延遲說法（+3 天與 +5 天）未對帳 | 發布延遲說法的對帳 |
| 利率與流動性 | C3、C5、C8、C9、C10、C11、C12、C13 | `net_liquidity_series` 是純函式、可獨立搬出；C5 只有 Old 自算版（月底法），`T10Y3M` 沒有取數 | C5 的月底法與日頻語意須與 C4 一併定義（第 5 節風險 3）；淨流動性的詮釋是否獲客戶核准未查 |

### 4.4 REDESIGN（8）

| ID | 為何 | 還缺哪一個最小驗證 |
|---|---|---|
| A2、A4、A5、A6 | production 沒有任何來源；新來源屬 Stop Gate「新資料來源」 | 客戶先裁示是否需要、再做來源可得性盤點；本報告不提議來源 |
| D13 CNY／CNH | 現行 Yahoo 取法只拿到 1 根，改 `range` 或 `interval` 是改探測設定、換源是 Stop Gate | E1175 M7-a／b（離線與設定變更，皆須授權） |
| B10 ISM PMI | 非 FRED 的 HTML 源、代理值語意 | 逐段確認 `is_proxy` 於 UI 可見；各源授權與穩定性未查 |
| B11 費城聯儲代理 | 換算常數 3.0 無出處，違反反捏造原則，不可當水準值 | 常數出處或改為只看方向的設計 |
| C4 10Y–2Y | 同名兩法（Old 月底、ui_v2 日頻 vintage），觸 PROJECT_RULES 13.3 Cross-View Consistency | 擇一為正式定義；同日兩路徑對帳 |

### 4.5 NOT VERIFIED（14）

| ID | 為何 | 還缺哪一個最小驗證 |
|---|---|---|
| A7 | Yahoo 空表與已停供無法區分，證據只有註解口述 | `^VIX3M`、`^MOVE` 是否回 null 與時間戳（須授權的唯讀取數） |
| A12 | ETF 只供基準與廣度，與 NASDAQ／MSCI 缺口無關，不得充數 | 無，除非客戶把它納入範圍 |
| D5、D7 | 備援方向定義衝突（D5）、名稱與實際不符且「已生產驗證」註解無證據檔（D7） | 以官方定義加實值各對一點；並問客戶這條備援保留或刪除 |
| D9 | 序列身分與「DXY」稱呼未驗 | 與官方收盤對一點，並決定 New UI2 採用 D9 或 D8 |
| D11、D12 | 週一異常與水位差成因未明；不得由 USD 外推 | E1175 M3-a、M4-a／b（離線描述性分析） |
| D14 | 備援 er-api 與 Frankfurter 無探測證據；Old 換算不帶觀測日 | 先盤點 Old 換算覆蓋的幣別與是否帶日期 |
| B3、B6、B7、B22 | 沒有取數實作（B7、B22 只有常數） | 新增 L1 呼叫屬新資料能力，須先裁示範圍 |
| B9 | 停更（USSLIND），不得復活 | 若需 LEI 須另選有授權的來源 |
| B12 | OECD 序列是否仍在更新未驗 | 實測最後觀測日（須授權） |

## 5. 日期、錯誤、快取、FX、正式 Gate 風險

1. **FX 閘門仍關，且「抓得到」與「可准入」必須分開。** `FX_OBS_DATE_RULE_VERIFIED=False`（`services/v2_tables/market_indicator.py`，V1）；E1174 §0 結論 7「是否足以支持開閘決策：否」；E1175 七項缺口無一補齊。`DEC-2026-11-08-02` 維持 D8 關閉。D83 規劃的 Sheet 的「Fetch 成功」欄位**不得**被讀成 eligibility。E1175 記載冬令錯位窗口約 2026-11-24（上限約 11-26），且 11-08 探測報告只在 `probe/fx-obs-date-results` 分支、未存 main；本報告只轉述，**不推薦**任何補跑。
2. **`^GSPC`、`^TWII` 的日期證據是空白。** `mi.rows_from_daily_close` 對它們套用與 VIX、匯率同一條規則，但探測清單（`scripts/probe_fx_obs_date.py` 的 `DEFAULT_TICKERS`）只有 USDTWD、`^VIX`、EURTWD、JPYTWD、CNYTWD、CNHTWD（V19）。**INFERENCE**：未收盤界線取 max(UTC 日, 當地日)，美股收盤（16:00 ET）到 UTC 午夜之間約 4～5 小時，當日收盤可能被判未收盤而不寫（未跑）。
3. **同名指標兩套算法與粒度。** Old UI 的 10Y–2Y、10Y–3M 是月底 resample 加 ffill 後相減的月頻約 120 點；`ui_v2` 是 FRED `T10Y2Y` 日頻 vintage。兩者值與日期都可能不同；10Y–3M 只有 Old 自算版，`T10Y3M` 只有常數與發布日對照（V13）。
4. **美元方向與稱呼。** (a) `DTWEXBGS`（D8）不是 ICE DXY（D83 §6）；Old UI 的「美元指數 DXY」卡取自 Yahoo `DX-Y.NYB`（D9），`LQ` 的 DXY proxy 取自 `DTWEXBGS`，repo 內兩者都叫 DXY（V9、V25）。(b) USD/JPY（D2、D3）是 JPY per USD，EUR/USD（D4、D5）是 USD per EUR，`FAI` 對兩者的「高＝強」分支方向相反，重用前須在契約中寫明。(c) `get_latest_fx` 的 FRED 備援對 `EURUSD=X` 取 `1/DEXUSEU`，與 Yahoo 主路方向相反；同檔 `diagnose_fx_sources` 的 FRED 分支卻直接回原值（V6）。**目前**沒有 production 呼叫端會讓 TWD 幣對進入這個分支（V22，單組未驗），所以屬潛在風險，不是現行錯誤。
5. **Yahoo 回空與失敗。** New UI2：`fyc` 以 `.attrs["fetch_error"]` 旁路交出原文，`mv`／`mi` 轉成系統錯誤，不是資料未備；但研究組讀到 `ui_v3` adapter 把 `reason` 丟掉、只剩失敗與原因碼，使用者看不到「200 全 null」與「429」的差別（INFERENCE）。Old UI：`RR` 的 `s.empty` 一律 `_empty(...)`，`FAI` 長度不足無聲不建鍵；`RR` 註解自述 Yahoo `^CPC`、`^VIX3M` 曾回空，證明空有時是該 ticker 已不存在。
6. **FRED 發布日與修正版追溯只涵蓋 3 條，且未實測。** `fetch_fred_vintages`（`output_type=1`）在 production 只被 `mi.build_market_indicator_table` 對 `BAMLH0A0HYM2`、`T10Y2Y`、`FEDFUNDS` 三鍵呼叫（V12），其餘 FRED 指標只有觀測日；另外 `fetch_fred` 沒有帶 real-time 參數，`realtime_start` 依 FRED 官方預設是查詢當天，但 `fetch_fred` 自己的 docstring 仍寫它約等於真實 publish 時間，與 `fred_vintage.py`、`mv` 檔頭的說法矛盾（研究組讀碼所得，我未逐行複核該 docstring）。
7. **重複抓取。** `^VIX`、`^GSPC`、FRED 殖利率以不同引數形狀各自快取（第 3.3 節）；多打幾次上游屬讀碼推論，**未**量測請求數。
8. **主機級冷卻是單點。** Yahoo 所有 ticker 共用 `query1.finance.yahoo.com` 一個退避鍵；`mv` 一次多打 3 個 Yahoo 鍵、2 個 FRED 鍵，一旦 429（冷卻 1800 秒）S&P、TAIEX、匯率會一起消失；`phase1_hosts()`、`source_cooldowns()` 不涵蓋 `<ISO>TWD=X`（`mi.build_fx_indicator_table` docstring 自陳，閘門打開前須處理）。
9. **常數存在但無取數。** `FRED_GDPNOW`、`FRED_LEI`、`FRED_NFCI`、`FRED_PAYEMS_MANEMP`、`FRED_SAHM_CURRENT` 在除定義檔外沒有任何 production 引用；`FRED_T10Y3M` 只被 `data_registry` 引用；`FRED_ISM_PMI` 只剩 re-export（V13）。PCE、GDP、核心 CPI 連常數都沒有（V14）。
10. **`ai_service._key_inds` 的 SP500 鍵。** `services/ai_service.py` 的 `_key_inds` 含 `"SP500"`，`FAI` 產出鍵中沒有 `SP500`（V8），所以 AI 摘要永遠少這一項且不報錯；研究組同時宣稱 `PMI` 也缺，**我實查不成立**（`FAI` 有 `R["PMI"]`），見第 9 節。
11. **`DEXCHUS` 與已退役的中國 OECD series** 的命名或殘留風險見 D7 與 2.5 表；`data_registry` 的 `CHN_*` 殘留是否仍會對已退役 series 發 `fred_get_next_release_date` 請求，單組未驗。
12. **Cloud 與真機。** `ui_v2`、`ui_v3` 的 live 真資料（Yahoo、FRED）從未在 Cloud 或真機驗過（HANDOFF：Preview 不等於 Cloud；`mv` 檔頭自述 FRED 真實連線未驗）；`data_cache/*.parquet` 本機缺 pyarrow，逐 series 最後觀測日讀不到。

## 6. 新監控 Sheet 四分頁準備度

**前提**：四個分頁（`catalog_status`、`fetch_events`、`coverage_summary`、`data_gaps`）是 `docs/v2/83` §4 的**候選**，名稱、欄位、Schema 都未核准、未升格；本節只評「現有機器證據能否供應」。**本報告不宣稱任何新 Sheet 可運作。**

### 6.1 既有可用原料

- **L1 `*_with_error`**（`fyce`、`ffrede`、`ffv`）：交回 `(資料, 失敗原文或 None)`；資料 attrs 含 `source`、`fetched_at`（FRED 另有 `realtime_start`）。
- **L2 `mi.build_market_indicator_table`**：回 `{rows, errors, pending, skipped, fetched}`，逐 `indicator_key` 帶失敗原文、pending 原因碼與取回列數；範圍只有 `INDICATOR_SPECS` 的 7 鍵（`vol_index`、`fx_twd_per_usd`、`credit_spread_pct`、`term_spread_pct`、`policy_rate_pct`、`leading_index`、`coincident_index`；V16）。
- **L2 `mv.build_market_view`**：12 個 domain 的 `status`、`reason_code`、`source`、`fetched_at`、`obs_date`（`DOMAIN_ORDER` 12 個，V16）。
- **L0 `infra/source_backoff.py`**：**主機粒度、行程記憶體**，無逐指標、無持久化；冷卻秒數 SSOT 在 `shared/backoff_policy.py`。
- **`shared/ttls.py`** 沒有逐指標的 expected-frequency 或 stale 門檻；逐指標頻率表只存在 Old UI `ui/helpers/io/data_registry.py` 的區域變數 `_FREQ`，L2 不可引用。
- **`shared/ui_semantics/rules.py`** 的核准字彙沒有 D83 §5 的 Fetch／Validation／Eligibility 英文詞（D83 自述不是新增正式狀態詞；我未逐 key 比對）。

### 6.2 逐分頁

| 分頁 | 現有機器證據可供應 | 需新契約 | 不可取得或不可合法使用 | 與既有 SETTINGS 重疊 | 待設計 |
|---|---|---|---|---|---|
| `catalog_status` | `indicator_key`（僅 7 鍵加 `mv` 12 domain）；provider、series id、`value_unit`（`INDICATOR_SPECS`）；`obs_date`、`fetched_at`；`fetch_state` 的部分（`errors`／`pending`／`fetched`、domain `status` 加 `reason_code`）；`gate_ref`（可由常數推，非 Sheet 值） | `region`、`topic`、`display_name`（無 catalog 常數）；`frequency`（只在 Old UI 區域變數）；`quote_direction`；`source_contract_ref`；`validation_state`、`eligibility_state`；`last_success_at`（沒有程式追蹤「最近成功」，`fetched_at` 在快取命中時是舊值）；FRED 殖利率沒有 `release_date` | NASDAQ、MSCI World、MSCI EM 無來源（A）；USD/TWD 與其他幣別被閘門（D）擋下，Sheet 顯示成功不能開閘；NDC 兩鍵無公布日；`DTWEXBGS` 不是 ICE DXY | **部分重疊**：`market_indicator` 分頁（8 欄，主鍵 key＋obs_date＋release_date）已存正式採用的值，`catalog_status` 是一指標一列最新狀態，粒度不同；重疊在 key 清單與 pending 邏輯 | `indicator_key` 命名空間；last_success 由誰算、存哪；upsert 或 append；與 `INDICATOR_SPECS` 的單一來源（Sheet 不得反向驅動 Gate，D83 §3） |
| `fetch_events` | `FETCH_LOG_SPEC` **只有 7 欄**：`log_id`、`source_tier`、`started_at`、`finished_at`、`outcome`、`row_count`、`message`（`repositories/settings_sheet_repository.py`，V2）；可對應開始與結束時間、attempt 狀態（`outcome` 只有 `ok`／`failed`）、`row_count`、已遮蔽的訊息 | `indicator_key`、`provider`（`source_tier` 值域只有 淨值／配息／市場指標／其他）；未嘗試／空／解析失敗／來源不可用的細分；`error_code`；`provenance_ref` | 「成功但空」與「失敗」在 `fetch_log` 層無法分辨（寫進去都是 failed） | **高度重疊**：`fetch_log` 與 `fetch_log_open` 已是 append-only 取數紀錄（50 §5.3）；D83 §4.2 自陳施工前需定義 lineage、去重與成本 | 寫入責任（見 6.3）；`event_id` 組法；去重；寫入頻率與配額估算需重做（50 §9 以每次取數 3 次寫入估） |
| `coverage_summary` | 純投影：由 `catalog_status` 的狀態計數得出；程式碼目前沒有任何「母集合」定義；`DOMAIN_ORDER`（12）與 `INDICATOR_SPECS`（7）是兩份互不對齊的清單（只有 `vol_index` 與 vix 兩邊都有） | 正式母集合與適用條件（D83 §4.3 嚴禁無分母算百分比）；群組歸屬 | 分母未核准前不得算任何涵蓋率；`BL-0545`（Active Sheet 覆蓋率）NOT VERIFIED，不得混用 | 與 Sheet 無重疊；與設定頁資料健康度（80 §16.2）的 UI 呈現層重疊 | 可能根本不必落 Sheet，改為 `catalog_status` 的衍生視圖，避免重複儲存（13.4 Anti-Bloat 第 7 點） |
| `data_gaps` | 機器可推導的缺口：`mv._MISSING_DOMAINS`（`no_official_source` 等）、`mi` 的 `PENDING_*`、FX 閘門；`gap_type` 可對應這些代碼 | `owner`、`next_action`、`decision_ref`、`verification_status`、`evidence`、`blocker` 皆為人為治理欄位，機器不能產生 | 不得由推論把缺口寫成已修復（D83 §4.4）；待驗不得改寫為不重要 | 與 Sheet 無重疊，但與 `docs/BACKLOG.md`、`docs/v2/82` 的缺口清單**內容重疊**（同一缺口兩處維護，違反 13.4 第 7 點） | 該表是 GitHub 契約的唯讀投影或人工維護表；若人工維護，如何避免與 BACKLOG 漂移 |

### 6.3 共同限制

- **與 `SETTINGS_SHEET_ID` 的關係**：既有四表（`user_setting_log`、`market_indicator`、`fetch_log`、`fetch_log_open`）使用 `SETTINGS_SHEET_ID`（`get_secret`，無預設，缺值 fail loud）；D83 的方案 B 是**獨立** Sheet，**不得**修改既有 ID、Active Sheet、`POLICY_SHEET_ID`、`NAV_SHEET_ID`、OAuth 或 Secret。
- **既有 `fetch_log` 不能提供逐指標健康度（讀碼確認）**：(1) 欄位只有 7 欄且沒有 indicator、provider、series id；(2) `source_tier` 值域四個，一次「重新取數」只寫**一列**「市場指標」（`settings_store.py` 的 `open_fetch_log(mi.SOURCE_TIER)`，V10），涵蓋 vix 與三個 FRED 鍵，混成單一 outcome；(3) 逐鍵失敗原文只存在 L2 回傳的 `errors{鍵:原文}` 與 `message` 字串（人讀文字，非結構欄）；(4) 寫入點：L1 的 `close_fetch_log` 休眠，New UI2 第一階段只寫 session 記憶體（`RuntimeFetchStore`）；(5) `WIRED_TABLES`、`WIRED_TIERS` 只是常數清單，不等於 production 有寫入。
- **writer 受約束**：`is_read_only()` **恆為 True**（客戶 2026-10-26 裁示 J-6：New UI2 第一階段全唯讀、Sheet 零寫入；V11）；L1 寫入函式（`open_fetch_log`、`close_fetch_log`、`append_market_indicator`、`save_user_setting`）存在但休眠；守衛為 `tests/ui_v2/test_readonly_write_surface_guard.py::test_no_settings_sheet_l1_write_calls`（我讀了 docstring 引用，**未跑測試**）。因此**今天沒有任何會把取數事件寫進 Sheet 的 production 程式路徑**（單組讀碼，指令見第 9 節 V10／附錄）。任何新監控 Sheet 的寫入都需要客戶另行裁示，不能沿用既有授權。
- **機密與隱私**：D83 §2 要求新表**不得**讀寫私人持倉、密碼、Token；現有 `services/v2_tables/masking.mask_message` 可沿用；新表欄位候選清單沒有持倉欄位（以設計文件為準，未驗實作）。
- **分層**：資料（取回的值與其出處）、驗證（日期、單位、方向是否被獨立證據支持）、AI（只吃正式、可追溯資料，不得寫回 canonical data）必須分層；Sheet 是狀態 registry，不是市場價格的來源，**也不得人工把 Gate 改成已核准**（D83 §3）。
- **冷卻與去重**：`source_backoff` 為行程記憶體，Streamlit 重啟即清；若要跨 session 的冷卻紀錄需新持久化；去重可沿用或複製 `settings_sheet_repository` 的寫入前讀主鍵做法。
- **其他待裁**：權限、新 secret 鍵命名、分頁 header 鎖定、保留政策（D83 §8-2）；三層狀態英文詞須先走字彙 Gate。

## 7. 三方案比較

這三個方案是**實作路線**，與 `docs/v2/83` 第 3 節的「方案 A／B／C」（擴充既有 Sheet／獨立 Sheet／Sheet 驅動來源）是不同維度，請勿混讀。

| 維度 | 方案 A：直接重用符合正式契約的共用 L1／L2 | 方案 B：從 Old UI／`ui_v2` 抽離合格來源能力 | 方案 C：對確實無法重用的部分另行設計 |
|---|---|---|---|
| 適用列（依第 4 節） | REUSE 的 8 列 | EXTRACT 的 31 列 | REDESIGN 的 8 列，以及 NOT VERIFIED 14 列中經確認無法重用者 |
| 正確性風險 | 最低：程式、測試、接線已存在；風險在日期證據與 Eligibility，不在程式 | 中：換算、tier、拐點邏輯埋在大檔，抽離時可能改變語意；方向與日期語意須先定（第 5 節風險 3、4） | 最高：新來源、新契約、新語意；代理值與無出處常數屬反捏造風險 |
| 開發速度 | 最快（沿用） | 中（須逐項抽離並補測試） | 最慢（需先過 Decision Gate） |
| Token／成本 | 最省：只需盤點與連結，不改程式 | 中：需讀大檔（`FAI` 單檔 2,000 餘行）與補測試 | 最高：新設計、新驗證、可能新來源成本 |
| 需改哪些模組 | 原則上不改；僅在需要時補契約文件 | `services/macro/*`、`services/risk_radar.py`、`services/liquidity_engine.py` 內的邏輯搬到 `services/v2_tables/` 或 `services/v2_domain/`；新增 `INDICATOR_SPECS` 鍵屬 44 資料契約變更 | 新 L1 fetcher、新 L2 domain、新 UI 契約 |
| 需哪些驗證 | Eligibility 與日期證據（含第 4.2 節各項） | 替身測試鎖數值；Cross-View Consistency（PROJECT_RULES 13.3）；方向與單位 | 全套：來源可得性、授權、日期、單位、方向、獨立 QA |
| 是否碰正式財務／來源／FX Gate | 不改；但 D1 受 FX Gate 約束，REUSE 不等於放行 | 觸及公式、門檻、方向語意者須停手請客戶核准（PROJECT_RULES 13.6） | 新來源屬 Stop Gate；匯率仍受 FX Gate |

**專案 AI 推薦（未經客戶裁示、可被推翻）**：**優先採方案 A → 方案 B → 方案 C 的順序**，即最快、最不容易出錯、Token 最省的路線是先處理 REUSE 的 8 列（直接重用），再逐組處理 EXTRACT，最後才處理確定無法重用的部分；理由是方案 A 不改程式、不碰 Gate，且與 `docs/v2/83` 的混合治理（指標 ID、來源語意與 Gate 在 GitHub 版本化契約、Sheet 只呈現）一致。**本推薦不授權任何施工、抓取或探測。**

## 8. 需客戶裁示的 Decision Gate（最多三題）

以下三題由專案 AI 彙整，推薦不是裁示。

### G1：盤點範圍與母集合（要把哪些指標算進正式清單）

| 方案 | 內容 | 風險／成本 |
|---|---|---|
| A（推薦） | 先只納入 REUSE 的 8 列與已有 `INDICATOR_SPECS`／`mv` 契約者作為正式母集合；其餘列保持候選並標明缺口 | 最小；母集合小但可信 |
| B | 再納入 EXTRACT 的 31 列（含 Old UI 才有的總經與流動性） | 需先定義方向與日期語意（G3）；母集合大 |
| C | 同時納入 NASDAQ、MSCI World、MSCI EM、歐洲股指（需新來源） | 屬 Stop Gate「新資料來源」；成本與授權未知 |

**推薦 A**：母集合是 `coverage_summary` 能否算百分比的前提，先小而可信，再擴大。

### G2：監控紀錄放哪裡、誰能寫

| 方案 | 內容 | 風險／成本 |
|---|---|---|
| A（推薦） | 先在 repo 內以版本化契約（候選 catalog 與狀態）表達清單與缺口，不新建 Sheet、不寫 Sheet；Sheet 日後只作唯讀投影 | 不碰 J-6 零寫入；最快、最省 |
| B | 建獨立監控 Sheet（D83 方案 B），writer 維持停寫，待另行授權 | 需新 secret、權限、header 鎖定；寫入仍須新裁示 |
| C | 擴充既有 `SETTINGS_SHEET_ID` | 觸及 frozen 44／50 四表與讀寫相容；D83 已列為不建議 |

**推薦 A**：現有證據顯示 `fetch_log` 無法承載逐指標健康度，而 writer 受 J-6 約束，先把契約落在 GitHub 是風險最低的一步。

### G3：日期與美元／匯率的正式語意

| 方案 | 內容 | 風險／成本 |
|---|---|---|
| A（推薦） | 沿用「觀測日」語意、不顯示公布日；`DTWEXBGS` 與 `DX-Y.NYB` 都不稱 DXY（分別改稱廣義美元指數與另一個名稱）；USD/JPY 與 EUR/USD 的方向在契約中明寫 | 最小；不需要 vintage 全面接入 |
| B | 要求所有會修正的 FRED 指標都顯示首次公布日與修正版（需把 vintage 擴到更多 series） | vintage 路徑本身 NOT VERIFIED；成本高 |
| C | 暫不納入 Old UI 才有的總經與匯率指標 | 最安全但能力差距不變 |

**推薦 A**：這題決定的是資料身分與方向語意（屬 Stop Gate 範圍），不是抓取；先把語意寫死，EXTRACT 類才有可抽離的目標。

## 9. 方法與限制

### 9.1 方法與限制聲明

- 三組研究皆為**單組、唯讀**：沒有打任何外部 API、沒有跑 pytest（彙整者另跑守衛測試，見 9.3）、沒有改 repo 程式。`data_cache/*.parquet` 本機缺 pyarrow，只讀了 `metadata.json`。
- **研究原稿在 scratchpad，不入庫**；本報告是彙整與核實，不是原稿的逐字轉錄。Evidence 欄的 `file:symbol` 是彙整者與研究組都可再查證的位置，**不寫行號**（行號會漂移）。
- 研究組初稿基於 `15538a57`，之後以 main `558fc00f` 重核（`*.py` 差異只有 `tests/test_doc_counters.py` 一行）。
- 研究組自述未做：真實網路請求；解壓三份舊 `.json.gz`；重算 E1174 的數字；通讀 `docs/v2/49`、`44`、`79`；比對 `shared/ui_semantics/rules.py` 全部 key；逐一核對 DECISIONS 原文（本報告彙整者只核對了第 9.2 節列出的 DEC 的標題與性質）。
- 以下全稱性結論一律**單組未驗**：「Old UI 無 S&P 500 價格圖」「`get_latest_fx` 無 production 呼叫端到達 FRED 備援」「`FAI` 對所有長度不足的指標都無聲不建鍵」「`ui/` 下沒有第二處私有取數」「那些常數除所列外沒有引用」。
- 本報告不覆蓋：台股選股、EPS×PE、Risk Cap（本批不移植）；OneBrain、Phase 7 與 Digest（未授權）；基金 NAV、配息、持股等非國際市場資料；新聞情緒的內容品質。
- **一律不解鎖**：FX Gate、金融公式、OneBrain、Phase 7；本報告也不推薦或授權任何實際抓取或探測。

### 9.2 彙整者的實查（在 `b1109e_wt`，HEAD 為 `558fc00f` 的工作樹，共 25 項）

下表列出我自己重跑或讀碼核對的項目；「結果」欄是我的實查。與研究組不符之處以我的實查為準，並在「不符」欄標註。

| # | 核對對象 | 我的實查結果 | 與研究組 |
|---|---|---|---|
| V1 | `FX_OBS_DATE_RULE_VERIFIED` 位置與值 | `services/v2_tables/market_indicator.py` 的定義處為 `False`；在同檔 `build_fx_indicator_table` 內以 `if not FX_OBS_DATE_RULE_VERIFIED` 擋下 | 相符 |
| V2 | `FETCH_LOG_SPEC` 欄數 | 7 欄（`log_id`、`source_tier`、`started_at`、`finished_at`、`outcome`、`row_count`、`message`）；`OUTCOME_VALUES=("ok","failed")`；`SOURCE_TIER_VALUES` 四個（淨值／配息／市場指標／其他） | 相符 |
| V3 | `^GSPC` call site | `services/risk_radar.py`（`range_="1y"`）、`services/macro/turning_points.py`（`range_` 變數）、`services/crisis_backtest.py`（`"SPX": "^GSPC"`）、`services/v2_tables/market_view.py`（`SP500_TICKER`、5y）；`us_indicators.py` 沒有 `^GSPC` | 相符 |
| V4 | NASDAQ／歐洲股指字面 | 以 `^IXIC`、`^NDX`、`^GDAXI`、`^STOXX`、`^FTSE`、`^FCHI` 掃 `*.py`：僅命中 `tests/test_v2_tables_market_view.py` 的負向守衛字串（`^IXIC` 一行） | 相符 |
| V5 | Old UI 是否 import `ui_v2`／`ui_v3` | 掃 `app.py`、`ui/*.py`、`ui/**/*.py`：0 命中 | 相符 |
| V6 | `get_latest_fx` 的 FRED 備援與 EUR 倒數 | `_FRED_FX_MAP` 中 `("EUR","USD")` 為 `(FRED_EUR_USD, "inv")`，模式 `inv` 時回 `1.0 / _val`；`shared/fred_series.py` 註解 `FRED_EUR_USD` 為 `USD per EUR (inverse)`；`diagnose_fx_sources` 的 FRED 分支（另一份 `_FRED_FX_MAP`）直接回 `float(_df.iloc[-1]["value"])`、不取倒數 | 相符；**補充**：診斷函式與取值函式的 FRED 分支方向處理不一致（研究組沒提） |
| V7 | `get_latest_fx` 的 pair 解析 | 以前 3 碼為 base、後 3 碼為 quote；`_is_twd` 為真時跳過 FRED；不足 6 碼回 None | 相符 |
| V8 | `ai_service._key_inds` | 內容為 `["VIX","T10Y2Y","PMI","FED_RATE","SP500","USDJPY"]`；非測試 `*.py` 中 `"SP500"` 字串只命中該行（另 `mv` 有 `SP500_*` 常數，不是指標鍵）；`us_indicators.py` 沒有 `SP500` 鍵 | **部分不符**：研究組 R1 稱「`FAI` 產出鍵無 SP500 與 PMI」；`us_indicators.py` 有 `R["PMI"]`（且 `EXPECTED_INDICATOR_KEYS` 含 `PMI`），**PMI 缺失宣稱不成立**，SP500 成立 |
| V9 | `DTWEXBGS` 用途 | `liquidity_engine.py`（`build_xccy_proxy`，`fetch_fred(FRED_DXY, ..., 800)`）、`us_indicators.py`（預熱 `(FRED_DXY, 800)`）、`scripts/update_macro_history.py`（cron 清單） | 相符 |
| V10 | `fetch_log` 的 production 寫入 | `services/v2_tables/settings_store.py` 的 `begin()` 呼叫 `self._runtime.open_fetch_log(mi.SOURCE_TIER)`（runtime 版，不是 L1 寫入）；`class RuntimeFetchStore` 存在；`WIRED_TABLES`、`WIRED_TIERS` 為常數 | 相符 |
| V11 | `is_read_only()` | `repositories/settings_sheet_repository.py::is_read_only` docstring 載明第一階段恆為 True；SET-5 的零寫入靠不呼叫、不靠它 | 相符 |
| V12 | `fetch_fred_vintages` 呼叫點 | 非測試 `*.py` 中 `ffv` 的呼叫在 `services/v2_tables/market_indicator.py`（以 `_call(fetch_fred_vintages_with_error, ...)`）；另 `settings_store.py` 把它登記為快取清除對象（`_CACHED_FETCHER_BY_SOURCE`）；`mv` 檔頭載明 2026-10-28 起改走 `ffrede`、不走 vintage | 相符 |
| V13 | 常數是否有取數呼叫 | 對 `FRED_GDPNOW`、`FRED_LEI`、`FRED_NFCI`、`FRED_PAYEMS_MANEMP`、`FRED_SAHM_CURRENT`：除 `shared/fred_series.py` 外，非測試 `*.py` 的引用檔為空；`FRED_T10Y3M` 只在 `ui/helpers/io/data_registry.py`；`FRED_ISM_PMI` 只在 `services/macro/_helpers.py` | 相符 |
| V14 | PCE／GDP／GDPNow 取數 | 以 `PCEPI`、`PCEPILFE`、`PCE`、`GDPC1`、`GDPNOW`、`USSLIND` 掃非測試 `*.py`：只有常數與註解，沒有取數呼叫 | 相符 |
| V15 | `data_registry` 的 `CHN_*` | `ui/helpers/io/data_registry.py` 仍有 `CHN_CLI`／`CHN_PMI`／`CHN_CPI`／`CHN_M2` 的頻率與 series id 字面值 | 相符 |
| V16 | `INDICATOR_SPECS` 與 `DOMAIN_ORDER` 鍵數 | 以 AST 解析：`INDICATOR_SPECS` 為 `vol_index`、`fx_twd_per_usd`、`credit_spread_pct`、`term_spread_pct`、`policy_rate_pct`、`leading_index`、`coincident_index` 共 7 鍵；`DOMAIN_ORDER` 為 12 個 domain；`_MISSING_DOMAINS` 含 TAIEX 成交量、市場統計、NASDAQ、MSCI World、MSCI EM、EPS×PE、implied earnings | 相符 |
| V17 | 退避秒數 | `shared/backoff_policy.py`：unreachable 60、server_error 300、blocked 900、rate_limited 1800 | 相符 |
| V18 | 快取 TTL | `fetch_yf_close` 為 `@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=64)`；`fetch_fred` 為 `@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=32)`；另 `fetch_yf_latest` 為 TTL_5MIN | 相符 |
| V19 | 探測清單 | `scripts/probe_fx_obs_date.py`：`REQUIRED_TICKERS` 是 `(PRIMARY_TICKER, "^VIX")`（`PRIMARY_TICKER` 為 `USDTWD=X`），`DEFAULT_TICKERS` 再加 EURTWD、JPYTWD、CNYTWD、CNHTWD；沒有 `^GSPC`、`^TWII`；該腳本自己實作取數（用同一端點與 `fetch_url`），**不是**呼叫 `fetch_yf_close` 本體 | 相符；**補充**：E1174 的 Fetch 證據是「同端點同傳輸的探測」，不是 `fetch_yf_close` 本體的執行紀錄 |
| V20 | `metadata.json` | `datasets` 內 `fred_indicators`（2026-11-05、row_count 13829、無 error）、`vix_history`（2026-11-06、3881）、`spx_history`（2026-11-06、3879）、`twii_history`（2026-11-06、3762），`last_error` 皆為空；cron 的 `FRED_SERIES_IDS` 含 `DGS10`、`DGS2`、`DGS3MO`、`BAMLH0A0HYM2`、`M2SL`、`WALCL`、`CPIAUCSL`、`UNRATE`、`DTWEXBGS`、`PPIACO`、`PCOPPUSDM` | 相符 |
| V21 | FX 測試鎖 | 掃 `tests`：`FX_OBS_DATE_RULE_VERIFIED is False` 共 8 處、分布在 7 個測試檔 | **細節不符**：R1 寫「八支測試」，實為 8 處斷言、7 個檔 |
| V22 | `get_latest_fx` 非測試呼叫端 | `scripts/audit_6d_coverage.py`、`services/fund_invest_calc.py`、`services/fund_row.py`、`services/fx_regime_service.py`（`USDTWD=X`）、`ui/helpers/fund/checkup.py`、`ui/helpers/fund_grp_health/investment.py`、`ui/helpers/portfolio/fee_deduction.py`、`ui/tab2_single_fund.py`，傳入都是 `<ccy>TWD`／`TWD=X` 形式；`services/fund_service.py` 為 re-export | 相符（單組、範圍為非測試 `*.py`） |
| V23 | `^VIX` 非 builder 呼叫點 | `fund_service.py`（`("^VIX","1y")`）、`liquidity_engine.py`（`("^VIX","5y")`）、`us_indicators.py`（`_yf_iso("^VIX","5y")`）、`risk_radar.py`（兩處 `range_="6mo"`）；加上 `mi`、`mv` 為至少 5 種引數形狀 | 相符 |
| V24 | DEC 性質 | `DEC-2026-10-27-41`＝客戶裁示（A＋C 並行）；`-43`＝客戶裁示（Yahoo `^TWII`）；`-42`、`-44`＝**執行組讀法、不是客戶裁示**；`DEC-2026-11-08-02`、`DEC-2026-11-09-05` 存在 | **部分不符**：R1 在 A1 的 Formal Gate 把 `-42(a)` 與 `-41` 並列為客戶裁示；`-42` 是執行組讀法，已在 A1 更正 |
| V25 | 美元稱呼 | `us_indicators.py` 有 `DX-Y.NYB` 預熱與 `s_dxy` 區塊，`_CROSS_RATES` 為 `EURUSD=X`（1.05／1.15）、`JPY=X`（140／155）、`CNH=X`（7.0／7.3） | 相符 |

**其他不符與更正彙總**：(a) R1 稱 `FAI` 無 `PMI` 鍵——不成立（V8）；(b) R2 §2.3 自稱 5 列，實為 6 列（`DTWEXBGS`、`DEXJPUS／DEXSZUS`、`DEXCHUS／DEXUSEU`、`VXVCLS`、`PCOPPUSDM`、中國四條）——本報告第 2.5 節以 6 列呈現；(c) R3 稱「快取鍵不同」是讀碼推論未驗——我讀了 `_ttl_cache` 的 key 實作確認為 `(args, sorted kwargs)`，升為 FACT（第 3.3 節），但「請求次數增加」仍是推論；(d) 研究組之間分類界線不一致（R1 與 R2 對 L1 現成但 L2 在 Old UI 的項目標籤不同），已在第 4.1 節統一。

### 9.3 守衛測試

自查時執行（皆於 `b1109e_wt`，用 `/root/.local/bin/pytest`，帶 `--noconftest`，因 pytest 所在的 uv-tool 直譯器沒有 `requests`／`pandas`／`streamlit`，這**不是** CI 的完整指令；CI 的完整依賴環境本機驗不到）：`tests/test_doc_counters.py`、`tests/test_constitution_file_refs.py`、`tests/test_amendment_8_integrity.py`，以及 `PYTHONPATH=. tests/test_canonical_rule_consistency.py`。結果見回報（不在本檔寫死數字，因為測試數會隨守衛長大而漂移）。`tests/test_doc_counters.py` 的射程是 `docs/v2/` 底下的 `.md` 與 `prototype/*.html`；本檔位於 `docs/evidence/`，**不在其射程內**，但本檔仍依其規則自律（不把掃描指令寫成與數字同句、不以全稱詞開頭而無反向檢查）。

## 附錄：主要查證指令（pinned 到 `558fc00f`，範圍 `*.py`，除另註）

以下指令都對 `558fc00f` 的內容執行（工作樹 HEAD 即該 commit、無修改）。結果的解讀見第 9.2 節對應列。

```
git grep -n "FX_OBS_DATE_RULE_VERIFIED" 558fc00f -- '*.py' ':!tests'
git grep -n "FETCH_LOG_SPEC" 558fc00f -- 'repositories/*.py'
git grep -n "\^GSPC" 558fc00f -- '*.py' ':!tests' ':!scripts'
git grep -nE "ui_v2|ui_v3" 558fc00f -- app.py 'ui/*.py' 'ui/**/*.py'
git grep -n "SP500" 558fc00f -- '*.py' ':!tests'
git grep -n "fetch_fred_vintages" 558fc00f -- '*.py' ':!tests'
git grep -n "get_latest_fx(" 558fc00f -- '*.py' ':!tests'
git grep -nE "FRED_(GDPNOW|LEI|NFCI|PAYEMS_MANEMP|SAHM_CURRENT|T10Y3M|ISM_PMI)" 558fc00f -- '*.py' ':!tests'
git grep -niE "PCEPI|PCEPILFE|GDPC1|GDPNOW|USSLIND" 558fc00f -- '*.py' ':!tests'
git grep -n "CHN_" 558fc00f -- ui/helpers/io/data_registry.py
git show 558fc00f:data_cache/metadata.json
```

