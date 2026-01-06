@echo off
REM Batch script to start GCS with PyMAVLink on Windows
echo ================================
echo Starting Ground Control Station
echo ================================
echo.

REM Check if Python is installed
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if Node.js is installed
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed or not in PATH
    pause
    exit /b 1
)

REM Check/create virtual environment
if not exist "myvenv" (
    echo [INFO] Creating virtual environment...
    python -m venv myvenv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Upgrade pip
echo [INFO] Upgrading pip...
myvenv\Scripts\python.exe -m pip install --upgrade pip --quiet

REM Install Python dependencies
echo [INFO] Installing Python dependencies...
myvenv\Scripts\python.exe -m pip install -r external-services\requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Python dependencies
    echo.
    echo Try running manually:
    echo    myvenv\Scripts\python.exe -m pip install -r external-services\requirements.txt
    pause
    exit /b 1
)

REM Verify shapely
echo [INFO] Verifying shapely installation...
myvenv\Scripts\python.exe -c "import shapely; print('Shapely version:', shapely.__version__)" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Shapely not found, installing separately...
    myvenv\Scripts\python.exe -m pip install shapely --force-reinstall
)

echo [OK] Python dependencies installed
echo.

REM Install Node.js dependencies
if not exist "node_modules" (
    echo [INFO] Installing Node.js dependencies...
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install Node.js dependencies
        pause
        exit /b 1
    )
)

REM Check for axios
npm list axios >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] Installing axios...
    call npm install axios
)

echo [OK] Node.js dependencies installed
echo.

REM Start PyMAVLink service
echo [INFO] Starting PyMAVLink service...
start "PyMAVLink Service" myvenv\Scripts\python.exe external-services\pymavlink_service.py

REM Wait for service to start
timeout /t 3 /nobreak >nul

REM Start Node.js server
echo [INFO] Starting GCS server...
start "GCS Server" node server.js

echo.
echo ================================
echo All services started!
echo ================================
echo.
echo Mission Control: http://localhost:3000/mission-control
echo Landing Page:    http://localhost:3000
echo PyMAVLink API:   http://localhost:5000
echo.
echo Press Ctrl+C in service windows to stop
echo.

REM Keep this window open
echo This window can be closed to keep services running
pause
