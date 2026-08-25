# TRIDENT — TCS Prime Resume Bullets & Technical Defense Guide
**Target Track:** TCS Prime (₹9–11.5 LPA) | **Candidate:** Harshit Singh | **Date:** August 27, 2026

---

### TRIDENT (Unified Emergency Command Platform)

**Resume bullet (X-Y-Z):** Designed and deployed a containerized disaster response platform exposing **25 REST API endpoints** over a **6-table relational schema** (63 columns, 4 foreign keys), implementing a deterministic 15-factor triage engine ($1 \le P \le 5$) that executes **atomic auto-dispatch of response teams for Priority $\ge 4$ incidents**, powering a 2,960-line single-page operational dashboard with 11 Chart.js visualizations.

**Description (2-3 sentences):** TRIDENT is a full-stack emergency command platform consolidating disaster intake, situational awareness, and resource dispatch into a single-page web dashboard. It processes incoming emergency requests through a 15-factor Multi-Criteria Decision Analysis (MCDA) engine, scoring incident severity on a 1–5 scale and atomically dispatching available response teams or autonomous ROVs. The platform includes PyTorch LSTM weather forecasting, graph-based spatial risk propagation, and a containerized Docker/Gunicorn production architecture deployed on Render.

---

### Be Ready to Defend (TCS Prime Question Patterns)

#### 1. SQL Query Writing, Joins, Indexes, and Views
* **Question:** *"Write a SQL query to create a view summarizing high-priority active incidents along with their assigned response team details. Explain the join type and how you would index this table."*
* **Defense / Code:**
  ```sql
  CREATE VIEW high_priority_active_incidents AS
  SELECT 
      s.reference_id,
      s.name AS victim_name,
      s.city,
      s.emergency_type,
      s.priority,
      s.status,
      t.team_name,
      t.deployment_mode,
      s.created_at
  FROM sos_requests s
  LEFT JOIN response_teams t ON s.assigned_team_id = t.id
  WHERE s.priority >= 4 AND s.status != 'resolved'
  ORDER BY s.priority DESC, s.created_at DESC;
  ```
  - **Join Type:** Uses a `LEFT JOIN` linking `sos_requests.assigned_team_id` to `response_teams.id`. A `LEFT JOIN` preserves all high-priority emergency rows even if a team has not yet been assigned (`assigned_team_id IS NULL`), ensuring pending unassigned incidents remain visible to operational dispatchers.
  - **Indexing Strategy:** In `main.py`, queries frequently filter by `priority` and `status` and order by `created_at`. To optimize this query pattern from $O(N)$ full table scans to $O(\log N)$ B-tree lookups, I would create a composite index:
    ```sql
    CREATE INDEX idx_sos_priority_status_created ON sos_requests(priority, status, created_at DESC);
    ```

---

#### 2. Database ACID Properties with Codebase Realities
* **Question:** *"Explain ACID properties using a real-world transaction scenario from TRIDENT."*
* **Defense:**
  - **Atomicity:** When an emergency request is processed by `assign_team_for_emergency()`, updating `sos_requests.assigned_team_id`, incrementing `response_teams.current_load`, and inserting a record into `sos_assignments` must occur as a single atomic unit. If incrementing the team load fails, the entire transaction rolls back via `conn.rollback()` so no orphan assignments exist.
  - **Consistency:** Database schema constraints (e.g., `FOREIGN KEY (assigned_team_id) REFERENCES response_teams(id)`, `NOT NULL` on `reference_id`, and `CHECK` constraints) guarantee the database transitions only between valid states.
  - **Isolation:** SQLite handles isolation using database lock modes (or Write-Ahead Logging). During `BEGIN IMMEDIATE` or serializable write transactions, concurrent request threads cannot read partially updated team loads.
  - **Durability:** Once `conn.commit()` succeeds, the transaction log is flushed to disk (`trident_sos.db`), ensuring emergency data persists even if the server crashes immediately after.

---

#### 3. Database Schema & Normalization (6 Tables, 63 Columns, 4 Foreign Keys)
* **Question:** *"Walk me through your database schema. Why did you split it into 6 tables, and why does `sos_requests` have 27 columns?"*
* **Defense:**
  - **Schema Breakdown (6 Tables):** `sos_requests` (27 cols), `response_teams` (12 cols), `emergency_contacts` (8 cols), `sos_status_history` (6 cols), `sos_assignments` (5 cols), `sos_notes` (5 cols).
  - **4 Foreign Keys:** (1) `sos_requests.assigned_team_id → response_teams.id`, (2) `sos_status_history.reference_id → sos_requests.reference_id`, (3) `sos_assignments.reference_id → sos_requests.reference_id`, (4) `sos_notes.reference_id → sos_requests.reference_id`.
  - **Normalization Justification:** The schema is normalized into 3NF. Audit logs (`sos_status_history`), assignment tracking (`sos_assignments`), and notes (`sos_notes`) are decoupled into separate 1-to-N child tables. This prevents table lock contention on `sos_requests` during status updates.
  - **27 Columns in `sos_requests`:** It captures victim demographics, location, casualty counts, 5 boolean vulnerability flags (`pregnant`, `elderly`, `children`, `disabled`, `medical`), resource scarcity states (`food`, `water`), and scoring metrics in a flat row to allow single-query ingestion without multiple JOIN bottlenecks during intake.

