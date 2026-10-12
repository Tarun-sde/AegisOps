from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    salt: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list[Membership]] = relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[UserSession]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="memberships")
    organization: Mapped[Organization] = relationship("Organization", back_populates="memberships")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="sessions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(32))  # success | failure | denied
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list[Membership]] = relationship(
        "Membership", back_populates="organization", cascade="all, delete-orphan"
    )
    services: Mapped[list[Service]] = relationship(
        "Service", back_populates="organization", cascade="all, delete-orphan"
    )
    outbox_events: Mapped[list[OutboxEvent]] = relationship(
        "OutboxEvent", back_populates="organization", cascade="all, delete-orphan"
    )
    action_proposals: Mapped[list[ActionProposal]] = relationship(
        "ActionProposal", back_populates="organization", cascade="all, delete-orphan"
    )
    simulation_runs: Mapped[list[SimulationRun]] = relationship(
        "SimulationRun", back_populates="organization", cascade="all, delete-orphan"
    )
    action_executions: Mapped[list[ActionExecution]] = relationship(
        "ActionExecution", back_populates="organization", cascade="all, delete-orphan"
    )


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    environment: Mapped[str] = mapped_column(String(32), default="staging")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship("Organization", back_populates="services")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("services.id"), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64), default="alertmanager")
    status: Mapped[str] = mapped_column(String(32))  # firing | resolved
    severity: Mapped[str] = mapped_column(String(32))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    labels: Mapped[dict[str, Any]] = mapped_column(JSON)
    annotations: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index(
            "uq_open_incident_fingerprint",
            "organization_id",
            "service_id",
            "fingerprint",
            unique=True,
            postgresql_where=text("status in ('open', 'reopened')"),
            sqlite_where=text("status in ('open', 'reopened')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))  # Lifecycle: open -> resolved -> closed
    environment: Mapped[str] = mapped_column(String(32), default="staging")
    version: Mapped[int] = mapped_column(default=1)
    correlated_alert_count: Mapped[int] = mapped_column(default=1)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list[IncidentEvent]] = relationship(
        "IncidentEvent", back_populates="incident", cascade="all, delete-orphan"
    )
    investigations: Mapped[list[InvestigationRun]] = relationship(
        "InvestigationRun", back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(64), default="system")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    incident: Mapped[Incident] = relationship("Incident", back_populates="events")


class InvestigationRun(Base):
    __tablename__ = "investigation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    execution_mode: Mapped[str] = mapped_column(String(32), default="offline")
    provider: Mapped[str] = mapped_column(String(64), default="offline")
    model: Mapped[str] = mapped_column(String(120), default="gemini-3.5-flash")
    prompt_version: Mapped[str] = mapped_column(String(64), default="phase2-v1")
    summary: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    missing_evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    suggested_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    tool_call_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    incident: Mapped[Incident] = relationship("Incident", back_populates="investigations")
    tool_executions: Mapped[list[ToolExecution]] = relationship(
        "ToolExecution", back_populates="run", cascade="all, delete-orphan"
    )
    evidence_items: Mapped[list[EvidenceItem]] = relationship(
        "EvidenceItem", back_populates="run", cascade="all, delete-orphan"
    )
    hypotheses: Mapped[list[HypothesisRecord]] = relationship(
        "HypothesisRecord", back_populates="run", cascade="all, delete-orphan"
    )
    proposals: Mapped[list[ActionProposal]] = relationship(
        "ActionProposal", back_populates="investigation_run"
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32))  # success | error
    latency_ms: Mapped[float] = mapped_column(default=0.0)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[InvestigationRun] = relationship(
        "InvestigationRun", back_populates="tool_executions"
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = (UniqueConstraint("run_id", "evidence_id", name="uq_run_evidence_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[str] = mapped_column(String(128), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), index=True)
    source: Mapped[str] = mapped_column(String(32))  # metrics | logs | alert
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locator: Mapped[str] = mapped_column(String(500))
    redacted_snippet: Mapped[str] = mapped_column(String(32000))
    content_hash: Mapped[str] = mapped_column(String(64))
    query_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[InvestigationRun] = relationship(
        "InvestigationRun", back_populates="evidence_items"
    )


class HypothesisRecord(Base):
    __tablename__ = "hypotheses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="CASCADE"), index=True
    )
    cause: Mapped[str] = mapped_column(String(1000))
    confidence: Mapped[str] = mapped_column(String(32))  # low | medium | high
    supporting_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    contradicting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    unverified_assumptions: Mapped[list[str]] = mapped_column(JSON, default=list)
    next_check: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[InvestigationRun] = relationship("InvestigationRun", back_populates="hypotheses")


# Phase 6: Outbox & Remediation Proposals


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    aggregate_type: Mapped[str] = mapped_column(String(64))  # incident | investigation | proposal
    aggregate_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    # PENDING | PROCESSING | DELIVERED | RETRY_SCHEDULED | DEAD_LETTERED
    attempt_count: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="outbox_events"
    )


class ActionProposal(Base):
    __tablename__ = "action_proposals"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_proposal_org_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    environment: Mapped[str] = mapped_column(String(32), default="staging")
    investigation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_catalog_id: Mapped[str] = mapped_column(String(64), index=True)
    immutable_parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    parameters_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(2000))
    expected_outcome: Mapped[str] = mapped_column(String(2000))
    known_risks: Mapped[str] = mapped_column(String(2000))
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="PROPOSED", index=True)
    # PROPOSED | APPROVED | REJECTED | EXPIRED
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="action_proposals"
    )
    service: Mapped[Service] = relationship("Service")
    investigation_run: Mapped[InvestigationRun | None] = relationship(
        "InvestigationRun", back_populates="proposals"
    )
    approval: Mapped[ProposalApproval | None] = relationship(
        "ProposalApproval", back_populates="proposal", uselist=False, cascade="all, delete-orphan"
    )
    execution: Mapped[ActionExecution | None] = relationship(
        "ActionExecution", back_populates="proposal", uselist=False, cascade="all, delete-orphan"
    )


