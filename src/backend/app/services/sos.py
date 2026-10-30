"""SOS lifecycle: idempotent intake, triage, state machine, assignment with capacity, notes.

Every mutation is one ACID transaction (request row + timeline event + team load + audit) and
uses optimistic locking: the client sends the `version` it saw; a stale version is a 409.
Realtime events are published only after the transaction commits.
"""

from __future__ import annotations

import base64
import math
import secrets
from datetime import timedelta
from typing import List, Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import iso, read_session, utcnow, write_tx
from ..deps import Principal
from ..errors import Conflict, Forbidden, NotFound
from ..models import Device, DeviceState, IdempotencyKey, SOSEvent, SOSRequest, Team
from ..realtime import HUB
from ..schemas import SOSIn, device_out, event_out, sos_out
from ..security import new_reference_id, sha256
from . import triage

TRANSITIONS = {
    'pending': {'triaged', 'assigned', 'cancelled'},
    'triaged': {'assigned', 'cancelled'},
    'assigned': {'en_route', 'triaged', 'cancelled'},       # -> triaged = unassign
    'en_route': {'on_scene', 'cancelled'},
    'on_scene': {'resolved', 'cancelled'},
    'resolved': set(),
    'cancelled': set(),
}
FINAL = {'resolved', 'cancelled'}
TEAM_BUSY = {'assigned', 'en_route', 'on_scene'}             # states that occupy a team slot


def _device_summary(s: Session, device_id: Optional[str]) -> Optional[dict]:
    if not device_id:
        return None
    d = s.scalar(select(Device).where(Device.device_id == device_id))
    if d is None:
        return None
    return {'alert_level': d.alert_level, 'ml_health_state': d.state, 'online': d.online}


DUPLICATE_RADIUS_M = 100
DUPLICATE_WINDOW = timedelta(hours=2)


def _duplicate_of(s: Session, data: dict) -> Optional[str]:
    """An open request from the same phone, or within ~100 m in the last 2 h, is probably the same
    emergency (people resend when they hear nothing). It is linked, not merged: a dispatcher decides.
    Candidates are narrowed in SQL (phone, or a lat/lng bounding box) so this stays cheap with
    thousands of open requests."""
    since = utcnow() - DUPLICATE_WINDOW
    near = [SOSRequest.phone == data.get('phone')]
    lat, lng = data.get('latitude'), data.get('longitude')
    if lat is not None and lng is not None:
        dlat = DUPLICATE_RADIUS_M / 111_320
        dlng = dlat / max(0.1, math.cos(math.radians(lat)))
        near.append(SOSRequest.latitude.between(lat - dlat, lat + dlat) & SOSRequest.longitude.between(lng - dlng, lng + dlng))
    rows = s.scalars(select(SOSRequest).where(SOSRequest.status.notin_(FINAL), SOSRequest.created_at >= since, or_(*near))
                     .order_by(SOSRequest.created_at).limit(50)).all()
    for r in rows:
        if r.phone == data.get('phone'):
            return r.reference_id
        if None not in (r.latitude, r.longitude, data.get('latitude'), data.get('longitude')):
            dy = (r.latitude - data['latitude']) * 111_320
            dx = (r.longitude - data['longitude']) * 111_320 * math.cos(math.radians(r.latitude))
            if math.hypot(dx, dy) <= DUPLICATE_RADIUS_M:
                return r.reference_id
    return None


def cached_response(source: str, key: str) -> Optional[dict]:
    with read_session() as s:
        hit = s.get(IdempotencyKey, idem_key(source, key))
        return hit.response if hit is not None else None


def idem_key(source: str, key: str) -> str:
    """Idempotency keys are namespaced by channel: a public client choosing `Idempotency-Key: sms:…`
    must never collide with (and so suppress or read) an SMS or wearable request."""
    return f'sos:{source}:{key}'


