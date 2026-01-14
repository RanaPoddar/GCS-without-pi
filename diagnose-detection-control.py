#!/usr/bin/env python3
"""
Diagnostic Tool: Check MAVLink Detection Control Setup
Tests both GCS and Pi sides
"""

import requests
import sys

SERVICE_URL = "http://localhost:5000"

def check_gcs_service():
    """Check if GCS pymavlink service is running and connected"""
    print("\n" + "="*60)
    print("GCS SIDE CHECK")
    print("="*60)
    
    try:
        # Check service is alive
        response = requests.get(f"{SERVICE_URL}/drones", timeout=5)
        if response.status_code == 200:
            drones = response.json().get('drones', [])
            print(f"✅ PyMAVLink service running")
            print(f"✅ {len(drones)} drone(s) connected")
            
            for drone in drones:
                drone_id = drone['drone_id']
                connected = drone['connected']
                port = drone['port']
                print(f"\n   Drone {drone_id}:")
                print(f"      Port: {port}")
                print(f"      Connected: {'✅ Yes' if connected else '❌ No'}")
                
                if connected:
                    # Get telemetry
                    telem_resp = requests.get(f"{SERVICE_URL}/drone/{drone_id}/telemetry")
                    if telem_resp.status_code == 200:
                        telem = telem_resp.json()
                        print(f"      Flight Mode: {telem.get('telemetry', {}).get('flight_mode')}")
                        print(f"      GPS: {telem.get('telemetry', {}).get('satellites_visible')} sats")
                        print(f"      Battery: {telem.get('telemetry', {}).get('battery_remaining')}%")
            
            return True, drones
        else:
            print(f"❌ Service returned HTTP {response.status_code}")
            return False, []
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to {SERVICE_URL}")
        print(f"   PyMAVLink service not running")
        return False, []
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, []

def test_detection_command(drone_id):
    """Test sending detection command and analyze result"""
    print("\n" + "="*60)
    print("DETECTION COMMAND TEST")
    print("="*60)
    
    print(f"\n📡 Sending START DETECTION command (42000) to Drone {drone_id}...")
    
    try:
        response = requests.post(
            f"{SERVICE_URL}/drone/{drone_id}/pi/start_detection",
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            success = result.get('success', False)
            ack_result = result.get('ack_result', -1)
            
            # Decode ACK result
            ack_meanings = {
                0: "MAV_RESULT_ACCEPTED - ✅ Command accepted!",
                1: "MAV_RESULT_TEMPORARILY_REJECTED - ⏳ Try again later",
                2: "MAV_RESULT_DENIED - ❌ Command denied by flight controller",
                3: "MAV_RESULT_UNSUPPORTED - ❌ Command not supported/recognized",
                4: "MAV_RESULT_FAILED - ❌ Command execution failed",
                5: "MAV_RESULT_IN_PROGRESS - ⏳ Command being executed",
                6: "MAV_RESULT_CANCELLED - ❌ Command cancelled"
            }
            
            ack_text = ack_meanings.get(ack_result, f"Unknown result ({ack_result})")
            
            print(f"\nResult: {ack_text}")
            
            if ack_result == 0:
                print("\n🎉 SUCCESS! Detection command accepted by Pi")
                print("   Pi should now be detecting yellow crops")
                return True
            elif ack_result == 3:
                print("\n❌ UNSUPPORTED: Pi doesn't recognize command 42000")
                print("\n💡 This means:")
                print("   1. Pi is NOT running pi_controller.py, OR")
                print("   2. Pi command listener not initialized, OR")
                print("   3. Pi is using different command IDs")
                print("\n📋 On Pi, run:")
                print("   cd /home/pi/rpi-connect")
                print("   source venv/bin/activate")
                print("   python3 pi_controller.py")
                print("\n   Look for: '📡 MAVLink command handler registered (42000/42001)'")
                return False
            else:
                print(f"\n⚠️  Unexpected result: {ack_text}")
                print("\n💡 Check Pi logs for errors")
                return False
        else:
            print(f"❌ HTTP {response.status_code}")
            error = response.json() if response.content else response.text
            print(f"   {error}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("="*60)
    print("MAVLink Detection Control Diagnostic")
    print("="*60)
    
    # Check GCS
    gcs_ok, drones = check_gcs_service()
    
    if not gcs_ok or not drones:
        print("\n❌ Cannot proceed - GCS service not available")
        print("\n💡 Start it with:")
        print("   cd external-services")
        print("   python pymavlink_service.py")
        return
    
    # Test command with first connected drone
    connected_drones = [d for d in drones if d['connected']]
    if connected_drones:
        drone_id = connected_drones[0]['drone_id']
        test_detection_command(drone_id)
    else:
        print("\n❌ No drones connected")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("\nFor detection to work, you need:")
    print("1. ✅ PyMAVLink service running (COM4 connected)")
    print("2. ✅ Radio link active (drone telemetry visible)")
    print("3. ⚠️  Pi running pi_controller.py with command listener")
    print("\nIf command shows 'UNSUPPORTED', the Pi is not listening.")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
