# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡狀態檔。專案具體進度見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md`、`SPEC.md`、`STRATEGY.md`。

## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — 對應台灣 user 的 USD/EUR 計價基金 TWD 換匯後績效分析
- **技術棧**：Streamlit + pandas + plotly/altair + Google Sheets + FinMind/Yahoo
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金
- **目前版本**：v18.263_FormulaSheetInCalc（Tab2 投資試算加「📐 完整計算公式」expander — 含數字代入 / 4 分支全覆蓋 / 公式參考 Tab3 estimate_dividend_split 但加入逐步展示）
  - **#120**：Tab2「💰 投資試算」widget 在 4 個 metric 卡 + st.success 摘要句後，加一個收合 `📐 完整計算公式（含數字代入）`，用 `st.code(language="text")` 等寬呈現「公式 = 數字代入 = 結果」三段。覆蓋 4 個分支（配息型/累積型 × TWD/非 TWD）— 配息型展示 7 段（原幣本金 / 可申購單位 / 年月配息原幣 / 年月配息 TWD / 月配股單位）；累積型展示 3 段（單位 / 1Y 後預估 / 預估損益）。caption 列 4 條估算假設（FX/NAV/ADR 不變、配息 100% 再投入計算月配股）+ 「實際配息以保險公司每月對帳單為準」免責。零 logic 變更，純呈現增量。
  - **#119**：P0 hotfix — Streamlit Cloud「Oh no. Error running app.」白屏。根因 `ui/helpers/data_registry.py:104` 用 `os.environ.get` 但檔頭缺 `import os`，Bug 自 5/18 初始 migration commit `9dcab88` 就潛伏；Python `or` short-circuit 在 secrets 有 `FRED_API_KEY` 時不會走到 `os.environ` → 一直沒爆；近期某次 redeploy 把 secret 清空 → fallback 走到 `os.environ` → NameError → app crash。fix 補 `import os` 一行，零行為變更。
  - **#117**：危機回測室「跑訊號回看 / 跑網格」按鈕無反應。根因：Phase 1 主按鈕 `run = st.button(...)` + `if not run: return` 是 click-only 一次性 gating；按 Phase 3/4 button 觸發 rerun 後 `run = False` → 主函式提前 return → Phase 3/4 sections 不再渲染 → 點擊被吞。fix 三段 session_state cache + 參數 hash invalidation：Phase 1 寫 `_crisis_phase1_cache`、Phase 3 寫 `_crisis_phase3_cache`、Phase 4 既有 `_crisis_grid_cache` 自動 reachable；market/threshold/years/fund_key 任一改變 → invalidate 全部下游 cache。test_tab_crisis_backtest_gating +7 case（params signature 純函式 / invalidate 副作用 / cache key 互不相同）。
  - **#118**：docs — 對齊 STATE.md 至 v18.261（PR #117 後漏同步 doc）。
  - **#98**：v18.251 風險評分真值校準器 + Tab1 互動式儀表板 — 新 `services/risk_calibration.py`（純函式，零 I/O）：`label_forward_drawdown` / `compute_calibration` / `grid_search_threshold` / `rolling_risk_score` / `generate_synthetic_demo`。Tab1 加「🎯 風險評分校準」expander（3 滑桿 horizon/drawdown/window + 4 metrics 最佳門檻/Precision/Recall/F1 + Top10 grid 表）。test_risk_calibration +9 case。sandbox 無 FRED outbound → 用合成資料 demo pipeline；真值校準需 user-side 餵入 live (VIX,HY,Yield,SPX) 月序列。**v18.253 後**由 PR #103 + #104 補上真實 FRED+SPX 路徑、PR #105 進 AI snapshot。
  - **#116**：closed (duplicate of #115)。本 session 沒先 fetch main 就規劃 v18.252 改 TWD 優先，發現 main 早在 PR #115 (14:54) 已實現等價功能，主動關閉避免合併造成代碼漂移。教訓：動工前必須 `git log HEAD..origin/main` sync。
