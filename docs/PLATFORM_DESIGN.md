# TRIDENT platform design and API contract

P6 replaces the single-file Flask backend (`src/backend/main.py`) and the single-page UI with:

- `src/backend/app/`: FastAPI service, SQLAlchemy 2 + Alembic, JWT auth, WebSockets, background scheduler
- `src/ml/weather/`: multi-variable, multi-horizon weather forecaster with live observations
- `src/frontend/web/`: React + Vite + TypeScript console, built to static files served by the API
- firmware v2 updated to this contract (P7)

Decisions confirmed by the user (2026-10-30):

| Decision | Choice |
|---|---|
| Framework | FastAPI |
| Database | SQLite with WAL now, PostgreSQL by changing one URL |
| Access | Staff log in, with roles; the public SOS form stays open |
| UI | React + Vite, "operations console", dark |
| Weather | Multi-variable forecasts, live data |
| Live demo | A replay simulator |
| P7 | Update the firmware and compile it |

Hosting is deferred to CI/CD.

---

## 1. Design principles applied

### Consistency and availability (CAP)

TRIDENT runs on a single primary database. Different data has different needs, and the choices follow from that.

| Data | Choice | Why and how |
|---|---|---|
| SOS requests, assignments, team capacity, alerts | **Consistency first (CP)** | Two dispatchers must never send the same team twice, or lose a status change. All writes go to the primary in ACID transactions with optimistic locking. If the DB is unreachable, the API returns 503 rather than accepting a write it can't commit. |
| Wearable telemetry | **Availability first (AP)** | A device must never block on the server. Firmware keeps 320 frames (8 min) offline, keeping event frames when full, and flushes them in `seq` order. The server ingests idempotently on `(device_id, boot, seq)`, so retries and replays are safe and don't create duplicates. Late frames are still stored; fusion runs in arrival order per device. |
| Real-time push (WebSocket) | **Best effort** | Clients load a REST snapshot, then apply deltas. Every message carries a per-topic `seq`; on a gap or a reconnect, the client reloads the snapshot. The WebSocket is never the source of truth. |

### ACID and concurrency

- These steps happen in **one transaction each**:
  - creating an SOS, with its first status history row and audit row
  - assigning a team: the SOS, the assignment, the team's load and the history
  - opening an alert, with any SOS escalation
- **Optimistic locking:** `sos_requests.version` is incremented on every update. A client sends the `version` it saw, and the server answers **409 Conflict** if the row has changed since.
- **State-machine transitions** are enforced in the service layer, not the UI. The allowed SOS transitions are:

  ```
  pending → triaged → assigned → en_route → on_scene → resolved
  any non-final state → cancelled
  ```

- **SQLite:** WAL mode, `foreign_keys=ON`, `busy_timeout`, and `BEGIN IMMEDIATE` for write transactions.
- **PostgreSQL:** the same code at READ COMMITTED, plus `SELECT … FOR UPDATE` on team capacity.

### Idempotency

| Operation | Mechanism |
|---|---|
| Telemetry | A unique key on `(device_id, boot, seq)` |
| SOS submit | An optional `Idempotency-Key` header, stored for 48 h; a repeat returns the original response |
| Device commands | Each command has an id and moves through `queued → delivered → acked` (outbox pattern) |

### Scheduling (background jobs)

An in-process scheduler (`app/jobs/`) runs periodic jobs. Leader election uses a lease row in the database (`scheduler_leases`), so with several API replicas only one runs the jobs.

| Job | Interval | Purpose |
|---|---|---|
| `weather_refresh` | 30 min | Pull Open-Meteo observations and recompute the forecast; publish to `weather` |
| `device_liveness` | 15 s | Mark a device offline after 30 s without frames; open an alert for a device that is in a critical state |
| `sos_auto_triage` | 10 s | Score pending SOS (form plus linked wearable state) and auto-assign by capacity |
| `alert_escalation` | 30 s | Escalate a critical alert not acknowledged within 2 min |
| `rov_simulation` | 1 s | Advance simulated ROVs (autonomous transit, manual thrust, dead-man stop); record the 1 Hz track; publish to `rov` |
| `public_data` | 3 h | Refresh river discharge (Open-Meteo Flood API, GloFAS) into `public_data_cache` |
| `retention` | 6 h | Delete raw telemetry frames older than 7 days (state transitions and alerts are kept); purge expired idempotency keys and refresh tokens |

### Authentication and authorisation (JWT)

**Staff tokens**

