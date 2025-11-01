#include "safety_system.h"
#include "relay_controller.h"
#include "telemetry_manager.h"
// NetworkManager include removed - non-networking version
#include "sequence_controller.h"
#include "logger.h"

extern void debugPrintf(const char* fmt, ...);
extern TelemetryManager telemetryManager;

void SafetySystem::begin() {
    // Initialize pin 11 (safety status LED)
    pinMode(SAFETY_STATUS_PIN, OUTPUT);
    digitalWrite(SAFETY_STATUS_PIN, LOW);
    safetyStatusLedState = false;
    pressureLimitUsedPersistent = false;
    
    // Initialize engine to running state (turn ON Relay 8 - engine runs when relay is ON)
    debugPrintf("SafetySystem: Initializing engine to running state...\n");
    
    // Small delay to ensure relay board is ready after power-on
    delay(100);
    
    // Force engine initialization by setting it to stopped first, then starting
    engineStopped = true;  // Force state change
    setEngineStop(false);  // Start engine on system startup
    LOG_WARN("SafetySystem: Engine started - relay R8 initialized to ON (running state)");
    debugPrintf("SafetySystem: Engine and safety status LED initialization complete\n");
}

void SafetySystem::setEngineStop(bool stop) {
    if (engineStopped != stop) {
        engineStopped = stop;
        
        // Control engine via Relay 8 through relay controller
        // Engine ON = Relay R8 ON, Engine OFF = Relay R8 OFF
        if (relayController) {
            relayController->setRelay(RELAY_ENGINE_STOP, !stop, false); // Invert: !stop means ON when not stopping
            debugPrintf("Engine %s via relay R%d %s\n", stop ? "STOPPED" : "STARTED", RELAY_ENGINE_STOP, stop ? "OFF" : "ON");
        } else {
            debugPrintf("Engine control failed - relay controller not available\n");
        }
        
        // Network publishing removed - non-networking version
    }
}

void SafetySystem::update(float currentPressure) {
    lastPressure = currentPressure;
    
    // Check if cylinder is at end-of-travel (limit switches)
    extern bool g_limitExtendActive;
    extern bool g_limitRetractActive;
    bool atLimitSwitch = g_limitExtendActive || g_limitRetractActive;
    
    checkPressure(currentPressure, atLimitSwitch);
    
    // Update safety status LED (pin 11)
    updateSafetyStatusLed();
    
    lastSafetyCheck = millis();
}

void SafetySystem::checkPressure(float pressure) {
    checkPressure(pressure, false); // Default: not at limit switch
}

void SafetySystem::checkPressure(float pressure, bool atLimitSwitch) {
    unsigned long now = millis();
    
    // Check for sustained high pressure (E-stop trigger)
    if (pressure >= HIGH_PRESSURE_ESTOP_THRESHOLD) {  // 2300 PSI
        if (!highPressureActive) {
            // Start timing high pressure condition
            highPressureActive = true;
            highPressureStartTime = now;
            debugPrintf("High pressure detected: %.1f PSI >= %.1f PSI - starting 10s timer\n", 
                       pressure, HIGH_PRESSURE_ESTOP_THRESHOLD);
        } else {
            // Check if sustained for too long
            if (now - highPressureStartTime >= HIGH_PRESSURE_TIMEOUT_MS) {
                if (!eStopActive) {  // Only trigger if E-stop not already active
                    LOG_CRITICAL("Sustained high pressure %.1f PSI for %lu ms - triggering E-stop", 
                                pressure, now - highPressureStartTime);
                    activateEStop();  // Trigger E-stop due to sustained pressure
                }
            }
        }
    } else {
        // Pressure dropped below E-stop threshold - reset timer
        if (highPressureActive) {
            debugPrintf("High pressure cleared: %.1f PSI < %.1f PSI after %lu ms\n", 
                       pressure, HIGH_PRESSURE_ESTOP_THRESHOLD, now - highPressureStartTime);
            highPressureActive = false;
            highPressureStartTime = 0;
        }
    }
    
    // Original safety threshold logic (2500 PSI)
    if (pressure >= SAFETY_THRESHOLD_PSI) {
        if (!safetyActive) {
            const char* reason = atLimitSwitch ? "pressure_at_limit" : "pressure_threshold";
            activate(reason);
        }
    } else if (pressure < (SAFETY_THRESHOLD_PSI - SAFETY_HYSTERESIS_PSI)) {
        if (safetyActive) {
            // Pressure dropped below threshold with hysteresis - BUT DO NOT AUTO-CLEAR
            // Safety system should only be cleared manually via safety clear button
            debugPrintf("Pressure normalized: %.1f PSI below threshold - safety remains active (manual clear required)\n", pressure);
            
            // Network publishing removed - non-networking version
            
            // DO NOT automatically clear safety - must be done via safety clear button
            // safetyActive remains true until manual intervention
        }
    }
}

