#!/usr/bin/env python3
"""
Test script to validate protobuf integration setup
This script checks if the Arduino code compiles with protobuf support
"""

import subprocess
import sys
import os

def test_compilation():
    """Test Arduino compilation with protobuf support"""
    print("🔧 Testing Arduino protobuf integration compilation...")
    
    try:
        # Change to project directory
        os.chdir("c:/Users/USER/Documents/GitHub/LogSplitter_Monitor")
        
        # Run PlatformIO build check
        result = subprocess.run(
            ["pio", "run", "--target", "clean"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            print("✅ Clean successful")
        else:
            print(f"⚠️ Clean warnings: {result.stderr}")
        
        # Now try build
        result = subprocess.run(
            ["pio", "run"],
            capture_output=True, 
            text=True,
            timeout=300  # 5 minutes max
        )
        
        if result.returncode == 0:
            print("✅ Compilation successful!")
            print("✅ Protobuf integration ready")
            return True
        else:
            print(f"❌ Compilation failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Compilation timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_protobuf_files():
    """Check if protobuf files are in place"""
    print("📋 Checking protobuf integration files...")
    
    files_to_check = [
        "platformio.ini",
        "controller_telemetry.proto", 
        "include/protobuf_decoder.h",
        "src/protobuf_decoder.cpp",
        "include/serial_bridge.h",
        "src/serial_bridge.cpp"
    ]
    
    all_present = True
    for file in files_to_check:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - MISSING")
            all_present = False
    
    return all_present

def main():
    print("🚀 LogSplitter Protobuf Integration Test")
    print("=" * 50)
    
    # Check files first
    if not check_protobuf_files():
        print("❌ Missing required files")
        return False
    
    # Test compilation
    if not test_compilation():
        print("❌ Integration test failed")
        return False
    
    print("✅ Protobuf integration test PASSED")
    print("\n📌 Next steps when back at hardware:")
    print("1. Upload firmware to Arduino Monitor")
    print("2. Verify Controller is sending protobuf on Serial1")
    print("3. Monitor controller/protobuff MQTT topic")
    print("4. Test individual topic decoding")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)