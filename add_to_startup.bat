@echo off
:: Adds claude_usage.py to Windows startup so it runs automatically on login

set "SCRIPT_DIR=%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=ClaudeUsageMonitor.bat"

echo @echo off > "%STARTUP%\%SHORTCUT_NAME%"
echo cd /d "%SCRIPT_DIR%" >> "%STARTUP%\%SHORTCUT_NAME%"
echo start "" pythonw.exe "%SCRIPT_DIR%claude_usage.py" >> "%STARTUP%\%SHORTCUT_NAME%"

echo.
echo  Claude Usage Monitor will now start automatically on login.
echo  To remove: delete  %STARTUP%\%SHORTCUT_NAME%
echo.
pause
