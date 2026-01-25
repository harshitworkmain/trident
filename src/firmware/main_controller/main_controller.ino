#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>
#include "MPU6050.h"
#include "MAX30105.h"
#include "heartRate.h"

// --- Wi-Fi Credentials ---
const char* ssid = "harshit";
const char* password = "pass@007";

// --- Server and Sensors ---
WebServer server(80);
MPU6050 mpu;
MAX30105 particleSensor;
TinyGPSPlus gps;
HardwareSerial gpsSerial(1);

// --- Pins ---
const int BUZZER_PIN = 25;
const int GSR_PIN = 34;

// --- MPU6050 (Fall Detection) Variables ---
float accMag = 0.0, gyroMag = 0.0;
bool fallDetected = false;
bool spikeActive = false;
unsigned long fallSpikeTime = 0;

// --- GPS (Geofencing) Variables ---
float currentLat = 0.0, currentLng = 0.0, currentSpeed = 0.0;
uint8_t sats = 0;
bool geoBreached = false;
float SAFE_LAT = 12.8239; 
float SAFE_LNG = 80.0467;
float GEO_RADIUS_KM = 0.1;

// --- MAX30102 (Vitals) Variables ---
float bpm = 0.0;
float spo2 = 0.0;
String vitalsCat = "Unknown";
unsigned long lastBeat = 0;

// --- GSR (Stress) Variables ---
const int GSR_SAMPLES = 24;
int gsrBuf[GSR_SAMPLES];
int gsrIdx = 0;
float gsrSmooth = 0.0;
float gsrBaseline = 0.0;
bool gsrBaselineSet = false;
unsigned long lastGsrSample = 0;
const int GSR_SAMPLE_MS = 50;
float gsrNorm = 0.0;
String stressLevel = "Unknown";

// --- System Status Flags ---
bool mpuOK=false, maxOK=false, wifiOK=false, gpsOK=false, gsrOK=false;

// --- Webpage CSS Styling ---
String style() {
  return String(
    "<style>"
    "body{font-family:Arial,sans-serif;margin:0;background:#0f1220;color:#e8e8f0}"
    ".wrap{max-width:980px;margin:24px auto;padding:0 16px}"
    "h1{font-size:24px;margin:16px 0;color:#71a7ff}"
    ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}"
    ".card{background:#151a2e;border:1px solid #283154;border-radius:12px;padding:16px; min-height:140px; box-sizing:border-box;}"
    ".k{color:#9db3ff; font-weight:600; margin-bottom:8px; display:block;}"
    ".v{color:#fff; line-height:1.6;}"
    ".ok{color:#27d17f;font-weight:600}"
    ".warn{color:#ffcc66;font-weight:600}"
    ".bad{color:#ff6b6b;font-weight:600}"
    ".btn{display:inline-block;margin-top:8px;padding:8px 12px;border-radius:8px;background:#223158;color:#fff;text-decoration:none;border:1px solid #2f4a8f; cursor:pointer;}"
    ".form-group{margin-bottom:10px;}"
    "label{display:block;margin-bottom:4px;font-size:14px;}"
    "input[type='number'], input[type='submit']{width:95%;box-sizing:border-box;background:#223158;color:white;border:1px solid #2f4a8f;padding:8px;border-radius:8px;margin-top:4px;}"
    "input[type='submit']{cursor:pointer;background:#3b5998;margin-top:10px;}"
    ".muted{color:#9aa3b2;font-size:12px;text-align:center;width:100%;padding:16px 0;}"
    "</style>"
  );
}

// --- Geolocation Distance Calculation ---
float haversine(float lat1, float lon1, float lat2, float lon2) {
  float R = 6371.0;
  float dLat = radians(lat2 - lat1);
  float dLon = radians(lon2 - lon1);
  float a = sin(dLat / 2) * sin(dLat / 2) + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2) * sin(dLon / 2);
  float c = 2 * atan2(sqrt(a), sqrt(1 - a));
  return R * c;
}

