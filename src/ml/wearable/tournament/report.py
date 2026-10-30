"""Render docs/reports/MODEL_TOURNAMENT_RESULTS.md from the saved tournament results (v2, with the v1 baseline)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from .. import paths

REPORT_PATH = paths.PROJECT_ROOT / 'docs' / 'reports' / 'MODEL_TOURNAMENT_RESULTS.md'
RESULTS_DIR = paths.DATA_ROOT / 'processed' / 'wearable' / 'tournament'
V1_DIR = RESULTS_DIR / 'v1'
ORDER = ['stress', 'fall', 'activity', 'hr_trust', 'rhythm']
TITLES = {'stress': 'Stress (WESAD; external: Stress-Predict)',
          'fall': 'Fall / impact (UP-Fall + SisFall + daily life; external: HIFD)',
          'activity': 'Activity intensity (PPG-DaLiA + PAMAP2 + Capture-24)',
          'hr_trust': 'Heart-rate trust (PPG-DaLiA + WESAD, ECG reference)',
          'rhythm': 'Heart rhythm (MIT-BIH + AFDB + LTAFDB, PPG-like augmentation)'}
# The single dataset each v1 head was trained on: v2 scores on that subset are the like-for-like comparison
V1_DATASET = {'stress': 'wesad', 'fall': None, 'activity': 'ppg_dalia', 'hr_trust': 'ppg_dalia', 'rhythm': 'mitbih'}


def _f(x, nd=3):
    return '—' if x is None else f'{x:.{nd}f}'


def _load(dir_, head) -> Optional[dict]:
    path = dir_ / f'{head}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def _winner_f1(r: dict) -> float:
    s3 = r['stage3']
    if s3.get('members', [s3['winner']]) != [s3['winner']] and 'stage3_vote' in r:
        return r['stage3_vote']['oof_metrics']['macro_f1']
    return r['stage2'][s3['winner']]['oof_metrics']['macro_f1']


def _stage_table(stage: dict, classes: List[str], winner_marks=()) -> List[str]:
    binary = len(classes) == 2
    head = '| Model | Macro-F1 (fold mean ± sd) | Balanced acc. | AUROC | ' + \
           ('Sensitivity | Specificity | ' if binary else '') + 'Log-loss | ECE | Fit s/fold | Latency ms | Size KB |'
    rows = [head, '|' + '---|' * (head.count('|') - 1)]
    for name, r in sorted(stage.items(), key=lambda kv: -kv[1]['fold_macro_f1']['mean']):
        m = r['oof_metrics']
        cells = [f'**{name}**' if name in winner_marks else name,
                 f"{r['fold_macro_f1']['mean']:.3f} ± {r['fold_macro_f1']['std']:.3f}",
                 _f(m.get('balanced_accuracy')), _f(m.get('auroc'))]
        if binary:
            cells += [_f(m.get('sensitivity')), _f(m.get('specificity'))]
        cells += [_f(m['log_loss']), _f(m['ece']), _f(r['fit_seconds_per_fold'], 1), _f(r['latency_ms'], 2),
                  _f(r['size_kb'], 0)]
        rows.append('| ' + ' | '.join(cells) + ' |')
    return rows


def _per_class(stage: dict, classes: List[str]) -> List[str]:
    rows = ['| Model | ' + ' | '.join(f'F1 {c}' for c in classes) + ' |', '|---|' + '---|' * len(classes)]
    for name, r in stage.items():
        rows.append(f'| {name} | ' + ' | '.join(_f(r['oof_metrics'].get(f'f1_{c}')) for c in classes) + ' |')
    return rows


def _per_dataset(r: dict) -> List[str]:
    if 'per_dataset' not in r:
        return []
    binary = len(r['classes']) == 2
    rows = ['', f"**Selected model (`{r['stage3']['winner']}`) per source dataset (out-of-fold):**", '',
            '| Dataset | Windows | Subjects | Macro-F1 | Balanced acc. |' + (' Sensitivity | Specificity |' if binary else ''),
            '|---|---|---|---|---|' + ('---|---|' if binary else '')]
    for ds, m in r['per_dataset'].items():
        cells = [ds, f"{m['windows']:,}", str(m['groups']),
                 _f(m.get('macro_f1')) if 'macro_f1' in m else f"acc. {_f(m.get('accuracy'))} (one class)",
                 _f(m.get('balanced_accuracy'))]
        if binary:
            cells += [_f(m.get('sensitivity')), _f(m.get('specificity'))]
        rows.append('| ' + ' | '.join(cells) + ' |')
    return rows


def _fall_alarms(r: dict) -> List[str]:
    sc = r.get('specificity_check')
    if not sc or 'thresholds' not in sc:
        return []
    first = next(iter(sc['thresholds'].values()))
    lines = ['', '### Daily-life false alarms (accelerometer-only fall model)', '',
             f"- **Held-out people:** {sc['replay_people']} Capture-24 participants ({first['heldout_hours']:,.0f} h of "
             'free-living wrist data) were never used for training or tuning.',
             f"- **Out-of-fold daily life:** PPG-DaLiA, WESAD and PAMAP2 subjects ({first['oof_daily_life_hours']:,.0f} h), "
             'each scored by a model that never saw that person.',
             f"- **Fall sensitivity:** share of the {first['oof_fall_events']:,} UP-Fall/SisFall fall trials with at least one "
             'alarm (out-of-fold). Alarms within 10 s are merged into one event. Target ≤ 1 false alarm per 8 h.', '',
             '| Threshold | False alarms / 8 h (held-out Capture-24) | False alarms / 8 h (OOF daily life) | Fall sensitivity (OOF) |',
             '|---|---|---|---|']
    for thr, t in sc['thresholds'].items():
        lines.append(f"| {thr} | {t['heldout_false_alarms_per_8h']:.2f} | {t['oof_daily_life_false_alarms_per_8h']:.2f} | "
                     f"{t['oof_fall_sensitivity']:.3f} |")
    lines.append('')
    lines.append('These are Tier-1 numbers. The Tier-2 fusion layer (P5) adds post-impact confirmation; the operating '
                 'threshold is chosen in P4.')
    return lines


def _head_section(r: dict, v1: Optional[dict]) -> List[str]:
    s3 = r['stage3']
    classes = r['classes']
    lines = [f"## {TITLES.get(r['head'], r['head'])}", '',
             f"- **Windows:** {r['n_windows']:,} from {r['n_groups']} subjects/patients · window {r['T']} frames "
             f"({r['T'] * 1.5:g} s) · {r['n_features']} tabular features",
             '- **Classes:** ' + ', '.join(f'{c}: {n:,}' for c, n in r['class_counts'].items()),
             f"- **Validation:** {r['protocol']['outer_folds']}-fold StratifiedGroupKFold by subject "
             f"(no subject appears in both train and test); Stage 2 tunes inside each training split with "
             f"{r['protocol']['inner_folds']}-fold inner CV",
             f"- **Winner: `{s3['winner']}`** — {s3['reason']}"]
    if v1:
        lines.append(f"- **v1 (P3 baseline):** `{v1['stage3']['winner']}` {_winner_f1(v1):.3f} on "
                     f"{v1['n_windows']:,} windows / {v1['n_groups']} subjects")
    if r.get('not_applicable'):
        lines.append(f"- Not entered: {', '.join(r['not_applicable'])} (window of {r['T']} frames is shorter than "
                     'MiniRocket\'s kernel span)')
    lines += ['', '### Stage 1 — screening (default hyper-parameters, all candidates)', '']
    lines += _stage_table(r['stage1'], classes, winner_marks=r['finalists'])
    lines += ['', f"Finalists (bold): {', '.join(r['finalists'])}. `logreg` is the reference baseline the "
              'contenders must beat; it advances only if it places in the top two.', '',
              '### Stage 2 — semifinal (nested Optuna tuning)', '']
    lines += _stage_table(r['stage2'], classes, winner_marks=s3.get('members', [s3['winner']]))
    vote = r.get('stage3_vote')
    params = s3['winner_params']
    lines += ['', '### Stage 3 — final', '',
              f"- Paired fold comparison `{s3['leader']}` − `{s3['runner_up']}`: mean {s3['paired_fold_diff']['mean']:+.3f}, "
              f"leader better in {s3['paired_fold_diff']['wins']}/{s3['paired_fold_diff']['folds']} folds",
              f"- Subject-level bootstrap ({s3['bootstrap']['n_boot']} resamples) of macro-F1 difference: "
              f"{s3['bootstrap']['mean_diff']:+.3f}, 95 % CI [{s3['bootstrap']['ci_low']:+.3f}, {s3['bootstrap']['ci_high']:+.3f}]"]
    if vote:
        vb = vote['vs_single']
        lines.append(f"- Soft-vote `{'+'.join(vote['members'])}`: macro-F1 {vote['oof_metrics']['macro_f1']:.3f}; vs single "
                     f"winner {vb['mean_diff']:+.3f}, 95 % CI [{vb['ci_low']:+.3f}, {vb['ci_high']:+.3f}] → "
                     f"{'adopted' if vote['adopted'] else 'not adopted'}")
    lines += [f"- Selected hyper-parameters: `{json.dumps(params)}`", '', '**Per-class F1 (Stage 2, out-of-fold):**', '']
    lines += _per_class(r['stage2'], classes)
    lines += _per_dataset(r)
    if 'external' in r:
        ext = r['external']
        lines += ['', f"### External test — {', '.join(ext['datasets'])} ({ext['windows']:,} windows, never seen in training or tuning)", '',
                  '| Model | Macro-F1 | Sensitivity | Specificity | AUROC |', '|---|---|---|---|---|']
        for name in (s3['leader'], s3['runner_up'], 'vote'):
            if name in ext:
                m = ext[name]
                lines.append(f"| {name} | {_f(m['macro_f1'])} | {_f(m.get('sensitivity'))} | {_f(m.get('specificity'))} | {_f(m.get('auroc'))} |")
    lines += _fall_alarms(r)
    lines += ['', f"_Runtime: {r.get('runtime_minutes', '?')} min._", '']
    return lines


def write_report() -> None:
    results = {h: r for h in ORDER if (r := _load(RESULTS_DIR, h))}
    v1 = {h: r for h in ORDER if (r := _load(V1_DIR, h))}
    lines = ['# Wearable ML — Model Tournament Results (P3 v2)', '',
             f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by "
             '`python -m src.ml.wearable.pipeline tournament`. Protocol: `docs/WEARABLE_ML_ARCHITECTURE.md` §8._', '',
             'Each Tier-1 head runs its own tournament. Contenders: **XGBoost, LightGBM, Extra-Trees, MLP, 1D-CNN, '
             'MiniRocket**, against logistic regression as the reference baseline; Stage 3 also tests a soft-vote of the '
             'two finalists. All scores are **out-of-fold on subjects the model never saw**. Thresholds are 0.5 here; '
             'calibration and operating thresholds are fixed in P4.', '',
             'v2 adds data (WESAD chest-ECG reference, PAMAP2, Capture-24, AFDB, LTAFDB; Stress-Predict as an external test) '
             'and candidates. '
             'Because v2 test sets are larger and differently balanced, the like-for-like comparison with v1 is the '
             '**v2 model scored on the v1 dataset** column.', '',
             '## Summary', '',
             '| Head | Winner (v2) | Macro-F1 v2 (all data) | v2 on v1 dataset | v1 winner · macro-F1 | Runner-up | Baseline (logreg) | Decision |',
             '|---|---|---|---|---|---|---|---|']
    for head, r in results.items():
        s3 = r['stage3']
        other = s3['runner_up'] if s3['leader'] in s3.get('members', [s3['winner']]) else s3['leader']
        on_v1 = r.get('per_dataset', {}).get(V1_DATASET.get(head) or '', {}).get('macro_f1')
        old = v1.get(head)
        decision = 'significant' if s3['bootstrap']['ci_low'] > 0 else 'tie → efficiency'
        if r.get('stage3_vote', {}).get('adopted'):
            decision = 'soft-vote significantly better'
        lines.append(f"| {head} | **{s3['winner']}** | {_winner_f1(r):.3f} | {_f(on_v1)} | "
                     f"{(old['stage3']['winner'] + ' · ' + format(_winner_f1(old), '.3f')) if old else '—'} | "
                     f"{other} ({r['stage2'][other]['oof_metrics']['macro_f1']:.3f}) | "
                     f"{r['stage1']['logreg']['oof_metrics']['macro_f1']:.3f} | {decision} |")
    pending = [h for h in ORDER if h not in results]
    if pending:
        lines += ['', f"_Pending heads: {', '.join(pending)}._"]
    lines.append('')
    for head, r in results.items():
        lines += _head_section(r, v1.get(head))
    lines += ['---', '', 'v1 results (P3, 2026-10-30) are archived in '
              '`data/processed/wearable/tournament/v1/` (JSON + the v1 report).', '']
    REPORT_PATH.write_text('\n'.join(lines), encoding='utf-8')
