#!/usr/bin/env python3
"""
Current Status Diagnostic for LogSplitter System
Shows ONLY the absolute latest status from each measurement
"""

import json
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient

def load_config():
    """Load InfluxDB configuration"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "influxdb": {
                "url": "http://192.168.1.155:8086",
                "token": "your_token_here",
                "org": "your_org",
                "bucket": "mqtt"
            }
        }

class CurrentStatusDiagnostic:
    def __init__(self, config):
        """Initialize diagnostic with InfluxDB connection"""
        influx_config = config['influxdb']
        
        self.client = InfluxDBClient(
            url=influx_config['url'],
            token=influx_config['token'],
            org=influx_config['org']
        )
        self.bucket = influx_config['bucket']
        self.query_api = self.client.query_api()
    
    def get_latest_from_measurement(self, measurement, field=None, additional_filters=""):
        """Get the absolute latest record from a measurement"""
        field_filter = f'|> filter(fn: (r) => r._field == "{field}")' if field else ""
        
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "{measurement}")
          {field_filter}
          {additional_filters}
          |> last()
        '''
        
        try:
            result = self.query_api.query(query)
            records = []
            for table in result:
                for record in table.records:
                    records.append({
                        'time': record.get_time(),
                        'value': record.get_value(),
                        'field': record.get_field(),
                        'measurement': record.get_measurement(),
                        'tags': {k: v for k, v in record.values.items() if k not in ['_time', '_value', '_field', '_measurement']}
                    })
            return records
        except Exception as e:
            return [{'error': str(e)}]
    
    def print_diagnostic(self):
        """Print comprehensive current status diagnostic"""
        print("=" * 80)
        print("🔍 LOGSPLITTER CURRENT STATUS DIAGNOSTIC")
        print("=" * 80)
        print(f"Diagnostic Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Controller System Status
        print("📊 CONTROLLER SYSTEM:")
        system_records = self.get_latest_from_measurement("controller_system")
        for record in system_records:
            if 'error' in record:
                print(f"   ERROR: {record['error']}")
            else:
                print(f"   {record['field']}: {record['value']} (at {record['time']})")
        print()
        
        # Controller Sequence Status
        print("⚡ CONTROLLER SEQUENCE:")
        sequence_records = self.get_latest_from_measurement("controller_sequence")
        for record in sequence_records:
            if 'error' in record:
                print(f"   ERROR: {record['error']}")
            else:
                tags_str = ", ".join([f"{k}={v}" for k, v in record['tags'].items() if v])
                print(f"   {record['field']}: {record['value']} [{tags_str}] (at {record['time']})")
        print()
        
        # Latest Pressure Reading
        print("🔧 LATEST PRESSURE:")
        pressure_records = self.get_latest_from_measurement("controller_pressure", "psi")
        for record in pressure_records:
            if 'error' in record:
                print(f"   ERROR: {record['error']}")
            else:
                sensor = record['tags'].get('sensor', 'unknown')
                print(f"   Sensor {sensor}: {record['value']} PSI (at {record['time']})")
        print()
        
        # Latest Relay Status
        print("🔌 LATEST RELAY STATUS:")
        relay_records = self.get_latest_from_measurement("controller_relay")
        for record in relay_records:
            if 'error' in record:
                print(f"   ERROR: {record['error']}")
            else:
                relay = record['tags'].get('relay', 'unknown')
                state = "ON" if record['value'] == 1 else "OFF"
                print(f"   {relay}: {state} (at {record['time']})")
        print()
        
        # Latest Input Status
        print("📡 LATEST INPUT STATUS:")
        input_records = self.get_latest_from_measurement("controller_input")
        for record in input_records:
            if 'error' in record:
                print(f"   ERROR: {record['error']}")
            else:
                pin = record['tags'].get('pin', 'unknown')
                state = "HIGH" if record['value'] == 1 else "LOW"
                print(f"   Pin {pin}: {state} (at {record['time']})")
        print()
        
        # Check for RECENT critical logs (last 5 minutes only)
        print("🚨 RECENT CRITICAL EVENTS (Last 5 minutes):")
        recent_logs = self.get_latest_critical_logs(5)
        if recent_logs:
            for log in recent_logs[-5:]:  # Show last 5 events
                if 'error' in log:
                    print(f"   ERROR: {log['error']}")
                else:
                    level = log['tags'].get('level', 'unknown')
                    time_str = log['time'].strftime('%H:%M:%S') if log['time'] else 'No time'
                    print(f"   [{time_str}] {level.upper()}: {log['value']}")
        else:
            print("   ✅ No critical events in last 5 minutes")
        print()
        
        # Overall Assessment
        print("🎯 CURRENT SYSTEM ASSESSMENT:")
        self.assess_current_state()
        
    def get_latest_critical_logs(self, minutes=5):
        """Get critical logs from the last N minutes"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "controller_log")
          |> filter(fn: (r) => r._field == "message")
          |> filter(fn: (r) => r.level == "crit" or r.level == "error")
          |> sort(columns: ["_time"], desc: false)
        '''
        
        try:
            result = self.query_api.query(query)
            records = []
            for table in result:
                for record in table.records:
                    records.append({
                        'time': record.get_time(),
                        'value': record.get_value(),
                        'field': record.get_field(),
                        'measurement': record.get_measurement(),
                        'tags': {k: v for k, v in record.values.items() if k not in ['_time', '_value', '_field', '_measurement']}
                    })
            return records
        except Exception as e:
            return [{'error': str(e)}]
    
    def assess_current_state(self):
        """Provide overall system assessment"""
        now = datetime.now(timezone.utc)
        
        # Check for recent E-Stop or engine stop events
        recent_critical = self.get_latest_critical_logs(2)  # Last 2 minutes
        
        recent_estop = any("E-STOP ACTIVATED" in log.get('value', '') for log in recent_critical if 'error' not in log)
        recent_engine_stop = any("Engine stopped" in log.get('value', '') for log in recent_critical if 'error' not in log)
        
        if recent_estop:
            print("   🚨 EMERGENCY STOP DETECTED (Last 2 minutes)")
            print("   🔴 SYSTEM STATUS: EMERGENCY")
        elif recent_engine_stop:
            print("   ⚠️  ENGINE STOP DETECTED (Last 2 minutes)")
            print("   🟡 SYSTEM STATUS: ENGINE SHUTDOWN")
        else:
            print("   ✅ NO RECENT EMERGENCY EVENTS")
            print("   🟢 SYSTEM STATUS: OPERATIONAL")
        
        # Check system active status
        system_records = self.get_latest_from_measurement("controller_system", "active")
        if system_records and not any('error' in r for r in system_records):
            active_value = system_records[0]['value']
            if active_value == 1:
                print("   📊 CONTROLLER: ACTIVE")
            else:
                print("   📊 CONTROLLER: INACTIVE")
        
        print()
        print("💡 INTERPRETATION:")
        if recent_estop or recent_engine_stop:
            print("   The system shows recent emergency events.")
            print("   If you believe the system should be running normally,")
            print("   check the physical E-Stop button and controller status.")
        else:
            print("   No recent emergency events detected.")
            print("   System appears to be in normal operational state.")

def main():
    """Main diagnostic function"""
    config = load_config()
    diagnostic = CurrentStatusDiagnostic(config)
    
    try:
        diagnostic.print_diagnostic()
    except Exception as e:
        print(f"Diagnostic error: {e}")
    finally:
        diagnostic.client.close()

if __name__ == "__main__":
    main()