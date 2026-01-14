# MAVLink Command Reference for Detection Control

## Overview
Control Pi detection system over long-range telemetry radio (1-10km range).
Works when drone is beyond WiFi range.

## Connection Setup
- **GCS Side**: Telemetry radio connected to USB (e.g., COM5)
- **Drone Side**: Radio → Pixhawk TELEM1 → Pi via TELEM2
- **Baud Rate**: 57600 (both radios must match)

## Command IDs

| Command | ID | Description | Parameters |
|---------|-----|-------------|------------|
| **Start Detection** | 42000 | Start yellow crop detection | None |
| **Stop Detection** | 42001 | Stop detection | None |
| **Request Stats** | 42002 | Get detection statistics | None |
| **Start Capture** | 42003 | Start periodic image capture | param1: interval (seconds) |
| **Stop Capture** | 42004 | Stop periodic capture | None |

## Usage Methods

### Method 1: Python Script (Easiest)
```bash
# From GCS-without-pi folder
python send-mavlink-command.py COM5

# Or use batch file
send-mavlink-command.bat COM5
```

Interactive menu will appear with numbered options.

### Method 2: Mission Planner Scripts
1. Connect to drone via telemetry
2. Go to **Flight Data** → **Actions** → **Scripts**
3. Enter command:
```
COMMAND_LONG 1 1 42000 0 0 0 0 0 0 0 0
```

Replace `42000` with desired command ID.

### Method 3: MAVProxy Console
```bash
# Start detection
command long 1 1 42000 0 0 0 0 0 0 0 0

# Stop detection
command long 1 1 42001 0 0 0 0 0 0 0 0

# Start capture every 5 seconds
command long 1 1 42003 0 5 0 0 0 0 0 0
```

### Method 4: Direct PyMAVLink Code
```python
from pymavlink import mavutil

# Connect
master = mavutil.mavlink_connection('COM5', baud=57600)
master.wait_heartbeat()

# Send command
master.mav.command_long_send(
    1,      # target_system
    1,      # target_component
    42000,  # command (start detection)
    0,      # confirmation
    0, 0, 0, 0, 0, 0, 0  # params
)

# Wait for ACK
ack = master.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
if ack and ack.result == 0:
    print("✅ Command accepted!")
```

## Troubleshooting

### No Acknowledgment
- Check radio connection (both ends)
- Verify COM port in Device Manager
- Ensure radios are paired (same net ID)
- Check baud rate matches (57600)

### Command Not Working
1. Verify Pi is running: `python3 pi_controller.py`
2. Check Pi logs for "📡 MAVLink Command: START DETECTION"
3. Ensure Pixhawk is connected to Pi (TELEM2)
4. Test telemetry flow first (check you're receiving GPS data)

### Radio Not Connected
```powershell
# Check available COM ports
[System.IO.Ports.SerialPort]::getportnames()

# Test connection
python -c "from pymavlink import mavutil; m = mavutil.mavlink_connection('COM5', baud=57600); m.wait_heartbeat(timeout=10); print('Connected!')"
```

## Expected Behavior

### Start Detection (42000)
**Pi Output:**
```
📡 MAVLink Command: START DETECTION (42000)
🌾 Detection started via MAVLink
✅ Sent COMMAND_ACK for 42000
```

**GCS Output:**
```
📡 Sending command 42000...
⏳ Waiting for acknowledgment...
📥 Command 42000: ✅ ACCEPTED
```

### Stop Detection (42001)
**Pi Output:**
```
📡 MAVLink Command: STOP DETECTION (42001)
🛑 Detection stopped via MAVLink
✅ Sent COMMAND_ACK for 42001
```

## Testing Without Drone
You can test on the same computer:
1. Install virtual serial port (com0com or similar)
2. Create pair: COM10 ↔ COM11
3. Run Pi simulator on COM10
4. Run command sender on COM11

## Integration with Dashboard

The [pymavlink_service.py](external-services/pymavlink_service.py) automatically forwards these commands to the Node.js server, so detection status appears in the GCS dashboard even when using radio commands.

## Long-Range Operation Profile

| Range | WiFi (Socket.IO) | Radio (MAVLink) |
|-------|-----------------|-----------------|
| 0-100m | ✅ Primary | ✅ Backup |
| 100m-2km | ❌ Disconnected | ✅ Primary |
| 2km-10km | ❌ Not available | ✅ Works |
| 10km+ | ❌ Not available | ⚠️ Weak signal |

**Key Point**: Detection continues working beyond WiFi range using MAVLink radio. Commands and detection data both flow through the telemetry radio link.
