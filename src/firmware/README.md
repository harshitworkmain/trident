# TRIDENT Wearable Firmware v2

ESP32 firmware for the TRIDENT wearable. Every **1.5 s** it sends one telemetry frame (schema 2)
to the command center. Each frame summarises what happened during that interval, not just one
instantaneous reading. The payload contract is defined in
[`src/ml/wearable/schema.py`](../ml/wearable/schema.py); the server and the ML training emulator
use the same definition.

## What changed from v1

| Area | v1 | v2 |
|---|---|---|
| SpO2 | Simulated (random walk between 95 and 99.9) | Measured: Maxim reference algorithm on MAX30102 red/IR, with a `spo2_valid` flag |
| Heart | EMA BPM only | BPM plus every beat-to-beat interval (`rr_ms`), timed to 10 ms |
| Motion | One instantaneous reading, ±2 g (impacts clipped) | 50 Hz, ±16 g / ±2000 °/s, max/min/mean/std over the 1.5 s frame, tilt |
| Fall detection | Spike followed by calm | Free fall (< 0.5 g) → impact (> 3 g) within 1 s → 2 s of stillness |
| EDA | Raw ADC | Skin conductance in µS (Grove formula), slope, baseline; raw and norm kept |
| New sensors | — | MAX30205 skin temperature, BMP388 barometer, water contact, battery voltage |
| Timing | One loop with a blocking HTTP POST and `delay(20)` (IMU gaps) | FreeRTOS: fixed-rate sensor tasks on core 1, network task on core 0 |
| Offline | Frames lost | 320-frame queue (8 min, ~50 KB), flushed in `seq` order, in batches of up to 10; when full the oldest *routine* frame is dropped and event frames (fall, impact ≥ 3 g, water, geofence) are kept |
| Credentials | Hard-coded in the sketch | `include/secrets.h` (gitignored), per-device API key |
| Backend API | `POST /api/telemetry/wearable`, no auth | `POST /api/v1/telemetry` with `X-Device-Key`, command acks, server health state (fw 2.1) |
| Emergency | — | SOS push button: hold 1.5 s or press 3 times, sent at once, acknowledged by the control room with a reference id (fw 2.2) |

## Bill of materials

| Part | Role | Interface | Notes |
|---|---|---|---|
| ESP32 DevKit (WROOM-32) | MCU, Wi-Fi | — | |
| MPU6050 (GY-521) | Accelerometer + gyroscope | I²C 0x68 | AD0 → GND |
| MAX30102 | PPG: heart rate, RR intervals, SpO2 | I²C 0x57 | Needs firm skin contact and ambient-light shielding |
| **MAX30205** breakout | Skin temperature, ±0.1 °C | I²C 0x48 | A0/A1/A2 → GND; sensing face against the skin with a thermal pad |
| **BMP388** breakout (BMP280 also works with a lib change) | Pressure: fall height, submersion | I²C 0x77 | SDO → VCC (0x77) or GND (0x76, also auto-detected); keep the vent open, use an ePTFE membrane for water resistance |
| Grove GSR v1.2 | Electrodermal activity | ADC (GPIO34) | Finger or wrist electrodes |
| **2 water-contact pads** + 1 MΩ + 1 kΩ | Immersion detection | ADC (GPIO33) + GPIO26 | Stainless or gold pads ~5 mm apart on the *outer* face of the case, away from the skin |
| **100 kΩ + 100 kΩ** resistors (+100 nF) | Battery voltage divider | ADC (GPIO35) | |
| NEO-6M GPS | Location, geofence | UART1 | |
| Buzzer | Local alert | GPIO25 | Drive through an NPN transistor if it draws > 12 mA |
| Momentary push button (normally open) | Emergency SOS | GPIO27 | Recessed or with a raised rim so it is not pressed by accident |
| 1S LiPo / 18650 + charger | Power | — | |

## Wiring

All analog inputs are on **ADC1**. ADC2 cannot be read while Wi-Fi is active.

