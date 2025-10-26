#!/usr/bin/env python3
"""
LogSplitter Monitor & Controller Metrics to InfluxDB v2
Collects MQTT telemetry data and stores it in InfluxDB v2 for monitoring and analysis.

This program subscribes to all LogSplitter MQTT topics and writes metrics to InfluxDB
with proper measurement names, tags, and field values for time-series analysis.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import re

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


class LogSplitterInfluxCollector:
    """Collects LogSplitter MQTT metrics and stores them in InfluxDB v2"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.influx_client = None
        self.write_api = None
        self.mqtt_client = None
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.get('log_level', 'INFO').upper()),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_written': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
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
                "controller/+/+",      # All controller topics
                "monitor/+/+",         # All monitor topics  
                "controller/+",        # Single level controller
                "monitor/+",          # Single level monitor
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
            self.stats['messages_received'] += 1
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            timestamp = datetime.now(timezone.utc)
            
            self.logger.debug(f"Received: {topic} = {payload}")
            
            # Parse and write to InfluxDB
            points = self._parse_message(topic, payload, timestamp)
            if points:
                self.write_api.write(
                    bucket=self.config['influxdb']['bucket'],
                    org=self.config['influxdb']['org'],
                    record=points
                )
                self.stats['messages_written'] += len(points)
                self.logger.debug(f"Wrote {len(points)} points to InfluxDB")
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error processing message {topic}: {e}")
    
    def _parse_message(self, topic: str, payload: str, timestamp: datetime) -> list:
        """Parse MQTT message and convert to InfluxDB points"""
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
        """Parse controller MQTT messages"""
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
                    if payload.isdigit() or '.' in payload:
                        value = float(payload)
                        points.append(
                            Point("controller_pressure")
                            .tag("sensor", sensor.upper())
                            .field("psi", value)
                            .time(timestamp, WritePrecision.NS)
                        )
                    else:
                        # Parse structured pressure data "A1=245.2psi A5=12.1psi"
                        pressure_values = self._parse_pressure_data(payload)
                        for sensor_name, psi_value in pressure_values.items():
                            points.append(
                                Point("controller_pressure")
                                .tag("sensor", sensor_name)
                                .field("psi", psi_value)
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
            
        elif category == 'relay':
            # Relay states: controller/relay/r1, controller/relay/r2
            if len(topic_parts) >= 3:
                relay = topic_parts[2].upper()
                state = payload.upper()
                points.append(
                    Point("controller_relay")
                    .tag("relay", relay)
                    .tag("state", state)
                    .field("active", 1 if state == 'ON' else 0)
                    .time(timestamp, WritePrecision.NS)
                )
                
        elif category == 'input':
            # Input states: controller/input/pin6, controller/input/pin12
            if len(topic_parts) >= 3:
                pin = topic_parts[2]
                state = int(payload) if payload.isdigit() else 0
                points.append(
                    Point("controller_input")
                    .tag("pin", pin)
                    .field("state", state)
                    .time(timestamp, WritePrecision.NS)
                )
                
        elif category == 'system':
            # System status: controller/system/status
            points.append(
                Point("controller_system")
                .field("status", payload)
                .field("active", 1)
                .time(timestamp, WritePrecision.NS)
            )
            
        return points
    
    def _parse_monitor_message(self, topic_parts: list, payload: str, timestamp: datetime) -> list:
        """Parse monitor MQTT messages"""
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
            # Weight data converted to fuel volume: monitor/weight, monitor/weight/raw
            subcategory = topic_parts[2] if len(topic_parts) >= 3 else 'filtered'
            try:
                weight_pounds = float(payload)
                # Convert weight to fuel volume (assuming diesel fuel density ~7.2 lbs/gallon)
                fuel_gallons = weight_pounds / 7.2
                
                points.append(
                    Point("monitor_fuel")
                    .tag("type", subcategory)
                    .field("pounds", weight_pounds)  # Keep original weight
                    .field("gallons", fuel_gallons)  # Add fuel volume
                    .time(timestamp, WritePrecision.NS)
                )
            except ValueError:
                if subcategory == 'status':
                    # Parse fuel status from weight status message
                    parsed_fuel = self._parse_fuel_status(payload, timestamp)
                    if parsed_fuel:
                        points.extend(parsed_fuel)
                    
                    points.append(
                        Point("monitor_fuel")
                        .tag("type", "status")
                        .field("status", payload)
                        .time(timestamp, WritePrecision.NS)
                    )
                    
        elif category == 'power':
            # Power monitoring: monitor/power/voltage, monitor/power/current, etc.
            if len(topic_parts) >= 3:
                metric = topic_parts[2]
                try:
                    value = float(payload)
                    field_name = metric
                    if metric == 'watts':
                        field_name = 'power'
                    
                    points.append(
                        Point("monitor_power")
                        .tag("metric", metric)
                        .field(field_name, value)
                        .time(timestamp, WritePrecision.NS)
                    )
                except ValueError:
                    if metric == 'status':
                        points.append(
                            Point("monitor_power")
                            .field("status", payload)
                            .time(timestamp, WritePrecision.NS)
                        )
                        
        elif category == 'input':
            # Digital inputs: monitor/input/2, monitor/input/3, etc.
            if len(topic_parts) >= 3:
                pin = topic_parts[2]
                state = int(payload) if payload.isdigit() else 0
                points.append(
                    Point("monitor_input")
                    .tag("pin", pin)
                    .field("state", state)
                    .time(timestamp, WritePrecision.NS)
                )
                
        elif category == 'bridge':
            # Serial bridge status: monitor/bridge/status
            points.append(
                Point("monitor_bridge")
                .field("status", payload)
                .time(timestamp, WritePrecision.NS)
            )
            
        elif category in ['status', 'heartbeat', 'uptime', 'memory', 'error']:
            # System metrics: monitor/status, monitor/heartbeat, etc.
            try:
                # Try to parse as number first
                value = float(payload)
                points.append(
                    Point("monitor_system")
                    .tag("metric", category)
                    .field("value", value)
                    .time(timestamp, WritePrecision.NS)
                )
            except ValueError:
                # Store as string
                points.append(
                    Point("monitor_system")
                    .tag("metric", category)
                    .field("message", payload)
                    .time(timestamp, WritePrecision.NS)
                )
                
                # Parse monitor status messages
                if category == 'status':
                    parsed_points = self._parse_monitor_status(payload, timestamp)
                    points.extend(parsed_points)
                
        return points
    
    def _parse_pressure_data(self, data: str) -> Dict[str, float]:
        """Parse pressure data string like 'A1=245.2psi A5=12.1psi'"""
        pressure_values = {}
        
        # Pattern to match "A1=245.2psi" format
        pattern = r'([A-Z]\d+)=([0-9.]+)psi'
        matches = re.findall(pattern, data)
        
        for sensor, value in matches:
            try:
                pressure_values[sensor] = float(value)
            except ValueError:
                pass
                
        return pressure_values
    
    def _parse_status_message(self, message: str, timestamp: datetime) -> list:
        """Parse status messages and extract structured data for dashboards"""
        points = []
        
        # E-Stop Status Detection
        if "E-STOP ACTIVATED" in message:
            points.append(
                Point("controller_estop")
                .field("active", True)
                .field("message", message)
                .time(timestamp, WritePrecision.NS)
            )
            
        # Engine Status Detection 
        if "Engine stopped" in message or "SAFETY: Engine stopped" in message:
            points.append(
                Point("controller_engine")
                .field("running", False)
                .field("stopped", True)
                .field("message", message)
                .time(timestamp, WritePrecision.NS)
            )
        elif "Engine started" in message or "Engine running" in message:
            points.append(
                Point("controller_engine")
                .field("running", True)
                .field("stopped", False)
                .field("message", message)
                .time(timestamp, WritePrecision.NS)
            )
            
        # System Status Parsing: "System: uptime=3630s state=IDLE"
        system_match = re.search(r'System:\s+uptime=(\d+)s\s+state=(\w+)', message)
        if system_match:
            uptime = int(system_match.group(1))
            state = system_match.group(2)
            
            points.append(
                Point("controller_system_parsed")
                .tag("state", state)
                .field("uptime_seconds", uptime)
                .field("active", True)
                .field("state_idle", 1 if state == "IDLE" else 0)
                .field("state_running", 1 if state == "RUNNING" else 0)
                .field("state_error", 1 if state == "ERROR" else 0)
                .time(timestamp, WritePrecision.NS)
            )
            
        # Sequence State Detection: "EXTENDING->WAIT_EXTEND_LIMIT", "RETRACTING->IDLE", etc.
        sequence_states = ["IDLE", "START_WAIT", "EXTENDING", "WAIT_EXTEND_LIMIT", 
                          "RETRACTING", "WAIT_RETRACT_LIMIT", "ERROR", "TIMEOUT"]
        
        for state in sequence_states:
            if state in message and ("->" in message or message.endswith(state)):
                # Extract transition if present: "EXTENDING->WAIT_EXTEND_LIMIT"
                if "->" in message:
                    transition_match = re.search(rf'(\w+)->(\w+)', message)
                    if transition_match:
                        from_state = transition_match.group(1)
                        to_state = transition_match.group(2)
                        
                        points.append(
                            Point("controller_sequence_parsed")
                            .tag("from_state", from_state)
                            .tag("to_state", to_state)
                            .tag("current_state", to_state)
                            .field("active", 1)
                            .field("transitioning", True)
                            .field("idle", 1 if to_state == "IDLE" else 0)
                            .field("extending", 1 if "EXTEND" in to_state else 0)
                            .field("retracting", 1 if "RETRACT" in to_state else 0)
                            .field("waiting", 1 if "WAIT" in to_state else 0)
                            .time(timestamp, WritePrecision.NS)
                        )
                        break
                else:
                    # Single state
                    points.append(
                        Point("controller_sequence_parsed")
                        .tag("current_state", state)
                        .field("active", 1)
                        .field("transitioning", False)
                        .field("idle", 1 if state == "IDLE" else 0)
                        .field("extending", 1 if "EXTEND" in state else 0)
                        .field("retracting", 1 if "RETRACT" in state else 0)
                        .field("waiting", 1 if "WAIT" in state else 0)
                        .time(timestamp, WritePrecision.NS)
                    )
                    break
                    
        # Safety Events Detection
        if any(keyword in message.lower() for keyword in ["safety", "emergency", "fault", "alarm"]):
            points.append(
                Point("controller_safety_events")
                .field("event", message)
                .field("critical", "critical" in message.lower() or "emergency" in message.lower())
                .field("warning", "warning" in message.lower() or "warn" in message.lower())
                .time(timestamp, WritePrecision.NS)
            )
            
        # Pressure Safety Detection
        if "pressure" in message.lower() and any(word in message.lower() for word in ["high", "low", "limit", "safety"]):
            points.append(
                Point("controller_pressure_safety")
                .field("event", message)
                .field("high_pressure", "high" in message.lower())
                .field("low_pressure", "low" in message.lower())
                .field("pressure_limit", "limit" in message.lower())
                .time(timestamp, WritePrecision.NS)
            )
            
        return points
    
    def _parse_monitor_status(self, message: str, timestamp: datetime) -> list:
        """Parse monitor status messages for structured data"""
        points = []
        
        # Monitor system status parsing
        # Example: "Monitor: sensors=OK weight=calibrated temp=72.5F uptime=1234s"
        
        # Extract individual status components
        if "sensors=" in message:
            sensors_match = re.search(r'sensors=(\w+)', message)
            if sensors_match:
                status = sensors_match.group(1)
                points.append(
                    Point("monitor_sensors_status")
                    .field("status", status)
                    .field("ok", status.lower() == "ok")
                    .field("error", status.lower() == "error")
                    .time(timestamp, WritePrecision.NS)
                )
                
        if "weight=" in message:
            weight_match = re.search(r'weight=(\w+)', message)
            if weight_match:
                status = weight_match.group(1)
                points.append(
                    Point("monitor_weight_status")
                    .field("status", status)
                    .field("calibrated", status.lower() == "calibrated")
                    .field("error", status.lower() == "error")
                    .time(timestamp, WritePrecision.NS)
                )
                
        if "temp=" in message:
            temp_match = re.search(r'temp=([0-9.]+)F', message)
            if temp_match:
                temp_value = float(temp_match.group(1))
                points.append(
                    Point("monitor_temperature_parsed")
                    .field("fahrenheit", temp_value)
                    .field("celsius", (temp_value - 32) * 5/9)
                    .field("normal", 50 <= temp_value <= 150)
                    .time(timestamp, WritePrecision.NS)
                )
                
        if "uptime=" in message:
            uptime_match = re.search(r'uptime=(\d+)s', message)
            if uptime_match:
                uptime_seconds = int(uptime_match.group(1))
                points.append(
                    Point("monitor_uptime_parsed")
                    .field("seconds", uptime_seconds)
                    .field("minutes", uptime_seconds / 60)
                    .field("hours", uptime_seconds / 3600)
                    .time(timestamp, WritePrecision.NS)
                )
                
        # LCD and display status
        if any(keyword in message.lower() for keyword in ["lcd", "display", "backlight"]):
            points.append(
                Point("monitor_display_status")
                .field("status", message)
                .field("lcd_on", "on" in message.lower())
                .field("backlight_on", "backlight" in message.lower() and "on" in message.lower())
                .time(timestamp, WritePrecision.NS)
            )
            
        # Heartbeat animation status
        if "heartbeat" in message.lower():
            points.append(
                Point("monitor_heartbeat_status")
                .field("status", message)
                .field("active", "active" in message.lower() or "on" in message.lower())
                .field("rate_bpm", self._extract_number_from_text(message, r'(\d+)\s*bpm'))
                .field("brightness", self._extract_number_from_text(message, r'brightness[=:\s]*(\d+)'))
                .time(timestamp, WritePrecision.NS)
            )
            
        return points
    
    def _extract_number_from_text(self, text: str, pattern: str) -> Optional[float]:
        """Extract a number from text using regex pattern"""
        match = re.search(pattern, text.lower())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None
    
    def _parse_fuel_status(self, message: str, timestamp: datetime) -> list:
        """Parse fuel/weight status messages for structured data"""
        points = []
        
        # Parse status message: "status: OK, ready: NO, weight: 24328.602, raw: 1656116"
        weight_match = re.search(r'weight:\s*([0-9.]+)', message)
        ready_match = re.search(r'ready:\s*(\w+)', message)
        status_match = re.search(r'status:\s*(\w+)', message)
        raw_match = re.search(r'raw:\s*([0-9.]+)', message)
        
        if weight_match:
            weight_pounds = float(weight_match.group(1))
            fuel_gallons = weight_pounds / 7.2  # Convert to fuel volume
            
            points.append(
                Point("monitor_fuel_parsed")
                .field("weight_pounds", weight_pounds)
                .field("fuel_gallons", fuel_gallons)
                .field("fuel_ready", ready_match.group(1).upper() == "YES" if ready_match else False)
                .field("sensor_ok", status_match.group(1).upper() == "OK" if status_match else False)
                .field("raw_reading", float(raw_match.group(1)) if raw_match else None)
                .field("fuel_level_percent", min(100, max(0, (fuel_gallons / 500) * 100)))  # Assuming 500 gal tank
                .time(timestamp, WritePrecision.NS)
            )
            
        return points
    
    def print_stats(self):
        """Print collection statistics"""
        uptime = datetime.now() - self.stats['start_time']
        print(f"\n=== LogSplitter InfluxDB Collector Stats ===")
        print(f"Uptime: {uptime}")
        print(f"Messages received: {self.stats['messages_received']}")
        print(f"Messages written: {self.stats['messages_written']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"Rate: {self.stats['messages_received'] / uptime.total_seconds():.1f} msg/sec")
    
    def run(self):
        """Main collection loop"""
        if not self.connect_influxdb():
            return False
            
        if not self.connect_mqtt():
            return False
        
        self.logger.info("LogSplitter InfluxDB collector started")
        
        try:
            # Start MQTT loop
            self.mqtt_client.loop_start()
            
            # Print stats periodically
            last_stats = time.time()
            
            while True:
                time.sleep(1)
                
                # Print stats every 60 seconds
                if time.time() - last_stats > 60:
                    self.print_stats()
                    last_stats = time.time()
                    
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            self.print_stats()
            
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
            "log_level": "INFO"
        }


def main():
    """Main entry point"""
    config = load_config()
    
    collector = LogSplitterInfluxCollector(config)
    
    try:
        success = collector.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()