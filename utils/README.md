# LogSplitter InfluxDB Collector

This utility collects MQTT telemetry data from the LogSplitter Monitor and Controller systems and stores it in InfluxDB v2 for time-series analysis, monitoring, and dashboard creation.

## Features

- **Comprehensive MQTT Collection**: Subscribes to all LogSplitter MQTT topics
- **Intelligent Data Parsing**: Automatically parses and structures different message types
- **InfluxDB v2 Integration**: Stores data with proper measurements, tags, and fields
- **Real-time Statistics**: Tracks collection rates and errors
- **Robust Error Handling**: Continues operation despite individual message failures
- **Configurable Logging**: Debug, info, warning, and error levels

## Installation

1. **Install Python Dependencies**:
   ```bash
   cd utils
   python -m pip install -r requirements.txt
   ```

2. **Run Setup Script** (recommended):
   ```bash
   python setup.py
   ```
   
   Or manually create configuration:
   ```bash
   cp config.json.template config.json
   # Edit config.json with your settings
   ```

## Configuration

Edit `config.json` to match your environment:

```json
{
  "mqtt": {
    "host": "192.168.1.100",
    "port": 1883,
    "keepalive": 60,
    "username": "",
    "password": ""
  },
  "influxdb": {
    "url": "http://localhost:8086",
    "token": "your-influxdb-v2-token-here",
    "org": "your-organization", 
    "bucket": "logsplitter"
  },
  "log_level": "INFO"
}
```

### InfluxDB v2 Setup

1. **Install InfluxDB v2**: Download from https://portal.influxdata.com/downloads/
2. **Create Organization**: Set up your organization in InfluxDB UI
3. **Create Bucket**: Create a bucket named "logsplitter" (or customize in config)
4. **Generate Token**: Create a token with write permissions to your bucket
5. **Update Config**: Add token, org, and bucket to config.json

## Usage

### Run Manually
```bash
python logsplitter_influx_collector.py
```

### Run as Service (Linux)
```bash
# Setup creates the service file
sudo cp /tmp/logsplitter-collector.service /etc/systemd/system/
sudo systemctl enable logsplitter-collector
sudo systemctl start logsplitter-collector

# Check status
sudo systemctl status logsplitter-collector

# View logs
sudo journalctl -u logsplitter-collector -f
```

### Windows Service
Use `nssm` or similar to run as Windows service:
```cmd
nssm install LogSplitterCollector "C:\Python39\python.exe" "C:\path\to\logsplitter_influx_collector.py"
nssm start LogSplitterCollector
```

## Data Structure

The collector creates the following measurements in InfluxDB:

### Controller Data

#### `controller_log`
Raw log messages from the controller
- **Tags**: `level` (emerg, alert, crit, error, warn, notice, info, debug)
- **Fields**: `message` (string), `count` (integer)

#### `controller_pressure`  
Pressure sensor readings
- **Tags**: `sensor` (A1, A5)
- **Fields**: `psi` (float)

#### `controller_sequence`
Sequence state changes
- **Tags**: `state` (idle, extend_start, extending, etc.)
- **Fields**: `active` (integer, 1=active)

#### `controller_relay`
Relay state changes
- **Tags**: `relay` (R1, R2), `state` (ON, OFF)
- **Fields**: `active` (integer, 1=on, 0=off)

#### `controller_input`
Input pin states
- **Tags**: `pin` (pin6, pin12)
- **Fields**: `state` (integer, 0 or 1)

#### `controller_system`
System status messages
- **Fields**: `status` (string), `active` (integer)

### Monitor Data

#### `monitor_temperature`
Temperature sensor readings
- **Tags**: `sensor` (local, remote)
- **Fields**: `fahrenheit` (float)

#### `monitor_weight`
Weight sensor readings
- **Tags**: `type` (filtered, raw, status)
- **Fields**: `pounds` (float), `status` (string)

#### `monitor_power`
Power monitoring data
- **Tags**: `metric` (voltage, current, watts, status)
- **Fields**: `voltage` (float), `current` (float), `power` (float), `status` (string)

