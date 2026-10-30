"""Tier-1 head definitions and their training datasets.

For every head this module defines which emulated recordings it learns from, how windows
are labelled, how subjects are grouped for cross-validation, and builds the table by
replaying each recording through the online FeatureEngine (training == serving).

Output per head (under data/processed/wearable/heads/):
    <head>.parquet   meta + label + split + group + tabular features (one row per window)
    <head>_seq.npy   float32 (rows, T, C) sequences aligned with the parquet rows

Splits: `cv` rows enter the tournament (subject-grouped CV); `external` rows are only ever
tested (fall: HIFD); `replay` rows are fall-free daily life from people never used for
training, used to count false alarms.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from multiprocessing import Pool
from typing import Callable, Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd

from .. import paths
from ..data.loaders import load_afdb, load_ltafdb, load_mitbih
from ..emulator import emulate
from ..features.engine import replay
from ..features.frame_features import FEATURE_SETS
from ..schema import FIELD_NAMES
from .augment import PPGNoise, ppg_like_beats

logger = logging.getLogger(__name__)
HEADS_DIR = paths.DATA_ROOT / 'processed' / 'wearable' / 'heads'
MIN_PURITY = 0.8
BUILDER_VERSION = '2.0.0'
WORKERS = 3

# Label maps (source codes -> head classes); None = window excluded.
# Stress: WESAD protocol ids; Stress-Predict (external test) is loaded with the same ids (1 rest, 2 stress).
STRESS_PROTOCOL = {1: 0, 2: 1, 3: 0}                    # baseline, stress, amusement
# Activity intensity, behaviour-based like Walmsley et al. 2020 (rest / light / active):
DALIA_ACTIVITY = {1: 0, 5: 0, 6: 0, 8: 0,               # sitting, driving, lunch, working -> rest
                  3: 1,                                  # table soccer -> light
                  2: 2, 4: 2, 7: 2}                      # stairs, cycling, walking -> active
PAMAP2_ACTIVITY = {1: 0, 2: 0, 9: 0, 10: 0, 11: 0,      # lying, sitting, TV, computer, driving -> rest
                   3: 1, 16: 1, 17: 1, 18: 1, 19: 1,    # standing, vacuuming, ironing, laundry, cleaning -> light
                   4: 2, 5: 2, 6: 2, 7: 2, 12: 2, 13: 2, 20: 2, 24: 2}  # walk, run, cycle, stairs, sport -> active
WALMSLEY_ACTIVITY = {0: 0, 1: 0, 2: 1, 3: 2}            # sleep, sedentary -> rest; light; MVPA -> active
ACTIVITY_MAPS = {'ppg_dalia': DALIA_ACTIVITY, 'pamap2': PAMAP2_ACTIVITY, 'capture24': WALMSLEY_ACTIVITY}
ACTIVITY_COLUMN = {'ppg_dalia': 'y_activity', 'pamap2': 'y_activity', 'capture24': 'y_walmsley'}
RHYTHM_REGULAR = {'(N', '(SBR'}
RHYTHM_ABNORMAL = {'(AFIB', '(AFL', '(B', '(T', '(VT', '(VFL', '(SVTA', '(IVR', '(AB', '(BII', '(NOD', '(J'}
HR_TRUST_TOL_BPM = 10.0
MITBIH_SAME_PATIENT = {'202': '201'}
# Rhythm sources: (loader, PPG-noise copies, stride in frames). Long Holter records are
# sub-sampled so the 24 h LTAFDB records do not swamp the 30 min MIT-BIH records.
RHYTHM_SOURCES = {'mitbih': (load_mitbih, 2, 4), 'afdb': (load_afdb, 1, 20), 'ltafdb': (load_ltafdb, 1, 60)}

# Fall head: daily-life negatives
FALL_DAILY_LIFE_STRIDE = 2           # PPG-DaLiA, WESAD, PAMAP2 (every 3 s)
CAPTURE24_CV_STRIDE = 20             # background windows every 30 s ...
CAPTURE24_HARD_PEAK_G = 1.8          # ... plus every window containing a motion spike
CAPTURE24_HARD_TROUGH_G = 0.4
CAPTURE24_HARD_CAP = 1500            # per participant, random subset when exceeded
CAPTURE24_ACTIVITY_STRIDE = 80       # 30 s windows every 2 min


def capture24_fall_split(pid: str) -> str:
    """One third of Capture-24 participants are held out entirely for the false-alarm replay."""
    return 'replay' if int(hashlib.sha256(pid.encode()).hexdigest()[:8], 16) % 3 == 0 else 'cv'


@dataclass
class Recording:
    """A recording's frames plus the context its label function needs."""
    dataset: str
    subject: str
    trial: str
    frames: pd.DataFrame
    split: str = 'cv'
    stride: Optional[int] = None                 # overrides HeadSpec.stride
    extra_ends: Tuple[int, ...] = ()
    context: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class HeadSpec:
    name: str
    feature_set: str
    classes: Tuple[str, ...]
    stride: int
    recordings: Callable[[], Iterator[Recording]]
    label: Callable[[Recording, int, int], Optional[int]]   # (rec, start, end) -> class / None
    primary_metric: str = 'macro_f1'

    @property
    def T(self) -> int:
        return FEATURE_SETS[self.feature_set].T


