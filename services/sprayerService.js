const logger = require('../config/logger');
const EventEmitter = require('events');

/**
 * Sprayer Service
 * Manages automated spray missions with tank refill management
 */
class SprayerService extends EventEmitter {
  constructor() {
    super();
    
    // Sprayer configuration
    this.config = {
      tank_capacity_ml: 1000,              // 1 liter tank
      spray_volume_per_target_ml: 50,      // 50ml per spray target
      refill_threshold_ml: 100,            // Trigger refill at 100ml
      spray_duration_sec: 3,               // Spray for 3 seconds
      loiter_time_sec: 5,                  // Loiter 5 sec at target
      spray_altitude_m: 5,                 // Spray at 5m altitude
      auto_resume_after_refill: true,      // Auto-resume mission after refill
      require_manual_confirmation: true    // Require operator confirmation
    };
    
    // Active spray missions (one per drone)
    this.activeMissions = new Map();
    
    // Spray queue for each drone
    this.sprayQueues = new Map();
    
    // Tank status for each drone
    this.tankStatus = new Map();
  }
  
  /**
   * Initialize sprayer for a drone
   */
  initializeSprayer(droneId) {
    if (!this.tankStatus.has(droneId)) {
      this.tankStatus.set(droneId, {
        drone_id: droneId,
        current_volume_ml: this.config.tank_capacity_ml,
        capacity_ml: this.config.tank_capacity_ml,
        refills_count: 0,
        last_refill_time: new Date().toISOString(),
        total_sprayed_ml: 0
      });
      
      this.sprayQueues.set(droneId, []);
      
      logger.info(`🎯 Sprayer initialized for Drone ${droneId}: Tank ${this.config.tank_capacity_ml}ml`);
    }
    
    return this.tankStatus.get(droneId);
  }
  
  /**
   * Add detection targets to spray queue
   */
  queueTargets(droneId, detections) {
    this.initializeSprayer(droneId);
    
    const queue = this.sprayQueues.get(droneId);
    
    // Convert detections to spray targets
    const targets = detections.map((det, index) => ({
      target_id: `spray_${droneId}_${Date.now()}_${index}`,
      detection_id: det.detection_id || det.target_id,
      latitude: det.latitude,
      longitude: det.longitude,
      altitude: det.altitude || this.config.spray_altitude_m,
      spray_volume_ml: this.config.spray_volume_per_target_ml,
      status: 'queued',
      queued_at: new Date().toISOString(),
      sprayed_at: null,
      confidence: det.confidence,
      priority: det.priority || 1
    }));
    
    queue.push(...targets);
    
    logger.info(`💧 Queued ${targets.length} spray targets for Drone ${droneId}. Total queue: ${queue.length}`);
    
    this.emit('targets_queued', {
      drone_id: droneId,
      targets_added: targets.length,
      total_queued: queue.length
    });
    
    return {
      success: true,
      targets_added: targets.length,
      total_queued: queue.length
    };
  }
  
  /**
   * Start automated spray mission
   */
  async startSprayMission(droneId, io) {
    this.initializeSprayer(droneId);
    
    const queue = this.sprayQueues.get(droneId);
    const tankStatus = this.tankStatus.get(droneId);
    
    if (queue.length === 0) {
      return {
        success: false,
        error: 'No targets in spray queue'
      };
    }
    
    // Check if enough spray for at least one target + return home
    const minRequired = this.config.spray_volume_per_target_ml + 50; // Safety margin
    if (tankStatus.current_volume_ml < minRequired) {
      return {
        success: false,
        error: `Insufficient spray volume. Need ${minRequired}ml, have ${tankStatus.current_volume_ml}ml. Refill required.`
      };
    }
    
    const mission = {
      mission_id: `spray_mission_${droneId}_${Date.now()}`,
      drone_id: droneId,
      status: 'active',
      started_at: new Date().toISOString(),
      ended_at: null,
      current_target_index: 0,
      total_targets: queue.length,
      targets_completed: 0,
      targets_failed: 0,
      paused_for_refill: false,
      refills_during_mission: 0,
      home_location: null,
      last_sprayed_index: -1
    };
    
    this.activeMissions.set(droneId, mission);
    
    logger.info(`🚁 Starting spray mission for Drone ${droneId}: ${queue.length} targets`);
    
    this.emit('mission_started', {
      drone_id: droneId,
      mission_id: mission.mission_id,
      total_targets: queue.length,
      tank_volume: tankStatus.current_volume_ml
    });
    
    if (io) {
      io.emit('spray_mission_started', {
        drone_id: droneId,
        mission_id: mission.mission_id,
        total_targets: queue.length,
        tank_status: tankStatus
      });
    }
    
    // Start executing spray mission
    this.executeSprayMission(droneId, io);
    
    return {
      success: true,
      mission_id: mission.mission_id,
      total_targets: queue.length
    };
  }
  
