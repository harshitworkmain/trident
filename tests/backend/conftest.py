"""Each test module gets a fresh SQLite database and app instance; the scheduler and weather are off."""

import os
import tempfile
from pathlib import Path

import pytest

DEMO_PASSWORD = 'trident-demo-2026'


@pytest.fixture(scope='module')
def client():
    tmp = Path(tempfile.mkdtemp(prefix='trident-test-'))
    os.environ.update({'TRIDENT_ENV': 'test', 'TRIDENT_RUN_SCHEDULER': 'false', 'TRIDENT_WEATHER_ENABLED': 'false',
                       'TRIDENT_SOS_RATE_PER_MIN': '100000', 'TRIDENT_LOGIN_RATE_PER_MIN': '100000',
                       'TRIDENT_SMS_SECRET': '',          # tests must not depend on a developer's .env
                       'TRIDENT_DATABASE_URL': f"sqlite:///{(tmp / 'test.db').as_posix()}"})
    from src.backend.app import config, db
    config.get_settings.cache_clear()
    db.reset_engine()
    from fastapi.testclient import TestClient
    from src.backend.app.main import create_app
    with TestClient(create_app()) as c:
        yield c
    db.reset_engine()


def login(client, username):
    r = client.post('/api/v1/auth/login', json={'username': username, 'password': DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def auth(client, username):
    return {'Authorization': 'Bearer ' + login(client, username)['access_token']}


SOS_BODY = {'name': 'Ravi Kumar', 'age': 72, 'phone': '9876500000', 'address': '12 Canal Road, Kotturpuram',
            'city': 'Chennai', 'pincode': '600085', 'people_to_rescue': 3, 'people_injured': 1,
            'food_availability': 'limited', 'water_availability': 'critical',
            'vulnerabilities': {'elderly': True, 'medical': True}, 'emergency_type': 'flood',
            'latitude': 13.0120, 'longitude': 80.2410}
