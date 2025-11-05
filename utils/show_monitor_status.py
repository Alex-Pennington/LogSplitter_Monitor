#!/usr/bin/env python3
"""
LogSplitter Monitor Status Dashboard

Display current status of all monitor sensors with last readings and age.
Similar to show_telemetry_status.py but for monitor sensor data.
"""

import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

DB_FILE = Path(__file__).parent / 'monitor_data.db'

def format_age(timestamp_str: str) -> str:
    """Format timestamp age in human-readable format"""
    try:
        # Parse UTC timestamp from database
        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        
        # Calculate age
        now = datetime.now(timezone.utc)
        age_seconds = (now - ts).total_seconds()
        
        if age_seconds < 60:
            return f"{int(age_seconds)}s ago"
        elif age_seconds < 3600:
            return f"{int(age_seconds/60)}m ago"
        elif age_seconds < 86400:
            return f"{int(age_seconds/3600)}h ago"
        else:
            return f"{int(age_seconds/86400)}d ago"
    except Exception as e:
        return "unknown age"

def get_sensor_status(db_path: str) -> List[Tuple]:
    """Get latest reading for each sensor type"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get latest reading for each sensor type
    cursor.execute('''
        SELECT 
            sensor_type,
            sensor_name,
            value,
            unit,
            received_timestamp,
            COUNT(*) as total_readings
        FROM sensor_readings
        WHERE id IN (
            SELECT MAX(id) 
            FROM sensor_readings 
            GROUP BY sensor_type, sensor_name
        )
        GROUP BY sensor_type, sensor_name
        ORDER BY sensor_type, sensor_name
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return results

def get_weight_status(db_path: str) -> Tuple:
    """Get latest weight reading"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            weight,
            raw_value,
            is_calibrated,
            received_timestamp,
            COUNT(*) as total_readings
        FROM weight_readings
        WHERE id = (SELECT MAX(id) FROM weight_readings)
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    return result

def get_digital_input_status(db_path: str) -> List[Tuple]:
    """Get latest state for each digital input pin"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            pin,
            state,
            received_timestamp,
            COUNT(*) as total_changes
        FROM digital_inputs
        WHERE id IN (
            SELECT MAX(id) 
            FROM digital_inputs 
            GROUP BY pin
        )
        GROUP BY pin
        ORDER BY pin
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return results

def get_system_status(db_path: str) -> Tuple:
    """Get latest system status"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            uptime_seconds,
            free_memory,
            received_timestamp,
            COUNT(*) as total_updates
        FROM system_status
        WHERE id = (SELECT MAX(id) FROM system_status)
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    return result

def get_database_stats(db_path: str) -> Dict:
    """Get overall database statistics"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {}
    
    # Count records in each table
    cursor.execute('SELECT COUNT(*) FROM sensor_readings')
    stats['sensor_readings'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM weight_readings')
    stats['weight_readings'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM digital_inputs')
    stats['digital_inputs'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM system_status')
    stats['system_status'] = cursor.fetchone()[0]
    
    # Get oldest and newest timestamps
    cursor.execute('''
        SELECT MIN(received_timestamp), MAX(received_timestamp)
        FROM sensor_readings
    ''')
    result = cursor.fetchone()
    stats['oldest'] = result[0]
    stats['newest'] = result[1]
    
    conn.close()
    
    return stats

def print_status(db_path: str, verbose: bool = False):
    """Print monitor status dashboard"""
    
    print("\n" + "="*80)
    print("LogSplitter Monitor Status".center(80))
    print("="*80)
    
    # Database statistics
    if verbose:
        stats = get_database_stats(db_path)
        print(f"\nDatabase: {db_path}")
        print(f"Total Records: {sum([stats['sensor_readings'], stats['weight_readings'], stats['digital_inputs'], stats['system_status']])}")
        print(f"  Sensor Readings: {stats['sensor_readings']}")
        print(f"  Weight Readings: {stats['weight_readings']}")
        print(f"  Digital Inputs: {stats['digital_inputs']}")
        print(f"  System Status: {stats['system_status']}")
        if stats['oldest'] and stats['newest']:
            print(f"Data Range: {stats['oldest']} to {stats['newest']}")
        print()
    
    # Sensor readings
    print("\n" + "-"*80)
    print("SENSOR READINGS")
    print("-"*80)
    print(f"{'Type':<15} {'Name':<15} {'Value':<15} {'Unit':<10} {'Age':<15} {'Count':<10}")
    print("-"*80)
    
    sensors = get_sensor_status(db_path)
    if sensors:
        for sensor_type, sensor_name, value, unit, timestamp, count in sensors:
            age = format_age(timestamp)
            name_display = sensor_name or "—"
            unit_display = unit or ""
            print(f"{sensor_type:<15} {name_display:<15} {value:<15.2f} {unit_display:<10} {age:<15} {count:<10}")
    else:
        print("No sensor readings found")
    
    # Weight readings
    print("\n" + "-"*80)
    print("WEIGHT SENSOR")
    print("-"*80)
    
    weight = get_weight_status(db_path)
    if weight:
        weight_val, raw_val, is_cal, timestamp, count = weight
        age = format_age(timestamp)
        cal_status = "✓ Calibrated" if is_cal else "⚠ Uncalibrated"
        print(f"Weight: {weight_val:.2f} (raw: {raw_val}) - {cal_status}")
        print(f"Last Update: {age} ({count} total readings)")
    else:
        print("No weight readings found")
    
    # Digital inputs
    print("\n" + "-"*80)
    print("DIGITAL INPUTS")
    print("-"*80)
    print(f"{'Pin':<10} {'State':<15} {'Age':<15} {'Changes':<10}")
    print("-"*80)
    
    inputs = get_digital_input_status(db_path)
    if inputs:
        for pin, state, timestamp, changes in inputs:
            age = format_age(timestamp)
            state_display = "HIGH" if state else "LOW"
            print(f"{pin:<10} {state_display:<15} {age:<15} {changes:<10}")
    else:
        print("No digital input data found")
    
    # System status
    print("\n" + "-"*80)
    print("SYSTEM STATUS")
    print("-"*80)
    
    system = get_system_status(db_path)
    if system:
        uptime, memory, timestamp, count = system
        age = format_age(timestamp)
        if uptime:
            uptime_hours = uptime / 3600
            print(f"Uptime: {uptime_hours:.2f} hours ({uptime}s)")
        if memory:
            memory_kb = memory / 1024
            print(f"Free Memory: {memory_kb:.2f} KB ({memory} bytes)")
        print(f"Last Update: {age} ({count} total updates)")
    else:
        print("No system status data found")
    
    print("\n" + "="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Display LogSplitter Monitor sensor status')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show verbose output with database statistics')
    parser.add_argument('--db', type=str, default=str(DB_FILE),
                       help='Path to monitor database file')
    
    args = parser.parse_args()
    
    if not Path(args.db).exists():
        print(f"Error: Database file not found: {args.db}")
        return 1
    
    print_status(args.db, args.verbose)
    return 0

if __name__ == "__main__":
    exit(main())
