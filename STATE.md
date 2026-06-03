# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡狀態檔。專案具體進度見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md`、`SPEC.md`、`STRATEGY.md`。

## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — 對應台灣 user 的 USD/EUR 計價基金 TWD 換匯後績效分析
- **技術棧**：Streamlit + pandas + plotly/altair + Google Sheets + FinMind/Yahoo
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金
- **目前版本**：v18.278_PhaseECrossSource（Phase E 全球 macro_score × 台股 TWII 對照引擎）
  - **User 需求**：「Phase E」— 把 fund repo 的「全球 FRED 合成 0-10 macro_score」與台股 TWII 同框比對，找 macro_score 領先 TWII 月變化率最強相關的月數
  - **方案 A 案**（單站式）：sister repo my-stock-dashboard v18.157 已降級為純 TWII drawdown 不再算 NDC 信號 → fund repo 直接抓 `^TWII` 進自家 `data_cache/twii_history.parquet`（鏡像現有 `^GSPC` `^VIX` 模式），避免跨倉資料流
  - **scripts/update_macro_history.py**（+~15 行）：新 `fetch_twii_history()` 委派 `_yf_fetch_close("%5ETWII", ...)`；`DATASETS` 從 3 表擴 4 表；`FETCHERS` 同步註冊 `twii_history`（needs_fred_key=False, dedupe_keys=["date"]）；workflow YAML **不動**（cron 自動迭代 `DATASETS`）
  - **services/cross_source_compare.py**（新檔 ~180 行，純函式零 I/O 除 Parquet 讀）：
    - `load_twii_from_parquet(cache_dir)` → 日線 close Series
    - `align_score_with_twii(score_df, twii_series, freq='ME')` → DataFrame[score, twii_close, twii_mom_pct]（月末對齊；twii resample(ME).last；inner join）
    - `compute_lead_lag_correlation(aligned_df, max_lag_months=12)` → DataFrame[lag_months, correlation]，公式 `corr(score.shift(k), twii_mom_pct)`，k ∈ [-12, +12]
    - `find_best_lead_lag(corr_df, prefer_positive=True)` → (best_lag, best_corr)；只挑正相關
    - `summarize_crisis_score_around_events(events, score_series, lookback_months=6)` → list[dict]（每場 crisis：peak 前 N 月平均 score / peak score / trough score / 降幅）
  - **ui/tab_crisis_backtest.py**（+~165 行）：新 `_render_phase_e_cross_source_section(events, years)` 插在 Phase 4+5 之後、限制提示之前。缺檔守門 + 2 sliders（max_lag 3-18 / lookback 3-12）+ 跑按鈕 → 3 metric 卡（最佳領先期 / 相關係數 / 分析月數）+ plotly 雙軸圖（macro_score 主軸藍 + TWII 副軸紅 + crisis 灰區）+ cross-correlation 完整表 expander + Crisis 事件 macro_score 統計表 + 對齊月資料 CSV 下載
  - **test_cross_source_compare.py**（新檔 +15 case）：load 缺檔 / 排序 / 壞檔 graceful、align 三欄結構 / 第一列 NaN mom_pct 保留 / 空 score 或 twii、cross_corr 對稱範圍 / 空、find_best 正相關挑最大 / 全負回 None / 空 / 全 NaN、summarize crisis 平均/peak/trough 正確 / 空 events / 空 score / 無 trough graceful
  - **test_update_macro_history.py**：DATASETS 集合從 3 擴 4；新增 `test_fetch_twii_history_calls_yf_chart`（驗證 ticker 為 `%5ETWII`）+ `fetch_twii_history` 簽名校驗
  - **回歸**：test_cross_source_compare + test_update_macro_history + test_macro_validation + test_crisis_backtest + test_app_smoke **192 passed + 1 skipped** 零功能回歸
  - **下一步**：merge 後手動觸發 `update_macro_history.yml` workflow_dispatch + bootstrap=true / years=15 → 應抓到 15 年 TWII 日線（~3,700 列）→ Tab4「📉 危機回測室」末段就能跑 Phase E
