"""ORM models. Schema changes go through Alembic migrations (src/backend/migrations)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow

SOS_STATUSES = ('pending', 'triaged', 'assigned', 'en_route', 'on_scene', 'resolved', 'cancelled')
ROLES = ('admin', 'dispatcher', 'responder', 'viewer')


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey('teams.id'), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RefreshToken(Base):
    """Opaque refresh tokens (hashed). A family is one login; reusing a rotated token kills the family."""
    __tablename__ = 'refresh_tokens'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Team(Base):
    __tablename__ = 'teams'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    team_type: Mapped[str] = mapped_column(String(64))
    contact_phone: Mapped[str] = mapped_column(String(32))
    location: Mapped[str] = mapped_column(String(64))
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=5)            # concurrent missions
    current_load: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    deployment_mode: Mapped[str] = mapped_column(String(16), default='MANUAL_DEPLOY')
    description: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[int] = mapped_column(Integer, default=1)


class SOSRequest(Base):
    __tablename__ = 'sos_requests'
    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(16), unique=True)
    tracking_hash: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)      # unknown for SMS requests
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    address: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(64))
    pincode: Mapped[str] = mapped_column(String(12))
    people_to_rescue: Mapped[int] = mapped_column(Integer)
    people_injured: Mapped[int] = mapped_column(Integer)
    food_availability: Mapped[str] = mapped_column(String(16))
    water_availability: Mapped[str] = mapped_column(String(16))
    vulnerabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    emergency_type: Mapped[str] = mapped_column(String(32))
    additional_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    device_verified: Mapped[bool] = mapped_column(Boolean, default=False)   # link confirmed by device or dispatcher
    source: Mapped[str] = mapped_column(String(16), default='web')          # web | sms | wearable
    duplicate_of: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    awaiting_resources: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    priority_score: Mapped[int] = mapped_column(Integer, default=0)
    priority_reasons: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default='pending', index=True)
    assigned_team_id: Mapped[Optional[int]] = mapped_column(ForeignKey('teams.id'), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    team: Mapped[Optional[Team]] = relationship(lazy='joined')


class SOSEvent(Base):
    """Status history, assignments and notes in one append-only timeline."""
    __tablename__ = 'sos_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    sos_id: Mapped[int] = mapped_column(ForeignKey('sos_requests.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(16))            # status | assign | note | priority
    status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey('teams.id'), nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(64), default='system')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Device(Base):
    __tablename__ = 'devices'
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(128), default='')
    key_hash: Mapped[str] = mapped_column(String(64))
    key_rotated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    boot_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    fw: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_summary: Mapped[dict] = mapped_column(JSON, default=dict)      # latest frame summary + fusion state
    state: Mapped[str] = mapped_column(String(32), default='STABLE')
    alert_level: Mapped[str] = mapped_column(String(16), default='none')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TelemetryFrame(Base):
    __tablename__ = 'telemetry_frames'
    __table_args__ = (UniqueConstraint('device_id', 'boot_id', 'seq', name='uq_frame_device_boot_seq'),
                      Index('ix_frames_device_time', 'device_id', 'received_at'))
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64))
    boot_id: Mapped[str] = mapped_column(String(32), default='')
    seq: Mapped[int] = mapped_column(BigInteger)
    uptime_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    values: Mapped[dict] = mapped_column(JSON)           # schema.FIELD_NAMES -> value (null = unavailable)
    rr_ms: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(32), default='STABLE')
    risk: Mapped[float] = mapped_column(Float, default=0.0)
    alert_level: Mapped[str] = mapped_column(String(16), default='none')
    heads: Mapped[dict] = mapped_column(JSON, default=dict)


class DeviceState(Base):
    """Fusion state transitions (one row per change), the clinical timeline of a device."""
    __tablename__ = 'device_states'
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32))
    alert_level: Mapped[str] = mapped_column(String(16))
    risk: Mapped[float] = mapped_column(Float)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DeviceCommand(Base):
    """Outbox: queued -> delivered (returned in a telemetry response) -> acked (id echoed back)."""
    __tablename__ = 'device_commands'
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default='queued')
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Alert(Base):
    __tablename__ = 'alerts'
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32))
    risk: Mapped[float] = mapped_column(Float)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default='open', index=True)   # open | acked | resolved
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    acked_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sos_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sos_requests.id'), nullable=True)


class ROVUnit(Base):
    """A semi-autonomous ROV: navigates to its target on its own (`mode=auto`); one dispatcher at a
    time can take manual control (`pilot`). Real units report through the serial bridge
    (src/rov/bridge.py, `link=online`); without one the unit is simulated (`simulated=True`)."""
    __tablename__ = 'rov_units'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey('teams.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default='idle')   # idle|deploying|on_mission|returning|stopped
    mode: Mapped[str] = mapped_column(String(8), default='auto')      # auto | manual
    pilot: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    battery_pct: Mapped[float] = mapped_column(Float, default=100.0)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    depth_m: Mapped[float] = mapped_column(Float, default=0.0)
    heading_deg: Mapped[float] = mapped_column(Float, default=0.0)
    water_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_pct: Mapped[int] = mapped_column(Integer, default=0)
    thrust: Mapped[str] = mapped_column(String(16), default='stop')    # last movement command
    lights_on: Mapped[bool] = mapped_column(Boolean, default=False)
    home_lat: Mapped[float] = mapped_column(Float)
    home_lng: Mapped[float] = mapped_column(Float)
    target_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mission_sos_id: Mapped[Optional[int]] = mapped_column(ForeignKey('sos_requests.id'), nullable=True)
    mission_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)      # serial bridge key
    vision_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # camera/CV worker key
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    video_url: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ROVCommand(Base):
    """Outbox for real units: the bridge picks commands up and writes them to the ROV's serial line."""
    __tablename__ = 'rov_commands'
    id: Mapped[int] = mapped_column(primary_key=True)
    rov_id: Mapped[int] = mapped_column(ForeignKey('rov_units.id', ondelete='CASCADE'), index=True)
    command: Mapped[str] = mapped_column(String(32))
    speed_pct: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default='queued')    # queued | delivered | acked
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ROVSample(Base):
    """ROV telemetry track (1 Hz while active), for the mission map and depth/heading charts."""
    __tablename__ = 'rov_samples'
    id: Mapped[int] = mapped_column(primary_key=True)
    rov_id: Mapped[int] = mapped_column(ForeignKey('rov_units.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    depth_m: Mapped[float] = mapped_column(Float)
    heading_deg: Mapped[float] = mapped_column(Float)
    battery_pct: Mapped[float] = mapped_column(Float)
    water_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class PublicDataCache(Base):
    """Snapshots of external public data (e.g. Open-Meteo GloFAS river discharge), refreshed by a job."""
    __tablename__ = 'public_data_cache'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[Any] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(128))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IdempotencyKey(Base):
    __tablename__ = 'idempotency_keys'
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    scope: Mapped[str] = mapped_column(String(32))
    response: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SchedulerLease(Base):
    """Leader election for periodic jobs: one row per job, held by one process until it expires."""
    __tablename__ = 'scheduler_leases'
    job: Mapped[str] = mapped_column(String(64), primary_key=True)
    holder: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class AuditLog(Base):
    __tablename__ = 'audit_log'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(128))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    request_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class EmergencyContact(Base):
    __tablename__ = 'emergency_contacts'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(32))
    department: Mapped[str] = mapped_column(String(64))
    location: Mapped[str] = mapped_column(String(64), default='')
