#!/usr/bin/env python3
import sys, time
from pymavlink import mavutil

def send_cmd(m, cmd_id, p1=0):
    m.mav.command_long_send(m.target_system, m.target_component, cmd_id, 0, p1, 0, 0, 0, 0, 0, 0)
    ack = m.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
    return ack and ack.result == 0

port = sys.argv[1] if len(sys.argv) > 1 else 'COM4'
print(f'📡 MAVLink Command Sender')
print(f'Port: {port} @ 57600 baud')
print('=' * 50)

try:
    print(f'Connecting...')
    # Important: Use source_system=255 to match test-command-send.py
    m = mavutil.mavlink_connection(port, baud=57600, source_system=255, source_component=0)
    print('Waiting for heartbeat...')
    m.wait_heartbeat(timeout=10)
    print(f'✅ Connected! Target System: {m.target_system}\n')
except Exception as e:
    print(f'❌ Failed: {e}\n')
    print(f'💡 Common fixes:')
    print(f'   1. Close Mission Planner / QGC / other MAVLink tools')
    print(f'   2. Check Device Manager for correct port')
    print(f'   3. Try: python test-command-send.py (works same way)')
    print(f'   4. Verify radio is powered and connected')
    sys.exit(1)

while True:
    print('\n1=Start Detection  2=Stop  0=Exit')
    c = input('Choice: ').strip()
    if c == '1':
        print('Starting detection...')
        send_cmd(m, 42000) and print('OK') or print('Failed')
    elif c == '2':
        print('Stopping detection...')
        send_cmd(m, 42001) and print('OK') or print('Failed')
    elif c == '0':
        break
