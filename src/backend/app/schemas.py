"""Request bodies (validated) and response serialisers."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .db import iso, utcnow
from .models import Alert, Device, DeviceState, SOSEvent, SOSRequest, Team, User

Availability = Literal['adequate', 'limited', 'critical', 'none']
EmergencyType = Literal['flood', 'tsunami', 'dam-breach', 'storm', 'water-level-rising', 'coastal-erosion',
                        'medical', 'other']
SOSStatus = Literal['pending', 'triaged', 'assigned', 'en_route', 'on_scene', 'resolved', 'cancelled']
Role = Literal['admin', 'dispatcher', 'responder', 'viewer']


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


# ─── auth / users ──────────────────────────────────────────────────────────

class LoginIn(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RefreshIn(Strict):
    refresh_token: str = Field(min_length=20, max_length=256)


class UserIn(Strict):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[a-zA-Z0-9_.-]+$')
    display_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=10, max_length=256)
    role: Role
    team_id: Optional[int] = None


class UserPatch(Strict):
    display_name: Optional[str] = Field(default=None, max_length=128)
    password: Optional[str] = Field(default=None, min_length=10, max_length=256)
    role: Optional[Role] = None
    team_id: Optional[int] = None
    is_active: Optional[bool] = None


def user_out(u: User) -> dict:
    return {'id': u.id, 'username': u.username, 'display_name': u.display_name, 'role': u.role,
            'team_id': u.team_id, 'is_active': u.is_active, 'last_login_at': iso(u.last_login_at)}


# ─── SOS ───────────────────────────────────────────────────────────────────

class Vulnerabilities(Strict):
    pregnant: bool = False
    elderly: bool = False
    children: bool = False
    disabled: bool = False
    medical: bool = False


class SOSIn(Strict):
    name: str = Field(min_length=1, max_length=128)
    age: Optional[int] = Field(default=None, ge=0, le=120)       # a person in distress may not say
    phone: str = Field(min_length=6, max_length=20, pattern=r'^[0-9+()\- ]+$')
    email: Optional[EmailStr] = None
    address: str = Field(min_length=3, max_length=500)
    city: str = Field(min_length=1, max_length=64)
    pincode: Optional[str] = Field(default=None, max_length=12, pattern=r'^[0-9A-Za-z -]*$')

    @field_validator('pincode')
    @classmethod
    def _pincode(cls, v):
        if v is not None and v.strip() and len(v.strip()) < 3:
            raise ValueError('pincode must have at least 3 characters when given')
        return v.strip() or None if v is not None else None
    people_to_rescue: int = Field(ge=1, le=500)
    people_injured: int = Field(ge=0, le=500)
    food_availability: Availability
    water_availability: Availability
    vulnerabilities: Vulnerabilities = Vulnerabilities()
    emergency_type: EmergencyType
    additional_info: Optional[str] = Field(default=None, max_length=2000)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    device_id: Optional[str] = Field(default=None, max_length=64)

    @field_validator('people_injured')
    @classmethod
    def _injured_le_people(cls, v, info):
        n = info.data.get('people_to_rescue')
        if n is not None and v > n:
            raise ValueError('people_injured cannot exceed people_to_rescue')
        return v


class StatusIn(Strict):
    status: SOSStatus
    note: Optional[str] = Field(default=None, max_length=2000)
    version: int = Field(ge=1)


class AssignIn(Strict):
    team_id: int
    version: int = Field(ge=1)


class ReallocateIn(Strict):
    team_id: int
    from_reference_id: str = Field(min_length=4, max_length=16)
    version: int = Field(ge=1)
    from_version: int = Field(ge=1)


class SmsIn(BaseModel):
    model_config = ConfigDict(extra='ignore')
    sender: str = Field(alias='from', min_length=3, max_length=32)
    text: str = Field(min_length=1, max_length=1000)
    id: Optional[str] = Field(default=None, max_length=80)        # gateway message id (retries reuse it)


class NoteIn(Strict):
    text: str = Field(min_length=1, max_length=2000)


def team_brief(t: Optional[Team]) -> Optional[dict]:
    return None if t is None else {'id': t.id, 'name': t.name}


def waiting_min(r: SOSRequest) -> Optional[int]:
    """Minutes an open request has been waiting for a team (None once a team is on it)."""
    if r.status not in ('pending', 'triaged') or r.created_at is None:
        return None
    return int((utcnow() - r.created_at).total_seconds() // 60)


def sos_out(r: SOSRequest) -> dict:
    return {'reference_id': r.reference_id, 'name': r.name, 'age': r.age, 'phone': r.phone, 'email': r.email,
            'address': r.address, 'city': r.city, 'pincode': r.pincode or None, 'people_to_rescue': r.people_to_rescue,
            'people_injured': r.people_injured, 'food_availability': r.food_availability,
            'water_availability': r.water_availability, 'vulnerabilities': r.vulnerabilities,
            'emergency_type': r.emergency_type, 'additional_info': r.additional_info, 'latitude': r.latitude,
            'longitude': r.longitude, 'device_id': r.device_id, 'device_verified': bool(r.device_verified),
            'source': r.source, 'duplicate_of': r.duplicate_of,
            'awaiting_resources': r.awaiting_resources, 'waiting_min': waiting_min(r), 'priority': r.priority,
            'priority_score': r.priority_score, 'priority_reasons': r.priority_reasons, 'status': r.status,
            'version': r.version, 'assigned_team': team_brief(r.team), 'created_at': iso(r.created_at),
            'updated_at': iso(r.updated_at), 'resolved_at': iso(r.resolved_at)}


def event_out(e: SOSEvent) -> dict:
    return {'id': e.id, 'kind': e.kind, 'status': e.status, 'team_id': e.team_id, 'text': e.text,
            'note': e.text, 'actor': e.actor, 'by': e.actor, 'author': e.actor, 'at': iso(e.created_at)}


# ─── teams ─────────────────────────────────────────────────────────────────

class TeamPatch(Strict):
    is_available: Optional[bool] = None
    capacity: Optional[int] = Field(default=None, ge=0, le=100)


def team_out(t: Team) -> dict:
    return {'id': t.id, 'name': t.name, 'type': t.team_type, 'team_type': t.team_type, 'location': t.location,
            'latitude': t.latitude, 'longitude': t.longitude, 'capacity': t.capacity,
            'current_load': t.current_load, 'is_available': t.is_available,
            'deployment_mode': t.deployment_mode, 'contact_phone': t.contact_phone}


# ─── devices / alerts ──────────────────────────────────────────────────────

class DeviceIn(Strict):
    device_id: str = Field(min_length=3, max_length=64, pattern=r'^[A-Za-z0-9_.:-]+$')
    label: str = Field(default='', max_length=128)


class CommandIn(Strict):
    action: Literal['reset_fall', 'calibrate_gsr', 'calibrate_gsr_open', 'set_geofence', 'buzz']
    params: Dict[str, Any] = {}

    @field_validator('params')
    @classmethod
    def _params(cls, v, info):
        a = info.data.get('action')
        if a == 'set_geofence':
            for k in ('lat', 'lng', 'radius_km'):
                if not isinstance(v.get(k), (int, float)):
                    raise ValueError('set_geofence needs numeric lat, lng, radius_km')
        if a == 'buzz' and not (isinstance(v.get('ms', 500), int) and 50 <= v.get('ms', 500) <= 10_000):
            raise ValueError('buzz ms must be 50..10000')
        return v


def device_out(d: Device) -> dict:
    summary = d.last_summary or {}
    return {'device_id': d.device_id, 'label': d.label, 'online': d.online, 'last_seen': iso(d.last_seen),
            'boot_id': d.boot_id, 'fw': d.fw, 'battery_v': summary.get('battery_v'),
            'location': ({'lat': summary['lat'], 'lng': summary['lng']}
                         if summary.get('lat') is not None and summary.get('lng') is not None else None),
            'state': {'ml_health_state': d.state, 'alert_level': d.alert_level, 'risk': summary.get('risk', 0.0),
                      'evidence': summary.get('evidence', [])},
            'heads': summary.get('heads', {}), 'vitals': {k: summary.get(k) for k in
                                                          ('bpm', 'spo2', 'temp_skin_c', 'eda_us', 'acc_std_g')},
            'is_active': d.is_active}


def state_out(s: DeviceState) -> dict:
    return {'state': s.state, 'alert_level': s.alert_level, 'risk': s.risk, 'evidence': s.evidence,
            'at': iso(s.created_at)}


class ResolveIn(Strict):
    note: Optional[str] = Field(default=None, max_length=2000)


def alert_out(a: Alert, sos_ref: Optional[str] = None) -> dict:
    return {'id': a.id, 'device_id': a.device_id, 'state': a.state, 'risk': a.risk, 'evidence': a.evidence,
            'status': a.status, 'escalated': a.escalated, 'opened_at': iso(a.opened_at), 'acked_by': a.acked_by,
            'acked_at': iso(a.acked_at), 'resolved_at': iso(a.resolved_at),
            'resolution_note': a.resolution_note, 'sos_reference_id': sos_ref}


class DeployIn(Strict):
    reference_id: str = Field(min_length=4, max_length=16)


class ROVControlIn(Strict):
    command: Literal['forward', 'backward', 'left', 'right', 'up', 'down', 'stop', 'lights_on', 'lights_off']
    speed_pct: int = Field(default=50, ge=0, le=100)


class BridgeKeyIn(Strict):
    video_url: Optional[str] = Field(default=None, max_length=256, pattern=r'^https?://')


def page(items: List[dict], next_cursor: Optional[str]) -> dict:
    return {'items': items, 'next_cursor': next_cursor}