# ─── recording sources ───────────────────────────────────────────────────────

def _recordings(dataset: str, split: str = 'cv', stride: Optional[int] = None) -> Iterator[Recording]:
    path = paths.FRAMES_DIR / dataset
    if path.is_dir():                                    # partitioned: one parquet per recording
        for f in sorted(path.glob('*.parquet')):
            df = pd.read_parquet(f)
            yield Recording(dataset, str(df['subject'].iloc[0]), str(df['trial'].iloc[0]), df, split, stride)
        return
    df = pd.read_parquet(paths.FRAMES_DIR / f'{dataset}.parquet')
    for (subject, trial), g in df.groupby(['subject', 'trial'], sort=True):
        yield Recording(dataset, str(subject), str(trial), g.sort_values('frame').reset_index(drop=True),
                        split, stride)


def _impact_frame(rec: Recording) -> int:
    """Frame of the fall impact: peak |acc| (UP-Fall: restricted to frames tagged as falling)."""
    f = rec.frames
    candidates = f
    if 'y_tag' in f.columns:
        tagged = f[f['y_tag'].between(1, 5)]
        if len(tagged):
            candidates = tagged
    return int(candidates['imu_acc_max_g'].idxmax())


def _hard_ends(frames: pd.DataFrame, T: int, seed: str) -> Tuple[int, ...]:
    """Ends of every window that contains a motion spike (label-free hard-negative mining)."""
    hot = np.flatnonzero((frames['imu_acc_max_g'] >= CAPTURE24_HARD_PEAK_G).to_numpy() |
                         (frames['imu_acc_min_g'] <= CAPTURE24_HARD_TROUGH_G).to_numpy())
    ends = np.unique(np.clip(hot[:, None] + np.arange(T), T - 1, len(frames) - 1))
    if len(ends) > CAPTURE24_HARD_CAP:
        rng = np.random.default_rng(int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16))
        ends = np.sort(rng.choice(ends, CAPTURE24_HARD_CAP, replace=False))
    return tuple(int(e) for e in ends)


def _fall_recordings() -> Iterator[Recording]:
    T = FEATURE_SETS['fall_acc_only'].T
    for name, split in (('upfall', 'cv'), ('sisfall', 'cv'), ('hifd', 'external')):
        for rec in _recordings(name, split):
            if bool(rec.frames['m_is_fall'].iloc[0]):
                rec.context['impact'] = _impact_frame(rec)
            yield rec
    for name in ('ppg_dalia', 'wesad', 'pamap2'):
        yield from _recordings(name, 'cv', FALL_DAILY_LIFE_STRIDE)
    for rec in _recordings('capture24'):
        rec.split = capture24_fall_split(rec.subject)
        if rec.split == 'cv':
            rec.stride = CAPTURE24_CV_STRIDE
            rec.extra_ends = _hard_ends(rec.frames, T, rec.subject)
        yield rec


def _rhythm_recordings() -> Iterator[Recording]:
    for dataset, (loader, copies, stride) in RHYTHM_SOURCES.items():
        for rec in loader():
            for k in range(copies):
                seed = int(hashlib.sha256(f'{dataset}:{rec.subject}:{k}'.encode()).hexdigest()[:8], 16)
                rng = np.random.default_rng(seed)
                noise = PPGNoise.sample(rng)
                frames = emulate(rec, beats_s=ppg_like_beats(rec.beats_s, noise, rng))
                subject = MITBIH_SAME_PATIENT.get(rec.subject, rec.subject) if dataset == 'mitbih' else rec.subject
                yield Recording(dataset, subject, f'{rec.subject}_aug{k}', frames, stride=stride,
                                context={'noise': noise.__dict__})


