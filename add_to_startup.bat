@echo off
cd /d "%~dp0"
set APPDIR=%~dp0
set ELECTRON=%APPDIR%node_modules\.bin\electron.cmd
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "ClaudeUsageMonitor" /t REG_SZ /d "\"%ELECTRON%\" \"%APPDIR%.\"" /f
echo Lagt til Windows-opstart.
pause
