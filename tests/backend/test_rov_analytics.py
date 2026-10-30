"""ROV missions (semi-autonomous transit, exclusive manual control, dead-man, serial bridge) and
analytics computed from live data."""

import math

from src.ml.wearable.schema import FIELD_NAMES, to_payload

from .conftest import SOS_BODY, auth


def _rov(client, h, name='ROV-001'):
    return next(u for u in client.get('/api/v1/rov', headers=h).json() if u['name'] == name)


def test_mission_transit_and_victims(client):
    disp, admin = auth(client, 'dispatcher'), auth(client, 'admin')
    key = client.post('/api/v1/devices', json={'device_id': 'W-VICTIM'}, headers=admin).json()['api_key']
    v = {k: math.nan for k in FIELD_NAMES}
    v.update(ppg_finger_on=1.0, ppg_bpm=96.0, imu_acc_std_g=0.01, imu_acc_max_g=1.0, gps_lat=13.012, gps_lng=80.241)
    client.post('/api/v1/telemetry', json=to_payload(v, [620.0], device_id='W-VICTIM', seq=1),
                headers={'X-Device-Key': key})
    ref = client.post('/api/v1/sos', json={**SOS_BODY, 'device_id': 'W-VICTIM'}).json()['reference_id']
    unit = _rov(client, disp)
    r = client.post(f"/api/v1/rov/{unit['id']}/deploy", json={'reference_id': ref}, headers=disp)
    assert r.status_code == 200 and r.json()['mode'] == 'auto'
    m = next(x for x in client.get('/api/v1/missions', headers=disp).json() if x['rov']['id'] == unit['id'])
    assert m['sos']['reference_id'] == ref and m['team']['name'] == 'Chennai ROV Alpha'
    victim = next(x for x in m['victims'] if x['reference_id'] == ref)
    assert victim['device']['vitals']['bpm'] == 96.0
    from src.backend.app.services import rov
    for _ in range(600):                               # autonomous transit at simulated speed
        rov.tick()
        if _rov(client, disp)['status'] == 'on_mission':
            break
    after = _rov(client, disp)
    assert after['status'] == 'on_mission' and after['battery_pct'] < unit['battery_pct']
    assert len(client.get(f"/api/v1/rov/{unit['id']}/track", headers=disp).json()) > 5
    notes = [n['text'] for n in client.get(f'/api/v1/sos/{ref}', headers=disp).json()['notes']]
    assert any('arrived on scene' in t for t in notes)
    perf = client.get('/api/v1/analytics/performance', headers=disp).json()
    assert perf['missions']['completed_transits'] >= 1 and perf['missions']['median_transit_min'] is not None


def test_manual_control_is_exclusive(client):
    disp, admin, resp = auth(client, 'dispatcher'), auth(client, 'admin'), auth(client, 'responder')
    unit = _rov(client, disp, 'ROV-002')
    rid = unit['id']
    assert client.post(f'/api/v1/rov/{rid}/control', json={'command': 'forward', 'speed_pct': 50},
                       headers=disp).status_code == 409                       # not in manual yet
    r = client.post(f'/api/v1/rov/{rid}/takeover', headers=disp)
    assert r.json()['mode'] == 'manual' and r.json()['pilot'] == 'dispatcher'
    # another dispatcher-level user cannot drive while dispatcher holds it; an admin can take over
    other = client.post('/api/v1/users', json={'username': 'disp2', 'display_name': 'D2', 'password': 'another-pass-123',
                                                'role': 'dispatcher'}, headers=admin)
    assert other.status_code == 201
    d2 = {'Authorization': 'Bearer ' + client.post('/api/v1/auth/login', json={
        'username': 'disp2', 'password': 'another-pass-123'}).json()['access_token']}
    assert client.post(f'/api/v1/rov/{rid}/takeover', headers=d2).status_code == 409
    assert client.post(f'/api/v1/rov/{rid}/control', json={'command': 'forward'}, headers=d2).status_code == 409
    from src.backend.app.services import rov
    before = _rov(client, disp, 'ROV-002')
    client.post(f'/api/v1/rov/{rid}/control', json={'command': 'forward', 'speed_pct': 100}, headers=disp)
    client.post(f'/api/v1/rov/{rid}/control', json={'command': 'lights_on'}, headers=disp)
    for _ in range(5):
        rov.tick()
    moved = _rov(client, disp, 'ROV-002')
    assert moved['lights_on'] and (moved['latitude'], moved['longitude']) != (before['latitude'], before['longitude'])
    # emergency stop from a responder is always accepted
    assert client.post(f'/api/v1/rov/{rid}/stop', headers=resp).json()['status'] == 'stopped'
    assert client.post(f'/api/v1/rov/{rid}/control', json={'command': 'forward'}, headers=disp).status_code == 409
    assert client.post(f'/api/v1/rov/{rid}/release', headers=d2).status_code == 403
    assert client.post(f'/api/v1/rov/{rid}/release', headers=disp).json()['mode'] == 'auto'
    assert client.post(f'/api/v1/rov/{rid}/reset', headers=disp).json()['status'] == 'returning'


