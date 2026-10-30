"""Window features over schema-v2 frames, shared by offline training and online serving.

A `Window` is the last T frames of one device (or one emulated recording) plus a running
per-session calibration. Every head declares a feature set: window length T, a tabular
feature function and a sequence function (input for the 1D-CNN candidate).
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Callable, Dict, List

import numpy as np

from ..schema import FRAME_PERIOD_S

CALIB_FRAMES = 80          # first 120 s of a session define the personal baseline
EPS = 1e-6


# ─── window + calibration ────────────────────────────────────────────────────

class Calibrator:
    """Personal baseline from the first CALIB_FRAMES frames of a session, then frozen.

    Early in a session the baseline uses whatever frames have been seen so far, which is
    exactly what the server can know at that moment (no look-ahead offline either).
    """

    def __init__(self) -> None:
        self.n = 0
        self._bpm: List[float] = []
        self._eda: List[float] = []
        self._temp: List[float] = []

    def update(self, values: Dict[str, float]) -> None:
        if self.n >= CALIB_FRAMES:
            return
        self.n += 1
        self._bpm.append(values.get('ppg_bpm', math.nan))
        self._eda.append(values.get('eda_us', math.nan))
        self._temp.append(values.get('temp_skin_c', math.nan))

    def values(self) -> Dict[str, float]:
        return {'bpm_base': _nanmedian(self._bpm), 'eda_base': _nanmean(self._eda),
                'temp_base': _nanmedian(self._temp), 'calib_frames': float(self.n)}


@dataclass
class Window:
    v: Dict[str, np.ndarray]      # field -> (T,) float array
    rr: List[List[float]]         # per-frame RR intervals (ms)
    calib: Dict[str, float]

    @property
    def T(self) -> int:
        return len(next(iter(self.v.values())))

    def rr_flat(self) -> np.ndarray:
        return np.array([r for frame in self.rr for r in frame], dtype=np.float64)


# ─── nan-safe numerics ───────────────────────────────────────────────────────

def _finite(x) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return x[np.isfinite(x)]


def _nanmean(x) -> float:
    f = _finite(x)
    return float(f.mean()) if len(f) else math.nan


def _nanmedian(x) -> float:
    f = _finite(x)
    return float(np.median(f)) if len(f) else math.nan


def _nanstd(x) -> float:
    f = _finite(x)
    return float(f.std()) if len(f) > 1 else math.nan


def _nanmax(x) -> float:
    f = _finite(x)
    return float(f.max()) if len(f) else math.nan


def _nanmin(x) -> float:
    f = _finite(x)
    return float(f.min()) if len(f) else math.nan


def _slope_per_s(x) -> float:
    x = np.asarray(x, dtype=np.float64)
    t = np.arange(len(x)) * FRAME_PERIOD_S
    ok = np.isfinite(x)
    if ok.sum() < 3:
        return math.nan
    return float(np.polyfit(t[ok], x[ok], 1)[0])


def _rel(x: float, base: float) -> float:
    if not (math.isfinite(x) and math.isfinite(base)) or abs(base) < EPS:
        return math.nan
    return x / base - 1.0


# ─── RR / HRV ────────────────────────────────────────────────────────────────

def clean_rr(rr: np.ndarray) -> np.ndarray:
    """Drop intervals >30 % from the local median (ectopic beats / PPG artefacts)."""
    if len(rr) < 3:
        return rr
    med = np.median(rr)
    return rr[np.abs(rr - med) <= 0.3 * med]


def sample_entropy(x: np.ndarray, m: int = 2, r_frac: float = 0.2) -> float:
    n = len(x)
    if n < m + 3:
        return math.nan
    r = r_frac * np.std(x)
    if r <= 0:
        return 0.0

    def count(mm: int) -> int:
        emb = np.lib.stride_tricks.sliding_window_view(x, mm)[: n - m]
        d = np.max(np.abs(emb[:, None, :] - emb[None, :, :]), axis=2)
        return int((d <= r).sum() - len(emb))

    b, a = count(m), count(m + 1)
    if a == 0 or b == 0:
        return math.nan
    return float(-np.log(a / b))


def rr_stats(rr: np.ndarray, prefix: str) -> Dict[str, float]:
    keys = ['n', 'mean', 'sdnn', 'rmssd', 'pnn50', 'cv', 'sd1', 'sd2', 'sd1_sd2', 'tpr']
    if len(rr) < 4:
        out = {f'{prefix}_{k}': math.nan for k in keys}
        out[f'{prefix}_n'] = float(len(rr))
        return out
    d = np.diff(rr)
    sdnn, rmssd = float(np.std(rr)), float(np.sqrt(np.mean(d ** 2)))
    sd1 = rmssd / math.sqrt(2)
    sd2 = math.sqrt(max(2 * sdnn ** 2 - sd1 ** 2, 0.0))
    turning = np.sum((rr[1:-1] - rr[:-2]) * (rr[1:-1] - rr[2:]) > 0)
    return {
        f'{prefix}_n': float(len(rr)), f'{prefix}_mean': float(rr.mean()), f'{prefix}_sdnn': sdnn,
        f'{prefix}_rmssd': rmssd, f'{prefix}_pnn50': float(np.mean(np.abs(d) > 50)),
        f'{prefix}_cv': sdnn / float(rr.mean()), f'{prefix}_sd1': sd1, f'{prefix}_sd2': sd2,
        f'{prefix}_sd1_sd2': sd1 / sd2 if sd2 > EPS else math.nan,
        f'{prefix}_tpr': float(turning / (len(rr) - 2)),
    }


# ─── head feature functions ──────────────────────────────────────────────────

def stress_features(w: Window) -> Dict[str, float]:
    v, c = w.v, w.calib
    eda, bpm, temp = v['eda_us'], v['ppg_bpm'], v['temp_skin_c']
    eda_mean = _nanmean(eda)
    f = {
        'eda_rel_mean': _rel(eda_mean, c['eda_base']),
        'eda_rel_max': _rel(_nanmax(eda), c['eda_base']),
        'eda_std': _nanstd(eda),
        'eda_slope': _slope_per_s(eda),
        'eda_rise_frac': float(np.mean(_finite(v['eda_slope_us_s']) > 0.005)) if len(_finite(v['eda_slope_us_s'])) else math.nan,
        'eda_range': _nanmax(eda) - _nanmin(eda),
        'bpm_mean': _nanmean(bpm),
        'bpm_rel': _rel(_nanmean(bpm), c['bpm_base']),
        'bpm_std': _nanstd(bpm),
        'bpm_slope': _slope_per_s(bpm),
        'temp_delta': _nanmean(temp) - c['temp_base'],
        'temp_slope': _slope_per_s(temp),
        'acc_activity': _nanmean(v['imu_acc_std_g']),
        'acc_peak': _nanmax(v['imu_acc_max_g']),
    }
    f.update(rr_stats(clean_rr(w.rr_flat()), 'hrv'))
    return f


def _fall_features(w: Window, use_gyro: bool) -> Dict[str, float]:
    v = w.v
    amax, amin, amean, astd = v['imu_acc_max_g'], v['imu_acc_min_g'], v['imu_acc_mean_g'], v['imu_acc_std_g']
    if not np.isfinite(amax).any():
        k = w.T - 1
    else:
        k = int(np.nanargmax(amax))
    peak = _nanmax(amax)
    trough_before = _nanmin(amin[: k + 1])
    f = {
        'peak_g': peak,
        'trough_g': _nanmin(amin),
        'trough_before_peak_g': trough_before,
        'peak_minus_trough': peak - trough_before,
        'peak_rel_median': peak / (_nanmedian(amax) + EPS),
        'peak_rel_mean_level': peak / (_nanmean(amean) + EPS),
        'peak_pos': k / max(w.T - 1, 1),
        'std_max': _nanmax(astd),
        'std_after_peak': _nanmean(astd[k + 1:]) if k < w.T - 1 else math.nan,
        'level_dev_last': abs(amean[-1] - 1.0) if np.isfinite(amean[-1]) else math.nan,
        'tilt_change': abs(v['imu_tilt_deg'][-1] - v['imu_tilt_deg'][0]),
        'tilt_change_after_peak': abs(v['imu_tilt_deg'][-1] - v['imu_tilt_deg'][k]),
    }
    if use_gyro:
        f['gyro_peak'] = _nanmax(v['imu_gyro_max_dps'])
        f['gyro_mean'] = _nanmean(v['imu_gyro_mean_dps'])
        f['gyro_at_peak'] = float(v['imu_gyro_max_dps'][k])
    return f


def fall_features(w: Window) -> Dict[str, float]:
    return _fall_features(w, use_gyro=True)


def fall_features_acc_only(w: Window) -> Dict[str, float]:
    return _fall_features(w, use_gyro=False)


def activity_features(w: Window) -> Dict[str, float]:
    v, c = w.v, w.calib
    astd = v['imu_acc_std_g']
    return {
        'acc_std_mean': _nanmean(astd), 'acc_std_max': _nanmax(astd),
        'acc_std_p90': float(np.percentile(_finite(astd), 90)) if len(_finite(astd)) else math.nan,
        'acc_max_mean': _nanmean(v['imu_acc_max_g']), 'acc_max_max': _nanmax(v['imu_acc_max_g']),
        'acc_min_min': _nanmin(v['imu_acc_min_g']),
        'acc_level_dev': _nanmean(np.abs(v['imu_acc_mean_g'] - 1.0)),
        'tilt_mean': _nanmean(v['imu_tilt_deg']), 'tilt_std': _nanstd(v['imu_tilt_deg']),
        'moving_frac': float(np.mean(_finite(astd) > 0.05)) if len(_finite(astd)) else math.nan,
        'bpm_mean': _nanmean(v['ppg_bpm']),
        'bpm_rel': _rel(_nanmean(v['ppg_bpm']), c['bpm_base']),
    }


def hr_trust_features(w: Window) -> Dict[str, float]:
    v = w.v
    bpm = v['ppg_bpm']
    rr = w.rr_flat()
    n_rr = np.array([len(r) for r in w.rr], dtype=float)
    bpm_last = float(bpm[-1])
    expected = _nanmean(bpm) * w.T * FRAME_PERIOD_S / 60.0
    f = {
        'bpm_last': bpm_last, 'bpm_std': _nanstd(bpm), 'bpm_range': _nanmax(bpm) - _nanmin(bpm),
        'bpm_missing_frac': float(np.mean(~np.isfinite(bpm))),
        'beats_vs_expected': float(n_rr.sum() / expected) if math.isfinite(expected) and expected > 0 else math.nan,
        'no_rr_frac': float(np.mean(n_rr == 0)),
        'rr_cv': float(np.std(rr) / np.mean(rr)) if len(rr) > 2 else math.nan,
        'rr_succ_mad': float(np.median(np.abs(np.diff(rr)))) if len(rr) > 2 else math.nan,
        'hr_from_rr_vs_bpm': (60000.0 / np.median(rr) - bpm_last) if len(rr) > 2 and math.isfinite(bpm_last) else math.nan,
        'acc_std_mean': _nanmean(v['imu_acc_std_g']), 'acc_std_max': _nanmax(v['imu_acc_std_g']),
        'acc_peak': _nanmax(v['imu_acc_max_g']),
    }
    return f


def rhythm_features(w: Window) -> Dict[str, float]:
    rr = w.rr_flat()
    f = rr_stats(rr, 'rr')
    if len(rr) >= 4:
        d = np.abs(np.diff(rr))
        f.update({
            'rr_sampen': sample_entropy(rr),
            'rr_big_jump_frac': float(np.mean(d > 0.2 * np.median(rr))),
            'rr_max_min_ratio': float(rr.max() / rr.min()),
            'rr_mad_rel': float(np.median(np.abs(rr - np.median(rr))) / np.median(rr)),
            'hr_mean': 60000.0 / float(rr.mean()),
        })
    else:
        f.update({k: math.nan for k in ('rr_sampen', 'rr_big_jump_frac', 'rr_max_min_ratio',
                                        'rr_mad_rel', 'hr_mean')})
    return f


# ─── sequence inputs (1D-CNN candidate) ──────────────────────────────────────

def _stack(cols: List[np.ndarray]) -> np.ndarray:
    return np.stack([np.asarray(c, dtype=np.float32) for c in cols], axis=1)  # (T, C)


def _rr_frame_mean(w: Window) -> np.ndarray:
    return np.array([np.mean(r) / 1000.0 if r else np.nan for r in w.rr])


def stress_sequence(w: Window) -> np.ndarray:
    c = w.calib
    eda_base = c['eda_base'] if math.isfinite(c['eda_base']) and c['eda_base'] > EPS else np.nan
    bpm_base = c['bpm_base'] if math.isfinite(c['bpm_base']) and c['bpm_base'] > EPS else np.nan
    return _stack([w.v['eda_us'] / eda_base - 1, w.v['eda_slope_us_s'], w.v['ppg_bpm'] / bpm_base - 1,
                   _rr_frame_mean(w), w.v['temp_skin_c'] - c['temp_base'],
                   w.v['imu_acc_std_g'], w.v['imu_acc_mean_g']])


def fall_sequence(w: Window) -> np.ndarray:
    v = w.v
    return _stack([v['imu_acc_max_g'], v['imu_acc_min_g'], v['imu_acc_mean_g'], v['imu_acc_std_g'],
                   v['imu_gyro_max_dps'] / 100.0, v['imu_gyro_mean_dps'] / 100.0, v['imu_tilt_deg'] / 180.0])


def fall_sequence_acc_only(w: Window) -> np.ndarray:
    return fall_sequence(w)[:, [0, 1, 2, 3, 6]]


def activity_sequence(w: Window) -> np.ndarray:
    v, c = w.v, w.calib
    bpm_base = c['bpm_base'] if math.isfinite(c['bpm_base']) and c['bpm_base'] > EPS else np.nan
    return _stack([v['imu_acc_max_g'], v['imu_acc_min_g'], v['imu_acc_mean_g'], v['imu_acc_std_g'],
                   v['imu_tilt_deg'] / 180.0, v['ppg_bpm'] / bpm_base - 1])


def hr_trust_sequence(w: Window) -> np.ndarray:
    v = w.v
    return _stack([v['ppg_bpm'] / 100.0, np.array([len(r) for r in w.rr], float), _rr_frame_mean(w),
                   np.array([np.std(r) / 1000.0 if len(r) > 1 else np.nan for r in w.rr]),
                   v['imu_acc_std_g'], v['imu_acc_max_g']])


RHYTHM_SEQ_LEN = 64


def rhythm_sequence(w: Window) -> np.ndarray:
    rr = w.rr_flat()[-RHYTHM_SEQ_LEN:]
    out = np.full((RHYTHM_SEQ_LEN, 2), np.nan, dtype=np.float32)
    if len(rr):
        med = np.median(rr)
        out[-len(rr):, 0] = rr / med - 1.0
        out[-len(rr):, 1] = np.r_[0.0, np.diff(rr)] / med
    return out


# ─── registry ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FeatureSet:
    name: str
    T: int                                            # window length in frames
    tabular: Callable[[Window], Dict[str, float]]
    sequence: Callable[[Window], np.ndarray]


FEATURE_SETS: Dict[str, FeatureSet] = {fs.name: fs for fs in [
    FeatureSet('stress', 40, stress_features, stress_sequence),
    FeatureSet('fall', 4, fall_features, fall_sequence),
    FeatureSet('fall_acc_only', 4, fall_features_acc_only, fall_sequence_acc_only),
    FeatureSet('activity', 20, activity_features, activity_sequence),
    FeatureSet('hr_trust', 8, hr_trust_features, hr_trust_sequence),
    FeatureSet('rhythm', 40, rhythm_features, rhythm_sequence),
]}


def compute(feature_set: str, window: Window):
    """Tabular features and sequence for one window (warnings from all-NaN slices muted)."""
    fs = FEATURE_SETS[feature_set]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        return fs.tabular(window), fs.sequence(window)
