from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

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
    next_check: Text | None = None


class InvestigationResult(Contract):
    status: Literal["complete", "inconclusive"]
    summary: Text
    hypotheses: Annotated[list[Hypothesis], Field(max_length=10)]
    missing_evidence: Annotated[list[Text], Field(max_length=20)] = []
    suggested_action_catalog_ids: Annotated[list[Identifier], Field(max_length=10)] = []
    limitations: Annotated[list[Text], Field(max_length=20)] = []

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


def validate_evidence(
    result: InvestigationResult,
    *,
    scope: Scope,
    returned_ledger: Mapping[str, Evidence],
    allowed_action_ids: frozenset[str] = frozenset(),
) -> InvestigationResult:
    """Caller supplies authorized run scope and only evidence actually returned by its tools."""
    for hypothesis in result.hypotheses:
        references = [ref.evidence_id for ref in hypothesis.supporting_evidence]
        references.extend(hypothesis.contradicting_evidence_ids)
        for reference in references:
            evidence = returned_ledger.get(reference)
            if evidence is None or evidence.evidence_id != reference:
                raise ValueError("Unknown evidence reference")
            if any(getattr(evidence, key) != value for key, value in scope.model_dump().items()):
                raise ValueError("Evidence is outside the authorized run scope")
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
    fingerprint: str
    started_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


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


class InvestigationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    organization_id: UUID
    service_id: UUID
    status: str
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
    confidence: str
    supporting_evidence: list[dict[str, Any]]
    contradicting_evidence_ids: list[str]
    next_check: str | None = None
    created_at: datetime


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
