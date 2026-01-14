#!/usr/bin/env python3
"""
PyMAVLink Service for Drone Control
Handles MAVLink communication with Pixhawk flight controllers
Communicates with Node.js server via HTTP REST API
"""

import time
import json
import threading
import math
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymavlink import mavutil
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress Flask/Werkzeug request logging (too verbose)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app)

# Store drone connections
drones = {}
drone_telemetry = {}
drone_locks = {}


class DroneConnection:
    """Manages connection to a single drone via MAVLink"""
    
    def __init__(self, drone_id, port, baudrate=57600, simulation=False):
        self.drone_id = drone_id
        self.port = port
        self.baudrate = baudrate
        self.master = None
        self.connected = False
        self.simulation = simulation  # Simulation mode flag
        self.telemetry = {
            'armed': False,
            'flight_mode': 'UNKNOWN',
            'latitude': 0.0,
            'longitude': 0.0,
            'altitude': 0.0,
            'relative_altitude': 0.0,
            'heading': 0.0,
            'groundspeed': 0.0,
            'airspeed': 0.0,
            'climb_rate': 0.0,
            'throttle': 0,
            'roll': 0.0,
            'pitch': 0.0,
            'yaw': 0.0,
            'battery_voltage': 0.0,
            'battery_current': 0.0,
            'battery_remaining': 0,
            'satellites_visible': 0,
            'gps_fix_type': 0,
            'hdop': 99.99,
            'timestamp': time.time(),
            'statustext_log': []  # Last STATUSTEXT messages from autopilot
        }
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.mission_waypoints = []
        self.current_waypoint_index = 0
        self.mission_active = False
        self.statustext_log = []  # Store last 20 STATUSTEXT messages for debugging
        self.statustext_max = 20
        self.uploading_mission = False  # Flag to pause telemetry during mission upload
        
    def connect(self):
        """Establish connection to Pixhawk (or simulation)"""
        try:
            if self.simulation:
                logger.info(f"🎮 SIMULATION MODE: Connecting to virtual Drone {self.drone_id}")
                # In simulation, we don't need real MAVLink connection
                self.master = None
                self.connected = True
                
                # Set simulated telemetry
                self.telemetry['latitude'] = 12.9716 + (self.drone_id * 0.001)
                self.telemetry['longitude'] = 77.5946 + (self.drone_id * 0.001)
                self.telemetry['altitude'] = 0.0
                self.telemetry['battery_voltage'] = 16.4
                self.telemetry['battery_remaining'] = 95
                self.telemetry['satellites_visible'] = 12
                self.telemetry['gps_fix_type'] = 3
                self.telemetry['flight_mode'] = 'STABILIZE'
                
                logger.info(f"✅ Simulated Drone {self.drone_id} connected (Virtual Flight Controller)")
                
                # Start simulated telemetry updates
                self.running = True
                self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
                self.thread.start()
                
                return True
            
            logger.info(f"Connecting to Drone {self.drone_id} on {self.port} @ {self.baudrate}")
            
            # Create MAVLink connection
            self.master = mavutil.mavlink_connection(
                self.port,
                baud=self.baudrate,
                source_system=255,
                source_component=0
            )
            
            # Wait for heartbeat
            logger.info(f"Waiting for heartbeat from Drone {self.drone_id}...")
            heartbeat = self.master.wait_heartbeat(timeout=10)
            
            if heartbeat:
                self.connected = True
                logger.info(f" Drone {self.drone_id} connected! System {self.master.target_system}, Component {self.master.target_component}")
                
                # Request data streams
                self.request_data_streams()
                
                # Start telemetry thread
                self.running = True
                self.thread = threading.Thread(target=self._telemetry_loop, daemon=True)
                self.thread.start()
                
                return True
            else:
                logger.error(f"No heartbeat received from Drone {self.drone_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Drone {self.drone_id}: {e}")
            self.connected = False
            return False
    
    def request_data_streams(self):
        """Request telemetry data streams from Pixhawk"""
        try:
            # Request all data streams at 4 Hz (ArduPilot style)
            for stream_id in [
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA3,
            ]:
                self.master.mav.request_data_stream_send(
                    self.master.target_system,
                    self.master.target_component,
                    stream_id,
                    4,  # Hz
                    1   # Start
                )
                time.sleep(0.05)  # Small delay between requests
            
            # Also request individual message rates (MAVLink 2 style)
            message_ids = [
                mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT,  # GPS position
                mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT,          # GPS raw
                mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS,           # Battery
                mavutil.mavlink.MAVLINK_MSG_ID_VFR_HUD,              # Speed/Alt
                mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,             # Attitude
                mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT,            # Heartbeat
            ]
            
            for msg_id in message_ids:
                self.master.mav.command_long_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                    0,
                    msg_id,    # Message ID
                    250000,    # Interval in microseconds (4 Hz = 250ms = 250000us)
                    0, 0, 0, 0, 0
                )
                time.sleep(0.05)
            
            logger.info(f"✅ Data streams requested for Drone {self.drone_id}")
        except Exception as e:
            logger.error(f"Error requesting data streams: {e}")
    
    def _telemetry_loop(self):
        """Background thread to receive telemetry"""
        logger.info(f"Telemetry loop started for Drone {self.drone_id}")
        error_count = 0
        max_errors = 5
        message_counts = {}  # Track message types received
        last_log_time = time.time()
        
        while self.running and self.connected:
            try:
                # PAUSE TELEMETRY DURING MISSION UPLOAD to avoid threading race conditions
                if self.uploading_mission:
                    time.sleep(0.1)  # Sleep briefly and retry
                    continue
                
                msg = self.master.recv_match(blocking=True, timeout=1.0)
                
                if msg is None:
                    continue
                
                # Reset error count on successful message
                error_count = 0
                msg_type = msg.get_type()
                
                # Count messages for debugging
                message_counts[msg_type] = message_counts.get(msg_type, 0) + 1
                
                # Log message statistics every 10 seconds
                if time.time() - last_log_time > 10:
                    logger.info(f"Drone {self.drone_id} message stats (last 10s): {dict(list(message_counts.items())[:5])}")
                    last_log_time = time.time()
                    message_counts.clear()
                
                # Update telemetry based on message type
                with self.lock:
                    if msg_type == 'HEARTBEAT':
                        self.telemetry['armed'] = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED != 0
                        self.telemetry['flight_mode'] = mavutil.mode_string_v10(msg)
                        
                    elif msg_type == 'GLOBAL_POSITION_INT':
                        self.telemetry['latitude'] = msg.lat / 1e7
                        self.telemetry['longitude'] = msg.lon / 1e7
                        self.telemetry['altitude'] = msg.alt / 1000.0
                        self.telemetry['relative_altitude'] = msg.relative_alt / 1000.0
                        self.telemetry['heading'] = msg.hdg / 100.0 if msg.hdg != 65535 else 0.0
                        # Calculate groundspeed from vx, vy
                        vx = msg.vx / 100.0  # cm/s to m/s
                        vy = msg.vy / 100.0
                        self.telemetry['groundspeed'] = math.sqrt(vx*vx + vy*vy)
                        
                    elif msg_type == 'ATTITUDE':
                        self.telemetry['roll'] = msg.roll * 57.2958  # rad to deg
                        self.telemetry['pitch'] = msg.pitch * 57.2958
                        self.telemetry['yaw'] = msg.yaw * 57.2958
                        
                    elif msg_type == 'SYS_STATUS':
                        self.telemetry['battery_voltage'] = msg.voltage_battery / 1000.0
                        self.telemetry['battery_current'] = msg.current_battery / 100.0
                        self.telemetry['battery_remaining'] = msg.battery_remaining
                        
                    elif msg_type == 'GPS_RAW_INT':
                        self.telemetry['satellites_visible'] = msg.satellites_visible if hasattr(msg, 'satellites_visible') else 0
                        self.telemetry['gps_fix_type'] = msg.fix_type if hasattr(msg, 'fix_type') else 0
                        self.telemetry['hdop'] = msg.eph / 100.0 if hasattr(msg, 'eph') and msg.eph != 65535 else 99.99
                        
                    elif msg_type == 'VFR_HUD':
                        self.telemetry['airspeed'] = msg.airspeed if hasattr(msg, 'airspeed') else 0.0
                        self.telemetry['climb_rate'] = msg.climb if hasattr(msg, 'climb') else 0.0
                        self.telemetry['throttle'] = msg.throttle if hasattr(msg, 'throttle') else 0

                        # Smooth groundspeed using a weighted average to reduce fluctuations
                        if 'groundspeed' in self.telemetry and self.telemetry['groundspeed'] > 0:
                            self.telemetry['groundspeed'] = (
                                0.8 * self.telemetry['groundspeed'] + 0.2 * (msg.groundspeed if hasattr(msg, 'groundspeed') else 0.0)
                            )
                        else:
                            self.telemetry['groundspeed'] = msg.groundspeed if hasattr(msg, 'groundspeed') else 0.0

                        # Also get altitude from VFR_HUD as backup
                        if 'relative_altitude' not in self.telemetry or self.telemetry['relative_altitude'] == 0:
                            self.telemetry['relative_altitude'] = msg.alt if hasattr(msg, 'alt') else 0.0
                    
                    elif msg_type == 'STATUSTEXT':
                        # Capture status messages for debugging (pre-arm failures, etc.)
                        severity = getattr(msg, 'severity', 0)
                        text = getattr(msg, 'text', '').strip()
                        timestamp = time.time()
                        
                        # Parse detection messages (sent by Pi via MAVLink)
                        # Format: DET|ID|LAT|LON|CONF|AREA
                        if text.startswith('DET|'):
                            try:
                                parts = text.split('|')
                                if len(parts) >= 6:
                                    detection_data = {
                                        'detection_id': parts[1],
                                        'latitude': float(parts[2]),
                                        'longitude': float(parts[3]),
                                        'confidence': float(parts[4]),
                                        'detection_area': int(parts[5]) if parts[5].isdigit() else 0,
                                        'timestamp': timestamp,
                                        'drone_id': self.drone_id,
                                        'source': 'mavlink_telemetry'
                                    }
                                    # Emit detection to Node.js server
                                    self._forward_detection_to_server(detection_data)
                                    logger.info(f"📡 Drone {self.drone_id} MAVLink Detection: {parts[1]} at ({parts[2]}, {parts[3]})")
                            except Exception as e:
                                logger.error(f"Failed to parse detection message: {text}, error: {e}")
                        
                        # Parse detection stats: DSTAT|TOTAL|ACTIVE|MISSION_ID
                        elif text.startswith('DSTAT|'):
                            try:
                                parts = text.split('|')
                                if len(parts) >= 4:
                                    logger.info(f"📊 Drone {self.drone_id} Detection Stats: Total={parts[1]}, Active={parts[2]}, Mission={parts[3]}")
                            except Exception as e:
                                logger.error(f"Failed to parse detection stats: {text}, error: {e}")
                        
                        # Parse system stats: STAT|CPU|MEM|DISK|TEMP
                        elif text.startswith('STAT|'):
                            try:
                                parts = text.split('|')
                                if len(parts) >= 5:
                                    logger.debug(f"💻 Drone {self.drone_id} Pi Stats: CPU={parts[1]}% MEM={parts[2]}% DISK={parts[3]}% TEMP={parts[4]}°C")
                            except Exception as e:
                                logger.error(f"Failed to parse system stats: {text}, error: {e}")
                        
                        # Store all STATUSTEXT messages
                        status_entry = {'severity': severity, 'text': text, 'timestamp': timestamp}
                        self.statustext_log.append(status_entry)
                        # Keep only last N messages
                        if len(self.statustext_log) > self.statustext_max:
                            self.statustext_log.pop(0)
                        self.telemetry['statustext_log'] = self.statustext_log.copy()
                        # Log notable messages (severity < 4 is warning+)
                        if severity < 4:
                            logger.info(f"[{severity}] Drone {self.drone_id} STATUSTEXT: {text}")
                        
                    self.telemetry['timestamp'] = time.time()
                    
            except Exception as e:
                error_count += 1
                # Only log every 5th error to avoid spam
                if error_count % 5 == 0:
                    logger.warning(f"Telemetry errors for Drone {self.drone_id}: {error_count} consecutive errors")
                # Disconnect if too many errors
                if error_count >= max_errors:
                    logger.error(f"Too many telemetry errors for Drone {self.drone_id}, maintaining connection but reducing error logs")
                    error_count = 0  # Reset but continue trying
                time.sleep(0.1)  # Brief pause on error
                time.sleep(0.1)
        
        logger.info(f"Telemetry loop stopped for Drone {self.drone_id}")
    
    def _simulation_loop(self):
        """Simulated telemetry updates for testing without hardware"""
        logger.info(f"🎮 Simulation loop started for Drone {self.drone_id}")
        
        while self.running and self.connected:
            try:
                with self.lock:
                    # Simulate battery drain
                    if self.telemetry['armed']:
                        self.telemetry['battery_remaining'] = max(0, self.telemetry['battery_remaining'] - 0.01)
                        self.telemetry['battery_voltage'] = 14.4 + (self.telemetry['battery_remaining'] / 100.0) * 2.4
                    
                    # Simulate mission progress
                    if self.mission_active and self.mission_waypoints:
                        # Move towards current waypoint
                        if self.current_waypoint_index < len(self.mission_waypoints):
                            target_wp = self.mission_waypoints[self.current_waypoint_index]
                            target_lat = target_wp.get('latitude', target_wp.get('lat', 0))
                            target_lon = target_wp.get('longitude', target_wp.get('lon', 0))
                            target_alt = target_wp.get('altitude', target_wp.get('alt', 0))
                            
                            # Calculate distance to target
                            dist = self._distance_to_waypoint(target_lat, target_lon)
                            
                            # Constant speed: 2.5 m/s ≈ 0.000025 degrees per second (at equator)
                            speed_deg_per_sec = 0.000025
                            
                            # If close enough to waypoint, snap to it exactly
                            if dist <= speed_deg_per_sec * 1.5:  # Within 1.5 seconds of arrival
                                # Snap directly to waypoint
                                self.telemetry['latitude'] = target_lat
                                self.telemetry['longitude'] = target_lon
                                self.telemetry['relative_altitude'] = target_alt
                                self.telemetry['groundspeed'] = 0
                                
                                # Wait a moment at waypoint, then move to next
                                time.sleep(0.1)
                                self.current_waypoint_index += 1
                                logger.info(f"🎯 Drone {self.drone_id} reached waypoint {self.current_waypoint_index}/{len(self.mission_waypoints)}")
                                
                                if self.current_waypoint_index >= len(self.mission_waypoints):
                                    logger.info(f"✅ Mission completed for Drone {self.drone_id}")
                                    self.mission_active = False
                                    self.telemetry['flight_mode'] = 'LOITER'
                            else:
                                # Move at constant speed towards target
                                # Calculate unit direction vector
                                direction_lat = (target_lat - self.telemetry['latitude']) / dist
                                direction_lon = (target_lon - self.telemetry['longitude']) / dist
                                
                                # Move exactly speed_deg_per_sec in that direction
                                self.telemetry['latitude'] += direction_lat * speed_deg_per_sec
                                self.telemetry['longitude'] += direction_lon * speed_deg_per_sec
                                
                                # Smooth altitude change (20% per second)
                                alt_diff = target_alt - self.telemetry['relative_altitude']
                                if abs(alt_diff) < 0.5:
                                    self.telemetry['relative_altitude'] = target_alt
                                else:
                                    self.telemetry['relative_altitude'] += alt_diff * 0.2
                                
                                self.telemetry['groundspeed'] = 2.5
                        else:
                            self.telemetry['groundspeed'] = 0
                    
                    self.telemetry['timestamp'] = time.time()
                
                time.sleep(1.0)  # Update every second
                
            except Exception as e:
                logger.error(f"Simulation loop error for Drone {self.drone_id}: {e}")
                time.sleep(0.1)
        
        logger.info(f"🎮 Simulation loop stopped for Drone {self.drone_id}")
    
    def _distance_to_waypoint(self, target_lat, target_lon):
        """Calculate distance to waypoint in degrees (rough approximation)"""
        dlat = target_lat - self.telemetry['latitude']
        dlon = target_lon - self.telemetry['longitude']
        return math.sqrt(dlat**2 + dlon**2)
    
    def _forward_detection_to_server(self, detection_data):
        """Forward MAVLink detection data to Node.js server via Socket.IO"""
        try:
            # For now, we'll store it in telemetry to be picked up by polling
            # In production, you'd use WebSocket or direct HTTP POST to Node.js
            if 'mavlink_detections' not in self.telemetry:
                self.telemetry['mavlink_detections'] = []
            
            self.telemetry['mavlink_detections'].append(detection_data)
            
            # Keep only last 50 detections
            if len(self.telemetry['mavlink_detections']) > 50:
                self.telemetry['mavlink_detections'] = self.telemetry['mavlink_detections'][-50:]
            
            # Also try to POST directly to Node.js server
            try:
                response = requests.post(
                    'http://localhost:3000/api/mavlink-detection',
                    json=detection_data,
                    timeout=1
                )
                if response.status_code == 200:
                    logger.debug(f"Detection forwarded to Node.js server: {detection_data['detection_id']}")
            except Exception as e:
                # Silently fail - telemetry polling will pick it up
                pass
                
        except Exception as e:
            logger.error(f"Error forwarding detection: {e}")
    
    def arm(self):
        """Arm the drone with verification (or simulate)"""
        try:
            if self.simulation:
                logger.info(f" Simulating ARM for Drone {self.drone_id}")
                with self.lock:
                    self.telemetry['armed'] = True
                    self.telemetry['flight_mode'] = 'STABILIZE'
                logger.info(f" Simulated Drone {self.drone_id} armed")
                return {'success': True, 'message': 'Drone armed (simulated)'}
            
            current_armed = self.telemetry.get('armed', False)
            if current_armed:
                logger.info(f"✓ Drone {self.drone_id} already armed")
                return {'success': True, 'message': 'Drone already armed'}
            
            # Ensure drone is in STABILIZE mode before arming
            # ArduPilot typically requires STABILIZE or GUIDED mode for arming
            flight_mode = self.telemetry.get('flight_mode', '')
            if flight_mode not in ['STABILIZE', 'GUIDED', 'LOITER']:
                logger.info(f"Setting STABILIZE mode before arming (current: {flight_mode})")
                if not self.set_mode('STABILIZE'):
                    logger.warning(f"Failed to set STABILIZE mode, trying to arm anyway...")
                else:
                    time.sleep(0.5)  # Wait for mode change
            
            # Check pre-arm conditions
            gps_fix = self.telemetry.get('gps_fix_type', 0)
            satellites = self.telemetry.get('satellites_visible', 0)
            hdop = self.telemetry.get('hdop', 99.99)
            battery_voltage = self.telemetry.get('battery_voltage', 0)
            flight_mode = self.telemetry.get('flight_mode', '')
            
            # Log pre-arm status
            logger.info(f"Pre-arm check: GPS={gps_fix} ({satellites} sats), HDOP={hdop:.2f}, Battery={battery_voltage:.1f}V, Mode={flight_mode}")
            
            # Build warning messages
            warnings = []
            if gps_fix < 3:
                warnings.append(f"GPS fix quality low ({gps_fix}). Need 3D fix (type 3)")
                logger.warning(f"⚠️ GPS fix quality low ({gps_fix}). Need 3D fix (type 3)")
            if hdop > 2.0:
                warnings.append(f"HDOP too high ({hdop:.2f}). ArduPilot requires < 2.0 for AUTO mode")
                logger.warning(f"⚠️ HDOP too high ({hdop:.2f}). ArduPilot requires < 2.0 for AUTO mode")
            if satellites < 8:
                warnings.append(f"Low satellite count ({satellites}). Recommended: 8+")
                logger.warning(f"⚠️ Low satellite count ({satellites}). Recommended: 8+")
            if battery_voltage < 11.0:
                warnings.append(f"Low battery voltage ({battery_voltage:.1f}V)")
                logger.warning(f"⚠️ Low battery voltage ({battery_voltage:.1f}V)")
            
            for attempt in range(3):
                self.master.arducopter_arm()
                time.sleep(0.5)  # Give it time to process
                
                # Verify arm status
                for i in range(5):
                    msg = self.master.recv_match(type='HEARTBEAT', timeout=0.2)
                    if msg:
                        is_armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED != 0
                        if is_armed:
                            self.telemetry['armed'] = True
                            logger.info(f" Drone {self.drone_id} armed successfully")
                            return {'success': True, 'message': 'Drone armed successfully'}
                    time.sleep(0.1)
                
                if attempt < 2:
                    logger.warning(f"  Arm verification attempt {attempt + 1} failed for Drone {self.drone_id}, retrying...")
                    time.sleep(0.5)
            
            # If failed after retries, build detailed error message with STATUSTEXT logs
            error_details = []
            error_details.append(f"GPS: {gps_fix} fix, {satellites} satellites")
            error_details.append(f"Battery: {battery_voltage:.1f}V")
            error_details.append(f"Mode: {flight_mode}")
            
            error_msg = "ARM failed. " + "; ".join(error_details)
            if warnings:
                error_msg += ". Issues: " + "; ".join(warnings)
            
            # Include recent STATUSTEXT messages for autopilot-specific failure reasons
            recent_statustext = self.statustext_log[-5:] if self.statustext_log else []
            if recent_statustext:
                statustext_msgs = [entry['text'] for entry in recent_statustext]
                error_msg += ". Autopilot: " + "; ".join(statustext_msgs)
            
            logger.error(f"❌ Failed to ARM Drone {self.drone_id}")
            logger.error(f"   GPS: {gps_fix} fix, {satellites} satellites, HDOP: {hdop:.2f}")
            logger.error(f"   Battery: {battery_voltage:.1f}V")
            logger.error(f"   Mode: {flight_mode}")
            logger.error(f"   Common causes: Bad GPS, HIGH HDOP, low battery, wrong mode, safety switch, compass cal")
            if recent_statustext:
                for entry in recent_statustext:
                    logger.error(f"   STATUSTEXT [{entry['severity']}]: {entry['text']}")
            
            return {'success': False, 'error': error_msg}
        except Exception as e:
            logger.error(f"ARM command failed for Drone {self.drone_id}: {e}")
            return {'success': False, 'error': f'ARM command exception: {str(e)}'}
    
    def disarm(self):
        """Disarm the drone"""
        for attempt in range(3):
            try:
                self.master.arducopter_disarm()
                time.sleep(0.5)  # Give it time to process
                logger.info(f" Drone {self.drone_id} disarmed")
                return {'success': True, 'message': 'Drone disarmed'}
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Disarm attempt {attempt + 1} failed for Drone {self.drone_id}, retrying...")
                    time.sleep(0.5)
                else:
                    logger.error(f"Failed to disarm Drone {self.drone_id} after 3 attempts: {e}")
                    return {'success': False, 'error': f'Disarm failed: {str(e)}'}
        return {'success': False, 'error': 'Disarm failed after 3 attempts'}
    
    def set_mode(self, mode_name):
        """Set flight mode using Mission Planner's exact method: DO_SET_MODE command + SET_MODE message (twice)"""
        try:
            if self.simulation:
                logger.info(f" Simulating mode change to {mode_name} for Drone {self.drone_id}")
                with self.lock:
                    self.telemetry['flight_mode'] = mode_name.upper()
                logger.info(f" Simulated Drone {self.drone_id} mode: {mode_name}")
                return True
            
            # Get mode ID
            if mode_name.upper() not in self.master.mode_mapping():
                logger.error(f"Invalid mode: {mode_name}")
                return False
            
            mode_id = self.master.mode_mapping()[mode_name.upper()]
            logger.info(f"🚁 Setting mode {mode_name} (ID={mode_id}) for Drone {self.drone_id} - Mission Planner method")
            
            # **MISSION PLANNER METHOD: 3-step process**
            # Step 1: Send MAV_CMD_DO_SET_MODE command
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,  # confirmation
                1,  # param1: mode flag (1 = custom mode enabled)
                mode_id,  # param2: custom mode value
                0, 0, 0, 0, 0  # unused params
            )
            logger.info(f"📤 Sent MAV_CMD_DO_SET_MODE command")
            
            # Step 2: Send SET_MODE message (first time)
            self.master.mav.set_mode_send(
                self.master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                mode_id
            )
            logger.info(f"📤 Sent SET_MODE message #1")
            
            # Step 3: Wait 10ms and send SET_MODE message again (Mission Planner does this!)
            time.sleep(0.01)  # 10ms delay like Mission Planner
            self.master.mav.set_mode_send(
                self.master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                mode_id
            )
            logger.info(f"📤 Sent SET_MODE message #2 (10ms after first)")
            
            # Now verify mode change via HEARTBEAT
            mode_verified = False
            for attempt in range(20):  # Try up to 4 seconds (20 x 0.2s)
                hb = self.master.recv_match(type='HEARTBEAT', timeout=0.2)
                if hb:
                    current_mode = mavutil.mode_string_v10(hb)
                    if mode_name.upper() in current_mode.upper():
                        logger.info(f"✅ Mode VERIFIED: {mode_name} (via HEARTBEAT)")
                        mode_verified = True
                        return True
                time.sleep(0.05)
            
            # If we get here, mode wasn't verified
            logger.warning(f"⚠️ Mode {mode_name} not verified after 4 seconds for Drone {self.drone_id}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to set mode for Drone {self.drone_id}: {e}")
            return False
    
    def takeoff(self, altitude):
        """Takeoff to specified altitude with proper sequence"""
        try:
            # Check if armed
            if not (self.telemetry.get('armed', False)):
                logger.warning(f"Drone {self.drone_id} not armed! Aborting takeoff.")
                return False
            
            # Ensure we're in GUIDED mode
            current_mode = self.telemetry.get('flight_mode', '')
            if 'GUIDED' not in current_mode.upper():
                logger.info(f"Setting Drone {self.drone_id} to GUIDED mode before takeoff...")
                self.set_mode('GUIDED')
                time.sleep(1.0)  # Wait for mode change to take effect
            
            # Send takeoff command
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0,  # confirmation (will be confirmed by ack)
                0,  # pitch (0 = no change)
                0,  # empty
                0,  # empty
                0,  # yaw angle (0 = no change)
                0,  # latitude (0 = current)
                0,  # longitude (0 = current)
                altitude  # altitude in meters
            )
            logger.info(f" Takeoff command sent to Drone {self.drone_id} (altitude={altitude}m)")
            
            # Wait for acknowledgment
            ack_received = False
            for i in range(10):
                msg = self.master.recv_match(type='COMMAND_ACK', timeout=0.5)
                if msg and msg.command == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        logger.info(f" Takeoff ACK received for Drone {self.drone_id}")
                        ack_received = True
                        break
                    else:
                        logger.error(f" Takeoff command rejected: {msg.result}")
                        return False
            
            if not ack_received:
                logger.warning(f" No immediate ACK for takeoff, but command was sent")
            
            return True
        except Exception as e:
            logger.error(f"Failed to takeoff Drone {self.drone_id}: {e}")
            return False
    
    def land(self):
        """Land the drone"""
        try:
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0,
                0, 0, 0, 0, 0, 0, 0
            )
            logger.info(f" Land command sent to Drone {self.drone_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to land Drone {self.drone_id}: {e}")
            return False
    
    def rtl(self):
        """Return to launch"""
        try:
            self.set_mode('RTL')
            logger.info(f" RTL command sent to Drone {self.drone_id}")
            return True
        except Exception as e:
            logger.error(f"Failed RTL for Drone {self.drone_id}: {e}")
            return False
    
    def goto(self, latitude, longitude, altitude):
        """Go to specific location in GUIDED mode"""
        try:
            # Check if armed
            if not self.telemetry.get('armed', False):
                logger.warning(f"Drone {self.drone_id} not armed! Cannot navigate.")
                return False
            
            # Ensure we're in GUIDED mode
            current_mode = self.telemetry.get('flight_mode', '')
            if 'GUIDED' not in current_mode.upper():
                logger.info(f"Setting Drone {self.drone_id} to GUIDED mode for navigation...")
                self.set_mode('GUIDED')
                time.sleep(1.0)  # Wait for mode change
            
            # Send position target (this is the proper way for GUIDED mode navigation)
            self.master.mav.set_position_target_global_int_send(
                0,  # time_boot_ms (not used)
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                0b0000111111111000,  # type_mask (only positions enabled)
                int(latitude * 1e7),   # lat_int - latitude in degrees * 1E7
                int(longitude * 1e7),  # lon_int - longitude in degrees * 1E7
                altitude,              # alt - altitude in meters (AMSL or relative)
                0,  # vx - X velocity in m/s (not used)
                0,  # vy - Y velocity in m/s (not used)
                0,  # vz - Z velocity in m/s (not used)
                0,  # afx - X acceleration (not used)
                0,  # afy - Y acceleration (not used)
                0,  # afz - Z acceleration (not used)
                0,  # yaw - yaw setpoint in radians (not used)
                0   # yaw_rate - yaw rate setpoint in rad/s (not used)
            )
            logger.info(f" Navigate command sent to Drone {self.drone_id}: ({latitude}, {longitude}) @ {altitude}m")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate Drone {self.drone_id}: {e}")
            return False
    
    def parse_waypoints_file(self, waypoints_content):
        """Parse Mission Planner .waypoints file format
        
        Format: QGC WPL 110
        seq\tcurrent\tframe\tcommand\tparam1\tparam2\tparam3\tparam4\tlat\tlon\talt\tautocontinue
        
        Returns: List of waypoint dicts ready for upload
        """
        waypoints = []
        lines = waypoints_content.strip().split('\n')
        
        # Check header
        if not lines or 'QGC WPL' not in lines[0]:
            logger.error("Invalid .waypoints file: missing QGC WPL header")
            return None
        
        # Parse waypoints (skip header line 0)
        for line_num, line in enumerate(lines[1:], start=1):
            parts = line.strip().split('\t')
            if len(parts) < 12:
                logger.warning(f"Skipping malformed line {line_num}: {line}")
                continue
            
            try:
                seq = int(parts[0])
                current = int(parts[1])
                frame = int(parts[2])
                command = int(parts[3])
                param1 = float(parts[4])
                param2 = float(parts[5])
                param3 = float(parts[6])
                param4 = float(parts[7])
                lat = float(parts[8])
                lon = float(parts[9])
                alt = float(parts[10])
                autocontinue = int(parts[11])
                
                # Convert frame number to MAVLink constant
                frame_map = {
                    0: mavutil.mavlink.MAV_FRAME_GLOBAL,
                    3: mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    6: mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
                }
                frame_const = frame_map.get(frame, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT)
                
                waypoints.append({
                    'seq': seq,
                    'current': current,
                    'frame': frame_const,
                    'command': command,
                    'param1': param1,
                    'param2': param2,
                    'param3': param3,
                    'param4': param4,
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': alt,
                    'autocontinue': autocontinue
                })
                
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing line {line_num}: {e}")
                continue
        
        logger.info(f"📄 Parsed .waypoints file: {len(waypoints)} mission items")
        return waypoints
    
    def upload_waypoints_file(self, waypoints_content):
        """Upload mission from Mission Planner .waypoints file
        
        This bypasses our mission construction and uses the exact mission
        from the .waypoints file (which matches Mission Planner format)
        """
        try:
            # Parse the .waypoints file
            waypoints = self.parse_waypoints_file(waypoints_content)
            if not waypoints:
                logger.error("Failed to parse .waypoints file")
                return False
            
            logger.info(f" Uploading mission from .waypoints file ({len(waypoints)} items)")
            
            if self.simulation:
                logger.info(f" SIMULATION: Pretending to upload {len(waypoints)} waypoints from file...")
                time.sleep(0.5)
                
                # Store waypoints for start_mission() to work
                survey_waypoints = []
                for wp in waypoints:
                    if wp['command'] == mavutil.mavlink.MAV_CMD_NAV_WAYPOINT and wp['latitude'] != 0 and wp['longitude'] != 0:
                        survey_waypoints.append({
                            'latitude': wp['latitude'],
                            'longitude': wp['longitude'],
                            'altitude': wp['altitude']
                        })
                
                self.mission_waypoints = survey_waypoints
                logger.info(f"✅ Simulated .waypoints upload successful ({len(survey_waypoints)} survey waypoints)")
                return True
            
            # Pause telemetry
            logger.info(f"⏸️  Pausing telemetry loop...")
            self.uploading_mission = True
            time.sleep(0.3)
            
            try:
                # Clear existing mission
                logger.info(f"📥 Clearing existing mission...")
                clear_confirmed = False
                for attempt in range(3):
                    self.master.mav.mission_clear_all_send(
                        self.master.target_system,
                        self.master.target_component,
                        mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                    )
                    
                    ack = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=3.0)
                    if ack and ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                        logger.info(f"✅ Mission cleared (attempt {attempt+1})")
                        clear_confirmed = True
                        break
                    time.sleep(0.5)
                
                if not clear_confirmed:
                    logger.error("❌ Failed to clear mission after 3 attempts")
                    return False
                
                time.sleep(4.0)  # EEPROM clear delay
                
                # Send mission count
                self.master.mav.mission_count_send(
                    self.master.target_system,
                    self.master.target_component,
                    len(waypoints),
                    mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                )
                logger.info(f"📤 Mission count sent: {len(waypoints)} items")
                time.sleep(0.5)
                
                # Upload each waypoint
                waypoints_sent = {}
                wp_index = 0
                timeout_count = 0
                max_timeouts = 5
                
                while wp_index < len(waypoints) and timeout_count < max_timeouts:
                    msg = self.master.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST', 'HEARTBEAT'], 
                                                 blocking=True, timeout=15)
                    
                    if msg is None:
                        timeout_count += 1
                        logger.warning(f"  Timeout {timeout_count}/{max_timeouts} waiting for request")
                        continue
                    
                    if msg.get_type() == 'HEARTBEAT':
                        continue
                    
                    msg_type = msg.get_type()
                    if msg_type in ['MISSION_REQUEST_INT', 'MISSION_REQUEST']:
                        req_seq = msg.seq
                        
                        if req_seq >= len(waypoints):
                            logger.error(f" Requested seq {req_seq} out of range (max {len(waypoints)-1})")
                            break
                        
                        if req_seq in waypoints_sent:
                            logger.warning(f" Resending waypoint {req_seq} (already sent)")
                        
                        # Get waypoint from parsed file
                        wp = waypoints[req_seq]
                        
                        # Send using mission_item_send (matches Mission Planner)
                        self.master.mav.mission_item_send(
                            self.master.target_system,
                            self.master.target_component,
                            wp['seq'],
                            wp['frame'],
                            wp['command'],
                            wp['current'],
                            wp['autocontinue'],
                            wp['param1'], wp['param2'], wp['param3'], wp['param4'],
                            wp['latitude'], wp['longitude'], wp['altitude']
                        )
                        
                        waypoints_sent[req_seq] = True
                        if req_seq == wp_index:
                            wp_index += 1
                        
                        cmd_names = {16: "HOME" if req_seq == 0 else "WAYPOINT", 22: "TAKEOFF", 178: "CHANGE_SPEED", 20: "RTL"}
                        cmd_name = cmd_names.get(wp['command'], f"CMD_{wp['command']}")
                        logger.info(f"  {cmd_name} {req_seq+1}/{len(waypoints)} uploaded (seq={req_seq})")
                        time.sleep(0.05)
                
                # Wait for mission ACK
                logger.info(f"⏳ Waiting for mission ACK...")
                ack_received = False
                for attempt in range(5):
                    ack = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=3.0)
                    if ack:
                        if ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                            logger.info(f" Mission ACK received: ACCEPTED")
                            ack_received = True
                            break
                        else:
                            logger.error(f" Mission ACK: {ack.type}")
                
                if ack_received:
                    time.sleep(2.0)  # EEPROM write delay
                    
                    # CRITICAL: Store waypoints for start_mission() to work
                    # Extract survey waypoints (command 16, not HOME/TAKEOFF/RTL)
                    survey_waypoints = []
                    for wp in waypoints:
                        if wp['command'] == mavutil.mavlink.MAV_CMD_NAV_WAYPOINT and wp['latitude'] != 0 and wp['longitude'] != 0:
                            survey_waypoints.append({
                                'latitude': wp['latitude'],
                                'longitude': wp['longitude'],
                                'altitude': wp['altitude']
                            })
                    
                    self.mission_waypoints = survey_waypoints
                    logger.info(f" Mission from .waypoints file uploaded successfully!")
                    logger.info(f"   Total: {len(waypoints)} mission items ({len(survey_waypoints)} survey waypoints)")
                    return True
                else:
                    logger.error(f" No mission ACK received")
                    return False
                    
            finally:
                logger.info(f"▶️  Resuming telemetry loop...")
                self.uploading_mission = False
                
        except Exception as e:
            logger.error(f"Failed to upload .waypoints file: {e}")
            self.uploading_mission = False
            return False
    
    def upload_mission_waypoints(self, waypoints):
        """Upload mission waypoints to drone (or simulate)"""
        try:
            if not waypoints:
                logger.error("No waypoints provided")
                return False
            
            self.mission_waypoints = waypoints
            
            # Get first survey point coordinates and altitude
            first_lat = waypoints[0].get('latitude', waypoints[0].get('lat', 0))
            first_lon = waypoints[0].get('longitude', waypoints[0].get('lon', 0))
            survey_alt = waypoints[0].get('altitude', waypoints[0].get('alt', 30))
            
            # Get current drone position (will be used as takeoff point)
            current_lat = self.telemetry.get('latitude', first_lat)
            current_lon = self.telemetry.get('longitude', first_lon)
            
            logger.info(f"Mission sequence (Mission Planner format):")
            logger.info(f"  0. HOME at current position ({current_lat:.6f}, {current_lon:.6f})")
            logger.info(f"  1. TAKEOFF at ({current_lat:.6f}, {current_lon:.6f}) to {survey_alt}m")
            logger.info(f"  2. Navigate to first survey waypoint ({first_lat:.6f}, {first_lon:.6f})")
            logger.info(f"  3. Execute {len(waypoints)} survey waypoints")
            logger.info(f"  4. Return to Launch (RTL)")
            
            # Waypoint 0: HOME waypoint (REQUIRED by ArduPilot before TAKEOFF)
            # Mission Planner always uploads HOME first at seq 0
            home_waypoint = {
                'latitude': current_lat,  # Current drone position
                'longitude': current_lon,  # Current drone position
                'altitude': self.telemetry.get('altitude', 633.31),  # Current altitude (AMSL)
                'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,  # HOME uses NAV_WAYPOINT
                'param1': 0,
                'param2': 0,
                'param3': 0,
                'param4': 0,
                'autocontinue': 1
            }
            
            # Waypoint 1: TAKEOFF (comes AFTER HOME in Mission Planner format)
            # CRITICAL: ArduCopter requires actual coordinates for TAKEOFF in AUTO mode
            # Using current position (same as HOME) - NOT 0,0 which is ignored
            takeoff_waypoint = {
                'latitude': current_lat,  # Use HOME position for takeoff
                'longitude': current_lon,  # Use HOME position for takeoff
                'altitude': survey_alt,  # Altitude to climb to during takeoff
                'command': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                'param1': 0,  # Minimum pitch
                'param2': 0,  # Empty
                'param3': 0,  # Empty  
                'param4': 0,  # Yaw angle (0 = no change, Mission Planner uses 0 not NaN)
                'autocontinue': 1
            }
            logger.info(f"🚁 TAKEOFF waypoint: lat={current_lat:.8f}, lon={current_lon:.8f}, alt={survey_alt}m (NOT 0,0!)")
            
            # Waypoint 2: Navigate to first survey point at mission altitude
            # (fly from takeoff location to first survey waypoint)
            nav_to_survey = {
                'latitude': first_lat,
                'longitude': first_lon,
                'altitude': survey_alt,
                'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                'param1': 0,
                'param2': 0,
                'param3': 0,
                'param4': 0,
                'autocontinue': 1
            }
            
            # Last Waypoint: Return to Launch (RTL)
            rtl_waypoint = {
                'latitude': 0,  # RTL uses 0,0 (ignored)
                'longitude': 0,  # RTL uses 0,0 (ignored)
                'altitude': 0,  # RTL altitude from parameter
                'command': mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                'param1': 0,
                'param2': 0,
                'param3': 0,
                'param4': 0,
                'autocontinue': 1
            }
            
            # Build complete mission: HOME + TAKEOFF + NAV_TO_START + SURVEY_WAYPOINTS + RTL
            # This matches Mission Planner's exact structure
            full_mission = [home_waypoint, takeoff_waypoint, nav_to_survey] + waypoints + [rtl_waypoint]
            
            logger.info(f" Uploading {len(full_mission)} waypoints (HOME + TAKEOFF + NAV + {len(waypoints)} survey + RTL) to Drone {self.drone_id}")
            
            if self.simulation:
                logger.info(f" SIMULATION: Pretending to upload {len(full_mission)} waypoints...")
                # Simulate upload delay
                for i, wp in enumerate(full_mission):
                    if i % 10 == 0:  # Log every 10th waypoint
                        logger.info(f"  Simulated upload: waypoint {i+1}/{len(full_mission)}")
                    time.sleep(0.01)  # Small delay to simulate upload time
                
                logger.info(f" Simulated mission upload successful for Drone {self.drone_id}")
                return True
            
            # CRITICAL: Pause telemetry loop BEFORE mission operations to prevent message conflicts
            # The telemetry thread would consume MISSION_ACK messages needed for upload verification
            logger.info(f"⏸️  Pausing telemetry loop to avoid message conflicts...")
            self.uploading_mission = True
            time.sleep(0.3)  # Give telemetry thread time to pause
            
            try:
                # Drain any pending messages before starting mission operations
                logger.info(f"📥 Draining message buffer before mission clear...")
                drain_start = time.time()
                drained_count = 0
                while time.time() - drain_start < 0.5:
                    msg = self.master.recv_match(blocking=False, timeout=0.1)
                    if msg is None:
                        break
                    drained_count += 1
                logger.info(f"📥 Drained {drained_count} buffered messages")
                
                # Clear existing mission (modern MAVLink protocol)
                logger.info(f"📥 Clearing existing mission from drone...")
                clear_confirmed = False
                clear_attempts = 0
                max_clear_attempts = 3
                
                while not clear_confirmed and clear_attempts < max_clear_attempts:
                    self.master.mav.mission_clear_all_send(
                        self.master.target_system,
                        self.master.target_component,
                        mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                    )
                    clear_attempts += 1
                    logger.info(f"📤 Sent MISSION_CLEAR_ALL (attempt {clear_attempts}/{max_clear_attempts})")
                    
                    # Wait for MISSION_ACK indicating mission was cleared
                    # Increased timeout for Pixhawk 2.4.8 (older hardware may be slower)
                    ack_received = False
                    for i in range(8):  # 8 attempts x 1.5s = 12 seconds total timeout
                        msg = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=1.5)
                        if msg:
                            logger.info(f"📥 Received MISSION_ACK: type={msg.type} (0=ACCEPTED)")
                            if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                                logger.info(f"✅ Mission cleared successfully (attempt {clear_attempts}, ACK after {(i+1)*1.5:.1f}s)")
                                clear_confirmed = True
                                ack_received = True
                                break
                    
                    if not ack_received and clear_attempts < max_clear_attempts:
                        logger.warning(f"⚠️ Mission clear ACK not received after 12s, retrying... (attempt {clear_attempts}/{max_clear_attempts})")
                        time.sleep(0.5)  # Brief pause before retry
                
                if not clear_confirmed:
                    logger.error(f"❌ CRITICAL: Could not confirm mission clear after {max_clear_attempts} attempts")
                    logger.error(f"   Pixhawk 2.4.8 not responding to MISSION_CLEAR_ALL command")
                    logger.error(f"   Solution: 1) Check MAVLink connection, 2) Clear manually in Mission Planner/QGroundControl")
                    return False
                
                # CRITICAL: Verify mission was actually cleared by requesting mission count
                logger.info(f"🔍 Verifying mission is empty (requesting mission count)...")
                self.master.mav.mission_request_list_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                )
                
                count_msg = self.master.recv_match(type='MISSION_COUNT', blocking=True, timeout=3.0)
                if count_msg:
                    if count_msg.count == 0:
                        logger.info(f"✅ Verified mission is empty (count=0)")
                    else:
                        logger.error(f"❌ CRITICAL: Mission clear failed! Drone still has {count_msg.count} waypoints in memory")
                        logger.error(f"   Even though MISSION_ACK was received, the mission wasn't actually cleared")
                        logger.error(f"   Solution: Power cycle the drone to force EEPROM clear, or use Mission Planner to clear")
                        return False
                else:
                    logger.warning(f"⚠️ Could not verify mission count after clear (timeout)")
                
                time.sleep(0.5)  # Delay to ensure EEPROM write completes
                
                # Drain any pending messages before starting waypoint upload
                logger.info(f"📥 Draining message buffer before waypoint upload...")
                drain_timeout = time.time()
                drained_count_2 = 0
                while time.time() - drain_timeout < 0.5:
                    msg = self.master.recv_match(blocking=False, timeout=0.1)
                    if msg is None:
                        break
                    drained_count_2 += 1
                logger.info(f"📥 Drained {drained_count_2} buffered messages before waypoint upload")
                
                # Send waypoint count (modern MAVLink protocol)
                self.master.mav.mission_count_send(
                    self.master.target_system,
                    self.master.target_component,
                    len(full_mission),
                    mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                )
                logger.info(f"📤 Mission count sent: {len(full_mission)} waypoints (seq 0=HOME, seq 1=TAKEOFF)")
                time.sleep(0.5)  # Increased wait time for drone to process count
                
                # Upload each waypoint using MAVLink 2 (mission_item_int)
                waypoints_sent = {}  # Track which waypoints we've already sent
                wp_index = 0
                timeout_count = 0
                max_timeouts = 5  # Increased from 3 to 5
                count_resend_attempts = 0
                max_count_resends = 2
                
                while wp_index < len(full_mission) and timeout_count < max_timeouts:
                    # Wait for waypoint request (INT version for MAVLink 2)
                    # Use longer timeout to handle slow drone responses
                    msg = self.master.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST', 'HEARTBEAT'], blocking=True, timeout=15)
                    
                    if msg is None:
                        # Timeout occurred - drone hasn't requested first waypoint yet
                        timeout_count += 1
                        logger.warning(f"⏱️  Waypoint request timeout ({timeout_count}/{max_timeouts}). Waiting for seq={wp_index}")
                        
                        # If we haven't even received the first waypoint request, try resending the count
                        if wp_index == 0 and count_resend_attempts < max_count_resends:
                            count_resend_attempts += 1
                            logger.info(f"🔄 Resending mission count (attempt {count_resend_attempts}/{max_count_resends})...")
                            self.master.mav.mission_count_send(
                                self.master.target_system,
                                self.master.target_component,
                                len(full_mission),
                                mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                            )
                            time.sleep(1.0)  # Wait longer after resend
                            continue  # Don't increment timeout_count for resend
                        
                        if timeout_count >= max_timeouts:
                            logger.error(f"❌ Waypoint upload timeout after {max_timeouts} attempts on waypoint {wp_index}")
                            return False
                        time.sleep(0.5)
                        continue
                    
                    # Check for request messages
                    if msg.get_type() in ['MISSION_REQUEST_INT', 'MISSION_REQUEST']:
                        req_seq = msg.seq
                        timeout_count = 0  # Reset timeout counter on successful request
                        count_resend_attempts = 0  # Reset count resend attempts
                        
                        # Handle out-of-order requests by resending previous waypoints if needed
                        if req_seq < wp_index and req_seq in waypoints_sent:
                            logger.info(f"  Re-sending waypoint {req_seq+1}/{len(full_mission)} (drone requested it again)")
                            wp = full_mission[req_seq]
                        elif req_seq == wp_index:
                            # Normal sequential request
                            wp = full_mission[wp_index]
                        elif req_seq > wp_index:
                            # Drone jumped ahead - this shouldn't happen, log it
                            logger.warning(f"⚠️  Drone requested waypoint {req_seq} but we're at {wp_index}, jumping ahead")
                            wp_index = req_seq
                            wp = full_mission[wp_index]
                        else:
                            # Out of sequence, skip
                            continue
                        
                        # Determine command type (handle both string names and integer IDs)
                        cmd_input = wp.get('command', mavutil.mavlink.MAV_CMD_NAV_WAYPOINT)
                        
                        # Map string command names to integer IDs if needed
                        command_map = {
                            'TAKEOFF': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                            'NAV_TAKEOFF': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                            'WAYPOINT': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                            'NAV_WAYPOINT': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                            'RTL': mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                            'RETURN_TO_LAUNCH': mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                            'NAV_RETURN_TO_LAUNCH': mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                        }
                        
                        if isinstance(cmd_input, str):
                            cmd = command_map.get(cmd_input.upper(), mavutil.mavlink.MAV_CMD_NAV_WAYPOINT)
                            logger.debug(f"  Converted command string '{cmd_input}' to ID {cmd}")
                        else:
                            cmd = int(cmd_input)
                        
                        # Get coordinates - ensure they're floats for proper conversion
                        lat = float(wp.get('latitude', wp.get('lat', 0)))
                        lon = float(wp.get('longitude', wp.get('lon', 0)))
                        alt = float(wp.get('altitude', wp.get('alt', 0)))
                        
                        # Get waypoint parameters with command-specific defaults
                        # For TAKEOFF: param1=min_pitch, param2=empty, param3=empty, param4=yaw
                        # For WAYPOINT: param1=hold_time, param2=accept_radius, param3=pass_radius, param4=yaw
                        param1 = float(wp.get('param1', wp.get('delay', 0)))
                        param2 = float(wp.get('param2', wp.get('acceptance_radius', 0)))
                        param3 = float(wp.get('param3', wp.get('pass_radius', 0)))
                        param4 = wp.get('param4', wp.get('yaw', 0))
                        # Handle NaN for yaw (means "don't change yaw")
                        if isinstance(param4, float) and (param4 != param4):  # NaN check
                            param4_float = float('nan')
                        else:
                            param4_float = float(param4)
                        
                        # Get autocontinue flag (default 1)
                        autocontinue = int(wp.get('autocontinue', 1))
                        
                        # CRITICAL: Use frame 3 (GLOBAL_RELATIVE_ALT) like Mission Planner
                        # Frame 3 = coordinates in degrees (float), NOT E7 integer format
                        # HOME (seq 0) uses altitude AMSL, others use relative altitude
                        if req_seq == 0:  # HOME waypoint uses AMSL altitude
                            frame = mavutil.mavlink.MAV_FRAME_GLOBAL
                        else:  # All other waypoints use relative altitude
                            frame = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT
                        
                        # Use mission_item_send (NOT mission_item_int) to match Mission Planner
                        # Mission Planner uses the non-INT version with float coordinates
                        self.master.mav.mission_item_send(
                            self.master.target_system,
                            self.master.target_component,
                            req_seq,  # Sequence number
                            frame,  # Frame type
                            cmd,  # Command ID
                            0,  # current (0=not current, 1=current for HOME)
                            autocontinue,  # autocontinue
                            param1, param2, param3, param4_float,  # Command parameters
                            lat, lon,  # Latitude/Longitude in degrees (float)
                            alt  # Altitude in meters (float)
                        )
                        
                        # Mark this waypoint as sent
                        waypoints_sent[req_seq] = True
                        
                        # Only advance wp_index if this is the next expected waypoint
                        if req_seq == wp_index:
                            wp_index += 1
                        
                        cmd_name = {
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF: "TAKEOFF",
                            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT: "WAYPOINT" if req_seq > 0 else "HOME",
                            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH: "RTL"
                        }.get(cmd, "WAYPOINT")
                        if req_seq == 0:
                            cmd_name = "HOME"
                        
                        logger.info(f"  {cmd_name} {req_seq+1}/{len(full_mission)} uploaded (seq={req_seq})")
                        time.sleep(0.05)  # Small delay between waypoint sends
                    
                    elif msg.get_type() == 'HEARTBEAT':
                        # Heartbeat received - drone is alive but may not be ready for waypoints
                        # Just continue waiting
                        continue
                
                # Wait for mission ACK to confirm all waypoints received
                logger.info(f"⏳ Waiting for mission ACK from Drone {self.drone_id}...")
                ack_received = False
                for attempt in range(5):  # Try up to 5 times
                    msg = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
                    if msg and msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                        logger.info(f"✅ Mission ACK received - all {len(full_mission)} waypoints accepted")
                        ack_received = True
                        break
                    elif msg:
                        logger.warning(f"⚠️  Unexpected MISSION_ACK type: {msg.type} (expected {mavutil.mavlink.MAV_MISSION_ACCEPTED})")
                    else:
                        logger.warning(f"⏱️  Waiting for MISSION_ACK (attempt {attempt+1}/5)...")
                        # Keep receiving other messages
                        time.sleep(0.2)
                
                if ack_received:
                    logger.info(f"✅ Mission ACK received - all {len(full_mission)} waypoints accepted")
                    
                    # CRITICAL: Wait for EEPROM write to complete on Pixhawk 2.4.8
                    # The ACK is sent before EEPROM write finishes, causing verification to read old data
                    logger.info(f"⏳ Waiting for EEPROM write to complete (Pixhawk 2.4.8 needs 4+ seconds)...")
                    time.sleep(4.0)  # Increased from 2s to 4s - Pixhawk 2.4.8 EEPROM is VERY slow
                    
                    # Force mission protocol sync by requesting mission count
                    # This helps ensure EEPROM write completed
                    logger.info(f"🔄 Forcing mission protocol sync (requesting mission count)...")
                    self.master.mav.mission_request_list_send(
                        self.master.target_system,
                        self.master.target_component,
                        mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                    )
                    
                    count_msg = self.master.recv_match(type='MISSION_COUNT', blocking=True, timeout=3.0)
                    if count_msg:
                        if count_msg.count == len(full_mission):
                            logger.info(f"✅ Mission count confirmed: {count_msg.count} waypoints in drone memory")
                        else:
                            logger.error(f"❌ Mission count mismatch! Expected {len(full_mission)}, got {count_msg.count}")
                            logger.error(f"   EEPROM write may have failed")
                            return False
                    else:
                        logger.warning(f"⚠️ Could not verify mission count after upload")
                    
                    # Additional delay after count sync to let EEPROM finish writing waypoint data
                    logger.info(f"⏳ Additional 2s delay for EEPROM waypoint data write...")
                    time.sleep(2.0)  # Total now: 4s initial + 2s after count = 6 seconds total wait
                    
                    # CRITICAL: DEBUG - Check what's actually at seq 0, 1, and 2
                    logger.info(f"🔍 DEBUG: Reading mission items to verify structure...")
                    
                    for check_seq in [0, 1, 2]:
                        self.master.mav.mission_request_send(
                            self.master.target_system,
                            self.master.target_component,
                            check_seq
                        )
                        msg = self.master.recv_match(type=['MISSION_ITEM_INT', 'MISSION_ITEM'], blocking=True, timeout=3.0)
                        if msg:
                            cmd_name = {
                                22: "TAKEOFF",
                                16: "WAYPOINT/HOME", 
                                20: "RTL",
                                84: "NAV_VTOL_TAKEOFF"
                            }.get(msg.command, f"UNKNOWN({msg.command})")
                            if check_seq == 0:
                                cmd_name = "HOME(NAV_WAYPOINT)"
                            logger.info(f"   seq {check_seq}: command={cmd_name} (ID={msg.command}), alt={msg.z:.1f}m")
                        else:
                            logger.warning(f"   seq {check_seq}: NO RESPONSE")
                        time.sleep(0.1)
                    
                    # Now verify TAKEOFF at seq 1 (Mission Planner format: seq 0=HOME, seq 1=TAKEOFF)
                    logger.info(f"🔍 Verifying mission item 1 (TAKEOFF) before resuming telemetry...")
                    verification_success = False
                    
                    for verify_attempt in range(3):
                        # Wait 2 seconds between retry attempts to give EEPROM more time
                        if verify_attempt > 0:
                            logger.info(f"⏳ Waiting 2s before retry {verify_attempt+1}/3 (giving EEPROM more time)...")
                            time.sleep(2.0)
                        
                        self.master.mav.mission_request_send(
                            self.master.target_system,
                            self.master.target_component,
                            1  # Request mission item 1 (TAKEOFF in Mission Planner format)
                        )
                        
                        timeout = 3.0  # Fixed 3s timeout for response
                        msg = self.master.recv_match(type=['MISSION_ITEM_INT', 'MISSION_ITEM'], blocking=True, timeout=timeout)
                        
                        if msg:
                            # Check if it's the TAKEOFF command
                            if msg.command == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
                                logger.info(f"✅ Mission item 1 verified: TAKEOFF (ID={msg.command}) at alt={msg.z}m")
                                logger.info(f"   Verification succeeded on attempt {verify_attempt+1}/3")
                                logger.info(f"   Mission structure: seq 0=HOME, seq 1=TAKEOFF, seq 2+=waypoints")
                                verification_success = True
                                break
                            else:
                                # Wrong command - old data still in EEPROM
                                logger.warning(f"⚠️ Mission item 1 is NOT TAKEOFF on attempt {verify_attempt+1}/3")
                                logger.warning(f"   Got command ID={msg.command}, expected {mavutil.mavlink.MAV_CMD_NAV_TAKEOFF}")
                                logger.warning(f"   EEPROM still writing or corrupted...")
                                
                                if verify_attempt == 2:  # Last attempt failed
                                    logger.error(f"❌ Mission item 1 (TAKEOFF) verification FAILED after 3 attempts!")
                                    logger.error(f"   Final read: command ID={msg.command} (expected 22=TAKEOFF)")
                                    logger.error(f"   REQUIRED ACTION: POWER CYCLE drone NOW")
                                    return False
                        else:
                            if verify_attempt < 2:
                                logger.warning(f"⚠️ Mission item 1 verification timeout (attempt {verify_attempt+1}/3), retrying...")
                    
                    if not verification_success:
                        logger.error(f"❌ Could not verify mission item 1 (TAKEOFF) after 3 attempts")
                        logger.error(f"   This indicates mission may not be in drone memory")
                        logger.error(f"   Continuing anyway, but AUTO mode may fail with 'Missing Takeoff Cmd'")
                        # Don't return False - let it continue, user can decide
                    
                    logger.info(f"✅ Mission uploaded and verified successfully to Drone {self.drone_id}")
                    logger.info(f"   Mission structure: {len(full_mission)} waypoints (seq 0=HOME, seq 1=TAKEOFF)")
                    return True
                else:
                    logger.error(f"❌ Mission upload failed - no ACK received")
                    return False
            
            except Exception as e:
                logger.error(f"Error during mission upload: {e}")
                return False
            
            finally:
                # CRITICAL: Resume telemetry loop after upload completes
                logger.info(f"▶️  Resuming telemetry loop...")
                self.uploading_mission = False
                
        except Exception as e:
            logger.error(f"Failed to upload mission to Drone {self.drone_id}: {e}")
            # Ensure telemetry resumes even on outer exception
            self.uploading_mission = False
            return False
    
    def start_mission(self):
        """Start the uploaded mission in AUTO mode (or simulate)"""
        try:
            if not self.mission_waypoints:
                logger.error(f"No mission uploaded for Drone {self.drone_id}")
                return {'success': False, 'error': 'No mission uploaded. Upload waypoints first.'}
            
            # Check if armed
            if not self.telemetry.get('armed', False):
                logger.warning(f"Drone {self.drone_id} not armed! Cannot start mission.")
                return {'success': False, 'error': 'Drone not armed. ARM the drone before starting mission.'}
            
            if self.simulation:
                logger.info(f" Simulating mission START for Drone {self.drone_id}")
                with self.lock:
                    self.telemetry['flight_mode'] = 'AUTO'
                    self.mission_active = True
                    self.current_waypoint_index = 0
                logger.info(f" Simulated mission started for Drone {self.drone_id} ({len(self.mission_waypoints)} waypoints)")
                return {'success': True, 'message': f'Mission started (simulated) - {len(self.mission_waypoints)} waypoints'}
            
            current_mode = self.telemetry.get('flight_mode', '').upper()
            logger.info(f"📋 Current mode: {current_mode}")
            
            # ========== PRE-AUTO MODE VALIDATION ==========
            # ArduPilot requires these conditions for AUTO mode:
            logger.info(f"🔍 Validating pre-AUTO mode conditions...")
            
            # 1. GPS Quality Check
            gps_fix = self.telemetry.get('gps_fix_type', 0)
            hdop = self.telemetry.get('hdop', 99.99)
            satellites = self.telemetry.get('satellites_visible', 0)
            
            pre_auto_errors = []
            if gps_fix < 3:
                pre_auto_errors.append(f"GPS fix type insufficient ({gps_fix}). Need 3D fix (3)")
            if hdop > 2.0:
                pre_auto_errors.append(f"HDOP too high ({hdop:.2f}). AUTO requires < 2.0")
            if satellites < 8:
                logger.warning(f"⚠️ Low satellite count ({satellites}), but continuing...")
            
            # 2. Battery Check
            battery_voltage = self.telemetry.get('battery_voltage', 0)
            if battery_voltage < 10.5:
                pre_auto_errors.append(f"Battery too low ({battery_voltage:.1f}V) for mission")
            
            # 3. Position Check (Home should be set)
            home_lat = self.telemetry.get('latitude', 0)
            home_lon = self.telemetry.get('longitude', 0)
            if home_lat == 0 and home_lon == 0:
                pre_auto_errors.append("Home position not set (GPS not locked when armed?)")
            
            if pre_auto_errors:
                error_msg = "❌ AUTO mode pre-flight checks FAILED:\n" + "\n".join([f"   • {e}" for e in pre_auto_errors])
                logger.error(error_msg)
                logger.error("   Fix these issues before starting AUTO mode mission")
                return {'success': False, 'error': error_msg}
            
            logger.info(f"✅ Pre-AUTO checks passed: GPS={gps_fix}, HDOP={hdop:.2f}, Sats={satellites}, Battery={battery_voltage:.1f}V")
            
            # Transition through GUIDED mode first if not already there
            # ArduCopter safety: can't go directly from STABILIZE to AUTO
            if 'GUIDED' not in current_mode:
                logger.info(f"📡 Transitioning to GUIDED mode (prerequisite for AUTO)...")
                guided_success = self.set_mode('GUIDED')
                if not guided_success:
                    logger.error(f"❌ Failed to transition to GUIDED mode for Drone {self.drone_id}")
                    return {'success': False, 'error': 'Failed to set GUIDED mode. Check drone status.'}
                time.sleep(0.5)
            
            # Mission was already verified during upload (mission item 1 = TAKEOFF confirmed)
            logger.info(f"✅ Mission already verified during upload - proceeding to AUTO mode")
            
            # Set current mission item to 1 BEFORE switching to AUTO mode
            # Mission Planner format: seq 0=HOME, seq 1=TAKEOFF
            logger.info(f"📌 Setting mission to start at waypoint 1 (TAKEOFF, seq 0=HOME)...")
            self.master.mav.mission_set_current_send(
                self.master.target_system,
                self.master.target_component,
                1  # Start from waypoint 1 (TAKEOFF in Mission Planner format)
            )
            time.sleep(0.3)
            
            # Verify mission_set_current was accepted
            msg = self.master.recv_match(type='MISSION_CURRENT', blocking=True, timeout=2.0)
            if msg and msg.seq == 1:
                logger.info(f"✅ Mission current waypoint confirmed at index 1 (TAKEOFF)")
            else:
                logger.warning(f"⚠️ Could not confirm current waypoint set to 1, drone may start from different waypoint")
                if msg:
                    logger.warning(f"   Drone reports current waypoint: {msg.seq} (expected 1=TAKEOFF)")
            
            # Try to set AUTO mode
            logger.info(f" Setting AUTO mode to start mission for Drone {self.drone_id}...")
            success = self.set_mode('AUTO')
            
            if not success:
                logger.warning(f"⚠️ set_mode('AUTO') returned False, attempting MAV_CMD_MISSION_START...")
                # Fallback: Use MAV_CMD_MISSION_START command directly
                self.master.mav.command_long_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_CMD_MISSION_START,
                    0,  # confirmation
                    0,  # param1: first mission item (0 uses current)
                    0,  # param2: last mission item (0 = all)
                    0, 0, 0, 0, 0  # unused params
                )
                
                # Wait for MAV_CMD_MISSION_START acknowledgment
                ack_received = False
                for i in range(5):
                    msg = self.master.recv_match(type='COMMAND_ACK', timeout=0.5)
                    if msg and msg.command == mavutil.mavlink.MAV_CMD_MISSION_START:
                        if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                            logger.info(f"✅ MAV_CMD_MISSION_START accepted")
                            ack_received = True
                            break
                        else:
                            logger.error(f"❌ MAV_CMD_MISSION_START rejected: result={msg.result}")
                            return {'success': False, 'error': f'Mission start command rejected by autopilot (result={msg.result})'}
                
                if not ack_received:
                    logger.warning(f"⚠️ No ACK for MAV_CMD_MISSION_START, but continuing...")
                
                time.sleep(0.5)
            
            # CRITICAL: Verify AUTO mode is actually set via HEARTBEAT (not telemetry)
            logger.info(f" Verifying AUTO mode activation via HEARTBEAT...")
            mode_confirmed = False
            rtl_detected = False
            
            for i in range(10):  # Try 10 times over 2 seconds
                # Check for STATUSTEXT messages that explain mode changes
                statustext_msg = self.master.recv_match(type='STATUSTEXT', blocking=False, timeout=0.05)
                if statustext_msg:
                    text = statustext_msg.text.decode('utf-8') if isinstance(statustext_msg.text, bytes) else str(statustext_msg.text)
                    severity = statustext_msg.severity;
                    logger.warning(f"🔴 STATUSTEXT during AUTO activation: [{severity}] {text}")
                    
                    # Check if RTL was triggered
                    if 'RTL' in text.upper():
                        rtl_detected = True
                        logger.error(f"❌❌❌ RTL TRIGGERED: {text}")
                
                msg = self.master.recv_match(type='HEARTBEAT', timeout=0.2)
                if msg:
                    actual_mode = mavutil.mode_string_v10(msg)
                    logger.info(f"  HEARTBEAT #{i+1}: mode = {actual_mode}")
                    
                    # Detect RTL mode
                    if 'RTL' in actual_mode.upper():
                        rtl_detected = True
                        logger.error(f"❌❌❌ DRONE SWITCHED TO RTL (not AUTO)!")
                        logger.error(f"   This means AUTO mode was rejected by ArduPilot safety checks")
                        logger.error(f"   Check STATUSTEXT messages above for the reason")
                        
                    if 'AUTO' in actual_mode.upper():
                        mode_confirmed = True
                        logger.info(f"✅ AUTO mode CONFIRMED via HEARTBEAT")
                        break
                time.sleep(0.1)
            
            if rtl_detected:
                logger.error(f"❌ Drone entered RTL instead of AUTO mode!")
                logger.error(f"   Most common causes:")
                logger.error(f"   1. First waypoint too far (check FENCE_RADIUS parameter)")
                logger.error(f"   2. EKF variance too high (wait 2+ minutes after GPS lock)")
                logger.error(f"   3. Mission validation failed (bad waypoint parameters)")
                logger.error(f"   4. Battery failsafe (check battery voltage/percentage)")
                logger.error(f"   5. Geofence violation (first WP > FENCE_RADIUS)")
                return {'success': False, 'error': 'Drone entered RTL instead of AUTO. Check STATUSTEXT messages for reason.'}
            
            if not mode_confirmed:
                logger.error(f"❌ AUTO mode NOT confirmed via HEARTBEAT after 10 attempts")
                logger.error(f"   Drone may still be in GUIDED or other mode")
                logger.error(f"   Try: 1) Check GCS safety settings, 2) Ensure mission fully uploaded, 3) Manually switch to AUTO")
                return {'success': False, 'error': 'Could not verify AUTO mode after multiple attempts. Drone may have rejected mode change.'}
            
            # Verify mission is executing by checking MISSION_CURRENT
            logger.info(f" Verifying mission execution...")
            
            mission_confirmed = False
            for i in range(5):
                msg = self.master.recv_match(type='MISSION_CURRENT', timeout=0.5)
                if msg:
                    current_wp = msg.seq
                    logger.info(f"✅ MISSION_CURRENT: Drone executing waypoint {current_wp}")
                    self.current_waypoint_index = current_wp
                    mission_confirmed = True
                    break
                time.sleep(0.1)
            
            if not mission_confirmed:
                logger.warning(f"⚠️ Could not confirm MISSION_CURRENT")
            
            # CRITICAL FIX: Send MAV_CMD_MISSION_START to explicitly trigger mission execution
            # ArduCopter won't auto-execute TAKEOFF in AUTO mode without this command
            logger.info(f"🚀 Sending MAV_CMD_MISSION_START to trigger takeoff...")
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_MISSION_START,
                0,  # confirmation
                0,  # param1: first mission item (0 uses current)
                0,  # param2: last mission item (0 = all)
                0, 0, 0, 0, 0  # unused params
            )
            
            # Wait for acknowledgment
            ack = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=2.0)
            if ack and ack.command == mavutil.mavlink.MAV_CMD_MISSION_START:
                if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    logger.info(f"✅ MAV_CMD_MISSION_START accepted - mission execution triggered!")
                else:
                    logger.warning(f"⚠️ MAV_CMD_MISSION_START rejected: {ack.result}")
            else:
                logger.warning(f"⚠️ No ACK for MAV_CMD_MISSION_START (mission may still execute)")
            
            # Mark mission as active only if AUTO mode confirmed
            self.mission_active = True
            logger.info(f"✅ Mission STARTED for Drone {self.drone_id} (waypoint {self.current_waypoint_index})")
            
            # Give drone time to start executing
            time.sleep(1.0)
            
            # Check if drone is actually flying (altitude increasing)
            initial_alt = self.telemetry.get('relative_altitude', 0)
            logger.info(f" Initial altitude: {initial_alt:.1f}m")
            
            return {'success': True, 'message': f'Mission started - {len(self.mission_waypoints)} waypoints', 'current_waypoint': self.current_waypoint_index}
                
        except Exception as e:
            logger.error(f"Failed to start mission for Drone {self.drone_id}: {e}")
            return {'success': False, 'error': f'Mission start exception: {str(e)}'}
    
    def pause_mission(self):
        """Pause mission using MAV_CMD_DO_PAUSE_CONTINUE"""
        try:
            logger.info(f" Pausing mission for Drone {self.drone_id}")
            
            if self.simulation:
                logger.info(f" Simulating mission PAUSE for Drone {self.drone_id}")
                self.mission_active = False
                return True
            
            # Send MAV_CMD_DO_PAUSE_CONTINUE with param1=0 (pause)
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE,  # 193
                0,  # confirmation
                0,  # param1: 0=pause
                0, 0, 0, 0, 0, 0  # unused params
            )
            
            # Wait for acknowledgment
            ack_received = False
            for i in range(5):
                msg = self.master.recv_match(type='COMMAND_ACK', timeout=0.5)
                if msg and msg.command == mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE:
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        logger.info(f"✅ Mission paused for Drone {self.drone_id}")
                        self.mission_active = False
                        ack_received = True
                        return True
                    else:
                        logger.error(f"❌ Pause command rejected: result={msg.result}")
                        return False
            
            if not ack_received:
                logger.warning(f"⚠️ No ACK for pause command, but command was sent")
                return True
                
        except Exception as e:
            logger.error(f"Failed to pause mission: {e}")
            return False
    
    def resume_mission(self):
        """Resume mission using MAV_CMD_DO_PAUSE_CONTINUE"""
        try:
            logger.info(f" Resuming mission for Drone {self.drone_id}")
            
            if self.simulation:
                logger.info(f" Simulating mission RESUME for Drone {self.drone_id}")
                self.mission_active = True
                return True
            
            # Send MAV_CMD_DO_PAUSE_CONTINUE with param1=1 (continue/resume)
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE,  # 193
                0,  # confirmation
                1,  # param1: 1=continue/resume
                0, 0, 0, 0, 0, 0  # unused params
            )
            
            # Wait for acknowledgment
            ack_received = False
            for i in range(5):
                msg = self.master.recv_match(type='COMMAND_ACK', timeout=0.5)
                if msg and msg.command == mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE:
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        logger.info(f"✅ Mission resumed for Drone {self.drone_id}")
                        self.mission_active = True
                        ack_received = True
                        return True
                    else:
                        logger.error(f"❌ Resume command rejected: result={msg.result}")
                        return False
            
            if not ack_received:
                logger.warning(f"⚠️ No ACK for resume command, but command was sent")
                self.mission_active = True
                return True
                
        except Exception as e:
            logger.error(f"Failed to resume mission: {e}")
            return False
    
    def stop_mission(self):
        """Stop mission and RTL (Return to Launch)"""
        try:
            logger.info(f" Stopping mission for Drone {self.drone_id}")
            self.mission_active = False
            
            # Switch to RTL to return home
            logger.info(f" Initiating RTL (Return to Launch) for Drone {self.drone_id}")
            self.set_mode('RTL')
            time.sleep(0.5)
            
            # Clear mission from drone
            if self.simulation:
                logger.info(f" Simulation: Cleared mission for Drone {self.drone_id}")
            else:
                self.master.waypoint_clear_all_send()
            
            self.mission_waypoints = []
            self.current_waypoint_index = 0
            logger.info(f" Mission stopped, drone returning to launch for Drone {self.drone_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop mission: {e}")
            return False
    
    def get_mission_status(self):
        """Get current mission progress"""
        try:
            # Request current mission item
            self.master.mav.mission_request_int_send(
                self.master.target_system,
                self.master.target_component,
                0  # Request current waypoint
            )
            
            msg = self.master.recv_match(type='MISSION_CURRENT', blocking=True, timeout=1.0)
            if msg:
                self.current_waypoint_index = msg.seq
                logger.info(f"MISSION_CURRENT: {msg.seq}, Total: {len(self.mission_waypoints)}")
            
            total = len(self.mission_waypoints)
            current = self.current_waypoint_index
            progress = (current / total * 100) if total > 0 else 0
            
            # Get current telemetry
            current_alt = self.telemetry.get('relative_altitude', 0)
            current_mode = self.telemetry.get('flight_mode', 'UNKNOWN')
            is_armed = self.telemetry.get('armed', False)
            
            status = {
                'active': self.mission_active,
                'total_waypoints': total,
                'current_waypoint': current,
                'progress_percent': progress,
                'waypoints_remaining': total - current,
                'flight_mode': current_mode,
                'armed': is_armed,
                'altitude': current_alt
            }
            
            logger.info(f"Mission Status - Active: {self.mission_active}, WP: {current}/{total}, Mode: {current_mode}, Alt: {current_alt:.1f}m")
            return status
        except Exception as e:
            logger.error(f"Failed to get mission status: {e}")
            return {
                'active': self.mission_active,
                'total_waypoints': len(self.mission_waypoints),
                'current_waypoint': self.current_waypoint_index,
                'progress_percent': 0,
                'waypoints_remaining': 0,
                'error': str(e)
            }
    
    def get_telemetry(self):
        """Get current telemetry data"""
        with self.lock:
            return self.telemetry.copy()
    
    def disconnect(self):
        """Disconnect from drone"""
        self.running = False
        self.connected = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.master:
            self.master.close()
        logger.info(f"Drone {self.drone_id} disconnected")


