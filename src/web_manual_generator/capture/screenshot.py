"""
Screenshot management for capturing page states.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


class ScreenshotManager:
    """
    Manages screenshot capture with automatic naming and organization.
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def _get_next_filename(self, prefix: str = "step") -> str:
        """Generate the next screenshot filename."""
        self._counter += 1
        return f"{prefix}_{self._counter:03d}.png"

    async def capture_page(
        self,
        page: "Page",
        name: Optional[str] = None,
        full_page: bool = False,
    ) -> Path:
        """
        Capture a screenshot of the entire page.

        Args:
            page: Playwright page instance
            name: Custom filename (without extension)
            full_page: Capture full scrollable page

        Returns:
            Path to the saved screenshot
        """
        filename = f"{name}.png" if name else self._get_next_filename()
        filepath = self.output_dir / filename

        await page.screenshot(path=str(filepath), full_page=full_page)
        return filepath

    async def capture_element(
        self,
        page: "Page",
        selector: str,
        name: Optional[str] = None,
        padding: int = 10,
    ) -> Optional[Path]:
        """
        Capture a screenshot of a specific element.

        Args:
            page: Playwright page instance
            selector: CSS selector for the element
            name: Custom filename (without extension)
            padding: Padding around the element (not directly supported, for future use)

        Returns:
            Path to the saved screenshot, or None if element not found
        """
        element = await page.query_selector(selector)
        if not element:
            return None

        filename = f"{name}.png" if name else self._get_next_filename("element")
        filepath = self.output_dir / filename

        await element.screenshot(path=str(filepath))
        return filepath

    async def capture_with_highlight(
        self,
        page: "Page",
        selector: str,
        name: Optional[str] = None,
        highlight_color: str = "rgba(255, 0, 0, 0.3)",
        border_color: str = "red",
        border_width: int = 3,
    ) -> Path:
        """
        Capture a screenshot with an element highlighted.

        Args:
            page: Playwright page instance
            selector: CSS selector for the element to highlight
            name: Custom filename (without extension)
            highlight_color: Background color for highlight
            border_color: Border color for highlight
            border_width: Border width in pixels

        Returns:
            Path to the saved screenshot
        """
        # Add highlight style
        await page.evaluate(
            """
            ([selector, bgColor, borderColor, borderWidth]) => {
                const element = document.querySelector(selector);
                if (element) {
                    element.style.setProperty('outline', `${borderWidth}px solid ${borderColor}`, 'important');
                    element.style.setProperty('outline-offset', '2px', 'important');
                    element.dataset.wmgHighlight = 'true';
                }
            }
            """,
            [selector, highlight_color, border_color, border_width],
        )

        # Capture screenshot
        filename = f"{name}.png" if name else self._get_next_filename("highlight")
        filepath = self.output_dir / filename
        await page.screenshot(path=str(filepath))

        # Remove highlight style
        await page.evaluate(
            """
            (selector) => {
                const element = document.querySelector(selector);
                if (element && element.dataset.wmgHighlight) {
                    element.style.removeProperty('outline');
                    element.style.removeProperty('outline-offset');
                    delete element.dataset.wmgHighlight;
                }
            }
            """,
            selector,
        )

        return filepath

    async def capture_before_after(
        self,
        page: "Page",
        action_callback,
        name_prefix: Optional[str] = None,
    ) -> tuple[Path, Path]:
        """
        Capture screenshots before and after an action.

        Args:
            page: Playwright page instance
            action_callback: Async function to execute between captures
            name_prefix: Prefix for filenames

        Returns:
            Tuple of (before_path, after_path)
        """
        prefix = name_prefix or f"step_{self._counter + 1:03d}"

        before_path = await self.capture_page(page, name=f"{prefix}_before")
        await action_callback()
        after_path = await self.capture_page(page, name=f"{prefix}_after")

        self._counter += 1
        return before_path, after_path

    def reset_counter(self) -> None:
        """Reset the filename counter."""
        self._counter = 0

    @property
    def screenshot_count(self) -> int:
        """Get the number of screenshots taken."""
        return self._counter
