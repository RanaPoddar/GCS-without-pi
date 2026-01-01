const { SerialPort } = require('serialport');
const { MavLinkPacketSplitter, MavLinkPacketParser, MavLinkProtocolV2, minimal, common, ardupilotmega } = require('node-mavlink');
const EventEmitter = require('events');

class PixhawkConnection extends EventEmitter {
  constructor(droneId, portPath, baudRate = 57600, logger) {
    super();
    this.droneId = droneId;
    this.portPath = portPath;
    this.baudRate = baudRate;
    this.logger = logger;
    this.port = null;
    this.reader = null;
    this.parser = null;
    this.connected = false;
    this.heartbeatInterval = null;
    this.sequenceNumber = 0;
    this.telemetryData = {
      drone_id: droneId,
      gps: { lat: 0, lon: 0, alt: 0, satellites_visible: 0, fix_type: 0, hdop: 0 },
      battery: { voltage: 0, current: 0, remaining: 100 },
      attitude: { roll: 0, pitch: 0, yaw: 0 },
      altitude: 0,
      heading: 0,
      groundspeed: 0,
      flight_mode: 'UNKNOWN',
      armed: false,
      system_status: 'UNKNOWN'
    };
    
    // MAVLink system/component IDs
    this.systemId = 255; // GCS
    this.componentId = 190; // GCS component
    this.targetSystem = 1; // Pixhawk
    this.targetComponent = 1; // Autopilot
  }

  async connect() {
    return new Promise((resolve, reject) => {
      try {
        this.logger.info(`[Drone ${this.droneId}] Connecting to Pixhawk on ${this.portPath} @ ${this.baudRate}`);
        
        // Create serial port connection
        this.port = new SerialPort({
          path: this.portPath,
          baudRate: this.baudRate,
          dataBits: 8,
          parity: 'none',
          stopBits: 1,
          autoOpen: false  // Don't auto-open, we'll open manually
        });

        // Setup MAVLink parser - pipe splitter directly to parser
        // IMPORTANT: Pass message definitions to parser so it can decode messages
        const splitter = new MavLinkPacketSplitter();
        const parser = new MavLinkPacketParser(ardupilotmega.REGISTRY);
        
        this.port.pipe(splitter).pipe(parser);
        
        // Debug splitter output
        splitter.on('data', (buffer) => {
          if (!this._splitterData) {
            this.logger.info(`[Drone ${this.droneId}] 🔄 Splitter received data (${buffer.length} bytes)`);
            this._splitterData = true;
          }
        });

        // Handle incoming MAVLink messages from parser
        parser.on('data', (packet) => {
          if (!this._parserData) {
            this.logger.info(`[Drone ${this.droneId}] 📦 Parser emitted packet: ${packet ? packet.constructor.name : 'null'}`);
            if (packet && packet.message) {
              this.logger.info(`[Drone ${this.droneId}] 📨 Message type: ${packet.message.constructor.name}`);
            }
            this._parserData = true;
          }
          
          try {
            // packet is already parsed by the pipeline
            if (packet && packet.message) {
              this.handleMavLinkMessage(packet);
            } else {
              this.logger.warn(`[Drone ${this.droneId}] ⚠️ Packet without message: ${JSON.stringify(packet)}`);
            }
          } catch (error) {
            this.logger.error(`[Drone ${this.droneId}] Handle error: ${error.message}`);
          }
        });

        parser.on('error', (error) => {
          this.logger.error(`[Drone ${this.droneId}] Parser error: ${error.message}`);
        });
        
        splitter.on('error', (error) => {
          this.logger.error(`[Drone ${this.droneId}] Splitter error: ${error.message}`);
        });

        // Port event handlers
        this.port.on('open', () => {
          this.connected = true;
          this.logger.info(`[Drone ${this.droneId}] ✅ Pixhawk connected`);
          this.emit('connected', { drone_id: this.droneId });
          this.startHeartbeat();
          resolve();
        });

        this.port.on('close', () => {
          this.connected = false;
          this.logger.warn(`[Drone ${this.droneId}] Pixhawk disconnected`);
          this.emit('disconnected', { drone_id: this.droneId });
          this.stopHeartbeat();
        });

        this.port.on('error', (error) => {
          this.connected = false;
          this.logger.error(`[Drone ${this.droneId}] Port error: ${error.message}`);
          this.emit('error', { drone_id: this.droneId, error: error.message });
          this.emit('disconnected', { drone_id: this.droneId });
        });

        // Now try to open the port
        this.port.open((error) => {
          if (error) {
            this.connected = false;
            this.logger.error(`[Drone ${this.droneId}] Failed to open port: ${error.message}`);
            this.emit('disconnected', { drone_id: this.droneId });
            reject(error);
          }
        });

      } catch (error) {
        this.connected = false;
        this.logger.error(`[Drone ${this.droneId}] Connection failed: ${error.message}`);
        this.emit('disconnected', { drone_id: this.droneId });
        reject(error);
      }
    });
  }

