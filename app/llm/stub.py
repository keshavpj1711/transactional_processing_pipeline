"""Deterministic LLM stub.

Used when no API key is configured or when ``USE_STUB_LLM`` is set. It lets the
whole stack run with a single ``docker compose up`` and no external calls, and
makes tests reproducible. Classification is a keyword match on the merchant; the
narrative is templated from the supplied stats.
"""

from app.llm.base import (
    ClassifyItem,
    ClassifyResult,
    LLMClient,
    NarrativeResult,
)

_MERCHANT_CATEGORY = {
    "swiggy": "Food",
    "zomato": "Food",
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "irctc": "Travel",
    "makemytrip": "Travel",
    "ola": "Transport",
    "uber": "Transport",
    "jio recharge": "Utilities",
    "hdfc atm": "Cash Withdrawal",
}


def _category_for(merchant: str | None) -> str:
    if not merchant:
        return "Other"
    key = merchant.strip().lower()
    return _MERCHANT_CATEGORY.get(key, "Other")


class StubLLMClient(LLMClient):
    def classify_batch(self, items: list[ClassifyItem]) -> ClassifyResult:
        mapping = {item.index: _category_for(item.merchant) for item in items}
        return ClassifyResult(categories=mapping, raw_response="stub")

    def summarize(self, stats: dict) -> NarrativeResult:
        anomaly_count = stats.get("anomaly_count", 0)
        total_inr = stats.get("total_spend_inr", 0.0)
        total_usd = stats.get("total_spend_usd", 0.0)
        if anomaly_count >= 5:
            risk = "high"
        elif anomaly_count >= 1:
            risk = "medium"
        else:
            risk = "low"
        narrative = (
            f"Processed transactions totalling {total_inr:.2f} INR and "
            f"{total_usd:.2f} USD. {anomaly_count} transaction(s) were flagged as "
            f"anomalous. Overall risk is assessed as {risk}."
        )
        return NarrativeResult(narrative=narrative, risk_level=risk, raw_response="stub")
