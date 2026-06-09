# STATE.md — 基金戰情室 (Fund Dashboard)

> 極簡熱資料檔。完整 roadmap 見 `BACKLOG.md`；技術細節見 `ARCHITECTURE.md` / `SPEC.md` / `STRATEGY.md`。

## 專案定位
- **產品**：境外共同基金（保險型保單）戰情室 — TWD 換匯後績效 + 總經訊號 + 危機回測 + AI 策略建議
- **技術棧**：Streamlit + pandas + plotly/altair + FRED / Yahoo / FundClear / Cnyes + Google Sheets + Gemini API + NAS Squid Proxy
- **入口**：`app.py`（Streamlit Cloud 部署）
- **核心禁令**：🚫 全面排除 ETF / 個股，本系統專注共同基金

## 目錄速覽
- `app.py` — Streamlit 主入口
- `services/` — 業務邏輯純函式層（macro / fund / portfolio / AI advisor / screener / risk）
- `repositories/` — 資料抓取層（FundClear / Cnyes / Yahoo / FRED / GSheet）
- `ui/` — Streamlit Tab 渲染層（總經 / 組合 / 單一基金 / 配置模擬 / 組合健診 / 資料診斷 / 說明書）
- `infra/` — OAuth / Proxy / 基礎建設
- `models/` — Pydantic / 領域物件
- `tests/` + 根 `test_*.py` — 單元測試
- `cache/` + `data_cache/` — 落地快取（NAV / FX / 政策 / MJ 快照）
- `scripts/` — 工具腳本（`quick_merge.sh` 等）
- `docs/`、`ARCHITECTURE.md`、`SPEC.md`、`BACKLOG.md`、`STRATEGY.md` — 技術文檔

## 當前版本
- **fix(fund-health) PR #241 @ f791ba2**：保單體系代碼仍抓不到 → 鏡像 Tab2「單一基金」`_auto_fetch_moneydj` 套路改用 `fetch_fund_from_moneydj_url(https://www.moneydj.com/funddj/ya/yp01000{0,1}.djhtm?a={code})` 一發拿 series + dividends + currency + fund_name；currency 自動偵測時直接用，無法偵測退回 fallback；表格加「基金名 / 幣別偵測」兩欄。
- **fix(fund-health) PR #239 @ 32546a8**：cnyes 單源不收保單代碼 → 改 `fetch_nav / fetch_div` 多源 fallback（後被 PR #241 超越）。
- 初始化基準：協議 v2.0 Auto-Ship 套用，歷史版本紀錄詳見 `git log`。

## 下一步
（待 user 指示）
