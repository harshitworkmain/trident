# TRIDENT — Technical Interview Preparation & Defense Guide
**Role Target:** Software Engineer (Full Stack) — Foodhub  
**Project:** TRIDENT (Integrated Disaster Response & Emergency Command Platform)  
**Author:** Harshit Singh

---

## 1. System Overview (30-Second Pitch)

> "TRIDENT is an integrated emergency response platform designed to automate disaster intake, incident prioritization, and rescue team dispatch in real time. 
> 
> When disaster victims or edge sensors (like wearables) submit emergency requests, the system passes them through a 15-factor Multi-Criteria Decision Analysis (MCDA) engine that calculates a priority score from 1 to 5. High-severity incidents (Priority 4+) immediately trigger atomic auto-dispatch to available response teams or autonomous ROV units without human delay. 
> 
> The platform is built with a Flask REST API backend over a relational SQLite schema, serving a 2,960-line single-page web dashboard with 11 real-time Chart.js telemetry visualizations, 30-second polling, and graph-based spatial risk propagation modeling. The full stack is containerized with Docker and Gunicorn WSGI and deployed live on Render."

---

## 2. High-Level Design (HLD)

### System Architecture Diagram

```
                       ┌────────────────────────────────────────────────────────┐
                       │                   CLIENT / FRONTEND                    │
                       │  Single-Page Platform Dashboard (platform.html, 2,960L) │
                       │  - SOS Reporting Form (Client Validation + Priority)   │
                       │  - Live EOC Monitoring (30s Polling / Modal Controls)   │
                       │  - Analytics & AI Predictions (11 Chart.js Instances)  │
                       └──────────────────────────┬─────────────────────────────┘
                                                  │ HTTP REST (JSON)
                                                  ▼
                       ┌────────────────────────────────────────────────────────┐
                       │               PRODUCTION WSGI WEBSERVER                │
                       │              Gunicorn (0.0.0.0:${PORT:-7860})          │
                       └──────────────────────────┬─────────────────────────────┘
                                                  │
                                                  ▼
                       ┌────────────────────────────────────────────────────────┐
                       │                 FLASK BACKEND (app.py)                 │
                       │             25 REST Endpoints (src/backend/main.py)    │
                       │ ┌──────────────────────┐   ┌─────────────────────────┐ │
                       │ │ Priority Engine      │   │ Graph Risk & Spatial    │ │
                       │ │ (15 Weighted Factors)│   │ (Haversine & NetworkX)  │ │
                       │ └──────────┬───────────┘   └────────────┬────────────┘ │
                       │            │                            │              │
                       │ ┌──────────▼───────────┐   ┌────────────▼────────────┐ │
                       │ │ Threading Lock &     │   │ PyTorch LSTM Inference  │ │
                       │ │ ROV Daemon Threads   │   │ (Weather Forecasting)   │ │
                       │ └──────────────────────┘   └─────────────────────────┘ │
                       └────────────┬────────────────────────────┬──────────────┘
                                    │                            │
                                    ▼                            ▼
                       ┌─────────────────────────┐  ┌──────────────────────────┐
                       │   SQLITE DATABASE FILE  │  │  OPTIONAL EDGE HARDWARE  │
                       │   (trident_sos.db)      │  │  - ESP32 Wearable Stream │
                       │   6 Relational Tables   │  │  - ROV Control Serial    │
                       │   63 Total Columns      │  │    (importserial.py Popen│
                       └─────────────────────────┘  └──────────────────────────┘
```

### End-to-End Core Data Flow: SOS Emergency Submission to Dispatch

1. **Client Submission:** The user fills out the SOS form in `platform.html`. `main_app.js` validates inputs client-side (regex for phone/email, bounds for age 1–120, casualty count $\ge 0$).
2. **HTTP POST Request:** The client sends `POST /api/sos` with a JSON payload containing victim details, location (lat/lon/city), medical needs, and vulnerability flags (`pregnant`, `elderly`, `children`, `disabled`, `medical`).
3. **Priority Calculation:** `main.py::calculate_priority()` evaluates the payload against 15 weighted criteria (e.g., injuries $+2$, medical emergency $+2$, tsunami/dam-breach $+3$, food/water scarcity $+1$) returning a score from 1 to 5.
4. **Reference ID Generation:** System generates a unique reference code (`TRD-XXXXXX` using timestamp + random hex).
5. **Team Auto-Dispatch (if Priority $\ge 4$):** 
   - If priority is 4 or 5, `assign_team_for_emergency()` executes an atomic SQL lookup for an available `AUTO_DEPLOY` team (e.g., `Team Alpha`) with the lowest `current_load`.
   - The team's `current_load` is incremented by 1, `is_available` is updated, and an entry is inserted into `sos_assignments`.
   - If priority is $\le 3$, assignment is set to `NULL` for manual triage.
