#!/usr/bin/env python3
"""
Test MAVLink Command Sending - Run on GCS laptop
Tests if COMMAND_LONG messages reach the serial port
"""

from pymavlink import mavutil
import time

print("📡 Testing MAVLink COMMAND_LONG transmission")
print("=" * 50)

# Connect to COM4 (same as PyMAVLink service)
print("Connecting to COM4...")
master = mavutil.mavlink_connection('COM4', baud=57600, source_system=255, source_component=0)

print("Waiting for heartbeat...")
heartbeat = master.wait_heartbeat(timeout=5)

if heartbeat:
    print(f"✅ Connected! Target: System {master.target_system}, Component {master.target_component}")
    
    print("\nSending COMMAND_LONG (42000 - Start Detection)...")
    master.mav.command_long_send(
        master.target_system,      # target_system
        master.target_component,    # target_component
        42000,                      # command (START_DETECTION)
        0,                          # confirmation
        0, 0, 0, 0, 0, 0, 0        # params 1-7
    )
    
    print("Waiting for COMMAND_ACK...")
    start = time.time()
    ack = master.recv_match(type='COMMAND_ACK', blocking=True, timeout=5.0)
    elapsed = time.time() - start
    
    if ack:
        print(f"✅ ACK received after {elapsed:.2f}s:")
        print(f"   Command: {ack.command}")
        print(f"   Result: {ack.result} (0=accepted, 4=unsupported)")
    else:
        print(f"❌ No ACK received after {elapsed:.2f}s")
        print("\nPossible issues:")
        print("  1. Pi not running pi_controller.py")
        print("  2. Pi command listener not initialized")
        print("  3. Serial connection issue")
    
else:
    print("❌ No heartbeat - drone not connected")

print("\nDone!")
