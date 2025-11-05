#!/usr/bin/env python3
"""
LogSplitter Telemetry Status Display

Shows the last value and timestamp for every telemetry message type
with age calculation for quick status overview.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple


def format_age(timestamp_str: str) -> str:
    """Convert timestamp to human-readable age"""
    try:
        # Parse timestamp (SQLite stores as UTC)
        ts = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
        # Get current UTC time for comparison
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        delta = now - ts
        
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds/60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds/3600)}h ago"
        else:
            return f"{int(seconds/86400)}d ago"
    except:
        return "unknown"


def get_telemetry_status(db_path: str = 'logsplitter_data.db') -> List[Dict[str, Any]]:
    """Query database for latest telemetry data"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get latest message for each type
    query = """
        SELECT 
            message_type,
            message_type_name,
            COUNT(*) as total_count,
            MAX(received_timestamp) as last_seen,
            (SELECT payload_json FROM telemetry t2 
             WHERE t2.message_type = t1.message_type 
             ORDER BY received_timestamp DESC LIMIT 1) as last_payload_json
        FROM telemetry t1
        GROUP BY message_type, message_type_name
        ORDER BY last_seen DESC
    """
    
    cursor.execute(query)
    results = []
    
    for row in cursor.fetchall():
        msg_type, msg_type_name, total_count, last_seen, payload_json = row
        
        # Parse decoded data
        parsed_data = {}
        if payload_json:
            try:
                parsed_data = json.loads(payload_json)
            except:
                parsed_data = {"raw": payload_json}
        
        # Calculate age
        age = format_age(last_seen) if last_seen else "never"
        
        # Extract key values based on message type
        key_value = extract_key_value(msg_type, msg_type_name, parsed_data)
        
        results.append({
            'type': msg_type,
            'type_name': msg_type_name,
            'count': total_count,
            'last_seen': last_seen,
            'age': age,
            'value': key_value,
            'decoded': parsed_data
        })
    
    conn.close()
    return results


def extract_key_value(msg_type: int, msg_type_name: str, data: Dict[str, Any]) -> str:
    """Extract the most important value from decoded data"""
    
    if not data:
        return "no data"
    
    # PRESSURE (0x13 = 19)
    if msg_type == 19 or 'pressure_psi' in data:
        psi = data.get('pressure_psi', 0)
        sensor = data.get('sensor_pin', '?')
        return f"A{sensor}: {psi:.1f} PSI"
    
    # DIGITAL_INPUT (0x10 = 16)
    if msg_type == 16 or 'DIGITAL_INPUT' in msg_type_name:
        pin = data.get('pin', '?')
        state = data.get('state_name', data.get('state', '?'))
        input_type = data.get('input_type_name', '')
        return f"Pin {pin}: {state} ({input_type})"
    
    # DIGITAL_OUTPUT (0x11 = 17)
    if msg_type == 17 or 'DIGITAL_OUTPUT' in msg_type_name:
        pin = data.get('pin', '?')
        state = data.get('state_name', data.get('state', '?'))
        output_type = data.get('output_type_name', '')
        return f"Pin {pin}: {state} ({output_type})"
    
    # RELAY_EVENT (0x12 = 18)
    if msg_type == 18 or 'RELAY_EVENT' in msg_type_name:
        relay = data.get('relay_number', '?')
        state = 'ON' if data.get('state') else 'OFF'
        relay_type = data.get('relay_type_name', '')
        return f"R{relay}: {state} ({relay_type})"
    
    # SYSTEM_STATUS (0x16 = 22)
    if msg_type == 22 or 'SYSTEM_STATUS' in msg_type_name:
        uptime = data.get('uptime_seconds', 0)
        mem = data.get('free_memory_bytes', 0)
        freq = data.get('loop_frequency_hz', 0)
        return f"Uptime: {uptime:.1f}s, Mem: {mem}B, Freq: {freq}Hz"
    
    # SEQUENCE_EVENT (0x17 = 23)
    if msg_type == 23 or 'SEQUENCE_EVENT' in msg_type_name:
        event = data.get('event_type_name', 'Unknown')
        step = data.get('step_number', '?')
        elapsed = data.get('elapsed_time_ms', 0)
        return f"{event} (Step {step}, {elapsed}ms)"
    
    # SAFETY_EVENT (0x15 = 21)
    if msg_type == 21 or 'SAFETY_EVENT' in msg_type_name:
        event = data.get('event_type_name', 'Unknown')
        status = data.get('status', '?')
        return f"{event}: {status}"
    
    # SYSTEM_ERROR (0x14 = 20)
    if msg_type == 20 or 'SYSTEM_ERROR' in msg_type_name:
        error = data.get('error_name', 'Unknown')
        severity = data.get('severity_name', '?')
        desc = data.get('description', '')
        return f"{error} ({severity}): {desc}"
    
    # Default: return first few fields
    if len(data) > 0:
        first_key = list(data.keys())[0]
        return f"{first_key}={data[first_key]}"
    
    return "no value"


def print_telemetry_status(results: List[Dict[str, Any]], verbose: bool = False):
    """Print formatted telemetry status"""
    
    print("\n" + "="*100)
    print("LogSplitter Telemetry Status")
    print("="*100)
    print(f"{'Type':<25} {'Count':>8} {'Age':>12} {'Last Value':<50}")
    print("-"*100)
    
    for item in results:
        type_display = f"{item['type_name']} (0x{item['type']:02X})"
        print(f"{type_display:<25} {item['count']:>8} {item['age']:>12} {item['value']:<50}")
        
        if verbose and item['last_seen']:
            print(f"  └─ Last seen: {item['last_seen']}")
    
    print("-"*100)
    print(f"Total message types: {len(results)}")
    print()


def print_detailed_status(results: List[Dict[str, Any]]):
    """Print detailed status with full decoded data"""
    
    print("\n" + "="*100)
    print("LogSplitter Detailed Telemetry Status")
    print("="*100)
    
    for item in results:
        print(f"\n[{item['type_name']}] (Type: 0x{item['type']:02X})")
        print(f"  Count:     {item['count']:,} messages")
        print(f"  Last Seen: {item['last_seen']} ({item['age']})")
        print(f"  Value:     {item['value']}")
        
        if item['decoded']:
            print(f"  Decoded Data:")
            for key, value in item['decoded'].items():
                if isinstance(value, float):
                    print(f"    {key}: {value:.4f}")
                else:
                    print(f"    {key}: {value}")
    
    print("\n" + "="*100)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Show LogSplitter telemetry status')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show timestamps')
    parser.add_argument('-d', '--detailed', action='store_true', help='Show detailed decoded data')
    parser.add_argument('--db', default='logsplitter_data.db', help='Database path')
    parser.add_argument('-t', '--type', type=str, help='Filter by message type name')
    
    args = parser.parse_args()
    
    results = get_telemetry_status(args.db)
    
    # Filter by type if requested
    if args.type:
        results = [r for r in results if args.type.upper() in r['type_name'].upper()]
    
    if args.detailed:
        print_detailed_status(results)
    else:
        print_telemetry_status(results, args.verbose)


if __name__ == '__main__':
    main()
