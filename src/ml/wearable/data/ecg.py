"""Chest-ECG R-peak detection and the ECG reference heart rate used by the HR-trust head.

PPG-DaLiA ships R-peaks; WESAD only ships the raw 700 Hz chest ECG. This detector is
validated against the PPG-DaLiA R-peaks (`python -m src.ml.wearable.data.ecg --validate`)
before its WESAD output is trusted as a label source.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import butter, find_peaks, resample_poly, sosfiltfilt

ECG_WORK_FS = 250.0


def detect_rpeaks(ecg: np.ndarray, fs: float) -> np.ndarray:
    """R-peak times (s): band-pass, squared slope, moving integration, adaptive threshold."""
    x = np.asarray(ecg, dtype=np.float64).ravel()
    if fs != ECG_WORK_FS:
        x = resample_poly(x, int(ECG_WORK_FS), int(fs)) if float(fs).is_integer() else x
        fs_w = ECG_WORK_FS if float(fs).is_integer() else fs
    else:
        fs_w = fs
    band = sosfiltfilt(butter(3, [5.0, 20.0], btype='bandpass', fs=fs_w, output='sos'), x)
    energy = np.convolve(np.gradient(band) ** 2, np.ones(int(0.15 * fs_w)) / int(0.15 * fs_w), mode='same')
    ref = pd.Series(energy).rolling(int(5 * fs_w), center=True, min_periods=1).quantile(0.98).to_numpy()
    peaks, _ = find_peaks(energy, height=0.3 * ref, distance=int(0.3 * fs_w))
    # refine each detection to the largest |band-passed ECG| sample within +-75 ms
    half = int(0.075 * fs_w)
    refined = np.array([max(0, p - half) + int(np.argmax(np.abs(band[max(0, p - half):p + half + 1])))
                        for p in peaks], dtype=np.int64)
    return np.unique(refined) / fs_w


def reference_hr(rpeaks_s: np.ndarray, duration_s: float, win_s: float = 8.0, step_s: float = 2.0) -> np.ndarray:
    """Mean HR over 8 s windows shifted by 2 s (the PPG-DaLiA ground-truth convention)."""
    starts = np.arange(0.0, duration_s - win_s + 1e-9, step_s)
    rr_end = rpeaks_s[1:]
    rr = np.diff(rpeaks_s)
    out = np.full(len(starts), np.nan)
    lo = np.searchsorted(rr_end, starts)
    hi = np.searchsorted(rr_end, starts + win_s)
    for i, (a, b) in enumerate(zip(lo, hi)):
        seg = rr[a:b]
        seg = seg[(seg > 0.27) & (seg < 2.0)]
        if len(seg) >= 3:
            out[i] = 60.0 / seg.mean()
    return out


def match_peaks(detected: np.ndarray, reference: np.ndarray, tol_s: float = 0.05) -> dict:
    pos = np.clip(np.searchsorted(detected, reference), 1, max(len(detected) - 1, 1))
    nearest = np.minimum(np.abs(detected[pos] - reference), np.abs(detected[pos - 1] - reference))
    tp = int((nearest <= tol_s).sum())
    return {'reference': len(reference), 'detected': len(detected), 'sensitivity': tp / max(len(reference), 1),
            'ppv': tp / max(len(detected), 1)}


def _validate() -> None:
    import io
    import zipfile

    from .. import paths
    from .compact import SafeUnpickler, load_registry

    cfg = load_registry()['ppg_dalia']
    with zipfile.ZipFile(paths.RAW_DIR / cfg['archive']) as outer:
        inner = zipfile.ZipFile(outer.open(cfg['archive_nested']))
        for subject in ('S1', 'S7', 'S12'):
            member = next(n for n in inner.namelist() if n.endswith(f'/{subject}.pkl'))
            with inner.open(member) as fh:
                data = SafeUnpickler(io.BufferedReader(fh, 1 << 24), encoding='latin1').load()
            ecg = np.asarray(data['signal']['chest']['ECG']).ravel()
            ref = np.asarray(data['rpeaks']) / 700.0
            det = detect_rpeaks(ecg, 700.0)
            hr_det = reference_hr(det, len(ecg) / 700.0)
            hr_ref = np.asarray(data['label']).ravel()
            n = min(len(hr_det), len(hr_ref))
            err = np.abs(hr_det[:n] - hr_ref[:n])
            print(subject, match_peaks(det, ref), f'HR median abs err {np.nanmedian(err):.2f} bpm, '
                  f'p95 {np.nanpercentile(err, 95):.2f}')
            del data


if __name__ == '__main__':
    _validate()
