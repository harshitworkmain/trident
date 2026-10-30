# TRIDENT weather forecaster (v1.0.0)

Multi-variable, 1-48 h hourly, probabilistic (p10/p50/p90) forecasts for one site (Chennai by default),
with derived hazard flags. Replaces the legacy temperature-only LSTM (`src/ml/weather_prediction/`, since removed) and the fake "waterflow prediction" in `src/backend/main.py`.

Code: `src/ml/weather/` - `config/weather.yaml` (site, split, model, hazard settings), `data.py`, `features.py`,
`baselines.py`, `gbm.py`, `seqmodel.py` (the only torch user), `predict.py`, `calibration.py`, `backtest.py`,
`metrics.py`, `hazards.py`, `serving.py`, `train.py`. Tests: `tests/ml/test_weather.py` (no network).
Artefacts: `models/weather/1.0.0/` + `models/weather/registry.json` (chosen model per variable/band, sha256 of
every file). Full card with every table: `models/weather/1.0.0/card.md`; per-horizon numbers: `metrics.json`.

```
python -m src.ml.weather.data            # (re)download the Open-Meteo archive cache
python -m src.ml.weather.train           # full: backtest + calibration + selection + refit (~35 min, 3 threads)
python -m src.ml.weather.train --quick   # ~1 min smoke run -> models/weather/_quick/
python -m pytest -q tests/ml/test_weather.py
```

## 1. Data

| Use | Source | Notes |
|---|---|---|
| Training | https://archive-api.open-meteo.com/v1/archive | Free, keyless. ERA5/ERA5T reanalysis (0.25°), ~5-day lag. Yearly chunks, `timezone=GMT`, `wind_speed_unit=ms`: `temperature_2m, relative_humidity_2m, precipitation, wind_speed_10m, wind_gusts_10m, surface_pressure, dew_point_2m, cloud_cover`. Cache: `data/raw/weather/open_meteo_chennai_2015-01-01_2026-10-24.parquet` (103,560 h, no gaps). |
| Live (serving) | https://api.open-meteo.com/v1/forecast | Same variables, `past_days=N&forecast_days=1`, trimmed to the current hour. |
| Offline fallback | `data/raw/weather/chennai_historical.csv` | Meteostat hourly (UTC). `wspd`/`wpgt` km/h -> m/s; sea-level pressure reduced to surface (0.12 hPa/m x 16 m). |

All loaders return one schema (UTC hourly index; `temp, rh, rain, wind, gust, pres, dwpt, cloud`); gaps <= 6 h
are interpolated, missing rain is 0. `attrs['source']` is `open-meteo`, `offline-cache` or `offline-csv`.
Network failures never raise: training falls back to cache then CSV; serving likewise.

## 2. Method

**Targets.** Temperature (°C), relative humidity (%), precipitation (mm/h), 10 m wind speed (m/s), surface
pressure (hPa) at horizons 1-48 h, quantiles 0.1/0.5/0.9; plus 24 h rain accumulation for hours 1-24 and 25-48
(for IMD heavy-rain hazards). Smooth variables are modelled as change from the origin value.

**Features** (`features.py`; causal by construction, tested by truncation and future-poisoning): current values;
lags 1, 2, 3, 6, 12, 24, 48, 168 h; 6/24 h rolling mean/std; 24 h max/min temperature; dew-point depression;
pressure tendency 3 h / 24 h; rain accumulations 3/6/24/72 h, hours since rain, 7-day antecedent precipitation
index; local hour and day-of-year sin/cos (origin and target time); SW (Jun-Sep) / NE (Oct-Dec) monsoon flags
at target time; horizon; "same hour, last observed day" value of each variable. A forecast needs 192 h of history.

**Candidates.**
- `persistence`, `seasonal_naive` (same hour, last observed day) - intervals from their training-error quantiles per horizon.
- `climatology` - quantiles by local week-of-year x hour.
- `lgbm` - LightGBM quantile regression, direct multi-horizon: one booster per variable x horizon group
  {1-3, 4-6, 7-12, 13-24, 25-48} x quantile (horizon is a feature), 300 trees, 90k sampled (origin, horizon)
  rows per group: 75 boosters + 3 for 24 h rain (gzip text).
- `gru` - GRU(64) over the last 72 h of 8 weather + 4 calendar channels -> 48 x 5 x 3 quantiles (median +
  softplus widths: monotone by construction), pinball loss, 10 epochs on CPU (~7 min). Exported to ONNX
  (opset 17); onnxruntime vs torch max |diff| 1.4e-6.
- `blend` - average of `lgbm` and `gru` quantiles.

**Protocol** (`train.py`, `backtest.py`). Split by time: train 2015-01-09 .. 2025-04-24; calibration/selection
slice 2025-04-24 .. 2025-10-24 (1,448 origins); test 2025-10-24 .. 2026-10-24 (2,905 origins every 3 h, all
hours of day). Backtest models are fitted on the train period only (every training *target* precedes the
calibration slice); each origin uses only data up to itself. Backtest forecasts go through the same
`predict.Predictor` code path as serving (ONNX for the GRU), so what was evaluated is what is served.

