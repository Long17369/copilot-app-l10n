@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/2] creating virtual environment...
  py -3.13 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo failed to create .venv - install Python 3.9+ first
    pause
    exit /b 1
  )
)

echo [2/2] installing dependencies...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo failed to install dependencies
  pause
  exit /b 1
)

".venv\Scripts\python.exe" install_zh.py %*
echo.
pause
