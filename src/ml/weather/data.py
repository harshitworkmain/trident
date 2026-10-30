"""Hourly weather observations: Open-Meteo archive (training), Open-Meteo live (serving), Meteostat CSV (offline).

Every loader returns the same frame: a tz-aware UTC hourly DatetimeIndex and canonical columns
    temp (°C), rh (%), rain (mm/h), wind (m/s), gust (m/s), pres (surface hPa), dwpt (°C), cloud (%)
with `attrs['source']` in {'open-meteo', 'offline-cache', 'offline-csv'}.

Sources
- archive : https://archive-api.open-meteo.com/v1/archive   (ERA5/ERA5-Land reanalysis + ERA5T, ~5 day lag)
- live    : https://api.open-meteo.com/v1/forecast?past_days=..&forecast_days=1  (model analysis up to now)
Both are free and keyless. Requests use timezone=GMT so timestamps are UTC (India has no DST,
so this is equivalent to asking for Asia/Kolkata and shifting by 5:30).

    python -m src.ml.weather.data            # download / refresh the training cache
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT, RAW_DIR, load_config

logger = logging.getLogger('weather.data')

ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'
LIVE_URL = 'https://api.open-meteo.com/v1/forecast'
# Open-Meteo name -> canonical column. wind_speed_unit=ms is requested, so no conversion needed.
OM_VARS = {'temperature_2m': 'temp', 'relative_humidity_2m': 'rh', 'precipitation': 'rain',
           'wind_speed_10m': 'wind', 'wind_gusts_10m': 'gust', 'surface_pressure': 'pres',
           'dew_point_2m': 'dwpt', 'cloud_cover': 'cloud'}
COLUMNS = list(OM_VARS.values())
MAX_INTERP_GAP_H = 6      # short gaps are interpolated; longer ones stay NaN (LightGBM handles NaN)


# ─── Open-Meteo ──────────────────────────────────────────────────────────────

def _om_frame(payload: dict) -> pd.DataFrame:
    h = payload['hourly']
    idx = pd.to_datetime(h['time']).tz_localize('UTC')
    df = pd.DataFrame({col: np.asarray(h.get(om, [np.nan] * len(idx)), dtype=float) for om, col in OM_VARS.items()},
                      index=idx)
    df.index.name = 'time'
    return df


def _om_get(url: str, params: dict, timeout: float = 60.0) -> dict:
    import httpx
    r = httpx.get(url, params={**params, 'hourly': ','.join(OM_VARS), 'wind_speed_unit': 'ms', 'timezone': 'GMT'},
                  timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_archive(site: dict, start: str, end: str) -> pd.DataFrame:
    """Download [start, end] from the archive API in yearly chunks (keeps each response small)."""
    parts, y0, y1 = [], int(start[:4]), int(end[:4])
    for year in range(y0, y1 + 1):
        s = max(start, f'{year}-01-01')
        e = min(end, f'{year}-12-31')
        logger.info('archive %s .. %s', s, e)
        parts.append(_om_frame(_om_get(ARCHIVE_URL, {'latitude': site['lat'], 'longitude': site['lon'],
                                                      'start_date': s, 'end_date': e})))
    return clean(pd.concat(parts))


def cache_path(site_name: str, start: str, end: str) -> Path:
    return RAW_DIR / f'open_meteo_{site_name}_{start}_{end}.parquet'


def latest_cache(site_name: str) -> Optional[Path]:
    files = sorted(RAW_DIR.glob(f'open_meteo_{site_name}_*.parquet'))
    return files[-1] if files else None


def load_history(cfg: Optional[dict] = None, refresh: bool = False, offline: bool = False) -> pd.DataFrame:
    """Training history. Uses the newest parquet cache; downloads if missing (or `refresh`).

    Falls back to the cache, then to the Meteostat CSV, if the network is unavailable.
    """
    cfg = cfg or load_config()
    site, cached = cfg['site'], latest_cache(cfg['site']['name'])
    if cached is not None and not refresh:
        return _read_cache(cached)
    if not offline:
        end = (date.today() - timedelta(days=cfg['data']['archive_lag_days'])).isoformat()
        try:
            df = fetch_archive(site, cfg['data']['start'], end)
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            path = cache_path(site['name'], cfg['data']['start'], end)
            df.to_parquet(path)
            logger.info('cached %d rows -> %s', len(df), path)
            df.attrs['source'] = 'open-meteo'
            return df
        except Exception as exc:  # network down, API change: degrade, never crash training
            logger.warning('archive download failed (%s); falling back to local data', exc)
    if cached is not None:
        return _read_cache(cached)
    return load_meteostat_csv(cfg)


def _read_cache(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.attrs['source'] = 'offline-cache'
    df.attrs['path'] = str(path)
    return df


def fetch_live(site: dict, hours: int, now: Optional[datetime] = None, timeout: float = 10.0) -> pd.DataFrame:
    """Most recent `hours` hourly values up to the current hour from the forecast API (model analysis)."""
    past_days = min(92, math.ceil(hours / 24) + 1)
    df = _om_frame(_om_get(LIVE_URL, {'latitude': site['lat'], 'longitude': site['lon'],
                                      'past_days': past_days, 'forecast_days': 1}, timeout=timeout))
    now = pd.Timestamp(now or datetime.now(timezone.utc)).floor('h')
    df = clean(df.loc[:now]).iloc[-hours:]
    df.attrs['source'] = 'open-meteo'
    return df


# ─── Meteostat CSV (offline) ─────────────────────────────────────────────────

def load_meteostat_csv(cfg: Optional[dict] = None, path: Optional[Path] = None) -> pd.DataFrame:
    """Meteostat hourly export (UTC timestamps). wspd/wpgt km/h -> m/s; sea-level -> surface pressure."""
    cfg = cfg or load_config()
    path = Path(path or PROJECT_ROOT / cfg['site']['local_csv'])
    raw = pd.read_csv(path, parse_dates=['time'])
    # Hypsometric reduction near sea level: ~0.12 hPa per metre.
    pres = raw['pres'] - 0.12 * cfg['site'].get('elevation_m', 0)
    df = pd.DataFrame({'temp': raw['temp'], 'rh': raw['rhum'], 'rain': raw['prcp'],
                       'wind': raw['wspd'] / 3.6, 'gust': raw['wpgt'] / 3.6, 'pres': pres,
                       'dwpt': raw['dwpt'], 'cloud': np.nan},
                      index=pd.DatetimeIndex(raw['time']).tz_localize('UTC'))
    df.index.name = 'time'
    df = clean(df)
    df.attrs['source'] = 'offline-csv'
    return df


# ─── cleaning ────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Regular hourly UTC grid, canonical columns, physical ranges, short gaps interpolated."""
    df = df[~df.index.duplicated(keep='last')].sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    full = pd.date_range(df.index[0], df.index[-1], freq='h', tz='UTC', name='time')
    df = df.reindex(full)
    for c in COLUMNS:
        if c not in df:
            df[c] = np.nan
    df = df[COLUMNS].astype('float32')
    df['rain'] = df['rain'].clip(lower=0).fillna(0.0)   # missing rain is overwhelmingly "no rain"
    df['rh'] = df['rh'].clip(0, 100)
    df[['wind', 'gust']] = df[['wind', 'gust']].clip(lower=0)
    smooth = [c for c in COLUMNS if c != 'rain']
    df[smooth] = df[smooth].interpolate(limit=MAX_INTERP_GAP_H, limit_area='inside')
    return df


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
    h = load_history(refresh=True)
    print(h.attrs.get('source'), h.shape, h.index[0], h.index[-1])
    print(h.describe().T.round(2))
