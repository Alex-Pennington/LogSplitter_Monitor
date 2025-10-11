#pragma once

#include <Arduino.h>
#include "arduino_secrets.h"

// System Constants
const unsigned long WATCHDOG_TIMEOUT_MS = 15000;
const unsigned long MAIN_LOOP_TIMEOUT_MS = 10000;

// Network Constants (broker host/port from arduino_secrets.h)
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 20000;
const unsigned long WIFI_CONNECT_CHECK_INTERVAL_MS = 500;
const unsigned long MQTT_RECONNECT_INTERVAL_MS = 5000;
const unsigned long NETWORK_STABILITY_TIME_MS = 10000;
const uint8_t MAX_CONNECT_RETRIES = 3;
const uint8_t MAX_WIFI_RETRIES = 3;
const uint8_t MAX_MQTT_RETRIES = 3;

// Syslog Constants (hostname, tag, facility from arduino_secrets.h for server/port)
const char* const SYSLOG_HOSTNAME = "LogMonitor";   // Hostname for syslog messages
const char* const SYSLOG_TAG = "logmonitor";        // Application tag for syslog
const int SYSLOG_FACILITY = 16;                     // Local use facility (local0 = 16)
const int SYSLOG_SEVERITY = 6;                      // Info level (0=emergency, 6=info, 7=debug)

// MQTT Topics - Monitor specific
const char TOPIC_MONITOR_STATUS[] PROGMEM = "monitor/status";
const char TOPIC_MONITOR_DATA[] PROGMEM = "monitor/data";
const char TOPIC_MONITOR_CONTROL[] PROGMEM = "monitor/control";
const char TOPIC_MONITOR_CONTROL_RESP[] PROGMEM = "monitor/control/resp";
const char TOPIC_MONITOR_HEARTBEAT[] PROGMEM = "monitor/heartbeat";
const char TOPIC_MONITOR_ERROR[] PROGMEM = "monitor/error";

// Monitor-specific Topics
const char TOPIC_SENSOR_TEMPERATURE[] PROGMEM = "monitor/temperature";
const char TOPIC_SENSOR_HUMIDITY[] PROGMEM = "monitor/humidity";
const char TOPIC_SENSOR_VOLTAGE[] PROGMEM = "monitor/voltage";
const char TOPIC_SYSTEM_UPTIME[] PROGMEM = "monitor/uptime";
const char TOPIC_SYSTEM_MEMORY[] PROGMEM = "monitor/memory";

// NAU7802 Load Cell Topics
const char TOPIC_NAU7802_WEIGHT[] PROGMEM = "monitor/weight";
const char TOPIC_NAU7802_RAW[] PROGMEM = "monitor/weight/raw";
const char TOPIC_NAU7802_STATUS[] PROGMEM = "monitor/weight/status";
const char TOPIC_NAU7802_CALIBRATION[] PROGMEM = "monitor/weight/calibration";

// INA219 Power Sensor Topics
const char TOPIC_INA219_VOLTAGE[] PROGMEM = "monitor/power/voltage";
const char TOPIC_INA219_CURRENT[] PROGMEM = "monitor/power/current";
const char TOPIC_INA219_POWER[] PROGMEM = "monitor/power/watts";
const char TOPIC_INA219_STATUS[] PROGMEM = "monitor/power/status";

// MCP3421 ADC Sensor Topics
const char TOPIC_MCP3421_VOLTAGE[] PROGMEM = "monitor/adc/voltage";
const char TOPIC_MCP3421_RAW[] PROGMEM = "monitor/adc/raw";
const char TOPIC_MCP3421_STATUS[] PROGMEM = "monitor/adc/status";

// Pin Configuration (Monitor-specific)
const uint8_t WATCH_PINS[] = {2, 3, 4, 5, 6, 7, 8, 9};
const size_t WATCH_PIN_COUNT = sizeof(WATCH_PINS) / sizeof(WATCH_PINS[0]);
const unsigned long DEBOUNCE_DELAY_MS = 50;  // Standard debounce for buttons/switches

// Status LED
const uint8_t STATUS_LED_PIN = 13;  // Built-in LED

// NAU7802 Load Cell Sensor (I2C)
const uint8_t NAU7802_SDA_PIN = SDA;     // I2C Data pin (A4 on Uno R4)
const uint8_t NAU7802_SCL_PIN = SCL;     // I2C Clock pin (A5 on Uno R4)
const uint8_t NAU7802_I2C_ADDRESS = 0x2A; // Default NAU7802 I2C address
const unsigned long NAU7802_READ_INTERVAL_MS = 1000;  // Read every 1 second

// INA219 Power Sensor (I2C)
const unsigned long POWER_READ_INTERVAL_MS = 2000;    // Read every 2 seconds

// MCP3421 ADC Sensor (I2C)
const unsigned long ADC_READ_INTERVAL_MS = 1500;      // Read every 1.5 seconds

// Digital I/O
const uint8_t DIGITAL_INPUT_1 = 2;       // Configurable digital input
const uint8_t DIGITAL_INPUT_2 = 3;       // Configurable digital input
const uint8_t DIGITAL_OUTPUT_1 = 4;      // Configurable digital output
const uint8_t DIGITAL_OUTPUT_2 = 5;      // Configurable digital output

// Memory Management
const size_t SHARED_BUFFER_SIZE = 256;
const size_t TOPIC_BUFFER_SIZE = 64;
const size_t COMMAND_BUFFER_SIZE = 80;
const size_t MAX_CMD_LENGTH = 16;

// EEPROM Configuration
const uint32_t CONFIG_MAGIC = 0x4D4F4E49; // 'MONI'
const int CONFIG_EEPROM_ADDR = 0;

// System States
enum SystemState {
    SYS_INITIALIZING,
    SYS_CONNECTING,
    SYS_MONITORING,
    SYS_ERROR,
    SYS_MAINTENANCE
};

// Monitoring intervals
const unsigned long STATUS_PUBLISH_INTERVAL_MS = 10000;  // 10 seconds
const unsigned long HEARTBEAT_INTERVAL_MS = 30000;       // 30 seconds
const unsigned long SENSOR_READ_INTERVAL_MS = 5000;      // 5 seconds

// Command validation
extern const char* const ALLOWED_COMMANDS[];
extern const char* const ALLOWED_SET_PARAMS[];