// Sensor module interfaces. Each module samples on its task's tick and fills its part of a
// FrameData when the frame closes. "Fast" modules run on the fast task, "slow" ones on the
// slow task; slow modules guard their accumulators internally because the fast task closes
// the frame.
#pragma once
#include <Arduino.h>
#include "frame.h"

// ---- IMU: MPU6050, 50 Hz, +/-16 g, +/-2000 deg/s (fast task) ----
bool imu_begin();
void imu_sample(uint32_t now_ms);
void imu_close(FrameData &f);
void imu_reset_fall();
bool imu_fall_latched();

// ---- PPG: MAX30102, 100 Hz FIFO, beats/RR + SpO2 (fast task) ----
bool ppg_begin();
void ppg_poll();
void ppg_close(FrameData &f, uint32_t now_ms);

// ---- EDA: Grove GSR on ADC1, 20 Hz (fast task) ----
bool eda_begin();
void eda_sample();
void eda_close(FrameData &f);
void eda_request_baseline();      // remote "calibrate_gsr": current on-skin level = baseline
void eda_request_open_circuit();  // remote "calibrate_gsr_open": sensor off skin, record ref

// ---- Skin temperature: MAX30205 (slow task) ----
bool skintemp_begin();
void skintemp_sample();
void skintemp_close(FrameData &f);

// ---- Barometer: BMP388 (slow task) ----
bool baro_begin();
void baro_sample();
void baro_close(FrameData &f);

// ---- Water contact electrodes (slow task) ----
void water_begin();
void water_sample();
void water_close(FrameData &f);

// ---- Battery voltage (slow task) ----
void power_begin();
void power_sample();
void power_close(FrameData &f);

// ---- GPS: NEO-6M on UART1 + geofence (slow task) ----
void gps_begin();
void gps_poll();
void gps_close(FrameData &f);
bool gps_breached_latched();
