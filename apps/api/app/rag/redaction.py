from __future__ import annotations

import re
from typing import NamedTuple

from agents.incident_investigator.tools.redaction import redact_sensitive_text

# Regex patterns for sensitive operational document redactions
SECRET_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:[A-Z0-9_-]+\s+)*KEY-----[\s\S]*?"
            r"-----END (?:[A-Z0-9_-]+\s+)*KEY-----",
            re.MULTILINE,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        "connection_string",
        re.compile(
            r"(?i)\b(?P<scheme>postgres|postgresql|mysql|mongodb|redis|amqp)://"
            r"(?P<user>[^:\s]+):(?P<pass>[^@\s]+)@(?P<host>[^\s/]+)",
        ),
        r"\g<scheme>://\g<user>:[REDACTED_PASSWORD]@\g<host>",
    ),
    (
        "password_assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|api_key|token|auth_token)\s*[:=]\s*['\"]([^'\"]{4,})['\"]",
        ),
        r"password = '[REDACTED_SECRET]'",
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9_\-\.]{16,}\b"),
        "Bearer [REDACTED_TOKEN]",
    ),
    (
        "google_api_key",
        re.compile(r"\bAIzaSy[a-zA-Z0-9_\-]{33}\b"),
        "[REDACTED_GOOGLE_API_KEY]",
    ),
    (
        "aws_access_key",
        re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        "github_token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
]


class RedactionResult(NamedTuple):
    clean_text: str
    redactions_count: int


def redact_document_text(text: str) -> RedactionResult:
    """Conservatively scan and redact credentials and sensitive tokens from runbook text.

    Applies document-level secret patterns followed by the standard telemetry redaction suite.
    Never stores or logs the detected raw secrets.
    """
    if not text:
        return RedactionResult(clean_text="", redactions_count=0)

    count = 0
    result = text

    for _name, pattern, replacement in SECRET_PATTERNS:
        matches = len(pattern.findall(result))
        if matches > 0:
            count += matches
            result = pattern.sub(replacement, result)

    # Secondary pass through base telemetry redactor for general tokens and auth headers
    base_redacted = redact_sensitive_text(result)
    if base_redacted != result:
        count += 1
        result = base_redacted

    return RedactionResult(clean_text=result, redactions_count=count)
