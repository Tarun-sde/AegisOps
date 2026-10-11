"""Qualitative confidence, unverified assumptions, and execution mode metadata.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add execution_mode and provider to investigation_runs
    op.add_column(
        "investigation_runs",
        sa.Column("execution_mode", sa.String(32), nullable=False, server_default="offline"),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("provider", sa.String(64), nullable=False, server_default="offline"),
    )

    # 2. Add unverified_assumptions to hypotheses
    op.add_column(
        "hypotheses",
        sa.Column(
            "unverified_assumptions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("hypotheses", "unverified_assumptions")
    op.drop_column("investigation_runs", "provider")
    op.drop_column("investigation_runs", "execution_mode")
