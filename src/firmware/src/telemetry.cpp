#include "telemetry.h"
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include "buzzer.h"
#include "config.h"
#include "secrets.h"
#include "sensors.h"
#include "settings.h"
#include "sos.h"

#ifndef DEVICE_KEY
#error "Add DEVICE_KEY to include/secrets.h (see include/secrets.example.h)"
#endif

static uint32_t s_bootId = 0;

void telemetry_begin(uint32_t boot_id) { s_bootId = boot_id; }

// ---------------- JSON encoding ----------------

static void put_num(JsonObject o, const char *key, float v, int decimals) {
  if (isnan(v)) o[key] = nullptr;
  else o[key] = serialized(String(v, decimals));
}

static void put_tri(JsonObject o, const char *key, Tri t) {
  if (t == TRI_NULL) o[key] = nullptr;
  else o[key] = (t == TRI_TRUE);
}

void telemetry_to_json(const FrameData &f, String &out) {
  JsonDocument doc;
  doc["schema"] = 2;
  doc["device_id"] = DEVICE_ID;
  doc["fw"] = FW_VERSION;
  doc["seq"] = f.seq;
  doc["uptime_ms"] = f.uptime_ms;
  doc["boot_id"] = s_bootId;  // increments per reboot; uptime_ms restarts with it

  JsonObject imu = doc["imu"].to<JsonObject>();
  put_num(imu, "acc_max_g", f.acc_max_g, 3);
  put_num(imu, "acc_min_g", f.acc_min_g, 3);
  put_num(imu, "acc_mean_g", f.acc_mean_g, 3);
  put_num(imu, "acc_std_g", f.acc_std_g, 4);
  put_num(imu, "gyro_max_dps", f.gyro_max_dps, 1);
  put_num(imu, "gyro_mean_dps", f.gyro_mean_dps, 1);
  put_num(imu, "tilt_deg", f.tilt_deg, 1);
  if (f.mpu_ok) imu["n"] = f.imu_n; else imu["n"] = nullptr;
  put_tri(imu, "fall_detected", f.fall_detected);

  JsonObject ppg = doc["ppg"].to<JsonObject>();
  put_tri(ppg, "finger_on", f.finger_on);
  put_num(ppg, "bpm", f.bpm, 1);
  JsonArray rr = ppg["rr_ms"].to<JsonArray>();
  for (uint8_t i = 0; i < f.rr_count; i++) rr.add(f.rr_ms[i]);
  put_num(ppg, "spo2", f.spo2, 1);
  put_tri(ppg, "spo2_valid", f.spo2_valid);
  put_num(ppg, "perfusion", f.perfusion, 2);

  JsonObject eda = doc["eda"].to<JsonObject>();
  put_num(eda, "us", f.eda_us, 3);
  put_num(eda, "slope_us_s", f.eda_slope_us_s, 4);
  put_num(eda, "baseline_us", f.eda_baseline_us, 3);
  put_num(eda, "raw", f.eda_raw, 0);
  put_num(eda, "norm", f.eda_norm, 3);

  put_num(doc["temp"].to<JsonObject>(), "skin_c", f.skin_c, 2);

  JsonObject baro = doc["baro"].to<JsonObject>();
  put_num(baro, "hpa", f.baro_hpa, 2);
  put_num(baro, "dmax_hpa", f.baro_dmax_hpa, 3);

  put_tri(doc["water"].to<JsonObject>(), "wet", f.wet);
  put_num(doc["power"].to<JsonObject>(), "batt_v", f.batt_v, 2);

  JsonObject gps = doc["gps"].to<JsonObject>();
  if (isnan(f.lat)) gps["lat"] = nullptr; else gps["lat"] = serialized(String(f.lat, 6));
  if (isnan(f.lng)) gps["lng"] = nullptr; else gps["lng"] = serialized(String(f.lng, 6));
  if (f.sats < 0) gps["sats"] = nullptr; else gps["sats"] = f.sats;
  put_num(gps, "hdop", f.hdop, 2);
  put_tri(gps, "breached", f.breached);

  // Device health: not part of the schema-2 contract, ignored by the parser.
  JsonObject sys = doc["sys"].to<JsonObject>();
  sys["mpu_ok"] = f.mpu_ok;
  sys["max_ok"] = f.max_ok;
  sys["gsr_ok"] = f.gsr_ok;
  sys["temp_ok"] = f.temp_ok;
  sys["baro_ok"] = f.baro_ok;
  sys["gps_fix"] = f.gps_fix;
  sys["queue"] = (uint32_t)queue_size();
  sys["dropped"] = f.queue_dropped;

  // Emergency button: not part of the schema-2 contract either; only present after a press.
  if (f.sos_phase != SOS_NONE) {
    JsonObject sos = doc["sos"].to<JsonObject>();
    sos["active"] = f.sos_phase == SOS_ACTIVE;
    sos["press_id"] = f.sos_press_id;
    if (f.sos_phase == SOS_ACTIVE) sos["pressed_uptime_ms"] = f.sos_pressed_ms;
    else sos["cancelled"] = true;
  }

  serializeJson(doc, out);
}

