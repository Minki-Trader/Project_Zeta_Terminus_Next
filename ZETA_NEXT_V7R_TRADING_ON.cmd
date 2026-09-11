@echo off
rem Retired legacy entrypoint. The desktop replacement always starts non-trading.
call "%~dp0..\Zeta_Master_Terminal\START_V7.cmd"
exit /b %errorlevel%