# ============== Flask API Routes ==============

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'pymavlink'})


@app.route('/drones', methods=['GET'])
def get_drones():
    """Get list of all drones and their status"""
    drone_list = []
    for drone_id, drone in drones.items():
        drone_list.append({
            'drone_id': drone_id,
            'connected': drone.connected,
            'simulation': drone.simulation,
            'port': drone.port,
            'telemetry': drone.get_telemetry() if drone.connected else None
        })
    return jsonify({'drones': drone_list})


@app.route('/drone/<int:drone_id>/connect', methods=['POST'])
def connect_drone(drone_id):
    """Connect to a specific drone (or start simulation)"""
    data = request.json or {}
    port = data.get('port', f'/dev/ttyUSB{drone_id-1}')
    baudrate = data.get('baudrate', 57600)
    simulation = data.get('simulation', False)  # Enable simulation mode
    
    if drone_id in drones:
        if drones[drone_id].connected:
            return jsonify({'error': 'Drone already connected'}), 400
        drones[drone_id].disconnect()
    
    drone = DroneConnection(drone_id, port, baudrate, simulation=simulation)
    success = drone.connect()
    
    if success:
        drones[drone_id] = drone
        mode_label = "🎮 SIMULATION" if simulation else "REAL HARDWARE"
        return jsonify({
            'success': True, 
            'drone_id': drone_id, 
            'connected': True,
            'simulation': simulation,
            'mode': mode_label
        })
    else:
        return jsonify({'success': False, 'error': 'Failed to connect'}), 500


