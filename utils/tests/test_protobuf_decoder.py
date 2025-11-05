"""
Unit tests for LogSplitter Protobuf Decoder

Tests verify that binary protobuf messages from the controller are correctly
decoded according to the structures defined in telemetry_manager.h

Run tests with: pytest -v tests/test_protobuf_decoder.py
"""
import pytest
import struct


class TestMessageHeader:
    """Test basic message header parsing"""
    
    def test_minimum_message_size(self, decoder):
        """Messages must be at least 7 bytes (size + type + seq + timestamp)"""
        # Message too short
        too_short = bytes([0x05, 0x10, 0x01])
        result = decoder.decode_message(too_short)
        assert result is None
        assert decoder.decode_errors == 1
    
    def test_header_extraction(self, decoder, sample_messages):
        """Header fields should be correctly extracted"""
        result = decoder.decode_message(sample_messages['pressure'])
        assert result is not None
        assert result['size'] == 0x0F
        assert result['type'] == 0x13
        assert result['type_name'] == 'PRESSURE'
        assert result['sequence'] == 4
        assert result['timestamp'] == 12345678


class TestDigitalInput:
    """Test DIGITAL_INPUT (0x10) message decoding"""
    
    def test_digital_input_decode(self, decoder, sample_messages, expected_results):
        """Should decode 3-byte digital input payload correctly"""
        result = decoder.decode_message(sample_messages['digital_input_3byte'])
        expected = expected_results['digital_input_3byte']
        
        assert result is not None
        assert result['type'] == 0x10
        assert result['type_name'] == 'DIGITAL_INPUT'
        
        # Check payload fields
        payload = result['payload']
        assert payload is not None
        assert payload['pin'] == expected['payload']['pin']
        assert payload['state'] == expected['payload']['state']
        assert payload['state_name'] == expected['payload']['state_name']
        assert payload['is_debounced'] == expected['payload']['is_debounced']
        assert payload['input_type'] == expected['payload']['input_type']
        assert payload['input_type_name'] == expected['payload']['input_type_name']
    
    def test_digital_input_all_pins(self, decoder):
        """Should handle all input pin types"""
        input_types = [
            (2, 1, 'INPUT_MANUAL_EXTEND'),
            (3, 2, 'INPUT_MANUAL_RETRACT'),
            (4, 3, 'INPUT_SAFETY_CLEAR'),
            (5, 4, 'INPUT_SEQUENCE_START'),
            (6, 5, 'INPUT_LIMIT_EXTEND'),
            (7, 6, 'INPUT_LIMIT_RETRACT'),
            (8, 7, 'INPUT_SPLITTER_OPERATOR'),
            (12, 8, 'INPUT_EMERGENCY_STOP')
        ]
        
        for pin, input_type, type_name in input_types:
            # Construct message with specific input type
            flags = (input_type << 2) | 0x02  # Set input_type and debounced flag
            message = bytes([
                0x0A, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00,  # Header
                pin, flags, 0x0A  # Payload: pin, flags, debounce
            ])
            result = decoder.decode_message(message)
            assert result['payload']['pin'] == pin
            assert result['payload']['input_type'] == input_type
            assert result['payload']['input_type_name'] == type_name


class TestDigitalOutput:
    """Test DIGITAL_OUTPUT (0x11) message decoding"""
    
    def test_digital_output_decode(self, decoder, sample_messages, expected_results):
        """Should decode 3-byte digital output payload correctly"""
        result = decoder.decode_message(sample_messages['digital_output'])
        expected = expected_results['digital_output']
        
        assert result is not None
        assert result['type'] == 0x11
        
        payload = result['payload']
        assert payload is not None
        assert payload['pin'] == expected['payload']['pin']
        assert payload['state'] == expected['payload']['state']
        assert payload['output_type'] == expected['payload']['output_type']
        assert payload['output_type_name'] == expected['payload']['output_type_name']


