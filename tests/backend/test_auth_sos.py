"""Auth (JWT, rotation, reuse detection, RBAC) and the SOS lifecycle (idempotency, state machine,
optimistic locking, team capacity)."""

from .conftest import SOS_BODY, auth, login


def test_login_refresh_rotation_and_reuse_detection(client):
    tokens = login(client, 'dispatcher')
    assert client.post('/api/v1/auth/login', json={'username': 'dispatcher', 'password': 'nope'}).status_code == 401
    r = client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    assert r.status_code == 200
    new = r.json()
    # replaying the rotated token revokes the whole family, including the new token
    r = client.post('/api/v1/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    assert r.status_code == 401 and r.json()['error']['code'] == 'session_revoked'
    assert client.post('/api/v1/auth/refresh', json={'refresh_token': new['refresh_token']}).status_code == 401


def test_errors_use_one_envelope_with_request_id(client):
    r = client.get('/api/v1/sos')
    assert r.status_code == 401
    body = r.json()
    assert body['error']['code'] == 'unauthorized' and body['request_id'] == r.headers['X-Request-ID']
    assert r.headers['X-Content-Type-Options'] == 'nosniff'


def test_sos_intake_is_idempotent_and_trackable(client):
    r1 = client.post('/api/v1/sos', json=SOS_BODY, headers={'Idempotency-Key': 'k-1'})
    r2 = client.post('/api/v1/sos', json=SOS_BODY, headers={'Idempotency-Key': 'k-1'})
    assert r1.status_code == 201 and r1.json() == r2.json()
    ref, token = r1.json()['reference_id'], r1.json()['tracking_token']
    t = client.get(f'/api/v1/sos/track/{ref}', params={'token': token})
    assert t.status_code == 200 and t.json()['status'] == 'pending'
    assert client.get(f'/api/v1/sos/track/{ref}', params={'token': 'x' * 20}).status_code == 404
    assert r1.json()['priority'] <= 2                       # P1 = most urgent; flood + injured elderly, medical need


def test_sos_validation(client):
    bad = {**SOS_BODY, 'people_injured': 9}
    r = client.post('/api/v1/sos', json=bad)
    assert r.status_code == 422 and r.json()['error']['code'] == 'validation_error'


def test_state_machine_version_conflict_and_capacity(client):
    disp = auth(client, 'dispatcher')
    ref = client.post('/api/v1/sos', json={**SOS_BODY, 'people_injured': 0, 'vulnerabilities': {},
                                           'emergency_type': 'coastal-erosion'}).json()['reference_id']
    sos = client.get(f'/api/v1/sos/{ref}', headers=disp).json()
    v = sos['version']
    # illegal transition
    r = client.patch(f'/api/v1/sos/{ref}/status', json={'status': 'resolved', 'version': v}, headers=disp)
    assert r.status_code == 409 and 'allowed' in r.json()['error']['details']
    r = client.patch(f'/api/v1/sos/{ref}/status', json={'status': 'triaged', 'version': v}, headers=disp)
    assert r.status_code == 200 and r.json()['version'] == v + 1
    # a stale version is rejected with the current record attached
    r = client.patch(f'/api/v1/sos/{ref}/status', json={'status': 'cancelled', 'version': v}, headers=disp)
    assert r.status_code == 409 and r.json()['error']['details']['current']['status'] == 'triaged'
    teams = client.get('/api/v1/teams', headers=disp).json()
    beta = next(t for t in teams if t['name'] == 'Chennai ROV Beta')
    r = client.post(f'/api/v1/sos/{ref}/assign', json={'team_id': beta['id'], 'version': v + 1}, headers=disp)
    assert r.status_code == 200 and r.json()['status'] == 'assigned'
    load = next(t for t in client.get('/api/v1/teams', headers=disp).json() if t['id'] == beta['id'])['current_load']
    assert load == beta['current_load'] + 1
    # finishing the mission frees the team slot
    cur = r.json()['version']
    for status in ('en_route', 'on_scene', 'resolved'):
        r = client.patch(f'/api/v1/sos/{ref}/status', json={'status': status, 'version': cur}, headers=disp)
        assert r.status_code == 200, r.text
        cur = r.json()['version']
    after = next(t for t in client.get('/api/v1/teams', headers=disp).json() if t['id'] == beta['id'])
    assert after['current_load'] == beta['current_load']
    # the timeline shows the assignment, and assignment rows carry who and when
    d = client.get(f'/api/v1/sos/{ref}', headers=disp).json()
    assert 'assigned' in [h['status'] for h in d['history']]
    a = d['assignments'][0]
    assert a['team_name'] == 'Chennai ROV Beta' and a['assigned_by'] == 'dispatcher' and a['assigned_at']


def test_rbac(client):
    viewer = auth(client, 'viewer')
    ref = client.post('/api/v1/sos', json=SOS_BODY).json()['reference_id']
    assert client.get(f'/api/v1/sos/{ref}', headers=viewer).status_code == 200
    r = client.post(f'/api/v1/sos/{ref}/assign', json={'team_id': 1, 'version': 1}, headers=viewer)
    assert r.status_code == 403
    assert client.get('/api/v1/users', headers=auth(client, 'dispatcher')).status_code == 403
    # responders may only move requests assigned to their own team
    resp = auth(client, 'responder')
    r = client.patch(f'/api/v1/sos/{ref}/status', json={'status': 'triaged', 'version': 1}, headers=resp)
    assert r.status_code == 403


def test_public_summary_and_contacts(client):
    s = client.get('/api/v1/public/summary').json()
    assert {'teams_available', 'sos_open', 'weather', 'updated_at'} <= set(s)
    assert len(client.get('/api/v1/contacts').json()) >= 3


def test_weather_unavailable_is_503(client):
    r = client.get('/api/v1/weather/forecast', headers=auth(client, 'viewer'))
    assert r.status_code == 503 and r.json()['error']['code'] == 'unavailable'


def test_token_bucket_limits_bursts():
    from src.backend.app.ratelimit import TokenBucket
    b = TokenBucket(per_minute=6, burst=3)
    assert [b.take('ip') == 0 for _ in range(4)] == [True, True, True, False]
    assert b.take('other-ip') == 0                      # buckets are per client
    assert 9 < b.take('ip') <= 10                       # ~10 s until the next token at 6/min


def test_age_and_pincode_are_optional_for_people_in_distress(client):
    body = {k: v for k, v in SOS_BODY.items() if k not in ('age', 'pincode')}
    r = client.post('/api/v1/sos', json={**body, 'phone': '9012345678', 'latitude': 9.9, 'longitude': 78.1})
    assert r.status_code == 201
    d = client.get(f"/api/v1/sos/{r.json()['reference_id']}", headers=auth(client, 'viewer')).json()
    assert d['age'] is None and d['pincode'] is None
    assert client.post('/api/v1/sos', json={**body, 'pincode': '12'}).status_code == 422      # given but too short
    assert client.post('/api/v1/sos', json={**body, 'age': 130}).status_code == 422
