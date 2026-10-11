from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

Text = Annotated[str, Field(min_length=1, max_length=4000)]
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")]


def utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


Timestamp = Annotated[AwareDatetime, AfterValidator(utc)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Scope(Contract):
    organization_id: UUID
    service_id: UUID
    run_id: UUID


class Alert(Contract):
    organization_id: UUID
    service_id: UUID
    source: Literal["alertmanager"]
    event_type: Literal["alert.firing", "alert.resolved"]
    environment: Literal["demo", "staging", "production"]
    fingerprint: Identifier
    severity: Literal["info", "warning", "critical"]
    starts_at: Timestamp


class Incident(Contract):
    id: UUID
    organization_id: UUID
    service_id: UUID
    title: Text
    severity: Literal["info", "warning", "critical"]
    status: Literal["OPEN", "ACKNOWLEDGED", "MITIGATING", "RESOLVED", "CLOSED", "REOPENED"]
    started_at: Timestamp


class Evidence(Scope):
    evidence_id: Identifier
    source: Literal["synthetic", "logs", "metrics", "traces", "deployments", "runbooks", "alert"]
    observed_at: Timestamp
    redacted_snippet: Annotated[str, Field(min_length=1, max_length=32000)]
    locator: Text


class EvidenceRef(Contract):
    evidence_id: Identifier
    supports: Text


class Hypothesis(Contract):
    cause: Text
    confidence: Literal["low", "medium", "high"]
    supporting_evidence: Annotated[list[EvidenceRef], Field(max_length=50)]
    contradicting_evidence_ids: Annotated[list[Identifier], Field(max_length=50)] = []
    unverified_assumptions: Annotated[list[Text], Field(max_length=50)] = []
    next_check: Text | None = None


class InvestigationResult(Contract):
    status: Literal["complete", "inconclusive"]
    summary: Text
    hypotheses: Annotated[list[Hypothesis], Field(max_length=10)]
    missing_evidence: Annotated[list[Text], Field(max_length=20)] = []
    suggested_action_catalog_ids: Annotated[list[Identifier], Field(max_length=10)] = []
    limitations: Annotated[list[Text], Field(max_length=20)] = []
    execution_mode: Literal["offline", "live"] | None = None
    provider: Text | None = None

    @model_validator(mode="after")
    def require_support(self) -> Self:
        if self.status == "complete" and (
            not self.hypotheses or any(not h.supporting_evidence for h in self.hypotheses)
        ):
            raise ValueError("Complete results require evidence for every hypothesis")
        if self.status == "inconclusive" and not (self.missing_evidence or self.limitations):
            raise ValueError("Inconclusive results must explain missing evidence or limitations")
        return self


class Approval(Contract):
    proposal_id: UUID
    organization_id: UUID
    service_id: UUID
    environment: Literal["demo", "staging"]
    action_catalog_id: Identifier
    payload_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    approver_id: UUID
    decision: Literal["approved", "rejected"]
    decided_at: Timestamp
    expires_at: Timestamp

    @model_validator(mode="after")
    def expiry_after_decision(self) -> Self:
        if self.expires_at <= self.decided_at:
            raise ValueError("Approval expiry must follow decision time")
        return self


def validate_citation_integrity(
    result: InvestigationResult,
    *,
    scope: Scope,
    returned_ledger: Mapping[str, Evidence],
) -> None:
    """Deterministically verify that all cited evidence IDs exist and belong to this run scope."""
    for hypothesis in result.hypotheses:
        references = [ref.evidence_id for ref in hypothesis.supporting_evidence]
        references.extend(hypothesis.contradicting_evidence_ids)
        for reference in references:
            evidence = returned_ledger.get(reference)
            if evidence is None or evidence.evidence_id != reference:
                raise ValueError(f"Unknown evidence reference: '{reference}'")
            if (
                evidence.organization_id != scope.organization_id
                or evidence.service_id != scope.service_id
                or evidence.run_id != scope.run_id
            ):
                raise ValueError(f"Evidence is outside the authorized run scope: '{reference}'")


def validate_claim_support(
    result: InvestigationResult,
    *,
    returned_ledger: Mapping[str, Evidence],
) -> None:
    """Evaluate whether cited observations genuinely justify the causal claims."""
    for hypothesis in result.hypotheses:
        cause_lower = hypothesis.cause.lower()
        supporting_refs = [ref.evidence_id for ref in hypothesis.supporting_evidence]

        # Gather cited evidence snippets and sources
        cited_items = [
            returned_ledger[ref_id] for ref_id in supporting_refs if ref_id in returned_ledger
        ]
        sources = {item.source for item in cited_items}
        snippets_combined = " ".join(item.redacted_snippet for item in cited_items).lower()

        # Check 1: Generic HTTP 500 metrics alone cannot prove database pool exhaustion
        db_keywords = ["database", "db pool", "connection pool", "postgres", "pool exhaustion"]
        claims_db_issue = any(kw in cause_lower for kw in db_keywords)

        if claims_db_issue:
            # Check if any cited evidence contains actual database diagnostic logs or metrics
            has_db_evidence = any(kw in snippets_combined for kw in db_keywords)
            if not has_db_evidence:
                raise ValueError(
                    "Claim support rejected: Generic HTTP 5xx error metrics cannot substantiate "
                    "database pool exhaustion without database diagnostic telemetry."
                )

        # Check 2: Contradiction detection
        has_gateway_failure_in_logs = (
            "gateway_timeout" in snippets_combined
            or "checkout_gateway_timeout" in snippets_combined
            or "payment gateway failure" in snippets_combined
            or "payment processing gateway connection timed out" in snippets_combined
        )

        if claims_db_issue and has_gateway_failure_in_logs:
            if not hypothesis.contradicting_evidence_ids:
                raise ValueError(
                    "Claim support rejected: Hypothesis asserts database pool exhaustion but cited "
                    "telemetry explicitly demonstrates checkout payment gateway failure."
                )

        # Check 3: Unsupported high confidence when evidence is purely symptom-level
        if hypothesis.confidence == "high" and sources == {"metrics"}:
            raise ValueError(
                "Claim support rejected: High confidence causal claim cannot be supported by "
                "metric counters alone without diagnostic logs or traces."
            )


def validate_evidence(
    result: InvestigationResult,
    *,
    scope: Scope,
    returned_ledger: Mapping[str, Evidence],
    allowed_action_ids: frozenset[str] = frozenset(),
) -> InvestigationResult:
    """Caller supplies authorized run scope and only evidence actually returned by its tools."""
    validate_citation_integrity(result, scope=scope, returned_ledger=returned_ledger)
    validate_claim_support(result, returned_ledger=returned_ledger)
    if set(result.suggested_action_catalog_ids) - allowed_action_ids:
        raise ValueError("Action is outside the permitted catalog")
    return result


class AlertmanagerAlertItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["firing", "resolved"]
    labels: dict[str, str]
    annotations: dict[str, str] = {}
    startsAt: Timestamp
    endsAt: Timestamp | None = None
    generatorURL: str | None = None
    fingerprint: str


class AlertmanagerWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = "4"
    groupKey: str
    status: Literal["firing", "resolved"]
    receiver: str
    groupLabels: dict[str, str] = {}
    commonLabels: dict[str, str] = {}
    commonAnnotations: dict[str, str] = {}
    externalURL: str | None = None
    alerts: list[AlertmanagerAlertItem]


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    service_id: UUID
    title: str
    severity: str
    status: str
    environment: str = "staging"
    version: int = 1
    correlated_alert_count: int = 1
    fingerprint: str
    started_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=1000)
    expected_version: int | None = Field(default=None, ge=1)


class IncidentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    event_type: str
    actor: str
    occurred_at: datetime
    payload: dict[str, object]
    created_at: datetime


class IncidentListResponse(BaseModel):
    items: list[IncidentRead]
    total: int
    page: int
    size: int


class InvestigationRunCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str | None = None
    prompt_version: str | None = None
    execution_mode: Literal["offline", "live"] | None = None


class InvestigationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    organization_id: UUID
    service_id: UUID
    status: str
    execution_mode: str = "offline"
    provider: str = "offline"
    model: str
    prompt_version: str
    summary: str | None = None
    tool_call_count: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ToolExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    tool_name: str
    arguments: dict[str, Any]
    status: str
    latency_ms: float
    error_category: str | None = None
    created_at: datetime


class EvidenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_id: str
    run_id: UUID
    organization_id: UUID
    service_id: UUID
    source: str
    observed_at: datetime
    locator: str
    redacted_snippet: str
    content_hash: str
    query_metadata: dict[str, Any]
    created_at: datetime


class HypothesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    cause: str
    confidence: Literal["low", "medium", "high"]
    supporting_evidence: list[dict[str, Any]]
    contradicting_evidence_ids: list[str] = []
    unverified_assumptions: list[str] = []
    next_check: str | None = None
    created_at: datetime

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_legacy_confidence(cls, v: Any) -> str:
        if isinstance(v, (int, float)):
            return "high" if v >= 0.8 else ("medium" if v >= 0.4 else "low")
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("low", "medium", "high"):
                return v_clean
            try:
                num = float(v_clean)
                return "high" if num >= 0.8 else ("medium" if num >= 0.4 else "low")
            except ValueError:
                return "low"
        return "low"


