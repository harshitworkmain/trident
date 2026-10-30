// Battery voltage through a 100k/100k divider on ADC1 (calibrated millivolt read).
#include "config.h"
#include "sensors.h"

static volatile float s_battV = NAN;

void power_begin() {
  analogSetPinAttenuation(PIN_BATT, ADC_11db);
  power_sample();
}

void power_sample() {
  float v = analogReadMilliVolts(PIN_BATT) * BATT_DIVIDER / 1000.0f;
  s_battV = (v >= 2.5f && v <= 4.5f) ? v : NAN;  // no battery / USB only -> unavailable
}

void power_close(FrameData &f) { f.batt_v = s_battV; }
