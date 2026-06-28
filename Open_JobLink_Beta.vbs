Option Explicit

Dim shell, fileSystem, projectFolder, pythonExe, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectFolder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExe = projectFolder & "\.venv\Scripts\pythonw.exe"

If Not fileSystem.FileExists(pythonExe) Then
    MsgBox "The Python environment was not found in the job folder.", vbExclamation, "JobLink"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectFolder
command = Chr(34) & pythonExe & Chr(34) & _
          " -c " & Chr(34) & _
          "from scraper.app import app; app.run(host='127.0.0.1', port=5050, debug=False, threaded=True)" & _
          Chr(34)

shell.Run command, 0, False
WScript.Sleep 2500
shell.Run "http://127.0.0.1:5050", 1, False
