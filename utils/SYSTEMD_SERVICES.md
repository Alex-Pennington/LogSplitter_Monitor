# LogSplitter Systemd Services

This document describes how to set up and manage the LogSplitter monitoring services using systemd.

## Overview

Three systemd services provide complete LogSplitter monitoring:

1. **logsplitter-protobuf-logger** - MQTT message capture and database storage
2. **logsplitter-web-dashboard** - Web interface with analytics (http://127.0.0.1:5000)  
3. **logsplitter-realtime-monitor** - Terminal-based real-time monitoring

## Quick Start

### 1. Install Services
```bash
cd /home/rayvn/monitor/LogSplitter_Monitor/utils
./logsplitter-services.sh install
```

### 2. Enable Auto-Start on Boot
```bash
./logsplitter-services.sh enable
```

### 3. Start All Services
```bash
./logsplitter-services.sh start
```

### 4. Check Service Status
```bash
./logsplitter-services.sh status
```

## Service Management Commands

### Installation & Setup
```bash
# Install service files to systemd
./logsplitter-services.sh install

# Remove service files from systemd  
./logsplitter-services.sh uninstall

# Enable services to start on boot
./logsplitter-services.sh enable

# Disable auto-start on boot
./logsplitter-services.sh disable
```

### Service Control
```bash
# Start all services
./logsplitter-services.sh start

# Stop all services  
./logsplitter-services.sh stop

# Restart all services
./logsplitter-services.sh restart

# Start specific service
./logsplitter-services.sh start logger
./logsplitter-services.sh start dashboard  
./logsplitter-services.sh start monitor

# Stop specific service
./logsplitter-services.sh stop logger
```

### Monitoring & Diagnostics
```bash
# Check status of all services
./logsplitter-services.sh status

# Check specific service status
./logsplitter-services.sh status logger

# View logs for all services
./logsplitter-services.sh logs

# View logs for specific service
./logsplitter-services.sh logs dashboard
```

## Direct systemctl Commands

You can also use standard systemctl commands directly:

```bash
# Start services
sudo systemctl start logsplitter-protobuf-logger
sudo systemctl start logsplitter-web-dashboard
sudo systemctl start logsplitter-realtime-monitor

# Stop services
sudo systemctl stop logsplitter-protobuf-logger
sudo systemctl stop logsplitter-web-dashboard  
sudo systemctl stop logsplitter-realtime-monitor

# Check status
sudo systemctl status logsplitter-protobuf-logger
sudo systemctl status logsplitter-web-dashboard
sudo systemctl status logsplitter-realtime-monitor

# View logs
sudo journalctl -u logsplitter-protobuf-logger -f
sudo journalctl -u logsplitter-web-dashboard -f
sudo journalctl -u logsplitter-realtime-monitor -f
```

## Service Dependencies

Services are configured with proper dependencies:

- **protobuf-logger**: Starts first (base data collection)
- **web-dashboard**: Starts after logger (depends on database)
- **realtime-monitor**: Starts after logger (depends on database)

## Environment Configuration

Services use environment variables from:
- Built-in defaults in service files
- External `.env` file (if present)

Key environment variables:
- `MQTT_BROKER=159.203.138.46`
- `MQTT_PORT=1883`  
- `MQTT_USER=rayven`
- `MQTT_TOPIC=controller/protobuff`
- `DATABASE_PATH=/home/rayvn/monitor/LogSplitter_Monitor/utils/logsplitter_telemetry.db`

## Service Locations

**Service Files:** `/etc/systemd/system/`
- `logsplitter-protobuf-logger.service`
- `logsplitter-web-dashboard.service`
- `logsplitter-realtime-monitor.service`

**Application Files:** `/home/rayvn/monitor/LogSplitter_Monitor/utils/`
- `protobuf_database_logger.py`
- `web_dashboard.py`
- `realtime_monitor.py`

**Management Script:** `/home/rayvn/monitor/LogSplitter_Monitor/utils/logsplitter-services.sh`

## Automatic Restart

All services are configured with `Restart=always` and `RestartSec=10`, meaning:
- Services automatically restart if they crash
- 10-second delay between restart attempts
- Prevents rapid restart loops

## Logging

Service logs are captured by systemd journal:
```bash
# View recent logs
sudo journalctl -u logsplitter-protobuf-logger -n 50

# Follow live logs
sudo journalctl -u logsplitter-web-dashboard -f

# View logs with timestamps
sudo journalctl -u logsplitter-realtime-monitor -o short-iso
```

## Troubleshooting

### Service Won't Start
```bash
# Check service status for error details
sudo systemctl status logsplitter-protobuf-logger

# Check recent logs
sudo journalctl -u logsplitter-protobuf-logger -n 20

# Manually test the application
cd /home/rayvn/monitor/LogSplitter_Monitor/utils
/home/rayvn/monitor/LogSplitter_Monitor/venv/bin/python protobuf_database_logger.py
```

### Permission Issues
```bash
# Ensure files are owned by correct user
sudo chown -R rayvn:rayvn /home/rayvn/monitor/LogSplitter_Monitor/

# Check service file permissions
ls -la /etc/systemd/system/logsplitter-*.service
```

### Database Issues
```bash
# Check database file permissions
ls -la /home/rayvn/monitor/LogSplitter_Monitor/utils/logsplitter_telemetry.db

# Test database connectivity
cd /home/rayvn/monitor/LogSplitter_Monitor/utils
python3 database_analyzer.py stats
```

### Network Issues
```bash
# Test MQTT connectivity
python3 mqtt_protobuf_decoder.py

# Check network status
./logsplitter-services.sh logs logger | grep -i "mqtt\|network\|connect"
```

## Performance Monitoring

Monitor service performance:
```bash
# CPU and memory usage
systemctl status logsplitter-protobuf-logger
systemctl status logsplitter-web-dashboard
systemctl status logsplitter-realtime-monitor

# Detailed process information
ps aux | grep -E "(protobuf_database_logger|web_dashboard|realtime_monitor)"

# Service restart history
sudo journalctl -u logsplitter-protobuf-logger | grep -i "started\|stopped\|restart"
```

## Service Access

Once services are running:

- **Web Dashboard**: http://127.0.0.1:5000
  - Overview tab: System status and metrics
  - Analytics tab: Comprehensive firewood splitter analytics 
  - Real-time tab: Live data updates

- **Database Analyzer**: Command-line analysis tool
  ```bash
  cd /home/rayvn/monitor/LogSplitter_Monitor/utils
  python3 database_analyzer.py stats
  python3 database_analyzer.py live-cycles --follow
  ```

- **Direct Database**: SQLite database file
  ```bash
  sqlite3 /home/rayvn/monitor/LogSplitter_Monitor/utils/logsplitter_telemetry.db
  ```

## Security Considerations

- Services run as user `rayvn` (not root) for security
- Network access limited to MQTT broker connection
- Web dashboard binds to localhost only (127.0.0.1)
- Database file has restricted permissions

## Backup Recommendations

Important files to backup:
- Database: `/home/rayvn/monitor/LogSplitter_Monitor/utils/logsplitter_telemetry.db`
- Configuration: `/home/rayvn/monitor/LogSplitter_Monitor/utils/.env`
- Service files: `/etc/systemd/system/logsplitter-*.service`

---

**Last Updated**: October 2025  
**Version**: 1.0.0