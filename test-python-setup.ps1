# PowerShell script to test Python setup for GCS
Write-Host "=== Testing Python Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "myvenv")) {
    Write-Host "❌ Virtual environment 'myvenv' not found!" -ForegroundColor Red
    Write-Host "   Run: python -m venv myvenv" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Virtual environment found" -ForegroundColor Green

# Get Python path
$pythonPath = ".\myvenv\Scripts\python.exe"
if (-not (Test-Path $pythonPath)) {
    Write-Host "❌ Python executable not found at: $pythonPath" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python executable found: $pythonPath" -ForegroundColor Green

# Check Python version
Write-Host ""
Write-Host "Python version:" -ForegroundColor Cyan
& $pythonPath --version

# Test importing required libraries
Write-Host ""
Write-Host "Testing Python libraries..." -ForegroundColor Cyan
$testScript = @"
import sys
import os

print('Python executable:', sys.executable)
print('Python version:', sys.version)
print('')

# Test imports
libraries = [
    ('pymavlink', 'pymavlink'),
    ('flask', 'Flask'),
    ('flask_cors', 'flask-cors'),
    ('serial', 'pyserial'),
    ('shapely', 'shapely'),
    ('shapely.geometry', 'shapely (geometry module)')
]

print('Library Status:')
print('-' * 60)
all_ok = True
for module, name in libraries:
    try:
        __import__(module)
        print(f'✅ {name:30s} - OK')
    except ImportError as e:
        print(f'❌ {name:30s} - MISSING')
        print(f'   Error: {e}')
        all_ok = False

print('-' * 60)
if all_ok:
    print('\\n✅ All required libraries are installed!')
    sys.exit(0)
else:
    print('\\n❌ Some libraries are missing!')
    print('\\nTo install missing libraries, run:')
    print('   .\\myvenv\\Scripts\\python.exe -m pip install -r external-services\\requirements.txt')
    sys.exit(1)
"@

# Save test script to temp file
$tempScript = "temp_test.py"
$testScript | Out-File -FilePath $tempScript -Encoding UTF8

# Run test
& $pythonPath $tempScript
$exitCode = $LASTEXITCODE

# Cleanup
Remove-Item $tempScript -ErrorAction SilentlyContinue

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "=== All tests passed! ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now start the GCS with: .\start-pymavlink.ps1" -ForegroundColor Cyan
} else {
    Write-Host "=== Tests failed! ===" -ForegroundColor Red
    Write-Host ""
    Write-Host "To fix, run:" -ForegroundColor Yellow
    Write-Host "   .\myvenv\Scripts\python.exe -m pip install -r external-services\requirements.txt" -ForegroundColor Yellow
}

exit $exitCode