class TestRelayEvent:
    """Test RELAY_EVENT (0x12) message decoding"""
    
    def test_relay_event_decode(self, decoder, sample_messages, expected_results):
        """Should decode 3-byte relay event payload correctly"""
        result = decoder.decode_message(sample_messages['relay_event'])
        expected = expected_results['relay_event']
        
        assert result is not None
        assert result['type'] == 0x12
        
        payload = result['payload']
        assert payload is not None
        assert payload['relay_number'] == expected['payload']['relay_number']
        assert payload['state'] == expected['payload']['state']
        assert payload['is_manual'] == expected['payload']['is_manual']
        assert payload['success'] == expected['payload']['success']
        assert payload['relay_type'] == expected['payload']['relay_type']
        assert payload['relay_type_name'] == expected['payload']['relay_type_name']
    
    def test_relay_event_all_relays(self, decoder):
        """Should handle all relay types"""
        relay_types = [
            (1, 1, 'RELAY_HYDRAULIC_EXTEND'),
            (2, 2, 'RELAY_HYDRAULIC_RETRACT'),
            (7, 7, 'RELAY_OPERATOR_BUZZER'),
            (8, 8, 'RELAY_ENGINE_STOP'),
            (9, 9, 'RELAY_POWER_CONTROL')
        ]
        
        for relay_num, relay_type, type_name in relay_types:
            # Construct message with specific relay type
            flags = (relay_type << 3) | 0x05  # Set relay_type, state=1, success=1
            message = bytes([
                0x0A, 0x12, 0x00, 0x00, 0x00, 0x00, 0x00,  # Header
                relay_num, flags, 0x00  # Payload
            ])
            result = decoder.decode_message(message)
            assert result['payload']['relay_number'] == relay_num
            assert result['payload']['relay_type'] == relay_type
            assert result['payload']['relay_type_name'] == type_name


class TestPressureReading:
    """Test PRESSURE (0x13) message decoding"""
    
    def test_pressure_decode(self, decoder, sample_messages, expected_results):
        """Should decode 8-byte pressure payload correctly"""
        result = decoder.decode_message(sample_messages['pressure'])
        expected = expected_results['pressure']
        
        assert result is not None
        assert result['type'] == 0x13
        
        payload = result['payload']
        assert payload is not None
        assert payload['sensor_pin'] == expected['payload']['sensor_pin']
        assert abs(payload['pressure_psi'] - expected['payload']['pressure_psi']) < 0.01
        assert payload['raw_value'] == expected['payload']['raw_value']
        assert payload['is_fault'] == expected['payload']['is_fault']
    
    def test_pressure_range_validation(self, decoder):
        """Should handle pressure values across valid range"""
        test_values = [
            (0.0, False),      # Minimum
            (2500.0, False),   # Mid-range
            (5000.0, False),   # Maximum
            (5001.0, True),    # Over-pressure fault
        ]
        
        for pressure, should_fault in test_values:
            # Construct pressure message
            pressure_bytes = struct.pack('<f', pressure)
            flags = 0x01 if should_fault else 0x00
            message = bytes([
                0x0F, 0x13, 0x00, 0x00, 0x00, 0x00, 0x00,  # Header
                0x00, flags, 0x00, 0x03  # Pin, flags, raw_value (2 bytes)
            ]) + pressure_bytes
            
            result = decoder.decode_message(message)
            assert result['payload']['pressure_psi'] == pytest.approx(pressure, abs=0.01)
            assert result['payload']['is_fault'] == should_fault


class TestSystemStatus:
    """Test SYSTEM_STATUS (0x16) message decoding - CRITICAL FIX"""
    
    def test_system_status_decode(self, decoder, sample_messages, expected_results):
        """Should decode 12-byte system status payload correctly"""
        result = decoder.decode_message(sample_messages['system_status'])
        expected = expected_results['system_status']
        
        assert result is not None, "System status decode should not return None"
        assert result['type'] == 0x16
        
        payload = result['payload']
        assert payload is not None, "System status payload should not be None"
        
        # Critical fields
        assert payload['uptime_ms'] == expected['payload']['uptime_ms']
        assert payload['loop_frequency_hz'] == expected['payload']['loop_frequency_hz']
        assert payload['free_memory_bytes'] == expected['payload']['free_memory_bytes']
        assert payload['active_error_count'] == expected['payload']['active_error_count']
        
        # Flag fields
        assert payload['safety_active'] == expected['payload']['safety_active']
        assert payload['estop_active'] == expected['payload']['estop_active']
        assert payload['sequence_state'] == expected['payload']['sequence_state']
        assert payload['sequence_state_name'] == expected['payload']['sequence_state_name']
        assert payload['mill_lamp_pattern'] == expected['payload']['mill_lamp_pattern']
        assert payload['mill_lamp_pattern_name'] == expected['payload']['mill_lamp_pattern_name']
    
    def test_system_status_flags(self, decoder):
        """Should correctly parse all flag combinations"""
        flag_tests = [
            (0x00, False, False, 0, 0),  # All flags off
            (0x01, True, False, 0, 0),   # Safety active
            (0x02, False, True, 0, 0),   # E-stop active
            (0x03, True, True, 0, 0),    # Both active
            (0x05, True, False, 1, 0),   # Safety + sequence state 1
            (0xC1, True, False, 0, 3),   # Safety + mill lamp pattern 3
        ]
        
        for flags, safety, estop, seq_state, lamp_pattern in flag_tests:
            message = bytes([
                0x13, 0x16, 0x00, 0x00, 0x00, 0x00, 0x00,  # Header
                0x00, 0x00, 0x00, 0x00,  # Uptime: 0
                0x64, 0x00,  # Loop freq: 100 Hz
                0x00, 0x10,  # Free mem: 4096 bytes
                0x00,  # Error count: 0
                flags,  # Flags byte
                0x00, 0x00  # Reserved
            ])
            result = decoder.decode_message(message)
            assert result['payload']['safety_active'] == safety
            assert result['payload']['estop_active'] == estop
            assert result['payload']['sequence_state'] == seq_state
            assert result['payload']['mill_lamp_pattern'] == lamp_pattern


