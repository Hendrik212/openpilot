#!/usr/bin/env python3

import time
import datetime
import cereal.messaging as messaging
from openpilot.system.hardware import HARDWARE
from pyextra.paho.mqtt import client as mqtt_client
from pyextra.paho.mqtt.client import MQTT_ERR_SUCCESS
import json

#f = open("mqtt_daemon_log.txt", "w")

# Generate a unique client ID based on device type and serial number
def client_id():
    device_type = HARDWARE.get_device_type()
    serial = HARDWARE.get_serial()
    return f"{device_type}-{serial}"

# Publish a message to a specified MQTT topic
def publish(pm, topic, message):
    #f.write(f"{datetime.datetime.now()} preparing to publish message with topic " + topic + "\n")
    #f.flush()
    dat = messaging.new_message("mqttPubQueue")
    dat.mqttPubQueue.publish = True
    dat.mqttPubQueue.topic = topic
    dat.mqttPubQueue.content = json.dumps(message)
    pm.send("mqttPubQueue", dat)

# Subscribe to an MQTT topic
def subscribe(pm, topic):
    dat = messaging.new_message("mqttPubQueue")
    dat.mqttPubQueue.subscribe = True
    dat.mqttPubQueue.topic = topic
    pm.send("mqttPubQueue", dat)

# Unsubscribe from an MQTT topic
def unsubscribe(pm, topic):
    dat = messaging.new_message("mqttPubQueue")
    dat.mqttPubQueue.subscribe = False
    dat.mqttPubQueue.publish = False
    dat.mqttPubQueue.topic = topic
    pm.send("mqttPubQueue", dat)

# Callback function when the MQTT client connects
def on_connect(client, userdata, flags, rc):
    if rc != 0:
        client.connected_flag = False
        print(f"Failed to connect, return code {rc}")
        #f.write(f"{datetime.datetime.now()} Failed to connect, return code {rc}\n")
        #f.flush()
    else:
        #f.write(f"{datetime.datetime.now()} connected successfully\n")
        #f.flush()
        client.connected_flag = True
        client.sub_dict = update_subs(client, True)

# Callback function when a message is received
def on_message(client, userdata, msg):
    dat = messaging.new_message("mqttRecvQueue")
    dat.mqttRecvQueue.topic = msg.topic
    dat.mqttRecvQueue.payload = msg.payload
    #pm.send("mqttRecvQueue", dat)
    print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
    #f.write(f"{datetime.datetime.now()} Received `{msg.payload.decode()}` from `{msg.topic}` topic\n")
    #f.flush()

# Callback function when a message is successfully published
def on_publish(client, userdata, mid):
    #print(f"SENT {mid} with SUCCESS")
    #f.write(f"{datetime.datetime.now()}" + {mid} + "with SUCCESS\n")
    #f.flush()
    mid_filter = lambda message: message["mid"] != mid
    client.pub_list = list(filter(mid_filter, client.pub_list))

# Callback function when the MQTT client disconnects
def on_disconnect(client, userdata, rc):
    if rc != 0:
        print("Unexpected disconnection.")
        #f.write(f"{datetime.datetime.now()} Unexpected disconnection.\n")
        #f.flush()
    client.connected_flag = False
    for key in client.sub_dict.keys():
        client.sub_dict[key]["server_state"] = False

# Connect to the MQTT broker
def connect_mqtt(client, broker, port, username, password, pm):
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect

    if port == 8883:
        client.tls_set()

    client.connect(broker, port)
    return client

# Update MQTT subscriptions based on the connection status
def update_subs(client, connect_flag):
    sub_dict = client.sub_dict
    #print(f"\n{sub_dict}\n")
    #f.write(f"{datetime.datetime.now()} {sub_dict}\n")
    #f.flush()
    for key in sub_dict.keys():
        if not sub_dict[key]["subscribe"] and sub_dict[key]["server_state"]:
            if connect_flag:
                sub_dict.pop(key)
            else:
                res, mid = client.unsubscribe(key)
                if res == MQTT_ERR_SUCCESS:
                    sub_dict.pop(key)
                else:
                    print("COULDNT UNSUB")
                    #f.write(f"{datetime.datetime.now()} COULDNT UNSUB\n")
                    #f.flush()
        if sub_dict[key]["subscribe"] and (not sub_dict[key]["server_state"] or connect_flag):
            res, mid = client.subscribe(key)
            if res == MQTT_ERR_SUCCESS:
                print(f"SUBBED {key}")
                #f.write(f"{datetime.datetime.now()} SUBBED {key}\n")
                #f.flush()
                sub_dict[key]["server_state"] = True
            else:
                print("COULDNT SUB")
                #f.write(f"{datetime.datetime.now()} COULDNT SUB\n")
                #f.flush()
    return sub_dict

