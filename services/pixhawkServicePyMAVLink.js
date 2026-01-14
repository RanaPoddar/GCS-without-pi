const axios = require('axios');
const logger = require('../config/logger');
const config = require('../config/config');

// PyMAVLink service configuration
const PYMAVLINK_SERVICE_URL = process.env.PYMAVLINK_URL || 'http://localhost:5000';
const TELEMETRY_POLL_INTERVAL = 250; // ms

// Store connected drones and their stats
const connectedDrones = new Map();
const droneStats = new Map();
const telemetryIntervals = new Map();
const processedDetections = new Set(); // Track processed detection IDs to avoid duplicates

/**
 * Make HTTP request to PyMAVLink service
 */
async function callPyMAVLink(endpoint, method = 'GET', data = null) {
  try {
    const config = {
      method,
      url: `${PYMAVLINK_SERVICE_URL}${endpoint}`,
      headers: { 'Content-Type': 'application/json' }
    };
    
    if (data && (method === 'POST' || method === 'PUT')) {
      config.data = data;
    }
    
    const response = await axios(config);
    return { success: true, data: response.data };
  } catch (error) {
    logger.error(`PyMAVLink API error [${endpoint}]: ${error.message}`);
    return { 
      success: false, 
      error: error.response?.data?.error || error.message 
    };
  }
}

/**
 * Process STATUSTEXT messages for detection data
 */
function processStatustextForDetections(droneId, statustextLog, io) {
  const missionService = require('./missionService');
  
  for (const entry of statustextLog) {
    const text = entry.text || '';
    
    // Check for detection message format: DET|ID|LAT|LON|CONF|AREA
    if (text.startsWith('DET|')) {
      const parts = text.split('|');
      
      if (parts.length >= 6) {
        const detectionId = parts[1];
        
        // Skip if already processed
        if (processedDetections.has(detectionId)) {
          continue;
        }
        
        const detection = {
          detection_id: detectionId,
          latitude: parseFloat(parts[2]),
          longitude: parseFloat(parts[3]),
          confidence: parseFloat(parts[4]),
          detection_area: parseInt(parts[5]),
          source: 'mavlink',
          timestamp: entry.timestamp || Date.now() / 1000
        };
        
        logger.info(`🌾 Detection via MAVLink from Drone ${droneId}: ${detection.detection_id} at (${detection.latitude}, ${detection.longitude})`);
        
        // Save detection
        const detectionData = missionService.saveDetection(droneId, detection);
        
        if (detectionData && io) {
          io.emit('crop_detection', detectionData);
          logger.info(`   ✅ Detection broadcasted to all clients`);
        }
        
        // Mark as processed
        processedDetections.add(detectionId);
        
        // Clean up old processed IDs (keep last 1000)
        if (processedDetections.size > 1000) {
          const toDelete = Array.from(processedDetections).slice(0, 100);
          toDelete.forEach(id => processedDetections.delete(id));
        }
      }
    }
    // Check for detection stats: DSTAT|TOTAL|ACTIVE|MISSION_ID
    else if (text.startsWith('DSTAT|')) {
      const parts = text.split('|');
      if (parts.length >= 4) {
        logger.info(`📊 Detection Stats from Drone ${droneId}: Total=${parts[1]}, Active=${parts[2]}, Mission=${parts[3]}`);
        if (io) {
          io.emit('detection_stats', {
            drone_id: droneId,
            total_detections: parseInt(parts[1]),
            active_status: parts[2],
            mission_id: parts[3],
            timestamp: entry.timestamp || Date.now() / 1000
          });
        }
      }
    }
    // Check for image captured: IMG|ID|PATH
    else if (text.startsWith('IMG|')) {
      const parts = text.split('|');
      if (parts.length >= 3) {
        logger.info(`📷 Image captured from Drone ${droneId}: ${parts[1]} -> ${parts[2]}`);
        if (io) {
          io.emit('image_captured', {
            drone_id: droneId,
            detection_id: parts[1],
            image_path: parts[2],
            timestamp: entry.timestamp || Date.now() / 1000
          });
        }
      }
    }
    // Check for system status: STAT|CPU|MEM|DISK|TEMP
    else if (text.startsWith('STAT|')) {
      const parts = text.split('|');
      if (parts.length >= 5) {
        logger.debug(`💻 Pi Stats from Drone ${droneId}: CPU=${parts[1]}% MEM=${parts[2]}% DISK=${parts[3]}% TEMP=${parts[4]}°C`);
        if (io) {
          io.emit('pi_stats', {
            drone_id: droneId,
            cpu_percent: parseFloat(parts[1]),
            memory_percent: parseFloat(parts[2]),
            disk_percent: parseFloat(parts[3]),
            temperature: parseFloat(parts[4]),
            timestamp: entry.timestamp || Date.now() / 1000
          });
        }
      }
    }
  }
}

