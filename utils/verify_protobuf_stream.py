#!/usr/bin/env python3
"""
Protobuf Stream Verification Tool

Subscribes to MQTT and verifies that all received protobuf messages match
the official controller_telemetry.proto specification (types 0x10-0x17).

This tool:
1. Captures raw binary messages from controller/protobuff
2. Validates message structure and type codes
3. Detects corruption, invalid types, or malformed messages
4. Provides detailed hexdumps of problematic messages
5. Reports statistics on message type distribution
"""

import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
from collections import Counter
from typing import Dict, Any

# Load configuration
def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found")
        exit(1)

config = load_config()
MQTT_BROKER = config['mqtt']['host']
MQTT_PORT = config['mqtt']['port']
MQTT_USER = config['mqtt']['username']
MQTT_PASS = config['mqtt']['password']
MQTT_TOPIC = 'controller/protobuff'

# Valid protobuf message types from controller_telemetry.proto
VALID_MESSAGE_TYPES = {
    0x10: 'DIGITAL_INPUT',
    0x11: 'DIGITAL_OUTPUT',
    0x12: 'RELAY_EVENT',
    0x13: 'PRESSURE',
    0x14: 'SYSTEM_ERROR',
    0x15: 'SAFETY_EVENT',
    0x16: 'SYSTEM_STATUS',
    0x17: 'SEQUENCE_EVENT',
}

# Expected payload sizes (excluding 6-byte header)
# NOTE: Controller sends size byte = sizeof(struct) which does NOT include the size byte itself
# So actual wire format is: [struct_size][header(6)][payload(N)]
# where struct_size = 6 + N (not including the size byte)
EXPECTED_PAYLOAD_SIZES = {
    0x10: 4,   # DigitalInputEvent: header(6) + payload(4) = 10 on wire
    0x11: 3,   # DigitalOutputEvent: header(6) + payload(3) = 9 on wire  
    0x12: 3,   # RelayEvent: header(6) + payload(3) = 9 on wire
    0x13: 8,   # PressureReading: header(6) + payload(8) = 14 on wire
    0x14: range(3, 28),  # SystemError (variable 3-27 bytes)
    0x15: 3,   # SafetyEvent: header(6) + payload(3) = 9 on wire
    0x16: 12,  # SystemStatus: header(6) + payload(12) = 18 on wire
    0x17: 4,   # SequenceEvent: header(6) + payload(4) = 10 on wire
}

# Statistics
stats = {
    'total_messages': 0,
    'valid_messages': 0,
    'invalid_type': 0,
    'invalid_size': 0,
    'malformed': 0,
    'message_types': Counter(),
    'invalid_types_seen': Counter(),
    'start_time': time.time()
}

def hexdump(data: bytes, prefix: str = "") -> str:
    """Create a hexdump string for binary data"""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"{prefix}{i:04X}: {hex_part:<48}  {ascii_part}")
    return '\n'.join(lines)

def validate_message(data: bytes) -> Dict[str, Any]:
    """Validate a protobuf message structure"""
    result = {
        'valid': False,
        'issues': [],
        'msg_type': None,
        'msg_size': None,
        'sequence_id': None,
        'timestamp': None,
        'payload_size': None
    }
    
    # Check minimum size (1 size + 6 header = 7 bytes minimum for struct, 8 total with size byte)
    if len(data) < 7:
        result['issues'].append(f"Too short: {len(data)} bytes (minimum 7)")
        return result
    
    # Extract size byte (first byte) - this is the struct size WITHOUT the size byte itself
    struct_size = data[0]
    result['msg_size'] = struct_size
    
    # Actual message length should be struct_size + 1 (for the size byte)
    expected_length = struct_size + 1
    if expected_length != len(data):
        result['issues'].append(f"Size mismatch: size byte={struct_size}, struct expects {expected_length} bytes total, got {len(data)}")
        return result
    
    # Check maximum size (6 header + 27 max payload = 33 bytes struct, 34 total)
    if struct_size > 33:
        result['issues'].append(f"Too large: {struct_size} bytes struct (maximum 33)")
        return result
    
    # Check minimum struct size (6 header + 3 min payload = 9 minimum)
    if struct_size < 9:
        result['issues'].append(f"Too small: {struct_size} bytes struct (minimum 9)")
        return result
    
    # Extract header fields
    msg_type = data[1]
    result['msg_type'] = msg_type
    result['sequence_id'] = data[2]
    result['timestamp'] = int.from_bytes(data[3:7], byteorder='little')
    
    # Validate message type
    if msg_type not in VALID_MESSAGE_TYPES:
        result['issues'].append(f"Invalid message type: 0x{msg_type:02X}")
        return result
    
    # Calculate payload size: struct_size - header(6) = payload size
    payload_size = struct_size - 6
    result['payload_size'] = payload_size
    
    # Validate payload size for this message type
    expected = EXPECTED_PAYLOAD_SIZES[msg_type]
    if isinstance(expected, range):
        if payload_size not in expected:
            result['issues'].append(f"Invalid payload size: {payload_size} bytes (expected {min(expected)}-{max(expected)})")
            return result
    else:
        if payload_size != expected:
            result['issues'].append(f"Invalid payload size: {payload_size} bytes (expected {expected})")
            return result
    
    # All checks passed
    result['valid'] = True
    return result

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✓ Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"✓ Subscribed to {MQTT_TOPIC}")
        print("\n" + "="*80)
        print("Protobuf Stream Verification - Press Ctrl+C to stop")
        print("="*80)
        print(f"Valid message types: {', '.join(f'0x{t:02X} ({n})' for t, n in VALID_MESSAGE_TYPES.items())}")
        print("="*80 + "\n")
    else:
        print(f"✗ Connection failed with code {rc}")

