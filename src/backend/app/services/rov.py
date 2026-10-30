"""ROV fleet: semi-autonomous missions, exclusive manual control, serial-bridge outbox, live telemetry.

Modes. In `auto` the unit navigates itself to its target (deploy) or home (recall). A dispatcher
can take manual control (`takeover`); only that pilot can then drive it, until `release` hands
it back to auto. STOP is always accepted from any responder. If a manual pilot sends nothing for
DEADMAN_S, thrust is cut (the unit holds position) - a lost browser must not leave a ROV driving.

Real vs simulated. A unit with a serial bridge (src/rov/bridge.py) reports its own telemetry and
receives commands through the outbox, written to the ROV in the station's serial protocol
(`forward_75`, `up_0`, `on`/`off`). Without a bridge the unit is simulated: the 1 Hz tick moves it
(compressed time: SIM_SPEED_MPS is boat-like so a demo mission takes minutes, not hours) and
derives water temperature from the live air temperature. The UI always shows which it is.
"""

from __future__ import annotations

import math
import threading
import time
from datetime import timedelta
from typing import Dict, List, Optional

from sqlalchemy import delete, or_, select

from ..audit import audit
from ..db import iso, read_session, utcnow, write_tx
from ..errors import Conflict, Forbidden, NotFound
from ..models import ROVCommand, ROVSample, ROVUnit, SOSEvent, SOSRequest, Team
from ..realtime import HUB
from ..security import new_device_key, sha256

SIM_SPEED_MPS = 8.0                  # full thrust, simulated (compressed time)
TURN_DEG_PER_S = 20.0
DEPTH_RATE_MPS = 0.25
MISSION_DEPTH_M = 1.5
DEADMAN_S = 120
BRIDGE_OFFLINE_S = 10
ACTIVE = ('deploying', 'on_mission', 'returning', 'stopped')
MOVES = ('forward', 'backward', 'left', 'right', 'up', 'down')
M_PER_DEG = 111_320.0

_last_control: Dict[int, float] = {}
_lock = threading.Lock()


def serial_line(command: str, speed: int) -> List[str]:
    """Station protocol (src/rov/communication/serial_interface.py)."""
    if command in MOVES:
        return [f'{command}_{int(speed)}']
    if command == 'stop':
        return ['forward_0', 'up_0']
    return {'lights_on': ['on'], 'lights_off': ['off']}[command]


def rov_out(u: ROVUnit, ref: Optional[str] = None) -> dict:
    link = 'simulated' if u.simulated else (
        'online' if u.last_seen and utcnow() - u.last_seen < timedelta(seconds=BRIDGE_OFFLINE_S) else 'offline')
    return {'id': str(u.id), 'name': u.name, 'status': u.status, 'mode': u.mode, 'pilot': u.pilot,
            'battery_pct': round(u.battery_pct, 1), 'latitude': u.latitude, 'longitude': u.longitude,
            'depth_m': round(u.depth_m, 2), 'heading_deg': round(u.heading_deg % 360, 1),
            'water_temp_c': None if u.water_temp_c is None else round(u.water_temp_c, 1),
            'speed_pct': u.speed_pct, 'thrust': u.thrust, 'lights_on': u.lights_on, 'link': link,
            'last_seen': iso(u.last_seen), 'target': ({'lat': u.target_lat, 'lng': u.target_lng}
                                                      if u.target_lat is not None else None),
            'home': {'lat': u.home_lat, 'lng': u.home_lng}, 'mission_reference_id': ref, 'team_id': u.team_id,
            'video_url': u.video_url, 'simulated': u.simulated, 'mission_started_at': iso(u.mission_started_at),
            'vision': _vision(u.id),
            'updated_at': iso(u.updated_at)}


def _vision(unit_id: int) -> dict:
    from .vision import VISION
    return VISION.summary(unit_id)


def _ref(s, u: ROVUnit) -> Optional[str]:
    return s.get(SOSRequest, u.mission_sos_id).reference_id if u.mission_sos_id else None


