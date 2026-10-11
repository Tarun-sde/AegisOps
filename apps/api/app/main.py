import asyncio
import hashlib
import hmac
import os
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload
from starlette.responses import JSONResponse

from apps.api.app.db import get_db
from apps.api.app.models import (
    AlertEvent,
    EvidenceItem,
    Incident,
    IncidentEvent,
    InvestigationRun,
    Organization,
    Service,
    ToolExecution,
)
from apps.api.app.schemas import (
    AlertmanagerWebhookPayload,
    EvidenceItemRead,
    EvidenceListResponse,
    HypothesisRead,
    IncidentEventRead,
    IncidentListResponse,
    IncidentRead,
    InvestigationRunCreate,
    InvestigationRunDetailRead,
    InvestigationRunRead,
    ToolExecutionRead,
)
from apps.worker.tasks import run_investigation_task


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"


app = FastAPI(title="AegisOps Control Plane", version="0.1.0")

DbSession = Annotated[Session, Depends(get_db)]


@app.get("/healthz", response_model=Health)
def healthz() -> Health:
    return Health()


async def check_postgres() -> None:
    async with await psycopg.AsyncConnection.connect(
        os.environ["DATABASE_URL"], connect_timeout=3
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT 1")
            if await cursor.fetchone() != (1,):
                raise RuntimeError("Database probe failed")


async def check_redis() -> None:
    async with Redis.from_url(
        os.environ["REDIS_URL"], socket_connect_timeout=3, socket_timeout=3
    ) as client:
        if not await client.ping():
            raise RuntimeError("Redis probe failed")


@app.get("/readyz")
async def readyz() -> JSONResponse:
    checks: dict[str, str] = {}
    for name, probe in (("postgres", check_postgres), ("redis", check_redis)):
        try:
            async with asyncio.timeout(3):
                await probe()
            checks[name] = "ok"
        except (
            KeyError,
            ValueError,
            TimeoutError,
            OSError,
            psycopg.Error,
            RedisError,
            RuntimeError,
        ):
            checks[name] = "unavailable"
    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "unavailable", "checks": checks},
        status_code=200 if ready else 503,
    )


# --- Phase 1: Webhook & Incident Management ---

ALERTMANAGER_SECRET = os.environ.get("ALERTMANAGER_SECRET", "aegisops-demo-alertmanager-secret")


def verify_alertmanager_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer authentication header",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, ALERTMANAGER_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized webhook credentials",
        )


