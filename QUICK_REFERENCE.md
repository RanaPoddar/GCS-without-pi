# Mission Start - Quick Reference Card

## ⚡ Quick Commands

### Check System Status
```bash
./test-mission-connectivity.sh
```

### Start Services
```bash
# PyMAVLink Service
./start-pymavlink.sh

# Node.js Server
npm start
```

### Check Drone Connection
```bash
curl -s http://localhost:5000/drones | python -m json.tool
```

---

## 🚦 Mission Start Flow

```
1. Upload KML file
   ↓
2. Generate survey grid
   ↓
3. Click "Start Mission"
   ↓
4. Watch alerts:
   📤 Uploading waypoints...
   ✅ Waypoints uploaded
   🔧 Arming drone...
   ✅ Drone armed
   🚀 Starting mission...
   ✅ Mission ACTIVE!
```

---

## ❌ Error Messages & Solutions

### "PyMAVLink Service Unreachable!"
**Fix:** `./start-pymavlink.sh`

### "Drone not connected"
**Fix:** Check serial port, verify `.env` settings, restart PyMAVLink

### "Failed to ARM - GPS: No Fix"
**Fix:** Wait for GPS lock (8+ satellites)

### "Failed to ARM - Battery low"
**Fix:** Charge battery to >10.5V

### "Failed to start mission"
**Fix:** Check drone armed, verify GPS lock, check battery

---

## 📊 System Messages Panel

Watch the bottom panel on dashboard for real-time alerts:
- ✅ Green = Success
- ⚠️ Yellow = Warning
- ❌ Red = Error
- 📍 Blue = Information

---

## 🔍 Troubleshooting Steps

1. Run: `./test-mission-connectivity.sh`
2. Read the error alert carefully
3. Check "System Messages" console
4. Follow instructions in error message
5. Restart services if needed
6. Try mission start again

---

## 📝 Files to Check

- **Frontend code:** `public/mission_control.js`
- **Backend API:** `external-services/pymavlink_service.py`
- **Diagnostics:** `./test-mission-connectivity.sh`
- **Docs:** `docs/MISSION_START_ALERTS_SUMMARY.md`

---

## 🎯 Pre-Flight Checklist

Before starting mission:

- [ ] PyMAVLink service running (port 5000)
- [ ] Node.js server running (port 3000)
- [ ] Drone connected (check `/drones` endpoint)
- [ ] GPS lock (8+ satellites)
- [ ] Battery charged (>10.5V)
- [ ] Mission uploaded successfully
- [ ] Test script passed: `./test-mission-connectivity.sh`

---

## 💡 Tips

- **Always run diagnostic test first**: `./test-mission-connectivity.sh`
- **Wait for GPS lock**: 1-2 minutes after power on
- **Check alerts panel**: Bottom of dashboard for real-time status
- **Use browser console**: F12 → Console for detailed logs
- **Read error messages**: They contain specific solutions

---

## 📞 Need Help?

1. Check: `docs/MISSION_START_TROUBLESHOOTING.md`
2. Run: `./test-mission-connectivity.sh`
3. Check browser console (F12)
4. Check PyMAVLink service logs
5. Verify drone hardware (GPS, battery, connections)
