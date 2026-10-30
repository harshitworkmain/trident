"""Passwords, JWT access tokens, rotating refresh tokens and device keys."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt

from .config import get_settings

JWT_ALG = 'HS256'
JWT_ISSUER = 'trident'


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# a fixed hash to compare against when the user does not exist, so login time does not reveal it
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_password_or_dummy(password: str, hashed: Optional[str]) -> bool:
    return verify_password(password, hashed or _DUMMY_HASH) and hashed is not None


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_access_token(user_id: int, role: str) -> Tuple[str, int]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    claims = {'sub': str(user_id), 'role': role, 'iss': JWT_ISSUER, 'iat': now,
              'exp': now + timedelta(seconds=s.access_ttl_s), 'jti': secrets.token_hex(8), 'typ': 'access'}
    return jwt.encode(claims, s.jwt_secret, algorithm=JWT_ALG), s.access_ttl_s


def decode_access_token(token: str) -> dict:
    """Raises jwt.InvalidTokenError (expired, bad signature, wrong issuer/type)."""
    claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALG], issuer=JWT_ISSUER,
                        options={'require': ['exp', 'sub', 'role']})
    if claims.get('typ') != 'access':
        raise jwt.InvalidTokenError('not an access token')
    return claims


def new_refresh_token() -> Tuple[str, str]:
    """(token for the client, sha256 to store)."""
    token = secrets.token_urlsafe(48)
    return token, sha256(token)


def new_device_key() -> Tuple[str, str]:
    key = 'tdk_' + secrets.token_urlsafe(32)
    return key, sha256(key)


def key_matches(key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(sha256(key), stored_hash)


def new_reference_id() -> str:
    # no 0/O/1/I so references survive being read out over a phone line
    alphabet = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
    return 'SOS-' + ''.join(secrets.choice(alphabet) for _ in range(6))
