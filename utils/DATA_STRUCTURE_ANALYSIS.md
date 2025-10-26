# LogSplitter InfluxDB Data Structure Analysis

## Current Data Structure (8 Measurements Found)

### 🎛️ Controller Data

#### 1. `controller_log` 
- **Fields**: `message`, `count`
- **Tags**: `level` (crit, debug, info, warn, error, unknown, unstructured)
- **Sample Data**:
  ```
  message = "531656|E-STOP ACTIVATED - Emergency shutdown initiated" (level=crit)
  message = "294046|SAFETY: Engine stopped via relay R8" (level=crit)  
  message = "900281|Safety: estop=true engine=false active=true" (level=info)
  message = "960009|Subsystem timing issues detected - generating report" (level=warn)
  message = "985626|Pressure normalized: 293.0 PSI below threshold" (level=debug)
  ```

#### 2. `controller_pressure`
- **Fields**: `psi` 
- **Tags**: `sensor` (A1, A5)
- **Sample Data**:
  ```
  psi = 652.0 (sensor=A1)   # Main hydraulic pressure
  psi = 164.1 (sensor=A5)   # Filter pressure
  ```

#### 3. `controller_sequence`
- **Fields**: `active` (always 1 when logging)
- **Tags**: `state` (transition descriptions)
- **Sample Data**:
  ```
  active = 1 (state=EXTENDING->WAIT_EXTEND_LIMIT)
  active = 1 (state=IDLE->START_WAIT)
  active = 1 (state=RETRACTING->IDLE)
  active = 1 (state=WAIT_RETRACT_LIMIT->IDLE)
  ```

#### 4. `controller_system`
- **Fields**: `active`, `status`
- **Sample Data**:
  ```
  active = 1
  status = "System: uptime=3630s state=IDLE"
  ```

### 📊 Monitor Data

#### 5. `monitor_power`
- **Fields**: `status`, `current`, `voltage`, `power`
- **Tags**: `metric` (current, voltage, watts)
- **Sample Data**:
  ```
  status = "ready: YES, voltage: 14.336V, current: -61.00mA, power: 0.00mW"
  current = -61.0 (metric=current)
  voltage = 14.336 (metric=voltage)  
  power = 0.0 (metric=watts)
  ```

#### 6. `monitor_system`
- **Fields**: `message`, `value`
- **Tags**: `metric` (heartbeat, memory, uptime)
- **Sample Data**:
  ```
  message = "uptime=7146 state=2" (metric=heartbeat)
  value = 21768.0 (metric=memory)
  value = 7136.0 (metric=uptime)
  ```

#### 7. `monitor_temperature`
- **Fields**: `fahrenheit`
- **Tags**: `sensor` (local, remote)
- **Sample Data**:
  ```
  fahrenheit = 65.68 (sensor=local)    # Ambient/local temp
  fahrenheit = 120.09 (sensor=remote)  # Thermocouple/remote temp
  ```

#### 8. `monitor_weight`
- **Fields**: `pounds`, `status`
- **Tags**: `type` (filtered, raw, status)
- **Sample Data**:
  ```
  pounds = 24325.086 (type=filtered)  # Filtered weight reading
  pounds = 1656116.0 (type=raw)       # Raw ADC reading
  status = "status: OK, ready: NO, weight: 24328.602, raw: 1656116" (type=status)
  ```

## 🎯 Key Findings for Dashboard Creation

### ✅ What's Working Well
1. **Pressure Data** - Clean numeric values with sensor tags
2. **Temperature Data** - Good local/remote separation  
3. **Weight Data** - Multiple data types (filtered, raw, status)
4. **Power Monitoring** - Voltage, current, power metrics
5. **Sequence States** - Good transition tracking

### ⚠️ What Needs Parsing (Status Messages)

#### Critical Safety Data in Log Messages:
```
"E-STOP ACTIVATED - Emergency shutdown initiated" → needs estop_active=true
"SAFETY: Engine stopped via relay R8" → needs engine_running=false  
"Safety: estop=true engine=false active=true" → needs separate boolean fields
"System: uptime=3630s state=IDLE" → needs uptime_seconds=3630, state="IDLE"
```

#### Monitor Status Parsing Needed:
```
"uptime=7146 state=2" → needs uptime=7146, monitor_state=2
"ready: YES, voltage: 14.336V, current: -61.00mA" → already parsed well
"status: OK, ready: NO, weight: 24328.602" → weight parsing is good
```

## 📊 Recommended Dashboard Structure

### Dashboard 1: 🚨 **Safety & Alerts** (HIGH PRIORITY)
```flux
# Current E-Stop Status (parse from logs)
from(bucket: "mqtt") 
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "controller_log")
  |> filter(fn: (r) => r._field == "message") 
  |> filter(fn: (r) => r._value =~ /E-STOP ACTIVATED/)
  |> count()

# Current Engine Status (parse from logs)  
from(bucket: "mqtt")
  |> range(start: -5m) 
  |> filter(fn: (r) => r._measurement == "controller_log")
  |> filter(fn: (r) => r._field == "message")
  |> filter(fn: (r) => r._value =~ /Engine stopped/)
  |> count()

# Pressure Safety
from(bucket: "mqtt")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "controller_pressure")
  |> filter(fn: (r) => r._field == "psi")
```

### Dashboard 2: 🎛️ **System Overview**
```flux
# System Status
from(bucket: "mqtt") 
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "controller_system")
  |> filter(fn: (r) => r._field == "active")
  |> last()

# Current Sequence State  
from(bucket: "mqtt")
  |> range(start: -1h) 
  |> filter(fn: (r) => r._measurement == "controller_sequence")
  |> filter(fn: (r) => r._field == "active")
  |> last()

# Latest Pressure Readings
from(bucket: "mqtt")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "controller_pressure") 
  |> filter(fn: (r) => r._field == "psi")
  |> last()
```

### Dashboard 3: 📊 **Monitor Data**
```flux
# Temperature Monitoring
from(bucket: "mqtt")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "monitor_temperature")
  |> filter(fn: (r) => r._field == "fahrenheit")

# Weight Monitoring  
from(bucket: "mqtt")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "monitor_weight")
  |> filter(fn: (r) => r._field == "pounds")
  |> filter(fn: (r) => r.type == "filtered")

# Power Monitoring
from(bucket: "mqtt") 
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "monitor_power")
  |> filter(fn: (r) => r._field == "voltage" or r._field == "current")
```

## 🚀 Next Steps

1. **IMMEDIATE**: Create dashboards with current data structure
2. **SHORT-TERM**: Implement status message parsing in collector  
3. **LONG-TERM**: Add parsed boolean fields for cleaner dashboard queries

The current data is sufficient for functional dashboards, but parsing will make them much cleaner and more reliable.