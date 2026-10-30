"""Device auth, idempotent ingest, the command outbox, real-data fusion -> alert, WebSocket events,
and scheduler leases."""

import math

import pandas as pd
import pytest

from src.ml.wearable import paths
from src.ml.wearable.schema import FIELD_NAMES, to_payload

from .conftest import SOS_BODY, auth


def _register(client, device_id):
    r = client.post('/api/v1/devices', json={'device_id': device_id, 'label': 'test'}, headers=auth(client, 'admin'))
    assert r.status_code == 201
    return {'X-Device-Key': r.json()['api_key']}


def _frame(seq, device_id='W-T1', **values):
    v = {k: math.nan for k in FIELD_NAMES}
    v.update({'imu_acc_std_g': 0.2, 'imu_acc_max_g': 1.3, 'imu_acc_mean_g': 1.0, 'ppg_finger_on': 1.0,
              'ppg_bpm': 74.0, 'power_batt_v': 3.9}, **values)
    p = to_payload(v, [810.0], device_id=device_id, seq=seq)
    p['boot_id'] = 7
    return p


def test_device_auth_dedup_and_commands(client):
    key = _register(client, 'W-T1')
    assert client.post('/api/v1/telemetry', json=_frame(1)).status_code == 401
    assert client.post('/api/v1/telemetry', json=_frame(1), headers={'X-Device-Key': 'tdk_wrong'}).status_code == 401
    r = client.post('/api/v1/telemetry', json={'frames': [_frame(1), _frame(2), _frame(3)]}, headers=key)
    assert r.status_code == 200 and r.json()['accepted'] == 3
    r = client.post('/api/v1/telemetry', json={'frames': [_frame(2), _frame(3), _frame(4)]}, headers=key)
    assert (r.json()['accepted'], r.json()['duplicates']) == (1, 2)
    disp = auth(client, 'dispatcher')
    cmd = client.post('/api/v1/devices/W-T1/commands', json={'action': 'buzz', 'params': {'ms': 300}}, headers=disp)
    assert cmd.status_code == 201
    r = client.post('/api/v1/telemetry', json=_frame(5), headers=key).json()
    assert [c['action'] for c in r['commands']] == ['buzz']
    client.post('/api/v1/telemetry', json={'frames': [_frame(6)], 'acks': [r['commands'][0]['id']]}, headers=key)
    statuses = [c['status'] for c in client.get('/api/v1/devices/W-T1/commands', headers=disp).json()]
    assert statuses == ['acked']
    dev = next(d for d in client.get('/api/v1/devices', headers=disp).json() if d['device_id'] == 'W-T1')
    assert dev['online'] and dev['boot_id'] == '7' and dev['vitals']['bpm'] == 74.0


def test_bad_command_params_rejected(client):
    r = client.post('/api/v1/devices/W-T1/commands', json={'action': 'set_geofence', 'params': {'lat': 13}},
                    headers=auth(client, 'dispatcher'))
    assert r.status_code == 422


