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
    
    // Decode and publish to individual topics
    bool decodeSuccess = decodeAndPublish(decodingBuffer, length);
    
    if (decodeSuccess) {
        messagesDecoded++;
        lastTelemetryTime = millis();
        updateTelemetryStats(true, length);
        return true;
    } else {
        decodingErrors++;
        updateTelemetryStats(false, length);
        return false;
    }
}

bool ProtobufDecoder::decodeAndPublish(uint8_t* data, size_t length) {
    // Per TELEMETRY_API.md format:
    // Byte 0: SIZE (header + payload length, NOT including size byte)
    // Byte 1: Message Type (0x10-0x17)
    // Byte 2: Sequence ID
    // Bytes 3-6: Timestamp (uint32_t little-endian)
    // Bytes 7+: Payload
    
    if (length < 7) {
        logDecodingError("Message too short", String(length) + " bytes");
        return false;
    }
    
    uint8_t sizeField = data[0];
    uint8_t msgType = data[1];
    uint8_t sequence = data[2];
    uint32_t timestamp = data[3] | (data[4] << 8) | (data[5] << 16) | (data[6] << 24);
    
    // Validate size field
    if ((sizeField + 1) != length) {
        logDecodingError("Size mismatch", String("SIZE=") + String(sizeField) + " len=" + String(length));
        return false;
    }
    
    // Extract payload (everything after 7-byte header)
    uint8_t* payload = data + 7;
    size_t payloadLen = length - 7;
    
    Logger::log(LOG_DEBUG, "ProtobufDecoder: Type=0x%02X Seq=%d TS=%lu PayloadLen=%d", 
                msgType, sequence, timestamp, payloadLen);
    
    // Dispatch to appropriate decoder based on message type
    switch (msgType) {
        case 0x10:
            return decodeDigitalInput(payload, payloadLen, sequence, timestamp);
        case 0x11:
            return decodeDigitalOutput(payload, payloadLen, sequence, timestamp);
        case 0x12:
            return decodeRelayEvent(payload, payloadLen, sequence, timestamp);
        case 0x13:
            return decodePressure(payload, payloadLen, sequence, timestamp);
        case 0x14:
            return decodeSystemError(payload, payloadLen, sequence, timestamp);
        case 0x15:
            return decodeSafetyEvent(payload, payloadLen, sequence, timestamp);
        case 0x16:
            return decodeSystemStatus(payload, payloadLen, sequence, timestamp);
        case 0x17:
            return decodeSequenceEvent(payload, payloadLen, sequence, timestamp);
        default:
            logDecodingError("Unknown message type", String("0x") + String(msgType, HEX));
            return false;
    }
}

// ===== INDIVIDUAL MESSAGE DECODERS =====

bool ProtobufDecoder::decodeDigitalInput(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: pin(1) + flags(1) + debounce_time(2) = 4 bytes
    if (length < 4) return false;
    
    uint8_t pin = payload[0];
    uint8_t flags = payload[1];
    uint16_t debounceTime = payload[2] | (payload[3] << 8);
    
    bool state = flags & 0x01;
    bool isDebounced = flags & 0x02;
    uint8_t inputType = (flags >> 2) & 0x3F;
    
    // Publish to individual topics
    char topic[48];
    char value[32];
    
    // State topic
    snprintf(topic, sizeof(topic), "controller/input/%d/state", pin);
    publishToMqtt(topic, state ? "ACTIVE" : "INACTIVE");
    
    // Type topic  
    snprintf(topic, sizeof(topic), "controller/input/%d/type", pin);
    static const char* inputTypes[] = {"UNKNOWN", "MANUAL_EXTEND", "MANUAL_RETRACT", "SAFETY_CLEAR", 
                                        "SEQUENCE_START", "LIMIT_EXTEND", "LIMIT_RETRACT", 
                                        "SPLITTER_OPERATOR", "EMERGENCY_STOP"};
    const char* typeName = (inputType < 9) ? inputTypes[inputType] : "UNKNOWN";
    publishToMqtt(topic, typeName);
    
    Logger::log(LOG_DEBUG, "DI%d: %s (%s)", pin, state ? "ACTIVE" : "INACTIVE", typeName);
    return true;
}

