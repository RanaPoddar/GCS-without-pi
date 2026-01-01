const fs = require('fs');
const logger = require('../config/logger');
const config = require('../config/config');

// Store marked waypoints
const markedWaypoints = [];

/**
 * Load waypoints from file on startup
 */
function loadWaypoints() {
  try {
    if (fs.existsSync(config.WAYPOINTS_FILE)) {
      const data = fs.readFileSync(config.WAYPOINTS_FILE, 'utf8');
      const loaded = JSON.parse(data);
      markedWaypoints.push(...loaded);
      logger.info(`Loaded ${loaded.length} waypoints from file`);
    }
  } catch (error) {
    logger.error('Error loading waypoints:', error);
  }
}

/**
 * Save waypoints to file
 */
function saveWaypoints() {
  try {
    fs.writeFileSync(config.WAYPOINTS_FILE, JSON.stringify(markedWaypoints, null, 2));
    logger.debug('Waypoints saved to file');
  } catch (error) {
    logger.error('Error saving waypoints:', error);
  }
}

/**
 * Get all waypoints
 */
function getAllWaypoints() {
  return markedWaypoints;
}

/**
 * Get recent waypoints
 */
function getRecentWaypoints(limit = 10) {
  return markedWaypoints.slice(-limit).reverse();
}

/**
 * Add a new waypoint
 */
function addWaypoint(waypointData) {
  logger.info(`📍 Waypoint marked: (${waypointData.latitude.toFixed(6)}, ${waypointData.longitude.toFixed(6)})`);
  markedWaypoints.push(waypointData);
  saveWaypoints();
  return waypointData;
}

/**
 * Delete waypoint by ID
 */
function deleteWaypoint(waypointId) {
  const index = markedWaypoints.findIndex(wp => wp.waypoint_id === waypointId);
  
  if (index === -1) {
    return false;
  }
  
  markedWaypoints.splice(index, 1);
  saveWaypoints();
  return true;
}

/**
 * Clear all waypoints
 */
function clearAllWaypoints() {
  markedWaypoints.length = 0;
  saveWaypoints();
}

module.exports = {
  markedWaypoints,
  loadWaypoints,
  saveWaypoints,
  getAllWaypoints,
  getRecentWaypoints,
  addWaypoint,
  deleteWaypoint,
  clearAllWaypoints
};