- **前一版**：v18.277_FredRateLimitRetry（FRED 429 rate-limit 修復 + bootstrap 失敗復原 + 測試隔離）
  - **背景**：v18.275 在 15-year bootstrap 時 FRED 8 series 中 4 個（DGS3MO / BAMLH0A0HYM2 / CPIAUCSL / UNRATE）遭 HTTP 429 Too Many Requests，順序連打觸發 API rate limit → Parquet 只抓到 4 個 series。同時發現 v18.276 引入的 test isolation bug：bootstrap 後 cwd/data_cache/ 有真資料，3 個 synthetic indicator 測試讀到真 Parquet 蓋掉 fixture → 假陽性失敗
  - **scripts/update_macro_history.py**：
    - `_fred_get_single` 加 429 重試 3 次 exponential backoff (2/4/8 秒；模組常數 `_FRED_429_BACKOFF_SEC`)；連線異常維持原本 graceful 回空
    - `fetch_fred_indicators` 在 series 間插 `_FRED_INTER_CALL_SLEEP_SEC = 1.0` 秒間隔避免 burst（+8 秒 cron 時間換 8 series 全到）
    - `import time` 新增
  - **test_macro_validation.py**：4 個 synthetic indicator 測試明確帶 `prefer_parquet=False` 隔離 cwd data_cache 真資料
  - **test_update_macro_history.py**：新增 3 case
    - 429 → 200 重試成功：sleep 序列 `[2.0, 4.0]`
    - 429 exhausts：4 次全 429 → sleep `[2.0, 4.0, 8.0]` 並回空
    - inter-call sleep：N series 之間 N-1 次 `[1.0]`
    - 既有 2 個 `fetch_fred_indicators` 測試補 monkeypatch `time.sleep` 避免 real-sleep 7 秒
  - **回歸**：test_macro_validation + test_update_macro_history **58 passed + 1 skipped**（v18.276 35 → 58 含新 +23）；full suite 預期僅剩 `test_tab6_manual` 2 個 pre-existing mock-spec 失敗（與此 hotfix 完全無關，tab6 自身 issue）
  - **下一步**：merge 後請手動觸發 `update_macro_history.yml` workflow_dispatch + bootstrap=true / years=15 → 應抓到全 8 FRED series；接 Phase E 跨來源比對工具
- **前一版**：v18.276_MacroValidationReadsParquet（Phase 6a 驗證解綁 Tab1 — 改讀 Parquet + 加 CSV 下載）
  - **User 需求**（接 Phase B v18.275）：「繼續 B.2」。把 PR #160 v18.275 鋪好的 `data_cache/*.parquet` 接到 Phase 6a 驗證流程 → user 不用先去 Tab1 抓 FRED 就能跑驗證；加 macro_score 月序列 CSV 下載讓 user 拿到原始資料二次分析
  - **services/macro_validation.py**：新增 `load_indicators_from_parquet(cache_dir)` 把 `fred_indicators.parquet`（長格式 8 series）+ `vix_history.parquet` 重組成跟 `fetch_all_indicators` 同結構的 `{key: {"series": pd.Series}}` dict；轉換邏輯**完全鏡像 services/macro_service**：殖利率 spread（DGS10-DGS2 / DGS10-DGS3MO）+ M2 YoY%（shift 12）+ FED_BS YoY%（shift 52 週頻）+ CPI YoY%（shift 12）+ HY/UNRATE/VIX 直接 level。**PMI 不在 Parquet 內**（PR #160 暫不抓），留 indicators_now fallback。`calc_macro_score_series` 簽名擴 `prefer_parquet=True / cache_dir=DEFAULT_PARQUET_CACHE_DIR`，Parquet 優先、indicators_now 補洞 PMI
  - **ui/tab_crisis_backtest.py Phase 3.5**：
    - 偵測 `data_cache/fred_indicators.parquet` 存在 → 印「📦 資料源：Parquet（+Tab1 cache 補位 PMI）」caption，**不再強制 user 先進 Tab1**；缺 Parquet + 缺 session_state → 引導 user 等下次週日 cron 或手動觸發 workflow
    - 覆蓋率檢查改算「Parquet ∪ indicators_now 合併後」`n_covered`
    - `calc_macro_score_series` 帶入 `prefer_parquet=_has_parquet, cache_dir=...`
    - 新增「📥 下載 macro_score 月序列 CSV」按鈕（utf-8-sig BOM 解 Excel 中文亂碼），檔名含 years + 日期
  - **test_macro_validation.py**（+16 case = 35 全綠 + 1 skipped）：
    - `_write_fred_parquet` / `_write_vix_parquet` 兩個 helper 寫合成 Parquet
    - `load_indicators_from_parquet`：缺目錄 / 空目錄 / DGS10-DGS2 spread / DGS10-DGS3MO 倒掛 / HY 直 level / M2 YoY 計算（13 點線性升 10→ YoY=10%）/ M2 只有 10 點不足 13 → 不在 output / UNRATE 直 level / VIX 從獨立檔 / PMI 不在 output（PR #160 確認）/ 壞 Parquet graceful 不 raise
    - `calc_macro_score_series`：prefer_parquet=True 預設用 Parquet / prefer_parquet=False 完全略過 Parquet / Parquet+indicators_now 合併共 3 個指標 / Parquet 覆蓋 indicators_now 同 key（VIX 50 vs 10 取 Parquet）
    - UI source-level：CSV 下載按鈕存在 + key + to_csv 邏輯；`load_indicators_from_parquet` 與 `fred_indicators.parquet` 被 import
  - **回歸**：test_macro_validation + signal_lookback + crisis_backtest + strategy_grid + update_macro_history + tab2_single_fund + app_smoke **231 passed + 1 skipped** 零回歸
  - Roadmap：Phase C（stock-dashboard macro tab 加歷史驗證 UI 子區塊 — 讀 NDC + 領先指標 Parquet）→ Phase D（PMI 補抓進 Parquet）
