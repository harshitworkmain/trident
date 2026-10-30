"""Rolling-origin backtest: score every candidate on held-out origins, select per variable x band.

Protocol (see train.py for the split): all models are fitted on data strictly before the
calibration slice; forecasts are issued from origins every `origin_stride_h` hours across the
calibration slice (used for quantile calibration and model selection) and the final 12 months
(used only for reporting). Each origin sees only data up to itself; its 1-48 h targets are
scored against observations. Selection never looks at the test window.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from . import calibration, metrics
from .baselines import _point
from .config import TARGETS
from .features import rain24_target
from .gbm import RAIN24_HORIZONS
from .predict import Predictor, Prepared


def truth(prep: Prepared, pos: np.ndarray, H: int) -> Dict[str, np.ndarray]:
    fut = pos[:, None] + np.arange(1, H + 1)[None, :]
    out = {v: prep.values[v][fut].astype(np.float64) for v in TARGETS}
    hs = np.array(RAIN24_HORIZONS)
    out['rain24'] = rain24_target(prep.values, np.repeat(pos, 2), np.tile(hs, len(pos))).reshape(len(pos), 2)
    return out


def bands(groups: List[List[int]]) -> Dict[str, np.ndarray]:
    return {f'{g[0]}-{g[1]}': np.arange(g[0] - 1, g[1]) for g in groups}


def calibrate(raw: dict, offsets: dict) -> dict:
    out = {}
    for c, preds in raw.items():
        out[c] = {v: calibration.apply('rain' if v == 'rain24' else v, p, offsets[c][v])
                  for v, p in preds.items() if v in offsets.get(c, {})}
    return out


def score(preds: dict, tr: Dict[str, np.ndarray]) -> dict:
    """{cand: {var: {metric: [per-horizon list]}}}"""
    return {c: {v: {k: m.tolist() for k, m in metrics.per_horizon(p, tr[v]).items()}
                for v, p in pv.items() if v in TARGETS} for c, pv in preds.items()}


def select(scores: dict, groups: List[List[int]]) -> Dict[str, Dict[str, str]]:
    """Per variable and horizon band, the candidate with the lowest mean pinball loss."""
    chosen = {}
    for v in TARGETS:
        chosen[v] = {}
        for b, idx in bands(groups).items():
            best = min(scores, key=lambda c: np.mean(np.asarray(scores[c][v]['pinball'])[idx]))
            chosen[v][b] = best
    return chosen


def compose(preds: dict, chosen: dict, groups: List[List[int]], H: int) -> Dict[str, np.ndarray]:
    out = {}
    for v in TARGETS:
        n = next(iter(preds.values()))[v].shape[0]
        arr = np.full((n, H, 3), np.nan)
        for b, idx in bands(groups).items():
            idx = idx[idx < H]
            arr[:, idx] = preds[chosen[v][b]][v][:, idx]
        out[v] = arr
    return out


def point_skill(pred_mae: np.ndarray, prep: Prepared, pos: np.ndarray, tr: dict, var: str, H: int) -> dict:
    """Skill = 1 - MAE / MAE_ref against the *plain* persistence and seasonal-naive point forecasts."""
    out = {}
    for ref in ('persistence', 'seasonal_naive'):
        mae_ref = np.nanmean(np.abs(_point(ref, prep.values[var], pos, H) - tr[var]), axis=0)
        out[f'mae_{ref}'] = mae_ref.tolist()
        out[f'skill_vs_{ref}'] = (1 - pred_mae / np.where(mae_ref > 0, mae_ref, np.nan)).tolist()
    return out


def rain_events(pred: np.ndarray, r24: np.ndarray, tr: dict, groups: List[List[int]], thr_h: float,
                thr_24: float) -> dict:
    """Heavy-rain contingency scores: hourly (per band) on p50 and p90, 24 h accumulation on p50 / p90."""
    out = {'hourly': {}, 'acc24': {}}
    for b, idx in bands(groups).items():
        idx = idx[idx < pred.shape[1]]
        out['hourly'][b] = {q: metrics.events(pred[:, idx, k].ravel(), tr['rain'][:, idx].ravel(), thr_h)
                            for q, k in (('p50', 1), ('p90', 2))}
    for j, h in enumerate(RAIN24_HORIZONS):
        out['acc24'][f'next_{h - 23}-{h}h'] = {q: metrics.events(r24[:, j, k], tr['rain24'][:, j], thr_24)
                                                for q, k in (('p50', 1), ('p90', 2))}
    return out


def forecast_origins(predictor: Predictor, prep: Prepared, pos: np.ndarray, H: int):
    """(raw candidate forecasts, raw LightGBM 24 h-accumulation quantiles (n, 2, 3) or None)."""
    raw = predictor.predict(prep, pos, H)
    r24 = raw['lgbm'].pop('rain24', None) if 'lgbm' in raw else None
    return raw, r24
