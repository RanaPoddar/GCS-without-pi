#!/usr/bin/env python3
"""
Verify MAVLink Command Setup - Check if system is ready for long-range control
"""

import sys
import json
from pathlib import Path

def check_gcs_setup():
    """Check GCS side setup"""
    print("\n📡 GCS SIDE CHECK")
    print("=" * 60)
    
    issues = []
    
    # Check if pymavlink is available
    try:
        from pymavlink import mavutil
        print("✅ PyMAVLink installed")
    except ImportError:
        print("❌ PyMAVLink not installed")
        issues.append("Install: pip install pymavlink")
    
    # Check if command sender script exists
    if Path("send-mavlink-command.py").exists():
        print("✅ Command sender script ready")
    else:
        print("❌ Command sender script missing")
        issues.append("Create send-mavlink-command.py")
    
    # Check if pymavlink service exists
    if Path("external-services/pymavlink_service.py").exists():
        print("✅ PyMAVLink service exists")
    else:
        print("⚠️  PyMAVLink service not found")
    
    return issues

def check_pi_config():
    """Check Pi configuration"""
    print("\n🤖 PI SIDE CHECK")
    print("=" * 60)
    
    issues = []
    pi_config_path = Path("../rpi-connect/config.json")
    
    if not pi_config_path.exists():
        print("❌ Pi config.json not found")
        print("   Expected at: ../rpi-connect/config.json")
        return ["Cannot verify Pi config - file not found"]
    
    try:
        with open(pi_config_path) as f:
            config = json.load(f)
        
        # Check Socket.IO setting
        socketio_enabled = config.get('socketio', {}).get('enabled', True)
        if socketio_enabled:
            print("⚠️  Socket.IO enabled (good for short-range only)")
            print("   For long-range, set socketio.enabled = false")
        else:
            print("✅ Socket.IO disabled (telemetry-only mode)")
            print("   Perfect for long-range operations")
        
        # Check Pixhawk settings
        pixhawk = config.get('pixhawk', {})
        if pixhawk.get('enabled', True):
            print("✅ Pixhawk enabled")
            conn = pixhawk.get('connection_string', 'unknown')
            print(f"   Connection: {conn}")
        else:
            print("❌ Pixhawk disabled")
            issues.append("Enable Pixhawk in config.json")
        
        # Check MAVLink detection
        mavlink_det = config.get('mavlink_detection', {})
        if mavlink_det.get('enabled', False):
            print("✅ MAVLink detection transmission enabled")
        else:
            print("❌ MAVLink detection disabled")
            issues.append("Enable mavlink_detection in config.json")
        
        # Check detection settings
        detection = config.get('detection', {})
        if detection.get('enabled', True):
            print("✅ Detection enabled")
        else:
            print("⚠️  Detection disabled")
        
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        issues.append("Fix config.json syntax")
    
    return issues

def print_next_steps(gcs_issues, pi_issues):
    """Print next steps"""
    print("\n" + "=" * 60)
    
    all_issues = gcs_issues + pi_issues
    
    if not all_issues:
        print("🎉 ALL CHECKS PASSED!")
        print("\n✅ Your system is ready for long-range MAVLink control")
        print("\nNext steps:")
        print("1. Start Pi: python3 pi_controller.py")
        print("2. Connect radios: GCS radio → USB, Drone radio → Pixhawk")
        print("3. Send commands: python send-mavlink-command.py COM5")
        print("\n💡 Detection will work up to 2-10km via telemetry radio")
    else:
        print("⚠️  SETUP INCOMPLETE")
        print("\nIssues found:")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
        
        print("\n📋 Recommended Pi config.json settings for long-range:")
        print("""
{
  "socketio": {
    "enabled": false  ← Disable WiFi dependency
  },
  "pixhawk": {
    "enabled": true,
    "connection_string": "/dev/ttyAMA0",
    "baud_rate": 921600
  },
  "mavlink_detection": {
    "enabled": true  ← Enable radio transmission
  },
  "detection": {
    "enabled": true
  }
}
        """)

def main():
    print("=" * 60)
    print("MAVLink Command Setup Verification")
    print("=" * 60)
    print("\nThis checks if your system is configured for long-range")
    print("detection control via telemetry radio (1-10km range)")
    
    gcs_issues = check_gcs_setup()
    pi_issues = check_pi_config()
    
    print_next_steps(gcs_issues, pi_issues)
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
