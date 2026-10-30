// TRIDENT wearable firmware v2.
//   fast task  (core 1, 100 Hz tick): PPG FIFO, IMU 50 Hz, EDA 20 Hz, buzzer, frame close every 1.5 s
//   slow task  (core 1,  25 Hz tick): barometer, skin temperature, water, battery, GPS UART
//   sos        (core 1, 100 Hz tick): SOS button (debounce, hold / 3 presses / cancel), cue beeps
//   network    (core 0)             : Wi-Fi, upload queue, remote commands, web UI, settings
#include <Arduino.h>
#include "buzzer.h"
#include "config.h"
#include "frame.h"
#include "i2c_bus.h"
#include "sensors.h"
#include "settings.h"
#include "sos.h"
#include "telemetry.h"

static uint32_t s_seqStart = 0;

static void fast_task(void *) {
  TickType_t last = xTaskGetTickCount();
  uint32_t tick = 0, frameTicks = 0, seq = s_seqStart;
  for (;;) {
    vTaskDelayUntil(&last, pdMS_TO_TICKS(FAST_TICK_MS));
    tick++;
    uint32_t now = millis();
    ppg_poll();
    if (tick % IMU_EVERY_TICKS == 0) imu_sample(now);
    if (tick % EDA_EVERY_TICKS == 0) eda_sample();
    if (tick % 10 == 0) buzzer_update(now, imu_fall_latched() || gps_breached_latched());
    // A raised or cancelled SOS closes the frame early so it goes out now (that frame is
    // shorter than 1.5 s: imu.n shows it); the 1.5 s cadence restarts from there.
    if (++frameTicks >= FRAME_TICKS || sos_take_frame_request()) {
      frameTicks = 0;
      FrameData f;
      frame_clear(f);
      f.seq = seq++;
      f.uptime_ms = now;
      imu_close(f);
      ppg_close(f, now);
      eda_close(f);
      skintemp_close(f);
      baro_close(f);
      water_close(f);
      power_close(f);
      gps_close(f);
      sos_close(f);
      queue_push(f);
    }
  }
}

static void slow_task(void *) {
  TickType_t last = xTaskGetTickCount();
  uint32_t tick = 0;
  for (;;) {
    vTaskDelayUntil(&last, pdMS_TO_TICKS(SLOW_TICK_MS));
    tick++;
    gps_poll();
    baro_sample();
    if (tick % TEMP_EVERY_TICKS == 0) skintemp_sample();
    if (tick % WATER_EVERY_TICKS == 0) water_sample();
    if (tick % POWER_EVERY_TICKS == 0) power_sample();
  }
}

void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("\nTRIDENT wearable fw " FW_VERSION);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  analogReadResolution(12);

  i2c_init();
  settings_load();
  BootInfo boot = settings_boot_begin();
  s_seqStart = boot.seq_start;
  telemetry_begin(boot.boot_id);
  Serial.printf("boot %u, seq from %u\n", boot.boot_id, boot.seq_start);
  queue_init();

  Serial.printf("MPU6050  %s\n", imu_begin() ? "ok" : "not detected");
  Serial.printf("MAX30102 %s\n", ppg_begin() ? "ok" : "not detected");
  Serial.printf("GSR      %s\n", eda_begin() ? "ok" : "not detected");
  Serial.printf("MAX30205 %s\n", skintemp_begin() ? "ok" : "not detected");
  Serial.printf("BMP388   %s\n", baro_begin() ? "ok" : "not detected");
  water_begin();
  power_begin();
  gps_begin();

  xTaskCreatePinnedToCore(fast_task, "fast", 6144, nullptr, 5, nullptr, 1);
  xTaskCreatePinnedToCore(slow_task, "slow", 4096, nullptr, 3, nullptr, 1);
  TaskHandle_t net = nullptr;
  xTaskCreatePinnedToCore(network_task, "net", 16384, nullptr, 2, &net, 0);
  sos_begin(net);
}

void loop() { vTaskDelete(nullptr); }  // all work happens in the tasks above
