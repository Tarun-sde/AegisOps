import os
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from apps.api.app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AEGISOPS_INTEGRATION") != "1", reason="Use isolated Compose verify service"
    ),
]


def test_migration_round_trip_and_database_constraints():
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "aegisops_phase0_verify",
        ), "Migration round-trip requires the dedicated verification database"
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        org_id = uuid4()
        service_id = uuid4()
        with connection.transaction(force_rollback=True):
            connection.execute(
                "INSERT INTO organizations (id,name) VALUES (%s,%s)", (org_id, "Synthetic test")
            )
            connection.execute(
                "INSERT INTO services (id,organization_id,name) VALUES (%s,%s,%s)",
                (service_id, org_id, "shop-api"),
            )
            assert connection.execute(
                "SELECT organization_id FROM services WHERE id=%s", (service_id,)
            ).fetchone() == (org_id,)
            with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO services (id,organization_id,name) VALUES (%s,%s,%s)",
                    (uuid4(), uuid4(), "alien"),
                )
            with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO services (id,organization_id,name) VALUES (%s,%s,%s)",
                    (uuid4(), org_id, "shop-api"),
                )
        assert (
            connection.execute("SELECT id FROM organizations WHERE id=%s", (org_id,)).fetchone()
            is None
        )
        assert connection.execute(
            "SELECT default_version FROM pg_available_extensions WHERE name='vector'"
        ).fetchone() == ("0.8.7",)
    # This command is for a dedicated disposable verification project, never an operator database.
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_real_dependency_readiness():
    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 200, response.text
        assert response.json()["checks"] == {"postgres": "ok", "redis": "ok"}