def _stress_recordings() -> Iterator[Recording]:
    # Stress-Predict is an external test only: pooling it into training lowered WESAD out-of-fold
    # macro-F1 (smoke run 0.834 vs 0.885) because its protocol labels inter-task relaxation as
    # non-stress and counts hyperventilation/interview as stress - a different target definition.
    yield from _recordings('wesad')
    yield from _recordings('stress_predict', 'external')


def _activity_recordings() -> Iterator[Recording]:
    # PAMAP2 is an external test only: its light/active split runs the other way at the wrist
    # (PPG-DaLiA "light" = table soccer moves the wrist more than its walking/cycling "active").
    # Pooling it cost PPG-DaLiA 0.90 -> 0.83 macro-F1, while Capture-24's MET-based labels agree
    # with PPG-DaLiA (tournament/activity_capture24_check.json).
    yield from _recordings('ppg_dalia')
    yield from _recordings('capture24', stride=CAPTURE24_ACTIVITY_STRIDE)
    yield from _recordings('pamap2', 'external')


def _chain(*datasets: str) -> Callable[[], Iterator[Recording]]:
    def gen() -> Iterator[Recording]:
        for d in datasets:
            yield from _recordings(d)
    return gen


# ─── label functions ─────────────────────────────────────────────────────────

def _mode(values: pd.Series) -> Tuple[object, float]:
    counts = values.value_counts()
    if counts.empty:
        return None, 0.0
    return counts.index[0], counts.iloc[0] / len(values)


def label_stress(rec: Recording, s: int, e: int) -> Optional[int]:
    mode, purity = _mode(rec.frames['y_protocol'].iloc[s:e + 1])
    return STRESS_PROTOCOL.get(mode) if purity >= MIN_PURITY else None


def label_activity(rec: Recording, s: int, e: int) -> Optional[int]:
    mode, purity = _mode(rec.frames[ACTIVITY_COLUMN[rec.dataset]].iloc[s:e + 1])
    return ACTIVITY_MAPS[rec.dataset].get(mode) if purity >= MIN_PURITY else None


def label_hr_trust(rec: Recording, s: int, e: int) -> Optional[int]:
    tail = rec.frames.iloc[max(s, e - 2):e + 1]
    bpm = rec.frames['ppg_bpm'].iloc[e]
    ref = tail['y_hr_ecg'].dropna()
    if not np.isfinite(bpm) or ref.empty:
        return None
    return int(abs(bpm - ref.iloc[-1]) <= HR_TRUST_TOL_BPM)


def label_rhythm(rec: Recording, s: int, e: int) -> Optional[int]:
    mode, purity = _mode(rec.frames['y_rhythm'].iloc[s:e + 1].dropna())
    if purity < MIN_PURITY:
        return None
    return 0 if mode in RHYTHM_REGULAR else 1 if mode in RHYTHM_ABNORMAL else None


def label_fall(rec: Recording, s: int, e: int) -> Optional[int]:
    impact = rec.context.get('impact')
    if impact is None:
        return 0                       # ADL trials and daily life: every window negative
    return 1 if s <= impact <= e else None  # fall trial: only the impact windows are labelled


# The fall head uses accelerometer-only features: most daily-life sources (PPG-DaLiA, WESAD,
# Capture-24) have no gyroscope, and mixing gyro-present falls with gyro-missing negatives
# would let a model learn "gyro missing => no fall". v1 showed gyro adds ~0.004 macro-F1.
HEADS: Dict[str, HeadSpec] = {h.name: h for h in [
    HeadSpec('stress', 'stress', ('non_stress', 'stress'), 4, _stress_recordings, label_stress),
    HeadSpec('fall', 'fall_acc_only', ('no_fall', 'fall'), 1, _fall_recordings, label_fall),
    HeadSpec('activity', 'activity', ('rest', 'light', 'active'), 4, _activity_recordings, label_activity),
    HeadSpec('hr_trust', 'hr_trust', ('unreliable', 'reliable'), 2, _chain('ppg_dalia', 'wesad'), label_hr_trust),
    HeadSpec('rhythm', 'rhythm', ('regular', 'abnormal'), 4, _rhythm_recordings, label_rhythm),
]}


# ─── builder ─────────────────────────────────────────────────────────────────

