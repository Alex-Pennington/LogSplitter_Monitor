#!/usr/bin/env python3
"""
Real-Time Safety Monitor for LogSplitter System
Monitors E-Stop status, engine status, and critical safety events
"""

import json
import time
from datetime import datetime
from influxdb_client import InfluxDBClient

def load_config():
    """Load InfluxDB configuration"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "influxdb": {
                "host": "192.168.1.238",
                "port": 8086,
                "token": "your_token_here",
                "org": "your_org",
                "bucket": "mqtt"
            }
        }

class SafetyMonitor:
    def __init__(self, config):
        """Initialize safety monitor with InfluxDB connection"""
        influx_config = config['influxdb']
        url = influx_config['url']
        
        self.client = InfluxDBClient(
            url=url,
            token=influx_config['token'],
            org=influx_config['org']
        )
        self.bucket = influx_config['bucket']
        self.query_api = self.client.query_api()
        
    def get_estop_status(self):
        """Check if E-Stop is currently active (only last 2 minutes)"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -2m)
          |> filter(fn: (r) => r._measurement == "controller_log")
          |> filter(fn: (r) => r._field == "message")
          |> filter(fn: (r) => r._value =~ /E-STOP ACTIVATED/)
          |> last()
        '''
        
        try:
            result = self.query_api.query(query)
            for table in result:
                for record in table.records:
                    # Only consider it active if it's very recent (last 2 minutes)
                    return {
                        'active': True,
                        'time': record.get_time(),
                        'message': record.get_value(),
                        'level': record.values.get('level', 'unknown')
                    }
            return {'active': False}
        except Exception as e:
            print(f"Error checking E-Stop status: {e}")
            return {'active': None, 'error': str(e)}
    
    def get_engine_status(self):
        """Check if engine is currently stopped (only last 2 minutes)"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -2m)
          |> filter(fn: (r) => r._measurement == "controller_log")
          |> filter(fn: (r) => r._field == "message")
          |> filter(fn: (r) => r._value =~ /Engine stopped/)
          |> last()
        '''
        
        try:
            result = self.query_api.query(query)
            for table in result:
                for record in table.records:
                    # Only consider it stopped if it's very recent (last 2 minutes)
                    return {
                        'stopped': True,
                        'time': record.get_time(),
                        'message': record.get_value(),
                        'level': record.values.get('level', 'unknown')
                    }
            return {'stopped': False}
        except Exception as e:
            print(f"Error checking engine status: {e}")
            return {'stopped': None, 'error': str(e)}
    
    def get_system_status(self):
        """Get overall system status"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -2m)
          |> filter(fn: (r) => r._measurement == "controller_system")
          |> filter(fn: (r) => r._field == "active" or r._field == "status")
          |> last()
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        
        try:
            result = self.query_api.query(query)
            for table in result:
                for record in table.records:
                    return {
                        'active': record.values.get('active', 0),
                        'status': record.values.get('status', 'Unknown'),
                        'time': record.get_time()
                    }
            return {'active': None, 'status': 'No Data'}
        except Exception as e:
            print(f"Error checking system status: {e}")
            return {'active': None, 'status': f'Error: {e}'}
    
    def get_current_pressure(self):
        """Get current hydraulic pressure"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -2m)
          |> filter(fn: (r) => r._measurement == "controller_pressure")
          |> filter(fn: (r) => r._field == "psi")
          |> filter(fn: (r) => r.sensor == "A1")
          |> last()
        '''
        
        try:
            result = self.query_api.query(query)
            for table in result:
                for record in table.records:
                    return {
                        'psi': record.get_value(),
                        'time': record.get_time(),
                        'critical': record.get_value() > 2500 if record.get_value() else False
                    }
            return {'psi': None, 'critical': False}
        except Exception as e:
            print(f"Error checking pressure: {e}")
            return {'psi': None, 'critical': False, 'error': str(e)}
    
    def get_sequence_state(self):
        """Get current sequence state"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -2m)
          |> filter(fn: (r) => r._measurement == "controller_sequence")
          |> filter(fn: (r) => r._field == "active")
          |> last()
        '''
        
        try:
            result = self.query_api.query(query)
            for table in result:
                for record in table.records:
                    return {
                        'state': record.values.get('state', 'Unknown'),
                        'active': record.get_value(),
                        'time': record.get_time()
                    }
            return {'state': 'No Data', 'active': None}
        except Exception as e:
            print(f"Error checking sequence: {e}")
            return {'state': f'Error: {e}', 'active': None}
    
    def get_recent_alerts(self, minutes=10):
        """Get recent critical alerts"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -{minutes}m)
          |> filter(fn: (r) => r._measurement == "controller_log")
          |> filter(fn: (r) => r._field == "message")
          |> filter(fn: (r) => r.level == "crit" or r.level == "error")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 5)
        '''
        
        try:
            result = self.query_api.query(query)
            alerts = []
            for table in result:
                for record in table.records:
                    alerts.append({
                        'time': record.get_time(),
                        'message': record.get_value(),
                        'level': record.values.get('level', 'unknown')
                    })
            return alerts
        except Exception as e:
            print(f"Error getting alerts: {e}")
            return []

def format_status_indicator(status, true_text="🟢 OK", false_text="🔴 ALERT", none_text="❓ UNKNOWN"):
    """Format status with appropriate emoji"""
    if status is None:
        return none_text
    elif status:
        return false_text  # True means alert condition
    else:
        return true_text

def print_safety_status(monitor):
    """Print comprehensive safety status"""
    # Clear screen
    print("\033[2J\033[H")
    
    print("=" * 80)
    print("🚨 LOGSPLITTER SAFETY MONITOR - REAL-TIME STATUS 🚨")
    print("=" * 80)
    print(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # E-Stop Status
    estop = monitor.get_estop_status()
    estop_status = format_status_indicator(
        estop.get('active'),
        "🟢 NORMAL", 
        "🚨 E-STOP ACTIVE!",
        "❓ NO DATA"
    )
    print(f"E-STOP STATUS:     {estop_status}")
    if estop.get('active'):
        print(f"                   ⚠️  {estop.get('message', 'No message')}")
        print(f"                   🕐 {estop.get('time', 'No timestamp')}")
    
    # Engine Status
    engine = monitor.get_engine_status()
    engine_status = format_status_indicator(
        engine.get('stopped'),
        "🟢 RUNNING",
        "🛑 STOPPED!",
        "❓ NO DATA"
    )
    print(f"ENGINE STATUS:     {engine_status}")
    if engine.get('stopped'):
        print(f"                   ⚠️  {engine.get('message', 'No message')}")
        print(f"                   🕐 {engine.get('time', 'No timestamp')}")
    
    # System Status
    system = monitor.get_system_status()
    sys_status = format_status_indicator(
        system.get('active') == 0 if system.get('active') is not None else None,
        "🟢 ONLINE",
        "🔴 OFFLINE",
        "❓ NO DATA"
    )
    print(f"SYSTEM STATUS:     {sys_status}")
    if system.get('status'):
        print(f"                   📊 {system.get('status')}")
    
    # Pressure Status
    pressure = monitor.get_current_pressure()
    if pressure.get('psi') is not None:
        psi_value = pressure['psi']
        if pressure.get('critical'):
            pressure_status = f"🚨 CRITICAL: {psi_value:.1f} PSI"
        elif psi_value > 2000:
            pressure_status = f"⚠️ HIGH: {psi_value:.1f} PSI"
        else:
            pressure_status = f"🟢 NORMAL: {psi_value:.1f} PSI"
    else:
        pressure_status = "❓ NO DATA"
    print(f"PRESSURE STATUS:   {pressure_status}")
    
    # Sequence Status
    sequence = monitor.get_sequence_state()
    seq_active = sequence.get('active')
    if seq_active is not None:
        if seq_active == 1:
            seq_status = f"🔄 ACTIVE: {sequence.get('state', 'Unknown')}"
        else:
            seq_status = f"⏸️ IDLE: {sequence.get('state', 'Unknown')}"
    else:
        seq_status = "❓ NO DATA"
    print(f"SEQUENCE STATUS:   {seq_status}")
    
    print()
    print("-" * 80)
    print("📋 RECENT CRITICAL ALERTS (Last 10 minutes):")
    print("-" * 80)
    
    alerts = monitor.get_recent_alerts(10)
    if alerts:
        for alert in alerts:
            level_emoji = {
                'crit': '🚨',
                'error': '❌', 
                'warn': '⚠️'
            }.get(alert['level'], '📢')
            
            time_str = alert['time'].strftime('%H:%M:%S') if alert['time'] else 'No time'
            print(f"{level_emoji} [{time_str}] {alert['message']}")
    else:
        print("✅ No critical alerts in the last 10 minutes")
    
    print()
    print("-" * 80)
    print("Press Ctrl+C to exit")

def main():
    """Main monitoring loop"""
    config = load_config()
    monitor = SafetyMonitor(config)
    
    print("Starting LogSplitter Safety Monitor...")
    print("Connecting to InfluxDB...")
    
    try:
        while True:
            print_safety_status(monitor)
            time.sleep(2)  # Update every 2 seconds
            
    except KeyboardInterrupt:
        print("\n\nSafety monitor stopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
    finally:
        monitor.client.close()

if __name__ == "__main__":
    main()