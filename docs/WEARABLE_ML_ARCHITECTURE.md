# TRIDENT Wearable ML — Implementation Architecture (v2, Hybrid)

> **Status (2026-10-31).** Implemented through P8. §10 and §12 describe the system as built; the other sections keep the design record with its decisions. Results are in [reports/](reports/), and how to retrain is in [TRAINING_GUIDE.md](TRAINING_GUIDE.md).
>
> **As built vs. this design record.** Where the sections below differ from the code, the code and the
> generated reports are authoritative:
> - **Validation:** every head uses 5-fold StratifiedGroupKFold by subject (not leave-one-subject-out).
> - **Candidates and tuning:** 7 candidates (logistic regression, XGBoost, LightGBM, Extra-Trees, MLP, 1D-CNN, MiniRocket). Optuna budgets are 6–20 trials per candidate with time caps (`config/tournament.yaml`), not 40.
> - **Calibration:** Platt scaling for binary heads and temperature scaling for activity, not isotonic regression.
> - **Artifacts:** `model_<member>.onnx` + `calibration.json` + compiled forests + `card.md`. The Extra-Trees ONNX files are 6.7–75 MB, and serving uses the compiled numpy forests.
> - **IMU rate:** 50 Hz (decision 1), not 100 Hz.
> - **Fusion thresholds:**
>   - HR trust uses the registry threshold (0.59) in every rule, and `shock.hr_trust_p` in `fusion.yaml` is unused.
>   - CARDIAC_ARREST uses rhythm p ≥ 0.8, and stress fusion uses 0.85.
>   - Hypoxia's fast-fall rule is a drop of more than 2 percentage points from the 10 s maximum.
>   - The CONCUSSIVE severe-drop rule is a barometric rise of at least 0.12 hPa (about 1 m).
> - **§9 "Priority" column:** this is the state id. The severity order is in `config/fusion.yaml`.


**Status:** Approved 2026-10-30 — P0, P1, P7 in progress
**Date:** 2026-10-30
**Supersedes:** the single 8-class synthetic classifier described in `WEARABLE_ML_SUBPROJECT_CONTEXT.md` §5–8

