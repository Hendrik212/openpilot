#!/usr/bin/env python3
"""
Analyze CAN errors and relay issues in a log.
"""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.append(str(Path(__file__).parent.parent))

from tools.lib.logreader import LogReader


def analyze_can_error(log_path):
    """Analyze CAN errors and events."""

    lr = LogReader(log_path)

    events = []
    uds_msgs = []
    can_errors = []
    adas_ecu_msgs = []
    radar_ecu_msgs = []

    print(f"Analyzing {log_path}...")

    for msg in lr:
        t = msg.logMonoTime * 1e-9
        which = msg.which()

        # Check for carEvents
        if which == 'carEvents':
            for event in msg.carEvents:
                events.append({
                    'time': t,
                    'event': str(event.name)
                })

        # Check pandaStates for faults and CAN errors
        if which == 'pandaStates':
            for ps in msg.pandaStates:
                if ps.faultStatus != 'none':
                    events.append({
                        'time': t,
                        'type': 'pandaFault',
                        'fault': str(ps.faultStatus)
                    })
                if ps.safetyRxChecksInvalid > 0:
                    can_errors.append({
                        'time': t,
                        'count': ps.safetyRxChecksInvalid
                    })

        # Check for UDS and ECU messages
        if which == 'can':
            for c in msg.can:
                # UDS addresses
                if c.address in [0x730, 0x7d0, 0x7d1, 0x731]:
                    uds_msgs.append({
                        'time': t,
                        'addr': hex(c.address),
                        'bus': c.src,
                        'data': c.dat.hex()
                    })

                # ADAS ECU messages (SCC control messages)
                if c.address == 0x730 and c.src == 1:  # ECAN
                    adas_ecu_msgs.append({'time': t, 'addr': '0x730'})

                # Radar ECU
                if c.address == 0x7d0 and c.src == 1:  # ECAN
                    radar_ecu_msgs.append({'time': t, 'addr': '0x7d0'})

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    # Event counts
    event_counts = defaultdict(int)
    for e in events:
        event_name = e.get('event', e.get('type', 'unknown'))
        event_counts[event_name] += 1

    if event_counts:
        print("\n=== Events ===")
        for event, count in sorted(event_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {event}: {count}")
    else:
        print("\n✓ No events recorded")

    print(f"\nCAN safety RX check errors: {len(can_errors)}")
    print(f"UDS-related messages: {len(uds_msgs)}")
    print(f"ADAS ECU (0x730) messages: {len(adas_ecu_msgs)}")
    print(f"Radar ECU (0x7d0) messages: {len(radar_ecu_msgs)}")

    # Detailed CAN errors
    if can_errors:
        print("\n" + "="*60)
        print("CAN SAFETY RX CHECK ERRORS")
        print("="*60)
        print(f"\nFirst 10 occurrences:")
        for err in can_errors[:10]:
            print(f"  Time {err['time']:.2f}s: {err['count']} invalid RX checks")

    # UDS message analysis
    if uds_msgs:
        print("\n" + "="*60)
        print("UDS MESSAGES")
        print("="*60)

        # Group by address
        by_addr = defaultdict(list)
        for m in uds_msgs:
            by_addr[m['addr']].append(m)

        for addr in sorted(by_addr.keys()):
            msgs = by_addr[addr]
            print(f"\n{addr}: {len(msgs)} messages")
            print(f"  First occurrence: {msgs[0]['time']:.2f}s on bus {msgs[0]['bus']}")
            print(f"  Sample data: {msgs[0]['data'][:32]}...")

            # Check for diagnostic responses
            if msgs[0]['data'].startswith('10'):
                print(f"  → Extended Diagnostic Session response")
            elif msgs[0]['data'].startswith('28'):
                print(f"  → Communication Control response")
            elif msgs[0]['data'].startswith('3e'):
                print(f"  → Tester Present")

    # ADAS ECU activity check
    if adas_ecu_msgs:
        print("\n" + "="*60)
        print("ADAS ECU (0x730) ACTIVITY")
        print("="*60)
        print(f"\n⚠️  Found {len(adas_ecu_msgs)} messages from ADAS ECU")
        print(f"First occurrence: {adas_ecu_msgs[0]['time']:.2f}s")
        print(f"Last occurrence: {adas_ecu_msgs[-1]['time']:.2f}s")
        print("\nThis indicates the ADAS ECU is still active!")
        print("It should be disabled for longitudinal control.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_can_error.py <path_to_rlog.zst>")
        sys.exit(1)

    analyze_can_error(sys.argv[1])
