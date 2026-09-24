@echo off
set "SNS_PYTHON="
if exist "%~dp0runtime.local.bat" call "%~dp0runtime.local.bat"
if defined SNS_PYTHON if exist "%SNS_PYTHON%" exit /b 0
set "SNS_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%SNS_PYTHON%" exit /b 0
echo Python not found. Install Python 3.12+ from python.org or update runtime.local.bat.
exit /b 1
