# Raspberry Pi Detection Service Setup Guide

This guide will help you set up and troubleshoot the detection service on your Raspberry Pi.

## Prerequisites

- Raspberry Pi with Python 3.7+
- Network connectivity to GCS server
- Python virtual environment (recommended)

## Installation

### 1. Create Virtual Environment (on Pi)

```bash
cd ~
mkdir -p drone-detection
cd drone-detection

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install python-socketio[client]
pip install requests
pip install python-engineio
```

### 3. Get Server IP Address

**On your Windows GCS server machine:**

```powershell
ipconfig | findstr IPv4
```

Look for your local network IP (usually starts with 192.168.x.x or 10.x.x.x)

Example output:
```
IPv4 Address. . . . . . . . . . . : 192.168.1.100
```

## Configuration

### Update Server URL

Before running any scripts, update the `SERVER_IP` in the detection script:

```python
# In your detection script
SERVER_IP = '192.168.1.100'  # Replace with YOUR server IP!
SERVER_PORT = 3000
SERVER_URL = f'http://{SERVER_IP}:{SERVER_PORT}'
```

## Testing Connection

### Step 1: Copy Test Script to Pi

Copy the `test_pi_connection.py` file to your Raspberry Pi:

```bash
# On Pi
scp user@server:/path/to/test_pi_connection.py ~/drone-detection/
```

Or create it manually on the Pi using the content from the file.

### Step 2: Update Server IP in Test Script

Edit the script:
```bash
nano ~/drone-detection/test_pi_connection.py
```

Change this line:
```python
SERVER_IP = '192.168.1.100'  # <-- UPDATE THIS!
```

### Step 3: Run Test

```bash
cd ~/drone-detection
source venv/bin/activate
python test_pi_connection.py
```

The test will check:
1. ✅ Network connectivity (ping)
2. ✅ HTTP connectivity  
3. ✅ Socket.IO endpoint
4. ✅ Socket.IO connection and registration

### Expected Output

```
====================================================================
🔍 Pi Detection Service Connection Test
====================================================================
Server URL: http://192.168.1.100:3000
Pi ID: detection_drone_pi_pushpak
Time: 2026-01-12 10:30:00

====================================================================
Network Information
====================================================================

📍 Pi IP Address: 192.168.1.150
📍 Hostname: raspberrypi

====================================================================
1. Testing Network Connectivity
====================================================================

📡 Testing connection to 192.168.1.100...
✅ Ping successful!

====================================================================
2. Testing HTTP Connectivity
====================================================================

🌐 Testing HTTP connection to http://192.168.1.100:3000...
✅ HTTP connection successful! Status: 200

====================================================================
3. Testing Socket.IO Endpoint
====================================================================

🔌 Testing Socket.IO endpoint...
   URL: http://192.168.1.100:3000/socket.io/?EIO=4&transport=polling
✅ Socket.IO endpoint accessible! Status: 200
   Response length: 97 bytes

====================================================================
4. Testing Socket.IO Connection
====================================================================

🔗 Attempting to connect to Socket.IO server...
   Server: http://192.168.1.100:3000
   Pi ID: detection_drone_pi_pushpak

⏳ Connecting (timeout: 30 seconds)...

✅ Socket.IO connection SUCCESSFUL!
   Connection ID: abc123def456
   Transport: websocket

📝 Registering Pi with server...
   Registration message sent!

✅ Pi registered successfully!
   Data: {'pi_id': 'detection_drone_pi_pushpak', 'status': 'success'}

⏳ Testing connection stability (5 seconds)...

🧪 Sending test detection...
   Test detection sent!

🔌 Disconnecting...

====================================================================
📊 Test Summary
====================================================================

Test                           Result    
------------------------------------------------------------
network                        ✅ PASS    
http                           ✅ PASS    
socketio_endpoint              ✅ PASS    
socketio_connection            ✅ PASS    

====================================================================
✅ ALL TESTS PASSED!

Your Pi detection service should work correctly.
You can now run your main detection script.
====================================================================
```

## Troubleshooting

### Error: "Connection refused"

**Problem:** Server is not accessible

**Solutions:**
1. Verify server is running:
   ```powershell
   # On server
   node server.js
   ```

2. Check firewall:
   ```powershell
   # On Windows server
   netsh advfirewall firewall add rule name="Node.js GCS" dir=in action=allow protocol=TCP localport=3000
   ```

3. Verify server IP is correct:
   ```powershell
   ipconfig | findstr IPv4
   ```

### Error: "Connection timeout" / "timed out"

**Problem:** Network latency or timeout settings too short

**Solutions:**
1. ✅ Server timeout settings have been increased (already done)

2. Check network quality:
   ```bash
   ping -c 10 <SERVER_IP>
   ```

3. Try with polling transport only:
   ```python
   sio.connect(SERVER_URL, transports=['polling'])
   ```

### Error: "Network unreachable"

**Problem:** Pi and server on different networks

**Solutions:**
1. Ensure both on same WiFi/network
2. Use server's public IP if on different networks
3. Set up port forwarding if needed

### Server shows no connection attempts

**Problem:** Firewall blocking or wrong port

**Solutions:**
1. Check server logs:
   ```powershell
   Get-Content combined.log -Tail 50 -Wait
   ```

2. Test if port is accessible:
   ```bash
   # From Pi
   curl http://<SERVER_IP>:3000/
   ```

