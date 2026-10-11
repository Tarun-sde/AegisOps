"""Phase 3 authentication, RBAC memberships, user sessions, audit events, and service metadata.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11
"""

import hashlib
import secrets
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("salt", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. Memberships table
    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])

    # 3. User sessions table
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_token_hash", sa.String(64), nullable=False),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_user_sessions_session_token_hash", "user_sessions", ["session_token_hash"], unique=True
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    # 4. Audit events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])

    # 5. Service metadata additions
    op.add_column(
        "services",
        sa.Column("environment", sa.String(32), nullable=False, server_default="staging"),
    )
    op.add_column("services", sa.Column("description", sa.String(255), nullable=True))
    op.add_column(
        "services",
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    )
    op.add_column(
        "services",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # 6. Safe backfill for demo organization
    bind = op.get_bind()
    demo_org = bind.execute(
        sa.text("SELECT id FROM organizations WHERE name = 'AegisOps Demo' LIMIT 1")
    ).fetchone()
    if demo_org:
        demo_org_id = demo_org[0]
        # Check if default demo user exists
        demo_user = bind.execute(
            sa.text("SELECT id FROM users WHERE email = 'demo@aegisops.local' LIMIT 1")
        ).fetchone()
        if not demo_user:
            demo_user_id = uuid.uuid4()
            salt = secrets.token_hex(16)
            hashed_pwd = hashlib.scrypt(
                b"demo-password-123", salt=salt.encode(), n=16384, r=8, p=1
            ).hex()
            insert_user_sql = (
                "INSERT INTO users (id, email, hashed_password, salt, name, is_active, "
                "created_at, updated_at) "
                "VALUES (:id, 'demo@aegisops.local', :hashed_password, :salt, 'Demo Admin', "
                "true, NOW(), NOW())"
            )
            bind.execute(
                sa.text(insert_user_sql),
                {"id": demo_user_id, "hashed_password": hashed_pwd, "salt": salt},
            )
            bind.execute(
                sa.text(
                    "INSERT INTO memberships (id, user_id, organization_id, role, created_at) "
                    "VALUES (:id, :user_id, :organization_id, 'owner', NOW())"
                ),
                {"id": uuid.uuid4(), "user_id": demo_user_id, "organization_id": demo_org_id},
            )


def downgrade() -> None:
    op.drop_column("services", "updated_at")
    op.drop_column("services", "status")
    op.drop_column("services", "description")
    op.drop_column("services", "environment")
    op.drop_table("audit_events")
    op.drop_table("user_sessions")
    op.drop_table("memberships")
    op.drop_table("users")
