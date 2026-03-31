$action  = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "C:\Users\Tony\Desktop\Schmuck_Tracker\RELAY_STARTEN.vbs"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "LYL Markt Relay" -Action $action -Trigger $trigger -RunLevel Highest -Force
Write-Host "Task erstellt!"
