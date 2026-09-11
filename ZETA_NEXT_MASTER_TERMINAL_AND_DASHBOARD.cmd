@echo off
rem Retired legacy entrypoint. The desktop replacement always starts non-trading.
call "%~dp0..\Zeta_Master_Terminal\START_NEW.cmd"
exit /b %errorlevel%
