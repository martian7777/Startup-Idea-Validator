"""Application settings.

Model tiering and search budgets live here because they are the two levers
that decide what a validation run costs. Gemini 3 bills per *search query the
model chooses to execute*, not per request, so an unbounded research agent can
quietly issue many billable searches inside a single call. The budget is
enforced in llm/budget.py, not merely requested in a prompt.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Gemini -----------------------------------------------------------
    gemini_api_key: str = ""

    # Tiering: cheap model for structuring, mid for research, best for judgement.
    model_extract: str = "gemini-3.5-flash-lite"
    model_research: str = "gemini-3.5-flash"
    model_critic: str = "gemini-3.6-flash"

    # Grounding must be a Gemini 3 model: search + structured output together
    # is a Gemini-3-only capability.
    enable_search_grounding: bool = True

    # --- Cost control -----------------------------------------------------
    max_searches_per_agent: int = 6
    max_searches_per_run: int = 25
    max_critic_revisions: int = 1
    node_timeout_seconds: float = 180.0
    node_max_attempts: int = 3

    # --- Database ---------------------------------------------------------
    # Supabase pooler (6543) is transaction-mode and breaks asyncpg prepared
    # statements; see db/session.py. Alembic must use the direct URL (5432).
    database_url: str = ""
    database_direct_url: str = ""

    # --- App --------------------------------------------------------------
    environment: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    dev_user_id: str = "00000000-0000-0000-0000-000000000001"
    max_request_body_bytes: int = 16_384
    trusted_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])

    @model_validator(mode="after")
    def _default_direct_url(self) -> "Settings":
        if not self.database_direct_url:
            self.database_direct_url = self.database_url
        return self

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.environment.lower() == "production":
            if not self.database_url:
                raise ValueError("DATABASE_URL is required in production")
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required in production")
            if any(origin.startswith("http://") for origin in self.cors_origins):
                raise ValueError("CORS_ORIGINS must contain only HTTPS origins in production")
            if "*" in self.cors_origins or "*" in self.trusted_hosts:
                raise ValueError("Wildcard origins/hosts are forbidden in production")
        return self

    @property
    def grounding_available(self) -> bool:
        return bool(self.gemini_api_key) and self.enable_search_grounding


@lru_cache
def get_settings() -> Settings:
    return Settings()
