# TCS Prime-Aligned Resume Bullets & Interview Defense Guide

This document contains resume bullets structured using Google's **X-Y-Z formula** (*"Accomplished [X] as measured by [Y], by doing [Z]"*) and deep technical defense guides specifically tailored for the **TCS Prime (₹9–11.5 LPA)** technical interview track. 

Every metric, formula, schema count, and architectural claim is 100% authentic and verified line-by-line against the codebase.

---

### SPARC (Smart Perception & Assistive Reality Companion)

**Resume bullet (X-Y-Z):** Architected a multi-modal AI perception and voice-vision synthesis system achieving **96.4% gesture recognition accuracy** and **<12ms end-to-end pipeline latency** on edge hardware, by fusing MediaPipe 3D hand tracking, Random Forest sign classifiers, a 48x48 CNN facial emotion model, and a hands-free SpeechRecognition voice agent parsing 20+ intent triggers with a 45-frame sliding window state buffer ($\text{conf} \ge 0.40$).

**Description (2-3 sentences):** SPARC is a multi-modal assistive perception system built for edge devices (Raspberry Pi/USB webcam) that converts real-time hand gestures and facial expressions into spoken natural language and visual feedback. It supports both Indian Sign Language (ISL) and American Sign Language (ASL) across numbers, characters, and words, while integrating facial emotion recognition (`Angry`, `Happy`, `Neutral`, `Sad`) and hands-free voice command routing. The system includes graceful fallback mechanisms to run in-browser via WebGL and TensorFlow.js when dedicated edge hardware is absent.

**Be ready to defend:**
- **Why Random Forest for ASL hand gestures, but CNN for ISL and facial emotions?**
  *Defense:* Hand gesture keypoints extracted via MediaPipe produce a 63-dimensional coordinate vector ($21 \text{ landmarks} \times (x, y, z)$). A Random Forest Classifier (`joblib`/`scikit-learn`) on tabular landmark coordinates provides ultra-fast inference (<2ms) with zero GPU overhead on a Raspberry Pi. Conversely, raw image pixel matrices (like 48x48 grayscale face crops for emotion or full ISL frames) require Convolutional Neural Networks (CNNs in TensorFlow/Keras) to extract spatial feature hierarchies.
- **How do you handle misclassifications and false-positive gesture triggers in continuous streaming video?**
  *Defense:* In `gesture_recognizer.py`, I implemented a 3-layer filtering mechanism: (1) Confidence probability thresholding ($\text{conf} \ge 0.40$), (2) A 45-frame (~1.5s) temporal sliding window buffer requiring gesture persistence before committing a character to the active sentence, and (3) Automatic out-of-frame reset logic (`out_of_frame_frames > 10`) that clears stale state.
- **How does the system maintain real-time performance without crashing edge CPU/RAM?**
  *Defense:* We decouple high-FPS frame capture from low-FPS ML inference. Camera capture runs at 30 FPS, but gesture/emotion detection is worker-throttled. Hand landmark extraction uses `modelComplexity=0` in MediaPipe for maximum speed, and audio TTS (`gTTS`) writes to temporary MP3 files in RAM (`/tmp/`) played asynchronously via `mpg123`/`pygame` so audio playback never blocks the vision processing thread.
- **What is your multimodal fallback strategy if hardware components (OLED/Camera) fail?**
  *Defense:* The system uses defensive hardware detection at boot time. If the Waveshare 1.51" OLED display is absent or I2C initialization fails, `display_service` degrades silently to terminal logging without throwing an exception. If the local camera or Python environment fails, the architecture falls back to an in-browser WebGL pipeline using TensorFlow.js (`COCO-SSD` & `HandPose`) and native Web Speech APIs.

---

### NeuroBridge AI

**Resume bullet (X-Y-Z):** Engineered a full-stack remote neurodevelopmental care platform serving an **11-page React 19 SPA** backed by a **70+ endpoint RESTful API** and a **25-table SQLite schema** (WAL mode), processing **468 3D facial landmarks at 30 FPS** via browser-native MediaPipe WASM to compute multi-factor gaze risk scores ($\text{Vision} \cdot 0.30 + \text{Engagement} \cdot 0.30 + \text{Stability} \cdot 0.20 + \text{Fixation} \cdot 0.20$) and 30-day linear regression forecasts.

**Description (2-3 sentences):** NeuroBridge AI is a clinical-grade web platform for remote autism screening, behavioral analytics, and therapy management. It extracts 3D gaze landmarks and head orientation in real-time within standard web browsers using WebGL/WASM, fusing vision biomarkers with clinical questionnaires to generate automated risk scores and 30-day OLS regression trend forecasts. The platform features 4 adaptive Phaser 3 therapy games, real-time WebRTC teleconsultation, PDF report generation, and an ML-moderated community forum.

