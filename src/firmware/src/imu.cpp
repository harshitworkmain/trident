// MPU6050 via direct register access. Ranges are widened from the v1 firmware (+/-2 g,
// +/-250 deg/s) because fall impacts routinely exceed 2 g and saturated readings hide them.
#include <math.h>
#include "config.h"
#include "i2c_bus.h"
#include "sensors.h"

static bool s_ok = false;

// frame accumulators
static uint16_t s_n = 0;
static float s_accMax, s_accMin, s_accSum, s_accSq, s_gyroMax, s_gyroSum;
static float s_ax, s_ay, s_az;  // mean acc vector for tilt

// fall detector
enum FallState { FALL_IDLE, FALL_FREEFALL, FALL_SETTLE, FALL_STILL };
static FallState s_fs = FALL_IDLE;
static uint32_t s_fsT = 0;
static uint16_t s_stillN = 0;
static float s_stillSum = 0, s_stillSq = 0, s_stillGyro = 0;
static volatile bool s_fallLatched = false;

static void reset_accumulators() {
  s_n = 0;
  s_accMax = 0;
  s_accMin = 1e9f;
  s_accSum = s_accSq = s_gyroMax = s_gyroSum = 0;
  s_ax = s_ay = s_az = 0;
}

bool imu_begin() {
  uint8_t who = 0;
  i2c_lock();
  bool ok = i2c_read_regs(ADDR_MPU6050, 0x75, &who, 1);
  // genuine parts report 0x68; common clones report 0x70/0x72/0x98
  ok = ok && (who == 0x68 || who == 0x70 || who == 0x72 || who == 0x98);
  if (ok) {
    ok = i2c_write_reg(ADDR_MPU6050, 0x6B, 0x01)      // wake, PLL clock
         && i2c_write_reg(ADDR_MPU6050, 0x1A, 0x04)   // DLPF ~21 Hz (anti-alias for 50 Hz)
         && i2c_write_reg(ADDR_MPU6050, 0x19, 19)     // 1 kHz / (1+19) = 50 Hz
         && i2c_write_reg(ADDR_MPU6050, 0x1B, 0x18)   // gyro +/-2000 deg/s
         && i2c_write_reg(ADDR_MPU6050, 0x1C, 0x18);  // accel +/-16 g
  }
  i2c_unlock();
  s_ok = ok;
  reset_accumulators();
  return ok;
}

static void fall_step(uint32_t now, float acc, float gyro) {
  switch (s_fs) {
    case FALL_IDLE:
      if (acc < FALL_FREEFALL_G) { s_fs = FALL_FREEFALL; s_fsT = now; }
      break;
    case FALL_FREEFALL:
      if (acc > FALL_IMPACT_G) { s_fs = FALL_SETTLE; s_fsT = now; }
      else if (now - s_fsT > FALL_IMPACT_WINDOW_MS) s_fs = FALL_IDLE;
      break;
    case FALL_SETTLE:
      if (now - s_fsT >= FALL_SETTLE_MS) {
        s_fs = FALL_STILL; s_fsT = now;
        s_stillN = 0; s_stillSum = s_stillSq = s_stillGyro = 0;
      }
      break;
    case FALL_STILL:
      s_stillN++; s_stillSum += acc; s_stillSq += acc * acc; s_stillGyro += gyro;
      if (now - s_fsT >= FALL_STILL_MS) {
        float mean = s_stillSum / s_stillN;
        float sd = sqrtf(fmaxf(s_stillSq / s_stillN - mean * mean, 0));
        if (sd < FALL_STILL_STD_G && s_stillGyro / s_stillN < FALL_STILL_GYRO_DPS) {
          s_fallLatched = true;
          Serial.println("[imu] fall detected");
        }
        s_fs = FALL_IDLE;
      }
      break;
  }
}

void imu_sample(uint32_t now_ms) {
  if (!s_ok) return;
  uint8_t b[14];
  i2c_lock();
  bool ok = i2c_read_regs(ADDR_MPU6050, 0x3B, b, sizeof(b));
  i2c_unlock();
  if (!ok) return;
  auto rd = [&](int i) { return (int16_t)((b[i] << 8) | b[i + 1]); };
  float ax = rd(0) / 2048.0f, ay = rd(2) / 2048.0f, az = rd(4) / 2048.0f;  // g
  float gx = rd(8) / 16.4f, gy = rd(10) / 16.4f, gz = rd(12) / 16.4f;     // deg/s
  float acc = sqrtf(ax * ax + ay * ay + az * az);
  float gyro = sqrtf(gx * gx + gy * gy + gz * gz);

  s_n++;
  s_accMax = fmaxf(s_accMax, acc);
  s_accMin = fminf(s_accMin, acc);
  s_accSum += acc;
  s_accSq += acc * acc;
  s_gyroMax = fmaxf(s_gyroMax, gyro);
  s_gyroSum += gyro;
  s_ax += ax; s_ay += ay; s_az += az;

  fall_step(now_ms, acc, gyro);
}

void imu_close(FrameData &f) {
  f.mpu_ok = s_ok;
  f.fall_detected = s_ok ? (s_fallLatched ? TRI_TRUE : TRI_FALSE) : TRI_NULL;
  f.imu_n = s_n;
  if (s_n > 0) {
    float mean = s_accSum / s_n;
    f.acc_max_g = s_accMax;
    f.acc_min_g = s_accMin;
    f.acc_mean_g = mean;
    f.acc_std_g = sqrtf(fmaxf(s_accSq / s_n - mean * mean, 0));
    f.gyro_max_dps = s_gyroMax;
    f.gyro_mean_dps = s_gyroSum / s_n;
    float mx = s_ax / s_n, my = s_ay / s_n, mz = s_az / s_n;
    float norm = sqrtf(mx * mx + my * my + mz * mz);
    if (norm > 0.05f) f.tilt_deg = acosf(fmaxf(-1.f, fminf(1.f, mz / norm))) * 180.0f / PI;
  }
  reset_accumulators();
}

void imu_reset_fall() { s_fallLatched = false; }
bool imu_fall_latched() { return s_fallLatched; }
