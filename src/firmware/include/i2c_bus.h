// Shared I2C bus guarded by a mutex: the fast and slow sensor tasks both talk to it.
#pragma once
#include <Arduino.h>
#include <Wire.h>

void i2c_init();
void i2c_lock();
void i2c_unlock();

// Register helpers for drivers written directly against the bus (MPU6050, MAX30205).
// Callers must hold the lock.
bool i2c_write_reg(uint8_t addr, uint8_t reg, uint8_t value);
bool i2c_read_regs(uint8_t addr, uint8_t reg, uint8_t *buf, size_t len);
