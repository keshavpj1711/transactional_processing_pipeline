"""Select the LLM client based on settings.

The stub is used whenever real calls are not configured, so the pipeline always
has a working client and never blocks on a missing key. When a real key is set
but no explicit model is pinned, the best currently-available free model is
chosen automatically and cached so the probe runs once per process.
"""

import logging

from app.config import get_settings
from app.llm import models as model_catalogue
from app.llm.base import LLMClient
from app.llm.openrouter import OpenRouterClient
from app.llm.stub import StubLLMClient

logger = logging.getLogger(__name__)

_cached_model: str | None = None


def resolve_model() -> str | None:
    """Return the model id to use: the pinned one, or an auto-selected free one.

    The auto-selected result is cached for the life of the process.
    """
    global _cached_model
    settings = get_settings()

    if settings.llm_model:
        return settings.llm_model
    if _cached_model:
        return _cached_model

    _cached_model = model_catalogue.select_best_model(
        settings.openrouter_base_url,
        settings.openrouter_api_key,
        settings.llm_model_preferences,
    )
    return _cached_model


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_enabled:
        model = resolve_model()
        if model:
            logger.info("using OpenRouter model %s", model)
            return OpenRouterClient(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=model,
                max_retries=settings.llm_max_retries,
            )
        logger.warning("no free model available; falling back to stub")
    logger.info("using deterministic stub LLM client")
    return StubLLMClient()
