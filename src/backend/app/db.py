"""Database engine, sessions and transaction helpers.

SQLite runs in WAL mode with foreign keys on and a busy timeout, and write transactions start
with BEGIN IMMEDIATE so two writers serialise at the start instead of failing at commit. The
same code runs on PostgreSQL (READ COMMITTED + SELECT ... FOR UPDATE where it matters).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)    # stored naive-UTC; serialised with 'Z'


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.replace(microsecond=(dt.microsecond // 1000) * 1000).isoformat() + 'Z'


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute('PRAGMA journal_mode=WAL')
    cur.execute('PRAGMA foreign_keys=ON')
    cur.execute('PRAGMA busy_timeout=5000')
    cur.execute('PRAGMA synchronous=NORMAL')
    cur.close()


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        s = get_settings()
        if s.is_sqlite:
            path = s.database_url.split('sqlite:///', 1)[-1]
            if path and path != ':memory:':
                from pathlib import Path
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(s.database_url, connect_args={'check_same_thread': False, 'timeout': 5},
                                    pool_pre_ping=True)
            event.listen(_engine, 'connect', _sqlite_pragmas)

            # pysqlite's implicit transactions would defer the write lock; take it up front instead
            @event.listens_for(_engine, 'connect')
            def _no_autobegin(dbapi_conn, _record):
                dbapi_conn.isolation_level = None

            @event.listens_for(_engine, 'begin')
            def _begin(conn):
                conn.exec_driver_sql('BEGIN IMMEDIATE' if conn.info.get('write') else 'BEGIN')
        else:
            _engine = create_engine(s.database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Tests: drop the cached engine so a new TRIDENT_DATABASE_URL takes effect."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine, _SessionLocal = None, None


def session_factory() -> sessionmaker:
    get_engine()
    return _SessionLocal


@contextmanager
def read_session() -> Iterator[Session]:
    with session_factory()() as s:
        yield s


@contextmanager
def write_tx() -> Iterator[Session]:
    """One ACID write transaction: commit on success, roll back on any exception.

    The connection is marked as a writer *before* the session begins on it, so on SQLite the
    transaction opens with BEGIN IMMEDIATE (the write lock is taken up front).
    """
    with get_engine().connect() as conn:
        conn.info['write'] = True
        s = Session(bind=conn, expire_on_commit=False)
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()
            conn.info.pop('write', None)


def get_db() -> Iterator[Session]:
    """FastAPI dependency for read paths; writes use `write_tx()` explicitly in services."""
    with read_session() as s:
        yield s
