"""
Action logging for recording user interactions.

Records each action with metadata for manual generation.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


ActionType = Literal[
    "navigate",
    "click",
    "fill",
    "select",
    "check",
    "uncheck",
    "hover",
    "scroll",
    "keyboard",
    "wait",
    "screenshot",
    "custom",
]


class ActionStep(BaseModel):
    """Represents a single recorded action."""

    id: int = Field(..., description="Step number")
    action: ActionType = Field(..., description="Type of action performed")
    timestamp: datetime = Field(default_factory=datetime.now)

    # Action details
    selector: Optional[str] = Field(None, description="CSS selector for the element")
    value: Optional[str] = Field(None, description="Input value (for fill, select)")
    url: Optional[str] = Field(None, description="URL (for navigate)")
    key: Optional[str] = Field(None, description="Key pressed (for keyboard)")

    # Documentation
    description: str = Field("", description="Human-readable description")
    description_zh: str = Field("", description="Chinese description")
    description_ja: str = Field("", description="Japanese description")
    description_en: str = Field("", description="English description")

    # Captured artifacts
    screenshot: Optional[str] = Field(None, description="Screenshot filename")
    element_screenshot: Optional[str] = Field(None, description="Element screenshot filename")

    # Additional metadata
    page_title: Optional[str] = Field(None, description="Page title at time of action")
    page_url: Optional[str] = Field(None, description="Page URL at time of action")
    notes: Optional[str] = Field(None, description="Additional notes")

    def get_description(self, lang: str = "zh") -> str:
        """Get description in specified language."""
        lang_map = {
            "zh": self.description_zh or self.description,
            "ja": self.description_ja or self.description,
            "en": self.description_en or self.description,
        }
        return lang_map.get(lang, self.description)


class ActionLog(BaseModel):
    """Collection of action steps with metadata."""

    title: str = Field("Untitled Recording", description="Recording title")
    title_zh: str = Field("", description="Chinese title")
    title_ja: str = Field("", description="Japanese title")
    title_en: str = Field("", description="English title")

    description: str = Field("", description="Recording description")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    start_url: Optional[str] = Field(None, description="Starting URL")
    steps: List[ActionStep] = Field(default_factory=list)

    video_file: Optional[str] = Field(None, description="Video recording filename")

    # Prerequisites
    prerequisites: List[str] = Field(default_factory=list)
    prerequisites_zh: List[str] = Field(default_factory=list)
    prerequisites_ja: List[str] = Field(default_factory=list)
    prerequisites_en: List[str] = Field(default_factory=list)

    def add_step(
        self,
        action: ActionType,
        selector: Optional[str] = None,
        value: Optional[str] = None,
        url: Optional[str] = None,
        description: str = "",
        **kwargs,
    ) -> ActionStep:
        """Add a new action step."""
        step = ActionStep(
            id=len(self.steps) + 1,
            action=action,
            selector=selector,
            value=value,
            url=url,
            description=description,
            **kwargs,
        )
        self.steps.append(step)
        self.updated_at = datetime.now()
        return step

    def get_last_step(self) -> Optional[ActionStep]:
        """Get the most recent step."""
        return self.steps[-1] if self.steps else None

    def update_last_step(self, **kwargs) -> Optional[ActionStep]:
        """Update the most recent step with additional data."""
        if self.steps:
            for key, value in kwargs.items():
                if hasattr(self.steps[-1], key):
                    setattr(self.steps[-1], key, value)
            self.updated_at = datetime.now()
            return self.steps[-1]
        return None

    def get_title(self, lang: str = "zh") -> str:
        """Get title in specified language."""
        lang_map = {
            "zh": self.title_zh or self.title,
            "ja": self.title_ja or self.title,
            "en": self.title_en or self.title,
        }
        return lang_map.get(lang, self.title)

    def get_prerequisites(self, lang: str = "zh") -> List[str]:
        """Get prerequisites in specified language."""
        lang_map = {
            "zh": self.prerequisites_zh or self.prerequisites,
            "ja": self.prerequisites_ja or self.prerequisites,
            "en": self.prerequisites_en or self.prerequisites,
        }
        return lang_map.get(lang, self.prerequisites)

    def save(self, path: str | Path) -> None:
        """Save action log to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(mode="json"), f, ensure_ascii=False, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path) -> "ActionLog":
        """Load action log from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def to_script(self) -> str:
        """Generate a Python Playwright script from the recorded actions."""
        lines = [
            "from playwright.sync_api import sync_playwright",
            "",
            "def run():",
            "    with sync_playwright() as p:",
            "        browser = p.chromium.launch(headless=False)",
            "        page = browser.new_page()",
            "",
        ]

        for step in self.steps:
            if step.action == "navigate":
                lines.append(f'        page.goto("{step.url}")')
            elif step.action == "click":
                lines.append(f'        page.click("{step.selector}")')
            elif step.action == "fill":
                lines.append(f'        page.fill("{step.selector}", "{step.value}")')
            elif step.action == "select":
                lines.append(f'        page.select_option("{step.selector}", "{step.value}")')
            elif step.action == "check":
                lines.append(f'        page.check("{step.selector}")')
            elif step.action == "uncheck":
                lines.append(f'        page.uncheck("{step.selector}")')
            elif step.action == "hover":
                lines.append(f'        page.hover("{step.selector}")')
            elif step.action == "keyboard":
                lines.append(f'        page.keyboard.press("{step.key}")')
            elif step.action == "wait":
                lines.append(f'        page.wait_for_timeout({step.value})')

            if step.description:
                lines[-1] += f"  # {step.description}"

        lines.extend([
            "",
            "        browser.close()",
            "",
            'if __name__ == "__main__":',
            "    run()",
        ])

        return "\n".join(lines)
