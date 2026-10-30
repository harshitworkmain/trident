"""Alembic migrations, run on start-up (`upgrade()`) and from the CLI:

    python -m src.backend.app.migrate upgrade            # apply all
    python -m src.backend.app.migrate revision "message" # autogenerate a new revision from the models
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import get_settings

MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations'


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option('script_location', str(MIGRATIONS))
    cfg.set_main_option('sqlalchemy.url', get_settings().database_url.replace('%', '%%'))
    return cfg


def upgrade(rev: str = 'head') -> None:
    command.upgrade(_config(), rev)


def revision(message: str) -> None:
    command.revision(_config(), message=message, autogenerate=True)


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'revision':
        revision(sys.argv[2] if len(sys.argv) > 2 else 'change')
    else:
        upgrade()
