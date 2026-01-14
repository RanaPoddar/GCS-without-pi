# Pi Detection Service Troubleshooting Guide

## Issue: WebSocket Timeout Error

### Error Message
```
websocket._exceptions.WebSocketTimeoutException: timed out
❌ Disconnected from server
```

## Root Causes & Solutions

### 1. Network Connectivity Issues

**Check if Pi can reach the server:**
```bash
# On Raspberry Pi
ping <SERVER_IP>
curl http://<SERVER_IP>:3000
```

**Verify server is running:**
```bash
# On server machine
netstat -ano | findstr :3000  # Windows
netstat -tuln | grep :3000    # Linux
```

### 2. Firewall Blocking Connection

**Windows Firewall:**
```powershell
# Allow Node.js through firewall
netsh advfirewall firewall add rule name="Node.js Server" dir=in action=allow protocol=TCP localport=3000

# Or disable for testing
netsh advfirewall set allprofiles state off
```

**Linux Firewall (if server on Linux):**
```bash
sudo ufw allow 3000/tcp
sudo ufw reload
```

### 3. Server Configuration

**Ensure server is listening on all interfaces (0.0.0.0):**
- Check `config/config.js` has `HOST: '0.0.0.0'` ✅ (Already configured)

**Socket.IO configuration updated:**
- ✅ Increased `pingTimeout` to 120 seconds
- ✅ Added `connectTimeout` of 60 seconds
- ✅ Enabled both websocket and polling transports
- ✅ Increased buffer size for large payloads

### 4. Pi Detection Service Configuration

The Pi detection service needs to connect to: `http://<SERVER_IP>:3000`

**Connection String Format:**
```python
# In Pi detection script
SERVER_URL = 'http://192.168.1.100:3000'  # Replace with actual server IP
sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=0,  # Infinite
    reconnection_delay=1,
    reconnection_delay_max=5,
    logger=True,
    engineio_logger=True
)
```

## Testing Steps

### Step 1: Verify Server is Accessible

From the Pi:
```bash
# Test HTTP connectivity
curl -v http://<SERVER_IP>:3000/

# Test Socket.IO endpoint
curl -v http://<SERVER_IP>:3000/socket.io/?EIO=4&transport=polling
```

### Step 2: Check Server Logs

On server machine, check for connection attempts:
```bash
# Windows
Get-Content combined.log -Tail 50 -Wait

# Linux
tail -f combined.log
```

### Step 3: Test with Simple Client

Create a test script on Pi:
```python
import socketio
import time

SERVER_URL = 'http://192.168.1.100:3000'  # Replace with your server IP

sio = socketio.Client(
    logger=True,
    engineio_logger=True,
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=2
)

@sio.on('connect')
def on_connect():
    print('✅ Connected to server!')

@sio.on('disconnect')
def on_disconnect():
    print('❌ Disconnected from server')

try:
    print(f'Connecting to {SERVER_URL}...')
    sio.connect(SERVER_URL, transports=['websocket', 'polling'])
    print('Connection successful!')
    
    # Keep alive
    while True:
        time.sleep(1)
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
```

### Step 4: Network Configuration

**Find Server IP Address:**
```powershell
# Windows
ipconfig | findstr IPv4

# Linux/Mac
ip addr show | grep inet
```

**Ensure Pi and Server on Same Network:**
- Both should be on same subnet (e.g., 192.168.1.x)
- Or server should have port forwarding configured

## Common Issues

### Issue: Connection Refused
- Server not running
- Wrong port number
- Firewall blocking

### Issue: Connection Timeout
- Network unreachable
- Server behind NAT without port forwarding
- Long network latency

### Issue: Connection Drops After Connect
- Timeout settings too short ✅ (Fixed)
- Network instability
- Server overloaded

## Recommended Pi Detection Service Settings

```python
import socketio
import time
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

SERVER_URL = 'http://192.168.1.100:3000'  # UPDATE THIS!

sio = socketio.Client(
    logger=True,
    engineio_logger=True,
    reconnection=True,
    reconnection_attempts=0,      # Infinite retries
    reconnection_delay=2,          # Start with 2 second delay
    reconnection_delay_max=30,     # Max 30 seconds between attempts
    randomization_factor=0.5       # Add jitter to prevent thundering herd
)

@sio.on('connect')
def on_connect():
    print('✅ Connected to Ground Control Station')
    # Register Pi with server
    sio.emit('register_pi', {
        'pi_id': 'detection_drone_pi_pushpak',
        'type': 'detection',
        'capabilities': ['crop_detection', 'image_capture']
    })

@sio.on('disconnect')
def on_disconnect():
    print('❌ Disconnected from server - will auto-reconnect')

@sio.on('connect_error')
def on_connect_error(data):
    print(f'⚠️ Connection error: {data}')

# Send detection data
def send_detection(detection_data):
    try:
        sio.emit('crop_detection', detection_data)
        return True
    except Exception as e:
        print(f'Failed to send detection: {e}')
        return False

# Main connection
try:
    sio.connect(SERVER_URL, transports=['websocket', 'polling'])
    sio.wait()  # Keep connection alive
except KeyboardInterrupt:
    print('Shutting down...')
    sio.disconnect()
```

## Monitoring

### Server Side
Monitor connections in real-time:
```javascript
// In server.js or socketHandlersPyMAVLink.js
io.on('connection', (socket) => {
    console.log(`📱 Client connected: ${socket.id}`);
    console.log(`   IP: ${socket.handshake.address}`);
    console.log(`   Transport: ${socket.conn.transport.name}`);
});
```

### Pi Side
Check connection status:
```python
# Check if connected
if sio.connected:
    print('Connected')
else:
    print('Not connected')
```

## Quick Fix Checklist

- [ ] Server is running (`npm start` or `node server.js`)
- [ ] Server accessible from Pi (`curl http://<SERVER_IP>:3000`)
- [ ] Firewall allows port 3000
- [ ] Correct SERVER_URL in Pi detection script
- [ ] Pi and server on same network or port forwarded
- [ ] Server logs show connection attempts
- [ ] Socket.IO timeout settings increased ✅
- [ ] Both websocket and polling transports enabled ✅

## Need More Help?

1. Check server logs: `combined.log` and `error.log`
2. Run Pi test script with full debugging
3. Use Wireshark to capture network traffic
4. Check if other services can connect to port 3000
