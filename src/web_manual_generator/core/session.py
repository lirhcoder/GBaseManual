"""
Browser session management using Playwright.

Handles browser lifecycle, video recording, and provides the foundation
for both recording and execution modes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Literal
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


BrowserType = Literal["chromium", "firefox", "webkit"]


class BrowserSession:
    """
    Manages a Playwright browser session with video recording support.

    Usage:
        async with BrowserSession(output_dir="./output") as session:
            page = await session.new_page()
            await page.goto("https://example.com")
    """

    def __init__(
        self,
        output_dir: str | Path = "./output",
        browser_type: BrowserType = "chromium",
        headless: bool = False,
        record_video: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        slow_mo: int = 100,  # Slow down for better recording
    ):
        self.output_dir = Path(output_dir)
        self.browser_type = browser_type
        self.headless = headless
        self.record_video = record_video
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.slow_mo = slow_mo

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir = self.output_dir / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)
        self.videos_dir = self.output_dir / "videos"
        self.videos_dir.mkdir(exist_ok=True)

    async def __aenter__(self) -> "BrowserSession":
        """Start the browser session."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the browser session."""
        await self.close()

    async def start(self) -> None:
        """Initialize and start the browser."""
        self._playwright = await async_playwright().start()

        # Get browser launcher
        if self.browser_type == "chromium":
            browser_launcher = self._playwright.chromium
        elif self.browser_type == "firefox":
            browser_launcher = self._playwright.firefox
        else:
            browser_launcher = self._playwright.webkit

        # Launch browser
        self._browser = await browser_launcher.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
        )

        # Create context with video recording
        context_options = {
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
        }

        if self.record_video:
            context_options["record_video_dir"] = str(self.videos_dir)
            context_options["record_video_size"] = {
                "width": self.viewport_width,
                "height": self.viewport_height,
            }

        self._context = await self._browser.new_context(**context_options)

    async def close(self) -> None:
        """Close all browser resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        """Create a new page in the current context."""
        if not self._context:
            raise RuntimeError("Browser session not started. Call start() first.")
        self._page = await self._context.new_page()
        return self._page

    @property
    def page(self) -> Optional[Page]:
        """Get the current page."""
        return self._page

    @property
    def context(self) -> Optional[BrowserContext]:
        """Get the current browser context."""
        return self._context

    async def take_screenshot(
        self,
        name: str,
        full_page: bool = False,
        element_selector: Optional[str] = None,
    ) -> Path:
        """
        Take a screenshot of the current page or specific element.

        Args:
            name: Screenshot filename (without extension)
            full_page: Capture full scrollable page
            element_selector: CSS selector for specific element

        Returns:
            Path to the saved screenshot
        """
        if not self._page:
            raise RuntimeError("No page available. Call new_page() first.")

        screenshot_path = self.screenshots_dir / f"{name}.png"

        if element_selector:
            element = await self._page.query_selector(element_selector)
            if element:
                await element.screenshot(path=str(screenshot_path))
            else:
                raise ValueError(f"Element not found: {element_selector}")
        else:
            await self._page.screenshot(path=str(screenshot_path), full_page=full_page)

        return screenshot_path

    async def get_video_path(self) -> Optional[Path]:
        """Get the path to the recorded video after closing the page."""
        if self._page and self.record_video:
            video = self._page.video
            if video:
                return Path(await video.path())
        return None

    async def wait_for_user_input(self, prompt: str) -> str:
        """
        Pause execution and wait for user input.
        Used in semi-automatic mode.

        Args:
            prompt: Message to display to the user

        Returns:
            User's input string
        """
        print(f"\n{'='*50}")
        print(f"  {prompt}")
        print(f"{'='*50}")

        # Run input in a thread to not block the event loop
        loop = asyncio.get_event_loop()
        user_input = await loop.run_in_executor(None, lambda: input("> "))
        return user_input.strip()

    async def confirm_action(self, action_description: str) -> bool:
        """
        Ask user to confirm an action before proceeding.

        Args:
            action_description: Description of the action to confirm

        Returns:
            True if user confirms, False otherwise
        """
        response = await self.wait_for_user_input(
            f"{action_description}\n[Y/n]"
        )
        return response.lower() in ("", "y", "yes")


@asynccontextmanager
async def create_session(**kwargs):
    """
    Convenience context manager for creating browser sessions.

    Usage:
        async with create_session(output_dir="./output") as session:
            page = await session.new_page()
            await page.goto("https://example.com")
    """
    session = BrowserSession(**kwargs)
    try:
        await session.start()
        yield session
    finally:
        await session.close()
