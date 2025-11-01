#!/usr/bin/env python3
"""
Test script to verify LogSplitter data flow and basket metrics system

This script will:
1. Check MQTT connectivity
2. Monitor for incoming protobuf messages
3. Test the database logger
4. Display basket metrics dashboard when data is available
"""

import time
import json
import sqlite3
import threading
from datetime import datetime
import paho.mqtt.client as mqtt
from basket_metrics_dashboard import BasketMetricsDashboard

class LogSplitterSystemTest:
    def __init__(self):
        self.db_path = 'logsplitter_telemetry.db'
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.message_count = 0
        self.running = True
        
        # Load config
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print("❌ config.json not found. Please create it from config.json.template")
            raise
        
    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT broker")
            print("📡 Subscribing to topics:")
            
            # Subscribe to both controller protobuf and monitor topics
            client.subscribe("controller/protobuff")
            print("   - controller/protobuff (protobuf messages)")
            
            client.subscribe("monitor/+")
            print("   - monitor/+ (monitor sensor data)")
            
            # Subscribe to a few key specific monitor topics
            for topic in ['monitor/temperature', 'monitor/temperature/remote', 'monitor/fuel_gallons']:
                client.subscribe(topic)
                print(f"   - {topic}")
                
        else:
            print(f"❌ Failed to connect to MQTT broker: {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        self.message_count += 1
        timestamp = datetime.now().isoformat()
        
        if msg.topic == "controller/protobuff":
            print(f"🔵 [{timestamp}] Protobuf message #{self.message_count}: {len(msg.payload)} bytes")
            
            # Try to decode the message
            try:
                from mqtt_protobuf_decoder import LogSplitterProtobufDecoder
                decoder = LogSplitterProtobufDecoder()
                decoded = decoder.decode_message(msg.payload)
                
                if decoded:
                    print(f"   Type: {decoded.get('message_type_name', 'Unknown')}")
                    if decoded.get('payload_json'):
                        payload = json.loads(decoded['payload_json'])
                        print(f"   Data: {payload}")
                    else:
                        print("   Payload: Empty")
                else:
                    print("   ⚠️  Failed to decode")
                    
            except Exception as e:
                print(f"   ❌ Decode error: {e}")
                
        elif msg.topic.startswith("monitor/"):
            try:
                value = float(msg.payload.decode())
                print(f"🟢 [{timestamp}] Monitor data: {msg.topic} = {value}")
            except:
                payload_str = msg.payload.decode()
                print(f"🟢 [{timestamp}] Monitor data: {msg.topic} = {payload_str}")
    
    def check_database(self):
        """Check database status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                print("📊 Database: Empty (no tables)")
                conn.close()
                return
                
            print(f"📊 Database tables: {', '.join(tables)}")
            
            # Check record counts
            if 'telemetry' in tables:
                cursor.execute("SELECT COUNT(*) FROM telemetry")
                telemetry_count = cursor.fetchone()[0]
                print(f"   - Telemetry messages: {telemetry_count}")
                
                if telemetry_count > 0:
                    cursor.execute("SELECT message_type_name, COUNT(*) FROM telemetry GROUP BY message_type_name ORDER BY COUNT(*) DESC")
                    for row in cursor.fetchall():
                        print(f"     - {row[0]}: {row[1]} messages")
            
            if 'monitor_data' in tables:
                cursor.execute("SELECT COUNT(*) FROM monitor_data")
                monitor_count = cursor.fetchone()[0]
                print(f"   - Monitor data points: {monitor_count}")
                
                if monitor_count > 0:
                    cursor.execute("SELECT topic, COUNT(*) FROM monitor_data GROUP BY topic ORDER BY COUNT(*) DESC")
                    for row in cursor.fetchall():
                        print(f"     - {row[0]}: {row[1]} readings")
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
    
    def test_basket_metrics(self):
        """Test the basket metrics system"""
        try:
            dashboard = BasketMetricsDashboard(self.db_path)
            exchanges = dashboard.analyze_basket_exchanges(hours=1)
            
            print(f"🧺 Basket Exchange Analysis:")
            print(f"   - Exchanges found: {len(exchanges)}")
            
            if exchanges:
                for i, exchange in enumerate(exchanges, 1):
                    print(f"   - Exchange {i}: {exchange.duration_seconds:.1f}s, "
                          f"Type: {exchange.exchange_type}, "
                          f"Confidence: {exchange.confidence:.2f}")
            else:
                print("   - No basket exchanges detected yet")
                print("   - Run splitter operations to generate exchange data")
                
        except Exception as e:
            print(f"❌ Basket metrics error: {e}")
    
    def monitor_system(self, duration_minutes: int = 5):
        """Monitor the system for a specified duration"""
        print(f"🔍 Monitoring LogSplitter system for {duration_minutes} minutes...")
        print("💡 Tip: Run splitter operations to see protobuf messages and basket exchange detection")
        print("⏹️  Press Ctrl+C to stop monitoring early\n")
        
        # Connect to MQTT
        mqtt_config = self.config['mqtt']
        self.mqtt_client.username_pw_set(mqtt_config['username'], mqtt_config['password'])
        
        try:
            self.mqtt_client.connect(mqtt_config['host'], mqtt_config['port'], 60)
            self.mqtt_client.loop_start()
            
            start_time = time.time()
            last_status = time.time()
            
            while self.running and (time.time() - start_time) < (duration_minutes * 60):
                time.sleep(1)
                
                # Print status every 30 seconds
                if time.time() - last_status >= 30:
                    elapsed = int(time.time() - start_time)
                    remaining = int((duration_minutes * 60) - elapsed)
                    print(f"\n📈 Status update ({elapsed}s elapsed, {remaining}s remaining):")
                    print(f"   - MQTT messages received: {self.message_count}")
                    self.check_database()
                    self.test_basket_metrics()
                    print()
                    last_status = time.time()
            
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")
        finally:
            self.running = False
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        # Final status
        print(f"\n🏁 Final Status:")
        print(f"   - Total MQTT messages: {self.message_count}")
        self.check_database()
        self.test_basket_metrics()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='LogSplitter System Test')
    parser.add_argument('--minutes', type=int, default=5, help='Minutes to monitor (default: 5)')
    parser.add_argument('--dashboard', action='store_true', help='Show basket metrics dashboard')
    parser.add_argument('--status-only', action='store_true', help='Check status only, no monitoring')
    args = parser.parse_args()
    
    tester = LogSplitterSystemTest()
    
    if args.status_only:
        print("🔍 LogSplitter System Status Check")
        print("=" * 50)
        tester.check_database()
        tester.test_basket_metrics()
    elif args.dashboard:
        print("📊 Opening Basket Metrics Dashboard...")
        dashboard = BasketMetricsDashboard()
        dashboard.update_dashboard(hours=24)
        import matplotlib.pyplot as plt
        plt.show()
    else:
        tester.monitor_system(args.minutes)

if __name__ == "__main__":
    main()