class ProposalApproval(Base):
    __tablename__ = "proposal_approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="CASCADE"), unique=True, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    approver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    decision: Mapped[str] = mapped_column(String(32))  # APPROVED | REJECTED
    parameters_hash: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proposal: Mapped[ActionProposal] = relationship("ActionProposal", back_populates="approval")
    approver: Mapped[User | None] = relationship("User")
    organization: Mapped[Organization] = relationship("Organization")


# Phase 7: Incident Simulation Lab & Sandboxed Remediation Execution


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    environment: Mapped[str] = mapped_column(String(32), default="staging")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    # ACTIVE | COMPLETED | EXPIRED | FAILED | CANCELLED
    scenario_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_cause: Mapped[str] = mapped_column(String(255))
    initial_release: Mapped[str | None] = mapped_column(String(64), nullable=True)
    affected_release: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fault_configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    related_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cleanup_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    # PENDING | CLEANED | FAILED
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="simulation_runs"
    )
    service: Mapped[Service] = relationship("Service")
    started_by: Mapped[User | None] = relationship("User")
    events: Mapped[list[SimulationEvent]] = relationship(
        "SimulationEvent",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SimulationEvent.created_at",
    )


class SimulationEvent(Base):
    __tablename__ = "simulation_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    # simulation.started | simulation.fault_activated | simulation.reset
    # simulation.expired | service.recovery_observed
    actor: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[SimulationRun] = relationship("SimulationRun", back_populates="events")


class ActionExecution(Base):
    __tablename__ = "action_executions"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_execution_proposal_id"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_execution_org_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_proposals.id", ondelete="CASCADE"), unique=True, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    executor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_catalog_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="CLAIMED", index=True)
    # CLAIMED | EXECUTING | SUCCEEDED | FAILED
    parameters_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True)
    target_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    environment: Mapped[str] = mapped_column(String(32), default="staging")
    pre_execution_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    post_execution_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verification_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="action_executions"
    )
    proposal: Mapped[ActionProposal] = relationship("ActionProposal", back_populates="execution")
    executor: Mapped[User | None] = relationship("User")
    target_service: Mapped[Service] = relationship("Service")