def create(body: SOSIn, idempotency_key: Optional[str], request_id: Optional[str], source: str = 'web',
           actor: str = 'public', device_verified: bool = False) -> dict:
    scope_key = idem_key(source, idempotency_key) if idempotency_key else None
    if scope_key:
        with read_session() as s:
            hit = s.get(IdempotencyKey, scope_key)
            if hit is not None:
                return hit.response
    token = secrets.token_urlsafe(18)
    data = body.model_dump()
    data['pincode'] = data.get('pincode') or ''           # column is NOT NULL; empty = not given
    try:
        with write_tx() as s:
            linked = body.device_id if device_verified else None
            priority, pts, reasons = triage.score({**data, 'source': source}, _device_summary(s, linked))
            dup = _duplicate_of(s, data)
            if dup:
                reasons = reasons + [f'possible duplicate of {dup}']
            for _ in range(5):                                         # reference ids are random; retry a clash
                ref = new_reference_id()
                if s.scalar(select(SOSRequest.id).where(SOSRequest.reference_id == ref)) is None:
                    break
            r = SOSRequest(reference_id=ref, tracking_hash=sha256(token), priority=priority, priority_score=pts,
                           priority_reasons=reasons, source=source, duplicate_of=dup,
                           device_verified=bool(body.device_id) and device_verified, **data)
            s.add(r)
            s.flush()
            s.add(SOSEvent(sos_id=r.id, kind='status', status='pending', actor=actor,
                           text=f'Request received via {source}, priority P{priority} ({pts}/100)'
                                + (f'; possible duplicate of {dup}' if dup else '')))
            audit(s, actor, 'sos.create', ref, {'priority': priority, 'source': source, 'duplicate_of': dup},
                  request_id)
            response = {'reference_id': ref, 'tracking_token': token, 'priority': priority, 'status': 'pending',
                        'duplicate_of': dup}
            if scope_key:
                s.add(IdempotencyKey(key=scope_key, scope='sos', response=response))
            out = sos_out(r)
    except IntegrityError:
        # a concurrent retry with the same Idempotency-Key committed first: return its response
        if scope_key:
            with read_session() as s:
                hit = s.get(IdempotencyKey, scope_key)
                if hit is not None:
                    return hit.response
        raise
    HUB.publish('sos', {'event': 'created', 'sos': out})
    return response


def track(ref: str, token: str) -> dict:
    with read_session() as s:
        r = s.scalar(select(SOSRequest).where(SOSRequest.reference_id == ref))
        # same error for unknown reference and wrong token: do not confirm that a reference exists
        if r is None or not token or sha256(token) != r.tracking_hash:
            raise NotFound('No request matches this reference and token')
        history = s.scalars(select(SOSEvent).where(SOSEvent.sos_id == r.id, SOSEvent.kind.in_(('status', 'assign')))
                            .order_by(SOSEvent.created_at)).all()
        return {'reference_id': r.reference_id, 'status': r.status, 'priority': r.priority,
                'created_at': sos_out(r)['created_at'], 'updated_at': sos_out(r)['updated_at'],
                'team_name': r.team.name if r.team and r.status in TEAM_BUSY | {'resolved'} else None,
                'eta_min': None,
                'history': [{'status': e.status or 'assigned', 'at': event_out(e)['at']} for e in history]}


MAX_OFFSET = 1_000_000


def link_device(ref: str, device_id: Optional[str], actor: str, request_id: Optional[str]) -> dict:
    """A dispatcher confirms (or clears) which wearable belongs to this request. Only a verified link
    feeds triage, alerts and automatic reallocation."""
    with write_tx() as s:
        r = _get(s, ref)
        if device_id and s.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
            raise NotFound(f'Device {device_id} not found')
        r.device_id, r.device_verified = device_id, bool(device_id)
        r.version += 1
        r.updated_at = utcnow()
        s.add(SOSEvent(sos_id=r.id, kind='note', actor=actor,
                       text=f'Wearable {device_id} linked (verified)' if device_id else 'Wearable link removed'))
        audit(s, actor, 'sos.link_device', ref, {'device_id': device_id}, request_id)
        s.flush()
        out = sos_out(r)
    HUB.publish('sos', {'event': 'updated', 'sos': out})
    return out


def _cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _offset(cursor: Optional[str]) -> int:
    if not cursor:
        return 0
    try:
        return min(MAX_OFFSET, max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode())))
    except Exception:
        return 0


