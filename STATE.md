# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡狀態檔。專案具體進度見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md`、`SPEC.md`、`STRATEGY.md`。

## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — 對應台灣 user 的 USD/EUR 計價基金 TWD 換匯後績效分析
- **技術棧**：Streamlit + pandas + plotly/altair + Google Sheets + FinMind/Yahoo
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金
- **目前版本**：v18.254_CalibHealthInAISnapshot（兩校準器去合成模式 + 校準健檢入 AI 白話總體檢）
  - **#104**：兩個校準器（3-factor 風險 / 14-factor 景氣）radio「🧪 合成 / 📊 真實」改為單一「真實 FRED+SPX」路徑；校準結果寫 `st.session_state["_cal_macro_score"|"_cal_risk_score"]`；`_build_macro_ai_snapshot` 新增「校準健檢」段落（總命中率 / 各位階命中率 / grid_search top / 最佳 F1 門檻 或無命中訊息），sections 加 `"校準健檢"` widget 自動產白話段落。`services/*.generate_synthetic_demo()` 保留供測試 fixture。tests 735 passed, 1 skipped。
- **前版**：v18.253_RiskCalibrationReal（3-factor 風險評分校準補上真實 FRED+SPX 模式）
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
