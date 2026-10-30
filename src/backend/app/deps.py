"""Request dependencies: the authenticated staff user, role checks, and device authentication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy import select

from .db import read_session
from .errors import Forbidden, Unauthorized
from .models import Device, User
from .security import decode_access_token, sha256

ROLE_RANK = {'viewer': 0, 'responder': 1, 'dispatcher': 2, 'admin': 3}


@dataclass(frozen=True)
class Principal:
    id: int
    username: str
    role: str
    team_id: Optional[int]

    def at_least(self, role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]


def principal_from_token(token: str) -> Principal:
    try:
        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise Unauthorized('Access token expired', code='token_expired')
    except jwt.InvalidTokenError:
        raise Unauthorized('Invalid access token')
    with read_session() as s:
        user = s.get(User, int(claims['sub']))
        if user is None or not user.is_active:
            raise Unauthorized('Account disabled or removed')
        # the role is read from the database, not the token, so a demotion applies immediately
        return Principal(user.id, user.username, user.role, user.team_id)


def current_user(request: Request, authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith('bearer '):
        raise Unauthorized('Missing bearer token', headers={'WWW-Authenticate': 'Bearer'})
    p = principal_from_token(authorization.split(' ', 1)[1].strip())
    request.state.actor = p.username
    return p


def require(role: str) -> Callable[..., Principal]:
    def dep(user: Principal = Depends(current_user)) -> Principal:
        if not user.at_least(role):
            raise Forbidden(f'Requires role {role} or higher')
        return user
    return dep


def current_device(x_device_key: str | None = Header(default=None)) -> Device:
    """Device auth: the key identifies the device. Only its SHA-256 is stored, and the lookup is by
    that hash, so a timing difference can only reveal hash prefixes, never the key."""
    if not x_device_key or len(x_device_key) > 128:
        raise Unauthorized('Missing or malformed X-Device-Key')
    with read_session() as s:
        dev = s.scalar(select(Device).where(Device.key_hash == sha256(x_device_key)))
        if dev is None or not dev.is_active:
            raise Unauthorized('Unknown or revoked device key')
        s.expunge(dev)
        return dev
