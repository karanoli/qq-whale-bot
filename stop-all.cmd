@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-all.ps1" %*
if errorlevel 1 pause
