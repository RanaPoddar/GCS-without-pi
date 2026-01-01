# External Services

This directory contains external services that the GCS depends on.

## PyMAVLink Service

A Python-based MAVLink communication service using the official PyMAVLink library.

### Structure

```
external-services/
├── pymavlink_service.py    # Flask API server for MAVLink communication
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

### Installation

```bash
cd external-services
pip3 install -r requirements.txt
```

### Running

```bash
# From this directory
python3 pymavlink_service.py

# Or from project root
python3 external-services/pymavlink_service.py
```

### API Documentation

The PyMAVLink service runs on **http://localhost:5000** and provides:

- `GET /health` - Health check
- `GET /drones` - List all drones
- `POST /drone/:id/connect` - Connect to drone
- `GET /drone/:id/telemetry` - Get telemetry
- `POST /drone/:id/arm` - Arm motors
- `POST /drone/:id/disarm` - Disarm motors
- `POST /drone/:id/takeoff` - Takeoff
- `POST /drone/:id/land` - Land
- `POST /drone/:id/rtl` - Return to launch
- `POST /drone/:id/goto` - Go to waypoint

### Dependencies

- **pymavlink** >= 2.4.41 - Official MAVLink protocol library
- **Flask** >= 2.3.0 - HTTP API framework
- **flask-cors** >= 4.0.0 - CORS support

### Adding More Services

This folder can contain additional external services:
- Image processing services
- ML/AI inference services
- Database services
- Third-party integrations

Each service should have its own subdirectory with proper documentation.
