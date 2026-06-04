# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡熱資料檔。完整 roadmap 見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md` / `SPEC.md` / `STRATEGY.md`。

## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — TWD 換匯後績效 + 總經訊號 + 危機回測 + AI 策略建議
- **技術棧**：Streamlit + pandas + plotly/altair + FRED/Yahoo/FundClear + Google Sheets + Gemini API + NAS Squid Proxy
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金
- **入口**：`app.py`（Streamlit Cloud 部署）

## 當前版本
- **v18.285_MultiFactorPlateauWalkForward**：Phase 3 加「🔬 多因子權重最佳化」expander — 綜合分數 S_t = Σ w_i × normalize(I_{i,t−1})（lag=1 防未來引用），simplex 權重 grid sweep 算 F1+Sharpe，**plateau 評分 = 鄰域 mean − λ × std**（不取單一最高 F1）；walk-forward 滾動 train/test 串 OOS 權益曲線；plotly 2D heatmap + 3D surface toggle；10 因子池（4 現有 + 6 raw FRED：PMI/CPI/FedFunds/M2/DXY/T10Y3M）；28 case 驗收
- **v18.284_PresetMatrixCompareTable**：配置模擬器 selectbox 上方加「📊 4 風格 × 4 階段 對照表（全展開）」expander — DataFrame 4 phases × 4 styles = 16 cells "D / C / S" 字串，read-only，方便 user 橫向比較再選 preset 套用；engine 加 `build_preset_matrix_df()` helper
- **v18.283_MT5StyleAutoCalibration**：Phase 3 加「🎯 MT5-style 自動校準」expander — walk-forward 4 折 grid sweep × 3 重 anti-overfit gate（折間票選 + drift>30% 回退 + cap 守門）；session-only override 機制；對齊 stock v18.164；1205 passed
- **v18.282_SignalPrecisionAnalysis**：Phase 3 加「📐 訊號精確率分析」forward-looking 區塊 — 解召回率單面向：遍歷歷史 crossings 算 TP/FP/精確率/誤報率/avg lead time；對齊 stock v18.163；1195 passed
- **v18.281_Phase3EdgeDetection**：Phase 3 訊號回看引擎 port stock v18.160 v2 edge detection（從非警戒「跨越到」警戒的轉折日），修「常態性已警戒 = 假預警」誤判；UI 加「v2 轉折偵測」標示
- **v18.280_StrategyPresets**：配置模擬器加 4 風格 × 4 階段 preset 矩陣（積極成長 / 穩健平衡 / 收益優先 / 防禦保本），UI 一鍵套用 4 階段 DRIP/CASH/STAY 比例
- **v18.279_MacroScoreCalibration**：VIX 閾值 OOS 自動校正（5 重 anti-overfit gate：walk-forward / 正則項 / 票選 / bootstrap CI / 末段 36 月 holdout）
- **同期合入**：v18.279p_Phase5StackOrder — Phase 5 AI 區塊壓底，render 順序固定為 Phase 4 → Phase E → Phase 5

## 目錄結構
- `services/` — 業務邏輯（macro / strategy / AI / cross-source / liquidity / calibration）
- `repositories/` — 資料源抓取（FRED / Yahoo / FundClear / Macro）
- `infra/proxy.py` — NAS Squid 中繼站；HTTP gateway（含 407 / 403 / 429 / timeout 完整 fallback）
- `ui/` — Streamlit 分頁元件（tab1~tab6 + components）
- `scripts/` — `update_macro_history.py`（每週 cron 抓 FRED + Yahoo Parquet）/ `calibrate_macro_score.py`（VIX OOS 自動校正）
- `data_cache/*.parquet` — fred_indicators / spx_history / twii_history / vix_history（每週日 cron 更新）
- `.github/workflows/` — update_macro_history / recalibrate_macro_score / fetch_nav_cache / pr-check

## 即時健康指標
- **Test**：~1098 passed / 2 skipped / 0 failed（PR #169 修掉 3 個 pre-existing fail）
- **本日 PR**：#164 mk_clock 衰退誤判 / #165 Phase E 引擎 / #166 proxy 429 backoff / #167 Phase 5 壓底 / #170 VIX OOS 校正
- **協議**：Core Protocol v2.0（PR #168，嚴禁自動 Merge）
