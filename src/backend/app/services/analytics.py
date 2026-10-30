"""Operational analytics, computed from the live database and cached public data - never hardcoded.

Portable SQL (SQLite and PostgreSQL); time bucketing is done in Python over bounded windows.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Optional

import numpy as np
from sqlalchemy import func, select

from ..config import PROJECT_ROOT
from ..db import iso, read_session, utcnow
from ..models import Alert, Device, DeviceState, ROVUnit, SOSEvent, SOSRequest, Team, TelemetryFrame
from . import public_data

OPEN = ('pending', 'triaged', 'assigned', 'en_route', 'on_scene')
SIGNALS = {'ppg': 'ppg_bpm', 'eda': 'eda_us', 'temp': 'temp_skin_c', 'imu': 'imu_acc_std_g', 'gps': 'gps_lat',
           'spo2': 'ppg_spo2'}


def summary() -> dict:
    with read_session() as s:
        sos_open = s.scalar(select(func.count()).where(SOSRequest.status.in_(OPEN)))
        sos_critical = s.scalar(select(func.count()).where(SOSRequest.status.in_(OPEN), SOSRequest.priority <= 2))
        teams_total = s.scalar(select(func.count()).select_from(Team))
        teams_free = s.scalar(select(func.count()).where(Team.is_available.is_(True), Team.current_load < Team.capacity))
        devices_online = s.scalar(select(func.count()).where(Device.online.is_(True)))
        devices_total = s.scalar(select(func.count()).select_from(Device))
        alerts_open = s.scalar(select(func.count()).where(Alert.status == 'open'))
        resolved_24h = s.scalar(select(func.count()).where(SOSRequest.resolved_at >= utcnow() - timedelta(hours=24),
                                                           SOSRequest.status == 'resolved'))
        rovs_active = s.scalar(select(func.count()).where(ROVUnit.status.in_(('deploying', 'on_mission', 'returning'))))
    rt = response_times()
    return {'sos_open': sos_open, 'sos_critical': sos_critical, 'sos_resolved_24h': resolved_24h,
            'avg_response_min': rt['overall']['mean_min'], 'teams_available': teams_free, 'teams_total': teams_total,
            'devices_online': devices_online, 'devices_total': devices_total, 'alerts_open': alerts_open,
            'rovs_active': rovs_active, 'updated_at': iso(utcnow())}


STEPS = {'minute': timedelta(minutes=1), 'hour': timedelta(hours=1), 'day': timedelta(days=1)}
DEFAULT_SPAN = {'minute': timedelta(hours=2), 'hour': timedelta(days=2), 'day': timedelta(days=30)}


MAX_SPAN = {'minute': timedelta(days=1), 'hour': timedelta(days=31), 'day': timedelta(days=730)}


def timeseries(metric: str, bucket: str, since=None) -> dict:
    # bounded: one bucket per step since `since` must never be allowed to grow without limit
    since = max(since or utcnow() - DEFAULT_SPAN[bucket], utcnow() - MAX_SPAN[bucket])
    col = {'sos_created': SOSRequest.created_at, 'sos_resolved': SOSRequest.resolved_at, 'alerts': Alert.opened_at,
           'telemetry_frames': TelemetryFrame.received_at, 'state_changes': DeviceState.created_at}[metric]
    with read_session() as s:
        stmt = select(col).where(col >= since)
        if metric == 'sos_resolved':
            stmt = stmt.where(SOSRequest.status == 'resolved')
        times = [t for (t,) in s.execute(stmt).all() if t is not None]
    step = STEPS[bucket]
    start = since.replace(second=0, microsecond=0)
    if bucket in ('hour', 'day'):
        start = start.replace(minute=0)
    if bucket == 'day':
        start = start.replace(hour=0)
    n = int((utcnow() - start) / step) + 1
    counts = [0] * n
    for t in times:
        i = int((t - start) / step)
        if 0 <= i < n:
            counts[i] += 1
    return {'metric': metric, 'bucket': bucket,
            'points': [{'t': iso(start + i * step), 'value': c} for i, c in enumerate(counts)]}


def breakdown(by: str) -> dict:
    col = {'type': SOSRequest.emergency_type, 'status': SOSRequest.status, 'priority': SOSRequest.priority}[by]
    with read_session() as s:
        rows = s.execute(select(col, func.count()).group_by(col).order_by(func.count().desc())).all()
    return {'by': by, 'items': [{'key': str(k), 'count': c} for k, c in rows]}


def _pcts(values, unit: str = 'min') -> dict:
    if not values:
        return {'n': 0, f'mean_{unit}': None, f'p50_{unit}': None, f'p90_{unit}': None}
    a = np.asarray(values)
    return {'n': len(a), f'mean_{unit}': round(float(a.mean()), 1), f'p50_{unit}': round(float(np.percentile(a, 50)), 1),
            f'p90_{unit}': round(float(np.percentile(a, 90)), 1)}


def response_times(days: Optional[int] = 30) -> dict:
    """Minutes from request to first team assignment, per priority."""
    with read_session() as s:
        first_assign = (select(SOSEvent.sos_id, func.min(SOSEvent.created_at).label('t'))
                        .where(SOSEvent.kind == 'assign').group_by(SOSEvent.sos_id).subquery())
        rows = s.execute(select(SOSRequest.priority, SOSRequest.created_at, first_assign.c.t)
                         .join(first_assign, first_assign.c.sos_id == SOSRequest.id)
                         .where(SOSRequest.created_at >= utcnow() - timedelta(days=days or 3650))).all()
    by_p, all_m = defaultdict(list), []
    for p, created, t in rows:
        m = max(0.0, (t - created).total_seconds() / 60)
        by_p[p].append(m)
        all_m.append(m)
    items = [{'priority': p, 'n': len(v), 'p50': round(float(np.percentile(v, 50)), 1),
              'p90': round(float(np.percentile(v, 90)), 1), 'p95': round(float(np.percentile(v, 95)), 1)}
             for p, v in sorted(by_p.items())]
    return {'overall': _pcts(all_m), 'by_priority': {str(p): _pcts(v) for p, v in sorted(by_p.items())},
            'items': items, 'unit': 'min'}


def sensors() -> dict:
    """Per-device live health from the last 10 minutes of frames and 24 h of fusion states."""
    now = utcnow()
    out = []
    with read_session() as s:
        devices = s.scalars(select(Device).order_by(Device.device_id)).all()
        for d in devices:
            frames = s.execute(select(TelemetryFrame.received_at, TelemetryFrame.values, TelemetryFrame.state)
                               .where(TelemetryFrame.device_id == d.device_id,
                                      TelemetryFrame.received_at >= now - timedelta(minutes=10))).all()
            recent = [f for f in frames if f[0] >= now - timedelta(minutes=5)]
            avail = {k: (round(sum(f[1].get(col) is not None for f in frames) / len(frames), 3) if frames else None)
                     for k, col in SIGNALS.items()}
            states = Counter(st for (st,) in s.execute(
                select(TelemetryFrame.state).where(TelemetryFrame.device_id == d.device_id,
                                                   TelemetryFrame.received_at >= now - timedelta(hours=24))).all())
            total = sum(states.values())
            out.append({'device_id': d.device_id, 'label': d.label, 'online': d.online, 'last_seen': iso(d.last_seen),
                        'frames_5min': len(recent), 'frame_rate_hz': round(len(recent) / 300, 3),
                        'battery_v': (d.last_summary or {}).get('battery_v'), 'signal_availability': avail,
                        'state_share_24h': {k: round(v / total, 4) for k, v in states.items()} if total else {},
                        'sensor_fault': (d.last_summary or {}).get('sensor_fault'), 'state': d.state,
                        'alert_level': d.alert_level})
        per_min = s.scalar(select(func.count()).where(TelemetryFrame.received_at >= now - timedelta(minutes=1)))
    return {'devices': out, 'totals': {'frames_per_min': per_min, 'devices_online': sum(x['online'] for x in out),
                                       'devices_total': len(out)}, 'updated_at': iso(now)}


def performance() -> dict:
    with read_session() as s:
        acks = s.execute(select(Alert.opened_at, Alert.acked_at).where(Alert.acked_at.isnot(None))).all()
        teams = s.scalars(select(Team).order_by(Team.name)).all()
        util = [{'team_id': t.id, 'name': t.name, 'load': t.current_load, 'capacity': t.capacity,
                 'utilization': round(t.current_load / t.capacity, 3) if t.capacity else None,
                 'available': t.is_available} for t in teams]
        # ROV transit: '<unit> deployed' -> '<unit> arrived on scene' on the same request's timeline
        notes = s.execute(select(SOSEvent.sos_id, SOSEvent.created_at, SOSEvent.text).where(
            SOSEvent.kind == 'note', SOSEvent.text.like('ROV-%')).order_by(SOSEvent.created_at)).all()
    started, transit = {}, []
    for sos_id, t, text in notes:
        unit = text.split(' ', 1)[0]
        if 'deployed' in text:
            started[(sos_id, unit)] = t
        elif 'arrived' in text and (sos_id, unit) in started:
            transit.append((t - started.pop((sos_id, unit))).total_seconds() / 60)
    ack_s = [(a - o).total_seconds() for o, a in acks]
    return {'response_times': response_times(), 'alert_ack': _pcts(ack_s, 's'), 'team_utilization': util,
            'missions': {'n': len(transit) + len(started), 'completed_transits': len(transit),
                         'median_transit_min': round(float(np.median(transit)), 1) if transit else None},
            'updated_at': iso(utcnow())}


def _grid(points, cell=0.01):
    """Count of requests per ~1 km cell, for the density layer."""
    g = Counter((round(lat / cell) * cell, round(lng / cell) * cell) for lat, lng in points)
    return [{'lat': round(a, 4), 'lng': round(b, 4), 'count': c} for (a, b), c in g.items()]


def geo() -> dict:
    from .rov import rov_out
    from ..schemas import team_out
    with read_session() as s:
        sos = s.scalars(select(SOSRequest).where(SOSRequest.latitude.isnot(None),
                                                 SOSRequest.created_at >= utcnow() - timedelta(days=7))).all()
        devices = s.scalars(select(Device)).all()
        teams = s.scalars(select(Team)).all()
        rovs = s.scalars(select(ROVUnit)).all()
        sos_items = [{'reference_id': r.reference_id, 'lat': r.latitude, 'lng': r.longitude, 'priority': r.priority,
                      'status': r.status, 'emergency_type': r.emergency_type} for r in sos]
        dev_items = [{'device_id': d.device_id, 'lat': (d.last_summary or {}).get('lat'),
                      'lng': (d.last_summary or {}).get('lng'), 'state': d.state, 'alert_level': d.alert_level,
                      'online': d.online} for d in devices if (d.last_summary or {}).get('lat') is not None]
        out = {'sos': sos_items, 'devices': dev_items,
               'teams': [{**team_out(t), 'lat': t.latitude, 'lng': t.longitude} for t in teams if t.latitude is not None],
               'rovs': [{**rov_out(u), 'lat': u.latitude, 'lng': u.longitude} for u in rovs]}
    rv = public_data.rivers()
    out.update(rivers=rv['items'], rivers_source=rv['source'], rivers_fetched_at=rv['fetched_at'],
               grid=_grid([(x['lat'], x['lng']) for x in sos_items]), updated_at=iso(utcnow()))
    return out


def _json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def models() -> dict:
    """Model cards as measured: Tier-1 metrics from the P4 registry, fusion replay (P5), external tests."""
    reg = _json(PROJECT_ROOT / 'models' / 'wearable' / 'registry.json') or {'heads': {}}
    heads = []
    for name, e in reg['heads'].items():
        m = (_json(PROJECT_ROOT / 'models' / 'wearable' / e['path'] / 'metrics.json') or {}).get('metrics', {})
        o = m.get('oof_calibrated', {})
        ext = m.get('external')
        heads.append({'head': name, 'model': e['tournament']['winner'], 'macro_f1': o.get('macro_f1'),
                      'ci95': o.get('macro_f1_ci95'), 'auroc': o.get('auroc'), 'threshold': e.get('threshold'),
                      'training': e.get('training'), 'per_dataset': {k: v.get('macro_f1') for k, v in
                                                                      m.get('per_dataset', {}).items()},
                      'external': {'datasets': ext['datasets'], 'macro_f1': ext.get('macro_f1')} if ext else None})
    replay = _json(PROJECT_ROOT / 'data' / 'processed' / 'wearable' / 'replay' / 'p5_replay.json') or {}
    fusion = {'version': (replay.get('fusion') or {}).get('version'),
              'false_alarms_per_8h': {k: v.get('critical_alarms_per_8h') for k, v in replay.get('daily_life', {}).items()},
              'falls': replay.get('falls')}
    af = _json(PROJECT_ROOT / 'data' / 'processed' / 'wearable' / 'external' / 'mimic_perform_af.json')
    from .weather import WEATHER
    card = WEATHER.card if WEATHER.card else None
    return {'wearable': heads, 'fusion': fusion, 'rhythm_ppg_af': af, 'weather': card, 'updated_at': iso(utcnow())}
