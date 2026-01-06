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
            'timestamp': time.time()
        }
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.mission_waypoints = []
        self.current_waypoint_index = 0
        self.mission_active = False
        
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
            
            # If failed after retries, build detailed error message
            error_details = []
            error_details.append(f"GPS: {gps_fix} fix, {satellites} satellites")
            error_details.append(f"Battery: {battery_voltage:.1f}V")
            error_details.append(f"Mode: {flight_mode}")
            
            error_msg = "ARM failed. " + "; ".join(error_details)
            if warnings:
                error_msg += ". Issues: " + "; ".join(warnings)
            
            logger.error(f" Failed to ARM Drone {self.drone_id}")
            logger.error(f"   GPS: {gps_fix} fix, {satellites} satellites")
            logger.error(f"   Battery: {battery_voltage:.1f}V")
            logger.error(f"   Mode: {flight_mode}")
            logger.error(f"   Common causes: Bad GPS, low battery, wrong mode, safety switch, compass cal")
            
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
        """Set flight mode with confirmation (or simulate)"""
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
            
            # Try to set mode with retries
            for attempt in range(3):
                self.master.set_mode(mode_id)
                time.sleep(0.3)
                
                # Verify mode was set (check telemetry)
                current_mode = self.telemetry.get('flight_mode', '')
                if mode_name.upper() in current_mode.upper():
                    logger.info(f"Drone {self.drone_id} mode confirmed: {mode_name}")
                    return True
                
                if attempt < 2:
                    logger.warning(f"Mode set attempt {attempt + 1} for {mode_name}, retrying...")
                    time.sleep(0.5)
            
            logger.info(f"Mode command sent for {mode_name} (confirmation pending)")
            return True
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
    
    def _convert_command_to_int(self, cmd):
        """Convert command (int or string) to integer constant"""
        if isinstance(cmd, int):
            return cmd
        if isinstance(cmd, str):
            # Map common string names to MAVLink constants
            cmd_upper = cmd.upper()
            if 'TAKEOFF' in cmd_upper:
                return mavutil.mavlink.MAV_CMD_NAV_TAKEOFF
            elif 'WAYPOINT' in cmd_upper:
                return mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
            elif 'LAND' in cmd_upper:
                return mavutil.mavlink.MAV_CMD_NAV_LAND
            elif 'LOITER' in cmd_upper:
                return mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM
            else:
                logger.warning(f"Unknown command string: {cmd}, defaulting to NAV_WAYPOINT")
                return mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
        return mavutil.mavlink.MAV_CMD_NAV_WAYPOINT

    def _upload_mission_event_driven(self, full_mission, first_request_msg):
        """Upload waypoints using request-driven protocol (drone requests each waypoint)"""
        logger.info(f"  Starting request-driven upload ({len(full_mission)} waypoints)...")
        uploaded = set()
        request_count = 1  # Already received first request
        last_request_time = time.time()
        overall_timeout = max(30, len(full_mission) * 3)
        upload_start = time.time()

        # Send first waypoint from initial request
        seq = getattr(first_request_msg, 'seq', 0)
        if seq < len(full_mission):
            wp = full_mission[seq]
            cmd = self._convert_command_to_int(wp.get('command', mavutil.mavlink.MAV_CMD_NAV_WAYPOINT))
            lat = float(wp.get('latitude', wp.get('lat', 0)))
            lon = float(wp.get('longitude', wp.get('lon', 0)))
            alt = float(wp.get('altitude', wp.get('alt', 0)))
            
            self.master.mav.mission_item_send(
                self.master.target_system,
                self.master.target_component,
                int(seq), mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                int(cmd), 0, 1, 0, 0, 0, 0, lat, lon, alt
            )
            cmd_name = "TAKEOFF" if cmd == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF else "WAYPOINT"
            logger.info(f"  ✓ {cmd_name} {seq+1}/{len(full_mission)} uploaded")
            uploaded.add(seq)

        # Wait for remaining requests
        while time.time() - upload_start < overall_timeout:
            msg = self.master.recv_match(blocking=True, timeout=2)
            if msg is None:
                continue

            msg_type = msg.get_type()

            if msg_type in ('MISSION_REQUEST', 'MISSION_REQUEST_INT'):
                request_count += 1
                last_request_time = time.time()
                seq = getattr(msg, 'seq', None)
                
                if seq is None or seq < 0 or seq >= len(full_mission):
                    logger.warning(f"  Invalid request seq={seq}, ignoring")
                    continue

                if seq in uploaded:
                    logger.debug(f"  Waypoint {seq} already uploaded, re-sending...")

                wp = full_mission[seq]
                cmd = self._convert_command_to_int(wp.get('command', mavutil.mavlink.MAV_CMD_NAV_WAYPOINT))
                lat = float(wp.get('latitude', wp.get('lat', 0)))
                lon = float(wp.get('longitude', wp.get('lon', 0)))
                alt = float(wp.get('altitude', wp.get('alt', 0)))

                self.master.mav.mission_item_send(
                    self.master.target_system,
                    self.master.target_component,
                    int(seq), mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    int(cmd), 0, 1, 0, 0, 0, 0, lat, lon, alt
                )
                cmd_name = "TAKEOFF" if cmd == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF else "WAYPOINT"
                logger.info(f"  ✓ {cmd_name} {seq+1}/{len(full_mission)} uploaded (request #{request_count})")
                uploaded.add(seq)

            elif msg_type == 'MISSION_ACK':
                logger.info(f"  Received MISSION_ACK during request-driven upload")
                return uploaded if len(uploaded) > 0 else False

        logger.error(f"  Request-driven upload timed out with {len(uploaded)}/{len(full_mission)} waypoints")
        return False

    def _upload_mission_send_all(self, full_mission):
        """Upload waypoints using send-all protocol (send all waypoints sequentially without requests)"""
        logger.info(f"  Starting send-all upload ({len(full_mission)} waypoints)...")
        uploaded = set()

        for seq in range(len(full_mission)):
            wp = full_mission[seq]
            cmd = self._convert_command_to_int(wp.get('command', mavutil.mavlink.MAV_CMD_NAV_WAYPOINT))
            lat = float(wp.get('latitude', wp.get('lat', 0)))
            lon = float(wp.get('longitude', wp.get('lon', 0)))
            alt = float(wp.get('altitude', wp.get('alt', 0)))

            try:
                self.master.mav.mission_item_send(
                    self.master.target_system,
                    self.master.target_component,
                    int(seq), mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    int(cmd), 0, 1, 0, 0, 0, 0, lat, lon, alt
                )
                cmd_name = "TAKEOFF" if cmd == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF else "WAYPOINT"
                logger.info(f"  ✓ {cmd_name} {seq+1}/{len(full_mission)} uploaded")
                uploaded.add(seq)
                time.sleep(0.05)  # Small delay between sends
            except Exception as e:
                logger.error(f"  ❌ Failed to send waypoint {seq}: {e}")
                return False

        logger.info(f"  All {len(uploaded)} waypoints sent; waiting for MISSION_ACK...")
        return uploaded if len(uploaded) == len(full_mission) else False

    def upload_mission_waypoints(self, waypoints):
        """Upload mission waypoints to drone (or simulate)"""
        try:
            if not waypoints:
                logger.error("No waypoints provided")
                return False
            
            self.mission_waypoints = waypoints
            
            # Get first survey point coordinates
            first_lat = waypoints[0].get('latitude', waypoints[0].get('lat', 0))
            first_lon = waypoints[0].get('longitude', waypoints[0].get('lon', 0))
            takeoff_alt = waypoints[0].get('altitude', waypoints[0].get('alt', 15))
            
            # Waypoint 0: Navigate to start point at low altitude (5m)
            # This ensures drone flies horizontally to mission start before takeoff
            nav_to_start = {
                'latitude': first_lat,
                'longitude': first_lon,
                'altitude': 5,  # Low altitude during horizontal transit
                'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
            }
            
            # Waypoint 1: Takeoff at start point to mission altitude
            takeoff_waypoint = {
                'latitude': first_lat,
                'longitude': first_lon,
                'altitude': takeoff_alt,
                'command': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF
            }
            
            # Prepend navigation and takeoff to mission
            full_mission = [nav_to_start, takeoff_waypoint] + waypoints
            
            logger.info(f" Uploading {len(full_mission)} waypoints (including TAKEOFF) to Drone {self.drone_id}")
            
            if self.simulation:
                logger.info(f" SIMULATION: Pretending to upload {len(full_mission)} waypoints...")
                # Simulate upload delay
                for i, wp in enumerate(full_mission):
                    if i % 10 == 0:  # Log every 10th waypoint
                        logger.info(f"  Simulated upload: waypoint {i+1}/{len(full_mission)}")
                    time.sleep(0.01)  # Small delay to simulate upload time
                
                logger.info(f" Simulated mission upload successful for Drone {self.drone_id}")
                return True
            
            # CRITICAL: Pause telemetry loop to prevent it from consuming MISSION_REQUEST messages
            was_running = self.running
            self.running = False
            time.sleep(0.5)  # Give telemetry thread time to stop
            logger.info(f" Paused telemetry loop for Drone {self.drone_id} to upload mission")
            
            try:
                # Clear existing mission
                logger.info(f"  Sending MISSION_CLEAR_ALL to Drone {self.drone_id}")
                self.master.waypoint_clear_all_send()
                time.sleep(1.0)  # Wait for clear to complete

                # Flush any pending messages from clear_all
                logger.info(f"  Flushing pending messages...")
                flush_start = time.time()
                while time.time() - flush_start < 0.5:
                    msg = self.master.recv_match(blocking=False, timeout=0.1)
                    if msg:
                        msg_type = msg.get_type()
                        logger.debug(f"    Flushed: {msg_type}")

                # Send waypoint count
                logger.info(f"  Sending MISSION_COUNT={len(full_mission)} to Drone {self.drone_id}")
                self.master.waypoint_count_send(len(full_mission))
                time.sleep(0.2)

                # Try request-driven approach first: wait for MISSION_REQUEST messages
                logger.info(f"  Attempting request-driven upload (waiting for MISSION_REQUEST)...")
                uploaded = set()
                upload_start = time.time()
                request_timeout = 3  # Wait 3s for first request
                last_request_time = time.time()

                # Wait for at least one MISSION_REQUEST to know if this protocol works
                while time.time() - last_request_time < request_timeout:
                    msg = self.master.recv_match(blocking=True, timeout=0.5)
                    if msg is None:
                        continue

                    msg_type = msg.get_type()

                    if msg_type in ('MISSION_REQUEST', 'MISSION_REQUEST_INT'):
                        # Drone is using request-driven protocol - proceed normally
                        logger.info(f"  ✓ Drone using REQUEST-DRIVEN protocol")
                        seq = getattr(msg, 'seq', None)
                        if seq == 0:
                            # Good, drone is asking for waypoint 0 - use event loop
                            uploaded = self._upload_mission_event_driven(full_mission, msg)
                            if uploaded is False:
                                return False
                            # Check if all waypoints were uploaded
                            if isinstance(uploaded, set) and len(uploaded) == len(full_mission):
                                logger.info(f"  ✅ Mission SUCCESSFULLY uploaded to Drone {self.drone_id} ({len(uploaded)}/{len(full_mission)} waypoints)")
                                return True
                            break
                    elif msg_type == 'MISSION_ACK':
                        # Drone accepted empty mission - drone is not using request-driven protocol
                        logger.info(f"  ⚠ Drone sent MISSION_ACK without requesting waypoints")
                        logger.info(f"  ✓ Drone using SEND-ALL protocol (proactive push)")
                        # Send all waypoints proactively
                        uploaded = self._upload_mission_send_all(full_mission)
                        if uploaded is False:
                            return False
                        break

                if not uploaded:
                    logger.warning(f"  Upload protocol detection timed out; trying send-all approach...")
                    uploaded = self._upload_mission_send_all(full_mission)
                    if uploaded is False:
                        return False

                # Verify final ACK (only if we haven't already succeeded)
                logger.info(f"  Waiting for final MISSION_ACK confirmation...")
                ack_start = time.time()
                while time.time() - ack_start < 5:
                    msg = self.master.recv_match(blocking=True, timeout=1)
                    if msg and msg.get_type() == 'MISSION_ACK':
                        ack_type = getattr(msg, 'type', None)
                        logger.info(f"  Received MISSION_ACK: type={ack_type} (ACCEPTED=0, ERROR=15)")
                        if ack_type == 0 or ack_type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                            logger.info(f"  ✅ Mission SUCCESSFULLY uploaded to Drone {self.drone_id} ({len(uploaded)}/{len(full_mission)} waypoints)")
                            return True
                        else:
                            logger.error(f"  ❌ Mission rejected: MISSION_ACK type {ack_type}")
                            return False

                logger.error(f"  ❌ No MISSION_ACK received within timeout")
                return False
                    
            finally:
                # Resume telemetry loop after mission upload
                self.running = was_running
                if was_running:
                    logger.info(f"  ✓ Resumed telemetry loop for Drone {self.drone_id}")
                else:
                    logger.info(f"  Telemetry loop was not running; leaving paused")
                
        except Exception as e:
            logger.error(f"Failed to upload mission to Drone {self.drone_id}: {e}")
            self.running = was_running  # Ensure telemetry is resumed even on exception
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
            
            # Step 1: Set to GUIDED mode first (required before AUTO)
            current_mode = self.telemetry.get('flight_mode', '')
            if 'GUIDED' not in current_mode.upper():
                logger.info(f" Setting GUIDED mode before mission start...")
                mode_result = self.set_mode('GUIDED')
                if not mode_result:
                    logger.error(f"Failed to set GUIDED mode")
                    return {'success': False, 'error': f'Failed to set GUIDED mode. Current mode: {current_mode}'}
                time.sleep(1.0)  # Wait for mode change
            
            # Step 2: Set to AUTO mode to start mission
            logger.info(f" Starting AUTO mission for Drone {self.drone_id}")
            success = self.set_mode('AUTO')
            
            if success:
                self.mission_active = True
                self.current_waypoint_index = 0
                logger.info(f" Mission started for Drone {self.drone_id} (TAKEOFF + {len(self.mission_waypoints)} waypoints)")
                return {'success': True, 'message': f'Mission started - {len(self.mission_waypoints)} waypoints'}
            else:
                logger.error(f"Failed to set AUTO mode for Drone {self.drone_id}")
                return {'success': False, 'error': f'Failed to set AUTO mode. Current mode: {self.telemetry.get("flight_mode", "UNKNOWN")}'}
                
        except Exception as e:
            logger.error(f"Failed to start mission for Drone {self.drone_id}: {e}")
            return {'success': False, 'error': f'Mission start exception: {str(e)}'}
    
    def pause_mission(self):
        """Pause mission by switching to LOITER"""
        try:
            logger.info(f" Pausing mission for Drone {self.drone_id}")
            return self.set_mode('LOITER')
        except Exception as e:
            logger.error(f"Failed to pause mission: {e}")
            return False
    
    def resume_mission(self):
        """Resume mission by switching back to AUTO"""
        try:
            logger.info(f" Resuming mission for Drone {self.drone_id}")
            success = self.set_mode('AUTO')
            if success:
                self.mission_active = True
            return success
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
            
            total = len(self.mission_waypoints)
            current = self.current_waypoint_index
            progress = (current / total * 100) if total > 0 else 0
            
            return {
                'active': self.mission_active,
                'total_waypoints': total,
                'current_waypoint': current,
                'progress_percent': progress,
                'waypoints_remaining': total - current
            }
        except Exception as e:
            logger.error(f"Failed to get mission status: {e}")
            return {
                'active': self.mission_active,
                'total_waypoints': len(self.mission_waypoints),
                'current_waypoint': self.current_waypoint_index,
                'progress_percent': 0,
                'waypoints_remaining': 0
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

    drone = drones[drone_id]
    telemetry = drone.get_telemetry() if hasattr(drone, 'get_telemetry') else {}

    # Add debug info
    debug_info = {
        'simulation_mode': drone.simulation,
        'connected': drone.connected,
        'has_gps_data': telemetry.get('satellites_visible', 0) > 0,
        'has_battery_data': telemetry.get('battery_voltage', 0) > 0,
        'has_position_data': telemetry.get('latitude', 0) != 0 or telemetry.get('longitude', 0) != 0,
        'has_altitude_data': telemetry.get('relative_altitude', 0) != 0 or telemetry.get('altitude', 0) != 0,
        'data_age_seconds': time.time() - telemetry.get('timestamp', time.time()) if telemetry else None
    }

    if not drone.connected:
        logger.warning(f"/telemetry requested for Drone {drone_id} but it's not connected; returning last-known telemetry")
        return jsonify({
            'drone_id': drone_id,
            'connected': False,
            'simulation': drone.simulation,
            'telemetry': telemetry,
            'timestamp': telemetry.get('timestamp', time.time()) if telemetry else time.time(),
            'debug': debug_info,
            'message': 'Drone not connected; returning last-known telemetry if available'
        }), 200

    return jsonify({
        'drone_id': drone_id,
        'connected': True,
        'simulation': drone.simulation,
        'telemetry': telemetry,
        'timestamp': telemetry.get('timestamp', time.time()),
        'debug': debug_info
    })


@app.route('/drone/<int:drone_id>/debug', methods=['GET'])
def debug_telemetry(drone_id):
    """Debug endpoint to see raw telemetry data"""
    if drone_id not in drones:
        return jsonify({'error': 'Drone not found'}), 404

    drone = drones[drone_id]
    telemetry = drone.get_telemetry() if hasattr(drone, 'get_telemetry') else {}

    # Return formatted for easy reading
    payload = {
        'drone_id': drone_id,
        'connected': drone.connected,
        'running': drone.running,
        'telemetry_fields': list(telemetry.keys()),
        'telemetry_values': telemetry,
        'non_zero_fields': {k: v for k, v in telemetry.items() if v not in [0, 0.0, False, 'UNKNOWN', '']}
    }

    if not drone.connected:
        payload['message'] = 'Drone not connected; returning last-known telemetry (if any)'

    return jsonify(payload)


@app.route('/drone/<int:drone_id>/arm', methods=['POST'])
def arm_drone(drone_id):
    """Arm a drone"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'success': False, 'error': 'Drone not connected', 'command': 'arm'}), 404
    
    result = drones[drone_id].arm()
    if result['success']:
        return jsonify({'success': True, 'command': 'arm', 'message': result.get('message', 'Armed')})
    else:
        return jsonify({'success': False, 'command': 'arm', 'error': result.get('error', 'ARM failed')}), 400


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
        return jsonify({'error': 'Drone not connected'}), 404
    
    data = request.json
    waypoints = data.get('waypoints', [])
    
    if not waypoints:
        return jsonify({'error': 'No waypoints provided'}), 400
    
    success = drones[drone_id].upload_mission_waypoints(waypoints)
    return jsonify({
        'success': success,
        'command': 'mission_upload',
        'waypoint_count': len(waypoints)
    })


@app.route('/drone/<int:drone_id>/mission/start', methods=['POST'])
def start_mission(drone_id):
    """Start the uploaded mission"""
    if drone_id not in drones or not drones[drone_id].connected:
        return jsonify({'success': False, 'error': 'Drone not connected', 'command': 'mission_start'}), 404
    
    result = drones[drone_id].start_mission()
    if result['success']:
        return jsonify({'success': True, 'command': 'mission_start', 'message': result.get('message', 'Mission started')})
    else:
        return jsonify({'success': False, 'command': 'mission_start', 'error': result.get('error', 'Mission start failed')}), 400


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
