"""Celery tasks.

``process_job`` is the asynchronous entry point: the API enqueues it with a job
id and returns immediately. The worker owns the full lifecycle of the job's
status. The data-processing pipeline is added in a later phase; for now the task
manages the state transitions it will wrap.
"""

import logging

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models import JobStatus
from app import repository

logger = logging.getLogger(__name__)


@celery_app.task(name="process_job")
def process_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = repository.get_job(db, job_id)
        if job is None:
            logger.warning("process_job called for missing job %s", job_id)
            return
        if job.status == JobStatus.completed.value:
            logger.info("job %s already completed; skipping", job_id)
            return

        repository.set_job_status(db, job, JobStatus.processing.value)

        # Re-running must not leave duplicate rows behind.
        repository.clear_job_results(db, job_id)

        # The cleaning/anomaly/LLM pipeline is wired in here in a later phase.

        repository.set_job_status(db, job, JobStatus.completed.value)
        logger.info("job %s completed", job_id)
    except Exception as exc:  # noqa: BLE001 - surface any failure on the job
        logger.exception("job %s failed", job_id)
        job = repository.get_job(db, job_id)
        if job is not None:
            repository.set_job_status(db, job, JobStatus.failed.value, error_message=str(exc))
        raise
    finally:
        db.close()
