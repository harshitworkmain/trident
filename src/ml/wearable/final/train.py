"""P4 - final Tier-1 models: refit, calibrate, choose thresholds, export ONNX, write registry + cards.

For each head the P3 v2 tournament fixed the model family (or soft-vote pair) and its
hyper-parameters. This module:

1. refits the selected member(s) on every CV window of the head;
2. exports each member to ONNX and checks it against Python on held-back rows (golden file);
3. fits a probability calibrator on the tournament's out-of-fold winner probabilities
   (Platt scaling for binary heads, temperature scaling for activity) and reports its effect
   with subject-grouped cross-fitting, so calibration is never evaluated on its own fit data;
4. chooses an operating threshold (binary heads) on cross-fitted calibrated OOF probabilities:
   macro-F1 for stress / HR-trust / rhythm; for fall, the most sensitive threshold whose
   out-of-fold daily-life false-alarm rate meets the Tier-1 budget;
5. reports final metrics with subject-bootstrap 95 % CIs, external tests and (fall) the
   held-out Capture-24 replay at the chosen threshold;
6. writes models/wearable/<head>/<version>/ (ONNX, calibration.json, metrics.json, card.md,
   golden.npz) and models/wearable/registry.json.

    python -m src.ml.wearable.pipeline final [heads...]
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import onnx
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold

from .. import __version__ as package_version
from .. import paths
from ..heads.build import HEADS, feature_columns, load_head
from ..models.candidates import CANDIDATES
from ..tournament.metrics import classification_metrics, false_alarms_per_hour
from ..tournament.run import RESULTS_DIR, Data, load_config
from ..serving.calibration import apply_calibrator, logit
from .export import export_candidate, max_abs_diff

logger = logging.getLogger('wearable.final')
MODEL_VERSION = '2.0.0'
REGISTRY_PATH = paths.MODELS_DIR / 'registry.json'
GOLDEN_ROWS = 64
PARITY_ROWS = 4000
PARITY_MAX_ABS = 0.02
PARITY_MAX_FLIPS = 0.002
FALL_FA_BUDGET_PER_8H = 1.0        # Tier-1 target; P5 fusion adds post-impact confirmation on top
FALL_MIN_SENSITIVITY = 0.80
THRESHOLD_GRID = np.round(np.concatenate([np.arange(0.05, 0.95, 0.01), np.arange(0.95, 0.9995, 0.0025)]), 4)


# ─── calibration ─────────────────────────────────────────────────────────────

def fit_calibrator(proba: np.ndarray, y: np.ndarray) -> dict:
    """Platt scaling on logit(p1) for binary heads; temperature scaling on log p otherwise."""
    if proba.shape[1] == 2:
        from sklearn.linear_model import LogisticRegression
        lr = LogisticRegression(C=1e6, max_iter=1000).fit(logit(proba[:, 1])[:, None], y)
        return {'method': 'platt', 'a': float(lr.coef_[0, 0]), 'b': float(lr.intercept_[0])}
    logp = np.log(np.clip(proba, 1e-7, 1))

    def nll(t):
        z = logp / t
        z = z - z.max(axis=1, keepdims=True)
        return float(-(z[np.arange(len(y)), y] - np.log(np.exp(z).sum(axis=1))).mean())
    t = minimize_scalar(nll, bounds=(0.05, 20.0), method='bounded').x
    return {'method': 'temperature', 'T': float(t)}


def cross_fit_calibration(proba, y, groups, folds: int = 5) -> np.ndarray:
    """Calibrated OOF probabilities where each subject's calibrator never saw that subject."""
    out = np.zeros_like(proba)
    for tr, te in GroupKFold(folds).split(proba, y, groups):
        out[te] = apply_calibrator(fit_calibrator(proba[tr], y[tr]), proba[te])
    return out


# ─── thresholds ──────────────────────────────────────────────────────────────

def _binary_scores(y, p1, thr) -> dict:
    pred = (p1 >= thr).astype(int)
    tp, fn = int(((pred == 1) & (y == 1)).sum()), int(((pred == 0) & (y == 1)).sum())
    tn, fp = int(((pred == 0) & (y == 0)).sum()), int(((pred == 1) & (y == 0)).sum())
    return {'threshold': float(thr), 'macro_f1': float(f1_score(y, pred, average='macro', zero_division=0)),
            'sensitivity': tp / max(tp + fn, 1), 'specificity': tn / max(tn + fp, 1),
            'ppv': tp / max(tp + fp, 1)}


