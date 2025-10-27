#include "monitor_system.h"
#include "network_manager.h"
#include "lcd_display.h"
#include "serial_bridge.h"
#include "logger.h"
#include <Arduino.h>
#include <WiFiS3.h>

extern void debugPrintf(const char* fmt, ...);
extern NetworkManager* g_networkManager;
extern LCDDisplay* g_lcdDisplay;
extern SerialBridge* g_serialBridge;
extern MCP9600Sensor* g_mcp9600Sensor;

MonitorSystem::MonitorSystem() :
    currentState(SYS_INITIALIZING),
    systemStartTime(0),
    localTemperature(0.0),
    remoteTemperature(0.0),
    humidity(0.0),
    lastSensorRead(0),
    lastTemperatureRead(0),
    currentWeight(0.0),
    currentRawWeight(0),
    fuelGallons(0.0),
    lastWeightRead(0),
    currentVoltage(0.0),
    currentCurrent(0.0),
    currentPower(0.0),
    lastPowerRead(0),
    powerSensorAvailable(false),
    currentAdcVoltage(0.0),
    currentAdcRaw(0),
    lastAdcRead(0),
    adcSensorAvailable(false),
    publishInterval(STATUS_PUBLISH_INTERVAL_MS),
    heartbeatInterval(HEARTBEAT_INTERVAL_MS),
    lastStatusPublish(0),
    lastHeartbeat(0),
    lastSensorAvailable(false),
    lastHealthCheck(0),
    temperatureSensorFailures(0),
    weightSensorFailures(0),
    powerSensorFailures(0),
    adcSensorFailures(0),
    i2cBusError(false),
    i2cMux(0x70) {  // TCA9548A at address 0x70
    
    // Initialize digital I/O states
    for (int i = 0; i < 8; i++) {
        digitalInputStates[i] = false;
        digitalOutputStates[i] = false;
    }
}

void MonitorSystem::begin() {
    systemStartTime = millis();
    initializePins();
    
    // Set global pointer for external access
    g_mcp9600Sensor = &temperatureSensor;
    
    // Initialize I2C multiplexer first
    debugPrintf("MonitorSystem: Initializing TCA9548A I2C multiplexer...\n");
    if (i2cMux.begin()) {
        LOG_INFO("MonitorSystem: TCA9548A multiplexer initialized successfully");
        debugPrintf("MonitorSystem: I2C multiplexer ready\n");
    } else {
        LOG_ERROR("MonitorSystem: TCA9548A multiplexer initialization failed");
        debugPrintf("MonitorSystem: I2C multiplexer NOT found - sensors may not work!\n");
    }
    
    // Initialize MCP9600 temperature sensor
    debugPrintf("MonitorSystem: Initializing MCP9600 temperature sensor on channel %d...\n", MCP9600_CHANNEL);
    i2cMux.selectChannel(MCP9600_CHANNEL);
    if (temperatureSensor.begin()) {
        LOG_INFO("MonitorSystem: MCP9600 temperature sensor initialized successfully");
        
        // Enable temperature filtering to smooth readings
        temperatureSensor.enableFiltering(true, 5);  // 5-sample moving average
        
        // Set thermocouple type to K-type (most common)
        temperatureSensor.setThermocoupleType(0x00); // Type K
        debugPrintf("MonitorSystem: MCP9600 configured (Type K, 5-sample filter)\n");
    } else {
        LOG_WARN("MonitorSystem: MCP9600 temperature sensor initialization failed or not present");
    }
    
    // Initialize sensor availability tracking
    lastSensorAvailable = temperatureSensor.isAvailable();
    
    // Initialize NAU7802 weight sensor
    debugPrintf("MonitorSystem: Initializing NAU7802 weight sensor on channel %d...\n", NAU7802_CHANNEL);
    i2cMux.selectChannel(NAU7802_CHANNEL);
    NAU7802Status status = weightSensor.begin();
    if (status == NAU7802_OK) {
        debugPrintf("MonitorSystem: NAU7802 weight sensor initialized successfully\n");
        // Enable filtering for stable readings
        weightSensor.enableFiltering(true, 10);
    } else {
        LOG_ERROR("MonitorSystem: NAU7802 weight sensor initialization failed: %s", 
            weightSensor.getStatusString());
        debugPrintf("MonitorSystem: NAU7802 weight sensor initialization failed: %s\n", 
            weightSensor.getStatusString());
    }
    
    // Initialize INA219 power sensor
    debugPrintf("MonitorSystem: Initializing INA219 power sensor on channel %d...\n", INA219_CHANNEL);
    i2cMux.selectChannel(INA219_CHANNEL);
    if (powerSensor.begin()) {
        LOG_INFO("MonitorSystem: INA219 power sensor initialized successfully");
        powerSensorAvailable = true;
        debugPrintf("MonitorSystem: INA219 power sensor ready\n");
    } else {
        LOG_WARN("MonitorSystem: INA219 power sensor initialization failed or not present");
        powerSensorAvailable = false;
    }
    
    // Initialize MCP3421 ADC sensor
    debugPrintf("MonitorSystem: Initializing MCP3421 ADC sensor on channel %d...\n", MCP3421_CHANNEL);
    i2cMux.selectChannel(MCP3421_CHANNEL);
    if (adcSensor.begin()) {
        LOG_INFO("MonitorSystem: MCP3421 ADC sensor initialized successfully");
        adcSensorAvailable = true;
        debugPrintf("MonitorSystem: MCP3421 ADC sensor ready\n");
    } else {
        LOG_WARN("MonitorSystem: MCP3421 ADC sensor initialization failed or not present");
        adcSensorAvailable = false;
    }
    
    // Disable all multiplexer channels when done with initialization
    i2cMux.disableAllChannels();
    
    setSystemState(SYS_CONNECTING);
    debugPrintf("MonitorSystem: All sensors initialized\n");
}