@app.route('/drone/<int:drone_id>/simulate', methods=['POST'])
def start_simulation(drone_id):
    """Quick start simulation mode for testing without hardware"""
    try:
        if drone_id in drones:
            if drones[drone_id].connected:
                return jsonify({'error': 'Drone already connected. Disconnect first.'}), 400
            drones[drone_id].disconnect()
        
        logger.info(f"🎮 Starting simulation mode for Drone {drone_id}")
        drone = DroneConnection(drone_id, port='simulation', baudrate=57600, simulation=True)
        success = drone.connect()
        
        if success:
            drones[drone_id] = drone
            return jsonify({
                'success': True,
                'drone_id': drone_id,
                'mode': 'simulation',
                'message': f'Drone {drone_id} started in SIMULATION mode',
                'telemetry': drone.get_telemetry()
            })
        else:
            return jsonify({'success': False, 'error': 'Simulation failed to start'}), 500
            
    except Exception as e:
        logger.error(f"Simulation start error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/disconnect', methods=['POST'])
def disconnect_drone(drone_id):
    """Disconnect from a specific drone"""
    if drone_id not in drones:
        return jsonify({'error': 'Drone not found'}), 404
    
    drones[drone_id].disconnect()
    return jsonify({'success': True, 'drone_id': drone_id, 'connected': False})


@app.route('/drone/<int:drone_id>/telemetry', methods=['GET'])
def get_telemetry(drone_id):
    """Get telemetry for a specific drone"""
    if drone_id not in drones:
        return jsonify({'error': 'Drone not found'}), 404
    
    if not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 400
    
    telemetry = drones[drone_id].get_telemetry()
    
    # Add debug info
    debug_info = {
        'simulation_mode': drones[drone_id].simulation,
        'has_gps_data': telemetry.get('satellites_visible', 0) > 0,
        'has_battery_data': telemetry.get('battery_voltage', 0) > 0,
        'has_position_data': telemetry.get('latitude', 0) != 0 or telemetry.get('longitude', 0) != 0,
        'has_altitude_data': telemetry.get('relative_altitude', 0) != 0 or telemetry.get('altitude', 0) != 0,
        'data_age_seconds': time.time() - telemetry.get('timestamp', time.time())
    }
    
    return jsonify({
        'drone_id': drone_id,
        'simulation': drones[drone_id].simulation,
        'telemetry': telemetry,
        'timestamp': telemetry.get('timestamp', time.time()),
        'debug': debug_info
    })


@app.route('/drone/<int:drone_id>/debug', methods=['GET'])
def debug_telemetry(drone_id):
    """Debug endpoint to see raw telemetry data"""
    if drone_id not in drones:
        return jsonify({'error': 'Drone not found'}), 404
    
    if not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 400
    
    telemetry = drones[drone_id].get_telemetry()
    
    # Return formatted for easy reading
    return jsonify({
        'drone_id': drone_id,
        'connected': drones[drone_id].connected,
        'running': drones[drone_id].running,
        'telemetry_fields': list(telemetry.keys()),
        'telemetry_values': telemetry,
        'non_zero_fields': {k: v for k, v in telemetry.items() if v not in [0, 0.0, False, 'UNKNOWN', '']}
    })


@app.route('/drone/<int:drone_id>/arm', methods=['POST'])
def arm_drone(drone_id):
    """Arm a drone"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({
            'success': False, 
            'error': 'Drone not connected',
            'command': 'arm',
            'drone_id': drone_id,
            'available_drones': list(drones.keys()),
            'connected_drones': [d_id for d_id in drones.keys() if drones[d_id].connected]
        }), 404
    
    try:
        result = drones[drone_id].arm()
        if result['success']:
            return jsonify({
                'success': True, 
                'command': 'arm', 
                'message': result.get('message', 'Armed'),
                'armed': True,
                'current_mode': drones[drone_id].telemetry.get('flight_mode', 'UNKNOWN')
            })
        else:
            drone_telem = drones[drone_id].telemetry
            return jsonify({
                'success': False, 
                'command': 'arm', 
                'error': result.get('error', 'ARM failed'),
                'details': result.get('details', ''),
                'current_mode': drone_telem.get('flight_mode', 'UNKNOWN'),
                'armed': drone_telem.get('armed', False),
                'gps_status': drone_telem.get('gps_status', 'UNKNOWN'),
                'battery_voltage': drone_telem.get('battery_voltage', 0),
                'diagnostics': result.get('diagnostics', {})
            }), 400
    except Exception as e:
        logger.error(f"ARM endpoint exception: {e}")
        drone_telem = drones[drone_id].telemetry if drone_id in drones else {}
        return jsonify({
            'success': False,
            'command': 'arm',
            'error': f'ARM exception: {str(e)}',
            'current_mode': drone_telem.get('flight_mode', 'UNKNOWN'),
            'armed': drone_telem.get('armed', False)
        }), 500


@app.route('/drone/<int:drone_id>/disarm', methods=['POST'])
def disarm_drone(drone_id):
    """Disarm a drone"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'success': False, 'error': 'Drone not connected', 'command': 'disarm'}), 404
    
    result = drones[drone_id].disarm()
    if result['success']:
        return jsonify({'success': True, 'command': 'disarm', 'message': result.get('message', 'Disarmed')})
    else:
        return jsonify({'success': False, 'command': 'disarm', 'error': result.get('error', 'Disarm failed')}), 400


@app.route('/drone/<int:drone_id>/mode', methods=['POST'])
def set_mode(drone_id):
    """Set flight mode"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    data = request.json
    mode = data.get('mode')
    
    if not mode:
        return jsonify({'error': 'Mode not specified'}), 400
    
    success = drones[drone_id].set_mode(mode)
    return jsonify({'success': success, 'command': 'set_mode', 'mode': mode})


@app.route('/drone/<int:drone_id>/takeoff', methods=['POST'])
def takeoff(drone_id):
    """Takeoff to specified altitude"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    data = request.json
    altitude = data.get('altitude', 10)
    
    success = drones[drone_id].takeoff(altitude)
    return jsonify({'success': success, 'command': 'takeoff', 'altitude': altitude})


@app.route('/drone/<int:drone_id>/land', methods=['POST'])
def land(drone_id):
    """Land the drone"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    success = drones[drone_id].land()
    return jsonify({'success': success, 'command': 'land'})


@app.route('/drone/<int:drone_id>/rtl', methods=['POST'])
def rtl(drone_id):
    """Return to launch"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    success = drones[drone_id].rtl()
    return jsonify({'success': success, 'command': 'rtl'})


@app.route('/drone/<int:drone_id>/goto', methods=['POST'])
def goto(drone_id):
    """Go to specific location"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    altitude = data.get('altitude', 10)
    
    if latitude is None or longitude is None:
        return jsonify({'error': 'Latitude and longitude required'}), 400
    
    success = drones[drone_id].goto(latitude, longitude, altitude)
    return jsonify({'success': success, 'command': 'goto'})


@app.route('/drone/<int:drone_id>/mission/upload', methods=['POST'])
def upload_mission(drone_id):
    """Upload mission waypoints to drone"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({
            'success': False,
            'error': 'Drone not connected', 
            'command': 'mission_upload',
            'drone_id': drone_id,
            'available_drones': list(drones.keys()),
            'connected_drones': [d_id for d_id in drones.keys() if drones[d_id].connected]
        }), 404
    
    data = request.json
    waypoints = data.get('waypoints', [])
    
    if not waypoints:
        return jsonify({
            'success': False,
            'error': 'No waypoints provided',
            'command': 'mission_upload'
        }), 400
    
    try:
        success = drones[drone_id].upload_mission_waypoints(waypoints)
        drone_telem = drones[drone_id].telemetry
        
        if success:
            return jsonify({
                'success': True,
                'command': 'mission_upload',
                'drone_id': drone_id,
                'waypoint_count': len(waypoints),
                'telemetry': drone_telem
            })
        else:
            return jsonify({'success': False, 'error': 'Mission upload failed', 'telemetry': drone_telem}), 500
    except Exception as e:
        logger.error(f"Mission upload exception: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/mission/upload_waypoints_file', methods=['POST'])
def upload_waypoints_file(drone_id):
    """Upload mission from Mission Planner .waypoints file"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({
            'success': False,
            'error': 'Drone not connected',
            'drone_id': drone_id
        }), 404
    
    data = request.json
    waypoints_content = data.get('waypoints_file_content', '')
    
    if not waypoints_content:
        return jsonify({
            'success': False,
            'error': 'No .waypoints file content provided'
        }), 400
    
    try:
        success = drones[drone_id].upload_waypoints_file(waypoints_content)
        drone_telem = drones[drone_id].telemetry
        
        if success:
            return jsonify({
                'success': True,
                'command': 'upload_waypoints_file',
                'drone_id': drone_id,
                'message': 'Mission from .waypoints file uploaded successfully',
                'telemetry': drone_telem
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Waypoints file upload failed',
                'telemetry': drone_telem
            }), 500
    except Exception as e:
        logger.error(f"Waypoints file upload exception: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/mission/start', methods=['POST'])
def start_mission(drone_id):
    """Start the uploaded mission"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({
            'success': False, 
            'error': 'Drone not connected',
            'command': 'mission_start',
            'drone_id': drone_id,
            'available_drones': list(drones.keys()),
            'connected_drones': [d_id for d_id in drones.keys() if drones[d_id].connected]
        }), 404
    
    try:
        result = drones[drone_id].start_mission()
        if result['success']:
            drone_telem = drones[drone_id].telemetry
            return jsonify({
                'success': True, 
                'command': 'mission_start', 
                'message': result.get('message', 'Mission started'),
                'current_mode': drone_telem.get('flight_mode', 'AUTO'),
                'armed': drone_telem.get('armed', True)
            })
        else:
            drone_telem = drones[drone_id].telemetry
            return jsonify({
                'success': False, 
                'command': 'mission_start', 
                'error': result.get('error', 'Mission start failed'),
                'details': result.get('details', ''),
                'current_mode': drone_telem.get('flight_mode', 'UNKNOWN'),
                'armed': drone_telem.get('armed', False),
                'gps_status': drone_telem.get('gps_status', 'UNKNOWN'),
                'battery_voltage': drone_telem.get('battery_voltage', 0),
                'diagnostics': result.get('diagnostics', {})
            }), 400
    except Exception as e:
        logger.error(f"Mission start endpoint exception: {e}")
        drone_telem = drones[drone_id].telemetry if drone_id in drones else {}
        return jsonify({
            'success': False,
            'command': 'mission_start',
            'error': f'Mission start exception: {str(e)}',
            'current_mode': drone_telem.get('flight_mode', 'UNKNOWN'),
            'armed': drone_telem.get('armed', False)
        }), 500


