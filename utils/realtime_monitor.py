#!/usr/bin/env python3
"""
LogSplitter Real-Time Monitor

Quick real-time monitoring dashboard for terminal.
Perfect for monitoring splitter operations as they happen.

Usage:
    python3 realtime_monitor.py
"""

import sqlite3
import json
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_PATH = os.getenv('DATABASE_PATH', 'logsplitter_telemetry.db')

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_latest_data():
    """Get latest operational data"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    data = {
        'last_update': datetime.now(),
        'messages_last_minute': 0,
        'current_sequence': None,
        'latest_pressure': None,
        'operator_signals': [],
        'system_status': None,
        'recent_events': []
    }
    
    try:
        # Messages in last minute
        cursor.execute("""
            SELECT COUNT(*) FROM telemetry 
            WHERE received_timestamp > datetime('now', '-1 minute')
        """)
        data['messages_last_minute'] = cursor.fetchone()[0]
        
        # Latest sequence event
        cursor.execute("""
            SELECT payload_json, received_timestamp 
            FROM telemetry 
            WHERE message_type_name = 'SEQUENCE_EVENT'
            ORDER BY received_timestamp DESC 
            LIMIT 1
        """)
        seq_result = cursor.fetchone()
        if seq_result:
            seq_payload = json.loads(seq_result[0])
            data['current_sequence'] = {
                'event': seq_payload.get('event_type_name', 'UNKNOWN'),
                'step': seq_payload.get('step_number', 0),
                'elapsed': seq_payload.get('elapsed_time_ms', 0),
                'timestamp': seq_result[1]
            }
        
        # Latest pressure reading
        cursor.execute("""
            SELECT payload_json, received_timestamp 
            FROM telemetry 
            WHERE message_type_name = 'PRESSURE'
            ORDER BY received_timestamp DESC 
            LIMIT 1
        """)
        pressure_result = cursor.fetchone()
        if pressure_result:
            pressure_payload = json.loads(pressure_result[0])
            data['latest_pressure'] = {
                'psi': pressure_payload.get('pressure_psi', 0),
                'sensor': pressure_payload.get('sensor_pin', 0),
                'fault': pressure_payload.get('fault_status', 'OK'),
                'timestamp': pressure_result[1]
            }
        
        # Recent operator signals (last 5 minutes)
        cursor.execute("""
            SELECT payload_json, received_timestamp 
            FROM telemetry 
            WHERE message_type_name = 'DIGITAL_INPUT'
            AND received_timestamp > datetime('now', '-5 minutes')
            ORDER BY received_timestamp DESC
            LIMIT 10
        """)
        signal_results = cursor.fetchall()
        for signal in signal_results:
            signal_payload = json.loads(signal[0])
            input_type = signal_payload.get('input_type_name', 'UNKNOWN')
            if 'OPERATOR' in input_type or 'MANUAL' in input_type:
                data['operator_signals'].append({
                    'type': input_type,
                    'state': signal_payload.get('state', False),
                    'pin': signal_payload.get('pin', 0),
                    'timestamp': signal[1]
                })
        
        # Latest system status
        cursor.execute("""
            SELECT payload_json 
            FROM telemetry 
            WHERE message_type_name = 'SYSTEM_STATUS'
            ORDER BY received_timestamp DESC 
            LIMIT 1
        """)
        status_result = cursor.fetchone()
        if status_result:
            data['system_status'] = json.loads(status_result[0])
        
        # Recent events (all types, last 2 minutes)
        cursor.execute("""
            SELECT message_type_name, payload_json, received_timestamp 
            FROM telemetry 
            WHERE received_timestamp > datetime('now', '-2 minutes')
            ORDER BY received_timestamp DESC 
            LIMIT 20
        """)
        event_results = cursor.fetchall()
        for event in event_results:
            data['recent_events'].append({
                'type': event[0],
                'payload': json.loads(event[1]),
                'timestamp': event[2]
            })
    
    except Exception as e:
        print(f"Database error: {e}")
    
    conn.close()
    return data

def format_timestamp(timestamp_str):
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime("%H:%M:%S")
    except:
        return "N/A"

def display_dashboard(data):
    """Display the real-time dashboard"""
    clear_screen()
    
    print("🪵 LogSplitter Real-Time Monitor")
    print("=" * 80)
    print(f"Last Update: {data['last_update'].strftime('%H:%M:%S')} | Messages/min: {data['messages_last_minute']}")
    print()
    
    # System Status
    print("💻 SYSTEM STATUS")
    print("-" * 40)
    if data['system_status']:
        status = data['system_status']
        uptime_min = status.get('uptime_minutes', 0)
        free_mem = status.get('free_memory_bytes', 0)
        errors = status.get('active_error_count', 0)
        safety_active = status.get('safety_active', False)
        sequence_state = status.get('sequence_state_name', 'UNKNOWN')
        
        print(f"Uptime: {uptime_min:.1f} min | Memory: {free_mem} bytes | Errors: {errors}")
        
        safety_icon = "🔴" if safety_active else "🟢"
        print(f"Safety: {safety_icon} {'ACTIVE' if safety_active else 'OK'} | Sequence: {sequence_state}")
    else:
        print("❌ No system status available")
    
    print()
    
    # Current Sequence
    print("🔄 CURRENT SEQUENCE")
    print("-" * 40)
    if data['current_sequence']:
        seq = data['current_sequence']
        timestamp = format_timestamp(seq['timestamp'])
        elapsed_sec = seq['elapsed'] / 1000.0
        
        # Color coding for sequence events
        event = seq['event']
        if 'STARTED' in event:
            icon = "🟢"
        elif 'COMPLETE' in event:
            icon = "🔵"
        elif 'ABORTED' in event:
            icon = "🔴"
        else:
            icon = "🟡"
        
        print(f"{icon} {event}")
        print(f"Step: {seq['step']} | Elapsed: {elapsed_sec:.1f}s | Time: {timestamp}")
    else:
        print("ℹ️  No recent sequence activity")
    
    print()
    
    # Pressure Status
    print("⚡ PRESSURE STATUS")
    print("-" * 40)
    if data['latest_pressure']:
        pressure = data['latest_pressure']
        timestamp = format_timestamp(pressure['timestamp'])
        psi = pressure['psi']
        fault_icon = "⚠️" if pressure['fault'] != 'OK' else "✅"
        
        # Color coding for pressure levels
        if psi > 2500:
            pressure_icon = "🔴"  # High pressure
        elif psi > 1500:
            pressure_icon = "🟡"  # Medium pressure
        else:
            pressure_icon = "🟢"  # Normal pressure
        
        print(f"{pressure_icon} {psi:.1f} PSI | Sensor: A{pressure['sensor']} | {fault_icon} {pressure['fault']}")
        print(f"Time: {timestamp}")
    else:
        print("❌ No pressure data available")
    
    print()
    
    # Operator Signals
    print("👷 OPERATOR SIGNALS (Last 5 min)")
    print("-" * 40)
    if data['operator_signals']:
        for signal in data['operator_signals'][:5]:  # Show last 5
            timestamp = format_timestamp(signal['timestamp'])
            state_icon = "🟢" if signal['state'] else "🔴"
            print(f"[{timestamp}] {state_icon} {signal['type']} (Pin {signal['pin']})")
    else:
        print("ℹ️  No recent operator signals")
    
    print()
    
    # Recent Activity
    print("📡 RECENT ACTIVITY (Last 2 min)")
    print("-" * 40)
    if data['recent_events']:
        activity_count = {}
        for event in data['recent_events']:
            msg_type = event['type']
            activity_count[msg_type] = activity_count.get(msg_type, 0) + 1
        
        for msg_type, count in sorted(activity_count.items(), key=lambda x: x[1], reverse=True):
            print(f"{msg_type}: {count} messages")
    else:
        print("ℹ️  No recent activity")
    
    print()
    print("Press Ctrl+C to exit | Updates every 2 seconds")

def main():
    """Main monitoring loop"""
    print("Starting LogSplitter Real-Time Monitor...")
    time.sleep(1)
    
    try:
        while True:
            data = get_latest_data()
            display_dashboard(data)
            time.sleep(2)
    
    except KeyboardInterrupt:
        clear_screen()
        print("👋 LogSplitter Monitor stopped by user")
    except Exception as e:
        print(f"❌ Monitor error: {e}")

if __name__ == "__main__":
    main()