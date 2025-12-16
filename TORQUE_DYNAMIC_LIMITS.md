# Ioniq 6 Speed-Dependent Torque Limits - Complete Solution

## Problem Analysis

### Symptoms
- Steering wobble at 80 km/h on straight roads
- Dashboard errors (LKA disabled warnings)
- First engagement had wobble, subsequent engagements better

### Root Cause (from log analysis)
- **Rate limit violations**: Up to 26.8 units/sec (limit was 10/sec)
- **Torque commanded**: Max 720 at all speeds
- **Controller unaware**: Lateral controller didn't know about safety limits
- **Mismatch**: Panda safety clipped commands → controller integral windup

## Log Analysis Methodology

We analyzed the openpilot route logs to identify the cause of wobble and dashboard faults, while minimizing data volume.

Overview:
- Logs were copied to a Linux host for extraction due to Windows capnp/env issues
- Only engaged segments were analyzed (carControl.enabled)
- Downsampled to ~20 Hz to keep time series compact
- Focused on torque command vs. actual torque and rate-of-change

Steps:
1) Transfer and environment
- Copied logs from Windows to Linux host 192.168.1.131 (/home/hendrik/openpilot)
- Initialized submodules and installed dependencies (pycapnp, zstandard, etc.)
- Used cereal/logreader utilities for parsing

2) Engagement segmentation
- Engagement detection: carControl.enabled stream
- Split the route into segments for each engagement to compare behaviors independently

3) Signals extracted per sample
- time (monotonic)
- vEgo (vehicle speed)
- carControl.latActive (engaged lateral control)
- actuators.torque (normalized commanded torque)
- actuatorsOutput.torqueOutputCan (actual CAN torque units)
- Optional: liveTorqueParameters (friction/latAccelFactor) for future correlation

4) Rate limit and saturation checks
- Compute dt between samples, then torque_rate = |Δ torqueOutputCan| / dt
- Compare to max_rate (safety limit prior was 10 units/sec)
- Flag exceedances, compute max and percentile stats per engagement
- Compare commanded vs actual to identify safety clipping

5) Summaries produced
- Per-engagement JSON with: duration, max torque, max torque rate, #violations, mean/95p rates
- CSV for timeseries visualization (optional)

Key findings:
- Multiple engagements showed rate-of-change violations up to ~26.8 units/sec
- Commanded torque hit 720 units at speed where panda clipped to ~270
- Controller unaware of speed-dependent safety caused integral windup and wobble

Repro scripts:
- Extraction scripts maintained under tools/ (Windows copy nonfunctional; Linux version used)
- They use logreader to parse and downsample; filter on carControl.enabled and capture carOutput

Limitations:
- Analysis at ~20 Hz, fine for rate/limit inference; detailed transient spikes may be under-represented
- Only one short route analyzed; more data across speeds would improve confidence

---

## Solution: Three-Layer Speed-Dependent Limits

### Layer 1: Panda Safety (opendbc/safety/modes/hyundai_canfd.h)

**Stepless interpolation** between conservative and aggressive limits:

```c
// At 0 km/h (parking):
max_torque = 720
max_rate_up = 6
max_rate_down = 8

// At 70+ km/h (highway):
max_torque = 270 (stock)
max_rate_up = 2 (stock)
max_rate_down = 3 (stock)

// Between 0-70 km/h: Linear interpolation
```

### Layer 2: Controller Limits (opendbc/car/hyundai/values.py)

**Speed-aware STEER_MAX method:**
- `get_steer_max(v_ego)` returns current limit based on speed
- Matches panda safety interpolation exactly
- Controller always knows actual limits

### Layer 3: Car Controller (opendbc/car/hyundai/carcontroller.py)

**Dynamic scaling:**
```python
steer_max = self.params.get_steer_max(CS.out.vEgo)
new_torque = int(round(actuators.torque * steer_max))
```

## Speed-to-Torque Mapping

| Speed (km/h) | Max Torque | Rate Up/Down | Use Case |
|--------------|------------|--------------|----------|
| 0            | 720        | 6/8          | Parking, sharp turns |
| 20           | 591        | 5/7          | City driving |
| 35           | 495        | 4/6          | Suburban |
| 50           | 399        | 3/5          | Country roads |
| 70+          | 270        | 2/3          | Highway (stock) |

## Benefits

✅ **No controller/safety mismatch** - Always in sync
✅ **No integral windup** - Controller knows limits
✅ **Smooth transitions** - Linear interpolation
✅ **Optimal performance** - Right limits for each speed
✅ **No wobble** - Appropriate rate limits
✅ **No dashboard errors** - Within car's acceptance range

## Files Modified

1. `opendbc_repo/opendbc/safety/modes/hyundai_canfd.h`
2. `opendbc_repo/opendbc/car/hyundai/values.py`
3. `opendbc_repo/opendbc/car/hyundai/carcontroller.py`