> **Implementation decisions taken after approval**
> 1. **IMU at 50 Hz, not 100 Hz.** This matches HIFD, the wrist fall test set. The emulator downsamples
>    faster sources (SisFall 200 Hz) with anti-aliasing and keeps slower ones (E4 32 Hz, UP-Fall ~20 Hz) as they are.
> 2. **EDA travels in µS.** The firmware converts the Grove GSR ADC reading to skin conductance with Seeed's
>    formula. An open-circuit calibration value is stored in NVS (`calibrate_gsr_open` command).
>    This puts device EDA in the same unit as WESAD and PPG-DaLiA.
> 3. **`imu_fall_detected` is NaN in emulated frames.** It's a firmware heuristic, used only as a fusion
>    backstop, never as a model feature.
> 4. **Loaders live in a single module** (`data/loaders.py`) rather than one file per dataset.
> 5. **Measured cross-dataset domain gap.** The median wrist fall peak is 13.3 g in HIFD vs 3.3 g in
>    UP-Fall (20 Hz sampling flattens impacts). P2 fall features must be robust to this, e.g. by using
>    relative and shape features rather than only absolute peaks.
>
> **P2/P3 decisions**
> 6. **Training == serving by construction.** Head tables are produced by replaying each emulated recording
>    frame by frame through the online `FeatureEngine`. A test pushes frames through
>    JSON → `parse_payload` → engine and asserts bit-identical features for all six feature sets.
> 7. **Personal calibration uses only the past.** Baselines (BPM, EDA, skin temperature) come from the first
>    80 frames (2 min) of a session and use only frames already seen, offline and online alike.
> 8. **Wrist-PPG beat quality measured on PPG-DaLiA** with an offset-robust method (the chest and wrist
>    clocks differ per subject): at rest the beat-count ratio is 1.00 (IQR 0.96–1.03) and the median
>    |RR error| is 58 ms. Rhythm-head augmentation draws σ_RR from 30–90 ms, 1–6 % missed beats and 0–4 %
>    spurious beats, with 2 augmented copies per MIT-BIH record. Records 201/202 are grouped as one patient.
>    The ventricular-ectopy fraction output was dropped: the device cannot observe beat morphology.
> 9. **Fall labels:** only windows containing the impact frame of a fall trial are positive (peak |acc|;
>    UP-Fall restricted to frames tagged as falling). Other windows of fall trials are excluded as
>    ambiguous; every window of an ADL trial is negative.
> 10. **False-alarm replay needs an accelerometer-only variant**, because the PPG-DaLiA and WESAD wrists have
>     no gyroscope. The fall winner's family and hyper-parameters are retrained on gyro-free features
>     (`fall_acc_only`) and replayed over about 60 h of real daily life.
> 11. **Activity classes:** rest = sitting, driving, lunch, working; light = table soccer;
>     active = stairs, cycling, walking. Windows need ≥ 80 % label purity.
>     **HR-trust label:** firmware-style BPM within 10 bpm of ECG HR.
> 12. **Tournament rules:**
>     - Outer validation is 5-fold StratifiedGroupKFold by subject, with 3-fold inner CV for Optuna.
>     - Tuning starts from the screening configuration.
>     - **The logreg baseline advances if it ranks in the Stage 1 top two.** Contenders must beat it,
>       and it isn't excluded just for being simple.
>     - Stage 3 winner: the subject-bootstrap CI of the macro-F1 difference must exclude 0; otherwise the
>       smaller/faster finalist wins.
>
> **P3 v2 decisions (2026-10-30)**
> 13. **More data per head.**
>     - HR-trust adds WESAD, with a chest-ECG reference from our R-peak detector (validated on PPG-DaLiA:
>       sensitivity ≥ 98.7 %, precision ≈ 99.5 %, median HR error < 0.5 bpm).
>     - Rhythm adds AFDB and LTAFDB, sub-sampled with strides of 20 and 60 frames and 1 PPG-noise copy each.
>     - Activity adds PAMAP2 and Capture-24.
>     - Fall adds daily-life negatives from PPG-DaLiA, WESAD, PAMAP2 and Capture-24.
> 14. **Stress-Predict is an external stress test, not training data.** Pooling it lowered WESAD
>     out-of-fold macro-F1 in a smoke run (0.834 vs 0.885): its protocol labels inter-task relaxation as
>     non-stress and counts hyperventilation and interview as stress, a different target definition.
> 15. **The fall head is accelerometer-only.** Most daily-life sources have no gyroscope. Mixing falls that
>     have gyro data with negatives that lack it would teach "gyro missing ⇒ no fall". In v1 the gyro added
>     only ~0.004 macro-F1. The firmware still sends gyro data (fusion and future use).
> 16. **Capture-24 split for the fall head** (stable SHA-256 of the participant id):
>     - One third of participants are held out entirely to measure false alarms on unseen people.
>     - The other two thirds enter CV as negatives: a window every 30 s, plus every window containing a
>       motion spike (≥ 1.8 g or ≤ 0.4 g), capped at 1,500 per person (label-free hard-negative mining).
> 17. **Activity labels follow Walmsley 2020** (behaviour-based):
>     - rest = sleep / sedentary (incl. driving)
>     - light = standing and household chores
>     - active = walking, stairs, sport (MVPA)
>
>     PAMAP2 and PPG-DaLiA activities are mapped to the same three classes. Capture-24 windows are taken
>     every 2 min.
> 18. **New candidates:**
>     - Extra-Trees (bootstrap capped at 60k rows per tree).
>     - MiniRocket (own numpy implementation, sequence features + tabular features → logistic regression;
>       needs windows ≥ 8 frames, so it is not entered for fall).
>     - A Stage 3 soft-vote of the two tuned finalists, adopted only if its subject-bootstrap CI against
>       the single winner excludes 0.
> 19. **Like-for-like with v1:** every head also reports the selected model's out-of-fold scores per
>     source dataset. The v1 results are archived in `data/processed/wearable/tournament/v1/`.

---

## 1. Goal and design principles

Build a real-time pipeline that turns live wearable telemetry into one of the 8 disaster-trauma
states, a risk score and an explanation, and feeds `calculate_priority()` and Auto-ROV dispatch.

| Principle | What it means in practice |
|---|---|
| **Real data trains models; rules cover what has no data** | Tier 1 heads are trained and validated only on real recordings. States with no public data are produced by an explicit, versioned rule engine. |
| **Train exactly what we serve** | Raw datasets are converted into the *same* 1.5 s telemetry frames the ESP32 sends. One feature module is used for both training and serving. |
| **Honest evaluation** | Every number comes from subjects or records the model never saw. Synthetic data is used only to test the fusion rules, never as training labels. |
| **Everything traceable** | Each prediction carries model versions, its basis (`ml`, `rule` or `ml+rule`) and the evidence behind it. |
| **Portable artifacts** | Models are exported to ONNX, never pickle. This matters because training runs on Python 3.13 / numpy 2.x locally while production runs on Python 3.10 / numpy 1.26 in Docker. |

