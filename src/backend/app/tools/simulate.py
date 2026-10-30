"""Replay simulator: real recorded sessions streamed into the API as virtual wearables.

Each virtual device sends schema-2 frames built from emulated real recordings (PPG-DaLiA daily
life, a WESAD session through its stress phase, a HIFD fall followed by lying still) through the
same path as hardware: device key -> /api/v1/telemetry -> Tier-1 heads -> fusion -> alerts ->
WebSocket. Nothing is synthesised; frames are taken as recorded and only re-timed.

    python -m src.backend.app.tools.simulate --api http://localhost:8000 --speed 4 --with-sos
"""

from __future__ import annotations

import argparse
import math
import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx
import pandas as pd

from src.ml.wearable import paths
from src.ml.wearable.schema import FIELD_NAMES, FRAME_PERIOD_S, to_payload

# Chennai flood-prone neighbourhoods; GPS is not in the source datasets, so each device is placed here
PLACES = {'W-DALIA-01': (13.0418, 80.2341), 'W-WESAD-01': (12.9791, 80.2210), 'W-FALL-01': (13.0120, 80.2410),
          'W-DALIA-02': (13.0827, 80.2707)}


@dataclass
class Scenario:
    device_id: str
    label: str
    frames: pd.DataFrame


def _load(dataset: str) -> pd.DataFrame:
    return pd.read_parquet(paths.FRAMES_DIR / f'{dataset}.parquet')


def scenarios() -> List[Scenario]:
    out = []
    dalia = _load('ppg_dalia')
    for dev, subj in (('W-DALIA-01', 'S1'), ('W-DALIA-02', 'S5')):
        g = dalia[dalia['subject'] == subj].sort_values('frame')
        out.append(Scenario(dev, f'PPG-DaLiA {subj}: daily activities', g))
    wesad = _load('wesad')
    g = wesad[wesad['subject'] == 'S2'].sort_values('frame')
    out.append(Scenario('W-WESAD-01', 'WESAD S2: baseline, TSST stress, amusement', g))
    hifd = _load('hifd')
    fall = hifd[(hifd['subject'] == 'subject_01') & (hifd['trial'] == 'fall__fall3')].sort_values('frame')
    walk = dalia[dalia['subject'] == 'S3'].sort_values('frame').iloc[2000:2200]    # normal life before the fall
    still = pd.concat([fall.iloc[[-1]]] * 160, ignore_index=True)                  # then lying still for 4 min
    out.append(Scenario('W-FALL-01', 'Daily life, a recorded HIFD fall, then lying still', pd.concat(
        [walk, fall, still], ignore_index=True)))
    return out


def _payload(row, device_id: str, seq: int, boot_id: int) -> dict:
    values = {k: (float(row[k]) if k in row and pd.notna(row[k]) else math.nan) for k in FIELD_NAMES}
    lat, lng = PLACES.get(device_id, (13.05, 80.25))
    values.update(gps_lat=lat + random.uniform(-2e-4, 2e-4), gps_lng=lng + random.uniform(-2e-4, 2e-4),
                  gps_sats=9.0, gps_hdop=1.1, power_batt_v=round(4.05 - seq * 2e-5, 3))
    p = to_payload(values, list(row['rr_ms']) if 'rr_ms' in row else [], device_id=device_id, seq=seq)
    p.update(boot_id=boot_id, uptime_ms=int(seq * FRAME_PERIOD_S * 1000), fw='sim-replay')
    return p


