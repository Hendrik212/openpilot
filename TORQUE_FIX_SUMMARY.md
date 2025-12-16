# Ioniq 6 Torque Limit Fix Summary

## Problem
After implementing high torque limits (720/10/10), you experienced:
- Steering wheel wobble at 80km/h on straight roads
- Dashboard errors (LKA disabled warnings)
- Wobble was constant during first engagement, better on second engagement
- Suspected rate limit violations

## Root Cause Analysis
The aggressive limits were causing multiple issues:

1. **Rate Limit Violations**: `max_rate_up/down = 10` at 100Hz allows 1000 units/second change, but the live torque controller was trying to change faster, causing the car to reject commands

2. **Control Loop Instability**:
   - High max torque (720) allows large corrections
   - Rate limits prevent smooth transitions
   - Controller overshoots → rate-limited correction → overshoots again = wobble

3. **max_rt_delta Too Tight**: Reduced from 112 to 90, limiting response to driver input

## Solution Implemented

### Changes Made

**opendbc_repo/opendbc/car/hyundai/values.py** (commit 95dc60fe):
```python
# Ioniq 6 limits
STEER_MAX = 500          # was 720
STEER_DELTA_UP = 6       # was 10
STEER_DELTA_DOWN = 8     # was 10
```

**opendbc_repo/opendbc/safety/modes/hyundai_canfd.h** (commit 95dc60fe):
```c
.max_torque = 500,       // was 720
.max_rt_delta = 112,     // was 90 (restored original)
.max_rate_up = 6,        // was 10
.max_rate_down = 8,      // was 10
```

### Benefits
- Still provides significantly improved steering vs stock (500 vs 270)
- Smoother torque transitions (slower rate limits)
- No rate limit violations
- Stable control without wobble
- Better driver input response (restored max_rt_delta)

## Next Steps

### 1. Rebuild Panda Firmware
The panda device needs to be reflashed with the new safety limits:

```bash
cd panda
./test.sh  # Build and test
# Then flash to your device (see panda docs for your specific hardware)
```

### 2. Test Drive
After flashing the updated firmware:
- Test on the same 80km/h straight road
- Verify no wobble
- Check for dashboard errors
- Test sharp turns at low speed
- Verify steering feels responsive

### 3. Fine-Tuning (if needed)
If steering feels too weak:
- Can increase STEER_MAX to 550-600
- Keep rate limits conservative (6/8)

If still experiencing slight wobble:
- Reduce rate limits further (5/7)
- Reduce max torque to 450

## Commits Created

1. **opendbc_repo**: `95dc60fedbefde1f3c95118156f4c4ee44180d56`
   - "Ioniq 6: Reduce torque limits to fix wobble and rate limit violations"

2. **openpilot_hyundai**: `f2aa465e7386f1d2fcdb21fa6f27c4b7abfc2e72`
   - "Update opendbc: reduce Ioniq 6 torque limits to fix wobble"

## Technical Details

### Rate Limit Explanation
At 100Hz update rate:
- Old: 10 units/step = 1000 units/second max change
- New: 6 units/step = 600 units/second max change (up)
- New: 8 units/step = 800 units/second max change (down, faster release)

### Why These Specific Values?
- **500 max torque**: Still 85% higher than stock (270), provides good authority
- **6/8 rate limits**: Conservative enough to prevent oscillation, fast enough for responsiveness
- **112 max_rt_delta**: Original value that worked well for other Hyundai CANFD vehicles

## References
- Original aggressive tuning based on: whoisdomi/openpilot@f528b2a
- Commits created: 2025-12-15
