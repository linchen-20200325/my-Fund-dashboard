@echo off
chcp 65001 >nul
cd /d E:\01.Github\my-Fund-dashboard
echo === 準備 commit v19.294 ===
git add ui/tab5_data_guard.py
git add ui/tab6_manual.py
git add ui/helpers/io/data_registry.py
git add app.py
git add STATE.md
git commit -m "fix: stale Reuters references in RSS source description strings (v19.294)

Reuters was removed from news_repository.py in v19.293, but 3 display
strings still listed it as an active source:
- ui/tab5_data_guard.py:408: RSS 來源欄更新
- ui/tab6_manual.py:511: 說明書 RSS 來源列表更新
- ui/helpers/io/data_registry.py:479: source 字串更新
All now show: MarketWatch/FT/Yahoo/Investing/CNBC/BBC/Bloomberg"
echo === 推送到 GitHub ===
git push
echo === 完成 ===
pause
