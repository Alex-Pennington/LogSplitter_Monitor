#!/usr/bin/env python3
"""
Safety Data Inspector - Query InfluxDB for safety-related data formats
"""

from influxdb_client import InfluxDBClient
import json
from datetime import datetime

def load_config():
    """Load InfluxDB configuration"""
    with open('config.json') as f:
        return json.load(f)

def inspect_safety_data():
    """Inspect all safety-related data in InfluxDB"""
    config = load_config()
    
    client = InfluxDBClient(
        url=config['influxdb']['url'],
        token=config['influxdb']['token'],
        org=config['influxdb']['org']
    )
    
    query_api = client.query_api()
    
    print("🔍 SAFETY DATA INSPECTOR")
    print("=" * 50)
    
    # 1. Check controller_system for engine/system status
    print("\n1. 📊 Controller System Status:")
    print("-" * 30)
    
    system_query = '''
    from(bucket: "mqtt")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "controller_system")
      |> limit(n: 10)
    '''
    
    try:
        result = query_api.query(system_query)
        for table in result:
            for record in table.records:
                field = record.get_field()
                value = record.get_value()
                time = record.get_time()
                tags = {k: v for k, v in record.values.items() if not k.startswith('_') and k not in ['result', 'table']}
                print(f"  Field: {field}")
                print(f"  Value: {value}")
                print(f"  Tags: {tags}")
                print(f"  Time: {time}")
                print("  ---")
    except Exception as e:
        print(f"  ❌ Error querying controller_system: {e}")
    
    # 2. Check controller_sequence for sequence states
    print("\n2. 🔄 Controller Sequence States:")
    print("-" * 35)
    
    sequence_query = '''
    from(bucket: "mqtt")
      |> range(start: -2h)
      |> filter(fn: (r) => r._measurement == "controller_sequence")
      |> limit(n: 10)
    '''
    
    try:
        result = query_api.query(sequence_query)
        states_seen = set()
        for table in result:
            for record in table.records:
                field = record.get_field()
                value = record.get_value()
                state = record.values.get('state', 'unknown')
                time = record.get_time()
                states_seen.add(state)
                print(f"  State: {state}")
                print(f"  Field: {field} = {value}")
                print(f"  Time: {time}")
                print("  ---")
        
        print(f"\n  Unique states seen: {list(states_seen)}")
    except Exception as e:
        print(f"  ❌ Error querying controller_sequence: {e}")
    
    # 3. Check for any e-stop or safety-related fields
    print("\n3. 🚨 Safety/E-Stop Related Fields:")
    print("-" * 40)
    
    # Look for any measurements with safety-related keywords
    safety_keywords = ['estop', 'emergency', 'safety', 'limit', 'input', 'relay']
    
    for keyword in safety_keywords:
        print(f"\n  Searching for '{keyword}'...")
        
        keyword_query = f'''
        from(bucket: "mqtt")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement =~ /{keyword}/ or r._field =~ /{keyword}/)
          |> group(columns: ["_measurement", "_field"])
          |> distinct(column: "_value")
          |> keep(columns: ["_measurement", "_field"])
          |> limit(n: 5)
        '''
        
        try:
            result = query_api.query(keyword_query)
            found = False
            for table in result:
                for record in table.records:
                    measurement = record.get_value_by_key('_measurement')
                    field = record.get_value_by_key('_field')
                    print(f"    Found: {measurement} -> {field}")
                    found = True
            if not found:
                print(f"    No matches for '{keyword}'")
        except Exception as e:
            print(f"    Error searching for '{keyword}': {e}")
    
    # 4. Check controller_log for safety messages
    print("\n4. 📋 Recent Controller Log Messages (Safety Related):")
    print("-" * 55)
    
    log_query = '''
    from(bucket: "mqtt")
      |> range(start: -2h)
      |> filter(fn: (r) => r._measurement == "controller_log")
      |> filter(fn: (r) => r.level == "crit" or r.level == "error" or r.level == "warn")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 10)
    '''
    
    try:
        result = query_api.query(log_query)
        for table in result:
            for record in table.records:
                field = record.get_field()
                value = record.get_value()
                level = record.values.get('level', 'unknown')
                time = record.get_time()
                print(f"  [{level.upper()}] {field}: {value}")
                print(f"    Time: {time}")
                print("  ---")
    except Exception as e:
        print(f"  ❌ Error querying controller_log: {e}")
    
    # 5. Check for any input measurements (potential e-stop/limit switches)
    print("\n5. 🔌 Input/Digital Signal Measurements:")
    print("-" * 45)
    
    # Look for measurements containing 'input' or digital signals
    input_query = '''
    from(bucket: "mqtt")
      |> range(start: -24h)
      |> group(columns: ["_measurement"])
      |> distinct(column: "_measurement")
      |> filter(fn: (r) => r._value =~ /input/ or r._value =~ /digital/ or r._value =~ /switch/)
    '''
    
    try:
        result = query_api.query(input_query)
        for table in result:
            for record in table.records:
                measurement = record.get_value()
                print(f"  Found input measurement: {measurement}")
                
                # Get sample data from this measurement
                sample_query = f'''
                from(bucket: "mqtt")
                  |> range(start: -1h)
                  |> filter(fn: (r) => r._measurement == "{measurement}")
                  |> limit(n: 3)
                '''
                
                sample_result = query_api.query(sample_query)
                for sample_table in sample_result:
                    for sample_record in sample_table.records:
                        field = sample_record.get_field()
                        value = sample_record.get_value()
                        tags = {k: v for k, v in sample_record.values.items() if not k.startswith('_') and k not in ['result', 'table']}
                        print(f"    Field: {field} = {value}, Tags: {tags}")
    except Exception as e:
        print(f"  ❌ Error querying input measurements: {e}")
    
    # 6. Check all measurements for any with 'status' fields
    print("\n6. ⚡ Status Fields Across All Measurements:")
    print("-" * 50)
    
    status_query = '''
    from(bucket: "mqtt")
      |> range(start: -24h)
      |> filter(fn: (r) => r._field =~ /status/ or r._field =~ /state/ or r._field =~ /active/)
      |> group(columns: ["_measurement", "_field"])
      |> distinct(column: "_value")
      |> keep(columns: ["_measurement", "_field"])
    '''
    
    try:
        result = query_api.query(status_query)
        for table in result:
            for record in table.records:
                measurement = record.get_value_by_key('_measurement')
                field = record.get_value_by_key('_field')
                print(f"  {measurement} -> {field}")
                
                # Get recent sample
                sample_query = f'''
                from(bucket: "mqtt")
                  |> range(start: -30m)
                  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
                  |> last()
                '''
                
                try:
                    sample_result = query_api.query(sample_query)
                    for sample_table in sample_result:
                        for sample_record in sample_table.records:
                            value = sample_record.get_value()
                            tags = {k: v for k, v in sample_record.values.items() if not k.startswith('_') and k not in ['result', 'table']}
                            print(f"    Current value: {value}, Tags: {tags}")
                except:
                    print(f"    No recent data")
    except Exception as e:
        print(f"  ❌ Error querying status fields: {e}")
    
    client.close()
    
    print("\n" + "=" * 50)
    print("🏁 Safety data inspection complete!")

if __name__ == "__main__":
    inspect_safety_data()