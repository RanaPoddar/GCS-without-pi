@echo off
REM Send MAVLink Commands to Pi via Telemetry Radio
REM This works over long-range radio (1-10km) without WiFi

echo ========================================
echo MAVLink Command Sender
echo ========================================
echo.

REM Check if COM port provided
if "%1"=="" (
    echo Usage: send-mavlink-command.bat COM5
    echo.
    echo Using default COM5...
    echo If your radio is on different port, specify it:
    echo   send-mavlink-command.bat COM3
    echo.
    python send-mavlink-command.py COM5
) else (
    python send-mavlink-command.py %1
)

pause