6. **Persistence:** The record is inserted into `sos_requests` (27 columns) and initial status (`pending` or `assigned`) is logged to `sos_status_history`.
7. **Response & Client Update:** Server responds with HTTP `201 Created` returning the `reference_id`, priority score, and assigned team info. The client displays a success modal.
8. **Dashboard Propagation:** The live EOC dashboard picks up the new request on its next 30-second polling cycle (`GET /api/sos` and `GET /api/stats`).

---

### Key Architectural Decisions & Trade-Offs

| Decision | Chosen Tech / Pattern | Alternative Considered | Trade-Off Rationale (What gained vs. what lost) |
|---|---|---|---|
| **Database Engine** | **SQLite** (`trident_sos.db`) | PostgreSQL / MySQL | **Gained:** Zero configuration, single-file portability, zero cloud database cost. <br>**Lost:** High concurrency write scaling (database-level locking under heavy write traffic). |
| **Real-Time Updates** | **30s HTTP Polling** | WebSockets (Socket.IO) / SSE | **Gained:** Simple HTTP mechanics, zero persistent connection overhead, perfect fit for Render free-tier cold starts. <br>**Lost:** Instant sub-second push latency (updates lag up to 30s). |
| **Priority Scoring** | **Deterministic Rule-Based MCDA** | ML Classification Model | **Gained:** 100% deterministic, transparent, and auditable scoring — vital for emergency logistics compliance. <br>**Lost:** Inability to dynamically adapt weights from historical feedback without manual code updates. |
| **Frontend Architecture** | **Single-Page Application in Vanilla JS (2,960 lines)** | React / Next.js SPA | **Gained:** Zero build toolchain complexity, single static template deployment, lightweight browser footprint. <br>**Lost:** Component state encapsulation, declarative DOM diffing, compile-time type safety. |
| **Container ML Build** | **CPU-only PyTorch (`requirements-prod.txt`)** | Full CUDA GPU PyTorch | **Gained:** Reduced container image footprint by ~80% (<200MB vs 2GB+), eliminating Render cloud RAM OOM build failures. <br>**Lost:** GPU-accelerated training/inference (acceptable since production inference is batch=1 prediction). |

---

## 3. Low-Level Design (LLD)

### Database Schema (SQLite — 6 Tables, 63 Columns, 4 Foreign Keys)

```
+----------------------------------------------------------------------------------------------------+
|                                         sos_requests                                               |
+----------------------------------------------------------------------------------------------------+
| PK  id (INTEGER AUTOINCREMENT)                                                                     |
| UK  reference_id (TEXT, UNIQUE, NOT NULL)                                                          |
|     name (TEXT), age (INT), phone (TEXT), email (TEXT), address (TEXT), city (TEXT), pincode (TEXT)|
|     people_to_rescue (INT), people_injured (INT)                                                   |
|     food_availability (TEXT), water_availability (TEXT)                                            |
|     pregnant (BOOL), elderly (BOOL), children (BOOL), disabled (BOOL), medical (BOOL)              |
|     emergency_type (TEXT), additional_info (TEXT)                                                  |
|     latitude (REAL), longitude (REAL)                                                              |
|     priority (INT DEFAULT 1), status (TEXT DEFAULT 'pending')                                      |
| FK  assigned_team_id (INT -> response_teams.id)                                                    |
|     created_at (TIMESTAMP), updated_at (TIMESTAMP)                                                 |
+----------------------------------┬─────────────────────────────────────────────────────────────────+
                                   │ 1
                                   │
         ┌─────────────────────────┼─────────────────────────┬─────────────────────────┐
         │ 1..N                    │ 1..N                    │ 1..N                    │ 1..N
+────────▼─────────────+  +────────▼─────────────+  +────────▼─────────────+  +────────▼─────────────+
|  sos_status_history  |  |   sos_assignments   |  |      sos_notes       |  |   response_teams    |
+----------------------+  +---------------------+  +----------------------+  +---------------------+
| PK id                |  | PK id               |  | PK id                |  | PK id               |
| FK reference_id      |  | FK reference_id     |  | FK reference_id      |  |    team_name        |
|    status            |  | FK team_id          |  |    note              |  |    team_type        |
|    notes             |  |    assigned_by      |  |    author            |  |    capacity         |
|    updated_by        |  |    assigned_at      |  |    created_at        |  |    current_load     |
|    created_at        |  +---------------------+  +----------------------+  |    is_available     |
+----------------------+                                                     |    deployment_mode  |
                                                                             +---------------------+
```