  /**
   * Execute spray mission (main control loop)
   */
  async executeSprayMission(droneId, io) {
    const mission = this.activeMissions.get(droneId);
    const queue = this.sprayQueues.get(droneId);
    const tankStatus = this.tankStatus.get(droneId);
    
    if (!mission || mission.status !== 'active') {
      return;
    }
    
    logger.info(`▶️ Executing spray mission for Drone ${droneId}`);
    
    // Get next target
    const target = queue[mission.current_target_index];
    
    if (!target) {
      // Mission complete
      this.completeMission(droneId, io);
      return;
    }
    
    // Check if we have enough volume for this target + RTL margin
    const requiredVolume = this.config.spray_volume_per_target_ml + 50;
    
    if (tankStatus.current_volume_ml < requiredVolume) {
      // Need refill
      logger.warn(`⚠️ Low spray volume: ${tankStatus.current_volume_ml}ml. Initiating refill sequence...`);
      this.initiateRefillSequence(droneId, io);
      return;
    }
    
    // Emit next target to frontend
    this.emit('next_target', {
      drone_id: droneId,
      target: target,
      progress: ((mission.current_target_index / mission.total_targets) * 100).toFixed(1)
    });
    
    if (io) {
      io.emit('spray_next_target', {
        drone_id: droneId,
        target: target,
        target_index: mission.current_target_index,
        total_targets: mission.total_targets,
        tank_volume: tankStatus.current_volume_ml
      });
    }
    
    logger.info(`🎯 Target ${mission.current_target_index + 1}/${mission.total_targets}: [${target.latitude}, ${target.longitude}]`);
  }
  
  /**
   * Handle spray completion for a target
   */
  onSprayComplete(droneId, targetId, success, io) {
    const mission = this.activeMissions.get(droneId);
    const queue = this.sprayQueues.get(droneId);
    const tankStatus = this.tankStatus.get(droneId);
    
    if (!mission) return;
    
    const target = queue[mission.current_target_index];
    
    if (target && target.target_id === targetId) {
      if (success) {
        // Update target status
        target.status = 'completed';
        target.sprayed_at = new Date().toISOString();
        
        // Update tank volume
        tankStatus.current_volume_ml -= this.config.spray_volume_per_target_ml;
        tankStatus.total_sprayed_ml += this.config.spray_volume_per_target_ml;
        
        mission.targets_completed++;
        mission.last_sprayed_index = mission.current_target_index;
        
        logger.info(`✅ Spray completed for target ${targetId}. Tank: ${tankStatus.current_volume_ml}ml remaining`);
        
        if (io) {
          io.emit('spray_target_complete', {
            drone_id: droneId,
            target_id: targetId,
            targets_completed: mission.targets_completed,
            total_targets: mission.total_targets,
            tank_status: tankStatus
          });
        }
      } else {
        target.status = 'failed';
        mission.targets_failed++;
        
        logger.error(`❌ Spray failed for target ${targetId}`);
      }
      
      // Move to next target
      mission.current_target_index++;
      
      // Continue mission after delay
      setTimeout(() => {
        this.executeSprayMission(droneId, io);
      }, 2000);
    }
  }
  
  /**
   * Initiate refill sequence
   */
  initiateRefillSequence(droneId, io) {
    const mission = this.activeMissions.get(droneId);
    const tankStatus = this.tankStatus.get(droneId);
    
    if (!mission) return;
    
    mission.status = 'refilling';
    mission.paused_for_refill = true;
    mission.refills_during_mission++;
    
    logger.info(`🔄 Initiating refill sequence for Drone ${droneId}`);
    logger.info(`   Completed: ${mission.targets_completed}/${mission.total_targets}`);
    logger.info(`   Tank: ${tankStatus.current_volume_ml}ml / ${tankStatus.capacity_ml}ml`);
    
    this.emit('refill_required', {
      drone_id: droneId,
      mission_id: mission.mission_id,
      targets_completed: mission.targets_completed,
      targets_remaining: mission.total_targets - mission.current_target_index,
      tank_volume: tankStatus.current_volume_ml
    });
    
    if (io) {
      io.emit('spray_refill_required', {
        drone_id: droneId,
        mission_id: mission.mission_id,
        targets_completed: mission.targets_completed,
        targets_remaining: mission.total_targets - mission.current_target_index,
        tank_status: tankStatus,
        message: 'Returning to home for refill'
      });
    }
  }
  
