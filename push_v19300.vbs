Dim shell
Set shell = CreateObject("WScript.Shell")
Dim git
git = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" "
shell.Run git & "add -A", 1, True
shell.Run git & "commit -m ""v19.300: fix UTC date.today() bug in tab5 hot money age display""", 1, True
shell.Run git & "push origin main", 1, True
MsgBox "Fund v19.300 push done!", vbInformation, "Git Push"
