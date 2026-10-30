"""Wearable telemetry: idempotent ingest, ML + fusion per device, alerts and the command outbox.

Availability first: devices buffer frames offline and resend them; the unique key
(device_id, boot_id, seq) makes every resend harmless. Each device has its own serving runtime
(`src/ml/wearable/serving/runtime.py`: FeatureEngine -> Tier-1 heads -> fusion) keyed by boot, so
a reboot starts a fresh calibration exactly like a new session. Frames for one device are
processed under a per-device lock, in `seq` order; a frame older than the last processed one is
stored but not fed to fusion (its state would be out of order).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, update

from ..audit import audit
from ..config import get_settings
from ..db import iso, read_session, utcnow, write_tx
from ..errors import AppError, Conflict, NotFound
from ..models import Alert, Device, DeviceCommand, DeviceState, SOSRequest, TelemetryFrame
from ..observability import METRICS
from ..realtime import HUB
from ..schemas import alert_out, device_out, state_out
from ..security import new_device_key

logger = logging.getLogger('trident.telemetry')
MAX_BATCH = 200
REDELIVER_AFTER = timedelta(seconds=30)
SUMMARY_EVERY_S = 1.5


class _Runtimes:
    """Lazily loaded Tier-1 models shared by all devices, plus one DeviceRuntime per (device, boot)."""

    def __init__(self):
        self.models = None
        self.error: Optional[str] = None
        self.loaded = False
        self.load_lock = threading.Lock()
        self.devices: Dict[str, Tuple[str, Any, Optional[int]]] = {}   # device -> (boot, runtime, last seq)
        self.locks: Dict[str, threading.Lock] = {}
        self.guard = threading.Lock()

    def load(self) -> None:
        with self.load_lock:
            if self.loaded:
                return
            self.loaded = True
            if not get_settings().ml_enabled:
                self.error = 'ML disabled by configuration'
                return
            try:
                from src.ml.wearable.serving.runtime import load_heads
                t0 = time.perf_counter()
                self.models = load_heads()
                logger.info('wearable heads loaded in %.1fs: %s', time.perf_counter() - t0, sorted(self.models))
            except Exception as e:            # the API must keep working without ML (rules still need models)
                self.error = f'{type(e).__name__}: {e}'
                logger.exception('could not load wearable models')

    def lock(self, device_id: str) -> threading.Lock:
        with self.guard:
            return self.locks.setdefault(device_id, threading.Lock())

    def runtime(self, device_id: str, boot_id: str):
        self.load()
        if self.models is None:
            return None, None
        cur = self.devices.get(device_id)
        if cur is None or cur[0] != boot_id:
            from src.ml.wearable.serving.runtime import DeviceRuntime
            cur = (boot_id, DeviceRuntime(self.models), None)
            self.devices[device_id] = cur
        return cur[1], cur[2]

    def set_last_seq(self, device_id: str, seq: int) -> None:
        boot, rt, _ = self.devices[device_id]
        self.devices[device_id] = (boot, rt, seq)

    def status(self) -> dict:
        return {'loaded': self.models is not None, 'heads': sorted(self.models or {}), 'error': self.error}


RUNTIMES = _Runtimes()
_last_summary_pub: Dict[str, float] = {}


def _clean(x):
    return None if isinstance(x, float) and math.isnan(x) else x


def _summary(values: dict, out: Optional[dict]) -> dict:
    v = values
    spo2 = v.get('ppg_spo2') if v.get('ppg_spo2_valid') == 1.0 else None
    s = {'bpm': v.get('ppg_bpm'), 'spo2': spo2, 'temp_skin_c': v.get('temp_skin_c'), 'eda_us': v.get('eda_us'),
         'acc_std_g': v.get('imu_acc_std_g'), 'acc_max_g': v.get('imu_acc_max_g'), 'battery_v': v.get('power_batt_v'),
         'lat': v.get('gps_lat'), 'lng': v.get('gps_lng'), 'water_wet': v.get('water_wet')}
    s = {k: _clean(x) for k, x in s.items()}
    if out:
        s.update({'state': out['ml_health_state'], 'alert_level': out['alert_level'], 'risk': out['ml_risk_score'],
                  'evidence': out['evidence'], 'heads': out['heads'], 'sensor_fault': out['sensor_fault'],
                  'unavailable_inputs': out['unavailable_inputs']})
    return s


def _frames_from(body: dict) -> Tuple[List[dict], List[int]]:
    if isinstance(body.get('frames'), list):
        frames, acks = body['frames'], body.get('acks')
    else:
        frames, acks = [body], body.get('acks')
    acks = acks if isinstance(acks, list) else []
    if len(frames) > MAX_BATCH:
        raise AppError(f'At most {MAX_BATCH} frames per request', status=413, code='too_large')
    return frames, [int(a) for a in acks[:MAX_BATCH] if isinstance(a, (int, str)) and str(a).isdigit() and len(str(a)) <= 15]


def ingest(device: Device, body: dict) -> dict:
    """Store, de-duplicate, run fusion, open alerts, deliver commands. Returns the device response."""
    from src.ml.wearable.schema import parse_payload
    raw_frames, acks = _frames_from(body)
    parsed, sos_groups = [], []
    rejected = 0
    for raw in raw_frames:
        if not isinstance(raw, dict):
            rejected += 1
            continue
        raw = {**raw, 'device_id': device.device_id}          # the key, not the payload, decides identity
        try:
            f = parse_payload(raw)
        except (ValueError, TypeError, AttributeError, OverflowError):
            # a malformed frame is dropped on its own: a device resending its backlog must not get stuck
            rejected += 1
            continue
        seq = f.seq if isinstance(f.seq, int) else raw.get('seq')
        if not isinstance(seq, int) or isinstance(seq, bool) or not 0 <= seq < 2 ** 53:
            continue
        if isinstance(f.uptime_ms, (int, float)) and not 0 <= f.uptime_ms < 2 ** 53:
            f.uptime_ms = None
        parsed.append((seq, str(raw.get('boot_id') or '')[:32], f))
        if isinstance(raw.get('sos'), dict):
            sos_groups.append((str(raw.get('boot_id') or '')[:32], raw['sos'], f.values))
    parsed.sort(key=lambda x: (x[1], x[0]))
    dev_id = device.device_id
    events: List[Tuple[str, dict]] = []
    with RUNTIMES.lock(dev_id):
        # 1. de-duplicate (read only)
        boots = {b for _, b, _ in parsed}
        with read_session() as s:
            existing = set(s.execute(select(TelemetryFrame.boot_id, TelemetryFrame.seq).where(
                TelemetryFrame.device_id == dev_id, TelemetryFrame.boot_id.in_(boots),
                TelemetryFrame.seq.in_([q for q, _, _ in parsed]))).all()) if parsed else set()
        # 2. ML + fusion outside any transaction: a 120-frame backlog takes seconds of CPU and must not
        #    hold the database write lock (SOS writes would wait behind it)
        fresh, duplicates = [], 0
        for seq, boot, f in parsed:
            if (boot, seq) in existing:
                duplicates += 1
                continue
            existing.add((boot, seq))
            rt, last_seq = RUNTIMES.runtime(dev_id, boot)
            out = None
            if rt is not None and (last_seq is None or seq > last_seq):
                t = (f.uptime_ms / 1000.0) if isinstance(f.uptime_ms, (int, float)) else seq * 1.5
                out = rt.step(t, f.values, f.rr_ms)
                RUNTIMES.set_last_seq(dev_id, seq)
            fresh.append((seq, boot, f, {k: _clean(v) for k, v in f.values.items()}, out))
        # 3. one short write transaction
        with write_tx() as s:
            dev = s.scalar(select(Device).where(Device.device_id == dev_id))
            prev_state = dev.state
            last_out, last_values = None, None
            for seq, boot, f, values, out in fresh:
                s.add(TelemetryFrame(device_id=dev_id, boot_id=boot, seq=seq, uptime_ms=f.uptime_ms, values=values,
                                     rr_ms=f.rr_ms, state=out['ml_health_state'] if out else dev.state,
                                     risk=out['ml_risk_score'] if out else 0.0,
                                     alert_level=out['alert_level'] if out else dev.alert_level,
                                     heads=out['heads'] if out else {}))
                last_values = values
                if out is None:
                    continue
                last_out = out
                if out['ml_health_state'] != dev.state:
                    st = DeviceState(device_id=dev_id, state=out['ml_health_state'], alert_level=out['alert_level'],
                                     risk=out['ml_risk_score'], evidence=out['evidence'])
                    s.add(st)
                    dev.state, dev.alert_level = out['ml_health_state'], out['alert_level']
                    s.flush()
                    events.append(('state', state_out(st)))
                    if out['alert_level'] == 'critical':
                        a = _open_alert(s, dev_id, out)
                        if a is not None:
                            events.append(('alert', a))
            accepted = len(fresh)
            now = utcnow()
            dev.last_seen, dev.online = now, True
            if parsed:
                dev.boot_id = parsed[-1][1] or dev.boot_id
                fw = parsed[-1][2].fw
                dev.fw = str(fw)[:32] if fw else dev.fw
            if last_values is not None:
                dev.last_summary = (_summary(last_values, last_out) if last_out
                                    else {**(dev.last_summary or {}), **_summary(last_values, None)})
            if RUNTIMES.models is None and RUNTIMES.loaded:
                dev.state, dev.alert_level = 'UNKNOWN', 'none'      # ML unavailable: do not show "STABLE"
            commands = _commands(s, dev_id, acks, now)
            device_view = device_out(dev)
            went_online = not device.online
    METRICS.inc('telemetry_frames_total', accepted, result='accepted')
    METRICS.inc('telemetry_frames_total', duplicates, result='duplicate')
    _publish(dev_id, device_view, events, went_online, prev_state != device_view['state']['ml_health_state'])
    state = device_view['state']
    METRICS.inc('telemetry_frames_total', rejected, result='rejected')
    out = {'accepted': accepted, 'duplicates': duplicates, 'rejected': rejected, 'commands': commands,
           'state': {'ml_health_state': state['ml_health_state'], 'ml_risk_score': state['risk'],
                     'alert_level': state['alert_level']}}
    if sos_groups:
        ack = sos_button(dev_id, device.label, sos_groups, device_view)
        if ack:
            out['sos'] = ack
    return out


def sos_button(dev_id: str, label: str, groups, view: dict) -> Optional[dict]:
    """The band's SOS button: a deliberate cry for help from someone who may have no phone.

    Each press (boot, press_id) becomes one SOS request (idempotent: the band repeats the group in
    every frame until acknowledged) plus a critical SOS_BUTTON alert. A cancel from the band adds a
    note and resolves the alert but leaves the request for a dispatcher: a cancelled SOS can be an
    accident, or someone who is no longer able to ask.
    """
    from ..schemas import SOSIn, Vulnerabilities
    from ..models import IdempotencyKey
    from . import sos as sos_service
    latest = {}
    for boot, g, values in groups:
        press = g.get('press_id')
        if (isinstance(press, int) and not isinstance(press, bool) and 0 <= press < 2 ** 32
                and (g.get('active') is True or g.get('cancelled') is True)):
            latest[(boot, press)] = (g, values)
    ack = None
    for (boot, press), (g, values) in sorted(latest.items(), key=lambda kv: kv[0][1]):
        key = f'wsos:{dev_id}:{boot}:{press}'
        with read_session() as s:
            known = s.get(IdempotencyKey, sos_service.idem_key('wearable', key)) is not None
        lat = values.get('gps_lat') if values.get('gps_lat') == values.get('gps_lat') else None
        lng = values.get('gps_lng') if values.get('gps_lng') == values.get('gps_lng') else None
        loc = view.get('location') or {}
        lat, lng = lat if lat is not None else loc.get('lat'), lng if lng is not None else loc.get('lng')
        wet = values.get('water_wet') == 1.0
        body = SOSIn.model_construct(
            name=label or dev_id, age=None, phone='-', email=None,
            address=(f'Wearable {dev_id} GPS position' if lat is not None else f'Wearable {dev_id}: no GPS fix yet'),
            city='Unknown (wearable)', pincode='-', people_to_rescue=1, people_injured=0,
            food_availability='adequate', water_availability='adequate', vulnerabilities=Vulnerabilities(),
            emergency_type='flood' if wet else 'other',
            additional_info=f'SOS button pressed on wearable {dev_id} (press {press}); device state '
                            f"{view['state']['ml_health_state']}", latitude=lat, longitude=lng, device_id=dev_id)
        res = sos_service.create(body, key, None, source='wearable', actor=f'device:{dev_id}', device_verified=True)
        ref = res['reference_id']
        if not known:
            with write_tx() as s:
                sid = s.scalar(select(SOSRequest.id).where(SOSRequest.reference_id == ref))
                a = Alert(device_id=dev_id, state='SOS_BUTTON', risk=1.0, sos_id=sid,
                          evidence=['SOS button pressed on the band',
                                    f'position {lat:.5f}, {lng:.5f}' if lat is not None else 'no GPS fix',
                                    f"device state {view['state']['ml_health_state']}"])
                s.add(a)
                s.flush()
                opened = alert_out(a, ref)
            HUB.publish('alerts', {'event': 'opened', 'alert': opened})
        cancelled = g.get('cancelled') is True and g.get('active') is not True
        if cancelled:
            _sos_cancelled(dev_id, ref, f'wsos-cancel:{dev_id}:{boot}:{press}')
        ack = {'received': True, 'reference_id': ref, 'press_id': press, 'cancelled': cancelled}
    return ack


def _sos_cancelled(dev_id: str, ref: str, key: str) -> None:
    from ..models import IdempotencyKey, SOSEvent
    with write_tx() as s:
        if s.get(IdempotencyKey, key) is not None:
            return
        s.add(IdempotencyKey(key=key, scope='wsos', response={'reference_id': ref}))
        sid = s.scalar(select(SOSRequest.id).where(SOSRequest.reference_id == ref))
        s.add(SOSEvent(sos_id=sid, kind='note', actor=f'device:{dev_id}',
                       text='Wearer cancelled the SOS on the band (held 5 s). Check before standing down.'))
        a = s.scalar(select(Alert).where(Alert.sos_id == sid, Alert.state == 'SOS_BUTTON', Alert.status != 'resolved'))
        out = None
        if a is not None:
            a.status, a.resolved_at, a.resolution_note = 'resolved', utcnow(), 'cancelled by the wearer on the band'
            out = alert_out(a, ref)
    if out:
        HUB.publish('alerts', {'event': 'resolved', 'alert': out})


def _open_alert(s, dev_id: str, out: dict) -> Optional[dict]:
    """One open alert per device and state; links to the most urgent open SOS that names the device."""
    open_same = s.scalar(select(Alert).where(Alert.device_id == dev_id, Alert.state == out['ml_health_state'],
                                             Alert.status.in_(('open', 'acked'))))
    if open_same is not None:
        return None
    sos = s.scalar(select(SOSRequest).where(SOSRequest.device_id == dev_id, SOSRequest.device_verified.is_(True),
                                            SOSRequest.status.notin_(('resolved', 'cancelled')))
                   .order_by(SOSRequest.priority_score.desc()))
    a = Alert(device_id=dev_id, state=out['ml_health_state'], risk=out['ml_risk_score'], evidence=out['evidence'],
              sos_id=sos.id if sos else None)
    s.add(a)
    s.flush()
    return alert_out(a, sos.reference_id if sos else None)


def _commands(s, dev_id: str, acks: List[int], now) -> List[dict]:
    if acks:
        s.execute(update(DeviceCommand).where(DeviceCommand.device_id == dev_id, DeviceCommand.id.in_(acks),
                                              DeviceCommand.status != 'acked')
                  .values(status='acked', acked_at=now))
    due = s.scalars(select(DeviceCommand).where(
        DeviceCommand.device_id == dev_id,
        (DeviceCommand.status == 'queued') |
        ((DeviceCommand.status == 'delivered') & (DeviceCommand.delivered_at < now - REDELIVER_AFTER)))
        .order_by(DeviceCommand.id).limit(10)).all()
    for c in due:
        c.status, c.delivered_at = 'delivered', now
    return [{'id': c.id, 'action': c.action, 'params': c.params} for c in due]


def _publish(dev_id: str, view: dict, events, went_online: bool, state_changed: bool) -> None:
    loc = view.get('location') or {}
    view = {**view, **view.get('vitals', {}), 'lat': loc.get('lat'), 'lng': loc.get('lng'),
            'risk': view['state']['risk'], 'alert_level': view['state']['alert_level']}
    if went_online:
        HUB.publish('devices', {'event': 'online', 'device_id': dev_id, 'summary': view})
    for kind, data in events:
        if kind == 'state':
            HUB.publish('devices', {'event': 'state', 'device_id': dev_id, 'summary': view, 'transition': data})
        else:
            HUB.publish('alerts', {'event': 'opened', 'alert': data})
    now = time.monotonic()
    if state_changed or now - _last_summary_pub.get(dev_id, 0) >= SUMMARY_EVERY_S:
        _last_summary_pub[dev_id] = now
        HUB.publish('devices', {'event': 'frame', 'device_id': dev_id, 'summary': view})


# ─── staff-side device management ──────────────────────────────────────────

def register(device_id: str, label: str, actor: str, request_id: Optional[str]) -> dict:
    key, key_hash = new_device_key()
    with write_tx() as s:
        if s.scalar(select(Device.id).where(Device.device_id == device_id)) is not None:
            raise Conflict(f'Device {device_id} already exists')
        s.add(Device(device_id=device_id, label=label, key_hash=key_hash))
        audit(s, actor, 'device.register', device_id, {'label': label}, request_id)
    return {'device_id': device_id, 'api_key': key}


def rotate_key(device_id: str, actor: str, request_id: Optional[str]) -> dict:
    key, key_hash = new_device_key()
    with write_tx() as s:
        d = s.scalar(select(Device).where(Device.device_id == device_id))
        if d is None:
            raise NotFound(f'Device {device_id} not found')
        d.key_hash, d.key_rotated_at = key_hash, utcnow()
        audit(s, actor, 'device.rotate_key', device_id, {}, request_id)
    return {'device_id': device_id, 'api_key': key}


def queue_command(device_id: str, action: str, params: dict, actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        if s.scalar(select(Device.id).where(Device.device_id == device_id)) is None:
            raise NotFound(f'Device {device_id} not found')
        c = DeviceCommand(device_id=device_id, action=action, params=params, created_by=actor)
        s.add(c)
        audit(s, actor, 'device.command', device_id, {'action': action, 'params': params}, request_id)
        s.flush()
        return {'id': c.id, 'device_id': device_id, 'action': action, 'params': params, 'status': c.status,
                'created_at': iso(c.created_at)}


def list_devices() -> List[dict]:
    with read_session() as s:
        return [device_out(d) for d in s.scalars(select(Device).order_by(Device.device_id)).all()]


def frames(device_id: str, since=None, limit: int = 400) -> List[dict]:
    limit = max(1, min(2000, limit))
    with read_session() as s:
        stmt = select(TelemetryFrame).where(TelemetryFrame.device_id == device_id)
        if since is not None:
            stmt = stmt.where(TelemetryFrame.received_at >= since)
        rows = s.scalars(stmt.order_by(TelemetryFrame.id.desc()).limit(limit)).all()
        return [{'seq': f.seq, 'boot_id': f.boot_id, 'received_at': iso(f.received_at), 'uptime_ms': f.uptime_ms,
                 **f.values, 'rr_ms': f.rr_ms, 'state': f.state, 'risk': f.risk, 'alert_level': f.alert_level,
                 'heads': f.heads} for f in reversed(rows)]


def states(device_id: str, since=None, limit: int = 200) -> List[dict]:
    with read_session() as s:
        stmt = select(DeviceState).where(DeviceState.device_id == device_id)
        if since is not None:
            stmt = stmt.where(DeviceState.created_at >= since)
        rows = s.scalars(stmt.order_by(DeviceState.id.desc()).limit(limit)).all()
        return [state_out(x) for x in reversed(rows)]


def commands_for(device_id: str, limit: int = 50) -> List[dict]:
    with read_session() as s:
        rows = s.scalars(select(DeviceCommand).where(DeviceCommand.device_id == device_id)
                         .order_by(DeviceCommand.id.desc()).limit(limit)).all()
        return [{'id': c.id, 'action': c.action, 'params': c.params, 'status': c.status, 'created_by': c.created_by,
                 'created_at': iso(c.created_at), 'delivered_at': iso(c.delivered_at), 'acked_at': iso(c.acked_at)}
                for c in rows]


# ─── scheduled ─────────────────────────────────────────────────────────────

def mark_offline(offline_after_s: int) -> int:
    cutoff = utcnow() - timedelta(seconds=offline_after_s)
    opened = []
    with write_tx() as s:
        stale = s.scalars(select(Device).where(Device.online.is_(True), Device.last_seen < cutoff)).all()
        for d in stale:
            d.online = False
            if d.state not in ('STABLE', 'UNKNOWN'):   # UNKNOWN: ML off, nothing known to escalate
                # silence from someone in a non-stable state is itself an emergency (dead battery, crushed
                # or submerged device, out of range) - nobody should have to notice a grey dot
                secs = int((utcnow() - d.last_seen).total_seconds())
                a = _open_alert(s, d.device_id, {'ml_health_state': 'LOST_CONTACT', 'ml_risk_score': 0.9,
                                                 'evidence': [f'last seen {secs} s ago in {d.state}',
                                                              f'last risk {(d.last_summary or {}).get("risk", 0):.2f}']})
                if a is not None:
                    opened.append(a)
        views = [device_out(d) for d in stale]
    for v in views:
        HUB.publish('devices', {'event': 'offline', 'device_id': v['device_id'], 'summary': v})
    for a in opened:
        HUB.publish('alerts', {'event': 'opened', 'alert': a})
    return len(views)


def retention(keep_days: int = 7) -> int:
    """Drop raw frames older than keep_days, keeping state transitions and alerts (the clinical record)."""
    cutoff = utcnow() - timedelta(days=keep_days)
    with write_tx() as s:
        from sqlalchemy import delete
        return s.execute(delete(TelemetryFrame).where(TelemetryFrame.received_at < cutoff)).rowcount or 0
