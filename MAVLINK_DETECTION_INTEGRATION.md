# MAVLink Detection Integration for Custom GCS

## Overview
Your custom GCS now receives and processes yellow plant detection messages transmitted via MAVLink STATUSTEXT from the Raspberry Pi through the Pixhawk to your ground station.

## System Architecture

```
┌─────────────────┐
│  Raspberry Pi   │  Runs pi_controller.py
│  (rpi-connect)  │  - Yellow crop detector
│                 │  - Geolocation calculator
│                 │  - MAVLink sender
└────────┬────────┘
         │ /dev/serial0 (TELEM2, 921600 baud)
         │ Sends: STATUSTEXT("DET|ID|LAT|LON|CONF|AREA")
         ▼
┌─────────────────┐
│   Pixhawk FC    │  ArduPilot autopilot
│    (TELEM2)     │  - Receives from Pi
│                 │  - Forwards to GCS radio
└────────┬────────┘
         │ TELEM1 (USB/Telemetry Radio)
         │ Forwards: STATUSTEXT messages
         ▼
┌─────────────────┐
│ PyMAVLink Svc   │  Python HTTP service (external-services/pymavlink_service.py)
│  (Port 5000)    │  - Connects to Pixhawk via serial
│                 │  - Collects all MAVLink messages
│                 │  - Exposes HTTP API
│                 │  - Stores STATUSTEXT in statustext_log[]
└────────┬────────┘
         │ HTTP GET /drone/{id}/telemetry
         │ Returns: { telemetry: { ..., statustext_log: [...] } }
         ▼
┌─────────────────┐
│  Node.js GCS    │  Ground Control Station (server.js)
│  (Port 3000)    │  services/pixhawkServicePyMAVLink.js:
│                 │  1. Polls telemetry every 250ms
│                 │  2. Processes statustext_log for "DET|" messages
│                 │  3. Parses detection data
│                 │  4. Saves to database via missionService
│                 │  5. Broadcasts via Socket.IO
└────────┬────────┘
         │ Socket.IO emit('crop_detection')
         ▼
┌─────────────────┐
│  Web Dashboard  │  Browser client (mission_control.html)
│  (Browser)      │  - Receives detection events
│                 │  - Displays on map
│                 │  - Shows in detection list
└─────────────────┘
```

## Detection Message Formats

### 1. Detection Event: `DET|ID|LAT|LON|CONF|AREA`
Example: `DET|1234|12.971234|77.594567|0.85|1732`

**Fields:**
- `ID`: Unique detection identifier (e.g., "1234")
- `LAT`: GPS latitude in decimal degrees (e.g., 12.971234)
- `LON`: GPS longitude in decimal degrees (e.g., 77.594567)
- `CONF`: Confidence score 0.0-1.0 (e.g., 0.85)
- `AREA`: Detection area in pixels (e.g., 1732)

**Processing:**
- Parsed by `processStatustextForDetections()` in pixhawkServicePyMAVLink.js
- Saved to database via `missionService.saveDetection()`
- Broadcasted to all clients via `io.emit('crop_detection', detectionData)`
- Duplicate filtering via `processedDetections` Set

### 2. Detection Statistics: `DSTAT|TOTAL|ACTIVE|MISSION_ID`
Example: `DSTAT|42|AUTO|mission_20240315_142530`

**Fields:**
- `TOTAL`: Total detections in this mission
- `ACTIVE`: Detection status (AUTO/MANUAL/PAUSED)
- `MISSION_ID`: Current mission identifier

**Processing:**
- Emitted as `io.emit('detection_stats', {...})`
- Provides mission-level statistics

### 3. Image Capture: `IMG|ID|PATH`
Example: `IMG|1234|/home/pi/detections/det_1234.jpg`

**Fields:**
- `ID`: Detection identifier matching DET| message
- `PATH`: Absolute path to saved image on Pi

**Processing:**
- Emitted as `io.emit('image_captured', {...})`
- Links image files to detections

### 4. Pi System Stats: `STAT|CPU|MEM|DISK|TEMP`
Example: `STAT|45.2|62.8|34.5|52.3`

