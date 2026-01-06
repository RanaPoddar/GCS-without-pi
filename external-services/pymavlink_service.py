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
                        # Use VFR_HUD groundspeed if GLOBAL_POSITION_INT not available
                        if 'groundspeed' not in self.telemetry or self.telemetry['groundspeed'] == 0:
                            self.telemetry['groundspeed'] = msg.groundspeed if hasattr(msg, 'groundspeed') else 0.0
                        # Also get altitude from VFR_HUD as backup
                        if 'relative_altitude' not in self.telemetry or self.telemetry['relative_altitude'] == 0:
                            self.telemetry['relative_altitude'] = msg.alt if hasattr(msg, 'alt') else 0.0
                    
                    elif msg_type == 'STATUSTEXT':
                        # Capture status messages for debugging (pre-arm failures, etc.)
                        severity = getattr(msg, 'severity', 0)
                        text = getattr(msg, 'text', '')
                        timestamp = time.time()
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
            battery_voltage = self.telemetry.get('battery_voltage', 0)
            flight_mode = self.telemetry.get('flight_mode', '')
            
            # Log pre-arm status
            logger.info(f"Pre-arm check: GPS={gps_fix} ({satellites} sats), Battery={battery_voltage:.1f}V, Mode={flight_mode}")
            
            # Build warning messages
            warnings = []
            if gps_fix < 3:
                warnings.append(f"GPS fix quality low ({gps_fix}). Need 3D fix (type 3)")
                logger.warning(f"  GPS fix quality low ({gps_fix}). Need 3D fix (type 3)")
            if satellites < 8:
                warnings.append(f"Low satellite count ({satellites}). Recommended: 8+")
                logger.warning(f"  Low satellite count ({satellites}). Recommended: 8+")
            if battery_voltage < 11.0:
                warnings.append(f"Low battery voltage ({battery_voltage:.1f}V)")
                logger.warning(f"  Low battery voltage ({battery_voltage:.1f}V)")
            
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
            
            logger.error(f" Failed to ARM Drone {self.drone_id}")
            logger.error(f"   GPS: {gps_fix} fix, {satellites} satellites")
            logger.error(f"   Battery: {battery_voltage:.1f}V")
            logger.error(f"   Mode: {flight_mode}")
            logger.error(f"   Common causes: Bad GPS, low battery, wrong mode, safety switch, compass cal")
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
            logger.info(f"✅ Navigate command sent to Drone {self.drone_id}: ({latitude}, {longitude}) @ {altitude}m")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate Drone {self.drone_id}: {e}")
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
            
            logger.info(f"Mission sequence:")
            logger.info(f"  1. Takeoff at current position ({current_lat:.6f}, {current_lon:.6f}) to {survey_alt}m")
            logger.info(f"  2. Navigate to first survey waypoint ({first_lat:.6f}, {first_lon:.6f})")
            logger.info(f"  3. Execute {len(waypoints)} survey waypoints")
            logger.info(f"  4. Return to Launch (RTL)")
            
            # Waypoint 0: Takeoff at current position to mission altitude
            # (drone stays at current location, just climbs to altitude)
            takeoff_waypoint = {
                'latitude': current_lat,
                'longitude': current_lon,
                'altitude': survey_alt,
                'command': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF
            }
            
            # Waypoint 1: Navigate to first survey point at mission altitude
            # (fly from takeoff location to first survey waypoint)
            nav_to_survey = {
                'latitude': first_lat,
                'longitude': first_lon,
                'altitude': survey_alt,
                'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
            }
            
            # Last Waypoint: Return to Launch (RTL)
            # Note: RTL command uses current position, lat/lon are ignored but required for protocol
            rtl_waypoint = {
                'latitude': current_lat,
                'longitude': current_lon,
                'altitude': survey_alt,  # RTL altitude (will use parameter RTL_ALT instead)
                'command': mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH
            }
            
            # Build complete mission: TAKEOFF + NAV_TO_START + SURVEY_WAYPOINTS + RTL
            full_mission = [takeoff_waypoint, nav_to_survey] + waypoints + [rtl_waypoint]
            
            logger.info(f" Uploading {len(full_mission)} waypoints (TAKEOFF + NAV + {len(waypoints)} survey + RTL) to Drone {self.drone_id}")
            
            if self.simulation:
                logger.info(f" SIMULATION: Pretending to upload {len(full_mission)} waypoints...")
                # Simulate upload delay
                for i, wp in enumerate(full_mission):
                    if i % 10 == 0:  # Log every 10th waypoint
                        logger.info(f"  Simulated upload: waypoint {i+1}/{len(full_mission)}")
                    time.sleep(0.01)  # Small delay to simulate upload time
                
                logger.info(f" Simulated mission upload successful for Drone {self.drone_id}")
                return True
            
            # Clear existing mission (modern MAVLink protocol)
            self.master.mav.mission_clear_all_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            )
            time.sleep(0.5)
            
            # Send waypoint count (modern MAVLink protocol)
            self.master.mav.mission_count_send(
                self.master.target_system,
                self.master.target_component,
                len(full_mission),
                mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            )
            time.sleep(0.3)
            
            # Upload each waypoint using MAVLink 2 (mission_item_int)
            for i, wp in enumerate(full_mission):
                # Wait for waypoint request (INT version for MAVLink 2)
                msg = self.master.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST'], blocking=True, timeout=5)
                if msg and msg.seq == i:
                    # Determine command type
                    cmd = wp.get('command', mavutil.mavlink.MAV_CMD_NAV_WAYPOINT)
                    
                    # Get coordinates
                    lat = wp.get('latitude', wp.get('lat', 0))
                    lon = wp.get('longitude', wp.get('lon', 0))
                    alt = wp.get('altitude', wp.get('alt', 0))
                    
                    # Use mission_item_int_send for MAVLink 2 (lat/lon as integers)
                    self.master.mav.mission_item_int_send(
                        self.master.target_system,
                        self.master.target_component,
                        i,  # seq
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        cmd,  # Use appropriate command
                        0,  # current (0=not current, 1=current waypoint)
                        1,  # autocontinue
                        0,  # param1 (hold time for waypoint, min pitch for takeoff)
                        0,  # param2 (acceptance radius)
                        0,  # param3 (pass through)
                        0,  # param4 (yaw)
                        int(lat * 1e7),  # x: latitude in degrees * 1E7
                        int(lon * 1e7),  # y: longitude in degrees * 1E7
                        alt,             # z: altitude in meters
                        mavutil.mavlink.MAV_MISSION_TYPE_MISSION  # mission_type
                    )
                    cmd_name = "TAKEOFF" if cmd == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF else "WAYPOINT"
                    logger.info(f"  {cmd_name} {i+1}/{len(full_mission)} uploaded")
                else:
                    logger.error(f"No request received for waypoint {i}")
                    return False
            
            # Wait for mission ACK
            msg = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
            if msg and msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                logger.info(f" Mission uploaded successfully to Drone {self.drone_id}")
                return True
            else:
                logger.error(f"Mission upload failed or not acknowledged")
                return False
                
        except Exception as e:
            logger.error(f"Failed to upload mission to Drone {self.drone_id}: {e}")
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
            logger.info(f" Current mode: {current_mode}")
            
            # Transition through GUIDED mode first if not already there
            # ArduCopter safety: can't go directly from STABILIZE to AUTO
            if 'GUIDED' not in current_mode:
                logger.info(f" Transitioning to GUIDED mode (prerequisite for AUTO)...")
                guided_success = self.set_mode('GUIDED')
                if not guided_success:
                    logger.error(f"Failed to transition to GUIDED mode for Drone {self.drone_id}")
                    return {'success': False, 'error': 'Failed to set GUIDED mode. Check drone status.'}
                time.sleep(0.5)
            
            # CRITICAL: Set current mission item to 0 BEFORE switching to AUTO mode
            logger.info(f" Setting mission start waypoint to 0...")
            self.master.mav.mission_set_current_send(
                self.master.target_system,
                self.master.target_component,
                0  # Start from waypoint 0 (TAKEOFF)
            )
            time.sleep(0.5)
            
            # Verify mission set_current was accepted
            msg = self.master.recv_match(type='MISSION_CURRENT', blocking=True, timeout=2.0)
            if msg and msg.seq == 0:
                logger.info(f"✅ Mission current waypoint set to 0")
            else:
                logger.warning(f"⚠️ Could not confirm current waypoint set to 0")
            
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
                    0, 0, 0, 0, 0, 0, 0  # params (all unused)
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
            for i in range(10):  # Try 10 times over 2 seconds
                msg = self.master.recv_match(type='HEARTBEAT', timeout=0.2)
                if msg:
                    actual_mode = mavutil.mode_string_v10(msg)
                    logger.info(f"  HEARTBEAT #{i+1}: mode = {actual_mode}")
                    if 'AUTO' in actual_mode.upper():
                        mode_confirmed = True
                        logger.info(f"✅ AUTO mode CONFIRMED via HEARTBEAT")
                        break
                time.sleep(0.1)
            
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
                'waypoint_count': len(waypoints),
                'message': f'Successfully uploaded {len(waypoints)} waypoints',
                'drone_mode': drone_telem.get('flight_mode', 'UNKNOWN')
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Mission upload failed - check drone connection',
                'command': 'mission_upload',
                'waypoint_count': len(waypoints),
                'drone_mode': drone_telem.get('flight_mode', 'UNKNOWN'),
                'armed': drone_telem.get('armed', False)
            }), 400
    except Exception as e:
        logger.error(f"Mission upload exception: {e}")
        return jsonify({
            'success': False,
            'error': f'Mission upload exception: {str(e)}',
            'command': 'mission_upload',
            'waypoint_count': len(waypoints)
        }), 500


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


if __name__ == '__main__':
    logger.info("🚀 Starting PyMAVLink Service...")
    logger.info("📡 Service will listen on http://0.0.0.0:5000")
    logger.info("🌾 Long-range Pi control enabled via MAVLink (commands 42000-42999)")
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
