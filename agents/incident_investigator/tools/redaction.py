import re

PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_.~+/]+=*", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.IGNORECASE), "Basic [REDACTED]"),
    (
        re.compile(
            r'(["\']?(?:password|passwd|secret|token|api[_-]?key)["\']?\s*[:=]\s*["\']?)([^"\'\s,;]+)(["\']?)',
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\3",
    ),
    (re.compile(r"(postgres(?:ql)?://[^:]+:)([^@]+)(@)", re.IGNORECASE), r"\1[REDACTED]\3"),
]


def redact_sensitive_text(text: str) -> str:
    """Pre-export redaction ensuring secrets never reach model context or evidence storage."""
    result = text
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result