---

## 2. System overview

```
┌──────────────────────────── EDGE: ESP32 wearable (firmware v2) ────────────────────────────┐
│ MPU6050 100 Hz │ MAX30102 100 Hz (beats, RR, real SpO2) │ GSR 20 Hz │ MAX30205 1 Hz       │
│ BMP388 25 Hz   │ water-contact 2 Hz │ battery 0.2 Hz │ NEO-6M GPS 1 Hz                     │
│        └── sensor task (core 1) → 1.5 s interval aggregates (double buffer) ──┐            │
│ on-device fall flag + buzzer (offline safety net)                              │            │
│        network task (core 0): JSON frame v2 → HTTP POST, offline queue + seq ◄─┘            │
└───────────────────────────────────────────────┬────────────────────────────────────────────┘
                                                │ every 1.5 s
┌───────────────────────────────── SERVER: Flask backend ────────────────────────────────────┐
│ POST /api/telemetry/wearable                                                               │
│   1. schema validation (v1 legacy | v2) → normalised Frame (missing fields = NaN)          │
│   2. per-device ring buffer (last 120 s = 80 frames)                                       │
│   3. shared feature module  ◄──────────── same code as offline training ─────────┐         │
│   4. Tier 1 heads (onnxruntime)  stress │ fall │ activity+HR-trust │ rhythm       │         │
│   5. temporal smoothing (EMA + hysteresis)                                        │         │
│   6. Tier 2 fusion state machine → 8 states + risk + evidence + basis             │         │
│   7. persist frame + prediction → calculate_priority() → Auto-ROV / dashboard     │         │
│ GET /api/ml/status  (versions, mode, latency, drift summary)                      │         │
└───────────────────────────────────────────────────────────────────────────────────┼─────────┘
                                                                                    │
┌──────────────────────────────── OFFLINE: training pipeline (local) ───────────────┴────────┐
│ raw datasets → compact (lossless .npz) → device emulator (→ 1.5 s frames) → features       │
│ → per-head datasets → tournament (5 candidates, nested CV) → winner per head               │
│ → calibrate + threshold → ONNX export + model card → models/wearable/registry.json         │
│ → MLflow (local) + auto-generated docs/reports/MODEL_TOURNAMENT_RESULTS.md                          │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Telemetry frame contract (schema v2)

This schema is the single source of truth. It is used by the firmware, the server, the emulator
and the tests, and it is defined once in `src/ml/wearable/schema.py` plus a JSON Schema file.

```json
{
  "schema": 2, "device_id": "TRIDENT-W01", "fw": "2.0.0", "seq": 18234, "uptime_ms": 27351000,
  "imu":   {"acc_max_g": 1.12, "acc_min_g": 0.91, "acc_mean_g": 1.01, "acc_std_g": 0.04,
            "gyro_max_dps": 35.2, "gyro_mean_dps": 8.1, "tilt_deg": 12.5, "n": 75,
            "fall_detected": false},
  "ppg":   {"finger_on": true, "bpm": 78.0, "rr_ms": [772, 768, 781], "spo2": 97.0,
            "spo2_valid": true, "perfusion": 0.84},
  "eda":   {"us": 2.4, "slope_us_s": 0.003, "baseline_us": 2.2, "raw": 1840, "norm": 0.12},
  "temp":  {"skin_c": 33.4},
  "baro":  {"hpa": 1009.82, "dmax_hpa": 0.04},
  "water": {"wet": false},
  "power": {"batt_v": 3.92},
  "gps":   {"lat": 13.0827, "lng": 80.2707, "sats": 7, "hdop": 1.2, "breached": false}
}
```

**Backward compatibility.** v1 payloads from the current firmware are still accepted. They are
mapped onto the v2 frame, and every field v1 doesn't provide becomes NaN. Rules that depend on a
missing field are switched off, and the dashboard shows which inputs are unavailable.

---

## 4. Firmware v2

### 4.1 Hardware additions

All new sensors share the existing I²C bus on GPIO 21/22. None of their addresses conflict.

| Part | Address / pin | Purpose | Unlocks |
|---|---|---|---|
| MPU6050 (existing) | 0x68 | Raised to 100 Hz; computes interval aggregates | Fall head, immobility |
| MAX30102 (existing) | 0x57 | FIFO at 100 Hz; beat detection → RR list; **real SpO₂** (Maxim algorithm over a 4 s buffer, updated every 1 s); perfusion and finger-contact detection | Rhythm head, stress HRV, hypoxia, arrest |
| **MAX30205** | 0x48 | Clinical-grade skin temperature (±0.1 °C) | Hypothermia, shock (peripheral cooling) |
| **BMP388** (BMP280 also works) | 0x77 | Barometric pressure at 25 Hz | Fall height (0.5–2 m drop ≈ 0.06–0.24 hPa); **submersion** (+~98 hPa per metre of water) |
| **Water-contact electrodes** | GPIO 33 (ADC1 / touch) | Immersion flag | Drowning / aspiration context |
| **Battery divider** (100k/100k) | GPIO 35 (ADC1) | Battery voltage | Separates "device dying" from "patient deteriorating" |
| GSR (existing) | GPIO 34 (ADC1) | Unchanged pin; sampled at 20 Hz; raw value plus normalised value | Stress head |

New analog inputs use **ADC1 only**, because ADC2 cannot be read while Wi-Fi is active on the ESP32.

### 4.2 Software structure

- **Two tasks.** A sensor task on core 1 samples on fixed timers. A network task on core 0 builds
  the JSON and sends it. Today a blocking HTTP POST plus `delay(20)` in a single loop leaves gaps
  in IMU sampling, and a fall impact lasts about 100 ms. Splitting the tasks fixes that.
- **Interval aggregation.** Every 1.5 s the sensor task closes the window (max/min/mean/std,
  RR list and so on) and swaps it into a double buffer protected by a mutex.
- **Offline resilience.** Frames carry a `seq` number. Up to 120 frames are queued while Wi-Fi is
  down and flushed in order when it returns.
- **Edge safety net.** The on-device fall detection and buzzer still work without any network.
- **Module layout** (PlatformIO, `platformio.ini` with pinned libraries):
  `config.h`, `imu.*`, `ppg.*`, `eda.*`, `skintemp.*`, `baro.*`, `water.*`, `power.*`, `gps.*`,
  `telemetry.*`, `remote_cmd.*`, `webui.*`, `main.cpp`.
- **Payload size.** About 650 bytes per frame (ArduinoJson).
- The existing remote commands (`reset_fall`, `calibrate_gsr`, `set_geofence`) and the local web
  UI are kept.
- **Verification.** Compile with PlatformIO locally (toolchain is about 1 GB). Flashing and wiring
  are done by the user using the wiring table in `src/firmware/README.md`.

---

## 5. Data layer

### 5.1 Dataset registry (`src/ml/wearable/config/datasets.yaml` + `data/manifest.json`)

| Dataset | Used for | Subjects | Sensor location | Signals used | Notes |
|---|---|---|---|---|---|
| WESAD | Stress head | 15 | wrist (E4) | EDA 4 Hz, BVP 64 Hz, ACC 32 Hz, TEMP 4 Hz; protocol labels | Labels: baseline / stress / amusement |
| PPG-DaLiA | Activity + HR-trust head; false-alarm replay | 15 | wrist (E4) | BVP, ACC, EDA, TEMP; ECG heart rate and R-peaks as ground truth | About 36 h of real daily life |
| UP-Fall | Fall head | 17 | wrist IMU (one of 5 locations) | wrist ACC + gyro | Per-sample activity tags |
| HIFD | Fall head (held-out test) | 21 | wrist | ACC, gyro, quaternion, PPG; 50 Hz | Gravity was removed in the source; reconstructed from the quaternion |
| SisFall | Fall head (extra training data, ablation) | 38 (23 young + 15 elderly) | waist | ADXL345 + ITG3200, 200 Hz | Placement differs; whether it helps is tested, not assumed |
| MIT-BIH | Rhythm head | 47 patients (48 records) | chest ECG | R-peak / beat annotations → RR series; rhythm labels | ECG RR is made PPG-like using noise calibrated on PPG-DaLiA |

Each dataset's entry records its source URL, license, SHA-256 hash and subject list. Raw and
processed data are git-ignored.

### 5.2 Lossless compaction (`compact.py`)

- One `.npz` per subject, holding only the channels the emulator needs. Values are kept at their
  original precision, so compaction is lossless. For example, SisFall integer counts stay int16.
- A verification step checks row counts, value checksums and subject/trial counts against the
  manifest **before** any raw data is deleted.
- Expected size: about 72 MB (PPG-DaLiA, done), about 100 MB (WESAD), about 120 MB (SisFall),
  about 30 MB (UP-Fall), about 15 MB (HIFD).
- Deletion policy:
  - SisFall raw text is deleted after verification. The compaction is lossless and the original
    host is offline, so the `.npz` copy becomes the canonical copy.
  - The WESAD and PPG-DaLiA zips are kept until the pipeline is validated. Deleting them later is
    optional, because they can be downloaded again from UCI/Sciebo.

### 5.3 Device emulator (`emulator.py`)

The emulator converts any raw recording into the v2 frame stream the server would receive.

| v2 field | How it is derived from raw data |
|---|---|
| `imu.*` | Resample to 100 Hz, convert units to g and °/s, cut into 1.5 s windows, then compute max/min/mean/std and tilt against gravity |
| `ppg.rr_ms`, `bpm` | Detect peaks on BVP (or use ECG R-peaks), then apply the firmware's own beat logic: valid interval 270–2000 ms, EMA 0.9/0.1 |
| `eda.*` | Normalise per subject against a calibration baseline (first 2 minutes), mirroring `calibrate_gsr` |
| `temp.skin_c` | E4 wrist temperature, where the dataset has it |
| Fields the dataset doesn't contain | NaN |

Unit tests use synthetic signals with known answers. For example, a 1.2 Hz pulse wave must give
72 bpm and RR ≈ 833 ms.

---

## 6. Feature layer (`features/frame_features.py`)

The input is a ring buffer of frames. The same function runs offline on emulated streams and
online in the server. Each head declares which frames (look-back window) and which features it uses.

| Head | Look-back | Features |
|---|---|---|
| Stress | 60 s (40 frames) | EDA level, slope and skin-conductance-response count/amplitude (subject-normalised); HR mean; HRV (RMSSD, SDNN, pNN50, LF/HF proxy); skin-temperature slope; movement intensity |
| Fall | 6 s (4 frames) | Peak acceleration, free-fall minimum, peak-minus-trough, gyroscope peak, tilt change before vs after, stillness after impact, pressure change (NaN in datasets) |
| Activity + HR-trust | 30 s (20 frames) | Acceleration mean/std/percentiles, gyroscope energy, cadence proxy, BPM agreement between beats, RR outlier fraction, perfusion |
| Rhythm | 60 s of RR intervals | RR coefficient of variation, RMSSD, pNN50, Poincaré SD1/SD2, sample entropy, turning-point ratio, ectopic-beat fraction |

The 1D-CNN candidate receives the **raw frame sequence** (time × channels) instead of these
hand-made features. That gives deep learning a fair comparison against the hand-engineered
features.

---

## 7. Tier 1 heads (trained on real data)

| Head | Output | Labels | Validation scheme | Primary metric |
|---|---|---|---|---|
| **Stress** | P(stress) | stress vs non-stress (baseline + amusement) | Leave-one-subject-out (15 folds) | Macro-F1, balanced accuracy |
| **Fall** | P(fall), impact severity | fall vs non-fall; near-falls counted as hard negatives | GroupKFold by subject on UP-Fall (+SisFall); **cross-dataset test on HIFD** | F1, sensitivity at ≤ 1 false alarm per 8 h (measured on PPG-DaLiA daily life) |
| **Activity + HR-trust** | activity intensity {rest, light, moderate-vigorous}; P(BPM reliable) | PPG-DaLiA activity protocol; reliable = within 10 bpm of ECG heart rate | Leave-one-subject-out (15 folds) | Macro-F1; AUROC for HR-trust |
| **Rhythm** | P(irregular rhythm), ventricular-ectopy fraction | MIT-BIH rhythm and beat annotations | GroupKFold by patient (records 201/202 grouped together) | AUROC, F1 for irregular rhythm |

The heads are deliberately small and independent. Each one can be retrained and versioned on its own.

---

## 8. Tournament protocol (run once per head)

"Choosing a single model" means **one winning algorithm per head**. Each head's task and data
differ, so they may pick different winners.

**Candidates**

| # | Candidate | Input |
|---|---|---|
| 0 | Logistic regression | Features — reference baseline that every contender must beat |
| 1 | XGBoost | Features |
| 2 | LightGBM | Features |
| 3 | Deep MLP (BatchNorm, Dropout) | Features |
| 4 | 1D Temporal CNN | Raw frame sequence |

**Stages.** These replace the earlier 10 → 35 → 100 % data split, which made small stages
unrepresentative and dominated by synthetic subjects.

1. **Screening.** All candidates run with default hyperparameters on 100 % of the data under the
   outer cross-validation. The top 2 contenders advance.
2. **Semifinal.** Each advancing contender gets Optuna tuning with the same budget (40 trials).
   Tuning uses an inner group CV inside each training fold (nested CV, so there is no leakage),
   and the outer CV gives the unbiased score.
3. **Final.**
   - Compare the two contenders with a paired per-fold comparison and 95 % bootstrap confidence
     intervals.
   - If the CIs overlap, the smaller and faster model wins.
   - Train the winner on all data.
   - Calibrate its probabilities with isotonic regression on out-of-fold predictions.
   - Choose the decision threshold from the out-of-fold predictions. Example: fall sensitivity
     ≥ 0.95.
   - Export the model.

**What gets recorded**

- Per-fold metrics, out-of-fold predictions and confusion matrices.
- Calibration error (ECE) and log-loss.
- Inference latency (p50 / p95) and model size.
- All runs go to MLflow (`mlruns/`, local).
- `docs/reports/MODEL_TOURNAMENT_RESULTS.md` is auto-generated, covering all stages and all heads.

**Reproducibility.** Fixed seeds, deterministic data order and a config hash stored with every run.

---

## 9. Tier 2 fusion engine (`serving/fusion.py`)

The fusion engine is a deterministic state machine that runs per device. Each state has an
**enter** condition, a **dwell** time it must hold for, and an **exit** hysteresis. When more
than one state is true, the most severe one wins.
All thresholds live in `config/fusion.yaml` and are versioned with a reference for each.

| Priority | State | Basis | Core logic (simplified) |
|---|---|---|---|
| — | SENSOR_FAULT (overlay) | rule | Finger contact lost while moving, or battery low → suppress cardiac rules and flag the reading |
| 7 | CARDIAC_ARREST | ml+rule | Contact confirmed, no beats ≥ 10 s, immobile; **or** rhythm head = ventricular with BPM > 180 or < 30 |
| 3 | ASPIRATION_HYPOXIA | rule | Valid SpO₂ < 90 % for ≥ 15 s, or falling faster than 2 %/10 s; escalated when submerged (pressure +5 hPa and wet) |
| 4 | HEMORRHAGIC_SHOCK | ml+rule | HR > 120 at **rest** (activity head) and rising, plus skin temperature falling, plus high EDA (ATLS class II–IV pattern) |
| 5 | CONCUSSIVE_STASIS | ml+rule | Fall head event (fusion operating point P ≥ 0.6, `head_thresholds` in `fusion.yaml`), then immobility ≥ 30 s (escalated if impact > 6 g or drop > 1 m) |
| 6 | CRUSH_ENTRAPMENT | ml+rule | GPS movement ≈ 0 and HR ≥ 20 bpm above the personal baseline, plus **either** immobile ≥ 120 s starting within 10 min of a detected impact **or** immobile ≥ 300 s (fallback). Stress head not used (P5) |
| 2 | HYPOTHERMIA_RISK | rule | Skin temperature < 32 °C and falling, plus HR < 60 or wet/immersed |
| 1 | ELEVATED_STRESS | ml | Stress head P > 0.85 for ≥ 120 s while activity is rest or light. **Advisory** (`alert_level`), never critical (P5) |
| 0 | STABLE | — | Otherwise |

**Output contract.** This extends today's fields, so the backend and dashboard keep working:

```json
{"ml_health_state": "CONCUSSIVE_STASIS", "ml_state_id": 5, "ml_risk_score": 0.86,
 "basis": "ml+rule", "evidence": ["fall p=0.97 @ 7.4 g", "immobile 41 s", "HR 96 trusted"],
 "heads": {"stress": 0.31, "fall": 0.97, "activity": "rest", "hr_trust": 0.92, "rhythm": 0.04},
 "unavailable_inputs": [], "model_versions": {"fall": "1.0.0", "...": "..."}, "ml_mode": "hybrid"}
