"""Shared test setup.

Force the in-memory state store for every test: the runtime default is the
file-backed store under ``~/.kaizen/state``, and tests must never touch the
operator's real state directory. Tests that exercise the file store pass an
explicit ``tmp_path``-based Settings instead.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _in_memory_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIZEN_STATE_DIR", "")
