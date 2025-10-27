# LogSplitter Monitor - MQTT Protobuf Reference

## Overview

The LogSplitter Monitor receives binary protobuf messages from the Controller via Serial1 and forwards them to MQTT topic `controller/protobuff` without modification. This document provides a complete reference for downstream systems that need to decode and process these binary messages.

## MQTT Topic

**Topic**: `controller/protobuff`  
**Format**: Binary protobuf data (size-prefixed)  
**QoS**: 0 (default)  
**Retained**: No  

## Message Structure

All messages follow the size-prefixed binary format from the LogSplitter Controller Binary Telemetry API:

```
[SIZE_BYTE][MESSAGE_TYPE][SEQUENCE_ID][TIMESTAMP][PAYLOAD...]
```

### Header Format (7 bytes total)
```
Byte 0    : Message Size (total bytes including this size byte)
Byte 1    : Message Type (0x10-0x17)
Byte 2    : Sequence ID (rolling counter)
Bytes 3-6 : Timestamp (uint32_t milliseconds since boot, little-endian)
Bytes 7+  : Message-specific payload
```

### Size Validation
- **Minimum**: 7 bytes (size byte + 6-byte header with no payload)
- **Maximum**: 33 bytes (largest message with full payload)
- **Invalid sizes**: Discarded by Monitor with parse error logged

## Message Types

| Type | ID   | Description | Total Size | Payload Size |
|------|------|-------------|------------|--------------|
| Digital Input  | 0x10 | DI state changes | 11 bytes | 4 bytes |
| Digital Output | 0x11 | DO state changes | 10 bytes | 3 bytes |
| Relay Event    | 0x12 | Relay operations | 10 bytes | 3 bytes |
| Pressure       | 0x13 | Pressure readings | 15 bytes | 8 bytes |
| System Error   | 0x14 | Error conditions | 9-33 bytes | 3-27 bytes |
| Safety Event   | 0x15 | Safety system | 10 bytes | 3 bytes |
| System Status  | 0x16 | Heartbeat/status | 19 bytes | 12 bytes |
| Sequence Event | 0x17 | Sequence control | 11 bytes | 4 bytes |

## Payload Structures

### Digital Input Event (Type 0x10)
**Size**: 11 bytes total (1 size + 6 header + 4 payload)

```c
struct DigitalInputPayload {
    uint8_t pin;           // Pin number (2-12)
    uint8_t flags;         // Packed flags
    uint16_t debounce_time; // Debounce time in ms
} __attribute__((packed));

// Flags bit layout:
// Bit 0: state (0=INACTIVE, 1=ACTIVE)
// Bit 1: is_debounced (0=raw, 1=filtered)
// Bits 2-7: input_type (0-8)
```

**Input Types**:
- `0x00`: UNKNOWN
- `0x01`: MANUAL_EXTEND (Pin 2)
- `0x02`: MANUAL_RETRACT (Pin 3)
- `0x03`: SAFETY_CLEAR (Pin 4)
- `0x04`: SEQUENCE_START (Pin 5)
- `0x05`: LIMIT_EXTEND (Pin 6)
- `0x06`: LIMIT_RETRACT (Pin 7)
- `0x07`: SPLITTER_OPERATOR (Pin 8)
- `0x08`: EMERGENCY_STOP (Pin 12)

### Digital Output Event (Type 0x11)
**Size**: 10 bytes total (1 size + 6 header + 3 payload)

```c
struct DigitalOutputPayload {
    uint8_t pin;      // Output pin number
    uint8_t flags;    // Packed flags
    uint8_t reserved; // Reserved for alignment
} __attribute__((packed));

// Flags bit layout:
// Bit 0: state (0=LOW, 1=HIGH)
// Bits 1-3: output_type (0-2)
// Bits 4-7: mill_lamp_pattern (0-3)
```

**Output Types**:
- `0x00`: UNKNOWN
- `0x01`: MILL_LAMP (Pin 9)
- `0x02`: STATUS_LED (Pin 13)

**Mill Lamp Patterns**:
- `0x00`: OFF
- `0x01`: SOLID
- `0x02`: SLOW_BLINK
- `0x03`: FAST_BLINK

### Relay Event (Type 0x12)
**Size**: 10 bytes total (1 size + 6 header + 3 payload)

