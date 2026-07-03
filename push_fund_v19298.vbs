Dim shell, cmd, result
Set shell = CreateObject("WScript.Shell")

cmd = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" add -A"
shell.Exec(cmd)
WScript.Sleep 1500

cmd = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" commit -m ""v19.298: MK 3-3-3 inception_date priority + wb01 3Y fallback for short NAV series; fixes group health tab + health report + replacement verdict"""
shell.Exec(cmd)
WScript.Sleep 3000

cmd = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" push origin main"
shell.Exec(cmd)
WScript.Sleep 5000

MsgBox "Fund v19.298 push done!", vbInformation, "Git Push"