def test_serial_bridge_outbox(client):
    disp, admin = auth(client, 'dispatcher'), auth(client, 'admin')
    unit = _rov(client, disp, 'ROV-001')
    key = client.post(f"/api/v1/rov/{unit['id']}/bridge-key", json={}, headers=admin).json()['api_key']
    assert client.post('/api/v1/rov/bridge/telemetry', json={}, headers={'X-ROV-Key': 'nope'}).status_code == 401
    client.post(f"/api/v1/rov/{unit['id']}/takeover", headers=admin)
    client.post(f"/api/v1/rov/{unit['id']}/control", json={'command': 'down', 'speed_pct': 40}, headers=admin)
    r = client.post('/api/v1/rov/bridge/telemetry', json={'depth_m': 0.8, 'water_temp_c': 27.4},
                    headers={'X-ROV-Key': key}).json()
    lines = [l for c in r['commands'] for l in c['lines']]
    assert lines == ['forward_0', 'up_0', 'down_40']                 # takeover stop, then the move
    live = _rov(client, disp, 'ROV-001')
    assert live['link'] == 'online' and live['depth_m'] == 0.8 and not live['simulated']


def test_analytics_are_live(client):
    h = auth(client, 'viewer')
    sens = client.get('/api/v1/analytics/sensors', headers=h).json()
    victim = next(d for d in sens['devices'] if d['device_id'] == 'W-VICTIM')
    assert victim['signal_availability']['ppg'] == 1.0 and victim['signal_availability']['eda'] == 0.0
    ts = client.get('/api/v1/analytics/timeseries', params={'metric': 'telemetry_frames', 'bucket': 'minute'},
                    headers=h).json()
    assert sum(p['value'] for p in ts['points']) >= 1
    geo = client.get('/api/v1/analytics/geo', headers=h).json()
    assert geo['sos'] and geo['rovs'] and 'rivers' in geo
    models = client.get('/api/v1/analytics/models', headers=h).json()
    assert {m['head'] for m in models['wearable']} >= {'fall', 'stress', 'rhythm'}


def test_river_trend():
    from src.backend.app.services.public_data import _trend
    assert _trend([5, 5, 5, 10, 12]) == 'rising'
    assert _trend([12, 12, 12, 6, 5]) == 'falling'
    assert _trend([5, 5, 5, 5, 5]) == 'steady'


def test_bridge_parses_station_serial_lines():
    from src.rov.bridge import parse_line
    assert parse_line('Temperature: 27.4') == {'water_temp_c': 27.4}
    assert parse_line('Depth: 1.25\r\n') == {'depth_m': 1.25}
    assert parse_line('hello') == {} and parse_line('Speed: 3') == {}
