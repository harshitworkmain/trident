"""Three-stage model tournament, run independently for every Tier-1 head.

Stage 1 - screening : every candidate with default hyper-parameters, outer subject-grouped CV.
                      The two best advance. logreg is the reference baseline the four contenders
                      must beat; if it ranks in the top two it advances too.
Stage 2 - semifinal : each finalist tuned with Optuna inside every outer training split
                      (nested CV: tuning never sees the outer test subjects).
Stage 3 - final     : paired per-fold comparison + subject-level bootstrap CI of the difference.
                      A significant winner wins; otherwise the smaller/faster model wins.
                      A soft-vote of both finalists replaces the single winner only if it is
                      significantly better than it (it costs two models at serving time).
                      Finalists are also scored on external data (fall: HIFD) and, for the fall
                      head, on daily-life replay of held-out people (false alarms per 8 h).

Results: data/processed/wearable/tournament/<head>.json (+ out-of-fold predictions parquet),
MLflow runs under mlruns/, and docs/reports/MODEL_TOURNAMENT_RESULTS.md (see report.py).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import optuna
import pandas as pd
import yaml
from sklearn.model_selection import StratifiedGroupKFold

from .. import paths
from ..heads.build import HEADS, feature_columns, load_head
from ..models.candidates import BASELINE, CANDIDATES, CONTENDERS, applicable
from .metrics import classification_metrics, false_alarms_per_hour, group_bootstrap_diff

logger = logging.getLogger('wearable.tournament')
RESULTS_DIR = paths.DATA_ROOT / 'processed' / 'wearable' / 'tournament'
TOURNAMENT_HEADS = ['stress', 'fall', 'activity', 'hr_trust', 'rhythm']


def load_config() -> dict:
    with open(paths.CONFIG_DIR / 'tournament.yaml', encoding='utf-8') as fh:
        return yaml.safe_load(fh)


class Data:
    """Arrays for one split of a head table."""

    def __init__(self, table: pd.DataFrame, seq: np.ndarray, mask: np.ndarray, feats: List[str]):
        self.table = table.loc[mask].reset_index(drop=True)
        self.X = self.table[feats].to_numpy(dtype=np.float64)
        self.S = seq[mask]
        self.y = self.table['y'].to_numpy()
        self.groups = self.table['group'].to_numpy()

    def __len__(self):
        return len(self.y)

    def take(self, idx):
        return self.X[idx], self.S[idx], self.y[idx], self.groups[idx]


def _fit(name: str, params: Optional[dict], n_classes: int, X, S, y, g, seed: int):
    return CANDIDATES[name](n_classes, params, seed).fit(X, S, y, g)


def cross_val(name: str, params: Optional[dict], data: Data, folds, n_classes: int, seed: int):
    oof = np.zeros((len(data), n_classes))
    scores, fit_s, model = [], 0.0, None
    for tr, te in folds:
        t0 = time.perf_counter()
        model = _fit(name, params, n_classes, *data.take(tr), seed)
        fit_s += time.perf_counter() - t0
        oof[te] = model.predict_proba(data.X[te], data.S[te])
        scores.append(classification_metrics(data.y[te], oof[te], [str(i) for i in range(n_classes)])['macro_f1'])
    return oof, scores, fit_s / len(folds), model


def tune(name: str, data: Data, idx: np.ndarray, n_classes: int, cfg: dict) -> Tuple[dict, float]:
    budget = cfg['budget'][name]
    X, S, y, g = data.take(idx)
    inner = list(StratifiedGroupKFold(cfg['inner_folds'], shuffle=True, random_state=cfg['seed']).split(X, y, g))
    cls = CANDIDATES[name]

    def objective(trial: optuna.Trial) -> float:
        params = cls.suggest(trial)
        scores = []
        for step, (tr, va) in enumerate(inner):
            model = cls(n_classes, params, cfg['seed']).fit(X[tr], S[tr], y[tr], g[tr])
            p = model.predict_proba(X[va], S[va])
            scores.append(classification_metrics(y[va], p, [str(i) for i in range(n_classes)])['macro_f1'])
            trial.report(float(np.mean(scores)), step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(scores))

    study = optuna.create_study(direction='maximize',
                                sampler=optuna.samplers.TPESampler(seed=cfg['seed']),
                                pruner=optuna.pruners.MedianPruner(n_startup_trials=3))
    defaults = cls.default_params()
    study.enqueue_trial(defaults)  # tuning starts from the screening configuration
    study.optimize(objective, n_trials=budget['trials'], timeout=budget['timeout_s'])
    best = {**defaults, **study.best_trial.params}
    return best, float(study.best_value)


def latency_ms(model, data: Data, repeats: int = 50) -> float:
    x, s = data.X[:1], data.S[:1]
    model.predict_proba(x, s)
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        model.predict_proba(x, s)
        times.append((time.perf_counter() - t0) * 1000)
    return float(np.median(times))


def _summary(scores: List[float]) -> Dict[str, float]:
    return {'mean': float(np.mean(scores)), 'std': float(np.std(scores)), 'folds': [float(s) for s in scores]}


def _mlflow_log(head: str, stage: str, name: str, params: dict, metrics: dict) -> None:
    try:
        import mlflow
        mlflow.set_tracking_uri(f"sqlite:///{(paths.PROJECT_ROOT / 'mlruns' / 'mlflow.db').as_posix()}")
        mlflow.set_experiment(f'wearable-{head}')
        with mlflow.start_run(run_name=f'{stage}:{name}'):
            mlflow.log_params({k: v for k, v in (params or {}).items()})
            mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float)) and np.isfinite(v)})
    except Exception as exc:  # tracking must never break the tournament
        logger.warning('MLflow logging skipped: %s', exc)


def run_head(head: str, cfg: dict) -> dict:
    spec = HEADS[head]
    table, seq = load_head(head)
    feats = feature_columns(table)
    data = Data(table, seq, (table['split'] == 'cv').to_numpy(), feats)
    k = len(spec.classes)
    folds = list(StratifiedGroupKFold(cfg['outer_folds'], shuffle=True, random_state=cfg['seed'])
                 .split(data.X, data.y, data.groups))
    result = {
        'head': head, 'classes': list(spec.classes), 'feature_set': spec.feature_set, 'T': spec.T,
        'n_features': len(feats), 'n_windows': len(data), 'n_groups': int(len(np.unique(data.groups))),
        'class_counts': {spec.classes[c]: int((data.y == c).sum()) for c in range(k)},
        'outer_folds': [{'train': len(tr), 'test': len(te), 'test_groups': int(len(np.unique(data.groups[te])))}
                        for tr, te in folds],
        'protocol': {key: cfg[key] for key in ('seed', 'outer_folds', 'inner_folds', 'bootstrap')},
        'stage1': {}, 'stage2': {}, 'stage3': {},
    }
    oof_frame = data.table[['dataset', 'subject', 'trial', 'group', 'end_frame', 'y']].copy()

    # Stage 1 - screening
    entrants = [n for n in [BASELINE] + CONTENDERS if applicable(n, spec.T)]
    result['not_applicable'] = [n for n in [BASELINE] + CONTENDERS if n not in entrants]
    for name in entrants:
        logger.info('[%s] stage 1: %s', head, name)
        oof, scores, fit_s, model = cross_val(name, None, data, folds, k, cfg['seed'])
        metrics = classification_metrics(data.y, oof, spec.classes)
        result['stage1'][name] = {'fold_macro_f1': _summary(scores), 'oof_metrics': metrics,
                                  'fit_seconds_per_fold': round(fit_s, 2),
                                  'latency_ms': round(latency_ms(model, data), 3), 'size_kb': round(model.size_bytes() / 1024, 1),
                                  'params': CANDIDATES[name].default_params()}
        for c in range(k):
            oof_frame[f's1_{name}_p{c}'] = oof[:, c]
        _mlflow_log(head, 'stage1', name, CANDIDATES[name].default_params(), {**metrics, 'fold_macro_f1_mean': np.mean(scores)})
        logger.info('[%s]   %s macro-F1 %.3f ± %.3f', head, name, np.mean(scores), np.std(scores))
    # Contenders must beat the baseline: if logreg ranks in the top two it advances as a finalist.
    ranked = sorted(entrants, key=lambda n: result['stage1'][n]['fold_macro_f1']['mean'], reverse=True)
    finalists = ranked[:cfg['finalists']]
    result['stage1_ranking'] = ranked
    result['finalists'] = finalists

    # Stage 2 - nested tuning of the finalists
    oof2 = {}
    for name in finalists:
        oof = np.zeros((len(data), k))
        scores, fold_params, fit_s, model = [], [], 0.0, None
        for i, (tr, te) in enumerate(folds):
            logger.info('[%s] stage 2: %s outer fold %d/%d', head, name, i + 1, len(folds))
            params, inner_best = tune(name, data, tr, k, cfg)
            t0 = time.perf_counter()
            model = _fit(name, params, k, *data.take(tr), cfg['seed'])
            fit_s += time.perf_counter() - t0
            oof[te] = model.predict_proba(data.X[te], data.S[te])
            scores.append(classification_metrics(data.y[te], oof[te], [str(c) for c in range(k)])['macro_f1'])
            fold_params.append({'params': params, 'inner_macro_f1': inner_best})
        metrics = classification_metrics(data.y, oof, spec.classes)
        best_params = max(fold_params, key=lambda f: f['inner_macro_f1'])['params']
        result['stage2'][name] = {'fold_macro_f1': _summary(scores), 'oof_metrics': metrics,
                                  'fit_seconds_per_fold': round(fit_s / len(folds), 2),
                                  'latency_ms': round(latency_ms(model, data), 3), 'size_kb': round(model.size_bytes() / 1024, 1),
                                  'fold_params': fold_params, 'selected_params': best_params}
        oof2[name] = oof
        for c in range(k):
            oof_frame[f's2_{name}_p{c}'] = oof[:, c]
        _mlflow_log(head, 'stage2', name, best_params, {**metrics, 'fold_macro_f1_mean': np.mean(scores)})
        logger.info('[%s]   %s tuned macro-F1 %.3f ± %.3f', head, name, np.mean(scores), np.std(scores))

    # Stage 3 - final comparison
    a, b = sorted(finalists, key=lambda n: result['stage2'][n]['fold_macro_f1']['mean'], reverse=True)
    fold_diff = np.array(result['stage2'][a]['fold_macro_f1']['folds']) - np.array(result['stage2'][b]['fold_macro_f1']['folds'])
    boot = group_bootstrap_diff(data.y, oof2[a], oof2[b], data.groups, n=cfg['bootstrap'], seed=cfg['seed'])
    if boot['ci_low'] > 0:
        winner, reason = a, f'{a} better: subject-bootstrap 95% CI of macro-F1 difference excludes 0'
    else:
        eff = {n: (result['stage2'][n]['size_kb'], result['stage2'][n]['latency_ms']) for n in (a, b)}
        winner = min((a, b), key=lambda n: eff[n])
        reason = (f'no significant difference (95% CI [{boot["ci_low"]:+.3f}, {boot["ci_high"]:+.3f}] includes 0); '
                  f'tie broken by efficiency -> {winner} (smaller/faster)')
    # Soft-vote of the two tuned finalists: adopted only if significantly better than the single winner
    vote = (oof2[a] + oof2[b]) / 2
    vote_boot = group_bootstrap_diff(data.y, vote, oof2[winner], data.groups, n=cfg['bootstrap'], seed=cfg['seed'])
    result['stage3_vote'] = {'members': [a, b], 'oof_metrics': classification_metrics(data.y, vote, spec.classes),
                             'vs_single': vote_boot, 'adopted': bool(vote_boot['ci_low'] > 0)}
    members = [a, b] if result['stage3_vote']['adopted'] else [winner]
    if len(members) == 2:
        reason += (f'; soft-vote {a}+{b} significantly better than {winner} '
                   f'(CI [{vote_boot["ci_low"]:+.3f}, {vote_boot["ci_high"]:+.3f}]) -> adopted')
        winner = f'vote({a}+{b})'
    result['stage3'] = {'leader': a, 'runner_up': b, 'paired_fold_diff': {'mean': float(fold_diff.mean()),
                        'wins': int((fold_diff > 0).sum()), 'folds': len(fold_diff)},
                        'bootstrap': boot, 'winner': winner, 'members': members, 'reason': reason,
                        'winner_params': {m: result['stage2'][m]['selected_params'] for m in members}}
    winner_oof = np.mean([oof2[m] for m in members], axis=0)
    for c in range(k):
        oof_frame[f'winner_p{c}'] = winner_oof[:, c]
    result['per_dataset'] = _per_dataset(data, winner_oof, spec.classes)

    # External evaluation (data never used for training or tuning)
    ext_mask = (table['split'] == 'external').to_numpy()
    if ext_mask.any():
        ext = Data(table, seq, ext_mask, feats)
        result['external'] = {'datasets': sorted(ext.table['dataset'].unique()), 'windows': len(ext)}
        probs = {}
        for name in (a, b):
            model = _fit(name, result['stage2'][name]['selected_params'], k, data.X, data.S, data.y, data.groups, cfg['seed'])
            probs[name] = model.predict_proba(ext.X, ext.S)
            result['external'][name] = classification_metrics(ext.y, probs[name], spec.classes)
        result['external']['vote'] = classification_metrics(ext.y, (probs[a] + probs[b]) / 2, spec.classes)
    oof_frame.to_parquet(RESULTS_DIR / f'{head}_oof.parquet', index=False)
    return result


def _per_dataset(data: Data, proba: np.ndarray, classes) -> Dict[str, dict]:
    """Out-of-fold metrics of the selected model on each source dataset separately."""
    out = {}
    for ds in sorted(data.table['dataset'].unique()):
        m = (data.table['dataset'] == ds).to_numpy()
        entry = {'windows': int(m.sum()), 'groups': int(len(np.unique(data.groups[m])))}
        if len(np.unique(data.y[m])) < 2:
            entry['accuracy'] = float((proba[m].argmax(axis=1) == data.y[m]).mean())
        else:
            met = classification_metrics(data.y[m], proba[m], classes)
            entry.update({key: met[key] for key in ('macro_f1', 'balanced_accuracy', 'sensitivity', 'specificity')
                          if key in met})
        out[ds] = entry
    return out


FALL_THRESHOLDS = (0.5, 0.7, 0.9, 0.95)
# Out-of-fold false alarms only on fully covered daily life (stride 2). Capture-24 CV windows are a
# sparse, spike-enriched sample, so Capture-24 is measured on its held-out participants instead.
DAILY_LIFE_OOF = ('ppg_dalia', 'wesad', 'pamap2')


def _alarms(table: pd.DataFrame, p: np.ndarray, thr: float) -> dict:
    rec_id = table.groupby(['dataset', 'subject', 'trial'], observed=True, sort=False).ngroup().to_numpy()
    return false_alarms_per_hour(p >= thr, rec_id, table['end_frame'].to_numpy())


def fall_specificity_check(fall_result: dict, cfg: dict) -> dict:
    """False alarms of the selected fall model in real daily life, at several thresholds.

    * held-out replay: Capture-24 participants never used for training or tuning (~1/3 of 151)
    * out-of-fold: daily-life subjects inside CV, scored by the fold that did not train on them
    Sensitivity on the fall trials at each threshold is reported alongside (the trade-off).
    """
    members = fall_result['stage3']['members']
    params = fall_result['stage3']['winner_params']
    table, seq = load_head('fall')
    feats = feature_columns(table)
    train = Data(table, seq, (table['split'] == 'cv').to_numpy(), feats)
    rep = Data(table, seq, (table['split'] == 'replay').to_numpy(), feats)
    p_rep = np.mean([_fit(m, params[m], 2, train.X, train.S, train.y, train.groups, cfg['seed'])
                     .predict_proba(rep.X, rep.S)[:, 1] for m in members], axis=0)
    oof = pd.read_parquet(RESULTS_DIR / 'fall_oof.parquet')
    daily = oof['dataset'].isin(DAILY_LIFE_OOF).to_numpy()
    # event-level sensitivity: a fall trial counts as detected if any of its impact windows alarms
    fall_peak = oof[oof['y'] == 1].groupby(['dataset', 'subject', 'trial'], observed=True)['winner_p1'].max()
    out = {'model': fall_result['stage3']['winner'], 'features': 'accelerometer only',
           'replay_datasets': sorted(rep.table['dataset'].unique()),
           'replay_people': int(rep.table['subject'].nunique()), 'thresholds': {}}
    for thr in FALL_THRESHOLDS:
        held = _alarms(rep.table, p_rep, thr)
        cv_fa = _alarms(oof[daily], oof.loc[daily, 'winner_p1'].to_numpy(), thr)
        out['thresholds'][str(thr)] = {
            'heldout_hours': held['hours'], 'heldout_events': held['events'],
            'heldout_false_alarms_per_8h': held['false_alarms_per_8h'],
            'oof_daily_life_hours': cv_fa['hours'],
            'oof_daily_life_false_alarms_per_8h': cv_fa['false_alarms_per_8h'],
            'oof_fall_events': int(len(fall_peak)),
            'oof_fall_sensitivity': float((fall_peak >= thr).mean()),
        }
    return out


def run_tournaments(heads: Optional[List[str]] = None) -> Dict[str, dict]:
    from .report import write_report

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    cfg = load_config()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for head in heads or TOURNAMENT_HEADS:
        t0 = time.perf_counter()
        res = run_head(head, cfg)
        if head == 'fall':
            res['specificity_check'] = fall_specificity_check(res, cfg)
        res['runtime_minutes'] = round((time.perf_counter() - t0) / 60, 1)
        (RESULTS_DIR / f'{head}.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
        logger.info('[%s] winner: %s (%s)', head, res['stage3']['winner'], res['stage3']['reason'])
        results[head] = res
        write_report()
    return results
