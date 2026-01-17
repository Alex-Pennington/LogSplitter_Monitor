#pragma once

#include <Arduino.h>
#include <ArduinoMqttClient.h>

// Note: After nanopb installation and proto compilation, include generated headers:
// #include "controller_telemetry.pb.h"

class NetworkManager; // Forward declaration

/**
 * @brief ProtobufDecoder class for decoding LogSplitter Controller telemetry data
 * 
 * This class receives binary protobuf messages from the Controller via Serial1,
 * decodes the structured telemetry data, and republishes to individual MQTT topics.
 * 
 * The Controller sends structured telemetry as protobuf messages containing:
 * - Pressure readings (A1/A5 sensors)
 * - Relay states (R1/R2 hydraulic control)
 * - Digital inputs (limit switches, e-stop)
 * - Sequence status (operation states)
 * - System health (uptime, memory, errors)
 * 
 * Features:
 * - Efficient binary protobuf decoding with nanopb
 * - Individual MQTT topic publishing for each data type
 * - Data validation and error handling
 * - Statistics tracking for monitoring performance
 * - API integration ready for bidirectional communication
 */
class ProtobufDecoder {
private:
    NetworkManager* networkManager;
    
    // Message processing statistics
    uint32_t messagesReceived;
    uint32_t messagesDecoded;
    uint32_t decodingErrors;
    uint32_t publishErrors;
    uint32_t lastSequenceNumber;
    
    // Decoding buffers - sized for Arduino memory constraints
    static const size_t MAX_PROTOBUF_SIZE = 512;    // Maximum expected protobuf message size
    uint8_t decodingBuffer[MAX_PROTOBUF_SIZE];
    
    // Rate limiting for individual topic publishing
    unsigned long lastPressurePublish;
    unsigned long lastRelayPublish;
    unsigned long lastSequencePublish;
    unsigned long lastSystemPublish;
    static const unsigned long MIN_PUBLISH_INTERVAL_MS = 1000;  // Minimum between topic updates
    
    // Data validation helpers
    bool validatePressureData(float a1_psi, float a5_psi);
    bool validateRelayData(bool r1_state, bool r2_state);
    bool validateSequenceData(const String& state);
    bool validateTimestamp(uint64_t timestamp);
    
    // Individual data type publishers
    bool publishPressureData(const void* pressure_pb);
    bool publishRelayStatus(const void* relay_pb);
    bool publishInputStatus(const void* input_pb);
    bool publishSequenceStatus(const void* sequence_pb);
    bool publishSystemHealth(const void* system_pb);
    bool publishErrorReport(const void* error_pb);
    bool publishConfigStatus(const void* config_pb);
    
    // MQTT topic publishing helpers
    bool publishToMqtt(const char* topic, const char* payload);
    bool publishToMqtt(const char* topic, float value);
    bool publishToMqtt(const char* topic, bool value);
    bool publishToMqtt(const char* topic, uint32_t value);
    
public:
    ProtobufDecoder();
    
    // Initialization
    void begin(NetworkManager* network);
    
    // Core decoding method - called by SerialBridge
    bool decodeProtobufMessage(uint8_t* data, size_t length);
    
    // Decode and publish to individual MQTT topics
    bool decodeAndPublish(uint8_t* data, size_t length);
    
    // Individual message type decoders
    bool decodeTelemetryMessage(uint8_t* data, size_t length);
    bool decodeCommandResponse(uint8_t* data, size_t length);
    
    // Binary message decoders (0x10-0x17)
    bool decodeDigitalInput(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    bool decodeDigitalOutput(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    bool decodeRelayEvent(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    bool decodePressure(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    bool decodeSystemError(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    bool decodeSafetyEvent(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    bool decodeSystemStatus(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    bool decodeSequenceEvent(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp);
    
    // Statistics and diagnostics
    void getStatistics(char* buffer, size_t bufferSize);
    uint32_t getMessagesReceived() const { return messagesReceived; }
    uint32_t getMessagesDecoded() const { return messagesDecoded; }
    uint32_t getDecodingErrors() const { return decodingErrors; }
    uint32_t getPublishErrors() const { return publishErrors; }
    
    // Rate limiting checks
    bool canPublishPressure() const;
    bool canPublishRelay() const;
    bool canPublishSequence() const;
    bool canPublishSystem() const;
    
    // === API INTEGRATION METHODS ===
    // These work with the Controller's existing protobuf API
    
    /**
     * @brief Send command to Controller via protobuf
     * @param commandType Command type string
     * @param parameters Command parameters
     * @return true if command was encoded and sent successfully
     */
    bool sendControllerCommand(const String& commandType, const String& parameters);
    
    /**
     * @brief Process incoming command responses from Controller
     * @param data Binary protobuf response data
     * @param length Data length in bytes
     * @return true if response was successfully processed
     */
    bool processCommandResponse(const uint8_t* data, size_t length);
    
    /**
     * @brief Register callback for command responses
     * @param handler Function to call when response received
     */
    void setResponseHandler(void (*handler)(uint32_t commandId, bool success, const String& message));
    
    /**
     * @brief Enable/disable command processing
     * @param enabled True to enable bidirectional communication
     */
    void setCommandsEnabled(bool enabled);
    
    /**
     * @brief Get last Controller telemetry timestamp
     * @return System time of last received telemetry message
     */
    uint64_t getLastTelemetryTime() const;
    
    /**
     * @brief Check if Controller telemetry is current
     * @param maxAgeMs Maximum acceptable age in milliseconds
     * @return true if telemetry is fresh
     */
    bool isTelemetryCurrent(uint32_t maxAgeMs = 5000) const;
    
private:
    // API integration state
    bool commandsEnabled;
    void (*responseHandler)(uint32_t commandId, bool success, const String& message);
    uint32_t nextCommandId;
    unsigned long lastTelemetryTime;
    uint32_t missedTelemetryCount;
    
    // Command encoding helpers (for sending to Controller)
    bool encodeCommand(const String& commandType, const String& parameters, uint8_t* buffer, size_t* length);
    bool sendBinaryCommand(const uint8_t* data, size_t length);
    
    // Telemetry parsing helpers
    bool extractPressureReadings(const void* telemetry_pb, float* a1_psi, float* a5_psi);
    bool extractRelayStates(const void* telemetry_pb, bool* r1_state, bool* r2_state);
    bool extractSequenceInfo(const void* telemetry_pb, String* currentState, uint32_t* elapsedMs);
    bool extractSystemHealth(const void* telemetry_pb, String* systemMode, bool* safetyActive);
    
    // Placeholder decoding (until nanopb headers available)
    bool decodeProtobufPlaceholder(uint8_t* data, size_t length);
    
    // Error handling and logging
    void logDecodingError(const String& context, const String& details = "");
    void logApiActivity(const String& activity, const String& details = "");
    void updateTelemetryStats(bool success, size_t messageSize);
};