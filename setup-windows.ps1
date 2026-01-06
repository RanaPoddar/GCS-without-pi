# PowerShell script to setup GCS on Windows

Write-Host "🚀 Setting up Ground Control Station..." -ForegroundColor Green
Write-Host ""

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python not found! Please install Python 3.8+ first." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Check Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Node.js not found! Please install Node.js first." -ForegroundColor Red
    Write-Host "Download from: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Create virtual environment
if (-not (Test-Path "myvenv\Scripts\python.exe")) {
    Write-Host "📦 Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv myvenv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✅ Virtual environment already exists" -ForegroundColor Green
}

# Upgrade pip
Write-Host "📦 Upgrading pip..." -ForegroundColor Yellow
& ".\myvenv\Scripts\python.exe" -m pip install --upgrade pip

# Install Python dependencies
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
& ".\myvenv\Scripts\python.exe" -m pip install -r external-services\requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install Python dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python dependencies installed" -ForegroundColor Green

# Install Node.js dependencies
Write-Host "📦 Installing Node.js dependencies..." -ForegroundColor Yellow
npm install

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install Node.js dependencies" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Node.js dependencies installed" -ForegroundColor Green

# Create required directories
Write-Host "📁 Creating required directories..." -ForegroundColor Yellow
$dirs = @("data\kml_uploads", "data\missions")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "   Created: $dir" -ForegroundColor Gray
    }
}
Write-Host "✅ Directories ready" -ForegroundColor Green

Write-Host ""
Write-Host "🎉 Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the system:" -ForegroundColor Cyan
Write-Host "   .\start-pymavlink.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To check setup:" -ForegroundColor Cyan
Write-Host "   .\check-setup.ps1" -ForegroundColor White
Write-Host ""
