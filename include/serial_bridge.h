#pragma once

#include <Arduino.h>
#include "constants.h"
#include "network_manager.h"
#include "logger.h"
#include "protobuf_decoder.h"

// Serial bridge configuration
#define SERIAL_BRIDGE_BAUD 115200
#define BRIDGE_BUFFER_SIZE 512
#define MAX_MESSAGE_LENGTH 256
#define BRIDGE_TIMEOUT_MS 1000
#define PROTOBUF_MIN_MESSAGE_SIZE 7     // Minimum protobuf message size (1 size + 6 header)
#define PROTOBUF_MAX_MESSAGE_SIZE 33    // Maximum protobuf message size per API

// Rate limiting configuration
#define BRIDGE_RATE_LIMIT_MS 100          // Minimum 100ms between MQTT publishes
#define BRIDGE_MAX_BURST_COUNT 5          // Maximum 5 messages in burst
#define BRIDGE_BURST_WINDOW_MS 1000       // 1 second burst window

// Priority-based rate limiting
#define BRIDGE_HIGH_PRIORITY_RATE_MS 25   // High priority content (sequence/pressure/relay)
#define BRIDGE_WARNING_RATE_MS 50         // WARNING level messages  
#define BRIDGE_DEBUG_BURST_LIMIT 1        // Only 1 DEBUG message per burst
#define BRIDGE_INFO_BURST_LIMIT 3         // Up to 3 INFO messages per burst

// Message parsing states
enum ParseState {
    PARSE_TIMESTAMP,
    PARSE_LEVEL,
    PARSE_CONTENT
};

// Telemetry control states
enum TelemetryState {
    TELEMETRY_ENABLED,
    TELEMETRY_DISABLED,
    TELEMETRY_UNKNOWN
};

class SerialBridge {
public:
    SerialBridge();
    
    void begin();
    void update();
    
    // Configuration
    void setNetworkManager(NetworkManager* network);
    
    // Status
    bool isConnected() const { return bridgeConnected; }
    unsigned long getMessagesReceived() const { return messagesReceived; }
    unsigned long getMessagesForwarded() const { return messagesForwarded; }
    unsigned long getWindowedReceived() const { return windowedReceived; }
    unsigned long getWindowedForwarded() const { return windowedForwarded; }
    unsigned long getLastMessageTime() const { return lastMessageTime; }
    TelemetryState getTelemetryState() const { return telemetryState; }
    
    // Statistics
    void getStatistics(char* buffer, size_t bufferSize);

    /*
     * OPERATION MODE: Binary Pass-Through
     * 
     * This SerialBridge implementation reads size-prefixed binary protobuf messages
     * from Serial1 and forwards them directly to MQTT topic "controller/protobuff"
     * without modification or decoding.
     * 
     * Message Format (per LogSplitter Controller Binary Telemetry API):
     * [SIZE_BYTE][MESSAGE_TYPE][SEQUENCE_ID][TIMESTAMP][PAYLOAD...]
     * 
     * Size range: 7-33 bytes total (including size byte)
     * Baud rate: 115200 (fixed)
     * Protocol: Size-prefixed binary frames
     */
    
private:
    NetworkManager* networkManager;
    ProtobufDecoder protobufDecoder;
    
    // Connection state
    bool bridgeConnected;
    unsigned long lastMessageTime;
    TelemetryState telemetryState;
    
    // Statistics
    unsigned long messagesReceived;
    unsigned long messagesForwarded;
    unsigned long criticalMessages;
    unsigned long parseErrors;
    unsigned long messagesDropped;  // Rate limited messages
    
    // 5-minute windowed statistics
    unsigned long windowedReceived;
    unsigned long windowedForwarded;
    unsigned long windowStartTime;
    static const unsigned long WINDOW_DURATION_MS = 5 * 60 * 1000; // 5 minutes
    
    // Rate limiting
    unsigned long lastPublishTime;
    unsigned long burstStartTime;
    int burstCount;
    
    // Message buffer
    char messageBuffer[BRIDGE_BUFFER_SIZE];
    size_t bufferIndex;
    uint8_t expectedMessageSize;  // Expected size for current message being received
    
    // Message processing
    void processProtobufMessage(uint8_t* data, size_t length);  // NEW: Protobuf handler
    void processMessage(const String& message);                 // LEGACY: Text handler
    void checkAndResetWindow();                                 // Window management
    bool parseStructuredMessage(const String& message, unsigned long& timestamp, 
                               String& level, String& content);
    void handleTelemetryMessage(unsigned long timestamp, const String& level, 
                               const String& content);
    void handleControlMessage(const String& message);
    void handleRawMessage(const String& message);
    
    // Message filtering
    bool shouldForwardMessage(const String& level) const;
    bool isCriticalLevel(const String& level) const;
    bool isInteractiveMessage(const String& message) const;
    bool isTelemetryControlMessage(const String& message) const;
    
    // MQTT publishing
    void publishToMQTT(unsigned long timestamp, const String& level, 
                       const String& content);
    void publishParsedData(const String& content);
    void publishPressureData(const String& content);
    void publishSequenceData(const String& content);
    void publishRelayData(const String& content);
    void publishInputData(const String& content);
    void publishSystemStatus(const String& content);
    
    // Utility functions
    String extractValue(const String& text, const String& prefix, const String& suffix = "");
    void logBridgeActivity(LogLevel level, const char* format, ...);
    
    // Rate limiting
    bool shouldPublishMessage(const String& level);
};

// MQTT Topics for bridge data
#define TOPIC_BRIDGE_RAW_EMERG     "controller/raw/emerg"
#define TOPIC_BRIDGE_RAW_ALERT     "controller/raw/alert"  
#define TOPIC_BRIDGE_RAW_CRIT      "controller/raw/crit"
#define TOPIC_BRIDGE_RAW_ERROR     "controller/raw/error"
#define TOPIC_BRIDGE_RAW_WARN      "controller/raw/warn"
#define TOPIC_BRIDGE_RAW_NOTICE    "controller/raw/notice"
#define TOPIC_BRIDGE_RAW_INFO      "controller/raw/info"
#define TOPIC_BRIDGE_RAW_DEBUG     "controller/raw/debug"

#define TOPIC_BRIDGE_PRESSURE_A1   "controller/pressure/a1"
#define TOPIC_BRIDGE_PRESSURE_A5   "controller/pressure/a5"
#define TOPIC_BRIDGE_SEQUENCE      "controller/sequence/state"
#define TOPIC_BRIDGE_RELAY_R1      "controller/relay/r1"
#define TOPIC_BRIDGE_RELAY_R2      "controller/relay/r2"
#define TOPIC_BRIDGE_INPUT_PIN6    "controller/input/pin6"
#define TOPIC_BRIDGE_INPUT_PIN12   "controller/input/pin12"
#define TOPIC_BRIDGE_SYSTEM        "controller/system/status"
#define TOPIC_BRIDGE_STATUS        "monitor/bridge/status"