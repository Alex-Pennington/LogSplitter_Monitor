# Copilot Coding Agent Instructions for LogSplitter_Monitor

## Project Overview
- **LogSplitter_Monitor** is a unified industrial control and monitoring system for Arduino UNO R4 WiFi, managing both a Controller and a Monitor unit.
- The codebase is split into two main firmware targets: Controller (root) and Monitor (`monitor/`). Shared code is in `shared/`.
- All commands, logging, and diagnostics are accessible via Telnet, MQTT, and Serial interfaces.
- **HTTP Server**: An optional HTTP web interface is available in the `feature/http-server` branch. Main branch is production-optimized without HTTP.

## Architecture & Key Components
- **Controller**: Main industrial logic, relay control, safety, and sequence management. Source: `src/`, headers: `include/`.
- **Monitor**: Environmental and sensor monitoring, network health, and logging. Source: `monitor/src/`, headers: `monitor/include/`.
- **Shared Logger**: Unified logging in `shared/logger/` (used by both units).
- **Command Processing**: All commands are parsed in `command_processor.cpp` and exposed via Telnet/Serial.
- **Secrets**: WiFi/MQTT credentials in `include/arduino_secrets.h` (not in repo; copy from `.template`).

## Build & Development Workflow
- **PlatformIO** is the primary build system. Use VS Code tasks or these commands:
  - Build Controller: `pio run` (root)
  - Build Monitor: `cd monitor && pio run`
  - Upload: `pio run --target upload` (in respective dir)
  - Serial Monitor: `pio device monitor` (in respective dir)
- **Makefile** provides unified shortcuts (e.g., `make build-all`, `make upload-controller`).
- **Secrets Setup**: Copy `include/arduino_secrets.h.template` to `include/arduino_secrets.h` (and same for `monitor/include/`).

## Command Interface & Patterns
- **Unified Command Set**: Both units support commands like `help`, `show`, `status`, `network`, `loglevel`, `test sensors`, `syslog status`, `reset system`.
- **Controller-Specific**: `relay R1 ON`, `sequence start`, `set <param> <value>` (see `COMMANDS.md`).
- **Monitor-Specific**: `weight status`, `temp status`, `set debug on`, `heartbeat on/off`, `heartbeat rate 72`.
- **Telnet Access**: Both units provide full command interface via telnet on port 23.
- **MQTT Control**: Commands can be sent via MQTT topics for remote operation.
- **Logging**: All debug output is sent to syslog (UDP, RFC 3164, see `set syslog <ip>`). No local debug output by default.
- **Safety**: All relay operations are safety-monitored; see `COMMANDS.md` for error handling and safety feedback.

## Project Conventions
- **No secrets in repo**: Never commit `arduino_secrets.h`.
- **All new commands** must be documented in `COMMANDS.md` (Controller) or `MONITOR_README.md` (Monitor).
- **Logging**: Use the shared logger for all debug/info/error output.
- **Testing**: Use Telnet/Serial to run `test` commands for diagnostics.
- **Documentation**: Key docs in `README.md`, `docs/UNIFIED_ARCHITECTURE.md`, and `docs/DEPLOYMENT_GUIDE.md`.

## 🔒 FROZEN PRODUCTION SCRIPTS (DO NOT EDIT)
**The following scripts are validated, in production, and frozen. DO NOT modify without explicit user authorization.**

### Protobuf Telemetry Pipeline (Validated Nov 5, 2025)
- **`utils/protobuf_database_logger.py`** - Production service ingesting protobuf messages to SQLite
  - Service: `logsplitter-protobuf-logger.service`
  - Status: OPERATIONAL - 7,821+ messages validated
  - Features: 8 message types (0x10-0x17), corruption filtering, real-time ingestion
  - Database: `utils/logsplitter_data.db`
  
