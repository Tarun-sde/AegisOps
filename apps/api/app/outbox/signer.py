"""HMAC-SHA256 signature envelope and replay protection for outbound webhooks."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime

DEFAULT_WEBHOOK_SECRET = "aegisops-demo-webhook-secret-phase6"
MAX_SKEW_SECONDS = 300  # 5 minutes clock skew tolerance


def get_webhook_signing_secret() -> str:
    return os.environ.get("AEGISOPS_WEBHOOK_SECRET", DEFAULT_WEBHOOK_SECRET)


def build_canonical_string(timestamp_str: str, event_id: str, payload_bytes: bytes) -> str:
    """Canonical representation combining timestamp, event ID, and payload SHA-256 digest."""
    payload_digest = hashlib.sha256(payload_bytes).hexdigest()
    return f"{timestamp_str}.{event_id}.{payload_digest}"


def sign_event_envelope(
    payload_bytes: bytes,
    event_id: str,
    timestamp_str: str,
    secret: str | None = None,
) -> str:
    """Generate HMAC-SHA256 signature string formatted as 'sha256={hex}'."""
    signing_secret = secret or get_webhook_signing_secret()
    canonical = build_canonical_string(timestamp_str, event_id, payload_bytes)
    sig = hmac.new(
        signing_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


def verify_event_signature(
    payload_bytes: bytes,
    event_id: str,
    timestamp_str: str,
    signature: str,
    secret: str | None = None,
    max_skew_seconds: int = MAX_SKEW_SECONDS,
) -> tuple[bool, str | None]:
    """Verify inbound signature in constant time with clock-skew enforcement.

    Returns:
        (is_valid, error_reason)
    """
    if not signature or not signature.startswith("sha256="):
        return False, "Signature missing or not prefixed with 'sha256='"

    provided_sig = signature.removeprefix("sha256=").strip()
    if not provided_sig:
        return False, "Empty signature digest"

    # 1. Clock skew / replay check
    try:
        # Standardize ISO-8601 UTC timestamp
        clean_ts = timestamp_str.replace("Z", "+00:00")
        event_time = datetime.fromisoformat(clean_ts)
        now = datetime.now(UTC)
        skew = abs((now - event_time).total_seconds())
        if skew > max_skew_seconds:
            return (
                False,
                f"Timestamp skew ({skew:.1f}s) exceeds allowed limit of {max_skew_seconds}s",
            )
    except Exception as exc:
        return False, f"Invalid ISO-8601 timestamp format '{timestamp_str}': {exc}"

    # 2. Recompute expected signature
    signing_secret = secret or get_webhook_signing_secret()
    canonical = build_canonical_string(timestamp_str, event_id, payload_bytes)
    expected_sig = hmac.new(
        signing_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # 3. Constant-time digest comparison
    if not hmac.compare_digest(provided_sig, expected_sig):
        return False, "Signature mismatch"

    return True, None
