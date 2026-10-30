"""P5: replay real recordings through the full serving path (registry heads + fusion) and count states.

* daily life (no trauma events): every critical state entered is a false alarm. Held-out Capture-24
  people and Stress-Predict were never used to train the fall/activity heads; PPG-DaLiA, WESAD and
  PAMAP2 were (in-sample for some heads), so their counts are optimistic.
* WESAD: ELEVATED_STRESS time share per protocol phase (baseline / stress / amusement).
* HIFD (external fall set): each trial followed by 60 s of its final frame repeated (semi-synthetic
  lying still) - CONCUSSIVE_STASIS should follow falls, not ADL trials.

    python -m src.ml.wearable.pipeline replay
"""

from __future__ import annotations

import json
import logging
from multiprocessing import Pool
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .. import paths
from ..schema import FRAME_PERIOD_S
from .runtime import load_heads, replay_frames

logger = logging.getLogger('wearable.replay')

REPLAY_DIR = paths.DATA_ROOT / 'processed' / 'wearable' / 'replay'
REPORT_MD = paths.PROJECT_ROOT / 'docs' / 'reports' / 'WEARABLE_FUSION_REPLAY.md'
DAILY_LIFE = ('ppg_dalia', 'wesad', 'pamap2', 'stress_predict', 'capture24')
IN_SAMPLE = {'ppg_dalia': 'fall, activity, hr_trust', 'wesad': 'stress, fall, hr_trust',
             'pamap2': 'fall', 'stress_predict': 'none (stress external)', 'capture24': 'none (held-out people)'}
CRITICAL = ('CARDIAC_ARREST', 'ASPIRATION_HYPOXIA', 'HEMORRHAGIC_SHOCK', 'CONCUSSIVE_STASIS', 'CRUSH_ENTRAPMENT',
            'HYPOTHERMIA_RISK')
WESAD_PHASES = {1: 'baseline', 2: 'stress', 3: 'amusement'}
STASIS_PAD_S = 60.0

_MODELS = None


def _init():
    global _MODELS
    _MODELS = load_heads()


def _summarise(dataset: str, frames: pd.DataFrame, outs: List[dict]) -> dict:
    states = [o['ml_health_state'] for o in outs]
    entries: Dict[str, int] = {}
    prev = 'STABLE'
    for s in states:
        if s != prev and s != 'STABLE':
            entries[s] = entries.get(s, 0) + 1
        prev = s
    time_in = pd.Series(states).value_counts().to_dict()
    res = {'frames': len(states), 'entries': entries, 'frames_in_state': {k: int(v) for k, v in time_in.items()},
           'sensor_fault_frames': int(sum(o['sensor_fault'] for o in outs)),
           'head_available_frames': {h: int(sum(o['heads'].get(h) is not None for o in outs))
                                     for h in ('stress', 'fall', 'activity', 'hr_trust', 'rhythm')},
           'evidence_samples': {}}
    for i, o in enumerate(outs):
        if o['ml_health_state'] != 'STABLE' and o['ml_health_state'] not in res['evidence_samples']:
            res['evidence_samples'][o['ml_health_state']] = {'t_s': round(i * FRAME_PERIOD_S, 1), 'evidence': o['evidence']}
    if dataset == 'wesad' and 'y_protocol' in frames.columns:
        stressed = np.array([s == 'ELEVATED_STRESS' for s in states])
        res['stress_by_phase'] = {name: [int(stressed[(frames['y_protocol'] == code).to_numpy()].sum()),
                                         int((frames['y_protocol'] == code).sum())]
                                  for code, name in WESAD_PHASES.items()}
    return res


def _replay_one(args) -> dict:
    dataset, key, frames = args
    if isinstance(frames, str):                                   # partitioned recording: path
        frames = pd.read_parquet(frames)
    frames = frames.reset_index(drop=True)
    res = _summarise(dataset, frames, replay_frames(frames, _MODELS))
    res.update({'dataset': dataset, 'recording': key})
    return res


def _stasis_case(rec: pd.DataFrame) -> pd.DataFrame:
    """Trial followed by its final frame repeated for STASIS_PAD_S (semi-synthetic lying still)."""
    n = int(STASIS_PAD_S / FRAME_PERIOD_S)
    last = rec.iloc[[-1] * n].copy()
    last['frame'] = np.arange(len(rec), len(rec) + n)
    return pd.concat([rec, last], ignore_index=True)


