#!/usr/bin/env python3
"""
Basket Exchange Metrics Analyzer for LogSplitter System

This module analyzes operator signals and system events to detect and track basket 
exchange operations, providing insights into operational efficiency and timing.

Author: LogSplitter Monitor System
"""

import sqlite3
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import statistics

@dataclass
class BasketExchange:
    """Represents a detected basket exchange operation"""
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    operator_signals: List[Dict[str, Any]]
    sequence_events: List[Dict[str, Any]]
    relay_events: List[Dict[str, Any]]
    exchange_type: str  # 'MANUAL', 'SEQUENCE', or 'MIXED'
    confidence: float   # 0.0-1.0 confidence in detection
    # Monitor data integration
    remote_temperature: Optional[float] = None  # Average remote temperature during exchange
    fuel_consumption: Optional[float] = None    # Fuel consumption estimate
    monitor_data: List[Dict[str, Any]] = None   # All monitor readings during exchange
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': round(self.duration_seconds, 2),
            'duration_minutes': round(self.duration_seconds / 60, 2),
            'operator_signals_count': len(self.operator_signals),
            'sequence_events_count': len(self.sequence_events),
            'relay_events_count': len(self.relay_events),
            'exchange_type': self.exchange_type,
            'confidence': round(self.confidence, 2)
        }
        
        # Add monitor data if available
        if self.remote_temperature is not None:
            result['remote_temperature_f'] = round(self.remote_temperature, 1)
        
        if self.fuel_consumption is not None:
            result['fuel_consumption_gallons'] = round(self.fuel_consumption, 2)
        
        if self.monitor_data:
            result['monitor_data_points'] = len(self.monitor_data)
        
        return result

