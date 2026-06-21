"""Pydantic models for API request and response bodies.

These define the contract the API exposes; they are intentionally separate from
the SQLAlchemy ORM models so storage and serialization can evolve independently.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobCreatedResponse(BaseModel):
    """Returned immediately from the upload endpoint."""

    job_id: int
    status: str
    filename: str


class JobStatusSummary(BaseModel):
    """High-level stats included once a job is completed."""

    row_count_raw: int | None = None
    row_count_clean: int | None = None
    anomaly_count: int | None = None
    risk_level: str | None = None


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    summary: JobStatusSummary | None = None
    error_message: str | None = None


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    row_count_raw: int | None = None
    row_count_clean: int | None = None
    created_at: datetime


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    txn_id: str | None = None
    date: str | None = None
    merchant: str | None = None
    amount: float | None = None
    currency: str | None = None
    status: str | None = None
    category: str | None = None
    account_id: str | None = None
    notes: str | None = None
    is_anomaly: bool = False
    anomaly_reason: str | None = None
    llm_category: str | None = None
    llm_failed: bool = False


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    txn_id: str | None = None
    merchant: str | None = None
    amount: float | None = None
    currency: str | None = None
    account_id: str | None = None
    anomaly_reason: str | None = None


class NarrativeSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_spend_inr: float = 0.0
    total_spend_usd: float = 0.0
    top_merchants: list = []
    anomaly_count: int = 0
    narrative: str | None = None
    risk_level: str | None = None
    llm_failed: bool = False


class CategorySpend(BaseModel):
    category: str
    currency: str
    total: float
    count: int


class JobResultsResponse(BaseModel):
    job_id: int
    status: str
    transactions: list[TransactionOut]
    anomalies: list[AnomalyOut]
    category_breakdown: list[CategorySpend]
    summary: NarrativeSummaryOut | None = None
