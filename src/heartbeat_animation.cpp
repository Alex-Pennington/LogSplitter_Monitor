#include "heartbeat_animation.h"
#include "Arduino_LED_Matrix.h"

ArduinoLEDMatrix matrix;

HeartbeatAnimation::HeartbeatAnimation() {
  isEnabled = false;
  currentBrightness = 128;
  spinnerFrame = 0;
  lastSpinnerTime = 0;
}

void HeartbeatAnimation::begin() {
  matrix.begin();
  isEnabled = true;
  spinnerFrame = 0;
  lastSpinnerTime = millis();
}

void HeartbeatAnimation::update() {
  if (!isEnabled) return;
  
  unsigned long currentTime = millis();
  
  if (currentTime - lastSpinnerTime >= 1000) {
    spinnerFrame = (spinnerFrame + 1) % 4;
    lastSpinnerTime = currentTime;
    displaySpinner();
  }
}

void HeartbeatAnimation::enable() {
  if (!isEnabled) {
    matrix.begin();
    isEnabled = true;
    spinnerFrame = 0;
    lastSpinnerTime = millis();
  }
}

void HeartbeatAnimation::disable() {
  if (isEnabled) {
    isEnabled = false;
    matrix.clear();
  }
}

void HeartbeatAnimation::setBrightness(uint8_t brightness) {
  currentBrightness = brightness;
}

bool HeartbeatAnimation::getEnabled() const {
  return isEnabled;
}

uint8_t HeartbeatAnimation::getBrightness() const {
  return currentBrightness;
}

void HeartbeatAnimation::clear() {
  matrix.clear();
}

void HeartbeatAnimation::displaySpinner() {
  uint32_t frame[3] = {0, 0, 0};
  
  if (spinnerFrame == 0) {
    for (int col = 9; col <= 11; col++) {
      int bitIndex = 0 * 12 + col;
      int wordIndex = bitIndex / 32;
      int bitPos = bitIndex % 32;
      if (wordIndex < 3) {
        frame[wordIndex] |= (1UL << (31 - bitPos));
      }
    }
  } else if (spinnerFrame == 1) {
    int positions[][2] = {{0, 11}, {1, 10}, {2, 9}};
    for (int i = 0; i < 3; i++) {
      int bitIndex = positions[i][0] * 12 + positions[i][1];
      int wordIndex = bitIndex / 32;
      int bitPos = bitIndex % 32;
      if (wordIndex < 3) {
        frame[wordIndex] |= (1UL << (31 - bitPos));
      }
    }
  } else if (spinnerFrame == 2) {
    for (int row = 0; row <= 2; row++) {
      int bitIndex = row * 12 + 11;
      int wordIndex = bitIndex / 32;
      int bitPos = bitIndex % 32;
      if (wordIndex < 3) {
        frame[wordIndex] |= (1UL << (31 - bitPos));
      }
    }
  } else if (spinnerFrame == 3) {
    int positions[][2] = {{0, 9}, {1, 10}, {2, 11}};
    for (int i = 0; i < 3; i++) {
      int bitIndex = positions[i][0] * 12 + positions[i][1];
      int wordIndex = bitIndex / 32;
      int bitPos = bitIndex % 32;
      if (wordIndex < 3) {
        frame[wordIndex] |= (1UL << (31 - bitPos));
      }
    }
  }
  
  matrix.loadFrame(frame);
}