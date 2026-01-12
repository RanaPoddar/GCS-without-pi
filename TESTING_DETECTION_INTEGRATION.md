# Testing MAVLink Detection Integration

## Quick Test Procedure

### Prerequisites
✅ Raspberry Pi running with pi_controller.py  
✅ Pi connected to Pixhawk TELEM2 (921600 baud)  
✅ Pixhawk connected to GCS computer via USB/radio  
✅ PyMAVLink service installed (external-services/)  
✅ Node.js GCS installed (npm install completed)  

---

## Test 1: Check PyMAVLink Service Connection

### Step 1: Start PyMAVLink Service
```powershell
cd C:\Users\ranab\Desktop\GCS-without-pi\external-services
python pymavlink_service.py
```

**Expected Output:**
```
INFO - PyMAVLink service starting...
INFO - Listening on http://localhost:5000
INFO - Waiting for Flask to start...
 * Running on http://127.0.0.1:5000
```

### Step 2: Verify API is Responding
Open new PowerShell window:
```powershell
curl http://localhost:5000/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "service": "pymavlink",
  "version": "1.0.0"
}
```

✅ **PyMAVLink service is ready**

---

## Test 2: Connect to Pixhawk

### Step 1: Find Pixhawk COM Port
```powershell
# List serial ports
Get-PnpDevice | Where-Object {$_.Class -eq "Ports" -and $_.Status -eq "OK"}
```

Look for something like:
```
USB Serial Device (COM5)
```

### Step 2: Set Environment Variable
```powershell
$env:DRONE1_PORT="COM5"  # Replace with your port
```

### Step 3: Start GCS Server
```powershell
cd C:\Users\ranab\Desktop\GCS-without-pi
npm start
```

**Expected Output:**
```
🚀 Ground Control Station running on http://localhost:3000
📊 Mission Control Dashboard: http://localhost:3000/mission-control
🚁 Initializing Pixhawk connections...
✅ PyMAVLink service is running
Connecting to Drone 1...
Waiting for heartbeat from Drone 1...
✅ Drone 1 connected! System 1, Component 1
✅ Drone 1 initialized on COM5
Telemetry polling started for Drone 1
🚁 Pixhawk initialization complete: 1/1 drones connected
```

✅ **GCS connected to Pixhawk**

---

## Test 3: Verify Telemetry Flow

### Step 1: Check Telemetry API
```powershell
curl http://localhost:5000/drone/1/telemetry
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "drone_id": 1,
    "timestamp": 1710512345.67,
    "telemetry": {
      "latitude": 12.971234,
      "longitude": 77.594567,
      "altitude": 525.3,
      "relative_altitude": 0.0,
      "heading": 90,
      "groundspeed": 0.0,
      "battery_voltage": 16.4,
      "battery_remaining": 95,
      "satellites_visible": 12,
      "gps_fix_type": 3,
      "flight_mode": "STABILIZE",
      "armed": false,
      "statustext_log": []
    }
  }
}
```

✅ **Telemetry data flowing from Pixhawk**

### Step 2: Open Dashboard
Open browser: http://localhost:3000/mission-control

**Expected:**
- Map shows drone position
- Telemetry panel shows altitude, battery, GPS
- "CONNECTED" indicator green

✅ **Dashboard receiving telemetry**

---

## Test 4: Raspberry Pi Detection Transmission

### Step 1: SSH to Raspberry Pi
```bash
ssh pi@raspberrypi.local
# Or use IP: ssh pi@192.168.1.xxx
```

### Step 2: Check Pi Configuration
```bash
cd ~/rpi-connect
cat config.json | grep -A 5 "mavlink_detection"
```

**Expected:**
```json
"mavlink_detection": {
  "enabled": true,
  "port": "/dev/serial0",
  "baudrate": 921600,
  "system_id": 2,
  "component_id": 191
}
```

**Also check read_only:**
```bash
cat config.json | grep "read_only"
```
**Must show:** `"read_only": false`

### Step 3: Start Pi Controller
```bash
cd ~/rpi-connect
python3 pi_controller.py
```

**Expected Output:**
```
📡 MAVLink Detection Sender initialized
   Port: /dev/serial0
   Baud: 921600
   System: 2, Component: 191
   Status: ✅ CONNECTED
🎥 Camera initialized: IMX477 (4056x3040)
🌾 Yellow Crop Detector initialized
   HSV Range: [20, 80, 60] to [32, 255, 255]
   Min Area: 150 px
   Confidence: 0.50
✈️  Connected to Pixhawk on /dev/ttyAMA0
   System 1, Component 1
   ✅ Heartbeat OK
🟢 Starting autonomous detection in AUTO mode
```

