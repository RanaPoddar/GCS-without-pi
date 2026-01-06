#!/bin/bash

# Mission Start Connectivity Test
# Tests all components needed for mission start to work

echo "=========================================="
echo "MISSION START CONNECTIVITY TEST"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0
PASSED=0

# Test 1: Check if PyMAVLink service is running
echo "[1] Checking PyMAVLink Service (port 5000)..."
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✓ PyMAVLink service is RUNNING${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ PyMAVLink service is NOT RUNNING${NC}"
    echo "  Start it with: ./start-pymavlink.sh"
    ((FAILED++))
fi
echo ""

# Test 2: Check if Node.js server is running
echo "[2] Checking Node.js Server (port 3000)..."
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Node.js server is RUNNING${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ Node.js server is NOT RUNNING${NC}"
    echo "  Start it with: npm start or node server.js"
    ((FAILED++))
fi
echo ""

# Test 3: Check PyMAVLink API connectivity
echo "[3] Testing PyMAVLink API Connectivity..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/drones 2>/dev/null)
if [ "$RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ PyMAVLink API is RESPONSIVE (HTTP ${RESPONSE})${NC}"
    ((PASSED++))
elif [ "$RESPONSE" = "000" ]; then
    echo -e "${RED}✗ Cannot connect to PyMAVLink (Connection refused)${NC}"
    echo "  Make sure: python external-services/pymavlink_service.py"
    ((FAILED++))
else
    echo -e "${YELLOW}⚠ PyMAVLink API responded with HTTP ${RESPONSE}${NC}"
    ((PASSED++))
fi
echo ""

# Test 4: Check drone connection status
echo "[4] Checking Drone Connection Status..."
DRONE_RESPONSE=$(curl -s http://localhost:5000/drones 2>/dev/null)
echo "Response: $DRONE_RESPONSE"
if echo "$DRONE_RESPONSE" | grep -q "drone_id"; then
    echo -e "${GREEN}✓ Drone list received${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ No drone data received${NC}"
    echo "  PyMAVLink may not have connected to drone yet"
    ((FAILED++))
fi
echo ""

# Test 5: Check ARM endpoint
echo "[5] Testing ARM Endpoint (will not actually arm)..."
ARM_TEST=$(curl -s -X POST http://localhost:5000/drone/1/arm -H "Content-Type: application/json" 2>/dev/null)
if [ -z "$ARM_TEST" ]; then
    echo -e "${RED}✗ ARM endpoint did not respond${NC}"
    echo "  PyMAVLink service may be down"
    ((FAILED++))
else
    echo -e "${GREEN}✓ ARM endpoint is RESPONSIVE${NC}"
    echo "  Response: $ARM_TEST"
    ((PASSED++))
fi
echo ""

# Test 6: Check mission upload endpoint
echo "[6] Testing Mission Upload Endpoint..."
UPLOAD_TEST=$(curl -s -X POST http://localhost:5000/drone/1/mission/upload \
    -H "Content-Type: application/json" \
    -d '{"waypoints":[]}' 2>/dev/null)
if [ -z "$UPLOAD_TEST" ]; then
    echo -e "${RED}✗ Mission upload endpoint did not respond${NC}"
    ((FAILED++))
else
    echo -e "${GREEN}✓ Mission upload endpoint is RESPONSIVE${NC}"
    echo "  Response: $UPLOAD_TEST"
    ((PASSED++))
fi
echo ""

# Test 7: Check mission start endpoint
echo "[7] Testing Mission Start Endpoint..."
START_TEST=$(curl -s -X POST http://localhost:5000/drone/1/mission/start 2>/dev/null)
if [ -z "$START_TEST" ]; then
    echo -e "${RED}✗ Mission start endpoint did not respond${NC}"
    ((FAILED++))
else
    echo -e "${GREEN}✓ Mission start endpoint is RESPONSIVE${NC}"
    echo "  Response: $START_TEST"
    ((PASSED++))
fi
echo ""

# Test 8: Check Node.js API
echo "[8] Testing Node.js API (localhost:3000)..."
NODE_TEST=$(curl -s http://localhost:3000/api/drones 2>/dev/null)
if [ -z "$NODE_TEST" ]; then
    echo -e "${RED}✗ Node.js API did not respond${NC}"
    ((FAILED++))
else
    echo -e "${GREEN}✓ Node.js API is RESPONSIVE${NC}"
    ((PASSED++))
fi
echo ""

# Summary
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo -e "${GREEN}PASSED: $PASSED${NC}"
echo -e "${RED}FAILED: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All systems ready for mission start!${NC}"
    exit 0
else
    echo -e "${RED}Some systems are not ready. Fix the issues above.${NC}"
    echo ""
    echo "Common issues:"
    echo "1. PyMAVLink not running:"
    echo "   → cd /home/ranapoddar/Documents/Nidar/GCS-without-pi"
    echo "   → ./start-pymavlink.sh"
    echo ""
    echo "2. Node.js server not running:"
    echo "   → npm start"
    echo ""
    echo "3. Drone not connected to PyMAVLink:"
    echo "   → Check terminal running PyMAVLink service"
    echo "   → Verify serial port (DRONE1_PORT env variable)"
    echo "   → Check baud rate (DRONE1_BAUD env variable)"
    echo ""
    exit 1
fi
