@echo off
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
 echo Please run install.cmd or setup.cmd first.
 pause
 exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0model_settings.py"
