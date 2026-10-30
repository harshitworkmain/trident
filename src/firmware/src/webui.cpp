// Local status page on the wearable's own IP (same LAN): SOS state, latest frame, upload link
// and the server's health state, calibration actions.
#include <WebServer.h>
#include "buzzer.h"
#include "config.h"
#include "frame.h"
#include "settings.h"
#include "sos.h"
#include "telemetry.h"

static WebServer s_server(80);

static String fmt(float v, int dp, const char *unit) {
  return isnan(v) ? String("&mdash;") : String(v, dp) + " " + unit;
}

static String tri(Tri t) { return t == TRI_NULL ? "&mdash;" : (t == TRI_TRUE ? "yes" : "no"); }

static void row(String &h, const char *k, const String &v) {
  h += "<tr><td>"; h += k; h += "</td><td>"; h += v; h += "</td></tr>";
}

static String ago(uint32_t ms) { return String((millis() - ms) / 1000) + " s ago"; }

static String link_text(const NetStatus &n) {
  int32_t wait = (int32_t)(n.retry_at_ms - millis());
  String retry = wait > 0 ? ", retry in " + String((wait + 999) / 1000) + " s" : String("");
  if (n.auth_failed)
    return "<b class='bad'>auth failed</b> (HTTP " + String(n.last_code) + ", check DEVICE_KEY)" + retry;
  if (n.last_code == 0) return "connecting";
  if (n.last_code == 200) return "ok (last upload " + ago(n.last_ok_ms) + ")";
  String err = n.last_code < 0 ? String("no response") : "HTTP " + String(n.last_code);
  return "<b class='warn'>" + err + "</b>" + retry +
         (n.last_ok_ms ? ", last ok " + ago(n.last_ok_ms) : String(""));
}

static String sos_text(const SosStatus &s) {
  String id = " (press #" + String(s.press_id) + ", " + ago(s.pressed_uptime_ms) + ")";
  if (s.phase == SOS_ACTIVE && s.received)
    return "<b class='bad'>received " + String(s.reference_id[0] ? s.reference_id : "(no reference)") +
           "</b>" + id;
  if (s.phase == SOS_ACTIVE) return "<b class='bad'>sending</b>" + id;
  if (s.phase == SOS_CANCELLED)
    return "cancelled" + id + (s.cancel_acked ? ", cancel acknowledged" : "") +
           (s.received ? ", was " + String(s.reference_id) : "");
  return "none";
}

