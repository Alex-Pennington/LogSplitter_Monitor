# LogSplitter Monitor MQTT Topics Documentation

## Overview

The LogSplitter Monitor system publishes comprehensive sensor data and system status via MQTT for integration with other systems. This document provides complete topic definitions, data formats, and usage examples for AI integration and external systems.

**System Context**: Arduino UNO R4 WiFi monitor unit with precision sensors for weight, power, temperature monitoring, plus LCD display and LED heartbeat animation.

## MQTT Configuration

- **Broker**: 159.203.138.46:1883 (configured in constants.h)
- **Client ID**: Auto-generated from MAC address (format: monitor-XXXXXX)
- **Authentication**: Username/password from arduino_secrets.h
- **QoS**: 0 (fire and forget)
- **Retain**: False for most topics

## Published Topics (Monitor → External Systems)

### System Status Topics

#### monitor/heartbeat
**Purpose**: System health and uptime monitoring
**Format**: `uptime=<seconds> state=<int>`
**Publish Interval**: Every 30 seconds (configurable via HEARTBEAT_INTERVAL_MS)
**Example**: `uptime=1247 state=1`
**States**: 0=Initializing, 1=Connecting, 2=Monitoring, 3=Error, 4=Maintenance

#### monitor/error
**Purpose**: System error notifications
**Format**: Error description string
**Trigger**: On error conditions
**Example**: `CRITICAL: Sensor missing`

### Weight Sensor Topics (NAU7802)

#### monitor/weight
**Purpose**: Calibrated weight reading
**Format**: Decimal number as string (3 decimal places)
**Unit**: Configured weight units (typically pounds or kg)
**Publish Interval**: Every sensor reading cycle (~1-2 seconds)
**Example**: `234.567`
**Range**: 0.000 to sensor maximum capacity

#### monitor/weight/raw
**Purpose**: Raw ADC reading from NAU7802
**Format**: Integer as string
**Unit**: Raw 24-bit ADC counts
**Publish Interval**: Same as calibrated weight
**Example**: `1847362`
**Range**: -8388608 to 8388607 (24-bit signed)

#### monitor/weight/status
**Purpose**: Comprehensive weight sensor status
**Format**: `status: <status>, ready: <YES/NO>, weight: <float>, raw: <long>`
**Example**: `status: Ready, ready: YES, weight: 234.567, raw: 1847362`
**Status Values**: Ready, Not Ready, Calibration Required, Error

### Temperature Sensor Topics (MCP9600)

#### monitor/temperature (Legacy)
**Purpose**: Local/ambient temperature (backward compatibility)
**Format**: Decimal number as string (2 decimal places)
**Unit**: Fahrenheit
**Publish Interval**: Every 10 seconds
**Example**: `72.15`
**Range**: -40.00 to 257.00°F

#### monitor/temperature/local
**Purpose**: Local/ambient temperature from MCP9600
**Format**: Decimal number as string (2 decimal places)
**Unit**: Fahrenheit
**Publish Interval**: Every 10 seconds
**Example**: `72.15`

#### monitor/temperature/remote
**Purpose**: Remote/thermocouple temperature from MCP9600
**Format**: Decimal number as string (2 decimal places)
**Unit**: Fahrenheit
**Publish Interval**: Every 10 seconds
**Example**: `68.50`

### Power Monitor Topics (INA219)

#### monitor/power/voltage
**Purpose**: Bus voltage measurement
**Format**: Decimal number as string (3 decimal places)
**Unit**: Volts
**Publish Interval**: Every sensor reading cycle
**Example**: `12.345`
**Range**: 0.000 to 26.000V (INA219 limit)

#### monitor/power/current
**Purpose**: Current measurement
**Format**: Decimal number as string (2 decimal places)
**Unit**: Milliamperes (mA)
**Publish Interval**: Same as voltage
**Example**: `1234.56`
**Range**: Depends on shunt resistor configuration

#### monitor/power/watts
**Purpose**: Calculated power consumption
**Format**: Decimal number as string (2 decimal places)
**Unit**: Milliwatts (mW)
**Publish Interval**: Same as voltage
**Example**: `15123.45`
**Calculation**: Voltage × Current

#### monitor/power/status
**Purpose**: Comprehensive power sensor status
**Format**: `ready: <YES/NO>, voltage: <float>V, current: <float>mA, power: <float>mW`
**Example**: `ready: YES, voltage: 12.345V, current: 1234.56mA, power: 15123.45mW`

### System Monitoring Topics

#### monitor/uptime
**Purpose**: System uptime in seconds
**Format**: Integer as string
**Unit**: Seconds since boot
**Publish Interval**: Every 10 seconds
**Example**: `1247`

#### monitor/memory
**Purpose**: Available free memory
**Format**: Integer as string
**Unit**: Bytes
**Publish Interval**: Every 10 seconds
**Example**: `25600`

### Fuel Monitoring Topic

#### monitor/fuel/gallons
**Purpose**: Calculated fuel volume from weight sensor
**Format**: Decimal number as string (2 decimal places)
**Unit**: Gallons (US)
**Calculation**: Weight in kg ÷ gasoline density (0.7489 kg/gal)
**Example**: `12.34`
**Note**: Derived from weight sensor reading

## Subscribed Topics (External Systems → Monitor)

### Command and Control