def choose_threshold_macro_f1(y, p1) -> Tuple[float, List[dict]]:
    curve = [_binary_scores(y, p1, t) for t in THRESHOLD_GRID]
    best = max(curve, key=lambda c: (c['macro_f1'], -abs(c['threshold'] - 0.5)))
    return best['threshold'], curve


def _rec_ids(table: pd.DataFrame) -> np.ndarray:
    return table.groupby(['dataset', 'subject', 'trial'], observed=True, sort=False).ngroup().to_numpy()


def choose_threshold_fall(oof: pd.DataFrame, p1: np.ndarray) -> Tuple[float, List[dict], str]:
    """Most sensitive threshold whose OOF daily-life false-alarm rate is within budget."""
    from ..tournament.run import DAILY_LIFE_OOF
    daily = oof['dataset'].isin(DAILY_LIFE_OOF).to_numpy()
    ids, frames = _rec_ids(oof[daily]), oof.loc[daily, 'end_frame'].to_numpy()
    falls = oof['y'].to_numpy() == 1
    peak = pd.Series(p1[falls]).groupby(_rec_ids(oof[falls])).max().to_numpy()   # one score per fall trial
    curve = []
    for t in THRESHOLD_GRID[THRESHOLD_GRID >= 0.3]:
        fa = false_alarms_per_hour(p1[daily] >= t, ids, frames)
        curve.append({'threshold': float(t), 'oof_daily_false_alarms_per_8h': fa['false_alarms_per_8h'],
                      'oof_fall_event_sensitivity': float((peak >= t).mean()),
                      **{k: v for k, v in _binary_scores(oof['y'].to_numpy(), p1, t).items() if k != 'threshold'}})
    ok = [c for c in curve if c['oof_daily_false_alarms_per_8h'] <= FALL_FA_BUDGET_PER_8H]
    if ok:
        best = max(ok, key=lambda c: (c['oof_fall_event_sensitivity'], -c['threshold']))
        return best['threshold'], curve, f'most sensitive threshold with OOF daily-life false alarms ≤ {FALL_FA_BUDGET_PER_8H}/8 h'
    sens_ok = [c for c in curve if c['oof_fall_event_sensitivity'] >= FALL_MIN_SENSITIVITY]
    best = min(sens_ok or curve, key=lambda c: (c['oof_daily_false_alarms_per_8h'], -c['oof_fall_event_sensitivity']))
    return best['threshold'], curve, (f'no threshold meets ≤ {FALL_FA_BUDGET_PER_8H}/8 h at Tier 1; fewest false alarms '
                                      f'while keeping fall sensitivity ≥ {FALL_MIN_SENSITIVITY:.0%} (fusion must close the gap)')


# ─── metrics with confidence intervals ───────────────────────────────────────