- **前版**：v18.262_DataRegistryOsImportFix（補 os import 救活 app）
- **前二版**：v18.261_CrisisTabButtonsFix（危機回測室按鈕 session_state cache）
- **前三版**：v18.260p6_InvestCalcTWDFirst（投資試算改 TWD 為主，內部換原幣算單位/月配息/月配股）
  - **#114**：上接 #113。新增 `services/crisis_ai_advisor.py`（~170 行）+ 13 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加 `_render_ai_advice_block`（共用 `_GRID_CACHE_KEY` session_state 把 Phase 4 結果跨 rerun 保活，按「請 Gemini 解讀」即把事件 + grid + Top-1 餵 Gemini）。引擎核心：`build_strategy_advice_prompt`（≤800 字白話 prompt：危機事件條列 + grid markdown 表 + Top-1 條列 + 4 段輸出模板「最佳策略解讀/風險盲點/該怎麼做/一句話總結」）+ `generate_strategy_advice`（薄包 `services.ai_service.gemini_generate` + `get_gemini_keys` 守衛，無 key/空 grid 給警示不丟例外）+ 3 內部 summarizer（`_summarize_events`/`_summarize_grid`/`_summarize_top` 限筆 + NaN safe + Series/dict 雙吃）。UI：「🤖 AI 策略建議」expander 於 grid section 末尾，呼叫前用 `get_gemini_keys()` 守衛無 key warning + 顯示可用 key 數，呼叫中 `st.spinner` 提示 10-20 秒。累計測試 77 passed（Phase 1: 20 + Phase 3: 19 + Phase 4: 25 + Phase 5: 13）。
  - **#113**：Phase 4 — 新增 `services/crisis_strategy_grid.py`（~220 行）+ 25 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加「🧪 策略網格搜尋」section。引擎核心：`StrategySpec` frozen dataclass + `DEFAULT_STRATEGIES`（buy_and_hold/signal_exit/signal_half/buy_dip）+ `run_strategy`（t-1 訊號決定 t 倉位避免前視偏誤、計算 final_value/total_return/max_drawdown/sharpe/crisis_return_pct）+ `grid_search`（4×3 cell）+ `results_to_dataframe` + `build_heatmap_data`（pivot 成策略×門檻矩陣）+ `rank_results`（top-N）。UI 3 inputs（訊號 selectbox、metric selectbox、門檻文字框）+「跑網格」按鈕 + plotly heatmap（RdYlGn 色階）+ Top-5 排行 DataFrame + 完整 12-cell expander。
  - **#112**：Phase 3 — 新增 `services/macro_signal_lookback.py`（249 行）+ 19 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加「🚦 總經訊號預測力驗證」section。引擎核心：`SignalSpec` dataclass + `DEFAULT_SIGNALS`（VIX > 25 / HY > 6% / T10Y2Y < 0 / UNRATE > 5%）+ `fetch_signal_series`（Yahoo / FRED 雙來源 wrapper）+ `evaluate_signal_at_event`（點觀測 + 峰前最早警戒搜尋 → lead_time_days）+ `lookback_all_signals`（批次）+ `compute_signal_hit_rate`（命中率/平均提前天數）。UI 2 sliders（offset 30-180、上限 90-540 天）+「跑訊號回看」按鈕 + 命中率總覽 DataFrame + 逐事件 × 逐訊號明細表（✅/❌/— 圖示）。
  - **#111**：Phase 2 UI — 新增 `ui/tab_crisis_backtest.py` 230 行 + `app.py` 註冊 Tab「📉 危機回測室」（插在「🔍 單一基金」與「🔬 資料診斷」之間，共 6 個 tab）。UI：3 inputs（market radio SPX/TWII、threshold slider -30%~-5%、年數 3-20）+ 基金 full_key 預設帶 `st.session_state.fund_data` + 「開始回測」按鈕。輸出：4 統計卡 + 該基金 3 卡 + plotly 走勢圖（紅色 shaded 危機區 + 跌幅 annotation）+ DataFrame 事件清單（10 欄）+ CSV 下載。
  - **#110**：Phase 1 純後端引擎 `services/crisis_backtest.py`（247 行）+ 20 單元測試。`CrisisEvent` dataclass + `detect_crisis_events`（HWM walk-forward）+ `attach_fund_drawdown` + `fetch_market_series`（SPX/TWII wrapper）+ `summarize_events_with_fund` 一條龍。
- **前版**：v18.260p5_AIAdvice（危機回測室 + Gemini AI 策略建議，Phase 5，5-PR Sprint 收官）
- **前二版**：v18.260p4_StrategyGrid（危機回測室 + 4 策略 × 3 門檻 grid_search + heatmap，Phase 4）
- **前三版**：v18.260p3_MacroSignalLookback（危機回測室 + 總經訊號預測力驗證，Phase 3）
  - **#109**：v18.258「投資試算」原本只顯示基金原幣，user 反映「USD/EUR 看不直觀」→ 加 TWD 換算。非 TWD 基金用既有 `repositories.fund_repository.get_latest_fx("{CCY}TWD=X")`（5min TTL cache + NAS proxy 抓 Yahoo Chart REST API）取即時匯率，原幣 metrics 維持，下方加 `st.success` 顯示「💱 換算 TWD（1 USD = X.XXXX）：本金 / 年息 / 月息 TWD 金額」；累積型同理顯示本金 + 1Y 後預估 + 損益 TWD。Stash 加 `fx_to_twd / amount_twd / annual_dividend_twd / monthly_dividend_twd / proj_1y_twd` 欄位；AI snapshot 拼進 TWD 換算字串讓 AI 解盤可雙幣別參考。加 4 個 regression tests（FX import / TWD 顯示 / stash 欄位 / snapshot 翻譯）。test_tab2_single_fund.py **12 passed**（+4）。
