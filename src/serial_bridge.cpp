#include "serial_bridge.h"
#include <string.h>

SerialBridge::SerialBridge()
    : networkManager(nullptr)
    , bridgeConnected(false)
    , lastMessageTime(0)
    , telemetryState(TELEMETRY_UNKNOWN)
    , messagesReceived(0)
    , messagesForwarded(0)
    , criticalMessages(0)
    , parseErrors(0)
    , messagesDropped(0)
    , windowedReceived(0)
    , windowedForwarded(0)
    , windowStartTime(millis())
    , bufferIndex(0)
    , expectedMessageSize(0)
    , lastPublishTime(0)
    , burstStartTime(0)
    , burstCount(0) {
    
    memset(messageBuffer, 0, sizeof(messageBuffer));
}

void SerialBridge::begin() {
    // Initialize Serial1 for controller communication
    Serial1.begin(SERIAL_BRIDGE_BAUD);
    
    // Clear any pending data
    while (Serial1.available()) {
        Serial1.read();
    }
    
    bridgeConnected = true;
    logBridgeActivity(LOG_INFO, "Serial bridge initialized on Serial1 at %d baud", SERIAL_BRIDGE_BAUD);
}

void SerialBridge::checkAndResetWindow() {
    unsigned long currentTime = millis();
    
    // Check if window has expired (handle overflow)
    bool windowExpired = false;
    if (currentTime >= windowStartTime) {
        windowExpired = (currentTime - windowStartTime) >= WINDOW_DURATION_MS;
    } else {
        // Handle millis() overflow (happens every ~49 days)
        windowExpired = ((0xFFFFFFFF - windowStartTime) + currentTime) >= WINDOW_DURATION_MS;
    }
    
    if (windowExpired) {
        windowedReceived = 0;
        windowedForwarded = 0;
        windowStartTime = currentTime;
        logBridgeActivity(LOG_DEBUG, "5-minute traffic window reset");
    }
}

void SerialBridge::setNetworkManager(NetworkManager* network) {
    networkManager = network;
    
    // Initialize protobuf decoder for individual topic publishing
    protobufDecoder.begin(network);
    logBridgeActivity(LOG_INFO, "Network manager and protobuf decoder configured");
}

void SerialBridge::update() {
    if (!bridgeConnected) return;
    
    // Read available data from Serial1 (size-prefixed binary protobuf data)
    // Per TELEMETRY_API.md: SIZE byte = header + payload length (NOT including size byte itself)
    // Total message on wire = 1 (size byte) + SIZE value
    while (Serial1.available()) {
        uint8_t byte = Serial1.read();
        
        // State machine for size-prefixed message parsing
        if (bufferIndex == 0) {
            // First byte is the message size (header + payload, NOT including size byte)
            expectedMessageSize = byte;
            
            // Validate size is within reasonable bounds (6-32 bytes for header+payload)
            // Per API: min 6 bytes (header only), max 32 bytes (header + max payload)
            if (expectedMessageSize < 6 || expectedMessageSize > 32) {
                parseErrors++;
                logBridgeActivity(LOG_WARNING, "Invalid message size: %d bytes", expectedMessageSize);
                continue; // Skip this byte and try next
            }
            
            // Store the size byte at index 0
            messageBuffer[bufferIndex++] = byte;
        }
        else {
            // Add byte to buffer if there's space
            if (bufferIndex < sizeof(messageBuffer) - 1) {
                messageBuffer[bufferIndex++] = byte;
                
                // Check if we have received the complete message
                // bufferIndex includes size byte, so complete when bufferIndex = 1 + expectedMessageSize
                if (bufferIndex >= (size_t)(expectedMessageSize + 1)) {
                    // Process the complete protobuf message (including size byte)
                    processProtobufMessage(reinterpret_cast<uint8_t*>(messageBuffer), bufferIndex);
                    
                    // Reset buffer for next message
                    bufferIndex = 0;
                    expectedMessageSize = 0;
                    memset(messageBuffer, 0, sizeof(messageBuffer));
                }
            }
            // Buffer overflow - reset and log error
            else {
                parseErrors++;
                logBridgeActivity(LOG_ERROR, "Protobuf buffer overflow, discarding data");
                bufferIndex = 0;
                expectedMessageSize = 0;
                memset(messageBuffer, 0, sizeof(messageBuffer));
            }
        }
    }
    
    // Check for communication timeout
    if (lastMessageTime > 0 && (millis() - lastMessageTime) > 60000) {
        // No messages for 60 seconds - might indicate controller issue
        static unsigned long lastTimeoutLog = 0;
        if (millis() - lastTimeoutLog > 300000) { // Log every 5 minutes
            logBridgeActivity(LOG_WARNING, "No controller messages for %lu seconds", 
                            (millis() - lastMessageTime) / 1000);
            lastTimeoutLog = millis();
        }
    }
    
    // Check for incomplete message timeout (reset partial message after 1 second)
    static unsigned long lastByteTime = 0;
    if (bufferIndex > 0) {
        if (lastByteTime == 0) {
            lastByteTime = millis();
        } else if (millis() - lastByteTime > 1000) {
            logBridgeActivity(LOG_WARNING, "Incomplete message timeout, discarding %d bytes", bufferIndex);
            bufferIndex = 0;
            expectedMessageSize = 0;
            memset(messageBuffer, 0, sizeof(messageBuffer));
            parseErrors++;
            lastByteTime = 0;
        }
    } else {
        lastByteTime = 0;
    }
}

