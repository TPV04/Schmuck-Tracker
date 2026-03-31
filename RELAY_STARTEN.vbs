Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\lyl_relay.py""", 0, False
Set WshShell = Nothing
