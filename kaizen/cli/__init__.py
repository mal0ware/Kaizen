"""Dev CLI surface — the runnable mock entry point (`python -m kaizen`).

Wires the core with a MockProvider + in-memory store so it runs with no infra
and no API keys. Graduates into surfaces/terminal/ (Rich + prompt_toolkit) later.
"""
