// Build-time configuration: identity, pins, sampling rates and detection thresholds.
#pragma once
#include <Arduino.h>

#define FW_VERSION "2.2.0"
#define DEVICE_ID "TRIDENT-WEAR-01"
#define TELEMETRY_PATH "/api/v1/telemetry"  // TELEMETRY_URL in secrets.h must end with this

// ---- Pins (all analog inputs on ADC1: ADC2 is unusable while Wi-Fi is active) ----
constexpr int PIN_I2C_SDA = 21;
constexpr int PIN_I2C_SCL = 22;
constexpr int PIN_BUZZER = 25;
constexpr int PIN_GSR = 34;           // Grove GSR SIG (ADC1_CH6)
constexpr int PIN_WATER_SENSE = 33;   // water electrode B (ADC1_CH5) + 1 MOhm pull-down
constexpr int PIN_WATER_EXCITE = 26;  // water electrode A, driven only while measuring
constexpr int PIN_BATT = 35;          // battery via 100k/100k divider (ADC1_CH7)
constexpr int PIN_GPS_RX = 16;        // ESP32 RX  <- GPS TX
constexpr int PIN_GPS_TX = 17;        // ESP32 TX  -> GPS RX
constexpr int PIN_SOS_BUTTON = 27;    // momentary push button to GND (INPUT_PULLUP); 0 = DevKit BOOT
constexpr uint32_t I2C_HZ = 400000;

// ---- I2C addresses ----
constexpr uint8_t ADDR_MPU6050 = 0x68;
constexpr uint8_t ADDR_MAX30205 = 0x48;
constexpr uint8_t ADDR_BMP388 = 0x77;  // 0x76 tried as fallback

// ---- Timing (must match src/ml/wearable/schema.py: FRAME_PERIOD_S = 1.5, IMU_HZ = 50) ----
constexpr uint32_t FAST_TICK_MS = 10;     // 100 Hz scheduler (PPG FIFO poll)
constexpr uint32_t IMU_EVERY_TICKS = 2;   // 50 Hz
constexpr uint32_t EDA_EVERY_TICKS = 5;   // 20 Hz
constexpr uint32_t FRAME_TICKS = 150;     // 1.5 s
constexpr uint32_t SLOW_TICK_MS = 40;     // 25 Hz scheduler (barometer, GPS UART)
constexpr uint32_t TEMP_EVERY_TICKS = 25;    // 1 Hz
constexpr uint32_t WATER_EVERY_TICKS = 12;   // ~2 Hz
constexpr uint32_t POWER_EVERY_TICKS = 125;  // 0.2 Hz

// ---- Queue / network ----
constexpr size_t QUEUE_CAPACITY = 320;    // 8 minutes of frames buffered while offline (~50 KB RAM)
constexpr float EVENT_IMPACT_G = 3.0f;      // frames above this peak are kept over routine ones when full
constexpr size_t RR_MAX_PER_FRAME = 16;
constexpr size_t BATCH_MAX_FRAMES = 10;   // frames per POST (~0.8 kB each -> ~8 kB body)
constexpr size_t PENDING_ACKS_MAX = 16;   // executed command ids awaiting the next request
constexpr uint32_t HTTP_TIMEOUT_MS = 5000;
constexpr uint32_t BACKOFF_MIN_MS = 1000;      // 429/5xx/timeout: 1, 2, 4 .. 30 s, with jitter
constexpr uint32_t BACKOFF_MAX_MS = 30000;
constexpr uint32_t AUTH_BACKOFF_MS = 60000;    // 401/403/404: wrong key or URL, retry slowly
constexpr uint32_t RETRY_AFTER_MAX_MS = 60000; // cap on a server-sent Retry-After
constexpr uint32_t SERVER_STATE_TTL_MS = 60000;  // server alert state expires without updates
constexpr uint32_t SEQ_BLOCK = 4000;      // seq numbers reserved in NVS per write (~100 min)

// ---- SOS button ----
constexpr uint32_t SOS_POLL_MS = 10;          // button task period
constexpr uint32_t SOS_DEBOUNCE_MS = 30;      // level must be stable this long
constexpr uint32_t SOS_HOLD_MS = 1500;        // hold to raise an SOS
constexpr uint8_t SOS_TAPS = 3;               // ... or this many presses
constexpr uint32_t SOS_TAP_WINDOW_MS = 2000;  // ... within this window (first to last press)
constexpr uint32_t SOS_CANCEL_HOLD_MS = 5000; // hold (a new press) while active to cancel
constexpr uint32_t SOS_REMINDER_MS = 10000;   // short beep while not yet acknowledged
constexpr uint8_t SOS_CANCEL_FRAMES = 10;     // frames carrying the cancel, unless acked earlier
constexpr uint32_t SOS_RETRY_MAX_MS = 3000;   // upload retry cap while an SOS is unacknowledged

// ---- Buzzer ----
constexpr uint32_t BUZZ_MAX_MS = 10000;   // cap for the remote "buzz" command

// ---- PPG (MAX30102) ----
constexpr uint32_t FINGER_IR_MIN = 30000;  // IR DC level indicating skin contact
constexpr uint32_t RR_MIN_MS = 270;        // same acceptance window as schema.py
constexpr uint32_t RR_MAX_MS = 2000;
constexpr uint32_t BPM_LOST_MS = 4000;     // no beat for this long -> bpm unavailable
constexpr uint32_t SPO2_MAX_AGE_MS = 3000;

// ---- On-device fall detector (edge safety net) ----
constexpr float FALL_FREEFALL_G = 0.5f;
constexpr float FALL_IMPACT_G = 3.0f;
constexpr uint32_t FALL_IMPACT_WINDOW_MS = 1000;  // impact must follow free fall within this
constexpr uint32_t FALL_SETTLE_MS = 1000;         // ignore rebound after impact
constexpr uint32_t FALL_STILL_MS = 2000;          // stillness window that confirms the fall
constexpr float FALL_STILL_STD_G = 0.15f;
constexpr float FALL_STILL_GYRO_DPS = 40.0f;

// ---- EDA (Grove GSR) ----
constexpr float GSR_OPEN_DEFAULT = 2048.0f;  // open-circuit ADC reading until calibrated
constexpr int GSR_SMOOTH_SAMPLES = 10;

// ---- Water / power ----
constexpr int WATER_WET_RAW = 600;   // ~0.5 V across the 1 MOhm pull-down
constexpr int WATER_DEBOUNCE = 3;    // consecutive readings to change state
constexpr float BATT_DIVIDER = 2.0f;