void MonitorSystem::initializePins() {
    // Configure status LED
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
    
    // Configure digital inputs with pullup
    pinMode(DIGITAL_INPUT_1, INPUT_PULLUP);
    pinMode(DIGITAL_INPUT_2, INPUT_PULLUP);
    
    // Configure digital outputs
    pinMode(DIGITAL_OUTPUT_1, OUTPUT);
    pinMode(DIGITAL_OUTPUT_2, OUTPUT);
    digitalWrite(DIGITAL_OUTPUT_1, LOW);
    digitalWrite(DIGITAL_OUTPUT_2, LOW);
    
    // Configure additional watch pins as inputs
    for (size_t i = 0; i < WATCH_PIN_COUNT; i++) {
        if (WATCH_PINS[i] != DIGITAL_OUTPUT_1 && WATCH_PINS[i] != DIGITAL_OUTPUT_2) {
            pinMode(WATCH_PINS[i], INPUT_PULLUP);
        }
    }
    
    debugPrintf("MonitorSystem: Pins initialized\n");
}

void MonitorSystem::update() {
    unsigned long now = millis();
    
    // Perform periodic I2C health check (every 5 minutes)
    checkI2CHealth();
    
    // Round-robin I2C sensor reading: read one sensor every 10 seconds
    // LCD updates 5 seconds after each sensor read
    const unsigned long SENSOR_READ_INTERVAL = 10000;  // 10 seconds between sensor reads
    const unsigned long LCD_UPDATE_DELAY = 5000;       // LCD updates 5 seconds after sensor read
    static uint8_t currentSensor = 0;  // 0=temp, 1=weight, 2=power, 3=adc
    static unsigned long lastSensorReadTime = 0;
    static unsigned long nextLCDUpdate = 0;
    static bool lcdUpdatePending = false;
    static bool firstRun = true;
    
    // On first run, read first sensor immediately
    if (firstRun || (now - lastSensorReadTime >= SENSOR_READ_INTERVAL)) {
        firstRun = false;
        
        // Read the current sensor and publish its data
        switch (currentSensor) {
            case 0:
                LOG_INFO("Polling temperature sensor (10s rotation)");
                readSensors();  // Reads temperature sensor
                break;
            case 1:
                LOG_INFO("Polling weight sensor (10s rotation)");
                readWeightSensor();
                break;
            case 2:
                LOG_INFO("Polling power sensor (10s rotation)");
                readPowerSensor();
                break;
            case 3:
                LOG_INFO("Polling ADC sensor (10s rotation)");
                readAdcSensor();
                break;
        }
        
        // Schedule LCD update for 5 seconds from now
        nextLCDUpdate = now + LCD_UPDATE_DELAY;
        lcdUpdatePending = true;
        
        // Move to next sensor in rotation
        currentSensor = (currentSensor + 1) % 4;
        lastSensorReadTime = now;
    }
    
    // Update LCD 5 seconds after sensor read
    if (lcdUpdatePending && now >= nextLCDUpdate) {
        LOG_INFO("Updating LCD display (5s after sensor read)");
        updateLCDDisplay();
        lcdUpdatePending = false;
    }
    
    // Publish status periodically
    if (now - lastStatusPublish >= publishInterval) {
        publishStatus();
        lastStatusPublish = now;
    }
    
    // Publish heartbeat periodically
    if (now - lastHeartbeat >= heartbeatInterval) {
        publishHeartbeat();
        lastHeartbeat = now;
    }
    
    // Update status LED based on system state
    switch (currentState) {
        case SYS_INITIALIZING:
            // Fast blink during initialization
            digitalWrite(STATUS_LED_PIN, (now / 100) % 2);
            break;
        case SYS_CONNECTING:
            // Slow blink while connecting
            digitalWrite(STATUS_LED_PIN, (now / 500) % 2);
            break;
        case SYS_MONITORING:
            // Solid on when monitoring
            digitalWrite(STATUS_LED_PIN, HIGH);
            break;
        case SYS_ERROR:
            // Very fast blink for errors
            digitalWrite(STATUS_LED_PIN, (now / 50) % 2);
            break;
        case SYS_MAINTENANCE:
            // Alternating pattern for maintenance
            digitalWrite(STATUS_LED_PIN, ((now / 200) % 4) < 2);
            break;
    }
}

void MonitorSystem::readSensors() {
    readAnalogSensors();
    readTemperatureSensor();
    readDigitalInputs();
}

void MonitorSystem::readAnalogSensors() {
    // Analog sensors removed - using dedicated I2C sensors instead
    // MAX6656 provides temperature readings via I2C
    // Voltage monitoring can be added later with proper sensor
    humidity = 0.0; // No humidity sensor connected
}