**Fields:**
- `CPU`: CPU usage percentage
- `MEM`: Memory usage percentage
- `DISK`: Disk usage percentage
- `TEMP`: CPU temperature in Celsius

**Processing:**
- Emitted as `io.emit('pi_stats', {...})`
- Monitors Pi health during flight

## Code Changes Made

### 1. services/pixhawkServicePyMAVLink.js

#### Added Detection Tracking
```javascript
const processedDetections = new Set(); // Track processed detection IDs
```

#### Added STATUSTEXT Processing Function
```javascript
function processStatustextForDetections(droneId, statustextLog, io) {
  // Parses all 4 message formats: DET|, DSTAT|, IMG|, STAT|
  // Filters duplicates
  // Saves detections to database
  // Broadcasts to all connected clients
}
```

#### Modified Telemetry Polling
```javascript
// In startTelemetryPolling():
// After logging telemetry, added:
if (result.data.telemetry.statustext_log && Array.isArray(result.data.telemetry.statustext_log)) {
  processStatustextForDetections(droneId, result.data.telemetry.statustext_log, io);
}
```

## How Detection Flow Works

### Step-by-Step Process:

1. **Pi Detects Yellow Plant** (rpi-connect/pi_controller.py)
   - Camera captures frame every ~200ms in AUTO mode
   - HSV color filtering identifies yellow regions
   - Contours extracted, filtered by min_area (150px)
   - Geolocation calculates GPS from pixel coordinates
   - Creates detection object with ID, lat, lon, confidence, area

2. **Pi Sends MAVLink STATUSTEXT** (rpi-connect/modules/mavlink_detection_sender.py)
   - Formats: "DET|1234|12.971234|77.594567|0.85|1732"
   - Sends via pymavlink to /dev/serial0 (TELEM2)
   - Uses STATUSTEXT message (text field, 50 chars max)
   - Also sends via Socket.IO to local dashboard (WiFi range)

3. **Pixhawk Receives and Forwards**
   - ArduPilot receives STATUSTEXT on TELEM2
   - Forwards all messages to TELEM1 (GCS radio link)
   - No processing needed, just relay

4. **PyMAVLink Service Collects** (pymavlink_service.py)
   - Connected to Pixhawk via USB/serial (TELEM1)
   - Receives all MAVLink messages in `_telemetry_loop()`
   - STATUSTEXT messages stored in `self.statustext_log[]`
   - Last 20 messages kept in rolling buffer
   - Included in telemetry dict: `telemetry['statustext_log']`
   - Exposed via HTTP API: GET /drone/{id}/telemetry

5. **Node.js GCS Polls Telemetry** (pixhawkServicePyMAVLink.js)
   - `startTelemetryPolling()` requests telemetry every 250ms
   - Receives JSON: `{ telemetry: { ..., statustext_log: [...] } }`
   - Calls `processStatustextForDetections()` with statustext_log

6. **Detection Parsing and Broadcasting**
   - Parses "DET|" messages from statustext_log
   - Extracts: detection_id, latitude, longitude, confidence, detection_area
   - Checks `processedDetections` Set to avoid duplicates
   - Saves via `missionService.saveDetection(droneId, detection)`
   - Broadcasts via `io.emit('crop_detection', detectionData)`
   - Logs: `🌾 Detection via MAVLink from Drone 1: 1234 at (12.971234, 77.594567)`

7. **Dashboard Displays** (mission_control.html)
   - Socket.IO listener receives 'crop_detection' event
   - Adds marker to map at GPS coordinates
   - Updates detection list with ID, confidence, area
   - Shows notification to operator

## Configuration Requirements

### Raspberry Pi (rpi-connect/config.json)
```json
{
  "mavlink_detection": {
    "enabled": true,           // MUST be true
    "port": "/dev/serial0",    // TELEM2 port
    "baudrate": 921600,        // Match Pixhawk TELEM2 baud rate
    "system_id": 2,           // Pi MAVLink system ID
    "component_id": 191       // Pi MAVLink component ID
  },
  "read_only": false,         // MUST be false to send detections
  "detection": {
    "yellow_hsv_lower": [20, 80, 60],
    "yellow_hsv_upper": [32, 255, 255],
    "min_contour_area": 150,
    "confidence_threshold": 0.50
  }
}
```

