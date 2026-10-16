import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.orm import Session, selectinload
from starlette.responses import JSONResponse

from apps.api.app.actions import (
    ACTION_CATALOG,
    ProposalExpiredError,
    ProposalHashMismatchError,
    ProposalNotFoundError,
    ProposalPermissionDeniedError,
    ProposalService,
    ProposalStateConflictError,
)
from apps.api.app.auth import (
    TenantContext,
    clear_auth_cookies,
    compute_tenant_webhook_secret,
    create_user_session,
    extract_raw_token,
    get_current_user,
    get_ssrf_safe_opener,
    get_tenant_context,
    hash_password,
    log_audit_event,
    revoke_user_session,
    set_auth_cookies,
    validate_connector_url,
    verify_password,
)
from apps.api.app.correlation import correlate_alert
from apps.api.app.db import get_db
from apps.api.app.integrations.github import ScopedGitHubClient
from apps.api.app.lifecycle import (
    ACTIVE_INCIDENT_STATUSES,
    ConcurrencyConflictError,
    InvalidTransitionError,
    transition_incident,
)
from apps.api.app.models import (
    AlertEvent,
    EvidenceItem,
    Incident,
    IncidentEvent,
    InvestigationRun,
    Membership,
    Organization,
    OutboxEvent,
    Service,
    ServiceHealthObservation,
    ToolExecution,
    User,
)
from apps.api.app.outbox import dispatch_outbox_batch, verify_event_signature
from apps.api.app.rag.models import Document
from apps.api.app.rag.retrieval import HybridRetrievalService
from apps.api.app.rag.service import DocumentIngestionService, ValidationError
from apps.api.app.schemas import (
    ActionCatalogItemRead,
    ActionExecuteRequest,
    ActionExecutionOut,
    ActionProposalCreate,
    ActionProposalRead,
    AlertmanagerWebhookPayload,
    AuthResponse,
    DemoSinkResponse,
    DemoSinkTicketRead,
    DeploymentRecordRead,
    EvidenceItemRead,
    EvidenceListResponse,
    HypothesisRead,
    IncidentEventRead,
    IncidentListResponse,
    IncidentRead,
    IncidentUpdate,
    InvestigationRunCreate,
    InvestigationRunDetailRead,
    InvestigationRunRead,
    LoginRequest,
    MemberAddRequest,
    MembershipRead,
    MetricDataPoint,
    MetricSeries,
    OrganizationCreate,
    OrganizationRead,
    OutboxEventRead,
    OutboxListResponse,
    ProposalApprovalCreate,
    ProposalListResponse,
    ProposalRejectCreate,
    RegisterRequest,
    RetrievedChunkRead,
    RunbookListResponse,
    RunbookRead,
    RunbookSearchRequest,
    RunbookSearchResult,
    RunbookUploadRequest,
    ServiceCreate,
    ServiceHealthObservationRead,
    ServiceMetricsResponse,
    ServiceRead,
    ServiceUpdate,
    ServiceVerifyRequest,
    ServiceVerifyResponse,
    SpanRead,
    ToolExecutionRead,
    TraceSummaryRead,
    UserRead,
)
from apps.api.app.simulation.router import router as simulation_router
from apps.api.app.telemetry.promql import build_service_metrics_queries
from apps.api.app.telemetry.tempo import TempoClient, validate_trace_id
from apps.worker.tasks import (
    ingest_document_task,
    run_investigation_task,
)

logger = logging.getLogger("aegisops.api")


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"


app = FastAPI(title="AegisOps Control Plane", version="0.1.0")

# DEC-331: CORS Configuration with explicit allowed origins and credentials support
allowed_origins_env = os.environ.get("AEGISOPS_ALLOWED_ORIGINS", "")
allowed_origins = [
    origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()
] or [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(simulation_router)


# DEC-331: Centralized Exception Handlers for Domain Errors
@app.exception_handler(ProposalNotFoundError)
def proposal_not_found_handler(request: Request, exc: ProposalNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(ProposalPermissionDeniedError)
def proposal_permission_denied_handler(
    request: Request, exc: ProposalPermissionDeniedError
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})


@app.exception_handler(ProposalStateConflictError)
def proposal_state_conflict_handler(
    request: Request, exc: ProposalStateConflictError
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(ProposalExpiredError)
def proposal_expired_handler(request: Request, exc: ProposalExpiredError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_410_GONE, content={"detail": str(exc)})


@app.exception_handler(ProposalHashMismatchError)
def proposal_hash_mismatch_handler(
    request: Request, exc: ProposalHashMismatchError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)}
    )


@app.exception_handler(ConcurrencyConflictError)
def concurrency_conflict_handler(request: Request, exc: ConcurrencyConflictError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(InvalidTransitionError)
def invalid_transition_handler(request: Request, exc: InvalidTransitionError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)}
    )


DbSession = Annotated[Session, Depends(get_db)]


@app.get("/healthz", response_model=Health)
def healthz() -> Health:
    return Health()


