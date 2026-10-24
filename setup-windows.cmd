@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12 or newer from https://www.python.org/downloads/windows/ then run this file again.
  pause
  exit /b 1
)
py -3 -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer is required'"
if errorlevel 1 goto :failed
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto :failed
.venv\Scripts\python.exe run.py init
if errorlevel 1 goto :failed
echo.
echo Setup complete. Double-click start-windows.cmd to open Joblane.
pause
exit /b 0
:failed
echo.
echo Setup failed. Read the error above before trying again.
pause
exit /b 1