def list_sos(status: Optional[List[str]], priority_max: Optional[int], etype: Optional[str], q: Optional[str],
             since=None, sort: str = 'priority', limit: int = 50, cursor: Optional[str] = None) -> dict:
    limit = max(1, min(200, limit))
    off = _offset(cursor)
    with read_session() as s:
        stmt = select(SOSRequest)
        if status:
            stmt = stmt.where(SOSRequest.status.in_(status))
        if priority_max:                                    # P1 is most urgent: 'at least P2' = priority <= 2
            stmt = stmt.where(SOSRequest.priority <= priority_max)
        if etype:
            stmt = stmt.where(SOSRequest.emergency_type == etype)
        if since is not None:
            stmt = stmt.where(SOSRequest.updated_at >= since)
        if q:
            like = f'%{q.strip()}%'
            stmt = stmt.where(or_(SOSRequest.reference_id.ilike(like), SOSRequest.name.ilike(like),
                                  SOSRequest.address.ilike(like), SOSRequest.city.ilike(like)))
        order = ((SOSRequest.priority_score.desc(), SOSRequest.created_at.asc()) if sort == 'priority'
                 else (SOSRequest.created_at.desc(),))
        rows = s.scalars(stmt.order_by(*order, SOSRequest.id.desc()).offset(off).limit(limit + 1)).all()
        items = [sos_out(r) for r in rows[:limit]]
        return {'items': items, 'next_cursor': _cursor(off + limit) if len(rows) > limit else None}


def _get(s: Session, ref: str) -> SOSRequest:
    r = s.scalar(select(SOSRequest).where(SOSRequest.reference_id == ref))
    if r is None:
        raise NotFound(f'SOS {ref} not found')
    return r


def detail(ref: str) -> dict:
    with read_session() as s:
        r = _get(s, ref)
        events = s.scalars(select(SOSEvent).where(SOSEvent.sos_id == r.id).order_by(SOSEvent.created_at)).all()
        teams = {t.id: t.name for t in s.scalars(select(Team)).all()}
        out = sos_out(r)
        out['history'] = [event_out(e) for e in events if e.kind in ('status', 'priority', 'assign')]
        out['notes'] = [event_out(e) for e in events if e.kind == 'note']
        out['assignments'] = [{**event_out(e), 'team_name': teams.get(e.team_id), 'assigned_by': e.actor,
                             'assigned_at': iso(e.created_at)} for e in events if e.kind == 'assign']
        dev = s.scalar(select(Device).where(Device.device_id == r.device_id)) if r.device_id else None
        out['linked_device'] = device_out(dev) if dev else None        # same shape as GET /devices
        return out


def _bump(s: Session, r: SOSRequest, expected_version: int) -> None:
    """Optimistic lock: the UPDATE only matches the version the client saw."""
    n = s.execute(update(SOSRequest).where(SOSRequest.id == r.id, SOSRequest.version == expected_version)
                  .values(version=expected_version + 1, updated_at=utcnow())).rowcount
    if n != 1:
        s.rollback()
        raise Conflict('This request was changed by someone else', {'current': detail(r.reference_id)})
    s.refresh(r)


def _release_team(s: Session, r: SOSRequest) -> None:
    if r.assigned_team_id and r.status in TEAM_BUSY:
        s.execute(update(Team).where(Team.id == r.assigned_team_id, Team.current_load > 0)
                  .values(current_load=Team.current_load - 1))


def change_status(ref: str, status: str, note: Optional[str], version: int, user: Principal,
                  request_id: Optional[str]) -> dict:
    with write_tx() as s:
        r = _get(s, ref)
        if user.role == 'responder' and (r.assigned_team_id is None or r.assigned_team_id != user.team_id):
            raise Forbidden('Responders can only update requests assigned to their team')
        if status == r.status:
            raise Conflict(f'Already {status}', {'current': sos_out(r)})
        if status not in TRANSITIONS[r.status]:
            raise Conflict(f'Cannot go from {r.status} to {status}',
                           {'allowed': sorted(TRANSITIONS[r.status]), 'current': sos_out(r)})
        if status == 'assigned':
            raise Conflict('Use the assign endpoint to assign a team')
        prev = r.status
        _bump(s, r, version)
        if status in FINAL or status == 'triaged':
            _release_team(s, r)
        if status == 'triaged' and prev == 'assigned':
            r.assigned_team_id = None
        r.status = status
        if status in FINAL:
            r.resolved_at = utcnow()
        s.add(SOSEvent(sos_id=r.id, kind='status', status=status, text=note, actor=user.username))
        audit(s, user.username, 'sos.status', ref, {'from': prev, 'to': status}, request_id)
        s.flush()
        s.refresh(r)
        out = sos_out(r)
    HUB.publish('sos', {'event': 'updated', 'sos': out})
    return out


