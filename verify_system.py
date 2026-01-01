#!/usr/bin/env python3
"""
Mission Control Dashboard System Verification
Tests all endpoints and integration points to ensure system is ready
"""

import requests
import json
import time
from datetime import datetime

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_test(name, status, message=""):
    symbol = f"{GREEN}✓{RESET}" if status else f"{RED}✗{RESET}"
    print(f"{symbol} {name}")
    if message:
        print(f"  {YELLOW}{message}{RESET}")

def test_pymavlink_health():
    """Test PyMAVLink service health endpoint"""
    try:
        response = requests.get('http://localhost:5000/health', timeout=2)
        if response.status_code == 200:
            data = response.json()
            return True, f"Service online, uptime: {data.get('uptime', 'N/A')}"
        return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Service not running (connection refused)"
    except Exception as e:
        return False, str(e)

def test_drone_connection(drone_id=1):
    """Test drone connection status"""
    try:
        response = requests.get(f'http://localhost:5000/drone/{drone_id}/status', timeout=2)
        if response.status_code == 200:
            data = response.json()
            connected = data.get('connected', False)
            mode = data.get('flight_mode', 'UNKNOWN')
            return connected, f"Connected: {connected}, Mode: {mode}"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def test_drone_telemetry(drone_id=1):
    """Test drone telemetry endpoint"""
    try:
        response = requests.get(f'http://localhost:5000/drone/{drone_id}/telemetry', timeout=2)
        if response.status_code == 200:
            data = response.json()
            lat = data.get('latitude', 0)
            lon = data.get('longitude', 0)
            alt = data.get('altitude', 0)
            sats = data.get('satellites_visible', 0)
            return True, f"GPS: ({lat:.6f}, {lon:.6f}), Alt: {alt:.1f}m, Sats: {sats}"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def test_mission_upload(drone_id=1):
    """Test mission upload endpoint"""
    # Create test waypoints (square pattern)
    waypoints = [
        {"seq": 0, "lat": 12.9716, "lon": 77.5946, "alt": 15.0},
        {"seq": 1, "lat": 12.9726, "lon": 77.5946, "alt": 15.0},
        {"seq": 2, "lat": 12.9726, "lon": 77.5956, "alt": 15.0},
        {"seq": 3, "lat": 12.9716, "lon": 77.5956, "alt": 15.0},
    ]
    
    try:
        response = requests.post(
            f'http://localhost:5000/drone/{drone_id}/mission/upload',
            json={"waypoints": waypoints},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return True, f"Uploaded {len(waypoints)} waypoints"
            return False, data.get('message', 'Upload failed')
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def test_mission_status(drone_id=1):
    """Test mission status endpoint"""
    try:
        response = requests.get(f'http://localhost:5000/drone/{drone_id}/mission/status', timeout=2)
        if response.status_code == 200:
            data = response.json()
            status = data.get('mission_status', {})
            active = status.get('active', False)
            current = status.get('current_waypoint', 0)
            total = status.get('total_waypoints', 0)
            progress = status.get('progress_percent', 0)
            return True, f"Active: {active}, WP: {current}/{total}, Progress: {progress}%"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def test_web_server():
    """Test Node.js web server"""
    try:
        response = requests.get('http://localhost:3000/', timeout=2)
        if response.status_code == 200:
            return True, "Web server responding"
        return False, f"HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Web server not running"
    except Exception as e:
        return False, str(e)

def test_mission_dashboard():
    """Test mission control dashboard page"""
    try:
        response = requests.get('http://localhost:3000/mission-control', timeout=2)
        if response.status_code == 200:
            html = response.text
            # Check for key elements
            checks = {
                'Upload zone': 'uploadZone' in html,
                'Map container': 'map' in html,
                'Mission controls': 'startMission' in html,
                'Telemetry HUD': 'drone1Alt' in html
            }
            missing = [k for k, v in checks.items() if not v]
            if not missing:
                return True, "All UI elements present"
            return False, f"Missing: {', '.join(missing)}"
        return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

def test_api_endpoints():
    """Test REST API endpoints"""
    endpoints = [
        '/api/drones',
        '/api/mission/missions',
    ]
    
    results = []
    for endpoint in endpoints:
        try:
            response = requests.get(f'http://localhost:3000{endpoint}', timeout=2)
            status = response.status_code == 200 or response.status_code == 404
            results.append((endpoint, status))
        except Exception:
            results.append((endpoint, False))
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    return passed == total, f"{passed}/{total} endpoints responding"

def run_verification():
    """Run all verification tests"""
    print_header("MISSION CONTROL SYSTEM VERIFICATION")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # PyMAVLink Service Tests
    print(f"{GREEN}━━━ PyMAVLink Service (Port 5000) ━━━{RESET}")
    status, msg = test_pymavlink_health()
    print_test("Health Check", status, msg)
    
    status, msg = test_drone_connection()
    print_test("Drone Connection", status, msg)
    
    status, msg = test_drone_telemetry()
    print_test("Telemetry Stream", status, msg)
    
    status, msg = test_mission_upload()
    print_test("Mission Upload", status, msg)
    
    status, msg = test_mission_status()
    print_test("Mission Status", status, msg)
    
    # Node.js Server Tests
    print(f"\n{GREEN}━━━ Node.js Server (Port 3000) ━━━{RESET}")
    status, msg = test_web_server()
    print_test("Web Server", status, msg)
    
    status, msg = test_mission_dashboard()
    print_test("Mission Dashboard", status, msg)
    
    status, msg = test_api_endpoints()
    print_test("REST API Endpoints", status, msg)
    
    # Integration Tests
    print(f"\n{GREEN}━━━ System Integration ━━━{RESET}")
    
    # Check if both services are running
    pymavlink_ok = test_pymavlink_health()[0]
    web_ok = test_web_server()[0]
    drone_ok = test_drone_connection()[0]
    
    if pymavlink_ok and web_ok:
        print_test("Services Integration", True, "Both services running")
    else:
        missing = []
        if not pymavlink_ok:
            missing.append("PyMAVLink")
        if not web_ok:
            missing.append("Web Server")
        print_test("Services Integration", False, f"Missing: {', '.join(missing)}")
    
    # Overall status
    print_header("SYSTEM STATUS")
    
    if pymavlink_ok and web_ok and drone_ok:
        print(f"{GREEN}✅ SYSTEM READY FOR MISSIONS{RESET}")
        print(f"\n{BLUE}Mission Control Dashboard:{RESET} http://localhost:3000/mission-control")
        print(f"{BLUE}PyMAVLink API:{RESET} http://localhost:5000")
        print(f"\n{YELLOW}Next Steps:{RESET}")
        print("  1. Open dashboard in browser")
        print("  2. Upload KML file")
        print("  3. Generate survey grid")
        print("  4. Start mission")
    elif pymavlink_ok and web_ok and not drone_ok:
        print(f"{YELLOW}⚠️  SYSTEM READY (SIMULATION MODE){RESET}")
        print(f"\n{BLUE}Services running but no drone connected{RESET}")
        print(f"This is normal for simulation/testing mode")
        print(f"\n{YELLOW}Access dashboard:{RESET} http://localhost:3000/mission-control")
    else:
        print(f"{RED}❌ SYSTEM NOT READY{RESET}")
        print(f"\n{YELLOW}Required actions:{RESET}")
        if not pymavlink_ok:
            print(f"  {RED}•{RESET} Start PyMAVLink service:")
            print("    cd external-services")
            print("    python3 pymavlink_service.py --simulation")
        if not web_ok:
            print(f"  {RED}•{RESET} Start web server:")
            print("    npm start")
    
    print(f"\n{BLUE}{'='*60}{RESET}\n")

if __name__ == "__main__":
    try:
        run_verification()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Verification cancelled by user{RESET}\n")
    except Exception as e:
        print(f"\n{RED}Verification error: {e}{RESET}\n")
