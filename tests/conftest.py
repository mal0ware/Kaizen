"""Test-suite isolation.

``Settings`` (pydantic-settings) reads ``KAIZEN_*`` environment variables and a
``.env`` file. The integration tests call ``build_agent()`` with no explicit
settings, so without isolation they pick up whatever ``.env`` / env the operator
has locally — e.g. ``KAIZEN_USE_LOCAL_MODEL=true`` swaps the mock LOCAL provider
for a real Ollama client, and the background scribe then tries to hit a network
endpoint that does not exist in CI. That made the suite pass in clean CI but fail
on a configured developer box.

This autouse fixture strips every ``KAIZEN_*`` variable and points the settings
loader at a non-existent env file, so every test runs against the documented
zero-config defaults (mock provider, in-memory store) regardless of the host.
Tests that want non-default behavior pass an explicit ``Settings(...)``.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

import kaizen.config as config


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(__import__("os").environ):
        if key.startswith("KAIZEN_"):
            monkeypatch.delenv(key, raising=False)
    # Disable .env discovery: an absolute path that cannot exist on any host.
    monkeypatch.setattr(
        config.Settings,
        "model_config",
        {**config.Settings.model_config, "env_file": None},
    )
    yield
