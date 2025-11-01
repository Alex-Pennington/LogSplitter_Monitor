#!/usr/bin/env python3
"""
LogSplitter Database Analyzer

Real-time analysis tools for LogSplitter operational data.
Use this to query and analyze cycle operations, operator signals, and basket exchange patterns.

Usage:
    python3 database_analyzer.py [command] [options]

Commands:
    live-cycles     - Monitor cycles in real-time
    operator-signals - Analyze operator signal patterns
    basket-exchange - Track basket exchange operations
    pressure-profile - Analyze pressure patterns during cycles
    query          - Custom SQL queries
    stats          - Quick operational statistics
"""

import sqlite3
import json
import time
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DATABASE_PATH = os.getenv('DATABASE_PATH', 'logsplitter_telemetry.db')

class DatabaseAnalyzer:
    """LogSplitter database analysis tools"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def live_cycle_monitor(self, follow: bool = True):
        """Monitor cycles in real-time"""
        print("🔄 LogSplitter Live Cycle Monitor")
        print("=" * 50)
        
        last_timestamp = datetime.now() - timedelta(minutes=5)
        
        while True:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Get recent sequence events
                cursor.execute("""
                    SELECT 
                        received_timestamp,
                        controller_timestamp,
                        payload_json,
                        sequence_id
                    FROM telemetry 
                    WHERE message_type_name = 'SEQUENCE_EVENT'
                    AND received_timestamp > ?
                    ORDER BY received_timestamp ASC
                """, (last_timestamp.isoformat(),))
                
                events = cursor.fetchall()
                
                for event in events:
                    received_time = datetime.fromisoformat(event[0])
                    controller_time = event[1]
                    payload = json.loads(event[2])
                    sequence_id = event[3]
                    
                    event_type = payload.get('event_type_name', 'UNKNOWN')
                    step_number = payload.get('step_number', 0)
                    elapsed_time = payload.get('elapsed_time_ms', 0)
                    
                    timestamp_str = received_time.strftime("%H:%M:%S")
                    
                    # Color coding for different events
                    if 'STARTED' in event_type:
                        color = '\033[92m'  # Green
                        icon = "🟢"
                    elif 'COMPLETE' in event_type:
                        color = '\033[94m'  # Blue
                        icon = "🔵"
                    elif 'ABORTED' in event_type:
                        color = '\033[93m'  # Yellow (short stroke)
                        icon = "�"
                    else:
                        color = '\033[93m'  # Yellow
                        icon = "🟡"
                    
                    reset = '\033[0m'
                    
                    print(f"{color}[{timestamp_str}] {icon} {event_type}{reset}")
                    print(f"  Sequence: {sequence_id} | Step: {step_number} | Elapsed: {elapsed_time}ms")
                    
                    if events:
                        last_timestamp = received_time
                
                conn.close()
                
                if not follow:
                    break
                    
                if events:
                    print()
                
                time.sleep(2)
                
            except KeyboardInterrupt:
                print("\n📊 Cycle monitoring stopped")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)
    
    def analyze_operator_signals(self, hours: int = 1):
        """Analyze operator signal patterns"""
        print(f"👷 Operator Signal Analysis (Last {hours} hours)")
        print("=" * 50)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get digital input events (operator signals)
        cursor.execute("""
            SELECT 
                received_timestamp,
                payload_json
            FROM telemetry 
            WHERE message_type_name = 'DIGITAL_INPUT'
            AND received_timestamp > datetime('now', '-{} hours')
            ORDER BY received_timestamp DESC
        """.format(hours))
        
        signals = cursor.fetchall()
        
        signal_counts = {}
        state_changes = []
        
        for signal in signals:
            received_time = signal[0]
            payload = json.loads(signal[1])
            
            pin = payload.get('pin', 0)
            state = payload.get('state', False)
            input_type = payload.get('input_type_name', 'UNKNOWN')
            
            # Count signal types
            if input_type not in signal_counts:
                signal_counts[input_type] = {'active': 0, 'inactive': 0}
            
            if state:
                signal_counts[input_type]['active'] += 1
            else:
                signal_counts[input_type]['inactive'] += 1
            
            # Track state changes for timing analysis
            state_changes.append({
                'timestamp': received_time,
                'pin': pin,
                'state': state,
                'type': input_type
            })
        
        # Display signal summary
        print("\n📊 Signal Summary:")
        for signal_type, counts in signal_counts.items():
            total = counts['active'] + counts['inactive']
            active_pct = (counts['active'] / total * 100) if total > 0 else 0
            print(f"  {signal_type}:")
            print(f"    Total: {total} | Active: {counts['active']} ({active_pct:.1f}%)")
        
        # Analyze operator signal patterns
        print("\n🔍 Recent Operator Signals:")
        operator_signals = [s for s in state_changes if 'OPERATOR' in s['type'] or 'MANUAL' in s['type']]
        
        for signal in operator_signals[:10]:  # Show last 10
            timestamp = datetime.fromisoformat(signal['timestamp']).strftime("%H:%M:%S")
            state_icon = "🟢" if signal['state'] else "🔴"
            print(f"  [{timestamp}] {state_icon} {signal['type']} - Pin {signal['pin']}")
        
        conn.close()
    
    def analyze_basket_exchange(self, hours: int = 2):
        """Track basket exchange operations"""
        print(f"🧺 Basket Exchange Analysis (Last {hours} hours)")
        print("=" * 50)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Look for patterns that might indicate basket exchanges
        # This typically involves operator signals, sequence starts, and relay operations
        
        cursor.execute("""
            SELECT 
                received_timestamp,
                message_type_name,
                payload_json
            FROM telemetry 
            WHERE received_timestamp > datetime('now', '-{} hours')
            AND (
                message_type_name = 'DIGITAL_INPUT' OR
                message_type_name = 'SEQUENCE_EVENT' OR
                message_type_name = 'RELAY_EVENT'
            )
            ORDER BY received_timestamp ASC
        """.format(hours))
        
        events = cursor.fetchall()
        
        # Group events into potential basket exchange sequences
        exchange_sequences = []
        current_sequence = []
        last_operator_signal = None
        
        for event in events:
            timestamp = event[0]
            msg_type = event[1]
            payload = json.loads(event[2])
            
            event_time = datetime.fromisoformat(timestamp)
            
            # Look for operator signal patterns
            if msg_type == 'DIGITAL_INPUT':
                input_type = payload.get('input_type_name', '')
                if 'OPERATOR' in input_type or 'MANUAL' in input_type:
                    if payload.get('state', False):  # Signal activated
                        if last_operator_signal and (event_time - last_operator_signal).seconds < 30:
                            # Close signals might indicate basket positioning
                            current_sequence.append({
                                'timestamp': timestamp,
                                'type': 'OPERATOR_SIGNAL',
                                'details': input_type
                            })
                        last_operator_signal = event_time
            
            # Look for sequence starts after operator signals
            elif msg_type == 'SEQUENCE_EVENT':
                event_type = payload.get('event_type_name', '')
                if 'STARTED' in event_type and current_sequence:
                    current_sequence.append({
                        'timestamp': timestamp,
                        'type': 'CYCLE_START',
                        'details': event_type
                    })
                elif 'COMPLETE' in event_type and current_sequence:
                    current_sequence.append({
                        'timestamp': timestamp,
                        'type': 'CYCLE_COMPLETE',
                        'details': event_type
                    })
                    
                    # If we have a complete sequence, save it
                    if len(current_sequence) >= 2:
                        exchange_sequences.append(current_sequence.copy())
                    current_sequence = []
        
        # Display basket exchange patterns
        print(f"\n📊 Detected {len(exchange_sequences)} potential basket exchange sequences:")
        
        for i, sequence in enumerate(exchange_sequences[-5:], 1):  # Show last 5
            start_time = datetime.fromisoformat(sequence[0]['timestamp'])
            end_time = datetime.fromisoformat(sequence[-1]['timestamp'])
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n🧺 Exchange #{i} - Duration: {duration:.1f}s")
            print(f"  Start: {start_time.strftime('%H:%M:%S')}")
            
            for step in sequence:
                step_time = datetime.fromisoformat(step['timestamp']).strftime('%H:%M:%S')
                print(f"  [{step_time}] {step['type']}: {step['details']}")
        
        conn.close()
    
    def analyze_pressure_profile(self, minutes: int = 10):
        """Analyze pressure patterns during recent cycles"""
        print(f"⚡ Pressure Profile Analysis (Last {minutes} minutes)")
        print("=" * 50)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get pressure readings
        cursor.execute("""
            SELECT 
                received_timestamp,
                controller_timestamp,
                payload_json
            FROM telemetry 
            WHERE message_type_name = 'PRESSURE'
            AND received_timestamp > datetime('now', '-{} minutes')
            ORDER BY received_timestamp ASC
        """.format(minutes))
        
        pressure_readings = cursor.fetchall()
        
        if not pressure_readings:
            print("❌ No pressure data found in the specified time range")
            return
        
        pressures = []
        max_pressure = 0
        pressure_spikes = 0
        
        for reading in pressure_readings:
            payload = json.loads(reading[2])
            pressure_psi = payload.get('pressure_psi', 0)
            sensor_pin = payload.get('sensor_pin', 0)
            fault_status = payload.get('fault_status', 'OK')
            timestamp = reading[0]
            
            pressures.append({
                'timestamp': timestamp,
                'pressure': pressure_psi,
                'sensor': sensor_pin,
                'fault': fault_status != 'OK'
            })
            
            if pressure_psi > max_pressure:
                max_pressure = pressure_psi
            
            if pressure_psi > 2500:  # High pressure threshold
                pressure_spikes += 1
        
        # Calculate statistics
        avg_pressure = sum(p['pressure'] for p in pressures) / len(pressures) if pressures else 0
        
        print(f"\n📊 Pressure Statistics:")
        print(f"  Readings: {len(pressures)}")
        print(f"  Max Pressure: {max_pressure:.1f} PSI")
        print(f"  Avg Pressure: {avg_pressure:.1f} PSI") 
        print(f"  Pressure Spikes (>2500 PSI): {pressure_spikes}")
        
        # Show recent high-pressure events
        high_pressure = [p for p in pressures if p['pressure'] > 2000]
        if high_pressure:
            print(f"\n⚡ Recent High Pressure Events:")
            for event in high_pressure[-5:]:  # Last 5
                timestamp = datetime.fromisoformat(event['timestamp']).strftime('%H:%M:%S')
                fault_icon = "⚠️" if event['fault'] else "✅"
                print(f"  [{timestamp}] {fault_icon} {event['pressure']:.1f} PSI (Sensor A{event['sensor']})")
        
        conn.close()
    
    def custom_query(self, query: str):
        """Execute custom SQL query"""
        print("🔍 Custom Query Results")
        print("=" * 50)
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            # Get column names
            columns = [description[0] for description in cursor.description]
            
            if results:
                # Print header
                print("  ".join(f"{col:15}" for col in columns))
                print("-" * (15 * len(columns)))
                
                # Print rows
                for row in results:
                    print("  ".join(f"{str(val)[:15]:15}" for val in row))
                
                print(f"\n📊 {len(results)} rows returned")
            else:
                print("❌ No results returned")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Query error: {e}")
    
    def quick_stats(self):
        """Show quick operational statistics"""
        print("📊 Quick Operational Statistics")
        print("=" * 50)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total messages by type (last hour)
        cursor.execute("""
            SELECT 
                message_type_name,
                COUNT(*) as count
            FROM telemetry 
            WHERE received_timestamp > datetime('now', '-1 hour')
            GROUP BY message_type_name
            ORDER BY count DESC
        """)
        
        message_stats = cursor.fetchall()
        
        print("\n📈 Messages (Last Hour):")
        for msg_type, count in message_stats:
            print(f"  {msg_type}: {count}")
        
        # Recent sequence events
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN payload_json LIKE '%COMPLETE%' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN payload_json LIKE '%ABORTED%' THEN 1 ELSE 0 END) as short_strokes
            FROM telemetry 
            WHERE message_type_name = 'SEQUENCE_EVENT'
            AND received_timestamp > datetime('now', '-1 hour')
        """)
        seq_stats = cursor.fetchone()
        if seq_stats and seq_stats[0] > 0:
            total, completed, short_strokes = seq_stats
            success_rate = (completed / (completed + short_strokes) * 100) if (completed + short_strokes) > 0 else 0
            
            print(f"\n🔄 Cycles (Last Hour):")
            print(f"  Total Events: {total}")
            print(f"  Completed: {completed}")
            print(f"  Short Strokes: {short_strokes}")
            print(f"  Success Rate: {success_rate:.1f}%")
        
        # System health
        cursor.execute("""
            SELECT 
                payload_json
            FROM telemetry 
            WHERE message_type_name = 'SYSTEM_STATUS'
            ORDER BY received_timestamp DESC
            LIMIT 1
        """)
        
        status_result = cursor.fetchone()
        if status_result:
            status = json.loads(status_result[0])
            uptime = status.get('uptime_minutes', 0)
            free_memory = status.get('free_memory_bytes', 0)
            active_errors = status.get('active_error_count', 0)
            
            print(f"\n💻 System Status:")
            print(f"  Uptime: {uptime:.1f} minutes")
            print(f"  Free Memory: {free_memory} bytes")
            print(f"  Active Errors: {active_errors}")
        
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='LogSplitter Database Analyzer')
    parser.add_argument('command', choices=[
        'live-cycles', 'operator-signals', 'basket-exchange', 
        'pressure-profile', 'query', 'stats'
    ], help='Analysis command to run')
    
    parser.add_argument('--hours', type=int, default=1, help='Hours of data to analyze')
    parser.add_argument('--minutes', type=int, default=10, help='Minutes of data to analyze')
    parser.add_argument('--follow', action='store_true', help='Follow live updates')
    parser.add_argument('--sql', type=str, help='SQL query for custom analysis')
    
    args = parser.parse_args()
    
    analyzer = DatabaseAnalyzer()
    
    try:
        if args.command == 'live-cycles':
            analyzer.live_cycle_monitor(follow=args.follow)
        elif args.command == 'operator-signals':
            analyzer.analyze_operator_signals(hours=args.hours)
        elif args.command == 'basket-exchange':
            analyzer.analyze_basket_exchange(hours=args.hours)
        elif args.command == 'pressure-profile':
            analyzer.analyze_pressure_profile(minutes=args.minutes)
        elif args.command == 'query':
            if args.sql:
                analyzer.custom_query(args.sql)
            else:
                print("❌ Please provide --sql query")
        elif args.command == 'stats':
            analyzer.quick_stats()
    
    except KeyboardInterrupt:
        print("\n👋 Analysis stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()