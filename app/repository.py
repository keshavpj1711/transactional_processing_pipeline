"""Database access helpers.

These functions are the only place the rest of the app reads or writes job data.
They contain no business logic; cleaning, anomaly detection, and aggregation
live in ``app.pipeline``.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Job, JobStatus, JobSummary, Transaction


def create_job(db: Session, filename: str, raw_csv: str) -> Job:
    job = Job(filename=filename, raw_csv=raw_csv, status=JobStatus.pending.value)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> Job | None:
    return db.get(Job, job_id)


def list_jobs(db: Session, status: str | None = None) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if status:
        stmt = stmt.where(Job.status == status)
    return list(db.scalars(stmt).all())


def set_job_status(db: Session, job: Job, status: str, error_message: str | None = None) -> None:
    job.status = status
    if error_message is not None:
        job.error_message = error_message
    if status in (JobStatus.completed.value, JobStatus.failed.value):
        job.completed_at = datetime.now(timezone.utc)
    db.commit()


def clear_job_results(db: Session, job_id: int) -> None:
    """Remove any prior transactions/summary so reprocessing is idempotent."""
    db.query(Transaction).filter(Transaction.job_id == job_id).delete()
    db.query(JobSummary).filter(JobSummary.job_id == job_id).delete()
    db.commit()


def get_transactions(db: Session, job_id: int) -> list[Transaction]:
    stmt = select(Transaction).where(Transaction.job_id == job_id).order_by(Transaction.id)
    return list(db.scalars(stmt).all())


def get_summary(db: Session, job_id: int) -> JobSummary | None:
    return db.scalars(select(JobSummary).where(JobSummary.job_id == job_id)).first()


def category_breakdown(db: Session, job_id: int) -> list[dict]:
    """Per-category, per-currency spend computed in the database.

    The resolved category is the LLM-assigned one when present, otherwise the
    original category. Currencies are kept separate so INR and USD never mix.
    """
    resolved = func.coalesce(Transaction.llm_category, Transaction.category)
    stmt = (
        select(
            resolved.label("category"),
            Transaction.currency,
            func.sum(Transaction.amount).label("total"),
            func.count().label("count"),
        )
        .where(Transaction.job_id == job_id)
        .group_by(resolved, Transaction.currency)
        .order_by(resolved, Transaction.currency)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "category": r.category or "Uncategorised",
            "currency": r.currency or "UNKNOWN",
            "total": round(float(r.total or 0.0), 2),
            "count": int(r.count),
        }
        for r in rows
    ]
