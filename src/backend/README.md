# TRIDENT command-center API

FastAPI service behind the TRIDENT web console. It handles:
- public SOS intake and dispatch
- wearable telemetry, run through the Tier-1 ML heads and Tier-2 fusion
- alerts
- ROV missions and their controls
- weather forecasts
- analytics on live data

The design, contract and principles are in [docs/PLATFORM_DESIGN.md](../../docs/PLATFORM_DESIGN.md).

## Run

```bash
pip install -r requirements-prod.txt                    # or requirements.txt for training too
(cd src/frontend/web && npm ci && npm run build)        # web console -> served at /
python app.py                                           # http://localhost:8000, API docs at /api/docs
python -m src.backend.app.tools.simulate --with-sos     # optional: virtual wearables streaming real recordings
```

**First start**
- Alembic migrations are applied automatically, and reference data (teams, ROVs, contacts) is seeded.
- Outside production, demo staff accounts are created: `admin`, `dispatcher`, `responder` and `viewer`. They share the password `trident-demo-2026` and must never be used in production.
- In production, set `TRIDENT_ADMIN_PASSWORD` to create the first admin.

**Other entry points**
- Tests: `python -m pytest tests/backend`. Each module uses a fresh temporary SQLite database.
- Real ROV: `python -m src.rov.bridge --port COM5 --key <bridge key>`. Get the key from `POST /api/v1/rov/{id}/bridge-key`.

## Configuration (environment variables or `.env`)

| Variable | Default | Notes |
|---|---|---|
| `TRIDENT_ENV` | `development` | `production` requires `TRIDENT_JWT_SECRET`, gives JSON logs, and skips the demo users |
| `TRIDENT_DATABASE_URL` | `sqlite:///data/databases/trident.db` | `postgresql+psycopg://user:pass@host/db` for PostgreSQL |
| `TRIDENT_JWT_SECRET` | random per process (dev) | HS256 signing key |
| `TRIDENT_ADMIN_PASSWORD` | — | Creates the `admin` user if it is missing |
| `TRIDENT_CORS_ORIGINS` | `http://localhost:5173` | Vite dev server |
| `TRIDENT_RUN_SCHEDULER` | `true` | Set `false` on replicas that should not compete for jobs (not required: leases already make jobs exclusive) |
| `TRIDENT_ML_ENABLED`, `TRIDENT_WEATHER_ENABLED` | `true` | The API degrades gracefully without them |
| `TRIDENT_SOS_RATE_PER_MIN`, `TRIDENT_SOS_BURST`, `TRIDENT_LOGIN_RATE_PER_MIN` | 20, 10, 10 | Per-IP token buckets (SOS sized for shelter Wi-Fi / CGNAT sharing one IP) |
| `TRIDENT_SMS_SECRET`, `TRIDENT_SMS_NUMBER` | empty | SMS gateway webhook secret (empty = SMS intake off) and the number shown to the public |
| `TRIDENT_PUBLIC_URL` | `http://localhost:8000` | Base URL used in SMS replies and tracking links |
| `TRIDENT_EXPOSE_DOCS` | off in production | Serve `/docs` and `/openapi.json` in production |

The full list of variables is in [docs/GETTING_STARTED.md](../../docs/GETTING_STARTED.md).

## Layout

```
app/
  main.py          app factory: lifespan (migrate, seed, scheduler, ML warm-up), middleware, /ws, health, SPA
  config.py        settings from the environment
  db.py            engine (SQLite WAL + BEGIN IMMEDIATE / PostgreSQL), write_tx() = one ACID transaction
  models.py        ORM; schema changes go through migrations/ (Alembic)
  security.py      bcrypt, JWT access tokens, rotating refresh tokens, device/bridge keys
  deps.py          current user, role checks (admin > dispatcher > responder > viewer), device auth
  realtime.py      WebSocket hub: per-topic seq; clients resync via REST on a gap
  jobs.py          scheduler with database-lease leader election
  observability.py JSON logs, request ids, security headers, /metrics
  api/routes.py    REST v1
  services/        sos (state machine, optimistic locking, capacity), triage (0-100 score with reasons),
                   telemetry (idempotent ingest -> ML -> fusion -> alerts, command outbox), alerts,
                   rov (semi-autonomous missions, exclusive manual control, serial-bridge outbox),
                   weather (cached forecasts), public_data (Open-Meteo GloFAS rivers), analytics, auth
  tools/simulate.py  replay simulator (real recordings -> virtual wearables)
migrations/        Alembic revisions
```

## How the principles show up

- **ACID.** Each command runs in one `write_tx()`: the row, its timeline event, the team load and the audit row commit together. Events are published only after commit.
- **Consistency vs availability (CAP).**
  - Dispatch state is consistency-first: optimistic locking with a `version` column (stale version → 409), state-machine transitions enforced on the server, and team capacity checked inside the transaction.
  - Telemetry is availability-first: devices queue frames offline, and the server de-duplicates on `(device, boot, seq)`, so a resend is harmless.
- **Idempotency.** It covers SOS submissions (`Idempotency-Key`), telemetry, and both command outboxes (device commands are acked; ROV commands are acked by the bridge).
- **Scheduling.** Each job holds a lease row in the database, renewed while it runs, so with N replicas a job still runs on exactly one of them.
- **Security.**
  - Access tokens are short JWTs. Refresh tokens rotate, and reusing an old one revokes the whole login. The role is re-read from the database on every request.
  - Devices and ROV bridges authenticate with hashed per-unit keys.
  - Public endpoints are rate-limited. Every write is audited. CSP and other security headers are set, and inputs are strictly validated.
- **Graceful degradation.** Without models or weather, the API keeps working and `/readyz` reports what is missing. Only the database is required.
