@echo off
title Claude Usage Monitor – Installer
echo.
echo  Claude AI Usage Monitor for Windows
echo  =====================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Download it from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo  Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo  [ERROR] Installation failed. Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo  Done! Run the app with:  run.bat
echo  Or double-click run.bat
echo.
pause
