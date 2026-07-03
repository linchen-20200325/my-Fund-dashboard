@echo off
chcp 65001 >nul
cd /d E:\01.Github\my-Fund-dashboard
echo === 準備 commit v19.293 ===
git add repositories/news_repository.py
git add ui/tab5_data_guard.py
git add app.py
git add STATE.md
git commit -m "fix: dead Reuters RSS + Tab5 build_signals kwarg + APP_VERSION update (v19.293)

- repositories/news_repository.py: remove 3 feeds.reuters.com entries
  (Reuters Business / Markets / Top News dead since June 2020, all 404)
- ui/tab5_data_guard.py: fix build_signals() kwarg names
  flow_thr_yi -> flow_thr, fx_thr_pct -> fx_thr (TypeError fix)
- app.py: APP_VERSION v19.45_MacroNavigator -> v19.293_MacroNavigator"
echo === 推送到 GitHub ===
git push
echo === 完成 ===
pause
