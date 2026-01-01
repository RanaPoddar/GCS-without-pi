# 🚁 Ground Control Station with PyMAVLink

A comprehensive Ground Control Station for controlling drones with modular architecture, featuring PyMAVLink integration, live telemetry, autonomous mission planning, and real-time detection tracking.

## 🎯 Quick Start

### Using PyMAVLink (Recommended)

```bash
# Install dependencies
pip3 install -r external-services/requirements.txt
npm install

# Start everything
./start-pymavlink.sh

# Open dashboard
# http://localhost:3000/mission-control
```

### Manual Start

```bash
# Terminal 1: Start PyMAVLink service
python3 external-services/pymavlink_service.py

# Terminal 2: Start Node.js server
node server.js
```

## 📁 Project Structure

```
GCS-without-pi/
├── config/                    # Configuration files
│   ├── config.js             # Central configuration
│   └── logger.js             # Winston logger setup
├── services/                  # Business logic services
│   ├── missionService.js     # Mission management
│   ├── waypointService.js    # Waypoint handling
│   ├── pixhawkService.js     # Node-mavlink (legacy)
│   └── pixhawkServicePyMAVLink.js  # PyMAVLink integration
├── routes/                    # Express API routes
│   ├── droneRoutes.js        # Drone endpoints
│   ├── missionRoutes.js      # Mission endpoints
│   └── waypointRoutes.js     # Waypoint endpoints
├── socket/                    # Socket.IO handlers
│   ├── socketHandlers.js     # Node-mavlink handlers
│   └── socketHandlersPyMAVLink.js  # PyMAVLink handlers
├── external-services/         # External services (Python, etc.)
│   ├── pymavlink_service.py  # PyMAVLink Flask API
│   └── requirements.txt      # Python dependencies
├── public/                    # Frontend files
│   ├── mission_control.html  # Main dashboard
│   ├── mission_control.js    # Dashboard logic
│   └── ...
├── docs/                      # Documentation
├── data/                      # Runtime data (missions, waypoints)
└── server.js                 # Main Node.js entry point
```

## ✨ Features

## ✨ Features

### 🚀 Mission Control Dashboard
- 🗺️ **Interactive Map**: Real-time position tracking for multiple drones
- 📋 **KML Mission Planning**: Upload boundaries, generate survey grids
- 🎮 **Mission Control**: Start, pause, stop, and monitor missions
- 📊 **Live Telemetry**: Comprehensive status for each drone
- 🎯 **Detection Tracking**: View all crop detections on map
- 🌑 **Dark Modern UI**: Professional interface with real-time updates

### 🚁 Flight Control (PyMAVLink)
- **MAVLink Communication**: Official PyMAVLink library for reliable control
- **Basic Commands**: ARM, DISARM, Takeoff, Land, RTL
- **Flight Modes**: GUIDED, AUTO, LOITER, STABILIZE, and more
- **Autonomous Missions**: Upload and execute waypoint-based missions
- **Manual Navigation**: Fly to specific GPS coordinates
- **Real-time Telemetry**: GPS, altitude, battery, attitude at 4Hz

### 🛡️ Safety & Monitoring
- **Connection Health**: Automatic reconnection on failures
- **Telemetry Validation**: Check GPS, battery, and system status
- **Emergency Procedures**: Return to Launch, Emergency Land
- **Mission Data Logging**: Complete telemetry logs and CSV export

### 📍 Mission Management
- Mark waypoints during flight
- Create missions from marked waypoints
- KML boundary import for survey missions
- Store and retrieve mission history
- Detection image capture and storage

### 🏗️ Modular Architecture
- **Separation of Concerns**: Config, services, routes, sockets
- **External Services**: Python services in dedicated folder
- **Easy Testing**: SITL support for simulation
- **Scalable**: Add new services without touching core code

## 📦 Installation

### Prerequisites

- **Node.js** >= 16.x
- **Python** >= 3.7
- **npm** or **yarn**

### Quick Install

```bash
# Clone repository
git clone <repository-url>
cd GCS-without-pi

# Install Node.js dependencies
npm install

# Install Python dependencies (for PyMAVLink)
pip3 install -r external-services/requirements.txt
```

### Configuration

Set drone serial ports via environment variables or edit [config/config.js](config/config.js):

```bash
# Environment variables
export DRONE1_PORT="/dev/ttyUSB0"
export DRONE1_BAUD="57600"
export DRONE2_PORT="/dev/ttyUSB1"
export DRONE2_BAUD="57600"
```

## 🚀 Usage

### Option 1: Automated Start (Recommended)

