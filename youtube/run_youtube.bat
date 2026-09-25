@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
call "%~dp0bootstrap.bat"
if errorlevel 1 goto finish
if not defined SNS_DATA_HOME set "SNS_DATA_HOME=%LOCALAPPDATA%\GorictionSNS"
set "PYTHONDONTWRITEBYTECODE=1"
echo Goriction YouTube - launcher v0.1.4
echo Data folder: "%SNS_DATA_HOME%"
"%SNS_PYTHON%" -B -X utf8 "%~dp0run.py" --allow-google-auth %*
if errorlevel 1 echo Fetch failed. Please show the message above to Codex.
:finish
pause
