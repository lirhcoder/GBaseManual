"""
AI-powered description generator for operation manuals.

Uses vision models to analyze screenshots and generate natural,
context-aware descriptions for each step.

Supported providers:
- Gemini (Google) - Default, lowest cost
- Claude (Anthropic)
- OpenAI GPT-4o
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..capture.action_log import ActionLog, ActionStep
from ..i18n import get_text

console = Console()

# Supported AI providers
AIProvider = Literal["gemini", "claude", "openai"]


class DescriptionGenerator:
    """
    Generates intelligent descriptions for manual steps using AI vision models.

    Analyzes screenshots in context to understand user intent and
    generate natural, helpful descriptions.

    Supported providers:
    - gemini: Google Gemini (default, lowest cost)
    - claude: Anthropic Claude
    - openai: OpenAI GPT-4o
    """

    def __init__(
        self,
        language: str = "zh",
        api_key: Optional[str] = None,
        provider: AIProvider = "gemini",
        model: Optional[str] = None,
    ):
        self.language = language
        self.provider = provider
        self.api_key = api_key or self._get_api_key(provider)

        # Set default model based on provider
        self.model = model or self._get_default_model(provider)

        # Language-specific prompts
        self.language_names = {
            "zh": "中文",
            "ja": "日本語",
            "en": "English",
        }

    def _get_api_key(self, provider: str) -> Optional[str]:
        """Get API key from environment based on provider."""
        import os
        key_map = {
            "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
            "claude": ["ANTHROPIC_API_KEY"],
            "openai": ["OPENAI_API_KEY"],
        }
        for key_name in key_map.get(provider, []):
            key = os.environ.get(key_name)
            if key:
                return key
        return None

    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider."""
        return {
            "gemini": "gemini-2.0-flash",  # 最便宜且支持视觉
            "claude": "claude-sonnet-4-20250514",
            "openai": "gpt-4o-mini",
        }.get(provider, "gemini-2.0-flash")

    def _encode_image(self, image_path: Path) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def _get_media_type(self, image_path: Path) -> str:
        """Get media type for image."""
        suffix = image_path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

    async def generate_descriptions(
        self,
        action_log: ActionLog,
        screenshots_dir: Path,
        context_window: int = 3,  # Number of previous steps to consider
    ) -> ActionLog:
        """
        Generate AI-enhanced descriptions for all steps in an action log.

        Args:
            action_log: The action log to enhance
            screenshots_dir: Directory containing screenshots
            context_window: Number of previous steps to include for context

        Returns:
            Updated ActionLog with AI-generated descriptions
        """
        if not self.api_key:
            console.print("[yellow]Warning: No API key found. Using original descriptions.[/yellow]")
            return action_log

        console.print(f"\n[blue]Generating AI descriptions ({len(action_log.steps)} steps)...[/blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing screenshots...", total=len(action_log.steps))

            for i, step in enumerate(action_log.steps):
                progress.update(task, description=f"Step {step.id}: Analyzing...")

                # Get context (previous steps)
                context_steps = action_log.steps[max(0, i - context_window):i]

                # Generate description
                try:
                    new_description = await self._generate_step_description(
                        step=step,
                        context_steps=context_steps,
                        screenshots_dir=screenshots_dir,
                        manual_title=action_log.title,
                    )

                    # Update step descriptions
                    if self.language == "zh":
                        step.description_zh = new_description
                        step.description = new_description
                    elif self.language == "ja":
                        step.description_ja = new_description
                        step.description = new_description
                    else:
                        step.description_en = new_description
                        step.description = new_description

                except Exception as e:
                    console.print(f"[yellow]Step {step.id}: Using original description ({e})[/yellow]")

                progress.advance(task)

        console.print("[green]AI descriptions generated successfully![/green]")
        return action_log

    async def _generate_step_description(
        self,
        step: ActionStep,
        context_steps: List[ActionStep],
        screenshots_dir: Path,
        manual_title: str,
    ) -> str:
        """Generate description for a single step."""
        # Build context summary
        context_summary = self._build_context_summary(context_steps)

        # Prepare images
        images = []

        # Add current step screenshot
        if step.screenshot:
            current_screenshot = screenshots_dir / step.screenshot
            if current_screenshot.exists():
                images.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self._get_media_type(current_screenshot),
                        "data": self._encode_image(current_screenshot),
                    }
                })

        # Build prompt
        prompt = self._build_prompt(step, context_summary, manual_title)

        # Call API
        return await self._call_vision_api(images, prompt)

    def _build_context_summary(self, context_steps: List[ActionStep]) -> str:
        """Build a summary of previous steps for context."""
        if not context_steps:
            return "This is the first step."

        summary_parts = []
        for s in context_steps:
            action_desc = {
                "navigate": f"Navigated to {s.url or 'a page'}",
                "click": f"Clicked on '{s.selector or 'an element'}'",
                "fill": f"Entered text in '{s.selector or 'a field'}'",
                "select": f"Selected option in '{s.selector or 'a dropdown'}'",
            }.get(s.action, s.action)
            summary_parts.append(f"- Step {s.id}: {action_desc}")

        return "Previous steps:\n" + "\n".join(summary_parts)

    def _build_prompt(
        self,
        step: ActionStep,
        context_summary: str,
        manual_title: str,
    ) -> str:
        """Build the prompt for description generation."""
        lang_name = self.language_names.get(self.language, "English")

        action_info = f"""
Action type: {step.action}
Selector: {step.selector or 'N/A'}
Value: {step.value or 'N/A'}
Page URL: {step.page_url or 'N/A'}
Page title: {step.page_title or 'N/A'}
"""

        prompt = f"""You are writing a user manual titled "{manual_title}".

Analyze the screenshot and write a clear, helpful description for this step in {lang_name}.

{context_summary}

Current step information:
{action_info}

The screenshot shows the current state of the page with:
- A red circle indicating where the user is clicking/interacting
- A blue outline highlighting the target element (if applicable)

Instructions:
1. Describe what the user should do in this step
2. Explain WHY this action is needed (based on the workflow context)
3. Mention any important visual cues the user should look for
4. Keep the description concise but informative (2-3 sentences)
5. Write in {lang_name}
6. Use a friendly, instructional tone

Output only the description text, no additional formatting or labels."""

        return prompt

    async def _call_vision_api(self, images: List[Dict], prompt: str) -> str:
        """Call the vision API based on configured provider."""
        if self.provider == "gemini":
            return await self._call_gemini_vision(images, prompt)
        elif self.provider == "claude":
            return await self._call_claude_vision(images, prompt)
        elif self.provider == "openai":
            return await self._call_openai_vision(images, prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _call_gemini_vision(self, images: List[Dict], prompt: str) -> str:
        """Call Google Gemini vision API."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Build content parts
            content_parts = []

            for img in images:
                if img["type"] == "image":
                    # New API uses Part.from_bytes
                    image_bytes = base64.b64decode(img["source"]["data"])
                    content_parts.append(
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type=img["source"]["media_type"],
                        )
                    )

            content_parts.append(prompt)

            response = client.models.generate_content(
                model=self.model,
                contents=content_parts,
            )
            return response.text.strip()

        except ImportError:
            raise ImportError(
                "google-genai is required for Gemini. "
                "Install it with: pip install google-genai"
            )
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {e}")

    async def _call_claude_vision(self, images: List[Dict], prompt: str) -> str:
        """Call Anthropic Claude vision API."""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.api_key)

            # Build message content
            content = []
            for img in images:
                content.append(img)
            content.append({"type": "text", "text": prompt})

            message = client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[
                    {"role": "user", "content": content}
                ]
            )

            return message.content[0].text.strip()

        except ImportError:
            raise ImportError(
                "anthropic is required for Claude. "
                "Install it with: pip install anthropic"
            )
        except Exception as e:
            raise RuntimeError(f"Claude API call failed: {e}")

    async def _call_openai_vision(self, images: List[Dict], prompt: str) -> str:
        """Call OpenAI vision API."""
        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key)

            # Convert images to OpenAI format
            content = []
            for img in images:
                if img["type"] == "image":
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{img['source']['media_type']};base64,{img['source']['data']}"
                        }
                    })
            content.append({"type": "text", "text": prompt})

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": content}
                ],
                max_tokens=500,
            )

            return response.choices[0].message.content.strip()

        except ImportError:
            raise ImportError(
                "openai is required for OpenAI. "
                "Install it with: pip install openai"
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {e}")


async def enhance_action_log_with_ai(
    action_log: ActionLog | str | Path,
    screenshots_dir: str | Path,
    language: str = "zh",
    api_key: Optional[str] = None,
    provider: AIProvider = "gemini",
    model: Optional[str] = None,
) -> ActionLog:
    """
    Convenience function to enhance an action log with AI descriptions.

    Args:
        action_log: ActionLog object or path to JSON file
        screenshots_dir: Directory containing screenshots
        language: Target language for descriptions
        api_key: API key (uses env var if not provided)
        provider: AI provider - "gemini" (default), "claude", or "openai"
        model: Optional model name override

    Returns:
        Enhanced ActionLog
    """
    # Load action log if path provided
    if isinstance(action_log, (str, Path)):
        action_log = ActionLog.load(action_log)

    screenshots_dir = Path(screenshots_dir)

    generator = DescriptionGenerator(
        language=language,
        api_key=api_key,
        provider=provider,
        model=model,
    )
    return await generator.generate_descriptions(action_log, screenshots_dir)


def generate_descriptions_sync(
    action_log: ActionLog | str | Path,
    screenshots_dir: str | Path,
    language: str = "zh",
    api_key: Optional[str] = None,
    provider: AIProvider = "gemini",
    model: Optional[str] = None,
) -> ActionLog:
    """Synchronous wrapper for enhance_action_log_with_ai."""
    import asyncio
    return asyncio.run(enhance_action_log_with_ai(
        action_log, screenshots_dir, language, api_key, provider, model
    ))
