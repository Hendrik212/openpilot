#!/usr/bin/env python3
import argparse
import binascii
import os
import re
import time
from collections import defaultdict

import cereal.messaging as messaging
from openpilot.selfdrive.debug.can_table import can_table
from openpilot.tools.lib.logreader import LogIterable, LogReader

RED = '\033[91m'
CLEAR = '\033[0m'

# Global DBC data and cache
dbc_data = None
message_name_cache = {}

def load_dbc(dbc_path):
  """Load DBC file content."""
  global dbc_data
  try:
    with open(dbc_path, 'r', errors='ignore') as f:
      dbc_data = f.read()
    print(f"Loaded DBC file: {dbc_path}")
  except Exception as e:
    print(f"Warning: Could not load DBC file {dbc_path}: {e}")
    dbc_data = None

def get_message_name(address):
  """Get message name from DBC file for given address."""
  if dbc_data is None:
    return "UNKNOWN"

  # Check cache first
  if address in message_name_cache:
    return message_name_cache[address]

  # Parse DBC for this address
  # Looking for pattern: BO_ <address> <MESSAGE_NAME>:
  try:
    pattern = re.compile(r'BO_ ' + str(address) + r' ([^:]+):', re.MULTILINE)
    match = pattern.search(dbc_data)
    if match:
      name = match.group(1).strip()
      message_name_cache[address] = name
      return name
  except Exception:
    pass

  message_name_cache[address] = "UNKNOWN"
  return "UNKNOWN"

def update(msgs, bus_filter, dat, low_to_high, high_to_low, quiet=False):
  """
  Update function now tracks ALL buses regardless of bus_filter.
  bus_filter is only used for display filtering.
  """
  for x in msgs:
    if x.which() != 'can':
      continue

    for y in x.can:
      bus = y.src

      # Store data per bus
      dat[bus][y.address] = y.dat

      i = int.from_bytes(y.dat, byteorder='big')
      l_h = low_to_high[bus][y.address]
      h_l = high_to_low[bus][y.address]

      change = None
      if (i | l_h) != l_h:
        low_to_high[bus][y.address] = i | l_h
        change = "+"

      if (~i | h_l) != h_l:
        high_to_low[bus][y.address] = ~i | h_l
        change = "-"

      # Print if there's a change and we should display this bus
      if change and not quiet and (bus_filter is None or bus == bus_filter):
        msg_name = get_message_name(y.address)
        print(f"{time.monotonic():.2f}\tBus {bus}\t{hex(y.address)} ({y.address})\t[{msg_name}]\t{change}{binascii.hexlify(y.dat)}")


def can_printer(bus=None, init_msgs=None, new_msgs=None, table=False):
  logcan = messaging.sub_sock('can', timeout=10)

  # Multi-bus data structures: dict[bus][address] -> value
  dat = defaultdict(lambda: defaultdict(int))
  low_to_high = defaultdict(lambda: defaultdict(int))
  high_to_low = defaultdict(lambda: defaultdict(int))

  if init_msgs is not None:
    update(init_msgs, bus, dat, low_to_high, high_to_low, quiet=True)

  # Deep copy for nested defaultdicts
  low_to_high_init = defaultdict(lambda: defaultdict(int))
  high_to_low_init = defaultdict(lambda: defaultdict(int))
  for b in low_to_high:
    low_to_high_init[b] = low_to_high[b].copy()
    high_to_low_init[b] = high_to_low[b].copy()

  if new_msgs is not None:
    update(new_msgs, bus, dat, low_to_high, high_to_low)
  else:
    # Live mode
    if bus is None:
      print("Waiting for messages on ALL buses")
    else:
      print(f"Waiting for messages on bus {bus}")
    try:
      while 1:
        can_recv = messaging.drain_sock(logcan)
        update(can_recv, bus, dat, low_to_high, high_to_low)
        time.sleep(0.02)
    except KeyboardInterrupt:
      pass

  # Summary output - iterate through all buses
  print("\n\n")
  tables = ""
  for bus_num in sorted(dat.keys()):
    for addr in sorted(dat[bus_num].keys()):
      init = low_to_high_init[bus_num][addr] & high_to_low_init[bus_num][addr]
      now = low_to_high[bus_num][addr] & high_to_low[bus_num][addr]
      d = now & ~init
      if d == 0:
        continue
      b = d.to_bytes(len(dat[bus_num][addr]), byteorder='big')

      byts = ''.join([(c if c == '0' else f'{RED}{c}{CLEAR}') for c in str(binascii.hexlify(b))[2:-1]])
      msg_name = get_message_name(addr)
      header = f"Bus {bus_num} {hex(addr).ljust(6)}({str(addr).ljust(4)}) [{msg_name}]"
      print(header, byts)
      tables += f"{header}\n"
      tables += can_table(b) + "\n\n"

  if table:
    print(tables)

if __name__ == "__main__":
  desc = """Collects messages and prints when a new bit transition is observed.
  This is very useful to find signals based on user triggered actions, such as blinkers and seatbelt.
  Leave the script running until no new transitions are seen, then perform the action.

  Now supports multi-bus tracking and DBC message name resolution."""
  parser = argparse.ArgumentParser(description=desc,
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)

  # Calculate default DBC path relative to openpilot root
  # Script is at: /data/openpilot/selfdrive/debug/can_print_changes.py
  # DBC is at:    /data/openpilot/opendbc_repo/opendbc/dbc/generator/hyundai/hyundai_canfd.dbc
  script_dir = os.path.dirname(os.path.abspath(__file__))
  openpilot_root = os.path.join(script_dir, '..', '..')
  default_dbc = os.path.join(openpilot_root, 'opendbc_repo', 'opendbc', 'dbc', 'generator', 'hyundai', 'hyundai_canfd.dbc')

  parser.add_argument("--bus", type=int, help="CAN bus to filter display (omit to show all buses)", default=None)
  parser.add_argument("--dbc", type=str, help="Path to DBC file for message name resolution",
                      default=default_dbc)
  parser.add_argument("--table", action="store_true", help="Print a cabana-like table")
  parser.add_argument("init", type=str, nargs='?', help="Route or segment to initialize with. Use empty quotes to compare against all zeros.")
  parser.add_argument("comp", type=str, nargs='?', help="Route or segment to compare against init")

  args = parser.parse_args()

  # Load DBC file
  load_dbc(args.dbc)

  init_lr: LogIterable | None = None
  new_lr: LogIterable | None = None

  if args.init:
    if args.init == '':
      init_lr = []
    else:
      init_lr = LogReader(args.init)
  if args.comp:
    new_lr = LogReader(args.comp)

  can_printer(args.bus, init_msgs=init_lr, new_msgs=new_lr, table=args.table)