bool ProtobufDecoder::decodeDigitalOutput(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: pin(1) + flags(1) + reserved(1) = 3 bytes
    if (length < 3) return false;
    
    uint8_t pin = payload[0];
    uint8_t flags = payload[1];
    
    bool state = flags & 0x01;
    uint8_t outputType = (flags >> 1) & 0x07;
    uint8_t lampPattern = (flags >> 4) & 0x0F;
    
    char topic[48];
    
    snprintf(topic, sizeof(topic), "controller/output/%d/state", pin);
    publishToMqtt(topic, state ? "HIGH" : "LOW");
    
    if (outputType == 1) { // MILL_LAMP
        static const char* patterns[] = {"OFF", "SOLID", "SLOW_BLINK", "FAST_BLINK"};
        const char* patternName = (lampPattern < 4) ? patterns[lampPattern] : "UNKNOWN";
        publishToMqtt("controller/output/mill_lamp/pattern", patternName);
    }
    
    Logger::log(LOG_DEBUG, "DO%d: %s", pin, state ? "HIGH" : "LOW");
    return true;
}

bool ProtobufDecoder::decodeRelayEvent(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: relay_number(1) + flags(1) + reserved(1) = 3 bytes
    if (length < 3) return false;
    
    uint8_t relayNum = payload[0];
    uint8_t flags = payload[1];
    
    bool state = flags & 0x01;
    bool isManual = flags & 0x02;
    bool success = flags & 0x04;
    uint8_t relayType = (flags >> 3) & 0x1F;
    
    char topic[48];
    
    // State topic
    snprintf(topic, sizeof(topic), "controller/relay/r%d/state", relayNum);
    publishToMqtt(topic, state ? "ON" : "OFF");
    
    // Mode topic
    snprintf(topic, sizeof(topic), "controller/relay/r%d/mode", relayNum);
    publishToMqtt(topic, isManual ? "MANUAL" : "AUTO");
    
    // Type name for logging
    static const char* relayTypes[] = {"UNKNOWN", "HYDRAULIC_EXTEND", "HYDRAULIC_RETRACT", 
                                        "RESERVED", "RESERVED", "RESERVED", "RESERVED",
                                        "OPERATOR_BUZZER", "ENGINE_STOP", "POWER_CONTROL"};
    const char* typeName = (relayType < 10) ? relayTypes[relayType] : "UNKNOWN";
    
    Logger::log(LOG_DEBUG, "R%d: %s (%s, %s)", relayNum, state ? "ON" : "OFF", 
                isManual ? "MANUAL" : "AUTO", typeName);
    
    lastRelayPublish = millis();
    return true;
}

bool ProtobufDecoder::decodePressure(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: sensor_pin(1) + flags(1) + raw_value(2) + pressure_psi(4) = 8 bytes
    if (length < 8) return false;
    
    uint8_t sensorPin = payload[0];
    uint8_t flags = payload[1];
    uint16_t rawValue = payload[2] | (payload[3] << 8);
    float pressurePsi;
    memcpy(&pressurePsi, payload + 4, sizeof(float));
    
    bool isFault = flags & 0x01;
    uint8_t pressureType = (flags >> 1) & 0x7F;
    
    char topic[48];
    char value[16];
    
    // Pressure value topic
    snprintf(topic, sizeof(topic), "controller/pressure/a%d", sensorPin);
    snprintf(value, sizeof(value), "%.2f", pressurePsi);
    publishToMqtt(topic, value);
    
    // Raw ADC topic
    snprintf(topic, sizeof(topic), "controller/pressure/a%d/raw", sensorPin);
    publishToMqtt(topic, (uint32_t)rawValue);
    
    // Fault status
    if (isFault) {
        snprintf(topic, sizeof(topic), "controller/pressure/a%d/fault", sensorPin);
        publishToMqtt(topic, "FAULT");
    }
    
    static const char* pressureTypes[] = {"UNKNOWN", "SYSTEM_PRESSURE", "TANK_PRESSURE", 
                                           "LOAD_PRESSURE", "AUXILIARY"};
    const char* typeName = (pressureType < 5) ? pressureTypes[pressureType] : "UNKNOWN";
    
    Logger::log(LOG_DEBUG, "Pressure A%d: %.2f PSI (raw=%d, %s)", 
                sensorPin, pressurePsi, rawValue, typeName);
    
    lastPressurePublish = millis();
    return true;
}

bool ProtobufDecoder::decodeSystemError(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: error_code(1) + flags(1) + desc_length(1) + description(0-24) = 3-27 bytes
    if (length < 3) return false;
    
    uint8_t errorCode = payload[0];
    uint8_t flags = payload[1];
    uint8_t descLength = payload[2];
    
    bool acknowledged = flags & 0x01;
    bool active = flags & 0x02;
    uint8_t severity = (flags >> 2) & 0x03;
    
    char description[25] = {0};
    if (descLength > 0 && length > 3) {
        size_t copyLen = (descLength < 24) ? descLength : 24;
        if (copyLen > (length - 3)) copyLen = length - 3;
        memcpy(description, payload + 3, copyLen);
    }
    
    static const char* severities[] = {"INFO", "WARNING", "ERROR", "CRITICAL"};
    
    // Publish error info
    publishToMqtt("controller/error/code", (uint32_t)errorCode);
    publishToMqtt("controller/error/severity", severities[severity]);
    publishToMqtt("controller/error/active", active);
    if (descLength > 0) {
        publishToMqtt("controller/error/description", description);
    }
    
    Logger::log(LOG_CRITICAL, "Error 0x%02X: %s [%s] %s", 
                errorCode, severities[severity], active ? "ACTIVE" : "cleared", description);
    
    return true;
}