#### monitor/control
**Purpose**: Remote command execution
**Format**: Plain text commands (same as telnet interface)
**Examples**:
- `help` - Get available commands
- `show` - Get current readings
- `weight tare` - Tare the scale
- `heartbeat rate 60` - Set heartbeat to 60 BPM
- `lcd off` - Turn off LCD display

#### monitor/control/resp
**Purpose**: Command response publication
**Format**: Response text from command execution
**Auto-publish**: Responses to commands sent via monitor/control

## Data Integration Examples

### Database Integration Pattern
```sql
-- Example table structure for time-series data
CREATE TABLE monitor_data (
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    topic VARCHAR(100),
    value DECIMAL(10,3),
    unit VARCHAR(20)
);

-- Insert pattern for numeric topics
INSERT INTO monitor_data (topic, value, unit) VALUES 
('monitor/weight', 234.567, 'lbs'),
('monitor/temperature/local', 72.15, 'F'),
('monitor/power/voltage', 12.345, 'V');
```

### Home Assistant Integration
```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "Monitor Weight"
      state_topic: "monitor/weight"
      unit_of_measurement: "lbs"
      device_class: "weight"
      
    - name: "Monitor Temperature"
      state_topic: "monitor/temperature/local"
      unit_of_measurement: "°F"
      device_class: "temperature"
      
    - name: "Monitor Power"
      state_topic: "monitor/power/watts"
      unit_of_measurement: "mW"
      device_class: "power"
```

### Node-RED Flow Pattern
```javascript
// Example Node-RED function to process weight data
if (msg.topic === "monitor/weight") {
    const weight = parseFloat(msg.payload);
    
    // Convert to different units
    msg.weight_lbs = weight;
    msg.weight_kg = weight * 0.453592;
    
    // Set alerts
    if (weight > 500) {
        msg.alert = "High weight detected";
    }
    
    return msg;
}
```

## Publishing Intervals and Timing

| Data Type | Default Interval | Configurable |
|-----------|------------------|-------------|
| System Status | 10 seconds | STATUS_PUBLISH_INTERVAL_MS |
| Heartbeat | 30 seconds | HEARTBEAT_INTERVAL_MS |
| Weight Data | ~1-2 seconds | Sensor reading cycle |
| Power Data | ~1-2 seconds | Sensor reading cycle |
| Temperature | 10 seconds | Status publish cycle |
| Digital Inputs | Immediate | On state change |

## Error Handling and Reliability

### Connection Monitoring
- **WiFi Status**: Monitor connection health via heartbeat
- **MQTT Status**: Failed publish attempts tracked
- **Sensor Status**: Individual sensor health in status topics

### Data Validation
- **Range Checking**: Invalid sensor readings filtered
- **Timestamp**: Uptime provides message freshness
- **Status Fields**: Comprehensive status in sensor status topics

### Retry Logic
- **Network Reconnection**: Automatic with exponential backoff
- **Failed Publishes**: Counted in system metrics
- **Sensor Errors**: Tracked and reported in status

## Command Interface via MQTT

### Available Commands
All telnet commands available via `r4/monitor/control` topic:

#### System Commands
```
help                    # Show available commands
show                    # Display current readings  
status                  # Detailed system information
network                 # Network health check
reset system            # Restart monitor
```

#### Sensor Commands
```
weight read             # Get current weight
weight tare             # Tare scale
weight calibrate 400.0  # Calibrate with known weight
temp read               # Get temperature readings
test sensors            # Test all sensors
```

#### Display Commands
```
lcd on/off              # Control LCD display
lcd clear               # Clear LCD
lcd backlight on/off    # Control backlight
heartbeat on/off        # Control heartbeat animation
heartbeat rate 72       # Set heart rate (30-200 BPM)
heartbeat brightness 255 # Set LED brightness (0-255)
```

### Command Response Format
Commands sent to `monitor/control` receive responses on `monitor/control/resp`:
```
> weight read
234.567

> heartbeat rate 60
Heartbeat rate set to 60 BPM

> invalid command
Unknown command: invalid
```

## Integration Notes for AI Systems

### Topic Parsing Patterns
```python
# Python example for topic parsing
def parse_monitor_topic(topic, payload):
    if topic.startswith("monitor/"):
        parts = topic.split("/")
        
        if parts[1] == "weight":
            if len(parts) == 2:
                return {"type": "weight", "value": float(payload)}
            elif parts[2] == "raw":
                return {"type": "weight_raw", "value": int(payload)}
                
        elif parts[1] == "temperature":
            if len(parts) == 2:
                return {"type": "temp_local", "value": float(payload)}
            elif parts[2] == "local":
                return {"type": "temp_local", "value": float(payload)}
            elif parts[2] == "remote": 
                return {"type": "temp_remote", "value": float(payload)}
                
        elif parts[1] == "power":
            return {"type": f"power_{parts[2]}", "value": float(payload)}
```

### Real-time Monitoring
- **High Frequency**: Weight and power data update every 1-2 seconds
- **Medium Frequency**: System status every 10 seconds
- **Low Frequency**: Heartbeat every 30 seconds
- **Event-based**: Digital inputs and errors as they occur

### Data Persistence Recommendations
- **Time-series Database**: InfluxDB for sensor readings
- **Relational Database**: PostgreSQL for events and status
- **Message Queue**: Redis for real-time processing
- **File Logging**: JSON logs for audit trail

---

**Document Version**: 1.0  
**Last Updated**: December 2024  
**System Version**: Monitor 1.1.0  
**Platform**: Arduino UNO R4 WiFi  
**MQTT Broker**: 159.203.138.46:1883