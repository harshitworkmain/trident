# TRIDENT Source Code Walkthrough: Firmware 

This document is designed to help you understand the **ESP32 Firmware** component of the TRIDENT disaster response ecosystem. Review this before your interview with Multi D Drone R&D.

## File Location
`src/firmware/main_controller/main_controller.ino`

## Core Responsibilities
The firmware runs on an ESP32 microcontroller, acting as the "brain" of the wearable edge device. Its primary jobs are:
1. Reading data from multiple physical sensors (Motion, GPS, Heart Rate, Skin Resistance).
2. Processing that data locally (Edge Computing) to detect emergencies like falls or geofence breaches.
3. Hosting a local web server to display real-time telemetry.

## Deep Dive: Key Sensors & Logic

### 1. Motion & Fall Detection (MPU6050)
- **What it does**: Measures acceleration (`accMag`) and rotation (`gyroMag`).
- **How it works (Lines 280-310)**: 
  The code looks for a sudden "spike" (Acc > 3.0g or Gyro > 250°/s). If a spike is detected, it starts a 2-second timer. If the motion settles down drastically within those 2 seconds (Acc < 1.3g and Gyro < 100°/s), it flags `fallDetected = true`. This represents a person falling and then remaining motionless.

### 2. Location & Geofencing (NEO-6M GPS via `TinyGPSPlus`)
- **What it does**: Tracks Latitude and Longitude.
- **How it works (Lines 85-92, 313-324)**: 
  It uses the **Haversine formula** to calculate the distance between the user's current GPS coordinates and a predefined `SAFE_LAT`/`SAFE_LNG` center point. If the distance exceeds `GEO_RADIUS_KM`, it flags `geoBreached = true`.
  - **How the Haversine Formula Works**: The Haversine formula calculates the shortest distance between two points on a sphere given their longitudes and latitudes. In the code, it converts the coordinates from degrees to radians, applies trigonometric functions (`sin`, `cos`, `atan2`) to account for the Earth's curvature, and multiplies the result by the Earth's radius (`R = 6371.0` km) to get the straight-line distance over the surface.

### 3. Vitals Monitoring (MAX30102)
- **What it does**: Measures Heart Rate (BPM) and Blood Oxygen (SpO2).
- **How it works (Lines 327-354)**: 
  It uses Infrared (IR) light absorption. If an IR signal > 20,000 is detected (meaning a finger is present), it measures the time between pulses (`dt`) to calculate BPM. It categorizes the user's health:
  - **Critical**: SpO2 < 92%, or extreme heart rates (<50 or >130).
  - **Warning**: Borderline levels.

### 4. Stress Detection (GSR - Galvanic Skin Response)
- **What it does**: Measures skin conductivity to estimate stress/sweat levels.
- **How it works (Lines 357-372)**: 
  It takes rolling averages of the analog input. Users can click a button to set a "baseline". The code then compares the current reading against the baseline, normalizing it between 0 and 1. Values > 0.30 trigger a "High" stress state.
  - **How the Rolling Average Works**: The code maintains a circular buffer (`gsrBuf`) of the last 24 samples (`GSR_SAMPLES = 24`). Every 50ms, a new analog reading replaces the oldest reading in the array at `gsrIdx`, and the index wraps around using the modulo operator (`%`). The code then sums all 24 values and divides by 24 to get `gsrSmooth`. This acts as a digital low-pass filter, smoothing out sudden, noisy spikes in the raw skin resistance analog signal before comparing it against the baseline.

## Web Server & Communication
The ESP32 uses the `WebServer.h` library to host a simple, auto-refreshing HTML dashboard on port 80.
- `handleRoot()`: Dynamically generates an HTML string injecting the real-time sensor variables.
- It uses HTTP POST (`/set_geofence`) to allow the command center to update the safe zone dynamically.

## Interview Talking Points for a Drone/Hardware Startup
If the interviewer asks about your embedded systems experience, highlight these specific technical details:
1. **Edge Processing**: Explain how you implemented the Haversine formula and Fall Detection directly on the ESP32 rather than sending raw data to the cloud. This saves bandwidth and reduces latency—critical for drone telemtry.
2. **Sensor Fusion**: Mention how you integrated I2C sensors (MPU6050, MAX30102) and UART/Serial sensors (GPS) simultaneously using the ESP32's hardware capabilities.
   - **Communication Protocols Explained**:
     - **I2C (Inter-Integrated Circuit)**: Used for the MPU6050 and MAX30102. It's a synchronous, multi-drop bus using two wires: SDA (Data, pin 21) and SCL (Clock, pin 22). It allows the ESP32 to query both sensors on the same bus using unique hardware addresses.
     - **UART (Universal Asynchronous Receiver-Transmitter)**: Used for the NEO-6M GPS. It's asynchronous serial communication. The ESP32 uses `HardwareSerial(1)` on pins 16 (RX) and 17 (TX) at 9600 baud rate to listen to the continuous NMEA sentence stream from the GPS module without blocking the main program.
     - **ADC (Analog-to-Digital Converter)**: Used for the GSR sensor. Pin 34 reads continuous analog voltage values (0-4095 representing 12-bit resolution) and converts the physical skin resistance into a digital integer.
     - **Wi-Fi / HTTP**: Used to serve the dashboard. The ESP32 connects to the local network and uses standard TCP/IP to serve HTML to connected clients.
3. **Non-blocking Code**: Note the use of `millis()` instead of `delay()` for the GSR sampling (Line 357) to ensure the main loop runs fast enough to serve web pages without stuttering.
