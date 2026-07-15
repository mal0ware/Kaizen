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
    use_local_model: bool = False  # when True, the LOCAL tier uses Ollama instead of the mock
    local_model_endpoint: str = "http://localhost:11434"  # Ollama default
    frontier_model: str = "claude-opus-4"
    cheap_model: str = "claude-haiku-4"
    local_model: str = "qwen2.5:7b"

    # Memory
    embed_model: str = "nomic-embed-text"  # Ollama embedding model (768-dim)
    vector_dim: int = 768
    enable_scribe: bool = True  # ambient learning: extract + store facts after each exchange

    # Surfaces
    discord_token: str | None = None
    active_window_seconds: int = 180  # after you address it, keep replying for this long

    # Infra (empty = use in-memory store; set to use self-hosted/managed Postgres)
    database_url: str | None = None
    redis_url: str | None = None

    # Self-state persistence (traits, skills, instincts, proposals, sessions).
    # A directory of JSON files — zero infra. Empty = in-memory (test default).
    state_dir: str = "~/.kaizen/state"

    # Behavior
    system_prompt: str = "You are Kaizen, a personal, always-improving assistant."
    talkativeness: float = 0.5


def load_settings() -> Settings:
    return Settings()
