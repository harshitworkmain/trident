"""ROV camera + computer vision relay.

The vision worker (src/cv/vision, next to the ROV or the station laptop) reads the ROV camera, runs
YOLOv8n object detection, Haar + LBPH face recognition and pinhole distance estimation, and posts
annotated JPEG frames with their detections here (authenticated by the unit's vision key). The
API keeps only the latest frame per unit in memory and relays it to dashboards as an MJPEG
stream; detections also go out on the `rov` WebSocket topic. Heavy CV dependencies (torch,
ultralytics) therefore never load into the API process.

Browsers cannot send a bearer header for <img> streams, so a signed-in user first gets a
short-lived single-purpose ticket (POST .../vision/ticket) and opens the stream with it; access
tokens never appear in URLs or logs.
"""

from __future__ import annotations

import asyncio
import base64
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from sqlalchemy import select

from ..audit import audit
from ..db import iso, read_session, utcnow, write_tx
from ..errors import AppError, NotFound, Unauthorized
from ..models import ROVUnit
from ..realtime import HUB
from ..security import new_device_key, sha256

MAX_JPEG_BYTES = 600_000
STALE_S = 5.0                     # no frame for this long: the feed is shown as offline
TICKET_TTL_S = 60                 # a ticket must be used to open the stream within this time
STREAM_MAX_FPS = 8
PUBLISH_EVERY_S = 0.5             # detections on the WebSocket at most twice a second per unit


@dataclass
class _Feed:
    jpeg: bytes = b''
    detections: dict = field(default_factory=dict)
    at: float = 0.0
    received_at: Optional[str] = None
    frames: int = 0
    fps: float = 0.0
    published: float = 0.0
    seq: int = 0


class _VisionHub:
    def __init__(self):
        self.feeds: Dict[int, _Feed] = {}
        self.tickets: Dict[str, tuple] = {}            # ticket -> (rov_id, expires monotonic)
        self.lock = threading.Lock()

    def summary(self, rov_id: int) -> dict:
        f = self.feeds.get(rov_id)
        if f is None or not f.jpeg:
            return {'active': False}
        d = f.detections
        return {'active': time.monotonic() - f.at < STALE_S, 'fps': round(f.fps, 1), 'last_frame_at': f.received_at,
                'persons': d.get('persons', 0), 'faces': d.get('faces', []), 'objects': d.get('objects', [])[:12],
                'model': d.get('model')}

    def ingest(self, rov_id: int, jpeg: bytes, detections: dict) -> dict:
        now = time.monotonic()
        with self.lock:
            f = self.feeds.setdefault(rov_id, _Feed())
            if f.at:
                dt = now - f.at
                f.fps = 0.8 * f.fps + 0.2 * (1.0 / dt) if dt > 0 else f.fps
            f.jpeg, f.detections, f.at, f.received_at = jpeg, detections, now, iso(utcnow())
            f.frames += 1
            f.seq += 1
            publish = now - f.published >= PUBLISH_EVERY_S
            if publish:
                f.published = now
        if publish:
            HUB.publish('rov', {'event': 'vision', 'rov_id': str(rov_id), 'vision': self.summary(rov_id)})
        return {'accepted': True, 'frames': f.frames}

    def ticket(self, rov_id: int) -> str:
        t = secrets.token_urlsafe(24)
        now = time.monotonic()
        with self.lock:
            self.tickets = {k: v for k, v in self.tickets.items() if v[1] > now}     # drop expired
            self.tickets[t] = (rov_id, now + TICKET_TTL_S)
        return t

    def redeem(self, rov_id: int, ticket: str) -> None:
        with self.lock:
            hit = self.tickets.pop(ticket, None)
        if hit is None or hit[0] != rov_id or hit[1] < time.monotonic():
            raise Unauthorized('Invalid or expired stream ticket')

    stream_idle_end_s = 30.0          # a feed silent this long ends the stream; the dashboard reconnects

    async def mjpeg(self, rov_id: int):
        """multipart/x-mixed-replace stream of the latest annotated frame, while the client reads."""
        last_seq, period, idle_since = -1, 1.0 / STREAM_MAX_FPS, time.monotonic()
        while time.monotonic() - idle_since < self.stream_idle_end_s:
            f = self.feeds.get(rov_id)
            if f is not None and f.seq != last_seq and f.jpeg:
                last_seq, idle_since = f.seq, time.monotonic()
                yield (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(f.jpeg)).encode()
                       + b'\r\n\r\n' + f.jpeg + b'\r\n')
            await asyncio.sleep(period)


VISION = _VisionHub()


def vision_key(unit_id: int, actor: str, request_id: Optional[str]) -> dict:
    key, key_hash = new_device_key()
    with write_tx() as s:
        u = s.get(ROVUnit, unit_id)
        if u is None:
            raise NotFound('ROV not found')
        u.vision_key_hash = key_hash
        audit(s, actor, 'rov.vision_key', u.name, {}, request_id)
    return {'rov_id': str(unit_id), 'api_key': key}


def ingest(key: str, body: dict) -> dict:
    with read_session() as s:
        u = s.scalar(select(ROVUnit).where(ROVUnit.vision_key_hash == sha256(key)))
        if u is None:
            raise Unauthorized('Unknown ROV vision key')
        unit_id = u.id
    try:
        jpeg = base64.b64decode(body.get('jpeg_b64') or '', validate=True)
    except (ValueError, TypeError):
        raise AppError('jpeg_b64 is not valid base64')
    if not jpeg.startswith(b'\xff\xd8') or len(jpeg) > MAX_JPEG_BYTES:
        raise AppError(f'Expected a JPEG of at most {MAX_JPEG_BYTES // 1000} kB', status=413, code='too_large')
    det = body.get('detections') if isinstance(body.get('detections'), dict) else {}
    return VISION.ingest(unit_id, jpeg, _clean(det))


def _clean(d: dict) -> dict:
    """Keep only the expected detection fields, bounded, so a worker cannot push arbitrary data to dashboards."""
    def num(x, lo=0.0, hi=1e6):
        return float(x) if isinstance(x, (int, float)) and lo <= x <= hi else None

    objects = []
    for o in (d.get('objects') or [])[:50]:
        if isinstance(o, dict) and isinstance(o.get('label'), str):
            box = o.get('box') if isinstance(o.get('box'), list) and len(o.get('box')) == 4 else None
            objects.append({'label': o['label'][:32], 'confidence': num(o.get('confidence'), 0, 1),
                            'distance_m': num(o.get('distance_m'), 0, 500),
                            'box': [int(v) for v in box] if box and all(isinstance(v, (int, float)) for v in box) else None})
    faces = []
    for fc in (d.get('faces') or [])[:20]:
        if isinstance(fc, dict):
            faces.append({'name': str(fc.get('name') or 'Unknown')[:64], 'match': num(fc.get('match'), 0, 1),
                          'distance_m': num(fc.get('distance_m'), 0, 500)})
    return {'objects': objects, 'faces': faces, 'persons': int(num(d.get('persons'), 0, 1000) or 0),
            'model': str(d.get('model') or '')[:64], 'frame_w': int(num(d.get('frame_w'), 0, 10000) or 0),
            'frame_h': int(num(d.get('frame_h'), 0, 10000) or 0)}
