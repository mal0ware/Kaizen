"""The headless core service — one agent, exposed over HTTP for every surface.

FastAPI/uvicorn are optional deps (``pip install "kaizen[service]"``); nothing
here is imported unless a caller reaches for the service explicitly, matching
the lazy-import pattern used by the provider and memory factories.
"""
