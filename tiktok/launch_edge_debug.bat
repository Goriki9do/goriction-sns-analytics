@echo off
REM 既存のEdgeを一旦閉じて、外部から操作できるモードで開き直す。
REM プロファイル（ログイン状態・お気に入り）はそのまま引き継がれる。
REM 開いたら、いつも通りTikTokにログインしてTikTok Studioを開いておくこと。

taskkill /F /IM msedge.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --profile-directory="Default"

echo Edgeをリモート操作モードで起動したで。
echo このままEdgeでTikTokにログインし、TikTok Studioの分析画面まで開いておいてな。
echo 準備できたら export_studio_csv.py を実行してOK。
pause
