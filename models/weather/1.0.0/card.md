# Weather forecaster 1.0.0 - model card

Site: chennai (13.0827, 80.2707). Data: offline-cache (open_meteo_chennai_2015-01-01_2026-10-24.parquet) 2015-01-01 .. 2026-10-24 (103560 hourly rows).
Backtest: models fitted on 2015-01-09 .. 2025-04-24; calibration/selection slice 2025-04-24 .. 2025-10-24 (1448 origins); test 2025-10-24 .. 2026-10-24 (2905 origins every 3 h).

## Headline (test window, chosen model, calibrated)

| variable | h | chosen | MAE | MAE persistence | MAE seasonal-naive | skill vs pers. | skill vs s-naive | p10-p90 coverage (raw) |
|---|---|---|---|---|---|---|---|---|
| temp (°C) | 6 | lgbm | 0.689 | 2.708 | 0.865 | 0.75 | 0.20 | 0.83 (0.74) |
| temp (°C) | 24 | blend | 0.805 | 0.864 | 0.864 | 0.07 | 0.07 | 0.82 (0.73) |
| temp (°C) | 48 | blend | 0.954 | 1.059 | 1.059 | 0.10 | 0.10 | 0.79 (0.70) |
| rh (%) | 6 | blend | 4.727 | 13.875 | 6.272 | 0.66 | 0.25 | 0.77 (0.74) |
| rh (%) | 24 | blend | 5.648 | 6.273 | 6.273 | 0.10 | 0.10 | 0.79 (0.73) |
| rh (%) | 48 | blend | 6.791 | 8.087 | 8.087 | 0.16 | 0.16 | 0.76 (0.69) |
| rain (mm/h) | 6 | blend | 0.162 | 0.256 | 0.264 | 0.37 | 0.39 | 0.80 (0.73) |
| rain (mm/h) | 24 | gru | 0.170 | 0.265 | 0.265 | 0.36 | 0.36 | 0.81 (0.77) |
| rain (mm/h) | 48 | gru | 0.171 | 0.290 | 0.290 | 0.41 | 0.41 | 0.80 (0.83) |
| wind (m/s) | 6 | blend | 0.636 | 1.046 | 0.788 | 0.39 | 0.19 | 0.76 (0.81) |
| wind (m/s) | 24 | blend | 0.698 | 0.787 | 0.787 | 0.11 | 0.11 | 0.77 (0.82) |
| wind (m/s) | 48 | blend | 0.814 | 0.924 | 0.924 | 0.12 | 0.12 | 0.73 (0.80) |
| pres (hPa) | 6 | blend | 0.455 | 1.930 | 0.827 | 0.76 | 0.45 | 0.79 (0.77) |
| pres (hPa) | 24 | blend | 0.761 | 0.829 | 0.829 | 0.08 | 0.08 | 0.76 (0.76) |
| pres (hPa) | 48 | blend | 1.180 | 1.266 | 1.266 | 0.07 | 0.07 | 0.72 (0.73) |

## Candidates by horizon band (test window, calibrated; mean pinball loss, lower is better)

**temp** (°C) - chosen per band: 1-3: blend, 4-6: lgbm, 7-12: blend, 13-24: blend, 25-48: blend

| band | persistence | seasonal_naive | climatology | lgbm | gru | blend | chosen MAE | chosen coverage |
|---|---|---|---|---|---|---|---|---|
| 1-3 h | 0.3663 | 0.3006 | 0.3914 | **0.1624** | 0.1777 | 0.1646 | 0.496 | 0.78 |
| 4-6 h | 0.7169 | 0.3009 | 0.3910 | **0.2222** | 0.2561 | 0.2282 | 0.682 | 0.81 |
| 7-12 h | 0.9889 | 0.3008 | 0.3914 | **0.2531** | 0.2807 | 0.2547 | 0.785 | 0.79 |
| 13-24 h | 0.7344 | 0.3008 | 0.3917 | 0.2698 | 0.2856 | **0.2675** | 0.828 | 0.78 |
| 25-48 h | 0.7846 | 0.3636 | 0.3933 | 0.3090 | 0.3265 | **0.3073** | 0.948 | 0.79 |

**rh** (%) - chosen per band: 1-3: lgbm, 4-6: blend, 7-12: blend, 13-24: blend, 25-48: blend

| band | persistence | seasonal_naive | climatology | lgbm | gru | blend | chosen MAE | chosen coverage |
|---|---|---|---|---|---|---|---|---|
| 1-3 h | 2.0315 | 2.0594 | 2.4627 | **1.0615** | 1.1375 | 1.0659 | 3.232 | 0.76 |
| 4-6 h | 3.7822 | 2.0616 | 2.4643 | **1.4525** | 1.6115 | 1.4733 | 4.584 | 0.77 |
| 7-12 h | 4.9643 | 2.0617 | 2.4661 | 1.6301 | 1.7434 | **1.6250** | 5.101 | 0.77 |
| 13-24 h | 3.8895 | 2.0616 | 2.4655 | 1.7740 | 1.8343 | **1.7551** | 5.543 | 0.77 |
| 25-48 h | 4.2169 | 2.5875 | 2.4626 | 2.0647 | 2.0957 | **2.0329** | 6.476 | 0.78 |

**rain** (mm/h) - chosen per band: 1-3: blend, 4-6: blend, 7-12: blend, 13-24: gru, 25-48: gru

