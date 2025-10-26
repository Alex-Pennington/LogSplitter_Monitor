# LogSplitter Web Dashboard

A Flask-based real-time web dashboard integrated with MQTT collection and InfluxDB storage for the LogSplitter industrial control system.

## Features

### 🎛️ **Integrated Architecture**
- **MQTT Collection**: Subscribes to all LogSplitter controller/* and monitor/* topics
- **Smart Parsing**: Converts log messages to structured boolean/numeric fields
- **InfluxDB Storage**: Stores time-series data for historical analysis
- **Real-time Web UI**: Live dashboard with WebSocket updates
- **Fuel Volume Conversion**: Automatic weight-to-gallons conversion (7.2 lbs/gal)

### 📊 **Dashboard Components**
- **System Status Cards**: E-Stop, Engine, Sequence State, Uptime
- **Pressure Gauges**: Interactive Plotly gauges with safety thresholds
- **Fuel Tank Visual**: Animated fuel level with color coding
- **Real-time Charts**: Pressure history, fuel consumption, temperature trends
- **Event Log**: Recent system events and alerts
- **Alert System**: Real-time notifications for critical events

### 🔧 **Technical Features**
- **WebSocket Integration**: Real-time updates via Flask-SocketIO
- **Responsive Design**: Bootstrap 5 with mobile support
- **Interactive Charts**: Plotly.js with zoom, pan, and hover details
- **Safety Monitoring**: E-Stop detection, pressure alerts, engine status
- **Historical Data**: Query InfluxDB for trend analysis
- **Clean UI**: Modern design with status color coding

## Quick Start

### 1. Installation
```bash
# Navigate to utils directory
cd LogSplitter_Monitor/utils

# Install dependencies and start dashboard
python start_dashboard.py
```

### 2. Configuration
The dashboard uses the same `config.json` as the collector:
```json
{
  "mqtt": {
    "host": "192.168.1.155",
    "port": 1883,
    "username": "your_user",
    "password": "your_pass"
  },
  "influxdb": {
    "url": "http://192.168.1.155:8086",
    "token": "your_influx_token",
    "org": "your_org",
    "bucket": "mqtt"
  },
  "web": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false
  }
}
```

### 3. Access Dashboard
- **Main Dashboard**: http://localhost:5000
- **Safety View**: http://localhost:5000/safety  
- **Fuel View**: http://localhost:5000/fuel
- **System View**: http://localhost:5000/system

## Architecture

### Data Flow
```
Arduino Controllers → MQTT Broker → Web Collector → InfluxDB
                                        ↓
                                  Web Dashboard ← WebSocket Updates
```

### Key Components

#### 1. **LogSplitterWebCollector** (`logsplitter_web_collector.py`)
- Combines MQTT collection with Flask web server
- Real-time data caching for instant dashboard updates
- Background MQTT thread with WebSocket emission
- InfluxDB query API for historical data

#### 2. **Dashboard Template** (`templates/dashboard.html`)
- Bootstrap 5 responsive layout
- Plotly.js interactive gauges and charts
- Socket.IO client for real-time updates
- Custom CSS animations and fuel tank visual

#### 3. **Real-time Updates**
- **WebSocket Events**: `status_update`, `alert`, `chart_data`
- **Live Data Cache**: Controller and monitor state tracking
- **Auto-refresh**: Charts update every 5 minutes
- **Alert System**: Toast notifications for critical events

## Dashboard Features

### System Status Cards
- **E-Stop Status**: 🚨 Active detection with animated alerts
- **Engine Status**: 🟢 Running / 🛑 Stopped with color coding  
- **Sequence State**: Current operation (IDLE, EXTENDING, RETRACTING)
- **System Uptime**: Formatted uptime display (hours/minutes)

### Pressure Monitoring
- **Interactive Gauges**: A1 (Main) and A5 (Filter) pressure
- **Safety Thresholds**: Color-coded zones (Normal/Warning/Critical)
- **Real-time Values**: Live PSI readings with decimal precision
- **Historical Charts**: Pressure trends with time selection

### Fuel Management
- **Visual Fuel Tank**: Animated level indicator with color coding
- **Multiple Units**: Gallons (primary), pounds, percentage
- **Consumption Tracking**: Historical fuel usage charts
- **Low Fuel Alerts**: Automatic warnings below 25%

### Temperature Monitoring
- **Dual Sensors**: Local/Ambient and Remote/Engine temperatures
- **Trend Charts**: Temperature history with sensor comparison
- **Safety Ranges**: Normal operating temperature validation

### Event Logging
- **Recent Events**: Live scroll of system messages
- **Alert Levels**: Critical, Warning, Info with color coding
- **Time Stamps**: Precise event timing for troubleshooting
- **Auto-scroll**: Latest events always visible

## API Endpoints

### REST APIs
- `GET /api/status` - Current system status
- `GET /api/pressure/history?hours=6` - Pressure history
- `GET /api/fuel/history?hours=24` - Fuel consumption
- `GET /api/events/recent?hours=2` - Recent events

### WebSocket Events
- **Client → Server**:
  - `request_chart_data` - Request historical chart data
- **Server → Client**:
  - `status_update` - Real-time system status
  - `alert` - Critical system alerts
  - `chart_data` - Historical chart data

## Parsing Intelligence

### Enhanced Message Processing
The collector intelligently parses MQTT messages:

**E-Stop Detection**:
```
"E-STOP ACTIVATED" → controller_estop.active=true
```

**Engine Status**:
```  
"Engine stopped" → controller_engine.running=false
"Engine started" → controller_engine.running=true
```

**System State**:
```
"System: uptime=3630s state=IDLE" → structured fields
```

**Fuel Conversion**:
```
Weight: 3380 lbs → Fuel: 469.4 gallons (÷7.2)
```

**Sequence Transitions**:
```
"EXTENDING->WAIT_EXTEND_LIMIT" → detailed transition tracking
```

## Customization

### Adding New Charts
1. **Create SocketIO Handler**:
```python
@self.socketio.on('request_my_chart')
def handle_my_chart(data):
    chart_data = self._get_my_chart_data(data.get('hours', 1))
    emit('my_chart_data', chart_data)
```

2. **Add Chart Method**:
```python
def _get_my_chart_data(self, hours: int) -> Dict:
    # Query InfluxDB and return Plotly chart data
```

3. **Update Frontend**:
```javascript
socket.emit('request_my_chart', {hours: 6});
socket.on('my_chart_data', function(data) {
    Plotly.newPlot('myChart', data.data, data.layout);
});
```

### Custom Alerts
Add alert conditions in `_update_live_data()`:
```python
if fuel_gallons < 50:  # Low fuel alert
    self._add_alert('warning', 'Low fuel level detected', timestamp)
```

## Performance Notes

- **Memory Usage**: ~50MB for web server + collector
- **Real-time Updates**: <100ms latency via WebSocket
- **Chart Loading**: 1-2 seconds for 24-hour history
- **Concurrent Users**: Supports 10+ simultaneous connections
- **Data Retention**: Limited by InfluxDB retention policy

## Troubleshooting

### Connection Issues
```bash
# Check MQTT connection
telnet 192.168.1.155 1883

# Check InfluxDB connection  
curl http://192.168.1.155:8086/health

# Check web dashboard
curl http://localhost:5000/api/status
```

### Missing Data
1. **No Pressure Data**: Check controller/pressure/* MQTT topics
2. **No Fuel Data**: Verify monitor/weight/* topics  
3. **No Charts**: Confirm InfluxDB contains data for time range
4. **No Real-time Updates**: Check WebSocket connection in browser console

### Performance Issues
- **Slow Charts**: Reduce time range or increase aggregation window
- **High Memory**: Limit alert history and live data cache size
- **Connection Drops**: Increase MQTT keepalive timeout

## Dependencies

```
flask>=2.3.0           # Web framework
flask-socketio>=5.3.0  # Real-time WebSocket support  
plotly>=5.15.0         # Interactive charts
pandas>=1.5.0          # Data manipulation
paho-mqtt>=1.6.0       # MQTT client
influxdb-client>=1.36.0 # InfluxDB v2 client
```

## Security Considerations

- **Network Access**: Dashboard accessible on all interfaces (0.0.0.0)
- **Authentication**: No built-in authentication (secure network recommended)
- **Input Validation**: MQTT message validation prevents injection
- **CORS**: Enabled for development (restrict in production)

---

**Created**: October 2025  
**Platform**: Flask + SocketIO + Plotly  
**Compatibility**: LogSplitter Controller v2.0.0+