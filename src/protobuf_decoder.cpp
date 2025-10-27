#include "protobuf_decoder.h"
#include "network_manager.h"
#include "logger.h"
#include <string.h>

// Note: After nanopb installation and proto compilation, include generated protobuf headers:
// #include "controller_telemetry.pb.h"
// #include "pb_encode.h"
// #include "pb_decode.h"

ProtobufDecoder::ProtobufDecoder()
    : networkManager(nullptr)
    , messagesReceived(0)
    , messagesDecoded(0)
    , decodingErrors(0)
    , publishErrors(0)
    , lastSequenceNumber(0)
    , lastPressurePublish(0)
    , lastRelayPublish(0)
    , lastSequencePublish(0)
    , lastSystemPublish(0)
    , commandsEnabled(false)
    , responseHandler(nullptr)
    , nextCommandId(1)
    , lastTelemetryTime(0)
    , missedTelemetryCount(0) {
    
    memset(decodingBuffer, 0, sizeof(decodingBuffer));
}

void ProtobufDecoder::begin(NetworkManager* network) {
    networkManager = network;
    messagesReceived = 0;
    messagesDecoded = 0;
    decodingErrors = 0;
    publishErrors = 0;
    lastTelemetryTime = millis();
    
    Logger::log(LOG_INFO, "ProtobufDecoder: Initialized for Controller telemetry");
}

bool ProtobufDecoder::decodeProtobufMessage(uint8_t* data, size_t length) {
    if (!data || length == 0 || length > MAX_PROTOBUF_SIZE) {
        logDecodingError("Invalid message", String("Length: ") + String(length));
        return false;
    }
    
    messagesReceived++;
    
    // Copy data to working buffer
    memcpy(decodingBuffer, data, length);
    
    // TODO: Replace with actual nanopb decoding when protobuf headers are available
    // For now, implement placeholder decoding logic
    
    bool decodeSuccess = decodeProtobufPlaceholder(decodingBuffer, length);
    
    if (decodeSuccess) {
        messagesDecoded++;
        lastTelemetryTime = millis();
        updateTelemetryStats(true, length);
        
        Logger::log(LOG_DEBUG, "ProtobufDecoder: Successfully decoded %d byte message", length);
        return true;
    } else {
        decodingErrors++;
        updateTelemetryStats(false, length);
        logDecodingError("Protobuf decode failed", String("Length: ") + String(length));
        return false;
    }
}

bool ProtobufDecoder::decodeProtobufPlaceholder(uint8_t* data, size_t length) {
    // PLACEHOLDER: This will be replaced with actual nanopb decoding
    // For now, simulate successful decoding and extract mock data
    
    // Simulate extracting telemetry data from protobuf
    // In real implementation, this would use pb_decode() with generated structs
    
    // Mock pressure data extraction
    if (canPublishPressure()) {
        float mockA1Pressure = 245.5f;  // Simulate decoded pressure
        float mockA5Pressure = 12.3f;
        
        publishToMqtt("controller/pressure/a1", mockA1Pressure);
        publishToMqtt("controller/pressure/a5", mockA5Pressure);
        
        lastPressurePublish = millis();
    }
    
    // Mock relay status extraction
    if (canPublishRelay()) {
        bool mockR1State = false;  // Simulate decoded relay states
        bool mockR2State = true;
        
        publishToMqtt("controller/relay/r1", mockR1State ? "ON" : "OFF");
        publishToMqtt("controller/relay/r2", mockR2State ? "ON" : "OFF");
        
        lastRelayPublish = millis();
    }
    
    // Mock sequence status extraction
    if (canPublishSequence()) {
        String mockSequenceState = "IDLE";  // Simulate decoded sequence state
        uint32_t mockElapsedMs = 0;
        
        publishToMqtt("controller/sequence/state", mockSequenceState.c_str());
        publishToMqtt("controller/sequence/elapsed", mockElapsedMs);
        
        lastSequencePublish = millis();
    }
    
    // Mock system health extraction
    if (canPublishSystem()) {
        String mockSystemMode = "READY";
        bool mockSafetyActive = false;
        uint32_t mockUptime = millis();
        
        publishToMqtt("controller/system/mode", mockSystemMode.c_str());
        publishToMqtt("controller/system/safety_active", mockSafetyActive);
        publishToMqtt("controller/system/uptime", mockUptime);
        
        lastSystemPublish = millis();
    }
    
    return true;  // Simulate successful decoding
}

