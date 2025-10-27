#ifndef HEARTBEAT_ANIMATION_H
#define HEARTBEAT_ANIMATION_H

#include <Arduino.h>

/**
 * @class HeartbeatAnimation
 * @brief Manages spinner animation on Arduino R4 WiFi LED matrix
 * 
 * Provides a simple spinning activity indicator in the top right corner
 * of the LED matrix, updating every second.
 */
class HeartbeatAnimation {
private:
  bool isEnabled;
  uint8_t currentBrightness;
  
  // Spinner animation in top right corner
  uint8_t spinnerFrame;
  unsigned long lastSpinnerTime;
  
public:
  HeartbeatAnimation();
  
  /**
   * Initialize the LED matrix and start animation
   */
  void begin();
  
  /**
   * Update animation - call this frequently in main loop
   */
  void update();
  
  /**
   * Enable spinner animation
   */
  void enable();
  
  /**
   * Disable spinner animation and clear display
   */
  void disable();
  
  /**
   * Set LED matrix brightness
   * @param brightness 0-255 (0=off, 255=max brightness)
   */
  void setBrightness(uint8_t brightness);
  
  /**
   * Check if animation is currently enabled
   * @return true if enabled, false if disabled
   */
  bool getEnabled() const;
  
  /**
   * Get current brightness
   * @return Current brightness (0-255)
   */
  uint8_t getBrightness() const;
  
  /**
   * Clear the LED matrix display
   */
  void clear();

private:
  /**
   * Display current spinner frame
   */
  void displaySpinner();
};

#endif // HEARTBEAT_ANIMATION_H