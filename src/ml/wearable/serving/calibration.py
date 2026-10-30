"""Applying the P4 calibrators at serving time (numpy only; fitting lives in final/train.py)."""

from __future__ import annotations

import numpy as np


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def apply_calibrator(cal: dict, proba: np.ndarray) -> np.ndarray:
    """Platt scaling on logit(p1) for binary heads; temperature scaling on log p otherwise."""
    if cal['method'] == 'platt':
        p1 = 1.0 / (1.0 + np.exp(-(cal['a'] * logit(proba[:, 1]) + cal['b'])))
        return np.column_stack([1 - p1, p1])
    z = np.log(np.clip(proba, 1e-7, 1)) / cal['T']
    z = np.exp(z - z.max(axis=1, keepdims=True))
    return z / z.sum(axis=1, keepdims=True)
