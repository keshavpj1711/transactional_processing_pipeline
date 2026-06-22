"""Lookup of available OpenRouter models.

The model catalogue is a public endpoint, so this does not need an API key. A
model is considered free when both its prompt and completion token prices are
zero. This is used to populate the ``/models/free`` endpoint so a caller can see
which model ids are valid for ``LLM_MODEL``.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


def _is_free(pricing: dict) -> bool:
    def zero(value) -> bool:
        try:
            return float(value) == 0.0
        except (TypeError, ValueError):
            return False

    return zero(pricing.get("prompt")) and zero(pricing.get("completion"))


def list_free_models(base_url: str, timeout: float = 30.0) -> list[dict]:
    """Return the free models from OpenRouter, sorted by id.

    Raises on a network/response error so the caller can surface it.
    """
    url = f"{base_url.rstrip('/')}/models"
    resp = httpx.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json().get("data", [])

    free = []
    for model in data:
        pricing = model.get("pricing") or {}
        if _is_free(pricing):
            free.append(
                {
                    "id": model.get("id"),
                    "name": model.get("name"),
                    "context_length": model.get("context_length"),
                }
            )
    free.sort(key=lambda m: m["id"] or "")
    return free


def _responds(base_url: str, api_key: str, model: str, timeout: float = 20.0) -> bool:
    """Cheap probe: does this model answer a one-token request right now?

    Free models are frequently rate limited (HTTP 429); this filters those out
    so selection lands on a model that is actually usable at this moment.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
    try:
        resp = httpx.post(
            url, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout
        )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def select_best_model(
    base_url: str, api_key: str, preferences: list[str]
) -> str | None:
    """Pick the first preferred model that is both free and responding now.

    Returns the model id, or None if nothing in the preference list is available.
    """
    try:
        free_ids = {m["id"] for m in list_free_models(base_url)}
    except httpx.HTTPError as exc:
        logger.warning("could not fetch model catalogue for selection: %s", exc)
        free_ids = set(preferences)  # fall back to trusting the preference list

    for model in preferences:
        if model in free_ids and _responds(base_url, api_key, model):
            logger.info("selected free model: %s", model)
            return model
        logger.info("model unavailable, trying next: %s", model)
    logger.warning("no preferred free model is currently available")
    return None
