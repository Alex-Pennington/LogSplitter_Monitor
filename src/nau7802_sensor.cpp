#include "nau7802_sensor.h"
#include "logger.h"
#include <EEPROM.h>

extern void debugPrintf(const char* fmt, ...);

// Temporary debug function for serial output only (troubleshooting)
static void debugSerial(const char* fmt, ...) {
    char buffer[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    Serial.print("DEBUG: ");
    Serial.print(buffer);
}

NAU7802Sensor::NAU7802Sensor() :
    lastError(NAU7802_OK),
    calibrationFactor(1.0),
    zeroOffset(0),
    isCalibrated(false),
    lastRawReading(0),
    lastWeight(0.0),
    lastFilteredWeight(0.0),
    filteringEnabled(false),
    filterSamples(10),
    filterBuffer(nullptr),
    filterIndex(0),
    filterBufferFull(false),
    currentGain(NAU7802_GAIN_128),
    currentSampleRate(NAU7802_SPS_10),
    totalReadings(0),
    minReading(0),
    maxReading(0) {
    
    initializeDefaults();
}

NAU7802Status NAU7802Sensor::begin() {
    // Standard system logging (permanent) - goes to syslog
    LOG_INFO("NAU7802: Initializing weight sensor");
    
    // Initialize I2C on Wire1 for Arduino R4 WiFi Qwiic connector
    Wire1.begin();
    
    // Initialize the NAU7802
    if (!scale.begin(Wire1)) {
        lastError = NAU7802_NOT_FOUND;
        LOG_ERROR("NAU7802: Sensor not found on I2C");
        logError(lastError, "begin");
        return lastError;
    }
    
    // Turn off the internal LDO. Save 150uA
    scale.setLDO(NAU7802_LDO_2V4);
    
    // Set gain to 128 (default)
    scale.setGain(currentGain);
    
    // Set sample rate
    scale.setSampleRate(currentSampleRate);
    
    // Turn on digital and analog power
    scale.powerUp();
    
    // Calibrate analog front end
    NAU7802Status calibStatus = calibrateAFE();
    if (calibStatus != NAU7802_OK) {
        return calibStatus;
    }
    
    // Wait for sensor to stabilize after initialization
    debugPrintf("NAU7802: Waiting for sensor to stabilize...\n");
    delay(500);  // Give sensor time to stabilize
    
    // Take a few dummy readings to ensure sensor is ready
    for (int i = 0; i < 5; i++) {
        if (scale.available()) {
            scale.getReading();  // Dummy reading
        }
        delay(100);
    }
    
    // Try to load calibration from EEPROM
    if (!loadCalibration()) {
        debugPrintf("NAU7802: No valid calibration found in EEPROM\n");
    }
    
    debugPrintf("NAU7802: Sensor initialized successfully\n");
    debugPrintf("NAU7802: Gain=%d, SampleRate=%d, RevisionCode=0x%02X\n", 
        currentGain, currentSampleRate, getRevisionCode());
    
    lastError = NAU7802_OK;
    return NAU7802_OK;
}

bool NAU7802Sensor::isConnected() {
    return scale.isConnected();
}

void NAU7802Sensor::reset() {
    debugPrintf("NAU7802: Performing sensor reset\n");
    scale.reset();
    
    // Re-apply configuration after reset
    scale.setGain(currentGain);
    scale.setSampleRate(currentSampleRate);
    scale.powerUp();
    
    // Reset statistics
    resetStatistics();
    
    lastError = NAU7802_OK;
}

NAU7802Status NAU7802Sensor::calibrateAFE() {
    debugPrintf("NAU7802: Starting AFE calibration...\n");
    
    // Calibrate analog front end
    if (!scale.calibrateAFE()) {
        lastError = NAU7802_CALIBRATION_FAILED;
        logError(lastError, "calibrateAFE");
        return lastError;
    }
    
    debugPrintf("NAU7802: AFE calibration completed\n");
    return NAU7802_OK;
}

NAU7802Status NAU7802Sensor::calibrateZero() {
    debugPrintf("NAU7802: Starting zero calibration (ensure no load on sensor)...\n");
    
    // Give sensor extra time to stabilize before zero calibration
    debugPrintf("NAU7802: Allowing sensor to stabilize for zero calibration...\n");
    delay(1000);
    
    // Clear any pending readings
    while (scale.available()) {
        scale.getReading();
        delay(10);
    }
    
    // Wait for sensor to be ready with extended timeout
    debugPrintf("NAU7802: Waiting for sensor to be ready...\n");
    unsigned long timeout = millis() + 10000;  // 10 second timeout
    int readyCount = 0;
    
    while (millis() < timeout) {
        if (scale.available()) {
            readyCount++;
            if (readyCount >= 3) {  // Wait for multiple consecutive ready states
                break;
            }
        } else {
            readyCount = 0;  // Reset count if not ready
        }
        delay(50);
    }
    
    if (readyCount < 3) {
        lastError = NAU7802_NOT_READY;
        logError(lastError, "calibrateZero - sensor not consistently ready");
        return lastError;
    }
    
    debugPrintf("NAU7802: Sensor ready, taking calibration readings...\n");
    
    // Take average of multiple readings for zero calibration
    long sum = 0;
    const uint8_t samples = 50;
    uint8_t validSamples = 0;
    
    for (uint8_t i = 0; i < samples; i++) {
        // Wait for data to be available
        unsigned long sampleTimeout = millis() + 1000;
        while (!scale.available() && millis() < sampleTimeout) {
            delay(10);
        }
        
        if (scale.available()) {
            long reading = scale.getReading();
            sum += reading;
            validSamples++;
            debugPrintf("NAU7802: Sample %d: %ld\n", i+1, reading);
        } else {
            debugPrintf("NAU7802: Sample %d: timeout\n", i+1);
        }
        delay(100); // Wait between readings
    }
    
    if (validSamples < samples / 2) {
        lastError = NAU7802_CALIBRATION_FAILED;
        logError(lastError, "calibrateZero - insufficient samples");
        debugPrintf("NAU7802: Only got %d valid samples out of %d\n", validSamples, samples);
        return lastError;
    }
    
    zeroOffset = sum / validSamples;
    debugPrintf("NAU7802: Zero calibration completed, offset=%ld (from %d samples)\n", 
        zeroOffset, validSamples);
    
    // Save calibration to EEPROM
    saveCalibration();
    
    return NAU7802_OK;
}

NAU7802Status NAU7802Sensor::calibrateScale(float knownWeight) {
    // Standard system logging (permanent) - goes to syslog
    LOG_INFO("NAU7802: Starting scale calibration with known weight: %.2f", knownWeight);
    
    // Temporary debugging (troubleshooting) - goes to serial only
    debugSerial("NAU7802 calibrateScale() called with weight=%.2f\n", knownWeight);
    
    if (knownWeight <= 0) {
        lastError = NAU7802_CALIBRATION_FAILED;
        LOG_ERROR("NAU7802: Invalid calibration weight: %.2f", knownWeight);
        logError(lastError, "calibrateScale - invalid weight");
        return lastError;
    }
    
    // Wait for sensor to be ready
    debugSerial("Waiting for sensor to be ready for scale calibration...\n");
    unsigned long timeout = millis() + 5000;
    while (!scale.available() && millis() < timeout) {
        delay(10);
    }
    
    if (!scale.available()) {
        lastError = NAU7802_NOT_READY;
        LOG_ERROR("NAU7802: Sensor not ready for calibration after timeout");
        logError(lastError, "calibrateScale - sensor not ready");
        return lastError;
    }
    
    // Take multiple readings and average for better accuracy
    long sum = 0;
    const uint8_t samples = 20;
    uint8_t validSamples = 0;
    
    debugSerial("Taking %d readings for scale calibration...\n", samples);
    
    for (uint8_t i = 0; i < samples; i++) {
        // Wait for data to be available
        unsigned long sampleTimeout = millis() + 1000;
        while (!scale.available() && millis() < sampleTimeout) {
            delay(10);
        }
        
        if (scale.available()) {
            long reading = scale.getReading();
            sum += reading;
            validSamples++;
            debugSerial("Scale sample %d: %ld\n", i+1, reading);
        } else {
            debugSerial("Scale sample %d: timeout\n", i+1);
        }
        delay(50); // Short delay between readings
    }
    
    if (validSamples < samples / 2) {
        lastError = NAU7802_CALIBRATION_FAILED;
        LOG_ERROR("NAU7802: Insufficient calibration samples: %d/%d", validSamples, samples);
        logError(lastError, "calibrateScale - insufficient samples");
        debugSerial("Only got %d valid samples out of %d\n", validSamples, samples);
        return lastError;
    }
    
    long rawReading = sum / validSamples;
    debugSerial("Average raw reading: %ld, zero offset: %ld\n", rawReading, zeroOffset);
    
    // Calculate calibration factor
    float adjustedReading = rawReading - zeroOffset;
    debugSerial("Calibration calculation details:\n");
    debugSerial("  Raw reading: %ld\n", rawReading);
    debugSerial("  Zero offset: %ld\n", zeroOffset);
    debugSerial("  Adjusted reading: %.2f\n", adjustedReading);
    debugSerial("  Known weight: %.2f\n", knownWeight);
    
    if (abs(adjustedReading) < 10) { // Lower threshold for sensitive load cells
        lastError = NAU7802_CALIBRATION_FAILED;
        LOG_ERROR("NAU7802: Calibration failed - adjusted reading %.2f too small", adjustedReading);
        logError(lastError, "calibrateScale - reading too close to zero");
        debugSerial("ERROR: Adjusted reading %.2f is too small (< 10)\n", adjustedReading);
        debugSerial("This suggests zero calibration was not done or failed\n");
        return lastError;
    }
    
    // Perform the division and check for validity
    calibrationFactor = knownWeight / adjustedReading;
    debugSerial("  Calculated factor: %.6f\n", calibrationFactor);
    
    // Validate calibration factor
    if (isnan(calibrationFactor) || isinf(calibrationFactor) || calibrationFactor == 0.0) {
        lastError = NAU7802_CALIBRATION_FAILED;
        LOG_ERROR("NAU7802: Invalid calibration factor calculated: %.6f", calibrationFactor);
        logError(lastError, "calibrateScale - invalid calibration factor calculated");
        debugSerial("ERROR: Invalid calibration factor %.6f\n", calibrationFactor);
        debugSerial("NaN check: %s, Inf check: %s, Zero check: %s\n",
            isnan(calibrationFactor) ? "TRUE" : "FALSE",
            isinf(calibrationFactor) ? "TRUE" : "FALSE", 
            (calibrationFactor == 0.0) ? "TRUE" : "FALSE");
        calibrationFactor = 1.0; // Reset to safe default
        return lastError;
    }
    
    isCalibrated = true;
    
    // Standard system logging (permanent)
    LOG_INFO("NAU7802: Scale calibration completed successfully, factor=%.6f", calibrationFactor);
    
    // Temporary debugging (troubleshooting)
    debugSerial("Scale calibration completed successfully, factor=%.6f\n", calibrationFactor);
    debugSerial("Test calculation: %.2f weight -> %.2f result\n", 
        knownWeight, adjustedReading * calibrationFactor);
    
    // Save calibration to EEPROM
    saveCalibration();
    
    return NAU7802_OK;
}

void NAU7802Sensor::setCalibrationFactor(float factor) {
    // Temporary debugging (troubleshooting) - goes to serial only
    debugSerial("setCalibrationFactor called with %.6f\n", factor);
    
    // Validate the factor before setting
    if (isnan(factor) || isinf(factor)) {
        LOG_ERROR("NAU7802: Invalid calibration factor rejected: %.6f", factor);
        debugSerial("ERROR: Attempting to set invalid calibration factor %.6f, rejecting\n", factor);
        return;
    }
    
    calibrationFactor = factor;
    isCalibrated = (factor != 1.0);
    
    // Standard system logging (permanent) - goes to syslog
    LOG_INFO("NAU7802: Calibration factor set to %.6f", factor);
    
    // Temporary debugging (troubleshooting) - goes to serial only
    debugSerial("Calibration factor successfully set to %.6f (calibrated=%s)\n", 
               factor, isCalibrated ? "true" : "false");
}

float NAU7802Sensor::getCalibrationFactor() const {
    return calibrationFactor;
}

bool NAU7802Sensor::isReady() {
    return scale.available();
}

bool NAU7802Sensor::dataAvailable() {
    return scale.available();
}

long NAU7802Sensor::getRawReading() {
    return lastRawReading;
}

float NAU7802Sensor::getWeight() {
    return lastWeight;
}

float NAU7802Sensor::getFilteredWeight() {
    return lastFilteredWeight;
}

void NAU7802Sensor::updateReading() {
    if (!scale.available()) {
        return;
    }
    
    lastRawReading = scale.getReading();
    totalReadings++;
    
    // Update min/max tracking
    if (totalReadings == 1) {
        minReading = lastRawReading;
        maxReading = lastRawReading;
    } else {
        if (lastRawReading < minReading) minReading = lastRawReading;
        if (lastRawReading > maxReading) maxReading = lastRawReading;
    }
    
    lastWeight = applyCalibration(lastRawReading);
    
    if (filteringEnabled) {
        updateFilter(lastWeight);
        
        // Calculate filtered weight
        if (!filterBufferFull && filterIndex == 0) {
            lastFilteredWeight = lastWeight;
        } else {
            float sum = 0;
            uint8_t count = filterBufferFull ? filterSamples : filterIndex;
            
            for (uint8_t i = 0; i < count; i++) {
                sum += filterBuffer[i];
            }
            
            lastFilteredWeight = sum / count;
        }
    } else {
        lastFilteredWeight = lastWeight;
    }
}

void NAU7802Sensor::setGain(uint8_t gain) {
    currentGain = gain;
    scale.setGain(gain);
    debugPrintf("NAU7802: Gain set to %d\n", gain);
}

uint8_t NAU7802Sensor::getGain() const {
    return currentGain;
}

void NAU7802Sensor::setSampleRate(uint8_t rate) {
    currentSampleRate = rate;
    scale.setSampleRate(rate);
    debugPrintf("NAU7802: Sample rate set to %d\n", rate);
}

uint8_t NAU7802Sensor::getSampleRate() const {
    return currentSampleRate;
}

void NAU7802Sensor::tareScale() {
    debugPrintf("NAU7802: Taring scale...\n");
    
    // Take current reading as new zero
    long currentReading = getRawReading();
    if (currentReading != 0) {
        zeroOffset = currentReading;
        debugPrintf("NAU7802: Scale tared, new zero offset=%ld\n", zeroOffset);
        saveCalibration();
    }
}

void NAU7802Sensor::setZeroOffset(long offset) {
    zeroOffset = offset;
    debugPrintf("NAU7802: Zero offset set to %ld\n", offset);
}

long NAU7802Sensor::getZeroOffset() const {
    return zeroOffset;
}

void NAU7802Sensor::enableFiltering(bool enable, uint8_t samples) {
    if (enable && samples > 0 && samples <= 50) {
        if (filterBuffer) {
            delete[] filterBuffer;
        }
        
        filterBuffer = new float[samples];
        filterSamples = samples;
        filterIndex = 0;
        filterBufferFull = false;
        filteringEnabled = true;
        
        debugPrintf("NAU7802: Filtering enabled with %d samples\n", samples);
    } else {
        if (filterBuffer) {
            delete[] filterBuffer;
            filterBuffer = nullptr;
        }
        filteringEnabled = false;
        debugPrintf("NAU7802: Filtering disabled\n");
    }
}

float NAU7802Sensor::getAverageReading(uint8_t samples) {
    float sum = 0;
    uint8_t validSamples = 0;
    
    for (uint8_t i = 0; i < samples; i++) {
        if (scale.available()) {
            float weight = getWeight();
            sum += weight;
            validSamples++;
        }
        delay(50); // Wait between readings
    }
    
    return validSamples > 0 ? sum / validSamples : 0.0;
}

void NAU7802Sensor::resetStatistics() {
    totalReadings = 0;
    minReading = 0;
    maxReading = 0;
}

NAU7802Status NAU7802Sensor::getLastError() const {
    return lastError;
}

const char* NAU7802Sensor::getStatusString() const {
    switch (lastError) {
        case NAU7802_OK: return "OK";
        case NAU7802_NOT_FOUND: return "NOT_FOUND";
        case NAU7802_CALIBRATION_FAILED: return "CALIBRATION_FAILED";
        case NAU7802_READ_ERROR: return "READ_ERROR";
        case NAU7802_NOT_READY: return "NOT_READY";
        default: return "UNKNOWN";
    }
}

uint8_t NAU7802Sensor::getRevisionCode() {
    return scale.getRevisionCode();
}

void NAU7802Sensor::powerUp() {
    scale.powerUp();
    debugPrintf("NAU7802: Powered up\n");
}

void NAU7802Sensor::powerDown() {
    scale.powerDown();
    debugPrintf("NAU7802: Powered down\n");
}

bool NAU7802Sensor::isPoweredUp() {
    // The NAU7802 library doesn't provide a direct way to check power status
    // We'll assume it's powered up if we can communicate with it
    return isConnected();
}

bool NAU7802Sensor::saveCalibration() {
    NAU7802CalibrationData data;
    data.magic = NAU7802_CALIBRATION_MAGIC;
    data.calibrationFactor = calibrationFactor;
    data.zeroOffset = zeroOffset;
    data.gain = currentGain;
    data.sampleRate = currentSampleRate;
    
    // Calculate simple checksum
    data.checksum = (uint32_t)data.magic + 
                   (uint32_t)(data.calibrationFactor * 1000) + 
                   (uint32_t)data.zeroOffset + 
                   data.gain + data.sampleRate;
    
    // Write to EEPROM
    uint8_t* dataPtr = (uint8_t*)&data;
    for (size_t i = 0; i < sizeof(data); i++) {
        EEPROM.write(NAU7802_CALIBRATION_ADDR + i, dataPtr[i]);
    }
    
    debugPrintf("NAU7802: Calibration saved to EEPROM\n");
    return true;
}

bool NAU7802Sensor::loadCalibration() {
    NAU7802CalibrationData data;
    
    // Read from EEPROM
    uint8_t* dataPtr = (uint8_t*)&data;
    for (size_t i = 0; i < sizeof(data); i++) {
        dataPtr[i] = EEPROM.read(NAU7802_CALIBRATION_ADDR + i);
    }
    
    // Verify magic number
    if (data.magic != NAU7802_CALIBRATION_MAGIC) {
        LOG_WARN("NAU7802: No valid calibration found in EEPROM");
        debugSerial("Invalid calibration magic in EEPROM\n");
        return false;
    }
    
    // Verify checksum
    uint32_t calculatedChecksum = (uint32_t)data.magic + 
                                 (uint32_t)(data.calibrationFactor * 1000) + 
                                 (uint32_t)data.zeroOffset + 
                                 data.gain + data.sampleRate;
    
    if (data.checksum != calculatedChecksum) {
        LOG_ERROR("NAU7802: Calibration data corrupted in EEPROM");
        debugSerial("Calibration checksum mismatch in EEPROM\n");
        return false;
    }
    
    // Apply loaded calibration
    LOG_INFO("NAU7802: Loading calibration from EEPROM");
    debugSerial("Loading calibration from EEPROM:\n");
    debugSerial("  Magic: 0x%08X (expected: 0x%08X)\n", data.magic, NAU7802_CALIBRATION_MAGIC);
    debugSerial("  Factor: %.6f\n", data.calibrationFactor);
    debugSerial("  Zero offset: %ld\n", data.zeroOffset);
    debugSerial("  Gain: %d\n", data.gain);
    debugSerial("  Sample rate: %d\n", data.sampleRate);
    
    // Validate calibration factor before applying
    if (isnan(data.calibrationFactor) || isinf(data.calibrationFactor) || data.calibrationFactor == 0.0) {
        LOG_ERROR("NAU7802: Invalid calibration factor in EEPROM: %.6f", data.calibrationFactor);
        debugSerial("ERROR: Invalid calibration factor %.6f in EEPROM, using default\n", data.calibrationFactor);
        calibrationFactor = 1.0;
        isCalibrated = false;
    } else {
        calibrationFactor = data.calibrationFactor;
        isCalibrated = true;
    }
    
    zeroOffset = data.zeroOffset;
    setGain(data.gain);
    setSampleRate(data.sampleRate);
    
    LOG_INFO("NAU7802: Calibration loaded successfully (factor=%.6f, offset=%ld)", 
        calibrationFactor, zeroOffset);
    debugSerial("Calibration loaded from EEPROM (factor=%.6f, offset=%ld)\n", 
        calibrationFactor, zeroOffset);
    return true;
}

void NAU7802Sensor::clearCalibration() {
    // Clear EEPROM by writing zeros
    for (size_t i = 0; i < sizeof(NAU7802CalibrationData); i++) {
        EEPROM.write(NAU7802_CALIBRATION_ADDR + i, 0);
    }
    
    // Reset to defaults
    calibrationFactor = 1.0;
    zeroOffset = 0;
    isCalibrated = false;
    
    debugPrintf("NAU7802: Calibration cleared from EEPROM\n");
}

// Private helper functions
void NAU7802Sensor::initializeDefaults() {
    resetStatistics();
}

float NAU7802Sensor::applyCalibration(long rawValue) {
    float adjustedValue = rawValue - zeroOffset;
    float result = adjustedValue * calibrationFactor;
    
    // Debug: Check for problematic calibration factor
    if (calibrationFactor == 0.0 || isnan(calibrationFactor) || isinf(calibrationFactor)) {
        // System error (permanent) - goes to syslog
        LOG_ERROR("NAU7802: Invalid calibration factor during weight calculation: %.6f", calibrationFactor);
        
        // Temporary debugging (troubleshooting) - goes to serial only
        debugSerial("ERROR in applyCalibration - invalid calibrationFactor=%.6f\n", calibrationFactor);
        debugSerial("  rawValue=%ld, zeroOffset=%ld, adjustedValue=%.2f\n", 
                   rawValue, zeroOffset, adjustedValue);
        return NAN; // Return NaN to indicate error
    }
    
    // Debug: Check for infinite result
    if (isnan(result) || isinf(result)) {
        // System error (permanent) - goes to syslog
        LOG_ERROR("NAU7802: Invalid weight calculation result: %.6f", result);
        
        // Temporary debugging (troubleshooting) - goes to serial only
        debugSerial("ERROR in applyCalibration - invalid result=%.6f\n", result);
        debugSerial("  rawValue=%ld, zeroOffset=%ld, adjustedValue=%.2f, factor=%.6f\n", 
                   rawValue, zeroOffset, adjustedValue, calibrationFactor);
        return NAN;
    }
    
    return result;
}

void NAU7802Sensor::updateFilter(float value) {
    if (!filteringEnabled || !filterBuffer) {
        return;
    }
    
    filterBuffer[filterIndex] = value;
    filterIndex++;
    
    if (filterIndex >= filterSamples) {
        filterIndex = 0;
        filterBufferFull = true;
    }
}

void NAU7802Sensor::logError(NAU7802Status error, const char* function) {
    debugPrintf("NAU7802 ERROR in %s: %s\n", function, getStatusString());
}