void SerialBridge::processProtobufMessage(uint8_t* data, size_t length) {
    if (length == 0) return;
    
    // Check and reset 5-minute window if needed
    checkAndResetWindow();
    
    messagesReceived++;
    windowedReceived++;
    lastMessageTime = millis();
    
    logBridgeActivity(LOG_DEBUG, "Received protobuf message: %d bytes", length);
    
    // Forward complete raw protobuf message (including size byte) to MQTT
    if (networkManager && networkManager->isMQTTConnected()) {
        // Publish raw protobuf data to controller/protobuff topic
        bool rawSuccess = networkManager->publishBinary("controller/protobuff", data, length);
        
        if (rawSuccess) {
            messagesForwarded++;
            windowedForwarded++;
            logBridgeActivity(LOG_DEBUG, "Forwarded raw protobuf to MQTT: %d bytes", length);
        } else {
            messagesDropped++;
            logBridgeActivity(LOG_WARNING, "Failed to forward raw protobuf message to MQTT");
        }
        
        // Decode protobuf and publish to individual topics
        if (length >= 7) { // Minimum valid message size (1 size + 6 header)
            protobufDecoder.decodeAndPublish(data, length);
        }
    } else {
        messagesDropped++;
        logBridgeActivity(LOG_WARNING, "Cannot forward protobuf - MQTT not connected");
    }
}

// Legacy text message processing (deprecated)
void SerialBridge::processMessage(const String& message) {
    if (message.length() == 0) return;
    
    messagesReceived++;
    lastMessageTime = millis();
    
    // Handle telemetry control messages
    if (isTelemetryControlMessage(message)) {
        handleControlMessage(message);
        return;
    }
    
    // Skip interactive prompts
    if (isInteractiveMessage(message)) {
        return;
    }
    
    // Try to parse as structured message
    unsigned long timestamp;
    String level, content;
    
    if (parseStructuredMessage(message, timestamp, level, content)) {
        handleTelemetryMessage(timestamp, level, content);
    } else {
        // Handle as raw message if parsing fails
        handleRawMessage(message);
    }
}

bool SerialBridge::parseStructuredMessage(const String& message, unsigned long& timestamp, 
                                         String& level, String& content) {
    int firstPipe = message.indexOf('|');
    int secondPipe = message.indexOf('|', firstPipe + 1);
    
    if (firstPipe <= 0 || secondPipe <= firstPipe) {
        return false;
    }
    
    // Extract timestamp
    String timestampStr = message.substring(0, firstPipe);
    timestamp = timestampStr.toInt();
    if (timestamp == 0 && timestampStr != "0") {
        return false; // Invalid timestamp
    }
    
    // Extract level
    level = message.substring(firstPipe + 1, secondPipe);
    level.trim();
    
    // Extract content
    content = message.substring(secondPipe + 1);
    content.trim();
    
    return true;
}

