"""Celery tasks.

``process_job`` is the asynchronous entry point: the API enqueues it with a job
id and returns immediately. The worker owns the job's status lifecycle and runs
the processing pipeline, then persists the cleaned transactions and summary.
"""

import logging

import pandas as pd

from app.celery_app import celery_app
from app.db import SessionLocal
from app.llm.factory import get_llm_client
from app.models import Job, JobStatus, JobSummary, Transaction
from app.pipeline import orchestrator
from app.pipeline.aggregate import resolved_category
from app import repository

logger = logging.getLogger(__name__)


def _persist(db, job: Job, result: orchestrator.PipelineResult) -> None:
    df = result.transactions

    job.row_count_raw = result.reconcile.raw
    job.row_count_clean = result.reconcile.clean

    any_classification_failed = False
    for _, row in df.iterrows():
        llm_failed = bool(row.get("llm_failed", False))
        any_classification_failed = any_classification_failed or llm_failed
        db.add(
            Transaction(
                job_id=job.id,
                txn_id=row["txn_id"],
                date=row["date"],
                merchant=row["merchant"],
                amount=None if pd.isna(row["amount"]) else float(row["amount"]),
                currency=row["currency"],
                status=row["status"],
                category=row["category"],
                account_id=row["account_id"],
                notes=row["notes"],
                is_anomaly=bool(row["is_anomaly"]),
                anomaly_reason=row["anomaly_reason"],
                llm_category=row.get("llm_category"),
                llm_raw_response=row.get("llm_raw_response"),
                llm_failed=llm_failed,
            )
        )

    stats = result.summary_stats
    db.add(
        JobSummary(
            job_id=job.id,
            total_spend_inr=stats["total_spend_inr"],
            total_spend_usd=stats["total_spend_usd"],
            top_merchants=stats["top_merchants"],
            anomaly_count=stats["anomaly_count"],
            narrative=result.narrative,
            risk_level=result.risk_level,
            llm_failed=result.summary_llm_failed or any_classification_failed,
        )
    )
    db.commit()


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
        repository.clear_job_results(db, job_id)

        client = get_llm_client()
        result = orchestrator.run(job.raw_csv, client)

        if not result.reconcile.is_consistent():
            raise ValueError(
                f"row reconciliation failed: raw={result.reconcile.raw} "
                f"duplicates={result.reconcile.duplicates_removed} "
                f"clean={result.reconcile.clean}"
            )

        _persist(db, job, result)
        repository.set_job_status(db, job, JobStatus.completed.value)
        logger.info(
            "job %s completed: %d raw, %d clean, %d anomalies",
            job_id,
            result.reconcile.raw,
            result.reconcile.clean,
            result.summary_stats["anomaly_count"],
        )
    except Exception as exc:  # noqa: BLE001 - surface any failure on the job
        logger.exception("job %s failed", job_id)
        db.rollback()
        job = repository.get_job(db, job_id)
        if job is not None:
            repository.set_job_status(db, job, JobStatus.failed.value, error_message=str(exc))
        raise
    finally:
        db.close()
