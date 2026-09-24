@echo off
REM Closes the current Edge and reopens it in remote-debugging mode.
REM The profile (login state, favorites, etc.) is kept as-is.
REM After it opens, log in to TikTok as usual and open TikTok Studio.

taskkill /F /IM msedge.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --profile-directory="Default"

echo Edge started in remote-debugging mode.
echo Log in to TikTok in that window as usual, and open TikTok Studio Analytics.
echo Once ready, run export_studio_csv.py
pause
