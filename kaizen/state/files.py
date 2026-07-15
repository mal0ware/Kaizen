"""File-backed state store — the zero-infra runtime default.

One JSON file per collection under a state directory (default
``~/.kaizen/state``). Every write goes to a temp file in the same directory
and lands via :func:`os.replace`, so a crash mid-write never corrupts the
previous good state. No database, no daemon dependencies — a directory is
the whole persistence story.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from kaizen.core.models import Session
from kaizen.curator.instinct import Instinct
from kaizen.curator.proposals import Proposal
from kaizen.skills.base import Skill
from kaizen.state import serde


class FileStateStore:
    name = "file-state"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser()

    # --- file mechanics ------------------------------------------------------

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def _load(self, key: str) -> list[Any]:
        path = self._path(key)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []

    def _save(self, key: str, data: list[Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path(key))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # --- collections ----------------------------------------------------------

    def load_traits(self) -> list[str]:
        return [str(t) for t in self._load("traits")]

    def save_traits(self, traits: list[str]) -> None:
        self._save("traits", list(traits))

    def load_skills(self) -> list[Skill]:
        return [serde.skill_from_dict(d) for d in self._load("skills")]

    def save_skills(self, skills: list[Skill]) -> None:
        self._save("skills", [serde.skill_to_dict(s) for s in skills])

    def load_instincts(self) -> list[Instinct]:
        return [serde.instinct_from_dict(d) for d in self._load("instincts")]

    def save_instincts(self, instincts: list[Instinct]) -> None:
        self._save("instincts", [serde.instinct_to_dict(i) for i in instincts])

    def load_pending(self) -> list[Proposal]:
        return [serde.proposal_from_dict(d) for d in self._load("proposals")]

    def save_pending(self, proposals: list[Proposal]) -> None:
        self._save("proposals", [serde.proposal_to_dict(p) for p in proposals])

    def load_sessions(self) -> list[Session]:
        return [serde.session_from_dict(d) for d in self._load("sessions")]

    def save_sessions(self, sessions: list[Session]) -> None:
        self._save("sessions", [serde.session_to_dict(s) for s in sessions])