static void handle_root() {
  FrameData f;
  bool have = latest_frame(f);
  String h;
  h.reserve(4096);
  h += F("<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' "
         "content='width=device-width,initial-scale=1'><meta http-equiv='refresh' content='2'>"
         "<title>TRIDENT Wearable</title><style>body{font-family:Arial,sans-serif;margin:0;"
         "background:#0f1220;color:#e8e8f0}.w{max-width:720px;margin:16px auto;padding:0 16px}"
         "h1{font-size:20px;color:#71a7ff}table{width:100%;border-collapse:collapse}"
         "td{padding:6px;border-bottom:1px solid #283154}td:first-child{color:#9db3ff}"
         "a,button{display:inline-block;margin:8px 8px 0 0;padding:8px 12px;border-radius:8px;"
         "background:#223158;color:#fff;text-decoration:none;border:1px solid #2f4a8f}"
         "input{background:#223158;color:#fff;border:1px solid #2f4a8f;padding:6px;"
         "border-radius:6px;width:110px}.bad{color:#ff6b6b}.warn{color:#ffb347}</style></head>"
         "<body><div class='w'>"
         "<h1>TRIDENT Wearable &bull; fw " FW_VERSION "</h1><table>");
  row(h, "SOS", sos_text(sos_status()));
  if (have) {
    row(h, "Frame", String(f.seq) + " @ " + String(f.uptime_ms / 1000) + " s");
    row(h, "Accel max / mean / std", fmt(f.acc_max_g, 2, "g") + " / " + fmt(f.acc_mean_g, 2, "g") + " / " + fmt(f.acc_std_g, 3, "g"));
    row(h, "Gyro max", fmt(f.gyro_max_dps, 0, "&deg;/s"));
    row(h, "Fall detected", tri(f.fall_detected));
    row(h, "Finger on", tri(f.finger_on));
    row(h, "Heart rate", fmt(f.bpm, 0, "bpm") + " (" + String(f.rr_count) + " beats)");
    row(h, "SpO2", fmt(f.spo2, 1, "%"));
    row(h, "Skin conductance", fmt(f.eda_us, 2, "&micro;S") + " (baseline " + fmt(f.eda_baseline_us, 2, "&micro;S") + ")");
    row(h, "Skin temperature", fmt(f.skin_c, 2, "&deg;C"));
    row(h, "Pressure", fmt(f.baro_hpa, 2, "hPa") + " (&Delta; " + fmt(f.baro_dmax_hpa, 3, "hPa") + ")");
    row(h, "Wet", tri(f.wet));
    row(h, "Battery", fmt(f.batt_v, 2, "V"));
    row(h, "GPS", isnan(f.lat) ? String("no fix") : String(f.lat, 6) + ", " + String(f.lng, 6));
    row(h, "Geofence breached", tri(f.breached));
  }
  row(h, "Upload queue", String((uint32_t)queue_size()) + " frames, " + String(queue_dropped()) + " dropped");
  const NetStatus &n = net_status();
  row(h, "Server link", link_text(n));
  row(h, "Server accepted / duplicates", String(n.accepted) + " / " + String(n.duplicates));
  if (n.has_state) {
    bool stale = millis() - n.state_ms > SERVER_STATE_TTL_MS;
    bool critical = strcmp(n.alert_level, "critical") == 0;
    row(h, "Health state (server)", String(n.ml_health_state) + (stale ? " (stale)" : ""));
    row(h, "Alert level", critical ? "<b class='bad'>critical</b>" : String(n.alert_level));
    row(h, "Risk score", fmt(n.ml_risk_score, 2, ""));
  } else {
    row(h, "Health state (server)", "&mdash;");
  }
  Settings st = settings_get();
  h += F("</table><a href='/reset_fall'>Reset fall</a><a href='/cal_gsr'>Calibrate GSR "
         "(on skin, at rest)</a><a href='/cal_gsr_open'>Calibrate GSR open-circuit (off skin)"
         "</a><a href='/buzz'>Test buzzer</a><a href='/frame.json'>frame.json</a><form method='POST' action='/set_geofence'>"
         "<p>Geofence: ");
  h += "<input name='latitude' value='" + String(st.geo_lat, 6) + "'> ";
  h += "<input name='longitude' value='" + String(st.geo_lng, 6) + "'> ";
  h += "<input name='radius' value='" + String(st.geo_radius_km, 3) + "'> km ";
  h += F("<button type='submit'>Save</button></p></form></div></body></html>");
  s_server.send(200, "text/html", h);
}

static void redirect_home() {
  s_server.sendHeader("Location", "/");
  s_server.send(302, "text/plain", "");
}

void webui_begin() {
  s_server.on("/", handle_root);
  s_server.on("/frame.json", [] {
    FrameData f;
    String out = "{}";
    if (latest_frame(f)) { out = ""; telemetry_to_json(f, out); }
    s_server.send(200, "application/json", out);
  });
  s_server.on("/reset_fall", [] { remote_apply("reset_fall", 0, 0, 0, false, false, false); redirect_home(); });
  s_server.on("/cal_gsr", [] { remote_apply("calibrate_gsr", 0, 0, 0, false, false, false); redirect_home(); });
  s_server.on("/cal_gsr_open", [] { remote_apply("calibrate_gsr_open", 0, 0, 0, false, false, false); redirect_home(); });
  s_server.on("/buzz", [] { buzzer_request_ms(1000); redirect_home(); });
  s_server.on("/set_geofence", HTTP_POST, [] {
    remote_apply("set_geofence", s_server.arg("latitude").toFloat(), s_server.arg("longitude").toFloat(),
                 s_server.arg("radius").toFloat(), s_server.hasArg("latitude"),
                 s_server.hasArg("longitude"), s_server.hasArg("radius"));
    redirect_home();
  });
  s_server.begin();
}

void webui_handle() { s_server.handleClient(); }