✅ **Pi controller running and connected**

---

## Test 5: Manual Detection Test

### Option A: Trigger Detection Manually (No Flight Required)

#### Step 1: Create Test Script on Pi
```bash
cd ~/rpi-connect
nano test_manual_detection.py
```

Paste this code:
```python
#!/usr/bin/env python3
import time
import sys
sys.path.append('/home/pi/rpi-connect')
from modules.mavlink_detection_sender import MAVLinkDetectionSender

# Initialize MAVLink sender
sender = MAVLinkDetectionSender(
    port='/dev/serial0',
    baudrate=921600,
    system_id=2,
    component_id=191
)

time.sleep(2)  # Wait for connection

# Send test detection
detection_id = f"TEST_{int(time.time())}"
lat = 12.971234
lon = 77.594567
conf = 0.85
area = 1732

print(f"📡 Sending test detection: {detection_id}")
sender.send_detection(detection_id, lat, lon, conf, area)
print("✅ Detection sent via MAVLink")
print(f"   ID: {detection_id}")
print(f"   GPS: ({lat}, {lon})")
print(f"   Confidence: {conf}, Area: {area} px")

time.sleep(2)
sender.close()
```

Save and exit (Ctrl+X, Y, Enter)

#### Step 2: Run Test Script
```bash
chmod +x test_manual_detection.py
python3 test_manual_detection.py
```

**Expected Output:**
```
📡 Sending test detection: TEST_1710512345
✅ Detection sent via MAVLink
   ID: TEST_1710512345
   GPS: (12.971234, 77.594567)
   Confidence: 0.85, Area: 1732 px
```

#### Step 3: Check GCS Logs
Look at Node.js GCS terminal. Within 1-2 seconds you should see:
```
🌾 Detection via MAVLink from Drone 1: TEST_1710512345 at (12.971234, 77.594567)
   ✅ Detection broadcasted to all clients
```

