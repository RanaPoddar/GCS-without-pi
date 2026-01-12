const express = require('express');
const router = express.Router();
const logger = require('../config/logger');
const sprayerService = require('../services/sprayerService');
const axios = require('axios');

const PYMAVLINK_URL = process.env.PYMAVLINK_URL || 'http://localhost:5000';

/**
 * Queue spray targets for a drone
 * POST /api/sprayer/:droneId/queue
 */
router.post('/:droneId/queue', (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const { detections } = req.body;
    
    if (!detections || !Array.isArray(detections)) {
      return res.status(400).json({ error: 'Invalid detections array' });
    }
    
    const result = sprayerService.queueTargets(droneId, detections);
    res.json(result);
  } catch (error) {
    logger.error(`Error queueing spray targets: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Start spray mission
 * POST /api/sprayer/:droneId/start
 */
router.post('/:droneId/start', async (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const io = req.app.get('io');
    
    const result = await sprayerService.startSprayMission(droneId, io);
    res.json(result);
  } catch (error) {
    logger.error(`Error starting spray mission: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Stop spray mission
 * POST /api/sprayer/:droneId/stop
 */
router.post('/:droneId/stop', (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const io = req.app.get('io');
    
    const result = sprayerService.stopMission(droneId, io);
    res.json(result);
  } catch (error) {
    logger.error(`Error stopping spray mission: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get spray mission status
 * GET /api/sprayer/:droneId/status
 */
router.get('/:droneId/status', (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const status = sprayerService.getMissionStatus(droneId);
    res.json(status);
  } catch (error) {
    logger.error(`Error getting spray status: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get tank status
 * GET /api/sprayer/:droneId/tank
 */
router.get('/:droneId/tank', (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const tankStatus = sprayerService.getTankStatus(droneId);
    res.json(tankStatus);
  } catch (error) {
    logger.error(`Error getting tank status: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Confirm refill complete
 * POST /api/sprayer/:droneId/refill-complete
 */
router.post('/:droneId/refill-complete', (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const io = req.app.get('io');
    
    const result = sprayerService.confirmRefill(droneId, io);
    res.json(result);
  } catch (error) {
    logger.error(`Error confirming refill: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Update sprayer configuration
 * PUT /api/sprayer/config
 */
router.put('/config', (req, res) => {
  try {
    const newConfig = req.body;
    const config = sprayerService.updateConfig(newConfig);
    res.json({ success: true, config });
  } catch (error) {
    logger.error(`Error updating config: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get spray queue
 * GET /api/sprayer/:droneId/queue
 */
router.get('/:droneId/queue', (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const queue = sprayerService.getQueue(droneId);
    res.json({ queue, count: queue.length });
  } catch (error) {
    logger.error(`Error getting spray queue: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Clear spray queue
 * DELETE /api/sprayer/:droneId/queue
 */
router.delete('/:droneId/queue', (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const result = sprayerService.clearQueue(droneId);
    res.json(result);
  } catch (error) {
    logger.error(`Error clearing spray queue: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Manual spray at specific location
 * POST /api/sprayer/:droneId/spray-at-location
 */
router.post('/:droneId/spray-at-location', async (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const { latitude, longitude, altitude, spray_duration_sec, loiter_time_sec } = req.body;
    
    if (!latitude || !longitude) {
      return res.status(400).json({ error: 'Missing latitude or longitude' });
    }
    
    // Call PyMAVLink service to spray at target
    const response = await axios.post(
      `${PYMAVLINK_URL}/drone/${droneId}/spray/spray_at_target`,
      {
        latitude,
        longitude,
        altitude: altitude || 5,
        spray_duration_sec: spray_duration_sec || 3,
        loiter_time_sec: loiter_time_sec || 5
      }
    );
    
    res.json(response.data);
  } catch (error) {
    logger.error(`Error spraying at location: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Activate spray manually
 * POST /api/sprayer/:droneId/activate
 */
router.post('/:droneId/activate', async (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const { duration_sec, servo_channel, pwm_value } = req.body;
    
    const response = await axios.post(
      `${PYMAVLINK_URL}/drone/${droneId}/spray/activate`,
      {
        duration_sec: duration_sec || 3,
        servo_channel: servo_channel || 9,
        pwm_value: pwm_value || 1900
      }
    );
    
    res.json(response.data);
  } catch (error) {
    logger.error(`Error activating spray: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Deactivate spray manually
 * POST /api/sprayer/:droneId/deactivate
 */
router.post('/:droneId/deactivate', async (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const { servo_channel, pwm_value } = req.body;
    
    const response = await axios.post(
      `${PYMAVLINK_URL}/drone/${droneId}/spray/deactivate`,
      {
        servo_channel: servo_channel || 9,
        pwm_value: pwm_value || 1100
      }
    );
    
    res.json(response.data);
  } catch (error) {
    logger.error(`Error deactivating spray: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Execute next spray target (called by automation)
 * POST /api/sprayer/:droneId/execute-next
 */
router.post('/:droneId/execute-next', async (req, res) => {
  try {
    const droneId = parseInt(req.params.droneId);
    const io = req.app.get('io');
    
    const status = sprayerService.getMissionStatus(droneId);
    
    if (!status.active_mission) {
      return res.status(400).json({ error: 'No active spray mission' });
    }
    
    const queue = sprayerService.getQueue(droneId);
    const mission = status.active_mission;
    const target = queue[mission.current_target_index];
    
    if (!target) {
      return res.status(400).json({ error: 'No more targets in queue' });
    }
    
    // Send spray command to PyMAVLink
    const response = await axios.post(
      `${PYMAVLINK_URL}/drone/${droneId}/spray/spray_at_target`,
      {
        latitude: target.latitude,
        longitude: target.longitude,
        altitude: target.altitude,
        spray_duration_sec: sprayerService.config.spray_duration_sec,
        loiter_time_sec: sprayerService.config.loiter_time_sec
      }
    );
    
    if (response.data.success) {
      // Simulate completion after spray duration (in real scenario, monitor telemetry)
      setTimeout(() => {
        sprayerService.onSprayComplete(droneId, target.target_id, true, io);
      }, (sprayerService.config.loiter_time_sec + sprayerService.config.spray_duration_sec) * 1000);
    }
    
    res.json({
      success: true,
      target: target,
      pymavlink_response: response.data
    });
  } catch (error) {
    logger.error(`Error executing next spray: ${error}`);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
