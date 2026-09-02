Option Explicit

Dim shell, fileSystem, projectFolder, pythonExe, pythonConsoleExe, launcherScript, command, checkCommand, checkProcess
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectFolder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExe = projectFolder & "\.venv\Scripts\pythonw.exe"
pythonConsoleExe = projectFolder & "\.venv\Scripts\python.exe"
launcherScript = projectFolder & "\desktop_launcher.py"

If Not fileSystem.FileExists(pythonExe) Then
    MsgBox "Linc could not find its Python environment. Finish the local setup, then try again.", vbExclamation, "Linc"
    WScript.Quit 1
End If

If Not fileSystem.FileExists(launcherScript) Then
    MsgBox "Linc could not find its desktop launcher.", vbExclamation, "Linc"
    WScript.Quit 1
End If

shell.CurrentDirectory = projectFolder
checkCommand = Chr(34) & pythonConsoleExe & Chr(34) & " -c " & Chr(34) & "import flask, werkzeug" & Chr(34)
Set checkProcess = shell.Exec(checkCommand)
Do While checkProcess.Status = 0
    WScript.Sleep 50
Loop

If checkProcess.ExitCode <> 0 Then
    MsgBox "Linc's local Python environment is missing required packages. Run the local setup again, then open Linc from this file.", vbExclamation, "Linc"
    WScript.Quit 1
End If

command = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & launcherScript & Chr(34)
shell.Run command, 1, False
