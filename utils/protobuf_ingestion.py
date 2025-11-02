#!/usr/bin/env python3
"""
LogSplitter Protobuf Ingestion System
Bare bones MQTT protobuf message collector
"""

import logging
import signal
import sys
import time

import paho.mqtt.client as mqtt

# Configuration
MQTT_BROKER = "192.168.1.155"
MQTT_PORT = 1883
TOPIC_PROTOBUF = "controller/protobuff"

# Global state
running = True
stats = {
    'messages_received': 0,
    'bytes_received': 0,
    'start_time': time.time()
}

logger = logging.getLogger(__name__)

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False

def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        logger.info(f"✅ Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TOPIC_PROTOBUF)
        logger.info(f"📡 Subscribed to {TOPIC_PROTOBUF}")
    else:
        logger.error(f"❌ Failed to connect to MQTT broker: {rc}")

def on_message(client, userdata, msg):
    """Handle incoming protobuf messages"""
    stats['messages_received'] += 1
    stats['bytes_received'] += len(msg.payload)
    
    logger.info(f"📦 Protobuf #{stats['messages_received']}: {len(msg.payload)} bytes")
    
    # TODO: Parse protobuf when schema is available
    # For now, just log the message reception

def on_disconnect(client, userdata, rc):
    """MQTT disconnect callback"""
    if rc != 0:
        logger.warning("⚠️ Unexpected MQTT disconnection")

def print_stats():
    """Print current statistics"""
    uptime = time.time() - stats['start_time']
    rate = stats['messages_received'] / uptime if uptime > 0 else 0
    
    logger.info("=" * 50)
    logger.info(f"📊 Stats - Uptime: {uptime:.1f}s")
    logger.info(f"📊 Messages: {stats['messages_received']} ({rate:.2f}/sec)")
    logger.info(f"📊 Data: {stats['bytes_received']} bytes")
    logger.info("=" * 50)

def main():
    """Main function"""
    setup_logging()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Starting LogSplitter Protobuf Ingestion System")
    logger.info(f"🎯 Target: {MQTT_BROKER}:{MQTT_PORT} -> {TOPIC_PROTOBUF}")
    
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    try:
        # Connect to MQTT broker
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        # Main loop
        last_stats = time.time()
        while running:
            time.sleep(1)
            
            # Print stats every 30 seconds
            if time.time() - last_stats >= 30:
                print_stats()
                last_stats = time.time()
        
        print_stats()  # Final stats
        
    except Exception as e:
        logger.error(f"💥 Error: {e}")
    
    finally:
        logger.info("🛑 Shutting down...")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()