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
const sprayerRoutes = require('./routes/sprayerRoutes');

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

// Forward mavlink_detection events from external services to all dashboard clients
io.on('connection', (socket) => {
  socket.on('mavlink_detection', (data) => {
    io.emit('mavlink_detection', data);
  });
});

// Serve mission files
app.use('/missions', express.static(config.MISSIONS_DIR));

// Mount API routes
app.use('/api/drones', droneRoutes);
app.use('/api/drone', droneRoutes); // Keep both for backwards compatibility
app.use('/api/mission', missionRoutes);
app.use('/api/missions', missionRoutes);
app.use('/api/waypoints', waypointRoutes);
app.use('/api/sprayer', sprayerRoutes);

// MAVLink detection forwarding endpoint
app.post('/api/mavlink-detection', (req, res) => {
  const detection = req.body;
  logger.info(`📡 MAVLink detection received: ${detection.detection_id} from Drone ${detection.drone_id}`);
  
  // Emit to all connected clients
  io.emit('mavlink_detection', detection);
  
  res.json({ success: true, message: 'Detection forwarded' });
});

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
  res.sendFile(path.join(config.PUBLIC_DIR, 'index.html'));
});

app.get('/landing', (req, res) => {
  res.sendFile(path.join(config.PUBLIC_DIR, 'landing.html'));
});

app.get('/mission-control', (req, res) => {
  res.sendFile(path.join(config.PUBLIC_DIR, 'mission_control.html'));
});

app.get('/flight-test', (req, res) => {
  res.sendFile(path.join(config.PUBLIC_DIR, 'flight_test.html'));
});

// Video stream proxy - proxies MJPEG stream from Pi
app.get('/stream', (req, res) => {
  const piId = req.query.pi_id;
  
  if (!piId) {
    return res.status(400).send('Missing pi_id parameter');
  }
  
  // Get Pi's stream URL from connected Pis (this would be stored during Pi registration)
  // For now, assume Pi is running on port 8080
  const streamUrl = `http://${piId}:8080/stream`;
  
  // Set headers for MJPEG streaming
  res.setHeader('Content-Type', 'multipart/x-mixed-replace; boundary=frame');
  res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Expires', '0');
  
  // Proxy the stream (simple implementation)
  // In production, you'd use http.request or a library like http-proxy
  logger.info(`Proxying stream from ${piId}`);
  
  // For now, just send a placeholder response
  res.status(503).send('Stream not available - Pi streaming service not configured');
});

// Setup Socket.IO handlers
setupSocketHandlers(io);

// Make io accessible to routes
app.set('io', io);


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