bool ProtobufDecoder::decodeTelemetryMessage(uint8_t* data, size_t length) {
    // TODO: Implement with actual nanopb when available
    /*
    controller_ControllerTelemetry telemetry = controller_ControllerTelemetry_init_zero;
    pb_istream_t stream = pb_istream_from_buffer(data, length);
    
    if (!pb_decode(&stream, controller_ControllerTelemetry_fields, &telemetry)) {
        logDecodingError("Telemetry decode failed", String(PB_GET_ERROR(&stream)));
        return false;
    }
    
    // Process decoded telemetry data
    if (telemetry.has_pressure) {
        publishPressureData(&telemetry.pressure);
    }
    
    if (telemetry.has_relay) {
        publishRelayStatus(&telemetry.relay);
    }
    
    if (telemetry.has_sequence) {
        publishSequenceStatus(&telemetry.sequence);
    }
    
    if (telemetry.has_system) {
        publishSystemHealth(&telemetry.system);
    }
    
    return true;
    */
    
    // Placeholder - use the placeholder decoder for now
    return decodeProtobufPlaceholder(data, length);
}

bool ProtobufDecoder::publishToMqtt(const char* topic, const char* payload) {
    if (!networkManager || !networkManager->isMQTTConnected()) {
        publishErrors++;
        return false;
    }
    
    bool success = networkManager->publish(topic, payload);
    if (!success) {
        publishErrors++;
    }
    
    return success;
}

bool ProtobufDecoder::publishToMqtt(const char* topic, float value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "%.2f", value);
    return publishToMqtt(topic, buffer);
}

bool ProtobufDecoder::publishToMqtt(const char* topic, bool value) {
    return publishToMqtt(topic, value ? "1" : "0");
}

bool ProtobufDecoder::publishToMqtt(const char* topic, uint32_t value) {
    char buffer[16];
    snprintf(buffer, sizeof(buffer), "%lu", (unsigned long)value);
    return publishToMqtt(topic, buffer);
}

bool ProtobufDecoder::canPublishPressure() const {
    return (millis() - lastPressurePublish) >= MIN_PUBLISH_INTERVAL_MS;
}

bool ProtobufDecoder::canPublishRelay() const {
    return (millis() - lastRelayPublish) >= MIN_PUBLISH_INTERVAL_MS;
}

bool ProtobufDecoder::canPublishSequence() const {
    return (millis() - lastSequencePublish) >= MIN_PUBLISH_INTERVAL_MS;
}

bool ProtobufDecoder::canPublishSystem() const {
    return (millis() - lastSystemPublish) >= MIN_PUBLISH_INTERVAL_MS;
}

void ProtobufDecoder::getStatistics(char* buffer, size_t bufferSize) {
    snprintf(buffer, bufferSize,
        "Protobuf Decoder Stats:\n"
        "Messages Received: %lu\n"
        "Messages Decoded: %lu\n"
        "Decoding Errors: %lu\n"
        "Publish Errors: %lu\n"
        "Success Rate: %.1f%%\n"
        "Last Telemetry: %lu ms ago\n"
        "Missed Telemetry: %lu",
        (unsigned long)messagesReceived,
        (unsigned long)messagesDecoded,
        (unsigned long)decodingErrors,
        (unsigned long)publishErrors,
        messagesReceived > 0 ? (float)messagesDecoded / messagesReceived * 100.0f : 0.0f,
        lastTelemetryTime > 0 ? millis() - lastTelemetryTime : 0,
        (unsigned long)missedTelemetryCount
    );
}

// === API INTEGRATION METHODS ===

bool ProtobufDecoder::sendControllerCommand(const String& commandType, const String& parameters) {
    if (!commandsEnabled || !networkManager) {
        logApiActivity("Command disabled", commandType);
        return false;
    }
    
    // TODO: Implement with actual nanopb when available
    /*
    controller_ControllerCommand command = controller_ControllerCommand_init_zero;
    
    // Fill command structure
    command.command_id = nextCommandId++;
    strncpy(command.command_type, commandType.c_str(), sizeof(command.command_type) - 1);
    command.requires_response = true;
    command.timeout_ms = 5000;
    
    // Encode command to protobuf
    uint8_t commandBuffer[256];
    pb_ostream_t stream = pb_ostream_from_buffer(commandBuffer, sizeof(commandBuffer));
    
    if (!pb_encode(&stream, controller_ControllerCommand_fields, &command)) {
        logApiActivity("Command encode failed", commandType);
        return false;
    }
    
    // Send via Serial1 to Controller
    return sendBinaryCommand(commandBuffer, stream.bytes_written);
    */
    
    // Placeholder implementation
    logApiActivity("Command sent (placeholder)", commandType + ": " + parameters);
    return true;
}

