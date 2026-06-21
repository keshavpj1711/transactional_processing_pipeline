"""LLM client interface and shared data types.

The pipeline depends only on this interface, so the concrete provider
(OpenRouter or the deterministic stub) is an implementation detail selected at
runtime by the factory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# The fixed set of categories the model is allowed to assign.
ALLOWED_CATEGORIES = [
    "Food",
    "Shopping",
    "Travel",
    "Transport",
    "Utilities",
    "Cash Withdrawal",
    "Entertainment",
    "Other",
]


@dataclass
class ClassifyItem:
    """One uncategorised transaction to be classified."""

    index: int
    merchant: str | None
    notes: str | None
    amount: float | None


@dataclass
class NarrativeResult:
    narrative: str
    risk_level: str
    raw_response: str = ""
    failed: bool = False


@dataclass
class ClassifyResult:
    """Maps a ClassifyItem.index to its assigned category."""

    categories: dict[int, str] = field(default_factory=dict)
    raw_response: str = ""
    failed: bool = False


class LLMClient(ABC):
    @abstractmethod
    def classify_batch(self, items: list[ClassifyItem]) -> ClassifyResult:
        """Assign a category to each item. Must not raise on a bad response."""

    @abstractmethod
    def summarize(self, stats: dict) -> NarrativeResult:
        """Produce a narrative summary and risk level from precomputed stats."""
