# 🎮 Testing Without Physical Drone

## Quick Start (2 Methods)

### Method 1: Using UI Button (Easiest) ⭐
1. **Open Mission Control**: http://localhost:3000/mission-control
2. **Click the 🎮 button** next to "Drone 1" in the header
3. Wait 2 seconds - Drone status will change to "Connected"
4. **You're ready!** Upload KML and start mission

### Method 2: Using Command Line
```bash
# Connect Drone 1 in simulation mode
curl -X POST http://localhost:5000/drone/1/simulate

# Connect Drone 2 in simulation mode  
curl -X POST http://localhost:5000/drone/2/simulate
```

---

## Complete Testing Workflow

### Step 1: Start Services
```bash
# Terminal 1: Start Node.js server
npm start

# Terminal 2: Start PyMAVLink service
python3 external-services/pymavlink_service.py
```

### Step 2: Connect Simulated Drone
- Open http://localhost:3000/mission-control
- Click **🎮 button** next to "Drone 1"
- Status changes: "Disconnected" → "Connected"
- You'll see: "🎮 Drone 1 connected in SIMULATION mode"

### Step 3: Upload KML & Generate Waypoints
1. **Upload KML file**: 
   - Drag-drop KML file to upload zone
   - Or click to browse
   - Example files in `kml_files/` folder

2. **Set Parameters** (defaults are good):
   - Altitude: 15m
   - Speed: 2m/s
   - Overlap: 70%
   - Grid Angle: 0°

3. **Click "Generate Survey Grid"**
   - Waypoints will appear on map
   - "Start Mission" button will be enabled

### Step 4: Start Mission
1. **Click "Start Mission"** button
2. Mission sequence:
   - ✅ Uploads waypoints to drone
   - ✅ Arms the drone
   - ✅ Starts mission execution
   
3. **Watch the simulation**:
   - Drone marker moves on map
   - Telemetry updates in real-time
   - Battery drains slowly
   - Waypoints are followed automatically

### Step 5: Test Features
- **Manual Detection**: Click 🎯 in bottom panel to simulate crop detection
- **Pause Mission**: Click "Pause" button
- **Resume Mission**: Click "Resume" button
- **Stop Mission**: Click "Stop" (drone will RTL - Return to Launch)
- **Export Log**: Click "Export" in detection log

---

## What Gets Simulated?

### ✅ Fully Simulated
- **GPS Position**: Drone moves through waypoints
- **Altitude**: Simulated climb/descent
- **Battery**: Drains from 95% → 0%
- **Flight Mode**: Changes (STABILIZE → GUIDED → AUTO)
- **Armed Status**: Can arm/disarm
- **Mission Progress**: Waypoint navigation
- **Telemetry**: All fields update (speed, heading, etc.)

### ❌ Not Simulated
- **Camera Feed**: No video stream
- **Actual Flight**: No motors/props
- **RC Control**: No physical radio
- **GPS Accuracy**: Perfect positioning (no drift)

---

## Verification Checklist

### Before Mission Start
- [ ] PyMAVLink service running (check port 5000)
- [ ] Node.js server running (check port 3000)
- [ ] Drone shows "Connected" status
- [ ] KML file uploaded successfully
- [ ] Survey grid generated on map
- [ ] "Start Mission" button is enabled

### During Mission
- [ ] Drone marker moves on map
- [ ] Altitude increases after takeoff
- [ ] Battery percentage decreases
- [ ] Groundspeed shows ~2 m/s
- [ ] Flight mode shows "AUTO"
- [ ] Armed status is "true"

### After Mission
- [ ] Drone completes all waypoints
- [ ] Flight mode changes to "RTL" (if stopped)
- [ ] Drone returns to start position
- [ ] Mission timer shows elapsed time
- [ ] Detection log has entries (if triggered)

---

## Troubleshooting

### Problem: "Drone not connected" error when starting mission
**Solution**: 
```bash
# Check if drone is connected in PyMAVLink
curl http://localhost:5000/drones

# If empty, click 🎮 button again or run:
curl -X POST http://localhost:5000/drone/1/simulate
```

### Problem: PyMAVLink service not reachable
**Solution**:
```bash
# Check if service is running
curl http://localhost:5000/health

# If not, start it:
cd /home/ranapoddar/Documents/Nidar/GCS-without-pi
python3 external-services/pymavlink_service.py
```

### Problem: No waypoints generated
**Solution**:
- Check KML file format (should be polygon/boundary)
- Try example file: `kml_files/sample_field_boundary.kml`
- Check browser console for errors (F12)

### Problem: Mission starts but drone doesn't move
**Solution**:
- This is normal in simulation - movement is slow
- Check telemetry: altitude should increase
- Wait 5-10 seconds to see movement
- Simulation updates every 1 second

### Problem: Can't arm drone
**Solution**: In simulation, arming should always work. If it fails:
```bash
# Restart simulation
curl -X POST http://localhost:5000/drone/1/disconnect
curl -X POST http://localhost:5000/drone/1/simulate
```

---

## Advanced: Multiple Drones

### Test with 2 Drones
```bash
# Connect both drones in simulation
curl -X POST http://localhost:5000/drone/1/simulate
curl -X POST http://localhost:5000/drone/2/simulate
```

Or click both 🎮 buttons in the UI!

---

## Tips for Realistic Testing

1. **Use real field boundaries**: Upload actual KML files from Google Earth
2. **Test different parameters**: Try altitude 20m, speed 5m/s
3. **Test edge cases**: 
   - Very small fields (5m x 5m)
   - Very large fields (100m x 100m)
   - Irregular shapes
4. **Test mission control**:
   - Pause mid-flight
   - Stop and RTL
   - Manual detection triggers
5. **Check logs**: Watch browser console and terminal output

---

## Quick Commands Reference

```bash
# Health check
curl http://localhost:5000/health

# List connected drones
curl http://localhost:5000/drones

# Connect simulation
curl -X POST http://localhost:5000/drone/1/simulate

# Disconnect drone
curl -X POST http://localhost:5000/drone/1/disconnect

# Get telemetry
curl http://localhost:5000/drone/1/telemetry

# Arm drone
curl -X POST http://localhost:5000/drone/1/arm

# Start mission (after waypoints uploaded)
curl -X POST http://localhost:5000/drone/1/mission/start
```

---

## Next Steps

Once testing is complete:
1. **Hardware Testing**: Connect real Pixhawk via USB/serial
2. **Field Testing**: Test with actual drone outdoors
3. **Integration**: Add Pi for crop detection
4. **Production**: Deploy to actual agricultural operations

---

## Need Help?

- Check logs: `tail -f nohup.out`
- Browser console: Press F12 → Console tab
- Server logs: Terminal where `npm start` is running
- PyMAVLink logs: Terminal where Python service is running
