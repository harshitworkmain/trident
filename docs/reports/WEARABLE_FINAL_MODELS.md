# Wearable ML — Final Tier-1 Models (P4)

_Generated 2026-10-30 06:13 UTC by `python -m src.ml.wearable.pipeline final`. Registry: `models/wearable/registry.json`._

Each head is the P3 v2 tournament winner, refitted on all of its training windows, exported to ONNX (verified against Python), calibrated on out-of-fold predictions and given an operating threshold. All metrics are out-of-fold on subjects the scoring model never saw, after cross-fitted calibration, with subject-bootstrap 95 % confidence intervals.

| Head | Model | Macro-F1 (95 % CI) | AUROC | Sensitivity | Specificity | ECE before → after | Threshold | External test | Card |
|---|---|---|---|---|---|---|---|---|---|
| stress | `minirocket` | 0.935 (0.889–0.970) | 0.985 | 0.945 | 0.944 | 0.023 → 0.008 | 0.33 | stress_predict: macro-F1 0.521 | [card](../../models/wearable/stress/2.0.0/card.md) |
| hr_trust | `vote(cnn1d+extratrees)` | 0.768 (0.742–0.792) | 0.872 | 0.792 | 0.775 | 0.015 → 0.004 | 0.59 | — | [card](../../models/wearable/hr_trust/2.0.0/card.md) |
| rhythm | `cnn1d` | 0.932 (0.915–0.949) | 0.977 | 0.900 | 0.961 | 0.014 → 0.008 | 0.61 | — | [card](../../models/wearable/rhythm/2.0.0/card.md) |
| activity | `extratrees` | 0.801 (0.778–0.820) | 0.953 | — | — | 0.022 → 0.011 | argmax | pamap2: macro-F1 0.590 | [card](../../models/wearable/activity/2.0.0/card.md) |
| fall | `vote(extratrees+cnn1d)` | 0.867 (0.843–0.886) | 0.994 | 0.614 | 0.999 | 0.006 → 0.001 | 0.72 | hifd: macro-F1 0.716; 2.14 false alarms / 8 h on 1,403 h held-out daily life | [card](../../models/wearable/fall/2.0.0/card.md) |

Serving contract per head: inputs `X` (tabular features, registry order) and `S` (frame sequence), output `proba`; members of a soft-vote are averaged, then the calibrator and threshold in `calibration.json` are applied. `golden.npz` holds reference inputs/outputs for serving tests.
