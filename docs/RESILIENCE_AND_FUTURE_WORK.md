# TRIDENT: degraded conditions, fallbacks and future-work roadmap

This covers what the system does when things go wrong in the field, what was built for it in P6,
and what is deliberately left for later. "Now" means implemented and tested in this repository
(`tests/backend/test_resilience.py` and the related tests); "Future" means designed but not built.

## 1. No or poor internet (mountain floods, remote areas)

The Nepal floods are the typical case: mobile data disappears for hours, 2G voice/SMS often
survives longer, and power is intermittent.

| Situation | What happens now | Future |
|---|---|---|
| **Victim has no mobile data** | The SOS page is a PWA: after one visit it loads offline. A request filled in offline is saved on the phone and sent automatically when a connection returns. The same `Idempotency-Key` is reused, so a retry can never create a second request. | Cell-broadcast alerts. A USSD menu (`*xxx#`) with a telecom operator. |
| **Only SMS works** | "Send by SMS instead" fills in a compact message, `SOS 13.0120,80.2410 P3 I1 Tflood …` (≤ 160 chars). The control room's SMS gateway posts it to `POST /api/v1/sms/inbound`, which accepts typed variants too. The sender gets the reference, priority and a tracking link back. Gateway retries are de-duplicated. | Two-way SMS status updates ("team on the way"). |
| **Wearable loses its uplink** | The device keeps measuring and buffers 8 min (320 frames). When full it drops routine frames first and keeps event frames (fall, impact ≥ 3 g, water contact, geofence). The device's own fall detector and buzzer work without any network. On reconnect the backlog uploads in order with no duplicates. | Flash (LittleFS) buffer for hours of data, down-sampled. On-device fusion so the band alarms locally. |
| **Wearable goes silent while not STABLE** | After 30 s without frames, a `LOST_CONTACT` critical alert opens with the last state, for example "last seen 45 s ago in CONCUSSIVE_STASIS". A dead battery, a submerged band or going out of range is treated as an emergency. | Last-known-position search area on the map. |
| **Control room loses internet** | Everything critical runs on the LAN: API, database, ML, fusion, dispatch, the ROV bridge, and devices on the local network. What is lost:<br>- **Weather:** falls back to the cached forecast, labelled stale.<br>- **River discharge:** the last cached values.<br>- **Map tiles:** markers still show on a blank map with a note. | An offline map-tile pack (MBTiles) for the area of operations. |
| **ROV link to the control room drops** | The station bridge stops the thrusters after 5 s with no server contact. A manual pilot who goes quiet for 120 s also triggers a stop, delivered to real units through the outbox. | A return-home behaviour on the ROV firmware itself. |
| **Server restarts** | Migrations run; a background job releases its leases cleanly, or another replica takes over within 60 s. The per-device fusion state is in memory, so each device recalibrates (about 2 min). | Persist the fusion state for a warm restart. |

### Connectivity options for later (no internet at all)

| Option | Range / bandwidth | Fits TRIDENT how | Hardware |
|---|---|---|---|
| **LoRa / Meshtastic mesh** | 2–15 km per hop, ~1 kbps | Wearables send a compact alert (state, HR, position) every 30–60 s to a field gateway, hopping through other nodes. This is the best fit for mountains. | A SX1262 module on the band (or a LoRa-ESP32 board), gateways at the field base |
| **ESP-NOW relay** | ~200 m per hop, ~1 Mbps | Band to band to a field laptop with no infrastructure, on the ESP32 radio we already have. | None extra (firmware only) |
| **Bluetooth LE to the victim's phone** | ~30 m | The band uses the phone's connectivity, including SMS fallback, through a small companion app. | Phone app |
| **Satellite messaging** | global, short messages | Field teams and base stations (not each band) relay SOS and alerts. | Garmin inReach, Iridium or Swarm modems; Starlink Mini at the field base |
| **Wi-Fi mesh at a shelter** | 100 m per node | Local hotspots for the SOS PWA, plus a portable TRIDENT server ("edge kit"). | Mesh routers, a laptop or Raspberry Pi |

