const fs = require('fs');
const path = require('path');
const logger = require('../config/logger');
const config = require('../config/config');

// Store active missions
const activeMissions = new Map();
const pendingMissions = new Map();

/**
 * Save mission metadata to JSON file
 */
function saveMissionMetadata(missionData) {
  try {
    const metadataPath = path.join(missionData.directory, 'metadata.json');
    const metadata = {
      mission_id: missionData.mission_id,
      drone_id: missionData.drone_id,
      start_time: missionData.start_time,
      end_time: missionData.end_time,
      duration_seconds: missionData.duration_seconds,
      duration_minutes: missionData.duration_minutes,
      mission_name: missionData.mission_name,
      description: missionData.description,
      parameters: missionData.parameters,
      statistics: {
        total_detections: missionData.total_detections,
        periodic_images_count: missionData.periodic_images_count || 0,
        total_frames_processed: missionData.telemetry_log.length
      },
      detections_summary: missionData.detections.map(d => ({
        detection_id: d.detection_id,
        timestamp: d.timestamp,
        latitude: d.latitude,
        longitude: d.longitude,
        confidence: d.confidence
      }))
    };
    
    fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
    logger.debug(`Metadata saved for mission ${missionData.mission_id}`);
  } catch (error) {
    logger.error(`Error saving mission metadata: ${error}`);
  }
}

/**
 * Export telemetry data to CSV
 */
function exportTelemetryCSV(missionData) {
  try {
    const csvPath = path.join(missionData.directory, 'telemetry.csv');
    
    const header = 'timestamp,latitude,longitude,altitude,heading,pitch,roll,groundspeed,battery_voltage,battery_percent,mode,armed,satellites,hdop\n';
    
    const rows = missionData.telemetry_log.map(t => {
      return [
        t.timestamp,
        t.latitude || 0,
        t.longitude || 0,
        t.altitude || 0,
        t.heading || 0,
        t.pitch || 0,
        t.roll || 0,
        t.groundspeed || 0,
        t.battery_voltage || 0,
        t.battery_percent || 0,
        t.mode || 'UNKNOWN',
        t.armed ? 'true' : 'false',
        t.satellites || 0,
        t.hdop || 0
      ].join(',');
    }).join('\n');
    
    fs.writeFileSync(csvPath, header + rows);
    logger.info(`✅ Telemetry CSV exported: ${csvPath} (${missionData.telemetry_log.length} records)`);
  } catch (error) {
    logger.error(`Error exporting telemetry CSV: ${error}`);
  }
}

/**
 * Initialize a new mission
 */
function initializeMission(droneId, missionParams = {}) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const mission_id = `mission_drone${droneId}_${timestamp}`;
  
  logger.info(`🚁 Starting mission: ${mission_id} on Drone ${droneId}`);
  
  // Create mission directory structure
  const missionDir = path.join(config.MISSIONS_DIR, mission_id);
  const imagesDir = path.join(missionDir, 'images');
  const detectionsDir = path.join(missionDir, 'detections');
  
  [missionDir, imagesDir, detectionsDir].forEach(dir => {
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  });
  
  // Initialize mission data
  const missionData = {
    mission_id: mission_id,
    drone_id: droneId,
    start_time: new Date().toISOString(),
    end_time: null,
    mission_name: missionParams.mission_name || 'Agricultural Survey Mission',
    description: missionParams.description || '',
    parameters: {
      altitude_m: missionParams.altitude || config.MISSION_DEFAULTS.altitude,
      speed_ms: missionParams.speed || config.MISSION_DEFAULTS.speed,
      field_size_acres: missionParams.field_size || config.MISSION_DEFAULTS.field_size_acres
    },
    total_detections: 0,
    periodic_images_count: 0,
    detections: [],
    telemetry_log: [],
    directory: missionDir,
    status: 'initializing'
  };
  
  activeMissions.set(droneId, missionData);
  saveMissionMetadata(missionData);
  
  missionData.status = 'ready';
  
  return missionData;
}

/**
 * Stop a mission and finalize data
 */
function stopMission(droneId) {
  const missionData = activeMissions.get(droneId);
  
  if (!missionData) {
    logger.warn(`No active mission for Drone ${droneId}`);
    return null;
  }
  
  logger.info(`🏁 Stopping mission: ${missionData.mission_id}`);
  
  missionData.end_time = new Date().toISOString();
  const duration_s = (new Date(missionData.end_time) - new Date(missionData.start_time)) / 1000;
  missionData.duration_seconds = duration_s;
  missionData.duration_minutes = (duration_s / 60).toFixed(2);
  
  saveMissionMetadata(missionData);
  exportTelemetryCSV(missionData);
  
  logger.info(`✅ Mission ${missionData.mission_id} completed: ${missionData.total_detections} detections in ${missionData.duration_minutes} min`);
  
  activeMissions.delete(droneId);
  
  return missionData;
}

/**
 * Get all missions from storage
 */
function getAllMissions() {
  try {
    const missions = fs.readdirSync(config.MISSIONS_DIR)
      .filter(name => name.startsWith('mission_'))
      .map(missionId => {
        const metadataPath = path.join(config.MISSIONS_DIR, missionId, 'metadata.json');
        if (fs.existsSync(metadataPath)) {
          const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
          return metadata;
        }
        return null;
      })
      .filter(m => m !== null)
      .sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
    
    return missions;
  } catch (error) {
    logger.error(`Error listing missions: ${error}`);
    return [];
  }
}

/**
 * Get mission by ID
 */
