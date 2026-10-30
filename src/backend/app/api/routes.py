"""REST API v1 (docs/PLATFORM_DESIGN.md, section 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response
from sqlalchemy import select

from ..config import get_settings
from ..db import read_session
from ..deps import Principal, current_device, current_user, require
from ..errors import AppError, NotFound
from ..models import AuditLog, Device, EmergencyContact, Team
from ..ratelimit import TokenBucket, limit
from ..schemas import (AssignIn, CommandIn, DeployIn, DeviceIn, LoginIn, NoteIn, RefreshIn, ResolveIn, SOSIn,
                       StatusIn, TeamPatch, UserIn, UserPatch, ROVControlIn, BridgeKeyIn, ReallocateIn, SmsIn, team_out)
from ..services import alerts, analytics, auth, public_data, rov, sms, sos, telemetry
from ..services.weather import WEATHER

router = APIRouter(prefix='/api/v1')
_cfg = get_settings()
SOS_BUCKET = TokenBucket(_cfg.sos_rate_per_min, burst=max(_cfg.sos_burst, min(_cfg.sos_rate_per_min, 1000)))
TRACK_BUCKET = TokenBucket(60)
SMS_BUCKET = TokenBucket(120, burst=30)            # a gateway relays many senders from one address
LOGIN_BUCKET = TokenBucket(_cfg.login_rate_per_min, burst=max(5, min(_cfg.login_rate_per_min, 1000)))


def _rid(request: Request) -> Optional[str]:
    return getattr(request.state, 'request_id', None)


def _since(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise AppError('`since` must be an ISO-8601 timestamp', status=422, code='validation_error')
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


# ─── auth ──────────────────────────────────────────────────────────────────

@router.post('/auth/login', tags=['auth'])
def login(body: LoginIn, request: Request):
    limit(LOGIN_BUCKET, request, 'login')
    return auth.login(body.username, body.password, _rid(request))


@router.post('/auth/refresh', tags=['auth'])
def refresh(body: RefreshIn, request: Request):
    limit(LOGIN_BUCKET, request, 'refresh')
    return auth.refresh(body.refresh_token, _rid(request))


@router.post('/auth/logout', status_code=204, tags=['auth'])
def logout(body: RefreshIn):
    auth.logout(body.refresh_token)
    return Response(status_code=204)


@router.get('/auth/me', tags=['auth'])
def me(user: Principal = Depends(current_user)):
    return auth.me(user.id)


@router.get('/users', tags=['users'])
def users(_: Principal = Depends(require('admin'))):
    return {'items': auth.list_users(), 'next_cursor': None}


@router.post('/users', status_code=201, tags=['users'])
def create_user(body: UserIn, request: Request, user: Principal = Depends(require('admin'))):
    return auth.create_user(body.model_dump(), user.username, _rid(request))


@router.patch('/users/{user_id}', tags=['users'])
def update_user(user_id: int, body: UserPatch, request: Request, user: Principal = Depends(require('admin'))):
    return auth.update_user(user_id, body.model_dump(exclude_unset=True), user.username, _rid(request))


# ─── public ────────────────────────────────────────────────────────────────

@router.post('/sos', status_code=201, tags=['sos'])
def submit_sos(body: SOSIn, request: Request,
               idempotency_key: Optional[str] = Header(default=None, max_length=80)):
    # a retry of a request we already accepted (e.g. a phone resending after an outage) always gets its
    # original answer back, rate limit or not
    cached = sos.cached_response('web', idempotency_key) if idempotency_key else None
    if cached is not None:
        return cached
    limit(SOS_BUCKET, request, 'sos')
    return sos.create(body, idempotency_key, _rid(request))


@router.get('/sos/track/{ref}', tags=['sos'])
def track_sos(ref: str, request: Request, token: str = Query(..., min_length=10, max_length=64)):
    limit(TRACK_BUCKET, request, 'track')
    return sos.track(ref.upper(), token)


@router.get('/public/summary', tags=['public'])
def public_summary():
    s = analytics.summary()
    w = WEATHER.current if WEATHER.current else None
    hz = (WEATHER.summary() or {}).get('hazards', [])
    return {'sms_number': _cfg.sms_number or None,
            'teams_available': s['teams_available'], 'teams_total': s['teams_total'], 'sos_open': s['sos_open'],
            'sos_resolved_24h': s['sos_resolved_24h'], 'devices_online': s['devices_online'],
            'weather': {'temp_c': w.get('temp_c') if w else None, 'hazards': hz}, 'updated_at': s['updated_at']}


@router.get('/contacts', tags=['public'])
def contacts():
    with read_session() as s:
        return [{'name': c.name, 'phone': c.phone, 'department': c.department}
                for c in s.scalars(select(EmergencyContact)).all()]


# ─── SOS (staff) ───────────────────────────────────────────────────────────

@router.get('/sos', tags=['sos'])
def list_sos(status: Optional[List[str]] = Query(default=None), priority_max: Optional[int] = Query(None, ge=1, le=5),
             type: Optional[str] = None, q: Optional[str] = Query(None, max_length=100), since: Optional[str] = None,
             sort: str = Query('priority', pattern='^(priority|recent)$'), limit_: int = Query(50, alias='limit'),
             cursor: Optional[str] = None, _: Principal = Depends(current_user)):
    return sos.list_sos(status, priority_max, type, q, _since(since), sort, limit_, cursor)


@router.get('/sos/{ref}', tags=['sos'])
def get_sos(ref: str, _: Principal = Depends(current_user)):
    return sos.detail(ref.upper())


@router.patch('/sos/{ref}/status', tags=['sos'])
def sos_status(ref: str, body: StatusIn, request: Request, user: Principal = Depends(require('responder'))):
    return sos.change_status(ref.upper(), body.status, body.note, body.version, user, _rid(request))


@router.post('/sos/{ref}/assign', tags=['sos'])
def sos_assign(ref: str, body: AssignIn, request: Request, user: Principal = Depends(require('dispatcher'))):
    return sos.assign(ref.upper(), body.team_id, body.version, user.username, _rid(request))


@router.post('/sos/{ref}/reallocate', tags=['sos'])
def sos_reallocate(ref: str, body: ReallocateIn, request: Request, user: Principal = Depends(require('dispatcher'))):
    return sos.reallocate(ref.upper(), body.team_id, body.from_reference_id.upper(), body.version, body.from_version,
                          user.username, _rid(request))


@router.post('/sos/{ref}/link-device', tags=['sos'])
def sos_link_device(ref: str, request: Request, body: dict = Body(...), user: Principal = Depends(require('dispatcher'))):
    device_id = body.get('device_id')
    if device_id is not None and (not isinstance(device_id, str) or not 3 <= len(device_id) <= 64):
        raise AppError('device_id must be a string (3-64 chars) or null', status=422, code='validation_error')
    return sos.link_device(ref.upper(), device_id, user.username, _rid(request))


@router.get('/dispatch/capacity', tags=['sos'])
def dispatch_capacity(_: Principal = Depends(current_user)):
    return sos.capacity(_cfg.auto_assign_max_priority)


@router.post('/sms/inbound', tags=['sos'])
def sms_inbound(body: SmsIn, request: Request, x_sms_secret: Optional[str] = Header(default=None, max_length=128)):
    """SMS gateway webhook (provider or GSM modem bridge). Off unless TRIDENT_SMS_SECRET is set."""
    import hmac
    from ..errors import Unauthorized, Unavailable
    if not _cfg.sms_secret:
        raise Unavailable('SMS intake is not configured')
    limit(SMS_BUCKET, request, 'sms')                       # before the secret check: no free guessing
    if not x_sms_secret or not hmac.compare_digest(x_sms_secret.encode('utf-8', 'replace'),
                                                   _cfg.sms_secret.encode('utf-8')):
        raise Unauthorized('Bad SMS gateway secret')
    return sms.ingest(body.sender, body.text, body.id, _rid(request))


@router.post('/sms/test', tags=['sos'])
def sms_test(body: SmsIn, request: Request, user: Principal = Depends(require('admin'))):
    """Admin-only: run a message through the SMS intake without a gateway (development and drills)."""
    return sms.ingest(body.sender, body.text, body.id, _rid(request))


@router.post('/sos/{ref}/notes', status_code=201, tags=['sos'])
def sos_note(ref: str, body: NoteIn, request: Request, user: Principal = Depends(require('responder'))):
    return sos.add_note(ref.upper(), body.text, user.username, _rid(request))


# ─── teams ─────────────────────────────────────────────────────────────────

@router.get('/teams', tags=['teams'])
def teams(_: Principal = Depends(current_user)):
    with read_session() as s:
        return [team_out(t) for t in s.scalars(select(Team).order_by(Team.name)).all()]


@router.patch('/teams/{team_id}', tags=['teams'])
def patch_team(team_id: int, body: TeamPatch, request: Request, user: Principal = Depends(require('dispatcher'))):
    from ..audit import audit
    from ..db import write_tx
    from ..realtime import HUB
    with write_tx() as s:
        t = s.get(Team, team_id)
        if t is None:
            raise NotFound('Team not found')
        changes = body.model_dump(exclude_unset=True)
        for k, v in changes.items():
            setattr(t, k, v)
        t.version += 1
        audit(s, user.username, 'team.update', t.name, changes, _rid(request))
        out = team_out(t)
    HUB.publish('sos', {'event': 'team', 'team': out})
    return out


# ─── devices & telemetry ───────────────────────────────────────────────────

@router.post('/telemetry', tags=['telemetry'])
def ingest(body: dict = Body(...), device: Device = Depends(current_device)):
    return telemetry.ingest(device, body)


@router.get('/devices', tags=['devices'])
def devices(_: Principal = Depends(current_user)):
    return telemetry.list_devices()


@router.post('/devices', status_code=201, tags=['devices'])
def register_device(body: DeviceIn, request: Request, user: Principal = Depends(require('admin'))):
    return telemetry.register(body.device_id, body.label, user.username, _rid(request))


@router.post('/devices/{device_id}/rotate-key', tags=['devices'])
def rotate_key(device_id: str, request: Request, user: Principal = Depends(require('admin'))):
    return telemetry.rotate_key(device_id, user.username, _rid(request))


@router.post('/devices/{device_id}/commands', status_code=201, tags=['devices'])
def device_command(device_id: str, body: CommandIn, request: Request, user: Principal = Depends(require('dispatcher'))):
    return telemetry.queue_command(device_id, body.action, body.params, user.username, _rid(request))


@router.get('/devices/{device_id}/commands', tags=['devices'])
def device_commands(device_id: str, _: Principal = Depends(current_user)):
    return telemetry.commands_for(device_id)


@router.get('/devices/{device_id}/frames', tags=['devices'])
def device_frames(device_id: str, since: Optional[str] = None, limit_: int = Query(400, alias='limit'),
                  _: Principal = Depends(current_user)):
    return telemetry.frames(device_id, _since(since), limit_)


@router.get('/devices/{device_id}/states', tags=['devices'])
def device_states(device_id: str, since: Optional[str] = None, _: Principal = Depends(current_user)):
    return telemetry.states(device_id, _since(since))


# ─── alerts ────────────────────────────────────────────────────────────────

@router.get('/alerts', tags=['alerts'])
def list_alerts(status: Optional[str] = Query(None, pattern='^(open|acked|resolved)$'),
                _: Principal = Depends(current_user)):
    return alerts.list_alerts(status)


@router.post('/alerts/{alert_id}/ack', tags=['alerts'])
def ack_alert(alert_id: int, request: Request, user: Principal = Depends(require('responder'))):
    return alerts.ack(alert_id, user.username, _rid(request))


@router.post('/alerts/{alert_id}/resolve', tags=['alerts'])
def resolve_alert(alert_id: int, request: Request, body: ResolveIn = Body(default=ResolveIn()),
                  user: Principal = Depends(require('responder'))):
    return alerts.resolve(alert_id, body.note, user.username, _rid(request))


# ─── weather ───────────────────────────────────────────────────────────────

@router.get('/weather/current', tags=['weather'])
def weather_current(_: Principal = Depends(current_user)):
    return WEATHER.get_current()


@router.get('/weather/forecast', tags=['weather'])
def weather_forecast(hours: int = Query(48, ge=1, le=48), _: Principal = Depends(current_user)):
    return WEATHER.get_forecast(hours)


@router.get('/weather/model', tags=['weather'])
def weather_model(_: Principal = Depends(current_user)):
    return WEATHER.get_card()


# ─── analytics ─────────────────────────────────────────────────────────────

@router.get('/analytics/summary', tags=['analytics'])
def analytics_summary(_: Principal = Depends(current_user)):
    return analytics.summary()


@router.get('/analytics/timeseries', tags=['analytics'])
def analytics_ts(metric: str = Query('sos_created', pattern='^(sos_created|sos_resolved|alerts|telemetry_frames|state_changes)$'),
                 bucket: str = Query('hour', pattern='^(minute|hour|day)$'), since: Optional[str] = None,
                 _: Principal = Depends(current_user)):
    return analytics.timeseries(metric, bucket, _since(since))


@router.get('/analytics/breakdown', tags=['analytics'])
def analytics_breakdown(by: str = Query('type', pattern='^(type|status|priority)$'),
                        _: Principal = Depends(current_user)):
    return analytics.breakdown(by)


@router.get('/analytics/response-times', tags=['analytics'])
def analytics_rt(_: Principal = Depends(current_user)):
    return analytics.response_times()


# ─── ROV ───────────────────────────────────────────────────────────────────

@router.get('/rov', tags=['rov'])
def rov_units(_: Principal = Depends(current_user)):
    return rov.list_units()


@router.get('/rov/{unit_id}/track', tags=['rov'])
def rov_track(unit_id: int, minutes: int = Query(30, ge=1, le=24 * 60), _: Principal = Depends(current_user)):
    return rov.track(unit_id, minutes)


@router.get('/missions', tags=['rov'])
def missions(_: Principal = Depends(current_user)):
    return rov.missions()


@router.post('/rov/{unit_id}/deploy', tags=['rov'])
def rov_deploy(unit_id: int, body: DeployIn, request: Request, user: Principal = Depends(require('dispatcher'))):
    return rov.deploy(unit_id, body.reference_id.upper(), user.username, _rid(request))


@router.post('/rov/{unit_id}/recall', tags=['rov'])
def rov_recall(unit_id: int, request: Request, user: Principal = Depends(require('dispatcher'))):
    return rov.recall(unit_id, user.username, _rid(request))


@router.post('/rov/{unit_id}/stop', tags=['rov'])
def rov_stop(unit_id: int, request: Request, user: Principal = Depends(require('responder'))):
    return rov.recall(unit_id, user.username, _rid(request), stop=True)


@router.post('/rov/{unit_id}/reset', tags=['rov'])
def rov_reset(unit_id: int, request: Request, user: Principal = Depends(require('dispatcher'))):
    return rov.reset(unit_id, user.username, _rid(request))


@router.post('/rov/{unit_id}/takeover', tags=['rov'])
def rov_takeover(unit_id: int, request: Request, user: Principal = Depends(require('dispatcher'))):
    return rov.takeover(unit_id, user.username, user.role == 'admin', _rid(request))


@router.post('/rov/{unit_id}/release', tags=['rov'])
def rov_release(unit_id: int, request: Request, user: Principal = Depends(require('dispatcher'))):
    return rov.release(unit_id, user.username, user.role == 'admin', _rid(request))


@router.post('/rov/{unit_id}/control', tags=['rov'])
def rov_control(unit_id: int, body: ROVControlIn, request: Request, user: Principal = Depends(require('dispatcher'))):
    return rov.control(unit_id, body.command, body.speed_pct, user.username, _rid(request))


@router.post('/rov/{unit_id}/bridge-key', tags=['rov'])
def rov_bridge_key(unit_id: int, request: Request, body: BridgeKeyIn = Body(default=BridgeKeyIn()),
                   user: Principal = Depends(require('admin'))):
    return rov.bridge_key(unit_id, body.video_url, user.username, _rid(request))


@router.post('/rov/{unit_id}/vision-key', tags=['rov'])
def rov_vision_key(unit_id: int, request: Request, user: Principal = Depends(require('admin'))):
    from ..services import vision
    return vision.vision_key(unit_id, user.username, _rid(request))


@router.post('/rov/vision/frame', tags=['rov'])
def rov_vision_frame(body: dict = Body(...), x_rov_vision_key: str = Header(..., max_length=128)):
    """CV worker: one annotated JPEG (base64) + its detections."""
    from ..services import vision
    return vision.ingest(x_rov_vision_key, body)


@router.get('/rov/{unit_id}/vision', tags=['rov'])
def rov_vision(unit_id: int, _: Principal = Depends(current_user)):
    from ..services.vision import VISION
    return VISION.summary(unit_id)


@router.post('/rov/{unit_id}/vision/ticket', tags=['rov'])
def rov_vision_ticket(unit_id: int, _: Principal = Depends(current_user)):
    from ..services.vision import TICKET_TTL_S, VISION
    t = VISION.ticket(unit_id)
    return {'ticket': t, 'expires_in': TICKET_TTL_S, 'url': f'/api/v1/rov/{unit_id}/vision/stream?ticket={t}'}


@router.get('/rov/{unit_id}/vision/stream', tags=['rov'])
def rov_vision_stream(unit_id: int, ticket: str = Query(..., min_length=10, max_length=64)):
    """MJPEG stream for <img src>; opened with a single-use ticket instead of a bearer header."""
    from fastapi.responses import StreamingResponse
    from ..services.vision import VISION
    VISION.redeem(unit_id, ticket)
    return StreamingResponse(VISION.mjpeg(unit_id), media_type='multipart/x-mixed-replace; boundary=frame',
                             headers={'Cache-Control': 'no-store'})


@router.post('/rov/bridge/telemetry', tags=['rov'])
def rov_bridge(body: dict = Body(...), x_rov_key: str = Header(..., max_length=128)):
    return rov.bridge_ingest(x_rov_key, body)


# ─── audit ─────────────────────────────────────────────────────────────────

@router.get('/audit', tags=['admin'])
def audit_log(limit_: int = Query(200, alias='limit', ge=1, le=1000), _: Principal = Depends(require('admin'))):
    from ..db import iso
    with read_session() as s:
        rows = s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit_)).all()
        return [{'id': a.id, 'actor': a.actor, 'action': a.action, 'target': a.target, 'details': a.details,
                 'request_id': a.request_id, 'at': iso(a.created_at)} for a in rows]


@router.get('/analytics/sensors', tags=['analytics'])
def analytics_sensors(_: Principal = Depends(current_user)):
    return analytics.sensors()


@router.get('/analytics/performance', tags=['analytics'])
def analytics_performance(_: Principal = Depends(current_user)):
    return analytics.performance()


@router.get('/analytics/geo', tags=['analytics'])
def analytics_geo(_: Principal = Depends(current_user)):
    return analytics.geo()


@router.get('/analytics/models', tags=['analytics'])
def analytics_models(_: Principal = Depends(current_user)):
    return analytics.models()


@router.get('/public-data/rivers', tags=['analytics'])
def rivers(_: Principal = Depends(current_user)):
    return public_data.rivers()