class Device(threading.Thread):
    def __init__(self, api: str, key: str, sc: Scenario, speed: float, batch: int, stop: threading.Event):
        super().__init__(daemon=True, name=sc.device_id)
        self.api, self.key, self.sc, self.speed, self.batch, self.stop = api, key, sc, speed, batch, stop
        self.boot_id = int(time.time()) % 100_000

    def run(self) -> None:
        rows = self.sc.frames.reset_index(drop=True)
        acks: List = []
        seq, i = 0, 0
        with httpx.Client(base_url=self.api, headers={'X-Device-Key': self.key}, timeout=10) as c:
            while not self.stop.is_set():
                chunk = [_payload(rows.iloc[(i + k) % len(rows)], self.sc.device_id, seq + k + 1, self.boot_id)
                         for k in range(self.batch)]
                try:
                    r = c.post('/api/v1/telemetry', json={'frames': chunk, 'acks': acks})
                    if r.status_code == 200:
                        body = r.json()
                        acks = [cmd['id'] for cmd in body.get('commands', [])]
                        for cmd in body.get('commands', []):
                            print(f"[{self.sc.device_id}] command {cmd['action']} {cmd['params']}")
                        seq, i = seq + self.batch, i + self.batch
                        st = body['state']
                        if st['alert_level'] != 'none':
                            print(f"[{self.sc.device_id}] {st['ml_health_state']} ({st['alert_level']})")
                    else:
                        print(f'[{self.sc.device_id}] HTTP {r.status_code}: {r.text[:120]}')
                        time.sleep(5)
                except httpx.HTTPError as e:
                    print(f'[{self.sc.device_id}] {type(e).__name__}; retrying')
                    time.sleep(3)
                if i >= len(rows):                     # loop the session as a new boot
                    i, seq, self.boot_id = 0, 0, self.boot_id + 1
                time.sleep(self.batch * FRAME_PERIOD_S / self.speed)


def _admin_token(c: httpx.Client, username: str, password: str) -> str:
    r = c.post('/api/v1/auth/login', json={'username': username, 'password': password})
    r.raise_for_status()
    return r.json()['access_token']


def ensure_devices(c: httpx.Client, token: str, scs: List[Scenario]) -> Dict[str, str]:
    """Register each virtual device (or rotate its key if it exists) and return the keys."""
    h = {'Authorization': f'Bearer {token}'}
    keys = {}
    for sc in scs:
        r = c.post('/api/v1/devices', json={'device_id': sc.device_id, 'label': sc.label}, headers=h)
        if r.status_code == 409:
            r = c.post(f'/api/v1/devices/{sc.device_id}/rotate-key', headers=h)
        r.raise_for_status()
        keys[sc.device_id] = r.json()['api_key']
    return keys


def file_sos(c: httpx.Client, token: str) -> None:
    """Public SOS requests from the people wearing the virtual devices (as the form would send them).
    A wearable named on a public form is only a claim; a dispatcher confirms the link (as here)."""
    people = [('Lakshmi R', 68, 'W-FALL-01', 'flood', 1, {'elderly': True}),
              ('Arun K', 34, 'W-WESAD-01', 'water-level-rising', 0, {}),
              ('Meena S', 41, None, 'storm', 0, {'children': True})]
    for name, age, dev, etype, injured, vul in people:
        lat, lng = PLACES.get(dev, (13.0569, 80.2425))
        body = {'name': name, 'age': age, 'phone': '98400' + str(random.randint(10000, 99999)),
                'address': 'Ground floor, near the canal', 'city': 'Chennai', 'pincode': '600020',
                'people_to_rescue': 1 + injured, 'people_injured': injured, 'food_availability': 'limited',
                'water_availability': 'critical', 'vulnerabilities': vul, 'emergency_type': etype,
                'latitude': lat, 'longitude': lng, 'device_id': dev}
        r = c.post('/api/v1/sos', json=body, headers={'Idempotency-Key': f'sim-{name}-{time.strftime("%Y%m%d")}'})
        print('SOS', r.status_code, r.json().get('reference_id'))
        if dev and r.status_code in (200, 201):
            c.post(f"/api/v1/sos/{r.json()['reference_id']}/link-device", json={'device_id': dev},
                   headers={'Authorization': f'Bearer {token}'})


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--api', default='http://localhost:8000')
    ap.add_argument('--user', default='admin')
    ap.add_argument('--password', default='trident-demo-2026')
    ap.add_argument('--speed', type=float, default=1.0, help='replay speed (1 = real time)')
    ap.add_argument('--batch', type=int, default=2, help='frames per request')
    ap.add_argument('--with-sos', action='store_true', help='also file public SOS requests linked to the devices')
    args = ap.parse_args(argv)
    scs = scenarios()
    with httpx.Client(base_url=args.api, timeout=20) as c:
        token = _admin_token(c, args.user, args.password)
        keys = ensure_devices(c, token, scs)
        if args.with_sos:
            file_sos(c, token)
    stop = threading.Event()
    threads = [Device(args.api, keys[sc.device_id], sc, args.speed, args.batch, stop) for sc in scs]
    for t in threads:
        t.start()
        print(f'{t.sc.device_id}: {t.sc.label} ({len(t.sc.frames)} frames)')
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()


if __name__ == '__main__':
    main()