def on_message(client, userdata, msg):
    stats['total_messages'] += 1
    data = msg.payload
    
    # Validate message structure
    validation = validate_message(data)
    
    if validation['valid']:
        stats['valid_messages'] += 1
        msg_type = validation['msg_type']
        msg_name = VALID_MESSAGE_TYPES[msg_type]
        stats['message_types'][msg_name] += 1
        
        # Print valid message summary (compact)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✓ {msg_name:18s} "
              f"seq={validation['sequence_id']:3d} "
              f"struct={validation['msg_size']:2d} "
              f"payload={validation['payload_size']:2d}B "
              f"ts={validation['timestamp']}")
    else:
        # Invalid message - print detailed analysis
        stats['malformed'] += 1
        
        if validation['msg_type'] is not None and validation['msg_type'] not in VALID_MESSAGE_TYPES:
            stats['invalid_type'] += 1
            stats['invalid_types_seen'][validation['msg_type']] += 1
        
        if 'size mismatch' in str(validation['issues']).lower() or 'payload size' in str(validation['issues']).lower():
            stats['invalid_size'] += 1
        
        print(f"\n{'='*80}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✗ INVALID MESSAGE #{stats['malformed']}")
        print(f"{'='*80}")
        print(f"Issues: {', '.join(validation['issues'])}")
        print(f"Message Type: 0x{validation['msg_type']:02X} ({validation['msg_type']})" if validation['msg_type'] is not None else "Message Type: Unknown")
        print(f"Size Byte: {validation['msg_size']}, Actual Length: {len(data)}")
        print(f"\nHexdump ({len(data)} bytes):")
        print(hexdump(data, "  "))
        print(f"{'='*80}\n")
    
    # Print statistics every 100 messages
    if stats['total_messages'] % 100 == 0:
        print_statistics()

def print_statistics():
    """Print current statistics"""
    elapsed = time.time() - stats['start_time']
    rate = stats['total_messages'] / elapsed if elapsed > 0 else 0
    
    print(f"\n{'─'*80}")
    print(f"Statistics ({int(elapsed)}s elapsed, {rate:.1f} msg/s)")
    print(f"{'─'*80}")
    print(f"Total Messages:    {stats['total_messages']}")
    print(f"✓ Valid:           {stats['valid_messages']} ({100*stats['valid_messages']/max(1,stats['total_messages']):.1f}%)")
    print(f"✗ Invalid Type:    {stats['invalid_type']}")
    print(f"✗ Invalid Size:    {stats['invalid_size']}")
    print(f"✗ Malformed:       {stats['malformed']}")
    
    if stats['message_types']:
        print(f"\nValid Message Distribution:")
        for msg_name, count in stats['message_types'].most_common():
            pct = 100 * count / max(1, stats['valid_messages'])
            print(f"  {msg_name:20s}: {count:5d} ({pct:5.1f}%)")
    
    if stats['invalid_types_seen']:
        print(f"\nInvalid Types Detected:")
        for msg_type, count in stats['invalid_types_seen'].most_common():
            print(f"  0x{msg_type:02X}: {count:5d} occurrences")
    
    print(f"{'─'*80}\n")

def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\nStopping stream verification...")
        print_statistics()
        print("\nVerification complete.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == '__main__':
    main()
