@echo off
REM TikTok Studioでダウンロードした後、これをダブルクリックするだけでOK。
REM 1. Downloadsフォルダのzipを展開してexports/inboxへコピー
REM 2. inboxのCSVをexports配下の各csvに整理

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
