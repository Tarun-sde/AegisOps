"""Deterministic Multi-Alert Correlation Engine.

Groups related Alertmanager alerts into incidents within bounded time windows,
enforcing strict organization and environment isolation boundaries,
and preventing false merges of unrelated services.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.models import Incident, IncidentEvent
from apps.api.app.schemas import AlertmanagerAlertItem

CORRELATION_WINDOW_MINUTES = 30
ACTIVE_STATUSES = {"open", "acknowledged", "mitigating", "reopened"}

SEVERITY_WEIGHTS: dict[str, int] = {
    "info": 1,
    "warning": 2,
    "critical": 3,
}


def _severity_rank(sev: str) -> int:
    return SEVERITY_WEIGHTS.get(sev.strip().lower(), 0)


def correlate_alert(
    *,
    db: Session,
    org_id: uuid.UUID,
    svc_id: uuid.UUID,
    alert: AlertmanagerAlertItem,
    environment: str = "staging",
    actor: str = "alertmanager",
) -> tuple[Incident, str]:
    """Correlate an incoming Alertmanager alert into an incident.

    Returns:
        tuple[Incident, str]: The incident and correlation action
        ('created', 'duplicate', 'correlated', 'resolved')
    """
    now_utc = datetime.now(UTC)
    window_start = now_utc - timedelta(minutes=CORRELATION_WINDOW_MINUTES)

    # 1. Look up existing active incident for this org, service, and environment
    # Use with_for_update() to prevent race conditions during concurrent webhook deliveries
    query = (
        select(Incident)
        .where(
            Incident.organization_id == org_id,
            Incident.service_id == svc_id,
            Incident.environment == environment,
            Incident.status.in_(ACTIVE_STATUSES),
            Incident.updated_at >= window_start,
        )
        .order_by(Incident.updated_at.desc())
        .with_for_update()
    )
    active_incident = db.scalar(query)

    if alert.status == "firing":
        if active_incident:
            # Case A: Same fingerprint -> Deduplicate firing alert delivery
            if active_incident.fingerprint == alert.fingerprint:
                active_incident.updated_at = now_utc
                dup_event = IncidentEvent(
                    incident_id=active_incident.id,
                    event_type="alert_firing_duplicate",
                    actor=actor,
                    occurred_at=now_utc,
                    payload={
                        "fingerprint": alert.fingerprint,
                        "alertname": alert.labels.get("alertname", "UnknownAlert"),
                        "starts_at": alert.startsAt.isoformat(),
                        "action": "deduplicated",
                    },
                )
                db.add(dup_event)
                return active_incident, "duplicate"

            # Case B: Distinct fingerprint, same service/env in active episode -> Correlate!
            active_incident.updated_at = now_utc
            active_incident.correlated_alert_count += 1

            new_sev = alert.labels.get("severity", "warning").lower()
            if _severity_rank(new_sev) > _severity_rank(active_incident.severity):
                active_incident.severity = new_sev

            corr_event = IncidentEvent(
                incident_id=active_incident.id,
                event_type="alert_correlated",
                actor=actor,
                occurred_at=now_utc,
                payload={
                    "fingerprint": alert.fingerprint,
                    "alertname": alert.labels.get("alertname", "UnknownAlert"),
                    "severity": new_sev,
                    "starts_at": alert.startsAt.isoformat(),
                    "reason": "same_service_and_environment_within_active_episode",
                    "rule_version": "v1-service-environment-window",
                    "window_minutes": CORRELATION_WINDOW_MINUTES,
                },
            )
            db.add(corr_event)
            return active_incident, "correlated"

        # Case C: No active incident within window -> Create new Incident
        title = (
            alert.annotations.get("summary")
            or f"High error rate on {alert.labels.get('service', 'service')}"
        )
        new_incident = Incident(
            organization_id=org_id,
            service_id=svc_id,
            environment=environment,
            title=title,
            severity=alert.labels.get("severity", "critical").lower(),
            status="open",
            version=1,
            correlated_alert_count=1,
            fingerprint=alert.fingerprint,
            started_at=alert.startsAt,
        )
        db.add(new_incident)
        db.flush()

        init_event = IncidentEvent(
            incident_id=new_incident.id,
            event_type="incident_created",
            actor=actor,
            occurred_at=alert.startsAt,
            payload={
                "summary": title,
                "description": alert.annotations.get("description", ""),
                "labels": alert.labels,
                "generatorURL": alert.generatorURL,
                "correlation_rule": "new_incident_unmatched_episode",
            },
        )
        db.add(init_event)

        from apps.api.app.outbox.service import create_outbox_event

        create_outbox_event(
            db,
            organization_id=org_id,
            aggregate_type="incident",
            aggregate_id=str(new_incident.id),
            event_type="incident.created",
            payload={
                "incident_id": str(new_incident.id),
                "service_id": str(svc_id),
                "environment": environment,
                "title": title,
                "severity": new_incident.severity,
                "status": "open",
                "started_at": alert.startsAt.isoformat(),
                "fingerprint": alert.fingerprint,
                "summary": title,
            },
            idempotency_key=f"outbox:incident_created:{new_incident.id}",
        )

        return new_incident, "created"

    elif alert.status == "resolved":
        # Handle alert resolution
        # First check if active_incident has this primary fingerprint
        if active_incident and active_incident.fingerprint == alert.fingerprint:
            active_incident.status = "resolved"
            active_incident.resolved_at = alert.endsAt or now_utc
            active_incident.updated_at = now_utc
            active_incident.version += 1

            resolved_event = IncidentEvent(
                incident_id=active_incident.id,
                event_type="incident_resolved",
                actor=actor,
                occurred_at=alert.endsAt or now_utc,
                payload={
                    "resolved_at": (alert.endsAt or now_utc).isoformat(),
                    "fingerprint": alert.fingerprint,
                    "reason": "primary_alert_resolved",
                },
            )
            db.add(resolved_event)

            from apps.api.app.outbox.service import create_outbox_event

            create_outbox_event(
                db,
                organization_id=org_id,
                aggregate_type="incident",
                aggregate_id=str(active_incident.id),
                event_type="incident.resolved",
                payload={
                    "incident_id": str(active_incident.id),
                    "service_id": str(active_incident.service_id),
                    "environment": active_incident.environment,
                    "title": active_incident.title,
                    "severity": active_incident.severity,
                    "status": "resolved",
                    "resolved_at": (alert.endsAt or now_utc).isoformat(),
                    "actor": actor,
                    "reason": "primary_alert_resolved",
                },
                idempotency_key=f"outbox:incident_resolved:{active_incident.id}:v{active_incident.version}",
            )

            return active_incident, "resolved"

        # Check if it was a correlated alert on active incident
        if active_incident:
            active_incident.updated_at = now_utc
            alert_res_event = IncidentEvent(
                incident_id=active_incident.id,
                event_type="alert_resolved",
                actor=actor,
                occurred_at=alert.endsAt or now_utc,
                payload={
                    "resolved_at": (alert.endsAt or now_utc).isoformat(),
                    "fingerprint": alert.fingerprint,
                    "alertname": alert.labels.get("alertname", ""),
                },
            )
            db.add(alert_res_event)
            return active_incident, "resolved"

        # If no active incident found, match most recent incident by fingerprint
        matching_incident = db.scalar(
            select(Incident)
            .where(
                Incident.organization_id == org_id,
                Incident.service_id == svc_id,
                Incident.fingerprint == alert.fingerprint,
            )
            .order_by(Incident.started_at.desc())
        )
        if matching_incident:
            if matching_incident.status in ("resolved", "closed"):
                return matching_incident, "duplicate"
            matching_incident.status = "resolved"
            matching_incident.resolved_at = alert.endsAt or now_utc
            matching_incident.updated_at = now_utc
            matching_incident.version += 1
            return matching_incident, "resolved"

        # Return dummy or created placeholder if out-of-order resolution arrives with no incident
        return None, "unmatched"  # type: ignore[return-value]
