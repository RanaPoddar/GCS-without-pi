
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


cd external-services

python pymavlink_service.py


