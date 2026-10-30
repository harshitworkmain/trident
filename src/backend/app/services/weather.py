"""Weather: cached observations + forecast from `src/ml/weather` (refreshed by the scheduler).

The forecast is recomputed every 30 min from live Open-Meteo observations (falling back to local
data offline). Requests are served from the cache, so a slow or failing weather API never slows
the dashboard; the payload says which source and when.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from ..config import get_settings
from ..db import iso, utcnow
from ..errors import Unavailable
from ..realtime import HUB

logger = logging.getLogger('trident.weather')


class _WeatherCache:
    def __init__(self):
        self.svc: Any = None
        self.error: Optional[str] = None
        self.current: Optional[dict] = None
        self.forecast: Optional[dict] = None
        self.card: Optional[dict] = None
        self.updated_at = None
        self.lock = threading.Lock()

    def _service(self):
        if self.svc is None and self.error is None:
            if not get_settings().weather_enabled:
                self.error = 'weather disabled by configuration'
                return None
            try:
                from src.ml.weather.serving import WeatherService
                self.svc = WeatherService.load()
            except Exception as e:
                self.error = f'{type(e).__name__}: {e}'
                logger.warning('weather model unavailable: %s', self.error)
        return self.svc

    def refresh(self) -> bool:
        with self.lock:
            svc = self._service()
            if svc is None:
                return False
            t0 = time.perf_counter()
            obs = svc.fetch_observations(hours=168)
            self.current = svc.current(obs)
            self.forecast = svc.forecast(obs, hours=48)
            self.card = self.card or svc.model_card()
            self.updated_at = utcnow()
            logger.info('weather refreshed in %.1fs (source %s, %d hazards)', time.perf_counter() - t0,
                        self.current.get('source'), len(self.forecast.get('hazards', [])))
        HUB.publish('weather', {'event': 'updated', 'current': self.current, 'forecast_summary': self.summary()})
        return True

    def _ensure(self):
        if self.forecast is None and not self.refresh():
            raise Unavailable('Weather model is not available', {'reason': self.error})

    def get_current(self) -> dict:
        self._ensure()
        return {**self.current, 'cached_at': iso(self.updated_at)}

    def get_forecast(self, hours: int) -> dict:
        self._ensure()
        hours = max(1, min(48, hours))
        return {**self.forecast, 'horizon': self.forecast['horizon'][:hours], 'cached_at': iso(self.updated_at)}

    def get_card(self) -> dict:
        self._ensure()
        return {**self.card, **_card_view(self.card)}

    def summary(self) -> Optional[dict]:
        if self.forecast is None:
            return None
        nxt = self.forecast['horizon'][:24]
        return {'temp_max_24h': max(h['temp_c']['p50'] for h in nxt) if nxt else None,
                'rain_24h_mm': round(sum(h['rain_mm']['p50'] for h in nxt), 1) if nxt else None,
                'hazards': [{'type': h['type'], 'level': h['level']} for h in self.forecast.get('hazards', [])]}

    def status(self) -> dict:
        return {'loaded': self.svc is not None, 'error': self.error, 'updated_at': iso(self.updated_at)}


def _card_view(card: dict) -> dict:
    """Flat fields for the console: skill per variable and horizon, the model chosen at 24 h, training range."""
    by_h = (card.get('backtest') or {}).get('by_horizon', {})
    skill = [{'variable': var, 'horizon_h': int(h), 'model_mae': m.get('mae'), 'skill': m.get('skill_vs_persistence'),
              'skill_vs_seasonal_naive': m.get('skill_vs_seasonal_naive'), 'coverage_80': m.get('coverage_80'),
              'persistence_mae': (m['mae'] / (1 - m['skill_vs_persistence'])
                                  if m.get('mae') is not None and m.get('skill_vs_persistence') not in (None, 1) else None)}
             for var, hs in by_h.items() for h, m in hs.items()]
    data = card.get('data') or {}
    return {'model_version': card.get('version'), 'skill': skill,
            'chosen_by_band': card.get('chosen'),
            'chosen': {var: bands.get('13-24', next(iter(bands.values()), None)) for var, bands in
                       (card.get('chosen') or {}).items()},
            'training_data': {'from': data.get('data_start'), 'to': data.get('data_end'), 'rows': data.get('rows'),
                              'source': 'Open-Meteo historical archive (ERA5), hourly'}}


WEATHER = _WeatherCache()
