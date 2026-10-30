#include "frame.h"
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

static FrameData s_ring[QUEUE_CAPACITY];
static size_t s_head = 0, s_count = 0;
static uint16_t s_dropped = 0;
static FrameData s_latest;
static bool s_hasLatest = false;
static SemaphoreHandle_t s_mux = nullptr;

void frame_clear(FrameData &f) {
  memset(&f, 0, sizeof(f));
  f.acc_max_g = f.acc_min_g = f.acc_mean_g = f.acc_std_g = NAN;
  f.gyro_max_dps = f.gyro_mean_dps = f.tilt_deg = NAN;
  f.fall_detected = TRI_NULL;
  f.finger_on = TRI_NULL;
  f.bpm = f.spo2 = f.perfusion = NAN;
  f.spo2_valid = TRI_NULL;
  f.eda_us = f.eda_slope_us_s = f.eda_baseline_us = f.eda_raw = f.eda_norm = NAN;
  f.skin_c = NAN;
  f.baro_hpa = f.baro_dmax_hpa = NAN;
  f.wet = TRI_NULL;
  f.batt_v = NAN;
  f.lat = f.lng = NAN;
  f.hdop = NAN;
  f.sats = -1;
  f.breached = TRI_NULL;
}

void queue_init() { s_mux = xSemaphoreCreateMutex(); }

// Frames that carry an event: these are what the control room needs after a long outage, so they
// outlive routine frames when the queue overflows.
static bool is_event(const FrameData &f) {
  return f.sos_phase != SOS_NONE || f.fall_detected == TRI_TRUE || f.wet == TRI_TRUE ||
         f.breached == TRI_TRUE || (!isnan(f.acc_max_g) && f.acc_max_g >= EVENT_IMPACT_G);
}

// Full queue: drop the oldest routine frame (keeping seq order), or the oldest frame if all are events.
static void drop_one() {
  size_t victim = 0;
  for (size_t i = 0; i < s_count; i++) {
    if (!is_event(s_ring[(s_head + i) % QUEUE_CAPACITY])) {
      victim = i;
      break;
    }
  }
  for (size_t i = victim; i > 0; i--)  // shift the older frames up by one, then advance the head
    s_ring[(s_head + i) % QUEUE_CAPACITY] = s_ring[(s_head + i - 1) % QUEUE_CAPACITY];
  s_head = (s_head + 1) % QUEUE_CAPACITY;
  s_count--;
  s_dropped++;
}

void queue_push(const FrameData &f) {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  if (s_count == QUEUE_CAPACITY) drop_one();
  s_ring[(s_head + s_count) % QUEUE_CAPACITY] = f;
  s_count++;
  s_latest = f;
  s_hasLatest = true;
  xSemaphoreGive(s_mux);
}

size_t queue_peek_n(FrameData *out, size_t max) {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  size_t n = s_count < max ? s_count : max;
  for (size_t i = 0; i < n; i++) out[i] = s_ring[(s_head + i) % QUEUE_CAPACITY];
  xSemaphoreGive(s_mux);
  return n;
}

void queue_pop_through(uint32_t seq) {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  while (s_count > 0 && s_ring[s_head].seq <= seq) {
    s_head = (s_head + 1) % QUEUE_CAPACITY;
    s_count--;
  }
  xSemaphoreGive(s_mux);
}

size_t queue_size() {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  size_t n = s_count;
  xSemaphoreGive(s_mux);
  return n;
}

uint16_t queue_dropped() {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  uint16_t n = s_dropped;
  xSemaphoreGive(s_mux);
  return n;
}

bool latest_frame(FrameData &out) {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  bool ok = s_hasLatest;
  if (ok) out = s_latest;
  xSemaphoreGive(s_mux);
  return ok;
}