def get_or_create_demo_scope(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    org = session.scalar(select(Organization).where(Organization.name == "AegisOps Demo"))
    if not org:
        org = Organization(name="AegisOps Demo")
        session.add(org)
        session.flush()

    svc = session.scalar(
        select(Service).where(Service.organization_id == org.id, Service.name == "shop-api")
    )
    if not svc:
        svc = Service(organization_id=org.id, name="shop-api")
        session.add(svc)
        session.flush()

    return org.id, svc.id


@app.post("/api/v1/webhooks/alertmanager", status_code=status.HTTP_200_OK)
async def alertmanager_webhook(
    request: Request,
    payload: AlertmanagerWebhookPayload,
    db: DbSession,
    _auth: Annotated[None, Depends(verify_alertmanager_auth)],
) -> dict[str, object]:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 524_288:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload exceeds maximum permitted size of 512KB",
        )

    org_id, svc_id = get_or_create_demo_scope(db)
    now_utc = datetime.now(UTC)
    created_count = 0
    resolved_count = 0
    duplicate_count = 0

    for alert in payload.alerts:
        payload_hash = hashlib.sha256(
            f"{alert.fingerprint}:{alert.startsAt}:{alert.status}".encode()
        ).hexdigest()

        alert_event = AlertEvent(
            organization_id=org_id,
            service_id=svc_id,
            fingerprint=alert.fingerprint,
            payload_hash=payload_hash,
            source="alertmanager",
            status=alert.status,
            severity=alert.labels.get("severity", "critical"),
            starts_at=alert.startsAt,
            ends_at=alert.endsAt,
            labels=alert.labels,
            annotations=alert.annotations,
        )
        db.add(alert_event)

        # Look up existing open incident for active episode deduplication
        existing_incident = db.scalar(
            select(Incident)
            .where(
                Incident.organization_id == org_id,
                Incident.service_id == svc_id,
                Incident.fingerprint == alert.fingerprint,
                Incident.status == "open",
            )
            .with_for_update()
        )

        if alert.status == "firing":
            if existing_incident:
                duplicate_count += 1
                existing_incident.updated_at = now_utc
                dup_event = IncidentEvent(
                    incident_id=existing_incident.id,
                    event_type="alert_firing_duplicate",
                    actor="alertmanager",
                    occurred_at=now_utc,
                    payload={
                        "fingerprint": alert.fingerprint,
                        "starts_at": alert.startsAt.isoformat(),
                    },
                )
                db.add(dup_event)
            else:
                created_count += 1
                title = (
                    alert.annotations.get("summary")
                    or f"High error rate on {alert.labels.get('service', 'shop-api')}"
                )
                new_incident = Incident(
                    organization_id=org_id,
                    service_id=svc_id,
                    title=title,
                    severity=alert.labels.get("severity", "critical"),
                    status="open",
                    fingerprint=alert.fingerprint,
                    started_at=alert.startsAt,
                )
                db.add(new_incident)
                db.flush()

                init_event = IncidentEvent(
                    incident_id=new_incident.id,
                    event_type="incident_created",
                    actor="alertmanager",
                    occurred_at=alert.startsAt,
                    payload={
                        "summary": title,
                        "description": alert.annotations.get("description", ""),
                        "labels": alert.labels,
                        "generatorURL": alert.generatorURL,
                    },
                )
                db.add(init_event)

        elif alert.status == "resolved":
            if existing_incident:
                resolved_count += 1
                existing_incident.status = "resolved"
                existing_incident.resolved_at = alert.endsAt or now_utc
                existing_incident.updated_at = now_utc

                resolved_event = IncidentEvent(
                    incident_id=existing_incident.id,
                    event_type="incident_resolved",
                    actor="alertmanager",
                    occurred_at=alert.endsAt or now_utc,
                    payload={
                        "resolved_at": (alert.endsAt or now_utc).isoformat(),
                        "fingerprint": alert.fingerprint,
                    },
                )
                db.add(resolved_event)

    db.commit()
    return {
        "status": "success",
        "processed_alerts": len(payload.alerts),
        "incidents_created": created_count,
        "incidents_resolved": resolved_count,
        "duplicates_skipped": duplicate_count,
    }


