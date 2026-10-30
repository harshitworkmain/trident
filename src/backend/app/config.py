"""Runtime settings, read once from the environment (TRIDENT_* variables, optional .env file)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv() -> None:
    env = PROJECT_ROOT / '.env'
    if not env.exists():
        return
    for line in env.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _list(name: str, default: str) -> List[str]:
    return [x.strip() for x in os.environ.get(name, default).split(',') if x.strip()]


@dataclass(frozen=True)
class Settings:
    env: str = 'development'                      # development | test | production
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'databases' / 'trident.db').as_posix()}"
    jwt_secret: str = ''
    access_ttl_s: int = 15 * 60
    refresh_ttl_s: int = 7 * 24 * 3600
    cors_origins: List[str] = field(default_factory=list)
    seed_demo_users: bool = True                  # dev only: admin/dispatcher/responder/viewer
    admin_password: str = ''
    run_scheduler: bool = True
    ml_enabled: bool = True
    weather_enabled: bool = True
    web_dist: Path = PROJECT_ROOT / 'src' / 'frontend' / 'web' / 'dist'
    sos_rate_per_min: int = 20                    # public SOS per IP (shelter Wi-Fi / CGNAT share one IP)
    sos_burst: int = 10
    login_rate_per_min: int = 10
    device_offline_s: int = 30
    alert_escalate_s: int = 120
    auto_assign_max_priority: int = 2          # auto-dispatch P1 and P2
    sms_secret: str = ''                       # shared secret for the SMS gateway webhook ('' = SMS intake off)
    sms_number: str = ''                       # control-room number shown to the public for SMS SOS
    public_url: str = 'http://localhost:8000'

    @property
    def is_production(self) -> bool:
        return self.env == 'production'

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith('sqlite')


@lru_cache
def get_settings() -> Settings:
    _load_dotenv()
    env = os.environ.get('TRIDENT_ENV', 'development')
    secret = os.environ.get('TRIDENT_JWT_SECRET', '')
    if not secret:
        if env == 'production':
            raise RuntimeError('TRIDENT_JWT_SECRET must be set in production')
        # dev/test: random per process - tokens do not survive a restart, which is fine locally
        secret = secrets.token_urlsafe(48)
    truthy = ('1', 'true', 'yes')
    return Settings(
        env=env,
        database_url=os.environ.get('TRIDENT_DATABASE_URL', Settings.database_url),
        jwt_secret=secret,
        access_ttl_s=int(os.environ.get('TRIDENT_ACCESS_TTL_S', 15 * 60)),
        refresh_ttl_s=int(os.environ.get('TRIDENT_REFRESH_TTL_S', 7 * 24 * 3600)),
        cors_origins=_list('TRIDENT_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173'),
        seed_demo_users=os.environ.get('TRIDENT_SEED_DEMO_USERS', 'false' if env == 'production' else 'true').lower() in truthy,
        admin_password=os.environ.get('TRIDENT_ADMIN_PASSWORD', ''),
        run_scheduler=os.environ.get('TRIDENT_RUN_SCHEDULER', 'true').lower() in truthy,
        ml_enabled=os.environ.get('TRIDENT_ML_ENABLED', 'true').lower() in truthy,
        weather_enabled=os.environ.get('TRIDENT_WEATHER_ENABLED', 'true').lower() in truthy,
        sos_rate_per_min=int(os.environ.get('TRIDENT_SOS_RATE_PER_MIN', 20)),
        sos_burst=int(os.environ.get('TRIDENT_SOS_BURST', 10)),
        login_rate_per_min=int(os.environ.get('TRIDENT_LOGIN_RATE_PER_MIN', 10)),
        sms_secret=os.environ.get('TRIDENT_SMS_SECRET', ''),
        sms_number=os.environ.get('TRIDENT_SMS_NUMBER', ''),
        public_url=os.environ.get('TRIDENT_PUBLIC_URL', 'http://localhost:8000'),
    )
