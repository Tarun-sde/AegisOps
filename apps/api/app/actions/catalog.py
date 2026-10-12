"""Deterministic action catalog definitions and parameter schema validation for Phase 6.

Security invariant:
- All proposal types must be explicitly pre-defined in this catalog.
- Execution is strictly DISABLED in Phase 6. Awaiting Phase 7 security gate.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class RestartDemoServiceParams(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=5, max_length=500)
    grace_period_seconds: int = Field(default=10, ge=0, le=60)


class RollbackDemoReleaseParams(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    target_version: str = Field(..., min_length=2, max_length=50)
    reason: str = Field(..., min_length=5, max_length=500)


class RequestStagingRollbackParams(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    target_commit: str = Field(..., min_length=7, max_length=40)
    reason: str = Field(..., min_length=5, max_length=500)

    def model_post_init(self, __context: Any) -> None:
        if not re.fullmatch(r"^[0-9a-fA-F]{7,40}$", self.target_commit):
            raise ValueError("target_commit must be a 7-40 character hexadecimal Git SHA")


@dataclass(frozen=True)
class ActionCatalogItem:
    action_catalog_id: str
    name: str
    description: str
    applicable_environments: tuple[str, ...]
    risk_classification: str  # LOW | MEDIUM | HIGH
    required_role: str  # admin | owner
    default_expiry_seconds: int
    param_model: type[BaseModel]


ACTION_CATALOG: dict[str, ActionCatalogItem] = {
    "restart_demo_service": ActionCatalogItem(
        action_catalog_id="restart_demo_service",
        name="Restart Demo Service",
        description="Restart staging container for shop-api after pool exhaustion or memory reset",
        applicable_environments=("staging", "development"),
        risk_classification="LOW",
        required_role="admin",
        default_expiry_seconds=1800,
        param_model=RestartDemoServiceParams,
    ),
    "rollback_demo_release": ActionCatalogItem(
        action_catalog_id="rollback_demo_release",
        name="Rollback Demo Release",
        description="Rollback staging release to a previous stable deployment version",
        applicable_environments=("staging", "development"),
        risk_classification="MEDIUM",
        required_role="admin",
        default_expiry_seconds=1800,
        param_model=RollbackDemoReleaseParams,
    ),
    "request_staging_rollback": ActionCatalogItem(
        action_catalog_id="request_staging_rollback",
        name="Request Staging Rollback",
        description="Request staging Git commit rollback and canary configuration reset",
        applicable_environments=("staging", "development"),
        risk_classification="MEDIUM",
        required_role="admin",
        default_expiry_seconds=1800,
        param_model=RequestStagingRollbackParams,
    ),
}


def get_catalog_item(action_catalog_id: str) -> ActionCatalogItem | None:
    return ACTION_CATALOG.get(action_catalog_id)


def compute_parameters_hash(parameters: dict[str, Any]) -> str:
    """Compute canonical SHA-256 hash of parameters for tamper-evident review."""
    canonical_json = json.dumps(
        parameters,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def validate_proposal_parameters(
    action_catalog_id: str,
    parameters: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Validate action parameters against catalog schema and return (canonical_params, hash)."""
    item = get_catalog_item(action_catalog_id)
    if not item:
        raise ValueError(
            f"Action catalog ID '{action_catalog_id}' is not permitted. "
            f"Allowed IDs: {sorted(ACTION_CATALOG.keys())}"
        )

    try:
        validated = item.param_model(**parameters)
        canonical_dict = validated.model_dump(mode="json")
        param_hash = compute_parameters_hash(canonical_dict)
        return canonical_dict, param_hash
    except (ValidationError, ValueError) as err:
        raise ValueError(f"Invalid parameters for action '{action_catalog_id}': {err}") from err


def execute_action(action_catalog_id: str, parameters: dict[str, Any]) -> None:
    """Security barrier: zero remediation execution is permitted in Phase 6."""
    raise NotImplementedError(
        f"Remediation action execution for '{action_catalog_id}' is disabled in Phase 6. "
        "Awaiting Phase 7 security gate."
    )
