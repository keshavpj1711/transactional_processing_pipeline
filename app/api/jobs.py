"""Job endpoints.

The read path (status, results, list) only reads from the database; it never
computes anything. All processing happens asynchronously in the Celery worker.
The upload endpoint validates the file, records the job, enqueues the work, and
returns the job id immediately.
"""

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app import repository, schemas
from app.db import get_db
from app.models import JobStatus
from app.tasks import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])

EXPECTED_COLUMNS = {
    "txn_id",
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
    "category",
    "account_id",
    "notes",
}

_VALID_STATUSES = {s.value for s in JobStatus}


@router.post("/upload", response_model=schemas.JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_job(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Accept a CSV upload, create a pending job, and enqueue processing."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only .csv files are accepted.")

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File is not valid UTF-8 text.")

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise HTTPException(status_code=422, detail="CSV file is empty.")

    header_set = {h.strip() for h in header}
    missing = EXPECTED_COLUMNS - header_set
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CSV is missing required columns: {', '.join(sorted(missing))}",
        )

    job = repository.create_job(db, filename=file.filename, raw_csv=text)
    process_job.delay(job.id)
    return schemas.JobCreatedResponse(job_id=job.id, status=job.status, filename=job.filename)


@router.get("/{job_id}/status", response_model=schemas.JobStatusResponse)
def job_status(job_id: int, db: Session = Depends(get_db)):
    job = repository.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    summary = None
    if job.status == JobStatus.completed.value:
        job_summary = repository.get_summary(db, job_id)
        summary = schemas.JobStatusSummary(
            row_count_raw=job.row_count_raw,
            row_count_clean=job.row_count_clean,
            anomaly_count=job_summary.anomaly_count if job_summary else None,
            risk_level=job_summary.risk_level if job_summary else None,
        )

    return schemas.JobStatusResponse(
        job_id=job.id,
        status=job.status,
        summary=summary,
        error_message=job.error_message,
    )


@router.get("/{job_id}/results", response_model=schemas.JobResultsResponse)
def job_results(job_id: int, db: Session = Depends(get_db)):
    job = repository.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != JobStatus.completed.value:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not complete (current status: {job.status}).",
        )

    transactions = repository.get_transactions(db, job_id)
    anomalies = [t for t in transactions if t.is_anomaly]
    breakdown = repository.category_breakdown(db, job_id)
    summary = repository.get_summary(db, job_id)

    return schemas.JobResultsResponse(
        job_id=job.id,
        status=job.status,
        transactions=[schemas.TransactionOut.model_validate(t) for t in transactions],
        anomalies=[schemas.AnomalyOut.model_validate(t) for t in anomalies],
        category_breakdown=[schemas.CategorySpend(**b) for b in breakdown],
        summary=schemas.NarrativeSummaryOut.model_validate(summary) if summary else None,
    )


@router.get("", response_model=list[schemas.JobListItem])
def list_jobs(
    status: str | None = Query(default=None, description="Filter by job status."),
    db: Session = Depends(get_db),
):
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Expected one of: {', '.join(sorted(_VALID_STATUSES))}",
        )
    jobs = repository.list_jobs(db, status=status)
    return [schemas.JobListItem.model_validate(j) for j in jobs]
