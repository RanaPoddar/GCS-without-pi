require('dotenv').config();

const express = require('express');
const http = require('http');
const socketIO = require('socket.io');
const path = require('path');
const fs = require('fs');

// Import configuration and logger
const config = require('./config/config');
const logger = require('./config/logger');

// Import services
const pixhawkService = require('./services/pixhawkServicePyMAVLink');
const missionService = require('./services/missionService');
const waypointService = require('./services/waypointService');

// Import routes
const droneRoutes = require('./routes/droneRoutes');
const missionRoutes = require('./routes/missionRoutes');
const waypointRoutes = require('./routes/waypointRoutes');

// Import socket handlers
const { setupSocketHandlers } = require('./socket/socketHandlersPyMAVLink');

// Initialize Express app
const app = express();
const server = http.createServer(app);
const io = socketIO(server, config.SOCKET_CONFIG);


// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(config.PUBLIC_DIR));

// Serve mission files
app.use('/missions', express.static(config.MISSIONS_DIR));

// Mount API routes
app.use('/api/drones', droneRoutes);
app.use('/api/drone', droneRoutes); // Keep both for backwards compatibility
app.use('/api/mission', missionRoutes);
app.use('/api/missions', missionRoutes);
app.use('/api/waypoints', waypointRoutes);

// Create necessary directories
[config.PUBLIC_DIR, config.DATA_DIR, config.MISSIONS_DIR, config.KML_UPLOADS_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// Load waypoints on startup
waypointService.loadWaypoints();


// Page Routes
app.get('/', (req, res) => {
  res.sendFile(path.join(config.PUBLIC_DIR, 'landing.html'));
});

app.get('/legacy', (req, res) => {
  res.sendFile(path.join(config.PUBLIC_DIR, 'index.html'));
});

app.get('/mission-control', (req, res) => {
  res.sendFile(path.join(config.PUBLIC_DIR, 'mission_control.html'));
});

app.get('/flight-test', (req, res) => {
  res.sendFile(path.join(config.PUBLIC_DIR, 'flight_test.html'));
});

// Setup Socket.IO handlers
setupSocketHandlers(io);


// Initialize Pixhawk connections after a short delay
setTimeout(() => {
  pixhawkService.initializePixhawkConnections(io).catch(error => {
    logger.error(`Failed to initialize Pixhawk connections: ${error.message}`);
  });
}, 1000);

// Cleanup on shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM signal received: closing connections');
  pixhawkService.disconnectAll();
  server.close(() => {
    logger.info('HTTP server closed');
  });
});

process.on('SIGINT', () => {
  logger.info('SIGINT signal received: closing connections');
  pixhawkService.disconnectAll();
  server.close(() => {
    logger.info('HTTP server closed');
    process.exit(0);
  });
});

// Start server
server.listen(config.PORT, config.HOST, () => {
  logger.info(`🚀 Ground Control Station running on http://${config.HOST}:${config.PORT}`);
  logger.info(`📊 Mission Control Dashboard: http://localhost:${config.PORT}/mission-control`);
  logger.info(`🎮 Landing Page: http://localhost:${config.PORT}`);
  logger.info(`\n🔧 Pixhawk Configuration:`);
  config.DRONE_CONFIGS.forEach(droneConfig => {
    logger.info(`   Drone ${droneConfig.drone_id}: ${droneConfig.port} @ ${droneConfig.baudRate} baud`);
  });
  logger.info(`\n💡 Tip: Set DRONE1_PORT, DRONE2_PORT environment variables to customize serial ports`);
});

