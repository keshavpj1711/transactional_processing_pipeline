"""Pipeline orchestration.

Runs the stages in the order the assignment requires:
  a) clean  b) detect anomalies  c) LLM-classify blank categories (batched)
  d) LLM narrative summary

It operates on data only (a CSV string in, a result object out) and depends on
the LLM interface, not a concrete provider, so it stays unit testable. The
caller (the Celery task) is responsible for persistence.
"""

from dataclasses import dataclass

import pandas as pd

from app.config import get_settings
from app.llm.base import ClassifyItem, LLMClient
from app.pipeline import aggregate, anomaly, cleaning
from app.pipeline.cleaning import ReconcileReport, UNCATEGORISED


@dataclass
class PipelineResult:
    transactions: pd.DataFrame
    reconcile: ReconcileReport
    summary_stats: dict
    narrative: str
    risk_level: str
    summary_llm_failed: bool


def _rows_needing_classification(df: pd.DataFrame) -> list[int]:
    return [pos for pos, cat in enumerate(df["category"]) if cat == UNCATEGORISED]


def _classify(df: pd.DataFrame, client: LLMClient, batch_size: int) -> pd.DataFrame:
    """Fill llm_category for rows whose category is Uncategorised, in batches."""
    df = df.copy()
    df["llm_category"] = None
    df["llm_raw_response"] = None
    df["llm_failed"] = False

    positions = _rows_needing_classification(df)
    for start in range(0, len(positions), batch_size):
        chunk = positions[start : start + batch_size]
        items = [
            ClassifyItem(
                index=pos,
                merchant=df.iloc[pos]["merchant"],
                notes=df.iloc[pos]["notes"],
                amount=df.iloc[pos]["amount"],
            )
            for pos in chunk
        ]
        result = client.classify_batch(items)
        for pos in chunk:
            df.at[df.index[pos], "llm_raw_response"] = result.raw_response
            if result.failed or pos not in result.categories:
                # Batch failed or this row was not returned: keep it flagged and
                # leave the category as Uncategorised so the job still completes.
                df.at[df.index[pos], "llm_failed"] = True
            else:
                df.at[df.index[pos], "llm_category"] = result.categories[pos]
    return df


def run(csv_text: str, client: LLMClient) -> PipelineResult:
    settings = get_settings()

    raw_df = cleaning.read_csv(csv_text)
    clean_df, reconcile = cleaning.normalize(raw_df)
    flagged_df = anomaly.detect(clean_df)
    classified_df = _classify(flagged_df, client, settings.llm_classify_batch_size)

    stats = aggregate.build_summary_stats(classified_df)
    narrative_result = client.summarize(stats)

    return PipelineResult(
        transactions=classified_df,
        reconcile=reconcile,
        summary_stats=stats,
        narrative=narrative_result.narrative,
        risk_level=narrative_result.risk_level,
        summary_llm_failed=narrative_result.failed,
    )