## 2. Not enough teams

| Situation | What happens now |
|---|---|
| **Several urgent requests at once** | Auto-dispatch now runs in order of urgency: P1 before P2, a higher score first, then first-come. The scarce teams go to the most urgent requests. Capacity is checked inside the transaction, so two dispatchers or two requests can't overbook a team. |
| **No free team** | P1/P2 requests that can't be dispatched are flagged `awaiting_resources`. `GET /api/v1/dispatch/capacity` and the `system` WebSocket topic report `ok`, `strained` or `exhausted`, and the ops banner lists who is waiting and for how long. |
| **A lower-priority mission holds the only team** | The system suggests moving a team from an assigned request at least two priority levels lower, as long as it isn't en route yet. A dispatcher must confirm every move. `POST /sos/{ref}/reallocate` moves the team in one transaction; the other request returns to the queue with a note, and both versions are checked. |
| **Extreme case: every signal says a life is at immediate risk** | This is the one exception to "a dispatcher confirms" (owner policy, 2026-10-31). The team is moved at once, with the full evidence written to both timelines and the audit log, when **all** of these hold:<br>- The request is P1 with a triage score ≥ 80.<br>- The linked wearable has been in a critical fusion state with risk ≥ 0.85 for ≥ 60 s.<br>- The environment corroborates it: a water-disaster emergency type, an active weather warning, or a rising river.<br>- No team is free.<br>The team is only ever taken from a P4/P5 request that is not yet en route. |
| **Victim has no phone at all** | The band's **SOS button** (hold 1.5 s, or 3 taps): every frame carries the press until the control room acknowledges it.<br>- **Request:** it becomes an SOS (`source: wearable`, +40 triage points, so at least P2) with the band's GPS position, plus a critical `SOS_BUTTON` alert.<br>- **Feedback:** the band beeps when the request is received, and reminds every 10 s while it is still sending.<br>- **Cancel:** holding the button 5 s adds a note and resolves the alert, but leaves the request for a dispatcher. |
| **Requests waiting a long time** | Priority ageing adds 2 points per 5 min waiting, up to 20, with a "waiting N min" reason. Nothing starves at the bottom of the queue. |
| **People resend the same SOS** | The same phone, or a request within 100 m in the last 2 h, is linked as "possible duplicate of SOS-…". Duplicates are never auto-dispatched, so one emergency can't take two teams. |
| **Wearable of a waiting victim deteriorates** | Re-triage runs every 10 s. A critical wearable state adds 30 points, so the request rises and is dispatched first when a team frees up. |

**Future:**
- Mutual aid: send an automatic request to neighbouring districts (NDRF/SDRF) when the queue is `exhausted` for longer than a set time.
- ETA-aware assignment using road and water routing.
- Self-reported team availability from responders' phones.
- Mass-casualty mode, with a simpler triage form and grouping of nearby requests into one mission.

## 3. Other failure modes

| Situation | Handling |
|---|---|
| Weather API down | The cached forecast is served, with `observed_at` and the source shown; the job retries every 30 min. |
| Weather or wearable models missing | The API keeps working. `/readyz` reports what is missing; fusion rules that need a missing head are skipped and the head is listed as unavailable. |
| Database unavailable | Writes fail with 503 rather than being accepted and lost; devices keep buffering. |
| Duplicate telemetry or out-of-order batches | Ingest is idempotent on (device, boot, seq). An out-of-order frame is stored but not fused. |
| Browser disconnects | The WebSocket reconnects with backoff and reloads the REST snapshot on any sequence gap. |
| Two dispatchers edit the same request | Version check → 409 with the current record; the UI offers to re-apply. |
| A stolen refresh token is replayed | The whole login family is revoked. |
| A device key leaks | Rotate the key in Admin; the old one stops working at once. |
| Battery low | `SENSOR_FAULT` suppresses cardiac rules, and the battery is shown on every device card. |

