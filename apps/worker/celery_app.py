import os

from celery import Celery  # type: ignore[import-untyped]

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

celery_app = Celery(
    "aegisops_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["apps.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_always_eager=os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1",
)

celery_app.conf.beat_schedule = {
    "reconcile-simulation-expiry-periodic": {
        "task": "aegisops.reconcile_simulation_expiry",
        "schedule": 10.0,
        "options": {"expires": 8.0},
    },
    "dispatch-outbox-events-periodic": {
        "task": "aegisops.dispatch_outbox_events",
        "schedule": 15.0,
        "options": {"expires": 12.0},
    },
}
