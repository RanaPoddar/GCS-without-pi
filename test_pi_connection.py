#!/usr/bin/env python3
"""
Test script for Pi Detection Service connection to GCS
Run this on the Raspberry Pi to test connectivity
"""

import socketio
import time
import sys
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
# UPDATE THIS WITH YOUR SERVER IP ADDRESS!
SERVER_IP = '192.168.1.100'  # <-- CHANGE THIS!
SERVER_PORT = 3000
SERVER_URL = f'http://{SERVER_IP}:{SERVER_PORT}'
# ======================================================

PI_ID = 'detection_drone_pi_pushpak'

def test_network_connectivity():
    """Test basic network connectivity to server"""
    print("\n" + "="*60)
    print("1. Testing Network Connectivity")
    print("="*60)
    
    # Test ping
    print(f"\n📡 Testing connection to {SERVER_IP}...")
    import subprocess
    try:
        # Ping test
        result = subprocess.run(
            ['ping', '-c', '3', SERVER_IP],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ Ping successful!")
        else:
            print("❌ Ping failed!")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"⚠️ Could not test ping: {e}")
    
    return True

def test_http_connectivity():
    """Test HTTP connectivity to server"""
    print("\n" + "="*60)
    print("2. Testing HTTP Connectivity")
    print("="*60)
    
    # Test basic HTTP
    print(f"\n🌐 Testing HTTP connection to {SERVER_URL}...")
    try:
        response = requests.get(SERVER_URL, timeout=10)
        print(f"✅ HTTP connection successful! Status: {response.status_code}")
        return True
    except requests.exceptions.Timeout:
        print("❌ HTTP request timed out!")
        print("   → Server may not be running or firewall is blocking")
        return False
    except requests.exceptions.ConnectionError as e:
        print("❌ Connection refused!")
        print(f"   → Error: {e}")
        print("   → Make sure server is running and accessible")
        return False
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")
        return False

def test_socketio_endpoint():
    """Test Socket.IO endpoint specifically"""
    print("\n" + "="*60)
    print("3. Testing Socket.IO Endpoint")
    print("="*60)
    
    socketio_url = f"{SERVER_URL}/socket.io/?EIO=4&transport=polling"
    print(f"\n🔌 Testing Socket.IO endpoint...")
    print(f"   URL: {socketio_url}")
    
    try:
        response = requests.get(socketio_url, timeout=10)
        print(f"✅ Socket.IO endpoint accessible! Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response length: {len(response.content)} bytes")
            return True
        else:
            print(f"   ⚠️ Unexpected status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Socket.IO endpoint test failed: {e}")
        return False

def test_socketio_connection():
    """Test actual Socket.IO connection"""
    print("\n" + "="*60)
    print("4. Testing Socket.IO Connection")
    print("="*60)
    
    print(f"\n🔗 Attempting to connect to Socket.IO server...")
    print(f"   Server: {SERVER_URL}")
    print(f"   Pi ID: {PI_ID}")
    
    # Create Socket.IO client with recommended settings
    sio = socketio.Client(
        logger=True,
        engineio_logger=True,
        reconnection=False,  # Disable for testing
    )
    
    connection_successful = False
    
    @sio.on('connect')
    def on_connect():
        nonlocal connection_successful
        connection_successful = True
        print("\n✅ Socket.IO connection SUCCESSFUL!")
        print(f"   Connection ID: {sio.sid}")
        print(f"   Transport: {sio.connection().transport()}")
        
        # Register Pi
        print("\n📝 Registering Pi with server...")
        sio.emit('register_pi', {
            'pi_id': PI_ID,
            'type': 'detection',
            'capabilities': ['crop_detection', 'image_capture'],
            'timestamp': datetime.now().isoformat()
        })
        print("   Registration message sent!")
    
    @sio.on('disconnect')
    def on_disconnect():
        print("\n❌ Disconnected from server")
    
    @sio.on('connect_error')
    def on_connect_error(data):
        print(f"\n❌ Connection error: {data}")
    
    @sio.on('pi_registered')
    def on_pi_registered(data):
        print(f"\n✅ Pi registered successfully!")
        print(f"   Data: {data}")
    
    # Try to connect
    try:
        print("\n⏳ Connecting (timeout: 30 seconds)...")
        sio.connect(
            SERVER_URL, 
            transports=['websocket', 'polling'],
            wait_timeout=30
        )
        
        # Wait a bit to receive messages
        print("\n⏳ Testing connection stability (5 seconds)...")
        time.sleep(5)
        
        # Send test detection
        if sio.connected:
            print("\n🧪 Sending test detection...")
            test_detection = {
                'pi_id': PI_ID,
                'detection_id': f'test_{int(time.time())}',
                'latitude': 28.4595,
                'longitude': 77.0266,
                'altitude': 15.0,
                'confidence': 0.95,
                'crop_type': 'wheat',
                'timestamp': datetime.now().isoformat()
            }
            sio.emit('crop_detection', test_detection)
            print("   Test detection sent!")
            time.sleep(2)
        
        # Disconnect
        print("\n🔌 Disconnecting...")
        sio.disconnect()
        
        return connection_successful
        
    except socketio.exceptions.ConnectionError as e:
        print(f"\n❌ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_network_info():
    """Print network information"""
    print("\n" + "="*60)
    print("Network Information")
    print("="*60)
    
    import socket
    
    # Get Pi's IP address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        pi_ip = s.getsockname()[0]
        s.close()
        print(f"\n📍 Pi IP Address: {pi_ip}")
    except:
        print("\n⚠️ Could not determine Pi IP address")
    
    # Get hostname
    try:
        hostname = socket.gethostname()
        print(f"📍 Hostname: {hostname}")
    except:
        pass

def main():
    """Run all connectivity tests"""
    print("\n" + "="*60)
    print("🔍 Pi Detection Service Connection Test")
    print("="*60)
    print(f"Server URL: {SERVER_URL}")
    print(f"Pi ID: {PI_ID}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Print network info
    print_network_info()
    
    # Run tests
    results = {}
    
    results['network'] = test_network_connectivity()
    results['http'] = test_http_connectivity()
    results['socketio_endpoint'] = test_socketio_endpoint()
    results['socketio_connection'] = test_socketio_connection()
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    print(f"\n{'Test':<30} {'Result':<10}")
    print("-" * 60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30} {status:<10}")
    
    # Overall result
    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("\nYour Pi detection service should work correctly.")
        print("You can now run your main detection script.")
    else:
        print("❌ SOME TESTS FAILED!")
        print("\nTroubleshooting steps:")
        
        if not results['network']:
            print("\n1. Network connectivity failed:")
            print("   → Check if Pi and server are on same network")
            print("   → Verify SERVER_IP is correct")
            print("   → Check network cables/WiFi connection")
        
        if not results['http']:
            print("\n2. HTTP connectivity failed:")
            print("   → Make sure Node.js server is running")
            print("   → Check firewall settings on server")
            print("   → Run 'node server.js' on server machine")
        
        if not results['socketio_endpoint']:
            print("\n3. Socket.IO endpoint failed:")
            print("   → Server may not have Socket.IO properly configured")
            print("   → Check server logs for errors")
        
        if not results['socketio_connection']:
            print("\n4. Socket.IO connection failed:")
            print("   → Check server logs: tail -f combined.log")
            print("   → Verify Socket.IO configuration in config/config.js")
            print("   → Check for timeout settings")
    
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
