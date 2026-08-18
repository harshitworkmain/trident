# TRIDENT — Fast-Track Technical Interview Prep & Defense Guide
**Role Target:** Software Engineer (Full Stack) — Foodhub | **Candidate:** Harshit Singh

---

## 1. System Overview (30-Second Pitch)

> "TRIDENT is a full-stack emergency command platform that automates incident intake, priority scoring, and resource dispatch. 
> 
> Incoming emergency requests are evaluated by a 15-factor decision engine scoring priority from 1 to 5. High-priority incidents (P4/P5) trigger atomic auto-dispatch to available rescue teams or ROVs. 
> 
> The stack uses a Flask REST API (25 endpoints) over a 6-table SQLite schema (63 columns, 4 FKs), powering a 2,960-line single-page dashboard with 11 Chart.js charts and 30-second polling. It is containerized via Docker and Gunicorn WSGI and deployed on Render."

---

## 2. High-Level Design (HLD)

### Architecture & Data Flow

```
[Client SPA (2,960L platform.html)] 
   │ HTTP POST /api/sos (Payload + 5 Vulnerability Flags)
   ▼
[Gunicorn WSGI (0.0.0.0:${PORT:-7860})] ──► [Flask REST API (app.py / main.py)]
                                                │
                                  ┌─────────────┴─────────────┐
                                  ▼                           ▼
                      [Priority Engine (15 factors)]   [Spatial/Graph Modules]
                                  │                     (Haversine & NetworkX)
                         (If P4/P5: Auto-Dispatch)
                                  │
                                  ▼
                      [SQLite DB (trident_sos.db)]
                      6 Tables | 63 Cols | 4 FKs
```

1. **Intake & Validation:** Client validates inputs (`main_app.js`) and POSTs payload to `/api/sos`.
2. **Scoring & Dispatch:** Server computes priority score ($1 \le P \le 5$). If $P \ge 4$, atomically assigns the lowest-load `AUTO_DEPLOY` team.
3. **Persistence & Response:** Inserts into `sos_requests` (27 cols) and `sos_status_history`, returning HTTP 201 + Reference ID (`TRD-XXXXXX`).
4. **Dashboard Polling:** Client UI auto-refreshes every 30s via `GET /api/sos` and `GET /api/stats`.

### Architectural Trade-offs

* **SQLite vs PostgreSQL:** Zero setup and free Render deployment; gave up concurrent write throughput.
* **30s Polling vs WebSockets:** Stateless and zero cold-start failures on Render; gave up sub-second push updates.
* **Rule-Based MCDA vs ML Scoring:** 100% auditable and deterministic emergency scoring; gave up dynamic weight learning.

---

## 3. Low-Level Design (LLD)

### Database Schema (6 Tables, 63 Columns, 4 Foreign Keys)

* **`sos_requests` (27 cols):** `id` (PK), `reference_id` (UK), victim info, `people_injured`, food/water availability, 5 vulnerability flags (`pregnant`, `elderly`, `children`, `disabled`, `medical`), `priority`, `status`, `assigned_team_id` (FK $\to$ `response_teams.id`), geolocations, timestamps.
* **`sos_status_history` (6 cols):** `id` (PK), `reference_id` (FK $\to$ `sos_requests.reference_id`), `status`, `notes`, `updated_by`, `created_at`.
* **`sos_assignments` (5 cols):** `id` (PK), `reference_id` (FK), `team_id` (FK $\to$ `response_teams.id`), `assigned_by`, `assigned_at`.
* **`sos_notes` (5 cols):** `id` (PK), `reference_id` (FK), `note`, `author`, `created_at`.
* **`response_teams` (12 cols):** `id` (PK), `team_name`, `team_type`, `capacity`, `current_load`, `is_available`, `deployment_mode` (`AUTO_DEPLOY` vs `MANUAL_DEPLOY`).
* **`emergency_contacts` (8 cols):** Standalone lookup table.

### Core Algorithms