function getMissionById(missionId) {
  try {
    const metadataPath = path.join(config.MISSIONS_DIR, missionId, 'metadata.json');
    
    if (!fs.existsSync(metadataPath)) {
      return null;
    }
    
    const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
    return metadata;
  } catch (error) {
    logger.error(`Error fetching mission: ${error}`);
    return null;
  }
}

/**
 * Get detections for a mission
 */
function getMissionDetections(missionId) {
  try {
    const detectionsDir = path.join(config.MISSIONS_DIR, missionId, 'detections');
    
    if (!fs.existsSync(detectionsDir)) {
      return [];
    }
    
    const detections = fs.readdirSync(detectionsDir)
      .filter(f => f.endsWith('.json'))
      .map(file => {
        const data = fs.readFileSync(path.join(detectionsDir, file), 'utf8');
        return JSON.parse(data);
      });
    
    return detections;
  } catch (error) {
    logger.error(`Error fetching detections: ${error}`);
    return [];
  }
}

/**
 * Save detection image and metadata
 */
function saveDetection(droneId, detectionData) {
  const missionData = activeMissions.get(droneId);
  
  if (!missionData) {
    logger.warn(`Detection received from Drone ${droneId} but no active mission`);
    return null;
  }
  
  detectionData.mission_id = missionData.mission_id;
  
  logger.info(`🌾 [${missionData.mission_id}] Detection: ${detectionData.detection_id}`);
  
  if (detectionData.image) {
    const missionDir = path.join(config.MISSIONS_DIR, missionData.mission_id);
    const imagesDir = path.join(missionDir, 'images');
    const detectionsDir = path.join(missionDir, 'detections');
    
    [imagesDir, detectionsDir].forEach(dir => {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    });
    
    const imageFilename = `${detectionData.detection_id}.jpg`;
    const imagePath = path.join(imagesDir, imageFilename);
    
    try {
      const imageBuffer = Buffer.from(detectionData.image, 'base64');
      fs.writeFileSync(imagePath, imageBuffer);
      
      detectionData.image_url = `/missions/${missionData.mission_id}/images/${imageFilename}`;
      delete detectionData.image;
      
      logger.info(`   Image saved: ${imageFilename}`);
    } catch (error) {
      logger.error(`Error saving detection image: ${error}`);
    }
    
    const detectionFile = path.join(detectionsDir, `${detectionData.detection_id}.json`);
    const detectionMeta = {
      detection_id: detectionData.detection_id,
      timestamp: detectionData.timestamp,
      latitude: detectionData.latitude,
      longitude: detectionData.longitude,
      altitude: detectionData.altitude,
      confidence: detectionData.confidence,
      area: detectionData.area,
      bbox: detectionData.bbox,
      centroid: detectionData.centroid,
      heading: detectionData.heading,
      drone_mode: detectionData.drone_mode,
      image_path: `images/${imageFilename}`
    };
    
    fs.writeFileSync(detectionFile, JSON.stringify(detectionMeta, null, 2));
    
    missionData.total_detections++;
    missionData.detections.push(detectionMeta);
  }
  
  return detectionData;
}

/**
 * Save periodic image
 */
function savePeriodicImage(droneId, imageData) {
  const missionData = activeMissions.get(droneId);
  
  if (!missionData) {
    logger.warn(`Periodic image received from Drone ${droneId} but no active mission`);
    return false;
  }
  
  try {
    const missionDir = path.join(config.MISSIONS_DIR, missionData.mission_id);
    const periodicImagesDir = path.join(missionDir, 'periodic_images');
    
    if (!fs.existsSync(periodicImagesDir)) {
      fs.mkdirSync(periodicImagesDir, { recursive: true });
    }
    
    const imageFilename = `${imageData.image_id}.jpg`;
    const imagePath = path.join(periodicImagesDir, imageFilename);
    
    const imageBuffer = Buffer.from(imageData.image, 'base64');
    fs.writeFileSync(imagePath, imageBuffer);
    
    const metadataPath = path.join(periodicImagesDir, `${imageData.image_id}.json`);
    const metadata = {
      image_id: imageData.image_id,
      timestamp: imageData.timestamp,
      latitude: imageData.latitude,
      longitude: imageData.longitude,
      altitude: imageData.altitude,
      heading: imageData.heading,
      mode: imageData.mode
    };
    fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
    
    if (!missionData.periodic_images_count) {
      missionData.periodic_images_count = 0;
    }
    missionData.periodic_images_count++;
    
    logger.debug(`📷 Periodic image saved: ${imageFilename} (${missionData.periodic_images_count} total)`);
    
    return true;
  } catch (error) {
    logger.error(`Error saving periodic image: ${error}`);
    return false;
  }
}

/**
 * Log telemetry to active mission
 */
function logTelemetry(droneId, telemetryData) {
  const missionData = activeMissions.get(droneId);
  
  if (missionData) {
    const telem = telemetryData.telemetry;
    missionData.telemetry_log.push({
      timestamp: telemetryData.timestamp,
      latitude: telem.gps?.lat,
      longitude: telem.gps?.lon,
      altitude: telem.altitude,
      heading: telem.heading,
      pitch: telem.attitude?.pitch,
      roll: telem.attitude?.roll,
      groundspeed: telem.groundspeed,
      battery_voltage: telem.battery?.voltage,
      battery_percent: telem.battery?.remaining,
      mode: telem.flight_mode,
      armed: telem.armed,
      satellites: telem.gps?.satellites_visible,
      hdop: telem.gps?.hdop
    });
  }
}

module.exports = {
  activeMissions,
  pendingMissions,
  initializeMission,
  stopMission,
  getAllMissions,
  getMissionById,
  getMissionDetections,
  saveDetection,
  savePeriodicImage,
  logTelemetry,
  saveMissionMetadata,
  exportTelemetryCSV
};