void SerialBridge::handleTelemetryMessage(unsigned long timestamp, const String& level, 
                                         const String& content) {
    // Special handling for high-priority content types
    bool isSequenceData = (content.indexOf("sequence") >= 0 || content.indexOf("Sequence") >= 0);
    bool isPressureData = (content.indexOf("Pressure:") >= 0 || content.indexOf("pressure") >= 0);
    bool isRelayData = (content.indexOf("relay") >= 0 || content.indexOf("Relay") >= 0);
    bool isHighPriorityContent = isSequenceData || isPressureData || isRelayData;
    
    // Check if we should forward this message
    if (shouldForwardMessage(level)) {
        // For high-priority content, bypass some rate limiting
        bool shouldPublish = false;
        if (isHighPriorityContent && !isCriticalLevel(level)) {
            // For sequence/pressure/relay data, use reduced rate limiting
            if (millis() - lastPublishTime >= BRIDGE_HIGH_PRIORITY_RATE_MS) {
                shouldPublish = true;
                lastPublishTime = millis();
            }
        }
        else {
            shouldPublish = shouldPublishMessage(level);
        }
        
        if (shouldPublish) {
            publishToMQTT(timestamp, level, content);
            messagesForwarded++;
            
            // Count critical messages
            if (isCriticalLevel(level)) {
                criticalMessages++;
            }
            
            // Always try to parse structured content for specific topics
            // This creates dedicated MQTT topics regardless of rate limiting
            publishParsedData(content);
        }
    }
    
    logBridgeActivity(LOG_DEBUG, "Controller [%s]: %s", level.c_str(), content.c_str());
}

void SerialBridge::handleControlMessage(const String& message) {
    if (message.indexOf("TELEMETRY/DEBUG OUTPUT ENABLED") >= 0) {
        telemetryState = TELEMETRY_ENABLED;
        logBridgeActivity(LOG_INFO, "Controller telemetry enabled");
    }
    else if (message.indexOf("TELEMETRY/DEBUG OUTPUT DISABLED") >= 0) {
        telemetryState = TELEMETRY_DISABLED;
        logBridgeActivity(LOG_INFO, "Controller telemetry disabled");
    }
    
    // Don't forward control messages to MQTT
}

void SerialBridge::handleRawMessage(const String& message) {
    // Log non-structured messages for debugging
    logBridgeActivity(LOG_DEBUG, "Raw controller message: %s", message.c_str());
    
    // Could still publish to a raw topic if needed
    if (networkManager && networkManager->isMQTTConnected()) {
        networkManager->publish("controller/raw/unstructured", message.c_str());
    }
}

bool SerialBridge::shouldForwardMessage(const String& level) const {
    // Always forward critical messages
    if (isCriticalLevel(level)) {
        return true;
    }
    
    // For non-critical messages, only forward if telemetry is enabled
    // If telemetry state is unknown, assume enabled (fail-safe)
    return (telemetryState == TELEMETRY_ENABLED || telemetryState == TELEMETRY_UNKNOWN);
}

bool SerialBridge::isCriticalLevel(const String& level) const {
    return (level == "EMERG" || level == "ALERT" || level == "CRIT" || level == "ERROR");
}

bool SerialBridge::isInteractiveMessage(const String& message) const {
    return (message.startsWith("> ") || message == ">" || 
            message.indexOf("Interactive mode") >= 0);
}

bool SerialBridge::isTelemetryControlMessage(const String& message) const {
    return (message.indexOf("TELEMETRY/DEBUG OUTPUT") >= 0);
}

void SerialBridge::publishToMQTT(unsigned long timestamp, const String& level, 
                                const String& content) {
    if (!networkManager || !networkManager->isMQTTConnected()) {
        return;
    }
    
    // Publish to level-specific topic
    String topic = "controller/raw/";
    if (level == "EMERG") topic += "emerg";
    else if (level == "ALERT") topic += "alert";
    else if (level == "CRIT") topic += "crit";
    else if (level == "ERROR") topic += "error";
    else if (level == "WARN") topic += "warn";
    else if (level == "NOTICE") topic += "notice";
    else if (level == "INFO") topic += "info";
    else if (level == "DEBUG") topic += "debug";
    else topic += "unknown";
    
    // Create message with timestamp
    char mqttMessage[512];
    snprintf(mqttMessage, sizeof(mqttMessage), "%lu|%s", timestamp, content.c_str());
    
    networkManager->publish(topic.c_str(), mqttMessage);
}