- **前二版**：v18.275_MacroHistoryCache（全球 FRED 8 序列 + VIX + SPX Parquet 快取 + 每週 cron）
  - **User 需求**：「兩邊都可以做回測來驗證台股的總經 tab 與基金（全球的）總經 tab」+「直接抓取資料放在資料庫，之後每周定期更新」。Sister repo `my-stock-dashboard` 已於 v18.149 用 Parquet 模式做台灣指標歷史 → 本 repo 鏡像對全球 FRED.
  - **scripts/update_macro_history.py**（~280 行）：純函式爬蟲、無 streamlit 相依、無 repo internal import；FRED 直連（全球可達不需 proxy）+ Yahoo VIX/SPX 走 `_fetch_url_via_proxy`（infra.proxy → repositories.macro_repository.fetch_url → 直連三層 fallback）；CLI `--bootstrap --years N --only NAME`。
  - **新增 Parquet 表**（3）：
    - `data_cache/fred_indicators.parquet` (date, series_id, value) ← **長格式** 8 series：DGS10 / DGS2 / DGS3MO（殖利率日頻）/ BAMLH0A0HYM2（HY 利差日頻）/ M2SL（M2 月頻）/ WALCL（Fed BS 週頻）/ CPIAUCSL（CPI 月頻）/ UNRATE（失業率月頻）。Spread/YoY 由分析端 on-the-fly 算
    - `data_cache/vix_history.parquet` (date, close) ← ^VIX 日線
    - `data_cache/spx_history.parquet` (date, close) ← ^GSPC 日線（crisis 偵測對齊）
    - `data_cache/metadata.json` ← 各表 last_updated + row_count + last_error
  - **`.github/workflows/update_macro_history.yml`**：**每週日 UTC 00:00**（TW 週日 08:00）+ workflow_dispatch（input bootstrap/years），需 Secrets `FRED_API_KEY`（+選配 `PROXY_URL`），跑完直接 commit `data_cache/` 到 main（純資料增量、無邏輯 → 不開 PR）
  - **不抓 PMI**：services/macro_service 用 OECD/Phil Fed 多源 proxy 邏輯複雜（n_sources=9 並行），留 Phase B.2；當前 8 個 FRED 序列已覆蓋 SCORE_RULES 80%（PMI weight=2 缺位）
  - **test_update_macro_history.py**（20 tests passed）：merge_dedupe 單欄/複合欄 / Parquet roundtrip 長格式 / load_existing 缺檔 / last_date 跨 series 取 max / DATASETS+FETCHERS 註冊 + FRED_SERIES_IDS 覆蓋 SCORE_RULES / update_one 已最新跳過 + 缺 key graceful + fetch 回空保留 existing / `_fred_get_single` 解 observations + `.` 剔除 + HTTP error + no api_key 短路 / `fetch_fred_indicators` 長格式 + 任一 series 失敗其他繼續 / `_yf_fetch_close` 解 Yahoo Chart JSON + None response graceful / fetch_vix/spx 簽名一致
  - **回歸**：test_macro_validation + test_macro_signal_lookback + test_macro_score_calibration + test_update_macro_history **84 passed + 1 skipped** 零回歸
  - Roadmap：Phase B.2（services/macro_validation `calc_macro_score_series` 改讀 Parquet，加 macro_score 時序 CSV 下載按鈕）→ Phase C（stock-dashboard 補 macro tab 歷史驗證 UI）