async def check_postgres() -> None:
    async with (
        await psycopg.AsyncConnection.connect(
            os.environ["DATABASE_URL"], connect_timeout=3
        ) as connection,
        connection.cursor() as cursor,
    ):
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
    raw_token, _session = create_user_session(db, user.id, ip, ua)
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
    raw_token, _session = create_user_session(db, user.id, ip, ua)
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
    # DEC-385: aggregate before presentation, never count a paginated incident sample.
    summaries = db.execute(
        select(
            Incident.service_id,
            func.sum(case((Incident.status.not_in(["resolved", "closed"]), 1), else_=0)),
            func.max(Incident.updated_at),
        )
        .where(Incident.organization_id == context.organization.id)
        .group_by(Incident.service_id)
    ).all()
    by_service = {row[0]: (row[1], row[2]) for row in summaries}
    return [
        ServiceRead.model_validate(service).model_copy(
            update={
                "active_incident_count": by_service.get(service.id, (0, None))[0],
                "last_incident_at": by_service.get(service.id, (0, None))[1],
            }
        )
        for service in services
    ]


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

    healthcheck_url = None
    monitoring_status = "unknown"
    if payload.healthcheck_url:
        allow_local = os.environ.get("AEGISOPS_ALLOW_LOCAL_CONNECTOR", "false").lower() in (
            "true",
            "1",
        )
        try:
            healthcheck_url = validate_connector_url(
                payload.healthcheck_url, allow_local_demo=allow_local
            )
            monitoring_status = "configured"
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SSRF Protection: {e}",
            ) from e

    service = Service(
        organization_id=context.organization.id,
        name=payload.name.strip(),
        environment=payload.environment,
        description=payload.description,
        github_repo=payload.github_repo,
        status="active",
        healthcheck_url=healthcheck_url,
        monitoring_status=monitoring_status,
        is_monitored=payload.is_monitored,
        monitoring_interval_seconds=max(10, payload.monitoring_interval_seconds),
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
    if "description" in payload.model_fields_set:
        service.description = payload.description.strip() if payload.description else None
    if payload.status is not None:
        service.status = payload.status
    if "github_repo" in payload.model_fields_set:
        repo_val = payload.github_repo.strip() if payload.github_repo else None
        service.github_repo = repo_val if repo_val else None
    if "current_version" in payload.model_fields_set:
        ver_val = payload.current_version.strip() if payload.current_version else None
        service.current_version = ver_val if ver_val else None
    if "current_commit_sha" in payload.model_fields_set:
        sha_val = payload.current_commit_sha.strip() if payload.current_commit_sha else None
        service.current_commit_sha = sha_val if sha_val else None
    if "healthcheck_url" in payload.model_fields_set:
        url_val = payload.healthcheck_url.strip() if payload.healthcheck_url else ""
        if not url_val:
            service.healthcheck_url = None
            service.monitoring_status = "unknown"
        else:
            allow_local = os.environ.get("AEGISOPS_ALLOW_LOCAL_CONNECTOR", "false").lower() in (
                "true",
                "1",
            )
            try:
                service.healthcheck_url = validate_connector_url(
                    url_val, allow_local_demo=allow_local
                )
                if service.monitoring_status == "unknown":
                    service.monitoring_status = "configured"
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"SSRF Protection: {e}",
                ) from e
    if payload.monitoring_status is not None:
        service.monitoring_status = payload.monitoring_status
    if payload.is_monitored is not None:
        service.is_monitored = payload.is_monitored
    if payload.monitoring_interval_seconds is not None:
        service.monitoring_interval_seconds = max(10, payload.monitoring_interval_seconds)
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

    allow_local = os.environ.get("AEGISOPS_ALLOW_LOCAL_CONNECTOR", "false").lower() in ("true", "1")
    try:
        validated_url = validate_connector_url(payload.url, allow_local_demo=allow_local)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSRF Protection: {e}",
        ) from e

    t0 = time.perf_counter()
    now = datetime.now(UTC)
    threshold = service.failure_threshold or 3
    fp = hashlib.sha256(f"healthcheck:{service.id}".encode()).hexdigest()[:32]

    try:
        req = urllib.request.Request(
            validated_url, headers={"User-Agent": "AegisOps-Connector/1.0"}
        )
        opener = get_ssrf_safe_opener(allow_local_demo=allow_local)
        with opener.open(req, timeout=3.0) as res:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            st_code = res.status
            success = 200 <= st_code < 400

            service.healthcheck_url = validated_url
            service.last_verified_at = now
            service.last_probe_status_code = st_code
            service.last_probe_latency_ms = latency_ms

            if success:
                obs_status = "reachable"
                service.monitoring_status = "reachable"
                service.last_success_at = now
                service.consecutive_failures = 0
                service.consecutive_successes += 1
                service.last_probe_error = None

                # Manual recovery: resolve active healthcheck outage incidents for this service
                active_incidents = db.scalars(
                    select(Incident).where(
                        Incident.service_id == service.id,
                        Incident.organization_id == context.organization.id,
                        Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
                        Incident.fingerprint == fp,
                    )
                ).all()
                for active_incident in active_incidents:
                    active_incident.status = "resolved"
                    active_incident.updated_at = now
                    active_incident.resolved_at = now
                    evt = IncidentEvent(
                        incident_id=active_incident.id,
                        event_type="resolved",
                        actor=f"user:{context.user.email}",
                        occurred_at=now,
                        payload={
                            "message": (
                                f"Service recovered via manual connection recheck. "
                                f"HTTP {st_code} ({latency_ms} ms)."
                            )
                        },
                    )
                    db.add(evt)
            else:
                service.consecutive_failures += 1
                service.consecutive_successes = 0
                service.last_probe_error = f"HTTP {st_code}"

                if service.consecutive_failures < threshold:
                    obs_status = "degraded"
                    service.monitoring_status = "degraded"
                else:
                    obs_status = "down"
                    service.monitoring_status = "down"

                    existing_incident = db.scalar(
                        select(Incident).where(
                            Incident.service_id == service.id,
                            Incident.organization_id == context.organization.id,
                            Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
                            Incident.fingerprint == fp,
                        )
                    )
                    if not existing_incident:
                        outage_inc = Incident(
                            organization_id=context.organization.id,
                            service_id=service.id,
                            title=f"Service Outage: {service.name} unreachable",
                            severity="critical",
                            status="open",
                            environment=service.environment,
                            fingerprint=fp,
                            started_at=now,
                        )
                        db.add(outage_inc)
                        db.flush()
                        db.add(
                            IncidentEvent(
                                incident_id=outage_inc.id,
                                event_type="created",
                                actor=f"user:{context.user.email}",
                                occurred_at=now,
                                payload={
                                    "message": (
                                        f"Manual connection recheck failed with HTTP {st_code}."
                                    )
                                },
                            )
                        )

            obs = ServiceHealthObservation(
                service_id=service.id,
                organization_id=context.organization.id,
                observed_at=now,
                status=obs_status,
                status_code=st_code,
                latency_ms=latency_ms,
                error_message=None if success else f"HTTP {st_code}",
            )
            db.add(obs)
            db.commit()
            db.refresh(service)

            log_audit_event(
                db,
                organization_id=context.organization.id,
                actor_id=context.user.id,
                resource_type="connector",
                resource_id=str(service.id),
                action="integration.connection_verified",
                result="success" if success else "failure",
                metadata={"url": validated_url, "status_code": st_code, "latency_ms": latency_ms},
            )
            return ServiceVerifyResponse(
                success=success,
                message=f"Endpoint responded with HTTP {st_code}",
                status_code=st_code,
                latency_ms=latency_ms,
                monitoring_status=service.monitoring_status,
                last_verified_at=service.last_verified_at,
            )
    except ValueError as e:
        # SSRF violation during redirect or socket connection
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSRF Protection: {e}",
        ) from e
    except Exception as e:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        service.healthcheck_url = validated_url
        service.last_verified_at = now
        service.last_probe_latency_ms = latency_ms
        service.last_probe_error = str(e)[:500]
        service.consecutive_failures += 1
        service.consecutive_successes = 0

        if service.consecutive_failures < threshold:
            obs_status = "degraded"
            service.monitoring_status = "degraded"
        else:
            obs_status = "down"
            service.monitoring_status = "down"

            existing_incident = db.scalar(
                select(Incident).where(
                    Incident.service_id == service.id,
                    Incident.organization_id == context.organization.id,
                    Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
                    Incident.fingerprint == fp,
                )
            )
            if not existing_incident:
                outage_inc = Incident(
                    organization_id=context.organization.id,
                    service_id=service.id,
                    title=f"Service Outage: {service.name} unreachable",
                    severity="critical",
                    status="open",
                    environment=service.environment,
                    fingerprint=fp,
                    started_at=now,
                )
                db.add(outage_inc)
                db.flush()
                db.add(
                    IncidentEvent(
                        incident_id=outage_inc.id,
                        event_type="created",
                        actor=f"user:{context.user.email}",
                        occurred_at=now,
                        payload={
                            "message": (
                                f"Manual connection recheck failed with error: {str(e)[:500]}"
                            )
                        },
                    )
                )

        obs = ServiceHealthObservation(
            service_id=service.id,
            organization_id=context.organization.id,
            observed_at=now,
            status=obs_status,
            latency_ms=latency_ms,
            error_message=str(e)[:500],
        )
        db.add(obs)
        db.commit()
        db.refresh(service)

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
            latency_ms=latency_ms,
            monitoring_status=service.monitoring_status,
            last_verified_at=service.last_verified_at,
        )


