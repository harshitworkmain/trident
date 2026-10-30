# TRIDENT: career notes (resume bullets and interview prep)

Replaces the old `AI_ENGINEER_RESUME_DESCRIPTION.md`, `DATA_ENGINEER_RESUME_DESCRIPTION.md`,
`RESUME_PROJECT_DESCRIPTION.md` and `interview_prep_trident.md`. Those described the old system (Flask,
an 8-state synthetic XGBoost classifier, a Kaggle tournament, a temperature-only LSTM, NetworkX graph
demos). None of that is in the current system, so don't put it on a resume.

Every number here comes from these files. Check them before an interview:
`docs/WEARABLE_ML_SUBPROJECT_CONTEXT.md` §7, `docs/WEARABLE_ML_ARCHITECTURE.md`,
`docs/reports/MODEL_TOURNAMENT_RESULTS.md`, `docs/reports/WEARABLE_FINAL_MODELS.md`,
`docs/reports/WEARABLE_FUSION_REPLAY.md`, `docs/reports/WEARABLE_RHYTHM_PPG_AF_TEST.md`,
`docs/WEATHER_MODEL.md`, `docs/PLATFORM_DESIGN.md`, `docs/RESILIENCE_AND_FUTURE_WORK.md`,
`src/firmware/README.md`, `src/backend/README.md`, `src/cv/vision/pipeline.py`.

---

## 1. Project summary (3 lines)

TRIDENT is a disaster-response command platform: public SOS intake (web PWA, SMS, wearable button), triage and capacity-aware dispatch, ROV missions with a live computer-vision feed, and a weather/flood-risk forecaster.
Its ESP32 wrist wearable streams 1.5 s telemetry frames into a hybrid ML pipeline: five Tier-1 heads trained only on real public datasets, plus a deterministic Tier-2 fusion state machine that opens alerts.
The stack is FastAPI + SQLAlchemy/Alembic (SQLite WAL, PostgreSQL-ready) + React/Vite/TypeScript, with ONNX-served models, JWT/RBAC, WebSockets and 127 passing tests.

**Resume header:** *TRIDENT: Disaster-Response Platform with Wearable ML, Fusion Alerts and Probabilistic Weather Forecasting*.
*Python, PyTorch, scikit-learn, LightGBM/XGBoost, ONNX Runtime, Optuna, MLflow, FastAPI, SQLAlchemy, Alembic, React, TypeScript, WebSockets, ESP32 (FreeRTOS, PlatformIO), YOLOv8, OpenCV*

---

## 2. Resume bullets

Pick 4–5 per role. The parentheses at the end of each bullet say where the numbers come from; delete them on the resume.

### A. ML / AI engineer

- I replaced a synthetic-label 8-class wearable classifier with a hybrid architecture: five Tier-1 heads (stress, fall, activity, heart-rate trust, rhythm) trained only on real public datasets, and a rule-based Tier-2 fusion state machine for states that have no public data. (Architecture doc; context log, Architecture v2)
- I ran a 3-stage model tournament for each head: logistic-regression baseline vs XGBoost, LightGBM, Extra-Trees, MLP, 1D-CNN and a MiniRocket I implemented in numpy. It used 5-fold subject-grouped CV, nested Optuna tuning and subject-bootstrap CIs to pick winners. Rhythm macro-F1 went from 0.752 to 0.932 and stress from 0.885 to 0.935. (Tournament report; final models)
- I cut fall-detector false alarms on 1,403 h of real daily life from people the model never saw. Tier-1 alone went from 119 per 8 h (v1 baseline) to 2.1 through label-free hard-negative mining on 561k windows from 190 subjects. A post-impact stillness rule in fusion then got held-out critical alarms down to 1.20 per 8 h while still catching 84.6 % of external HIFD falls. (Context log P3, P4, P5; fusion replay)
- I calibrated every head out of fold (Platt or temperature scaling, cross-fitted by subject), which cut ECE by 2–5x (for example, stress 0.023 to 0.008). I picked operating thresholds with pre-registered rules, such as "most sensitive with at most 1 false alarm per 8 h" for falls. (Final models report)
- I exported every model to ONNX with a parity check on 4,000 rows (max |Δp| ≤ 1.2e-6, 0 argmax flips). Large Extra-Trees forests are also served as compiled numpy arrays (≤ 3e-7 difference, 0 flips), so loading all heads takes 0.5 s instead of about 9 min. (Context log P4, P5)
- I validated the ECG-trained rhythm head on real PPG from an external ICU dataset it never saw (35 patients, 6,685 windows): window AUROC 0.987 and macro-F1 0.938 at the unchanged threshold. I separated model error from beat-detection error using an ECG reference run. (Rhythm PPG AF report)
- I built a 1–48 h probabilistic weather forecaster (p10/p50/p90 for 5 variables) using direct LightGBM quantile regression blended with a GRU exported to ONNX, plus split-conformal calibration. On a 12-month rolling-origin backtest it beat persistence and seasonal-naive at every horizon (6 h temperature MAE 0.69 °C vs 2.71 °C for persistence). (Weather model doc §3)