- **Access JWT:** HS256, valid 15 min. Claims: `sub`, `role`, `exp`, `iat`, `jti`.
- **Refresh token:** opaque and random, valid 7 days. It is stored as a SHA-256 hash in `refresh_tokens`, together with a `family_id`.
- **Rotation:** every refresh rotates the token. Reusing an already-rotated token revokes the whole family, which detects theft.

**Roles (RBAC)**

| Role | Can |
|---|---|
| `admin` | Everything, including users and devices |
| `dispatcher` | Triage, assign and change SOS status, send device commands, acknowledge alerts |
| `responder` | Read everything; change the status of SOS assigned to their team; acknowledge alerts |
| `viewer` | Read only |

**Devices**

- Each wearable has its own API key, sent as `X-Device-Key`. Only the SHA-256 hash is stored, and the key is shown once.
- `POST /devices/{id}/rotate-key` replaces it.

**Public endpoints**

`POST /sos` and `GET /sos/track/{ref}` need no login. A tracking token is returned when the SOS is created and is needed to view its status. Both endpoints have per-IP token-bucket rate limits.

**Hardening**

- Passwords are hashed with bcrypt.
- CORS uses an allow-list.
- Security headers are set: CSP, X-Content-Type-Options, Referrer-Policy and frame-ancestors.
- Pydantic validates every input.
- Every write appends a row to `audit_log`.

### Observability

- JSON logs carry a `request_id`, which is also returned as `X-Request-ID`.
- `/healthz` reports liveness.
- `/readyz` checks the database, the ML runtime and the weather model.
- `/metrics` exposes request counts, latency histograms, ingest rate and WebSocket clients in Prometheus text format.

---

## 2. API contract (`/api/v1`)

### Conventions

- **Errors:** `{"error": {"code": "conflict", "message": "...", "details": {...}}, "request_id": "..."}`.
- **Status codes:** 400/422 validation, 401 unauthenticated, 403 forbidden, 404, 409 version conflict, 429 rate limit, 503 dependency down.
- **Lists:** `{"items": [...], "next_cursor": "..." | null}`, with `?limit=` (max 200) and `?cursor=`.
- **Timestamps:** ISO-8601 UTC with `Z`.
- **Auth header:** `Authorization: Bearer <access>` unless marked public or device.

### Auth

| Method | Path | Body → Response |
|---|---|---|
| POST | `/auth/login` | `{username, password}` → `{access_token, refresh_token, token_type:"bearer", expires_in, user}` |
| POST | `/auth/refresh` | `{refresh_token}` → same as login |
| POST | `/auth/logout` | `{refresh_token}` → 204 |
| GET | `/auth/me` | → `user` = `{id, username, display_name, role, team_id}` |
| GET/POST/PATCH | `/users`, `/users/{id}` | admin only |

### SOS

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/sos` | public | Body below → `{reference_id, tracking_token, priority, status}` |
| GET | `/sos/track/{ref}?token=` | public | `{reference_id, status, priority, created_at, updated_at, team_name?, eta_min?, history:[{status, at}]}` |
| GET | `/sos` | staff | Filters: `status`, `priority_min`, `type`, `q`, `since` |
| GET | `/sos/{ref}` | staff | Full record + `history`, `notes`, `assignments`, `linked_device` |
| PATCH | `/sos/{ref}/status` | dispatcher+, responder on own team | `{status, note?, version}` |
| POST | `/sos/{ref}/assign` | dispatcher+ | `{team_id, version}` |
| POST | `/sos/{ref}/notes` | staff (not viewer) | `{text}` |
| POST | `/sos/{ref}/reallocate` | dispatcher+ | `{team_id, from_reference_id, version, from_version}`: atomically moves a team from a lower-priority request that is `assigned` (not yet en route) |
| GET | `/dispatch/capacity` | staff | `{status: ok\|strained\|exhausted, teams_free, teams_total, waiting[], suggestions[], updated_at}`, also pushed on WS topic `system` (`event: capacity`) |
| POST | `/sms/inbound` | SMS gateway (`X-SMS-Secret`) | `{from, text, id?}` → `{reference_id, tracking_token, priority, reply}`; off unless `TRIDENT_SMS_SECRET` is set |

SOS records also carry:
- `source`: `web`, `sms` or `wearable`
- `duplicate_of`: the reference of an earlier open request from the same phone, or within 100 m in the last 2 h
- `waiting_min`
- `awaiting_resources`

`age` may be null for SMS requests. Alerts may have `state: LOST_CONTACT`. `/public/summary` includes `sms_number`. Degraded conditions and future work are covered in [RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md).

**SOS submit body**

```json
{"name","age","phone","email?","address","city","pincode",
 "people_to_rescue","people_injured",
 "food_availability":"adequate|limited|critical|none",
 "water_availability":"adequate|limited|critical|none",
 "vulnerabilities":{"pregnant","elderly","children","disabled","medical"},
 "emergency_type":"flood|tsunami|dam-breach|storm|water-level-rising|coastal-erosion|medical|other",
 "additional_info?","latitude?","longitude?","device_id?"}
