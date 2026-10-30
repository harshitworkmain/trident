"""Critical wearable alerts: acknowledge, resolve, and escalate when nobody responds."""

from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from sqlalchemy import select

from ..audit import audit
from ..db import read_session, utcnow, write_tx
from ..errors import Conflict, NotFound
from ..models import Alert, SOSRequest
from ..realtime import HUB
from ..schemas import alert_out


def _ref(s, a: Alert) -> Optional[str]:
    return s.get(SOSRequest, a.sos_id).reference_id if a.sos_id else None


def list_alerts(status: Optional[str], limit: int = 100) -> List[dict]:
    with read_session() as s:
        stmt = select(Alert)
        if status:
            stmt = stmt.where(Alert.status == status)
        rows = s.scalars(stmt.order_by(Alert.opened_at.desc()).limit(max(1, min(500, limit)))).all()
        return [alert_out(a, _ref(s, a)) for a in rows]


def ack(alert_id: int, actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        a = s.get(Alert, alert_id)
        if a is None:
            raise NotFound(f'Alert {alert_id} not found')
        if a.status != 'open':
            raise Conflict(f'Alert is already {a.status}', {'current': alert_out(a, _ref(s, a))})
        a.status, a.acked_by, a.acked_at = 'acked', actor, utcnow()
        audit(s, actor, 'alert.ack', str(alert_id), {}, request_id)
        out = alert_out(a, _ref(s, a))
    HUB.publish('alerts', {'event': 'acked', 'alert': out})
    return out


def resolve(alert_id: int, note: Optional[str], actor: str, request_id: Optional[str]) -> dict:
    with write_tx() as s:
        a = s.get(Alert, alert_id)
        if a is None:
            raise NotFound(f'Alert {alert_id} not found')
        if a.status == 'resolved':
            raise Conflict('Alert is already resolved', {'current': alert_out(a, _ref(s, a))})
        if a.acked_at is None:
            a.acked_by, a.acked_at = actor, utcnow()
        a.status, a.resolved_at, a.resolution_note = 'resolved', utcnow(), note
        audit(s, actor, 'alert.resolve', str(alert_id), {'note': note}, request_id)
        out = alert_out(a, _ref(s, a))
    HUB.publish('alerts', {'event': 'resolved', 'alert': out})
    return out


def escalate(after_s: int) -> int:
    """Flag critical alerts left unacknowledged; the UI raises them to the top and re-announces them."""
    cutoff = utcnow() - timedelta(seconds=after_s)
    with write_tx() as s:
        rows = s.scalars(select(Alert).where(Alert.status == 'open', Alert.escalated.is_(False),
                                             Alert.opened_at < cutoff)).all()
        for a in rows:
            a.escalated = True
            audit(s, 'scheduler', 'alert.escalate', str(a.id), {'after_s': after_s})
        outs = [alert_out(a, _ref(s, a)) for a in rows]
    for out in outs:
        HUB.publish('alerts', {'event': 'escalated', 'alert': out})
    return len(outs)
