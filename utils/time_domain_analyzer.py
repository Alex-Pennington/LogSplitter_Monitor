#!/usr/bin/env python3
"""
LogSplitter Time-Domain Data Analyzer

Core framework for analyzing time-series data from both controller protobuf 
telemetry and monitor sensor databases. Provides unified time-domain queries,
correlation analysis, and report generation.

Databases:
- logsplitter_data.db - Controller protobuf telemetry (8 message types)
- monitor_data.db - Monitor sensor data (temperature, fuel, weight, etc.)

Analysis Capabilities:
- Time-range queries across both databases
- Event correlation (controller actions vs sensor responses)
- Cycle detection and metrics
- Trend analysis
- Statistical summaries
"""

import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict

# Database paths
SCRIPT_DIR = Path(__file__).parent
CONTROLLER_DB = SCRIPT_DIR / 'logsplitter_data.db'
MONITOR_DB = SCRIPT_DIR / 'monitor_data.db'

@dataclass
class TimeRange:
    """Time range for queries"""
    start: datetime
    end: datetime
    
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()
    
    def __str__(self):
        return f"{self.start.isoformat()} to {self.end.isoformat()} ({self.duration_seconds():.1f}s)"

@dataclass
class AnalysisResult:
    """Container for analysis results"""
    title: str
    time_range: TimeRange
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'time_range': {
                'start': self.time_range.start.isoformat(),
                'end': self.time_range.end.isoformat(),
                'duration_seconds': self.time_range.duration_seconds()
            },
            'data': self.data,
            'metadata': self.metadata
        }

