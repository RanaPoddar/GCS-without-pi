# Troubleshooting Immediate RTL After Mission Start

## Problem
Drone executes RTL (Return to Launch) immediately after starting AUTO mission, sometimes right after takeoff.

## Common Causes & Solutions

### 1. GPS/EKF Not Ready ⚠️ MOST COMMON

**Symptoms:**
- RTL immediately when switching to AUTO
- STATUSTEXT: "EKF variance"
- STATUSTEXT: "Bad AHRS"
- STATUSTEXT: "Need 3D Fix"

**Solution:**
```bash
# Wait for good GPS before arming:
# - 10+ satellites visible
# - HDOP < 2.0
# - 3D Fix (gps_fix_type = 3)
# - Wait 1-2 minutes after power-on for EKF to settle
```

**Check in GCS Dashboard:**
- Satellites: Should be ≥10
- HDOP: Should be <2.0
- GPS Fix: Should show "3D Fix"
- Flight mode: Wait in STABILIZE for 60+ seconds before ARM

**ArduCopter Pre-Arm Checks:**
- EKF must converge (takes 30-60 seconds after GPS lock)
- Compass must be calibrated
- Accelerometers must be calibrated

### 2. First Waypoint Too Far From Home

**Symptoms:**
- Drone arms, takes off, reaches altitude
- Immediately switches to RTL
- STATUSTEXT: "Waypoint x dist too far"
- Or: "Auto mission not started"

**Cause:**
First survey waypoint is >500m from takeoff point (geofence radius)

**Solution:**
Check your mission:
```python
# In kml_mission_planner.py output, check:
# Distance from takeoff to first waypoint

# Fix: Reduce mission area or increase geofence
```

**Check Geofence:**
```bash
# In Mission Planner, Parameters tab:
# FENCE_ENABLE = 1 (enabled)
# FENCE_RADIUS = 500 (default, meters)
# FENCE_ALT_MAX = 120 (default, meters)

# Your rpi-connect config.json has:
"geofence_radius": 500,  # Increase if needed
"geofence_max_altitude": 120,
```

**Quick Fix:**
Edit [config.json](rpi-connect/config.json):
```json
"safety": {
  "geofence_enabled": true,
  "geofence_radius": 1000,  // Increase from 500 to 1000m
  "geofence_max_altitude": 120,
  "geofence_min_altitude": 2
}
```

### 3. Battery Failsafe Triggered

**Symptoms:**
- RTL happens during flight
- STATUSTEXT: "Low battery"
- STATUSTEXT: "Battery failsafe"

**Solution:**
Check battery levels before flight:
- Voltage: Should be >14.8V (4S) or >22.2V (6S)
- Remaining: Should be >50%

**Check in config.json:**
```json
"safety": {
  "battery_rtl_threshold": 25,    // RTL at 25%
  "battery_land_threshold": 15,   // Land at 15%
  "battery_critical_voltage": 13.5 // RTL at 13.5V
}
```

**ArduCopter Parameters:**
```bash
# Check in Mission Planner:
BATT_LOW_VOLT = 14.0    # Voltage for RTL (4S)
BATT_CRT_VOLT = 13.0    # Voltage for LAND
BATT_LOW_MAH = 2000     # mAh for RTL
```

### 4. Mission Validation Failure

**Symptoms:**
- Mission uploads successfully
- RTL immediately when AUTO mode selected
- No error messages

**Cause:**
Mission has invalid parameters or waypoint order

**Solution:**
Verify mission structure:

```python
# Mission MUST have this order:
# 0. HOME (MAV_CMD_NAV_WAYPOINT at current position)
# 1. TAKEOFF (MAV_CMD_NAV_TAKEOFF with real coordinates, NOT 0,0)
# 2. NAV_WAYPOINT (fly to first survey point)
# 3-N. Survey waypoints (MAV_CMD_NAV_WAYPOINT)
# N+1. RTL (MAV_CMD_NAV_RETURN_TO_LAUNCH)
```

**Check TAKEOFF waypoint:**
```python
# CRITICAL: ArduCopter requires REAL coordinates for TAKEOFF
# NOT (0, 0) which is invalid!

# In pymavlink_service.py, verify:
takeoff_waypoint = {
    'latitude': current_lat,  # MUST be real GPS coords
    'longitude': current_lon,  # NOT 0.0!
    'altitude': 10.0,
    'command': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF
}
```