void SerialBridge::publishParsedData(const String& content) {
    if (!networkManager || !networkManager->isMQTTConnected()) {
        return;
    }
    
    // Parse pressure data: "Pressure: A1=245.2psi A5=12.1psi"
    if (content.startsWith("Pressure:")) {
        publishPressureData(content);
    }
    // Parse sequence data: "Sequence: IDLE -> EXTEND_START"
    else if (content.startsWith("Sequence:")) {
        publishSequenceData(content);
    }
    // Parse relay data: "Relay: R1=ON (Extend valve)"
    else if (content.startsWith("Relay:")) {
        publishRelayData(content);
    }
    // Parse input data: "Input: pin=6 state=true name=LIMIT_EXTEND"
    else if (content.startsWith("Input:")) {
        publishInputData(content);
    }
    // Parse system status: "System: state=READY estop=false pressure_ok=true"
    else if (content.startsWith("System:")) {
        publishSystemStatus(content);
    }
}

void SerialBridge::publishPressureData(const String& content) {
    // Parse "Pressure: A1=245.2psi A5=12.1psi"
    String a1Value = extractValue(content, "A1=", "psi");
    String a5Value = extractValue(content, "A5=", "psi");
    
    if (a1Value.length() > 0) {
        networkManager->publish(TOPIC_BRIDGE_PRESSURE_A1, a1Value.c_str());
    }
    if (a5Value.length() > 0) {
        networkManager->publish(TOPIC_BRIDGE_PRESSURE_A5, a5Value.c_str());
    }
}

void SerialBridge::publishSequenceData(const String& content) {
    // Parse "Sequence: IDLE -> EXTEND_START" or "Sequence: type=AUTO state=EXTENDING elapsed=2340ms"
    if (content.indexOf("->") >= 0) {
        // State transition
        int arrowPos = content.indexOf("->");
        String fromState = content.substring(content.indexOf(":") + 1, arrowPos);
        String toState = content.substring(arrowPos + 2);
        fromState.trim();
        toState.trim();
        
        String transition = fromState + "->" + toState;
        networkManager->publish(TOPIC_BRIDGE_SEQUENCE, transition.c_str());
    } else {
        // Status update - extract current state
        String state = extractValue(content, "state=", " ");
        if (state.length() == 0) {
            state = extractValue(content, "state=", "");  // End of string
        }
        if (state.length() > 0) {
            networkManager->publish(TOPIC_BRIDGE_SEQUENCE, state.c_str());
        }
    }
}

void SerialBridge::publishRelayData(const String& content) {
    // Parse "Relay: R1=ON (Extend valve)"
    if (content.indexOf("R1=") >= 0) {
        String state = extractValue(content, "R1=", " ");
        if (state.length() == 0) state = extractValue(content, "R1=", ")");
        if (state.length() > 0) {
            networkManager->publish(TOPIC_BRIDGE_RELAY_R1, state.c_str());
        }
    }
    if (content.indexOf("R2=") >= 0) {
        String state = extractValue(content, "R2=", " ");
        if (state.length() == 0) state = extractValue(content, "R2=", ")");
        if (state.length() > 0) {
            networkManager->publish(TOPIC_BRIDGE_RELAY_R2, state.c_str());
        }
    }
}

void SerialBridge::publishInputData(const String& content) {
    // Parse "Input: pin=6 state=true name=LIMIT_EXTEND"
    String pin = extractValue(content, "pin=", " ");
    String state = extractValue(content, "state=", " ");
    
    if (pin == "6" && state.length() > 0) {
        networkManager->publish(TOPIC_BRIDGE_INPUT_PIN6, state.c_str());
    }
    else if (pin == "12" && state.length() > 0) {
        networkManager->publish(TOPIC_BRIDGE_INPUT_PIN12, state.c_str());
    }
}

