"""Wearable ML pipeline CLI.

    python -m src.ml.wearable.pipeline compact [datasets...]   # lossless per-subject .npz
    python -m src.ml.wearable.pipeline manifest                # hash sources -> data/manifest/
    python -m src.ml.wearable.pipeline frames [datasets...]    # emulate 1.5 s device frames
    python -m src.ml.wearable.pipeline report                  # data report (markdown + json)
    python -m src.ml.wearable.pipeline heads [heads...]        # per-head window feature tables (P2)
    python -m src.ml.wearable.pipeline tournament [heads...]   # 3-stage model tournament (P3)
    python -m src.ml.wearable.pipeline final [heads...]        # calibrate, threshold, ONNX, registry (P4)
    python -m src.ml.wearable.pipeline replay [datasets...]    # serving path + fusion on real recordings (P5)
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import List

import numpy as np
import pandas as pd

from . import paths
from .data import compact as compact_mod
from .data.loaders import LOADERS, ppg_dalia_ecg_beats
from .data.manifest import data_hash, write_manifest
from .emulator import EMULATOR_VERSION, emulate
from .schema import FIELD_NAMES, FRAME_PERIOD_S

logger = logging.getLogger('wearable.pipeline')


def _meta(name: str, rows: int) -> None:
    (paths.FRAMES_DIR / f'{name}.meta.json').write_text(json.dumps({
        'dataset': name, 'rows': rows, 'data_hash': data_hash(name),
        'emulator_version': EMULATOR_VERSION, 'frame_period_s': FRAME_PERIOD_S,
    }, indent=2), encoding='utf-8')


def _capture24_frames(pid: str) -> int:
    from .data.loaders import load_capture24

    out = paths.FRAMES_DIR / 'capture24' / f'{pid}.parquet'
    if out.exists():
        return pd.read_parquet(out, columns=['frame']).shape[0]
    df = emulate(next(load_capture24([pid])))
    df.attrs = {}
    df.to_parquet(out.with_suffix('.tmp'), index=False)
    out.with_suffix('.tmp').replace(out)
    logger.info('capture24 %s: %d frames', pid, len(df))
    return len(df)


def build_partitioned_frames(name: str, workers: int = 3) -> None:
    """One parquet per recording under frames/<name>/ (resumable, bounded memory)."""
    from multiprocessing import Pool

    out_dir = paths.FRAMES_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    if name == 'capture24':
        from .data.loaders import capture24_participants
        with Pool(workers) as pool:
            rows = sum(pool.imap_unordered(_capture24_frames, capture24_participants()))
    else:
        rows = 0
        for rec in LOADERS[name]():
            out = out_dir / f'{rec.subject}_{rec.trial}.parquet'
            df = emulate(rec)
            df.attrs = {}
            df.to_parquet(out, index=False)
            rows += len(df)
    _meta(name, rows)
    logger.info('%s: %d frames -> %s', name, rows, out_dir)


def build_frames(datasets: List[str]) -> None:
    from .data.loaders import PARTITIONED

    paths.FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    for name in datasets:
        if name in PARTITIONED:
            build_partitioned_frames(name)
            continue
        parts = []
        for rec in LOADERS[name]():
            df = emulate(rec)
            if len(df):
                parts.append(df)
        frames = pd.concat(parts, ignore_index=True)
        frames.attrs = {}
        out = paths.FRAMES_DIR / f'{name}.parquet'
        frames.to_parquet(out, index=False)
        _meta(name, len(frames))
        logger.info('%s: %d frames from %d recordings -> %s', name, len(frames), len(parts), out)


# ─── data report ─────────────────────────────────────────────────────────────

def _label_table(df: pd.DataFrame) -> dict:
    tables = {}
    for col in [c for c in df.columns if c.startswith('y_') and not c.endswith('_purity')]:
        if df[col].dtype.kind == 'f' and df[col].nunique() > 50:
            tables[col] = {'mean': round(float(df[col].mean()), 2), 'min': round(float(df[col].min()), 2),
                           'max': round(float(df[col].max()), 2)}
        else:
            tables[col] = {str(k): int(v) for k, v in df[col].value_counts().sort_index().items()}
    for col in ('m_is_fall', 'm_code', 'm_scenario', 'm_activity', 'm_age_group'):
        if col in df.columns:
            trials = df.drop_duplicates(['subject', 'trial'])
            tables[col + ' (trials)'] = {str(k): int(v) for k, v in trials[col].value_counts().sort_index().items()}
    return tables


def _hr_check(df: pd.DataFrame) -> dict:
    """Emulated (firmware-style) BPM vs ECG reference BPM on PPG-DaLiA, per activity."""
    ok = df['ppg_bpm'].notna() & df['y_hr_ecg'].notna()
    err = (df.loc[ok, 'ppg_bpm'] - df.loc[ok, 'y_hr_ecg']).abs()
    by_act = err.groupby(df.loc[ok, 'y_activity']).median().round(1)
    return {'frames_with_bpm_pct': round(100 * ok.mean(), 1),
            'median_abs_err_bpm': round(float(err.median()), 1),
            'within_10bpm_pct': round(100 * float((err <= 10).mean()), 1),
            'median_abs_err_by_activity': {str(k): float(v) for k, v in by_act.items()}}


def _beat_detection_check() -> dict:
    """BVP peak detector vs chest-ECG R-peaks (PPG-DaLiA S1): share of R-peaks matched."""
    from .data.loaders import load_ppg_dalia
    from .emulator import detect_beats

    rec = next(load_ppg_dalia())
    det = detect_beats(rec.bvp)
    ref = ppg_dalia_ecg_beats(rec.subject)
    # PPG peaks lag ECG R-peaks by the pulse transit time (~0.2-0.4 s at the wrist)
    pos = np.searchsorted(det, ref)
    nxt = det[np.clip(pos, 0, len(det) - 1)]
    lag = nxt - ref
    matched = (lag >= 0) & (lag <= 0.5)
    return {'subject': rec.subject, 'ecg_beats': len(ref), 'ppg_beats': len(det),
            'ecg_beats_matched_pct': round(100 * float(matched.mean()), 1)}


def build_report() -> None:
    paths.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {}
    for f in sorted(paths.FRAMES_DIR.glob('*.parquet')):
        df = pd.read_parquet(f)
        name = f.stem
        avail = {c: round(100 * float(df[c].notna().mean()), 1) for c in FIELD_NAMES if df[c].notna().any()}
        entry = {
            'subjects': int(df['subject'].nunique()),
            'recordings': int(df.groupby(['subject', 'trial']).ngroups),
            'frames': len(df),
            'hours': round(len(df) * FRAME_PERIOD_S / 3600, 2),
            'fields_available_pct': avail,
            'frames_with_rr_pct': round(100 * float(df['rr_ms'].map(len).gt(0).mean()), 1),
            'labels': _label_table(df),
        }
        if name == 'ppg_dalia':
            entry['hr_vs_ecg'] = _hr_check(df)
            entry['beat_detection_vs_ecg'] = _beat_detection_check()
        if name in ('hifd', 'sisfall', 'upfall'):
            still = df['imu_acc_std_g'] < 0.02
            entry['still_frames_acc_mean_g'] = round(float(df.loc[still, 'imu_acc_mean_g'].median()), 3)
            entry['peak_acc_g_falls_vs_adl'] = {
                'falls_p50': round(float(df[df['m_is_fall']].groupby(['subject', 'trial'])['imu_acc_max_g'].max().median()), 2),
                'adl_p50': round(float(df[~df['m_is_fall']].groupby(['subject', 'trial'])['imu_acc_max_g'].max().median()), 2),
            }
        report[name] = entry
        logger.info('%s: %s', name, {k: entry[k] for k in ('subjects', 'frames', 'hours')})
    (paths.REPORTS_DIR / 'data_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    DATA_REPORT_MD.write_text(_report_markdown(report), encoding='utf-8')


DATA_REPORT_MD = paths.PROJECT_ROOT / 'docs' / 'reports' / 'WEARABLE_DATA_REPORT.md'


def _report_markdown(report: dict) -> str:
    lines = ['# Wearable ML — Data Report (generated)', '',
             f'Generated by `python -m src.ml.wearable.pipeline report` · emulator {EMULATOR_VERSION} · '
             f'frame period {FRAME_PERIOD_S} s', '',
             '| Dataset | Subjects | Recordings | Frames | Hours | Frames with RR |',
             '|---|---|---|---|---|---|']
    for name, e in report.items():
        lines.append(f"| {name} | {e['subjects']} | {e['recordings']} | {e['frames']:,} | {e['hours']} | "
                     f"{e['frames_with_rr_pct']} % |")
    for name, e in report.items():
        lines += ['', f'## {name}', '', '**Fields available (% of frames):** ' +
                  ', '.join(f'`{k}` {v}' for k, v in e['fields_available_pct'].items()), '']
        for label, counts in e['labels'].items():
            lines.append(f'- **{label}:** ' + ', '.join(f'{k}: {v}' for k, v in counts.items()))
        for key in ('hr_vs_ecg', 'beat_detection_vs_ecg', 'still_frames_acc_mean_g', 'peak_acc_g_falls_vs_adl'):
            if key in e:
                lines.append(f'- **{key}:** `{json.dumps(e[key])}`')
    lines += _heads_markdown()
    return '\n'.join(lines) + '\n'


def _heads_markdown() -> List[str]:
    from .heads.build import HEADS_DIR

    metas = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(HEADS_DIR.glob('*.meta.json'))]
    if not metas:
        return []
    lines = ['', '## Head datasets (P2)', '',
             'Windows are produced by replaying every emulated recording through the online `FeatureEngine` '
             '(identical code to serving). `cv` rows enter the tournament; `external` rows are only ever tested; '
             '`replay` rows are fall-free daily life used to count false alarms.', '',
             '| Head | Window | Stride | Features | Split | Windows | Groups | Classes |', '|---|---|---|---|---|---|---|---|']
    for m in metas:
        for split, c in m['counts'].items():
            lines.append(f"| {m['head']} | {m['T']} frames ({m['T'] * FRAME_PERIOD_S:g} s) | {m['stride']} | "
                         f"{len(m['features'])} | {split} | {c['windows']:,} | {c['groups']} | "
                         + ', '.join(f'{k}: {v:,}' for k, v in c['classes'].items()) + ' |')
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('step', choices=['compact', 'manifest', 'frames', 'report', 'heads', 'tournament', 'final', 'replay'])
    parser.add_argument('targets', nargs='*', help='datasets (data steps) or heads (model steps)')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if args.step == 'compact':
        registry = compact_mod.load_registry()
        for name in args.targets or list(LOADERS):
            compact_mod.COMPACTORS[name](registry[name])
    elif args.step == 'manifest':
        write_manifest()
    elif args.step == 'frames':
        build_frames(args.targets or list(LOADERS))
    elif args.step == 'report':
        build_report()
    elif args.step == 'heads':
        from .heads.build import HEADS, build_head
        for name in args.targets or list(HEADS):
            build_head(name)
    elif args.step == 'tournament':
        from .tournament.run import run_tournaments
        run_tournaments(args.targets or None)
    elif args.step == 'final':
        from .final.train import finalize
        finalize(args.targets or None)
    elif args.step == 'replay':
        from .serving.replay import run_replay
        run_replay(args.targets or None)


if __name__ == '__main__':
    main()
