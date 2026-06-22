"""OpenRouter-backed LLM client (OpenAI-compatible chat completions API).

Each call retries with exponential backoff. If every retry fails, the result is
marked ``failed`` and returned rather than raised, so one bad batch never fails
the whole job.
"""

import logging
import time

import httpx

from app.llm import prompts
from app.llm.base import (
    ClassifyItem,
    ClassifyResult,
    LLMClient,
    NarrativeResult,
)

logger = logging.getLogger(__name__)


class OpenRouterClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_retries: int = 3,
        timeout: float = 60.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_retries = max_retries
        self._timeout = timeout

    def _chat(self, system: str, user: str) -> str:
        """Call the model, retrying with exponential backoff. Raises on failure."""
        url = f"{self._base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = httpx.post(url, json=payload, headers=headers, timeout=self._timeout)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"].get("content")
                if not content:
                    raise ValueError("model returned empty content")
                return content
            except Exception as exc:  # noqa: BLE001 - retry any transport/response error
                last_error = exc
                wait = 2 ** attempt
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s; retrying in %ds",
                    attempt + 1,
                    self._max_retries,
                    exc,
                    wait,
                )
                if attempt < self._max_retries - 1:
                    time.sleep(wait)
        raise RuntimeError(f"LLM call failed after {self._max_retries} attempts: {last_error}")

    def classify_batch(self, items: list[ClassifyItem]) -> ClassifyResult:
        if not items:
            return ClassifyResult()
        valid_indices = {item.index for item in items}
        user = prompts.build_classify_prompt(items)
        try:
            raw = self._chat(prompts.CLASSIFY_SYSTEM, user)
            mapping = prompts.parse_classify_response(raw, valid_indices)
            return ClassifyResult(categories=mapping, raw_response=raw)
        except Exception as exc:  # noqa: BLE001
            logger.error("classification batch failed permanently: %s", exc)
            return ClassifyResult(raw_response=str(exc), failed=True)

    def summarize(self, stats: dict) -> NarrativeResult:
        user = prompts.build_narrative_prompt(stats)
        try:
            raw = self._chat(prompts.NARRATIVE_SYSTEM, user)
            narrative, risk = prompts.parse_narrative_response(raw)
            return NarrativeResult(narrative=narrative, risk_level=risk, raw_response=raw)
        except Exception as exc:  # noqa: BLE001
            logger.error("narrative summary failed permanently: %s", exc)
            return NarrativeResult(
                narrative="Summary unavailable; the language model could not be reached.",
                risk_level="medium",
                raw_response=str(exc),
                failed=True,
            )
