"""
Action recorder for capturing user interactions.

Uses Playwright's CDP (Chrome DevTools Protocol) to intercept and record
user actions in the browser.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Callable, Awaitable, TYPE_CHECKING
from datetime import datetime

from rich.console import Console
from rich.panel import Panel

from ..capture.action_log import ActionLog, ActionStep
from ..capture.screenshot import ScreenshotManager
from ..capture.video import VideoChapterMarker
from ..i18n import get_text

if TYPE_CHECKING:
    from playwright.async_api import Page, BrowserContext

console = Console()


class ActionRecorder:
    """
    Records user interactions in a browser session.

    Captures clicks, inputs, navigation, and other actions,
    along with screenshots at each step.
    """

    def __init__(
        self,
        output_dir: str | Path,
        language: str = "zh",
        auto_screenshot: bool = True,
        highlight_elements: bool = True,
        show_cursor: bool = True,  # 新增：是否显示鼠标
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.language = language
        self.auto_screenshot = auto_screenshot
        self.highlight_elements = highlight_elements
        self.show_cursor = show_cursor  # 是否在截图中显示鼠标

        self.action_log = ActionLog()
        self.screenshot_manager = ScreenshotManager(self.output_dir / "screenshots")
        self.chapter_marker = VideoChapterMarker()

        self._page: Optional[Page] = None
        self._is_recording = False
        self._action_handlers: list[Callable[[ActionStep], Awaitable[None]]] = []
        self._stop_event: Optional[asyncio.Event] = None
        self._last_mouse_position: tuple[int, int] = (0, 0)

    async def start_recording(
        self,
        page: "Page",
        title: str = "",
        start_url: Optional[str] = None,
    ) -> None:
        """
        Start recording actions on a page.

        Args:
            page: Playwright page to record
            title: Title for the recording
            start_url: Initial URL to navigate to
        """
        self._page = page
        self._is_recording = True
        self._stop_event = asyncio.Event()
        self.chapter_marker.start()

        # Initialize action log
        self.action_log = ActionLog(
            title=title or get_text("untitled_recording", self.language),
            start_url=start_url,
        )

        # Navigate to start URL if provided
        if start_url:
            await page.goto(start_url)
            await self._record_action(
                action="navigate",
                url=start_url,
                description=get_text("navigate_to", self.language).format(url=start_url),
            )

        # Set up event listeners
        await self._setup_listeners(page)

        console.print(Panel(
            get_text("recording_started", self.language) + "\n\n" +
            "[yellow]" + self._get_stop_hint() + "[/yellow]",
            title=get_text("recorder", self.language),
            border_style="green",
        ))

    def _get_stop_hint(self) -> str:
        """Get the hint for stopping recording."""
        hints = {
            "zh": "按 F2 或点击页面右上角的停止按钮结束录制",
            "ja": "F2キーまたは右上の停止ボタンで録画を終了",
            "en": "Press F2 or click the Stop button to end recording",
        }
        return hints.get(self.language, hints["en"])

    async def stop_recording(self) -> ActionLog:
        """
        Stop recording and return the action log.

        Returns:
            The recorded ActionLog
        """
        self._is_recording = False
        if self._stop_event:
            self._stop_event.set()

        # Remove the control panel from the page
        if self._page:
            try:
                await self._page.evaluate("window.__wmg_cleanup && window.__wmg_cleanup()")
            except Exception:
                pass

        # Save the action log
        log_path = self.output_dir / "action_log.json"
        self.action_log.save(log_path)

        # Save chapters
        chapters_path = self.output_dir / "chapters.json"
        self.chapter_marker.save_chapters(chapters_path)

        console.print(Panel(
            get_text("recording_stopped", self.language).format(
                steps=len(self.action_log.steps)
            ),
            title=get_text("recorder", self.language),
            border_style="yellow",
        ))

        return self.action_log

    async def wait_for_stop(self) -> None:
        """Wait until recording is stopped (via UI or programmatically)."""
        if self._stop_event:
            await self._stop_event.wait()

    def request_stop(self) -> None:
        """Request to stop recording (can be called from any context)."""
        self._is_recording = False
        if self._stop_event:
            self._stop_event.set()

    async def _setup_listeners(self, page: "Page") -> None:
        """Set up event listeners on the page."""

        # Expose functions to the page for recording actions
        await page.expose_function("__wmg_record_click", self._on_click)
        await page.expose_function("__wmg_record_input", self._on_input)
        await page.expose_function("__wmg_record_mouse", self._on_mouse_move)
        await page.expose_function("__wmg_stop_recording", self._on_stop_request)

        # Inject recording script with control panel
        await page.add_init_script("""
            (() => {
                let lastMouseX = 0;
                let lastMouseY = 0;

                // Track mouse position
                document.addEventListener('mousemove', (e) => {
                    lastMouseX = e.clientX;
                    lastMouseY = e.clientY;
                    if (window.__wmg_record_mouse) {
                        window.__wmg_record_mouse(e.clientX, e.clientY);
                    }
                }, true);

                // Track clicks - use mousedown to capture BEFORE click happens
                // This allows capturing dropdown menus before they close
                document.addEventListener('mousedown', async (e) => {
                    // Ignore clicks on our control panel
                    if (e.target.closest && e.target.closest('#__wmg_control_panel')) {
                        return;
                    }

                    const target = e.target;
                    const selector = getSelector(target);
                    const text = target.innerText?.slice(0, 100) || '';
                    const tagName = target.tagName.toLowerCase();

                    // Pass mouse position for cursor display
                    if (window.__wmg_record_click) {
                        window.__wmg_record_click(selector, text, tagName, lastMouseX, lastMouseY);
                    }
                }, true);

                // Track input changes
                document.addEventListener('change', async (e) => {
                    const target = e.target;
                    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
                        const selector = getSelector(target);
                        const value = target.value;
                        const inputType = target.type || 'text';

                        if (window.__wmg_record_input) {
                            window.__wmg_record_input(selector, value, inputType);
                        }
                    }
                }, true);

                // F2 key to stop recording
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'F2') {
                        e.preventDefault();
                        if (window.__wmg_stop_recording) {
                            window.__wmg_stop_recording();
                        }
                    }
                }, true);

                // Create control panel
                createControlPanel();

                function createControlPanel() {
                    const panel = document.createElement('div');
                    panel.id = '__wmg_control_panel';
                    panel.innerHTML = `
                        <style>
                            #__wmg_control_panel {
                                position: fixed;
                                top: 10px;
                                right: 10px;
                                z-index: 999999;
                                background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                                padding: 8px 16px;
                                border-radius: 20px;
                                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                                cursor: pointer;
                                display: flex;
                                align-items: center;
                                gap: 8px;
                                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                                transition: transform 0.2s, box-shadow 0.2s;
                            }
                            #__wmg_control_panel:hover {
                                transform: scale(1.05);
                                box-shadow: 0 6px 16px rgba(0,0,0,0.4);
                            }
                            #__wmg_control_panel .dot {
                                width: 12px;
                                height: 12px;
                                background: white;
                                border-radius: 50%;
                                animation: pulse 1.5s infinite;
                            }
                            #__wmg_control_panel .text {
                                color: white;
                                font-size: 14px;
                                font-weight: 600;
                            }
                            @keyframes pulse {
                                0%, 100% { opacity: 1; }
                                50% { opacity: 0.5; }
                            }
                        </style>
                        <div class="dot"></div>
                        <span class="text">Stop (F2)</span>
                    `;
                    panel.addEventListener('click', () => {
                        if (window.__wmg_stop_recording) {
                            window.__wmg_stop_recording();
                        }
                    });
                    document.body.appendChild(panel);
                }

                // Cleanup function
                window.__wmg_cleanup = function() {
                    const panel = document.getElementById('__wmg_control_panel');
                    if (panel) {
                        panel.remove();
                    }
                };

                // Helper function to generate CSS selector
                function getSelector(element) {
                    if (element.id && !element.id.startsWith('__wmg')) {
                        return '#' + element.id;
                    }

                    if (element.name) {
                        return `[name="${element.name}"]`;
                    }

                    const path = [];
                    while (element && element.nodeType === Node.ELEMENT_NODE) {
                        let selector = element.tagName.toLowerCase();

                        if (element.className && typeof element.className === 'string') {
                            const classes = element.className.trim().split(/\\s+/).filter(c => c && !c.startsWith('__wmg'));
                            if (classes.length > 0) {
                                selector += '.' + classes.slice(0, 2).join('.');
                            }
                        }

                        const siblings = element.parentNode ?
                            Array.from(element.parentNode.children).filter(e => e.tagName === element.tagName) : [];

                        if (siblings.length > 1) {
                            const index = siblings.indexOf(element) + 1;
                            selector += `:nth-of-type(${index})`;
                        }

                        path.unshift(selector);

                        if (path.length >= 3) break;
                        element = element.parentNode;
                    }

                    return path.join(' > ');
                }
            })();
        """)

    async def _on_mouse_move(self, x: int, y: int) -> None:
        """Track mouse position for cursor display."""
        self._last_mouse_position = (int(x), int(y))

    async def _on_stop_request(self) -> None:
        """Handle stop recording request from the page."""
        console.print("\n[yellow]Stop recording requested...[/yellow]")
        self.request_stop()

    async def _on_click(self, selector: str, text: str, tag_name: str, mouse_x: int, mouse_y: int) -> None:
        """Handle recorded click action."""
        if not self._is_recording:
            return

        # Update mouse position
        self._last_mouse_position = (int(mouse_x), int(mouse_y))

        description = get_text("click_element", self.language).format(
            element=text[:50] if text else tag_name
        )

        await self._record_action(
            action="click",
            selector=selector,
            description=description,
        )

    async def _on_input(self, selector: str, value: str, input_type: str) -> None:
        """Handle recorded input action."""
        if not self._is_recording:
            return

        # Mask password inputs
        display_value = "***" if input_type == "password" else value[:50]

        description = get_text("input_value", self.language).format(value=display_value)

        await self._record_action(
            action="fill",
            selector=selector,
            value=value if input_type != "password" else "",
            description=description,
        )

    async def _record_action(
        self,
        action: str,
        selector: Optional[str] = None,
        value: Optional[str] = None,
        url: Optional[str] = None,
        description: str = "",
        **kwargs,
    ) -> ActionStep:
        """Record an action with optional screenshot."""
        if not self._page:
            raise RuntimeError("No page available for recording")

        # Get page info
        page_title = await self._page.title()
        page_url = self._page.url

        # Take screenshot if enabled
        screenshot_name = None
        if self.auto_screenshot:
            step_num = len(self.action_log.steps) + 1
            screenshot_name = f"step_{step_num:03d}"

            # Capture screenshot with optional cursor and highlight
            await self._capture_screenshot_with_cursor(
                screenshot_name,
                selector if self.highlight_elements else None
            )
            screenshot_name += ".png"

        # Add step to log
        step = self.action_log.add_step(
            action=action,
            selector=selector,
            value=value,
            url=url,
            description=description,
            screenshot=screenshot_name,
            page_title=page_title,
            page_url=page_url,
            **kwargs,
        )

        # Mark chapter
        self.chapter_marker.mark_chapter(description)

        # Notify handlers
        for handler in self._action_handlers:
            await handler(step)

        # Display action
        console.print(f"  [{step.id}] {step.action}: {description}")

        return step

    async def _capture_screenshot_with_cursor(
        self,
        name: str,
        highlight_selector: Optional[str] = None
    ) -> Path:
        """Capture screenshot with optional cursor and element highlight."""
        if not self._page:
            raise RuntimeError("No page available")

        # Add cursor indicator and highlight if needed
        cursor_style = ""
        if self.show_cursor:
            mx, my = self._last_mouse_position
            cursor_style = f"""
                const cursor = document.createElement('div');
                cursor.id = '__wmg_cursor';
                cursor.style.cssText = `
                    position: fixed;
                    left: {mx - 12}px;
                    top: {my - 12}px;
                    width: 24px;
                    height: 24px;
                    border: 3px solid #ef4444;
                    border-radius: 50%;
                    background: rgba(239, 68, 68, 0.3);
                    pointer-events: none;
                    z-index: 999998;
                    box-shadow: 0 0 10px rgba(239, 68, 68, 0.5);
                `;
                document.body.appendChild(cursor);
            """

        highlight_style = ""
        if highlight_selector:
            highlight_style = f"""
                const el = document.querySelector('{highlight_selector.replace("'", "\\'")}');
                if (el) {{
                    el.style.setProperty('outline', '3px solid #2563eb', 'important');
                    el.style.setProperty('outline-offset', '2px', 'important');
                    el.dataset.wmgHighlight = 'true';
                }}
            """

        # Inject cursor and highlight
        if cursor_style or highlight_style:
            await self._page.evaluate(f"""
                (() => {{
                    {cursor_style}
                    {highlight_style}
                }})();
            """)

        # Take screenshot
        filepath = self.screenshot_manager.output_dir / f"{name}.png"
        await self._page.screenshot(path=str(filepath))

        # Remove cursor and highlight
        cleanup_script = """
            (() => {
                const cursor = document.getElementById('__wmg_cursor');
                if (cursor) cursor.remove();

                document.querySelectorAll('[data-wmg-highlight]').forEach(el => {
                    el.style.removeProperty('outline');
                    el.style.removeProperty('outline-offset');
                    delete el.dataset.wmgHighlight;
                });
            })();
        """
        await self._page.evaluate(cleanup_script)

        return filepath

    def add_action_handler(
        self,
        handler: Callable[[ActionStep], Awaitable[None]],
    ) -> None:
        """Add a callback for recorded actions."""
        self._action_handlers.append(handler)

    async def add_manual_step(
        self,
        description: str,
        action: str = "custom",
        take_screenshot: bool = True,
    ) -> ActionStep:
        """
        Manually add a step to the recording.

        Useful for adding explanatory steps or custom actions.

        Args:
            description: Step description
            action: Action type
            take_screenshot: Whether to take a screenshot

        Returns:
            The created ActionStep
        """
        screenshot_name = None
        if take_screenshot and self._page:
            step_num = len(self.action_log.steps) + 1
            screenshot_name = f"step_{step_num:03d}"
            await self._capture_screenshot_with_cursor(screenshot_name)
            screenshot_name += ".png"

        step = self.action_log.add_step(
            action=action,
            description=description,
            screenshot=screenshot_name,
        )

        self.chapter_marker.mark_chapter(description)

        return step

    async def wait_for_user_action(self, prompt: str) -> str:
        """
        Pause and wait for user to perform an action or provide input.

        Args:
            prompt: Message to display

        Returns:
            User's input
        """
        console.print(Panel(
            prompt,
            title=get_text("waiting_for_input", self.language),
            border_style="cyan",
        ))

        loop = asyncio.get_event_loop()
        user_input = await loop.run_in_executor(
            None,
            lambda: input(f"{get_text('press_enter', self.language)} > ")
        )

        return user_input.strip()

    async def annotate_last_step(
        self,
        description: Optional[str] = None,
        description_zh: Optional[str] = None,
        description_ja: Optional[str] = None,
        description_en: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[ActionStep]:
        """
        Add annotations to the last recorded step.

        Args:
            description: Main description
            description_zh: Chinese description
            description_ja: Japanese description
            description_en: English description
            notes: Additional notes

        Returns:
            The updated step, or None if no steps exist
        """
        return self.action_log.update_last_step(
            description=description,
            description_zh=description_zh,
            description_ja=description_ja,
            description_en=description_en,
            notes=notes,
        )

    def get_action_log(self) -> ActionLog:
        """Get the current action log."""
        return self.action_log

    def generate_script(self) -> str:
        """Generate a Playwright script from the recorded actions."""
        return self.action_log.to_script()

    def save_script(self, filename: str = "script.py") -> Path:
        """Save the generated script to a file."""
        script = self.generate_script()
        script_path = self.output_dir / filename
        script_path.write_text(script, encoding="utf-8")
        return script_path
