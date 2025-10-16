# Hyundai Ioniq 6 CAN Bus Analysis - Findings

## Summary
Analysis of CAN bus 0 and bus 1 messages to identify metrics for MQTT publishing.

## ✅ VERIFIED Metrics (Charging Session: 24% → 31%, 129km → 164km)

### 1. Battery State of Charge (SOC)
- **Message ID**: 0x2fa (762)
- **Bus**: 1
- **Byte**: 15
- **Encoding**: **Divide by 2**
- **Formula**: `byte_value / 2.0 = SOC%`
- **Verification Data**:
  - Charging session: 24% → 31% SOC
  - Captured progression: 24.0% → 24.5% → 25.0% → 25.5% → 26.0% → 26.5% → 28.0% → 28.5% → 29.0% → 30.5%
  - Raw byte values: 48 → 49 → 50 → 51 → 52 → 53 → 56 → 57 → 58 → 61
- **Example**: 48 / 2 = 24.0%, 61 / 2 = 30.5%
- **Status**: ✅ **VERIFIED** (Capture file: can_changes_soc_24_to_31.txt)

### 2. Estimated Driving Range
- **Message ID**: 0x28d (653)
- **Bus**: 1
- **Byte**: 24
- **Encoding**: **Direct km value**
- **Formula**: `byte_value = range_km`
- **Verification Data**:
  - Charging session: 129km → 164km range
  - Captured progression: 136 → 137 → 138 → 139 → 140 → 144 → 160 km
  - Note: Message starts with 0 values, then jumps to ~136km after initialization
- **Example**: 0x88 (136) = 136 km, 0xA0 (160) = 160 km
- **Status**: ✅ **VERIFIED** (Capture file: can_changes_soc_24_to_31.txt)

---

## ❌ DISCARDED - Previous Incorrect Findings

### Message 0x3b5 (949) - Bus 1
- **Status**: ❌ **INCORRECT** - This message does NOT contain battery metrics
- **Reason**: Not present in Hyundai CAN FD DBC file, values did not match dashboard during verification
- **Note**: This was from earlier incorrect analysis before proper charging session capture

#### Option B: Message 0x28d (653) - Bus 1
- **Message ID**: 0x28d (653)
- **Byte**: 24
- **Encoding**: Direct km value
- **Formula**: `byte_value = range_km`
- **Evidence**: Values 177, 179, 180, 181, 184, 186 (progressive)
- **Status**: Alternative candidate

#### Option C: Message 0x255 (597) - Bus 1
- **Message ID**: 0x255 (597)
- **Bytes**: 14-15 (16-bit big-endian)
- **Encoding**: Divide by 2
- **Formula**: `((byte14 << 8) | byte15) / 2 = range_km`
- **Example**: 0x015E (350) / 2 = 175 km
- **Status**: From earlier capture, needs re-verification

#### Option D: Message 0x2b5 (693) - Bus 1
- **Message ID**: 0x2b5 (693)
- **Byte**: 1
- **Encoding**: Direct km value
- **Formula**: `byte_value = range_km`
- **Example**: 0xAD (173) ≈ 174 km (1 km difference acceptable)
- **Status**: From earlier capture, needs re-verification

## Pending Metrics

### 3. Odometer
- **Target**: 32,939 km (0x80AB)
- **Status**: ❌ NOT FOUND YET
- **Search strategy**: Look for messages with:
  - Very stable bytes (rarely changing)
  - 16-bit or 24-bit encoding
  - Value near 32939 or 32939/10 = 3294 (if scaled)
  - Likely in message range 0x200-0x400 (vehicle info domain)

### 4. Outside Temperature
- **Status**: ❌ NOT FOUND YET
- **User note**: Temperature value not provided yet

### 5. Charging Status
- **Status**: ❌ NOT FOUND YET
- **Expected**: Boolean or enumeration field

## Analysis Tools Created

1. **can_printer.py** (enhanced)
   - Added `--log` parameter to save messages to CSV format
   - Usage: `python3 /data/openpilot/selfdrive/debug/can_printer.py --bus 1 --log /data/can_capture.csv`

2. **analyze_can_log.py**
   - Parses CSV log files
   - Identifies changing vs constant bytes
   - Searches for dashboard values in multiple encodings

3. **analyze_soc_range_change.py**
   - Parses can_changes.txt format
   - Searches for SOC change patterns (34% → 35%)
   - Searches for range change patterns (~175km → 183km)

4. **find_progressive_values.py** ⭐
   - Identifies bytes that progress through target value ranges
   - Tracks timeline of changes
   - Found the key candidates for range metric

## Data Sources

1. **Bus 0 capture**: Earlier session, found SOC in 0x100
2. **Bus 1 capture (can_capture.csv)**: 125,481 lines, 139 unique messages
3. **Bus 1 changes (can_changes.txt)**: Captured during SOC change 34% → 35%, range ~175km → 183km

## Encoding Patterns Found in Hyundai CAN

Based on analysis of DBC files and data:
- **Direct value**: byte = value
- **Divide by 2**: Common for range/distance
- **Divide by 3**: Used for SOC percentage
- **16-bit big-endian**: `(byte_n << 8) | byte_n+1`
- **Scaling with offset**: `value * scale + offset` (from DBC signal definitions)

## Next Steps

1. ✅ Find range metric - **COMPLETED** (0x3b5 byte 16)
2. ⏳ Verify range metric with fresh capture at different range values
3. ⏳ Find odometer - search for stable multi-byte values near 32939
4. ⏳ Get current outside temperature from user
5. ⏳ Find temperature encoding
6. ⏳ Find charging status bits
7. ⏳ Implement verified findings in mqtt.py

## Implementation Notes

- Bus 0 messages require different cereal subscription (`can` vs `can_fd`)
- SOC is only available on bus 0 (message 0x100)
- Range appears on bus 1 in multiple messages (redundancy for safety?)
- Need to verify which bus the openpilot system monitors for each message type
- Consider subscribing to both buses if needed

## Dashboard Values at Capture Time

- **Odometer**: 32,939 km
- **Range**: Started ~175 km, ended at 183 km
- **SOC**: 34% → 35% (but change not visible on bus 1)
- **Outside Temperature**: Not provided yet
