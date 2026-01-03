"""
Web Manual Generator - Browser automation with automatic documentation generation.

Supports:
- Recording user interactions
- AI-driven automated execution
- Semi-automatic mode with user prompts
- Video recording
- Manual generation (HTML/PDF) with screenshots
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .core.session import BrowserSession
from .core.recorder import ActionRecorder
from .core.executor import ScriptExecutor
from .manual.generator import ManualGenerator

__all__ = [
    "BrowserSession",
    "ActionRecorder",
    "ScriptExecutor",
    "ManualGenerator",
]