---

#### 4. End-to-End Triage & Auto-Dispatch Logic
* **Question:** *"How does the priority scoring algorithm work end-to-end, and how is team auto-dispatch triggered?"*
* **Defense:**
  - **Scoring Engine (`calculate_priority()`):** Base score starts at `1` (Low). Adds $+2$ for injuries (`peopleInjured > 0`), $+2$ for medical emergencies (`medical == 'true'`), $+1$ for each vulnerability flag (`pregnant`, `elderly`, `children`, `disabled`), $+1$ for critical resource scarcity (`food` or `water` equal to `'none'`/`'critical'`), and $+1 \text{ to } +3$ based on disaster type (`tsunami`/`dam-breach` $= +3$, `flood`/`storm` $= +2$). The score is capped at 5 via `min(priority, 5)`.
  - **Auto-Dispatch Threshold ($P \ge 4$):** If calculated priority is 4 or 5, `assign_team_for_emergency()` executes:
    ```sql
    SELECT id, team_name FROM response_teams 
    WHERE deployment_mode = 'AUTO_DEPLOY' AND is_available = 1 
    ORDER BY current_load ASC LIMIT 1;
    ```
    It selects the available `AUTO_DEPLOY` team (e.g., `Team Alpha`) with the lowest workload, increments `current_load`, updates `assigned_team_id`, and sets incident status to `'assigned'`. If $P \le 3$, assignment remains `NULL` for manual dispatch.

---

#### 5. System Reliability, Docker Optimization, and Cloud Deployment
* **Question:** *"How did you ensure system reliability, avoid cloud container memory crashes, and deploy the full stack?"*
* **Defense:**
  - **Docker Build Optimization:** Development dependencies (`requirements.txt`, 47 packages) included CUDA PyTorch (~2GB), desktop GUI tools (`PyQt6`, `pyqtgraph`), and OpenCV, which caused Render cloud container builds to crash due to out-of-memory (OOM) limits (512MB RAM).
  - **Production Manifest (`requirements-prod.txt`):** Reduced dependencies to 15 packages and specified CPU-only PyTorch wheels: `--extra-index-url https://download.pytorch.org/whl/cpu`. This replaced the 2GB CUDA package with a ~170MB CPU PyTorch wheel, shrinking container build size by ~80%.
  - **Context Minimization:** Authored `.dockerignore` to exclude local virtual environments (`venv/`), `.git/`, `.pio/`, and `*.db`, reducing Docker build context from ~200MB to <1MB.
  - **WSGI Process Management:** Deployed using a 5-step `Dockerfile` with `python:3.10-slim` base image, bound to Render's dynamic `$PORT` via Gunicorn WSGI (`CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-7860} app:app"]`), bringing production build time under 60 seconds.

---

### TRIDENT Technical Metric Quick-Reference

| Metric / Feature | Codebase Truth & Verification |
|---|---|
| **REST Endpoints** | **25 endpoints** (18 GET, 5 POST, 2 PUT) — verified via `@app.route` count in `src/backend/main.py`. |
| **Relational Schema** | **6 tables, 63 columns, 4 foreign keys** — initialized in `init_database()` ([main.py:63-163](file:///home/harshit/Documents/projects-all/trident/src/backend/main.py#L63-L163)). |
| **Single-Page Dashboard** | **2,960 lines** in `platform.html` — 3 tab panes, 29 inline JS functions, 9 `fetch()` routes. |
| **Data Visualizations** | **11 Chart.js instances** across 9 distinct charts (Doughnut, Bar, Line, Multi-axis). |
| **Real-Time Polling** | **30-second interval** (`setInterval(..., 30000)` in `dashboard.js`). |
| **Priority Factors** | **15 weighted conditions** evaluated in `calculate_priority()` (score bounded $1 \le P \le 5$). |
| **Containerization** | **5-step Dockerfile**, 15-package `requirements-prod.txt` (~80% size reduction), Gunicorn WSGI. |
