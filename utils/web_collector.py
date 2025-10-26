#!/usr/bin/env python3
"""
LogSplitter Web Dashboard & InfluxDB Collector
Combines MQTT data collection with real-time web dashboard
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import re
from threading import Thread
import os

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS


class LogSplitterWebCollector:
    """Combined MQTT collector and Flask web dashboard"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.influx_client = None
        self.write_api = None
        self.mqtt_client = None
        self.flask_app = None
        self.socketio = None
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.get('log_level', 'INFO').upper()),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Real-time data cache for web dashboard
        self.realtime_data = {
            'controller': {
                'estop_active': False,
                'engine_running': False,
                'system_active': True,
                'current_state': 'UNKNOWN',
                'pressure_a1': 0.0,
                'pressure_a5': 0.0,
                'uptime_seconds': 0,
                'sequence_count': 0
            },
            'monitor': {
                'fuel_gallons': 0.0,
                'fuel_pounds': 0.0,
                'fuel_ready': False,
                'temp_local': 0.0,
                'temp_remote': 0.0,
                'sensors_ok': True,
                'uptime_seconds': 0,
                'heartbeat_active': True,
                'heartbeat_bpm': 72
            },
            'system': {
                'messages_received': 0,
                'messages_written': 0,
                'errors': 0,
                'start_time': datetime.now(),
                'last_update': datetime.now()
            }
        }
        
        self.setup_flask()
        
    def setup_flask(self):
        """Initialize Flask application and routes"""
        # Create Flask app
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
        
        self.flask_app = Flask(__name__, 
                              template_folder=template_dir,
                              static_folder=static_dir)
        self.flask_app.config['SECRET_KEY'] = 'logsplitter-dashboard-2025'
        
        # Enable CORS and WebSocket
        CORS(self.flask_app)
        self.socketio = SocketIO(self.flask_app, cors_allowed_origins="*")
        
        # Routes
        @self.flask_app.route('/')
        def dashboard():
            return render_template('dashboard.html')
            
        @self.flask_app.route('/api/status')
        def api_status():
            return jsonify(self.realtime_data)
            
        @self.flask_app.route('/api/controller')
        def api_controller():
            return jsonify(self.realtime_data['controller'])
            
        @self.flask_app.route('/api/monitor')  
        def api_monitor():
            return jsonify(self.realtime_data['monitor'])
            
        @self.flask_app.route('/api/system')
        def api_system():
            stats = self.realtime_data['system'].copy()
            uptime = datetime.now() - stats['start_time']
            stats['uptime_seconds'] = uptime.total_seconds()
            stats['uptime_formatted'] = str(uptime).split('.')[0]
            stats['start_time'] = stats['start_time'].isoformat()
            stats['last_update'] = stats['last_update'].isoformat()
            return jsonify(stats)
            
        # WebSocket events
        @self.socketio.on('connect')
        def handle_connect():
            self.logger.info('Dashboard client connected')
            emit('status_update', self.realtime_data)
            
        @self.socketio.on('disconnect')
        def handle_disconnect():
            self.logger.info('Dashboard client disconnected')
    
    def connect_influxdb(self):
        """Initialize InfluxDB v2 connection"""
        try:
            self.influx_client = InfluxDBClient(
                url=self.config['influxdb']['url'],
                token=self.config['influxdb']['token'],
                org=self.config['influxdb']['org']
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            
            # Test connection
            health = self.influx_client.health()
            self.logger.info(f"InfluxDB connection established: {health.status}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to InfluxDB: {e}")
            return False
    
    def connect_mqtt(self):
        """Initialize MQTT connection"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            # Set credentials if provided
            if self.config['mqtt'].get('username'):
                self.mqtt_client.username_pw_set(
                    self.config['mqtt']['username'],
                    self.config['mqtt'].get('password', '')
                )
            
            self.mqtt_client.connect(
                self.config['mqtt']['host'],
                self.config['mqtt']['port'],
                self.config['mqtt']['keepalive']
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            # Subscribe to all LogSplitter topics
            topics = [
                "controller/+/+",
                "monitor/+/+",
                "controller/+",
                "monitor/+",
            ]
            
            for topic in topics:
                client.subscribe(topic)
                self.logger.info(f"Subscribed to {topic}")
                
        else:
            self.logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.logger.warning(f"Disconnected from MQTT broker: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Process incoming MQTT message"""
        try:
            self.realtime_data['system']['messages_received'] += 1
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            timestamp = datetime.now(timezone.utc)
            
            self.logger.debug(f"Received: {topic} = {payload}")
            
            # Update real-time cache
            self._update_realtime_data(topic, payload)
            
            # Parse and write to InfluxDB
            points = self._parse_message(topic, payload, timestamp)
            if points:
                self.write_api.write(
                    bucket=self.config['influxdb']['bucket'],
                    org=self.config['influxdb']['org'],
                    record=points
                )
                self.realtime_data['system']['messages_written'] += len(points)
                self.logger.debug(f"Wrote {len(points)} points to InfluxDB")
            
            # Update timestamp
            self.realtime_data['system']['last_update'] = datetime.now()
            
            # Emit real-time update to web clients
            if self.socketio:
                self.socketio.emit('status_update', self.realtime_data)
            
        except Exception as e:
            self.realtime_data['system']['errors'] += 1
            self.logger.error(f"Error processing message {topic}: {e}")
    
    def _update_realtime_data(self, topic: str, payload: str):
        """Update real-time data cache for web dashboard"""
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            return
            
        system = topic_parts[0]  # 'controller' or 'monitor'
        category = topic_parts[1]
        
        try:
            if system == 'controller':
                if category == 'raw':
                    # Parse status messages for dashboard
                    if "E-STOP ACTIVATED" in payload:
                        self.realtime_data['controller']['estop_active'] = True
                    elif "E-STOP cleared" in payload:
                        self.realtime_data['controller']['estop_active'] = False
                        
                    if "Engine stopped" in payload:
                        self.realtime_data['controller']['engine_running'] = False
                    elif "Engine started" in payload:
                        self.realtime_data['controller']['engine_running'] = True
                        
                    # Parse system state
                    state_match = re.search(r'state=(\w+)', payload)
                    if state_match:
                        self.realtime_data['controller']['current_state'] = state_match.group(1)
                        
                    # Parse uptime
                    uptime_match = re.search(r'uptime=(\d+)s', payload)
                    if uptime_match:
                        self.realtime_data['controller']['uptime_seconds'] = int(uptime_match.group(1))
                        
                elif category == 'pressure' and len(topic_parts) >= 3:
                    sensor = topic_parts[2].lower()
                    try:
                        value = float(payload)
                        if sensor == 'a1':
                            self.realtime_data['controller']['pressure_a1'] = value
                        elif sensor == 'a5':
                            self.realtime_data['controller']['pressure_a5'] = value
                    except ValueError:
                        pass
                        
            elif system == 'monitor':
                if category == 'weight':
                    try:
                        weight_pounds = float(payload)
                        fuel_gallons = weight_pounds / 7.2
                        self.realtime_data['monitor']['fuel_pounds'] = weight_pounds
                        self.realtime_data['monitor']['fuel_gallons'] = fuel_gallons
                    except ValueError:
                        # Parse weight status message
                        if "ready: YES" in payload:
                            self.realtime_data['monitor']['fuel_ready'] = True
                        elif "ready: NO" in payload:
                            self.realtime_data['monitor']['fuel_ready'] = False
                            
                elif category == 'temperature' and len(topic_parts) >= 3:
                    sensor = topic_parts[2]
                    try:
                        temp = float(payload)
                        if sensor == 'local':
                            self.realtime_data['monitor']['temp_local'] = temp
                        elif sensor == 'remote':
                            self.realtime_data['monitor']['temp_remote'] = temp
                    except ValueError:
                        pass
                        
                elif category == 'status':
                    if "sensors=OK" in payload:
                        self.realtime_data['monitor']['sensors_ok'] = True
                    elif "sensors=" in payload and "OK" not in payload:
                        self.realtime_data['monitor']['sensors_ok'] = False
                        
                    # Parse uptime from monitor status
                    uptime_match = re.search(r'uptime=(\d+)s', payload)
                    if uptime_match:
                        self.realtime_data['monitor']['uptime_seconds'] = int(uptime_match.group(1))
                        
                    # Parse heartbeat info
                    if "heartbeat" in payload.lower():
                        if "active" in payload.lower() or "on" in payload.lower():
                            self.realtime_data['monitor']['heartbeat_active'] = True
                        bpm_match = re.search(r'(\d+)\s*bpm', payload.lower())
                        if bpm_match:
                            self.realtime_data['monitor']['heartbeat_bpm'] = int(bpm_match.group(1))
                            
        except Exception as e:
            self.logger.error(f"Error updating realtime data for {topic}: {e}")
    
    def _parse_message(self, topic: str, payload: str, timestamp: datetime) -> list:
        """Parse MQTT message and convert to InfluxDB points - using original parsing logic"""
        points = []
        
        # Split topic into components
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            return points
            
        system = topic_parts[0]  # 'controller' or 'monitor'
        category = topic_parts[1]  # 'raw', 'pressure', 'temperature', etc.
        
        try:
            # Handle different message types
            if system == 'controller':
                points.extend(self._parse_controller_message(topic_parts, payload, timestamp))
            elif system == 'monitor':
                points.extend(self._parse_monitor_message(topic_parts, payload, timestamp))
                
        except Exception as e:
            self.logger.error(f"Error parsing {topic}: {e}")
            
        return points
    
    def _parse_controller_message(self, topic_parts: list, payload: str, timestamp: datetime) -> list:
        """Parse controller MQTT messages - original logic from collector"""
        points = []
        system, category = topic_parts[0], topic_parts[1]
        
        if category == 'raw':
            # Raw log messages: controller/raw/debug, controller/raw/error, etc.
            if len(topic_parts) >= 3:
                level = topic_parts[2]
                points.append(
                    Point("controller_log")
                    .tag("level", level)
                    .field("message", payload)
                    .field("count", 1)
                    .time(timestamp, WritePrecision.NS)
                )
                
                # Parse status messages into separate measurements with boolean/numeric fields
                parsed_points = self._parse_status_message(payload, timestamp)
                points.extend(parsed_points)
                
        elif category == 'pressure':
            # Pressure data: controller/pressure/a1, controller/pressure/a5
            if len(topic_parts) >= 3:
                sensor = topic_parts[2]
                try:
                    # Handle both numeric and structured data
                    if payload.replace('.', '').isdigit():
                        value = float(payload)
                        points.append(
                            Point("controller_pressure")
                            .tag("sensor", sensor.upper())
                            .field("psi", value)
                            .time(timestamp, WritePrecision.NS)
                        )
                except ValueError:
                    self.logger.warning(f"Could not parse pressure value: {payload}")
                    
        elif category == 'sequence':
            # Sequence state: controller/sequence/state
            points.append(
                Point("controller_sequence")
                .tag("state", payload)
                .field("active", 1)
                .time(timestamp, WritePrecision.NS)
            )
            
        return points
    
    def _parse_monitor_message(self, topic_parts: list, payload: str, timestamp: datetime) -> list:
        """Parse monitor MQTT messages - original logic from collector"""
        points = []
        system, category = topic_parts[0], topic_parts[1]
        
        if category == 'temperature':
            # Temperature data: monitor/temperature/local, monitor/temperature/remote
            if len(topic_parts) >= 3:
                sensor = topic_parts[2]
                try:
                    value = float(payload)
                    points.append(
                        Point("monitor_temperature")
                        .tag("sensor", sensor)
                        .field("fahrenheit", value)
                        .time(timestamp, WritePrecision.NS)
                    )
                except ValueError:
                    pass
                    
        elif category == 'weight':
            # Weight data converted to fuel volume
            try:
                weight_pounds = float(payload)
                fuel_gallons = weight_pounds / 7.2
                
                points.append(
                    Point("monitor_fuel")
                    .field("pounds", weight_pounds)
                    .field("gallons", fuel_gallons)
                    .time(timestamp, WritePrecision.NS)
                )
            except ValueError:
                # Parse fuel status message
                points.append(
                    Point("monitor_fuel")
                    .field("status", payload)
                    .time(timestamp, WritePrecision.NS)
                )
                
        elif category in ['status', 'heartbeat', 'uptime', 'memory']:
            # System metrics
            try:
                value = float(payload)
                points.append(
                    Point("monitor_system")
                    .tag("metric", category)
                    .field("value", value)
                    .time(timestamp, WritePrecision.NS)
                )
            except ValueError:
                points.append(
                    Point("monitor_system")
                    .tag("metric", category)
                    .field("message", payload)
                    .time(timestamp, WritePrecision.NS)
                )
                
        return points
    
    def _parse_status_message(self, message: str, timestamp: datetime) -> list:
        """Parse status messages for structured data - simplified version"""
        points = []
        
        # E-Stop Status
        if "E-STOP ACTIVATED" in message:
            points.append(
                Point("controller_estop")
                .field("active", True)
                .time(timestamp, WritePrecision.NS)
            )
            
        # Engine Status
        if "Engine stopped" in message:
            points.append(
                Point("controller_engine")
                .field("running", False)
                .time(timestamp, WritePrecision.NS)
            )
        elif "Engine started" in message:
            points.append(
                Point("controller_engine")
                .field("running", True)
                .time(timestamp, WritePrecision.NS)
            )
            
        # System Status: "System: uptime=3630s state=IDLE"
        system_match = re.search(r'System:\s+uptime=(\d+)s\s+state=(\w+)', message)
        if system_match:
            uptime = int(system_match.group(1))
            state = system_match.group(2)
            
            points.append(
                Point("controller_system")
                .tag("state", state)
                .field("uptime_seconds", uptime)
                .field("active", True)
                .time(timestamp, WritePrecision.NS)
            )
            
        return points
    
    def run_mqtt_collector(self):
        """Run MQTT collector in separate thread"""
        if not self.connect_influxdb():
            self.logger.error("Failed to connect to InfluxDB")
            return
            
        if not self.connect_mqtt():
            self.logger.error("Failed to connect to MQTT")
            return
        
        self.logger.info("MQTT collector started")
        self.mqtt_client.loop_forever()
    
    def run_web_server(self):
        """Run Flask web server"""
        web_config = self.config.get('web', {})
        host = web_config.get('host', '0.0.0.0')
        port = web_config.get('port', 8080)
        debug = web_config.get('debug', False)
        
        self.logger.info(f"Starting web dashboard on http://{host}:{port}")
        self.socketio.run(self.flask_app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    
    def run(self):
        """Main entry point - run both MQTT collector and web server"""
        # Start MQTT collector in background thread
        mqtt_thread = Thread(target=self.run_mqtt_collector, daemon=True)
        mqtt_thread.start()
        
        # Give MQTT time to connect
        time.sleep(2)
        
        # Run web server in main thread
        try:
            self.run_web_server()
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            if self.influx_client:
                self.influx_client.close()


def load_config(config_file: str = 'config.json') -> Dict[str, Any]:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default config
        return {
            "mqtt": {
                "host": "localhost",
                "port": 1883,
                "keepalive": 60,
                "username": "",
                "password": ""
            },
            "influxdb": {
                "url": "http://localhost:8086",
                "token": "your-influxdb-token",
                "org": "your-org",
                "bucket": "logsplitter"
            },
            "web": {
                "host": "0.0.0.0",
                "port": 8080,
                "debug": False
            },
            "log_level": "INFO"
        }


def main():
    """Main entry point"""
    config = load_config()
    
    collector = LogSplitterWebCollector(config)
    
    try:
        collector.run()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()