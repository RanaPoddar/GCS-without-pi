const path = require('path');

const config = {
  // Server configuration
  PORT: process.env.PORT || 3000,
  HOST: '0.0.0.0',

  // Directories
  PUBLIC_DIR: path.join(__dirname, '..', 'public'),
  DATA_DIR: path.join(__dirname, '..', 'data'),
  MISSIONS_DIR: path.join(__dirname, '..', 'data', 'missions'),
  KML_UPLOADS_DIR: path.join(__dirname, '..', 'data', 'kml_uploads'),
  WAYPOINTS_FILE: path.join(__dirname, '..', 'data', 'waypoints.json'),

  // Socket.IO configuration
  SOCKET_CONFIG: {
    cors: {
      origin: "*",
      methods: ["GET", "POST"]
    },
    pingTimeout: 120000,      // Increased to 120 seconds
    pingInterval: 25000,
    connectTimeout: 60000,     // Connection timeout 60 seconds
    transports: ['websocket', 'polling'],  // Allow both transports
    allowUpgrades: true,       // Allow transport upgrades
    perMessageDeflate: false,  // Disable compression for better performance
    httpCompression: false,
    maxHttpBufferSize: 1e8     // 100MB for large payloads
  },

  // Drone configurations
  DRONE_CONFIGS: [
    {
      drone_id: 1,
      port: process.env.DRONE1_PORT || 'COM4',  // F10 RC ground module via USB Type-C
      baudRate: parseInt(process.env.DRONE1_BAUD) || 57600,
      name: 'Detection Drone via F10 RC'
    },
    {
      drone_id: 2,
      port: process.env.DRONE2_PORT || '/dev/ttyACM0',
      baudRate: parseInt(process.env.DRONE2_BAUD) || 57600
    }
  ],

  // Mission default parameters
  MISSION_DEFAULTS: {
    altitude: 8,
    speed: 2.0,
    field_size_acres: 2
  }
};

module.exports = config;
