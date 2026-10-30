// MAX30205 skin temperature (+/-0.1 degC), 1 Hz, minimal register driver.
// Sampled on the slow task, closed by the fast task -> accumulators behind a mutex.
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"
#include "i2c_bus.h"
#include "sensors.h"

static SemaphoreHandle_t s_mux = nullptr;
static bool s_ok = false;
static float s_sum = 0;
static uint16_t s_n = 0;
static float s_last = NAN;

static bool read_celsius(float &c) {
  uint8_t b[2];
  i2c_lock();
  bool ok = i2c_read_regs(ADDR_MAX30205, 0x00, b, 2);
  i2c_unlock();
  if (!ok) return false;
  c = (int16_t)((b[0] << 8) | b[1]) / 256.0f;
  return c > 10.0f && c < 45.0f;
}

bool skintemp_begin() {
  s_mux = xSemaphoreCreateMutex();
  float c;
  s_ok = read_celsius(c);  // power-on default is continuous conversion
  return s_ok;
}

void skintemp_sample() {
  float c;
  bool ok = read_celsius(c);
  xSemaphoreTake(s_mux, portMAX_DELAY);
  s_ok = ok;
  if (ok) { s_sum += c; s_n++; s_last = c; }
  xSemaphoreGive(s_mux);
}

void skintemp_close(FrameData &f) {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  f.temp_ok = s_ok;
  // 1 Hz sensor vs 1.5 s frames: some frames get no new reading, reuse the last one
  if (s_n) f.skin_c = s_sum / s_n;
  else if (s_ok) f.skin_c = s_last;
  s_sum = 0;
  s_n = 0;
  xSemaphoreGive(s_mux);
}