void MonitorSystem::readTemperatureSensor() {
    unsigned long now = millis();
    if (now - lastTemperatureRead >= 1000) { // Read every second
        // Select MCP9600 multiplexer channel
        i2cMux.selectChannel(MCP9600_CHANNEL);
        delay(10); // Allow multiplexer channel to stabilize
        
        bool currentAvailable = temperatureSensor.isAvailable();
        
        // Check for sensor availability state changes
        if (lastSensorAvailable != currentAvailable) {
            if (currentAvailable) {
                LOG_INFO("MCP9600 temperature sensor reconnected");
                debugPrintf("\n=== MCP9600 sensor reconnected ===\n");
                temperatureSensorFailures = 0;  // Reset failure counter on reconnect
            } else {
                temperatureSensorFailures++;
                LOG_CRITICAL("MCP9600 temperature sensor disconnected or failed (consecutive failures: %d)", 
                           temperatureSensorFailures);
                debugPrintf("\n*** CRITICAL - MCP9600 sensor disconnected! ***\n");
            }
            lastSensorAvailable = currentAvailable;
        }
        
        if (currentAvailable) {
            // Reset failure counter on successful read
            temperatureSensorFailures = 0;
            
            // Only show verbose debug if temperature sensor debug is enabled
            bool tempDebugEnabled = temperatureSensor.isDebugEnabled();
            
            if (tempDebugEnabled) {
                debugPrintf("\n--- Temperature Reading Cycle ---\n");
            }
            
            float newLocalTemp = temperatureSensor.getLocalTemperature();
            float newRemoteTemp = temperatureSensor.getRemoteTemperature();
            
            // Static variables to track previous temperatures for validation
            static float lastLocalTemp = 70.0;  // Initialize to reasonable room temp
            static float lastRemoteTemp = 70.0;
            static bool firstRead = true;
            
            // Simple validation: reject obvious errors (50-200°F range for reasonable readings)
            const float MIN_VALID_TEMP_F = 50.0;
            const float MAX_VALID_TEMP_F = 200.0;
            
            // Convert Celsius to Fahrenheit for validation
            float newLocalTempF = (newLocalTemp * 9.0 / 5.0) + 32.0;
            float newRemoteTempF = (newRemoteTemp * 9.0 / 5.0) + 32.0;
            
            bool localValid = (newLocalTempF >= MIN_VALID_TEMP_F && newLocalTempF <= MAX_VALID_TEMP_F);
            bool remoteValid = (newRemoteTempF >= MIN_VALID_TEMP_F && newRemoteTempF <= MAX_VALID_TEMP_F);
            
            if (!firstRead) {
                float localChange = newLocalTemp - lastLocalTemp;
                float remoteChange = newRemoteTemp - lastRemoteTemp;
                
                if (tempDebugEnabled) {
                    debugPrintf("MonitorSystem: Local: %.1fC (%.1fF) valid=%s change=%.3fC\n", 
                               newLocalTemp, newLocalTempF, localValid ? "YES" : "NO", localChange);
                    debugPrintf("MonitorSystem: Remote: %.1fC (%.1fF) valid=%s change=%.3fC\n", 
                               newRemoteTemp, newRemoteTempF, remoteValid ? "YES" : "NO", remoteChange);
                }
                
                // Reject readings outside valid temperature range
                if (!localValid) {
                    temperatureSensorFailures++;
                    LOG_WARN("Temperature rejected: Local %.1fF out of range (keeping %.1fF)", 
                            newLocalTempF, (lastLocalTemp * 9.0 / 5.0) + 32.0);
                    newLocalTemp = lastLocalTemp; // Keep previous value
                } else if (abs(localChange) > 20.0) {
                    // Rate limiting: reject readings with unreasonable changes (>20C/second)
                    temperatureSensorFailures++;
                    if (tempDebugEnabled) {
                        debugPrintf("MonitorSystem: *** REJECTED local temp jump: %.1fC ***\n", localChange);
                    }
                    newLocalTemp = lastLocalTemp; // Keep previous value
                } else {
                    temperatureSensorFailures = 0;  // Reset on good reading
                }
                
                if (!remoteValid) {
                    LOG_WARN("Temperature rejected: Remote %.1fF out of range (keeping %.1fF)", 
                            newRemoteTempF, (lastRemoteTemp * 9.0 / 5.0) + 32.0);
                    newRemoteTemp = lastRemoteTemp; // Keep previous value
                } else if (abs(remoteChange) > 20.0) {
                    if (tempDebugEnabled) {
                        debugPrintf("MonitorSystem: *** REJECTED remote temp jump: %.1fC ***\n", remoteChange);
                    }
                    newRemoteTemp = lastRemoteTemp; // Keep previous value
                }
            } else {
                if (tempDebugEnabled) {
                    debugPrintf("MonitorSystem: First temperature reading - Local: %.1fF Remote: %.1fF\n", 
                               newLocalTempF, newRemoteTempF);
                }
                
                // On first read, validate but don't reject - just log
                if (!localValid) {
                    LOG_WARN("Temperature: First local reading out of range: %.1fF", newLocalTempF);
                }
                if (!remoteValid) {
                    LOG_WARN("Temperature: First remote reading out of range: %.1fF", newRemoteTempF);
                }
            }
            
            // Only update if readings are reasonable
            if (localValid || firstRead) {
                localTemperature = newLocalTemp;
                lastLocalTemp = newLocalTemp;
            }
            
            if (remoteValid || firstRead) {
                remoteTemperature = newRemoteTemp;
                lastRemoteTemp = newRemoteTemp;
            }
            
            if (tempDebugEnabled) {
                debugPrintf("MonitorSystem: FINAL - Local: %.1fC, Remote: %.1fC\n", localTemperature, remoteTemperature);
                debugPrintf("--- End Temperature Cycle ---\n\n");
            }
            
            firstRead = false;
            lastTemperatureRead = now;
        } else {
            // Sensor not available - use last known values but don't update timestamp
            // This will prevent stale data from being reported as current
        }
        
        // Disable multiplexer channel after reading to prevent conflicts
        i2cMux.disableAllChannels();
    }
}

