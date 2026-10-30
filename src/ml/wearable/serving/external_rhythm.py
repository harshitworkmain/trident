"""External test of the registry rhythm head on real PPG: MIMIC PERform AF (35 ICU adults, 19 AF).

The head was trained on ECG RR (MIT-BIH/AFDB/LTAFDB) with PPG-like augmentation and has never
seen real PPG. Each recording is replayed twice through the serving feature path, so the gap
between the two is the cost of PPG beat detection, not of the model:

* `ppg` - beats detected from the fingertip PPG by the emulator (the device path)
* `ecg` - lead-II ECG R-peaks (reference)

Labels are per subject (AF / non-AF), so every window inherits its subject's label. No model is
retrained or changed.

    python -m src.ml.wearable.serving.external_rhythm
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List

import numpy as np
from sklearn.metrics import f1_score, roc_auc_score

from .. import paths
from ..data.loaders import load_mimic_perform_af
from ..emulator import emulate
from ..features.engine import replay
from ..schema import FIELD_NAMES
from .runtime import HEAD_STRIDE, head_available, load_heads

logger = logging.getLogger('wearable.external_rhythm')

OUT_JSON = paths.DATA_ROOT / 'processed' / 'wearable' / 'external' / 'mimic_perform_af.json'
N_BOOT = 1000


def _windows(frames, model) -> Dict[str, list]:
    """Rhythm windows at the head's serving stride: availability and P(abnormal) when available."""
    values = frames[FIELD_NAMES].to_dict('records')
    rr = [list(x) for x in frames['rr_ms']]
    block = frames[FIELD_NAMES].to_numpy(dtype=np.float64)
    T = model.T
    avail, xs, ss = [], [], []
    for end, tab, seq in replay(values, rr, model.feature_set, HEAD_STRIDE['rhythm']):
        ok = head_available('rhythm', block[end - T + 1:end + 1], rr[end - T + 1:end + 1])
        avail.append(ok)
        if ok:
            xs.append([tab[f] for f in model.entry['features']])
            ss.append(seq)
    proba = model.predict(np.array(xs), np.stack(ss))[:, 1] if xs else np.empty(0)
    return {'available': avail, 'proba': proba.tolist()}


def _metrics(y: np.ndarray, p: np.ndarray, thr: float) -> Dict[str, float]:
    pred = (p >= thr).astype(int)
    return {
        'n': int(len(y)), 'n_af': int(y.sum()),
        'auroc': float(roc_auc_score(y, p)) if len(set(y)) == 2 else float('nan'),
        'sensitivity': float(pred[y == 1].mean()) if (y == 1).any() else float('nan'),
        'specificity': float(1 - pred[y == 0].mean()) if (y == 0).any() else float('nan'),
        'macro_f1': float(f1_score(y, pred, average='macro')),
    }


def _evaluate(per_subject: List[dict], path: str, thr: float, seed: int = 42) -> dict:
    subj = [s for s in per_subject if s[path]['proba']]
    y_w = np.concatenate([[s['af']] * len(s[path]['proba']) for s in subj])
    p_w = np.concatenate([s[path]['proba'] for s in subj])
    y_s = np.array([s['af'] for s in subj])
    p_s = np.array([np.median(s[path]['proba']) for s in subj])
    n_win = sum(len(s[path]['available']) for s in per_subject)
    n_ok = sum(sum(s[path]['available']) for s in per_subject)
    out = {
        'windows_total': n_win, 'windows_available': n_ok,
        'availability_pct': 100.0 * n_ok / max(n_win, 1),
        'subjects_with_windows': len(subj),
        'window': _metrics(y_w, p_w, thr),
        'subject_median': _metrics(y_s, p_s, thr),
    }
    # Subject-level bootstrap: resample subjects (windows of one subject are not independent)
    rng = np.random.default_rng(seed)
    idx_af, idx_non = np.flatnonzero(y_s == 1), np.flatnonzero(y_s == 0)
    boots = {'window_auroc': [], 'window_macro_f1': [], 'subject_auroc': []}
    for _ in range(N_BOOT):
        pick = np.concatenate([rng.choice(idx_af, len(idx_af)), rng.choice(idx_non, len(idx_non))])
        yw = np.concatenate([[y_s[i]] * len(subj[i][path]['proba']) for i in pick])
        pw = np.concatenate([subj[i][path]['proba'] for i in pick])
        boots['window_auroc'].append(roc_auc_score(yw, pw))
        boots['window_macro_f1'].append(f1_score(yw, (pw >= thr).astype(int), average='macro'))
        boots['subject_auroc'].append(roc_auc_score(y_s[pick], p_s[pick]))
    out['ci95'] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in boots.items()}
    return out


def run() -> dict:
    model = load_heads(heads=['rhythm'])['rhythm']
    thr = float(model.threshold)
    per_subject = []
    for rec in load_mimic_perform_af(with_ecg_beats=True):
        ecg_beats = rec.meta.pop('ecg_beats_s')
        ppg_frames = emulate(rec)
        ecg_frames = emulate(rec, beats_s=ecg_beats)
        n_ppg_beats = sum(len(r) for r in ppg_frames['rr_ms'])
        n_ecg_beats = sum(len(r) for r in ecg_frames['rr_ms'])
        row = {'subject': rec.subject, 'af': int(rec.meta['af']),
               'rr_accepted': {'ppg': n_ppg_beats, 'ecg': n_ecg_beats},
               'ppg': _windows(ppg_frames, model), 'ecg': _windows(ecg_frames, model)}
        logger.info('%s af=%d  ppg %d/%d win  ecg %d/%d win  median p ppg=%.2f ecg=%.2f', rec.subject, row['af'],
                    sum(row['ppg']['available']), len(row['ppg']['available']),
                    sum(row['ecg']['available']), len(row['ecg']['available']),
                    np.median(row['ppg']['proba']) if row['ppg']['proba'] else np.nan,
                    np.median(row['ecg']['proba']) if row['ecg']['proba'] else np.nan)
        per_subject.append(row)
    result = {
        'dataset': 'MIMIC PERform AF (Zenodo 10.5281/zenodo.6807403, WFDB zips)',
        'head': {'version': model.entry['version'], 'members': model.entry['members'], 'threshold': thr,
                 'stride_frames': HEAD_STRIDE['rhythm'], 'window_frames': model.T},
        'subjects': len(per_subject), 'subjects_af': sum(s['af'] for s in per_subject),
        'paths': {p: _evaluate(per_subject, p, thr) for p in ('ppg', 'ecg')},
        'per_subject': [{'subject': s['subject'], 'af': s['af'], 'rr_accepted': s['rr_accepted'],
                         **{f'{p}_available_pct': 100.0 * float(np.mean(s[p]['available'])) for p in ('ppg', 'ecg')},
                         **{f'{p}_median_proba': float(np.median(s[p]['proba'])) if s[p]['proba'] else None
                            for p in ('ppg', 'ecg')}}
                        for s in per_subject],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding='utf-8')
    logger.info('wrote %s', OUT_JSON)
    return result


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    run()
