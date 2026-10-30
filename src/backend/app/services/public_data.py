"""External public data, cached in the database by a scheduled job.

Rivers: daily discharge (m3/s) from the GloFAS hydrological model via the free, keyless Open-Meteo
Flood API (https://open-meteo.com/en/docs/flood-api), 30 days back and 14 days ahead, for the
three rivers that flood Chennai. GloFAS cells are ~5 km, so the values describe the river reach,
not a street; they are shown as such, with the source and fetch time.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import httpx

from ..db import iso, read_session, utcnow, write_tx
from ..models import PublicDataCache

logger = logging.getLogger('trident.public_data')
FLOOD_API = 'https://flood-api.open-meteo.com/v1/flood'
SOURCE = 'Open-Meteo Flood API (GloFAS v4)'
RIVERS = [('Adyar', 13.005, 80.205), ('Cooum', 13.072, 80.240), ('Kosasthalaiyar', 13.215, 80.250)]


def _trend(series: List[Optional[float]]) -> str:
    vals = [v for v in series if v is not None]
    if len(vals) < 4:
        return 'steady'
    recent, before = sum(vals[-2:]) / 2, sum(vals[-5:-2]) / 3
    if before <= 0:
        return 'steady'
    ratio = recent / before
    return 'rising' if ratio > 1.15 else 'falling' if ratio < 0.87 else 'steady'


def refresh_rivers() -> int:
    params = {'latitude': ','.join(str(r[1]) for r in RIVERS), 'longitude': ','.join(str(r[2]) for r in RIVERS),
              'daily': 'river_discharge,river_discharge_median,river_discharge_max', 'past_days': 30,
              'forecast_days': 14}
    r = httpx.get(FLOOD_API, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    data = data if isinstance(data, list) else [data]
    today = utcnow().date().isoformat()
    rivers = []
    for (name, lat, lng), d in zip(RIVERS, data):
        daily = d['daily']
        days = daily['time']
        q = daily['river_discharge']
        i = max([k for k, t in enumerate(days) if t <= today] or [0])
        rivers.append({'name': name, 'lat': d['latitude'], 'lng': d['longitude'], 'date': days[i],
                       'discharge_m3s': q[i], 'discharge_p50_30d': daily['river_discharge_median'][i],
                       'trend': _trend(q[max(0, i - 6):i + 1]),
                       'history': [{'date': t, 'discharge_m3s': v} for t, v in zip(days[:i + 1], q[:i + 1])],
                       'forecast': [{'date': t, 'discharge_m3s': v} for t, v in zip(days[i + 1:], q[i + 1:])],
                       'source': SOURCE})
    with write_tx() as s:
        row = s.get(PublicDataCache, 'rivers')
        if row is None:
            s.add(PublicDataCache(key='rivers', payload=rivers, source=SOURCE))
        else:
            row.payload, row.fetched_at = rivers, utcnow()
    logger.info('river discharge refreshed: %s', {r['name']: r['discharge_m3s'] for r in rivers})
    return len(rivers)


def rivers() -> dict:
    with read_session() as s:
        row = s.get(PublicDataCache, 'rivers')
        if row is None:
            return {'items': [], 'source': SOURCE, 'fetched_at': None}
        return {'items': row.payload, 'source': row.source, 'fetched_at': iso(row.fetched_at)}
