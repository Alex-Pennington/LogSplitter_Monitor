#!/usr/bin/env python3
"""
LogSplitter Monitor Database Logger

This script connects to MQTT, captures monitor sensor data, and stores it in a 
SQLite database for historical analysis and trend monitoring.

Features:
- Real-time monitor sensor data capture
- SQLite database with proper indexing
- Multiple sensor types: temperature, weight, voltage, digital I/O
- Statistics tracking and monitoring
- Separate from controller protobuf pipeline

Monitor MQTT Topics:
- r4/monitor/status        - Comprehensive system status
- r4/monitor/heartbeat     - Periodic heartbeat with uptime
- r4/monitor/temperature/local   - Local/Ambient temperature (°F)
- r4/monitor/temperature/remote  - Remote/Thermocouple temperature (°F)
- r4/monitor/voltage       - Voltage monitoring (V)
- r4/monitor/weight        - Weight readings (calibrated)
- r4/monitor/weight/raw    - Raw ADC values
- r4/monitor/uptime        - System uptime (seconds)
- r4/monitor/memory        - Free memory (bytes)
- r4/monitor/input/+       - Digital input state changes
"""

import sqlite3
import json
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: config.json not found, using defaults")
        return {
            'mqtt': {
                'host': '127.0.0.1',
                'port': 1883,
                'username': 'rayven',
                'password': 'Th1s1sas3cr3t'
            }
        }

config = load_config()
MQTT_BROKER = config['mqtt']['host']
MQTT_PORT = config['mqtt']['port']
MQTT_USER = config['mqtt']['username']
MQTT_PASS = config['mqtt']['password']

# Database configuration
DB_FILE = 'monitor_data.db'
SCRIPT_DIR = Path(__file__).parent

