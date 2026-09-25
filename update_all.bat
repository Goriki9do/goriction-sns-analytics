@echo off
REM Updates TikTok first, then YouTube, in one go.
REM Runs even if there is no new TikTok zip in Downloads (that step just skips).

chcp 65001 >nul
cd /d "%~dp0"

echo === Updating TikTok ===
pushd tiktok
.venv\Scripts\python import_downloads.py
if errorlevel 1 (
    popd
    goto :error
)
.venv\Scripts\python normalize_export.py
if errorlevel 1 (
    popd
    goto :error
)
popd

echo.
echo === Updating YouTube ===
if not exist youtube\run.py (
    echo youtube\run.py not found. Has the YouTube project been moved here yet?
    goto :error
)
pushd youtube
REM Same steps as run_youtube.bat, but without its trailing pause, so this
REM script can continue straight on to the exports_local copy step below.
call bootstrap.bat
if errorlevel 1 (
    popd
    goto :error
)
if not defined SNS_DATA_HOME set "SNS_DATA_HOME=%LOCALAPPDATA%\GorictionSNS"
set "PYTHONDONTWRITEBYTECODE=1"
echo Goriction YouTube - launcher v0.1.4
echo Data folder: "%SNS_DATA_HOME%"
"%SNS_PYTHON%" -B -X utf8 run.py --allow-google-auth
if errorlevel 1 (
    echo Fetch failed. Please show the message above to Codex.
    popd
    goto :error
)
popd

echo.
echo === Copying YouTube exports into youtube\exports_local ===
pushd youtube
python sync_exports.py
popd

echo.
echo All done.
pause
exit /b 0

:error
echo.
echo Something went wrong. See the error message above.
pause
exit /b 1
