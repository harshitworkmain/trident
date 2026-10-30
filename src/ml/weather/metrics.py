"""Forecast scores: point (MAE, RMSE), probabilistic (pinball, CRPS approximation, coverage), events."""

from __future__ import annotations

from typing import Dict

import numpy as np

QS = np.array([0.1, 0.5, 0.9])


def pinball(pred: np.ndarray, truth: np.ndarray) -> np.ndarray:
    """Mean pinball loss over the 3 quantiles, per horizon. pred (n, H, 3), truth (n, H) -> (H,)."""
    e = truth[:, :, None] - pred
    return np.nanmean(np.maximum(QS * e, (QS - 1) * e), axis=(0, 2))


def per_horizon(pred: np.ndarray, truth: np.ndarray) -> Dict[str, np.ndarray]:
    """All scores per horizon. CRPS ~ 2 x mean pinball over the quantile levels (3-point approximation)."""
    err = pred[:, :, 1] - truth
    pb = pinball(pred, truth)
    cover = ((truth >= pred[:, :, 0]) & (truth <= pred[:, :, 2])).astype(float)
    cover[np.isnan(truth)] = np.nan
    return {'mae': np.nanmean(np.abs(err), axis=0), 'rmse': np.sqrt(np.nanmean(err ** 2, axis=0)),
            'pinball': pb, 'crps_approx': 2 * pb, 'coverage_80': np.nanmean(cover, axis=0),
            'bias': np.nanmean(err, axis=0)}


def events(forecast: np.ndarray, observed: np.ndarray, thr: float) -> dict:
    """Contingency scores for `value >= thr`. CSI = hits / (hits + misses + false alarms)."""
    ok = np.isfinite(forecast) & np.isfinite(observed)
    f, o = forecast[ok] >= thr, observed[ok] >= thr
    hits, misses, fa = int((f & o).sum()), int((~f & o).sum()), int((f & ~o).sum())
    return {'threshold': thr, 'observed_events': hits + misses, 'forecast_events': hits + fa, 'hits': hits,
            'misses': misses, 'false_alarms': fa,
            'hit_rate': hits / (hits + misses) if hits + misses else None,
            'false_alarm_ratio': fa / (hits + fa) if hits + fa else None,
            'csi': hits / (hits + misses + fa) if hits + misses + fa else None}
