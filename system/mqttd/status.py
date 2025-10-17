#!/usr/bin/env python3
import time
import datetime

import cereal.messaging as messaging
from openpilot.common.realtime import DT_CTRL
from openpilot.common.dict_helpers import strip_deprecated_keys
from collections import defaultdict

from openpilot.system.mqttd import mqttd
from opendbc.car.hyundai import mqtt
from openpilot.system.hardware import HARDWARE


#f = open("mqtt_status_log.txt", "w")

def format_time(minutes):
  """Convert minutes to HH:MM format. Returns None if minutes < 0."""
  if minutes < 0:
    return None
  hours = minutes // 60
  mins = minutes % 60
  return f"{hours:02d}:{mins:02d}"

def publish_ha_discovery(pm, count, config_prefix):
  client_id = mqttd.client_id()
  content = {"name": "car","state_topic": f"home/binary_sensor/car/{client_id}", "device_class": "motion", "unique_id": client_id, "count": count}
  topic = f"{config_prefix}/binary_sensor/car/{client_id}/config"
  mqttd.publish(pm, topic, content)

def status_thread():
  config_prefix = 'openpilot'
  status_prefix = ''

  #time.sleep(30)
  #f.write(str(datetime.datetime.now()) + '--------------------------------------------\n')
  #f.write("mqtt status daemon started\n\n")
  #f.flush()
  pm = messaging.PubMaster(['mqttPubQueue'])
  sm = messaging.SubMaster(['mqttRecvQueue'])
  logcan = messaging.sub_sock('can', timeout=10)
  dat = defaultdict(int)

  panda_state_timeout = int(1000 * 2.5 * DT_CTRL)  # 2.5x the expected pandaState frequency
  panda_state_sock = messaging.sub_sock('pandaState', timeout=panda_state_timeout)
  location_sock = messaging.sub_sock('gpsLocationExternal')
  device_sock = messaging.sub_sock('deviceState')

  publish_ha_discovery(pm, "FIRST", config_prefix)

  count = 0
  total_count = 0
  panda_prev = None
  location_prev = None
  device_prev = None
  soc_prev = None
  range_prev = None
  pack_voltage_prev = None
  charging_current_prev = None
  charging_power_prev = None
  charging_time_remaining_prev = None
  charging_status_prev = None
  sleeptimer = time.monotonic()

  while True:
    cur_time = time.monotonic()

    # get can messages
    can_recv = messaging.drain_sock(logcan)
    bus = 1
    mqtt.getParsedMessages(can_recv, bus, dat)

    if cur_time > sleeptimer + 30: # update mqtt all 30s
      #f.write(str(datetime.datetime.now()) + " entering loop...\n")
      #f.flush()
      sleeptimer = cur_time

      # mqtt message receiver
      mqttd.subscribe(pm, "openpilot/command")
      sm.update(1)
      if count == 10:
        count = 0
        publish_ha_discovery(pm, total_count, config_prefix)
      count = count + 1

      if sm.updated["mqttRecvQueue"]:
        print("I got a message")
        message = sm["mqttRecvQueue"]
        print(f"I RECEVIED A MESSAGE {message.payload}")


      panda = messaging.recv_sock(panda_state_sock)
      location = messaging.recv_sock(location_sock)
      device = messaging.recv_sock(device_sock)

      panda_prev = panda if panda else panda_prev
      device_prev = device if device else device_prev
      location_prev = location if location else location_prev

      topic = f"{status_prefix}/openpilot/status"
      content = {"panda_state": (strip_deprecated_keys(panda_prev.to_dict()) if panda_prev else None),
                }
      mqttd.publish(pm, topic, content)


      topic = f"{status_prefix}/openpilot/car_status"
      content = {"battery_level": mqtt.soc_out if soc_prev != mqtt.soc_out else None,
                 "range": mqtt.range_out if range_prev != mqtt.range_out else None,
                 "pack_voltage": mqtt.pack_voltage_out if pack_voltage_prev != mqtt.pack_voltage_out else None,
                 "charging_current": mqtt.charging_current_out if charging_current_prev != mqtt.charging_current_out else None,
                 "charging_power": mqtt.charging_power_out if charging_power_prev != mqtt.charging_power_out else None,
                 "charging_time_remaining_minutes": mqtt.charging_time_remaining_out if charging_time_remaining_prev != mqtt.charging_time_remaining_out else None,
                 "charging_time_remaining": format_time(mqtt.charging_time_remaining_out) if charging_time_remaining_prev != mqtt.charging_time_remaining_out else None,
                 "charging_status": mqtt.charging_status_out if charging_status_prev != mqtt.charging_status_out else None,
                }
      mqttd.publish(pm, topic, content)

      soc_prev = mqtt.soc_out
      range_prev = mqtt.range_out
      pack_voltage_prev = mqtt.pack_voltage_out
      charging_current_prev = mqtt.charging_current_out
      charging_power_prev = mqtt.charging_power_out
      charging_time_remaining_prev = mqtt.charging_time_remaining_out
      charging_status_prev = mqtt.charging_status_out


def main():
  status_thread()

if __name__ == "__main__":
  main()