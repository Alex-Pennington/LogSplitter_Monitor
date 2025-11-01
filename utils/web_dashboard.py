#!/usr/bin/env python3
"""
LogSplitter Protobuf Web Dashboard

Real-time web dashboard for visualizing LogSplitter protobuf telemetry data.

Features:
- Real-time message monitoring
- Historical data analysis
- Message type breakdown
- System statistics
- Interactive charts and graphs
"""

import json
import sqlite3
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'logsplitter_dashboard_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

DATABASE_PATH = os.getenv('DATABASE_PATH', 'logsplitter_data.db')
DASHBOARD_HOST = os.getenv('DASHBOARD_HOST', '0.0.0.0')
DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', '5000'))

class DashboardDataProvider:
    """Data provider for the web dashboard"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def get_recent_messages(self, limit: int = 50):
        """Get recent messages for real-time display"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    received_timestamp,
                    controller_timestamp,
                    message_type,
                    message_type_name,
                    sequence_id,
                    payload_json,
                    raw_size
                FROM telemetry 
                ORDER BY received_timestamp DESC 
                LIMIT ?
            """, (limit,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'received_timestamp': row[0],
                    'controller_timestamp': row[1],
                    'message_type': f"0x{row[2]:02x}",
                    'message_type_name': row[3],
                    'sequence_id': row[4],
                    'payload': json.loads(row[5]),
                    'raw_size': row[6]
                })
            
            conn.close()
            return messages
            
        except Exception as e:
            print(f"Error getting recent messages: {e}")
            return []
    
    def get_message_type_stats(self):
        """Get message type statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    message_type,
                    message_type_name,
                    COUNT(*) as count,
                    AVG(raw_size) as avg_size,
                    MIN(controller_timestamp) as first_seen,
                    MAX(controller_timestamp) as last_seen
                FROM telemetry 
                GROUP BY message_type, message_type_name
                ORDER BY count DESC
            """)
            
            stats = []
            for row in cursor.fetchall():
                stats.append({
                    'type_id': f"0x{row[0]:02x}",
                    'type_name': row[1],
                    'count': row[2],
                    'avg_size': round(row[3], 1),
                    'first_seen': row[4],
                    'last_seen': row[5]
                })
            
            conn.close()
            return stats
            
        except Exception as e:
            print(f"Error getting message type stats: {e}")
            return []
    
    def get_hourly_activity(self, hours: int = 24):
        """Get hourly message activity for charts"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', received_timestamp) as hour,
                    message_type_name,
                    COUNT(*) as count
                FROM telemetry 
                WHERE received_timestamp > datetime('now', '-{} hours')
                GROUP BY hour, message_type_name
                ORDER BY hour ASC
            """.format(hours))
            
            activity = {}
            for row in cursor.fetchall():
                hour = row[0]
                msg_type = row[1]
                count = row[2]
                
                if hour not in activity:
                    activity[hour] = {}
                activity[hour][msg_type] = count
            
            conn.close()
            return activity
            
        except Exception as e:
            print(f"Error getting hourly activity: {e}")
            return {}
    
    def get_system_overview(self):
        """Get system overview statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Total messages
            cursor.execute("SELECT COUNT(*) FROM telemetry")
            total_messages = cursor.fetchone()[0]
            
            # Messages in last hour
            cursor.execute("""
                SELECT COUNT(*) FROM telemetry 
                WHERE received_timestamp > datetime('now', '-1 hour')
            """)
            messages_last_hour = cursor.fetchone()[0]
            
            # Database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            
            # Unique message types
            cursor.execute("SELECT COUNT(DISTINCT message_type) FROM telemetry")
            unique_types = cursor.fetchone()[0]
            
            # Latest message
            cursor.execute("""
                SELECT received_timestamp, message_type_name 
                FROM telemetry 
                ORDER BY received_timestamp DESC 
                LIMIT 1
            """)
            latest = cursor.fetchone()
            latest_message = latest[0] if latest else None
            latest_type = latest[1] if latest else None
            
            conn.close()
            
            return {
                'total_messages': total_messages,
                'messages_last_hour': messages_last_hour,
                'database_size_mb': round(db_size_mb, 2),
                'unique_types': unique_types,
                'latest_message': latest_message,
                'latest_type': latest_type
            }
            
        except Exception as e:
            print(f"Error getting system overview: {e}")
            return {}
    
    def get_analytics_data(self):
        """Get comprehensive analytics data for splitter operations"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            analytics = {
                'cycle_analysis': self._get_cycle_analysis(cursor),
                'pressure_analysis': self._get_pressure_analysis(cursor),
                'efficiency_metrics': self._get_efficiency_metrics(cursor),
                'safety_analysis': self._get_safety_analysis(cursor),
                'operational_patterns': self._get_operational_patterns(cursor),
                'system_health': self._get_system_health_metrics(cursor)
            }
            
            conn.close()
            return analytics
            
        except Exception as e:
            print(f"Error getting analytics data: {e}")
            return {}
    
    def _get_cycle_analysis(self, cursor):
        """Analyze splitting cycles from sequence events"""
        # Get sequence events for cycle analysis
        cursor.execute("""
            SELECT 
                received_timestamp,
                payload_json,
                controller_timestamp
            FROM telemetry 
            WHERE message_type = 23 AND message_type_name = 'SEQUENCE_EVENT'
            ORDER BY received_timestamp DESC
            LIMIT 100
        """)
        
        sequence_events = []
        cycles_completed = 0
        cycles_aborted = 0
        avg_cycle_time = 0
        cycle_times = []
        
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[1])
                event_type = payload.get('event_type_name', '')
                
                if event_type == 'SEQUENCE_STARTED':
                    sequence_events.append({
                        'type': 'start',
                        'timestamp': row[0],
                        'controller_time': row[2]
                    })
                elif event_type == 'SEQUENCE_COMPLETE':
                    cycles_completed += 1
                    sequence_events.append({
                        'type': 'complete',
                        'timestamp': row[0],
                        'controller_time': row[2]
                    })
                elif event_type == 'SEQUENCE_ABORTED':
                    cycles_aborted += 1
                    
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Calculate cycle times
        starts = [e for e in sequence_events if e['type'] == 'start']
        completes = [e for e in sequence_events if e['type'] == 'complete']
        
        for complete in completes:
            # Find matching start event
            matching_start = None
            for start in starts:
                if start['controller_time'] < complete['controller_time']:
                    if not matching_start or start['controller_time'] > matching_start['controller_time']:
                        matching_start = start
            
            if matching_start:
                cycle_time = complete['controller_time'] - matching_start['controller_time']
                if 0 < cycle_time < 300000:  # Reasonable cycle time (5 minutes max)
                    cycle_times.append(cycle_time / 1000.0)  # Convert to seconds
        
        if cycle_times:
            avg_cycle_time = sum(cycle_times) / len(cycle_times)
        
        success_rate = 0
        if cycles_completed + cycles_aborted > 0:
            success_rate = (cycles_completed / (cycles_completed + cycles_aborted)) * 100
        
        return {
            'cycles_completed': cycles_completed,
            'short_strokes': cycles_aborted,  # Renamed from cycles_aborted
            'success_rate': round(success_rate, 1),
            'avg_cycle_time_sec': round(avg_cycle_time, 1),
            'cycle_times': cycle_times[-10:],  # Last 10 cycle times
            'total_cycles': cycles_completed + cycles_aborted
        }
    
    def _get_pressure_analysis(self, cursor):
        """Analyze pressure patterns and performance"""
        cursor.execute("""
            SELECT 
                payload_json,
                received_timestamp
            FROM telemetry 
            WHERE message_type = 19 AND message_type_name = 'PRESSURE'
            ORDER BY received_timestamp DESC
            LIMIT 200
        """)
        
        pressures = []
        max_pressure = 0
        avg_pressure = 0
        pressure_spikes = 0
        pressure_faults = 0
        
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[0])
                pressure_psi = payload.get('pressure_psi', 0)
                pressure_type_name = payload.get('pressure_type_name', '')
                is_fault = payload.get('is_fault', False)
                timestamp = row[1]
                
                # Only process SYSTEM_PRESSURE (hydraulic system pressure)
                if pressure_type_name != 'SYSTEM_PRESSURE':
                    continue
                
                if is_fault:
                    pressure_faults += 1
                
                # Validate pressure is within reasonable range (0-5000 PSI)
                if pressure_psi > 0 and pressure_psi <= 5000:
                    pressures.append({
                        'pressure': pressure_psi,
                        'timestamp': timestamp
                    })
                    
                    if pressure_psi > max_pressure:
                        max_pressure = pressure_psi
                    
                    # Count pressure spikes (over 2500 PSI)
                    if pressure_psi > 2500:
                        pressure_spikes += 1
                        
            except (json.JSONDecodeError, KeyError):
                continue
        
        if pressures:
            avg_pressure = sum(p['pressure'] for p in pressures) / len(pressures)
        
        # Calculate pressure efficiency (operating pressure vs max rated)
        rated_max = 5000  # PSI - system max
        pressure_efficiency = 0
        if max_pressure > 0:
            pressure_efficiency = (avg_pressure / rated_max) * 100
        
        return {
            'max_pressure_psi': round(max_pressure, 1),
            'avg_pressure_psi': round(avg_pressure, 1),
            'pressure_spikes': pressure_spikes,
            'pressure_faults': pressure_faults,
            'pressure_efficiency': round(pressure_efficiency, 1),
            'recent_pressures': [p['pressure'] for p in pressures[-20:]]
        }
    
    def _get_efficiency_metrics(self, cursor):
        """Calculate operational efficiency metrics"""
        # Get relay events for uptime analysis
        cursor.execute("""
            SELECT 
                payload_json,
                received_timestamp
            FROM telemetry 
            WHERE message_type = 18 AND message_type_name = 'RELAY_EVENT'
            ORDER BY received_timestamp DESC
            LIMIT 100
        """)
        
        relay_events = []
        extend_operations = 0
        retract_operations = 0
        manual_operations = 0
        auto_operations = 0
        
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[0])
                relay_name = payload.get('relay_name', '')
                state = payload.get('state', False)
                is_manual = payload.get('is_manual', False)
                success = payload.get('success', False)
                
                if success and state:  # Only count successful activations
                    if relay_name == 'R1':  # Extend relay
                        extend_operations += 1
                    elif relay_name == 'R2':  # Retract relay
                        retract_operations += 1
                    
                    if is_manual:
                        manual_operations += 1
                    else:
                        auto_operations += 1
                        
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Calculate automation ratio
        total_ops = manual_operations + auto_operations
        automation_ratio = 0
        if total_ops > 0:
            automation_ratio = (auto_operations / total_ops) * 100
        
        # Get system status for uptime calculation
        cursor.execute("""
            SELECT 
                payload_json
            FROM telemetry 
            WHERE message_type = 22 AND message_type_name = 'SYSTEM_STATUS'
            ORDER BY received_timestamp DESC
            LIMIT 1
        """)
        
        uptime_minutes = 0
        system_load = 0
        
        result = cursor.fetchone()
        if result:
            try:
                payload = json.loads(result[0])
                uptime_minutes = payload.get('uptime_minutes', 0)
                loop_freq = payload.get('loop_frequency_hz', 0)
                # Calculate system load based on loop frequency (lower = higher load)
                if loop_freq > 0:
                    system_load = max(0, 100 - (loop_freq / 100 * 100))
            except (json.JSONDecodeError, KeyError):
                pass
        
        return {
            'extend_operations': extend_operations,
            'retract_operations': retract_operations,
            'manual_operations': manual_operations,
            'auto_operations': auto_operations,
            'automation_ratio': round(automation_ratio, 1),
            'uptime_minutes': round(uptime_minutes, 1),
            'system_load_percent': round(system_load, 1),
            'total_operations': total_ops
        }
    
    def _get_safety_analysis(self, cursor):
        """Analyze safety system performance"""
        cursor.execute("""
            SELECT 
                payload_json,
                received_timestamp
            FROM telemetry 
            WHERE message_type = 21 AND message_type_name = 'SAFETY_EVENT'
            ORDER BY received_timestamp DESC
            LIMIT 50
        """)
        
        safety_activations = 0
        emergency_stops = 0
        limit_triggers = 0
        pressure_safeties = 0
        last_safety_event = None
        
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[0])
                event_type = payload.get('event_type_name', '')
                is_active = payload.get('is_active', False)
                timestamp = row[1]
                
                if is_active:
                    if 'SAFETY_ACTIVATED' in event_type:
                        safety_activations += 1
                        if not last_safety_event:
                            last_safety_event = timestamp
                    elif 'EMERGENCY_STOP' in event_type:
                        emergency_stops += 1
                    elif 'LIMIT_SWITCH' in event_type:
                        limit_triggers += 1
                    elif 'PRESSURE_SAFETY' in event_type:
                        pressure_safeties += 1
                        
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Calculate safety score (fewer activations = better)
        total_safety_events = safety_activations + emergency_stops + limit_triggers + pressure_safeties
        safety_score = max(0, 100 - (total_safety_events * 5))  # Reduce 5 points per event
        
        return {
            'safety_activations': safety_activations,
            'emergency_stops': emergency_stops,
            'limit_triggers': limit_triggers,
            'pressure_safeties': pressure_safeties,
            'total_safety_events': total_safety_events,
            'safety_score': round(safety_score, 1),
            'last_safety_event': last_safety_event
        }
    
    def _get_operational_patterns(self, cursor):
        """Analyze operational patterns and timing"""
        cursor.execute("""
            SELECT 
                strftime('%H', received_timestamp) as hour,
                COUNT(*) as activity
            FROM telemetry 
            WHERE received_timestamp > datetime('now', '-7 days')
            GROUP BY hour
            ORDER BY hour
        """)
        
        hourly_activity = {}
        peak_hour = 0
        peak_activity = 0
        
        for row in cursor.fetchall():
            hour = int(row[0])
            activity = row[1]
            hourly_activity[hour] = activity
            
            if activity > peak_activity:
                peak_activity = activity
                peak_hour = hour
        
        # Get daily patterns
        cursor.execute("""
            SELECT 
                date(received_timestamp) as day,
                COUNT(*) as daily_activity
            FROM telemetry 
            WHERE received_timestamp > datetime('now', '-7 days')
            GROUP BY day
            ORDER BY day DESC
            LIMIT 7
        """)
        
        daily_patterns = []
        for row in cursor.fetchall():
            daily_patterns.append({
                'date': row[0],
                'activity': row[1]
            })
        
        return {
            'hourly_activity': hourly_activity,
            'peak_hour': peak_hour,
            'peak_activity': peak_activity,
            'daily_patterns': daily_patterns
        }
    
    def _get_system_health_metrics(self, cursor):
        """Get system health and performance metrics"""
        cursor.execute("""
            SELECT 
                payload_json,
                received_timestamp
            FROM telemetry 
            WHERE message_type = 22 AND message_type_name = 'SYSTEM_STATUS'
            ORDER BY received_timestamp DESC
            LIMIT 10
        """)
        
        memory_usage = []
        loop_frequencies = []
        error_counts = []
        
        for row in cursor.fetchall():
            try:
                payload = json.loads(row[0])
                free_memory = payload.get('free_memory_bytes', 0)
                loop_freq = payload.get('loop_frequency_hz', 0)
                active_errors = payload.get('active_error_count', 0)
                
                if free_memory > 0:
                    memory_usage.append(free_memory)
                if loop_freq > 0:
                    loop_frequencies.append(loop_freq)
                error_counts.append(active_errors)
                
            except (json.JSONDecodeError, KeyError):
                continue
        
        avg_memory = sum(memory_usage) / len(memory_usage) if memory_usage else 0
        avg_loop_freq = sum(loop_frequencies) / len(loop_frequencies) if loop_frequencies else 0
        avg_errors = sum(error_counts) / len(error_counts) if error_counts else 0
        
        # Calculate health score
        memory_score = min(100, (avg_memory / 10000) * 100) if avg_memory else 0
        performance_score = min(100, (avg_loop_freq / 1000) * 100) if avg_loop_freq else 0
        error_score = max(0, 100 - (avg_errors * 20))
        
        overall_health = (memory_score + performance_score + error_score) / 3
        
        return {
            'avg_free_memory': round(avg_memory, 0),
            'avg_loop_frequency': round(avg_loop_freq, 1),
            'avg_active_errors': round(avg_errors, 1),
            'memory_health_score': round(memory_score, 1),
            'performance_score': round(performance_score, 1),
            'error_score': round(error_score, 1),
            'overall_health_score': round(overall_health, 1)
        }
    
    def get_basket_metrics(self, hours: int = 24):
        """Get basket exchange metrics by analyzing SPLITTER_OPERATOR button presses"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get SPLITTER_OPERATOR button press events (Pin 8 ACTIVE signals)
            cursor.execute("""
                SELECT 
                    received_timestamp,
                    payload_json
                FROM telemetry 
                WHERE message_type = 16 
                  AND message_type_name = 'DIGITAL_INPUT'
                  AND received_timestamp > datetime('now', '-{} hours')
                ORDER BY received_timestamp ASC
            """.format(hours))
            
            button_presses = []
            for row in cursor.fetchall():
                try:
                    timestamp = row[0]
                    payload = json.loads(row[1]) if row[1] else {}
                    input_type_name = payload.get('input_type_name', '')
                    is_active = payload.get('state', False)
                    
                    if input_type_name == 'SPLITTER_OPERATOR' and is_active:
                        button_presses.append({
                            'timestamp': timestamp,
                            'payload': payload
                        })
                except (json.JSONDecodeError, KeyError):
                    continue
            
            # Each button press = one basket exchange
            exchanges_detected = len(button_presses)
            
            # Get completed sequences (cycles) in the same time window
            cursor.execute("""
                SELECT 
                    received_timestamp,
                    payload_json
                FROM telemetry 
                WHERE message_type = 23 
                  AND message_type_name = 'SEQUENCE_EVENT'
                  AND received_timestamp > datetime('now', '-{} hours')
                ORDER BY received_timestamp ASC
            """.format(hours))
            
            cycles_completed = 0
            for row in cursor.fetchall():
                try:
                    payload = json.loads(row[1])
                    event_type = payload.get('event_type_name', '')
                    if event_type == 'SEQUENCE_COMPLETE':
                        cycles_completed += 1
                except (json.JSONDecodeError, KeyError):
                    continue
            
            # Get environmental data for each exchange window (10s before, 20s after)
            exchanges_with_data = []
            for press in button_presses:
                press_time = press['timestamp']
                
                # Get monitor data (temperature, weight) in exchange window
                cursor.execute("""
                    SELECT 
                        topic,
                        value,
                        received_timestamp
                    FROM monitor_data 
                    WHERE received_timestamp BETWEEN 
                        datetime(?, '-10 seconds') AND datetime(?, '+20 seconds')
                    ORDER BY received_timestamp ASC
                """, (press_time, press_time))
                
                local_temps = []
                remote_temps = []
                weights = []
                for row in cursor.fetchall():
                    topic = row[0]
                    value = float(row[1]) if row[1] else 0
                    
                    if 'temperature/local' in topic and 50 < value < 200:
                        local_temps.append(value)
                    elif 'temperature/remote' in topic and 50 < value < 200:
                        remote_temps.append(value)
                    elif 'weight' in topic and value > 0:
                        weights.append(value)
                
                # Get sequence events in exchange window
                cursor.execute("""
                    SELECT 
                        payload_json
                    FROM telemetry 
                    WHERE message_type = 23 
                      AND message_type_name = 'SEQUENCE_EVENT'
                      AND payload_json NOT LIKE '%_legacy_empty%'
                      AND received_timestamp BETWEEN 
                        datetime(?, '-10 seconds') AND datetime(?, '+20 seconds')
                    ORDER BY received_timestamp ASC
                """, (press_time, press_time))
                
                seq_starts = 0
                seq_completes = 0
                seq_aborts = 0
                for row in cursor.fetchall():
                    try:
                        payload = json.loads(row[0])
                        event_type_name = payload.get('event_type_name', '')
                        if 'STARTED' in event_type_name:
                            seq_starts += 1
                        elif 'COMPLETE' in event_type_name:
                            seq_completes += 1
                        elif 'ABORTED' in event_type_name:
                            seq_aborts += 1
                    except (json.JSONDecodeError, KeyError):
                        continue
                
                # Calculate exchange metrics
                avg_local_temp = round(sum(local_temps) / len(local_temps), 1) if local_temps else None
                avg_remote_temp = round(sum(remote_temps) / len(remote_temps), 1) if remote_temps else None
                avg_weight_g = round(sum(weights) / len(weights), 0) if weights else None
                
                exchange = {
                    'timestamp': press_time,
                    'button_press': True,
                    'avg_weight_g': avg_weight_g,
                    'avg_local_temp_f': avg_local_temp,
                    'avg_remote_temp_f': avg_remote_temp,
                    'seq_starts': seq_starts,
                    'seq_completes': seq_completes,
                    'seq_aborts': seq_aborts,
                    'efficiency_score': 100  # Simplified efficiency
                }
                
                exchanges_with_data.append(exchange)
            
            # Calculate delta gallons between consecutive basket exchanges
            for i in range(len(exchanges_with_data)):
                if i > 0:
                    prev_weight = exchanges_with_data[i-1].get('avg_weight_g', 0)
                    curr_weight = exchanges_with_data[i].get('avg_weight_g', 0)
                    if prev_weight and curr_weight:
                        # Delta weight in grams, converted to gallons
                        delta_weight_g = curr_weight - prev_weight
                        # Convert to gallons (assuming fuel density ~700 g/L, 1 gal = 3.78541 L)
                        delta_gallons = delta_weight_g / (700 * 3.78541)
                        exchanges_with_data[i]['delta_gallons'] = round(delta_gallons, 2)
                    else:
                        exchanges_with_data[i]['delta_gallons'] = None
                else:
                    exchanges_with_data[i]['delta_gallons'] = None  # First basket has no delta
            
            # Calculate aggregate metrics
            avg_efficiency = 100
            avg_delta_gallons = None
            
            if exchanges_with_data:
                efficiencies = [e['efficiency_score'] for e in exchanges_with_data]
                delta_gallons_all = [e['delta_gallons'] for e in exchanges_with_data if e.get('delta_gallons') is not None]
                
                if efficiencies:
                    avg_efficiency = sum(efficiencies) / len(efficiencies)
                if delta_gallons_all:
                    avg_delta_gallons = sum(delta_gallons_all) / len(delta_gallons_all)
            
            conn.close()
            
            return {
                'total_exchanges': exchanges_detected,
                'exchanges_last_hour': len([e for e in button_presses 
                    if (datetime.now() - datetime.fromisoformat(e['timestamp'])).total_seconds() < 3600]),
                'avg_efficiency_score': round(avg_efficiency, 1),
                'avg_delta_gallons': round(avg_delta_gallons, 2) if avg_delta_gallons else None,
                'cycles_completed': cycles_completed,
                'recent_exchanges': exchanges_with_data[-10:],  # Last 10 exchanges
                'detection_method': 'BUTTON_PRESS',
                'confidence': 0.9  # High confidence for direct button detection
            }
            
        except Exception as e:
            print(f"Error getting basket metrics: {e}")
            return {
                'total_exchanges': 0,
                'exchanges_last_hour': 0,
                'avg_efficiency_score': 0,
                'avg_delta_gallons': None,
                'cycles_completed': 0,
                'recent_exchanges': [],
                'detection_method': 'BUTTON_PRESS',
                'confidence': 0
            }
    
    def _calculate_basket_efficiency(self, local_temps, remote_temps):
        """Calculate efficiency score based on temperature stability"""
        score = 100.0
        
        # Local temperature stability bonus
        if local_temps:
            temp_range = max(local_temps) - min(local_temps)
            if temp_range < 5:  # Very stable
                score += 5
            elif temp_range > 15:  # Unstable
                score -= 10
        
        # Remote temperature stability bonus
        if remote_temps:
            temp_range = max(remote_temps) - min(remote_temps)
            if temp_range < 5:  # Very stable
                score += 5
            elif temp_range > 15:  # Unstable
                score -= 10
        
        return max(0, min(100, score))
    
    def get_sequence_events(self, hours: int = 24):
        """Get sequence events (starts, completes, aborts) from telemetry"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    received_timestamp,
                    payload_json
                FROM telemetry 
                WHERE message_type = 23 
                  AND message_type_name = 'SEQUENCE_EVENT'
                  AND payload_json != '{{}}'
                  AND payload_json NOT LIKE '%_legacy_empty%'
                  AND received_timestamp > datetime('now', '-{} hours')
                ORDER BY received_timestamp ASC
            """.format(hours))
            
            events = []
            stats = {'starts': 0, 'completes': 0, 'aborts': 0, 'pauses': 0}
            
            for row in cursor.fetchall():
                try:
                    timestamp = row[0]
                    payload = json.loads(row[1]) if row[1] else {}
                    event_type_name = payload.get('event_type_name', '')
                    
                    events.append({
                        'timestamp': timestamp,
                        'event_type': event_type_name,
                        'step_number': payload.get('step_number', 0),
                        'elapsed_time_ms': payload.get('elapsed_time_ms', 0)
                    })
                    
                    # Count event types
                    if 'STARTED' in event_type_name:
                        stats['starts'] += 1
                    elif 'COMPLETE' in event_type_name:
                        stats['completes'] += 1
                    elif 'ABORTED' in event_type_name:
                        stats['aborts'] += 1
                    elif 'PAUSED' in event_type_name:
                        stats['pauses'] += 1
                        
                except (json.JSONDecodeError, KeyError):
                    continue
            
            conn.close()
            
            return {
                'events': events[-20:],  # Last 20 events
                'stats': stats,
                'total_events': len(events)
            }
            
        except Exception as e:
            print(f"Error getting sequence events: {e}")
            return {'events': [], 'stats': {}, 'total_events': 0}
    
    def get_manual_moves(self, hours: int = 24):
        """Get manual relay operations from telemetry"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    received_timestamp,
                    payload_json
                FROM telemetry 
                WHERE message_type = 18 
                  AND message_type_name = 'RELAY_EVENT'
                  AND payload_json != '{{}}'
                  AND payload_json NOT LIKE '%_legacy_empty%'
                  AND received_timestamp > datetime('now', '-{} hours')
                ORDER BY received_timestamp ASC
            """.format(hours))
            
            manual_moves = []
            auto_moves = []
            
            for row in cursor.fetchall():
                try:
                    timestamp = row[0]
                    payload = json.loads(row[1]) if row[1] else {}
                    is_manual = payload.get('is_manual', False)
                    
                    move = {
                        'timestamp': timestamp,
                        'relay_number': payload.get('relay_number', 0),
                        'relay_name': payload.get('relay_name', ''),
                        'state': payload.get('state_name', ''),
                        'mode': payload.get('operation_mode', ''),
                        'success': payload.get('success', False)
                    }
                    
                    if is_manual:
                        manual_moves.append(move)
                    else:
                        auto_moves.append(move)
                        
                except (json.JSONDecodeError, KeyError):
                    continue
            
            conn.close()
            
            return {
                'manual_moves': manual_moves[-20:],  # Last 20 manual
                'auto_moves': auto_moves[-20:],  # Last 20 auto
                'manual_count': len(manual_moves),
                'auto_count': len(auto_moves)
            }
            
        except Exception as e:
            print(f"Error getting manual moves: {e}")
            return {'manual_moves': [], 'auto_moves': [], 'manual_count': 0, 'auto_count': 0}