// ---------------- Upload ----------------
// POST <TELEMETRY_URL> with X-Device-Key, always in the batch form
//   {"frames":[frame, ...], "acks":[command_id, ...]}
// Frames leave the queue only after a 200; the server de-duplicates on (device_id, seq), so a
// batch resent after a lost response is harmless.

static WiFiClientSecure s_tls;
static WiFiClient s_plain;
static HTTPClient s_http;
static NetStatus s_status;
static FrameData s_batch[BATCH_MAX_FRAMES];  // static: keeps ~2 kB off the task stack
static String s_body;
static size_t s_batchMax = BATCH_MAX_FRAMES;
static uint32_t s_failures = 0;              // consecutive transient failures

const NetStatus &net_status() { return s_status; }

static int post_body(const String &body, String &response, uint32_t &retryAfterMs) {
  static const char *kHeaders[] = {"Retry-After"};
  retryAfterMs = 0;
  bool https = strncmp(TELEMETRY_URL, "https", 5) == 0;
  bool ok = https ? s_http.begin(s_tls, TELEMETRY_URL) : s_http.begin(s_plain, TELEMETRY_URL);
  if (!ok) return -1;
  s_http.collectHeaders(kHeaders, 1);
  s_http.setTimeout(HTTP_TIMEOUT_MS);
  s_http.setReuse(true);  // keep-alive makes flushing a backlog much faster
  s_http.addHeader("Content-Type", "application/json");
  s_http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = s_http.POST((uint8_t *)body.c_str(), body.length());
  if (code == 200) {
    response = s_http.getString();
  } else if (code > 0 && s_http.hasHeader("Retry-After")) {
    long sec = s_http.header("Retry-After").toInt();  // delta-seconds form only
    if (sec > 0) retryAfterMs = min((uint32_t)sec * 1000, RETRY_AFTER_MAX_MS);
  }
  s_http.end();
  return code;
}

// Exponential backoff with jitter: base 1, 2, 4 .. 30 s, actual delay uniform in [base/2, base].
static uint32_t backoff_ms() {
  uint32_t base = BACKOFF_MIN_MS << (s_failures < 6 ? s_failures : 6);
  if (base > BACKOFF_MAX_MS) base = BACKOFF_MAX_MS;
  return base / 2 + esp_random() % (base / 2 + 1);
}

static void handle_response(const String &body) {
  JsonDocument doc;
  if (deserializeJson(doc, body)) {
    Serial.println("[net] unparseable response");
    return;
  }
  s_status.accepted += doc["accepted"] | 0u;
  s_status.duplicates += doc["duplicates"] | 0u;
  remote_handle_commands(doc["commands"].as<JsonArrayConst>());
  JsonObjectConst st = doc["state"];
  s_status.has_state = !st.isNull();
  if (s_status.has_state) {
    strlcpy(s_status.ml_health_state, st["ml_health_state"] | "", sizeof(s_status.ml_health_state));
    strlcpy(s_status.alert_level, st["alert_level"] | "", sizeof(s_status.alert_level));
    s_status.ml_risk_score = st["ml_risk_score"] | NAN;
    s_status.state_ms = millis();
  }
  buzzer_set_server_critical(s_status.has_state && strcmp(s_status.alert_level, "critical") == 0);
  JsonObjectConst sos = doc["sos"];
  if (!sos.isNull()) sos_handle_response(sos);
}

