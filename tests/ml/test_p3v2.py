"""P3 v2 additions: ECG reference HR, HR-integrated beats, MiniRocket, Extra-Trees, hard negatives."""

import numpy as np
import pandas as pd

from src.ml.wearable.data.ecg import detect_rpeaks, match_peaks, reference_hr
from src.ml.wearable.data.loaders import beats_from_hr
from src.ml.wearable.heads.build import _hard_ends, capture24_fall_split
from src.ml.wearable.models.candidates import CANDIDATES, MiniRocketTransform, applicable


def _synthetic_ecg(hr_bpm=72.0, fs=700.0, seconds=60.0, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * fs)) / fs
    beats = np.arange(0.5, seconds - 0.5, 60.0 / hr_bpm)
    beats = beats + rng.normal(0, 0.01, len(beats))
    ecg = np.zeros_like(t)
    for b in beats:
        ecg += np.exp(-0.5 * ((t - b) / 0.012) ** 2)              # narrow R wave
        ecg += 0.25 * np.exp(-0.5 * ((t - b - 0.25) / 0.05) ** 2)  # broad T wave
    return ecg + rng.normal(0, 0.02, len(t)), beats


def test_rpeak_detector_finds_synthetic_beats():
    ecg, beats = _synthetic_ecg()
    det = detect_rpeaks(ecg, 700.0)
    m = match_peaks(det, beats, tol_s=0.03)
    assert m['sensitivity'] > 0.97 and m['ppv'] > 0.97


def test_reference_hr_matches_rate():
    beats = np.arange(0, 120, 0.8)                                  # 75 bpm
    hr = reference_hr(beats, 120.0)
    assert abs(np.nanmedian(hr) - 75.0) < 1e-6


def test_beats_from_hr_rate_and_gaps():
    t = np.arange(0, 60, 0.1)
    hr = np.full_like(t, 60.0)
    hr[(t > 20) & (t < 30)] = np.nan                                 # 10 s strap dropout
    beats = beats_from_hr(t, hr)
    assert 45 <= len(beats) <= 52
    assert not ((beats > 21) & (beats < 29)).any()


def test_minirocket_deterministic_and_shaped():
    rng = np.random.default_rng(1)
    A = rng.normal(size=(64, 3, 40)).astype(np.float32)
    f1 = MiniRocketTransform(500, seed=7).fit(A).transform(A)
    f2 = MiniRocketTransform(500, seed=7).fit(A).transform(A)
    assert np.array_equal(f1, f2)
    assert f1.shape[0] == 64 and f1.shape[1] >= 84 and np.all((f1 >= 0) & (f1 <= 1))


def test_new_candidates_fit_with_nans():
    rng = np.random.default_rng(2)
    n, T, C = 300, 20, 4
    X = rng.normal(size=(n, 6)); X[::5, 1] = np.nan
    S = rng.normal(size=(n, T, C)).astype(np.float32); S[::9, 3, 2] = np.nan
    y = rng.integers(0, 3, n)
    g = np.repeat(np.arange(30), 10)
    for name in ('extratrees', 'minirocket'):
        p = CANDIDATES[name](3, None, 0).fit(X, S, y, g).predict_proba(X, S)
        assert p.shape == (n, 3) and np.allclose(p.sum(axis=1), 1)
    assert not applicable('minirocket', 4) and applicable('minirocket', 8)


def test_hard_negative_ends_cover_spikes():
    f = pd.DataFrame({'imu_acc_max_g': np.ones(100), 'imu_acc_min_g': np.ones(100)})
    f.loc[50, 'imu_acc_max_g'] = 3.0
    ends = _hard_ends(f, 4, 'P001')
    assert ends == (50, 51, 52, 53)                                  # every 4-frame window containing frame 50


def test_capture24_split_is_stable_and_partial():
    pids = [f'P{i:03d}' for i in range(1, 152)]
    held = [p for p in pids if capture24_fall_split(p) == 'replay']
    assert held == [p for p in pids if capture24_fall_split(p) == 'replay']
    assert 35 <= len(held) <= 65
