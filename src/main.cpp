#include <Arduino.h>
#include <Wire.h>
#include "constants.h"
#include "network_manager.h"
#include "telnet_server.h"
#include "http_server.h"
#include "monitor_system.h"
#include "command_processor.h"
#include "lcd_display.h"
#include "mcp9600_sensor.h"
#include "logger.h"

// Global instances
NetworkManager networkManager;
TelnetServer telnetServer;
HTTPServer httpServer;
MonitorSystem monitorSystem;
CommandProcessor commandProcessor;
LCDDisplay lcdDisplay;

// Global pointer for external access
NetworkManager* g_networkManager = &networkManager;
LCDDisplay* g_lcdDisplay = &lcdDisplay;
MCP9600Sensor* g_mcp9600Sensor = nullptr; // Will be set by monitor system

// Global debug flag
bool g_debugEnabled = false; // Disabled by default for production use

// System state
SystemState currentSystemState = SYS_INITIALIZING;
unsigned long lastWatchdog = 0;

// Debug printf function that sends to syslog
void debugPrintf(const char* fmt, ...) {
    if (!g_debugEnabled) return;
    
    char buffer[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    
    // Send to syslog server if network is available
    if (networkManager.isWiFiConnected()) {
        // Remove newlines for syslog
        size_t len = strlen(buffer);
        if (len > 0 && buffer[len-1] == '\n') {
            buffer[len-1] = '\0';
        }
        networkManager.sendSyslog(buffer);
    } else {
        // Only send to Serial when network is NOT available and debug is enabled
        // This allows local debugging during startup or network issues
        Serial.print("DEBUG: ");
        Serial.print(buffer);
    }
}

void setup() {
    // Initialize Serial FIRST
    Serial.begin(115200);
    delay(1000); // Give time for serial monitor to connect
    
    // Essential startup banner - always show
    Serial.println("===============================================");
    Serial.println("   LogSplitter Monitor v1.0.0 - Starting");
    Serial.println("===============================================");
    
    // Initialize I2C bus (Wire1) BEFORE any sensors try to use it
    Wire1.begin();
    Wire1.setClock(100000); // 100kHz for better compatibility with multiple devices
    delay(200); // Give I2C bus time to stabilize
    Serial.println("I2C Wire1 initialized at 100kHz");
    
    // Initialize command processor and network FIRST
    commandProcessor.begin(&networkManager, &monitorSystem);
    debugPrintf("Command processor initialized\n");
    
    networkManager.begin();
    debugPrintf("Network manager initialized\n");
    
    // Initialize Logger system with NetworkManager
    Logger::begin(&networkManager);
    Logger::setLogLevel(LOG_INFO);  // Default to INFO level
    debugPrintf("Logger initialized\n");
    
    networkManager.setHostname("LogMonitor");
    telnetServer.setConnectionInfo("LogMonitor", "1.0.0");
    
    // Initialize HTTP server
    httpServer.setMonitorSystem(&monitorSystem);
    httpServer.setNetworkManager(&networkManager);
    httpServer.setCommandProcessor(&commandProcessor);
    
    debugPrintf("Network initialization complete\n");
    currentSystemState = SYS_CONNECTING;
    
    // Essential status message - always show 
    Serial.println("System ready - connecting to network...");
}

void loop() {
    unsigned long now = millis();
    
    // Update watchdog
    lastWatchdog = now;
    
    // Update network first
    networkManager.update();
    
    // Initialize sensors after network is connected (one-time initialization)
    static bool sensorsInitialized = false;
    if (networkManager.isWiFiConnected() && !sensorsInitialized) {
        Serial.println("Network connected - initializing I2C sensors...");
        
        // Now initialize the monitor system with all sensors
        monitorSystem.begin();
        debugPrintf("Monitor system initialized\n");
        
        // Initialize LCD display last
        Serial.println("Initializing LCD display on channel 7...");
        
        // Use the multiplexer from monitor system to select LCD channel
        Wire1.beginTransmission(0x70);  // TCA9548A multiplexer address
        Wire1.write(1 << 7);  // Select channel 7 for LCD
        byte muxError = Wire1.endTransmission();
        
        if (muxError == 0) {
            Serial.println("LCD multiplexer channel 7 selected");
            delay(100);  // Allow channel to stabilize
            
            if (lcdDisplay.begin()) {
                Serial.println("LCD display initialized successfully");
                debugPrintf("LCD display initialized\n");
                delay(200);  // Give LCD time to fully initialize
                
                // Initial LCD update with default values
                lcdDisplay.updateSystemStatus(SYS_MONITORING, 0, true, false, false);
                lcdDisplay.updateSensorReadings(0.0, 0.0, 0.0);  // Will be updated by monitor system
                lcdDisplay.updateAdditionalSensors(0.0, 0.0, 0.0);
                Serial.println("LCD test write complete - initial display set");
            } else {
                Serial.println("WARNING: LCD display initialization failed - not present or not responding");
                debugPrintf("LCD display not present\n");
            }
        } else {
            Serial.print("ERROR: Failed to select LCD multiplexer channel, error code: ");
            Serial.println(muxError);
        }
        
        // Disable multiplexer channels after LCD init
        Wire1.beginTransmission(0x70);
        Wire1.write(0x00);  // Disable all channels
        Wire1.endTransmission();
        
        sensorsInitialized = true;
        monitorSystem.setSystemState(SYS_MONITORING);
        
        debugPrintf("All sensors initialized after network connection\n");
        Serial.print("Network connected! IP: ");
        Serial.println(WiFi.localIP());
    }
    
    // Start telnet server once network is connected
    if (networkManager.isWiFiConnected() && currentSystemState == SYS_CONNECTING) {
        telnetServer.begin(23);
        httpServer.begin(80);  // Start HTTP server on port 80
        currentSystemState = SYS_MONITORING;
        
        debugPrintf("Telnet server started\n");
        debugPrintf("HTTP server started on port 80\n");
        Serial.print("HTTP server: http://");
        Serial.println(WiFi.localIP());
    }
    
    // Update monitor system (only if sensors are initialized)
    if (sensorsInitialized) {
        monitorSystem.update();
    }
    
    // Update telnet server
    if (networkManager.isWiFiConnected()) {
        telnetServer.update();
        httpServer.update();  // Update HTTP server
        
        // Process telnet commands
        if (telnetServer.isConnected()) {
            String command = telnetServer.readLine();
            if (command.length() > 0) {
                char commandBuffer[COMMAND_BUFFER_SIZE];
                command.toCharArray(commandBuffer, sizeof(commandBuffer));
                
                char response[SHARED_BUFFER_SIZE];
                bool success = commandProcessor.processCommand(commandBuffer, false, response, sizeof(response));
                
                if (strlen(response) > 0) {
                    telnetServer.print(response);
                    telnetServer.print("\r\n");
                }
                
                // Show prompt
                telnetServer.print("\r\n> ");
                
                debugPrintf("Telnet: %s -> %s\n", 
                    commandBuffer, strlen(response) > 0 ? response : "none");
            }
        }
    }
    
    // Handle serial commands for local debugging
    if (Serial.available()) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        
        if (command.length() > 0) {
            char commandBuffer[COMMAND_BUFFER_SIZE];
            command.toCharArray(commandBuffer, sizeof(commandBuffer));
            
            char response[SHARED_BUFFER_SIZE];
            bool success = commandProcessor.processCommand(commandBuffer, false, response, sizeof(response));
            
            if (strlen(response) > 0) {
                Serial.print("Response: ");
                Serial.println(response);
            }
            
            Serial.print("> ");
        }
    }
    
    // Check for system errors
    if (!networkManager.isWiFiConnected() && currentSystemState == SYS_MONITORING) {
        currentSystemState = SYS_CONNECTING;
        monitorSystem.setSystemState(SYS_CONNECTING);
        debugPrintf("Network disconnected, reconnecting\n");
    }
    
    // System health check
    static unsigned long lastHealthCheck = 0;
    if (now - lastHealthCheck >= 60000) { // Every minute
        lastHealthCheck = now;
        
        char healthStatus[256];
        monitorSystem.getStatusString(healthStatus, sizeof(healthStatus));
        debugPrintf("Health: %s\n", healthStatus);
        
        // Check memory and system health
        unsigned long freeMemory = monitorSystem.getFreeMemory();
        if (freeMemory < 5000) { // Less than 5KB free
            // Critical memory warning - always show
            Serial.print("WARNING: Low memory: ");
            Serial.print(freeMemory);
            Serial.println(" bytes free");
            debugPrintf("Low memory: %lu bytes free\n", freeMemory);
        }
    }
    
    // Prevent watchdog timeout with a small delay
    delay(10);
}

// Handle system interrupts and errors
void systemErrorHandler(const char* error) {
    debugPrintf("SYSTEM ERROR: %s\n", error);
    Serial.print("SYSTEM ERROR: ");
    Serial.println(error);
    
    // Set system to error state
    currentSystemState = SYS_ERROR;
    monitorSystem.setSystemState(SYS_ERROR);
    
    // Try to send error to MQTT if possible
    if (networkManager.isMQTTConnected()) {
        char errorTopic[64];
        snprintf(errorTopic, sizeof(errorTopic), "%s", TOPIC_MONITOR_ERROR);
        networkManager.publish(errorTopic, error);
    }
}

// System status helper
const char* getSystemStateString(SystemState state) {
    switch (state) {
        case SYS_INITIALIZING: return "INITIALIZING";
        case SYS_CONNECTING: return "CONNECTING";
        case SYS_MONITORING: return "MONITORING";
        case SYS_ERROR: return "ERROR";
        case SYS_MAINTENANCE: return "MAINTENANCE";
        default: return "UNKNOWN";
    }
}
