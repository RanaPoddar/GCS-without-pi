# ✅ Long-Range Detection Control Setup Complete

## Your Pi Configuration (ALREADY CORRECT ✅)

From [rpi-connect/config.json](../rpi-connect/config.json):
```json
{
  "socketio_enabled": false,  ✅ WiFi disabled - telemetry only
  "pixhawk.enabled": true,    ✅ Pixhawk connected
  "mavlink_detection.enabled": true,  ✅ Radio transmission enabled
  "detection.enabled": true   ✅ Detection ready
}
```

**Your Pi is already configured for long-range operations! No changes needed.**

---

## How to Control Detection via MAVLink Radio

### On Raspberry Pi:
```bash
cd /home/pi/rpi-connect
source venv/bin/activate
python3 pi_controller.py
```

Wait for:
```
📡 MAVLink command handler registered (42000/42001)
✅ System ready!
```

### On GCS Computer:

**Method 1: Simple Interactive Script**
```bash
cd GCS-without-pi
python send-mavlink-cmd.py COM4
```
Then press:
- `1` = Start detection
- `2` = Stop detection  
- `0` = Exit

**Method 2: Test Script (More Detailed)**
```bash
python test-command-send.py
```

**Method 3: One-Line Command**
```bash
# Start
python -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('COM4',baud=57600); m.wait_heartbeat(); m.mav.command_long_send(m.target_system,m.target_component,42000,0,0,0,0,0,0,0,0); print('Started!')"

# Stop
python -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('COM4',baud=57600); m.wait_heartbeat(); m.mav.command_long_send(m.target_system,m.target_component,42001,0,0,0,0,0,0,0,0); print('Stopped!')"
```

---

## Command Reference

| Command | ID | Menu Option |
|---------|-----|-------------|
| Start Detection | 42000 | 1 |
| Stop Detection | 42001 | 2 |

---

## Expected Behavior

### When You Send "Start Detection"

**GCS Output:**
```
Connecting to COM4...
Connected!
1=Start Detection  2=Stop  0=Exit
Choice: 1
Starting detection...
OK
```

**Pi Output:**
```
📡 MAVLink Command: START DETECTION (42000)
🌾 Detection started via MAVLink
✅ Sent COMMAND_ACK for 42000
```

### Detections Flow Back via Radio

Detections are sent from Pi → Pixhawk → Radio → GCS:
```
🌾 Yellow crop detected @ lat=28.123, lon=77.456
📡 MAVLink: Detection sent via STATUSTEXT
```

GCS receives them in:
- [pymavlink_service.py](external-services/pymavlink_service.py) → Node.js server → Dashboard
- Mission Planner → Messages tab

---

## Troubleshooting

### "No heartbeat" Error

**Check COM port:**
```powershell
# List all serial ports
[System.IO.Ports.SerialPort]::getportnames()
```

Then try the correct port:
```bash
python send-mavlink-cmd.py COM5   # or COM3, COM6, etc.
```

### "Failed" or No Response

1. **Verify Pi is running:**
   ```bash
   # On Pi
   ps aux | grep pi_controller
   ```

2. **Check Pi logs:**
   ```bash
   tail -f ~/pi_controller.log | grep MAVLink
   ```

3. **Verify radio connection:**
   - GCS radio → USB → Computer
   - Drone radio → Pixhawk TELEM1 port
   - Both radios powered and green light on

4. **Test basic telemetry:**
   ```bash
   # Should see GPS data
   python -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('COM4',baud=57600); m.wait_heartbeat(); print(m.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5))"
   ```

---

## Range Performance

| Distance | Method | Status |
|----------|--------|--------|
| 0-100m | WiFi Socket.IO | ❌ Disabled (telemetry-only mode) |
| 0-100m | MAVLink Radio | ✅ Works perfectly |
| 100m-2km | MAVLink Radio | ✅ Works perfectly |
| 2-10km | MAVLink Radio | ✅ Works (may have delays) |
| 10km+ | MAVLink Radio | ⚠️ Depends on radio quality |

**With 915MHz/433MHz telemetry radios:** Commands and detections work reliably up to 2-5km, potentially 10km+ with high-power radios and good line-of-sight.

---

## Files Created

1. ✅ `send-mavlink-cmd.py` - Simple interactive menu
2. ✅ `test-command-send.py` - Detailed test script (already existed)
3. ✅ `send-mavlink-command.bat` - Windows batch launcher
4. ✅ `MAVLINK_COMMAND_GUIDE.md` - Complete documentation
5. ✅ `QUICK_START_MAVLINK.md` - Quick reference
6. ✅ `verify-mavlink-setup.py` - Setup verification tool
7. ✅ This file - Setup summary

---

## Quick Test Right Now

```bash
# 1. On Pi (if not already running)
cd /home/pi/rpi-connect && source venv/bin/activate && python3 pi_controller.py

# 2. On GCS
cd GCS-without-pi
python send-mavlink-cmd.py COM4

# 3. Press 1 to start detection
# 4. Fly the drone and watch for detections!
```

---

## Why This Setup is Better for Your Use Case

✅ **No WiFi dependency** - Works in remote fields  
✅ **Long range** - Up to 2-10km with telemetry radios  
✅ **Reliable** - Radio link designed for drones  
✅ **Bidirectional** - Send commands, receive detections  
✅ **Already configured** - Your Pi config is perfect  

The Socket.IO dashboard commands won't work because `socketio_enabled = false`, but that's intentional for long-range operations. MAVLink commands are the right solution for your agricultural spraying missions in remote areas.
