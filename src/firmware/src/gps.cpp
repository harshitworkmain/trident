// NEO-6M on UART1 and the geofence check (geofence persisted in settings).
#include <TinyGPSPlus.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"
#include "sensors.h"
#include "settings.h"

static TinyGPSPlus s_gps;
static HardwareSerial s_serial(1);
static SemaphoreHandle_t s_mux = nullptr;
static volatile bool s_breached = false;

static float haversine_km(double lat1, double lon1, double lat2, double lon2) {
  const double R = 6371.0;
  double dLat = radians(lat2 - lat1), dLon = radians(lon2 - lon1);
  double a = sin(dLat / 2) * sin(dLat / 2) +
             cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2) * sin(dLon / 2);
  return (float)(R * 2 * atan2(sqrt(a), sqrt(1 - a)));
}

void gps_begin() {
  s_mux = xSemaphoreCreateMutex();
  s_serial.begin(9600, SERIAL_8N1, PIN_GPS_RX, PIN_GPS_TX);
}

void gps_poll() {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  while (s_serial.available() > 0) s_gps.encode(s_serial.read());
  xSemaphoreGive(s_mux);
}

void gps_close(FrameData &f) {
  xSemaphoreTake(s_mux, portMAX_DELAY);
  bool fix = s_gps.location.isValid() && s_gps.location.age() < 3000;
  double lat = s_gps.location.lat(), lng = s_gps.location.lng();
  int sats = s_gps.satellites.isValid() ? (int)s_gps.satellites.value() : -1;
  float hdop = s_gps.hdop.isValid() ? s_gps.hdop.hdop() : NAN;
  xSemaphoreGive(s_mux);

  f.gps_fix = fix;
  f.sats = sats;
  f.hdop = hdop;
  if (fix) {
    f.lat = lat;
    f.lng = lng;
    Settings st = settings_get();
    s_breached = haversine_km(lat, lng, st.geo_lat, st.geo_lng) > st.geo_radius_km;
    f.breached = s_breached ? TRI_TRUE : TRI_FALSE;
  }
}

bool gps_breached_latched() { return s_breached; }
