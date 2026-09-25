@echo off
cd /d "%~dp0"

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :error
)

.venv\Scripts\pip install -q -r requirements.txt
if errorlevel 1 goto :error

.venv\Scripts\python fetch.py
if errorlevel 1 goto :error

echo.
echo Done. See exports\posts.csv
pause
exit /b 0

:error
echo.
echo Something went wrong. See the error message above.
pause
exit /b 1
