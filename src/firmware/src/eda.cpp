// Grove GSR -> skin conductance (uS), so the device reports the same unit as WESAD/PPG-DaLiA.
// Seeed's formula R = ((1024 + 2r) * 10000) / (512 - r) is written for a 10-bit ADC; scaled to
// the ESP32's 12-bit ADC: R = ((4096 + 2r) * 10000) / (cal_open - r), with cal_open the
// open-circuit (sensor off skin) reading.
#include "config.h"
#include "sensors.h"
#include "settings.h"

static bool s_ok = false;
static int s_buf[GSR_SMOOTH_SAMPLES];
static int s_idx = 0;
static float s_smooth = NAN;
static float s_sum = 0;
static uint32_t s_n = 0;
static float s_prevUs = NAN;
static uint32_t s_prevMs = 0;  // uptime_ms of the frame that set s_prevUs
static volatile bool s_reqBaseline = false, s_reqOpen = false;

static float raw_to_us(float raw, float calOpen) {
  if (raw <= 10.0f || calOpen - raw < 1.0f) return NAN;
  float ohms = ((4096.0f + 2.0f * raw) * 10000.0f) / (calOpen - raw);
  return ohms > 0 ? 1e6f / ohms : NAN;
}

bool eda_begin() {
  analogSetPinAttenuation(PIN_GSR, ADC_11db);
  int r = analogRead(PIN_GSR);
  for (int i = 0; i < GSR_SMOOTH_SAMPLES; i++) s_buf[i] = r;
  s_ok = r > 10 && r < 4090;  // floating or shorted input -> treat as absent
  return s_ok;
}

void eda_sample() {
  s_buf[s_idx] = analogRead(PIN_GSR);
  s_idx = (s_idx + 1) % GSR_SMOOTH_SAMPLES;
  long sum = 0;
  for (int i = 0; i < GSR_SMOOTH_SAMPLES; i++) sum += s_buf[i];
  s_smooth = (float)sum / GSR_SMOOTH_SAMPLES;
  s_sum += s_smooth;
  s_n++;
}

void eda_request_baseline() { s_reqBaseline = true; }
void eda_request_open_circuit() { s_reqOpen = true; }

void eda_close(FrameData &f) {
  float raw = s_n ? s_sum / s_n : NAN;
  s_sum = 0;
  s_n = 0;
  s_ok = !isnan(raw) && raw > 10 && raw < 4090;
  f.gsr_ok = s_ok;

  Settings st = settings_get();
  if (s_reqOpen && !isnan(raw)) {  // must be done with the electrodes OFF the skin
    st.gsr_open = raw;
    settings_set(st);
    Serial.printf("[eda] open-circuit reference = %.0f\n", raw);
  }
  s_reqOpen = false;

  float us = raw_to_us(raw, st.gsr_open);
  if (s_reqBaseline && !isnan(us)) {
    st.gsr_baseline_us = us;
    st.gsr_baseline_raw = raw;
    settings_set(st);
    Serial.printf("[eda] on-skin baseline = %.3f uS\n", us);
  }
  s_reqBaseline = false;

  if (!s_ok) {
    s_prevUs = NAN;
    return;
  }
  f.eda_raw = raw;
  f.eda_us = us;
  // Over the real frame length: a frame closed early for an SOS is shorter than 1.5 s.
  uint32_t dtMs = f.uptime_ms - s_prevMs;
  if (!isnan(us) && !isnan(s_prevUs) && dtMs > 0) f.eda_slope_us_s = (us - s_prevUs) / (dtMs / 1000.0f);
  s_prevUs = us;
  s_prevMs = f.uptime_ms;
  f.eda_baseline_us = st.gsr_baseline_us;
  // Relative conductance rise over the resting baseline, clipped to [0, 1]
  // (feeds the legacy dashboard Low/Medium/High bands).
  if (!isnan(us) && !isnan(st.gsr_baseline_us) && st.gsr_baseline_us > 0) {
    f.eda_norm = fminf(1.0f, fmaxf(0.0f, (us - st.gsr_baseline_us) / st.gsr_baseline_us));
  }
}