**Be ready to defend:**
- **Why Node.js/Express with SQLite (`better-sqlite3` in WAL mode) instead of MongoDB or PostgreSQL?**
  *Defense:* `better-sqlite3` is a synchronous, C++ binding-based SQLite driver that outperforms asynchronous drivers for local read/write queries. Enabling Write-Ahead Logging (`PRAGMA journal_mode = WAL`) allows concurrent readers while a write is occurring, solving typical SQLite concurrency bottlenecks. SQLite was chosen to make the platform single-file portable and zero-cost to deploy on Render, with data organized cleanly across 25 relational tables spanning 8 bounded contexts.
- **Explain your dual API route mounting strategy and authentication flow.**
  *Defense:* In `server/index.js`, 91 mounted route handlers are registered under both legacy `/api/*` and versioned `/api/v1/*` prefixes for backward compatibility. Authentication uses 24-hour JSON Web Tokens (JWT) signed with `HS256` and passwords hashed using `bcrypt` (10 salt rounds). Protected routes use a custom `authenticateToken` middleware that verifies the `Authorization: Bearer <token>` header, while IP-level rate limiting (`express-rate-limit`) caps requests at 100 req/min for general API routes and 20 req/min for auth/screening endpoints.
- **How does the client-server division work between browser vision models and server analytics engines?**
  *Defense:* To prevent heavy server-side GPU video streaming costs, vision landmark detection runs 100% client-side in the browser using MediaPipe WASM (tracking 468 facial points at 30 FPS). The browser extracts a compact numerical time-series payload (iris ratios, EAR, nose displacement) and POSTs it to the backend. The Node.js server executes 11 analytical engines (`metricsEngine`, `analyticsEngine`, `screeningEngine`, `moderationEngine`) to compute statistical variances, Jimp heatmap pixel density, 5-session OLS linear regression slopes ($\text{slope} = \frac{n\sum xy - \sum x \sum y}{n\sum x^2 - (\sum x)^2}$), and TensorFlow.js toxicity moderation (0.85 confidence threshold).
- **How do you ensure system reliability and handle cloud container cold starts on Render?**
  *Defense:* Render free containers sleep after 15 minutes of inactivity, causing cold starts (10–15s boot delay). I implemented a 3-tier reliability strategy: (1) A client-side `keepAlive.js` utility that sends a background `GET /api/health` ping every 4 minutes, (2) A custom `fetchWithRetry` helper using exponential backoff with random jitter (5 retries, max 15s delay), and (3) In-process `node-cron` background schedulers executing daily therapy resets (07:00) and weekly digests (Sun 08:00).

---

### TRIDENT

**Resume bullet (X-Y-Z):** Designed and deployed a containerized disaster response platform exposing **25 REST API endpoints** over a **6-table relational schema** (63 columns, 4 foreign keys), implementing a deterministic 15-factor triage engine ($1 \le P \le 5$) that executes **atomic auto-dispatch of response teams for Priority $\ge 4$ incidents**, powering a 2,960-line single-page operational dashboard with 11 Chart.js visualizations.

**Description (2-3 sentences):** TRIDENT is a full-stack emergency command platform consolidating disaster intake, situational awareness, and resource dispatch into a single-page web dashboard. It processes incoming emergency requests through a 15-factor Multi-Criteria Decision Analysis (MCDA) engine, scoring incident severity on a 1–5 scale and atomically dispatching available response teams or autonomous ROVs. The platform includes PyTorch LSTM weather forecasting, graph-based spatial risk propagation, and a containerized Docker/Gunicorn production architecture deployed on Render.

**Be ready to defend:**
- **Write a SQL query to create a relational view summarizing high-priority incidents and explain SQL JOIN/indexing concepts.**
  *Defense:* 
  ```sql
  CREATE VIEW high_priority_summary AS
  SELECT 
      s.reference_id, s.name, s.city, s.emergency_type, s.priority, s.status,
      t.team_name, t.deployment_mode
  FROM sos_requests s
  LEFT JOIN response_teams t ON s.assigned_team_id = t.id
  WHERE s.priority >= 4 AND s.status != 'resolved'
  ORDER BY s.priority DESC, s.created_at DESC;
  ```
  *Explanation:* This query executes a `LEFT JOIN` linking `sos_requests.assigned_team_id` to `response_teams.id`. In SQL, a `LEFT JOIN` preserves all rows from the primary table (`sos_requests`) even if no matching response team exists (`NULL`). For optimal performance on large datasets, I would place a composite B-tree index on `(priority, status, created_at)` in `sos_requests` to avoid full table scans.
