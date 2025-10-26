#!/usr/bin/env python3
"""
InfluxDB Data Verification and Dashboard Generator
Queries the LogSplitter InfluxDB to verify data formats and generate comprehensive dashboards.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
import argparse

try:
    from influxdb_client import InfluxDBClient
    from influxdb_client.client.query_api import QueryApi
except ImportError:
    print("ERROR: influxdb-client not installed. Run: pip install influxdb-client")
    sys.exit(1)

class InfluxDataVerifier:
    """Verifies InfluxDB data structure and generates Grafana dashboards"""
    
    def __init__(self, config_file: str = "config.json"):
        """Initialize with configuration"""
        try:
            with open(config_file, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Config file {config_file} not found")
            sys.exit(1)
        
        self.client = None
        self.query_api = None
        
    def connect(self) -> bool:
        """Connect to InfluxDB"""
        try:
            self.client = InfluxDBClient(
                url=self.config['influxdb']['url'],
                token=self.config['influxdb']['token'],
                org=self.config['influxdb']['org']
            )
            self.query_api = self.client.query_api()
            
            # Test connection
            buckets = self.client.buckets_api().find_buckets()
            print(f"✅ Connected to InfluxDB at {self.config['influxdb']['url']}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to InfluxDB: {e}")
            return False
    
    def verify_data_structure(self) -> Dict[str, Any]:
        """Verify the actual data structure in InfluxDB"""
        bucket = self.config['influxdb']['bucket']
        
        print(f"\n📊 Analyzing data in bucket: {bucket}")
        print("=" * 60)
        
        # Query to get all measurements
        measurements_query = f'''
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{bucket}")
        '''
        
        try:
            measurements_result = self.query_api.query(measurements_query)
            measurements = []
            for table in measurements_result:
                for record in table.records:
                    measurements.append(record.get_value())
            
            print(f"📋 Found {len(measurements)} measurements:")
            for m in sorted(measurements):
                print(f"  • {m}")
            
            # Analyze each measurement
            data_structure = {}
            for measurement in measurements:
                print(f"\n🔍 Analyzing measurement: {measurement}")
                structure = self._analyze_measurement(bucket, measurement)
                data_structure[measurement] = structure
                
            return data_structure
            
        except Exception as e:
            print(f"❌ Error querying measurements: {e}")
            return {}
    
    def _analyze_measurement(self, bucket: str, measurement: str) -> Dict[str, Any]:
        """Analyze a specific measurement"""
        # Get fields for this measurement
        fields_query = f'''
        import "influxdata/influxdb/schema"
        schema.measurementFieldKeys(
            bucket: "{bucket}",
            measurement: "{measurement}"
        )
        '''
        
        # Get tags for this measurement  
        tags_query = f'''
        import "influxdata/influxdb/schema"
        schema.measurementTagKeys(
            bucket: "{bucket}",
            measurement: "{measurement}"
        )
        '''
        
        # Get recent sample data
        sample_query = f'''
        from(bucket: "{bucket}")
        |> range(start: -24h)
        |> filter(fn: (r) => r._measurement == "{measurement}")
        |> limit(n: 5)
        '''
        
        structure = {
            'fields': [],
            'tags': [],
            'sample_data': [],
            'record_count': 0
        }
        
        try:
            # Get fields
            fields_result = self.query_api.query(fields_query)
            for table in fields_result:
                for record in table.records:
                    structure['fields'].append(record.get_value())
            
            # Get tags
            tags_result = self.query_api.query(tags_query)
            for table in tags_result:
                for record in table.records:
                    structure['tags'].append(record.get_value())
            
            # Get sample data
            sample_result = self.query_api.query(sample_query)
            for table in sample_result:
                for record in table.records:
                    structure['record_count'] += 1
                    if len(structure['sample_data']) < 3:  # Limit samples
                        sample = {
                            'time': record.get_time(),
                            'field': record.get_field(),
                            'value': record.get_value(),
                            'tags': {k: v for k, v in record.values.items() if k not in ['_time', '_field', '_value', '_measurement', '_start', '_stop']}
                        }
                        structure['sample_data'].append(sample)
            
            print(f"    Fields: {structure['fields']}")
            print(f"    Tags: {structure['tags']}")
            print(f"    Records (24h): {structure['record_count']}")
            
            if structure['sample_data']:
                print(f"    Sample data:")
                for i, sample in enumerate(structure['sample_data']):
                    print(f"      {i+1}. {sample['field']}={sample['value']} {sample['tags']} @ {sample['time']}")
            
            return structure
            
        except Exception as e:
            print(f"    ❌ Error analyzing {measurement}: {e}")
            return structure
    
    def generate_dashboards(self, data_structure: Dict[str, Any]) -> None:
        """Generate comprehensive Grafana dashboards based on actual data"""
        
        dashboards = [
            self._create_system_overview_dashboard(data_structure),
            self._create_controller_dashboard(data_structure),
            self._create_monitor_dashboard(data_structure),
            self._create_safety_dashboard(data_structure),
            self._create_maintenance_dashboard(data_structure)
        ]
        
        for dashboard in dashboards:
            filename = f"grafana_{dashboard['title'].lower().replace(' ', '_')}.json"
            with open(filename, 'w') as f:
                json.dump(dashboard, f, indent=2)
            print(f"📄 Created dashboard: {filename}")
    
    def _create_system_overview_dashboard(self, data_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Create system overview dashboard"""
        dashboard = {
            "annotations": {"list": []},
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "liveNow": False,
            "panels": [],
            "refresh": "5s",
            "schemaVersion": 36,
            "style": "dark",
            "tags": ["logsplitter", "overview"],
            "templating": {"list": []},
            "time": {"from": "now-6h", "to": "now"},
            "timepicker": {},
            "timezone": "browser",
            "title": "LogSplitter System Overview",
            "uid": "logsplitter-overview",
            "version": 1,
            "weekStart": ""
        }
        
        panel_id = 1
        y_pos = 0
        
        # Add pressure panel if controller_pressure exists
        if 'controller_pressure' in data_structure:
            pressure_panel = self._create_timeseries_panel(
                panel_id, "System Pressure", 0, y_pos, 12, 8,
                f'from(bucket: "mqtt") |> range(start: -6h) |> filter(fn: (r) => r._measurement == "controller_pressure") |> filter(fn: (r) => r._field == "psi")',
                unit="psi", max_value=5000
            )
            dashboard["panels"].append(pressure_panel)
            panel_id += 1
        
        # Add temperature panel if monitor_temperature exists
        if 'monitor_temperature' in data_structure:
            temp_panel = self._create_timeseries_panel(
                panel_id, "Temperature Monitoring", 12, y_pos, 12, 8,
                f'from(bucket: "mqtt") |> range(start: -6h) |> filter(fn: (r) => r._measurement == "monitor_temperature") |> filter(fn: (r) => r._field == "fahrenheit")',
                unit="fahrenheit"
            )
            dashboard["panels"].append(temp_panel)
            panel_id += 1
        
        y_pos += 8
        
        # Add relay status if controller_relay exists
        if 'controller_relay' in data_structure:
            relay_panel = self._create_stat_panel(
                panel_id, "Relay Status", 0, y_pos, 8, 4,
                f'from(bucket: "mqtt") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "controller_relay") |> filter(fn: (r) => r._field == "active") |> last()',
                mappings=[{"options": {"0": {"text": "OFF", "color": "gray"}, "1": {"text": "ON", "color": "green"}}, "type": "value"}]
            )
            dashboard["panels"].append(relay_panel)
            panel_id += 1
        
        # Add weight gauge if monitor_weight exists
        if 'monitor_weight' in data_structure:
            weight_panel = self._create_gauge_panel(
                panel_id, "Current Weight", 8, y_pos, 8, 4,
                f'from(bucket: "mqtt") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "monitor_weight") |> filter(fn: (r) => r._field == "pounds") |> last()',
                min_val=0, max_val=200, unit="short"
            )
            dashboard["panels"].append(weight_panel)
            panel_id += 1
        
        # Add sequence status if controller_sequence exists
        if 'controller_sequence' in data_structure:
            seq_panel = self._create_stat_panel(
                panel_id, "Sequence Status", 16, y_pos, 8, 4,
                f'from(bucket: "mqtt") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "controller_sequence") |> filter(fn: (r) => r._field == "active") |> last()',
                mappings=[{"options": {"0": {"text": "IDLE", "color": "gray"}, "1": {"text": "ACTIVE", "color": "green"}}, "type": "value"}]
            )
            dashboard["panels"].append(seq_panel)
            panel_id += 1
        
        return dashboard
    
    def _create_controller_dashboard(self, data_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Create controller-specific dashboard"""
        dashboard = {
            "annotations": {"list": []},
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "liveNow": False,
            "panels": [],
            "refresh": "5s",
            "schemaVersion": 36,
            "style": "dark",
            "tags": ["logsplitter", "controller"],
            "templating": {"list": []},
            "time": {"from": "now-2h", "to": "now"},
            "timepicker": {},
            "timezone": "browser",
            "title": "LogSplitter Controller Dashboard",
            "uid": "logsplitter-controller",
            "version": 1,
            "weekStart": ""
        }
        
        panel_id = 1
        y_pos = 0
        
        # Pressure monitoring with thresholds
        if 'controller_pressure' in data_structure:
            pressure_panel = self._create_timeseries_panel(
                panel_id, "Hydraulic Pressure (A1/A5 Sensors)", 0, y_pos, 24, 8,
                f'from(bucket: "mqtt") |> range(start: -2h) |> filter(fn: (r) => r._measurement == "controller_pressure") |> filter(fn: (r) => r._field == "psi") |> group(columns: ["sensor"])',
                unit="psi", max_value=5000,
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 2500},
                    {"color": "red", "value": 4000}
                ]
            )
            dashboard["panels"].append(pressure_panel)
            panel_id += 1
            y_pos += 8
        
        # Relay control status
        if 'controller_relay' in data_structure:
            relay_panel = self._create_stat_panel(
                panel_id, "Hydraulic Relay Control", 0, y_pos, 12, 6,
                f'from(bucket: "mqtt") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "controller_relay") |> filter(fn: (r) => r._field == "active") |> group(columns: ["relay"]) |> last()',
                mappings=[{"options": {"0": {"text": "OFF", "color": "gray"}, "1": {"text": "ON", "color": "green"}}, "type": "value"}]
            )
            dashboard["panels"].append(relay_panel)
            panel_id += 1
        
        # Input status (limit switches, e-stop)
        if 'controller_input' in data_structure:
            input_panel = self._create_stat_panel(
                panel_id, "Safety Inputs", 12, y_pos, 12, 6,
                f'from(bucket: "mqtt") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "controller_input") |> filter(fn: (r) => r._field == "state") |> group(columns: ["pin"]) |> last()',
                mappings=[{"options": {"0": {"text": "OPEN", "color": "red"}, "1": {"text": "CLOSED", "color": "green"}}, "type": "value"}]
            )
            dashboard["panels"].append(input_panel)
            panel_id += 1
        
        y_pos += 6
        
        # Sequence activity over time
        if 'controller_sequence' in data_structure:
            seq_activity_panel = self._create_timeseries_panel(
                panel_id, "Sequence Activity Over Time", 0, y_pos, 24, 6,
                f'from(bucket: "mqtt") |> range(start: -2h) |> filter(fn: (r) => r._measurement == "controller_sequence") |> filter(fn: (r) => r._field == "active") |> aggregateWindow(every: 5m, fn: sum)',
                unit="none"
            )
            dashboard["panels"].append(seq_activity_panel)
            panel_id += 1
            y_pos += 6
        
        return dashboard
    
    def _create_monitor_dashboard(self, data_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Create monitor-specific dashboard"""
        dashboard = {
            "annotations": {"list": []},
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "liveNow": False,
            "panels": [],
            "refresh": "5s",
            "schemaVersion": 36,
            "style": "dark",
            "tags": ["logsplitter", "monitor"],
            "templating": {"list": []},
            "time": {"from": "now-4h", "to": "now"},
            "timepicker": {},
            "timezone": "browser",
            "title": "LogSplitter Monitor Dashboard", 
            "uid": "logsplitter-monitor",
            "version": 1,
            "weekStart": ""
        }
        
        panel_id = 1
        y_pos = 0
        
        # Temperature monitoring
        if 'monitor_temperature' in data_structure:
            temp_panel = self._create_timeseries_panel(
                panel_id, "Temperature Sensors (Local/Remote)", 0, y_pos, 12, 8,
                f'from(bucket: "mqtt") |> range(start: -4h) |> filter(fn: (r) => r._measurement == "monitor_temperature") |> filter(fn: (r) => r._field == "fahrenheit") |> group(columns: ["sensor"])',
                unit="fahrenheit"
            )
            dashboard["panels"].append(temp_panel)
            panel_id += 1
        
        # Weight monitoring with trend
        if 'monitor_weight' in data_structure:
            weight_trend_panel = self._create_timeseries_panel(
                panel_id, "Weight Trend", 12, y_pos, 12, 8,
                f'from(bucket: "mqtt") |> range(start: -4h) |> filter(fn: (r) => r._measurement == "monitor_weight") |> filter(fn: (r) => r._field == "pounds") |> group(columns: ["type"])',
                unit="short"
            )
            dashboard["panels"].append(weight_trend_panel)
            panel_id += 1
        
        y_pos += 8
        
        # Current weight gauge
        if 'monitor_weight' in data_structure:
            weight_gauge = self._create_gauge_panel(
                panel_id, "Current Weight", 0, y_pos, 8, 6,
                f'from(bucket: "mqtt") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "monitor_weight") |> filter(fn: (r) => r._field == "pounds") |> filter(fn: (r) => r.type == "filtered") |> last()',
                min_val=0, max_val=200, unit="short",
                thresholds=[
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 80},
                    {"color": "red", "value": 150}
                ]
            )
            dashboard["panels"].append(weight_gauge)
            panel_id += 1
        
        # Power monitoring
        if 'monitor_power' in data_structure:
            power_panel = self._create_timeseries_panel(
                panel_id, "Power Consumption", 8, y_pos, 16, 6,
                f'from(bucket: "mqtt") |> range(start: -4h) |> filter(fn: (r) => r._measurement == "monitor_power") |> group(columns: ["metric", "_field"])',
                unit="watt"
            )
            dashboard["panels"].append(power_panel)
            panel_id += 1
        
        y_pos += 6
        
        # Digital inputs
        if 'monitor_input' in data_structure:
            input_panel = self._create_stat_panel(
                panel_id, "Digital Inputs", 0, y_pos, 24, 4,
                f'from(bucket: "mqtt") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "monitor_input") |> filter(fn: (r) => r._field == "state") |> group(columns: ["pin"]) |> last()',
                mappings=[{"options": {"0": {"text": "LOW", "color": "gray"}, "1": {"text": "HIGH", "color": "blue"}}, "type": "value"}]
            )
            dashboard["panels"].append(input_panel)
            panel_id += 1
        
        return dashboard
    
    def _create_safety_dashboard(self, data_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Create safety-focused dashboard"""
        dashboard = {
            "annotations": {"list": []},
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "liveNow": False,
            "panels": [],
            "refresh": "1s",  # Faster refresh for safety
            "schemaVersion": 36,
            "style": "dark",
            "tags": ["logsplitter", "safety"],
            "templating": {"list": []},
            "time": {"from": "now-30m", "to": "now"},
            "timepicker": {},
            "timezone": "browser",
            "title": "LogSplitter Safety Dashboard",
            "uid": "logsplitter-safety",
            "version": 1,
            "weekStart": ""
        }
        
        panel_id = 1
        y_pos = 0
        
        # Emergency stop status
        if 'controller_input' in data_structure:
            estop_panel = self._create_stat_panel(
                panel_id, "EMERGENCY STOP", 0, y_pos, 12, 4,
                f'from(bucket: "mqtt") |> range(start: -1m) |> filter(fn: (r) => r._measurement == "controller_input") |> filter(fn: (r) => r._field == "state") |> filter(fn: (r) => r.pin == "pin12") |> last()',
                mappings=[{"options": {"0": {"text": "NORMAL", "color": "green"}, "1": {"text": "E-STOP!", "color": "red"}}, "type": "value"}]
            )
            dashboard["panels"].append(estop_panel)
            panel_id += 1
        
        # Pressure safety status
        if 'controller_pressure' in data_structure:
            pressure_safety_panel = self._create_stat_panel(
                panel_id, "PRESSURE STATUS", 12, y_pos, 12, 4,
                f'from(bucket: "mqtt") |> range(start: -1m) |> filter(fn: (r) => r._measurement == "controller_pressure") |> filter(fn: (r) => r._field == "psi") |> max()',
                mappings=[
                    {"options": {"range": {"from": 0, "to": 2500}}, "result": {"text": "NORMAL", "color": "green"}},
                    {"options": {"range": {"from": 2500, "to": 4000}}, "result": {"text": "CAUTION", "color": "yellow"}},
                    {"options": {"range": {"from": 4000, "to": None}}, "result": {"text": "DANGER", "color": "red"}}
                ]
            )
            dashboard["panels"].append(pressure_safety_panel)
            panel_id += 1
        
        y_pos += 4
        
        # Limit switches
        if 'controller_input' in data_structure:
            limit_panel = self._create_stat_panel(
                panel_id, "Limit Switches", 0, y_pos, 24, 3,
                f'from(bucket: "mqtt") |> range(start: -1m) |> filter(fn: (r) => r._measurement == "controller_input") |> filter(fn: (r) => r._field == "state") |> filter(fn: (r) => r.pin == "pin6") |> group(columns: ["pin"]) |> last()',
                mappings=[{"options": {"0": {"text": "OPEN", "color": "red"}, "1": {"text": "CLOSED", "color": "green"}}, "type": "value"}]
            )
            dashboard["panels"].append(limit_panel)
            panel_id += 1
        
        y_pos += 3
        
        # Safety timeline
        if 'controller_pressure' in data_structure:
            safety_timeline_panel = self._create_timeseries_panel(
                panel_id, "Safety Events Timeline", 0, y_pos, 24, 8,
                f'from(bucket: "mqtt") |> range(start: -30m) |> filter(fn: (r) => r._measurement == "controller_pressure" or r._measurement == "controller_input") |> filter(fn: (r) => r._field == "psi" or r._field == "state")',
                unit="none"
            )
            dashboard["panels"].append(safety_timeline_panel)
            panel_id += 1
        
        return dashboard
    
    def _create_maintenance_dashboard(self, data_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Create maintenance and diagnostics dashboard"""
        dashboard = {
            "annotations": {"list": []},
            "editable": True,
            "fiscalYearStartMonth": 0,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "liveNow": False,
            "panels": [],
            "refresh": "30s",
            "schemaVersion": 36,
            "style": "dark",
            "tags": ["logsplitter", "maintenance"],
            "templating": {"list": []},
            "time": {"from": "now-24h", "to": "now"},
            "timepicker": {},
            "timezone": "browser",
            "title": "LogSplitter Maintenance Dashboard",
            "uid": "logsplitter-maintenance",
            "version": 1,
            "weekStart": ""
        }
        
        panel_id = 1
        y_pos = 0
        
        # System uptime
        if 'monitor_system' in data_structure:
            uptime_panel = self._create_stat_panel(
                panel_id, "System Uptime", 0, y_pos, 8, 4,
                f'from(bucket: "mqtt") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "monitor_system") |> filter(fn: (r) => r._field == "value") |> filter(fn: (r) => r.metric == "uptime") |> last()',
                unit="s"
            )
            dashboard["panels"].append(uptime_panel)
            panel_id += 1
        
        # Message rates
        message_rate_panel = self._create_timeseries_panel(
            panel_id, "MQTT Message Rates", 8, y_pos, 16, 4,
            f'from(bucket: "mqtt") |> range(start: -24h) |> aggregateWindow(every: 1h, fn: count) |> group(columns: ["_measurement"])',
            unit="none"
        )
        dashboard["panels"].append(message_rate_panel)
        panel_id += 1
        y_pos += 4
        
        # Cycle counts
        if 'controller_sequence' in data_structure:
            cycle_panel = self._create_timeseries_panel(
                panel_id, "Operation Cycle Counts", 0, y_pos, 12, 6,
                f'from(bucket: "mqtt") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "controller_sequence") |> filter(fn: (r) => r._field == "active") |> aggregateWindow(every: 1h, fn: sum)',
                unit="none"
            )
            dashboard["panels"].append(cycle_panel)
            panel_id += 1
        
        # Temperature trends for maintenance
        if 'monitor_temperature' in data_structure:
            temp_maintenance_panel = self._create_timeseries_panel(
                panel_id, "Temperature Trends (24h)", 12, y_pos, 12, 6,
                f'from(bucket: "mqtt") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "monitor_temperature") |> filter(fn: (r) => r._field == "fahrenheit") |> aggregateWindow(every: 1h, fn: mean) |> group(columns: ["sensor"])',
                unit="fahrenheit"
            )
            dashboard["panels"].append(temp_maintenance_panel)
            panel_id += 1
        
        y_pos += 6
        
        # Error/log summary
        if 'controller_log' in data_structure:
            log_panel = self._create_stat_panel(
                panel_id, "System Logs (24h)", 0, y_pos, 24, 4,
                f'from(bucket: "mqtt") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "controller_log") |> filter(fn: (r) => r._field == "count") |> group(columns: ["level"]) |> sum()',
                unit="none"
            )
            dashboard["panels"].append(log_panel)
            panel_id += 1
        
        return dashboard
    
    def _create_timeseries_panel(self, panel_id: int, title: str, x: int, y: int, w: int, h: int, 
                                query: str, unit: str = "none", max_value: int = None, 
                                thresholds: List[Dict] = None) -> Dict[str, Any]:
        """Create a timeseries panel"""
        panel = {
            "datasource": {"type": "influxdb", "uid": "influxdb-1"},
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisLabel": "", "axisPlacement": "auto", "barAlignment": 0,
                        "drawStyle": "line", "fillOpacity": 0, "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "vis": False},
                        "lineInterpolation": "linear", "lineWidth": 1, "pointSize": 5,
                        "scaleDistribution": {"type": "linear"}, "showPoints": "auto",
                        "spanNulls": False, "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"}
                    },
                    "mappings": [], "unit": unit,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": thresholds or [{"color": "green", "value": None}, {"color": "red", "value": 80}]
                    }
                },
                "overrides": []
            },
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "id": panel_id,
            "options": {
                "legend": {"calcs": [], "displayMode": "list", "placement": "bottom"},
                "tooltip": {"mode": "single", "sort": "none"}
            },
            "targets": [{"datasource": {"type": "influxdb", "uid": "influxdb-1"}, "query": query, "refId": "A"}],
            "title": title,
            "type": "timeseries"
        }
        
        if max_value:
            panel["fieldConfig"]["defaults"]["max"] = max_value
            panel["fieldConfig"]["defaults"]["min"] = 0
            
        return panel
    
    def _create_stat_panel(self, panel_id: int, title: str, x: int, y: int, w: int, h: int, 
                          query: str, unit: str = "none", mappings: List[Dict] = None) -> Dict[str, Any]:
        """Create a stat panel"""
        return {
            "datasource": {"type": "influxdb", "uid": "influxdb-1"},
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": mappings or [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green", "value": None}, {"color": "red", "value": 80}]
                    },
                    "unit": unit
                },
                "overrides": []
            },
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "id": panel_id,
            "options": {
                "colorMode": "background", "graphMode": "area", "justifyMode": "center",
                "orientation": "horizontal",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "textMode": "auto"
            },
            "pluginVersion": "9.0.0",
            "targets": [{"datasource": {"type": "influxdb", "uid": "influxdb-1"}, "query": query, "refId": "A"}],
            "title": title,
            "type": "stat"
        }
    
    def _create_gauge_panel(self, panel_id: int, title: str, x: int, y: int, w: int, h: int, 
                           query: str, min_val: int = 0, max_val: int = 100, unit: str = "none",
                           thresholds: List[Dict] = None) -> Dict[str, Any]:
        """Create a gauge panel"""
        return {
            "datasource": {"type": "influxdb", "uid": "influxdb-1"},
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [], "max": max_val, "min": min_val,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": thresholds or [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 60},
                            {"color": "red", "value": 80}
                        ]
                    },
                    "unit": unit
                },
                "overrides": []
            },
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "id": panel_id,
            "options": {
                "orientation": "auto",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "showThresholdLabels": False, "showThresholdMarkers": True
            },
            "pluginVersion": "9.0.0",
            "targets": [{"datasource": {"type": "influxdb", "uid": "influxdb-1"}, "query": query, "refId": "A"}],
            "title": title,
            "type": "gauge"
        }

