#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "harshit";
const char* password = "pass@007";

WebServer server(80);

const int ADC_PIN = 34;
const int SAMPLES = 24;
int adcBuf[SAMPLES];
int bufIndex = 0;
float smoothVal = 0.0;
float baseline = 0.0;
bool baselineSet = false;
unsigned long lastSample = 0;
const int SAMPLE_INTERVAL_MS = 50;

float norm = 0.0;
float lastNorm = 0.0;
int statusStableCount = 0;
String stressLevel = "Unknown";

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta http-equiv='refresh' content='2'>";
  html += "<title>TRIDENT GSR Telemetry</title></head><body style='font-family:Arial;text-align:center'>";
  html += "<h2>TRIDENT GSR Telemetry</h2>";
  html += "<p><b>Raw ADC:</b> " + String((int)smoothVal) + "</p>";

  float displayNorm = 0.0;
  if (baselineSet) {
    displayNorm = norm * 100.0;
    html += "<p><b>Normalized GSR:</b> " + String(displayNorm, 1) + " %</p>";
  } else {
    html += "<p><b>Normalized GSR:</b> --</p>";
  }

  html += "<p><b>Baseline:</b> " + String(baseline, 1) + (baselineSet ? " (set)" : " (not set)") + "</p>";
  html += "<p><a href='/cal'>Calibrate baseline now</a></p>";
  html += "<h3>Status: " + stressLevel + " Stress</h3>";
  html += "<p><i>Auto-refresh every 2s</i></p></body></html>";

  server.send(200, "text/html", html);
}

void handleCal() {
  baseline = smoothVal;
  baselineSet = true;
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "");
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < SAMPLES; i++) adcBuf[i] = 0;
  analogReadResolution(12);
  analogSetPinAttenuation(ADC_PIN, ADC_11db);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300); Serial.print(".");
  }

  Serial.println("\nWiFi connected!");
  Serial.print("Local IP address: ");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/cal", handleCal);
  server.begin();
  Serial.println("Web server started");

  lastSample = millis();
}

void loop() {
  if (millis() - lastSample >= SAMPLE_INTERVAL_MS) {
    lastSample = millis();
    int raw = analogRead(ADC_PIN);

    if (raw < 100) raw = 100;
    if (raw > 4000) raw = 4000;

    adcBuf[bufIndex] = raw;
    bufIndex = (bufIndex + 1) % SAMPLES;

    long sum = 0;
    for (int i = 0; i < SAMPLES; i++) sum += adcBuf[i];
    smoothVal = (float)sum / SAMPLES;

    if (baselineSet) {
      norm = (smoothVal - baseline) / (4095.0 - baseline);
      if (norm < 0) norm = 0;
      if (norm > 1) norm = 1;

      float delta = norm - lastNorm;
      if (abs(delta) < 0.02) {
        statusStableCount++;
      } else {
        statusStableCount = 0;
      }

      if (statusStableCount >= 3) {
        if (norm < 0.10) stressLevel = "Low";
        else if (norm < 0.30) stressLevel = "Medium";
        else stressLevel = "High";
      }

      lastNorm = norm;
    }
  }

  server.handleClient();
}
