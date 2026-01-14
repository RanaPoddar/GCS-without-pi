@echo off
REM Send Detection Commands via HTTP (works while pymavlink_service is running)
cd /d "%~dp0"
myvenv\Scripts\python.exe send-detection-command-http.py %*
pause