void MonitorSystem::readDigitalInputs() {
    // Read all digital inputs
    for (size_t i = 0; i < WATCH_PIN_COUNT; i++) {
        uint8_t pin = WATCH_PINS[i];
        // Skip output pins
        if (pin != DIGITAL_OUTPUT_1 && pin != DIGITAL_OUTPUT_2) {
            bool currentState = digitalRead(pin) == LOW; // Active low with pullup
            size_t index = i < 8 ? i : 7; // Bounds check
            
            // Detect state change
            if (digitalInputStates[index] != currentState) {
                digitalInputStates[index] = currentState;
                LOG_INFO("MonitorSystem: Digital input %d changed to %s", 
                    pin, currentState ? "ACTIVE" : "INACTIVE");
                
                // Publish state change to MQTT
                if (g_networkManager && g_networkManager->isMQTTConnected()) {
                    char topic[64];
                    snprintf(topic, sizeof(topic), "monitor/input/%d", pin);
                    g_networkManager->publish(topic, currentState ? "1" : "0");
                }
            }
        }
    }
}

void MonitorSystem::readWeightSensor() {
    // Select NAU7802 multiplexer channel
    i2cMux.selectChannel(NAU7802_CHANNEL);
    delay(10); // Allow multiplexer channel to stabilize
    
    if (!weightSensor.isConnected()) {
        static bool wasConnected = true;  // Track previous state
        if (wasConnected) {
            weightSensorFailures++;
            LOG_CRITICAL("NAU7802 weight sensor disconnected (consecutive failures: %d)", weightSensorFailures);
            wasConnected = false;
        }
        i2cMux.disableAllChannels();
        return;
    } else {
        static bool wasConnected = false;  // Track previous state
        if (!wasConnected) {
            LOG_INFO("NAU7802 weight sensor reconnected");
            weightSensorFailures = 0;  // Reset failure counter
            wasConnected = true;
        }
    }
    
    if (weightSensor.dataAvailable()) {
        weightSensorFailures = 0;  // Reset on successful read
        weightSensor.updateReading();
        currentRawWeight = weightSensor.getRawReading();
        currentWeight = weightSensor.getFilteredWeight();
        
        // Calculate fuel gallons from weight
        // Current calibration: weight sensor returns grams
        // Gasoline density: ~2.8 kg/gal (6.17 lbs/gal)
        // Container tare weight: Need to calibrate/set based on your setup
        
        float weightInKg = currentWeight / 1000.0;  // Convert grams to kilograms
        
        // Simple calculation: divide total weight by fuel density
        // Container tare is already accounted for in zero calibration (scale zeroed with empty container)
        // So the weight reading is the fuel weight directly
        const float GASOLINE_DENSITY_KG_PER_GAL = 2.8;  // ~6.17 lbs/gal at 15°C
        
        // Weight reading is fuel weight (container tare already zeroed out)
        float fuelWeightKg = weightInKg;
        fuelGallons = fuelWeightKg / GASOLINE_DENSITY_KG_PER_GAL;
        
        // Ensure non-negative value (can't have negative fuel)
        if (fuelGallons < 0.0) {
            fuelGallons = 0.0;
        }
        
        // Publish weight data to MQTT
        if (g_networkManager && g_networkManager->isMQTTConnected()) {
            char valueBuffer[16];
            
            // Publish filtered weight
            snprintf(valueBuffer, sizeof(valueBuffer), "%.3f", currentWeight);
            g_networkManager->publish(TOPIC_NAU7802_WEIGHT, valueBuffer);
            
            // Publish raw reading
            snprintf(valueBuffer, sizeof(valueBuffer), "%ld", currentRawWeight);
            g_networkManager->publish(TOPIC_NAU7802_RAW, valueBuffer);
            
            // Publish fuel gallons
            snprintf(valueBuffer, sizeof(valueBuffer), "%.2f", fuelGallons);
            g_networkManager->publish("monitor/fuel/gallons", valueBuffer);
            
            // Publish comprehensive weight sensor status
            char statusBuffer[128];
            snprintf(statusBuffer, sizeof(statusBuffer), 
                "status: %s, ready: %s, weight: %.3f, raw: %ld",
                weightSensor.getStatusString(),
                weightSensor.isReady() ? "YES" : "NO",
                currentWeight,
                currentRawWeight);
            g_networkManager->publish(TOPIC_NAU7802_STATUS, statusBuffer);
        }
    }
    
    // Disable multiplexer channel after reading to prevent conflicts
    i2cMux.disableAllChannels();
}

