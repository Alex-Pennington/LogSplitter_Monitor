# Protobuf Pass-Through Implementation

## Overview

The LogSplitter Monitor firmware has been updated to properly handle size-prefixed binary protobuf messages from the Controller and pass them through to MQTT without modification.

## Key Changes Made

### 1. **Size-Prefixed Message Parsing** (`src/serial_bridge.cpp`)
- Implemented proper state machine for reading size-prefixed binary messages
- First byte read is the message size (7-33 bytes as per API)
- Validates message size bounds before processing
- Accumulates bytes until complete message is received

### 2. **Message Format Compliance**
- Follows LogSplitter Controller Binary Telemetry API specification
- Handles messages from 7 bytes (minimum) to 33 bytes (maximum)
- Preserves complete binary message including size byte

### 3. **Binary Pass-Through** (`processProtobufMessage`)
- Forwards complete binary messages to MQTT topic `controller/protobuff`
- No decoding or modification of the binary data
- Maintains message integrity for downstream processing

### 4. **Error Handling & Robustness**
- Buffer overflow protection
- Message timeout handling (1 second for incomplete messages)
- Parse error counting and logging
- Connection timeout monitoring

### 5. **Updated Constants** (`include/serial_bridge.h`)
- `PROTOBUF_MIN_MESSAGE_SIZE`: 7 bytes (1 size + 6 header minimum)
- `PROTOBUF_MAX_MESSAGE_SIZE`: 33 bytes (maximum per API)
- Added size validation bounds

## Message Flow

```
Controller (A4 TX) ──► Monitor Serial1 ──► SerialBridge ──► MQTT ──► controller/protobuff
```

### Detailed Flow:
1. **Controller** sends size-prefixed binary protobuf on A4 (TX) at 115200 baud
2. **Monitor Serial1** receives binary data
3. **SerialBridge** parses size-prefixed messages:
   - Reads size byte first
   - Validates size (7-33 bytes)
   - Accumulates message bytes
   - Forwards complete message to MQTT
4. **MQTT** publishes to `controller/protobuff` topic
5. **Downstream systems** receive raw binary protobuf for processing

## Testing & Verification

### 1. **Build Verification**
```bash
cd monitor/
pio run
# ✅ Build successful
```

### 2. **Serial Monitor Testing**
```bash
pio device monitor
# Look for logs like:
# "Serial bridge initialized on Serial1 at 115200 baud"
# "Network manager configured for binary pass-through"
```

### 3. **MQTT Topic Monitoring**
```bash
mosquitto_sub -h <mqtt_broker> -t "controller/protobuff" -v
# Should show binary data when Controller is sending protobuf messages
```

### 4. **Statistics Monitoring**
Connect via Telnet and check bridge statistics:
```
telnet <monitor_ip> 23
> status
# Look for:
# "Protobuf Mode: Size-Prefixed Binary"
# "Messages Received: X"
# "Messages Forwarded: X"
# "Parse Errors: 0" (should be 0 or very low)
```

## Expected Behavior

### Normal Operation:
- Monitor receives size-prefixed binary messages from Controller
- Messages are immediately forwarded to MQTT without modification
- Statistics show successful receive/forward counts
- No parse errors under normal conditions

### Error Conditions:
- **Invalid size bytes**: Logged as parse errors, discarded
- **Incomplete messages**: Timeout after 1 second, buffer reset
- **MQTT disconnection**: Messages counted as dropped
- **Buffer overflow**: Rare, but handled with error logging

## API Compliance

This implementation fully complies with the LogSplitter Controller Binary Telemetry API:

- ✅ **Size-Prefixed Format**: `[SIZE_BYTE][MESSAGE_HEADER][MESSAGE_PAYLOAD]`
- ✅ **Size Range**: 7-33 bytes (validated)
- ✅ **Baud Rate**: 115200 (fixed)
- ✅ **Binary Pass-Through**: No ASCII conversion or modification
- ✅ **Message Types**: Supports all types 0x10-0x17
- ✅ **Error Handling**: Robust parsing with timeout protection

## Message Types Supported (Pass-Through)

| Type | ID   | Description | Size |
|------|------|-------------|------|
| Digital Input  | 0x10 | DI# state changes | 11 bytes |
| Digital Output | 0x11 | DO# state changes | 10 bytes |
| Relay Event    | 0x12 | R# relay operations | 10 bytes |
| Pressure       | 0x13 | Hydraulic pressure | 15 bytes |
| System Error   | 0x14 | Error conditions | 9-33 bytes |
| Safety Event   | 0x15 | Safety system | 10 bytes |
| System Status  | 0x16 | Heartbeat/status | 19 bytes |
| Sequence Event | 0x17 | Sequence control | 11 bytes |

All message types are forwarded as raw binary data to the MQTT topic.

## Troubleshooting

### No Messages Received
1. Check Serial1 connection between Controller A4 and Monitor
2. Verify Controller is sending binary telemetry
3. Check baud rate (115200)
4. Monitor parse errors in statistics

### Parse Errors
1. Check electrical connections
2. Verify common ground between units
3. Check for electrical noise
4. Monitor for buffer overflows

### MQTT Issues
1. Verify MQTT broker connectivity
2. Check topic subscription: `controller/protobuff`
3. Verify binary data is being published
4. Check network stability

## Future Enhancements

While this implementation focuses on pass-through, future versions could:
- Add optional message decoding for local display
- Implement message validation
- Add performance metrics
- Support multiple output topics
- Add message filtering by type

## Dependencies

- **NetworkManager**: For MQTT publishing
- **Logger**: For debug output and statistics
- **Arduino Serial1**: Hardware UART for Controller communication
- **MQTT Client**: For binary message publishing

The implementation is self-contained and requires no external protobuf libraries for pass-through operation.