```bash
./start-pymavlink.sh
```

This starts:
- PyMAVLink service on port 5000
- Node.js GCS on port 3000
- Auto-reconnect on failures

### Option 2: Manual Start

```bash
# Terminal 1: PyMAVLink Service
python3 external-services/pymavlink_service.py

# Terminal 2: Node.js Server
node server.js
```

### Access Dashboards

- **Mission Control**: http://localhost:3000/mission-control
- **Landing Page**: http://localhost:3000
- **Legacy Dashboard**: http://localhost:3000/legacy
- **PyMAVLink API**: http://localhost:5000/health

## 📡 API Endpoints

### Node.js REST API (Port 3000)

#### Drones
```http
GET  /api/drones              # List all drones
GET  /api/drone/:id/stats     # Get drone statistics
POST /api/drone/:id/command   # Send command (legacy)
```

#### Missions
```http
GET  /api/missions                      # List all missions
GET  /api/missions/:id                  # Get mission details
GET  /api/missions/:id/detections       # Get mission detections
POST /api/mission/upload_kml            # Upload KML for mission planning
POST /api/mission/:id/start             # Start a mission
```

#### Waypoints
```http
GET    /api/waypoints           # Get all waypoints
GET    /api/waypoints/recent    # Get recent waypoints
DELETE /api/waypoints/:id       # Delete waypoint
DELETE /api/waypoints           # Clear all waypoints
```

### PyMAVLink API (Port 5000)

#### Connection
```http
GET  /health                    # Health check
GET  /drones                    # List all drones
POST /drone/:id/connect         # Connect to drone
POST /drone/:id/disconnect      # Disconnect
GET  /drone/:id/telemetry       # Get telemetry
```

#### Commands
```http
POST /drone/:id/arm             # Arm motors
POST /drone/:id/disarm          # Disarm motors
POST /drone/:id/mode            # Set flight mode
POST /drone/:id/takeoff         # Takeoff
POST /drone/:id/land            # Land
POST /drone/:id/rtl             # Return to launch
POST /drone/:id/goto            # Goto waypoint
```

### Socket.IO Events

#### Client → Server
    pi_id: "pi_001",
    command: "camera_test",
    args: {}
  }
  ```
- `start_stream` - Start video stream from Pi
  ```javascript
  {
    pi_id: "pi_001",
    settings: {
      resolution: [640, 480],
      framerate: 30
    }
  }
  ```
- `stop_stream` - Stop video stream
- `request_stats` - Request system statistics

#### Server → Client

- `pi_list` - List of connected Pis
- `pi_connected` - New Pi connected
- `pi_disconnected` - Pi disconnected
- `pi_stats_update` - Updated system statistics
- `video_frame` - Video frame data (Base64 JPEG)
- `command_response` - Result of command execution
- `stream_update` - Stream status update

## Configuration

### Server Configuration

Edit `.env` file:
```env
PORT=3000
NODE_ENV=production
```

### Pi Configuration

Each Pi should have a unique ID set in its config:
```json
{
  "server_url": "http://YOUR_SERVER_IP:3000",
  "pi_id": "pi_001"
}
```

## Deployment

### Production Deployment

1. **Using PM2 (Recommended):**
   ```bash
   npm install -g pm2
   pm2 start server.js --name rpi-streaming
   pm2 save
   pm2 startup
   ```

2. **Using systemd:**
   ```bash
   sudo nano /etc/systemd/system/rpi-streaming.service
   ```
   
   Add:
   ```ini
   [Unit]
   Description=RPi Video Streaming Server
   After=network.target

   [Service]
   Type=simple
   User=youruser
   WorkingDirectory=/path/to/rpi-video-streaming
   ExecStart=/usr/bin/node server.js
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   
   Then:
   ```bash
   sudo systemctl enable rpi-streaming
   sudo systemctl start rpi-streaming
   ```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /socket.io/ {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }
}
```

## Troubleshooting

### Server won't start
```bash
# Check if port is in use
lsof -i :3000

# Check logs
npm start 2>&1 | tee server.log
```

### Pi won't connect
- Verify server URL in Pi config
- Check firewall settings
- Ensure server is running: `curl http://SERVER_IP:3000`
- Check Pi logs: `sudo journalctl -u pi-controller -f`

### Video not streaming
- Verify camera is working on Pi
- Check network bandwidth
- Ensure Pi camera is enabled
- Check browser console for errors

### High latency
- Reduce video resolution/framerate
- Check network conditions
- Use WebRTC for lower latency (see `webrtc_server.py`)

## Development

