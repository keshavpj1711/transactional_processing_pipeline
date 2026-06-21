"""Aggregations over cleaned, classified transactions.

These feed the narrative summary (totals, top merchants, anomaly count). The
per-category breakdown served by the API is computed separately in the
repository, directly from the database.
"""

import pandas as pd


def resolved_category(row: pd.Series) -> str:
    """LLM category takes precedence over the original when present."""
    return row.get("llm_category") or row.get("category") or "Uncategorised"


def total_spend_by_currency(df: pd.DataFrame) -> dict[str, float]:
    if df.empty or "amount" not in df.columns:
        return {}
    grouped = df.dropna(subset=["amount"]).groupby("currency")["amount"].sum()
    return {str(k): round(float(v), 2) for k, v in grouped.items()}


def top_merchants(df: pd.DataFrame, n: int = 3) -> list[dict]:
    if df.empty or "merchant" not in df.columns:
        return []
    grouped = (
        df.dropna(subset=["amount"])
        .groupby("merchant")["amount"]
        .agg(["sum", "count"])
        .sort_values("sum", ascending=False)
        .head(n)
    )
    return [
        {"merchant": str(merchant), "total": round(float(r["sum"]), 2), "count": int(r["count"])}
        for merchant, r in grouped.iterrows()
    ]


def build_summary_stats(df: pd.DataFrame) -> dict:
    """Stats passed to the LLM for the narrative and stored on the summary."""
    totals = total_spend_by_currency(df)
    return {
        "total_spend_inr": totals.get("INR", 0.0),
        "total_spend_usd": totals.get("USD", 0.0),
        "top_merchants": top_merchants(df),
        "anomaly_count": int(df["is_anomaly"].sum()) if "is_anomaly" in df.columns else 0,
    }
