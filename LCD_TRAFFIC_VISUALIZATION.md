# LCD Traffic Visualization for Serial1→MQTT Bridge

## Overview

The LogSplitter Monitor firmware now displays real-time Serial1→MQTT traffic statistics on the LCD screen, providing visual indication of protobuf message flow from the Controller to MQTT broker.

## LCD Display Layout (20x4 Character Display)

### Line 1: System Status
```
State Uptime Net Status
MONITORING 01:23:45 WiFi:OK MQTT:OK Syslog:OK
```

### Line 2-3: Sensor Readings
```
Local: 72.5°F Remote: 180.3°F
Fuel: 45.2 gallons
```

### Line 4: Power Data + Serial1 Traffic
```
12.3V 45mA S1:123→120
```

**Traffic Display Format**: `S1:{received}→{forwarded}`
- `S1:` - Serial1 interface identifier
- `{received}` - Total protobuf messages received from Controller
- `→` - Visual arrow indicating flow direction
- `{forwarded}` - Total messages successfully forwarded to MQTT

## Traffic Statistics

### Message Counters
- **Messages Received**: Increments for each valid size-prefixed protobuf message received from Serial1
- **Messages Forwarded**: Increments for each message successfully published to MQTT topic `controller/protobuff`
- **Counter Persistence**: Counters reset to 0 on firmware restart but provide session totals
- **Update Frequency**: LCD updates every 5 seconds with current statistics

### Example Traffic Patterns
```
S1:---          # No traffic detected
S1:1→1          # First message received and forwarded
S1:25→24        # 25 received, 24 forwarded (1 failed)
S1:150→150      # Perfect forwarding ratio
S1:999→995      # High traffic with few MQTT failures
```

### Traffic Analysis
- **Perfect Ratio** (`received == forwarded`): Healthy operation, no MQTT publish failures
- **Forwarded < Received**: Some MQTT publish failures occurred
- **No Traffic** (`S1:---`): Controller not sending protobuf data or connection issue

## Technical Implementation

### Code Changes

#### LCD Display Update (lcd_display.cpp)
```cpp
void LCDDisplay::updateAdditionalSensors(float voltage, float current, float adcVoltage, 
                                        uint32_t serialMsgCount, uint32_t mqttMsgCount)
```
- Modified method signature to accept traffic statistics
- Compact display format: `"12.3V 45mA S1:123→120"`
- Removed ADC voltage display to make room for traffic data

#### Monitor System Integration (monitor_system.cpp)
```cpp
if (g_serialBridge) {
    serialMsgCount = g_serialBridge->getMessagesReceived();
    mqttMsgCount = g_serialBridge->getMessagesForwarded();
}
```
- Retrieves real-time statistics from SerialBridge instance
- Updates LCD display with current counters every refresh cycle

#### Global Access Pattern (main.cpp)
```cpp
SerialBridge* g_serialBridge = &serialBridge;
```
- Provides global access to SerialBridge statistics
- Enables integration with LCD display system

### Message Flow Visualization

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Controller    │    │     Monitor      │    │   MQTT Broker   │
│                 │    │   SerialBridge   │    │                 │
├─────────────────┤    ├──────────────────┤    ├─────────────────┤
│ Serial1 TX   ───┼───→│ Serial1 RX       │    │                 │
│ Protobuf msgs   │    │ Parse size-prefix│    │                 │
│ 7-33 bytes      │    │ Validate message │    │                 │
│ @115200 baud    │    │ Forward to MQTT ─┼───→│ controller/     │
│                 │    │ Update counters  │    │ protobuff       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   LCD Display    │
                       │ Line 4: Traffic  │
                       │ S1:123→120       │
                       └──────────────────┘
```

## Troubleshooting

### No Traffic Display (`S1:---`)
1. **Check Controller Connection**: Verify Serial1 wiring between units
2. **Controller Firmware**: Ensure Controller is sending protobuf data
3. **Baud Rate**: Confirm both units use 115200 baud on Serial1
4. **Power**: Check Controller power and operational status

### Traffic Imbalance (Forwarded < Received)
1. **MQTT Connection**: Check Monitor's MQTT broker connectivity
2. **Network Health**: Use `network` command via telnet to check status
3. **Broker Load**: Verify MQTT broker can handle message rate
4. **Buffer Overflow**: High message rates may cause occasional drops

### LCD Not Updating
1. **I2C Connection**: Check LCD connection via TCA9548A multiplexer
2. **Channel Selection**: Verify LCD is on I2C multiplexer channel 7
3. **Display Enable**: Use telnet command `lcd on` to enable display
4. **Backlight**: Use telnet command `lcd backlight on` to enable visibility

## Commands for Testing

### Via Telnet (port 23)
```bash
telnet <monitor-ip> 23

# Check LCD status
> lcd
LCD: ENABLED, Backlight: ON, Ready: true

# Show system status
> show
Serial1→MQTT: 123 received, 120 forwarded

# Monitor network health
> network
wifi=OK mqtt=OK stable=YES disconnects=0 fails=0 uptime=1247s
```

### Real-time Monitoring
```bash
# Watch LCD updates in real-time
> monitor start
MONITORING mode activated - LCD traffic display active

# Check protobuf bridge status
> status
SerialBridge: 123 msgs received, 120 forwarded, 3 errors
```

## Performance Impact

### Memory Usage
- **RAM Overhead**: Minimal (~32 bytes for traffic counters)
- **Flash Overhead**: ~200 bytes for additional LCD display code
- **CPU Impact**: Negligible (statistics updated only during LCD refresh)

### Update Frequency
- **LCD Refresh**: Every 5 seconds (configurable)
- **Counter Updates**: Real-time with each message processed
- **Network Overhead**: No additional network traffic for statistics

## Integration Benefits

### Operational Monitoring
- **Real-time Feedback**: Immediate visual confirmation of data flow
- **Problem Detection**: Traffic imbalances indicate connectivity issues
- **Session Tracking**: Message counts provide operational metrics

### Maintenance Support
- **Visual Diagnostics**: LCD display eliminates need for serial/telnet monitoring
- **Traffic Patterns**: Historical patterns visible through counter progression
- **System Health**: Traffic flow indicates overall system health

---

**Version**: 1.0  
**Last Updated**: November 2024  
**Hardware**: Arduino UNO R4 WiFi, I2C LCD 20x4  
**Dependencies**: SerialBridge, LCDDisplay, MonitorSystem