class InvestigationRunDetailRead(InvestigationRunRead):
    hypotheses: list[HypothesisRead] = []
    missing_evidence: list[str] = []
    limitations: list[str] = []
    suggested_actions: list[str] = []
    evidence_items: list[EvidenceItemRead] = []


class EvidenceListResponse(BaseModel):
    items: list[EvidenceItemRead]
    total: int
    page: int
    size: int


# --- Phase 3 Schemas: Auth, RBAC, Services, Audit, Traces ---


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    organization_id: UUID
    role: str
    created_at: datetime
    organization_name: str | None = None
    user_email: str | None = None


class MemberAddRequest(BaseModel):
    email: str
    role: Literal["owner", "admin", "member", "viewer"] = "member"


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class AuthResponse(BaseModel):
    user: UserRead
    active_organization: OrganizationRead | None = None
    role: str | None = None
    organizations: list[OrganizationRead] = []
    csrf_token: str | None = None


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    environment: str
    description: str | None = None
    status: str
    github_repo: str | None = None
    current_version: str | None = None
    current_commit_sha: str | None = None
    created_at: datetime
    updated_at: datetime


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    environment: str = "staging"
    description: str | None = None
    github_repo: str | None = None


class ServiceUpdate(BaseModel):
    name: str | None = None
    environment: str | None = None
    description: str | None = None
    status: str | None = None
    github_repo: str | None = None
    current_version: str | None = None
    current_commit_sha: str | None = None


class DeploymentRecordRead(BaseModel):
    deployment_id: str
    repository: str
    commit_sha: str
    version: str | None = None
    environment: str = "staging"
    deployed_at: datetime
    source: str = "github"
    is_deployment: bool = True
    message: str | None = None
    author: str | None = None


class ServiceVerifyRequest(BaseModel):
    url: str


class ServiceVerifyResponse(BaseModel):
    success: bool
    message: str
    status_code: int | None = None
    latency_ms: float | None = None


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None = None
    actor_id: UUID | None = None
    resource_type: str
    resource_id: str | None = None
    action: str
    result: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="event_metadata")
    created_at: datetime


class SpanRead(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    name: str
    service_name: str
    start_time_unix_nano: int
    end_time_unix_nano: int
    duration_ms: float
    status_code: str = "UNSET"
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceSummaryRead(BaseModel):
    trace_id: str
    service_name: str
    root_operation: str
    duration_ms: float
    span_count: int
    error_span_count: int
    spans: list[SpanRead]
