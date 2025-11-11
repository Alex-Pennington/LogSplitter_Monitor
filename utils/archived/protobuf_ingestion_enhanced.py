#!/usr/bin/env python3
"""
LogSplitter Protobuf Ingestion System (Enhanced)
Ready for protobuf definition integration
"""

import sys
import os
import time
import json
import logging
from datetime import datetime

# Add proto compiled directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'proto', 'compiled'))

import paho.mqtt.client as mqtt

# Protobuf imports will be added once definitions are compiled
# Example imports (will be uncommented after compilation):
# import controller_messages_pb2
# import sensor_data_pb2  
# import system_status_pb2
# import error_messages_pb2

class ProtobufIngestionSystem:
    """Enhanced protobuf message ingestion with schema-based parsing"""
    
    def __init__(self):
        self.message_count = 0
        self.protobuf_enabled = False
        
        # MQTT Configuration
        self.mqtt_host = "159.203.138.46"
        self.mqtt_port = 1883
        self.mqtt_username = "logsplitter"
        self.mqtt_password = "wifipassword"
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Check if protobuf classes are available
        self.check_protobuf_availability()
        
    def check_protobuf_availability(self):
        """Check if protobuf classes have been compiled and are available"""
        try:
            # Try to import generated protobuf classes
            # This will be updated once actual definitions are provided
            proto_dir = os.path.join(os.path.dirname(__file__), '..', 'proto', 'compiled')
            if os.path.exists(proto_dir) and os.listdir(proto_dir):
                self.logger.info("Protobuf compiled classes found")
                self.protobuf_enabled = True
            else:
                self.logger.warning("Protobuf classes not found - raw binary mode")
                self.protobuf_enabled = False
        except ImportError as e:
            self.logger.warning(f"Protobuf import failed: {e}")
            self.protobuf_enabled = False
    
    def parse_protobuf_message(self, raw_data):
        """Parse protobuf message based on message type"""
        if not self.protobuf_enabled:
            return self.parse_raw_binary(raw_data)
        
        try:
            # Message parsing will be implemented once protobuf definitions are available
            # Example structure:
            #
            # # Determine message type (could be from header or message content)
            # message_type = self.determine_message_type(raw_data)
            # 
            # if message_type == 'controller_status':
            #     message = controller_messages_pb2.ControllerStatus()
            #     message.ParseFromString(raw_data)
            #     return self.process_controller_status(message)
            # elif message_type == 'sensor_data':
            #     message = sensor_data_pb2.SensorReading()
            #     message.ParseFromString(raw_data)
            #     return self.process_sensor_data(message)
            # else:
            #     self.logger.warning(f"Unknown message type: {message_type}")
            #     return None
            
            # Placeholder for now
            return {"parsed": False, "raw_length": len(raw_data)}
            
        except Exception as e:
            self.logger.error(f"Protobuf parsing error: {e}")
            return self.parse_raw_binary(raw_data)
    
    def parse_raw_binary(self, raw_data):
        """Fallback raw binary parsing"""
        return {
            "timestamp": datetime.now().isoformat(),
            "raw_data": raw_data.hex() if len(raw_data) < 100 else f"{raw_data[:50].hex()}...",
            "length": len(raw_data),
            "parsed": False
        }
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            client.subscribe("controller/protobuff")
            self.logger.info("Subscribed to controller/protobuff")
        else:
            self.logger.error(f"MQTT connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message callback with protobuf parsing"""
        self.message_count += 1
        
        try:
            # Parse the protobuf message
            parsed_data = self.parse_protobuf_message(msg.payload)
            
            # Log the parsed result
            if parsed_data.get('parsed', False):
                self.logger.info(f"Message {self.message_count}: Parsed protobuf successfully")
                self.logger.debug(f"Parsed data: {json.dumps(parsed_data, indent=2)}")
            else:
                self.logger.info(f"Message {self.message_count}: Raw binary data ({len(msg.payload)} bytes)")
            
            # Store or process the parsed data here
            self.process_parsed_data(parsed_data)
            
        except Exception as e:
            self.logger.error(f"Message processing error: {e}")
    
    def process_parsed_data(self, data):
        """Process parsed protobuf data (placeholder for implementation)"""
        # This will be expanded based on the actual protobuf schema
        # Examples:
        # - Store to database
        # - Forward to other systems
        # - Trigger alerts
        # - Update dashboards
        pass
    
    def run(self):
        """Start the protobuf ingestion system"""
        self.logger.info("Starting LogSplitter Protobuf Ingestion System")
        self.logger.info(f"Protobuf parsing: {'ENABLED' if self.protobuf_enabled else 'DISABLED (raw binary mode)'}")
        
        client = mqtt.Client()
        client.username_pw_set(self.mqtt_username, self.mqtt_password)
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        
        try:
            client.connect(self.mqtt_host, self.mqtt_port, 60)
            client.loop_forever()
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            client.disconnect()
        except Exception as e:
            self.logger.error(f"MQTT error: {e}")

if __name__ == "__main__":
    system = ProtobufIngestionSystem()
    system.run()