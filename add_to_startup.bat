@echo off
cd /d "%~dp0"
set LAUNCHER=%~dp0launch.vbs
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "ClaudeUsageMonitor" /t REG_SZ /d "wscript.exe \"%LAUNCHER%\"" /f
echo Lagt til Windows-opstart.
pause
