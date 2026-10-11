"""Scoped Read-Only GitHub Integration Adapter.

Retrieves commit and deployment metadata using least-privilege read access.
Enforces strict server-side credential isolation, bounded pagination,
and graceful failure handling on network timeouts or rate limits.
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HTTP_TIMEOUT = 5.0
MAX_COMMITS = 10
MAX_DEPLOYMENTS = 5


class GitHubIntegrationError(Exception):
    """Base exception for GitHub API errors."""


class GitHubRateLimitError(GitHubIntegrationError):
    """Raised when GitHub API rate limit is exceeded."""


class GitHubAuthError(GitHubIntegrationError):
    """Raised when GitHub token is invalid or lacks repository access."""


class ScopedGitHubClient:
    """Read-only GitHub API client with least-privilege scoping."""

    def __init__(self, token: str | None = None, timeout: float = DEFAULT_HTTP_TIMEOUT) -> None:
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN", "").strip()
        self.timeout = timeout
        self.offline_mode = False

    @property
    def is_offline(self) -> bool:
        return self.offline_mode or os.environ.get("AEGISOPS_GITHUB_OFFLINE", "0") == "1"

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AegisOps-Incident-Intelligence/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, endpoint: str, query_params: dict[str, Any] | None = None) -> Any:
        url = f"https://api.github.com{endpoint}"
        if query_params:
            url += f"?{urllib.parse.urlencode(query_params)}"

        req = urllib.request.Request(url, headers=self._get_headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                if status == 200:
                    return json.loads(body)
                return None
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                # Check for rate limit
                remaining = err.headers.get("x-ratelimit-remaining")
                if remaining == "0":
                    raise GitHubRateLimitError("GitHub API rate limit exceeded") from err
                msg = f"GitHub authentication/permission failure ({err.code})"
                raise GitHubAuthError(msg) from err
            if err.code == 404:
                logger.warning("GitHub repository or resource not found: %s", endpoint)
                return None
            err_msg = f"GitHub API returned HTTP {err.code}: {err.reason}"
            raise GitHubIntegrationError(err_msg) from err
        except urllib.error.URLError as err:
            raise GitHubIntegrationError(f"GitHub network connection failed: {err.reason}") from err
        except TimeoutError as err:
            raise GitHubIntegrationError("GitHub request timed out") from err

    def get_recent_commits(
        self, repo: str, limit: int = 10, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve recent commits for an authorized repository."""
        clean_repo = repo.strip()
        if not clean_repo or "/" not in clean_repo:
            raise ValueError(f"Invalid repository reference '{repo}'. Must be 'owner/repo'.")

        limit = max(1, min(limit, MAX_COMMITS))

        if self.is_offline:
            # Deterministic offline mock for CI/isolated testing
            return [
                {
                    "commit_sha": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4",
                    "message": "fix: update payment gateway timeout configuration",
                    "author": "AegisOps CI",
                    "committed_at": datetime.now(UTC).isoformat(),
                    "html_url": f"https://github.com/{clean_repo}/commit/a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4",
                }
            ]

        params: dict[str, Any] = {"per_page": limit}
        if since:
            params["since"] = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        data = self._request(f"/repos/{clean_repo}/commits", params)
        if not data or not isinstance(data, list):
            return []

        commits = []
        for item in data[:limit]:
            sha = item.get("sha", "")
            commit_info = item.get("commit", {})
            author_info = commit_info.get("author", {})
            msg = commit_info.get("message", "").split("\n")[0]
            committed_at = author_info.get("date", datetime.now(UTC).isoformat())

            commits.append(
                {
                    "commit_sha": sha,
                    "message": msg[:200],  # bound message length
                    "author": author_info.get("name", "Unknown"),
                    "committed_at": committed_at,
                    "html_url": item.get("html_url", ""),
                }
            )
        return commits

    def get_commit_details(self, repo: str, sha: str) -> dict[str, Any] | None:
        """Retrieve commit details for a specific SHA."""
        clean_repo = repo.strip()
        clean_sha = sha.strip()
        if not clean_repo or "/" not in clean_repo or not clean_sha:
            return None

        if self.is_offline:
            return {
                "commit_sha": clean_sha,
                "message": "feat: release version 0.1.1",
                "author": "AegisOps Demo",
                "committed_at": datetime.now(UTC).isoformat(),
                "files_changed": ["src/app.ts", "package.json"],
            }

        data = self._request(f"/repos/{clean_repo}/commits/{clean_sha}")
        if not data:
            return None

        commit_info = data.get("commit", {})
        author_info = commit_info.get("author", {})
        files = [f.get("filename", "") for f in data.get("files", [])[:10]]

        return {
            "commit_sha": clean_sha,
            "message": commit_info.get("message", "").split("\n")[0][:200],
            "author": author_info.get("name", "Unknown"),
            "committed_at": author_info.get("date", datetime.now(UTC).isoformat()),
            "files_changed": files,
        }

    def get_recent_deployments(
        self, repo: str, environment: str = "staging", limit: int = 5
    ) -> list[dict[str, Any]]:
        """Retrieve deployment metadata or fallback to commit history."""
        clean_repo = repo.strip()
        if not clean_repo or "/" not in clean_repo:
            raise ValueError(f"Invalid repository reference '{repo}'. Must be 'owner/repo'.")

        limit = max(1, min(limit, MAX_DEPLOYMENTS))

        if self.is_offline:
            return [
                {
                    "deployment_id": "dep-offline-01",
                    "repository": clean_repo,
                    "commit_sha": "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4",
                    "version": "0.1.0",
                    "environment": environment,
                    "deployed_at": datetime.now(UTC).isoformat(),
                    "source": "github",
                    "is_deployment": True,
                    "message": "production release 0.1.0",
                    "author": "AegisOps Deployer",
                }
            ]

        try:
            deploy_data = self._request(
                f"/repos/{clean_repo}/deployments",
                {"environment": environment, "per_page": limit},
            )
            if deploy_data and isinstance(deploy_data, list) and len(deploy_data) > 0:
                deployments = []
                for d in deploy_data[:limit]:
                    deployments.append(
                        {
                            "deployment_id": str(d.get("id", "")),
                            "repository": clean_repo,
                            "commit_sha": d.get("sha", ""),
                            "version": d.get("ref", "unknown"),
                            "environment": d.get("environment", environment),
                            "deployed_at": d.get("created_at", datetime.now(UTC).isoformat()),
                            "source": "github",
                            "is_deployment": True,
                            "message": d.get("description") or "GitHub deployment",
                            "author": d.get("creator", {}).get("login", "github-actions"),
                        }
                    )
                return deployments
        except GitHubIntegrationError as err:
            logger.warning(
                "Deployment API query failed for %s: %s; falling back to commits",
                clean_repo,
                err,
            )

        # Fallback: return recent commits explicitly labeled as commit history only
        commits = self.get_recent_commits(clean_repo, limit=limit)
        return [
            {
                "deployment_id": f"commit-{c['commit_sha'][:8]}",
                "repository": clean_repo,
                "commit_sha": c["commit_sha"],
                "version": None,
                "environment": environment,
                "deployed_at": c["committed_at"],
                "source": "github",
                "is_deployment": False,  # Commit history only!
                "message": c["message"],
                "author": c["author"],
            }
            for c in commits
        ]