class MonitorDatabaseLogger:
    """Logs monitor sensor data to SQLite database"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or (SCRIPT_DIR / DB_FILE)
        self.conn = None
        self.mqtt_client = None
        
        # Statistics
        self.messages_received = 0
        self.messages_stored = 0
        self.errors = 0
        self.start_time = time.time()
        
        # Initialize database
        self.init_database()
        
    def init_database(self):
        """Create database tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # Sensor readings table (temperature, voltage, etc.)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                sensor_type TEXT NOT NULL,
                sensor_name TEXT,
                value REAL NOT NULL,
                unit TEXT,
                metadata JSON
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sensor_time 
            ON sensor_readings(sensor_type, received_timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sensor_received 
            ON sensor_readings(received_timestamp)
        ''')
        
        # Weight readings table (separate due to calibration info)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weight_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                weight REAL NOT NULL,
                raw_value INTEGER,
                is_calibrated BOOLEAN,
                metadata JSON
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_weight_time 
            ON weight_readings(received_timestamp)
        ''')
        
        # Digital input events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS digital_inputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                pin INTEGER NOT NULL,
                state BOOLEAN NOT NULL,
                metadata JSON
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_input_pin_time 
            ON digital_inputs(pin, received_timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_input_time 
            ON digital_inputs(received_timestamp)
        ''')
        
        # System status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                uptime_seconds INTEGER,
                free_memory INTEGER,
                status_json JSON
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status_time 
            ON system_status(received_timestamp)
        ''')
        
        self.conn.commit()
        print(f"✓ Database initialized: {self.db_path}")
        
    def store_sensor_reading(self, sensor_type: str, value: float, 
                            sensor_name: str = None, unit: str = None,
                            metadata: Dict = None):
        """Store a sensor reading in the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO sensor_readings 
                (sensor_type, sensor_name, value, unit, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                sensor_type,
                sensor_name,
                value,
                unit,
                json.dumps(metadata) if metadata else None
            ))
            self.conn.commit()
            self.messages_stored += 1
            
        except Exception as e:
            self.errors += 1
            print(f"❌ Error storing sensor reading: {e}")
            
    def store_weight_reading(self, weight: float, raw_value: int = None,
                            is_calibrated: bool = True, metadata: Dict = None):
        """Store a weight reading in the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO weight_readings 
                (weight, raw_value, is_calibrated, metadata)
                VALUES (?, ?, ?, ?)
            ''', (
                weight,
                raw_value,
                is_calibrated,
                json.dumps(metadata) if metadata else None
            ))
            self.conn.commit()
            self.messages_stored += 1
            
        except Exception as e:
            self.errors += 1
            print(f"❌ Error storing weight reading: {e}")
            
    def store_digital_input(self, pin: int, state: bool, metadata: Dict = None):
        """Store a digital input event in the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO digital_inputs 
                (pin, state, metadata)
                VALUES (?, ?, ?)
            ''', (
                pin,
                state,
                json.dumps(metadata) if metadata else None
            ))
            self.conn.commit()
            self.messages_stored += 1
            
        except Exception as e:
            self.errors += 1
            print(f"❌ Error storing digital input: {e}")
            
    def store_system_status(self, uptime: int = None, memory: int = None,
                           status_data: Dict = None):
        """Store system status in the database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO system_status 
                (uptime_seconds, free_memory, status_json)
                VALUES (?, ?, ?)
            ''', (
                uptime,
                memory,
                json.dumps(status_data) if status_data else None
            ))
            self.conn.commit()
            self.messages_stored += 1
            
        except Exception as e:
            self.errors += 1
            print(f"❌ Error storing system status: {e}")
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print("✓ Connected to MQTT broker")
            # Subscribe to all monitor topics
            client.subscribe("monitor/#")
            print("✓ Subscribed to monitor/#")
        else:
            print(f"❌ Connection failed with code {rc}")
            
    def on_message(self, client, userdata, message):
        """MQTT message callback"""
        self.messages_received += 1
        
        try:
            topic = message.topic
            payload = message.payload.decode('utf-8')
            
            # Parse topic to determine data type
            topic_parts = topic.split('/')
            
            if len(topic_parts) < 2:
                return
                
            # monitor/[category]/[subcategory]
            category = topic_parts[1] if len(topic_parts) > 1 else None
            subcategory = topic_parts[2] if len(topic_parts) > 2 else None
            
            timestamp_str = datetime.now().strftime("%H:%M:%S")
            
            # Handle different message types
            if category == 'temperature':
                # Temperature readings
                try:
                    temp = float(payload)
                    sensor_name = subcategory if subcategory else "unknown"
                    self.store_sensor_reading('temperature', temp, sensor_name, '°F')
                    print(f"[{timestamp_str}] Temperature/{sensor_name}: {temp}°F")
                except ValueError:
                    pass
                    
            elif category == 'voltage':
                # Voltage readings
                try:
                    voltage = float(payload)
                    self.store_sensor_reading('voltage', voltage, unit='V')
                    print(f"[{timestamp_str}] Voltage: {voltage}V")
                except ValueError:
                    pass
                    
            elif category == 'adc':
                # ADC readings (voltage, raw values)
                if subcategory == 'voltage':
                    try:
                        voltage = float(payload)
                        self.store_sensor_reading('adc_voltage', voltage, 'ADC', 'V')
                        print(f"[{timestamp_str}] ADC/Voltage: {voltage}V")
                    except ValueError:
                        pass
                elif subcategory == 'raw':
                    try:
                        raw = int(payload)
                        self.store_sensor_reading('adc_raw', float(raw), 'ADC', 'counts')
                        print(f"[{timestamp_str}] ADC/Raw: {raw}")
                    except ValueError:
                        pass
            
            elif category == 'fuel':
                # Fuel level readings
                if subcategory == 'gallons':
                    try:
                        gallons = float(payload)
                        self.store_sensor_reading('fuel', gallons, 'fuel_tank', 'gallons')
                        print(f"[{timestamp_str}] Fuel: {gallons} gallons")
                    except ValueError:
                        pass
                    
            elif category == 'weight':
                # Weight readings
                if subcategory == 'raw':
                    try:
                        raw = int(payload)
                        self.store_weight_reading(0.0, raw_value=raw, is_calibrated=False,
                                                metadata={'type': 'raw'})
                        print(f"[{timestamp_str}] Weight/Raw: {raw}")
                    except ValueError:
                        pass
                else:
                    try:
                        weight = float(payload)
                        self.store_weight_reading(weight, is_calibrated=True)
                        print(f"[{timestamp_str}] Weight: {weight}")
                    except ValueError:
                        pass
                        
            elif category == 'uptime':
                # System uptime
                try:
                    uptime = int(payload)
                    self.store_system_status(uptime=uptime)
                    print(f"[{timestamp_str}] Uptime: {uptime}s")
                except ValueError:
                    pass
                    
            elif category == 'memory':
                # Free memory
                try:
                    memory = int(payload)
                    self.store_system_status(memory=memory)
                    print(f"[{timestamp_str}] Memory: {memory} bytes")
                except ValueError:
                    pass
                    
            elif category == 'input':
                # Digital input state changes
                try:
                    pin = int(subcategory) if subcategory else 0
                    state = int(payload) == 1
                    self.store_digital_input(pin, state)
                    print(f"[{timestamp_str}] Input/{pin}: {'HIGH' if state else 'LOW'}")
                except (ValueError, TypeError):
                    pass
                    
            elif category == 'status':
                # Comprehensive status (JSON)
                try:
                    status_data = json.loads(payload)
                    self.store_system_status(status_data=status_data)
                    print(f"[{timestamp_str}] Status update received")
                except json.JSONDecodeError:
                    pass
                    
            elif category == 'heartbeat':
                # Heartbeat messages (can extract uptime if present)
                print(f"[{timestamp_str}] Heartbeat received")
                
        except Exception as e:
            self.errors += 1
            print(f"❌ Error processing message: {e}")
            
    def print_statistics(self):
        """Print current statistics"""
        runtime = time.time() - self.start_time
        print("\n" + "="*60)
        print(f"Runtime: {runtime:.1f}s")
        print(f"Messages Received: {self.messages_received}")
        print(f"Messages Stored: {self.messages_stored}")
        print(f"Errors: {self.errors}")
        print(f"Messages/sec: {self.messages_received/runtime:.2f}")
        print("="*60 + "\n")
        
    def run(self):
        """Start the MQTT client and run the logger"""
        print("="*60)
        print("LogSplitter Monitor Database Logger")
        print("="*60)
        print(f"Database: {self.db_path}")
        print(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print("="*60 + "\n")
        
        # Setup MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        # Connect and start loop
        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            
            # Start statistics printer
            last_stats = time.time()
            
            # Run forever
            self.mqtt_client.loop_start()
            
            while True:
                time.sleep(1)
                
                # Print statistics every 60 seconds
                if time.time() - last_stats >= 60:
                    self.print_statistics()
                    last_stats = time.time()
                    
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            self.print_statistics()
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.conn.close()
            print("✓ Shutdown complete")
            
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            self.conn.close()

if __name__ == "__main__":
    logger = MonitorDatabaseLogger()
    logger.run()
