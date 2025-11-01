#!/usr/bin/env python3
"""
LogSplitter Protobuf Database Logger

This script connects to MQTT, decodes protobuf messages, and stores them in a 
SQLite database for historical analysis and web dashboard integration.

Features:
- Real-time protobuf decoding and storage
- SQLite database with proper indexing
- JSON payload storage for flexible querying
- Statistics tracking and monitoring
- Web dashboard data provider
"""

import sqlite3
import json
import time
import threading
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

import paho.mqtt.client as mqtt
from mqtt_protobuf_decoder import LogSplitterProtobufDecoder
from dotenv import load_dotenv

# Load configuration from config.json (same as mqtt_protobuf_decoder.py)
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
MQTT_TOPIC = 'controller/protobuff'

DATABASE_PATH = 'logsplitter_data.db'  # Use same database name as other tools
MAX_DB_SIZE_MB = 500  # Auto-cleanup when database exceeds this size

class ProtobufDatabaseLogger:
    """Database logger for LogSplitter protobuf telemetry"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.decoder = LogSplitterProtobufDecoder()
        self.mqtt_client = None
        self.db_connection = None
        
        # Statistics
        self.messages_processed = 0
        self.db_writes = 0
        self.errors = 0
        self.start_time = time.time()
        
        # Initialize database
        self.init_database()
        
    def init_database(self):
        """Initialize SQLite database with proper schema"""
        try:
            self.db_connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                isolation_level=None  # Auto-commit mode
            )
            
            # Enable WAL mode for better concurrent access
            self.db_connection.execute("PRAGMA journal_mode=WAL")
            self.db_connection.execute("PRAGMA synchronous=NORMAL")
            self.db_connection.execute("PRAGMA cache_size=10000")
            self.db_connection.execute("PRAGMA temp_store=memory")
            
            # Create main telemetry table
            self.db_connection.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    controller_timestamp INTEGER NOT NULL,
                    message_type INTEGER NOT NULL,
                    message_type_name TEXT NOT NULL,
                    sequence_id INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    raw_size INTEGER NOT NULL,
                    processed_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create monitor data table for temperature and fuel data
            self.db_connection.execute("""
                CREATE TABLE IF NOT EXISTS monitor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    received_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    topic TEXT NOT NULL,
                    value REAL,
                    value_text TEXT,
                    processed_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for efficient querying
            self.db_connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp 
                ON telemetry(controller_timestamp)
            """)
            
            self.db_connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_monitor_timestamp 
                ON monitor_data(received_timestamp)
            """)
            
            self.db_connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_monitor_topic 
                ON monitor_data(topic)
            """)
            
            self.db_connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_type 
                ON telemetry(message_type)
            """)
            
            self.db_connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_received 
                ON telemetry(received_timestamp)
            """)
            
            # Create statistics table
            self.db_connection.execute("""
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    total_messages INTEGER NOT NULL,
                    messages_per_minute REAL NOT NULL,
                    database_size_mb REAL NOT NULL,
                    uptime_seconds INTEGER NOT NULL
                )
            """)
            
            # Create message type summary view
            self.db_connection.execute("""
                CREATE VIEW IF NOT EXISTS message_type_summary AS
                SELECT 
                    message_type,
                    message_type_name,
                    COUNT(*) as total_count,
                    MIN(controller_timestamp) as first_seen,
                    MAX(controller_timestamp) as last_seen,
                    AVG(raw_size) as avg_size_bytes
                FROM telemetry 
                GROUP BY message_type, message_type_name
                ORDER BY total_count DESC
            """)
            
            print(f"Database initialized: {self.db_path}")
            self.print_database_stats()
            
        except Exception as e:
            print(f"Database initialization error: {e}")
            raise
    
    def print_database_stats(self):
        """Print current database statistics"""
        try:
            cursor = self.db_connection.cursor()
            
            # Get total message count
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            total_messages = cursor.fetchone()[0]
            
            # Get database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size") 
            page_size = cursor.fetchone()[0]
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            
            # Get message type breakdown
            cursor.execute("SELECT * FROM message_type_summary LIMIT 5")
            type_summary = cursor.fetchall()
            
            print(f"Database Stats:")
            print(f"  Total Messages: {total_messages:,}")
            print(f"  Database Size: {db_size_mb:.2f} MB")
            print(f"  Message Types:")
            for row in type_summary:
                print(f"    {row[1]} ({row[0]:02x}): {row[2]:,} messages")
                
        except Exception as e:
            print(f"Error getting database stats: {e}")
    
    def store_protobuf_message(self, decoded_message: Dict[str, Any], raw_size: int):
        """Store decoded protobuf message in database"""
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute("""
                INSERT INTO telemetry (
                    controller_timestamp,
                    message_type,
                    message_type_name,
                    sequence_id,
                    payload_json,
                    raw_size
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                decoded_message['timestamp'],
                decoded_message['type'],
                decoded_message['type_name'],
                decoded_message['sequence'],
                json.dumps(decoded_message['payload'] or {}, ensure_ascii=False),
                raw_size
            ))
            
            self.db_writes += 1
            
            # Periodically update statistics
            if self.db_writes % 100 == 0:
                self.update_statistics()
                
            # Check database size and cleanup if needed
            if self.db_writes % 1000 == 0:
                self.check_database_size()
                
        except Exception as e:
            print(f"Database write error: {e}")
            self.errors += 1
    
    def store_monitor_message(self, topic: str, value: float = None, value_text: str = None):
        """Store monitor message in database"""
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute("""
                INSERT INTO monitor_data (
                    topic,
                    value,
                    value_text
                ) VALUES (?, ?, ?)
            """, (topic, value, value_text))
            
            self.db_writes += 1
            
        except Exception as e:
            print(f"Monitor database write error: {e}")
            self.errors += 1
    
    def update_statistics(self):
        """Update statistics table"""
        try:
            uptime = int(time.time() - self.start_time)
            messages_per_minute = (self.messages_processed / max(uptime, 1)) * 60
            
            # Get current database size
            cursor = self.db_connection.cursor()
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            
            cursor.execute("""
                INSERT INTO statistics (
                    total_messages,
                    messages_per_minute,
                    database_size_mb,
                    uptime_seconds
                ) VALUES (?, ?, ?, ?)
            """, (self.messages_processed, messages_per_minute, db_size_mb, uptime))
            
        except Exception as e:
            print(f"Statistics update error: {e}")
    
    def check_database_size(self):
        """Check database size and perform cleanup if needed"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            
            if db_size_mb > MAX_DB_SIZE_MB:
                print(f"Database size ({db_size_mb:.1f} MB) exceeds limit ({MAX_DB_SIZE_MB} MB)")
                print("Cleaning up old records...")
                
                # Delete oldest 25% of records
                cursor.execute("SELECT COUNT(*) FROM telemetry")
                total_records = cursor.fetchone()[0]
                delete_count = total_records // 4
                
                cursor.execute("""
                    DELETE FROM telemetry 
                    WHERE id IN (
                        SELECT id FROM telemetry 
                        ORDER BY received_timestamp ASC 
                        LIMIT ?
                    )
                """, (delete_count,))
                
                # Vacuum to reclaim space
                self.db_connection.execute("VACUUM")
                
                print(f"Deleted {delete_count:,} old records")
                self.print_database_stats()
                
        except Exception as e:
            print(f"Database cleanup error: {e}")
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
            # Subscribe to protobuf messages
            client.subscribe(MQTT_TOPIC)
            print(f"Subscribed to topic: {MQTT_TOPIC}")
            # Subscribe to monitor topics for temperature and fuel data
            client.subscribe("monitor/+")
            print(f"Subscribed to topic: monitor/+")
            print("Waiting for protobuf and monitor messages...")
            print("=" * 60)
        else:
            print(f"Failed to connect to MQTT broker (result code {rc})")
    
    def on_mqtt_message(self, client, userdata, message):
        """MQTT message callback with database storage for both protobuf and monitor messages"""
        try:
            self.messages_processed += 1
            
            # Check if this is a protobuf message or monitor message
            if message.topic == MQTT_TOPIC:
                # Handle protobuf message
                self._handle_protobuf_message(message)
            elif message.topic.startswith("monitor/"):
                # Handle monitor message (temperature, fuel, etc.)
                self._handle_monitor_message(message)
                
        except Exception as e:
            self.errors += 1
            print(f"❌ Message processing error: {e}")
    
    def _handle_protobuf_message(self, message):
        """Handle protobuf messages from controller"""
        # Decode protobuf message
        decoded = self.decoder.decode_message(message.payload)
        
        if decoded:
            # Store in database
            self.store_protobuf_message(decoded, len(message.payload))
            
            # Print real-time output (same format as original decoder)
            timestamp_str = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp_str}] {decoded['type_name']} (0x{decoded['type']:02x})")
            print(f"  Sequence: {decoded['sequence']}")
            print(f"  Timestamp: {decoded['timestamp']} ms ({decoded['timestamp']/1000:.1f}s)")
            
            if decoded['payload']:
                print(f"  Payload:")
                for key, value in decoded['payload'].items():
                    print(f"    {key}: {value}")
            
            print()
            
            # Show periodic statistics
            if self.messages_processed % 50 == 0:
                uptime = int(time.time() - self.start_time)
                rate = self.messages_processed / max(uptime, 1)
                print(f"📊 Stats: {self.messages_processed:,} messages, "
                      f"{self.db_writes:,} stored, "
                      f"{rate:.1f} msg/s, "
                      f"{self.errors} errors")
                print("=" * 60)
    
    def _handle_monitor_message(self, message):
        """Handle monitor messages (temperature, fuel, etc.)"""
        try:
            # Decode message payload as string/number
            payload_str = message.payload.decode('utf-8')
            topic = message.topic
            
            # Try to convert to float, keep as string if not numeric
            try:
                value = float(payload_str)
                value_text = None
            except ValueError:
                value = None
                value_text = payload_str
            
            # Store monitor data in database
            self.store_monitor_message(topic, value, value_text)
            
            # Print monitor message (less verbose than protobuf)
            timestamp_str = datetime.now().strftime("%H:%M:%S")
            display_value = value if value is not None else value_text
            print(f"[{timestamp_str}] MONITOR {topic}: {display_value}")
            
        except Exception as e:
            print(f"❌ Monitor message error: {e}")
    
    def get_recent_data(self, limit: int = 100) -> list:
        """Get recent telemetry data for web dashboard"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT 
                    received_timestamp,
                    controller_timestamp,
                    message_type,
                    message_type_name,
                    sequence_id,
                    payload_json,
                    raw_size
                FROM telemetry 
                ORDER BY received_timestamp DESC 
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'received_timestamp': row[0],
                    'controller_timestamp': row[1],
                    'message_type': f"0x{row[2]:02x}",
                    'message_type_name': row[3],
                    'sequence_id': row[4],
                    'payload': json.loads(row[5]) if row[5] else {},
                    'raw_size': row[6]
                })
            
            return results
            
        except Exception as e:
            print(f"Error getting recent data: {e}")
            return []
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """Get statistics for web dashboard"""
        try:
            cursor = self.db_connection.cursor()
            
            # Overall stats
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            total_messages = cursor.fetchone()[0]
            
            # Message type breakdown
            cursor.execute("SELECT * FROM message_type_summary")
            type_breakdown = [
                {
                    'type_id': f"0x{row[0]:02x}",
                    'type_name': row[1],
                    'count': row[2],
                    'first_seen': row[3],
                    'last_seen': row[4],
                    'avg_size': round(row[5], 1)
                }
                for row in cursor.fetchall()
            ]
            
            # Recent activity (last hour)
            cursor.execute("""
                SELECT COUNT(*) FROM telemetry 
                WHERE received_timestamp > datetime('now', '-1 hour')
            """)
            recent_count = cursor.fetchone()[0]
            
            uptime = int(time.time() - self.start_time)
            
            return {
                'total_messages': total_messages,
                'recent_messages_1h': recent_count,
                'type_breakdown': type_breakdown,
                'uptime_seconds': uptime,
                'messages_per_second': total_messages / max(uptime, 1),
                'database_writes': self.db_writes,
                'errors': self.errors
            }
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}
    
    def run(self):
        """Start the database logger"""
        print("LogSplitter Protobuf Database Logger")
        print("Press Ctrl+C to stop")
        print()
        
        # Setup MQTT client
        self.mqtt_client = mqtt.Client()
        if MQTT_USER and MQTT_PASS:
            self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        try:
            # Connect to MQTT broker
            print(f"Connecting to MQTT broker {MQTT_BROKER}:{MQTT_PORT}...")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            
            # Start MQTT loop
            self.mqtt_client.loop_forever()
            
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.update_statistics()
            self.print_database_stats()
            
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                
            if self.db_connection:
                self.db_connection.close()
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    logger = ProtobufDatabaseLogger()
    logger.run()