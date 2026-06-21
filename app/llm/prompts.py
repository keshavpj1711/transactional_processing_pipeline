"""Prompt construction and response parsing for the LLM calls.

Parsing is deliberately defensive: the model is asked for JSON, but the output
is treated as untrusted and validated before use.
"""

import json

from app.llm.base import ALLOWED_CATEGORIES, ClassifyItem

CLASSIFY_SYSTEM = (
    "You are a financial transaction classifier. Assign each transaction exactly "
    "one category from this list: " + ", ".join(ALLOWED_CATEGORIES) + ". "
    "Respond only with a JSON object of the form "
    '{"results": [{"index": <int>, "category": "<one of the allowed>"}]}.'
)

NARRATIVE_SYSTEM = (
    "You are a financial analyst. Given aggregate statistics about a batch of "
    "transactions, respond only with a JSON object of the form "
    '{"narrative": "<2-3 sentences>", "risk_level": "low|medium|high"}.'
)


def build_classify_prompt(items: list[ClassifyItem]) -> str:
    lines = ["Classify these transactions:"]
    for item in items:
        merchant = item.merchant or "unknown"
        notes = (item.notes or "").strip()
        amount = item.amount if item.amount is not None else "unknown"
        line = f"- index {item.index}: merchant={merchant}, amount={amount}"
        if notes:
            line += f", notes={notes[:80]}"
        lines.append(line)
    return "\n".join(lines)


def build_narrative_prompt(stats: dict) -> str:
    return "Summarise this transaction batch:\n" + json.dumps(stats, default=str)


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Strip a leading ```json / ``` fence and the trailing fence.
        cleaned = cleaned.split("```", 2)
        cleaned = cleaned[1] if len(cleaned) > 1 else text
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned)


def parse_classify_response(text: str, valid_indices: set[int]) -> dict[int, str]:
    """Parse a classification response into {index: category}.

    Raises ValueError on malformed JSON or unusable content so the caller can
    retry; entries with unknown categories or indices are dropped.
    """
    data = _extract_json(text)
    results = data.get("results", data if isinstance(data, list) else None)
    if not isinstance(results, list):
        raise ValueError("classification response missing 'results' list")

    allowed = set(ALLOWED_CATEGORIES)
    mapping: dict[int, str] = {}
    for entry in results:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("index")
        category = entry.get("category")
        if idx in valid_indices and category in allowed:
            mapping[int(idx)] = category
    if not mapping:
        raise ValueError("classification response produced no valid entries")
    return mapping


def parse_narrative_response(text: str) -> tuple[str, str]:
    data = _extract_json(text)
    narrative = data.get("narrative")
    risk = data.get("risk_level")
    if not isinstance(narrative, str) or risk not in {"low", "medium", "high"}:
        raise ValueError("narrative response missing valid fields")
    return narrative, risk
