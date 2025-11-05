#!/usr/bin/env python3
"""
LogSplitter Report Generator

Generate detailed analysis reports from controller and monitor databases.
Uses the time_domain_analyzer framework to produce formatted reports.

Report Types:
- Summary: High-level statistics and counts
- Sequences: Detailed sequence analysis with timing
- Sensors: Temperature, fuel, weight trends
- Correlation: Controller actions vs sensor responses
- Custom: User-defined time ranges and filters
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from time_domain_analyzer import (
    LogSplitterAnalyzer, 
    TimeRange, 
    create_time_range
)

def print_header(title: str):
    """Print formatted section header"""
    print("\n" + "="*80)
    print(title.center(80))
    print("="*80)

def print_section(title: str):
    """Print formatted subsection header"""
    print("\n" + "-"*80)
    print(title)
    print("-"*80)

def format_duration(ms: float) -> str:
    """Format duration in milliseconds to human readable"""
    if ms < 1000:
        return f"{ms:.0f}ms"
    else:
        return f"{ms/1000:.2f}s"

def generate_summary_report(analyzer: LogSplitterAnalyzer, time_range: TimeRange):
    """Generate summary report for time range"""
    
    print_header("LOGSPLITTER SUMMARY REPORT")
    
    print(f"\nTime Range: {time_range}")
    print(f"Duration: {format_duration(time_range.duration_seconds() * 1000)}")
    
    # Get statistics
    stats = analyzer.get_statistics(time_range)
    
    print_section("Data Collection Statistics")
    print(f"Total Events Captured: {stats.data['combined_total']:,}")
    print(f"  Controller Events: {stats.data['controller_total']:,}")
    print(f"  Monitor Sensors: {stats.data['sensor_total']:,}")
    print(f"\nCapture Rate:")
    print(f"  Controller: {stats.data['events_per_second']['controller']:.2f} events/sec")
    print(f"  Monitor: {stats.data['events_per_second']['sensors']:.2f} readings/sec")
    
    print_section("Controller Message Types")
    for msg_type, count in sorted(stats.data['controller_events'].items()):
        percent = (count / stats.data['controller_total'] * 100) if stats.data['controller_total'] > 0 else 0
        print(f"  {msg_type:<30} {count:>6,}  ({percent:>5.1f}%)")
    
    print_section("Monitor Sensor Types")
    for sensor_type, count in sorted(stats.data['sensor_readings'].items()):
        percent = (count / stats.data['sensor_total'] * 100) if stats.data['sensor_total'] > 0 else 0
        print(f"  {sensor_type:<30} {count:>6,}  ({percent:>5.1f}%)")
    
    # Sequence analysis
    seq_analysis = analyzer.analyze_sequences(time_range)
    
    print_section("Sequence Operations")
    print(f"Total Sequences: {seq_analysis.data['total_sequences']}")
    print(f"  Completed: {seq_analysis.data['completed']}")
    print(f"  Aborted: {seq_analysis.data['aborted']}")
    print(f"  Incomplete: {seq_analysis.data['incomplete']}")
    
    if seq_analysis.data['completed'] > 0:
        completion_rate = seq_analysis.data['completion_rate'] * 100
        print(f"\nCompletion Rate: {completion_rate:.1f}%")
    
    if seq_analysis.data['durations']['count'] > 0:
        durations = seq_analysis.data['durations']
        print(f"\nSequence Duration Statistics:")
        print(f"  Minimum: {format_duration(durations['min_ms'])}")
        print(f"  Maximum: {format_duration(durations['max_ms'])}")
        print(f"  Average: {format_duration(durations['avg_ms'])}")
        print(f"  Sample Size: {durations['count']}")

def generate_sequence_detail_report(analyzer: LogSplitterAnalyzer, time_range: TimeRange, limit: int = 20):
    """Generate detailed sequence report"""
    
    print_header("SEQUENCE DETAIL REPORT")
    
    print(f"\nTime Range: {time_range}")
    
    seq_analysis = analyzer.analyze_sequences(time_range)
    sequences = seq_analysis.data['sequences']
    
    print(f"\nTotal Sequences: {len(sequences)}")
    print(f"Showing: First {min(limit, len(sequences))} sequences")
    
    print_section("Sequence Timeline")
    print(f"{'#':<4} {'Start Time':<20} {'End Time':<20} {'Status':<12} {'Duration':<10}")
    print("-"*80)
    
    for idx, seq in enumerate(sequences[:limit], 1):
        start_time = seq['start_time']
        end_time = seq['end_time'] if seq['end_time'] else "—"
        status = seq['status']
        duration = format_duration(seq['duration_ms']) if seq['duration_ms'] else "—"
        
        print(f"{idx:<4} {start_time:<20} {str(end_time):<20} {status:<12} {duration:<10}")
    
    if len(sequences) > limit:
        print(f"\n... and {len(sequences) - limit} more sequences")

def generate_sensor_report(analyzer: LogSplitterAnalyzer, time_range: TimeRange):
    """Generate sensor trends report"""
    
    print_header("SENSOR TRENDS REPORT")
    
    print(f"\nTime Range: {time_range}")
    
    # Get temperature readings - only show REMOTE
    temp_readings = analyzer.get_sensor_readings(time_range, ['temperature'])
    
    if temp_readings:
        print_section("Remote Temperature")
        
        # Filter for REMOTE sensor only
        remote_values = []
        for reading in temp_readings:
            name = reading['sensor_name'] or 'unknown'
            if name.upper() == 'REMOTE':
                remote_values.append(reading['value'])
        
        if remote_values:
            print(f"  Readings: {len(remote_values)}")
            print(f"  Min: {min(remote_values):.2f}°F")
            print(f"  Max: {max(remote_values):.2f}°F")
            print(f"  Avg: {sum(remote_values)/len(remote_values):.2f}°F")
            print(f"  Range: {max(remote_values) - min(remote_values):.2f}°F")
        else:
            print("  No remote temperature data in this time range")
    
    # Get fuel readings
    fuel_readings = analyzer.get_sensor_readings(time_range, ['fuel'])
    
    if fuel_readings:
        print_section("Fuel Level")
        values = [r['value'] for r in fuel_readings]
        print(f"  Readings: {len(values)}")
        print(f"  Min: {min(values):.2f} gallons")
        print(f"  Max: {max(values):.2f} gallons")
        print(f"  Latest: {values[-1]:.2f} gallons")
        print(f"  Change: {values[-1] - values[0]:.2f} gallons")
    
    # Get pressure readings - only show SYSTEM_PRESSURE (hydraulic system)
    pressure_events = analyzer.get_pressure_readings(time_range)
    
    if pressure_events:
        print_section("Hydraulic System Pressure")
        
        # Filter for SYSTEM_PRESSURE only
        system_pressures = []
        for event in pressure_events:
            payload = event['payload']
            pressure_type = payload.get('pressure_type_name', 'UNKNOWN')
            if pressure_type == 'SYSTEM_PRESSURE':
                pressure = payload.get('pressure_psi', 0)
                system_pressures.append(pressure)
        
        if system_pressures:
            # Filter valid pressure values: non-zero, positive, and < 5000 PSI (realistic max)
            valid = [v for v in system_pressures if 0 < v < 5000]
            
            if valid:
                print(f"  Total Readings: {len(system_pressures)}")
                print(f"  Valid Readings: {len(valid)}")
                print(f"  Min: {min(valid):.1f} PSI")
                print(f"  Max: {max(valid):.1f} PSI")
                print(f"  Avg: {sum(valid)/len(valid):.1f} PSI")
                print(f"  Range: {max(valid) - min(valid):.1f} PSI")
            else:
                zeros = len([v for v in system_pressures if v == 0])
                invalid = len([v for v in system_pressures if v < 0 or v >= 5000])
                print(f"  Total Readings: {len(system_pressures)}")
                print(f"  All readings invalid (zeros: {zeros}, out-of-range: {invalid})")
        else:
            print("  No hydraulic system pressure data in this time range")
    
    # Add sequence metrics
    sequences = analyzer.find_sequences(time_range)
    if sequences:
        print_section("Sequence Metrics")
        
        analysis_result = analyzer.analyze_sequences(time_range)
        analysis = analysis_result.data
        
        print(f"  Total Sequences: {analysis['total_sequences']}")
        print(f"  Completed: {analysis['completed']} ({analysis['completion_rate']*100:.1f}%)")
        print(f"  Aborted: {analysis['aborted']}")
        print(f"  Incomplete: {analysis['incomplete']}")
        
        if analysis['durations']['count'] > 0:
            print(f"\n  Duration Statistics:")
            print(f"    Min: {analysis['durations']['min_ms']:.0f}ms")
            print(f"    Max: {analysis['durations']['max_ms']:.0f}ms")
            print(f"    Avg: {analysis['durations']['avg_ms']:.0f}ms")
    
    # Add operator signals
    digital_inputs = analyzer.get_digital_inputs(time_range)
    
    if digital_inputs:
        print_section("Operator Signals")
        
        # Filter for operator signals only (INPUT_SPLITTER_OPERATOR on pin 8)
        operator_events = []
        for event in digital_inputs:
            payload = event['payload']
            if payload.get('input_type_name') == 'INPUT_SPLITTER_OPERATOR':
                operator_events.append({
                    'timestamp': event['received_timestamp'],
                    'state': payload.get('state_name', 'UNKNOWN')
                })
        
        if operator_events:
            # Count active vs inactive
            active_count = sum(1 for e in operator_events if e['state'] == 'ACTIVE')
            inactive_count = sum(1 for e in operator_events if e['state'] == 'INACTIVE')
            
            print(f"  Total Events: {len(operator_events)}")
            print(f"  Active Signals: {active_count}")
            print(f"  Inactive Signals: {inactive_count}")
            
            # Show last few events
            print(f"\n  Recent Events (last 5):")
            for event in operator_events[-5:]:
                print(f"    {event['timestamp']}: {event['state']}")
        else:
            print("  No operator signal events in this time range")

def main():
    parser = argparse.ArgumentParser(description='Generate LogSplitter analysis reports')
    parser.add_argument('-t', '--type', choices=['summary', 'sequences', 'sensors', 'all'],
                       default='summary', help='Report type to generate')
    parser.add_argument('--hours', type=float, help='Analyze last N hours')
    parser.add_argument('--minutes', type=float, help='Analyze last N minutes')
    parser.add_argument('--start', type=str, help='Start time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end', type=str, help='End time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--limit', type=int, default=20, help='Limit sequences shown in detail report')
    parser.add_argument('--controller-db', type=str, help='Path to controller database')
    parser.add_argument('--monitor-db', type=str, help='Path to monitor database')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    # Create analyzer
    try:
        analyzer = LogSplitterAnalyzer(
            controller_db=args.controller_db,
            monitor_db=args.monitor_db
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    
    # Determine time range
    if args.start and args.end:
        time_range = TimeRange(
            start=datetime.fromisoformat(args.start),
            end=datetime.fromisoformat(args.end)
        )
    else:
        time_range = create_time_range(hours=args.hours, minutes=args.minutes)
    
    # Generate report(s)
    if args.type == 'summary' or args.type == 'all':
        generate_summary_report(analyzer, time_range)
    
    if args.type == 'sequences' or args.type == 'all':
        generate_sequence_detail_report(analyzer, time_range, args.limit)
    
    if args.type == 'sensors' or args.type == 'all':
        generate_sensor_report(analyzer, time_range)
    
    print("\n" + "="*80 + "\n")
    
    return 0

if __name__ == "__main__":
    exit(main())