void MonitorSystem::readPowerSensor() {
    debugPrintf("MonitorSystem: readPowerSensor() called, available=%s\n", powerSensorAvailable ? "YES" : "NO");
    
    // Only attempt to read if sensor was successfully initialized
    if (!powerSensorAvailable) {
        debugPrintf("MonitorSystem: Power sensor not available, skipping read\n");
        return;
    }
    
    // Select INA219 multiplexer channel
    i2cMux.selectChannel(INA219_CHANNEL);
    delay(10); // Allow multiplexer channel to stabilize
    
    debugPrintf("MonitorSystem: Attempting power sensor reading...\n");
    
    // Read power sensor values with error checking
    if (powerSensor.takereading()) {
        powerSensorFailures = 0;  // Reset on successful read
        currentVoltage = powerSensor.getBusVoltage();
        currentCurrent = powerSensor.getCurrent();
        currentPower = powerSensor.getPower();
        
        debugPrintf("MonitorSystem: Power reading successful: %.3fV, %.2fmA, %.2fmW\n", 
                   currentVoltage, currentCurrent, currentPower);
        
        // Publish power data to MQTT
        if (g_networkManager && g_networkManager->isMQTTConnected()) {
            debugPrintf("MonitorSystem: Publishing power data to MQTT\n");
            char valueBuffer[16];
            
            // Publish bus voltage
            snprintf(valueBuffer, sizeof(valueBuffer), "%.3f", currentVoltage);
            g_networkManager->publish(TOPIC_INA219_VOLTAGE, valueBuffer);
            
            // Publish current in mA
            snprintf(valueBuffer, sizeof(valueBuffer), "%.2f", currentCurrent);
            g_networkManager->publish(TOPIC_INA219_CURRENT, valueBuffer);
            
            // Publish power in mW
            snprintf(valueBuffer, sizeof(valueBuffer), "%.2f", currentPower);
            g_networkManager->publish(TOPIC_INA219_POWER, valueBuffer);
            
            // Publish comprehensive power sensor status
            char statusBuffer[128];
            snprintf(statusBuffer, sizeof(statusBuffer), 
                "ready: %s, voltage: %.3fV, current: %.2fmA, power: %.2fmW",
                powerSensorAvailable ? "YES" : "NO",
                currentVoltage,
                currentCurrent,
                currentPower);
            g_networkManager->publish(TOPIC_INA219_STATUS, statusBuffer);
            debugPrintf("MonitorSystem: Power data published to MQTT successfully\n");
        } else {
            debugPrintf("MonitorSystem: MQTT not connected, cannot publish power data\n");
        }
    } else {
        powerSensorFailures++;
        
        if (powerSensorFailures >= 5) {
            LOG_CRITICAL("Power sensor persistent failure (consecutive failures: %d)", powerSensorFailures);
        } else if (powerSensorFailures == 1) {
            LOG_WARN("Power sensor reading failed (consecutive failures: %d)", powerSensorFailures);
        }
        
        debugPrintf("MonitorSystem: Power sensor reading failed\n");
    }
    
    // Disable multiplexer channel after reading to prevent conflicts
    i2cMux.disableAllChannels();
}

void MonitorSystem::readAdcSensor() {
    // Only attempt to read if sensor was successfully initialized
    if (!adcSensorAvailable) {
        return;
    }
    
    // Select MCP3421 multiplexer channel
    i2cMux.selectChannel(MCP3421_CHANNEL);
    delay(10); // Allow multiplexer channel to stabilize
    
    // Take ADC reading with error checking
    if (adcSensor.takeReading()) {
        adcSensorFailures = 0;  // Reset on successful read
        currentAdcVoltage = adcSensor.getVoltage();
        currentAdcRaw = adcSensor.getRawValue();
        
        // Publish ADC data to MQTT
        if (g_networkManager && g_networkManager->isMQTTConnected()) {
            char valueBuffer[16];
            
            // Publish voltage reading
            snprintf(valueBuffer, sizeof(valueBuffer), "%.6f", currentAdcVoltage);
            g_networkManager->publish(TOPIC_MCP3421_VOLTAGE, valueBuffer);
            
            // Publish raw ADC value
            snprintf(valueBuffer, sizeof(valueBuffer), "%ld", currentAdcRaw);
            g_networkManager->publish(TOPIC_MCP3421_RAW, valueBuffer);
            
            // Publish comprehensive ADC sensor status
            char statusBuffer[128];
            snprintf(statusBuffer, sizeof(statusBuffer), 
                "ready: %s, voltage: %.6fV, raw: %ld, resolution: %d-bit",
                adcSensorAvailable ? "YES" : "NO",
                currentAdcVoltage,
                currentAdcRaw,
                adcSensor.getResolution());
            g_networkManager->publish(TOPIC_MCP3421_STATUS, statusBuffer);
        }
    } else {
        adcSensorFailures++;
        
        if (adcSensorFailures >= 5) {
            LOG_CRITICAL("MCP3421 ADC sensor persistent failure (consecutive failures: %d)", adcSensorFailures);
        } else if (adcSensorFailures == 1) {
            LOG_WARN("MCP3421 ADC sensor reading failed (consecutive failures: %d)", adcSensorFailures);
        }
    }
    
    // Disable multiplexer channel after reading to prevent conflicts
    i2cMux.disableAllChannels();
}

void MonitorSystem::publishStatus() {
    if (!g_networkManager || !g_networkManager->isMQTTConnected()) {
        return;
    }
    
    // Publish individual sensor readings
    char valueBuffer[16];
    
    // Publish MCP9600 local temperature (in Fahrenheit)
    float localTempF = (localTemperature * 9.0 / 5.0) + 32.0;
    snprintf(valueBuffer, sizeof(valueBuffer), "%.2f", localTempF);
    g_networkManager->publish(TOPIC_SENSOR_TEMPERATURE, valueBuffer);  // Backward compatibility
    g_networkManager->publish(TOPIC_SENSOR_TEMPERATURE_LOCAL, valueBuffer);  // Explicit local topic
    
    // Publish MCP9600 remote temperature (in Fahrenheit)
    float remoteTempF = (remoteTemperature * 9.0 / 5.0) + 32.0;
    snprintf(valueBuffer, sizeof(valueBuffer), "%.2f", remoteTempF);
    g_networkManager->publish(TOPIC_SENSOR_TEMPERATURE_REMOTE, valueBuffer);
    
    snprintf(valueBuffer, sizeof(valueBuffer), "%lu", getUptime());
    g_networkManager->publish(TOPIC_SYSTEM_UPTIME, valueBuffer);
    
    snprintf(valueBuffer, sizeof(valueBuffer), "%lu", getFreeMemory());
    g_networkManager->publish(TOPIC_SYSTEM_MEMORY, valueBuffer);
    
    LOG_DEBUG("MonitorSystem: Status published");
}