  disconnect() {
    this.logger.info(`[Drone ${this.droneId}] Disconnecting...`);
    this.stopHeartbeat();
    if (this.port && this.port.isOpen) {
      this.port.close();
    }
    this.connected = false;
  }

  handleMavLinkMessage(packet) {
    const message = packet.message;
    const msgName = message.constructor.name;
    
    // Log first few messages for debugging
    if (!this._debugLogged) {
      this.logger.info(`[Drone ${this.droneId}] Receiving MAVLink messages: ${msgName}`);
      this._debugLogged = true;
    }
    
    // Count message types for debugging
    if (!this._msgCounts) this._msgCounts = {};
    this._msgCounts[msgName] = (this._msgCounts[msgName] || 0) + 1;
    
    // Log summary every 100 messages
    if (!this._totalMsgs) this._totalMsgs = 0;
    this._totalMsgs++;
    if (this._totalMsgs === 100) {
      this.logger.info(`[Drone ${this.droneId}] 📊 Message stats: ${Object.entries(this._msgCounts).map(([k,v]) => `${k}:${v}`).join(', ')}`);
    }
    
    switch (msgName) {
      case 'Heartbeat':
        this.handleHeartbeat(message);
        break;
      case 'GlobalPositionInt':
        this.handleGlobalPosition(message);
        break;
      case 'GpsRawInt':
        this.handleGpsRaw(message);
        break;
      case 'Attitude':
        this.handleAttitude(message);
        break;
      case 'VfrHud':
        this.handleVfrHud(message);
        break;
      case 'SysStatus':
        this.handleSysStatus(message);
        break;
      case 'BatteryStatus':
        this.handleBatteryStatus(message);
        break;
      default:
        // Uncomment for debugging all messages
        // this.logger.debug(`[Drone ${this.droneId}] Received: ${msgName}`);
        break;
    }
  }

  handleHeartbeat(message) {
    // Get flight mode and armed status
    const customMode = message.customMode;
    const baseMode = message.baseMode;
    
    this.telemetryData.armed = (baseMode & 128) !== 0; // MAV_MODE_FLAG_SAFETY_ARMED
    this.telemetryData.system_status = this.getSystemStatus(message.systemStatus);
    
    // Parse custom mode for flight mode (ArduCopter/ArduPilot)
    this.telemetryData.flight_mode = this.parseFlightMode(customMode);
    
    if (!this._heartbeatLogged) {
      this.logger.info(`[Drone ${this.droneId}] 💓 Heartbeat received - Mode: ${this.telemetryData.flight_mode}, Armed: ${this.telemetryData.armed}`);
      this._heartbeatLogged = true;
    }
    
    this.emit('heartbeat', {
      drone_id: this.droneId,
      armed: this.telemetryData.armed,
      flight_mode: this.telemetryData.flight_mode,
      system_status: this.telemetryData.system_status
    });
    
    // Also emit telemetry on heartbeat so dashboard gets updates
    this.emitTelemetry();
  }

