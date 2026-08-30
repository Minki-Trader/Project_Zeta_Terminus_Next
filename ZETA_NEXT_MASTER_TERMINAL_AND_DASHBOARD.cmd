@echo off
setlocal
title Project Zeta Terminus Next V8 Live-Dev Launcher
cd /d "%~dp0"

set "SYSTEM_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "PWSH_EXE="
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "PWSH_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined PWSH_EXE for /f "delims=" %%I in ('where pwsh.exe 2^>nul') do if not defined PWSH_EXE set "PWSH_EXE=%%~fI"
if not defined PWSH_EXE if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe" set "PWSH_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"

if not exist "%SYSTEM_POWERSHELL%" (
    echo Windows PowerShell was not found.
    echo.
    pause
    exit /b 1
)

if not defined PWSH_EXE (
    echo PowerShell 7 ^(pwsh.exe^) was not found.
    echo.
    pause
    exit /b 1
)

"%SYSTEM_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0live-dev\tools\Start-ZetaNextDetachedMaster.ps1" -WorkerPowerShellPath "%PWSH_EXE%"
if errorlevel 1 (
    echo.
    echo The detached Next V8 Live-Dev launcher stopped at a safety check. Review the error above.
    echo.
    pause
    exit /b 1
)

exit /b 0
