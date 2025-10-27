#!/usr/bin/env python3
"""
LogSplitter MQTT Protobuf Decoder Example

This script demonstrates how to connect to the MQTT broker and decode
binary protobuf messages from the LogSplitter Monitor.

Usage:
    python mqtt_protobuf_decoder.py

Requirements:
    pip install paho-mqtt

Configuration:
    Update MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASS below
"""

import paho.mqtt.client as mqtt
import struct
import time
import json
from typing import Optional, Dict, Any

# MQTT Configuration
MQTT_BROKER = "your-mqtt-broker.com"  # Update with your broker
MQTT_PORT = 1883
MQTT_USER = "your-username"           # Update with your credentials
MQTT_PASS = "your-password"
MQTT_TOPIC = "controller/protobuff"

class LogSplitterProtobufDecoder:
    """Decoder for LogSplitter Controller binary protobuf messages"""
    
    def __init__(self):
        self.message_handlers = {
            0x10: self._decode_digital_input,
            0x11: self._decode_digital_output,
            0x12: self._decode_relay_event,
            0x13: self._decode_pressure,
            0x14: self._decode_system_error,
            0x15: self._decode_safety_event,
            0x16: self._decode_system_status,
            0x17: self._decode_sequence_event
        }
        
        # Statistics
        self.messages_received = 0
        self.messages_decoded = 0
        self.decode_errors = 0
        self.last_sequence = {}  # Track sequence numbers per message type
        
    def decode_message(self, binary_data: bytes) -> Optional[Dict[str, Any]]:
        """Decode a complete protobuf message from MQTT"""
        try:
            self.messages_received += 1
            
            if len(binary_data) < 7:  # Minimum message size
                self.decode_errors += 1
                print(f"ERROR: Message too short: {len(binary_data)} bytes")
                return None
            
            # Parse header
            size_byte = binary_data[0]
            if size_byte != len(binary_data):
                self.decode_errors += 1
                print(f"ERROR: Size mismatch: expected {size_byte}, got {len(binary_data)}")
                return None
            
            msg_type = binary_data[1]
            sequence = binary_data[2]
            timestamp = struct.unpack('<L', binary_data[3:7])[0]  # Little-endian uint32
            payload = binary_data[7:] if len(binary_data) > 7 else b''
            
            # Check for missing messages
            if msg_type in self.last_sequence:
                expected_seq = (self.last_sequence[msg_type] + 1) % 256
                if sequence != expected_seq:
                    print(f"WARNING: Sequence gap for type 0x{msg_type:02X}: "
                          f"expected {expected_seq}, got {sequence}")
            
            self.last_sequence[msg_type] = sequence
            
            # Decode payload based on message type
            decoded_payload = None
            if msg_type in self.message_handlers:
                decoded_payload = self.message_handlers[msg_type](payload)
                if decoded_payload is not None:
                    self.messages_decoded += 1
            else:
                print(f"WARNING: Unknown message type: 0x{msg_type:02X}")
            
            return {
                'size': size_byte,
                'type': msg_type,
                'type_name': self._get_type_name(msg_type),
                'sequence': sequence,
                'timestamp': timestamp,
                'timestamp_sec': timestamp / 1000.0,
                'payload': decoded_payload,
                'raw_payload_hex': payload.hex() if payload else ''
            }
            
        except Exception as e:
            self.decode_errors += 1
            print(f"ERROR: Decode exception: {e}")
            return None
    
    def _decode_digital_input(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 4:
            return None
        
        pin, flags, debounce_time = struct.unpack('<BBH', payload)
        
        return {
            'pin': pin,
            'state': bool(flags & 0x01),
            'state_name': 'ACTIVE' if (flags & 0x01) else 'INACTIVE',
            'is_debounced': bool(flags & 0x02),
            'input_type': (flags >> 2) & 0x3F,
            'input_type_name': self._get_input_type_name((flags >> 2) & 0x3F),
            'debounce_time_ms': debounce_time
        }
    
    def _decode_digital_output(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 3:
            return None
        
        pin, flags, reserved = struct.unpack('<BBB', payload)
        
        return {
            'pin': pin,
            'state': bool(flags & 0x01),
            'state_name': 'HIGH' if (flags & 0x01) else 'LOW',
            'output_type': (flags >> 1) & 0x07,
            'output_type_name': self._get_output_type_name((flags >> 1) & 0x07),
            'mill_lamp_pattern': (flags >> 4) & 0x0F,
            'mill_lamp_pattern_name': self._get_mill_lamp_pattern_name((flags >> 4) & 0x0F)
        }
    
    def _decode_relay_event(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 3:
            return None
        
        relay_number, flags, reserved = struct.unpack('<BBB', payload)
        
        return {
            'relay_number': relay_number,
            'relay_name': f'R{relay_number}',
            'state': bool(flags & 0x01),
            'state_name': 'ON' if (flags & 0x01) else 'OFF',
            'is_manual': bool(flags & 0x02),
            'operation_mode': 'MANUAL' if (flags & 0x02) else 'AUTO',
            'success': bool(flags & 0x04),
            'success_name': 'SUCCESS' if (flags & 0x04) else 'FAILED',
            'relay_type': (flags >> 3) & 0x1F,
            'relay_type_name': self._get_relay_type_name((flags >> 3) & 0x1F)
        }
    
    def _decode_pressure(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 8:
            return None
        
        sensor_pin, flags, raw_value = struct.unpack('<BBH', payload[:4])
        pressure_psi = struct.unpack('<f', payload[4:8])[0]
        
        return {
            'sensor_pin': sensor_pin,
            'sensor_name': f'A{sensor_pin}',
            'is_fault': bool(flags & 0x01),
            'fault_status': 'FAULT' if (flags & 0x01) else 'OK',
            'pressure_type': (flags >> 1) & 0x7F,
            'pressure_type_name': self._get_pressure_type_name((flags >> 1) & 0x7F),
            'raw_adc_value': raw_value,
            'pressure_psi': round(pressure_psi, 2)
        }
    
    def _decode_system_error(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 3:
            return None
        
        error_code, flags, desc_length = struct.unpack('<BBB', payload[:3])
        
        description = ""
        if desc_length > 0 and len(payload) > 3:
            desc_bytes = payload[3:3+min(desc_length, len(payload)-3)]
            description = desc_bytes.decode('ascii', errors='ignore').rstrip('\x00')
        
        return {
            'error_code': error_code,
            'error_code_hex': f'0x{error_code:02X}',
            'error_name': self._get_error_code_name(error_code),
            'acknowledged': bool(flags & 0x01),
            'active': bool(flags & 0x02),
            'severity': (flags >> 2) & 0x03,
            'severity_name': self._get_severity_name((flags >> 2) & 0x03),
            'description': description
        }
    
    def _decode_safety_event(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 3:
            return None
        
        event_type, flags, reserved = struct.unpack('<BBB', payload)
        
        return {
            'event_type': event_type,
            'event_type_name': self._get_safety_event_name(event_type),
            'is_active': bool(flags & 0x01),
            'status': 'ACTIVE' if (flags & 0x01) else 'INACTIVE'
        }
    
    def _decode_system_status(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 12:
            return None
        
        uptime_ms, loop_freq_hz, free_memory, active_errors, flags, reserved = \
            struct.unpack('<LHHBBH', payload)
        
        return {
            'uptime_ms': uptime_ms,
            'uptime_seconds': round(uptime_ms / 1000.0, 1),
            'uptime_minutes': round(uptime_ms / 60000.0, 1),
            'loop_frequency_hz': loop_freq_hz,
            'free_memory_bytes': free_memory,
            'active_error_count': active_errors,
            'safety_active': bool(flags & 0x01),
            'estop_active': bool(flags & 0x02),
            'sequence_state': (flags >> 2) & 0x0F,
            'sequence_state_name': self._get_sequence_state_name((flags >> 2) & 0x0F),
            'mill_lamp_pattern': (flags >> 6) & 0x03,
            'mill_lamp_pattern_name': self._get_mill_lamp_pattern_name((flags >> 6) & 0x03)
        }
    
    def _decode_sequence_event(self, payload: bytes) -> Optional[Dict[str, Any]]:
        if len(payload) < 4:
            return None
        
        event_type, step_number, elapsed_time_ms = struct.unpack('<BBH', payload)
        
        return {
            'event_type': event_type,
            'event_type_name': self._get_sequence_event_name(event_type),
            'step_number': step_number,
            'elapsed_time_ms': elapsed_time_ms,
            'elapsed_time_sec': round(elapsed_time_ms / 1000.0, 2)
        }
    
    # Name lookup methods
    def _get_type_name(self, msg_type: int) -> str:
        types = {
            0x10: 'DIGITAL_INPUT',
            0x11: 'DIGITAL_OUTPUT', 
            0x12: 'RELAY_EVENT',
            0x13: 'PRESSURE',
            0x14: 'SYSTEM_ERROR',
            0x15: 'SAFETY_EVENT',
            0x16: 'SYSTEM_STATUS',
            0x17: 'SEQUENCE_EVENT'
        }
        return types.get(msg_type, f'UNKNOWN_0x{msg_type:02X}')
    
    def _get_input_type_name(self, input_type: int) -> str:
        types = {
            0x00: 'UNKNOWN',
            0x01: 'MANUAL_EXTEND',
            0x02: 'MANUAL_RETRACT', 
            0x03: 'SAFETY_CLEAR',
            0x04: 'SEQUENCE_START',
            0x05: 'LIMIT_EXTEND',
            0x06: 'LIMIT_RETRACT',
            0x07: 'SPLITTER_OPERATOR',
            0x08: 'EMERGENCY_STOP'
        }
        return types.get(input_type, f'UNKNOWN_{input_type}')
    
    def _get_output_type_name(self, output_type: int) -> str:
        types = {
            0x00: 'UNKNOWN',
            0x01: 'MILL_LAMP',
            0x02: 'STATUS_LED'
        }
        return types.get(output_type, f'UNKNOWN_{output_type}')
    
    def _get_mill_lamp_pattern_name(self, pattern: int) -> str:
        patterns = {
            0x00: 'OFF',
            0x01: 'SOLID',
            0x02: 'SLOW_BLINK',
            0x03: 'FAST_BLINK'
        }
        return patterns.get(pattern, f'UNKNOWN_{pattern}')
    
    def _get_relay_type_name(self, relay_type: int) -> str:
        types = {
            0x00: 'UNKNOWN',
            0x01: 'HYDRAULIC_EXTEND',
            0x02: 'HYDRAULIC_RETRACT',
            0x07: 'OPERATOR_BUZZER',
            0x08: 'ENGINE_STOP',
            0x09: 'POWER_CONTROL'
        }
        return types.get(relay_type, f'RESERVED_{relay_type}')
    
    def _get_pressure_type_name(self, pressure_type: int) -> str:
        types = {
            0x00: 'UNKNOWN',
            0x01: 'SYSTEM_PRESSURE',
            0x02: 'TANK_PRESSURE',
            0x03: 'LOAD_PRESSURE',
            0x04: 'AUXILIARY'
        }
        return types.get(pressure_type, f'UNKNOWN_{pressure_type}')
    
    def _get_error_code_name(self, error_code: int) -> str:
        codes = {
            0x01: 'EEPROM_CRC',
            0x02: 'EEPROM_SAVE',
            0x04: 'SENSOR_FAULT',
            0x08: 'NETWORK_PERSISTENT',
            0x10: 'CONFIG_INVALID',
            0x20: 'MEMORY_LOW',
            0x40: 'HARDWARE_FAULT',
            0x80: 'SEQUENCE_TIMEOUT'
        }
        return codes.get(error_code, f'UNKNOWN_0x{error_code:02X}')
    
    def _get_severity_name(self, severity: int) -> str:
        levels = {
            0x00: 'INFO',
            0x01: 'WARNING',
            0x02: 'ERROR', 
            0x03: 'CRITICAL'
        }
        return levels.get(severity, f'UNKNOWN_{severity}')
    
    def _get_safety_event_name(self, event_type: int) -> str:
        events = {
            0x00: 'SAFETY_ACTIVATED',
            0x01: 'SAFETY_CLEARED',
            0x02: 'EMERGENCY_STOP_ACTIVATED',
            0x03: 'EMERGENCY_STOP_CLEARED',
            0x04: 'LIMIT_SWITCH_TRIGGERED',
            0x05: 'PRESSURE_SAFETY'
        }
        return events.get(event_type, f'UNKNOWN_{event_type}')
    
    def _get_sequence_state_name(self, state: int) -> str:
        states = {
            0x00: 'IDLE',
            0x01: 'EXTENDING',
            0x02: 'EXTENDED',
            0x03: 'RETRACTING',
            0x04: 'RETRACTED',
            0x05: 'PAUSED',
            0x06: 'ERROR_STATE'
        }
        return states.get(state, f'UNKNOWN_{state}')
    
    def _get_sequence_event_name(self, event_type: int) -> str:
        events = {
            0x00: 'SEQUENCE_STARTED',
            0x01: 'SEQUENCE_STEP_COMPLETE',
            0x02: 'SEQUENCE_COMPLETE',
            0x03: 'SEQUENCE_PAUSED',
            0x04: 'SEQUENCE_RESUMED',
            0x05: 'SEQUENCE_ABORTED',
            0x06: 'SEQUENCE_TIMEOUT'
        }
        return events.get(event_type, f'UNKNOWN_{event_type}')
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get decoder statistics"""
        success_rate = 0.0
        if self.messages_received > 0:
            success_rate = (self.messages_decoded / self.messages_received) * 100.0
        
        return {
            'messages_received': self.messages_received,
            'messages_decoded': self.messages_decoded,
            'decode_errors': self.decode_errors,
            'success_rate_percent': round(success_rate, 1)
        }


class MQTTProtobufMonitor:
    """MQTT client for monitoring LogSplitter protobuf messages"""
    
    def __init__(self, broker_host: str, broker_port: int = 1883, 
                 username: str = None, password: str = None):
        self.decoder = LogSplitterProtobufDecoder()
        self.client = mqtt.Client()
        self.connected = False
        self.start_time = time.time()
        
        # Configure MQTT client
        if username and password:
            self.client.username_pw_set(username, password)
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Connect to broker
        try:
            print(f"Connecting to MQTT broker {broker_host}:{broker_port}...")
            self.client.connect(broker_host, broker_port, 60)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print(f"Connected to MQTT broker (result code {rc})")
            print(f"Subscribing to topic: {MQTT_TOPIC}")
            client.subscribe(MQTT_TOPIC)
            print("Waiting for protobuf messages...")
            print("=" * 60)
        else:
            print(f"Failed to connect to MQTT broker (result code {rc})")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        print(f"Disconnected from MQTT broker (result code {rc})")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT message"""
        if msg.topic == MQTT_TOPIC:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            
            # Decode the binary protobuf message
            decoded = self.decoder.decode_message(msg.payload)
            
            if decoded:
                self._print_decoded_message(timestamp, decoded)
            else:
                print(f"[{timestamp}] DECODE ERROR: {len(msg.payload)} bytes")
                print(f"  Raw hex: {msg.payload.hex()}")
                print()
    
    def _print_decoded_message(self, timestamp: str, decoded: Dict[str, Any]):
        """Pretty print a decoded message"""
        print(f"[{timestamp}] {decoded['type_name']} (0x{decoded['type']:02X})")
        print(f"  Sequence: {decoded['sequence']}")
        print(f"  Timestamp: {decoded['timestamp']} ms ({decoded['timestamp_sec']:.1f}s)")
        
        if decoded['payload']:
            print(f"  Payload:")
            for key, value in decoded['payload'].items():
                if key.endswith('_name') or key in ['state_name', 'status', 'operation_mode', 'success_name', 'fault_status']:
                    continue  # Skip name fields for cleaner output
                
                # Show name alongside numeric values where available
                name_key = key + '_name'
                if name_key in decoded['payload']:
                    print(f"    {key}: {value} ({decoded['payload'][name_key]})")
                else:
                    print(f"    {key}: {value}")
        
        print()
    
    def print_statistics(self):
        """Print decoder statistics"""
        stats = self.decoder.get_statistics()
        runtime = time.time() - self.start_time
        
        print("=" * 60)
        print("STATISTICS")
        print(f"Runtime: {runtime:.1f} seconds")
        print(f"Messages received: {stats['messages_received']}")
        print(f"Messages decoded: {stats['messages_decoded']}")
        print(f"Decode errors: {stats['decode_errors']}")
        print(f"Success rate: {stats['success_rate_percent']}%")
        print("=" * 60)
    
    def run(self):
        """Run the monitor loop"""
        try:
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.print_statistics()
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    print("LogSplitter MQTT Protobuf Monitor")
    print("Press Ctrl+C to stop")
    print()
    
    # Create and run monitor
    try:
        monitor = MQTTProtobufMonitor(
            broker_host=MQTT_BROKER,
            broker_port=MQTT_PORT,
            username=MQTT_USER if MQTT_USER != "your-username" else None,
            password=MQTT_PASS if MQTT_PASS != "your-password" else None
        )
        monitor.run()
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nPlease update the MQTT configuration in this script:")
        print("- MQTT_BROKER: Your MQTT broker hostname")
        print("- MQTT_USER/MQTT_PASS: Your MQTT credentials")