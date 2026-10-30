// MAX30102: 100 Hz red+IR. Beats (SparkFun checkForBeat) give RR intervals timed by sample
// count, so RR resolution is 10 ms regardless of task jitter. SpO2 replaces the v1 simulated
// value: every 4 IR/red samples are averaged to 25 Hz and the Maxim reference algorithm runs
// once a second over the last 4 s (100 samples), as spo2_algorithm.h expects.
#include <MAX30105.h>
#include <heartRate.h>
#include <spo2_algorithm.h>
#include "config.h"
#include "i2c_bus.h"
#include "sensors.h"

static MAX30105 s_sensor;
static bool s_ok = false;

static const uint32_t SAMPLE_MS = 10;  // 100 Hz
static uint32_t s_sampleCount = 0;
static uint32_t s_lastBeatMs = 0;
static bool s_haveBeat = false;
static float s_bpm = NAN;

// frame accumulators
static uint64_t s_irSum = 0;
static uint32_t s_irN = 0, s_irMax = 0, s_irMin = UINT32_MAX;
static uint8_t s_rrCount = 0;
static uint16_t s_rr[RR_MAX_PER_FRAME];

// SpO2 pipeline (25 Hz rolling buffer)
static const int SPO2_LEN = 100;
static uint32_t s_irBuf[SPO2_LEN], s_redBuf[SPO2_LEN];
static int s_bufPos = 0, s_bufFill = 0, s_sinceRun = 0;
static uint32_t s_decIr = 0, s_decRed = 0;
static uint8_t s_decN = 0;
static float s_spo2 = NAN;
static uint32_t s_spo2Ms = 0;

bool ppg_begin() {
  i2c_lock();
  bool ok = s_sensor.begin(Wire, I2C_SPEED_FAST);
  if (ok) {
    // brightness, sampleAverage, ledMode (2 = red+IR), sampleRate, pulseWidth, adcRange
    s_sensor.setup(0x24, 1, 2, 100, 411, 16384);
  }
  i2c_unlock();
  s_ok = ok;
  return ok;
}

static void run_spo2(uint32_t now_ms) {
  static uint32_t ir[SPO2_LEN], red[SPO2_LEN];
  for (int i = 0; i < SPO2_LEN; i++) {  // unroll ring buffer oldest -> newest
    int j = (s_bufPos + i) % SPO2_LEN;
    ir[i] = s_irBuf[j];
    red[i] = s_redBuf[j];
  }
  int32_t spo2, hr;
  int8_t spo2Valid, hrValid;
  maxim_heart_rate_and_oxygen_saturation(ir, SPO2_LEN, red, &spo2, &spo2Valid, &hr, &hrValid);
  if (spo2Valid && spo2 >= 50 && spo2 <= 100) {
    s_spo2 = (float)spo2;
    s_spo2Ms = now_ms;
  }
}

static void handle_sample(uint32_t red, uint32_t ir) {
  s_sampleCount++;
  uint32_t t = s_sampleCount * SAMPLE_MS;

  s_irSum += ir;
  s_irN++;
  if (ir > s_irMax) s_irMax = ir;
  if (ir < s_irMin) s_irMin = ir;

  if (ir >= FINGER_IR_MIN && checkForBeat((long)ir)) {
    if (s_haveBeat) {
      uint32_t rr = t - s_lastBeatMs;
      if (rr >= RR_MIN_MS && rr <= RR_MAX_MS) {
        if (s_rrCount < RR_MAX_PER_FRAME) s_rr[s_rrCount++] = (uint16_t)rr;
        float inst = 60000.0f / rr;
        s_bpm = isnan(s_bpm) ? inst : 0.9f * s_bpm + 0.1f * inst;  // same EMA as v1
      }
    }
    s_lastBeatMs = t;
    s_haveBeat = true;
  }

  s_decIr += ir;
  s_decRed += red;
  if (++s_decN == 4) {
    s_irBuf[s_bufPos] = s_decIr / 4;
    s_redBuf[s_bufPos] = s_decRed / 4;
    s_bufPos = (s_bufPos + 1) % SPO2_LEN;
    if (s_bufFill < SPO2_LEN) s_bufFill++;
    s_decIr = s_decRed = 0;
    s_decN = 0;
    if (++s_sinceRun >= 25 && s_bufFill == SPO2_LEN) {
      s_sinceRun = 0;
      run_spo2(t);
    }
  }
}

void ppg_poll() {
  if (!s_ok) return;
  // The library's internal store holds only a few samples, so drain on every call.
  i2c_lock();
  s_sensor.check();
  while (s_sensor.available()) {
    uint32_t red = s_sensor.getFIFORed();
    uint32_t ir = s_sensor.getFIFOIR();
    s_sensor.nextSample();
    i2c_unlock();
    handle_sample(red, ir);
    i2c_lock();
  }
  i2c_unlock();
}

void ppg_close(FrameData &f, uint32_t now_ms) {
  (void)now_ms;
  f.max_ok = s_ok;
  uint32_t t = s_sampleCount * SAMPLE_MS;
  if (s_ok && s_irN > 0) {
    float irMean = (float)s_irSum / s_irN;
    bool finger = irMean >= FINGER_IR_MIN;
    f.finger_on = finger ? TRI_TRUE : TRI_FALSE;
    if (finger) {
      f.perfusion = (float)(s_irMax - s_irMin) / irMean * 100.0f;
      if (s_haveBeat && t - s_lastBeatMs <= BPM_LOST_MS) f.bpm = s_bpm;
      bool fresh = !isnan(s_spo2) && t - s_spo2Ms <= SPO2_MAX_AGE_MS;
      f.spo2_valid = fresh ? TRI_TRUE : TRI_FALSE;
      if (fresh) f.spo2 = s_spo2;
      f.rr_count = s_rrCount;
      memcpy(f.rr_ms, s_rr, s_rrCount * sizeof(uint16_t));
    } else {
      f.spo2_valid = TRI_FALSE;
      s_bpm = NAN;  // restart the EMA when contact returns
      s_haveBeat = false;
    }
  }
  s_irSum = 0;
  s_irN = 0;
  s_irMax = 0;
  s_irMin = UINT32_MAX;
  s_rrCount = 0;
}
