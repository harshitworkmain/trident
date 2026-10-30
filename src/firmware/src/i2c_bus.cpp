#include "i2c_bus.h"
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"

static SemaphoreHandle_t s_mux = nullptr;

void i2c_init() {
  s_mux = xSemaphoreCreateMutex();
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(I2C_HZ);
}

void i2c_lock() { xSemaphoreTake(s_mux, portMAX_DELAY); }
void i2c_unlock() { xSemaphoreGive(s_mux); }

bool i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool i2c_read_regs(uint8_t addr, uint8_t reg, uint8_t *buf, size_t len) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)len) != len) return false;
  for (size_t i = 0; i < len; i++) buf[i] = Wire.read();
  return true;
}