### B. Data / ML-platform engineer

- I built a reproducible wearable data pipeline: 12 public datasets registered with SHA-256 manifests, compacted losslessly to per-subject `.npz` (SisFall verified value for value on 4,505/4,505 trials before the raw copy was deleted), and read zips in place to fit an 8 GB-RAM machine. (Context log §3, P1)
- I wrote a device emulator that turns raw research recordings into the exact 1.5 s frames the ESP32 sends. Training tables are built by replaying those frames through the same online `FeatureEngine` used in serving, and a test asserts bit-identical features from JSON parse to feature vector for all 6 feature sets. (Architecture decision 6)
- I prevented subject leakage everywhere: StratifiedGroupKFold by subject, nested inner CV for tuning, records 201/202 grouped as one patient, and a stable SHA-256 hash split that held out a third of Capture-24 participants (55 people) for false-alarm replay only. (Architecture decisions 8, 12, 16)
- I tested data decisions empirically instead of assuming them. Pooling Stress-Predict lowered WESAD stress F1 from 0.885 to 0.834, and pooling PAMAP2 lowered PPG-DaLiA activity F1 from 0.90 to 0.83 (opposite label semantics at the wrist), so both became external tests only. (Architecture decision 14; context log P3 v2)
- I built and validated an ECG R-peak detector as the heart-rate ground truth (98.7–99.3 % sensitivity, about 99.5 % precision, median HR error under 0.5 bpm against PPG-DaLiA's reference). It extended the HR-trust dataset to 72,003 windows from 30 subjects. (Context log §3.C item 11)
- I set up experiment tracking and a model registry: MLflow runs, an auto-generated tournament report, and `registry.json` with an ONNX model, model card, metrics, calibration and golden inputs/outputs for each head. 96/96 model-file hashes were verified in QA. (Architecture §11; context log QA)
- I designed weather training without leakage: 103,560 hourly ERA5 rows (2015–2026), causal features tested by truncation and future-poisoning, separate calibration and test slices in time order, and backtests run through the same predictor code path as serving. (Weather model doc §1–2)

### C. Backend / full-stack / systems engineer

- I rewrote a single-file Flask app as a FastAPI + SQLAlchemy 2 + Alembic service with a React/Vite/TypeScript console. Each command commits as one ACID transaction, dispatch uses optimistic locking (stale version returns 409) and a server-enforced SOS state machine, and the database moves from SQLite (WAL) to PostgreSQL by changing one URL. (Platform design §1)
- I applied CAP choices per data type. Dispatch is consistency-first (503 rather than an uncommitted write). Telemetry is availability-first: frames are de-duplicated on (device, boot, seq) and SOS submissions carry an Idempotency-Key, so offline replays never create duplicates. (Platform design §1; backend README)
- I implemented auth and multi-replica safety: 15-min HS256 access JWTs, rotating refresh tokens whose reuse revokes the whole token family, 4-role RBAC, hashed per-device keys, a scheduler with DB-lease leader election, and a WebSocket hub with per-topic sequence numbers for gap detection. (Platform design §1)
- I ran a full QA round: security review of 52 endpoints x 5 roles, load and failure injection (dispatch races, 20 devices x 5 min, kill -9, a 20-min soak), and accessibility checks with axe. I fixed 2 high and 5 medium security issues, 12 load/failure defects and 7 UI bugs, and took serious axe violations from 4 to 0. 127 tests pass. (Context log QA)
- I wrote FreeRTOS ESP32 firmware (sensor task on core 1, network task on core 0) with real SpO2, RR intervals and a 320-frame (8 min) offline queue that keeps event frames when full, plus batched acks and an SOS button. The build uses 34.1 % RAM and 53.1 % flash. (Firmware README)
- I built degraded-mode features: an offline-capable PWA SOS form, an SMS intake webhook, LOST_CONTACT alerts, a 5 s ROV thruster cut-off when the control room drops, urgency-ordered auto-dispatch, priority ageing (+2 per 5 min, cap 20), and duplicate linking (same phone, or within 100 m in 2 h). (Resilience doc §1–2)
- I integrated an ROV camera worker (YOLOv8n + Haar/LBPH + pinhole distance) into the API through a vision key, single-use 60 s stream tickets and an MJPEG relay, with live detections on the missions page. (Platform design §5; `src/cv/vision/pipeline.py`)

---

## 3. Technical deep-dive Q&A

### Architecture and ML

**Q1. Why a hybrid architecture instead of one classifier?**
The v1 design was a single 8-class model, and 5 of the 8 states had only generator-made labels, so the model could never be validated. v1 firmware even simulated SpO2. In v2, real data trains small independent heads (stress, fall, activity, HR-trust, rhythm). States with no public data (cardiac arrest, hypoxia, haemorrhagic shock, hypothermia) are explicit, versioned rules in a fusion state machine. Every output says whether its basis is `ml`, `rule` or `ml+rule`, plus its evidence.

**Q2. How did the tournament pick winners?**
For each head there were three stages. (1) Screening: every candidate with default hyperparameters, run under 5-fold StratifiedGroupKFold by subject. (2) The top two get 40-trial Optuna tuning with 3-fold inner CV inside each training fold (nested, no leakage). (3) The final compares them with a 1,000-resample subject-bootstrap CI on the macro-F1 difference. If the CI includes 0, the smaller/faster model wins. A soft-vote of the two finalists is adopted only if its CI against the single winner excludes 0. The logistic-regression baseline advances if it finishes in the top two.

**Q3. Which models won, and why so many different ones?**
Stress: MiniRocket (0.935). HR-trust: soft-vote of 1D-CNN and Extra-Trees (0.768). Rhythm: 1D-CNN (0.932, AUROC 0.977). Activity: Extra-Trees (0.801). Fall: soft-vote of Extra-Trees and 1D-CNN (0.867, AUROC 0.994). Each task has different data and signals, so "one winner" means one winner per head. In v1 the logreg baseline actually won stress and rhythm, which is why the rules let it advance instead of excluding it for being simple.

**Q4. Why subject-grouped CV?**
Windows from the same person are highly correlated. A random split would score the model on people it trained on and inflate every number. Every reported metric is out of fold on subjects the scoring model never saw, and the CIs come from resampling subjects, not windows.

**Q5. How did you calibrate and choose thresholds?**
Calibration was fitted on out-of-fold predictions and cross-fitted by subject: Platt scaling for the binary heads, temperature scaling for activity. ECE dropped for every head, for example fall 0.006 to 0.001 and stress 0.023 to 0.008. Thresholds follow pre-registered rules, decided before seeing the result. For the fall head the rule was "most sensitive threshold with at most 1 false alarm per 8 h on out-of-fold daily life", which gave 0.72.

**Q6. Fall false alarms were the hardest problem. What happened?**
v1 looked great on lab data (macro-F1 0.972) but gave 119 false alarms per 8 h on real daily life, because scripted lab ADLs don't cover real motion. In v2 I added daily-life negatives with label-free hard-negative mining (a window every 30 s plus every motion spike ≥ 1.8 g or ≤ 0.4 g, capped at 1,500 per person) and held out 55 Capture-24 participants (1,403 h) purely for replay. At 0.72, Tier-1 gives 2.1 false alarms per 8 h on that held-out set. Fusion then requires 30 s of immobility after the impact and runs the fall head at 0.6: held-out critical alarms are 1.20 per 8 h and 84.6 % of external HIFD falls reach CONCUSSIVE_STASIS (61.5 % at 0.72).

**Q7. Why is the fall head accelerometer-only?**
Most daily-life negative sources have no gyroscope. If falls have gyro data and negatives don't, the model learns "gyro missing means no fall". In v1 the gyro added only about 0.004 macro-F1. The firmware still sends gyro data for future use.

**Q8. Explain ONNX parity and the compiled forests.**
Training ran on Python 3.13 / numpy 2.x and production on Python 3.10, so ONNX is the only artefact format shared between them; nothing is pickled. Every export was checked on 4,000 rows: max |Δp| ≤ 1.2e-6 (MiniRocket 5.4e-3), 0 argmax flips. Then a serving problem appeared: onnxruntime 1.22 took about 280 s to load the HR-trust Extra-Trees (73 MB, 1.9 M nodes), and load time grew linearly with node count. I stored tree members as numpy arrays derived from the ONNX and parity-checked them against it (≤ 3e-7, 0 flips). All heads now load in 0.5 s. ONNX remains the canonical artefact.

**Q9. How does the fusion state machine work?**
It is deterministic and runs per device. Each state has an enter condition, a dwell time and exit hysteresis, and the most severe true state wins. All thresholds are in a versioned `fusion.yaml`. Examples: CONCUSSIVE_STASIS needs a fall event (p ≥ 0.6) and then ≥ 30 s of immobility. CRUSH_ENTRAPMENT needs HR ≥ 20 bpm above the personal baseline plus either ≥ 120 s of stillness within 10 min of an impact or ≥ 300 s of stillness. ELEVATED_STRESS is advisory only. A SENSOR_FAULT overlay suppresses cardiac rules when contact is lost or the battery is low.

**Q10. How did you validate fusion without trauma data?**
Synthetic scenarios are used only as unit tests of the rules. The real check is a replay of the full serving path over real recordings: PPG-DaLiA, WESAD, PAMAP2, Stress-Predict and 1,403 h of held-out Capture-24, where every critical state is by definition a false alarm. Final critical alarms per 8 h: 0.67, 0.33, 2.24, 0.51 and 1.20. On WESAD, ELEVATED_STRESS fires 86 % of the time in the stress phase and 0 % at baseline. The replay also found a bug: `bool(nan)` is True, so missing water flags made every wearer look wet. Fixing it took hypothermia alarms from 118 to 2.

**Q11. How do you guarantee training-serving parity?**
Head training tables are produced by replaying emulated frames one by one through the online `FeatureEngine`, the same code the server runs. A test pushes frames through JSON, `parse_payload` and the engine and asserts bit-identical features for all six feature sets. Personal baselines use only the first 2 min of past frames, both offline and online. Streaming replay and batched replay are tested to agree.

**Q12. What does the device emulator do?**
It turns any raw recording into schema-2 frames: it resamples the IMU to 50 Hz (anti-aliased), computes 1.5 s max/min/mean/std and tilt, detects beats with the firmware's own RR logic (valid intervals 270–2000 ms), converts EDA to µS, and sets fields the dataset lacks to NaN. Rhythm training uses ECG RR made PPG-like with noise calibrated on PPG-DaLiA (median RR error 58 ms, beat-count ratio 0.96–1.03).

**Q13. Did the ECG-trained rhythm head work on PPG?**
On MIMIC PERform AF (35 ICU adults, fingertip PPG, never trained on): window AUROC 0.987, sensitivity 0.936 and specificity 0.941 at the unchanged 0.61 threshold, subject AUROC 1.0. On the ECG R-peak reference run, window AUROC was 1.000. So the remaining PPG errors come from missed beats looking irregular, not from the model. Caveats: fingertip is not wrist, and n = 35.

**Q14. How does the weather forecaster work?**
It forecasts 5 variables (temperature, RH, rain, wind, pressure) at 1–48 h as p10/p50/p90. The candidates were persistence, seasonal-naive, climatology, direct LightGBM quantile regression (75 boosters across variable x horizon group x quantile, plus 3 for 24 h rain), a GRU exported to ONNX (1.4e-6 parity), and an LGBM+GRU blend. A rolling-origin backtest covers the final 12 months (2,905 origins). Quantiles are calibrated with split-conformal offsets from a separate 6-month slice, and the model for each band is chosen on that slice, never on the test year.

**Q15. How good is the weather model, honestly?**
Learned models beat every baseline at every horizon. Temperature at 6 h has MAE 0.69 °C vs 2.71 °C for persistence (skill 0.75) and 0.87 °C for seasonal-naive. At 24–48 h the skill over seasonal-naive is only +0.07 to +0.16. Coverage went from about 0.73 raw to about 0.80, but wind and 48 h pressure are under-covered (0.72–0.77). Heavy hourly rain is essentially unpredictable (CSI 0.15 at 1–3 h). The flood output is an antecedent-precipitation risk index, not an inundation forecast. The natural v2 is adding NWP forecasts as features.

**Q16. How does the CV pipeline work?**
YOLOv8n detects objects with confidence ≥ 0.4, and people are kept (in a rescue they are the point). A Haar cascade finds faces at scale step 1.1, and an LBPH recognizer matches enrolled responders when the LBPH distance is below 50. Distance uses the pinhole model D = W_real x f / w_px with per-class real widths and f = 700 px at 640 px width. It is labelled approximate (±30 % at best) and needs per-camera calibration. The worker runs outside the API process and posts annotated JPEGs with a vision key. The browser views them through single-use 60 s tickets as MJPEG.

### Platform and systems

**Q17. Where did you choose consistency vs availability?**
SOS requests, assignments, team capacity and alerts are CP: two dispatchers must never send the same team twice, so writes are ACID with optimistic locking, and an unreachable DB returns 503 instead of accepting a write it can't commit. Telemetry is AP: the device never blocks on the server, buffers offline, and the server de-duplicates. The WebSocket is best effort and never the source of truth.

**Q18. Walk through the ACID and concurrency design.**
Creating an SOS (plus history and audit rows), assigning a team (SOS, assignment, team load, history) and opening an alert each commit in one transaction, and events are published only after commit. `version` is incremented on every update, and a stale version returns 409 with the current record. SOS transitions (pending → triaged → assigned → en_route → on_scene → resolved, or cancelled) are enforced in the service layer. SQLite uses WAL and `BEGIN IMMEDIATE`; PostgreSQL uses `SELECT … FOR UPDATE` on team capacity.

**Q19. How is idempotency handled?**
Telemetry is de-duplicated on (device, boot_id, seq), so a resend after a lost response is harmless. SOS submissions accept an `Idempotency-Key` that the offline PWA reuses on retry, and keys are namespaced by channel (web/sms/wearable) after QA found a public key could collide with and suppress an SMS or band SOS. Device and ROV commands use an outbox (queued → delivered → acked).

**Q20. Explain the JWT design.**
Access tokens are HS256 JWTs valid for 15 min. Refresh tokens are opaque, last 7 days, are stored as SHA-256 hashes with a family id, and rotate on every refresh. Reusing an already-rotated token revokes the whole family, which detects theft. The role is re-read from the DB on every request, and WebSockets re-check the account every 30 s and close on deactivation or a role change.

**Q21. How do scheduler leases work, and what went wrong?**
Each job holds a lease row that it renews while running, so with N replicas each job runs on exactly one. Live testing showed leases blocked takeover for 3x the job interval. I switched to short renewed leases plus a shared `last_run_at`; fast safety jobs use 10 s leases, and failed jobs retry with backoff from 5 s to 300 s.

**Q22. How does real-time push stay correct?**
Clients load a REST snapshot, then apply WebSocket deltas. Each message has a per-topic `seq`, and on a gap or reconnect the client reloads the snapshot. Device frame summaries are throttled to one per device per 1.5 s. Each user may hold at most 10 sockets, and a foreign Origin is closed with 4403.

**Q23. How does triage and auto-dispatch work?**
The triage score runs 0–100 with human-readable reasons and maps to P1 (most urgent) through P5. A linked wearable in a critical state adds 30 points, and a band SOS button press adds 40. P1–P2 requests are auto-dispatched by capacity in urgency order. When no team is free they are flagged `awaiting_resources` and the system suggests reallocating from requests at least 2 levels lower that aren't en route; a human confirms each move. Priority ageing adds 2 points per 5 min, capped at 20.

**Q24. When does the system move a team without a human?**
Only in the owner-approved extreme case, when all of these hold: P1 with score ≥ 80; the linked wearable critical with risk ≥ 0.85 for ≥ 60 s; environmental corroboration (water-disaster type, an active weather warning or a rising river); and no free team. The donor can only be a P4/P5 request not yet en route, and the full evidence goes to both timelines and the audit log. A wearable ID typed on a public form is only a claim and doesn't count until the band raised the SOS itself or a dispatcher links the device.

**Q25. What happens with no or poor internet?**
The SOS page is a PWA that works offline after one visit and resends with the same Idempotency-Key. There is an SMS fallback: a compact ≤ 160-character message goes through a gateway webhook. The wearable buffers 8 min (320 frames), drops routine frames before event frames, and keeps its on-device fall detector and buzzer working. LOST_CONTACT opens after 30 s of silence from a non-STABLE device. The ROV bridge cuts thrust after 5 s without the server. Planned but not built: LoRa/Meshtastic (2–15 km per hop) as the mountain-flood option, ESP-NOW relays, a BLE companion app, and an offline edge kit.

**Q26. What did QA find?**
Security: an unbounded time-series DoS, the idempotency namespace collision, unverified public wearable claims, WebSockets surviving deactivation, SMS secret brute force, and stored HTML in map tooltips. Load and failure: rate-limit bursts (shelter Wi-Fi and CGNAT share IPs), idempotent retries hitting the rate limit, DB busy errors that needed to become 503, one malformed frame blocking a whole backlog (now validated per frame), and tokens in logs. Live testing earlier also found the schema rejecting impacts over 16 g (now a per-axis range with |a| ≤ 27.7 g) and fusion recording the impact at the wrong frame.

**Q27. How would you scale it?**
Today it is a single-node monolith. Five kinds of in-memory state have to move deliberately: WebSocket fan-out to Redis pub/sub (with `seq` via INCR), per-device fusion runtimes to device-affinity routing with roughly 5 KB state snapshots, rate limits to Redis token buckets, weather cache to the DB, and vision frames to a separate relay. Idempotency, leases and refresh tokens are already in the database. Beyond about 200 devices, a Kafka/Redpanda backbone partitioned by device would take inference off the HTTP path.

**Q28. What are the honest limitations, and what would you do next?**
See section 4. Next: real-hardware data collection with a chest-strap reference to measure the emulator-to-device gap, CI plus a one-VM deployment (PostgreSQL, TLS, backups), signal-quality gating of the rhythm head by HR-trust, clinician review of the rule-only states, and camera calibration plus a person-in-water detector for the ROV.

**Q29. What would you do differently?**
I'd measure real daily-life false alarms from day one. The v1 fall model's 0.972 lab F1 hid 119 alarms per 8 h. I'd also have avoided synthetic labels entirely; the v2 audit had to throw the v1 approach away for that reason.

---

## 4. Honest limitations (say these before the interviewer does)

- **No clinical validation.** Nothing is a medical device. Cardiac arrest, hypoxia, haemorrhagic shock and hypothermia are rule-only states with sourced thresholds but no real-event sensitivity measured.
- **Emulated device data.** Every head was trained on public research recordings passed through the emulator, never on TRIDENT's own sensors. The firmware compiles but is untested on wired hardware, and the device-vs-emulator gap is unmeasured.
- **The stress head doesn't transfer.** 0.935 macro-F1 on WESAD but only about 0.52 on Stress-Predict (same E4 device, different protocol). That's why it is advisory and excluded from critical rules.
- **Falls are lab falls.** Young adults falling onto mats. HIFD Tier-1 window sensitivity at 0.72 is 0.34; fusion catches 84.6 % only with semi-synthetic stillness padding. PAMAP2 replay still gives 2.24 critical alarms per 8 h (3 in 10.7 h).
- **Rhythm on wrist PPG is untested.** The external test used ICU fingertip PPG, n = 35, AF vs non-AF only.
- **HR-trust is moderate** (macro-F1 0.768), and activity transfers poorly to PAMAP2 (0.59).
- **Weather** is a statistical short-range model on reanalysis data. Heavy hourly rain is not predictable, the flood output is a risk index, and calibration doesn't fully transfer across seasons.
- **CV** uses off-the-shelf YOLOv8n (not fine-tuned on people in water), LBPH faces and uncalibrated distances (±30 % at best). Face recognition on victims needs a consent policy.
- **Platform** is single-node and not yet deployed: no CI, no hosting, and SMS gateway, LoRa and the edge kit are designed but not built. Restarting loses per-device fusion state (about 2 min of recalibration).
- **Process.** I built this with AI coding assistants under a phase-by-phase review. Be ready to explain and defend every design choice and number yourself.
