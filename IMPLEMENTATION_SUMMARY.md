# MQTT Implementation Summary - Hyundai Ioniq 6

## Implementation Complete ✓

Successfully cleaned up and implemented MQTT publishing for two verified metrics.

## Changes Made

### 1. mqtt.py (opendbc_repo/opendbc/car/hyundai/mqtt.py)

**Removed:**
- All VW hybrid placeholder code (charging_status, kilometerstand, aussen_temp, charging_time_remaining)
- Complex range dictionary → simplified to single integer
- Unused helper functions (parse_bmc_data, parse_cluster_data, parse_vmcu_data, parse_environmental_data)
- Unused bit/byte manipulation helpers
- wakeCanBus() function (not needed for passive listening)
- Long TODO comments and implementation notes

**Added:**
- **Range parsing** for message 0x3b5, bus 1, byte 16 (direct km value)

**Kept:**
- SOC parsing for message 0x100, bus 0, byte 20 (divide by 3)
- Simple, clean code with only verified metrics

**Final Output Variables:**
```python
soc_out = -1.0      # Battery SOC percentage
range_out = -1      # Range in kilometers
```

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

## Verified Metrics

| Metric | Message ID | Bus | Byte | Encoding | Example |
|--------|-----------|-----|------|----------|---------|
| **SOC** | 0x100 (256) | 0 | 20 | Divide by 3 | 0x68 (104) / 3 = 34.7% |
| **Range** | 0x3b5 (949) | 1 | 16 | Direct km | 0xB7 (183) = 183 km |

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
