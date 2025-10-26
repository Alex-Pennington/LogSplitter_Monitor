#!/usr/bin/env python3
"""
Quick InfluxDB Data Format Checker
Simple script to verify data formats and structure in InfluxDB
"""

import json
import sys
from datetime import datetime, timedelta

try:
    from influxdb_client import InfluxDBClient
except ImportError:
    print("ERROR: influxdb-client not installed. Run: pip install influxdb-client")
    sys.exit(1)

def quick_check():
    """Quick verification of InfluxDB data"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: config.json not found")
        return False

    try:
        client = InfluxDBClient(
            url=config['influxdb']['url'],
            token=config['influxdb']['token'],
            org=config['influxdb']['org']
        )
        query_api = client.query_api()
        bucket = config['influxdb']['bucket']
        
        print(f"🔍 Quick check of bucket: {bucket}")
        print("-" * 50)
        
        # Get recent data from all measurements
        quick_query = f'''
        from(bucket: "{bucket}")
        |> range(start: -1h)
        |> group(columns: ["_measurement"])
        |> count()
        '''
        
        result = query_api.query(quick_query)
        
        measurements = {}
        for table in result:
            for record in table.records:
                measurement = record.values.get('_measurement')
                count = record.get_value()
                measurements[measurement] = count
        
        if not measurements:
            print("❌ No recent data found (last 1 hour)")
            return False
            
        print(f"✅ Found {len(measurements)} active measurements:")
        for measurement, count in sorted(measurements.items()):
            print(f"  • {measurement}: {count} records")
        
        # Sample latest data from each measurement
        print(f"\n📋 Latest data samples:")
        for measurement in measurements.keys():
            sample_query = f'''
            from(bucket: "{bucket}")
            |> range(start: -10m)
            |> filter(fn: (r) => r._measurement == "{measurement}")
            |> limit(n: 1)
            |> last()
            '''
            
            try:
                sample_result = query_api.query(sample_query)
                for table in sample_result:
                    for record in table.records:
                        field = record.get_field()
                        value = record.get_value()
                        tags = {k: v for k, v in record.values.items() 
                               if k not in ['_time', '_field', '_value', '_measurement', '_start', '_stop']}
                        print(f"  {measurement}.{field} = {value} {tags}")
                        break
                    break
            except Exception as e:
                print(f"  {measurement}: Error - {e}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def verify_expected_structure():
    """Verify expected data structure matches actual"""
    print(f"\n🧪 Verifying expected data structure...")
    
    expected = {
        'controller_pressure': {'fields': ['psi'], 'tags': ['sensor']},
        'controller_relay': {'fields': ['active'], 'tags': ['relay']},
        'controller_sequence': {'fields': ['active', 'state'], 'tags': []},
        'controller_input': {'fields': ['state'], 'tags': ['pin']},
        'monitor_temperature': {'fields': ['fahrenheit'], 'tags': ['sensor']},
        'monitor_weight': {'fields': ['pounds', 'raw'], 'tags': ['type']},
        'monitor_power': {'fields': ['voltage', 'current', 'power'], 'tags': ['metric']},
        'monitor_input': {'fields': ['state'], 'tags': ['pin']},
    }
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            
        client = InfluxDBClient(
            url=config['influxdb']['url'],
            token=config['influxdb']['token'],
            org=config['influxdb']['org']
        )
        query_api = client.query_api()
        bucket = config['influxdb']['bucket']
        
        verified = 0
        for measurement, expected_structure in expected.items():
            print(f"\n  Checking {measurement}...")
            
            # Check if measurement exists
            check_query = f'''
            from(bucket: "{bucket}")
            |> range(start: -24h)
            |> filter(fn: (r) => r._measurement == "{measurement}")
            |> limit(n: 1)
            '''
            
            try:
                result = query_api.query(check_query)
                found_record = False
                for table in result:
                    for record in table.records:
                        found_record = True
                        break
                    if found_record:
                        break
                
                if found_record:
                    print(f"    ✅ {measurement} exists with recent data")
                    verified += 1
                else:
                    print(f"    ❌ {measurement} not found or no recent data")
                    
            except Exception as e:
                print(f"    ❌ {measurement} error: {e}")
        
        print(f"\n📊 Verification Summary: {verified}/{len(expected)} measurements verified")
        client.close()
        
        return verified == len(expected)
        
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 LogSplitter Quick Data Verification")
    print("=" * 40)
    
    if quick_check():
        print("\n" + "=" * 40)
        verify_expected_structure()
    else:
        print("❌ Quick check failed")
        sys.exit(1)
        
    print(f"\n✅ Verification complete at {datetime.now()}")