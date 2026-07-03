@echo off
taskkill /f /im wscript.exe 2>nul
timeout /t 2 /nobreak >nul

cd /d "E:\01.Github\my-Fund-dashboard"

"C:\Program Files\Git\cmd\git.exe" add -A
"C:\Program Files\Git\cmd\git.exe" commit -m "v19.298: MK 3-3-3 inception_date priority + wb01 3Y fallback for short NAV series; fixes group health tab + health report + replacement verdict"
"C:\Program Files\Git\cmd\git.exe" push origin main

echo.
echo === Done! ===
pause
