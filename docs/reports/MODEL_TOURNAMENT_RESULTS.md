# Wearable ML — Model Tournament Results (P3 v2)

_Generated 2026-10-30 05:58 UTC by `python -m src.ml.wearable.pipeline tournament`. Protocol: `docs/WEARABLE_ML_ARCHITECTURE.md` §8._

Each Tier-1 head runs its own tournament. Contenders: **XGBoost, LightGBM, Extra-Trees, MLP, 1D-CNN, MiniRocket**, against logistic regression as the reference baseline; Stage 3 also tests a soft-vote of the two finalists. All scores are **out-of-fold on subjects the model never saw**. Thresholds are 0.5 here; calibration and operating thresholds are fixed in P4.

v2 adds data (WESAD chest-ECG reference, PAMAP2, Capture-24, AFDB, LTAFDB; Stress-Predict as an external test) and candidates. Because v2 test sets are larger and differently balanced, the like-for-like comparison with v1 is the **v2 model scored on the v1 dataset** column.

## Summary

| Head | Winner (v2) | Macro-F1 v2 (all data) | v2 on v1 dataset | v1 winner · macro-F1 | Runner-up | Baseline (logreg) | Decision |
|---|---|---|---|---|---|---|---|
| stress | **minirocket** | 0.937 | 0.937 | logreg · 0.885 | extratrees (0.893) | 0.877 | significant |
| fall | **vote(extratrees+cnn1d)** | 0.898 | — | xgboost · 0.972 | cnn1d (0.842) | 0.691 | soft-vote significantly better |
| activity | **extratrees** | 0.801 | 0.903 | xgboost · 0.903 | lightgbm (0.794) | 0.737 | significant |
| hr_trust | **vote(cnn1d+extratrees)** | 0.767 | 0.753 | cnn1d · 0.755 | extratrees (0.753) | 0.729 | soft-vote significantly better |
| rhythm | **cnn1d** | 0.932 | 0.822 | logreg · 0.752 | minirocket (0.912) | 0.892 | significant |

## Stress (WESAD; external: Stress-Predict)

- **Windows:** 5,268 from 15 subjects/patients · window 40 frames (60 s) · 24 tabular features
- **Classes:** non_stress: 3,694, stress: 1,574
- **Validation:** 5-fold StratifiedGroupKFold by subject (no subject appears in both train and test); Stage 2 tunes inside each training split with 3-fold inner CV
- **Winner: `minirocket`** — minirocket better: subject-bootstrap 95% CI of macro-F1 difference excludes 0
- **v1 (P3 baseline):** `logreg` 0.885 on 5,268 windows / 15 subjects

### Stage 1 — screening (default hyper-parameters, all candidates)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **minirocket** | 0.932 ± 0.049 | 0.928 | 0.989 | 0.887 | 0.969 | 0.143 | 0.023 | 3.6 | 6.84 | 44 |
| **extratrees** | 0.893 ± 0.067 | 0.897 | 0.976 | 0.858 | 0.935 | 0.201 | 0.053 | 0.5 | 37.57 | 4162 |
| mlp | 0.884 ± 0.072 | 0.890 | 0.947 | 0.860 | 0.919 | 0.272 | 0.026 | 2.0 | 0.61 | 53 |
| logreg | 0.873 ± 0.078 | 0.870 | 0.956 | 0.797 | 0.942 | 0.338 | 0.062 | 0.0 | 0.39 | 2 |
| cnn1d | 0.873 ± 0.080 | 0.878 | 0.945 | 0.842 | 0.914 | 0.288 | 0.028 | 4.1 | 0.63 | 67 |
| lightgbm | 0.856 ± 0.082 | 0.866 | 0.952 | 0.827 | 0.905 | 0.459 | 0.092 | 0.4 | 1.56 | 777 |
| xgboost | 0.850 ± 0.085 | 0.862 | 0.952 | 0.830 | 0.894 | 0.415 | 0.090 | 0.6 | 1.04 | 363 |

Finalists (bold): minirocket, extratrees. `logreg` is the reference baseline the contenders must beat; it advances only if it places in the top two.

