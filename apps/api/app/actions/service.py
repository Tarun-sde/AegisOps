"""Remediation proposal lifecycle, validation, and human-approval service."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from apps.api.app.actions.catalog import (
    ACTION_CATALOG,
    compute_parameters_hash,
    get_catalog_item,
    validate_proposal_parameters,
)
from apps.api.app.actions.executor import RemediationExecutor
from apps.api.app.auth import TenantContext, log_audit_event
from apps.api.app.models import (
    ActionExecution,
    ActionProposal,
    InvestigationRun,
    ProposalApproval,
    Service,
)
from apps.api.app.outbox.service import create_outbox_event
from apps.api.app.schemas import (
    ActionProposalCreate,
    ProposalApprovalCreate,
    ProposalRejectCreate,
)

logger = logging.getLogger(__name__)


class ProposalError(Exception):
    """Base exception for proposal operations."""


class ProposalNotFoundError(ProposalError):
    pass


class ProposalExpiredError(ProposalError):
    pass


class ProposalStateConflictError(ProposalError):
    pass


class ProposalHashMismatchError(ProposalError):
    pass


class ProposalPermissionDeniedError(ProposalError):
    pass


class ProposalService:
    def __init__(self, db: Session, context: TenantContext) -> None:
        self.db = db
        self.context = context

    def _check_lazy_expiry(self, proposal: ActionProposal) -> bool:
        """Lazily transitions proposal status to EXPIRED if past expires_at."""
        now = datetime.now(UTC)
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if proposal.status == "PROPOSED" and expires_at <= now:
            proposal.status = "EXPIRED"
            return True
        return False

    def create_proposal(
        self,
        data: ActionProposalCreate,
        ip_address: str | None = None,
    ) -> ActionProposal:
        """Create an immutable, policy-validated proposal with an atomic outbox event."""
        # 1. Tenant Service Scoping
        service = self.db.scalar(
            select(Service).where(
                Service.id == data.service_id,
                Service.organization_id == self.context.organization.id,
            )
        )
        if not service:
            raise ProposalNotFoundError(
                f"Service {data.service_id} not found in active organization"
            )

        # 2. Action Catalog and Parameter Validation
        catalog_item = get_catalog_item(data.action_catalog_id)
        if not catalog_item:
            raise ValueError(
                f"Action catalog ID '{data.action_catalog_id}' is not permitted. "
                f"Allowed IDs: {sorted(ACTION_CATALOG.keys())}"
            )

        if data.environment not in catalog_item.applicable_environments:
            raise ValueError(
                f"Environment '{data.environment}' is not allowed for '{data.action_catalog_id}'. "
                f"Allowed: {catalog_item.applicable_environments}"
            )

        canonical_params, param_hash = validate_proposal_parameters(
            data.action_catalog_id, data.immutable_parameters
        )

        # 3. Investigation Run Scoping (if provided)
        if data.investigation_run_id:
            run = self.db.scalar(
                select(InvestigationRun).where(
                    InvestigationRun.id == data.investigation_run_id,
                    InvestigationRun.organization_id == self.context.organization.id,
                )
            )
            if not run:
                raise ProposalNotFoundError(
                    f"Run {data.investigation_run_id} not found in active organization"
                )

        # 4. Idempotency Check
        idempotency_key = (
            data.idempotency_key
            or f"proposal:{self.context.organization.id}:{data.action_catalog_id}:{param_hash[:16]}"
        )
        existing = self.db.scalar(
            select(ActionProposal).where(
                ActionProposal.organization_id == self.context.organization.id,
                ActionProposal.idempotency_key == idempotency_key,
            )
        )
        if existing:
            self._check_lazy_expiry(existing)
            self.db.commit()
            return existing

        # 5. Persistence within atomic transaction
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=data.expires_in_seconds)

        proposal = ActionProposal(
            organization_id=self.context.organization.id,
            service_id=service.id,
            environment=data.environment,
            investigation_run_id=data.investigation_run_id,
            action_catalog_id=data.action_catalog_id,
            immutable_parameters=canonical_params,
            parameters_hash=param_hash,
            reason=data.reason,
            expected_outcome=data.expected_outcome,
            known_risks=data.known_risks,
            supporting_evidence_ids=data.supporting_evidence_ids,
            status="PROPOSED",
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        self.db.add(proposal)
        self.db.flush()

        # 6. Atomic Outbox Event publication (DEC-300, DEC-313)
        create_outbox_event(
            self.db,
            organization_id=self.context.organization.id,
            aggregate_type="action_proposal",
            aggregate_id=str(proposal.id),
            event_type="proposal.created",
            payload={
                "proposal_id": str(proposal.id),
                "service_id": str(proposal.service_id),
                "service_name": service.name,
                "environment": proposal.environment,
                "action_catalog_id": proposal.action_catalog_id,
                "parameters_hash": proposal.parameters_hash,
                "risk_classification": catalog_item.risk_classification,
                "expires_at": proposal.expires_at.isoformat(),
                "reason": proposal.reason,
            },
            idempotency_key=f"outbox:proposal_created:{proposal.id}",
        )

        log_audit_event(
            self.db,
            organization_id=self.context.organization.id,
            actor_id=self.context.user.id,
            resource_type="action_proposal",
            resource_id=str(proposal.id),
            action="proposal_created",
            result="success",
            metadata={
                "action_catalog_id": proposal.action_catalog_id,
                "parameters_hash": proposal.parameters_hash,
            },
            ip_address=ip_address,
        )

        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def list_proposals(
        self,
        service_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActionProposal], int]:
        """List proposals for the active organization with lazy expiry updates."""
        query = (
            select(ActionProposal)
            .options(selectinload(ActionProposal.approval))
            .where(ActionProposal.organization_id == self.context.organization.id)
        )
        if service_id:
            query = query.where(ActionProposal.service_id == service_id)
        if status:
            query = query.where(ActionProposal.status == status)

        query = query.order_by(desc(ActionProposal.created_at))
        proposals = self.db.scalars(query.offset(offset).limit(limit)).all()

        # Apply lazy expiry
        modified = False
        for p in proposals:
            if self._check_lazy_expiry(p):
                modified = True
        if modified:
            self.db.commit()

        total = len(proposals)  # simplified count for bounded queries
        return list(proposals), total

    def get_proposal(self, proposal_id: uuid.UUID) -> ActionProposal:
        """Retrieve proposal with organization boundary validation and lazy expiry."""
        proposal = self.db.scalar(
            select(ActionProposal)
            .options(selectinload(ActionProposal.approval))
            .where(
                ActionProposal.id == proposal_id,
                ActionProposal.organization_id == self.context.organization.id,
            )
        )
        if not proposal:
            raise ProposalNotFoundError(f"Proposal {proposal_id} not found in active organization")

        if self._check_lazy_expiry(proposal):
            self.db.commit()

        return proposal

    def approve_proposal(
        self,
        proposal_id: uuid.UUID,
        approval_data: ProposalApprovalCreate,
        ip_address: str | None = None,
    ) -> ActionProposal:
        """Approve proposal with RBAC verification, hash checking, and concurrency control.

        Zero execution occurs here (DEC-310, DEC-312).
        """
        # 1. RBAC Check: admin or owner required
        if not self.context.can("admin"):
            raise ProposalPermissionDeniedError(
                f"Role '{self.context.role}' cannot approve proposals (requires admin or owner)."
            )

        # 2. Concurrency-safe query
        query = (
            select(ActionProposal)
            .options(selectinload(ActionProposal.approval))
            .where(
                ActionProposal.id == proposal_id,
                ActionProposal.organization_id == self.context.organization.id,
            )
        )
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update()

        proposal = self.db.scalar(query)
        if not proposal:
            raise ProposalNotFoundError(f"Proposal {proposal_id} not found in active organization")

        # 3. Expiry check
        if self._check_lazy_expiry(proposal):
            self.db.commit()
            raise ProposalExpiredError(f"Proposal {proposal_id} has expired.")

        # 4. State Machine check: must be PROPOSED
        if proposal.status != "PROPOSED":
            raise ProposalStateConflictError(
                f"Proposal is in state '{proposal.status}' (requires PROPOSED)."
            )

        # 5. Exact Hash Match check (DEC-309)
        if approval_data.expected_parameters_hash != proposal.parameters_hash:
            raise ProposalHashMismatchError(
                f"Expected hash '{approval_data.expected_parameters_hash}' does not match "
                f"proposal's canonical hash '{proposal.parameters_hash}'."
            )

        # 6. Apply transition: PROPOSED -> APPROVED
        proposal.status = "APPROVED"
        approval_record = ProposalApproval(
            proposal_id=proposal.id,
            organization_id=self.context.organization.id,
            approver_id=self.context.user.id,
            decision="APPROVED",
            parameters_hash=proposal.parameters_hash,
            comment=approval_data.comment,
        )
        self.db.add(approval_record)

        # 7. Atomic Outbox Event publication (DEC-300)
        create_outbox_event(
            self.db,
            organization_id=self.context.organization.id,
            aggregate_type="action_proposal",
            aggregate_id=str(proposal.id),
            event_type="proposal.approved",
            payload={
                "proposal_id": str(proposal.id),
                "service_id": str(proposal.service_id),
                "environment": proposal.environment,
                "action_catalog_id": proposal.action_catalog_id,
                "parameters_hash": proposal.parameters_hash,
                "approver_id": str(self.context.user.id),
                "comment": approval_data.comment,
            },
            idempotency_key=f"outbox:proposal_approved:{proposal.id}",
        )

        log_audit_event(
            self.db,
            organization_id=self.context.organization.id,
            actor_id=self.context.user.id,
            resource_type="action_proposal",
            resource_id=str(proposal.id),
            action="proposal_approved",
            result="success",
            metadata={
                "parameters_hash": proposal.parameters_hash,
                "comment": approval_data.comment,
            },
            ip_address=ip_address,
        )

        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def reject_proposal(
        self,
        proposal_id: uuid.UUID,
        reject_data: ProposalRejectCreate,
        ip_address: str | None = None,
    ) -> ActionProposal:
        """Reject proposal with RBAC verification and audit logging."""
        if not self.context.can("admin"):
            raise ProposalPermissionDeniedError(
                f"Role '{self.context.role}' cannot reject proposals (requires admin or owner)."
            )

        query = (
            select(ActionProposal)
            .options(selectinload(ActionProposal.approval))
            .where(
                ActionProposal.id == proposal_id,
                ActionProposal.organization_id == self.context.organization.id,
            )
        )
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update()

        proposal = self.db.scalar(query)
        if not proposal:
            raise ProposalNotFoundError(f"Proposal {proposal_id} not found in active organization")

        self._check_lazy_expiry(proposal)
        if proposal.status != "PROPOSED":
            raise ProposalStateConflictError(
                f"Proposal is in state '{proposal.status}' (requires PROPOSED)."
            )

        proposal.status = "REJECTED"
        approval_record = ProposalApproval(
            proposal_id=proposal.id,
            organization_id=self.context.organization.id,
            approver_id=self.context.user.id,
            decision="REJECTED",
            parameters_hash=proposal.parameters_hash,
            comment=reject_data.comment,
        )
        self.db.add(approval_record)

        create_outbox_event(
            self.db,
            organization_id=self.context.organization.id,
            aggregate_type="action_proposal",
            aggregate_id=str(proposal.id),
            event_type="proposal.rejected",
            payload={
                "proposal_id": str(proposal.id),
                "service_id": str(proposal.service_id),
                "environment": proposal.environment,
                "action_catalog_id": proposal.action_catalog_id,
                "parameters_hash": proposal.parameters_hash,
                "approver_id": str(self.context.user.id),
                "comment": reject_data.comment,
            },
            idempotency_key=f"outbox:proposal_rejected:{proposal.id}",
        )

        log_audit_event(
            self.db,
            organization_id=self.context.organization.id,
            actor_id=self.context.user.id,
            resource_type="action_proposal",
            resource_id=str(proposal.id),
            action="proposal_rejected",
            result="success",
            metadata={"comment": reject_data.comment},
            ip_address=ip_address,
        )

        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def execute_proposal(
        self,
        proposal_id: uuid.UUID,
        idempotency_key: str | None = None,
        ip_address: str | None = None,
    ) -> ActionExecution:
        """Atomically claim and execute an approved remediation action (DEC-320, DEC-321)."""
        # 1. RBAC check: role >= admin required (DEC-328, DEC-329)
        if not self.context.can("admin"):
            raise ProposalPermissionDeniedError(
                f"Role '{self.context.role}' cannot execute remediation actions "
                "(requires admin or owner)."
            )

        # 2. Concurrency-safe proposal retrieval with row-level locking
        query = (
            select(ActionProposal)
            .options(selectinload(ActionProposal.approval), selectinload(ActionProposal.service))
            .where(
                ActionProposal.id == proposal_id,
                ActionProposal.organization_id == self.context.organization.id,
            )
        )
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update()

        proposal = self.db.scalar(query)
        if not proposal:
            raise ProposalNotFoundError(f"Proposal {proposal_id} not found in active organization")

        # 3. Lazy expiry check (DEC-311)
        if self._check_lazy_expiry(proposal):
            self.db.commit()
            raise ProposalExpiredError(f"Proposal {proposal_id} has expired.")

        # 4. State validation: Must be APPROVED
        if proposal.status != "APPROVED":
            # Idempotency check: if already EXECUTING or SUCCEEDED, return existing execution
            if proposal.status in ("EXECUTING", "SUCCEEDED", "FAILED"):
                existing = self.db.scalar(
                    select(ActionExecution).where(ActionExecution.proposal_id == proposal.id)
                )
                if existing:
                    return existing
            raise ProposalStateConflictError(
                f"Proposal is in state '{proposal.status}' (requires APPROVED to execute)."
            )

        # 5. Environment check: Staging or development only (Rule 1, DEC-322)
        if proposal.environment == "production":
            raise ValueError(
                "Remediation execution against production targets is strictly forbidden."
            )
        if proposal.environment not in ("staging", "development"):
            raise ValueError(
                f"Environment '{proposal.environment}' is not permitted for remediation execution."
            )

        # 6. Payload integrity & cryptographic hash verification (DEC-321)
        recomputed_hash = compute_parameters_hash(proposal.immutable_parameters)
        if recomputed_hash != proposal.parameters_hash:
            raise ProposalHashMismatchError(
                "Parameters hash tampering detected! Execution aborted."
            )
        if not proposal.approval or proposal.approval.parameters_hash != proposal.parameters_hash:
            raise ProposalHashMismatchError("Approval parameters hash mismatch! Execution aborted.")

        # 7. Idempotency key & unique execution check (DEC-320, DEC-326)
        effective_idempotency_key = idempotency_key or f"exec:{proposal.id}"
        existing_exec = self.db.scalar(
            select(ActionExecution).where(ActionExecution.proposal_id == proposal.id)
        )
        if existing_exec:
            return existing_exec

        # 8. Two-phase claiming: atomically transition proposal to EXECUTING
        # and insert ActionExecution
        proposal.status = "EXECUTING"
        execution = ActionExecution(
            proposal_id=proposal.id,
            organization_id=self.context.organization.id,
            executor_id=self.context.user.id,
            action_catalog_id=proposal.action_catalog_id,
            status="CLAIMED",
            parameters_hash=proposal.parameters_hash,
            idempotency_key=effective_idempotency_key,
            target_service_id=proposal.service_id,
            environment=proposal.environment,
            pre_execution_state={
                "proposal_id": str(proposal.id),
                "service_id": str(proposal.service_id),
                "action_catalog_id": proposal.action_catalog_id,
                "parameters": proposal.immutable_parameters,
            },
        )
        self.db.add(execution)
        # Commit claim phase to release DB row lock before network execution
        self.db.commit()
        self.db.refresh(execution)

        # 9. Dispatch to sandboxed executor
        executor = RemediationExecutor()
        try:
            post_state, verification = executor.execute(proposal, proposal.service)
            execution.status = "SUCCEEDED"
            execution.post_execution_state = post_state
            execution.verification_result = verification
            execution.finished_at = datetime.now(UTC)
            proposal.status = "SUCCEEDED"

            create_outbox_event(
                self.db,
                organization_id=self.context.organization.id,
                aggregate_type="action_execution",
                aggregate_id=str(execution.id),
                event_type="action.execution_succeeded",
                payload={
                    "execution_id": str(execution.id),
                    "proposal_id": str(proposal.id),
                    "service_id": str(proposal.service_id),
                    "action_catalog_id": proposal.action_catalog_id,
                    "status": "SUCCEEDED",
                    "verification": verification,
                },
                idempotency_key=f"outbox:execution_succeeded:{execution.id}",
            )

            log_audit_event(
                self.db,
                organization_id=self.context.organization.id,
                actor_id=self.context.user.id,
                resource_type="action_execution",
                resource_id=str(execution.id),
                action="action_execution_succeeded",
                result="success",
                metadata={"proposal_id": str(proposal.id)},
                ip_address=ip_address,
            )
        except Exception as err:
            logger.exception(f"Execution dispatch failed for proposal {proposal.id}: {err}")
            execution.status = "FAILED"
            execution.error_message = str(err)
            execution.finished_at = datetime.now(UTC)
            proposal.status = "FAILED"

            create_outbox_event(
                self.db,
                organization_id=self.context.organization.id,
                aggregate_type="action_execution",
                aggregate_id=str(execution.id),
                event_type="action.execution_failed",
                payload={
                    "execution_id": str(execution.id),
                    "proposal_id": str(proposal.id),
                    "service_id": str(proposal.service_id),
                    "action_catalog_id": proposal.action_catalog_id,
                    "status": "FAILED",
                    "error": str(err),
                },
                idempotency_key=f"outbox:execution_failed:{execution.id}",
            )

            log_audit_event(
                self.db,
                organization_id=self.context.organization.id,
                actor_id=self.context.user.id,
                resource_type="action_execution",
                resource_id=str(execution.id),
                action="action_execution_failed",
                result="failure",
                metadata={"error": str(err)},
                ip_address=ip_address,
            )

        self.db.commit()
        self.db.refresh(execution)
        return execution

    def get_execution(self, proposal_id: uuid.UUID) -> ActionExecution:
        """Retrieve execution record for an approved/executed proposal."""
        execution = self.db.scalar(
            select(ActionExecution).where(
                ActionExecution.proposal_id == proposal_id,
                ActionExecution.organization_id == self.context.organization.id,
            )
        )
        if not execution:
            raise ProposalNotFoundError(
                f"Execution for proposal {proposal_id} not found in active organization"
            )
        return execution