@app.get(
    "/api/v1/services/{service_id}/health-observations",
    response_model=list[ServiceHealthObservationRead],
)
def list_service_health_observations(
    service_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ServiceHealthObservationRead]:
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
    stmt = (
        select(ServiceHealthObservation)
        .where(
            ServiceHealthObservation.service_id == service_id,
            ServiceHealthObservation.organization_id == context.organization.id,
        )
        .order_by(desc(ServiceHealthObservation.observed_at))
        .limit(limit)
    )
    observations = db.scalars(stmt).all()
    return [ServiceHealthObservationRead.model_validate(o) for o in observations]


@app.get(
    "/api/v1/services/{service_id}/metrics",
    response_model=ServiceMetricsResponse,
)
def get_service_metrics(
    service_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
    window: Annotated[Literal["15m", "1h", "6h", "24h"], Query()] = "1h",
) -> ServiceMetricsResponse:
    """Tenant-safe bounded metric queries for application performance analytics (AUD-011)."""
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

    window_configs = {
        "15m": (900, 15),
        "1h": (3600, 60),
        "6h": (21600, 300),
        "24h": (86400, 1200),
    }
    duration_sec, step_sec = window_configs.get(window, (3600, 60))
    end_ts = time.time()
    start_ts = end_ts - duration_sec

    prom_url = os.environ.get(
        "AEGISOPS_PROM_URL",
        "http://prometheus:9090" if os.environ.get("IN_DOCKER") else "http://127.0.0.1:9090",
    )

    is_demo = context.organization.name.lower() in ("demo", "demo org", "demo organization")
    queries = build_service_metrics_queries(
        service_id=service.id,
        organization_id=context.organization.id,
        service_name=service.name,
        is_demo_org=is_demo,
    )

    metrics_result: dict[str, MetricSeries] = {}
    any_instrumented = False

    for m_name, (promql, unit) in queries.items():
        try:
            params = {
                "query": promql,
                "start": start_ts,
                "end": end_ts,
                "step": f"{step_sec}s",
            }
            url = f"{prom_url}/api/v1/query_range?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "AegisOps-API/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = data.get("data", {}).get("result", [])
            points: list[MetricDataPoint] = []
            if results:
                raw_values = results[0].get("values", [])
                for ts, val_str in raw_values:
                    try:
                        val = float(val_str)
                        if not math.isnan(val) and not math.isinf(val):
                            points.append(MetricDataPoint(timestamp=float(ts), value=round(val, 2)))
                    except (
                        ValueError,
                        TypeError,
                    ):
                        pass

            current_val = points[-1].value if points else None
            if points:
                any_instrumented = True
            metrics_result[m_name] = MetricSeries(
                name=m_name,
                unit=unit,
                current_value=current_val,
                points=points,
            )
        except Exception as err:
            logger.debug(f"Failed to query Prometheus for {m_name}: {err}")
            metrics_result[m_name] = MetricSeries(
                name=m_name,
                unit=unit,
                current_value=None,
                points=[],
            )

    if any_instrumented:
        return ServiceMetricsResponse(
            service_id=service.id,
            service_name=service.name,
            window=window,
            is_instrumented=True,
            status="instrumented",
            message="Live Prometheus telemetry active.",
            metrics=metrics_result,
        )
    else:
        return ServiceMetricsResponse(
            service_id=service.id,
            service_name=service.name,
            window=window,
            is_instrumented=False,
            status="uninstrumented",
            message=(
                f"No Prometheus metrics scraped for '{service.name}'. "
                "See documentation to configure Prometheus or OpenTelemetry collector."
            ),
            metrics=metrics_result,
        )


