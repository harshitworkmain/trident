"""Hazard flags derived from a quantile forecast: heat, heavy_rain, high_wind, flood_risk.

Each hour gets a level (0 none, 1 watch, 2 warning); contiguous hours at the same level become
one {type, level, from, to, reason} episode. Medians drive warnings; the p90 drives watches
("plausible, not expected"). Thresholds live in config/weather.yaml (`hazards`).

flood_risk is an antecedent-precipitation-index (API) *risk index*, i.e. how wet the ground
has been over the last week plus forecast rain, compared with percentiles of the same index in
the training climate. It is NOT a river-flow or inundation forecast: there is no gauge data.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

from .features import antecedent_precip_index

LEVELS = {1: 'watch', 2: 'warning'}


def heat_index_c(temp_c: np.ndarray, rh: np.ndarray) -> np.ndarray:
    """NOAA heat index (Rothfusz regression with NWS adjustments; Steadman's simple form below 80 °F)."""
    T = np.asarray(temp_c, dtype=float) * 9 / 5 + 32
    R = np.clip(np.asarray(rh, dtype=float), 0, 100)
    simple = 0.5 * (T + 61.0 + (T - 68.0) * 1.2 + R * 0.094)
    hi = (-42.379 + 2.04901523 * T + 10.14333127 * R - 0.22475541 * T * R - 6.83783e-3 * T ** 2
          - 5.481717e-2 * R ** 2 + 1.22874e-3 * T ** 2 * R + 8.5282e-4 * T * R ** 2 - 1.99e-6 * T ** 2 * R ** 2)
    low_rh = (R < 13) & (T >= 80) & (T <= 112)
    hi = np.where(low_rh, hi - (13 - R) / 4 * np.sqrt(np.clip(17 - np.abs(T - 95.0), 0, None) / 17), hi)
    high_rh = (R > 85) & (T >= 80) & (T <= 87)
    hi = np.where(high_rh, hi + (R - 85) / 10 * (87 - T) / 5, hi)
    hi = np.where((simple + T) / 2 < 80, simple, hi)
    return (hi - 32) * 5 / 9


def _episodes(kind: str, level: np.ndarray, times: Sequence[str], reason) -> List[dict]:
    out, i, n = [], 0, len(level)
    while i < n:
        if level[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and level[j + 1] == level[i]:
            j += 1
        out.append({'type': kind, 'level': LEVELS[int(level[i])], 'from': times[i], 'to': times[j],
                    'reason': reason(i, j, int(level[i]))})
        i = j + 1
    return out


def detect(times: Sequence[str], fc: Dict[str, np.ndarray], cfg: dict, past_rain: np.ndarray,
           api_thresholds: Optional[dict] = None, rain24: Optional[np.ndarray] = None) -> List[dict]:
    """times: H ISO strings; fc: {var: (H, 3)} calibrated quantiles; past_rain: observed hourly rain
    (>= 168 h, oldest first); rain24: (2, 3) quantiles of 24 h accumulation for hours 1-24 / 25-48."""
    H = len(times)
    t, rh, rain, wind = fc['temp'], fc['rh'], fc['rain'], fc['wind']
    hazards: List[dict] = []

    # heat
    hi50 = heat_index_c(t[:, 1], rh[:, 1])
    lvl = np.where((hi50 >= cfg['heat_index_warning_c']) | (t[:, 1] >= cfg['temp_warning_c']), 2,
                   np.where((hi50 >= cfg['heat_index_watch_c']) | (t[:, 1] >= cfg['temp_watch_c'])
                            | (t[:, 2] >= cfg['temp_warning_c']), 1, 0))
    hazards += _episodes('heat', lvl, times, lambda i, j, l: (
        f'peak heat index {hi50[i:j + 1].max():.1f} °C, temperature p50 up to {t[i:j + 1, 1].max():.1f} °C '
        f'(thresholds: HI {cfg["heat_index_watch_c"]}/{cfg["heat_index_warning_c"]} °C, T {cfg["temp_watch_c"]}/{cfg["temp_warning_c"]} °C)'))

    # heavy rain: hourly rate and 24 h accumulation (IMD heavy / very heavy)
    thr = cfg['rain_hourly_mm']
    lvl = np.where(rain[:, 1] >= thr, 2, np.where(rain[:, 2] >= thr, 1, 0))
    acc = rain24 if rain24 is not None else np.stack([rain[s:s + 24].sum(axis=0) for s in (0, 24)])
    for k, s in enumerate((0, 24)):
        if s >= H or k >= len(acc):
            continue
        a50, a90 = acc[k, 1], acc[k, 2]
        l24 = 2 if (a50 >= cfg['rain_24h_heavy_mm'] or a90 >= cfg['rain_24h_very_heavy_mm']) else \
            1 if a90 >= cfg['rain_24h_heavy_mm'] else 0
        lvl[s:s + 24] = np.maximum(lvl[s:s + 24], l24)

    def rain_reason(i, j, l):
        k = 0 if i < 24 else 1
        return (f'hourly rain p50/p90 up to {rain[i:j + 1, 1].max():.1f}/{rain[i:j + 1, 2].max():.1f} mm/h '
                f'(heavy >= {thr} mm/h); 24 h accumulation p50/p90 {acc[min(k, len(acc) - 1), 1]:.0f}/'
                f'{acc[min(k, len(acc) - 1), 2]:.0f} mm (IMD heavy >= {cfg["rain_24h_heavy_mm"]} mm)')
    hazards += _episodes('heavy_rain', lvl, times, rain_reason)

    # high wind (10 m mean wind; gusts are not forecast)
    lvl = np.where(wind[:, 1] >= cfg['wind_warning_ms'], 2,
                   np.where((wind[:, 1] >= cfg['wind_watch_ms']) | (wind[:, 2] >= cfg['wind_warning_ms']), 1, 0))
    hazards += _episodes('high_wind', lvl, times, lambda i, j, l: (
        f'10 m wind p50/p90 up to {wind[i:j + 1, 1].max():.1f}/{wind[i:j + 1, 2].max():.1f} m/s '
        f'(watch {cfg["wind_watch_ms"]}, warning {cfg["wind_warning_ms"]} m/s)'))

    # flood risk index from antecedent + forecast rain
    if api_thresholds:
        past = np.nan_to_num(np.asarray(past_rain, dtype=float)[-168:])
        api50 = antecedent_precip_index(np.concatenate([past, rain[:, 1]]), cfg['api_decay_per_day'])[-H:]
        api90 = antecedent_precip_index(np.concatenate([past, rain[:, 2]]), cfg['api_decay_per_day'])[-H:]
        w, wa = api_thresholds['warning'], api_thresholds['watch']
        lvl = np.where(api50 >= w, 2, np.where((api50 >= wa) | (api90 >= w), 1, 0))
        hazards += _episodes('flood_risk', lvl, times, lambda i, j, l: (
            f'antecedent precipitation index (7-day, decay {cfg["api_decay_per_day"]}/day) p50 up to '
            f'{api50[i:j + 1].max():.0f} mm vs climatological p{cfg["api_watch_percentile"]}={wa:.0f} / '
            f'p{cfg["api_warning_percentile"]}={w:.0f} mm - a soil-saturation risk index, not a river-flow forecast'))
    return hazards


def api_thresholds(rain: np.ndarray, cfg: dict) -> dict:
    api = antecedent_precip_index(rain, cfg['api_decay_per_day'])[168:]
    return {'watch': float(np.percentile(api, cfg['api_watch_percentile'])),
            'warning': float(np.percentile(api, cfg['api_warning_percentile']))}