1. **Priority Scoring (`calculate_priority()`):** Base = 1. Adds +2 for injuries/medical, +1 per vulnerability flag (pregnant, elderly, children, disabled, food/water critical), +1 to +3 for emergency type (tsunami/dam breach = +3, flood/storm = +2). Bounded by `min(priority, 5)`.
2. **Pairwise Routing (`calculate_shortest_paths()`):** Computes distance between active nodes via Haversine approximation ($d = 111 \cdot \sqrt{\Delta\text{lat}^2 + \Delta\text{lon}^2}$ km) and sorts by `(distance, -(priority_sum))`.
3. **Graph Risk Diffusion (`network_analyzer.py`):** 10-node coastal graph with edge weights $w = |\Delta T| + |\Delta\text{Wind}| + 0.1|\Delta\text{Hum}|$. Runs 5-iteration risk diffusion ($\gamma = 0.75$) + Edmonds-Karp Max Flow (`nx.maximum_flow`).

---

## 4. Resume Metrics — Sourced & Defended

| Metric | Source File / Exact Count | Quick Interview Defense |
|---|---|---|
| **25 Endpoints** | `main.py` (25 `@app.route` decorators) | Covers 3 web views, 6 SOS CRUD, 3 status/team updates, 4 stats/analytics, 4 AI endpoints, 4 ROV control, 1 wearable status route. |
| **6 Tables / 63 Cols** | `init_database()` ([main.py:63-163](file:///home/harshit/Documents/projects-all/trident/src/backend/main.py#L63-L163)) | Normalized 3NF layout. Decouples core requests (27 cols) from append-only audit histories (`sos_status_history`, `sos_assignments`, `sos_notes`). |
| **4 Foreign Keys** | DDL FK constraints ([main.py:91, 104, 116, 129](file:///home/harshit/Documents/projects-all/trident/src/backend/main.py#L91)) | Links `assigned_team_id` $\to$ `response_teams.id`, and links history/notes/assignments $\to$ `sos_requests.reference_id`. |
| **2,960-Line Dashboard** | `wc -l src/frontend/templates/platform.html` | Unified single-page HTML template containing structure for 3 main tabs, inline CSS, and 29 inline JS functions. |
| **11 Charts / 30s Polling** | `platform.html` (11 `new Chart()`), `dashboard.js` (`setInterval` 30s) | 9 distinct chart types (Doughnut, Bar, Line, Multi-axis). 30s polling balances fresh telemetry with zero connection leaks on free hosting. |
| **15 Weighted Factors** | `calculate_priority()` ([main.py:431-464](file:///home/harshit/Documents/projects-all/trident/src/backend/main.py#L431-L464)) | Evaluates injuries, medical need, 5 vulnerability flags, 2 resource states, and 4 disaster classifications on a 1–5 scale. |
| **5 Docker Steps / ~80% Footprint Cut** | `Dockerfile` (5 instructions), `requirements-prod.txt` (15 pkgs) | Used CPU-only PyTorch `--extra-index-url https://download.pytorch.org/whl/cpu` (~170MB vs 2GB CUDA), dropping container size by ~80%. |

---

## 5. Real Challenges & Fixes

1. **Render OOM & Debian Build Failure:** CUDA PyTorch (~2GB) and missing `libgl1-mesa-glx` broke Render builds. **Fix:** Created `requirements-prod.txt` with CPU PyTorch wheels, stripped desktop GUI libs, and added `.dockerignore` to drop build context from ~200MB to <1MB.
2. **WSGI Initialization Bug:** `init_database()` was inside `if __name__ == '__main__':` in `main.py`, so Gunicorn imports skipped DB setup. **Fix:** Refactored `app.py` to call `init_database()` and `init_ai_model()` unconditionally at module import time.
3. **ROV Mission State Concurrency:** Race condition on mutating shared `active_rov_missions` dict. **Fix:** Wrapped dict operations in `threading.Lock()` and spawned non-blocking deployment sequences in background daemon threads (`threading.Thread(daemon=True)`).

---

## 6. Foodhub Tech Stack Alignment

* **Node.js/Express $\to$ Python/Flask:** Direct concept transfer — REST routing, request parsing, HTTP verbs, WSGI/middleware concepts.
* **TypeScript $\to$ Vanilla JS:** Event-driven DOM handling, async `fetch()`, SPA hash routing (`platform.js`). (Acknowledge TS learning curve).
* **REST APIs & SQL:** Exact match — 25 REST endpoints, relational SQLite schema (6 tables, 4 FKs), DDL, parameterized queries.
* **Docker & Infra:** Exact match — 5-step `Dockerfile`, `.dockerignore`, Gunicorn WSGI, environment variables, Render cloud deployment.

---

## 7. Key Interview Questions & Concise Answers

* **Q: Walk me through the SOS submit-to-dispatch flow.**  
  *A:* Client POSTs to `/api/sos`. `calculate_priority()` scores 15 criteria (1–5). If score $\ge 4$, `assign_team_for_emergency()` atomically assigns the lowest-load `AUTO_DEPLOY` team. The record is written to `sos_requests` (27 cols) and `sos_status_history`, returning HTTP 201 + Ref ID.

* **Q: Why SQLite instead of PostgreSQL?**  
  *A:* Zero configuration and single-file container portability for a Render prototype. For production, I'd migrate to AWS RDS PostgreSQL + PgBouncer for concurrent write scaling.

* **Q: Why 30s polling instead of WebSockets?**  
  *A:* Avoids stateful connection dropouts when free-tier Render instances sleep. Polling provides simple, stateless state sync. In production, I'd use Socket.IO + Redis Pub/Sub.

* **Q: What happens if Gunicorn runs with 4 worker processes?**  
  *A:* Multi-process memory isolation means in-memory dicts (`active_rov_missions`) and `threading.Lock()` are NOT shared across workers. Shared state must be moved to Redis.

---

## 8. Probing Follow-Up Chains (Practice)

### Chain 1: Database Architecture & Concurrency
* **Q1:** *Why SQLite?* $\to$ **A1:** Portability and zero setup in a single Docker container on Render.
* **Q2:** *How does SQLite handle concurrent writes?* $\to$ **A2:** File-level locking. Each request opens a short-lived connection via `sqlite3.connect()`, commits, and closes immediately.
* **Q3:** *What if 2 high-priority requests hit at the exact same time?* $\to$ **A3:** Both could read the same team load before writing, causing a race condition double-assignment. Needs a `BEGIN IMMEDIATE` transaction.
* **Q4:** *How to scale to 10k writes/sec?* $\to$ **A4:** PostgreSQL + PgBouncer, row-level locking (`SELECT FOR UPDATE`), or buffer incoming requests into Kafka/SQS for batch writes.

### Chain 2: Priority Scoring & Auto-Dispatch
* **Q1:** *How does priority scoring work?* $\to$ **A1:** Base 1. Adds +2 for injuries/medical, +1 per vulnerability flag, +1 to +3 for disaster type, capped at 5 via `min(priority, 5)`.
* **Q2:** *How are teams assigned?* $\to$ **A2:** Priority $\ge 4$ triggers auto-dispatch querying `AUTO_DEPLOY` teams ordered by `current_load ASC LIMIT 1`.
* **Q3:** *What if all AUTO_DEPLOY teams are full?* $\to$ **A3:** SQL query returns `None`, request stays `pending` with `assigned_team_id = NULL` for manual dispatcher intervention.
* **Q4:** *How to prevent low-priority request starvation?* $\to$ **A4:** Add a time-decay factor — increment priority by +0.5 for every 15 minutes an incident remains pending.

### Chain 3: Production Docker Deployment
* **Q1:** *Why `requirements-prod.txt`?* $\to$ **A1:** Drops dev/GUI tools (OpenCV, PyQt6) to shrink dependencies from 47 to 15 packages.
* **Q2:** *How did you shrink PyTorch?* $\to$ **A2:** Added `--extra-index-url https://download.pytorch.org/whl/cpu`, replacing the 2GB CUDA wheel with a ~170MB CPU wheel.
* **Q3:** *Why Gunicorn instead of `app.run()`?* $\to$ **A3:** `app.run()` is single-threaded for dev. Gunicorn provides pre-fork worker process management and dynamic `$PORT` binding.
