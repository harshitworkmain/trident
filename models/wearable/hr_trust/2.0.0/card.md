# Model card — `hr_trust` v2.0.0

- **Model:** `vote(cnn1d+extratrees)` (mean) · features `hr_trust` (12 tabular + sequence 8×6) · window 8 frames (12 s)
- **Selected by:** P3 v2 tournament — no significant difference (95% CI [-0.004, +0.011] includes 0); tie broken by efficiency -> cnn1d (smaller/faster); soft-vote cnn1d+extratrees significantly better than cnn1d (CI [+0.006, +0.013]) -> adopted
- **Training data:** 72,003 windows, 30 subjects (ppg_dalia, wesad)
- **Calibration:** platt (ECE 0.015 → 0.004, cross-fitted by subject)
- **Decision rule:** threshold 0.59 — maximises out-of-fold macro-F1 (cross-fitted calibrated probabilities)
- **Serving:** ONNX (model_cnn1d.onnx 61 KB, model_extratrees.onnx 73383 KB); parity with Python max |Δp| 3.2e-07

## Intended use

Gates heart-rate-based rules: low trust suppresses cardiac/shock rules and flags the reading.

## Performance (out-of-fold, subjects never seen by the model that scored them)

- **Macro-F1:** 0.768 (95 % CI 0.742–0.792, subject bootstrap)
- **AUROC:** 0.872 · **log-loss:** 0.409 · **ECE:** 0.004
- **Sensitivity:** 0.792 (95 % CI 0.749–0.831) · **specificity:** 0.775 · **PPV:** 0.880

**Per class F1:** unreliable 0.702, reliable 0.834

**Per source dataset:**

| Dataset | Macro-F1 (95 % CI) | Sensitivity | Specificity |
|---|---|---|---|
| ppg_dalia | 0.755 (0.722–0.790) | 0.751 | 0.798 |
| wesad | 0.784 (0.757–0.803) | 0.850 | 0.734 |

## Limitations

The label is defined by our firmware-style BPM vs an ECG reference (10 bpm tolerance); a different PPG front-end changes what "reliable" means.

## Reproduce

```
python -m src.ml.wearable.pipeline tournament hr_trust
python -m src.ml.wearable.pipeline final hr_trust
```