void SafetySystem::activate(const char* reason) {
    if (safetyActive) return; // Already active
    
    safetyActive = true;
    
    debugPrintf("SAFETY ACTIVATED: %s (pressure=%.1f PSI)\n", 
        reason ? reason : "unknown", lastPressure);
    
    // Send telemetry for safety activation
    telemetryManager.sendSafetyEvent(1, true); // 1 = safety activation event
    
    // Emergency stop sequence
    emergencyStop(reason);
    
    // Network publishing removed - non-networking version
}

void SafetySystem::emergencyStop(const char* reason) {
    // Abort any active sequence
    if (sequenceController && sequenceController->isActive()) {
        sequenceController->abort();
    }
    
    // Turn off all operational relays (keep power relay as-is)
    if (relayController) {
        relayController->enableSafety(); // This will block future AUTOMATIC relay operations
        
        // Turn off hydraulic relays immediately
        relayController->setRelay(RELAY_EXTEND, false, false);   // false = automatic operation
        relayController->setRelay(RELAY_RETRACT, false, false);  // false = automatic operation
        
        // Turn off other operational relays (3-8 available for future use)
        for (uint8_t i = 3; i <= 8; i++) {
            relayController->setRelay(i, false, false); // false = automatic operation
        }
        
        // Turn ON relay 9 for E-stop condition indication
        if (eStopActive) {
            relayController->setRelay(9, true, false);  // Turn on relay 9 during E-stop
        }
    }
    
    // SAFETY CRITICAL: Stop engine immediately via relay controller
    setEngineStop(true);
    LOG_CRITICAL("SAFETY: Engine stopped via relay R%d", RELAY_ENGINE_STOP);
    
    Serial.print("EMERGENCY STOP: ");
    Serial.println(reason ? reason : "unknown");
    Serial.println("Manual relay control still available for pressure relief");
}

void SafetySystem::activateEStop() {
    if (eStopActive) return; // Already active
    
    eStopActive = true;
    safetyActive = true;  // E-stop also activates general safety
    
    debugPrintf("E-STOP ACTIVATED - Emergency shutdown initiated\n");
    
    // Send telemetry for e-stop activation
    telemetryManager.sendSafetyEvent(2, true); // 2 = e-stop activation event
    
    // Emergency stop sequence with E-stop specific handling
    emergencyStop("e_stop_pressed");
    
    // Network publishing removed - non-networking version
}

void SafetySystem::clearEStop() {
    if (!eStopActive) return; // Not active
    
    eStopActive = false;
    
    // Reset high pressure monitoring when E-stop is cleared
    highPressureActive = false;
    highPressureStartTime = 0;
    
    debugPrintf("E-STOP: Cleared via safety clear button - high pressure timer reset\n");
    
    // Send telemetry for e-stop clear
    telemetryManager.sendSafetyEvent(2, false); // 2 = e-stop event, false = cleared
    
    // Turn OFF relay 9 when E-stop is cleared
    if (relayController) {
        relayController->setRelay(9, false, false);  // Turn off relay 9
    }
    
    // Clear general safety system
    if (safetyActive) {
        deactivate();
    }
    
    // Network publishing removed - non-networking version
}