- **前版**：v18.274_PyArrowMixedTypeFix（**全域除錯協議揭露真因** — cash/fund 列空欄改 None 解 pyarrow ArrowInvalid → 連帶解開「Tab2 FX 都暫無」假象）
- **進度標記**：✅ 代碼淨化與收尾完成（2026-06-02）
  - **#142**：fix — MK 景氣時鐘誤判衰退根治。User 截圖回報「股市大漲卻判衰退」，根因鎖定 `ui/components/mk_clock.py:classify_phase` 三個疊加 bug：(1) **else 變垃圾桶** — CPI/FED 缺資料時 `cpi_t=0/fed_t=0` 落入 `else: phase="recession"`，把「資料不足」誤判成「衰退」。(2) **PMI 50 硬切無容忍** — 49.9 vs 50 在統計噪音內也翻 phase。(3) **UI 不顯示 CPI/利率數值** — 只畫箭頭沒數字，使用者看不出資料是否載入。Surgical fix：加 `"unknown"` phase（缺 PMI 或 CPI → return unknown，UI 顯示警示卡 + 灰階象限不畫指針）；PMI 加 ±0.5 緩衝（49.5~50.5 視 trend 方向判定）；三面向 UI 補上 `{cpi_v:.2f}%` `{fed_v:.2f}%` 並對缺值欄位標紅「—／未抓到」。新 test_mk_clock.py +15 case（user 原始 case PMI=49.9 無 CPI/FED → 必 unknown / 五種缺資料變體 / PMI 邊界 49.9-50.5 不誤判 / 四象限正常判定 parametrize / meta 完整性）。回歸 test_mk_clock + test_mk_dashboard + test_tab1_macro + test_macro_core + test_app_smoke **173 passed**。
  - **#141**：chore — Cleanup imports round 5（test + scripts 收尾）。ruff F401 --fix 自動清 24 個 `test_*.py` + 1 個 `scripts/migrate_v149_schema.py` + `hot_money.py` + `scripts/fetch_nav_cache.py` 共 27 個檔；移除 34 個未用 imports（多為 `pytest` 14 個、`pandas/json/numpy/Path` 等 stdlib）。**全 repo F401 歸零**：5 輪累計 13 檔 / -182 行 imports / 0 個 F401 殘留。回歸 **1003 passed**（3 個 pre-existing 失敗無關此 PR — `test_hot_money::test_altair_import_chain` altair 套件版本問題、`test_tab6_manual` mock 缺 expander attr，main 上就有）。
  - **#140**：chore — Cleanup imports round 4。砍 `fund_fetcher.py` 7 個（module-level `requests, re, time, pd, np, st, BeautifulSoup` 確認全檔零引用；legacy re-export 區塊 `from infra.cache import ... # noqa: F401` 不動）+ `repositories/fund_repository.py` 6 個（皆為函數內 local `import re as _re` / `import urllib.parse as _up2` 等 alias 從未被 function body 使用；ruff F401 scope-aware 精準辨識）。合計 -10 行；test_app_smoke + 10 個 fetcher/repo 相關 test 共 **224 passed**。**業務代碼 F401 歸零**（10 檔累計 -148 行 imports）；剩 34 個全在 `test_*.py` + `scripts/migrate_v149_schema.py`（非 production code，留作未來個別處理）。
  - **#139**：chore — Cleanup imports round 3 (app.py)。砍 `app.py` 67 個 F401（-64 行；547→487 LOC）。事前驗證：（1）grep `from app import` 全 repo 無外部依賴；（2）`getattr/globals/eval` 動態查名為零；（3）`_friendly_error` / `_parse_indicator_date` re-export 已有 `# noqa: F401` 護身符；（4）`# noqa: smoke-allow-pass` 是 `test_app_smoke::test_no_silent_except_pass_in_app` 用的 custom marker（不是 ruff），保留。`test_app_smoke` **96 passed**（含 `test_module_level_imports_resolvable` + `test_app_full_module_execution_with_secrets`）；test_app_apptest 抽 5 case 17.6s 通過。剩 `fund_fetcher.py` (7) + `repositories/fund_repository.py` (6) 留 round 4。
  - **#138**：chore — Cleanup imports round 2。再砍 6 個檔的 9 個 F401（`ui/tab1_macro.py` / `ui/helpers/v2_editor.py` / `ui/tab5_data_guard.py` / `services/macro_service.py` / `services/ai_service.py` / `ui/tab_crisis_backtest.py`）；補回 `parse_indicator_date as _parse_indicator_date` re-export 給 `test_tab5_data_guard.py` 用。fast lane test_v2_editor + ai_service + macro_core + tab1 + tab5 + crisis backtest **290 passed**。剩 `app.py` (67) + `fund_fetcher.py` (7) + `repositories/fund_repository.py` (6) 因 legacy re-export shim 與 test 斷言依賴需逐行 noqa，留下輪專做。
  - **#137**：chore — Cleanup imports round 1。ruff F401 自動掃 → ui/tab3_portfolio.py 砍 31 個未用 imports、ui/tab2_single_fund.py 砍 13 個、ui/tab3_t7_ledger.py 砍 6 個（合計 -64 行；保留 `friendly_error as _friendly_error` 等 alias re-export 給 tests）。`repositories/fund_repository.py` 內 200 個 `print()` 經辨識為結構化 logging（`[src_xxx] ✅/❌` patterns 給 Streamlit Cloud 抓 log），**保留不動**。零邏輯改動：test_app_smoke + test_tab2_single_fund + test_tab3_portfolio + test_tab2_ccy_normalize + test_tab6_manual + test_tab1_macro **116 passed**；test_app_apptest 抽 4 case 通過。
  - **#136**：User 觸發「全域除錯協議」拿到真實 traceback `pyarrow.lib.ArrowInvalid: Could not convert '' with type str: tried to convert to int64. Conversion failed for column div_cash_pct`。根因鎖定 `ui/helpers/v2_editor.py:_merge_policy_df` cash 列把基金欄位 (units/avg_nav/avg_nav_with_div/avg_fx/invest_twd/div_cash_pct) 塞 `""`、fund 列同欄位是 float → pyarrow 推斷 column type 遇到 mixed str/float 直接 crash → `st.dataframe` 無法 render → **整頁 freeze → Tab2 FX widget 沒重跑抓取邏輯**，顯示「都暫無」純粹是頁面渲染卡死的副作用（**前 6 個 PR #129-#133 嘗試修 FX 全是治標方向錯誤**）。Surgical fix 9 行：cash 列空欄 → None；fund 列 amount → None。pyarrow 視 None 為 nullable numeric 可正確序列化。downstream 安全：`write_policy_v2` 用 `_normalize_float / _cell_empty` 已正確處理 None。**regression test_v2_editor_arrow_compat +6 case**（混 fund/cash 必須 pyarrow.Table.from_pandas 不 crash / 純 cash / 純 fund / 精確驗 None 不是 "" / roundtrip 完整）。**fast lane 230 passed 零回歸**。教訓：拿到 traceback 前不要猜「可能是 X」。Phase 1-4 協議完整執行（.bak/.log 已自動清理）。
  - **#135**：chore — `*.bak` / `debug.log` 加入 .gitignore（全域除錯協議 Phase 1-4 中間產物，stop-hook 不該擋）。
  - **#134**：docs — 同步 STATE.md 至 v18.273（補 #127-#133 沿革）。
