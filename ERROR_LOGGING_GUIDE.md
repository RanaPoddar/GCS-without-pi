# Error Logging & Troubleshooting Guide

## Overview
The system now provides **comprehensive error logging** when mission start fails. All errors are displayed in multiple places for easy troubleshooting.

## Where to See Errors

### 1. **System Messages Console** (Mission Control Dashboard)
- Located in the bottom section of `/mission-control` page
- Color-coded messages:
  - 🔵 **Blue** - Info messages
  - 🟢 **Green** - Success messages
  - 🟡 **Yellow** - Warning messages  
  - 🔴 **Red** - Error messages
- Shows real-time errors with timestamps
- Use 🗑️ button to clear console

### 2. **Alert Popups**
- Browser alerts show critical errors immediately
- Contains detailed error descriptions
- Guides you to check System Messages console

### 3. **Browser Console** (F12 Developer Tools)
- Full error objects and stack traces
- Network request/response details
- Advanced debugging information

### 4. **Server Logs**

#### Node.js Server Logs:
```bash
# View combined logs (all messages)
tail -f combined.log

# View error logs only
tail -f error.log

# View last 100 lines
tail -100 combined.log
```

#### PyMAVLink Service Logs:
```bash
# View PyMAVLink logs (after restarting with updated script)
tail -f pymavlink.log

# View last 50 lines
tail -50 pymavlink.log
```

**Note:** You need to restart PyMAVLink service to create `pymavlink.log`:
```bash
# Stop current service
pkill -f pymavlink_service

# Start with new logging
./start-pymavlink.sh
```

## Mission Start Error Flow

When you click "Start Mission", the system performs these steps:

### Step 1: Validation
**Errors caught:**
- ❌ **No mission loaded** - Upload KML file first
- ❌ **Drone not connected** - Start PyMAVLink service and connect

**UI Response:**
- Alert popup with clear message
- Red error in System Messages console
- Start button remains enabled

### Step 2: Upload Waypoints
**Errors caught:**
- ❌ **Cannot connect to PyMAVLink** (port 5000 unreachable)
- ❌ **HTTP 404** - Drone not found
- ❌ **HTTP 400** - Invalid waypoint data

**UI Response:**
```
System Messages Console:
[12:45:30] 📤 Uploading waypoints to drone...
[12:45:31] ❌ Failed to upload mission!
[12:45:31] ⚠️ Cannot connect to PyMAVLink service...
```

**Alert popup** shows:
- Network error details
- Instructions to start PyMAVLink service
- Port and command information

### Step 3: ARM Drone
**Errors caught with detailed diagnostics:**

#### GPS Issues:
```
ARM failed. GPS: 0 fix, 5 satellites; Battery: 12.6V; Mode: STABILIZE. 
Issues: GPS fix quality low (0). Need 3D fix (type 3); Low satellite count (5). Recommended: 8+
```

**System Messages shows:**
```
[12:45:32] 🔧 Arming drone...
[12:45:33] ❌ Failed to arm drone!
[12:45:33] ⚠️ ARM failed. GPS: 0 fix, 5 satellites; Battery: 12.6V; Mode: STABILIZE...
```

#### Battery Issues:
```
ARM failed. GPS: 3 fix, 10 satellites; Battery: 10.2V; Mode: STABILIZE.
Issues: Low battery voltage (10.2V)
```

#### Already Armed:
```
✅ Drone armed successfully
(if already armed, shows: "Drone already armed")
```

**Alert popup** includes:
- Exact error from PyMAVLink
- Current GPS fix type and satellite count
- Battery voltage
- Flight mode
- Common solutions checklist

### Step 4: Start Mission
**Errors caught:**

#### Not Armed:
```
Drone not armed. ARM the drone before starting mission.
```

#### Wrong Flight Mode:
```
Failed to set GUIDED mode. Current mode: STABILIZE
```
or
```
Failed to set AUTO mode. Current mode: GUIDED
```

#### No Mission Uploaded:
```
No mission uploaded. Upload waypoints first.
```

**UI Response:**
```
System Messages Console:
[12:45:34] 🚀 Starting mission execution...
[12:45:35] ❌ Failed to start mission!
[12:45:35] ⚠️ Failed to set AUTO mode. Current mode: GUIDED
```

## Common Error Scenarios

### 1. PyMAVLink Not Running
**Symptoms:**
- "Cannot connect to PyMAVLink service" errors
- Network fetch failures

**Solution:**
```bash
cd /home/ranapoddar/Documents/Nidar/GCS-without-pi
./start-pymavlink.sh
```

### 2. Drone Not Connected (Simulation)
**Symptoms:**
- "Drone not connected" in dashboard
- HTTP 404 errors on API calls