```c
struct RelayEventPayload {
    uint8_t relay_number; // R1-R9
    uint8_t flags;        // Packed flags
    uint8_t reserved;     // Reserved
} __attribute__((packed));

// Flags bit layout:
// Bit 0: state (0=OFF, 1=ON)
// Bit 1: is_manual (0=auto, 1=manual)
// Bit 2: success (0=fail, 1=success)
// Bits 3-7: relay_type (0-9)
```

**Relay Types**:
- `0x00`: UNKNOWN
- `0x01`: HYDRAULIC_EXTEND (R1)
- `0x02`: HYDRAULIC_RETRACT (R2)
- `0x03-0x06`: RESERVED_3_6 (R3-R6)
- `0x07`: OPERATOR_BUZZER (R7)
- `0x08`: ENGINE_STOP (R8)
- `0x09`: POWER_CONTROL (R9)

### Pressure Reading (Type 0x13)
**Size**: 15 bytes total (1 size + 6 header + 8 payload)

```c
struct PressurePayload {
    uint8_t sensor_pin;   // Analog pin A0-A3
    uint8_t flags;        // Packed flags
    uint16_t raw_value;   // ADC reading
    float pressure_psi;   // Calculated pressure in PSI
} __attribute__((packed));

// Flags bit layout:
// Bit 0: is_fault (0=OK, 1=fault)
// Bits 1-7: pressure_type (0-4)
```

**Pressure Types**:
- `0x00`: UNKNOWN
- `0x01`: SYSTEM_PRESSURE (A1)
- `0x02`: TANK_PRESSURE (A0)
- `0x03`: LOAD_PRESSURE (A2)
- `0x04`: AUXILIARY (A3)

### System Error (Type 0x14)
**Size**: 9-33 bytes total (1 size + 6 header + 3-27 payload)

```c
struct SystemErrorPayload {
    uint8_t error_code;     // Error type code
    uint8_t flags;          // Packed flags
    uint8_t desc_length;    // Description string length (0-24)
    char description[24];   // Error description (variable length)
} __attribute__((packed));

// Flags bit layout:
// Bit 0: acknowledged (0=no, 1=yes)
// Bit 1: active (0=cleared, 1=active)
// Bits 2-3: severity (0-3)
// Bits 4-7: reserved
```

**Error Codes**:
- `0x01`: ERROR_EEPROM_CRC
- `0x02`: ERROR_EEPROM_SAVE
- `0x04`: ERROR_SENSOR_FAULT
- `0x08`: ERROR_NETWORK_PERSISTENT
- `0x10`: ERROR_CONFIG_INVALID
- `0x20`: ERROR_MEMORY_LOW
- `0x40`: ERROR_HARDWARE_FAULT
- `0x80`: ERROR_SEQUENCE_TIMEOUT

**Severity Levels**:
- `0x00`: INFO
- `0x01`: WARNING
- `0x02`: ERROR
- `0x03`: CRITICAL

### Safety Event (Type 0x15)
**Size**: 10 bytes total (1 size + 6 header + 3 payload)

```c
struct SafetyEventPayload {
    uint8_t event_type; // Safety event type
    uint8_t flags;      // Packed flags
    uint8_t reserved;   // Reserved
} __attribute__((packed));

// Flags bit layout:
// Bit 0: is_active (0=inactive, 1=active)
// Bits 1-7: reserved
```

**Event Types**:
- `0x00`: SAFETY_ACTIVATED
- `0x01`: SAFETY_CLEARED
- `0x02`: EMERGENCY_STOP_ACTIVATED
- `0x03`: EMERGENCY_STOP_CLEARED
- `0x04`: LIMIT_SWITCH_TRIGGERED
- `0x05`: PRESSURE_SAFETY

### System Status (Type 0x16)
**Size**: 19 bytes total (1 size + 6 header + 12 payload)

```c
struct SystemStatusPayload {
    uint32_t uptime_ms;     // System uptime in milliseconds
    uint16_t loop_freq_hz;  // Main loop frequency
    uint16_t free_memory;   // Available RAM in bytes
    uint8_t active_errors;  // Count of active errors
    uint8_t flags;          // Packed system flags
    uint16_t reserved;      // Reserved for future use
} __attribute__((packed));

// Flags bit layout:
// Bit 0: safety_active
// Bit 1: estop_active
// Bits 2-5: sequence_state (0-6)
// Bits 6-7: mill_lamp_pattern (0-3)
```

**Sequence States**:
- `0x00`: IDLE
- `0x01`: EXTENDING
- `0x02`: EXTENDED
- `0x03`: RETRACTING
- `0x04`: RETRACTED
- `0x05`: PAUSED
- `0x06`: ERROR_STATE

