# LogSplitter Dashboard Collection - FIXED & UPDATED

## ✅ CORRECTED DASHBOARDS WITH LIVE DATA

All dashboards have been updated with **verified queries** based on your actual InfluxDB data structure. These dashboards now use the correct field names, measurements, and tags found in your live system.

## 🔧 Fixed Dashboard Files

### **Ready-to-Import Dashboards**
1. **grafana_system_overview_fixed.json** - Main system overview
2. **grafana_controller_fixed.json** - Controller operations
3. **grafana_monitor_fixed.json** - Monitor sensors  
4. **grafana_safety_fixed.json** - Safety monitoring
5. **grafana_maintenance_fixed.json** - Maintenance trends

### **Auto-Generated Dashboards** (from verification script)
1. **grafana_logsplitter_system_overview.json**
2. **grafana_logsplitter_controller_dashboard.json**  
3. **grafana_logsplitter_monitor_dashboard.json**
4. **grafana_logsplitter_safety_dashboard.json**
5. **grafana_logsplitter_maintenance_dashboard.json**

## 📊 Dashboard Details

### 1. System Overview Dashboard
**File:** `grafana_system_overview_fixed.json`

**Panels:**
- **Hydraulic System Pressure** - Real pressure from A1 sensor (`controller_pressure` → `psi` → `sensor=A1`)
- **Monitor Temperature** - Local temperature (`monitor_temperature` → `fahrenheit` → `sensor=local`)
- **Sequence Active Status** - Live sequence state (`controller_sequence` → `active`)
- **System Active Status** - Controller health (`controller_system` → `active`)  
- **Current Weight** - Filtered weight reading (`monitor_weight` → `pounds` → `type=filtered`)
- **Power Monitoring** - Voltage, current, power (`monitor_power` → `voltage|current|power`)
- **System Log Activity** - Log trends by severity level (`controller_log` → `count` by `level`)

**Refresh:** 5 seconds | **Time Range:** Last 1 hour

### 2. Controller Operations Dashboard  
**File:** `grafana_controller_fixed.json`

**Panels:**
- **Real-time Pressure Chart** - 30-minute hydraulic pressure history with safety thresholds
- **Current Pressure Gauge** - Live pressure with color-coded safety zones
- **Sequence Status** - Current sequence state (IDLE/ACTIVE)
- **Controller Status** - System online/offline status
- **Controller Log Activity** - Error/warning/critical message trends
- **Sequence State History** - State transitions over time

**Refresh:** 2 seconds | **Time Range:** Last 30 minutes

### 3. Monitor Sensors Dashboard
**File:** `grafana_monitor_fixed.json`

**Panels:**
- **Temperature Trend** - 2-hour local temperature history
- **Weight Trend** - Filtered weight readings over time  
- **Current Weight Gauge** - Live weight with thresholds (8K-15K lbs)
- **Current Temperature** - Live temperature display
- **Monitor Heartbeat Status** - System heartbeat messages
- **Power System Monitoring** - Comprehensive voltage/current/power trends

**Refresh:** 5 seconds | **Time Range:** Last 2 hours

### 4. Safety & Alerts Dashboard
**File:** `grafana_safety_fixed.json`

**Panels:**
- **Sequence Running Status** - Critical safety indicator
- **Pressure Status** - Real-time pressure safety check (2500 PSI threshold)
- **Controller Status** - System health monitoring
- **Pressure Safety Chart** - 10-minute pressure history with danger zones
- **Critical System Alerts** - Error/warning/critical log activity
- **Sequence State Transitions** - Safety-relevant state changes

**Refresh:** 1 second | **Time Range:** Last 30 minutes

### 5. Maintenance & Trends Dashboard
**File:** `grafana_maintenance_fixed.json`

**Panels:**
- **24h Pressure Trends** - Daily pressure averages for maintenance analysis
- **24h Temperature Trends** - Temperature patterns for environmental monitoring
- **7-day Sequence Activity** - Daily operation counts for usage tracking
- **7-day Error Trends** - Daily error patterns for maintenance planning
- **24h Statistics** - Total operations, critical errors, max pressure, avg weight
- **Power Trends** - 24-hour power system analysis

