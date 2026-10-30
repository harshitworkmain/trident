"""Train, backtest, calibrate, select and register the weather forecaster.

1. history  : Open-Meteo archive cache (data.load_history); split by time into
              train | calibration (6 months) | test (final 12 months).
2. backtest : baselines, LightGBM and the GRU are fitted on train only; every candidate forecasts
              1-48 h from origins every 3 h across calibration and test (predict.Predictor - the
              serving code path, ONNX for the GRU).
3. calibrate: per candidate x variable x horizon quantile offsets fitted on the calibration slice.
4. select   : per variable x horizon band, lowest calibrated pinball loss on the calibration
              slice. The test window is only scored, never used to choose.
5. refit    : all models refitted on the full history (same settings), calibration offsets and
              selection carried over; written to models/weather/<version>/ + registry.json.

    python -m src.ml.weather.train            # full run (~45-70 min on 3 CPU threads)
    python -m src.ml.weather.train --quick    # smoke run on 3 years / tiny models -> models/weather/_quick/
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from . import backtest, baselines, calibration, gbm, hazards
from .config import DATA_ROOT, MODELS_DIR, TARGETS, load_config, site as site_of
from .data import load_history
from .features import MIN_HISTORY_H
from .predict import CANDIDATES, Predictor, Prepared

logger = logging.getLogger('weather.train')
MODEL_VERSION = '1.0.0'
HEADLINE_H = (6, 24, 48)


def quick_overrides(cfg: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    cfg['split'].update({'test_months': 3, 'cal_months': 2, 'origin_stride_h': 12})
    cfg['lgbm']['rows_per_group'] = 8000
    cfg['lgbm']['params']['num_iterations'] = 40
    cfg['seq'].update({'epochs': 1, 'hidden': 16, 'train_stride_h': 6})
    return cfg


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ─── fitting one model directory ─────────────────────────────────────────────

def fit_models(df: pd.DataFrame, prep: Prepared, train_pos: np.ndarray, last_target: int, cfg: dict,
               out_dir: Path) -> dict:
    """Fit baselines, LightGBM and GRU on origins in `train_pos` with targets <= `last_target`."""
    from . import seqmodel   # torch is imported only when training
    H, groups, tz = cfg['horizons'], cfg['horizon_groups'], cfg['site']['timezone']
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    timing = {}
    t0 = time.perf_counter()
    tables = baselines.fit(prep.values, prep.F, train_pos[train_pos + H <= last_target], H)
    (out_dir / 'baselines.json').write_text(json.dumps(tables))
    timing['baselines_s'] = time.perf_counter() - t0
    g = gbm.fit(prep.F, prep.values, train_pos, last_target, groups, cfg['lgbm']['rows_per_group'],
                cfg['lgbm']['params'], out_dir / 'lgbm')
    timing['lgbm_s'] = g['seconds']
    model, seq_spec = seqmodel.fit(df, tz, train_pos, last_target, cfg['seq'], H)
    parity = seqmodel.export_onnx(model, seq_spec, out_dir / 'seq.onnx')
    # golden file: lets tests check the ONNX graph against torch without importing torch
    x = np.random.default_rng(1).standard_normal((8, seq_spec['lookback'], len(seq_spec['mean']))).astype(np.float32)
    import torch
    with torch.no_grad():
        np.savez_compressed(out_dir / 'seq_golden.npz', x=x, q=model(torch.from_numpy(x)).numpy())
    timing['gru_s'] = seq_spec['train_seconds']
    spec = {'site': site_of(cfg), 'horizons': H, 'horizon_groups': groups, 'quantiles': [0.1, 0.5, 0.9],
            'min_history_h': MIN_HISTORY_H, 'lgbm_features': g['features'], 'lgbm_params': cfg['lgbm'],
            'seq': {k: v for k, v in seq_spec.items() if k != 'history'}, 'seq_config': cfg['seq'],
            'seq_onnx_parity': parity, 'trained_on': {'first_origin': str(df.index[int(train_pos[0])]),
                                                      'last_target': str(df.index[last_target])},
            'timing': timing}
    (out_dir / 'spec.json').write_text(json.dumps(spec, indent=1))
    logger.info('fitted models in %s (%s); onnx parity %.2e', out_dir, {k: round(v) for k, v in timing.items()},
                parity['max_abs_diff'])
    return {'spec': spec, 'gru_history': seq_spec['history']}


# ─── run ─────────────────────────────────────────────────────────────────────

def run(quick: bool = False, df: Optional[pd.DataFrame] = None, cfg: Optional[dict] = None,
        out_root: Optional[Path] = None, version: Optional[str] = None, refit: bool = True,
        bt_root: Optional[Path] = None) -> dict:
    t_start = time.perf_counter()
    cfg = copy.deepcopy(cfg or load_config())
    if quick:
        cfg = quick_overrides(cfg)
    out_root = Path(out_root or (MODELS_DIR / '_quick' if quick else MODELS_DIR))
    version = version or (f'{MODEL_VERSION}-quick' if quick else MODEL_VERSION)
    df = df if df is not None else load_history(cfg)
    source = df.attrs.get('source', 'unknown') + (f" ({Path(df.attrs['path']).name})" if 'path' in df.attrs else '')
    if quick and len(df) > 3 * 8766:
        df = df.iloc[-3 * 8766:]
    H, groups, tz, stride = cfg['horizons'], cfg['horizon_groups'], cfg['site']['timezone'], cfg['split']['origin_stride_h']
    idx, T = df.index, len(df)
    test_start = int(idx.searchsorted(idx[-1] - pd.DateOffset(months=cfg['split']['test_months'])))
    cal_start = int(idx.searchsorted(idx[test_start] - pd.DateOffset(months=cfg['split']['cal_months'])))
    train_pos = np.arange(MIN_HISTORY_H, cal_start)
    cal_pos = np.arange(cal_start, test_start - H, stride)       # targets stay before the test window
    test_pos = np.arange(test_start, T - H, stride)
    split = {'data_source': source, 'data_start': str(idx[0]), 'data_end': str(idx[-1]), 'rows': T,
             'train': [str(idx[train_pos[0]]), str(idx[cal_start - 1])],
             'calibration': [str(idx[cal_start]), str(idx[test_start - 1])], 'test': [str(idx[test_start]), str(idx[-1])],
             'n_cal_origins': len(cal_pos), 'n_test_origins': len(test_pos), 'origin_stride_h': stride}
    logger.info('split %s', split)

    # 1-2. backtest models (train only) and forecasts from every cal / test origin
    prep = Prepared(df, tz)
    bt_dir = Path(bt_root or DATA_ROOT / 'processed' / 'weather') / f'backtest_{version}'   # not registered
    fitted = fit_models(df, prep, train_pos, cal_start - 1, cfg, bt_dir)
    predictor = Predictor(bt_dir, fitted['spec'])
    prep_bt = predictor.prepare(df)
    raw_cal, r24_cal = backtest.forecast_origins(predictor, prep_bt, cal_pos, H)
    raw_test, r24_test = backtest.forecast_origins(predictor, prep_bt, test_pos, H)
    tr_cal, tr_test = backtest.truth(prep_bt, cal_pos, H), backtest.truth(prep_bt, test_pos, H)

    # 3. calibration on the calibration slice
    offsets = calibration.fit_all(raw_cal, tr_cal)
    offsets['rain24'] = {'rain24': calibration.fit(r24_cal, tr_cal['rain24'], smooth=1).round(5).tolist()}
    cal_cal, cal_test = backtest.calibrate(raw_cal, offsets), backtest.calibrate(raw_test, offsets)

    # 4. selection on the calibration slice; scoring on test
    scores_cal = backtest.score(cal_cal, tr_cal)
    chosen = backtest.select(scores_cal, groups)
    scores_test = backtest.score(cal_test, tr_test)
    scores_test_raw = backtest.score(raw_test, tr_test)
    comp_test = backtest.compose(cal_test, chosen, groups, H)
    comp_scores = backtest.score({'chosen': comp_test}, tr_test)['chosen']
    for v in TARGETS:
        comp_scores[v].update(backtest.point_skill(np.asarray(comp_scores[v]['mae']), prep_bt, test_pos, tr_test, v, H))
        comp_scores[v]['coverage_80_uncalibrated'] = backtest.score(
            {'c': backtest.compose(raw_test, chosen, groups, H)}, tr_test)['c'][v]['coverage_80']
    r24_cal_test = calibration.apply('rain', r24_test, offsets['rain24']['rain24'])
    hz = cfg['hazards']
    events = backtest.rain_events(comp_test['rain'], r24_cal_test, tr_test, groups, hz['rain_hourly_mm'],
                                  hz['rain_24h_heavy_mm'])
    events['acc24_sum_of_hourly_p50'] = backtest.metrics.events(comp_test['rain'][:, :24, 1].sum(axis=1),
                                                                tr_test['rain24'][:, 0], hz['rain_24h_heavy_mm'])
    del raw_cal, raw_test, cal_cal, cal_test

    # 5. production refit on everything
    model_dir = out_root / version
    if refit:
        all_pos = np.arange(MIN_HISTORY_H, T)
        final = fit_models(df, prep, all_pos, T - 1, cfg, model_dir)
    else:
        if model_dir.exists():
            shutil.rmtree(model_dir)
        shutil.copytree(bt_dir, model_dir)
        final = fitted
    (model_dir / 'calibration.json').write_text(json.dumps(
        {'method': 'per-horizon empirical quantile offsets (5 h smoothing), fitted on the calibration slice '
                   'with backtest models', 'offsets': offsets}))
    (model_dir / 'hazards.json').write_text(json.dumps(
        {'thresholds': hz, 'api_thresholds_mm': hazards.api_thresholds(prep.values['rain'], hz)}, indent=1))

    band_summary = _band_summary(scores_test, comp_scores, groups)
    metrics = {'version': version, 'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'split': split, 'chosen': chosen,
               'selection_pinball_cal': {c: {v: {b: float(np.mean(np.asarray(scores_cal[c][v]['pinball'])[i]))
                                                 for b, i in backtest.bands(groups).items()} for v in TARGETS}
                                         for c in scores_cal},
               'test': {'chosen': comp_scores, 'candidates': scores_test, 'candidates_uncalibrated_coverage':
                        {c: {v: s[v]['coverage_80'] for v in s} for c, s in scores_test_raw.items()}},
               'band_summary_test': band_summary, 'rain_events_test': events,
               'gru_history': {'backtest': fitted['gru_history'], 'final': final['gru_history']},
               'timing': {'backtest_fit': fitted['spec']['timing'], 'final_fit': final['spec']['timing'],
                          'total_s': time.perf_counter() - t_start}}
    (model_dir / 'metrics.json').write_text(json.dumps(metrics, default=_json_default))
    (model_dir / 'card.md').write_text(model_card(metrics, final['spec']), encoding='utf-8')
    _write_registry(out_root, model_dir, version, chosen, split, final['spec'])
    logger.info('done in %.0fs -> %s', time.perf_counter() - t_start, model_dir)
    return metrics


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def _band_summary(scores_test: dict, comp: dict, groups) -> dict:
    out = {}
    for v in TARGETS:
        out[v] = {}
        for b, i in backtest.bands(groups).items():
            row = {c: {m: float(np.nanmean(np.asarray(scores_test[c][v][m])[i])) for m in ('mae', 'pinball', 'coverage_80')}
                   for c in scores_test}
            row['chosen'] = {m: float(np.nanmean(np.asarray(comp[v][m])[i]))
                             for m in ('mae', 'pinball', 'coverage_80', 'skill_vs_persistence', 'skill_vs_seasonal_naive')}
            out[v][b] = row
    return out


def _write_registry(out_root: Path, model_dir: Path, version: str, chosen: dict, split: dict, spec: dict) -> None:
    files = {str(p.relative_to(model_dir)).replace('\\', '/'): {'sha256': _sha256(p), 'bytes': p.stat().st_size}
             for p in sorted(model_dir.rglob('*')) if p.is_file()}
    reg = {'component': 'weather', 'version': version, 'model_dir': version,
           'created_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'site': spec['site'],
           'horizons': spec['horizons'], 'horizon_bands': [f'{g[0]}-{g[1]}' for g in spec['horizon_groups']],
           'quantiles': spec['quantiles'], 'candidates': list(CANDIDATES), 'chosen': chosen,
           'data': split, 'files': files}
    (out_root / 'registry.json').write_text(json.dumps(reg, indent=1))


# ─── model card ──────────────────────────────────────────────────────────────

def _f(x, nd=2):
    return '–' if x is None or (isinstance(x, float) and not np.isfinite(x)) else f'{x:.{nd}f}'


def headline_rows(metrics: dict) -> list:
    rows = []
    comp, chosen = metrics['test']['chosen'], metrics['chosen']
    from .predict import band_of
    groups = [[int(a) for a in b.split('-')] for b in next(iter(chosen.values()))]
    for v in TARGETS:
        for h in HEADLINE_H:
            i = h - 1
            rows.append({'var': v, 'h': h, 'model': chosen[v][band_of(h, groups)], 'mae': comp[v]['mae'][i],
                         'mae_persistence': comp[v]['mae_persistence'][i], 'mae_seasonal_naive': comp[v]['mae_seasonal_naive'][i],
                         'skill_pers': comp[v]['skill_vs_persistence'][i], 'skill_sn': comp[v]['skill_vs_seasonal_naive'][i],
                         'coverage': comp[v]['coverage_80'][i], 'coverage_raw': comp[v]['coverage_80_uncalibrated'][i]})
    return rows


def model_card(metrics: dict, spec: dict) -> str:
    units = {'temp': '°C', 'rh': '%', 'rain': 'mm/h', 'wind': 'm/s', 'pres': 'hPa'}
    s = metrics['split']
    lines = [f'# Weather forecaster {metrics["version"]} - model card', '',
             f'Site: {spec["site"]["name"]} ({spec["site"]["lat"]}, {spec["site"]["lon"]}). Data: {s["data_source"]} '
             f'{s["data_start"][:10]} .. {s["data_end"][:10]} ({s["rows"]} hourly rows).',
             f'Backtest: models fitted on {s["train"][0][:10]} .. {s["train"][1][:10]}; calibration/selection slice '
             f'{s["calibration"][0][:10]} .. {s["calibration"][1][:10]} ({s["n_cal_origins"]} origins); test '
             f'{s["test"][0][:10]} .. {s["test"][1][:10]} ({s["n_test_origins"]} origins every {s["origin_stride_h"]} h).', '',
             '## Headline (test window, chosen model, calibrated)', '',
             '| variable | h | chosen | MAE | MAE persistence | MAE seasonal-naive | skill vs pers. | skill vs s-naive | p10-p90 coverage (raw) |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in headline_rows(metrics):
        lines.append(f'| {r["var"]} ({units[r["var"]]}) | {r["h"]} | {r["model"]} | {_f(r["mae"], 3)} | {_f(r["mae_persistence"], 3)} | '
                     f'{_f(r["mae_seasonal_naive"], 3)} | {_f(r["skill_pers"])} | {_f(r["skill_sn"])} | '
                     f'{_f(r["coverage"])} ({_f(r["coverage_raw"])}) |')
    lines += ['', '## Candidates by horizon band (test window, calibrated; mean pinball loss, lower is better)', '']
    cands = [c for c in CANDIDATES if c in metrics['test']['candidates']]
    for v in TARGETS:
        lines += [f'**{v}** ({units[v]}) - chosen per band: ' + ', '.join(f'{b}: {c}' for b, c in metrics['chosen'][v].items()), '',
                  '| band | ' + ' | '.join(cands) + ' | chosen MAE | chosen coverage |',
                  '|---' * (len(cands) + 3) + '|']
        for b, row in metrics['band_summary_test'][v].items():
            best = min(cands, key=lambda c: row[c]['pinball'])
            cells = [(f'**{_f(row[c]["pinball"], 4)}**' if c == best else _f(row[c]['pinball'], 4)) for c in cands]
            lines.append(f'| {b} h | ' + ' | '.join(cells) + f' | {_f(row["chosen"]["mae"], 3)} | {_f(row["chosen"]["coverage_80"])} |')
        lines.append('')
    ev = metrics['rain_events_test']
    lines += ['## Heavy rain events (test window)', '',
              '| event | forecast rule | observed | forecast | hits | hit rate | FAR | CSI |', '|---|---|---|---|---|---|---|---|']
    for b, d in ev['hourly'].items():
        for q, e in d.items():
            lines.append(f'| rain >= {e["threshold"]} mm/h, h {b} | {q} | {e["observed_events"]} | {e["forecast_events"]} | '
                         f'{e["hits"]} | {_f(e["hit_rate"])} | {_f(e["false_alarm_ratio"])} | {_f(e["csi"])} |')
    for w, d in ev['acc24'].items():
        for q, e in d.items():
            lines.append(f'| 24 h rain >= {e["threshold"]} mm, {w} | rain24 {q} | {e["observed_events"]} | {e["forecast_events"]} | '
                         f'{e["hits"]} | {_f(e["hit_rate"])} | {_f(e["false_alarm_ratio"])} | {_f(e["csi"])} |')
    e = ev['acc24_sum_of_hourly_p50']
    lines.append(f'| 24 h rain >= {e["threshold"]} mm, next 1-24h | sum of hourly p50 | {e["observed_events"]} | '
                 f'{e["forecast_events"]} | {e["hits"]} | {_f(e["hit_rate"])} | {_f(e["false_alarm_ratio"])} | {_f(e["csi"])} |')
    lines += ['', '## Notes', '',
              '- Skill = 1 - MAE / MAE_ref against plain persistence and plain seasonal-naive (same hour, last observed day).',
              '- Coverage = share of test targets inside the calibrated p10-p90 interval (target 0.80); raw = before calibration.',
              '- Candidates are selected per variable and horizon band on the calibration slice (never on test).',
              f'- GRU ONNX vs torch max |diff| = {spec["seq_onnx_parity"]["max_abs_diff"]:.2e} (normalised units).',
              '- flood_risk hazard is an antecedent-precipitation risk index, not a river-flow forecast.', '']
    return '\n'.join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--quick', action='store_true', help='3 years of data, tiny models, writes models/weather/_quick/')
    ap.add_argument('--no-refit', action='store_true', help='register the backtest models instead of refitting on all data')
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    m = run(quick=args.quick, refit=not args.no_refit)
    for r in headline_rows(m):
        print(f'{r["var"]:5s} h{r["h"]:2d} {r["model"]:15s} MAE {r["mae"]:.3f}  skill pers {r["skill_pers"]:+.2f}  '
              f's-naive {r["skill_sn"]:+.2f}  cov {r["coverage"]:.2f}')


if __name__ == '__main__':
    main()
