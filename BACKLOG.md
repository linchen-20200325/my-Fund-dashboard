# BACKLOG.md — 動態任務追蹤

> 與 `STATE.md`（靜態架構地圖 + 高層 Roadmap）分離，本檔追蹤逐項進度。
> 規則：每項一行 checkbox，附 commit hash / PR # / 狀態。

---

## 🟡 Open — CLAUDE.md Bootstrap-audit 後續(2026-06-23 step 4 收尾後盤點)

> Bootstrap 4 步流程已完成(§0 改名「填寫紀錄」#322)，§3.3 反捏造 / §8.2 高項違憲皆 0。
> 以下為**步驟 3 audit 中發現但本輪未動**的 ⚠️ / 灰色地帶 / 補洞項目，下個 session 入口。

- [x] **F-PROV-1** §2.2 provenance 補洞;v19.82-84 完成 phase 1-3:
  * phase 1(#326):`fetch_fred` 加 source/fetched_at columns
  * phase 2(#327):`fetch_yf_close` 加 attrs
  * phase 3(#328):`fetch_defillama_stablecoin_mcap` (attrs) + `fetch_aaii_sentiment` (dict keys)
  * **phase 6**(v19.92):`fund_repository._src_fundclear_meta` + `_src_tdcc_meta` 補 source/fetched_at(FundClear:GetFundBasicInfo / TDCC:OpenAPI:3-2+3-4,僅成功 path)
  * **phase 7**(v19.93):`fund_repository._src_fundclear_nav` 加 source/fetched_at(Series.attrs:`FundClear:GetFundNAV`)
  * **phase 8**(v19.94):`tw_macro.py` 3 fetcher 補 source/fetched_at(`TWSE:MI_INDEX:MS` / `FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor` / `CBC:M1B_M2` 3-tier aware)
  * **phase 9**(v19.95):`fund_repository._src_tcb_nav` MoneyDJ 多 URL 3 return path 補 Series.attrs source/fetched_at(`MoneyDJ:tcbbankfund/chubb/www.moneydj.com:<endpoint>` / `MoneyDJ:tcbbankfund:yp004002:<page>` / `MoneyDJ:nav_30day:fallback`)
  * **phase 10**(v19.96):`fund_repository._src_cnyes_nav` + `_src_morningstar_nav`(UK + lt 2 endpoint)+ `_src_yahoo_finance_nav` 補 Series.attrs source/fetched_at(`Cnyes:fund_nav_api` / `Morningstar:UK:timeseries:<secId>` / `Morningstar:lt:<token>:<secId>` / `Yahoo:chart:<yf_symbol>`)
  * **phase 11**(v19.97):`fund_repository` 5 個基金公司直連 / 保險子網域 / fallback NAV fetcher 補 Series.attrs(`AllianzGI:<host>` / `AlphaVantage:TIME_SERIES_DAILY_ADJUSTED:<symbol>` / `InsuranceSubdomain:<host>:<endpoint>` / `Franklin:franklintempleton.com.tw:nav_direct` / `JPMorgan:am.jpmorgan.com/tw:nav_direct` / `MoneyDJ:nav_30day:table_parse`)
  * **phase 12**(v19.98):`fund_repository._src_sitca_nav` + `_src_insurance_subdomain_nav`(2 fallback path)補 Series.attrs(`SITCA:IN2213.aspx` / `InsuranceSubdomain:<portal>.moneydj.com:wf01-wb02` / `InsuranceSubdomain:<portal>.moneydj.com:yp004002:<page>`)
  * **phase 13**(v19.99):`fund_repository` 3 個 dict-returning 績效/風險/持股 fetcher 補 source/fetched_at(`fetch_performance_wb01` → `MoneyDJ:<host>:wb01` / `fetch_risk_metrics` → `MoneyDJ:<host>:wb07` / `fetch_holdings` → `MoneyDJ:yp:<page>`)— MoneyDJ 4 大資料頁(wb01 / wb07 / yp013000 / yp013001)provenance 鏈完成
  * **phase 14**(v19.100):`fund_repository._src_bank_platform_nav` 3 return path 補 Series.attrs(`BankPlatform:<domain>:taiwanlife_mobile` / `BankPlatform:<domain>:yp004002:<page>` / `BankPlatform:<domain>:<page>:30day`)
  * **phase 15**(v19.101):`fund_repository._src_cache_files`(Series.attrs + cache_updated_at)+ 3 個 meta fetcher(`_src_morningstar_meta` → `Morningstar:lt:SecuritySearch` / `_src_allianzgi_meta` → `AllianzGI:ifund_meta` / `_src_tcb_meta` → `MoneyDJ:<host>:<endpoint>` / `_src_sitca_meta` → `SITCA:IN2213.aspx:meta`)
  * **phase 16**(v19.102):`fund_repository` 高層 NAV orchestrator + 4 個 long-history fetcher 補 Series.attrs:`fetch_nav_cnyes`(`Cnyes:fund.api:v2/funds/<cand>/nav`)/ `fetch_nav`(`MoneyDJ:<host>:<endpoint>:fetch_nav`)/ `_fetch_nav_cnyes`(`Cnyes:api:v1/fund:<ep>` + html __NEXT_DATA__ + table)/ `_fetch_nav_moneydj_history`(`MoneyDJ:<host>:<ep>:nav_history_long`)/ `_fetch_nav_fundrich`(`FundRich:api:v1/funds:<ep>`)/ `_fetch_nav_fundclear`(`FundClear:<host>:nav_history_long:<json|csv>`)
  * **phase 17**(v19.103):`fund_repository.fetch_fund_structure` 加 `MoneyDJ:STRUCTURE_PAGES:multi_portal` source + fetched_at;`fetch_fund_by_key` 加 `nav_source_used`(從 series.attrs 取出來)+ `fetched_at` orchestrator-level 旗標
  * **phase 18**(v19.104):services 層 NAV 抓取的 wrapper provenance:`crisis_backtest.fetch_market_series`(`Yahoo:fetch_yf_close:<ticker>:<range>:crisis_backtest`,setdefault 不蓋過上游)+ `multi_factor_optimization.fetch_factor_series`(yahoo / fred / COPPER_GOLD_RATIO / VIX_DELTA_5D `_stamp_prov` helper,涵蓋 calculated 因子)
  * **phase 19**(v19.105):3 個 L2 service 多指標融合 orchestrator 補 provenance:`us_liquidity_engine`(6 sub-fetcher 每個結果 dict 加 `source` + orchestrator-level `_provenance.sources`/`fetched_at`)/ `valuation.detect_valuation`(2 estimate 加 `_provenance.sources`:yfinance `^GSPC.info` chain + FRED GDPNOW)/ `risk_calibration.fetch_real_3factor_monthly`(df.attrs + spx.attrs + notes._provenance,涵蓋 HY_Spread/Yield_Curve/VIX/SPX 月度 resample 4 條來源)
  * **phase 20**(v19.106):`tests/test_provenance_smoke.py` 4 個契約測試防退化(runtime fetch_fred + 靜態檢查 fund_repository / services 層命名 / reconcile pattern)
  * **phase 21**(v19.107):`services/macro_service.calc_macro_phase` 12 指標融合處 `_provenance`(sources / contributing / total/earned weight / aggregator)
  * **phase 22+(WONTFIX)**:剩餘 fetcher provenance — 套 §-1 工作準則,核心 40+ fetcher 已涵蓋,邊際效益遞減。v19.109 結案
  * **v19.185 二次確認 audit**:user 重評時平行 audit 確認剩餘 fetcher 全屬「多源融合 orchestrator / 落後輔助診斷 / 純邏輯包裝 / 邊界 dict.source 已含」4 類,維持 WONTFIX 結案
- [x] **F-PIT-1** §2.3 v19.81 audit 結案:`crisis_backtest.py` + `crisis_strategy_grid.py` **PIT-safe**(時序順序掃描 + `shift(1)` 防 same-bar lookahead + 嚴格時間窗切片,無 merge_asof 跨頻)
- [x] **F-RECON-1** §4.3 雙演算法對帳;**v19.87 phase 1+2**:新建 `services/reconcile.py`(L2 純函式)+ 21/21 unit tests。對外 API:`reconcile_pair`(通用)/ `reconcile_us10y_yield`(FRED DGS10 vs Yahoo ^TNX/10, 5bp 容差)/ `reconcile_fund_annual_return`(自算 vs MoneyDJ wb01)/ `reconcile_sharpe`(自算 vs MoneyDJ wb07)/ `reconcile_dividend_yield`(自算 vs MoneyDJ)。**Phase 2**:`services/risk_radar._signal_yield_10y_shock` 接入 reconcile,額外抓 `^TNX` 與 FRED DGS10 比對,結果以 schema-additive `reconcile` 欄寫入返回 dict;`ui/tab1_macro.py` 雷達卡片新增「✅/⚠️ 對帳 chip」;3 新 unit tests + 既有 3 test 不破。**v19.88 phase 3**:`services/fund_service.calc_metrics` 接入 `reconcile_sharpe`,在返回 dict 新增 `sharpe_reconcile` 欄(self-calc vs MoneyDJ wb07);3 新 unit tests 全綠;16/16 fund_metrics 不破。**v19.89 phase 4**:`repositories/fund_repository._finish_metrics` 1Y 報酬對帳(self-calc `ret_1y_total` vs MoneyDJ wb01 `perf["1Y"]`);schema-additive 寫入 `result["metrics"]["ret_1y_reconcile"]`,僅在真 wb01 來源(`perf_source != "local_calc"`)時啟動。**v19.90 phase 5**:同 `_finish_metrics` 加配息殖利率對帳(self-calc `annual_div_rate` vs MoneyDJ `moneydj_div_yield`);寫入 `result["metrics"]["div_yield_reconcile"]`,兩值皆 % 單位內部轉小數。**v19.91 phase 6**:`ui/tab2_single_fund.py` 接入三組對帳 chip 渲染(Sharpe / 配息殖利率 / 1Y 報酬),phase 3-5 寫入 metrics 的對帳資料正式被使用者看見。**F-RECON-1 完整收尾**(5 phase data + 1 phase UI)。
- [x] **F-SCHEMA-1** §3.1 pandera — 原 v19.109 WONTFIX 標籤**過時**(v19.187 audit 發現):實際早已啟動且推進至 Phase B5:
  * **shared/schemas.py 已有 5 個 Schema**:`MacroFredSchema` / `YahooCloseSchema` / `FundNavSchema` / `FundDividendSchema` / `ForeignFlowSchema`
  * **8 處 production caller 接入**:`fund_service.calc_metrics`(L228-229)/ `macro_repository.fetch_fred`(L324)/ `macro_repository.fetch_yf_close`(L451)/ `fund_repository.fetch_nav`(L3621)/ `fund_repository.fetch_div`(L4111)/ `hot_money.fetch_foreign_flow_series`(L155-158)
  * **7 個 test 檔 91 tests 全綠**:test_schemas_phase_a/b/b2_fund_nav/b3_dividends/b_foreign_flow/c
  * **Phase A v19.155(pilot)** + **Phase B v19.161-163(fetch_yf_close / fetch_nav / fetch_div)** + **Phase B5 v19.186(foreign_flow)** 已落地
  * **pandera 已 pin** `requirements.txt`(>=0.20,<1.0),冷啟動 cost 已實測可接受
  * Phase C/D(全面 + CI gate)留待 user 觸發,**遵 §-1 不主動推進**
- [x] **F-GRAY-1** §8.3 v19.81 audit 結案:`fund_fetcher.py` **保留根目錄**(18 條 re-export shim + 57 caller,搬移為 cosmetic)
- [x] **F-GRAY-2** §8.3 v19.81 audit 結案:`hot_money.py` / `tw_macro.py` 同上,根目錄 vs `repositories/` 為純 cosmetic
- [x] **F-GRAY-3** §8.3 v19.81 audit 結案:`app.py`(568 LOC)已是 orchestrator,無業務邏輯需下沉;同步刪除 1 處 dead code `_unused_old_calculate_composite_score`
- [x] **F-GRAY-4** §8.3 `MACRO_THRESHOLDS` harmonize:v19.168(#406)architecture proposal 立案(SPEC §16.2)。**v19.169 HY_SPREAD** 落地:新建 `shared/macro_thresholds_v2.py` SSOT(4 sub-dict:stoplight / score_function / portfolio_advisor / beginner_panic),migrate 6 sites(macro_repository / macro_validation / macro_score_calibration / portfolio_service / macro_service / macro_beginner_view / tab1_macro),+ `tests/test_macro_thresholds_v2.py` 13 守護 tests 全綠。**v19.178 CPI(部分)** + **v19.179-180 PMI(完整,8 sub-dict)** 落地。**v19.183 CPI 完整收尾**:`repositories/macro_repository.py:198` 最後 1 處 inline `{"green_low": 1.5, ...}` 改 `_CPI_THR["stoplight"]` SSOT(值完全等價)+ 註解同步更新。**HY+CPI+PMI 全部 v2 SSOT 化結案**
- [x] **F-MED** Bootstrap-audit 中項(M) — W5-1~W5-4 + **v19.170 Top-10 sweep** + **v19.184 第二輪 15 處 sweep** 已收三輪共 25 處:
  * **v19.170(本批 10 項)**:10 處 silent `except Exception:` 散在 L2 service 層 → 全改 `except Exception as e:` + stderr log
    - `services/nav_history_store.py:51` `_load_cache_series` cache 解析失敗
    - `services/portfolio_service.py:400` `calc_shadow_score` numpy import 失敗
    - `services/portfolio_service.py:526` `calc_correlation_matrix` 失敗
    - `services/ai_service.py:192` risk_alert 注入失敗
    - `services/ai_service.py:329` `single_fund_summary` tr1y/adr parse fail
    - `services/ai_service.py:526` `_append_error_ledger` 寫檔失敗
    - `services/fund_service.py:382` `calc_metrics` days_span 計算
    - `services/fund_service.py:392` `calc_metrics` 1Y window 計算
    - `services/fund_dividend_health.py:296` 配息解析
    - `services/fund_dividend_health.py:370` mk_simple 嚴格計算
  * **v19.184(本批 15 項)**:user 指派續做,15 處 silent except 全改 stderr log
    - `services/fund_health_report.py:48,89,96,108,125,152` — _compute_holding_years / compute_1y_total_return / _resolve_adr_with_fallback / compute_4d_health / calc_fund_factor_score / check_333_principle
    - `services/fund_replacement_verdict.py:115,138,158` — check_eating_principal_1y_mk / compute_4d_health / check_333_principle
    - `services/macro_tw_local_fetch.py:71` — FinMind JSON parse
    - `services/macro_service.py:2076` — _daily_spx_return
    - `services/fund_history.py:51` — preset funds JSON parse
    - ~~`services/quadrant_simulator.py:235` — resample "ME" fallback~~(v19.210 P0-3-#2 整檔拔毒,production 0 caller)
    - `services/macro_validation.py:282` — index to_datetime
    - `repositories/fund_repository.py:3199` — nav_rows mmdd parse
  * 介面 0 改;只把「失敗時靜默」改成「失敗時 stderr 留軌跡」,便於生產 debug
  * 三輪共 25 處收齊;剩餘 (M) 項**遵 §-1 等實際 bug 觸發再收**,不主動清

**v19.109 收尾**(CLAUDE.md §-1 工作準則立):Open 項全數 WONTFIX 或結案,僅 F-MED 等實際 bug 觸發再收。0 個 active pending。

**v19.185 二次收尾**(user 指派 3 epic「F-GRAY-4 + F-MED + F-PROV-1 phase 22+ 繼續」後完整盤點):
- F-GRAY-4 ✅ HY+CPI+PMI 全 v2 SSOT 化(PR #436)
- F-MED ✅ 三輪共 25 處 silent except 收齊(PR #436)
- F-PROV-1 phase 22+ ✅ 二次 audit 確認 WONTFIX 維持(剩餘屬「多源融合 / 輔助診斷 / 純邏輯 / dict.source 已含」4 類)
- F-RECON-1 ✅ 書記同步(v19.91 早已完整收尾,checkbox 改 [x])
- F-PROV-1 ✅ 書記同步(v19.109 結案,checkbox 改 [x])

4 個 ⚙️ checkbox 同步成 [x],BACKLOG 與實質狀態對齊。0 個 active pending。

**v19.187-189 三 epic 第三輪續做**(user 指派「F-PROV-1 phase 22+ + F-SCHEMA-1 + F-MED 餘量」):
- **v19.187 F-MED L3** ✅ `infra/cache.py` 12 處 silent except 全改 stderr log
  - `_normalize_moneydj_url_for_cache` malformed URL fallback
  - `_ttl_cache` wrapper `key_fn` fail
  - `clear_all_caches` / `clear_caches_by_names` / `get_all_cache_info` 單一 fn fail
  - `clear_disk_cache` rm/listdir fail(2 處)
  - `global_refresh_all` L1-L4 各層 fail(5 處)
  - 介面 0 改,純可觀測性提升
- **v19.188 F-PROV-1 phase 23** ✅ `services/risk_radar.py` 2 個 CSV fetcher 補 Series.attrs source/fetched_at
  - `_fetch_cboe_csv` → `CBOE:cdn:daily_prices:{short_name}_History.csv`
  - `_fetch_stooq_csv` → `stooq:q/d/l:{symbol}`
  - 其餘 15 個無 provenance fetcher audit 結果:scalar return / list return / wrapper / orchestrator 4 類,**結構性無法 stamp**,WONTFIX 仍對
- **v19.189 F-SCHEMA-1 audit** ✅ WONTFIX 標籤撤除,改 [x] — 實際 Phase A/B/B5 早已推進(細項見上)
- 974/977 全測過(剩 1 fail = pre-existing yfinance 環境問題,非本批)

### 2026-05-29（429 殘留 + D 模式 / Switch 引擎連環修：PR #74 → #94）

- [x] **PR #95** `v18.249` UX — 相關性矩陣 `NaN`（兩檔 NAV 序列無重疊期）改顯示「—」+ 配色 `#888` 灰；矩陣下方加 caption 解釋「`—` ≠ 0 ≠ 無相關，純粹是無重疊期無法計算」；test_holdings_overlap +1 case（無重疊 → NaN）。**8 → 9 passed**
- [x] **PR (next)** `v18.250` PR C — `cloud_io.dump_all_to_sheet / load_all_from_sheet` 開頭加 `detect_sheet_schema_version()` schema-aware routing；`v2` → 走新 helper `_dump_all_to_sheet_v2 / _load_all_from_sheet_v2`（per-policy 13 欄整 tab 覆寫 + 從 13 欄重建 portfolio_funds + ledger snapshot via Ledger.subscribe()）；`v1`/`empty`/detect 失敗 → 維持既有 v1 path 完全不動（向後相容）。test_cloud_io +4 case（routing v2 / v1 不變 / round-trip 13 欄 / load 13 欄反推 portfolio_funds + ledger）。**14 → 18 passed**。⚠️ **PR D 不做**（破壞性、需先在 Sheet 副本驗 v2 round-trip OK）。
- [x] **PR (next)** `v18.251` 風險評分真值校準器 + Tab1 互動式儀表板 — 新 `services/risk_calibration.py`（純函式）：`label_forward_drawdown`（SPX → forward-N-month drawdown < threshold ⇒ 1）/ `compute_calibration`（score+label+門檻 → confusion matrix + precision/recall/F1）/ `grid_search_threshold`（掃描 −1.0~3.0 → F1 排序表）/ `rolling_risk_score`（滑動 Z-score，公式同 PSE.calculate_composite_risk）/ `generate_synthetic_demo`（60 月內含 2 段壓力事件，給 sandbox demo / 測試用）。`ui/tab1_macro.py:1265+` 加「🎯 風險評分校準」expander（3 滑桿：horizon / drawdown / window；4 metrics：最佳門檻 / Precision / Recall / F1；Top10 grid 表）。test_risk_calibration +9 case（drawdown happy / 平穩市 / perfect score / empty / NaN-aligned / grid sort / synthetic stress / pipeline 收斂 / 缺欄 fallback）。**0 → 9 passed**。⚠️ sandbox 無 FRED outbound → 用合成資料 demo pipeline 正確性；真值校準需 user-side 餵入 live (VIX,HY,Yield,SPX) 月序列。
- [x] **任務 audit 對齊**（2026-05-30）— PM 盤點時誤標 「總經風險 UI 接線（壓力卡 / 趨勢圖 / 因子融合 / 宏觀研判）#2-#5 未做」實際 v18.228 已完整實現（`ui/tab1_macro.py:1267-1391`：壓力卡 `st.metric` + tier color + 因子貢獻 bar chart + `score_series` 歷史趨勢 sparkline + 3 risk-off 因子個別卡 + SSR 子彈水位 + `liquidity_verdict()` 白話研判）；計算層 `services/liquidity_engine.py:303 compute_liquidity_score()` production-ready。**無需再做任何 code 改動**，純 BACKLOG 對齊。
- [x] **PR #94** `v18.248` perf(sheets) — `load_all_policy_worksheets` 加 60 秒 TTL 短快取（key=sheet_id，return `.copy()` 防 mutate，`gspread.Client` unhashable 走手動 dict 而非 `_ttl_cache` decorator）；export `clear_load_all_ws_cache()` 給「🔄 清空快取」按鈕；test_policy_store +2 case（cache hit / sheet_id 隔離）。**67 → 87 passed**

### 2026-05-17（v11.1 後續優化：PR #165 → #196，36 commits）

> v11.0 完工後同日衝刺 — AI 強化 + Tab 拆檔完工 + helper 收口 + cloud crash 連環修 + sys.modules hack 全清 + AppTest 防退化網。
> 累積：app.py **9643 → 425 行（−95.6%）**，fast tests **359 → 460（+101）**，AppTest 12 cases。

#### 🤖 AI 強化（PR #165-#170, #193）
- [x] **PR #165** `v18.117` Phase 4 / 3-B 資料窗口拉長修「資料不足」
- [x] **PR #166** `v18.118` AI-1 — MK advisor prompt 接 Phase 4 driver + Phase 3-B 燈號回測
- [x] **PR #167** `v18.119` F1 — Phase 3-B frequency-aware 治本（series 統一月頻）
- [x] **PR #168** `v18.120` AI-2 — 5 個 prompt 模板抽出 → `services/ai_prompts.py`
- [x] **PR #169** `v18.121` AI-3 — 多 provider fallback chain（Gemini → Claude → GPT 透明升級）
- [x] **PR #170** `v18.122` AI-4 — `analyze_fund_json` 結構化 JSON 輸出 PoC（4 節 dict + tolerant parser）
- [x] **PR #193** `v18.135` — 單一基金 + MK AI 加「持股 × 新聞」交叉分析（fund_json 4→5 節）

#### 🏗️ v12.0 backlog 完工（PR #171-#172）
- [x] **PR #171** `v18.123` B-A — `fund_fetcher` HTTP 層收口到 `infra/proxy.py`（順手修 30+ pre-existing NameError）
- [x] **PR #172** `v18.124` B-B — `PrecisionStrategy.fetch_stock_three_ratios` I/O 拆 → `repositories/financial_repository.py`

#### 🎨 B-C 6 Tab 全部抽出（PR #173-#185）
- [x] **PR #173** `v18.125` B-C.1 Tab6 說明書 → `ui/tab6_manual.py`（250 行）
- [x] **PR #181** `v18.126` B-C.2 Tab4 回測 → `ui/tab4_backtest.py`（410 行）
- [x] **PR #182** `v18.127` B-C.3 Tab5 資料診斷 → `ui/tab5_data_guard.py`（963 行）
- [x] **PR #183** `v18.128` B-C.4 Tab2 單一基金 → `ui/tab2_single_fund.py`（1132 行）
- [x] **PR #184** `v18.129` B-C.5 Tab1 總經 → `ui/tab1_macro.py`（1870 行）
- [x] **PR #185** `v18.130` B-C.6 Tab3 組合（最大 3897 行）→ `ui/tab3_portfolio.py`

#### 🚨 Cloud crash hotfix 連環修（PR #186-#192）
- [x] **PR #186** `v18.131` 補 13 個 app.py module-level helper 漏 lazy import
- [x] **PR #187** `v18.132` 改用 `sys.modules['__main__']` 取代 `from app import`（修 set_page_config re-init）
- [x] **PR #188** `v18.133` 刪 app.py 殘留 Tab5 第一個 block（DuplicateElementKey）
- [x] **PR #189** `v18.134` 補齊 40 個 public service/repo import（audit 漏 public name）
- [x] **PR #190** `v18.135-fix` MACRO_EDU cross-ui/components import
- [x] **PR #191** `v18.136-1` 搬 6 個 app.py-local helper → `ui/helpers/macro_helpers.py`
- [x] **PR #192** `v18.137` 統一 Tab2/Tab3 1Y 含息報酬 fallback chain（修同基金兩 view 不同數字 9.09% vs 37.6%）

#### 🐛 User 部署反饋（PR #174-#180，issue rounds 1-6）
- [x] **PR #174-180** PMI series fix / fund_repository 9 個 NameError 連環修 / Tab2 partial 阻擋訊息 / NAS Proxy 可視化 / page_type fallback / `calc_metrics` 漏 import

#### 🏁 Helper 收口（PR #194 — 完成清單 1/2/3）
- [x] **PR #194** `v18.138` 搬 3 大 helper → `ui/helpers/`：
  - `holdings.py`（_HOLDING_ZH 410+ keys + _zh_holding，347 行）
  - `data_registry.py`（_update_data_registry 374 行）
  - `oauth_state.py`（OAuth chain 91 行，加 `_safe_secret` wrapper 防 module-load crash）
  - **app.py 1164 → 425 行**

#### 📚 文件 + Smoke 守門（PR #195）
- [x] **PR #195** `v18.138-docs` STATE/BACKLOG/ARCHITECTURE 同步 v18.117→v18.138 + 新增 `test_tab_modules_import_without_error`（< 1s fast tier 防退化）

#### 🧹 sys.modules hack 全清 + AppTest 防退化網（PR #196 — v18.139~v18.143）
- [x] **PR #196** 一次 squash 收口 5 commits：
  - `v18.139` 搬 `_sync_invest_twd_from_ledgers` → `ui/helpers/data_registry.py` + 清 Tab1/2 `sys.modules['__main__']` getattr 殘留
  - `v18.140` Tab3 OAuth chain（5 helper）改正規 `from ui.helpers.oauth_state import ...` + ARCHITECTURE.md §0 同步
  - `v18.141` AppTest seed `macro_done=True` + 23 指標 / phase_info → 進 `calculate_composite_score / composite_verdict / category_score / category_history / MACRO_EDU` 路徑（防 PR #186-191 同類 NameError；191s）
  - `v18.142` AppTest `monkeypatch oauth_state._oauth_configured=True` → 進 Tab3 OAuth-aware 分支（38s）
  - `v18.143` AppTest seed loaded fund + macro_done → 進 `mk_fund_signal / _quartile_check / _zh_holding` 鏈（102s）
  - **成果**：Tab1/2/3 徹底脫離 `sys.modules['__main__']` hack；三條關鍵分支補上 AppTest 防退化網（即便將來重構誤動 helper，AppTest 會在 CI 抓到，不會等部署後爆）

### 2026-05-16（後續修補：PR #71 → #162）
- [x] **v18.109 — 全面導入分層架構重構**（A-1 → E-30, 30 commits, `2d61e6c` → `15977d9`）— 使用者要求「全面導入分層架構」：
  - **Phase A 葉節點** (4): infra/proxy + oauth + cache / models/policy + ledger
  - **Phase B 倉儲** (12): repositories/ 7 檔（fund 4216 行大重構：B-9a/b-1~b-6 拆解 / macro / ledger / snapshot / policy / news）
  - **Phase C 服務** (8): services/ 8 檔（macro 2128 / fund 481 / ledger 502 / portfolio / precision / backtest / ai 857 / policy_advisor）
  - **Phase D UI** (2): ui/components/ 4 檔（macro_card / macro_card_edu / mk_dashboard / mk_clock）+ ui/helpers/session.py（_D5_KEYS / calc_data_health / init_session_state）
  - **Phase E 收尾** (3): 53 行 import 改新路徑 / 刪 17 shim + shared/ 目錄 / 更新 ARCHITECTURE / STATE / BACKLOG
  - **體積變化**：fund_fetcher.py 5290 → 593 行（-89%），根目錄業務 py 18 → 2 個，fast tier 357 → 359 passed 零回歸
  - **修順手**：v18.110 Tab4 回測 KPI 空白 bug（calc_performance_metrics 階梯式門檻 n<2/n>=2/n>=3）
  - **未完成（v12.0 backlog）**：app.py Tab 拆檔（Streamlit `with tab:` closure 限制）/ fund_fetcher.py 殘留 utility / PrecisionStrategyEngine I/O 拆分
  - **最大教訓**：(1) shim + monkeypatch 衝突需修 patch 路徑為新模組；(2) 整檔搬 + cp + 改 docstring 比 surgical edit 更穩定；(3) repositories 同層橫向 import 可接受（PolicySheetError）；(4) AST 解析型 test 必須隨檔案位置調整路徑

- [x] **v18.106 → v18.108 — Ideas 區候選 3 條再清掃**（`6b0f599` → `e545432`, pushed）— 使用者「Ideas 區請繼續」依序推進：
  - **v18.106** (`6b0f599`)：AppTest 進階場景 12 — Tab4 回測 mock NAV 注入（2 檔同 P001 / 60000+40000 invest_twd / 600 B-day NAV）→ 找到 run_backtest_btn 並 click().run() → 驗證結果區渲染 6 個 hit-words 之一（淨值擷取/年化/Sharpe/Max DD/回測結果/資料不足）；AppTest 11 → 12 cases passed
  - **v18.107** (`c0eb8b6`)：跨幣別 macro 指標 — yfinance EURUSD=X / JPY=X / CNH=X 三組 forex pair 整合進 macro_engine R 字典；macro_core.MACRO_THRESHOLDS 加 EURUSD/USDJPY/USDCNH 門檻；high_is_bad 邏輯翻轉（EURUSD 高=利多 / USDxxx 高=利空）；+1 unit test
  - **v18.108** (`e545432`)：總經指南針 Phase 4 — `rank_macro_drivers` 對 Sankey 8 節點計算與 target 在 lag_months 後 level 的 Pearson |corr|，排序回 Top-N driver；用標準 leading indicator level vs level 定義（非 delta vs delta）；UI 加 expander「📊 變數重要性 Top-N」含 target dropdown + lag slider + 🥇🥈🥉 排名 dataframe；+4 unit tests；不引入 sklearn / shap 套件
  - **總計**：3 commits / fast tier 352 → 357 passed (+5) / AppTest 11 → 12 cases / Tab1 新增第 3 個 Phase 4 expander
  - **Ideas 區候選全清掃**：(1) Tab4 AppTest ✅ (2) 跨幣別 ✅ (3) Phase 4 變數重要性 ✅

- [x] **P1 即時抓取速率限制 — live-env 觀察通過**（使用者於 prod 手動驗收）— 連按 3-5 次「重整 / 即時抓取」按鈕，yfinance / NAS proxy 無轉灰被速率限制。**結案：不需追加 client-side debounce 或退避邏輯**。

- [x] **v18.102 → v18.105 — Ideas 區全清掃（一次再掃 4 項）**（`1ff2392` → `5dc37e2`, pushed）— 使用者「請繼續，做完一個提醒下一個」依序推進：
  - **v18.102** (`1ff2392`)：`_HOLDING_ZH` 補強歐洲（DAX/CAC40/FTSE100/瑞士/北歐 ~76）+ 新興市場（土耳其/印尼/越南/南非/菲律賓/馬來西亞/中東 ~35）；撤回撞名 RIO TINTO/BHP（保留 v18.97 既有映射）；baseline 門檻 200 → 380；test_app_smoke 92 cases passed
  - **v18.103** (`0c1075c`)：Phase B-3 跨 viewport pixel-diff — `RESPONSIVE_VIEWPORTS` 三組（desktop_1440 / tablet_768 / mobile_375）+ Tab1 各自 snapshot + `test_mobile_viewport_no_horizontal_overflow` 守門 (scrollWidth ≤ clientWidth+8px tolerance)；playwright cases 4 → 8
  - **v18.104** (`bd96038`)：AppTest 進階 4 場景 — Tab2 搜尋輸入欄/按鈕存在性 / Tab6 容器層說明書章標 / T7 帳本初始 dict 型守門 / T7 seed 後 startup 不誤清；除錯：AppTest session_state **沒有 .get()** API（safe_session_state.__getattr__ raise AttributeError），改用 `in` + 索引；AppTest 7 → 11 cases passed
  - **v18.105** (`5dc37e2`)：總經指南針 Phase 3 — (A) `build_macro_sankey_dynamic` 邊粗細用 |corr|×加權（取代 Phase 2 固定 |z|），hover 顯實際 corr 值；(B) `backtest_sub_cycle_lights` expanding window 重算 z_avg 避未來資訊洩漏，分桶 🟢🟡🟠🔴 → 後 N 月 target 變化平均；Tab1 雙 expander：Sankey 動態權重 checkbox + 燈號回測 dataframe（target dropdown + forward months slider）；+4 unit tests
  - **總計**：4 commits / fast tier 348 → 352 passed（+4 unit）/ smoke 55 → 92 cases（+37 持股 hit-rate）/ AppTest 7 → 11 cases（+4 進階）/ playwright 4 → 8 cases（+4 跨 viewport）
  - **BACKLOG Ideas 區「持股對照表 / Phase B-3 / AppTest 進階 / 總經 Phase 3」全部結案**；目前可程式化項目歸零
  - **唯一未完成**：P1 即時抓取速率限制觀察 — 需 live env 手動，**程式無法代跑**

- [x] **v18.94 → v18.101 — BACKLOG 全清掃（一次掃 6 項）**（`5704702` → `a02dfce`, pushed）— 使用者要求「每個都要 但每做好一個 就提醒還剩那些沒做完」依序推進並逐項通報：
  - **v18.94** (`5704702`)：AppTest 第 3 場景 — Tab3 mock fund 注入 → KPI 4 卡（🟢 撿便宜雷達 / 🔴 留校查看警示 / 💰 停利提醒（衛星）/ ⚖️ 配置比例）回歸；補 `_mock_loaded_fund` helper，並修 v18.46 歡迎卡關鍵字 drift（「👋 歡迎」→「👋 三步驟」OR 條件）
  - **v18.95** (`93ffca4`)：AppTest 第 4 場景 — Tab1 載入入口（按鈕 / info hint）存在性；**取代** 原 Idea「Tab2 view_mode L1/L2/L3」（v17.0 已硬編單軌完整版，toggle 已廢棄）
  - **v18.96** (`4325bc4`)：AppTest 第 5 場景 — Tab5 重疊度按鈕點擊 → 計算方式 caption；注入 2 檔同 policy_id mock 基金（無 holdings → 自動降 NAV fallback）
  - **v18.97** (`5cce554`)：`_HOLDING_ZH` 補強澳紐 + 拉美區域 — +38 entries（澳紐 18 / 拉美 20）+ 19 test cases；字典從 ~277 → ~315 keys，baseline 門檻保持綠
  - **v18.98** (`2a63a08`)：三引擎 baseline 單測 — `test_engines.py` +27 cases 涵蓋 precision_engine（risk_score 5 段門檻 / composite_risk 4 分支 / build_macro_df 缺資料）、ai_engine（assign_asset_role 13 cases / _gemini 空 key + HTTP 503 mock）、fund_fetcher.calc_metrics（empty / too_short / 300 日合成 / 季配 4 筆）；補 PR #56 列為「三引擎技債」
  - **v18.99** (`c95285e`)：Phase B 升級 pixel-diff baseline — Tab1/3/4 三 screenshot 場景接 pytest-playwright-snapshot，threshold=0.1；fixture 加 chromium binary 缺失 → skip 守門；requirements-dev.txt 補 5 套件（playwright/pytest-playwright/pytest-playwright-snapshot/pillow/pixelmatch）
  - **v18.100** (`8a87ede`)：總經指南針 Phase 2 (1/2) — `calc_sub_cycle_lights` 7 子領域燈號（製造業/房市/就業/信貸/流動性/消費/通膨壓力），各取 1-2 個既有指標 z-score 平均後依 high_is_bad 翻轉 → 🟢🟡🟠🔴 四色；Tab1「📡 景氣拐點監控」之後插 4×2 卡片網格；+4 unit tests
  - **v18.101** (`a02dfce`)：總經指南針 Phase 2 (2/2) — `build_macro_sankey_data` 3 層 8 節點 9 邊（政策 → 信貸 → 實體經濟 → 市場），plotly go.Sankey 渲染於 Tab1 expander；節點色＝z_norm 健康度、邊粗細＝起點 |z|、hover 顯因果教學；+3 unit tests
  - **總計**：8 commits / fast tier 254 → 311 passed（+57）/ AppTest 5 → 7 場景 / playwright 2 → 4 場景 + pixel-diff 整合 / Tab1 新增 2 個 Phase 2 視覺區塊 / `_HOLDING_ZH` +38 entries
  - **唯一未完成**：P1 即時抓取速率限制觀察 — 需 live env 連按 3-5 次 yfinance / NAS proxy 看是否轉灰，**程式無法代跑、保留交使用者於 prod 手動驗證**

- [x] **PR #162 — v18.93：BACKLOG 收尾 — P0 驗收改 unit test + P2 Phase B playwright skeleton**（`6d88820`, merged）— 把 BACKLOG 「🚧 Next」3 個可程式化項目從「手動驗收等待」改成「自動化測試守護」：(1) **P0 Tab5 ⚠️ caption (PR #49)** — 抽出 `_parse_indicator_date(iv)` helper（app.py:256），Tab5 渲染 loop 23 行 → 4 行；test_app_smoke.py +5 cases 覆蓋合法 / 壞 date / 壞 series / 空 dict / 雙來源優先序；(2) **P0 APAC 持股中文 ≥80% (PR #43)** — `_APAC_FUND_TOP10` 字典涵蓋摩根大中華/印度/富邦日本/摩根亞太代表性 top-10 → 用既有 `_zh_holding` 跑 hit-rate 守門，三檔 ≥80% 通過、印度刻意保留 4 個未覆蓋呈現邊界（threshold 放寬 60%）；(3) **P2 Phase B playwright skeleton** — 新增 test_app_playwright.py（pytest.mark.slow + playwright 雙標記 + importorskip）2 場景：app 載入後 console error 守門 / Tab1 screenshot baseline 存 tmp；pytest.ini 註冊 playwright marker。258 passed / 1 skipped (playwright) / 4 deselected。test_app_smoke 27 → 36 cases。

- [x] **PR #161 — v18.92：修「仍無法回測」三大坑 — timeout / 降週頻 / 避 altair**（`8cebdc1`, merged）— 使用者連兩次「仍無法回測」截圖，最後附 Streamlit TypeError traceback（`st.line_chart` → `altair._config.StepKwds(TypedDict, closed=True)`）。三層修補：(1) **補抓無限重試** → `concurrent.futures.ThreadPoolExecutor + result(timeout=20s)` 硬截斷，超時走 cache 退而求其次；(2) **補抓改 opt-in** → 預設關閉「🌐 同時嘗試補抓全歷史」checkbox（fast mode），proxy 環境的使用者不會被強迫等待；(3) **cache 太短自動降頻** → 月底 resample <2 期時自動試 W-FRI 週頻；週頻再不夠就丟「指定期間」用全 cache；freq 12→52 metrics 年化基數仍對齊；(4) **altair × Python 3.14 broken** → Streamlit Cloud 的 Python 3.14 altair `TypedDict(closed=True)` 語法 broken，`st.line_chart` / `st.area_chart` 改用 plotly.graph_objects 重畫 equity/drawdown，go 已是 module-level import；(5) cache 任何長度都先收下（不再硬擋），coverage tag 改顯實際長度「cache(30d) / refetch(900d)」；完全沒 cache 提示「請至組合基金載入」。預設執行回測 cache-only <1s；opt-in 補抓每支封頂 20s（4 支 ≤80s）。27 smoke tests passed。

- [x] **PR #160 — v18.91：老師名字 → 策略 1/2/3（陳=1 / 孫=2 / MK=3）— UI + AI prompt**（`8506487`, merged）— 使用者要求「把所有老師的名字拿掉，改用策略 1、2、3 表示」。固定對應：陳重銘→策略1、孫慶龍→策略2、MK 郭俊宏→策略3。**範圍**（per user choice 「只改 UI 文字 + AI prompt」）：app.py 美林時鐘 4 段老師語音 + 三合一圖 caption + 戰情室 + Tab6 講義 + MK AI 按鈕標題 + error message；ai_engine.py 3 個 prompt 自我介紹段 + docstring；mk_dashboard.py 「郭老師白話文」expander × 3 + 80/20 metric + help text；mk_clock.py expander 標題 + 教學示意 caption；macro_engine.py 10Y-2Y 翻正 signal text。不動 function/file/variable name 與 `#` 註解。grep 確認殘留「老師/MK/郭俊宏/陳重銘/孫慶龍」全在 # 註解或 module docstring（不顯示給使用者）。27 smoke tests passed。

- [x] **PR #159 — v18.90：修「無法回測」— cache 太短時自動補抓 + 涵蓋透明化 + 門檻降至 2 期**（`1b8a1bb`, merged）— 使用者反饋「無法回測」附 Tab4 截圖（進度條「淨值擷取完成（成功 4/4）」但紅框「有效月底淨值資料不足（需至少 4 期）」）。Root cause：v18.89 解了「卡 60-120s」但暴露另一情境 — cached `fund["series"]` 常常只覆蓋幾週/幾天（初始 fetch 走 Cnyes fallback 或 MoneyDJ 部分解析失敗），月底 resample 後 <4 期 → 無法跑「近 3 年」。**Fix**：(1) `_need_min_days = target_months × 25 trading days`，cache 點數不夠 → 自動觸發 `fetch_fund_from_moneydj_url` 補抓全歷史，與 cache 合併（去重保留 last）；(2) 補抓失敗仍降階用 cache，顯 ⚠️「cache 退而求其次」；(3) 新增「📋 各基金淨值涵蓋範圍」expander 顯每支 起/迄/天數/來源（cache / refetch / 合併）；(4) 月底樣本門檻 4 → 2 期，錯誤訊息改顯「總天數 X / 篩後 Y / 三大解法」（縮短期間 / 重載基金 / 排 proxy）。預期 cache 夠 → 秒出（同 v18.89）；cache 不夠 → 補抓 progress → 出結果 + 涵蓋表；補抓失敗 → 黃色警告 + 降階。27 smoke tests passed。

- [x] **PR #158 — v18.89：修 Tab4「執行回測無反應」— 改用已載入 fund.series 不重打網路**（`972ef99`, merged）— 使用者反饋「執行回測沒有反應」附 Tab4 截圖（按保單組合 / 4 支基金 / 卡在「正在抓取 4 支基金淨值…」）。Root cause：Tab4 line 7912 檢查 `cached.moneydj_raw.nav_history` 取已載入 NAV，**但 fund 物件從未存 `nav_history` 這個 key**（資料一律放 `fund["series"]` pd.Series），cache 檢查永遠不命中 → 每支基金都掉回 `fetch_fund_from_moneydj_url` → sandbox/proxy 403 × 4-6 retry × 3-5s backoff × 4 funds ≈ 60-120s 完全靜默卡頓。**Fix**：(1) 優先用 `pf_loaded` 已有的 `fund["series"]` 直接餵 nav_data（純記憶體 <1s），index 統一 `pd.to_datetime` + `sort_index`；(2) 只在 series 缺失或長度 <4 才補抓，補抓也改讀 `res["series"]` 而非不存在的 `nav_history`；(3) `st.progress` 逐 fund 即時更新文字「[2/4] ACDD01 — 讀取已載入淨值…」，看得到進度；(4) 補抓失敗顯 `[ExceptionType] 訊息` + 「可能被 proxy 擋」，不再 silent。預期 4 支已載入基金時間 60-120s → <1s。27 smoke tests passed。

- [x] **PR #155 — v18.88：MK AI prompt 大瘦身 + RSS 清理 + 真實錯誤訊息**（`189b2c5`, merged）— 使用者反饋「其他 AI 還可以使用，但這邊的突然無法使用，是不是資料過於龐大，新聞要先處理過才能給 AI 讀取」+ 截圖看到「MK 老師建議生成失敗」。Root cause：v18.86 加 30 條新聞 × 含 RSS HTML/特殊字元 + 19 檔基金重複列 → prompt 暴增到 8000+ token，Gemini 偶爾 400/超時；且 `_gemini` 失敗回字串「❌ HTTP 400/429」app.py 沒檢查就存進 session，使用者看不到真實原因。**Fix**：(1) `_clean_news_text` 用 re strip HTML tag + html.unescape 解 entity + re.sub 統一空白；(2) news cap 從 15 條 → 8 條（5 systemic + 3 general），title 100/summary 80 字元，改一行不換行省排版 token；(3) fund snapshot **按 code dedup**（19 entry → ~7 unique code），同 code 跨保單合併 invest_twd，policies 列表顯「跨 N 保單」；cap 從 25 → 20 unique；每行縮短（拿掉 σ、policy id），留核心 配息率/1Y含息/Sharpe；(4) 預估 prompt 從 ~8000 token → ~3000 token；(5) app.py handler 加 `isinstance + startswith("❌", "⚠️")` 檢查 `_gemini` 失敗字串 → `st.error` 顯實際訊息；except 改為直接顯「[ExceptionType] 訊息」+ 三大可能原因清單（429 配額/400 prompt 超限/網路逾時）。249 fast tests passed。

- [x] **PR #153 — v18.87：MK 老師 AI 資料來源透明化 + 防禦性 deep-copy snapshot**（`8100b5d`, merged）— 使用者反饋「MK 老師的判斷不能抓取重新配置的資料，因為這資料只是給我想要重新配置的參考值」。Code 檢查結論：`analyze_portfolio_mk_advisor` 確實只讀 `_pf_t7` (portfolio_funds) + `t7_ledgers` (主帳本)，A/B/C 暫存方案存在 `t7_scenarios` 從未傳給 AI；暫存方案 submit 流程也有 snapshot/restore 把主帳本還原 → 邏輯正確。**真正問題**：UI 沒明說「分析哪份資料」使用者擔心 form 內輸入值被偷抓。**Fix**：(1) MK 按鈕上方加「🔍 分析範圍」資訊框 — 明確列「主帳本 N 檔 / 合計 NT$X / A/B/C 暫存方案 M 個（不納入分析）」；(2) 按鈕 help tooltip 改為「只分析主帳本（已落帳的實際持倉），A/B/C 暫存方案不會被納入」；(3) **防禦性 deep-copy snapshot** — 呼叫 AI 前用 `copy.deepcopy(_pf_t7)` + `_t7_snapshot_ledgers()` 再從 snapshot 重建 ledger dict，杜絕 spinner 期間任何 callback / rerun side-effect 污染 AI 看到的資料；(4) AI prompt 投資組合 section 標題加「**目前主帳本實際持倉**」+ 副標「注意：以下是使用者已經落帳的實際投入，**不包含** A/B/C 再平衡分頁中尚未提交的試算金額」。249 fast tests passed。

- [x] **PR #151 — v18.86：新聞 fetcher 加 SYSTEMIC_RISK 過濾 — 戰爭/雷曼級事件優先**（`c9e0d35`, merged）— 使用者反饋「新聞要與全球與美國或是財經相關，怕又戰爭或是雷曼兄弟事件等重大利空等系統性風險」。Root cause：原 `fetch_market_news` 只看一般財經 KEYWORDS（Fed/CPI/利率/股市），戰爭爆發 / 銀行倒閉 / 黑天鵝事件可能因不在關鍵字裡而被過濾掉。**Fix**：(1) 加 `SYSTEMIC_RISK_KEYWORDS` 60+ 條中英雙語，涵蓋戰爭/地緣政治（war/invasion/ukraine/israel/taiwan strait/missile/sanctions/nuclear/戰爭/侵略）、金融危機/破產（bankruptcy/lehman/credit suisse/svb/bank run/contagion/雷曼/倒閉/兌付危機）、央行緊急動作（emergency rate/QT halt/FDIC/bail-in）、市場崩盤訊號（circuit breaker/VIX spike/flight to safety/崩盤/黑天鵝/擠兌）；(2) 加 3 個地緣政治 / 突發新聞 RSS feed（BBC World / Reuters Top News / Bloomberg Markets）— 純財經 feed 對「戰爭爆發」反應較慢；(3) 每條 news 加 `is_systemic` tag，systemic 永遠收錄（一般財經需命中 KEYWORDS）；(4) 排序：systemic news 優先（最新→最舊）→ 一般 news（最新→最舊），cap 30 條；(5) `ai_engine.analyze_portfolio_mk_advisor` prompt 把新聞分兩段「⚠️ 系統性風險事件（最高優先級）」🚨 前綴 + 「📰 一般財經新聞」；(6) `app.py` 抓新聞後若 `is_systemic > 0` 顯紅 st.warning「🚨 偵測到 N 條系統性風險新聞（戰爭/銀行倒閉/黑天鵝事件）— 已餵給 AI 優先判讀」+ 結果區頂部 caption 標「含 N 條 🚨 系統性風險」。249 fast tests passed。

- [x] **PR #150 — v18.85：MK 老師 AI 加抓 RSS 新聞判斷系統性風險**（`dd65a54`, merged）— 使用者反饋「投資組合 AI 沒有抓取近期新聞來判斷」。Root cause：v18.81 `analyze_portfolio_mk_advisor` prompt 只給景氣位階 + 6 個總經指標，沒餵新聞 → AI「⚠️ 系統性風險警示」段只能空泛談 VIX。**Fix**：(1) 函式 sig 加 `news_headlines: list = None`；(2) prompt 新增「═══ 近期國際財經新聞（N 條）═══」section（每條 [date｜source] title + summary 摘要，cap 12 條避免爆 token）；(3) prompt 強制「⚠️ 系統性風險警示」段必須引用 1-2 條新聞；(4) prompt 第二節換股建議也要對應新聞事件（聯準會降息預期 / 地緣政治 / AI 泡沫疑慮）；(5) app.py MK 按鈕 handler 加 `fetch_market_news(max_per_feed=3)` 流程：抓新聞 spinner → 顯示「✅ 已抓 N 條」caption → 餵給 AI → 結果區顯示「📰 本次分析已納入 N 條近期新聞判斷系統性風險」。新聞抓取失敗不擋分析（degrade 為「未提供新聞」分支）。249 fast tests passed。

- [x] **PR #149 — v18.84：C 轉換 — 加強賣方多選引導文案**（`9ba8119`, merged）— 使用者確認「賣方組也可以多個，一個賣方對應多個買方，個別計算比例」設計但 hint 不夠明顯。**Fix**：(1) multiselect label 加粗「**可多選**」+ 「每個賣方下面會有自己的買方組與權重」說明；(2) help tooltip 舉例「A 賣 10% → C 100% / B 賣 20% → D 60% E 40%」；(3) 即時提示「📋 已選 N 個賣方 — 下方每個賣方獨立設定買方組 + 比例個別計算（最多可再加 M 個）」/「已選滿 5 個（上限）」。純文案調整，邏輯零變動。249 fast tests passed。

- [x] **PR #147 — v18.82-83：C 分區 + MK 搬位 + 回測按保單模式 + Tab5 資料診斷去重**（`8ccddd9`, merged）— 連續 4 個使用者反饋一次到位：(1)「C 賣方/買方放一起會看錯」→ expander 內三段式：📉 紅區（漸層深紅 + 4px 左紅邊）→ 漸層分隔線 → 📈 綠區（漸層深綠）+ 賣方標題加序號「🔁 #N」+ 買方權重總和綠/紅燈即時顯示；(2)「組合基金下方缺乏 AI 組合分析」→ root cause：v18.81 MK expander 寫在 `_panel_ph.container()` 裡而 placeholder 是在 A/B/C tabs **上方**創建的，渲染進去 = 顯示在 tabs 上方（使用者在 C tab 操作完往下看當然看不到），搬出 placeholder dedent 到 col 12 後 expander 渲染在 A/B/C 下方 + 加紫色 banner 標題卡片 + 「🗑️ 清除上次結果」按鈕；(3)「回測請以保單為一個組合個別回測」→ Tab4 加 radio：🎯 按保單組合（推薦）/ 🔧 自訂選擇，按保單模式選保單 → 自動納入該保單所有已載入基金 + 按 invest_twd 比例配權重 + 即時 dataframe 預覽（代碼/名稱/投資金額/權重）+ 權重 readonly st.metric 顯示；(4)「基金資料診斷很多重複，移除重複只保留單一」→ Tab5 按 code dedup（19 筆 → 7 unique）+ caption「移除 N 筆同 code 跨保單重複」+ expander 標題加標籤「· 共 N 保單共用」讓使用者知道該 code 跨幾張保單。249 fast tests passed。

- [x] **PR #145 — v18.81：T7 三件套大改（P&L bug + A 新投入多選 + MK 老師深度建議）**（`2c801dc`, merged）— 使用者貼 T7 截圖反饋三件事一次來：(1)「整體未實現損益 (TWD) 計算有錯」全表 +0.00% 報酬率；(2)「新投入也讓我可以多選標的，由保單先選，再來選標的」；(3)「ETf 組合下方也需要放一個 MK 老師的建議」涵蓋缺點 / 換股 / 配置 / 高賣低買 vs 跌就買 + 系統性風險。**Fix**：(a) v18.81-A — auto-estimate 原本用 `_d_t7.today()` 與 latest NAV 當 cost basis → cost = current → P&L 永遠 0。新增 `_nav_at_date_t7(fund, date_str)` helper (pd.Series.asof) 取**投資日期當天 NAV** 做 cost、subscribe 用該日期，cost_unit ≠ current NAV → 真實 P&L 浮現；既有 ledger 守護不覆寫（要重估按重置帳本）；(b) v18.81-B — A 新投入單一 selectbox 改 policy selectbox + fund multiselect（必須放 form 外才能 reactive），form 內動態 render 每檔 number_input + 「📊 合計投入 NT$X,XXX」即時加總，submit handler 改 loop subscribe + sheet rows batch sync，暫存/直接套用兩種落帳都支援多檔；(c) v18.81-C — 新函式 `ai_engine.analyze_portfolio_mk_advisor(api_key, pf, phase, ledgers, ind)` 強制 4 節結構化 prompt：🚨 3 大缺點 / 🔄 對應景氣位階的換股 / ⚖️ 核心衛星現金 % / 🎯 高賣低買 vs 跌就買 + ⚠️ 系統性風險警示根據 VIX/T10Y2Y 給結論；位置：T7 帳本下方獨立 expander 預設收合，紅燈提醒先載總經。249 fast tests passed。

- [x] **PR #143 — v18.80：幣別中英對照 — 修「美元/台幣」中文名讓保底匯率永遠找不到**（`4f8eb0e`, merged）— 使用者第三次反饋「仍無法同步」附 T7 截圖：最新 NAV 欄有值（75.33/8.50/393.94 等）但最新 FX 欄全表「—」、KPI 仍 NT$0、warning「19 檔需估算但 NAV 抓不到」。Root cause：v18.76 加的 `_FX_FALLBACK = {"USD": 32.0, ...}` 字典 key 是 ISO，但使用者帳本 currency 欄存中文「美元」「台幣」，`str(_fund.get("currency")).upper()` 對「美元」`.upper()` 還是「美元」，`_FX_FALLBACK.get("美元")` 永遠 None → 全部 19 檔 fx 仍 0 → skip。**Fix**：加 `_CCY_NORMALIZE` 字典涵蓋台灣理財平台常見中文幣別名（美元/美金→USD、歐元→EUR、港幣/港元→HKD、日圓/日元→JPY、澳幣/澳元→AUD、英鎊→GBP、人民幣/CNH→CNY、台幣/新台幣/新臺幣→TWD、瑞郎/瑞士法郎→CHF、新幣/新加坡幣/星幣→SGD、加幣/加元→CAD、紐幣/紐元→NZD、蘭特/南非幣→ZAR）+ `_norm_ccy(raw)` helper 同時接受中英輸入回 ISO 3 碼，套用在 `_latest_nav_fx_t7` + `_ledger_for` + auto-estimate ledger 創建三處。預期 T7 自動估算 success「⚡ 自動估算 19 檔」、最新 FX 顯 32.0000（USD）/ 1.0000（TWD）、KPI 全部有數字。249 fast tests passed。

- [x] **PR #141 — v18.79：「載入所有未載入基金」改用 st.status + progress bar 即時顯示進度**（`b12ed96`, merged）— 使用者反饋「無法正常下載 試了很多次，都沒有動作」並截圖顯示「📡 載入所有未載入基金（19 條 entry / 7 unique）」按鈕。Root cause：button 確實有觸發，但 `for code in unique_codes: with st.spinner(...): fetch(...)` per-iter spinner 在 Streamlit 不會增量重繪，每檔 fetch 30s+ × 7 unique ≈ 3.5 分鐘，`st.rerun()` 在迴圈尾才呼叫 → 期間整頁 UI 完全靜止，使用者誤判為壞掉。**Fix**：改成 `with st.status(...) as _ld_status: + st.progress(0.0)`，每抓完一檔即時 `st.write(f"✅ {code} {name}" / "❌ ...")` + `_ld_prog.progress((i+1)/n)`，完成後 `status.update(state="complete", expanded=False)` 自動收合。整體 fetch 時間不變，但 UX 從「凍 3.5min」→「持續看到進度條跑 + 逐檔 ✅/❌」。249 fast tests passed。

- [x] **PR #139 — v18.77-78：三合一圖買賣價 sanity check + AI 按鈕紅燈可 override**（`b91533a`, merged）— 使用者連發兩張截圖反饋：(1) 單一基金「三合一趨勢診斷圖」JFZN3 NAV=75.33 但 MK 6 條買賣線跑到 5.2~6.1（差 13x），完全錯位；(2)「單一基金下方的 AI 決策按鈕不見了」— 截圖顯示紅燈阻斷訊息存在但「🤖 AI 基金分析」按鈕完全消失。**Root cause**：(a) `fetch_basic` 解析 wb01 表格「年最高/最低淨值」時欄位錯位（境外月配型常見：解析到報酬率/配息率欄位的值），`calc_metrics` 沒做合理性檢查直接套用 σ 公式 → 買賣線完全偏離；(b) 原 `if _ai_fd_pct < 50` 紅燈路徑只顯示阻斷訊息，整段 `else` 分支才畫按鈕，紅燈時按鈕完全 unreachable。**Fix**：(1) v18.77 — `calc_metrics` 加 sanity：`_yh / _yl` 偏離當前 NAV 0.3x~3x 範圍 → 判定解析錯誤 fallback NAV 序列 2Y 高低點，console 印 ⚠️ 警告；(2) v18.78 — 紅燈時改顯示阻斷說明 + override checkbox「略過阻斷 — 僅用基金本身資料分析」，勾選後按鈕 enabled，label 改「🤖 AI 基金分析（無總經背景）」，help tooltip 提示「先載入總經」。預期 JFZN3 6 條買賣線從 5.2~6.1 → NAV 70~80 區間；紅燈時 AI 按鈕仍可見可勾用。249 fast tests passed。

- [x] **PR #137 — v18.76：T7 自動估算加幣別保底匯率 — 救「FX 抓不到全部 skip」**（`b95f663`, merged）— 使用者反饋「資料仍不同步」附兩張截圖：(1) 投資組合 19 檔 invest_twd 都有值、買入匯率全 0；(2) T7 帳本「持有單位 / 市值 / 配息率」全表「—」、最新 NAV 有值（從 Cnyes fallback 抓到 75.33 / 8.50 / 9.51 / 309.82 ...），但最新 FX 全「—」。Root cause：`_latest_nav_fx_t7` 三層 fallback 都失效 — (a) `_fx_now("USDTWD=X")` 是 yfinance 呼叫，使用者環境被擋回 None；(b) `_fund.fx_rate` = 0（買入匯率沒填）；(c) `ledger.fx_avg` = 0（ledger 還沒 units，這正是要估算的對象）→ 整批 `if _fx <= 0: continue` skip，19 檔全部 KPI 歸 0、顯「⚠️ 19 檔需估算但 NAV/FX 抓不到」。Fix：加 `_FX_FALLBACK` 幣別字典常數 `{USD:32, EUR:34.5, HKD:4.1, JPY:0.21, AUD:21, GBP:40, CNY:4.45, CHF:36, SGD:24, CAD:23.5, NZD:19.5, ZAR:1.75}` 作為最終一道 fallback；估算 success message 加註「FX 抓不到會用保底匯率，可在編輯持倉改 fx_at_buy 校準」；warning message 改成「NAV 抓不到」（FX 已不該是擋點）。預期 T7 KPI 從「已計入 0 / 19 檔」變「19 / 19」。249 fast tests passed。

- [x] **PR #135 — v18.75：Google 登入 UI 搬到左側 sidebar**（`26c0062`, merged）— 使用者反饋「google 登入改到 左邊 slider 的頁面」。原本登入按鈕埋在 Tab3 →「📋 保單管理」expander 內，需先切分頁才看得到，登入入口太深。**Fix**：(1) 把 OAuth 設定解析（`_resolve_oauth_cfg / _oauth_cfg / _oauth_configured / _get_oauth_client`）和 callback handler（URL 帶 `?code=...` 自動換 token）從 tab3 內 hoist 到 module level，sidebar 與 tab3 共用同一份；(2) sidebar「♻️ 強制同步」按鈕下方新增「🔐 Google 帳號」區塊 — 已登入顯綠 badge + 全寬「🚪 登出」、未登入顯「🔐 用 Google 登入」link button、未配置顯提示去 Tab3 設定、SA 模式顯 caption；(3) Tab3 內認證 UI 改成純狀態指引（登入/登出操作一律走 sidebar，不再有第二個按鈕避免混淆）；(4) 5 步驟 GCP wizard 留在 Tab3 expander（含三個 text_input + 引導文字，搬 sidebar 會擠版面）。249 fast tests passed。

### 2026-05-15（後續修補：PR #71 → #133）
- [x] **PR #133 — v18.72-74 三合包：hover 來源標籤 / T7 429 配額修復 / C 卡保單卡控**（`a7345ce`, merged）— 使用者反饋三件事一次處理：(1) Tab2 健康矩陣看不出 1Y 含息來自 wb01 還是新還原淨值法 → hover 加「來源：MoneyDJ wb01（官方含息）/ 還原淨值法（本地，v18.71）/ ret_1y（純 NAV）/ NAV 序列年化」標籤 + `scripts/compare_wb01_vs_local.py` 一次性對照腳本；(2) T7「📦 全部寫入 Sheet」按下後紅框「⚠️ _T7_State 寫入失敗：Quota exceeded」— `ledger_snapshot_store.save_all_ledgers_snapshot` 用 `delete_rows + append_row` 迴圈，N 檔 = O(M+N) API call → 改成單次 `ws.clear()` + 單次 `ws.update(range, values)` batch，加 1s/2s/4s/8s 指數退避 helper（只對 429/Quota/RATE_LIMIT 重試）；17 檔情境 API call ≈ 37 → 5 次；附帶 Tab B 投入再平衡權重欄 label 加基金名稱（`{pid}/{code}｜{name_short}`）；(3) C 轉換再平衡兩個問題 — 試算後紅框「name '_sell_codes' is not defined」是 `_sell_pks` typo（`t7c_sell_codes` 是 widget key 字串），改名；使用者要求「同一保單號碼才能互轉」於 C 卡頂部加「1️⃣ 先選保單號碼」selectbox，賣方候選只列該保單下有部位、買方候選只列同保單任意基金，切保單時 multiselect key 含 `_sel_pid` 自動 reset 避免殘留跨保單 pk。test_ledger_snapshot_store 3 個舊案改 assert clear+update。249 fast tests passed。

### 2026-05-15（後續修補：PR #71 → #131）
- [x] **PR #131 — v18.71：含息報酬率改用還原淨值法（配息再投資複利）**（`58a91fc`, merged）— 使用者提供「國內基金含息報酬率計算指南」參考資料，指出舊版單利加總 `(NAV變化 + Σdiv)/base` 與 MoneyDJ wb01 官方含息值有 ±2~5pp 差距（主因：配息再投資複利 vs 單利、配息頻繁的境外月配型如 JFZN3 影響最大）。**改動**：(1) 新增模組級 `calculate_fund_total_return(nav_df, div_df)` 函式，向量化還原淨值法 — `Factor_t = 1 + D_t/NAV_t` → `Cum_Factor = ΠFactor` → `Adj_NAV = NAV × Cum_Factor`，回完整 DataFrame；(2) `calc_metrics` 內 `ret_1y_total` 計算改呼叫上述函式，取 `Adj_NAV_end/Adj_NAV_start − 1`；(3) `perf["1Y"]` 注入鏈順序不變（wb01 仍第一順位），短窗口 window_days 邏輯不變。**邊界**：空表 / 累積型 (Adj==NAV) / NAV≤0 或 NaN → Factor=1 防 inf / 配息日落非交易日 → merge 補 0。test_fund_metrics.py 9 → 13 case (新增 4 個 calculate_fund_total_return 直接單元測試 + 改寫 2 個舊測試期望值)。249 fast tests passed。
- [x] **PR #129 — v18.70：「遊戲存檔風格」UX 重構 — 4 動作清晰化**（`2c0ad62`, merged）— 使用者反饋「請重新設計 全部檢視一下」+「JSON 備份應在 Sheets 旁」+「上下資料不同步」+「應該像打遊戲：新增 / 存檔 / 讀取 / 編輯」。**重構 4 段**：(1) 存讀整合 — 「📋 保單管理」expander 內加 JSON 備份 4 大按鈕區（☁️ 全部寫入 / ☁️ 全部讀回 / 💾 下載 JSON / 📂 上傳 JSON），全部存讀動作一處看完；(2) T7「💾 帳本存檔...」expander 整段移除 -165 行（Sheet ID 顯示 / Sheets 直連登入 / 雲端狀態 / JSON 下載上傳全併入上方）；(3) T7「✏️ 編輯持倉」改成 expanded=True 預設展開，標題加圖示，使用者反饋「修改地方藏太深」→ 永遠可見；(4) 下方 KPI 加 invest_twd fallback — ledger 空但 invest_twd 有值時顯「⚠️ 近似 NT$13.65M」+ help 引導用「⚡ 自動估算」，避免上下視覺斷層。Upload 還原後 pop _t7_auto_restore_done flag 讓 T7 重新對齊。淨減 ~48 行。245 fast tests passed。
- [x] **PR #127 — v18.69：T7 自動估算改 fund-level 冪等 — 移除 session flag 卡住問題**（`5b7b7c6`, merged）— 使用者反饋「自動估算 沒有看到」。Root cause：v18.68 的 session-level `_t7_auto_estimate_done` flag 有副作用 — 第一次進 T7 若 NAV/FX 抓不到 → `_auto_est_count = 0` 但 flag 設 True，後續即使 NAV/FX 補到也不再嘗試。Fix：移除 session flag，改 fund-level 冪等（`ledger.units > 0 → skip` 既保護手動值又防重複），每次 rerun 重檢所有 fund，後續抓到 NAV/FX 也能補估算。診斷加強：計數 NAV 抓不到的 fund、估算成功時用 st.success（比 st.info 更顯眼）、全部抓不到 NAV 顯 st.warning + 引導「🗑️ 清空抓取快取」。245 fast tests passed。
- [x] **PR #126 — v18.68：T7 entry 自動估算單位 — 上下 KPI 自動對齊**（`ac625a6`, merged）— 使用者截圖：上方核心戰情室「總資產 NT$13.65M」(invest_twd) vs 下方 T7 帳本「組合當前市值 NT$0」(ledger.units × NAV × FX)；19 檔基金「持有單位 / NAV / FX 全 —」KPI footer 寫「未計入 19 檔」。v18.66 的「⚡ 自動估算」按鈕需手動按，使用者要求自動同步。**Fix**：把 v18.66 estimation block 從手動按鈕改為 T7 entry 自動觸發（用 `_t7_auto_estimate_done` flag 防重複；v18.69 移除）。「📥 全部讀回」流程同步 pop flag。245 fast tests passed。
- [x] **PR #125 — v18.67：全局指標關聯地圖 Sankey 縮小（高度 400→220）**（`328f7f8`, merged）— 使用者反饋「這縮小，太大了」— 全局指標關聯地圖 Sankey 在 Tab1 頂部佔太大版面。Fix：height 400 → 220 (-45%)、字體 size 12 → 10、node pad 20→10 / thickness 20→14、margin top/bottom 30/10 → 8/4。仍保持 7 個節點標籤可讀。245 fast tests passed。
- [x] **PR #123 — v18.66：T7 ⚡ 從 invest_twd + 最新 NAV/FX 自動估算單位 — 救「上方有資料下方空」**（`e9bf572`, merged）— 使用者反饋「上方抓取存檔有抓到所有資料，但下方帳本都是空的，請連動並保留一種存讀取格式」。Root cause：T7 帳本「持有單位 / 平均 NAV / 平均匯率」必須從 CHUBB 對帳單手動輸入，app 抓不到個人持倉。Fix：T7「📝 編輯初始持倉」form 上方加偵測「invest_twd > 0 且 ledger.units = 0」+ 顯示 info caption 告知「N 檔基金可估算」+「⚡ 自動估算填入」按鈕一鍵：units = invest_twd / (latest_nav × latest_fx)，建立 _LedT7 + .subscribe() 寫進 t7_ledgers + _sync_invest_twd_from_ledgers + _t7_save_snapshot_to_sheets 自動 dump _T7_State。已有手動輸入值 (units > 0) 不覆蓋。245 fast tests passed。
- [x] **PR #122 — v18.65：短窗口含息不再年化 + Tab3 矩陣 wb01 真 1Y 優先**（`7baf979`, merged）— 使用者問「JFZN3 含息 51% vs 之前 wb01 的 15% 差很大」+「累積型不配息為何有 311% 含息」。Root cause：(a) v18.55 把 Tab3 矩陣 fallback chain 改成 ret_1y_total（本地年化）優先，覆蓋境外 wb01 真 1Y；(b) v18.61 cap 12× 讓 30 天 NAV 漲 25% 變 300% 假象。Fix：(1) calc_metrics 短窗口（< 252 點）改回「累積實值不年化」+ 新增 ret_1y_window_days 欄位；(2) _finish_metrics 注入 perf["1Y"] 條件加「window_days >= 350」（避免短窗口累積被當 1Y）；(3) Tab3 矩陣 fallback chain 改回「perf["1Y"] (wb01 真 1Y) → ret_1y → ret_1y_total → NAV」順序。預期 JFZN3 顯 ~15%、累積型 30 天歷史顯 25%（不再 300%）。新增 test_ret_1y_total_full_year_marks_window_365、改寫 short_window 測試從「年化驗證」→「累積實值驗證」。244 → 245 fast tests passed。
- [x] **PR #121 — v18.64：政策 DataFrame 表頭改顯繁體中文**（`5c6c5a5`, merged）— 使用者反饋表格欄位仍是 policy_id / policy_name / fund_url 等英文。改用 st.column_config 9 個欄位映射繁中（保單編號 / 保單名稱 / 基金代碼 / 投資金額 (TWD) / 投資日期 / 幣別 / 買入匯率 / 備註 / 配置定位）。schema 仍英文，向後相容。244 fast tests passed。
- [x] **PR #120 — v18.63：移除「保單分頁」管理區塊 — 簡化主流程**（`2f21ac7`, merged）— 使用者反饋「保單分頁這區塊移除」— 該區塊（建立/選取/管理 per-policy worksheet）功能與「批次加入」+「📦 全部寫入」自動流程重複。移除 ~114 行：「📌 從投資組合代入或輸入新號碼」/「➕ 建立保單分頁」/「選擇保單分頁進行管理」/「🗑️ 從此保單移除選中基金」/「⚠️ 刪除整個保單分頁」。import 清理 4 個函式 (delete_fund_in_policy / delete_policy_worksheet / ensure_policy_worksheet / load_policy_worksheet)。簡化後流程：建立保單分頁 → 「📦 全部寫入」自動建；修改基金 → T7「📝 編輯初始持倉」+ 寫入；刪整個保單 → Google Sheets UI 直接刪 tab。244 fast tests passed。
- [x] **PR #119 — v18.62：「➕ 批次加入」按鈕加 next-step 提示 + textarea 縮短**（`fe9ca76`, merged）— 使用者截圖反饋「沒有將標的下載的鈕」— 貼了 ACCP138 在 textarea 後找不到下載按鈕，因 textarea(h=120) + 預設保單 input 把按鈕擠到手機 fold 下方。Fix：textarea 高度 120 → 75；按鈕標籤改「➕ 批次加入（加完按上方「📡 載入所有未載入基金」抓資料）」明示下一步；caption 加強流程提示。244 fast tests passed。
- [x] **PR #117 — v18.61：calc_metrics 用 len(s)≥20 為主 trigger + Tab2 KPI 含息優先**（`24cba1f`, merged)— 使用者部署 v18.60 後 ACCP138 (境內，30 NAV) Tab2 仍顯「1Y 含息報酬 —」+「資料不足」。Root cause：(a) `calc_metrics` 用 `hasattr(s.index[-1], "to_pydatetime")` 守護 days_span，某些 NAV source 回非 DatetimeIndex → days_span=0 全跳過；(b) Tab2「吃本金檢查」KPI fallback 鏈 NAV 序列門檻 130 點（6 個月），30 點 ACCP138 卡掉。**Fix**：(1) calc_metrics 主要 trigger 從 `_days_span >= 30` 改成 `len(s) >= 20`，days_span 用 `pd.to_datetime` 強制轉換 失敗則用 `len(s)×1.4` 估算，短窗口 scale 加 cap 12× 防呆；(2) Tab2 KPI fallback 重排對齊 Tab3 v18.55 含息優先順序（`ret_1y_total` → `perf["1Y"]` → `ret_1y` → NAV ≥ 20 點），NAV fallback scale 也 cap 12×。加 print log 方便部署後從 Streamlit Cloud logs 驗證。244 fast tests passed。
- [x] **PR #115 — v18.60：含息門檻 60→30 + 載入前自動清快取**（`e0e94d8`, merged）— 使用者部署 v18.59 後仍回報「含息報酬率沒有」截圖 Tab5「Sharpe(1Y) ✅、淨值歷史筆數 ✅、1Y含息報酬 ⚠️缺失」。Root cause：(a) 30 trading days 約 42 calendar days，v18.59 的 60 日門檻仍卡掉境內極短 NAV 歷史；(b) v18.58 module-level TTL cache 跨 Streamlit hot-reload 仍存活，使用者部署 v18.59 後若 15 min 內已抓過，新 calc_metrics 邏輯吃不到。**Fix**：(1) calc_metrics + Tab3 NAV fallback 門檻 60 → 30 自然日（30 日年化噪音較大但「有近似值」比「灰柱資料不足」實用）；(2) Tab2「📡 載入資料」+ Tab3「📡 載入所有未載入基金」按鈕點下去前自動 `clear_all_caches()`，確保 fresh fetch 不被 cache 攔截舊邏輯。test_ret_1y_total_too_short n_days 30→15、新增 test_ret_1y_total_30_day_window。243 → 244 fast tests passed。
- [x] **PR #113 — v18.59 三合包：含息門檻 60 日 / T7 持倉診斷 / 標題改名**（`d5658e7`, merged）— 使用者回報 (1) 4 個境內基金 (ACTI71 / ACDD01 / ACDD19 / ACTI94) 真實收益矩陣仍灰柱「1Y 資料不足」、(2)「重新 Loading 後持倉變 0」、(3) Label「平均買入 NAV (美元)」希望改名。**Fix**：(a) 含息年化門檻 90 → 60 自然日（`calc_metrics._days_span` + Tab3 NAV fallback `_d_actual`）救境內 NAV 短歷史；(b) T7「📝 編輯初始持倉」頂部加診斷 caption「{n_funds} fund / {n_ledgers} ledger / {n_match} 條匹配」+「🧹 清理孤立 ledger」按鈕，根因是 v18.56 前舊版 ledger 用 code 單鍵存的，遷移到複合鍵 `pid::code` 後只有 first_pid 能匹配；(c) 「平均買入 NAV」→「平均買入淨值 NAV」3 處同步。test_ret_1y_total_too_short 描述同步從 90 → 60。243 fast tests passed。
- [x] **PR #111 — v18.58：模組層 TTL 快取 + Tab3 batch dedupe — 同 code 跨保單只抓一次**（`d4060e1`, merged）— 使用者問「不同保單相同標的，是否可以共用標的資訊，不需重複抓取」+ 要求全區稽核。經查實況 19 筆 / 7 unique → 每 (code, pid) entry 各打一次 HTTP（JFZN3 抓 4 次、ACDD19 抓 3 次等），浪費 2.7×；T7 帳本 19 funds × 8 call site = 152 個 NAV+FX 呼叫，FX (USDTWD) 對每檔 USD 基金重打；Tab1 macro compass 每次 widget rerun 抓 ^VIX/^TNX/^GSPC。**A** 寫模組層 `_ttl_cache(ttl_sec, maxsize)` 裝飾器套到 6 個 fetch 函式（`fetch_fund_from_moneydj_url` 900s / `get_latest_nav` 300s / `get_latest_fx` 300s / `fetch_yf_close` 600s / `fetch_fred` 1800s / `fetch_macro_compass` 300s），跨 Streamlit rerun 共享、自帶 `cache_clear` + `cache_info`、註冊進 `_CACHE_REGISTRY` 統一管理、防 unhashable args；**B** Tab3 兩個 batch site 預先 dedupe by unique code，「批次加入」+「📡 載入所有未載入基金」按鈕標籤改顯「N 條 entry / M unique」；**C**「📋 保單管理」加「🗑️ 清空抓取快取」按鈕 + 即時 cache hit-rate 顯示。預期：Tab3 19→7 HTTP（2.7×）、T7 render 19 NAV+19 FX → 7 NAV+1 FX（≈5×）、Tab1 切換間 0 HTTP。`conftest.py` autouse fixture 防 mock test 互相污染。`test_fetch_cache.py` 新增 10 case。233 → 243 fast tests passed。
- [x] **PR #109 — v18.57：Tab5「1Y含息報酬」加資料來源標籤**（`25335cb`, merged）— 接 v18.55 含息 fallback 鏈完工，使用者要求能一眼看出資料來自 wb01（境外 MoneyDJ 官方）/ local_calc（境內 v18.53+ NAV+配息自算）/ cache 救援（v18.55 救已快取 session_state）。標籤格式：`1Y含息報酬 [wb01]` / `[本地]` / `[本地·cache]` / 無標籤。perf_source 抓不到時 fallback 到無標籤格式（不爆 None+str concat）。233 fast tests passed。
- [x] **PR #108 — v18.56：sync_policies_to_portfolio_funds 改用複合鍵 — 救「19 筆讀回變 7 檔」**（`84098db`, merged）— 使用者實測：Excel 19 筆跨 4 保單（7 個 unique code），存進 Google Sheet 後按「📥 全部讀回」portfolio_funds 變成只剩 7 檔 3 保單。Root cause：`sync_policies_to_portfolio_funds` 第 316 行 dedupe 鍵用 `code` 單鍵，函式 docstring 自己標註「v1 暫合併，t7_ledgers 複合鍵升級交給 P2」— P2 改了 T7 但 sync 函式漏跟（PR #64 / v18.31）。Fix: aggregation key 從 `code` → `(policy_id, code)` 組成 pk_str，`cur_by_code` → `cur_by_pk`，`report["added"/"kept"/"removed"]` 改用 pk_str 格式（如 `"P1::AAAA"`）UI caption 顯示「在哪保單」更明確。同 `(pid, code)` 邊界（Sheet 內重複行）仍 invest_twd 加總。測試重寫：移除 `test_sync_aggregates_same_code_across_policies`（v1 語義已失效），新增 `test_sync_preserves_same_code_across_policies` + `test_sync_aggregates_dup_rows_same_pk`。232 → 233 fast tests passed。
- [x] **PR #106 — v18.55：短 NAV 含息年化 + Tab5/Tab3 fallback 救 ACTI71 1Y 無法判定**（`a57bea6`, merged）— 使用者刷新 Streamlit Cloud 後反饋 ACTI71（聯博）「含息報酬抓不到，依舊吃本金」截圖：Tab5「1Y含息報酬」⚠️缺失、Tab3 真實收益矩陣 ACTI71 灰柱「1Y 資料不足 無法判定」。Root cause：v18.53 含息計算需 NAV ≥ 252 日才觸發，但境內基金常只抓到 30~250 日（FundClear/TCB MoneyDJ 範圍變動），`ret_1y_total = None`、perf["1Y"] 也補不上。三段修正：(a) `calc_metrics` 含息改用「窗口年化」— NAV ≥ 252 走原邏輯，90 ≤ days_span < 252 取 `s.iloc[0]` 為期初 + scale = `365/days_span`、累積配息只算窗口內、< 90 自然日仍 None；(b) Tab5「1Y含息報酬」fallback 鏈 `perf["1Y"]` → `metrics.ret_1y_total`（救已快取 session_state，wb01報酬資料欄維持嚴格 perf["1Y"] 保留來源辨識）；(c) Tab3 真實收益矩陣 fallback 順序調整為「含息優先」`ret_1y_total → perf["1Y"] → ret_1y → NAV 序列年化`（原序純 NAV 排第一導致境內含息被忽略）。test_fund_metrics.py 新增 3 case（full_window / short_annualized / too_short）。229 → 232 fast tests passed。
- [x] **PR #104 — v18.54：移除 T7 重複的存檔/讀取雙鈕 + 批次加入改 2 步驟教育**（`9ba6256`, merged）— 使用者反饋「下方帳本的資料 要整合在上方的存檔吧 不燃我每次讀取資料，裡面都空的 只有基金標的」。其實 v18.50/52 已把 T7 部位整合進上方「📦 全部寫入 / 📥 全部讀回」，但 T7 expander 內仍保留同名「💾 存檔到 Sheets / 📥 從 Sheets 讀取」雙鈕造成混淆。Fix: (a) 移除 T7 內這對雙鈕（保留自動還原 + 本機 JSON 備份）；(b) 改顯 info 提示「存讀統一在上方」+ 雲端 _T7_State 列數 / 最後同步時間；(c) 「➕ 手動加入基金」caption 改成「2 步驟流程：貼代碼 → 下方 T7 編輯持倉 → 上方一鍵存」。229 fast tests passed。
- [x] **PR #102 — v18.53：境內基金 1Y 含息報酬本地計算 + Tab5 累積型 N/A 標示**（`688af3b`, merged）— 使用者截圖 Tab5 資料診斷顯示：境外基金（JFZN3 / TLZF9）大多 ✅ 完整，境內基金（ACCP138 / ACTI71 / ACDD01 / ACDD19）皆 ⚠️「1Y含息報酬」+「wb01報酬資料」缺失。Root cause：MoneyDJ `wb01.djhtm` 是**境外基金專屬頁**，境內 fund 走 `_fetch_domestic_perf` 取 yp020000 但 MoneyDJ 常顯 N/A。**Fix**：(a) `calc_metrics` 新增 `ret_1y_total` 欄位：本地用 NAV 變化% + 過去 365 日累積配息 / 1Y NAV × 100 計算（累積型 divs=0 → 含息=NAV change；配息型 → 加回現金配息）；(b) `_finish_metrics` + 另兩處 calc_metrics call site，若 `perf["1Y"]` 為 None 自動注入 ret_1y_total，並標 `perf_source="local_calc"`；(c) Tab5 偵測累積型基金（名稱含「累積」「智慧」「Accumulation」或 dividend_freq 寫「不配息」）→「年化配息率」「配息記錄筆數」改顯「ℹ️ N/A 不適用」灰標而非「⚠️ 缺失」橘標，並於 expander 頂部加 caption「ℹ️ 此基金為累積型 / 不配息」；(d) `_d5_cell` 多識別 `"N/A"` sentinel 字串。連動：Tab2 健康總覽 / 吃本金 KPI / Tab3 真實收益矩陣 都會自動拿到非零含息報酬。229 fast tests passed。
- [x] **PR #100 — v18.50 + v18.51 + v18.52 三合包：帳本內容速覽 + 配息抓取修復 + NameError**（`4a4ad92`, merged）—
  - **v18.50**：使用者反饋「Google sheet 內容很怪，不同按鍵存取位置都不同」（同一筆保單散在 per-policy worksheet / `_T7_State` / `_Ledgers` 三 tab，看不出全貌）。「📋 保單管理」expander 內：(a) 加 3 metrics「保單分頁 / 部位快照 / 交易流水」即時顯示三本 tab 各幾列；(b) 「📦 全部寫入 Sheet」串 `upsert_fund_in_policy` × N + `save_all_ledgers_snapshot` 一次寫齊；(c) 「📥 全部讀回」串 `load_all_policy_worksheets` → `sync_policies_to_portfolio_funds` + `load_all_ledgers_snapshot` 一次讀齊；(d) `load_all_ledgers` 加入 import；(e) 保留「🔄 重新整理分頁清單」作次級選項。
  - **v18.51**：使用者截圖證實 `www.moneydj.com/funddj/yp/funddividend.djhtm?a=ACCP138`（翰亞）/ `?a=ACTI71`（聯博）主站有完整配息表，但 app 抓不到。Root cause：`_src_tcb_div` loop 先試 `tcbbankfund.moneydj.com` 子網域，該子網域對部分境內代碼**只回表頭、無資料列**，原邏輯只檢查「`配息基準日 in r.text`」就 `break`，導致 `www.moneydj.com` fallback 永遠不啟動 → `dividends` 為空 → 配息率 / 含息報酬率全空 → Tab2 健康總覽 + 吃本金 KPI + Tab3 真實收益矩陣全失靈。Fix: 把 parse 搬到 loop 內，**只在解析出非空 divs 才 return**；境內候選加 `wb05.djhtm` 次援。
  - **v18.52**：使用者截圖：T7「📥 從 Sheets 讀取」報「name '_sync_invest_twd_from_ledgers' is not defined」+ 保單管理「📥 全部讀回」回的資料只有名稱、沒有單位數 + 「新增 / 更新基金到 XXX (fund_url 為主鍵)」表單與上方批次加入 + T7 編輯初始持倉重複。Fix: (a) `_sync_invest_twd_from_ledgers` 從 T7 nested def hoist 到模組層 (line 358) — 原本 Python sequential 找不到尚未定義的內層 def，呼叫即 NameError；(b) 保單管理「📥 全部讀回」 _T7_State 載回後自動呼叫 sync 讓 invest_twd 從 ledger 灌回 portfolio_funds，並 pop `_t7_auto_restore_done` flag 讓 T7 進入時可重新生效；(c) 把保單分頁內 8 欄輸入表單替換成「下拉選基金 + 🗑️ 移除選中 / ⚠️ 刪整個保單」雙小鈕，配 caption 指引「加入用上方批次、編輯單位數用下方 T7」。229 fast tests passed throughout。
- [x] **PR #98 — v18.48 多帳本管理 UI + v18.49 配息率 divs 歷史 fallback**（`b02e62f`, merged）— (48) 「📋 保單管理」內新增「📁 多帳本管理」區，3 個 sub-tabs：🆕 建立另一本 / 📝 改名目前帳本 / 🔁 切換到別本（filter 掉目前這本）；用途為不同人/帳戶各自一本 Sheet。(49) 配息率 fallback 加第 3 層：從 `divs[]` 12 個月歷史推算（amount 累加 / 現價 × 100），套用 Tab2 健康總覽 + 吃本金 KPI + Tab3 真實收益。
- [x] **PR #97 — v18.48 HOTFIX：補推 policy_store.rename_sheet / get_sheet_title**（`c15b354`, merged）— PR #96 app.py 多了 import 但 policy_store.py 改動沒一起 commit → ImportError 起不來。補推救部署。
- [x] **PR #96 — v18.48：1Y fallback 日期版 + Tab3 真實收益分「真 0%」與「資料不足」**（`ea5e4ec`, merged）— 使用者觀察：「組合中與單一基金同檔基金，組合中顯示，難道組合配息也誤判?」對。Tab3 寫 `_ret = ... or 0` 缺資料當 0 觸發吃本金 → 修。新增 `_rc_real` is_real 旗標 + 第 4 個 KPI「⬜ 1Y 資料不足」+ 灰色標註；Tab2 v18.47 NAV fallback 從筆數版 → 日期版 救週/月頻 NAV。
- [x] **PR #95 — v18.47：Tab2 基金健康總覽大卡（4 維度評分 + Overall Grade + 白話結論）**（pending, merged）— 使用者反饋「單一基金的基金評分太少了 甚至不知道是否吃本金」。Tab2 頂部新增大卡片，計算 4 個 0-100 分維度：(1) 配息健康度（Coverage = 1Y 含息 / 配息率）、(2) 風險調整報酬（Sharpe）、(3) 走勢健康（60MA 方向 × 含息報酬正負）、(4) 低波動性（σ 等級）。Overall 平均後映射 A/B/C/D/F 評等 + 一行白話結論「✅ 健康優質基金 / 🔴 多項警示」。D1 < 50 顯式標「吃本金風險」。
- [x] **PR #94 — v18.45/46：從 Drive 選 Sheet + 按鈕用語直白 + 歡迎卡緊湊**（`464b864`, merged）— (45) OAuth scope 補 `drive.metadata.readonly`，新增 `policy_store.list_user_sheets(client)` helper（呼叫 gspread `list_spreadsheet_files()`、過濾缺欄位、依名稱排序）；保單管理 expander 內追加「📂 從 Drive 列出 Sheets」+ selectbox 挑檔；(46a) 按鈕用語「同步／還原」一律改「存檔／讀取」；(46b) 歡迎三步驟卡從 3-column grid（~140px）改成單列 flex（~32px）。+3 test cases。
- [x] **PR #92 — v18.44：自動建 Sheet 後 StreamlitAPIException 修復**（`efe82e6`, merged）— v18.40 成功路徑寫 `st.session_state["inp_sheet_id"] = _new_sid` 違反 Streamlit「widget key 已實體化不能直接寫入」規則。改寫 canonical `policy_sheet_id` + 刪 widget key 讓 rerun 重 init。
- [x] **PR #90 — v18.43：資產成長曲線 dedupe by code + OAuth 403 scope 提示重登入**（`7d6fd1b`, merged）— (A) 同 code 跨保單時 `_curve_df.join` 因欄名衝突拋例外 → 迴圈內按 code 去重，與 v18.36 T5 / v18.38 真實收益矩陣策略一致；(B) 「🚀 自動建立 Sheet」403 insufficient scopes 因 OAuth token 在 drive.file scope 加入前授權 → 偵測錯誤訊息後給針對性「登出再登入」提示。
- [x] **PR #89 — v18.42：Tab2 吃本金檢查卡 1Y 含息報酬 fallback 鏈**（`5968cda`, merged）— 建立三層 fallback：metrics.ret_1y → moneydj.perf["1Y"] → NAV series 線性年化外推；訊息層標示「〔1Y 來源：...〕」。
- [x] **PR #87 — v18.41：強化「開啟 Sheet 失敗」診斷訊息 + T7 inline URL 解析 + 顯示綁定 ID**（`fbf27f9`, merged）— 截圖顯示「開啟 Sheet 失敗：」訊息結尾空白（gspread 例外 `str(e)` 常回空字串）。強化點：(a) `ensure_state_worksheet` / `ensure_policy_worksheet` 訊息補 `type(e).__name__` + sheet_id 前 12 碼；(b) sheet_id 為空時直接 raise 帶提示；(c) T7 inline `inp_sheet_id_t7` 補 URL → ID regex 解析（v18.39 只做了上方那欄）；(d) T7 expander 頂部新增 caption「📌 目前綁定 Sheet ID」便利 debug；(e) 例外訊息截斷 60 → 200 字。
- [x] **PR #85 — v18.40：一鍵自動建立 Google Sheet**（`d68c83b`, merged）— `policy_store.create_dashboard_sheet(client, title)` 新 helper（gspread `client.create()` + 回傳 sheet_id / sheet_url）；app.py「📋 保單管理」expander OAuth 已登入但 Sheet ID 為空時顯示「🚀 自動建立 Sheet」按鈕，預設名稱「Fund Dashboard - 投資組合」，建檔後 session_state 自動寫入 ID + 顯示 Drive 連結。免去使用者先到 Drive 手動開檔。`test_policy_store.py` +3 case（成功 / 失敗 / 空 ID）。226 passed。
- [x] **PR #83 — v18.39：Sheet URL 自動解析 / pid 反查代入 / 預估月配息修零**（`0616099`, merged）— 一次修 3 個獨立 bug：(A) 「保單分組視圖」上方 KPI「預估月配息 NT$ 0」永遠是 0 — 改用 `moneydj_div_yield` / `annual_div_rate` 取代不存在的 `dividend_yield_pct`；(B) 「保單分頁」要重複輸入既有 pid — 新增 selectbox 從 portfolio_funds 反查 + 「(輸入新號碼)」fallback；(C) Sheet ID 欄貼整段 URL → 404 — regex 解析 `/spreadsheets/d/([a-zA-Z0-9_-]+)`。
- [x] **PR #81 — v18.38：真實收益 vs 配息率矩陣按 code 去重**（`a117a89`, merged）— 截圖顯示長條圖出現多條同 code 跨保單的重複條目（19 條中有大量重複），右側產生空紅框且 KPI 數字被放大污染。`_loaded_pf` 計算後新增按 code 去重，與 v18.34 MK 戰情室 / v18.36 T5 矩陣策略一致。
- [x] **PR #79 — v18.37：投資組合主清單按保單號碼分組成 expander**（`a0b96d8`, merged）— v18.35 per-fund expander 取代為「外層保單 expander」（一張保單 = 一個摺疊區塊；點開後 KPI + advice + MK 訊號全部攤平顯示）。Streamlit 禁止 expander 巢狀，因此移除內層 expander。無 policy_id 的基金歸「(未綁保單)」群組。🗑️ 刪除按鈕仍以原 portfolio index 運作。
- [x] **PR #77 — v18.36：T5 重疊度按保單分組 + 修 pyarrow Duplicate column names 例外**（`09d775f`, merged）— 同 code 跨多保單時 `calc_holdings_overlap` 回傳 DataFrame 重複欄名讓 `st.dataframe` 爆 pyarrow `Duplicate column names found`。T5 區塊重構為「按 policy_id 分群 → 組內按 code 去重 → 每組各自 expander + 獨立矩陣」，session_state 鍵 `corr_result_{pid}` / 按鈕鍵 `btn_corr_{pid}` 跨組獨立。shadow_pairs / 共同持股 / heatmap 全保留。
- [x] **PR #76 — v18.35：投資組合主清單每檔詳細區包進 expander（預設收合）**（`d7cbd32`, merged）— Tab3 主清單迴圈內，把「💡 advice 建議帶 + 📍 MK 訊號 6 格方塊」兩塊包進 `st.expander("📋 詳細建議 + MK 訊號", expanded=False)`，上方 KPI 列（名稱/NAV/配息/Sharpe/σ/🗑️）永遠可見。多檔基金時版面長度減約 60%。
- [x] **PR #75 — docs(state+arch): v18.34 模組地圖 + 目錄樹補 7 個新模組**（`c424c6f`, merged）— STATE.md 補 mk_dashboard / policy_keys / policy_advisor / policy_store / oauth_helper / ledger_store / ledger_snapshot_store + 近期里程碑 PR #62-#73；ARCHITECTURE.md §2 目錄樹同步。
- [x] **PR #74 — docs(backlog): 補 PR #71/#72/#73 drift**（`2ad3771`, merged）— 對齊 STATE.md / BACKLOG.md 與已 merge PR。
- [x] **PR #73 — v18.34：MK 戰情室分析視圖按 code 去重**（`986ac2f`, merged）— `render_mk_war_room()` 內 `loaded` 計算後新增按 code 去重（保留第一筆）；同基金綁多保單時，KPI 卡 / 核心戰情室表 / 波段觀測站表 / 衛星 vs SPY 折線圖只算一筆。Tab3 portfolio_funds 與 T7 帳本仍以 `(code, policy_id)` 複合鍵分流，不影響獨立記帳。223 passed / 0 failed。
- [x] **PR #72 — v18.33：批次加入基金 + 並行抓取（4 workers）**（`c18911f`, merged）— Tab3「➕ 手動加入基金」改 `st.text_area`（每行一檔，可加 `,pid` 逐行覆寫保單），`ThreadPoolExecutor(max_workers=4)` 並行 fetch + `st.progress` 進度條 + as_completed 即時顯示；composite (code, policy_id) 去重；OAuth client 一次建構。
- [x] **PR #71 — 補 BACKLOG #62-#70 drift**（`28091a5`, merged）— 對齊 STATE.md / BACKLOG.md 與已 merge 的 PR #62-#70（保單視圖 + Google Sheets 整合系列）。

### 2026-05-14（保單視圖 + Google Sheets 整合系列：PR #62 → #70）
- [x] **PR #62 — 保單視圖 P1+P2+P3 PR 封包 + 抓取規則 audit fix v18.22**（`ee7c8c2`, merged）— 把先前 P1.1 / P1.2 / P1.3 / P2 / P3 五個分支封一個 PR 推進 main；同步加 `canonicalize_moneydj_url()` 把 mobile / 平台子網域 URL 統一轉 canonical。
- [x] **PR #63 — v18.23+24：Tab3 抓不到資料修復**（`f2c34f4`, merged）— (a) `fund_fetcher.py` 加 `_install_global_urllib_proxy()` 模組層 install_opener，所有 30+ 處裸 `urllib.request.urlopen()` 自動走 NAS Squid，修 ACCP138/ACDD01 因 IP 封鎖抓不到；(b) Tab3「➕ 加入」改成「加入即 fetch」與 Tab1 UX 對齊，告別 ⌛ 卡關。
- [x] **PR #64 — Google Sheet OAuth + 每保單一 worksheet + T7 帳目同步**（`ee7c8c2`, merged）— Phase A `oauth_helper.py` OAuth 2.0 web flow + `docs/OAUTH_SETUP.md`；Phase B `policy_store.py` per-policy worksheet API（tab 名 = 保單號碼）+ OAuth client；Phase C `ledger_store.py` `_Ledgers` 系統 tab 交易帳；Phase D Tab3 UI 整合 + T7「📝 編輯初始持倉」雙寫進 `_Ledgers`。
- [x] **PR #65 — v18.26：T7 市值 NT$0 + -100% 綠色 ↓ 假象修復**（`eaf5e0e`, merged）— 兩個 bug：(a) `_latest_nav_fx_t7` FX fallback chain 補第三層 `ledger.position.fx_avg`（最新 FX 抓不到時用買入匯率，避免市值整個歸 0）；(b) `delta_color="normal"` 寫死（原本 `inverse if 虧損` 把紅反成綠）。
- [x] **PR #66 — v18.27：加入即綁保單 + A/B/C 落帳同步進 `_Ledgers`**（`ee09a3c`, merged）— (a) Tab3「➕ 加入」加 policy_id 欄、加入時 `upsert_fund_in_policy` 寫對應保單 worksheet；(b) `_sync_actions_to_sheet` helper + T7 三種落帳（A 加碼 / B 再平衡 / C 轉換）都同步 `_Ledgers`，C 轉換 sell + buy 各記一筆。
- [x] **PR #67 — v18.28+29：T7 加 policy_id 欄 + JSON 存檔 + T7↔Sheets 雙向直連**（`faf1431`, merged）— v18.28 (a) T7「編輯初始持倉」加 policy_id 欄、pid 變更時自動遷移 ledger key + upsert fund row 到新保單；(b) Tab3 Sheets expander 預設展開；(c) JSON 存檔下載/上傳。v18.29 新建 `ledger_snapshot_store.py` + 11 測試，`_T7_State` tab 存 ledger JSON snapshot；T7 入口自動還原、四落帳點自動 dump、「☁️ 立即同步」/「🔄 從 Sheets 還原」按鈕。
- [x] **PR #68 — v18.30：T7 直連 inline 登入 + 主清單每檔顯示 advise 字眼**（`e4d3f44`, merged）— (a) T7「☁️ Sheets 直連」未登入時 inline 顯示「🔐 用 Google 登入」link button（不必滑回上方 expander）+ sheet_id 輸入欄；(b) Tab3 投資組合主清單每檔基金卡片下方加左邊框 advice 條（持有/加碼/賣出/吃本金警示等），抽 `_compute_advice_for(pf_item)` helper 封裝 σ / div_safety / 60MA 三組訊號計算。
- [x] **PR #69 — v18.31：同 code 不同保單能共存 + KPI 與表格差額來源說明**（`250fcc5`, merged）— (a) Tab3「➕ 加入」重複檢查改 `(code, policy_id)` 複合鍵（截圖中 JFZN3 + 新保單不再被擋）；(b) T7「目前帳本」KPI 卡下方加 caption「ℹ️ KPI 已計入 N/M 檔；未計入 K 檔（XXX(pid)…）— 請在『📝 編輯初始持倉』填入持有單位/NAV/匯率」。
- [x] **PR #70 — v18.32：in-app OAuth Client 引導 wizard（免改 secrets.toml）**（`1e475b3`, merged）— `_resolve_oauth_cfg()` helper fallback chain（secrets → session_state["custom_oauth_cfg"]），8 處取用點全改走它；「📋 保單管理」未設定時顯示 4 步驟 GCP 引導 + 3 欄表單（Client ID / Secret / Redirect URI 自動帶 `st.context.url`），按「💾 套用設定」立即生效，session-only。

### 2026-05-14（早期，PR #62 之前）
- [x] **fund_fetcher audit fix v18.22** — 新增 `canonicalize_moneydj_url()` 純函式：把 mobile (`m.moneydj.com/a1.aspx`) / 平台子網域 (`chubb.moneydj.com/w/wr/wr01.djhtm` 等) URL 統一轉成 canonical `www.moneydj.com/funddj/ya/yp01000X.djhtm?a={base_code}`，後續解析器零改動即可重用。同步擴充 `parse_moneydj_input` page_type regex 涵蓋 `.aspx` / `/w/wb/` / `/w/wr/` 路徑（標 `a1_mobile` / `b1_mobile` / `wb01` / `wr01` 等），放寬 `is_valid_moneydj_page` 第 3 條從 `"moneydj.com/funddj"` → `"moneydj.com"` 涵蓋所有子網域，並修既有 docstring `\d` 的 DeprecationWarning。新增 `test_fund_url_canonicalize.py` 16 cases。零回歸（189 passed / 0 failed；smoke 27/27 通過）。

### 2026-05-13
- [x] **保單視圖 P1.1** — `policy_advisor.py` 純規則建議引擎（10 條短路規則，σ 位階 × 配息覆蓋率 × 60MA × VIX）+ `test_policy_advisor.py` 21 cases（規則 1-10 + 邊界 + 容錯）。零外部依賴、零回歸（smoke 27/27 通過）。
- [x] **保單視圖 P1.2** — `policy_store.py` gspread + Service Account 儲存層（`get_gspread_client` / `load_policies` / `upsert_policy_row` / `delete_policy_row` + 純函式 `sync_policies_to_portfolio_funds`，lazy import + duck-typed 介面）+ `test_policy_store.py` 11 cases（MagicMock 模擬 Worksheet，無需安裝 gspread）+ `docs/POLICY_SHEETS_SETUP.md`（GCP Console 6 步教學 + 8 欄 schema 表）+ `requirements.txt` 加 gspread/google-auth + `.streamlit/secrets.toml.example` 加 `[google_service_account]` 區塊。零回歸（148 passed / 0 failed）。
- [x] **保單視圖 P1.3** — `app.py` Tab3 改造：頂部新增 2 個 top-level expander（📋 保單管理 = Sheet 同步 + 8 欄表單 upsert/delete；🗂️ 保單分組視圖 = 依 `policy_id` 分組，每檔基金顯示 σ 位階 / 賺息賠本 / `advise_fund()` 單句建議），既有「核心/衛星甜甜圈」雙欄縮成單列 mini chart（高 270→140、刪右欄持倉明細），既有「➕ 加入基金」表單包成 collapsed expander。零回歸（148 passed / 0 failed；smoke 27/27 含跨檔 expander 巢狀偵測通過）。
- [x] **保單視圖 P2** — T7 帳本 key 從 `fund_code` 升級為 `(policy_id, fund_code)` 複合鍵：新增 `policy_keys.py` 純函式 helper（`make_pk` / `pk_str` / `parse_pk` / `fund_pk_str` / `migrate_ledger_dict`）+ `test_policy_keys.py` 12 cases，T7 整個區塊（~900 行）所有 `t7_ledgers.get(code)` / form widget key 改為 pk_str，Tab4 multiselect 顯示「保單/代碼 – 名稱」label，Tab A/B/C 結果表加「保單」欄；session_state 一次性遷移 shim 把舊 code-only 鍵自動 rekey 成 composite。零回歸（160 passed / 0 failed；smoke 27/27 通過）。
- [x] **保單視圖 P3** — Sheets schema 加選填 `policy_tier`（core/satellite）+ 保單級核心衛星 mini 甜甜圈 + 自動配置建議：`policy_store.py` 拆 `REQUIRED_COLS` (8) + `OPTIONAL_COLS` (1)，`load_policies` 缺欄向後相容、`upsert_policy_row` 依既有表頭自動寫 8 或 9 欄；`policy_advisor.py` 新增 `recommend_policy(funds_in_policy, target_core_pct=75)` 5 規則短路（core 過重/過輕/多檔超跌/多檔吃本金/健康）+ 8 cases 單測；Tab3「🗂️ 保單分組視圖」每組標題下方新增高 120 mini donut + 建議單句；`docs/POLICY_SHEETS_SETUP.md` schema 表 + P3 預告區同步更新。零回歸（173 passed / 0 failed；smoke 27/27 通過）。

### 2026-05-12
- [x] PR #39 — 🧭 總經指南針 (Top-Down Macro) Phase 1：VIX × TNX × GSPC + 60MA (`a6262bf`, merged)
- [x] PR #41 — MK 戰情室 expander 巢狀錯誤修復（**stock repo**, `1e9a0d4`, merged）
- [x] commit `0bb8f46` — 總經指南針禁用 15 分鐘 session_state 快取，改即時抓取（首次提交誤刪 c1/c2/c3）
- [x] PR #42 — 補回 `0bb8f46` 誤刪的三張卡片渲染 (`5cfb73b`, merged)
- [x] PR #43 — feat(holdings): 擴充亞太企業中文對照（_HOLDING_ZH 277 keys）+ T5 影子基金共同持股顯示 (merged)
- [x] PR #45 — docs(state): 補 Roadmap + 近期里程碑（冷熱資料分離）(merged)
- [x] PR #44 — chore(state): 新增 `BACKLOG.md` 動態任務追蹤檔 (`35b7182`, merged)
- [x] PR #46 — test(smoke): `test_app_smoke.py` 26 cases（AST 編譯 + expander 巢狀偵測（跨檔 transitive）+ _zh_holding 對照）(`4ae73a3`, merged)
- [x] PR #47 — docs(backlog): 補齊 PR #43-46 drift + P0-P2 待辦 (`12645a9`, merged)
- [x] PR #48 — build(ci): pre-commit hook 強制驗證機制 + 修 trend_arrow 反彈誤判 (`26b737f`, merged)
- [x] PR #49 — fix(tab5): 修兩個 except:pass 沉默吞例外 + smoke test AST 偵測護欄（白名單機制） (`e024707`, merged)
- [x] PR #51 — test(apptest): Streamlit AppTest 首炮 3 cases + pytest slow marker 雙車道 (`2ed35e5`, merged)
- [x] PR #52 — docs(state): 同步 PR #48/#49/#51 + 消除 STATE/BACKLOG 雙頭管理 (`2f9cd61`, merged)
- [x] PR #53 — docs(backlog): P0 驗收通過（compass）+ 補進 PR #47/#52 條目（取代 #50）(`91bfef6`, merged)
- [x] PR #54 — build(ci): GitHub Actions PR 檢查 workflow（Phase C 落地）(`6700386`, merged)
- [x] PR #55 — test(apptest): AppTest 第二場景 — Tab1 缺 FRED_API_KEY 降級警告 + 補 #54 BACKLOG drift (merged)
- [x] PR #56 — refactor(backtest): backtest_engine 排毒（iterrows 死碼 / weights ZeroDiv 防護 / freq 參數）+ 14 cases 單測 + ARCHITECTURE §4.5b (merged)
- [x] **P0 驗收通過**：compass 三張卡片渲染 + 副標 `更新於 11:20:38` 時間戳 + 「無快取」字樣（使用者截圖確認 VIX 19.01 / TNX 4.41% / GSPC 7,412.84）

---

## ✅ Done — 2026-06-28 第三階段排毒(v19.202-208)

> User 2026-06-28 「B+C → D1+D2+B3」分批授權後執行。把第二階段 P2-1/P2-4/P2-5
> revert backlog 用「直接搬位置 + _* 集中 + 改 test patch path」策略重做成功,並
> 補完 F-PROV-1 phase 22+ 高 ROI fetcher。

- [x] **A1**(v19.202, `61af3e0`):清 2 個空殼目錄(P2-1/P2-5 revert 殘留)+ 修 2 個過時 SSOT-guard test(test_provenance_smoke 改讀子套件 concat)
- [x] **B1**(v19.205, `b9eab84`):P2-5 重做 — `repositories/macro_repository.py` 1078 LOC 拆 5 子檔(`fred / yf / china / alternate / math_utils`)+ 23 LOC shim。同步改 28 處 test patch path 至子模組,規避 v19.199 patch shim 不穿透 sub-module。485 passed
- [x] **B2**(v19.206, `b35dcbd`):P2-4 重做 — `repositories/policy_repository.py` 1372 LOC 拆 3 子檔(`_helpers / v1 / v2`)+ 23 LOC shim。共用 `_*` 私函集中 `_helpers.py`,規避 v19.199 `from X import *` 不取 `_*` 死結。239 passed
- [x] **C3**(v19.207, `5b32618`):app.py 542 → 471 LOC(−13%)。抽 `_render_compass_card + render_macro_compass`(78 LOC)到 `ui/components/macro_compass_top.py`。第二輪 sidebar 抽取 abort(over-engineering risk,需 7-8 module-level vars 注入接口)
- [x] **C2**(v19.208, `b7eb171`):F-PROV-1 phase 22+ 補洞 9 個 fetcher(5 實質 + 4 docstring 標明)。audit OK 23 → 31(+35%),PARTIAL 全清(4 → 0)
  * **實質補洞**:`fetch_market_news` / `fetch_stock_news` 加 `fetched_at` + `_now_iso_utc` helper / `fetch_fund_from_moneydj_url` 加 `source='MoneyDJ:fund_url_orchestrator'` / `fetch_tw_market_snapshot` 加 orchestrator-level source + fetched_at
  * **Pass-through 標明 inheritance**:`fetch_china_macro` / `fetch_fred_batch` / `fetch_macro_news` / `fetch_fund_by_code`
  * **8 MISS 留 backlog**(complexity-justified):3 scalar return(scalar 無法 schema-additively 加)/ 4 fallback chain(deep audit)/ 1 tuple(audit script 誤判)
- [x] **C1**(藍圖誤判):`fund_checkup` v19.150 已走 SSOT(`check_eating_principal_1y_mk`),`_compute_fund_health_kpis`(KPI 卡 7 欄)與 `build_health_analysis_row`(dataframe row 15+ 欄)職責不同 — 同 P2-8 SCORE_RULES 案例
- [x] **B3**(藍圖誤判):Fund Health 6 檔職責不同(4 services data layer 各維度 + 1 row builder facade + 2 UI presentation views),非「重複實作」;v19.181 SSOT 抽取後各檔均走 SSOT。同 C1 案例
- [x] **D1**:`ARCHITECTURE_AUDIT.md §6` 同步本次第三階段執行紀錄
- [x] **D2**:`BACKLOG.md` / `STATE.md` 同步本檔

---

## 🚧 Next

> **目前 sandbox 可獨立推進項：0**（v19.15 已 ship，無 in-flight epic）。新需求隨時開新 epic 起新三步法。

### ~~PR C/D — Sheet v2 主路徑收口~~ — 已結案，不再列為 Next

- **PR C（v18.250 已 ship）**：`cloud_io.dump_all_to_sheet / load_all_from_sheet` 開頭已加 `detect_sheet_schema_version` schema-aware routing，v2 走 `_dump/_load_all_to_sheet_v2`（13 欄整 tab 覆寫 + 反推 portfolio_funds + ledger snapshot via `Ledger.subscribe()`），v1 / empty / detect 失敗維持舊路徑向後相容。test_cloud_io 14 → 18 passed（4 case：`test_dump_routes_to_v2_when_detected` / `test_load_routes_to_v2_when_detected` / `test_v1_path_unchanged_when_v1` / `test_v2_round_trip_keeps_13_cols`）。詳見 `## ✅ Done` 區 2026-05-29 條目。
- **PR D — 不做（已宣告拒做）**：破壞性移除 `_T7_State` / `_Ledgers` 寫入路徑需先在 Sheet 副本驗 v2 round-trip OK，且風險 / 收益不成比例（v1 + v2 雙寫即將上線多月已穩定 / 無人抱怨儲存空間或效能）。BACKLOG line 13 末尾已標註 `⚠️ PR D 不做`。若未來 user 改變主意要做，重新開新 epic 走三步法。

### 其他可選

> - 🌐 **部署驗證**：tab cloud 互動全綠（user 需手動）
> - 🌐 **streamlit-pages**：是否取代 `st.tabs`（影響 routing / URL share，user 決策）
> - 🔧 polish：拆 `ui/helpers/session.py` 為 session 工具 vs UI 工具（low value）
> - [x] **v18.144** Tab3 T7 抽檔 → `ui/tab3_t7_ledger.py`（tab3_portfolio.py 3976 → 2001 行 −49.7%）
> - [x] **v18.145** 總經指南針 UI 標籤誠實化 — `app.py:349/363`「即時抓取」改「5min TTL 快取」（PR #3）

---

## 💡 Ideas

> 原 Ideas 區於 v18.102 → v18.105 全部結案。再有需求時參考已 ship 的 helper 為基礎：
> - 持股對照表 → `_HOLDING_ZH` (~410 keys, app.py:103)
> - Phase B-3 跨 viewport → `RESPONSIVE_VIEWPORTS` (test_app_playwright.py)
> - AppTest 進階場景 → 11 cases (test_app_apptest.py)，可繼續加 Tab4 回測流程 / 切換策略後 KPI 重算
> - 總經 Phase 3 → `build_macro_sankey_dynamic` + `backtest_sub_cycle_lights` (macro_engine.py)
>
> Ideas 候選 3 條於 v18.106 → v18.108 全部結案：
> - Tab4 AppTest 回測 → v18.106 (`6b0f599`)
> - 跨幣別 EUR/JPY/CNH → v18.107 (`c0eb8b6`)
> - Phase 4 變數重要性 → v18.108 (`e545432`)
>
> 全 BACKLOG 至 v18.108 達成 100% 結案。
> 若再有新需求 → 直接於對話啟動，BACKLOG 重新打開。

---

## 規則
- 完成的項目移到 `## ✅ Done` 並附日期分組
- 新想法先丟到 `## 💡 Ideas`，動工前才升級到 `## 🚧 Next`
- PR / commit 都用 backtick 包起來方便點擊
- 每個 PR merge 後**同步更新本檔**（避免 PR #43–46 那種 drift 重演）
