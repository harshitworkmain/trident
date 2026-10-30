"""Device emulator: raw Recording -> stream of schema-v2 telemetry frames.

The emulator reproduces what firmware v2 would have sent had the subject worn the TRIDENT
wearable, so models are trained on exactly the representation the server receives:

* IMU resampled to the firmware rate (IMU_HZ) when the source is faster, then |acc| / |gyro|
  aggregated per FRAME_PERIOD_S window.
* Beats -> RR intervals accepted by the firmware window (RR_MIN_MS..RR_MAX_MS), and the
  firmware's heart-rate EMA (0.9 old + 0.1 new); BPM drops out after BPM_TIMEOUT_S without
  a beat, as on the device.
* EDA in uS with a per-recording calibration baseline (first EDA_BASELINE_S), mirroring
  the device's calibrate_gsr command.

Fields the source dataset cannot provide stay NaN. `imu_fall_detected` is left NaN on
purpose: it is a firmware heuristic, used only by the fusion layer as a backstop.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy.signal import butter, find_peaks, resample_poly, sosfiltfilt

from .data.recording import Recording, Signal
from .schema import FIELD_NAMES, FRAME_PERIOD_S, IMU_HZ, RR_MAX_MS, RR_MIN_MS

BPM_TIMEOUT_S = 4.0
EDA_BASELINE_S = 120.0
EMULATOR_VERSION = '1.0.0'


# ─── helpers ─────────────────────────────────────────────────────────────────

def _frame_index(times: np.ndarray, n_frames: int):
    idx = np.floor(times / FRAME_PERIOD_S).astype(np.int64)
    ok = (idx >= 0) & (idx < n_frames)
    return idx, ok


def _bin_stats(times: np.ndarray, values: np.ndarray, n_frames: int) -> Dict[str, np.ndarray]:
    idx, ok = _frame_index(times, n_frames)
    idx, v = idx[ok], values[ok]
    count = np.bincount(idx, minlength=n_frames).astype(np.float64)
    total = np.bincount(idx, weights=v, minlength=n_frames)
    total_sq = np.bincount(idx, weights=v * v, minlength=n_frames)
    vmax = np.full(n_frames, -np.inf)
    vmin = np.full(n_frames, np.inf)
    np.maximum.at(vmax, idx, v)
    np.minimum.at(vmin, idx, v)
    with np.errstate(invalid='ignore', divide='ignore'):
        mean = total / count
        std = np.sqrt(np.maximum(total_sq / count - mean ** 2, 0.0))
    empty = count == 0
    for arr in (mean, std, vmax, vmin):
        arr[empty] = np.nan
    return {'count': count, 'mean': mean, 'std': std, 'max': vmax, 'min': vmin}


def _bin_slope(times: np.ndarray, values: np.ndarray, n_frames: int) -> np.ndarray:
    """Least-squares slope of values vs time inside each frame (units per second)."""
    idx, ok = _frame_index(times, n_frames)
    idx, t, v = idx[ok], times[ok], values[ok]
    n = np.bincount(idx, minlength=n_frames).astype(np.float64)
    st, sv = np.bincount(idx, t, n_frames), np.bincount(idx, v, n_frames)
    stt, stv = np.bincount(idx, t * t, n_frames), np.bincount(idx, t * v, n_frames)
    with np.errstate(invalid='ignore', divide='ignore'):
        slope = (n * stv - st * sv) / (n * stt - st * st)
    slope[n < 2] = np.nan
    return slope


def to_imu_rate(sig: Signal) -> Signal:
    """Anti-aliased resampling down to the firmware IMU rate; slower sources are kept as-is."""
    if sig.fs <= IMU_HZ + 1e-6:
        return sig
    ratio = Fraction(IMU_HZ / sig.fs).limit_denominator(200)
    data = resample_poly(sig.data, ratio.numerator, ratio.denominator, axis=0)
    return Signal(data, IMU_HZ, sig.t0, sig.kind)


def detect_beats(bvp: Signal) -> np.ndarray:
    """Systolic peak times (s) from a raw optical pulse wave."""
    x = np.asarray(bvp.data, dtype=np.float64).ravel()
    if len(x) < bvp.fs * 3:
        return np.empty(0)
    sos = butter(2, [0.5, 3.5], btype='bandpass', fs=bvp.fs, output='sos')
    y = sosfiltfilt(sos, x)
    win = max(int(bvp.fs * 5), 1)
    rms = np.sqrt(np.convolve(y * y, np.ones(win) / win, mode='same')) + 1e-9
    peaks, _ = find_peaks(y / rms, distance=max(int(bvp.fs * 0.33), 1), prominence=0.5)
    return bvp.t0 + peaks / bvp.fs


def firmware_bpm(beats_s: np.ndarray):
    """RR list and EMA heart rate exactly as the firmware computes them."""
    rr = np.diff(beats_s) * 1000.0
    ends = beats_s[1:]
    valid = (rr >= RR_MIN_MS) & (rr <= RR_MAX_MS)
    rr, ends = rr[valid], ends[valid]
    ema = np.empty_like(rr)
    bpm = 0.0
    for i, interval in enumerate(rr):
        inst = 60000.0 / interval
        bpm = inst if bpm == 0.0 else 0.9 * bpm + 0.1 * inst
        ema[i] = bpm
    return rr, ends, ema


# ─── emulator ────────────────────────────────────────────────────────────────

def emulate(rec: Recording, beats_s: Optional[np.ndarray] = None) -> pd.DataFrame:
    """Convert a Recording into a DataFrame with one row per 1.5 s telemetry frame.

    Columns: identity (dataset, subject, trial, frame, t_start), every schema field, `rr_ms`
    (list), `beat_symbols` (str, when annotated), `y_<label>` / `y_<label>_purity`, `m_<meta>`.
    """
    n = int(rec.duration // FRAME_PERIOD_S)
    if n <= 0:
        return pd.DataFrame()
    out: Dict[str, object] = {name: np.full(n, np.nan) for name in FIELD_NAMES}

    if rec.acc is not None:
        acc = to_imu_rate(rec.acc)
        vec = np.asarray(acc.data, dtype=np.float64)
        st = _bin_stats(acc.times(), np.linalg.norm(vec, axis=1), n)
        out.update(imu_acc_max_g=st['max'], imu_acc_min_g=st['min'], imu_acc_mean_g=st['mean'],
                   imu_acc_std_g=st['std'], imu_n=st['count'])
        mean_axes = [_bin_stats(acc.times(), vec[:, k], n)['mean'] for k in range(3)]
        norm = np.sqrt(sum(m ** 2 for m in mean_axes))
        with np.errstate(invalid='ignore', divide='ignore'):
            out['imu_tilt_deg'] = np.degrees(np.arccos(np.clip(mean_axes[2] / norm, -1, 1)))
    if rec.gyro is not None:
        gyro = to_imu_rate(rec.gyro)
        st = _bin_stats(gyro.times(), np.linalg.norm(np.asarray(gyro.data, float), axis=1), n)
        out.update(imu_gyro_max_dps=st['max'], imu_gyro_mean_dps=st['mean'])

    if beats_s is None:
        beats_s = rec.beats_s if rec.beats_s is not None else (
            detect_beats(rec.bvp) if rec.bvp is not None else None)
    rr_lists = [[] for _ in range(n)]
    if beats_s is not None and len(beats_s) > 1:
        rr, ends, ema = firmware_bpm(np.asarray(beats_s, dtype=np.float64))
        idx, ok = _frame_index(ends, n)
        for i, r in zip(idx[ok], rr[ok]):
            rr_lists[i].append(float(r))
        frame_end = (np.arange(n) + 1) * FRAME_PERIOD_S
        last = np.searchsorted(ends, frame_end, side='right') - 1
        has = last >= 0
        bpm = np.full(n, np.nan)
        bpm[has] = ema[last[has]]
        stale = ~has | (frame_end - np.where(has, ends[np.maximum(last, 0)], -np.inf) > BPM_TIMEOUT_S)
        bpm[stale] = np.nan
        out['ppg_bpm'] = bpm
        out['ppg_finger_on'] = np.ones(n)

    if rec.eda is not None:
        t, x = rec.eda.times(), np.asarray(rec.eda.data, float).ravel()
        out['eda_us'] = _bin_stats(t, x, n)['mean']
        out['eda_slope_us_s'] = _bin_slope(t, x, n)
        base = x[t < rec.eda.t0 + EDA_BASELINE_S]
        out['eda_baseline_us'] = np.full(n, float(np.mean(base)) if len(base) else np.nan)
    if rec.temp is not None:
        out['temp_skin_c'] = _bin_stats(rec.temp.times(), np.asarray(rec.temp.data, float).ravel(), n)['mean']

    df = pd.DataFrame(out)
    df['rr_ms'] = rr_lists

    if rec.beat_symbols is not None and rec.beats_s is not None:
        idx, ok = _frame_index(rec.beats_s, n)
        symbols = [''] * n
        for i, s in zip(idx[ok], rec.beat_symbols[ok]):
            symbols[i] += s
        df['beat_symbols'] = symbols

    for name, sig in rec.labels.items():
        t = sig.times()
        if sig.kind == 'categorical':
            idx, ok = _frame_index(t, n)
            codes = np.asarray(sig.data, dtype=np.int64)[ok]
            offset = codes.min() if len(codes) else 0
            k = int(codes.max() - offset + 1) if len(codes) else 1
            counts = np.bincount(idx[ok] * k + (codes - offset), minlength=n * k).reshape(n, k)
            total = counts.sum(axis=1)
            mode = np.where(total > 0, counts.argmax(axis=1) + offset, -1)
            with np.errstate(invalid='ignore', divide='ignore'):
                purity = np.where(total > 0, counts.max(axis=1) / total, np.nan)
            df[f'y_{name}'] = mode
            df[f'y_{name}_purity'] = purity
        else:
            df[f'y_{name}'] = _bin_stats(t, np.asarray(sig.data, float).ravel(), n)['mean']

    mid = (np.arange(n) + 0.5) * FRAME_PERIOD_S
    for name, (times, values) in rec.state_labels.items():
        pos = np.searchsorted(times, mid, side='right') - 1
        df[f'y_{name}'] = np.where(pos >= 0, np.asarray(values, dtype=object)[np.maximum(pos, 0)], None)

    for key, value in rec.meta.items():
        if key != 'duration_s':
            df[f'm_{key}'] = value

    df.insert(0, 't_start', np.arange(n) * FRAME_PERIOD_S)
    df.insert(0, 'frame', np.arange(n))
    df.insert(0, 'trial', rec.trial)
    df.insert(0, 'subject', rec.subject)
    df.insert(0, 'dataset', rec.dataset)
    return df