- **前版**：v18.273_FxDirectRequests_DivLiveFx（er-api 改 direct requests.get + 配息折算用即時 FX）— ⚠️ user reboot 後仍報「FX 都暫無」直到 v18.274 才真解
- **前二版**：v18.272_FundHistoryInManual（說明書新增「曾經查過的基金清單」Tab2/Tab3 自動記錄）
- **前三版**：v18.271_FredProbeUrlFix（sidebar FRED probe URL 改首頁避免 404 假警示）
  - **#133**：兩件事一起修。(1) `repositories/fund_repository.py:get_latest_fx / diagnose_fx_sources` 的 er-api / Frankfurter 兩段從 `infra.proxy.fetch_url` 改用 `requests.get(proxies=..., timeout=15, verify=False)` 直連（與 sidebar 測試同樣 mechanism）— user 截圖證實 sidebar er-api ✓ HTTP 200 但 Tab2 widget 失敗，疑為 fetch_url 的 retry session / 5xx auto-retry / 客製 user-agent 行為差異。(2) `repositories/policy_repository.py:estimate_dividend_split` 新增 `current_fx` / `current_nav` 兩個 optional 參數（user 反饋「組合買入的匯率固定，但轉配息由美元轉台必須要即時匯率」）：公式 `fx_ratio = current_fx / avg_fx`、`annual_div_twd = invest_twd × ADR% × fx_ratio`；不傳 current_* → fallback avg_*（向後相容）。output 加 `fx_ratio` 欄。`ui/helpers/v2_editor.py` caller 對每檔 fund 抓 `get_latest_fx(f"{ccy}TWD=X")` 帶 FRED_KEY 傳入；每幣別只抓一次（in-loop cache）。test_dividend_current_fx +7 case；test_get_latest_fx_fred_fallback 20 case 既有更新（monkeypatch target 從 `infra.proxy.fetch_url` 改 `requests.get`，_FakeResp 加 status_code）。**fast lane 226 passed**。
  - **#132**：說明書新增「曾經查過的基金清單」(Tab2/Tab3 自動記錄)。新 `services/fund_history.py` 純函式（record_fund/get_history_df/clear_history/history_size）+ JSON 存 `cache/fund_history.json`。Hook：Tab2 fetch 成功後 record_fund(fk, name, "Tab2")；Tab3 portfolio fund 載入成功後 record_fund(code, name, "Tab3")。Tab6「📖 說明書」最上方新 expander「📋 曾經查過的基金標的清單」（預設展開）：3 卡（計數 / 💾 下載 CSV / 🗑️ 清空）+ DataFrame 6 欄。caption 警示容器重啟會清空。test_fund_history +12 case；fast lane 124 passed。
  - **#131**：sidebar Proxy 測試「FRED API HTTP 404」修正 — probe URL 從 `api.stlouisfed.org/fred/`（FRED API base 真會 404）改用 `fred.stlouisfed.org/`（網站首頁 200/302）。
  - **#130**：sidebar Proxy 測試從 2 個 endpoint 擴成 6 個（加 Yahoo Chart / FRED / er-api / Frankfurter）讓 user 一眼看出是 Cloud 整體網路問題還是某個 endpoint 個別被擋。配合 Tab5「🌍 FX 來源診斷」(v18.268) 形成 sidebar 快測 + Tab5 精測雙重保險。
  - **#129**：v18.268 加 open.er-api.com 第三來源（150+ 幣別含 TWD，免 auth） + Tab5「🌍 FX 即時匯率來源診斷」expander（selectbox 選對 + 按鈕跑診斷 + 表格 4 來源狀態）。Frankfurter 對含 TWD pair 直接跳過（節省 HTTP）。test_get_latest_fx_fred_fallback +6 case。fast lane 151 passed。
  - **#127**：docs — 對齊 app.py 與 STATE.md 描述漂移，統一 bump v18.267_Ship_FxAndMacroValidation。