void MonitorSystem::publishHeartbeat() {
    if (!g_networkManager || !g_networkManager->isMQTTConnected()) {
        return;
    }
    
    char heartbeatMsg[64];
    snprintf(heartbeatMsg, sizeof(heartbeatMsg), "uptime=%lu state=%d", 
        getUptime(), (int)currentState);
    
    g_networkManager->publish(TOPIC_MONITOR_HEARTBEAT, heartbeatMsg);
    LOG_DEBUG("MonitorSystem: Heartbeat sent");
}

void MonitorSystem::getStatusString(char* buffer, size_t bufferSize) {
    // Convert cached Celsius temperatures to Fahrenheit for display
    float localTempF = (localTemperature * 9.0 / 5.0) + 32.0;
    float remoteTempF = (remoteTemperature * 9.0 / 5.0) + 32.0;
    
    snprintf(buffer, bufferSize,
        "local=%.1f remote=%.1f weight=%.3f uptime=%lu state=%d memory=%lu inputs=%d%d%d%d",
        localTempF, remoteTempF, currentWeight, getUptime(), (int)currentState, getFreeMemory(),
        digitalInputStates[0] ? 1 : 0,
        digitalInputStates[1] ? 1 : 0,
        digitalInputStates[2] ? 1 : 0,
        digitalInputStates[3] ? 1 : 0);
}

float MonitorSystem::getLocalTemperature() const {
    return localTemperature;
}

float MonitorSystem::getRemoteTemperature() const {
    return remoteTemperature;
}

float MonitorSystem::getLocalTemperatureF() const {
    return (localTemperature * 9.0 / 5.0) + 32.0;
}

float MonitorSystem::getRemoteTemperatureF() const {
    return (remoteTemperature * 9.0 / 5.0) + 32.0;
}

float MonitorSystem::getHumidity() const {
    return humidity;
}

bool MonitorSystem::isTemperatureSensorReady() {
    // Select MCP9600 multiplexer channel before checking availability
    i2cMux.selectChannel(MCP9600_CHANNEL);
    return temperatureSensor.isAvailable();
}

void MonitorSystem::getTemperatureSensorStatus(char* buffer, size_t bufferSize) {
    temperatureSensor.getStatusString(buffer, bufferSize);
}

void MonitorSystem::setTemperatureOffset(float localOffset, float remoteOffset) {
    temperatureSensor.setTemperatureOffset(localOffset, remoteOffset);
}

MCP9600Sensor* MonitorSystem::getTemperatureSensor() {
    return &temperatureSensor;
}

unsigned long MonitorSystem::getUptime() const {
    return (millis() - systemStartTime) / 1000; // Uptime in seconds
}

unsigned long MonitorSystem::getFreeMemory() const {
    // Rough estimate of free memory for Arduino
    // This is a simplified calculation
    return 32768 - 11000; // Assume ~11KB used, 32KB total for UNO R4
}

SystemState MonitorSystem::getSystemState() const {
    return currentState;
}

void MonitorSystem::setSystemState(SystemState state) {
    if (currentState != state) {
        debugPrintf("MonitorSystem: State changed from %d to %d\n", (int)currentState, (int)state);
        currentState = state;
    }
}

bool MonitorSystem::getDigitalInput(uint8_t pin) const {
    // Find the pin in the watch pins array
    for (size_t i = 0; i < WATCH_PIN_COUNT && i < 8; i++) {
        if (WATCH_PINS[i] == pin) {
            return digitalInputStates[i];
        }
    }
    return false;
}

void MonitorSystem::setDigitalOutput(uint8_t pin, bool state) {
    if (pin == DIGITAL_OUTPUT_1 || pin == DIGITAL_OUTPUT_2) {
        digitalWrite(pin, state ? HIGH : LOW);
        
        // Update internal state tracking
        if (pin == DIGITAL_OUTPUT_1) {
            digitalOutputStates[0] = state;
        } else if (pin == DIGITAL_OUTPUT_2) {
            digitalOutputStates[1] = state;
        }
        
        debugPrintf("MonitorSystem: Digital output %d set to %s\n", 
            pin, state ? "HIGH" : "LOW");
    }
}

void MonitorSystem::setPublishInterval(unsigned long interval) {
    publishInterval = interval;
    debugPrintf("MonitorSystem: Publish interval set to %lu ms\n", interval);
}

void MonitorSystem::setHeartbeatInterval(unsigned long interval) {
    heartbeatInterval = interval;
    debugPrintf("MonitorSystem: Heartbeat interval set to %lu ms\n", interval);
}

unsigned long MonitorSystem::getPublishInterval() const {
    return publishInterval;
}

unsigned long MonitorSystem::getHeartbeatInterval() const {
    return heartbeatInterval;
}

// NAU7802 Weight Sensor Functions
float MonitorSystem::getWeight() {
    return currentWeight;
}

float MonitorSystem::getFilteredWeight() {
    return weightSensor.getFilteredWeight();
}

long MonitorSystem::getRawWeight() const {
    return currentRawWeight;
}

float MonitorSystem::getFuelGallons() const {
    return fuelGallons;
}

bool MonitorSystem::isWeightSensorReady() {
    return weightSensor.isReady();
}