```

**How the fusion engine is validated**

1. **Scenario tests.** Synthetic trajectories are used only here. Example: a fall followed by 40 s
   of immobility must give CONCUSSIVE_STASIS within 45 s, and must not give it at 20 s.
2. **Real-data replay.** Run the full pipeline over all PPG-DaLiA and WESAD streams (about 40 h of
   real, healthy life). This measures **false alarms per hour for every critical state**, with a
   target of ≤ 1 per 8 h. This is the real-data check on specificity.

**P5 decisions (2026-10-30, `docs/reports/WEARABLE_FUSION_REPLAY.md`)**

20. **Replay through the serving path.** `serving/runtime.py` runs registry heads at their training
    stride on the online `FeatureEngine`, holds the last output, and marks a head unavailable when its
    window lacks the inputs it was trained on (e.g. no PPG on Capture-24). Streaming and batched replay
    are tested to agree. Replay covers PPG-DaLiA, WESAD, PAMAP2, Stress-Predict and 1,403 h of held-out
    Capture-24, plus HIFD falls padded with 60 s of their final frame (semi-synthetic stillness).
21. **Missing flags are false.** A NaN device flag (`water_wet`, contact, SpO₂ valid, firmware fall)
    counted as true (`bool(nan)`), so every wearer looked wet: 118 → 2 hypothermia alarms after the fix.
22. **CRUSH_ENTRAPMENT needs an impact or a long stillness, and HR, not the stress head.** The spec rule
    gave 14.3 false alarms / 8 h on Stress-Predict; the chosen rule gives 0.51 there and 0 elsewhere.
23. **Fall operating point for fusion: 0.6** (registry keeps P4's 0.72 as the Tier-1 point). Through
    fusion, 84.6 % of HIFD falls reach CONCUSSIVE_STASIS (0.72: 61.5 %) for 1.20 vs 0.74 false alarms
    / 8 h on held-out Capture-24.
24. **Stress is advisory.** It does not transfer (Stress-Predict 0.52), so it is excluded from critical
    rules and its state has `alert_level: advisory`, p 0.85, 120 s dwell.
25. **Compiled forests for serving.** onnxruntime 1.22 needs ~280 s to build the HR-trust Extra-Trees
    kernel (1.9 M nodes; the .ort format does not help). Tree members are also stored as numpy arrays
    (`serving/forest.py`), derived from the ONNX and parity-checked against it (≤ 3e-7, 0 flips):
    all heads load in 0.5 s. ONNX stays the canonical artefact.

---

## 10. Serving integration (as built)

The P0 plan here (a `WearableHealthPredictor` wrapper inside the old Flask `main.py`) was superseded
by the P6 platform. As built:

- **Runtime** (`src/ml/wearable/serving/runtime.py`):
  - `load_heads()` reads `models/wearable/registry.json`.
  - Tree members load from the compiled numpy forests (`serving/forest.py`, parity-checked against the ONNX); the other members load through onnxruntime.
  - Loading all five heads takes about 0.5 s; one frame through all heads plus fusion takes about 5–60 ms of CPU.
  - Heads run at their training stride, and their last output is held between runs.
  - A head whose inputs are missing from the window reports `None` (unavailable).
- **Ingest** (`src/backend/app/services/telemetry.py`):
  - one `DeviceRuntime` per (device, boot)
  - per-device lock, frames processed in `seq` order
  - ML runs outside the database write transaction
  - frames go to `telemetry_frames`, state transitions to `device_states`
  - a critical state opens an alert, linked to the device's verified SOS
- **Missing models:** the API keeps running. Devices show `UNKNOWN`, and `/readyz` reports `wearable_ml: false`.
- **Triage:** a linked wearable in a critical state adds 30 points with the reason `wearable: <STATE>`; an advisory state adds 5. Extreme-case auto-reallocation also requires the fusion state (see [RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md) §2).
- **Console:** state chips with alert level and evidence, Tier-1 head probabilities, and live vitals charts. The models are summarised on the analytics "AI predictions" tab (`GET /api/v1/analytics/models`).

---

## 11. MLOps

| Concern | Approach |
|---|---|
| Environments | `requirements-ml.txt` for local training (py3.13); `requirements-prod.txt` for serving (py3.10 in Docker). The only artifact format shared between them is ONNX. |
| Data versioning | `data/manifest.json` (hashes) + a processed-data hash = hash(manifest, emulator version, config). The pipeline skips work when the hash is unchanged. |
| Pipeline entrypoint | `python -m src.ml.wearable.pipeline {compact,frames,features,tournament,final,export,replay,all}` |
| Experiment tracking | MLflow file store `mlruns/` (git-ignored) |
| Model registry | `models/wearable/registry.json` plus, for each head and version, `model.onnx`, `card.md`, `metrics.json` and `thresholds.json`. These are committed; each model is a few MB at most. |
| Model cards | Data, metrics with confidence intervals, intended use, limitations, subgroup results (e.g. SisFall young vs elderly) |
| Tests (pytest, `tests/ml/`) | Schema v1/v2, emulator correctness, **feature parity offline vs online**, fusion scenarios, golden predictions from the exported models, latency budget, backend endpoint integration |
| Monitoring | Prediction log, per-device feature drift against the training reference (PSI) in `/api/ml/status`, and a shadow-mode flag so a new model version can run log-only before being promoted |
| CI | GitHub Actions (lint + tests) is added when git is connected; nothing is pushed before then |
| Security | Remove the committed Kaggle token from the docs (the user should revoke it); pickle data is read through a restricted loader; no pickle model artifacts |

---

## 12. Repository layout (as built)

```
src/ml/wearable/
  config/        datasets.yaml, tournament.yaml, fusion.yaml (versioned rule parameters)
  data/          archive readers, compaction, loaders (incl. Capture-24, PAMAP2, AFDB/LTAFDB, MIMIC PERform AF), ECG R-peaks, manifest
  emulator.py    raw recordings -> 1.5 s schema-2 device frames
  schema.py      the frame contract shared with firmware and server
  features/      online FeatureEngine (training == serving) and feature sets
  heads/         per-head window tables (build.py)
  models/        tournament candidates (logreg, XGBoost, LightGBM, Extra-Trees, MLP, 1D-CNN, MiniRocket)
  tournament/    run.py (3 stages + soft vote), metrics, report
  final/         train.py (refit, ONNX export + parity, calibration, thresholds, model cards, registry), export.py, report.py
  serving/       runtime.py, fusion.py, forest.py, calibration.py, replay.py, external_rhythm.py
  pipeline.py    CLI (compact, manifest, frames, report, heads, tournament, final, replay)
