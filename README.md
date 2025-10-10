# LogSplitter Monitor System

A comprehensive Arduino-based monitoring system for industrial log splitting operations, featuring precision sensors, LCD display, LED matrix heartbeat animation, and remote management capabilities.

## 🏗️ System Architecture

The LogSplitter Monitor is a standalone system designed to provide comprehensive monitoring for industrial operations:

- **Monitor System** (root directory) - Remote monitoring with precision sensors, LCD display, and LED matrix heartbeat animation
- **Sensor Integration** - Weight, temperature, and environmental monitoring with I2C multiplexer support

The Monitor system provides comprehensive sensor integration, visual feedback, and remote monitoring capabilities.

### Key Features of the Monitor System:
- **Precision Sensing**: Weight monitoring with NAU7802, temperature with MAX6656, and environmental sensors
- **Visual Feedback**: 20x4 LCD display and 12x8 LED matrix with animated heartbeat (30-200 BPM)
- **Network Integration**: WiFi connectivity, MQTT communication, and telnet command interface
- **Comprehensive Monitoring**: Real-time sensor data collection and remote system management

## ⚡ Quick Start

### 1. Hardware Setup
Connect your sensors to the Arduino UNO R4 WiFi via the Qwiic connector and I2C interface.

### 2. Build and Upload
```bash
# Build the monitor system
pio run --target upload
```

