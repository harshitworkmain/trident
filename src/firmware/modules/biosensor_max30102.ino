#include <WiFi.h>
#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"
#include <WebServer.h>

const char* ssid = "harshit";
const char* password = "pass@007";

MAX30105 particleSensor;
WebServer server(80);

float bpm = 0.0;
float spo2 = 0.0;
bool fingerDetected = false;
String category = "Unknown";
const int buzzerPin = 4;

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);

  if (!particleSensor.begin(Wire, I2C_SPEED_STANDARD)) {
    Serial.println("MAX30102 not detected. Check wiring/power.");
    while (1);
  }

  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeGreen(0);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }

  Serial.println("\nWiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.begin();
}

void loop() {
  long irValue = particleSensor.getIR();

  if (irValue > 50000) {
    fingerDetected = true;
    bpm = getHeartRate();
    spo2 = getSpO2();

    if (spo2 < 90 || bpm < 50 || bpm > 120) {
      category = "Critical";
      digitalWrite(buzzerPin, HIGH);
    } else if ((spo2 >= 90 && spo2 < 95) || (bpm >= 50 && bpm <= 60) || (bpm > 100 && bpm <= 120)) {
      category = "Warning";
      digitalWrite(buzzerPin, LOW);
    } else {
      category = "Normal";
      digitalWrite(buzzerPin, LOW);
    }

  } else {
    fingerDetected = false;
    bpm = 0.0;
    spo2 = 0.0;
    category = "No Finger";
    digitalWrite(buzzerPin, LOW);
  }

  server.handleClient();
  delay(20);
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta http-equiv='refresh' content='2'>";
  html += "<title>TRIDENT Health Telemetry</title></head><body style='font-family:Arial;text-align:center'>";
  html += "<h2>TRIDENT Live Health Data</h2>";

  if (fingerDetected) {
    html += "<p><b>Heart Rate:</b> " + String(bpm, 1) + " bpm</p>";
    html += "<p><b>SpO2:</b> " + String(spo2, 1) + " %</p>";
    html += "<p><b>Category:</b> " + category + "</p>";
  } else {
    html += "<p style='color:red'><b>Status:</b> No finger detected</p>";
  }

  html += "<p><i>Page auto-refreshes every 2 seconds.</i></p></body></html>";
  server.send(200, "text/html", html);
}

// Dummy processing functions
float getHeartRate() {
  return random(70, 125); // Simulate HR
}

float getSpO2() {
  return random(90, 100); // Simulate SpO2
}