class LogSplitterAnalyzer:
    """Core analyzer for controller and monitor data"""
    
    def __init__(self, controller_db: str = None, monitor_db: str = None):
        self.controller_db = controller_db or str(CONTROLLER_DB)
        self.monitor_db = monitor_db or str(MONITOR_DB)
        
        # Validate databases exist
        if not Path(self.controller_db).exists():
            raise FileNotFoundError(f"Controller database not found: {self.controller_db}")
        if not Path(self.monitor_db).exists():
            raise FileNotFoundError(f"Monitor database not found: {self.monitor_db}")
    
    def get_data_time_range(self) -> Tuple[TimeRange, TimeRange]:
        """Get time ranges for both databases"""
        
        # Controller data range
        conn = sqlite3.connect(self.controller_db)
        cursor = conn.cursor()
        cursor.execute('SELECT MIN(received_timestamp), MAX(received_timestamp) FROM telemetry')
        controller_range = cursor.fetchone()
        conn.close()
        
        # Monitor data range
        conn = sqlite3.connect(self.monitor_db)
        cursor = conn.cursor()
        cursor.execute('SELECT MIN(received_timestamp), MAX(received_timestamp) FROM sensor_readings')
        monitor_range = cursor.fetchone()
        conn.close()
        
        controller_tr = TimeRange(
            start=datetime.fromisoformat(controller_range[0]),
            end=datetime.fromisoformat(controller_range[1])
        )
        
        monitor_tr = TimeRange(
            start=datetime.fromisoformat(monitor_range[0]),
            end=datetime.fromisoformat(monitor_range[1])
        )
        
        return controller_tr, monitor_tr
    
    def get_controller_events(self, time_range: TimeRange, 
                             message_types: List[int] = None) -> List[Dict]:
        """Get controller events within time range"""
        conn = sqlite3.connect(self.controller_db)
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                received_timestamp,
                controller_timestamp,
                message_type,
                message_type_name,
                sequence_id,
                payload_json
            FROM telemetry
            WHERE received_timestamp BETWEEN ? AND ?
        '''
        
        # Convert datetime to string format for SQLite comparison
        start_str = time_range.start.strftime('%Y-%m-%d %H:%M:%S')
        end_str = time_range.end.strftime('%Y-%m-%d %H:%M:%S')
        params = [start_str, end_str]
        
        if message_types:
            placeholders = ','.join('?' * len(message_types))
            query += f' AND message_type IN ({placeholders})'
            params.extend(message_types)
        
        query += ' ORDER BY received_timestamp'
        
        cursor.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            events.append({
                'received_timestamp': row[0],
                'controller_timestamp': row[1],
                'message_type': row[2],
                'message_type_name': row[3],
                'sequence_id': row[4],
                'payload': json.loads(row[5]) if row[5] else {}
            })
        
        conn.close()
        return events
    
    def get_sensor_readings(self, time_range: TimeRange,
                           sensor_types: List[str] = None) -> List[Dict]:
        """Get monitor sensor readings within time range"""
        conn = sqlite3.connect(self.monitor_db)
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                received_timestamp,
                sensor_type,
                sensor_name,
                value,
                unit,
                metadata
            FROM sensor_readings
            WHERE received_timestamp BETWEEN ? AND ?
        '''
        
        # Convert datetime to string format for SQLite comparison
        start_str = time_range.start.strftime('%Y-%m-%d %H:%M:%S')
        end_str = time_range.end.strftime('%Y-%m-%d %H:%M:%S')
        params = [start_str, end_str]
        
        if sensor_types:
            placeholders = ','.join('?' * len(sensor_types))
            query += f' AND sensor_type IN ({placeholders})'
            params.extend(sensor_types)
        
        query += ' ORDER BY received_timestamp'
        
        cursor.execute(query, params)
        
        readings = []
        for row in cursor.fetchall():
            readings.append({
                'timestamp': row[0],
                'sensor_type': row[1],
                'sensor_name': row[2],
                'value': row[3],
                'unit': row[4],
                'metadata': json.loads(row[5]) if row[5] else {}
            })
        
        conn.close()
        return readings
    
    def get_relay_events(self, time_range: TimeRange) -> List[Dict]:
        """Get relay events (type 18) within time range"""
        events = self.get_controller_events(time_range, [18])
        return events
    
    def get_sequence_events(self, time_range: TimeRange) -> List[Dict]:
        """Get sequence events (type 23) within time range"""
        events = self.get_controller_events(time_range, [23])
        return events
    
    def get_pressure_readings(self, time_range: TimeRange) -> List[Dict]:
        """Get pressure readings (type 19) within time range"""
        events = self.get_controller_events(time_range, [19])
        return events
    
    def get_digital_inputs(self, time_range: TimeRange) -> List[Dict]:
        """Get digital input events (type 16) within time range"""
        events = self.get_controller_events(time_range, [16])
        return events
    
    def count_events_by_type(self, time_range: TimeRange) -> Dict[str, int]:
        """Count controller events by message type"""
        events = self.get_controller_events(time_range)
        
        counts = defaultdict(int)
        for event in events:
            counts[event['message_type_name']] += 1
        
        return dict(counts)
    
    def count_sensors_by_type(self, time_range: TimeRange) -> Dict[str, int]:
        """Count sensor readings by type"""
        readings = self.get_sensor_readings(time_range)
        
        counts = defaultdict(int)
        for reading in readings:
            counts[reading['sensor_type']] += 1
        
        return dict(counts)
    
    def get_statistics(self, time_range: TimeRange) -> AnalysisResult:
        """Get overall statistics for time range"""
        
        controller_counts = self.count_events_by_type(time_range)
        sensor_counts = self.count_sensors_by_type(time_range)
        
        total_controller = sum(controller_counts.values())
        total_sensors = sum(sensor_counts.values())
        
        data = {
            'controller_events': controller_counts,
            'controller_total': total_controller,
            'sensor_readings': sensor_counts,
            'sensor_total': total_sensors,
            'combined_total': total_controller + total_sensors,
            'events_per_second': {
                'controller': total_controller / time_range.duration_seconds() if time_range.duration_seconds() > 0 else 0,
                'sensors': total_sensors / time_range.duration_seconds() if time_range.duration_seconds() > 0 else 0
            }
        }
        
        metadata = {
            'controller_db': self.controller_db,
            'monitor_db': self.monitor_db,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        return AnalysisResult(
            title="Time Range Statistics",
            time_range=time_range,
            data=data,
            metadata=metadata
        )
    
    def find_sequences(self, time_range: TimeRange) -> List[Dict]:
        """Find all sequence start/complete/abort cycles"""
        sequence_events = self.get_sequence_events(time_range)
        
        sequences = []
        current_sequence = None
        
        for event in sequence_events:
            payload = event['payload']
            event_type = payload.get('event_type')
            event_name = payload.get('event_type_name', 'UNKNOWN')
            
            if event_type == 0:  # SEQUENCE_STARTED
                if current_sequence:
                    # Previous sequence didn't complete - mark as incomplete
                    current_sequence['status'] = 'INCOMPLETE'
                    sequences.append(current_sequence)
                
                current_sequence = {
                    'start_time': event['received_timestamp'],
                    'start_event': event,
                    'end_time': None,
                    'end_event': None,
                    'status': 'IN_PROGRESS',
                    'duration_ms': None
                }
            
            elif event_type == 2 and current_sequence:  # SEQUENCE_COMPLETE
                current_sequence['end_time'] = event['received_timestamp']
                current_sequence['end_event'] = event
                current_sequence['status'] = 'COMPLETED'
                current_sequence['duration_ms'] = payload.get('elapsed_time_ms')
                sequences.append(current_sequence)
                current_sequence = None
            
            elif event_type == 5 and current_sequence:  # SEQUENCE_ABORTED
                current_sequence['end_time'] = event['received_timestamp']
                current_sequence['end_event'] = event
                current_sequence['status'] = 'ABORTED'
                current_sequence['duration_ms'] = payload.get('elapsed_time_ms')
                sequences.append(current_sequence)
                current_sequence = None
        
        # Handle final incomplete sequence
        if current_sequence:
            current_sequence['status'] = 'INCOMPLETE'
            sequences.append(current_sequence)
        
        return sequences
    
    def analyze_sequences(self, time_range: TimeRange) -> AnalysisResult:
        """Analyze sequence patterns and statistics"""
        sequences = self.find_sequences(time_range)
        
        completed = [s for s in sequences if s['status'] == 'COMPLETED']
        aborted = [s for s in sequences if s['status'] == 'ABORTED']
        incomplete = [s for s in sequences if s['status'] == 'INCOMPLETE']
        
        completed_durations = [s['duration_ms'] for s in completed if s['duration_ms']]
        
        data = {
            'total_sequences': len(sequences),
            'completed': len(completed),
            'aborted': len(aborted),
            'incomplete': len(incomplete),
            'completion_rate': len(completed) / len(sequences) if sequences else 0,
            'durations': {
                'min_ms': min(completed_durations) if completed_durations else None,
                'max_ms': max(completed_durations) if completed_durations else None,
                'avg_ms': sum(completed_durations) / len(completed_durations) if completed_durations else None,
                'count': len(completed_durations)
            },
            'sequences': sequences
        }
        
        metadata = {
            'analysis_type': 'sequence_analysis',
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        return AnalysisResult(
            title="Sequence Analysis",
            time_range=time_range,
            data=data,
            metadata=metadata
        )

def create_time_range(hours: float = None, minutes: float = None, 
                     start: datetime = None, end: datetime = None) -> TimeRange:
    """Helper to create time ranges"""
    if start and end:
        return TimeRange(start=start, end=end)
    
    end_time = datetime.now(timezone.utc)
    
    if hours:
        start_time = end_time - timedelta(hours=hours)
    elif minutes:
        start_time = end_time - timedelta(minutes=minutes)
    else:
        start_time = end_time - timedelta(hours=1)  # Default 1 hour
    
    return TimeRange(start=start_time, end=end_time)

if __name__ == "__main__":
    # Example usage
    analyzer = LogSplitterAnalyzer()
    
    print("="*80)
    print("LogSplitter Time-Domain Data Analyzer")
    print("="*80)
    
    # Get data ranges
    controller_range, monitor_range = analyzer.get_data_time_range()
    print(f"\nController Data: {controller_range}")
    print(f"Monitor Data: {monitor_range}")
    
    # Analyze last hour
    time_range = create_time_range(hours=1)
    print(f"\nAnalyzing: {time_range}")
    
    # Get statistics
    stats = analyzer.get_statistics(time_range)
    print(f"\nTotal Events: {stats.data['combined_total']}")
    print(f"  Controller: {stats.data['controller_total']}")
    print(f"  Sensors: {stats.data['sensor_total']}")
    
    print("\nController Events:")
    for event_type, count in stats.data['controller_events'].items():
        print(f"  {event_type}: {count}")
    
    print("\nSensor Readings:")
    for sensor_type, count in stats.data['sensor_readings'].items():
        print(f"  {sensor_type}: {count}")
    
    # Analyze sequences
    seq_analysis = analyzer.analyze_sequences(time_range)
    print(f"\nSequences: {seq_analysis.data['total_sequences']}")
    print(f"  Completed: {seq_analysis.data['completed']}")
    print(f"  Aborted: {seq_analysis.data['aborted']}")
    print(f"  Incomplete: {seq_analysis.data['incomplete']}")
    
    if seq_analysis.data['durations']['count'] > 0:
        print(f"\nDuration Statistics:")
        print(f"  Min: {seq_analysis.data['durations']['min_ms']}ms")
        print(f"  Max: {seq_analysis.data['durations']['max_ms']}ms")
        print(f"  Avg: {seq_analysis.data['durations']['avg_ms']:.1f}ms")
