# ✅ Mission Debug Tool - Testing Checklist

## Pre-Flight Checks

### 1. Services Running
- [ ] PyMAVLink service is running on port 5000
  ```bash
  python external-services/pymavlink_service.py
  ```
- [ ] Node.js server is running on port 3000
  ```bash
  npm start
  ```
- [ ] Both terminals show no errors

### 2. Open Dashboard
- [ ] Navigate to: `http://localhost:3000/mission_debug.html`
- [ ] Dashboard loads without errors
- [ ] Can see all sections: Connection, Mission Input, Upload, Debug Log

---

## Test Scenarios

### Scenario 1: Quick Connection Test
**Goal:** Verify PyMAVLink communication

1. - [ ] Select Drone ID (1, 2, or 3)
2. - [ ] Click "Check Connection"
3. - [ ] See green status box with connection info
4. - [ ] Debug log shows connection success

**Expected Result:**
```
✅ Drone 1 connected - STABILIZE
```

---

### Scenario 2: Test Pattern Upload
**Goal:** Test basic waypoint upload flow

1. - [ ] Click "Generate 4-Point Square Pattern"
2. - [ ] Verify 4 waypoints appear in table
3. - [ ] Check waypoint preview stats
4. - [ ] Click "📤 Upload Mission to Drone"
5. - [ ] Watch debug log for upload confirmation
6. - [ ] Verify message: "Successfully uploaded X waypoints"

**Expected Output:**
```
📤 Uploading 4 waypoints to drone 1...
✅ Mission uploaded successfully! 7 waypoints
   (Includes TAKEOFF + NAV_TO_START + 4 survey + RTL)
```

**Pixhawk receives:**
- Seq 0: TAKEOFF
- Seq 1: NAV_WAYPOINT (to first point)
- Seq 2-5: Your 4 survey waypoints
- Seq 6: RETURN_TO_LAUNCH

---

### Scenario 3: Mission Planner File Upload
**Goal:** Test .waypoints file parsing

1. - [ ] Click "Upload Mission File" 
2. - [ ] Select: `data/kml_uploads/test_mission.waypoints`
3. - [ ] Verify 12 waypoints load in table
4. - [ ] Check coordinates match file
5. - [ ] Upload to drone
6. - [ ] Confirm 15 total waypoints sent (12 + TAKEOFF + NAV + RTL)

**Expected:**
```
✅ Loaded 12 waypoints from Mission Planner file
📤 Uploading 12 waypoints to drone 1...
✅ Mission uploaded successfully! 15 waypoints
```

---

### Scenario 4: JSON Mission File Upload
**Goal:** Test generated KML mission file

1. - [ ] Click "Upload Mission File"
2. - [ ] Select: `data/kml_uploads/mission_1767731890338.json`
3. - [ ] Verify 12 waypoints load
4. - [ ] Check first point: ~23.295, 85.310
5. - [ ] Upload to drone
6. - [ ] Confirm success

**Expected:**
```
✅ Loaded 12 waypoints from mission_1767731890338.json
✅ Mission uploaded successfully! 15 waypoints
```

---

### Scenario 5: JSON Paste Test
**Goal:** Test manual JSON input

1. - [ ] Paste this into the JSON textarea:
```json
[
  {"seq": 0, "lat": 23.295, "lon": 85.310, "alt": 15.0},
  {"seq": 1, "lat": 23.296, "lon": 85.311, "alt": 15.0},
  {"seq": 2, "lat": 23.296, "lon": 85.312, "alt": 15.0}
]
```
2. - [ ] Click "Load from JSON"
3. - [ ] Verify 3 waypoints appear
4. - [ ] Upload to drone
5. - [ ] Confirm 6 total waypoints (3 + TAKEOFF + NAV + RTL)

---

### Scenario 6: Start Mission (Simulation Only)
**Goal:** Test mission execution (ONLY IN SIMULATION)

⚠️ **WARNING:** Only do this in simulation mode or safe test environment!

1. - [ ] Upload a mission (any method)
2. - [ ] Click "▶️ Start Mission (AUTO Mode)"
3. - [ ] Watch debug log for mode change
4. - [ ] Drone should enter AUTO mode

**Expected:**
```
▶️ Starting mission on Drone 1...
✅ Mission started! Drone in AUTO mode
```

---

### Scenario 7: Emergency Stop
**Goal:** Test RTL/stop command

1. - [ ] Click "⏹️ Stop Mission (RTL)"
2. - [ ] Confirm stop command sent
3. - [ ] Drone should switch to RTL mode

**Expected:**
```
⏹️ Stopping mission and initiating RTL...
✅ Mission stopped, RTL initiated
```

---

## Validation Criteria

### ✅ Pass Criteria:
- All waypoint formats parse correctly
- Upload shows success message
- PyMAVLink confirms waypoint count
- TAKEOFF + NAV + RTL added automatically
- Debug log shows detailed information
- No JavaScript errors in browser console

### ❌ Fail Indicators:
- "PyMAVLink service not reachable" error
- Waypoint count = 0 after loading
- Upload returns error
- Missing TAKEOFF or RTL commands
- JavaScript errors in console

---

## Common Issues & Solutions

### Issue: "Cannot connect to PyMAVLink service"
**Solution:**
```bash
# Check if service is running
ps aux | grep pymavlink_service

# If not running, start it
cd /home/ranapoddar/Documents/Nidar/New/GCS-without-pi
source myvenv/bin/activate
python external-services/pymavlink_service.py
```

### Issue: "No waypoints loaded"
**Solution:**
- Check file format (JSON must be valid)
- .waypoints file must have proper QGC format
- Verify file path is correct

### Issue: "Upload failed"
**Solution:**
- Ensure drone is connected
- Check PyMAVLink terminal for errors
- Verify waypoints have lat, lon, alt fields

### Issue: Dashboard doesn't load
**Solution:**
```bash
# Restart Node.js server
cd /home/ranapoddar/Documents/Nidar/New/GCS-without-pi
npm start
```

---

## Success Metrics

After completing all tests, you should have:

✅ Successfully parsed multiple waypoint formats
✅ Uploaded missions to PyMAVLink service
✅ Verified TAKEOFF + NAV + SURVEY + RTL sequence
✅ Confirmed waypoint count matches expectations
✅ Tested emergency stop functionality
✅ No errors in debug logs
✅ Confidence in mission upload pipeline

---

## Next Steps

Once all tests pass:

1. **Export real mission from Mission Planner**
   - Plan your survey in Mission Planner
   - Export as .waypoints file
   - Upload through debug dashboard
   - Verify waypoint sequence

2. **Test with real Pixhawk (if available)**
   - Connect Pixhawk via MAVLink
   - Upload simple test mission
   - Verify mission shows in Pixhawk
   - Check AUTO mode behavior (SAFE AREA ONLY!)

3. **Integrate with main dashboard**
   - Once validated, use same upload logic
   - Can add file upload to mission_control.html
   - Reuse waypoint normalization code

---

## Sign-Off

Date: ____________

Tester: ____________

Tests Passed: _____ / 7

Notes:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

System Status: [ ] Ready for Flight Testing  [ ] Needs More Work
