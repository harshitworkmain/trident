"""Alembic environment: uses the app's engine (so SQLite pragmas apply) and models metadata.

Offline mode (`alembic upgrade head --sql`, or command.upgrade(cfg, 'head', sql=True)) renders the
DDL for the configured URL without connecting - e.g. to review PostgreSQL migrations in CI.
"""

from alembic import context

from src.backend.app import models  # noqa: F401  (registers tables on Base.metadata)
from src.backend.app.db import Base, get_engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = context.config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True,
                      render_as_batch=url.startswith('sqlite'), dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        sqlite = connection.dialect.name == 'sqlite'
        if sqlite:
            # SQLite ALTERs rebuild the table (copy, drop, rename); with enforcement on, dropping a
            # table that others reference fails. Turn it off for the migration, then verify integrity.
            # (on the raw driver connection: through SQLAlchemy it would autobegin, and SQLite ignores
            # this pragma inside a transaction)
            connection.connection.dbapi_connection.execute('PRAGMA foreign_keys=OFF')
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=sqlite, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            raw = connection.connection.dbapi_connection
            broken = raw.execute('PRAGMA foreign_key_check').fetchall()
            raw.execute('PRAGMA foreign_keys=ON')
            if broken:
                raise RuntimeError(f'foreign key violations after migration: {broken[:5]}')


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
