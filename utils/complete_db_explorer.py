#!/usr/bin/env python3
"""
Complete InfluxDB Data Explorer for LogSplitter System
Shows all measurements, fields, tags, and sample data to understand the full data structure
"""

import json
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient

def load_config():
    """Load InfluxDB configuration"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "influxdb": {
                "url": "http://192.168.1.155:8086",
                "token": "your_token_here",
                "org": "your_org",
                "bucket": "mqtt"
            }
        }

class InfluxDataExplorer:
    def __init__(self, config):
        """Initialize data explorer with InfluxDB connection"""
        influx_config = config['influxdb']
        
        self.client = InfluxDBClient(
            url=influx_config['url'],
            token=influx_config['token'],
            org=influx_config['org']
        )
        self.bucket = influx_config['bucket']
        self.query_api = self.client.query_api()
    
    def get_all_measurements(self):
        """Get all measurements in the database"""
        query = f'''
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{self.bucket}")
        '''
        
        try:
            result = self.query_api.query(query)
            measurements = []
            for table in result:
                for record in table.records:
                    measurements.append(record.get_value())
            return sorted(measurements)
        except Exception as e:
            print(f"Error getting measurements: {e}")
            return []
    
    def get_measurement_schema(self, measurement):
        """Get field keys and tag keys for a measurement"""
        # Get field keys
        field_query = f'''
        import "influxdata/influxdb/schema"
        schema.fieldKeys(bucket: "{self.bucket}", measurement: "{measurement}")
        '''
        
        # Get tag keys
        tag_query = f'''
        import "influxdata/influxdb/schema"
        schema.tagKeys(bucket: "{self.bucket}", measurement: "{measurement}")
        '''
        
        fields = []
        tags = []
        
        try:
            result = self.query_api.query(field_query)
            for table in result:
                for record in table.records:
                    fields.append(record.get_value())
        except Exception as e:
            print(f"Error getting fields for {measurement}: {e}")
            
        try:
            result = self.query_api.query(tag_query)
            for table in result:
                for record in table.records:
                    tags.append(record.get_value())
        except Exception as e:
            print(f"Error getting tags for {measurement}: {e}")
        
        return sorted(fields), sorted(tags)
    
    def get_sample_data(self, measurement, limit=5):
        """Get sample data for a measurement"""
        query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "{measurement}")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: {limit})
        '''
        
        try:
            result = self.query_api.query(query)
            samples = []
            for table in result:
                for record in table.records:
                    sample = {
                        'time': record.get_time(),
                        'field': record.get_field(),
                        'value': record.get_value(),
                        'tags': {k: v for k, v in record.values.items() 
                                if k not in ['_time', '_value', '_field', '_measurement', 'result', 'table', '_start', '_stop']}
                    }
                    samples.append(sample)
            return samples
        except Exception as e:
            print(f"Error getting sample data for {measurement}: {e}")
            return []
    
    def get_tag_values(self, measurement, tag_key):
        """Get all values for a specific tag in a measurement"""
        query = f'''
        import "influxdata/influxdb/schema"
        schema.tagValues(bucket: "{self.bucket}", measurement: "{measurement}", tag: "{tag_key}")
        '''
        
        try:
            result = self.query_api.query(query)
            values = []
            for table in result:
                for record in table.records:
                    values.append(record.get_value())
            return sorted(values)
        except Exception as e:
            print(f"Error getting tag values for {measurement}.{tag_key}: {e}")
            return []
    
    def explore_complete_database(self):
        """Complete database exploration"""
        print("=" * 100)
        print("📊 COMPLETE INFLUXDB DATA EXPLORATION - LOGSPLITTER SYSTEM")
        print("=" * 100)
        print(f"Exploration Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database: {self.bucket}")
        print()
        
        # Get all measurements
        measurements = self.get_all_measurements()
        
        if not measurements:
            print("❌ No measurements found in database!")
            return
        
        print(f"📈 FOUND {len(measurements)} MEASUREMENTS:")
        for i, measurement in enumerate(measurements, 1):
            print(f"  {i:2d}. {measurement}")
        print()
        
        # Detailed exploration of each measurement
        for measurement in measurements:
            self.explore_measurement(measurement)
            print("-" * 80)
    
    def explore_measurement(self, measurement):
        """Explore a specific measurement in detail"""
        print(f"🔍 MEASUREMENT: {measurement}")
        print()
        
        # Get schema
        fields, tags = self.get_measurement_schema(measurement)
        
        print(f"📋 FIELDS ({len(fields)}):")
        if fields:
            for field in fields:
                print(f"  • {field}")
        else:
            print("  (No fields found)")
        print()
        
        print(f"🏷️  TAGS ({len(tags)}):")
        if tags:
            for tag in tags:
                values = self.get_tag_values(measurement, tag)
                if len(values) <= 5:
                    values_str = ", ".join(values)
                else:
                    values_str = ", ".join(values[:5]) + f"... ({len(values)} total)"
                print(f"  • {tag}: {values_str}")
        else:
            print("  (No tags found)")
        print()
        
        # Get sample data
        samples = self.get_sample_data(measurement, 3)
        print(f"📊 SAMPLE DATA (Last 3 records):")
        if samples:
            for i, sample in enumerate(samples, 1):
                time_str = sample['time'].strftime('%H:%M:%S') if sample['time'] else 'No time'
                print(f"  {i}. [{time_str}] {sample['field']} = {sample['value']}")
                if sample['tags']:
                    tag_str = ", ".join([f"{k}={v}" for k, v in sample['tags'].items()])
                    print(f"     Tags: {tag_str}")
        else:
            print("  (No sample data found)")
        print()
    
    def analyze_data_patterns(self):
        """Analyze data patterns and suggest dashboard structure"""
        print("=" * 100)
        print("🎯 DATA PATTERN ANALYSIS & DASHBOARD SUGGESTIONS")
        print("=" * 100)
        
        measurements = self.get_all_measurements()
        
        # Categorize measurements
        controller_measurements = [m for m in measurements if m.startswith('controller')]
        monitor_measurements = [m for m in measurements if m.startswith('monitor')]
        system_measurements = [m for m in measurements if 'system' in m]
        safety_measurements = [m for m in measurements if any(word in m.lower() for word in ['safety', 'estop', 'emergency', 'alert'])]
        
        print(f"📊 CONTROLLER DATA ({len(controller_measurements)} measurements):")
        for m in controller_measurements:
            fields, tags = self.get_measurement_schema(m)
            print(f"  • {m} - Fields: {len(fields)}, Tags: {len(tags)}")
        print()
        
        print(f"📡 MONITOR DATA ({len(monitor_measurements)} measurements):")
        for m in monitor_measurements:
            fields, tags = self.get_measurement_schema(m)
            print(f"  • {m} - Fields: {len(fields)}, Tags: {len(tags)}")
        print()
        
        print(f"🖥️  SYSTEM DATA ({len(system_measurements)} measurements):")
        for m in system_measurements:
            fields, tags = self.get_measurement_schema(m)
            print(f"  • {m} - Fields: {len(fields)}, Tags: {len(tags)}")
        print()
        
        print(f"🚨 SAFETY DATA ({len(safety_measurements)} measurements):")
        for m in safety_measurements:
            fields, tags = self.get_measurement_schema(m)
            print(f"  • {m} - Fields: {len(fields)}, Tags: {len(tags)}")
        print()
        
        # Dashboard suggestions
        print("💡 SUGGESTED DASHBOARD STRUCTURE:")
        print("  1. 🎛️  SYSTEM OVERVIEW - controller_system, monitor_system, uptime, status")
        print("  2. 🚨 SAFETY & ALERTS - controller_estop, controller_engine, safety events")
        print("  3. 🔧 CONTROLLER - pressure, sequence, relay states, input states")
        print("  4. 📊 MONITOR - temperature, weight, sensors, heartbeat")
        print("  5. 🛠️  MAINTENANCE - logs, errors, diagnostics, performance")
        print()
    
    def get_current_status_summary(self):
        """Get current status of key system components"""
        print("=" * 100)
        print("⚡ CURRENT SYSTEM STATUS SUMMARY")
        print("=" * 100)
        
        status_queries = {
            "E-Stop Active": ('controller_estop', 'active'),
            "Engine Running": ('controller_engine', 'running'),
            "System Active": ('controller_system', 'active'),
            "Sequence Active": ('controller_sequence', 'active'),
            "Latest Pressure A1": ('controller_pressure', 'psi', 'sensor', 'A1'),
            "Latest Pressure A5": ('controller_pressure', 'psi', 'sensor', 'A5'),
            "Monitor Temperature": ('monitor_temperature', 'fahrenheit'),
            "Monitor Weight": ('monitor_weight', 'pounds'),
            "System Uptime": ('controller_system_parsed', 'uptime_seconds'),
        }
        
        for status_name, query_info in status_queries.items():
            measurement = query_info[0]
            field = query_info[1]
            
            # Build query
            if len(query_info) == 4:  # Has tag filter
                tag_key, tag_value = query_info[2], query_info[3]
                query = f'''
                from(bucket: "{self.bucket}")
                  |> range(start: -1h)
                  |> filter(fn: (r) => r._measurement == "{measurement}")
                  |> filter(fn: (r) => r._field == "{field}")
                  |> filter(fn: (r) => r.{tag_key} == "{tag_value}")
                  |> last()
                '''
            else:
                query = f'''
                from(bucket: "{self.bucket}")
                  |> range(start: -1h)
                  |> filter(fn: (r) => r._measurement == "{measurement}")
                  |> filter(fn: (r) => r._field == "{field}")
                  |> last()
                '''
            
            try:
                result = self.query_api.query(query)
                value = None
                timestamp = None
                
                for table in result:
                    for record in table.records:
                        value = record.get_value()
                        timestamp = record.get_time()
                        break
                
                if value is not None:
                    time_str = timestamp.strftime('%H:%M:%S') if timestamp else 'Unknown'
                    print(f"  {status_name:20} = {value} (at {time_str})")
                else:
                    print(f"  {status_name:20} = No data")
                    
            except Exception as e:
                print(f"  {status_name:20} = Error: {e}")
        
        print()

def main():
    """Main exploration function"""
    config = load_config()
    explorer = InfluxDataExplorer(config)
    
    try:
        # Complete database exploration
        explorer.explore_complete_database()
        
        # Data pattern analysis
        explorer.analyze_data_patterns()
        
        # Current status summary
        explorer.get_current_status_summary()
        
    except Exception as e:
        print(f"Exploration error: {e}")
    finally:
        explorer.client.close()

if __name__ == "__main__":
    main()