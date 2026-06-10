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
- **feat(macro) PR #251 @ fb4622d v19.42**：拆除單一 tab 包裝 → ① 戰情室（總經）成為頁面首屏。user v19.41 後仍反饋「上方仍沒有總經 短期 拐點面板」— 根因：Streamlit 單一 tab strip + roadmap caption 擋在 ① 戰情室上方。改動：`(tab_main,) = st.tabs([...])` 改用 `contextlib.nullcontext()`，所有 `with tab_main:` 區塊保持縮排不變（零功能變動）；roadmap caption 移除，由 ①②③④⑤⑥ 編號 heading 隱含順序。新視覺流：資料 banner → ① 戰情室（總經）→ ④ 短期 → ② 拐點 → ⑤⑥ → ③ → MK 時鐘。
- **feat(macro) PR #250 @ 016dd63 v19.41**：總經面板上移至 tab 首屏 — ③ 🔬 即時訊號決策矩陣 從戰情首頁 tab 外（L799）下移至 tab 內結尾（MK 時鐘前），讓 ① 戰情室（總經）成為 tab 首屏。新順序：① 總經 → ④ 短期 → ② 拐點 → ⑤ 流動性 → ⑥ 台股熱錢 → ③ 即時決策。caption 同步更新；指標教學手冊指引改指 📖 說明書 Tab §11 宏觀教學文獻。
- **feat(macro) PR #249 @ 8293d62 v19.40 PR2**：教學面板搬遷至 📖 說明書 Tab §11 宏觀教學文獻（tab1 −361 行 / 2465→2104；tab6 +381 行 / 578→959）— §A 🎯 為什麼是這位階 / §B 📊 23指標教學手冊 / §C 📈 歷史對照圖 / §D 👉 加扣分明細（_macro_23items stash）/ §E 📊 變數重要性（_macro_var_importance stash）。stash 契約：tab1 寫入 _macro_ind，tab6 讀取並重現面板；stash 空 → 友善提示。1826 passed / 5 skipped。roadmap PR1→PR2 全部完成。
- **feat(macro) PR #247 @ 13026cc v19.39 PR1C**：archive 8 inline 面板（−830 行 / 3296→2466）— 🌡️ 風險溫度計 4 cards / V4 複合 / 🎯 風險評分校準 / 🧮 景氣分數校準 / 🧭 景氣羅盤 / 📅 Tier A / 🔗 因果鏈 Sankey / 📊 細項燈號回測。Stash 介面契約完整保留（_macro_compass / _macro_sankey / _macro_subsector_bt / _cal_*）— AI 摘要 widget 繼續吃齊。Cleanup：移除 3 個 unused imports + sc/ph_c 變數；2 個 archive-dependent tests 改 @pytest.mark.skip。
- **feat(macro) PR #245 @ a991f4f v19.38 PR1B**：archive 10+ inline 面板（−477 行 / 3772→3295）— 7 維獨立合議 / 7 子領域燈號 / 四大類別 / Hero 卡 / 景氣時鐘 / 天氣 / 風險警示 / 美林時鐘 / T1 事件衝擊。
- **feat(macro) PR #243 @ 91da530 v19.38 PR1**：總經 Tab 矛盾修正 — archive 雙速合議 + 台股本地視角；6 KEEP 面板按熊市驗證 ROI 重新編號（① 戰情室 / ② 拐點 / ③ 即時決策 / ④ 短線雷達 / ⑤ 流動性 / ⑥ 台股熱錢）；AI 景氣判斷總結加 caption 明示涵蓋同源資料。
- **fix(fund-health) PR #241 @ f791ba2**：保單體系代碼用 Tab2 同款 `fetch_fund_from_moneydj_url` 取 series + dividends + currency + fund_name。
- 初始化基準：協議 v2.0 Auto-Ship 套用，歷史版本紀錄詳見 `git log`。

## 下一步
v19.42 拆除單一 tab 包裝完成 → ① 戰情室（總經）為頁面首屏。
v19.41 + v19.42 雙重保險：③ 已在 tab 結尾 + tab strip 已消滅。
（待 user 確認 Streamlit Cloud redeploy 完成 → 應顯示 v19.42_MacroNoTabStrip）
