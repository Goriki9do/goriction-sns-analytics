@echo off
REM Updates TikTok first, then YouTube, in one go.
REM Runs even if there is no new TikTok zip in Downloads (that step just skips).

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
if not exist youtube\run_youtube.bat (
    echo youtube\run_youtube.bat not found. Has the YouTube project been moved here yet?
    goto :error
)
pushd youtube
call run_youtube.bat
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
