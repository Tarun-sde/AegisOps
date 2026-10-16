"""Phase 8.5 WP2: Service connection persistence, monitoring configuration, and health observations.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add connection and monitoring configuration fields to services
    with op.batch_alter_table("services") as batch_op:
        batch_op.add_column(sa.Column("healthcheck_url", sa.String(500), nullable=True))
        batch_op.add_column(
            sa.Column("monitoring_status", sa.String(32), nullable=False, server_default="unknown")
        )
        batch_op.add_column(
            sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("last_probe_status_code", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("last_probe_latency_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("last_probe_error", sa.String(500), nullable=True))
        batch_op.add_column(
            sa.Column("is_monitored", sa.Boolean(), nullable=False, server_default="true")
        )
        batch_op.add_column(
            sa.Column(
                "monitoring_interval_seconds", sa.Integer(), nullable=False, server_default="60"
            )
        )
        batch_op.add_column(
            sa.Column("failure_threshold", sa.Integer(), nullable=False, server_default="3")
        )
        batch_op.add_column(
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("consecutive_successes", sa.Integer(), nullable=False, server_default="0")
        )

    # 2. Create service_health_observations table
    op.create_table(
        "service_health_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column(
            "observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_service_health_observations_service_id",
        "service_health_observations",
        ["service_id"],
    )
    op.create_index(
        "ix_service_health_observations_organization_id",
        "service_health_observations",
        ["organization_id"],
    )
    op.create_index(
        "ix_service_health_observations_observed_at",
        "service_health_observations",
        ["observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_service_health_observations_observed_at", table_name="service_health_observations"
    )
    op.drop_index(
        "ix_service_health_observations_organization_id", table_name="service_health_observations"
    )
    op.drop_index(
        "ix_service_health_observations_service_id", table_name="service_health_observations"
    )
    op.drop_table("service_health_observations")

    with op.batch_alter_table("services") as batch_op:
        batch_op.drop_column("consecutive_successes")
        batch_op.drop_column("consecutive_failures")
        batch_op.drop_column("failure_threshold")
        batch_op.drop_column("monitoring_interval_seconds")
        batch_op.drop_column("is_monitored")
        batch_op.drop_column("last_probe_error")
        batch_op.drop_column("last_probe_latency_ms")
        batch_op.drop_column("last_probe_status_code")
        batch_op.drop_column("last_success_at")
        batch_op.drop_column("last_verified_at")
        batch_op.drop_column("monitoring_status")
        batch_op.drop_column("healthcheck_url")
