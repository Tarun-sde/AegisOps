import asyncio
import hashlib
import hmac
import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine, desc, func, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse

from apps.api.app.models import AlertEvent, Incident, IncidentEvent, Organization, Service
from apps.api.app.schemas import (
    AlertmanagerWebhookPayload,
    IncidentEventRead,
    IncidentListResponse,
    IncidentRead,
)


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"


app = FastAPI(title="AegisOps Control Plane", version="0.1.0")

# Database engine & sessionmaker
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://aegisops:test@127.0.0.1:5432/aegisops")
engine_url = (
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    if "postgresql" in DATABASE_URL and "+psycopg" not in DATABASE_URL
    else DATABASE_URL
)
engine = create_engine(engine_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