**Solution:**
- Click 🎮 **Simulation** button in dashboard header
- Or run: `curl -X POST http://localhost:5000/drone/1/connect_simulation`

### 3. GPS Not Ready
**Symptoms:**
- ARM fails with "GPS fix quality low"
- Satellite count < 8

**Solution (Simulation):**
- Simulation mode automatically provides GPS fix
- For real hardware: Wait for GPS lock outdoors, ensure clear sky view

**Error Details:**
```
Pre-arm check: GPS=0 (5 sats), Battery=12.6V, Mode=STABILIZE
⚠️ GPS fix quality low (0). Need 3D fix (type 3)
⚠️ Low satellite count (5). Recommended: 8+
```

### 4. Low Battery
**Symptoms:**
- ARM fails with "Low battery voltage"
- Battery < 11.0V

**Solution:**
- Charge battery
- For simulation: Battery is automatically set to 100%

### 5. Wrong Flight Mode
**Symptoms:**
- Mission start fails with "Failed to set GUIDED mode"
- Cannot switch to AUTO

**Solution:**
- Check flight mode restrictions in ArduPilot parameters
- Ensure GUIDED and AUTO modes are enabled
- For simulation: Mode changes work automatically

## Testing Error Messages

### Test 1: ARM Without Connection
```bash
# Make sure drone is NOT connected
curl -X POST http://localhost:5000/drone/1/arm
```

**Expected Response:**
```json
{
  "success": false,
  "error": "Drone not connected",
  "command": "arm"
}
```

### Test 2: Mission Start Without ARM
```bash
# Connect in simulation (but don't ARM)
curl -X POST http://localhost:5000/drone/1/connect_simulation

# Try to start mission
curl -X POST http://localhost:5000/drone/1/mission/start
```

**Expected Response:**
```json
{
  "success": false,
  "command": "mission_start",
  "error": "Drone not armed. ARM the drone before starting mission."
}
```

### Test 3: Mission Start Without Upload
```bash
# Connect and ARM
curl -X POST http://localhost:5000/drone/1/connect_simulation
curl -X POST http://localhost:5000/drone/1/arm

# Try to start (no waypoints uploaded)
curl -X POST http://localhost:5000/drone/1/mission/start
```

**Expected Response:**
```json
{
  "success": false,
  "command": "mission_start",
  "error": "No mission uploaded. Upload waypoints first."
}
```

## Logging Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  (Mission Control Dashboard - /mission-control)          │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │     System Messages Console                      │  │
│  │  • Real-time error display                       │  │
│  │  • Color-coded messages                          │  │
│  │  • Timestamps                                    │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ Socket.IO Events
                          │
┌─────────────────────────────────────────────────────────┐
│              Node.js Server (Port 3000)                  │
│                                                          │
│  • Socket.IO event handlers                              │
│  • Winston logger → combined.log, error.log              │
│  • Forwards commands to PyMAVLink                        │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ HTTP API
                          │
┌─────────────────────────────────────────────────────────┐
│         PyMAVLink Service (Port 5000)                    │
│                                                          │
│  • Flask REST API                                        │
│  • MAVLink protocol handler                              │
│  • Python logging → pymavlink.log (stdout/stderr)        │
│  • Drone simulation engine                               │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ MAVLink/Serial
                          │
┌─────────────────────────────────────────────────────────┐
│              Pixhawk Flight Controller                   │
│           (or Simulation Virtual Flight Controller)      │
└─────────────────────────────────────────────────────────┘
```

## API Error Response Format

All endpoints now return consistent error format:

### Success Response:
```json
{
  "success": true,
  "command": "arm",
  "message": "Drone armed successfully"
}
```

### Error Response:
```json
{
  "success": false,
  "command": "arm",
  "error": "ARM failed. GPS: 0 fix, 5 satellites; Battery: 12.6V; Mode: STABILIZE. Issues: GPS fix quality low (0). Need 3D fix (type 3); Low satellite count (5). Recommended: 8+"
}
```

### HTTP Status Codes:
- **200** - Success
- **400** - Bad request (validation failed, command rejected)
- **404** - Drone not found/connected
- **500** - Server error (unexpected exception)

## Summary

✅ **Now implemented:**
1. Detailed error messages from PyMAVLink ARM checks
2. GPS, battery, mode status in error messages
3. Error display in System Messages Console
4. Alert popups with actionable guidance
5. Comprehensive logging to files
6. Consistent API error format

🎯 **Result:**
When you click "Start Mission" and something fails, you'll **immediately see**:
- **What went wrong** (specific error)
- **Why it happened** (GPS fix, battery, mode, etc.)
- **How to fix it** (clear instructions)

No more mysterious failures! 🚀
