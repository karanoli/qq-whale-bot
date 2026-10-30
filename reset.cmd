@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Run setup.cmd first.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0reset-memory.py"
pause
