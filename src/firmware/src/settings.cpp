#include "settings.h"
#include <Preferences.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"

static Settings s_settings;
static bool s_dirty = false;
static SemaphoreHandle_t s_mux = nullptr;
static uint32_t s_seqLimit = 0;  // first seq not yet reserved in NVS (network task only)
static uint32_t s_sosLast = 0;   // last SOS press id handed out (SOS task only after boot)

void settings_load() {
  s_mux = xSemaphoreCreateMutex();
  Preferences p;
  p.begin("trident", true);
  s_settings.gsr_open = p.getFloat("gsr_open", GSR_OPEN_DEFAULT);
  s_settings.gsr_baseline_us = p.getFloat("gsr_base_us", NAN);
  s_settings.gsr_baseline_raw = p.getFloat("gsr_base_raw", NAN);
  s_settings.geo_lat = p.getDouble("geo_lat", 12.8239);
  s_settings.geo_lng = p.getDouble("geo_lng", 80.0467);
  s_settings.geo_radius_km = p.getFloat("geo_rad_km", 0.1f);
  p.end();
}

Settings settings_get() {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  Settings s = s_settings;
  xSemaphoreGive(s_mux);
  return s;
}

void settings_set(const Settings &s) {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  s_settings = s;
  s_dirty = true;
  xSemaphoreGive(s_mux);
}

void settings_flush_if_dirty() {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  bool dirty = s_dirty;
  Settings s = s_settings;
  s_dirty = false;
  xSemaphoreGive(s_mux);
  if (!dirty) return;
  Preferences p;
  p.begin("trident", false);
  p.putFloat("gsr_open", s.gsr_open);
  p.putFloat("gsr_base_us", s.gsr_baseline_us);
  p.putFloat("gsr_base_raw", s.gsr_baseline_raw);
  p.putDouble("geo_lat", s.geo_lat);
  p.putDouble("geo_lng", s.geo_lng);
  p.putFloat("geo_rad_km", s.geo_radius_km);
  p.end();
  Serial.println("[settings] saved");
}

BootInfo settings_boot_begin() {
  Preferences p;
  p.begin("trident", false);
  BootInfo b;
  b.boot_id = p.getUInt("boot_n", 0) + 1;
  b.seq_start = p.getUInt("seq_next", 0);
  s_seqLimit = b.seq_start + SEQ_BLOCK;
  s_sosLast = p.getUInt("sos_n", 0);
  p.putUInt("boot_n", b.boot_id);
  p.putUInt("seq_next", s_seqLimit);
  p.end();
  return b;
}

void settings_seq_extend(uint32_t next_seq) {
  if (next_seq + SEQ_BLOCK / 2 < s_seqLimit) return;
  s_seqLimit = next_seq + SEQ_BLOCK;
  Preferences p;
  p.begin("trident", false);
  p.putUInt("seq_next", s_seqLimit);
  p.end();
}

uint32_t settings_sos_next_press_id() { return ++s_sosLast; }

void settings_sos_save_press_id(uint32_t id) {
  Preferences p;
  p.begin("trident", false);
  p.putUInt("sos_n", id);
  p.end();
}
