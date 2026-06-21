"""Data cleaning.

Pure functions that take raw transaction rows and return a normalised
DataFrame plus a reconciliation report. Nothing here touches the database or the
queue, so the rules can be unit tested in isolation and reused by any caller.

Cleaning rules (from the assignment):
  - normalise dates to ISO 8601 (input is a mix of DD-MM-YYYY and YYYY/MM/DD)
  - strip currency symbols from amounts
  - uppercase status values
  - uppercase currency values
  - fill missing categories with 'Uncategorised'
  - remove exact duplicate rows
"""

from dataclasses import dataclass
from datetime import datetime
import io

import pandas as pd

RAW_COLUMNS = [
    "txn_id",
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
    "category",
    "account_id",
    "notes",
]

# Input dates appear in exactly these two shapes. Parsing with explicit formats
# keeps the result predictable and debuggable; an unparseable date is left blank
# rather than guessed at.
DATE_FORMATS = ("%d-%m-%Y", "%Y/%m/%d")

UNCATEGORISED = "Uncategorised"


@dataclass
class ReconcileReport:
    raw: int
    duplicates_removed: int
    clean: int

    def is_consistent(self) -> bool:
        return self.raw - self.duplicates_removed == self.clean


def read_csv(text: str) -> pd.DataFrame:
    """Parse CSV text into a DataFrame with all fields as strings."""
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    return df


def normalize_date(value: str | None) -> str | None:
    """Return an ISO 8601 date string, or None if the value cannot be parsed."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def strip_amount(value: str | None) -> float | None:
    """Strip currency symbols/commas and return a float, or None if not numeric."""
    if value is None:
        return None
    raw = str(value).strip().replace("$", "").replace(",", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


def normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, ReconcileReport]:
    """Apply all cleaning rules and report the row accounting.

    Deduplication is on the full normalised row so that genuinely identical rows
    collapse while rows that merely share a blank txn_id are kept.
    """
    df = df.copy()
    for col in RAW_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[RAW_COLUMNS]

    raw_count = len(df)

    df["date"] = df["date"].map(normalize_date)
    df["amount"] = df["amount"].map(strip_amount)
    df["merchant"] = df["merchant"].map(_clean_text)
    df["account_id"] = df["account_id"].map(_clean_text)
    df["notes"] = df["notes"].map(_clean_text)
    df["txn_id"] = df["txn_id"].map(_clean_text)

    df["status"] = df["status"].map(lambda v: _clean_text(v).upper() if _clean_text(v) else None)
    df["currency"] = df["currency"].map(lambda v: _clean_text(v).upper() if _clean_text(v) else None)

    category = df["category"].map(_clean_text)
    df["category"] = category.where(category.notna(), UNCATEGORISED)

    before = len(df)
    df = df.drop_duplicates(keep="first").reset_index(drop=True)
    duplicates_removed = before - len(df)

    report = ReconcileReport(
        raw=raw_count,
        duplicates_removed=duplicates_removed,
        clean=len(df),
    )
    return df, report
