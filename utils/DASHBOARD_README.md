# InfluxDB Data Verification & Grafana Dashboard Suite

This directory contains comprehensive tools for verifying InfluxDB data formats and generating specialized Grafana dashboards for the LogSplitter monitoring system.

## 📋 Table of Contents

- [Tools Overview](#tools-overview)
- [Quick Start](#quick-start)
- [Data Verification](#data-verification)
- [Dashboard Collection](#dashboard-collection)
- [Installation & Usage](#installation--usage)
- [Troubleshooting](#troubleshooting)

## 🛠️ Tools Overview

### Data Verification Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| **verify_influx_data.py** | Comprehensive data structure verification and dashboard generation | `python verify_influx_data.py` |
| **quick_verify.py** | Quick data format check and validation | `python quick_verify.py` |

### Grafana Dashboard Collection

| Dashboard | Focus Area | Panels | Refresh Rate |
|-----------|------------|--------|--------------|
| **grafana_system_overview.json** | Complete system status | 8 panels | 5s |
| **grafana_controller_dashboard.json** | Hydraulic control operations | 6 panels | 2s |
| **grafana_monitor_dashboard.json** | Sensor monitoring | 9 panels | 5s |
| **grafana_safety_dashboard.json** | Safety systems monitoring | 6 panels | 1s |
| **grafana_maintenance_dashboard.json** | Maintenance and diagnostics | 9 panels | 30s |

## 🚀 Quick Start

### 1. Verify Your Data
```bash
# Quick check of data structure
python quick_verify.py

# Comprehensive verification with dashboard generation
python verify_influx_data.py
```

### 2. Import Dashboards
1. Open Grafana UI
2. Navigate to **+ → Import**
3. Upload any of the `.json` dashboard files
4. Select datasource: `influxdb-1`
5. Click **Import**

## 🔍 Data Verification

### Expected Data Structure

The verification scripts check for these measurements in InfluxDB:

#### Controller Measurements
- **controller_pressure**: PSI readings from A1/A5 sensors
  - Fields: `psi`
  - Tags: `sensor` (A1, A5)
- **controller_relay**: Hydraulic relay states  
  - Fields: `active` (0/1)
  - Tags: `relay` (R1, R2)
- **controller_sequence**: Operation sequences
  - Fields: `active` (0/1), `state` (IDLE/EXTENDING/RETRACTING/COMPLETE)
- **controller_input**: Safety inputs
  - Fields: `state` (0/1)
  - Tags: `pin` (pin6, pin7, pin12)

#### Monitor Measurements  
- **monitor_temperature**: Temperature readings
  - Fields: `fahrenheit`
  - Tags: `sensor` (local, remote)
- **monitor_weight**: Weight measurements
  - Fields: `pounds`, `raw`
  - Tags: `type` (raw, filtered)
- **monitor_power**: Power monitoring
  - Fields: `voltage`, `current`, `power`
  - Tags: `metric` (voltage, current, power)
- **monitor_input**: Digital inputs
  - Fields: `state` (0/1)
  - Tags: `pin`

### Verification Process

```bash
# Quick verification
python quick_verify.py
```

**Output Example:**
```
🔍 Quick check of bucket: mqtt
--------------------------------------------------
✅ Found 8 active measurements:
  • controller_pressure: 245 records
  • controller_relay: 89 records
  • monitor_temperature: 156 records
  • monitor_weight: 198 records
  
📋 Latest data samples:
  controller_pressure.psi = 2450.5 {'sensor': 'A1'}
  monitor_temperature.fahrenheit = 72.3 {'sensor': 'local'}
```

## 📊 Dashboard Collection

### 1. System Overview Dashboard
**File:** `grafana_system_overview.json`

**Purpose:** Complete system status at a glance

**Key Panels:**
- Hydraulic pressure sensors (A1/A5) with safety thresholds
- Temperature monitoring (local/remote)  
- Hydraulic relay status (extend/retract)
- Safety input status (limit switches, E-stop)
- Current weight gauge with color coding
- Power monitoring trends
- Weight trend analysis
- Current sequence state

**Best For:** Operations monitoring, general system health

### 2. Controller Operations Dashboard  
**File:** `grafana_controller_dashboard.json`

**Purpose:** Detailed hydraulic control system monitoring

**Key Panels:**
- Pressure monitoring with safety thresholds (2500/4000 PSI)
- Hydraulic relay status with real-time feedback
- Safety input monitoring (limit switches, E-stop)
- Sequence activity timeline
- Relay operation timeline
- Current operation state display

**Best For:** Operations staff, hydraulic system diagnostics

### 3. Monitor Sensors Dashboard
**File:** `grafana_monitor_dashboard.json`

**Purpose:** Environmental and precision sensor monitoring

**Key Panels:**
- MCP9600 temperature sensors (local/thermocouple)
- NAU7802 weight monitoring (raw/filtered)
- Current weight gauge
- Current temperature displays
- Digital input status
- INA219 power monitoring
- System uptime and memory
- Data collection activity metrics

**Best For:** Environmental monitoring, sensor calibration

### 4. Safety Systems Dashboard
**File:** `grafana_safety_dashboard.json`

**Purpose:** Critical safety system monitoring (1-second refresh)

**Key Panels:**
- **Emergency Stop Status** (prominent red alert display)
- **Pressure Safety Gauges** with color-coded thresholds
- **Limit Switch Status** (extend/retract positions)
- **Pressure Safety Timeline** (last 30 minutes)
- **Safety Input Events** timeline
- **Hydraulic Relay Activity** safety monitor

**Best For:** Safety personnel, emergency response, compliance

### 5. Maintenance Dashboard
**File:** `grafana_maintenance_dashboard.json`

**Purpose:** Long-term trends and maintenance planning

**Key Panels:**
- System uptime and memory usage
- 24-hour peak pressure tracking
- Operation cycle counts
- MQTT message activity analysis
- Temperature trends (24h averages)
- Pressure trends (24h averages)
- Relay operation frequency
- Weight trends analysis

**Best For:** Maintenance staff, performance analysis, planning

## 💾 Installation & Usage

### Prerequisites
```bash
pip install influxdb-client
```

### Configuration
Ensure your `config.json` contains:
```json
{
  "influxdb": {
    "url": "http://localhost:8086",
    "token": "your-influxdb-token",
    "org": "your-organization", 
    "bucket": "mqtt"
  }
}
```

### Running Verification
```bash
# Basic verification
python quick_verify.py

# Full verification with dashboard generation
python verify_influx_data.py

# Verification only (no dashboard generation)
python verify_influx_data.py --verify-only

# Custom config file
python verify_influx_data.py --config custom_config.json
```

### Dashboard Import Process
1. **Access Grafana:** Navigate to your Grafana instance
2. **Import Dashboard:** Click **+ → Import**
3. **Upload JSON:** Select any dashboard `.json` file
4. **Configure Datasource:** Choose `influxdb-1` as datasource
5. **Customize:** Adjust time ranges, refresh rates as needed

### Datasource Configuration
All dashboards are configured for datasource UID: `influxdb-1`

If your datasource has a different name:
1. Import the dashboard
2. Go to dashboard settings
3. Update datasource references
4. Save the dashboard

## 🔧 Troubleshooting

### Common Issues

#### 1. "No Data" in Panels
```bash
# Check data exists
python quick_verify.py

# Verify time ranges
# Default: -6h for overview, -2h for controller, -4h for monitor
```

#### 2. Wrong Datasource Error  
- Ensure datasource UID is `influxdb-1`
- Or update dashboard JSON before import
- Check InfluxDB connection in Grafana

#### 3. Query Errors
```bash
# Verify bucket name
python verify_influx_data.py

# Check measurement names
# Expected: controller_*, monitor_*
```

#### 4. Missing Measurements
```bash
# Check MQTT collector status
python test_collector.py

# Verify Serial1 bridge operation
# Check controller/monitor MQTT publishing
```

### Data Validation

#### Expected Value Ranges
- **Pressure:** 0-5000 PSI (safety thresholds at 2500/4000)
- **Temperature:** 50-200°F (invalid readings filtered)
- **Weight:** 0-200 lbs (typical range)
- **Relay States:** 0 (OFF) or 1 (ON)
- **Input States:** 0 (OPEN) or 1 (CLOSED)

#### Sample Queries for Testing
```flux
// Check recent controller pressure
from(bucket: "mqtt")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "controller_pressure")
  |> filter(fn: (r) => r._field == "psi")
  |> last()

// Check monitor temperature sensors  
from(bucket: "mqtt")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "monitor_temperature")
  |> filter(fn: (r) => r._field == "fahrenheit")
  |> group(columns: ["sensor"])
  |> last()
```

### Performance Considerations

#### Refresh Rates
- **Safety Dashboard:** 1s (critical monitoring)
- **Controller Dashboard:** 2s (operational monitoring)
- **System Overview:** 5s (general status)
- **Monitor Dashboard:** 5s (sensor data)
- **Maintenance Dashboard:** 30s (trend analysis)

#### Query Optimization
- Use appropriate time ranges for each dashboard
- Group by relevant tags to reduce data volume
- Use `last()` for current status panels
- Use `aggregateWindow()` for trend analysis

## 📈 Dashboard Customization

### Adding New Panels
1. **Edit Dashboard:** Click dashboard title → Edit
2. **Add Panel:** Click "Add panel" 
3. **Configure Query:** Use existing patterns as templates
4. **Set Visualization:** Choose appropriate panel type
5. **Configure Thresholds:** Set safety/warning levels

### Query Patterns
```flux
// Current status (for stat panels)
from(bucket: "mqtt")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "measurement_name")
  |> filter(fn: (r) => r._field == "field_name")
  |> last()

// Trends (for timeseries panels)  
from(bucket: "mqtt")
  |> range(start: -4h)
  |> filter(fn: (r) => r._measurement == "measurement_name")
  |> group(columns: ["tag_name"])

// Aggregated data (for maintenance)
from(bucket: "mqtt")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "measurement_name")
  |> aggregateWindow(every: 1h, fn: mean)
```

### Color Coding Standards
- **Green:** Normal operation, safe values
- **Yellow:** Caution, approaching limits  
- **Orange:** Warning, attention needed
- **Red:** Critical, immediate action required
- **Gray:** Inactive, disabled, or no data
- **Blue:** Information, non-critical status

---

## 📚 Additional Resources

- **InfluxDB Documentation:** [https://docs.influxdata.com/](https://docs.influxdata.com/)
- **Grafana Documentation:** [https://grafana.com/docs/](https://grafana.com/docs/)
- **Flux Query Language:** [https://docs.influxdata.com/flux/](https://docs.influxdata.com/flux/)

**Version:** 1.0.0  
**Last Updated:** October 2025  
**Compatibility:** InfluxDB 2.x, Grafana 9.0+