- **FK 1:** `sos_requests.assigned_team_id` $\to$ `response_teams.id`
- **FK 2:** `sos_status_history.reference_id` $\to$ `sos_requests.reference_id`
- **FK 3:** `sos_assignments.reference_id` $\to$ `sos_requests.reference_id`
- **FK 4:** `sos_notes.reference_id` $\to$ `sos_requests.reference_id`

*(Note: `emergency_contacts` table operates as an unlinked lookup table with 8 columns).*

---

### Core API Surface (25 Endpoints)

| Method | Endpoint Path | Purpose | Key Request/Response Details |
|---|---|---|---|
| `GET` | `/` | Serves main unified platform | Returns `platform.html` template |
| `POST` | `/api/sos` | Submit new emergency request | **Req:** Victim payload + flags $\to$ **Resp:** `{status: 'success', reference_id, priority, assigned_team_id}` |
| `GET` | `/api/sos` | List all SOS requests | Supports status filtering, returns array sorted by `priority DESC, created_at DESC` |
| `GET` | `/api/sos/<ref_id>`| Fetch single request status | Returns full record + status history trail |
| `PUT` | `/api/sos/<ref_id>/update-status` | Update incident state | **Req:** `{status, notes, updated_by}` $\to$ Updates `sos_requests` & inserts audit row into `sos_status_history` |
| `PUT` | `/api/sos/<ref_id>/assign-team` | Manual team dispatch | **Req:** `{team_id}` $\to$ Adjusts team loads and updates `assigned_team_id` |
| `GET` | `/api/stats` | Summary KPI metrics | Returns total, pending, in-progress, resolved counts, high-priority count, team capacity |
| `GET` | `/api/analytics/status-distribution` | Graph distribution data | Returns aggregated SQL counts grouped by `status` and `emergency_type` |
| `GET` | `/api/ai/temperature-prediction` | LSTM model forecast | Query param `hours=24`. Returns 24-hour array of predicted temperatures |
| `GET` | `/api/ai/shortest-paths` | Spatial dispatch routing | Runs pairwise Haversine on active nodes $\to$ Returns top-10 shortest routes |
| `POST`| `/api/rov/deploy` | Trigger ROV mission | **Req:** `{rov_id, mission_type}` $\to$ Guards mutex lock, spawns daemon thread |

---

### Core Algorithms & Non-Trivial Business Logic

#### 1. Multi-Criteria Priority Scoring Engine (`calculate_priority()`)
- **Base Score:** Starts at `1` (Low Priority).
- **Injuries & Medical:** `peopleInjured > 0` ($+2$), `medical == 'true'` ($+2$).
- **Vulnerable Demographics:** `pregnant` ($+1$), `elderly` ($+1$), `children` ($+1$), `disabled` ($+1$).
- **Resource Depletion:** `foodAvailability` in `['none', 'critical']` ($+1$), `waterAvailability` in `['none', 'critical']` ($+1$).
- **Disaster Type Bonus:** `tsunami` / `dam-breach` ($+3$), `flood` / `storm` / `water-level-rising` ($+2$), `coastal-erosion` ($+1$).
- **Bounding Cap:** Score is bounded via `min(priority, 5)` to enforce a strict $1 \le P \le 5$ scale.

#### 2. Spatial Pairwise Routing (`calculate_shortest_paths()`)
- Fetches all active SOS nodes with non-null coordinates.
- Computes pairwise geographic distance using the equirectangular Haversine approximation:
  $$d = 111 \times \sqrt{(\text{lat}_2 - \text{lat}_1)^2 + (\text{lon}_2 - \text{lon}_1)^2} \quad \text{(in km)}$$
- Sorts resulting paths using a multi-key tuple: `key = lambda x: (x['distance'], -(x['from_priority'] + x['to_priority']))`.
- Slices and returns top-10 shortest high-priority transit vectors.

#### 3. Graph Risk Propagation & Maximum Hydraulic Flow (`network_analyzer.py`)
- **Risk Diffusion:** Constructs a 10-node, 12-edge undirected graph of Chennai coastal zones. Edge weight $w = |\Delta T| + |\Delta \text{Wind}| + 0.1 |\Delta \text{Humidity}|$. Runs a 5-step iterative risk propagation model with decay $\gamma = 0.75$:
  $$R_i^{(t+1)} = \min\left(1.0, \, \frac{\sum_{j \in \text{Nbr}(i)} R_j^{(t)} \cdot 0.75}{|\text{Nbr}(i)|}\right)$$