- **前版**：v18.272_FundHistoryInManual（說明書新增「曾經查過的基金清單」Tab2/Tab3 自動記錄）
- **前二版**：v18.271_FredProbeUrlFix（sidebar FRED probe URL 改首頁避免 404 假警示）
- **前三版**：v18.270_SidebarProxyTestFx（sidebar Proxy 測試擴成 6 個 endpoint）
- **前四版**：v18.269_AllocationSimulator（配息分配前向模擬器 Phase 6b — 配股/領現/停泊三桶 + 4 段景氣劇本 + 蒙地卡羅）
  - **#128**：User 提需求「設模擬器在不同階段調整配股、配息、放停泊帳戶，本金/配息變化要考慮匯差」。新增 `services/allocation_simulator.py`（~250 行，零 I/O 純函式）+ `ui/tab_allocation_simulator.py`（~280 行）+ `app.py` 註冊 Tab「💼 配置模擬器」（插 Tab 4 危機回測室與 Tab 5 資料診斷之間，共 7 tabs）+ 24 單元測試。引擎核心：`SimulationParams` frozen dataclass + `validate_and_normalize`（三桶 sum=100% 自動 normalize + 邊界校驗）+ `_build_fx_path`（fixed/linear/random GBM 月 shock ~ N(0, σ/√12)）+ `run_single_simulation`（月度迴圈：NAV×(1+phase變化%) → 月配息=units×NAV×yield/12 → 三桶分配【DRIP÷NAV 加單位、CASH 累積外幣桶、STAY×FX 進 TWD 定存桶月複利】→ 算 fund/cash/stay/total/div/cum_div TWD）+ `run_monte_carlo`（fx_model=random 跑 N 次，回 5/50/95% quantile + 50 條樣本路徑供 fan chart）+ `summarize_simulation`。**預設 4 段景氣劇本**（User 指定）：復甦 12m(+0.8%/月) → 擴張 18m(+0.5%) → 放緩 12m(+0.1%) → 衰退 6m(-1.0%)，合計 48 月（4 年）。UI 4 section：①基本設定（從 `_calc_invest_*` stash 帶預設） ②景氣劇本（`st.data_editor` 動態多行表） ③三桶比例（3 sliders + 即時 normalize 提示）+ 停泊利率 ④FX 模型 radio（隨機展開波動 σ + MC 次數 50-1000）→ 4 張終值卡 + plotly 4 主線（基金/現金/定存/合計 TWD）+ random 模式疊 30 條淡色 MC 路徑 + 3 卡 P5/P50/P95 quantile。tests 24 passed。回歸 test_app_smoke + test_tab2_single_fund + test_macro_validation + test_crisis_backtest **150 passed + 1 skipped**。Roadmap：Phase 6c（核心 vs 衛星資產配置維度）。
- **前版**：v18.268_FxErApi_Tab5Diag（PR #129 加 open.er-api.com 第三來源 + Tab5 FX 診斷區塊）
- **前二版**：v18.267_Ship_FxAndMacroValidation（PR #125 Frankfurter FX 第三來源 + PR #124 Tab1 Macro Score 預測力驗證 Phase 3.5 合併 ship）
- **前三版**：v18.266_MacroScoreValidation（Tab1 Macro Score 預測力驗證 Phase 3.5 — 重算歷史月度分數對齊崩盤）
  - **#124**：User 提出新需求「想驗證 Tab1 那個 0-10 分在歷史景氣變差時準不準（這樣才知道看總經 Tab 可不可信）」。新增 `services/macro_validation.py`（~230 行）+ 19 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加「📊 Tab1 Macro Score 預測力驗證」section（夾在 Phase 3 訊號回看與 Phase 4 grid search 之間）。引擎核心：`SCORE_RULES` dict（9 個核心指標的 `(weight, score_fn)`：PMI/YIELD_10Y2Y/YIELD_10Y3M/HY_SPREAD/M2/FED_BS/VIX/CPI/UNEMPLOYMENT，鏡像 `fetch_all_indicators` 的閾值規則）+ `aggregate_score`（公式同 `calc_macro_phase`：`(earned_w + total_w) / (2 * total_w) * 10` → 0-10）+ `calc_macro_score_series(indicators_now, years=15, freq='ME')`（對各指標 `.series` 用 ffill 對齊月末 → 逐月重算 score → 回 DataFrame[date, score, phase, n_indicators]）+ `verify_score_vs_crises`（每事件比 peak 前 N 月 vs peak 月 score 降幅，命中門檻可調，預設 20%）+ `compute_period_stats`（crisis 期 vs 平時 mean/std + Welch t-test p-value，scipy 缺則 None）。UI 3 sliders（lead_months 3-12 / drop_pct 10-50% / score_years 5-20）+「跑 Score 驗證」按鈕 + plotly 走勢圖（含 3 條 phase 區間線 + 紅色 crisis vlines + annotation）+ 命中表 DataFrame + 3 張 metric 卡（危機平均/平時平均/t-test）。**不重抓 FRED**：reuse Tab1 已塞進 `st.session_state["indicators"]` 的快取，無快取則 `st.info` 引導使用者先跑 Tab1。資料源瓶頸明確標示：排除 ADL/DXY/cross-rates（需 monthly change，回測對齊複雜，留 6b）。tests 19（SCORE_RULES 結構/邊界、aggregate 公式、series 維度、命中判定、t-test）— 18 passed + 1 skipped（scipy 未裝環境）。**回歸**：test_app_smoke + test_tab2_single_fund + test_crisis_backtest + test_crisis_strategy_grid + test_macro_signal_lookback **176 passed**。Roadmap：Phase 6b（策略模擬器 DRIP/CASH/停泊 + 匯差）、Phase 6c（核心 vs 衛星配置）。
