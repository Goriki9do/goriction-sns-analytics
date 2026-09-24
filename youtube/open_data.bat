@echo off
setlocal
call "%~dp0runtime.local.bat"
explorer "%SNS_DATA_HOME%"
