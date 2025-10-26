#!/usr/bin/env python3
"""
Test the new message parsing functionality
"""

import json
from datetime import datetime, timezone
from logsplitter_influx_collector import LogSplitterInfluxCollector

def test_parsing():
    """Test the new status message parsing"""
    
    # Mock config
    config = {
        "mqtt": {"host": "test", "port": 1883, "keepalive": 60},
        "influxdb": {"url": "test", "token": "test", "org": "test", "bucket": "test"},
        "log_level": "INFO"
    }
    
    collector = LogSplitterInfluxCollector(config)
    timestamp = datetime.now(timezone.utc)
    
    # Test messages we've seen in the system
    test_messages = [
        "6728710|E-STOP ACTIVATED - Emergency shutdown initiated",
        "6716093|SAFETY: Engine stopped via relay R8",
        "System: uptime=3630s state=IDLE",
        "EXTENDING->WAIT_EXTEND_LIMIT",
        "RETRACTING->IDLE", 
        "WAIT_RETRACT_LIMIT->IDLE",
        "Subsystem timing issues detected - generating report",
        "Monitor: sensors=OK weight=calibrated temp=72.5F uptime=1234s"
    ]
    
    print("=== New Status Message Parsing Test ===")
    print()
    
    for message in test_messages:
        print(f"Input: {message}")
        points = collector._parse_status_message(message, timestamp)
        
        if points:
            for point in points:
                # Convert point to dict-like representation for display
                measurement = point._name
                tags = point._tags or {}
                fields = point._fields or {}
                
                print(f"  → Measurement: {measurement}")
                if tags:
                    print(f"    Tags: {tags}")
                if fields:
                    print(f"    Fields: {fields}")
        else:
            print("  → No parsed data")
        print()
        
    # Test monitor status parsing  
    print("=== Monitor Status Parsing ===")
    monitor_message = "Monitor: sensors=OK weight=calibrated temp=72.5F uptime=1234s"
    print(f"Input: {monitor_message}")
    
    points = collector._parse_monitor_status(monitor_message, timestamp)
    for point in points:
        measurement = point._name
        tags = point._tags or {}
        fields = point._fields or {}
        
        print(f"  → Measurement: {measurement}")
        if tags:
            print(f"    Tags: {tags}")
        if fields:
            print(f"    Fields: {fields}")
    print()
    
    print("=== Dashboard Query Examples ===")
    print("With this parsed data, dashboard queries become much simpler:")
    print()
    print("E-Stop Status:")
    print('  from(bucket: "mqtt") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "controller_estop") |> filter(fn: (r) => r._field == "active") |> last()')
    print()
    print("Engine Status:")
    print('  from(bucket: "mqtt") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "controller_engine") |> filter(fn: (r) => r._field == "running") |> last()')
    print()
    print("System Uptime:")
    print('  from(bucket: "mqtt") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "controller_system_parsed") |> filter(fn: (r) => r._field == "uptime_seconds") |> last()')
    print()
    print("Sequence State:")
    print('  from(bucket: "mqtt") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "controller_sequence_parsed") |> filter(fn: (r) => r._field == "idle") |> last()')

if __name__ == "__main__":
    test_parsing()