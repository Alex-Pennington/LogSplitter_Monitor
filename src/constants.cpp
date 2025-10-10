#include "constants.h"

// Command validation arrays
const char* const ALLOWED_COMMANDS[] = {
    "help", "show", "status", "set", "debug", "network", "reset", "test", "syslog", "monitor", "weight", "temp", "temperature", "power", "adc", "lcd", "loglevel", "i2c", nullptr
};

const char* const ALLOWED_SET_PARAMS[] = {
    "debug", "syslog", "mqtt_broker", "wifi_ssid", "loglevel", "interval", "heartbeat", "threshold", "calibration", nullptr
};