# Model card — `activity` v2.0.0

- **Model:** `extratrees` (single) · features `activity` (12 tabular + sequence 20×6) · window 20 frames (30 s)
- **Selected by:** P3 v2 tournament — extratrees better: subject-bootstrap 95% CI of macro-F1 difference excludes 0
- **Training data:** 90,349 windows, 166 subjects (capture24, ppg_dalia)
- **Calibration:** temperature (ECE 0.022 → 0.011, cross-fitted by subject)
- **Decision rule:** threshold argmax — argmax (multi-class)
- **Serving:** ONNX (model_extratrees.onnx 64098 KB); parity with Python max |Δp| 2.6e-07

## Intended use

Context for fusion (rest vs exercise) so exertion is not mistaken for shock or stress.

## Performance (out-of-fold, subjects never seen by the model that scored them)

- **Macro-F1:** 0.801 (95 % CI 0.778–0.820, subject bootstrap)
- **AUROC:** 0.953 · **log-loss:** 0.311 · **ECE:** 0.011

**Per class F1:** rest 0.942, light 0.668, active 0.793

**Per source dataset:**

| Dataset | Macro-F1 (95 % CI) |
|---|---|
| capture24 | 0.732 (0.713–0.750) |
| ppg_dalia | 0.903 (0.863–0.934) |

## External test (pamap2, never used for training or tuning)

- Macro-F1 0.590 (95 % CI 0.562–0.616) · AUROC 0.886

## Limitations

Behaviour-based intensity labels (Walmsley 2020); light-class boundaries are fuzzy. Capture-24 windows have no heart rate, PPG-DaLiA/PAMAP2 windows do.

## Reproduce

```
python -m src.ml.wearable.pipeline tournament activity
python -m src.ml.wearable.pipeline final activity
```