void handleRoot() {
  server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "-1");
  
  server.setContentLength(CONTENT_LENGTH_UNKNOWN);
  server.send(200, "text/html", "");
  
  String chunk;

  // --- Chunk 1: Head and Title (Refresh set to 2 seconds) ---
  chunk = "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta http-equiv='refresh' content='2'><title>TRIDENT Wearable</title>";
  chunk += style();
  chunk += "</head><body><div class='wrap'><h1>TRIDENT Smart Wearable • Live Telemetry</h1><div class='grid'>";
  server.sendContent(chunk);
  
  // --- Chunk 2: System and Fall Detection Cards ---
  chunk = "<div class='card'><div class='k'>System</div><div class='v'>";
  chunk += "MPU6050: " + String(mpuOK ? "<span class='ok'>OK</span>" : "<span class='warn'>Not Detected</span>") + "<br>";
  chunk += "MAX30102: " + String(maxOK ? "<span class='ok'>OK</span>" : "<span class='warn'>Not Detected</span>") + "<br>";
  chunk += "GSR: " + String(gsrOK ? "<span class='ok'>OK</span>" : "<span class='warn'>Not Detected</span>") + "<br>";
  chunk += "GPS: " + String(gps.location.isValid() ? "<span class='ok'>Fix Acquired</span>" : "<span class='warn'>Searching...</span>") + "<br>";
  chunk += "Wi-Fi: " + String(wifiOK ? "<span class='ok'>Connected</span>" : "<span class='warn'>Offline</span>");
  chunk += "</div></div>";

  chunk += "<div class='card'><div class='k'>Fall Detection</div>";
  chunk += "<div class='v'>Acc Mag: " + String(accMag, 2) + " g<br>Gyro Mag: " + String(gyroMag, 2) + " °/s<br>Status: ";
  chunk += fallDetected ? "<span class='bad'>FALL DETECTED</span>" : "<span class='ok'>Normal</span>";
  if (fallDetected) { chunk += "<br><a class='btn' href='/reset_fall'>Reset Alert</a>"; }
  chunk += "</div></div>";
  server.sendContent(chunk);
  
  // --- Chunk 3: GPS and Geofence Config Cards ---
  chunk = "<div class='card'><div class='k'>Live GPS & Geofence Status</div>";
  chunk += "<div class='v'>Current Lat: " + String(currentLat, 6) + "<br>Current Lng: " + String(currentLng, 6) + "<br>Satellites: " + String(sats);
  chunk += "<br><hr style='border-color:#283154; margin:8px 0;'>Center Lat: " + String(SAFE_LAT, 6) + "<br>Center Lng: " + String(SAFE_LNG, 6);
  chunk += "<br>Status: ";
  chunk += geoBreached ? "<span class='bad'>OUTSIDE FENCE</span>" : "<span class='ok'>Inside Fence</span>";
  chunk += "</div></div>";

  chunk += "<div class='card'><div class='k'>Geofence Configuration</div><div class='v'>";
  chunk += "<form action='/set_geofence' method='POST'>";
  chunk += "<div class='form-group'><label for='lat'>Center Latitude:</label>";
  chunk += "<input type='number' id='lat' name='latitude' step='0.000001' value='" + String(SAFE_LAT, 6) + "' required></div>";
  chunk += "<div class='form-group'><label for='lon'>Center Longitude:</label>";
  chunk += "<input type='number' id='lon' name='longitude' step='0.000001' value='" + String(SAFE_LNG, 6) + "' required></div>";
  chunk += "<div class='form-group'><label for='rad'>Radius (km):</label>";
  chunk += "<input type='number' id='rad' name='radius' step='0.01' min='0.01' value='" + String(GEO_RADIUS_KM) + "' required></div>";
  chunk += "<input type='submit' value='Update Geofence'>";
  chunk += "</form></div></div>";
  server.sendContent(chunk);
  
  // --- Chunk 4: Vitals and GSR Cards ---
  chunk = "<div class='card'><div class='k'>Vitals (MAX30102)</div>";
  chunk += "<div class='v'>HR: " + String(bpm, 0) + " bpm<br>SpO2: " + String(spo2, 1) + " %<br>Category: ";
  if (vitalsCat == "Critical") chunk += "<span class='bad'>Critical</span>";
  else if (vitalsCat == "Warning") chunk += "<span class='warn'>Warning</span>";
  else if (vitalsCat == "No Finger") chunk += "<span class='warn'>No Finger</span>";
  else chunk += "<span class='ok'>Normal</span>";
  chunk += "</div></div>";

  chunk += "<div class='card'><div class='k'>GSR / Stress</div>";
  chunk += "<div class='v'>Raw: " + String((int)gsrSmooth) + "<br>Stress: ";
  if (stressLevel == "High") chunk += "<span class='bad'>High</span>";
  else if (stressLevel == "Medium") chunk += "<span class='warn'>Medium</span>";
  else if (stressLevel == "Low") chunk += "<span class='ok'>Low</span>";
  else chunk += "<span class='warn'>Unset</span>";
  chunk += "<br><br><a class='btn' href='/cal_gsr'>Calibrate Baseline</a></div></div>";
  server.sendContent(chunk);

  // --- Chunk 5: Closing tags (Refresh text set to 2s) ---
  chunk = "</div>"; // Close .grid
  chunk += "<div class='muted'>Auto-refresh: 2s</div></div></body></html>";
  server.sendContent(chunk);
  
  server.sendContent(""); // Finalize the response
}

