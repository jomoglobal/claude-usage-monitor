@echo off
REM Claude Usage Monitor — startup launcher
REM
REM Drop this file (or a shortcut to it) into:
REM   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
REM
REM Edit the path below to match where you cloned this repo on Windows.

set MONITOR_PATH=%USERPROFILE%\claude-usage-monitor\monitor.py

start /min "" pythonw "%MONITOR_PATH%"
