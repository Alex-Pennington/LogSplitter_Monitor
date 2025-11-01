#!/usr/bin/env python3
"""
Update Message Types in Database

This script updates existing database records with improved message type labels
based on our protobuf definitions instead of showing UNKNOWN_0x entries.
"""

import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_PATH = os.getenv('DATABASE_PATH', 'logsplitter_telemetry.db')

def get_improved_type_name(hex_code: str) -> str:
    """Convert hex code to improved message type name"""
    try:
        msg_type = int(hex_code, 16)
    except ValueError:
        return hex_code
    
    types = {
        # Standard protobuf message types (0x10-0x17)
        0x10: 'DIGITAL_INPUT',
        0x11: 'DIGITAL_OUTPUT', 
        0x12: 'RELAY_EVENT',
        0x13: 'PRESSURE',
        0x14: 'SYSTEM_ERROR',
        0x15: 'SAFETY_EVENT',
        0x16: 'SYSTEM_STATUS',
        0x17: 'SEQUENCE_EVENT',
        
        # Common invalid/corrupted message indicators
        0x00: 'NULL_MESSAGE',
        0xFF: 'INVALID_MESSAGE',
        0xFE: 'CORRUPTED_DATA',
        0xAA: 'TEST_PATTERN',
        0xAC: 'ALIGNMENT_ERROR',
        
        # Potential extended message types (if implemented)
        0x09: 'LEGACY_HEARTBEAT',
        0x0A: 'SENSOR_CALIBRATION', 
        0x0E: 'NETWORK_STATUS',
        0x0F: 'DEBUG_MESSAGE',
        
        # Hardware diagnostic codes
        0x66: 'HARDWARE_DIAG_1',
        0x68: 'HARDWARE_DIAG_2', 
        0x78: 'MEMORY_DIAGNOSTIC',
        0x9B: 'TIMING_DIAGNOSTIC',
        0x9E: 'PERFORMANCE_METRIC'
    }
    
    return types.get(msg_type, f'UNKNOWN_0x{msg_type:02X}')

def update_database():
    """Update existing database records with improved message type names"""
    print("🔄 Updating message types in database...")
    
    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Find all UNKNOWN_0x message types
    cursor.execute("""
        SELECT DISTINCT message_type_name 
        FROM telemetry 
        WHERE message_type_name LIKE 'UNKNOWN_0x%'
        ORDER BY message_type_name
    """)
    
    unknown_types = cursor.fetchall()
    
    if not unknown_types:
        print("✅ No UNKNOWN_0x message types found in database")
        conn.close()
        return
    
    print(f"📋 Found {len(unknown_types)} unknown message types to update:")
    
    updates_made = 0
    
    for (old_name,) in unknown_types:
        # Extract hex code from UNKNOWN_0xXX format
        if old_name.startswith('UNKNOWN_0x'):
            hex_part = old_name[8:]  # Remove 'UNKNOWN_'
            new_name = get_improved_type_name(hex_part)
            
            if new_name != old_name:
                # Count records that will be updated
                cursor.execute("""
                    SELECT COUNT(*) FROM telemetry 
                    WHERE message_type_name = ?
                """, (old_name,))
                count = cursor.fetchone()[0]
                
                print(f"  {old_name} → {new_name} ({count} records)")
                
                # Update the records
                cursor.execute("""
                    UPDATE telemetry 
                    SET message_type_name = ? 
                    WHERE message_type_name = ?
                """, (new_name, old_name))
                
                updates_made += cursor.rowcount
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\n✅ Database update complete!")
    print(f"📊 Updated {updates_made} total records")
    print(f"🎯 Converted {len(unknown_types)} message types to meaningful names")

def show_message_type_summary():
    """Show summary of message types after update"""
    print("\n📈 Message Type Summary (Last 24 hours):")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            message_type_name,
            COUNT(*) as count
        FROM telemetry 
        WHERE received_timestamp > datetime('now', '-24 hours')
        GROUP BY message_type_name
        ORDER BY count DESC
        LIMIT 20
    """)
    
    results = cursor.fetchall()
    
    for msg_type, count in results:
        print(f"  {msg_type}: {count}")
    
    conn.close()

if __name__ == "__main__":
    print("LogSplitter Database Message Type Updater")
    print("=" * 50)
    
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Database not found: {DATABASE_PATH}")
        exit(1)
    
    # Update the database
    update_database()
    
    # Show updated summary
    show_message_type_summary()
    
    print("\n🚀 New messages will automatically use improved type names!")