/**
 * Broadcast STATUSTEXT messages to dashboard
 */
function broadcastStatustextMessages(droneId, statustextLog, io) {
  if (!io) return;
  
  // Track last broadcast timestamp per drone to avoid spam
  if (!broadcastStatustextMessages.lastBroadcast) {
    broadcastStatustextMessages.lastBroadcast = {};
  }
  
  const now = Date.now();
  const minInterval = 500; // Minimum 500ms between broadcasts per drone
  
  if (broadcastStatustextMessages.lastBroadcast[droneId] && 
      now - broadcastStatustextMessages.lastBroadcast[droneId] < minInterval) {
    return; // Too soon, skip this broadcast
  }
  
  broadcastStatustextMessages.lastBroadcast[droneId] = now;
  
  // Send recent STATUSTEXT messages to dashboard
  // Priority: warnings (severity < 4) and critical messages
  const importantMessages = statustextLog
    .filter(entry => {
      const text = (entry.text || '').toLowerCase();
      const severity = entry.severity || 6;
      
      // Always show critical messages (severity < 4)
      if (severity < 4) return true;
      
      // Always show these keywords
      const keywords = [
        'rtl', 'failsafe', 'battery', 'fence', 'ekf', 'gps',
        'pre-arm', 'arming', 'mode', 'waypoint', 'mission',
        'error', 'failed', 'bad', 'compass', 'variance'
      ];
      
      return keywords.some(keyword => text.includes(keyword));
    })
    .slice(-5); // Last 5 important messages
  
  if (importantMessages.length > 0) {
    io.emit('statustext_messages', {
      drone_id: droneId,
      messages: importantMessages.map(entry => ({
        text: entry.text,
        severity: entry.severity || 6,
        timestamp: entry.timestamp || Date.now() / 1000
      }))
    });
  }
}

/**
 * Start telemetry polling for a drone
 */
function startTelemetryPolling(droneId, io) {
  // Clear existing interval if any
  if (telemetryIntervals.has(droneId)) {
    clearInterval(telemetryIntervals.get(droneId));
  }
  
  // Poll telemetry at regular intervals
  const interval = setInterval(async () => {
    const result = await callPyMAVLink(`/drone/${droneId}/telemetry`);
    
    if (result.success && result.data) {
      const telemetryData = {
        drone_id: droneId,
        timestamp: result.data.timestamp,
        telemetry: {
          gps: {
            lat: result.data.telemetry.latitude,
            lon: result.data.telemetry.longitude,
            satellites_visible: result.data.telemetry.satellites_visible,
            hdop: result.data.telemetry.hdop,
            fix_type: result.data.telemetry.gps_fix_type
          },
          altitude: result.data.telemetry.relative_altitude || result.data.telemetry.altitude,
          heading: result.data.telemetry.heading,
          groundspeed: result.data.telemetry.groundspeed,
          attitude: {
            pitch: result.data.telemetry.pitch,
            roll: result.data.telemetry.roll,
            yaw: result.data.telemetry.yaw
          },
          battery: {
            voltage: result.data.telemetry.battery_voltage,
            current: result.data.telemetry.battery_current,
            remaining: result.data.telemetry.battery_remaining
          },
          flight_mode: result.data.telemetry.flight_mode,
          armed: result.data.telemetry.armed,
          airspeed: result.data.telemetry.airspeed,
          climb_rate: result.data.telemetry.climb_rate,
          throttle: result.data.telemetry.throttle
        }
      };
      
      // Store telemetry
      droneStats.set(droneId, telemetryData);
      
      // Broadcast to all connected clients
      if (io) {
        io.emit('drone_telemetry_update', telemetryData);
      }
      
      // Log to active mission if needed
      const missionService = require('./missionService');
      missionService.logTelemetry(droneId, telemetryData);
      
      // Check for detection messages in STATUSTEXT
      if (result.data.telemetry.statustext_log && Array.isArray(result.data.telemetry.statustext_log)) {
        processStatustextForDetections(droneId, result.data.telemetry.statustext_log, io);
      }
      
      // Broadcast STATUSTEXT messages to dashboard
      if (result.data.telemetry.statustext_log && Array.isArray(result.data.telemetry.statustext_log)) {
        broadcastStatustextMessages(droneId, result.data.telemetry.statustext_log, io);
      }
    }
  }, TELEMETRY_POLL_INTERVAL);
  
  telemetryIntervals.set(droneId, interval);
  logger.debug(`Telemetry polling started for Drone ${droneId}`);
}

