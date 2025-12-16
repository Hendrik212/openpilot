#!/usr/bin/env python3
"""
Decode UDS messages from a log.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from tools.lib.logreader import LogReader


def decode_uds(log_path):
    """Decode UDS diagnostic messages."""

    lr = LogReader(log_path)

    uds_730 = []
    uds_7d0 = []
    uds_731 = []
    uds_7d1 = []

    for msg in lr:
        t = msg.logMonoTime * 1e-9

        if msg.which() == 'can':
            for c in msg.can:
                if c.address == 0x730:
                    uds_730.append({'time': t, 'bus': c.src, 'data': c.dat.hex()})
                elif c.address == 0x7d0:
                    uds_7d0.append({'time': t, 'bus': c.src, 'data': c.dat.hex()})
                elif c.address == 0x731:
                    uds_731.append({'time': t, 'bus': c.src, 'data': c.dat.hex()})
                elif c.address == 0x7d1:
                    uds_7d1.append({'time': t, 'bus': c.src, 'data': c.dat.hex()})

    def decode_msg(data):
        """Decode UDS message type."""
        if data.startswith('021003'):
            return 'Extended Diagnostic Request (0x10 0x03)'
        elif data.startswith('03288301'):
            return 'Communication Control Request (0x28 0x83 0x01 - disable TX/RX)'
        elif data.startswith('023e00'):
            return 'Tester Present (0x3E suppress response)'
        elif data.startswith('065001') or data.startswith('025003'):
            return 'Extended Diag Response (positive)'
        elif data.startswith('066801') or data.startswith('026801'):
            return 'Communication Control Response (positive)'
        elif data.startswith('037f'):
            return 'Negative Response (error)'
        else:
            return 'Unknown'

    print("="*60)
    print("UDS MESSAGE DECODE")
    print("="*60)

    print(f"\n=== 0x730 (ADAS ECU Requests) ===")
    print(f"Total: {len(uds_730)}")
    if uds_730:
        print("\nAll messages:")
        for m in uds_730:
            msg_type = decode_msg(m['data'])
            print(f"  {m['time']:.2f}s bus {m['bus']:3d}: {m['data'][:32]:32s} → {msg_type}")

    print(f"\n=== 0x731 (ADAS ECU Responses) ===")
    print(f"Total: {len(uds_731)}")
    if uds_731:
        print("\nAll messages:")
        for m in uds_731:
            msg_type = decode_msg(m['data'])
            print(f"  {m['time']:.2f}s bus {m['bus']:3d}: {m['data'][:32]:32s} → {msg_type}")

    print(f"\n=== 0x7d0 (Radar ECU Requests) ===")
    print(f"Total: {len(uds_7d0)}")
    if uds_7d0:
        print("\nAll messages:")
        for m in uds_7d0:
            msg_type = decode_msg(m['data'])
            print(f"  {m['time']:.2f}s bus {m['bus']:3d}: {m['data'][:32]:32s} → {msg_type}")

    print(f"\n=== 0x7d1 (Radar ECU Responses) ===")
    print(f"Total: {len(uds_7d1)}")
    if uds_7d1:
        print("\nAll messages:")
        for m in uds_7d1:
            msg_type = decode_msg(m['data'])
            print(f"  {m['time']:.2f}s bus {m['bus']:3d}: {m['data'][:32]:32s} → {msg_type}")

    # Analysis
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)

    # Count message types for 0x730
    ext_diag_730 = sum(1 for m in uds_730 if m['data'].startswith('021003'))
    comm_ctrl_730 = sum(1 for m in uds_730 if m['data'].startswith('03288301'))
    tester_730 = sum(1 for m in uds_730 if m['data'].startswith('023e00'))

    print(f"\n0x730 (ADAS ECU):")
    print(f"  Extended Diagnostic requests: {ext_diag_730}")
    print(f"  Communication Control requests: {comm_ctrl_730}")
    print(f"  Tester Present: {tester_730}")

    # Count message types for 0x7d0
    ext_diag_7d0 = sum(1 for m in uds_7d0 if m['data'].startswith('021003'))
    comm_ctrl_7d0 = sum(1 for m in uds_7d0 if m['data'].startswith('03288301'))
    tester_7d0 = sum(1 for m in uds_7d0 if m['data'].startswith('023e00'))

    print(f"\n0x7d0 (Radar ECU):")
    print(f"  Extended Diagnostic requests: {ext_diag_7d0}")
    print(f"  Communication Control requests: {comm_ctrl_7d0}")
    print(f"  Tester Present: {tester_7d0}")

    if comm_ctrl_730 > 0:
        print("\n✓ Communication Control sent to 0x730 (ADAS ECU)")
        print("  This is CORRECT for your car with CANFD_LKA_STEERING")
    else:
        print("\n✗ No Communication Control sent to 0x730 (ADAS ECU)")

    if comm_ctrl_7d0 > 0:
        print("\n⚠️  Communication Control sent to 0x7d0 (Radar ECU)")
        print("  This is WRONG - your car doesn't have a radar at 0x7d0")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 decode_uds_messages.py <path_to_rlog.zst>")
        sys.exit(1)

    decode_uds(sys.argv[1])
