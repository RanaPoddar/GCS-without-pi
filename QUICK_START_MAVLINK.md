# 🚀 QUICK START: Long-Range Detection Control

## FOR LONG-RANGE OPERATIONS (No WiFi Needed)

### 1️⃣ Start Pi (on Raspberry Pi)
```bash
cd /home/pi/rpi-connect
source venv/bin/activate
python3 pi_controller.py
```

Expected: `✅ MAVLink command handler registered (42000/42001)`

---

### 2️⃣ Send Commands (from GCS Computer)

**Option A: Interactive Menu (Easiest)**
```bash
cd GCS-without-pi
python send-mavlink-command.py COM5
```
Then press `1` to start detection, `2` to stop.

**Option B: One-Line Commands**
```python
# Start detection
python -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('COM5',baud=57600); m.wait_heartbeat(); m.mav.command_long_send(1,1,42000,0,0,0,0,0,0,0,0); print('Sent!')"

# Stop detection  
python -c "from pymavlink import mavutil; m=mavutil.mavlink_connection('COM5',baud=57600); m.wait_heartbeat(); m.mav.command_long_send(1,1,42001,0,0,0,0,0,0,0,0); print('Sent!')"
```

**Option C: Mission Planner**
1. Connect to drone
2. Flight Data → Actions → Scripts
3. Enter: `COMMAND_LONG 1 1 42000 0 0 0 0 0 0 0 0`

---

### 3️⃣ Verify Detection Working

**On Pi terminal:**
```
📡 MAVLink Command: START DETECTION (42000)
🌾 Detection started via MAVLink
```

**On GCS:**
```
📥 Command 42000: ✅ ACCEPTED
```

---

## Command Reference Card

| Action | Command ID | Button in Menu |
|--------|-----------|----------------|
| Start Detection | 42000 | 1 |
| Stop Detection | 42001 | 2 |
| Get Stats | 42002 | 3 |
| Start Capture | 42003 | 4 |
| Stop Capture | 42004 | 5 |

---

## Troubleshooting

### "No heartbeat" error
- Check COM port (might be COM3, COM4, COM5, etc.)
- Run: `python send-mavlink-command.py COM3` (try different ports)
- Verify radio is connected (Device Manager → Ports)

### "Command not accepted"
- Ensure Pi is running `pi_controller.py`
- Check Pi config: `mavlink_detection.enabled = true`
- Verify Pixhawk connected to Pi

### Change COM port
```bash
# Windows
python send-mavlink-command.py COM3

# Linux  
python send-mavlink-command.py /dev/ttyUSB0
```

---

## Range Capability

| Distance | WiFi | Radio (MAVLink) |
|----------|------|-----------------|
| 0-100m | ✅ | ✅ |
| 100m-2km | ❌ | ✅ |
| 2-10km | ❌ | ✅ |

**Bottom line:** Commands work up to 10km with good telemetry radios, no WiFi needed!
