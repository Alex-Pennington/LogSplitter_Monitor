# Copilot Coding Agent Instructions for LogSplitter_Monitor

## Project Overview
- **LogSplitter_Monitor** is a standalone Arduino UNO R4 WiFi monitoring system for industrial applications.
- This is the **Monitor component only** - companion to a separate Controller system.
- Features precision sensors, LCD display, LED matrix heartbeat animation, and comprehensive telnet/MQTT interfaces.
- **HTTP Server**: An optional web interface was available in `feature/http-server` branch but has been removed for production optimization.

## Architecture & Key Components
- **MonitorSystem** (`monitor_system.cpp`): Core monitoring logic, sensor management, and data collection
- **HeartbeatAnimation** (`heartbeat_animation.cpp`): 12x8 LED matrix heartbeat animation (30-200 BPM, configurable brightness)
- **CommandProcessor** (`command_processor.cpp`): Unified command parsing for Telnet/MQTT/Serial interfaces
- **NetworkManager** (`network_manager.cpp`): WiFi, MQTT, and syslog connectivity with hostname "LogMonitor"
- **LCDDisplay** (`lcd_display.cpp`): 20x4 character LCD for real-time status display
- **Sensor Classes**: NAU7802 (weight), MCP9600 (temperature), INA219 (power), MCP3421 (ADC), TCA9548A (I2C mux)
- **Shared Logger** (`shared/logger/`): RFC 3164 syslog with dynamic severity levels
- **Secrets**: WiFi/MQTT credentials in `include/arduino_secrets.h` (not in repo; copy from `.template`)

## Build & Development Workflow
- **PlatformIO** on Arduino UNO R4 WiFi platform. Use VS Code tasks or CLI:
  - Build: `pio run`
  - Upload: `pio run --target upload` 
  - Serial Monitor: `pio device monitor`
- **I2C Architecture**: Uses Wire1 (Qwiic connector) for all sensors to avoid conflicts
- **Secrets Setup**: Copy `include/arduino_secrets.h.template` to `include/arduino_secrets.h` with WiFi/MQTT credentials
- **VS Code Tasks**: Pre-configured tasks for build/upload/monitor operations available in workspace

## Command Interface & Patterns
- **Telnet Server**: Port 23 provides full command-line interface for remote administration
- **Core Commands**: `help`, `show`, `status`, `network`, `loglevel 0-7`, `test sensors`, `reset system`
- **Sensor Commands**: `weight read|tare|calibrate`, `temp read`, `power read`, `i2c scan`
- **Visual Control**: `lcd on/off/clear`, `heartbeat on/off/rate 72/brightness 255`
- **Configuration**: `set debug on/off`, `set interval 5000`, `set syslog <ip>`
- **MQTT Integration**: Commands via `monitor/control` topic, responses on `monitor/control/resp`
- **Logging**: RFC 3164 syslog to central server (192.168.1.238:514) with 8-level severity control
- **Rate Limiting**: Commands limited to 10/sec to prevent system overload

## Project Conventions
- **No secrets in repo**: Never commit `arduino_secrets.h`.
- **All new commands** must be documented in `MONITOR_README.md`.
- **Logging**: Use the shared logger (`LOG_INFO`, `LOG_DEBUG`, etc.) for all output.
- **Testing**: Use Telnet/Serial to run `test` commands for diagnostics.
- **I2C Best Practice**: All sensors use Wire1 bus through `i2cMux.selectChannel()` for clean device management.
- **Documentation**: Key docs in `README.md`, `MONITOR_README.md`, and `docs/UNIFIED_ARCHITECTURE.md`.

## Integration & External Dependencies
- **MQTT**: Used for remote monitoring and control via topics like `monitor/weight`, `monitor/temperature`
- **Syslog**: All logs sent to central server (192.168.1.238:514) with RFC 3164 format
- **I2C Sensors**: NAU7802 (weight @0x2A), MCP9600 (temp @0x67), INA219 (power @0x40), MCP3421 (ADC @0x68)
- **Display**: LCD2004A (@0x27) and built-in 12x8 LED matrix for heartbeat animation
- **TCA9548A I2C Multiplexer**: (@0x70) manages multiple sensors on single Wire1 bus

## Examples
- Build and upload Monitor:
  ```bash
  pio run --target upload
  ```
- Configure heartbeat animation:
  ```
  heartbeat rate 60
  heartbeat brightness 200
  heartbeat on
  ```
- Weight sensor calibration:
  ```
  weight zero
  weight calibrate 500.0
  weight save
  ```
- Set syslog server:
  ```
  set syslog 192.168.1.238
  syslog server set to 192.168.1.238:514
  ```

## References
- [README.md](../README.md)
- [MONITOR_README.md](../MONITOR_README.md)
- [docs/UNIFIED_ARCHITECTURE.md](../docs/UNIFIED_ARCHITECTURE.md)
- [Makefile](../Makefile)

---
**Keep these instructions up to date as project structure or conventions evolve.**
