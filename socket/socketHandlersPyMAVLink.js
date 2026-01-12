const logger = require('../config/logger');
const pixhawkService = require('../services/pixhawkServicePyMAVLink');
const missionService = require('../services/missionService');
const waypointService = require('../services/waypointService');
const sprayerService = require('../services/sprayerService');

// Track connected Raspberry Pis
const connectedPis = new Map();

/**
 * Setup all Socket.IO event handlers for PyMAVLink
 */
function setupSocketHandlers(io) {
  // Setup sprayer service event forwarding
  sprayerService.on('targets_queued', (data) => {
    io.emit('spray_targets_queued', data);
  });
  
  sprayerService.on('mission_started', (data) => {
    io.emit('spray_mission_started', data);
  });
  
  sprayerService.on('next_target', (data) => {
    io.emit('spray_next_target', data);
  });
  
  sprayerService.on('refill_required', (data) => {
    io.emit('spray_refill_required', data);
  });
  
  sprayerService.on('refill_complete', (data) => {
    io.emit('spray_refill_complete', data);
  });
  
  sprayerService.on('mission_complete', (data) => {
    io.emit('spray_mission_complete', data);
  });
  
  io.on('connection', (socket) => {
    logger.info(`Client connected: ${socket.id}`);
    
    // Send current drone status to newly connected client
    const droneList = pixhawkService.getDroneStatusList();
    socket.emit('drones_status', { drones: droneList });

    // Emit individual drone connection status
    pixhawkService.connectedDrones.forEach((connection, droneId) => {
      if (connection.connected) {
        socket.emit('drone_connected', { drone_id: droneId });
      } else {
        socket.emit('drone_disconnected', { drone_id: droneId });
      }
    });
    
    // ========================================
    //      Raspberry Pi Registration         |
    // ========================================
    
    // Pi identifies itself
    socket.on('pi_register', (data) => {
      const piId = data.pi_id || socket.id;
      logger.info(`🥧 Raspberry Pi registered: ${piId}`);
      logger.info(`   Socket ID: ${socket.id}`);
      logger.info(`   Total Pis connected: ${connectedPis.size + 1}`);
      
      connectedPis.set(piId, {
        id: piId,
        socket_id: socket.id,
        connected: true,
        connected_at: new Date().toISOString(),
        ...data
      });
      
      // Notify all clients
      io.emit('pi_connected', { pi_id: piId });
      logger.info(`   Broadcasted pi_connected event to all clients`);
      
      // Store pi_id in socket for later use
      socket.pi_id = piId;
    });
    
    // Request list of connected Pis
    socket.on('request_pi_list', () => {
      const piList = Array.from(connectedPis.values()).map(pi => ({
        id: pi.id,
        connected: pi.connected,
        connected_at: pi.connected_at
      }));
      
      socket.emit('pi_list', { pis: piList });
      logger.info(`📋 Sent Pi list: ${piList.length} connected`);
    });
    
    // System stats from Pi
    socket.on('system_stats', (data) => {
      const piId = data.pi_id;
      logger.info(`📊 System stats from Pi: ${piId}`);
      
      // Update Pi info with stats
      if (connectedPis.has(piId)) {
        const pi = connectedPis.get(piId);
        pi.stats = data.stats;
        pi.last_stats_update = new Date().toISOString();
      }
      
      // Broadcast to all clients
      io.emit('system_stats', data);
    });
    
    // Drone telemetry from Pi (Pixhawk data)
    socket.on('drone_telemetry', (data) => {
      const piId = data.pi_id;
      
      // Update Pi info with telemetry
      if (connectedPis.has(piId)) {
        const pi = connectedPis.get(piId);
        pi.telemetry = data.telemetry;
        pi.last_telemetry_update = new Date().toISOString();
      }
      
      // Broadcast to all clients (no logging - telemetry updates at 10Hz)
      io.emit('drone_telemetry', data);
    });
    
    // Request stats from Pi
    socket.on('request_stats', (data) => {
      const piId = data.pi_id;
      logger.info(`Requesting stats from Pi: ${piId}`);
      io.emit('request_stats', data);
    });
    
    // ========================================
    //      Drone Control Commands            |
    // ========================================
    
    // ARM
    socket.on('drone_arm', async (data) => {
      const { drone_id } = data;
      
      try {
        await pixhawkService.sendCommand(drone_id, 'arm');
        logger.info(`ARM command sent to Drone ${drone_id}`);
        socket.emit('drone_command_result', { success: true, drone_id, command: 'arm' });
      } catch (error) {
        logger.error(`ARM failed for Drone ${drone_id}: ${error.message}`);
        socket.emit('drone_command_result', { success: false, drone_id, command: 'arm', error: error.message });
      }
    });
    
    // DISARM
    socket.on('drone_disarm', async (data) => {
      const { drone_id } = data;
      
      try {
        await pixhawkService.sendCommand(drone_id, 'disarm');
        logger.info(` DISARM command sent to Drone ${drone_id}`);
        socket.emit('drone_command_result', { success: true, drone_id, command: 'disarm' });
      } catch (error) {
        logger.error(` DISARM failed for Drone ${drone_id}: ${error.message}`);
        socket.emit('drone_command_result', { success: false, drone_id, command: 'disarm', error: error.message });
      }
    });
    
    // Set flight mode
    socket.on('drone_set_mode', async (data) => {
      const { drone_id, mode } = data;
      
      try {
        await pixhawkService.sendCommand(drone_id, 'set_mode', { mode });
        logger.info(`🚁 Set flight mode to ${mode} for Drone ${drone_id}`);
        socket.emit('drone_command_result', { success: true, drone_id, command: 'set_mode', mode });
      } catch (error) {
        logger.error(`❌ Set mode failed for Drone ${drone_id}: ${error.message}`);
        socket.emit('drone_command_result', { success: false, drone_id, command: 'set_mode', error: error.message });
      }
    });
    
    // Takeoff
    socket.on('drone_takeoff', async (data) => {
      const { drone_id, altitude } = data;
      
      try {
        await pixhawkService.sendCommand(drone_id, 'takeoff', { altitude: altitude || 10 });
        logger.info(`🚁 Takeoff command sent to Drone ${drone_id} (altitude=${altitude}m)`);
        socket.emit('drone_command_result', { success: true, drone_id, command: 'takeoff' });
      } catch (error) {
        logger.error(`❌ Takeoff failed for Drone ${drone_id}: ${error.message}`);
        socket.emit('drone_command_result', { success: false, drone_id, command: 'takeoff', error: error.message });
      }
    });
    
    // Landing
    socket.on('drone_land', async (data) => {
      const { drone_id } = data;
      
      try {
        await pixhawkService.sendCommand(drone_id, 'land');
        logger.info(`🚁 Land command sent to Drone ${drone_id}`);
        socket.emit('drone_command_result', { success: true, drone_id, command: 'land' });
      } catch (error) {
        logger.error(`❌ Land failed for Drone ${drone_id}: ${error.message}`);
        socket.emit('drone_command_result', { success: false, drone_id, command: 'land', error: error.message });
      }
    });
    
    // Return to launch
    socket.on('drone_rtl', async (data) => {
      const { drone_id } = data;
      
      try {
        await pixhawkService.sendCommand(drone_id, 'rtl');
        logger.info(`🚁 RTL command sent to Drone ${drone_id}`);
        socket.emit('drone_command_result', { success: true, drone_id, command: 'rtl' });
      } catch (error) {
        logger.error(`❌ RTL failed for Drone ${drone_id}: ${error.message}`);
        socket.emit('drone_command_result', { success: false, drone_id, command: 'rtl', error: error.message });
      }
    });
    
    // Goto location
    socket.on('drone_goto', async (data) => {
      const { drone_id, latitude, longitude, altitude } = data;
      
      try {
        await pixhawkService.sendCommand(drone_id, 'goto', {
          latitude,
          longitude,
          altitude: altitude || 10
        });
        logger.info(`🚁 Goto command sent to Drone ${drone_id}: (${latitude}, ${longitude}) @ ${altitude}m`);
        socket.emit('drone_command_result', { success: true, drone_id, command: 'goto' });
      } catch (error) {
        logger.error(`❌ Goto failed for Drone ${drone_id}: ${error.message}`);
        socket.emit('drone_command_result', { success: false, drone_id, command: 'goto', error: error.message });
      }
    });

    // Drone reconnect handler
    socket.on('drone_reconnect', async (data) => {
      const { drone_id } = data;
      
      try {
        const success = await pixhawkService.reconnectDrone(drone_id, io);
        if (!success) {
          throw new Error('Reconnection failed');
        }
      } catch (error) {
        logger.error(` Failed to reconnect Drone ${drone_id}: ${error.message}`);
      }
    });
    
    // Sync with PyMAVLink service (detect already-connected drones)
    socket.on('sync_drones', async () => {
      logger.info('🔄 Manual sync requested');
      try {
        await pixhawkService.syncConnectedDrones(io);
        socket.emit('sync_complete', { success: true });
      } catch (error) {
        logger.error(`Sync failed: ${error.message}`);
        socket.emit('sync_complete', { success: false, error: error.message });
      }
    });

    // ========================================
    //      Mission Detection & Image Capture |
    // ========================================
    
    // Camera/Stream control - forward to Pi
    socket.on('start_stream', (data) => {
      logger.info(`Dashboard requesting start stream for Pi: ${data.pi_id}`);
      io.emit('start_stream', data);
    });
    
    socket.on('stop_stream', (data) => {
      logger.info(`Dashboard requesting stop stream for Pi: ${data.pi_id}`);
      io.emit('stop_stream', data);
    });
    
    // Stream status from Pi
    socket.on('stream_status', (data) => {
      logger.info(`Stream status from Pi ${data.pi_id}: ${data.status}`);
      io.emit('stream_status', data);
    });
    
    // Camera frame from Pi
    socket.on('camera_frame', (data) => {
      // Forward camera frame to all clients
      io.emit('camera_frame', data);
    });

    socket.on('crop_detection', (data) => {
      // Map pi_id to drone_id if needed
      let droneId = data.drone_id;
      if (!droneId && data.pi_id) {
        droneId = data.pi_id === 'detection_drone_pi_pushpak' ? 1 : 2;
        data.drone_id = droneId;
      }
      
      logger.info(`🌾 Detection from Pi ${data.pi_id}: ${data.detection_id} at (${data.latitude}, ${data.longitude})`);
      
      const detectionData = missionService.saveDetection(droneId, data);
      
      if (detectionData) {
        io.emit('crop_detection', detectionData);
        logger.info(`   ✅ Detection broadcasted to all clients`);
      } else {
        logger.warn(`   ⚠️ Failed to save detection data`);
      }
    });

    // Manual detection trigger (for testing)
    socket.on('manual_detection', (data) => {
      logger.info(`📍 Manual detection triggered - Drone ${data.drone_id} at [${data.latitude}, ${data.longitude}]`);
      logger.info(`   Confidence: ${(data.confidence * 100).toFixed(1)}% | Type: ${data.type}`);
      
      // Save detection
      const detectionData = missionService.saveDetection(data.drone_id, data);
      
      if (detectionData) {
        // Broadcast to all clients
        io.emit('detection', detectionData);
        io.emit('crop_detection', detectionData);
        
        logger.info(`   Detection broadcasted to all clients`);
      }
    });
    
    socket.on('detection_status', (data) => {
      logger.info(`Detection status from Drone ${data.drone_id}: ${data.status}`);
      io.emit('detection_status', data);
    });
    
    // Detection control - forward to Pi
    socket.on('start_detection', (data) => {
      logger.info(`Dashboard requesting start detection for Pi: ${data.pi_id}`);
      io.emit('start_detection', data);
    });
    
    socket.on('stop_detection', (data) => {
      logger.info(`Dashboard requesting stop detection for Pi: ${data.pi_id}`);
      io.emit('stop_detection', data);
    });
    
    socket.on('get_detection_stats', (data) => {
      logger.info(`Dashboard requesting detection stats for Pi: ${data.pi_id}`);
      io.emit('get_detection_stats', data);
    });
    
    // ========================================
    //          Mission Management            |
    // ========================================
    
    // Mission started from Pi (auto-mission)
    socket.on('mission_started', (data) => {
      const droneId = data.drone_id || 1;
      const missionData = missionService.initializeMission(droneId, {
        mission_id: data.mission_id,
        auto_started: data.auto_started || false
      });
      
      logger.info(`🚀 Mission ${data.mission_id} started from Pi for Drone ${droneId}`);
      
      // Broadcast to all clients
      io.emit('mission_started', {
        mission_id: missionData.mission_id,
        drone_id: droneId,
        timestamp: missionData.start_time,
        auto_started: data.auto_started
      });
    });
    
    socket.on('start_mission', async (data) => {
      const droneId = data.drone_id || 1;
      const missionData = missionService.initializeMission(droneId, data);
      
      io.emit('mission_started', {
        mission_id: missionData.mission_id,
        drone_id: droneId,
        timestamp: missionData.start_time
      });
      
      logger.info(` Mission ${missionData.mission_id} initialized for Drone ${droneId}`);
    });
    
    socket.on('mission_completed', (data) => {
      const droneId = data.drone_id || 1;
      const missionData = missionService.activeMissions.get(droneId);
      
      if (missionData) {
        logger.info(` Mission completed: ${missionData.mission_id}`);
        missionData.status = 'completed';
        
        io.emit('mission_status', {
          mission_id: missionData.mission_id,
          drone_id: droneId,
          status: 'completed',
          progress: 100
        });
      }
    });
    
    socket.on('mission_error', (data) => {
      const droneId = data.drone_id || 1;
      const missionData = missionService.activeMissions.get(droneId);
      
      if (missionData) {
        const errorMsg = data.error || 'Unknown error';
        logger.error(` Mission error: ${missionData.mission_id} - ${errorMsg}`);
        
        missionData.status = 'error';
        missionData.error = errorMsg;
        missionData.error_time = new Date().toISOString();
        
        missionService.saveMissionMetadata(missionData);
        
        io.emit('mission_status', {
          mission_id: missionData.mission_id,
          status: 'error',
          error: errorMsg
        });
      }
    });
    
    socket.on('stop_mission', (data) => {
      const droneId = data.drone_id || 1;
      const completedMission = missionService.stopMission(droneId);
      
      if (completedMission) {
        io.emit('mission_stopped', {
          mission_id: completedMission.mission_id,
          drone_id: droneId,
          total_detections: completedMission.total_detections,
          duration_minutes: completedMission.duration_minutes
        });
      }
    });
    
    socket.on('detection_stats', (data) => {
      logger.info(`Detection stats from Drone ${data.drone_id}: ${data.stats.total_detections} total`);
      io.emit('detection_stats', data);
    });
    
    // ========================================
    //      Periodic Image Capture            |
    // ========================================
    
    socket.on('periodic_image', (data) => {
      const droneId = data.drone_id || 1;
      const success = missionService.savePeriodicImage(droneId, data);
      
      if (success) {
        const missionData = missionService.activeMissions.get(droneId);
        io.emit('periodic_image_received', {
          mission_id: missionData.mission_id,
          image_id: data.image_id,
          count: missionData.periodic_images_count
        });
      }
    });
    
    // ========================================
    //      Waypoint Management                |
    // ========================================
    
    socket.on('waypoint_marked', (data) => {
      const waypoint = waypointService.addWaypoint(data);
      
      io.emit('waypoint_added', {
        waypoint: waypoint,
        total: waypointService.markedWaypoints.length
      });
    });
    
    socket.on('request_waypoints', () => {
      socket.emit('waypoints_list', {
        waypoints: waypointService.getAllWaypoints()
      });
    });
    
    // Request drone list
    socket.on('request_drone_list', () => {
      const droneList = pixhawkService.getDroneStatusList();
      socket.emit('drones_status', { drones: droneList });
    });
    
    // ========================================
    //      Sprayer Mission Control           |
    // ========================================
    
    // Queue spray targets
    socket.on('spray_queue_targets', (data) => {
      logger.info(`💧 Queueing spray targets for Drone ${data.drone_id}: ${data.detections.length} targets`);
      const result = sprayerService.queueTargets(data.drone_id, data.detections);
      socket.emit('spray_targets_queued', result);
      io.emit('spray_queue_updated', {
        drone_id: data.drone_id,
        queue_length: result.total_queued
      });
    });
    
    // Start spray mission
    socket.on('spray_start_mission', async (data) => {
      logger.info(`🚁 Starting spray mission for Drone ${data.drone_id}`);
      const result = await sprayerService.startSprayMission(data.drone_id, io);
      socket.emit('spray_mission_started', result);
    });
    
    // Stop spray mission
    socket.on('spray_stop_mission', (data) => {
      logger.info(`⏹️ Stopping spray mission for Drone ${data.drone_id}`);
      const result = sprayerService.stopMission(data.drone_id, io);
      socket.emit('spray_mission_stopped', result);
    });
    
    // Confirm refill complete
    socket.on('spray_refill_complete', (data) => {
      logger.info(`✅ Refill confirmed for Drone ${data.drone_id}`);
      const result = sprayerService.confirmRefill(data.drone_id, io);
      socket.emit('spray_refill_confirmed', result);
    });
    
    // Request spray status
    socket.on('spray_request_status', (data) => {
      const status = sprayerService.getMissionStatus(data.drone_id);
      socket.emit('spray_status_update', status);
    });
    
    // Request tank status
    socket.on('spray_request_tank_status', (data) => {
      const tankStatus = sprayerService.getTankStatus(data.drone_id);
      socket.emit('spray_tank_status', tankStatus);
    });
    
    // Clear spray queue
    socket.on('spray_clear_queue', (data) => {
      logger.info(`🗑️ Clearing spray queue for Drone ${data.drone_id}`);
      const result = sprayerService.clearQueue(data.drone_id);
      socket.emit('spray_queue_cleared', result);
      io.emit('spray_queue_updated', {
        drone_id: data.drone_id,
        queue_length: 0
      });
    });
    
    // Handle disconnection
    socket.on('disconnect', () => {
      logger.info(`Client disconnected: ${socket.id}`);
      
      // If this was a registered Pi, mark it as disconnected
      if (socket.pi_id) {
        const pi = connectedPis.get(socket.pi_id);
        if (pi) {
          pi.connected = false;
          pi.disconnected_at = new Date().toISOString();
          logger.info(`🥧 Raspberry Pi disconnected: ${socket.pi_id}`);
          
          // Notify all clients
          io.emit('pi_disconnected', { pi_id: socket.pi_id });
          
          // Remove from map after a delay (in case it reconnects)
          setTimeout(() => {
            if (!pi.connected) {
              connectedPis.delete(socket.pi_id);
            }
          }, 60000); // 1 minute
        }
      }
    });
  });
}

module.exports = { setupSocketHandlers };