def _fall_one(args) -> dict:
    key, frames, is_fall = args
    frames = _stasis_case(frames.reset_index(drop=True))
    outs = replay_frames(frames, _MODELS)
    n_trial = len(frames) - int(STASIS_PAD_S / FRAME_PERIOD_S)
    stasis = [i for i, o in enumerate(outs) if o['ml_health_state'] == 'CONCUSSIVE_STASIS']
    impact = int(np.argmax(frames['imu_acc_max_g'].to_numpy()[:n_trial]))
    return {'recording': key, 'is_fall': bool(is_fall), 'stasis': bool(stasis),
            'latency_s': round((stasis[0] - impact) * FRAME_PERIOD_S, 1) if stasis else None,
            'fall_p_max': max((o['heads'].get('fall') or 0.0) for o in outs[:n_trial])}


def _daily_jobs(dataset: str):
    from ..heads.build import capture24_fall_split
    if dataset == 'capture24':
        for f in sorted((paths.FRAMES_DIR / 'capture24').glob('*.parquet')):
            if capture24_fall_split(f.stem) == 'replay':
                yield dataset, f.stem, str(f)
        return
    df = pd.read_parquet(paths.FRAMES_DIR / f'{dataset}.parquet')
    for (s, t), g in df.groupby(['subject', 'trial'], sort=True):
        yield dataset, f'{s}/{t}', g.sort_values('frame')


def _aggregate(rows: List[dict]) -> dict:
    frames = sum(r['frames'] for r in rows)
    hours = frames * FRAME_PERIOD_S / 3600
    entries: Dict[str, int] = {}
    time_in: Dict[str, int] = {}
    for r in rows:
        for k, v in r['entries'].items():
            entries[k] = entries.get(k, 0) + v
        for k, v in r['frames_in_state'].items():
            time_in[k] = time_in.get(k, 0) + v
    crit = sum(v for k, v in entries.items() if k in CRITICAL)
    out = {'recordings': len(rows), 'hours': round(hours, 2),
           'critical_alarms': crit, 'critical_alarms_per_8h': round(8 * crit / hours, 3) if hours else None,
           'entries': entries, 'entries_per_8h': {k: round(8 * v / hours, 3) for k, v in entries.items()},
           'time_share': {k: round(v / frames, 4) for k, v in sorted(time_in.items())},
           'sensor_fault_share': round(sum(r['sensor_fault_frames'] for r in rows) / frames, 4),
           'head_available_share': {h: round(sum(r['head_available_frames'][h] for r in rows) / frames, 3)
                                    for h in rows[0]['head_available_frames']},
           'evidence_samples': {}}
    for r in rows:
        for k, v in r['evidence_samples'].items():
            out['evidence_samples'].setdefault(k, {'recording': r['recording'], **v})
    if any('stress_by_phase' in r for r in rows):
        out['stress_by_phase'] = {}
        for ph in WESAD_PHASES.values():
            num = sum(r['stress_by_phase'][ph][0] for r in rows if 'stress_by_phase' in r)
            den = sum(r['stress_by_phase'][ph][1] for r in rows if 'stress_by_phase' in r)
            out['stress_by_phase'][ph] = round(num / den, 3) if den else None
    return out


