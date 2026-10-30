"""Evaluation metrics, group bootstrap and false-alarm rate for the tournament."""

from __future__ import annotations

import math
from typing import Callable, Dict, Sequence

import numpy as np
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score, f1_score,
                             log_loss, recall_score, roc_auc_score)

from ..schema import FRAME_PERIOD_S


def ece(y: np.ndarray, proba: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error of the top-label probability."""
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(total)


def classification_metrics(y: np.ndarray, proba: np.ndarray, classes: Sequence[str]) -> Dict[str, float]:
    k = len(classes)
    proba = np.clip(np.asarray(proba, dtype=np.float64), 1e-7, 1.0)
    proba = proba / proba.sum(axis=1, keepdims=True)
    pred = proba.argmax(axis=1)
    out = {
        'macro_f1': float(f1_score(y, pred, average='macro', labels=list(range(k)), zero_division=0)),
        'balanced_accuracy': float(balanced_accuracy_score(y, pred)),
        'accuracy': float(accuracy_score(y, pred)),
        'log_loss': float(log_loss(y, proba, labels=list(range(k)))),
        'ece': ece(y, proba),
    }
    per_class = f1_score(y, pred, average=None, labels=list(range(k)), zero_division=0)
    out.update({f'f1_{c}': float(v) for c, v in zip(classes, per_class)})
    if k == 2 and len(np.unique(y)) == 2:
        out.update({
            'auroc': float(roc_auc_score(y, proba[:, 1])),
            'auprc': float(average_precision_score(y, proba[:, 1])),
            'sensitivity': float(recall_score(y, pred, pos_label=1, zero_division=0)),
            'specificity': float(recall_score(y, pred, pos_label=0, zero_division=0)),
        })
    elif k > 2 and len(np.unique(y)) == k:
        out['auroc'] = float(roc_auc_score(y, proba, multi_class='ovr', average='macro'))
    return out


METRIC_FUNCS: Dict[str, Callable[[np.ndarray, np.ndarray], float]] = {
    'macro_f1': lambda y, p: f1_score(y, p.argmax(axis=1), average='macro',
                                      labels=list(range(p.shape[1])), zero_division=0),
}


def group_bootstrap_diff(y, pa, pb, groups, metric: str = 'macro_f1', n: int = 1000, seed: int = 42) -> Dict[str, float]:
    """Bootstrap (resampling whole subjects) of metric(A) - metric(B) on out-of-fold predictions."""
    fn = METRIC_FUNCS[metric]
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in uniq}
    diffs = []
    for _ in range(n):
        idx = np.concatenate([index[g] for g in rng.choice(uniq, size=len(uniq), replace=True)])
        if len(np.unique(y[idx])) < 2:
            continue
        diffs.append(fn(y[idx], pa[idx]) - fn(y[idx], pb[idx]))
    d = np.array(diffs)
    return {'mean_diff': float(d.mean()), 'ci_low': float(np.percentile(d, 2.5)),
            'ci_high': float(np.percentile(d, 97.5)), 'p_b_better': float(np.mean(d < 0)), 'n_boot': len(d)}


def false_alarms_per_hour(alarm: np.ndarray, recording: np.ndarray, end_frame: np.ndarray,
                          merge_gap_s: float = 10.0) -> Dict[str, float]:
    """Alarm events per hour over negative-only daily-life replay (consecutive alarms merged)."""
    gap_frames = int(round(merge_gap_s / FRAME_PERIOD_S))
    events, frames = 0, 0
    for rec in np.unique(recording):
        m = recording == rec
        order = np.argsort(end_frame[m])
        f, a = end_frame[m][order], alarm[m][order]
        frames += int(f.max() - f.min() + 1) if len(f) else 0
        last = -10 ** 9
        for fi, ai in zip(f, a):
            if ai:
                if fi - last > gap_frames:
                    events += 1
                last = fi
    hours = frames * FRAME_PERIOD_S / 3600.0
    return {'events': events, 'hours': round(hours, 2),
            'false_alarms_per_hour': events / hours if hours else math.nan,
            'false_alarms_per_8h': 8 * events / hours if hours else math.nan}