// Sends up to s_batchMax queued frames; returns how long to wait before the next attempt.
static uint32_t send_batch() {
  size_t n = queue_peek_n(s_batch, s_batchMax);
  if (n == 0) return 0;
  uint16_t dropped = queue_dropped();
  // An unacknowledged SOS rides on every frame of the batch, so it reaches the control room with
  // the first request even when an offline backlog is still draining ahead of the SOS frame.
  SosStatus sos = sos_status();
  bool sosPending = sos.phase == SOS_ACTIVE && !sos.received;
  String one;
  s_body = "{\"frames\":[";
  for (size_t i = 0; i < n; i++) {
    s_batch[i].queue_dropped = dropped;
    if (sosPending && s_batch[i].sos_phase == SOS_NONE) {
      s_batch[i].sos_phase = SOS_ACTIVE;
      s_batch[i].sos_press_id = sos.press_id;
      s_batch[i].sos_pressed_ms = sos.pressed_uptime_ms;
    }
    telemetry_to_json(s_batch[i], one);
    if (i) s_body += ',';
    s_body += one;
  }
  s_body += "],\"acks\":[";
  size_t nAcks = remote_append_acks(s_body);
  s_body += "]}";

  String response;
  uint32_t retryAfter;
  int code = post_body(s_body, response, retryAfter);
  uint32_t lastSeq = s_batch[n - 1].seq;
  s_status.last_code = code;

  if (code == 200) {
    queue_pop_through(lastSeq);
    remote_acks_sent(nAcks);  // before handling: the response may queue new acks
    s_failures = 0;
    s_status.auth_failed = false;
    s_status.last_ok_ms = millis();
    if (s_batchMax < BATCH_MAX_FRAMES) s_batchMax = min(s_batchMax * 2, BATCH_MAX_FRAMES);
    handle_response(response);
    return 0;
  }
  if (code == 401 || code == 403 || code == 404) {
    // Wrong key, revoked device or wrong URL: retrying fast cannot help. Keep queueing.
    s_status.auth_failed = code != 404;
    Serial.printf("[net] %s (%d), retry in %u s\n",
                  code == 404 ? "endpoint not found" : "auth failed", code,
                  (unsigned)(AUTH_BACKOFF_MS / 1000));
    return max(AUTH_BACKOFF_MS, retryAfter);
  }
  if (code >= 400 && code < 500 && code != 408 && code != 429) {
    // The server rejected the payload. Resend frame by frame (in halves for 413) to isolate the
    // bad frame; a single rejected frame is dropped, otherwise it would block the queue forever.
    if (n > 1) {
      s_batchMax = code == 413 ? n / 2 : 1;
      return 0;
    }
    Serial.printf("[net] frame %u rejected (%d), dropped\n", (unsigned)lastSeq, code);
    queue_pop_through(lastSeq);
    return 0;
  }
  // 408, 429, 5xx, timeout or no connection: back off and keep queueing.
  s_failures++;
  uint32_t wait = max(backoff_ms(), retryAfter);
  Serial.printf("[net] upload failed (%d), retry in %u ms\n", code, (unsigned)wait);
  return wait;
}

static void wifi_maintain() {
  static uint32_t lastAttempt = 0;
  static bool started = false;
  if (!started) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    started = true;
    lastAttempt = millis();
    return;
  }
  if (WiFi.status() != WL_CONNECTED && millis() - lastAttempt > 10000) {
    WiFi.reconnect();
    lastAttempt = millis();
  }
}

void network_task(void *arg) {
  (void)arg;
  // TLS without certificate pinning; pin a root CA here for production deployments.
  s_tls.setInsecure();
  s_body.reserve(BATCH_MAX_FRAMES * 900 + 64 + PENDING_ACKS_MAX * 50);
  s_status.ml_risk_score = NAN;
  size_t urlLen = strlen(TELEMETRY_URL), pathLen = strlen(TELEMETRY_PATH);
  if (urlLen < pathLen || strcmp(TELEMETRY_URL + urlLen - pathLen, TELEMETRY_PATH) != 0)
    Serial.println("[net] warning: TELEMETRY_URL does not end with " TELEMETRY_PATH);
  if (strcmp(DEVICE_KEY, "CHANGE_ME") == 0)
    Serial.println("[net] warning: DEVICE_KEY is not set in secrets.h");

  bool webStarted = false;
  uint32_t nextTry = millis(), lastSeqCheck = 0;
  for (;;) {
    wifi_maintain();
    bool online = WiFi.status() == WL_CONNECTED;
    if (online && !webStarted) {
      Serial.printf("[net] Wi-Fi up, IP %s\n", WiFi.localIP().toString().c_str());
      webui_begin();
      webStarted = true;
    }
    if (webStarted) webui_handle();
    settings_flush_if_dirty();

    uint32_t now = millis();
    if (now - lastSeqCheck >= 1000) {
      lastSeqCheck = now;
      FrameData last;
      if (latest_frame(last)) settings_seq_extend(last.seq + 1);
    }
    if (online && (int32_t)(now - nextTry) >= 0) {
      uint32_t wait = send_batch();
      // An unacknowledged SOS overrides the backoff (including the slow auth/404 retry).
      if (sos_pending() && wait > SOS_RETRY_MAX_MS) wait = SOS_RETRY_MAX_MS;
      nextTry = millis() + wait;
      s_status.retry_at_ms = nextTry;
    }
    // Sleep 10 ms, or less when the SOS button task wakes us: then retry immediately.
    if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(10))) nextTry = millis();
  }
}
