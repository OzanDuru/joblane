@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup-windows.cmd first.
  pause
  exit /b 1
)
powershell.exe -NoProfile -File "%~dp0start-windows.ps1"
pause
