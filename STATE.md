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
- **feat(macro) PR #243 @ 91da530 v19.38**：總經 Tab 矛盾修正 PR1 — archive 雙速合議 + 台股本地視角（user 抱怨的長期/短期矛盾源頭，sub-function 模組保留磁碟）；6 個 KEEP 面板按熊市驗證 ROI 重新編號 ①-⑥（① 戰情室 / ② 拐點 / ③ 即時決策 / ④ 短線雷達 / ⑤ 流動性 / ⑥ 台股熱錢）；AI 景氣判斷總結加 caption 明示涵蓋上方 6 KEEP 同源資料。PR1B 待續（archive 11+ 冗余 inline 面板），PR2 待續（教學面板搬遷至 📖 說明書 Tab）。
- **fix(fund-health) PR #241 @ f791ba2**：保單體系代碼用 Tab2 同款 `fetch_fund_from_moneydj_url` 取 series + dividends + currency + fund_name；表格加「基金名 / 幣別偵測」。
- **fix(fund-health) PR #239 @ 32546a8**：cnyes 單源 → `fetch_nav / fetch_div` 多源 fallback（後被 #241 超越）。
- 初始化基準：協議 v2.0 Auto-Ship 套用，歷史版本紀錄詳見 `git log`。

## 下一步
（待 user 指示）
