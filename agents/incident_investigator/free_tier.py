"""Operator-reviewed account evidence; this is not an automatic billing lookup."""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Provider = Literal["gemini", "groq"]


class FreeTierEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Provider
    tier: Literal["free"]
    key_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    account_reference: str = Field(min_length=1, max_length=200)
    source: Literal["google_ai_studio_project_billing", "groq_organization_billing"]
    verified_at: AwareDatetime
    verified_by: Literal["operator"]

    def check(self, provider: Provider, key: str) -> None:
        source = (
            "google_ai_studio_project_billing"
            if provider == "gemini"
            else "groq_organization_billing"
        )
        if (
            self.provider != provider
            or self.source != source
            or self.key_sha256 != hashlib.sha256(key.encode()).hexdigest()
            or not timedelta(0) <= datetime.now(UTC) - self.verified_at <= timedelta(hours=1)
        ):
            raise ValueError("BLOCKED: tier evidence is stale or does not match this key/provider")


def require_free_tier(path: Path | None, provider: Provider, key: str) -> FreeTierEvidence:
    if path is None:
        raise ValueError("BLOCKED: zero-spend ceiling requires reviewed free-tier evidence")
    evidence = FreeTierEvidence.model_validate_json(path.read_text())
    evidence.check(provider, key)
    return evidence
