@echo off
REM Updates TikTok first, then YouTube, in one go.
REM Assumes the YouTube project has been moved into the youtube/ folder here.

cd /d "%~dp0"

echo === Updating TikTok ===
call tiktok\update_tiktok.bat
if errorlevel 1 goto :error

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
echo All done.
pause
exit /b 0

:error
echo.
echo Something went wrong. See the error message above.
pause
exit /b 1
