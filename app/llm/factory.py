"""Select the LLM client based on settings.

The stub is used whenever real calls are not configured, so the pipeline always
has a working client and never blocks on a missing key.
"""

import logging

from app.config import get_settings
from app.llm.base import LLMClient
from app.llm.openrouter import OpenRouterClient
from app.llm.stub import StubLLMClient

logger = logging.getLogger(__name__)


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_enabled:
        logger.info("using OpenRouter model %s", settings.llm_model)
        return OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.llm_model,
            max_retries=settings.llm_max_retries,
        )
    logger.info("using deterministic stub LLM client")
    return StubLLMClient()
