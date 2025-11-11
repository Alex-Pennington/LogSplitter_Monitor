#!/usr/bin/env python3
"""
Operator Signal Metrics - Lap-based analysis using operator button presses

Uses operator signal events (ACTIVE/INACTIVE transitions) as lap markers to calculate
performance metrics between each press. Provides delta analysis for fuel consumption,
sequence counts, temperature trends, and timing.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from time_domain_analyzer import LogSplitterAnalyzer, TimeRange

def format_duration(seconds):
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.2f}h"

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(text.center(80))
    print("="*80)

def print_section(text):
    """Print a section header"""
    print("\n" + "-"*80)
    print(text)
    print("-"*80)

def get_operator_laps(analyzer, time_range):
    """
    Extract operator signal events and create lap periods
    Returns list of lap periods with start/end times
    """
    digital_inputs = analyzer.get_digital_inputs(time_range)
    
    # Filter for operator signals and parse timestamps
    operator_events = []
    for event in digital_inputs:
        payload = event['payload']
        if payload.get('input_type_name') == 'INPUT_SPLITTER_OPERATOR':
            # Parse timestamp
            timestamp_str = event['received_timestamp']
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            operator_events.append({
                'timestamp': timestamp,
                'state': payload.get('state_name', 'UNKNOWN')
            })
    
    if not operator_events:
        return []
    
    # Sort by timestamp
    operator_events.sort(key=lambda x: x['timestamp'])
    
    # Create laps from consecutive events (each press creates one lap to next press)
    laps = []
    for i in range(len(operator_events) - 1):
        lap_start = operator_events[i]['timestamp']
        lap_end = operator_events[i + 1]['timestamp']
        
        laps.append({
            'lap_number': i + 1,
            'start': lap_start,
            'end': lap_end,
            'start_state': operator_events[i]['state'],
            'end_state': operator_events[i + 1]['state'],
            'duration': (lap_end - lap_start).total_seconds()
        })
    
    return laps

def calculate_lap_metrics(analyzer, lap):
    """Calculate metrics for a single lap period"""
    lap_range = TimeRange(start=lap['start'], end=lap['end'])
    
    metrics = {
        'lap_number': lap['lap_number'],
        'start_time': lap['start'],
        'end_time': lap['end'],
        'duration': lap['duration']
    }
    
    # Get fuel readings
    fuel_readings = analyzer.get_sensor_readings(lap_range, ['fuel'])
    if fuel_readings:
        fuel_values = [r['value'] for r in fuel_readings]
        metrics['fuel_start'] = fuel_values[0]
        metrics['fuel_end'] = fuel_values[-1]
        metrics['fuel_delta'] = fuel_values[-1] - fuel_values[0]
        metrics['fuel_readings'] = len(fuel_values)
    else:
        metrics['fuel_start'] = None
        metrics['fuel_end'] = None
        metrics['fuel_delta'] = None
        metrics['fuel_readings'] = 0
    
    # Get temperature readings (REMOTE only)
    temp_readings = analyzer.get_sensor_readings(lap_range, ['temperature'])
    if temp_readings:
        remote_temps = [r['value'] for r in temp_readings if r['sensor_name'] == 'remote']
        if remote_temps:
            metrics['temp_avg'] = sum(remote_temps) / len(remote_temps)
            metrics['temp_min'] = min(remote_temps)
            metrics['temp_max'] = max(remote_temps)
            metrics['temp_readings'] = len(remote_temps)
        else:
            metrics['temp_avg'] = None
            metrics['temp_min'] = None
            metrics['temp_max'] = None
            metrics['temp_readings'] = 0
    else:
        metrics['temp_avg'] = None
        metrics['temp_min'] = None
        metrics['temp_max'] = None
        metrics['temp_readings'] = 0
    
    # Get sequence analysis
    sequences = analyzer.find_sequences(lap_range)
    if sequences:
        completed = [s for s in sequences if s['status'] == 'COMPLETED']
        aborted = [s for s in sequences if s['status'] == 'ABORTED']
        
        metrics['sequence_total'] = len(sequences)
        metrics['sequence_completed'] = len(completed)
        metrics['sequence_aborted'] = len(aborted)
        metrics['sequence_incomplete'] = len(sequences) - len(completed) - len(aborted)
        
        if completed:
            completed_durations = [s['duration_ms'] for s in completed if s['duration_ms']]
            if completed_durations:
                metrics['sequence_avg_duration'] = sum(completed_durations) / len(completed_durations)
            else:
                metrics['sequence_avg_duration'] = None
        else:
            metrics['sequence_avg_duration'] = None
    else:
        metrics['sequence_total'] = 0
        metrics['sequence_completed'] = 0
        metrics['sequence_aborted'] = 0
        metrics['sequence_incomplete'] = 0
        metrics['sequence_avg_duration'] = None
    
    # Get hydraulic pressure
    pressure_events = analyzer.get_pressure_readings(lap_range)
    if pressure_events:
        system_pressures = []
        for event in pressure_events:
            payload = event['payload']
            if payload.get('pressure_type_name') == 'SYSTEM_PRESSURE':
                pressure = payload.get('pressure_psi', 0)
                if 0 < pressure < 5000:  # Valid range
                    system_pressures.append(pressure)
        
        if system_pressures:
            metrics['pressure_avg'] = sum(system_pressures) / len(system_pressures)
            metrics['pressure_min'] = min(system_pressures)
            metrics['pressure_max'] = max(system_pressures)
            metrics['pressure_readings'] = len(system_pressures)
        else:
            metrics['pressure_avg'] = None
            metrics['pressure_min'] = None
            metrics['pressure_max'] = None
            metrics['pressure_readings'] = 0
    else:
        metrics['pressure_avg'] = None
        metrics['pressure_min'] = None
        metrics['pressure_max'] = None
        metrics['pressure_readings'] = 0
    
    return metrics

def generate_lap_report(analyzer, time_range):
    """Generate lap-based metrics report"""
    print_header("OPERATOR SIGNAL LAP METRICS")
    print(f"\nTime Range: {time_range}")
    
    # Get operator laps
    laps = get_operator_laps(analyzer, time_range)
    
    if not laps:
        print("\nNo operator signal events found in this time range.")
        print("At least 2 operator button presses are required to create lap periods.")
        return
    
    print(f"\nTotal Laps: {len(laps)}")
    print(f"First Press: {laps[0]['start'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Last Press: {laps[-1]['end'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Calculate metrics for each lap
    lap_metrics = []
    for lap in laps:
        metrics = calculate_lap_metrics(analyzer, lap)
        lap_metrics.append(metrics)
    
    # Print detailed lap table
    print_section("Lap Details")
    
    # Table header
    print(f"\n{'Lap':<5} {'Start Time':<20} {'Duration':<10} {'Fuel Δ':<10} "
          f"{'Sequences':<12} {'Avg Temp':<10} {'Avg Press':<12}")
    print("-" * 95)
    
    # Table rows
    for m in lap_metrics:
        start_time = m['start_time'].strftime('%m-%d %H:%M:%S')
        duration = format_duration(m['duration'])
        
        fuel_delta = f"{m['fuel_delta']:+.2f}g" if m['fuel_delta'] is not None else "N/A"
        
        sequences = f"{m['sequence_completed']}/{m['sequence_total']}"
        
        temp_avg = f"{m['temp_avg']:.1f}°F" if m['temp_avg'] is not None else "N/A"
        
        pressure_avg = f"{m['pressure_avg']:.1f} PSI" if m['pressure_avg'] is not None else "N/A"
        
        print(f"{m['lap_number']:<5} {start_time:<20} {duration:<10} {fuel_delta:<10} "
              f"{sequences:<12} {temp_avg:<10} {pressure_avg:<12}")
    
    # Summary statistics
    print_section("Summary Statistics")
    
    # Total duration
    total_duration = sum(m['duration'] for m in lap_metrics)
    print(f"\nTotal Duration: {format_duration(total_duration)}")
    print(f"Average Lap Duration: {format_duration(total_duration / len(lap_metrics))}")
    
    # Fuel statistics
    fuel_deltas = [m['fuel_delta'] for m in lap_metrics if m['fuel_delta'] is not None]
    if fuel_deltas:
        print(f"\nFuel Consumption:")
        print(f"  Total Change: {sum(fuel_deltas):+.2f} gallons")
        print(f"  Average per Lap: {sum(fuel_deltas)/len(fuel_deltas):+.2f} gallons")
        print(f"  Min Lap: {min(fuel_deltas):+.2f} gallons")
        print(f"  Max Lap: {max(fuel_deltas):+.2f} gallons")
    
    # Temperature statistics
    temps = [m['temp_avg'] for m in lap_metrics if m['temp_avg'] is not None]
    if temps:
        print(f"\nRemote Temperature:")
        print(f"  Average: {sum(temps)/len(temps):.1f}°F")
        print(f"  Min: {min(temps):.1f}°F")
        print(f"  Max: {max(temps):.1f}°F")
        print(f"  Range: {max(temps) - min(temps):.1f}°F")
    
    # Sequence statistics
    total_sequences = sum(m['sequence_total'] for m in lap_metrics)
    total_completed = sum(m['sequence_completed'] for m in lap_metrics)
    total_aborted = sum(m['sequence_aborted'] for m in lap_metrics)
    
    print(f"\nSequence Performance:")
    print(f"  Total Sequences: {total_sequences}")
    print(f"  Completed: {total_completed} ({total_completed/total_sequences*100:.1f}%)" if total_sequences > 0 else "  Completed: 0")
    print(f"  Aborted: {total_aborted}")
    print(f"  Average per Lap: {total_sequences/len(lap_metrics):.1f}")
    
    # Average durations
    durations = [m['sequence_avg_duration'] for m in lap_metrics if m['sequence_avg_duration'] is not None]
    if durations:
        print(f"  Avg Sequence Duration: {sum(durations)/len(durations):.0f}ms")
    
    # Pressure statistics
    pressures = [m['pressure_avg'] for m in lap_metrics if m['pressure_avg'] is not None]
    if pressures:
        print(f"\nHydraulic System Pressure:")
        print(f"  Average: {sum(pressures)/len(pressures):.1f} PSI")
        print(f"  Min: {min(pressures):.1f} PSI")
        print(f"  Max: {max(pressures):.1f} PSI")

def main():
    parser = argparse.ArgumentParser(
        description='Operator Signal Lap Metrics - Analyze performance between operator button presses',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze last 4 hours
  %(prog)s --hours 4
  
  # Analyze last 2 hours
  %(prog)s --hours 2
  
  # Analyze specific time range
  %(prog)s --start "2025-11-05 14:00:00" --end "2025-11-05 18:00:00"
  
  # Use custom database paths
  %(prog)s --hours 4 --controller-db /path/to/logsplitter_data.db
        """
    )
    
    parser.add_argument('--hours', type=float, help='Analyze last N hours')
    parser.add_argument('--minutes', type=float, help='Analyze last N minutes')
    parser.add_argument('--start', type=str, help='Start time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end', type=str, help='End time (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--controller-db', type=str, help='Path to controller database')
    parser.add_argument('--monitor-db', type=str, help='Path to monitor database')
    
    args = parser.parse_args()
    
    # Create analyzer
    analyzer = LogSplitterAnalyzer(
        controller_db=args.controller_db,
        monitor_db=args.monitor_db
    )
    
    # Create time range
    if args.start and args.end:
        start = datetime.strptime(args.start, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        end = datetime.strptime(args.end, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        time_range = TimeRange(start=start, end=end)
    else:
        end_time = datetime.now(timezone.utc)
        if args.hours:
            start_time = end_time - timedelta(hours=args.hours)
        elif args.minutes:
            start_time = end_time - timedelta(minutes=args.minutes)
        else:
            start_time = end_time - timedelta(hours=4)  # Default 4 hours
        time_range = TimeRange(start=start_time, end=end_time)
    
    # Generate report
    generate_lap_report(analyzer, time_range)
    
    print("\n" + "="*80 + "\n")
    
    return 0

if __name__ == "__main__":
    exit(main())