  handleGlobalPosition(message) {
    this.telemetryData.gps.lat = message.lat / 1e7;
    this.telemetryData.gps.lon = message.lon / 1e7;
    this.telemetryData.gps.alt = message.alt / 1000; // mm to m
    this.telemetryData.altitude = message.relativeAlt / 1000; // mm to m
    this.telemetryData.heading = message.hdg / 100; // centidegrees to degrees
    
    // Velocity in cm/s to m/s
    const vx = message.vx / 100;
    const vy = message.vy / 100;
    this.telemetryData.groundspeed = Math.sqrt(vx * vx + vy * vy);
    
    this.emitTelemetry();
  }

  handleGpsRaw(message) {
    this.telemetryData.gps.satellites_visible = message.satellitesVisible;
    this.telemetryData.gps.fix_type = message.fixType;
    this.telemetryData.gps.hdop = message.eph / 100;
    
    // Update position if no GlobalPositionInt
    if (this.telemetryData.gps.lat === 0) {
      this.telemetryData.gps.lat = message.lat / 1e7;
      this.telemetryData.gps.lon = message.lon / 1e7;
      this.telemetryData.gps.alt = message.alt / 1000;
    }
  }

  handleAttitude(message) {
    this.telemetryData.attitude.roll = message.roll * (180 / Math.PI);
    this.telemetryData.attitude.pitch = message.pitch * (180 / Math.PI);
    this.telemetryData.attitude.yaw = message.yaw * (180 / Math.PI);
  }

  handleVfrHud(message) {
    this.telemetryData.groundspeed = message.groundspeed;
    this.telemetryData.altitude = message.alt;
    this.telemetryData.heading = message.heading;
  }

  handleSysStatus(message) {
    this.telemetryData.battery.voltage = message.voltageBattery / 1000; // mV to V
    this.telemetryData.battery.current = message.currentBattery / 100; // cA to A
    this.telemetryData.battery.remaining = message.batteryRemaining;
  }

  handleBatteryStatus(message) {
    if (message.voltages && message.voltages.length > 0) {
      // Sum cell voltages and convert mV to V
      const totalVoltage = message.voltages.reduce((sum, v) => sum + v, 0) / 1000;
      if (totalVoltage > 0) {
        this.telemetryData.battery.voltage = totalVoltage;
      }
    }
    this.telemetryData.battery.current = message.currentBattery / 100; // cA to A
    this.telemetryData.battery.remaining = message.batteryRemaining;
  }

  emitTelemetry() {
    if (!this._telemetryLogged) {
      this.logger.info(`[Drone ${this.droneId}] Emitting telemetry - GPS: ${this.telemetryData.gps.lat.toFixed(6)}, ${this.telemetryData.gps.lon.toFixed(6)}`);
      this._telemetryLogged = true;
    }
    
    this.emit('telemetry', {
      drone_id: this.droneId,
      timestamp: new Date().toISOString(),
      telemetry: { ...this.telemetryData }
    });
  }

  startHeartbeat() {
    // Send heartbeat every second
    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, 1000);
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  sendHeartbeat() {
    if (!this.connected || !this.port || !this.port.isOpen) return;

    try {
      // Get Heartbeat from minimal registry (message ID 0)
      const HeartbeatClass = minimal.REGISTRY[0];
      const heartbeat = new HeartbeatClass();
      heartbeat.type = 6; // MAV_TYPE_GCS
      heartbeat.autopilot = 8; // MAV_AUTOPILOT_INVALID
      heartbeat.baseMode = 0;
      heartbeat.customMode = 0;
      heartbeat.systemStatus = 4; // MAV_STATE_ACTIVE
      heartbeat.mavlinkVersion = 3; // MAVLink 2

      // Serialize using protocol
      const protocol = new MavLinkProtocolV2();
      const buffer = protocol.serialize(heartbeat, this.systemId, this.componentId, this.sequenceNumber++);
      this.port.write(buffer);
    } catch (error) {
      this.logger.debug(`[Drone ${this.droneId}] Heartbeat send error: ${error.message}`);
    }
  }

  // Command methods
  async arm() {
    return this.sendCommand(400, 1, 0, 0, 0, 0, 0, 0); // MAV_CMD_COMPONENT_ARM_DISARM
  }

  async disarm() {
    return this.sendCommand(400, 0, 0, 0, 0, 0, 0, 0);
  }

