// Copy to secrets.h (gitignored) and fill in. Never commit real credentials.
#pragma once

#define WIFI_SSID "your-ssid"
#define WIFI_PASSWORD "your-password"
// Full endpoint URL: <backend base> + /api/v1/telemetry (http:// works for a LAN backend).
#define TELEMETRY_URL "https://trident-command-center.onrender.com/api/v1/telemetry"
// Per-device API key, sent as X-Device-Key. Created by POST /api/v1/devices (admin) or
// POST /api/v1/devices/{id}/rotate-key; the server shows it once. Device id is in config.h.
#define DEVICE_KEY "CHANGE_ME"
