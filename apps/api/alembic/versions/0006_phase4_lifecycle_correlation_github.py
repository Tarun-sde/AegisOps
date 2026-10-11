"""Phase 4 incident lifecycle, correlation metadata, and service GitHub integration.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add lifecycle, correlation, and environment fields to incidents
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(
            sa.Column("environment", sa.String(32), nullable=False, server_default="staging")
        )
        batch_op.add_column(
            sa.Column("correlated_alert_count", sa.Integer(), nullable=False, server_default="1")
        )

    # 2. Add GitHub repository and current release metadata to services
    with op.batch_alter_table("services") as batch_op:
        batch_op.add_column(sa.Column("github_repo", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("current_version", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("current_commit_sha", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("services") as batch_op:
        batch_op.drop_column("current_commit_sha")
        batch_op.drop_column("current_version")
        batch_op.drop_column("github_repo")

    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_column("correlated_alert_count")
        batch_op.drop_column("environment")
        batch_op.drop_column("version")