# --- Phase 3: Distributed Tracing ---


@app.get("/api/v1/traces/{trace_id}", response_model=TraceSummaryRead)
def get_trace(
    trace_id: str,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    db: DbSession,
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

    # Multi-tenant trace authorization: enforce trustworthy provenance and span-level isolation
    org_services = db.scalars(
        select(Service).where(Service.organization_id == context.organization.id)
    ).all()
    authorized_service_names = {s.name.lower(): str(s.id).lower() for s in org_services}
    authorized_service_ids = {str(s.id).lower() for s in org_services}
    caller_org_id = str(context.organization.id).lower()

    is_demo = context.organization.name.lower() in ("demo", "demo org", "demo organization")
    if is_demo:
        authorized_service_names["shop-api"] = str(DEFAULT_DEMO_SERVICE_ID).lower()
        authorized_service_ids.add(str(DEFAULT_DEMO_SERVICE_ID).lower())

    authorized_spans: list[SpanRead] = []
    for s in summary.spans:
        # 1. Require service name matching an authorized service of the organization
        s_name = s.service_name.lower() if s.service_name else ""
        if not s_name or s_name not in authorized_service_names:
            continue

        # 2. Check explicit tenant provenance in span/resource attributes
        span_org = (
            s.attributes.get("organization_id")
            or s.attributes.get("organization.id")
            or s.attributes.get("tenant.id")
            or s.attributes.get("tenant_id")
        )
        if span_org and str(span_org).lower() != caller_org_id:
            # Foreign organization provenance: reject span
            continue

        # 3. Check explicit service provenance in span/resource attributes
        span_svc_id = s.attributes.get("service_id") or s.attributes.get("service.id")
        if span_svc_id:
            if str(span_svc_id).lower() not in authorized_service_ids:
                # Foreign service ID provenance: reject span
                continue
            expected_svc_id = authorized_service_names.get(s_name)
            if expected_svc_id and expected_svc_id != str(span_svc_id).lower():
                # Service ID / name mismatch: reject span
                continue

        authorized_spans.append(s)

    # Fail closed: if no authorized spans belong to the caller's organization, 404
    if not authorized_spans:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{clean_id}' not found in Tempo or has no spans.",
        )

    # Reconstruct sanitized summary exposing ONLY authorized spans
    earliest = min(s.start_time_unix_nano for s in authorized_spans)
    latest = max(s.end_time_unix_nano for s in authorized_spans)
    dur_ms = max(0.0, (latest - earliest) / 1_000_000)
    error_count = sum(1 for s in authorized_spans if s.status_code == "ERROR")

    return TraceSummaryRead(
        trace_id=clean_id,
        service_name=authorized_spans[0].service_name,
        root_operation=authorized_spans[0].name,
        duration_ms=round(dur_ms, 2),
        span_count=len(authorized_spans),
        error_span_count=error_count,
        spans=authorized_spans,
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


def resolve_webhook_target_service(
    session: Session,
    alert_labels: dict[str, str],
    target_org_override: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID, str]:
    """Resolve organization and service for incoming alert.

    Strictly requires an explicit, authenticated organization and pre-registered service.
    Rejects missing target organization, unknown organization, mismatched identifiers,
    and unknown services (no automatic creation).
    """
    raw_target_org = (
        target_org_override
        or alert_labels.get("organization")
        or alert_labels.get("organization_id")
    )
    if not raw_target_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing target organization in webhook alert payload or request parameters.",
        )

    # Check for mismatch if both override and label are specified
    label_org = alert_labels.get("organization") or alert_labels.get("organization_id")
    if (
        target_org_override
        and label_org
        and str(target_org_override).strip() != str(label_org).strip()
    ):
        try:
            override_uuid = uuid.UUID(str(target_org_override).strip())
            label_uuid = uuid.UUID(str(label_org).strip())
            if override_uuid != label_uuid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Target organization mismatch: request specifies '{target_org_override}' "
                        f"but alert label specifies '{label_org}'"
                    ),
                )
        except ValueError:
            if str(target_org_override).strip().lower() != str(label_org).strip().lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Target organization mismatch: request specifies '{target_org_override}' "
                        f"but alert label specifies '{label_org}'"
                    ),
                ) from None

    # Look up organization by UUID or Name
    org = None
    try:
        org_uuid = uuid.UUID(str(raw_target_org).strip())
        org = session.scalar(select(Organization).where(Organization.id == org_uuid))
    except ValueError:
        org = session.scalar(
            select(Organization).where(Organization.name == str(raw_target_org).strip())
        )

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target organization '{raw_target_org}' not found.",
        )

    service_name = alert_labels.get("service") or alert_labels.get("app")
    if not service_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is missing required 'service' or 'app' label.",
        )

    svc = session.scalar(
        select(Service).where(
            Service.organization_id == org.id,
            Service.name == service_name,
        )
    )
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Service '{service_name}' not found under organization '{org.name}'. "
                "Automatic service creation from untrusted alerts is disabled."
            ),
        )

    env = alert_labels.get("environment") or alert_labels.get("env") or svc.environment
    return org.id, svc.id, env