class BasketExchangeAnalyzer:
    """Analyzes telemetry data to detect basket exchange patterns"""
    
    def __init__(self, db_path: str = 'logsplitter_telemetry.db'):
        self.db_path = db_path
        
        # Configurable thresholds for detection
        self.min_exchange_duration = 30  # seconds
        self.max_exchange_duration = 600  # 10 minutes
        self.operator_signal_timeout = 60  # seconds
        self.sequence_correlation_window = 120  # seconds
        
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_monitor_data(self, start_time: datetime, end_time: datetime, topics: List[str] = None) -> List[Dict[str, Any]]:
        """Get monitor data within time window"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        topic_filter = ""
        params = [start_time.isoformat(), end_time.isoformat()]
        
        if topics:
            placeholders = ','.join(['?' for _ in topics])
            topic_filter = f"AND topic IN ({placeholders})"
            params.extend(topics)
        
        cursor.execute(f"""
            SELECT 
                received_timestamp,
                topic,
                value,
                value_text
            FROM monitor_data 
            WHERE received_timestamp BETWEEN ? AND ?
            {topic_filter}
            ORDER BY received_timestamp ASC
        """, params)
        
        monitor_data = []
        for row in cursor.fetchall():
            monitor_data.append({
                'timestamp': datetime.fromisoformat(row[0]),
                'topic': row[1],
                'value': row[2],
                'value_text': row[3]
            })
        
        conn.close()
        return monitor_data
    
    def analyze_basket_exchanges(self, hours: int = 24) -> List[BasketExchange]:
        """
        Detect basket exchange operations from telemetry data
        
        Basket exchanges are identified by:
        1. Operator signal activity (SPLITTER_OPERATOR type digital inputs)
        2. Sequence operations (automatic cycles)
        3. Manual relay operations
        4. Time correlation between events
        """
        print(f"🧺 Analyzing Basket Exchanges (Last {hours} hours)")
        print("=" * 60)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all relevant events for analysis
        cursor.execute("""
            SELECT 
                received_timestamp,
                message_type_name,
                payload_json
            FROM telemetry 
            WHERE received_timestamp > datetime('now', '-{} hours')
            AND (
                message_type_name = 'DIGITAL_INPUT' OR
                message_type_name = 'SEQUENCE_EVENT' OR
                message_type_name = 'RELAY_EVENT' OR
                message_type_name = 'SYSTEM_STATUS'
            )
            ORDER BY received_timestamp ASC
        """.format(hours))
        
        events = cursor.fetchall()
        conn.close()
        
        # Process events into structured data
        processed_events = []
        for event in events:
            timestamp_str, msg_type, payload_json = event
            timestamp = datetime.fromisoformat(timestamp_str)
            
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                continue
                
            processed_events.append({
                'timestamp': timestamp,
                'type': msg_type,
                'payload': payload
            })
        
        # Detect basket exchange sequences
        exchanges = self._detect_exchanges(processed_events)
        
        # Display results
        self._display_exchange_summary(exchanges)
        
        return exchanges
    
    def _detect_exchanges(self, events: List[Dict[str, Any]]) -> List[BasketExchange]:
        """Detect basket exchange operations from events"""
        exchanges = []
        
        # Look for operator signal clusters that might indicate basket changes
        operator_events = [e for e in events if e['type'] == 'DIGITAL_INPUT']
        
        # Group operator events into potential exchange windows
        exchange_candidates = self._identify_exchange_windows(operator_events)
        
        # For each candidate window, collect all related events
        for start_time, end_time in exchange_candidates:
            window_events = [
                e for e in events 
                if start_time <= e['timestamp'] <= end_time
            ]
            
            # Classify events by type
            operator_signals = [e for e in window_events if e['type'] == 'DIGITAL_INPUT']
            sequence_events = [e for e in window_events if e['type'] == 'SEQUENCE_EVENT']
            relay_events = [e for e in window_events if e['type'] == 'RELAY_EVENT']
            
            # Determine exchange type and confidence
            exchange_type, confidence = self._classify_exchange(
                operator_signals, sequence_events, relay_events
            )
            
            # Only include high-confidence exchanges
            if confidence >= 0.6:
                duration = (end_time - start_time).total_seconds()
                
                if self.min_exchange_duration <= duration <= self.max_exchange_duration:
                    # Get monitor data for this exchange window
                    monitor_data = self.get_monitor_data(
                        start_time, 
                        end_time,
                        topics=['monitor/temperature/remote', 'monitor/fuel_gallons']
                    )
                    
                    # Calculate average remote temperature during exchange
                    remote_temps = [d['value'] for d in monitor_data 
                                  if d['topic'] == 'monitor/temperature/remote' and d['value'] is not None]
                    avg_temp = statistics.mean(remote_temps) if remote_temps else None
                    
                    # Calculate fuel consumption (if fuel data available)
                    fuel_readings = [d['value'] for d in monitor_data 
                                   if d['topic'] == 'monitor/fuel_gallons' and d['value'] is not None]
                    fuel_consumption = None
                    if len(fuel_readings) >= 2:
                        # Fuel consumption is initial reading minus final reading
                        fuel_consumption = fuel_readings[0] - fuel_readings[-1]
                    
                    exchange = BasketExchange(
                        start_time=start_time,
                        end_time=end_time,
                        duration_seconds=duration,
                        operator_signals=operator_signals,
                        sequence_events=sequence_events,
                        relay_events=relay_events,
                        exchange_type=exchange_type,
                        confidence=confidence,
                        remote_temperature=avg_temp,
                        fuel_consumption=fuel_consumption,
                        monitor_data=monitor_data
                    )
                    exchanges.append(exchange)
        
        return exchanges
    
    def _identify_exchange_windows(self, operator_events: List[Dict[str, Any]]) -> List[Tuple[datetime, datetime]]:
        """Identify time windows that likely contain basket exchanges"""
        windows = []
        
        if not operator_events:
            return windows
        
        # Look for operator signal clusters (multiple signals within a short time)
        current_window_start = None
        last_signal_time = None
        
        for event in operator_events:
            timestamp = event['timestamp']
            payload = event['payload']
            
            # Only consider SPLITTER_OPERATOR signals that are active (state=True)
            if (payload.get('input_type_name') == 'SPLITTER_OPERATOR' and 
                payload.get('state') is True):
                
                if current_window_start is None:
                    # Start new window
                    current_window_start = timestamp
                    last_signal_time = timestamp
                elif (timestamp - last_signal_time).total_seconds() <= self.operator_signal_timeout:
                    # Extend current window
                    last_signal_time = timestamp
                else:
                    # Close current window and start new one
                    if current_window_start and last_signal_time:
                        # Add some buffer time around the signals
                        window_start = current_window_start - timedelta(seconds=30)
                        window_end = last_signal_time + timedelta(seconds=120)
                        windows.append((window_start, window_end))
                    
                    current_window_start = timestamp
                    last_signal_time = timestamp
        
        # Close final window if exists
        if current_window_start and last_signal_time:
            window_start = current_window_start - timedelta(seconds=30)
            window_end = last_signal_time + timedelta(seconds=120)
            windows.append((window_start, window_end))
        
        return windows
    
    def _classify_exchange(self, operator_signals: List[Dict], sequence_events: List[Dict], 
                          relay_events: List[Dict]) -> Tuple[str, float]:
        """Classify the type of exchange and confidence level"""
        
        # Count different types of activity
        operator_count = len([e for e in operator_signals 
                             if e['payload'].get('input_type_name') == 'SPLITTER_OPERATOR'])
        sequence_count = len(sequence_events)
        manual_relay_count = len(relay_events)
        
        confidence = 0.0
        exchange_type = 'UNKNOWN'
        
        # High confidence if we have operator signals (key indicator)
        if operator_count >= 1:
            confidence += 0.5
            
        # Additional confidence from correlated events
        if sequence_count > 0:
            confidence += 0.3
            exchange_type = 'SEQUENCE'
            
        if manual_relay_count > 0:
            confidence += 0.2
            if exchange_type == 'SEQUENCE':
                exchange_type = 'MIXED'
            else:
                exchange_type = 'MANUAL'
        
        # Boost confidence for multiple operator signals (typical of basket changes)
        if operator_count >= 2:
            confidence += 0.2
            
        # Ensure confidence doesn't exceed 1.0
        confidence = min(confidence, 1.0)
        
        return exchange_type, confidence
    
    def _display_exchange_summary(self, exchanges: List[BasketExchange]):
        """Display summary of detected exchanges"""
        if not exchanges:
            print("📋 No basket exchanges detected in the time period")
            return
        
        print(f"\n📋 Detected {len(exchanges)} basket exchange operations")
        print("=" * 60)
        
        # Summary statistics
        durations = [e.duration_seconds for e in exchanges]
        avg_duration = statistics.mean(durations) if durations else 0
        median_duration = statistics.median(durations) if durations else 0
        
        print(f"\n📊 Exchange Statistics:")
        print(f"  Total Exchanges: {len(exchanges)}")
        print(f"  Average Duration: {avg_duration/60:.1f} minutes")
        print(f"  Median Duration: {median_duration/60:.1f} minutes")
        print(f"  Shortest: {min(durations)/60:.1f} minutes" if durations else "  Shortest: N/A")
        print(f"  Longest: {max(durations)/60:.1f} minutes" if durations else "  Longest: N/A")
        
        # Exchange type breakdown
        type_counts = {}
        for exchange in exchanges:
            ex_type = exchange.exchange_type
            type_counts[ex_type] = type_counts.get(ex_type, 0) + 1
        
        print(f"\n🔧 Exchange Types:")
        for ex_type, count in type_counts.items():
            percentage = (count / len(exchanges)) * 100
            print(f"  {ex_type}: {count} ({percentage:.1f}%)")
        
        # Recent exchanges detail
        print(f"\n🕒 Recent Exchanges (Last 10):")
        recent_exchanges = sorted(exchanges, key=lambda x: x.start_time, reverse=True)[:10]
        
        for i, exchange in enumerate(recent_exchanges, 1):
            start_str = exchange.start_time.strftime("%m/%d %H:%M:%S")
            duration_str = f"{exchange.duration_seconds/60:.1f}min"
            conf_str = f"{exchange.confidence*100:.0f}%"
            
            print(f"  {i:2d}. [{start_str}] {duration_str:>6} | "
                  f"{exchange.exchange_type:>8} | Conf: {conf_str:>4} | "
                  f"Ops: {exchange.operator_signals_count} | "
                  f"Seq: {exchange.sequence_events_count} | "
                  f"Rel: {exchange.relay_events_count}")
    
    def generate_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive basket exchange report"""
        exchanges = self.analyze_basket_exchanges(hours)
        
        if not exchanges:
            return {
                'period_hours': hours,
                'total_exchanges': 0,
                'exchanges': []
            }
        
        # Calculate efficiency metrics
        durations = [e.duration_seconds for e in exchanges]
        
        # Calculate monitor data statistics
        remote_temps = [e.remote_temperature for e in exchanges if e.remote_temperature is not None]
        fuel_consumptions = [e.fuel_consumption for e in exchanges if e.fuel_consumption is not None]
        
        report = {
            'period_hours': hours,
            'total_exchanges': len(exchanges),
            'avg_duration_minutes': statistics.mean(durations) / 60,
            'median_duration_minutes': statistics.median(durations) / 60,
            'min_duration_minutes': min(durations) / 60,
            'max_duration_minutes': max(durations) / 60,
            'exchanges_per_hour': len(exchanges) / hours,
            'exchange_types': {},
            'exchanges': [e.to_dict() for e in exchanges]
        }
        
        # Add monitor data statistics if available
        if remote_temps:
            report['remote_temperature_stats'] = {
                'avg_temp_f': round(statistics.mean(remote_temps), 1),
                'min_temp_f': round(min(remote_temps), 1),
                'max_temp_f': round(max(remote_temps), 1),
                'exchanges_with_temp_data': len(remote_temps)
            }
        
        if fuel_consumptions:
            positive_fuel = [f for f in fuel_consumptions if f > 0]  # Only positive consumption
            report['fuel_consumption_stats'] = {
                'total_fuel_gallons': round(sum(fuel_consumptions), 2),
                'avg_fuel_per_exchange_gallons': round(statistics.mean(fuel_consumptions), 3),
                'max_fuel_per_exchange_gallons': round(max(fuel_consumptions), 3),
                'exchanges_with_fuel_data': len(fuel_consumptions),
                'positive_consumption_exchanges': len(positive_fuel)
            }
        
        # Exchange type statistics
        for exchange in exchanges:
            ex_type = exchange.exchange_type
            if ex_type not in report['exchange_types']:
                report['exchange_types'][ex_type] = {
                    'count': 0,
                    'avg_duration_minutes': 0,
                    'percentage': 0
                }
            report['exchange_types'][ex_type]['count'] += 1
        
        # Calculate percentages and averages for each type
        for ex_type, stats in report['exchange_types'].items():
            type_exchanges = [e for e in exchanges if e.exchange_type == ex_type]
            type_durations = [e.duration_seconds for e in type_exchanges]
            
            stats['percentage'] = (stats['count'] / len(exchanges)) * 100
            stats['avg_duration_minutes'] = statistics.mean(type_durations) / 60
        
        return report

def main():
    """Main entry point for command-line usage"""
    parser = argparse.ArgumentParser(description='Analyze basket exchange operations')
    parser.add_argument('--hours', type=int, default=24,
                       help='Number of hours to analyze (default: 24)')
    parser.add_argument('--db', type=str, default='logsplitter_telemetry.db',
                       help='Path to telemetry database (default: logsplitter_telemetry.db)')
    parser.add_argument('--report', action='store_true',
                       help='Generate JSON report instead of console output')
    
    args = parser.parse_args()
    
    analyzer = BasketExchangeAnalyzer(args.db)
    
    if args.report:
        report = analyzer.generate_report(args.hours)
        print(json.dumps(report, indent=2))
    else:
        analyzer.analyze_basket_exchanges(args.hours)

if __name__ == '__main__':
    main()