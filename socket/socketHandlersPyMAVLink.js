const logger = require('../config/logger');
const pixhawkService = require('../services/pixhawkServicePyMAVLink');
const missionService = require('../services/missionService');
const waypointService = require('../services/waypointService');

/**
 * Setup all Socket.IO event handlers for PyMAVLink
 */
function setupSocketHandlers(io) {
  io.on('connection', (socket) => {
    logger.info(`Dashboard client connected: ${socket.id}`);
    
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

    // ========================================
    //      Mission Detection & Image Capture |
    // ========================================

    socket.on('crop_detection', (data) => {
      const droneId = data.drone_id || 1;
      const detectionData = missionService.saveDetection(droneId, data);
      
      if (detectionData) {
        io.emit('crop_detection', detectionData);
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
    
    // Handle disconnection
    socket.on('disconnect', () => {
      logger.info(`Dashboard client disconnected: ${socket.id}`);
    });
  });
}

module.exports = { setupSocketHandlers };
