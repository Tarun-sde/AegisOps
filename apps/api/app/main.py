import asyncio
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload
from starlette.responses import JSONResponse

from apps.api.app.auth import (
    TenantContext,
    clear_auth_cookies,
    create_user_session,
    extract_raw_token,
    get_current_user,
    get_tenant_context,
    hash_password,
    log_audit_event,
    revoke_user_session,
    set_auth_cookies,
    validate_connector_url,
    verify_password,
)
from apps.api.app.db import get_db
from apps.api.app.models import (
    AlertEvent,
    EvidenceItem,
    Incident,
    IncidentEvent,
    InvestigationRun,
    Membership,
    Organization,
    Service,
    ToolExecution,
    User,
)
from apps.api.app.schemas import (
    AlertmanagerWebhookPayload,
    AuthResponse,
    EvidenceItemRead,
    EvidenceListResponse,
    HypothesisRead,
    IncidentEventRead,
    IncidentListResponse,
    IncidentRead,
    InvestigationRunCreate,
    InvestigationRunDetailRead,
    InvestigationRunRead,
    LoginRequest,
    MemberAddRequest,
    MembershipRead,
    OrganizationCreate,
    OrganizationRead,
    RegisterRequest,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
    ServiceVerifyRequest,
    ServiceVerifyResponse,
    ToolExecutionRead,
    TraceSummaryRead,
    UserRead,
)
from apps.api.app.telemetry.tempo import TempoClient, validate_trace_id
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


# --- Phase 3: Authentication & Session Lifecycle ---


@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    db: DbSession,
) -> AuthResponse:
    email_clean = payload.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email address is required.",
        )
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )

    existing = db.scalar(select(User).where(User.email == email_clean))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    pwd_hash, salt = hash_password(payload.password)
    user = User(
        email=email_clean,
        hashed_password=pwd_hash,
        salt=salt,
        name=payload.name.strip() or email_clean.split("@")[0],
    )
    db.add(user)
    db.flush()

    org_name = f"{user.name}'s Workspace"
    org = Organization(name=org_name)
    db.add(org)
    db.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=org.id,
        role="owner",
    )
    db.add(membership)
    db.flush()

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    raw_token, session = create_user_session(db, user.id, ip, ua)
    csrf_token = set_auth_cookies(response, raw_token)

    log_audit_event(
        db,
        organization_id=org.id,
        actor_id=user.id,
        resource_type="user",
        resource_id=str(user.id),
        action="user.registered",
        result="success",
        metadata={"email": email_clean},
        ip_address=ip,
    )

    return AuthResponse(
        user=UserRead.model_validate(user),
        active_organization=OrganizationRead.model_validate(org),
        role="owner",
        organizations=[OrganizationRead.model_validate(org)],
        csrf_token=csrf_token,
    )


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: DbSession,
) -> AuthResponse:
    email_clean = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email_clean))

    ip = request.client.host if request.client else None
    if not user or not verify_password(payload.password, user.hashed_password, user.salt):
        log_audit_event(
            db,
            organization_id=None,
            actor_id=user.id if user else None,
            resource_type="auth",
            resource_id=email_clean,
            action="user.login_failed",
            result="failure",
            metadata={"reason": "invalid_credentials"},
            ip_address=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
        )

    memberships = db.scalars(
        select(Membership)
        .where(Membership.user_id == user.id)
        .order_by(Membership.created_at.asc())
    ).all()

    active_org: Organization | None = None
    role: str | None = None
    all_orgs: list[OrganizationRead] = []

    if memberships:
        org_ids = [m.organization_id for m in memberships]
        orgs = db.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()
        org_map = {o.id: o for o in orgs}
        all_orgs = [OrganizationRead.model_validate(o) for o in orgs]
        active_org = org_map.get(memberships[0].organization_id)
        role = memberships[0].role

    ua = request.headers.get("user-agent")
    raw_token, session = create_user_session(db, user.id, ip, ua)
    csrf_token = set_auth_cookies(response, raw_token)

    log_audit_event(
        db,
        organization_id=active_org.id if active_org else None,
        actor_id=user.id,
        resource_type="auth",
        resource_id=str(user.id),
        action="user.login",
        result="success",
        ip_address=ip,
    )

    return AuthResponse(
        user=UserRead.model_validate(user),
        active_organization=OrganizationRead.model_validate(active_org) if active_org else None,
        role=role,
        organizations=all_orgs,
        csrf_token=csrf_token,
    )