def run_replay(datasets: Optional[List[str]] = None, workers: int = 3) -> dict:
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    reg = json.loads((paths.MODELS_DIR / 'registry.json').read_text(encoding='utf-8'))
    result = {'models': {h: {'version': e['version'], 'members': e['members'], 'threshold': e.get('threshold')}
                         for h, e in reg['heads'].items()}, 'daily_life': {}, 'falls': None}
    from .fusion import load_fusion_config
    fcfg = load_fusion_config()
    result['fusion'] = {'version': fcfg['version'], 'head_thresholds': fcfg.get('head_thresholds') or {}}
    previous = REPLAY_DIR / 'p5_replay.json'
    if datasets and previous.exists():            # partial rerun: keep the other datasets' results
        result['daily_life'] = json.loads(previous.read_text(encoding='utf-8'))['daily_life']
    with Pool(workers, initializer=_init) as pool:
        for ds in datasets or DAILY_LIFE:
            rows = list(pool.imap_unordered(_replay_one, _daily_jobs(ds)))
            result['daily_life'][ds] = {'in_sample_heads': IN_SAMPLE[ds], **_aggregate(rows)}
            logger.info('%s: %s', ds, {k: result['daily_life'][ds][k] for k in ('hours', 'critical_alarms_per_8h', 'entries')})
            (REPLAY_DIR / f'{ds}_recordings.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
        hifd = pd.read_parquet(paths.FRAMES_DIR / 'hifd.parquet')
        jobs = [(f'{s}/{t}', g.sort_values('frame'), bool(g['m_is_fall'].iloc[0]))
                for (s, t), g in hifd.groupby(['subject', 'trial'], sort=True)]
        falls = list(pool.imap_unordered(_fall_one, jobs))
    f = pd.DataFrame(falls)
    lat = f.loc[f['is_fall'] & f['stasis'], 'latency_s']
    result['falls'] = {
        'dataset': 'hifd (external; trials + 60 s final frame repeated = semi-synthetic lying still)',
        'fall_trials': int(f['is_fall'].sum()), 'adl_trials': int((~f['is_fall']).sum()),
        'stasis_after_fall_rate': round(float(f.loc[f['is_fall'], 'stasis'].mean()), 3),
        'stasis_after_adl_rate': round(float(f.loc[~f['is_fall'], 'stasis'].mean()), 3),
        'latency_s_median': float(lat.median()) if len(lat) else None,
        'latency_s_range': [float(lat.min()), float(lat.max())] if len(lat) else None,
    }
    logger.info('hifd: %s', result['falls'])
    (REPLAY_DIR / 'p5_replay.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    REPORT_MD.write_text(_markdown(result), encoding='utf-8')
    return result


def _markdown(r: dict) -> str:
    lines = ['# Wearable ML — Tier-2 fusion replay on real data (P5, generated)', '',
             'Generated by `python -m src.ml.wearable.pipeline replay`. Every frame of each recording goes through the '
             'serving path: online `FeatureEngine` → registry ONNX heads (calibrated, at their training stride, '
             'inputs checked) → `FusionEngine`. No synthetic trauma data is used except the HIFD stasis padding below.', '',
             f"Fusion engine {r['fusion']['version']}; fusion operating points (override the Tier-1 registry "
             f"thresholds): {r['fusion']['head_thresholds'] or 'none'}.", '',
             '## Models', '', '| Head | Version | Members | Tier-1 threshold |', '|---|---|---|---|']
    for h, m in r['models'].items():
        lines.append(f"| {h} | {m['version']} | {' + '.join(m['members'])} | {m['threshold'] if m['threshold'] is not None else 'argmax'} |")
    lines += ['', '## Daily life — every critical state is a false alarm', '',
              'Critical = all states except ELEVATED_STRESS. Rates are state *entries* per 8 h of wear.', '',
              '| Dataset | Heads trained on it | Recordings | Hours | Critical alarms / 8 h | Entries / 8 h by state | Sensor-fault time |',
              '|---|---|---|---|---|---|---|']
    for ds, d in r['daily_life'].items():
        per = ', '.join(f'{k} {v}' for k, v in sorted(d['entries_per_8h'].items())) or '—'
        lines.append(f"| {ds} | {d['in_sample_heads']} | {d['recordings']} | {d['hours']} | {d['critical_alarms_per_8h']} | "
                     f"{per} | {100 * d['sensor_fault_share']:.1f} % |")
    lines += ['', '**Head availability (share of frames with an output):**', '']
    for ds, d in r['daily_life'].items():
        lines.append(f"- {ds}: " + ', '.join(f'{h} {100 * v:.0f} %' for h, v in d['head_available_share'].items()))
    w = r['daily_life'].get('wesad', {}).get('stress_by_phase')
    if w:
        lines += ['', '## WESAD — ELEVATED_STRESS time share by protocol phase', '',
                  '| Baseline | Stress (TSST) | Amusement |', '|---|---|---|',
                  f"| {100 * w['baseline']:.1f} % | {100 * w['stress']:.1f} % | {100 * w['amusement']:.1f} % |"]
    f = r['falls']
    lines += ['', '## Falls → CONCUSSIVE_STASIS (HIFD, external)', '', f"Setup: {f['dataset']}.", '',
              '| Fall trials | Stasis after fall | ADL trials | Stasis after ADL | Latency from impact (median, range) |',
              '|---|---|---|---|---|',
              f"| {f['fall_trials']} | {100 * f['stasis_after_fall_rate']:.1f} % | {f['adl_trials']} | "
              f"{100 * f['stasis_after_adl_rate']:.1f} % | {f['latency_s_median']} s, {f['latency_s_range']} |"]
    lines += ['', '## Example evidence (first occurrence per state)', '']
    for ds, d in r['daily_life'].items():
        for s, e in d['evidence_samples'].items():
            lines.append(f"- **{ds} / {s}** ({e['recording']}, t={e['t_s']} s): " + '; '.join(e['evidence']))
    return '\n'.join(lines) + '\n'
