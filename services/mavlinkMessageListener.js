/**
 * MAVLink STATUSTEXT Message Listener
 * 
 * Listens for detection and image metadata from Pi over long-range radio
 * Converts MAVLink STATUSTEXT messages back to Socket.IO events for dashboard
 * 
 * This enables the GCS to receive data when the drone is out of WiFi range
 * but still connected via MAVLink radio telemetry.
 */

const logger = require('../config/logger');
const axios = require('axios');

const PYMAVLINK_SERVICE_URL = process.env.PYMAVLINK_URL || 'http://localhost:5000';
const POLL_INTERVAL_MS = 500; // Poll every 500ms

class MAVLinkMessageListener {
  constructor(io) {
    this.io = io;
    this.listening = false;
    this.pollInterval = null;
    this.lastMessageIds = new Set(); // Prevent duplicate processing
    this.messageCache = [];
    this.maxCacheSize = 100;
  }

  /**
   * Start listening for MAVLink STATUSTEXT messages from all drones
   */
  start() {
    if (this.listening) {
      logger.warn('MAVLink message listener already running');
      return;
    }
    
    this.listening = true;
    this.pollInterval = setInterval(() => this.pollMessages(), POLL_INTERVAL_MS);
    logger.info('📡 MAVLink message listener started (polling every 500ms)');
  }

  /**
   * Stop listening
   */
  stop() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
    this.listening = false;
    this.lastMessageIds.clear();
    logger.info('📡 MAVLink message listener stopped');
  }

  /**
   * Poll PyMAVLink service for new STATUSTEXT messages
   */
  async pollMessages() {
    try {
      // Query PyMAVLink service for recent STATUSTEXT messages
      const response = await axios.get(`${PYMAVLINK_SERVICE_URL}/messages/statustext`, {
        timeout: 1000
      });
      
      if (response.data && response.data.messages) {
        for (const msg of response.data.messages) {
          // Create unique ID to prevent duplicate processing
          const msgId = `${msg.drone_id}_${msg.timestamp}_${msg.text}`;
          
          if (!this.lastMessageIds.has(msgId)) {
            this.lastMessageIds.add(msgId);
            this.parseMessage(msg.text, msg.drone_id);
            
            // Trim cache to prevent memory leak
            if (this.lastMessageIds.size > this.maxCacheSize) {
              const firstId = this.lastMessageIds.values().next().value;
              this.lastMessageIds.delete(firstId);
            }
          }
        }
      }
    } catch (error) {
      // Silent fail - PyMAVLink service might not be running yet or no messages available
      // Only log if it's not a connection error
      if (error.code !== 'ECONNREFUSED' && error.code !== 'ETIMEDOUT') {
        logger.debug(`MAVLink message poll error: ${error.message}`);
      }
    }
  }

  /**
   * Parse MAVLink STATUSTEXT message and emit appropriate Socket.IO event
   * 
   * Message formats:
   * - DET|ID|LAT|LON|CONF|AREA - Detection event
   * - IMG|ID|LAT|LON|TYPE|MISSION - Image metadata
   * - DSTAT|TOTAL|ACTIVE|MISSION - Detection statistics
   * - STAT|CPU|MEM|DISK|TEMP - System statistics
   */
  parseMessage(text, droneId) {
    try {
      // Detection message: DET|ID|LAT|LON|CONF|AREA
      if (text.startsWith('DET|')) {
        const parts = text.split('|');
        if (parts.length >= 6) {
          const detection = {
            detection_id: parts[1],
            latitude: parseFloat(parts[2]),
            longitude: parseFloat(parts[3]),
            confidence: parseFloat(parts[4]),
            detection_area: parseInt(parts[5]),
            pi_id: `detection_drone_pi_${droneId}`,
            mission_id: 'unknown', // Not included in compact message
            source: 'mavlink',
            timestamp: new Date().toISOString(),
            transmission_method: 'MAVLink Radio'
          };
          
          // Emit to dashboard
          this.io.emit('crop_detection', detection);
          logger.info(`📡 MAVLink Detection received from Drone ${droneId}: ${detection.detection_id}`);
        }
      }
      
      // Image metadata message: IMG|ID|LAT|LON|TYPE|MISSION
      else if (text.startsWith('IMG|')) {
        const parts = text.split('|');
        if (parts.length >= 6) {
          const imageMetadata = {
            image_id: parts[1],
            latitude: parseFloat(parts[2]),
            longitude: parseFloat(parts[3]),
            image_type: parts[4],
            mission_id: parts[5],
            pi_id: `detection_drone_pi_${droneId}`,
            source: 'mavlink',
            stored_locally: true,
            timestamp: new Date().toISOString(),
            transmission_method: 'MAVLink Radio'
          };
          
          // Emit to dashboard (notify image was captured and stored locally)
          this.io.emit('periodic_image_metadata', imageMetadata);
          logger.info(`📡 MAVLink Image metadata received from Drone ${droneId}: ${imageMetadata.image_id}`);
        }
      }
      
      // Detection statistics: DSTAT|TOTAL|ACTIVE|MISSION
      else if (text.startsWith('DSTAT|')) {
        const parts = text.split('|');
        if (parts.length >= 4) {
          const stats = {
            total_detections: parseInt(parts[1]),
            detection_active: Boolean(parseInt(parts[2])),
            mission_id: parts[3],
            pi_id: `detection_drone_pi_${droneId}`,
            source: 'mavlink',
            timestamp: new Date().toISOString()
          };
          
          this.io.emit('detection_stats', stats);
          logger.debug(`📡 MAVLink Detection stats from Drone ${droneId}: ${stats.total_detections} total`);
        }
      }
      
      // System statistics: STAT|CPU|MEM|DISK|TEMP
      else if (text.startsWith('STAT|')) {
        const parts = text.split('|');
        if (parts.length >= 5) {
          const systemStats = {
            cpu_usage: parseFloat(parts[1]),
            memory_usage: parseFloat(parts[2]),
            disk_usage: parseFloat(parts[3]),
            cpu_temp: parseFloat(parts[4]),
            pi_id: `detection_drone_pi_${droneId}`,
            source: 'mavlink',
            timestamp: new Date().toISOString(),
            transmission_method: 'MAVLink Radio'
          };
          
          // Emit to dashboard
          this.io.emit('system_stats', {
            pi_id: systemStats.pi_id,
            stats: systemStats
          });
          logger.info(`📡 MAVLink System stats from Drone ${droneId}: CPU ${systemStats.cpu_usage.toFixed(1)}% MEM ${systemStats.memory_usage.toFixed(1)}% TEMP ${systemStats.cpu_temp.toFixed(1)}°C`);
        }
      }
      
      // Detection metadata (multi-part, extended info)
      else if (text.startsWith('DMET')) {
        // Handle multi-part detection metadata if needed
        logger.debug(`📡 MAVLink Detection metadata received: ${text}`);
      }
      
    } catch (error) {
      logger.error(`Error parsing MAVLink message "${text}": ${error.message}`);
    }
  }

  /**
   * Get listener statistics
   */
  getStats() {
    return {
      listening: this.listening,
      messagesProcessed: this.lastMessageIds.size,
      cacheSize: this.messageCache.length
    };
  }
}

module.exports = MAVLinkMessageListener;
