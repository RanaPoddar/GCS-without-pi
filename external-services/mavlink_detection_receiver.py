import threading
from flask import Flask
from pymavlink import mavutil
import socketio

# CONFIGURATION
MAVLINK_CONNECTION = 'udp:0.0.0.0:14550'  # Update as needed for your GCS
NODE_SERVER_URL = 'http://localhost:3000'  # Update to your Node.js server address/port

# Set up Flask and Socket.IO client
app = Flask(__name__)
sio = socketio.Client()
sio.connect(NODE_SERVER_URL)

def parse_detection_statustext(text):
    # Example: DET|ID|LAT|LON|CONF|AREA
    if text.startswith('DET|'):
        parts = text.strip().split('|')
        if len(parts) >= 6:
            return {
                'detection_id': parts[1],
                'latitude': float(parts[2]),
                'longitude': float(parts[3]),
                'confidence': float(parts[4]),
                'area': int(parts[5])
            }
    return None

def mavlink_listener():
    master = mavutil.mavlink_connection(MAVLINK_CONNECTION)
    print(f"Listening for MAVLink STATUSTEXT on {MAVLINK_CONNECTION}")
    while True:
        msg = master.recv_match(type='STATUSTEXT', blocking=True)
        if msg:
            text = msg.text
            detection = parse_detection_statustext(text)
            if detection:
                print("Detection received:", detection)
                # Forward to Node.js server via Socket.IO
                sio.emit('mavlink_detection', detection)

# Run the MAVLink listener in a background thread
threading.Thread(target=mavlink_listener, daemon=True).start()

@app.route('/')
def index():
    return "MAVLink Flask Receiver Running"

if __name__ == '__main__':
    app.run(port=5001)
