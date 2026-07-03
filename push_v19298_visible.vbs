Dim shell
Set shell = CreateObject("WScript.Shell")
Dim git
git = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" "

shell.Run git & "add -A", 1, True
shell.Run git & "commit -m ""v19.298: MK 3-3-3 inception_date priority + wb01 3Y fallback for short NAV series; fixes group health tab + health report + replacement verdict""", 1, True
shell.Run git & "push origin main", 1, True

MsgBox "Fund v19.298 push done!", vbInformation, "Git Push"