models/wearable/ registry.json + <head>/<version>/ (ONNX, compiled forests, calibration, metrics, golden.npz, card.md)
tests/ml/        schema, emulator, features, candidates, fusion, runtime, P3 v2, weather, MIMIC AF, vision
docs/reports/    generated reports (data, tournament, final models, fusion replay, rhythm external test)
```

---

## 13. Delivery phases

Each phase ends with a checkpoint where the user reviews and approves.

| # | Phase | Output | Checkpoint |
|---|---|---|---|
| P0 | Cleanup & scaffolding | Legacy code removed, token scrubbed, package skeleton, configs, requirements | Tree review |
| P1 | Data | Manifest, lossless compaction (+ verification), loaders, emulator + tests | Data summary report |
| P2 | Features & head datasets | Per-head frame/feature tables, label distributions, parity tests | Dataset report |
| P3 | Tournament | 4 heads × 5 candidates × 3 stages; `MODEL_TOURNAMENT_RESULTS.md` | Pick / confirm winners |
| P4 | Final models | Calibrated, thresholded, ONNX-exported winners + model cards + registry | Model cards |
| P5 | Fusion | State machine, scenario tests, real-data false-alarm replay | Replay report |
| P6 | Serving | Backend integration, DB, status endpoint, dashboard, integration tests | Local run demo |
| P7 | Firmware v2 | PlatformIO project, modules, wiring table, compiled build | Build log + wiring |
| P8 | Docs | README, training guide, context memory & iteration log | Final review → git |

---

## 14. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| GSR sensor domain shift (E4 µS vs Grove ADC) | Stress head is less accurate on the real device | Subject-normalised EDA features only; calibration routine; HRV features carry part of the signal; documented in the model card |
| PPG RR vs ECG RR (rhythm head trained on ECG) | False "irregular" flags | Noise augmentation calibrated from PPG-DaLiA (BVP-derived vs ECG RR); fusion requires the HR-trust head to agree |
| Fall data comes from young adults simulating falls in the lab | Real falls differ | Cross-dataset HIFD test; elderly ADLs from SisFall as hard negatives; firmware fall flag kept as a backstop |
| HIFD has gravity removed | Wrong magnitudes if used naively | Gravity reconstructed from the quaternion; unit test against the HIFD paper's statistics |
| No real data for 4 states | Those states can't be ML-validated | Explicit `basis: rule`, sourced thresholds, scenario tests, false-alarm replay; upgrade path once data exists |
| Class imbalance (falls, arrhythmia) | Biased models | Class weights, thresholds chosen on out-of-fold predictions, PR-AUC reported |
| Python 3.13 (train) vs 3.10 (prod) | Artifacts won't load in production | ONNX only; a golden test runs the exported model through onnxruntime |
| 8 GB RAM | Out-of-memory during preparation | One subject at a time; frame tables are small (< 200 MB) |
| Render free tier (512 MB) | Memory pressure | onnxruntime adds about 50 MB; heads total < 10 MB |
| New sensors not yet wired | v2 fields arrive empty | Every rule checks its inputs; v1 frames keep working; dashboard shows unavailable inputs |
