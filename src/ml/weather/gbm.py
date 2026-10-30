"""LightGBM direct multi-horizon quantile forecaster.

One booster per (variable, horizon group, quantile); horizon is a feature inside a group, so
5 variables x 5 groups x 3 quantiles = 75 boosters (+3 for 24 h rain accumulation) instead of
48 x 15. Each group trains on a random sample of (origin, horizon) pairs whose *target time*
lies inside the training period, which bounds memory and time regardless of history length.
"""

from __future__ import annotations

import gzip
import logging
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd

from .config import TARGETS
from .features import rain24_target, row_features, target, untarget

logger = logging.getLogger('weather.gbm')
QS = (0.1, 0.5, 0.9)
RAIN24_HORIZONS = (24, 48)


def model_name(var: str, group: Sequence[int], q: float) -> str:
    return f'{var}_h{group[0]}-{group[1]}_q{int(round(q * 100)):02d}.txt.gz'


def save_booster(b: lgb.Booster, path: Path) -> None:
    # gzip: LightGBM text models compress ~5x, keeping models/weather small enough for git
    path.write_bytes(gzip.compress(b.model_to_string().encode('utf-8'), compresslevel=9, mtime=0))


def load_booster(path: Path) -> lgb.Booster:
    return lgb.Booster(model_str=gzip.decompress(path.read_bytes()).decode('utf-8'))


def _sample(train_pos: np.ndarray, last_target: int, hs: np.ndarray, n: int, rng) -> Tuple[np.ndarray, np.ndarray]:
    h = rng.choice(hs, size=n)
    pos = rng.choice(train_pos, size=n)
    ok = pos + h <= last_target                    # target time must be inside the training period
    return pos[ok], h[ok]


def fit(F: pd.DataFrame, values: Dict[str, np.ndarray], train_pos: np.ndarray, last_target: int,
        groups: List[List[int]], rows_per_group: int, params: dict, out_dir: Path, seed: int = 0) -> dict:
    """Train and save every booster; returns {'files': [...], 'features': [...], 'seconds': float}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    p = dict(params)
    n_iter = p.pop('num_iterations', 300)
    files, feats, t0 = [], None, time.perf_counter()
    jobs = [(tuple(g), np.arange(g[0], g[1] + 1), list(TARGETS)) for g in groups]
    jobs.append(((RAIN24_HORIZONS[0], RAIN24_HORIZONS[1]), np.array(RAIN24_HORIZONS), ['rain24']))
    for g, hs, variables in jobs:
        pos, h = _sample(train_pos, last_target, hs, rows_per_group, rng)
        X = row_features(F, values, pos, h)
        feats = list(X.columns)
        for var in variables:
            y = rain24_target(values, pos, h) if var == 'rain24' else target(values, var, pos, h)
            keep = np.isfinite(y)
            ds = lgb.Dataset(X[keep], y[keep], free_raw_data=True)
            for q in QS:
                b = lgb.train({**p, 'objective': 'quantile', 'alpha': q, 'seed': seed}, ds, num_boost_round=n_iter)
                name = model_name(var, g, q)
                save_booster(b, out_dir / name)
                files.append(name)
            logger.info('lgbm %s h%s-%s: %d rows (%.0fs elapsed)', var, g[0], g[1], keep.sum(), time.perf_counter() - t0)
        del X
    return {'files': files, 'features': feats, 'seconds': time.perf_counter() - t0}


class GBMForecaster:
    """Loads the boosters of one model directory and predicts all variables for many origins."""

    def __init__(self, model_dir: Path, groups: List[List[int]], features: List[str]):
        self.groups = [tuple(g) for g in groups]
        self.features = features
        self.boosters = {}
        for var in TARGETS:
            for g in self.groups:
                for q in QS:
                    self.boosters[(var, g, q)] = load_booster(model_dir / model_name(var, g, q))
        r24 = (RAIN24_HORIZONS[0], RAIN24_HORIZONS[1])
        for q in QS:
            path = model_dir / model_name('rain24', r24, q)
            if path.exists():
                self.boosters[('rain24', r24, q)] = load_booster(path)

    def predict(self, F: pd.DataFrame, values: Dict[str, np.ndarray], pos: np.ndarray, H: int) -> Dict[str, np.ndarray]:
        """{var: (n, H, 3)} raw quantile forecasts in physical units; plus 'rain24': (n, 2, 3) for h=24/48."""
        pos = np.asarray(pos, dtype=np.int64)
        n = len(pos)
        out = {v: np.full((n, H, 3), np.nan) for v in TARGETS}
        for g in self.groups:
            hs = np.arange(g[0], min(g[1], H) + 1)
            if len(hs) == 0:
                continue
            pp, hh = np.repeat(pos, len(hs)), np.tile(hs, n)
            X = row_features(F, values, pp, hh)[self.features].to_numpy(dtype=np.float32)
            for var in TARGETS:
                pred = np.column_stack([self.boosters[(var, g, q)].predict(X, num_threads=3) for q in QS])
                pred = untarget(values, var, pp, pred).reshape(n, len(hs), 3)
                out[var][:, hs - 1, :] = pred
        r24 = (RAIN24_HORIZONS[0], RAIN24_HORIZONS[1])
        if ('rain24', r24, 0.5) in self.boosters:
            hs = np.array(RAIN24_HORIZONS)
            pp, hh = np.repeat(pos, len(hs)), np.tile(hs, n)
            X = row_features(F, values, pp, hh)[self.features].to_numpy(dtype=np.float32)
            out['rain24'] = np.column_stack([self.boosters[('rain24', r24, q)].predict(X, num_threads=3)
                                             for q in QS]).reshape(n, len(hs), 3)
        return out