### Stage 2 — semifinal (nested Optuna tuning)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **minirocket** | 0.936 ± 0.046 | 0.930 | 0.989 | 0.885 | 0.975 | 0.152 | 0.023 | 3.0 | 6.89 | 25 |
| extratrees | 0.885 ± 0.091 | 0.886 | 0.967 | 0.823 | 0.950 | 0.231 | 0.054 | 0.4 | 46.65 | 8846 |

### Stage 3 — final

- Paired fold comparison `minirocket` − `extratrees`: mean +0.050, leader better in 4/5 folds
- Subject-level bootstrap (1000 resamples) of macro-F1 difference: +0.044, 95 % CI [+0.001, +0.096]
- Soft-vote `minirocket+extratrees`: macro-F1 0.933; vs single winner -0.004, 95 % CI [-0.011, +0.002] → not adopted
- Selected hyper-parameters: `{"minirocket": {"n_features": 1000, "C": 0.1}}`

**Per-class F1 (Stage 2, out-of-fold):**

| Model | F1 non_stress | F1 stress |
|---|---|---|
| minirocket | 0.964 | 0.911 |
| extratrees | 0.938 | 0.848 |

**Selected model (`minirocket`) per source dataset (out-of-fold):**

| Dataset | Windows | Subjects | Macro-F1 | Balanced acc. | Sensitivity | Specificity |
|---|---|---|---|---|---|---|
| wesad | 5,268 | 15 | 0.937 | 0.930 | 0.885 | 0.975 |

### External test — stress_predict (17,323 windows, never seen in training or tuning)

| Model | Macro-F1 | Sensitivity | Specificity | AUROC |
|---|---|---|---|---|
| minirocket | 0.549 | 0.594 | 0.550 | 0.588 |
| extratrees | 0.575 | 0.488 | 0.672 | 0.621 |
| vote | 0.557 | 0.568 | 0.581 | 0.618 |

_Runtime: 6.1 min._

## Fall / impact (UP-Fall + SisFall + daily life; external: HIFD)