/**
 * Stop telemetry polling for a drone
 */
function stopTelemetryPolling(droneId) {
  if (telemetryIntervals.has(droneId)) {
    clearInterval(telemetryIntervals.get(droneId));
    telemetryIntervals.delete(droneId);
    logger.debug(`Telemetry polling stopped for Drone ${droneId}`);
  }
}

/**
 * Initialize PyMAVLink connections for all configured drones
 */
async function initializePixhawkConnections(io) {
  logger.info('🚁 Initializing PyMAVLink connections...');
  
  // Check if PyMAVLink service is running
  try {
    const health = await callPyMAVLink('/health');
    if (!health.success) {
      logger.error('❌ PyMAVLink service is not running!');
      logger.info('   Start it with: python3 pymavlink_service.py');
      return;
    }
    logger.info('✅ PyMAVLink service is running');
  } catch (error) {
    logger.error('❌ Cannot connect to PyMAVLink service');
    logger.info('   Start it with: python3 pymavlink_service.py');
    return;
  }
  
  // First, sync any drones that are already connected in PyMAVLink
  await syncConnectedDrones(io);
  
  let connectedCount = 0;
  
  for (const droneConfig of config.DRONE_CONFIGS) {
    try {
      logger.info(`Connecting to Drone ${droneConfig.drone_id}...`);
      
      const result = await callPyMAVLink(`/drone/${droneConfig.drone_id}/connect`, 'POST', {
        port: droneConfig.port,
        baudrate: droneConfig.baudRate
      });
      
      if (result.success) {
        connectedDrones.set(droneConfig.drone_id, {
          connected: true,
          port: droneConfig.port,
          baudRate: droneConfig.baudRate
        });
        
        // Start telemetry polling
        startTelemetryPolling(droneConfig.drone_id, io);
        
        logger.info(`✅ Drone ${droneConfig.drone_id} connected on ${droneConfig.port}`);
        
        // Emit connection event
        if (io) {
          io.emit('drone_connected', { drone_id: droneConfig.drone_id });
        }
        
        connectedCount++;
      } else {
        logger.error(`❌ Failed to connect Drone ${droneConfig.drone_id}: ${result.error}`);
        logger.info(`   Check if ${droneConfig.port} is available and Pixhawk is connected`);
        
        connectedDrones.set(droneConfig.drone_id, {
          connected: false,
          port: droneConfig.port,
          baudRate: droneConfig.baudRate
        });
        
        // Emit disconnection event
        if (io) {
          io.emit('drone_disconnected', { drone_id: droneConfig.drone_id });
        }
      }
    } catch (error) {
      logger.error(`❌ Error connecting Drone ${droneConfig.drone_id}: ${error.message}`);
    }
  }
  
  logger.info(`🚁 PyMAVLink initialization complete: ${connectedCount}/${config.DRONE_CONFIGS.length} drones connected`);
}

/**
 * Reconnect a specific drone
 */