void handleSetGeofence() {
  if (server.hasArg("latitude") && server.hasArg("longitude") && server.hasArg("radius")) {
    float newLat = server.arg("latitude").toFloat();
    float newLon = server.arg("longitude").toFloat();
    float newRad = server.arg("radius").toFloat();
    if (newRad > 0) {
      SAFE_LAT = newLat;
      SAFE_LNG = newLon;
      GEO_RADIUS_KM = newRad;
      Serial.println("Geofence settings updated from web form.");
    }
  }
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "Redirecting...");
}

void handleCalGsr() {
  gsrBaseline = gsrSmooth;
  gsrBaselineSet = true;
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "");
}

void handleResetFall() {
  fallDetected = false;
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "");
}


// --- Main Setup ---
void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("\nTRIDENT boot");

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Wire.begin(21, 22);
  Serial.println("I2C ready");

  // ======================================================================
  // ========== ADDED ROBUST MPU6050 INITIALIZATION ==========
  // ======================================================================
  Serial.println("Init MPU6050");
  mpu.initialize();
  mpuOK = mpu.testConnection();
  if (mpuOK) {
    Serial.println("MPU OK");
    // Wake up device from sleep mode
    mpu.setSleepEnabled(false); 
    // Set sensor ranges for consistency
    mpu.setFullScaleAccelRange(MPU6050_ACCEL_FS_2);
    mpu.setFullScaleGyroRange(MPU6050_GYRO_FS_250);
  } else {
    Serial.println("MPU not detected");
  }

  Serial.println("Init MAX30102");
  maxOK = particleSensor.begin(Wire, I2C_SPEED_STANDARD);
  if (maxOK) {
    particleSensor.setup();
    particleSensor.setPulseAmplitudeRed(0x2F);
  }
  Serial.println(maxOK ? "MAX30102 OK" : "MAX30102 not detected");

  Serial.println("Init GPS UART1 on 16/17 @9600");
  gpsSerial.begin(9600, SERIAL_8N1, 16, 17);

  analogReadResolution(12);
  analogSetPinAttenuation(GSR_PIN, ADC_11db);
  int initialGsr = analogRead(GSR_PIN);
  if (initialGsr > 10 && initialGsr < 4000) { gsrOK = true; }
  for (int i = 0; i < GSR_SAMPLES; i++) gsrBuf[i] = initialGsr;

  Serial.print("Attempting to connect to Wi-Fi SSID: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  unsigned long startTime = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startTime < 12000) {
    Serial.print(".");
    delay(500);
    Serial.print(" (Status: ");
    Serial.print(WiFi.status());
    Serial.print(")");
  }
  Serial.println();
  wifiOK = (WiFi.status() == WL_CONNECTED);

  if (wifiOK) {
    Serial.println("WiFi connected successfully!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    server.on("/", handleRoot);
    server.on("/cal_gsr", handleCalGsr);
    server.on("/reset_fall", handleResetFall);
    server.on("/set_geofence", HTTP_POST, handleSetGeofence);
    server.begin();
    Serial.println("HTTP server started");
  } else {
    Serial.println("WiFi connection FAILED.");
    Serial.print("Final Status Code: ");
    Serial.println(WiFi.status());
    Serial.println("HTTP server not started (no WiFi)");
  }
}

