Option Explicit

Dim shell, fileSystem, projectFolder, pythonExe, launcherScript, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectFolder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExe = projectFolder & "\.venv\Scripts\pythonw.exe"
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
command = Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & launcherScript & Chr(34)
shell.Run command, 1, False
