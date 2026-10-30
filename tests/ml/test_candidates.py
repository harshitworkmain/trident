import numpy as np
import pytest

from src.ml.wearable.models.candidates import CANDIDATES
from src.ml.wearable.tournament.metrics import classification_metrics, false_alarms_per_hour, group_bootstrap_diff


def _toy(n=600, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, n)
    X = rng.normal(0, 1, (n, 6)) + y[:, None] * 1.5
    X[rng.random(X.shape) < 0.05] = np.nan               # missing values like real frames
    S = np.repeat(X[:, None, :3], 8, axis=1).astype(np.float32)  # (n, T=8, C=3)
    groups = np.repeat(np.arange(n // 30), 30)
    return X, S, y, groups


@pytest.mark.parametrize('name', list(CANDIDATES))
def test_candidate_learns_separable_problem(name):
    X, S, y, g = _toy()
    model = CANDIDATES[name](2, seed=1).fit(X[:450], S[:450], y[:450], g[:450])
    p = model.predict_proba(X[450:], S[450:])
    assert p.shape == (150, 2) and np.allclose(p.sum(axis=1), 1, atol=1e-5)
    assert classification_metrics(y[450:], p, ('a', 'b'))['macro_f1'] > 0.8
    assert model.size_bytes() > 0


def test_bootstrap_detects_clearly_better_model():
    X, S, y, g = _toy()
    good = np.column_stack([1 - y, y]).astype(float) * 0.9 + 0.05
    bad = np.full((len(y), 2), 0.5)
    bad[:, 1] += np.random.default_rng(0).normal(0, 0.1, len(y))
    bad[:, 0] = 1 - bad[:, 1]
    out = group_bootstrap_diff(y, good, bad, g, n=200)
    assert out['ci_low'] > 0


def test_false_alarm_events_merge_consecutive_windows():
    alarm = np.array([0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0], bool)
    rec = np.zeros(len(alarm), dtype=object)
    out = false_alarms_per_hour(alarm, rec, np.arange(len(alarm)), merge_gap_s=10.0)
    assert out['events'] == 2