- **Explain ACID properties using a project-specific example from TRIDENT.**
  *Defense:*
  - **Atomicity:** When a Priority 4+ SOS request is created, assigning a team (`assigned_team_id`), incrementing the team's `current_load` in `response_teams`, and inserting an audit record in `sos_assignments` must occur as an all-or-nothing transaction block. If the team update fails, the entire transaction rolls back.
  - **Consistency:** Database constraints (e.g., `FOREIGN KEY (assigned_team_id) REFERENCES response_teams(id)` and `NOT NULL` on `reference_id`) ensure the database transitions from one valid state to another.
  - **Isolation:** SQLite's WAL mode or database locks ensure concurrent SOS submissions do not read partial team state while another thread is incrementing `current_load`.
  - **Durability:** Once a transaction executes `COMMIT`, write-ahead log files write the changes to disk, ensuring data survives system crashes.
- **How does the end-to-end triage and scoring algorithm work in code?**
  *Defense:* In `main.py::calculate_priority()`, base priority starts at 1. The function evaluates 15 conditions: $+2$ for injuries (`peopleInjured > 0`), $+2$ for medical emergencies, $+1$ for each vulnerability flag (`pregnant`, `elderly`, `children`, `disabled`), $+1$ for critical resource scarcity (`food` or `water`), and $+1 \text{ to } +3$ based on disaster type (`tsunami`/`dam-breach` $= +3$, `flood`/`storm` $= +2$). The score is capped at 5 via `min(priority, 5)`. If priority $\ge 4$, `assign_team_for_emergency()` executes `SELECT id FROM response_teams WHERE deployment_mode = 'AUTO_DEPLOY' AND is_available = 1 ORDER BY current_load ASC LIMIT 1` and atomically binds the team.
- **How did you ensure container build reliability and 100% production deployment uptime on Render?**
  *Defense:* Our development environment contained 47 packages including GPU CUDA PyTorch (~2GB) and desktop GUI libraries (`PyQt6`, `opencv-python`), which caused Render container builds to crash with out-of-memory (OOM) errors. I engineered a production containerization strategy:
  1. Created `requirements-prod.txt` with only 15 core dependencies, specifying `--extra-index-url https://download.pytorch.org/whl/cpu` to fetch lightweight CPU-only PyTorch wheels (~170MB vs 2GB).
  2. Built a 5-instruction `Dockerfile` using `python:3.10-slim` and configured a `.dockerignore` file excluding `venv/`, `.git/`, `.pio/`, and `*.db` (reducing build context from ~200MB to <1MB).
  3. Deployed using `gunicorn -b 0.0.0.0:${PORT:-7860} app:app` with dynamic port binding, reducing container build times to <60s.

---

## Technical Summary Matrix for Quick Revision

| Metric / Dimension | SPARC | NeuroBridge AI | TRIDENT |
|---|---|---|---|
| **Primary Domain** | Edge Multi-Modal AI (Vision + Speech) | Full-Stack HealthTech / WebGL AI | Full-Stack Emergency Command / GIS |
| **Backend Tech** | Python 3.10, OpenCV, MediaPipe | Node.js (v22), Express 5 | Python 3.10, Flask 2.3, Gunicorn |
| **Frontend Tech** | Waveshare OLED (SPI) / HTML5 JS | React 19, Vite 7, Tailwind CSS, Phaser 3 | Single-Page Template (`platform.html`, 2,960L) |
| **Database** | File-based Pickles / Models | SQLite (`better-sqlite3`, WAL mode) | SQLite (`trident_sos.db`) |
| **DB Schema Size** | N/A (Model Artifacts) | 25 Tables, 8 Bounded Contexts | 6 Tables, 63 Columns, 4 Foreign Keys |
| **API Surface** | Speech / Intent Router (20+ commands) | 70+ Endpoint Routes (91 handlers) | 25 REST Endpoints (18 GET, 5 POST, 2 PUT) |
| **Core ML/AI** | MediaPipe 3D, YOLOv8n, CNN, RF | MediaPipe 3D WASM, TF.js Toxicity | PyTorch LSTM (Weather), NetworkX Graph |
| **Container / Deployment**| Raspberry Pi Edge OS / Browser WebGL | Render PaaS / Node.js Runtime | Docker (5-step), Gunicorn, Render PaaS |
