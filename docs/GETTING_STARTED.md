# Getting started with TRIDENT

This guide takes you from a fresh clone to a running command center with live demo data, and then
to real hardware. It is written for a developer or operator who is new to the repository.

For production hosting, see [DEPLOYMENT.md](DEPLOYMENT.md). For how the pieces fit together, see
[ARCHITECTURE.md](ARCHITECTURE.md) and [PLATFORM_DESIGN.md](PLATFORM_DESIGN.md). For day-to-day use
of the console, see [USER_GUIDE.md](USER_GUIDE.md).

## Contents

1. [What you are running](#1-what-you-are-running)
2. [Prerequisites](#2-prerequisites)
3. [Install](#3-install)
4. [Build the web console](#4-build-the-web-console)
5. [Run the server](#5-run-the-server)
6. [First login and a 5-minute tour](#6-first-login-and-a-5-minute-tour)
7. [Live demo: simulator, vision worker, ROV mission](#7-live-demo-simulator-vision-worker-rov-mission)
8. [Run the tests](#8-run-the-tests)
9. [Connect real hardware](#9-connect-real-hardware)
10. [Configuration](#10-configuration)
11. [Data and model files](#11-data-and-model-files)
12. [Troubleshooting](#12-troubleshooting)

## 1. What you are running

| Component | Location | What it does |
|---|---|---|
| API server | `src/backend/app/` (entry point `app.py`) | FastAPI service: SOS intake and dispatch, wearable telemetry, ML inference, alerts, ROV missions, weather, analytics, WebSocket. Also serves the built web console at `/`. |
| Web console | `src/frontend/web/` | React app: the public request-help site and the staff console. Built to static files that the API serves. |
| Wearable ML | `src/ml/wearable/` | Tier-1 heads (activity, fall, heart rhythm, HR trust, stress) and Tier-2 fusion. Served from `models/wearable/`. |
| Weather model | `src/ml/weather/` | 48-hour forecast and hazard flags for Chennai. Served from `models/weather/`. See [WEATHER_MODEL.md](WEATHER_MODEL.md). |
| Replay simulator | `src/backend/app/tools/simulate.py` | Virtual wearables that stream real recorded sessions into the API. |
| Wearable firmware | `src/firmware/` | ESP32 firmware that posts a telemetry frame every 1.5 s. See [src/firmware/README.md](../src/firmware/README.md). |
| ROV serial bridge | `src/rov/bridge.py` | Connects a physical ROV on a USB serial port to the API. |
| ROV vision worker | `src/cv/vision/` | Camera to YOLOv8n person/object detection and LBPH face recognition, streamed to the mission dashboard. See [src/cv/README.md](../src/cv/README.md). |

Only the API server is required. Everything else is optional and can be added one piece at a time.

## 2. Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.11 or newer (the development machine uses 3.13; the Docker image uses 3.12) | API server, simulator, tests, ML, bridge, vision worker |
| Node.js | 22 (with npm) | Building the web console |
| Git | any recent | Cloning |
| A USB serial driver for your ESP32 board (CP210x or CH340) | | Flashing the wearable only |

Check what you have:

```bash
python --version
node --version
npm --version
```

On Windows, if `python` opens the Microsoft Store or reports the wrong version, use the launcher
instead (`py -3.13 --version`) and replace `python` with `py -3.13` in the commands below.

## 3. Install

All commands run from the repository root unless a step says otherwise.

### 3.1 Create a virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell refuses to run the activation script, allow local scripts for your user once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Windows (Git Bash):

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 3.2 Install Python packages

There are three requirement files:

| File | Contents | Use it when |
|---|---|---|
| `requirements-prod.txt` | API server plus wearable/weather inference (FastAPI, SQLAlchemy, Alembic, onnxruntime, LightGBM, psycopg). No torch, no training stack. | You only want to run the server. |
| `requirements-ml.txt` | Training stack (torch, scikit-learn, xgboost, optuna, mlflow, ONNX export). | You want to retrain models. Pulled in by `requirements.txt`. |
| `requirements.txt` | Everything: the two files above, plus the vision worker (`ultralytics`, `opencv-contrib-python`), the ROV bridge (`pyserial`), PlatformIO and test tools (`pytest`, `pillow`, `jsonschema`). | Full development, the live demo with the camera, tests, firmware. |

Full development environment:

```bash
pip install -r requirements.txt
```

Serving only:

```bash
pip install -r requirements-prod.txt
```

`requirements.txt` is large (torch alone is several hundred MB). If you only need the server plus
the camera demo, install `requirements-prod.txt` and then
`pip install "ultralytics>=8.3" "opencv-contrib-python>=4.11"`.

## 4. Build the web console

The API serves the built console from `src/frontend/web/dist/`. Build it once, and again after
any change to the frontend.

```bash
cd src/frontend/web
npm ci
npm run build
cd ../../..
```

`npm run build` runs the TypeScript type check and then the Vite production build.

For frontend work you do not need to rebuild on every change; use the Vite dev server instead:

| Command (in `src/frontend/web`) | What it does |
|---|---|
| `npm run dev` | Dev server on http://localhost:5173 with hot reload. Proxies `/api`, `/ws` and `/healthz` to http://localhost:8000, so the API server must be running. To proxy elsewhere, set `TRIDENT_API` (PowerShell: `$env:TRIDENT_API='http://host:port'; npm run dev`, Bash: `TRIDENT_API=http://host:port npm run dev`). |
| `npm run dev:mock` | Same, with an in-browser mock backend. No API server needed. Mock users are `admin`, `dispatcher`, `responder`, `viewer`, all with password `trident` (not the server's demo password). |
| `npm run typecheck` | TypeScript check only. |
| `npm run build:mock` | Builds a demo bundle with the mock compiled in. It also writes to `dist/`, so run `npm run build` again before you serve the real console. |

More detail: [src/frontend/web/README.md](../src/frontend/web/README.md).

## 5. Run the server

```bash
python app.py
```

Open http://localhost:8000.

- `app.py` starts uvicorn on `127.0.0.1:8000` with auto-reload (reload is off when
  `TRIDENT_ENV=production`). Override the bind address and port with the `HOST` and `PORT`
  environment variables (these two have no `TRIDENT_` prefix).
- Interactive API documentation is at http://localhost:8000/api/docs (only outside production,
  unless `TRIDENT_EXPOSE_DOCS=true`).
- The equivalent uvicorn command is
  `python -m uvicorn src.backend.app.main:app --host 127.0.0.1 --port 8000`.

**What happens on the first start**

1. Alembic migrations are applied to the database. By default this is SQLite at
   `data/databases/trident.db`, created if it does not exist.
2. Reference data is seeded: five rescue teams, two ROV units (`ROV-001`, `ROV-002`) and the
   emergency contact numbers. Seeding is idempotent and runs on every start.
3. Outside production, four demo staff accounts are created, all with the password
   `trident-demo-2026`:

   | Username | Role | Notes |
   |---|---|---|
   | `admin` | admin | Everything, including the Admin page, device registration and keys |
   | `dispatcher` | dispatcher | Dispatch, alerts, ROV deployment and control |
   | `responder` | responder | Member of team "Chennai ROV Alpha" |
   | `viewer` | viewer | Read-only |

4. The wearable models and the weather service load in background threads, and the job
   scheduler starts (device liveness, auto-triage, alert escalation, ROV simulation, weather
   refresh every 30 minutes, river data every 3 hours, retention).

If `TRIDENT_ADMIN_PASSWORD` is set and no `admin` user exists yet, an `admin` account is created
with that password instead.

**Helper scripts.** `scripts/deployment/start_app.sh` (Linux/macOS/Git Bash) and
`scripts/deployment/start_app.bat` (Windows `cmd`) build the console if `dist/index.html` is
missing and start the API on port 8000. With `--demo` they also start the replay simulator with
`--with-sos`:

```bash
scripts/deployment/start_app.sh --demo
```

```powershell
scripts\deployment\start_app.bat --demo
```

## 6. First login and a 5-minute tour

Go to http://localhost:8000/login and sign in as `admin` / `trident-demo-2026`. Without live data
most pages are quiet; start the simulator first ([section 7](#7-live-demo-simulator-vision-worker-rov-mission))
if you want something to look at.

| Page | What to look at |
|---|---|
| `/ops` | The operations overview: the SOS queue, open alerts, the map with teams, ROVs and requests, and dispatch capacity. Press `?` for keyboard shortcuts (`1` to `7` switch pages, `/` searches the queue). |
| `/sos/<reference>` | Open any request from the queue: triage score and reasons, timeline, assigned team, linked wearable. |
| `/wearables` | Every registered device with its last vitals and the ML health state. Click a device for live charts (heart rate, SpO2, motion, EDA) and the fusion state history. |
| `/rov` | The ROV fleet: status, battery, link (`simulated`, `online`, `offline`), and the Deploy, Recall, Stop and Bridge key actions. |
| `/missions` | Units on a mission: map track, telemetry, manual control takeover, and the camera panel when a vision worker is streaming. |
| `/weather` | Current conditions, the 48-hour forecast with uncertainty bands, hazard flags, and the model card (skill against persistence per horizon). |
| `/analytics` | Reports computed from the database and live ingest: SOS created vs resolved, breakdowns by type and source, response time by priority, telemetry ingest rate, alerts and state changes. |
| `/admin` | Admin only: users, device registration and key rotation, and the **SMS intake test** panel. |

The public side needs no login: `/` (landing page), `/sos` (request-help form) and
`/track/<reference>` (status page the requester receives).

## 7. Live demo: simulator, vision worker, ROV mission

Use three terminals, each with the virtual environment activated and the working directory at the
repository root.

### 7.1 Terminal 1: the server

```bash
python app.py
```

### 7.2 Terminal 2: the replay simulator

```bash
python -m src.backend.app.tools.simulate --with-sos
```

The simulator:

1. Logs in as `admin` / `trident-demo-2026` (change with `--user` and `--password`).
2. Registers four virtual wearables (`W-DALIA-01`, `W-DALIA-02`, `W-WESAD-01`, `W-FALL-01`), or
   rotates their keys if they already exist.
3. With `--with-sos`, files three public SOS requests and links two of them to wearables.
4. Streams real recorded sessions as schema-2 telemetry frames through `/api/v1/telemetry`, the
   same path as hardware: PPG-DaLiA daily life, a WESAD session through its stress phase, and a
   recorded fall followed by lying still. Each session loops as a new boot when it ends.

| Option | Default | Meaning |
|---|---|---|
| `--api` | `http://localhost:8000` | Server base URL |
| `--user`, `--password` | `admin`, `trident-demo-2026` | Admin account used to register devices |
| `--speed` | `1.0` | Replay speed; `1` is real time (one frame per 1.5 s per device) |
| `--batch` | `2` | Frames per request |
| `--with-sos` | off | Also file public SOS requests linked to the devices |

To reach the fall and stress events sooner, speed it up:

```bash
python -m src.backend.app.tools.simulate --with-sos --speed 4
```

Watch `/wearables` and `/ops`. The fall device (`W-FALL-01`) produces a fall alert after the
recorded fall and an escalation while the wearer lies still.

The simulator needs local data files that are not in git; see [section 11](#11-data-and-model-files).
Press `Ctrl+C` to stop it.

### 7.3 Terminal 3: the vision worker (demo source)

The vision worker needs `opencv-contrib-python` and `ultralytics` (both in `requirements.txt`).
It authenticates with a per-ROV **vision key**. There is no button for this key in the console;
issue it through the API as an admin. ROV ids are integers; on a fresh database `ROV-001` is `1`
(check with `GET /api/v1/rov`).

PowerShell:

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -ContentType 'application/json' -Body '{"username":"admin","password":"trident-demo-2026"}'
$key = (Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/rov/1/vision-key -Headers @{ Authorization = "Bearer $($login.access_token)" }).api_key
$key
```

Bash (Linux, macOS, Git Bash):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"trident-demo-2026"}' | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
KEY=$(curl -s -X POST http://localhost:8000/api/v1/rov/1/vision-key -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys, json; print(json.load(sys.stdin)['api_key'])")
echo "$KEY"
```

You can also do this from http://localhost:8000/api/docs: **Authorize** with the token, then call
`POST /api/v1/rov/{unit_id}/vision-key`. The key is shown only once; issuing a new one replaces it.

Start the worker with the demo source (a slow pan across sample photos and enrolled faces, no
camera needed):

```powershell
python -m src.cv.vision --key $key --source demo
```

```bash
python -m src.cv.vision --key "$KEY" --source demo
```

| Option | Default | Meaning |
|---|---|---|
| `--api` | `http://localhost:8000` | Server base URL |
| `--key` | required | ROV vision key |
| `--source` | `0` | Webcam index (`0`, `1`, ...), a camera URL (MJPEG/RTSP, e.g. `http://192.168.4.1:81/stream`), a video file path, or `demo` |
| `--fps` | `4.0` | Frames processed per second (CPU budget) |
| `--focal-px` | `700.0` | Camera focal length in pixels at 640 px width, used for distance estimates |

### 7.4 Deploy a ROV to see the camera panel

1. Open `/rov`. `ROV-001` should show the camera thumbnail with person and face counts once
   frames arrive.
2. Press **Deploy** on `ROV-001` and enter the reference of one of the simulator's SOS requests
   (copy it from `/ops`). The unit must be idle with at least 30 % battery, and the request must
   have a location.
3. Open `/missions`. The mission panel shows the simulated track, telemetry and the annotated
   camera stream with detections and distances.

Without a serial bridge the ROV is **simulated**: the 1 Hz scheduler tick moves it toward the
target. Issuing a bridge key turns the unit into a real one (see [9.2](#92-rov-serial-bridge)), and its link then
shows `offline` until a bridge connects.

### 7.5 SMS intake without a gateway

On `/admin`, the **SMS intake test** panel runs a message through the same parser the SMS gateway
uses, without a gateway or provider. Use the compact format
`SOS <lat>,<lng> P<people> I<injured> T<type> <note>` (at most 160 characters), for example
`SOS 13.0418,80.2341 P3 I1 Tflood water at first floor`. A request with `source: sms` appears in
the queue.

The real webhook, `POST /api/v1/sms/inbound`, stays disabled (HTTP 503) until
`TRIDENT_SMS_SECRET` is set; the gateway must then send that value in the `X-SMS-Secret` header.

## 8. Run the tests

```bash
python -m pytest tests
```

There are 128 tests (49 backend, 79 ML): `tests/backend` (API, auth, SOS, telemetry, ROV, vision, resilience) and
`tests/ml` (wearable features, emulator, fusion, runtime, weather, vision pipeline). Each backend
test module uses a fresh temporary SQLite database, so the tests never touch
`data/databases/trident.db`. The weather tests run without network access.

| Command | Runs |
|---|---|
| `python -m pytest tests/backend` | Backend only |
| `python -m pytest tests/ml` | ML only |
| `python -m pytest tests -q -x` | Everything, quiet, stop at the first failure |

Some ML tests need the full `requirements.txt` environment (training packages, OpenCV contrib,
ultralytics) and local data files.

## 9. Connect real hardware

### 9.1 Wearable (ESP32)

Full wiring, bill of materials and protocol: [src/firmware/README.md](../src/firmware/README.md).

1. **Register the device.** On `/admin`, under Devices, press **Register device**. Use the device
   id the firmware sends: `DEVICE_ID` in `src/firmware/include/config.h` (default
   `TRIDENT-WEAR-01`). The console shows the device key **once**; copy it. The API equivalent is
   `POST /api/v1/devices` with `{"device_id": "...", "label": "..."}` (admin).
2. **Create the secrets file.** Copy the template:

   ```powershell
   Copy-Item src\firmware\include\secrets.example.h src\firmware\include\secrets.h
   ```

   ```bash
   cp src/firmware/include/secrets.example.h src/firmware/include/secrets.h
   ```

   `secrets.h` is gitignored. Edit it and set the values described in `secrets.example.h`:

   | Define | Value |
   |---|---|
   | `WIFI_SSID`, `WIFI_PASSWORD` | Your Wi-Fi network (2.4 GHz; the ESP32 has no 5 GHz radio) |
   | `TELEMETRY_URL` | Full endpoint: `http://<server-ip>:8000/api/v1/telemetry` for a LAN server, or `https://<your-domain>/api/v1/telemetry` |
   | `DEVICE_KEY` | The key from step 1 |

   The build fails if `DEVICE_KEY` is missing, and the boot log warns if it is still `CHANGE_ME`
   or the URL has the wrong path. Never commit `secrets.h` or paste its contents into issues or
   logs.
3. **Let the device reach the server.** `python app.py` binds to `127.0.0.1`, which other machines
   cannot reach. For a device on your LAN, bind to all interfaces and allow port 8000 through the
   firewall:

   ```powershell
   $env:HOST = '0.0.0.0'; python app.py
   ```

   ```bash
   HOST=0.0.0.0 python app.py
   ```

4. **Build and flash.** PlatformIO is installed by `requirements.txt` (`pip install platformio`
   otherwise):

   ```bash
   cd src/firmware
   python -m platformio run
   python -m platformio run -t upload
   python -m platformio device monitor
   ```

   The monitor runs at 115200 baud. If upload cannot find the board, pass the port:
   `python -m platformio run -t upload --upload-port COM4` (Windows) or
   `--upload-port /dev/ttyUSB0` (Linux).
5. **Check it.** The device appears online on `/wearables` within a few seconds. A device that has
   not posted for 30 s is marked offline.

If a key leaks, or the flash was erased (`pio run -t erase` resets the device's sequence counters),
use **Rotate key** on `/admin` and re-flash with the new key.

### 9.2 ROV serial bridge

The bridge runs on the station laptop that has the ROV's USB serial cable. Every second it reads
`Temperature:`, `Depth:`, `Heading:` and `Battery:` lines from the serial port, posts them to the
API, and writes queued commands back (`forward_75`, `up_0`, `on`, `off`). If the server is
unreachable for 5 s it sends a thruster stop on its own. Operating it is covered in [USER_GUIDE.md](USER_GUIDE.md) §10.

1. On `/rov`, press **Bridge key** on the unit (admin). Optionally enter the camera's video URL.
   Copy the key; it is shown once. The API equivalent is `POST /api/v1/rov/{id}/bridge-key`.
   From now on the unit is no longer simulated.
2. On the station laptop (needs `pyserial` and `httpx`):

   ```bash
   python -m src.rov.bridge --port COM5 --key <bridge key>
   ```

   Use `--port /dev/ttyUSB0` (or `/dev/ttyACM0`) on Linux and `/dev/tty.usbserial-*` on macOS.
   Other options: `--api` (default `http://localhost:8000`) and `--baud` (default `9600`).

### 9.3 ROV camera

Run the vision worker against the real camera with the unit's vision key
([section 7.3](#73-terminal-3-the-vision-worker-demo-source)):

```bash
python -m src.cv.vision --key <vision key> --source http://192.168.4.1:81/stream
```

`--source 0` uses the laptop's first webcam; a video file path also works. The worker usually
runs on the station laptop next to the ROV.

## 10. Configuration

The server reads `TRIDENT_*` environment variables once at start-up. It also reads an optional
`.env` file in the repository root (`KEY=value` lines; `#` comments; surrounding quotes are
stripped). Variables already set in the environment take precedence over `.env`.

Example `.env` for local development:

```dotenv
TRIDENT_ENV=development
TRIDENT_SMS_SECRET=local-test-secret
TRIDENT_SMS_NUMBER=+91 90000 00000
```

### 10.1 Server variables

| Variable | Default | Meaning |
|---|---|---|
| `TRIDENT_ENV` | `development` | `development`, `test` or `production`. Production requires `TRIDENT_JWT_SECRET`, switches to JSON logs, never seeds demo users, hides `/api/docs`, trims `/readyz` details and turns off auto-reload in `app.py`. |
| `TRIDENT_DATABASE_URL` | `sqlite:///<repo>/data/databases/trident.db` | SQLAlchemy URL. For PostgreSQL use `postgresql+psycopg://user:password@host:5432/dbname`. |
| `TRIDENT_JWT_SECRET` | random per process outside production | HS256 signing key for access tokens. Outside production a random key is generated at each start, so logins do not survive a restart. Required in production. |
| `TRIDENT_ACCESS_TTL_S` | `900` (15 min) | Access token lifetime in seconds. |
| `TRIDENT_REFRESH_TTL_S` | `604800` (7 days) | Refresh token lifetime in seconds. |
| `TRIDENT_ADMIN_PASSWORD` | empty | If set and no `admin` user exists, creates `admin` with this password at start-up. |
| `TRIDENT_SEED_DEMO_USERS` | `true` (`false` in production) | Create the four demo accounts. Ignored in production: demo users are never seeded there. |
| `TRIDENT_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed to call the API and open `/ws` from another origin. The console served by the API itself is same-origin and needs no entry. |
| `TRIDENT_RUN_SCHEDULER` | `true` | Run background jobs in this process: device liveness, auto-triage, alert escalation, ROV simulation tick, weather and river refresh, retention. With `false`, simulated ROVs do not move and alerts do not escalate. |
| `TRIDENT_ML_ENABLED` | `true` | Load the wearable models. With `false`, telemetry is stored without ML health states. |
| `TRIDENT_WEATHER_ENABLED` | `true` | Load the weather model and fetch observations. With `false`, the weather page has no data. |
| `TRIDENT_SOS_RATE_PER_MIN` | `20` | Public SOS submissions per client IP per minute. |
| `TRIDENT_SOS_BURST` | `10` | SOS token-bucket burst size (the effective burst is at least the per-minute rate, capped at 1000). |
| `TRIDENT_LOGIN_RATE_PER_MIN` | `10` | Login attempts per client IP per minute (burst at least 5). |
| `TRIDENT_SMS_SECRET` | empty | Shared secret for `POST /api/v1/sms/inbound` (header `X-SMS-Secret`). Empty disables the webhook. The admin SMS test works either way. |
| `TRIDENT_SMS_NUMBER` | empty | Control-room number shown on the public site for SMS SOS. |
| `TRIDENT_PUBLIC_URL` | `http://localhost:8000` | Public base URL used in tracking links sent back to SMS requesters. |
| `TRIDENT_EXPOSE_DOCS` | unset | `true` or `1` serves `/api/docs` and `/api/openapi.json` in production too. Outside production they are always served. |
| `HOST` | `127.0.0.1` | Bind address for `python app.py` only. |
| `PORT` | `8000` | Port for `python app.py` and the Docker image. |

Fixed in code (not configurable through the environment): devices go offline after 30 s without
telemetry, unacknowledged alerts escalate after 120 s, and auto-dispatch handles priorities 1 and 2.

### 10.2 Other variables

| Variable | Used by | Meaning |
|---|---|---|
| `TRIDENT_DATA_ROOT` | wearable ML and the simulator | Relocates the `data/` tree (default `<repo>/data`). |
| `TRIDENT_WEATHER_CONFIG` | weather model | Path to an alternative `weather.yaml` (default `src/ml/weather/config/weather.yaml`). |
| `TRIDENT_API` | `npm run dev` | API the Vite dev server proxies to (default `http://localhost:8000`). |
| `VITE_MAP_TILE_URL` | web console build | Leaflet tile URL template. Unset: Stadia Maps `alidade_smooth_dark` (keyless on localhost; a deployed domain must be registered with Stadia), with OpenStreetMap as automatic fallback. |
| `VITE_MAP_TILE_ATTRIBUTION` | web console build | Attribution text for a custom tile source. |
| `VITE_MAP_TILE_DARKEN` | web console build | `1` applies the dark CSS filter to a light custom tile source. |

`VITE_*` variables are read at build time. Set them before `npm run build` (for example in
`src/frontend/web/.env.local`), then rebuild.

## 11. Data and model files

| Path | In git | Needed by | If it is missing |
|---|---|---|---|
| `models/wearable/` (`registry.json` and one folder per head: `activity`, `fall`, `hr_trust`, `rhythm`, `stress`) | yes | API server (wearable ML) | Telemetry is still stored, but without ML health states. `/readyz` reports `wearable_ml.ok: false`. |
| `models/weather/` (`registry.json`, `1.0.0/`) | yes | API server (weather) | The weather page is empty. `/readyz` reports `weather.ok: false`. |
| `data/processed/wearable/frames/ppg_dalia.parquet`, `wesad.parquet`, `hifd.parquet` | no | Replay simulator | The simulator stops with a file-not-found error. |
| `data/raw/weather/` (Open-Meteo archive cache, `chennai_historical.csv`) | no | Weather offline fallback, weather training | Serving uses the live Open-Meteo API; without network and without these files there is no forecast. |
| `data/databases/trident.db` | no | API server (SQLite) | Created on first start. |

The simulator's frame tables are generated from the public datasets by the wearable pipeline:

```bash
python -m src.ml.wearable.pipeline compact ppg_dalia wesad hifd
python -m src.ml.wearable.pipeline frames ppg_dalia wesad hifd
```

This needs the downloaded dataset archives under `data/raw/wearable_ml_datasets/` and the full
`requirements.txt` environment. Where to get the datasets and how the pipeline works:
[TRAINING_GUIDE.md](TRAINING_GUIDE.md). If someone on the team already has the files, copying the
three `.parquet` files into `data/processed/wearable/frames/` is enough for the simulator.

## 12. Troubleshooting

Start with the readiness endpoint; it reports each dependency separately:

```bash
curl http://localhost:8000/readyz
```

```powershell
Invoke-RestMethod http://localhost:8000/readyz | ConvertTo-Json -Depth 5
```

Only the database is required for `ready: true`; the ML and weather checks report degraded
features.

| Symptom | Cause | Fix |
|---|---|---|
| `[Errno 10048]` / `address already in use` on start | Something else (often an earlier server) holds port 8000. | Find it: `Get-NetTCPConnection -LocalPort 8000` (PowerShell) or `lsof -i :8000` (Linux/macOS), then stop that process. Or use another port: `$env:PORT=8001; python app.py` / `PORT=8001 python app.py` (then pass `--api http://localhost:8001` to the simulator and set `TRIDENT_API` for `npm run dev`). |
| Log line `web UI not built (...index.html missing)`, and `/` returns 404 | The console has not been built. | Run `npm ci` and `npm run build` in `src/frontend/web`, then restart the server. |
| Console loads but looks stale after a frontend change | Old build, or the service worker cached the old shell. | Rebuild, then hard-reload (Ctrl+Shift+R). If needed, unregister the service worker in DevTools, Application. |
| `/readyz` shows `wearable_ml.ok: false`, wearables show no health state | `models/wearable/` missing or incomplete, `onnxruntime` not installed, or `TRIDENT_ML_ENABLED=false`. | Check the `error` field in `/readyz`, restore `models/wearable/` from git, `pip install -r requirements-prod.txt`. |
| `/readyz` shows `weather.ok: false`, or the weather page is empty | No internet access to `api.open-meteo.com` and no local cache under `data/raw/weather/`, `lightgbm` missing, or `TRIDENT_WEATHER_ENABLED=false`. | Check network and the `error` field. The forecast refreshes every 30 minutes on its own. Recreate the cache with `python -m src.ml.weather.data`. |
| `/readyz` shows `database` with `database is locked or read-only` | Another process holds the SQLite write lock: a second server on the same file, a database browser with an open write transaction, or the file is on a network or synced drive. | Run one server per database file. Close database tools. Keep `data/databases/` on a local disk. |
| `AttributeError: module 'cv2' has no attribute 'face'` | The vision worker needs the OpenCV **contrib** build, but `opencv-python` (or `opencv-python-headless`) is installed and shadows it. | `pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python` then `pip install "opencv-contrib-python>=4.11"`. |
| Simulator: `FileNotFoundError ... frames/ppg_dalia.parquet` | The frame tables are not present locally. | See [section 11](#11-data-and-model-files). |
| Simulator: HTTP 401 on login | Demo users are not seeded (production mode, or `TRIDENT_SEED_DEMO_USERS=false`), or the password differs. | Pass `--user` and `--password` for an existing admin. |
| Logged out after every server restart | Outside production the JWT secret is random per process. | Expected. Set `TRIDENT_JWT_SECRET` in `.env` to keep sessions across restarts. |
| HTTP 429 with `Retry-After` | Per-IP rate limit on SOS, login, tracking or SMS. | Wait, or raise `TRIDENT_SOS_RATE_PER_MIN` / `TRIDENT_LOGIN_RATE_PER_MIN` for local testing. |
| Wearable never appears online | Wrong `TELEMETRY_URL`, server bound to `127.0.0.1`, firewall, or wrong key. | Read the serial monitor: HTTP 401 means the key; a connection error means the URL, bind address or firewall. |
| ROV **Deploy** button disabled | The unit's link is `offline`: a bridge key was issued but no bridge is connected. | Start the bridge, or for a demo use the other, still simulated, unit. |
| `npm ci` fails | Wrong Node version or a missing `package-lock.json`. | Use Node 22. |
