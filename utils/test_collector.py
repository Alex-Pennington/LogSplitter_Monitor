#!/usr/bin/env python3
"""
Test script for LogSplitter InfluxDB Collector
Sends test MQTT messages to verify collection is working
"""

import json
import time
import random
from datetime import datetime

import paho.mqtt.client as mqtt


class TestMessageSender:
    """Sends test MQTT messages to verify collector functionality"""
    
    def __init__(self, mqtt_host='localhost', mqtt_port=1883):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.client = mqtt.Client()
        
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port, 60)
            print(f"Connected to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            return True
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def send_test_messages(self, count=20):
        """Send a variety of test messages"""
        print(f"Sending {count} test messages...")
        
        for i in range(count):
            # Controller messages
            self.client.publish("controller/raw/info", f"Test info message {i}")
            self.client.publish("controller/pressure/a1", f"{245.2 + random.uniform(-5, 5):.1f}")
            self.client.publish("controller/pressure/a5", f"{12.1 + random.uniform(-2, 2):.1f}")
            self.client.publish("controller/sequence/state", 
                              random.choice(["IDLE", "EXTEND_START", "EXTENDING", "RETRACT_START", "RETRACTING"]))
            self.client.publish("controller/relay/r1", random.choice(["ON", "OFF"]))
            self.client.publish("controller/relay/r2", random.choice(["ON", "OFF"]))
            self.client.publish("controller/input/pin6", str(random.randint(0, 1)))
            self.client.publish("controller/input/pin12", str(random.randint(0, 1)))
            
            # Monitor messages
            self.client.publish("monitor/temperature/local", f"{72.5 + random.uniform(-5, 5):.1f}")
            self.client.publish("monitor/temperature/remote", f"{165.8 + random.uniform(-10, 10):.1f}")
            self.client.publish("monitor/weight", f"{125.7 + random.uniform(-10, 10):.1f}")
            self.client.publish("monitor/weight/raw", str(random.randint(50000, 60000)))
            self.client.publish("monitor/power/voltage", f"{12.1 + random.uniform(-0.5, 0.5):.2f}")
            self.client.publish("monitor/power/current", f"{2.3 + random.uniform(-0.3, 0.3):.2f}")
            self.client.publish("monitor/power/watts", f"{27.8 + random.uniform(-2, 2):.1f}")
            self.client.publish("monitor/input/2", str(random.randint(0, 1)))
            self.client.publish("monitor/input/3", str(random.randint(0, 1)))
            self.client.publish("monitor/bridge/status", "Connected")
            self.client.publish("monitor/status", "Running")
            self.client.publish("monitor/heartbeat", str(int(time.time())))
            
            print(f"  Sent batch {i+1}/{count}")
            time.sleep(0.5)  # Small delay between batches
        
        print("✅ Test messages sent successfully")
    
    def send_structured_messages(self):
        """Send structured message formats"""
        print("Sending structured test messages...")
        
        # Structured pressure data
        self.client.publish("controller/pressure/a1", "A1=247.3psi A5=13.8psi")
        
        # Log messages with different levels
        levels = ["debug", "info", "warn", "error", "crit"]
        for level in levels:
            self.client.publish(f"controller/raw/{level}", f"Test {level} message from controller")
        
        # System status messages
        self.client.publish("controller/system/status", "System operational")
        self.client.publish("monitor/system/uptime", "86400")  # 1 day in seconds
        self.client.publish("monitor/system/memory", "45.2")   # Memory usage percentage
        
        print("✅ Structured messages sent")
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.disconnect()
        print("Disconnected from MQTT broker")


def main():
    """Main test function"""
    print("LogSplitter InfluxDB Collector Test")
    print("===================================")
    
    # Get MQTT broker details
    mqtt_host = input("MQTT Host [localhost]: ").strip() or "localhost"
    mqtt_port = input("MQTT Port [1883]: ").strip() or "1883"
    mqtt_port = int(mqtt_port)
    
    sender = TestMessageSender(mqtt_host, mqtt_port)
    
    if not sender.connect():
        return
    
    try:
        # Send test messages
        sender.send_test_messages(10)
        
        print("\nWaiting 2 seconds...")
        time.sleep(2)
        
        # Send structured messages
        sender.send_structured_messages()
        
        print("\n🎉 Test complete!")
        print("\nIf the collector is running, you should see:")
        print("1. Log messages showing received MQTT messages")
        print("2. Data appearing in your InfluxDB bucket")
        print("3. Statistics showing messages received and written")
        
    finally:
        sender.disconnect()


if __name__ == "__main__":
    main()