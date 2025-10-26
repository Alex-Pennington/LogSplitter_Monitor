#!/usr/bin/env python3
"""
LogSplitter Web Dashboard Startup Script
Installs dependencies and starts the web dashboard
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install required Python packages"""
    print("Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def start_dashboard():
    """Start the web dashboard"""
    print("Starting LogSplitter Web Dashboard...")
    try:
        # Run the web collector
        subprocess.run([sys.executable, "web_collector.py"])
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")

def main():
    """Main startup function"""
    print("🚀 LogSplitter Web Dashboard Startup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("requirements.txt"):
        print("❌ Error: requirements.txt not found!")
        print("Please run this script from the utils directory")
        sys.exit(1)
        
    if not os.path.exists("config.json"):
        print("❌ Error: config.json not found!")
        print("Please ensure config.json exists with MQTT and InfluxDB settings")
        sys.exit(1)
        
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies. Exiting.")
        sys.exit(1)
    
    # Start dashboard
    print("\n🌐 Web dashboard will be available at:")
    print("   http://localhost:5000")
    print("   http://192.168.1.155:5000 (if accessible)")
    print("\n📊 The dashboard will show:")
    print("   • Real-time E-Stop, Engine, and System status")
    print("   • Live pressure monitoring with charts") 
    print("   • Fuel volume and temperature readings")
    print("   • System statistics and message rates")
    print("\n⚡ Press Ctrl+C to stop the dashboard")
    print("=" * 50)
    
    start_dashboard()

if __name__ == "__main__":
    main()