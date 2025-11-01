# LogSplitter Analysis Tools Reference

## 🚀 Quick Start Guide

### 1. Real-Time Monitoring
```bash
# Terminal-based real-time dashboard
python3 realtime_monitor.py

# Live cycle monitoring
python3 database_analyzer.py live-cycles --follow

# Quick stats
python3 database_analyzer.py stats
```

### 2. Operational Analysis
```bash
# Analyze operator signals (last 2 hours)
python3 database_analyzer.py operator-signals --hours 2

# Track basket exchange patterns
python3 database_analyzer.py basket-exchange --hours 1

# Pressure profile analysis
python3 database_analyzer.py pressure-profile --minutes 30
```

### 3. Web Dashboard
```bash
# Start web dashboard (runs on port 5000)
python3 web_dashboard.py

# Access at: http://127.0.0.1:5000
# Three tabs: Overview, Analytics, Real-time
```

### 4. Database Logger (Background)
```bash
# Start database logging (run in separate terminal)
python3 protobuf_database_logger.py
```

## 📊 Analysis Commands

### Database Analyzer Commands
```bash
# Live cycle monitoring with color coding
python3 database_analyzer.py live-cycles --follow

# Operator signal analysis
python3 database_analyzer.py operator-signals --hours 1

# Basket exchange detection
python3 database_analyzer.py basket-exchange --hours 2

# Pressure analysis during cycles
python3 database_analyzer.py pressure-profile --minutes 15

# Custom SQL queries
python3 database_analyzer.py query --sql "SELECT * FROM telemetry WHERE message_type_name='PRESSURE' ORDER BY received_timestamp DESC LIMIT 10"

# Quick operational statistics
python3 database_analyzer.py stats
```

## 🔍 Key Metrics to Watch

### Cycle Operations
- **Sequence Events**: STARTED, COMPLETE, ABORTED (Short Strokes)
- **Success Rate**: Completed vs Short Stroke cycles
- **Cycle Time**: Duration from start to completion
- **Step Progression**: Individual sequence steps

### Operator Signals
- **Manual Controls**: MANUAL_EXTEND, MANUAL_RETRACT
- **Safety Signals**: SAFETY_CLEAR, EMERGENCY_STOP
- **Operator Interface**: SPLITTER_OPERATOR signals
- **Timing Patterns**: Signal frequency and timing

### Pressure Monitoring
- **System Pressure**: Hydraulic system PSI readings
- **Pressure Spikes**: Events >2500 PSI
- **Fault Detection**: Sensor fault conditions
- **Cycle Correlation**: Pressure patterns during cycles

### Basket Exchange Detection
Look for patterns:
1. Operator signals (positioning)
2. Sequence starts (new cycle)
3. Multiple operator interactions
4. Time gaps between cycles

## 🎯 What to Look For During Testing

### Normal Operation Patterns
- **Consistent Cycle Times**: 15-45 seconds typical for full strokes
- **Clean Pressure Profiles**: Smooth rise and fall
- **Minimal Operator Intervention**: High automation ratio
- **No Safety Events**: Clean operation without stops

### Potential Issues to Monitor
- **Pressure Spikes**: >3000 PSI indicates potential problems
- **Excessive Short Strokes**: High short stroke rate may indicate operator hesitation or material issues
- **Irregular Timing**: Inconsistent cycle times
- **Safety Activations**: Emergency stops or limit triggers

### Basket Exchange Signatures
- **Pre-cycle Operator Signals**: Manual positioning
- **Sequence Gaps**: Time between cycles for loading
- **Multiple Manual Signals**: Basket positioning adjustments
- **Consistent Patterns**: Regular exchange intervals

## 💡 Analysis Tips

### Real-Time Monitoring
```bash
# Run in separate terminals for best results:
Terminal 1: python3 realtime_monitor.py
Terminal 2: python3 database_analyzer.py live-cycles --follow
Terminal 3: python3 web_dashboard.py
```

### Historical Analysis
```bash
# After operation session, analyze patterns:
python3 database_analyzer.py operator-signals --hours 4
python3 database_analyzer.py basket-exchange --hours 4
python3 database_analyzer.py pressure-profile --minutes 60
```

### Custom Queries for Specific Analysis
```sql
-- Find all cycles in last hour
SELECT * FROM telemetry WHERE message_type_name='SEQUENCE_EVENT' 
AND received_timestamp > datetime('now', '-1 hour');

-- Pressure readings during specific time
SELECT received_timestamp, payload_json FROM telemetry 
WHERE message_type_name='PRESSURE' 
AND received_timestamp BETWEEN '2025-10-27 14:00:00' AND '2025-10-27 15:00:00';

-- Operator signal frequency
SELECT COUNT(*) as signals, 
       json_extract(payload_json, '$.input_type_name') as signal_type
FROM telemetry 
WHERE message_type_name='DIGITAL_INPUT' 
GROUP BY signal_type;
```

## 🌐 Web Dashboard Features

### Overview Tab
- System statistics
- Message breakdown
- Connection status

### Analytics Tab (NEW!)
- **Cycle Analysis**: Success rates, timing
- **Pressure Analysis**: Profiles and efficiency
- **Safety Analysis**: Event tracking
- **System Health**: Performance metrics
- **Operational Patterns**: Usage trends

### Real-time Tab
- Live message feed
- Activity charts
- Real-time updates

## 📁 File Organization
```
utils/
├── database_analyzer.py     # Comprehensive analysis tool
├── realtime_monitor.py      # Terminal dashboard
├── web_dashboard.py         # Web interface
├── protobuf_database_logger.py  # Data collection
├── mqtt_protobuf_decoder.py # MQTT decoder
├── .env                     # Configuration
└── logsplitter_telemetry.db # SQLite database
```

## 🚨 Emergency Commands
```bash
# Quick system check
python3 database_analyzer.py stats

# Check for recent errors
python3 database_analyzer.py query --sql "SELECT * FROM telemetry WHERE message_type_name='SYSTEM_ERROR' ORDER BY received_timestamp DESC LIMIT 5"

# Monitor pressure in real-time
python3 database_analyzer.py pressure-profile --minutes 5

# Check last operator actions
python3 database_analyzer.py operator-signals --hours 1
```

---

**Ready for splitter testing!** 🪵⚡

Start with `python3 realtime_monitor.py` for live monitoring, then use the specific analysis tools to dive deeper into the operational data as you generate it.