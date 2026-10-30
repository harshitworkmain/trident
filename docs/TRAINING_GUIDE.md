# TRIDENT model training guide

This guide covers rebuilding every model TRIDENT serves, from raw datasets to the registries the
server loads:
- the **wearable** Tier-1 heads, with their fusion replay
- the **weather** forecaster

It also covers what **computer vision** needs, since it has no training step of its own. For the
design behind the models, see [WEARABLE_ML_ARCHITECTURE.md](WEARABLE_ML_ARCHITECTURE.md) and
[WEATHER_MODEL.md](WEATHER_MODEL.md).

You only need this guide to change or reproduce models. The repository already contains the exported
models (`models/wearable/registry.json`, `models/weather/registry.json`), and the server runs without
retraining.

## 1. Environment

| Need | Notes |
|---|---|
| Python 3.11+ | `pip install -r requirements.txt` (the full development set: serving + training + CV + tools) |
| CPU and RAM | Everything runs on CPU. 8 GB of RAM is enough because the pipeline streams partitioned data. Don't run two heavy steps at once. |
| Disk | About 10 GB for the zipped datasets plus about 6 GB of processed frames and head tables. Archives are read in place: never fully unzip them. |
| Time on 3 cores | Data steps: about 1–2 h for all datasets. Tournament: about 4–5 h for all heads. Final export: about 30 min. Replay: about 30 min. Weather training: about 35–70 min. |

## 2. Datasets

Put each dataset at the path listed in `src/ml/wearable/config/datasets.yaml`. Most are zips under
`data/raw/wearable_ml_datasets/_zips/`. Download URLs, DOIs and licences are recorded in
[WEARABLE_ML_SUBPROJECT_CONTEXT.md](WEARABLE_ML_SUBPROJECT_CONTEXT.md) §3.

| Dataset | Used for | Location |
|---|---|---|
| WESAD | stress (CV), HR-trust, fall negatives | `_zips/wesad.zip` |
| PPG-DaLiA | activity, HR-trust, fall negatives | `_zips/ppg_dalia.zip` |
| MIT-BIH Arrhythmia, AFDB, LTAFDB | rhythm | `_zips/mitdb.zip`, `afdb.zip`, `ltafdb.zip` |
| UP-Fall, SisFall | fall (CV) | folders `UP_Fall_sensors`, `SisFall_data` |
| HIFD | fall (external test) | folder `HR_IMU_falldetection_dataset-master` |
| PAMAP2 | activity (external test), fall negatives | `_zips/pamap2.zip` |
| Capture-24 | activity, fall hard negatives, held-out daily-life false-alarm replay | `_zips/capture24.zip` |
| Stress-Predict | stress (external test) | `_zips/stress_predict.zip` |
| MIMIC PERform AF | rhythm on real fingertip PPG (external test only) | `_zips/mimic_perform_af_wfdb.zip`, `mimic_perform_non_af_wfdb.zip` |

Weather history is downloaded automatically from the Open-Meteo archive and cached under
`data/raw/weather/` (see §5).

## 3. Wearable pipeline

All steps go through one command line:
`python -m src.ml.wearable.pipeline <step> [targets...]`. Each step reads the previous step's output, so
run them in order. Targets limit a step to some datasets or heads.

| Step | Command | Output |
|---|---|---|
| 1. Compact | `pipeline compact [datasets]` | Lossless per-subject `.npz` under `data/interim/wearable/compact/` |
| 2. Manifest | `pipeline manifest` | Source hashes in `data/manifest/` (reproducibility) |
| 3. Frames | `pipeline frames [datasets]` | Emulated 1.5 s device frames (`data/processed/wearable/frames/`); Capture-24 and LTAFDB are partitioned per recording |
| 4. Report | `pipeline report` | [reports/WEARABLE_DATA_REPORT.md](reports/WEARABLE_DATA_REPORT.md) |
| 5. Heads | `pipeline heads [stress fall activity hr_trust rhythm]` | Window feature tables + sequences (`data/processed/wearable/heads/`) |
| 6. Tournament | `pipeline tournament [heads]` | A winner per head (`data/processed/wearable/tournament/`), MLflow runs in `mlruns/`, [reports/MODEL_TOURNAMENT_RESULTS.md](reports/MODEL_TOURNAMENT_RESULTS.md) |
| 7. Final | `pipeline final [heads]` | Refit on all CV data; ONNX export with a parity check; compiled forests for tree members; calibration and thresholds; golden rows; model cards; `models/wearable/registry.json`; [reports/WEARABLE_FINAL_MODELS.md](reports/WEARABLE_FINAL_MODELS.md) |
| 8. Replay | `pipeline replay [datasets]` | The full serving path (heads + fusion) over real recordings; false alarms per 8 h; [reports/WEARABLE_FUSION_REPLAY.md](reports/WEARABLE_FUSION_REPLAY.md) |
| External test | `python -m src.ml.wearable.serving.external_rhythm` | Rhythm head on MIMIC PERform AF, [reports/WEARABLE_RHYTHM_PPG_AF_TEST.md](reports/WEARABLE_RHYTHM_PPG_AF_TEST.md) |

