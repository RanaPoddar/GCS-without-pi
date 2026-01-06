# PowerShell script to check GCS setup on Windows

Write-Host "🔍 Checking GCS Setup..." -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Check Python installation
Write-Host "1. Checking Python..." -ForegroundColor Yellow
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version
    Write-Host "   ✅ Python found: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "   ❌ Python not found!" -ForegroundColor Red
    Write-Host "   Please install Python 3.8+ from python.org" -ForegroundColor Red
    $allGood = $false
}

# Check Node.js installation
Write-Host "2. Checking Node.js..." -ForegroundColor Yellow
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVersion = node --version
    Write-Host "   ✅ Node.js found: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "   ❌ Node.js not found!" -ForegroundColor Red
    Write-Host "   Please install Node.js from nodejs.org" -ForegroundColor Red
    $allGood = $false
}

# Check virtual environment
Write-Host "3. Checking Python virtual environment..." -ForegroundColor Yellow
if (Test-Path "myvenv\Scripts\python.exe") {
    Write-Host "   ✅ Virtual environment found" -ForegroundColor Green
    
    # Check if packages are installed
    Write-Host "4. Checking Python packages..." -ForegroundColor Yellow
    $pipList = & ".\myvenv\Scripts\python.exe" -m pip list 2>&1
    
    $packages = @("pymavlink", "Flask", "flask-cors", "pyserial", "shapely")
    foreach ($package in $packages) {
        if ($pipList -match $package) {
            Write-Host "   ✅ $package installed" -ForegroundColor Green
        } else {
            Write-Host "   ❌ $package not installed" -ForegroundColor Red
            $allGood = $false
        }
    }
} else {
    Write-Host "   ❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "   Run: python -m venv myvenv" -ForegroundColor Yellow
    $allGood = $false
}

# Check Node modules
Write-Host "5. Checking Node.js packages..." -ForegroundColor Yellow
if (Test-Path "node_modules") {
    Write-Host "   ✅ node_modules found" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  node_modules not found" -ForegroundColor Yellow
    Write-Host "   Run: npm install" -ForegroundColor Yellow
    $allGood = $false
}

# Check required directories
Write-Host "6. Checking required directories..." -ForegroundColor Yellow
$dirs = @("data/kml_uploads", "data/missions")
foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "   ✅ $dir exists" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  $dir missing (will be created automatically)" -ForegroundColor Yellow
    }
}

Write-Host ""
if ($allGood) {
    Write-Host "🎉 All checks passed! You're ready to go." -ForegroundColor Green
    Write-Host ""
    Write-Host "To start the system, run:" -ForegroundColor Cyan
    Write-Host "   .\start-pymavlink.ps1" -ForegroundColor White
} else {
    Write-Host "⚠️  Some issues found. Please fix them before starting." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Quick fix commands:" -ForegroundColor Cyan
    Write-Host "   1. Create venv:           python -m venv myvenv" -ForegroundColor White
    Write-Host "   2. Install Python deps:   .\myvenv\Scripts\python.exe -m pip install -r external-services\requirements.txt" -ForegroundColor White
    Write-Host "   3. Install Node deps:     npm install" -ForegroundColor White
}

Write-Host ""
Read-Host "Press Enter to exit"