- **前四版**：v18.263_FormulaSheetInCalc（Tab2 投資試算加「📐 完整計算公式」expander — 含數字代入 / 4 分支全覆蓋）
  - **#120**：Tab2「💰 投資試算」widget 在 4 個 metric 卡 + st.success 摘要句後，加一個收合 `📐 完整計算公式（含數字代入）`，用 `st.code(language="text")` 等寬呈現「公式 = 數字代入 = 結果」三段。覆蓋 4 個分支（配息型/累積型 × TWD/非 TWD）— 配息型展示 7 段（原幣本金 / 可申購單位 / 年月配息原幣 / 年月配息 TWD / 月配股單位）；累積型展示 3 段（單位 / 1Y 後預估 / 預估損益）。caption 列 4 條估算假設（FX/NAV/ADR 不變、配息 100% 再投入計算月配股）+ 「實際配息以保險公司每月對帳單為準」免責。零 logic 變更，純呈現增量。
  - **#119**：P0 hotfix — Streamlit Cloud「Oh no. Error running app.」白屏。根因 `ui/helpers/data_registry.py:104` 用 `os.environ.get` 但檔頭缺 `import os`，Bug 自 5/18 初始 migration commit `9dcab88` 就潛伏；Python `or` short-circuit 在 secrets 有 `FRED_API_KEY` 時不會走到 `os.environ` → 一直沒爆；近期某次 redeploy 把 secret 清空 → fallback 走到 `os.environ` → NameError → app crash。fix 補 `import os` 一行，零行為變更。
  - **#117**：危機回測室「跑訊號回看 / 跑網格」按鈕無反應。根因：Phase 1 主按鈕 `run = st.button(...)` + `if not run: return` 是 click-only 一次性 gating；按 Phase 3/4 button 觸發 rerun 後 `run = False` → 主函式提前 return → Phase 3/4 sections 不再渲染 → 點擊被吞。fix 三段 session_state cache + 參數 hash invalidation：Phase 1 寫 `_crisis_phase1_cache`、Phase 3 寫 `_crisis_phase3_cache`、Phase 4 既有 `_crisis_grid_cache` 自動 reachable；market/threshold/years/fund_key 任一改變 → invalidate 全部下游 cache。test_tab_crisis_backtest_gating +7 case（params signature 純函式 / invalidate 副作用 / cache key 互不相同）。
  - **#118**：docs — 對齊 STATE.md 至 v18.261（PR #117 後漏同步 doc）。
  - **#98**：v18.251 風險評分真值校準器 + Tab1 互動式儀表板 — 新 `services/risk_calibration.py`（純函式，零 I/O）：`label_forward_drawdown` / `compute_calibration` / `grid_search_threshold` / `rolling_risk_score` / `generate_synthetic_demo`。Tab1 加「🎯 風險評分校準」expander（3 滑桿 horizon/drawdown/window + 4 metrics 最佳門檻/Precision/Recall/F1 + Top10 grid 表）。test_risk_calibration +9 case。sandbox 無 FRED outbound → 用合成資料 demo pipeline；真值校準需 user-side 餵入 live (VIX,HY,Yield,SPX) 月序列。**v18.253 後**由 PR #103 + #104 補上真實 FRED+SPX 路徑、PR #105 進 AI snapshot。
  - **#116**：closed (duplicate of #115)。本 session 沒先 fetch main 就規劃 v18.252 改 TWD 優先，發現 main 早在 PR #115 (14:54) 已實現等價功能，主動關閉避免合併造成代碼漂移。教訓：動工前必須 `git log HEAD..origin/main` sync。