# Set up the MQTT connection
def setup_connection(client, pm):
    broker = 'mqtt.hendrikgroove.de'
    print("MQTT is going to attempt to connect now")
    #f.write(f"{datetime.datetime.now()} MQTT is going to attempt to connect now\n")
    #f.flush()
    try:
        client = connect_mqtt(client=client, broker=broker, pm=pm, port=1883, username='fhem', password='fhem')
        client.loop_start()
    except:
        print("MQTT connection failed")
        #f.write(f"{datetime.datetime.now()} MQTT connection failed\n")
        #f.flush()
        return True
    return False

# Send MQTT publications
def send_pubs(client):
    updated_pub_list = []
    for message in client.pub_list:
        if message["attempts"] > 4:
            continue
        if message["attempts"] != 0 and time.time() - message["last_sent"] < 0.2:
            updated_pub_list.append(message)
            continue
        #f.write(f"{datetime.datetime.now()} now publishing " + message["topic"] + "\n")
        #f.write(f"{datetime.datetime.now()} " + str(message["content"]) + "\n")
        #f.flush()
        result, mid = client.publish(message["topic"], message["content"])
        #f.write(f"{datetime.datetime.now()} result: "  + str(result) + "\n")
        #f.flush()
        message["mid"] = mid
        message["attempts"] += 1
        message["last_sent"] = time.time()
        updated_pub_list.append(message)

    return updated_pub_list

# Main MQTT thread
def mqtt_thread():
    #f.write(f"{datetime.datetime.now()} --------------------------------------------\n")
    #f.write("mqtt daemon started\n\n")
    #f.flush()

    pm = messaging.PubMaster(['mqttRecvQueue'])
    sm = messaging.SubMaster(['mqttPubQueue'])

    # Set Connecting Client ID
    client = mqtt_client.Client(client_id())
    client.connected_flag = False
    client.sub_dict = {}
    client.pub_list = []

    first_connect = True
    connected = False

    while True:
        if first_connect:
            first_connect = setup_connection(client, pm)

        sm.update()
        if not sm.updated["mqttPubQueue"]:
            continue

        message = sm["mqttPubQueue"]
        if not message.subscribe and not message.publish and message.topic in client.sub_dict:
            client.sub_dict[message.topic]["subscribe"] = False
        if message.subscribe:
            if message.topic not in client.sub_dict:
                client.sub_dict[message.topic] = {"server_state": False}
            client.sub_dict[message.topic]["subscribe"] = True
        if message.publish:
            msg = {"topic": message.topic, "content": message.content, "attempts": 0, "last_sent": time.time(), "mid": -1}
            client.pub_list.append(msg)
            client.pub_list = client.pub_list[-100:]
        if client.connected_flag:
            if not connected:
                connected = True
                print("CONNECTED")
                #f.write(f"{datetime.datetime.now()} CONNECTED\n")
                #f.flush()
            #f.write(f"{datetime.datetime.now()} client sending_pubs\n")
            #f.flush()
            client.sub_dict = update_subs(client, False)
            client.pub_list = send_pubs(client)
        elif not first_connect:
            connected = False
            print("RECONNECTING MANUALLY")
            #f.write(f"{datetime.datetime.now()} RECONNECTING MANUALLY\n")
            #f.flush()
            try:
                client.reconnect()
            except Exception as e:
                first_connect = True
                #f.write(f"{datetime.datetime.now()} error reconnecting " + str(e) + "\n")
                #f.flush()
        #time.sleep(1)
# Main function
def main():
    mqtt_thread()

if __name__ == "__main__":
    main()