NAU7802Status MonitorSystem::getWeightSensorStatus() const {
    return weightSensor.getLastError();
}

// INA219 Power Sensor Functions
float MonitorSystem::getBusVoltage() {
    return currentVoltage;
}

float MonitorSystem::getCurrent() {
    return currentCurrent;
}

float MonitorSystem::getPower() {
    return currentPower;
}

bool MonitorSystem::isPowerSensorReady() {
    return powerSensorAvailable;
}

// MCP3421 ADC Sensor Functions
float MonitorSystem::getAdcVoltage() {
    return currentAdcVoltage;
}

int32_t MonitorSystem::getAdcRawValue() {
    return currentAdcRaw;
}

float MonitorSystem::getFilteredAdcVoltage(uint8_t samples) {
    return adcSensor.getFilteredVoltage(samples);
}

bool MonitorSystem::isAdcSensorReady() {
    return adcSensorAvailable;
}

void MonitorSystem::getAdcSensorStatus(char* buffer, size_t bufferSize) {
    adcSensor.getStatusString(buffer, bufferSize);
}

MCP3421_Sensor* MonitorSystem::getAdcSensor() {
    return &adcSensor;
}

bool MonitorSystem::calibrateWeightSensorZero() {
    debugPrintf("MonitorSystem: Starting weight sensor zero calibration\n");
    
    // Select the correct multiplexer channel for NAU7802
    i2cMux.selectChannel(NAU7802_CHANNEL);
    delay(50); // Give multiplexer time to switch
    
    NAU7802Status status = weightSensor.calibrateZero();
    if (status == NAU7802_OK) {
        debugPrintf("MonitorSystem: Weight sensor zero calibration completed\n");
        
        // Force LCD to clear its cached content so it updates with new calibration
        if (g_lcdDisplay) {
            i2cMux.selectChannel(LCD_CHANNEL);
            delay(50);
            g_lcdDisplay->clear();
            delay(100);
        }
        
        return true;
    } else {
        LOG_ERROR("MonitorSystem: Weight sensor zero calibration failed: %s", 
            weightSensor.getStatusString());
        debugPrintf("MonitorSystem: Weight sensor zero calibration failed: %s\n", 
            weightSensor.getStatusString());
        return false;
    }
}

bool MonitorSystem::calibrateWeightSensorScale(float knownWeight) {
    debugPrintf("MonitorSystem: Starting weight sensor scale calibration with %.2f\n", knownWeight);
    
    // Select the correct multiplexer channel for NAU7802
    i2cMux.selectChannel(NAU7802_CHANNEL);
    delay(50); // Give multiplexer time to switch
    
    NAU7802Status status = weightSensor.calibrateScale(knownWeight);
    if (status == NAU7802_OK) {
        debugPrintf("MonitorSystem: Weight sensor scale calibration completed\n");
        
        // Force LCD to clear its cached content so it updates with new calibration
        if (g_lcdDisplay) {
            i2cMux.selectChannel(LCD_CHANNEL);
            delay(50);
            g_lcdDisplay->clear();
            delay(100);
        }
        
        return true;
    } else {
        LOG_ERROR("MonitorSystem: Weight sensor scale calibration failed: %s", 
            weightSensor.getStatusString());
        debugPrintf("MonitorSystem: Weight sensor scale calibration failed: %s\n", 
            weightSensor.getStatusString());
        return false;
    }
}

void MonitorSystem::tareWeightSensor() {
    debugPrintf("MonitorSystem: Taring weight sensor\n");
    
    // Select the correct multiplexer channel for NAU7802
    i2cMux.selectChannel(NAU7802_CHANNEL);
    delay(50); // Give multiplexer time to switch
    
    weightSensor.tareScale();
}

bool MonitorSystem::saveWeightCalibration() {
    return weightSensor.saveCalibration();
}

bool MonitorSystem::loadWeightCalibration() {
    return weightSensor.loadCalibration();
}

void MonitorSystem::updateLCDDisplay() {
    // Only update LCD if it's available
    if (!g_lcdDisplay) return;
    
    // Select LCD multiplexer channel
    i2cMux.selectChannel(LCD_CHANNEL);
    
    // Get network status for combined display
    bool wifiConnected = false;
    bool mqttConnected = false;
    bool syslogWorking = false;
    
    if (g_networkManager) {
        wifiConnected = g_networkManager->isWiFiConnected();
        mqttConnected = g_networkManager->isMQTTConnected();
        syslogWorking = g_networkManager->isSyslogWorking();
    }
    
    // Update system status with network status and runtime (line 1)
    unsigned long uptime = getUptime();
    g_lcdDisplay->updateSystemStatus(currentState, uptime, wifiConnected, mqttConnected, syslogWorking);
    
    // Update sensor readings (lines 2-3) - Show MCP9600 temperatures in Fahrenheit and fuel gallons
    // Use temperature values directly - sensor availability checked during sensor reads
    float displayLocalTempF = (localTemperature > -100.0) ? 
                               (localTemperature * 9.0 / 5.0) + 32.0 : -999.0;
    float displayRemoteTempF = (remoteTemperature > -100.0) ? 
                               (remoteTemperature * 9.0 / 5.0) + 32.0 : -999.0;
    g_lcdDisplay->updateSensorReadings(displayLocalTempF, fuelGallons, displayRemoteTempF);
    
    // Update additional sensor data (line 4) - Power sensors and Serial1→MQTT traffic
    uint32_t serialMsgCount = 0;
    uint32_t mqttMsgCount = 0;
    
    if (g_serialBridge) {
        serialMsgCount = g_serialBridge->getMessagesReceived();
        mqttMsgCount = g_serialBridge->getMessagesForwarded();
    }
    
    g_lcdDisplay->updateAdditionalSensors(currentVoltage, currentCurrent, currentAdcVoltage, serialMsgCount, mqttMsgCount);
    
    // Disable multiplexer channel after LCD update
    i2cMux.disableAllChannels();
}