@pytest.mark.skipif(not (paths.FRAMES_DIR / 'hifd.parquet').exists(), reason='HIFD frames not built')
def test_real_fall_then_stillness_opens_alert_and_raises_linked_sos(client):
    """A recorded HIFD fall followed by lying still goes through the full serving path."""
    key = _register(client, 'W-FALL')
    ref = client.post('/api/v1/sos', json={**SOS_BODY, 'device_id': 'W-FALL', 'people_injured': 0,
                                           'vulnerabilities': {}}).json()['reference_id']
    # a wearable named on the public form is only a claim until a dispatcher confirms the link
    assert client.post(f'/api/v1/sos/{ref}/link-device', json={'device_id': 'W-FALL'},
                       headers=auth(client, 'dispatcher')).json()['device_verified']
    hifd = pd.read_parquet(paths.FRAMES_DIR / 'hifd.parquet')
    # a fixed trial the P5 replay shows reaching CONCUSSIVE_STASIS (fall p 0.80): this test checks the
    # serving path end to end, not detection accuracy (that is docs/reports/WEARABLE_FUSION_REPLAY.md)
    rec = hifd[(hifd['subject'] == 'subject_01') & (hifd['trial'] == 'fall__fall3')].sort_values('frame')
    rec = rec.reset_index(drop=True)
    assert len(rec)
    still = pd.concat([rec.iloc[[-1]]] * 40, ignore_index=True)
    frames = pd.concat([rec, still], ignore_index=True)
    payloads = []
    for i, row in frames.iterrows():
        values = {k: (float(row[k]) if pd.notna(row[k]) else math.nan) for k in FIELD_NAMES}
        p = to_payload(values, list(row['rr_ms']), device_id='W-FALL', seq=i + 1)
        p['uptime_ms'] = int(i * 1500)
        payloads.append(p)
    for i in range(0, len(payloads), 50):
        r = client.post('/api/v1/telemetry', json={'frames': payloads[i:i + 50]}, headers=key)
        assert r.status_code == 200
    disp = auth(client, 'dispatcher')
    states = [s['state'] for s in client.get('/api/v1/devices/W-FALL/states', headers=disp).json()]
    assert 'CONCUSSIVE_STASIS' in states
    alerts = client.get('/api/v1/alerts', params={'status': 'open'}, headers=disp).json()
    alert = next(a for a in alerts if a['device_id'] == 'W-FALL')
    linked = client.get(f'/api/v1/sos/{ref}', headers=disp).json()['linked_device']
    assert linked['device_id'] == 'W-FALL' and 'vitals' in linked and 'state' in linked      # GET /devices shape
    assert alert['state'] == 'CONCUSSIVE_STASIS' and alert['sos_reference_id'] == ref
    assert client.post(f"/api/v1/alerts/{alert['id']}/ack", headers=disp).json()['status'] == 'acked'
    # re-triage picks up the measured state of the linked wearable
    from src.backend.app.services import sos
    sos.auto_triage(max_priority=0)                          # re-score only, no auto-dispatch
    detail = client.get(f'/api/v1/sos/{ref}', headers=disp).json()
    assert any('wearable: CONCUSSIVE_STASIS' in r for r in detail['priority_reasons'])


def test_websocket_receives_sos_events(client):
    token = client.post('/api/v1/auth/login', json={'username': 'viewer', 'password': 'trident-demo-2026'}
                        ).json()['access_token']
    with client.websocket_connect(f'/ws?token={token}') as ws:
        assert ws.receive_json()['type'] == 'hello'
        ws.send_json({'type': 'subscribe', 'topics': ['sos']})
        ws.send_json({'type': 'ping'})
        assert ws.receive_json()['type'] == 'pong'
        client.post('/api/v1/sos', json=SOS_BODY)
        msg = ws.receive_json()
        assert msg['topic'] == 'sos' and msg['data']['event'] == 'created' and msg['seq'] >= 1


def test_websocket_rejects_bad_token(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/ws?token=bad') as ws:
            ws.receive_json()


def test_scheduler_lease_is_exclusive(client):
    from datetime import timedelta
    from src.backend.app.db import utcnow, write_tx
    from src.backend.app.jobs import _acquire
    from src.backend.app.models import SchedulerLease
    assert _acquire('unit-test-job', 30)
    assert _acquire('unit-test-job', 30)                      # renewing our own lease
    with write_tx() as s:
        s.get(SchedulerLease, 'unit-test-job').holder = 'other-replica:1'
    assert not _acquire('unit-test-job', 30)                  # held elsewhere and not expired
    with write_tx() as s:
        s.get(SchedulerLease, 'unit-test-job').expires_at = utcnow() - timedelta(seconds=1)
    assert _acquire('unit-test-job', 30)                      # expired: taken over
    # due-ness is shared: a job that ran 5 s ago on another replica is not re-run early
    with write_tx() as s:
        s.get(SchedulerLease, 'unit-test-job').last_run_at = utcnow() - timedelta(seconds=5)
    assert not _acquire('unit-test-job', 30, every_s=60)
    assert _acquire('unit-test-job', 30, every_s=4)


def test_health_ready_metrics(client):
    assert client.get('/healthz').json()['status'] == 'ok'
    ready = client.get('/readyz').json()
    assert ready['ready'] and ready['checks']['database']['ok']
    assert 'http_requests_total' in client.get('/metrics').text
