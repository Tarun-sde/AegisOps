from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from apps.api.app.models import Incident, InvestigationRun

logger = logging.getLogger(__name__)

DEFAULT_HISTORICAL_LIMIT = 5
MAX_HISTORICAL_LIMIT = 10


@dataclass
class RelatedIncidentResult:
    evidence_id: str
    incident_id: str
    title: str
    severity: str
    service_id: str
    started_at: str
    resolved_at: str | None
    status: str
    match_reason: str
    resolution_summary: str | None


class RelatedIncidentService:
    """Service to retrieve tenant-scoped historical incidents for pattern comparison."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_related_incidents(
        self,
        organization_id: uuid.UUID,
        service_id: uuid.UUID | None = None,
        symptoms: str = "",
        exclude_incident_id: uuid.UUID | None = None,
        limit: int = DEFAULT_HISTORICAL_LIMIT,
    ) -> list[RelatedIncidentResult]:
        """Query historically resolved or closed incidents matching service or symptom patterns."""
        limit = max(1, min(limit, MAX_HISTORICAL_LIMIT))
        conditions = [
            Incident.organization_id == organization_id,
            Incident.status.in_(["resolved", "closed"]),
        ]
        if exclude_incident_id is not None:
            conditions.append(Incident.id != exclude_incident_id)

        if service_id is not None:
            conditions.append(Incident.service_id == service_id)

        stmt = (
            select(Incident)
            .where(and_(*conditions))
            .order_by(Incident.resolved_at.desc().nullslast(), Incident.created_at.desc())
            .limit(limit * 2)
        )
        candidates = list(self.db.scalars(stmt).all())

        if not candidates and service_id is not None:
            # Broaden to all organization resolved incidents if service-specific pool is empty
            broad_conditions = [
                Incident.organization_id == organization_id,
                Incident.status.in_(["resolved", "closed"]),
            ]
            if exclude_incident_id is not None:
                broad_conditions.append(Incident.id != exclude_incident_id)
            stmt = (
                select(Incident)
                .where(and_(*broad_conditions))
                .order_by(Incident.resolved_at.desc().nullslast())
                .limit(limit)
            )
            candidates = list(self.db.scalars(stmt).all())

        tokens = [t.lower() for t in symptoms.split() if len(t) >= 3]

        scored: list[tuple[Incident, str, float]] = []
        for inc in candidates:
            # Find latest completed investigation summary if available
            inv = self.db.scalar(
                select(InvestigationRun)
                .where(
                    InvestigationRun.incident_id == inc.id,
                    InvestigationRun.status == "COMPLETE",
                )
                .order_by(InvestigationRun.completed_at.desc())
            )
            summary_text = inv.summary if inv and inv.summary else ""
            combined_text = f"{inc.title} {summary_text}".lower()

            matches = sum(1 for token in tokens if token in combined_text) if tokens else 0
            if tokens and matches > 0:
                reason = f"symptom_keyword_match: {matches} overlapping terms"
                score = matches + 1.0
            elif service_id and inc.service_id == service_id:
                reason = "prior_resolved_incident_same_service"
                score = 1.0
            else:
                reason = "historical_organization_incident"
                score = 0.5

            scored.append((inc, reason, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        top = scored[:limit]

        results: list[RelatedIncidentResult] = []
        for inc, reason, _ in top:
            # Query investigation summary
            inv = self.db.scalar(
                select(InvestigationRun)
                .where(
                    InvestigationRun.incident_id == inc.id,
                    InvestigationRun.status == "COMPLETE",
                )
                .order_by(InvestigationRun.completed_at.desc())
            )
            res_summary = inv.summary if inv else None
            ev_id = f"ev_hist_{inc.id.hex[:12]}"
            results.append(
                RelatedIncidentResult(
                    evidence_id=ev_id,
                    incident_id=str(inc.id),
                    title=inc.title,
                    severity=inc.severity,
                    service_id=str(inc.service_id),
                    started_at=inc.started_at.isoformat() if inc.started_at else "",
                    resolved_at=inc.resolved_at.isoformat() if inc.resolved_at else None,
                    status=inc.status,
                    match_reason=reason,
                    resolution_summary=res_summary,
                )
            )

        return results
