"""Typed configuration via pydantic-settings.

All fields have safe defaults so the mock/dev path needs no .env. Real
deployment fills in keys and infra URLs (see ADR 0006, 0007, 0008).
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAIZEN_", env_file=".env", extra="ignore")

    # Models / providers
    anthropic_api_key: str | None = None
    use_claude_code_auth: bool = False
    local_model_endpoint: str = "http://localhost:11434"  # Ollama default
    frontier_model: str = "claude-opus-4"
    cheap_model: str = "claude-haiku-4"
    local_model: str = "qwen2.5:7b"

    # Infra (filled in once Hetzner / Postgres / Redis exist)
    database_url: str | None = None
    redis_url: str | None = None

    # Behavior
    system_prompt: str = "You are Kaizen, a personal, always-improving assistant."
    talkativeness: float = 0.5


def load_settings() -> Settings:
    return Settings()
