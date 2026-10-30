"""ROV camera relay: vision key, frame ingest (validated, bounded), stream tickets, MJPEG stream,
summary on the ROV record. No CV libraries needed here (the worker is tested in tests/ml/test_vision_pipeline.py)."""

import base64
import io

from .conftest import auth


def _jpeg(color=(30, 60, 90)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (64, 48), color).save(buf, format='JPEG')
    return buf.getvalue()


def _unit(client, h, name='ROV-001'):
    return next(u for u in client.get('/api/v1/rov', headers=h).json() if u['name'] == name)


def test_vision_ingest_ticket_and_stream(client):
    admin, viewer = auth(client, 'admin'), auth(client, 'viewer')
    unit = _unit(client, viewer)
    assert unit['vision'] == {'active': False}
    assert client.post(f"/api/v1/rov/{unit['id']}/vision-key", headers=viewer).status_code == 403
    key = client.post(f"/api/v1/rov/{unit['id']}/vision-key", headers=admin).json()['api_key']
    frame = {'jpeg_b64': base64.b64encode(_jpeg()).decode(), 'detections': {
        'persons': 2, 'model': 'yolov8n + lbph',
        'objects': [{'label': 'person', 'confidence': 0.91, 'distance_m': 3.2, 'box': [1, 2, 30, 40]},
                    {'label': 'boat', 'confidence': 2.5, 'distance_m': -4, 'box': 'x'}],      # out of range values
        'faces': [{'name': '<img src=x onerror=alert(1)>' * 3, 'match': 0.7, 'distance_m': 1.1}],
        'extra': 'dropped'}}
    assert client.post('/api/v1/rov/vision/frame', json=frame, headers={'X-ROV-Vision-Key': 'nope'}).status_code == 401
    assert client.post('/api/v1/rov/vision/frame', json={**frame, 'jpeg_b64': base64.b64encode(b'not a jpeg').decode()},
                       headers={'X-ROV-Vision-Key': key}).status_code == 413
    r = client.post('/api/v1/rov/vision/frame', json=frame, headers={'X-ROV-Vision-Key': key})
    assert r.status_code == 200
    v = client.get(f"/api/v1/rov/{unit['id']}/vision", headers=viewer).json()
    assert v['active'] and v['persons'] == 2 and v['model'] == 'yolov8n + lbph'
    boat = v['objects'][1]
    assert boat['confidence'] is None and boat['distance_m'] is None and boat['box'] is None
    assert len(v['faces'][0]['name']) <= 64 and 'extra' not in v
    assert _unit(client, viewer)['vision']['active']
    # the stream needs a fresh single-use ticket, never the access token
    assert client.get(f"/api/v1/rov/{unit['id']}/vision/stream", params={'ticket': 'x' * 20}).status_code == 401
    t = client.post(f"/api/v1/rov/{unit['id']}/vision/ticket", headers=viewer).json()
    assert t['url'].endswith(t['ticket'])
    from src.backend.app.services.vision import VISION
    VISION.stream_idle_end_s = 1.0                      # the stream ends once the feed goes quiet
    with client.stream('GET', t['url']) as resp:
        assert resp.status_code == 200 and resp.headers['content-type'].startswith('multipart/x-mixed-replace')
        first = next(resp.iter_bytes())
        assert b'Content-Type: image/jpeg' in first and b'\xff\xd8' in first
    assert client.get(t['url']).status_code == 401                      # single use
    # another unit's ticket does not open this unit's stream
    other = _unit(client, viewer, 'ROV-002')
    t2 = client.post(f"/api/v1/rov/{other['id']}/vision/ticket", headers=viewer).json()['ticket']
    assert client.get(f"/api/v1/rov/{unit['id']}/vision/stream", params={'ticket': t2}).status_code == 401