  async setMode(mode) {
    // Send SET_MODE command
    const modeNum = this.getModeNumber(mode);
    return this.sendCommand(176, 1, modeNum, 0, 0, 0, 0, 0); // MAV_CMD_DO_SET_MODE
  }

  async takeoff(altitude) {
    // MAV_CMD_NAV_TAKEOFF
    return this.sendCommand(22, 0, 0, 0, 0, 0, 0, altitude);
  }

  async land() {
    // MAV_CMD_NAV_LAND
    return this.sendCommand(21, 0, 0, 0, 0, 0, 0, 0);
  }

  async rtl() {
    // Set RTL mode
    return this.setMode('RTL');
  }

  async goto(lat, lon, alt) {
    // MAV_CMD_NAV_WAYPOINT (simplified)
    return this.sendCommand(16, 0, 0, 0, 0, lat, lon, alt);
  }

  sendCommand(command, param1, param2, param3, param4, param5, param6, param7) {
    return new Promise((resolve, reject) => {
      if (!this.connected || !this.port || !this.port.isOpen) {
        return reject(new Error('Not connected'));
      }

      try {
        // Get CommandLong from minimal or common registry
        const CommandLongClass = minimal.REGISTRY[76] || common.REGISTRY[76];
        const cmdLong = new CommandLongClass();
        cmdLong.targetSystem = this.targetSystem;
        cmdLong.targetComponent = this.targetComponent;
        cmdLong.command = command;
        cmdLong.confirmation = 0;
        cmdLong.param1 = param1;
        cmdLong.param2 = param2;
        cmdLong.param3 = param3;
        cmdLong.param4 = param4;
        cmdLong.param5 = param5;
        cmdLong.param6 = param6;
        cmdLong.param7 = param7;

        // Serialize using protocol
        const protocol = new MavLinkProtocolV2();
        const buffer = protocol.serialize(cmdLong, this.systemId, this.componentId, this.sequenceNumber++);
        this.port.write(buffer);
        
        this.logger.info(`[Drone ${this.droneId}] Command sent: ${command}`);
        resolve({ success: true });
      } catch (error) {
        this.logger.error(`[Drone ${this.droneId}] Command error: ${error.message}`);
        reject(error);
      }
    });
  }

  // Helper methods
  parseFlightMode(customMode) {
    // ArduCopter flight modes
    const modes = {
      0: 'STABILIZE',
      1: 'ACRO',
      2: 'ALT_HOLD',
      3: 'AUTO',
      4: 'GUIDED',
      5: 'LOITER',
      6: 'RTL',
      7: 'CIRCLE',
      9: 'LAND',
      16: 'POSHOLD',
      17: 'BRAKE',
      18: 'THROW',
      19: 'AVOID_ADSB',
      20: 'GUIDED_NOGPS',
      21: 'SMART_RTL',
      22: 'FLOWHOLD',
      23: 'FOLLOW',
      24: 'ZIGZAG',
      25: 'SYSTEMID',
      26: 'AUTOROTATE'
    };
    return modes[customMode] || `MODE_${customMode}`;
  }

  getModeNumber(modeName) {
    const modes = {
      'STABILIZE': 0,
      'ACRO': 1,
      'ALT_HOLD': 2,
      'AUTO': 3,
      'GUIDED': 4,
      'LOITER': 5,
      'RTL': 6,
      'CIRCLE': 7,
      'LAND': 9,
      'POSHOLD': 16,
      'BRAKE': 17
    };
    return modes[modeName.toUpperCase()] || 0;
  }

  getSystemStatus(status) {
    const statuses = {
      0: 'UNINIT',
      1: 'BOOT',
      2: 'CALIBRATING',
      3: 'STANDBY',
      4: 'ACTIVE',
      5: 'CRITICAL',
      6: 'EMERGENCY',
      7: 'POWEROFF',
      8: 'FLIGHT_TERMINATION'
    };
    return statuses[status] || 'UNKNOWN';
  }

  getTelemetryData() {
    return {
      drone_id: this.droneId,
      timestamp: new Date().toISOString(),
      telemetry: { ...this.telemetryData }
    };
  }
}

module.exports = PixhawkConnection;
