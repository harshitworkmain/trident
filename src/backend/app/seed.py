"""Reference data (teams, ROVs, contacts) and, outside production, demo staff accounts.

Idempotent: only inserts what is missing, so it runs on every start.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from .config import get_settings
from .db import write_tx
from .models import EmergencyContact, ROVUnit, Team, User
from .security import hash_password

logger = logging.getLogger('trident.seed')

TEAMS = [
    # name, type, phone, location, lat, lng, capacity, mode, description
    ('Chennai ROV Alpha', 'ROV Water Rescue', '9876543210', 'Adyar', 13.0067, 80.2575, 3, 'AUTO_DEPLOY',
     'Primary autonomous ROV unit; auto-dispatched for priority-5 water rescues'),
    ('Chennai ROV Beta', 'ROV Water Rescue', '9876543211', 'Velachery', 12.9791, 80.2210, 2, 'MANUAL_DEPLOY',
     'Secondary ROV unit for dispatcher-led operations'),
    ('Coastal Rescue Marina', 'Coastal Rescue', '9876543212', 'Marina', 13.0500, 80.2824, 4, 'MANUAL_DEPLOY',
     'Boats and divers for the coastal strip'),
    ('Medical Response North', 'Medical', '9876543215', 'Perambur', 13.1180, 80.2330, 4, 'MANUAL_DEPLOY',
     'Paramedic team with a 4x4 ambulance'),
    ('Water & Supplies Unit', 'Water Emergency Supply', '9876543213', 'T. Nagar', 13.0418, 80.2341, 6,
     'MANUAL_DEPLOY', 'Drinking water, food and medicine distribution'),
]
ROVS = [('ROV-001', 13.0067, 80.2575, 'Chennai ROV Alpha'), ('ROV-002', 12.9791, 80.2210, 'Chennai ROV Beta')]
CONTACTS = [('Emergency Services', '112', 'General Emergency'), ('Fire & Rescue', '101', 'Fire & Rescue'),
            ('Ambulance', '108', 'Medical Services'), ('Police', '100', 'Law Enforcement'),
            ('Disaster Management (TN SDMA)', '1070', 'Disaster Response')]
DEMO_USERS = [('admin', 'Admin', 'admin', None), ('dispatcher', 'Duty Dispatcher', 'dispatcher', None),
              ('responder', 'ROV Alpha Lead', 'responder', 'Chennai ROV Alpha'),
              ('viewer', 'Observer', 'viewer', None)]
DEMO_PASSWORD = 'trident-demo-2026'      # local development only; never seeded in production


def seed() -> None:
    s_cfg = get_settings()
    with write_tx() as s:
        names = set(s.scalars(select(Team.name)).all())
        for name, ttype, phone, loc, lat, lng, cap, mode, desc in TEAMS:
            if name not in names:
                s.add(Team(name=name, team_type=ttype, contact_phone=phone, location=loc, latitude=lat,
                           longitude=lng, capacity=cap, deployment_mode=mode, description=desc))
        s.flush()
        team_ids = {t.name: t.id for t in s.scalars(select(Team)).all()}
        rovs = {u.name: u for u in s.scalars(select(ROVUnit)).all()}
        for name, lat, lng, team in ROVS:
            if name not in rovs:
                s.add(ROVUnit(name=name, latitude=lat, longitude=lng, home_lat=lat, home_lng=lng,
                              team_id=team_ids.get(team)))
            elif rovs[name].team_id is None:
                rovs[name].team_id = team_ids.get(team)
        if not s.scalar(select(EmergencyContact.id)):
            s.add_all(EmergencyContact(name=n, phone=p, department=d, location='Tamil Nadu') for n, p, d in CONTACTS)
        s.flush()
        users = set(s.scalars(select(User.username)).all())
        if 'admin' not in users and s_cfg.admin_password:
            s.add(User(username='admin', display_name='Administrator', role='admin',
                       password_hash=hash_password(s_cfg.admin_password)))
            users.add('admin')
        if s_cfg.seed_demo_users and not s_cfg.is_production:
            teams = {t.name: t.id for t in s.scalars(select(Team)).all()}
            for username, display, role, team in DEMO_USERS:
                if username not in users:
                    s.add(User(username=username, display_name=display, role=role, team_id=teams.get(team),
                               password_hash=hash_password(DEMO_PASSWORD)))
                    logger.info('demo user %s (%s) created', username, role)
        elif 'admin' not in users:
            logger.warning('no admin account: set TRIDENT_ADMIN_PASSWORD to create one')