**Calibration.** Per candidate x variable x horizon, each quantile is shifted by the matching quantile of its
calibration-slice residuals (empirical / split-conformal adjustment, smoothed over 5 neighbouring horizons),
then physical bounds (rain, wind >= 0; RH in [0, 100]) and sorting (p10 <= p50 <= p90).

**Selection.** Per variable x horizon band: lowest calibrated mean pinball loss on the *calibration* slice. The
test year is only scored. Production models are then refitted on the full history with the same settings;
calibration offsets and selection are carried over.

## 3. Backtest results (test year 2025-10-24 .. 2026-10-24, calibrated)

Skill = 1 - MAE / MAE(reference) vs plain persistence and plain seasonal-naive. Coverage = share of
observations inside p10-p90 (target 0.80); in brackets before calibration.

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

### Mean pinball loss by candidate and horizon band (bold = best on test; "chosen" was picked on the calibration slice)

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

### Heavy-rain events

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

**Who won where.** The learned models beat every baseline at every horizon for every variable. LightGBM alone
is the best single model in most bands; the LightGBM+GRU blend is marginally better at longer horizons for
temperature, RH, wind and pressure and was selected almost everywhere. The GRU alone never beats LightGBM
except for rain at 13-48 h, where all learned models are within ~1 %. Margins between lgbm and blend are small
(~1-3 % pinball). Seasonal-naive is a strong reference at 24/48 h (skill vs it only +0.07..+0.16).

## 4. Hazards (`hazards.py`)

`{type, level: watch|warning, from, to, reason}`; contiguous hours at the same level form one episode.
Thresholds in `config/weather.yaml`:
- `heat` - NOAA heat index (Rothfusz + NWS adjustments) on p50 T/RH. Watch: HI >= 41 °C or T >= 37 °C (IMD
  coastal) or p90 T >= 40 °C. Warning: HI >= 54 °C or T >= 40 °C (IMD plains).
- `heavy_rain` - hourly p50 >= 7.6 mm/h warning, p90 >= 7.6 watch; 24 h accumulation (LightGBM `rain24`):
  p90 >= 64.5 mm (IMD heavy) watch, p50 >= 64.5 or p90 >= 115.6 mm (IMD very heavy) warning.
- `high_wind` - p50 >= 17.2 m/s warning; p50 >= 10.8 or p90 >= 17.2 m/s watch.
- `flood_risk` - 7-day **antecedent precipitation index** (decay 0.85/day) over observed + forecast rain vs its
  training-climate percentiles (p97.5 = 92 mm watch, p99.5 = 168 mm warning). A soil-saturation **risk index,
  not a river-flow or inundation forecast** (there is no gauge data). Replaces the old fake "waterflow".

## 5. Serving (`serving.py`)

```python
from src.ml.weather.serving import WeatherService
svc = WeatherService.load()              # models/weather/registry.json
obs = svc.fetch_observations(hours=168)  # returns >= 192 rows; attrs['source']
fc  = svc.forecast(obs, hours=48)        # {site, generated_at, model_version, issued_from, source, horizon[], hazards[]}
svc.current(obs); svc.model_card()
```
Runtime dependencies: numpy, pandas, lightgbm, onnxruntime, pyyaml, httpx (live fetch only); torch is never
imported (tested). `load()` ~4 s (decompress + parse 78 boosters), ~250 MB RSS: load once at startup and share.
`forecast()` ~0.1-0.2 s. Times are UTC (`...Z`), starting one hour after the last observation (`issued_from`).
If an input variable is missing, that variable falls back to calibrated climatology.

## 6. Limitations

- **Reanalysis, not station data.** ERA5 at 0.25° smooths local extremes (convective rain peaks, sea-breeze
  wind). Live inputs come from Open-Meteo's forecast-model analysis, a different product: expect some
  distribution shift. The Meteostat fallback (airport station) differs more.
- **Statistical short-range model, not NWP.** Beyond ~12 h, skill over seasonal-naive is modest (temperature
  +0.07..+0.10 at 24-48 h). For operations, adding Open-Meteo's NWP forecast (`forecast_days=2`) as a feature
  or candidate is the natural v2.
- **Heavy hourly rain is essentially not predictable here.** p50 never reaches 7.6 mm/h; p90 catches some
  events only at 1-3 h (CSI 0.15). 24 h accumulation at p90: CSI ~0.33 (15/35 heavy-rain origins hit, FAR ~0.4).
  Test-year events come from a handful of NE-monsoon / cyclone days, so these statistics are noisy.
- **Calibration does not fully transfer across seasons.** The calibration slice is Apr-Oct; the test year is
  all seasons. Calibrated coverage: temperature, RH, rain 0.76-0.83; wind 0.71-0.77 and 48 h pressure
  0.72-0.74 are under-covered (for wind, calibration made it worse than raw ~0.80). Season-conditional offsets
  or a rolling 12-month calibration window are the obvious fix.
- Rain coverage counts dry hours with p10 = 0 as covered (flattering); rain MAE skill largely reflects
  correctly predicting "no rain".
- Heavy hourly rain is more frequent in the archive after 2021 (upstream data non-stationarity).
- Single site; change `site` in the YAML and retrain for another location.
