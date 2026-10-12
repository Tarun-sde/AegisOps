"""Phase 6: Transactional outbox, action proposals, and proposal approvals.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create outbox_events table
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_summary", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_outbox_events_organization_id"), "outbox_events", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_outbox_events_event_type"), "outbox_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_outbox_events_idempotency_key"), "outbox_events", ["idempotency_key"], unique=False
    )
    op.create_index(op.f("ix_outbox_events_status"), "outbox_events", ["status"], unique=False)
    op.create_index(
        op.f("ix_outbox_events_next_attempt_at"), "outbox_events", ["next_attempt_at"], unique=False
    )

    # 2. Create action_proposals table
    op.create_table(
        "action_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="staging"),
        sa.Column("investigation_run_id", sa.Uuid(), nullable=True),
        sa.Column("action_catalog_id", sa.String(length=64), nullable=False),
        sa.Column("immutable_parameters", sa.JSON(), nullable=False),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column("expected_outcome", sa.String(length=2000), nullable=False),
        sa.Column("known_risks", sa.String(length=2000), nullable=False),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PROPOSED"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["investigation_run_id"], ["investigation_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_proposal_org_idempotency"
        ),
    )
    op.create_index(
        op.f("ix_action_proposals_organization_id"),
        "action_proposals",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_action_proposals_service_id"), "action_proposals", ["service_id"], unique=False
    )
    op.create_index(
        op.f("ix_action_proposals_investigation_run_id"),
        "action_proposals",
        ["investigation_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_action_proposals_action_catalog_id"),
        "action_proposals",
        ["action_catalog_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_action_proposals_status"), "action_proposals", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_action_proposals_idempotency_key"),
        "action_proposals",
        ["idempotency_key"],
        unique=False,
    )

    # 3. Create proposal_approvals table
    op.create_table(
        "proposal_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_proposal_approval_proposal_id"),
    )
    op.create_index(
        op.f("ix_proposal_approvals_proposal_id"),
        "proposal_approvals",
        ["proposal_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_proposal_approvals_organization_id"),
        "proposal_approvals",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposal_approvals_approver_id"),
        "proposal_approvals",
        ["approver_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("proposal_approvals")
    op.drop_table("action_proposals")
    op.drop_table("outbox_events")
