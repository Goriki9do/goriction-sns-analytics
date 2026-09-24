@echo off
REM After downloading from TikTok Studio, just double-click this file.
REM 1. Extract zip files from the Downloads folder into exports/inbox
REM 2. Normalize the CSVs in exports/inbox into the exports/*.csv files

cd /d "%~dp0"

.venv\Scripts\python import_downloads.py
if errorlevel 1 goto :error

.venv\Scripts\python normalize_export.py
if errorlevel 1 goto :error

echo.
echo Done. See the exports folder for videos.csv / channel_daily.csv / follower_daily.csv
pause
exit /b 0

:error
echo.
echo Something went wrong. See the error message above.
pause
exit /b 1