DEFAULT_DEMO_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000064")
DEFAULT_DEMO_SERVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000066")


def get_or_create_demo_scope(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    org = session.scalar(
        select(Organization).where(
            (Organization.name == "AegisOps Demo") | (Organization.id == DEFAULT_DEMO_ORG_ID)
        )
    )
    if not org:
        org = Organization(id=DEFAULT_DEMO_ORG_ID, name="AegisOps Demo")
        session.add(org)
        session.flush()
    svc = session.scalar(
        select(Service).where(
            Service.organization_id == org.id,
            (Service.name == "shop-api") | (Service.id == DEFAULT_DEMO_SERVICE_ID),
        )
    )
    if not svc:
        svc = Service(
            id=DEFAULT_DEMO_SERVICE_ID,
            organization_id=org.id,
            name="shop-api",
            environment="staging",
        )
        session.add(svc)
        session.flush()
    return org.id, svc.id


@app.post("/api/v1/webhooks/alertmanager", status_code=status.HTTP_200_OK)
@app.post("/api/v1/webhooks/alertmanager/{target_org}", status_code=status.HTTP_200_OK)
async def alertmanager_webhook(
    request: Request,
    payload: AlertmanagerWebhookPayload,
    db: DbSession,
    target_org: str | None = None,
    organization: Annotated[str | None, Query()] = None,
    organization_id: Annotated[str | None, Query()] = None,
    x_organization: Annotated[str | None, Header(alias="x-organization")] = None,
    x_organization_id: Annotated[str | None, Header(alias="x-organization-id")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 524_288:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload exceeds maximum permitted size of 512KB",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer authentication header",
        )
    token = authorization.removeprefix("Bearer ").strip()

    req_target_org = (
        target_org or organization or organization_id or x_organization or x_organization_id
    )

    # Check if authorized by global ALERTMANAGER_SECRET
    is_global_secret = hmac.compare_digest(token, ALERTMANAGER_SECRET)

    # If not global secret, must authenticate via per-tenant secret
    authenticated_org_id: uuid.UUID | None = None
    if not is_global_secret:
        cand_org_str = req_target_org
        if not cand_org_str and payload.alerts:
            cand_org_str = payload.alerts[0].labels.get("organization") or payload.alerts[
                0
            ].labels.get("organization_id")

        if not cand_org_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing target organization in webhook request.",
            )

        cand_org = None
        try:
            cand_uuid = uuid.UUID(str(cand_org_str).strip())
            cand_org = db.scalar(select(Organization).where(Organization.id == cand_uuid))
        except ValueError:
            cand_org = db.scalar(
                select(Organization).where(Organization.name == str(cand_org_str).strip())
            )

        if not cand_org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target organization '{cand_org_str}' not found.",
            )

        expected_tenant_secret = compute_tenant_webhook_secret(cand_org.id)
        if not hmac.compare_digest(token, expected_tenant_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized webhook credentials for target organization",
            )
        authenticated_org_id = cand_org.id

    created_count = 0
    resolved_count = 0
    duplicate_count = 0
    correlated_count = 0

    for alert in payload.alerts:
        org_id, svc_id, env = resolve_webhook_target_service(
            db, alert.labels, target_org_override=req_target_org
        )

        # If authenticated with tenant token, prevent cross-tenant alert injection
        if authenticated_org_id and org_id != authenticated_org_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook token does not match target alert organization",
            )

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

        # Correlate alert into incident via deterministic correlation engine
        _inc, action = correlate_alert(
            db=db,
            org_id=org_id,
            svc_id=svc_id,
            alert=alert,
            environment=env,
            actor="alertmanager",
        )
        if action == "created":
            created_count += 1
        elif action == "duplicate":
            duplicate_count += 1
        elif action == "correlated":
            correlated_count += 1
        elif action == "resolved":
            resolved_count += 1

    db.commit()
    return {
        "status": "success",
        "processed_alerts": len(payload.alerts),
        "incidents_created": created_count,
        "incidents_resolved": resolved_count,
        "duplicates_skipped": duplicate_count,
        "alerts_correlated": correlated_count,
    }


