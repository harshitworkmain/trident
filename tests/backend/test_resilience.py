"""Degraded conditions: duplicates, priority ageing, no free teams (urgency order, suggestions,
atomic reallocation), SMS intake without data, lost contact, ROV dead-man and bridge fail-safe."""

import math
from datetime import timedelta

import pytest

from src.ml.wearable.schema import FIELD_NAMES, to_payload

from .conftest import SOS_BODY, auth


def _sos(client, **kw):
    r = client.post('/api/v1/sos', json={**SOS_BODY, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_duplicate_requests_are_linked_not_dispatched_twice(client):
    first = _sos(client, phone='9000000001', latitude=13.100, longitude=80.200)
    again = _sos(client, phone='9000000001', latitude=13.300, longitude=80.300)        # same phone
    nearby = _sos(client, phone='9000000002', latitude=13.1004, longitude=80.2003)       # ~50 m away
    far = _sos(client, phone='9000000003', latitude=13.150, longitude=80.250)
    assert again['duplicate_of'] == first['reference_id']
    assert nearby['duplicate_of'] == first['reference_id']
    assert far['duplicate_of'] is None


def test_priority_ageing():
    from src.backend.app.services import triage
    base = {**SOS_BODY, 'people_injured': 0, 'vulnerabilities': {}, 'emergency_type': 'storm',
            'water_availability': 'adequate', 'food_availability': 'adequate', 'age': 30, 'people_to_rescue': 1}
    p0, s0, _ = triage.score(base)
    p1, s1, r1 = triage.score(base, waiting_min=31)
    assert s1 == s0 + 12 and 'waiting 31 min' in r1 and p1 <= p0
    assert triage.score(base, waiting_min=600)[1] == s0 + triage.AGEING_CAP


def _fill_all_teams(client, disp):
    """Occupy every team slot with low-priority assignments (not yet en route)."""
    teams = client.get('/api/v1/teams', headers=disp).json()
    refs = []
    for t in teams:
        for _ in range(t['capacity'] - t['current_load']):
            ref = _sos(client, phone=f'95{len(refs):08d}', latitude=12.5 + len(refs) * 0.01, longitude=79.5,
                       emergency_type='coastal-erosion', people_injured=0, vulnerabilities={},
                       water_availability='adequate', food_availability='adequate', age=30,
                       people_to_rescue=1)['reference_id']
            v = client.get(f'/api/v1/sos/{ref}', headers=disp).json()['version']
            assert client.post(f'/api/v1/sos/{ref}/assign', json={'team_id': t['id'], 'version': v},
                               headers=disp).status_code == 200
            refs.append(ref)
    return refs


def test_no_free_teams_urgent_first_suggestions_and_reallocation(client):
    from src.backend.app.services import sos
    disp = auth(client, 'dispatcher')
    sos.auto_triage(max_priority=2)                  # settle anything earlier tests left open
    donors = _fill_all_teams(client, disp)
    urgent = [_sos(client, phone=f'97{i:08d}', latitude=11.0 + i * 0.05, longitude=78.0, emergency_type='tsunami',
                   people_injured=2, people_to_rescue=4, vulnerabilities={'medical': True, 'elderly': True},
                   water_availability='none')['reference_id'] for i in range(2)]
    sos.auto_triage(max_priority=2)
    cap = client.get('/api/v1/dispatch/capacity', headers=disp).json()
    assert cap['status'] == 'exhausted' and cap['teams_free'] == 0
    assert {w['reference_id'] for w in cap['waiting']} >= set(urgent)
    for ref in urgent:
        d = client.get(f'/api/v1/sos/{ref}', headers=disp).json()
        assert d['awaiting_resources'] and d['status'] == 'pending' and d['priority'] == 1
    sug = next(x for x in cap['suggestions'] if x['for_reference_id'] == urgent[0])
    assert sug['from_reference_id'] in donors and sug['from_priority'] >= 3
    # the dispatcher accepts: one transaction moves the team
    tgt = client.get(f"/api/v1/sos/{urgent[0]}", headers=disp).json()
    src = client.get(f"/api/v1/sos/{sug['from_reference_id']}", headers=disp).json()
    r = client.post(f'/api/v1/sos/{urgent[0]}/reallocate', headers=disp, json={
        'team_id': sug['team_id'], 'from_reference_id': src['reference_id'], 'version': tgt['version'],
        'from_version': src['version']})
    assert r.status_code == 200 and r.json()['status'] == 'assigned' and not r.json()['awaiting_resources']
    back = client.get(f"/api/v1/sos/{src['reference_id']}", headers=disp).json()
    assert back['status'] == 'triaged' and back['assigned_team'] is None
    # replaying the same reallocation is refused (versions moved on)
    again = client.post(f'/api/v1/sos/{urgent[0]}/reallocate', headers=disp, json={
        'team_id': sug['team_id'], 'from_reference_id': src['reference_id'], 'version': tgt['version'],
        'from_version': src['version']})
    assert again.status_code == 409


def test_sms_parser_is_tolerant():
    from src.backend.app.services.sms import parse
    p = parse('SOS 13.0120,80.2410 P3 I1 Tflood elderly, water rising fast')
    assert (p['lat'], p['lng'], p['people'], p['injured'], p['type']) == (13.012, 80.241, 3, 1, 'flood')
    assert p['vulnerabilities'] == {'elderly': True} and 'water rising fast' in p['note']
    q = parse('sos p 2 i 5 storm near anna nagar depot, baby with fever')
    assert (q['lat'], q['people'], q['injured'], q['type']) == (None, 2, 2, 'storm')   # injured capped at people
    assert q['vulnerabilities'] == {'children': True}


def test_sms_webhook(client):
    from src.backend.app.api import routes
    body = {'from': '+919840012345', 'text': 'SOS 13.0300,80.2100 P2 I0 Tflood ground floor flooded', 'id': 'gw-1'}
    assert client.post('/api/v1/sms/inbound', json=body).status_code == 503              # off until configured
    object.__setattr__(routes._cfg, 'sms_secret', 's3cret')            # settings are frozen; restored below
    try:
        assert client.post('/api/v1/sms/inbound', json=body, headers={'X-SMS-Secret': 'nope'}).status_code == 401
        r = client.post('/api/v1/sms/inbound', json=body, headers={'X-SMS-Secret': 's3cret'})
        assert r.status_code == 200 and r.json()['reference_id'].startswith('SOS-')
        assert 'received' in r.json()['reply'] and len(r.json()['reply']) <= 300
        # gateways retry: the same message id does not create a second request
        r2 = client.post('/api/v1/sms/inbound', json=body, headers={'X-SMS-Secret': 's3cret'})
        assert r2.json()['reference_id'] == r.json()['reference_id']
        d = client.get(f"/api/v1/sos/{r.json()['reference_id']}", headers=auth(client, 'viewer')).json()
        assert d['source'] == 'sms' and d['age'] is None and d['latitude'] == 13.03
    finally:
        object.__setattr__(routes._cfg, 'sms_secret', '')


def test_lost_contact_while_not_stable_opens_alert(client):
    from src.backend.app.db import utcnow, write_tx
    from src.backend.app.models import Device
    from src.backend.app.services import telemetry
    key = client.post('/api/v1/devices', json={'device_id': 'W-SILENT'}, headers=auth(client, 'admin')).json()['api_key']
    v = {k: math.nan for k in FIELD_NAMES}
    v.update(imu_acc_std_g=0.2, imu_acc_max_g=1.2)
    client.post('/api/v1/telemetry', json=to_payload(v, [], device_id='W-SILENT', seq=1), headers={'X-Device-Key': key})
    with write_tx() as s:
        d = s.query(Device).filter_by(device_id='W-SILENT').one()
        d.state, d.alert_level, d.last_seen = 'CONCUSSIVE_STASIS', 'critical', utcnow() - timedelta(seconds=90)
    telemetry.mark_offline(30)
    alerts = client.get('/api/v1/alerts', params={'status': 'open'}, headers=auth(client, 'viewer')).json()
    a = next(a for a in alerts if a['device_id'] == 'W-SILENT' and a['state'] == 'LOST_CONTACT')
    assert 'in CONCUSSIVE_STASIS' in a['evidence'][0]


def test_lost_contact_skips_unknown_state(client):
    from src.backend.app.db import utcnow, write_tx
    from src.backend.app.models import Device
    from src.backend.app.services import telemetry
    client.post('/api/v1/devices', json={'device_id': 'W-NOML'}, headers=auth(client, 'admin'))
    with write_tx() as s:
        d = s.query(Device).filter_by(device_id='W-NOML').one()
        d.online, d.state, d.last_seen = True, 'UNKNOWN', utcnow() - timedelta(seconds=90)
    telemetry.mark_offline(30)
    alerts = client.get('/api/v1/alerts', params={'status': 'open'}, headers=auth(client, 'viewer')).json()
    assert not any(a['device_id'] == 'W-NOML' for a in alerts)


def test_real_rov_deadman_queues_stop(client):
    from src.backend.app.services import rov
    admin = auth(client, 'admin')
    unit = next(u for u in client.get('/api/v1/rov', headers=admin).json() if u['name'] == 'ROV-002')
    key = client.post(f"/api/v1/rov/{unit['id']}/bridge-key", json={}, headers=admin).json()['api_key']
    client.post(f"/api/v1/rov/{unit['id']}/reset", headers=admin)
    client.post(f"/api/v1/rov/{unit['id']}/takeover", headers=admin)
    client.post(f"/api/v1/rov/{unit['id']}/control", json={'command': 'forward', 'speed_pct': 60}, headers=admin)
    client.post('/api/v1/rov/bridge/telemetry', json={}, headers={'X-ROV-Key': key})       # drain the outbox
    rov._last_control[int(unit['id'])] -= rov.DEADMAN_S + 1                               # pilot went quiet
    rov.tick()
    lines = [l for c in client.post('/api/v1/rov/bridge/telemetry', json={}, headers={'X-ROV-Key': key}
                                    ).json()['commands'] for l in c['lines']]
    assert lines == ['forward_0', 'up_0']


def test_bridge_stops_rov_when_control_room_unreachable(monkeypatch):
    """The station bridge cuts thrust by itself after LINK_LOSS_STOP_S without server contact."""
    import httpx
    from src.rov import bridge

    class FakeSerial:
        def __init__(self, *a, **k):
            self.written, self.reads = [], 0

        def readline(self):
            self.reads += 1
            if self.reads > 400:
                raise KeyboardInterrupt
            return b''

        def write(self, b):
            self.written.append(b.decode().strip())

    fake = FakeSerial()
    import sys, types
    monkeypatch.setitem(sys.modules, 'serial', types.SimpleNamespace(Serial=lambda *a, **k: fake))
    clock = iter(range(0, 10_000))
    monkeypatch.setattr(bridge.time, 'monotonic', lambda: float(next(clock)) * 0.05)

    def down(*a, **k):
        raise httpx.ConnectError('no route')
    monkeypatch.setattr(httpx.Client, 'post', down)
    with pytest.raises(KeyboardInterrupt):
        bridge.run('COM9', 'http://x', 'k', period_s=1.0)
    assert fake.written == ['forward_0', 'up_0']                 # once, not every retry


def _frame_with_sos(device_id, seq, sos, **values):
    v = {k: math.nan for k in FIELD_NAMES}
    v.update(imu_acc_std_g=0.2, imu_acc_max_g=1.2, gps_lat=13.0405, gps_lng=80.2337, **values)
    p = to_payload(v, [], device_id=device_id, seq=seq)
    p.update(boot_id=3, sos=sos)
    return p


def test_wearable_sos_button_creates_one_request_and_alert(client):
    admin, viewer = auth(client, 'admin'), auth(client, 'viewer')
    key = {'X-Device-Key': client.post('/api/v1/devices', json={'device_id': 'W-BTN', 'label': 'Kavya (band 7)'},
                                       headers=admin).json()['api_key']}
    acks = []
    for seq in (1, 2, 3):                 # the band repeats the group in every frame until acknowledged
        r = client.post('/api/v1/telemetry', headers=key, json=_frame_with_sos(
            'W-BTN', seq, {'active': True, 'press_id': 41, 'pressed_uptime_ms': 1000}, water_wet=1.0)).json()
        acks.append(r['sos'])
    ref = acks[0]['reference_id']
    assert all(a == {'received': True, 'reference_id': ref, 'press_id': 41, 'cancelled': False} for a in acks)
    d = client.get(f'/api/v1/sos/{ref}', headers=viewer).json()
    assert d['source'] == 'wearable' and d['device_id'] == 'W-BTN' and d['emergency_type'] == 'flood'
    assert d['latitude'] == 13.0405 and 'SOS button pressed on wearable' in d['priority_reasons']
    alerts = [a for a in client.get('/api/v1/alerts', headers=viewer).json() if a['device_id'] == 'W-BTN']
    assert [a['state'] for a in alerts] == ['SOS_BUTTON'] and alerts[0]['sos_reference_id'] == ref
    # cancel from the band: note + alert resolved, request kept for a dispatcher
    r = client.post('/api/v1/telemetry', headers=key, json=_frame_with_sos(
        'W-BTN', 4, {'active': False, 'press_id': 41, 'cancelled': True})).json()
    assert r['sos']['cancelled'] is True
    client.post('/api/v1/telemetry', headers=key, json=_frame_with_sos(
        'W-BTN', 5, {'active': False, 'press_id': 41, 'cancelled': True}))
    d = client.get(f'/api/v1/sos/{ref}', headers=viewer).json()
    assert d['status'] == 'pending' and sum('cancelled the SOS' in n['text'] for n in d['notes']) == 1
    alert = next(a for a in client.get('/api/v1/alerts', headers=viewer).json() if a['device_id'] == 'W-BTN')
    assert alert['status'] == 'resolved'


def test_extreme_case_reallocates_automatically_only_when_everything_agrees(client):
    from src.backend.app.db import utcnow, write_tx
    from src.backend.app.models import Device, DeviceState
    from src.backend.app.services import sos
    disp = auth(client, 'dispatcher')
    sos.auto_triage(max_priority=2)
    _fill_all_teams(client, disp)                               # every team busy (P4/P5 work, possibly from earlier tests)
    key = {'X-Device-Key': client.post('/api/v1/devices', json={'device_id': 'W-EXT'},
                                       headers=auth(client, 'admin')).json()['api_key']}
    client.post('/api/v1/telemetry', headers=key, json=_frame_with_sos('W-EXT', 1, None) | {'sos': None})
    body = dict(phone='9811111111', latitude=10.5, longitude=77.5, device_id='W-EXT', emergency_type='other',
                people_injured=1, people_to_rescue=2, vulnerabilities={'medical': True, 'elderly': True},
                water_availability='none')
    ref = _sos(client, **body)['reference_id']
    client.post(f'/api/v1/sos/{ref}/link-device', json={'device_id': 'W-EXT'}, headers=disp)

    def set_device(state, risk, held_s):
        with write_tx() as s:
            d = s.query(Device).filter_by(device_id='W-EXT').one()
            d.state, d.alert_level, d.last_summary = state, 'critical', {**(d.last_summary or {}), 'risk': risk}
            s.add(DeviceState(device_id='W-EXT', state=state, alert_level='critical', risk=risk, evidence=[],
                              created_at=utcnow() - timedelta(seconds=held_s)))

    # critical wearable, but no environmental corroboration ('other' emergency, no hazards): suggestion only
    set_device('ASPIRATION_HYPOXIA', 0.95, 120)
    sos.auto_triage(max_priority=2)
    d = client.get(f'/api/v1/sos/{ref}', headers=disp).json()
    assert d['priority'] == 1 and d['status'] == 'pending' and d['awaiting_resources']
    # flood confirmed, but the state is a transient (10 s): still no automatic move
    with write_tx() as s:
        from src.backend.app.models import SOSRequest
        s.query(SOSRequest).filter_by(reference_id=ref).one().emergency_type = 'flood'
        s.query(DeviceState).filter_by(device_id='W-EXT').delete()
    set_device('ASPIRATION_HYPOXIA', 0.95, 10)
    sos.auto_triage(max_priority=2)
    assert client.get(f'/api/v1/sos/{ref}', headers=disp).json()['status'] == 'pending'
    # sustained critical state + water disaster + P1 >= 80: the team moves without confirmation
    with write_tx() as s:
        s.query(DeviceState).filter_by(device_id='W-EXT').delete()
    set_device('ASPIRATION_HYPOXIA', 0.95, 120)
    sos.auto_triage(max_priority=2)
    d = client.get(f'/api/v1/sos/{ref}', headers=disp).json()
    assert d['status'] == 'assigned' and not d['awaiting_resources']
    moved = next(e for e in d['assignments'] if 'extreme case' in e['text'])
    donor_ref = moved['text'].split('from ')[1].split(' ')[0]
    donor = client.get(f'/api/v1/sos/{donor_ref}', headers=disp).json()
    assert donor['status'] == 'triaged' and donor['priority'] >= 4


# ── security QA regressions ───────────────────────────────────────────────

def test_public_idempotency_keys_cannot_hijack_sms_or_wearable_requests(client):
    from src.backend.app.api import routes
    _sos(client, phone='9333333333', latitude=11.9, longitude=79.8)            # unrelated noise
    r = client.post('/api/v1/sos', json={**SOS_BODY, 'phone': '9444444444', 'latitude': 12.0, 'longitude': 79.0},
                    headers={'Idempotency-Key': 'sms:GW-1001'})
    attacker_ref = r.json()['reference_id']
    object.__setattr__(routes._cfg, 'sms_secret', 's3cret')
    try:
        real = client.post('/api/v1/sms/inbound', json={'from': '+919811122233', 'text': 'SOS P2 Tflood', 'id': 'GW-1001'},
                           headers={'X-SMS-Secret': 's3cret'}).json()
    finally:
        object.__setattr__(routes._cfg, 'sms_secret', '')
    assert real['reference_id'] != attacker_ref                   # the real SMS still creates its own request


def test_public_device_claim_is_not_trusted(client):
    ref = _sos(client, phone='9555555555', latitude=11.5, longitude=79.5, device_id='W-FALL')['reference_id']
    d = client.get(f'/api/v1/sos/{ref}', headers=auth(client, 'viewer')).json()
    assert d['device_id'] == 'W-FALL' and d['device_verified'] is False
    assert not any(r.startswith('wearable:') for r in d['priority_reasons'])
    assert client.post(f'/api/v1/sos/{ref}/link-device', json={'device_id': 'W-FALL'},
                       headers=auth(client, 'viewer')).status_code == 403


def test_bad_since_is_422_and_timeseries_is_bounded(client):
    h = auth(client, 'viewer')
    assert client.get('/api/v1/sos', params={'since': 'not-a-date'}, headers=h).status_code == 422
    r = client.get('/api/v1/analytics/timeseries', params={'metric': 'sos_created', 'bucket': 'hour',
                                                          'since': '0001-01-01T00:00:00Z'}, headers=h)
    assert r.status_code == 200 and len(r.json()['points']) <= 31 * 24 + 2


def test_body_size_limit_and_api_no_store(client):
    big = {**SOS_BODY, 'additional_info': 'x' * 400_000}
    r = client.post('/api/v1/sos', json=big)
    assert r.status_code == 413 and r.json()['error']['code'] == 'too_large'
    r = client.get('/api/v1/public/summary')
    assert r.headers['Cache-Control'] == 'no-store'
    r = client.get('/healthz', headers={'X-Request-ID': '<script>'})
    assert r.headers['X-Request-ID'] != '<script>'


def test_oversized_numbers_do_not_500(client):
    key = {'X-Device-Key': client.post('/api/v1/devices', json={'device_id': 'W-BIG'},
                                       headers=auth(client, 'admin')).json()['api_key']}
    p = _frame_with_sos('W-BIG', 2 ** 70, None) | {'sos': None, 'boot_id': 'b' * 100}
    r = client.post('/api/v1/telemetry', headers=key, json={'frames': [p], 'acks': ['9' * 30]})
    assert r.status_code == 200 and r.json()['accepted'] == 0
    assert client.get('/api/v1/sos', params={'cursor': 'OTk5OTk5OTk5OTk5OTk5OTk5OTk5'},
                      headers=auth(client, 'viewer')).status_code == 200


def test_websocket_closes_when_user_is_deactivated(client):
    admin = auth(client, 'admin')
    u = client.post('/api/v1/users', json={'username': 'ws-temp', 'display_name': 'WS', 'password': 'temporary-pass-1',
                                           'role': 'viewer'}, headers=admin).json()
    tok = client.post('/api/v1/auth/login', json={'username': 'ws-temp', 'password': 'temporary-pass-1'}).json()['access_token']
    from starlette.websockets import WebSocketDisconnect
    with client.websocket_connect(f'/ws?token={tok}') as ws:
        assert ws.receive_json()['type'] == 'hello'
        client.patch(f"/api/v1/users/{u['id']}", json={'is_active': False}, headers=admin)
        with pytest.raises(WebSocketDisconnect):
            for _ in range(50):
                ws.receive_json()


def test_websocket_rejects_foreign_origin(client):
    tok = client.post('/api/v1/auth/login', json={'username': 'viewer', 'password': 'trident-demo-2026'}).json()['access_token']
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f'/ws?token={tok}', headers={'origin': 'https://evil.example'}) as ws:
            ws.receive_json()


# ── load / failure QA regressions ─────────────────────────────────────────

def test_idempotent_retry_gets_its_answer_even_when_rate_limited(client):
    from src.backend.app.api import routes
    from src.backend.app.ratelimit import TokenBucket
    first = client.post('/api/v1/sos', json={**SOS_BODY, 'phone': '9666666666', 'latitude': 10.1, 'longitude': 76.1},
                        headers={'Idempotency-Key': 'phone-outbox-1'}).json()
    saved = routes.SOS_BUCKET
    routes.SOS_BUCKET = TokenBucket(1, burst=1)
    try:
        routes.SOS_BUCKET.take('sos:testclient')                       # bucket now empty for this client
        again = client.post('/api/v1/sos', json={**SOS_BODY, 'phone': '9666666666'},
                            headers={'Idempotency-Key': 'phone-outbox-1'})
        assert again.status_code in (200, 201) and again.json()['reference_id'] == first['reference_id']
        fresh = client.post('/api/v1/sos', json={**SOS_BODY, 'phone': '9777777777'})
        assert fresh.status_code == 429
    finally:
        routes.SOS_BUCKET = saved


def test_malformed_frames_are_rejected_individually(client):
    key = {'X-Device-Key': client.post('/api/v1/devices', json={'device_id': 'W-MAL'},
                                       headers=auth(client, 'admin')).json()['api_key']}
    good = _frame_with_sos('W-MAL', 7, None) | {'sos': None}
    bad = [{'schema': 2, 'seq': 1, 'ppg': 5}, {'schema': 2, 'seq': 2, 'imu': 'x', 'gps': [1, 2]}, 'not a frame',
           {'schema': 2, 'seq': 3, 'sos': {'press_id': -1, 'active': 'maybe'}}]
    r = client.post('/api/v1/telemetry', headers=key, json={'frames': bad + [good], 'acks': 5})
    assert r.status_code == 200
    body = r.json()
    assert body['accepted'] == 4 and body['rejected'] == 1 and 'sos' not in body     # bad groups -> unavailable values
    viewer = auth(client, 'viewer')
    assert not [s for s in client.get('/api/v1/sos', headers=viewer).json()['items'] if s['device_id'] == 'W-MAL']


def test_database_busy_is_503_with_retry_after(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from src.backend.app.services import sos

    def locked(*a, **k):
        raise OperationalError('INSERT', {}, Exception('database is locked'))
    monkeypatch.setattr(sos, 'create', locked)
    r = client.post('/api/v1/sos', json={**SOS_BODY, 'phone': '9888888888'})
    assert r.status_code == 503 and r.headers['Retry-After'] and r.json()['error']['code'] == 'unavailable'


def test_unexpected_error_is_one_clean_500(client, monkeypatch):
    from src.backend.app.services import analytics

    def boom():
        raise RuntimeError('bug')
    monkeypatch.setattr(analytics, 'summary', boom)
    r = client.get('/api/v1/public/summary')
    assert r.status_code == 500 and r.json()['error']['code'] == 'internal_error' and r.json()['request_id']


def test_readyz_reports_write_lock(client):
    import sqlite3
    from src.backend.app.config import get_settings
    assert client.get('/readyz').json()['checks']['database']['writable'] is True
    path = get_settings().database_url.split('sqlite:///', 1)[-1]
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute('BEGIN IMMEDIATE')
    try:
        r = client.get('/readyz')
        assert r.status_code == 503 and r.json()['checks']['database']['writable'] is False
    finally:
        holder.execute('ROLLBACK')
        holder.close()
    assert client.get('/readyz').status_code == 200


def test_failed_job_is_retried_not_marked_done(client):
    from src.backend.app.db import write_tx
    from src.backend.app.jobs import HOLDER, _acquire, _record, lease_ttl
    from src.backend.app.models import SchedulerLease
    assert _acquire('flaky-job', 30)
    _record('flaky-job', 'ok: first')
    with write_tx() as s:
        done = s.get(SchedulerLease, 'flaky-job').last_run_at
    _record('flaky-job', 'error: ConnectError', success=False)
    with write_tx() as s:
        lease = s.get(SchedulerLease, 'flaky-job')
        assert lease.last_run_at == done and lease.last_status.startswith('error') and lease.holder == HOLDER
    assert lease_ttl(1) == 10 and lease_ttl(3600) == 60


def test_log_redaction():
    import logging
    from src.backend.app.observability import RedactSecrets
    rec = logging.LogRecord('uvicorn.error', logging.INFO, '', 0, '"WebSocket /ws?token=%s" [accepted]', ('eyJabc.def',), None)
    RedactSecrets().filter(rec)
    assert 'eyJabc' not in rec.getMessage() and 'token=***' in rec.getMessage()