3. Check if server is listening:
   ```powershell
   # On server
   netstat -ano | findstr :3000
   ```

## Detection Service Template

Here's a template for your detection service:

```python
#!/usr/bin/env python3
"""
Crop Detection Service for Drone
Connects to GCS and sends detection events
"""

import socketio
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SERVER_IP = '192.168.1.100'  # UPDATE THIS!
SERVER_PORT = 3000
SERVER_URL = f'http://{SERVER_IP}:{SERVER_PORT}'
PI_ID = 'detection_drone_pi_pushpak'

# Create Socket.IO client
sio = socketio.Client(
    logger=False,
    engineio_logger=False,
    reconnection=True,
    reconnection_attempts=0,      # Infinite retries
    reconnection_delay=2,
    reconnection_delay_max=30,
    randomization_factor=0.5
)

@sio.on('connect')
def on_connect():
    logger.info('✅ Connected to Ground Control Station')
    
    # Register with server
    sio.emit('register_pi', {
        'pi_id': PI_ID,
        'type': 'detection',
        'capabilities': ['crop_detection', 'image_capture'],
        'version': '1.0.0'
    })

@sio.on('pi_registered')
def on_pi_registered(data):
    logger.info(f'✅ Pi registered: {data}')

@sio.on('disconnect')
def on_disconnect():
    logger.warning('❌ Disconnected from server - will auto-reconnect')

@sio.on('connect_error')
def on_connect_error(data):
    logger.error(f'⚠️ Connection error: {data}')

def send_detection(latitude, longitude, crop_type='unknown', confidence=0.0):
    """Send crop detection to GCS"""
    try:
        detection_data = {
            'pi_id': PI_ID,
            'detection_id': f'{PI_ID}_{int(time.time()*1000)}',
            'latitude': latitude,
            'longitude': longitude,
            'altitude': 15.0,  # Get from GPS/telemetry
            'confidence': confidence,
            'crop_type': crop_type,
            'timestamp': datetime.now().isoformat()
        }
        
        sio.emit('crop_detection', detection_data)
        logger.info(f'🌾 Detection sent: {crop_type} at ({latitude}, {longitude})')
        return True
        
    except Exception as e:
        logger.error(f'Failed to send detection: {e}')
        return False

def main():
    """Main detection loop"""
    logger.info(f'Starting Detection Service')
    logger.info(f'Server: {SERVER_URL}')
    logger.info(f'Pi ID: {PI_ID}')
    
    # Connect to server
    try:
        logger.info('Connecting to GCS...')
        sio.connect(SERVER_URL, transports=['websocket', 'polling'])
        logger.info('Connection established!')
        
        # Your detection logic here
        while True:
            # Example: send test detection every 10 seconds
            if sio.connected:
                send_detection(
                    latitude=28.4595,
                    longitude=77.0266,
                    crop_type='wheat',
                    confidence=0.95
                )
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        sio.disconnect()
    except Exception as e:
        logger.error(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
```

## Server Changes Made

The following improvements have been made to the GCS server:

### 1. Increased Socket.IO Timeouts

**File:** `config/config.js`

```javascript
SOCKET_CONFIG: {
  pingTimeout: 120000,      // 120 seconds (was 60)
  pingInterval: 25000,
  connectTimeout: 60000,    // 60 seconds (new)
  transports: ['websocket', 'polling'],
  allowUpgrades: true,
  perMessageDeflate: false,
  httpCompression: false,
  maxHttpBufferSize: 1e8    // 100MB
}
```

### 2. Added Pi Registration Handler

**File:** `socket/socketHandlersPyMAVLink.js`

- Added support for both `pi_register` and `register_pi` events
- Sends acknowledgment back to Pi with `pi_registered` event
- Logs Pi type and capabilities
- Broadcasts `pi_connected` to all clients

## Monitoring

### Server Side

Check server logs for Pi connections:
```powershell
# Windows
Get-Content combined.log -Tail 50 -Wait

# Or view in real-time
node server.js
```

Look for:
```
🥧 Raspberry Pi registered: detection_drone_pi_pushpak
   Socket ID: abc123
   Type: detection
   Capabilities: crop_detection, image_capture
```

### Pi Side

Monitor connection status:
```python
if sio.connected:
    print('Connected ✅')
else:
    print('Disconnected ❌')
```

## Quick Start Checklist

- [ ] Python virtual environment created on Pi
- [ ] Dependencies installed (`python-socketio`, `requests`)
- [ ] Server IP address obtained from Windows machine
- [ ] Server IP updated in detection script
- [ ] Test script runs successfully
- [ ] Server firewall allows port 3000
- [ ] Server is running (`node server.js`)
- [ ] Detection script connects successfully
- [ ] Detections appear in server logs

## Support

If you continue to have issues after following this guide:

1. Run the test script and save output
2. Check server logs (`combined.log`)
3. Verify network connectivity
4. Check firewall settings on both machines
5. Try with polling transport only
6. Review the troubleshooting guide: `PI_DETECTION_TROUBLESHOOTING.md`

## Files Reference

- `test_pi_connection.py` - Connection test script
- `PI_DETECTION_TROUBLESHOOTING.md` - Detailed troubleshooting guide
- `config/config.js` - Server Socket.IO configuration
- `socket/socketHandlersPyMAVLink.js` - Socket event handlers
