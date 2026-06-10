Dim fso, dir, shell
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = dir
shell.Run "cmd /c " & Chr(34) & "C:\Program Files\nodejs\npm.cmd" & Chr(34) & " start", 0, False
