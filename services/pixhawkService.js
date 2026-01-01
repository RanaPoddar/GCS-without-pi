const PixhawkConnection = require('../mavlink_handler');
const logger = require('../config/logger');
const config = require('../config/config');
const missionService = require('./missionService');

// Store connected drones and their stats
const connectedDrones = new Map();
const droneStats = new Map();

/**
 * Setup event handlers for a drone connection
 */
function setupDroneEventHandlers(connection, io) {
  connection.on('connected', (data) => {
    logger.info(`✅ Drone ${data.drone_id} connected`);
    io.emit('drone_connected', data);
  });
  
  connection.on('disconnected', (data) => {
    logger.warn(`⚠️  Drone ${data.drone_id} disconnected`);
    io.emit('drone_disconnected', data);
  });
  
  connection.on('telemetry', (data) => {
    // Store telemetry
    droneStats.set(data.drone_id, data);
    
    // Broadcast to all connected dashboard clients
    io.emit('drone_telemetry_update', data);
    
    // Log to active mission if any
    missionService.logTelemetry(data.drone_id, data);
  });
  
  connection.on('heartbeat', (data) => {
    io.emit('drone_heartbeat', data);
  });
  
  connection.on('error', (data) => {
    logger.error(`❌ Drone ${data.drone_id} error: ${data.error}`);
    io.emit('drone_error', data);
  });
}

/**
 * Initialize Pixhawk connections for all configured drones
 */
async function initializePixhawkConnections(io) {
  logger.info('🚁 Initializing Pixhawk connections...');
  
  for (const droneConfig of config.DRONE_CONFIGS) {
    const connection = new PixhawkConnection(
      droneConfig.drone_id,
      droneConfig.port,
      droneConfig.baudRate,
      logger
    );
    
    setupDroneEventHandlers(connection, io);
    connectedDrones.set(droneConfig.drone_id, connection);
    
    try {
      await connection.connect();
      logger.info(`✅ Drone ${droneConfig.drone_id} initialized on ${droneConfig.port}`);
    } catch (error) {
      logger.error(`❌ Failed to connect Drone ${droneConfig.drone_id}: ${error.message}`);
      logger.info(`   Check if ${droneConfig.port} is available and Pixhawk is connected`);
    }
  }
  
  const actuallyConnected = Array.from(connectedDrones.values()).filter(c => c.connected).length;
  logger.info(`🚁 Pixhawk initialization complete: ${actuallyConnected}/${config.DRONE_CONFIGS.length} drones connected`);
}

/**
 * Reconnect a specific drone
 */
async function reconnectDrone(droneId) {
  logger.info(`🔄 Reconnect request for Drone ${droneId}`);
  
  const droneConnection = connectedDrones.get(droneId);
  
  if (droneConnection) {
    if (droneConnection.connected) {
      droneConnection.disconnect();
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    await droneConnection.connect();
    logger.info(`✅ Drone ${droneId} reconnected successfully`);
    return true;
  } else {
    const droneConfig = config.DRONE_CONFIGS.find(c => c.drone_id === droneId);
    if (droneConfig) {
      const newConnection = new PixhawkConnection(
        droneConfig.drone_id,
        droneConfig.port,
        droneConfig.baudRate,
        logger
      );
      
      await newConnection.connect();
      connectedDrones.set(droneId, newConnection);
      logger.info(`✅ Drone ${droneId} connected for the first time`);
      return true;
    } else {
      throw new Error(`No configuration found for Drone ${droneId}`);
    }
  }
}

/**
 * Get drone connection status list
 */
function getDroneStatusList() {
  return Array.from(connectedDrones.entries()).map(([id, connection]) => {
    const stats = droneStats.get(id) || {};
    return {
      drone_id: id,
      connected: connection.connected,
      telemetry: stats.telemetry || null,
      lastSeen: stats.timestamp || null
    };
  });
}

/**
 * Get connection for specific drone
 */
function getDroneConnection(droneId) {
  return connectedDrones.get(droneId);
}

/**
 * Get stats for specific drone
 */
function getDroneStats(droneId) {
  return droneStats.get(droneId);
}

/**
 * Disconnect all drones
 */
function disconnectAll() {
  connectedDrones.forEach((connection) => {
    connection.disconnect();
  });
}

module.exports = {
  connectedDrones,
  droneStats,
  initializePixhawkConnections,
  reconnectDrone,
  getDroneStatusList,
  getDroneConnection,
  getDroneStats,
  disconnectAll,
  setupDroneEventHandlers
};
