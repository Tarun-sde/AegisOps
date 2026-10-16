"""Active incident fingerprint uniqueness across all non-terminal states.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-16

PREFLIGHT OPERATIONAL INSTRUCTIONS:
===================================
Before applying this migration to a production database, operators MUST verify that
no duplicate active incidents exist for the same (organization_id, service_id, fingerprint).
If duplicate active fingerprints exist, PostgreSQL index creation will fail with:
    ERROR: could not create unique index "uq_active_incident_fingerprint"
    Key (organization_id, service_id, fingerprint)=(...) is duplicated.

1. READ-ONLY PREFLIGHT DUPLICATE DETECTION QUERY:
   Execute the following read-only SQL query against the target database:

   SELECT
       organization_id,
       service_id,
       fingerprint,
       COUNT(*) AS duplicate_count,
       ARRAY_AGG(id ORDER BY created_at ASC) AS incident_ids
   FROM incidents
   WHERE status IN ('open', 'acknowledged', 'mitigating', 'reopened')
   GROUP BY organization_id, service_id, fingerprint
   HAVING COUNT(*) > 1;

2. SAFE REMEDIATION PROCEDURE (NO AUTOMATIC DELETION):
   - Production incident records must NEVER be deleted or automatically purged.
   - For any returned duplicate tuple, inspect the associated incidents with human responders.
   - Retain the earliest or primary active incident episode in its current active state.
   - Safely reconcile redundant duplicates by transitioning their status to 'resolved' with
     a documented audit event in incident_events (e.g. actor="operator:migration_0011_preflight",
     event_type="resolved", payload={"reason": "reconciled duplicate prior to migration 0011"}).
   - Once all duplicates have been safely reconciled so the detection query returns 0 rows,
     apply `alembic upgrade head`.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop previous index that only covered status = 'open'
    op.drop_index("uq_open_incident_fingerprint", table_name="incidents")

    # Enforce uniqueness across all active/in-progress incident states
    op.create_index(
        "uq_active_incident_fingerprint",
        "incidents",
        ["organization_id", "service_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'acknowledged', 'mitigating', 'reopened')"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_incident_fingerprint", table_name="incidents")
    op.create_index(
        "uq_open_incident_fingerprint",
        "incidents",
        ["organization_id", "service_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
