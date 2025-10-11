# Copilot Coding Agent Instructions for LogSplitter_Monitor

## Project Overview
- **LogSplitter_Monitor** is a unified industrial control and monitoring system for Arduino UNO R4 WiFi, managing both a Controller and a Monitor unit.
- The codebase is split into two main firmware targets: Controller (root) and Monitor (`monitor/`). Shared code is in `shared/`.
- All commands, logging, and diagnostics are accessible via Telnet, MQTT, and Serial interfaces.

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
- **Monitor-Specific**: `weight status`, `temp status`, `set debug on`.
- **HTTP API**: Monitor provides REST API on port 80 with endpoints: `/api/status`, `/api/sensors`, `/api/weight`, `/api/temperature`, `/api/network`, `/api/system`, `/api/command` (POST).
- **Web Dashboard**: Modern responsive web UI at `http://<monitor-ip>` with auto-refresh and interactive controls.
- **Logging**: All debug output is sent to syslog (UDP, RFC 3164, see `set syslog <ip>`). No local debug output by default.
- **Safety**: All relay operations are safety-monitored; see `COMMANDS.md` for error handling and safety feedback.

## Project Conventions
- **No secrets in repo**: Never commit `arduino_secrets.h`.
- **All new commands** must be documented in `COMMANDS.md` (Controller) or `MONITOR_README.md` (Monitor).
- **Logging**: Use the shared logger for all debug/info/error output.
- **Testing**: Use Telnet/Serial to run `test` commands for diagnostics.
- **Documentation**: Key docs in `README.md`, `docs/UNIFIED_ARCHITECTURE.md`, and `docs/DEPLOYMENT_GUIDE.md`.

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