- **`utils/mqtt_protobuf_decoder.py`** - Core protobuf decoder library
  - Status: VALIDATED - All 8 message types decoding correctly
  - Wire format: [size][type][seq][timestamp_4B][payload]
  - Message handlers: DIGITAL_INPUT, DIGITAL_OUTPUT, RELAY_EVENT, PRESSURE, SYSTEM_ERROR, SAFETY_EVENT, SYSTEM_STATUS, SEQUENCE_EVENT
  
- **`utils/show_telemetry_status.py`** - Telemetry monitoring dashboard script
  - Status: VALIDATED - Correct age calculations, UTC timezone handling
  - Features: Last value display, age formatting, verbose/detailed modes
  - Usage: `./show_telemetry_status.py [-v] [-d] [--db path] [-t type]`

### Validation Evidence
- E-Stop event capture confirmed (2025-11-05 17:21:57 - 17:22:04)
- Zero database corruption (all messages 0x10-0x17)
- Pressure sensor A15 operational (0-3000 PSI range)
- 2,605+ digital inputs, 1,340+ relay events, 2,546+ sequence events captured
- Real-time latency: <5 seconds

**⚠️ CRITICAL**: Any modifications to these scripts require:
1. User explicit approval
2. Service shutdown: `sudo systemctl stop logsplitter-protobuf-logger.service`
3. Database backup: `cp utils/logsplitter_data.db utils/logsplitter_data.db.backup`
4. Full validation testing before service restart

### Monitor Sensor Pipeline (Validated Nov 5, 2025)
- **`utils/monitor_database_logger.py`** - Production service ingesting monitor sensor data to SQLite
  - Service: `logsplitter-monitor-logger.service`
  - Status: OPERATIONAL - 277+ messages validated
  - Features: Temperature, fuel, weight, voltage, ADC, system status
  - Database: `utils/monitor_data.db`
  - Topics: `monitor/temperature/*`, `monitor/fuel/gallons`, `monitor/weight/*`, `monitor/adc/*`, `monitor/memory`, `monitor/uptime`
  
- **`utils/show_monitor_status.py`** - Monitor sensor dashboard script
  - Status: VALIDATED - Real-time sensor display, age calculations
  - Features: Sensor readings, weight data, digital I/O, system status
  - Usage: `./show_monitor_status.py [-v] [--db path]`

### Monitor Validation Evidence
- Fuel level capture confirmed: 2.95 gallons
- Temperature sensors operational: Local (118.78°F), Remote (129.47°F)
- Weight sensor raw data: 947,993 counts
- ADC readings: Voltage and raw values captured
- System status: Memory usage tracked (21.26 KB free)
- 165+ sensor readings, 22+ weight readings, 90+ system status updates
- Real-time latency: <20 seconds

**⚠️ CRITICAL**: Any modifications to monitor scripts require:
1. User explicit approval
2. Service shutdown: `sudo systemctl stop logsplitter-monitor-logger.service`
3. Database backup: `cp utils/monitor_data.db utils/monitor_data.db.backup`
4. Full validation testing before service restart

## Integration & External Dependencies
- **MQTT**: Used for remote monitoring and control.
- **Syslog**: All logs sent to a central syslog server (configurable).
- **Sensors**: INA219, MCP3421, NAU7802, MCP9600, MAX6656, TCA9548A (see `include/` and `monitor/include/`).

## Examples
- Build and upload Controller:
  ```bash
  pio run --target upload
  ```
- Set syslog server:
  ```
  set syslog 192.168.1.238
  syslog server set to 192.168.1.238:514
  ```
- Safety-monitored relay control:
  ```
  relay R1 ON
  manual extend started (safety-monitored)
  ```

## References
- [README.md](../README.md)
- [COMMANDS.md](../COMMANDS.md)
- [MONITOR_README.md](../MONITOR_README.md)
- [docs/UNIFIED_ARCHITECTURE.md](../docs/UNIFIED_ARCHITECTURE.md)
- [Makefile](../Makefile)

---
**Keep these instructions up to date as project structure or conventions evolve.**