| band | persistence | seasonal_naive | climatology | lgbm | gru | blend | chosen MAE | chosen coverage |
|---|---|---|---|---|---|---|---|---|
| 1-3 h | 0.0931 | 0.1180 | 0.0762 | 0.0563 | 0.0573 | **0.0561** | 0.144 | 0.79 |
| 4-6 h | 0.1150 | 0.1181 | 0.0764 | 0.0630 | 0.0641 | **0.0628** | 0.156 | 0.79 |
| 7-12 h | 0.1224 | 0.1181 | 0.0760 | **0.0641** | 0.0660 | 0.0644 | 0.159 | 0.80 |
| 13-24 h | 0.1241 | 0.1179 | 0.0756 | 0.0667 | 0.0674 | **0.0665** | 0.163 | 0.80 |
| 25-48 h | 0.1308 | 0.1320 | 0.0757 | 0.0701 | 0.0708 | **0.0698** | 0.165 | 0.80 |

**wind** (m/s) - chosen per band: 1-3: blend, 4-6: blend, 7-12: blend, 13-24: blend, 25-48: blend

| band | persistence | seasonal_naive | climatology | lgbm | gru | blend | chosen MAE | chosen coverage |
|---|---|---|---|---|---|---|---|---|
| 1-3 h | 0.2043 | 0.2601 | 0.2979 | **0.1568** | 0.1687 | 0.1585 | 0.496 | 0.75 |
| 4-6 h | 0.2990 | 0.2601 | 0.2987 | **0.1971** | 0.2124 | 0.1983 | 0.628 | 0.76 |
| 7-12 h | 0.3668 | 0.2601 | 0.2988 | **0.2108** | 0.2276 | 0.2113 | 0.667 | 0.76 |
| 13-24 h | 0.3260 | 0.2600 | 0.2989 | 0.2237 | 0.2293 | **0.2203** | 0.694 | 0.77 |
| 25-48 h | 0.3540 | 0.3022 | 0.2992 | 0.2572 | 0.2603 | **0.2526** | 0.797 | 0.73 |

**pres** (hPa) - chosen per band: 1-3: blend, 4-6: blend, 7-12: blend, 13-24: blend, 25-48: blend

| band | persistence | seasonal_naive | climatology | lgbm | gru | blend | chosen MAE | chosen coverage |
|---|---|---|---|---|---|---|---|---|
| 1-3 h | 0.2829 | 0.2625 | 0.5794 | 0.0926 | 0.0949 | **0.0915** | 0.287 | 0.78 |
| 4-6 h | 0.5328 | 0.2624 | 0.5790 | 0.1354 | 0.1406 | **0.1321** | 0.418 | 0.79 |
| 7-12 h | 0.4520 | 0.2625 | 0.5790 | 0.1701 | 0.1754 | **0.1671** | 0.526 | 0.79 |
| 13-24 h | 0.4623 | 0.2627 | 0.5789 | 0.2209 | 0.2279 | **0.2164** | 0.684 | 0.76 |
| 25-48 h | 0.5355 | 0.4034 | 0.5788 | 0.3329 | 0.3306 | **0.3227** | 1.029 | 0.74 |

## Heavy rain events (test window)

| event | forecast rule | observed | forecast | hits | hit rate | FAR | CSI |
|---|---|---|---|---|---|---|---|
| rain >= 7.6 mm/h, h 1-3 | p50 | 28 | 0 | 0 | 0.00 | – | 0.00 |
| rain >= 7.6 mm/h, h 1-3 | p90 | 28 | 34 | 8 | 0.29 | 0.76 | 0.15 |
| rain >= 7.6 mm/h, h 4-6 | p50 | 28 | 0 | 0 | 0.00 | – | 0.00 |
| rain >= 7.6 mm/h, h 4-6 | p90 | 28 | 19 | 1 | 0.04 | 0.95 | 0.02 |
| rain >= 7.6 mm/h, h 7-12 | p50 | 55 | 0 | 0 | 0.00 | – | 0.00 |
| rain >= 7.6 mm/h, h 7-12 | p90 | 55 | 20 | 0 | 0.00 | 1.00 | 0.00 |
| rain >= 7.6 mm/h, h 13-24 | p50 | 108 | 0 | 0 | 0.00 | – | 0.00 |
| rain >= 7.6 mm/h, h 13-24 | p90 | 108 | 4 | 0 | 0.00 | 1.00 | 0.00 |
| rain >= 7.6 mm/h, h 25-48 | p50 | 216 | 0 | 0 | 0.00 | – | 0.00 |
| rain >= 7.6 mm/h, h 25-48 | p90 | 216 | 0 | 0 | 0.00 | – | 0.00 |
| 24 h rain >= 64.5 mm, next_1-24h | rain24 p50 | 35 | 0 | 0 | 0.00 | – | 0.00 |
| 24 h rain >= 64.5 mm, next_1-24h | rain24 p90 | 35 | 26 | 15 | 0.43 | 0.42 | 0.33 |
| 24 h rain >= 64.5 mm, next_25-48h | rain24 p50 | 35 | 0 | 0 | 0.00 | – | 0.00 |
| 24 h rain >= 64.5 mm, next_25-48h | rain24 p90 | 35 | 24 | 15 | 0.43 | 0.38 | 0.34 |
| 24 h rain >= 64.5 mm, next 1-24h | sum of hourly p50 | 35 | 0 | 0 | 0.00 | – | 0.00 |

## Notes

- Skill = 1 - MAE / MAE_ref against plain persistence and plain seasonal-naive (same hour, last observed day).
- Coverage = share of test targets inside the calibrated p10-p90 interval (target 0.80); raw = before calibration.
- Candidates are selected per variable and horizon band on the calibration slice (never on test).
- GRU ONNX vs torch max |diff| = 1.43e-06 (normalised units).
- flood_risk hazard is an antecedent-precipitation risk index, not a river-flow forecast.
