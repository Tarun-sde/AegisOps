"""Reliable Outbox delivery dispatcher with concurrency-safe leasing and retries."""

from __future__ import annotations

import json
import logging
import os
import random
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from apps.api.app.models import OutboxEvent
from apps.api.app.outbox.signer import sign_event_envelope

logger = logging.getLogger(__name__)

DEFAULT_DESTINATION_URL = "http://127.0.0.1:8000/api/v1/automations/demo-sink"


def get_destination_url() -> str:
    return os.environ.get(
        "N8N_WEBHOOK_URL",
        os.environ.get("AEGISOPS_OUTBOX_DESTINATION_URL", DEFAULT_DESTINATION_URL),
    )


def calculate_backoff_delay(
    attempt: int,
    base_seconds: float = 2.0,
    max_seconds: float = 3600.0,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff delay with random jitter (DEC-302)."""
    exponent = max(0, attempt - 1)
    delay: float = float(min(max_seconds, base_seconds * (2**exponent)))
    if jitter:
        delay += float(random.uniform(0.1, 1.0))
    return float(delay)


def dispatch_outbox_batch(
    db: Session,
    *,
    batch_size: int = 20,
    destination_url: str | None = None,
    signing_secret: str | None = None,
    lease_seconds: int = 60,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Claim and dispatch a batch of pending outbox events (DEC-301, DEC-302).

    Concurrency invariant:
    - Events are claimed and leased in a short database transaction.
    - External HTTP delivery is performed outside of open database transactions.
    - Outcome is persisted in a follow-up transaction.
    """
    now = datetime.now(UTC)
    target_url = destination_url or get_destination_url()

    # Step 1: Claim eligible events with lease lock
    claim_query = (
        select(OutboxEvent)
        .where(
            OutboxEvent.status.in_(["PENDING", "RETRY_SCHEDULED"]),
            OutboxEvent.next_attempt_at <= now,
            or_(OutboxEvent.locked_until.is_(None), OutboxEvent.locked_until < now),
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(batch_size)
    )

    if db.bind and db.bind.dialect.name == "postgresql":
        claim_query = claim_query.with_for_update(skip_locked=True)

    claimed_events = db.scalars(claim_query).all()
    if not claimed_events:
        return {"claimed": 0, "delivered": 0, "retry_scheduled": 0, "dead_lettered": 0}

    lease_expiry = now + timedelta(seconds=lease_seconds)
    event_ids = [ev.id for ev in claimed_events]

    for ev in claimed_events:
        ev.status = "PROCESSING"
        ev.locked_until = lease_expiry
        ev.attempt_count += 1

    db.commit()

    # Step 2: Dispatch claimed events over HTTP
    delivered_count = 0
    retry_count = 0
    dead_letter_count = 0

    for event_id in event_ids:
        # Fresh query per event to avoid stale state
        event = db.get(OutboxEvent, event_id)
        if not event:
            continue

        payload_bytes = json.dumps(event.payload, default=str).encode("utf-8")
        timestamp_str = datetime.now(UTC).isoformat()
        signature = sign_event_envelope(
            payload_bytes=payload_bytes,
            event_id=str(event.id),
            timestamp_str=timestamp_str,
            secret=signing_secret,
        )

        headers = {
            "Content-Type": "application/json",
            "X-AegisOps-Event-ID": str(event.id),
            "X-AegisOps-Timestamp": timestamp_str,
            "X-AegisOps-Key-ID": "v1",
            "X-AegisOps-Signature": signature,
        }

        req = urllib.request.Request(
            url=target_url,
            data=payload_bytes,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8", errors="replace")

            if 200 <= status_code < 300:
                event.status = "DELIVERED"
                event.delivered_at = datetime.now(UTC)
                event.locked_until = None
                event.last_error_code = None
                event.last_error_summary = None
                delivered_count += 1
                logger.info(f"Delivered outbox event {event.id} ({event.event_type})")
            else:
                _handle_failure(event, status_code, response_body)
                if event.status == "DEAD_LETTERED":
                    dead_letter_count += 1
                else:
                    retry_count += 1

        except urllib.error.HTTPError as http_err:
            status_code = http_err.code
            error_body = http_err.read().decode("utf-8", errors="replace")
            _handle_failure(event, status_code, error_body)
            if event.status == "DEAD_LETTERED":
                dead_letter_count += 1
            else:
                retry_count += 1

        except Exception as exc:
            logger.warning(f"Transient network failure delivering event {event.id}: {exc}")
            _schedule_retry_or_dead_letter(event, error_code=type(exc).__name__, error_msg=str(exc))
            if event.status == "DEAD_LETTERED":
                dead_letter_count += 1
            else:
                retry_count += 1

        db.commit()

    return {
        "claimed": len(event_ids),
        "delivered": delivered_count,
        "retry_scheduled": retry_count,
        "dead_lettered": dead_letter_count,
    }


def _handle_failure(event: OutboxEvent, status_code: int, error_body: str) -> None:
    # 4xx (except 429 Too Many Requests) are permanent client errors -> DEAD_LETTER
    if 400 <= status_code < 500 and status_code != 429:
        event.status = "DEAD_LETTERED"
        event.locked_until = None
        event.last_error_code = str(status_code)
        event.last_error_summary = f"Non-retryable client error {status_code}: {error_body[:400]}"
        logger.error(f"Outbox event {event.id} permanently rejected with HTTP {status_code}")
    else:
        # 5xx, 429, or network errors -> retry or dead-letter if max attempts reached
        _schedule_retry_or_dead_letter(
            event,
            error_code=str(status_code),
            error_msg=f"HTTP {status_code}: {error_body[:400]}",
        )


def _schedule_retry_or_dead_letter(
    event: OutboxEvent,
    error_code: str,
    error_msg: str,
) -> None:
    event.locked_until = None
    event.last_error_code = error_code
    event.last_error_summary = error_msg[:500]

    if event.attempt_count >= event.max_attempts:
        event.status = "DEAD_LETTERED"
        logger.error(
            f"Outbox event {event.id} exceeded max retries ({event.max_attempts}); dead-lettered."
        )
    else:
        event.status = "RETRY_SCHEDULED"
        delay = calculate_backoff_delay(event.attempt_count)
        event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        logger.info(
            f"Outbox event {event.id} retry in {delay:.1f}s "
            f"(attempt {event.attempt_count}/{event.max_attempts})"
        )
