Dim oShell
Set oShell = CreateObject("WScript.Shell")
oShell.CurrentDirectory = "E:\01.Github\my-Fund-dashboard"
oShell.Run "cmd /c git add -A && git commit -m ""v19.295-296: audit fixes - Bloomberg/Investing/FT RSS removed, USDJPY/EURUSD thresholds, CHN_BCI label, AAII error label, Tab1 staleness emoji"" && git push origin main > E:\01.Github\my-Fund-dashboard\push_v19296.log 2>&1", 1, True
MsgBox "Fund push done - check push_v19296.log in repo root"
