Linux :
source myvenv/bin/activate
./start-pymavlink.sh

Windows :
myvenv\Scripts\activate
./start-pymavlink.ps1

### For Logs :
- Start services
./start-pymavlink.sh

- In another terminal, watch PyMAVLink logs
tail -f pymavlink.log

- In another terminal, watch Node.js logs
tail -f combined.log

KIll services :
pkill -f pymavlink_service
pkill -f "node server"


Mission Start Flow:
   1. upload KML → Mission generated
   2. Click 'Start Mission'
   3. System checks drone position vs mission start
   4. Uploads waypoints (NAV + TAKEOFF + Survey)
   5. ARMs drone (with detailed error checking)
   6. Starts AUTO mode
   7. Drone navigates to start → takes off → executes mission