| ESP32 pin | Connects to | Detail |
|---|---|---|
| 3V3 | VCC of MPU6050, MAX30102, MAX30205, BMP388, Grove GSR | |
| GND | All grounds | |
| GPIO21 (SDA) | SDA of MPU6050, MAX30102, MAX30205, BMP388 | Shared I²C bus, 400 kHz; 4.7 kΩ pull-ups if the breakouts have none |
| GPIO22 (SCL) | SCL of the same four | |
| GPIO34 | Grove GSR `SIG` | Input-only pin, ADC1_CH6 |
| GPIO33 | Water pad B | Plus a 1 MΩ resistor from GPIO33 to GND (pull-down) |
| GPIO26 | Water pad A through 1 kΩ | Driven high only during the 0.3 ms measurement (limits corrosion) |
| GPIO35 | Battery divider midpoint | BAT+ → 100 kΩ → GPIO35 → 100 kΩ → GND, 100 nF from GPIO35 to GND |
| GPIO16 (RX1) | GPS `TX` | 9600 baud |
| GPIO17 (TX1) | GPS `RX` | |
| GPIO25 | Buzzer (+), via transistor if needed | See [Buzzer](#buzzer) |
| GPIO27 | SOS button, other leg to GND | Internal pull-up (`INPUT_PULLUP`), pressed = LOW, no external parts. See [SOS button](#sos-button) |

I²C address map: 0x48 MAX30205 · 0x57 MAX30102 · 0x68 MPU6050 · 0x77 BMP388. No conflicts.

Missing sensors are tolerated. The firmware logs `not detected` at boot, sends their fields as
JSON `null`, and reports `false` in the `sys` health group.

## Build and flash

```bash
pip install platformio                       # once
cd src/firmware
cp include/secrets.example.h include/secrets.h   # then edit Wi-Fi, server URL, DEVICE_KEY
pio run                                      # build
pio run -t upload                            # flash over USB
pio device monitor                           # serial log @ 115200
```

`secrets.h` needs four values: `WIFI_SSID`, `WIFI_PASSWORD`, `TELEMETRY_URL` (the full endpoint,
ending in `/api/v1/telemetry`) and `DEVICE_KEY`. The build stops with an error if `DEVICE_KEY` is
missing. At boot the serial log warns if the key is still `CHANGE_ME` or the URL has the wrong
path.

Everything is pinned in `platformio.ini`: platform espressif32 6.9.0 (Arduino core 2.0.17),
SparkFun MAX3010x 1.1.2, Adafruit BMP3XX 2.1.5 (with Adafruit BusIO 1.17.4 and Adafruit Unified
Sensor 1.1.15), ArduinoJson 7.2.1, TinyGPSPlus 1.1.0. The MPU6050 and MAX30205 use small
register drivers in `src/`.

Last build (fw 2.2.0, `pio run`, clean): **SUCCESS**, no warnings from the project sources.

| | Used | Of | |
|---|---|---|---|
| RAM (static) | 111,684 B | 327,680 B | 34.1 % |
| Flash (app) | 1,044,777 B | 1,966,080 B | 53.1 % (`min_spiffs.csv`, OTA-sized slot) |

Most of the RAM increase over fw 2.1.0 (106,308 B, 32.4 %) is the SOS fields in each of the 320
queued frames.

The remaining warnings come from the SparkFun MAX3010x library (`I2C_BUFFER_LENGTH` redefined,
unused variables, `&` between comparisons). They are harmless: the library just reads the FIFO
in 32-byte chunks, and `&` on two booleans gives the same result as `&&`.

## Backend API

The firmware talks only to the P6 backend (`docs/PLATFORM_DESIGN.md`, "Devices and
telemetry"). The legacy `/api/telemetry/wearable` path and the v1 payload groups are no longer
sent.

**Request.** `POST <TELEMETRY_URL>` (`.../api/v1/telemetry`) with headers
`Content-Type: application/json` and `X-Device-Key: <DEVICE_KEY>`. The device always uses the
batch form, even for a single frame:

```json
{"frames": [{"schema": 2, "device_id": "TRIDENT-WEAR-01", "seq": 4012, "boot_id": 7, ...},
            {"schema": 2, "device_id": "TRIDENT-WEAR-01", "seq": 4013, "boot_id": 7, ...}],
 "acks": [17, 18]}
```

- Up to 10 frames per request (about 8 kB of JSON), oldest first, in `seq` order. When the device
  is online the queue holds one frame, so a request normally carries one frame. After an outage,
  the 320-frame backlog drains in 32 requests over a keep-alive connection.
- A frame leaves the queue only after a 200. If the response is lost, the same frames are sent
  again; the server de-duplicates on `(device_id, seq)` and counts them in `duplicates`.
- `acks` lists the ids of the commands the device executed since the last successful request.

**`seq` across reboots.** `seq` never repeats for a device, including after a reboot or a
re-flash that keeps NVS. At boot the firmware reserves a block of 4000 numbers in NVS and
extends the reservation from the network task before it runs out (one flash write about every
50 minutes). A reboot skips the unused part of the block, so the server sees a forward gap in
`seq`, never a repeat. Each frame also carries `boot_id`, a counter that increments on every
boot, so the server can tell that `uptime_ms` restarted. Erasing the flash (`pio run -t erase`)
resets both counters. Rotate the device key, or delete the device's stored frames, if that
happens.

**Response 200.**

```json
{"accepted": 2, "duplicates": 0,
 "commands": [{"id": 19, "action": "buzz", "params": {"ms": 1500}}],
 "state": {"ml_health_state": "normal", "ml_risk_score": 0.12, "alert_level": "none"}}
```

- `commands` run immediately on the network task: `reset_fall`, `calibrate_gsr`,
  `calibrate_gsr_open`, `set_geofence` (`lat`, `lng`, `radius_km`; the older `latitude`, `longitude`, `radius` are also accepted) and `buzz`
  (`ms`, capped at 10 s). Every id is acked in the next request, including unknown actions
  (they are logged and ignored). Ids are echoed exactly as received, whether number or string.
  If the server re-delivers a command whose ack was lost, the device acks it again without
  running it a second time (the last 16 ids are remembered).
- `sos` acknowledges the wearer's emergency request, see [SOS button](#sos-button).
- `state` is shown on the local web page (health state, alert level, risk score). When
  `alert_level` is `"critical"` the buzzer sounds a pattern (see below). If no fresh state arrives
  for 60 s, the device treats it as expired.

**Errors and backoff.** Frames keep queueing in every case. When the queue is full, the oldest
frame is dropped and counted in `sys.dropped`.

| Response | Device behaviour |
|---|---|
| 200 | Pop the frames, clear the sent acks, run the commands, handle the SOS ack, retry delay reset |
| 401, 403 | Key rejected. Retry every 60 s, and the web page shows **auth failed** |
| 404 | Wrong URL. Retry every 60 s |
| 408, 429, 5xx, timeout (5 s), no connection | Exponential backoff with jitter: 1, 2, 4, 8, 16, 30 s cap, each a random value between half and all of the step. Reset on the next 200 |
| Other 4xx (400, 413, 422) | Payload rejected. The batch is resent one frame at a time (in halves for 413) to isolate the bad frame. A single rejected frame is dropped |

A `Retry-After` header (in seconds, capped at 60 s) on an error response is respected if it is
longer than the computed delay. While an SOS is raised and not yet acknowledged, every wait
(backoff, auth/404 retry, `Retry-After`) is capped at 3 s.

## SOS button

A wearer without a phone can call for help from the band. The button is polled every 10 ms by a
small FreeRTOS task (core 1, priority 4) with a 30 ms debounce; nothing blocks the sensor tasks.

| Action | Condition | Result |
|---|---|---|
| **Raise** | Hold ≥ 1.5 s, or 3 presses within 2 s (first to third press) | New `press_id`, 2 short beeps at once, the current frame closes early and the network task is woken to send immediately |
| Waiting | Raised, no acknowledgement yet | One short beep every 10 s ("still trying"); upload retries at least every 3 s |
| **Received** | Server reply carries `sos.received: true` for this `press_id` | One 800 ms beep (first ack only), reminders stop, the web page shows the reference id |
| **Cancel** | A *new* press held ≥ 5 s while an SOS is active (accidental raise) | Two 400 ms beeps; frames carry the cancel until the server acknowledges it, or for 10 frames |
| Ignored | Presses shorter than 5 s while active; holding on after the raise | Holding the raising press past 5 s does not cancel it |

- `press_id` is a counter stored in NVS (`sos_n`), so ids never repeat across reboots (like
  `seq`). It is written right after the confirmation beep.
- The raising (or cancelling) frame closes early, so it is shorter than 1.5 s (`imu.n` shows the
  actual sample count; `eda.slope_us_s` uses the real frame length). The 1.5 s cadence restarts
  from there.
- Frames carrying an SOS (active or cancelled) count as **event frames**: on queue overflow they
  are kept over routine frames.
- While the SOS is unacknowledged, every frame of every request carries the `sos` group, so it
  reaches the server with the first request even if an offline backlog is still draining ahead
  of the SOS frame. Frames closed while the SOS is active always carry it.
- An SOS does not survive a reboot (the next raise gets a new id).
- The local web page shows SOS: `none`, `sending`, `received SOS-XXXXXX` or `cancelled`.

**Frame** (non-schema top-level group, like `sys`; absent when there is no SOS):

```json
"sos": {"active": true, "press_id": 42, "pressed_uptime_ms": 27349512}
"sos": {"active": false, "press_id": 42, "cancelled": true}
```

`pressed_uptime_ms` is on the same clock as the frame's `uptime_ms` (it restarts with `boot_id`).

**Response 200 fields read by the device:**

```json
{"accepted": 1, "duplicates": 0,
 "sos": {"received": true, "reference_id": "SOS-4F2A9C", "press_id": 42}}
```

- `sos.press_id` must match the current press, otherwise the object is ignored (a late ack for an
  older press does nothing).
- `received: true` acknowledges an active SOS; `reference_id` (up to 23 characters) is shown on
  the web page and logged.
- `cancelled: true` with the same `press_id` acknowledges a cancel and stops sending it before
  the 10 frames are up.

**Bench testing without a button:** set `PIN_SOS_BUTTON = 0` in `include/config.h` to use the
DevKit's **BOOT** button (GPIO0, already pulled up on the board). GPIO0 is a strapping pin: do not
hold it while powering up or resetting, or the ESP32 enters the serial bootloader instead of
running the firmware. Use GPIO27 on the wearable.

## Buzzer

The buzzer is driven from the fast task every 100 ms and never blocks. Sources are listed by
priority: a higher one owns the buzzer while it is active.

| Trigger | Sound |
|---|---|
| SOS cue (one-shot, ≤ 1.1 s; starts with a 100 ms gap so it stands out even over a continuous alarm) | Raised: 2 × 200 ms · Received: 800 ms · Cancelled: 2 × 400 ms · Reminder: 100 ms every 10 s (never interrupts another cue) |
| Fall latched on the device, or geofence breached | Continuous, until `reset_fall` or back inside the fence |
| `buzz` command, or **Test buzzer** on the local page | Continuous for `ms` (default 1000) |
| Server `alert_level == "critical"` | Three 200 ms beeps every 2 s, while the server reports critical (expires 60 s after the last report) |

## Calibration

Do these once after assembly. Values are stored in NVS and survive reboots. Each can be run from
the device's local page (`http://<device-ip>/`) or remotely through the dashboard command queue.

1. **GSR open-circuit reference** (`calibrate_gsr_open`). Electrodes **off** the skin, not
   touching anything. This stores the ADC reference used to convert readings into µS (default
   2048 until calibrated).
2. **GSR resting baseline** (`calibrate_gsr`). Wear the device and sit still for about 2 minutes,
   then run it. This sets `eda.baseline_us`, which `eda.norm` and the stress features are
   relative to.
3. **Geofence** (`set_geofence` with `lat`, `lng`, `radius_km`).
4. Check the water pads by dipping them in tap water: the web page should show `Wet: yes` within
   about 2 s.

Backend note: the P6 command endpoint (`POST /api/v1/devices/{id}/commands`) lists
`reset_fall`, `calibrate_gsr`, `set_geofence` and `buzz`. The firmware also accepts
`calibrate_gsr_open`. If the server does not offer it, use the local web page.

## Payload (schema 2)

```json
{
  "schema": 2, "device_id": "TRIDENT-WEAR-01", "fw": "2.2.0", "seq": 18234, "uptime_ms": 27351000,
  "boot_id": 7,
  "imu":   {"acc_max_g": 1.124, "acc_min_g": 0.912, "acc_mean_g": 1.008, "acc_std_g": 0.0412,
            "gyro_max_dps": 35.2, "gyro_mean_dps": 8.1, "tilt_deg": 12.5, "n": 75,
            "fall_detected": false},
  "ppg":   {"finger_on": true, "bpm": 78.0, "rr_ms": [772, 768], "spo2": 97.0,
            "spo2_valid": true, "perfusion": 0.84},
  "eda":   {"us": 2.314, "slope_us_s": 0.0031, "baseline_us": 2.105, "raw": 1840, "norm": 0.099},
  "temp":  {"skin_c": 33.41},
  "baro":  {"hpa": 1009.82, "dmax_hpa": 0.041},
  "water": {"wet": false},
  "power": {"batt_v": 3.92},
  "gps":   {"lat": 13.082700, "lng": 80.270700, "sats": 7, "hdop": 1.20, "breached": false},
  "sys":   {"mpu_ok": true, "max_ok": true, "gsr_ok": true, "temp_ok": true, "baro_ok": true,
            "gps_fix": true, "queue": 0, "dropped": 0},
  "sos":   {"active": true, "press_id": 42, "pressed_uptime_ms": 27349512}
}
```

- Unavailable values are `null`: sensor absent, no finger contact, no GPS fix, SpO2 not yet valid.
- `sys` is device health and is not part of the ML contract. Neither is `sos`, which is only
  present after the SOS button was used (see [SOS button](#sos-button)).
- `boot_id` (integer, added in fw 2.1) is outside `schema.py` as well. The backend should accept
  it and may store it; parsers that ignore unknown keys are unaffected.
- The v1 groups (`system`, `fall`, `vitals`, `stress`) are no longer sent.

## Source layout

```
platformio.ini
include/  config.h  frame.h  sensors.h  telemetry.h  buzzer.h  sos.h  i2c_bus.h  settings.h  secrets.example.h
src/      main.cpp       task setup (fast / slow / sos / network)
          imu.cpp        MPU6050 driver, frame aggregates, on-device fall detector
          ppg.cpp        MAX30102: beats -> RR/BPM, Maxim SpO2, perfusion, finger contact
          eda.cpp        Grove GSR -> uS, slope, baseline, calibration
          skintemp.cpp   MAX30205 driver
          baro.cpp       BMP388 mean pressure + in-frame swing
          water.cpp      water-contact electrodes (pulsed excitation, debounce)
          power.cpp      battery divider
          gps.cpp        NEO-6M + geofence
          frame.cpp      frame struct + bounded upload queue
          telemetry.cpp  schema-2 JSON, batched HTTP(S) upload, backoff, Wi-Fi upkeep (network task)
          remote_cmd.cpp commands from the server response, pending acks
          buzzer.cpp     non-blocking buzzer patterns (SOS cues, local alert, buzz command, server critical)
          sos.cpp        SOS button task (debounce, hold / 3 presses / cancel), SOS state, server ack
          webui.cpp      local status page (SOS, sensors, upload link, server health state)
          settings.cpp   NVS-persisted calibration, geofence, boot counter, seq reservation, SOS press id
          i2c_bus.cpp    shared bus + mutex
```
