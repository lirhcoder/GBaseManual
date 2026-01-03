"""
Web editor module.

Provides FastAPI-based web interface for editing manuals.
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
