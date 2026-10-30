"""Weather forecaster tests - no network: synthetic hourly data and a tiny model trained in a temp dir."""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import pytest

from src.ml.weather import calibration, hazards, serving
from src.ml.weather.config import TARGETS, load_config
from src.ml.weather.features import MIN_HISTORY_H, origin_features, rain24_target, row_features
from src.ml.weather.predict import finalize

TZ = 'Asia/Kolkata'


def synthetic(days: int = 420, seed: int = 0) -> pd.DataFrame:
    """Chennai-like hourly series: diurnal + annual cycles, AR noise, intermittent rain bursts."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range('2024-01-01', periods=days * 24, freq='h', tz='UTC', name='time')
    n = len(idx)
    hod = (idx.hour + 5.5) % 24
    doy = idx.dayofyear.to_numpy()
    ar = np.zeros(n)
    for i in range(1, n):
        ar[i] = 0.95 * ar[i - 1] + rng.normal(0, 0.3)
    temp = 28 + 3 * np.sin(2 * np.pi * (hod - 9) / 24) + 2.5 * np.sin(2 * np.pi * (doy - 80) / 365) + ar
    rh = np.clip(75 - 3.0 * (temp - 28) + rng.normal(0, 3, n), 20, 100)
    rain = np.where(rng.random(n) < 0.04, rng.gamma(0.6, 3.0, n), 0.0)
    wind = np.abs(3.5 + 1.2 * np.sin(2 * np.pi * (hod - 14) / 24) + rng.normal(0, 0.6, n))
    pres = 1008 + 1.2 * np.sin(4 * np.pi * hod / 24) - 3 * np.sin(2 * np.pi * (doy - 80) / 365) + 0.5 * ar
    df = pd.DataFrame({'temp': temp, 'rh': rh, 'rain': rain, 'wind': wind, 'gust': wind * 1.8, 'pres': pres,
                       'dwpt': temp - (100 - rh) / 5, 'cloud': np.clip(50 + 10 * ar, 0, 100)}, index=idx).astype('float32')
    df.attrs['source'] = 'synthetic'
    return df


def tiny_cfg() -> dict:
    import copy
    cfg = copy.deepcopy(load_config())
    cfg['split'].update({'test_months': 2, 'cal_months': 2, 'origin_stride_h': 24})
    cfg['lgbm']['rows_per_group'] = 1500
    cfg['lgbm']['params']['num_iterations'] = 15
    cfg['seq'].update({'epochs': 1, 'hidden': 8, 'train_stride_h': 24, 'batch': 128})
    return cfg


@pytest.fixture(scope='module')
def trained(tmp_path_factory):
    from src.ml.weather import train
    root = tmp_path_factory.mktemp('weather')
    metrics = train.run(df=synthetic(), cfg=tiny_cfg(), out_root=root / 'models', version='t', bt_root=root / 'bt')
    return root / 'models', metrics


@pytest.fixture(scope='module')
def svc(trained):
    return serving.WeatherService.load(trained[0] / 'registry.json')


# ─── features ────────────────────────────────────────────────────────────────

def test_origin_features_are_causal():
    df = synthetic(days=30)
    full = origin_features(df, TZ)
    for t in (MIN_HISTORY_H, 400, len(df) - 30):
        trunc = origin_features(df.iloc[:t + 1], TZ)
        pd.testing.assert_series_equal(full.iloc[t], trunc.iloc[-1], check_names=False)


def test_row_features_ignore_future_values():
    df = synthetic(days=30)
    F = origin_features(df, TZ)
    values = {c: df[c].to_numpy() for c in df}
    t = 500
    pos, h = np.full(48, t), np.arange(1, 49)
    a = row_features(F, values, pos, h)
    poisoned = {c: v.copy() for c, v in values.items()}
    for v in poisoned.values():
        v[t + 1:] = 1e6                       # anything read after the origin would show up
    b = row_features(F, poisoned, pos, h)
    pd.testing.assert_frame_equal(a, b)
    assert np.isfinite(a.to_numpy()).all()


def test_rain24_target_sums_next_day():
    vals = {'rain': np.arange(100, dtype=np.float32)}
    assert rain24_target(vals, np.array([10]), np.array([24]))[0] == pytest.approx(sum(range(11, 35)))


# ─── quantiles ───────────────────────────────────────────────────────────────

def test_finalize_monotone_and_bounded():
    rng = np.random.default_rng(1)
    q = rng.normal(0, 50, (20, 48, 3))
    for v in TARGETS:
        out = finalize(v, q)
        assert (np.diff(out, axis=-1) >= 0).all()
    assert finalize('rain', q).min() >= 0
    assert finalize('rh', q).min() >= 0 and finalize('rh', q + 200).max() <= 100


def test_calibration_hits_target_coverage():
    rng = np.random.default_rng(2)
    y = rng.normal(0, 1, (4000, 6))
    pred = np.stack([np.full_like(y, -0.3), np.zeros_like(y), np.full_like(y, 0.3)], axis=-1)   # far too narrow
    off = calibration.fit(pred[:2000], y[:2000], smooth=1)
    cal = calibration.apply('temp', pred[2000:], off)
    cover = ((y[2000:] >= cal[..., 0]) & (y[2000:] <= cal[..., 2])).mean()
    assert 0.76 < cover < 0.84


# ─── hazards ─────────────────────────────────────────────────────────────────

def _fc(H=48, temp=30.0, rh=60.0, rain=0.0, wind=3.0):
    def q(x):
        return np.tile(np.array([x * 0.9, x, x * 1.1]), (H, 1))
    return {'temp': q(temp), 'rh': q(rh), 'rain': q(rain), 'wind': q(wind), 'pres': q(1008.0)}


TIMES = [f'2026-05-01T{h % 24:02d}:00:00Z' for h in range(48)]


def test_heat_index_reference_values():
    # NWS table: 90 F / 70 % RH -> 105-106 F; 80 F / 40 % -> ~80 F (simple formula branch)
    assert hazards.heat_index_c(32.22, 70) * 9 / 5 + 32 == pytest.approx(105.9, abs=1.0)
    assert hazards.heat_index_c(26.67, 40) * 9 / 5 + 32 == pytest.approx(80, abs=1.5)


def test_hazard_rules():
    cfg = load_config()['hazards']
    calm = hazards.detect(TIMES, _fc(), cfg, np.zeros(168), {'watch': 50, 'warning': 100})
    assert calm == []

    fc = _fc()
    fc['temp'][10:14] = [38.0, 41.0, 44.0]           # p50 41 -> warning (>= 40 C)
    out = hazards.detect(TIMES, fc, cfg, np.zeros(168))
    heat = [h for h in out if h['type'] == 'heat']
    assert heat and heat[0]['level'] == 'warning' and heat[0]['from'] == TIMES[10] and heat[0]['to'] == TIMES[13]

    fc = _fc()
    fc['rain'][5] = [2.0, 10.0, 20.0]                # p50 >= 7.6 mm/h
    fc['rain'][6] = [0.0, 2.0, 9.0]                  # only p90 -> watch
    out = [h for h in hazards.detect(TIMES, fc, cfg, np.zeros(168), rain24=np.zeros((2, 3))) if h['type'] == 'heavy_rain']
    assert [(h['level'], h['from']) for h in out] == [('warning', TIMES[5]), ('watch', TIMES[6])]

    out = hazards.detect(TIMES, _fc(), cfg, np.zeros(168), rain24=np.array([[40, 70, 130], [0, 0, 0]]))
    rain = [h for h in out if h['type'] == 'heavy_rain']
    assert rain[0]['level'] == 'warning' and rain[0]['from'] == TIMES[0] and rain[0]['to'] == TIMES[23]

    assert [h['level'] for h in hazards.detect(TIMES, _fc(wind=18.0), cfg, np.zeros(168)) if h['type'] == 'high_wind'] == ['warning']

    wet = np.full(168, 3.0)                          # a very wet week
    out = [h for h in hazards.detect(TIMES, _fc(), cfg, wet, {'watch': 50, 'warning': 100}) if h['type'] == 'flood_risk']
    assert out and out[0]['level'] == 'warning' and 'not a river-flow' in out[0]['reason']
    for h in out:
        assert set(h) == {'type', 'level', 'from', 'to', 'reason'}


# ─── trained artefacts, ONNX, serving ────────────────────────────────────────

def test_registry_and_metrics(trained):
    root, metrics = trained
    reg = json.loads((root / 'registry.json').read_text())
    assert set(reg['chosen']) == set(TARGETS)
    for f, meta in reg['files'].items():
        assert (root / reg['model_dir'] / f).stat().st_size == meta['bytes']
    for v in TARGETS:
        assert len(metrics['test']['chosen'][v]['mae']) == 48


def test_onnx_matches_torch_golden(trained):
    import onnxruntime as ort
    d = trained[0] / 't'
    g = np.load(d / 'seq_golden.npz')
    got = ort.InferenceSession(str(d / 'seq.onnx'), providers=['CPUExecutionProvider']).run(None, {'x': g['x']})[0]
    assert np.abs(got - g['q']).max() < 1e-4
    assert json.loads((d / 'spec.json').read_text())['seq_onnx_parity']['max_abs_diff'] < 1e-4


def test_forecast_payload(svc):
    obs = synthetic(days=20, seed=5)
    t0 = time.perf_counter()
    fc = svc.forecast(obs, hours=48)
    assert time.perf_counter() - t0 < 1.0
    json.dumps(fc)                                   # JSON-able (no NaN / numpy types)
    assert {'site', 'generated_at', 'model_version', 'horizon', 'hazards'} <= set(fc)
    assert set(fc['site']) == {'name', 'lat', 'lon', 'timezone'}
    assert len(fc['horizon']) == 48 and fc['generated_at'].endswith('Z')
    assert pd.Timestamp(fc['horizon'][0]['time']) == obs.index[-1] + pd.Timedelta(hours=1)
    for step in fc['horizon']:
        assert set(step) == {'time', 'temp_c', 'rain_mm', 'wind_ms', 'pressure_hpa', 'rh'}
        for key in ('temp_c', 'rain_mm', 'wind_ms', 'pressure_hpa', 'rh'):
            q = step[key]
            assert q['p10'] <= q['p50'] <= q['p90']
        assert step['rain_mm']['p10'] >= 0 and 0 <= step['rh']['p10'] and step['rh']['p90'] <= 100
    for h in fc['hazards']:
        assert h['type'] in {'heat', 'heavy_rain', 'flood_risk', 'high_wind'} and h['level'] in {'watch', 'warning'}
    assert len(svc.forecast(obs, hours=12)['horizon']) == 12


def test_serving_never_imports_torch():
    import subprocess
    import sys
    code = ('import sys; import src.ml.weather.serving, src.ml.weather.predict, src.ml.weather.hazards; '
            'print("torch" in sys.modules)')
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == 'False'


def test_current_and_card(svc):
    obs = synthetic(days=10, seed=6)
    obs.attrs['source'] = 'offline-csv'
    cur = svc.current(obs)
    assert set(cur) == {'site', 'observed_at', 'temp_c', 'rh', 'rain_mm', 'wind_ms', 'gust_ms', 'pressure_hpa', 'source'}
    assert cur['source'] == 'offline-csv' and cur['observed_at'].endswith('Z')
    card = svc.model_card()
    json.dumps(card)
    assert card['chosen'] and card['backtest']['by_band'] and card['version'] == 't'


def test_fetch_observations_offline_fallback(svc, monkeypatch, tmp_path):
    def boom(*a, **k):
        raise OSError('no network')
    cache = tmp_path / 'open_meteo_chennai_x.parquet'
    synthetic(days=12).to_parquet(cache)
    monkeypatch.setattr(serving, 'fetch_live', boom)
    monkeypatch.setattr(serving, 'latest_cache', lambda name: cache)
    obs = svc.fetch_observations(hours=168)
    assert obs.attrs['source'] == 'offline-cache' and len(obs) >= 168
    monkeypatch.setattr(serving, 'latest_cache', lambda name: None)
    monkeypatch.setattr(serving, 'load_meteostat_csv', lambda cfg: synthetic(days=12))
    assert svc.fetch_observations(hours=168).attrs['source'] == 'offline-csv'