@app.get("/api/v1/incidents", response_model=IncidentListResponse)
def list_incidents(
    db: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    severity: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IncidentListResponse:
    query = select(Incident)
    count_query = select(func.count(Incident.id))

    if status_filter:
        query = query.where(Incident.status == status_filter)
        count_query = count_query.where(Incident.status == status_filter)
    if severity:
        query = query.where(Incident.severity == severity)
        count_query = count_query.where(Incident.severity == severity)

    total = db.scalar(count_query) or 0
    items = db.scalars(
        query.order_by(desc(Incident.started_at)).offset((page - 1) * size).limit(size)
    ).all()

    return IncidentListResponse(
        items=[IncidentRead.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@app.get("/api/v1/incidents/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: uuid.UUID, db: DbSession) -> IncidentRead:
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return IncidentRead.model_validate(incident)


@app.get("/api/v1/incidents/{incident_id}/events", response_model=list[IncidentEventRead])
def get_incident_events(incident_id: uuid.UUID, db: DbSession) -> list[IncidentEventRead]:
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    events = db.scalars(
        select(IncidentEvent)
        .where(IncidentEvent.incident_id == incident_id)
        .order_by(IncidentEvent.occurred_at.asc())
    ).all()
    return [IncidentEventRead.model_validate(e) for e in events]


@app.post(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=InvestigationRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_investigation(
    incident_id: uuid.UUID,
    db: DbSession,
    payload: InvestigationRunCreate | None = None,
) -> InvestigationRunRead:
    body = payload or InvestigationRunCreate()
    incident = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    # Check for an active running investigation on this incident
    active_run = db.scalar(
        select(InvestigationRun).where(
            InvestigationRun.incident_id == incident_id,
            InvestigationRun.status.in_(
                ["QUEUED", "COLLECTING_CONTEXT", "INVESTIGATING", "VALIDATING"]
            ),
        )
    )
    if active_run:
        return InvestigationRunRead.model_validate(active_run)

    model_name = body.model or os.environ.get("AEGISOPS_AGENT_MODEL", "gemini-3.5-flash")
    prompt_version = body.prompt_version or "phase2-v1"
    mode = body.execution_mode or os.environ.get("AEGISOPS_AGENT_MODE", "offline").lower()

    run = InvestigationRun(
        incident_id=incident.id,
        organization_id=incident.organization_id,
        service_id=incident.service_id,
        status="QUEUED",
        execution_mode=mode,
        provider="gemini" if mode == "live" else "offline",
        model=model_name,
        prompt_version=prompt_version,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Dispatch asynchronous background task
    try:
        run_investigation_task.delay(str(run.id))
    except Exception:
        # Fallback to local synchronous execution if broker is not reachable
        from agents.incident_investigator.investigator import execute_investigation

        execute_investigation(run.id, db)
        db.refresh(run)

    return InvestigationRunRead.model_validate(run)


@app.get(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=list[InvestigationRunRead],
)
def list_incident_investigations(
    incident_id: uuid.UUID,
    db: DbSession,
) -> list[InvestigationRunRead]:
    runs = db.scalars(
        select(InvestigationRun)
        .where(InvestigationRun.incident_id == incident_id)
        .order_by(desc(InvestigationRun.created_at))
    ).all()
    return [InvestigationRunRead.model_validate(r) for r in runs]


@app.get(
    "/api/v1/investigations/{investigation_id}",
    response_model=InvestigationRunDetailRead,
)
def get_investigation(
    investigation_id: uuid.UUID,
    db: DbSession,
) -> InvestigationRunDetailRead:
    run = db.scalar(
        select(InvestigationRun)
        .options(
            selectinload(InvestigationRun.hypotheses),
            selectinload(InvestigationRun.evidence_items),
        )
        .where(InvestigationRun.id == investigation_id)
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation run '{investigation_id}' not found",
        )

    return InvestigationRunDetailRead(
        id=run.id,
        incident_id=run.incident_id,
        organization_id=run.organization_id,
        service_id=run.service_id,
        status=run.status,
        model=run.model,
        prompt_version=run.prompt_version,
        summary=run.summary,
        tool_call_count=run.tool_call_count,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        hypotheses=[HypothesisRead.model_validate(h) for h in run.hypotheses],
        missing_evidence=run.missing_evidence or [],
        limitations=run.limitations or [],
        suggested_actions=run.suggested_actions or [],
        evidence_items=[EvidenceItemRead.model_validate(e) for e in run.evidence_items],
    )


@app.get(
    "/api/v1/investigations/{investigation_id}/events",
    response_model=list[ToolExecutionRead],
)
def get_investigation_events(
    investigation_id: uuid.UUID,
    db: DbSession,
) -> list[ToolExecutionRead]:
    run = db.scalar(select(InvestigationRun).where(InvestigationRun.id == investigation_id))
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation run '{investigation_id}' not found",
        )

    executions = db.scalars(
        select(ToolExecution)
        .where(ToolExecution.run_id == investigation_id)
        .order_by(ToolExecution.created_at.asc())
    ).all()
    return [ToolExecutionRead.model_validate(e) for e in executions]


@app.get(
    "/api/v1/investigations/{investigation_id}/evidence",
    response_model=EvidenceListResponse,
)
def get_investigation_evidence(
    investigation_id: uuid.UUID,
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> EvidenceListResponse:
    run = db.scalar(select(InvestigationRun).where(InvestigationRun.id == investigation_id))
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation run '{investigation_id}' not found",
        )

    count_query = (
        select(func.count())
        .select_from(EvidenceItem)
        .where(EvidenceItem.run_id == investigation_id)
    )
    total = db.scalar(count_query) or 0
    items = db.scalars(
        select(EvidenceItem)
        .where(EvidenceItem.run_id == investigation_id)
        .order_by(EvidenceItem.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    return EvidenceListResponse(
        items=[EvidenceItemRead.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@app.get("/api/v1/evidence/{evidence_id}", response_model=EvidenceItemRead)
def get_evidence_item(evidence_id: str, db: DbSession) -> EvidenceItemRead:
    item = db.scalar(select(EvidenceItem).where(EvidenceItem.evidence_id == evidence_id))
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item '{evidence_id}' not found",
        )
    return EvidenceItemRead.model_validate(item)


@app.post(
    "/api/v1/investigations/{investigation_id}/cancel",
    response_model=InvestigationRunRead,
)
def cancel_investigation(
    investigation_id: uuid.UUID,
    db: DbSession,
) -> InvestigationRunRead:
    run = db.scalar(select(InvestigationRun).where(InvestigationRun.id == investigation_id))
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation run '{investigation_id}' not found",
        )

    if run.status in ["QUEUED", "COLLECTING_CONTEXT", "INVESTIGATING", "VALIDATING"]:
        run.status = "CANCELLED"
        run.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)

    return InvestigationRunRead.model_validate(run)
