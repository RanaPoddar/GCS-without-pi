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
    pingTimeout: 60000,
    pingInterval: 25000
  },

  // Drone configurations
  DRONE_CONFIGS: [
    {
      drone_id: 1,
      port: process.env.DRONE1_PORT || '/dev/ttyUSB0',
      baudRate: parseInt(process.env.DRONE1_BAUD) || 57600
    },
    {
      drone_id: 2,
      port: process.env.DRONE2_PORT || '/dev/ttyUSB1',
      baudRate: parseInt(process.env.DRONE2_BAUD) || 57600
    }
  ],

  // Mission default parameters
  MISSION_DEFAULTS: {
    altitude: 15.0,
    speed: 2.0,
    field_size_acres: 2
  }
};

module.exports = config;
