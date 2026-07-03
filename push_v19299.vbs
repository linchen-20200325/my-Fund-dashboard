Dim shell
Set shell = CreateObject("WScript.Shell")
Dim git
git = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" "

shell.Run git & "add -A", 1, True
shell.Run git & "commit -m ""v19.299: 5Y return wb01 fallback + TW timezone fix for freshness banner""", 1, True
shell.Run git & "push origin main", 1, True

MsgBox "Fund v19.299 push done!", vbInformation, "Git Push"
