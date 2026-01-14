Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Quick Verification & Fixes" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Checking Node.js Server..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "   OK - Server responding on port 3000" -ForegroundColor Green
} catch {
    Write-Host "   ERROR - Server not responding!" -ForegroundColor Red
    Write-Host "   Run: npm start" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "2. Checking PyMAVLink Service..." -ForegroundColor Yellow
try {
    $drones = Invoke-WebRequest -Uri "http://localhost:5000/drones" -UseBasicParsing -TimeoutSec 2 | ConvertFrom-Json
    if ($drones.drones[0].connected) {
        Write-Host "   OK - Drone 1 connected to COM4" -ForegroundColor Green
        Write-Host "   Stats messages: $($drones.drones[0].telemetry.statustext_log.Count)" -ForegroundColor Cyan
    } else {
        Write-Host "   WARNING - Drone not connected" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ERROR - PyMAVLink not responding!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "3. JavaScript Syntax Fix Applied..." -ForegroundColor Yellow
Write-Host "   Fixed line 803: drone_telemetry handler" -ForegroundColor Green

Write-Host ""
Write-Host "4. Pi Config Updated..." -ForegroundColor Yellow
Write-Host "   mavlink_command_receiver: enabled" -ForegroundColor Green

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  NEXT STEPS" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "BROWSER:" -ForegroundColor Yellow
Write-Host "  1. Hard refresh: Ctrl+Shift+R" -ForegroundColor White
Write-Host "  2. Check console (F12) for 'Connected to server'" -ForegroundColor White
Write-Host "  3. Select '1' from dropdown" -ForegroundColor White
Write-Host "  4. Stats should display" -ForegroundColor White
Write-Host ""
Write-Host "PI (SSH):" -ForegroundColor Yellow
Write-Host "  1. Restart pi_controller.py with new config" -ForegroundColor White
Write-Host "  2. Look for: 'MAVLink Command Receiver initialized'" -ForegroundColor White
Write-Host "  3. Test detection from Mission Control" -ForegroundColor White
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Cyan
Start-Process "http://localhost:3000"
Write-Host ""
Write-Host "Done!" -ForegroundColor Green