```

**SOS record**

```json
{"reference_id":"SOS-7K2Q9X", "...submitted fields...",
 "priority":1-5 (P1 = most urgent), "priority_score":0-100 (higher = more urgent), "priority_reasons":["2 injured","medical need","wearable: CONCUSSIVE_STASIS"],
 "status", "version", "assigned_team":{"id","name"}|null,
 "created_at","updated_at"}
```

### Teams

| Method | Path | Notes |
|---|---|---|
| GET | `/teams` | `[{id, name, type, location, capacity, current_load, is_available, deployment_mode}]` |
| PATCH | `/teams/{id}` | dispatcher+: `{is_available?, capacity?}` |

### Devices and telemetry

**Ingest (device auth, `X-Device-Key`)**

- `POST /telemetry` takes one schema-2 frame (`src/ml/wearable/schema.py`), or a batch: `{"frames":[...], "acks":[command_id,...]}`.
- The response is:

  ```json
  {"accepted":n, "duplicates":n,
   "commands":[{"id","action","params"}],
   "state":{"ml_health_state","ml_risk_score","alert_level"}}
  ```

- Commands are marked `delivered` when they are returned, and `acked` when their ids come back in `acks`.
- `POST /api/telemetry/wearable` (outside v1) remains a legacy alias for v1 firmware.

**Staff endpoints**

| Method | Path | Notes |
|---|---|---|
| GET | `/devices` | `[{device_id, label, online, last_seen, battery_v, location, state:{ml_health_state, alert_level, risk, evidence[]}, heads:{...}}]` |
| POST | `/devices` | admin: `{device_id, label}` → `{device_id, api_key}` (key shown once) |
| POST | `/devices/{id}/rotate-key` | admin → `{api_key}` |
| POST | `/devices/{id}/commands` | dispatcher+: `{action: reset_fall|calibrate_gsr|set_geofence|buzz, params}` → command |
| GET | `/devices/{id}/frames?since=&limit=` | Flat frames (`schema.FIELD_NAMES`, `rr_ms`) plus the fusion output per frame |
| GET | `/devices/{id}/states?since=` | State transitions `[{state, alert_level, risk, evidence, at}]` |

### Alerts

- Opened automatically when a device enters a **critical** state (`alert_level` = critical). Advisory states are events only.
- `GET /alerts?status=open|acked|resolved`
- `POST /alerts/{id}/ack`
- `POST /alerts/{id}/resolve` with `{note?}`
- Alert record: `{id, device_id, state, risk, evidence, status, opened_at, acked_by?, acked_at?, resolved_at?, sos_reference_id?}`

### Weather

- `GET /weather/current` → `{site, observed_at, temp_c, rh, rain_mm, wind_ms, gust_ms?, pressure_hpa, source:"open-meteo"|"offline-csv"}`
- `GET /weather/forecast?hours=48` returns the payload below. Every variable has `p10`, `p50` and `p90` values.

  ```json
  {"site", "generated_at", "model_version",
   "horizon":[{"time",
               "temp_c":{"p10","p50","p90"},
               "rain_mm":{"p10","p50","p90"},
               "wind_ms":{"p10","p50","p90"},
               "pressure_hpa":{"p10","p50","p90"},
               "rh":{"p10","p50","p90"}}],
   "hazards":[{"type":"heat|heavy_rain|flood_risk|high_wind",
               "level":"watch|warning",
               "from","to","reason"}]}
  ```

- `GET /weather/model` → model card: candidates, backtest skill per variable and horizon, chosen models, training data range.

### ROV missions (semi-autonomous; added at the user's request)

**Modes**
- In `auto` the unit navigates itself to its target (deploy) or home (recall).
- A dispatcher can **take over**. Only that pilot can drive it until **release**; an admin can take over regardless.
- **STOP** is accepted from any responder at any time.
- A manual unit cuts its thrust after 120 s with no command (dead-man), so a lost browser never leaves a ROV driving.

**Real and simulated units**
- Real units connect through the serial bridge (`src/rov/bridge.py`), which speaks the station protocol of `src/rov/communication/serial_interface.py`.
- Units without a bridge are simulated, and every payload says which it is (`link`: `simulated`, `online` or `offline`).
- A camera feed is shown only if the unit has a `video_url`; nothing is faked.

**Endpoints**

| Method | Path | Notes |
|---|---|---|
| GET | `/rov` | `[RovUnit]` (shape below) |
| GET | `/rov/{id}/track?minutes=30` | 1 Hz samples `{t, lat, lng, depth_m, heading_deg, battery_pct, water_temp_c}` |
| GET | `/missions` | `[{rov, sos, team, victims:[{reference_id, name, status, priority, device_id, device}]}]`. Victims are the mission's own SOS plus the open SOS assigned to the ROV's team; `device` is the live wearable. |
| POST | `/rov/{id}/deploy` | dispatcher+: `{reference_id}` |
| POST | `/rov/{id}/recall`, `/rov/{id}/reset` | dispatcher+ |
| POST | `/rov/{id}/stop` | responder+ |
| POST | `/rov/{id}/takeover`, `/rov/{id}/release` | dispatcher+, exclusive (409 if someone else is piloting) |
| POST | `/rov/{id}/control` | Pilot only: `{command: forward\|backward\|left\|right\|up\|down\|stop\|lights_on\|lights_off, speed_pct}` |
| POST | `/rov/{id}/bridge-key` | admin: `{video_url?}` → `{api_key}`; marks the unit as real |
| POST | `/rov/bridge/telemetry` | Bridge auth `X-ROV-Key`: `{depth_m?, heading_deg?, water_temp_c?, battery_pct?, latitude?, longitude?, acks?}` → `{commands:[{id, lines:["forward_75"]}], mode, status}` |

**RovUnit**

```json
{"id","name","status":"idle|deploying|on_mission|returning|stopped",
 "mode":"auto|manual","pilot","battery_pct","latitude","longitude",
 "depth_m","heading_deg","water_temp_c","speed_pct","thrust","lights_on",
 "link","last_seen","target","home","mission_reference_id","team_id",
 "video_url","simulated","mission_started_at","updated_at"}
