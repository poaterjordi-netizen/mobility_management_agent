"""FastAPI surface for the mobility agent."""

from typing import Any


def create_app(*args: Any, **kwargs: Any) -> Any:
    """Import the application factory lazily to keep settings usable by integrations."""

    from mobility_agent.api.app import create_app as _create_app

    return _create_app(*args, **kwargs)


__all__ = ["create_app"]
