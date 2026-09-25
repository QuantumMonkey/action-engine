"""HTTP surface for action-engine (chapter B). Importing this package gives you the ASGI app."""

from .service import app  # noqa: F401

__all__ = ["app"]