void SafetySystem::deactivate() {
    if (!safetyActive) return;
    
    safetyActive = false;
    
    debugPrintf("Safety system deactivated manually\n");
    
    // Send telemetry for safety deactivation
    telemetryManager.sendSafetyEvent(1, false); // 1 = safety event, false = deactivated
    
    if (relayController) {
        relayController->disableSafety();
    }
    
    // Restart engine when safety is cleared
    setEngineStop(false);
    Serial.println("Engine restarted - safety system deactivated");
    
    // Network publishing removed - non-networking version
}

void SafetySystem::clearEmergencyStop() {
    if (safetyActive || eStopActive) {
        Serial.println("Safety system cleared via E-Stop reset");
        
        // Network publishing removed - non-networking version
        
        // Clear E-stop state first
        if (eStopActive) {
            clearEStop();
        } else {
            deactivate();
        }
    }
}

void SafetySystem::getStatusString(char* buffer, size_t bufferSize) {
    unsigned long highPressureElapsed = 0;
    if (highPressureActive && highPressureStartTime > 0) {
        highPressureElapsed = millis() - highPressureStartTime;
    }
    
    snprintf(buffer, bufferSize, 
        "safety=%s estop=%s engine=%s pressure=%.1f threshold=%.1f highP=%s elapsed=%lums",
        safetyActive ? "ACTIVE" : "OK",
        eStopActive ? "ACTIVE" : "OK",
        engineStopped ? "STOPPED" : "RUNNING",
        lastPressure,
        SAFETY_THRESHOLD_PSI,
        highPressureActive ? "ACTIVE" : "OK",
        highPressureElapsed
    );
}

void SafetySystem::publishIndividualValues() {
    // Network publishing removed - non-networking version
    // Safety status available via getStatusString() for serial output
}

void SafetySystem::markPressureLimitUsed() {
    // Mark that pressure limits were used - this is persistent until power reset
    if (!pressureLimitUsedPersistent) {
        pressureLimitUsedPersistent = true;
        debugPrintf("SafetySystem: Pressure limit usage detected - pin 11 will flash until power reset\n");
    }
}

void SafetySystem::updateSafetyStatusLed() {
    unsigned long currentTime = millis();
    
    // Determine LED behavior:
    // SOLID ON: Safety system has stopped the system
    // FLASHING: Pressure limit system used (persistent until power reset)
    // OFF: Normal operation
    
    if (safetyActive || eStopActive) {
        // SOLID ON: Safety system has stopped the system
        if (!safetyStatusLedState) {
            digitalWrite(SAFETY_STATUS_PIN, HIGH);
            safetyStatusLedState = true;
            telemetryManager.sendDigitalOutput(SAFETY_STATUS_PIN, true, Telemetry::OUTPUT_SAFETY_STATUS, "solid");
            debugPrintf("SafetySystem: Pin 11 SOLID ON - safety system active\n");
        }
    } else if (pressureLimitUsedPersistent) {
        // FLASHING: Pressure limit system was used (persistent until power reset)
        if (currentTime - lastSafetyStatusBlink >= SAFETY_STATUS_BLINK_INTERVAL_MS) {
            safetyStatusLedState = !safetyStatusLedState;
            digitalWrite(SAFETY_STATUS_PIN, safetyStatusLedState ? HIGH : LOW);
            telemetryManager.sendDigitalOutput(SAFETY_STATUS_PIN, safetyStatusLedState, Telemetry::OUTPUT_SAFETY_STATUS, "flashing");
            lastSafetyStatusBlink = currentTime;
        }
    } else {
        // OFF: Normal operation
        if (safetyStatusLedState) {
            digitalWrite(SAFETY_STATUS_PIN, LOW);
            safetyStatusLedState = false;
            telemetryManager.sendDigitalOutput(SAFETY_STATUS_PIN, false, Telemetry::OUTPUT_SAFETY_STATUS, "off");
            debugPrintf("SafetySystem: Pin 11 OFF - normal operation\n");
        }
    }
}