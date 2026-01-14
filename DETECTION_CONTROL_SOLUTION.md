# ✅ SOLUTION: Control Detection via MAVLink (Long-Range)

## The Problem
- Your Pi is in **telemetry-only mode** (`socketio_enabled: false`)
- Socket.IO dashboard buttons don't work (by design - for long-range ops)
- The `pymavlink_service.py` is already using COM4

## The Solution: Use HTTP API

The pymavlink_service already has the COM4 connection and can send MAVLink commands for you!

### Quick Start:

```bash
# Make sure pymavlink_service is running (it already is)
cd GCS-without-pi
myvenv\Scripts\python send-detection-command-http.py 1

# Or use the batch file
send-detection-cmd.bat 1
```

Then press:
- `1` = Start detection (sends MAVLink command 42000)
- `2` = Stop detection (sends MAVLink command 42001)

---

## How It Works

```
Your Script → HTTP → pymavlink_service (has COM4) → MAVLink → Radio → Pi
```

Instead of opening COM4 again (which fails because service has it), we tell the service to send the command.

---

## Files You Can Use

| File | Purpose | When to Use |
|------|---------|-------------|
| `send-detection-command-http.py` | HTTP API (easiest) | ✅ pymavlink_service running |
| `send-detection-cmd.bat` | Batch wrapper | ✅ pymavlink_service running |
| `send-mavlink-cmd.py` | Direct COM port | ❌ Fails if service running |
| `test-command-send.py` | Direct COM port test | ❌ Fails if service running |

---

## If You Want Direct COM Port Access

**Stop the pymavlink_service first:**
```powershell
# Find and stop it
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Where-Object {(Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*pymavlink_service*"} | Stop-Process

# Then use direct command
python send-mavlink-cmd.py COM4
```

**Restart service after:**
```powershell
cd external-services
python pymavlink_service.py
```

---

## Recommended Setup for Your Use Case

Since you need long-range (2-10km), keep this configuration:

**Pi Side** (`rpi-connect/config.json`):
```json
{
  "socketio": {"enabled": false},  ← No WiFi dependency
  "mavlink_detection": {"enabled": true}  ← Radio transmission
}
```

**GCS Side**:
1. Keep `pymavlink_service.py` running (it manages COM4)
2. Use HTTP API to send commands: `send-detection-command-http.py`
3. Detections come back via radio → service → Node.js → Dashboard

---

## Testing Right Now

```powershell
# 1. Check service is running
Get-Process | Where-Object {$_.CommandLine -like "*pymavlink_service*"}

# 2. Send command via HTTP
cd C:\Users\ranab\Desktop\GCS-without-pi
myvenv\Scripts\python send-detection-command-http.py 1

# 3. Press 1 to start detection
```

---

## Why This Is Better

✅ **No COM port conflicts** - Service manages it  
✅ **Works with running service** - No need to stop/restart  
✅ **Same MAVLink commands** - 42000/42001 still sent  
✅ **Long range** - Up to 2-10km via radio  
✅ **Integrated** - Service already forwards detections to dashboard

The direct COM port script (`send-mavlink-cmd.py`) would work if you stop the service first, but using the HTTP API is cleaner since the service is designed to run continuously.
