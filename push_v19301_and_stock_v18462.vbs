Dim shell
Set shell = CreateObject("WScript.Shell")

Dim gitF
gitF = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-Fund-dashboard"" "

Dim gitS
gitS = """C:\Program Files\Git\cmd\git.exe"" -C ""E:\01.Github\my-stock-dashboard"" "

' ── Fund v19.301 ──────────────────────────────────────────
shell.Run gitF & "add -A", 1, True
shell.Run gitF & "commit -m ""v19.301: fix OAuth state strict check — prevent cross-session token stealing (chen10021 account conflict)""", 1, True
shell.Run gitF & "push origin main", 1, True

' ── Stock v18.462 ─────────────────────────────────────────
shell.Run gitS & "add -A", 1, True
shell.Run gitS & "commit -m ""v18.462: fix OAuth state strict check — prevent cross-session token stealing""", 1, True
shell.Run gitS & "push origin main", 1, True

MsgBox "Done! Fund v19.301 + Stock v18.462 pushed.", vbInformation, "Git Push"
