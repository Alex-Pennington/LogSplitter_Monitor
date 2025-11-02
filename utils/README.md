# LogSplitter Monitor Utilities

This folder contains reference documentation and utilities for working with the LogSplitter Monitor's MQTT protobuf output.

## Files

### Documentation
- **`MQTT_PROTOBUF_REFERENCE.md`** - Complete reference guide for the binary protobuf messages published to MQTT
- **`controller_telemetry.proto`** - Protocol buffer definitions file defining all message structures

### Tools
- **`mqtt_protobuf_decoder.py`** - Python script to monitor and decode MQTT protobuf messages
- **`requirements.txt`** - Python dependencies for the decoder script
- **`config.json.template`** - Template configuration file for MQTT settings
- **`protobuf_ingestion.py`** - Data ingestion script for storing telemetry data
- **`start.sh`** - Shell script to start monitoring services

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure MQTT Settings
Edit `mqtt_protobuf_decoder.py` and update the MQTT configuration:
```python
MQTT_BROKER = "your-mqtt-broker.com"
MQTT_USER = "your-username"  
MQTT_PASS = "your-password"
```

### 3. Run the Decoder
```bash
python mqtt_protobuf_decoder.py
```

### 4. Monitor Output
The decoder will connect to MQTT and display decoded protobuf messages in real-time:
```
[14:32:15] DIGITAL_INPUT (0x10)
  Sequence: 42
  Timestamp: 1523456 ms (1523.5s)
  Payload:
    pin: 6 (LIMIT_EXTEND)
    state: True (ACTIVE)
    is_debounced: True
    debounce_time_ms: 50

[14:32:18] PRESSURE (0x13)
  Sequence: 15
  Timestamp: 1526780 ms (1526.8s)
  Payload:
    sensor_pin: 1 (A1)
    pressure_psi: 2345.67 (SYSTEM_PRESSURE)
    raw_adc_value: 512
    fault_status: OK
```

## Message Types

The LogSplitter Controller sends 8 different types of binary protobuf messages via the Monitor to MQTT:

| Type | ID | Description | Size | Frequency |
|------|----|-----------| -----|-----------|
| Digital Input | 0x10 | Button/switch state changes | 11 bytes | On change |
| Digital Output | 0x11 | Mill lamp state changes | 10 bytes | On change |
| Relay Event | 0x12 | Relay operations | 10 bytes | On command |
| Pressure | 0x13 | Hydraulic pressure readings | 15 bytes | Every 30s |
| System Error | 0x14 | Error conditions | 9-33 bytes | On error |
| Safety Event | 0x15 | Safety system events | 10 bytes | On change |
| System Status | 0x16 | Heartbeat/status | 19 bytes | Every 30s |
| Sequence Event | 0x17 | Sequence control events | 11 bytes | On change |

## MQTT Topic

All messages are published to the single topic: **`controller/protobuff`**

Messages are binary protobuf data with the following structure:
```
[SIZE_BYTE][MESSAGE_TYPE][SEQUENCE_ID][TIMESTAMP][PAYLOAD...]
```

## Integration Examples

### Python MQTT Client
```python
import paho.mqtt.client as mqtt
from mqtt_protobuf_decoder import LogSplitterProtobufDecoder

decoder = LogSplitterProtobufDecoder()

def on_message(client, userdata, message):
    if message.topic == "controller/protobuff":
        decoded = decoder.decode_message(message.payload)
        print(f"Received: {decoded['type_name']}")
        # Process decoded message...

client = mqtt.Client()
client.on_message = on_message
client.connect("your-broker", 1883)
client.subscribe("controller/protobuff")
client.loop_forever()
```

### Node.js Example
```javascript
const mqtt = require('mqtt');
const client = mqtt.connect('mqtt://your-broker');

client.subscribe('controller/protobuff');

client.on('message', (topic, message) => {
  if (topic === 'controller/protobuff') {
    // Decode binary message
    const size = message.readUInt8(0);
    const type = message.readUInt8(1);
    const sequence = message.readUInt8(2); 
    const timestamp = message.readUInt32LE(3);
    
    console.log(`Message type: 0x${type.toString(16)}, size: ${size} bytes`);
  }
});
```

## Data Storage Integration

### InfluxDB Time Series
The protobuf data is ideal for time series databases like InfluxDB:

```python
from influxdb_client import InfluxDBClient, Point

# Store pressure readings
if decoded['type_name'] == 'PRESSURE':
    point = Point("pressure") \
        .tag("sensor", f"A{decoded['payload']['sensor_pin']}") \
        .tag("type", decoded['payload']['pressure_type_name']) \
        .field("psi", decoded['payload']['pressure_psi']) \
        .field("raw_adc", decoded['payload']['raw_adc_value']) \
        .time(decoded['timestamp'])
    
    write_api.write("logsplitter", "telemetry", point)
```

### Database Schema Example
```sql
-- PostgreSQL table for storing telemetry
CREATE TABLE logsplitter_telemetry (
    id SERIAL PRIMARY KEY,
    received_at TIMESTAMP DEFAULT NOW(),
    message_type SMALLINT NOT NULL,
    message_type_name VARCHAR(20) NOT NULL,
    sequence_id SMALLINT NOT NULL,
    controller_timestamp BIGINT NOT NULL,
    payload_json JSONB NOT NULL
);

-- Index for time-based queries
CREATE INDEX idx_telemetry_timestamp ON logsplitter_telemetry(controller_timestamp);
CREATE INDEX idx_telemetry_type ON logsplitter_telemetry(message_type);
```

## Troubleshooting

### Connection Issues
1. Verify MQTT broker settings in script
2. Check network connectivity to broker
3. Verify MQTT credentials and permissions

### Decode Errors
1. Check message size validation (7-33 bytes)
2. Verify message type IDs (0x10-0x17)
3. Check for message corruption or network issues

### Missing Messages
1. Verify Monitor is connected to Controller Serial1
2. Check Monitor's MQTT publishing status
3. Monitor Controller's binary telemetry output

### Performance
1. Consider MQTT QoS settings for reliability
2. Monitor message rates and broker capacity
3. Implement message queuing for high-throughput scenarios

## Development

### Adding New Message Types
1. Update `controller_telemetry.proto` with new message definition
2. Add decoder method in `LogSplitterProtobufDecoder`
3. Update reference documentation
4. Test with real hardware

### Extending the Decoder
The decoder is designed to be extended for specific use cases:
- Add custom message filtering
- Implement data validation rules
- Add export formats (CSV, JSON, etc.)
- Create real-time dashboards
- Integrate with alerting systems

For questions or issues, refer to the main project documentation.