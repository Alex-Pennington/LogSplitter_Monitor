# MQTT Topic Structure Update

## Summary
Removed "r4/" prefix from all MQTT topics for cleaner organization.

## Updated Topic Structure

### Serial1 Bridge Topics (Controller Data)
```
controller/raw/emerg          # Emergency messages
controller/raw/alert          # Alert messages  
controller/raw/crit           # Critical messages
controller/raw/error          # Error messages
controller/raw/warn           # Warning messages
controller/raw/notice         # Notice messages
controller/raw/info           # Info messages
controller/raw/debug          # Debug messages
controller/raw/unstructured   # Unparseable messages

controller/pressure/a1        # A1 sensor pressure data
controller/pressure/a5        # A5 sensor pressure data
controller/sequence/state     # Sequence operation states
controller/relay/r1           # R1 relay state changes
controller/relay/r2           # R2 relay state changes
controller/input/pin6         # Pin 6 input state
controller/input/pin12        # Pin 12 input state (E-Stop)
controller/system/status      # System status messages
```

### Monitor System Topics (Local Data)
```
monitor/status               # System status
monitor/data                 # General data
monitor/control              # Command input
monitor/control/resp         # Command responses
monitor/heartbeat            # Heartbeat messages
monitor/error                # Error messages

monitor/temperature          # Temperature data (backward compatibility)
monitor/temperature/local    # Local temperature
monitor/temperature/remote   # Remote temperature
monitor/voltage              # Voltage monitoring
monitor/uptime               # System uptime
monitor/memory               # Memory usage

monitor/weight               # Weight readings
monitor/weight/raw           # Raw weight data
monitor/weight/status        # Weight sensor status
monitor/weight/calibration   # Calibration data

monitor/power/voltage        # Power voltage
monitor/power/current        # Power current
monitor/power/watts          # Power watts
monitor/power/status         # Power sensor status

monitor/input/{pin}          # Digital input states
monitor/bridge/status        # Serial bridge status
```

## Benefits
- **Cleaner hierarchy** without platform-specific prefixes
- **Shorter topic names** for reduced MQTT overhead
- **Clear separation** between controller and monitor data
- **Consistent structure** across all components

## Migration
- All MQTT subscribers need to update topic subscriptions
- Remove "r4/" prefix from existing topic filters
- Topic structure remains otherwise unchanged