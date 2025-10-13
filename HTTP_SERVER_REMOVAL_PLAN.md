# HTTP Server Removal Plan

## Overview
This document outlines the plan to remove the HTTP server from the LogSplitter Monitor to free up memory and reduce complexity. The HTTP server functionality is preserved in the `feature/http-server` branch.

## Current State (main branch with HTTP)
- **Branch**: `feature/http-server` (preserved)
- **Memory Usage**: RAM 32.7% (10,700 bytes), Flash 54.4% (142,720 bytes)
- **Features**: Full HTTP server with REST API and web dashboard
- **Status**: Working with temperature validation, I2C health monitoring, round-robin sensor polling

## Target State (main branch without HTTP)
- **Expected Memory Savings**: ~2-3KB RAM, ~10-15KB Flash
- **Retained Features**:
  - ✅ Telnet server (port 23) for command interface
  - ✅ MQTT publishing for remote monitoring
  - ✅ Serial console for debugging
  - ✅ LCD display for local status
  - ✅ LED matrix heartbeat animation
  - ✅ All sensor functionality (NAU7802, MCP9600, INA219, MCP3421)
  - ✅ I2C health monitoring
  - ✅ Temperature validation
  - ✅ Weight calibration
  
- **Removed Features**:
  - ❌ HTTP web dashboard
  - ❌ REST API endpoints
  - ❌ Web-based command terminal
  - ❌ Browser-based monitoring

## Files to Modify

### 1. Delete HTTP Server Files
- **include/http_server.h** - HTTP server class declaration
- **src/http_server.cpp** - HTTP server implementation

### 2. Modify src/main.cpp
**Remove**:
- `#include "http_server.h"`
- `HTTPServer httpServer;` global instance
- HTTP server initialization in `setup()`
- `httpServer.update();` call in `loop()`

**Keep**:
- All sensor initialization
- Network manager (WiFi + MQTT)
- Telnet server
- LCD display
- Monitor system

### 3. Update Documentation
**Files to Update**:
- **MONITOR_README.md**
  - Remove "HTTP Web Interface" section
  - Remove REST API endpoint documentation
  - Keep telnet command documentation
  - Add note about HTTP functionality in feature branch
  
- **.github/copilot-instructions.md**
  - Remove HTTP API references
  - Update with telnet-only access pattern
  
- **docs/UNIFIED_ARCHITECTURE.md**
  - Remove HTTP server from Monitor component list
  - Update network communication patterns

### 4. Constants and Configuration
**include/constants.h**:
- Review for HTTP-specific constants (likely none to remove)
- All MQTT topics, telnet, and network config remain unchanged

## Migration Path for Users

### Before Removal (Current HTTP Access)
```bash
# Web browser access
http://192.168.1.101

# REST API access
curl http://192.168.1.101/api/status
curl http://192.168.1.101/api/sensors
curl -X POST http://192.168.1.101/api/command -d '{"command":"weight tare"}'
```

### After Removal (Telnet + MQTT Only)
```bash
# Telnet access (identical commands)
telnet 192.168.1.101 23
> weight tare
> status
> test sensors

# MQTT monitoring
mosquitto_sub -h 159.203.138.46 -p 1883 -u <user> -P <pass> -t "r4/monitor/#"

# Serial console (always available)
pio device monitor
```

## Implementation Steps

1. ✅ **Create feature branch** - `feature/http-server` (DONE)
2. ✅ **Push current state** - Preserve working HTTP version (DONE)
3. ⏳ **Switch to main branch** - Ready for HTTP removal (DONE)
4. ⏳ **Delete HTTP files** - Remove http_server.h and http_server.cpp
5. ⏳ **Modify main.cpp** - Remove HTTP server integration
6. ⏳ **Update documentation** - Remove HTTP references, note feature branch
7. ⏳ **Build and test** - Verify functionality without HTTP
8. ⏳ **Upload and validate** - Test telnet, MQTT, sensors, LCD, heartbeat
9. ⏳ **Commit as "no-http"** - Document HTTP server removal
10. ⏳ **Push to main** - Update repository with streamlined version

## Testing Checklist

After HTTP removal, verify:
- [ ] Compiles successfully
- [ ] Memory usage reduced (check RAM/Flash percentages)
- [ ] WiFi connects successfully
- [ ] MQTT publishing works (all sensor topics)
- [ ] Telnet server responds on port 23
- [ ] All telnet commands work (status, weight, temp, test, etc.)
- [ ] Serial console shows debug output
- [ ] LCD display updates correctly
- [ ] LED matrix heartbeat animates
- [ ] All sensors read correctly (NAU7802, MCP9600, INA219, MCP3421)
- [ ] I2C health monitoring active
- [ ] Temperature validation working (50-200°F rejection)
- [ ] Weight calibration persists
- [ ] System stable for 60+ minutes

## Rollback Plan

If issues arise:
```bash
# Switch back to HTTP version
git checkout feature/http-server

# Or cherry-pick specific fixes to HTTP branch
git checkout feature/http-server
git cherry-pick <commit-hash>
```

## Benefits of Removal

### Memory Savings
- **RAM**: 2-3KB freed for sensor buffers and stability
- **Flash**: 10-15KB freed for future features

### Complexity Reduction
- **Fewer Network Ports**: Only MQTT (1883) and Telnet (23)
- **Simpler Debugging**: One less service to monitor
- **Faster Boot**: No HTTP server initialization

### Maintained Functionality
- **All monitoring preserved** via MQTT publishing
- **All control preserved** via telnet commands
- **All local display preserved** via LCD and LED matrix
- **All diagnostics preserved** via serial console

## Future Considerations

### When to Use HTTP Branch
- **Development/Testing**: Web dashboard helpful for quick checks
- **Demonstrations**: Browser interface more accessible than telnet
- **Mobile Monitoring**: Web dashboard works on phones/tablets

### When to Use Main (No-HTTP)
- **Production Deployment**: Maximum stability and memory efficiency
- **Integration Projects**: MQTT-only monitoring in larger systems
- **Long-term Operation**: Fewer services = fewer failure points

## Notes

- HTTP server code preserved in `feature/http-server` branch
- Can merge HTTP improvements back to feature branch if needed
- Main branch will be the recommended production version
- Both branches will remain actively maintained