- **前五版**：v18.262_DataRegistryOsImportFix（補 os import 救活 app）
- **前六版**：v18.261_CrisisTabButtonsFix（危機回測室按鈕 session_state cache）
- **前七版**：v18.260p6_InvestCalcTWDFirst（投資試算改 TWD 為主，內部換原幣算單位/月配息/月配股）
  - **#115**：上接 #109。`ui/tab2_single_fund.py:1200-1380` 投資試算大改寫：輸入永遠 `投入金額（新台幣 TWD）` 預設 1,000,000，內部 `amt_local = TWD ÷ FX` 換成基金原幣再 `÷ NAV` 算單位數，原幣算年/月配息後 `× FX` 回 TWD。**新增「月配股（單位）」** = 月配息 ÷ NAV（每月配息若再投入可換得的單位數）。metric 4 卡主秀「可申購單位數 / 月配息（TWD）/ 月配股（單位）/ 年化配息率」；累積型對應「單位數 / 累積型 / 1Y 後預估市值 TWD / 1Y 預估損益 TWD」。**FX 守衛降級**：Yahoo FX 抓不到 → `st.number_input` 手動填匯率（預設 32.0、附「⚠️ 切換手動模式」字樣）+ stash `fx_manual: True`，不擋流程。`_calc_invest_*` stash 欄位重構：`amount` 改義為 TWD、新增 `amount_local`/`monthly_dividend_units`/`fx_manual`；AI snapshot 翻譯字串同步翻轉為「本金 X TWD（≈ Y USD）→ 單位 ｜ 月配息 ≈ X TWD（月配股 ≈ X 單位）」。tests +4（label 翻 TWD / amount_local + monthly_dividend_units stash / metric 卡名 / 手動 FX fallback），`test_tab2_single_fund.py` **16 passed**（原 12 + 新 4）。
  - **#114**：上接 #113。新增 `services/crisis_ai_advisor.py`（~170 行）+ 13 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加 `_render_ai_advice_block`（共用 `_GRID_CACHE_KEY` session_state 把 Phase 4 結果跨 rerun 保活，按「請 Gemini 解讀」即把事件 + grid + Top-1 餵 Gemini）。引擎核心：`build_strategy_advice_prompt`（≤800 字白話 prompt：危機事件條列 + grid markdown 表 + Top-1 條列 + 4 段輸出模板「最佳策略解讀/風險盲點/該怎麼做/一句話總結」）+ `generate_strategy_advice`（薄包 `services.ai_service.gemini_generate` + `get_gemini_keys` 守衛，無 key/空 grid 給警示不丟例外）+ 3 內部 summarizer（`_summarize_events`/`_summarize_grid`/`_summarize_top` 限筆 + NaN safe + Series/dict 雙吃）。UI：「🤖 AI 策略建議」expander 於 grid section 末尾，呼叫前用 `get_gemini_keys()` 守衛無 key warning + 顯示可用 key 數，呼叫中 `st.spinner` 提示 10-20 秒。累計測試 77 passed（Phase 1: 20 + Phase 3: 19 + Phase 4: 25 + Phase 5: 13）。
  - **#113**：Phase 4 — 新增 `services/crisis_strategy_grid.py`（~220 行）+ 25 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加「🧪 策略網格搜尋」section。引擎核心：`StrategySpec` frozen dataclass + `DEFAULT_STRATEGIES`（buy_and_hold/signal_exit/signal_half/buy_dip）+ `run_strategy`（t-1 訊號決定 t 倉位避免前視偏誤、計算 final_value/total_return/max_drawdown/sharpe/crisis_return_pct）+ `grid_search`（4×3 cell）+ `results_to_dataframe` + `build_heatmap_data`（pivot 成策略×門檻矩陣）+ `rank_results`（top-N）。UI 3 inputs（訊號 selectbox、metric selectbox、門檻文字框）+「跑網格」按鈕 + plotly heatmap（RdYlGn 色階）+ Top-5 排行 DataFrame + 完整 12-cell expander。
  - **#112**：Phase 3 — 新增 `services/macro_signal_lookback.py`（249 行）+ 19 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加「🚦 總經訊號預測力驗證」section。引擎核心：`SignalSpec` dataclass + `DEFAULT_SIGNALS`（VIX > 25 / HY > 6% / T10Y2Y < 0 / UNRATE > 5%）+ `fetch_signal_series`（Yahoo / FRED 雙來源 wrapper）+ `evaluate_signal_at_event`（點觀測 + 峰前最早警戒搜尋 → lead_time_days）+ `lookback_all_signals`（批次）+ `compute_signal_hit_rate`（命中率/平均提前天數）。UI 2 sliders（offset 30-180、上限 90-540 天）+「跑訊號回看」按鈕 + 命中率總覽 DataFrame + 逐事件 × 逐訊號明細表（✅/❌/— 圖示）。
  - **#111**：Phase 2 UI — 新增 `ui/tab_crisis_backtest.py` 230 行 + `app.py` 註冊 Tab「📉 危機回測室」（插在「🔍 單一基金」與「🔬 資料診斷」之間，共 6 個 tab）。UI：3 inputs（market radio SPX/TWII、threshold slider -30%~-5%、年數 3-20）+ 基金 full_key 預設帶 `st.session_state.fund_data` + 「開始回測」按鈕。輸出：4 統計卡 + 該基金 3 卡 + plotly 走勢圖（紅色 shaded 危機區 + 跌幅 annotation）+ DataFrame 事件清單（10 欄）+ CSV 下載。
  - **#110**：Phase 1 純後端引擎 `services/crisis_backtest.py`（247 行）+ 20 單元測試。`CrisisEvent` dataclass + `detect_crisis_events`（HWM walk-forward）+ `attach_fund_drawdown` + `fetch_market_series`（SPX/TWII wrapper）+ `summarize_events_with_fund` 一條龍。
  - 更早 v18.260p5_AIAdvice ~ v18.251 全鏈見 git log；STATE.md 極簡保留近 7 版主線（v18.260p6 ~ v18.269）。

## 目錄結構（v11.0 分層架構）
```
ui/                  Streamlit Tab 渲染（tab1_macro / tab2_single_fund / tab3_*）
services/            業務邏輯（macro / fund / ledger / portfolio / ai_*）
repositories/        I/O 抽離（fund / macro / news / ledger / policy / snapshot）
models/              Dataclass（ledger / policy）
infra/               基礎設施（proxy / oauth）
scripts/             一次性腳本
docs/                靜態文件（含本檔對應的 specs）
```
- **頂層業務檔**：`app.py`（入口）、`fund_fetcher.py`、`hot_money.py`

## 測試
- `pytest` — 41 個 `test_*.py`；smoke + integration 雙層
- 核心 smoke：`test_app_smoke.py`、`test_hot_money.py`、`test_t7d_fetch_meta.py`

## 配置
- `requirements.txt` — runtime 依賴；`requirements-dev.txt` — 開發
- `secrets.toml.example` — Streamlit secrets 範本
- 分支：開發於 `claude/etf-portfolio-download-CKR5h`，主幹 `main`