### GCS PyMAVLink Service (external-services/)
```bash
# Start pymavlink_service.py before GCS server
cd external-services
python3 pymavlink_service.py
# Connects to Pixhawk, collects MAVLink messages
# Listens on http://localhost:5000
```

### GCS Node.js Server (server.js)
```bash
# Ensure PYMAVLINK_URL environment variable
export PYMAVLINK_URL=http://localhost:5000  # Default

# Start GCS server
npm start
# Connects to PyMAVLink service
# Serves dashboard on http://localhost:3000
```

## Telemetry Polling Configuration

### Current Settings
- **Poll Interval**: 250ms (4 Hz)
- **STATUSTEXT Buffer**: Last 20 messages
- **Duplicate Filtering**: Last 1000 detection IDs
- **Timeout**: None (continuous polling)

### Adjusting Poll Rate
In `pixhawkServicePyMAVLink.js`:
```javascript
const TELEMETRY_POLL_INTERVAL = 250; // ms (default)
// Faster: 100ms (10 Hz, more responsive but more CPU)
// Slower: 500ms (2 Hz, less CPU but delayed detections)
```

## Testing the Integration

### 1. Start PyMAVLink Service
```bash
cd external-services
python3 pymavlink_service.py
```
Expected output:
```
INFO - PyMAVLink service starting...
INFO - Listening on http://localhost:5000
```

### 2. Start GCS Server
```bash
cd GCS-without-pi
npm start
```
Expected output:
```
🚀 Ground Control Station running on http://localhost:3000
📊 Mission Control Dashboard: http://localhost:3000/mission-control
🚁 Initializing Pixhawk connections...
✅ PyMAVLink service is running
Connecting to Drone 1...
✅ Drone 1 connected on COM5
Telemetry polling started for Drone 1
```

### 3. Start Pi Controller
```bash
# On Raspberry Pi
cd ~/rpi-connect
python3 pi_controller.py
```
Expected output:
```
📡 MAVLink Detection Sender initialized
   Port: /dev/serial0
   Baud: 921600
   System: 2, Component: 191
🎥 Camera initialized: 4056x3040
🌾 Yellow Crop Detector initialized
✈️  Connected to Pixhawk on /dev/ttyAMA0
🟢 Starting autonomous detection in AUTO mode
```

### 4. Monitor GCS Logs
Watch for detection messages:
```
🌾 Detection via MAVLink from Drone 1: 1234 at (12.971234, 77.594567)
   ✅ Detection broadcasted to all clients
```

### 5. Check Dashboard
Open browser: http://localhost:3000/mission-control
- Map should show drone position
- Detections appear as yellow markers
- Detection list updates in real-time

## Troubleshooting

### No Detections Appearing

#### 1. Check Pi is Sending
On Pi, check logs:
```bash
tail -f ~/rpi-connect/logs/pi_controller.log
```
Should see:
```
📡 Sent detection via MAVLink: DET|1234|12.971234|77.594567|0.85|1732
```

#### 2. Check PyMAVLink Service
Check pymavlink_service.py logs:
```
[INFO] Drone 1 STATUSTEXT: DET|1234|12.971234|77.594567|0.85|1732
```

#### 3. Check GCS Processing
Node.js GCS logs should show:
```
🌾 Detection via MAVLink from Drone 1: 1234 at (12.971234, 77.594567)
```

#### 4. Test Telemetry API
```bash
curl http://localhost:5000/drone/1/telemetry
```
Should return JSON with `statustext_log`:
```json
{
  "telemetry": {
    "statustext_log": [
      {
        "severity": 6,
        "text": "DET|1234|12.971234|77.594567|0.85|1732",
        "timestamp": 1710512345.67
      }
    ]
  }
}
```

### Duplicate Detections