### 5. Compass/IMU Errors

**Symptoms:**
- Pre-arm check fails
- STATUSTEXT: "Compass not calibrated"
- STATUSTEXT: "Check mag field"
- STATUSTEXT: "High compass offsets"

**Solution:**
Calibrate sensors in Mission Planner:

```bash
# 1. Compass Calibration
Initial Setup → Mandatory Hardware → Compass
Click "Start" and rotate drone in all axes

# 2. Accelerometer Calibration  
Initial Setup → Mandatory Hardware → Accel Calibration
Follow on-screen instructions (level, nose down, etc.)

# 3. Radio Calibration
Initial Setup → Mandatory Hardware → Radio Calibration
Move all sticks to extremes
```

### 6. RC Failsafe Triggered

**Symptoms:**
- RTL during flight
- STATUSTEXT: "Radio failsafe"
- No RC input received

**Solution:**
```bash
# Check RC receiver connection
# Verify RC is powered on
# Check RC battery level
# Verify RC is bound to receiver

# In Mission Planner, Radio Calibration:
# All channels should show green bars
# Failsafe should be configured properly
```

### 7. AUTO Mode Not Enabled

**Symptoms:**
- Cannot switch to AUTO mode
- Mode immediately reverts to previous mode
- STATUSTEXT: "Mode change failed"

**Solution:**
```bash
# In Mission Planner, Config → Full Parameter List:
FLTMODE1 = Stabilize
FLTMODE2 = Alt Hold  
FLTMODE3 = Loiter
FLTMODE4 = Auto       # <-- Make sure AUTO is assigned
FLTMODE5 = RTL
FLTMODE6 = Land

# Or via RC transmitter:
# Ensure AUTO mode is assigned to a flight mode switch
```

## Diagnostic Steps

### Step 1: Check Pre-Arm Conditions
```bash
# Before arming, verify:
1. GPS: 10+ satellites, HDOP < 2.0
2. EKF: No "EKF variance" messages
3. Compass: Calibrated, no "mag field" errors
4. Battery: >15V (4S), >50%
5. RC: All channels responding
6. Mode: Start in STABILIZE
```

### Step 2: Wait for EKF Convergence
```bash
# After GPS lock (usually 30-60 seconds):
1. Power on drone
2. Wait for GPS lock (10+ sats)
3. Wait additional 1-2 minutes in STABILIZE
4. Watch for "EKF" messages to clear
5. Verify "Ready to ARM" in GCS
```

### Step 3: Check Mission Structure
```bash
# Verify mission file:
cd GCS-without-pi
cat test_mission_fixed.waypoints

# Should see:
QGC WPL 110
0	1	0	16	...		# HOME (seq 0, current=1)
1	0	3	22	...		# TAKEOFF (seq 1, cmd=22)
2	0	3	178	...		# SPEED (seq 2, cmd=178)
3	0	3	16	...		# First waypoint (cmd=16)
...
N	0	3	20	...		# RTL (cmd=20)
```

### Step 4: Check STATUSTEXT Messages
```bash
# In pymavlink_service.py logs or Mission Planner Messages tab:
# Look for error messages right before RTL:

[INFO] Drone 1 STATUSTEXT: EKF2 IMU0 is using GPS    # Good
[INFO] Drone 1 STATUSTEXT: EKF2 IMU1 is using GPS    # Good
[WARN] Drone 1 STATUSTEXT: Bad AHRS                   # BAD - Not ready
[WARN] Drone 1 STATUSTEXT: Waypoint 0 dist too far   # BAD - Too far
[WARN] Drone 1 STATUSTEXT: Auto mission not started  # BAD - Validation failed
```

### Step 5: Test with Simple Mission
```bash
# Create minimal test mission:
# Just HOME + TAKEOFF + 1 waypoint nearby + RTL

# Example: 20m away from takeoff
cd GCS-without-pi
python3
```

```python
import json

test_mission = {
    "version": "1.0",
    "mission_name": "Simple_Test",
    "waypoints": [
        {
            "id": 1,
            "latitude": 12.971234,  # 20m north of takeoff
            "longitude": 77.594567,
            "altitude": 10.0,
            "command": "NAV_WAYPOINT"
        }
    ]
}

with open('test_simple_mission.json', 'w') as f:
    json.dump(test_mission, f, indent=2)

print("Created test_simple_mission.json")
```

