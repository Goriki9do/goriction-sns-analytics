@echo off
cd /d "%~dp0"

.venv\Scripts\python fetch.py
if errorlevel 1 goto :error

echo.
echo Done. See exports\media.csv
pause
exit /b 0

:error
echo.
echo Something went wrong. See the error message above.
pause
exit /b 1