## 4. Inputs needed from the project owner

| Item | Why | Needed for |
|---|---|---|
| **An SMS gateway**: a provider (MSG91, Twilio, Gupshup, …) or a GSM modem / spare Android phone at the control room running an SMS-forwarder app | Receiving SMS SOS. `TRIDENT_SMS_SECRET` and `TRIDENT_SMS_NUMBER` are already supported. | SMS fallback in production |
| ~~A map-tile key~~: not needed locally (Stadia's dark tiles are served to localhost without a key). For a hosted domain, register the domain in a free Stadia account (no key in code) | Dark basemap | Hosting (CI/CD) |
| Helpline numbers to show the public | The landing page lists 112, 1070 and 1913; confirm these for the deployment area | Public page |
| The device API key in `secrets.h` | Registering the real wearable | Hardware test |
| Production secrets (`TRIDENT_JWT_SECRET`, `TRIDENT_ADMIN_PASSWORD`) | Never seeded in production | CI/CD |
| ~~Policy: should reallocation ever be automatic?~~ Decided: only in the extreme case above | Safety and accountability | Done |


---

# Part II: Future-work roadmap

Every item deferred during P0–P7 and the QA round, plus improvements found along the way, each with an
approach a developer can start from. Status as of 2026-10-31: the platform runs as a **single-node
monolith** (FastAPI + SQLite, in-process ML, scheduler and WebSocket hub), plus a separate vision worker
and the ESP32 firmware. 128 tests pass. Nothing below is built yet unless it says so.

**How to read it.** Each item has a **Why**, an **Approach**, a size (**S** < 1 day, **M** 1–5 days,
**L** 1–3 weeks, **XL** > 3 weeks) and **Needs** (hardware, accounts, data or decisions). Priorities:
**P1** comes next, **P2** after the first deployment, **P3** is later or exploratory.

## 5. Roadmap at a glance

| Horizon | Theme | Items |
|---|---|---|
| **Now (P1)** | Ship it safely | CI pipeline (§13.1); first deployment on one VM with PostgreSQL + TLS + backups (§6.1); hardware bring-up and data collection (§9.1); SMS gateway via the Android phone (§7.1); README / run-docs refresh (P8) |
| **Next (P2)** | Scale and harden | Multi-replica API with Redis (§6.2); telemetry storage tiering (§6.4); observability stack (§12); token/cookie hardening, MFA, privacy controls (§11); responder mobile app (§10.2); camera calibration and a better detector (§9.4) |
| **Later (P3)** | Reach and intelligence | LoRa / mesh networking (§7.3); edge kit with offline-first sync (§7.4); event-streaming backbone (§6.3); flood inundation model (§9.3); ETA/optimised dispatch (§8); TinyML on the band (§9.2); WebRTC video and ROV autonomy (§9.4, §10.4); government / CAP integration (§10.5) |

## 6. Cloud scaling and system design

Today the API keeps five kinds of state in memory: per-device fusion runtimes, the WebSocket hub,
rate-limit buckets, the weather cache and the vision frames. Scaling out means moving each of these
deliberately, not just adding replicas.

### 6.1 First deployment: one VM (P1, M)

**Why.** Hosting was deferred to CI/CD.

**Approach.**
- **Machine:** one always-on VM, for example Oracle Cloud Always Free Arm (about 2 OCPU / 12 GB), or Render Starter as the paid fallback.
- **Containers:** Docker Compose with:
  - `api`: the existing image.
  - `postgres:16`: set `TRIDENT_DATABASE_URL`, and the Alembic migrations already render valid PostgreSQL DDL.
  - `caddy`: automatic HTTPS and HSTS, and it overwrites `X-Forwarded-For`, which the security review requires before rate limits can be trusted.
  - `vision`: optional; usually on the station laptop next to the ROV instead.
- **Backups:** nightly `pg_dump` to object storage (Oracle Object Storage or Backblaze B2 free tier), keeping 14 days. Restore it in a monthly drill.
- **Secrets:** environment from the host's secret store or an `.env` readable only by the service user. `TRIDENT_JWT_SECRET`, `TRIDENT_ADMIN_PASSWORD` and `TRIDENT_SMS_SECRET` must be set; production refuses to start without the JWT secret.
- **Map tiles:** register the domain at Stadia (free, no key in code).

**Needs.** The owner's cloud account and a domain name.

### 6.2 Horizontal API scaling (P2, L)

| State today (in memory) | Move to | Notes |
|---|---|---|
| WebSocket hub fan-out | Redis pub/sub (or PostgreSQL `LISTEN/NOTIFY` for small scale) | Each replica subscribes and fans out to its own sockets. Keep per-topic `seq` in Redis (`INCR`) so clients still detect gaps. |
| Per-device fusion runtime (FeatureEngine buffers, calibration, state timers) | **Device affinity** | Route each device to one ingest worker with a consistent hash on `device_id` (an Nginx/HAProxy `hash` on the `X-Device-Key` header, or a queue partitioned by device). Snapshot the runtime state (about 5 KB per device) to Redis every 30 s for warm failover, which also fixes "a restart loses calibration". |
| Rate-limit buckets | Redis token bucket (atomic Lua script) | Becomes a global limit instead of per replica. |
| Weather and river cache | PostgreSQL `public_data_cache`, which already exists for rivers | One replica refreshes; the others read. |
| Vision latest-frame relay | A separate `vision-relay` service, or Redis with a frame TTL | Keeps large frames out of the API process. |
| Idempotency, leases, refresh tokens | Already in the database | No change; job leases already elect a single runner. |

**Concurrency on PostgreSQL.** Keep optimistic versions. Switch team-capacity checks to
`SELECT … FOR UPDATE` (already written that way) and run auto-triage per request with
`SKIP LOCKED` so replicas can share the work.

### 6.3 Event-streaming backbone (P3, XL)

**Why.** At hundreds of devices, inference should not sit on the HTTP request path, and analytics and
alerts should be consumers rather than code inside ingest.

**Approach.**
- **Pipeline:** `POST /telemetry` validates, writes to **Redpanda/Kafka** (or NATS JetStream) partitioned by `device_id`, and returns 202. An **inference service** consumes in order per partition, runs the heads and fusion, and emits `device.state` events.
- **Consumers:** alerting, the SOS re-triage trigger, and the storage sink (TimescaleDB).
- **Outbox pattern** for SOS and alert events, so WebSocket pushes are never lost between a commit and the publish.
- **Trade-off:** ingest latency grows by roughly 50–200 ms; worth it only beyond about 200 devices.

### 6.4 Telemetry storage tiering (P2, M)

**Why.** About 57 MB per device per day: 20 devices for 7 days is about 8 GB.

**Approach.**
- **Hot:** TimescaleDB hypertable on `telemetry_frames`, with compression after 1 day (5–10× smaller).
- **Warm:** a continuous aggregate of per-minute vitals per device, kept 90 days.
- **Cold:** daily Parquet export to object storage. That is also the training-data lake for §9.1.
- **Permanent:** state transitions, alerts and the audit log are the clinical and legal record.

### 6.5 API evolution (P3, S–M)

- Version the WebSocket messages, and publish an AsyncAPI document alongside the OpenAPI one.
- Use cursor pagination keyed on `(priority_score, created_at, id)` instead of offsets for very long queues.
- Add ETags or `If-Match` headers as an alternative to `version` in request bodies.

## 7. Connectivity in disasters

### 7.1 SMS gateway (P1, S): deferred until the spare Android phone is used

**Approach.**
- Install an open-source SMS gateway app (e.g. *SMS Gateway for Android*, sms-gate.app) on the spare phone, with a local SIM, kept charging at the control room.
- Point its incoming-SMS webhook at `POST /api/v1/sms/inbound`.
- Add a small adapter for the app's payload format if it differs from `{from, text, id}`, plus the `X-SMS-Secret` header.

**Two-way updates.** Use the same app's send API for "team assigned / en route" messages. Add a
`notifications` outbox table with retries, and cap SMS per request to control cost.

**Later.** A cloud provider with an Indian long code (MSG91 / Gupshup / Exotel) for redundancy, and
**USSD / IVR** (press 1 for SOS) through a telecom aggregator for feature phones.

### 7.2 Offline maps (P2, S)

Pre-render an **MBTiles** pack of the operating area (Chennai at zoom 10–16 is a few hundred MB) with
the OpenMapTiles/Planetiler toolchain. Serve it from the API at `/tiles/{z}/{x}/{y}` and have the UI fall
back to it when online tiles fail (the fallback hook already exists).

### 7.3 Networks without internet (P3, L–XL)

| Option | Approach | Fit |
|---|---|---|
| **LoRa / Meshtastic** | Add an SX1262 to the band (or use a LoRa-ESP32 board). Send a 30-byte compact frame every 30–60 s and immediately on SOS/fall: device id, state, HR, battery, lat/lng, SOS flag. A field gateway (LoRa → Wi-Fi/Ethernet) posts to `/api/v1/telemetry`. | Best for mountains and wide areas; 2–15 km per hop. |
| **ESP-NOW relay** | Bands relay each other's compact frames peer-to-peer to a gateway band near a working uplink. | Firmware-only; ~200 m per hop. |
| **BLE companion app** | The band pairs with the victim's phone; a small app forwards frames over whatever the phone has, including SMS fallback. | Uses existing phones. |
| **Satellite** | Base stations and teams carry inReach/Iridium or Starlink Mini; relay SOS digests. | Last resort; costs money. |

### 7.4 Edge kit: offline-first field deployment (P3, XL)

**Why.** A district control room may be cut off from the cloud for days.

**Approach.**
- **Kit:** a Raspberry Pi 5 or laptop with the full stack (API + PostgreSQL + tiles + ML), a Wi-Fi access point, and a LoRa gateway.
- **Ownership:** each SOS and device record gets an `origin_node`.
- **Sync:** when a link returns, sync with the cloud through a change feed (outbox to the cloud's ingest, idempotent on `(origin_node, id)`).
- **Conflicts:** last-writer-wins only for free text. Status transitions are merged by the state machine (the higher state wins); the dispatcher resolves anything else.
- **Simpler v1:** run the edge node as the source of truth for its district, and have the cloud keep a read-only mirror.

### 7.5 Public multi-channel intake (P2–P3)

- **WhatsApp:** a Business Platform bot (provider account needed), which forms a structured SOS from a guided chat or a shared location.
- **Voice:** an IVR in Tamil, Hindi and English.
- **Cell broadcast / CAP:** see §10.5.

## 8. Dispatch intelligence

| Item | Why | Approach | Size |
|---|---|---|---|
| **ETA-aware assignment** | Straight-line distance ignores flooded roads. | OSRM (self-hosted, OSM data) for roads, with flood-closed segments marked from the inundation model (§9.3) or by dispatchers. Rank teams by ETA, not distance. | L |
| **Optimised batch assignment** | Greedy per-request choice is suboptimal under load. | Each auto-triage tick, solve a min-cost assignment (Hungarian method / OR-Tools) over waiting P1–P3 requests and free team slots. Cost = ETA − w·priority. Keep the extreme-case rule (§2) as a hard constraint. | M |
| **Mission clustering** | One boat can rescue several nearby households. | DBSCAN on open requests within ~300 m of each other. Propose "missions" with a route (a small vehicle-routing problem in OR-Tools); a dispatcher confirms. | M |
| **Mutual aid escalation** | Local capacity runs out. | When capacity has been `exhausted` for more than N min, notify configured external contacts (NDRF/SDRF/district control room) by email or SMS with a digest and a link. Log acknowledgements. | S |
| **Mass-casualty mode** | Hundreds of requests per hour. | A simplified 3-question form; grouping by area; triage colours (START-like) instead of five priorities; bulk assignment. | M |
| **Resource inventory** | Boats, fuel, medical kits and food are finite. | Inventory tables per team or depot, consumed by missions, low-stock alerts, and supply requests linked to SOS "food/water critical". | M |
| **Responder status** | Assignment needs true availability. | Responders set on duty / en route / on scene / off duty from the mobile app (§10.2); GPS breadcrumbs. | M |

## 9. ML and computer vision

### 9.1 Real-hardware data and domain shift (P1, M–L)

**Why.** Every head was trained on public datasets passed through the emulator, never on TRIDENT's
own sensors, and the band is worn on the wrist.

**Approach.**
1. Bring-up: flash firmware 2.2.0 and register `TRIDENT-WEAR-01`.
2. Collect 1–2 h per volunteer of rest, walking, stairs and simulated falls onto a mattress, with consent. Use a reference chest strap (Polar H10) for heart rate and RR.
3. Run the existing emulator-vs-device parity report on these recordings.
4. Recalibrate thresholds, or fine-tune heads with the new subjects as an extra tournament fold.
5. Re-run the P5 replay before shipping.

**Needs.** The band, a chest strap (about ₹3–7k) and volunteers.

### 9.2 On-device intelligence (P3, L)

- **TinyML fall and SOS detection on the ESP32:** TFLite Micro, or simply porting the fall Extra-Trees as compiled C if-else via `m2cgen`, so the band raises a local alarm with no network at all.
- **Persistent buffer:** LittleFS ring buffer of compact frames for hours offline, downsampled when old.
- **Secure OTA updates:** signed images and A/B partitions.
- **Battery life:** duty-cycle the PPG and GPS when stable; target a 24 h minimum.

### 9.3 Weather and flood (P2–P3, M–XL)

- **Better forecasts:** use Open-Meteo's NWP forecasts (GFS/ICON) as features; the weather card already notes this as v2. This mainly improves 24–48 h skill and heavy rain.
- **Rain nowcasting (0–3 h):** IMD Doppler radar mosaics, if accessible, with an optical-flow extrapolation (pySTEPS).
- **River levels:** CWC India gauge data, if an API or feed is available, as ground truth for the GloFAS discharge already shown.
- **Inundation mapping:** a DEM (SRTM/Copernicus 30 m) plus rainfall accumulation, with a simple hydrological model (HAND, height above nearest drainage). That gives a per-neighbourhood flood-risk layer for the map and closed roads for routing (§8).
- **Coastal:** tide plus storm-surge alerts (INCOIS) for cyclones.

### 9.4 ROV computer vision (P2–P3)

| Item | Approach | Size |
|---|---|---|
| Camera calibration | A checkerboard routine (`cv2.calibrateCamera`) per ROV camera; store the focal length and distortion per unit (vision-key metadata); undistort before detecting. Distances become ±10–15 %. | S |
| Better detector | YOLOv8s/YOLO11n, fine-tuned on person-in-water and flood imagery (e.g. SeaDronesSee, AFO). Measure recall on people in water specifically. | M |
| Tracking and counting | ByteTrack / BoT-SORT on the detections, so "persons in view" counts unique people over time; alert on a new person. | S |
| Thermal camera | FLIR Lepton on the ROV for night and smoke; fuse RGB and thermal detections. | L |
| Face recognition upgrade | Replace LBPH with embeddings (ArcFace/InsightFace) and an enrolment flow for responders. Do **not** identify victims without consent (§11.3); default to blurring unknown faces. | M |
| Low-latency video | WebRTC (aiortc / a MediaMTX gateway) instead of MJPEG; adaptive bitrate over weak links. | L |
| On-ROV inference | Jetson Orin Nano on the ROV; send detections plus a low-rate preview when bandwidth is scarce. | L |
| Drone imagery | The same worker on drone RTSP feeds; geotag detections from drone telemetry onto the map. | L |

### 9.5 Wearable model improvements (P2)

- **Stress head transfer:** it currently doesn't transfer (Stress-Predict 0.52). Try per-user calibration (baseline normalisation over the first days) and domain adaptation on new device data, or retire it if it stays advisory-only.
- **Rhythm on wrist PPG:** it scored 0.987 window AUROC on fingertip PPG. Next is a wrist-PPG AF dataset, plus signal-quality gating so the band reports only on clean segments.
- **Rule-only states** (cardiac arrest, hypoxia, haemorrhagic shock, hypothermia): validate with clinicians, using simulation-lab data or published case data, before claiming sensitivity.
- **Learning from outcomes:** store the dispatcher's outcome for each alert (true / false / unknown), use it for threshold tuning and periodic re-evaluation, and show the alert precision per state on the AI-predictions tab.
- **Monitoring:** feature-drift dashboards per head (PSI on key features) and an alert when a deployment's input distribution moves.

## 10. Product features

### 10.1 Public side

- **Languages:** Tamil and Hindi for the SOS form and landing page (react-i18next); icon-first steps for low literacy.
- **Voice SOS:** record a short voice note with the request (stored privately).
- **Family reunification:** "find a person" searches the name or phone against resolved requests and shelter check-ins, with consent.
- **Shelter finder:** shelters with capacity, from an admin-managed table, shown on the public map.
- **Public alerts map:** current hazards and river levels, with no personal data.

### 10.2 Responder mobile app (P2, L)

A PWA (or React Native) for team members:
- the assigned mission with navigation
- status buttons and a photo/notes upload
- an offline queue (same outbox pattern as the SOS form)
- push notifications (Web Push / FCM)
- GPS breadcrumbs

### 10.3 Console

- **Upgrades:** react-router v7, which closes the two moderate advisories.
- **Errors:** Sentry (or GlitchTip, self-hosted) for frontend errors.
- **Reports:** a post-incident PDF of timelines, response times and resource usage.
- **Saved views and filters.**
- **Shift handover:** a summary of open items at shift change.

### 10.4 ROV

- **Firmware autonomy:** waypoint navigation on the ROV firmware itself (GPS/compass), with return-home on link loss so it doesn't depend on the bridge.
- **Collision avoidance:** sonar (Ping2) for obstacles and depth.
- **Fleet coordination:** coverage search patterns across several ROVs.
- **Mission replay:** playback from the 1 Hz track already stored.

### 10.5 Integrations

- **CAP (Common Alerting Protocol):** ingest official alerts (NDMA SACHET / IMD CAP feeds) as hazards. Publish TRIDENT situation summaries as CAP for other agencies.
- **112 / ERSS:** API partnership, if possible, for two-way case exchange.
- **GIS export:** GeoJSON / KML of requests and missions for district GIS teams.

## 11. Security and privacy

| Item | Approach | Size |
|---|---|---|
| Refresh token out of localStorage | An HttpOnly, Secure, SameSite=Strict cookie on `/api/v1/auth/refresh` only, plus a CSRF header check. Access token stays in memory. | S |
| MFA for admins and dispatchers | TOTP (pyotp) with recovery codes; required for the admin role. | S |
| Per-account lockout | Exponential backoff per username after failed logins, alongside the per-IP limit. | S |
| Audit log integrity | Hash-chain each audit row (store the previous row's hash), with daily anchoring to object storage, so tampering is detectable. | S |
| Device transport | HTTPS with CA pinning in the firmware (`WiFiClientSecure.setCACert`); the ROV bridge on HTTPS only; consider mTLS per device later. | M |
| Encryption at rest | Disk encryption on the VM. Column-level encryption (pgcrypto) for phone numbers and notes. | S–M |
| Secrets management | Doppler, Infisical or a cloud secret manager; rotate the JWT secret with a key id (`kid`) and two active keys. | S |
| WAF / DDoS | Cloudflare free plan in front of the public SOS page. | S |
| Dependency hygiene | Dependabot/Renovate, `pip-audit` and `npm audit` in CI, Trivy image scans. | S |

### 11.3 Privacy and compliance

- **India DPDP Act 2023:** a purpose-limited consent notice on the SOS form and the wearable enrolment. A data retention policy, for example: purge personal data from requests resolved more than 180 days ago, and anonymise for analytics. Data-subject requests for access and deletion handled by an admin tool.
- **Face recognition:** enrolled responders only, with written consent. Unknown faces are never stored, and are blurred in recordings by default. Document this in a DPIA.
- **Medical disclaimer:** TRIDENT is decision support, not a certified medical device. If clinical claims are ever made, the path is CDSCO medical-device rules and IEC 62304-style processes.

## 12. Observability and operations (P2, M)

- **Metrics:** `/metrics` already exists. Add Prometheus + Grafana dashboards: ingest rate, inference latency, WebSocket clients, alert open/ack times, job health, database locks.
- **Tracing:** OpenTelemetry for FastAPI and SQLAlchemy, exported to Grafana Tempo/Jaeger. Trace a frame from device to alert.
- **Logs:** they are already JSON in production. Ship them to Loki, keyed by `request_id`.
- **SLOs and paging:**

  | SLO | Target |
  |---|---|
  | SOS intake availability | 99.9 % |
  | Critical alert from frame to the console | p95 < 5 s |
  | Device ingest success | 99.5 % |

  Pages go to on-call through ntfy / Telegram / PagerDuty free.
- **Runbooks:** database restore, a device key leak, a ROV runaway, a weather API outage, an SMS gateway outage.
- **Drills:** a monthly tabletop exercise with the replay simulator.

## 13. Engineering process

### 13.1 CI pipeline (P1, M)

GitHub Actions, once git access is the owner's own:
1. `pytest` for backend and ML, with a PostgreSQL service container running the migrations for real.
2. `npx tsc --noEmit` and `npm run build`.
3. `python -m platformio run` for the firmware.
4. `pyflakes` / `ruff`.
5. `pip-audit` and `npm audit`.
6. Docker build and a Trivy scan.
7. On main: deploy to staging; a manual promote goes to production.

### 13.2 Testing

- **Browser E2E in CI:** Playwright, covering the role flows, offline SOS and the ROV takeover. The CDP scripts from QA are the starting point.
- **Load tests:** k6/Locust scenarios from the QA report (bursts, 20-device telemetry, WebSocket fan-out), run weekly against staging.
- **Chaos:** kill API replicas, pause PostgreSQL, drop the network to the weather API.
- **Hardware-in-the-loop:** a bench rig with the band on a test fixture (shaker for falls, a PPG simulator), driven by CI on a self-hosted runner.

## 14. Open decisions for the owner

| Decision | Options | Recommendation |
|---|---|---|
| First host | Oracle Always Free VM, Render Starter ($7), Cloud Run | Oracle VM with Docker Compose (§6.1) |
| SMS path | Android phone gateway, cloud provider | Android phone first, a cloud provider as backup |
| Video transport for real ROVs | Keep MJPEG, move to WebRTC | MJPEG until a real camera is fitted; WebRTC when bandwidth is constrained |
| Face recognition scope | Responders only, everyone with consent, off | Responders only; blur others |
| Data retention | 90 / 180 / 365 days for personal data | 180 days, then anonymise |
| Long-range band networking | LoRa, ESP-NOW, BLE + phone | LoRa (Meshtastic-compatible) for the mountain use case |
