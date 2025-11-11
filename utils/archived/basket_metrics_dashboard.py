#!/usr/bin/env python3
"""
Basket Exchange Metrics Dashboard for LogSplitter System

Real-time dashboard showing basket exchange operations with integrated
monitor data including temperature and fuel consumption.

Author: LogSplitter Monitor System
"""

import sqlite3
import json
import time
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import statistics
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
import numpy as np
import pandas as pd

@dataclass
class BasketExchange:
    """Represents a detected basket exchange operation with environmental data"""
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    operator_signals: List[Dict[str, Any]]
    sequence_events: List[Dict[str, Any]]
    relay_events: List[Dict[str, Any]]
    exchange_type: str  # 'MANUAL', 'SEQUENCE', or 'MIXED'
    confidence: float   # 0.0-1.0 confidence in detection
    
    # Environmental data from monitor
    avg_remote_temp: Optional[float] = None
    min_remote_temp: Optional[float] = None
    max_remote_temp: Optional[float] = None
    fuel_consumption: Optional[float] = None
    avg_pressure: Optional[float] = None
    max_pressure: Optional[float] = None
    
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
            'confidence': round(self.confidence, 2),
            'efficiency_score': self._calculate_efficiency_score()
        }
        
        # Add environmental data
        if self.avg_remote_temp is not None:
            result.update({
                'avg_remote_temp_f': round(self.avg_remote_temp, 1),
                'min_remote_temp_f': round(self.min_remote_temp, 1),
                'max_remote_temp_f': round(self.max_remote_temp, 1),
                'temp_stability': round(self.max_remote_temp - self.min_remote_temp, 1)
            })
        
        if self.fuel_consumption is not None:
            result['fuel_consumption_gallons'] = round(self.fuel_consumption, 3)
            result['fuel_efficiency_gal_per_min'] = round(self.fuel_consumption / (self.duration_seconds / 60), 4)
        
        if self.avg_pressure is not None:
            result.update({
                'avg_pressure_psi': round(self.avg_pressure, 1),
                'max_pressure_psi': round(self.max_pressure, 1)
            })
        
        return result
    
    def _calculate_efficiency_score(self) -> float:
        """Calculate efficiency score based on duration, fuel, and temperature"""
        score = 100.0
        
        # Duration penalty (longer operations are less efficient)
        if self.duration_seconds > 180:  # 3 minutes
            score -= min(20, (self.duration_seconds - 180) / 30)
        
        # Fuel consumption penalty
        if self.fuel_consumption and self.fuel_consumption > 0.1:  # > 0.1 gallons
            score -= min(15, (self.fuel_consumption - 0.1) * 100)
        
        # Temperature stability bonus
        if self.avg_remote_temp and self.min_remote_temp and self.max_remote_temp:
            temp_range = self.max_remote_temp - self.min_remote_temp
            if temp_range < 5:  # Very stable temperature
                score += 10
            elif temp_range > 15:  # Unstable temperature
                score -= 10
        
        # Pressure efficiency
        if self.max_pressure and self.max_pressure > 3000:  # High pressure usage
            score -= 5
        
        return max(0, min(100, score))

