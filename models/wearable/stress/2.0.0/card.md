# Model card — `stress` v2.0.0

- **Model:** `minirocket` (single) · features `stress` (24 tabular + sequence 40×7) · window 40 frames (60 s)
- **Selected by:** P3 v2 tournament — minirocket better: subject-bootstrap 95% CI of macro-F1 difference excludes 0
- **Training data:** 5,268 windows, 15 subjects (wesad)
- **Calibration:** platt (ECE 0.023 → 0.008, cross-fitted by subject)
- **Decision rule:** threshold 0.33 — maximises out-of-fold macro-F1 (cross-fitted calibrated probabilities)
- **Serving:** ONNX (model_minirocket.onnx 58 KB); parity with Python max |Δp| 5.4e-03

## Intended use

Evidence for ELEVATED_STRESS and CRUSH_ENTRAPMENT in the Tier-2 fusion layer; never a diagnosis.

## Performance (out-of-fold, subjects never seen by the model that scored them)

- **Macro-F1:** 0.935 (95 % CI 0.889–0.970, subject bootstrap)
- **AUROC:** 0.985 · **log-loss:** 0.150 · **ECE:** 0.008
- **Sensitivity:** 0.945 (95 % CI 0.878–0.989) · **specificity:** 0.944 · **PPV:** 0.878

**Per class F1:** non_stress 0.960, stress 0.910

**Per source dataset:**

| Dataset | Macro-F1 (95 % CI) | Sensitivity | Specificity |
|---|---|---|---|
| wesad | 0.935 (0.889–0.970) | 0.945 | 0.944 |

## External test (stress_predict, never used for training or tuning)

- Macro-F1 0.521 (95 % CI 0.479–0.559) · AUROC 0.589 · sensitivity 0.667 · specificity 0.459

## Limitations

Trained on 15 WESAD lab subjects (TSST protocol). Transfer to a different stress protocol (Stress-Predict) is weak - see external test. Treat as low-confidence evidence.

## Reproduce

```
python -m src.ml.wearable.pipeline tournament stress
python -m src.ml.wearable.pipeline final stress
```
