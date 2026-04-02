' ============================================================
' Tony-Chrome mit Debug-Port 9222 starten
' Nutzt das Default-Profil (Tony - Chrome vom Desktop)
' ============================================================

Set oShell = CreateObject("WScript.Shell")

chromePath  = "C:\Program Files\Google\Chrome\Application\chrome.exe"
profilPfad  = "C:\Users\Tony\AppData\Local\Google\Chrome\User Data"

' Laufendes Chrome beenden damit Profil nicht gesperrt ist
oShell.Run "taskkill /F /IM chrome.exe", 0, True
WScript.Sleep 1500

' Tony-Chrome mit Debug-Port starten (off-screen, unsichtbar)
oShell.Run """" & chromePath & """" & _
    " --remote-debugging-port=9222" & _
    " --remote-allow-origins=*" & _
    " --user-data-dir=""" & profilPfad & """" & _
    " --profile-directory=Default" & _
    " --window-position=-32000,-32000" & _
    " --window-size=1280,900" & _
    " --no-first-run" & _
    " --no-default-browser-check" & _
    " --disable-notifications" & _
    " https://ucp.lyl.gg/houses", 0, False
