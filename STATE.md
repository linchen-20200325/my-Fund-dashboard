# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡熱資料檔。完整 roadmap 見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md` / `SPEC.md` / `STRATEGY.md`。

## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — TWD 換匯後績效 + 總經訊號 + 危機回測 + AI 策略建議
- **技術棧**：Streamlit + pandas + plotly/altair + FRED/Yahoo/FundClear + Google Sheets + Gemini API + NAS Squid Proxy
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金
- **入口**：`app.py`（Streamlit Cloud 部署）

## 當前版本
- **v18.279_Phase5StackOrder**：Phase 5 AI 區塊壓底，render 順序固定為 Phase 4 → Phase E → Phase 5（確保 AI prompt 能讀完上方所有結果）

## 目錄結構
- `services/` — 業務邏輯（macro / strategy / AI / cross-source / liquidity）
- `repositories/` — 資料源抓取（FRED / Yahoo / FundClear / Macro）
- `infra/proxy.py` — NAS Squid 中繼站；HTTP gateway（含 407 / 403 / 429 / timeout 完整 fallback）
- `ui/` — Streamlit 分頁元件（tab1~tab6 + components）
- `scripts/update_macro_history.py` — 每週 cron 抓 FRED + Yahoo Parquet 快取
- `data_cache/*.parquet` — fred_indicators / spx_history / twii_history / vix_history（每週日 cron 更新）
- `.github/workflows/` — update_macro_history / fetch_nav_cache / pr-check

## 即時健康指標
- **Test**：1096 passed / 1 skipped / 3 pre-existing failed（test_hot_money altair 版本 + test_tab6_manual mock spec）
- **本日 PR**：#164 mk_clock 衰退誤判 / #165 Phase E 引擎 / #166 proxy 429 backoff / #167 Phase 5 壓底
- **主分支**：commit `dc48e5e`