```

### Analytics (computed live; never hardcoded)

| Method | Path | Notes |
|---|---|---|
| GET | `/analytics/summary` | |
| GET | `/analytics/timeseries?metric=sos_created\|sos_resolved\|alerts\|telemetry_frames\|state_changes&bucket=minute\|hour\|day&since=` | |
| GET | `/analytics/breakdown?by=type\|status\|priority` | |
| GET | `/analytics/response-times` | |
| GET | `/analytics/sensors` | Per device, from the last 10 min of frames: frame rate, signal availability (PPG, EDA, temperature, IMU, GPS, SpO₂), 24 h share of time in each state, battery |
| GET | `/analytics/performance` | Response-time percentiles by priority, alert acknowledgement time, team utilisation, ROV transit times |
| GET | `/analytics/geo` | SOS, devices, teams, ROVs, a ~1 km SOS density grid, and **rivers**: Adyar, Cooum and Kosasthalaiyar daily discharge, 30 days back and 14 ahead, from the Open-Meteo Flood API (GloFAS), refreshed every 3 h |
| GET | `/analytics/models` | Measured model cards: Tier-1 metrics from the P4 registry, P5 fusion replay false alarms, the MIMIC PERform AF external test, and the weather backtest |
| GET | `/public-data/rivers` | |
| GET | `/public/summary` | Public; the landing-page strip |

### Health

`GET /healthz`, `/readyz` and `/metrics`, all outside `/api/v1`.

### WebSocket `/ws?token=<access_token>`

**Server → client**

```json
{"type":"event", "topic":"sos|alerts|devices|weather|rov|system", "seq":n, "ts", "data":{...}}
```

- **On connect:** `{"type":"hello","server_time","topics":[...]}`.
- **Client → server:** `{"type":"subscribe","topics":[...]}` and `{"type":"ping"}`.

| Topic | `data` |
|---|---|
| `sos` | `{event: created\|updated\|assigned\|note, sos: <SOS record>}` |
| `alerts` | `{event: opened\|acked\|resolved\|escalated, alert}` |
| `devices` | `{event: frame\|state\|online\|offline, device_id, summary}`. The frame summary is throttled to one per device per 1.5 s and holds `{bpm, spo2, temp_skin_c, eda_us, acc_std_g, battery_v, lat, lng, state, risk, heads}`. |
| `weather` | `{event: updated, current, forecast_summary}` |
| `rov` | `{event: telemetry\|deployed\|recalled\|stopped\|control\|mode, rov}`, telemetry at 1 Hz per active unit |

---

## 3. Weather service interface (`src/ml/weather/`)

```python
from src.ml.weather.serving import WeatherService
svc = WeatherService.load()                 # reads models/weather/registry.json; no torch import at serving
svc.site                                    # {'name','lat','lon','timezone'}
obs = svc.fetch_observations(hours=168)     # hourly DataFrame; Open-Meteo, falls back to local CSV (obs.attrs['source'])
fc  = svc.forecast(obs, hours=48)           # JSON-able dict, exactly the /weather/forecast payload
svc.current(obs)                            # the /weather/current payload
svc.model_card()                            # the /weather/model payload
```

---

## 4. Live replay simulator

`python -m src.backend.app.tools.simulate`:
- registers virtual wearables
- streams real recorded sessions (PPG-DaLiA, WESAD, a HIFD fall followed by stillness) through `POST /api/v1/telemetry`, at real time or faster
- uses device keys, so the stream takes the same path as real hardware: auth, schema parse, Tier-1 heads, fusion, alerts and WebSocket

Every frame is real recorded data passed through the device emulator. Nothing is invented.

---

## 5. Changes from QA (2026-10-31)

**SOS intake**
- `age` and `pincode` are optional: a person in distress may not know or want to type them.
- Idempotency keys are namespaced by channel (`web`, `sms`, `wearable`), so a public key can never collide with an SMS or band request.
- A retry with an already-accepted `Idempotency-Key` is answered before the rate limit.
- Rate limits: public SOS defaults to 20/min with a burst of 10 per IP (shelter Wi-Fi and CGNAT share addresses). SMS has its own bucket, applied before the secret check.

**Wearable links**
- A `device_id` on a public or SMS request is only a claim (`device_verified: false`). It counts for triage, alerts and extreme-case reallocation only once the band itself raised the SOS, or a dispatcher confirms it with `POST /sos/{ref}/link-device {device_id|null}`.
- `GET /sos/{ref}` returns `linked_device` in the `GET /devices` shape.

**Errors and limits**
- A locked, read-only or unreachable database returns **503** with `Retry-After`; unexpected errors return one clean 500.
- Request body limits: 256 kB by default, 2 MB for telemetry, 1 MB for vision frames.
- API responses carry `Cache-Control: no-store`, and `X-Request-ID` is sanitised.
- Bad `since` values return 422, and time series are bounded (minute buckets: 1 day; hour: 31 days; day: 2 years).

**Telemetry**
- Frames are validated one by one; a malformed frame is counted in `rejected` instead of failing the batch.
- The band's `sos` group must have `press_id` (0 ≤ id < 2³²) and a boolean `active` or `cancelled`.
- Without models, a device's state is `UNKNOWN`, not `STABLE`.

**WebSockets**
- Sockets re-check the account every 30 s and are closed on deactivation, role change or logout.
- Each user may have at most 10 sockets.
- A foreign `Origin` is closed with 4403, a bad token with 4401.
- Tokens and stream tickets are redacted from logs.

**Health and jobs**
- `/readyz` includes a write probe (`writable`). In production it hides details, and `/api/docs` is off unless `TRIDENT_EXPOSE_DOCS=true`.
- A failed job is retried with backoff (5 s to 300 s) instead of waiting a full interval. Fast safety jobs use short leases (10 s).

**ROV camera / computer vision**
- The vision worker (`python -m src.cv.vision --key … --source <camera|url|file|demo>`) runs YOLOv8n, Haar + LBPH and pinhole distance estimates, and posts annotated JPEGs.
- Endpoints:

| Method | Path | Notes |
|---|---|---|
| POST | `/rov/{id}/vision-key` | admin |
| POST | `/rov/vision/frame` | `X-ROV-Vision-Key`, `{jpeg_b64, detections}` |
| GET | `/rov/{id}/vision` | |
| POST | `/rov/{id}/vision/ticket` | Single-use, 60 s |
| GET | `/rov/{id}/vision/stream?ticket=` | MJPEG |

- RovUnit carries a `vision` summary, and the `rov` topic adds `event: vision`.
