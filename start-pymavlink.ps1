# PowerShell script to start GCS with PyMAVLink on Windows
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

Write-Host " Starting Ground Control Station with PyMAVLink..." -ForegroundColor Green

# Check if Python is installed
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host " Python is not installed" -ForegroundColor Red
    exit 1
}

# Check if Node.js is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host " Node.js is not installed" -ForegroundColor Red
    exit 1
}

# Check/create virtual environment
if (-not (Test-Path "myvenv")) {
    Write-Host " Creating virtual environment..." -ForegroundColor Yellow
    python -m venv myvenv
    if ($LASTEXITCODE -ne 0) {
        Write-Host " Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Install Python dependencies
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
& ".\myvenv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\myvenv\Scripts\python.exe" -m pip install -r external-services\requirements.txt --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host " Failed to install Python dependencies" -ForegroundColor Red
    Write-Host "Try running manually:" -ForegroundColor Yellow
    Write-Host "   .\myvenv\Scripts\python.exe -m pip install -r external-services\requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Verify shapely installation (critical for KML processing)
Write-Host " Verifying shapely installation..." -ForegroundColor Yellow
& ".\myvenv\Scripts\python.exe" -c "import shapely; print(f' Shapely version: {shapely.__version__}')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host " Shapely not installed correctly!" -ForegroundColor Red
    Write-Host "Installing shapely separately..." -ForegroundColor Yellow
    & ".\myvenv\Scripts\python.exe" -m pip install shapely --force-reinstall
}

Write-Host " Python dependencies OK" -ForegroundColor Green

# Install Node.js dependencies
if (-not (Test-Path "node_modules")) {
    Write-Host " Installing Node.js dependencies..." -ForegroundColor Yellow
    npm install
}

# Add axios if not already installed
npm list axios 2>$null
if ($LASTEXITCODE -ne 0) {
    npm install axios
}

# Start PyMAVLink service in background
Write-Host " Starting PyMAVLink service..." -ForegroundColor Cyan
$pymavlinkJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & ".\myvenv\Scripts\python.exe" "external-services\pymavlink_service.py"
}
Write-Host "PyMAVLink service started with Job ID: $($pymavlinkJob.Id)" -ForegroundColor Green

# Wait for PyMAVLink service to be ready
Write-Host " Waiting for PyMAVLink service to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start Node.js server in background
Write-Host " Starting Node.js Ground Control Station..." -ForegroundColor Cyan
$serverJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    node server.js
}
Write-Host "GCS server started with Job ID: $($serverJob.Id)" -ForegroundColor Green

Write-Host ""
Write-Host " All services started!" -ForegroundColor Green
Write-Host " Mission Control: http://localhost:3000/mission-control" -ForegroundColor Cyan
Write-Host " Landing Page: http://localhost:3000" -ForegroundColor Cyan
Write-Host " PyMAVLink API: http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

# Function to cleanup jobs
function Cleanup {
    Write-Host ""
    Write-Host " Shutting down services..." -ForegroundColor Yellow
    Stop-Job $pymavlinkJob -ErrorAction SilentlyContinue
    Stop-Job $serverJob -ErrorAction SilentlyContinue
    Remove-Job $pymavlinkJob -ErrorAction SilentlyContinue
    Remove-Job $serverJob -ErrorAction SilentlyContinue
    Write-Host " Services stopped" -ForegroundColor Green
    exit 0
}

# Register cleanup for Ctrl+C
try {
    # Monitor jobs and show output
    while ($true) {
        # Check if jobs are still running
        $pymavlinkState = (Get-Job -Id $pymavlinkJob.Id).State
        $serverState = (Get-Job -Id $serverJob.Id).State
        
        if ($pymavlinkState -eq 'Failed' -or $serverState -eq 'Failed') {
            Write-Host " One or more services failed" -ForegroundColor Red
            
            if ($pymavlinkState -eq 'Failed') {
                Write-Host "PyMAVLink errors:" -ForegroundColor Red
                Receive-Job $pymavlinkJob
            }
            
            if ($serverState -eq 'Failed') {
                Write-Host "Server errors:" -ForegroundColor Red
                Receive-Job $serverJob
            }
            
            Cleanup
        }
        
        # Receive and display any output from jobs
        Receive-Job $pymavlinkJob -ErrorAction SilentlyContinue
        Receive-Job $serverJob -ErrorAction SilentlyContinue
        
        Start-Sleep -Seconds 1
    }
}
finally {
    Cleanup
}