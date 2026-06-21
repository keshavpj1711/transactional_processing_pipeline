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
    llm_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    use_stub_llm: bool = False

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
