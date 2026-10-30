"""Weather service used by the backend: observations, 1-48 h quantile forecast, hazards, model card.

    from src.ml.weather.serving import WeatherService
    svc = WeatherService.load()                 # reads models/weather/registry.json
    obs = svc.fetch_observations(hours=168)     # Open-Meteo live -> offline cache -> Meteostat CSV
    fc  = svc.forecast(obs, hours=48)           # JSON-able /weather/forecast payload
    svc.current(obs); svc.model_card()

Runtime dependencies: numpy, pandas, lightgbm, onnxruntime, pyyaml, httpx (live fetch only).
torch is never imported here. Instances are read-only after load() and safe to share across
requests; load once at startup (~1-3 s, mostly parsing LightGBM text models).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from . import calibration
from .config import REGISTRY_PATH, TARGETS, load_config
from .data import clean, fetch_live, latest_cache, load_meteostat_csv
from .hazards import detect
from .predict import BASELINES, Predictor, band_of, finalize, load_spec

logger = logging.getLogger('weather.serving')


def _iso(ts) -> str:
    return pd.Timestamp(ts).tz_convert('UTC').strftime('%Y-%m-%dT%H:%M:%SZ')


def _num(x, nd: int = 2):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


class WeatherService:
    def __init__(self, registry: dict, model_dir: Path, cfg: Optional[dict] = None):
        self.registry, self.model_dir = registry, Path(model_dir)
        self.cfg = cfg or load_config()
        self.spec = load_spec(self.model_dir)
        self.version = registry['version']
        self.chosen: Dict[str, Dict[str, str]] = registry['chosen']
        self.groups = self.spec['horizon_groups']
        self.H = self.spec['horizons']
        self.offsets = json.loads((self.model_dir / 'calibration.json').read_text())['offsets']
        hz = json.loads((self.model_dir / 'hazards.json').read_text())
        self.hazard_cfg, self.api_thresholds = hz['thresholds'], hz['api_thresholds_mm']
        needed = {c for bands in self.chosen.values() for c in bands.values()} | {'lgbm'}   # lgbm: 24 h rain for hazards
        self.predictor = Predictor(self.model_dir, self.spec, load=needed | set(BASELINES))
        mpath = self.model_dir / 'metrics.json'
        self._metrics = json.loads(mpath.read_text()) if mpath.exists() else {}

    @classmethod
    def load(cls, registry_path: Optional[Path] = None) -> 'WeatherService':
        path = Path(registry_path or REGISTRY_PATH)
        reg = json.loads(path.read_text())
        return cls(reg, path.parent / reg['model_dir'])

    @property
    def site(self) -> dict:
        return dict(self.spec['site'])

    # ─── observations ────────────────────────────────────────────────────────

    def fetch_observations(self, hours: int = 168, now: Optional[datetime] = None) -> pd.DataFrame:
        """Hourly UTC frame of the most recent hours; at least `min_history_h` (192) rows so every
        model feature (168 h lag) is defined. attrs['source'] says where it came from."""
        n = max(int(hours), int(self.spec['min_history_h']))
        try:
            return fetch_live(self.site, n, now=now)
        except Exception as exc:   # offline / API failure: degrade to the newest local data
            logger.warning('live fetch failed (%s); using offline data', exc)
        cache = latest_cache(self.site['name'])
        if cache is not None:
            df = pd.read_parquet(cache).iloc[-n:]
            df.attrs['source'] = 'offline-cache'
            return df
        df = load_meteostat_csv(self.cfg).iloc[-n:]
        df.attrs['source'] = 'offline-csv'
        return df

    def current(self, obs: pd.DataFrame) -> dict:
        row = obs.dropna(subset=['temp']).iloc[-1]
        return {'site': self.site, 'observed_at': _iso(row.name), 'temp_c': _num(row['temp'], 1),
                'rh': _num(row['rh'], 0), 'rain_mm': _num(row['rain'], 1), 'wind_ms': _num(row['wind'], 1),
                'gust_ms': _num(row.get('gust', np.nan), 1), 'pressure_hpa': _num(row['pres'], 1),
                'source': obs.attrs.get('source', 'unknown')}

    # ─── forecast ────────────────────────────────────────────────────────────

    def forecast_arrays(self, obs: pd.DataFrame, hours: int = 48):
        """(origin timestamp, {var: (hours, 3)} calibrated quantiles, rain24 (2, 3) or None)."""
        hours = int(min(max(hours, 1), self.H))
        df = clean(obs.copy())
        if len(df) < self.spec['min_history_h']:
            logger.warning('only %d h of observations (< %d): long-lag features are missing', len(df),
                           self.spec['min_history_h'])
        prep = self.predictor.prepare(df)
        pos = np.array([len(df) - 1])
        cands = {c for b in self.chosen.values() for c in b.values()} | {'lgbm', 'climatology'}
        if len(df) < self.spec['seq']['lookback']:
            cands -= {'gru', 'blend'}
        raw = self.predictor.predict(prep, pos, self.H, candidates=cands)
        r24 = raw.get('lgbm', {}).pop('rain24', None)
        fc = {}
        for v in TARGETS:
            out = np.full((self.H, 3), np.nan)
            for h in range(1, self.H + 1):
                c = self.chosen[v][band_of(h, self.groups)]
                if c not in raw:
                    c = 'lgbm'
                out[h - 1] = calibration.apply(v, raw[c][v][:, h - 1:h], np.asarray(self.offsets[c][v])[h - 1:h])[0, 0]
            bad = ~np.isfinite(out).all(axis=1)
            if bad.any():   # missing inputs (e.g. gappy offline CSV): fall back to calibrated climatology
                clim = calibration.apply(v, raw['climatology'][v], self.offsets['climatology'][v])[0]
                out[bad] = clim[bad]
            fc[v] = finalize(v, out)[:hours]
        if r24 is not None:
            r24 = calibration.apply('rain', r24, self.offsets['rain24']['rain24'])[0]
        return df.index[-1], fc, r24

    def forecast(self, obs: pd.DataFrame, hours: int = 48) -> dict:
        origin, fc, r24 = self.forecast_arrays(obs, hours)
        n = len(fc['temp'])
        times = [_iso(origin + pd.Timedelta(hours=h)) for h in range(1, n + 1)]
        nd = {'temp': 1, 'rh': 0, 'rain': 2, 'wind': 1, 'pres': 1}
        horizon = []
        for i, t in enumerate(times):
            step = {'time': t}
            for v, (key, _, _) in TARGETS.items():
                step[key] = {q: _num(fc[v][i, k], nd[v]) for k, q in enumerate(('p10', 'p50', 'p90'))}
            horizon.append(step)
        past_rain = clean(obs.copy())['rain'].to_numpy()
        hz = detect(times, fc, self.hazard_cfg, past_rain, self.api_thresholds, r24)
        return {'site': self.site, 'generated_at': _iso(datetime.now(timezone.utc)), 'model_version': self.version,
                'issued_from': _iso(origin), 'source': obs.attrs.get('source', 'unknown'),
                'horizon': horizon, 'hazards': hz}

    # ─── model card ──────────────────────────────────────────────────────────

    def model_card(self) -> dict:
        m = self._metrics
        skill = {}
        for v, bands in m.get('band_summary_test', {}).items():
            skill[v] = {b: {'chosen': self.chosen[v][b], **{k: _num(x, 3) for k, x in row['chosen'].items()},
                            'candidates_pinball': {c: _num(r['pinball'], 4) for c, r in row.items() if c != 'chosen'}}
                        for b, row in bands.items()}
        headline = {}
        comp = m.get('test', {}).get('chosen', {})
        for v in comp:
            headline[v] = {str(h): {k: _num(comp[v][k][h - 1], 3) for k in
                                    ('mae', 'rmse', 'coverage_80', 'skill_vs_persistence', 'skill_vs_seasonal_naive')}
                           for h in (1, 6, 12, 24, 48)}
        return {'version': self.version, 'site': self.site, 'created_utc': self.registry.get('created_utc'),
                'candidates': self.registry.get('candidates'), 'chosen': self.chosen,
                'data': self.registry.get('data'), 'quantiles': self.spec['quantiles'], 'horizons': self.H,
                'backtest': {'by_band': skill, 'by_horizon': headline,
                             'rain_events': m.get('rain_events_test')},
                'hazards': {'thresholds': self.hazard_cfg, 'flood_risk_api_thresholds_mm': self.api_thresholds,
                            'note': 'flood_risk is an antecedent-precipitation risk index, not a river-flow forecast'},
                'card_markdown': 'card.md'}
