Dim oShell, oFSO, oFile, oExec
Set oShell = CreateObject("WScript.Shell")
Set oFSO = CreateObject("Scripting.FileSystemObject")
Dim logPath: logPath = "E:\01.Github\my-Fund-dashboard\git_push_v19294_log.txt"
Set oFile = oFSO.CreateTextFile(logPath, True)
Dim gitPath: gitPath = "C:\Program Files\Git\cmd\git.exe"
oShell.CurrentDirectory = "E:\01.Github\my-Fund-dashboard"

oFile.WriteLine "=== " & Now() & " ==="

Set oExec = oShell.Exec("""" & gitPath & """ status --short")
oFile.WriteLine "STATUS:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' v19.293: Reuters RSS removed + Tab5 kwarg fix + APP_VERSION
Set oExec = oShell.Exec("""" & gitPath & """ add repositories/news_repository.py")
oFile.WriteLine "add news_repository: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add ui/tab5_data_guard.py")
oFile.WriteLine "add tab5: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' v19.294: stale Reuters description strings
Set oExec = oShell.Exec("""" & gitPath & """ add ui/tab6_manual.py")
oFile.WriteLine "add tab6: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add ui/helpers/io/data_registry.py")
oFile.WriteLine "add data_registry: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add app.py")
oFile.WriteLine "add app.py: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()
Set oExec = oShell.Exec("""" & gitPath & """ add STATE.md")
oFile.WriteLine "add STATE.md: " & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' Commit
Dim commitMsg
commitMsg = "fix: dead Reuters RSS + Tab5 kwarg + stale source strings (v19.293-294)" & vbCrLf & vbCrLf & _
    "v19.293: Remove 3 feeds.reuters.com entries (dead since June 2020)" & vbCrLf & _
    "  Tab5 build_signals() kwarg names corrected (TypeError fix)" & vbCrLf & _
    "v19.294: Stale Reuters description strings in tab5/tab6/data_registry updated"

Set oExec = oShell.Exec("""" & gitPath & """ commit -m """ & commitMsg & """")
oFile.WriteLine "COMMIT:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

' Push
Set oExec = oShell.Exec("""" & gitPath & """ push origin main")
oFile.WriteLine "PUSH:" & vbCrLf & oExec.StdOut.ReadAll() & oExec.StdErr.ReadAll()

oFile.WriteLine "=== Done " & Now() & " ==="
oFile.Close
MsgBox "Fund dashboard pushed! Check git_push_v19294_log.txt", 64, "Git Push Done"