void SerialBridge::publishSystemStatus(const String& content) {
    // Parse "System: state=READY estop=false pressure_ok=true"
    // Publish the entire status as a structured message
    networkManager->publish(TOPIC_BRIDGE_SYSTEM, content.c_str());
}

String SerialBridge::extractValue(const String& text, const String& prefix, const String& suffix) {
    int startPos = text.indexOf(prefix);
    if (startPos < 0) return "";
    
    startPos += prefix.length();
    
    int endPos;
    if (suffix.length() > 0) {
        endPos = text.indexOf(suffix, startPos);
        if (endPos < 0) return "";
    } else {
        endPos = text.length();
    }
    
    String value = text.substring(startPos, endPos);
    value.trim();
    return value;
}

void SerialBridge::getStatistics(char* buffer, size_t bufferSize) {
    snprintf(buffer, bufferSize,
        "Serial Bridge Stats:\n"
        "Connected: %s\n"
        "Protobuf Mode: Size-Prefixed Binary\n"
        "Messages Received: %lu\n"
        "Messages Forwarded: %lu\n"
        "Messages Dropped: %lu\n"
        "Parse Errors: %lu\n"
        "Buffer State: %d/%d bytes\n"
        "Expected Size: %d bytes\n"
        "Last Message: %lu ms ago",
        bridgeConnected ? "YES" : "NO",
        messagesReceived,
        messagesForwarded,
        messagesDropped,
        parseErrors,
        bufferIndex,
        sizeof(messageBuffer),
        expectedMessageSize,
        lastMessageTime > 0 ? millis() - lastMessageTime : 0
    );
}

void SerialBridge::logBridgeActivity(LogLevel level, const char* format, ...) {
    char buffer[256];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    
    Logger::log(level, "SerialBridge: %s", buffer);
}

bool SerialBridge::shouldPublishMessage(const String& level) {
    unsigned long currentTime = millis();
    
    // Priority system: Higher priority = more likely to be published
    // EMERGENCY/ALERT/CRITICAL/ERROR: Priority 4 (always publish)
    // WARNING: Priority 3 (high priority)
    // NOTICE/INFO: Priority 2 (medium priority)  
    // DEBUG: Priority 1 (lowest priority, drop first)
    
    int messagePriority = 1; // Default to lowest (DEBUG)
    if (level == "EMERG" || level == "ALERT" || level == "CRIT" || level == "ERROR") {
        messagePriority = 4; // Critical - always publish
    }
    else if (level == "WARN") {
        messagePriority = 3; // High priority
    }
    else if (level == "NOTICE" || level == "INFO") {
        messagePriority = 2; // Medium priority
    }
    // DEBUG and unknown levels stay at priority 1
    
    // Always allow critical messages (Priority 4)
    if (messagePriority == 4) {
        lastPublishTime = currentTime;
        return true;
    }
    
    // Check minimum time between publishes for non-critical
    if (currentTime - lastPublishTime < BRIDGE_RATE_LIMIT_MS) {
        // For high priority (WARNING), allow some rate limit bypass
        if (messagePriority >= 3 && (currentTime - lastPublishTime) >= BRIDGE_WARNING_RATE_MS) {
            lastPublishTime = currentTime;
            return true;
        }
        messagesDropped++;
        return false;
    }
    
    // Check burst limiting with priority consideration
    if (currentTime - burstStartTime > BRIDGE_BURST_WINDOW_MS) {
        // Reset burst window
        burstStartTime = currentTime;
        burstCount = 0;
    }
    
    // Apply stricter burst limits for lower priority messages
    int maxBurstForPriority = BRIDGE_MAX_BURST_COUNT;
    if (messagePriority == 1) { // DEBUG
        maxBurstForPriority = BRIDGE_DEBUG_BURST_LIMIT; // Only 1 DEBUG message per burst window
    }
    else if (messagePriority == 2) { // NOTICE/INFO
        maxBurstForPriority = BRIDGE_INFO_BURST_LIMIT; // Up to 3 INFO messages per burst window
    }
    // WARNING (priority 3) gets full burst allowance
    
    if (burstCount >= maxBurstForPriority) {
        messagesDropped++;
        return false;
    }
    
    // Allow message
    lastPublishTime = currentTime;
    burstCount++;
    return true;
}