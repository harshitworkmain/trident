"""Empirical (split-conformal style) quantile adjustment, fitted on a calibration slice.

For each candidate, variable and horizon, each quantile q_k is shifted by the k-quantile of the
calibration residuals y - q_k, so that on the calibration slice P(y < q_k') ~= k. Offsets are
smoothed across neighbouring horizons (5-hour moving average) to avoid fitting noise.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from .predict import finalize

QS = np.array([0.1, 0.5, 0.9])


def fit(pred: np.ndarray, truth: np.ndarray, smooth: int = 5) -> np.ndarray:
    """pred (n, H, 3), truth (n, H) -> offsets (H, 3)."""
    resid = truth[:, :, None] - pred
    off = np.stack([np.nanquantile(resid[:, :, k], QS[k], axis=0) for k in range(3)], axis=1)
    off = np.nan_to_num(off)
    if smooth > 1 and off.shape[0] >= smooth:
        pad = np.pad(off, ((smooth // 2, smooth // 2), (0, 0)), mode='edge')
        off = np.stack([np.convolve(pad[:, k], np.ones(smooth) / smooth, mode='valid') for k in range(3)], axis=1)
    return off


def apply(var: str, pred: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    H = pred.shape[1]
    return finalize(var, pred + np.asarray(offsets)[None, :H, :])


def fit_all(raw: Dict[str, Dict[str, np.ndarray]], truth: Dict[str, np.ndarray]) -> Dict[str, Dict[str, list]]:
    return {c: {v: fit(p, truth[v]).round(5).tolist() for v, p in preds.items() if v in truth}
            for c, preds in raw.items()}
