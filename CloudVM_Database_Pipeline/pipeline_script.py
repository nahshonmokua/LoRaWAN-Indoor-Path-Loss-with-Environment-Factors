import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
import json
import time

# MQTT Broker details
MQTT_BROKER = "xxxxx"
MQTT_PORT = xxxx
MQTT_USERNAME = "xxxxx"
MQTT_PASSWORD = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
MQTT_TOPIC = "xxxxx"

# InfluxDB details
INFLUXDB_HOST = "xxxx"
INFLUXDB_PORT = xxxx
INFLUXDB_DATABASE = "xxxxx"

# Callback for MQTT message
def on_message(client, userdata, message):
    payload = message.payload.decode('utf-8')
    topic = message.topic
    print("Received message:", payload)
    device_id = extract_device_id(topic)
    decoded_data = extract_parameters(payload)
    if decoded_data:
        decoded_data["device_id"] = device_id  # Include device ID in data
        write_to_influxdb(decoded_data)

# Function to extract device ID from the MQTT topic
def extract_device_id(topic):
    parts = topic.split('/')
    return parts[4]  # Device ID should be the 5th part of the topic

# Function to extract parameters from payload
def extract_parameters(payload):
    try:
        payload_json = json.loads(payload)

        def flatten_json(json_obj, parent_key='', sep='_'):
            items = {}
            for k, v in json_obj.items():
                new_key = f"{parent_key}{sep}{k}".replace('-', '_').replace('.', '_') if parent_key else k.replace('-',
                                                                                                                   '_').replace(
                    '.', '_')
                if isinstance(v, dict):
                    items.update(flatten_json(v, new_key, sep=sep))
                elif isinstance(v, list):
                    for i, item in enumerate(v):
                        items.update(flatten_json({f"{k}_{i}": item}, parent_key, sep))
                else:
                    items[new_key] = v
            return items

        flat_payload = flatten_json(payload_json)

        # Ensure correct data types for InfluxDB
        for key in flat_payload:
            if isinstance(flat_payload[key], bool):
                flat_payload[key] = str(flat_payload[key])  # Convert boolean to string
            elif isinstance(flat_payload[key], int):
                flat_payload[key] = float(flat_payload[key])  # Convert int to float
            elif isinstance(flat_payload[key], list):
                flat_payload[key] = str(flat_payload[key])  # Convert list to string

        return flat_payload

    except Exception as e:
        print("Error extracting parameters from payload:", e)
        return None

# Function to write data to InfluxDB
def write_to_influxdb(data):
    client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT)
    databases = client.get_list_database()
    if {"name": INFLUXDB_DATABASE} not in databases:
        client.create_database(INFLUXDB_DATABASE)
    client.switch_database(INFLUXDB_DATABASE)
    json_body = [
        {
            "measurement": "xxxxxx",
            "fields": data
        }
    ]
    client.write_points(json_body)

# Function to connect to MQTT broker with retry mechanism
def connect_mqtt():
    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.subscribe(MQTT_TOPIC)
            mqtt_client.loop_start()
            print("Connected to MQTT Broker")
            break
        except Exception as e:
            print("Failed to connect to MQTT Broker:", e)
            time.sleep(5)

# MQTT client setup
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USERNAME, password=MQTT_PASSWORD)
mqtt_client.on_message = on_message
mqtt_client.on_disconnect = lambda client, userdata, rc: connect_mqtt()

# Connect to MQTT broker
connect_mqtt()

# Keep the script running
while True:
    time.sleep(1)