@app.get("/api/v1/incidents", response_model=IncidentListResponse)
def list_incidents(
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    service_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    severity: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IncidentListResponse:
    query = select(Incident).where(Incident.organization_id == context.organization.id)
    count_query = select(func.count(Incident.id)).where(
        Incident.organization_id == context.organization.id
    )

    if service_id is not None:
        get_service(service_id, context, db)
        query = query.where(Incident.service_id == service_id)
        count_query = count_query.where(Incident.service_id == service_id)

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


@app.patch("/api/v1/incidents/{incident_id}", response_model=IncidentRead)
def update_incident(
    incident_id: uuid.UUID,
    payload: IncidentUpdate,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> IncidentRead:
    if not context.can("member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot modify incident status.",
        )
    incident = db.scalar(
        select(Incident)
        .where(
            Incident.id == incident_id,
            Incident.organization_id == context.organization.id,
        )
        .with_for_update()
    )
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    old_status = incident.status
    try:
        transition_incident(
            incident,
            target_status=payload.status,
            actor=context.user.email,
            reason=payload.reason,
            expected_version=payload.expected_version,
            db=db,
        )
        db.commit()
        db.refresh(incident)

        log_audit_event(
            db,
            organization_id=context.organization.id,
            actor_id=context.user.id,
            resource_type="incident",
            resource_id=str(incident.id),
            action=f"incident.{incident.status}",
            result="success",
            metadata={
                "from_status": old_status,
                "to_status": incident.status,
                "reason": payload.reason or "",
                "version": incident.version,
            },
        )
        return IncidentRead.model_validate(incident)
    except InvalidTransitionError as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err
    except ConcurrencyConflictError as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err


@app.get(
    "/api/v1/services/{service_id}/deployments",
    response_model=list[DeploymentRecordRead],
)
def get_service_deployments(
    service_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> list[DeploymentRecordRead]:
    service = db.scalar(
        select(Service).where(
            Service.id == service_id,
            Service.organization_id == context.organization.id,
        )
    )
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found",
        )

    repo = service.github_repo or "AegisOps/shop-api"
    client = ScopedGitHubClient()
    try:
        raw_deployments = client.get_recent_deployments(
            repo, environment=service.environment, limit=limit
        )
        records = []
        for d in raw_deployments:
            deployed_at_val = d.get("deployed_at")
            if isinstance(deployed_at_val, str):
                deployed_at_dt = datetime.fromisoformat(deployed_at_val.replace("Z", "+00:00"))
            elif isinstance(deployed_at_val, datetime):
                deployed_at_dt = deployed_at_val
            else:
                deployed_at_dt = datetime.now(UTC)

            records.append(
                DeploymentRecordRead(
                    deployment_id=str(d.get("deployment_id", "")),
                    repository=d.get("repository", repo),
                    commit_sha=d.get("commit_sha", ""),
                    version=d.get("version"),
                    environment=d.get("environment", service.environment),
                    deployed_at=deployed_at_dt,
                    source=d.get("source", "github"),
                    is_deployment=bool(d.get("is_deployment", True)),
                    message=d.get("message"),
                    author=d.get("author"),
                )
            )
        return records
    except Exception as err:
        logger.warning("Failed to fetch deployments for %s: %s", repo, err)
        return []


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


# --- Phase 5 RAG Runbook Endpoints ---


def _doc_to_read(doc: Document, chunk_count: int | None = None) -> RunbookRead:
    count = chunk_count if chunk_count is not None else (len(doc.chunks) if doc.chunks else 0)
    return RunbookRead(
        id=doc.id,
        organization_id=doc.organization_id,
        service_id=doc.service_id,
        filename=doc.filename,
        title=doc.title,
        content_type=doc.content_type,
        checksum=doc.checksum,
        version=doc.version,
        status=doc.status,
        embedding_model_id=doc.embedding_model_id,
        embedding_dimension=doc.embedding_dimension,
        chunk_count=count,
        error_code=doc.error_code,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        indexed_at=doc.indexed_at,
        deleted_at=doc.deleted_at,
    )


@app.get("/api/v1/runbooks", response_model=RunbookListResponse)
def list_runbooks(
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    service_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> RunbookListResponse:
    conditions = [
        Document.organization_id == context.organization.id,
        Document.deleted_at.is_(None),
    ]
    if service_id is not None:
        conditions.append(Document.service_id == service_id)

    total = db.scalar(select(func.count(Document.id)).where(and_(*conditions))) or 0
    docs = list(
        db.scalars(
            select(Document)
            .where(and_(*conditions))
            .options(selectinload(Document.chunks))
            .order_by(Document.updated_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )

    items = [_doc_to_read(d) for d in docs]
    return RunbookListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.post("/api/v1/runbooks", response_model=RunbookRead, status_code=status.HTTP_201_CREATED)
async def upload_runbook(
    payload: RunbookUploadRequest,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> RunbookRead:
    if not context.can("member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot upload runbooks.",
        )
    if payload.service_id:
        svc = db.scalar(
            select(Service).where(
                Service.id == payload.service_id,
                Service.organization_id == context.organization.id,
            )
        )
        if not svc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{payload.service_id}' not found in organization",
            )

    service = DocumentIngestionService(db)
    try:
        doc = service.create_pending_document(
            organization_id=context.organization.id,
            filename=payload.filename,
            content=payload.content,
            service_id=payload.service_id,
            created_by=context.user.id,
            title=payload.title,
        )
    except ValidationError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        ) from ve

    # Ingestion dispatch
    use_celery = os.environ.get("AEGISOPS_USE_CELERY", "1") == "1"
    dispatched_async = False
    if use_celery:
        try:
            ingest_document_task.delay(str(doc.id))
            dispatched_async = True
        except Exception as exc:
            logger.warning(
                f"Could not enqueue Celery document ingestion ({exc}); executing synchronously"
            )

    if not dispatched_async:
        doc = await service.process_document_ingestion(doc.id)

    log_audit_event(
        db,
        organization_id=context.organization.id,
        actor_id=context.user.id,
        resource_type="runbook",
        resource_id=str(doc.id),
        action="runbook.uploaded",
        result="success",
        metadata={"filename": doc.filename, "version": doc.version},
    )
    return _doc_to_read(doc)


@app.get("/api/v1/runbooks/{runbook_id}", response_model=RunbookRead)
def get_runbook(
    runbook_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> RunbookRead:
    doc = db.scalar(
        select(Document)
        .where(
            Document.id == runbook_id,
            Document.organization_id == context.organization.id,
            Document.deleted_at.is_(None),
        )
        .options(selectinload(Document.chunks))
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )
    return _doc_to_read(doc)


@app.delete("/api/v1/runbooks/{runbook_id}")
def delete_runbook(
    runbook_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> dict[str, Any]:
    if not context.can("member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot delete runbooks.",
        )
    service = DocumentIngestionService(db)
    success = service.soft_delete_document(runbook_id, context.organization.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found or already deleted",
        )

    log_audit_event(
        db,
        organization_id=context.organization.id,
        actor_id=context.user.id,
        resource_type="runbook",
        resource_id=str(runbook_id),
        action="runbook.deleted",
        result="success",
    )
    return {"status": "deleted", "id": str(runbook_id)}


@app.post("/api/v1/runbooks/{runbook_id}/reindex", response_model=RunbookRead)
async def reindex_runbook(
    runbook_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> RunbookRead:
    if not context.can("member"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot reindex runbooks.",
        )
    doc = db.scalar(
        select(Document).where(
            Document.id == runbook_id,
            Document.organization_id == context.organization.id,
            Document.deleted_at.is_(None),
        )
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )

    service = DocumentIngestionService(db)
    doc = await service.process_document_ingestion(doc.id)

    log_audit_event(
        db,
        organization_id=context.organization.id,
        actor_id=context.user.id,
        resource_type="runbook",
        resource_id=str(doc.id),
        action="runbook.reindexed",
        result="success",
    )
    return _doc_to_read(doc)


@app.get("/api/v1/runbooks/{runbook_id}/versions", response_model=list[RunbookRead])
def get_runbook_versions(
    runbook_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[RunbookRead]:
    target = db.scalar(
        select(Document).where(
            Document.id == runbook_id,
            Document.organization_id == context.organization.id,
        )
    )
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook '{runbook_id}' not found",
        )

    versions = list(
        db.scalars(
            select(Document)
            .where(
                Document.organization_id == context.organization.id,
                Document.filename == target.filename,
            )
            .options(selectinload(Document.chunks))
            .order_by(Document.version.desc())
        ).all()
    )
    return [_doc_to_read(d) for d in versions]


@app.post("/api/v1/runbooks/search", response_model=RunbookSearchResult)
async def search_runbooks(
    payload: RunbookSearchRequest,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> RunbookSearchResult:
    retrieval_service = HybridRetrievalService(db)
    res = await retrieval_service.search(
        organization_id=context.organization.id,
        query=payload.query,
        service_id=payload.service_id,
        limit=payload.limit,
        mode=payload.mode,
    )
    return RunbookSearchResult(
        query=res.query,
        mode=res.mode,
        results=[
            RetrievedChunkRead(
                evidence_id=c.evidence_id,
                document_id=c.document_id,
                chunk_id=c.chunk_id,
                document_version=c.document_version,
                title=c.title,
                section_title=c.section_title,
                section_path=c.section_path,
                content=c.content,
                content_hash=c.content_hash,
                relevance_score=c.relevance_score,
                source_type=c.source_type,
            )
            for c in res.results
        ],
        total_candidates=res.total_candidates,
    )


# -----------------------------------------------------------------------------
# Phase 6: Automation, Outbox Deliveries, and Demo Sink (DEC-300-DEC-304, DEC-315)
# -----------------------------------------------------------------------------

_demo_sink_processed_keys: set[str] = set()
_demo_sink_tickets: list[dict[str, Any]] = []


@app.post("/api/v1/automations/demo-sink", response_model=DemoSinkResponse)
async def receive_demo_sink_webhook(
    request: Request,
    x_aegisops_signature: Annotated[str | None, Header(alias="x-aegisops-signature")] = None,
    x_aegisops_timestamp: Annotated[str | None, Header(alias="x-aegisops-timestamp")] = None,
    x_aegisops_event_id: Annotated[str | None, Header(alias="x-aegisops-event-id")] = None,
    x_aegisops_key_id: Annotated[str | None, Header(alias="x-aegisops-key-id")] = None,
) -> DemoSinkResponse:
    """Authenticated, replay-protected demo notification sink (DEC-303, DEC-304, DEC-315)."""
    raw_body = await request.body()
    if not x_aegisops_signature or not x_aegisops_timestamp or not x_aegisops_event_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Missing required signature headers "
                "(X-AegisOps-Signature, X-AegisOps-Timestamp, X-AegisOps-Event-ID)"
            ),
        )

    is_valid, reason = verify_event_signature(
        payload_bytes=raw_body,
        event_id=x_aegisops_event_id,
        timestamp_str=x_aegisops_timestamp,
        signature=x_aegisops_signature,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Webhook signature verification failed: {reason}",
        )

    try:
        body_json = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {exc}",
        ) from exc

    # Durable receiver-side idempotency deduplication (DEC-304)
    idempotency_key = body_json.get("idempotency_key") or x_aegisops_event_id
    if idempotency_key in _demo_sink_processed_keys:
        return DemoSinkResponse(
            status="duplicate_ignored",
            event_id=x_aegisops_event_id,
            ticket_id=None,
            message="Event already processed idempotently; duplicate delivery ignored",
        )

    _demo_sink_processed_keys.add(idempotency_key)
    ticket_id = f"TICKET-{len(_demo_sink_tickets) + 1:04d}"
    event_type = body_json.get("event_type", "unknown")
    data = body_json.get("data", {})
    summary = (
        data.get("title") or data.get("summary") or f"Event {event_type} on {x_aegisops_event_id}"
    )

    _demo_sink_tickets.append(
        {
            "ticket_id": ticket_id,
            "event_id": x_aegisops_event_id,
            "event_type": event_type,
            "received_at": datetime.now(UTC),
            "summary": summary,
        }
    )

    return DemoSinkResponse(
        status="accepted",
        event_id=x_aegisops_event_id,
        ticket_id=ticket_id,
        message="Demo ticket created successfully",
    )


@app.get("/api/v1/automations/demo-sink/tickets", response_model=list[DemoSinkTicketRead])
def list_demo_sink_tickets() -> list[DemoSinkTicketRead]:
    return [DemoSinkTicketRead(**t) for t in _demo_sink_tickets]


@app.post("/api/v1/automations/demo-sink/reset")
def reset_demo_sink() -> dict[str, str]:
    _demo_sink_processed_keys.clear()
    _demo_sink_tickets.clear()
    return {"status": "reset", "message": "Demo sink tickets and idempotency cache cleared"}


@app.get("/api/v1/automations/deliveries", response_model=OutboxListResponse)
def list_outbox_deliveries(
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OutboxListResponse:
    query = (
        select(OutboxEvent)
        .where(OutboxEvent.organization_id == context.organization.id)
        .order_by(desc(OutboxEvent.created_at))
    )
    if status_filter:
        query = query.where(OutboxEvent.status == status_filter)

    events = list(db.scalars(query.offset(offset).limit(limit)).all())
    return OutboxListResponse(
        items=[OutboxEventRead.model_validate(e) for e in events],
        total=len(events),
    )


@app.get("/api/v1/automations/deliveries/{delivery_id}", response_model=OutboxEventRead)
def get_outbox_delivery(
    delivery_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> OutboxEventRead:
    event = db.scalar(
        select(OutboxEvent).where(
            OutboxEvent.id == delivery_id,
            OutboxEvent.organization_id == context.organization.id,
        )
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outbox delivery record not found in active organization",
        )
    return OutboxEventRead.model_validate(event)


@app.post("/api/v1/automations/deliveries/dispatch")
def trigger_outbox_dispatch(
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    batch_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    """Trigger an immediate outbox dispatch batch (DEC-301)."""
    return dispatch_outbox_batch(db, batch_size=batch_size)


# -----------------------------------------------------------------------------
# Phase 6: Action Catalog and Remediation Proposals (DEC-308-DEC-312)
# -----------------------------------------------------------------------------


@app.get("/api/v1/actions/catalog", response_model=list[ActionCatalogItemRead])
def list_action_catalog(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> list[ActionCatalogItemRead]:
    """List permitted non-executable remediation proposal types in catalog (DEC-308)."""
    return [
        ActionCatalogItemRead(
            action_catalog_id=item.action_catalog_id,
            name=item.name,
            description=item.description,
            applicable_environments=list(item.applicable_environments),
            risk_classification=item.risk_classification,
            required_role=item.required_role,
            default_expiry_seconds=item.default_expiry_seconds,
        )
        for item in ACTION_CATALOG.values()
    ]


@app.post(
    "/api/v1/actions/proposals",
    response_model=ActionProposalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_action_proposal(
    payload: ActionProposalCreate,
    request: Request,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> ActionProposalRead:
    """Create a policy-governed immutable remediation proposal (DEC-308, DEC-309)."""
    service = ProposalService(db, context)
    client_ip = request.client.host if request.client else None
    try:
        proposal = service.create_proposal(payload, ip_address=client_ip)
        return ActionProposalRead.model_validate(proposal)
    except ProposalNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@app.get("/api/v1/actions/proposals", response_model=ProposalListResponse)
def list_action_proposals(
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    service_id: Annotated[uuid.UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProposalListResponse:
    """List proposals for active organization with lazy expiry evaluation (DEC-311)."""
    service = ProposalService(db, context)
    items, total = service.list_proposals(
        service_id=service_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ProposalListResponse(
        items=[ActionProposalRead.model_validate(p) for p in items],
        total=total,
    )


@app.get("/api/v1/actions/proposals/{proposal_id}", response_model=ActionProposalRead)
def get_action_proposal(
    proposal_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> ActionProposalRead:
    """Retrieve action proposal detail with tenant isolation (DEC-309)."""
    service = ProposalService(db, context)
    try:
        proposal = service.get_proposal(proposal_id)
        return ActionProposalRead.model_validate(proposal)
    except ProposalNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err


@app.post("/api/v1/actions/proposals/{proposal_id}/approve", response_model=ActionProposalRead)
def approve_action_proposal(
    proposal_id: uuid.UUID,
    payload: ProposalApprovalCreate,
    request: Request,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> ActionProposalRead:
    """Approve an exact immutable proposal payload (DEC-309, DEC-310).

    Zero execution occurs in Phase 6 (DEC-312).
    """
    service = ProposalService(db, context)
    client_ip = request.client.host if request.client else None
    try:
        approved = service.approve_proposal(proposal_id, payload, ip_address=client_ip)
        return ActionProposalRead.model_validate(approved)
    except ProposalNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ProposalPermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except ProposalExpiredError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except ProposalHashMismatchError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except ProposalStateConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err


@app.post("/api/v1/actions/proposals/{proposal_id}/reject", response_model=ActionProposalRead)
def reject_action_proposal(
    proposal_id: uuid.UUID,
    payload: ProposalRejectCreate,
    request: Request,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> ActionProposalRead:
    """Reject a proposed action with reason comment (DEC-310)."""
    service = ProposalService(db, context)
    client_ip = request.client.host if request.client else None
    try:
        rejected = service.reject_proposal(proposal_id, payload, ip_address=client_ip)
        return ActionProposalRead.model_validate(rejected)
    except ProposalNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ProposalPermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except ProposalStateConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err


# Phase 7: Controlled Remediation Execution (DEC-320-DEC-322)


@app.post("/api/v1/actions/proposals/{proposal_id}/execute", response_model=ActionExecutionOut)
def execute_action_proposal(
    proposal_id: uuid.UUID,
    request: Request,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    payload: ActionExecuteRequest | None = None,
) -> ActionExecutionOut:
    """Atomically claim and execute an approved remediation action (DEC-320, DEC-321)."""
    service = ProposalService(db, context)
    client_ip = request.client.host if request.client else None
    idempotency_key = payload.idempotency_key if payload else None
    try:
        execution = service.execute_proposal(
            proposal_id,
            idempotency_key=idempotency_key,
            ip_address=client_ip,
        )
        return ActionExecutionOut.model_validate(execution)
    except ProposalNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ProposalPermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err)) from err
    except ProposalExpiredError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except ProposalHashMismatchError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except ProposalStateConflictError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@app.get("/api/v1/actions/proposals/{proposal_id}/execution", response_model=ActionExecutionOut)
def get_proposal_execution(
    proposal_id: uuid.UUID,
    db: DbSession,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> ActionExecutionOut:
    """Retrieve execution record for an approved/executed proposal."""
    service = ProposalService(db, context)
    try:
        execution = service.get_execution(proposal_id)
        return ActionExecutionOut.model_validate(execution)
    except ProposalNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