#### `monitor_input`
Digital input states
- **Tags**: `pin` (pin number)
- **Fields**: `state` (integer, 0 or 1)

#### `monitor_bridge`
Serial bridge status
- **Fields**: `status` (string)

#### `monitor_system`
System metrics and status
- **Tags**: `metric` (status, heartbeat, uptime, memory, error)
- **Fields**: `value` (float), `message` (string)

## MQTT Topic Mapping

The collector automatically maps MQTT topics to InfluxDB measurements:

```
controller/raw/debug          → controller_log (level=debug)
controller/pressure/a1        → controller_pressure (sensor=A1)
controller/sequence/state     → controller_sequence
controller/relay/r1           → controller_relay (relay=R1)
controller/input/pin6         → controller_input (pin=pin6)
controller/system/status      → controller_system

monitor/temperature/local     → monitor_temperature (sensor=local)
monitor/weight                → monitor_weight (type=filtered)
monitor/weight/raw            → monitor_weight (type=raw)
monitor/power/voltage         → monitor_power (metric=voltage)
monitor/input/2               → monitor_input (pin=2)
monitor/bridge/status         → monitor_bridge
monitor/status                → monitor_system (metric=status)
```

## Grafana Integration

Once data is flowing into InfluxDB, you can create Grafana dashboards:

### Example Flux Queries

**Controller Pressure Over Time**:
```flux
from(bucket: "logsplitter")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "controller_pressure")
  |> filter(fn: (r) => r._field == "psi")
```

**Monitor Temperature Trends**:
```flux
from(bucket: "logsplitter")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "monitor_temperature")
  |> filter(fn: (r) => r._field == "fahrenheit")
```

**System Activity Overview**:
```flux
from(bucket: "logsplitter")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "controller_sequence")
  |> filter(fn: (r) => r._field == "active")
  |> aggregateWindow(every: 1m, fn: sum)
```

## Monitoring

The collector provides real-time statistics:

```
=== LogSplitter InfluxDB Collector Stats ===
Uptime: 0:15:23.456789
Messages received: 1247
Messages written: 1195
Errors: 2
Rate: 1.3 msg/sec
```

### Health Checks

Monitor the collector with these checks:

1. **MQTT Connection**: Check for "Connected to MQTT broker" log messages
2. **InfluxDB Connection**: Check for "InfluxDB connection established" messages  
3. **Message Flow**: Verify `messages_received` is increasing
4. **Error Rate**: Monitor `errors` count and log ERROR messages
5. **Write Rate**: Ensure `messages_written` tracks with received messages

## Troubleshooting

### Common Issues

**Connection Errors**:
- Verify MQTT broker is accessible and credentials are correct
- Check InfluxDB URL, token, org, and bucket settings
- Ensure network connectivity between collector and services

**No Data in InfluxDB**:
- Check MQTT topics are publishing data
- Verify collector is subscribed to correct topics
- Enable DEBUG logging to see message processing details

**High Error Rate**:
- Check InfluxDB write permissions and bucket existence
- Verify MQTT message formats match expected patterns
- Review ERROR log messages for specific issues

### Debug Mode

Enable debug logging for detailed information:
```json
{
  "log_level": "DEBUG"
}
```

This shows every MQTT message received and InfluxDB point written.

## Performance

The collector is designed for continuous operation with:

- **Memory Efficient**: Processes messages without accumulating data
- **Network Resilient**: Handles MQTT and InfluxDB disconnections gracefully  
- **Error Tolerant**: Individual message failures don't stop collection
- **Scalable**: Can handle high-frequency telemetry data

Expected performance:
- **Message Rate**: 100+ messages/second
- **Memory Usage**: <50MB steady state
- **CPU Usage**: <5% on Raspberry Pi 4

## Files

- `logsplitter_influx_collector.py` - Main collector program
- `setup.py` - Interactive setup and installation script
- `config.json.template` - Configuration template
- `requirements.txt` - Python dependencies
- `README.md` - This documentation

## License

This utility is part of the LogSplitter Monitor project.