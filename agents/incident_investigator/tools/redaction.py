import re

PATTERNS = [
    # Authorization header tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_.~+/]+=*", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.IGNORECASE), "Basic [REDACTED]"),
    # JWT tokens
    (
        re.compile(
            r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+",
        ),
        "[REDACTED_JWT]",
    ),
    # Database connection URIs (PostgreSQL, MongoDB, MySQL, Redis)
    (
        re.compile(
            r"((?:postgres(?:ql)?|mongodb(?:\+srv)?|mysql|redis)://[^:]+:)([^@\s]+)(@[A-Za-z0-9_.\-:]+)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\3",
    ),
    # Credentials in key-value pairs (skip already redacted values)
    (
        re.compile(
            r'(["\']?(?:password|passwd|secret|token|api[_-]?key|client_secret|private_key)["\']?\s*[:=]\s*["\']?)(?!\[REDACTED)([^"\'\s,;]+)(["\']?)',
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\3",
    ),
    # Session cookies
    (
        re.compile(
            r"(?i)\b([A-Za-z0-9_]*session(?:_?id)?|connect\.sid|auth(?:_?token)?|access_token|refresh_token)\s*=\s*([A-Za-z0-9_\-\.%+=]+)",
        ),
        r"\1=[REDACTED_COOKIE]",
    ),
    # US Social Security Numbers
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
]


def redact_sensitive_text(text: str) -> str:
    """Pre-export redaction ensuring secrets never reach model context or evidence storage."""
    result = text
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result
