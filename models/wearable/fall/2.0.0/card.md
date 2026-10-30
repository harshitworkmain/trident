# Model card — `fall` v2.0.0

- **Model:** `vote(extratrees+cnn1d)` (mean) · features `fall_acc_only` (12 tabular + sequence 4×5) · window 4 frames (6 s)
- **Selected by:** P3 v2 tournament — extratrees better: subject-bootstrap 95% CI of macro-F1 difference excludes 0; soft-vote extratrees+cnn1d significantly better than extratrees (CI [+0.009, +0.034]) -> adopted
- **Training data:** 561,095 windows, 190 subjects (capture24, pamap2, ppg_dalia, sisfall, upfall, wesad)
- **Calibration:** platt (ECE 0.006 → 0.001, cross-fitted by subject)
- **Decision rule:** threshold 0.72 — most sensitive threshold with OOF daily-life false alarms ≤ 1.0/8 h
- **Serving:** ONNX (model_extratrees.onnx 6506 KB, model_cnn1d.onnx 61 KB); parity with Python max |Δp| 1.2e-06

## Intended use

Impact/fall evidence for CONCUSSIVE_STASIS; fusion requires post-impact immobility before alarming.

## Performance (out-of-fold, subjects never seen by the model that scored them)

- **Macro-F1:** 0.867 (95 % CI 0.843–0.886, subject bootstrap)
- **AUROC:** 0.994 · **log-loss:** 0.013 · **ECE:** 0.001
- **Sensitivity:** 0.614 (95 % CI 0.554–0.666) · **specificity:** 0.999 · **PPV:** 0.920

**Per class F1:** no_fall 0.997, fall 0.737

**Per source dataset:**

| Dataset | Macro-F1 (95 % CI) | Sensitivity | Specificity |
|---|---|---|---|
| sisfall | 0.861 (0.834–0.885) | 0.637 | 0.995 |
| upfall | 0.704 (0.645–0.761) | 0.274 | 1.000 |

## External test (hifd, never used for training or tuning)

- Macro-F1 0.716 (95 % CI 0.678–0.753) · AUROC 0.974 · sensitivity 0.337 · specificity 0.991

## Daily-life false alarms (held-out Capture-24 people)

- 55 people, 1,403 h: **2.14 false alarms per 8 h** at the operating threshold (375 events).

| Threshold | False alarms / 8 h |
|---|---|
| 0.5 | 5.09 |
| 0.7 | 2.40 |
| 0.9 | 0.79 |
| 0.95 | 0.38 |
| 0.98 | 0.14 |
| 0.99 | 0.07 |

## Limitations

Falls come from young/elderly volunteers falling onto mats (UP-Fall, SisFall), not real-world falls. Accelerometer-only. SisFall is waist-worn. Daily-life negatives are mostly healthy adults.

## Reproduce

```
python -m src.ml.wearable.pipeline tournament fall
python -m src.ml.wearable.pipeline final fall
```
