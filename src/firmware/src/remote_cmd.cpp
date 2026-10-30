// Remote commands delivered in the POST /api/v1/telemetry response:
//   {"commands": [{"id": 17, "action": "reset_fall", "params": {}},
//                 {"id": 18, "action": "set_geofence",
//                  "params": {"lat": .., "lng": .., "radius_km": ..}},   (latitude/longitude/radius also accepted)
//                 {"id": 19, "action": "buzz", "params": {"ms": 1500}}]}
// Every command id is sent back in the "acks" array of the next request. Ids are kept as their
// raw JSON text, so numeric and string ids round-trip unchanged. A command the server delivers
// again (its ack was lost) is acked again but not executed twice.
#include <ArduinoJson.h>
#include "buzzer.h"
#include "config.h"
#include "sensors.h"
#include "settings.h"
#include "telemetry.h"

constexpr size_t ACK_ID_MAX = 48;  // JSON text of one id (a quoted UUID is 38)
constexpr size_t RECENT_IDS = 16;

static char s_acks[PENDING_ACKS_MAX][ACK_ID_MAX];
static size_t s_ackCount = 0;
static char s_recent[RECENT_IDS][ACK_ID_MAX];  // ids already executed (ring)
static size_t s_recentNext = 0;

void remote_apply(const char *action, float lat, float lng, float radius, bool hasLat,
                  bool hasLng, bool hasRadius) {
  if (strcmp(action, "reset_fall") == 0) {
    imu_reset_fall();
    Serial.println("[cmd] fall alert reset");
  } else if (strcmp(action, "calibrate_gsr") == 0) {
    eda_request_baseline();  // applied at the next frame close
  } else if (strcmp(action, "calibrate_gsr_open") == 0) {
    eda_request_open_circuit();
  } else if (strcmp(action, "set_geofence") == 0) {
    Settings st = settings_get();
    if (hasLat) st.geo_lat = lat;
    if (hasLng) st.geo_lng = lng;
    if (hasRadius && radius > 0) st.geo_radius_km = radius;
    settings_set(st);
    Serial.println("[cmd] geofence updated");
  } else {
    Serial.printf("[cmd] unknown action '%s'\n", action);
  }
}

static bool seen_recently(const char *id) {
  for (size_t i = 0; i < RECENT_IDS; i++)
    if (strcmp(s_recent[i], id) == 0) return true;
  return false;
}

static void ack_add(const char *id) {
  for (size_t i = 0; i < s_ackCount; i++)
    if (strcmp(s_acks[i], id) == 0) return;
  if (s_ackCount == PENDING_ACKS_MAX) remote_acks_sent(1);  // drop oldest; server re-delivers
  strlcpy(s_acks[s_ackCount++], id, ACK_ID_MAX);
}

static void execute(const char *action, JsonObjectConst p) {
  if (strcmp(action, "buzz") == 0) {
    long ms = p["ms"] | 1000L;
    buzzer_request_ms(ms > 0 ? (uint32_t)ms : 0);
    Serial.printf("[cmd] buzz %ld ms\n", ms);
    return;
  }
  // API contract keys are lat / lng / radius_km; the older latitude / longitude / radius are still accepted
  JsonVariantConst lat = p["lat"].is<float>() ? p["lat"] : p["latitude"];
  JsonVariantConst lng = p["lng"].is<float>() ? p["lng"] : p["longitude"];
  JsonVariantConst rad = p["radius_km"].is<float>() ? p["radius_km"] : p["radius"];
  remote_apply(action, lat | 0.0f, lng | 0.0f, rad | 0.0f, lat.is<float>(), lng.is<float>(), rad.is<float>());
}

void remote_handle_commands(JsonArrayConst cmds) {
  for (JsonObjectConst cmd : cmds) {
    char id[ACK_ID_MAX] = "";
    JsonVariantConst idv = cmd["id"];
    if (!idv.isNull()) {
      if (measureJson(idv) < ACK_ID_MAX) serializeJson(idv, id, sizeof(id));
      else Serial.println("[cmd] command id too long, will not be acked");
    }
    if (id[0] && seen_recently(id)) {
      Serial.printf("[cmd] %s already executed, re-acking\n", id);
    } else {
      execute(cmd["action"] | "", cmd["params"]);
      if (id[0]) {
        strlcpy(s_recent[s_recentNext], id, ACK_ID_MAX);
        s_recentNext = (s_recentNext + 1) % RECENT_IDS;
      }
    }
    if (id[0]) ack_add(id);
  }
}

size_t remote_append_acks(String &out) {
  for (size_t i = 0; i < s_ackCount; i++) {
    if (i) out += ',';
    out += s_acks[i];
  }
  return s_ackCount;
}

void remote_acks_sent(size_t n) {
  if (n >= s_ackCount) {
    s_ackCount = 0;
    return;
  }
  memmove(s_acks[0], s_acks[n], (s_ackCount - n) * ACK_ID_MAX);
  s_ackCount -= n;
}
