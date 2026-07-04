Dim shell
Set shell = CreateObject("WScript.Shell")
Dim git
git = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" "
shell.Run git & "add -A", 1, True
shell.Run git & "commit -m ""v19.301: fix OAuth state strict check — prevent cross-session token stealing (chen10021 account conflict)""", 1, True
shell.Run git & "push origin main", 1, True
MsgBox "Fund v19.301 push done!", vbInformation, "Git Push"
