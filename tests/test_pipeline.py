from pathlib import Path

from app.llm.stub import StubLLMClient
from app.pipeline import orchestrator
from app.pipeline.cleaning import UNCATEGORISED

FIXTURE = Path(__file__).parent / "fixtures" / "transactions_sample.csv"


def test_pipeline_runs_end_to_end_with_stub():
    text = FIXTURE.read_text()
    result = orchestrator.run(text, StubLLMClient())

    # Reconciliation invariant holds across the whole pipeline.
    assert result.reconcile.is_consistent()
    assert result.reconcile.raw == 95
    assert result.reconcile.clean == 85
    assert len(result.transactions) == 85


def test_blank_categories_get_llm_category():
    text = FIXTURE.read_text()
    result = orchestrator.run(text, StubLLMClient())
    df = result.transactions

    needed = df[df["category"] == UNCATEGORISED]
    # Every uncategorised row receives an llm_category from the stub.
    assert (needed["llm_category"].notna()).all()
    # Rows that already had a category are not sent to the LLM.
    categorised = df[df["category"] != UNCATEGORISED]
    assert categorised["llm_category"].isna().all()


def test_summary_stats_present():
    text = FIXTURE.read_text()
    result = orchestrator.run(text, StubLLMClient())
    stats = result.summary_stats
    assert stats["total_spend_inr"] > 0
    assert len(stats["top_merchants"]) <= 3
    assert result.risk_level in {"low", "medium", "high"}
    assert isinstance(result.narrative, str) and result.narrative


def test_failing_llm_marks_rows_but_completes():
    """A classifier that always fails leaves rows Uncategorised + flagged, no raise."""

    class FailingClient(StubLLMClient):
        def classify_batch(self, items):
            from app.llm.base import ClassifyResult

            return ClassifyResult(raw_response="boom", failed=True)

    text = FIXTURE.read_text()
    result = orchestrator.run(text, FailingClient())
    df = result.transactions
    blanks = df[df["category"] == UNCATEGORISED]
    assert blanks["llm_failed"].all()
    assert (blanks["llm_category"].isna()).all()
    # Pipeline still produced a consistent result.
    assert result.reconcile.is_consistent()
