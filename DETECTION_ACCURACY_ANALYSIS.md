# Yellow Plant Detection System - Accuracy Analysis

## System Overview

Your detection pipeline consists of three main components:

### 1. **Yellow Crop Detector** (`yellow_crop_detector.py`)
- **Method:** HSV color space analysis
- **Target:** Yellow paper plants (0.5 ft diameter / 0.25 ft radius)
- **Detection Range:** HSV(20-30, 90-255, 60-255) - tight yellow only
- **Minimum Area:** 300 pixels
- **Confidence Threshold:** 0.5

### 2. **Geolocation Calculator** (`geolocation.py`)
- **Method:** Photogrammetry-based coordinate transformation
- **Camera:** Pi HQ Camera (IMX477) + 6mm lens
- **Resolution:** 4056 x 3040 pixels (12.3 MP)
- **FOV:** 66.7° horizontal, 53.1° vertical
- **Processing:** Pixel → Meters → GPS coordinates

### 3. **Integration** (`pi_controller.py`)
- Combines detection with drone telemetry (GPS, heading, altitude, pitch, roll)
- Real-time coordinate transformation
- Stores detection with precise GPS location

---

## Current Mission Parameters (Optimized)

| Parameter | Value | Impact |
|-----------|-------|--------|
| **Altitude** | 10m | Optimal for detection |
| **Speed** | 3.0 m/s | Fast scanning |
| **Overlap** | 20% | Minimal time |
| **Margin** | 5m from boundary | Safety buffer |

---

## Detection Accuracy at 10m Altitude

### Ground Sample Distance (GSD)
```
GSD = (sensor_width_mm × altitude_m × 1000) / (focal_length_mm × image_width_px)
GSD = (7.9 × 10 × 1000) / (6.0 × 4056)
GSD = 3.24 mm/pixel
```

### Yellow Plant Coverage
- **Plant diameter:** 0.5 ft = 0.1524m = 152.4mm
- **Pixels across plant:** 152.4mm / 3.24mm = **47 pixels**
- **Plant area:** ~1,735 pixels (π × 23.5²)

### GPS Accuracy
Your geolocation system uses **centroid-based positioning**:
- **Centroid precision:** ±3 pixels (standard for center-of-mass calculation)
- **GPS accuracy:** 3.24mm × 3 = **±9.7mm (~1cm accuracy)**

### Detection Quality: **ADEQUATE** ⚠️
- 47 pixels across is **marginal but workable** for yellow vs green discrimination
- HSV color detection should still work at this resolution
- Sub-centimeter photogrammetry precision is excellent, but limited by GPS accuracy
- **Note:** Consider reducing altitude to 8m if detection rate is low (would give 58 pixels)

---

## Detection Pipeline Accuracy Factors

### ✅ Strengths
1. **Photogrammetry Correction:**
   - Accounts for drone heading, pitch, and roll
   - Compensates for camera mount angle (-90° bottom-facing)
   - Proper rotation from camera frame to geographic frame

2. **High-Resolution Camera:**
   - 12.3 MP provides excellent detail
   - Pi HQ Camera with 6mm lens = wide coverage

3. **Color-Based Detection:**
   - HSV range (20-30) is **strict yellow only**
   - High saturation threshold (90+) avoids false positives
   - Morphological operations merge yellow regions

4. **Confidence Scoring:**
   - Multi-factor: circularity, fill ratio, size, density
   - Filters out low-quality detections

### ⚠️ Potential Accuracy Limitations

1. **GPS Error Sources:**
   - Drone GPS accuracy: ±1-3m (pixhawk GPS module)
   - Altitude measurement error: ±0.5m
   - Combined with photogrammetry: ±10-30cm total error

2. **Camera Distortion:**
   - 6mm wide-angle lens may have barrel distortion
   - Not corrected in current pipeline
   - Impact: ~5-15mm at image edges

3. **Motion Blur:**
   - At 3.0 m/s speed, potential blur if exposure too long
   - Recommendation: Keep shutter speed >1/500s

4. **Cricket Stadium Grass:**
   - Green grass vs green plants = good contrast
   - Yellow paper vs stadium grass = **excellent contrast** ✓

---

## Expected Accuracy for 2-Acre Cricket Stadium

### Best Case Scenario (ideal conditions)
- **Detection accuracy:** 100% (yellow plants easily visible)
- **GPS accuracy:** ±10-15cm (photogrammetry + good GPS)
- **False positive rate:** <5% (tight HSV thresholds)

### Realistic Field Performance
- **Detection accuracy:** 95-98% (some occlusion/lighting variation)
- **GPS accuracy:** ±20-30cm (typical GPS drift)
- **False positive rate:** 5-10% (grass shadows, reflections)

### Flight Time
- **2 acres:** ~8 passes × 80m = 640m distance
- **Time:** 640m / 3.0 m/s = 213s = **3.6 minutes**
- **With turns:** ~4.1 minutes

---

## Recommendations for Maximum Accuracy

### 1. **Camera Settings** (if adjustable)
```python
- Shutter speed: 1/500s or faster (minimize motion blur)
- ISO: Auto (or 100-400 for low noise)
- White balance: Daylight preset
- Image format: JPEG quality 85-95%
```

### 2. **Flight Optimization**
- Fly during **mid-morning or mid-afternoon** (avoid harsh shadows)
- Wind < 5 m/s for stable imagery
- Keep drone level (pitch/roll < 10°)

### 3. **Detection Tuning**
Current settings in `yellow_crop_detector.py` are already good:
```python
lower_yellow = [20, 90, 60]   # ✓ Tight range
upper_yellow = [30, 255, 255] # ✓ Excludes non-yellows
min_area = 300 pixels         # ⚠️ May need to reduce to 200px for 0.5ft plants
confidence_threshold = 0.5     # ✓ Balanced
```

### 4. **GPS Improvement** (optional)
- Use **RTK GPS** for ±2cm accuracy (expensive upgrade)
- Post-processing with **GCPs** (Ground Control Points) in stadium

---

## Validation Test Procedure

1. **Place Known Test Plants:**
   - Mark 5-10 yellow plants with surveyed GPS coordinates
   - Use handheld GPS or smartphone with GPS app

2. **Run Detection Mission:**
   - Execute lawn mower pattern
   - Record all detections with GPS coordinates

3. **Calculate Error:**
   - Compare detected GPS vs true GPS
   - Calculate mean error, std deviation, max error

4. **Expected Results:**
   - Mean error: 20-30cm
   - Max error: 50cm
   - Detection rate: 95%+

---

## Summary

Your system is **well-designed** for the task:

⚠️ **47 pixels** per plant = marginal (consider 8m altitude for 58px)  
✓ **±1cm** photogrammetry precision (limited by GPS accuracy)  
✓ **Strict HSV filtering** = low false positives  
✓ **Fast coverage** = 4 minutes for 2 acres  
✓ **5m safety margin** = avoids boundary issues  

**Overall Accuracy Estimate:** ±20-30cm GPS error, 85-95% detection rate

**Recommendation:** If detection rate is low during testing, reduce altitude to 8m for better resolution (58 pixels per plant)

This is **excellent** for a competition scenario where relative positioning and complete coverage matter more than sub-centimeter absolute accuracy.