### 3. Configuration
See [MONITOR_README.md](MONITOR_README.md) for detailed setup and [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for complete system deployment.

## 🔧 Core Features

### Unified Logging System
- **RFC 3164 Compliant Syslog** - Enterprise-grade logging to centralized server
- **8-Level Severity** - EMERGENCY (0) to DEBUG (7) with proper prioritization
- **Dynamic Log Levels** - Runtime adjustable via `loglevel 0-7` commands
- **Intelligent Filtering** - Reduces noise while preserving critical information

### Network Integration
- **WiFi Connectivity** - Automatic connection with health monitoring
- **MQTT Communication** - Real-time pub/sub messaging between units
- **Telnet Administration** - Remote command-line access on port 23
- **Syslog Transmission** - UDP logging to 192.168.1.238:514

### Safety & Monitoring
- **Pressure Safety Systems** - Multi-threshold monitoring with emergency stops
- **Hardware Watchdog** - Automatic recovery from system faults
- **Sensor Integration** - Temperature, pressure, and weight monitoring
- **LCD Status Display** - Real-time system information

## 🏭 Industrial Applications

### Primary Use Case: Industrial Monitoring Operations
- **Sensor Data Collection** - Precision weight, temperature, and environmental monitoring
- **Remote Monitoring** - Real-time sensor data collection and system health monitoring
- **Visual Feedback** - LCD display and LED matrix heartbeat animation for system status
- **Data Logging** - Complete audit trail of sensor readings and system events

### System Benefits
- **Precision** - Industrial-grade Arduino R4 WiFi platform with precision sensors
- **Reliability** - Comprehensive error handling and system health monitoring
- **Maintainability** - Remote diagnostics via telnet and comprehensive logging
- **Flexibility** - Modular sensor architecture with I2C multiplexer support

## 📊 Component Overview

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| **Monitor Core** | Main monitoring logic | Sensor management, display control, data collection |
| **Sensor Systems** | Data acquisition | Weight (NAU7802), temperature (MAX6656), environmental monitoring |
| **Display Systems** | Visual feedback | 20x4 LCD display, 12x8 LED matrix heartbeat animation |
| **Network Stack** | Connectivity | WiFi management, MQTT pub/sub, telnet server |
| **Logger System** | Data logging | RFC 3164 syslog, dynamic levels, network transmission |

## 🌐 Network Architecture

```
┌─────────────────┐
│  Monitor System │
│  (Standalone)   │
├─────────────────┤
│ • Sensor Data   │
│ • LCD Display   │
│ • Weight Scale  │
│ • LED Matrix    │
│ • Telnet :23    │
└─────────┬───────┘
          │
          │
          │
 ┌────────▼────────┐
 │  Network Infra  │
 ├─────────────────┤
 │ • WiFi Router   │
 │ • MQTT Broker   │
 │ • Syslog Server │
 └─────────────────┘
```

## 🚀 Getting Started

### Prerequisites
- **PlatformIO** - Arduino development environment
- **Arduino UNO R4 WiFi** - Single monitor unit
- **Network Infrastructure** - WiFi router, MQTT broker, syslog server
- **Sensors** - NAU7802 weight sensor, MAX6656 temperature sensor, LCD display

### Installation Steps

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd LogSplitter_Monitor
   ```

2. **Configure Secrets**
   ```bash
   # Controller (root directory)
   cp include/arduino_secrets.h.template include/arduino_secrets.h
   # Monitor  
   cp monitor/include/arduino_secrets.h.template monitor/include/arduino_secrets.h
   # Edit both files with your WiFi/MQTT credentials
   ```

3. **Build and Deploy**
   ```bash
   # Build controller (from root)
   pio run --target upload
   # Build monitor
   cd monitor && pio run --target upload
   ```

4. **Verify Operation**
   ```bash
   # Check serial output
   pio device monitor
   # Test telnet access
   telnet <controller-ip> 23
   telnet <monitor-ip> 23
   ```

## 📋 Command Interface

Both units support identical command interfaces with unified logging control:

### System Commands
```bash
help                    # Show available commands
show                    # Display current status
status                  # Detailed system information
network                 # Network health and connectivity
```

### Logging Commands
```bash
loglevel                # Show current log level
loglevel 0              # EMERGENCY - System unusable
loglevel 1              # ALERT - Immediate action required
loglevel 2              # CRITICAL - Critical conditions
loglevel 3              # ERROR - Error conditions  
loglevel 4              # WARNING - Warning conditions
loglevel 5              # NOTICE - Normal but significant
loglevel 6              # INFO - Informational (default)
loglevel 7              # DEBUG - Debug-level messages
```

### Testing Commands
```bash
test network            # Test network connectivity
test sensors            # Test sensor readings
syslog test             # Send test message to syslog server
syslog status           # Show syslog configuration
mqtt test               # Send test message to MQTT broker
mqtt status             # Show MQTT broker configuration
```

### Configuration Commands
```bash
set syslog <ip>         # Set syslog server IP
set mqtt <host>         # Set MQTT broker host
```

## 📚 Documentation

### Component Documentation
- **[Monitor System](MONITOR_README.md)** - Complete monitor setup and configuration  
- **[Sensor Integration](INA219_INTEGRATION_SUMMARY.md)** - INA219 current/power sensor integration
- **[ADC Integration](MCP3421_INTEGRATION_SUMMARY.md)** - MCP3421 precision ADC integration
- **[Logging System](docs/LOGGING_SYSTEM.md)** - RFC 3164 syslog architecture
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Complete system deployment

### Technical Documentation
- **[Monitor Architecture](docs/UNIFIED_ARCHITECTURE.md)** - Technical system overview
- **[Network Integration](docs/NETWORK_INTEGRATION.md)** - MQTT and syslog setup
- **[Command Reference](COMMANDS.md)** - Complete command documentation
- **[Error Codes](ERROR.md)** - System error documentation

## 🔧 Development

### Building
```bash
# Build Monitor system
pio run

# Upload to device
pio run --target upload

# Monitor serial output
pio device monitor
```

### Testing
```bash
# Test via telnet interface
telnet <monitor_ip> 23

# Available test commands:
test sensors     # Test all sensor systems  
test network     # Test network connectivity
test weight      # Test weight sensor
temp read        # Test temperature sensors
```

### Debugging
```bash
# Monitor serial output
pio device monitor

# Enable debug logging
telnet <device-ip> 23
> loglevel 7
```

## 🔒 Security Considerations

- **Network Security** - Consider VPN for remote access in production
- **Authentication** - Telnet connections are unencrypted (secure network required)
- **Input Validation** - All commands undergo strict validation
- **Rate Limiting** - Built-in protection against command flooding

## 📈 Monitoring & Maintenance

### System Health
- **Uptime Tracking** - Monitor reports operational uptime and system status
- **Connection Monitoring** - WiFi and MQTT health tracking
- **Sensor Monitoring** - Real-time sensor health and calibration status  
- **Performance Metrics** - Memory usage and response time monitoring

### Maintenance Tasks
- **Log Rotation** - Configure syslog server for log management
- **Firmware Updates** - Upload updates via PlatformIO  
- **Sensor Calibration** - Weight sensor calibration and EEPROM preservation
- **Hardware Monitoring** - Temperature, voltage, and current monitoring

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Safety Notice

This system controls industrial equipment. Always follow proper safety procedures:

- **Test thoroughly** before production deployment
- **Implement proper safety interlocks** for your specific application
- **Regular maintenance** of all safety systems
- **Emergency stop procedures** must be clearly documented and tested

---

**Version**: 1.0.0  
**Platform**: Arduino UNO R4 WiFi  
**Last Updated**: October 2025