async function reconnectDrone(droneId, io) {
  logger.info(`🔄 Reconnect request for Drone ${droneId}`);
  
  try {
    // Disconnect first
    await callPyMAVLink(`/drone/${droneId}/disconnect`, 'POST');
    stopTelemetryPolling(droneId);
    
    // Wait a moment
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Find configuration
    const droneConfig = config.DRONE_CONFIGS.find(c => c.drone_id === droneId);
    if (!droneConfig) {
      throw new Error(`No configuration found for Drone ${droneId}`);
    }
    
    // Reconnect
    const result = await callPyMAVLink(`/drone/${droneId}/connect`, 'POST', {
      port: droneConfig.port,
      baudrate: droneConfig.baudRate
    });
    
    if (result.success) {
      connectedDrones.set(droneId, {
        connected: true,
        port: droneConfig.port,
        baudRate: droneConfig.baudRate
      });
      
      startTelemetryPolling(droneId, io);
      
      logger.info(`✅ Drone ${droneId} reconnected successfully`);
      
      if (io) {
        io.emit('drone_connected', { drone_id: droneId });
      }
      
      return true;
    } else {
      throw new Error(result.error);
    }
  } catch (error) {
    logger.error(`❌ Failed to reconnect Drone ${droneId}: ${error.message}`);
    
    connectedDrones.set(droneId, {
      connected: false
    });
    
    if (io) {
      io.emit('drone_disconnected', { drone_id: droneId });
    }
    
    return false;
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
 * Get connection info for specific drone
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
 * Send command to drone
 */
async function sendCommand(droneId, command, params = {}) {
  const connection = connectedDrones.get(droneId);
  
  if (!connection || !connection.connected) {
    throw new Error('Drone not connected');
  }
  
  let endpoint = '';
  let data = {};
  
  switch (command) {
    case 'arm':
      endpoint = `/drone/${droneId}/arm`;
      break;
    case 'disarm':
      endpoint = `/drone/${droneId}/disarm`;
      break;
    case 'set_mode':
      endpoint = `/drone/${droneId}/mode`;
      data = { mode: params.mode };
      break;
    case 'takeoff':
      endpoint = `/drone/${droneId}/takeoff`;
      data = { altitude: params.altitude };
      break;
    case 'land':
      endpoint = `/drone/${droneId}/land`;
      break;
    case 'rtl':
      endpoint = `/drone/${droneId}/rtl`;
      break;
    case 'goto':
      endpoint = `/drone/${droneId}/goto`;
      data = {
        latitude: params.latitude,
        longitude: params.longitude,
        altitude: params.altitude
      };
      break;
    default:
      throw new Error(`Unknown command: ${command}`);
  }
  
  const result = await callPyMAVLink(endpoint, 'POST', data);
  
  if (!result.success) {
    throw new Error(result.error);
  }
  
  return result.data;
}

/**
 * Sync with PyMAVLink service to detect already-connected drones
 */
async function syncConnectedDrones(io) {
  try {
    logger.info('🔄 Syncing with PyMAVLink service...');
    
    const result = await callPyMAVLink('/drones');
    
    if (result.success && result.data && result.data.drones) {
      const pymavlinkDrones = result.data.drones;
      
      for (const drone of pymavlinkDrones) {
        if (drone.connected && !connectedDrones.has(drone.drone_id)) {
          logger.info(`📡 Found connected drone ${drone.drone_id} in PyMAVLink (${drone.simulation ? 'SIMULATION' : 'HARDWARE'})`);
          
          connectedDrones.set(drone.drone_id, {
            connected: true,
            port: drone.port,
            simulation: drone.simulation
          });
          
          // Start telemetry polling
          startTelemetryPolling(drone.drone_id, io);
          
          // Emit connection event
          if (io) {
            io.emit('drone_connected', { 
              drone_id: drone.drone_id,
              simulation: drone.simulation 
            });
          }
          
          logger.info(`✅ Synced Drone ${drone.drone_id} - telemetry polling started`);
        }
      }
    }
  } catch (error) {
    logger.error(`Failed to sync with PyMAVLink: ${error.message}`);
  }
}

/**
 * Disconnect all drones
 */
async function disconnectAll() {
  logger.info('Disconnecting all drones...');
  
  for (const droneId of connectedDrones.keys()) {
    try {
      await callPyMAVLink(`/drone/${droneId}/disconnect`, 'POST');
      stopTelemetryPolling(droneId);
    } catch (error) {
      logger.error(`Error disconnecting Drone ${droneId}: ${error.message}`);
    }
  }
  
  connectedDrones.clear();
  droneStats.clear();
}

module.exports = {
  connectedDrones,
  droneStats,
  initializePixhawkConnections,
  reconnectDrone,
  syncConnectedDrones,
  getDroneStatusList,
  getDroneConnection,
  getDroneStats,
  sendCommand,
  disconnectAll
};