Upload this simple mission first to verify AUTO mode works.

## Solution Checklist

Before starting AUTO mission:

- [ ] **GPS Lock**: 10+ satellites, 3D fix, HDOP < 2.0
- [ ] **EKF Ready**: Wait 1-2 minutes after GPS lock, no "EKF variance" messages
- [ ] **Compass**: Calibrated, no "mag field" errors  
- [ ] **Battery**: >15V (4S) or >22V (6S), >50% remaining
- [ ] **RC Connection**: All channels responding, failsafe configured
- [ ] **Geofence**: Radius large enough for mission area (500-1000m)
- [ ] **Mission Structure**: HOME → TAKEOFF → waypoints → RTL
- [ ] **TAKEOFF Coords**: Real GPS coordinates, NOT (0, 0)
- [ ] **Pre-Arm**: All pre-arm checks passed, "Ready to ARM"
- [ ] **Flight Mode**: AUTO mode enabled in parameters
- [ ] **Wait**: Stay in STABILIZE for 60+ seconds after GPS lock

## Most Likely Fix for Your Issue

Based on "drone is rtl everytime, sometimes taking off then rtl", the issue is most likely:

### **First waypoint too far from home** (geofence violation)

**Quick Fix:**

1. **Check mission distance:**
```bash
cd GCS-without-pi
python3 -c "
import json
with open('test_mission_fixed.json') as f:
    mission = json.load(f)
wps = mission.get('waypoints', [])
if wps:
    print(f'First waypoint: {wps[0][\"latitude\"]}, {wps[0][\"longitude\"]}')
"
```

2. **Check geofence in parameters:**
```bash
# In Mission Planner, Config → Full Parameter List:
# Search for: FENCE_RADIUS
# Default: 300m
# Increase to: 1000m or more
```

3. **Or disable geofence temporarily for testing:**
```bash
# In Mission Planner:
FENCE_ENABLE = 0  # Disable geofence
FENCE_ACTION = 0  # Or set to 0 (none) instead of 1 (RTL)
```

4. **Increase geofence in config.json:**
```json
"safety": {
  "geofence_radius": 1000  // Increase from 500
}
```

### **Or: EKF not converged yet**

**Quick Fix:**

1. **Wait longer before arming:**
   - Power on drone
   - Wait for 10+ satellites
   - Wait additional 2 minutes in STABILIZE mode
   - Watch for EKF messages to clear in Mission Planner

2. **Check EKF status:**
```bash
# In Mission Planner, Flight Data screen:
# HUD should show "Ready to ARM"
# No red "EKF" warnings
# GPS shows "3D Fix"
```

## Testing Procedure

1. **Power on drone, wait 3 minutes in STABILIZE**
   - Let GPS acquire satellites
   - Let EKF converge
   - Watch for "Ready to ARM"

2. **Check telemetry:**
   - Satellites: ≥10
   - HDOP: <2.0
   - Battery: >15V
   - No error messages

3. **Arm in STABILIZE mode first:**
   - Verify motors spin
   - Verify RC control works
   - Disarm and check for errors

4. **Takeoff in ALT HOLD mode:**
   - Manually take off to 10m
   - Verify stable hover
   - Check GPS position on map

5. **Switch to AUTO mode:**
   - If RTL happens, check STATUSTEXT messages
   - Note exact altitude/position when RTL triggered

6. **Review logs:**
   - Check Mission Planner Messages tab
   - Look for error messages right before RTL
   - Check pymavlink_service.py logs

## Expected Behavior (Correct Mission)

```
1. Power on → Wait for GPS (10+ sats, 3D fix)
2. Wait 2 minutes → EKF converges
3. Arm in STABILIZE → Motors spin
4. Switch to AUTO → Drone starts mission:
   - Takes off to mission altitude (10m)
   - Flies to first waypoint
   - Executes lawn mower pattern
   - Returns to home at end (RTL)
5. Lands automatically at home position
```

## If Still Having Issues

Check these logs:

1. **Mission Planner Messages tab** during flight
2. **pymavlink_service.py console output**
3. **DataFlash logs** after flight (download from drone)
4. **GCS console logs** in browser (F12 → Console)

Most common actual issue: **Geofence radius too small + first waypoint >500m away = immediate RTL**

**Solution: Increase FENCE_RADIUS to 1000m or disable fence for testing**