class BasketMetricsDashboard:
    """Real-time dashboard for basket exchange metrics"""
    
    def __init__(self, db_path: str = 'logsplitter_data.db'):
        self.db_path = db_path
        self.fig, self.axes = plt.subplots(2, 2, figsize=(16, 12))
        self.fig.suptitle('LogSplitter Basket Exchange Metrics Dashboard', fontsize=16, fontweight='bold')
        
        # Configure axes
        self.setup_axes()
        
        # Data storage
        self.exchanges = []
        self.pressure_data = []
        self.temperature_data = []
        self.fuel_data = []
        
        # Analysis parameters
        self.min_exchange_duration = 1  # seconds (allow very short exchanges)
        self.max_exchange_duration = 600  # 10 minutes
        self.operator_signal_timeout = 30  # seconds (shorter timeout for responsive detection)
        
    def setup_axes(self):
        """Configure dashboard axes"""
        # Top left - Exchange timeline
        self.axes[0, 0].set_title('Basket Exchanges Over Time', fontweight='bold')
        self.axes[0, 0].set_xlabel('Time')
        self.axes[0, 0].set_ylabel('Duration (minutes)')
        
        # Top right - Efficiency scores
        self.axes[0, 1].set_title('Exchange Efficiency Scores', fontweight='bold')
        self.axes[0, 1].set_xlabel('Exchange #')
        self.axes[0, 1].set_ylabel('Efficiency Score')
        self.axes[0, 1].set_ylim(0, 100)
        
        # Bottom left - Environmental data
        self.axes[1, 0].set_title('Environmental Conditions', fontweight='bold')
        self.axes[1, 0].set_xlabel('Time')
        self.axes[1, 0].set_ylabel('Temperature (°F) / Pressure (PSI/100)')
        
        # Bottom right - Fuel consumption
        self.axes[1, 1].set_title('Fuel Efficiency', fontweight='bold')
        self.axes[1, 1].set_xlabel('Exchange Duration (min)')
        self.axes[1, 1].set_ylabel('Fuel Consumption (gallons)')
        
        plt.tight_layout()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def analyze_basket_exchanges(self, hours: int = 24) -> List[BasketExchange]:
        """Analyze recent basket exchanges with environmental data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get SPLITTER_OPERATOR signals
            cursor.execute("""
                SELECT received_timestamp, controller_timestamp, payload_json
                FROM telemetry 
                WHERE received_timestamp > datetime('now', '-{} hours')
                AND message_type_name = 'DIGITAL_INPUT'
                AND json_extract(payload_json, '$.input_type_name') = 'SPLITTER_OPERATOR'
                ORDER BY controller_timestamp ASC
            """.format(hours))
            
            operator_events = []
            for row in cursor.fetchall():
                try:
                    payload = json.loads(row[2])
                    operator_events.append({
                        'timestamp': datetime.fromisoformat(row[0]),
                        'controller_time': row[1],
                        'payload': payload
                    })
                except (json.JSONDecodeError, ValueError):
                    continue
            
            if not operator_events:
                print("No SPLITTER_OPERATOR signals found in the time period")
                conn.close()
                return []
            
            # Identify exchange windows
            exchange_windows = self._identify_exchange_windows(operator_events)
            
            # Get all telemetry and monitor data for each window
            exchanges = []
            for start_time, end_time in exchange_windows:
                exchange = self._analyze_exchange_window(conn, start_time, end_time, operator_events)
                if exchange:
                    exchanges.append(exchange)
            
            conn.close()
            return exchanges
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []
    
    def _identify_exchange_windows(self, operator_events: List[Dict[str, Any]]) -> List[Tuple[datetime, datetime]]:
        """Identify basket exchange events from button presses (ACTIVE signals)"""
        windows = []
        
        if not operator_events:
            return windows
        
        # Each ACTIVE signal represents a basket exchange button press
        # Create a window around each ACTIVE signal to capture related events
        
        for event in operator_events:
            payload = event.get('payload', {})
            if payload.get('state_name') == 'ACTIVE':
                # This is a button press - create exchange window around it
                button_time = event['timestamp']
                
                # Create window: 10 seconds before to 20 seconds after button press
                # This captures any sequence/relay events triggered by the button press
                window_start = button_time - timedelta(seconds=10)
                window_end = button_time + timedelta(seconds=20)
                
                windows.append((window_start, window_end))
        
        return windows
    
    def _analyze_exchange_window(self, conn: sqlite3.Connection, start_time: datetime, 
                                end_time: datetime, all_operator_events: List[Dict[str, Any]]) -> Optional[BasketExchange]:
        """Analyze a specific exchange window"""
        cursor = conn.cursor()
        
        # Get operator signals in this window
        operator_signals = [e for e in all_operator_events 
                          if start_time <= e['timestamp'] <= end_time]
        
        if not operator_signals:
            return None
        
        # Get sequence events
        cursor.execute("""
            SELECT received_timestamp, payload_json FROM telemetry
            WHERE received_timestamp BETWEEN ? AND ?
            AND message_type_name = 'SEQUENCE_EVENT'
            ORDER BY received_timestamp ASC
        """, (start_time.isoformat(), end_time.isoformat()))
        
        sequence_events = []
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[1]) if row[1] else {}
                sequence_events.append({
                    'timestamp': datetime.fromisoformat(row[0]),
                    'payload': payload
                })
            except (json.JSONDecodeError, ValueError):
                continue
        
        # Get relay events
        cursor.execute("""
            SELECT received_timestamp, payload_json FROM telemetry
            WHERE received_timestamp BETWEEN ? AND ?
            AND message_type_name = 'RELAY_EVENT'
            ORDER BY received_timestamp ASC
        """, (start_time.isoformat(), end_time.isoformat()))
        
        relay_events = []
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[1]) if row[1] else {}
                relay_events.append({
                    'timestamp': datetime.fromisoformat(row[0]),
                    'payload': payload
                })
            except (json.JSONDecodeError, ValueError):
                continue
        
        # Get monitor data (temperature, fuel)
        monitor_data = self._get_monitor_data(conn, start_time, end_time)
        
        # Get pressure data
        pressure_data = self._get_pressure_data(conn, start_time, end_time)
        
        # Classify exchange type and calculate confidence
        exchange_type = self._classify_exchange(operator_signals, sequence_events, relay_events)
        confidence = self._calculate_confidence(operator_signals, sequence_events, relay_events)
        
        if confidence < 0.6:  # Low confidence exchanges are filtered out
            return None
        
        # Calculate environmental metrics
        remote_temps = [d['value'] for d in monitor_data 
                       if d['topic'] == 'monitor/temperature/remote' and d['value'] is not None]
        
        fuel_readings = [d['value'] for d in monitor_data 
                        if d['topic'] == 'monitor/fuel_gallons' and d['value'] is not None]
        
        pressures = [d for d in pressure_data if d['pressure_psi'] is not None and d['pressure_psi'] > 0]
        
        # Create exchange object
        duration = (end_time - start_time).total_seconds()
        
        exchange = BasketExchange(
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            operator_signals=operator_signals,
            sequence_events=sequence_events,
            relay_events=relay_events,
            exchange_type=exchange_type,
            confidence=confidence
        )
        
        # Add environmental data
        if remote_temps:
            exchange.avg_remote_temp = statistics.mean(remote_temps)
            exchange.min_remote_temp = min(remote_temps)
            exchange.max_remote_temp = max(remote_temps)
        
        if len(fuel_readings) >= 2:
            # Fuel consumption = initial - final
            exchange.fuel_consumption = fuel_readings[0] - fuel_readings[-1]
        
        if pressures:
            exchange.avg_pressure = statistics.mean([p['pressure_psi'] for p in pressures])
            exchange.max_pressure = max([p['pressure_psi'] for p in pressures])
        
        return exchange
    
    def _get_monitor_data(self, conn: sqlite3.Connection, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get monitor data within time window"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT received_timestamp, topic, value FROM monitor_data
            WHERE received_timestamp BETWEEN ? AND ?
            ORDER BY received_timestamp ASC
        """, (start_time.isoformat(), end_time.isoformat()))
        
        monitor_data = []
        for row in cursor.fetchall():
            monitor_data.append({
                'timestamp': datetime.fromisoformat(row[0]),
                'topic': row[1],
                'value': row[2]
            })
        
        return monitor_data
    
    def _get_pressure_data(self, conn: sqlite3.Connection, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get pressure data within time window"""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT received_timestamp, payload_json FROM telemetry
            WHERE received_timestamp BETWEEN ? AND ?
            AND message_type_name = 'PRESSURE'
            ORDER BY received_timestamp ASC
        """, (start_time.isoformat(), end_time.isoformat()))
        
        pressure_data = []
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[1]) if row[1] else {}
                pressure_data.append({
                    'timestamp': datetime.fromisoformat(row[0]),
                    'pressure_psi': payload.get('pressure_psi', 0)
                })
            except (json.JSONDecodeError, ValueError):
                continue
        
        return pressure_data
    
    def _classify_exchange(self, operator_signals: List[Dict], sequence_events: List[Dict], relay_events: List[Dict]) -> str:
        """Classify the type of basket exchange based on button press response"""
        if sequence_events and len(sequence_events) >= 2:
            if relay_events:
                return 'MIXED'  # Automatic sequence with manual relay operations
            else:
                return 'SEQUENCE'  # Pure automatic sequence triggered by button
        elif relay_events:
            return 'MANUAL'  # Manual relay operations triggered by button
        else:
            return 'BUTTON_ONLY'  # Just the button press, no other operations detected
    
    def _calculate_confidence(self, operator_signals: List[Dict], sequence_events: List[Dict], relay_events: List[Dict]) -> float:
        """Calculate confidence in basket exchange detection"""
        confidence = 0.8  # Start with high confidence for button press detection
        
        # Having ACTIVE operator signal is required (button press)
        active_signals = [s for s in operator_signals if s.get('payload', {}).get('state_name') == 'ACTIVE']
        if not active_signals:
            return 0.0  # No button press = no exchange
        
        # Multiple button presses in window reduces confidence (might be accidental)
        if len(active_signals) > 1:
            confidence -= 0.2
        
        # Presence of sequence events increases confidence (system responded)
        if sequence_events:
            confidence += 0.2
        
        # Presence of relay events increases confidence (actual operation)
        if relay_events:
            confidence += 0.2
        
        return min(1.0, max(0.6, confidence))  # Always at least 60% if button was pressed
    
    def update_dashboard(self, hours: int = 24):
        """Update dashboard with fresh data"""
        try:
            # Clear previous plots
            for ax in self.axes.flat:
                ax.clear()
            
            self.setup_axes()
            
            # Analyze exchanges
            exchanges = self.analyze_basket_exchanges(hours)
            
            if not exchanges:
                # Show "waiting for data" message
                self.axes[0, 0].text(0.5, 0.5, 'Waiting for basket exchange data...\nRun splitter operations to see metrics here', 
                                    ha='center', va='center', transform=self.axes[0, 0].transAxes, fontsize=12)
                return
            
            # Plot exchange timeline
            times = [ex.start_time for ex in exchanges]
            durations = [ex.duration_seconds / 60 for ex in exchanges]
            colors = ['green' if ex.exchange_type == 'SEQUENCE' else 'orange' if ex.exchange_type == 'MIXED' else 'blue' 
                     for ex in exchanges]
            
            self.axes[0, 0].scatter(times, durations, c=colors, alpha=0.7, s=60)
            self.axes[0, 0].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            self.axes[0, 0].tick_params(axis='x', rotation=45)
            
            # Plot efficiency scores
            efficiency_scores = [ex._calculate_efficiency_score() for ex in exchanges]
            exchange_nums = list(range(1, len(exchanges) + 1))
            self.axes[0, 1].bar(exchange_nums, efficiency_scores, color=['green' if score >= 80 else 'yellow' if score >= 60 else 'red' 
                                                                        for score in efficiency_scores])
            
            # Plot environmental data
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get recent temperature and pressure data
            cursor.execute("""
                SELECT received_timestamp, topic, value FROM monitor_data
                WHERE received_timestamp > datetime('now', '-{} hours')
                AND topic IN ('monitor/temperature/remote', 'monitor/temperature')
                ORDER BY received_timestamp ASC
            """.format(hours))
            
            temp_times = []
            temp_values = []
            for row in cursor.fetchall():
                temp_times.append(datetime.fromisoformat(row[0]))
                temp_values.append(row[2])
            
            if temp_times:
                self.axes[1, 0].plot(temp_times, temp_values, 'r-', label='Temperature (°F)', linewidth=2)
            
            # Get pressure data
            cursor.execute("""
                SELECT received_timestamp, payload_json FROM telemetry
                WHERE received_timestamp > datetime('now', '-{} hours')
                AND message_type_name = 'PRESSURE'
                ORDER BY received_timestamp ASC
            """.format(hours))
            
            pressure_times = []
            pressure_values = []
            for row in cursor.fetchall():
                try:
                    payload = json.loads(row[1]) if row[1] else {}
                    pressure_psi = payload.get('pressure_psi', 0)
                    if pressure_psi and pressure_psi > 0:
                        pressure_times.append(datetime.fromisoformat(row[0]))
                        pressure_values.append(pressure_psi / 100)  # Scale for display
                except (json.JSONDecodeError, ValueError):
                    continue
            
            if pressure_times:
                self.axes[1, 0].plot(pressure_times, pressure_values, 'b-', label='Pressure (PSI/100)', alpha=0.7)
            
            self.axes[1, 0].legend()
            self.axes[1, 0].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            self.axes[1, 0].tick_params(axis='x', rotation=45)
            
            # Plot fuel efficiency
            fuel_exchanges = [ex for ex in exchanges if ex.fuel_consumption is not None and ex.fuel_consumption > 0]
            if fuel_exchanges:
                fuel_durations = [ex.duration_seconds / 60 for ex in fuel_exchanges]
                fuel_consumptions = [ex.fuel_consumption for ex in fuel_exchanges]
                self.axes[1, 1].scatter(fuel_durations, fuel_consumptions, alpha=0.7, s=60, c='purple')
                
                # Add trend line if enough data
                if len(fuel_exchanges) >= 3:
                    z = np.polyfit(fuel_durations, fuel_consumptions, 1)
                    p = np.poly1d(z)
                    self.axes[1, 1].plot(fuel_durations, p(fuel_durations), "r--", alpha=0.8)
            
            conn.close()
            
            # Add statistics text
            if exchanges:
                stats_text = f"Exchanges: {len(exchanges)} | "
                stats_text += f"Avg Duration: {statistics.mean([ex.duration_seconds/60 for ex in exchanges]):.1f} min | "
                stats_text += f"Avg Efficiency: {statistics.mean(efficiency_scores):.1f}%"
                
                if fuel_exchanges:
                    avg_fuel = statistics.mean([ex.fuel_consumption for ex in fuel_exchanges])
                    stats_text += f" | Avg Fuel: {avg_fuel:.3f} gal"
                
                self.fig.suptitle(f'LogSplitter Basket Exchange Metrics Dashboard\n{stats_text}', 
                                 fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
        except Exception as e:
            print(f"Dashboard update error: {e}")
            # Show error on dashboard
            self.axes[0, 0].text(0.5, 0.5, f'Dashboard Error: {str(e)}', 
                               ha='center', va='center', transform=self.axes[0, 0].transAxes, fontsize=12)
    
    def generate_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive basket exchange report"""
        exchanges = self.analyze_basket_exchanges(hours)
        
        if not exchanges:
            return {
                'period_hours': hours,
                'total_exchanges': 0,
                'message': 'No basket exchanges detected. Run splitter operations to generate data.',
                'exchanges': []
            }
        
        # Calculate metrics
        durations = [e.duration_seconds for e in exchanges]
        efficiency_scores = [e._calculate_efficiency_score() for e in exchanges]
        
        report = {
            'period_hours': hours,
            'total_exchanges': len(exchanges),
            'avg_duration_minutes': statistics.mean(durations) / 60,
            'median_duration_minutes': statistics.median(durations) / 60,
            'min_duration_minutes': min(durations) / 60,
            'max_duration_minutes': max(durations) / 60,
            'exchanges_per_hour': len(exchanges) / hours,
            'avg_efficiency_score': statistics.mean(efficiency_scores),
            'exchanges': [e.to_dict() for e in exchanges]
        }
        
        # Environmental statistics
        temp_exchanges = [e for e in exchanges if e.avg_remote_temp is not None]
        if temp_exchanges:
            report['environmental_stats'] = {
                'avg_temperature_f': statistics.mean([e.avg_remote_temp for e in temp_exchanges]),
                'temperature_range_f': [
                    min([e.min_remote_temp for e in temp_exchanges]),
                    max([e.max_remote_temp for e in temp_exchanges])
                ],
                'exchanges_with_temp_data': len(temp_exchanges)
            }
        
        # Fuel statistics
        fuel_exchanges = [e for e in exchanges if e.fuel_consumption is not None and e.fuel_consumption > 0]
        if fuel_exchanges:
            total_fuel = sum([e.fuel_consumption for e in fuel_exchanges])
            report['fuel_stats'] = {
                'total_fuel_consumption_gallons': total_fuel,
                'avg_fuel_per_exchange_gallons': statistics.mean([e.fuel_consumption for e in fuel_exchanges]),
                'fuel_efficiency_exchanges_per_gallon': len(fuel_exchanges) / total_fuel if total_fuel > 0 else 0,
                'exchanges_with_fuel_data': len(fuel_exchanges)
            }
        
        # Exchange type breakdown
        type_counts = {}
        for exchange in exchanges:
            ex_type = exchange.exchange_type
            if ex_type not in type_counts:
                type_counts[ex_type] = {'count': 0, 'avg_duration': 0, 'avg_efficiency': 0}
            type_counts[ex_type]['count'] += 1
        
        for ex_type, stats in type_counts.items():
            type_exchanges = [e for e in exchanges if e.exchange_type == ex_type]
            stats['avg_duration_minutes'] = statistics.mean([e.duration_seconds for e in type_exchanges]) / 60
            stats['avg_efficiency'] = statistics.mean([e._calculate_efficiency_score() for e in type_exchanges])
            stats['percentage'] = (stats['count'] / len(exchanges)) * 100
        
        report['exchange_types'] = type_counts
        
        return report

def main():
    parser = argparse.ArgumentParser(description='LogSplitter Basket Exchange Metrics Dashboard')
    parser.add_argument('--hours', type=int, default=24, help='Hours of data to analyze (default: 24)')
    parser.add_argument('--report-only', action='store_true', help='Generate report only, no GUI')
    parser.add_argument('--live', action='store_true', help='Live updating dashboard')
    args = parser.parse_args()
    
    dashboard = BasketMetricsDashboard()
    
    if args.report_only:
        # Generate text report
        report = dashboard.generate_report(args.hours)
        
        print("🧺 LogSplitter Basket Exchange Report")
        print("=" * 60)
        print(f"Analysis Period: Last {report['period_hours']} hours")
        print(f"Total Exchanges: {report['total_exchanges']}")
        
        if report['total_exchanges'] > 0:
            print(f"Average Duration: {report['avg_duration_minutes']:.1f} minutes")
            print(f"Exchanges per Hour: {report['exchanges_per_hour']:.1f}")
            print(f"Average Efficiency Score: {report['avg_efficiency_score']:.1f}%")
            
            if 'environmental_stats' in report:
                env = report['environmental_stats']
                print(f"Average Temperature: {env['avg_temperature_f']:.1f}°F")
                print(f"Temperature Range: {env['temperature_range_f'][0]:.1f}°F - {env['temperature_range_f'][1]:.1f}°F")
            
            if 'fuel_stats' in report:
                fuel = report['fuel_stats']
                print(f"Total Fuel Consumption: {fuel['total_fuel_consumption_gallons']:.3f} gallons")
                print(f"Average Fuel per Exchange: {fuel['avg_fuel_per_exchange_gallons']:.3f} gallons")
            
            print("\nExchange Type Breakdown:")
            for ex_type, stats in report['exchange_types'].items():
                print(f"  {ex_type}: {stats['count']} exchanges ({stats['percentage']:.1f}%), "
                      f"avg {stats['avg_duration_minutes']:.1f} min, {stats['avg_efficiency']:.1f}% efficiency")
        else:
            print(report.get('message', 'No data available'))
            
    elif args.live:
        # Live updating dashboard
        def update_plot(frame):
            dashboard.update_dashboard(args.hours)
            return []
        
        ani = FuncAnimation(dashboard.fig, update_plot, interval=30000, blit=False)  # Update every 30 seconds
        plt.show()
    else:
        # Static dashboard
        dashboard.update_dashboard(args.hours)
        plt.show()

if __name__ == "__main__":
    main()