"""Transactional Outbox publication service."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.models import OutboxEvent

logger = logging.getLogger(__name__)

MAX_PAYLOAD_BYTES = 65536  # 64 KB bounded event size


def create_outbox_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
    event_version: int = 1,
) -> OutboxEvent:
    """Create an outbox event within the caller's active database transaction.

    DOES NOT commit the transaction: the caller must commit so that domain state changes
    and the outbox event persist atomically.
    """
    serialized = json.dumps(payload, default=str)
    if len(serialized.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"Outbox event payload exceeds maximum size limit of {MAX_PAYLOAD_BYTES} bytes"
        )

    event_id = uuid.uuid4()
    stable_idempotency_key = idempotency_key or f"{event_type}:{aggregate_id}:{event_id}"

    # Build standardized envelope
    envelope = {
        "event_id": str(event_id),
        "event_type": event_type,
        "event_version": event_version,
        "organization_id": str(organization_id),
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "idempotency_key": stable_idempotency_key,
        "data": payload,
    }

    event = OutboxEvent(
        id=event_id,
        organization_id=organization_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        event_version=event_version,
        payload=envelope,
        idempotency_key=stable_idempotency_key,
        status="PENDING",
        attempt_count=0,
        max_attempts=5,
    )
    db.add(event)
    return event
