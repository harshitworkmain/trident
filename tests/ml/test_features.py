import math

import numpy as np
import pandas as pd
import pytest

from src.ml.wearable.data.recording import Recording as RawRecording
from src.ml.wearable.data.recording import Signal
from src.ml.wearable.emulator import emulate
from src.ml.wearable.features.engine import FeatureEngine, replay
from src.ml.wearable.features.frame_features import (CALIB_FRAMES, Calibrator, FEATURE_SETS, Window,
                                                     rr_stats, sample_entropy)
from src.ml.wearable.heads.augment import PPGNoise, ppg_like_beats
from src.ml.wearable.heads.build import Recording, label_fall
from src.ml.wearable.schema import FIELD_NAMES, parse_payload, to_payload


def _synthetic_session(seconds=150, seed=0):
    rng = np.random.default_rng(seed)
    acc = np.tile([0.0, 0.0, 1.0], (int(seconds * 32), 1)) + rng.normal(0, 0.02, (int(seconds * 32), 3))
    beats = np.cumsum(rng.normal(0.8, 0.04, int(seconds / 0.8)))
    t4 = np.arange(0, seconds, 0.25)
    rec = RawRecording('sim', 's1', 'tr', 'wrist', acc=Signal(acc, 32.0), beats_s=beats[beats < seconds],
                       eda=Signal(3.0 + 0.002 * t4 + rng.normal(0, 0.01, len(t4)), 4.0),
                       temp=Signal(33.0 + 0.0 * t4, 4.0))
    return emulate(rec)


def _assert_same(a: dict, b: dict):
    assert a.keys() == b.keys()
    for k in a:
        assert (math.isnan(a[k]) and math.isnan(b[k])) or math.isclose(a[k], b[k], rel_tol=1e-9, abs_tol=1e-12), k


@pytest.mark.parametrize('feature_set', list(FEATURE_SETS))
def test_offline_features_equal_online_json_path(feature_set):
    """Training features (DataFrame replay) == serving features (JSON -> parse -> engine)."""
    frames = _synthetic_session()
    values = frames[FIELD_NAMES].to_dict('records')
    rr = [list(x) for x in frames['rr_ms']]
    offline = {end: (tab, seq) for end, tab, seq in replay(values, rr, feature_set, stride=3)}

    engine = FeatureEngine([feature_set])
    for i, (v, r) in enumerate(zip(values, rr)):
        engine.push_frame(parse_payload(to_payload(v, r, seq=i)))
        if i in offline:
            tab, seq = engine.features(feature_set)
            _assert_same(offline[i][0], tab)
            np.testing.assert_allclose(offline[i][1], seq, equal_nan=True)
    assert offline, 'no windows emitted'


def test_calibration_uses_only_frames_seen_so_far_then_freezes():
    cal = Calibrator()
    for i in range(CALIB_FRAMES + 50):
        cal.update({'ppg_bpm': 60.0 if i < CALIB_FRAMES else 150.0, 'eda_us': 2.0, 'temp_skin_c': 33.0})
        if i == 9:
            assert cal.values()['calib_frames'] == 10
    assert cal.values()['bpm_base'] == 60.0 and cal.values()['calib_frames'] == CALIB_FRAMES


def test_rr_stats_known_values():
    rr = np.array([800.0, 900.0, 800.0, 900.0, 800.0])
    s = rr_stats(rr, 'x')
    assert math.isclose(s['x_mean'], 840.0)
    assert math.isclose(s['x_rmssd'], 100.0)
    assert s['x_pnn50'] == 1.0 and s['x_tpr'] == 1.0


def test_sample_entropy_regular_lower_than_random():
    rng = np.random.default_rng(1)
    regular = 800 + 20 * np.sin(np.arange(60) / 3)
    irregular = rng.uniform(500, 1100, 60)
    assert sample_entropy(regular) < sample_entropy(irregular)


def test_fall_labels_only_impact_windows_positive():
    frames = pd.DataFrame({'imu_acc_max_g': [1, 1, 1, 6, 1, 1, 1, 1.0]})
    fall = Recording('d', 's', 't', frames, context={'impact': 3})
    adl = Recording('d', 's', 't', frames)
    assert label_fall(fall, 0, 3) == 1 and label_fall(fall, 3, 6) == 1
    assert label_fall(fall, 4, 7) is None
    assert label_fall(adl, 4, 7) == 0


def test_ppg_noise_matches_requested_rates():
    rng = np.random.default_rng(3)
    beats = np.arange(0, 20000, 0.8)
    noise = PPGNoise(sigma_rr_ms=60.0, p_miss=0.05, p_extra=0.02)
    out = ppg_like_beats(beats, noise, rng)
    assert abs(len(out) / len(beats) - (1 - 0.05 + 0.02 * 0.95)) < 0.01
    rr_err = np.diff(beats + rng.normal(0, 0.06 / np.sqrt(2), len(beats))) - 0.8
    assert abs(np.std(rr_err) * 1000 - 60) < 3
