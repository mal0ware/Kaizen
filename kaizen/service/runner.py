"""``python -m kaizen serve`` — run the headless core as a daemon.

Plain uvicorn, no TTY needed: suitable for nohup/systemd/a Hetzner box.
Import stays lazy so the base install never needs uvicorn.
"""
from __future__ import annotations

from kaizen.config import Settings, load_settings


def serve(settings: Settings | None = None) -> None:
    import uvicorn

    from kaizen.service.app import create_app

    settings = settings or load_settings()
    uvicorn.run(
        create_app(settings=settings),
        host=settings.service_host,
        port=settings.service_port,
        log_level="info",
    )
