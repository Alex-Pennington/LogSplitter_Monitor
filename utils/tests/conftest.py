"""
pytest configuration and fixtures for protobuf decoder tests
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path so we can import mqtt_protobuf_decoder
sys.path.insert(0, str(Path(__file__).parent.parent))

from mqtt_protobuf_decoder import LogSplitterProtobufDecoder


@pytest.fixture
def decoder():
    """Create a fresh decoder instance for each test"""
    return LogSplitterProtobufDecoder()


@pytest.fixture
def sample_messages():
    """
    Binary message samples matching telemetry_manager.h structures
    
    Each message format: [SIZE][TYPE][SEQ][TIMESTAMP_4BYTES][PAYLOAD]
    All integers are little-endian
    """
    return {
        # DIGITAL_INPUT (0x10) - 3 byte payload: pin + flags + debounce_low
        'digital_input_3byte': bytes([
            0x0A,       # Size: 10 bytes total
            0x10,       # Type: DIGITAL_INPUT
            0x01,       # Sequence: 1
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0x06,       # Pin: 6 (LIMIT_EXTEND)
            0x16,       # Flags: state=0, debounced=1, input_type=5 (LIMIT_EXTEND)
            0x0A        # Debounce: 10 ms (low byte only)
        ]),
        
        # DIGITAL_OUTPUT (0x11) - 3 byte payload: pin + flags + reserved
        'digital_output': bytes([
            0x0A,       # Size: 10 bytes total
            0x11,       # Type: DIGITAL_OUTPUT
            0x02,       # Sequence: 2
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0x09,       # Pin: 9 (MILL_LAMP)
            0x03,       # Flags: state=1, output_type=1 (bits 1-3), pattern=0 (bits 4-7)
            0x00        # Reserved
        ]),
        
        # RELAY_EVENT (0x12) - 3 byte payload: relay + flags + reserved
        'relay_event': bytes([
            0x0A,       # Size: 10 bytes total
            0x12,       # Type: RELAY_EVENT
            0x03,       # Sequence: 3
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0x01,       # Relay: 1 (R1)
            0x0D,       # Flags: state=1, manual=0, success=1, relay_type=1 (HYDRAULIC_EXTEND)
            0x00        # Reserved
        ]),
        
        # PRESSURE (0x13) - 8 byte payload: sensor_pin + flags + raw_value + pressure_float
        'pressure': bytes([
            0x0F,       # Size: 15 bytes total
            0x13,       # Type: PRESSURE
            0x04,       # Sequence: 4
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0x00,       # Sensor pin: A0
            0x00,       # Flags: no fault, pressure_type=0
            0x00, 0x03, # Raw value: 768 (0x0300 little-endian)
            0x00, 0x00, 0x7A, 0x44  # Pressure: 1000.0 PSI (float, little-endian)
        ]),
        
        # SYSTEM_STATUS (0x16) - 12 byte payload
        'system_status': bytes([
            0x13,       # Size: 19 bytes total
            0x16,       # Type: SYSTEM_STATUS
            0x05,       # Sequence: 5
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0xCE, 0x29, 0x00, 0x00, # Uptime: 10702 ms (0x29CE little-endian)
            0x64, 0x00, # Loop frequency: 100 Hz
            0x15, 0x38, # Free memory: 14357 bytes (0x3815 little-endian)
            0x02,       # Active error count: 2
            0x01,       # Flags: safety_active=1, estop_active=0, seq_state=0, lamp=0
            0x00, 0x00  # Reserved
        ]),
        
        # SEQUENCE_EVENT (0x17) - 4 byte payload: event_type + step + elapsed_time
        'sequence_event': bytes([
            0x0B,       # Size: 11 bytes total
            0x17,       # Type: SEQUENCE_EVENT
            0x06,       # Sequence: 6
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0x01,       # Event type: 1 (sequence start)
            0x00,       # Step: 0
            0x00, 0x00  # Elapsed time: 0 ms
        ]),
        
        # SAFETY_EVENT (0x15) - 3 byte payload: event_type + flags + reserved
        'safety_event': bytes([
            0x0A,       # Size: 10 bytes total
            0x15,       # Type: SAFETY_EVENT
            0x07,       # Sequence: 7
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0x01,       # Event type: 1 (estop activated)
            0x01,       # Flags: is_active=1
            0x00        # Reserved
        ]),
        
        # SYSTEM_ERROR (0x14) - Variable payload: error_code + flags + desc_length + description
        'system_error': bytes([
            0x18,       # Size: 24 bytes total (7 header + 3 fixed + 14 description)
            0x14,       # Type: SYSTEM_ERROR
            0x08,       # Sequence: 8
            0x4E, 0x61, 0xBC, 0x00,  # Timestamp: 12345678 ms
            0x10,       # Error code: 0x10 (CONFIG_INVALID)
            0x09,       # Flags: acked=1, active=0, severity=2 (ERROR)
            0x0E,       # Description length: 14 bytes
            0x43, 0x6F, 0x6E, 0x66, 0x69, 0x67, 0x20,  # "Config "
            0x69, 0x6E, 0x76, 0x61, 0x6C, 0x69, 0x64  # "invalid"
        ])
    }


@pytest.fixture
def expected_results():
    """Expected decoded results for sample messages"""
    return {
        'digital_input_3byte': {
            'size': 0x0A,
            'type': 0x10,
            'type_name': 'DIGITAL_INPUT',
            'sequence': 1,
            'timestamp': 12345678,
            'payload': {
                'pin': 6,
                'state': False,
                'state_name': 'INACTIVE',
                'is_debounced': True,
                'input_type': 5,
                'input_type_name': 'INPUT_LIMIT_EXTEND',
                'debounce_time_ms': 10
            }
        },
        'digital_output': {
            'size': 0x0A,
            'type': 0x11,
            'type_name': 'DIGITAL_OUTPUT',
            'sequence': 2,
            'timestamp': 12345678,
            'payload': {
                'pin': 9,
                'state': True,
                'output_type': 1,
                'output_type_name': 'OUTPUT_MILL_LAMP',
                'pattern': 0
            }
        },
        'relay_event': {
            'size': 0x0A,
            'type': 0x12,
            'type_name': 'RELAY_EVENT',
            'sequence': 3,
            'timestamp': 12345678,
            'payload': {
                'relay_number': 1,
                'state': True,
                'is_manual': False,
                'success': True,
                'relay_type': 1,
                'relay_type_name': 'RELAY_HYDRAULIC_EXTEND'
            }
        },
        'pressure': {
            'size': 0x0F,
            'type': 0x13,
            'type_name': 'PRESSURE',
            'sequence': 4,
            'timestamp': 12345678,
            'payload': {
                'sensor_pin': 0,
                'pressure_psi': 1000.0,
                'raw_value': 768,
                'is_fault': False,
                'pressure_type': 0
            }
        },
        'system_status': {
            'size': 0x13,
            'type': 0x16,
            'type_name': 'SYSTEM_STATUS',
            'sequence': 5,
            'timestamp': 12345678,
            'payload': {
                'uptime_ms': 10702,
                'loop_frequency_hz': 100,
                'free_memory_bytes': 14357,
                'active_error_count': 2,
                'safety_active': True,
                'estop_active': False,
                'sequence_state': 0,
                'sequence_state_name': 'SEQ_IDLE',
                'mill_lamp_pattern': 0,
                'mill_lamp_pattern_name': 'LAMP_OFF'
            }
        },
        'sequence_event': {
            'size': 0x0B,
            'type': 0x17,
            'type_name': 'SEQUENCE_EVENT',
            'sequence': 6,
            'timestamp': 12345678,
            'payload': {
                'event_type': 1,
                'step_number': 0,
                'elapsed_time_ms': 0
            }
        },
        'safety_event': {
            'size': 0x0A,
            'type': 0x15,
            'type_name': 'SAFETY_EVENT',
            'sequence': 7,
            'timestamp': 12345678,
            'payload': {
                'event_type': 1,
                'is_active': True
            }
        },
        'system_error': {
            'size': 0x18,
            'type': 0x14,
            'type_name': 'SYSTEM_ERROR',
            'sequence': 8,
            'timestamp': 12345678,
            'payload': {
                'error_code': 0x10,
                'acknowledged': True,
                'active': False,
                'severity': 2,
                'severity_name': 'ERROR',
                'description': 'Config invalid'
            }
        }
    }
