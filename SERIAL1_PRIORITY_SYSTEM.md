# Serial1 Bridge Priority System

## Overview
The Serial1 bridge implements a sophisticated priority-based rate limiting system to prevent MQTT network overload while ensuring critical messages always get through.

## Priority Levels

### Priority 4: Critical (Always Published)
- **EMERGENCY** - System unusable
- **ALERT** - Immediate action required  
- **CRITICAL** - Critical conditions
- **ERROR** - Error conditions

**Rate Limiting**: NONE - Always published immediately

### Priority 3: High Priority (WARNING)
- **WARNING** - Warning conditions

**Rate Limiting**: 
- Minimum 50ms between publishes (reduced from 100ms)
- Full burst allowance (5 messages per second)

### Priority 2: Medium Priority (INFO/NOTICE) 
- **INFO** - Informational messages
- **NOTICE** - Normal but significant conditions

**Rate Limiting**:
- Standard 100ms between publishes
- Limited to 3 messages per burst window

### Priority 1: Low Priority (DEBUG)
- **DEBUG** - Debug-level messages
- Unknown/unclassified messages

**Rate Limiting**:
- Standard 100ms between publishes  
- Limited to 1 message per burst window (most restrictive)

## Special Content Priority

### High-Priority Content (Reduced Rate Limiting)
Regardless of log level, these content types get priority:

- **Sequence Data** - Contains "sequence" or "Sequence"
  - Example: "Sequence: IDLE -> EXTEND_START"
- **Pressure Data** - Contains "pressure" or "Pressure:"
  - Example: "Pressure: A1=245.2psi A5=12.1psi"
- **Relay Data** - Contains "relay" or "Relay"  
  - Example: "Relay: R1=ON (Extend valve)"

**Special Rate Limiting**: 25ms between publishes (4x faster than normal)

## Rate Limiting Configuration

```cpp
#define BRIDGE_RATE_LIMIT_MS 100          // Standard rate limit
#define BRIDGE_HIGH_PRIORITY_RATE_MS 25   // High priority content
#define BRIDGE_WARNING_RATE_MS 50         // WARNING messages
#define BRIDGE_MAX_BURST_COUNT 5          // Standard burst limit
#define BRIDGE_DEBUG_BURST_LIMIT 1        // DEBUG burst limit
#define BRIDGE_INFO_BURST_LIMIT 3         // INFO/NOTICE burst limit
#define BRIDGE_BURST_WINDOW_MS 1000       // 1 second burst window
```

## Message Flow Priority

1. **Critical Messages** (EMERG/ALERT/CRIT/ERROR) - Always pass through immediately
2. **High-Priority Content** (Sequence/Pressure/Relay) - Fast lane with 25ms rate limit
3. **WARNING Messages** - Medium priority with 50ms rate limit
4. **INFO/NOTICE Messages** - Standard priority with burst limit of 3
5. **DEBUG Messages** - Lowest priority, only 1 per burst window

## Network Protection

- **Connection Check**: No MQTT publishes if network disconnected
- **Burst Protection**: Prevents overwhelming MQTT broker
- **Drop Statistics**: Tracks messages dropped for monitoring
- **Graceful Degradation**: System remains responsive during message floods

## Telnet Monitoring Commands

```bash
bridge status    # Connection status and message counts
bridge stats     # Detailed statistics including drops
```

## Example Behavior

During high message volume:
1. All EMERGENCY/ALERT/CRITICAL/ERROR messages publish immediately
2. Sequence state changes publish with 25ms delays
3. WARNING messages publish with 50ms delays  
4. INFO messages limited to 3 per second
5. DEBUG messages limited to 1 per second
6. Excess messages are dropped and counted

This ensures critical operational data always reaches MQTT while preventing network congestion from debug floods.