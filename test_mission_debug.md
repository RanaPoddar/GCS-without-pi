# Mission Upload Debug Tool - Usage Guide

## 🚀 Quick Start

### 1. Start the Services

```bash
# Terminal 1: Start PyMAVLink service
cd /home/ranapoddar/Documents/Nidar/New/GCS-without-pi
source myvenv/bin/activate
python external-services/pymavlink_service.py

# Terminal 2: Start Node.js server
cd /home/ranapoddar/Documents/Nidar/New/GCS-without-pi
npm start
```

### 2. Open Debug Dashboard

Open your browser and go to:
```
http://localhost:3000/mission_debug.html
```

---

## 📋 Features

### ✅ Mission Input Methods

#### Method 1: JSON Waypoints (Paste)
Paste waypoints in JSON format:
```json
[
  {"seq": 0, "lat": 23.295, "lon": 85.310, "alt": 15.0},
  {"seq": 1, "lat": 23.296, "lon": 85.311, "alt": 15.0},
  {"seq": 2, "lat": 23.296, "lon": 85.312, "alt": 15.0}
]
```

Or with full field names:
```json
[
  {"seq": 0, "latitude": 23.295, "longitude": 85.310, "altitude": 15.0},
  {"seq": 1, "latitude": 23.296, "longitude": 85.311, "altitude": 15.0}
]
```

#### Method 2: Upload Mission Planner .waypoints File
1. Export mission from Mission Planner as `.waypoints` file
2. Click "Upload Mission File" button
3. Select your `.waypoints` file
4. Waypoints will be automatically parsed

#### Method 3: Upload JSON Mission File
Upload the generated mission files from your KML processing:
```
/data/kml_uploads/mission_1767731890338.json
```

#### Method 4: Quick Test Pattern
Click "Generate 4-Point Square Pattern" to create a simple test mission with 4 waypoints in a square pattern.

---

## 🧪 Testing Workflow

### Full Test Sequence:

1. **Check Connection**
   - Select Drone ID (1, 2, or 3)
   - Click "Check Connection"
   - Verify status shows "Connected"

2. **Load Waypoints**
   - Use any of the 4 input methods
   - Verify waypoints appear in the table
   - Check waypoint count and coordinates

3. **Upload Mission**
   - Click "📤 Upload Mission to Drone"
   - Watch debug log for upload progress
   - Verify success message: "Mission uploaded successfully"
   - Note: PyMAVLink automatically adds TAKEOFF + NAV_TO_START + RTL

4. **Start Mission** (Optional - only in simulation or with real drone)
   - Click "▶️ Start Mission (AUTO Mode)"
   - Drone will switch to AUTO mode and begin mission
   - Mission will execute: TAKEOFF → WAYPOINTS → RTL

5. **Stop Mission** (Emergency)
   - Click "⏹️ Stop Mission (RTL)"
   - Drone will stop mission and return to launch

---

## 🐛 Debug Features

### Real-Time Log
- All operations are logged with timestamps
- Color-coded messages:
  - 🔵 Blue: Info messages
  - 🟢 Green: Success messages
  - 🔴 Red: Error messages
  - 🟡 Yellow: Warning messages

### Waypoint Display
- Total waypoint count
- First and last waypoint coordinates
- Mission altitude
- Full waypoint table with all coordinates

---

## 📁 Sample Mission Planner .waypoints Format

Mission Planner exports waypoints in QGroundControl format:

```
QGC WPL 110
0	1	0	16	0	0	0	0	23.295000	85.310000	15.000000	1
1	0	0	16	0	0	0	0	23.296000	85.311000	15.000000	1
2	0	0	16	0	0	0	0	23.296000	85.312000	15.000000	1
```

Columns: `seq current frame command p1 p2 p3 p4 lat lon alt autocontinue`

---

## ✅ What Gets Uploaded to Pixhawk

When you upload a mission with N waypoints, PyMAVLink automatically constructs:

| Seq | Command | Description |
|-----|---------|-------------|
| 0 | TAKEOFF | Takeoff at current position to survey altitude |
| 1 | NAV_WAYPOINT | Navigate from takeoff to first survey waypoint |
| 2 to N+1 | NAV_WAYPOINT | Your survey waypoints |
| N+2 | RETURN_TO_LAUNCH | RTL - Return home |

**Example**: Upload 12 waypoints → Pixhawk receives 15 commands (TAKEOFF + NAV + 12 + RTL)

---

## 🔧 Troubleshooting

### Connection Failed
- Ensure PyMAVLink service is running: `python external-services/pymavlink_service.py`
- Check port 5000 is not blocked
- Verify drone is connected (check terminal output)

### Upload Failed
- Check waypoint format (lat, lon, alt fields required)
- Verify drone is connected before upload
- Check PyMAVLink service logs for details

### Parse Error
- For JSON: Validate JSON syntax
- For .waypoints: Ensure Mission Planner format
- Check file encoding (should be UTF-8)

---

## 🎯 Testing Checklist

- [ ] PyMAVLink service running
- [ ] Node.js server running  
- [ ] Debug dashboard loads successfully
- [ ] Can check drone connection
- [ ] Can paste JSON waypoints
- [ ] Can upload .waypoints file
- [ ] Can upload .json mission file
- [ ] Can generate test pattern
- [ ] Waypoints display correctly in table
- [ ] Can upload mission to drone (sees TAKEOFF + NAV + SURVEY + RTL)
- [ ] Can start mission in AUTO mode
- [ ] Can stop mission with RTL

---

## 📝 Notes

- **Simulation Mode**: If PyMAVLink is in simulation mode, uploads are simulated but logged
- **Real Hardware**: Only test with real hardware in safe environment
- **AUTO Mode**: Starting mission requires drone to be armed first
- **RTL Safety**: RTL command ensures drone always returns home after mission

---

## 🆘 Support

If you encounter issues:
1. Check both terminal windows for error messages
2. Review debug log in the dashboard
3. Verify waypoint format matches expected structure
4. Ensure all services are running on correct ports
