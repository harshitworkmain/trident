// BMP388 barometer, 25 Hz. Frame reports mean pressure and the max-min swing within the frame:
// a 0.5-2 m fall is ~0.06-0.24 hPa, submersion adds ~98 hPa per metre of water.
#include <Adafruit_BMP3XX.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"
#include "i2c_bus.h"
#include "sensors.h"

static Adafruit_BMP3XX s_bmp;
static SemaphoreHandle_t s_mux = nullptr;
static bool s_ok = false;
static double s_sum = 0;
static uint16_t s_n = 0;
static float s_max = -1e9f, s_min = 1e9f;

bool baro_begin() {
  s_mux = xSemaphoreCreateMutex();
  i2c_lock();
  bool ok = s_bmp.begin_I2C(ADDR_BMP388, &Wire) || s_bmp.begin_I2C(0x76, &Wire);
  if (ok) {
    s_bmp.setTemperatureOversampling(BMP3_NO_OVERSAMPLING);
    s_bmp.setPressureOversampling(BMP3_OVERSAMPLING_2X);
    s_bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_3);
    s_bmp.setOutputDataRate(BMP3_ODR_25_HZ);
  }
  i2c_unlock();
  s_ok = ok;
  return ok;
}

void baro_sample() {
  if (!s_ok) return;
  i2c_lock();
  bool ok = s_bmp.performReading();
  float hpa = s_bmp.pressure / 100.0f;
  i2c_unlock();
  if (!ok || hpa < 300 || hpa > 1300) return;
  xSemaphoreTake(s_mux, portMAX_DELAY);
  s_sum += hpa;
  s_n++;
  s_max = fmaxf(s_max, hpa);
  s_min = fminf(s_min, hpa);
  xSemaphoreGive(s_mux);
}

void baro_close(FrameData &f) {
  f.baro_ok = s_ok;
  if (!s_mux) return;
  xSemaphoreTake(s_mux, portMAX_DELAY);
  if (s_n) {
    f.baro_hpa = s_sum / s_n;
    f.baro_dmax_hpa = s_max - s_min;
  }
  s_sum = 0;
  s_n = 0;
  s_max = -1e9f;
  s_min = 1e9f;
  xSemaphoreGive(s_mux);
}