class TestSequenceEvent:
    """Test SEQUENCE_EVENT (0x17) message decoding"""
    
    def test_sequence_event_decode(self, decoder, sample_messages, expected_results):
        """Should decode 4-byte sequence event payload correctly"""
        result = decoder.decode_message(sample_messages['sequence_event'])
        expected = expected_results['sequence_event']
        
        assert result is not None
        assert result['type'] == 0x17
        
        payload = result['payload']
        assert payload is not None
        assert payload['event_type'] == expected['payload']['event_type']
        assert payload['step_number'] == expected['payload']['step_number']
        assert payload['elapsed_time_ms'] == expected['payload']['elapsed_time_ms']


class TestSafetyEvent:
    """Test SAFETY_EVENT (0x15) message decoding"""
    
    def test_safety_event_decode(self, decoder, sample_messages, expected_results):
        """Should decode 3-byte safety event payload correctly"""
        result = decoder.decode_message(sample_messages['safety_event'])
        expected = expected_results['safety_event']
        
        assert result is not None
        assert result['type'] == 0x15
        
        payload = result['payload']
        assert payload is not None
        assert payload['event_type'] == expected['payload']['event_type']
        assert payload['is_active'] == expected['payload']['is_active']


class TestSystemError:
    """Test SYSTEM_ERROR (0x14) message decoding"""
    
    def test_system_error_decode(self, decoder, sample_messages, expected_results):
        """Should decode variable-length system error payload correctly"""
        result = decoder.decode_message(sample_messages['system_error'])
        expected = expected_results['system_error']
        
        assert result is not None
        assert result['type'] == 0x14
        
        payload = result['payload']
        assert payload is not None
        assert payload['error_code'] == expected['payload']['error_code']
        assert payload['acknowledged'] == expected['payload']['acknowledged']
        assert payload['active'] == expected['payload']['active']
        assert payload['severity'] == expected['payload']['severity']
        assert payload['severity_name'] == expected['payload']['severity_name']
        assert payload['description'] == expected['payload']['description']
    
    def test_system_error_severities(self, decoder):
        """Should correctly parse all error severity levels"""
        severities = [
            (0x00, 'INFO'),
            (0x04, 'WARNING'),
            (0x08, 'ERROR'),
            (0x0C, 'CRITICAL')
        ]
        
        for flags, severity_name in severities:
            message = bytes([
                0x0E, 0x14, 0x00, 0x00, 0x00, 0x00, 0x00,  # Header
                0x01,  # Error code
                flags,  # Flags with severity
                0x04,  # Description length: 4
                0x54, 0x65, 0x73, 0x74  # "Test"
            ])
            result = decoder.decode_message(message)
            assert result['payload']['severity_name'] == severity_name


class TestSequenceTracking:
    """Test sequence number gap detection"""
    
    def test_sequence_gap_detection(self, decoder):
        """Should detect sequence number gaps"""
        # Send first message
        msg1 = bytes([0x0A, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00, 0x0A])
        result1 = decoder.decode_message(msg1)
        assert result1 is not None
        
        # Send message with gap (seq 5 instead of 2)
        msg2 = bytes([0x0A, 0x10, 0x05, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00, 0x0A])
        result2 = decoder.decode_message(msg2)
        assert result2 is not None
        
        # Decoder should have tracked the gap (check console output)
        assert decoder.last_sequence[0x10] == 5


class TestStatistics:
    """Test decoder statistics tracking"""
    
    def test_message_counting(self, decoder, sample_messages):
        """Should track message statistics"""
        assert decoder.messages_received == 0
        assert decoder.messages_decoded == 0
        
        # Decode valid message
        result = decoder.decode_message(sample_messages['pressure'])
        assert result is not None
        assert decoder.messages_received == 1
        assert decoder.messages_decoded == 1
        
        # Decode invalid message
        invalid = bytes([0x03, 0xFF, 0x00])
        result = decoder.decode_message(invalid)
        assert result is None
        assert decoder.messages_received == 2
        assert decoder.messages_decoded == 1  # Should not increment
        assert decoder.decode_errors == 1
