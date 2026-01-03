"""
Script executor for replaying recorded actions.

Executes action scripts with support for semi-automatic mode,
video recording, and screenshot capture.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Callable, Awaitable, Any, TYPE_CHECKING
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..capture.action_log import ActionLog, ActionStep
from ..capture.screenshot import ScreenshotManager
from ..capture.video import VideoChapterMarker
from ..i18n import get_text

if TYPE_CHECKING:
    from playwright.async_api import Page

console = Console()


class ExecutionError(Exception):
    """Error during script execution."""

    def __init__(self, step: ActionStep, message: str):
        self.step = step
        super().__init__(f"Step {step.id} ({step.action}): {message}")


class ScriptExecutor:
    """
    Executes recorded action scripts.

    Supports:
    - Automatic execution of all steps
    - Semi-automatic mode with user confirmations
    - Step-by-step execution
    - Screenshot capture at each step
    """

    def __init__(
        self,
        output_dir: str | Path,
        language: str = "zh",
        semi_automatic: bool = False,
        step_delay: float = 0.5,
        capture_screenshots: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.language = language
        self.semi_automatic = semi_automatic
        self.step_delay = step_delay
        self.capture_screenshots = capture_screenshots

        self.screenshot_manager = ScreenshotManager(self.output_dir / "screenshots")
        self.chapter_marker = VideoChapterMarker()

        self._page: Optional[Page] = None
        self._current_step: int = 0
        self._execution_log: list[dict] = []
        self._input_handler: Optional[Callable[[str], Awaitable[str]]] = None

    def set_input_handler(
        self,
        handler: Callable[[str], Awaitable[str]],
    ) -> None:
        """
        Set a custom input handler for semi-automatic mode.

        Args:
            handler: Async function that takes a prompt and returns user input
        """
        self._input_handler = handler

    async def execute(
        self,
        page: "Page",
        action_log: ActionLog | str | Path,
        start_step: int = 1,
        end_step: Optional[int] = None,
    ) -> list[dict]:
        """
        Execute an action script.

        Args:
            page: Playwright page to execute on
            action_log: ActionLog object or path to JSON file
            start_step: First step to execute (1-indexed)
            end_step: Last step to execute (inclusive, None for all)

        Returns:
            List of execution results for each step
        """
        self._page = page
        self._execution_log = []
        self.chapter_marker.start()

        # Load action log if path provided
        if isinstance(action_log, (str, Path)):
            action_log = ActionLog.load(action_log)

        steps = action_log.steps
        if end_step:
            steps = steps[:end_step]
        steps = steps[start_step - 1:]

        console.print(Panel(
            get_text("execution_started", self.language).format(
                count=len(steps)
            ),
            title=get_text("executor", self.language),
            border_style="green",
        ))

        # Navigate to start URL if available
        if action_log.start_url and start_step == 1:
            await page.goto(action_log.start_url)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                get_text("executing", self.language),
                total=len(steps),
            )

            for step in steps:
                self._current_step = step.id
                progress.update(
                    task,
                    description=f"[{step.id}] {step.description[:40]}...",
                )

                result = await self._execute_step(step)
                self._execution_log.append(result)

                if not result["success"]:
                    if self.semi_automatic:
                        # Ask user how to proceed
                        response = await self._get_user_input(
                            get_text("step_failed_prompt", self.language).format(
                                error=result["error"]
                            )
                        )
                        if response.lower() in ("skip", "s"):
                            continue
                        elif response.lower() in ("retry", "r"):
                            result = await self._execute_step(step)
                            self._execution_log[-1] = result
                        elif response.lower() in ("quit", "q"):
                            break
                    else:
                        raise ExecutionError(step, result["error"])

                progress.advance(task)
                await asyncio.sleep(self.step_delay)

        # Save execution log
        self._save_execution_log()

        console.print(Panel(
            get_text("execution_completed", self.language).format(
                success=sum(1 for r in self._execution_log if r["success"]),
                total=len(self._execution_log),
            ),
            title=get_text("executor", self.language),
            border_style="green",
        ))

        return self._execution_log

    async def _execute_step(self, step: ActionStep) -> dict:
        """Execute a single action step."""
        result = {
            "step_id": step.id,
            "action": step.action,
            "success": False,
            "error": None,
            "screenshot": None,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            if not self._page:
                raise RuntimeError("No page available")

            # Semi-automatic mode: ask for confirmation
            if self.semi_automatic:
                confirm = await self._get_user_input(
                    get_text("confirm_step", self.language).format(
                        action=step.action,
                        description=step.description,
                    ) + " [Y/n/s(kip)]"
                )
                if confirm.lower() == "s":
                    result["success"] = True
                    result["error"] = "Skipped by user"
                    return result
                elif confirm.lower() == "n":
                    result["error"] = "Cancelled by user"
                    return result

            # Execute the action
            await self._perform_action(step)

            # Capture screenshot
            if self.capture_screenshots:
                screenshot_name = f"exec_{step.id:03d}"
                await self.screenshot_manager.capture_page(
                    self._page, name=screenshot_name
                )
                result["screenshot"] = f"{screenshot_name}.png"

            # Mark chapter
            self.chapter_marker.mark_chapter(step.description)

            result["success"] = True
            console.print(f"  [green]\u2713[/green] [{step.id}] {step.description[:50]}")

        except Exception as e:
            result["error"] = str(e)
            console.print(f"  [red]\u2717[/red] [{step.id}] {step.description[:50]}: {e}")

        return result

    async def _perform_action(self, step: ActionStep) -> None:
        """Perform the actual browser action."""
        if not self._page:
            raise RuntimeError("No page available")

        page = self._page

        if step.action == "navigate":
            await page.goto(step.url)

        elif step.action == "click":
            await page.click(step.selector, timeout=10000)

        elif step.action == "fill":
            # Handle input that needs user input
            value = step.value
            if not value and self.semi_automatic:
                value = await self._get_user_input(
                    get_text("enter_value", self.language).format(
                        selector=step.selector
                    )
                )
            if value:
                await page.fill(step.selector, value, timeout=10000)

        elif step.action == "select":
            await page.select_option(step.selector, step.value, timeout=10000)

        elif step.action == "check":
            await page.check(step.selector, timeout=10000)

        elif step.action == "uncheck":
            await page.uncheck(step.selector, timeout=10000)

        elif step.action == "hover":
            await page.hover(step.selector, timeout=10000)

        elif step.action == "keyboard":
            await page.keyboard.press(step.key)

        elif step.action == "wait":
            wait_time = int(step.value) if step.value else 1000
            await page.wait_for_timeout(wait_time)

        elif step.action == "scroll":
            await page.evaluate("window.scrollBy(0, 300)")

        elif step.action == "screenshot":
            # Just capture, no action needed
            pass

        elif step.action == "custom":
            # Custom actions may need special handling
            if self.semi_automatic:
                await self._get_user_input(
                    get_text("perform_custom_action", self.language).format(
                        description=step.description
                    )
                )

    async def _get_user_input(self, prompt: str) -> str:
        """Get input from user, using custom handler if set."""
        if self._input_handler:
            return await self._input_handler(prompt)

        console.print(Panel(prompt, border_style="cyan"))
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input("> "))

    def _save_execution_log(self) -> None:
        """Save the execution log to a file."""
        import json

        log_path = self.output_dir / "execution_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self._execution_log, f, ensure_ascii=False, indent=2)

        # Save chapters
        chapters_path = self.output_dir / "execution_chapters.json"
        self.chapter_marker.save_chapters(chapters_path)

    async def execute_single_step(
        self,
        page: "Page",
        step: ActionStep,
    ) -> dict:
        """
        Execute a single step independently.

        Args:
            page: Playwright page
            step: ActionStep to execute

        Returns:
            Execution result dictionary
        """
        self._page = page
        return await self._execute_step(step)

    def get_execution_log(self) -> list[dict]:
        """Get the execution log."""
        return self._execution_log.copy()


async def run_script(
    script_path: str | Path,
    output_dir: str | Path = "./output",
    headless: bool = False,
    semi_automatic: bool = False,
    language: str = "zh",
) -> list[dict]:
    """
    Convenience function to run a script file.

    Args:
        script_path: Path to the action log JSON file
        output_dir: Directory for output files
        headless: Run browser in headless mode
        semi_automatic: Enable semi-automatic mode
        language: Language for messages

    Returns:
        Execution log
    """
    from .session import BrowserSession

    async with BrowserSession(
        output_dir=output_dir,
        headless=headless,
        record_video=True,
    ) as session:
        page = await session.new_page()

        executor = ScriptExecutor(
            output_dir=output_dir,
            language=language,
            semi_automatic=semi_automatic,
        )

        return await executor.execute(page, script_path)