  /**
   * Confirm refill complete
   */
  confirmRefill(droneId, io) {
    const mission = this.activeMissions.get(droneId);
    const tankStatus = this.tankStatus.get(droneId);
    
    if (!mission) {
      return {
        success: false,
        error: 'No active mission'
      };
    }
    
    // Refill tank
    tankStatus.current_volume_ml = tankStatus.capacity_ml;
    tankStatus.refills_count++;
    tankStatus.last_refill_time = new Date().toISOString();
    
    mission.status = 'active';
    mission.paused_for_refill = false;
    
    logger.info(`✅ Refill confirmed for Drone ${droneId}. Tank: ${tankStatus.current_volume_ml}ml`);
    logger.info(`   Resuming mission: ${mission.total_targets - mission.current_target_index} targets remaining`);
    
    this.emit('refill_complete', {
      drone_id: droneId,
      tank_volume: tankStatus.current_volume_ml,
      targets_remaining: mission.total_targets - mission.current_target_index
    });
    
    if (io) {
      io.emit('spray_refill_complete', {
        drone_id: droneId,
        mission_id: mission.mission_id,
        tank_status: tankStatus,
        targets_remaining: mission.total_targets - mission.current_target_index,
        message: 'Refill complete - resuming mission'
      });
    }
    
    // Resume mission
    if (this.config.auto_resume_after_refill) {
      setTimeout(() => {
        this.executeSprayMission(droneId, io);
      }, 3000);
    }
    
    return {
      success: true,
      tank_volume: tankStatus.current_volume_ml,
      targets_remaining: mission.total_targets - mission.current_target_index
    };
  }
  
  /**
   * Complete spray mission
   */
  completeMission(droneId, io) {
    const mission = this.activeMissions.get(droneId);
    const tankStatus = this.tankStatus.get(droneId);
    
    if (!mission) return;
    
    mission.status = 'completed';
    mission.ended_at = new Date().toISOString();
    
    const duration = (new Date(mission.ended_at) - new Date(mission.started_at)) / 1000;
    
    logger.info(`🏁 Spray mission completed for Drone ${droneId}`);
    logger.info(`   Targets: ${mission.targets_completed}/${mission.total_targets}`);
    logger.info(`   Failed: ${mission.targets_failed}`);
    logger.info(`   Refills: ${mission.refills_during_mission}`);
    logger.info(`   Duration: ${(duration / 60).toFixed(1)} minutes`);
    logger.info(`   Spray used: ${tankStatus.total_sprayed_ml}ml`);
    
    this.emit('mission_complete', {
      drone_id: droneId,
      mission: mission,
      tank_status: tankStatus
    });
    
    if (io) {
      io.emit('spray_mission_complete', {
        drone_id: droneId,
        mission_id: mission.mission_id,
        targets_completed: mission.targets_completed,
        targets_failed: mission.targets_failed,
        refills: mission.refills_during_mission,
        duration_seconds: duration,
        tank_status: tankStatus
      });
    }
    
    // Clean up
    this.activeMissions.delete(droneId);
    this.sprayQueues.set(droneId, []); // Clear queue
  }
  
  /**
   * Stop spray mission
   */
  stopMission(droneId, io) {
    const mission = this.activeMissions.get(droneId);
    
    if (!mission) {
      return {
        success: false,
        error: 'No active mission'
      };
    }
    
    mission.status = 'stopped';
    mission.ended_at = new Date().toISOString();
    
    logger.info(`⏹️ Spray mission stopped for Drone ${droneId}`);
    
    if (io) {
      io.emit('spray_mission_stopped', {
        drone_id: droneId,
        mission_id: mission.mission_id,
        targets_completed: mission.targets_completed,
        targets_remaining: mission.total_targets - mission.current_target_index
      });
    }
    
    this.activeMissions.delete(droneId);
    
    return {
      success: true,
      targets_completed: mission.targets_completed
    };
  }
  
  /**
   * Get spray mission status
   */
  getMissionStatus(droneId) {
    const mission = this.activeMissions.get(droneId);
    const queue = this.sprayQueues.get(droneId) || [];
    const tankStatus = this.tankStatus.get(droneId);
    
    return {
      active_mission: mission || null,
      queue_length: queue.length,
      tank_status: tankStatus || null,
      config: this.config
    };
  }
  
  /**
   * Get tank status
   */
  getTankStatus(droneId) {
    this.initializeSprayer(droneId);
    return this.tankStatus.get(droneId);
  }
  
  /**
   * Update configuration
   */
  updateConfig(newConfig) {
    this.config = { ...this.config, ...newConfig };
    logger.info(`⚙️ Sprayer config updated:`, this.config);
    return this.config;
  }
  
  /**
   * Get spray queue
   */
  getQueue(droneId) {
    return this.sprayQueues.get(droneId) || [];
  }
  
  /**
   * Clear spray queue
   */
  clearQueue(droneId) {
    this.sprayQueues.set(droneId, []);
    logger.info(`🗑️ Spray queue cleared for Drone ${droneId}`);
    return { success: true };
  }
}

// Create singleton instance
const sprayerService = new SprayerService();

module.exports = sprayerService;