def main():
    parser = argparse.ArgumentParser(description='Verify InfluxDB data and generate Grafana dashboards')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    parser.add_argument('--verify-only', action='store_true', help='Only verify data, don\'t generate dashboards')
    args = parser.parse_args()
    
    print("🚀 LogSplitter InfluxDB Data Verifier & Dashboard Generator")
    print("=" * 60)
    
    verifier = InfluxDataVerifier(args.config)
    
    if not verifier.connect():
        sys.exit(1)
    
    # Verify data structure
    data_structure = verifier.verify_data_structure()
    
    if not data_structure:
        print("❌ No data found in InfluxDB")
        sys.exit(1)
    
    print(f"\n✅ Data verification complete. Found {len(data_structure)} measurements.")
    
    # Generate comprehensive dashboards
    if not args.verify_only:
        print("\n📊 Generating Grafana dashboards...")
        verifier.generate_dashboards(data_structure)
        print("\n✅ Dashboard generation complete!")
        print("\nTo import dashboards:")
        print("1. Open Grafana UI")
        print("2. Go to '+' → Import")
        print("3. Upload the generated .json files")
        print("4. Select your InfluxDB datasource: influxdb-1")
    
    # Summary report
    print(f"\n📋 SUMMARY REPORT")
    print("=" * 40)
    for measurement, structure in data_structure.items():
        print(f"📊 {measurement}:")
        print(f"   Fields: {', '.join(structure['fields'])}")
        print(f"   Tags: {', '.join(structure['tags'])}")
        print(f"   Records (24h): {structure['record_count']}")
    
    verifier.client.close()

if __name__ == "__main__":
    main()