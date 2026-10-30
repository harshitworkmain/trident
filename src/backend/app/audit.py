"""Append-only audit trail, written inside the same transaction as the change it records."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from .models import AuditLog


def audit(s: Session, actor: str, action: str, target: str, details: Optional[dict] = None,
          request_id: Optional[str] = None) -> None:
    s.add(AuditLog(actor=actor, action=action, target=target, details=details or {}, request_id=request_id))
