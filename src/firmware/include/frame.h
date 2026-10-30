// One 1.5 s telemetry frame (schema 2) and the bounded FIFO that buffers frames for upload.
// Floats use NAN for "unavailable" (serialised as JSON null); tri-state flags use -1.
#pragma once
#include <Arduino.h>
#include "config.h"

enum Tri : int8_t { TRI_NULL = -1, TRI_FALSE = 0, TRI_TRUE = 1 };
enum SosPhase : uint8_t { SOS_NONE = 0, SOS_ACTIVE = 1, SOS_CANCELLED = 2 };

struct FrameData {
  uint32_t seq;
  uint32_t uptime_ms;

  // imu
  float acc_max_g, acc_min_g, acc_mean_g, acc_std_g;
  float gyro_max_dps, gyro_mean_dps, tilt_deg;
  uint16_t imu_n;
  Tri fall_detected;

  // ppg
  Tri finger_on;
  float bpm, spo2, perfusion;
  Tri spo2_valid;
  uint8_t rr_count;
  uint16_t rr_ms[RR_MAX_PER_FRAME];

  // eda
  float eda_us, eda_slope_us_s, eda_baseline_us, eda_raw, eda_norm;

  // temp / baro / water / power
  float skin_c;
  float baro_hpa, baro_dmax_hpa;
  Tri wet;
  float batt_v;

  // gps
  double lat, lng;
  float hdop;
  int16_t sats;  // -1 = unavailable
  Tri breached;

  // device health (sent in the non-schema "sys" group)
  bool mpu_ok, max_ok, gsr_ok, temp_ok, baro_ok, gps_fix;
  uint16_t queue_dropped;

  // SOS button (sent in the non-schema "sos" group when not SOS_NONE)
  SosPhase sos_phase;
  uint32_t sos_press_id, sos_pressed_ms;
};

void frame_clear(FrameData &f);

// Thread-safe bounded FIFO: the sensor task pushes closed frames, the network task peeks a
// batch and pops it after a successful upload. When full, the oldest *routine* frame is dropped
// (event frames - SOS, fall, impact, water, geofence - are kept), so the network task pops by seq
// (not by count): frames dropped while a POST is in flight are not confused with the ones sent.
void queue_init();
void queue_push(const FrameData &f);
size_t queue_peek_n(FrameData *out, size_t max);  // oldest first, returns count copied
void queue_pop_through(uint32_t seq);              // pop leading frames with seq <= seq
size_t queue_size();
uint16_t queue_dropped();
bool latest_frame(FrameData &out);  // most recently closed frame (for the local web UI)
