# TRIDENT master context: reference for reports, papers and patents

**What this file is.** This is the single source of truth for writing about TRIDENT. It covers every component,
with exact numbers, design decisions, limitations and candidate inventive points. It also gives the structure and
formatting rules for these write-ups, each mapped to TRIDENT content:

- IEEE and Springer papers
- the VIT B.Tech capstone report
- Indian (Form 2) and foreign patent filings, through an agent such as Khurana & Khurana

**Compiled:** 2026-10-31, from the repository at P8 (all development phases complete), the generated reports and
model cards, and official web sources for the formats. Every number cites the file it came from.

**How to read the source tags.** Parts 0–6 are written for drafting.
- Appendix A is the checklist to run before you submit or file.
- Appendices B and C are the full fact sheets: B covers platform, hardware, ROV and QA; C covers ML, fusion,
  weather and CV.
- Appendix D holds the format rules with source URLs. Source abbreviations used throughout:

| Tag | File |
|---|---|
| ARCH | `docs/WEARABLE_ML_ARCHITECTURE.md` |
| CTX | `docs/WEARABLE_ML_SUBPROJECT_CONTEXT.md` (§3 datasets, §4 iteration log) |
| TG | `docs/TRAINING_GUIDE.md` |
| WX / WX-CARD | `docs/WEATHER_MODEL.md` / `models/weather/1.0.0/card.md` |
| DATA-R, TOUR-R, FINAL-R, REPLAY-R, AF-R | `docs/reports/` (data report, tournament, final models, fusion replay, rhythm AF test) |
| REG, CARD(h), MET(h) | `models/wearable/registry.json`, `models/wearable/<head>/2.0.0/card.md`, `metrics.json` |
| FUS-Y / FUS-PY | `src/ml/wearable/config/fusion.yaml` / `src/ml/wearable/serving/fusion.py` |
| TOUR-Y, DS-Y | `src/ml/wearable/config/tournament.yaml`, `datasets.yaml` |
| TJSON(h) | `data/processed/wearable/tournament/<head>.json` (generated, git-ignored) |
| PLATFORM | `docs/PLATFORM_DESIGN.md`; RESILIENCE = `docs/RESILIENCE_AND_FUTURE_WORK.md` |

---

## Part 0. Read this before writing anything

### 0.1 Five rules that protect the work

1. **File a patent before any public disclosure.** India applies absolute novelty. The grace period (s.31) covers
   only Gazette-notified exhibitions and papers read before a learned society. A public GitHub repository, arXiv
   preprint, accepted or presented paper, poster, project expo, hackathon demo, YouTube video or LinkedIn post can
   destroy patentability in India and Europe. **File at least an Indian provisional (₹1,600 for natural persons,
   e-filing) before submitting any paper**, and keep the repository private until then (Appendix D §4.6).
   - **Earlier public material is already prior art.** That includes the v1 code if the GitHub repo
     `harshitworkmain/trident` was public, the Render demo, and any posts. Claims must therefore rest on the v2
     features (Part 3), not on v1 features such as the additive priority counter or plain ESP32-to-cloud telemetry.
     Confirm with the agent which material was public and when.
2. **No foreign filing first.** Indian residents must file in India first and wait at least 6 weeks, or obtain a
   Foreign Filing Licence (Form 25), before any US provisional or PCT filing (s.39).
3. **Inventors are people.** Only humans who contributed to conceiving the claimed features are inventors. AI-inventor (DABUS) applications were refused in the UK, US and
   Europe, and Indian practice treats an inventor as a natural person; confirm with the agent. Much of the code was
   written with AI coding assistants under the team's direction (CTX §4).
   - Record which person conceived each claimed feature. Examples:
     - the owner's 2026-10-31 policy of automatic reallocation only in extreme, all-signals-agree cases
     - the band SOS button
     - wrist placement
     - the advisory-only role of the stress head
   - Disclose AI assistance where a venue requires it. IEEE asks for it in the acknowledgments. Springer Nature
     does not allow an LLM as an author and asks for its use to be documented in the Methods. Check each venue's
     current policy.
4. **Cite only what is measured.** Use the numbers in Part 2. Never quote the AI-generated infographics
   (`assets/images/infog-*.png`): they contain garbled specs. Don't claim hardware results: the band firmware
   compiles but has not been tested on wired hardware. Rule-only states (cardiac arrest, hypoxia, shock,
   hypothermia) have false-alarm (specificity) evidence only, and no sensitivity evidence.
5. **Never reproduce secrets.** Leave out the Wi-Fi credentials (`src/firmware/include/secrets.h`, and v1 firmware
   in git history), device keys and API tokens. Revoke the old Kaggle token that was committed and later scrubbed.

### 0.2 Facts to fill in (not recorded anywhere in the repo)

| Item | Value |
|---|---|
| Team members (full name, register number, programme, role) | **[TO FILL]**. Six people appear in `assets/images/team-photo.jpg`. Traces in the repo: "Thakur Akshayakumar 23BLC1120" (BOM spreadsheet metadata); "Avishkar" and "Harsh" (`src/cv/face_recognition/names.json`); git author "harshit". None of these states a role. |
| Institution / school / campus | **[TO FILL]**: VIT (Vellore Institute of Technology), School of ____, ______ campus |
| Guide (name, designation) and HoD / Programme Chair | **[TO FILL]** |
| Course code and semester | **[TO FILL]**: BCSE498J / BECE498J Project-II (Capstone)? (unverified, Appendix D §3.2) |
| Applicant for the patent (students, or VIT under its IPR policy) | **[TO FILL]**: check the VIT IPR / patent cell |
| Funding or sponsorship | **[TO FILL]**: none recorded |
| ROV hardware (frame, thrusters, motor drivers, controller, camera model, mass, dimensions, depth rating) | **[TO FILL]**. Only "Arduino Uno, 4 thrusters, LiPo", a PVC frame (team photo), a CAD isometric and a CFD image are recorded. |
| Band enclosure (material, IP rating, size, mass) and measured battery life | **[TO FILL]** |
| Prices (BOM) | Partial: `assets/documents/hardware_specs.xlsx` totals 2,388 (currency not stated, likely INR), covering ESP32, MPU6050, GSR, NEO-6M, MAX30102 and buzzer. MAX30205, BMP388, battery and enclosure are missing. |
| On-device results (real band) | **[TO FILL after hardware bring-up]**. Plan in RESILIENCE §9.1: Polar H10 chest reference. |
| Load-test latency and throughput numbers | **[TO FILL]**. The QA round recorded scope and defects but not latency percentiles. |
| Acronym expansion | Only one infographic gives "Tactical Rescue Interface for Disaster Events & Nautical Threats", with the ROV named "TRIDENT AURA". **Confirm with the team before using it.** |

### 0.3 Canonical facts and conventions

- **Name and tagline:** "TRIDENT: integrated flood and water-rescue platform", built for Chennai floods. It is a
  *decision-support tool, not a certified medical device*. Licence: MIT ("Copyright (c) 2025 TRIDENT Disaster
  Response System").
- **Versions:** API 2.0.0, firmware 2.2.0, web console 0.6.0, wearable models 2.0.0, fusion engine 1.2.0,
  weather model 1.0.0.
- **Priority convention:** **P1 = most urgent**, P5 = least. The v1 system used the opposite direction (higher =
  more urgent), so always state the v2 convention.
- **Tests:** 128 automated tests (49 backend, 79 ML/weather/vision), all passing as of 2026-10-31.
- **Code size:** about 18,900 lines of non-ML application code; about 6,150 lines of ML and weather code (incl. configs); 1,835 lines
  of tests (Appendix B §15).
- **Development timeline:**
  - v1 prototype uploaded 2026-01-26.
  - CV and Render deployment 2026-07.
  - ESP32 telemetry integration 2026-09-10.
  - 8-state synthetic ML engine 2026-09-18, Kaggle tournament 2026-09-25/28.
  - The 2026-10-30 audit found the synthetic approach could not be validated, which led to the v2 hybrid rebuild.
    Phases P0–P8 ran 2026-10-30/31: data, heads, fusion, platform, firmware, QA and docs.
  - The v2 rebuild is not yet committed to git (last commit `a424e02`, 2026-09-28).

---

## Part 1. Project narrative (adapt for any write-up)

### 1.1 Title options

| Use | Title |
|---|---|
| Capstone report | TRIDENT: An Integrated Flood and Water-Rescue Platform with Wearable Distress Detection, Semi-Autonomous ROV Vision and Corroborated Dispatch |
| Wearable ML paper | Train What You Serve: A Hybrid Wearable Distress-Detection System Combining Calibrated Real-Data Classifiers with Rule Fusion Validated on 1,500 Hours of Daily-Life Replay |
| Dispatch paper | Explainable, Sensor-Corroborated Triage and Automatic Resource Reallocation for Flood-Rescue Dispatch |
| Weather paper | Calibrated 48-Hour Probabilistic Multi-Variable Forecasting for Flood Early Warning in Chennai with Gradient Boosting and Recurrent Networks |
| Patent A (≤15 words) | System and method for corroborated automatic reallocation of rescue resources using wearable physiological states |
| Patent B (≤15 words) | Wearable distress-detection device with event-preserving telemetry and two-tier fall, immersion and SOS detection |

### 1.2 Problem statement

During urban floods, rescue capacity is scarce and information is poor. Concretely:

- **Victims may lose connectivity**, have no phone, or be unable to call: they may be trapped, injured,
  hypothermic, or under water.
- **Dispatchers rank requests by hand** from incomplete reports. When every team is busy, nobody can see that a
  waiting victim is deteriorating.
- **Water rescue is dangerous for responders**, and remote vehicles need fail-safe control.
- **Forecasts usually reach a control room as generic warnings**, not as calibrated, site-specific uncertainty
  tied to dispatch decisions.

Chennai has recurrent monsoon floods (for example December 2015, and Cyclone Michaung in December 2023). Cite an
official source such as NDMA, TNSDMA or IMD for any casualty or damage figure. None is recorded in the repo.

### 1.3 Objectives (map to "Objectives of the invention" or "Project goals")

1. **Many intake channels.** Let anyone raise an SOS through an offline-capable web app, plain SMS, or a phoneless
   wearable button. Each request is idempotent and trackable.
2. **Continuous detection from the band.** Detect falls, post-impact stasis, entrapment, cardiac and breathing
   emergencies, hypothermia, submersion and loss of contact from wrist-band telemetry. Use models trained only on
   real data, plus explicit rules where no data exists, and give every alert evidence and a basis label.
3. **Explainable triage.** Rank requests with a 0–100 score, raised by a *verified* wearable's measured state.
   Dispatch the most urgent first.
4. **Automatic reallocation only in extreme cases.** Move a rescue team without a human only when triage, the
   physiological state, environmental hazard and resource exhaustion all agree. Otherwise make suggestions that a
   person confirms.
5. **Safe ROV operation.** Run semi-autonomous ROVs with exclusive manual control, layered fail-safes, and an
   on-board camera with person detection, face recognition and distance estimates.
6. **Calibrated forecasts.** Provide p10/p50/p90 weather forecasts to 48 h with hazards and river discharge, and
   use them as corroboration in dispatch.
7. **Keep working when things fail.** Degrade gracefully: no internet, no ML, no team free, database busy, or a
   lost device link.

### 1.4 Contributions (bullet list for papers)

- A **device-emulator-anchored training pipeline**. Thirteen public datasets, recorded with 6 sensor
  placements/devices, are converted into the exact 1.5 s, 29-field telemetry frame the ESP32 band sends. One
  `FeatureEngine` serves both training and live inference, and a test checks feature equality between the two.
- **Five Tier-1 heads** (stress, fall, activity, HR-trust, rhythm). Each was selected by a statistically gated,
  subject-grouped 3-stage tournament over 7 candidate families, then calibrated (Platt / temperature) and exported
  to ONNX with parity checks.
- A **deterministic Tier-2 fusion state machine** (v1.2.0) with 8 states, dwell/exit hysteresis, signal-quality
  gating and evidence strings. Its rule thresholds were chosen on **≈1,505 h of real daily-life replay**
  (including 1,403 h of held-out people).
- **External validation:**
  - the rhythm head on real PPG from ICU patients with atrial fibrillation (MIMIC PERform AF: window AUROC 0.987,
    subject AUROC 1.000)
  - the fall pipeline on HIFD (84.6 % of falls reach post-impact stasis vs 6.9 % of daily activities)
- **Wearable-corroborated triage and all-signals-agree automatic reallocation**, with full audit evidence.
- **An event-preserving bounded telemetry queue and closed-loop SOS acknowledgement** on a phoneless band.
- **Layered ROV teleoperation safety** (exclusive lease, server dead-man 120 s, bridge link-loss stop 5 s,
  return-home reset), plus an **out-of-process vision relay with single-use stream tickets**.
- A **calibrated multi-variable weather forecaster** (LightGBM quantile + GRU, split-conformal calibration) that
  beats persistence and seasonal-naive baselines at every horizon for every variable.

### 1.5 System in one paragraph (for abstracts and summaries)

TRIDENT is a flood and water-rescue command platform with four field-facing parts:

- a public offline-capable web app and SMS channel for raising an SOS
- an ESP32 wrist band (IMU, PPG, skin temperature, barometer, electrodermal activity, water contact, GPS, buzzer,
  SOS button) that streams a 1.5 s telemetry frame
- semi-autonomous ROVs driven through a serial bridge, with a camera vision worker
- a staff console for dispatchers, responders, ROV pilots and administrators

On the server (FastAPI, SQLAlchemy, SQLite or PostgreSQL), five calibrated Tier-1 classifiers trained only on real
public datasets and a versioned Tier-2 rule-fusion engine turn each band's frames into one of eight health states,
each with a risk score and evidence. A 0–100 triage score combines the request's attributes with the state of a
verified linked band. Urgency-ordered auto-dispatch assigns teams. A team is moved automatically only when triage,
physiology, the environment (weather warning or rising river) and resource exhaustion all agree. Everything runs
on a single node, works offline on a LAN, and keeps working when ML, weather data or connectivity fail.

### 1.6 Keywords / index terms

Flood rescue; disaster management; emergency dispatch; triage; wearable sensors; fall detection; photoplethysmography;
atrial fibrillation; sensor fusion; probability calibration; ONNX; remotely operated vehicle; YOLOv8; face
recognition; probabilistic weather forecasting; quantile regression; offline-first; Internet of Things; ESP32.
(Pick 3–5 for IEEE and 4–6 for Springer.)

### 1.7 Relevance (SDGs and national programmes, for proposals and reports)

- UN SDG 11.5 (reduce deaths and losses from disasters), SDG 3 (health), and SDG 13.1 (resilience to
  climate-related hazards).
- Sendai Framework for Disaster Risk Reduction 2015–2030: priority 4, enhancing preparedness for effective
  response.
- India: the National Disaster Management Plan (NDMA) and the 112 ERSS. Integration with ERSS and NDMA's
  CAP/SACHET is future work (RESILIENCE §10.5). Verify the current names of these programmes before citing.

---

## Part 2. Results to cite (canonical numbers)

All numbers come from files in the repo. Appendix C gives the full tables. "OOF" means out-of-fold on subjects
never seen in training, with cross-fitted calibration. 95 % CIs come from a subject-level bootstrap.

### 2.1 Wearable Tier-1 heads (FINAL-R, cards)

| Head | Served model | Macro-F1 (95 % CI) | AUROC | Sens. | Spec. | ECE after cal. | Threshold |
|---|---|---|---|---|---|---|---|
| Stress | MiniRocket | 0.935 (0.889–0.970) | 0.985 | 0.945 | 0.944 | 0.008 | 0.33 |
| Fall (acc-only) | soft vote Extra-Trees + 1D-CNN | 0.867 (0.843–0.886) | 0.994 | 0.614 window / 0.727 per fall trial | 0.999 | 0.001 | 0.72 |
| Activity (rest/light/active) | Extra-Trees | 0.801 (0.778–0.820) | 0.953 | – | – | 0.011 | argmax |
| HR-trust | soft vote 1D-CNN + Extra-Trees | 0.768 (0.742–0.792) | 0.872 | 0.792 | 0.775 | 0.004 | 0.59 |
| Rhythm (regular/irregular) | 1D-CNN on last 64 RR | 0.932 (0.915–0.949) | 0.977 | 0.900 | 0.961 | 0.008 | 0.61 |

**Window counts.** Stress 5,268 windows / 15 subjects. Fall 561,095 / 190, of which 7,404 are falls. Activity
90,349 / 166. HR-trust 72,003 / 30. Rhythm 126,579 / 155 (44 % abnormal).

**External tests** (data never used for training or tuning):

| Head | External dataset | Macro-F1 | AUROC | Notes |
|---|---|---|---|---|
| Stress | Stress-Predict | 0.521 | 0.589 | Weak transfer, so the head is **advisory only** |
| Activity | PAMAP2 | 0.590 | 0.886 | – |
| Fall | HIFD | 0.716 | 0.974 | Sensitivity 0.337, specificity 0.991 |
| Fall | held-out Capture-24 (55 people, 1,403 h) | – | – | 2.14 false alarms / 8 h at threshold 0.72 |
| Rhythm | MIMIC PERform AF (35 ICU adults, PPG) | 0.938 window | 0.987 window; 1.000 subject | 19/19 AF and 15/16 non-AF subjects correct |

**Parity and serving:**

- ONNX matches Python within max |Δp| ≤ 1.2e-6 (MiniRocket 5.4e-3), with 0 argmax flips.
- The compiled forests match ONNX within ≤ 3e-7.
- Loading all heads takes about 0.5 s (about 9 min before the compiled forests). One frame through all heads and
  fusion takes about 5–60 ms of CPU, and the runtime uses about 230 MB of RAM.

### 2.2 Fusion engine v1.2.0 (FUS-Y, REPLAY-R)

**States (by severity):**

| State | Basis | Base risk |
|---|---|---|
| CARDIAC_ARREST | ml+rule | 0.95 |
| ASPIRATION_HYPOXIA | rule | 0.85 (+0.1 submerged) |
| HEMORRHAGIC_SHOCK | ml+rule | 0.85 |
| CONCUSSIVE_STASIS | ml+rule | 0.80 (+0.1 severe impact) |
| CRUSH_ENTRAPMENT | ml+rule | 0.75 |
| HYPOTHERMIA_RISK | rule | 0.60 |
| ELEVATED_STRESS | ml, advisory | 0.40 |
| STABLE | – | 0.05 |

The full entry rules, dwell and exit times are in Appendix C §9.3.

**Real-data false-alarm replay** (critical-state entries per 8 h, target ≤ 1):

| Dataset | Hours | Critical alarms / 8 h | Target met |
|---|---|---|---|
| PPG-DaLiA | 35.97 | 0.667 | yes |
| WESAD | 24.13 | 0.332 | yes |
| Stress-Predict | 31.34 | 0.511 | yes |
| PAMAP2 | 10.69 | 2.244 (3 events) | no |
| Capture-24 (55 held-out people) | 1,403 | 1.197 | no |

These figures come from the re-run on 2026-10-31 with the current fusion code; see the note in §2.6.

**Other fusion results:**

- **Falls on HIFD:** 84.6 % of 104 fall trials reach CONCUSSIVE_STASIS, against 6.9 % of 245 daily-activity
  trials. The median latency from impact is 32.25 s. The test pads each trial with 60 s of stillness, so it is
  semi-synthetic.
- **The rule redesign rests on measurements:**
  - The crush rule went from 14.29 to 0.51 false alarms / 8 h on Stress-Predict (option D + E fallback).
  - The fusion fall operating point of 0.6 raised the HIFD catch rate from 61.5 % to 84.6 %.
  - Stress was set to p > 0.85 with a 120 s dwell. This gives 0 % of WESAD baseline time and 86.4 % of TSST time.

### 2.3 Weather forecaster v1.0.0 (WX)

**Data and setup:**

- Chennai, ERA5 via Open-Meteo, 2015-01-01 to 2026-10-24: 103,560 hourly rows with no gaps.
- Split by time: test year 2025-10-24 to 2026-10-24, with 2,905 forecast origins.
- 78 LightGBM quantile boosters, plus a GRU(64) exported to ONNX (parity 1.4e-6), plus a blend.

**Skill of the chosen model vs persistence (1 − MAE/MAE_ref), by horizon:**

| Variable | 6 h | 24 h | 48 h |
|---|---|---|---|
| Temperature | 0.75 | 0.07 | 0.10 |
| Relative humidity | 0.66 | 0.10 | 0.16 |
| Rain | 0.37 | 0.36 | 0.41 |
| Wind | 0.39 | 0.11 | 0.12 |
| Pressure | 0.76 | 0.08 | 0.07 |

- **Coverage:** p10–p90 coverage after calibration is 0.72–0.83, against a target of 0.80.
- **Heavy-rain verification:**
  - 24 h rain ≥ 64.5 mm (IMD "heavy"), p90 rule: hit rate 0.43, CSI 0.33–0.34.
  - Hourly ≥ 7.6 mm/h is essentially unpredictable: CSI 0.15 at 1–3 h.
- **Hazards:**
  - heat: NOAA heat index plus IMD thresholds
  - heavy rain: IMD 64.5 / 115.6 mm
  - wind: Beaufort 6 / 8
  - flood risk: a 7-day antecedent precipitation index against climatological percentiles, 92 mm watch / 168 mm
    warning
- **River discharge:** GloFAS v4 for the Adyar, Cooum and Kosasthalaiyar. Trend "rising" > 1.15×.

### 2.4 Platform, dispatch, firmware, ROV and CV (Appendix B)

**Triage score (0–100):**

| Factor | Points |
|---|---|
| Wearable SOS button | +40 |
| Emergency type | 5–25 |
| Injured | ≤ 25 |
| People | ≤ 10 |
| Vulnerabilities | medical 12, pregnant 8, disabled 8, elderly 6, children 6 |
| Water / food scarcity | ≤ 10 / ≤ 5 |
| Age ≥ 70 or ≤ 5 | +4 |
| Verified linked band | critical +30, advisory +5, offline +3 |
| Ageing | +2 per 5 min waited, up to 20 |

Priority bands: P1 ≥ 60, P2 45–59, P3 30–44, P4 15–29, P5 < 15.

**Dispatch:**

- **Auto-dispatch** runs every 10 s for P1/P2 in the order (priority, −score, created_at).
- **Duplicate detection:** same phone or within 100 m, within the last 2 h. Duplicates are never auto-dispatched.
- **Extreme-case automatic reallocation** happens only when all of these hold: P1 with score ≥ 80; a verified band
  critical with risk ≥ 0.85 for ≥ 60 s; environmental corroboration; no free team. The donor team must be on a
  P4/P5 request that is not yet en route.

**Platform:**

- 64 REST routes under `/api/v1` plus WebSocket topics.
- JWT access tokens of 15 min, refresh tokens of 7 days with rotation and reuse detection.
- RBAC: admin > dispatcher > responder > viewer.
- DB-lease scheduler; idempotency namespaced by channel; optimistic locking; SQLite WAL with `BEGIN IMMEDIATE`.
- See Appendix B §5 for the remaining constants.

**Firmware 2.2.0:**

| Item | Value |
|---|---|
| Sampling | PPG 100 Hz, IMU 50 Hz (±16 g, ±2000 °/s), EDA 20 Hz, barometer 25 Hz, skin temperature 1 Hz, water ~2 Hz, battery 0.2 Hz |
| Offline queue | 320 frames (8 min), keeps event frames |
| Upload | batches of ≤ 10 frames |
| On-device fall detector | free fall < 0.5 g → impact ≥ 3 g within 1 s → stillness 2 s |
| SOS button | hold 1.5 s or 3 taps in 2 s; cancel by holding 5 s |
| Build | RAM 34.1 %, flash 53.1 % |

**ROV:**

- Deploy needs battery ≥ 30 %; the unit returns home below 20 %.
- Dead-man stop after 120 s without a control command; the bridge stops the unit 5 s after losing the server.
- Serial at 9600 baud with commands such as `forward_75`; track recorded at 1 Hz.

**CV:**

- YOLOv8n with confidence ≥ 0.4 on 80 COCO classes.
- Haar face detection plus LBPH recognition, match if distance < 50.
- Distance by pinhole model, D = W·f/w with f = 700 px at 640 px width; expect ±30 %.
- 0.3–0.5 s per frame on a laptop CPU, giving about 4 fps processed and ≤ 8 fps relayed.

**QA:**

- 128 tests.
- Security review of 52 endpoints × 5 roles; fixed 2 high and 5 medium issues.
- Load and failure testing: 20 devices × 5 min, a 20-min soak, kill -9; 12 defects fixed.
- Accessibility: axe serious issues went from 4 to 0.
- Model-file hashes verified 96/96.

### 2.5 What has *not* been measured (state this as a limitation, never invent it)

- Brier score
- calibrated AUPRC (only the uncalibrated tournament AUPRC exists)
- sensitivity of the rule-only states
- any on-band evaluation
- CV mAP or recall in water
- face-recognition FAR/FRR
- weather CRPS and per-season skill
- load-test latency percentiles
- battery life
- ROV specs

### 2.6 Inconsistencies already resolved (so drafts don't repeat old values)

- **Calibration** is Platt / temperature, not isotonic.
- **Validation** is 5-fold StratifiedGroupKFold by subject, not leave-one-subject-out.
- **Optuna** used 6–20 trials per candidate, not 40.
- **The offline buffer** is 320 frames / 8 min, not 120 / 3 min.
- **Idempotency keys** are kept 48 h, not 24 h.
- **The telemetry de-duplication key** is (device, boot, seq).
- **Retention:** raw frames are deleted after 7 days, not downsampled.
- **Fall sensitivity** depends on the definition: 0.614 per window, 0.727 per fall trial.
- **The replay numbers** in §2.2 were re-run on 2026-10-31 with the current fusion code. If they differ from an
  older copy, use §2.2.

---

## Part 3. Inventive points, prior-art positioning and patent strategy

### 3.1 Candidate inventive features (ranked by likely patent strength)

None of these has had a prior-art search. Treat them as candidates for the agent's search (§3.3).

| # | Feature | Why it may be inventive (technical effect) | Evidence in repo |
|---|---|---|---|
| **A1** | **Corroborated automatic reallocation of a rescue resource.** A team is moved from a lower-priority request to a waiting request with no human input only when four independent signals agree: (i) triage score ≥ 80 (P1); (ii) a *verified* wearable's fused state is critical with risk ≥ 0.85, sustained ≥ 60 s; (iii) environmental corroboration (water-disaster type, *or* an active weather-forecast warning, *or* a river-discharge trend > 1.15× labelled rising); (iv) no free resource. The donor is limited to P4/P5 not en route. Evidence is written to both timelines and the audit log. Below this bar, only human-confirmed suggestions are made, and they require a gap of ≥ 2 priority levels. | Removes the human bottleneck only where delay is most costly, while the multi-sensor agreement bounds the false-automation risk. Measurable effect: fewer unnecessary automated moves than a score-only trigger. | `src/backend/app/services/sos.py` (`_extreme`, `_auto_reallocate_if_extreme`, `_capacity`, `reallocate`); test `test_extreme_case_reallocates_automatically_only_when_everything_agrees` |
| **A2** | **Wearable-corroborated, explainable triage.** The measured state of a band counts only when the band's link is *verified* (the band itself raised the SOS, or a dispatcher confirmed it). Unverified claims are ignored. The score is re-evaluated every 10 s, so deteriorating waiting victims rise automatically. Every factor has a readable reason. | Stops spoofed device IDs from inflating priority; creates a closed loop from physiology to queue position. | `triage.py`, `sos.link_device`, `auto_triage`; test `test_public_device_claim_is_not_trusted` |
| **B1** | **Two-tier wearable distress detection with signal-quality gating.** Tier 1 is calibrated classifiers on 1.5 s aggregated frames (fall, activity, HR-trust, rhythm, stress). Tier 2 is a deterministic state machine with dwell/exit hysteresis. HR-based rules fire only when a learned HR-trust head says the PPG heart rate is reliable. Activity context gates the shock and stress rules. Fall impact plus post-impact immobility gives stasis. Impact-triggered or long stillness, plus HR above the personal baseline, plus GPS stillness gives entrapment. A sensor-fault overlay (contact lost while moving, or low battery) suppresses cardiac rules. | Fewer false alarms on real daily life (crush rule 14.29 → 0.51 / 8 h). The fusion fall operating point raises HIFD falls caught from 61.5 % to 84.6 %. | `serving/fusion.py`, `config/fusion.yaml`, REPLAY-R |
| **B2** | **Barometric and water-contact inference on a wrist band.** Submersion is inferred from a pressure rise of ≥ 5 hPa within 60 s while the water electrodes are wet; this escalates hypoxia risk. Fall height is inferred from a pressure rise of ≥ 0.12 hPa (~1 m) since impact, flagging a severe impact. The water electrodes use pulsed excitation (300 µs) to limit electrolysis. | Distinguishes drowning and fall-from-height from ordinary falls using low-cost sensors. | `fusion.yaml` hypoxia/concussive; `water.cpp`; `baro.cpp` |
| **B3** | **Event-preserving bounded telemetry queue.** A 320-frame ring evicts the oldest *routine* frame on overflow, keeping event frames (SOS, fall, ≥ 3 g impact, wet, geofence breach) in sequence order. Sequence numbers are reserved in NVS blocks of 4,000, and with a boot id they give a globally unique (device, boot, seq) for server de-duplication. The SOS group is replicated into every frame until acknowledged, so it overtakes a draining backlog. Retries are capped at 3 s while an SOS is pending. A bad frame is isolated by halving the batch. | Critical evidence survives outages longer than the buffer, without exceeding RAM, and flash wear stays low. | `frame.cpp`, `telemetry.cpp`, `settings.cpp`, `sos.cpp` |
| **B4** | **Closed-loop SOS on a phoneless wearable.** The server acknowledges by `press_id`, and the band plays distinct audible cues (raised / still sending / received / cancelled). Cancelling requires a new 5 s hold and never closes the request on the server. | A victim without a screen gets confirmation; accidental cancels are prevented. | `sos.cpp`, `buzzer.cpp`, `telemetry.sos_button` |
| **B5** | **Device-emulator-anchored training.** Heterogeneous public recordings (different devices, rates and placements) are converted into the exact firmware frame, reproducing firmware logic (50 Hz anti-alias resampling, RR window 270–2000 ms, 0.9/0.1 BPM EMA, 4 s BPM timeout, µS EDA with a 120 s baseline). Features are computed by the same online engine in training and serving. | Removes train/serve skew; models trained on lab data apply to the band's frames without retraining. Mostly a method, so claim it tied to the device. | `emulator.py`, `features/engine.py`, test `test_offline_features_equal_online_json_path` |
| **B6** | **Augmenting ECG beat labels to look like PPG**, calibrated on simultaneous wrist PPG and chest ECG (σ_RR 30–90 ms, 1–6 % missed beats, 0–4 % spurious beats), so a rhythm model trained on ECG works on wrist PPG. | External AUROC 0.987 on real PPG. | `heads/augment.py`, AF-R |
| **C1** | **Layered fail-safe ROV teleoperation.** An exclusive single-pilot lease with admin override; STOP available to a lower role than driving; a server dead-man stop (120 s) delivered to real units through a command outbox; an independent bridge-side stop 5 s after losing the server link; reset always returns home rather than resuming; automatic return below 20 % battery; deploy refused below 30 %. | Several independent failure paths each make the vehicle safe. | `rov.py`, `bridge.py`; tests `test_real_rov_deadman_queues_stop`, `test_bridge_stops_rov_when_control_room_unreachable` |
| **C2** | **Mission view fusing ROV telemetry with victims' live wearable states**, and an **out-of-process vision relay** with per-ROV keys and single-use 60 s stream tickets. | The pilot sees victim deterioration next to the camera feed; no bearer tokens appear in URLs. | `rov.missions`, `services/vision.py` |
| **D1** | **Offline-first SOS over many channels with idempotency namespaced by channel.** The same request identity holds across PWA outbox retries, SMS gateway retries and band button presses. Keys are namespaced `sos:{source}:{key}`, so one channel cannot suppress another. Idempotent retries are answered before rate limiting. | No duplicate dispatch and no lost SOS under flaky links. | `offline.ts`, `sms.py`, `sos.idem_key` |

**Weak or unpatentable on their own** (s.3(k) "algorithm per se" or obvious):

- the weather model
- the tournament procedure
- calibration
- the DB-lease scheduler
- the JWT scheme
- the console UI

Use them as supporting description, not as independent claims.

### 3.2 Recommended filing strategy (confirm with the agent)

1. **Two provisional applications, before any paper or public repo.**
   - **Application A (dispatch):** features A1, A2 and D1, with B1 and C2 as supporting embodiments.
   - **Application B (wearable):** features B1–B5, with B6 as an embodiment.
   - Each costs ₹1,600 when e-filed by natural persons; a complete filed later costs ₹0 plus extra pages and claims.
   - ROV feature C1 alone is probably obvious over known teleoperation dead-man practice. Keep it as an embodiment
     in A rather than filing it separately.
   - **Alternative:** one provisional describing everything, which is cheaper. Unity of invention (s.10(5)) then
     needs to be handled at the complete stage, which may mean divisional applications under s.16. Ask the agent
     which is better.
2. **Within 12 months, file the complete specification(s)** (Form 2 complete + Form 5).
   - Add the hardware bring-up results (RESILIENCE §9.1) and any new embodiments by then, since s.10(7) allows
     developments of the provisional.
   - File **Form 18 within 31 months** (₹4,000).
   - Form 9 (₹2,500) plus Form 18A (₹8,000) gives expedited examination, but natural persons qualify only if at
     least one applicant is a woman.
3. **Foreign filing.** After the Indian filing plus 6 weeks (or with a foreign filing licence), file a PCT within
   12 months of the Indian priority date (Paris Convention); national phase follows at 30/31 months. A US
   provisional within 12 months also works, but the s.39 rule still applies.
4. **Papers.** Submit only after the provisional's filing date. The paper must not disclose anything beyond what
   the provisional covers, so draft the provisional to include everything planned for publication.
5. **Applicant.** Decide whether the applicants are the students or VIT. VIT's IPR policy may require assignment
   (unverified); ask the VIT IPR cell. An educational institution also gets Column A fees with Form 28.

### 3.3 Prior-art search plan (for the agent or the team)

**Classification codes to search** (verify the codes in WIPO IPCPUB / Espacenet CPC):

| Feature | Codes |
|---|---|
| A1 / A2 (dispatch and triage) | G06Q 10/0631 (resource planning and allocation), G06Q 50/26 (government or public services, emergency), G08B 25/00 and G08B 27/00 (alarm systems), H04W 4/90 (emergency services), G16H 40/67 and G16H 50/20 (medical ICT, remote monitoring and diagnosis) |
| B1–B6 (wearable) | A61B 5/1117 (fall detection), A61B 5/0205 and 5/024 (heart rate), A61B 5/02405 (HR variability), A61B 5/361 (AF detection), A61B 5/7264 and 5/7267 (classification with ML), A61B 5/6802 and 5/681 (wrist-worn), G08B 21/043 and 21/0446 (fall or inactivity alarms worn on the body), G08B 21/08 (drowning alarms), G01L / G01C 5/06 (barometric altitude) |
| C1 / C2 (ROV) | B63G 8/001 (unmanned underwater vessels), B63C 11/52 (underwater tools / ROV), G05D 1/00 (vehicle control, teleoperation), G06V 20/52 (surveillance) and G06V 40/16 (face recognition) |

**Search strings (examples):**

- "wearable" AND ("fall" OR "immersion" OR "submersion") AND "barometric" AND ("rescue" OR "emergency")
- "emergency dispatch" AND "reallocat*" AND ("wearable" OR "physiological") AND ("weather" OR "flood")
- "triage score" AND "wearable sensor" AND "dispatch"
- "signal quality" AND "heart rate" AND "gating" AND "wrist" AND ("alarm" OR "alert")
- "telemetry buffer" AND "priority" AND "evict" AND "event" AND "wearable"

**Databases:**

- IP India InPASS (https://iprsearch.ipindia.gov.in/publicsearch)
- Google Patents
- Espacenet
- WIPO PATENTSCOPE
- for papers: IEEE Xplore, Scopus, Google Scholar

**Commercial references to distinguish:**

- smartwatch fall detection and emergency SOS (e.g. consumer smartwatches)
- PERS (personal emergency response) pendants
- drowning-detection wristbands
- CAD (computer-aided dispatch) systems with automatic vehicle location

TRIDENT differs from each of these on the combination: a verified physiological state plus environmental
corroboration driving dispatch, the barometric and water submersion logic, HR-trust gating, and event-preserving
telemetry.

---

## Part 4. Patent drafting kit

The official form rules are in Appendix D §4. Typical professional agent fees are extra; get quotes. **[TO FILL]**
marks team inputs.

### 4.1 Invention disclosure form (IDF), pre-filled

Khurana & Khurana has no public IDF. Their process is: disclosure meeting, then search, then drafting, then
filing. This form follows the common institutional IDF fields; take it to the first meeting.

| # | Field | Content |
|---|---|---|
| 1 | Title | See Part 1.1 (Patent A / Patent B) |
| 2 | Inventors (name, address, nationality, % contribution, what each conceived) | **[TO FILL]**. Map each person to features A1–D1 in §3.1. |
| 3 | Applicant(s) | **[TO FILL]**: students, or VIT under its IPR policy |
| 4 | Type | System (apparatus) + method (process) |
| 5 | Field | Emergency response and disaster management; wearable physiological monitoring; resource dispatch |
| 6 | Problem solved | Part 1.2 |
| 7 | Prior art known and differences | Part 3.3 (to be completed by the search) |
| 8 | Detailed description | Part 4.3 and Appendices B and C |
| 9 | What is new and non-obvious | §3.1, features A1, A2, B1–B5, D1 |
| 10 | Alternatives / variants (broaden claims) | §4.5 |
| 11 | Results / evidence | Part 2 (all measured on public datasets; hardware validation pending) |
| 12 | Development stage | TRL 4–5: system validated in the lab; band firmware builds but is not field-tested; platform QA'd |
| 13 | Disclosures, past and planned, with dates | **[TO FILL]**. Check: v1 GitHub repo (public?), Render deployment (2026-07), demo videos, career posts, college reviews, expos. Planned: papers (Part 5). |
| 14 | Funding / sponsor | **[TO FILL]** |
| 15 | Commercial interest | State disaster management authorities, municipal corporations, NDRF/SDRF, coastal and flood-prone districts; wearable makers |
| 16 | Signatures and dates | **[TO FILL]** |

### 4.2 Form 2 skeleton: provisional (Application A)

```
FORM 2
THE PATENTS ACT, 1970 (39 of 1970)
&
THE PATENTS RULES, 2003
PROVISIONAL SPECIFICATION
(See section 10 and rule 13)

1. TITLE OF THE INVENTION
   SYSTEM AND METHOD FOR CORROBORATED AUTOMATIC REALLOCATION OF RESCUE RESOURCES USING WEARABLE PHYSIOLOGICAL STATES

2. APPLICANT(S)
   (a) NAME: [TO FILL, family name first]   (b) NATIONALITY: Indian   (c) ADDRESS: [TO FILL, full postal address with PIN]

3. PREAMBLE TO THE DESCRIPTION
   The following specification describes the invention.

4. DESCRIPTION
   [sections below]

5. DATE AND SIGNATURE   [at the end of the last page]
```

For the complete specification, change the preamble to *"The following specification particularly describes the
invention and the manner in which it is to be performed."* Then add the claims, starting on a new page with
"We claim:", and the abstract on a separate page.

**Description (draft text to adapt; keep reference numerals consistent with the drawings):**

**FIELD OF THE INVENTION**
[001] The present invention relates to emergency response systems. More particularly, it relates to a system and
method for prioritising rescue requests and automatically reallocating rescue resources during floods and water
emergencies, using physiological states derived from a wearable device worn by a person in distress, corroborated
by environmental hazard information.

**BACKGROUND OF THE INVENTION**
[002] In urban floods, the number of rescue requests often exceeds the number of available rescue teams. In
conventional computer-aided dispatch, an operator ranks requests from caller-reported information. That
information is incomplete, does not change while the caller waits, and cannot reflect a person's deteriorating
condition.
[003] Wearable devices are known to detect falls and to raise emergency calls. They typically notify a contact or
a call centre, and do not alter the order in which scarce rescue resources are assigned. **[Agent: insert the
prior art found in the search and its drawbacks.]**
[004] Automatically reassigning a rescue team already committed to one request, so that it serves another, is
risky. A false trigger can leave the first person unattended. Known systems therefore either do not reallocate
automatically or do so on a single criterion such as a priority score.
[005] There is therefore a need for a system that (a) incorporates objectively measured physiological states into
request prioritisation only when the link between device and request is trustworthy, and (b) reallocates
resources automatically only when several independent sources of evidence agree.

**OBJECTS OF THE INVENTION**
[006] The principal object of the present invention is to provide a system that prioritises rescue requests using
a measured physiological state of the person in distress, obtained from a wearable device whose association with
the request has been verified.
[007] Another object is to provide a method of automatically reallocating a rescue resource from a lower-priority
request to a higher-priority request only when the triage score, the physiological state, environmental hazard
information and resource exhaustion all satisfy predetermined conditions.
[008] Another object is to record, for every automatic decision, the evidence on which it was based.
[009] Another object is to accept rescue requests over multiple channels (web application operable offline, short
message service, and a button on the wearable device) without creating duplicate requests.

**SUMMARY OF THE INVENTION**
[010] According to one aspect, the invention provides a rescue coordination system (100) comprising:

- wearable devices (200), each comprising sensors, a processor and a wireless transceiver, configured to transmit
  telemetry frames;
- a server (300) comprising a state-estimation module (320), a triage module (330), a dispatch module (340) and an
  environmental module (350);
- an operator console (400).

The state-estimation module determines, from the telemetry frames, a health state and a risk score for each wearable
device. The triage module computes an urgency score for each rescue request from request attributes and, only where
the device is verified as linked to the request, from the health state. The dispatch module assigns available
rescue resources in order of urgency. When no resource is available, it automatically reallocates a resource from a
donor request when all of the following hold:

- (i) the urgency score of the waiting request exceeds a first threshold;
- (ii) the linked device has been in a critical health state with a risk score above a second threshold for at
  least a predetermined duration;
- (iii) the environmental module indicates at least one corroborating hazard condition;
- (iv) the donor request has a priority below a predetermined level and its resource is not yet en route.

[011] According to another aspect, the invention provides a corresponding method (steps S1–S9, Fig. 3).

**BRIEF DESCRIPTION OF THE DRAWINGS** (each a separate A4 sheet; see §4.4)
[012] Fig. 1 is a block diagram of the rescue coordination system (100).
Fig. 2 is a block diagram of the wearable device (200).
Fig. 3 is a flow chart of the triage and dispatch method.
Fig. 4 is a flow chart of the corroborated automatic reallocation decision.
Fig. 5 is a state diagram of the health-state estimation.
Fig. 6 is a sequence diagram of the multi-channel request intake with idempotency.
Fig. 7 illustrates the operator console showing the capacity banner and reallocation evidence.

**DETAILED DESCRIPTION OF THE INVENTION**
[013] *Embodiment and best method* (s.10(4)(b) requires the best method known). Describe these in order, using the
constants from Appendix B §5 and Appendix C §9 as the best-mode values, and give ranges for breadth (for example
"a first threshold between 70 and 90, preferably 80"):

- system architecture (Appendix B §1)
- intake channels and idempotency (B §2.1, §5.8)
- the urgency score table (B §5.1), including the verified-link rule
- auto-dispatch ordering (B §5.3)
- the capacity states (B §5.4)
- the extreme-case conditions (B §5.5)
- the health-state engine (C §9)
- the environmental module: weather hazards from the quantile forecaster, river-discharge trend (C §11.6–11.7)
- audit and evidence (B §5.15, §5.19)

[014] *Example.* A wearable device linked to request SOS-XXXX reports CARDIAC_ARREST with risk 0.95 for 75 s. The
request's score is 85 (P1). A flood warning is active and the Adyar river trend is rising. All teams are assigned.
Team Alpha is serving a P5 request that is not yet en route. The system:

- moves Team Alpha;
- returns the donor request to the queue;
- records the evidence `['P1 85/100', 'wearable CARDIAC_ARREST risk 0.95 for 75 s', 'flood emergency', 'river Adyar rising']`;
- notifies the console.

### 4.3 Claim drafts (for the complete specification; refine with the agent)

Application A, independent claims:

> **1.** A rescue coordination system (100) comprising:
> a plurality of wearable devices (200), each comprising at least one physiological sensor (210), at least one
> motion sensor (220), a processor (250) and a wireless transceiver (260), configured to transmit telemetry frames;
> a server (300) communicatively coupled to the wearable devices (200), the server (300) comprising:
> a state-estimation module (320) configured to determine, from the telemetry frames of each wearable device (200),
> a health state selected from a plurality of predefined states, an alert level and a risk score;
> a triage module (330) configured to compute an urgency score for each rescue request, the urgency score being
> increased by an amount dependent on the health state of a wearable device (200) only when the wearable device
> (200) is verified as associated with the rescue request;
> an environmental module (350) configured to provide at least one hazard indication derived from a weather forecast
> or a river-discharge trend; and
> a dispatch module (340) configured to assign rescue resources to rescue requests in order of urgency and, when no
> rescue resource is free, to automatically reassign a rescue resource from a donor request to a waiting rescue
> request only when (i) the urgency score of the waiting request is at least a first threshold, (ii) the health state
> of the associated wearable device (200) has been critical with a risk score at least a second threshold for at
> least a predetermined duration, (iii) the environmental module (350) provides at least one corroborating hazard
> indication or the request is of a water-disaster type, and (iv) the donor request has a priority lower than a
> predetermined level and its rescue resource is not yet en route.

> **2.** A method for coordinating rescue resources, comprising the steps of: receiving (S1) telemetry frames from a
> wearable device (200); determining (S2) a health state and a risk score; receiving (S3) a rescue request and
> verifying (S4) an association between the rescue request and the wearable device (200); computing (S5) an urgency
> score; assigning (S6) a free rescue resource in order of urgency; when no rescue resource is free, evaluating (S7)
> conditions (i)–(iv) of claim 1; upon all conditions being satisfied, automatically reassigning (S8) the rescue
> resource and returning the donor request to a queue; and recording (S9) the evidence for the reassignment.

Dependent-claim ideas, each "The system as claimed in claim 1, wherein…":

- the association is verified when the rescue request was raised by the wearable device itself, or confirmed by an
  operator;
- the urgency score is recomputed periodically and includes a waiting-time component;
- the health state is determined by calibrated classifiers and a rule-based state machine with entry dwell and exit
  times;
- the hazard indication is a quantile weather-forecast warning, or a river-discharge ratio above 1.15;
- when the conditions are not met, the dispatch module presents reallocation suggestions requiring operator
  confirmation, limited to donor requests at least two priority levels lower;
- the reassignment is performed in a single database transaction with version checks on both requests;
- rescue requests are received over a web application with an offline queue, a short message service, and a button
  on the wearable device, with idempotency keys namespaced by channel;
- the rescue resource is a remotely operated vehicle (500) with a dead-man stop and a link-loss stop.

Application B, independent claims:

> **1.** A wearable distress-detection device (200) comprising: an inertial measurement unit (220); an optical
> pulse sensor (210); a barometric pressure sensor (230); water-contact electrodes (240); a satellite positioning
> receiver (270); a user-operable distress button (280); an audible indicator (290); a wireless transceiver (260);
> and a processor (250) configured to: aggregate sensor samples into telemetry frames of a fixed period comprising
> beat-to-beat interval values; store the frames in a bounded queue and, when the queue is full, discard the oldest
> frame not marked as an event frame; transmit the frames in batches with a device identifier, a boot identifier
> and a sequence number; and, upon actuation of the distress button, include a distress indication with a press
> identifier in every transmitted frame until an acknowledgement carrying the same press identifier is received,
> whereupon a distinct audible acknowledgement is emitted.

> **2.** A system comprising the device of claim 1 and a server (300) configured to determine a health state using
> (a) a fall classifier output together with immobility after the impact; (b) a heart-rate rule enabled only when a
> heart-rate-reliability classifier indicates that the optical heart rate is reliable; and (c) a submersion
> condition determined from a rise of barometric pressure above a threshold while the water-contact electrodes
> indicate wetness.

Dependent-claim ideas:

- the event frames comprise frames with an impact of ≥ 3 g, a distress indication, wetness or a geofence breach;
- sequence numbers are reserved in non-volatile memory in blocks;
- the retry interval is capped while a distress indication is unacknowledged;
- a cancel requires a new press held ≥ 5 s and does not close the request on the server;
- an on-device fall detector (free fall < 0.5 g, impact ≥ 3 g within 1 s, stillness 2 s) latches a local alarm
  independent of the network;
- severe impact is determined from a pressure rise corresponding to about 1 m;
- the water electrodes are excited only during measurement, for ≤ 300 µs;
- the classifiers are trained on recordings converted by an emulator into the same frame format;
- an ECG-derived rhythm dataset is augmented to resemble PPG.

**Notes on drafting:**

- Ten claims are included in the base fee; each extra claim costs ₹320.
- Keep every claim to one sentence.
- Use "comprising".
- Avoid bare "means for".
- Do not claim a computer-readable medium (CRI Guidelines 2025).

### 4.4 Drawings to prepare (Rule 15)

- A4 sheets, with margins of 4 cm top and left and 3 cm bottom and right.
- No dimensions; black lines. Text is allowed only in flow charts.
- Each sheet carries the applicant's name top-left, "Sheet x of y" top-right, and a signature bottom-right.
- Use reference numerals only.

Use these sources to redraw the figures:

| Figure | Redraw from |
|---|---|
| Fig. 1, system | `docs/ARCHITECTURE.md` mermaid diagram |
| Fig. 2, band | `assets/images/architecture.png`, `cad/wearable-*-line-diagram.jpg`, and the BOM (Appendix B §3.1) |
| Fig. 3 / 4, flow charts | Appendix B §2.1 and §5.5 |
| Fig. 5, state machine | Appendix C §9.3 |
| Fig. 7, console | `assets/images/console-operations.png`. Patent drawings must be line art, so trace it; don't paste the screenshot. |

Suggested reference numeral scheme:

- 100 system
- 200 wearable: 210 PPG, 220 IMU, 230 barometer, 240 water electrodes, 245 EDA, 247 skin temperature, 250 MCU,
  255 queue, 260 Wi-Fi, 270 GNSS, 280 SOS button, 290 buzzer
- 300 server: 310 ingest, 320 state estimation, 325 Tier-1 classifiers, 327 fusion engine, 330 triage,
  340 dispatch, 350 environmental module, 360 database, 370 real-time hub
- 400 console
- 500 ROV: 510 bridge, 520 camera, 530 vision worker
- 600 public web app, 610 SMS gateway

### 4.5 Variants to describe (broaden the claims)

- **Radios:** LoRa / Meshtastic, ESP-NOW mesh, BLE to a phone, satellite (RESILIENCE §7.3).
- **Sensors:** chest strap, ring or ankle placement; other wearables (smartwatch APIs).
- **Corroboration sources:** radar nowcast, river gauges (CWC), tide or storm surge (INCOIS), crowd reports, drone
  imagery.
- **Rescue resources:** boats, ROVs, drones, ambulances, NDRF/SDRF teams.
- **Models:** any calibrated classifier, including on-device TinyML; fusion by any rule or state machine with dwell
  and hysteresis.
- **Thresholds:** give ranges around the best-mode values.

### 4.6 Abstract (≤150 words; starts with the title; name the figure to accompany it)

**Application A (about 145 words including the title; recount after editing):**
SYSTEM AND METHOD FOR CORROBORATED AUTOMATIC REALLOCATION OF RESCUE RESOURCES USING WEARABLE PHYSIOLOGICAL STATES.
A rescue coordination system (100) comprises wearable devices (200) transmitting telemetry frames and a server
(300). A state-estimation module (320) determines a health state and risk score for each device. A triage module
(330) computes an urgency score for each rescue request, raised by the health state only when the device is
verified as associated with the request. A dispatch module (340) assigns rescue resources in order of urgency.
When no resource is free, it automatically reassigns a resource from a lower-priority donor request only when the
urgency score, a sustained critical health state, an environmental hazard indication from an environmental module
(350) and resource exhaustion all satisfy predetermined conditions, and it records the evidence. Otherwise it
offers operator-confirmed suggestions. This reduces delay in reaching deteriorating persons while limiting
erroneous reassignments. Fig. 4.

**Application B:** write it the same way from claim 1 of B, keeping it to ≤ 150 words.

### 4.7 Foreign route (summary; details in Appendix D §5)

- **US provisional:** a cover sheet plus a specification; no claims needed. A non-provisional must follow within
  12 months. It is attractive for a low-cost priority date, but only after the Indian filing plus 6 weeks, or with
  a licence.
- **US non-provisional:** sections in the 37 CFR 1.77(b) order. For §101 (Alice/Mayo), stress the technical
  improvements: fewer false alarms, bounded memory, fail-safe vehicle control, and data integrity under
  intermittent links.
- **PCT:** file within 12 months of the Indian priority date; national or regional phase at 30/31 months.

---

## Part 5. Write-up blueprints (structure × TRIDENT content)

Format rules (word limits, templates, captions, reference styles, fees) are in Appendix D. This part says **what
goes where**.

### 5.1 Recommended publication set (file the provisional first)

| # | Paper | Venue options (check the current CFP and scope) | Core content |
|---|---|---|---|
| P-1 | Hybrid wearable distress detection (emulator-anchored training, 5 calibrated heads, rule fusion, 1,505 h replay, external tests) | IEEE Sensors Journal (8 pages, graphical abstract required), IEEE Access, IEEE JBHI; Springer *Neural Computing and Applications* or *JAIHC* (12-page limit) | Appendix C §1–§10, §13–§14 |
| P-2 | Corroborated triage and automatic reallocation for flood dispatch (system plus policy evaluation) | Springer *Natural Hazards*; IEEE GHTC / TENCON / INDICON; *International Journal of Disaster Risk Reduction* (Elsevier; check the format separately) | Appendix B §2, §5, §11; Appendix C §11.6–11.7 |
| P-3 | Calibrated 48 h multi-variable probabilistic forecasting for Chennai | IEEE conference (e.g. IGARSS, INDICON), Springer *Natural Hazards* / *Theoretical and Applied Climatology* | Appendix C §11 |
| P-4 | Full system paper: TRIDENT architecture, resilience and QA | IEEE conference (ICCCNT, COMSNETS demo track, GHTC), Springer LNCS proceedings | Parts 1–2; Appendix B |

**Avoid self-plagiarism and duplicate publication.** Each paper needs its own primary contribution. IEEE Access
accepts extended conference papers only if similarity is below 35 %.

### 5.2 IEEE paper template mapped to P-1 (adapt for P-2–P-4)

| Section (IEEE order) | Content | Source |
|---|---|---|
| Title | Part 1.1. No "novel" and no math symbols. | – |
| Abstract (≤250 words, one paragraph, no citations, abbreviations or equations) | Draft below | Part 2.1–2.2 |
| Index Terms (3–5) | Wearable sensors, fall detection, photoplethysmography, sensor fusion, probability calibration | Part 1.6 |
| I. Introduction | Problem (Part 1.2); gap: lab-trained wearable models don't match the deployed device's data, and alarms lack evidence; contributions (Part 1.4, first 4 bullets); paper organisation | – |
| II. Related Work | Wearable fall detection, PPG AF detection, wearable stress detection, train/serve skew, calibration. **Cite only papers you have read**; the dataset papers in Part 6.1 are a starting point. | Part 6.1 |
| III. System and Frame Contract | Band hardware (B §3.1–3.3); 29-field frame (C §3); firmware/emulator parity (C §3.1–3.2) | B, C |
| IV. Data and Emulation | 13 datasets table (C §2.1); grouping and splits (C §2.2); emulator (C §3.2); ECG R-peak reference (C §3.3) | C |
| V. Tier-1 Heads | Labels (C §5); features (C §4); tournament protocol (C §6.1–6.2); calibration and thresholds (C §7.1, §7.3); export and parity (C §7.4) | C |
| VI. Tier-2 Fusion | States table (C §9.3); mechanics (C §9.1); signal-quality gating; option analyses (C §9.6) | C |
| VII. Results | Table I: final heads (Part 2.1). Table II: external tests. Table III: replay false alarms. Fig.: fall operating-point trade-off (C §9.6). Fig.: MIMIC AF ROC. | Part 2 |
| VIII. Discussion and Limitations | C §13; Part 2.5 | – |
| IX. Conclusion and Future Work | RESILIENCE §9 (hardware validation, TinyML) | – |
| Acknowledgment | Guide, institution, dataset providers; **AI-assistance disclosure** (§5.6) | – |
| References | IEEE numbered style (Appendix D §1.6) | Part 6.1 |

**Abstract draft for P-1 (≈240 words; check the count after editing):**
Wearable distress detection for flood rescue fails in practice when models trained on laboratory recordings meet
the different data produced by a deployed device, and when alarms carry no explanation. We present a hybrid
wrist-band system that is trained on exactly what it serves. Thirteen public datasets from six devices and body
placements are converted by a firmware emulator into the same 1.5-second, 29-field telemetry frame that our ESP32
band transmits, and one online feature engine computes features for both training and inference. Five Tier-1
heads (stress, fall, activity, heart-rate trust and rhythm) are each selected by a subject-grouped, statistically
gated tournament over seven model families, calibrated, and exported to ONNX with verified parity. A versioned
Tier-2 state machine combines head outputs with raw signals into eight states, each with dwell and exit
hysteresis, signal-quality gating and an evidence list. Its rule thresholds were chosen on 1,505 hours of real
daily-life replay, including 1,403 hours from held-out people. On unseen subjects, macro-F1 ranged from 0.768 to
0.935, and calibration error after calibration was at most 0.011. Externally, the rhythm head reached a window
AUROC of 0.987 on photoplethysmography from intensive-care patients with atrial fibrillation, and 84.6 % of
falls in an independent wrist dataset reached post-impact stasis, against 6.9 % of daily activities.
Critical-state false alarms were at most 0.67 per eight hours on three of five daily-life datasets. We report
remaining limitations, including rule states without positive data and the pending validation on the band itself.

### 5.3 Springer adaptations

- **LNCS:** 12–15 pages; abstract 150–250 words; keywords with `\and`; one corresponding author with email,
  ORCIDs encouraged. The **Disclosure of Interests** block is mandatory. References use `splncs04`. The appendix
  goes before the references.
- **SN journals:** use the `sn-jnl` template. A *Statements and Declarations* section is mandatory. Templates:

| Statement | Template text |
|---|---|
| Funding | "The authors did not receive support from any organization for the submitted work." **[or state the funder]** |
| Competing interests | "The authors have no relevant financial or non-financial interests to disclose." **[Note any pending patent application: "A patent application related to this work has been filed (Indian application no. [TO FILL])."]** |
| Ethics approval | "This study used only publicly available, de-identified datasets (WESAD, PPG-DaLiA, UP-Fall, SisFall, HIFD, MIT-BIH, AFDB, LTAFDB, PAMAP2, Capture-24, Stress-Predict, MIMIC PERform AF) under their published licences; no new data were collected from human participants, so ethics approval was not required." **[Change this if you collect band data from volunteers: obtain IEC approval first.]** |
| Consent | "Not applicable." |
| Data availability | "All datasets are publicly available from their original sources (see Table [n] for URLs and DOIs). Derived window tables can be regenerated with the published pipeline." |
| Code availability | "Code is available from the corresponding author on reasonable request" **[or a Zenodo DOI of a release, after the patent filing]**. |
| Author contributions (CRediT) | Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Writing (original draft), Writing (review & editing), Visualization, Supervision, Project administration: **[TO FILL per author]** |
| LLM use | "Large language model–based coding assistants were used to help implement software and draft documentation under the authors' direction; the authors designed the study, verified all code and results, and take full responsibility for the content." (Put this in Methods for SN, and in the Acknowledgment for IEEE.) |

- **JAIHC:** must use `\documentclass[iicol,sn-basic]{sn-jnl}`, with author-year references and a hard limit of 12
  pages including references.
- **Natural Hazards:** author-year references, line numbers, and declarations as noted in Appendix D §2.3.

### 5.4 VIT B.Tech capstone report (Project-II) mapped chapter by chapter

> The format below comes from VIT capstone templates shared by students and is **unverified**. Get the current
> template from VTOP or the school's project coordinator; it overrides this. Typical: A4, Times New Roman 12 pt,
> 1.5 spacing, chapter headings 14–16 pt bold, left margin about 1.5 in for binding, front matter in Roman
> numerals, figures "Fig. 3.2" (caption below), tables "Table 3.1" (caption above), IEEE references. Get the
> similarity limit from your guide (commonly under 10–15 % on Turnitin).

**Front matter**

1. **Title page:** title (Part 1.1); "Submitted in partial fulfilment of the requirements for the degree of
   Bachelor of Technology in [programme]"; names and register numbers; "Under the guidance of [Guide]"; School;
   VIT logo; month and year. **[TO FILL]**
2. **Declaration** (each student): "I hereby declare that the thesis entitled '…' submitted by me … is a record of
   bonafide work carried out by me under the supervision of … I further declare that the work reported in this
   thesis has not been submitted and will not be submitted, either in part or in full, for the award of any other
   degree or diploma in this institute or any other institute or university." Place, date, signature.
3. **Certificate** (bonafide): signed by the guide and the HoD / Programme Chair, with space for internal and
   external examiners.
4. **Acknowledgements:** Chancellor, VPs, VC, Dean, HoD, guide, review panel, dataset providers, family. Add the
   AI-assistance disclosure if the school requires it.
5. **Executive summary (≤200 words).** Draft:
   > TRIDENT is an integrated flood and water-rescue platform developed for Chennai. Citizens can request rescue
   > through an offline-capable web application, plain SMS, or an SOS button on a wrist band. The band, built on an
   > ESP32 with motion, pulse, skin-temperature, pressure, skin-conductance, water-contact and GPS sensors, sends a
   > 1.5-second telemetry frame and keeps eight minutes of data during outages. On the server, five machine-learning
   > models trained on thirteen public datasets and a rule-based fusion engine detect falls, entrapment, cardiac
   > and breathing emergencies, hypothermia and loss of contact, explaining each alert. A 0–100 triage score ranks
   > requests, raised by a verified band's measured state. Teams are dispatched by urgency and moved automatically
   > only when triage, physiology, weather or river data and resource exhaustion all agree. Semi-autonomous ROVs are
   > piloted from the browser with layered fail-safes, and their camera feed shows person detection, face
   > recognition and distance estimates. A probabilistic weather model forecasts five variables to 48 hours and
   > beats baseline methods at every horizon. The system passed 128 automated tests and a security, load and
   > failure-injection review.
   (≈180 words)
6. Table of contents; List of figures; List of tables; List of abbreviations (§5.7); Symbols and notations
   (§5.8).

**Chapters**

| Chapter | Sections | Content source | Suggested figures and tables |
|---|---|---|---|
| **1 Introduction** | 1.1 Objective (Part 1.3); 1.2 Motivation (Part 1.2; cite NDMA/IMD); 1.3 Background (floods, wearables, ROVs, dispatch; short literature survey, about 15–25 references) | Part 1 | Fig.: system concept (`assets/images/infog-trident.png` only as a concept image; don't quote its text) |
| **2 Project Description and Goals** | Scope, users (public, dispatcher, responder, ROV pilot, admin), goals and success criteria, use cases | USER_GUIDE §1, B §7.2 | Table: roles × capabilities (B §5.12); Fig.: use-case diagram |
| **3 Technical Specification** | Hardware specs (B §3.1–3.3, ROV B §4.1 + **[TO FILL]**); software stack (B §1.2); frame contract (C §3); API (B §6); performance targets | B, C | Table: BOM; Table: sampling rates; Table: frame fields; Table: API summary |
| **4 Design Approach and Details** | 4.1 Design approach / methods: architecture (B §1–2), firmware (B §3), ML pipeline (C §2–§9), weather (C §11), CV (C §12), backend algorithms (B §5), frontend (B §7). 4.2 Codes and standards (§5.9). 4.3 Constraints, alternatives and trade-offs (§5.10) | B, C | Fig.: architecture; Fig.: band block diagram + CAD (`assets/images/cad/*`); Fig.: FreeRTOS task diagram; Fig.: ML pipeline; Fig.: fusion state diagram; Fig.: SOS sequence; Fig.: ROV control path; Fig.: console screenshots (`assets/images/console-*.png`) |
| **5 Schedule, Tasks and Milestones** | Gantt chart from the iteration log (CTX §4) and the git dates (§0.3); team task split **[TO FILL]** | CTX §4 | Gantt chart |
| **6 Project Demonstration** | Demo script: public SOS, offline submit, SMS test, simulator wearables (`python -m src.backend.app.tools.simulate --with-sos`), fall → stasis alert, auto-dispatch, capacity banner and extreme case, ROV deploy, manual control, dead-man, vision feed, weather and analytics | GETTING_STARTED §7, USER_GUIDE | Screenshots; `assets/videos/*.mp4` |
| **7 Cost Analysis / Result and Discussion** | 7.1 Cost: BOM spreadsheet (2,388, partial) + missing parts **[TO FILL]**; hosting (free tier / Oracle Always Free). 7.2 Results: Part 2 tables. 7.3 Discussion: C §13, Part 2.5 | Part 2 | Tables I–V from Part 2; plots: fall operating points, weather skill vs horizon, MIMIC ROC, confusion matrices (regenerate from the reports) |
| **8 Summary** | Conclusions; future work (RESILIENCE Part II priorities P1–P3) | B §12 | – |
| References | IEEE numbered | Part 6.1 | – |
| Appendices | A: firmware pin map and config; B: API list; C: model cards (`models/wearable/*/2.0.0/card.md`); D: test list (B §10.1); E: user guide excerpts | – | – |

**Typical length:** 50–100 pages (older VIT guideline). **Reviews (unverified):** Review I covers problem,
literature, objectives and design; Review II covers implementation progress; Review III / Final covers the demo,
report and viva.

### 5.5 Other formats

**Poster (A0 or A1 portrait, unless the event specifies otherwise):**

- Title band with logos.
- Problem → Approach (architecture figure) → three result panels (wearable ML, dispatch, weather) → ROV / CV
  snapshot → conclusions → QR code to a **private** demo video (until the patent is filed).
- Use 3–4 colours, ≥ 24 pt body text and ≥ 72 pt title.

**SIH / hackathon idea or grant proposal:**

- **Sections:** problem statement; proposed solution; uniqueness (Part 3.1); technology stack (B §1.2);
  feasibility; impact (SDGs, Part 1.7); TRL (4–5 now); budget (BOM + hosting); timeline; team.
- **Remember:** a public pitch is a disclosure. File first.

### 5.6 Statements reused across venues

- **AI-assistance disclosure:** see the LLM row in §5.3.
- **Medical-device disclaimer:** "TRIDENT is a research prototype and decision-support tool; it is not a certified
  medical device and is not intended for diagnosis."
- **Dataset licences:** CC BY 4.0 (WESAD, PPG-DaLiA, PAMAP2, Capture-24); ODC-By 1.0 (PhysioNet MIT-BIH, AFDB,
  LTAFDB); ODbL 1.0 (MIMIC PERform AF); MIT (Stress-Predict); UP-Fall, SisFall and HIFD use their sources' terms
  (C §2.1). Cite each dataset paper as its licence requires.
- **Face recognition and consent:** enrolment covers consenting responders only, never victims or bystanders
  (`src/cv/README.md`). Note the DPDP Act 2023 if the system will process personal data in deployment.

### 5.7 Abbreviations (for lists and first use)

| Abbreviation | Meaning |
|---|---|
| ACID | atomicity, consistency, isolation, durability |
| AF | atrial fibrillation |
| API | application programming interface |
| AUROC / AUPRC | area under the ROC / precision–recall curve |
| BMP388 | barometric pressure sensor |
| CAP | consistency, availability, partition tolerance |
| CI | confidence interval |
| CNN | convolutional neural network |
| CSI | critical success index |
| CV | computer vision; cross-validation (context decides) |
| ECE | expected calibration error |
| ECG | electrocardiogram |
| EDA / GSR | electrodermal activity / galvanic skin response |
| EMA | exponential moving average |
| ERA5 | ECMWF reanalysis v5 |
| ERSS | Emergency Response Support System |
| FA | false alarm |
| FAR | false-alarm ratio |
| GloFAS | Global Flood Awareness System |
| GNSS / GPS | satellite positioning |
| GRU | gated recurrent unit |
| HIFD | heart-rate + IMU fall-detection dataset |
| HR / HRV | heart rate / heart-rate variability |
| IDF | invention disclosure form |
| IMD | India Meteorological Department |
| IMU | inertial measurement unit |
| JWT | JSON Web Token |
| LBPH | local binary pattern histogram |
| LTAFDB | Long-Term AF Database |
| MAE | mean absolute error |
| MCU | microcontroller unit |
| MJPEG | motion JPEG |
| NVS | non-volatile storage |
| ONNX | Open Neural Network Exchange |
| OOF | out-of-fold |
| PPG | photoplethysmography |
| PWA | progressive web app |
| RBAC | role-based access control |
| ROV | remotely operated vehicle |
| RR | beat-to-beat interval |
| SpO₂ | peripheral oxygen saturation |
| TRL | technology readiness level |
| TSST | Trier Social Stress Test |
| WAL | write-ahead logging |
| WS | WebSocket |
| YOLO | You Only Look Once |

### 5.8 Symbols (for "Symbols and notations")

| Symbol | Meaning |
|---|---|
| D = W·f/w | distance D (m) from real width W (m), focal length f (px), image width w (px) |
| p₁ = σ(a·logit(p) + b) | Platt calibration with parameters a, b |
| softmax(log p / T) | temperature scaling with temperature T |
| Skill = 1 − MAE/MAE_ref | forecast skill against a reference forecast |
| ρ_k = max(q(y−ŷ), (q−1)(y−ŷ)) | pinball loss at quantile q |
| API_t = Σ 0.85^k · R_{t−k} | 7-day antecedent precipitation index |
| HI | heat index (Rothfusz regression) |
| score = min(100, Σ factors) | triage score; priority P = 5 − \|{b ∈ (15, 30, 45, 60) : b ≤ score}\| |

### 5.9 Codes and standards (for VIT §4.2)

- **Radio and buses:** IEEE 802.11 b/g/n (ESP32 Wi-Fi); I²C (400 kHz); UART (NMEA 0183 from the NEO-6M);
  HTTP/1.1 over TLS.
- **Protocols and formats:**
  - RFC 6455 (WebSocket)
  - RFC 7519 (JWT)
  - RFC 9110 (HTTP semantics)
  - JSON Schema 2020-12 (frame contract)
  - OpenAPI 3 (FastAPI)
  - ONNX opset 15/17
- **Security and accessibility:** OWASP ASVS / Top 10 (security review); WCAG 2.1 AA (axe accessibility checks).
- **Product standards:**
  - IEC 60529 IP rating, a target for the band and ROV, not yet tested
  - IEC 62304 / ISO 13485 / CDSCO medical-device rules, *not claimed* because the system is decision support
- **Meteorology:**
  - IMD rainfall categories (heavy 64.5 mm, very heavy 115.6 mm per 24 h)
  - NOAA/NWS heat index
  - IMD heatwave criteria
  - Beaufort scale
- **Law and policy:** DPDP Act 2023 (personal data); Telecom Commercial Communications rules for SMS (if a
  provider is used).

### 5.10 Constraints, alternatives and trade-offs (for VIT §4.3)

| Decision | Chosen | Alternatives | Trade-off |
|---|---|---|---|
| ML location | Server-side inference on 1.5 s frames; on-device fall heuristic only | TinyML on band; phone app | Server allows heavy models and versioning; needs a link, so an 8 min buffer and an on-device fall alarm cover outages |
| Frame | Aggregated 1.5 s frame (~0.8 kB) with RR list | Raw waveform streaming | 50–100× less bandwidth; loses raw morphology (no PPG-waveform models) |
| IMU rate | 50 Hz, ±16 g | 100–200 Hz | Matches the HIFD wrist test set; less power and RAM; impacts up to 27.7 g measurable |
| Model family | Tournament-selected (MiniRocket, 1D-CNN, Extra-Trees, votes) | Single deep model | Best per task; Extra-Trees ONNX files are large (6.7–75 MB), so compiled numpy forests are used |
| Calibration | Platt / temperature | Isotonic | Smooth, stable with small positive counts |
| Rule states | Explicit versioned rules | Synthetic-data classifier (v1) | Auditable; no sensitivity data, flagged as a limitation |
| Stress | Advisory only | Critical driver | External macro-F1 only 0.52 |
| Fall threshold | Tier-1 0.72; fusion 0.6 | One threshold | Fusion's immobility check adds specificity, so it can afford a lower threshold |
| Database | SQLite WAL now; PostgreSQL ready | Postgres only | Zero-ops single node; Postgres for scale |
| Consistency | CP for SOS and assignments; AP for telemetry | Uniform | Correct dispatch under contention; telemetry never blocks devices |
| Auto-reallocation | Only when all signals agree | Never / score-only | Saves time in extreme cases; bounded risk of wrong moves |
| Video | MJPEG relay with tickets | WebRTC | Simple and robust at low frame rates; higher bandwidth (WebRTC is future work) |
| Weather | Statistical (LightGBM + GRU) on ERA5 | NWP downscaling | Cheap and calibrated; weak for heavy hourly rain |
| Hosting | Single node / LAN-capable | Cloud microservices | Works offline in a control room; multi-replica plan in RESILIENCE §6.2 |

---

## Part 6. References, figures and file map

### 6.1 Bibliography seeds (IEEE style; **verify every entry and DOI against the publisher before use**)

**Datasets**

[D1] P. Schmidt, A. Reiss, R. Duerichen, C. Marberger, and K. Van Laerhoven, "Introducing WESAD, a multimodal dataset for wearable stress and affect detection," in *Proc. 20th ACM Int. Conf. Multimodal Interact. (ICMI)*, 2018, pp. 400–408, doi: 10.1145/3242969.3242985.
[D2] A. Reiss, I. Indlekofer, P. Schmidt, and K. Van Laerhoven, "Deep PPG: Large-scale heart rate estimation with convolutional neural networks," *Sensors*, vol. 19, no. 14, Art. no. 3079, 2019, doi: 10.3390/s19143079.
[D3] L. Martínez-Villaseñor *et al.*, "UP-Fall detection dataset: A multimodal approach," *Sensors*, vol. 19, no. 9, Art. no. 1988, 2019, doi: 10.3390/s19091988.
[D4] A. Sucerquia, J. D. López, and J. F. Vargas-Bonilla, "SisFall: A fall and movement dataset," *Sensors*, vol. 17, no. 1, Art. no. 198, 2017, doi: 10.3390/s17010198.
[D5] Y.-H. Nho *et al.*, "Cluster-analysis-based user-adaptive fall detection using fusion of heart rate sensor and accelerometer in a wearable device," *IEEE Access*, vol. 8, 2020 (IEEE Xplore doc. 8970371). **Verify the pages and DOI.**
[D6] G. B. Moody and R. G. Mark, "The impact of the MIT-BIH Arrhythmia Database," *IEEE Eng. Med. Biol. Mag.*, vol. 20, no. 3, pp. 45–50, 2001, doi: 10.1109/51.932724.
[D7] G. B. Moody and R. G. Mark, "A new method for detecting atrial fibrillation using R-R intervals," *Computers in Cardiology*, vol. 10, pp. 227–230, 1983. (AFDB)
[D8] S. Petrutiu, A. V. Sahakian, and S. Swiryn, "Abrupt changes in fibrillatory wave characteristics at the termination of paroxysmal atrial fibrillation in humans," *Europace*, vol. 9, no. 7, pp. 466–470, 2007, doi: 10.1093/europace/eum096. (LTAFDB)
[D9] A. L. Goldberger *et al.*, "PhysioBank, PhysioToolkit, and PhysioNet," *Circulation*, vol. 101, no. 23, pp. e215–e220, 2000, doi: 10.1161/01.CIR.101.23.e215.
[D10] A. Reiss and D. Stricker, "Introducing a new benchmarked dataset for activity monitoring," in *Proc. 16th Int. Symp. Wearable Comput. (ISWC)*, 2012, pp. 108–109, doi: 10.1109/ISWC.2012.13. (PAMAP2)
[D11] S. Chan Chang *et al.*, "CAPTURE-24: A large dataset of wrist-worn activity tracker data collected in the wild for human activity recognition," *Scientific Data*, 2024. **Verify the authors, article number and DOI**; dataset at ORA (C §2.1).
[D12] T. Iqbal *et al.*, "Stress monitoring using wearable sensors: A pilot study and stress-predict dataset," *Sensors*, vol. 22, no. 21, Art. no. 8135, 2022, doi: 10.3390/s22218135.
[D13] P. H. Charlton *et al.*, MIMIC PERform AF dataset, Zenodo, 2022, doi: 10.5281/zenodo.6807403; see also P. H. Charlton *et al.*, "Detecting beats in the photoplethysmogram: Benchmarking open-source algorithms," *Physiol. Meas.*, 2022. **Verify.**

**Methods and tools**

[M1] P. Geurts, D. Ernst, and L. Wehenkel, "Extremely randomized trees," *Mach. Learn.*, vol. 63, pp. 3–42, 2006, doi: 10.1007/s10994-006-6226-1.
[M2] A. Dempster, D. F. Schmidt, and G. I. Webb, "MiniRocket: A very fast (almost) deterministic transform for time series classification," in *Proc. 27th ACM SIGKDD*, 2021, pp. 248–257, doi: 10.1145/3447548.3467231.
[M3] G. Ke *et al.*, "LightGBM: A highly efficient gradient boosting decision tree," in *Proc. NeurIPS*, 2017.
[M4] T. Chen and C. Guestrin, "XGBoost: A scalable tree boosting system," in *Proc. 22nd ACM SIGKDD*, 2016, pp. 785–794, doi: 10.1145/2939672.2939785.
[M5] T. Akiba *et al.*, "Optuna: A next-generation hyperparameter optimization framework," in *Proc. 25th ACM SIGKDD*, 2019, pp. 2623–2631, doi: 10.1145/3292500.3330701.
[M6] J. Platt, "Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods," in *Advances in Large Margin Classifiers*, MIT Press, 1999, pp. 61–74.
[M7] C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger, "On calibration of modern neural networks," in *Proc. 34th ICML*, 2017, pp. 1321–1330.
[M8] K. Cho *et al.*, "Learning phrase representations using RNN encoder–decoder for statistical machine translation," in *Proc. EMNLP*, 2014, pp. 1724–1734, doi: 10.3115/v1/D14-1179. (GRU)
[M9] R. Koenker and G. Bassett, "Regression quantiles," *Econometrica*, vol. 46, no. 1, pp. 33–50, 1978.
[M10] Y. Romano, E. Patterson, and E. Candès, "Conformalized quantile regression," in *Proc. NeurIPS*, 2019.
[M11] J. Pan and W. J. Tompkins, "A real-time QRS detection algorithm," *IEEE Trans. Biomed. Eng.*, vol. BME-32, no. 3, pp. 230–236, 1985, doi: 10.1109/TBME.1985.325532. (Basis of the R-peak detector style)
[M12] G. Jocher, A. Chaurasia, and J. Qiu. *Ultralytics YOLOv8*. (2023). GitHub. [Online]. Available: https://github.com/ultralytics/ultralytics
[M13] P. Viola and M. Jones, "Rapid object detection using a boosted cascade of simple features," in *Proc. IEEE CVPR*, 2001, doi: 10.1109/CVPR.2001.990517.
[M14] T. Ahonen, A. Hadid, and M. Pietikäinen, "Face description with local binary patterns: Application to face recognition," *IEEE Trans. Pattern Anal. Mach. Intell.*, vol. 28, no. 12, pp. 2037–2041, 2006, doi: 10.1109/TPAMI.2006.244.
[M15] H. Hersbach *et al.*, "The ERA5 global reanalysis," *Q. J. R. Meteorol. Soc.*, vol. 146, no. 730, pp. 1999–2049, 2020, doi: 10.1002/qj.3803.
[M16] S. Harrigan *et al.*, "GloFAS-ERA5 operational global river discharge reanalysis 1979–present," *Earth Syst. Sci. Data*, vol. 12, pp. 2043–2060, 2020, doi: 10.5194/essd-12-2043-2020.
[M17] P. Zippenfenig. *Open-Meteo.com Weather API*. Zenodo. **Verify the DOI.** [Online]. Available: https://open-meteo.com
[M18] L. P. Rothfusz, "The heat index 'equation'," NWS Southern Region Tech. Attachment SR 90-23, 1990.
[M19] UNDRR, *Sendai Framework for Disaster Risk Reduction 2015–2030*, 2015.
[M20] ONNX. *Open Neural Network Exchange*. [Online]. Available: https://onnx.ai
[M21] M. Jones, J. Bradley, and N. Sakimura, "JSON Web Token (JWT)," IETF RFC 7519, 2015.
[M22] I. Fette and A. Melnikov, "The WebSocket protocol," IETF RFC 6455, 2011.

**Related work** must come from your own literature search: wearable fall detection reviews, PPG AF detection,
drowning detection, CAD systems, flood early warning in India, ROVs for search and rescue. Do not cite papers you
have not read.

### 6.2 Figure and media inventory

| Asset | Path | Use |
|---|---|---|
| Logo | `assets/images/TRIDENT_logo.png` | Title pages, posters |
| Console screenshots (v2) | `assets/images/console-operations.png`, `console-rov-missions.png`, `console-wearable.png`, `console-weather.png`, `console-public.png` | Reports, papers (P-2, P-4), posters |
| Band CAD | `assets/images/cad/wearable-*.jpg` (isometric, exploded, PCB, side; line-diagram versions for patents) | Hardware chapter, patent Fig. 2 |
| ROV CAD and CFD | `assets/images/cad/rov-isometric-view.jpg`, `assets/images/cfd.jpg` | ROV section |
| Band logic (v1) | `assets/images/architecture.png` | Redraw for v2 (50 Hz, new sensors) |
| Team photo | `assets/images/team-photo.jpg` | Report, poster |
| Videos | `assets/videos/wearable-demo.mp4`, `Wearable-cad.mp4`, `finalrov.mp4` | Demo (keep private until filing) |
| **Do not use as evidence** | `assets/images/infog-*.png`, `band_ai_img.jpg` (AI-generated, garbled specs) | Concept art at most |
| Diagrams to draw | Architecture (`docs/ARCHITECTURE.md` mermaid), fusion states, SOS sequence, FreeRTOS tasks, ML pipeline, Gantt | – |
| Plots to generate | Fall operating-point trade-off (C §9.6), weather skill vs horizon (C §11.3), MIMIC ROC (AF-R JSON), reliability diagrams (`metrics.json`), confusion matrices | – |

### 6.3 Where the truth lives (to re-check numbers)

| Topic | File |
|---|---|
| Final head metrics | `docs/reports/WEARABLE_FINAL_MODELS.md`, `models/wearable/<head>/2.0.0/card.md` |
| Tournament | `docs/reports/MODEL_TOURNAMENT_RESULTS.md` |
| Replay | `docs/reports/WEARABLE_FUSION_REPLAY.md` |
| AF external test | `docs/reports/WEARABLE_RHYTHM_PPG_AF_TEST.md` |
| Data | `docs/reports/WEARABLE_DATA_REPORT.md` |
| Weather | `docs/WEATHER_MODEL.md`, `models/weather/1.0.0/card.md` |
| Fusion rules | `src/ml/wearable/config/fusion.yaml` |
| Platform constants | `src/backend/app/services/*.py`, `config.py` |
| Firmware constants | `src/firmware/include/config.h` |
| Decisions and history | `docs/WEARABLE_ML_ARCHITECTURE.md` (decisions 1–25), `docs/WEARABLE_ML_SUBPROJECT_CONTEXT.md` §4 |
| Roadmap | `docs/RESILIENCE_AND_FUTURE_WORK.md` Part II |

---

## Appendix A. Checklist before you submit or file

**Before any submission:**

- [ ] **Patent first:** the provisional is filed (application number and date recorded) before any paper, poster,
  public repo or demo.
- [ ] Every number is traced to a file in §6.3. No numbers come from the infographics.
- [ ] Unmeasured items (Part 2.5) are stated as limitations, not results.
- [ ] Fall sensitivity is stated with its definition (per window or per fall trial).
- [ ] Replay numbers come from the current report (Part 2.2).
- [ ] The priority convention (P1 = most urgent) is stated.
- [ ] Inventors and authors are listed with their real contributions, and the AI-assistance disclosure is included
  where the venue requires it.
- [ ] Dataset citations and licences are included (Part 5.6).
- [ ] No secrets (Wi-Fi, keys, tokens) appear in any text, figure, screenshot or appendix.
- [ ] VIT: the current school template, a Turnitin report under the school limit, and guide sign-off are done.
- [ ] Patent: Form 1, Form 2, Form 3 (if foreign filings are planned), Form 5 (with the complete), and Form 26 (if
  using an agent). Drawings follow Rule 15. The abstract is ≤ 150 words and the title ≤ 15 words. Claims start
  with "We claim:".
- [ ] Diary dates: complete specification ≤ 12 months after the provisional; Form 18 ≤ 31 months; PCT ≤ 12 months
  from priority.

**Hardware facts still to collect (they strengthen both the patent's best method and the papers):**

- band bring-up against a Polar H10 (RESILIENCE §9.1)
- battery life
- ROV specifications
- latency under load

## Appendix B. Platform, hardware, ROV and QA fact sheet

Compiled 2026-10-31 from the working tree at `D:\harshit\trident` (read-only pass). Every fact cites its file.
"Doc" = stated in documentation; "code" = verified in source. Where the two disagree, see §16 (discrepancies).
ML internals (heads, tournament, fusion thresholds, weather model metrics) are out of scope and only referenced
where the platform consumes them.

---

### 0. Identity and one-paragraph summary

- **Name:** TRIDENT. Expansion found only in an infographic: **"Tactical Rescue Interface for Disaster Events & Nautical Threats"** (`assets/images/infog-trident.png`). The same image names the ROV **"TRIDENT AURA"**; the legacy PyQt6 ROV console title is **"AURA Prototype Control Station"** (`src/rov/communication/serial_interface.py` line ~24).
- **Tagline (README):** "integrated flood and water-rescue platform"; built for **Chennai floods**; "decision-support tool, not a certified medical device" (`README.md`).
- Older tagline (historic README, commit `4ab536f`, 2026-03-30): "Integrated Disaster Response & Rescue Ecosystem"; "TRIDENT - Your Shield in Times of Crisis".
- **Licence:** MIT, "Copyright (c) 2025 TRIDENT Disaster Response System" (`LICENSE`).
- **Versions:** API `__version__ = '2.0.0'` (`src/backend/app/__init__.py`); firmware `FW_VERSION "2.2.0"` (`src/firmware/include/config.h`); web console `package.json` version `0.6.0`; ML models wearable 2.0.0, weather 1.0.0 (`models/`).
- **Status:** "Development phases P0–P8 are complete"; full QA round done (`README.md`, `docs/WEARABLE_ML_SUBPROJECT_CONTEXT.md` §1).
- **Four parts** (`docs/USER_GUIDE.md` intro): public web page for requesting rescue + tracking; staff console (dispatchers, responders, viewers, admins); wearable bands (vitals + SOS button); underwater ROV units sent to a request and driven from the console.

---

### 1. System architecture

#### 1.1 Components (`docs/ARCHITECTURE.md` §1, mermaid diagram)

| Component | Code | Role |
|---|---|---|
| Web console + public PWA | `src/frontend/web` | Public SOS form (offline-capable PWA), tracking; staff console: ops, SOS detail, wearables, ROV missions, weather, analytics, admin |
| Command server | `src/backend/app` | REST `/api/v1`, WebSocket `/ws`, auth, dispatch, telemetry ingest, alerts, background jobs |
| Wearable ML runtime | `src/ml/wearable` | 5 Tier-1 heads (stress, fall, activity, HR-trust, rhythm) + Tier-2 fusion state machine (in-process) |
| Weather | `src/ml/weather` | p10/p50/p90 forecasts to 48 h, hazards, flood-risk index |
| Wearable firmware | `src/firmware` | ESP32 band; 1.5 s frames, offline queue, SOS button, buzzer, local web UI |
| ROV bridge | `src/rov/bridge.py` | Serial bridge between physical ROV and server; legacy desktop console `src/rov/communication/serial_interface.py` |
| ROV vision worker | `src/cv/vision` | YOLOv8n + Haar/LBPH + pinhole distance on ROV camera |
| Replay simulator | `src/backend/app/tools/simulate.py` | Streams real recorded sessions as virtual wearables |
| Database | SQLite (WAL) / PostgreSQL | Only hard dependency |
| External data | Open-Meteo forecast, archive, GloFAS Flood API | Weather + river discharge |

Field-side links (ARCHITECTURE §1 diagram): public phone → HTTPS/offline queue → API; feature phone → SMS → SMS gateway (Android phone/provider) → webhook → API; wearable → schema-2 frames + device key → API; ROV → serial → station bridge → bridge key → API; ROV camera → vision worker → annotated JPEG + detections + vision key → API. Server: API → services → wearable runtime / weather service / DB; scheduler with DB-lease leader election; API → static build + live events → web console.

Deployment shape today: **single-node monolith** (FastAPI + SQLite, in-process ML, scheduler and WebSocket hub) + separate vision worker + ESP32 firmware (`docs/RESILIENCE_AND_FUTURE_WORK.md` Part II intro).

#### 1.2 Technology stack (`docs/ARCHITECTURE.md` §5, `requirements*.txt`, `package.json`)

| Layer | Choices |
|---|---|
| Backend | Python 3.11+ (dev machine 3.13, Docker 3.12), FastAPI ≥0.115, uvicorn[standard], SQLAlchemy 2, Alembic ≥1.13, PyJWT ≥2.8, bcrypt ≥4.1, httpx, psycopg[binary] 3 |
| Data | SQLite WAL locally; PostgreSQL (16 in reference deploy) |
| ML serving | onnxruntime ≥1.17, numpy compiled forests, LightGBM ≥4.0 |
| CV | ultralytics YOLOv8n (≥8.3), opencv-contrib-python ≥4.11 (Haar + LBPH) |
| Frontend | React 18.3, react-router-dom 6.30, TypeScript 5.9 (strict), Vite 5.4, uPlot 1.6, Leaflet 1.9 (Stadia `alidade_smooth_dark` tiles, OSM fallback), lucide-react icons, IBM Plex Sans/Mono via @fontsource, hand-written service worker |
| Firmware | ESP32 Arduino on PlatformIO (espressif32 6.9.0 / Arduino core 2.0.17), FreeRTOS |
| ROV bridge | pyserial ≥3.5, httpx |
| Tooling/tests | pytest, pyflakes, pillow, jsonschema, platformio ≥6.1 |

#### 1.3 Design principles (`docs/PLATFORM_DESIGN.md` §1, `docs/ARCHITECTURE.md` §3)

- **CAP per data type:** SOS/assignments/team capacity/alerts = consistency-first (CP: ACID, optimistic locking, 503 instead of an uncommittable write). Telemetry = availability-first (AP: device never blocks; offline buffer; idempotent ingest). Real-time push = best effort (REST snapshot + WS deltas with per-topic `seq`; resync on gap).
- **Graceful degradation:** API runs without ML, weather or internet; only the DB is required; `/readyz` reports missing pieces.
- **Training equals serving:** same FeatureEngine for training windows and live frames; ONNX parity-checked.
- **Security:** short-lived JWT + rotating refresh with reuse detection; role re-read from DB per request; per-device/bridge/vision hashed keys; rate-limited public endpoints; every write audited.

---

### 2. End-to-end flows

#### 2.1 SOS: creation → resolution (code: `src/backend/app/services/sos.py`, `triage.py`, `api/routes.py`)

1. **Intake** (one of three channels):
   - **Web PWA** `POST /api/v1/sos` (public), optional `Idempotency-Key` header (≤80 chars). If the key was already accepted, the cached response is returned *before* the rate limit (`routes.py submit_sos`). Then per-IP token bucket.
   - **SMS** `POST /api/v1/sms/inbound` (gateway, `X-SMS-Secret`), or admin `POST /sms/test`; parsed by `services/sms.py`; idempotency key = gateway message id or SHA-256 of `sender|text` (first 32 hex).
   - **Wearable SOS button**: `sos{active, press_id}` group inside telemetry frames → `telemetry.sos_button()` creates SOS with `source: wearable`, idempotency key `wsos:{device}:{boot}:{press_id}`, `device_verified=True`, plus critical `SOS_BUTTON` alert (risk 1.0).
2. **Create transaction** (`sos.create`, one `write_tx()`): idempotency check (key namespaced `sos:{source}:{key}`); triage score (verified linked device only); duplicate check; reference id `SOS-` + 6 chars from alphabet `23456789ABCDEFGHJKLMNPQRSTUVWXYZ` (no 0/O/1/I, "survive being read out over a phone line"; 5 retries on clash) (`security.new_reference_id`); tracking token `secrets.token_urlsafe(18)`, stored only as SHA-256; first `sos_events` row ("Request received via {source}, priority P{p} ({pts}/100)"); audit row `sos.create`; idempotency row. On a concurrent IntegrityError the stored response is returned. Then WS `sos/created`.
   - Response: `{reference_id, tracking_token, priority, status:'pending', duplicate_of}`.
3. **Re-triage + auto-dispatch** every 10 s (`sos_auto_triage` job → `auto_triage(max_priority=2)`): re-score open (`pending`/`triaged`) requests with waiting time + verified wearable state; log a `priority` event only on band change; then iterate in urgency order `(priority, -score, created_at)` and assign best team to P1/P2 non-duplicates; if no team: `awaiting_resources=True` and try **extreme-case auto-reallocation**; publish capacity snapshot on `system` topic when changed.
4. **Dispatcher actions**: assign (`POST /sos/{ref}/assign`), status changes (`PATCH /sos/{ref}/status`), notes, reallocation (`POST /sos/{ref}/reallocate`), confirm wearable link (`POST /sos/{ref}/link-device`).
5. **Status progression** pending → triaged → assigned → en_route → on_scene → resolved (or cancelled from any non-final), optimistic lock on every step; final states release the team slot; `resolved_at` set.
6. **Public tracking**: `GET /sos/track/{ref}?token=` returns status, priority, timestamps, team name (when assigned/en_route/on_scene/resolved), `eta_min: null` (ETA not computed), history of status + assign events. Same 404 for unknown ref or wrong token ("do not confirm that a reference exists"). Tracking page refreshes every 30 s (`docs/USER_GUIDE.md` §2).

#### 2.2 Wearable telemetry path (`src/backend/app/services/telemetry.py`; `docs/ARCHITECTURE.md` §2.2)

1. Band closes a schema-2 frame every 1.5 s, queues it (320 frames), uploads in batches ≤10 with `X-Device-Key`.
2. Device auth: SHA-256 of key looked up (`deps.current_device`; key length ≤128).
3. Parse each frame individually (`src/ml/wearable/schema.parse_payload`); malformed frames counted in `rejected` without failing the batch; `device_id` forced from the key, not the payload; `seq` must be int in [0, 2^53).
4. Under a per-device lock: read-only de-dup on `(device_id, boot_id, seq)` → ML + fusion **outside any DB transaction** (`DeviceRuntime.step`, per (device, boot); frames older than last processed seq are stored but not fused) → one short write transaction storing frames, state transitions (`device_states`), opening alerts on entry into a critical state, updating `last_seen/online/fw/boot_id/last_summary`, delivering commands.
5. If models failed to load: device state forced to `UNKNOWN`/`none` (not STABLE).
6. WS events: `devices/online`, `devices/state`, `alerts/opened`, and a throttled `devices/frame` summary (≤1 per device per 1.5 s, or on state change).
7. Response: `{accepted, duplicates, rejected, commands[], state{ml_health_state, ml_risk_score, alert_level}, sos?}`. `MAX_BATCH = 200` frames per request (413 otherwise).
8. Alert opening: one open/acked alert per (device, state); linked to the most urgent open **verified** SOS naming the device.
9. Liveness job every 15 s: device offline after 30 s; if last state not in {STABLE, UNKNOWN} → `LOST_CONTACT` alert (risk 0.9, evidence "last seen N s ago in STATE", "last risk x").
10. Retention job (6 h): deletes `telemetry_frames` older than 7 days (state transitions and alerts kept as "clinical record"); purges refresh tokens expired >1 day and idempotency keys >48 h; prunes ROV samples >48 h.

#### 2.3 ROV control path (`src/backend/app/services/rov.py`, `src/rov/bridge.py`)

Console → REST (`/rov/{id}/deploy|recall|stop|reset|takeover|release|control`) → `rov_units` row + `rov_commands` outbox (real units only) → bridge polls `POST /rov/bridge/telemetry` every 1 s with `X-ROV-Key` + telemetry + acks → response `{commands:[{id, lines:["forward_75"]}], mode, status}` → bridge writes lines to serial (9600 baud) → acks on next post. Simulated units are moved by the 1 Hz `rov_simulation` job. WS topic `rov` events: telemetry/deployed/recalled/stopped/control/mode/vision.

#### 2.4 Vision path (`src/cv/vision/*`, `src/backend/app/services/vision.py`, `src/cv/README.md`)

Camera (webcam index / MJPEG / RTSP / file / `demo`) → worker resizes to 640 px, runs YOLOv8n (conf ≥0.4, all 80 COCO classes), Haar faces + LBPH, pinhole distance → `POST /api/v1/rov/vision/frame` (`X-ROV-Vision-Key`, `{jpeg_b64, detections}`) → API keeps only the latest frame per ROV in memory (JPEG ≤600,000 B, must start `FF D8`; detections sanitised/bounded) → WS `rov/vision` summary ≤2/s per unit → browser obtains single-use 60 s ticket (`POST /rov/{id}/vision/ticket`) → `<img>` on `GET /rov/{id}/vision/stream?ticket=` (MJPEG `multipart/x-mixed-replace`, ≤8 fps, stream ends after 30 s without new frames; feed "stale" after 5 s).

---

### 3. Wearable band hardware and firmware (v2.2.0)

#### 3.1 Bill of materials (`src/firmware/README.md` "Bill of materials", `include/config.h`)

| Part | Role | Interface / address / pin | Notes |
|---|---|---|---|
| ESP32 DevKit (WROOM-32), board `esp32dev` | MCU, Wi-Fi | — | dual-core; tasks pinned to cores |
| MPU6050 (GY-521) | Accel + gyro | I²C 0x68 (AD0→GND) | WHO_AM_I accepted: 0x68, 0x70, 0x72, 0x98 (clones) |
| MAX30102 | PPG: HR, RR, SpO2 | I²C 0x57 | needs firm contact + light shielding |
| MAX30205 breakout | Skin temperature ±0.1 °C | I²C 0x48 (A0/A1/A2→GND) | thermal pad to skin |
| BMP388 breakout (BMP280 with lib change) | Pressure: fall height, submersion | I²C 0x77 (0x76 fallback auto-detected) | ePTFE membrane vent |
| Grove GSR v1.2 | EDA | ADC1 GPIO34 (ADC1_CH6) | |
| 2 water-contact pads + 1 MΩ + 1 kΩ | Immersion | ADC GPIO33 (sense, ADC1_CH5) + GPIO26 (excite) | pads ~5 mm apart, outer face |
| 100 kΩ + 100 kΩ (+100 nF) | Battery divider | ADC GPIO35 (ADC1_CH7) | divider ×2 |
| NEO-6M GPS | Location, geofence | UART1: GPIO16 RX ← GPS TX, GPIO17 TX → GPS RX, 9600 baud | TinyGPSPlus |
| Buzzer | Local alert | GPIO25 | NPN transistor if >12 mA |
| Momentary NO push button | SOS | GPIO27 to GND, `INPUT_PULLUP` | recessed/raised rim; `PIN_SOS_BUTTON=0` → DevKit BOOT for bench |
| 1S LiPo / 18650 + charger | Power | — | |

- Shared I²C on GPIO21 SDA / GPIO22 SCL at **400 kHz**, 4.7 kΩ pull-ups if breakouts lack them; bus mutex (`i2c_bus.cpp`). Address map: 0x48 MAX30205, 0x57 MAX30102, 0x68 MPU6050, 0x77 BMP388 — no conflicts.
- All analog inputs on **ADC1** because ADC2 is unusable with Wi-Fi active; `analogReadResolution(12)`; 11 dB attenuation.
- Missing sensors tolerated: boot log "not detected", fields sent as JSON `null`, `sys.*_ok=false`.
- **Purchase BOM spreadsheet** `assets/documents/hardware_specs.xlsx` (sheet1; currency not stated, prices look like INR; suppliers robu.in and "Swastik"): ESP32 ×2 @686; MPU6050 ×1 @165; GSR sensor ×1 @997; GPS NEO6M ×1 @290; MAX30102 ×1 @220; Buzzer ×21 @30 (quantity as written); **TOTAL 2388**. MAX30205, BMP388, button, pads, battery are not in this sheet. File metadata: creator "Akshay", last modified by "Thakur Akshayakumar 23BLC1120", modified 2025-09-11.
- Architecture diagram `assets/images/architecture.png` (v1-era block diagram): MPU6050 + MAX30102 on I²C, GSR FE (ADC/GPIO), NEO-6M (UART), status LED/buzzer (GPIO/PWM), user switch (GPIO), power Li-ion/Li-Po → power mgmt (BMS, buck/boost) → ESP32; firmware blocks FreeRTOS, HW drivers, networking, security, OTA/USB, NVS/SPIFFS, services; logic: Fall?/Geofence?/Vitals-Stress? → Arbiter (High/Medium/Low) → Latch+Buzzer+Badge / Notify / Advisory → Buzzer, LED/Haptic, Web UI, Log; "Pacemaker" block.
- `assets/images/infog-wearable.png` is an AI-generated infographic with garbled text ("ESP22", "ESP52", "MPUS050"); it claims water-resistant case, custom PCB, sealed switch, IMU 100–200 Hz, GPS 3–5 m, buzzer 75–78 dB @1 m. **Do not cite its numbers as specs** (they conflict with config.h: IMU 50 Hz).

#### 3.2 Sampling and task architecture (`src/firmware/src/main.cpp`, `include/config.h`)

| Task | Core | Priority | Stack | Tick | Work |
|---|---|---|---|---|---|
| `fast` | 1 | 5 | 6144 B | 10 ms (100 Hz) | PPG FIFO poll (MAX30102 at 100 Hz), IMU every 2 ticks (**50 Hz**), EDA every 5 ticks (**20 Hz**), buzzer every 10 ticks (100 ms), frame close every 150 ticks (**1.5 s**) |
| `slow` | 1 | 3 | 4096 B | 40 ms (25 Hz) | GPS UART poll, barometer (25 Hz), skin temp every 25 ticks (**1 Hz**), water every 12 ticks (**~2 Hz**), battery every 125 ticks (**0.2 Hz**) |
| `sos` | 1 | 4 | — | 10 ms | Button poll, 30 ms debounce, cue beeps |
| `net` | 0 | 2 | 16384 B | — | Wi-Fi, upload queue, remote commands, web UI, settings |

Timing must match `src/ml/wearable/schema.py` (`FRAME_PERIOD_S = 1.5`, `IMU_HZ = 50`, `SCHEMA_VERSION = 2`, `ACC_MAG_MAX_G = 16·√3 ≈ 27.7 g`).

#### 3.3 Sensor processing (per file)

- **IMU** (`imu.cpp`): register driver; DLPF ~21 Hz (reg 0x1A=0x04), sample rate 1 kHz/(1+19)=50 Hz, gyro ±2000 °/s, accel ±16 g (v1 was ±2 g / ±250 °/s, impacts clipped). Frame aggregates: acc max/min/mean/std (g), gyro max/mean (°/s), tilt from mean vector (acos(z/|v|)), `n` samples.
- **On-device fall detector** (edge safety net): states IDLE → FREEFALL (|a| < **0.5 g**) → impact (|a| > **3.0 g**) within **1000 ms** → SETTLE **1000 ms** (ignore rebound) → STILL window **2000 ms**: confirmed if std(|a|) < **0.15 g** and mean gyro < **40 °/s** → `fall_detected` latched (cleared by `reset_fall`).
- **PPG** (`ppg.cpp`): MAX30102 setup brightness 0x24, sampleAverage 1, red+IR, 100 Hz, pulse width 411, ADC range 16384. Finger contact if IR DC ≥ **30000**. Beats via SparkFun `checkForBeat`; RR timed by sample count (10 ms resolution), accepted **270–2000 ms**, ≤16 RR per frame; BPM EMA 0.9/0.1; BPM unavailable after **4000 ms** without a beat. SpO2: decimate 4 samples → 25 Hz, Maxim reference algorithm once per second over last 4 s (100 samples), accepted 50–100 %, stale after **3000 ms** (`spo2_valid`). Perfusion = (IRmax−IRmin)/IRmean·100. (v1 SpO2 was simulated random walk 95–99.9.)
- **EDA** (`eda.cpp`): Seeed formula scaled to 12-bit: R = ((4096 + 2r)·10000)/(cal_open − r), µS = 1e6/R; 10-sample moving average; open-circuit reference default **2048** until `calibrate_gsr_open`; baseline via `calibrate_gsr` (sit still ~2 min); slope over real frame length; `norm` = clip((µS−baseline)/baseline, 0, 1). Valid raw range 10–4090.
- **Skin temp** (`skintemp.cpp`): 1 Hz, valid 10–45 °C, reuse last value when a frame gets no new reading.
- **Barometer** (`baro.cpp`): BMP388 25 Hz ODR, pressure oversampling 2×, IIR coeff 3; frame mean hPa + max−min swing (`dmax_hpa`); valid 300–1300 hPa. Comment: a 0.5–2 m fall ≈ 0.06–0.24 hPa; submersion ≈ 98 hPa per metre of water.
- **Water** (`water.cpp`): excite pad A high for **300 µs** only during reading (limits electrolysis/corrosion), wet if ADC > **600** (~0.5 V across 1 MΩ), debounce **3** consecutive readings.
- **Battery** (`power.cpp`): `analogReadMilliVolts × 2 / 1000`; valid 2.5–4.5 V else null (USB only).
- **GPS** (`gps.cpp`): fix valid if age < 3000 ms; geofence via haversine (R = 6371 km); default fence centre **12.8239, 80.0467**, radius **0.1 km** (NVS `geo_lat/geo_lng/geo_rad_km`, `settings.cpp`).

#### 3.4 Frame (schema 2) (`src/firmware/README.md` "Payload")

Groups: `schema, device_id, fw, seq, uptime_ms, boot_id`; `imu{acc_max_g, acc_min_g, acc_mean_g, acc_std_g, gyro_max_dps, gyro_mean_dps, tilt_deg, n, fall_detected}`; `ppg{finger_on, bpm, rr_ms[], spo2, spo2_valid, perfusion}`; `eda{us, slope_us_s, baseline_us, raw, norm}`; `temp{skin_c}`; `baro{hpa, dmax_hpa}`; `water{wet}`; `power{batt_v}`; `gps{lat, lng, sats, hdop, breached}`; `sys{mpu_ok, max_ok, gsr_ok, temp_ok, baro_ok, gps_fix, queue, dropped}` (not ML contract); `sos{active, press_id, pressed_uptime_ms | cancelled}` (only when used). ~0.8 kB JSON per frame.

#### 3.5 Offline queue, upload batching, idempotency (`frame.cpp`, `telemetry.cpp`, `config.h`, firmware README)

- **Queue:** ring buffer `QUEUE_CAPACITY = 320` frames = **8 min** at 1.5 s, "~50 KB RAM"; mutex-protected.
- **Event-preserving overflow:** when full, drop the **oldest routine** frame (keeping seq order by shifting); if all are events drop the oldest. Event frame = SOS active/cancelled, `fall_detected`, `wet`, geofence `breached`, or `acc_max_g ≥ 3.0 g` (`EVENT_IMPACT_G`). Dropped count in `sys.dropped`.
- **Batching:** always batch form `{"frames":[…], "acks":[…]}`, up to **10 frames** (~8 kB), oldest first in seq order; online normally 1 frame/request; a full 320-frame backlog drains in 32 requests over a keep-alive connection (`setReuse(true)`). Frames popped only after HTTP 200 (`queue_pop_through(seq)`).
- **Idempotency:** server de-dups on (device, boot, seq). `seq` never repeats: firmware reserves blocks of **4000** seq numbers in NVS (one flash write ~every 50 min per README; comment says "~100 min"); reboot skips unused part (forward gap, never a repeat). `boot_id` increments every boot. Flash erase resets both (rotate key).
- **Backoff table:** 200 → pop, run commands, reset delay. 401/403 → retry every 60 s, web page "auth failed". 404 → 60 s. 408/429/5xx/timeout (HTTP timeout **5 s**)/no connection → exponential backoff with jitter 1, 2, 4, 8, 16, 30 s cap (random between half and full step). Other 4xx (400/413/422) → resend one frame at a time (halves for 413) to isolate bad frame; single rejected frame dropped. `Retry-After` respected up to 60 s. While SOS unacknowledged every wait capped at **3 s**.
- **Server state:** response `state` shown on local page; expires after **60 s** without update.
- **Transport:** HTTPS via `WiFiClientSecure` with `setInsecure()` (no certificate validation; CA pinning is future work §11 of resilience doc). Wi-Fi reconnect attempt every 10 s.
- Boot checks: warns if `DEVICE_KEY` is `CHANGE_ME` or URL does not end with `/api/v1/telemetry`; build fails if `DEVICE_KEY` missing (`secrets.h`, gitignored; template `secrets.example.h`).

#### 3.6 SOS button behaviour (`sos.cpp`, `config.h`, firmware README "SOS button")

| Action | Condition | Result |
|---|---|---|
| Raise | Hold ≥ **1500 ms** or **3** presses within **2000 ms** | New `press_id` (NVS counter `sos_n`, never repeats), 2 short beeps, current frame closed early, network task woken to send immediately |
| Waiting | Not acknowledged | 100 ms beep every **10 s**; upload retry ≤ **3 s** |
| Received | Response `sos.received:true` with matching `press_id` | One 800 ms beep (first ack only), reminders stop, web page shows reference id (≤23 chars) |
| Cancel | A *new* press held ≥ **5000 ms** while active | Two 400 ms beeps; frames carry the cancel until acked or for **10** frames |
| Ignored | Presses <5 s while active; holding the raising press past 5 s | — |

Polling 10 ms, debounce 30 ms, task core 1 priority 4. SOS frames are event frames. While unacknowledged, **every frame of every request** carries the `sos` group so it reaches the server even if a backlog is draining. SOS does not survive a reboot. Late acks for older press ids ignored. Server side: creates one SOS per (boot, press_id) (+40 triage points → ≥P2, band GPS or last known location, emergency type `flood` if band wet else `other`), critical `SOS_BUTTON` alert; band cancel adds a note "Wearer cancelled the SOS on the band (held 5 s). Check before standing down." and resolves the alert but **leaves the request open** (`telemetry.sos_button`, `_sos_cancelled`).

#### 3.7 Buzzer patterns (`buzzer.cpp`, firmware README "Buzzer", USER_GUIDE §3)

Non-blocking, updated every 100 ms from the fast task; priority order (higher owns buzzer):

| Trigger | Sound |
|---|---|
| SOS cue (one-shot ≤1.1 s, starts with 100 ms gap) | Raised `0110011` = 2×200 ms; Received `011111111` = 800 ms; Cancelled `01111001111` = 2×400 ms; Reminder `01` = 100 ms every 10 s (never interrupts another cue). A lower cue never interrupts a higher one. |
| Fall latched on device, or geofence breached | Continuous until `reset_fall` / back inside fence |
| `buzz` command or local "Test buzzer" | Continuous for `ms` (default 1000, cap **10 000 ms**) |
| Server `alert_level == "critical"` | Three 200 ms beeps every 2 s (phase <1000 ms of a 2000 ms cycle), expires 60 s after last report |

#### 3.8 Remote commands (`remote_cmd.cpp`, `schemas.CommandIn`)

`reset_fall`, `calibrate_gsr`, `calibrate_gsr_open`, `set_geofence` (`lat`, `lng`, `radius_km`; legacy `latitude`, `longitude`, `radius` accepted), `buzz` (`ms`). Delivered in the telemetry response (server: ≤10 per response, re-delivered if not acked within 30 s; outbox `queued → delivered → acked`). Device acks every id next request (≤16 pending acks), including unknown actions; remembers last 16 ids to avoid re-executing a re-delivered command. Ids echoed as received (number or string).

#### 3.9 Local web UI (`webui.cpp`)

`http://<band-ip>/` on same Wi-Fi: SOS line (`none`, `sending`, `received SOS-…`, `cancelled`), sensors, upload link status, server health state, actions `/reset_fall`, `/cal_gsr`, `/cal_gsr_open`, `/buzz`, `POST /set_geofence`, `/frame.json`.

#### 3.10 Build, memory, power

- `platformio.ini`: `espressif32@6.9.0`, `board = esp32dev`, framework arduino, monitor 115200, partitions `min_spiffs.csv` (OTA-sized slot), `-Wall -DCORE_DEBUG_LEVEL=1`; libs SparkFun MAX3010x 1.1.2, Adafruit BMP3XX 2.1.5, BusIO 1.17.4, Unified Sensor 1.1.15, ArduinoJson 7.2.1, TinyGPSPlus 1.1.0.
- **fw 2.2.0 build** (`src/firmware/README.md`): SUCCESS; RAM static **111,684 B / 327,680 B = 34.1 %**; Flash **1,044,777 B / 1,966,080 B = 53.1 %**. fw 2.1.0: RAM 106,308 B = 32.4 %. P6-era 2.1.0 earlier build: RAM 22.7 %, flash 52.9 % (context log, before the 320-frame queue). Increase 2.1→2.2 mostly SOS fields in each of the 320 queued frames.
- **Power:** 1S LiPo/18650 + charger; battery divider read at 0.2 Hz; no measured battery-life figure recorded (future target "24 h minimum" via duty-cycling PPG/GPS, resilience §9.2). Low battery → `SENSOR_FAULT` suppresses cardiac rules (resilience §3).
- **Hardware validation status:** "compiles, untested on hardware" / "untested on wired hardware" (context log P0/P1/P7 row; `docs/career/TRIDENT_CAREER_NOTES.md` §4).
- v1 → v2 changes table: firmware README "What changed from v1" (SpO2 simulated→measured; EMA BPM→BPM+RR; single reading ±2 g→50 Hz ±16 g aggregates; fall spike+calm→free-fall/impact/stillness; raw EDA→µS; new MAX30205/BMP388/water/battery; blocking loop with `delay(20)`→FreeRTOS tasks; frames lost offline→320-frame queue; hard-coded credentials→`secrets.h`; unauthenticated `/api/telemetry/wearable`→`/api/v1/telemetry` with key).

#### 3.11 Enclosure / CAD / media assets (paths)

| Path | Content |
|---|---|
| `assets/images/cad/wearable-isometric.jpg`, `wearable-isometric-line-diagram.jpg` | Band isometric (render + line drawing) |
| `assets/images/cad/wearable-disassembled-view.jpg`, `wearable-disassembled-view-line-diagram.jpg` | Exploded view |
| `assets/images/cad/wearable-pcb-cad.jpg`, `wearable-pcb-cad-line-diagram.jpg` | PCB CAD |
| `assets/images/cad/wearable-perspective-view.jpg` | Perspective |
| `assets/images/cad/wearable-sideview.jpg`, `wearable-sideview-line-diagram.jpg` | Side view |
| `assets/images/cad/rov-isometric-view.jpg` | ROV isometric CAD |
| `assets/images/cfd.jpg` | ROV CFD flow streamlines (SolidWorks-style flow simulation of the frame) |
| `assets/images/architecture.png` | Band block/logic diagram (v1 era) |
| `assets/images/infog-trident.png` | System infographic (acronym, "TRIDENT AURA" ROV) |
| `assets/images/infog-wearable.png` | Wearable infographic (AI-generated, garbled) |
| `assets/images/band_ai_img.jpg` | Band image (AI) |
| `assets/images/dashboard-photo.jpg`, `wearable-live-telemetry-data.png` | v1 dashboard photo, v1 live telemetry screenshot |
| `assets/images/console-operations.png`, `console-public.png`, `console-rov-missions.png`, `console-wearable.png`, `console-weather.png` | v2 console screenshots (2026-10-31) |
| `assets/images/team-photo.jpg` | Team photo (6 people with ROV prototype; PVC-pipe frame, white thruster pods) |
| `assets/images/TRIDENT_logo.png` | Logo |
| `assets/videos/wearable-demo.mp4` (10.7 MB), `Wearable-cad.mp4` (5.6 MB, CAD flythrough), `finalrov.mp4` (47.9 MB, "ROV Field Deployment") | Videos |
| `assets/documents/hardware_specs.xlsx` | Purchase BOM (above) |

No native CAD source files (STEP/SLDPRT/Gerber) are in the repo — only rendered JPGs.

---

### 4. ROV

#### 4.1 Hardware (what is documented)

- Current README: "Serial-controlled thrusters and lights, plus a camera for the vision worker" (`README.md` Hardware table).
- Historic README (commit `4ab536f`): "underwater ROV (Arduino Uno, 4x thrusters, LiPo)"; "undergoes rigorous fluid dynamics analysis to ensure stability under water currents" (CFD image). No ROV firmware source is in the repo or its history (only v1 wearable `.ino` files).
- Station serial protocol: 9600 baud, newline-terminated text. Commands `<direction>_<speed>` with direction ∈ forward/backward/left/right/up/down, speed 0–100 (e.g. `forward_75`); stop = `forward_0` + `up_0`; lights `on` / `off`. Telemetry lines `Temperature: 27.4`, optional `Depth:`, `Heading:`, `Battery:` (`src/rov/bridge.py`, `serial_interface.py`).
- Camera example URL `http://192.168.4.1:81/stream` (an ESP32-CAM-style MJPEG URL in docs; camera model not recorded).

#### 4.2 Modes and safety (`services/rov.py`; PLATFORM_DESIGN "ROV missions")

| Item | Value |
|---|---|
| Statuses | idle, deploying, on_mission, returning, stopped |
| Modes | `auto` (navigate to target on deploy / home on recall), `manual` (exclusive pilot) |
| Deploy preconditions | unit idle or returning; battery ≥ **30 %**; SOS must have coordinates |
| Takeover | dispatcher+; 409 `control_held` if another pilot holds it unless admin; takeover stops thrust |
| Release | pilot or admin; back to auto, thrust stopped |
| Control | pilot only (and dispatcher role); moves refused while `stopped`; speed_pct 0–100 (API default 50; UI slider default 40 %) |
| STOP | any responder+ at any time; status `stopped`, thrust off; queues `stop` for real units |
| Reset | clears stop → `returning` home on autopilot (does **not** resume mission) |
| Dead-man | `DEADMAN_S = 120` s without a control command in manual → thrust cut (simulated) / `stop` queued with actor `dead-man` (real) |
| Bridge link loss | bridge writes `forward_0`, `up_0` after **5 s** without server (`LINK_LOSS_STOP_S`) |
| Link status | `simulated`; `online` if last bridge post <10 s ago (`BRIDGE_OFFLINE_S`); else `offline` |
| Low battery | on mission and <20 % → returns home |
| Audit | deploy, recall, stop, reset, takeover, release, stops/lights (moves not audited: too frequent) |

#### 4.3 Simulation constants (1 Hz tick)

`SIM_SPEED_MPS = 8.0` (compressed time, "boat-like"), auto transit at 75 % thrust; `TURN_DEG_PER_S = 20`; `DEPTH_RATE_MPS = 0.25`; `MISSION_DEPTH_M = 1.5` station-keeping; surface transit depth ~0.4 m; battery drain (0.02 + 0.06·speed)%/s moving, recharge 0.2 %/s idle; simulated water temp = air temp − 1.5 − 0.3·depth, first-order lag 0.05. Arrival adds SOS note "{ROV} arrived on scene"; deploy adds "{ROV} deployed (autonomous transit)".

#### 4.4 Telemetry and track

RovUnit fields: id, name, status, mode, pilot, battery_pct, latitude, longitude, depth_m, heading_deg, water_temp_c, speed_pct, thrust, lights_on, link, last_seen, target, home, mission_reference_id, team_id, video_url, simulated, mission_started_at, vision{active, fps, last_frame_at, persons, faces, objects≤12, model}, updated_at. Bridge input bounds: depth 0–1000 m, heading 0–360, water temp −5–60 °C, battery 0–100 %, lat/lng valid. **1 Hz track** in `rov_samples` (`GET /rov/{id}/track?minutes=30`, 1–1440): t, lat, lng, depth_m, heading_deg, battery_pct, water_temp_c; kept 48 h.

#### 4.5 Mission flow and missions view

Dispatcher deploys to SOS → autonomous transit → on_mission (hold depth) → optional manual takeover → recall/return home. `/missions` returns every ROV active or manual with its SOS, team, and **victims** = mission SOS + every open SOS assigned to the ROV's team, each with live wearable (`device_out`). UI shows a red "victim critical" chip if any victim's band is critical; telemetry greyed "stale" after 5 s (USER_GUIDE §9).

Seeded fleet (`seed.py`): `ROV-001` home 13.0067, 80.2575 (team Chennai ROV Alpha); `ROV-002` 12.9791, 80.2210 (Chennai ROV Beta).

Legacy (v1): Flask backend auto-spawned the PyQt6 station app in `--emergency-mode` for priority ≥4 water emergencies, 12-second countdown, thrusters at 75 % (git history `docs/TEACHING_SYSTEM_OVERVIEW.md` at commit `bc1de03`, `docs/ROV_OPERATIONS.md` at `f857631`).

---

### 5. Backend algorithms and constants

#### 5.1 Triage score 0–100 (`src/backend/app/services/triage.py`)

| Factor | Points |
|---|---|
| Wearable SOS button (`source == 'wearable'`) | +40 ("SOS button pressed on wearable") |
| Emergency type | tsunami 25, dam-breach 25, flood 15, medical 15, storm 12, water-level-rising 12, coastal-erosion 5, other 5 |
| Injured n ≥1 | min(25, 10 + 5·(n−1)) |
| People to rescue n >1 | min(10, 2·(n−1)) |
| Vulnerabilities | medical 12, pregnant 8, disabled 8, elderly 6, children 6 |
| Water availability | none 10, critical 7, limited 2, adequate 0 |
| Food availability | half of the same table (integer division): none 5, critical 3, limited 1 |
| Age ≥70 or ≤5 | +4 |
| Linked **verified** wearable | critical +30 ("wearable: STATE"), advisory +5, offline +3 |
| Ageing (waiting ≥5 min) | min(20, 2·floor(wait/5)) ("waiting N min") |
| Cap | total = min(100, sum) |

**Priority mapping:** `PRIORITY_BANDS = (15, 30, 45, 60)`, priority = 5 − #bands ≤ score: **P1 ≥60, P2 45–59, P3 30–44, P4 15–29, P5 <15**. P1 = most urgent. Reasons list is human-readable and stored (`priority_reasons`). Docstring: replaces old additive 1–5 counter that "saturated at 5".

Legacy v1 algorithm (for history only; `docs/career/RESUME_BULLETS_TCS_PRIME.md`, `RESUME_BULLETS_FOODHUB.md`): base 1, +2 injuries, +2 medical, +1 per vulnerability, +1 food/water scarcity, +3 tsunami/dam-breach, +2 flood/storm, cap 5, auto-dispatch AUTO_DEPLOY team for priority ≥4 (higher = more urgent in v1).

#### 5.2 Duplicate detection (`sos.py _duplicate_of`)

Open (non-final) request created in last **2 h** with same phone, or within **100 m** (equirectangular metres, 111,320 m/deg, cos-lat corrected; SQL bounding-box prefilter, ≤50 candidates). Linked as `duplicate_of`, reason "possible duplicate of SOS-…", **never auto-dispatched** and excluded from capacity waiting list; not merged — dispatcher decides.

#### 5.3 Auto-dispatch (`sos.auto_triage`, `_best_team`)

- Runs every 10 s; considers `pending`/`triaged`; auto-assigns only priority ≤ `auto_assign_max_priority = 2` (P1, P2) and non-duplicates.
- Order: `(priority asc, priority_score desc, created_at asc)` — "P1 before P2, higher score first, then first come".
- Team choice: available teams with `current_load < capacity`; key = (AUTO_DEPLOY first **only for P1**, relative load `round(load/capacity, 2)`, straight-line degree distance). Flush after each assignment so next request sees new load. Event actor `auto-dispatch`.

#### 5.4 Capacity states and suggestions (`sos._capacity`)

- `free` = available teams with load < capacity. Status: **exhausted** if no free team and P1/P2 non-duplicate requests waiting; **strained** if free ≤1; else **ok**.
- Suggestions (only when no free team): for each waiting request in urgency order, a donor = `assigned` (not en route) request with priority ≥ waiting priority **+2**, ordered lowest priority first then most recently updated; each donor used once. Human-confirmed only. Snapshot pushed on WS `system` (`event: capacity`) only when it changes (ignoring `waiting_min`).
- Manual move `POST /sos/{ref}/reallocate` (`sos.reallocate`): single transaction; donor must still be `assigned` with that team; target must be pending/triaged; donor priority must be strictly lower (numerically greater) than target; both versions checked (`version`, `from_version`); team row `SELECT … FOR UPDATE`; donor → `triaged` without team ("back in the queue"), target → `assigned`, `awaiting_resources=False`; audit `sos.reallocate`.

#### 5.5 Extreme-case automatic reallocation (owner policy 2026-10-31) (`sos._extreme`, `_auto_reallocate_if_extreme`)

All must hold:
1. Request is **P1** with score ≥ **80** (`EXTREME_MIN_SCORE`).
2. Has a **verified** linked device whose `alert_level == 'critical'` and `risk ≥ 0.85` (`EXTREME_MIN_RISK`).
3. Device has been in that state ≥ **60 s** (`EXTREME_MIN_STATE_S`, from latest `device_states` row of that state).
4. Environmental corroboration (≥1): emergency type ∈ {flood, tsunami, dam-breach, water-level-rising}; any active weather hazard with level `warning`; any river (Adyar, Cooum, Kosasthalaiyar) with trend `rising`.
5. No free team (reached only from the no-team branch).

Donor: an `assigned` (not en route) request with priority ≥ **4** (P4/P5), choosing lowest priority, then lowest score. Effects: donor → triaged with note "Auto-reallocated (extreme case): {team} moved to {ref}; back in the queue"; target → assigned with evidence text; audit action `sos.reallocate_extreme` with `{team_id, from, evidence}`; evidence list e.g. `['P1 85/100', 'wearable CARDIAC_ARREST risk 0.91 for 75 s', 'flood emergency', …]`.

#### 5.6 SOS state machine (`sos.TRANSITIONS`)

| From | Allowed to |
|---|---|
| pending | triaged, assigned, cancelled |
| triaged | assigned, cancelled |
| assigned | en_route, triaged (= unassign, releases team), cancelled |
| en_route | on_scene, cancelled |
| on_scene | resolved, cancelled |
| resolved / cancelled | — (final) |

`TEAM_BUSY = {assigned, en_route, on_scene}`. Status PATCH cannot set `assigned` (use assign endpoint). Assign refused while en_route/on_scene/final. Same-status → 409. Responders only on requests assigned to their own team (403 otherwise).

#### 5.7 Optimistic locking and ACID

- `_bump`: `UPDATE sos_requests SET version=v+1 WHERE id=… AND version=v`; rowcount ≠1 → rollback + **409 Conflict** with `{current: detail}`.
- `write_tx()` = one ACID transaction: row + timeline event + team load + audit; WS published only after commit (`src/backend/README.md`).
- SQLite: `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `BEGIN IMMEDIATE` for writes (`db.py`). PostgreSQL: READ COMMITTED, `pool_size=10, max_overflow=10, pool_pre_ping`, `SELECT … FOR UPDATE` on team rows.
- Locked/read-only/unreachable DB → **503** with `Retry-After: 2` (`errors.py`).

#### 5.8 Idempotency summary

| Operation | Mechanism | Retention |
|---|---|---|
| SOS (web/SMS/wearable) | `idempotency_keys` row, key `sos:{source}:{key}` (namespaced after QA) | purged after **48 h** (`auth.IDEMPOTENCY_KEEP`) |
| Telemetry | unique `(device_id, boot_id, seq)` `uq_frame_device_boot_seq` | frames 7 days |
| Device commands | outbox queued → delivered → acked; redeliver after 30 s | — |
| ROV commands | outbox queued → delivered → acked by bridge | — |
| Band SOS cancel | key `wsos-cancel:{dev}:{boot}:{press}` | — |

#### 5.9 Scheduler with DB-lease leader election (`src/backend/app/jobs.py`)

| Job | Interval | Initial delay | Function |
|---|---|---|---|
| `device_liveness` | 15 s | 1 s | mark offline after 30 s; LOST_CONTACT |
| `sos_auto_triage` | 10 s | 3 s | re-score + auto-dispatch P1–P2 |
| `alert_escalation` | 30 s | 1 s | flag open alerts unacked >120 s |
| `rov_simulation` | 1 s | 1 s | ROV tick, dead-man, 1 Hz track |
| `weather_refresh` | 30 min | 2 s | Open-Meteo + forecast |
| `public_data` | 3 h | 5 s | GloFAS river discharge |
| `retention` | 6 h | 60 s | frames >7 d, tokens, idempotency >48 h, ROV samples >48 h |

- Lease table `scheduler_leases(job, holder, expires_at, last_run_at, last_status)`; holder = `hostname:pid`.
- Acquire: conditional `UPDATE … WHERE job=? AND (holder=me OR expires_at<now)`; due if `now − last_run_at ≥ every_s − 0.5`; INSERT for a new job; IntegrityError = another replica won.
- **Lease TTL** = `min(60, max(10, 10·every_s))` → 10 s for fast safety jobs, 60 s (`LEASE_TTL_S`) otherwise; check every `min(every_s, 10 s)`.
- `last_run_at` moves only on success. Failure → **backoff 5, 10, 20 … 300 s** (capped by interval). Clean shutdown sets `expires_at=now` for immediate takeover. Jobs run in worker threads (`asyncio.to_thread`). Fix from live testing: earlier leases blocked takeover for 3× interval (context log).

#### 5.10 WebSocket hub (`src/backend/app/realtime.py`, `main.py /ws`)

- `/ws?token=<access>`; topics `sos, alerts, devices, weather, rov, system`; message `{"type":"event","topic","seq","ts","data"}`, per-topic monotonic `seq`; `hello` on connect includes current seqs; client may `subscribe` and `ping` (→`pong`).
- Per-client queue max **500**; slow client dropped (close 1013) and must resync. ≤**10** sockets per user (close **4429**). Foreign Origin → **4403**; bad token → **4401**. Account re-checked every **30 s** (active and role unchanged) else 4401; logout/role change/deactivation also disconnects user. Thread-safe publish from jobs via `call_soon_threadsafe`.
- Client side (`api/live.ts`, web README): REST snapshot per topic on connect with event buffering; gap → reload topic; reconnect exponential backoff with jitter 1–30 s; watchdog closes socket silent for 70 s.

#### 5.11 Auth (`security.py`, `services/auth.py`, `config.py`)

- Passwords bcrypt rounds=12; constant-time dummy hash for unknown users (no username timing leak).
- Access JWT HS256, issuer `trident`, claims `sub, role, iss, iat, exp, jti(8-byte hex), typ:'access'`; TTL **900 s (15 min)** (`TRIDENT_ACCESS_TTL_S`).
- Refresh token opaque `token_urlsafe(48)`, stored SHA-256 with `family_id` (12-byte hex), TTL **604,800 s (7 days)**; rotates every refresh; reuse of a rotated/revoked token revokes the whole family (audit `auth.refresh_reuse`, 401 `session_revoked`). Logout revokes family and closes the user's sockets. Password/role/deactivation change revokes all refresh tokens and disconnects sockets.
- Role re-read from DB on every request (`deps.principal_from_token`); role ranks viewer 0 < responder 1 < dispatcher 2 < admin 3.
- Production refuses to start without `TRIDENT_JWT_SECRET`; dev uses a random per-process secret.
- Machine keys: `tdk_` + `token_urlsafe(32)`, only SHA-256 stored, shown once, issuing replaces old key (device `X-Device-Key`, bridge `X-ROV-Key`, vision `X-ROV-Vision-Key`). Lookup by hash.
- Failed logins audited (`auth.login_failed`).
- Frontend: access token in memory, refresh token in `localStorage`; single-flight refresh on 401 then retry once (web README). Future: HttpOnly cookie (resilience §11).

#### 5.12 RBAC matrix (code `api/routes.py` dependencies; doc `docs/USER_GUIDE.md` §1)

| Action | admin | dispatcher | responder | viewer | public/machine |
|---|:-:|:-:|:-:|:-:|:-:|
| Submit SOS, track (token), public summary, contacts | | | | | public |
| Read SOS, devices, alerts, teams, weather, analytics, ROV, missions | ✓ | ✓ | ✓ | ✓ | |
| Change SOS status | ✓ | ✓ | own team only | – | |
| Add notes | ✓ | ✓ | ✓ | – | |
| Assign, reallocate, link/confirm device, patch team | ✓ | ✓ | – | – | |
| Device commands | ✓ | ✓ | – | – | |
| Ack / resolve alerts | ✓ | ✓ | ✓ | – | |
| ROV deploy/recall/reset/takeover/release/control | ✓ | ✓ | – | – | |
| Take over from another pilot | ✓ | – | – | – | |
| ROV STOP | ✓ | ✓ | ✓ | – | |
| Users, device register/rotate, bridge key, vision key, audit log, SMS test | ✓ | – | – | – | |
| Telemetry ingest | | | | | device key |
| Bridge telemetry / vision frame | | | | | bridge key / vision key |
| SMS inbound | | | | | `X-SMS-Secret` |

#### 5.13 Rate limits (`ratelimit.py`, `routes.py`)

In-process token buckets per client IP (`request.client.host`; requires proxy overwriting X-Forwarded-For + `--proxy-headers`):

| Bucket | Rate | Burst |
|---|---|---|
| Public SOS | 20/min (`TRIDENT_SOS_RATE_PER_MIN`) | max(10, min(rate, 1000)) → effectively 20 |
| Login and refresh | 10/min | max(5, min(rate, 1000)) |
| Tracking | 60/min | 60 |
| SMS webhook | 120/min | 30 (checked before secret: limits brute force) |

429 with `Retry-After`; bucket map cleared above 50,000 keys (memory bound). Idempotent SOS retry answered before the limit.

#### 5.14 Request hardening (`observability.py`, `main.py`, `schemas.py`)

- Body limits: default **256,000 B**; `/api/v1/telemetry` and legacy `/api/telemetry/` **2,000,000 B**; `/api/v1/rov/vision/frame` **1,000,000 B**.
- Headers: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, `Permissions-Policy: geolocation=(self), camera=(), microphone=()`, CSP `default-src 'self'; img-src 'self' data: blob: https://*.basemaps.cartocdn.com https://*.tile.openstreetmap.org http: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' ws: wss:; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'`; API responses `Cache-Control: no-store`; `X-Request-ID` sanitised and echoed.
- CORS allow-list (default `http://localhost:5173,http://127.0.0.1:5173`), credentials off, methods GET/POST/PATCH/DELETE.
- Error envelope `{"error":{"code","message","details"},"request_id"}`; codes 400/422, 401, 403, 404, 409, 413, 429, 503; unexpected → one clean 500.
- Pydantic strict validation: e.g. SOS name 1–128, age 0–120 optional, phone 6–20 `[0-9+()\- ]`, address 3–500, pincode optional ≤12, people 1–500, injured 0–500, notes ≤2000; usernames 3–64 `[a-zA-Z0-9_.-]`, passwords ≥10; team capacity 0–100; device id 3–64 `[A-Za-z0-9_.:-]`; bridge video_url must be http(s).
- Lists: `{items, next_cursor}` base64 offset cursor, `limit` ≤200, offset ≤1,000,000.
- Time series bounded: minute buckets ≤1 day, hour ≤31 days, day ≤730 days; bad `since` → 422.
- Logs: JSON lines in production with `request_id`; filter replaces `token=` and `ticket=` query values with `***`.
- `/api/docs` and `/api/openapi.json` hidden in production unless `TRIDENT_EXPOSE_DOCS=true|1`.

#### 5.15 Alerts (`services/alerts.py`, `telemetry.py`)

Opened for: entry into a critical fusion state; `LOST_CONTACT`; `SOS_BUTTON`. Advisory states never open alerts. Status open → acked → resolved (resolve auto-acks). Escalation: open and unacked > **120 s** (`alert_escalate_s`) → `escalated=true`, audit `alert.escalate`, WS `escalated` (console-only signal, no external paging). Alert record `{id, device_id, state, risk, evidence, status, opened_at, acked_by?, acked_at?, resolved_at?, sos_reference_id?}`.

Fusion states consumed by the platform (`docs/USER_GUIDE.md` §1): STABLE (none), ELEVATED_STRESS (advisory, ml), CONCUSSIVE_STASIS, CRUSH_ENTRAPMENT, CARDIAC_ARREST, HEMORRHAGIC_SHOCK (critical, ml+rule), ASPIRATION_HYPOXIA, HYPOTHERMIA_RISK (critical, rule), LOST_CONTACT and SOS_BUTTON (alert types), UNKNOWN (no models).

#### 5.16 LOST_CONTACT rule

Device online, `last_seen` older than **30 s**, and state ∉ {STABLE, UNKNOWN} → critical alert `LOST_CONTACT`, risk 0.9, evidence "last seen {secs} s ago in {state}", "last risk {r}" (`telemetry.mark_offline`). Rationale: "silence from someone in a non-stable state is itself an emergency (dead battery, crushed or submerged device, out of range)". Advisory states do trigger it (only STABLE/UNKNOWN excluded).

#### 5.17 SMS format and parser (`services/sms.py`)

- Compact format: `SOS <lat>,<lng> P<people> I<injured> T<type> <note>`, ≤160 chars (example `SOS 13.0120,80.2410 P3 I1 Tflood elderly, ground floor flooded`).
- Parser: strips leading `sos`; coordinates regex `(-?\d{1,2}\.\d{2,})\s*[, ]\s*(-?\d{1,3}\.\d{2,})` validated to ranges; field regex `\b([pit])\s*[:=]?\s*([a-z0-9-]+)` case-insensitive (so `p 2`, `P:2` work); people clamped 1–500, injured ≤500 and ≤ people; type ∈ {flood, tsunami, dam-breach, storm, water-level-rising, coastal-erosion, medical, other}, bare type word in note also counts; vulnerability keywords: elderly/old→elderly, child/children/baby→children, pregnant, disabled/wheelchair→disabled, medical/injured/bleeding/diabetic→medical; note ≤500 chars.
- Request built with name `SMS <last4>`, food/water `adequate` (unknown, not scored up), city `Unknown (SMS)`, address = note or "Sent by SMS, no address given"; device link never verified.
- Reply ≤300 chars: `TRIDENT: request SOS-XXXXXX received, priority Pn. [Send your location as SOS <lat>,<lng> if you can.] Track: {public_url}/track/{ref}?token=…`.
- Webhook off (503) unless `TRIDENT_SMS_SECRET` set; admin `POST /sms/test` works without a gateway. Gateway plan: Android phone with SMS-gateway app (sms-gate.app) or provider (MSG91, Twilio, Gupshup, Exotel).

#### 5.18 Health, readiness, metrics (`main.py`, `docs/DEPLOYMENT.md` §7)

- `GET /healthz` → `{"status":"ok","version":"2.0.0"}`.
- `GET /readyz` → `{ready, checks{database{ok, writable}, wearable_ml{ok, loaded, heads, error}, weather{ok,…}, jobs[leases]}}`; 200 only if DB ok **and writable** (SQLite: `BEGIN IMMEDIATE` with 0.5 s timeout then rollback; PostgreSQL: `SHOW transaction_read_only == off`), else 503; ML/weather don't affect readiness. Production returns only `ok` flags.
- `GET /metrics` Prometheus text (`version=0.0.4`): `http_requests_total{method,route,status}`, `http_request_seconds` histograms, `telemetry_frames_total{result=accepted|duplicate|rejected}`, `job_runs_total{job,result}`, `job_seconds`, gauge `ws_clients`. Unauthenticated: block at proxy.

#### 5.19 Data model (`models.py`, migrations)

18 tables: `users, refresh_tokens, teams, sos_requests, sos_events, devices, telemetry_frames, device_states, device_commands, alerts, rov_units, rov_commands, rov_samples, public_data_cache, idempotency_keys, scheduler_leases, audit_log, emergency_contacts`. Index `ix_frames_device_time(device_id, received_at)`.

Alembic revisions (`src/backend/migrations/versions/`): `298adfd874df` initial schema (2026-10-30 22:59) → `dcea3b36ef46` ROV missions, telemetry track, public data cache (2026-10-30 23:09) → `5de2bad2e48d` SOS source, duplicates, awaiting resources, optional age (2026-10-31 00:54) → `5d9009ff556a` ROV vision key (2026-10-31 02:09) → `ec4472fc90c9` SOS device link verified (2026-10-31 02:26). Migrations run automatically at startup (`alembic upgrade head`, `migrate.py`); SQLite batch table rebuild for FK changes.

Seed (`seed.py`, idempotent each start): 5 teams — Chennai ROV Alpha (ROV Water Rescue, Adyar 13.0067/80.2575, cap 3, **AUTO_DEPLOY**), Chennai ROV Beta (Velachery 12.9791/80.2210, cap 2), Coastal Rescue Marina (13.0500/80.2824, cap 4), Medical Response North (Perambur 13.1180/80.2330, cap 4), Water & Supplies Unit (T. Nagar 13.0418/80.2341, cap 6) (others MANUAL_DEPLOY); 2 ROVs; contacts 112, 101, 108, 100, 1070 (TN SDMA); demo users admin/dispatcher/responder(team ROV Alpha)/viewer, password `trident-demo-2026` (dev only).

#### 5.20 Rivers / public data (`services/public_data.py`)

Rivers Adyar (13.005, 80.205), Cooum (13.072, 80.240), Kosasthalaiyar (13.215, 80.250); Open-Meteo Flood API (GloFAS) daily `river_discharge, _median, _max`, 30 days back + 14 ahead, refresh 3 h, cached in `public_data_cache`. Trend: mean of last 2 days ÷ mean of the 3 days before: >1.15 rising, <0.87 falling, else steady (≥4 values). UI colours ratio vs 30-day median: amber >1.3×, red >2× (USER_GUIDE §12).

#### 5.21 Analytics (`services/analytics.py`, PLATFORM_DESIGN)

All live from DB: summary, timeseries (metrics sos_created/sos_resolved/alerts/telemetry_frames/state_changes; buckets minute/hour/day), breakdown (type/status/priority), response-times (p50/p90/p95 by priority), sensors (last 10 min frames: rate (expected 0.67 Hz), signal availability PPG/SpO2/EDA/temp/IMU/GPS, 24 h state share, battery), performance (alert ack p50/p90, ROV transit, team utilisation), geo (SOS density grid `cell=0.01°` "~1 km", devices, teams, ROVs, rivers), models (registry cards, replay false alarms, MIMIC PERform AF, weather backtest).

#### 5.22 Simulator (`tools/simulate.py`, GETTING_STARTED §7)

Registers `W-DALIA-01`, `W-DALIA-02`, `W-WESAD-01`, `W-FALL-01` (rotates keys if existing); streams PPG-DaLiA, WESAD stress session, HIFD fall + stillness through `/api/v1/telemetry` (same auth path); options `--speed 1.0`, `--batch 2`, `--with-sos` (3 public SOS, 2 linked). Loops sessions as new boots.

---

### 6. API reference (64 routes under `/api/v1` + 5 outside) (`src/backend/app/api/routes.py`, `main.py`)

Role column = minimum role; "staff" = any signed-in role.

| Method | Path | Auth |
|---|---|---|
| POST | /auth/login | public (login bucket) |
| POST | /auth/refresh | public (login bucket) |
| POST | /auth/logout | refresh token |
| GET | /auth/me | staff |
| GET, POST | /users | admin |
| PATCH | /users/{id} | admin |
| POST | /sos | public (SOS bucket, Idempotency-Key) |
| GET | /sos/track/{ref}?token= | public (60/min) |
| GET | /public/summary | public |
| GET | /contacts | public |
| GET | /sos | staff (filters status, priority, type, q, since, sort, cursor) |
| GET | /sos/{ref} | staff |
| PATCH | /sos/{ref}/status | responder (own team) / dispatcher |
| POST | /sos/{ref}/assign | dispatcher |
| POST | /sos/{ref}/reallocate | dispatcher |
| POST | /sos/{ref}/link-device | dispatcher |
| POST | /sos/{ref}/notes | responder |
| GET | /dispatch/capacity | staff |
| POST | /sms/inbound | `X-SMS-Secret` (SMS bucket) |
| POST | /sms/test | admin |
| GET | /teams | staff |
| PATCH | /teams/{id} | dispatcher |
| POST | /telemetry | `X-Device-Key` |
| GET | /devices | staff |
| POST | /devices | admin |
| POST | /devices/{id}/rotate-key | admin |
| POST | /devices/{id}/commands | dispatcher |
| GET | /devices/{id}/commands | staff |
| GET | /devices/{id}/frames?since=&limit= | staff (≤2000) |
| GET | /devices/{id}/states?since= | staff |
| GET | /alerts?status= | staff |
| POST | /alerts/{id}/ack | responder |
| POST | /alerts/{id}/resolve | responder |
| GET | /weather/current, /weather/forecast?hours≤48, /weather/model | staff |
| GET | /analytics/summary, timeseries, breakdown, response-times, sensors, performance, geo, models | staff |
| GET | /public-data/rivers | staff |
| GET | /rov | staff |
| GET | /rov/{id}/track?minutes= | staff |
| GET | /missions | staff |
| POST | /rov/{id}/deploy, /recall, /reset, /takeover, /release, /control | dispatcher (control: pilot only) |
| POST | /rov/{id}/stop | responder |
| POST | /rov/{id}/bridge-key | admin |
| POST | /rov/{id}/vision-key | admin |
| POST | /rov/vision/frame | `X-ROV-Vision-Key` |
| GET | /rov/{id}/vision | staff |
| POST | /rov/{id}/vision/ticket | staff (single-use, 60 s) |
| GET | /rov/{id}/vision/stream?ticket= | ticket |
| POST | /rov/bridge/telemetry | `X-ROV-Key` |
| GET | /audit?limit≤1000 | admin |
| POST | /api/telemetry/wearable (legacy v1 alias, outside v1) | `X-Device-Key` |
| WS | /ws?token= | access JWT |
| GET | /healthz, /readyz, /metrics | public |

**WebSocket topics** (`docs/PLATFORM_DESIGN.md` §2):

| Topic | Events / data |
|---|---|
| sos | created, updated, assigned, note → `{sos}` |
| alerts | opened, acked, resolved, escalated → `{alert}` |
| devices | frame (≤1/device/1.5 s; bpm, spo2, temp_skin_c, eda_us, acc_std_g, battery_v, lat, lng, state, risk, heads), state, online, offline |
| weather | updated (current, forecast_summary) |
| rov | telemetry (1 Hz per active unit), deployed, recalled, stopped, control, mode, vision (≤2/s) |
| system | capacity `{status, teams_free, teams_total, waiting[], suggestions[], updated_at}` |

QA count at QA time: "52 endpoints × 5 roles" (context log) — the route count grew afterwards (link-device, vision, sms/test).

---

### 7. Frontend (web console + public PWA)

#### 7.1 Routes (`src/frontend/web/src/App.tsx`)

Public: `/` landing, `/sos` request-help form, `/track/:ref` tracking, `/login`. Staff (RequireAuth + StaffLayout, lazy-loaded): `/ops`, `/sos/:ref`, `/wearables`, `/wearables/:id`, `/weather`, `/analytics`, `/rov`, `/missions`, `/admin` (admin only). `/dashboard` → `/ops`; `*` NotFound.

Source structure: `api/` (types, client with single-flight refresh, live WebSocket store), `lib/` (format, permissions role matrix, SOS state machine and fusion labels, hooks, motion), `ui/` (primitives, DataTable, Dialog, Toast, uPlot charts + Sparkline, Leaflet MapView, KeyReveal, effects, ErrorBoundary), `features/` (public, auth, shell, ops incl. CapacityBanner/TeamsPanel, sos incl. SosQueue/SosFlags, alerts, wearables, rov incl. VisionFeed, weather incl. WeatherStrip, analytics tabs, admin), `mock/` (VITE_MOCK only).

#### 7.2 Per-role features (`docs/USER_GUIDE.md` §4–13)

- **Public:** 4-step form (what & where with "Use my location"; who is there incl. vulnerable groups; food & water; contact + optional band ID e.g. `TRD-W00`); answers saved locally; confirmation shows reference, tracking link, priority; helplines 112, 1070, 1913; tracking by link or reference + code; "Track SOS-…" for last request.
- **Dispatcher (Ops page):** weather strip, KPIs (open requests, open P1, open alerts, free teams, wearables online/critical, mean request→on-scene time), capacity banner, SOS queue (sorted P1 first, then score, then oldest; filters Open/Pending/All; search; flags SMS / Wearable SOS / Awaiting resources / waiting N min (amber for P1/P2 after 15 min) / possible duplicate), alerts panel, map (requests by priority, wearables, team bases, ROVs; layer toggles). SOS detail: request facts, location map, notes, next-step "Mark …" button, assign team (load e.g. `2/3`), cancel with reason, timeline, linked wearable panel (claimed vs verified; Confirm/Remove link), assignment history, 409 banner "Changed by someone else" with Re-apply/Discard.
- **Responder:** view all; status changes on own team's requests; notes; ack/resolve alerts; ROV STOP.
- **Viewer:** read-only all pages except Admin.
- **Wearables:** tiles (online, state, risk bar, HR, SpO2, skin temp, EDA 2-min trend, battery, time since last frame; filters All/Needs attention/Online/Offline); detail: vitals charts 2/5/10 min, fusion state + evidence, Tier-1 head outputs (HR trust <0.5 = unreliable), commands, state history.
- **ROV units / missions:** fleet table, Deploy (open requests with coordinates, most urgent first), Recall, Stop, Reset, Bridge key; live cameras list with "Persons seen" badge; mission panel with map (30-min track, dashed line to goal, request, victims' bands), telemetry (stale after 5 s; battery red <20 %), camera (LIVE / STALLED after 5 s / plain video / "No camera feed" — "nothing is ever faked"), victim wearables, controls (hold-to-move buttons or W/A/S/D, R/F, L, Space; releasing or blurring sends stop; speed slider default 40 %).
- **Weather:** current conditions (Open-Meteo or offline CSV), 24/48 h forecast p50 line with p10–p90 band, hazards (heat, heavy rain, flood risk, high wind; watch/warning), model card vs persistence.
- **Analytics tabs:** Overview, Sensors, Trends, Geographic, Performance, AI predictions.
- **Admin:** users (create/role/team/deactivate → disconnect ≤30 s), teams (capacity, available), register device (key shown once, must tick "I have stored this key"), rotate key, ROV bridge/vision keys panel, SMS intake test.
- **Keyboard:** `?`, `1–7` pages, `/` search, `j/k`, `Enter`, `a` ack oldest alert, `m` map, `Esc`, Ctrl+Enter note, WASD/R/F/L/Space ROV, arrows for analytics tabs.
- **Accessibility:** screen-reader announcements for new P1/P2, alerts, escalations, "No free teams"; text colours ≥4.5:1; all motion disabled under `prefers-reduced-motion`; axe serious violations 4 → 0 in QA.

#### 7.3 Offline PWA (`public/sw.js`, `features/public/offline.ts`, `public/manifest.webmanifest`, web README)

- Manifest: name TRIDENT, `display: standalone`, theme/background `#0d0e10`, icons 192/512 maskable, shortcut "Request help" → `/sos`.
- Hand-written service worker (production builds only); build plugin `swPrecache` writes precache list (index.html, referenced JS/CSS, woff2 fonts, logo, manifest). `/assets/*` cache-first; navigations network-first with 4 s timeout → cached `index.html`; `/api`, `/ws`, `/healthz` never cached; `sw.js` served `no-cache`.
- **SOS outbox:** on offline / network error / **20 s** timeout / 408 / 429 / 5xx → saved in `localStorage` key `trident.sos.outbox`, same `Idempotency-Key`; retried on `online` events and every **30 s**, plus Background Sync (outbox mirrored into Cache Storage for the worker). Other 4xx stops retries and shows the server reason ("Edit and send again"). Context log: kept 48 h.
- **SMS fallback:** `sms_number` from `/public/summary` cached in `trident.public.sms`; "Send by SMS instead" opens the messages app with composed ≤160-char text.

#### 7.4 Maps and charts

Leaflet; default Stadia `alidade_smooth_dark` (keyless on localhost; deployed domain must be registered); after 3 tile errors fall back to OSM darkened via CSS; after 3 more "Map tiles unavailable" (markers still shown). Overrides `VITE_MAP_TILE_URL`, `VITE_MAP_TILE_ATTRIBUTION`, `VITE_MAP_TILE_DARKEN`. Charts: uPlot time series and sparklines.

#### 7.5 Design system (`src/styles/tokens.css`)

Dark "operations console": surfaces `#0d0e10/#141619/#1b1e22/#24282e`, line `#2a2e35`, text `#ece8e1/#aaa59c/#8b867e`, single accent `#e8a33d`, semantic critical `#ef5b5b`, warning `#ee8a3a`, ok `#3fb8a1`, info `#8fa3b8`; IBM Plex Sans/Mono; 8 px grid; motion 120/200/400 ms.

#### 7.6 Mock mode

`npm run dev:mock` (`VITE_MOCK=1`): full fake REST + WS per the contract, users with password `trident`, test hooks on `window.__tridentMock` (`bumpVersion`, `setTeamsFree`, `setVisionCamera`, `setSmsConfigured`, `setNetworkDown`, `setLatency`). Excluded from real builds (dead-code dynamic import).

---

### 8. Computer vision (ROV camera) (`src/cv/README.md`, `src/cv/vision/pipeline.py`)

- YOLOv8n (`src/cv/yolov8_model/yolov8n.pt`), CPU, `CONF = 0.4`, all 80 COCO classes, `persons` = count of person boxes.
- Faces: Haar `haarcascade_frontalface_default.xml`, `detectMultiScale(gray, 1.1, 5, minSize=(40,40))`; LBPH (`cv2.face`, opencv-contrib) match when distance < **50** (`LBPH_MATCH_MAX`); enrolment 120 images per person (`face_taker.py`), `face_trainer.py` → `trainer.yml`, `names.json`.
- Distance: pinhole `D = W_real · f / w_px`, f = 700 px at 640 px width (laptop webcam calibration), real widths: person 0.45 m (shoulders), face 0.16, boat 2.5, car 1.8, truck 2.5, bus 2.55, motorcycle 0.8, bicycle 0.6, umbrella 0.9, bench 1.4, dog 0.30, cat 0.20, cow 0.70, horse 0.60, bottle 0.07, chair 0.50, backpack 0.30, handbag 0.30, suitcase 0.45, surfboard 0.50. Accuracy "about ±30 %"; underwater focal length ~1.33× behind a flat port.
- Worker: `--fps 4` default, `--quality 70` JPEG, `--focal-px 700`, reopen camera every 2 s, logs every 10 s; ~0.3–0.5 s/frame on laptop CPU.
- Origin: integrated from the "Empower" CV subsystem (commit `bc1de03`, 2026-07-06).
- Privacy policy (README): enrol responders only, with consent; never victims/bystanders.

---

### 9. Deployment (`Dockerfile`, `docs/DEPLOYMENT.md`)

- Two-stage image: `node:22-slim` (npm ci + build) → `python:3.12-slim`, `requirements-prod.txt` only (no torch), copies app.py, src/backend, src/ml, models/, built console; user `trident`; `TRIDENT_ENV=production`; `HEALTHCHECK` every 30 s on `/healthz`; `uvicorn … --proxy-headers`, one worker, port `${PORT:-8000}`.
- Reference: one VM (~2 vCPU/4 GB) with Docker Compose: `postgres:16`, `api`, `caddy:2` (auto-HTTPS, HSTS `max-age=31536000; includeSubDomains`, overwrites X-Forwarded-For, `/metrics` → 404, `flush_interval -1` for MJPEG); API port not published; `FORWARDED_ALLOW_IPS="*"` inside compose network.
- Backups: nightly `pg_dump -Fc` 02:15 cron, keep 14 days, off-machine; SQLite online backup API; monthly restore drill.
- Single-process constraint: in-memory per-device fusion runtimes, WS hub, rate-limit buckets, weather cache, vision frames → no `--workers N`. Safe across processes: idempotency keys, refresh tokens, job leases.
- History: v1 Flask app deployed on Render (`https://trident-command-center.onrender.com/`, commit `64a7abe` 2026-07-30) and a Dockerfile for Hugging Face Spaces (commit `116e8d7`, 2026-07-06), gunicorn. Current v2 hosting "deferred to CI/CD".

---

### 10. QA

#### 10.1 Automated tests (collected with `pytest --collect-only`, 2026-10-31)

**128 tests collected.** README and GETTING_STARTED were corrected to 128 on 2026-10-31.

| Suite | File | Tests | Covers |
|---|---|---:|---|
| backend | test_auth_sos.py | 10 | login/refresh rotation + reuse detection, error envelope, idempotent+trackable SOS, validation, state machine + version conflict + capacity, RBAC, public summary/contacts, weather unavailable 503, token bucket bursts, optional age/pincode |
| backend | test_resilience.py | 25 | duplicates linked not double-dispatched, priority ageing, no free teams/suggestions/reallocation, SMS parser + webhook, LOST_CONTACT (and skip for UNKNOWN), real-ROV dead-man queues stop, bridge stops ROV when control room unreachable, wearable SOS button → one request + alert, extreme-case reallocation only when everything agrees, idempotency namespacing, untrusted device claims, bounded time series/422, body limits + no-store, oversized numbers, WS closes on deactivation, WS rejects foreign origin, idempotent retry vs rate limit, malformed frames individually rejected, DB busy → 503 + Retry-After, clean 500, readyz write lock, failed job retried, log redaction |
| backend | test_rov_analytics.py | 6 | mission transit + victims, exclusive manual control, serial bridge outbox, live analytics, river trend, bridge serial-line parsing |
| backend | test_telemetry.py | 7 | device auth/dedup/commands, bad command params, real fall then stillness opens alert and raises linked SOS, WS SOS events, WS bad token, scheduler lease exclusivity, health/ready/metrics |
| backend | test_vision.py | 1 | vision ingest, ticket, stream |
| ml | test_archive (3), test_candidates (9), test_emulator (9), test_features (11), test_fusion (13), test_mimic_perform_af (2), test_p3v2 (7), test_runtime (4), test_schema (5), test_vision_pipeline (3), test_weather (13) | 79 | ML/weather/vision pipeline |

Backend total 49; ML total 79. Each backend module uses a fresh temporary SQLite DB; weather tests run offline.

Test count history (context log §4): 35 (P2) → 44 (P3 v2) → 61 (P5) → 98 (P6/P7) → 106 (degraded-mode wrap-up) → 108 (SOS button round) → 127 (full QA) → 128 (P8).

#### 10.2 Full-ecosystem QA round (2026-10-31) (`docs/WEARABLE_ML_SUBPROJECT_CONTEXT.md` §4)

- **Streams:** frontend E2E in real Chrome (every role, mobile + desktop, offline PWA, a11y via axe, resilience); security review (**52 endpoints × 5 roles**, JWT, injection, XSS, transport); load/concurrency/failure injection (bursts, dispatch races, **20 devices × 5 min**, WebSocket fan-out, **kill -9**, network/DB/ML failure, **20-min soak**); static checks, clean-venv prod install, PostgreSQL DDL (offline), model-file hashes (**96/96**), firmware build.
- **Fixed:** **2 high + 5 medium** security issues (unbounded time-series DoS; idempotency namespace collision letting the public suppress SMS/band SOS; unverified public wearable claims; WebSockets surviving deactivation; SMS secret brute force; stored HTML in map tooltips); **12 load/failure defects** (rate-limit bursts; idempotent retry vs rate limit; DB busy → 503; slow duplicate check/auto-triage; malformed frames blocking a backlog; readyz write probe; tokens in logs; job retry/backoff; UNKNOWN state without ML; SOS group validation; double error logging); **7 UI bugs** + all axe violations (**4 serious → 0**); a SQLite migration bug with existing data; outdated requirements.txt.
- Earlier live-testing fixes (P6 row): schema rejected impacts >16 g (now per-axis range, |a| ≤27.7 g); fusion impact recorded at wrong frame; serving imported training stack; ONNX trees loaded in minutes (compiled numpy forests 0.5 s); scheduler leases blocked takeover for 3× interval.
- P8 doc-pass fixes: geofence keys aligned to `lat/lng/radius_km`, buzz `{ms}`; timeline includes assignments with `assigned_by/assigned_at`; LOST_CONTACT no longer fires for UNKNOWN; admin ROV bridge/vision-key panel; link check 0 broken.
- **No quantitative load results** (latency percentiles, throughput, max concurrent devices/sockets) are recorded in the repo; the "QA report" and "CDP scripts" referenced in resilience §13.2 are not in the tree.

---

### 11. Resilience / degraded-mode behaviours (`docs/RESILIENCE_AND_FUTURE_WORK.md` Part I)

| Situation (§) | Behaviour now |
|---|---|
| No mobile data (§1) | PWA loads offline after one visit; offline outbox with same Idempotency-Key |
| Only SMS (§1) | compact ≤160-char SMS → gateway → `/sms/inbound`; reply with reference, priority, link; gateway retries de-duplicated |
| Wearable uplink lost (§1) | 8 min / 320-frame buffer, event frames kept; on-device fall detector + buzzer work offline; ordered, de-duplicated backlog upload |
| Wearable silent while not STABLE (§1) | LOST_CONTACT critical after 30 s |
| Control room loses internet (§1) | API/DB/ML/fusion/dispatch/bridge on LAN; weather → cached forecast labelled stale; rivers → last cache; map → markers on blank map |
| ROV link drops (§1) | bridge stop after 5 s; dead-man 120 s also reaches real units via outbox |
| Server restart (§1) | migrations run; leases released or taken over within 60 s; fusion state in memory → recalibration ~2 min |
| Several urgent requests (§2) | urgency-ordered auto-dispatch; capacity checked in-transaction |
| No free team (§2) | `awaiting_resources`; capacity ok/strained/exhausted; suggestions; human-confirmed atomic moves |
| Extreme case (§2) | automatic move under all-signals rule |
| Victim has no phone (§2) | band SOS button |
| Long waits (§2) | ageing +2 per 5 min up to 20 |
| Resent SOS (§2) | duplicate linking |
| Waiting victim deteriorates (§2) | critical wearable +30 every 10 s re-triage |
| Weather API down / models missing / DB down / duplicates / browser disconnect / concurrent edits / stolen refresh token / leaked device key / low battery (§3) | cached forecast; API works and `/readyz` reports; 503 + devices buffer; idempotent ingest; WS reconnect + resync; 409; family revoked; rotate key; SENSOR_FAULT suppresses cardiac rules |

Owner inputs outstanding (§4): SMS gateway, Stadia domain registration, helpline confirmation (112, 1070, 1913), device key in `secrets.h`, production secrets.

---

### 12. Future-work roadmap (Part II, §5–§14)

Sizes S <1 day, M 1–5 days, L 1–3 weeks, XL >3 weeks; priorities P1 next / P2 after first deployment / P3 later.

- **P1 (now):** CI pipeline (§13.1: pytest + PostgreSQL service, tsc + build, `pio run`, ruff/pyflakes, pip-audit/npm audit, Docker + Trivy, staging deploy); first deployment on one VM (Oracle Always Free Arm ~2 OCPU/12 GB or Render Starter) with PostgreSQL + Caddy TLS + backups (§6.1); hardware bring-up + data collection with Polar H10 reference (§9.1); Android SMS gateway (§7.1).
- **P2 (next):** multi-replica with Redis (§6.2: Redis pub/sub WS fan-out with seq via INCR, device-affinity consistent hashing on `X-Device-Key` with ~5 KB fusion snapshots every 30 s, Redis Lua token buckets, `SKIP LOCKED` auto-triage); telemetry tiering (§6.4: ~57 MB/device/day; TimescaleDB, compression, 90-day aggregates, Parquet cold); observability (§12: Prometheus/Grafana, OpenTelemetry, Loki; SLOs SOS intake 99.9 %, critical alert frame→console p95 <5 s, ingest success 99.5 %); security (§11: HttpOnly refresh cookie, TOTP MFA, per-account lockout, audit hash-chain, TLS CA pinning, pgcrypto, secret manager with `kid`, Cloudflare WAF; DPDP Act 2023 retention 180 days); responder mobile app (§10.2); offline MBTiles (§7.2); camera calibration + better detector (§9.4).
- **P3 (later):** LoRa/Meshtastic (SX1262, 30-byte frame every 30–60 s, 2–15 km/hop), ESP-NOW (~200 m/hop), BLE companion, satellite (§7.3); edge kit with offline-first sync (`origin_node`, state-machine merge) (§7.4); event streaming Redpanda/Kafka beyond ~200 devices (+50–200 ms) (§6.3); dispatch intelligence (§8: OSRM ETA routing, Hungarian/OR-Tools assignment with extreme-case rule as hard constraint, DBSCAN mission clustering ~300 m, mutual aid NDRF/SDRF, mass-casualty START-like mode, inventory, responder status); TinyML on band (m2cgen fall Extra-Trees), LittleFS buffer, signed OTA A/B, 24 h battery (§9.2); weather/flood (§9.3: NWP features, pySTEPS radar nowcasting, CWC gauges, HAND inundation, INCOIS surge); ROV CV (§9.4: YOLOv8s/YOLO11n fine-tuned on SeaDronesSee/AFO, ByteTrack, FLIR Lepton, ArcFace, WebRTC, Jetson Orin Nano, drones); ROV autonomy (§10.4: firmware waypoints + return-home, Ping2 sonar, fleet coverage, mission replay); integrations (§10.5: CAP/NDMA SACHET, 112 ERSS, GeoJSON/KML); public features (§10.1: Tamil/Hindi i18n, voice SOS, family reunification, shelter finder).
- **Open owner decisions (§14):** first host (rec. Oracle VM), SMS path (Android first), video transport (MJPEG until real camera), face-recognition scope (responders only), retention (180 days), long-range networking (LoRa Meshtastic).

---

### 13. Project metadata and history

| Item | Recorded value |
|---|---|
| Team member names / roles | **Not recorded** in docs or README (README "Team" section is only `assets/images/team-photo.jpg`, 6 people, no captions). Indirect traces only: git authors `harshit` / `harshitworkmain` (GitHub repo `harshitworkmain/trident`); Kaggle user `harshitsingh7883` (context log); xlsx BOM metadata "Akshay" / "Thakur Akshayakumar 23BLC1120"; face-enrolment `src/cv/face_recognition/names.json` ids 1–2 "Avishkar", 3 "Harsh". None of these state a project role. Memory note: the git account belongs to a friend of the user. |
| Institution | **Not recorded.** (Team photo is in an auditorium; "College Lab PC" scenario in a deleted historic doc.) |
| Guide / supervisor | **Not recorded.** |
| Licence holder | "TRIDENT Disaster Response System", 2025 |
| Dates | v1 uploaded 2026-01-26 (9 "Add files via upload" commits); docs/media restructure 2026-03-30; CV ("Empower") integration, Render/HF deployment 2026-07; career docs 2026-08; ESP32 telemetry integration 2026-09-10; 8-state ML engine 2026-09-18; Kaggle tournament 2026-09-25/28; v2 hybrid rebuild P0–P8 2026-10-30/31 (uncommitted in working tree: ~113 changed paths; last commit `a424e02` 2026-09-28). Iteration log starts 2026-09-17. |
| Earlier history (v1) | Flask single-file backend (`src/backend/main.py`), SQLite `trident_sos.db`, 6 tables / 63 columns / 4 FKs, 25 REST endpoints, 2,960-line single-page template with 11 Chart.js charts, additive 1–5 priority (higher = more urgent, auto-dispatch ≥4), PyTorch LSTM temperature forecast, NetworkX risk-graph demos (`src/ml/risk_analysis/network_analyzer.py` still present), PyQt6 ROV station auto-spawned for priority ≥4 with 12 s countdown; v1 firmware sent unauthenticated frames every 1.5 s to the Render URL (`docs/career/RESUME_BULLETS_*.md`, historic README). |
| Development process | Built under phase-by-phase owner review (career notes §4; context log in Sept 2026). |

---

### 14. Candidate novelty / inventive points (with evidence)

1. **Wearable-corroborated, explainable triage.** 0–100 additive score with per-factor caps and human-readable reasons; a measured Tier-2 fusion state from a *verified* linked band adds the largest single contribution (+30 critical, +5 advisory, +3 offline), re-evaluated every 10 s so waiting victims who deteriorate rise automatically; claimed (unverified) band IDs are ignored until the band itself raised the SOS or a dispatcher confirms. Evidence: `triage.py`, `sos.auto_triage`, `sos.link_device`, PLATFORM_DESIGN §5, test `test_public_device_claim_is_not_trusted`.
2. **Multi-signal-corroborated automatic resource reallocation.** Team moved without a human only when triage (P1 ≥80), physiological ML+rule state (critical, risk ≥0.85, sustained ≥60 s), environment (water-disaster type OR active weather *warning* from the quantile forecaster OR GloFAS river "rising" trend >1.15) and capacity (no free team) all agree; donor restricted to P4/P5 not en route; full evidence written to both timelines and audit. Otherwise suggestion-only with ≥2-level priority gap and atomic two-version-checked moves. Evidence: `sos._extreme`, `_auto_reallocate_if_extreme`, `_capacity`, `reallocate`; test `test_extreme_case_reallocates_automatically_only_when_everything_agrees`.
3. **Offline-first multi-channel SOS intake with channel-namespaced idempotency.** Same request identity across PWA outbox retries (localStorage + Background Sync via Cache Storage mirror), SMS gateway retries (message id or content hash) and wearable SOS presses (boot + press_id); keys namespaced `sos:{source}:{key}` so one channel cannot suppress another; idempotent retries answered before rate limiting; tolerant compact SMS grammar that the offline form pre-composes. Evidence: `offline.ts`, `sms.py`, `sos.idem_key`, `routes.submit_sos`.
4. **Event-preserving bounded telemetry queue on the band.** 320-frame RAM ring that, on overflow, evicts the oldest *routine* frame while preserving seq order and retaining event frames (SOS, fall, ≥3 g impact, immersion, geofence breach); NVS block-reserved monotonic seq (4000-number blocks) + boot_id giving globally unique (device, boot, seq) for server de-dup; SOS group replicated into every frame of every request until acknowledged so it overtakes a draining backlog; adaptive retry cap (3 s) while an SOS is pending; bad-frame isolation by bisection. Evidence: `frame.cpp`, `telemetry.cpp`, `settings.cpp`, `sos.cpp`.
5. **Closed-loop SOS acknowledgement on a phoneless wearable.** press_id-matched server ack drives distinct audible cues (raised / still-sending reminder / received / cancelled), cancel requires a *new* 5 s hold and never closes the request server-side. Evidence: `sos.cpp`, `buzzer.cpp`, `telemetry.sos_button`.
6. **Layered fail-safe ROV teleoperation.** Exclusive single-pilot lease with admin override; STOP available to lower role than drive; server dead-man (120 s) delivered to real units via command outbox; independent bridge-side link-loss stop (5 s); reset always returns home rather than resuming; auto return on <20 % battery; deploy gated on ≥30 % battery. Evidence: `rov.py`, `bridge.py`; tests `test_real_rov_deadman_queues_stop`, `test_bridge_stops_rov_when_control_room_unreachable`.
7. **Out-of-process CV relay with single-use stream tickets.** Heavy CV runs in a separate worker authenticated by a per-ROV vision key; API keeps only latest frame in memory, sanitises detections, relays MJPEG via single-use 60 s tickets so bearer tokens never appear in URLs/logs. Evidence: `services/vision.py`, `src/cv/vision`.
8. **Mission view fusing ROV telemetry with victims' live wearables** (mission SOS + all open requests of the ROV's team with live band state). Evidence: `rov.missions`.
9. **LOST_CONTACT as an alarm condition** (silence of a non-stable device is itself critical). Evidence: `telemetry.mark_offline`.
10. **DB-lease leader election with shared last_run_at, short leases for safety jobs and exponential backoff**, enabling multi-replica-safe scheduling without external coordination. Evidence: `jobs.py`.
11. **Edge two-tier fall detection** (on-device free-fall/impact/stillness state machine latching a local alarm independent of network; server ML + fusion for corroboration). Evidence: `imu.cpp`, ARCHITECTURE §2.2.
12. **Pulsed-excitation water-contact sensing** (300 µs drive, debounce 3) to limit electrode corrosion, and barometric in-frame swing for fall height/submersion. Evidence: `water.cpp`, `baro.cpp`.

(Assess against prior art before claiming; none of these has a documented prior-art search in the repo.)

---

### 15. Code size (non-ML and overall) — counted 2026-10-31

Counted with a line-count script (excludes node_modules, dist, .pio, __pycache__, data, images, secrets.h).

| Component | Files | Lines | Non-blank |
|---|---:|---:|---:|
| Backend API (`src/backend/app`, incl. simulator) | 32 | 4,745 | 3,868 |
| Backend migrations | 6 | 565 | 492 |
| Web console TS/TSX (`src/frontend/web/src`) | 52 | 8,740 | 8,005 |
| Web console CSS | 4 | 1,066 | 953 |
| Service worker `public/sw.js` | 1 | 139 | 127 |
| `vite.config.ts` | 1 | 71 | 67 |
| Firmware (`src/firmware` .cpp/.h/.ini, excl. secrets.h) | 27 | 2,026 | 1,816 |
| ROV bridge + legacy console (`src/rov`) | 3 | 616 | 524 |
| CV (`src/cv`, .py) | 11 | 913 | 743 |
| Wearable ML (`src/ml/wearable`, .py) | 28 | 4,294 | 3,572 |
| Wearable ML configs (.yaml) | 3 | 290 | 262 |
| Weather ML (`src/ml/weather`) | 14 | 1,566 | 1,285 |
| Legacy risk analysis | 1 | 463 | 374 |
| Tests backend | 7 | 926 | 776 |
| Tests ML | 11 | 909 | 700 |
| Docs (`docs/**/*.md`) | 19 | 4,778 | 3,664 |
| Component READMEs | 4 | 733 | 597 |
| `app.py` / `Dockerfile` | 2 | 42 | 35 |

Non-ML application code (backend + migrations + frontend TS/CSS/sw/vite + firmware + ROV + CV) ≈ **18,881 lines**.

---

### 16. Discrepancies found

> **Status:** items 1–6 and 9 were corrected in the docs on 2026-10-31. Items 7, 8 and 10–16 are still
> caveats; state them accurately in any write-up.

1. Offline queue: `docs/PLATFORM_DESIGN.md` §1 CAP table says "Firmware keeps **120 frames (3 min)**"; code/firmware README/README say **320 frames (8 min)** (`config.h QUEUE_CAPACITY = 320`). Use 320/8 min.
2. Idempotency retention: PLATFORM_DESIGN says Idempotency-Key "stored for **24 h**"; code purges after **48 h** (`auth.IDEMPOTENCY_KEEP`), context log says 48 h.
3. Telemetry key: PLATFORM_DESIGN says unique `(device_id, seq)`; code uses `(device_id, boot_id, seq)`.
4. Retention: PLATFORM_DESIGN says "Downsample telemetry older than 7 days"; code **deletes** raw frames older than 7 days (state transitions/alerts kept).
5. Test count: README/GETTING_STARTED/career notes "127"; `pytest --collect-only` gives **128** (matches P8 log row).
6. Density grid: PLATFORM_DESIGN/code "~1 km" (0.01°); USER_GUIDE §12 says "about 2 km cells".
7. Manual reallocation: docs say donor must be ≥2 levels lower; that rule applies to *suggestions*; the endpoint itself only requires the donor be strictly lower priority and still `assigned`.
8. State machine: docs show only the linear chain + cancel; code also allows pending→assigned directly and assigned→triaged (unassign / team moved).
9. USER_GUIDE §15 "Known limitations" is partly stale: geofence key mismatch, timeline without assignments and LOST_CONTACT for UNKNOWN were fixed in P8 (context log; code `mark_offline` skips UNKNOWN; `track`/`detail` include assign events).
10. Seed team description still says "auto-dispatched for priority-5 water rescues" (v1 semantics where 5 was most urgent).
11. seq NVS block: README "one flash write about every 50 minutes"; `config.h` comment "~100 min" (4000 × 1.5 s = 100 min).
12. SOS burst: config default `sos_burst=10` but effective burst = max(10, min(20, 1000)) = 20 (DEPLOYMENT §9.3 says "burst 10 or the rate, whichever is larger").
13. Firmware HTTPS does not validate certificates (`setInsecure()`).
14. Infographics are AI-generated with garbled specs; BOM xlsx quantities (ESP32 ×2, buzzer ×21) look like procurement, not per-unit.
15. Firmware 2.2.0 compiles but is documented as untested on wired hardware; no measured battery life, enclosure IP rating, ROV thruster/motor specs, ROV dimensions or mass are recorded.
16. Historic git history contains plaintext Wi-Fi credentials in the v1 firmware (`src/firmware/main_controller/main_controller.ino`, noted in context log) and a Kaggle token that was committed then scrubbed (must be revoked) — do not reproduce in reports.


---

## Appendix C. Wearable ML, fusion, weather and CV fact sheet

Extracted read-only from `D:\harshit\trident` on 2026-10-31. Every number below is copied from the file cited
next to it. "not recorded" = not found anywhere in the repo. Where two repo documents disagree, both values
are given and the discrepancy is flagged in §15.

Abbreviations of source files used throughout:
- **ARCH** = `docs/WEARABLE_ML_ARCHITECTURE.md`
- **CTX** = `docs/WEARABLE_ML_SUBPROJECT_CONTEXT.md` (dataset inventory §3, iteration log §4)
- **TG** = `docs/TRAINING_GUIDE.md`
- **DATA-R** = `docs/reports/WEARABLE_DATA_REPORT.md`
- **TOUR-R** = `docs/reports/MODEL_TOURNAMENT_RESULTS.md`
- **FINAL-R** = `docs/reports/WEARABLE_FINAL_MODELS.md`
- **REPLAY-R** = `docs/reports/WEARABLE_FUSION_REPLAY.md`
- **AF-R** = `docs/reports/WEARABLE_RHYTHM_PPG_AF_TEST.md`
- **REG** = `models/wearable/registry.json`
- **CARD(h)** = `models/wearable/<h>/2.0.0/card.md`; **MET(h)** = `models/wearable/<h>/2.0.0/metrics.json`
- **FUS-Y** = `src/ml/wearable/config/fusion.yaml`; **FUS-PY** = `src/ml/wearable/serving/fusion.py`
- **TOUR-Y** = `src/ml/wearable/config/tournament.yaml`; **DS-Y** = `src/ml/wearable/config/datasets.yaml`
- **TJSON(h)** = `data/processed/wearable/tournament/<h>.json` (generated, git-ignored, read for AUPRC)
- **WX** = `docs/WEATHER_MODEL.md`; **WX-CARD** = `models/weather/1.0.0/card.md`

---

### 0. One-paragraph system summary (for abstracts)

TRIDENT is a flood / water-rescue command platform. Its wearable ML is a **hybrid two-tier system** (ARCH §1–2):
an ESP32 wrist band sends a fixed **1.5 s telemetry frame (schema v2)**; the server runs one shared online
`FeatureEngine` (identical code for training and serving), **five independent Tier-1 heads** trained only on
real public datasets (stress, fall, activity, HR-trust, rhythm), each chosen by a **per-head 3-stage nested,
subject-grouped model tournament**, calibrated (Platt / temperature, cross-fitted by subject), thresholded and
exported to ONNX; then a **deterministic, versioned Tier-2 fusion state machine (v1.2.0)** that turns head
outputs + raw frame signals into one of 8 trauma states with dwell/exit hysteresis, a risk score, an evidence
list and a basis label (`ml`, `rule`, `ml+rule`). Rule thresholds are chosen on a **real-data false-alarm
replay** (~1,505 h of daily life incl. 1,403 h of held-out Capture-24 people). Separately: a probabilistic
weather forecaster (LightGBM quantile + GRU, p10/p50/p90, 1–48 h, Chennai) with hazard rules, and an ROV
camera CV worker (YOLOv8n + Haar/LBPH + pinhole distance).

Project phases P0–P8 were complete as of 2026-10-31 (CTX §1). 128 tests pass. `tests/ml/` contains 68 `def test_` functions (counted, some parametrised).

---

### 1. Design principles and the "why" (ARCH §1, §0 decisions)

| Principle | Statement (ARCH §1) |
|---|---|
| Real data trains models; rules cover what has no data | Tier-1 heads trained/validated only on real recordings; states with no public data come from an explicit, versioned rule engine |
| Train exactly what we serve | Raw datasets converted into the same 1.5 s telemetry frames the ESP32 sends; one feature module for training and serving |
| Honest evaluation | Every number from subjects/records the model never saw; synthetic data used only to test fusion rules, never as training labels |
| Everything traceable | Each prediction carries model versions, its basis (`ml`, `rule`, `ml+rule`) and evidence |
| Portable artifacts | ONNX, never pickle (training py3.13 / numpy 2.x locally; production py3.10 / numpy 1.26 in Docker) |

**Why v2 replaced v1** (CTX §4, row "Architecture v2 (Hybrid)", 2026-10-30): "Audit found the 8-class synthetic
approach unvalidatable (5/8 states had only generator-labelled data; v1 firmware SpO2 was simulated)." v1 was a
single 8-class synthetic classifier (ARCH header "Supersedes").

#### Numbered implementation decisions with rationale (ARCH header, decisions 1–25)
1. **IMU at 50 Hz, not 100 Hz** — matches HIFD (wrist fall test set). Emulator anti-alias-downsamples faster
   sources (SisFall 200 Hz), keeps slower ones (E4 32 Hz, UP-Fall ~20 Hz).
2. **EDA in µS** — firmware converts Grove GSR ADC to skin conductance (Seeed formula); open-circuit
   calibration stored in NVS (`calibrate_gsr_open`). Same unit as WESAD/PPG-DaLiA.
3. **`imu_fall_detected` is NaN in emulated frames** — firmware heuristic, fusion backstop only, never a feature.
4. Loaders in a single module (`data/loaders.py`).
5. **Measured cross-dataset domain gap:** median wrist fall peak 13.3 g in HIFD vs 3.3 g in UP-Fall (20 Hz
   sampling flattens impacts) → fall features must use relative/shape features, not only absolute peaks.
6. **Training == serving by construction** — head tables produced by replaying each emulated recording frame by
   frame through the online `FeatureEngine`; a test pushes frames through JSON → `parse_payload` → engine and
   asserts **bit-identical** features for all six feature sets.
7. **Personal calibration uses only the past** — baselines (BPM, EDA, skin temp) from the first **80 frames
   (2 min)**, using only frames already seen, offline and online alike.
8. **Wrist-PPG beat quality measured on PPG-DaLiA** with an offset-robust method: at rest beat-count ratio
   **1.00 (IQR 0.96–1.03)**, median |RR error| **58 ms**. Rhythm augmentation: σ_RR **30–90 ms**, **1–6 %**
   missed beats, **0–4 %** spurious beats, **2** augmented copies per MIT-BIH record. Records 201/202 grouped as
   one patient. Ventricular-ectopy fraction output dropped (device cannot observe beat morphology).
9. **Fall labels:** only windows containing the impact frame of a fall trial are positive (peak |acc|; UP-Fall
   restricted to frames tagged as falling). Other windows of fall trials excluded as ambiguous; every window of
   an ADL trial is negative.
10. **Accelerometer-only fall variant needed for replay** — PPG-DaLiA and WESAD wrists have no gyroscope; ~60 h of
    real daily life replayed.
11. **Activity classes (v1):** rest = sitting, driving, lunch, working; light = table soccer; active = stairs,
    cycling, walking. Windows need **≥ 80 %** label purity. **HR-trust label:** firmware-style BPM within
    **10 bpm** of ECG HR.
12. **Tournament rules:** outer 5-fold StratifiedGroupKFold by subject, 3-fold inner CV for Optuna; tuning
    starts from screening config; **logreg baseline advances if in Stage-1 top two**; Stage-3 winner needs
    subject-bootstrap CI of macro-F1 difference excluding 0, otherwise smaller/faster finalist wins.
13. **More data per head (P3 v2):** HR-trust + WESAD with chest-ECG reference from own R-peak detector
    (validated on PPG-DaLiA: sensitivity **≥ 98.7 %**, precision **≈ 99.5 %**, median HR error **< 0.5 bpm**);
    rhythm + AFDB and LTAFDB sub-sampled with strides **20 and 60 frames** and **1** PPG-noise copy each;
    activity + PAMAP2 and Capture-24; fall + daily-life negatives from PPG-DaLiA, WESAD, PAMAP2, Capture-24.
14. **Stress-Predict is external test, not training** — pooling lowered WESAD OOF macro-F1 in a smoke run
    (**0.834 vs 0.885**): its protocol labels inter-task relaxation as non-stress and counts hyperventilation and
    interview as stress (different target definition).
15. **Fall head is accelerometer-only** — mixing gyro-present falls with gyro-missing negatives would teach
    "gyro missing ⇒ no fall"; in v1 gyro added only **~0.004** macro-F1. Firmware still sends gyro.
16. **Capture-24 split for fall** (stable SHA-256 of participant id): **one third** held out entirely for false
    alarms on unseen people; other two thirds as CV negatives: a window **every 30 s**, plus every window with a
    motion spike (**≥ 1.8 g or ≤ 0.4 g**), capped at **1,500 per person** (label-free hard-negative mining).
17. **Activity labels follow Walmsley 2020:** rest = sleep/sedentary (incl. driving); light = standing and
    household chores; active = walking, stairs, sport (MVPA). Capture-24 windows every **2 min**.
18. **New candidates:** Extra-Trees (bootstrap capped at **60k rows per tree**); MiniRocket (own numpy
    implementation; needs windows **≥ 8 frames**, not entered for fall); Stage-3 soft-vote of two tuned
    finalists, adopted only if subject-bootstrap CI vs single winner excludes 0.
19. Like-for-like with v1: per-source-dataset OOF scores; v1 archived in `data/processed/wearable/tournament/v1/`.
20. **Replay through the serving path** (`serving/runtime.py`): heads at training stride, last output held,
    head marked unavailable when its window lacks trained inputs. Streaming == batched replay (tested). Replay
    covers PPG-DaLiA, WESAD, PAMAP2, Stress-Predict, **1,403 h** of held-out Capture-24, plus HIFD falls padded
    with **60 s** of their final frame (semi-synthetic stillness).
21. **Missing flags are false** — NaN device flag counted as true (`bool(nan)`) so every wearer looked wet:
    **118 → 2** hypothermia alarms after fix.
22. **CRUSH_ENTRAPMENT needs an impact or long stillness, and HR, not the stress head** — spec rule gave
    **14.3** false alarms / 8 h on Stress-Predict; chosen rule **0.51** there and **0** elsewhere.
23. **Fall operating point for fusion 0.6** (registry keeps P4's 0.72 as Tier-1 point). Through fusion
    **84.6 %** of HIFD falls reach CONCUSSIVE_STASIS (0.72: **61.5 %**) for **1.20 vs 0.74** false alarms / 8 h
    on held-out Capture-24.
24. **Stress is advisory** — doesn't transfer (Stress-Predict **0.52**); excluded from critical rules,
    `alert_level: advisory`, p **0.85**, **120 s** dwell.
25. **Compiled forests for serving** — onnxruntime 1.22 needs **~280 s** to build the HR-trust Extra-Trees kernel
    (**1.9 M nodes**; .ort format doesn't help). Tree members stored as numpy arrays (`serving/forest.py`),
    parity ≤ **3e-7**, **0 flips**; all heads load in **0.5 s**. ONNX stays canonical.

---

### 2. Datasets

#### 2.1 Master table (DS-Y, CTX §3, ARCH §5.1, DATA-R, TOUR-R)

| Dataset | Subjects / records | Sensors & placement | Rate(s) | Size / volume | Licence | URL / DOI | Head(s) & role |
|---|---|---|---|---|---|---|---|
| **WESAD** (Schmidt et al., ICMI 2018) | 15 (S2–S11, S13–S17) | Wrist Empatica E4: EDA 4 Hz, BVP 64 Hz, ACC 32 Hz, TEMP 4 Hz; chest RespiBAN ECG 700 Hz | as listed | WESAD.zip **2.25 GB**, 17.6 GB unzipped; 57,908 frames, **24.13 h** (DATA-R) | CC BY 4.0 | https://archive.ics.uci.edu/dataset/465/... ; working download https://uni-siegen.sciebo.de/s/HGdUkoNlW1Ub0Gx/download ; DOI 10.24432/C57K5T | Stress (CV); HR-trust (CV, chest-ECG reference); fall negatives; replay |
| **PPG-DaLiA** (Reiss et al., Sensors 2019) | 15 (S1–S15) | Wrist E4 BVP, ACC, EDA, TEMP; chest ECG HR & R-peaks as ground truth | E4 rates | zip **2.87 GB** (nested data.zip, 24 GB unzipped); 86,321 frames, **35.97 h** | CC BY 4.0 | https://archive.ics.uci.edu/dataset/495/ppg+dalia ; DOI 10.24432/C53890 | Activity (CV), HR-trust (CV), fall negatives, replay, PPG-noise calibration |
| **UP-Fall** (Martínez-Villaseñor et al., Sensors 2019) | 17 | Wrist IMU (one of 5 locations): acc + gyro | ~20 Hz (irregular ~21 Hz, interpolated to 20 Hz) | 560/561 trials obtained (S17-A11-T3 unpublished; S8-A11-T2–3 header-only); 558 recordings, 10,693 frames, 4.46 h | "see source" | https://sites.google.com/up.edu.mx/har-up/ ; DOI 10.3390/s19091988 | Fall (CV) |
| **SisFall** (Sucerquia et al., Sensors 2017) | 38 (23 young + 15 elderly) | **Waist** ADXL345 (±16 g, 13 bit) + ITG3200 (±2000 °/s, 16 bit) | 200 Hz | 4,505 trials (19 ADLs + 15 fall types); 52,188 frames, 21.75 h | "see source" | original host offline; mirror https://github.com/Sibonile7/Elderly-Fall-Detection-using-AI-SisFall-Dataset- ; DOI 10.3390/s17010198 | Fall (CV) |
| **HIFD** (Nho et al., IEEE Access 2020) | 21 | Wrist ACC, gyro, quaternion, PPG/HR | 50 Hz | 349 recordings (104 fall, 245 ADL trials), 4,910 frames, 2.05 h | "see source" | https://github.com/nhoyh/HR_IMU_falldetection_dataset ; IEEE 8970371 | Fall **external test only**; fusion replay (with 60 s stillness padding) |
| **MIT-BIH Arrhythmia** (Moody & Mark 2001) | 47 patients (48 records, 201/202 same patient) | Chest ECG, beat + rhythm annotations | 360 Hz (source; not stated in repo) | 48 × 30 min; 57,744 frames, 24.06 h | ODC-By 1.0 | https://physionet.org/content/mitdb/1.0.0/ ; DOI 10.13026/C2F305 | Rhythm (CV) |
| **AFDB** (MIT-BIH AF DB) | 25 records (~10 h each; 00735 & 03665 annotations only) | Chest ECG, rhythm annotations | — | zip 440 MB (annotations only compacted) | ODC-By 1.0 | https://physionet.org/content/afdb/1.0.0/ ; DOI 10.13026/C2MW2D | Rhythm (CV, stride 20, 1 copy) |
| **LTAFDB** (Petrutiu et al., Europace 2007) | 84 records × 24–25 h | Chest ECG, reviewed beat labels + rhythm | — | zip 1.78 GB | ODC-By 1.0 | https://physionet.org/content/ltafdb/1.0.0/ ; DOI 10.13026/C2QG6Q | Rhythm (CV, stride 60, 1 copy) |
| **PAMAP2** (Reiss & Stricker, ISWC 2012) | 9 (14 recordings in replay) | Dominant-wrist IMU (acc ±16 g, gyro), chest-strap HR; 18 activities, no falls | 100 Hz | zip 657 MB (nested) | CC BY 4.0 | https://archive.ics.uci.edu/dataset/231/... ; DOI 10.24432/C5NW2H | Activity **external test**; fall negatives (CV); replay (10.69 h) |
| **Capture-24** (Chan Chang et al., Sci. Data 2024) | 151 participants | Wrist Axivity AX3 accelerometer, no gyro/PPG; camera-annotated, Walmsley-2020 labels | 100 Hz | zip 6.5 GB, ~24 h each, read in place | CC BY 4.0 | https://ora.ox.ac.uk/objects/uuid:99d7c092-d865-4a19-b096-cc16440cd001 | Activity (CV); fall hard negatives (2/3 of people, CV); **55 people / 1,403 h held out** for false-alarm replay |
| **Stress-Predict** (Iqbal et al., Sensors 2022) | 35 (34 labelled, S02–S35) | Empatica E4 (same as WESAD); Stroop, interview, hyperventilation | E4 | zip 24 MB | MIT | https://github.com/italha-d/Stress-Predict-Dataset ; DOI 10.3390/s22218135 | Stress **external test only**; replay (31.34 h) |
| **MIMIC PERform AF** (Charlton et al., Physiol. Meas. 2022) | 35 ICU adults (19 AF / 16 non-AF), 20 min each | Fingertip PPG + lead-II ECG (+ impedance resp.) | 125 Hz | WFDB zips 11.9 MB + 10.2 MB (MD5 verified) | ODbL 1.0 | https://zenodo.org/records/6807403 ; DOI 10.5281/zenodo.6807403 | Rhythm **external test only**; kept out of `LOADERS` so it never reaches training |

Notes:
- Each registry entry records source URL, licence, SHA-256 and subject list; `data/manifest/wearable_datasets.json`
  holds SHA-256 of every source and compacted file (in git) (ARCH §5.1, CTX §3.D).
- Lossless compaction: one `.npz` per subject; SisFall raw deleted after value-for-value check **4505/4505**;
  archives read in place without extraction (`data/archive.py`) (CTX §3.D, ARCH §5.2).
- Total newly downloaded in P3 v2 ≈ **9.5 GB** (CTX §4). Disk need ≈ 10 GB zips + ~6 GB processed (TG §1).
- Data report also records: PPG-DaLiA firmware-style BPM vs ECG: frames with BPM 74.9 %, median abs err
  **6.3 bpm**, within 10 bpm **65.1 %**; beat detection vs ECG on S1: 11,431 ECG beats, 11,547 PPG beats, 64.3 %
  matched (DATA-R).
- Peak |acc| medians falls vs ADL: HIFD 13.34 / 2.05 g; SisFall 5.29 / 1.70 g; UP-Fall 3.34 / 1.56 g (DATA-R).
- "Frames with RR": HIFD 99.2 %, MIT-BIH 99.2 %, PPG-DaLiA 99.3 %, WESAD 98.6 %, SisFall/UP-Fall 0 % (DATA-R).
- HIFD gravity removed in source; reconstructed from quaternion (unit test `test_hifd_gravity_restoration_identity_orientation`).

#### 2.2 Splits, grouping, inclusion/exclusion
- **Group = `<dataset>:<subject>`**; outer CV = 5-fold `StratifiedGroupKFold(shuffle=True, random_state=42)`;
  "no subject appears in both train and test" (TOUR-R; `tournament/run.py`).
- Splits per row: `cv` (tournament), `external` (test only), `replay` (fall-free daily life of never-trained
  people) (`heads/build.py`).
- Label-purity rule: majority label must cover **≥ 0.8** of window (`MIN_PURITY = 0.8`) for stress, activity,
  rhythm; otherwise window excluded.
- MIT-BIH 202 mapped to 201 (`MITBIH_SAME_PATIENT`).
- Rhythm sources: (loader, copies, stride frames) = MIT-BIH (2, 4), AFDB (1, 20), LTAFDB (1, 60) — "Long Holter
  records are sub-sampled so the 24 h LTAFDB records do not swamp the 30 min MIT-BIH records."
- Fall daily-life stride 2 frames (every 3 s) for PPG-DaLiA/WESAD/PAMAP2; Capture-24 CV stride 20 (30 s) +
  hard-negative ends; Capture-24 activity stride 80 (30 s windows every 2 min).
- Capture-24 split: `replay` if `int(sha256(pid)[:8],16) % 3 == 0` else `cv`.
- PAMAP2 excluded from activity training: "its light/active split runs the other way at the wrist (PPG-DaLiA
  'light' = table soccer moves the wrist more than its walking/cycling 'active'). Pooling it cost PPG-DaLiA
  0.90 → 0.83 macro-F1" (`heads/build.py`; CTX §4).

#### 2.3 Activity pooling experiment (`data/processed/wearable/tournament/activity_capture24_check.json`)

| Training mix | PPG-DaLiA | PAMAP2 | Capture-24 | all |
|---|---|---|---|---|
| pooled (all three) | 0.832 | 0.801 | 0.731 | 0.801 |
| Capture-24 weight 0.25 | 0.832 | 0.814 | 0.72 | 0.801 |
| Capture-24 weight 0.1 | 0.829 | 0.821 | 0.709 | 0.799 |
| no Capture-24 | 0.831 | 0.819 | 0.662 | 0.742 |
| DaLiA only | 0.902 | 0.614 | 0.557 | 0.643 |
| **DaLiA + Capture-24 (chosen)** | 0.901 | 0.591 | 0.732 | 0.791 |
| PAMAP2 only | 0.555 | 0.886 | 0.697 | 0.725 |

---

### 3. Frame contract (schema v2) — `src/ml/wearable/schema.py`

Constants: `SCHEMA_VERSION = 2`; `FRAME_PERIOD_S = 1.5`; `IMU_HZ = 50`; `RR_MIN_MS, RR_MAX_MS = 270, 2000`
("222–30 bpm"); `ACC_MAG_MAX_G = 16·√3 = 27.7 g` ("|a| with every axis at the ±16 g full scale"; HIFD falls peak
at 27.2 g). Out-of-range values → NaN + warning. RR values outside 270–2000 ms dropped with a warning.

| # | Flat field | JSON path | Unit | Valid range |
|---|---|---|---|---|
| 1 | imu_acc_max_g | imu.acc_max_g | g | 0 – 27.7 |
| 2 | imu_acc_min_g | imu.acc_min_g | g | 0 – 27.7 |
| 3 | imu_acc_mean_g | imu.acc_mean_g | g | 0 – 27.7 |
| 4 | imu_acc_std_g | imu.acc_std_g | g | 0 – 27.7 |
| 5 | imu_gyro_max_dps | imu.gyro_max_dps | deg/s | 0 – 2000 |
| 6 | imu_gyro_mean_dps | imu.gyro_mean_dps | deg/s | 0 – 2000 |
| 7 | imu_tilt_deg | imu.tilt_deg | deg | 0 – 180 |
| 8 | imu_n | imu.n | samples | 0 – 1000 |
| 9 | imu_fall_detected | imu.fall_detected | bool | 0/1 |
| 10 | ppg_finger_on | ppg.finger_on | bool | 0/1 |
| 11 | ppg_bpm | ppg.bpm | bpm | 20 – 250 |
| 12 | ppg_spo2 | ppg.spo2 | % | 50 – 100 |
| 13 | ppg_spo2_valid | ppg.spo2_valid | bool | 0/1 |
| 14 | ppg_perfusion | ppg.perfusion | % | 0 – 100 |
| 15 | eda_us | eda.us | µS | 0 – 100 |
| 16 | eda_slope_us_s | eda.slope_us_s | µS/s | −10 – 10 |
| 17 | eda_baseline_us | eda.baseline_us | µS | 0 – 100 |
| 18 | eda_raw | eda.raw | ADC | 0 – 4095 |
| 19 | eda_norm | eda.norm | ratio | 0 – 1 |
| 20 | temp_skin_c | temp.skin_c | °C | 10 – 45 |
| 21 | baro_hpa | baro.hpa | hPa | 300 – 1300 |
| 22 | baro_dmax_hpa | baro.dmax_hpa | hPa | 0 – 200 |
| 23 | water_wet | water.wet | bool | 0/1 |
| 24 | power_batt_v | power.batt_v | V | 2.5 – 4.5 |
| 25 | gps_lat | gps.lat | deg | −90 – 90 |
| 26 | gps_lng | gps.lng | deg | −180 – 180 |
| 27 | gps_sats | gps.sats | count | 0 – 50 |
| 28 | gps_hdop | gps.hdop | ratio | 0 – 99.99 |
| 29 | gps_breached | gps.breached | bool | 0/1 |
| — | rr_ms (list) | ppg.rr_ms | ms | each 270 – 2000 |

Envelope: `schema` (const 2), `device_id` (required), `fw`, `seq` (int ≥ 0), `uptime_ms` (int ≥ 0). A JSON Schema
(draft 2020-12) is generated from `FIELDS` (`json_schema()`). **29 scalar fields + RR list.**

- **v1 backward compatibility** (`_parse_v1`): legacy snapshot mapped onto v2; only exact-meaning fields filled
  (acc_mag→acc_mean, gyro_mag→gyro_mean, fall flag, finger_on from category ≠ "No Finger", bpm only if finger on,
  GSR raw/norm, GPS). **v1 SpO2 never trusted** (`spo2_valid=False`; v1 firmware SpO2 was simulated).
- Example payload ~**650 bytes** per frame (ARCH §4.2); firmware config says ~0.8 kB each, batches of ≤ 10
  frames (~8 kB body) (`src/firmware/include/config.h`).
- Frame JSON example in ARCH §3 differs from the as-built schema (ARCH shows `eda.gsr_raw/gsr_norm/gsr_slope/
  baseline`; schema.py uses `eda.us/slope_us_s/baseline_us/raw/norm`) — see §15.

#### 3.1 Firmware side of the contract (`src/firmware/include/config.h`, ARCH §4)
- Scheduler: 100 Hz fast tick (PPG FIFO), **IMU 50 Hz**, EDA 20 Hz, frame every 150 ticks = **1.5 s**; slow tick
  25 Hz (barometer, GPS UART), skin temp 1 Hz, water ~2 Hz, battery 0.2 Hz.
- PPG: finger contact IR DC ≥ 30,000; RR window 270–2000 ms; BPM lost after 4,000 ms without a beat; SpO2 max
  age 3,000 ms; real SpO2 by Maxim algorithm over a 4 s buffer updated every 1 s (ARCH §4.1).
- Offline queue: 320 frames = **8 min** (~50 KB RAM); event frames (impact ≥ 3.0 g etc.) kept preferentially.
- **On-device fall detector (edge safety net):** free fall < 0.5 g, impact ≥ 3.0 g within 1,000 ms, settle
  1,000 ms, stillness 2,000 ms with std < 0.15 g and gyro < 40 °/s.
- Sensors: MPU6050 0x68, MAX30102 0x57, MAX30205 0x48 (±0.1 °C), BMP388 0x77 (0.5–2 m drop ≈ 0.06–0.24 hPa;
  +~98 hPa per metre of water), water electrodes GPIO 33, battery divider 100k/100k GPIO 35, GSR GPIO 34;
  new analog inputs ADC1 only (ADC2 unusable with Wi-Fi) (ARCH §4.1).
- Firmware v2.2.0 builds: RAM 34.1 %, flash 53.1 % (CTX §4). Hardware untested (P7 "compiles, untested on hardware").

#### 3.2 Device emulator (`src/ml/wearable/emulator.py`, version 1.0.0)
- IMU anti-aliased `resample_poly` down to 50 Hz when source faster; per-frame |acc| max/min/mean/std, count,
  tilt = arccos(mean_z / ‖mean‖) in degrees; |gyro| max/mean.
- Beat detection on BVP: 2nd-order Butterworth band-pass **0.5–3.5 Hz**, 5 s RMS normalisation, `find_peaks`
  distance 0.33 s, prominence 0.5.
- Firmware BPM: RR accepted 270–2000 ms; EMA **0.9 old + 0.1 new**; BPM → NaN after `BPM_TIMEOUT_S = 4.0` s
  without a beat.
- EDA: per-frame mean µS, in-frame least-squares slope (µS/s), baseline = mean of first `EDA_BASELINE_S = 120` s.
- Missing source fields stay NaN; `imu_fall_detected` deliberately NaN.
- Unit test: 1.2 Hz pulse → 72 bpm, RR ≈ 833 ms (ARCH §5.3).

#### 3.3 ECG R-peak reference (`src/ml/wearable/data/ecg.py`)
Band-pass 5–20 Hz (order 3) at 250 Hz work rate, squared gradient, 0.15 s moving integration, adaptive height
0.3 × rolling 98th percentile over 5 s, min distance 0.3 s, refine to max |ECG| within ±75 ms. Reference HR: mean
over 8 s windows shifted 2 s (PPG-DaLiA convention), RR 0.27–2.0 s, ≥ 3 intervals. Validation vs PPG-DaLiA R-peaks:
98.7–99.3 % sensitivity, ~99.5 % precision, median HR error < 0.5 bpm (CTX §3.C.11). Match tolerance 50 ms.

---

### 4. Feature engineering (`src/ml/wearable/features/frame_features.py`, `features/engine.py`)

- `CALIB_FRAMES = 80` (first 120 s): bpm_base = nanmedian, eda_base = nanmean, temp_base = nanmedian; frozen after.
- RR cleaning for HRV (stress): drop intervals > 30 % from the window median.
- `rr_stats`: n, mean, SDNN, RMSSD, pNN50, CV, SD1 = RMSSD/√2, SD2 = √(2·SDNN² − SD1²), SD1/SD2, turning-point
  ratio. Sample entropy m = 2, r = 0.2·std.
- Same `FeatureEngine` (ring buffer, deque maxlen = longest window) used offline (`replay`) and online.

#### 4.1 Window, stride, feature count per head (DATA-R; REG; `heads/build.py`; `runtime.HEAD_STRIDE`)

| Feature set | Window | Stride (frames) | Tabular features | Sequence input (T × C) |
|---|---|---|---|---|
| stress | 40 frames = 60 s | 4 (6 s) | **24** | 40 × 7 |
| fall (with gyro; v1 only) | 4 frames = 6 s | 1 | 15 | 4 × 7 |
| fall_acc_only (**served fall head**) | 4 frames = 6 s | 1 | **12** | 4 × 5 |
| activity | 20 frames = 30 s | 4 | **12** | 20 × 6 |
| hr_trust | 8 frames = 12 s | 2 | **12** | 8 × 6 |
| rhythm | 40 frames = 60 s | 4 | **15** | 64 × 2 (last 64 RR) |

#### 4.2 Feature lists (REG `features`, exact order)
- **stress (24):** eda_rel_mean, eda_rel_max, eda_std, eda_slope, eda_rise_frac (share of frames with EDA slope
  > 0.005 µS/s), eda_range, bpm_mean, bpm_rel, bpm_std, bpm_slope, temp_delta, temp_slope, acc_activity,
  acc_peak, hrv_n, hrv_mean, hrv_sdnn, hrv_rmssd, hrv_pnn50, hrv_cv, hrv_sd1, hrv_sd2, hrv_sd1_sd2, hrv_tpr.
  Sequence channels: EDA/base − 1, EDA slope, BPM/base − 1, mean RR (s), temp − base, acc std, acc mean.
- **fall_acc_only (12):** peak_g, trough_g, trough_before_peak_g, peak_minus_trough, peak_rel_median,
  peak_rel_mean_level, peak_pos, std_max, std_after_peak, level_dev_last (|mean_last − 1 g|), tilt_change,
  tilt_change_after_peak. (Gyro set adds gyro_peak, gyro_mean, gyro_at_peak = 15.) Sequence: acc max, min,
  mean, std, tilt/180.
- **activity (12):** acc_std_mean, acc_std_max, acc_std_p90, acc_max_mean, acc_max_max, acc_min_min,
  acc_level_dev, tilt_mean, tilt_std, moving_frac (std > 0.05 g), bpm_mean, bpm_rel.
- **hr_trust (12):** bpm_last, bpm_std, bpm_range, bpm_missing_frac, beats_vs_expected, no_rr_frac, rr_cv,
  rr_succ_mad, hr_from_rr_vs_bpm, acc_std_mean, acc_std_max, acc_peak.
- **rhythm (15):** rr_n, rr_mean, rr_sdnn, rr_rmssd, rr_pnn50, rr_cv, rr_sd1, rr_sd2, rr_sd1_sd2, rr_tpr,
  rr_sampen, rr_big_jump_frac (|ΔRR| > 0.2·median), rr_max_min_ratio, rr_mad_rel, hr_mean. Sequence: RR/median − 1
  and ΔRR/median for the last 64 beats.

ARCH §6 design-time feature list (e.g. SCR count/amplitude, LF/HF proxy, gyro peak for fall, pressure change)
differs from the as-built lists above — use the REG lists for papers.

#### 4.3 Head datasets — window counts

| Head | v1 (P2, DATA-R) | v2 (P3 v2, TOUR-R / REG) |
|---|---|---|
| stress | 5,268 / 15 subj (non_stress 3,694; stress 1,574) | same 5,268 / 15 (external Stress-Predict 17,323 windows) |
| fall | 41,867 / 55 subj (no_fall 34,463; fall 7,404); HIFD external 3,447 / 21 (3,031 / 416); replay 144,139 windows / 30 groups (~60 h) | **561,095 / 190 subj** (no_fall 553,691; fall 7,404); HIFD external 3,447 |
| activity | 15,405 / 15 (rest 10,995; light 729; active 3,681) | **90,349 / 166** (rest 68,980; light 14,090; active 7,279); PAMAP2 external 4,207 |
| hr_trust | 43,106 / 15 (unreliable 14,857; reliable 28,249) | **72,003 / 30** (unreliable 23,361; reliable 48,642) |
| rhythm | 22,812 / 46 (regular 19,696; abnormal 3,116) | **126,579 / 155** (regular 70,762; abnormal 55,817; "44 % abnormal") |

(CTX log says activity "94,556 windows / 175 subjects" and "light 729 → 15,485" for the pooled-with-PAMAP2 version
later reverted; the served activity head is 90,349 / 166.)

---

### 5. Tier-1 heads — task definitions and labels (`heads/build.py`, ARCH §7, cards)

| Head | Task / output | Positive / classes | Label rule | Intended use (card) |
|---|---|---|---|---|
| stress | P(stress) | non_stress (WESAD baseline id 1 + amusement id 3) vs stress (TSST id 2) | majority protocol label, purity ≥ 0.8 | "Evidence for ELEVATED_STRESS and CRUSH_ENTRAPMENT ... never a diagnosis" (crush no longer uses it since P5) |
| fall | P(fall/impact) | no_fall vs fall | only windows containing the impact frame of a fall trial = 1; other fall-trial windows excluded; all ADL/daily-life windows = 0 | "Impact/fall evidence for CONCUSSIVE_STASIS; fusion requires post-impact immobility" |
| activity | {rest, light, active} | 3 classes | PPG-DaLiA: sitting/driving/lunch/working → rest; table soccer → light; stairs/cycling/walking → active. Capture-24 Walmsley: sleep/sedentary → rest; light; MVPA → active. PAMAP2 (external): lying/sitting/TV/computer/driving → rest; standing/vacuum/ironing/laundry/cleaning → light; walk/run/cycle/stairs/sport → active. Purity ≥ 0.8 | "Context for fusion (rest vs exercise) so exertion is not mistaken for shock or stress" |
| hr_trust | P(BPM reliable) | unreliable vs reliable | reliable iff |firmware-style BPM at window end − ECG reference HR| ≤ **10 bpm** | "Gates heart-rate-based rules" |
| rhythm | P(irregular rhythm) | regular {(N, (SBR} vs abnormal {(AFIB, (AFL, (B, (T, (VT, (VFL, (SVTA, (IVR, (AB, (BII, (NOD, (J} | majority rhythm annotation, purity ≥ 0.8; other codes excluded | "Screening evidence of an irregular rhythm from wrist RR intervals; not an ECG diagnosis" |

MIT-BIH rhythm frame counts (DATA-R): (N 42,191; (AFIB 5,304; (P 4,405; (B 1,667; (SBR 1,203; (T 758; (AFL 522;
(PREX 498; (BII 467; (NOD 189; (SVTA 146; (VT 143; (IVR 97; (VFL 94; (AB 60. [(P and (PREX are neither regular
nor abnormal → excluded.]

---

### 6. Tournament

#### 6.1 Protocol (TOUR-Y, `tournament/run.py`, `models/candidates.py`, TG §3)
- Seed **42**; outer **5** folds StratifiedGroupKFold by subject; inner **3** folds (Stage-2 only); **2** finalists;
  **1,000** subject-level bootstrap resamples.
- **Stage 1 (screening):** every applicable candidate with defaults, outer CV; top 2 by fold-mean macro-F1 advance;
  logreg advances if top-2.
- **Stage 2 (semifinal):** Optuna TPE (seed 42) + MedianPruner (3 startup trials), tuning inside each outer
  training split with 3-fold inner StratifiedGroupKFold; defaults enqueued as first trial. Selected params =
  fold with best inner macro-F1.
- **Stage 3 (final):** paired per-fold comparison + subject bootstrap of macro-F1 difference; winner if CI low
  > 0, else smaller/faster (size_kb, latency_ms). Soft-vote (mean probability) of the two finalists adopted only if
  its bootstrap CI vs single winner excludes 0.
- Optuna budgets per outer fold (TOUR-Y): xgboost 20 trials / 240 s; lightgbm 20 / 240 s; mlp 8 / 360 s;
  cnn1d 8 / 360 s; logreg 10 / 60 s; extratrees 12 / 300 s; minirocket 6 / 420 s.
- Primary metric macro-F1 at 0.5 / argmax (Tier-1 thresholds fixed later in P4).
- Recorded per candidate: fold mean ± sd macro-F1, balanced acc., AUROC, AUPRC (JSON only), sensitivity,
  specificity, log-loss, ECE (10 bins, top-label), fit s/fold, latency ms (median of 50 single-row predicts),
  size KB; MLflow (`mlruns/mlflow.db`, experiment `wearable-<head>`).
- Runtimes: stress 6.1 min, fall 131.5 min, activity 63.5 min, HR-trust 51.7 min, rhythm 133.3 min (TOUR-R).
  v1 tournament: 80 min CPU (CTX §4).

#### 6.2 Candidates (`models/candidates.py`)
| # | Name | Input | Defaults | Search space |
|---|---|---|---|---|
| 0 | logreg (baseline) | tabular | median impute + standardise + L2 LR, C = 1.0, class_weight balanced | C ∈ [1e-3, 10] log |
| 1 | xgboost | tabular | 300 trees, depth 6, lr 0.08, subsample 0.8, colsample 0.8, mcw 1, λ 1; hist; balanced sample weights | n 100–800, depth 3–10, lr 0.02–0.3, … |
| 2 | lightgbm | tabular | 300 trees, 31 leaves, lr 0.08, min_child 20, subsample 0.8, colsample 0.8, λ 1; balanced | n 100–800, leaves 15–127, … |
| 3 | extratrees | tabular | 200 trees, max_features 0.5, min_samples_leaf 3; balanced; bootstrap capped 60k rows/tree when n > 60k; grown as 4 single-threaded sub-forests (joblib race fix) | n 100–400, max_features 0.2–1.0, leaf 1–30 |
| 4 | mlp | tabular | PyTorch: Linear–BN–ReLU–Dropout ×2 (128, 64), dropout 0.2, AdamW lr 1e-3, wd 1e-4 | h1 {64,128,256}, h2 {32,64,128}, dropout 0.05–0.5 … |
| 5 | cnn1d | raw frame sequence | Conv1d(k=3) C→32 + BN + ReLU + Dropout → Conv1d 32→64 + BN + ReLU → [mean ‖ max pool] → Linear 128→64 → ReLU → Dropout → out; dropout 0.2, AdamW lr 1e-3, wd 1e-4 | channels {16,32,64}, dropout 0.05–0.5, lr 3e-4–3e-3, wd 1e-5–1e-2 |
| 6 | minirocket | sequence + tabular | Own numpy multivariate MiniRocket (Dempster et al. KDD 2021): 84 length-9 kernels, ≤ 4 exponential dilations, random 1–3 channel subsets, PPV pooling, n_features 1000; concatenated with standardised tabular → LR C = 0.1; needs T ≥ 8 | n_features {500,1000,2000}, C 1e-3–3 |

Torch training: max 40 epochs, patience 6, batch 256 (1024 if > 100k rows), 15 % group-held validation split,
class-weighted cross-entropy.

#### 6.3 Summary of winners (TOUR-R)

| Head | Winner (v2) | Macro-F1 v2 (all data) | v2 on v1 dataset | v1 winner · macro-F1 | Runner-up | Baseline logreg | Decision |
|---|---|---|---|---|---|---|---|
| stress | **minirocket** | 0.937 | 0.937 | logreg · 0.885 | extratrees (0.893) | 0.877 | significant |
| fall | **vote(extratrees+cnn1d)** | 0.898 | — | xgboost · 0.972 | cnn1d (0.842) | 0.691 | soft-vote significantly better |
| activity | **extratrees** | 0.801 | 0.903 | xgboost · 0.903 | lightgbm (0.794) | 0.737 | significant |
| hr_trust | **vote(cnn1d+extratrees)** | 0.767 | 0.753 | cnn1d · 0.755 | extratrees (0.753) | 0.729 | soft-vote significantly better |
| rhythm | **cnn1d** | 0.932 | 0.822 | logreg · 0.752 | minirocket (0.912) | 0.892 | significant |

v1 (P3) winners (CTX §4): stress logreg 0.885 (tie with MLP); activity XGBoost 0.903 (tie LightGBM); HR-trust 1D-CNN
0.755 (significant over MLP, CI +0.007…+0.021); rhythm logreg 0.752 (tie MLP); fall XGBoost 0.972, sens 0.968 /
spec 0.987 (tie LightGBM); HIFD external macro-F1 0.864, sens 0.995, spec 0.919; but daily-life replay of acc-only
fall model **119** false alarms / 8 h at 0.5 (**48** at 0.9) → motivated P3 v2.

#### 6.4 Per-head stage tables (TOUR-R; AUPRC from TJSON, out-of-fold, uncalibrated)

**Stress** — 5,268 windows / 15 subjects; folds 4,208–4,221 train / 1,047–1,060 test, 3 test subjects each.

| Stage | Model | Macro-F1 (mean ± sd) | Bal. acc | AUROC | AUPRC | Sens | Spec | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | **minirocket** | 0.932 ± 0.049 | 0.928 | 0.989 | 0.974 | 0.887 | 0.969 | 0.143 | 0.023 | 3.6 | 6.84 | 44 |
| S1 | **extratrees** | 0.893 ± 0.067 | 0.897 | 0.976 | 0.953 | 0.858 | 0.935 | 0.201 | 0.053 | 0.5 | 37.57 | 4162 |
| S1 | mlp | 0.884 ± 0.072 | 0.890 | 0.947 | 0.919 | 0.860 | 0.919 | 0.272 | 0.026 | 2.0 | 0.61 | 53 |
| S1 | logreg | 0.873 ± 0.078 | 0.870 | 0.956 | 0.908 | 0.797 | 0.942 | 0.338 | 0.062 | 0.0 | 0.39 | 2 |
| S1 | cnn1d | 0.873 ± 0.080 | 0.878 | 0.945 | 0.914 | 0.842 | 0.914 | 0.288 | 0.028 | 4.1 | 0.63 | 67 |
| S1 | lightgbm | 0.856 ± 0.082 | 0.866 | 0.952 | 0.908 | 0.827 | 0.905 | 0.459 | 0.092 | 0.4 | 1.56 | 777 |
| S1 | xgboost | 0.850 ± 0.085 | 0.862 | 0.952 | 0.907 | 0.830 | 0.894 | 0.415 | 0.090 | 0.6 | 1.04 | 363 |
| S2 | **minirocket** | 0.936 ± 0.046 | 0.930 | 0.989 | 0.973 | 0.885 | 0.975 | 0.152 | 0.023 | 3.0 | 6.89 | 25 |
| S2 | extratrees | 0.885 ± 0.091 | 0.886 | 0.967 | 0.941 | 0.823 | 0.950 | 0.231 | 0.054 | 0.4 | 46.65 | 8846 |

Stage 3: paired fold diff +0.050 (leader better 4/5); bootstrap diff +0.044, 95 % CI [+0.001, +0.096]; soft-vote
0.933, vs single −0.004 [−0.011, +0.002] → not adopted. Params `{"n_features": 1000, "C": 0.1}`. Per-class F1
(S2): non_stress 0.964, stress 0.911. External Stress-Predict (17,323 windows): minirocket macro-F1 0.549, sens
0.594, spec 0.550, AUROC 0.588 (AUPRC 0.400); extratrees 0.575 / 0.488 / 0.672 / 0.621 (AUPRC 0.469); vote
0.557 / 0.568 / 0.581 / 0.618 (AUPRC 0.470).

**Fall** — 561,095 windows / 190 subjects; minirocket not entered (window 4 < kernel span).

| Stage | Model | Macro-F1 | Bal. acc | AUROC | AUPRC | Sens | Spec | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | **extratrees** | 0.868 ± 0.024 | 0.900 | 0.990 | 0.817 | 0.805 | 0.995 | 0.024 | 0.005 | 10.7 | 8.01 | 19778 |
| S1 | **cnn1d** | 0.835 ± 0.037 | 0.978 | 0.995 | 0.917 | 0.967 | 0.988 | 0.034 | 0.003 | 231.0 | 0.52 | 66 |
| S1 | xgboost | 0.820 ± 0.039 | 0.948 | 0.992 | 0.849 | 0.908 | 0.988 | 0.036 | 0.003 | 12.7 | 0.41 | 1062 |
| S1 | lightgbm | 0.819 ± 0.038 | 0.948 | 0.991 | 0.848 | 0.908 | 0.988 | 0.037 | 0.004 | 6.4 | 0.57 | 1023 |
| S1 | mlp | 0.722 ± 0.038 | 0.966 | 0.993 | 0.820 | 0.962 | 0.970 | 0.079 | 0.004 | 55.1 | 0.41 | 47 |
| S1 | logreg | 0.691 ± 0.034 | 0.955 | 0.988 | 0.696 | 0.947 | 0.963 | 0.137 | 0.013 | 2.1 | 0.36 | 2 |
| S2 | **extratrees** | 0.875 ± 0.021 | 0.871 | 0.988 | 0.820 | 0.746 | 0.997 | 0.021 | 0.004 | 5.6 | 4.93 | 12840 |
| S2 | **cnn1d** | 0.841 ± 0.035 | 0.977 | 0.995 | 0.911 | 0.965 | 0.989 | 0.031 | 0.003 | 239.3 | 0.64 | 66 |

Stage 3: paired diff +0.035 (4/5); bootstrap +0.034 [+0.013, +0.058]; soft-vote 0.898 vs single +0.022 [+0.009,
+0.034] → **adopted** (vote AUPRC 0.895). Params: extratrees `{n_estimators 100, max_features 0.43371571882817456,
min_samples_leaf 2}`; cnn1d `{channels 32, dropout 0.2, lr 0.001, weight_decay 0.0001}`. Per-class F1 (S2):
extratrees no_fall 0.997 / fall 0.756; cnn1d 0.994 / 0.689.
Per source (vote, OOF): Capture-24 434,332 windows / 96 subj acc 0.996 (one class); PAMAP2 12,814 / 9 acc 0.997;
PPG-DaLiA 43,144 / 15 acc 0.999; **SisFall** 33,145 / 38: macro-F1 0.944, bal. acc 0.954, sens 0.940, spec 0.968;
**UP-Fall** 8,722 / 17: 0.910, 0.872, 0.748, 0.997; WESAD 28,938 / 15 acc 0.999.
External HIFD (3,447): extratrees 0.868 / sens 0.760 / spec 0.970 / AUROC 0.981 (AUPRC 0.824); cnn1d 0.806 /
0.639 / 0.958 / 0.935 (AUPRC 0.621); vote 0.822 / 0.659 / 0.964 / 0.974 (AUPRC 0.773).
Daily-life false alarms (Tier-1, uncalibrated vote; alarms within 10 s merged; target ≤ 1 / 8 h; 2,053 OOF fall trials; OOF daily life 70.73 h):

| Threshold | FA / 8 h held-out Capture-24 (55 people, 1,403.29 h) | FA / 8 h OOF daily life | Fall-trial sensitivity (OOF) |
|---|---|---|---|
| 0.5 | 17.08 (2,996 events) | 8.71 | 0.948 |
| 0.7 | 5.67 (995) | 1.81 | 0.852 |
| 0.9 | 1.03 (181) | 0.11 | 0.596 |
| 0.95 | 0.38 (66) | 0.11 | 0.445 |

**Activity** — 90,349 windows / 166 subjects.

| Stage | Model | Macro-F1 | Bal. acc | AUROC (macro OvR) | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|
| S1 | **extratrees** | 0.799 ± 0.018 | 0.809 | 0.953 | 0.323 | 0.026 | 20.6 | 30.96 | 149040 |
| S1 | **lightgbm** | 0.780 ± 0.019 | 0.815 | 0.950 | 0.356 | 0.014 | 11.8 | 1.99 | 3021 |
| S1 | xgboost | 0.779 ± 0.022 | 0.816 | 0.950 | 0.360 | 0.010 | 14.0 | 1.66 | 3233 |
| S1 | cnn1d | 0.765 ± 0.026 | 0.817 | 0.948 | 0.399 | 0.013 | 113.1 | 0.62 | 67 |
| S1 | mlp | 0.763 ± 0.022 | 0.810 | 0.943 | 0.407 | 0.012 | 53.6 | 0.71 | 48 |
| S1 | minirocket | 0.746 ± 0.018 | 0.799 | 0.940 | 0.419 | 0.009 | 124.9 | 8.00 | 56 |
| S1 | logreg | 0.735 ± 0.011 | 0.781 | 0.924 | 0.472 | 0.045 | 0.9 | 0.49 | 2 |
| S2 | **extratrees** | 0.799 ± 0.017 | 0.798 | 0.953 | 0.313 | 0.022 | 2.6 | 5.24 | 103223 |
| S2 | lightgbm | 0.792 ± 0.017 | 0.787 | 0.949 | 0.400 | 0.062 | 10.8 | 1.86 | 18057 |

Stage 3: paired +0.007 (5/5); bootstrap +0.007 [+0.003, +0.012]; vote 0.799, −0.002 [−0.006, +0.001] → not adopted.
Per-class F1 (S2): extratrees rest 0.942 / light 0.668 / active 0.793; lightgbm 0.940 / 0.664 / 0.779. Per source:
Capture-24 74,944 / 151: 0.732 (bal. acc 0.724); PPG-DaLiA 15,405 / 15: 0.903 (0.876). External PAMAP2 (4,207):
extratrees 0.590 (AUROC 0.886); lightgbm 0.611 (0.943); vote 0.607 (0.892). AUPRC: not applicable (3-class).

**HR-trust** — 72,003 windows / 30 subjects; 5–7 test subjects per fold.

| Stage | Model | Macro-F1 | Bal. acc | AUROC | AUPRC | Sens | Spec | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | **cnn1d** | 0.756 ± 0.012 | 0.793 | 0.871 | 0.938 | 0.727 | 0.858 | 0.445 | 0.036 | 38.4 | 0.58 | 67 |
| S1 | **extratrees** | 0.752 ± 0.009 | 0.770 | 0.860 | 0.931 | 0.783 | 0.756 | 0.439 | 0.012 | 6.3 | 36.43 | 277997 |
| S1 | xgboost | 0.747 ± 0.009 | 0.775 | 0.858 | 0.930 | 0.746 | 0.804 | 0.459 | 0.033 | 1.9 | 0.65 | 1137 |
| S1 | lightgbm | 0.746 ± 0.010 | 0.775 | 0.859 | 0.931 | 0.743 | 0.808 | 0.458 | 0.035 | 1.0 | 0.72 | 1008 |
| S1 | mlp | 0.742 ± 0.009 | 0.780 | 0.862 | 0.932 | 0.711 | 0.848 | 0.465 | 0.038 | 12.6 | 0.51 | 47 |
| S1 | minirocket | 0.736 ± 0.006 | 0.762 | 0.841 | 0.923 | 0.741 | 0.783 | 0.495 | 0.031 | 18.4 | 2.73 | 42 |
| S1 | logreg | 0.726 ± 0.006 | 0.752 | 0.830 | 0.919 | 0.733 | 0.772 | 0.514 | 0.017 | 0.2 | 0.51 | 2 |
| S2 | **cnn1d** | 0.755 ± 0.014 | 0.791 | 0.870 | 0.938 | 0.729 | 0.853 | 0.442 | 0.033 | 42.6 | 0.67 | 67 |
| S2 | **extratrees** | 0.750 ± 0.011 | 0.766 | 0.858 | 0.930 | 0.791 | 0.740 | 0.439 | 0.010 | 4.7 | 25.95 | 134755 |

Stage 3: paired +0.005 (4/5); bootstrap +0.004 [−0.004, +0.011] → tie → cnn1d (smaller/faster); soft-vote 0.767 vs
cnn1d +0.010 [+0.006, +0.013] → **adopted** (AUPRC 0.939). Params: cnn1d `{channels 32, dropout
0.31939631788866646, lr 0.0004296748115469076, weight_decay 2.9375384576328295e-05}`; extratrees `{100,
0.43371571882817456, 2}`. Per-class (S2): cnn1d unreliable 0.705 / reliable 0.810; extratrees 0.681 / 0.826. Per
source (vote): PPG-DaLiA 43,106 / 15: 0.753, 0.780, sens 0.719, spec 0.841; WESAD 28,897 / 15: 0.785, 0.802, 0.826,
0.779. No external test.

**Rhythm** — 126,579 windows / 155 subjects.

| Stage | Model | Macro-F1 | Bal. acc | AUROC | AUPRC | Sens | Spec | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | **cnn1d** | 0.923 ± 0.034 | 0.932 | 0.978 | 0.974 | 0.930 | 0.935 | 0.180 | 0.014 | 233.5 | 0.65 | 65 |
| S1 | **minirocket** | 0.901 ± 0.043 | 0.914 | 0.971 | 0.960 | 0.928 | 0.901 | 0.220 | 0.014 | 64.6 | 7.68 | 43 |
| S1 | mlp | 0.896 ± 0.042 | 0.908 | 0.966 | 0.960 | 0.904 | 0.912 | 0.236 | 0.014 | 14.6 | 0.78 | 49 |
| S1 | xgboost | 0.891 ± 0.042 | 0.904 | 0.964 | 0.957 | 0.908 | 0.900 | 0.251 | 0.025 | 3.8 | 0.64 | 1167 |
| S1 | lightgbm | 0.891 ± 0.042 | 0.903 | 0.965 | 0.959 | 0.907 | 0.900 | 0.246 | 0.024 | 2.2 | 0.92 | 1020 |
| S1 | extratrees | 0.890 ± 0.046 | 0.903 | 0.965 | 0.958 | 0.909 | 0.897 | 0.245 | 0.011 | 5.8 | 35.81 | 132148 |
| S1 | logreg | 0.880 ± 0.050 | 0.894 | 0.954 | 0.929 | 0.903 | 0.885 | 0.274 | 0.018 | 0.5 | 0.38 | 2 |
| S2 | **cnn1d** | 0.923 ± 0.034 | 0.932 | 0.978 | 0.974 | 0.930 | 0.935 | 0.180 | 0.014 | 232.4 | 0.56 | 65 |
| S2 | minirocket | 0.901 ± 0.043 | 0.914 | 0.971 | 0.960 | 0.928 | 0.901 | 0.220 | 0.014 | 65.1 | 6.14 | 43 |

Stage 3: paired +0.022 (5/5); bootstrap +0.020 [+0.012, +0.028]; vote 0.930 vs single −0.002 [−0.005, +0.000] → not
adopted. Params `{channels 32, dropout 0.2, lr 0.001, weight_decay 0.0001}` (defaults won every fold). Per-class
(S2): cnn1d regular 0.939 / abnormal 0.924. Per source: AFDB 29,889 / 25: 0.936, 0.935, 0.919, 0.952; LTAFDB 73,878 /
84: 0.938, 0.939, 0.942, 0.935; MIT-BIH 22,812 / 46: 0.822, 0.870, 0.823, 0.917.

---

### 7. Final Tier-1 models (P4) — calibrated, thresholded, exported

#### 7.1 Pipeline (`final/train.py`, `final/export.py`, TG §3)
1. Refit winner on all CV windows; export each member to ONNX (opset **17**; ai.onnx.ml 3 for sklearn; XGBoost /
   LightGBM opset 15); torch wrappers for MLP/1D-CNN/MiniRocket.
2. **Parity check** on 4,000 random CV rows: promotion requires max |Δp| < **0.02** and argmax flips < **0.2 %**
   (`PARITY_MAX_ABS = 0.02`, `PARITY_MAX_FLIPS = 0.002`).
3. **Calibration** on tournament OOF winner probabilities: **Platt** (LR on logit(p1), C = 1e6) for binary heads;
   **temperature scaling** (bounded 0.05–20, NLL) for activity. Evaluated with 5-fold `GroupKFold` cross-fitting by
   subject ("calibration is never evaluated on its own fit data").
4. **Threshold** on cross-fitted calibrated OOF probabilities, grid 0.05–0.94 step 0.01 then 0.95–0.9975 step
   0.0025: stress / HR-trust / rhythm = maximise macro-F1 (tie → closest to 0.5); fall = most sensitive threshold
   (event-level) with OOF daily-life false alarms ≤ **1.0 / 8 h** (`FALL_FA_BUDGET_PER_8H`; fallback keeps
   sensitivity ≥ 0.80).
5. Golden rows (`golden.npz`), `card.md`, `metrics.json`, `calibration.json`, registry entry with SHA-256.
6. Compiled numpy forests for Extra-Trees members: must match ONNX within **1e-5**, no flips.

#### 7.2 Final metrics (FINAL-R, CARD(h), MET(h)) — OOF on unseen subjects, cross-fitted calibration, subject-bootstrap 95 % CI

| Head | Model | Macro-F1 (95 % CI) | AUROC | AUPRC* | Sens (95 % CI) | Spec | PPV | Log-loss | ECE before → after | Threshold | Rule |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stress | minirocket | **0.935** (0.889–0.970) | 0.985 | 0.973 | 0.945 (0.878–0.989) | 0.944 | 0.878 | 0.150 | 0.023 → 0.008 | **0.33** | max OOF macro-F1 |
| hr_trust | vote(cnn1d+extratrees) | **0.768** (0.742–0.792) | 0.872 | 0.939 | 0.792 (0.749–0.831) | 0.775 | 0.880 | 0.409 | 0.015 → 0.004 | **0.59** | max OOF macro-F1 |
| rhythm | cnn1d | **0.932** (0.915–0.949) | 0.977 | 0.974 | 0.900 (0.869–0.929) | 0.961 | 0.947 | 0.181 | 0.014 → 0.008 | **0.61** | max OOF macro-F1 |
| activity | extratrees | **0.801** (0.778–0.820) | 0.953 | n/a | — | — | — | 0.311 | 0.022 → 0.011 | argmax | multi-class |
| fall | vote(extratrees+cnn1d) | **0.867** (0.843–0.886) | 0.994 | 0.895 | 0.614 (0.554–0.666) window-level | 0.999 | 0.920 | 0.013 | 0.006 → 0.001 | **0.72** | most sensitive with OOF daily-life FA ≤ 1/8 h |

*AUPRC is not in the final reports/cards; values shown are the tournament OOF (pre-calibration) AUPRC of the same
model/vote from TJSON (Platt/temperature are monotone so ranking metrics are unchanged in principle, but this was
not recomputed in the repo). **Brier score: not recorded anywhere.**

Balanced accuracy (uncalibrated argmax, MET): stress 0.930, fall 0.961, activity 0.798, hr_trust 0.791, rhythm 0.932.
Per-class F1 (calibrated): stress non_stress 0.960 / stress 0.910; fall no_fall 0.997 / fall 0.737; activity rest
0.942 / light 0.668 / active 0.793; hr_trust unreliable 0.702 / reliable 0.834; rhythm regular 0.942 / abnormal 0.923.

**Per source dataset (calibrated, at threshold)**:
- stress WESAD = overall.
- fall: SisFall 0.861 (0.834–0.885), sens 0.637, spec 0.995, AUROC 0.989; UP-Fall 0.704 (0.645–0.761), sens 0.274,
  spec 1.000, AUROC 0.940.
- activity: Capture-24 0.732 (0.713–0.750), AUROC 0.937; PPG-DaLiA 0.903 (0.863–0.934), AUROC 0.980.
- hr_trust: PPG-DaLiA 0.755 (0.722–0.790), sens 0.751, spec 0.798, AUROC 0.858; WESAD 0.784 (0.757–0.803), sens 0.850,
  spec 0.734, AUROC 0.892.
- rhythm: AFDB 0.937 (0.885–0.969), sens 0.887, spec 0.976, AUROC 0.970; LTAFDB 0.936 (0.913–0.955), 0.914, 0.964,
  0.983; MIT-BIH 0.832 (0.705–0.904), 0.758, 0.942, 0.931.

**External tests (never used for training/tuning)**:
- stress → Stress-Predict: macro-F1 **0.521** (0.479–0.559), AUROC 0.589, sens 0.667, spec 0.459, PPV 0.367, ECE 0.339,
  log-loss 1.727.
- activity → PAMAP2: macro-F1 **0.590** (0.562–0.616), AUROC 0.886, ECE 0.209; F1 rest 0.767 / light 0.173 / active 0.830.
- fall → HIFD: macro-F1 **0.716** (0.678–0.753), AUROC 0.974, sens 0.337 (0.271–0.402), spec 0.991, PPV 0.838, ECE 0.043.
- fall → held-out Capture-24 (55 people, 1,403.29 h): **2.14 FA / 8 h** at 0.72 (375 events). Curve: 0.5 → 5.09
  (892 ev); 0.7 → 2.40 (421); 0.9 → 0.79 (138); 0.95 → 0.38 (66); 0.98 → 0.14 (24); 0.99 → 0.07 (13).
- Fall threshold curve (MET(fall), OOF calibrated): at 0.5 → OOF daily FA 1.70 / 8 h, event sensitivity 0.840; 0.6 →
  1.36, 0.798; **0.72 → 0.905, 0.727** (window sens 0.614, spec 0.9993, PPV 0.920); 0.3 → 4.98, 0.908. CTX: "At 0.72,
  73 % of fall trials are detected."

#### 7.3 Calibration parameters (REG / calibration.json)

| Head | Method | Parameters | OOF log-loss before → after |
|---|---|---|---|
| stress | Platt | a = 0.5885905873324683, b = 0.33701988011088235 | 0.1519 → 0.1503 |
| hr_trust | Platt | a = 1.1353111719479818, b = 0.5260593424269081 | 0.4262 → 0.4089 |
| rhythm | Platt | a = 0.8511953927442791, b = −0.1559641489844982 | 0.1799 → 0.1812 |
| activity | Temperature | T = 0.9170011843106313 | 0.3134 → 0.3113 |
| fall | Platt | a = 1.4642619545647209, b = −1.367902247728989 | 0.0198 → 0.0132 |

Serving formula (`serving/calibration.py`): Platt p1 = σ(a·logit(p) + b) with p clipped to [1e-6, 1−1e-6];
temperature softmax(log p / T). Soft-vote members averaged before calibration.

#### 7.4 Artifacts, sizes, parity (REG, cards)

| Head | Files (bytes) | ONNX↔Python parity max |Δp| | Compiled forest parity vs ONNX (4,000 rows) |
|---|---|---|---|
| stress | model_minirocket.onnx 59,977 | 5.4e-3 | — |
| hr_trust | model_cnn1d.onnx 63,341; model_extratrees.onnx 75,144,736; forest_extratrees.npz 64,947,381 | 3.2e-7 | 2.50e-7, 0 flips |
| rhythm | model_cnn1d.onnx 61,773 | 6.7e-7 | — |
| activity | model_extratrees.onnx 65,637,022; forest_extratrees.npz 54,090,457 | 2.6e-7 | 2.98e-7, 0 flips |
| fall | model_extratrees.onnx 6,662,850; model_cnn1d.onnx 62,949; forest_extratrees.npz 5,838,041 | 1.2e-6 | 2.38e-7, 0 flips |

CTX P4 row: "Parity was checked on 4,000 rows: max |Δp| ≤ 1.2e-6, MiniRocket 5.4e-3, 0 argmax flips." Runtime golden
test: served outputs within **1e-4** of `golden.npz` (`tests/ml/test_runtime.py`). HR-trust Extra-Trees: 73 MB,
1.9 M nodes, ~280 s ONNX load (CTX). Registry SHA-256 recorded for every file; model-file hashes verified 96/96 in QA
(CTX §4).

#### 7.5 Latency / resources
- Tournament single-row latency (Python, median of 50): see stage tables (e.g. minirocket 6.89 ms, cnn1d 0.56–0.67 ms,
  extratrees 4.93–46.65 ms).
- Serving: load all five heads ≈ **0.5 s** (vs ~9 min with ONNX tree kernels); one frame through all heads + fusion
  ≈ **5–60 ms** CPU (ARCH §10); "Runtime uses ~230 MB RAM and ~60 ms CPU per frame" (CTX P5 row).
- ARCH §14 design estimate: onnxruntime ~50 MB, "heads total < 10 MB" — superseded by actual sizes above.
- On-device inference: none (TinyML is future work, RESILIENCE §9.2).

---

### 8. Serving runtime (`src/ml/wearable/serving/runtime.py`)

- `HEAD_STRIDE = {stress: 4, fall: 1, activity: 4, hr_trust: 2, rhythm: 4}` (= training strides); a head is
  evaluated when its window is full and `(i − (T−1)) % stride == 0`; output **held** between evaluations.
- **Input-availability gating** (`head_available`): fall/activity need finite `imu_acc_max_g` in window; others need
  `ppg_finger_on` > 0 somewhere; stress also needs `eda_us`; rhythm needs beats in ≥ half the frames; else head =
  `None` ("never a guess from NaNs").
- Fusion thresholds = registry Tier-1 thresholds overridden by `fusion.yaml head_thresholds` (fall → 0.6).
- Head output to fusion: P(positive) for binary heads; class-probability vector for activity.
- Single-threaded onnxruntime sessions (`intra_op_num_threads = 1`), CPU provider.
- Ingest (ARCH §10): one `DeviceRuntime` per (device, boot); per-device lock, frames in `seq` order; ML outside the
  DB write transaction; missing models → device `UNKNOWN`, `/readyz` `wearable_ml: false`.
- **Triage coupling:** linked wearable in a critical state **+30** points (`wearable: <STATE>`), advisory **+5**
  (`src/backend/app/services/triage.py`); wearable SOS button **+40** (≥ P2). Extreme-case auto-reallocation requires
  P1 with score ≥ 80, linked wearable critical with risk ≥ **0.85** for ≥ **60 s** (`EXTREME_MIN_RISK = 0.85` in
  `services/sos.py`), environmental corroboration (water-disaster type, weather warning or rising river), and no
  free team; donor only a P4/P5 request not en route (RESILIENCE §2).

---

### 9. Tier-2 fusion engine (FUS-Y version **1.2.0**, FUS-PY)

#### 9.1 Mechanics
- Deterministic per-device state machine. Each frame: update derived signals → evaluate every state condition →
  per-state `_StateTimer` with **dwell_s** (condition must hold to enter) and **exit_s** (condition must be false to
  leave) → report the **most severe active** state.
- Severity order (first wins): CARDIAC_ARREST > ASPIRATION_HYPOXIA > HEMORRHAGIC_SHOCK > CONCUSSIVE_STASIS >
  CRUSH_ENTRAPMENT > HYPOTHERMIA_RISK > ELEVATED_STRESS > STABLE.
- Unavailable heads disable only the conditions that need them; engine never fails on a missing model.
- Derived-signal horizons: HR 600 s, SpO2 120 s, temp 900 s, baro 120 s, GPS 600 s; acc-peak buffer 6 + 3 s.
- Personal BPM baseline = median of first **80** finite BPM values (same 2 min as feature layer).
- Impact registration: when calibrated `p_fall ≥ fall threshold (0.6)` **or** firmware fall flag; peak g = max
  `imu_acc_max_g` over last **6 s** (IMPACT_WINDOW_S = fall window, because the head crosses threshold a few frames
  after impact); stores (t, peak g, min baro over 30 s, p). New impact if > 5 s since last or higher peak.
- Missing (NaN) device flags are false (`_flag`), fixing the `bool(nan)` bug.
- GPS displacement: equirectangular, 111,320 m/deg.

#### 9.2 Signals (FUS-Y `signals`)
immobile_acc_std_g **0.03** (per-frame |acc| std below → no movement); moving_acc_std_g **0.10**; battery_low_v **3.4**;
eda_high_ratio **1.3** (EDA / personal baseline); gps_still_m **10.0**.

**SENSOR_FAULT overlay** = (no contact AND moving) OR battery < 3.4 V → cardiac/hypoxia/shock conditions suppressed;
evidence line "SENSOR_FAULT: contact lost while moving or battery low - cardiac rules suppressed".
**HR trusted** = contact AND (hr_trust head unavailable OR p ≥ hr_trust threshold → registry **0.59**, default 0.5).

#### 9.3 States

| ID | State | Basis | Alert level | Base risk | Dwell / exit (s) | Entry condition (as coded) | Key parameters |
|---|---|---|---|---|---|---|---|
| 7 | CARDIAC_ARREST | ml+rule | critical | 0.95 | 0 / 15 | (a) contact ≥ 10 s AND no beat ≥ 10 s AND immobile ≥ 10 s AND no sensor fault; **or** (b) HR trusted AND rhythm p ≥ **0.8** AND (BPM > **180** or < **30**) | no_beat_s 10, brady 30, tachy 180, rhythm_p 0.8 |
| 3 | ASPIRATION_HYPOXIA | rule | critical | 0.85 (+0.1 if submerged) | 15 / 30 | valid SpO2 (≤ 5 s old) < **90 %** OR (max SpO2 in last 10 s − current) > **2 %**; no sensor fault. Submerged = wet AND baro − 60 s min ≥ **5 hPa** → risk +0.1, evidence "submerged (wet, pressure rising)" | spo2_low 90, drop_pct 2.0, drop_window_s 10, submerged_dp_hpa 5.0 |
| 4 | HEMORRHAGIC_SHOCK | ml+rule | critical | 0.85 | 60 / 120 | HR trusted AND BPM > **120** AND activity head = **rest** AND HR slope (60 s) > 0 AND skin-temp slope (120 s) < 0 AND EDA/baseline ≥ **1.3**; no sensor fault ("ATLS class II–IV pattern") | hr_min 120, hr_slope_window 60, temp_slope_window 120 |
| 5 | CONCUSSIVE_STASIS | ml+rule | critical | 0.80 (+0.1 if severe) | 0 / 30 | impact within last **120 s** AND immobile since (impact − 3 s) AND immobile ≥ **30 s**. Severe = peak ≥ **6.0 g** OR baro rise ≥ **0.12 hPa** (~1 m) since impact → risk +0.1, evidence "severe impact (> 6 g or ~1 m drop)" | fall_window_s 120, immobile_s 30, severe_impact_g 6.0, severe_drop_hpa 0.12; fall op. point 0.6 |
| 6 | CRUSH_ENTRAPMENT | ml+rule | critical | 0.75 | 0 / 60 | GPS moved < 10 m over 120 s (or no GPS) AND HR trusted with BPM − personal baseline ≥ **20 bpm** AND [triggered: immobile ≥ **120 s** with stillness starting within **600 s** of a detected impact, OR fallback: immobile ≥ **300 s**]. `use_stress_head: false` (stress_p 0.7 unused) | immobile_s 120, require_impact_s 600, untriggered_immobile_s 300, hr_above_baseline_bpm 20 |
| 2 | HYPOTHERMIA_RISK | rule | critical | 0.60 | 120 / 300 | skin temp < **32.0 °C** AND skin-temp slope (300 s) < 0 AND ((HR trusted AND BPM < **60**) OR wet) | skin_c 32.0, temp_slope_window_s 300, brady_bpm 60 |
| 1 | ELEVATED_STRESS | ml | **advisory** | 0.40 | 120 / 60 | stress head p > **0.85** AND activity ∈ {rest, light, unknown} | p 0.85 |
| 0 | STABLE | — | none | 0.05 | — | otherwise | — |

**Risk score formula** (`step`): `risk = base_risk[state]`; +0.1 (capped at 1.0) for ASPIRATION_HYPOXIA when
submerged and for CONCUSSIVE_STASIS when severe impact. No continuous combination of head probabilities.

**Output contract**: `ml_health_state`, `ml_state_id`, `ml_risk_score` (3 dp), `alert_level`, `basis`, `evidence[]`
(state evidence + optional SENSOR_FAULT line + "HR <n> trusted/untrusted"), `active_states[]`, `sensor_fault`,
`heads{}` (activity as label, others rounded to 3 dp), `unavailable_inputs[]`, `model_versions{}`,
`fusion_version`, `ml_mode: "hybrid"`.

#### 9.4 Scenario tests (`tests/ml/test_fusion.py`, 13 tests) — synthetic trajectories only here
Normal activity stays STABLE (400 frames); fall then immobility → CONCUSSIVE_STASIS first between **30 and 45 s**
after impact and never ≤ 20 s, with "severe impact" evidence at 7.5 g; fall followed by walking → no alarm; no beats
with contact & immobile → CARDIAC_ARREST (not at < 10 s); contact lost while moving → sensor fault not cardiac;
SpO2 low 15 s → hypoxia, escalates when submerged; stress needs dwell and rest context; missing heads reported and
rules still run; hysteresis keeps state briefly after condition clears; missing wet flag is not wet; stressed
sitting without impact is not crush; impact then still with raised HR → crush; long stillness with raised HR → crush
without impact.

#### 9.5 Real-data replay (REPLAY-R; `data/processed/wearable/replay/p5_replay.json`)
Serving path end-to-end (FeatureEngine → calibrated heads at stride with gating → FusionEngine). Fusion 1.2.0, fall
operating point 0.6. "Critical" = all states except ELEVATED_STRESS; rates are state **entries** per 8 h.

| Dataset | Heads trained on it | Recordings | Hours | Critical alarms / 8 h | Entries / 8 h by state | Sensor-fault time |
|---|---|---|---|---|---|---|
| PPG-DaLiA | fall, activity, hr_trust | 15 | 35.97 | **0.667** (3) | CONCUSSIVE_STASIS 0.222, ELEVATED_STRESS 16.237, HYPOTHERMIA_RISK 0.445 | 0.0 % |
| WESAD | stress, fall, hr_trust | 15 | 24.13 | **0.332** (1) | CONCUSSIVE_STASIS 0.332, ELEVATED_STRESS 6.3 | 0.0 % |
| PAMAP2 | fall | 14 | 10.69 | **2.244** (3) | CONCUSSIVE_STASIS 2.244 | 0.0 % |
| Stress-Predict | none (stress external) | 34 | 31.34 | **0.511** (2) | CRUSH_ENTRAPMENT 0.511, ELEVATED_STRESS 10.21 | 0.0 % |
| Capture-24 | none (held-out people) | 55 | 1,403.35 | **1.197** (210) | CONCUSSIVE_STASIS 1.197 | 21.1 % |

Total replayed daily life ≈ 1,505.5 h (sum of the five rows). Target was ≤ 1 per 8 h (ARCH §9); met on PPG-DaLiA,
WESAD, Stress-Predict; not met on PAMAP2 (3 events in 10.7 h) and Capture-24 (1.20).
Time share: PPG-DaLiA STABLE 60.45 %, ELEVATED_STRESS 38.81 %; WESAD STABLE 82.4 %, stress 17.55 %; Stress-Predict
STABLE 70.67 %, stress 29.19 %.

Head availability: PPG-DaLiA stress 99 % / fall 100 / activity 100 / hr_trust 100 / rhythm 99; WESAD same pattern;
PAMAP2 stress 0 % (no EDA); Stress-Predict 98/100/99/100/98; Capture-24 stress 0, fall 100, activity 100, hr_trust 0,
rhythm 0.

WESAD ELEVATED_STRESS time share by protocol phase: baseline **0.0 %**, stress (TSST) **86.4 %**, amusement **0.0 %**.

**HIFD falls → CONCUSSIVE_STASIS** (external; trials + 60 s of final frame repeated = semi-synthetic lying still):
104 fall trials → **84.6 %** stasis; 245 ADL trials → **6.9 %**; latency from impact median **32.25 s**, range
[31.5, 39.0] s.

Example evidence lines (first occurrence per state; re-run on 2026-10-31 with the current fusion code, and all rates are
unchanged): "capture24 / CONCUSSIVE_STASIS (P003, t=71931.0 s): fall p=0.64 @ 7.1 g; immobile 30 s; severe impact (> 6 g or
~1 m drop)"; "pamap2 / CONCUSSIVE_STASIS (subject102, t=651.0 s): fall p=0.76 @ 9.1 g; ..."; "stress_predict /
CRUSH_ENTRAPMENT (S29, t=937.5 s): immobile 300 s, HR 119 (+28 vs baseline)". The daily-life stasis false alarms are
therefore real wrist impacts (3.4–9.1 g) followed by 30 s of stillness.

#### 9.6 Option analyses behind the rule choices (`data/processed/wearable/replay/`)

**Crush rule options** (`crush_options.json`; crush FA / 8 h, critical FA / 8 h in brackets):

| Option | PPG-DaLiA (36.0 h) | WESAD (24.1 h) | PAMAP2 (10.7 h) | Stress-Predict (31.3 h) |
|---|---|---|---|---|
| A original (still 120 s + stress head or HR+20) | 1.78 (2.22) | 4.64 (4.64) | 0.0 (2.24) | **14.29** (14.29) |
| B + impact trigger (10 min) | 0.0 (0.44) | 0.0 (0.0) | 0.0 (2.24) | 0.0 (0.0) |
| C HR+20 only (no stress head) | 0.44 (0.89) | 0.99 (0.99) | 0.0 (2.24) | 2.81 (2.81) |
| D impact trigger + HR+20 only | 0.0 (0.44) | 0.0 (0.0) | 0.0 (2.24) | 0.0 (0.0) |
| E still 300 s + HR+20 only | 0.0 (0.44) | 0.0 (0.0) | 0.0 (2.24) | **0.51** (0.51) |
Chosen: **D + E fallback** (FUS-Y comment: "option D + E fallback").

**Fall operating point through fusion** (`fall_operating_points.json`; CONCUSSIVE FA / 8 h; HIFD caught / ADL alarm):

| Fall p | Capture-24 (1,403.4 h) | PAMAP2 | PPG-DaLiA | WESAD | Stress-Predict | HIFD falls caught | HIFD ADL alarm |
|---|---|---|---|---|---|---|---|
| 0.4 | 2.314 | 2.244 | 1.335 | 0.663 | 0.255 | 0.904 | 0.078 |
| 0.5 | 1.716 | 2.244 | 0.667 | 0.332 | 0.0 | 0.894 | 0.078 |
| **0.6** | **1.197** | 2.244 | 0.222 | 0.332 | 0.0 | **0.846** | 0.069 |
| 0.72 | 0.735 | 2.244 | 0.0 | 0.0 | 0.0 | 0.615 | 0.037 |
| 0.8 | 0.553 | 0.748 | 0.0 | 0.0 | 0.0 | 0.442 | 0.02 |

**Stress operating points** (`stress_operating_points.json`; alerts / 8 h; WESAD time shares):

| Setting | WESAD alerts | WESAD baseline share | WESAD stress share | PPG-DaLiA alerts | Stress-Predict alerts |
|---|---|---|---|---|---|
| p0.7, dwell 60 | 11.6 | 0.004 | 0.953 | 24.91 | 19.4 |
| p0.85, dwell 60 | 10.94 | 0.0 | 0.94 | 23.8 | 17.1 |
| **p0.85, dwell 120 (chosen)** | 6.3 | 0.0 | 0.864 | 16.24 | 9.7 |
| p0.95, dwell 120 | 5.97 | 0.0 | 0.771 | 14.68 | 8.17 |
| p0.95, dwell 300 | 3.32 | 0.0 | 0.364 | 10.23 | 3.06 |

---

### 10. External validation — rhythm head on real PPG (AF-R; `data/processed/wearable/external/mimic_perform_af.json`)

- Data: MIMIC PERform AF, 35 ICU adults (19 AF / 16 non-AF), 20 min, fingertip PPG + lead-II ECG @ 125 Hz, per-subject
  labels; none in rhythm training data. Head unchanged (v2.0.0 1D-CNN, threshold 0.61, 40-frame windows, stride 4).
- Method: (a) PPG resampled 125 → **64 Hz** (E4 training rate), beats via `emulator.detect_beats` + firmware RR window
  (device path); (b) ECG R-peaks via validated detector (reference). Subject score = median window probability.
  95 % CIs: 1,000 bootstrap resamples of subjects, stratified by class.

| Input | Windows (available) | Window AUROC [95 % CI] | Sens @0.61 | Spec @0.61 | Window macro-F1 [95 % CI] | Subject AUROC | Subject sens / spec |
|---|---|---|---|---|---|---|---|
| (a) PPG beats | 6,685 / 6,685 (100 %), 3,629 AF | **0.987** [0.968, 1.000] | 0.936 | 0.941 | **0.938** [0.894, 0.976] | **1.000** [1.000, 1.000] | 19/19, 15/16 (subject macro-F1 0.971) |
| (b) ECG R-peaks | 6,641 / 6,685 (99.3 %), 3,585 AF | 1.000 [0.999, 1.000] (0.9997) | 0.899 | 1.000 (0.9997) | 0.945 [0.891, 0.982] | 1.000 | 18/19, 16/16 (subject macro-F1 0.971) |

Per-subject notes: non_af_012 only PPG subject error (FP; median p 0.70 PPG vs 0.01 ECG; 1,100 vs 1,633 RR accepted);
non_af_014 borderline (0.32 vs 0.04); af_008 only ECG miss (0.41 ECG, 0.81 PPG); af_004 ECG detector 77 % windows
available. Interpretation: model separates AF almost perfectly on clean RR; PPG beat detection costs specificity
(0.94 vs 1.00); a beat-quality gate (e.g. HR-trust) would target this.

Other external tests summarised in §7.2: Stress-Predict (stress), PAMAP2 (activity), HIFD + held-out Capture-24
(fall). HR-trust has no external test.

---

### 11. Weather forecaster v1.0.0 (WX, WX-CARD, `models/weather/registry.json`, `src/ml/weather/config/weather.yaml`)

#### 11.1 Data
- Site Chennai (13.0827, 80.2707), tz Asia/Kolkata, elevation 16 m.
- Training: Open-Meteo archive API (ERA5/ERA5T reanalysis, 0.25°, ~5-day lag; `archive_lag_days: 6`), hourly
  `temperature_2m, relative_humidity_2m, precipitation, wind_speed_10m, wind_gusts_10m, surface_pressure,
  dew_point_2m, cloud_cover`; 2015-01-01 .. 2026-10-24, **103,560 h, no gaps**; cache ~1.7 MB parquet.
- Live: Open-Meteo forecast API (`past_days=N&forecast_days=1`, trimmed to current hour = model analysis, not station).
- Offline fallback: Meteostat hourly CSV (km/h → m/s; sea-level → surface pressure at 0.12 hPa/m × 16 m).
- Gaps ≤ 6 h interpolated; missing rain = 0. Network failures never raise.

#### 11.2 Targets, features, candidates
- Targets: temp (°C), RH (%), rain (mm/h), 10 m wind (m/s), surface pressure (hPa), horizons **1–48 h**, quantiles
  **0.1/0.5/0.9**; plus 24 h rain accumulation for hours 1–24 and 25–48. Smooth variables modelled as change from origin.
- Features (causal, tested by truncation and future-poisoning): current values; lags 1, 2, 3, 6, 12, 24, 48, 168 h;
  6/24 h rolling mean/std; 24 h max/min temp; dew-point depression; pressure tendency 3/24 h; rain accumulations
  3/6/24/72 h; hours since rain; 7-day antecedent precipitation index; local hour & day-of-year sin/cos (origin and
  target); SW (Jun–Sep) / NE (Oct–Dec) monsoon flags; horizon; same-hour-last-day value. Needs 192 h history.
- Candidates: `persistence`; `seasonal_naive` (same hour, last observed day); `climatology` (quantiles by local
  week-of-year × hour); `lgbm` — LightGBM quantile regression, direct multi-horizon, one booster per variable × horizon
  group {1–3, 4–6, 7–12, 13–24, 25–48} × quantile, 300 trees (lr 0.05, 31 leaves, min_data_in_leaf 100, feature/bagging
  fraction 0.8, λ2 1.0), 90k sampled rows per group: **75 boosters + 3** for 24 h rain (78 total); `gru` — GRU(64)
  over last **72 h** of 8 weather + 4 calendar channels → 48 × 5 × 3 quantiles (median + softplus widths, monotone by
  construction), pinball loss, 10 epochs, batch 256, lr 0.002 (~7 min CPU), ONNX opset 17 (`seq.onnx` 882,653 bytes),
  onnxruntime vs torch max |diff| **1.4e-6** (1.43e-06); `blend` = average of lgbm and gru quantiles.
- Protocol: split by time — train 2015-01-09 .. 2025-04-24; calibration/selection 2025-04-24 .. 2025-10-24 (**1,448
  origins**); test 2025-10-24 .. 2026-10-24 (**2,905 origins** every 3 h). Backtests go through the same `Predictor`
  code as serving (ONNX GRU).
- Calibration: per candidate × variable × horizon, each quantile shifted by matching quantile of calibration residuals
  (empirical/split-conformal, smoothed over 5 neighbouring horizons), then physical bounds and sorting.
- Selection: per variable × band, lowest calibrated mean pinball loss on the calibration slice; test only scored.
  Production refit on full history.
- Timing (metrics.json): backtest fit lgbm 616.7 s, gru 403.0 s; final fit lgbm 571.7 s, gru 452.9 s; total 2,104.4 s.
- Serving: `WeatherService.load()` ~4 s, ~250 MB RSS; `forecast()` ~0.1–0.2 s; torch never imported (tested).

#### 11.3 Backtest headline (test year, calibrated; skill = 1 − MAE/MAE_ref; coverage target 0.80, raw in brackets)

| Variable | h | Chosen | MAE | MAE persistence | MAE s-naive | Skill vs pers. | Skill vs s-naive | p10–p90 coverage (raw) |
|---|---|---|---|---|---|---|---|---|
| temp (°C) | 6 | lgbm | 0.689 | 2.708 | 0.865 | 0.75 | 0.20 | 0.83 (0.74) |
| temp | 24 | blend | 0.805 | 0.864 | 0.864 | 0.07 | 0.07 | 0.82 (0.73) |
| temp | 48 | blend | 0.954 | 1.059 | 1.059 | 0.10 | 0.10 | 0.79 (0.70) |
| rh (%) | 6 | blend | 4.727 | 13.875 | 6.272 | 0.66 | 0.25 | 0.77 (0.74) |
| rh | 24 | blend | 5.648 | 6.273 | 6.273 | 0.10 | 0.10 | 0.79 (0.73) |
| rh | 48 | blend | 6.791 | 8.087 | 8.087 | 0.16 | 0.16 | 0.76 (0.69) |
| rain (mm/h) | 6 | blend | 0.162 | 0.256 | 0.264 | 0.37 | 0.39 | 0.80 (0.73) |
| rain | 24 | gru | 0.170 | 0.265 | 0.265 | 0.36 | 0.36 | 0.81 (0.77) |
| rain | 48 | gru | 0.171 | 0.290 | 0.290 | 0.41 | 0.41 | 0.80 (0.83) |
| wind (m/s) | 6 | blend | 0.636 | 1.046 | 0.788 | 0.39 | 0.19 | 0.76 (0.81) |
| wind | 24 | blend | 0.698 | 0.787 | 0.787 | 0.11 | 0.11 | 0.77 (0.82) |
| wind | 48 | blend | 0.814 | 0.924 | 0.924 | 0.12 | 0.12 | 0.73 (0.80) |
| pres (hPa) | 6 | blend | 0.455 | 1.930 | 0.827 | 0.76 | 0.45 | 0.79 (0.77) |
| pres | 24 | blend | 0.761 | 0.829 | 0.829 | 0.08 | 0.08 | 0.76 (0.76) |
| pres | 48 | blend | 1.180 | 1.266 | 1.266 | 0.07 | 0.07 | 0.72 (0.73) |

Chosen per band (registry): temp 1-3 blend, 4-6 lgbm, 7-12/13-24/25-48 blend; rh 1-3 lgbm, rest blend; rain 1-3/4-6/
7-12 blend, 13-24/25-48 gru; wind all blend; pres all blend.

#### 11.4 Mean pinball loss by band (test, calibrated; bold = best on test) — copy of WX §3

temp: 1–3 h persistence 0.3663 / s-naive 0.3006 / clim 0.3914 / **lgbm 0.1624** / gru 0.1777 / blend 0.1646 (chosen MAE
0.496, cov 0.78); 4–6 h 0.7169 / 0.3009 / 0.3910 / **0.2222** / 0.2561 / 0.2282 (0.682, 0.81); 7–12 h 0.9889 / 0.3008 /
0.3914 / **0.2531** / 0.2807 / 0.2547 (0.785, 0.79); 13–24 h 0.7344 / 0.3008 / 0.3917 / 0.2698 / 0.2856 / **0.2675**
(0.828, 0.78); 25–48 h 0.7846 / 0.3636 / 0.3933 / 0.3090 / 0.3265 / **0.3073** (0.948, 0.79).

rh: 1–3 2.0315 / 2.0594 / 2.4627 / **1.0615** / 1.1375 / 1.0659 (3.232, 0.76); 4–6 3.7822 / 2.0616 / 2.4643 / **1.4525** /
1.6115 / 1.4733 (4.584, 0.77); 7–12 4.9643 / 2.0617 / 2.4661 / 1.6301 / 1.7434 / **1.6250** (5.101, 0.77); 13–24 3.8895 /
2.0616 / 2.4655 / 1.7740 / 1.8343 / **1.7551** (5.543, 0.77); 25–48 4.2169 / 2.5875 / 2.4626 / 2.0647 / 2.0957 / **2.0329**
(6.476, 0.78).

rain: 1–3 0.0931 / 0.1180 / 0.0762 / 0.0563 / 0.0573 / **0.0561** (0.144, 0.79); 4–6 0.1150 / 0.1181 / 0.0764 / 0.0630 /
0.0641 / **0.0628** (0.156, 0.79); 7–12 0.1224 / 0.1181 / 0.0760 / **0.0641** / 0.0660 / 0.0644 (0.159, 0.80); 13–24 0.1241 /
0.1179 / 0.0756 / 0.0667 / 0.0674 / **0.0665** (0.163, 0.80); 25–48 0.1308 / 0.1320 / 0.0757 / 0.0701 / 0.0708 / **0.0698**
(0.165, 0.80).

wind: 1–3 0.2043 / 0.2601 / 0.2979 / **0.1568** / 0.1687 / 0.1585 (0.496, 0.75); 4–6 0.2990 / 0.2601 / 0.2987 / **0.1971** /
0.2124 / 0.1983 (0.628, 0.76); 7–12 0.3668 / 0.2601 / 0.2988 / **0.2108** / 0.2276 / 0.2113 (0.667, 0.76); 13–24 0.3260 /
0.2600 / 0.2989 / 0.2237 / 0.2293 / **0.2203** (0.694, 0.77); 25–48 0.3540 / 0.3022 / 0.2992 / 0.2572 / 0.2603 / **0.2526**
(0.797, 0.73).

pres: 1–3 0.2829 / 0.2625 / 0.5794 / 0.0926 / 0.0949 / **0.0915** (0.287, 0.78); 4–6 0.5328 / 0.2624 / 0.5790 / 0.1354 /
0.1406 / **0.1321** (0.418, 0.79); 7–12 0.4520 / 0.2625 / 0.5790 / 0.1701 / 0.1754 / **0.1671** (0.526, 0.79); 13–24 0.4623 /
0.2627 / 0.5789 / 0.2209 / 0.2279 / **0.2164** (0.684, 0.76); 25–48 0.5355 / 0.4034 / 0.5788 / 0.3329 / 0.3306 / **0.3227**
(1.029, 0.74).

"The learned models beat every baseline at every horizon for every variable." Margins lgbm vs blend ~1–3 % pinball.

#### 11.5 Heavy-rain event verification (test year)

| Event | Rule | Observed | Forecast | Hits | Hit rate | FAR | CSI |
|---|---|---|---|---|---|---|---|
| ≥ 7.6 mm/h, h 1–3 | p50 | 28 | 0 | 0 | 0.00 | – | 0.00 |
| ≥ 7.6 mm/h, h 1–3 | p90 | 28 | 34 | 8 | 0.29 | 0.76 | 0.15 |
| ≥ 7.6 mm/h, h 4–6 | p90 | 28 | 19 | 1 | 0.04 | 0.95 | 0.02 |
| ≥ 7.6 mm/h, h 7–12 | p90 | 55 | 20 | 0 | 0.00 | 1.00 | 0.00 |
| ≥ 7.6 mm/h, h 13–24 | p90 | 108 | 4 | 0 | 0.00 | 1.00 | 0.00 |
| ≥ 7.6 mm/h, h 25–48 | p90 | 216 | 0 | 0 | 0.00 | – | 0.00 |
| 24 h ≥ 64.5 mm, next 1–24 h | rain24 p90 | 35 | 26 | 15 | 0.43 | 0.42 | 0.33 |
| 24 h ≥ 64.5 mm, next 25–48 h | rain24 p90 | 35 | 24 | 15 | 0.43 | 0.38 | 0.34 |
| 24 h ≥ 64.5 mm (any) | p50 / sum of hourly p50 | 35 | 0 | 0 | 0.00 | – | 0.00 |

#### 11.6 Hazard rules (`hazards.py`, weather.yaml, `models/weather/1.0.0/hazards.json`)
Output `{type, level: watch|warning, from, to, reason}`; contiguous hours at same level = one episode.
- **heat:** NOAA heat index (Rothfusz + NWS adjustments) on p50 T/RH. Watch: HI ≥ 41 °C or T ≥ 37 °C (IMD coastal) or
  p90 T ≥ 40 °C. Warning: HI ≥ 54 °C or T ≥ 40 °C (IMD plains).
- **heavy_rain:** hourly p50 ≥ 7.6 mm/h warning, p90 ≥ 7.6 watch; 24 h (LightGBM rain24): p90 ≥ 64.5 mm (IMD heavy)
  watch; p50 ≥ 64.5 or p90 ≥ 115.6 mm (IMD very heavy) warning.
- **high_wind:** p50 ≥ 17.2 m/s warning; p50 ≥ 10.8 or p90 ≥ 17.2 watch (Beaufort 6 / 8).
- **flood_risk:** 7-day antecedent precipitation index (decay **0.85/day**) over observed + forecast rain vs
  training-climate percentiles: p97.5 = **92 mm** watch (92.149), p99.5 = **168 mm** warning (168.401). "A
  soil-saturation risk index, not a river-flow or inundation forecast."

#### 11.7 GloFAS river discharge (not a TRIDENT-trained model) — `src/backend/app/services/public_data.py`
Open-Meteo Flood API (GloFAS v4), daily `river_discharge`, `_median`, `_max`; 30 days back, 14 ahead; rivers Adyar
(13.005, 80.205), Cooum (13.072, 80.240), Kosasthalaiyar (13.215, 80.250); refreshed every 3 h; trend = mean of last 2
days vs previous 3: rising > 1.15, falling < 0.87; GloFAS cells ~5 km. Console colours ratio to 30-day median amber
> 1.3×, red > 2× (USER_GUIDE). Used as environmental corroboration ("rising river") for extreme auto-reallocation.

#### 11.8 Legacy
`src/ml/risk_analysis/network_analyzer.py` is a legacy NetworkX risk-propagation script with hard-coded area risks —
not a trained/validated model. v1 temperature-only LSTM removed (CTX P6 row; WX §header says still present — see §15).

---

### 12. Computer vision (ROV camera) — `src/cv/README.md`, `src/cv/vision/pipeline.py`, `__main__.py`

| Item | Value |
|---|---|
| Detector | **YOLOv8n** pretrained COCO weights `src/cv/yolov8_model/yolov8n.pt` (6,534,387 bytes); all **80 COCO classes**, confidence ≥ **0.4** (`CONF = 0.4`); people kept |
| Input size | Frames resized to **640 px** width (aspect kept); YOLO `imgsz` not set explicitly (ultralytics default — value not recorded in repo) |
| Face detection | OpenCV Haar cascade `haarcascade_frontalface_default.xml`, scaleFactor **1.1**, minNeighbors **5**, minSize **40×40** (desktop demo used 1.3 / 5 / 30×30) |
| Face recognition | OpenCV **LBPH** (`cv2.face.LBPHFaceRecognizer_create`, default params), model `trainer.yml` (48,557,779 bytes); match iff LBPH distance < **50** (`LBPH_MATCH_MAX`); match score = max(0, 1 − d/100) |
| Enrolment | `face_taker.py` captures **120** images per person (`samples_needed: 120`), 640×480 camera; `face_trainer.py` trains LBPH; `names.json` currently has 3 entries. Consent-only enrolment of responders; never victims/bystanders |
| Distance | Pinhole **D = W_real · f / w_pixels**; default **f = 700 px at 640 px width** (original laptop-webcam calibration); expected **±30 %** even calibrated; underwater effective focal length ≈ **1.33×** behind flat port. Calibration: f = w·D/W (e.g. A4 0.21 m at 1.5 m), repeat 2–3 distances |
| Real widths (m) | person (shoulders) 0.45, face 0.16, boat 2.5, car 1.8, truck 2.5, bus 2.55, motorcycle 0.8, bicycle 0.6, dog 0.30, cat 0.20, cow 0.70, horse 0.60, bottle 0.07, chair 0.50, backpack 0.30, handbag 0.30, suitcase 0.45, umbrella 0.9, bench 1.4, surfboard 0.50; others `distance_m: null` |
| Throughput | 0.3–0.5 s per frame on laptop CPU (YOLOv8n + face det/rec) → default **4 fps** processed; API relays to dashboards at up to **8 fps**; JPEG quality 70; feed marked offline after 5 s; camera reopened every 2 s |
| Security | vision key `X-ROV-Vision-Key`; single-use stream tickets valid **60 s**; MJPEG; heavy deps only in worker |
| Tests | `tests/ml/test_vision_pipeline.py`: pinhole check (person 140 px at f = 700 → 0.45·700/140 m), frame width 640, enrolled face recognised with match > 0.5, strangers not |
| Measured FPS / mAP on TRIDENT data | **not recorded** (no CV training or evaluation in repo; TG §6) |

Legacy demos: `detection.py` processes every 3rd frame, conf > 0.5; `main.py` legacy KNOWN_WIDTHS in cm (bottle 7,
chair 50, default 20), FOCAL_LENGTH 700, speech every 10 s, LBPH confidence < 50.

Limitations (README): LBPH sensitive to lighting/pose/scale, high false-match rate ("treat names as hints, not
identification"); Haar finds only roughly frontal faces; pinhole assumes square-on view; YOLOv8n trained on COCO in
air — recall drops in murky water, at night, partially submerged people.

---

### 13. Limitations stated in the repo (collected)

Wearable (cards, AF-R, REPLAY-R, ARCH §14, RESILIENCE §9):
- All heads trained on public datasets passed through the emulator, never on TRIDENT's own sensors; device is
  wrist-worn; firmware compiles but is untested on hardware.
- **Stress:** 15 WESAD lab subjects (TSST); transfer weak (Stress-Predict macro-F1 0.52) → advisory only, "low-confidence
  evidence". GSR domain shift (E4 µS vs Grove ADC) mitigated by subject-normalised features.
- **Fall:** falls from young/elderly volunteers onto mats (UP-Fall, SisFall), not real-world falls; accelerometer-only;
  SisFall waist-worn; daily-life negatives mostly healthy adults. Tier-1 alone misses the ≤ 1 FA / 8 h target on held-out
  people (2.14 at 0.72); HIFD window sensitivity 0.34. HIFD fusion test uses semi-synthetic 60 s stillness.
- **Activity:** behaviour-based labels; fuzzy light class (F1 0.668); Capture-24 has no heart rate; PAMAP2 external 0.59.
- **HR-trust:** label defined by firmware-style BPM vs ECG (10 bpm); a different PPG front-end changes "reliable".
- **Rhythm:** learned from ECG beat annotations degraded to PPG-like noise, not real wrist PPG of arrhythmia patients; AF
  and other irregular rhythms pooled as "abnormal"; external test is ICU fingertip PPG (not wrist), n = 35, per-subject
  labels, different task (AF vs non-AF), PPG resampled 125 → 64 Hz.
- **Rule-only states** (cardiac arrest, hypoxia, haemorrhagic shock, hypothermia) have no real-data validation of
  sensitivity: "validate with clinicians ... before claiming sensitivity" (RESILIENCE §9.5). Replay measures only
  false alarms (specificity) on healthy daily life.
- Fusion state is in memory: restart → each device recalibrates (~2 min) (RESILIENCE §1).
- 8 GB RAM / CPU-only training constraints (TG §1, ARCH §14).

Weather (WX §6): reanalysis not station data (ERA5 0.25° smooths extremes; live input a different product);
statistical short-range model, not NWP — beyond ~12 h skill over seasonal-naive modest (+0.07..+0.10 temp); heavy
hourly rain essentially unpredictable (p50 never reaches 7.6 mm/h; p90 CSI 0.15 at 1–3 h); 24 h p90 CSI ~0.33;
calibration doesn't fully transfer across seasons (Apr–Oct slice; wind 0.71–0.77, 48 h pressure 0.72–0.74
under-covered; wind calibration worse than raw ~0.80); rain coverage flattered by dry hours; heavy hourly rain more
frequent after 2021 (non-stationarity); single site.

CV: see §12.

---

### 14. Candidate novelty / inventive points (with evidence)

1. **Device-emulator-anchored training ("train exactly what we serve")** — every public dataset (13 of them, 6 sensor
   placements/devices) is converted into the *same* 1.5 s aggregated wrist-band telemetry frame the ESP32 firmware
   emits, reproducing firmware logic (50 Hz IMU anti-alias resampling, 270–2000 ms RR window, 0.9/0.1 BPM EMA, 4 s BPM
   timeout, µS EDA with 120 s baseline). Evidence: `emulator.py`, ARCH §1/§5.3, decision 1–3.
2. **Bit-identical training/serving features by construction** — head tables are built by replaying recordings frame by
   frame through the online `FeatureEngine`; a test round-trips JSON → `parse_payload` → engine and asserts identical
   features for all six feature sets; past-only personal calibration (first 80 frames). Evidence: decision 6–7,
   `features/engine.py`, `test_offline_features_equal_online_json_path`.
3. **Bandwidth-light aggregated frame contract (~650 B / 1.5 s) carrying beat-level RR lists** so server-side models get
   HRV/rhythm information without raw waveform streaming; schema v1→v2 back-compat with NaN-for-missing and
   input-availability gating. Evidence: schema.py, ARCH §3, runtime `head_available`.
4. **Two-tier hybrid: calibrated Tier-1 heads + deterministic, versioned Tier-2 rule fusion with corroboration**, each
   output tagged `basis` (`ml`/`rule`/`ml+rule`), `alert_level`, evidence strings and model versions; heads gate each
   other (HR-trust gates all HR rules; activity context gates shock/stress; fall impact + post-impact immobility for
   stasis; impact-triggered or long stillness + HR above personal baseline + GPS stillness for crush). Evidence: FUS-PY,
   FUS-Y, ARCH §9.
5. **Separation of Tier-1 and fusion operating points**, each chosen on its own pre-registered criterion (Tier-1 fall
   0.72 = most sensitive with OOF daily-life FA ≤ 1/8 h; fusion fall 0.6 chosen on end-to-end replay because
   post-impact stillness supplies the extra specificity: HIFD caught 61.5 % → 84.6 %). Evidence: REG threshold_rule,
   FUS-Y `head_thresholds`, `fall_operating_points.json`.
6. **Real-data false-alarm replay as the specificity check for rule states without positive data** (~1,505 h incl.
   1,403 h of held-out Capture-24 people), with rule changes justified by replay numbers (crush 14.29 → 0.51 / 8 h;
   hypothermia 118 → 2 after NaN-flag fix). Evidence: REPLAY-R, `crush_options.json`, decision 21–22, TG §3.
7. **Label-free hard-negative mining from free-living accelerometry with deterministic hash-based subject hold-out**
   (spike windows ≥ 1.8 g or ≤ 0.4 g, cap 1,500 per person; SHA-256 % 3 hold-out). Evidence: decision 16, `heads/build.py`.
8. **Accelerometer-only fall head to avoid a "missing-modality shortcut"** (gyro-present positives vs gyro-missing
   negatives). Evidence: decision 15.
9. **PPG-realistic augmentation of ECG beat annotations calibrated on simultaneous wrist-PPG/chest-ECG data** (σ_RR
   30–90 ms, 1–6 % missed, 0–4 % spurious beats) so a rhythm model trained on ECG RR transfers to PPG — externally
   confirmed on real PPG (window AUROC 0.987, subject AUROC 1.000). Evidence: `heads/augment.py`, decision 8, AF-R.
10. **Signal-quality ("HR-trust") head learned against an ECG reference**, used to gate heart-rate rules (label: BPM
    within 10 bpm of ECG HR; own validated R-peak detector extends labels to WESAD). Evidence: decision 11/13, card.
11. **Statistically gated per-head model tournament** (nested subject-grouped CV, baseline must be beaten, subject
    bootstrap CI decides, efficiency tie-break, soft-vote only if significantly better) with an own numpy MiniRocket.
    Evidence: run.py, TOUR-R.
12. **Compiled numpy tree forests derived from and parity-checked against ONNX** (≤ 3e-7, 0 flips) to cut load time from
    ~280 s/~9 min to 0.5 s while keeping ONNX canonical. Evidence: `serving/forest.py`, decision 25.
13. **Coupling of wearable fusion state into dispatch triage** (+30 critical / +5 advisory; extreme auto-reallocation only
    when P1 ≥ 80, wearable critical with risk ≥ 0.85 for ≥ 60 s, plus environmental corroboration from weather warning /
    rising GloFAS river). Evidence: triage.py, sos.py, RESILIENCE §2.
14. **Wearable submersion / fall-height inference from barometer + water contact** (+5 hPa while wet = submerged;
    ≥ 0.12 hPa ≈ 1 m drop = severe impact). Evidence: FUS-Y hypoxia/concussion, ARCH §4.1.
15. Weather: per-variable × per-horizon-band model selection on a separate calibration slice with split-conformal
    quantile shifts; antecedent-precipitation flood-risk index with climatological percentile thresholds. Evidence: WX §2, §4.

(Patent caveat: novelty vs prior art was not assessed in the repo; these are candidates only.)

---

### 15. Inconsistencies found between sources

> **Status:** items 1–9 and 12–16 were corrected in the docs on 2026-10-31 (the architecture doc now has an
> "as built" list), so cite the code values. Item 10 was handled by re-running the replay. Items 11 and 17 are
> still caveats to state when citing.

1. **Validation scheme for stress/activity:** ARCH §7 table says leave-one-subject-out (15 folds); as built all heads use
   5-fold StratifiedGroupKFold (TOUR-Y, TOUR-R).
2. **Calibration method:** ARCH §8 says isotonic regression; as built Platt (binary) / temperature (activity) (REG).
3. **Optuna budget:** ARCH §8 says 40 trials each; TOUR-Y budgets are 6–20 trials with time caps.
4. **Candidate count:** ARCH §2/§8 list 5 candidates; as built 7 (logreg + 6 contenders incl. Extra-Trees, MiniRocket).
5. **Artifact names / sizes:** ARCH §11 mentions `model.onnx` + `thresholds.json` "a few MB at most", §14 "heads total
   < 10 MB"; actual files `model_<member>.onnx`, `calibration.json`, Extra-Trees ONNX 6.7–75 MB.
6. **Frame JSON example (ARCH §3)** uses `eda.gsr_raw/gsr_norm/gsr_slope/baseline`; schema.py uses
   `eda.us/slope_us_s/baseline_us/raw/norm`. ARCH §2/§4.1 says MPU6050 100 Hz; decision 1 and firmware use 50 Hz.
7. **Fusion thresholds vs config:** `fusion.yaml shock.hr_trust_p: 0.5` is not read by the code; HR trust uses the
   registry hr_trust threshold (0.59) for all rules. Rhythm in CARDIAC_ARREST uses p ≥ 0.8, not the Tier-1 0.61.
   Stress fusion uses 0.85, not Tier-1 0.33. ARCH §9 says hypoxia "falling faster than 2 %/10 s"; code = drop of > 2
   percentage points from the 10 s max.
8. **ARCH §9 priority column** (e.g. ASPIRATION_HYPOXIA "3") is the state_id, not the severity rank; severity order is the
   FUS-Y list.
9. **CONCUSSIVE severe-drop:** ARCH says "drop > 1 m"; config is baro rise ≥ 0.12 hPa ("~1 m").
10. **Replay evidence samples** show "fall p=0.00 @ 1.0 g" for CONCUSSIVE_STASIS entries in daily life — implies those
    entries were triggered by something other than a high fall probability (e.g. the firmware flag path sets p = 1.0, so
    not that either), or the evidence was recorded before the P6 fix "fusion recorded the impact peak/probability at
    the wrong frame" (CTX P6 row). File timestamps support the latter: `p5_replay.json` is dated 2026-10-30 22:12
    while `serving/fusion.py` was last modified 23:40 the same day, so the replay numbers in REPLAY-R predate the
    current fusion code. Re-running `pipeline replay` before publication is advisable.
11. **Fall sensitivity numbers differ by definition:** window-level 0.614 (card) vs fall-trial (event) level 0.727 at 0.72
    (MET) vs tournament event sensitivity at uncalibrated thresholds (0.852 at 0.7). Tournament FA (17.08 @0.5) uses
    uncalibrated probabilities; card FA (5.09 @0.5) uses calibrated — thresholds are not comparable.
12. **Activity v2 size:** CTX log says 94,556 windows / 175 subjects (PAMAP2 pooled, later reverted); served model is
    90,349 / 166.
13. **CTX §3 header** still says "4 open-source benchmark datasets" and maps datasets to v1 states (e.g. MIT-BIH "for
    CARDIAC_ARREST", PPG-DaLiA for "HEMORRHAGIC_SHOCK & HYPOTHERMIA_RISK") — outdated v1 wording; local path shown is a
    Linux path.
14. **TG §7** points to iteration log "§7"; it is §4 of CTX.
15. **WX header** says the legacy LSTM `src/ml/weather_prediction/` is "still present, untouched"; CTX P6 row says the v1
    weather LSTM was removed (directory not present under `src/ml/`).
16. Test totals: CTX §1 "127 tests passing" vs P8 row "128 tests pass".
17. HIFD fusion result (84.6 %) depends on semi-synthetic 60 s stillness padding.

---

### 16. Gaps — not recorded in the repo
- Brier score for any head (only log-loss and ECE).
- AUPRC in final calibrated reports/cards (only in tournament JSON, uncalibrated).
- AUPRC/PR-AUC for external tests in reports (only TJSON for stress/fall externals).
- Inference latency of ONNX/compiled heads per head in serving (only aggregate 5–60 ms / ~60 ms per frame).
- Any on-hardware (real TRIDENT band) evaluation; emulator-vs-device parity results (planned, RESILIENCE §9.1).
- Sensitivity of rule-only states (cardiac arrest, hypoxia, shock, hypothermia) — no positive data.
- CV accuracy metrics (mAP, recall in water), measured FPS on target hardware beyond the 0.3–0.5 s/frame estimate,
  YOLO input `imgsz`, LBPH radius/neighbours/grid (defaults used, values not stated), face-recognition FAR/FRR.
- Weather: CRPS not reported (pinball loss + MAE + coverage only); per-season results; GloFAS skill (external product,
  not evaluated).
- Subject demographics (age/sex) per dataset beyond SisFall young/elderly and MIMIC ICU.
- Fusion risk score calibration (risk is a fixed per-state constant, not a probability).


---

## Appendix D. Write-up formats and filing rules (with sources)

Compiled: 31 Oct 2026. Every rule below names its source URL. Anything I could not confirm from a primary or official source is marked **[unverified]**. Fees were checked on **31 Oct 2026** against the IP India First Schedule PDF (PDF metadata: created 31 Jul 2026).

Source-quality key: **[primary]** = publisher, statute or patent office; **[secondary]** = law firm, library or third party; **[student-shared]** = unofficial copy of an institutional template.

---

### 1. IEEE conference paper (IEEEtran `conference` mode) and IEEE journals

#### 1.1 Template
- LaTeX: `\documentclass[conference]{IEEEtran}`. The CTAN package (v1.8b) includes `bare_conf.tex`. Word templates are linked from the Author Center. [primary]
  - https://ctan.org/pkg/ieeetran (downloaded from https://mirrors.ctan.org/macros/latex/contrib/IEEEtran.zip)
  - https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/
- In conference mode the class turns off `\thanks`, `\IEEEPARstart`, `\IEEEbiography`, `\IEEEpubid` and `\IEEEmembership`. It also centres figure captions and shrinks the spacing after author names. Source: IEEEtran_HOWTO.pdf, inside the CTAN zip. [primary]
- Author block: `\IEEEauthorblockN{Name}` followed by `\IEEEauthorblockA{Dept., Institution, City, Country \\ email}`. For many authors, use `\IEEEauthorrefmark{n}` (see bare_conf.tex). [primary]

#### 1.2 Page limits
- **No IEEE-wide page limit for conferences.** Each conference sets its own limit in its call for papers. 4–6 pages, sometimes with paid extra pages up to 8, is common but **[unverified as a general rule]**. Always follow the specific CFP.

#### 1.3 Section order (IEEE Author Center, conferences)
Title → Author block → Abstract → Index Terms (keywords) → I. Introduction → Methods → Results and Discussion → Conclusion → Acknowledgment (optional) → References.
- https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/structure-your-paper/ [primary]
- The journal Author Center gives the same order, with a first-footnote block after the keywords and Acknowledgments placed **after** References in journals: https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/structure-your-article/ [primary]

#### 1.4 Abstract and index terms
- **One paragraph, at most 250 words.** It must be self-contained: "no abbreviations, footnotes, references, or mathematical equations." State the research, the conclusions, the implications and what is new. [primary, both URLs above]
- **3–5 keywords**, with abbreviations defined. Prefer IEEE Thesaurus terms. [primary]
- Title: be specific. Avoid "new" or "novel", and put no math symbols in the title or abstract. [primary]
- Funding: in journals, funding goes in the **first footnote**, not in the Acknowledgments. For conferences, a funding statement goes in the first footnote. [primary]
- Human-subject or animal work needs an ethics approval or exemption statement in the first footnote. Example opening: "Approval of all ethical and experimental procedures and protocols was granted by…" This applies to TRIDENT if wearable tests use human volunteers. [primary]

#### 1.5 Figures, tables and captions
- File formats: PS, EPS, PDF, PNG, TIFF. **Not** JPEG (except author photos), GIF, BMP or VSD. Office files only if the graphic was drawn in that program. Flatten all layers. [primary] https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/improve-your-graphics/
- Sizes: one column is 3.5 in (88.9 mm). Two columns are 7.16 in. Maximum figure size is 7.16 × 8.8 in. Text inside figures should be about **9–10 pt** at final size, in Helvetica, Times New Roman, Arial, Cambria or Symbol. [primary]
- Figures must read in greyscale. Do not rely on colour alone (avoid red/green pairs) and label lines directly. IEEE rejects papers that use the "Lena" image. [primary]
- Captions: **figure caption below the figure** ("Fig. 1."). **Table caption above the table** ("TABLE I", Roman numerals, title-case). IEEEtran_HOWTO: "IEEE places table captions before the tables." In LaTeX, `\caption` goes after `\includegraphics` and `\label` goes after `\caption`. [primary: IEEEtran_HOWTO.pdf and bare_conf.tex]
- If you use `subfig`, load it with `caption=false`. Otherwise caption.sty overrides IEEE caption style. [primary: bare_conf.tex comments]

#### 1.6 Reference style: IEEE numbered (IEEE Reference Guide v3.28.2025)
Source: https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE_Reference_Guide.pdf. This URL now redirects to a Google Doc: https://docs.google.com/document/d/1j1L96U2NagwWI9MEVDNVKt9pXxRzTH7h3krI3Mb6wZE [primary]

General rules:
- Cite in square brackets, e.g. [1], [2]–[4], or with location, e.g. [3, Fig. 1]. Number references in order of first citation. Do not use ibid. or op. cit.
- Initials come before the surname. List **all authors up to six**. With more than six, give the first author followed by "et al." In running text, use "et al." when there are three or more authors.
- Every reference ends with a period **unless it ends with a URL**. When an entry has both a DOI or access date and a URL, the DOI or access date comes first, then a period, then the URL.

Templates (verbatim "Basic Format" from the guide, plus a TRIDENT-style example):
- **Journal:** `J. K. Author, "Name of paper," Abbrev. Title of Periodical, vol. x, no. x, pp. xxx–xxx, Abbrev. Month, year, doi: xxx.`
  - Guide example: M. M. Chiampi and L. L. Zilberti, "Induction of electric field in human bodies moving near MRI: An efficient BEM computational procedure," *IEEE Trans. Biomed. Eng.*, vol. 58, pp. 2787–2793, Oct. 2011, doi: 10.1109/TBME.2011.2158315.
- **Conference (print proceedings):** `J. K. Author, "Title of paper," in Abbreviated Name of Conf., (location optional), (Month and day(s) if provided) year, pp. xxx–xxx.`
- **Conference with DOI:** `J. K. Author, "Title of paper," in Abbreviated Name of Conf., (location), year, pp. xxx–xxx, doi: xxx.`
  - Guide example: G. Veruggio, "The EURON roboethics roadmap," in *Proc. Humanoids '06: 6th IEEE-RAS Int. Conf. Humanoid Robots*, 2006, pp. 612–617, doi: 10.1109/ICHR.2006.321337.
- **Conference proceedings online:** `J. K. Author, "Title of paper," in Abbreviated Name of Conf., (location), year, pp. xxx–xxx. [Online]. Available: http://www.url.com`
- **Dataset (DOI):** `Author, Date, "Title of Dataset," Source, doi: xxx.`
- **Dataset (website):** `Author, Date, "Title of Dataset," Source. [Online]. Available: http://www.url.com`
- **Software:** `J. K. Author. Title of Software. (Date). Repository or Archive. (version or year). Publisher Name. Accessed: Date. [Type of Medium]. Global Persistent Identifier. Available: site/path/file`
  - Guide example: D. W. Arning *et al.* *Mixed Mode–Mixed Level Circuit Simulator*. (2011). Ngspice. Accessed: Jan. 11, 2019. [Online]. Available: http://ngspice.sourceforge.net
  - IEEE follows the FORCE11 software citation principles. Give the version, repository and a persistent ID, e.g. a Zenodo DOI for a GitHub release.
- **Website:** `First Initial(s) Last Name. "Page Title." Website Title. Accessed: Date. [Online]. Available: URL`
- **Patent:** `J. K. Author, "Title of patent," Country Patent xxx, Abbrev. Month, day, year.`
- Conference-name abbreviations: drop most articles and prepositions, and write ordinals as "1st" not "First". For example, "Proceedings of the 1996 Robotics and Automation Conference" becomes "Proc. 1996 Robot. Automat. Conf."

#### 1.7 Acknowledgment
- Use `\section*{Acknowledgment}`. IEEE uses the American spelling "Acknowledgment", singular, while Computer Society papers use "Acknowledgments". [primary: IEEEtran_HOWTO]
- It is optional and thanks people who do not qualify as authors. [primary]
- IEEE Access also requires any AI-generated content to be **disclosed in the acknowledgments**: https://ieeeaccess.ieee.org/authors/preparing-your-article/ [primary]

#### 1.8 IEEE Xplore and PDF eXpress compliance (common technical rejection causes)
Source: https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/meet-ieee-xplore-requirements/ [primary]
- PDF version 1.4 or later, but **not** Acrobat 9, X or XI output. Must be distilled, **not scanned**.
- **All fonts embedded or subset.**
- No password or security settings, no bookmarks or links, no attachments, no crop or registration marks or timestamps, and not a PDF Package or merged PDF.
- Conferences that don't use PDF eXpress use the IEEE PDF Checker instead.

Other common desk-reject formatting issues **[unverified, general practice]**:
- over the page limit
- changed template margins or font sizes
- page numbers or headers added when the CFP forbids them
- author names left in a double-blind submission
- missing copyright notice in the camera-ready version
- unembedded Type 3 fonts from matplotlib (fix with `pdf.fonttype 42`)

#### 1.9 IEEE journals compared
| Item | IEEE Transactions/Journals (general) | IEEE Access | IEEE Sensors Journal |
|---|---|---|---|
| Abstract | ≤250 words, single paragraph [primary, Author Center] | Not stated on the guideline pages I fetched **[unverified]**. The general IEEE ≤250-word rule likely applies. | Only says "prepared according to the requirements" [primary]. Use ≤250 words. |
| Keywords | 3–5 [primary] | **min 3, max 10** at submission [primary] | Must choose one category from the journal's keyword list [primary] |
| Length | Varies by journal | No hard limit. Strongly recommended **under 20 pages**; longer papers need a pre-inquiry [primary] | **8 pages** double-column for regular papers, 12 for reviews. **$175 per page** mandatory overlength charge beyond 8 [primary] |
| Graphical abstract | Optional in many journals | Any video you submit (≤100 MB) is published as the GA [primary] | **Mandatory** ("now a graphical is mandatory too") [primary] |
| Author bios | Usually required in Transactions (`\IEEEbiography` with photo) | **Required for ALL authors**, placed after the references [primary]. Photo not stated **[unverified]** | Not stated **[unverified]** |
| Template | IEEEtran journal mode | IEEE Access Word (Access-Template-2024.docx) or LaTeX template. Submit source **and** PDF, ≤40 MB [primary] | IEEE double-column template [primary] |
| Fees | Varies | **APC US$2,160** plus taxes [primary] | Open access **US$2,800**; non-OA voluntary $110 per page [primary] |

Sources:
- IEEE Access: https://ieeeaccess.ieee.org/authors/submission-guidelines/ and https://ieeeaccess.ieee.org/authors/preparing-your-article/
- IEEE Sensors Journal: https://ieee-sensors.org/ieee-sensors-journal/for-authors/
- IEEE Access also accepts expanded conference papers only if similarity to the conference version is **below 35%** (preparing-your-article page). [primary]

---

### 2. Springer

#### 2.1 LNCS / CCIS / LNAI proceedings (llncs class)
Sources [primary]:
- Series page: https://link.springer.com/series/558/information-for-authors-and-editors
- Instructions PDF: https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/27852130/data/
- LaTeX template ZIP (llncs.cls **v2.25, 2026/09/03**, includes `splncs04.bst`): https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/27851904/data/
- Word template ZIP: https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/27852136/data/

Rules:
- **Length:** full papers are typically **12–15 (or more) pages**. Short papers are 6–11 pages. Papers under 4 pages may go to the back matter and are not indexed. The conference sets the actual limit.
- **Abstract:** **150–250 words** (samplepaper.tex). No footnotes in the abstract.
- **Keywords:** `\keywords{First keyword \and Second keyword \and Another keyword.}`, placed inside the abstract environment.
- **Authors:** one corresponding author only, and their email is mandatory. Springer strongly recommends emails and **ORCIDs** for all authors; ORCIDs go in superscript next to the names.
- **Headings:** capitalise all words except articles, prepositions and conjunctions. Number 1st- and 2nd-level headings; never number a heading "0". Heading sizes are fixed by the class and listed in Table 1 of the Instructions. The extracted table text was garbled, so the exact point sizes are **[unverified]**: it shows a 10-pt bold 2nd level and a run-in bold lower level, and the 1st level is likely 12 pt bold. Do not override the class.
- **Captions:** table captions go **above** tables and figure captions **below** figures, set in 9 pt. Lettering inside figures must be at least 6 pt.
- No page numbers or running heads; Springer adds them.
- Do not change the template fonts.
- Appendix goes **before** the references.
- **Credits block** (LaTeX `credits` environment) at the end of the paper:
  - Acknowledgments, e.g. "This study was funded by X (grant number X)".
  - **Disclosure of Interests**, which is now mandatory, even if it only says "The authors have no competing interests to declare that are relevant to the content of this article."
- **References:** BibTeX style `splncs04`. Order is alphabetical (preferred) or citation order, with numbers in brackets. Include DOIs. Example: `Author, F., Author, S.: Title of a proceedings paper. In: Editor, F., Editor, S. (eds.) CONFERENCE 2016, LNCS, vol. 9999, pp. 1--13. Springer, Heidelberg (2016). \doi{...}`
- **At final submission:** all source files plus the bib/bbl, a final PDF that matches the source exactly, and the License-to-Publish form signed by hand by the corresponding author.

#### 2.2 Springer Nature journals (sn-jnl template)
Template ZIP (Dec 2024 version): https://cms-resources.apps.public.k8s.springernature.io/springer-cms/rest/v1/content/18782940/data/v12
Info page: https://www.springernature.com/gp/authors/campaigns/latex-author-support
Overleaf: https://www.overleaf.com/latex/templates/springer-nature-latex-template/gsvvftmrppwq [primary]

- **Class options set the reference style:**
  - `sn-basic` (Basic SN/Chemistry)
  - `sn-mathphys-num` (numbered)
  - `sn-mathphys-ay` (author-year)
  - `sn-vancouver-num` / `sn-vancouver-ay`
  - `sn-apa`, `sn-chicago`, `sn-aps`, `sn-nature`
  - add `iicol` for double column, `lineno` for line numbers, `referee` for double spacing
- **Abstract:** the template shows both an unstructured abstract and a structured one (Purpose / Methods / Results / Conclusion). As a guide it says ≤200 words, but the journal's own limit applies.
- **Declarations section** (template list; check which headings your journal requires):
  1. Funding
  2. Conflict of interest / Competing interests
  3. Ethics approval and consent to participate
  4. Consent for publication
  5. Data availability
  6. Materials availability
  7. Code availability
  8. Author contribution
- Back matter macros: `\bmhead{Supplementary information}` and `\bmhead{Acknowledgements}`.

#### 2.3 Journal-specific requirements (fetched 31 Oct 2026) [primary]
| | **Natural Hazards** (11069) | **J. Ambient Intell. Humaniz. Comput. (JAIHC)** (12652) | **Multimedia Tools & Applications (MTAP)** (11042) | **Neural Computing & Applications (NCAA)** (521) |
|---|---|---|---|---|
| Abstract | 150–250 words, unstructured, no undefined abbreviations or unspecified references | 150–250 words | 150–250 words | 150–250 words. May go **up to 450** when needed (e.g. systematic reviews) |
| Keywords | 4–6 | 4–6 | 4–6 | 4–6 |
| Length | Not stated | **12 pages including references**, double-column journal format. Revised or accepted papers up to 14. Surveys 24 at submission and 28 after revision (needs prior EIC approval). Non-compliant papers are **returned**. | Not stated | Not stated |
| Format | Word preferred (10-pt Times), or the SN LaTeX template. **Line numbering required**. Decimal headings, max 3 levels. | **Must use** `\documentclass[iicol,sn-basic]{sn-jnl}`, double column, **author-year** references. No space-saving tricks. | Word or SN LaTeX | Word or SN LaTeX. **Double-blind review:** separate title page, anonymised manuscript, and acknowledgements and funding on the title page only. |
| Citation style | **Author-year** (Thompson 1990) | **Author-year** | **Numbered** [1] | **Numbered** [1] |
| Statements | "Statements and Declarations" heading is **mandatory**, placed **after References**. Covers Funding, Competing Interests and Author Contributions (encouraged). Submissions without it are returned as incomplete. | "Statements and Declarations" required, including Competing Interests | Same as JAIHC | Same as JAIHC |
| Data policy | Type 1 (deposit encouraged) | Data Availability Statement **required** for original research | Data Availability Statement **required** for original research | Data Availability Statement **required** for original research |

- Note: another part of the same pages says to place these declarations in a "Declarations" section **before** the reference list. The guideline pages contradict each other on placement, so follow the specific journal's latest instructions or the SN template. The same pages list further declarations: Ethics approval, Consent, Data, Material and/or Code availability, and Authors' contribution statements.
- All four journals ask for:
  - acknowledgements on the title page
  - funding agency names written in full
  - figure files named Fig1.eps and so on
  - vector art in EPS, halftones in TIFF at ≥300 dpi, combination art ≥600 dpi, line art ≥1200 dpi
  - figure lettering in Helvetica or Arial at 8–12 pt
  - no captions inside image files
  - tables numbered with Arabic numerals
- **LLM policy (SN):** LLMs cannot be authors. Document any LLM use in the Methods section.
- URLs:
  - https://link.springer.com/journal/11069/submission-guidelines
  - https://link.springer.com/journal/12652/submission-guidelines
  - https://link.springer.com/journal/11042/submission-guidelines
  - https://link.springer.com/journal/521/submission-guidelines
- Springer reference examples (author-year style): `Gamelin FX, Baquet G, … (2009) Effect of … Eur J Appl Physiol 105:731–738. https://doi.org/10.1007/s00421-008-0955-8`. Online document: `Cartwright J (2007) Big stars have weather too. IOP Publishing PhysicsWeb. http://… Accessed 26 June 2007`.

---

### 3. VIT final-year capstone project report (B.Tech)

> Changed per coordinator: this section covers VIT, not Anna University. Anna University note (one line): Anna University's B.E. "Project Work" reports follow a centrally issued format (bonafide certificate signed by the HoD and supervisor, etc.). It was not researched further.

#### 3.1 What I could and could not verify
- **No official VIT guideline was publicly findable.** Searches of vit.ac.in, chennai.vit.ac.in and the VIT library returned no capstone or project-report format PDF. VIT circulates the template internally, through VTOP, the school's project coordinator or the guide. **The team must get the current template from the School (SCOPE / SENSE / SELECT, etc.) or from VTOP and treat it as overriding everything below.**
- **Vellore vs Chennai campus:** I found no public evidence that the two campuses use different formats. Both run the same FFCS curriculum and course codes **[unverified]**. Confirm with the Chennai school's project coordinator.

#### 3.2 Course codes [unverified, from a student-uploaded VIT B.Tech CSE curriculum dated June 2024]
Source: https://www.studocu.com/in/document/vellore-institute-of-technology/data-structures-and-algorithms/curriculum-student-btech-bce/97759300 [student-shared]
- **BCSE497J – Project-I**
- **BCSE498J – Project-II / Internship Project** (the final-year "Capstone")
- **BCSE499J – One-Semester Internship Project**
- BCSE399J – Summer Industrial Internship
- ECE programmes are expected to follow the same pattern, BECE497J/498J/499J **[unverified]**.
- Credits could not be read from the source **[unverified]**.

#### 3.3 Front matter order (VIT capstone template as shared by students) [student-shared, unverified]
Primary student copy: Scribd "Capstone Project Report Format", VIT, Power System Engineering, https://www.scribd.com/document/620692430/Capstone-Project-Report-Format
1. Cover / Title page: project title; "Submitted in partial fulfillment of the requirements for the degree of Bachelor of Technology in <programme>"; student name(s) and register number(s); "Under the guidance of <Guide>"; School; VIT logo; month and year.
2. **Declaration** by the candidate(s): states that the work is a record of bonafide work carried out under the guide and has not been submitted elsewhere for any degree or diploma. Signed and dated with place.
3. **Certificate** (bonafide): signed by the Guide and the Programme Chair / HoD. There is usually space for internal and external examiner signatures **[unverified]**.
4. **Acknowledgements**: typically thanks the Chancellor/VPs/VC/Dean, the HoD, the guide, the panel and family.
5. **Executive Summary**: one page, **≤200 words** (per the template description). It replaces the "Abstract".
6. Table of Contents
7. List of Figures
8. List of Tables
9. List of Abbreviations
10. Symbols and Notations

An older VIT School of Mechanical and Building Sciences guideline gives this order: Cover and Title page → Dedication (optional) → Declaration → **Bonafide Certificate** → Certificate by External Guide (for projects done outside VIT) → Acknowledgement → Abstract → Contents. It gives **50–100 pages** for B.Tech. Source: https://www.scribd.com/document/260178524/Project-Report-Format [student-shared, old]

#### 3.4 Chapter structure (VIT capstone template, ABET-style) [student-shared, unverified]
1. **Introduction**: 1.1 Objective, 1.2 Motivation, 1.3 Background
2. **Project Description and Goals**
3. **Technical Specification**
4. **Design Approach and Details**: 4.1 Design Approach / Materials and Methods, 4.2 Codes and Standards, 4.3 Constraints, Alternatives and Tradeoffs
5. **Schedule, Tasks and Milestones** (Gantt chart)
6. **Project Demonstration**
7. **Cost Analysis / Result and Discussion**
8. **Summary** (conclusion and future work)
9. References
10. Appendix (code, datasheets, drawings)

For TRIDENT, the design chapter maps well onto these sections:
- **Codes and Standards:** e.g. IEEE 802.11 / LoRa, IP ratings (IEC 60529) for the band and ROV, and data-protection law.
- **Constraints and tradeoffs:** e.g. battery vs sampling rate, edge vs cloud inference.

#### 3.5 Formatting [unverified for VIT]
I found no VIT-official values. Common Indian university defaults:
- A4 paper
- Times New Roman 12 pt body, 1.5 line spacing
- Chapter titles 14–16 pt bold; section headings 12 pt bold (the old VIT Mech guide gives 14 pt bold for paragraph headings and 12 pt bold for section and subsection headings)
- Margins roughly left 1.5 in (binding), others 1 in
- Front matter numbered in lower-case Roman (i, ii, …) and the main text in Arabic numerals from Chapter 1
- Figures numbered chapter-wise ("Fig. 3.2") with the caption below; tables numbered "Table 3.1" with the caption above
- Hard-bound or spiral binding as the school directs

**Get the School's template before formatting.**

#### 3.6 Reference style
VIT capstone templates typically use **IEEE numbered** style **[unverified]**. Use §1.6.

#### 3.7 Reviews and evaluation [unverified]
- VIT capstone courses are commonly assessed through **Review I** (problem, literature, objectives, design), **Review II** (implementation progress, partial results) and **Review III / Final** (full demo, report, viva by an internal and external panel).
- The rubric and weights are published on VTOP or by the school. No public source was found.
- **Plagiarism:** no VIT-specific similarity limit was found publicly.
  - VIT is a UGC-recognised Deemed University. The UGC (Promotion of Academic Integrity and Prevention of Plagiarism) Regulations, 2018 set bands (≤10% Level 0) for **Masters/PhD theses**, not explicitly for B.Tech reports. Secondary summary: https://casrai.org/guides/ugc-india-anti-plagiarism-regulations-2018
  - Schools commonly require a Turnitin report, often under about 10–15%; **[unverified]**, so confirm with your guide.

---

### 4. Indian patent filing

Statute and rules texts were all fetched from ipindia.gov.in on 31 Oct 2026 [primary]:
- Act sections: `https://ipindia.gov.in/acts/patent-act-1970/section-<n>`
- Rules: `https://ipindia.gov.in/acts/patent-rules-2003/rule-<n>`

#### 4.1 Forms (what each is) [primary]
List: https://ipindia.gov.in/patents-before-you-apply-forms-official-fees. IP India roadmap PDF: https://ipindia.gov.in/storage/uploads/media/21cd7739-77c1-4520-87f7-4c05ba2d1309.pdf
| Form | Purpose | Notes |
|---|---|---|
| **Form 1** | Application for grant of patent (s.7, 54, 135; r.20(1)) | Lists applicants, inventors, title, priority. |
| **Form 2** | Provisional or complete specification (s.10, r.13) | Structure in §4.2 below. |
| **Form 3** | Statement and undertaking under s.8 (foreign filings of the same invention) | File with the application or within 6 months **[6-month period per r.12, not re-fetched; unverified]**. Must be updated when foreign filings change. |
| **Form 5** | Declaration as to inventorship | With the complete specification, or within 1 month of it (extendable via Form 4). Required when a complete follows a provisional (r.13(6)). |
| **Form 9** | Request for early publication (s.11A(2), r.24A) | Mandatory together with Form 18A unless the application is already published (r.24C(3)). |
| **Form 18** | Request for examination (s.11B, r.24B) | **Must be filed within 31 months** of priority/filing (see §4.4). |
| **Form 18A** | Expedited examination (r.24C) | **E-filing only.** Eligible grounds in §4.4. |
| **Form 26** | Authorisation of a patent agent | No fee. |
| **Form 28** | Claim small entity / startup / educational institution status | No fee. Evidence: MSME registration (small entity), DPIIT recognition (startup), or "any document as evidence of eligibility" (educational institution). Natural persons do **not** need Form 28; they get the reduced fee column automatically. |
| **Form 31** | Grace period claim under s.31 (r.29A, new in 2024) | Needs documentary evidence or an affidavit for the specific s.31 ground. |
| **Form 4** | Extension of time / condonation of delay | Rule 138 extension up to 6 months (2024 amendment). |

#### 4.2 Form 2 specification: exact headings and order
**Official Form 2 cover-page boxes** (image PDF at https://ipindia.gov.in/storage/uploads/section-contents/bf118f84-1c70-4d5e-b479-025c1b1875f3.pdf; page https://ipindia.gov.in/acts/patent-rules-2003/form-2) [primary]:
1. TITLE OF THE INVENTION
2. APPLICANT(S): (a) Name, (b) Nationality, (c) Address
3. PREAMBLE TO THE DESCRIPTION
   - Provisional: "The following specification describes the invention."
   - Complete: "The following specification particularly describes the invention and the manner in which it is to be performed."
4. DESCRIPTION (starts on the next page)
5. CLAIMS. Not applicable to a provisional. "Claims should start with the preamble 'I/We claim' on separate page."
6. DATE AND SIGNATURE, at the end of the last page of the specification
7. ABSTRACT OF THE INVENTION, given with the complete specification on a separate page

Form 2 notes:
- Strike out the column that does not apply.
- Give the applicant's family name first.
- Give the full postal address with PIN.
- Sign as applicant or as a registered patent agent.

**Description sub-headings (conventional order).** The Act requires the content but not these exact headings, so this order is Indian practice **[convention; not in rule text]**:
1. Title (the abstract must start with the title, and the title should normally be **≤15 words**; r.13(7)(a))
2. Field of the Invention
3. Background of the Invention / Description of Related Art (prior art and its drawbacks)
4. Objects of the Invention ("The principal object of the present invention is to…")
5. Summary of the Invention
6. Brief Description of the Drawings ("Fig. 1 illustrates…")
7. Detailed Description of the Invention, with reference numerals matching the drawings
8. Best Method / Working Example: s.10(4)(b) requires disclosure of the **best method of performing the invention known to the applicant**
9. Claims: "I/We claim:" on a new page
10. Date and signature
11. Abstract: separate page, ≤150 words

**Statutory content of a complete specification (s.10(4)):**
- (a) fully and particularly describe the invention, its operation or use, and the method of performing it
- (b) disclose the best method known
- (c) end with claims defining the scope
- (d) be accompanied by an abstract
- Claims must relate to a single invention or a single inventive concept, be clear and succinct, and be "fairly based on the matter disclosed" (s.10(5)).
- A complete filed after a provisional may claim developments of the provisional (s.10(7)).
- Source: https://ipindia.gov.in/acts/patent-act-1970/section-10

**Abstract rules (r.13(7))** [primary] https://ipindia.gov.in/acts/patent-rules-2003/rule-13
- Starts with the title. Title normally **≤15 words**.
- Concise summary covering the technical field, the technical advancement over existing knowledge, and the principal use (no speculative use).
- **≤150 words.**
- Name the figure to accompany the abstract. Put reference signs after the features.
- Draft it as a search tool.

**Drawings (r.15)** [primary] https://ipindia.gov.in/acts/patent-rules-2003/rule-15
- **A4** sheets. Margins at least **4 cm top and left, 3 cm bottom and right**.
- Scale large enough to be clear. **No dimensions marked.**
- Number the sheets. Each sheet carries:
  - **top-left:** applicant's name
  - **top-right:** "Sheet x of y"
  - **bottom-right:** signature of the applicant or agent
- **No descriptive matter on drawings except flow diagrams.** Flowcharts may carry text; system block diagrams should use reference numerals.
- No drawings inside the specification text itself.
- Reference signs from the drawings go in parentheses in the claims (r.13(4)).

#### 4.3 Official fees, e-filing (First Schedule, checked 31 Oct 2026) [primary]
Fee PDF: https://ipindia.gov.in/storage/uploads/section-contents/35968e17-dfa4-4295-a7e4-41420601dd65.pdf (linked from https://ipindia.gov.in/acts/patent-rules-2003/fees). Rule 7: https://ipindia.gov.in/acts/patent-rules-2003/rule-7

Column A = **natural person, startup, small entity or educational institution**. Column B = others (alone or jointly with a Column A applicant). Physical filing costs about 10% more.

| Entry | Item | Form | Col A (INR) | Col B (INR) |
|---|---|---|---|---|
| 1 | Application (up to 30 pages and 10 claims) | 1 | **1,600** | 8,000 |
| 1(i) | Each sheet beyond 30 | 1 | 160 | 800 |
| 1(ii) | Each claim beyond 10 | 1 | 320 | 1,600 |
| 2 | Complete after provisional (up to 30 pages and 10 claims) | 2 | **No fee** (excess pages and claims charged as above) | No fee |
| 3 | Statement and undertaking | 3 | No fee | No fee |
| 5 | Inventorship declaration | 5 | No fee | No fee |
| 13 | Early publication | 9 | **2,500** | 12,500 |
| 28(i) | Request for examination | 18 | **4,000** | 20,000 |
| 28(ii) | Examination for PCT national phase under r.20(4)(ii) | 18 | 5,600 | 28,000 |
| 29 | Expedited examination (e-filing only) | 18A | **8,000** | 60,000 |
| 30 | Convert Form 18 to 18A | 18A | 4,000 | 40,000 |
| 4(v) | Extension under r.138 (per month) | 4 | 10,000 | 50,000 |
| 4(iii) | Extension for RFE under r.24B(6) (per month) | 4 | 1,000 | 4,000 |
| 47 | Patent agent authorisation | 26 | No fee | — |
| 55 | Small entity / startup / educational institution status | 28 | No fee | No fee |
| 59 | Grace period | 31 | **500** | 2,500 |
| 18 | Renewal, years 3–6 (each year) | — | 800 | 4,000 |
| 18 | Renewal, years 7–10 | — | 2,400 | 12,000 |
| 18 | Renewal, years 11–15 | — | 4,800 | 24,000 |
| 18 | Renewal, years 16–20 | — | 8,000 | 40,000 |
| 50 | PCT transmittal fee (international application) | — | 3,500 | 16,000 (Col A figure is the physical-filing column; e-filing Col A not legible) **[partially unverified]** |
| 51 | Transmittal via ePCT | — | No fee | — |

Refunds and rebates:
- If the application is withdrawn before the First Examination Report (FER), **90%** of the Form 18 or 18A fee is refunded (Form 29, r.7(4A)).
- A **10% rebate** applies to renewal fees paid in advance for at least 4 years electronically (r.80, 2024): https://www.khuranaandkhurana.com/2024/07/03/an-overview-of-patent-amendment-rules-2024 [secondary]

**Typical student-team minimum (natural persons, e-filing, ≤30 pages and ≤10 claims), excluding agent fees:**
- Provisional: ₹1,600.
- Complete: ₹0.
- Form 18: ₹4,000.
- Optional Form 9 plus Form 18A: ₹2,500 + ₹8,000.

**If VIT is the applicant:** it would also be Col A, as an educational institution with Form 28. VIT's IPR policy may require assignment to VIT **[unverified; check the VIT IPR/Patent Cell]**.

#### 4.4 Timelines [primary unless noted]
- **Provisional → complete: 12 months** from filing, otherwise deemed abandoned (s.9(1)). Not extendable under s.9 **[r.138 extension does not apply to this period; per the general understanding of Rule 138's exclusions, unverified]**. https://ipindia.gov.in/acts/patent-act-1970/section-9
- **Publication: 18 months** from the priority or filing date (s.11A, r.24). Early publication on Form 9 normally follows within about 1 month of the request (r.24A) **[r.24A text not retrieved, unverified]**.
- **Request for examination (Form 18): 31 months** from the priority or filing date, whichever is earlier. This is r.24B(1)(i) as amended by the Patents (Amendment) Rules 2024, notified 15 Mar 2024. The old **48 months** still applies to applications filed **before** the 2024 Rules commenced (r.24B(1)(vi)). If you miss it, the application is treated as withdrawn.
  - Rule: https://ipindia.gov.in/acts/patent-rules-2003/rule-24b
  - IP India roadmap: "No examination if Form 18/18A not filed within 31 months."
- **Expedited examination (Form 18A, r.24C).** Eligible applicants:
  - startup
  - small entity
  - **natural person(s) where the applicant, or at least one joint applicant, is female**
  - government departments and government-owned or financed institutions
  - India chosen as ISA/IPEA in a PCT application
  - notified sectors
  - PPH-type arrangements
  
  An ordinary male student applicant is **not** eligible unless a woman is a co-applicant. A private deemed university is eligible only if it is government-financed. https://ipindia.gov.in/acts/patent-rules-2003/rule-24c
- **FER reply:** 6 months, extendable by 3 months on Form 4 (IP India roadmap PDF).
- **Term:** 20 years from filing.
- **Extensions:** r.138 allows up to 6 months on Form 4 (2024 amendment). [secondary: K&K overview above]

#### 4.5 Section 3(k) and computer-related inventions (CRI)
- **s.3(k):** "a mathematical or business method or a computer programme *per se* or algorithms" are not inventions. Related exclusions:
  - s.3(m): mental acts and methods of playing games
  - s.3(n): presentation of information
  - https://ipindia.gov.in/acts/patent-act-1970/section-3 [primary]
- **CRI Guidelines 2025** were released by the CGPDTM on **29 Jul 2025** and replace the 2017 Guidelines.
  - Official PDF title: "Guidelines for Examination of Computer Related Inventions (CRIs) – 2025", with Annexure I (examples) and Annexure II (case law). The ipindia.gov.in PDF link I tried returned 404, so the points below come from secondary commentary: https://conventuslaw.com/report/india-a-detailed-analysis-of-indias-new-cri-guidelines-2025/ and https://www.aippi.org/news/decoding-cri-guidelines-2025/
  - Patentability turns on **technical effect / technical contribution**, read from the claim as a whole (substance over form). Recognised technical effects include:
    - higher speed
    - reduced memory access time
    - better control of robotic arms or external devices and physical processes
    - improved signal transmission or reception
    - network security
    - real-time monitoring and control of devices
  - Flow-chart tests are given for the s.3(k) categories.
  - Novelty uses the "Seven Stambhas" approach and inventive step a five-step test, both from *Ericsson v. Lava*.
  - **Method and system claims are both allowable** for patentable CRIs.
  - **Computer-readable-medium and computer-program-product claims remain non-patentable** (per Lex Orbis commentary).
  - **AI/ML:** the disclosure must be detailed enough for a skilled person to reproduce the invention (following *Caleb Suresh Motupalli*, Madras HC). This in practice means describing the model architecture, input features, training procedure and data characteristics **[the exact list is unverified]**.
  - On the old "novel hardware" requirement, the commentary cites the Delhi High Court in *Raytheon*: "The requirement of novel hardware is a higher standard which lacks any basis in law" **[confirm treatment in the official text]**.
- **2017 Guidelines** dropped the earlier "novel hardware" test and adopted a "substance of the claim" approach **[from general knowledge; 2017 PDF not re-fetched this session, unverified]**.
- **TRIDENT drafting implication:** claim the **system** (wearable band with sensors and radio, ROV with camera, server/console) and the **method** tied to physical effects. Examples of such effects:
  - triggering a rescue dispatch from sensor-fused distress detection
  - controlling ROV navigation from vision output
  - reducing radio transmissions or power on the band
  
  Avoid claims to the ML model, the forecasting algorithm or the console UI on their own.

#### 4.6 Novelty, prior disclosure and grace exceptions (critical)
- India applies **absolute novelty**. Anything published anywhere before the filing (priority) date can anticipate the claims, including:
  - a GitHub repository
  - an arXiv preprint or conference paper
  - a demo video, poster, hackathon pitch, project expo or viva open to the public
- **s.29(2):** prior publication does not anticipate only if the matter was **obtained from the inventor and published without consent**, and the inventor filed as soon as reasonably practicable after learning of it. https://ipindia.gov.in/acts/patent-act-1970/section-29
- **s.31 grace (12 months, claimed via Form 31):** covers only:
  - (a) display at an exhibition **notified by the Central Government in the Gazette**
  - (b) publication resulting from such a display
  - (c) unauthorised use during the exhibition
  - (d) a paper **read before a learned society or published in its transactions** by the inventor
  
  https://ipindia.gov.in/acts/patent-act-1970/section-31
  - Form 31 must be filed with evidence: https://ipindia.gov.in/storage/uploads/docs-operator/eb68c3bc-10c1-417b-81fa-a08913762464.pdf
  - Whether an IEEE or Springer conference counts as a "learned society" is a contested question **[unverified; do not rely on it]**.
  - **A public GitHub push, arXiv preprint, college expo, SIH demo or journal paper is NOT safely covered.**
- **Rule of thumb: file at least a provisional in India BEFORE any public disclosure** (paper submission, open-source repo, public demo). Keep repos private until filing. Draft the provisional broadly enough to cover what the paper will disclose.
- **Foreign filing permission (s.39):** an Indian resident may not file abroad first, including a US provisional or a PCT at a non-Indian receiving office, unless one of these applies:
  - an Indian application was filed **at least 6 weeks earlier** and no secrecy direction was issued, or
  - a Foreign Filing Licence was obtained (Form 25).
  
  https://ipindia.gov.in/acts/patent-act-1970/section-39 [primary]

#### 4.7 Invention disclosure form (IDF): typical contents
Khurana & Khurana (https://www.khuranaandkhurana.com/intellectual-property-rights/patents) describes its process as:
1. disclosure meetings with inventors
2. patent search and mapping
3. drafting provisional or complete specifications for IN/US/EP/PCT
4. multi-level screening and proofreading
5. filing and deadline docketing

**No downloadable K&K IDF or questionnaire was found publicly**; ask the firm or VIT's IPR cell. K&K is empanelled with institutions such as IIT (BHU), whose IDF fields are [primary institutional form]:
- inventor contact details
- whether it is a product, process or composition
- title
- public description and how it works
- components
- **novelty and a patent search report**
- **present stage of development**
- sponsorship or funding
- choice of agent
- signatures of all inventors

Source: https://www.iitbhu.ac.in/contents/institute/dean/dord/doc/patent_cell_form.pdf

Recommended IDF contents for TRIDENT (synthesis):
1. Title
2. All inventors, with % contribution and the specific contribution of each (inventorship is not the same as authorship)
3. Applicant (students vs VIT) and any funding or sponsor
4. Field and problem solved
5. Known prior art (patents, papers, products) and how TRIDENT differs
6. Detailed description with block diagrams:
   - band hardware (sensors, MCU, radio)
   - ROV and CV pipeline
   - backend/console
   - forecasting
   - data flows
7. What is new and non-obvious, listed as candidate claim features
8. Alternatives and variants (other sensors, radios, models), to broaden the claims
9. Experimental results (accuracy, latency, range, battery)
10. **All past and planned disclosures, with dates**: papers, GitHub, demos, competitions
11. Development stage (TRL) and commercial plans
12. Inventor signatures and dates

#### 4.8 Claim-drafting conventions (Indian practice; general guidance) [convention; secondary]
- Claims begin on a new page under "I/We claim:" (Form 2 note), or "We claim:".
- **Independent claims:** typically one **system** claim and one **method** claim. Example: "1. A flood-rescue system (100) comprising: a wearable device (110) comprising…; a remotely operated vehicle (120) comprising…; and a server (130) configured to…". Reference numerals go in parentheses (r.13(4)).
- **Transition word:** "comprising" is open-ended; "consisting of" is closed. Use "comprising".
- **Dependent claims:** "2. The system as claimed in claim 1, wherein…". Use them to add fallback features (specific sensor fusion, thresholds, LoRa link, CV model type, etc.).
- **Fees:** the Col A fee covers 10 claims; each extra claim costs ₹320. Each claim should be one sentence.
- **Functional / means-plus-function language:** India has no statutory means-plus-function provision like US 35 U.S.C. §112(f). Purely functional claims ("means for detecting distress") risk clarity and sufficiency objections (s.10(4), 10(5)). In the US they are construed narrowly under §112(f). Recite structural features (sensor, processor configured to…, transceiver). **[practice guidance, not a quoted rule]**
- Avoid claims to software alone or a "computer readable medium" (CRI 2025). Tie every step to hardware or a technical effect.
- **Unity:** one inventive concept per application (s.10(5)). The ROV and the wearable may need separate applications, or a system claim linking them, if their inventive features are independent **[strategy]**.

---

### 5. Foreign patents

#### 5.1 USPTO provisional application [primary]
Source: https://www.uspto.gov/patents/basics/apply/provisional-application
- Requirements:
  - written description meeting **35 U.S.C. §112(a)**
  - drawings as needed
  - cover sheet (**PTO/SB/16**: provisional identification, all inventors and residences, title, agent and docket, correspondence address, any US Government interest)
  - fee under 37 CFR 1.16(d)
- **No claims and no oath or declaration required.**
- Not examined. Pendency is **12 months, not extendable**, and the provisional is abandoned automatically after that.
- The non-provisional must be filed within 12 months and must share at least one inventor. Its claims get the provisional's date only where the provisional supports them, so make the disclosure "as complete as possible".
- "Patent pending" may be used.
- **Fees** (schedule effective 19 Jan 2025, page revised 14 Aug 2026; checked 31 Oct 2026), https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule:

| Fee | Standard | Small | Micro |
|---|---|---|---|
| Provisional filing fee (1005) | $325 | $130 | $65 |
| Utility basic filing (1011) | $350 | $140 | $70 |
| Search (1111) | $770 | $308 | $154 |
| Examination (1311) | $880 | $352 | $176 |

  Micro-entity eligibility (gross income limit, ≤4 prior applications) was not checked **[unverified]**.
- **Section 39 India:** a resident must file in India at least 6 weeks earlier, or obtain a foreign filing licence, before filing a US provisional.

#### 5.2 US non-provisional: specification order, 37 CFR 1.77(b) [primary]
Source: MPEP 608.01(a), https://www.uspto.gov/web/offices/pac/mpep/s608.html
1. Title of the invention
2. Cross-reference to related applications
3. Statement regarding federally sponsored research or development
4. Names of the parties to a joint research agreement
5. Incorporation by reference of material submitted on read-only optical disc, as a text file or XML file (sequence listings, computer program listings, tables)
6. Statement regarding prior disclosures by the inventor or a joint inventor
7. Background of the invention
8. Brief summary of the invention
9. Brief description of the several views of the drawing
10. Detailed description of the invention
11. Claim or claims, starting on a separate sheet (1.52(b)(3))
12. Abstract of the disclosure, on a separate sheet, **preferably ≤150 words** (1.72(b))
13. Sequence listing, if required

Format rules:
- Headings in **UPPERCASE, without underlining or bold** (1.77(c)).
- Paper A4 or Letter, one side only.
- Margins: top ≥2.0 cm, left ≥2.5 cm, right and bottom ≥2.0 cm.
- Line spacing 1.5 or double (1.52).

#### 5.3 US subject-matter eligibility (§101, Alice/Mayo) [primary]
Source: MPEP 2106 (R-10.2019; parts R-07.2022), https://www.uspto.gov/web/offices/pac/mpep/s2106.html
- **Step 1:** is the claim a process, machine, manufacture or composition? Software, data or signals *per se* fail.
- **Step 2A Prong One:** does the claim recite a judicial exception? Abstract ideas fall into three groups:
  - **mathematical concepts**
  - **certain methods of organising human activity**
  - **mental processes**
- **Step 2A Prong Two:** is the exception integrated into a **practical application**? Examples: an improvement to computer functionality or another technology (*Enfish*, *McRO*), a particular machine, or a transformation.
- **Step 2B:** do the additional elements amount to significantly more (an inventive concept)? An unconventional technical solution to a technical problem can qualify (*Amdocs*).
- **For TRIDENT:** frame the claims around concrete improvements to sensing, communication or control, such as:
  - lower false-alarm rate in distress detection from multi-sensor fusion on a constrained wearable
  - ROV control based on detection
  
  Avoid "collect data, analyse, display" claim shapes, which are the classic §101 failure.
- **US grace period:** 35 U.S.C. §102(b)(1) gives a 1-year grace for the inventor's own disclosures **[general knowledge; statute not fetched this session]**. India's s.31 is far narrower, and Europe (EPC) has essentially none. A US grace period does not protect Indian or European rights.

#### 5.4 PCT and the Paris Convention
- **Paris priority:** a PCT or foreign application can claim the first application's date if filed **within 12 months** of it. https://www.wipo.int/pct/en/faqs/faqs.html [primary]
- **International publication:** 18 months from priority. The ISR is published with it. [primary]
- **National phase:** for most offices, **30 months** from priority [primary, WIPO FAQ]. **India allows 31 months** (r.20(4)(ii), referenced in Form 18A: "without waiting for the expiry of 31 months as specified in rule 20(4)(ii)"). [primary, IP India Form 18A] Other offices' 31-month limits (e.g. EPO) are **[unverified here]**.
- **PCT fee reduction:** **90%** off certain PCT fees, including the international filing fee, for **natural persons from qualifying countries** filing in their own right. All applicants must qualify. The WIPO FAQ wording was summarised; India's eligibility under the per-capita GDP criteria is **[unverified]**. Check the PCT Applicant's Guide fee tables. [primary, WIPO FAQ]
- **India as an office:** the Indian Patent Office is an ISA/IPEA (WIPO FAQ lists India among the ISAs). IPO is a receiving office: transmittal fee entries 50–51 in the First Schedule, with no fee via ePCT.
- **Typical route:**
  1. Indian provisional (month 0)
  2. Indian complete plus PCT (month 12)
  3. national phases at month 30/31

---

### 6. Brief: hackathon/grant proposals and technical posters

#### 6.1 Smart India Hackathon (SIH) idea submission (structure from college-circulated templates) [secondary]
Sources:
- https://www.lets-code.co.in/blogs/sih-2025-complete-guide-ppt-template/
- https://www.slideshare.net/slideshow/innovative-smart-india-hackathon-2026-idea-submission-template-for-software-hardware-solutions/289256695
- Official portal: https://www.sih.gov.in **[current-year template not fetched; unverified]**

Slide order:
1. **Title:** Problem Statement ID, PS title, Theme, PS Category (Software/Hardware), Team ID, Team Name
2. **Idea / Proposed Solution:** explanation, how it addresses the problem, innovation and uniqueness
3. **Technical Approach:** technologies (languages, frameworks, hardware), methodology with flowcharts, images or a working prototype
4. **Feasibility and Viability:** feasibility analysis, risks, mitigation
5. **Impact and Benefits:** target audience, social, economic and environmental benefits
6. **Research and References**

Format rules seen in these templates:
- Usually **≤6 slides including the title**; some editions use 8.
- Submit as **PDF**.
- TRL is not part of the SIH template as seen.

#### 6.2 Grant or innovation proposal (generic; e.g. DST/BIRAC/MeitY-style or institutional seed grants) [unverified, general]
Typical sections:
- Title and PI/team
- Problem statement and need, with data (e.g. Chennai flood statistics)
- Objectives
- State of the art and gap
- Proposed methodology / work plan
- Deliverables and **TRL now → target**
- Timeline (Gantt) and milestones
- Budget with justification (equipment, consumables, travel, manpower)
- Team expertise
- Expected outcomes (patents, papers, prototype)
- Risks
- Ethics and data handling
- Sustainability / commercialisation

**TRL scale (NASA/EU H2020 convention):**
- TRL 1: basic principles
- TRL 3: proof of concept
- TRL 4: lab validation
- TRL 5: validation in a relevant environment
- TRL 6: demo in a relevant environment
- TRL 7: demo in the operational environment
- TRL 9: proven in operation

Reference: EU H2020 Work Programme General Annex G **[definition not fetched this session; unverified wording]**. A final-year TRIDENT prototype tested in a pool or lake is realistically about **TRL 4–5**.

#### 6.3 Technical poster [unverified, general convention]
- Size: A0 or A1 portrait as specified by the event (IEEE conference poster sessions set their own size).
- Layout: title banner (title, authors, affiliations, logos) → Problem/Motivation → System architecture (one big diagram) → Method (band, ROV CV, console, forecasting) → Results (2–3 charts, metrics table) → Conclusion/Future work → References (3–6, IEEE style) → QR code to the repo or paper.
- Text should be readable from about 1.5–2 m: title ≥72 pt, headings ≥36 pt, body ≥24 pt. Keep it to roughly 300–800 words, in 2–3 columns, with consistent colours and greyscale-safe charts (same accessibility rules as §1.5).
- **Do not show unpublished, unfiled inventive details on a public poster before the patent filing (§4.6).**

---

### Key caveats
1. **Disclose only after filing.** India requires absolute novelty, and s.31 grace is narrow (Gazette-notified exhibitions and learned-society papers only). A public GitHub repo, arXiv preprint, conference submission that becomes public, SIH/expo demo or poster made before filing can destroy patentability in India and Europe. File at least an Indian provisional first, then disclose.
2. **s.39 foreign filing.** No first filing abroad (US provisional, PCT outside the Indian RO) without an Indian filing at least 6 weeks earlier or a foreign filing licence.
3. **Form 18 within 31 months** (not 48) for any new application.
4. **CRI.** Software, ML models, algorithms and computer-readable-medium claims alone are excluded. Claim system and method with hardware and a technical effect.
5. **VIT format specifics are unverified.** Get the School's current template from VTOP or the project coordinator.
6. **Re-check fees** before paying. The First Schedule changes, and the PDF seen is dated 31 Jul 2026.
