"""Paths and configuration for the weather forecaster (site, split, model and hazard settings)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(os.environ.get('TRIDENT_DATA_ROOT', PROJECT_ROOT / 'data'))
RAW_DIR = DATA_ROOT / 'raw' / 'weather'
MODELS_DIR = PROJECT_ROOT / 'models' / 'weather'
REGISTRY_PATH = MODELS_DIR / 'registry.json'
CONFIG_PATH = Path(os.environ.get('TRIDENT_WEATHER_CONFIG', Path(__file__).resolve().parent / 'config' / 'weather.yaml'))

# Forecast targets: internal name -> (payload key, physical lower bound, upper bound).
TARGETS = {
    'temp': ('temp_c', None, None),
    'rh': ('rh', 0.0, 100.0),
    'rain': ('rain_mm', 0.0, None),
    'wind': ('wind_ms', 0.0, None),
    'pres': ('pressure_hpa', None, None),
}
# Smooth variables are modelled as a change from the value at the origin; rain is not
# (its "level" carries no information a few hours ahead, and the change is as skewed as the level).
DELTA_TARGETS = ('temp', 'rh', 'wind', 'pres')


@lru_cache(maxsize=4)
def load_config(path: str | None = None) -> dict:
    with open(path or CONFIG_PATH, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def site(cfg: dict | None = None) -> dict:
    s = (cfg or load_config())['site']
    return {'name': s['name'], 'lat': s['lat'], 'lon': s['lon'], 'timezone': s['timezone']}


def clip_bounds(var: str, values):
    """Clip an array to the physical range of `var` (rain >= 0, 0 <= rh <= 100, wind >= 0)."""
    import numpy as np
    _, lo, hi = TARGETS[var]
    return np.clip(values, lo if lo is not None else -np.inf, hi if hi is not None else np.inf)
