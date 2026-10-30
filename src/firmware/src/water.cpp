// Water-contact electrodes: A on PIN_WATER_EXCITE, B on PIN_WATER_SENSE with a 1 MOhm pull-down.
// A is driven high only during the reading to limit electrolysis and electrode corrosion.
#include "config.h"
#include "sensors.h"

static volatile bool s_wet = false;
static int s_votes = 0;

void water_begin() {
  pinMode(PIN_WATER_EXCITE, OUTPUT);
  digitalWrite(PIN_WATER_EXCITE, LOW);
  analogSetPinAttenuation(PIN_WATER_SENSE, ADC_11db);
}

void water_sample() {
  digitalWrite(PIN_WATER_EXCITE, HIGH);
  delayMicroseconds(300);
  int raw = analogRead(PIN_WATER_SENSE);
  digitalWrite(PIN_WATER_EXCITE, LOW);
  bool reading = raw > WATER_WET_RAW;
  if (reading != s_wet) {
    if (++s_votes >= WATER_DEBOUNCE) { s_wet = reading; s_votes = 0; }
  } else {
    s_votes = 0;
  }
}

void water_close(FrameData &f) { f.wet = s_wet ? TRI_TRUE : TRI_FALSE; }
