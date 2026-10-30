// Persistent settings (NVS via Preferences): GSR calibration, geofence, boot counter, the
// telemetry seq reservation and the SOS press counter.
// Writes are deferred: sensor tasks mark settings dirty, the network task flushes to flash,
// so slow flash writes never stall sampling.
#pragma once
#include <Arduino.h>

struct Settings {
  float gsr_open;          // open-circuit ADC reading (Grove formula reference)
  float gsr_baseline_us;   // on-skin resting conductance; NAN until calibrated
  float gsr_baseline_raw;  // matching ADC value, for the legacy norm
  double geo_lat, geo_lng;
  float geo_radius_km;
};

void settings_load();
Settings settings_get();
void settings_set(const Settings &s);  // marks dirty
void settings_flush_if_dirty();

// Boot counter and seq numbering. The server de-duplicates frames on (device_id, seq), so seq
// must never repeat, including across reboots. At boot a block of SEQ_BLOCK numbers is reserved
// in NVS; the network task extends the reservation before the block runs out. A reboot skips the
// unused rest of the block (a gap in seq, never a repeat).
struct BootInfo {
  uint32_t boot_id;    // increments on every boot (sent as "boot_id")
  uint32_t seq_start;  // first seq of this boot
};
BootInfo settings_boot_begin();             // call once in setup(), after settings_load()
void settings_seq_extend(uint32_t next_seq);  // network task: keep the reservation ahead

// SOS press ids never repeat either: the last id is loaded at boot (settings_boot_begin) and
// every new id is written to NVS by the SOS task right after the confirmation beep.
uint32_t settings_sos_next_press_id();         // SOS task: next id (RAM only, fast)
void settings_sos_save_press_id(uint32_t id);  // SOS task: persist it (flash write)
