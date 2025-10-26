#!/usr/bin/env python3
"""
LogSplitter Monitor & Controller Web Dashboard with InfluxDB Integration
Combines MQTT collection, InfluxDB storage, and real-time web dashboard in one application.

Features:
- MQTT to InfluxDB data collection with smart parsing
- Real-time web dashboard with live updates
- Safety monitoring and alerts
- Fuel volume tracking and conversion
- System status and health monitoring
- Interactive charts and gauges
"""

import json
import logging
import sys
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import re

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import plotly
import plotly.graph_objs as go
import plotly.utils
import pandas as pd


class LogSplitterWebCollector:
    """Combined MQTT collector and web dashboard for LogSplitter monitoring"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.influx_client = None
        self.write_api = None
        self.mqtt_client = None
        
        # Flask app setup
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'logsplitter-secret-key-2025'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.get('log_level', 'INFO').upper()),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Statistics and real-time data
        self.stats = {
            'messages_received': 0,
            'messages_written': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        # Real-time data cache for dashboard
        self.live_data = {
            'controller': {
                'estop_active': False,
                'engine_running': False,
                'system_state': 'UNKNOWN',
                'uptime': 0,
                'pressure_a1': 0.0,
                'pressure_a5': 0.0,
                'sequence_state': 'IDLE',
                'last_update': None
            },
            'monitor': {
                'fuel_gallons': 0.0,
                'fuel_pounds': 0.0,
                'fuel_percent': 0.0,
                'temperature_local': 0.0,
                'temperature_remote': 0.0,
                'sensors_ok': True,
                'weight_calibrated': True,
                'uptime': 0,
                'last_update': None
            },
            'alerts': [],
            'recent_events': []
        }
        
        # Setup Flask routes
        self._setup_routes()
        self._setup_socketio()
        
    def _setup_routes(self):
        """Setup Flask web routes"""
        
        @self.app.route('/')
        def dashboard():
            """Main dashboard page"""
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def api_status():
            """API endpoint for current system status"""
            return jsonify({
                'controller': self.live_data['controller'],
                'monitor': self.live_data['monitor'],
                'alerts': self.live_data['alerts'][-10:],  # Last 10 alerts
                'stats': self.stats,
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/api/pressure/history')
        def api_pressure_history():
            """Get pressure history from InfluxDB"""
            hours = request.args.get('hours', 1, type=int)
            try:
                query = f'''
                from(bucket: "{self.config['influxdb']['bucket']}")
                  |> range(start: -{hours}h)
                  |> filter(fn: (r) => r._measurement == "controller_pressure")
                  |> filter(fn: (r) => r._field == "psi")
                  |> group(columns: ["sensor"])
                '''
                
                result = self.influx_client.query_api().query(query)
                
                data = {'A1': [], 'A5': []}
                for table in result:
                    for record in table.records:
                        sensor = record.values.get('sensor', 'Unknown')
                        if sensor in data:
                            data[sensor].append({
                                'time': record.get_time().isoformat(),
                                'value': record.get_value()
                            })
                
                return jsonify(data)
                
            except Exception as e:
                self.logger.error(f"Error querying pressure history: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/fuel/history')
        def api_fuel_history():
            """Get fuel volume history from InfluxDB"""
            hours = request.args.get('hours', 6, type=int)
            try:
                query = f'''
                from(bucket: "{self.config['influxdb']['bucket']}")
                  |> range(start: -{hours}h)
                  |> filter(fn: (r) => r._measurement == "monitor_fuel")
                  |> filter(fn: (r) => r._field == "gallons")
                  |> last()
                '''
                
                result = self.influx_client.query_api().query(query)
                
                data = []
                for table in result:
                    for record in table.records:
                        data.append({
                            'time': record.get_time().isoformat(),
                            'gallons': record.get_value(),
                            'pounds': record.values.get('pounds', 0)
                        })
                
                return jsonify(data)
                
            except Exception as e:
                self.logger.error(f"Error querying fuel history: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/events/recent')
        def api_recent_events():
            """Get recent system events"""
            hours = request.args.get('hours', 2, type=int)
            try:
                query = f'''
                from(bucket: "{self.config['influxdb']['bucket']}")
                  |> range(start: -{hours}h)
                  |> filter(fn: (r) => r._measurement == "controller_log")
                  |> filter(fn: (r) => r._field == "message")
                  |> sort(columns: ["_time"], desc: true)
                  |> limit(n: 50)
                '''
                
                result = self.influx_client.query_api().query(query)
                
                events = []
                for table in result:
                    for record in table.records:
                        events.append({
                            'time': record.get_time().isoformat(),
                            'level': record.values.get('level', 'info'),
                            'message': record.get_value()
                        })
                
                return jsonify(events)
                
            except Exception as e:
                self.logger.error(f"Error querying recent events: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/safety')
        def safety_dashboard():
            """Safety monitoring dashboard"""
            return render_template('safety.html')
        
        @self.app.route('/fuel')
        def fuel_dashboard():
            """Fuel monitoring dashboard"""
            return render_template('fuel.html')
        
        @self.app.route('/system')
        def system_dashboard():
            """System health dashboard"""
            return render_template('system.html')
        
    def _setup_socketio(self):
        """Setup SocketIO for real-time updates"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Client connected"""
            self.logger.info(f"Client connected: {request.sid}")
            # Send current status immediately
            emit('status_update', {
                'controller': self.live_data['controller'],
                'monitor': self.live_data['monitor'],
                'alerts': self.live_data['alerts'][-5:]
            })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client disconnected"""
            self.logger.info(f"Client disconnected: {request.sid}")
        
        @self.socketio.on('request_chart_data')
        def handle_chart_request(data):
            """Handle request for chart data"""
            chart_type = data.get('type', 'pressure')
            hours = data.get('hours', 1)
            
            try:
                if chart_type == 'pressure':
                    chart_data = self._get_pressure_chart_data(hours)
                elif chart_type == 'fuel':
                    chart_data = self._get_fuel_chart_data(hours)
                elif chart_type == 'temperature':
                    chart_data = self._get_temperature_chart_data(hours)
                else:
                    chart_data = {'error': 'Unknown chart type'}
                
                emit('chart_data', {
                    'type': chart_type,
                    'data': chart_data
                })
                
            except Exception as e:
                emit('chart_data', {
                    'type': chart_type,
                    'error': str(e)
                })
    
    def _get_pressure_chart_data(self, hours: int) -> Dict:
        """Generate pressure chart data"""
        try:
            query = f'''
            from(bucket: "{self.config['influxdb']['bucket']}")
              |> range(start: -{hours}h)
              |> filter(fn: (r) => r._measurement == "controller_pressure")
              |> filter(fn: (r) => r._field == "psi")
              |> group(columns: ["sensor"])
            '''
            
            result = self.influx_client.query_api().query(query)
            
            traces = []
            for table in result:
                times = []
                values = []
                sensor = None
                
                for record in table.records:
                    if sensor is None:
                        sensor = record.values.get('sensor', 'Unknown')
                    times.append(record.get_time())
                    values.append(record.get_value())
                
                if times:
                    trace = go.Scatter(
                        x=times,
                        y=values,
                        mode='lines+markers',
                        name=f'{sensor} Pressure',
                        line=dict(width=3),
                        marker=dict(size=4)
                    )
                    traces.append(trace)
            
            layout = go.Layout(
                title=f'Hydraulic Pressure - Last {hours}h',
                xaxis=dict(title='Time'),
                yaxis=dict(title='Pressure (PSI)'),
                hovermode='closest',
                showlegend=True
            )
            
            fig = go.Figure(data=traces, layout=layout)
            return json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))
            
        except Exception as e:
            self.logger.error(f"Error generating pressure chart: {e}")
            return {'error': str(e)}
    
    def _get_fuel_chart_data(self, hours: int) -> Dict:
        """Generate fuel volume chart data"""
        try:
            query = f'''
            from(bucket: "{self.config['influxdb']['bucket']}")
              |> range(start: -{hours}h)
              |> filter(fn: (r) => r._measurement == "monitor_fuel")
              |> filter(fn: (r) => r._field == "gallons")
            '''
            
            result = self.influx_client.query_api().query(query)
            
            times = []
            gallons = []
            
            for table in result:
                for record in table.records:
                    times.append(record.get_time())
                    gallons.append(record.get_value())
            
            if times:
                trace = go.Scatter(
                    x=times,
                    y=gallons,
                    mode='lines+markers',
                    name='Fuel Volume',
                    line=dict(width=3, color='orange'),
                    fill='tonexty',
                    fillcolor='rgba(255, 165, 0, 0.2)'
                )
                
                layout = go.Layout(
                    title=f'Fuel Volume - Last {hours}h',
                    xaxis=dict(title='Time'),
                    yaxis=dict(title='Fuel (Gallons)'),
                    hovermode='closest'
                )
                
                fig = go.Figure(data=[trace], layout=layout)
                return json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))
            
            return {'error': 'No fuel data available'}
            
        except Exception as e:
            self.logger.error(f"Error generating fuel chart: {e}")
            return {'error': str(e)}
    
    def _get_temperature_chart_data(self, hours: int) -> Dict:
        """Generate temperature chart data"""
        try:
            query = f'''
            from(bucket: "{self.config['influxdb']['bucket']}")
              |> range(start: -{hours}h)
              |> filter(fn: (r) => r._measurement == "monitor_temperature")
              |> filter(fn: (r) => r._field == "fahrenheit")
              |> group(columns: ["sensor"])
            '''
            
            result = self.influx_client.query_api().query(query)
            
            traces = []
            colors = {'local': 'blue', 'remote': 'red'}
            
            for table in result:
                times = []
                values = []
                sensor = None
                
                for record in table.records:
                    if sensor is None:
                        sensor = record.values.get('sensor', 'unknown')
                    times.append(record.get_time())
                    values.append(record.get_value())
                
                if times:
                    trace = go.Scatter(
                        x=times,
                        y=values,
                        mode='lines+markers',
                        name=f'{sensor.title()} Temperature',
                        line=dict(width=3, color=colors.get(sensor, 'gray')),
                        marker=dict(size=4)
                    )
                    traces.append(trace)
            
            layout = go.Layout(
                title=f'Temperature Monitoring - Last {hours}h',
                xaxis=dict(title='Time'),
                yaxis=dict(title='Temperature (°F)'),
                hovermode='closest',
                showlegend=True
            )
            
            fig = go.Figure(data=traces, layout=layout)
            return json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))
            
        except Exception as e:
            self.logger.error(f"Error generating temperature chart: {e}")
            return {'error': str(e)}
    
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
            
            # Update live data cache
            self._update_live_data(topic, payload, timestamp)
            
            # Parse and write to InfluxDB
            points = self._parse_message(topic, payload, timestamp)
            if points:
                self.write_api.write(
                    bucket=self.config['influxdb']['bucket'],
                    org=self.config['influxdb']['org'],
                    record=points
                )
                self.stats['messages_written'] += len(points)
                
                # Emit real-time updates via SocketIO
                self._emit_live_updates(topic, payload, timestamp)
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error processing message {topic}: {e}")
    
    def _update_live_data(self, topic: str, payload: str, timestamp: datetime):
        """Update live data cache for real-time dashboard"""
        topic_parts = topic.split('/')
        
        if len(topic_parts) >= 2:
            system = topic_parts[0]  # 'controller' or 'monitor'
            category = topic_parts[1]
            
            if system == 'controller':
                if category == 'pressure' and len(topic_parts) >= 3:
                    sensor = topic_parts[2].lower()
                    try:
                        value = float(payload)
                        if sensor == 'a1':
                            self.live_data['controller']['pressure_a1'] = value
                        elif sensor == 'a5':
                            self.live_data['controller']['pressure_a5'] = value
                    except ValueError:
                        pass
                
                elif category == 'sequence':
                    self.live_data['controller']['sequence_state'] = payload
                
                elif category == 'raw' and 'E-STOP' in payload:
                    self.live_data['controller']['estop_active'] = 'ACTIVATED' in payload
                    if 'ACTIVATED' in payload:
                        self._add_alert('critical', 'E-STOP ACTIVATED!', timestamp)
                
                elif category == 'raw' and 'Engine' in payload:
                    self.live_data['controller']['engine_running'] = 'started' in payload or 'running' in payload
                
                # Parse system status
                if 'uptime=' in payload and 'state=' in payload:
                    uptime_match = re.search(r'uptime=(\d+)s', payload)
                    state_match = re.search(r'state=(\w+)', payload)
                    if uptime_match:
                        self.live_data['controller']['uptime'] = int(uptime_match.group(1))
                    if state_match:
                        self.live_data['controller']['system_state'] = state_match.group(1)
                
                self.live_data['controller']['last_update'] = timestamp.isoformat()
            
            elif system == 'monitor':
                if category == 'weight':
                    try:
                        weight_pounds = float(payload)
                        fuel_gallons = weight_pounds / 7.2
                        fuel_percent = min(100, max(0, (fuel_gallons / 500) * 100))  # Assume 500 gal tank
                        
                        self.live_data['monitor']['fuel_pounds'] = weight_pounds
                        self.live_data['monitor']['fuel_gallons'] = fuel_gallons
                        self.live_data['monitor']['fuel_percent'] = fuel_percent
                    except ValueError:
                        pass
                
                elif category == 'temperature' and len(topic_parts) >= 3:
                    sensor = topic_parts[2]
                    try:
                        value = float(payload)
                        if sensor == 'local':
                            self.live_data['monitor']['temperature_local'] = value
                        elif sensor == 'remote':
                            self.live_data['monitor']['temperature_remote'] = value
                    except ValueError:
                        pass
                
                # Parse monitor status
                if 'sensors=' in payload:
                    self.live_data['monitor']['sensors_ok'] = 'OK' in payload
                if 'weight=' in payload:
                    self.live_data['monitor']['weight_calibrated'] = 'calibrated' in payload
                if 'uptime=' in payload:
                    uptime_match = re.search(r'uptime=(\d+)s', payload)
                    if uptime_match:
                        self.live_data['monitor']['uptime'] = int(uptime_match.group(1))
                
                self.live_data['monitor']['last_update'] = timestamp.isoformat()
    
    def _add_alert(self, level: str, message: str, timestamp: datetime):
        """Add alert to live data"""
        alert = {
            'level': level,
            'message': message,
            'timestamp': timestamp.isoformat()
        }
        
        self.live_data['alerts'].append(alert)
        
        # Keep only last 50 alerts
        if len(self.live_data['alerts']) > 50:
            self.live_data['alerts'] = self.live_data['alerts'][-50:]
    
    def _emit_live_updates(self, topic: str, payload: str, timestamp: datetime):
        """Emit real-time updates via SocketIO"""
        # Emit status update to all connected clients
        self.socketio.emit('status_update', {
            'controller': self.live_data['controller'],
            'monitor': self.live_data['monitor'],
            'latest_message': {
                'topic': topic,
                'payload': payload,
                'timestamp': timestamp.isoformat()
            }
        })
        
        # Emit specific alerts
        if self.live_data['controller']['estop_active']:
            self.socketio.emit('alert', {
                'level': 'critical',
                'message': 'E-STOP ACTIVE - System Halted',
                'timestamp': timestamp.isoformat()
            })
    
    def _parse_message(self, topic: str, payload: str, timestamp: datetime) -> list:
        """Parse MQTT message and convert to InfluxDB points - same as original collector"""
        # [Include all the parsing logic from the original collector]
        # This would be the same _parse_message method from logsplitter_influx_collector.py
        # For brevity, I'll add a placeholder here
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
            
        elif category == 'system':
            # System status: controller/system/status
            points.append(
                Point("controller_system")
                .field("status", payload)
                .field("active", 1)
                .time(timestamp, WritePrecision.NS)
            )
            
            # Parse uptime from system messages
            uptime_match = re.search(r'uptime=(\d+)s', payload)
            if uptime_match:
                uptime_seconds = int(uptime_match.group(1))
                points.append(
                    Point("controller_system")
                    .field("uptime", uptime_seconds)
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
                
        return points
    
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
    
    def start_mqtt_thread(self):
        """Start MQTT collection in background thread"""
        def mqtt_worker():
            if not self.connect_influxdb():
                return
                
            if not self.connect_mqtt():
                return
            
            self.logger.info("MQTT collector thread started")
            self.mqtt_client.loop_forever()
        
        mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
        mqtt_thread.start()
        return mqtt_thread
    
    def run_web_server(self, host='0.0.0.0', port=5000, debug=False):
        """Run the Flask web server"""
        self.logger.info(f"Starting web dashboard on http://{host}:{port}")
        
        # Start MQTT collection in background
        self.start_mqtt_thread()
        
        # Run Flask app with SocketIO
        self.socketio.run(
            self.app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
        )


def load_config(config_file: str = 'config.json') -> Dict[str, Any]:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        # Add web server config if not present
        if 'web' not in config:
            config['web'] = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False
            }
            
        return config
        
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
                "port": 5000,
                "debug": False
            },
            "log_level": "INFO"
        }


def main():
    """Main entry point"""
    config = load_config()
    
    collector = LogSplitterWebCollector(config)
    
    try:
        # Run web server (includes MQTT collection)
        collector.run_web_server(
            host=config['web']['host'],
            port=config['web']['port'],
            debug=config['web']['debug']
        )
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()