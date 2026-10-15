@echo off
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
set "localcast_exit=%errorlevel%"
pause
exit /b %localcast_exit%

