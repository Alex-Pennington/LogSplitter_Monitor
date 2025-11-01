#!/usr/bin/env python3
"""
Simple protobuf message inspector to debug the data flow
"""
import paho.mqtt.client as mqtt
import json
import struct

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe("controller/protobuff")
        client.subscribe("monitor/+")
    else:
        print(f"❌ Failed to connect: {rc}")

def on_message(client, userdata, msg):
    timestamp = __import__('datetime').datetime.now().strftime('%H:%M:%S')
    
    if msg.topic == "controller/protobuff":
        payload = msg.payload
        print(f"🔵 [{timestamp}] Protobuf: {len(payload)} bytes")
        
        # Show raw bytes (first 20 bytes)
        hex_bytes = ' '.join([f'{b:02x}' for b in payload[:20]])
        print(f"   Raw: {hex_bytes}{'...' if len(payload) > 20 else ''}")
        
        if len(payload) >= 1:
            msg_type = payload[0]
            print(f"   Type: 0x{msg_type:02x}")
            
        # Try to decode basic structure
        if len(payload) >= 8:
            try:
                # Assume first 8 bytes might be timestamp
                timestamp_bytes = payload[1:9]
                timestamp_value = struct.unpack('<Q', timestamp_bytes)[0]
                print(f"   Possible timestamp: {timestamp_value}")
            except:
                pass
                
    elif msg.topic.startswith("monitor/"):
        payload_str = msg.payload.decode() if msg.payload else "empty"
        print(f"🟢 [{timestamp}] Monitor: {msg.topic} = {payload_str}")

def main():
    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found")
        return
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    mqtt_config = config['mqtt']
    client.username_pw_set(mqtt_config['username'], mqtt_config['password'])
    
    try:
        client.connect(mqtt_config['host'], mqtt_config['port'], 60)
        print(f"Monitoring MQTT messages for 60 seconds...")
        client.loop_start()
        
        import time
        time.sleep(60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()