bool ProtobufDecoder::processCommandResponse(const uint8_t* data, size_t length) {
    if (!responseHandler) {
        return false;  // No response handler registered
    }
    
    // TODO: Implement with actual nanopb when available
    /*
    controller_ControllerResponse response = controller_ControllerResponse_init_zero;
    pb_istream_t stream = pb_istream_from_buffer(data, length);
    
    if (!pb_decode(&stream, controller_ControllerResponse_fields, &response)) {
        logApiActivity("Response decode failed", String(length) + " bytes");
        return false;
    }
    
    // Call registered response handler
    responseHandler(response.command_id, response.success, String(response.result_message));
    return true;
    */
    
    // Placeholder implementation
    if (responseHandler) {
        responseHandler(1, true, "Mock response processed");
    }
    return true;
}

void ProtobufDecoder::setResponseHandler(void (*handler)(uint32_t commandId, bool success, const String& message)) {
    responseHandler = handler;
    logApiActivity("Response handler registered", "");
}

void ProtobufDecoder::setCommandsEnabled(bool enabled) {
    commandsEnabled = enabled;
    logApiActivity("Commands", enabled ? "ENABLED" : "DISABLED");
}

uint64_t ProtobufDecoder::getLastTelemetryTime() const {
    return lastTelemetryTime;
}

bool ProtobufDecoder::isTelemetryCurrent(uint32_t maxAgeMs) const {
    if (lastTelemetryTime == 0) return false;
    return (millis() - lastTelemetryTime) <= maxAgeMs;
}

// === PRIVATE HELPER METHODS ===

void ProtobufDecoder::logDecodingError(const String& context, const String& details) {
    Logger::log(LOG_ERROR, "ProtobufDecoder: %s - %s", context.c_str(), details.c_str());
}

void ProtobufDecoder::logApiActivity(const String& activity, const String& details) {
    Logger::log(LOG_INFO, "ProtobufDecoder API: %s - %s", activity.c_str(), details.c_str());
}

void ProtobufDecoder::updateTelemetryStats(bool success, size_t messageSize) {
    static unsigned long lastStatsUpdate = 0;
    
    // Update miss counter if too much time elapsed
    if (lastTelemetryTime > 0 && (millis() - lastTelemetryTime) > 10000) {
        missedTelemetryCount++;
    }
    
    // Log stats every 5 minutes
    if (millis() - lastStatsUpdate > 300000) {
        char statsBuffer[256];
        getStatistics(statsBuffer, sizeof(statsBuffer));
        Logger::log(LOG_INFO, "ProtobufDecoder Stats: Success rate %.1f%%, %lu messages", 
                   messagesReceived > 0 ? (float)messagesDecoded / messagesReceived * 100.0f : 0.0f,
                   (unsigned long)messagesReceived);
        lastStatsUpdate = millis();
    }
}

// === VALIDATION HELPERS ===

bool ProtobufDecoder::validatePressureData(float a1_psi, float a5_psi) {
    // Basic pressure validation
    return (a1_psi >= 0 && a1_psi <= 6000) && (a5_psi >= 0 && a5_psi <= 6000);
}

bool ProtobufDecoder::validateRelayData(bool r1_state, bool r2_state) {
    // Basic relay validation - both relays shouldn't be on simultaneously for safety
    return !(r1_state && r2_state);
}

bool ProtobufDecoder::validateSequenceData(const String& state) {
    // Validate sequence state strings
    return (state == "IDLE" || state == "EXTEND_START" || state == "EXTENDING" || 
            state == "EXTEND_COMPLETE" || state == "RETRACT_START" || state == "RETRACTING" ||
            state == "RETRACT_COMPLETE" || state == "FAULT" || state == "E_STOP");
}

bool ProtobufDecoder::validateTimestamp(uint64_t timestamp) {
    // Basic timestamp validation - should be reasonable system uptime
    return (timestamp > 0 && timestamp < 4294967295UL);  // Max 32-bit milliseconds (~49 days)
}