"""Reference forecasters every learned model must beat.

- persistence    : x(t+h) = x(t)
- seasonal_naive : x(t+h) = x(t + h - 24*ceil(h/24))  (same hour, last observed day)
- climatology    : quantiles of x by (local week of year, local hour) over the training period

Persistence and seasonal-naive get probabilistic intervals from the empirical quantiles of
their own training-period errors per horizon, so pinball loss and coverage are comparable.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from .config import TARGETS

QS = (0.1, 0.5, 0.9)


def _back(pos: np.ndarray, H: int) -> np.ndarray:
    h = np.arange(1, H + 1)
    return pos[:, None] + h[None, :] - 24 * np.ceil(h / 24).astype(np.int64)[None, :]


def _point(kind: str, x: np.ndarray, pos: np.ndarray, H: int) -> np.ndarray:
    if kind == 'persistence':
        return np.repeat(x[pos][:, None], H, axis=1).astype(np.float64)
    return x[_back(pos, H)].astype(np.float64)


def fit(values: Dict[str, np.ndarray], F: pd.DataFrame, train_pos: np.ndarray, H: int) -> dict:
    """Residual-quantile tables (persistence, seasonal-naive) and climatology table from train rows only."""
    pos = train_pos[(train_pos >= 24) & (train_pos + H < len(F))]
    week = np.minimum((F['doy'].to_numpy()[pos] // 7).astype(int), 52)
    hour = np.floor(F['hod'].to_numpy()[pos]).astype(int) % 24
    out = {'H': H, 'quantiles': list(QS), 'persistence': {}, 'seasonal_naive': {}, 'climatology': {}}
    for v in TARGETS:
        x = values[v]
        truth = x[pos[:, None] + np.arange(1, H + 1)[None, :]].astype(np.float64)
        for kind in ('persistence', 'seasonal_naive'):
            err = truth - _point(kind, x, pos, H)
            out[kind][v] = np.nanquantile(err, QS, axis=0).T.round(4).tolist()      # (H, 3)
        obs = pd.DataFrame({'w': week, 'hr': hour, 'x': x[pos]})
        tab = obs.groupby(['w', 'hr'])['x'].quantile(list(QS)).unstack()
        full = np.full((53, 24, 3), np.nan)
        for (w, hr), row in tab.iterrows():
            full[int(w), int(hr)] = row.to_numpy()
        # weeks with few hours (week 52 = the last 1-2 days) borrow from the hour's overall quantiles
        fallback = obs.groupby('hr')['x'].quantile(list(QS)).unstack().reindex(range(24)).to_numpy()
        full = np.where(np.isnan(full), fallback[None, :, :], full)
        out['climatology'][v] = full.round(4).tolist()
    return out


def predict(tables: dict, kind: str, values: Dict[str, np.ndarray], F: pd.DataFrame, pos: np.ndarray,
            H: int) -> Dict[str, np.ndarray]:
    """{var: (n, H, 3)} raw (uncalibrated, unclipped) quantile forecasts."""
    pos = np.asarray(pos, dtype=np.int64)
    out = {}
    if kind == 'climatology':
        h = np.arange(1, H + 1)
        hod_t = (F['hod'].to_numpy()[pos][:, None] + h[None, :]) % 24
        doy_t = (F['doy'].to_numpy()[pos][:, None] + h[None, :] / 24.0) % 365.25
        wk, hr = np.minimum((doy_t // 7).astype(int), 52), np.floor(hod_t).astype(int) % 24
        for v in TARGETS:
            out[v] = np.asarray(tables['climatology'][v])[wk, hr]
        return out
    for v in TARGETS:
        resid = np.asarray(tables[kind][v])[:H]                                    # (H, 3)
        out[v] = _point(kind, values[v], pos, H)[:, :, None] + resid[None, :, :]
    return out
