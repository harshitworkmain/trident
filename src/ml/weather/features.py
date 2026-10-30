"""Leakage-free features for direct multi-horizon forecasting.

A training/serving row is an (origin t, horizon h) pair. Origin features use only values at
times <= t (lags, trailing windows); target-time features are pure calendar functions of t + h
(known in advance), plus the "same hour, last known day" value x(t + h - 24*ceil(h/24)), which
is always <= t. Nothing here ever reads a row after the origin.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .config import DELTA_TARGETS, TARGETS

LAGS = (1, 2, 3, 6, 12, 24, 48, 168)
ROLL = (6, 24)
RAIN_ACC = (3, 6, 24, 72)
MIN_HISTORY_H = 192          # longest lag (168 h) + margin so every feature is defined at the origin
API_DECAY_PER_DAY = 0.85
SEQ_CHANNELS = ['temp', 'rh', 'rain', 'wind', 'pres', 'dwpt', 'cloud', 'gust']
SW_MONSOON = (152, 274)      # ~1 Jun .. 30 Sep (day of year)
NE_MONSOON_START = 274       # ~1 Oct .. 31 Dec - Chennai's main rain season


def local_calendar(index: pd.DatetimeIndex, tz: str) -> tuple[np.ndarray, np.ndarray]:
    loc = index.tz_convert(tz)
    hod = (loc.hour + loc.minute / 60.0).to_numpy(dtype=np.float64)
    doy = (loc.dayofyear - 1 + hod / 24.0).to_numpy(dtype=np.float64)
    return hod, doy


def antecedent_precip_index(rain: np.ndarray, decay_per_day: float = API_DECAY_PER_DAY,
                             window_h: int = 168) -> np.ndarray:
    """API_t = sum_j k^j * rain_{t-j} over a finite 7-day window, hourly decay k = decay_per_day ** (1/24).

    The window is finite so the value computed at serving time from a week of observations is
    identical to the one seen in training (an infinite recursion would depend on history length).
    """
    k = decay_per_day ** (1.0 / 24.0)
    w = k ** np.arange(window_h)
    r = np.nan_to_num(np.asarray(rain, dtype=np.float64), nan=0.0)
    return np.convolve(r, w)[:len(r)]


def origin_features(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    """One row per hour of `df`, describing the state known at that hour (causal)."""
    f: Dict[str, np.ndarray] = {}
    for c in ['temp', 'rh', 'rain', 'wind', 'pres', 'dwpt', 'cloud', 'gust']:
        f[f'{c}_0'] = df[c].to_numpy()
    for v in TARGETS:
        s = df[v]
        for lag in LAGS:
            f[f'{v}_lag{lag}'] = s.shift(lag).to_numpy()
        if v != 'rain':
            for w in ROLL:
                f[f'{v}_mean{w}'] = s.rolling(w, min_periods=w // 2).mean().to_numpy()
                f[f'{v}_std{w}'] = s.rolling(w, min_periods=w // 2).std().to_numpy()
    f['temp_max24'] = df['temp'].rolling(24, min_periods=12).max().to_numpy()
    f['temp_min24'] = df['temp'].rolling(24, min_periods=12).min().to_numpy()
    f['dewpt_depression'] = (df['temp'] - df['dwpt']).to_numpy()
    f['pres_tend3'] = (df['pres'] - df['pres'].shift(3)).to_numpy()
    f['pres_tend24'] = (df['pres'] - df['pres'].shift(24)).to_numpy()
    f['temp_tend24'] = (df['temp'] - df['temp'].shift(24)).to_numpy()
    for w in RAIN_ACC:
        f[f'rain_acc{w}'] = df['rain'].rolling(w, min_periods=1).sum().to_numpy()
    wet = (df['rain'] >= 0.1).to_numpy()
    last_wet = pd.Series(np.where(wet, np.arange(len(df)), np.nan)).ffill().to_numpy()
    f['hours_since_rain'] = np.minimum(np.arange(len(df)) - np.nan_to_num(last_wet, nan=-1e9), 168.0)
    f['api'] = antecedent_precip_index(df['rain'].to_numpy())
    hod, doy = local_calendar(df.index, tz)
    f['hod'], f['doy'] = hod, doy
    f['hod_sin'], f['hod_cos'] = np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24)
    f['doy_sin'], f['doy_cos'] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    return pd.DataFrame(f, index=df.index).astype('float32')


def row_features(F: pd.DataFrame, values: Dict[str, np.ndarray], pos: np.ndarray, h: np.ndarray) -> pd.DataFrame:
    """Assemble (origin, horizon) rows: origin features at `pos` + target-time calendar/seasonal-naive."""
    pos, h = np.asarray(pos, dtype=np.int64), np.asarray(h, dtype=np.int64)
    X = F.iloc[pos].reset_index(drop=True)
    hod_t = (X['hod'].to_numpy() + h) % 24
    doy_t = (X['doy'].to_numpy() + h / 24.0) % 365.25
    X['h'] = h.astype('float32')
    X['t_hod_sin'], X['t_hod_cos'] = np.sin(2 * np.pi * hod_t / 24), np.cos(2 * np.pi * hod_t / 24)
    X['t_doy_sin'], X['t_doy_cos'] = np.sin(2 * np.pi * doy_t / 365.25), np.cos(2 * np.pi * doy_t / 365.25)
    X['sw_monsoon'] = ((doy_t >= SW_MONSOON[0]) & (doy_t < SW_MONSOON[1])).astype('float32')
    X['ne_monsoon'] = (doy_t >= NE_MONSOON_START).astype('float32')
    back = pos + h - 24 * np.ceil(h / 24).astype(np.int64)      # always <= pos: no look-ahead
    ok = back >= 0
    for v in TARGETS:
        x = np.full(len(pos), np.nan, dtype=np.float32)
        x[ok] = values[v][back[ok]]
        X[f'{v}_samehour'] = x
    return X.drop(columns=['hod', 'doy']).astype('float32')


def feature_names(F: pd.DataFrame) -> List[str]:
    probe = row_features(F.iloc[:1], {v: np.zeros(1, np.float32) for v in TARGETS}, np.array([0]), np.array([1]))
    return list(probe.columns)


def target(values: Dict[str, np.ndarray], var: str, pos: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Modelled target: change from the origin for smooth variables, the level for rain."""
    y = values[var][pos + h].astype(np.float64)
    return y - values[var][pos] if var in DELTA_TARGETS else y


def untarget(values: Dict[str, np.ndarray], var: str, pos: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """Inverse of `target`; `pred` is (n, ...) and broadcast against the origin value."""
    if var not in DELTA_TARGETS:
        return pred
    base = values[var][pos].astype(np.float64)
    return pred + base.reshape((-1,) + (1,) * (pred.ndim - 1))


def rain24_target(values: Dict[str, np.ndarray], pos: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Rain accumulated over (t + h - 24, t + h] - the IMD 24 h heavy-rain quantity."""
    c = np.concatenate([[0.0], np.cumsum(values['rain'].astype(np.float64))])
    return c[pos + h + 1] - c[pos + h - 23]


def seq_inputs(df: pd.DataFrame, tz: str) -> np.ndarray:
    """Per-hour input channels for the sequence model (unscaled; rain as log1p)."""
    x = df[SEQ_CHANNELS].to_numpy(dtype=np.float32).copy()
    x[:, SEQ_CHANNELS.index('rain')] = np.log1p(x[:, SEQ_CHANNELS.index('rain')])
    hod, doy = local_calendar(df.index, tz)
    cal = np.column_stack([np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24),
                           np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)]).astype(np.float32)
    return np.concatenate([x, cal], axis=1)
