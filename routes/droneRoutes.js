const express = require('express');
const router = express.Router();
const pixhawkService = require('../services/pixhawkServicePyMAVLink');

/**
 * GET /api/drones
 * Get list of all drones and their status
 */
router.get('/', (req, res) => {
  const droneList = pixhawkService.getDroneStatusList();
  res.json({ drones: droneList });
});

/**
 * GET /api/drone/:id/stats
 * Get stats for a specific drone
 */
router.get('/:id/stats', (req, res) => {
  const droneId = parseInt(req.params.id);
  const stats = pixhawkService.getDroneStats(droneId);
  
  if (!stats) {
    return res.status(404).json({ error: 'Drone not found or no stats available' });
  }
  
  res.json({ drone_id: droneId, stats });
});

/**
 * POST /api/drone/:id/command
 * Send command to drone (legacy endpoint, commands now via socket.io)
 */
router.post('/:id/command', (req, res) => {
  const droneId = parseInt(req.params.id);
  const { command, args } = req.body;
  
  const droneConnection = pixhawkService.getDroneConnection(droneId);
  
  if (!droneConnection || !droneConnection.connected) {
    return res.status(404).json({ error: 'Drone not connected' });
  }
  
  res.json({ 
    success: true, 
    message: `Command '${command}' sent to Drone ${droneId}` 
  });
});

module.exports = router;