#### Step 4: Check Dashboard
In browser (http://localhost:3000/mission-control):
- Yellow marker appears at GPS coordinates
- Detection list shows new entry:
  - ID: TEST_1710512345
  - Confidence: 85%
  - Area: 1732 px
  - Source: mavlink

✅ **End-to-end detection pipeline working!**

---

## Test 6: Live Detection During Flight

### Prerequisites
⚠️ **Safety First:**
- Clear area, no obstacles
- GPS lock (10+ satellites)
- Battery >50%
- Emergency stop ready

### Step 1: Place Yellow Target
- Use yellow paper (A4 size, 210mm x 297mm)
- Place on ground in mission area
- Note GPS coordinates if possible

### Step 2: Upload Mission
Use mission planner:
```bash
cd ~/GCS-without-pi
# Assuming you have a generated mission file
curl -X POST http://localhost:3000/api/mission/upload \
  -H "Content-Type: application/json" \
  -d @missions/mission.json
```

Or use Mission Control dashboard:
- Click "Upload Mission"
- Select mission file
- Wait for "Mission Uploaded Successfully"

### Step 3: Arm and Launch
1. Switch to GUIDED mode
2. Arm throttle
3. Command takeoff to 10m
4. Switch to AUTO mode

### Step 4: Monitor Detection in Real-Time

**Pi Terminal:**
```
🌾 Detection: det_1710512345
   GPS: (12.971234, 77.594567)
   Confidence: 0.85, Area: 1732 px
   📡 Sent via MAVLink
```

**GCS Terminal:**
```
🌾 Detection via MAVLink from Drone 1: det_1710512345 at (12.971234, 77.594567)
   ✅ Detection broadcasted to all clients
```

**Dashboard:**
- Yellow marker appears on map
- Detection counter increments
- List updates with new detection

✅ **Live detection working during flight!**

---

## Troubleshooting

### Problem: No detections appearing on GCS

#### Check 1: Is Pi sending?
```bash
# On Pi, check logs
tail -f ~/rpi-connect/logs/detection.log
```
Should see:
```
[INFO] Detection sent via MAVLink: DET|det_xxx|12.97|77.59|0.85|1732
```

If NOT sending:
- Verify `read_only: false` in config.json
- Verify `mavlink_detection.enabled: true`
- Check Pi serial connection: `ls -l /dev/serial0`

#### Check 2: Is Pixhawk receiving?
```bash
# On GCS, check PyMAVLink logs
# Should see STATUSTEXT messages from system 2 (Pi)
```

If NOT receiving:
- Verify Pi UART enabled: `dtoverlay=disable-bt` in /boot/config.txt
- Check baud rate matches: Pi=921600, Pixhawk TELEM2=921600
- Swap TX/RX if needed

#### Check 3: Is GCS processing?
Check Node.js GCS logs for:
```
🌾 Detection via MAVLink from Drone 1: ...
```

If NOT processing:
- Verify `statustext_log` in telemetry API response
- Check `processStatustextForDetections()` function
- Verify `startTelemetryPolling()` calls processing function

---

### Problem: Duplicate detections

**Symptoms:** Same detection appears multiple times

**Cause:** Detection ID repeated in multiple telemetry polls

**Fix:** Already implemented!
- `processedDetections` Set tracks processed IDs
- Duplicates automatically filtered
- Last 1000 IDs kept in memory

**Verify:**
```javascript
// In pixhawkServicePyMAVLink.js:
if (processedDetections.has(detectionId)) {
  continue;  // Skip duplicate
}
```

---

### Problem: Detections delayed

**Symptoms:** Detection appears 1-2 seconds after Pi sends

**Causes:**
1. Telemetry poll interval (250ms default)
2. STATUSTEXT buffer delay in Pixhawk
3. Radio link latency

**Solutions:**

#### Reduce Poll Interval
Edit `pixhawkServicePyMAVLink.js`:
```javascript
const TELEMETRY_POLL_INTERVAL = 100; // Faster: 10 Hz
```
Restart GCS server.

#### Check Radio Link Quality
```bash
# In dashboard, check RSSI
# Should be >50% for good link
```

#### Expected Latency
- Pi → Pixhawk: ~50ms (serial)
- Pixhawk → Radio: ~100ms (MAVLink)
- Radio → GCS: ~100ms (RF link)
- GCS Poll: 250ms (HTTP polling)
- **Total: ~500ms (acceptable)**

---

## Success Criteria

✅ **All Tests Passing:**
1. PyMAVLink service starts and responds to /health
2. GCS connects to Pixhawk via serial/USB
3. Telemetry data flows (GPS, battery, altitude)
4. Dashboard displays drone position on map
5. Manual test detection appears on GCS
6. Live flight detections transmitted and displayed
7. No duplicate detections in list
8. Latency <1 second from Pi to dashboard

✅ **Ready for Competition!**

---

## Performance Metrics

### Expected Values During Mission
- **Detection Rate:** 0-5 per second
- **Telemetry Poll:** 4 Hz (250ms)
- **End-to-End Latency:** 300-700ms
- **CPU Usage (Pi):** 40-60%
- **CPU Usage (GCS):** 5-15%
- **Memory (GCS):** ~200 MB
- **Network (MAVLink):** ~20 kbps
- **Detection Accuracy:** ±20-30 cm GPS error

### Limits
- **Max Detection Rate:** ~80/sec (STATUSTEXT buffer)
- **Detection ID Buffer:** 1000 recent IDs
- **STATUSTEXT Buffer:** 20 messages × 4 Hz = 5 sec history
- **Mission Duration:** Unlimited (continuous operation)

---

## Next Steps After Testing

1. **Field Test:** Fly actual mission over test area with yellow targets
2. **Calibrate GPS Accuracy:** Compare detected vs actual GPS coordinates
3. **Optimize HSV Range:** Fine-tune yellow detection for lighting conditions
4. **Backup Strategy:** Enable Pi local storage (Socket.IO + MAVLink redundancy)
5. **Competition Run:** Deploy system with confidence! 🚁🌾

**Questions? Check:**
- [MAVLINK_DETECTION_INTEGRATION.md](MAVLINK_DETECTION_INTEGRATION.md) - Full technical details
- [MAVLINK_DETECTION_TROUBLESHOOTING.md](MAVLINK_DETECTION_TROUBLESHOOTING.md) - Common issues
- [STARTUP_AND_DETECTION_GUIDE.md](STARTUP_AND_DETECTION_GUIDE.md) - Operating procedures

Good luck with your competition! 🎯
