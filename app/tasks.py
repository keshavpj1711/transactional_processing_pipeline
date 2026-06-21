"""Celery tasks. Real pipeline orchestration is added in a later phase."""

from app.celery_app import celery_app


@celery_app.task(name="process_job")
def process_job(job_id: int) -> None:  # pragma: no cover - placeholder
    """Placeholder; replaced by the full pipeline orchestration."""
    return None
