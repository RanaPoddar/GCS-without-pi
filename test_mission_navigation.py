#!/usr/bin/env python3
"""
Test script to demonstrate the mission start navigation fix
Shows how the waypoint list is constructed with NAV → TAKEOFF → Survey
"""

import sys
import math

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two GPS points"""
    R = 6371000  # Earth radius in meters
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

# Simulated test data
print("=" * 70)
print("MISSION START NAVIGATION FIX - TEST DEMONSTRATION")
print("=" * 70)

# Current drone position (simulated)
drone_lat = 23.295000
drone_lon = 85.310000

# Mission waypoints (from KML)
mission_waypoints = [
    {'latitude': 23.295100, 'longitude': 85.310200, 'altitude': 15},  # First survey point
    {'latitude': 23.295150, 'longitude': 85.310200, 'altitude': 15},
    {'latitude': 23.295150, 'longitude': 85.310150, 'altitude': 15},
    {'latitude': 23.295100, 'longitude': 85.310150, 'altitude': 15},
]

first_waypoint = mission_waypoints[0]

# Calculate distance
distance = calculate_distance(
    drone_lat, drone_lon,
    first_waypoint['latitude'], first_waypoint['longitude']
)

print(f"\n📍 CURRENT SITUATION:")
print(f"   Drone position:   {drone_lat:.6f}, {drone_lon:.6f}")
print(f"   Mission start:    {first_waypoint['latitude']:.6f}, {first_waypoint['longitude']:.6f}")
print(f"   Distance apart:   {distance:.1f} meters")

print(f"\n🔴 OLD BEHAVIOR (WITHOUT FIX):")
print(f"   Waypoint 0: TAKEOFF at [{first_waypoint['latitude']:.6f}, {first_waypoint['longitude']:.6f}, {first_waypoint['altitude']}m]")
print(f"   Waypoint 1: Survey point 1")
print(f"   Waypoint 2: Survey point 2")
print(f"   ...")
print(f"\n   ❌ Problem: Drone takes off from CURRENT position ({drone_lat:.6f}, {drone_lon:.6f})")
print(f"   ❌ Then flies to first survey point AFTER being airborne")
print(f"   ❌ Entire mission is offset by {distance:.1f}m!")

print(f"\n🟢 NEW BEHAVIOR (WITH FIX):")
print(f"   Waypoint 0: NAVIGATE to [{first_waypoint['latitude']:.6f}, {first_waypoint['longitude']:.6f}, 5m]")
print(f"               ↓ (drone flies horizontally at 5m altitude)")
print(f"   Waypoint 1: TAKEOFF at [{first_waypoint['latitude']:.6f}, {first_waypoint['longitude']:.6f}, {first_waypoint['altitude']}m]")
print(f"               ↓ (drone climbs vertically to survey altitude)")
print(f"   Waypoint 2: Survey point 1")
print(f"   Waypoint 3: Survey point 2")
print(f"   ...")
print(f"\n   ✅ Solution: Drone navigates to start point FIRST at low altitude")
print(f"   ✅ Then performs vertical takeoff at correct location")
print(f"   ✅ Mission executes exactly as planned!")

# Show the constructed mission
print(f"\n📋 CONSTRUCTED MISSION WAYPOINTS:")
print(f"   Total waypoints: {len(mission_waypoints) + 2}")
print(f"   Transit time to start: ~{int(distance / 10)} seconds (at 10 m/s)")

nav_waypoint = {
    'latitude': first_waypoint['latitude'],
    'longitude': first_waypoint['longitude'],
    'altitude': 5,
    'command': 'MAV_CMD_NAV_WAYPOINT'
}

takeoff_waypoint = {
    'latitude': first_waypoint['latitude'],
    'longitude': first_waypoint['longitude'],
    'altitude': first_waypoint['altitude'],
    'command': 'MAV_CMD_NAV_TAKEOFF'
}

full_mission = [nav_waypoint, takeoff_waypoint] + mission_waypoints

for i, wp in enumerate(full_mission[:5]):  # Show first 5 waypoints
    cmd = wp.get('command', 'MAV_CMD_NAV_WAYPOINT')
    cmd_name = 'NAVIGATE' if i == 0 else ('TAKEOFF' if i == 1 else 'SURVEY')
    print(f"\n   [{i}] {cmd_name}")
    print(f"       Command: {cmd}")
    print(f"       Position: {wp['latitude']:.6f}, {wp['longitude']:.6f}")
    print(f"       Altitude: {wp['altitude']}m")

print(f"\n   ... ({len(full_mission) - 5} more waypoints)")

print(f"\n✅ MISSION VALIDATION:")
if distance > 10:
    print(f"   ⚠️  WARNING: Drone is {distance:.1f}m from start (> 10m threshold)")
    print(f"   ⚠️  Navigation phase will add ~{int(distance / 10)} seconds")
else:
    print(f"   ✅ Drone position OK ({distance:.1f}m from start)")

print(f"\n" + "=" * 70)
print("Ready to start mission!")
print("=" * 70 + "\n")
