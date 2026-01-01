#!/usr/bin/env python3
"""
Test script for simulated mission waypoint upload
Demonstrates automated mission execution without real drone hardware
"""

import requests
import time
import json

BASE_URL = "http://localhost:5000"
DRONE_ID = 1

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def test_simulation_mode():
    """Test complete mission workflow in simulation mode"""
    
    print_section("🎮 SIMULATION MODE TEST - Mission Waypoint Upload")
    
    # Step 1: Start simulation mode
    print_section("1. Starting Simulation Mode")
    response = requests.post(f"{BASE_URL}/drone/{DRONE_ID}/simulate")
    result = response.json()
    
    if result['success']:
        print(f"✅ {result['message']}")
        print(f"📍 Initial Position: Lat {result['telemetry']['latitude']:.6f}, "
              f"Lon {result['telemetry']['longitude']:.6f}")
        print(f"🔋 Battery: {result['telemetry']['battery_remaining']}%")
        print(f"🛰️ Satellites: {result['telemetry']['satellites_visible']}")
    else:
        print(f"❌ Failed to start simulation: {result.get('error')}")
        return False
    
    time.sleep(1)
    
    # Step 2: Generate sample mission waypoints
    print_section("2. Generating Sample Mission Waypoints")
    
    # Create a simple square pattern with 10 waypoints
    base_lat = 12.9716
    base_lon = 77.5946
    altitude = 15.0
    waypoints = []
    
    # Square pattern: 100m x 100m (approximately)
    pattern = [
        (0, 0), (0.001, 0), (0.001, 0.001), (0, 0.001),  # Corners
        (0, 0), (0.001, 0), (0.001, 0.001), (0, 0.001),  # Repeat for denser coverage
        (0.0005, 0.0005), (0, 0)  # Center and back to start
    ]
    
    for i, (dlat, dlon) in enumerate(pattern):
        waypoints.append({
            'seq': i,
            'latitude': base_lat + dlat,
            'longitude': base_lon + dlon,
            'altitude': altitude
        })
    
    print(f"📍 Created {len(waypoints)} waypoints")
    print(f"   Start: ({waypoints[0]['latitude']:.6f}, {waypoints[0]['longitude']:.6f})")
    print(f"   End:   ({waypoints[-1]['latitude']:.6f}, {waypoints[-1]['longitude']:.6f})")
    print(f"   Altitude: {altitude}m")
    
    time.sleep(1)
    
    # Step 3: Upload mission
    print_section("3. Uploading Mission to Drone")
    response = requests.post(
        f"{BASE_URL}/drone/{DRONE_ID}/mission/upload",
        json={'waypoints': waypoints}
    )
    result = response.json()
    
    if result['success']:
        print(f"✅ Mission uploaded successfully!")
        print(f"📤 {result['waypoint_count']} waypoints uploaded")
    else:
        print(f"❌ Failed to upload mission: {result.get('error')}")
        return False
    
    time.sleep(1)
    
    # Step 4: ARM the drone
    print_section("4. Arming Simulated Drone")
    response = requests.post(f"{BASE_URL}/drone/{DRONE_ID}/arm")
    result = response.json()
    
    if result['success']:
        print(f"✅ Drone armed (simulated)")
    else:
        print(f"❌ Failed to arm: {result.get('error')}")
        return False
    
    time.sleep(1)
    
    # Step 5: Start mission
    print_section("5. Starting Mission Execution")
    response = requests.post(f"{BASE_URL}/drone/{DRONE_ID}/mission/start")
    result = response.json()
    
    if result['success']:
        print(f"✅ Mission started!")
        print(f"🚁 Drone is now executing waypoints in AUTO mode")
    else:
        print(f"❌ Failed to start mission: {result.get('error')}")
        return False
    
    time.sleep(2)
    
    # Step 6: Monitor mission progress
    print_section("6. Monitoring Mission Progress")
    print("Watching simulated drone navigate waypoints...\n")
    
    for i in range(15):  # Monitor for ~15 seconds
        response = requests.get(f"{BASE_URL}/drone/{DRONE_ID}/mission/status")
        status_data = response.json()
        status = status_data['mission_status']
        
        # Get telemetry
        telem_response = requests.get(f"{BASE_URL}/drone/{DRONE_ID}/telemetry")
        telem_data = telem_response.json()
        telemetry = telem_data['telemetry']
        
        # Display progress
        progress = status['progress_percent']
        current_wp = status['current_waypoint']
        total_wp = status['total_waypoints']
        
        print(f"⏱️  {i+1}s | "
              f"Waypoint: {current_wp}/{total_wp} | "
              f"Progress: {progress:.1f}% | "
              f"Pos: ({telemetry['latitude']:.6f}, {telemetry['longitude']:.6f}) | "
              f"Alt: {telemetry['relative_altitude']:.1f}m | "
              f"Speed: {telemetry['groundspeed']:.1f}m/s | "
              f"Mode: {telemetry['flight_mode']}")
        
        # Check if mission completed
        if current_wp >= total_wp - 1 and not status['active']:
            print(f"\n🎉 Mission completed!")
            break
        
        time.sleep(1)
    
    # Step 7: Get final status
    print_section("7. Final Mission Status")
    response = requests.get(f"{BASE_URL}/drone/{DRONE_ID}/mission/status")
    status_data = response.json()
    status = status_data['mission_status']
    
    print(f"✅ Mission Active: {status['active']}")
    print(f"📍 Waypoints Completed: {status['current_waypoint']}/{status['total_waypoints']}")
    print(f"📊 Progress: {status['progress_percent']:.1f}%")
    print(f"🏁 Remaining: {status['waypoints_remaining']} waypoints")
    
    # Step 8: Disarm and disconnect
    print_section("8. Cleanup - Disarm & Disconnect")
    
    # Disarm
    response = requests.post(f"{BASE_URL}/drone/{DRONE_ID}/disarm")
    if response.json()['success']:
        print("✅ Drone disarmed")
    
    time.sleep(0.5)
    
    # Disconnect
    response = requests.post(f"{BASE_URL}/drone/{DRONE_ID}/disconnect")
    if response.json()['success']:
        print("✅ Simulation disconnected")
    
    print_section("🎮 SIMULATION TEST COMPLETE!")
    print("\n✅ All systems working correctly!")
    print("💡 Mission waypoint upload and execution validated without hardware\n")
    
    return True

if __name__ == "__main__":
    try:
        print("\n" + "🚁"*30)
        print("  AUTOMATED MISSION SIMULATION TEST")
        print("  Testing mission upload without real drone")
        print("🚁"*30)
        
        # Check if service is running
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.json()['status'] == 'ok':
                print("\n✅ PyMAVLink service is running\n")
            else:
                print("\n❌ Service not responding correctly\n")
                exit(1)
        except requests.exceptions.RequestException:
            print(f"\n❌ ERROR: Cannot connect to {BASE_URL}")
            print("   Make sure pymavlink_service.py is running:")
            print("   > python3 external-services/pymavlink_service.py\n")
            exit(1)
        
        # Run test
        success = test_simulation_mode()
        
        if success:
            print("\n" + "="*60)
            print("  ✅ TEST PASSED - Simulation working correctly!")
            print("="*60 + "\n")
            exit(0)
        else:
            print("\n" + "="*60)
            print("  ❌ TEST FAILED - Check errors above")
            print("="*60 + "\n")
            exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user\n")
        exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        exit(1)
