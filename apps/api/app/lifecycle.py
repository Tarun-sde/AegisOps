"""Deterministic Incident Lifecycle State Machine.

Enforces auditable state transitions according to the master plan:
OPEN -> ACKNOWLEDGED -> MITIGATING -> RESOLVED -> CLOSED
Reopening is supported from RESOLVED and CLOSED.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from apps.api.app.models import Incident, IncidentEvent

# Canonical valid transition matrix (all keys and values lowercase)
VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"acknowledged", "mitigating", "resolved"},
    "acknowledged": {"mitigating", "resolved"},
    "mitigating": {"resolved"},
    "resolved": {"closed", "reopened"},
    "closed": {"reopened"},
    "reopened": {"acknowledged", "mitigating", "resolved"},
}

ALL_STATUSES = set(VALID_TRANSITIONS.keys())


class InvalidTransitionError(ValueError):
    """Raised when an incident status transition is disallowed by the state machine."""


class ConcurrencyConflictError(ValueError):
    """Raised when an optimistic concurrency check fails."""


def normalize_status(status_str: str) -> str:
    """Normalize status string to canonical lowercase."""
    cleaned = status_str.strip().lower()
    if cleaned not in ALL_STATUSES:
        raise InvalidTransitionError(
            f"Unknown incident status '{status_str}'. Allowed: {sorted(ALL_STATUSES)}"
        )
    return cleaned


def can_transition(current_status: str, target_status: str) -> bool:
    """Check whether a transition from current_status to target_status is permitted."""
    curr = current_status.strip().lower()
    target = target_status.strip().lower()
    allowed = VALID_TRANSITIONS.get(curr, set())
    return target in allowed


def transition_incident(
    incident: Incident,
    *,
    target_status: str,
    actor: str,
    reason: str | None = None,
    expected_version: int | None = None,
    db: Session,
    extra_payload: dict[str, Any] | None = None,
) -> Incident:
    """Transition an incident to target_status with validation and concurrency protection."""
    current_norm = incident.status.strip().lower()
    target_norm = normalize_status(target_status)

    if current_norm == target_norm:
        # Idempotent no-op
        return incident

    if not can_transition(current_norm, target_norm):
        raise InvalidTransitionError(
            f"Invalid incident transition from '{current_norm}' to '{target_norm}'. "
            f"Allowed next states: {sorted(VALID_TRANSITIONS.get(current_norm, set()))}"
        )

    if expected_version is not None and incident.version != expected_version:
        raise ConcurrencyConflictError(
            f"Incident optimistic concurrency conflict: expected version {expected_version}, "
            f"but current version is {incident.version}."
        )

    now_utc = datetime.now(UTC)
    from_status = incident.status

    incident.status = target_norm
    incident.version += 1
    incident.updated_at = now_utc

    if target_norm == "resolved":
        incident.resolved_at = now_utc
    elif target_norm == "reopened":
        incident.resolved_at = None

    payload: dict[str, Any] = {
        "from_status": from_status,
        "to_status": target_norm,
        "reason": reason or "",
        "version": incident.version,
    }
    if extra_payload:
        payload.update(extra_payload)

    status_event = IncidentEvent(
        incident_id=incident.id,
        event_type="incident_status_changed",
        actor=actor,
        occurred_at=now_utc,
        payload=payload,
    )
    db.add(status_event)

    if target_norm == "resolved":
        from apps.api.app.outbox.service import create_outbox_event

        create_outbox_event(
            db,
            organization_id=incident.organization_id,
            aggregate_type="incident",
            aggregate_id=str(incident.id),
            event_type="incident.resolved",
            payload={
                "incident_id": str(incident.id),
                "service_id": str(incident.service_id),
                "environment": incident.environment,
                "title": incident.title,
                "severity": incident.severity,
                "status": "resolved",
                "resolved_at": now_utc.isoformat(),
                "actor": actor,
                "reason": reason or "",
            },
            idempotency_key=f"outbox:incident_resolved:{incident.id}:v{incident.version}",
        )

    return incident