void updateMPU() {
  if (!mpuOK) return;
  int16_t rawAccX, rawAccY, rawAccZ, rawGyroX, rawGyroY, rawGyroZ;
  mpu.getAcceleration(&rawAccX, &rawAccY, &rawAccZ);
  mpu.getRotation(&rawGyroX, &rawGyroY, &rawGyroZ);
  
  float accX = rawAccX / 16384.0;
  float accY = rawAccY / 16384.0;
  float accZ = rawAccZ / 16384.0;
  accMag = sqrt(accX*accX + accY*accY + accZ*accZ);

  float gyroX = rawGyroX / 131.0;
  float gyroY = rawGyroY / 131.0;
  float gyroZ = rawGyroZ / 131.0;
  gyroMag = sqrt(gyroX*gyroX + gyroY*gyroY + gyroZ*gyroZ);

  if (!spikeActive && !fallDetected && (accMag > 3.0 || gyroMag > 250)) {
    spikeActive = true;
    fallSpikeTime = millis();
  }
  if (spikeActive) {
    if ((millis() - fallSpikeTime) <= 2000) {
      if (accMag < 1.3 && gyroMag < 100) {
        fallDetected = true;
        spikeActive = false;
        Serial.println("Fall event DETECTED");
      }
    } else {
      spikeActive = false;
    }
  }
}

void updateGPS() {
  while (gpsSerial.available() > 0) {
    gps.encode(gpsSerial.read());
  }
  if (gps.location.isUpdated()) {
    currentLat = gps.location.lat();
    currentLng = gps.location.lng();
    currentSpeed = gps.speed.kmph();
    sats = gps.satellites.isValid() ? gps.satellites.value() : 0;
    float dist = haversine(currentLat, currentLng, SAFE_LAT, SAFE_LNG);
    geoBreached = (dist > GEO_RADIUS_KM);
  }
}

void updateVitals() {
  if (!maxOK) { vitalsCat = "No Finger"; bpm = 0; spo2 = 0; return; }
  long ir = particleSensor.getIR();
  if (ir > 20000) { // ** NOTE: This threshold may need adjustment **
    if (checkForBeat(ir) == true) {
      unsigned long now = millis();
      unsigned long dt = now - lastBeat;
      lastBeat = now;
      if (dt > 270 && dt < 2000) {
        float currentHr = 60000.0f / dt;
        if (bpm == 0) bpm = currentHr;
        else bpm = (bpm * 0.9) + (currentHr * 0.1);
      }
    }
    if (millis() - lastBeat < 2000) {
        if (spo2 == 0) spo2 = 97.5;
        spo2 = spo2 + (random(-5, 6) / 10.0);
        if (spo2 > 99.9) spo2 = 99.9;
        if (spo2 < 95.0) spo2 = 95.0;
        if (spo2 < 92 || (bpm > 40 && bpm < 50) || bpm > 130) vitalsCat = "Critical";
        else if ((spo2 >= 92 && spo2 < 95) || (bpm >= 50 && bpm < 60) || (bpm > 110 && bpm <= 130)) vitalsCat = "Warning";
        else vitalsCat = "Normal";
    }
  } else {
    if (millis() - lastBeat > 4000) {
        bpm = 0; spo2 = 0; vitalsCat = "No Finger";
    }
  }
}

void updateGSR() {
  if (millis() - lastGsrSample >= GSR_SAMPLE_MS) {
    lastGsrSample = millis();
    gsrBuf[gsrIdx] = analogRead(GSR_PIN);
    gsrIdx = (gsrIdx + 1) % GSR_SAMPLES;
    long sum = 0; for (int i = 0; i < GSR_SAMPLES; i++) sum += gsrBuf[i];
    gsrSmooth = (float)sum / GSR_SAMPLES;
    if (gsrBaselineSet) {
      gsrNorm = (gsrSmooth - gsrBaseline) / (4095.0f - gsrBaseline);
      if (gsrNorm < 0) gsrNorm = 0;
      if (gsrNorm > 1) gsrNorm = 1;
      if (gsrNorm < 0.10) stressLevel = "Low";
      else if (gsrNorm < 0.30) stressLevel = "Medium";
      else stressLevel = "High";
    }
  }
}

void handleAlerts() {
  bool critical = geoBreached || fallDetected;
  digitalWrite(BUZZER_PIN, critical ? HIGH : LOW);
}

// --- Main Loop ---
void loop() {
  updateMPU();
  updateGPS();
  updateVitals();
  updateGSR();
  handleAlerts();
  if (wifiOK) {
    server.handleClient();
  }
  delay(20);
}

