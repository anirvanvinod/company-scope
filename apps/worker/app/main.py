"""
CompanyScope Worker — Celery application entry point.

Phase 0: Celery app is configured with all queue definitions but no tasks yet.
Task modules (ingestion, document_fetch, parser, risk_engine, snapshot) are
registered in later phases and listed in the `include` parameter below.

Queue definitions match docs/01-system-architecture.md §Background jobs.
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "companyscope_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    # Task modules registered as they are implemented:
    # "app.tasks.risk_engine",
    # "app.tasks.snapshot",
    include=["app.tasks.ingestion", "app.tasks.document_fetch", "app.tasks.document_parse", "app.tasks.extraction", "app.tasks.analysis", "app.tasks.snapshot"],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Visibility into running tasks
    task_track_started=True,
    # Default queue for tasks that do not specify an explicit queue.
    # With a Redis broker, queues are created on demand as Redis list keys —
    # no explicit queue declaration is needed (unlike AMQP/RabbitMQ).
    #
    # Queue names defined in docs/01-system-architecture.md §Background jobs:
    #   company_refresh, document_fetch, document_parse, risk_recompute,
    #   watchlist_refresh, send_notifications, rebuild_snapshots
    #
    # task_routes (added in later phases) will map each task to its queue.
    task_default_queue="company_refresh",
    task_routes={},  # populated as task modules are added in later phases
    # Retry behaviour defaults — individual tasks may override
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


if __name__ == "__main__":
    celery_app.start()
