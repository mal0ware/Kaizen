"""Kaizen — a personal, always-on, self-improving AI agent.

This package is the headless core and its subsystems. Surfaces (Discord,
terminal) are thin clients of the core. See docs/architecture.md and the ADRs.

The skeleton runs with no external infrastructure: a MockProvider and an
in-memory store stand in for cloud models and Postgres/pgvector. Real adapters
drop in behind the same interfaces when infra exists.
"""

__version__ = "0.0.1"