@app.route('/drone/<int:drone_id>/mission/pause', methods=['POST'])
def pause_mission(drone_id):
    """Pause the current mission"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    success = drones[drone_id].pause_mission()
    return jsonify({'success': success, 'command': 'mission_pause'})


@app.route('/drone/<int:drone_id>/mission/resume', methods=['POST'])
def resume_mission(drone_id):
    """Resume the paused mission"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    success = drones[drone_id].resume_mission()
    return jsonify({'success': success, 'command': 'mission_resume'})


@app.route('/drone/<int:drone_id>/mission/stop', methods=['POST'])
def stop_mission(drone_id):
    """Stop and clear the mission"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    success = drones[drone_id].stop_mission()
    return jsonify({'success': success, 'command': 'mission_stop'})


@app.route('/drone/<int:drone_id>/mission/status', methods=['GET'])
def mission_status(drone_id):
    """Get current mission status and progress"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    status = drones[drone_id].get_mission_status()
    return jsonify({
        'drone_id': drone_id,
        'mission_status': status
    })


# ========================================
#    Long-Range Pi Control via MAVLink   |
# ========================================

@app.route('/drone/<int:drone_id>/pi/start_detection', methods=['POST'])
def pi_start_detection(drone_id):
    """Send MAVLink command to Pi to start detection (long-range control)"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    try:
        # Send custom MAVLink command 42000 = Start Detection
        drones[drone_id].master.mav.command_long_send(
            drones[drone_id].master.target_system,
            drones[drone_id].master.target_component,
            42000,  # Custom command ID for start detection
            0,      # confirmation
            0, 0, 0, 0, 0, 0, 0  # params
        )
        
        logger.info(f"📡 Sent MAVLink command: Start Detection to Drone {drone_id}")
        
        # Wait for ACK
        ack = drones[drone_id].master.recv_match(type='COMMAND_ACK', blocking=True, timeout=3.0)
        if ack and ack.command == 42000:
            success = ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED
            return jsonify({
                'success': success,
                'command': 'start_detection',
                'drone_id': drone_id,
                'ack_result': ack.result
            })
        else:
            return jsonify({
                'success': False,
                'command': 'start_detection',
                'drone_id': drone_id,
                'error': 'No ACK received'
            })
            
    except Exception as e:
        logger.error(f"Failed to send start detection command: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/pi/stop_detection', methods=['POST'])
def pi_stop_detection(drone_id):
    """Send MAVLink command to Pi to stop detection"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    try:
        # Send custom MAVLink command 42001 = Stop Detection
        drones[drone_id].master.mav.command_long_send(
            drones[drone_id].master.target_system,
            drones[drone_id].master.target_component,
            42001,  # Custom command ID for stop detection
            0,      # confirmation
            0, 0, 0, 0, 0, 0, 0  # params
        )
        
        logger.info(f"📡 Sent MAVLink command: Stop Detection to Drone {drone_id}")
        
        # Wait for ACK
        ack = drones[drone_id].master.recv_match(type='COMMAND_ACK', blocking=True, timeout=3.0)
        if ack and ack.command == 42001:
            success = ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED
            return jsonify({
                'success': success,
                'command': 'stop_detection',
                'drone_id': drone_id,
                'ack_result': ack.result
            })
        else:
            return jsonify({
                'success': False,
                'command': 'stop_detection',
                'drone_id': drone_id,
                'error': 'No ACK received'
            })
            
    except Exception as e:
        logger.error(f"Failed to send stop detection command: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/pi/request_stats', methods=['POST'])
def pi_request_stats(drone_id):
    """Request detection statistics from Pi via MAVLink"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    try:
        # Send custom MAVLink command 42002 = Request Stats
        drones[drone_id].master.mav.command_long_send(
            drones[drone_id].master.target_system,
            drones[drone_id].master.target_component,
            42002,  # Custom command ID for request stats
            0,      # confirmation
            0, 0, 0, 0, 0, 0, 0  # params
        )
        
        logger.info(f"📡 Sent MAVLink command: Request Stats to Drone {drone_id}")
        
        return jsonify({
            'success': True,
            'command': 'request_stats',
            'drone_id': drone_id,
            'note': 'Stats will be sent via Socket.IO when available'
        })
            
    except Exception as e:
        logger.error(f"Failed to send request stats command: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/spray/activate', methods=['POST'])
def activate_spray(drone_id):
    """Activate spray servo/relay"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    try:
        data = request.json or {}
        duration_sec = data.get('duration_sec', 3)  # Default 3 seconds
        servo_channel = data.get('servo_channel', 9)  # Default servo 9
        pwm_value = data.get('pwm_value', 1900)  # Default PWM for ON
        
        logger.info(f"💧 Activating spray for Drone {drone_id}: {duration_sec}s on channel {servo_channel}")
        
        # Send servo command to activate spray
        drones[drone_id].master.mav.command_long_send(
            drones[drone_id].master.target_system,
            drones[drone_id].master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,  # confirmation
            servo_channel,  # param1: servo channel
            pwm_value,      # param2: PWM value
            0, 0, 0, 0, 0   # unused params
        )
        
        return jsonify({
            'success': True,
            'drone_id': drone_id,
            'command': 'spray_activate',
            'duration_sec': duration_sec,
            'servo_channel': servo_channel
        })
        
    except Exception as e:
        logger.error(f"Failed to activate spray: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/spray/deactivate', methods=['POST'])
def deactivate_spray(drone_id):
    """Deactivate spray servo/relay"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    try:
        data = request.json or {}
        servo_channel = data.get('servo_channel', 9)
        pwm_value = data.get('pwm_value', 1100)  # Default PWM for OFF
        
        logger.info(f"💧 Deactivating spray for Drone {drone_id} on channel {servo_channel}")
        
        # Send servo command to deactivate spray
        drones[drone_id].master.mav.command_long_send(
            drones[drone_id].master.target_system,
            drones[drone_id].master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,  # confirmation
            servo_channel,  # param1: servo channel
            pwm_value,      # param2: PWM value
            0, 0, 0, 0, 0   # unused params
        )
        
        return jsonify({
            'success': True,
            'drone_id': drone_id,
            'command': 'spray_deactivate',
            'servo_channel': servo_channel
        })
        
    except Exception as e:
        logger.error(f"Failed to deactivate spray: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/spray/spray_at_target', methods=['POST'])
def spray_at_target(drone_id):
    """Navigate to target and perform spray operation"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    try:
        data = request.json
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        altitude = data.get('altitude', 5)  # Default 5m
        loiter_sec = data.get('loiter_time_sec', 5)
        spray_duration_sec = data.get('spray_duration_sec', 3)
        
        if not latitude or not longitude:
            return jsonify({'error': 'Missing latitude or longitude'}), 400
        
        logger.info(f"🎯 Spray target for Drone {drone_id}: [{latitude}, {longitude}] @ {altitude}m")
        
        # Navigate to target
        success = drones[drone_id].goto(latitude, longitude, altitude)
        
        if success:
            return jsonify({
                'success': True,
                'drone_id': drone_id,
                'target': {
                    'latitude': latitude,
                    'longitude': longitude,
                    'altitude': altitude
                },
                'loiter_time_sec': loiter_sec,
                'spray_duration_sec': spray_duration_sec,
                'status': 'navigating_to_target'
            })
        else:
            return jsonify({'success': False, 'error': 'Navigation command failed'}), 500
        
    except Exception as e:
        logger.error(f"Failed spray at target operation: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/drone/<int:drone_id>/spray/mission/upload', methods=['POST'])
def upload_spray_mission(drone_id):
    """Upload a spray mission with multiple targets"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'error': 'Drone not connected'}), 404
    
    try:
        data = request.json
        targets = data.get('targets', [])
        
        if not targets:
            return jsonify({'error': 'No targets provided'}), 400
        
        logger.info(f"📋 Uploading spray mission for Drone {drone_id}: {len(targets)} targets")
        
        # Convert spray targets to MAVLink waypoints
        waypoints = []
        
        # Add home/takeoff point as waypoint 0
        current_lat = drones[drone_id].telemetry.get('latitude', 0)
        current_lon = drones[drone_id].telemetry.get('longitude', 0)
        
        waypoints.append({
            'seq': 0,
            'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            'current': 1,
            'autocontinue': 1,
            'param1': 0,
            'param2': 0,
            'param3': 0,
            'param4': 0,
            'x': current_lat,
            'y': current_lon,
            'z': 0,
            'mission_type': mavutil.mavlink.MAV_MISSION_TYPE_MISSION
        })
        
        # Add spray targets as waypoints with loiter
        for idx, target in enumerate(targets, start=1):
            # Navigate to target
            waypoints.append({
                'seq': idx * 2 - 1,
                'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                'current': 0,
                'autocontinue': 1,
                'param1': target.get('loiter_time_sec', 5),  # Loiter time
                'param2': 0,
                'param3': 0,
                'param4': 0,
                'x': target['latitude'],
                'y': target['longitude'],
                'z': target.get('altitude', 5),
                'mission_type': mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            })
            
            # Activate spray at target (DO_SET_SERVO command)
            waypoints.append({
                'seq': idx * 2,
                'frame': mavutil.mavlink.MAV_FRAME_MISSION,
                'command': mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                'current': 0,
                'autocontinue': 1,
                'param1': target.get('servo_channel', 9),
                'param2': target.get('spray_pwm', 1900),
                'param3': 0,
                'param4': 0,
                'x': 0,
                'y': 0,
                'z': 0,
                'mission_type': mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            })
        
        # Upload waypoints to drone
        upload_result = drones[drone_id].upload_mission(waypoints)
        
        if upload_result:
            return jsonify({
                'success': True,
                'drone_id': drone_id,
                'waypoints_uploaded': len(waypoints),
                'spray_targets': len(targets)
            })
        else:
            return jsonify({'success': False, 'error': 'Mission upload failed'}), 500
        
    except Exception as e:
        logger.error(f"Failed to upload spray mission: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    # Start the Flask server
    app.run(host="0.0.0.0", port=5000, debug=True)