def _unit(s, unit_id: int) -> ROVUnit:
    u = s.get(ROVUnit, unit_id)
    if u is None:
        raise NotFound('ROV not found')
    return u


def _publish(event: str, out: dict) -> None:
    HUB.publish('rov', {'event': event, 'rov': out})


def list_units() -> List[dict]:
    with read_session() as s:
        return [rov_out(u, _ref(s, u)) for u in s.scalars(select(ROVUnit).order_by(ROVUnit.name)).all()]


def track(unit_id: int, minutes: int = 30) -> List[dict]:
    with read_session() as s:
        rows = s.scalars(select(ROVSample).where(ROVSample.rov_id == unit_id,
                                                 ROVSample.created_at >= utcnow() - timedelta(minutes=minutes))
                         .order_by(ROVSample.id)).all()
        return [{'t': iso(r.created_at), 'lat': r.latitude, 'lng': r.longitude, 'depth_m': r.depth_m,
                 'heading_deg': r.heading_deg, 'battery_pct': r.battery_pct, 'water_temp_c': r.water_temp_c}
                for r in rows]


# ─── mission commands ──────────────────────────────────────────────────────

def deploy(unit_id: int, ref: str, actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        u = _unit(s, unit_id)
        if u.status not in ('idle', 'returning'):
            raise Conflict(f'{u.name} is {u.status}')
        if u.battery_pct < 30:
            raise Conflict(f'{u.name} battery too low ({u.battery_pct:.0f} %)')
        sos = s.scalar(select(SOSRequest).where(SOSRequest.reference_id == ref))
        if sos is None:
            raise NotFound(f'SOS {ref} not found')
        if sos.latitude is None or sos.longitude is None:
            raise Conflict('This request has no location to navigate to')
        u.status, u.mode, u.pilot, u.mission_sos_id = 'deploying', 'auto', None, sos.id
        u.target_lat, u.target_lng, u.mission_started_at, u.updated_at = sos.latitude, sos.longitude, utcnow(), utcnow()
        s.add(SOSEvent(sos_id=sos.id, kind='note', actor=actor, text=f'{u.name} deployed (autonomous transit)'))
        audit(s, actor, 'rov.deploy', u.name, {'sos': ref}, request_id)
        out = rov_out(u, ref)
    _publish('deployed', out)
    return out


def recall(unit_id: int, actor: str, request_id: Optional[str], stop: bool = False) -> dict:
    with write_tx() as s:
        u = _unit(s, unit_id)
        if stop:
            u.status, u.thrust, u.speed_pct = 'stopped', 'stop', 0
            if not u.simulated:
                _queue(s, u, 'stop', 0, actor)
        else:
            if u.status == 'idle':
                raise Conflict(f'{u.name} is already home')
            u.status, u.mode, u.pilot = 'returning', 'auto', None
            u.target_lat, u.target_lng, u.thrust = u.home_lat, u.home_lng, 'stop'
        u.updated_at = utcnow()
        audit(s, actor, 'rov.stop' if stop else 'rov.recall', u.name, {}, request_id)
        out = rov_out(u, _ref(s, u))
    _publish('stopped' if stop else 'recalled', out)
    return out


def reset(unit_id: int, actor: str, request_id: Optional[str]) -> dict:
    """Clear an emergency stop: back to auto, returning home."""
    with write_tx() as s:
        u = _unit(s, unit_id)
        if u.status != 'stopped':
            raise Conflict(f'{u.name} is not stopped')
        u.status, u.mode, u.pilot = 'returning', 'auto', None
        u.target_lat, u.target_lng, u.updated_at = u.home_lat, u.home_lng, utcnow()
        audit(s, actor, 'rov.reset', u.name, {}, request_id)
        out = rov_out(u, _ref(s, u))
    _publish('recalled', out)
    return out


# ─── manual control (exclusive) ────────────────────────────────────────────

def takeover(unit_id: int, user: str, is_admin: bool, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        u = _unit(s, unit_id)
        if u.mode == 'manual' and u.pilot not in (None, user) and not is_admin:
            raise Conflict(f'{u.pilot} is piloting {u.name}', {'pilot': u.pilot}, code='control_held')
        previous = u.pilot
        u.mode, u.pilot, u.thrust, u.speed_pct, u.updated_at = 'manual', user, 'stop', 0, utcnow()
        if not u.simulated:
            _queue(s, u, 'stop', 0, user)
        audit(s, user, 'rov.takeover', u.name, {'from': previous}, request_id)
        out = rov_out(u, _ref(s, u))
    _last_control[unit_id] = time.monotonic()
    _publish('mode', out)
    return out


def release(unit_id: int, user: str, is_admin: bool, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        u = _unit(s, unit_id)
        if u.mode != 'manual':
            raise Conflict(f'{u.name} is already autonomous')
        if u.pilot != user and not is_admin:
            raise Forbidden(f'Only {u.pilot} (or an admin) can release {u.name}')
        u.mode, u.pilot, u.thrust, u.speed_pct, u.updated_at = 'auto', None, 'stop', 0, utcnow()
        if not u.simulated:
            _queue(s, u, 'stop', 0, user)
        audit(s, user, 'rov.release', u.name, {}, request_id)
        out = rov_out(u, _ref(s, u))
    _publish('mode', out)
    return out


def _queue(s, u: ROVUnit, command: str, speed: int, actor: str) -> None:
    s.add(ROVCommand(rov_id=u.id, command=command, speed_pct=speed, created_by=actor))


def control(unit_id: int, command: str, speed: int, user: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        u = _unit(s, unit_id)
        if u.mode != 'manual':
            raise Conflict('Take manual control first', {'pilot': None, 'mode': u.mode}, code='not_piloting')
        if u.pilot != user:
            raise Conflict(f'{u.pilot} is piloting {u.name}', {'pilot': u.pilot, 'mode': u.mode}, code='control_held')
        if u.status == 'stopped' and command in MOVES:
            raise Conflict(f'{u.name} is emergency-stopped; reset it first')
        if command in MOVES:
            u.thrust, u.speed_pct = command, speed
        elif command == 'stop':
            u.thrust, u.speed_pct = 'stop', 0
        else:
            u.lights_on = command == 'lights_on'
        if not u.simulated:
            _queue(s, u, command, speed, user)
        if command not in MOVES:                     # moves are too frequent to audit; stops and lights are kept
            audit(s, user, f'rov.{command}', u.name, {}, request_id)
        u.updated_at = utcnow()
        out = rov_out(u, _ref(s, u))
    _last_control[unit_id] = time.monotonic()
    _publish('control', out)
    return out


# ─── serial bridge (real units) ────────────────────────────────────────────

def bridge_key(unit_id: int, video_url: Optional[str], actor: str, request_id: Optional[str]) -> dict:
    key, key_hash = new_device_key()
    with write_tx() as s:
        u = _unit(s, unit_id)
        u.key_hash, u.simulated, u.video_url = key_hash, False, video_url or u.video_url
        audit(s, actor, 'rov.bridge_key', u.name, {}, request_id)
    return {'rov_id': unit_id, 'api_key': key}


def bridge_ingest(key: str, body: dict) -> dict:
    """Telemetry from the station bridge; returns queued commands as serial lines."""
    with write_tx() as s:
        u = s.scalar(select(ROVUnit).where(ROVUnit.key_hash == sha256(key)))
        if u is None:
            from ..errors import Unauthorized
            raise Unauthorized('Unknown ROV bridge key')
        bounds = {'depth_m': (0, 1000), 'heading_deg': (0, 360), 'water_temp_c': (-5, 60), 'battery_pct': (0, 100),
                  'latitude': (-90, 90), 'longitude': (-180, 180)}
        for f, (lo, hi) in bounds.items():
            v = body.get(f)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi:
                setattr(u, f, float(v))
        u.last_seen = u.updated_at = utcnow()
        acks = [int(a) for a in (body.get('acks') or [])[:50] if str(a).isdigit() and len(str(a)) <= 15]
        if acks:
            for c in s.scalars(select(ROVCommand).where(ROVCommand.rov_id == u.id, ROVCommand.id.in_(acks))).all():
                c.status = 'acked'
        due = s.scalars(select(ROVCommand).where(ROVCommand.rov_id == u.id, ROVCommand.status == 'queued')
                        .order_by(ROVCommand.id)).all()
        for c in due:
            c.status, c.delivered_at = 'delivered', utcnow()
        s.add(_sample(u))
        out = rov_out(u, _ref(s, u))
        cmds = [{'id': c.id, 'lines': serial_line(c.command, c.speed_pct)} for c in due]
    _publish('telemetry', out)
    return {'commands': cmds, 'mode': out['mode'], 'status': out['status']}


def _sample(u: ROVUnit) -> ROVSample:
    return ROVSample(rov_id=u.id, latitude=u.latitude, longitude=u.longitude, depth_m=u.depth_m,
                     heading_deg=u.heading_deg % 360, battery_pct=u.battery_pct, water_temp_c=u.water_temp_c)


# ─── simulation tick (1 Hz) ────────────────────────────────────────────────

def _move(u: ROVUnit, metres: float) -> None:
    rad = math.radians(u.heading_deg)
    u.latitude += metres * math.cos(rad) / M_PER_DEG
    u.longitude += metres * math.sin(rad) / (M_PER_DEG * math.cos(math.radians(u.latitude)))


def _navigate(u: ROVUnit, dt: float, s=None) -> None:
    dy = (u.target_lat - u.latitude) * M_PER_DEG
    dx = (u.target_lng - u.longitude) * M_PER_DEG * math.cos(math.radians(u.latitude))
    dist = math.hypot(dx, dy)
    u.heading_deg = math.degrees(math.atan2(dx, dy)) % 360
    step = SIM_SPEED_MPS * 0.75 * dt
    u.thrust, u.speed_pct = 'forward', 75
    if dist <= step:
        u.latitude, u.longitude, u.thrust, u.speed_pct = u.target_lat, u.target_lng, 'stop', 0
        if u.status == 'deploying':
            u.status = 'on_mission'
            if s is not None and u.mission_sos_id:
                s.add(SOSEvent(sos_id=u.mission_sos_id, kind='note', actor=u.name, text=f'{u.name} arrived on scene'))
        else:
            u.status, u.target_lat, u.target_lng, u.mission_sos_id, u.mission_started_at = 'idle', None, None, None, None
    else:
        _move(u, step)
    u.depth_m += (0.4 - u.depth_m) * 0.3            # surface transit


def tick(dt: float = 1.0) -> int:
    from .weather import WEATHER
    air = (WEATHER.current or {}).get('temp_c')
    now_m = time.monotonic()
    outs = []
    with write_tx() as s:
        for u in s.scalars(select(ROVUnit)).all():
            if not u.simulated:
                if (u.mode == 'manual' and u.thrust != 'stop'
                        and now_m - _last_control.get(u.id, now_m) > DEADMAN_S):
                    u.thrust, u.speed_pct, u.updated_at = 'stop', 0, utcnow()
                    _queue(s, u, 'stop', 0, 'dead-man')
                    outs.append(rov_out(u, _ref(s, u)))
                continue
            before = rov_out(u)
            if u.mode == 'manual':
                if now_m - _last_control.get(u.id, now_m) > DEADMAN_S and u.thrust != 'stop':
                    u.thrust, u.speed_pct = 'stop', 0     # dead-man: pilot went quiet
                k = u.speed_pct / 100.0
                if u.status != 'stopped':
                    if u.thrust in ('forward', 'backward'):
                        _move(u, (1 if u.thrust == 'forward' else -1) * SIM_SPEED_MPS * k * dt)
                    elif u.thrust in ('left', 'right'):
                        u.heading_deg += (-1 if u.thrust == 'left' else 1) * TURN_DEG_PER_S * k * dt
                    elif u.thrust in ('up', 'down'):
                        u.depth_m = max(0.0, u.depth_m + (1 if u.thrust == 'down' else -1) * DEPTH_RATE_MPS * k * dt)
            elif u.status in ('deploying', 'returning') and u.target_lat is not None:
                _navigate(u, dt, s)
            elif u.status == 'on_mission':
                u.depth_m += (MISSION_DEPTH_M - u.depth_m) * 0.2 + 0.03 * math.sin(now_m / 7)   # station-keeping
                u.heading_deg += 0.5 * math.sin(now_m / 11)
                if u.battery_pct < 20:                  # protect the unit: come home on low battery
                    u.status, u.target_lat, u.target_lng = 'returning', u.home_lat, u.home_lng
            moving = u.thrust != 'stop' or u.status in ('deploying', 'returning', 'on_mission')
            if moving:
                u.battery_pct = max(0.0, u.battery_pct - (0.02 + 0.06 * u.speed_pct / 100) * dt)
            elif u.status == 'idle':
                u.battery_pct = min(100.0, u.battery_pct + 0.2 * dt)
                u.depth_m = 0.0
            if air is not None:
                # simulated water temperature: lags the measured air temperature, cooler with depth
                target = float(air) - 1.5 - 0.3 * u.depth_m
                u.water_temp_c = target if u.water_temp_c is None else u.water_temp_c + (target - u.water_temp_c) * 0.05
            after = rov_out(u)
            changed = {k: v for k, v in after.items() if k not in ('updated_at', 'last_seen')} != \
                      {k: v for k, v in before.items() if k not in ('updated_at', 'last_seen')}
            if changed:
                u.updated_at = utcnow()
            if u.status in ACTIVE or u.mode == 'manual':
                s.add(_sample(u))
            if changed or u.status in ACTIVE:
                outs.append(rov_out(u, _ref(s, u)))
    for out in outs:
        _publish('telemetry', out)
    return len(outs)


def prune_samples(keep_hours: int = 48) -> int:
    with write_tx() as s:
        return s.execute(delete(ROVSample).where(ROVSample.created_at < utcnow() - timedelta(hours=keep_hours))).rowcount or 0


# ─── missions view ─────────────────────────────────────────────────────────

def missions() -> List[dict]:
    """Every ROV on a mission (or piloted), its SOS, its team, and the live wearables of its victims."""
    from ..schemas import device_out, sos_out
    from ..models import Device
    out = []
    with read_session() as s:
        units = s.scalars(select(ROVUnit).where((ROVUnit.status.in_(ACTIVE)) | (ROVUnit.mode == 'manual'))
                          .order_by(ROVUnit.name)).all()
        for u in units:
            sos = s.get(SOSRequest, u.mission_sos_id) if u.mission_sos_id else None
            team = s.get(Team, u.team_id) if u.team_id else None
            # the mission's own SOS plus every open request assigned to the ROV's team
            conds = ([SOSRequest.id == u.mission_sos_id] if u.mission_sos_id else []) + \
                    ([SOSRequest.assigned_team_id == u.team_id] if u.team_id else [])
            rows = s.scalars(select(SOSRequest).where(SOSRequest.status.notin_(('resolved', 'cancelled')),
                                                      or_(*conds))).all() if conds else []
            victims = []
            for r in sorted(rows, key=lambda r: -r.priority_score):
                dev = s.scalar(select(Device).where(Device.device_id == r.device_id)) if r.device_id else None
                victims.append({'reference_id': r.reference_id, 'name': r.name, 'status': r.status,
                                'priority': r.priority, 'device_id': r.device_id,
                                'latitude': r.latitude, 'longitude': r.longitude,
                                'device': device_out(dev) if dev else None})
            out.append({'rov': rov_out(u, sos.reference_id if sos else None), 'sos': sos_out(sos) if sos else None,
                        'team': {'id': team.id, 'name': team.name} if team else None, 'victims': victims})
    return out