### Sequence Event (Type 0x17)
**Size**: 11 bytes total (1 size + 6 header + 4 payload)

```c
struct SequenceEventPayload {
    uint8_t event_type;      // Event type
    uint8_t step_number;     // Current step
    uint16_t elapsed_time_ms; // Step duration in ms
} __attribute__((packed));
```

**Event Types**:
- `0x00`: SEQUENCE_STARTED
- `0x01`: SEQUENCE_STEP_COMPLETE
- `0x02`: SEQUENCE_COMPLETE
- `0x03`: SEQUENCE_PAUSED
- `0x04`: SEQUENCE_RESUMED
- `0x05`: SEQUENCE_ABORTED
- `0x06`: SEQUENCE_TIMEOUT

## Message Frequency & Timing

### Real-Time Events (Immediate)
- **Digital Input Changes**: When button/switch state changes
- **Digital Output Changes**: When mill lamp state changes
- **Relay Events**: On every relay command
- **Safety Events**: On safety system activation/deactivation
- **Sequence Events**: On sequence state transitions
- **System Errors**: When errors occur or are cleared

### Periodic Messages
- **Pressure Readings**: Every 30 seconds
- **System Status**: Every 30 seconds (heartbeat)

### Event-Driven Messages
- **System Errors**: Only when errors change state
- **Safety Events**: Only when safety conditions change
- **Sequence Events**: Only during active sequences

## Sample Message Parsing Code

### Python Example
```python
import struct
import time
from typing import Optional, Dict, Any

class LogSplitterProtobufDecoder:
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
    
    def decode_message(self, binary_data: bytes) -> Optional[Dict[str, Any]]:
        """Decode a complete protobuf message from MQTT"""
        if len(binary_data) < 7:  # Minimum message size
            return None
        
        # Parse header
        size_byte = binary_data[0]
        if size_byte != len(binary_data):
            return None  # Size mismatch
        
        msg_type = binary_data[1]
        sequence = binary_data[2]
        timestamp = struct.unpack('<L', binary_data[3:7])[0]  # Little-endian
        payload = binary_data[7:] if len(binary_data) > 7 else b''
        
        # Decode payload based on message type
        decoded_payload = None
        if msg_type in self.message_handlers:
            decoded_payload = self.message_handlers[msg_type](payload)
        
        return {
            'size': size_byte,
            'type': msg_type,
            'type_name': self._get_type_name(msg_type),
            'sequence': sequence,
            'timestamp': timestamp,
            'payload': decoded_payload,
            'raw_payload': payload
        }
    
    def _decode_digital_input(self, payload: bytes) -> Dict[str, Any]:
        if len(payload) < 4:
            return {}
        
        pin, flags, debounce_time = struct.unpack('<BBH', payload)
        
        return {
            'pin': pin,
            'state': bool(flags & 0x01),
            'is_debounced': bool(flags & 0x02),
            'input_type': (flags >> 2) & 0x3F,
            'input_type_name': self._get_input_type_name((flags >> 2) & 0x3F),
            'debounce_time': debounce_time
        }
    
    def _decode_digital_output(self, payload: bytes) -> Dict[str, Any]:
        if len(payload) < 3:
            return {}
        
        pin, flags, reserved = struct.unpack('<BBB', payload)
        
        return {
            'pin': pin,
            'state': bool(flags & 0x01),
            'output_type': (flags >> 1) & 0x07,
            'output_type_name': self._get_output_type_name((flags >> 1) & 0x07),
            'mill_lamp_pattern': (flags >> 4) & 0x0F,
            'mill_lamp_pattern_name': self._get_mill_lamp_pattern_name((flags >> 4) & 0x0F)
        }
    
    def _decode_relay_event(self, payload: bytes) -> Dict[str, Any]:
        if len(payload) < 3:
            return {}
        
        relay_number, flags, reserved = struct.unpack('<BBB', payload)
        
        return {
            'relay_number': relay_number,
            'state': bool(flags & 0x01),
            'is_manual': bool(flags & 0x02),
            'success': bool(flags & 0x04),
            'relay_type': (flags >> 3) & 0x1F,
            'relay_type_name': self._get_relay_type_name((flags >> 3) & 0x1F)
        }
    
    def _decode_pressure(self, payload: bytes) -> Dict[str, Any]:
        if len(payload) < 8:
            return {}
        
        sensor_pin, flags, raw_value = struct.unpack('<BBH', payload[:4])
        pressure_psi = struct.unpack('<f', payload[4:8])[0]
        
        return {
            'sensor_pin': sensor_pin,
            'is_fault': bool(flags & 0x01),
            'pressure_type': (flags >> 1) & 0x7F,
            'pressure_type_name': self._get_pressure_type_name((flags >> 1) & 0x7F),
            'raw_value': raw_value,
            'pressure_psi': pressure_psi
        }
    
    def _decode_system_status(self, payload: bytes) -> Dict[str, Any]:
        if len(payload) < 12:
            return {}
        
        uptime_ms, loop_freq_hz, free_memory, active_errors, flags, reserved = \
            struct.unpack('<LHHBBH', payload)
        
        return {
            'uptime_ms': uptime_ms,
            'uptime_seconds': uptime_ms / 1000.0,
            'loop_freq_hz': loop_freq_hz,
            'free_memory': free_memory,
            'active_errors': active_errors,
            'safety_active': bool(flags & 0x01),
            'estop_active': bool(flags & 0x02),
            'sequence_state': (flags >> 2) & 0x0F,
            'sequence_state_name': self._get_sequence_state_name((flags >> 2) & 0x0F),
            'mill_lamp_pattern': (flags >> 6) & 0x03,
            'mill_lamp_pattern_name': self._get_mill_lamp_pattern_name((flags >> 6) & 0x03)
        }
    
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

# Usage example
decoder = LogSplitterProtobufDecoder()

def on_mqtt_message(client, userdata, message):
    if message.topic == "controller/protobuff":
        decoded = decoder.decode_message(message.payload)
        if decoded:
            print(f"Message Type: {decoded['type_name']}")
            print(f"Timestamp: {decoded['timestamp']} ms")
            print(f"Payload: {decoded['payload']}")
```

