"""Turn compacted dataset files into canonical Recording objects.

Each loader yields one Recording per subject (continuous datasets) or per trial
(event datasets), converting to canonical units. Label semantics are kept raw here;
mapping labels to head classes happens in the head dataset builders (P2).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator

import numpy as np
from scipy.spatial.transform import Rotation

from .. import paths
from .recording import Recording, Signal

E4_FS = {'ACC': 32.0, 'BVP': 64.0, 'EDA': 4.0, 'TEMP': 4.0}


def _compact(name: str) -> Path:
    path = paths.COMPACT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f'{path} missing - run: python -m src.ml.wearable.data.compact {name}')
    return path


def _acc_to_g(acc: np.ndarray) -> np.ndarray:
    """E4 accelerometers are stored either in g or in raw 1/64 g counts depending on dataset."""
    median = float(np.median(np.linalg.norm(acc, axis=1)))
    if 40 < median < 90:
        return acc / 64.0
    if 0.7 < median < 1.4:
        return acc
    raise ValueError(f'unrecognised accelerometer scale (median |a| = {median:.2f})')


# ─── WESAD ───────────────────────────────────────────────────────────────────

def load_wesad() -> Iterator[Recording]:
    from .ecg import reference_hr

    for f in sorted(_compact('wesad').glob('S*.npz'), key=lambda p: int(p.stem[1:])):
        with np.load(f) as z:
            labels = {'protocol': Signal(z['label'].astype(np.int64), 700.0, kind='categorical')}
            if 'chest_rpeaks_s' in z.files:
                # chest and wrist streams are synchronised in the WESAD pickles
                hr = reference_hr(z['chest_rpeaks_s'], float(z['chest_ecg_duration_s']))
                labels['hr_ecg'] = Signal(hr, 0.5, t0=4.0)
            yield Recording(
                dataset='wesad', subject=f.stem, trial='session', placement='wrist',
                acc=Signal(_acc_to_g(z['wrist_ACC'].astype(np.float64)), E4_FS['ACC']),
                bvp=Signal(z['wrist_BVP'].ravel().astype(np.float64), E4_FS['BVP']),
                eda=Signal(z['wrist_EDA'].ravel().astype(np.float64), E4_FS['EDA']),
                temp=Signal(z['wrist_TEMP'].ravel().astype(np.float64), E4_FS['TEMP']),
                labels=labels,
            )


# ─── PPG-DaLiA ───────────────────────────────────────────────────────────────

def load_ppg_dalia() -> Iterator[Recording]:
    for f in sorted(_compact('ppg_dalia').glob('S*.npz'), key=lambda p: int(p.stem[1:])):
        with np.load(f) as z:
            yield Recording(
                dataset='ppg_dalia', subject=f.stem, trial='session', placement='wrist',
                acc=Signal(_acc_to_g(z['wrist_ACC'].astype(np.float64)), E4_FS['ACC']),
                bvp=Signal(z['wrist_BVP'].ravel().astype(np.float64), E4_FS['BVP']),
                eda=Signal(z['wrist_EDA'].ravel().astype(np.float64), E4_FS['EDA']),
                temp=Signal(z['wrist_TEMP'].ravel().astype(np.float64), E4_FS['TEMP']),
                labels={
                    'activity': Signal(z['activity'].astype(np.int64), 4.0, kind='categorical'),
                    # ECG reference HR: 8 s windows shifted by 2 s -> value i is centred at 4 + 2i s
                    'hr_ecg': Signal(z['label'].astype(np.float64), 0.5, t0=4.0),
                },
            )


def ppg_dalia_ecg_beats(subject: str) -> np.ndarray:
    """Chest-ECG R-peak times (s) for PPG-DaLiA - ground truth for beat-detection quality."""
    with np.load(_compact('ppg_dalia') / f'{subject}.npz') as z:
        return z['rpeaks'] / 700.0


# ─── SisFall ─────────────────────────────────────────────────────────────────

SISFALL_FS = 200.0
# ADXL345: +-16 g over 13 bits; ITG3200: +-2000 deg/s over 16 bits (SisFall Readme).
ADXL345_G_PER_COUNT = (2 * 16) / 2 ** 13
ITG3200_DPS_PER_COUNT = (2 * 2000) / 2 ** 16


def load_sisfall() -> Iterator[Recording]:
    for f in sorted(_compact('sisfall').glob('S*.npz')):
        with np.load(f) as z:
            for key in sorted(z.files):
                raw = z[key].astype(np.float64)
                code = key.split('_')[0]
                yield Recording(
                    dataset='sisfall', subject=f.stem, trial=key, placement='waist',
                    acc=Signal(raw[:, 0:3] * ADXL345_G_PER_COUNT, SISFALL_FS),
                    gyro=Signal(raw[:, 3:6] * ITG3200_DPS_PER_COUNT, SISFALL_FS),
                    meta={'code': code, 'is_fall': code.startswith('F'),
                          'age_group': 'elderly' if f.stem.startswith('SE') else 'young'},
                )


# ─── UP-Fall ─────────────────────────────────────────────────────────────────

UPFALL_FS = 20.0  # irregular ~21 Hz stream, interpolated onto a uniform 20 Hz grid


def _uniform(t: np.ndarray, values: np.ndarray, fs: float, categorical: bool = False):
    grid = np.arange(t[0], t[-1], 1.0 / fs)
    if categorical:
        idx = np.clip(np.searchsorted(t, grid, side='right') - 1, 0, len(t) - 1)
        return values[idx]
    if values.ndim == 1:
        return np.interp(grid, t, values)
    return np.column_stack([np.interp(grid, t, values[:, i]) for i in range(values.shape[1])])


def load_upfall() -> Iterator[Recording]:
    for f in sorted(_compact('upfall').glob('Subject*.npz'), key=lambda p: int(p.stem[7:])):
        with np.load(f) as z:
            columns = json.loads(str(z['__columns__']))
            wrist_acc = [i for i, c in enumerate(columns) if c == 'WristAccelerometer']
            wrist_gyro = [i for i, c in enumerate(columns) if c == 'WristAngularVelocity']
            tag_col = columns.index('Tag')
            for key in sorted(k for k in z.files if not k.startswith('__') and '__' not in k):
                values, t = z[key], z[f'{key}__t']
                order = np.argsort(t, kind='stable')
                t, values = t[order] - t[order][0], values[order]
                keep = np.concatenate([[True], np.diff(t) > 0])  # drop duplicate timestamps
                t, values = t[keep], values[keep]
                activity = int(key.split('Activity')[1].split('Trial')[0])
                yield Recording(
                    dataset='upfall', subject=f.stem, trial=key, placement='wrist',
                    acc=Signal(_uniform(t, values[:, wrist_acc], UPFALL_FS), UPFALL_FS),
                    gyro=Signal(_uniform(t, values[:, wrist_gyro], UPFALL_FS), UPFALL_FS),
                    labels={'tag': Signal(_uniform(t, values[:, tag_col].astype(np.int64),
                                                   UPFALL_FS, categorical=True),
                                          UPFALL_FS, kind='categorical')},
                    meta={'activity': activity, 'is_fall': activity <= 5},
                )


# ─── HIFD ────────────────────────────────────────────────────────────────────

HIFD_FS = 50.0
HIFD_FALLS = {'fall1', 'fall2', 'fall3', 'fall4', 'fall5', 'fall6'}


def hifd_restore_gravity(quat_wxyz: np.ndarray, acc_dynamic: np.ndarray) -> np.ndarray:
    """HIFD removed gravity; add it back in the sensor frame from the orientation quaternion.

    The quaternion rotates sensor->world, so world vertical seen from the sensor is R^T z.
    """
    rot = Rotation.from_quat(quat_wxyz[:, [1, 2, 3, 0]])
    return acc_dynamic + rot.inv().apply([0.0, 0.0, 1.0])


def _rising_edges(pulse: np.ndarray, fs: float) -> np.ndarray:
    high = pulse > (np.nanmax(pulse) / 2 if np.nanmax(pulse) > 0 else 0.5)
    return (np.flatnonzero(high[1:] & ~high[:-1]) + 1) / fs


def load_hifd() -> Iterator[Recording]:
    for f in sorted(_compact('hifd').glob('subject_*.npz')):
        with np.load(f) as z:
            for key in sorted(k for k in z.files if not k.startswith('__') and not k.endswith('__time')):
                a = z[key]
                scenario = key.split('__')[1]
                yield Recording(
                    dataset='hifd', subject=f.stem, trial=key, placement='wrist',
                    acc=Signal(hifd_restore_gravity(a[:, 0:4], a[:, 7:10]), HIFD_FS),
                    gyro=Signal(a[:, 4:7], HIFD_FS),
                    beats_s=_rising_edges(a[:, 10], HIFD_FS),
                    meta={'scenario': scenario, 'is_fall': scenario in HIFD_FALLS,
                          'duration_s': len(a) / HIFD_FS},
                )


# ─── MIT-BIH ─────────────────────────────────────────────────────────────────

MITBIH_BEAT_SYMBOLS = set('NLRBAaJSVrFejnE/fQ?')  # PhysioNet beat annotation codes


def load_mitbih() -> Iterator[Recording]:
    for f in sorted(_compact('mitbih').glob('*.npz')):
        with np.load(f) as z:
            fs = float(z['fs'])
            sample, symbol, aux = z['ann_sample'], z['ann_symbol'], z['ann_aux']
            beat = np.array([s in MITBIH_BEAT_SYMBOLS for s in symbol])
            rhythm = np.array([a.startswith('(') for a in aux])
            yield Recording(
                dataset='mitbih', subject=f.stem, trial='record', placement='chest',
                beats_s=sample[beat] / fs, beat_symbols=symbol[beat],
                state_labels={'rhythm': (sample[rhythm] / fs, aux[rhythm])},
                meta={'duration_s': float(z['sig_len']) / fs},
            )


# ─── AFDB / LTAFDB ───────────────────────────────────────────────────────────

def _load_physionet_rhythm(name: str) -> Iterator[Recording]:
    for f in sorted(_compact(name).glob('*.npz')):
        with np.load(f) as z:
            fs = float(z['fs'])
            aux = z['ann_aux']
            rhythm = np.array([a.startswith('(') for a in aux])
            symbols = z['beat_symbol']
            beat = np.array([s in MITBIH_BEAT_SYMBOLS for s in symbols])
            beats_s = z['beat_sample'][beat] / fs
            if len(beats_s) < 2 or not rhythm.any():
                continue
            yield Recording(
                dataset=name, subject=f.stem, trial='record', placement='chest',
                beats_s=beats_s, beat_symbols=symbols[beat],
                state_labels={'rhythm': (z['ann_sample'][rhythm] / fs, aux[rhythm])},
                meta={'duration_s': max(float(z['sig_len']) / fs, float(beats_s[-1]))},
            )


def load_afdb() -> Iterator[Recording]:
    return _load_physionet_rhythm('afdb')


def load_ltafdb() -> Iterator[Recording]:
    return _load_physionet_rhythm('ltafdb')


# ─── PAMAP2 ──────────────────────────────────────────────────────────────────

PAMAP2_FS = 100.0
G = 9.80665


def beats_from_hr(t: np.ndarray, hr_bpm: np.ndarray, max_gap_s: float = 5.0) -> np.ndarray:
    """Beat times implied by a sparse heart-rate stream (chest strap) by integrating the rate.

    Gives perfectly regular RR intervals at the measured rate; only rate-level features are
    meaningful for such recordings (used by the activity head, never by HR-trust or rhythm).
    """
    ok = np.isfinite(hr_bpm)
    if ok.sum() < 2:
        return np.empty(0)
    ts, hs = t[ok], hr_bpm[ok]
    grid = np.arange(ts[0], ts[-1], 0.05)
    rate = np.interp(grid, ts, hs) / 60.0
    gap = np.diff(ts) > max_gap_s                          # no beats across long HR dropouts
    if gap.any():
        for a, b in zip(ts[:-1][gap], ts[1:][gap]):
            rate[(grid > a) & (grid < b)] = 0.0
    phase = np.cumsum(rate) * 0.05
    idx = np.flatnonzero(np.diff(np.floor(phase)) > 0) + 1
    return grid[idx]


def load_pamap2() -> Iterator[Recording]:
    for f in sorted(_compact('pamap2').glob('subject*.npz')):
        with np.load(f) as z:
            cols = json.loads(str(z['__columns__']))
            for session in sorted(k for k in z.files if not k.startswith('__')):
                a = z[session]
                c = {name: a[:, i] for i, name in enumerate(cols)}
                t = c['t'] - c['t'][0]
                imu = np.column_stack([c[k] for k in ('acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z')])
                good = np.isfinite(imu).all(axis=1)              # wireless dropouts are NaN rows
                imu_u = _uniform(t[good], imu[good], PAMAP2_FS)
                act = _uniform(t, c['activity'].astype(np.int64), PAMAP2_FS, categorical=True)
                yield Recording(
                    dataset='pamap2', subject=f.stem, trial=session, placement='wrist',
                    acc=Signal(imu_u[:, 0:3] / G, PAMAP2_FS, t0=float(t[good][0])),
                    gyro=Signal(np.degrees(imu_u[:, 3:6]), PAMAP2_FS, t0=float(t[good][0])),
                    beats_s=beats_from_hr(t, c['hr']),
                    labels={'activity': Signal(act, PAMAP2_FS, kind='categorical')},
                )


# ─── Stress-Predict ──────────────────────────────────────────────────────────

def load_stress_predict() -> Iterator[Recording]:
    for f in sorted(_compact('stress_predict').glob('S*.npz')):
        with np.load(f) as z:
            ref = min(float(z[f'{s}_start']) for s in ('ACC', 'BVP', 'EDA', 'TEMP'))
            sig = {s: Signal(z[s].astype(np.float64), float(z[f'{s}_fs']), t0=float(z[f'{s}_start']) - ref)
                   for s in ('ACC', 'BVP', 'EDA', 'TEMP')}
            lt = z['label_time'].astype(np.float64) - ref
            # label codes follow WESAD's protocol ids: 1 = baseline/rest, 2 = stress task
            codes = z['label'].astype(np.int64) + 1
            grid_codes = _uniform(lt, codes, 1.0, categorical=True)
            yield Recording(
                dataset='stress_predict', subject=f.stem, trial='session', placement='wrist',
                acc=Signal(_acc_to_g(sig['ACC'].data), sig['ACC'].fs, sig['ACC'].t0),
                bvp=Signal(sig['BVP'].data.ravel(), sig['BVP'].fs, sig['BVP'].t0),
                eda=Signal(sig['EDA'].data.ravel(), sig['EDA'].fs, sig['EDA'].t0),
                temp=Signal(sig['TEMP'].data.ravel(), sig['TEMP'].fs, sig['TEMP'].t0),
                labels={'protocol': Signal(grid_codes, 1.0, t0=float(lt[0]), kind='categorical')},
            )


# ─── Capture-24 (read in place from the zip, one participant at a time) ──────

CAPTURE24_FS = 100.0
CAPTURE24_CLASSES = {'sleep': 0, 'sedentary': 1, 'light': 2, 'moderate-vigorous': 3}


def capture24_participants() -> list:
    import zipfile
    with zipfile.ZipFile(paths.RAW_DIR / '_zips' / 'capture24.zip') as zf:
        return sorted(Path(n).name.split('.')[0] for n in zf.namelist() if n.endswith('.csv.gz'))


def load_capture24(participants=None) -> Iterator[Recording]:
    import zipfile

    import pandas as pd

    with zipfile.ZipFile(paths.RAW_DIR / '_zips' / 'capture24.zip') as zf:
        with zf.open('capture24/annotation-label-dictionary.csv') as fh:
            vocab = pd.read_csv(fh)
        to_code = {a: CAPTURE24_CLASSES[w] for a, w in zip(vocab['annotation'], vocab['label:Walmsley2020'])}
        with zf.open('capture24/metadata.csv') as fh:
            meta = pd.read_csv(fh).set_index('pid')
        for pid in participants or capture24_participants():
            with zf.open(f'capture24/{pid}.csv.gz') as fh:
                df = pd.read_csv(fh, compression='gzip', usecols=['x', 'y', 'z', 'annotation'],
                                 dtype={'x': np.float32, 'y': np.float32, 'z': np.float32, 'annotation': str})
            codes = df['annotation'].map(to_code).fillna(-1).to_numpy(dtype=np.int64)  # -1 = not annotated
            acc = df[['x', 'y', 'z']].to_numpy(dtype=np.float64)
            del df
            yield Recording(
                dataset='capture24', subject=pid, trial='day', placement='wrist',
                acc=Signal(acc, CAPTURE24_FS),
                labels={'walmsley': Signal(codes, CAPTURE24_FS, kind='categorical')},
                meta={'age_group': str(meta.loc[pid, 'age']) if pid in meta.index else 'unknown'},
            )


# ─── MIMIC PERform AF (external rhythm test, read in place from the WFDB zips) ──

MIMIC_PERFORM_FS = 125.0
MIMIC_PERFORM_GROUPS = {'mimic_perform_af': 1, 'mimic_perform_non_af': 0}   # registry key -> AF label


def _read_wfdb16(zf, stem: str) -> Dict[str, np.ndarray]:
    """Physical-unit channels of a format-16 WFDB record inside an open zip (no extraction)."""
    header = zf.read(f'{stem}.hea').decode().splitlines()
    n_sig = int(header[0].split()[1])
    raw = np.frombuffer(zf.read(f'{stem}.dat'), dtype='<i2').reshape(-1, n_sig)
    out = {}
    for k, line in enumerate(header[1:n_sig + 1]):
        parts = line.split()
        gain, baseline = parts[2].split('/')[0].rstrip(')').split('(')
        x = (raw[:, k].astype(np.float64) - float(baseline)) / float(gain)
        x[raw[:, k] == -32768] = np.nan            # WFDB format-16 missing-sample marker
        out[parts[8].rstrip(',')] = x
    return out


def _fill_gaps(x: np.ndarray) -> np.ndarray:
    """Linear interpolation over missing samples (rare monitor dropouts)."""
    bad = ~np.isfinite(x)
    if bad.any() and not bad.all():
        x = x.copy()
        x[bad] = np.interp(np.flatnonzero(bad), np.flatnonzero(~bad), x[~bad])
    return x


def load_mimic_perform_af(with_ecg_beats: bool = False) -> Iterator[Recording]:
    """35 ICU adults, 20 min each: fingertip PPG (bedside monitor) + lead-II ECG, labelled per subject.

    The PPG is resampled to the E4 BVP rate the emulator's beat detector was used at in training.
    `beats_s` stays None so `emulate` detects beats from the PPG (the device path); with
    `with_ecg_beats` the ECG R-peaks are put in `meta['ecg_beats_s']` for the reference path
    (pop it before emulating - meta values are copied onto frames).
    Not in LOADERS on purpose: this is an external test set and must never reach training.
    """
    import zipfile
    from fractions import Fraction

    from scipy.signal import resample_poly

    from .compact import load_registry
    from .ecg import detect_rpeaks

    registry = load_registry()
    ratio = Fraction(E4_FS['BVP'] / MIMIC_PERFORM_FS).limit_denominator(200)
    for key, af in MIMIC_PERFORM_GROUPS.items():
        with zipfile.ZipFile(paths.RAW_DIR / registry[key]['archive']) as zf:
            folder = f'{key}_wfdb'
            for name in zf.read(f'{folder}/RECORDS').decode().split():
                sig = _read_wfdb16(zf, f'{folder}/{name}')
                ppg = resample_poly(_fill_gaps(sig['PPG']), ratio.numerator, ratio.denominator)
                meta = {'af': af, 'duration_s': len(sig['PPG']) / MIMIC_PERFORM_FS}
                if with_ecg_beats:
                    meta['ecg_beats_s'] = detect_rpeaks(_fill_gaps(sig['ECG']), MIMIC_PERFORM_FS)
                yield Recording(dataset='mimic_perform_af', subject=name, trial='icu', placement='finger',
                                bvp=Signal(ppg, E4_FS['BVP']), meta=meta)


LOADERS = {
    'wesad': load_wesad, 'ppg_dalia': load_ppg_dalia, 'sisfall': load_sisfall,
    'upfall': load_upfall, 'hifd': load_hifd, 'mitbih': load_mitbih,
    'afdb': load_afdb, 'ltafdb': load_ltafdb, 'pamap2': load_pamap2,
    'stress_predict': load_stress_predict, 'capture24': load_capture24,
}
# Datasets whose frames are stored one parquet file per recording (too large for one table in RAM)
PARTITIONED = {'capture24', 'ltafdb'}
