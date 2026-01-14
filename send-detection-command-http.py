#!/usr/bin/env python3
"""
Send detection commands via PyMAVLink Service HTTP API
Works while service is running - no need to stop it
"""

import requests
import sys

# PyMAVLink service URL
SERVICE_URL = "http://localhost:5000"

def send_detection_command(drone_id, action):
    """Send command via HTTP to pymavlink service"""
    try:
        url = f"{SERVICE_URL}/drone/{drone_id}/pi/{action}_detection"
        print(f"   POST {url}")
        
        response = requests.post(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            success = result.get('success', False)
            if not success:
                print(f"   ⚠️  Service returned: {result}")
            return success, result
        else:
            print(f"   ❌ HTTP {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data}")
            except:
                print(f"   Response: {response.text}")
            return False, None
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to PyMAVLink service at {SERVICE_URL}")
        print(f"   Is it running? Check: cd external-services && python pymavlink_service.py")
        return False, None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False, None

def main():
    drone_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    
    print(f"📡 Detection Control via HTTP API (MAVLink Commands)")
    print(f"Drone ID: {drone_id}")
    print(f"Service: {SERVICE_URL}")
    print("=" * 60)
    print("This sends MAVLink commands 42000/42001 via the running")
    print("pymavlink_service (which already has COM4 connection)")
    print("=" * 60)
    
    while True:
        print("\n1=Start Detection  2=Stop  0=Exit")
        choice = input("Choice: ").strip()
        
        if choice == "1":
            print("📡 Sending MAVLink command 42000 (Start Detection)...")
            success, result = send_detection_command(drone_id, "start")
            if success:
                print(f"✅ Detection started! ACK: {result.get('ack_result')}")
            else:
                print("❌ Failed")
                
        elif choice == "2":
            print("📡 Sending MAVLink command 42001 (Stop Detection)...")
            success, result = send_detection_command(drone_id, "stop")
            if success:
                print(f"✅ Detection stopped! ACK: {result.get('ack_result')}")
            else:
                print("❌ Failed")
                
        elif choice == "0":
            break
        else:
            print("Invalid choice")
    
    print("\n👋 Exiting...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