**Refresh:** 30 seconds | **Time Range:** Last 7 days

## 🚀 Import Instructions

### Step 1: Verify Data Source
Ensure your Grafana has an InfluxDB data source configured:
- **Name:** `influxdb-1` (or update UID in dashboard JSON)
- **URL:** `http://192.168.1.155:8086`
- **Database/Bucket:** `mqtt`
- **Query Language:** Flux

### Step 2: Import Dashboards
1. Open Grafana web interface
2. Click **"+"** → **"Import"**
3. Choose **"Upload JSON file"**
4. Select one of the fixed dashboard files
5. Choose your InfluxDB datasource when prompted
6. Click **"Import"**

### Step 3: Verify Data Display
After import, each dashboard should show:
- ✅ Live data from your running splitter
- ✅ Proper pressure readings (600-800 PSI range)
- ✅ Weight readings (~10,600 lbs)
- ✅ Temperature readings (~55°F)
- ✅ Sequence states and system status

## 📊 Real Data Verification

Your current live data shows:
```
📊 controller_pressure: psi=642.3-794.4 PSI (sensor=A1)
📊 monitor_weight: pounds=10608-10656 lbs (type=filtered)  
📊 monitor_temperature: fahrenheit=55.17°F (sensor=local)
📊 controller_sequence: active=1 (state=EXTENDING->WAIT_EXTEND_LIMIT)
📊 controller_system: active=1, status="System: uptime=3630s state=IDLE"
📊 monitor_power: voltage=14.3V, current=-61mA, power=0mW
```

All dashboards use these **exact measurements and field names**.

## 🔧 Troubleshooting

### No Data Showing?
1. **Check Data Source:** Verify InfluxDB connection in Grafana
2. **Check Time Range:** Ensure time range covers recent data
3. **Check Queries:** Verify bucket name is "mqtt"
4. **Check Field Names:** Use verification script to confirm current schema

### Wrong Data Values?
1. **Check Tags:** Ensure sensor tags match (sensor=A1, type=filtered, etc.)
2. **Check Measurements:** Verify measurement names in InfluxDB
3. **Check Time Zones:** Ensure Grafana timezone matches your location

### Performance Issues?
1. **Reduce Refresh Rate:** Change from 1s to 5s or 10s
2. **Adjust Time Range:** Use shorter ranges for real-time panels
3. **Optimize Queries:** Add more specific filters if needed

## 📈 Dashboard Usage Tips

### System Overview (Main Dashboard)
- Use for **general monitoring** and **system health checks**
- Watch pressure gauge for safety (green < 2500 PSI, red > 2800 PSI)
- Monitor sequence active status during operations

### Controller Operations (During Splits)
- Use for **active operation monitoring**  
- Watch real-time pressure during hydraulic cycles
- Monitor sequence state transitions for troubleshooting

### Monitor Sensors (Environmental)
- Use for **environmental monitoring**
- Track weight changes during log handling
- Monitor temperature for equipment health

### Safety & Alerts (Critical Monitoring)
- Use for **safety-critical monitoring**
- 1-second refresh for immediate alerts
- Red indicators require immediate attention

### Maintenance & Trends (Long-term Analysis)
- Use for **maintenance planning**
- Weekly/monthly trend analysis
- Usage statistics and error pattern analysis

## 🎯 Next Steps

1. **Import all 5 dashboards** using the fixed JSON files
2. **Set up dashboard shortcuts** in Grafana favorites
3. **Configure alerting** for critical thresholds
4. **Create dashboard playlists** for monitoring displays
5. **Set up automated screenshots** for reports

---

**Last Updated:** October 25, 2025  
**Data Verified:** ✅ Against live LogSplitter system  
**Dashboards Status:** ✅ All fixed and ready for import