long MonitorSystem::getWeightZeroPoint() const {
    return weightSensor.getZeroOffset();
}

float MonitorSystem::getWeightScale() const {
    return weightSensor.getCalibrationFactor();
}

bool MonitorSystem::isWeightCalibrated() const {
    return weightSensor.isReady() && (weightSensor.getCalibrationFactor() != 0.0);
}

// I2C Health Monitoring Functions

bool MonitorSystem::verifyAllSensorsPresent() {
    bool allPresent = true;
    
    // Check MCP9600 temperature sensor
    i2cMux.selectChannel(MCP9600_CHANNEL);
    delay(10);
    bool tempPresent = temperatureSensor.isAvailable();
    i2cMux.disableAllChannels();
    
    if (!tempPresent) {
        LOG_ERROR("I2C BUS ERROR: MCP9600 temperature sensor missing on channel %d", MCP9600_CHANNEL);
        allPresent = false;
    }
    
    // Check NAU7802 weight sensor
    i2cMux.selectChannel(NAU7802_CHANNEL);
    delay(10);
    bool weightPresent = weightSensor.isConnected();
    i2cMux.disableAllChannels();
    
    if (!weightPresent) {
        LOG_ERROR("I2C BUS ERROR: NAU7802 weight sensor missing on channel %d", NAU7802_CHANNEL);
        allPresent = false;
    }
    
    // Check INA219 power sensor
    i2cMux.selectChannel(INA219_CHANNEL);
    delay(10);
    bool powerPresent = powerSensorAvailable;  // Use initialization flag
    i2cMux.disableAllChannels();
    
    if (!powerPresent) {
        LOG_ERROR("I2C BUS ERROR: INA219 power sensor missing on channel %d", INA219_CHANNEL);
        allPresent = false;
    }
    
    // Check MCP3421 ADC sensor
    i2cMux.selectChannel(MCP3421_CHANNEL);
    delay(10);
    bool adcPresent = adcSensorAvailable;  // Use initialization flag
    i2cMux.disableAllChannels();
    
    if (!adcPresent) {
        LOG_ERROR("I2C BUS ERROR: MCP3421 ADC sensor missing on channel %d", MCP3421_CHANNEL);
        allPresent = false;
    }
    
    return allPresent;
}

void MonitorSystem::checkI2CHealth() {
    const unsigned long HEALTH_CHECK_INTERVAL = 300000;  // 5 minutes
    const uint8_t MAX_CONSECUTIVE_FAILURES = 5;
    
    unsigned long now = millis();
    
    // Periodic comprehensive health check every 5 minutes
    if (now - lastHealthCheck >= HEALTH_CHECK_INTERVAL) {
        LOG_INFO("Performing I2C health check");
        
        bool allSensorsPresent = verifyAllSensorsPresent();
        
        if (!allSensorsPresent) {
            i2cBusError = true;
            LOG_CRITICAL("I2C BUS ERROR: One or more sensors missing - hardware fault detected");
            
            // Set system to error state
            currentState = SYS_ERROR;
            
            // Publish critical error via MQTT
            if (g_networkManager && g_networkManager->isMQTTConnected()) {
                g_networkManager->publish("monitor/error/i2c_bus", "CRITICAL: Sensor missing");
            }
        } else {
            // All sensors present - check if we're recovering from previous error
            if (i2cBusError) {
                LOG_INFO("I2C bus recovered - all sensors present");
                i2cBusError = false;
                currentState = SYS_MONITORING;
            }
            
            // Reset failure counters on successful health check
            if (temperatureSensorFailures > 0 || weightSensorFailures > 0 || 
                powerSensorFailures > 0 || adcSensorFailures > 0) {
                LOG_INFO("I2C Health OK - Resetting failure counters (Temp:%d Weight:%d Power:%d ADC:%d)",
                        temperatureSensorFailures, weightSensorFailures, 
                        powerSensorFailures, adcSensorFailures);
                temperatureSensorFailures = 0;
                weightSensorFailures = 0;
                powerSensorFailures = 0;
                adcSensorFailures = 0;
            }
        }
        
        lastHealthCheck = now;
    }
    
    // Check for excessive consecutive failures (indicates persistent problem)
    if (temperatureSensorFailures >= MAX_CONSECUTIVE_FAILURES) {
        LOG_ERROR("Temperature sensor: %d consecutive failures - possible I2C bus issue", 
                 temperatureSensorFailures);
    }
    
    if (weightSensorFailures >= MAX_CONSECUTIVE_FAILURES) {
        LOG_ERROR("Weight sensor: %d consecutive failures - possible I2C bus issue", 
                 weightSensorFailures);
    }
    
    if (powerSensorFailures >= MAX_CONSECUTIVE_FAILURES) {
        LOG_ERROR("Power sensor: %d consecutive failures - possible I2C bus issue", 
                 powerSensorFailures);
    }
    
    if (adcSensorFailures >= MAX_CONSECUTIVE_FAILURES) {
        LOG_ERROR("ADC sensor: %d consecutive failures - possible I2C bus issue", 
                 adcSensorFailures);
    }
}