## MQTT Integration Examples

### Node.js Example
```javascript
const mqtt = require('mqtt');

class LogSplitterProtobufDecoder {
    constructor() {
        this.client = mqtt.connect('mqtt://your-broker');
        this.client.subscribe('controller/protobuff');
        this.client.on('message', this.handleMessage.bind(this));
    }
    
    handleMessage(topic, message) {
        if (topic === 'controller/protobuff') {
            const decoded = this.decodeMessage(message);
            console.log('Decoded message:', decoded);
        }
    }
    
    decodeMessage(buffer) {
        if (buffer.length < 7) return null;
        
        const size = buffer.readUInt8(0);
        const type = buffer.readUInt8(1);
        const sequence = buffer.readUInt8(2);
        const timestamp = buffer.readUInt32LE(3);
        const payload = buffer.slice(7);
        
        return {
            size,
            type: `0x${type.toString(16).padStart(2, '0')}`,
            sequence,
            timestamp,
            payload: payload.toString('hex')
        };
    }
}
```

## Troubleshooting

### Common Issues

1. **Size Mismatch**: Message size byte doesn't match actual message length
   - Check for message corruption or incomplete reads
   - Verify MQTT broker binary message handling

2. **Invalid Message Types**: Receiving unknown message type IDs
   - Check Controller firmware version compatibility
   - Log unknown types for debugging

3. **Timestamp Wraparound**: uint32_t timestamps will wrap after ~49 days
   - Handle wraparound in long-running systems
   - Use relative timing for sequence analysis

4. **Endianness**: All multi-byte values are little-endian
   - Ensure proper byte order conversion on big-endian systems

### Validation Checklist

- ✅ Message size validation (7-33 bytes)
- ✅ Message type validation (0x10-0x17)
- ✅ Timestamp monotonicity checking
- ✅ Payload length validation per message type
- ✅ Reserved field handling (ignore reserved bytes)
- ✅ Error handling for malformed messages

## Performance Considerations

### Message Rates
- **Peak**: ~500 bytes/minute during active operation
- **Normal**: ~50-100 bytes/minute during idle monitoring
- **Burst**: Multiple messages possible during rapid state changes

### Memory Usage
- **Message Buffer**: Maximum 33 bytes per message
- **Queue Depth**: Consider MQTT broker queuing for reliability
- **Historic Data**: Plan for data retention and archiving

### Network Impact
- **Bandwidth**: Minimal due to binary encoding efficiency
- **Latency**: Sub-millisecond transmission from Controller
- **Reliability**: Consider QoS levels for critical messages

This reference provides all necessary information for decoding and processing the binary protobuf messages forwarded by the LogSplitter Monitor.