- **前二版**：v18.258_InvestCalc（單一基金加投入金額試算 → 單位數 / 配息）
  - **#108**：Tab2 單一基金在 AI 深度解盤上方多一個「💰 投資試算」章節 — 用 `st.number_input` 收投入金額（預設 1,000,000、基金原幣別），用 NAV 算可申購單位數；配息型基金 → 年化配息 + 月配息估計；累積型基金 → 用近 1Y 含息報酬推估 1 年後市值。試算結果同步 stash 進 `st.session_state[f"_calc_invest_{fk}"]` 並接進 `_snap` AI snapshot；sections 清單擴入「投資試算」讓 AI 主動引用。加 3 個 source-level tests（section 存在 / 順序在 AI 上方 / stash 進 snapshot）。test_tab2_single_fund.py 8 passed（+3）。
- **前三版**：v18.257_NoStStop（移除 st.stop() 救活下方所有 sections）
  - **#107**：第二張校準卡（景氣分數）line 1445 + 1451 兩個 `st.stop()` 在沒按抓資料按鈕時直接 kill Streamlit script → user 看到「景氣分數校準」下方所有 sections（流動性壓力、景氣循環羅盤、23 項加扣分、熱錢、新聞 等）**全部不 render**。Hotfix 用 `_msc_ready` flag 模式取代 stop（與第一張卡 `_df_src is not None` 守衛同思路）；加 2 個 regression tests 鎖死「render_macro_tab 內禁 st.stop()」+「必須用 _msc_ready flag」。test_tab1_macro.py 15 passed（+2）。
- **前四版**：v18.256_NestedExpanderHotfix（校準卡解說改 checkbox toggle）
  - **#106**：v18.255 兩張校準卡的「📖 怎麼讀這張卡？」用 `st.expander` 在父層 expander 內巢狀崩潰（Streamlit 1.45.1 嚴禁）— Hotfix 改 `st.checkbox` toggle（與 line 1443 grid_search 同招）；regression test 加 assert 鎖死「必須是 st.checkbox」。Production blocker 已解除。
- **前五版**：v18.255_AISnapshotFullCoverage（校準卡白話三段式 + 9 章節進 AI 總體檢）
  - **#105**：兩張校準卡（風險評分 / 景氣分數）內聯解說 — 含①算什麼 / ②參數意義 / ③看到結果該怎麼做。Tab1 共 9 個原本未進 AI 的章節（流動性壓力、景氣循環羅盤、23 項加扣分明細、資本防線、倒掛翻正歷史回測、總經因果鏈 Sankey、細項燈號回測、變數重要性、台股熱錢）各自 stash 重點到 `st.session_state["_macro_<key>"]`（hot_money.py 同改）。`_build_macro_ai_snapshot` 讀全部 stash 用白話翻譯成新章節；校準健檢區塊改三段式「【代表】/【為什麼】/【該怎麼做】」；sections 清單擴 9 個 keys。新增 8 個測試（snapshot 各 section 翻譯 + 三段式格式 + sections 完整性 + 校準卡 expander 結構驗證）。
- **前六版**：v18.254_CalibHealthInAISnapshot（兩校準器去合成模式 + 校準健檢入 AI 白話總體檢）
  - **#104**：兩個校準器（3-factor 風險 / 14-factor 景氣）radio「🧪 合成 / 📊 真實」改為單一「真實 FRED+SPX」路徑；校準結果寫 `st.session_state["_cal_macro_score"|"_cal_risk_score"]`；`_build_macro_ai_snapshot` 新增「校準健檢」段落（總命中率 / 各位階命中率 / grid_search top / 最佳 F1 門檻 或無命中訊息），sections 加 `"校準健檢"` widget 自動產白話段落。`services/*.generate_synthetic_demo()` 保留供測試 fixture。tests 735 passed, 1 skipped。
- **前七版**：v18.253_RiskCalibrationReal（3-factor 風險評分校準補上真實 FRED+SPX 模式）
  - 沿革：#98 風險評分校準（3-factor）→ #99 修巢狀 expander → #100 景氣分數校準（14-factor）→ #101 grid_search 改 checkbox 避巢狀 → #102 synth lead-lag 升級 + 14-factor 真實 FRED+SPX 抓取 → #103 3-factor 真實 FRED+SPX 抓取
  - 兩個校準並存（v18.254 後皆改為單一真實 FRED+SPX 路徑）：
    - `services/risk_calibration.py`（3-factor SPX drawdown：VIX/HY/T10Y2Y）
    - `services/macro_score_calibration.py`（14-factor 景氣位階）

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
