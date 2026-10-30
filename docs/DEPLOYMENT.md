# Deploying TRIDENT

This guide covers running TRIDENT in production: the security checklist, a reference single-VM
setup with Docker Compose, PostgreSQL, backups, upgrades, monitoring, the limits of the current
single-node design, and security notes.

For a local development setup, see [GETTING_STARTED.md](GETTING_STARTED.md). The hosting plan
this guide implements is described in [RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md)
section 6.1. The API design is in [PLATFORM_DESIGN.md](PLATFORM_DESIGN.md) and
[src/backend/README.md](../src/backend/README.md).

## Contents

1. [Production checklist](#1-production-checklist)
2. [The container image](#2-the-container-image)
3. [Reference setup: one VM with Docker Compose](#3-reference-setup-one-vm-with-docker-compose)
4. [PostgreSQL and migrations](#4-postgresql-and-migrations)
5. [Backups and restore](#5-backups-and-restore)
6. [Upgrades](#6-upgrades)
7. [Health and monitoring](#7-health-and-monitoring)
8. [Scaling limits of the single-node design](#8-scaling-limits-of-the-single-node-design)
9. [Security notes](#9-security-notes)

## 1. Production checklist

Go through every row before the first public start.

| # | Item | How | Why |
|---|---|---|---|
| 1 | Production mode | `TRIDENT_ENV=production` (already set in the Docker image) | JSON logs, no demo users, no API docs, minimal `/readyz` output, and the server refuses to start without a JWT secret. |
| 2 | JWT secret | `TRIDENT_JWT_SECRET` = a long random value, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"` | Signs access tokens. Changing it logs everyone out. Keep it stable across restarts. |
| 3 | First admin | `TRIDENT_ADMIN_PASSWORD` = a strong password | Creates the `admin` account on start if it does not exist. Change the password after first login, then you may remove the variable (it is only used when `admin` is missing). |
| 4 | Demo users off | Nothing to do in production: the four demo accounts (password `trident-demo-2026`) are never seeded when `TRIDENT_ENV=production`. If you migrate a development database, delete or disable `admin`, `dispatcher`, `responder` and `viewer` demo accounts, or change their passwords. | The demo password is public. |
| 5 | Database | `TRIDENT_DATABASE_URL=postgresql+psycopg://...` | SQLite works for a single small node, but PostgreSQL is the production target ([section 4](#4-postgresql-and-migrations)). |
| 6 | HTTPS reverse proxy | Caddy, Nginx or a cloud load balancer in front of the API. It must **overwrite** (not append to) `X-Forwarded-For` with the real client address. Run uvicorn with `--proxy-headers` (the image does) and trust only the proxy (`FORWARDED_ALLOW_IPS`). | Rate limits are per client IP. If clients can set `X-Forwarded-For` themselves, they can bypass the SOS and login limits. Tokens and device keys must never cross the network in clear text. |
| 7 | Do not expose the API port directly | Publish only the proxy's ports 80/443. | Anything that reaches uvicorn without the proxy can spoof its client address when `FORWARDED_ALLOW_IPS` is broad. |
| 8 | CORS origins | `TRIDENT_CORS_ORIGINS=https://your.domain` (comma-separated if several) | The default lists the Vite dev server on localhost; remove it. The console served by the API is same-origin. The list also gates which cross-origin pages may open `/ws`. |
| 9 | Public URL | `TRIDENT_PUBLIC_URL=https://your.domain` | Used in tracking links sent to SMS requesters. |
| 10 | SMS webhook | `TRIDENT_SMS_SECRET` = a long random value; `TRIDENT_SMS_NUMBER` = the control-room number shown on the public site | Without the secret, `POST /api/v1/sms/inbound` returns 503. The gateway must send the secret in the `X-SMS-Secret` header. |
| 11 | API docs off | Leave `TRIDENT_EXPOSE_DOCS` unset | Production hides `/api/docs` and `/api/openapi.json` unless it is `true`. |
| 12 | `/metrics` not public | Block `/metrics` at the proxy (the Caddyfile below does) or allow it only from your monitoring host. | It is unauthenticated and reveals route names and traffic volume. |
| 13 | Map tiles | Register the domain with Stadia Maps, or build the console with your own `VITE_MAP_TILE_URL` | Stadia's keyless tiles work on localhost only; other domains must be registered. |
| 14 | Secrets storage | An `.env` file readable only by the deploy user (`chmod 600`), or your host's secret store | Never commit it. |
| 15 | Backups | Nightly `pg_dump` off the machine ([section 5](#5-backups-and-restore)) | |
| 16 | Single worker | Run one uvicorn worker process per database ([section 8](#8-scaling-limits-of-the-single-node-design)) | Live state is held in process memory. |

## 2. The container image

The repository `Dockerfile` builds one image that serves both the API and the web console:

| Stage | Base | What it does |
|---|---|---|
| `web` | `node:22-slim` | `npm ci` and `npm run build` in `src/frontend/web` |
| runtime | `python:3.12-slim` | Installs `requirements-prod.txt` only (no torch, no training stack). Copies `app.py`, `src/backend`, `src/ml`, `models/` and the built console. Runs as the unprivileged user `trident`. |

Image details that matter when you deploy:

- `TRIDENT_ENV=production` is set in the image.
- Command: `uvicorn src.backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers`.
  One worker process.
- `HEALTHCHECK` polls `http://127.0.0.1:8000/healthz` every 30 s. It assumes port 8000, so keep
  `PORT` at its default inside the container.
- `models/` is baked into the image, so the wearable and weather models ship with the code.
- Not in the image (excluded by `.dockerignore` or not copied): `data/raw`, `data/interim`,
  `data/processed`, local databases, logs, `mlruns`, the vision worker, the ROV bridge and the
  firmware. Consequences:
  - The weather service needs outbound HTTPS to `api.open-meteo.com`; the offline fallback files
    under `data/raw/weather/` are not available in the container.
  - The replay simulator does not run inside the image. Run it from a development checkout
    against the deployed URL if you need a drill ([section 7.3](#73-drills)).
- The writable directory is `/code/data/databases`. It only matters if you keep SQLite; then
  mount a volume there.
- `.env` in the repository root is not copied into the image. Configure the container through
  its environment.

Build and run it on its own (useful for a quick check, with SQLite inside the container):

```bash
docker build -t trident-api .
docker run --rm -p 8000:8000 \
  -e TRIDENT_JWT_SECRET=change-me-to-a-long-random-value \
  -e TRIDENT_ADMIN_PASSWORD=change-me \
  -v trident-sqlite:/code/data/databases \
  trident-api
```

PowerShell (same command on one line):

```powershell
docker build -t trident-api .
docker run --rm -p 8000:8000 -e TRIDENT_JWT_SECRET=change-me-to-a-long-random-value -e TRIDENT_ADMIN_PASSWORD=change-me -v trident-sqlite:/code/data/databases trident-api
```

## 3. Reference setup: one VM with Docker Compose

This is the first-deployment shape from
[RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md) section 6.1: one always-on Linux VM
(about 2 vCPU and 4 GB RAM or more) running three containers.

| Service | Image | Role |
|---|---|---|
| `postgres` | `postgres:16` | Database, on a named volume |
| `api` | built from the repository `Dockerfile` | API and web console, reachable only inside the Compose network |
| `caddy` | `caddy:2` | Automatic HTTPS (Let's Encrypt), HSTS, reverse proxy, overwrites `X-Forwarded-For` |

The vision worker and the ROV bridge normally run on the station laptop next to the ROV, not on
the VM. They connect to `https://your.domain` like any client.

### 3.1 Prerequisites

- A Linux VM with Docker Engine and the Docker Compose plugin (`docker compose version`).
- A domain name with an `A` (and optionally `AAAA`) record pointing to the VM.
- Ports 80 and 443 (TCP) and 443 (UDP, for HTTP/3) open in the VM firewall and the cloud
  security group. Do not open 8000 or 5432.

### 3.2 Layout on the VM

Keep the deployment files outside the repository checkout so that `git pull` never touches them:

```
/opt/trident/
  trident/              git checkout of this repository
  deploy/
    docker-compose.yml
    Caddyfile
    .env                secrets, chmod 600
    backups/
```

```bash
sudo mkdir -p /opt/trident && sudo chown "$USER" /opt/trident
cd /opt/trident
git clone <repository-url> trident
mkdir -p deploy/backups
```

### 3.3 `deploy/.env`

Docker Compose reads this file for `${...}` substitution in `docker-compose.yml`.

```dotenv
# Domain served by Caddy
TRIDENT_DOMAIN=trident.example.org

# PostgreSQL
POSTGRES_DB=trident
POSTGRES_USER=trident
POSTGRES_PASSWORD=replace-with-a-long-random-password

# API
TRIDENT_JWT_SECRET=replace-with-output-of-secrets.token_urlsafe-48
TRIDENT_ADMIN_PASSWORD=replace-with-a-strong-initial-admin-password
TRIDENT_SMS_SECRET=replace-with-a-long-random-value
TRIDENT_SMS_NUMBER=
```

Generate random values with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`, or
`openssl rand -base64 48 | tr -d '/+=' | head -c 64`. Avoid `@`, `:`, `/` and `%` in
`POSTGRES_PASSWORD`, because it is embedded in a database URL. Then:

```bash
chmod 600 /opt/trident/deploy/.env
```

### 3.4 `deploy/docker-compose.yml`

```yaml
name: trident

services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 10

  api:
    build:
      context: ../trident
      dockerfile: Dockerfile
    image: trident-api:latest
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      TRIDENT_ENV: production
      TRIDENT_DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      TRIDENT_JWT_SECRET: ${TRIDENT_JWT_SECRET}
      TRIDENT_ADMIN_PASSWORD: ${TRIDENT_ADMIN_PASSWORD}
      TRIDENT_CORS_ORIGINS: https://${TRIDENT_DOMAIN}
      TRIDENT_PUBLIC_URL: https://${TRIDENT_DOMAIN}
      TRIDENT_SMS_SECRET: ${TRIDENT_SMS_SECRET}
      TRIDENT_SMS_NUMBER: ${TRIDENT_SMS_NUMBER}
      # uvicorn --proxy-headers only trusts X-Forwarded-For from these addresses (default 127.0.0.1).
      # Caddy reaches the API from another container, so trust the Compose network. This is safe
      # only because the API port is not published: Caddy is the only client that can reach it.
      FORWARDED_ALLOW_IPS: "*"
    expose:
      - "8000"
    # no "ports:" on purpose - the API is reachable only through Caddy

  caddy:
    image: caddy:2
    restart: unless-stopped
    depends_on:
      - api
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    environment:
      TRIDENT_DOMAIN: ${TRIDENT_DOMAIN}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  pgdata:
  caddy_data:
  caddy_config:
```

### 3.5 `deploy/Caddyfile`

```caddyfile
{$TRIDENT_DOMAIN} {
	encode zstd gzip

	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains"
	}

	# Prometheus-style metrics are unauthenticated: keep them off the public internet.
	# To scrape from a monitoring host, replace this with a "remote_ip" matcher for that host.
	@metrics path /metrics
	respond @metrics 404

	reverse_proxy api:8000 {
		# Without trusted_proxies, Caddy ignores any X-Forwarded-For sent by the client and sets it
		# to the real client address - the overwrite the API's rate limits rely on.
		# Flush immediately so the MJPEG camera stream and long responses are not buffered.
		flush_interval -1
	}
}
```

Caddy obtains and renews the TLS certificate automatically, redirects HTTP to HTTPS, and proxies
the WebSocket at `/ws` without extra configuration. It passes the original `Host` header to the
API, which the WebSocket origin check uses.

If you use Nginx instead, the equivalent essentials are
`proxy_set_header X-Forwarded-For $remote_addr;` (set, not `$proxy_add_x_forwarded_for`),
`proxy_set_header X-Forwarded-Proto $scheme;`, `proxy_set_header Host $host;`, the WebSocket
`Upgrade`/`Connection` headers on `/ws`, and `proxy_buffering off;` for
`/api/v1/rov/` camera streams.

### 3.6 Start it

```bash
cd /opt/trident/deploy
docker compose up -d --build
docker compose ps
docker compose logs -f api
```

On the first start the API applies all migrations to the empty PostgreSQL database, seeds teams,
ROVs and contacts, and creates `admin` from `TRIDENT_ADMIN_PASSWORD`. Then:

1. Check readiness: `curl https://trident.example.org/readyz` should return `"ready": true`.
2. Sign in at `https://trident.example.org/login` as `admin` and change the password.
3. Create staff accounts on `/admin`.
4. Register wearables and issue ROV bridge and vision keys
   ([GETTING_STARTED.md section 9](GETTING_STARTED.md#9-connect-real-hardware)). Set the firmware's
   `TELEMETRY_URL` to `https://trident.example.org/api/v1/telemetry`, and start the bridge and
   vision worker with `--api https://trident.example.org`.

## 4. PostgreSQL and migrations

- **Driver.** psycopg 3, installed by `requirements-prod.txt` as `psycopg[binary]`. The URL scheme
  must be `postgresql+psycopg://` (plain `postgresql://` would make SQLAlchemy look for psycopg2,
  which is not installed).
- **Version.** The reference setup uses PostgreSQL 16.
- **Migrations run on start-up.** Every API start runs `alembic upgrade head` (from
  `src/backend/app/migrate.py`, revisions in `src/backend/migrations/versions/`), then the
  idempotent seed. There is no separate migration step to remember.
- **Manual run.** With `TRIDENT_DATABASE_URL` set in the environment:

  ```bash
  python -m src.backend.app.migrate upgrade
  ```

  In the Compose setup: `docker compose run --rm api python -m src.backend.app.migrate upgrade`.
- **Review the SQL without touching a database.** There is no `alembic.ini` in the repository and
  `migrate.py` has no `--sql` flag, but the Alembic environment supports offline mode. This prints
  the full PostgreSQL DDL for the configured URL; it does not connect to the server:

  Bash:

  ```bash
  TRIDENT_DATABASE_URL="postgresql+psycopg://user:pass@localhost/trident" \
    python -c "from alembic import command; from src.backend.app.migrate import _config; command.upgrade(_config(), 'head', sql=True)" > schema.sql
  ```

  PowerShell:

  ```powershell
  $env:TRIDENT_DATABASE_URL = 'postgresql+psycopg://user:pass@localhost/trident'
  python -c "from alembic import command; from src.backend.app.migrate import _config; command.upgrade(_config(), 'head', sql=True)" > schema.sql
  Remove-Item Env:TRIDENT_DATABASE_URL
  ```

  To render only the step between two revisions, replace `'head'` with `'<from>:<to>'`.
- **Moving from SQLite.** There is no built-in data copy tool. For a fresh deployment, start on
  PostgreSQL from day one. Development SQLite databases contain demo users and simulator data and
  should not be carried into production.

## 5. Backups and restore

Back up the database. Nothing else on the VM holds state that cannot be rebuilt: the image comes
from the repository, and Caddy's certificates are re-issued automatically.

### 5.1 PostgreSQL

Nightly dump in PostgreSQL's custom format, kept for 14 days:

```bash
cd /opt/trident/deploy
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "backups/trident-$(date +%Y%m%d-%H%M).dump"
find backups -name 'trident-*.dump' -mtime +14 -delete
```

Schedule it with cron (`crontab -e`):

```
15 2 * * * cd /opt/trident/deploy && docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/trident-$(date +\%Y\%m\%d-\%H\%M).dump" && find backups -name 'trident-*.dump' -mtime +14 -delete
```

Copy `backups/` off the machine (object storage such as Backblaze B2 or Oracle Object Storage,
with `rclone` or the provider's CLI). A backup that only exists on the same VM is not a backup.

Restore (stops the API so nothing writes during the restore):

```bash
cd /opt/trident/deploy
docker compose stop api
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
  < backups/trident-YYYYMMDD-HHMM.dump
docker compose start api
```

If the dump is from an older release, the API's start-up migration brings the schema up to date.
Test the restore regularly (for example monthly) on a scratch VM or a second Compose project.

### 5.2 SQLite (small single-node installs)

SQLite runs in WAL mode, so do not copy `trident.db` alone while the server is running (the
`-wal` file holds recent writes). Use SQLite's online backup instead:

```bash
python -c "import sqlite3; s = sqlite3.connect('data/databases/trident.db'); d = sqlite3.connect('trident-backup.db'); s.backup(d); d.close(); s.close()"
```

To restore, stop the server, delete `trident.db`, `trident.db-wal` and `trident.db-shm`, copy the
backup to `data/databases/trident.db`, and start the server.

## 6. Upgrades

1. Read the changes since the deployed version, especially new files in
   `src/backend/migrations/versions/`.
2. Take a backup ([section 5](#5-backups-and-restore)).
3. Optional: render the migration SQL for review ([section 4](#4-postgresql-and-migrations)).
4. Pull, rebuild and restart:

   ```bash
   cd /opt/trident/trident && git pull
   cd /opt/trident/deploy
   docker compose build api
   docker compose up -d api
   docker compose logs -f api
   ```

   The new container applies pending migrations before it serves requests.
5. Check `/readyz` and sign in.

Notes:

- There is a short outage while the single API container restarts. WebSocket clients reconnect on
  their own, wearables queue frames (up to 320 frames, about 8 minutes) and resend them, and the
  public SOS form keeps unsent requests in an outbox and retries.
- Restarting resets in-memory state: wearable fusion calibration and state timers, rate-limit
  buckets, the weather cache (re-fetched at start) and the last camera frames.
- **Rollback.** Migrations are forward-only in normal operation. To roll back a release that
  changed the schema, restore the backup taken in step 2 and deploy the previous commit.
- Keep `TRIDENT_JWT_SECRET` unchanged across upgrades, or every user is signed out.

## 7. Health and monitoring

### 7.1 Endpoints

| Endpoint | Auth | Returns | Use for |
|---|---|---|---|
| `GET /healthz` | none | `{"status": "ok", "version": "..."}`, always 200 while the process serves requests | Liveness. The image's `HEALTHCHECK` uses it. |
| `GET /readyz` | none | `{"ready": bool, "checks": {...}}`; 200 when ready, 503 when not | Readiness and load-balancer checks. |
| `GET /metrics` | none (block it at the proxy) | Prometheus text format | Scraping. |

`/readyz` checks:

| Check | Meaning | Affects `ready` |
|---|---|---|
| `database` | `SELECT 1` succeeds **and** a write probe succeeds. On SQLite the probe takes the write lock with `BEGIN IMMEDIATE` (0.5 s timeout) and rolls back; on PostgreSQL it checks that the session is not read-only (`SHOW transaction_read_only`). A database that answers reads but refuses writes reports `ok: false`. | yes |
| `wearable_ml` | Wearable models loaded | no (telemetry still stored) |
| `weather` | A forecast is available | no |
| `jobs` | Scheduler job leases | no |

In production, `/readyz` returns only the `ok` flag per check, without error text, hostnames or
PIDs. Outside production it includes details such as loaded model heads and the last error.

### 7.2 Metrics and logs

- `/metrics` exposes `http_requests_total` (by method, route and status) and
  `http_request_seconds` histograms (by route), plus counters recorded by the services.
- In production, logs are JSON lines on stdout with a `request_id`. The same id is returned in
  the `X-Request-ID` response header and shown in console error toasts, so a user report can be
  matched to a log line. Read them with `docker compose logs api`.
- Suggested alerts: `/readyz` not 200 for more than 1 minute; 5xx rate; no telemetry frames for
  longer than expected during an operation; backup job failures; certificate renewal failures in
  the Caddy logs.

### 7.3 Drills

Run the replay simulator from a development checkout against the deployed server to exercise the
whole path (needs an admin account and the simulator's local data files; see
[GETTING_STARTED.md section 11](GETTING_STARTED.md#11-data-and-model-files)):

```bash
python -m src.backend.app.tools.simulate --api https://trident.example.org --user <admin user> --password <password> --with-sos
```

Do this on a staging deployment, or delete the drill's SOS requests and virtual devices
(`W-DALIA-01`, `W-DALIA-02`, `W-WESAD-01`, `W-FALL-01`) afterwards.

## 8. Scaling limits of the single-node design

The API is designed to run as **one process**. The database is shared and transactional, but
several kinds of live state are held in that process's memory:

| In-memory state | Effect of running a second process or replica |
|---|---|
| Per-device fusion runtimes (feature buffers, calibration, state timers) | Frames for one device split across processes give each a partial view; health states and alerts become wrong. A restart also loses calibration. |
| WebSocket hub | Clients connected to one process do not see events published by another. |
| Rate-limit buckets | Each process limits independently, so the effective limit multiplies. |
| Weather cache | Each process fetches and caches its own forecast. |
| Vision latest-frame relay | Camera frames posted to one process cannot be streamed from another. |

What is already safe across processes: idempotency keys, refresh tokens, and scheduler jobs
(database leases make each job run on exactly one process).

Practical consequences:

- Do not add `--workers N` to uvicorn and do not run more than one `api` replica against the same
  database.
- Scale vertically first. One small VM handles a city-scale drill; ML inference is ONNX/LightGBM
  on CPU.
- Keep the vision worker off the VM (on the station laptop) so frame processing does not compete
  with the API.

The plan for horizontal scaling (Redis pub/sub for the hub, device affinity for fusion runtimes,
Redis rate limits, a separate vision relay) is in
[RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md) section 6.2.

## 9. Security notes

### 9.1 Keys for devices, bridges and cameras

| Key | Issued by (admin only) | Sent as | Used by |
|---|---|---|---|
| Device key | `/admin` Register device / Rotate key (`POST /api/v1/devices`, `POST /api/v1/devices/{id}/rotate-key`) | `X-Device-Key` header | Wearable firmware, simulator |
| Bridge key | `/rov` Bridge key (`POST /api/v1/rov/{id}/bridge-key`) | `X-ROV-Key` header | `src/rov/bridge.py` |
| Vision key | `POST /api/v1/rov/{id}/vision-key` (API only, no console button) | `X-ROV-Vision-Key` header | `src/cv/vision` |

- All three are random `tdk_...` tokens. The server stores only a hash and shows the key once.
- Issuing a new key replaces the old one immediately. That is also how you rotate: issue a new
  key, update the device or station laptop, and the old key stops working.
- Rotate a key when a device or laptop is lost, when someone who had the key leaves, and after a
  wearable's flash was erased.
- Every key issue is written to the audit log.
- Issuing a bridge key switches that ROV from simulated to real. Do not issue one for a unit that
  should stay simulated.
- Put device keys only in `src/firmware/include/secrets.h` (gitignored). Use
  `secrets.example.h` as the template; never commit real credentials or paste them into tickets.
- Wearables, bridges and vision workers must use `https://` URLs in production so keys are not
  sent in clear text.

### 9.2 Staff authentication

- Access tokens are short-lived JWTs (`TRIDENT_ACCESS_TTL_S`, 15 minutes by default). Refresh
  tokens rotate on every use (`TRIDENT_REFRESH_TTL_S`, 7 days); reusing an old refresh token
  revokes the whole login.
- The user's role and active flag are re-read from the database on every request and on open
  WebSocket connections, so disabling a user or changing a role takes effect at once.
- Passwords are hashed with bcrypt.

### 9.3 Rate limits

Per client IP, in process memory:

| Endpoint group | Limit |
|---|---|
| Public SOS submission | `TRIDENT_SOS_RATE_PER_MIN` (20/min), burst `TRIDENT_SOS_BURST` (10) or the rate, whichever is larger |
| Login | `TRIDENT_LOGIN_RATE_PER_MIN` (10/min), burst at least 5 |
| Public tracking page | 60/min |
| SMS webhook | 120/min, burst 30 (checked before the secret, so guessing is limited too) |

Rejected requests get HTTP 429 with a `Retry-After` header. Shelters and mobile carriers (CGNAT)
can put many people behind one IP; raise the SOS limit if that is expected. These limits are only
meaningful when the reverse proxy overwrites `X-Forwarded-For` ([section 1](#1-production-checklist), item 6).

### 9.4 Logs

- uvicorn logs WebSocket and stream URLs verbatim; a log filter replaces the values of `token=`
  and `ticket=` query parameters with `***` in every log record.
- Device and bridge keys travel in headers, which are not logged.
- Logs still contain request paths, SOS reference ids and usernames. Treat them as personal data
  under your retention policy.

### 9.5 Other

- The API sets a Content Security Policy and other security headers, and validates inputs
  strictly.
- Every write is recorded in the audit log with the actor and request id.
- Camera feeds are served through single-use tickets (`POST /api/v1/rov/{id}/vision/ticket`), not
  long-lived URLs.
- Planned hardening (MFA, refresh token in an HttpOnly cookie, certificate pinning in the
  firmware, encryption at rest, WAF) is listed in
  [RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md) section 11.
