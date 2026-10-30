"""docs/reports/WEARABLE_FINAL_MODELS.md - the P4 summary across heads (links to each model card)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .. import paths

REPORT_PATH = paths.PROJECT_ROOT / 'docs' / 'reports' / 'WEARABLE_FINAL_MODELS.md'


def _f(v, nd=3):
    return '—' if v is None else f'{v:.{nd}f}'


def write_final_report() -> None:
    reg_path = paths.MODELS_DIR / 'registry.json'
    if not reg_path.exists():
        return
    reg = json.loads(reg_path.read_text(encoding='utf-8'))
    lines = ['# Wearable ML — Final Tier-1 Models (P4)', '',
             f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by "
             '`python -m src.ml.wearable.pipeline final`. Registry: `models/wearable/registry.json`._', '',
             'Each head is the P3 v2 tournament winner, refitted on all of its training windows, exported to ONNX '
             '(verified against Python), calibrated on out-of-fold predictions and given an operating threshold. '
             'All metrics are out-of-fold on subjects the scoring model never saw, after cross-fitted calibration, '
             'with subject-bootstrap 95 % confidence intervals.', '',
             '| Head | Model | Macro-F1 (95 % CI) | AUROC | Sensitivity | Specificity | ECE before → after | Threshold | External test | Card |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for head, e in reg['heads'].items():
        m = json.loads((paths.MODELS_DIR / e['path'] / 'metrics.json').read_text(encoding='utf-8'))['metrics']
        o = m['oof_calibrated']
        ext = m.get('external')
        ext_txt = f"{', '.join(ext['datasets'])}: macro-F1 {ext['macro_f1']:.3f}" if ext else '—'
        if 'heldout_daily_life' in m:
            ext_txt += f"; {m['heldout_daily_life']['false_alarms_per_8h']:.2f} false alarms / 8 h on " \
                       f"{m['heldout_daily_life']['hours']:,.0f} h held-out daily life"
        cal = e['calibration']
        lines.append(f"| {head} | `{e['tournament']['winner']}` | {o['macro_f1']:.3f} ({o['macro_f1_ci95'][0]:.3f}–"
                     f"{o['macro_f1_ci95'][1]:.3f}) | {_f(o.get('auroc'))} | {_f(o.get('sensitivity'))} | "
                     f"{_f(o.get('specificity'))} | {cal['oof_ece_before']:.3f} → {cal['oof_ece_after_crossfit']:.3f} | "
                     f"{e['threshold'] if e['threshold'] is not None else 'argmax'} | {ext_txt} | "
                     f"[card](../../models/wearable/{e['path']}/card.md) |")
    lines += ['', 'Serving contract per head: inputs `X` (tabular features, registry order) and `S` (frame sequence), '
              'output `proba`; members of a soft-vote are averaged, then the calibrator and threshold in '
              '`calibration.json` are applied. `golden.npz` holds reference inputs/outputs for serving tests.', '']
    REPORT_PATH.write_text('\n'.join(lines), encoding='utf-8')
