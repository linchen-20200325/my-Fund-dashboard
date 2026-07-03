Dim oShell
Set oShell = CreateObject("WScript.Shell")

Dim gitExe
gitExe = "C:\Program Files\Git\cmd\git.exe"

Dim repoPath
repoPath = "E:\01.Github\my-Fund-dashboard"

Dim proc, exitCode

Set proc = oShell.Exec("""" & gitExe & """ -C """ & repoPath & """ add -A")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
exitCode = proc.ExitCode
If exitCode <> 0 Then
    MsgBox "git add failed: " & proc.StdErr.ReadAll, 16, "Push Fund v19.297"
    WScript.Quit exitCode
End If

Set proc = oShell.Exec("""" & gitExe & """ -C """ & repoPath & """ commit -m ""v19.297: L1 NAV T+1~T+3 delay note in freshness banner; Yahoo Finance RSS dead->news/rssindex fixed; USDCNH thresholds 7.0/7.15/7.3->7.1/7.3/7.45 align post-2022 CNY weakness; comprehensive re-check confirms all data sources normal""")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
exitCode = proc.ExitCode
If exitCode <> 0 Then
    MsgBox "git commit failed (may already be committed): " & proc.StdErr.ReadAll, 48, "Push Fund v19.297"
End If

Set proc = oShell.Exec("""" & gitExe & """ -C """ & repoPath & """ push origin main")
Do While proc.Status = 0 : WScript.Sleep 200 : Loop
exitCode = proc.ExitCode
If exitCode <> 0 Then
    MsgBox "git push failed: " & proc.StdErr.ReadAll, 16, "Push Fund v19.297"
    WScript.Quit exitCode
End If

MsgBox "Fund v19.297 pushed successfully!", 64, "Push Fund v19.297"
WScript.Quit 0
