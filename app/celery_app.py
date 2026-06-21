"""Celery application instance.

The worker and the API both import ``celery_app`` from here. Tasks live in
``app.tasks`` and are registered via ``include``.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "transaction_pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
)