### Project Structure
```
rpi-video-streaming/
├── server.js              # Main server with Socket.IO handlers
├── package.json           # Dependencies
├── .env                   # Configuration
├── public/
│   └── index.html         # Dashboard UI with drone control
├── data/
│   └── waypoints.json     # Stored waypoints
├── docs/
│   ├── DRONE_CONTROL_GUIDE.md    # Comprehensive drone control guide
│   └── TELEMETRY_UPDATE.md       # Telemetry integration docs
├── error.log              # Error logs
└── combined.log           # All logs
```

## Quick Start Guide

### 1. Setup Server
```bash
npm install
npm start
```

### 2. Setup Raspberry Pi
```bash
cd ../rpi-connect
python3 pi_controller.py
```

### 3. Access Dashboard
Open browser: `http://localhost:3000`

### 4. First Flight
1. Select your Pi from dropdown
2. Wait for telemetry (GPS coordinates visible)
3. Click "Pre-Flight Check"
4. Click "Set Geofence"
5. Click "ARM"
6. Click "Takeoff" (enter altitude)
7. Monitor telemetry
8. Click "Land"
9. Click "DISARM"

## 🔌 External Services

The `external-services/` folder contains services written in other languages that the GCS depends on.

### PyMAVLink Service (Python)

**Purpose**: Handles MAVLink communication with Pixhawk flight controllers

**Location**: `external-services/pymavlink_service.py`

**Why Python?**: 
- PyMAVLink is the official MAVLink library from ArduPilot
- More reliable and feature-complete than Node.js alternatives
- Better documentation and community support

**Running independently**:
```bash
cd external-services
python3 pymavlink_service.py
```

**API**: HTTP REST on port 5000

See [external-services/README.md](external-services/README.md) for details.

### Adding New External Services

The `external-services/` folder is designed to host additional services:

- **Image Processing**: Python services for ML/AI detection
- **Data Analytics**: Analysis services in Python/R
- **Video Processing**: FFmpeg-based services
- **Database**: PostgreSQL, MongoDB containers

Each service should:
1. Have its own subfolder
2. Include a README with setup instructions
3. Expose a clear API (REST/gRPC/WebSocket)
4. Be independently testable

## 📚 Documentation

### Main Documentation
- **[Mission Control Dashboard](docs/MISSION_CONTROL_DASHBOARD.md)** - Dashboard features and usage
- **[Mission Control Quick Start](docs/MISSION_CONTROL_QUICKSTART.md)** - Quick start guide
- **[Drone Control Guide](docs/DRONE_CONTROL_GUIDE.md)** - Complete flight control guide
- **[Telemetry Integration](docs/TELEMETRY_UPDATE.md)** - Telemetry system documentation

### External Services
- **[External Services README](external-services/README.md)** - Python services documentation

### Architecture
The system uses a modular architecture:
- **config/** - Centralized configuration
- **services/** - Business logic (missions, waypoints, drone control)
- **routes/** - HTTP API endpoints
- **socket/** - WebSocket handlers
- **external-services/** - Python/other language services

## Safety Warnings

⚠️ **IMPORTANT SAFETY INFORMATION**

- Always test in simulation (SITL) first
- Keep visual line of sight with drone
- Monitor battery levels continuously
- Have manual RC controller ready as backup
- Follow local aviation regulations
- Never fly over people or property
- Ensure proper calibration before flight
- Check weather conditions

## 🧪 Testing

### Testing with SITL (No Hardware)

```bash
# Install ArduPilot SITL
git clone https://github.com/ArduPilot/ardupilot
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y

# Start simulator
cd ArduCopter
sim_vehicle.py -v ArduCopter --console --map
```

Update PyMAVLink to connect to SITL:
```python
# In external-services/pymavlink_service.py
self.master = mavutil.mavlink_connection('tcp:127.0.0.1:5760')
```

## Security Considerations

⚠️ **Important Security Notes:**

- Use HTTPS/WSS in production
- Implement authentication before deployment
- Restrict command execution capabilities
- Use firewall rules to limit access
- Keep all packages updated
- Use VPN for remote access
- Validate all inputs server-side

## Performance Tips

- PyMAVLink service runs on separate process for better reliability
- Telemetry polling at 4Hz reduces overhead
- Mission data is logged to CSV for analysis
- Use SITL for load testing
- Monitor server resource usage

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Check the troubleshooting section
- Review server logs
- Check Pi client logs
- Open an issue on GitHub

## Related Projects

- [rpi-connect](../rpi-connect/) - Raspberry Pi client scripts
- Main NIDAR project - Parent repository
