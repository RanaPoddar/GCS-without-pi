#!/usr/bin/env python3
"""
KML Mission Planner for NIdar Competition
Parses KML boundary file and generates survey mission waypoints
Optimized for yellow leaf detection with minimal flight time
"""

import sys
import xml.etree.ElementTree as ET
import json
import math
from pathlib import Path
from typing import List, Tuple
import argparse

# Try to import shapely, provide helpful error if missing
try:
    from shapely.geometry import Polygon, LineString, Point
except ImportError as e:
    print("ERROR: shapely library is not installed!", file=sys.stderr)
    print("Please install it with: pip install shapely", file=sys.stderr)
    print(f"Import error details: {e}", file=sys.stderr)
    sys.exit(1)

class KMLMissionPlanner:
    """Generate survey mission from KML boundary
    
    Optimized for yellow paper plant detection in cricket stadium:
    - Target: Yellow paper plants at center of 2ft (~0.6m) radius circles
    - Non-target: Green paper plants
    - Goal: Accurate geolocation of yellow plants
    """
    
    # Earth radius for conversions
    EARTH_RADIUS_M = 6378137.0
    
    def __init__(self, altitude_m=10, speed_ms=3.0, lateral_overlap=0.20):
        """
        Initialize mission planner
        Optimized for yellow leaf detection with minimal flight time
        
        Args:
            altitude_m: Flight altitude in meters AGL (default: 10m for optimal detection)
            speed_ms: Ground speed in m/s (default: 3.0 m/s for faster scanning)
            lateral_overlap: Overlap between passes (default: 0.20 = 20% for time efficiency)
        """
        self.altitude_m = altitude_m
        self.speed_ms = speed_ms
        self.lateral_overlap = lateral_overlap
        
        # Camera specs (Pi HQ Camera + 6mm lens)
        self.ground_width_m = self._calculate_ground_width(altitude_m)
        self.swath_width_m = self.ground_width_m * (1 - lateral_overlap)
        
        # Calculate Ground Sample Distance (GSD) for detection accuracy
        # Pi HQ Camera: 4056 x 3040 pixels (12.3 MP)
        self.camera_width_px = 4056
        self.gsd_mm_per_px = (self.ground_width_m * 1000) / self.camera_width_px
        
        # Target detection capability
        # Yellow plant: 0.5 ft radius (1 ft diameter) = 0.3048m
        # Placed in 2 ft radius circle (rest is grass)
        target_diameter_m = 1 * 0.3048  # 1 ft diameter = 0.3048m
        pixels_across_target = target_diameter_m / (self.gsd_mm_per_px / 1000)
        
        print(f"[INFO] Mission Parameters:")
        print(f"   Altitude: {altitude_m}m")
        print(f"   Speed: {speed_ms} m/s")
        print(f"   Ground coverage width: {self.ground_width_m:.1f}m")
        print(f"   Swath width ({lateral_overlap*100:.0f}% overlap): {self.swath_width_m:.1f}m")
        print(f"\n[DETECTION] Yellow Plant Detection Capability:")
        print(f"   Ground Sample Distance (GSD): {self.gsd_mm_per_px:.1f} mm/pixel")
        print(f"   Yellow plant size: 1ft diameter (0.5ft radius)")
        print(f"   Plant coverage: ~{pixels_across_target:.0f} pixels across")
        print(f"   GPS accuracy: ~{self.gsd_mm_per_px * 3:.1f}mm (3-pixel center estimation)")
        if pixels_across_target >= 100:
            print(f"   Detection quality: EXCELLENT (>100px for yellow color discrimination)")
        elif pixels_across_target >= 60:
            print(f"   Detection quality: GOOD (60-100px sufficient for detection)")
        elif pixels_across_target >= 40:
            print(f"   Detection quality: ADEQUATE (40-60px marginal)")
        else:
            print(f"   Detection quality: INSUFFICIENT (<40px - reduce altitude or reduce speed)")
    
    def _calculate_ground_width(self, altitude_m):
        """Calculate ground coverage width at given altitude
        
        At 10m altitude: ~12.6m coverage width
        With 20% overlap: ~10.1m effective swath width
        Optimal for yellow leaf detection with minimal flight time
        """
        # Pi HQ Camera + 6mm lens: 66.7° horizontal FOV
        fov_horizontal_rad = math.radians(66.7)
        return 2 * altitude_m * math.tan(fov_horizontal_rad / 2)
    
    def parse_kml(self, kml_file):
        """
        Parse KML file and extract boundary coordinates
        
        Args:
            kml_file: Path to KML file
            
        Returns:
            List of (lat, lon) tuples defining boundary
        """
        tree = ET.parse(kml_file)
        root = tree.getroot()
        
        # Handle KML namespace
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Find coordinates in Polygon or LinearRing
        coords_elem = root.find('.//kml:coordinates', ns)
        if coords_elem is None:
            # Try without namespace
            coords_elem = root.find('.//coordinates')
        
        if coords_elem is None:
            raise ValueError("No coordinates found in KML file")
        
        # Parse coordinate string (format: "lon,lat,alt lon,lat,alt ...")
        coords_text = coords_elem.text.strip()
        boundary = []
        
        for coord in coords_text.split():
            parts = coord.split(',')
            if len(parts) >= 2:
                lon, lat = float(parts[0]), float(parts[1])
                boundary.append((lat, lon))
        
        if len(boundary) < 3:
            raise ValueError("Boundary must have at least 3 points")
        
        print(f"\n[GPS] KML Boundary parsed: {len(boundary)} points")
        print(f"   SW corner: {min(boundary, key=lambda x: x[0])[0]:.6f}, {min(boundary, key=lambda x: x[1])[1]:.6f}")
        print(f"   NE corner: {max(boundary, key=lambda x: x[0])[0]:.6f}, {max(boundary, key=lambda x: x[1])[1]:.6f}")
        
        return boundary
    
    def meters_to_lat(self, meters):
        """Convert meters to latitude degrees"""
        return meters / self.EARTH_RADIUS_M * (180 / math.pi)
    
    def meters_to_lon(self, meters, latitude):
        """Convert meters to longitude degrees at given latitude"""
        return meters / (self.EARTH_RADIUS_M * math.cos(math.radians(latitude))) * (180 / math.pi)
    
    def lat_lon_to_meters(self, lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two GPS points"""
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return self.EARTH_RADIUS_M * c
    
    def calculate_heading(self, lat1, lon1, lat2, lon2):
        """Calculate heading in degrees from point 1 to point 2"""
        dlon = math.radians(lon2 - lon1)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        
        x = math.sin(dlon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
        heading = math.degrees(math.atan2(x, y))
        return (heading + 360) % 360
    
    def generate_survey_waypoints(self, boundary):
        """
        Generate lawnmower survey pattern inside arbitrary polygon boundary using Shapely
        Adds 5m safety margin from boundary edges
        Args:
            boundary: List of (lat, lon) tuples
        Returns:
            List of waypoint dicts, metadata
        """
        # Convert boundary to Shapely Polygon (lon, lat order for Shapely)
        poly = Polygon([(lon, lat) for lat, lon in boundary])
        
        # Apply 5m negative buffer (inward) for safety margin
        # Convert 5 meters to degrees (approximate at center latitude)
        center_lat_temp = sum(lat for lat, _ in boundary) / len(boundary)
        margin_deg = self.meters_to_lat(5.0)  # ~5m in latitude degrees
        poly = poly.buffer(-margin_deg)  # Negative buffer = shrink polygon inward
        
        if poly.is_empty or poly.area < 1e-10:
            raise ValueError("Field too small after applying 5m safety margin")
        
        print(f"[SAFETY] Applied 5m inward margin from boundary edges")
        lats = [p[0] for p in boundary]
        lons = [p[1] for p in boundary]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        field_length_m = self.lat_lon_to_meters(min_lat, center_lon, max_lat, center_lon)
        field_width_m = self.lat_lon_to_meters(center_lat, min_lon, center_lat, max_lon)
        print(f"\n[FIELD] Field Dimensions:")
        print(f"   Length: {field_length_m:.0f}m ({field_length_m/1609.34*5280:.0f} ft)")
        print(f"   Width: {field_width_m:.0f}m ({field_width_m/1609.34*5280:.0f} ft)")
        print(f"   Area: {poly.area:.6f} (deg², not meters²)")

        # Survey direction: default to E-W (lines of constant lat)
        # You can make this smarter by analyzing polygon orientation
        swath = self.swath_width_m
        # Step in latitude (meters to degrees)
        step_lat = self.meters_to_lat(swath)
        # Start just south of min_lat, end just north of max_lat
        lat = min_lat + step_lat/2
        waypoints = []
        waypoint_id = 1
        direction = 1  # 1 = east, -1 = west
        pass_count = 0
        while lat <= max_lat:
            # Create a long E-W line at this latitude
            line = LineString([
                (min_lon-0.01, lat),
                (max_lon+0.01, lat)
            ])
            # Intersect with polygon
            clipped = poly.intersection(line)
            if clipped.is_empty:
                lat += step_lat
                continue
            # clipped can be MultiLineString or LineString
            if clipped.geom_type == 'LineString':
                segments = [clipped]
            elif clipped.geom_type == 'MultiLineString':
                segments = list(clipped.geoms)
            else:
                lat += step_lat
                continue
            for seg in segments:
                coords = list(seg.coords)
                if direction == 1:
                    start, end = coords[0], coords[-1]
                else:
                    start, end = coords[-1], coords[0]
                # Add start waypoint
                waypoints.append({
                    "id": waypoint_id,
                    "seq": waypoint_id - 1,
                    "latitude": start[1],
                    "longitude": start[0],
                    "altitude": self.altitude_m,
                    "speed": self.speed_ms,
                    "command": "NAV_WAYPOINT",
                    "frame": "MAV_FRAME_GLOBAL_RELATIVE_ALT"
                })
                waypoint_id += 1
                # Add end waypoint
                waypoints.append({
                    "id": waypoint_id,
                    "seq": waypoint_id - 1,
                    "latitude": end[1],
                    "longitude": end[0],
                    "altitude": self.altitude_m,
                    "speed": self.speed_ms,
                    "command": "NAV_WAYPOINT",
                    "frame": "MAV_FRAME_GLOBAL_RELATIVE_ALT"
                })
                waypoint_id += 1
                pass_count += 1
                direction *= -1  # Alternate direction
            lat += step_lat
        total_distance = pass_count * field_width_m
        mission_time_s = total_distance / self.speed_ms
        mission_time_min = mission_time_s / 60
        print(f"\n[MISSION] Mission Estimate:")
        print(f"   Total waypoints: {len(waypoints)}")
        print(f"   Passes: {pass_count}")
        print(f"   Flight distance: {total_distance:.0f}m")
        print(f"   Flight time: {mission_time_min:.1f} min (excluding turns)")
        print(f"   Estimated with turns: {mission_time_min * 1.15:.1f} min")
        return waypoints, {
            'center_lat': center_lat,
            'center_lon': center_lon,
            'field_length_m': field_length_m,
            'field_width_m': field_width_m,
            'num_passes': pass_count,
            'mission_time_min': mission_time_min * 1.15
        }
    
    def create_waypoints_file(self, waypoints, metadata, output_file='mission.waypoints'):
        """Create Mission Planner .waypoints file for comparison
        
        Format: QGC WPL 110
        seq\tcurrent\tframe\tcommand\tparam1\tparam2\tparam3\tparam4\tlat\tlon\talt\tautocontinue
        """
        with open(output_file, 'w') as f:
            # Header
            f.write("QGC WPL 110\n")
            
            # Line 0: HOME waypoint (current=1, frame=0, command=16)
            # Use first survey waypoint's position as HOME location
            # Altitude will be set by drone when armed (AMSL)
            if waypoints:
                home_lat = waypoints[0]['latitude']
                home_lon = waypoints[0]['longitude']
            else:
                home_lat = metadata['center_lat']
                home_lon = metadata['center_lon']
            home_alt = 0.0  # Will be set by drone at arming time (AMSL)
            f.write(f"0\t1\t0\t16\t0\t0\t0\t0\t{home_lat:.8f}\t{home_lon:.8f}\t{home_alt:.6f}\t1\n")
            
            # Line 1: TAKEOFF (current=0, frame=3, command=22, use HOME coordinates)
            # ArduCopter requires actual coordinates for TAKEOFF in AUTO mode, not 0.0
            f.write(f"1\t0\t3\t22\t0.00000000\t0.00000000\t0.00000000\t0.00000000\t{home_lat:.8f}\t{home_lon:.8f}\t{self.altitude_m:.6f}\t1\n")
            
            # Line 2: DO_CHANGE_SPEED (optional, command=178)
            # param1=1 (groundspeed), param2=speed in m/s
            f.write(f"2\t0\t3\t178\t1.00000000\t{self.speed_ms:.8f}\t0.00000000\t0.00000000\t0.00000000\t0.00000000\t0.000000\t1\n")
            
            # Lines 3+: Survey waypoints (frame=3, command=16)
            for idx, wp in enumerate(waypoints, start=3):
                lat = wp['latitude']
                lon = wp['longitude']
                alt = wp['altitude']
                # All survey waypoints: current=0, frame=3, command=16, params=0
                f.write(f"{idx}\t0\t3\t16\t0.00000000\t0.00000000\t0.00000000\t0.00000000\t{lat:.8f}\t{lon:.8f}\t{alt:.6f}\t1\n")
            
            # Last line: RTL (command=20)
            rtl_seq = 3 + len(waypoints)
            f.write(f"{rtl_seq}\t0\t3\t20\t0.00000000\t0.00000000\t0.00000000\t0.00000000\t0.00000000\t0.00000000\t0.000000\t1\n")
        
        total_lines = 3 + len(waypoints) + 1  # HOME + TAKEOFF + SPEED + waypoints + RTL
        print(f"\n[OK] Mission Planner .waypoints file created: {output_file}")
        print(f"   Format: QGC WPL 110 (Mission Planner compatible)")
        print(f"   Total mission items: {total_lines} (HOME + TAKEOFF + SPEED + {len(waypoints)} waypoints + RTL)")
        return output_file
    
    def create_mission_file(self, waypoints, metadata, output_file='mission.json'):
        """Create mission JSON file for upload
        
        NOTE: Only includes survey waypoints for map display.
        Backend (pymavlink_service.py) will add HOME, TAKEOFF, and RTL during upload.
        """
        mission = {
            "version": "1.0",
            "mission_name": "KML_Survey_Mission",
            "created": "auto-generated",
            "frame_type": "MAV_FRAME_GLOBAL_RELATIVE_ALT",
            "home_position": {
                "latitude": metadata['center_lat'],
                "longitude": metadata['center_lon'],
                "altitude": 0
            },
            "mission_params": {
                "altitude_m": self.altitude_m,
                "speed_ms": self.speed_ms,
                "swath_width_m": self.swath_width_m,
                "lateral_overlap": self.lateral_overlap,
                "field_length_m": metadata['field_length_m'],
                "field_width_m": metadata['field_width_m'],
                "num_passes": metadata['num_passes'],
                "estimated_time_min": metadata['mission_time_min']
            },
            "waypoints": waypoints,  # Only survey waypoints (backend adds HOME/TAKEOFF/RTL)
            "rtl_altitude": self.altitude_m + 10
        }
        
        with open(output_file, 'w') as f:
            json.dump(mission, f, indent=2)
        
        print(f"\n[OK] Mission file created: {output_file}")
        return output_file

def main():
    parser = argparse.ArgumentParser(description='Generate optimized survey mission for yellow leaf detection')
    parser.add_argument('kml_file', help='Path to KML boundary file')
    parser.add_argument('-a', '--altitude', type=float, default=10,
                       help='Flight altitude in meters (default: 10m for optimal detection)')
    parser.add_argument('-s', '--speed', type=float, default=3.0,
                       help='Ground speed in m/s (default: 3.0 for faster scanning)')
    parser.add_argument('-o', '--overlap', type=float, default=0.20,
                       help='Lateral overlap 0-1 (default: 0.20 = 20%% for minimal flight time)')
    parser.add_argument('--output', default='mission.json',
                       help='Output mission file (default: mission.json)')
    
    args = parser.parse_args()
    
    try:
        # Verify input file exists
        if not Path(args.kml_file).exists():
            print(f"ERROR: KML file not found: {args.kml_file}", file=sys.stderr)
            return 1
        
        print(f"Processing KML file: {args.kml_file}", file=sys.stderr)
        
        # Create planner
        planner = KMLMissionPlanner(
            altitude_m=args.altitude,
            speed_ms=args.speed,
            lateral_overlap=args.overlap
        )
        
        # Parse KML
        boundary = planner.parse_kml(args.kml_file)
        
        # Generate waypoints
        waypoints, metadata = planner.generate_survey_waypoints(boundary)
        
        # Create mission JSON file
        planner.create_mission_file(waypoints, metadata, args.output)
        
        # Create Mission Planner .waypoints file for comparison
        waypoints_file = args.output.replace('.json', '.waypoints')
        planner.create_waypoints_file(waypoints, metadata, waypoints_file)
        
        print(f"\n[OK] Ready to fly!")
        print(f"   JSON file: {args.output} (for dashboard upload)")
        print(f"   .waypoints file: {waypoints_file} (Mission Planner format for comparison)")
        
    except ImportError as e:
        print(f"\n[ERROR] Missing Python library: {e}", file=sys.stderr)
        print("Please install required libraries with: pip install shapely", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"\n[ERROR] File not found: {e}", file=sys.stderr)
        return 1
    except ET.ParseError as e:
        print(f"\n[ERROR] Invalid KML file format: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"\n[ERROR] Invalid data: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1
        return 1
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
