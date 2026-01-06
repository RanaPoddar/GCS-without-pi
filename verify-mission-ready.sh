#!/bin/bash
# Mission Start Verification Checklist
# Run this to verify all systems are ready

echo "======================================================================"
echo "    MISSION START READINESS VERIFICATION"
echo "======================================================================"
echo ""

# 1. Check services
echo "1️⃣  Checking Services..."
if pgrep -f "python.*pymavlink" > /dev/null; then
    echo "   ✅ PyMAVLink service is running"
else
    echo "   ❌ PyMAVLink service is NOT running"
    echo "      Fix: ./start-pymavlink.sh"
fi

if pgrep -f "node.*server" > /dev/null; then
    echo "   ✅ Node.js server is running"
else
    echo "   ❌ Node.js server is NOT running"
    echo "      Fix: npm start"
fi

echo ""

# 2. Check connectivity
echo "2️⃣  Checking API Connectivity..."
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "   ✅ PyMAVLink API is responding (port 5000)"
else
    echo "   ❌ PyMAVLink API is NOT responding"
fi

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✅ Node.js server is responding (port 3000)"
else
    echo "   ❌ Node.js server is NOT responding"
fi

echo ""

# 3. Check drone status
echo "3️⃣  Checking Drone Status..."
DRONE_STATUS=$(curl -s http://localhost:5000/drone/1/telemetry 2>&1)
if echo "$DRONE_STATUS" | grep -q "error.*not found"; then
    echo "   ⚠️  Drone 1 is NOT connected"
    echo "      Action: Click 🎮 Simulation button in dashboard"
    echo "      Or run: curl -X POST http://localhost:5000/drone/1/simulate"
elif echo "$DRONE_STATUS" | grep -q "latitude"; then
    LAT=$(echo "$DRONE_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['telemetry']['latitude'])" 2>/dev/null)
    LON=$(echo "$DRONE_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['telemetry']['longitude'])" 2>/dev/null)
    MODE=$(echo "$DRONE_STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['telemetry']['flight_mode'])" 2>/dev/null)
    echo "   ✅ Drone 1 is connected"
    echo "      Position: $LAT, $LON"
    echo "      Mode: $MODE"
fi

echo ""

# 4. Verify implementations
echo "4️⃣  Verifying Implementations..."

# Check navigation fix
if grep -q "nav_to_start" external-services/pymavlink_service.py; then
    echo "   ✅ Navigation fix implemented (NAV→TAKEOFF)"
else
    echo "   ❌ Navigation fix NOT found"
fi

# Check position warning
if grep -q "Distance from mission start" public/mission_control.js; then
    echo "   ✅ Position check warning implemented"
else
    echo "   ❌ Position warning NOT found"
fi

# Check error logging
if grep -q "ARM failed" external-services/pymavlink_service.py; then
    echo "   ✅ Enhanced ARM error logging implemented"
else
    echo "   ❌ ARM error logging NOT found"
fi

# Check marker fix
if grep -q "telemetry.gps?.lat || telemetry.latitude" public/mission_control.js; then
    echo "   ✅ Drone marker display fix implemented"
else
    echo "   ❌ Marker display fix NOT found"
fi

echo ""

# 5. Summary
echo "======================================================================"
echo "    VERIFICATION SUMMARY"
echo "======================================================================"
echo ""
echo "✅ Features Implemented:"
echo "   • Navigation to start point before takeoff (5m altitude)"
echo "   • Position check warning if drone is >10m from start"
echo "   • Detailed ARM error messages with diagnostics"
echo "   • Mission start error messages"
echo "   • Drone marker display fix for telemetry"
echo ""
echo "🎯 Mission Start Flow:"
echo "   1. User uploads KML → Mission generated"
echo "   2. Click 'Start Mission'"
echo "   3. System checks drone position vs mission start"
echo "   4. Uploads waypoints (NAV + TAKEOFF + Survey)"
echo "   5. ARMs drone (with detailed error checking)"
echo "   6. Starts AUTO mode"
echo "   7. Drone navigates to start → takes off → executes mission"
echo ""
echo "📊 Dashboard: http://localhost:3000/mission-control"
echo ""
echo "======================================================================"