- **Windows:** 561,095 from 190 subjects/patients · window 4 frames (6 s) · 12 tabular features
- **Classes:** no_fall: 553,691, fall: 7,404
- **Validation:** 5-fold StratifiedGroupKFold by subject (no subject appears in both train and test); Stage 2 tunes inside each training split with 3-fold inner CV
- **Winner: `vote(extratrees+cnn1d)`** — extratrees better: subject-bootstrap 95% CI of macro-F1 difference excludes 0; soft-vote extratrees+cnn1d significantly better than extratrees (CI [+0.009, +0.034]) -> adopted
- **v1 (P3 baseline):** `xgboost` 0.972 on 41,867 windows / 55 subjects
- Not entered: minirocket (window of 4 frames is shorter than MiniRocket's kernel span)

### Stage 1 — screening (default hyper-parameters, all candidates)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **extratrees** | 0.868 ± 0.024 | 0.900 | 0.990 | 0.805 | 0.995 | 0.024 | 0.005 | 10.7 | 8.01 | 19778 |
| **cnn1d** | 0.835 ± 0.037 | 0.978 | 0.995 | 0.967 | 0.988 | 0.034 | 0.003 | 231.0 | 0.52 | 66 |
| xgboost | 0.820 ± 0.039 | 0.948 | 0.992 | 0.908 | 0.988 | 0.036 | 0.003 | 12.7 | 0.41 | 1062 |
| lightgbm | 0.819 ± 0.038 | 0.948 | 0.991 | 0.908 | 0.988 | 0.037 | 0.004 | 6.4 | 0.57 | 1023 |
| mlp | 0.722 ± 0.038 | 0.966 | 0.993 | 0.962 | 0.970 | 0.079 | 0.004 | 55.1 | 0.41 | 47 |
| logreg | 0.691 ± 0.034 | 0.955 | 0.988 | 0.947 | 0.963 | 0.137 | 0.013 | 2.1 | 0.36 | 2 |

Finalists (bold): extratrees, cnn1d. `logreg` is the reference baseline the contenders must beat; it advances only if it places in the top two.

### Stage 2 — semifinal (nested Optuna tuning)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **extratrees** | 0.875 ± 0.021 | 0.871 | 0.988 | 0.746 | 0.997 | 0.021 | 0.004 | 5.6 | 4.93 | 12840 |
| **cnn1d** | 0.841 ± 0.035 | 0.977 | 0.995 | 0.965 | 0.989 | 0.031 | 0.003 | 239.3 | 0.64 | 66 |

### Stage 3 — final

- Paired fold comparison `extratrees` − `cnn1d`: mean +0.035, leader better in 4/5 folds
- Subject-level bootstrap (1000 resamples) of macro-F1 difference: +0.034, 95 % CI [+0.013, +0.058]
- Soft-vote `extratrees+cnn1d`: macro-F1 0.898; vs single winner +0.022, 95 % CI [+0.009, +0.034] → adopted
- Selected hyper-parameters: `{"extratrees": {"n_estimators": 100, "max_features": 0.43371571882817456, "min_samples_leaf": 2}, "cnn1d": {"channels": 32, "dropout": 0.2, "lr": 0.001, "weight_decay": 0.0001}}`

**Per-class F1 (Stage 2, out-of-fold):**

| Model | F1 no_fall | F1 fall |
|---|---|---|
| extratrees | 0.997 | 0.756 |
| cnn1d | 0.994 | 0.689 |

**Selected model (`vote(extratrees+cnn1d)`) per source dataset (out-of-fold):**

| Dataset | Windows | Subjects | Macro-F1 | Balanced acc. | Sensitivity | Specificity |
|---|---|---|---|---|---|---|
| capture24 | 434,332 | 96 | acc. 0.996 (one class) | — | — | — |
| pamap2 | 12,814 | 9 | acc. 0.997 (one class) | — | — | — |
| ppg_dalia | 43,144 | 15 | acc. 0.999 (one class) | — | — | — |
| sisfall | 33,145 | 38 | 0.944 | 0.954 | 0.940 | 0.968 |
| upfall | 8,722 | 17 | 0.910 | 0.872 | 0.748 | 0.997 |
| wesad | 28,938 | 15 | acc. 0.999 (one class) | — | — | — |

### External test — hifd (3,447 windows, never seen in training or tuning)

| Model | Macro-F1 | Sensitivity | Specificity | AUROC |
|---|---|---|---|---|
| extratrees | 0.868 | 0.760 | 0.970 | 0.981 |
| cnn1d | 0.806 | 0.639 | 0.958 | 0.935 |
| vote | 0.822 | 0.659 | 0.964 | 0.974 |

### Daily-life false alarms (accelerometer-only fall model)

- **Held-out people:** 55 Capture-24 participants (1,403 h of free-living wrist data) were never used for training or tuning.
- **Out-of-fold daily life:** PPG-DaLiA, WESAD and PAMAP2 subjects (71 h), each scored by a model that never saw that person.
- **Fall sensitivity:** share of the 2,053 UP-Fall/SisFall fall trials with at least one alarm (out-of-fold). Alarms within 10 s are merged into one event. Target ≤ 1 false alarm per 8 h.

| Threshold | False alarms / 8 h (held-out Capture-24) | False alarms / 8 h (OOF daily life) | Fall sensitivity (OOF) |
|---|---|---|---|
| 0.5 | 17.08 | 8.71 | 0.948 |
| 0.7 | 5.67 | 1.81 | 0.852 |
| 0.9 | 1.03 | 0.11 | 0.596 |
| 0.95 | 0.38 | 0.11 | 0.445 |

These are Tier-1 numbers. The Tier-2 fusion layer (P5) adds post-impact confirmation; the operating threshold is chosen in P4.

_Runtime: 131.5 min._

## Activity intensity (PPG-DaLiA + PAMAP2 + Capture-24)

- **Windows:** 90,349 from 166 subjects/patients · window 20 frames (30 s) · 12 tabular features
- **Classes:** rest: 68,980, light: 14,090, active: 7,279
- **Validation:** 5-fold StratifiedGroupKFold by subject (no subject appears in both train and test); Stage 2 tunes inside each training split with 3-fold inner CV
- **Winner: `extratrees`** — extratrees better: subject-bootstrap 95% CI of macro-F1 difference excludes 0
- **v1 (P3 baseline):** `xgboost` 0.903 on 15,405 windows / 15 subjects

### Stage 1 — screening (default hyper-parameters, all candidates)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|
| **extratrees** | 0.799 ± 0.018 | 0.809 | 0.953 | 0.323 | 0.026 | 20.6 | 30.96 | 149040 |
| **lightgbm** | 0.780 ± 0.019 | 0.815 | 0.950 | 0.356 | 0.014 | 11.8 | 1.99 | 3021 |
| xgboost | 0.779 ± 0.022 | 0.816 | 0.950 | 0.360 | 0.010 | 14.0 | 1.66 | 3233 |
| cnn1d | 0.765 ± 0.026 | 0.817 | 0.948 | 0.399 | 0.013 | 113.1 | 0.62 | 67 |
| mlp | 0.763 ± 0.022 | 0.810 | 0.943 | 0.407 | 0.012 | 53.6 | 0.71 | 48 |
| minirocket | 0.746 ± 0.018 | 0.799 | 0.940 | 0.419 | 0.009 | 124.9 | 8.00 | 56 |
| logreg | 0.735 ± 0.011 | 0.781 | 0.924 | 0.472 | 0.045 | 0.9 | 0.49 | 2 |

Finalists (bold): extratrees, lightgbm. `logreg` is the reference baseline the contenders must beat; it advances only if it places in the top two.

### Stage 2 — semifinal (nested Optuna tuning)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|
| **extratrees** | 0.799 ± 0.017 | 0.798 | 0.953 | 0.313 | 0.022 | 2.6 | 5.24 | 103223 |
| lightgbm | 0.792 ± 0.017 | 0.787 | 0.949 | 0.400 | 0.062 | 10.8 | 1.86 | 18057 |

### Stage 3 — final

- Paired fold comparison `extratrees` − `lightgbm`: mean +0.007, leader better in 5/5 folds
- Subject-level bootstrap (1000 resamples) of macro-F1 difference: +0.007, 95 % CI [+0.003, +0.012]
- Soft-vote `extratrees+lightgbm`: macro-F1 0.799; vs single winner -0.002, 95 % CI [-0.006, +0.001] → not adopted
- Selected hyper-parameters: `{"extratrees": {"n_estimators": 100, "max_features": 0.43371571882817456, "min_samples_leaf": 2}}`

**Per-class F1 (Stage 2, out-of-fold):**

| Model | F1 rest | F1 light | F1 active |
|---|---|---|---|
| extratrees | 0.942 | 0.668 | 0.793 |
| lightgbm | 0.940 | 0.664 | 0.779 |

**Selected model (`extratrees`) per source dataset (out-of-fold):**

| Dataset | Windows | Subjects | Macro-F1 | Balanced acc. |
|---|---|---|---|---|
| capture24 | 74,944 | 151 | 0.732 | 0.724 |
| ppg_dalia | 15,405 | 15 | 0.903 | 0.876 |

### External test — pamap2 (4,207 windows, never seen in training or tuning)

| Model | Macro-F1 | Sensitivity | Specificity | AUROC |
|---|---|---|---|---|
| extratrees | 0.590 | — | — | 0.886 |
| lightgbm | 0.611 | — | — | 0.943 |
| vote | 0.607 | — | — | 0.892 |

_Runtime: 63.5 min._

## Heart-rate trust (PPG-DaLiA + WESAD, ECG reference)

- **Windows:** 72,003 from 30 subjects/patients · window 8 frames (12 s) · 12 tabular features
- **Classes:** unreliable: 23,361, reliable: 48,642
- **Validation:** 5-fold StratifiedGroupKFold by subject (no subject appears in both train and test); Stage 2 tunes inside each training split with 3-fold inner CV
- **Winner: `vote(cnn1d+extratrees)`** — no significant difference (95% CI [-0.004, +0.011] includes 0); tie broken by efficiency -> cnn1d (smaller/faster); soft-vote cnn1d+extratrees significantly better than cnn1d (CI [+0.006, +0.013]) -> adopted
- **v1 (P3 baseline):** `cnn1d` 0.755 on 43,106 windows / 15 subjects

### Stage 1 — screening (default hyper-parameters, all candidates)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **cnn1d** | 0.756 ± 0.012 | 0.793 | 0.871 | 0.727 | 0.858 | 0.445 | 0.036 | 38.4 | 0.58 | 67 |
| **extratrees** | 0.752 ± 0.009 | 0.770 | 0.860 | 0.783 | 0.756 | 0.439 | 0.012 | 6.3 | 36.43 | 277997 |
| xgboost | 0.747 ± 0.009 | 0.775 | 0.858 | 0.746 | 0.804 | 0.459 | 0.033 | 1.9 | 0.65 | 1137 |
| lightgbm | 0.746 ± 0.010 | 0.775 | 0.859 | 0.743 | 0.808 | 0.458 | 0.035 | 1.0 | 0.72 | 1008 |
| mlp | 0.742 ± 0.009 | 0.780 | 0.862 | 0.711 | 0.848 | 0.465 | 0.038 | 12.6 | 0.51 | 47 |
| minirocket | 0.736 ± 0.006 | 0.762 | 0.841 | 0.741 | 0.783 | 0.495 | 0.031 | 18.4 | 2.73 | 42 |
| logreg | 0.726 ± 0.006 | 0.752 | 0.830 | 0.733 | 0.772 | 0.514 | 0.017 | 0.2 | 0.51 | 2 |

Finalists (bold): cnn1d, extratrees. `logreg` is the reference baseline the contenders must beat; it advances only if it places in the top two.

### Stage 2 — semifinal (nested Optuna tuning)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **cnn1d** | 0.755 ± 0.014 | 0.791 | 0.870 | 0.729 | 0.853 | 0.442 | 0.033 | 42.6 | 0.67 | 67 |
| **extratrees** | 0.750 ± 0.011 | 0.766 | 0.858 | 0.791 | 0.740 | 0.439 | 0.010 | 4.7 | 25.95 | 134755 |

### Stage 3 — final

- Paired fold comparison `cnn1d` − `extratrees`: mean +0.005, leader better in 4/5 folds
- Subject-level bootstrap (1000 resamples) of macro-F1 difference: +0.004, 95 % CI [-0.004, +0.011]
- Soft-vote `cnn1d+extratrees`: macro-F1 0.767; vs single winner +0.010, 95 % CI [+0.006, +0.013] → adopted
- Selected hyper-parameters: `{"cnn1d": {"channels": 32, "dropout": 0.31939631788866646, "lr": 0.0004296748115469076, "weight_decay": 2.9375384576328295e-05}, "extratrees": {"n_estimators": 100, "max_features": 0.43371571882817456, "min_samples_leaf": 2}}`

**Per-class F1 (Stage 2, out-of-fold):**

| Model | F1 unreliable | F1 reliable |
|---|---|---|
| cnn1d | 0.705 | 0.810 |
| extratrees | 0.681 | 0.826 |

**Selected model (`vote(cnn1d+extratrees)`) per source dataset (out-of-fold):**

| Dataset | Windows | Subjects | Macro-F1 | Balanced acc. | Sensitivity | Specificity |
|---|---|---|---|---|---|---|
| ppg_dalia | 43,106 | 15 | 0.753 | 0.780 | 0.719 | 0.841 |
| wesad | 28,897 | 15 | 0.785 | 0.802 | 0.826 | 0.779 |

_Runtime: 51.7 min._

## Heart rhythm (MIT-BIH + AFDB + LTAFDB, PPG-like augmentation)

- **Windows:** 126,579 from 155 subjects/patients · window 40 frames (60 s) · 15 tabular features
- **Classes:** regular: 70,762, abnormal: 55,817
- **Validation:** 5-fold StratifiedGroupKFold by subject (no subject appears in both train and test); Stage 2 tunes inside each training split with 3-fold inner CV
- **Winner: `cnn1d`** — cnn1d better: subject-bootstrap 95% CI of macro-F1 difference excludes 0
- **v1 (P3 baseline):** `logreg` 0.752 on 22,812 windows / 46 subjects

### Stage 1 — screening (default hyper-parameters, all candidates)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **cnn1d** | 0.923 ± 0.034 | 0.932 | 0.978 | 0.930 | 0.935 | 0.180 | 0.014 | 233.5 | 0.65 | 65 |
| **minirocket** | 0.901 ± 0.043 | 0.914 | 0.971 | 0.928 | 0.901 | 0.220 | 0.014 | 64.6 | 7.68 | 43 |
| mlp | 0.896 ± 0.042 | 0.908 | 0.966 | 0.904 | 0.912 | 0.236 | 0.014 | 14.6 | 0.78 | 49 |
| xgboost | 0.891 ± 0.042 | 0.904 | 0.964 | 0.908 | 0.900 | 0.251 | 0.025 | 3.8 | 0.64 | 1167 |
| lightgbm | 0.891 ± 0.042 | 0.903 | 0.965 | 0.907 | 0.900 | 0.246 | 0.024 | 2.2 | 0.92 | 1020 |
| extratrees | 0.890 ± 0.046 | 0.903 | 0.965 | 0.909 | 0.897 | 0.245 | 0.011 | 5.8 | 35.81 | 132148 |
| logreg | 0.880 ± 0.050 | 0.894 | 0.954 | 0.903 | 0.885 | 0.274 | 0.018 | 0.5 | 0.38 | 2 |

Finalists (bold): cnn1d, minirocket. `logreg` is the reference baseline the contenders must beat; it advances only if it places in the top two.

### Stage 2 — semifinal (nested Optuna tuning)

| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | Sensitivity | Specificity | Log-loss | ECE | Fit s/fold | Latency ms | Size KB |
|---|---|---|---|---|---|---|---|---|---|---|
| **cnn1d** | 0.923 ± 0.034 | 0.932 | 0.978 | 0.930 | 0.935 | 0.180 | 0.014 | 232.4 | 0.56 | 65 |
| minirocket | 0.901 ± 0.043 | 0.914 | 0.971 | 0.928 | 0.901 | 0.220 | 0.014 | 65.1 | 6.14 | 43 |

### Stage 3 — final

- Paired fold comparison `cnn1d` − `minirocket`: mean +0.022, leader better in 5/5 folds
- Subject-level bootstrap (1000 resamples) of macro-F1 difference: +0.020, 95 % CI [+0.012, +0.028]
- Soft-vote `cnn1d+minirocket`: macro-F1 0.930; vs single winner -0.002, 95 % CI [-0.005, +0.000] → not adopted
- Selected hyper-parameters: `{"cnn1d": {"channels": 32, "dropout": 0.2, "lr": 0.001, "weight_decay": 0.0001}}`

**Per-class F1 (Stage 2, out-of-fold):**

| Model | F1 regular | F1 abnormal |
|---|---|---|
| cnn1d | 0.939 | 0.924 |
| minirocket | 0.920 | 0.904 |

**Selected model (`cnn1d`) per source dataset (out-of-fold):**

| Dataset | Windows | Subjects | Macro-F1 | Balanced acc. | Sensitivity | Specificity |
|---|---|---|---|---|---|---|
| afdb | 29,889 | 25 | 0.936 | 0.935 | 0.919 | 0.952 |
| ltafdb | 73,878 | 84 | 0.938 | 0.939 | 0.942 | 0.935 |
| mitbih | 22,812 | 46 | 0.822 | 0.870 | 0.823 | 0.917 |

_Runtime: 133.3 min._

---

v1 results (P3, 2026-10-30) are archived in `data/processed/wearable/tournament/v1/` (JSON + the v1 report).