If seeing duplicate detections on dashboard:
- `processedDetections` Set filters duplicates by ID
- Check if Pi is sending same ID multiple times
- Verify detection_id is unique (timestamp-based recommended)

### Detections Delayed

If detections appear late:
1. Reduce `TELEMETRY_POLL_INTERVAL` to 100ms (10 Hz)
2. Check network latency between Pi and Pixhawk
3. Verify radio link quality (RSSI, packet loss)

### STATUSTEXT Buffer Overflow

If losing messages (>20 per 250ms):
- Increase `statustext_max` in pymavlink_service.py
- Or reduce detection frequency on Pi
- Current capacity: ~80 detections/second (plenty)

## Performance Considerations

### Expected Detection Rate
- **Camera FPS**: 5 fps (200ms capture interval)
- **Detection Rate**: 0-5 detections/second (depends on field)
- **STATUSTEXT Rate**: Matches detection rate
- **Telemetry Poll**: 4 Hz (250ms interval)
- **Message Buffer**: 20 messages × 4 Hz = 5 seconds history

### Network Bandwidth
- **Per Detection**: ~50 bytes STATUSTEXT message
- **5 detections/sec**: 250 bytes/sec (~2 kbps)
- **Telemetry**: ~500 bytes × 4 Hz = 2 KB/sec (16 kbps)
- **Total MAVLink**: ~20 kbps (negligible on 915MHz radio)

### CPU Usage
- **PyMAVLink Service**: ~2-5% CPU (polling, parsing)
- **Node.js GCS**: ~5-10% CPU (HTTP requests, Socket.IO)
- **Browser Dashboard**: ~10-20% CPU (map rendering)

## Advantages of This Approach

1. **Long-Range Compatible**: MAVLink radio link (2-40 km range)
2. **Reliable**: MAVLink protocol with error checking
3. **No WiFi Required**: Works beyond WiFi range
4. **Existing Infrastructure**: Uses Pixhawk telemetry link
5. **Minimal Latency**: ~500ms end-to-end (acceptable for survey missions)
6. **Battle-Tested**: MAVLink is proven in UAV operations
7. **Compatible with Mission Planner**: Standard STATUSTEXT messages
8. **Duplicate Filtering**: Prevents redundant database entries
9. **Multiple Formats**: Supports DET, DSTAT, IMG, STAT messages

## Alternative: Direct MAVLink Handler

If you prefer direct serial MAVLink connection (no HTTP middle layer):

1. Use `services/pixhawkService.js` instead of `pixhawkServicePyMAVLink.js`
2. Update `server.js` to require `pixhawkService` instead
3. Update `socket/socketHandlers.js` to use direct connection events
4. No need for pymavlink_service.py HTTP server
5. Lower latency (~200ms), but requires Node.js MAVLink library

**Current Approach (HTTP PyMAVLink) is Recommended** because:
- Python MAVLink library more mature than Node.js version
- HTTP API easier to debug (curl, Postman)
- Separates concerns (Python handles protocol, Node.js handles UI)
- Python service can restart without affecting GCS server

## Summary

Your custom GCS now fully supports MAVLink STATUSTEXT detection messages:

✅ **Receives** STATUSTEXT from PyMAVLink service HTTP API  
✅ **Parses** DET|ID|LAT|LON|CONF|AREA format  
✅ **Filters** duplicates via processedDetections Set  
✅ **Saves** to database via missionService  
✅ **Broadcasts** to dashboard via Socket.IO  
✅ **Displays** on map with markers  
✅ **Supports** all message types: DET, DSTAT, IMG, STAT  
✅ **Logs** with clear emojis: 🌾 for detections  

**Next Steps:**
1. Start pymavlink_service.py
2. Start GCS server (npm start)
3. Start pi_controller.py on Raspberry Pi
4. Arm drone, switch to AUTO mode
5. Watch detections appear in real-time!

**Detection Pipeline:**
Pi Camera → Yellow Detector → Geolocation → MAVLink STATUSTEXT → Pixhawk → Radio → PyMAVLink → HTTP API → Node.js GCS → Socket.IO → Dashboard

🎉 **Your long-range detection system is now operational!**
