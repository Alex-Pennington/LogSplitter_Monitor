#!/usr/bin/env python3
"""
Setup script for LogSplitter InfluxDB Collector
Installs dependencies and creates initial configuration
"""

import json
import os
import subprocess
import sys
from pathlib import Path

def install_requirements():
    """Install Python dependencies"""
    print("Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_config():
    """Create configuration file from template"""
    config_file = Path("config.json")
    template_file = Path("config.json.template")
    
    if config_file.exists():
        print("⚠️  config.json already exists, skipping creation")
        return True
        
    if not template_file.exists():
        print("❌ config.json.template not found")
        return False
    
    try:
        # Copy template to config
        with open(template_file, 'r') as f:
            config = json.load(f)
        
        # Get user input for configuration
        print("\n=== LogSplitter InfluxDB Collector Setup ===")
        
        # MQTT Configuration
        print("\n--- MQTT Broker Configuration ---")
        mqtt_host = input(f"MQTT Host [{config['mqtt']['host']}]: ").strip()
        if mqtt_host:
            config['mqtt']['host'] = mqtt_host
            
        mqtt_port = input(f"MQTT Port [{config['mqtt']['port']}]: ").strip()
        if mqtt_port:
            config['mqtt']['port'] = int(mqtt_port)
            
        mqtt_user = input("MQTT Username (optional): ").strip()
        if mqtt_user:
            config['mqtt']['username'] = mqtt_user
            mqtt_pass = input("MQTT Password (optional): ").strip()
            config['mqtt']['password'] = mqtt_pass
        
        # InfluxDB Configuration  
        print("\n--- InfluxDB v2 Configuration ---")
        influx_url = input(f"InfluxDB URL [{config['influxdb']['url']}]: ").strip()
        if influx_url:
            config['influxdb']['url'] = influx_url
            
        influx_token = input("InfluxDB Token: ").strip()
        if influx_token:
            config['influxdb']['token'] = influx_token
        else:
            print("⚠️  Warning: InfluxDB token is required for operation")
            
        influx_org = input("InfluxDB Organization: ").strip()
        if influx_org:
            config['influxdb']['org'] = influx_org
        else:
            print("⚠️  Warning: InfluxDB organization is required")
            
        influx_bucket = input(f"InfluxDB Bucket [{config['influxdb']['bucket']}]: ").strip()
        if influx_bucket:
            config['influxdb']['bucket'] = influx_bucket
        
        # Logging
        print("\n--- Logging Configuration ---")
        log_level = input(f"Log Level (DEBUG/INFO/WARNING/ERROR) [{config['log_level']}]: ").strip().upper()
        if log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            config['log_level'] = log_level
        
        # Write configuration
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
        print(f"✅ Configuration saved to {config_file}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create configuration: {e}")
        return False

def create_systemd_service():
    """Create systemd service file (Linux only)"""
    if sys.platform != 'linux':
        return True
        
    script_dir = Path(__file__).parent.absolute()
    service_content = f"""[Unit]
Description=LogSplitter InfluxDB Collector
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory={script_dir}
ExecStart={sys.executable} {script_dir}/logsplitter_influx_collector.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    try:
        service_file = Path("/tmp/logsplitter-collector.service")
        with open(service_file, 'w') as f:
            f.write(service_content)
            
        print(f"✅ Systemd service file created at {service_file}")
        print(f"   To install: sudo cp {service_file} /etc/systemd/system/")
        print(f"   To enable: sudo systemctl enable logsplitter-collector")
        print(f"   To start: sudo systemctl start logsplitter-collector")
        return True
        
    except Exception as e:
        print(f"⚠️  Could not create systemd service: {e}")
        return True  # Not critical

def main():
    """Setup main function"""
    print("LogSplitter InfluxDB Collector Setup")
    print("====================================")
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    # Install dependencies
    if not install_requirements():
        sys.exit(1)
    
    # Create configuration
    if not create_config():
        sys.exit(1)
    
    # Create systemd service (Linux only)
    create_systemd_service()
    
    print("\n🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Edit config.json if needed")
    print("2. Ensure InfluxDB v2 is running and accessible")
    print("3. Ensure MQTT broker is running")
    print("4. Run: python logsplitter_influx_collector.py")
    print("\nThe collector will create the following measurements in InfluxDB:")
    print("- controller_log: Raw log messages from controller")
    print("- controller_pressure: Pressure sensor readings")
    print("- controller_sequence: Sequence state changes")
    print("- controller_relay: Relay state changes")
    print("- controller_input: Input pin states")
    print("- controller_system: System status messages")
    print("- monitor_temperature: Temperature sensor readings")
    print("- monitor_weight: Weight sensor readings")
    print("- monitor_power: Power monitoring data")
    print("- monitor_input: Monitor input states")
    print("- monitor_bridge: Serial bridge status")
    print("- monitor_system: System metrics and status")

if __name__ == "__main__":
    main()