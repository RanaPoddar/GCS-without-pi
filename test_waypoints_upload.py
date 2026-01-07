#!/usr/bin/env python3
"""
Test uploading .waypoints file directly to Pixhawk
"""
import requests
import sys

def upload_waypoints_file(drone_id, waypoints_file_path):
    """Upload .waypoints file to drone via PyMAVLink service"""
    
    # Read .waypoints file
    with open(waypoints_file_path, 'r') as f:
        waypoints_content = f.read()
    
    print(f"📄 Read .waypoints file: {waypoints_file_path}")
    print(f"   Content length: {len(waypoints_content)} bytes")
    print(f"   Lines: {len(waypoints_content.splitlines())}")
    
    # Upload to PyMAVLink service
    url = f'http://localhost:5000/drone/{drone_id}/mission/upload_waypoints_file'
    
    payload = {
        'waypoints_file_content': waypoints_content
    }
    
    print(f"\n📤 Uploading to drone {drone_id}...")
    print(f"   URL: {url}")
    
    response = requests.post(url, json=payload, timeout=60)
    
    print(f"\n📥 Response:")
    print(f"   Status: {response.status_code}")
    print(f"   Data: {response.json()}")
    
    if response.status_code == 200 and response.json().get('success'):
        print(f"\n✅ SUCCESS! Mission uploaded from .waypoints file")
        return True
    else:
        print(f"\n❌ FAILED! {response.json().get('error', 'Unknown error')}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_waypoints_upload.py <waypoints_file> [drone_id]")
        print("Example: python test_waypoints_upload.py data/kml_uploads/mission_1767792270719.waypoints 1")
        sys.exit(1)
    
    waypoints_file = sys.argv[1]
    drone_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    
    success = upload_waypoints_file(drone_id, waypoints_file)
    sys.exit(0 if success else 1)