def assign(ref: str, team_id: int, version: int, actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        r = _get(s, ref)
        if r.status in FINAL | {'en_route', 'on_scene'}:
            raise Conflict(f'Cannot assign a team while {r.status}', {'current': sos_out(r)})
        team = s.scalar(select(Team).where(Team.id == team_id).with_for_update())
        if team is None:
            raise NotFound(f'Team {team_id} not found')
        same = r.assigned_team_id == team_id and r.status == 'assigned'
        if not same and (not team.is_available or team.current_load >= team.capacity):
            raise Conflict(f'{team.name} has no free capacity',
                           {'capacity': team.capacity, 'current_load': team.current_load})
        _bump(s, r, version)
        if not same:
            _release_team(s, r)
            team.current_load += 1
        r.assigned_team_id, r.status = team_id, 'assigned'
        s.add(SOSEvent(sos_id=r.id, kind='assign', status='assigned', team_id=team_id, actor=actor,
                       text=f'Assigned to {team.name}'))
        audit(s, actor, 'sos.assign', ref, {'team_id': team_id}, request_id)
        s.flush()
        s.refresh(r)
        out = sos_out(r)
    HUB.publish('sos', {'event': 'assigned', 'sos': out})
    return out


def add_note(ref: str, text: str, actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        r = _get(s, ref)
        e = SOSEvent(sos_id=r.id, kind='note', text=text, actor=actor)
        s.add(e)
        audit(s, actor, 'sos.note', ref, {}, request_id)
        s.flush()
        note, out = event_out(e), sos_out(r)
    HUB.publish('sos', {'event': 'note', 'sos': out, 'note': note})
    return note


# ─── scheduled: re-triage and auto-assignment ──────────────────────────────

def _best_team(s: Session, r: SOSRequest) -> Optional[Team]:
    """Lowest relative load among available teams with capacity; AUTO_DEPLOY teams first for top priority."""
    teams = s.scalars(select(Team).where(Team.is_available.is_(True), Team.current_load < Team.capacity)).all()
    if not teams:
        return None

    def key(t: Team):
        auto_first = 0 if (r.priority == 1 and t.deployment_mode == 'AUTO_DEPLOY') else 1
        dist = 0.0
        if None not in (r.latitude, r.longitude, t.latitude, t.longitude):
            dist = ((r.latitude - t.latitude) ** 2 + (r.longitude - t.longitude) ** 2) ** 0.5
        return auto_first, round(t.current_load / max(t.capacity, 1), 2), dist
    return min(teams, key=key)


def _urgency_key(r: SOSRequest):
    return r.priority, -r.priority_score, r.created_at


def auto_triage(max_priority: int) -> int:
    """Re-score open requests (wearable state, waiting time), then hand free teams out in order of
    urgency - P1 before P2, higher score first, then first come. Requests that qualify for
    auto-dispatch but find no free team are flagged `awaiting_resources`. Returns #changes."""
    changed: List[dict] = []
    with write_tx() as s:
        open_rows = s.scalars(select(SOSRequest).where(SOSRequest.status.in_(('pending', 'triaged')))).all()
        ids = {r.device_id for r in open_rows if r.device_id and r.device_verified}
        devices = {d.device_id: {'alert_level': d.alert_level, 'ml_health_state': d.state, 'online': d.online}
                   for d in s.scalars(select(Device).where(Device.device_id.in_(ids))).all()} if ids else {}
        for r in open_rows:
            wait = (utcnow() - r.created_at).total_seconds() / 60
            priority, pts, reasons = triage.score(sos_out(r), devices.get(r.device_id) if r.device_verified else None,
                                                  wait)
            if r.duplicate_of:
                reasons = reasons + [f'possible duplicate of {r.duplicate_of}']
            if (priority, pts) != (r.priority, r.priority_score):
                if priority != r.priority:                 # log band changes, not every ageing tick
                    s.add(SOSEvent(sos_id=r.id, kind='priority', actor='triage',
                                   text=f'Priority P{priority} ({pts}/100): ' + ', '.join(reasons[:4])))
                    r.version += 1
                r.priority, r.priority_score, r.priority_reasons = priority, pts, reasons
                r.updated_at = utcnow()
        for r in sorted(open_rows, key=_urgency_key):
            awaiting = False
            if r.priority <= max_priority and not r.duplicate_of:
                team = _best_team(s, r)
                if team is not None:
                    team.current_load += 1
                    r.assigned_team_id, r.status = team.id, 'assigned'
                    r.version += 1
                    r.updated_at = utcnow()
                    s.add(SOSEvent(sos_id=r.id, kind='assign', status='assigned', team_id=team.id,
                                   actor='auto-dispatch', text=f'Auto-assigned to {team.name}'))
                    audit(s, 'auto-dispatch', 'sos.assign', r.reference_id, {'team_id': team.id})
                    s.flush()                               # the next request sees this team's new load
                else:
                    awaiting = True
                    moved = _auto_reallocate_if_extreme(s, r, changed)
                    if moved:
                        awaiting = False
            if r.awaiting_resources != awaiting:
                r.awaiting_resources = awaiting
                r.updated_at = utcnow()
            if r in s.dirty:
                s.flush()
                changed.append(sos_out(r))
        snapshot = _capacity(s, max_priority)
    for out in changed:
        HUB.publish('sos', {'event': 'updated', 'sos': out})
    _publish_capacity(snapshot)
    return len(changed)


# Extreme case (owner policy, 2026-10-31): normally moving a team between requests is only suggested
# and a dispatcher confirms. When EVERY signal says a life is at immediate risk and no team is free,
# the system moves one at once from a low-priority request that is not yet en route. All must hold:
EXTREME_MIN_SCORE = 80                  # triage: P1 with a score of at least this
EXTREME_MIN_RISK = 0.85                 # Tier-2 fusion: linked wearable critical at this risk ...
EXTREME_MIN_STATE_S = 60                # ... sustained this long (not a transient)
EXTREME_DONOR_MIN_PRIORITY = 4          # only take a team from a P4/P5 request
WATER_DISASTERS = ('flood', 'tsunami', 'dam-breach', 'water-level-rising')


def _extreme(s: Session, r: SOSRequest) -> Optional[List[str]]:
    """The evidence for an extreme case, or None. Triage, the wearable's ML + fusion state and the
    environment (forecast hazards, rivers, the emergency itself) must all agree."""
    if r.priority != 1 or r.priority_score < EXTREME_MIN_SCORE or not r.device_id or not r.device_verified:
        return None
    dev = s.scalar(select(Device).where(Device.device_id == r.device_id))
    risk = (dev.last_summary or {}).get('risk', 0.0) if dev else 0.0
    if dev is None or dev.alert_level != 'critical' or risk < EXTREME_MIN_RISK:
        return None
    since = s.scalar(select(func.max(DeviceState.created_at)).where(DeviceState.device_id == dev.device_id,
                                                                    DeviceState.state == dev.state))
    held = (utcnow() - since).total_seconds() if since else 0
    if held < EXTREME_MIN_STATE_S:
        return None
    env = []
    if r.emergency_type in WATER_DISASTERS:
        env.append(f'{r.emergency_type} emergency')
    from .weather import WEATHER
    env += [f"{h['type'].replace('_', ' ')} warning" for h in (WEATHER.forecast or {}).get('hazards', [])
            if h.get('level') == 'warning']
    from . import public_data
    env += [f"{rv['name']} river rising" for rv in public_data.rivers()['items'] if rv.get('trend') == 'rising']
    if not env:
        return None
    return [f'P1 {r.priority_score}/100', f'wearable {dev.state} risk {risk:.2f} for {int(held)} s'] + env[:3]


def _auto_reallocate_if_extreme(s: Session, r: SOSRequest, changed: List[dict]) -> bool:
    evidence = _extreme(s, r)
    if not evidence:
        return False
    donor = s.scalar(select(SOSRequest).where(SOSRequest.status == 'assigned',
                                              SOSRequest.assigned_team_id.isnot(None),
                                              SOSRequest.priority >= EXTREME_DONOR_MIN_PRIORITY)
                     .order_by(SOSRequest.priority.desc(), SOSRequest.priority_score.asc()))
    if donor is None:
        return False
    team = s.get(Team, donor.assigned_team_id)
    why = '; '.join(evidence)
    donor.assigned_team_id, donor.status, donor.version, donor.updated_at = None, 'triaged', donor.version + 1, utcnow()
    s.add(SOSEvent(sos_id=donor.id, kind='status', status='triaged', actor='auto-dispatch',
                   text=f'Auto-reallocated (extreme case): {team.name} moved to {r.reference_id}; back in the queue'))
    r.assigned_team_id, r.status, r.version, r.updated_at = team.id, 'assigned', r.version + 1, utcnow()
    s.add(SOSEvent(sos_id=r.id, kind='assign', status='assigned', team_id=team.id, actor='auto-dispatch',
                   text=f'Auto-reallocated (extreme case) from {donor.reference_id} to {team.name}: {why}'))
    audit(s, 'auto-dispatch', 'sos.reallocate_extreme', r.reference_id,
          {'team_id': team.id, 'from': donor.reference_id, 'evidence': evidence})
    s.flush()
    changed.append(sos_out(donor))
    return True


_last_capacity: dict = {}


def _capacity(s: Session, max_priority: int) -> dict:
    """Free teams, urgent requests left waiting, and (if any) which lower-priority assignments a
    dispatcher could move to them. Suggestions only: moving a team is always a human decision."""
    teams = s.scalars(select(Team)).all()
    free = [t for t in teams if t.is_available and t.current_load < t.capacity]
    waiting = sorted(s.scalars(select(SOSRequest).where(SOSRequest.status.in_(('pending', 'triaged')),
                                                        SOSRequest.priority <= max_priority,
                                                        SOSRequest.duplicate_of.is_(None))).all(), key=_urgency_key)
    donors = sorted(s.scalars(select(SOSRequest).where(SOSRequest.status == 'assigned',
                                                       SOSRequest.assigned_team_id.isnot(None))).all(),
                    key=lambda r: (-r.priority, -(r.updated_at.timestamp() if r.updated_at else 0)))
    team_names = {t.id: t.name for t in teams}
    used, suggestions = set(), []
    if not free:
        for w in waiting:
            donor = next((d for d in donors if d.id not in used and d.priority >= w.priority + 2), None)
            if donor is None:
                continue
            used.add(donor.id)
            suggestions.append({'for_reference_id': w.reference_id, 'team_id': donor.assigned_team_id,
                                'team_name': team_names.get(donor.assigned_team_id),
                                'from_reference_id': donor.reference_id, 'from_priority': donor.priority,
                                'reason': f'P{donor.priority} request not yet en route; P{w.priority} waiting'})
    status = 'exhausted' if not free and waiting else 'strained' if len(free) <= 1 else 'ok'
    return {'status': status, 'teams_free': len(free), 'teams_total': len(teams),
            'waiting': [{'reference_id': w.reference_id, 'priority': w.priority, 'emergency_type': w.emergency_type,
                         'waiting_min': int((utcnow() - w.created_at).total_seconds() // 60)} for w in waiting],
            'suggestions': suggestions, 'updated_at': iso(utcnow())}


def _publish_capacity(snapshot: dict) -> None:
    global _last_capacity
    key = {k: v for k, v in snapshot.items() if k != 'updated_at'}
    key['waiting'] = [{k: v for k, v in w.items() if k != 'waiting_min'} for w in key['waiting']]
    if key != _last_capacity:
        _last_capacity = key
        HUB.publish('system', {'event': 'capacity', **snapshot})


def capacity(max_priority: int) -> dict:
    with read_session() as s:
        return _capacity(s, max_priority)


def reallocate(ref: str, team_id: int, from_ref: str, version: int, from_version: int, actor: str,
               request_id: Optional[str]) -> dict:
    """Move a team from a lower-priority assignment (not yet en route) to this request, atomically:
    both requests and the team change in one transaction or not at all."""
    with write_tx() as s:
        r, donor = _get(s, ref), _get(s, from_ref)
        if donor.status != 'assigned' or donor.assigned_team_id != team_id:
            raise Conflict(f'{from_ref} no longer holds that team', {'current': sos_out(donor)})
        if r.status not in ('pending', 'triaged'):
            raise Conflict(f'{ref} is already {r.status}', {'current': sos_out(r)})
        if donor.priority <= r.priority:
            raise Conflict(f'{from_ref} is not lower priority than {ref}')
        team = s.scalar(select(Team).where(Team.id == team_id).with_for_update())
        _bump(s, donor, from_version)
        _bump(s, r, version)
        donor.assigned_team_id, donor.status = None, 'triaged'
        s.add(SOSEvent(sos_id=donor.id, kind='status', status='triaged', actor=actor,
                       text=f'{team.name} reassigned to more urgent {ref}; back in the queue'))
        r.assigned_team_id, r.status, r.awaiting_resources = team_id, 'assigned', False
        s.add(SOSEvent(sos_id=r.id, kind='assign', status='assigned', team_id=team_id, actor=actor,
                       text=f'Assigned to {team.name} (moved from {from_ref})'))
        audit(s, actor, 'sos.reallocate', ref, {'team_id': team_id, 'from': from_ref}, request_id)
        s.flush()
        out, out_donor = sos_out(r), sos_out(donor)
    HUB.publish('sos', {'event': 'assigned', 'sos': out})
    HUB.publish('sos', {'event': 'updated', 'sos': out_donor})
    return out


def counts() -> dict:
    with read_session() as s:
        rows = s.execute(select(SOSRequest.status, func.count()).group_by(SOSRequest.status)).all()
        return {k: v for k, v in rows}
