### TRIDENT (Unified Emergency Command Platform)

**Resume bullet (X-Y-Z):** Containerized and deployed an emergency command platform exposing **25 REST API endpoints** over a **6-table relational schema** (63 columns, 4 foreign keys), implementing a deterministic 15-factor triage engine ($1 \le P \le 5$) that executes **atomic auto-dispatch of response teams for Priority $\ge 4$ incidents**, powering a 2,960-line single-page operational dashboard with 11 Chart.js visualizations.

**Description (2-3 sentences):** TRIDENT is a full-stack emergency command platform consolidating disaster intake, situational awareness, and resource dispatch into a single-page web dashboard. It processes incoming emergency requests through a 15-factor Multi-Criteria Decision Analysis (MCDA) engine, scoring incident severity on a 1–5 scale and atomically dispatching available response teams or autonomous ROVs. The platform includes PyTorch LSTM weather forecasting, graph-based spatial risk propagation, and a containerized Docker/Gunicorn production architecture deployed on Render.

**Be ready to defend:**
- **SQL Query & Indexing:** *Writing a query to create a view for high-priority incidents and explaining JOINs/indexes.*  
  ```sql
  CREATE VIEW high_priority_active_incidents AS
  SELECT 
      s.reference_id, s.name AS victim_name, s.city, s.emergency_type, s.priority, s.status,
      t.team_name, t.deployment_mode, s.created_at
  FROM sos_requests s
  LEFT JOIN response_teams t ON s.assigned_team_id = t.id
  WHERE s.priority >= 4 AND s.status != 'resolved'
  ORDER BY s.priority DESC, s.created_at DESC;
  ```
  *Defense:* A `LEFT JOIN` is used to link `sos_requests.assigned_team_id` to `response_teams.id` so that unassigned high-priority incidents (`assigned_team_id IS NULL`) are preserved in the operational view. To optimize query performance from an $O(N)$ full table scan to $O(\log N)$ B-tree lookups, a composite index is created on `(priority, status, created_at DESC)` in `sos_requests`.
- **ACID Properties:** *Explaining ACID properties with a project-specific example from TRIDENT.*  
  *Defense:* (1) **Atomicity:** When an incident is auto-assigned in `assign_team_for_emergency()`, updating `sos_requests.assigned_team_id`, incrementing `response_teams.current_load`, and inserting an audit record into `sos_assignments` execute as a single atomic transaction block (`conn.rollback()` on failure). (2) **Consistency:** Foreign key constraints (`assigned_team_id REFERENCES response_teams(id)`) enforce schema validity. (3) **Isolation:** SQLite's lock management / WAL mode isolates concurrent team load updates. (4) **Durability:** `conn.commit()` flushes writes to disk (`trident_sos.db`) so state survives server restarts.
- **System Uptime & Container Optimization:** *How uptime and container reliability were ensured during cloud deployment.*  
  *Defense:* The development environment contained 47 dependencies including 2GB+ CUDA PyTorch and desktop GUI libraries (`PyQt6`, `opencv-python`), which caused Render containers to fail with out-of-memory (OOM) errors during build. I created a 15-package production manifest (`requirements-prod.txt`) specifying `--extra-index-url https://download.pytorch.org/whl/cpu` to fetch lightweight CPU-only PyTorch wheels (~170MB), configured a `.dockerignore` file (<1MB build context), and built a 5-step `Dockerfile` deployed via Gunicorn WSGI (`0.0.0.0:${PORT:-7860}`), reducing image footprint by ~80% and bringing container build times under 60 seconds.
- **Triage Algorithm End-to-End:** *How the priority scoring and team dispatch engine works in code.*  
  *Defense:* In `main.py::calculate_priority()`, base priority starts at 1. The function evaluates 15 conditions: $+2$ for injuries (`peopleInjured > 0`), $+2$ for medical emergencies, $+1$ for each vulnerability flag (`pregnant`, `elderly`, `children`, `disabled`), $+1$ for critical food/water scarcity, and $+1 \text{ to } +3$ based on disaster type (`tsunami`/`dam-breach` $= +3$, `flood`/`storm` $= +2$). The score is capped at 5 via `min(priority, 5)`. If priority $\ge 4$, `assign_team_for_emergency()` executes `SELECT id FROM response_teams WHERE deployment_mode = 'AUTO_DEPLOY' AND is_available = 1 ORDER BY current_load ASC LIMIT 1` and atomically binds the team.
- **Database Schema & Normalization:** *Why the schema has 6 tables, 63 columns, and 4 foreign keys.*  
  *Defense:* The schema is normalized into 3NF across 6 tables (`sos_requests`, `response_teams`, `emergency_contacts`, `sos_status_history`, `sos_assignments`, `sos_notes`). Audit logs (`sos_status_history`) and assignments are separated into 1-to-N child tables linked by foreign keys to prevent table locking on `sos_requests`. `sos_requests` contains 27 columns to store victim vitals, 5 vulnerability flags, and geolocations in a flat structure, avoiding multi-table JOIN latency during critical emergency intake.
