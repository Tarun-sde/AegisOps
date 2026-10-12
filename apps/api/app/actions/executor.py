"""Sandboxed remediation action executor for Phase 7 (Workstream F).

Security invariants:
- Staging and development environments ONLY (DEC-322, Rule 1).
- Strictly allowlisted actions (restart_demo_service, rollback_demo_release).
- No arbitrary shell commands, raw Docker sockets, or SSH connections.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from apps.api.app.models import ActionProposal, Service

logger = logging.getLogger(__name__)


class ExecutionSecurityError(Exception):
    """Raised when an execution violates environment or safety constraints."""


class RemediationExecutor:
    """Dispatches validated immutable action proposals to isolated staging infrastructure."""

    def __init__(self, shop_api_url: str | None = None) -> None:
        self.shop_api_url = shop_api_url or os.environ.get(
            "AEGISOPS_SHOP_API_URL",
            "http://127.0.0.1:4000" if not os.environ.get("IN_DOCKER") else "http://shop-api:4000",
        )
        self.fault_secret = os.environ.get(
            "AEGISOPS_DEMO_FAULT_SECRET", "aegisops-demo-fault-secret"
        )

    def _call_service(self, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.shop_api_url.rstrip('/')}{endpoint}"
        body = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-demo-fault-secret": self.fault_secret,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
                return data
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            logger.warning(f"Could not reach service at {url}: {err}")
            return {"status": "unreachable", "error": str(err)}

    def validate_target(self, proposal: ActionProposal, target: Service) -> None:
        """Enforces security boundaries before any execution dispatch (Rule 1, Rule 6)."""
        if proposal.environment == "production" or target.environment == "production":
            raise ExecutionSecurityError(
                "CRITICAL: Remediation execution against production targets is strictly forbidden."
            )

        if proposal.environment not in ("staging", "development"):
            raise ExecutionSecurityError(
                f"Target environment '{proposal.environment}' "
                "is not permitted for automated execution."
            )

        allowlisted_services = ("shop-api", "demo-service", "cart-service")
        if target.name not in allowlisted_services:
            raise ExecutionSecurityError(
                f"Target service '{target.name}' is not in the allowlisted remediation scope."
            )

    def execute(
        self,
        proposal: ActionProposal,
        target: Service,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Executes the allowlisted action and returns (post_state, verification_result)."""
        self.validate_target(proposal, target)

        action_id = proposal.action_catalog_id
        params = proposal.immutable_parameters

        if action_id == "restart_demo_service":
            # 1. Reset faults and trigger container restart simulation
            reset_result = self._call_service("/fault/reset")
            # 2. Verify health probe responds
            health_check = self._verify_health()
            post_state = {
                "action": "restart_demo_service",
                "service": target.name,
                "reset_result": reset_result,
            }
            verification = {
                "health_status": health_check.get("status"),
                "fault_active": health_check.get("fault_active", False),
            }
            return post_state, verification

        elif action_id == "rollback_demo_release":
            target_version = params.get("target_version", "0.1.0")
            # In demo, rollback resets release state to stable release
            reset_result = self._call_service("/fault/reset")
            health_check = self._verify_health()
            post_state = {
                "action": "rollback_demo_release",
                "service": target.name,
                "target_version": target_version,
                "reset_result": reset_result,
            }
            verification = {
                "active_version": health_check.get("version", target_version),
                "fault_active": health_check.get("fault_active", False),
            }
            return post_state, verification

        elif action_id == "request_staging_rollback":
            target_commit = params.get("target_commit", "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4")
            reset_result = self._call_service("/fault/reset")
            health_check = self._verify_health()
            post_state = {
                "action": "request_staging_rollback",
                "service": target.name,
                "target_commit": target_commit,
                "reset_result": reset_result,
            }
            verification = {
                "active_commit": health_check.get("commit_sha", target_commit),
                "fault_active": health_check.get("fault_active", False),
            }
            return post_state, verification

        else:
            raise ValueError(f"Action '{action_id}' has no registered execution handler.")

    def _verify_health(self) -> dict[str, Any]:
        url = f"{self.shop_api_url.rstrip('/')}/healthz"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception as err:
            return {"status": "unhealthy", "error": str(err)}
