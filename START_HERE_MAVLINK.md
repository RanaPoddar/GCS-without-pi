# 🎯 START HERE: Control Detection via Radio (No WiFi Needed)

## Step 1: Start Pi
```bash
# On Raspberry Pi terminal
cd /home/pi/rpi-connect
source venv/bin/activate
python3 pi_controller.py
```

## Step 2: Send Commands from GCS
```bash
# On your Windows computer
cd C:\Users\ranab\Desktop\GCS-without-pi
python send-mavlink-cmd.py
```

Or if COM4 doesn't work, try:
```bash
python send-mavlink-cmd.py COM5
```

## Step 3: Control Detection
```
1=Start Detection  2=Stop  0=Exit
Choice: 1    ← Press 1 and Enter
```

## That's It!

Detection will work up to **2-10km** via telemetry radio.

---

## Troubleshooting

**"No heartbeat"** → Wrong COM port. Find yours:
```powershell
[System.IO.Ports.SerialPort]::getportnames()
```

**"Failed"** → Pi not running. Check Step 1.

---

## What's Happening?

```
Your Computer → USB → Telemetry Radio 
                         ↓ (915MHz/433MHz)
                    Telemetry Radio → Pixhawk → Pi
```

Commands: `YOU → Radio → Pixhawk → Pi → Start Detection`  
Detections: `Pi → Pixhawk → Radio → YOU → Dashboard`

**No WiFi needed. Works in remote fields. 2-10km range.**
