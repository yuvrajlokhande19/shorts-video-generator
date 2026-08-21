Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")

' Start the Flask server hidden (no terminal window)
WshShell.Run """" & scriptDir & "\venv\Scripts\python.exe"" """ & scriptDir & "\app.py""", 0, False

' Wait for the server to boot, then open the browser
WScript.Sleep 4000
WshShell.Run "http://127.0.0.1:5000"
