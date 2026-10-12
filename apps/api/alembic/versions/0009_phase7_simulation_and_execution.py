"""Phase 7: Incident Simulation Lab and Sandboxed Remediation Execution.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create simulation_runs table
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="staging"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("scenario_version", sa.String(length=32), nullable=False, server_default="1.0.0"),
        sa.Column("seed", sa.String(length=64), nullable=True),
        sa.Column("started_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_cause", sa.String(length=255), nullable=False),
        sa.Column("initial_release", sa.String(length=64), nullable=True),
        sa.Column("affected_release", sa.String(length=64), nullable=True),
        sa.Column("fault_configuration", sa.JSON(), nullable=False),
        sa.Column("related_incident_id", sa.Uuid(), nullable=True),
        sa.Column("cleanup_status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["started_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_simulation_runs_organization_id"),
        "simulation_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_runs_scenario_id"), "simulation_runs", ["scenario_id"], unique=False
    )
    op.create_index(
        op.f("ix_simulation_runs_service_id"), "simulation_runs", ["service_id"], unique=False
    )
    op.create_index(op.f("ix_simulation_runs_status"), "simulation_runs", ["status"], unique=False)
    op.create_index(
        op.f("ix_simulation_runs_expires_at"), "simulation_runs", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_simulation_runs_cleanup_status"),
        "simulation_runs",
        ["cleanup_status"],
        unique=False,
    )

    # 2. Create simulation_events table
    op.create_table(
        "simulation_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_simulation_events_run_id"), "simulation_events", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_simulation_events_organization_id"),
        "simulation_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_events_event_type"), "simulation_events", ["event_type"], unique=False
    )

    # 3. Create action_executions table
    op.create_table(
        "action_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("executor_id", sa.Uuid(), nullable=True),
        sa.Column("action_catalog_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CLAIMED"),
        sa.Column("parameters_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("target_service_id", sa.Uuid(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="staging"),
        sa.Column("pre_execution_state", sa.JSON(), nullable=False),
        sa.Column("post_execution_state", sa.JSON(), nullable=False),
        sa.Column("verification_result", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["executor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_execution_proposal_id"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_execution_org_idempotency"
        ),
    )
    op.create_index(
        op.f("ix_action_executions_proposal_id"), "action_executions", ["proposal_id"], unique=True
    )
    op.create_index(
        op.f("ix_action_executions_organization_id"),
        "action_executions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_action_executions_target_service_id"),
        "action_executions",
        ["target_service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_action_executions_status"), "action_executions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_action_executions_action_catalog_id"),
        "action_executions",
        ["action_catalog_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_action_executions_idempotency_key"),
        "action_executions",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("action_executions")
    op.drop_table("simulation_events")
    op.drop_table("simulation_runs")
