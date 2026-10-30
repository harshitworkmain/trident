# Model card — `rhythm` v2.0.0

- **Model:** `cnn1d` (single) · features `rhythm` (15 tabular + sequence 64×2) · window 40 frames (60 s)
- **Selected by:** P3 v2 tournament — cnn1d better: subject-bootstrap 95% CI of macro-F1 difference excludes 0
- **Training data:** 126,579 windows, 155 subjects (afdb, ltafdb, mitbih)
- **Calibration:** platt (ECE 0.014 → 0.008, cross-fitted by subject)
- **Decision rule:** threshold 0.61 — maximises out-of-fold macro-F1 (cross-fitted calibrated probabilities)
- **Serving:** ONNX (model_cnn1d.onnx 60 KB); parity with Python max |Δp| 6.7e-07

## Intended use

Screening evidence of an irregular rhythm from wrist RR intervals; not an ECG diagnosis.

## Performance (out-of-fold, subjects never seen by the model that scored them)

- **Macro-F1:** 0.932 (95 % CI 0.915–0.949, subject bootstrap)
- **AUROC:** 0.977 · **log-loss:** 0.181 · **ECE:** 0.008
- **Sensitivity:** 0.900 (95 % CI 0.869–0.929) · **specificity:** 0.961 · **PPV:** 0.947

**Per class F1:** regular 0.942, abnormal 0.923

**Per source dataset:**

| Dataset | Macro-F1 (95 % CI) | Sensitivity | Specificity |
|---|---|---|---|
| afdb | 0.937 (0.885–0.969) | 0.887 | 0.976 |
| ltafdb | 0.936 (0.913–0.955) | 0.914 | 0.964 |
| mitbih | 0.832 (0.705–0.904) | 0.758 | 0.942 |

## Limitations

Learned from ECG beat annotations degraded to PPG-like timing noise (calibrated on PPG-DaLiA), not from real wrist PPG of arrhythmia patients. AF and other irregular rhythms are pooled as "abnormal".

## Reproduce

```
python -m src.ml.wearable.pipeline tournament rhythm
python -m src.ml.wearable.pipeline final rhythm
```