@app.post("/api/v1/auth/logout")
def logout(
    request: Request,
    response: Response,
    db: DbSession,
) -> dict[str, str]:
    raw_token = extract_raw_token(request)
    if raw_token:
        revoke_user_session(db, raw_token)
    clear_auth_cookies(response)
    return {"status": "logged_out"}


@app.get("/api/v1/me", response_model=AuthResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> AuthResponse:
    memberships = db.scalars(
        select(Membership)
        .where(Membership.user_id == current_user.id)
        .order_by(Membership.created_at.asc())
    ).all()
    org_ids = [m.organization_id for m in memberships]
    orgs = db.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()
    all_orgs = [OrganizationRead.model_validate(o) for o in orgs]

    return AuthResponse(
        user=UserRead.model_validate(current_user),
        active_organization=OrganizationRead.model_validate(context.organization),
        role=context.role,
        organizations=all_orgs,
    )


# --- Phase 3: Organizations & Memberships ---


@app.get("/api/v1/organizations", response_model=list[OrganizationRead])
def list_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> list[OrganizationRead]:
    memberships = db.scalars(select(Membership).where(Membership.user_id == current_user.id)).all()
    org_ids = [m.organization_id for m in memberships]
    orgs = db.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()
    return [OrganizationRead.model_validate(o) for o in orgs]


@app.post(
    "/api/v1/organizations",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    payload: OrganizationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: DbSession,
) -> OrganizationRead:
    org = Organization(name=payload.name.strip())
    db.add(org)
    db.flush()

    membership = Membership(
        user_id=current_user.id,
        organization_id=org.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(org)

    log_audit_event(
        db,
        organization_id=org.id,
        actor_id=current_user.id,
        resource_type="organization",
        resource_id=str(org.id),
        action="organization.created",
        result="success",
        metadata={"name": org.name},
    )
    return OrganizationRead.model_validate(org)


@app.get("/api/v1/organizations/{org_id}/members", response_model=list[MembershipRead])
def list_organization_members(
    org_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> list[MembershipRead]:
    if context.organization.id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access membership details of another organization.",
        )
    memberships = db.scalars(
        select(Membership)
        .where(Membership.organization_id == org_id)
        .options(selectinload(Membership.user))
    ).all()
    results = []
    for m in memberships:
        mr = MembershipRead.model_validate(m)
        mr.user_email = m.user.email if m.user else None
        mr.organization_name = context.organization.name
        results.append(mr)
    return results


@app.post(
    "/api/v1/organizations/{org_id}/members",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
def add_organization_member(
    org_id: uuid.UUID,
    payload: MemberAddRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> MembershipRead:
    if context.organization.id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify membership of another organization.",
        )
    if not context.can("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can invite members.",
        )

    target_email = payload.email.strip().lower()
    target_user = db.scalar(select(User).where(User.email == target_email))
    if not target_user:
        pwd_hash, salt = hash_password(secrets.token_urlsafe(16))
        target_user = User(
            email=target_email,
            hashed_password=pwd_hash,
            salt=salt,
            name=target_email.split("@")[0],
        )
        db.add(target_user)
        db.flush()

    existing_membership = db.scalar(
        select(Membership).where(
            Membership.user_id == target_user.id,
            Membership.organization_id == org_id,
        )
    )
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{target_email}' is already a member of this organization.",
        )

    membership = Membership(
        user_id=target_user.id,
        organization_id=org_id,
        role=payload.role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    log_audit_event(
        db,
        organization_id=org_id,
        actor_id=context.user.id,
        resource_type="membership",
        resource_id=str(membership.id),
        action="membership.created",
        result="success",
        metadata={"user_email": target_email, "role": payload.role},
    )

    mr = MembershipRead.model_validate(membership)
    mr.user_email = target_email
    mr.organization_name = context.organization.name
    return mr


# --- Phase 3: Services & Connectors ---


@app.get("/api/v1/services", response_model=list[ServiceRead])
def list_services(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> list[ServiceRead]:
    services = db.scalars(
        select(Service)
        .where(Service.organization_id == context.organization.id)
        .order_by(Service.created_at.desc())
    ).all()
    return [ServiceRead.model_validate(s) for s in services]


@app.post("/api/v1/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> ServiceRead:
    if not context.can("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and owners can register new services.",
        )
    existing = db.scalar(
        select(Service).where(
            Service.organization_id == context.organization.id,
            Service.name == payload.name.strip(),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service '{payload.name}' already exists in this organization.",
        )

    service = Service(
        organization_id=context.organization.id,
        name=payload.name.strip(),
        environment=payload.environment,
        description=payload.description,
        status="active",
    )
    db.add(service)
    db.commit()
    db.refresh(service)

    log_audit_event(
        db,
        organization_id=context.organization.id,
        actor_id=context.user.id,
        resource_type="service",
        resource_id=str(service.id),
        action="service.created",
        result="success",
        metadata={"name": service.name, "environment": service.environment},
    )
    return ServiceRead.model_validate(service)


@app.get("/api/v1/services/{service_id}", response_model=ServiceRead)
def get_service(
    service_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> ServiceRead:
    service = db.scalar(
        select(Service).where(
            Service.id == service_id,
            Service.organization_id == context.organization.id,
        )
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found.",
        )
    return ServiceRead.model_validate(service)


@app.patch("/api/v1/services/{service_id}", response_model=ServiceRead)
def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> ServiceRead:
    if not context.can("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and owners can update services.",
        )
    service = db.scalar(
        select(Service).where(
            Service.id == service_id,
            Service.organization_id == context.organization.id,
        )
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found.",
        )

    if payload.name is not None:
        service.name = payload.name.strip()
    if payload.environment is not None:
        service.environment = payload.environment
    if payload.description is not None:
        service.description = payload.description
    if payload.status is not None:
        service.status = payload.status
    service.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(service)

    log_audit_event(
        db,
        organization_id=context.organization.id,
        actor_id=context.user.id,
        resource_type="service",
        resource_id=str(service.id),
        action="service.updated",
        result="success",
    )
    return ServiceRead.model_validate(service)


@app.post("/api/v1/services/{service_id}/verify-connection", response_model=ServiceVerifyResponse)
def verify_service_connection(
    service_id: uuid.UUID,
    payload: ServiceVerifyRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
) -> ServiceVerifyResponse:
    if not context.can("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and owners can verify connector endpoints.",
        )
    service = db.scalar(
        select(Service).where(
            Service.id == service_id,
            Service.organization_id == context.organization.id,
        )
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found.",
        )

    try:
        validated_url = validate_connector_url(payload.url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSRF Protection: {e}",
        ) from e

    import time
    import urllib.request

    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(
            validated_url, headers={"User-Agent": "AegisOps-Connector/1.0"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as res:
            latency_ms = (time.perf_counter() - t0) * 1000
            st_code = res.status
            success = 200 <= st_code < 400
            log_audit_event(
                db,
                organization_id=context.organization.id,
                actor_id=context.user.id,
                resource_type="connector",
                resource_id=str(service.id),
                action="integration.connection_verified",
                result="success" if success else "failure",
                metadata={"url": validated_url, "status_code": st_code},
            )
            return ServiceVerifyResponse(
                success=success,
                message=f"Endpoint responded with HTTP {st_code}",
                status_code=st_code,
                latency_ms=round(latency_ms, 2),
            )
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        log_audit_event(
            db,
            organization_id=context.organization.id,
            actor_id=context.user.id,
            resource_type="connector",
            resource_id=str(service.id),
            action="integration.connection_verified",
            result="failure",
            metadata={"url": validated_url, "error": str(e)},
        )
        return ServiceVerifyResponse(
            success=False,
            message=f"Connection failed: {e}",
            latency_ms=round(latency_ms, 2),
        )


# --- Phase 3: Distributed Tracing ---


@app.get("/api/v1/traces/{trace_id}", response_model=TraceSummaryRead)
def get_trace(
    trace_id: str,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TraceSummaryRead:
    try:
        clean_id = validate_trace_id(trace_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client = TempoClient()
    summary = client.get_trace_summary(clean_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found in Tempo or has no spans.",
        )
    return summary


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
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    severity: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IncidentListResponse:
    query = select(Incident).where(Incident.organization_id == context.organization.id)
    count_query = select(func.count(Incident.id)).where(
        Incident.organization_id == context.organization.id
    )

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
def get_incident(
    incident_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> IncidentRead:
    incident = db.scalar(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.organization_id == context.organization.id,
        )
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return IncidentRead.model_validate(incident)


@app.get("/api/v1/incidents/{incident_id}/events", response_model=list[IncidentEventRead])
def get_incident_events(
    incident_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[IncidentEventRead]:
    incident = db.scalar(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.organization_id == context.organization.id,
        )
    )
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
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    payload: InvestigationRunCreate | None = None,
) -> InvestigationRunRead:
    if not context.can("member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot launch investigations.",
        )
    body = payload or InvestigationRunCreate()
    incident = db.scalar(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.organization_id == context.organization.id,
        )
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    # Check for an active running investigation on this incident
    active_run = db.scalar(
        select(InvestigationRun).where(
            InvestigationRun.incident_id == incident_id,
            InvestigationRun.organization_id == context.organization.id,
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

    log_audit_event(
        db,
        organization_id=context.organization.id,
        actor_id=context.user.id,
        resource_type="investigation",
        resource_id=str(run.id),
        action="investigation.started",
        result="success",
        metadata={"incident_id": str(incident.id), "model": model_name, "mode": mode},
    )

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
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[InvestigationRunRead]:
    incident = db.scalar(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.organization_id == context.organization.id,
        )
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    runs = db.scalars(
        select(InvestigationRun)
        .where(
            InvestigationRun.incident_id == incident_id,
            InvestigationRun.organization_id == context.organization.id,
        )
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
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> InvestigationRunDetailRead:
    run = db.scalar(
        select(InvestigationRun)
        .options(
            selectinload(InvestigationRun.hypotheses),
            selectinload(InvestigationRun.evidence_items),
        )
        .where(
            InvestigationRun.id == investigation_id,
            InvestigationRun.organization_id == context.organization.id,
        )
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
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[ToolExecutionRead]:
    run = db.scalar(
        select(InvestigationRun).where(
            InvestigationRun.id == investigation_id,
            InvestigationRun.organization_id == context.organization.id,
        )
    )
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
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> EvidenceListResponse:
    run = db.scalar(
        select(InvestigationRun).where(
            InvestigationRun.id == investigation_id,
            InvestigationRun.organization_id == context.organization.id,
        )
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation run '{investigation_id}' not found",
        )

    count_query = (
        select(func.count())
        .select_from(EvidenceItem)
        .where(
            EvidenceItem.run_id == investigation_id,
            EvidenceItem.organization_id == context.organization.id,
        )
    )
    total = db.scalar(count_query) or 0
    items = db.scalars(
        select(EvidenceItem)
        .where(
            EvidenceItem.run_id == investigation_id,
            EvidenceItem.organization_id == context.organization.id,
        )
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
def get_evidence_item(
    evidence_id: str,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> EvidenceItemRead:
    item = db.scalar(
        select(EvidenceItem).where(
            EvidenceItem.evidence_id == evidence_id,
            EvidenceItem.organization_id == context.organization.id,
        )
    )
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
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> InvestigationRunRead:
    if not context.can("member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot cancel investigations.",
        )
    run = db.scalar(
        select(InvestigationRun).where(
            InvestigationRun.id == investigation_id,
            InvestigationRun.organization_id == context.organization.id,
        )
    )
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

        log_audit_event(
            db,
            organization_id=context.organization.id,
            actor_id=context.user.id,
            resource_type="investigation",
            resource_id=str(run.id),
            action="investigation.cancelled",
            result="success",
        )

    return InvestigationRunRead.model_validate(run)
