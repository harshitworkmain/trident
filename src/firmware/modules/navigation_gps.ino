#include <WiFi.h>
#include <WebServer.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

const char* ssid = "harshit";
const char* password = "pass@007";

TinyGPSPlus gps;
HardwareSerial gpsSerial(1);  // RX=16, TX=17
WebServer server(80);

const float safeLat = 12.843645347192979;   // Your chosen safe zone latitude (example: Delhi)
const float safeLng = 80.15303828079459;   // Your chosen safe zone longitude
const float geoRadius = 0.1;     // Safe zone radius in KM (100 meters)

const int buzzerPin = 4;

bool geoBreached = false;
float currentLat = 0.0, currentLng = 0.0;

void setup() {
  Serial.begin(115200);
  gpsSerial.begin(9600, SERIAL_8N1, 16, 17); // NEO-6M

  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi Connected");
  Serial.print("IP Address: "); Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.begin();
}

void loop() {
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }

  if (gps.location.isValid()) {
    currentLat = gps.location.lat();
    currentLng = gps.location.lng();

    float distance = getDistance(currentLat, currentLng, safeLat, safeLng);
    geoBreached = (distance > geoRadius);

    if (geoBreached) {
      digitalWrite(buzzerPin, HIGH);
    } else {
      digitalWrite(buzzerPin, LOW);
    }

    Serial.print("Lat: "); Serial.print(currentLat, 6);
    Serial.print(" | Lng: "); Serial.print(currentLng, 6);
    Serial.print(" | Distance: "); Serial.print(distance); Serial.println(" km");
  }

  server.handleClient();
}

float getDistance(float lat1, float lng1, float lat2, float lng2) {
  float R = 6371.0; // Earth radius in km
  float dLat = radians(lat2 - lat1);
  float dLng = radians(lng2 - lng1);
  float a = sin(dLat / 2) * sin(dLat / 2) +
            cos(radians(lat1)) * cos(radians(lat2)) *
            sin(dLng / 2) * sin(dLng / 2);
  float c = 2 * atan2(sqrt(a), sqrt(1 - a));
  return R * c;
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta http-equiv='refresh' content='5'>";
  html += "<title>TRIDENT GPS Tracker</title></head><body style='font-family:Arial; text-align:center'>";
  html += "<h2>TRIDENT GPS Live Tracker</h2>";

  html += "<p><b>Latitude:</b> " + String(currentLat, 6) + "</p>";
  html += "<p><b>Longitude:</b> " + String(currentLng, 6) + "</p>";
  html += "<p><b>Speed:</b> ";
  html += gps.speed.isValid() ? String(gps.speed.kmph(), 1) + " km/h" : "No Fix";
  html += "</p>";

  html += "<p><b>Altitude:</b> ";
  html += gps.altitude.isValid() ? String(gps.altitude.meters(), 1) + " m" : "No Fix";
  html += "</p>";

  html += "<p><b>UTC Time:</b> ";
  html += gps.time.isValid() ? String(gps.time.hour()) + ":" + String(gps.time.minute()) + ":" + String(gps.time.second()) : "No Fix";
  html += "</p>";

  html += "<p><b>Satellites:</b> ";
  html += gps.satellites.isValid() ? String(gps.satellites.value()) : "No Fix";
  html += "</p>";

  html += "<h3 style='color:" + String(geoBreached ? "red" : "green") + ";'>";
  html += geoBreached ? "⚠️ OUTSIDE SAFE ZONE" : "✅ INSIDE SAFE ZONE";
  html += "</h3>";

  html += "<p><i>Auto-refreshes every 5 seconds.</i></p>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}
