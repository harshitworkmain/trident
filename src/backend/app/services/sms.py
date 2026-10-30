"""SOS by SMS: the fallback when there is no mobile data (only a weak 2G signal).

People send a compact text to the control-room number; an SMS gateway (cloud provider or a GSM
modem attached to the control-room PC) forwards it here as a webhook. The format is what the
web form prepares offline, but parsing is tolerant because people also type it by hand:

    SOS 13.0120,80.2410 P3 I1 Tflood elderly, water critical
    sos p 2 i 0 storm near anna nagar bus depot

Coordinates, people (P), injured (I) and type (T) are optional. Anything the message cannot
carry (age, supplies) is stored as unknown rather than guessed, and scored conservatively.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..config import get_settings
from ..schemas import SOSIn, Vulnerabilities
from . import sos

TYPES = ('flood', 'tsunami', 'dam-breach', 'storm', 'water-level-rising', 'coastal-erosion', 'medical', 'other')
COORDS = re.compile(r'(-?\d{1,2}\.\d{2,})\s*[, ]\s*(-?\d{1,3}\.\d{2,})')
FIELD = re.compile(r'\b([pit])\s*[:=]?\s*([a-z0-9-]+)', re.I)
VULNERABLE = {'elderly': 'elderly', 'old': 'elderly', 'child': 'children', 'children': 'children', 'baby': 'children',
              'pregnant': 'pregnant', 'disabled': 'disabled', 'wheelchair': 'disabled', 'medical': 'medical',
              'injured': 'medical', 'bleeding': 'medical', 'diabetic': 'medical'}


def parse(text: str) -> dict:
    t = text.strip()
    t = re.sub(r'^\s*sos\b[:\s-]*', '', t, flags=re.I)
    out: dict = {'people': 1, 'injured': 0, 'type': 'other', 'lat': None, 'lng': None}
    m = COORDS.search(t)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            out['lat'], out['lng'] = lat, lng
        t = t[:m.start()] + t[m.end():]
    for key, val in FIELD.findall(t):
        k = key.lower()
        if k == 'p' and val.isdigit():
            out['people'] = max(1, min(500, int(val)))
        elif k == 'i' and val.isdigit():
            out['injured'] = min(500, int(val))
        elif k == 't' and val.lower() in TYPES:
            out['type'] = val.lower()
    note = FIELD.sub(' ', t)
    note = re.sub(r'\s+', ' ', note).strip(' ,;')
    if out['type'] == 'other':                           # a bare type word in the note also counts
        out['type'] = next((ty for ty in TYPES if re.search(rf'\b{ty}\b', note, re.I)), 'other')
    out['injured'] = min(out['injured'], out['people'])
    out['note'] = note[:500]
    words = set(re.findall(r'[a-z]+', note.lower()))
    out['vulnerabilities'] = {v: True for w, v in VULNERABLE.items() if w in words}
    return out


def ingest(sender: str, text: str, message_id: Optional[str], request_id: Optional[str]) -> dict:
    p = parse(text)
    body = SOSIn.model_construct(
        name=f'SMS {sender[-4:]}', age=None, phone=sender, email=None,
        address=p['note'] or 'Sent by SMS, no address given', city='Unknown (SMS)', pincode='-',
        people_to_rescue=p['people'], people_injured=p['injured'],
        food_availability='adequate', water_availability='adequate',       # unknown: not scored up
        vulnerabilities=Vulnerabilities(**p['vulnerabilities']), emergency_type=p['type'],
        additional_info=f'SMS from {sender}: {text[:900]}', latitude=p['lat'], longitude=p['lng'], device_id=None)
    # gateways retry deliveries: their message id (or the text itself, per sender per day) is the idempotency key
    key = 'sms:' + (message_id or hashlib.sha256(f'{sender}|{text.strip()}'.encode()).hexdigest()[:32])
    res = sos.create(body, key, request_id, source='sms', actor=f'sms:{sender[-4:]}')       # never verified
    track = f"{get_settings().public_url}/track/{res['reference_id']}?token={res['tracking_token']}"
    reply = (f"TRIDENT: request {res['reference_id']} received, priority P{res['priority']}. "
             + ('Send your location as SOS <lat>,<lng> if you can. ' if p['lat'] is None else '')
             + f'Track: {track}')
    return {**res, 'reply': reply[:300], 'parsed': {k: v for k, v in p.items() if k != 'note'}}
