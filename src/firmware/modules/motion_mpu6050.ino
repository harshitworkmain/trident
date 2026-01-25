#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include "MPU6050.h"

const char* ssid = "harshit";
const char* password = "pass@007";

MPU6050 mpu;
WebServer server(80);

int16_t rawAccX, rawAccY, rawAccZ;
int16_t rawGyroX, rawGyroY, rawGyroZ;

float accX, accY, accZ;
float gyroX, gyroY, gyroZ;
float accMagnitude = 0.0;
float gyroMagnitude = 0.0;

bool fallDetected = false;
bool spikeActive = false;
unsigned long fallSpikeTime = 0;

void handleRoot() {
  String html = "<!DOCTYPE html><html><head>";
  html += "<meta charset='UTF-8'>";
  html += "<meta http-equiv='refresh' content='2'>";
  html += "<title>TRIDENT Fall Detection</title></head><body style='font-family:Arial; text-align:center'>";
  html += "<h2>TRIDENT Fall Detection System</h2>";
  html += "<p><b>Accelerometer (g)</b><br>X: " + String(accX, 2) + " | Y: " + String(accY, 2) + " | Z: " + String(accZ, 2) + "</p>";
  html += "<p><b>Gyroscope (°/s)</b><br>X: " + String(gyroX, 2) + " | Y: " + String(gyroY, 2) + " | Z: " + String(gyroZ, 2) + "</p>";
  html += "<p><b>Acceleration Magnitude:</b> " + String(accMagnitude, 2) + " g</p>";
  html += "<p><b>Gyro Magnitude:</b> " + String(gyroMagnitude, 2) + " °/s</p>";
  html += "<h3>Status: <span style='color:" + String(fallDetected ? "red" : "green") + ";'>" + 
          String(fallDetected ? "FALL DETECTED" : "Normal") + "</span></h3>";
  html += "<p><i>Page refreshes every 2 seconds.</i></p>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  mpu.initialize();

  if (!mpu.testConnection()) {
    Serial.println("MPU6050 connection failed!");
    while (1);
  }

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi connected");
  Serial.print("Local IP: ");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.begin();
}

void loop() {
  mpu.getAcceleration(&rawAccX, &rawAccY, &rawAccZ);
  mpu.getRotation(&rawGyroX, &rawGyroY, &rawGyroZ);

  accX = rawAccX / 16384.0;
  accY = rawAccY / 16384.0;
  accZ = rawAccZ / 16384.0;

  gyroX = rawGyroX / 131.0;
  gyroY = rawGyroY / 131.0;
  gyroZ = rawGyroZ / 131.0;

  accMagnitude = sqrt(accX * accX + accY * accY + accZ * accZ);
  gyroMagnitude = sqrt(gyroX * gyroX + gyroY * gyroY + gyroZ * gyroZ);

  // Spike detection
  if (!spikeActive && (accMagnitude > 2.5 || gyroMagnitude > 2.0)) {
    spikeActive = true;
    fallSpikeTime = millis();
  }

  // Check for fall resolution (cooldown)
  if (spikeActive) {
    if ((millis() - fallSpikeTime) <= 2000) {
      if (accMagnitude < 1.2 && gyroMagnitude < 0.5) {
        fallDetected = true;
        spikeActive = false;
      }
    } else {
      spikeActive = false;
    }
  }

  server.handleClient();
  delay(50);
}