def _windows(args: Tuple[str, Recording]) -> Optional[Tuple[pd.DataFrame, np.ndarray]]:
    """Replay one recording through the FeatureEngine and label its windows (worker process)."""
    head, rec = args
    spec = HEADS[head]
    f = rec.frames
    values = f[FIELD_NAMES].to_dict('records')
    rr = [list(x) for x in f['rr_ms']]
    meta, tabs, seqs = [], [], []
    for end, tab, seq in replay(values, rr, spec.feature_set, rec.stride or spec.stride, extra_ends=rec.extra_ends):
        y = spec.label(rec, end - spec.T + 1, end)
        if y is None:
            continue
        meta.append((end, float(f['t_start'].iloc[end]), int(y)))
        tabs.append(tab)
        seqs.append(seq)
    if not meta:
        return None
    m = np.array(meta)
    table = pd.DataFrame({'dataset': rec.dataset, 'subject': rec.subject, 'trial': rec.trial,
                          'group': f'{rec.dataset}:{rec.subject}', 'split': rec.split,
                          'end_frame': m[:, 0].astype(np.int64), 't_end': m[:, 1], 'y': m[:, 2].astype(np.int64)})
    table = pd.concat([table, pd.DataFrame(tabs, dtype=np.float32)], axis=1)
    return table, np.stack(seqs).astype(np.float32)


def _batches(head: str, recs: Iterator[Recording], max_frames: int = 400_000, max_items: int = 256):
    """Group recordings into bounded batches so the pool never holds every recording in RAM."""
    batch, frames = [], 0
    for rec in recs:
        batch.append((head, rec))
        frames += len(rec.frames)
        if frames >= max_frames or len(batch) >= max_items:
            yield batch
            batch, frames = [], 0
    if batch:
        yield batch


def build_head(name: str) -> pd.DataFrame:
    spec = HEADS[name]
    tables, seqs = [], []
    with Pool(WORKERS) as pool:
        for batch in _batches(name, spec.recordings()):
            for res in pool.map(_windows, batch, chunksize=max(1, len(batch) // (WORKERS * 4))):
                if res is not None:
                    tables.append(res[0])
                    seqs.append(res[1])
            logger.info('%s: %d windows so far', name, sum(len(t) for t in tables))
    table = pd.concat(tables, ignore_index=True)
    HEADS_DIR.mkdir(parents=True, exist_ok=True)
    table.to_parquet(HEADS_DIR / f'{name}.parquet', index=False)
    np.save(HEADS_DIR / f'{name}_seq.npy', np.concatenate(seqs))
    summary = head_summary(name, table)
    (HEADS_DIR / f'{name}.meta.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    logger.info('%s: %s', name, summary['counts'])
    return table


def head_summary(name: str, table: pd.DataFrame) -> dict:
    spec = HEADS[name]
    counts, by_dataset = {}, {}
    for split, g in table.groupby('split'):
        counts[split] = {'windows': len(g), 'groups': int(g['group'].nunique()),
                         'classes': {spec.classes[k]: int(v) for k, v in g['y'].value_counts().sort_index().items()}}
    for (split, ds), g in table.groupby(['split', 'dataset']):
        by_dataset[f'{split}:{ds}'] = {'windows': len(g), 'groups': int(g['group'].nunique()),
                                       'classes': {spec.classes[k]: int(v) for k, v in g['y'].value_counts().sort_index().items()}}
    return {'head': name, 'feature_set': spec.feature_set, 'T': spec.T, 'stride': spec.stride,
            'classes': list(spec.classes), 'builder_version': BUILDER_VERSION,
            'features': [c for c in table.columns if c not in META_COLUMNS], 'counts': counts,
            'by_dataset': by_dataset}


META_COLUMNS = ['dataset', 'subject', 'trial', 'group', 'split', 'end_frame', 't_end', 'y']


def load_head(name: str) -> Tuple[pd.DataFrame, np.ndarray]:
    import pyarrow.parquet as pq
    # string metadata as categoricals: the fall table has ~4M rows and RAM is limited
    table = pq.read_table(HEADS_DIR / f'{name}.parquet',
                          read_dictionary=['dataset', 'subject', 'trial', 'group', 'split']).to_pandas()
    seq = np.load(HEADS_DIR / f'{name}_seq.npy')
    assert len(table) == len(seq), f'{name}: table/sequence misaligned'
    return table, seq


def feature_columns(table: pd.DataFrame) -> List[str]:
    return [c for c in table.columns if c not in META_COLUMNS]
