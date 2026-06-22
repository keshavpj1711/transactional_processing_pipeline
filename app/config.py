"""Application settings, loaded once from the environment.

This module is the single source of truth for configuration. Database, broker,
and LLM details are all read here so that nothing else in the codebase hardcodes
a connection string or an API key.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage / messaging
    database_url: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/transactions"
    redis_url: str = "redis://redis:6379/0"

    # LLM (OpenRouter, OpenAI-compatible)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # An explicit model id pins the choice. Left blank, the best available free
    # model is selected automatically (free models are frequently rate limited,
    # so a fixed choice can be unavailable at any moment).
    llm_model: str = ""
    use_stub_llm: bool = False

    # Ordered by preference; the first that responds (not rate limited) is used
    # when no explicit llm_model is set.
    llm_model_preferences: list[str] = [
        "openai/gpt-oss-120b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "openai/gpt-oss-20b:free",
        "nvidia/nemotron-nano-9b-v2:free",
        "google/gemma-4-31b-it:free",
    ]

    # Pipeline tuning
    llm_classify_batch_size: int = 20
    llm_max_retries: int = 3

    @property
    def llm_enabled(self) -> bool:
        """Real LLM is used only when not stubbed and a key is present."""
        return not self.use_stub_llm and bool(self.openrouter_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