bool ProtobufDecoder::decodeSafetyEvent(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: event_type(1) + flags(1) + reserved(1) = 3 bytes
    if (length < 3) return false;
    
    uint8_t eventType = payload[0];
    uint8_t flags = payload[1];
    
    bool isActive = flags & 0x01;
    
    static const char* eventTypes[] = {"SAFETY_ACTIVATED", "SAFETY_CLEARED", "EMERGENCY_STOP_ACTIVATED",
                                        "EMERGENCY_STOP_CLEARED", "LIMIT_SWITCH_TRIGGERED", "PRESSURE_SAFETY"};
    const char* eventName = (eventType < 6) ? eventTypes[eventType] : "UNKNOWN";
    
    publishToMqtt("controller/safety/event", eventName);
    publishToMqtt("controller/safety/active", isActive);
    
    Logger::log(LOG_CRITICAL, "Safety: %s (%s)", eventName, isActive ? "ACTIVE" : "INACTIVE");
    
    return true;
}

bool ProtobufDecoder::decodeSystemStatus(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: uptime(4) + loop_freq(2) + free_mem(2) + active_errors(1) + flags(1) + reserved(2) = 12 bytes
    if (length < 12) return false;
    
    uint32_t uptimeMs = payload[0] | (payload[1] << 8) | (payload[2] << 16) | (payload[3] << 24);
    uint16_t loopFreq = payload[4] | (payload[5] << 8);
    uint16_t freeMem = payload[6] | (payload[7] << 8);
    uint8_t activeErrors = payload[8];
    uint8_t flags = payload[9];
    
    bool safetyActive = flags & 0x01;
    bool estopActive = flags & 0x02;
    uint8_t seqState = (flags >> 2) & 0x0F;
    uint8_t lampPattern = (flags >> 6) & 0x03;
    
    // Publish system status
    publishToMqtt("controller/system/uptime", uptimeMs);
    publishToMqtt("controller/system/loop_hz", (uint32_t)loopFreq);
    publishToMqtt("controller/system/free_memory", (uint32_t)freeMem);
    publishToMqtt("controller/system/error_count", (uint32_t)activeErrors);
    publishToMqtt("controller/system/safety_active", safetyActive);
    publishToMqtt("controller/system/estop_active", estopActive);
    
    static const char* seqStates[] = {"IDLE", "EXTENDING", "EXTENDED", "RETRACTING", 
                                       "RETRACTED", "PAUSED", "ERROR_STATE"};
    const char* stateName = (seqState < 7) ? seqStates[seqState] : "UNKNOWN";
    publishToMqtt("controller/system/sequence_state", stateName);
    
    Logger::log(LOG_DEBUG, "Status: uptime=%lus, mem=%d, seq=%s", 
                uptimeMs/1000, freeMem, stateName);
    
    lastSystemPublish = millis();
    return true;
}

bool ProtobufDecoder::decodeSequenceEvent(uint8_t* payload, size_t length, uint8_t sequence, uint32_t timestamp) {
    // Payload: event_type(1) + step_number(1) + elapsed_time(2) = 4 bytes
    if (length < 4) return false;
    
    uint8_t eventType = payload[0];
    uint8_t stepNumber = payload[1];
    uint16_t elapsedMs = payload[2] | (payload[3] << 8);
    
    static const char* eventTypes[] = {"SEQUENCE_STARTED", "SEQUENCE_STEP_COMPLETE", "SEQUENCE_COMPLETE",
                                        "SEQUENCE_PAUSED", "SEQUENCE_RESUMED", "SEQUENCE_ABORTED", 
                                        "SEQUENCE_TIMEOUT"};
    const char* eventName = (eventType < 7) ? eventTypes[eventType] : "UNKNOWN";
    
    publishToMqtt("controller/sequence/event", eventName);
    publishToMqtt("controller/sequence/step", (uint32_t)stepNumber);
    publishToMqtt("controller/sequence/elapsed_ms", (uint32_t)elapsedMs);
    
    Logger::log(LOG_DEBUG, "Sequence: %s step=%d elapsed=%dms", eventName, stepNumber, elapsedMs);
    
    lastSequencePublish = millis();
    return true;
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