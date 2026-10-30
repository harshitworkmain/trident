"""Serial bridge: connects a physical ROV (station laptop, USB serial) to the TRIDENT API.

Every second it reads what the ROV printed on its serial line (the station protocol of
communication/serial_interface.py: `Temperature: 27.4` and, if the firmware sends them,
`Depth: 1.2` / `Heading: 140` / `Battery: 76`), posts it to /api/v1/rov/bridge/telemetry with the
unit's bridge key, and writes back the queued commands as serial lines (`forward_75`, `up_0`,
`on`, `off`), acknowledging them on the next post. The web dashboard then drives the real unit.
If the control room is unreachable for LINK_LOSS_STOP_S, the bridge stops the thrusters itself.

    python -m src.rov.bridge --port COM5 --api http://localhost:8000 --key tdk_...
    (get the key from POST /api/v1/rov/{id}/bridge-key as an admin)
"""

from __future__ import annotations

import argparse
import re
import time

import httpx

LINK_LOSS_STOP_S = 5.0          # no server contact for this long -> stop the thrusters (fail safe)
FIELDS = {'temperature': 'water_temp_c', 'depth': 'depth_m', 'heading': 'heading_deg', 'battery': 'battery_pct'}
FAILSAFE_LINES = ('forward_0', 'up_0')     # the station protocol's stop
LINE = re.compile(r'^\s*([A-Za-z]+)\s*:\s*(-?\d+(?:\.\d+)?)')


def parse_line(line: str) -> dict:
    m = LINE.match(line)
    if not m or m.group(1).lower() not in FIELDS:
        return {}
    return {FIELDS[m.group(1).lower()]: float(m.group(2))}


def _write(ser, line: str) -> None:
    ser.write((line + '\n').encode('utf-8'))


def run(port: str, api: str, key: str, baud: int = 9600, period_s: float = 1.0) -> None:
    import serial                                    # pyserial; only needed on the station laptop
    ser = serial.Serial(port, baud, timeout=0.1)
    acks: list = []
    reading: dict = {}
    with httpx.Client(base_url=api, headers={'X-ROV-Key': key}, timeout=3) as c:
        next_post = time.monotonic()
        last_ok, failsafe = time.monotonic(), False
        while True:
            raw = ser.readline()
            if raw:
                reading.update(parse_line(raw.decode('utf-8', 'replace')))
            if time.monotonic() < next_post:
                continue
            next_post = time.monotonic() + period_s
            try:
                r = c.post('/api/v1/rov/bridge/telemetry', json={**reading, 'acks': acks})
                r.raise_for_status()
                last_ok, failsafe, acks = time.monotonic(), False, []
                for cmd in r.json().get('commands', []):
                    for line in cmd['lines']:
                        _write(ser, line)
                    acks.append(cmd['id'])
                reading = {}
            except httpx.HTTPError as e:
                print(f'bridge: {type(e).__name__}: {e}')
                # a ROV must never keep driving on a command nobody can see or cancel any more
                if not failsafe and time.monotonic() - last_ok > LINK_LOSS_STOP_S:
                    for line in FAILSAFE_LINES:
                        _write(ser, line)
                    failsafe = True
                    print('bridge: link to the control room lost - thrusters stopped')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', required=True)
    ap.add_argument('--api', default='http://localhost:8000')
    ap.add_argument('--key', required=True)
    ap.add_argument('--baud', type=int, default=9600)
    a = ap.parse_args()
    run(a.port, a.api, a.key, a.baud)


if __name__ == '__main__':
    main()
