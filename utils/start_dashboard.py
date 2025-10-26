#!/usr/bin/env python3
"""
LogSplitter Web Dashboard Setup and Launcher
Installs dependencies and starts the integrated web dashboard with MQTT collection
"""

import subprocess
import sys
import os
from pathlib import Path


def install_requirements():
    """Install required Python packages"""
    print("Installing required Python packages...")
    try:
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        return False


def check_config():
    """Check if config.json exists"""
    if not os.path.exists('config.json'):
        print("❌ config.json not found!")
        print("Please copy config.json.template to config.json and configure your settings.")
        return False
    
    print("✅ Configuration file found")
    return True


def start_web_dashboard():
    """Start the web dashboard"""
    print("\n🚀 Starting LogSplitter Web Dashboard...")
    print("Dashboard will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    
    try:
        from logsplitter_web_collector import main
        main()
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        return False
    
    return True


def main():
    """Main setup and launch function"""
    print("=" * 60)
    print("🔧 LogSplitter Web Dashboard Setup & Launcher")
    print("=" * 60)
    
    # Check current directory
    if not os.path.exists('logsplitter_web_collector.py'):
        print("❌ Please run this script from the utils directory")
        sys.exit(1)
    
    # Install dependencies
    if not install_requirements():
        print("Failed to install dependencies. Please check your Python environment.")
        sys.exit(1)
    
    # Check configuration
    if not check_config():
        sys.exit(1)
    
    # Start the dashboard
    if not start_web_dashboard():
        sys.exit(1)


if __name__ == "__main__":
    main()