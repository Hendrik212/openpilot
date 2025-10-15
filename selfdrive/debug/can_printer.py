#!/usr/bin/env python3
import argparse
import binascii
import time
from collections import defaultdict

import cereal.messaging as messaging


def can_printer(bus, max_msg, addr, ascii_decode, log_file=None):
  logcan = messaging.sub_sock('can', addr=addr)

  start = time.monotonic()
  lp = time.monotonic()
  msgs = defaultdict(list)

  # Open log file if specified
  log_fp = None
  if log_file:
    log_fp = open(log_file, 'w')
    # Write header with metadata
    log_fp.write(f"# CAN Bus {bus} capture\n")
    log_fp.write(f"# Started at {time.time():.3f}\n")
    log_fp.write(f"# Format: timestamp,address,hex_data\n")
    log_fp.flush()

  while 1:
    can_recv = messaging.drain_sock(logcan, wait_for_one=True)
    for x in can_recv:
      for y in x.can:
        if y.src == bus:
          msgs[y.address].append(y.dat)

          # Log to file if enabled
          if log_fp:
            timestamp = time.monotonic() - start
            hex_data = binascii.hexlify(y.dat).decode('ascii')
            log_fp.write(f"{timestamp:.6f},{y.address:04x},{hex_data}\n")
            log_fp.flush()

    if time.monotonic() - lp > 0.1:
      dd = chr(27) + "[2J"
      dd += f"{time.monotonic() - start:5.2f}\n"
      for _addr in sorted(msgs.keys()):
        a = f"\"{msgs[_addr][-1].decode('ascii', 'backslashreplace')}\"" if ascii_decode else ""
        x = binascii.hexlify(msgs[_addr][-1]).decode('ascii')
        freq = len(msgs[_addr]) / (time.monotonic() - start)
        if max_msg is None or _addr < max_msg:
          dd += f"{_addr:04X}({_addr:4d})({len(msgs[_addr]):6d})({freq:3}dHz) {x.ljust(20)} {a}\n"
      print(dd)
      lp = time.monotonic()

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="simple CAN data viewer",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  parser.add_argument("--bus", type=int, help="CAN bus to print out", default=0)
  parser.add_argument("--max_msg", type=int, help="max addr")
  parser.add_argument("--ascii", action='store_true', help="decode as ascii")
  parser.add_argument("--addr", default="127.0.0.1")
  parser.add_argument("--log", type=str, help="log messages to file (CSV format)")

  args = parser.parse_args()
  can_printer(args.bus, args.max_msg, args.addr, args.ascii, args.log)
