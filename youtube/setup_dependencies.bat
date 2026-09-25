@echo off
setlocal
cd /d "%~dp0"
call bootstrap.bat
if errorlevel 1 goto finish
if not defined SNS_DATA_HOME set "SNS_DATA_HOME=%LOCALAPPDATA%\GorictionSNS"
"%SNS_PYTHON%" -m pip install --target "%SNS_DATA_HOME%\vendor" -r requirements-lock.txt
:finish
pause
