# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡狀態檔。專案具體進度見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md`、`SPEC.md`、`STRATEGY.md`。

## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — 對應台灣 user 的 USD/EUR 計價基金 TWD 換匯後績效分析
- **技術棧**：Streamlit + pandas + plotly/altair + Google Sheets + FinMind/Yahoo
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金
- **目前版本**：v18.260p3_MacroSignalLookback（危機回測室 + 總經訊號預測力驗證，Phase 3）
  - **#112**：上接 #111 UI。新增 `services/macro_signal_lookback.py`（249 行）+ 19 單元測試 + 擴充 `ui/tab_crisis_backtest.py` 加「🚦 總經訊號預測力驗證」section。引擎核心：`SignalSpec` dataclass + `DEFAULT_SIGNALS`（VIX > 25 / HY > 6% / T10Y2Y < 0 / UNRATE > 5%）+ `fetch_signal_series`（Yahoo / FRED 雙來源 wrapper）+ `evaluate_signal_at_event`（點觀測 + 峰前最早警戒搜尋 → lead_time_days）+ `lookback_all_signals`（批次）+ `compute_signal_hit_rate`（命中率/平均提前天數）。UI 2 sliders（offset 30-180、上限 90-540 天）+「跑訊號回看」按鈕 + 命中率總覽 DataFrame + 逐事件 × 逐訊號明細表（✅/❌/— 圖示）。FRED key 從 `os.environ["FRED_API_KEY"]` 取（app.py 已 inject）。
  - **#111**：Phase 2 UI — 新增 `ui/tab_crisis_backtest.py` 230 行 + `app.py` 註冊 Tab「📉 危機回測室」（插在「🔍 單一基金」與「🔬 資料診斷」之間，共 6 個 tab）。UI：3 inputs（market radio SPX/TWII、threshold slider -30%~-5%、年數 3-20）+ 基金 full_key 預設帶 `st.session_state.fund_data` + 「開始回測」按鈕。輸出：4 統計卡 + 該基金 3 卡 + plotly 走勢圖（紅色 shaded 危機區 + 跌幅 annotation）+ DataFrame 事件清單（10 欄）+ CSV 下載。
  - **#110**：Phase 1 純後端引擎 `services/crisis_backtest.py`（247 行）+ 20 單元測試。`CrisisEvent` dataclass + `detect_crisis_events`（HWM walk-forward）+ `attach_fund_drawdown` + `fetch_market_series`（SPX/TWII wrapper）+ `summarize_events_with_fund` 一條龍。
- **前版**：v18.259_InvestCalcTWD（投資試算加 TWD 即時匯率換算）
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