**Tournament protocol.** Folds are grouped by subject (5 outer, 3 inner), with nested Optuna tuning.
Candidates are logistic regression (baseline), XGBoost, LightGBM, Extra-Trees, MLP, 1D-CNN and
MiniRocket. A subject bootstrap decides between the finalists, and a soft vote of the top two is
adopted only if it wins significantly. Budgets live in `src/ml/wearable/config/tournament.yaml`.

**Promotion rules** (enforced by `final`):
- ONNX must match the Python model (max |Δp| < 0.02, argmax flips < 0.2 %).
- A compiled forest must match its ONNX within 1e-5 with no flips.
- The fall threshold must keep out-of-fold daily-life false alarms ≤ 1 per 8 h. Fusion uses its own operating point (`head_thresholds` in `src/ml/wearable/config/fusion.yaml`), chosen on the replay.

**Changing fusion rules.** Edit `config/fusion.yaml` (thresholds are versioned with references), run
`python -m pytest tests/ml/test_fusion.py`, and re-run `pipeline replay`. Rule changes must be
justified by replay numbers. The replay and the decisions taken so far are in
[WEARABLE_ML_ARCHITECTURE.md](WEARABLE_ML_ARCHITECTURE.md) §9.

**Compiled forests for existing models.** If you re-export by hand, refresh them without refitting:

```bash
python -c "from src.ml.wearable.final.train import compile_forests; compile_forests()"
```

## 4. Adding data from the real band

The heads were trained on public datasets passed through the device emulator. When TRIDENT hardware
data exists (see [RESILIENCE_AND_FUTURE_WORK.md](RESILIENCE_AND_FUTURE_WORK.md) §9.1):

1. Export frames from `GET /api/v1/devices/{id}/frames`, or directly from the `telemetry_frames` table.
2. Write a loader in `src/ml/wearable/data/loaders.py` that yields `Recording`s with labels, and register it in `config/datasets.yaml`.
3. Run `frames` → `heads` → `tournament` → `final` → `replay`. Keep new subjects grouped as their own folds so the scores stay subject-independent.

## 5. Weather model

```bash
python -m src.ml.weather.data            # refresh the cached Open-Meteo history (data/raw/weather/)
python -m src.ml.weather.train           # full: backtests, model choice, calibration, export (~35-70 min)
python -m src.ml.weather.train --quick   # smoke run -> models/weather/_quick/
```

This produces:
- `models/weather/<version>/`: LightGBM boosters, the GRU as ONNX, the spec, calibration, hazards, metrics and `card.md`
- an updated `models/weather/registry.json`

Method, backtest results and limitations are in [WEATHER_MODEL.md](WEATHER_MODEL.md).

## 6. Computer vision

There is no training step in the repository. The vision worker uses the pretrained YOLOv8n weights
(`src/cv/yolov8_model/yolov8n.pt`) and an LBPH face model (`src/cv/face_recognition/trainer.yml`).
To enrol faces, which should be limited to responders who have given consent, and to calibrate
distance estimates, see [src/cv/README.md](../src/cv/README.md).

## 7. After training

1. Run the tests: `python -m pytest tests`. The runtime golden tests check that the served models reproduce their exported outputs.
2. Restart the server; models are loaded at startup. Check `/readyz`.
3. Record the change in the iteration log ([WEARABLE_ML_SUBPROJECT_CONTEXT.md](WEARABLE_ML_SUBPROJECT_CONTEXT.md) §4).