# Initialize data provider
data_provider = DashboardDataProvider()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/basket')
def basket_metrics():
    """Basket metrics page with date range selection"""
    return render_template('basket_metrics.html')

@app.route('/api/recent')
def api_recent():
    """API endpoint for recent messages"""
    limit = request.args.get('limit', 50, type=int)
    messages = data_provider.get_recent_messages(limit)
    return jsonify(messages)

@app.route('/api/stats')
def api_stats():
    """API endpoint for message type statistics"""
    stats = data_provider.get_message_type_stats()
    return jsonify(stats)

@app.route('/api/activity')
def api_activity():
    """API endpoint for hourly activity data"""
    hours = request.args.get('hours', 24, type=int)
    activity = data_provider.get_hourly_activity(hours)
    return jsonify(activity)

@app.route('/api/overview')
def api_overview():
    """API endpoint for system overview"""
    overview = data_provider.get_system_overview()
    return jsonify(overview)

@app.route('/api/analytics')
def api_analytics():
    """API endpoint for comprehensive analytics data"""
    analytics = data_provider.get_analytics_data()
    return jsonify(analytics)

@app.route('/api/basket')
def api_basket():
    """API endpoint for basket exchange metrics"""
    hours = request.args.get('hours', 24, type=int)
    basket_metrics = data_provider.get_basket_metrics(hours)
    sequence_events = data_provider.get_sequence_events(hours)
    manual_moves = data_provider.get_manual_moves(hours)
    
    # Combine all data
    response = {
        **basket_metrics,
        'sequence_events': sequence_events,
        'manual_moves': manual_moves
    }
    
    return jsonify(response)

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('status', {'msg': 'Connected to LogSplitter Dashboard'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

def background_updates():
    """Background thread to send real-time updates"""
    last_message_count = 0
    
    while True:
        try:
            # Get current overview
            overview = data_provider.get_system_overview()
            
            # Check if new messages arrived
            current_count = overview.get('total_messages', 0)
            if current_count > last_message_count:
                # Get latest messages
                new_messages = data_provider.get_recent_messages(5)
                
                # Emit real-time update
                socketio.emit('new_messages', {
                    'messages': new_messages,
                    'overview': overview
                })
                
                last_message_count = current_count
            
            time.sleep(2)  # Update every 2 seconds
            
        except Exception as e:
            print(f"Background update error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    # Start background update thread
    update_thread = threading.Thread(target=background_updates, daemon=True)
    update_thread.start()
    
    print("LogSplitter Protobuf Dashboard")
    print(f"Starting web server on http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    print("Press Ctrl+C to stop")
    
    # Start Flask app with SocketIO
    socketio.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False, allow_unsafe_werkzeug=True)