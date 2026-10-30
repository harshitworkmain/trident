"""TRIDENT weather forecaster: multi-variable, 1-48 h probabilistic (p10/p50/p90) forecasts + hazards.

Training: `python -m src.ml.weather.train` (see train.py). Serving: `serving.WeatherService`
(numpy/pandas/lightgbm/onnxruntime only). Documentation: docs/WEATHER_MODEL.md.
"""
