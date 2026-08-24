@echo off
setlocal
title Project Zeta Terminus Next V7 Live-Dev Launcher
cd /d "%~dp0"

set "PWSH_EXE="
for /f "delims=" %%I in ('where pwsh.exe 2^>nul') do if not defined PWSH_EXE set "PWSH_EXE=%%~fI"
if not defined PWSH_EXE if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "PWSH_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined PWSH_EXE if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe" set "PWSH_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"

if not defined PWSH_EXE (
    echo PowerShell 7 ^(pwsh.exe^) was not found.
    echo.
    pause
    exit /b 1
)

"%PWSH_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0live-dev\tools\Open-ZetaNextMasterTerminalAndDashboard.ps1"
if errorlevel 1 (
    echo.
    echo The Next V7 Live-Dev launcher stopped at a safety check. Review the error above.
    echo.
    pause
    exit /b 1
)

exit /b 0
