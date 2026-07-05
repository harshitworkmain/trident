# TRIDENT Source Code Walkthrough: System Architecture & Interview Strategy

This document provides a high-level overview of how the entire TRIDENT ecosystem connects. Use this to construct your "Elevator Pitch" for the Multi D Drone R&D interview.

## The Big Picture (Data Flow)

The TRIDENT system operates in three distinct layers:

### 1. Edge Layer (The Wearable)
- **Hardware**: ESP32 Microcontroller.
- **Role**: Collects live data (GPS, Heart Rate, SpO2, Motion, Stress).
- **Processing**: Runs local logic (Edge Computing) to detect falls or geofence breaches without needing the cloud.
- **Output**: Hosts a local web dashboard and triggers a local buzzer on emergencies.

### 2. Decision Layer (The Backend/Cloud)
- **Hardware**: Central Server (Host PC running Python).
- **Role**: The "Brain" of the operation. Written in Flask.
- **Processing**: 
  - Receives SOS requests.
  - Scores the emergency priority (1 to 5).
  - Uses AI (PyTorch LSTM) to forecast weather/water conditions.
  - Calculates the shortest path to the victim using geospatial logic (Haversine formula).
- **Output**: Updates the SQLite database and triggers the Action Layer.

### 3. Action Layer (The ROV / Drone)
- **Hardware**: Arduino-powered Underwater ROV.
- **Software**: PyQt6 Python Desktop Application (`serial_interface.py`).
- **Role**: The physical response.
- **Execution**: When the Decision Layer detects a Priority 4+ water emergency, it automatically spawns the PyQt6 application via `subprocess`, placing it into `--emergency-mode`. This initiates a 12-second countdown, activates the thrusters over Serial connection, and navigates toward the target.

## How to Pitch this at a Drone Startup

Drone companies (like Multi D Drone R&D) are fundamentally looking for engineers who understand **Integration**. Anyone can write a web app, and anyone can blink an LED. Very few juniors can make a web app talk to a physical motor.

**Key Phrases to Use in Your Interview:**
1. *"I architected TRIDENT as a distributed system. I pushed the anomaly detection (like fall detection) to the Edge on the ESP32 to reduce latency, while keeping heavy AI computations on the central server."*
2. *"I implemented an autonomous deployment pipeline. Instead of a human having to click 'Deploy', the Flask backend scores the emergency severity and programmatically spawns the ROV Ground Control Station in an automated sequence."*
3. *"I utilized non-blocking architecture across the board. On the hardware side, I used `millis()` instead of `delay()` to keep the web server responsive. On the software side, I used Daemon threads in PyQt6 and background threads in Flask to ensure the UI and APIs never freeze during serial I/O operations."*

## Final Interview Tips
- **Be ready to explain the Haversine formula**: It's used in both the ESP32 firmware (Geofencing) and the Backend (Path Planning). It calculates the shortest distance between two points on a sphere (the Earth) using their latitudes and longitudes.
- **Understand the Serial Protocol**: If asked how the Python script controls the ROV, explain the string-based protocol: `"direction_speed\n"` (e.g., `"forward_75\n"`).
- **Admit Imperfections**: If they ask about flaws, mention that the current SQLite database and `subprocess.Popen` deployment mechanism are great for prototypes, but in a production drone swarm, you would migrate to **ROS (Robot Operating System)** or use **MQTT** for pub/sub messaging between the backend and the drones. This shows incredible industry awareness!
