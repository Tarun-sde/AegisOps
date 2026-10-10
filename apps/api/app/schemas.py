from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Literal, Self
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
    source: Literal["synthetic", "logs", "metrics", "traces", "deployments", "runbooks"]
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
