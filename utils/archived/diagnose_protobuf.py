#!/usr/bin/env python3
"""
Diagnostic script to analyze protobuf message structure
"""
import sqlite3
import struct

db_path = '/home/rayvn/monitor/LogSplitter_Monitor/utils/logsplitter_data.db'

print("=== Protobuf Message Structure Analysis ===\n")

# Get a recent SYSTEM_STATUS message from MQTT logs
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get the most recent message of each major type
for msg_type, msg_name in [(16, 'DIGITAL_INPUT'), (17, 'DIGITAL_OUTPUT'), 
                             (18, 'RELAY_EVENT'), (19, 'PRESSURE'),
                             (22, 'SYSTEM_STATUS'), (23, 'SEQUENCE_EVENT')]:
    cursor.execute("""
        SELECT raw_size, received_timestamp 
        FROM telemetry 
        WHERE message_type = ? AND message_type_name = ?
        ORDER BY received_timestamp DESC 
        LIMIT 1
    """, (msg_type, msg_name))
    
    row = cursor.fetchone()
    if row:
        size, timestamp = row
        print(f"{msg_name} (0x{msg_type:02X}):")
        print(f"  Raw size: {size} bytes")
        print(f"  Header size: 7 bytes (size + type + seq + timestamp)")
        print(f"  Payload size: {size - 7} bytes")
        print(f"  Last seen: {timestamp}")
        print()

conn.close()

print("\n=== Expected Payload Sizes ===")
print("DIGITAL_INPUT (0x10): 4 bytes minimum")
print("DIGITAL_OUTPUT (0x11): 3 bytes minimum")
print("RELAY_EVENT (0x12): 3 bytes minimum")
print("PRESSURE (0x13): 9 bytes minimum")
print("SYSTEM_STATUS (0x16): 10 bytes minimum")
print("SEQUENCE_EVENT (0x17): 3 bytes minimum")
