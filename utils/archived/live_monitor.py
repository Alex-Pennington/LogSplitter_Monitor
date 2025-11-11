#!/usr/bin/env python3
"""
Live LogSplitter Monitor - Real-time System Status

Shows current system activity and waits for basket exchange operations.
Displays pressure readings, monitor data, and digital inputs in real-time.
"""

import sqlite3
import json
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List

class LiveSystemMonitor:
    """Real-time LogSplitter system monitor"""
    
    def __init__(self, db_path: str = 'logsplitter_data.db'):
        self.db_path = db_path
        self.last_update = datetime.now()
        
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get recent telemetry counts
            cursor.execute("""
                SELECT message_type_name, COUNT(*) as count 
                FROM telemetry 
                WHERE received_timestamp > datetime('now', '-5 minutes')
                GROUP BY message_type_name
                ORDER BY count DESC
            """)
            
            telemetry_counts = dict(cursor.fetchall())
            
            # Get latest pressure readings
            cursor.execute("""
                SELECT payload_json FROM telemetry 
                WHERE message_type_name = 'PRESSURE'
                ORDER BY received_timestamp DESC 
                LIMIT 2
            """)
            
            pressure_readings = []
            for row in cursor.fetchall():
                try:
                    payload = json.loads(row[0]) if row[0] else {}
                    pressure_readings.append({
                        'sensor': payload.get('sensor_name', 'Unknown'),
                        'pressure_psi': payload.get('pressure_psi', 0),
                        'fault_status': payload.get('fault_status', 'UNKNOWN')
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # Get latest monitor data
            cursor.execute("""
                SELECT topic, value FROM monitor_data 
                WHERE received_timestamp > datetime('now', '-2 minutes')
                ORDER BY received_timestamp DESC
            """)
            
            monitor_data = {}
            seen_topics = set()
            for row in cursor.fetchall():
                topic, value = row
                if topic not in seen_topics:  # Get latest value for each topic
                    monitor_data[topic] = value
                    seen_topics.add(topic)
            
            # Check for digital inputs
            cursor.execute("""
                SELECT payload_json FROM telemetry 
                WHERE message_type_name = 'DIGITAL_INPUT'
                ORDER BY received_timestamp DESC 
                LIMIT 5
            """)
            
            digital_inputs = []
            for row in cursor.fetchall():
                try:
                    payload = json.loads(row[0]) if row[0] else {}
                    digital_inputs.append({
                        'pin': payload.get('pin', 0),
                        'state': payload.get('state_name', 'UNKNOWN'),
                        'input_type': payload.get('input_type_name', 'UNKNOWN')
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
            
            conn.close()
            
            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'telemetry_counts': telemetry_counts,
                'pressure_readings': pressure_readings,
                'monitor_data': monitor_data,
                'digital_inputs': digital_inputs
            }
            
        except Exception as e:
            return {'error': str(e), 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    def print_status(self, status: Dict[str, Any]):
        """Print formatted system status"""
        print(f"\n🎛️  LogSplitter System Status - {status['timestamp']}")
        print("=" * 70)
        
        if 'error' in status:
            print(f"❌ Error: {status['error']}")
            return
        
        # Message counts
        counts = status.get('telemetry_counts', {})
        if counts:
            print("📊 Message Activity (last 5 min):")
            for msg_type, count in counts.items():
                print(f"   {msg_type}: {count} messages")
        else:
            print("📊 No recent telemetry messages")
        
        # Pressure readings
        pressures = status.get('pressure_readings', [])
        if pressures:
            print("\n🔧 Pressure Sensors:")
            for p in pressures:
                print(f"   {p['sensor']}: {p['pressure_psi']:.1f} PSI ({p['fault_status']})")
        else:
            print("\n🔧 No pressure data available")
        
        # Monitor data
        monitor = status.get('monitor_data', {})
        if monitor:
            print("\n📡 Monitor Data:")
            for topic, value in sorted(monitor.items()):
                topic_short = topic.replace('monitor/', '')
                if isinstance(value, (int, float)):
                    if 'temp' in topic:
                        print(f"   {topic_short}: {value:.1f}°F")
                    elif 'weight' in topic:
                        print(f"   {topic_short}: {value:.1f}g")
                    elif 'uptime' in topic:
                        minutes = value / 60
                        print(f"   {topic_short}: {minutes:.1f} min")
                    elif 'memory' in topic:
                        kb = value / 1024
                        print(f"   {topic_short}: {kb:.1f} KB")
                    else:
                        print(f"   {topic_short}: {value}")
                else:
                    print(f"   {topic_short}: {value}")
        else:
            print("\n📡 No monitor data available")
        
        # Digital inputs (basket exchange detection)
        inputs = status.get('digital_inputs', [])
        if inputs:
            print("\n🎮 Digital Inputs (Recent):")
            for inp in inputs:
                print(f"   Pin {inp['pin']}: {inp['state']} ({inp['input_type']})")
                if inp['input_type'] == 'SPLITTER_OPERATOR':
                    print("   🧺 ← BASKET EXCHANGE SIGNAL DETECTED!")
        else:
            print("\n🎮 No digital input activity")
            print("   💡 Waiting for operator input (basket exchanges)...")
    
    def run_monitor(self, interval: int = 5):
        """Run live monitoring loop"""
        print("🎛️  LogSplitter Live Monitor")
        print("Press Ctrl+C to stop")
        print("\n💡 This monitor shows real-time system activity")
        print("🧺 When you operate the log splitter, basket exchanges will be detected here")
        print("📊 The basket metrics dashboard will analyze the exchange data")
        
        try:
            while True:
                status = self.get_system_status()
                
                # Clear screen (cross-platform)
                print('\033[2J\033[H', end='')
                
                self.print_status(status)
                
                # Show basket exchange readiness
                inputs = status.get('digital_inputs', [])
                operator_active = any(inp['input_type'] == 'SPLITTER_OPERATOR' for inp in inputs)
                
                if operator_active:
                    print("\n🟢 BASKET EXCHANGE DETECTION: ACTIVE")
                    print("   🧺 Operator input detected - basket metrics being recorded!")
                else:
                    print("\n🟡 BASKET EXCHANGE DETECTION: WAITING")
                    print("   🧺 Activate splitter operator signal to record basket exchanges")
                
                print(f"\n⏰ Next update in {interval} seconds...")
                print("   Press Ctrl+C to exit and run basket_metrics_dashboard.py")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped")
            print("\n🧺 To view basket exchange analysis:")
            print("   python3 basket_metrics_dashboard.py --report-only")
            print("   python3 basket_metrics_dashboard.py  # Visual dashboard")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='LogSplitter Live System Monitor')
    parser.add_argument('--interval', type=int, default=5, help='Update interval in seconds (default: 5)')
    args = parser.parse_args()
    
    monitor = LiveSystemMonitor()
    monitor.run_monitor(args.interval)

if __name__ == "__main__":
    main()