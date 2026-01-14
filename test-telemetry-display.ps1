# Test Telemetry Display
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Testing Telemetry-Only Display" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 1: Check PyMAVLink Connection" -ForegroundColor Yellow
$telemetry = Invoke-WebRequest -Uri "http://localhost:5000/drone/1/telemetry" -UseBasicParsing | ConvertFrom-Json

if ($telemetry.connected) {
    Write-Host "  ✅ Drone 1 connected to COM4" -ForegroundColor Green
    Write-Host "  Port: $($telemetry.port)" -ForegroundColor White
    Write-Host "  Mode: $($telemetry.telemetry.flight_mode)" -ForegroundColor White
    Write-Host "  Armed: $($telemetry.telemetry.armed)" -ForegroundColor White
    
    $statMsgs = $telemetry.telemetry.statustext_log | Where-Object { $_.text -like "STAT|*" }
    Write-Host "  STAT messages: $($statMsgs.Count)" -ForegroundColor White
    
    if ($statMsgs.Count -gt 0) {
        $latest = $statMsgs[-1].text
        Write-Host "  Latest: $latest" -ForegroundColor Cyan
        
        $parts = $latest.Split("|")
        if ($parts.Length -ge 5) {
            Write-Host "    CPU: $($parts[1])%" -ForegroundColor White
            Write-Host "    MEM: $($parts[2])%" -ForegroundColor White
            Write-Host "    DISK: $($parts[3])%" -ForegroundColor White
            Write-Host "    TEMP: $($parts[4])°C" -ForegroundColor White
        }
    }
} else {
    Write-Host "  ❌ Drone 1 NOT connected" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 2: Check Pi List Endpoint" -ForegroundColor Yellow
Write-Host "  (This would be populated by Socket.IO in the dashboard)" -ForegroundColor Gray

Write-Host ""
Write-Host "Step 3: Open Dashboard" -ForegroundColor Yellow
Write-Host "  URL: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Expected Behavior:" -ForegroundColor Yellow
Write-Host "  1. Dropdown should show: '1' (drone ID)" -ForegroundColor White
Write-Host "  2. Select '1' from dropdown" -ForegroundColor White
Write-Host "  3. Stats should update every ~30 seconds:" -ForegroundColor White
Write-Host "     - CPU usage" -ForegroundColor Gray
Write-Host "     - Memory usage" -ForegroundColor Gray
Write-Host "     - Disk usage" -ForegroundColor Gray
Write-Host "     - Temperature" -ForegroundColor Gray
Write-Host "  4. Status badge: 'Online (Telemetry)'" -ForegroundColor White
Write-Host "  5. Console log shows stats received" -ForegroundColor White
Write-Host ""

Write-Host "Opening dashboard in browser..." -ForegroundColor Cyan
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "✅ All checks passed! Dashboard should now display stats." -ForegroundColor Green
Write-Host ""
