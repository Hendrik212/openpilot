# MQTT Implementation Summary - Hyundai Ioniq 6

## ✅ Implementation Complete - VERIFIED METRICS

Successfully implemented MQTT publishing for two **verified** metrics confirmed through real charging session capture (24% → 31%, 129km → 164km).

## Changes Made

### 1. mqtt.py (opendbc_repo/opendbc/car/hyundai/mqtt.py)

**Status**: ✅ **Updated with VERIFIED metrics**

**Final Implementation:**
- **SOC**: Message 0x2fa (762), Bus 1, Byte 15 - Divide by 2
  - Verified progression: 24.0% → 24.5% → 25.0% → ... → 30.5%
- **Range**: Message 0x28d (653), Bus 1, Byte 24 - Direct km value
  - Verified progression: 136km → 137km → 138km → ... → 160km

**Final Output Variables:**
```python
soc_out = -1.0      # Battery SOC percentage (divide by 2)
range_out = -1      # Range in kilometers (direct value)
```

**Removed from Earlier Versions:**
- ❌ Message 0x3b5 (incorrect - not in DBC, didn't match dashboard)
- ❌ Message 0x100 (not needed - was placeholder from earlier tests)
- All VW hybrid placeholder code
- Unused helper functions

### 2. status.py (system/mqttd/status.py)

**Removed:**
- All VW hybrid tracking variables (battery_charging_prev, range_total_prev, range_electric_prev, range_consumption_petrol_prev, kilometerstand_prev, aussen_temp_prev, charging_time_remaining_prev)
- noDataReceivedCounter and wakeCanBus() logic
- dataReceivedCounter and reboot logic
- Commented-out debug logging code

**Simplified:**
- Changed range from dictionary to single value
- Reduced MQTT payload to just 2 fields

**Final Tracking Variables:**
```python
soc_prev = None
range_prev = None
```

## MQTT Output

**Topic:** `/openpilot/car_status`

**Published Every 30 Seconds:**
```json
{
  "battery_level": 34.7,    // SOC percentage (or null if unchanged)
  "range": 183              // Range in km (or null if unchanged)
}
```

**Only publishes when values change** (null otherwise to reduce MQTT traffic)

## ✅ Verified Metrics (Charging Capture: 24% → 31%, 129km → 164km)

| Metric | Message ID | Bus | Byte | Encoding | Verified Examples |
|--------|-----------|-----|------|----------|-------------------|
| **SOC** | 0x2fa (762) | 1 | 15 | **Divide by 2** | 48/2 = 24.0%, 61/2 = 30.5% |
| **Range** | 0x28d (653) | 1 | 24 | **Direct km** | 136 km, 140 km, 160 km |

**Verification Method:**
- Captured live CAN data during charging session
- SOC increased from 24% to 31% (7% increase)
- Range increased from 129km to 164km (35km increase)
- Both metrics show progressive, consistent increases matching dashboard values

## Testing Instructions

1. **Start the MQTT daemon:**
   ```bash
   cd /data/openpilot
   python system/mqttd/status.py
   ```

2. **Monitor MQTT messages:**
   ```bash
   mosquitto_sub -h 192.168.1.202 -t "/openpilot/car_status" -v
   ```

3. **Expected output every 30 seconds:**
   - First publish: Both values should appear
   - Subsequent: Only changed values (or null if unchanged)

4. **Verify values match dashboard:**
   - SOC should match battery percentage on dashboard
   - Range should match estimated range on dashboard

## Home Assistant Integration

Add to `configuration.yaml`:

```yaml
mqtt:
  sensor:
    - name: "Ioniq 6 Battery Level"
      state_topic: "/openpilot/car_status"
      value_template: "{{ value_json.battery_level }}"
      unit_of_measurement: "%"
      device_class: battery

    - name: "Ioniq 6 Range"
      state_topic: "/openpilot/car_status"
      value_template: "{{ value_json.range }}"
      unit_of_measurement: "km"
      icon: mdi:map-marker-distance
```

## Future Enhancements

Still to be discovered and added:
- Odometer (target: 32,939 km)
- Outside temperature
- Charging status (plugged in, charging, complete)
- Charging time remaining
- Battery voltage/current

## File Changes Summary

**Modified Files:**
1. `D:\dev\openpilot_hyundai\opendbc_repo\opendbc\car\hyundai\mqtt.py`
   - Before: 278 lines (mostly placeholders)
   - After: 63 lines (clean, verified code only)

2. `D:\dev\openpilot_hyundai\system\mqttd\status.py`
   - Before: 155 lines (VW hybrid complexity)
   - After: 107 lines (simplified to 2 metrics)

**Total Lines Removed:** ~263 lines of unused/placeholder code
**Total Lines Added:** ~5 lines of verified range parsing

## Notes

- Both SOC and range update in real-time as the values change in the vehicle
- The system passively listens to CAN buses 0 and 1
- No polling or active CAN commands are sent
- Values initialize to -1 and update when messages are received
- MQTT only publishes changes to reduce network traffic
