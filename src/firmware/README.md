# Firmware Directory

This directory contains embedded firmware for the TRIDENT wearable device.

## Structure

- `main_controller.ino` - Main ESP32 firmware with integrated sensor systems
- `modules/` - Individual sensor subsystems
  - `biosensor_gsr.ino` - GSR stress monitoring subsystem
  - `biosensor_max30102.ino` - Heart rate and SpO2 monitoring
  - `navigation_gps.ino` - GPS location and geofencing
  - `motion_mpu6050.ino` - Motion sensing and fall detection
- `libraries/` - Custom libraries and headers

## Hardware Requirements

- ESP32 microcontroller
- MPU6050 accelerometer/gyroscope
- MAX30102 pulse oximeter
- GPS module (NEO-6M or similar)
- GSR sensors
- Buzzer for alerts

## Integration

All modules are designed to work together in the main controller for comprehensive emergency monitoring and response.