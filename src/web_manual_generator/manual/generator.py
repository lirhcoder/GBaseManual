"""
Manual generator for creating HTML and PDF documentation.

Generates user-friendly operation manuals from recorded action logs.
"""

from __future__ import annotations

import base64
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..capture.action_log import ActionLog
from ..i18n import get_text, get_action_name


class ManualGenerator:
    """
    Generates operation manuals from action logs.

    Supports:
    - HTML output with embedded or linked screenshots
    - PDF output (requires WeasyPrint)
    - Multi-language support (Chinese, Japanese, English)
    """

    def __init__(
        self,
        output_dir: str | Path,
        language: str = "zh",
        embed_images: bool = False,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.language = language
        self.embed_images = embed_images

        # Set up Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate_html(
        self,
        action_log: ActionLog | str | Path,
        output_name: str = "manual",
        screenshots_dir: Optional[str | Path] = None,
    ) -> Path:
        """
        Generate an HTML manual from an action log.

        Args:
            action_log: ActionLog object or path to JSON file
            output_name: Output filename (without extension)
            screenshots_dir: Directory containing screenshots

        Returns:
            Path to the generated HTML file
        """
        # Load action log if path provided
        if isinstance(action_log, (str, Path)):
            action_log = ActionLog.load(action_log)

        # Determine screenshots directory
        if screenshots_dir is None:
            screenshots_dir = self.output_dir / "screenshots"
        else:
            screenshots_dir = Path(screenshots_dir)

        # Prepare template data
        template_data = self._prepare_template_data(action_log, screenshots_dir)

        # Render template
        template = self.env.get_template("manual.html")
        html_content = template.render(**template_data)

        # Write output
        output_path = self.output_dir / f"{output_name}.html"
        output_path.write_text(html_content, encoding="utf-8")

        # Copy screenshots if not embedding
        if not self.embed_images and screenshots_dir.exists():
            output_screenshots = self.output_dir / "screenshots"
            if output_screenshots != screenshots_dir:
                if output_screenshots.exists():
                    shutil.rmtree(output_screenshots)
                shutil.copytree(screenshots_dir, output_screenshots)

        return output_path

    def generate_pdf(
        self,
        action_log: ActionLog | str | Path,
        output_name: str = "manual",
        screenshots_dir: Optional[str | Path] = None,
    ) -> Path:
        """
        Generate a PDF manual from an action log.

        Uses Playwright for PDF generation (works on all platforms).
        Falls back to WeasyPrint if Playwright is not available.

        Args:
            action_log: ActionLog object or path to JSON file
            output_name: Output filename (without extension)
            screenshots_dir: Directory containing screenshots

        Returns:
            Path to the generated PDF file
        """
        # Generate HTML first (with embedded images for PDF)
        original_embed = self.embed_images
        self.embed_images = True

        html_path = self.generate_html(
            action_log,
            output_name=f"{output_name}_temp",
            screenshots_dir=screenshots_dir,
        )

        self.embed_images = original_embed

        output_path = self.output_dir / f"{output_name}.pdf"

        # Try Playwright first (works on all platforms)
        try:
            self._generate_pdf_playwright(html_path, output_path)
            html_path.unlink()
            return output_path
        except Exception as playwright_error:
            # Fall back to WeasyPrint
            try:
                self._generate_pdf_weasyprint(html_path, output_path)
                html_path.unlink()
                return output_path
            except Exception as weasyprint_error:
                html_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"PDF generation failed.\n\n"
                    f"Playwright error: {playwright_error}\n"
                    f"WeasyPrint error: {weasyprint_error}\n\n"
                    f"Alternative: Export HTML and use browser's 'Print to PDF' feature."
                )

    def _generate_pdf_playwright(self, html_path: Path, output_path: Path) -> None:
        """Generate PDF using Playwright."""
        import asyncio

        async def _generate():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.goto(f"file://{html_path.absolute()}")
                await page.pdf(
                    path=str(output_path),
                    format="A4",
                    print_background=True,
                    margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"}
                )
                await browser.close()

        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, need to run in a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _generate())
                future.result()
        except RuntimeError:
            # No running loop, can use asyncio.run directly
            asyncio.run(_generate())

    def _generate_pdf_weasyprint(self, html_path: Path, output_path: Path) -> None:
        """Generate PDF using WeasyPrint."""
        from weasyprint import HTML
        HTML(filename=str(html_path)).write_pdf(str(output_path))

    def _prepare_template_data(
        self,
        action_log: ActionLog,
        screenshots_dir: Path,
    ) -> Dict[str, Any]:
        """Prepare data for template rendering."""
        lang = self.language

        # Prepare steps data
        steps = []
        for step in action_log.steps:
            step_data = {
                "id": step.id,
                "action": step.action,
                "action_name": get_action_name(step.action, lang),
                "description": step.get_description(lang),
                "selector": step.selector,
                "value": step.value,
                "notes": step.notes,
                "details": self._generate_step_details(step, lang),
            }

            # Handle screenshot
            if step.screenshot:
                screenshot_path = screenshots_dir / step.screenshot
                if screenshot_path.exists():
                    if self.embed_images:
                        step_data["screenshot"] = self._embed_image(screenshot_path)
                    else:
                        step_data["screenshot"] = f"screenshots/{step.screenshot}"

            steps.append(step_data)

        # Prepare TOC items
        toc_items = [
            {"id": s["id"], "title": s["description"][:50]}
            for s in steps
        ]

        # Check for video
        video_file = None
        if action_log.video_file:
            video_path = self.output_dir / action_log.video_file
            if video_path.exists():
                video_file = action_log.video_file

        return {
            "lang": lang,
            "title": action_log.get_title(lang),
            "description": action_log.description,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "prerequisites": action_log.get_prerequisites(lang),
            "steps": steps,
            "toc_items": toc_items,
            "video_file": video_file,
            # Labels
            "toc_label": get_text("table_of_contents", lang),
            "prerequisites_label": get_text("prerequisites", lang),
            "steps_label": get_text("step", lang),
            "step_label": get_text("step", lang),
            "notes_label": get_text("notes", lang),
            "video_label": get_text("video_tutorial", lang),
            "watch_video_label": self._get_watch_video_label(lang),
            "generated_label": get_text("generated_at", lang),
            "screenshot_label": self._get_screenshot_label(lang),
            "footer_text": self._get_footer_text(lang),
        }

    def _generate_step_details(self, step, lang: str) -> str:
        """Generate detailed description for a step."""
        details = []

        if step.action == "navigate" and step.url:
            details.append(f"URL: {step.url}")
        elif step.action == "click" and step.selector:
            label = {"zh": "\u5143\u7d20", "ja": "\u8981\u7d20", "en": "Element"}.get(lang, "Element")
            details.append(f"{label}: {step.selector}")
        elif step.action == "fill" and step.selector:
            label = {"zh": "\u8f93\u5165\u6846", "ja": "\u5165\u529b\u6b04", "en": "Input field"}.get(lang, "Input field")
            details.append(f"{label}: {step.selector}")
            if step.value:
                value_label = {"zh": "\u503c", "ja": "\u5024", "en": "Value"}.get(lang, "Value")
                # Mask potential sensitive values
                display_value = step.value if len(step.value) < 50 else step.value[:47] + "..."
                details.append(f"{value_label}: {display_value}")

        return " | ".join(details) if details else ""

    def _embed_image(self, image_path: Path) -> str:
        """Convert image to base64 data URI."""
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        suffix = image_path.suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")
        return f"data:{mime_type};base64,{data}"

    def _get_watch_video_label(self, lang: str) -> str:
        """Get 'Watch Video' label."""
        return {
            "zh": "\u89c2\u770b\u89c6\u9891\u6559\u7a0b",
            "ja": "\u30d3\u30c7\u30aa\u3092\u898b\u308b",
            "en": "Watch Video Tutorial",
        }.get(lang, "Watch Video")

    def _get_screenshot_label(self, lang: str) -> str:
        """Get 'Screenshot' label."""
        return {
            "zh": "\u622a\u56fe",
            "ja": "\u30b9\u30af\u30ea\u30fc\u30f3\u30b7\u30e7\u30c3\u30c8",
            "en": "Screenshot",
        }.get(lang, "Screenshot")

    def _get_footer_text(self, lang: str) -> str:
        """Get footer text."""
        return {
            "zh": "\u6b64\u624b\u518c\u7531 Web Manual Generator \u81ea\u52a8\u751f\u6210",
            "ja": "\u3053\u306e\u30de\u30cb\u30e5\u30a2\u30eb\u306f Web Manual Generator \u306b\u3088\u3063\u3066\u81ea\u52d5\u751f\u6210\u3055\u308c\u307e\u3057\u305f",
            "en": "This manual was automatically generated by Web Manual Generator",
        }.get(lang, "Generated by Web Manual Generator")


def generate_manual_from_recording(
    recording_dir: str | Path,
    output_format: str = "html",
    language: str = "zh",
) -> Path:
    """
    Convenience function to generate a manual from a recording directory.

    Args:
        recording_dir: Directory containing action_log.json and screenshots
        output_format: "html" or "pdf"
        language: Output language (zh, ja, en)

    Returns:
        Path to the generated manual
    """
    recording_dir = Path(recording_dir)

    # Find action log
    action_log_path = recording_dir / "action_log.json"
    if not action_log_path.exists():
        raise FileNotFoundError(f"action_log.json not found in {recording_dir}")

    # Create generator
    generator = ManualGenerator(
        output_dir=recording_dir / "manual",
        language=language,
        embed_images=(output_format == "pdf"),
    )

    # Generate manual
    screenshots_dir = recording_dir / "screenshots"

    if output_format == "pdf":
        return generator.generate_pdf(
            action_log_path,
            output_name="manual",
            screenshots_dir=screenshots_dir,
        )
    else:
        return generator.generate_html(
            action_log_path,
            output_name="manual",
            screenshots_dir=screenshots_dir,
        )
