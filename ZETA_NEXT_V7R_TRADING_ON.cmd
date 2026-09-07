@echo off
setlocal
title Zeta Next V7R - User Trading Activation
cd /d "%~dp0"

set "ZETA_PWSH="
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "ZETA_PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined ZETA_PWSH for /f "delims=" %%I in ('where pwsh.exe 2^>nul') do if not defined ZETA_PWSH set "ZETA_PWSH=%%~fI"
if not defined ZETA_PWSH if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe" set "ZETA_PWSH=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
if not defined ZETA_PWSH (
    echo PowerShell 7 was not found. Trading was not started.
    pause
    exit /b 1
)

"%ZETA_PWSH%" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0live-dev\tools\Open-ZetaNextV7RTradingOn.ps1"
if errorlevel 1 (
    echo.
    echo Activation did not complete. Read the message above; do not force-close MT5.
    pause
    exit /b 1
)
exit /b 0
