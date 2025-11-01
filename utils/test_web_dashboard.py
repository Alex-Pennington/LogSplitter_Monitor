#!/usr/bin/env python3
"""
Comprehensive Unit Tests for LogSplitter Web Dashboard

Tests all data displays to ensure they show correct data from the database.
"""

import unittest
import json
import sqlite3
import os
from datetime import datetime, timedelta
from web_dashboard import DashboardDataProvider

class TestDashboardDataProvider(unittest.TestCase):
    """Test suite for DashboardDataProvider"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        # Use actual database
        cls.db_path = 'logsplitter_data.db'
        
        # Check if database exists
        if not os.path.exists(cls.db_path):
            raise FileNotFoundError(f"Database not found: {cls.db_path}")
        
        cls.provider = DashboardDataProvider(cls.db_path)
        print(f"\n✓ Connected to database: {cls.db_path}")
    
    def test_01_database_connection(self):
        """Test database connection"""
        conn = self.provider.get_connection()
        self.assertIsNotNone(conn, "Database connection should not be None")
        
        # Check tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn('telemetry', tables, "telemetry table should exist")
        self.assertIn('monitor_data', tables, "monitor_data table should exist")
        
        conn.close()
        print(f"  ✓ Tables found: {', '.join(tables)}")
    
    def test_02_recent_messages(self):
        """Test recent messages retrieval"""
        messages = self.provider.get_recent_messages(limit=10)
        
        self.assertIsInstance(messages, list, "Should return a list")
        
        if messages:
            # Validate message structure
            msg = messages[0]
            self.assertIn('received_timestamp', msg)
            self.assertIn('controller_timestamp', msg)
            self.assertIn('message_type', msg)
            self.assertIn('message_type_name', msg)
            self.assertIn('sequence_id', msg)
            self.assertIn('payload', msg)
            self.assertIn('raw_size', msg)
            
            print(f"  ✓ Retrieved {len(messages)} messages")
            print(f"  ✓ Latest message: {msg['message_type_name']} at {msg['received_timestamp']}")
        else:
            print("  ⚠ No messages in database")
    
    def test_03_message_type_stats(self):
        """Test message type statistics"""
        stats = self.provider.get_message_type_stats()
        
        self.assertIsInstance(stats, list, "Should return a list")
        
        if stats:
            # Validate stats structure
            stat = stats[0]
            self.assertIn('type_id', stat)
            self.assertIn('type_name', stat)
            self.assertIn('count', stat)
            self.assertIn('avg_size', stat)
            self.assertIn('first_seen', stat)
            self.assertIn('last_seen', stat)
            
            print(f"  ✓ Message types found: {len(stats)}")
            for s in stats:
                print(f"    - {s['type_name']} ({s['type_id']}): {s['count']} messages")
        else:
            print("  ⚠ No message stats available")
    
    def test_04_system_overview(self):
        """Test system overview statistics"""
        overview = self.provider.get_system_overview()
        
        self.assertIsInstance(overview, dict, "Should return a dictionary")
        self.assertIn('total_messages', overview)
        self.assertIn('messages_last_hour', overview)
        self.assertIn('database_size_mb', overview)
        self.assertIn('unique_types', overview)
        self.assertIn('latest_message', overview)
        self.assertIn('latest_type', overview)
        
        print(f"  ✓ Total messages: {overview['total_messages']}")
        print(f"  ✓ Messages last hour: {overview['messages_last_hour']}")
        print(f"  ✓ Database size: {overview['database_size_mb']} MB")
        print(f"  ✓ Unique message types: {overview['unique_types']}")
        print(f"  ✓ Latest message: {overview['latest_type']} at {overview['latest_message']}")
        
        # Validate data integrity
        self.assertGreaterEqual(overview['total_messages'], 0)
        self.assertGreaterEqual(overview['messages_last_hour'], 0)
        self.assertGreater(overview['database_size_mb'], 0)
        self.assertGreaterEqual(overview['unique_types'], 0)
    
    def test_05_cycle_analysis(self):
        """Test cycle analysis from analytics data"""
        analytics = self.provider.get_analytics_data()
        
        self.assertIsInstance(analytics, dict, "Should return a dictionary")
        self.assertIn('cycle_analysis', analytics)
        
        cycle = analytics['cycle_analysis']
        self.assertIn('cycles_completed', cycle)
        self.assertIn('short_strokes', cycle)
        self.assertIn('success_rate', cycle)
        self.assertIn('avg_cycle_time_sec', cycle)
        self.assertIn('cycle_times', cycle)
        self.assertIn('total_cycles', cycle)
        
        print(f"  ✓ Cycles completed: {cycle['cycles_completed']}")
        print(f"  ✓ Short strokes: {cycle['short_strokes']}")
        print(f"  ✓ Success rate: {cycle['success_rate']}%")
        print(f"  ✓ Avg cycle time: {cycle['avg_cycle_time_sec']}s")
        print(f"  ✓ Total cycles: {cycle['total_cycles']}")
        
        # Validate data consistency
        self.assertGreaterEqual(cycle['cycles_completed'], 0)
        self.assertGreaterEqual(cycle['short_strokes'], 0)
        self.assertEqual(cycle['total_cycles'], cycle['cycles_completed'] + cycle['short_strokes'])
        self.assertGreaterEqual(cycle['success_rate'], 0)
        self.assertLessEqual(cycle['success_rate'], 100)
    
    def test_06_pressure_analysis(self):
        """Test pressure analysis from analytics data"""
        analytics = self.provider.get_analytics_data()
        
        self.assertIn('pressure_analysis', analytics)
        
        pressure = analytics['pressure_analysis']
        self.assertIn('max_pressure_psi', pressure)
        self.assertIn('avg_pressure_psi', pressure)
        self.assertIn('pressure_spikes', pressure)
        self.assertIn('pressure_faults', pressure)
        self.assertIn('pressure_efficiency', pressure)
        self.assertIn('recent_pressures', pressure)
        
        print(f"  ✓ Max pressure: {pressure['max_pressure_psi']} PSI")
        print(f"  ✓ Avg pressure: {pressure['avg_pressure_psi']} PSI")
        print(f"  ✓ Pressure spikes: {pressure['pressure_spikes']}")
        print(f"  ✓ Pressure faults: {pressure['pressure_faults']}")
        print(f"  ✓ Pressure efficiency: {pressure['pressure_efficiency']}%")
        
        # Validate data ranges
        if pressure['max_pressure_psi'] > 0:
            self.assertGreaterEqual(pressure['max_pressure_psi'], pressure['avg_pressure_psi'])
            self.assertLessEqual(pressure['max_pressure_psi'], 5000)  # System max
        
        self.assertGreaterEqual(pressure['pressure_spikes'], 0)
        self.assertGreaterEqual(pressure['pressure_faults'], 0)
    
    def test_07_efficiency_metrics(self):
        """Test operational efficiency metrics"""
        analytics = self.provider.get_analytics_data()
        
        self.assertIn('efficiency_metrics', analytics)
        
        efficiency = analytics['efficiency_metrics']
        self.assertIn('extend_operations', efficiency)
        self.assertIn('retract_operations', efficiency)
        self.assertIn('manual_operations', efficiency)
        self.assertIn('auto_operations', efficiency)
        self.assertIn('automation_ratio', efficiency)
        self.assertIn('uptime_minutes', efficiency)
        self.assertIn('system_load_percent', efficiency)
        self.assertIn('total_operations', efficiency)
        
        print(f"  ✓ Extend operations: {efficiency['extend_operations']}")
        print(f"  ✓ Retract operations: {efficiency['retract_operations']}")
        print(f"  ✓ Manual operations: {efficiency['manual_operations']}")
        print(f"  ✓ Auto operations: {efficiency['auto_operations']}")
        print(f"  ✓ Automation ratio: {efficiency['automation_ratio']}%")
        print(f"  ✓ Uptime: {efficiency['uptime_minutes']} minutes")
        print(f"  ✓ System load: {efficiency['system_load_percent']}%")
        
        # Validate data consistency
        self.assertGreaterEqual(efficiency['extend_operations'], 0)
        self.assertGreaterEqual(efficiency['retract_operations'], 0)
        self.assertGreaterEqual(efficiency['manual_operations'], 0)
        self.assertGreaterEqual(efficiency['auto_operations'], 0)
        self.assertEqual(efficiency['total_operations'], 
                        efficiency['manual_operations'] + efficiency['auto_operations'])
    
    def test_08_safety_analysis(self):
        """Test safety system analysis"""
        analytics = self.provider.get_analytics_data()
        
        self.assertIn('safety_analysis', analytics)
        
        safety = analytics['safety_analysis']
        self.assertIn('safety_activations', safety)
        self.assertIn('emergency_stops', safety)
        self.assertIn('limit_triggers', safety)
        self.assertIn('pressure_safeties', safety)
        self.assertIn('total_safety_events', safety)
        self.assertIn('safety_score', safety)
        
        print(f"  ✓ Safety activations: {safety['safety_activations']}")
        print(f"  ✓ Emergency stops: {safety['emergency_stops']}")
        print(f"  ✓ Limit triggers: {safety['limit_triggers']}")
        print(f"  ✓ Pressure safeties: {safety['pressure_safeties']}")
        print(f"  ✓ Total safety events: {safety['total_safety_events']}")
        print(f"  ✓ Safety score: {safety['safety_score']}%")
        
        # Validate data consistency
        self.assertEqual(safety['total_safety_events'],
                        safety['safety_activations'] + safety['emergency_stops'] + 
                        safety['limit_triggers'] + safety['pressure_safeties'])
        self.assertGreaterEqual(safety['safety_score'], 0)
        self.assertLessEqual(safety['safety_score'], 100)
    
    def test_09_system_health(self):
        """Test system health metrics"""
        analytics = self.provider.get_analytics_data()
        
        self.assertIn('system_health', analytics)
        
        health = analytics['system_health']
        self.assertIn('avg_free_memory', health)
        self.assertIn('avg_loop_frequency', health)
        self.assertIn('avg_active_errors', health)
        self.assertIn('memory_health_score', health)
        self.assertIn('performance_score', health)
        self.assertIn('error_score', health)
        self.assertIn('overall_health_score', health)
        
        print(f"  ✓ Avg free memory: {health['avg_free_memory']} bytes")
        print(f"  ✓ Avg loop frequency: {health['avg_loop_frequency']} Hz")
        print(f"  ✓ Avg active errors: {health['avg_active_errors']}")
        print(f"  ✓ Memory health: {health['memory_health_score']}%")
        print(f"  ✓ Performance: {health['performance_score']}%")
        print(f"  ✓ Error score: {health['error_score']}%")
        print(f"  ✓ Overall health: {health['overall_health_score']}%")
        
        # Validate health scores are percentages
        for score_key in ['memory_health_score', 'performance_score', 'error_score', 'overall_health_score']:
            self.assertGreaterEqual(health[score_key], 0)
            self.assertLessEqual(health[score_key], 100)
    
    def test_10_operational_patterns(self):
        """Test operational pattern analysis"""
        analytics = self.provider.get_analytics_data()
        
        self.assertIn('operational_patterns', analytics)
        
        patterns = analytics['operational_patterns']
        self.assertIn('hourly_activity', patterns)
        self.assertIn('peak_hour', patterns)
        self.assertIn('peak_activity', patterns)
        self.assertIn('daily_patterns', patterns)
        
        print(f"  ✓ Peak hour: {patterns['peak_hour']}:00")
        print(f"  ✓ Peak activity: {patterns['peak_activity']} messages")
        print(f"  ✓ Daily patterns: {len(patterns['daily_patterns'])} days")
        
        # Validate peak hour is valid
        self.assertGreaterEqual(patterns['peak_hour'], 0)
        self.assertLessEqual(patterns['peak_hour'], 23)
        self.assertGreaterEqual(patterns['peak_activity'], 0)
    
    def test_11_basket_metrics(self):
        """Test basket exchange metrics"""
        basket = self.provider.get_basket_metrics(hours=24)
        
        self.assertIsInstance(basket, dict, "Should return a dictionary")
        self.assertIn('total_exchanges', basket)
        self.assertIn('exchanges_last_hour', basket)
        self.assertIn('avg_efficiency_score', basket)
        self.assertIn('avg_temperature_f', basket)
        self.assertIn('avg_weight_g', basket)
        self.assertIn('recent_exchanges', basket)
        self.assertIn('detection_method', basket)
        self.assertIn('confidence', basket)
        
        print(f"  ✓ Total exchanges (24h): {basket['total_exchanges']}")
        print(f"  ✓ Exchanges last hour: {basket['exchanges_last_hour']}")
        print(f"  ✓ Avg efficiency: {basket['avg_efficiency_score']}%")
        
        if basket['avg_temperature_f'] is not None:
            print(f"  ✓ Avg temperature: {basket['avg_temperature_f']}°F")
        else:
            print(f"  ⚠ No temperature data available")
        
        if basket['avg_weight_g'] is not None:
            print(f"  ✓ Avg weight: {basket['avg_weight_g']} g")
        else:
            print(f"  ⚠ No weight data available")
        
        print(f"  ✓ Detection method: {basket['detection_method']}")
        print(f"  ✓ Confidence: {basket['confidence'] * 100}%")
        print(f"  ✓ Recent exchanges: {len(basket['recent_exchanges'])}")
        
        # Validate data ranges
        self.assertGreaterEqual(basket['total_exchanges'], 0)
        self.assertGreaterEqual(basket['exchanges_last_hour'], 0)
        self.assertLessEqual(basket['exchanges_last_hour'], basket['total_exchanges'])
        self.assertGreaterEqual(basket['avg_efficiency_score'], 0)
        self.assertLessEqual(basket['avg_efficiency_score'], 100)
        self.assertGreaterEqual(basket['confidence'], 0)
        self.assertLessEqual(basket['confidence'], 1.0)
        
        # Validate temperature range if present
        if basket['avg_temperature_f'] is not None:
            self.assertGreaterEqual(basket['avg_temperature_f'], 50)
            self.assertLessEqual(basket['avg_temperature_f'], 200)
        
        # Validate recent exchanges structure
        if basket['recent_exchanges']:
            exchange = basket['recent_exchanges'][0]
            self.assertIn('timestamp', exchange)
            self.assertIn('button_press', exchange)
            self.assertIn('efficiency_score', exchange)
            print(f"  ✓ First exchange: {exchange['timestamp']}")
    
    def test_12_hourly_activity(self):
        """Test hourly activity data"""
        activity = self.provider.get_hourly_activity(hours=24)
        
        self.assertIsInstance(activity, dict, "Should return a dictionary")
        
        if activity:
            print(f"  ✓ Activity hours tracked: {len(activity)}")
            
            # Check for data structure
            first_hour = list(activity.keys())[0]
            hour_data = activity[first_hour]
            self.assertIsInstance(hour_data, dict, "Hour data should be a dictionary")
            
            print(f"  ✓ Sample hour: {first_hour}")
            print(f"    Message types: {list(hour_data.keys())}")
        else:
            print("  ⚠ No hourly activity data available")
    
    def test_13_data_consistency(self):
        """Test data consistency across different queries"""
        # Get data from multiple sources
        overview = self.provider.get_system_overview()
        stats = self.provider.get_message_type_stats()
        
        # Total messages from stats should match overview
        if stats:
            stats_total = sum(stat['count'] for stat in stats)
            self.assertEqual(stats_total, overview['total_messages'],
                           "Total messages should match between overview and stats")
            print(f"  ✓ Data consistency verified: {stats_total} messages")
        
        # Unique types should match
        if stats:
            self.assertEqual(len(stats), overview['unique_types'],
                           "Unique message types should match")
            print(f"  ✓ Unique types consistency verified: {len(stats)} types")
    
    def test_14_monitor_data_integration(self):
        """Test monitor data (temperature, weight) integration"""
        conn = self.provider.get_connection()
        cursor = conn.cursor()
        
        # Check monitor data table
        cursor.execute("""
            SELECT topic, COUNT(*) as count, AVG(CAST(value AS REAL)) as avg_value
            FROM monitor_data
            GROUP BY topic
        """)
        
        monitor_topics = []
        for row in cursor.fetchall():
            topic = row[0]
            count = row[1]
            avg_value = row[2] if row[2] is not None else 0.0
            monitor_topics.append(topic)
            print(f"  ✓ {topic}: {count} readings, avg={avg_value:.2f}")
        
        conn.close()
        
        # Verify expected topics
        if monitor_topics:
            self.assertTrue(any('temperature' in t.lower() for t in monitor_topics),
                          "Should have temperature data")
        else:
            print("  ⚠ No monitor data available")
    
    def test_15_database_performance(self):
        """Test database query performance"""
        import time
        
        # Test query execution times
        start = time.time()
        overview = self.provider.get_system_overview()
        overview_time = time.time() - start
        
        start = time.time()
        analytics = self.provider.get_analytics_data()
        analytics_time = time.time() - start
        
        start = time.time()
        basket = self.provider.get_basket_metrics()
        basket_time = time.time() - start
        
        print(f"  ✓ Overview query: {overview_time:.3f}s")
        print(f"  ✓ Analytics query: {analytics_time:.3f}s")
        print(f"  ✓ Basket metrics query: {basket_time:.3f}s")
        
        # All queries should complete within reasonable time
        self.assertLess(overview_time, 1.0, "Overview query should be fast")
        self.assertLess(analytics_time, 5.0, "Analytics query should complete in <5s")
        self.assertLess(basket_time, 5.0, "Basket metrics query should complete in <5s")

class TestDataValidation(unittest.TestCase):
    """Test data validation and error handling"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.db_path = 'logsplitter_data.db'
        cls.provider = DashboardDataProvider(cls.db_path)
    
    def test_16_empty_result_handling(self):
        """Test handling of empty query results"""
        # Test with extreme time range that should return no data
        activity = self.provider.get_hourly_activity(hours=0)
        self.assertIsInstance(activity, dict, "Should return empty dict, not None")
        print("  ✓ Empty result handling: OK")
    
    def test_17_invalid_payload_handling(self):
        """Test handling of invalid JSON payloads"""
        # This tests the error handling in data processing
        messages = self.provider.get_recent_messages(limit=100)
        
        # Check that all messages have valid payload structure
        for msg in messages:
            self.assertIsInstance(msg['payload'], dict, 
                                "Payload should be a dictionary even if original was invalid")
        
        print(f"  ✓ Payload validation: {len(messages)} messages checked")
    
    def test_18_zero_division_handling(self):
        """Test handling of division by zero in calculations"""
        analytics = self.provider.get_analytics_data()
        
        # Check that all percentage calculations are valid
        cycle = analytics['cycle_analysis']
        
        # Success rate calculation should not crash with zero total
        self.assertIsInstance(cycle['success_rate'], (int, float))
        self.assertGreaterEqual(cycle['success_rate'], 0)
        self.assertLessEqual(cycle['success_rate'], 100)
        
        print("  ✓ Zero division handling: OK")

def run_tests():
    """Run all tests with detailed output"""
    print("=" * 70)
    print("LogSplitter Web Dashboard - Comprehensive Unit Tests")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDashboardDataProvider))
    suite.addTests(loader.loadTestsFromTestCase(TestDataValidation))
    
    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print()
    
    if result.wasSuccessful():
        print("✓ All tests passed! Dashboard data displays are verified.")
    else:
        print("✗ Some tests failed. Review failures above.")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
