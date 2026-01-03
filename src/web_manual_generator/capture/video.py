"""
Video recording management using Playwright's built-in recording.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING
import shutil

if TYPE_CHECKING:
    from playwright.async_api import Page, BrowserContext


class VideoRecorder:
    """
    Manages video recording for browser sessions.

    Playwright handles video recording at the context level, so this class
    provides utilities for managing and processing recorded videos.
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._recordings: list[Path] = []

    @staticmethod
    def get_context_options(
        output_dir: str | Path,
        width: int = 1280,
        height: int = 720,
    ) -> dict:
        """
        Get browser context options for video recording.

        Use these options when creating a new browser context to enable recording.

        Args:
            output_dir: Directory to save videos
            width: Video width
            height: Video height

        Returns:
            Dictionary of context options
        """
        return {
            "record_video_dir": str(output_dir),
            "record_video_size": {"width": width, "height": height},
        }

    async def get_video_path(self, page: "Page") -> Optional[Path]:
        """
        Get the path to a page's recorded video.

        Note: The video path is only available after the page is closed.

        Args:
            page: Playwright page instance

        Returns:
            Path to the video file, or None if no video
        """
        if page.video:
            path = await page.video.path()
            return Path(path) if path else None
        return None

    async def save_video(
        self,
        page: "Page",
        filename: str,
        delete_original: bool = True,
    ) -> Optional[Path]:
        """
        Save the page's video with a custom filename.

        Args:
            page: Playwright page instance
            filename: Desired filename (with or without extension)
            delete_original: Whether to delete the original temp file

        Returns:
            Path to the saved video, or None if no video
        """
        video_path = await self.get_video_path(page)
        if not video_path:
            return None

        # Ensure filename has extension
        if not filename.endswith(".webm"):
            filename += ".webm"

        target_path = self.output_dir / filename

        # Copy or move the video
        if delete_original:
            shutil.move(str(video_path), str(target_path))
        else:
            shutil.copy2(str(video_path), str(target_path))

        self._recordings.append(target_path)
        return target_path

    async def finalize_recording(
        self,
        page: "Page",
        final_name: str = "recording",
    ) -> Optional[Path]:
        """
        Finalize the video recording by closing the page and saving the video.

        Args:
            page: Playwright page instance
            final_name: Name for the final video file

        Returns:
            Path to the saved video
        """
        # Get video reference before closing
        video = page.video

        # Close the page to finalize video
        await page.close()

        if video:
            original_path = await video.path()
            if original_path:
                original = Path(original_path)
                if original.exists():
                    final_path = self.output_dir / f"{final_name}.webm"
                    shutil.move(str(original), str(final_path))
                    self._recordings.append(final_path)
                    return final_path

        return None

    @property
    def recordings(self) -> list[Path]:
        """Get list of all recorded video paths."""
        return self._recordings.copy()

    def clear_recordings(self) -> None:
        """Clear the list of recordings (does not delete files)."""
        self._recordings.clear()


class VideoChapterMarker:
    """
    Utility for marking chapters/sections in recordings.

    Since we can't add actual markers to webm files easily,
    this creates a metadata file with timestamps.
    """

    def __init__(self):
        self._chapters: list[dict] = []
        self._start_time: Optional[float] = None

    def start(self) -> None:
        """Start timing for chapters."""
        import time
        self._start_time = time.time()
        self._chapters.clear()

    def mark_chapter(
        self,
        title: str,
        title_zh: str = "",
        title_ja: str = "",
        title_en: str = "",
    ) -> None:
        """
        Mark a new chapter at the current time.

        Args:
            title: Chapter title
            title_zh: Chinese title
            title_ja: Japanese title
            title_en: English title
        """
        import time

        if self._start_time is None:
            self.start()

        elapsed = time.time() - self._start_time
        self._chapters.append({
            "time": elapsed,
            "time_formatted": self._format_time(elapsed),
            "title": title,
            "title_zh": title_zh or title,
            "title_ja": title_ja or title,
            "title_en": title_en or title,
        })

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def get_chapters(self) -> list[dict]:
        """Get all marked chapters."""
        return self._chapters.copy()

    def save_chapters(self, path: str | Path) -> None:
        """Save chapters to a JSON file."""
        import json
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._chapters, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_chapters(cls, path: str | Path) -> list[dict]:
        """Load chapters from a JSON file."""
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
