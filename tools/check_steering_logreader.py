#!/usr/bin/env python3
"""
Check which steering method (LFA vs LKA) is currently being used.
Uses LogReader like analyze_longitudinal_relay.py
"""

import sys
from pathlib import Path
from collections import defaultdict

# Add openpilot to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.lib.logreader import LogReader


def check_steering_method(log_path):
    """Check which steering messages are being sent."""

    lr = LogReader(log_path)

    steering_msgs = defaultdict(int)
    all_sendcan_addrs = defaultdict(int)

    msg_count = 0
    for msg in lr:
        msg_count += 1
        if msg_count % 10000 == 0:
            print(f"  Processed {msg_count} messages...")

        which = msg.which()

        if which == 'sendcan':
            for can_msg in msg.sendcan:
                addr = can_msg.address
                bus = can_msg.src

                # Track all sendcan for debugging
                all_sendcan_addrs[(addr, bus)] += 1

                # Track steering-related messages
                # LFA: 0x12A, LKA: 0x50, alternatives: 0x2A0, 0x362, 0x2A4
                if addr in [0x12A, 0x50, 0x2A0, 0x362, 0x2A4]:
                    key = (addr, bus)
                    steering_msgs[key] += 1

    print(f"Done! Processed {msg_count} messages.\n")

    print("="*60)
    print("STEERING METHOD ANALYSIS")
    print("="*60)

    print(f"\nTotal sendcan messages: {sum(all_sendcan_addrs.values())}")
    print(f"Unique (address, bus) pairs: {len(all_sendcan_addrs)}")

    if all_sendcan_addrs:
        print("\nTop 20 sendcan addresses:")
        for (addr, bus), count in sorted(all_sendcan_addrs.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"  0x{addr:X} bus {bus}: {count:,}")

    if not steering_msgs:
        print("\n❌ No steering messages found in sendcan!")
        print("   (Checked for: 0x12A, 0x50, 0x2A0, 0x362, 0x2A4)")
        return

    print("\n" + "="*60)
    print("STEERING MESSAGES FOUND")
    print("="*60)

    for (addr, bus), count in sorted(steering_msgs.items()):
        msg_name = "UNKNOWN"
        msg_type = ""

        if addr == 0x12A:
            msg_name = "LFA"
            msg_type = "LFA steering on ECAN (without CANFD_LKA_STEERING flag)"
        elif addr == 0x50:
            msg_name = "LKAS"
            msg_type = "LKAS on ACAN (with CANFD_LKA_STEERING flag)"
        elif addr == 0x2A4:
            msg_name = "CAM_0x2A4"
            msg_type = "Camera message (LKA steering architecture)"
        elif addr == 0x2A0:
            msg_name = "LKAS (alt)"
            msg_type = "Alternative LKAS message"
        elif addr == 0x362:
            msg_name = "LKAS_ALT"
            msg_type = "Alternative LKAS architecture"

        bus_name = "ACAN (PT/0)" if bus == 0 else f"ECAN (1)" if bus == 1 else f"bus {bus}"

        print(f"\n  0x{addr:X} ({msg_name})")
        print(f"    Bus: {bus_name}")
        print(f"    Count: {count:,}")
        print(f"    Type: {msg_type}")

    # Determine steering architecture
    print("\n" + "="*60)
    print("ARCHITECTURE DETERMINATION")
    print("="*60)

    has_lfa_ecan = (0x12A, 1) in steering_msgs  # LFA message on ECAN
    has_lkas_acan = (0x50, 0) in steering_msgs or (0x2A0, 0) in steering_msgs or (0x362, 0) in steering_msgs  # LKAS on ACAN

    if has_lfa_ecan and not has_lkas_acan:
        print("\n✅ Currently using: **LFA STEERING**")
        print("   - Single message: 0x12A (LFA) on ECAN (bus 1)")
        print("   - Camera controls steering directly")
        print("   - CANFD_LKA_STEERING flag: NOT SET")
        print("\n   This is the default for Ioniq 6 without the flag.")
        print("\n   ⚠️  To enable longitudinal, you need to ADD the flag")
        print("       because your car uses ADAS ECU at 0x730, not radar at 0x7d0")

    elif has_lkas_acan and not has_lfa_ecan:
        print("\n✅ Currently using: **LKA STEERING**")
        print("   - Primary message: 0x50 (LKAS) on ACAN (bus 0)")
        print("   - Camera → LKAS → ADAS ECU → Steering")
        print("   - CANFD_LKA_STEERING flag: SET")
        print("\n   This architecture routes through the ADAS Driving ECU.")
        print("   Longitudinal control should target 0x730 (already correct).")

    elif has_lkas_acan and has_lfa_ecan:
        print("\n⚠️  Currently using: **MIXED ARCHITECTURE**")
        print("   - Both LKAS on ACAN and LFA on ECAN")
        print("   - This is the dual-message LKA architecture")
        print("   - CANFD_LKA_STEERING flag: SET")

    else:
        print("\n❓ Unknown steering architecture")
        print("   Check the messages above to determine the setup")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 check_steering_logreader.py <path_to_rlog.zst>")
        sys.exit(1)

    log_path = sys.argv[1]
    check_steering_method(log_path)
