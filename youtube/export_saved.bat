@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
call bootstrap.bat
if errorlevel 1 goto finish
"%SNS_PYTHON%" -B -X utf8 "%~dp0run.py" --export-only
:finish
pause
