"""Build the state store from settings.

If ``KAIZEN_STATE_DIR`` is set (default ``~/.kaizen/state``), use the
file-backed store so learned traits, skills, instincts, pending proposals,
and session snapshots survive restarts. An empty value opts out — everything
stays in-process (the test default, forced in ``tests/conftest.py``).
"""
from __future__ import annotations

from kaizen.config import Settings
from kaizen.state.base import StateStore
from kaizen.state.files import FileStateStore
from kaizen.state.inmemory import InMemoryStateStore


def build_state(settings: Settings) -> StateStore:
    if settings.state_dir:
        return FileStateStore(settings.state_dir)
    return InMemoryStateStore()
