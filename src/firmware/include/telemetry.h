// Schema-2 JSON encoding, batched upload of queued frames, remote commands and the local web UI.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "frame.h"

void telemetry_begin(uint32_t boot_id);  // call in setup() before the tasks start
void telemetry_to_json(const FrameData &f, String &out);

// Network task body (pinned to core 0): Wi-Fi upkeep, batched queue flush in seq order,
// remote commands + acks, SOS acknowledgements, deferred settings writes and the local status
// page. Woken early by a task notification from the SOS button task.
void network_task(void *arg);

// Upload link and the server's view of the wearer, from the last POST /api/v1/telemetry.
// Written and read only on the network task (the web UI is served from it): no lock.
struct NetStatus {
  int last_code;           // last HTTP status; < 0 = transport error/timeout; 0 = none yet
  uint32_t last_ok_ms;     // millis() of the last 200, 0 = never
  uint32_t retry_at_ms;    // next attempt not before this
  bool auth_failed;        // 401/403: DEVICE_KEY rejected
  uint32_t accepted, duplicates;  // totals since boot
  bool has_state;
  uint32_t state_ms;       // millis() when the state below was received
  char ml_health_state[32];
  char alert_level[16];
  float ml_risk_score;     // NAN when the server sent null
};
const NetStatus &net_status();

// remote_cmd.cpp
void remote_handle_commands(JsonArrayConst cmds);  // execute, remember ids for the next acks
size_t remote_append_acks(String &out);  // appends pending ids as JSON values, returns count
void remote_acks_sent(size_t n);         // drop the first n ids once the server returned 200
void remote_apply(const char *action, float lat, float lng, float radius, bool hasLat,
                  bool hasLng, bool hasRadius);

// webui.cpp
void webui_begin();
void webui_handle();
