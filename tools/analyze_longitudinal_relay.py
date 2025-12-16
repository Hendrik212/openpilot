#!/usr/bin/env python3
"""
Analyze longitudinal control relay malfunction.
Checks:
1. UDS disable_ecu attempts and responses
2. Messages from 0x730 (ADAS ECU) after disable attempt
3. Relay malfunction events
4. SCC control messages
"""

import sys
import json
from pathlib import Path
from collections import defaultdict

# Add openpilot to path
sys.path.append(str(Path(__file__).parent.parent))

from tools.lib.logreader import LogReader


def analyze_longitudinal_relay(log_path):
    """Analyze relay malfunction during longitudinal toggle."""

    results = {
        'uds_messages': [],
        'adas_ecu_messages_after_disable': [],
        'relay_events': [],
        'scc_messages': [],
        'timeline': []
    }

    lr = LogReader(log_path)

    disable_time = None

    for msg in lr:
        t = msg.logMonoTime * 1e-9
        which = msg.which()

        # Track UDS messages (diagnostic commands)
        if which == 'can':
            for can_msg in msg.can:
                addr = can_msg.address
                dat = can_msg.dat
                bus = can_msg.src

                # UDS diagnostics to 0x730 (ADAS ECU)
                if addr == 0x730:
                    # Extended diagnostic request or communication control
                    if len(dat) >= 2 and (dat[0] == 0x10 or dat[0] == 0x28):
                        uds_entry = {
                            'time': t,
                            'addr': hex(addr),
                            'bus': bus,
                            'service': hex(dat[0]),
                            'data': dat.hex(),
                            'type': 'extended_diag' if dat[0] == 0x10 else 'comm_control'
                        }
                        results['uds_messages'].append(uds_entry)
                        results['timeline'].append(f"{t:.2f}s: UDS to 0x730 - {uds_entry['type']}")

                        # Track when disable was attempted
                        if dat[0] == 0x28 and disable_time is None:
                            disable_time = t
                            results['timeline'].append(f"{t:.2f}s: DISABLE_ECU attempted")

                    # Tester present
                    elif len(dat) >= 2 and dat[0] == 0x02 and dat[1] == 0x3E:
                        results['timeline'].append(f"{t:.2f}s: Tester Present to 0x730")

                    # Any other message from ADAS ECU after disable
                    elif disable_time is not None and t > disable_time + 1.0:
                        results['adas_ecu_messages_after_disable'].append({
                            'time': t,
                            'time_after_disable': t - disable_time,
                            'addr': hex(addr),
                            'bus': bus,
                            'data': dat.hex()
                        })

                # UDS responses from 0x7B0 (likely response to 0x730)
                if addr == 0x7B0:
                    if len(dat) >= 2:
                        response_entry = {
                            'time': t,
                            'addr': hex(addr),
                            'bus': bus,
                            'data': dat.hex(),
                            'type': 'negative' if dat[0] == 0x7F else 'positive'
                        }
                        results['uds_messages'].append(response_entry)
                        results['timeline'].append(f"{t:.2f}s: UDS response from 0x7B0 - {response_entry['type']}")

                # SCC control messages (check if openpilot sent them)
                # Common SCC addresses for Hyundai CANFD
                if addr in [0x1A0, 0x1CF, 0x1E0]:  # SCC control addresses
                    results['scc_messages'].append({
                        'time': t,
                        'addr': hex(addr),
                        'bus': bus,
                        'data': dat.hex()
                    })

        # Relay malfunction events
        if which == 'onroadEvents':
            for event in msg.onroadEvents:
                event_name = str(event.name)
                if 'relay' in event_name.lower() or 'can' in event_name.lower():
                    event_entry = {
                        'time': t,
                        'name': event_name,
                        'noEntry': event.noEntry,
                        'immediateDisable': event.immediateDisable
                    }
                    results['relay_events'].append(event_entry)
                    results['timeline'].append(f"{t:.2f}s: EVENT - {event_name}")

        # Check selfdriveState for errors
        if which == 'selfdriveState':
            state = msg.selfdriveState
            if state.alertText1 or state.alertText2:
                results['timeline'].append(f"{t:.2f}s: ALERT - {state.alertText1} / {state.alertText2}")

    return results


def print_results(results):
    """Pretty print analysis results."""

    print("\n" + "="*80)
    print("LONGITUDINAL RELAY MALFUNCTION ANALYSIS")
    print("="*80)

    print("\n### TIMELINE ###")
    for entry in results['timeline'][:50]:  # First 50 events
        print(entry)
    if len(results['timeline']) > 50:
        print(f"... and {len(results['timeline']) - 50} more events")

    print("\n### UDS MESSAGES (disable_ecu attempts) ###")
    print(f"Total UDS messages: {len(results['uds_messages'])}")
    for msg in results['uds_messages'][:20]:
        print(f"  {msg['time']:.2f}s: {msg.get('type', 'response')} - {msg['data']}")

    print("\n### ADAS ECU (0x730) MESSAGES AFTER DISABLE ###")
    print(f"Total messages from 0x730 after disable: {len(results['adas_ecu_messages_after_disable'])}")
    if results['adas_ecu_messages_after_disable']:
        print("⚠️  ADAS ECU continued sending messages after disable attempt!")
        for msg in results['adas_ecu_messages_after_disable'][:10]:
            print(f"  {msg['time']:.2f}s (+{msg['time_after_disable']:.2f}s): {msg['data']}")
    else:
        print("✓ No messages from 0x730 after disable (or disable never attempted)")

    print("\n### RELAY MALFUNCTION EVENTS ###")
    print(f"Total relay/CAN events: {len(results['relay_events'])}")
    for event in results['relay_events']:
        print(f"  {event['time']:.2f}s: {event['name']} (noEntry={event['noEntry']}, disable={event['immediateDisable']})")

    print("\n### SCC CONTROL MESSAGES ###")
    print(f"Total SCC messages sent: {len(results['scc_messages'])}")
    if results['scc_messages']:
        print("First 5 SCC messages:")
        for msg in results['scc_messages'][:5]:
            print(f"  {msg['time']:.2f}s: {msg['addr']} on bus {msg['bus']}")

    print("\n" + "="*80)

    # Save detailed JSON
    return results


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_longitudinal_relay.py <path_to_rlog.zst>")
        print("\nExample:")
        print("  python3 analyze_longitudinal_relay.py /path/to/568c82e1de7c61a2_00000163--8db996a987--0--rlog.zst")
        sys.exit(1)

    log_path = sys.argv[1]

    print(f"Analyzing: {log_path}")
    results = analyze_longitudinal_relay(log_path)
    print_results(results)

    # Save JSON
    output_path = Path(log_path).parent / "longitudinal_relay_analysis.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")