def bootstrap_ci(y, pred, groups, fn, n: int = 1000, seed: int = 42) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in uniq}
    vals = []
    for _ in range(n):
        idx = np.concatenate([index[g] for g in rng.choice(uniq, len(uniq), replace=True)])
        if len(np.unique(y[idx])) > 1:
            vals.append(fn(y[idx], pred[idx]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def decision_metrics(y, proba, groups, classes, threshold: Optional[float]) -> dict:
    k = len(classes)
    pred = (proba[:, 1] >= threshold).astype(int) if threshold is not None else proba.argmax(axis=1)
    m = classification_metrics(y, proba, classes)
    out = {'log_loss': m['log_loss'], 'ece': m['ece'], 'auroc': m.get('auroc')}
    out['macro_f1'] = float(f1_score(y, pred, average='macro', labels=list(range(k)), zero_division=0))
    out['macro_f1_ci95'] = bootstrap_ci(y, pred, groups, lambda a, b: f1_score(a, b, average='macro',
                                                                                labels=list(range(k)), zero_division=0))
    per = f1_score(y, pred, average=None, labels=list(range(k)), zero_division=0)
    out.update({f'f1_{c}': float(v) for c, v in zip(classes, per)})
    if k == 2:
        out.update({key: v for key, v in _binary_scores(y, proba[:, 1], threshold if threshold is not None else 0.5).items()
                    if key != 'threshold'})
        out['sensitivity_ci95'] = bootstrap_ci(y, pred, groups, lambda a, b: float(((b == 1) & (a == 1)).sum() / max((a == 1).sum(), 1)))
    return out


# ─── one head ────────────────────────────────────────────────────────────────

def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def finalize_head(head: str) -> dict:
    spec = HEADS[head]
    cfg = load_config()
    res = json.loads((RESULTS_DIR / f'{head}.json').read_text(encoding='utf-8'))
    s3 = res['stage3']
    members, params = s3['members'], s3['winner_params']
    table, seq = load_head(head)
    feats = feature_columns(table)
    cv = Data(table, seq, (table['split'] == 'cv').to_numpy(), feats)
    k, T, C = len(spec.classes), seq.shape[1], seq.shape[2]
    out_dir = paths.MODELS_DIR / head / MODEL_VERSION
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info('[%s] final fit of %s on %d windows', head, members, len(cv))

    # 1-2. refit + ONNX export + parity
    rng = np.random.default_rng(cfg['seed'])
    check = rng.choice(len(cv), min(PARITY_ROWS, len(cv)), replace=False)
    files, parity, models = {}, {}, {}
    for m in members:
        model = CANDIDATES[m](k, params[m], cfg['seed']).fit(cv.X, cv.S, cv.y, cv.groups)
        onnx_model = export_candidate(model, len(feats), T, C)
        blob = onnx_model.SerializeToString()
        name = f'model_{m}.onnx'
        (out_dir / name).write_bytes(blob)
        files[name] = {'sha256': _sha256(blob), 'bytes': len(blob)}
        d, flips = max_abs_diff(model, onnx_model, cv.X[check].astype(np.float32), cv.S[check])
        parity[m] = {'rows': len(check), 'max_abs_proba_diff': d, 'argmax_flip_rate': flips}
        models[m] = blob
        logger.info('[%s]   %s exported (%d KB), parity max|dp| %.2e, flips %.4f', head, m, len(blob) // 1024, d, flips)
        # MiniRocket's PPV features compare float32 convolutions with biases; a sum-order difference
        # can flip a single comparison right at a bias (one 1/L step), hence a looser max tolerance.
        assert d < PARITY_MAX_ABS and flips < PARITY_MAX_FLIPS, f'{head}/{m}: ONNX parity failed ({d}, {flips})'
        if m == 'extratrees':
            files.update(compile_member_forest(out_dir, m, onnx_model, cv.X[check], cv.S[check]))

    # one session per member: building a large tree-ensemble session takes minutes in onnxruntime
    import onnxruntime as ort
    sessions = {m: ort.InferenceSession(models[m], providers=['CPUExecutionProvider']) for m in members}

    def predict(X, S):
        feed = {'X': X.astype(np.float32), 'S': S.astype(np.float32)}
        out = []
        for m in members:
            names = {i.name for i in sessions[m].get_inputs()}
            out.append(sessions[m].run(['proba'], {k: v for k, v in feed.items() if k in names})[0])
        return np.mean(out, axis=0).astype(np.float64)

    # 3. calibration on tournament OOF winner probabilities
    oof = pd.read_parquet(RESULTS_DIR / f'{head}_oof.parquet')
    p_oof = oof[[f'winner_p{c}' for c in range(k)]].to_numpy()
    y_oof, g_oof = oof['y'].to_numpy(), oof['group'].astype(str).to_numpy()
    cal = fit_calibrator(p_oof, y_oof)
    p_cf = cross_fit_calibration(p_oof, y_oof, g_oof)
    before, after = classification_metrics(y_oof, p_oof, spec.classes), classification_metrics(y_oof, p_cf, spec.classes)
    calibration = {**cal, 'fitted_on': 'tournament out-of-fold winner probabilities',
                   'oof_ece_before': before['ece'], 'oof_ece_after_crossfit': after['ece'],
                   'oof_log_loss_before': before['log_loss'], 'oof_log_loss_after_crossfit': after['log_loss']}

    # 4. threshold
    threshold, threshold_rule, curve = None, 'argmax (multi-class)', []
    if k == 2:
        if head == 'fall':
            threshold, curve, threshold_rule = choose_threshold_fall(oof, p_cf[:, 1])
        else:
            threshold, curve = choose_threshold_macro_f1(y_oof, p_cf[:, 1])
            threshold_rule = 'maximises out-of-fold macro-F1 (cross-fitted calibrated probabilities)'

    # 5. metrics
    metrics = {'oof_calibrated': decision_metrics(y_oof, p_cf, g_oof, spec.classes, threshold),
               'oof_uncalibrated_argmax': {key: before[key] for key in ('macro_f1', 'balanced_accuracy', 'log_loss', 'ece')},
               'per_dataset': {}}
    for ds in sorted(oof['dataset'].unique()):
        mask = (oof['dataset'] == ds).to_numpy()
        if len(np.unique(y_oof[mask])) > 1:
            metrics['per_dataset'][ds] = decision_metrics(y_oof[mask], p_cf[mask], g_oof[mask], spec.classes, threshold)
    ext_mask = (table['split'] == 'external').to_numpy()
    if ext_mask.any():
        ext = Data(table, seq, ext_mask, feats)
        p_ext = apply_calibrator(cal, predict(ext.X, ext.S))
        metrics['external'] = {'datasets': sorted(ext.table['dataset'].astype(str).unique()),
                               **decision_metrics(ext.y, p_ext, ext.groups.astype(str), spec.classes, threshold)}
    if head == 'fall':
        rep = Data(table, seq, (table['split'] == 'replay').to_numpy(), feats)
        p_rep = np.concatenate([apply_calibrator(cal, predict(rep.X[i:i + 200_000], rep.S[i:i + 200_000]))[:, 1]
                                for i in range(0, len(rep), 200_000)])
        ids, frames = _rec_ids(rep.table), rep.table['end_frame'].to_numpy()
        fa = false_alarms_per_hour(p_rep >= threshold, ids, frames)
        metrics['heldout_daily_life'] = {'people': int(rep.table['subject'].nunique()), 'hours': fa['hours'],
                                         'events': fa['events'], 'false_alarms_per_8h': fa['false_alarms_per_8h'],
                                         'curve': [{'threshold': t, **{kk: vv for kk, vv in
                                                   false_alarms_per_hour(p_rep >= t, ids, frames).items()
                                                   if kk in ('false_alarms_per_8h', 'events')}}
                                                   for t in (0.5, 0.7, 0.9, 0.95, 0.98, 0.99)]}
        del rep, p_rep

    # golden rows for serving tests (inputs + expected calibrated output of the ONNX ensemble)
    gi = check[:GOLDEN_ROWS]
    gX, gS = cv.X[gi].astype(np.float32), cv.S[gi].astype(np.float32)
    np.savez_compressed(out_dir / 'golden.npz', X=gX, S=gS, proba=apply_calibrator(cal, predict(gX, gS)))

    entry = {
        'head': head, 'version': MODEL_VERSION, 'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'package_version': package_version, 'feature_set': spec.feature_set, 'window_frames': spec.T,
        'features': feats, 'sequence_shape': [T, C], 'classes': list(spec.classes),
        'members': members, 'combine': 'mean' if len(members) > 1 else 'single', 'params': params,
        'files': files, 'calibration': calibration, 'threshold': threshold, 'threshold_rule': threshold_rule,
        'parity': parity, 'training': {'windows': len(cv), 'subjects': int(len(np.unique(cv.groups))),
                                       'datasets': sorted(cv.table['dataset'].astype(str).unique())},
        'tournament': {'winner': s3['winner'], 'reason': s3['reason']},
    }
    (out_dir / 'calibration.json').write_text(json.dumps({'calibration': calibration, 'threshold': threshold,
                                                          'threshold_rule': threshold_rule}, indent=2), encoding='utf-8')
    (out_dir / 'metrics.json').write_text(json.dumps({'metrics': metrics, 'threshold_curve': curve}, indent=2),
                                          encoding='utf-8')
    (out_dir / 'card.md').write_text(model_card(entry, metrics, res), encoding='utf-8')
    _update_registry(entry)
    return {'entry': entry, 'metrics': metrics}


def compile_member_forest(out_dir, member: str, onnx_model, X, S) -> dict:
    """Tree-ensemble member as numpy arrays (serving/forest.py): loads in < 1 s instead of minutes.

    Must reproduce the ONNX probabilities; returns the registry `files` entry.
    """
    from ..serving import forest
    from .export import onnx_predict
    f = forest.compile_forest(onnx_model)
    p_f = forest.predict_proba(f, X)
    p_o = onnx_predict(onnx_model.SerializeToString(), X, S)
    d, flips = float(np.abs(p_f - p_o).max()), float((p_f.argmax(1) != p_o.argmax(1)).mean())
    assert d < 1e-5 and flips == 0.0, f'{member}: compiled forest differs from ONNX ({d}, {flips})'
    name = f'forest_{member}.npz'
    forest.save(f, out_dir / name)
    blob = (out_dir / name).read_bytes()
    logger.info('   %s compiled forest (%d KB), parity vs ONNX max|dp| %.2e', member, len(blob) // 1024, d)
    return {name: {'sha256': _sha256(blob), 'bytes': len(blob), 'derived_from': f'model_{member}.onnx',
                   'parity_vs_onnx': {'rows': len(X), 'max_abs_proba_diff': d, 'argmax_flip_rate': flips}}}


def compile_forests(heads: Optional[List[str]] = None) -> None:
    """Add compiled forests to already-finalised heads (no refit) and record them in the registry."""
    reg = json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    for head, e in reg['heads'].items():
        if (heads and head not in heads) or 'extratrees' not in e['members']:
            continue
        out_dir = paths.MODELS_DIR / e['path']
        table, seq = load_head(head)
        cv = Data(table, seq, (table['split'] == 'cv').to_numpy(), e['features'])
        check = np.random.default_rng(load_config()['seed']).choice(len(cv), min(PARITY_ROWS, len(cv)), replace=False)
        onnx_model = onnx.load(str(out_dir / 'model_extratrees.onnx'))
        e['files'].update(compile_member_forest(out_dir, 'extratrees', onnx_model,
                                                cv.X[check].astype(np.float32), cv.S[check]))
        REGISTRY_PATH.write_text(json.dumps(reg, indent=2), encoding='utf-8')
        logger.info('[%s] registry updated with compiled forest', head)
        del table, seq, cv


def _update_registry(entry: dict) -> None:
    reg = json.loads(REGISTRY_PATH.read_text(encoding='utf-8')) if REGISTRY_PATH.exists() else {'heads': {}}
    reg['heads'][entry['head']] = {k: v for k, v in entry.items() if k not in ('parity',)}
    reg['heads'][entry['head']]['path'] = f"{entry['head']}/{entry['version']}"
    reg['updated_utc'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2), encoding='utf-8')


# ─── model card ──────────────────────────────────────────────────────────────

INTENDED_USE = {
    'stress': 'Evidence for ELEVATED_STRESS and CRUSH_ENTRAPMENT in the Tier-2 fusion layer; never a diagnosis.',
    'fall': 'Impact/fall evidence for CONCUSSIVE_STASIS; fusion requires post-impact immobility before alarming.',
    'activity': 'Context for fusion (rest vs exercise) so exertion is not mistaken for shock or stress.',
    'hr_trust': 'Gates heart-rate-based rules: low trust suppresses cardiac/shock rules and flags the reading.',
    'rhythm': 'Screening evidence of an irregular rhythm from wrist RR intervals; not an ECG diagnosis.',
}
LIMITATIONS = {
    'stress': 'Trained on 15 WESAD lab subjects (TSST protocol). Transfer to a different stress protocol '
              '(Stress-Predict) is weak - see external test. Treat as low-confidence evidence.',
    'fall': 'Falls come from young/elderly volunteers falling onto mats (UP-Fall, SisFall), not real-world falls. '
            'Accelerometer-only. SisFall is waist-worn. Daily-life negatives are mostly healthy adults.',
    'activity': 'Behaviour-based intensity labels (Walmsley 2020); light-class boundaries are fuzzy. Capture-24 '
                'windows have no heart rate, PPG-DaLiA/PAMAP2 windows do.',
    'hr_trust': 'The label is defined by our firmware-style BPM vs an ECG reference (10 bpm tolerance); a different '
                'PPG front-end changes what "reliable" means.',
    'rhythm': 'Learned from ECG beat annotations degraded to PPG-like timing noise (calibrated on PPG-DaLiA), not from '
              'real wrist PPG of arrhythmia patients. AF and other irregular rhythms are pooled as "abnormal".',
}


def _fmt(v, nd=3):
    return '—' if v is None else f'{v:.{nd}f}'


def model_card(entry: dict, metrics: dict, res: dict) -> str:
    head = entry['head']
    o = metrics['oof_calibrated']
    lines = [f"# Model card — `{head}` v{entry['version']}", '',
             f"- **Model:** `{res['stage3']['winner']}` ({entry['combine']}) · features `{entry['feature_set']}` "
             f"({len(entry['features'])} tabular + sequence {entry['sequence_shape'][0]}×{entry['sequence_shape'][1]}) · "
             f"window {entry['window_frames']} frames ({entry['window_frames'] * 1.5:g} s)",
             f"- **Selected by:** P3 v2 tournament — {res['stage3']['reason']}",
             f"- **Training data:** {entry['training']['windows']:,} windows, {entry['training']['subjects']} subjects "
             f"({', '.join(entry['training']['datasets'])})",
             f"- **Calibration:** {entry['calibration']['method']} (ECE {entry['calibration']['oof_ece_before']:.3f} → "
             f"{entry['calibration']['oof_ece_after_crossfit']:.3f}, cross-fitted by subject)",
             f"- **Decision rule:** threshold {entry['threshold'] if entry['threshold'] is not None else 'argmax'} — {entry['threshold_rule']}",
             f"- **Serving:** ONNX ({', '.join(f'{n} {v['bytes'] // 1024} KB' for n, v in entry['files'].items())}); "
             f"parity with Python max |Δp| {max(p['max_abs_proba_diff'] for p in entry['parity'].values()):.1e}",
             '', '## Intended use', '', INTENDED_USE[head], '',
             '## Performance (out-of-fold, subjects never seen by the model that scored them)', '',
             f"- **Macro-F1:** {o['macro_f1']:.3f} (95 % CI {o['macro_f1_ci95'][0]:.3f}–{o['macro_f1_ci95'][1]:.3f}, subject bootstrap)",
             f"- **AUROC:** {_fmt(o.get('auroc'))} · **log-loss:** {o['log_loss']:.3f} · **ECE:** {o['ece']:.3f}"]
    if 'sensitivity' in o:
        lines.append(f"- **Sensitivity:** {o['sensitivity']:.3f} (95 % CI {o['sensitivity_ci95'][0]:.3f}–{o['sensitivity_ci95'][1]:.3f}) · "
                     f"**specificity:** {o['specificity']:.3f} · **PPV:** {o['ppv']:.3f}")
    lines += ['', '**Per class F1:** ' + ', '.join(f"{c} {o[f'f1_{c}']:.3f}" for c in entry['classes']), '',
              '**Per source dataset:**', '', '| Dataset | Macro-F1 (95 % CI) |' + (' Sensitivity | Specificity |' if 'sensitivity' in o else ''),
              '|---|---|' + ('---|---|' if 'sensitivity' in o else '')]
    for ds, m in metrics['per_dataset'].items():
        row = f"| {ds} | {m['macro_f1']:.3f} ({m['macro_f1_ci95'][0]:.3f}–{m['macro_f1_ci95'][1]:.3f}) |"
        if 'sensitivity' in m:
            row += f" {m['sensitivity']:.3f} | {m['specificity']:.3f} |"
        lines.append(row)
    if 'external' in metrics:
        e = metrics['external']
        lines += ['', f"## External test ({', '.join(e['datasets'])}, never used for training or tuning)", '',
                  f"- Macro-F1 {e['macro_f1']:.3f} (95 % CI {e['macro_f1_ci95'][0]:.3f}–{e['macro_f1_ci95'][1]:.3f}) · "
                  f"AUROC {_fmt(e.get('auroc'))}" + (f" · sensitivity {e['sensitivity']:.3f} · specificity {e['specificity']:.3f}"
                                                     if 'sensitivity' in e else '')]
    if 'heldout_daily_life' in metrics:
        h = metrics['heldout_daily_life']
        lines += ['', '## Daily-life false alarms (held-out Capture-24 people)', '',
                  f"- {h['people']} people, {h['hours']:,.0f} h: **{h['false_alarms_per_8h']:.2f} false alarms per 8 h** at the "
                  f"operating threshold ({h['events']} events).", '',
                  '| Threshold | False alarms / 8 h |', '|---|---|']
        lines += [f"| {c['threshold']} | {c['false_alarms_per_8h']:.2f} |" for c in h['curve']]
    lines += ['', '## Limitations', '', LIMITATIONS[head], '',
              '## Reproduce', '', '```', 'python -m src.ml.wearable.pipeline tournament ' + head,
              'python -m src.ml.wearable.pipeline final ' + head, '```', '']
    return '\n'.join(lines)


def finalize(heads: Optional[List[str]] = None) -> Dict[str, dict]:
    from .report import write_final_report
    out = {}
    for head in heads or ['stress', 'fall', 'activity', 'hr_trust', 'rhythm']:
        if not (RESULTS_DIR / f'{head}.json').exists():
            logger.warning('[%s] no tournament result - skipped', head)
            continue
        out[head] = finalize_head(head)
        write_final_report()
    return out
