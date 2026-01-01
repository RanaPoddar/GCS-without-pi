const express = require('express');
const router = express.Router();
const waypointService = require('../services/waypointService');

/**
 * GET /api/waypoints
 * Get all waypoints
 */
router.get('/', (req, res) => {
  const waypoints = waypointService.getAllWaypoints();
  res.json({ waypoints });
});

/**
 * GET /api/waypoints/recent
 * Get recent waypoints
 */
router.get('/recent', (req, res) => {
  const limit = parseInt(req.query.limit) || 10;
  const recent = waypointService.getRecentWaypoints(limit);
  res.json({ waypoints: recent });
});

/**
 * DELETE /api/waypoints/:id
 * Delete a specific waypoint
 */
router.delete('/:id', (req, res) => {
  const waypointId = req.params.id;
  const success = waypointService.deleteWaypoint(waypointId);
  
  if (!success) {
    return res.status(404).json({ error: 'Waypoint not found' });
  }
  
  res.json({ success: true, message: 'Waypoint deleted' });
});

/**
 * DELETE /api/waypoints
 * Clear all waypoints
 */
router.delete('/', (req, res) => {
  waypointService.clearAllWaypoints();
  res.json({ success: true, message: 'All waypoints cleared' });
});

module.exports = router;
