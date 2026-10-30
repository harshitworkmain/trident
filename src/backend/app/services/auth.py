"""Login, rotating refresh tokens with reuse detection, and user administration."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import List, Optional

from sqlalchemy import select, update

from ..audit import audit
from ..config import get_settings
from ..db import read_session, utcnow, write_tx
from ..errors import Conflict, NotFound, Unauthorized
from ..models import RefreshToken, Team, User
from ..schemas import user_out
from ..security import create_access_token, hash_password, new_refresh_token, sha256, verify_password_or_dummy

logger = logging.getLogger('trident.auth')


def _issue(s, user: User, family_id: Optional[str] = None) -> dict:
    token, token_hash = new_refresh_token()
    s.add(RefreshToken(user_id=user.id, token_hash=token_hash, family_id=family_id or secrets.token_hex(12),
                       expires_at=utcnow() + timedelta(seconds=get_settings().refresh_ttl_s)))
    access, ttl = create_access_token(user.id, user.role)
    return {'access_token': access, 'refresh_token': token, 'token_type': 'bearer', 'expires_in': ttl,
            'user': user_out(user)}


def login(username: str, password: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        user = s.scalar(select(User).where(User.username == username))
        ok = verify_password_or_dummy(password, user.password_hash if user else None)
        if not ok or user is None or not user.is_active:
            audit(s, username[:64], 'auth.login_failed', username[:64], {}, request_id)
            s.commit()                                   # keep the failed-login audit row
            raise Unauthorized('Wrong username or password')
        user.last_login_at = utcnow()
        audit(s, user.username, 'auth.login', user.username, {}, request_id)
        return _issue(s, user)


def refresh(token: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        rt = s.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(token)))
        if rt is None:
            raise Unauthorized('Unknown refresh token')
        now = utcnow()
        if rt.rotated_at is not None or rt.revoked_at is not None:
            # a rotated token came back: someone else has a copy. Kill the whole login family.
            s.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id,
                                                 RefreshToken.revoked_at.is_(None)).values(revoked_at=now))
            audit(s, f'user:{rt.user_id}', 'auth.refresh_reuse', rt.family_id, {}, request_id)
            s.commit()
            logger.warning('refresh token reuse detected for user %s; family revoked', rt.user_id)
            raise Unauthorized('Session revoked, please sign in again', code='session_revoked')
        if rt.expires_at < now:
            raise Unauthorized('Session expired, please sign in again', code='session_expired')
        user = s.get(User, rt.user_id)
        if user is None or not user.is_active:
            raise Unauthorized('Account disabled')
        rt.rotated_at = now
        return _issue(s, user, rt.family_id)


def logout(token: str) -> None:
    username = None
    with write_tx() as s:
        rt = s.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(token)))
        if rt is not None:
            s.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id,
                                                 RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow()))
            u = s.get(User, rt.user_id)
            username = u.username if u else None
    if username:
        from ..realtime import HUB
        HUB.disconnect_user(username)                 # other tabs reconnect with their own valid tokens


def me(user_id: int) -> dict:
    with read_session() as s:
        return user_out(s.get(User, user_id))


def list_users() -> List[dict]:
    with read_session() as s:
        return [user_out(u) for u in s.scalars(select(User).order_by(User.username)).all()]


def create_user(data: dict, actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        if s.scalar(select(User.id).where(User.username == data['username'])) is not None:
            raise Conflict('Username taken')
        if data.get('team_id') and s.get(Team, data['team_id']) is None:
            raise NotFound('Team not found')
        u = User(username=data['username'], display_name=data['display_name'], role=data['role'],
                 team_id=data.get('team_id'), password_hash=hash_password(data['password']))
        s.add(u)
        audit(s, actor, 'user.create', data['username'], {'role': data['role']}, request_id)
        s.flush()
        return user_out(u)


def update_user(user_id: int, patch: dict, actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        u = s.get(User, user_id)
        if u is None:
            raise NotFound('User not found')
        changes = {}
        for k in ('display_name', 'role', 'team_id', 'is_active'):
            if patch.get(k) is not None:
                setattr(u, k, patch[k])
                changes[k] = patch[k]
        if patch.get('password'):
            u.password_hash = hash_password(patch['password'])
            changes['password'] = 'changed'
        if 'password' in changes or patch.get('is_active') is False or 'role' in changes:
            # credentials or rights changed: end existing sessions
            s.execute(update(RefreshToken).where(RefreshToken.user_id == u.id, RefreshToken.revoked_at.is_(None))
                      .values(revoked_at=utcnow()))
        audit(s, actor, 'user.update', u.username, changes, request_id)
        out = user_out(u)
    if {'password', 'role', 'is_active'} & set(changes):
        from ..realtime import HUB
        HUB.disconnect_user(out['username'])          # open live sessions end with the old rights
    return out


IDEMPOTENCY_KEEP = timedelta(hours=48)   # an SOS queued offline on a phone may be re-sent hours later


def purge_tokens() -> int:
    """Expired refresh tokens and idempotency keys older than IDEMPOTENCY_KEEP."""
    from sqlalchemy import delete
    from ..models import IdempotencyKey
    with write_tx() as s:
        n = s.execute(delete(RefreshToken).where(RefreshToken.expires_at < utcnow() - timedelta(days=1))).rowcount or 0
        n += s.execute(delete(IdempotencyKey).where(IdempotencyKey.created_at < utcnow() - IDEMPOTENCY_KEEP)).rowcount or 0
        return n