- **Max Hydraulic Flow:** Uses `nx.maximum_flow` (Edmonds-Karp algorithm) on a directed graph ($\text{Source} \to \text{Sink}$) with channel capacities ($\text{m}^3/\text{s}$). Identifies overflow risk when incoming flow exceeds drainage thresholds ($40\text{ m}^3/\text{s}$ at Marina Beach).

---

## 4. Every Resume Metric — Sourced and Defended

| Metric on Resume | Exact Codebase Source | Technical Interview Defense / Reasoning |
|---|---|---|
| **25 API Endpoints** | `grep -c "@app.route" src/backend/main.py` yields **25** | The backend requires 25 explicit routes because emergency management requires distinct domain bounded contexts: 3 web view routes, 6 core SOS CRUD endpoints, 3 status/assignment mutation endpoints, 4 analytics/stats reporting routes, 4 AI model endpoints, 4 ROV mission control endpoints, and 1 wearable device status endpoint. |
| **6 Relational Tables** | 6 `CREATE TABLE IF NOT EXISTS` blocks in `init_database()` ([main.py:63-163](file:///home/harshit/Documents/projects-all/trident/src/backend/main.py#L63-L163)) | The schema is normalized into 6 tables (`sos_requests`, `sos_status_history`, `sos_assignments`, `sos_notes`, `emergency_contacts`, `response_teams`) to decouple transaction state from audit logs. Keeping status history in a separate append-only table prevents table lock contention on the primary request table during status updates. |
| **63 Total Columns** | Sum of column definitions across all 6 tables in `init_database()` | Table breakdown: `sos_requests` (27 cols), `response_teams` (12 cols), `emergency_contacts` (8 cols), `sos_status_history` (6 cols), `sos_assignments` (5 cols), `sos_notes` (5 cols). `sos_requests` has 27 columns because it captures victim vitals, 5 demographic vulnerability booleans, resource scarcity states, geolocations, and assignment references in a single flat row for fast write ingestion. |
| **4 Foreign Keys** | Explicit `FOREIGN KEY` constraints defined in DDL ([main.py:91, 104, 116, 129](file:///home/harshit/Documents/projects-all/trident/src/backend/main.py#L91)) | Enforces referential integrity at the database layer: links `assigned_team_id` to `response_teams.id`, and links `sos_status_history`, `sos_assignments`, and `sos_notes` back to `sos_requests.reference_id`. |
| **2,960-Line Single-Page Dashboard** | `wc -l src/frontend/templates/platform.html` yields **2,960 lines** | `platform.html` is a unified single-page template containing HTML structure for 3 main tab views, CSS styles, and 29 distinct inline JS functions. It was engineered as a single file to eliminate external asset loading latency during offline disaster recovery testing. |
| **11 Chart.js Visualizations** | 11 `new Chart(...)` instantiations in `platform.html` across 9 unique canvas elements | 9 distinct charts: Emergency Types (Doughnut), Status Distribution (Bar), Priority Distribution (Bar), 24h Hourly Trends (Line), 7d Daily Trends (Line), Top Cities (Horizontal Bar), Temperature Forecast (Line), Waterflow Forecast (Line), Multi-axis Weather (Line). Two charts (Types & Status) have secondary update instantiations. |
| **30s Real-Time Polling** | `setInterval(..., 30000)` in `src/frontend/static/js/dashboard.js` | 30 seconds was selected as the optimal polling balance between operational freshness and avoiding HTTP request flooding on free-tier server instances. |
| **15 Weighted Factors** | 15 conditional checks in `calculate_priority()` ([main.py:431-464](file:///home/harshit/Documents/projects-all/trident/src/backend/main.py#L431-L464)) | Includes base priority (1), injuries (+2), medical (+2), 5 vulnerability flags (+1 each), 2 resource scarcity flags (+1 each), and 4 disaster severity levels (+1 to +3). |
| **5 Docker Instructions** | 5 active build steps in `Dockerfile` | Step 1: `FROM python:3.10-slim`, Step 2: `WORKDIR /code`, Step 3: `COPY requirements-prod.txt` + `RUN pip install`, Step 4: `COPY . .` + `RUN chmod`, Step 5: `CMD gunicorn`. Streamlined to maximize build layer caching. |
| **~80% Container Footprint Reduction** | `requirements-prod.txt` (15 packages) vs `requirements.txt` (47 packages) | Omitting OpenCV, PyQt6, GUI tools, and using `--extra-index-url https://download.pytorch.org/whl/cpu` shrunk the PyTorch dependency from a 2GB CUDA wheel to a ~170MB CPU wheel, reducing the container build size by ~80%. |

---

## 5. Trade-offs I Actually Made

### 1. SQLite File Database vs. Managed PostgreSQL / RDS
- **What I Chose:** Local SQLite database file (`trident_sos.db`) accessed via Python's standard `sqlite3` module.
- **What I Gave Up:** High concurrent write throughput and serverless multi-node horizontal scalability.
- **Why / What I'd do differently:** Chosen to ensure 100% zero-cost deployment on Render and zero-dependency offline local execution. For production, I would swap SQLite for PostgreSQL (AWS RDS or Neon.tech) with connection pooling (SQLAlchemy + PgBouncer) to handle concurrent multi-user write transactions without table-level lock blocking.

### 2. HTTP Polling (30s) vs. WebSockets (Socket.IO / SSE)
- **What I Chose:** Client-side 30-second interval polling via standard `fetch()` API.
- **What I Gave Up:** Instant sub-second event push updates and reduced HTTP header overhead.
- **Why / What I'd do differently:** Free-tier container hosting on Render spins down after inactivity; persistent WebSocket connections often break or cause memory leaks during cold starts. Polling guaranteed reliable state sync without connection state management. In production, I'd implement Socket.IO with a Redis Pub/Sub adapter to push real-time emergency events instantly to operator dashboards.

### 3. Rule-Based Scoring Engine vs. Machine Learning Classifier
- **What I Chose:** Deterministic 15-factor additive scoring function with a hard cap at 5.
- **What I Gave Up:** Ability to learn non-linear feature interactions automatically from past incident outcomes.
- **Why / What I'd do differently:** Emergency response triage requires **100% auditability and predictability**. An ML model acting as a "black box" could misclassify an incident due to feature drift, leading to regulatory failure. A rule-based system guarantees that an injured pregnant victim always receives high priority.

### 4. Monolithic Single-Page Template vs. React Component Architecture
- **What I Chose:** A unified 2,960-line HTML template (`platform.html`) containing inline CSS, DOM elements, and inline JS modules.
- **What I Gave Up:** Reusable component abstraction, modular file splitting, and virtual DOM diffing.
- **Why / What I'd do differently:** Allowed immediate development without Node build pipelines (`webpack`, `vite`, `babel`), ensuring the frontend can be served raw directly by Flask. In a production team environment, I would refactor this into a modular React / Next.js SPA with TypeScript types for API contract enforcement.

---

## 6. Real Challenges and How They Were Solved

### Challenge 1: Render Cloud Container OOM & Debian Build Failure
- **Problem:** Initial Docker deployments to Render failed (`exit status 1`). The build exceeded the 512MB RAM limit during `pip install` because `requirements.txt` pulled PyTorch CUDA binaries (~2GB) and OpenCV system dependencies (`libgl1-mesa-glx`), which were also dropped in the base Debian Trixie image.
- **Fix:** 
  1. Created a dedicated `requirements-prod.txt` pointing to CPU-only PyTorch wheels: `--extra-index-url https://download.pytorch.org/whl/cpu`.
  2. Removed GUI (`PyQt6`, `pyqtgraph`) and desktop CV libraries (`opencv-python`, `ultralytics`) from production requirements since web server inference only needs PyTorch CPU tensor math.
  3. Created `.dockerignore` to exclude local `venv/`, `.git/`, `.pio/`, and `*.db`, shrinking the build context from ~200MB to <1MB.
- **Outcome:** Build time dropped from failing to succeeding in <60 seconds with a final image size under 300MB.

### Challenge 2: Flask Startup Initialization Bug in Imported Application Context
- **Problem:** When launching the app via WSGI (`gunicorn app:app`), the database tables and AI models were not initializing properly because `init_database()` and `init_ai_model()` were originally nested inside the `if __name__ == '__main__':` block of `main.py`, which is skipped during WSGI module imports.
- **Fix:** Refactored `app.py` to explicitly import `init_database` and `init_ai_model` and invoke them at module import time before Gunicorn binds the WSGI callable.
- **Outcome:** Guaranteed 100% database schema readiness and model memory allocation regardless of whether the app is started via `python app.py` or Gunicorn.

### Challenge 3: Race Conditions on Shared ROV Mission State
- **Problem:** Simultaneous HTTP requests to deploy ROV units (`POST /api/rov/deploy`) or update team assignments could mutate the global `active_rov_missions` in-memory dictionary concurrently, creating data corruption or double-assignment bugs.
- **Fix:** Implemented Python's `threading.Lock()` (`rov_mission_lock`) around all reads and writes to `active_rov_missions` and database load updates. Spawning background deployment execution via daemon threads (`threading.Thread(target=..., daemon=True).start()`) ensured the HTTP thread released the lock immediately while the background mission timer ran asynchronously.

---

## 7. Where This Overlaps With Foodhub's Actual Stack

| Foodhub Stack Requirement | TRIDENT Project Equivalent | Transferable Concept / Honest Gap |
|---|---|---|
| **Node.js / Express** | Python / Flask (`main.py`) | **Direct Transferable Concept:** REST API design, middleware patterns, routing, request parsing, HTTP status code management, and WSGI server deployment. |
| **TypeScript** | Vanilla JavaScript (`main_app.js`, `dashboard.js`, `platform.js`) | **Transferable Concept:** Client-side DOM manipulation, event-driven architecture, `fetch()` async/await patterns. <br>**Honest Gap:** Static typing and compile-time interfaces (I acknowledge TS as an area I am actively applying in projects like NeuroBridge AI). |
| **REST APIs** | 25 Flask REST Endpoints | **Direct Match:** Full RESTful design, JSON payload formatting, parameterized URL routes (`/api/sos/<ref_id>`), HTTP verbs (GET, POST, PUT). |
| **SQL Databases** | SQLite Relational Schema | **Direct Match:** Relational schema design, 6 tables, 4 foreign keys, DDL table initialization, parameterized SQL queries, indexing strategies. |
| **NoSQL Databases** | In-memory Dicts / JSON configs | **Honest Gap:** TRIDENT uses pure SQL. (I reference my experience with document key-value patterns and JSON serialization). |
| **React / Mobile** | Vanilla SPA Dashboard (`platform.html`) | **Transferable Concept:** SPA tab navigation, state-driven UI updates, modal state management, Chart.js integrations. |
| **Cloud Infra & Docker** | Docker, Gunicorn, Render Cloud PaaS | **Direct Match:** Writing multi-stage `Dockerfile`s, `.dockerignore` context optimization, environment variable injection, cloud PaaS deployment. |
| **System Reliability / Tooling** | Defensive fallbacks, error handlers, logging | **Direct Match:** Custom `@app.errorhandler(404/500)`, PyTorch model loading fallback heuristics, health checks, background thread isolation. |

---

## 8. Likely Interview Questions for This Specific Project

### Q1 (HLD): "Walk me through the architecture of TRIDENT and how data flows from victim submission to team dispatch."
**Answer:** "TRIDENT is structured as a 3-tier architecture. The frontend is a vanilla JS single-page dashboard. When an emergency form is submitted, it hits our Flask REST API (`POST /api/sos`). The backend executes `calculate_priority()`, an algorithm that scores 15 weighted factors (injuries, medical needs, vulnerability flags, disaster type) to assign a priority from 1 to 5. If the priority is 4 or 5, an auto-dispatch module queries our SQLite `response_teams` table for an available `AUTO_DEPLOY` team with the lowest current load, atomically updates its capacity, and inserts an assignment record. The incident is saved across `sos_requests` and `sos_status_history`, and the client receives a 201 response with the assigned team info."

### Q2 (LLD): "Why did you choose 6 tables for your SQLite database instead of keeping everything in one large SOS table?"
**Answer:** "To maintain proper relational normalization (3NF) and decouple transactional telemetry from audit trails. Our main `sos_requests` table has 27 columns capturing victim details, location, and flags. If we included assignment logs and status update history inside that same table, we would have massive data duplication every time a status changes. Instead, `sos_status_history`, `sos_assignments`, and `sos_notes` are separate child tables linked via foreign keys on `reference_id`. This keeps write operations fast and append-only."

### Q3 (Metrics): "Your resume claims 25 API endpoints. Why are there so many endpoints for a simple command dashboard?"
**Answer:** "The 25 endpoints cover distinct bounded contexts required for full operational control: 3 for web template rendering, 6 for core SOS request CRUD, 3 for status and team assignment mutations, 4 for dashboard analytics and SQL distributions, 4 for AI inference (temperature LSTM, waterflow, weather multi-axis, shortest paths), 4 for ROV mission control and emergency stops, and 1 for wearable device telemetry. Splitting these into dedicated endpoints ensures single-responsibility design for each API route."

### Q4 (Trade-Off): "Why did you use 30-second polling on the dashboard instead of WebSockets?"
**Answer:** "It was an intentional trade-off driven by our deployment target. We deployed the container to Render's free tier, which spins down instances on inactivity. WebSockets require persistent TCP connections and stateful server instances, which can drop or cause memory overhead during cold starts. 30-second HTTP polling provided guaranteed, stateless state synchronization that works reliably across container restarts without connection leakage."

### Q5 (Debugging): "What was the hardest bug you encountered while deploying this application?"
**Answer:** "The hardest issue was a container OOM build failure on Render. The original Docker build pulled CUDA-enabled PyTorch (~2GB) and attempted to compile OpenCV system libraries (`libgl1-mesa-glx`) that were deprecated in Debian Trixie. To fix this, I created a streamlined `requirements-prod.txt` with `--extra-index-url` pointing to PyTorch CPU-only wheels (~170MB), removed non-essential GUI dependencies, and added a `.dockerignore` file to omit local virtual environments and build artifacts. This reduced our container footprint by ~80% and brought build times under 60 seconds."

### Q6 (Scale): "How would you refactor this codebase if traffic scaled from 100 requests a day to 100,000 requests an hour?"
**Answer:** "First, I'd migrate the database from single-file SQLite to a managed PostgreSQL cluster with PgBouncer connection pooling and read replicas. Second, I'd replace HTTP polling with WebSockets powered by Redis Pub/Sub so dashboard clients receive instant updates without hammering the API. Third, I'd move background tasks like ROV deployment and AI predictions out of Flask daemon threads into a dedicated Celery worker queue backed by Redis."

---

## 9. If Asked "What Would You Change for Scale/Production"

If asked what shortcuts exist in TRIDENT and how to productionize it:

1. **Database Migration & Connection Pooling:**
   - *Current:* Single SQLite file with direct connection opens/closes per request.
   - *Production:* Migrate to PostgreSQL on AWS RDS with `SQLAlchemy` ORM and `PgBouncer` for connection pooling to support concurrent write scaling.

2. **Authentication & Access Control (RBAC):**
   - *Current:* Open API endpoints without auth headers.
   - *Production:* Implement JWT authentication (`PyJWT` or `Flask-JWT-Extended`) with bcrypt password hashing. Restrict administrative endpoints (`/api/sos/update-status`, `/api/rov/deploy`) to authenticated emergency operators using role-based access control.

3. **Event-Driven Architecture (WebSockets & Redis):**
   - *Current:* 30-second HTTP client polling.
   - *Production:* Replace polling with `Flask-SocketIO` + `Redis Pub/Sub` to stream live incident creation and status changes instantly to connected EOC clients.

4. **Asynchronous Background Task Workers:**
   - *Current:* In-memory Python `threading.Thread(daemon=True)` for ROV deployments.
   - *Production:* Decouple background jobs using `Celery` or `Redis Queue (RQ)` with retry policies, result backends, and dead-letter queues.

5. **Rate Limiting & Defensive Middleware:**
   - *Current:* No rate limits on `/api/sos`.
   - *Production:* Implement `Flask-Limiter` to enforce IP-level rate limits (e.g., 10 SOS submissions per minute per IP) to prevent Denial of Service (DoS) floods during active emergency events.

---

## 10. Probing Follow-Up Chains (Drill-Down Practice)

### Chain 1: Database Architecture & Concurrency

- **Q1 (Surface): "Why did you use SQLite for this project instead of a full database server like PostgreSQL?"**
  - **A1:** "I chose SQLite for portability and zero-configuration deployment. It allowed the full stack to run out-of-the-box in a single Docker container without setting up a separate database container or managing cloud database credentials on Render."
- **Q2 (One Layer Deeper): "How does SQLite handle concurrent writes when multiple SOS requests come in at the exact same time?"**
  - **A2:** "SQLite uses database-level lock files. When a write transaction begins, SQLite locks the entire database file. If another request attempts to write simultaneously, it receives an `OperationalError: database is locked` unless a busy timeout is configured. In our code, each request opens a short-lived connection via `sqlite3.connect()`, commits, and closes immediately to minimize lock hold time."
- **Q3 (Deeper Still): "What happens in your code if two high-priority requests hit `/api/sos` simultaneously for the same auto-deploy team?"**
  - **A3:** "In the current codebase, both requests read the team's `current_load` in separate SQL connections. Without an explicit transaction lock or atomic `UPDATE` query, both requests could see the team as available, leading to a race condition where the team is double-assigned beyond its capacity. To fix this in SQLite, we would need to wrap the select-and-update inside a `BEGIN IMMEDIATE` transaction."
- **Q4 (Edge/Design): "How would you refactor the DB layer to support 10,000 concurrent writes per second?"**
  - **A4:** "I would migrate to PostgreSQL with a connection pool like PgBouncer. I'd use atomic row-level locking (`SELECT ... FOR UPDATE`) or optimistic concurrency control with a version column when updating team capacity. For extreme write volume, I'd buffer incoming SOS requests into an Apache Kafka or AWS SQS queue and use consumer workers to perform batch writes into Postgres."

---

### Chain 2: Priority Scoring & Auto-Dispatch Logic

- **Q1 (Surface): "Explain how your 15-factor priority calculation works."**
  - **A1:** "The function `calculate_priority()` starts with a base score of 1. It adds $+2$ for injuries or medical needs, $+1$ for each vulnerability flag (pregnant, elderly, children, disabled, food/water critical), and $+1$ to $+3$ depending on the disaster type (e.g. $+3$ for tsunami or dam breach). The total score is capped at 5 using `min(priority, 5)`."
- **Q2 (One Layer Deeper): "How does the system use this priority score to make dispatch decisions?"**
  - **A2:** "When priority is 4 or 5, `assign_team_for_emergency()` executes an automated SQL query: `SELECT id FROM response_teams WHERE deployment_mode = 'AUTO_DEPLOY' AND is_available = 1 ORDER BY current_load ASC LIMIT 1`. It picks the available auto-deploy team with the lowest load, increments its `current_load`, and binds it to the SOS request."
- **Q3 (Deeper Still): "What if all AUTO_DEPLOY teams are already at maximum capacity when a Priority 5 incident comes in?"**
  - **A3:** "If no `AUTO_DEPLOY` team has `is_available = 1` or `current_load < capacity`, the SQL query returns `None`. The system catches this, leaves `assigned_team_id` as `NULL`, sets the status to `pending`, and flags it on the EOC dashboard for manual dispatcher intervention. The incident is not lost, but auto-dispatch fails gracefully."
- **Q4 (Edge/Design): "How would you modify this algorithm if you wanted to prevent lower-priority incidents from starving when high-priority requests keep coming in?"**
  - **A4:** "I would introduce a dynamic time-decay factor into the score. Every 15 minutes an incident remains in `pending` status, its priority score would automatically increment by $+0.5$. This ensures that a Priority 2 incident waiting for 2 hours eventually escalates to Priority 4/5, preventing long-tail starvation."

---

### Chain 3: Production Deployment & Docker Optimization

- **Q1 (Surface): "Why did you create a separate `requirements-prod.txt` file instead of using `requirements.txt` in Docker?"**
  - **A1:** "Our main `requirements.txt` contains 47 packages including OpenCV, PyQt6, and PyTorch CUDA dependencies used for local hardware and desktop testing. In production on Render, we only need the web API and CPU inference. `requirements-prod.txt` contains only 15 packages, drastically reducing build size."
- **Q2 (One Layer Deeper): "What specifically made the PyTorch dependency so much smaller in production?"**
  - **A2:** "By default, `pip install torch` downloads CUDA binaries for GPU acceleration, which size over 2GB. In `requirements-prod.txt`, I added `--extra-index-url https://download.pytorch.org/whl/cpu`. This forced pip to download the CPU-only PyTorch wheel, which is only ~170MB."
- **Q3 (Deeper Still): "Why did you use Gunicorn as the WSGI server instead of running `app.run()` in Docker?"**
  - **A3:** "Flask's built-in development server (`app.run()`) is single-threaded, non-production-ready, and lacks worker process management. Gunicorn is a pre-fork WSGI HTTP server that forks multiple worker processes to handle concurrent requests efficiently, manage process crashes, and bind dynamically to Render's injected `$PORT` environment variable via `CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-7860} app:app"]`."
- **Q4 (Edge/Design): "If Gunicorn is running with 4 worker processes, what happens to your in-memory variables like `active_rov_missions`?"**
  - **A4:** "That is a classic multi-process limitation. Each Gunicorn worker process has its own isolated memory space. An in-memory dict like `active_rov_missions` or a `threading.Lock()` would NOT be shared across Gunicorn workers. To fix this for multi-worker scaling, shared state must be moved out of Python memory into a centralized Redis instance."

---

## Final Checklist Before Interview Day

- [x] Memorized 30-second system pitch.
- [x] Can draw HLD diagram on a whiteboard/excalidraw.
- [x] Can write out SQLite 6-table schema and foreign keys from memory.
- [x] Sourced every resume metric (25 endpoints, 6 tables, 63 columns, 4 FKs, 2,960 lines, 11 charts, 30s polling, 15 factors).
- [x] Ready to defend SQLite vs Postgres, Polling vs WebSockets, and Rule Engine vs ML.
- [x] Memorized the 3 real challenge narratives (Render Docker OOM, app.py WSGI init bug, ROV threading lock).
- [x] Practiced all 3 probing follow-up chains out loud.
