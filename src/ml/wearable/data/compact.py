"""Lossless per-subject compaction of the raw wearable datasets.

Every raw dataset is rewritten as one compressed .npz per subject, keeping only the
channels the emulator can use but keeping those channels at their original values.
Large archives (WESAD 17.6 GB, PPG-DaLiA 24 GB unzipped) are streamed straight out of
their zips, one subject in memory at a time.

Raw data is deleted only by `delete_raw()`, and only for datasets whose compaction has
been verified value-for-value against the raw source.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import pickle
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import scipy.io as sio
import yaml

from .. import paths

logger = logging.getLogger(__name__)

_PICKLE_ALLOWED = {
    ('numpy', 'ndarray'), ('numpy', 'dtype'),
    ('numpy.core.multiarray', '_reconstruct'), ('numpy._core.multiarray', '_reconstruct'),
    ('numpy.core.multiarray', 'scalar'), ('numpy._core.multiarray', 'scalar'),
    ('builtins', 'dict'), ('builtins', 'list'), ('builtins', 'tuple'),
    ('collections', 'OrderedDict'),
}


class SafeUnpickler(pickle.Unpickler):
    """Dataset pickles may only contain numpy arrays and plain containers."""

    def find_class(self, module, name):
        if (module, name) in _PICKLE_ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f'blocked global {module}.{name}')


def load_registry() -> Dict[str, dict]:
    with open(paths.CONFIG_DIR / 'datasets.yaml', encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def _out_dir(name: str) -> Path:
    out = paths.COMPACT_DIR / name
    out.mkdir(parents=True, exist_ok=True)
    return out


def _save(path: Path, arrays: Dict[str, np.ndarray]) -> None:
    tmp = path.with_suffix('.tmp.npz')
    np.savez_compressed(tmp, **arrays)
    tmp.replace(path)


# ─── E4 wrist pickles (WESAD, PPG-DaLiA) ─────────────────────────────────────

def _compact_e4_pickles(name: str, zip_path: Path, nested: str | None) -> List[str]:
    out = _out_dir(name)
    done = []
    with zipfile.ZipFile(zip_path) as outer:
        archive = zipfile.ZipFile(outer.open(nested)) if nested else outer
        for info in archive.infolist():
            if not info.filename.endswith('.pkl'):
                continue
            subject = Path(info.filename).stem
            target = out / f'{subject}.npz'
            if target.exists():
                done.append(subject)
                continue
            with archive.open(info) as fh:
                data = SafeUnpickler(io.BufferedReader(fh, 1 << 24), encoding='latin1').load()
            arrays = {f'wrist_{k}': np.asarray(v) for k, v in data['signal']['wrist'].items()}
            arrays['label'] = np.asarray(data['label'])
            if name == 'wesad':
                arrays['label'] = arrays['label'].astype(np.int8)  # 700 Hz protocol id 0-7
            else:
                arrays['activity'] = np.asarray(data['activity']).ravel().astype(np.int8)
                arrays['rpeaks'] = np.asarray(data['rpeaks']).astype(np.int64)
            _save(target, arrays)
            logger.info('%s %s: %s', name, subject,
                        ', '.join(f'{k}{v.shape}' for k, v in arrays.items()))
            done.append(subject)
            del data, arrays
    return done


def compact_wesad(cfg: dict) -> List[str]:
    done = _compact_e4_pickles('wesad', paths.RAW_DIR / cfg['raw'], nested=None)
    add_wesad_rpeaks(cfg)
    return done


def add_wesad_rpeaks(cfg: dict) -> None:
    """Add chest-ECG R-peak times (s) to each WESAD npz: the ECG reference for the HR-trust head."""
    from .ecg import detect_rpeaks

    out = paths.COMPACT_DIR / 'wesad'
    with zipfile.ZipFile(paths.RAW_DIR / cfg['raw']) as zf:
        for info in zf.infolist():
            if not info.filename.endswith('.pkl'):
                continue
            target = out / f'{Path(info.filename).stem}.npz'
            with np.load(target) as z:
                if 'chest_rpeaks_s' in z.files:
                    continue
                arrays = {k: z[k] for k in z.files}
            with zf.open(info) as fh:
                data = SafeUnpickler(io.BufferedReader(fh, 1 << 24), encoding='latin1').load()
            ecg = np.asarray(data['signal']['chest']['ECG']).ravel()
            del data
            arrays['chest_rpeaks_s'] = detect_rpeaks(ecg, 700.0)
            arrays['chest_ecg_duration_s'] = np.array(len(ecg) / 700.0)
            _save(target, arrays)
            logger.info('wesad %s: %d R-peaks', target.stem, len(arrays['chest_rpeaks_s']))


def compact_ppg_dalia(cfg: dict) -> List[str]:
    return _compact_e4_pickles('ppg_dalia', paths.RAW_DIR / cfg['raw'], nested='data.zip')


# ─── SisFall (text, 200 Hz, 9 integer columns) ───────────────────────────────

def _read_sisfall_txt(path: Path) -> np.ndarray:
    rows = [line.strip().rstrip(';') for line in path.read_text().splitlines()]
    data = np.array([[int(v) for v in r.split(',')] for r in rows if r], dtype=np.int64)
    assert data.shape[1] == 9, f'{path}: expected 9 columns, got {data.shape[1]}'
    assert np.abs(data).max() < 2 ** 15, f'{path}: value exceeds int16'
    return data.astype(np.int16)


def compact_sisfall(cfg: dict) -> List[str]:
    raw = paths.RAW_DIR / cfg['raw']
    out = _out_dir('sisfall')
    for doc in ('Readme.txt', 'Supplementary.pdf'):
        if (raw / doc).exists():
            shutil.copy2(raw / doc, out / doc)
    done = []
    for subj_dir in sorted(p for p in raw.iterdir() if p.is_dir()):
        target = out / f'{subj_dir.name}.npz'
        if not target.exists():
            arrays = {f.stem.replace(f'_{subj_dir.name}', ''): _read_sisfall_txt(f)
                      for f in sorted(subj_dir.glob('*.txt'))}
            _save(target, arrays)
            logger.info('sisfall %s: %d trials', subj_dir.name, len(arrays))
        done.append(subj_dir.name)
    return done


def verify_sisfall(cfg: dict) -> dict:
    raw = paths.RAW_DIR / cfg['raw']
    out = paths.COMPACT_DIR / 'sisfall'
    n_trials, mismatches = 0, []
    for subj_dir in sorted(p for p in raw.iterdir() if p.is_dir()):
        with np.load(out / f'{subj_dir.name}.npz') as z:
            for f in sorted(subj_dir.glob('*.txt')):
                key = f.stem.replace(f'_{subj_dir.name}', '')
                n_trials += 1
                if key not in z.files or not np.array_equal(z[key], _read_sisfall_txt(f)):
                    mismatches.append(f.name)
    return {'trials': n_trials, 'expected_trials': cfg['expected_trials'],
            'mismatches': mismatches,
            'ok': not mismatches and n_trials == cfg['expected_trials']}


# ─── UP-Fall (per-trial CSV, ~21 Hz, 5 IMU locations) ────────────────────────

def _read_upfall_csv(path: Path):
    header = path.open(encoding='utf-8').readline().strip().split(',')
    try:
        df = pd.read_csv(path, header=None, skiprows=2)
    except pd.errors.EmptyDataError:  # a few upstream files contain only the header rows
        return None
    if len(df) == 0:
        return None
    t = pd.to_datetime(df[0]).astype('int64').to_numpy() / 1e9
    values = df.drop(columns=[0]).to_numpy(dtype=np.float64)
    names, group = [], ''
    for i in range(1, df.shape[1]):
        label = header[i] if i < len(header) else 'Tag'
        group = label or group
        names.append(group)
    return t, values, names


def compact_upfall(cfg: dict) -> List[str]:
    raw = paths.RAW_DIR / cfg['raw']
    out = _out_dir('upfall')
    by_subject: Dict[str, List[Path]] = {}
    for f in raw.glob('Subject*Activity*Trial*.csv'):
        by_subject.setdefault(f.name.split('Activity')[0], []).append(f)
    done = []
    for subject, files in sorted(by_subject.items()):
        target = out / f'{subject}.npz'
        if not target.exists():
            arrays, columns, empty = {}, None, []
            for f in sorted(files):
                parsed = _read_upfall_csv(f)
                key = f.stem.replace(subject, '')  # ActivityXTrialY
                if parsed is None:
                    empty.append(key)
                    continue
                t, values, columns = parsed
                arrays[f'{key}__t'] = t
                arrays[key] = values
            arrays['__columns__'] = np.array(json.dumps(columns))
            arrays['__empty__'] = np.array(json.dumps(empty))
            _save(target, arrays)
            logger.info('upfall %s: %d trials (%d empty)', subject, len(files) - len(empty), len(empty))
        done.append(subject)
    return done


# ─── HIFD (.mat per trial, ~50 Hz, wrist) ────────────────────────────────────

HIFD_COLUMNS = ['w', 'x', 'y', 'z', 'droll', 'dpitch', 'dyaw', 'ax', 'ay', 'az', 'heart']


def compact_hifd(cfg: dict) -> List[str]:
    raw = paths.RAW_DIR / cfg['raw']
    out = _out_dir('hifd')
    done = []
    for subj_dir in sorted(raw.glob('subject_*')):
        target = out / f'{subj_dir.name}.npz'
        if not target.exists():
            arrays = {}
            for f in sorted(subj_dir.glob('*/*.mat')):
                m = sio.loadmat(f)
                key = f'{f.parent.name}__{f.stem}'
                arrays[key] = np.column_stack([m[c].astype(np.float64).ravel() for c in HIFD_COLUMNS])
                arrays[f'{key}__time'] = m['time'].astype(np.float64)
            arrays['__columns__'] = np.array(json.dumps(HIFD_COLUMNS))
            _save(target, arrays)
        done.append(subj_dir.name)
    return done


# ─── MIT-BIH (annotations only; RR series are derived from beat annotations) ─

def compact_mitbih(cfg: dict) -> List[str]:
    import wfdb

    raw = paths.RAW_DIR / cfg['raw']
    out = _out_dir('mitbih')
    done = []
    for hea in sorted(raw.glob('*.hea')):
        rec = hea.stem
        target = out / f'{rec}.npz'
        if not target.exists():
            ann = wfdb.rdann(str(raw / rec), 'atr')
            hdr = wfdb.rdheader(str(raw / rec))
            _save(target, {
                'ann_sample': np.asarray(ann.sample, dtype=np.int64),
                'ann_symbol': np.asarray(ann.symbol, dtype='U2'),
                'ann_aux': np.asarray([a.strip('\x00') for a in ann.aux_note], dtype='U16'),
                'fs': np.array(float(hdr.fs)),
                'sig_len': np.array(int(hdr.sig_len)),
            })
        done.append(rec)
    return done


# ─── AFDB / LTAFDB (annotations only, read from the PhysioNet zips) ──────────

def _compact_physionet_ann(name: str, zip_path: Path, beat_exts: List[str]) -> List[str]:
    """Rhythm annotations (.atr aux) plus beat times from the first available beat file."""
    import tempfile
    import wfdb

    out = _out_dir(name)
    done = []
    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory() as tmp:
        members = {Path(n).name: n for n in zf.namelist() if n.count('/') == 1}
        records = zf.read(members['RECORDS']).decode().split()
        for rec in records:
            target = out / f'{rec}.npz'
            if target.exists():
                done.append(rec)
                continue
            for ext in ['hea', 'atr'] + beat_exts:
                if f'{rec}.{ext}' in members:
                    (Path(tmp) / f'{rec}.{ext}').write_bytes(zf.read(members[f'{rec}.{ext}']))
            hdr = wfdb.rdheader(str(Path(tmp) / rec))
            atr = wfdb.rdann(str(Path(tmp) / rec), 'atr')
            beat_ext = next(e for e in beat_exts if (Path(tmp) / f'{rec}.{e}').exists())
            beats = atr if beat_ext == 'atr' else wfdb.rdann(str(Path(tmp) / rec), beat_ext)
            _save(target, {
                'ann_sample': np.asarray(atr.sample, dtype=np.int64),
                'ann_symbol': np.asarray(atr.symbol, dtype='U2'),
                'ann_aux': np.asarray([a.strip('\x00') for a in atr.aux_note], dtype='U16'),
                'beat_sample': np.asarray(beats.sample, dtype=np.int64),
                'beat_symbol': np.asarray(beats.symbol, dtype='U2'),
                'beat_source': np.array(beat_ext),
                'fs': np.array(float(hdr.fs)),
                'sig_len': np.array(int(hdr.sig_len or 0)),
            })
            logger.info('%s %s: %d beats (%s), %d rhythm marks', name, rec, len(beats.sample), beat_ext,
                        sum(a.startswith('(') for a in atr.aux_note))
            done.append(rec)
    return done


def compact_afdb(cfg: dict) -> List[str]:
    # .qrsc (manually corrected) exists for a few records; .qrs is the automatic detector
    return _compact_physionet_ann('afdb', paths.RAW_DIR / cfg['archive'], ['qrsc', 'qrs'])


def compact_ltafdb(cfg: dict) -> List[str]:
    # LTAFDB .atr carries reviewed beat labels as well as rhythm changes
    return _compact_physionet_ann('ltafdb', paths.RAW_DIR / cfg['archive'], ['atr'])


# ─── PAMAP2 (space-separated .dat, 100 Hz, nested zip) ───────────────────────

# Columns kept: timestamp, activityID, heart rate, dominant-wrist ("hand") IMU
# acc +-16 g (m/s^2) and gyro (rad/s). 1-based column numbers from the PAMAP2 readme.
PAMAP2_COLUMNS = {'t': 1, 'activity': 2, 'hr': 3, 'acc_x': 5, 'acc_y': 6, 'acc_z': 7,
                  'gyro_x': 11, 'gyro_y': 12, 'gyro_z': 13}


def compact_pamap2(cfg: dict) -> List[str]:
    out = _out_dir('pamap2')
    done = []
    with zipfile.ZipFile(paths.RAW_DIR / cfg['archive']) as outer:
        inner = zipfile.ZipFile(outer.open(cfg['archive_nested']))
        by_subject: Dict[str, Dict[str, str]] = {}
        for n in inner.namelist():
            if n.endswith('.dat'):
                session = Path(n).parent.name.lower()       # protocol | optional
                by_subject.setdefault(Path(n).stem, {})[session] = n
        for subject, sessions in sorted(by_subject.items()):
            target = out / f'{subject}.npz'
            if not target.exists():
                arrays = {}
                for session, member in sorted(sessions.items()):
                    with inner.open(member) as fh:
                        df = pd.read_csv(fh, sep=' ', header=None,
                                         usecols=[c - 1 for c in PAMAP2_COLUMNS.values()])
                    arrays[session] = df.to_numpy(dtype=np.float64)
                arrays['__columns__'] = np.array(json.dumps(list(PAMAP2_COLUMNS)))
                _save(target, arrays)
                logger.info('pamap2 %s: %s', subject, {k: v.shape for k, v in arrays.items()})
            done.append(subject)
    return done


# ─── Stress-Predict (Empatica E4 CSVs + per-second stress labels) ────────────

def compact_stress_predict(cfg: dict) -> List[str]:
    out = _out_dir('stress_predict')
    done = []
    with zipfile.ZipFile(paths.RAW_DIR / cfg['archive']) as zf:
        root = zf.namelist()[0].split('/')[0]
        labels = pd.read_csv(io.BytesIO(zf.read(f'{root}/Processed_data/Improved_All_Combined_hr_rsp_binary.csv')))
        for participant, g in labels.groupby('Participant'):
            subject = f'S{int(participant):02d}'
            target = out / f'{subject}.npz'
            if not target.exists():
                arrays = {}
                for stream in ('ACC', 'BVP', 'EDA', 'TEMP'):
                    raw = zf.read(f'{root}/Raw_data/{subject}/{stream}.csv').decode().splitlines()
                    arrays[f'{stream}_start'] = np.array(float(raw[0].split(',')[0]))
                    arrays[f'{stream}_fs'] = np.array(float(raw[1].split(',')[0]))
                    arrays[stream] = np.loadtxt(raw[2:], delimiter=',', ndmin=2 if stream == 'ACC' else 1)
                arrays['label_time'] = g['Time(sec)'].to_numpy(dtype=np.int64)
                arrays['label'] = g['Label'].to_numpy(dtype=np.int8)       # 0 baseline/rest, 1 stress task
                _save(target, arrays)
                logger.info('stress_predict %s: %s', subject, {k: v.shape for k, v in arrays.items() if v.ndim})
            done.append(subject)
    return done


COMPACTORS = {
    'wesad': compact_wesad, 'ppg_dalia': compact_ppg_dalia, 'sisfall': compact_sisfall,
    'upfall': compact_upfall, 'hifd': compact_hifd, 'mitbih': compact_mitbih,
    'afdb': compact_afdb, 'ltafdb': compact_ltafdb, 'pamap2': compact_pamap2,
    'stress_predict': compact_stress_predict,
}
VERIFIERS = {'sisfall': verify_sisfall}
DELETABLE_RAW = {'sisfall'}  # lossless + verified + original host offline -> npz is canonical


def delete_raw(name: str, cfg: dict) -> None:
    if name not in DELETABLE_RAW:
        raise ValueError(f'raw deletion not enabled for {name}')
    report = VERIFIERS[name](cfg)
    if not report['ok']:
        raise RuntimeError(f'{name}: verification failed, raw kept: {report}')
    raw = paths.RAW_DIR / cfg['raw']
    shutil.rmtree(raw)
    logger.info('%s: verified %d trials, deleted %s', name, report['trials'], raw)


def main() -> None:
    parser = argparse.ArgumentParser(description='Compact raw wearable datasets')
    parser.add_argument('datasets', nargs='*', default=list(COMPACTORS))
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--delete-raw', action='store_true',
                        help='delete raw data after successful verification (sisfall only)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    registry = load_registry()
    for name in args.datasets:
        cfg = registry[name]
        subjects = COMPACTORS[name](cfg)
        logger.info('%s: %d subjects/records compacted', name, len(subjects))
        if args.verify and name in VERIFIERS:
            logger.info('%s verification: %s', name, VERIFIERS[name](cfg))
        if args.delete_raw and name in DELETABLE_RAW:
            delete_raw(name, cfg)


if __name__ == '__main__':
    main()
